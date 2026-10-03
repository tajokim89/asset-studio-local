import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { TransformControls } from "three/addons/controls/TransformControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const SAMPLE_MODEL_URL = "/assets/models/generated/ual1_idle_loop.glb";
const SAMPLE_MODEL_NAME = "ual1_idle_loop.glb";
const ACTION_CLIP_NAMES = Object.freeze({
  idle: ["idle", "survey"],
  walk: ["walk"],
  run: ["run"],
});

const viewport = document.getElementById("pipelineThreeViewport");
const statusNode = document.getElementById("pipelineViewerStatus");
const transformPanel = document.getElementById("pipelineTransformPanel");

let renderer = null;
let scene = null;
let camera = null;
let orbitControls = null;
let transformControls = null;
let modelRoot = null;
let modelContent = null;
let mixer = null;
let activeAnimation = null;
let animationClips = [];
let currentAction = "idle";
let isPlaying = true;
let playbackSpeed = 1;
let cameraMode = "perspective";
let orthographicViewSize = 4;
let modelBounds = null;
let resizeObserver = null;
const timer = new THREE.Timer();
timer.connect(document);

const transformFields = {
  position: ["X", "Y", "Z"].map(axis => document.getElementById(`pipelinePosition${axis}`)),
  rotation: ["X", "Y", "Z"].map(axis => document.getElementById(`pipelineRotation${axis}`)),
  scale: ["X", "Y", "Z"].map(axis => document.getElementById(`pipelineScale${axis}`)),
};

function setStatus(state, message) {
  if (!statusNode) return;
  statusNode.dataset.state = state;
  statusNode.textContent = message;
  statusNode.hidden = false;
}

function setTransformEnabled(enabled) {
  if (!transformPanel) return;
  transformPanel.classList.toggle("is-disabled", !enabled);
  transformPanel.querySelectorAll("input, select, button").forEach(control => {
    control.disabled = !enabled;
  });
}

function initializeViewer() {
  if (!viewport) return false;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
  } catch (error) {
    setStatus("error", `WebGL 초기화 실패: ${error.message}`);
    return false;
  }

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.domElement.className = "pipeline-three-canvas";
  renderer.domElement.setAttribute("aria-label", "실제 3D 모델 뷰어");
  viewport.prepend(renderer.domElement);

  scene = new THREE.Scene();
  camera = createCamera(cameraMode, 1);
  camera.position.set(3, 2, 4);

  orbitControls = new OrbitControls(camera, renderer.domElement);
  orbitControls.enableDamping = true;
  orbitControls.dampingFactor = 0.08;
  orbitControls.screenSpacePanning = true;
  orbitControls.target.set(0, 0.9, 0);

  transformControls = new TransformControls(camera, renderer.domElement);
  transformControls.setMode("translate");
  scene.add(transformControls.getHelper());
  transformControls.addEventListener("mouseDown", () => { orbitControls.enabled = false; });
  transformControls.addEventListener("mouseUp", () => { orbitControls.enabled = true; });
  transformControls.addEventListener("objectChange", syncTransformFields);

  scene.add(new THREE.HemisphereLight(0xc5ddff, 0x273041, 2.1));
  const keyLight = new THREE.DirectionalLight(0xffffff, 3.2);
  keyLight.position.set(4, 7, 5);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  scene.add(keyLight);
  const rimLight = new THREE.DirectionalLight(0x799cff, 1.5);
  rimLight.position.set(-5, 3, -4);
  scene.add(rimLight);

  const grid = new THREE.GridHelper(20, 40, 0x52627a, 0x2e3949);
  grid.name = "viewer-grid";
  grid.material.transparent = true;
  grid.material.opacity = 0.5;
  scene.add(grid);

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(20, 20),
    new THREE.ShadowMaterial({ color: 0x000000, opacity: 0.22 }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.002;
  ground.receiveShadow = true;
  ground.name = "viewer-ground";
  scene.add(ground);

  resizeObserver = new ResizeObserver(resizeViewer);
  resizeObserver.observe(viewport);
  bindTransformUi();
  setTransformEnabled(false);
  setStatus("empty", "GLB 모델을 선택하세요");
  renderer.setAnimationLoop(renderFrame);
  return true;
}

function resizeViewer() {
  if (!renderer || !camera || !viewport) return;
  const width = Math.max(1, viewport.clientWidth);
  const height = Math.max(1, viewport.clientHeight);
  renderer.setSize(width, height, false);
  const aspect = width / height;
  if (camera.isOrthographicCamera) {
    const halfHeight = orthographicViewSize * 0.5;
    camera.left = -halfHeight * aspect;
    camera.right = halfHeight * aspect;
    camera.top = halfHeight;
    camera.bottom = -halfHeight;
  } else {
    camera.aspect = aspect;
  }
  camera.updateProjectionMatrix();
}

function createCamera(mode, aspect) {
  if (mode === "ortho") {
    const halfHeight = orthographicViewSize * 0.5;
    return new THREE.OrthographicCamera(-halfHeight * aspect, halfHeight * aspect, halfHeight, -halfHeight, 0.01, 2000);
  }
  return new THREE.PerspectiveCamera(36, aspect, 0.01, 2000);
}

function setCameraMode(mode) {
  const nextMode = mode === "ortho" ? "ortho" : "perspective";
  if (!renderer || nextMode === cameraMode) return;
  const previousPosition = camera.position.clone();
  const previousQuaternion = camera.quaternion.clone();
  cameraMode = nextMode;
  camera = createCamera(cameraMode, Math.max(1, viewport.clientWidth) / Math.max(1, viewport.clientHeight));
  camera.position.copy(previousPosition);
  camera.quaternion.copy(previousQuaternion);
  orbitControls.object = camera;
  transformControls.camera = camera;
  document.getElementById("pipelineCameraLabel").textContent = cameraMode === "ortho" ? "ORTHOGRAPHIC" : "PERSPECTIVE · 36°";
  resizeViewer();
  frameModel();
}

function renderFrame() {
  if (!renderer || !scene || !camera) return;
  timer.update();
  const delta = Math.min(timer.getDelta(), 0.05);
  if (mixer && isPlaying) mixer.update(delta * playbackSpeed);
  orbitControls?.update();
  renderer.render(scene, camera);
}

function disposeMaterial(material) {
  if (!material) return;
  for (const value of Object.values(material)) {
    if (value?.isTexture) value.dispose();
  }
  material.dispose?.();
}

function clearModel() {
  transformControls?.detach();
  if (modelRoot) {
    scene.remove(modelRoot);
    modelRoot.traverse(object => {
      object.geometry?.dispose?.();
      if (Array.isArray(object.material)) object.material.forEach(disposeMaterial);
      else disposeMaterial(object.material);
    });
  }
  mixer?.stopAllAction();
  modelRoot = null;
  modelContent = null;
  mixer = null;
  activeAnimation = null;
  animationClips = [];
  modelBounds = null;
  setTransformEnabled(false);
}

function countSceneObjects(root) {
  const counts = { meshes: 0, bones: 0, materials: new Set() };
  root.traverse(object => {
    if (object.isMesh || object.isSkinnedMesh) {
      counts.meshes += 1;
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.filter(Boolean).forEach(material => counts.materials.add(material.uuid));
      object.castShadow = true;
      object.receiveShadow = true;
    }
    if (object.isBone) counts.bones += 1;
  });
  return { meshes: counts.meshes, bones: counts.bones, materials: counts.materials.size };
}

function normalizeModelPivot(content) {
  content.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(content);
  if (box.isEmpty()) throw new Error("표시할 메시가 없습니다.");
  const center = box.getCenter(new THREE.Vector3());
  content.position.x -= center.x;
  content.position.y -= box.min.y;
  content.position.z -= center.z;
  content.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(content);
}

async function loadFromUrl(url, label, revokeAfterLoad = false) {
  if (!renderer) throw new Error("3D 뷰어가 준비되지 않았습니다.");
  clearModel();
  setStatus("loading", `${label} 로딩 중…`);
  try {
    const loader = new GLTFLoader();
    const gltf = await loader.loadAsync(url);
    modelRoot = new THREE.Group();
    modelRoot.name = "EditableModelRoot";
    modelContent = gltf.scene;
    modelBounds = normalizeModelPivot(modelContent);
    modelRoot.add(modelContent);
    scene.add(modelRoot);
    transformControls.attach(modelRoot);
    animationClips = gltf.animations || [];
    mixer = animationClips.length ? new THREE.AnimationMixer(modelContent) : null;
    const counts = countSceneObjects(modelContent);
    setTransformEnabled(true);
    resetTransform();
    frameModel();
    setAction(currentAction);
    setStatus("ready", `${label} · 메시 ${counts.meshes} · 본 ${counts.bones} · 애니메이션 ${animationClips.length}`);
    window.dispatchEvent(new CustomEvent("asset-studio:3d-loaded", {
      detail: { ...counts, animations: animationClips.map(clip => clip.name) },
    }));
    return { ...counts, animations: animationClips.map(clip => clip.name) };
  } catch (error) {
    clearModel();
    setStatus("error", `모델 로드 실패: ${error.message}`);
    window.dispatchEvent(new CustomEvent("asset-studio:3d-error", { detail: { message: error.message } }));
    throw error;
  } finally {
    if (revokeAfterLoad) URL.revokeObjectURL(url);
  }
}

function loadFile(file) {
  if (!file || !String(file.name).toLowerCase().endsWith(".glb")) {
    return Promise.reject(new Error("현재 실제 뷰어는 GLB 파일을 지원합니다."));
  }
  return loadFromUrl(URL.createObjectURL(file), file.name, true);
}

function loadSample() {
  return loadFromUrl(SAMPLE_MODEL_URL, SAMPLE_MODEL_NAME);
}

function loadAsset(url, label = "generated_model.glb") {
  if (typeof url !== "string" || !url.startsWith("/assets/") || !url.toLowerCase().endsWith(".glb")) {
    return Promise.reject(new Error("Asset Studio가 만든 GLB URL이 필요합니다."));
  }
  return loadFromUrl(url, label);
}

function frameModel() {
  if (!modelRoot || !modelBounds || !camera || !orbitControls) return;
  modelRoot.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(modelRoot);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const radius = Math.max(size.length() * 0.5, 0.25);
  const cameraDistance = camera.isOrthographicCamera
    ? Math.max(radius * 4, 2)
    : radius / Math.sin(THREE.MathUtils.degToRad(camera.fov * 0.5));
  if (camera.isOrthographicCamera) {
    const aspect = Math.max(1, viewport.clientWidth) / Math.max(1, viewport.clientHeight);
    orthographicViewSize = Math.max(size.y, size.x / aspect, size.z) * 1.35;
    resizeViewer();
  }
  camera.near = Math.max(cameraDistance / 1000, 0.001);
  camera.far = Math.max(cameraDistance * 50, 100);
  camera.position.set(center.x + cameraDistance * 0.72, center.y + cameraDistance * 0.38, center.z + cameraDistance * 0.72);
  camera.updateProjectionMatrix();
  orbitControls.target.copy(center);
  orbitControls.minDistance = radius * 0.25;
  orbitControls.maxDistance = cameraDistance * 8;
  orbitControls.update();
}

function capturePixelReference({ size = 1024, width = size, height = size, lockedBounds = null } = {}) {
  if (!renderer || !scene || !camera || !modelRoot) {
    throw new Error("먼저 3D 모델을 불러오세요.");
  }
  const outputWidth = Number(width);
  const outputHeight = Number(height);
  if (![outputWidth, outputHeight].every(value => Number.isInteger(value) && value >= 256 && value <= 2048)) {
    throw new Error("3D 캡처 가로·세로는 각각 256~2048px 정수여야 합니다.");
  }

  modelRoot.updateMatrixWorld(true);
  const bounds = lockedBounds?.isBox3 ? lockedBounds.clone() : new THREE.Box3().setFromObject(modelRoot);
  if (bounds.isEmpty()) throw new Error("캡처할 3D 메시가 없습니다.");
  const center = bounds.getCenter(new THREE.Vector3());
  const sphere = bounds.getBoundingSphere(new THREE.Sphere());
  const boundsSize = bounds.getSize(new THREE.Vector3());
  const aspect = outputWidth / outputHeight;
  const viewHeight = Math.max(boundsSize.y * 1.18, boundsSize.x / aspect * 1.18, sphere.radius * 2.15, 0.25);
  const viewWidth = viewHeight * aspect;
  const viewDirection = camera.getWorldDirection(new THREE.Vector3()).normalize();
  const captureCamera = new THREE.OrthographicCamera(
    -viewWidth / 2,
    viewWidth / 2,
    viewHeight / 2,
    -viewHeight / 2,
    0.01,
    Math.max(sphere.radius * 20, 100),
  );
  captureCamera.position.copy(center).addScaledVector(viewDirection, -Math.max(sphere.radius * 4, 2));
  captureCamera.quaternion.copy(camera.quaternion);
  captureCamera.updateMatrixWorld(true);
  captureCamera.updateProjectionMatrix();

  const target = new THREE.WebGLRenderTarget(outputWidth, outputHeight, {
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    format: THREE.RGBAFormat,
    type: THREE.UnsignedByteType,
    depthBuffer: true,
    stencilBuffer: false,
  });
  target.texture.colorSpace = THREE.SRGBColorSpace;
  const previousTarget = renderer.getRenderTarget();
  const previousBackground = scene.background;
  const hiddenObjects = [
    scene.getObjectByName("viewer-grid"),
    scene.getObjectByName("viewer-ground"),
    transformControls?.getHelper?.(),
  ].filter(Boolean).map(object => ({ object, visible: object.visible }));
  const pixels = new Uint8Array(outputWidth * outputHeight * 4);

  try {
    hiddenObjects.forEach(({ object }) => { object.visible = false; });
    scene.background = new THREE.Color(0xf3f5f7);
    renderer.setRenderTarget(target);
    renderer.clear(true, true, true);
    renderer.render(scene, captureCamera);
    renderer.readRenderTargetPixels(target, 0, 0, outputWidth, outputHeight, pixels);
  } finally {
    renderer.setRenderTarget(previousTarget);
    scene.background = previousBackground;
    hiddenObjects.forEach(({ object, visible }) => { object.visible = visible; });
    target.dispose();
    renderer.render(scene, camera);
  }

  const canvas = document.createElement("canvas");
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) throw new Error("3D 캡처 이미지를 만들 수 없습니다.");
  const imageData = context.createImageData(outputWidth, outputHeight);
  const rowBytes = outputWidth * 4;
  for (let y = 0; y < outputHeight; y += 1) {
    const sourceStart = (outputHeight - y - 1) * rowBytes;
    imageData.data.set(pixels.subarray(sourceStart, sourceStart + rowBytes), y * rowBytes);
  }
  context.putImageData(imageData, 0, 0);
  return {
    dataUrl: canvas.toDataURL("image/png"),
    width: outputWidth,
    height: outputHeight,
    camera: "orthographic-current-view",
  };
}

function dataUrlImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("애니메이션 캡처 프레임을 조합하지 못했습니다."));
    image.src = dataUrl;
  });
}

async function captureAnimationSheet({ action = currentAction, frameCount = 8, frameWidth = 256, frameHeight = 512 } = {}) {
  if (!modelRoot || !mixer) throw new Error("애니메이션이 포함된 3D 모델을 먼저 불러오세요.");
  if (!findClip(action)) throw new Error(`${action.toUpperCase()} 애니메이션 클립을 찾을 수 없습니다.`);
  if (frameCount !== 8) throw new Error("현재 로컬 파이프라인은 8프레임 동작 시트를 사용합니다.");

  const wasPlaying = isPlaying;
  setPlaying(false);
  setAction(action);
  const captures = [];
  try {
    const cycleBounds = new THREE.Box3();
    for (let index = 0; index < frameCount; index += 1) {
      seek(index / frameCount * 100);
      modelRoot.updateMatrixWorld(true);
      cycleBounds.expandByObject(modelRoot);
    }
    if (cycleBounds.isEmpty()) throw new Error("애니메이션 프레임의 3D 경계를 계산하지 못했습니다.");
    for (let index = 0; index < frameCount; index += 1) {
      seek(index / frameCount * 100);
      captures.push(capturePixelReference({ width: frameWidth, height: frameHeight, lockedBounds: cycleBounds }));
    }
  } finally {
    setPlaying(wasPlaying);
  }

  const images = await Promise.all(captures.map(capture => dataUrlImage(capture.dataUrl)));
  const canvas = document.createElement("canvas");
  canvas.width = frameWidth * 4;
  canvas.height = frameHeight * 2;
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) throw new Error("애니메이션 가이드 시트를 만들 수 없습니다.");
  context.fillStyle = "#f3f5f7";
  context.fillRect(0, 0, canvas.width, canvas.height);
  images.forEach((image, index) => {
    context.drawImage(image, (index % 4) * frameWidth, Math.floor(index / 4) * frameHeight, frameWidth, frameHeight);
  });
  return {
    dataUrl: canvas.toDataURL("image/png"),
    firstFrameDataUrl: captures[0].dataUrl,
    width: canvas.width,
    height: canvas.height,
    frameCount,
    frameWidth,
    frameHeight,
    action,
  };
}

function findClip(action) {
  const candidates = ACTION_CLIP_NAMES[action] || [action];
  return animationClips.find(clip => candidates.some(name => clip.name.toLowerCase().includes(name))) || null;
}

function setAction(action) {
  currentAction = ACTION_CLIP_NAMES[action] ? action : "idle";
  if (!mixer) return;
  const clip = findClip(currentAction);
  if (!clip) return;
  const next = mixer.clipAction(clip);
  if (activeAnimation === next) {
    next.paused = !isPlaying;
    return;
  }
  if (activeAnimation && activeAnimation !== next) activeAnimation.fadeOut(0.15);
  next.reset().setLoop(THREE.LoopRepeat, Infinity).fadeIn(0.15).play();
  next.paused = !isPlaying;
  activeAnimation = next;
}

function setPlaying(value) {
  isPlaying = Boolean(value);
  if (activeAnimation) activeAnimation.paused = !isPlaying;
}

function setPlaybackSpeed(value) {
  const parsed = Number(value);
  playbackSpeed = Number.isFinite(parsed) ? THREE.MathUtils.clamp(parsed, 0.1, 3) : 1;
}

function seek(percent) {
  if (!activeAnimation) return;
  const duration = activeAnimation.getClip().duration || 1;
  activeAnimation.time = THREE.MathUtils.clamp(Number(percent) || 0, 0, 100) / 100 * duration;
  mixer.update(0);
}

function syncTransformFields() {
  if (!modelRoot) return;
  const positions = modelRoot.position.toArray();
  const rotations = [modelRoot.rotation.x, modelRoot.rotation.y, modelRoot.rotation.z]
    .map(THREE.MathUtils.radToDeg);
  const scales = modelRoot.scale.toArray();
  transformFields.position.forEach((field, index) => { if (field) field.value = positions[index].toFixed(3); });
  transformFields.rotation.forEach((field, index) => { if (field) field.value = rotations[index].toFixed(1); });
  transformFields.scale.forEach((field, index) => { if (field) field.value = scales[index].toFixed(3); });
  publishTransformState();
}

function publishTransformState() {
  if (!modelRoot || !viewport) return;
  viewport.dataset.position = modelRoot.position.toArray().map(value => value.toFixed(3)).join(",");
  viewport.dataset.rotation = [modelRoot.rotation.x, modelRoot.rotation.y, modelRoot.rotation.z]
    .map(value => THREE.MathUtils.radToDeg(value).toFixed(1)).join(",");
  viewport.dataset.scale = modelRoot.scale.toArray().map(value => value.toFixed(3)).join(",");
}

function applyTransformFields() {
  if (!modelRoot) return;
  const position = transformFields.position.map(field => Number(field?.value) || 0);
  const rotation = transformFields.rotation.map(field => THREE.MathUtils.degToRad(Number(field?.value) || 0));
  const scale = transformFields.scale.map(field => Math.max(0.001, Number(field?.value) || 1));
  modelRoot.position.fromArray(position);
  modelRoot.rotation.set(...rotation);
  modelRoot.scale.fromArray(scale);
  modelRoot.updateMatrixWorld(true);
  publishTransformState();
  transformControls?.dispatchEvent({ type: "change" });
}

function resetTransform() {
  if (!modelRoot) return;
  modelRoot.position.set(0, 0, 0);
  modelRoot.rotation.set(0, 0, 0);
  modelRoot.scale.set(1, 1, 1);
  modelRoot.updateMatrixWorld(true);
  syncTransformFields();
}

function setTransformMode(mode) {
  if (!transformControls || !["translate", "rotate", "scale"].includes(mode)) return;
  transformControls.setMode(mode);
  document.querySelectorAll("[data-transform-mode]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.transformMode === mode));
  });
}

function bindTransformUi() {
  Object.values(transformFields).flat().forEach(field => field?.addEventListener("input", applyTransformFields));
  document.querySelectorAll("[data-transform-mode]").forEach(button => {
    button.addEventListener("click", () => setTransformMode(button.dataset.transformMode));
  });
  document.getElementById("pipelineTransformSpace")?.addEventListener("change", event => {
    transformControls?.setSpace(event.target.value);
  });
  document.getElementById("pipelineResetTransform")?.addEventListener("click", () => {
    resetTransform();
    frameModel();
  });
  document.getElementById("pipelineFrameModel")?.addEventListener("click", frameModel);
  document.getElementById("pipelineCamera")?.addEventListener("change", event => setCameraMode(event.target.value));
  viewport.addEventListener("keydown", event => {
    const mode = ({ w: "translate", e: "rotate", r: "scale" })[event.key.toLowerCase()];
    if (mode) {
      event.preventDefault();
      setTransformMode(mode);
    }
  });
}

function resetAll() {
  clearModel();
  setStatus("empty", "GLB 모델을 선택하세요");
}

const initialized = initializeViewer();
const api = Object.freeze({
  loadFile,
  loadSample,
  loadAsset,
  frameModel,
  resetTransform,
  resetAll,
  setAction,
  setPlaying,
  setPlaybackSpeed,
  setCameraMode,
  capturePixelReference,
  captureAnimationSheet,
  seek,
  setTransformMode,
});
window.AssetStudioPixelPipelineViewer = api;
window.dispatchEvent(new CustomEvent("asset-studio:3d-viewer-ready"));

if (initialized) {
  const state = window.AssetStudioPixelPipeline?.serialize?.();
  if (state?.action) setAction(state.action);
  if (state?.model?.url) loadAsset(state.model.url, state.model.name).catch(() => {});
  else if (state?.model?.sample) loadSample().catch(() => {});
}
