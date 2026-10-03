(function () {
  "use strict";
  const Core = window.PixelPipelineCore;
  if (!Core) return;

  const $ = id => document.getElementById(id);
  const STORAGE_KEY = Core.SCHEMA;
  const MAX_MODEL_BYTES = 500 * 1024 * 1024;
  const MODEL_EXTENSIONS = new Set(["glb"]);
  const UAL_IDLE_SAMPLE = Object.freeze({
    name: "ual1_idle_loop.glb",
    size: 820_044,
    type: "GLB",
    sample: true,
    source: "sample",
    url: "/assets/models/generated/ual1_idle_loop.glb",
    referenceUrl: "/assets/models/generated/chairman_reference.png",
    blendUrl: "/assets/models/generated/ual1_idle_loop.blend",
    approvedAtlasUrl: "/assets/generated/3d-actions/chairman-front-idle-approved/idle_96x192_atlas.png",
    approvedPreviewUrl: "/assets/generated/3d-actions/chairman-front-idle-approved/idle_preview.gif",
  });
  const CHIBI_STOMP_8DIR_SAMPLE = Object.freeze({
    name: "ual1_walk_loop.glb",
    size: 747_152,
    type: "GLB",
    sample: true,
    source: "sample",
    url: "/assets/models/generated/ual1_walk_loop.glb",
    referenceUrl: "/assets/models/generated/chairman_reference.png",
    blendUrl: "/assets/models/generated/ual1_walk_loop.blend",
    artifactRoot: "/assets/generated/3d-actions/chairman-chibi-stomp-8dir-v2",
  });
  const STEP_COPY = [
    ["STEP 01", "기본 3D 모델 생성·확정", "어떤 캐릭터 이미지든 정적 GLB로 만든 뒤 형태를 확인합니다."],
    ["STEP 02", "Idle·Walk·Run 만들기", "Blender가 리깅하고 각 동작을 하나씩 추가합니다."],
    ["STEP 03", "대표 포즈 설정", "픽셀화에 사용할 포즈와 카메라·접지 기준을 고정합니다."],
    ["STEP 04", "1방향 AI 픽셀화", "정면 한 방향으로 스타일과 픽셀 밀도를 먼저 승인합니다."],
    ["STEP 05", "8방향 전체 제작", "승인된 규칙을 잠그고 나머지 방향을 일괄 제작합니다."],
    ["STEP 06", "수작업 최종 검수", "모든 방향과 동작의 정체성·루프·접지를 직접 확인합니다."],
  ];
  const NEXT_COPY = [
    ["이미지로 기본 모델을 만든 뒤 확정하세요", "로컬 Hunyuan3D 결과를 회전해 보고 모델 확인 완료를 누릅니다."],
    ["Idle → Walk → Run을 순서대로 만드세요", "각 동작이 끝날 때마다 오른쪽에서 실제 루프를 재생해 확인합니다."],
    ["대표 포즈와 접지 기준을 고정하세요", "Orthographic 카메라와 Root Lock을 권장합니다."],
    ["S 방향 8프레임 시트를 생성·승인하세요", "브라우저가 3D 동작 전체 시트를 캡처하고 로컬 ComfyUI가 엄격 검증과 자동 재시도까지 처리합니다."],
    ["8방향 작업이 모두 끝났는지 확인하세요", "실패한 방향만 다시 생성할 수 있도록 방향별 상태를 보존합니다."],
    ["6개 수동 검수 항목을 모두 확인하세요", "자동 QA 결과와 확대 미리보기를 함께 보고 최종 승인합니다."],
  ];

  let state = loadState();
  let providerHealth = null;
  let generationToken = 0;
  let playing = true;
  let playStartedAt = performance.now();
  let toastTimer = 0;
  let viewerMetrics = null;
  let identityImageDataUrl = null;
  let identityImageName = "";
  let sourceImageDataUrl = null;
  let sourceImageName = "";

  function waitForViewer() {
    const existing = window.AssetStudioPixelPipelineViewer;
    if (existing) return Promise.resolve(existing);
    return new Promise((resolve, reject) => {
      const timeout = window.setTimeout(() => {
        window.removeEventListener("asset-studio:3d-viewer-ready", handleReady);
        reject(new Error("3D 뷰어 초기화 시간이 초과되었습니다. 페이지를 새로고침하세요."));
      }, 8000);
      function handleReady() {
        window.clearTimeout(timeout);
        const viewer = window.AssetStudioPixelPipelineViewer;
        if (viewer) resolve(viewer);
        else reject(new Error("3D 뷰어를 초기화하지 못했습니다."));
      }
      window.addEventListener("asset-studio:3d-viewer-ready", handleReady, { once: true });
    });
  }

  function loadState() {
    try {
      return normalizePipelineState(JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"));
    } catch (_error) {
      localStorage.removeItem(STORAGE_KEY);
      return Core.createState();
    }
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    const status = $("pipelineSaveStatus");
    if (status) {
      status.textContent = "● 방금 저장됨";
      clearTimeout(saveState.timer);
      saveState.timer = setTimeout(() => { status.textContent = "● 초안 자동 저장"; }, 1100);
    }
  }

  function showToast(message) {
    const toast = $("pipelineToast");
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 3400);
  }

  function setWorkspace(name) {
    const active = name === "pipeline";
    document.querySelector(".app")?.classList.toggle("pipeline-mode", active);
    $("pixelPipelineWorkspace").hidden = !active;
    document.querySelectorAll("#studioWorkspaceSwitch button").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.studioWorkspace === name));
    });
    if (active) {
      render();
      refreshProviderHealth();
      requestAnimationFrame(() => window.AssetStudioPixelPipelineViewer?.frameModel?.());
    }
  }

  async function refreshProviderHealth() {
    try {
      const response = await fetch("/api/local-3d-pipeline-health", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("provider health unavailable");
      providerHealth = await response.json();
    } catch (_error) {
      providerHealth = { available: false, reason: "backend_unreachable" };
    }
    renderProviderState();
    return providerHealth;
  }

  function renderProviderState() {
    const node = $("pipelineProviderState");
    if (!node) return;
    const ready = providerHealth?.available === true;
    const modelReady = providerHealth?.model_generation_available === true;
    const blenderReady = providerHealth?.animation_available === true;
    node.dataset.state = ready ? "ready" : "unavailable";
    node.innerHTML = ready
      ? `<i></i><span><b>로컬 제작 도구 준비됨</b><small>Hunyuan3D ${modelReady ? "✓" : "—"} · Blender ${blenderReady ? "✓" : "—"} · 픽셀 변환 ✓</small></span>`
      : `<i></i><span><b>로컬 제작 도구 확인 필요</b><small>Hunyuan3D ${modelReady ? "✓" : "—"} · Blender ${blenderReady ? "✓" : "—"} · 픽셀 변환 ${ready ? "✓" : "—"}</small></span>`;
    if ($("pipelineGenerateModel")) $("pipelineGenerateModel").disabled = !sourceImageDataUrl || !modelReady;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
  }

  function formatBytes(bytes) {
    const value = Number(bytes) || 0;
    if (value < 1024) return `${value} B`;
    if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 ** 2)).toFixed(1)} MB`;
  }

  function limitText(value, max = 120) {
    return String(value ?? "").trim().slice(0, max);
  }

  function normalizeStrictQa(raw) {
    if (!raw || typeof raw !== "object") return null;
    const checks = Array.isArray(raw.checks)
      ? raw.checks.slice(0, 8).map(item => ({
          id: limitText(item?.id || "qa-check", 40),
          label: limitText(item?.label || item?.id || "검사 항목", 80),
          pass: item?.pass === true,
          value: item?.value == null ? "" : limitText(item.value, 60),
          threshold: item?.threshold == null ? "" : limitText(item.threshold, 60),
        }))
      : [];
    const failures = Array.isArray(raw.failures)
      ? raw.failures.slice(0, 6).map(item => {
          if (typeof item === "string") return limitText(item, 120);
          const label = limitText(item?.label || item?.id || "검사 항목", 80);
          const value = item?.value == null ? "" : `현재 ${limitText(item.value, 40)}`;
          const threshold = item?.threshold == null ? "" : `기준 ${limitText(item.threshold, 40)}`;
          return [label, value, threshold].filter(Boolean).join(" · ");
        }).filter(Boolean)
      : [];
    return {
      pass: raw.pass === true,
      score: Math.max(0, Math.min(100, Number(raw.score) || 0)),
      attemptsUsed: Math.max(0, Number(raw.attempts_used ?? raw.attemptsUsed) || 0),
      maxAttempts: Math.max(0, Number(raw.max_attempts ?? raw.maxAttempts) || 0),
      checks,
      failures,
    };
  }

  function mergeDirectionArtifactQa(nextState, source) {
    if (!nextState?.directionArtifacts || !source?.directionArtifacts) return nextState;
    for (const direction of Core.DIRECTIONS) {
      const nextArtifact = nextState.directionArtifacts[direction];
      const sourceArtifact = source.directionArtifacts?.[direction];
      if (!nextArtifact || !sourceArtifact || nextArtifact.url !== sourceArtifact.url) continue;
      nextArtifact.accepted = sourceArtifact.accepted === true;
      const strictQa = normalizeStrictQa(
        sourceArtifact.strictQa
        || sourceArtifact.qa?.strict
        || sourceArtifact.metadata?.qa?.strict
      );
      if (strictQa) nextArtifact.strictQa = strictQa;
      else delete nextArtifact.strictQa;
    }
    nextState.singleDirectionReady = Boolean(nextState.directionArtifacts.S?.url);
    return nextState;
  }

  function normalizePipelineState(raw) {
    return mergeDirectionArtifactQa(Core.normalizeState(raw), raw || {});
  }

  function cloneState(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function qaListMarkup(item, pass) {
    return `<li data-pass="${pass ? "true" : "false"}">${item}</li>`;
  }

  function checkSummaryMarkup(check) {
    const details = [check.value && `현재 ${escapeHtml(check.value)}`, check.threshold && `기준 ${escapeHtml(check.threshold)}`]
      .filter(Boolean)
      .join(" · ");
    const body = details || (check.pass ? "기준 충족" : "기준 미달");
    return `<li data-pass="${check.pass ? "true" : "false"}"><strong>${escapeHtml(check.label)}</strong>${body}</li>`;
  }

  function renderIdentityReference(fileName = identityImageName) {
    const preview = $("pipelineIdentityPreview");
    const label = $("pipelineIdentityName");
    if (!preview || !label) return;
    preview.hidden = !identityImageDataUrl;
    if (identityImageDataUrl) preview.src = identityImageDataUrl;
    else preview.removeAttribute("src");
    label.textContent = identityImageDataUrl
      ? `${fileName || "기준 이미지"} · 8프레임 정체성 고정에 사용`
      : "선택 안 함 · 3D 첫 프레임 사용";
  }

  async function useIdentityImage(file) {
    if (!file) return;
    if (!/^image\/(png|jpeg|webp)$/i.test(file.type || "") || file.size > 6 * 1024 * 1024) {
      showToast("기준 이미지는 6MB 이하 PNG·JPG·WEBP만 사용할 수 있습니다.");
      return;
    }
    identityImageDataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("기준 이미지를 읽지 못했습니다."));
      reader.readAsDataURL(file);
    });
    identityImageName = file.name;
    invalidatePixelProof();
    renderIdentityReference(file.name);
    saveState();
    render();
    showToast("기준 이미지를 고정했습니다. 얼굴·의상 일관성에 사용합니다.");
  }

  async function loadIdentityAsset(url, name) {
    const response = await fetch(url, { headers: { Accept: "image/*" } });
    if (!response.ok) throw new Error(`외형 기준 이미지를 불러올 수 없습니다. (HTTP ${response.status})`);
    const blob = await response.blob();
    identityImageDataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("외형 기준 이미지를 읽지 못했습니다."));
      reader.readAsDataURL(blob);
    });
    identityImageName = name;
    renderIdentityReference(name);
  }

  function extensionFor(name) {
    return String(name || "").split(".").pop().toLowerCase();
  }

  function useModelFile(file) {
    if (!file) return;
    const extension = extensionFor(file.name);
    if (!MODEL_EXTENSIONS.has(extension)) {
      showToast("현재 실제 3D 뷰어는 GLB 파일을 지원합니다.");
      return;
    }
    if (file.size > MAX_MODEL_BYTES) {
      showToast("모델 파일은 500MB 이하만 사용할 수 있습니다.");
      return;
    }
    state = Core.createState();
    identityImageDataUrl = null;
    identityImageName = "";
    state.model = { name: file.name, size: file.size, type: extension.toUpperCase(), sample: false };
    viewerMetrics = null;
    saveState();
    render();
    showToast(`${file.name} 실제 3D 로딩을 시작했습니다.`);
    waitForViewer().then(viewer => viewer.loadFile(file)).catch(error => {
      if (state.model?.name === file.name) {
        state = Core.createState();
        saveState();
        render();
      }
      showToast(`3D 모델을 열 수 없습니다: ${error.message}`);
    });
  }

  async function useSampleModel() {
    state = Core.createState();
    identityImageDataUrl = null;
    identityImageName = "";
    state.model = { ...UAL_IDLE_SAMPLE };
    state.action = "idle";
    state.motions.idle = "ready";
    state.singleDirectionReady = true;
    state.selectedDirection = "S";
    state.directions.S = "ready";
    state.directionArtifacts.S = {
      url: UAL_IDLE_SAMPLE.approvedAtlasUrl,
      previewUrl: UAL_IDLE_SAMPLE.approvedPreviewUrl,
      provider: "approved-reference",
      model: "identity-locked front idle",
      resolution: 96,
      frameWidth: 96,
      frameHeight: 192,
      frameCount: 8,
      frameUrls: Array.from({ length: 8 }, (_, index) =>
        `/assets/generated/3d-actions/chairman-front-idle-approved/frames/idle_${String(index).padStart(2, "0")}.png`),
      action: "idle",
      paletteColors: 32,
      accepted: true,
      strictQa: {
        pass: true,
        score: 93,
        minimumScore: 90,
        attemptsUsed: 4,
        maxAttempts: 4,
        failures: [],
        checks: [],
      },
    };
    viewerMetrics = null;
    saveState();
    render();
    showToast("청년 정면 Idle 모델과 승인된 도트 결과를 불러오고 있습니다.");
    const referenceTask = loadIdentityAsset(UAL_IDLE_SAMPLE.referenceUrl, "chairman_reference.png")
      .catch(() => {});
    try {
      const viewer = await waitForViewer();
      viewer.setAction("idle");
      await viewer.loadSample();
      await referenceTask;
      saveState();
      render();
      showToast("청년 정면 Idle을 열었습니다. 오른쪽에서 3D 동작과 승인된 도트 결과를 확인하세요.");
    } catch (error) {
      if (state.model?.sample) {
        state = Core.createState();
        saveState();
        render();
      }
      showToast(`청년 정면 Idle 모델을 열 수 없습니다: ${error.message}`);
    }
  }

  function chibiStompArtifact(direction) {
    const root = `${CHIBI_STOMP_8DIR_SAMPLE.artifactRoot}/${direction}`;
    return {
      url: `${root}/walk_96x96_atlas.png`,
      previewUrl: `${root}/walk_preview.gif`,
      provider: "local-rigid-layer",
      model: "reference-locked stomp v2 · face polished",
      resolution: 96,
      frameWidth: 96,
      frameHeight: 96,
      frameCount: 4,
      frameUrls: Array.from({ length: 4 }, (_, index) =>
        `${root}/frames/walk_${String(index).padStart(2, "0")}.png`),
      action: "walk",
      paletteColors: 64,
      accepted: true,
      strictQa: {
        pass: true,
        score: 93,
        minimumScore: 90,
        attemptsUsed: 2,
        maxAttempts: 2,
        failures: [],
        checks: [],
      },
    };
  }

  async function useChibiStomp8DirSample() {
    state = Core.createState();
    identityImageDataUrl = null;
    identityImageName = "";
    state.model = { ...CHIBI_STOMP_8DIR_SAMPLE };
    state.action = "walk";
    state.motions.walk = "ready";
    state.singleDirectionReady = true;
    state.selectedDirection = "S";
    state.completedSteps = [0, 1, 2, 3];
    state.currentStep = 4;
    for (const direction of Core.DIRECTIONS) {
      state.directions[direction] = "ready";
      state.directionArtifacts[direction] = chibiStompArtifact(direction);
    }
    viewerMetrics = null;
    saveState();
    render();
    showToast("청년 2등신 발 구르기 8방향을 불러오고 있습니다.");
    const referenceTask = loadIdentityAsset(CHIBI_STOMP_8DIR_SAMPLE.referenceUrl, "chairman_reference.png")
      .catch(() => {});
    try {
      const viewer = await waitForViewer();
      viewer.setAction("walk");
      await viewer.loadAsset(CHIBI_STOMP_8DIR_SAMPLE.url, CHIBI_STOMP_8DIR_SAMPLE.name);
      await referenceTask;
      saveState();
      render();
      showToast("2등신 발 구르기 8방향을 열었습니다. 방향 버튼으로 각각 확인하세요.");
    } catch (error) {
      if (state.model?.sample) {
        state = Core.createState();
        saveState();
        render();
      }
      showToast(`2등신 8방향 샘플을 열 수 없습니다: ${error.message}`);
    }
  }

  function enterStep(step) {
    const target = Number(step);
    if (!Core.canEnterStep(state, target)) {
      showToast("이전 단계의 승인을 먼저 완료하세요.");
      return;
    }
    state.currentStep = target;
    saveState();
    render();
  }

  function completeCurrentStep(expectedStep) {
    if (state.currentStep !== expectedStep) return;
    state = mergeDirectionArtifactQa(Core.completeStep(state, expectedStep), state);
    saveState();
    render();
  }

  function selectAction(action) {
    if (!Core.ACTIONS.includes(action)) return;
    if (state.action !== action) invalidatePixelProof();
    state.action = action;
    state.poseFrame = 0;
    playStartedAt = performance.now();
    saveState();
    renderActionState();
    renderPoseState();
  }

  function invalidatePixelProof() {
    if (!state.singleDirectionReady && !state.directionArtifacts?.S) return;
    state.singleDirectionReady = false;
    state.directionArtifacts.S = null;
    Core.DIRECTIONS.forEach(direction => { state.directions[direction] = "pending"; });
    state.completedSteps = state.completedSteps.filter(step => step < 3);
    state.currentStep = Math.min(state.currentStep, 3);
    state.finalApproved = false;
    Core.REVIEW_KEYS.forEach(key => { state.review[key] = false; });
  }

  function renderActionState() {
    document.querySelectorAll("[data-pipeline-action]").forEach(button => {
      const active = button.dataset.pipelineAction === state.action;
      if (button.hasAttribute("aria-pressed")) button.setAttribute("aria-pressed", String(active));
      if (button.hasAttribute("aria-selected")) button.setAttribute("aria-selected", String(active));
      const label = button.querySelector("em");
      if (label) label.textContent = active ? "재생 중" : "미리보기";
    });
    $("pipelineActionLabel").textContent = state.action.toUpperCase();
    $("pipelineModelPreview").dataset.action = state.action;
    if ($("pipelineGenerateSingle")) {
      $("pipelineGenerateSingle").textContent = `S 방향 ${state.action.toUpperCase()} 8프레임 시트 생성`;
    }
    window.AssetStudioPixelPipelineViewer?.setAction?.(state.action);
  }

  function renderPoseState() {
    $("pipelinePoseFrame").value = String(state.poseFrame);
    $("pipelinePoseFrameLabel").textContent = `${state.poseFrame}%`;
    document.querySelectorAll("[data-pose-frame]").forEach(button => {
      button.setAttribute("aria-pressed", String(Number(button.dataset.poseFrame) === state.poseFrame));
    });
  }

  function setGenerating(active, detail = "형태와 팔레트를 잠그고 있습니다.") {
    $("pipelineGenerating").hidden = !active;
    $("pipelineGeneratingDetail").textContent = detail;
    for (const id of ["pipelineGenerateSingle", "pipelineGenerateDirections"]) {
      if ($(id)) $(id).disabled = active;
    }
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: { Accept: "application/json", ...(options.headers || {}) },
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch (_error) {
      throw new Error(`서버가 올바른 JSON을 반환하지 않았습니다. (HTTP ${response.status})`);
    }
    if (!response.ok || payload?.success === false) {
      throw new Error(payload?.error || `요청이 실패했습니다. (HTTP ${response.status})`);
    }
    return payload;
  }

  async function runGenerationJob(endpoint, payload, token) {
    const submitted = await requestJson("/api/generation-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint, payload }),
    });
    const jobId = submitted.job_id;
    if (!jobId) throw new Error("생성 작업 ID를 받지 못했습니다.");
    const startedAt = Date.now();
    while (Date.now() - startedAt < 30 * 60 * 1000) {
      if (token !== generationToken) throw new Error("생성 작업이 취소되었습니다.");
      await delay(900);
      const job = await requestJson(`/api/generation-jobs/${encodeURIComponent(jobId)}`);
      if (job.status === "succeeded") return job.result;
      if (job.status === "failed") throw new Error(job.error || "로컬 ComfyUI 생성 작업이 실패했습니다.");
      const elapsed = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
      setGenerating(true, `로컬 ComfyUI가 8프레임 전체 시트를 처리 중입니다. 자동 재생성/검증 포함 · ${elapsed}초`);
    }
    throw new Error("로컬 ComfyUI 생성 제한 시간(30분)을 초과했습니다.");
  }

  function selectedInteger(id, fallback) {
    const match = String($(id)?.value || "").match(/\d+/);
    return match ? Number(match[0]) : fallback;
  }

  function renderStrictQa(artifact) {
    const card = $("pipelineStrictQa");
    const badge = $("pipelineStrictQaBadge");
    const score = $("pipelineStrictQaScore");
    const attempts = $("pipelineStrictQaAttempts");
    const summary = $("pipelineStrictQaSummary");
    const list = $("pipelineStrictQaList");
    if (!card || !badge || !score || !attempts || !summary || !list) return;
    if (!artifact?.url) {
      card.hidden = true;
      list.innerHTML = "";
      return;
    }
    const strictQa = artifact.strictQa;
    const accepted = artifact.accepted === true;
    card.hidden = false;
    card.dataset.state = accepted ? "pass" : "fail";
    badge.textContent = accepted ? "자동 QA 통과" : "자동 QA 재검토 필요";
    score.textContent = strictQa ? `${strictQa.score}점` : "-점";
    attempts.textContent = strictQa
      ? `자동 재생성 ${strictQa.attemptsUsed} / ${strictQa.maxAttempts || 3}회`
      : "자동 재생성·검증 결과 없음";
    if (strictQa?.failures?.length) {
      summary.textContent = `${strictQa.failures.length}개 항목이 기준을 넘지 못했습니다.`;
      list.innerHTML = strictQa.failures.map(item => qaListMarkup(escapeHtml(item), false)).join("");
      return;
    }
    if (strictQa?.checks?.length) {
      summary.textContent = accepted
        ? `전체 ${strictQa.checks.length}개 항목을 통과했습니다.`
        : `세부 검사 ${strictQa.checks.length}개 결과를 확인하세요.`;
      list.innerHTML = strictQa.checks.map(checkSummaryMarkup).join("");
      return;
    }
    summary.textContent = accepted
      ? "자동 검증은 통과했지만 세부 항목이 전달되지 않았습니다."
      : "자동 검증 세부 정보가 없어 수동 확인이 필요합니다.";
    list.innerHTML = "";
  }

  function renderPixelArtifact() {
    const artifact = state.directionArtifacts?.[state.selectedDirection]
      || state.directionArtifacts?.S;
    const image = $("pipelinePixelImage");
    const empty = $("pipelinePixelEmpty");
    const meta = $("pipelinePixelMeta");
    if (!image || !empty || !meta) return;
    const available = Boolean(artifact?.url);
    image.hidden = !available;
    empty.hidden = available;
    renderStrictQa(artifact);
    if (!available) {
      image.removeAttribute("src");
      meta.textContent = "로컬 ComfyUI의 8프레임 결과가 여기에 표시됩니다.";
      return;
    }
    if (image.getAttribute("src") !== artifact.url) image.src = artifact.url;
    image.alt = `${state.selectedDirection} 방향 AI 픽셀화 결과`;
    const width = artifact.frameWidth || artifact.resolution;
    const height = artifact.frameHeight || artifact.resolution;
    meta.textContent = `${width}×${height} · ${artifact.frameCount || 8} frames · ${artifact.paletteColors} colors · ${artifact.model || artifact.provider || "로컬 ComfyUI"}`;
  }

  async function generateSingleDirection() {
    const token = ++generationToken;
    setGenerating(true, "로컬 ComfyUI와 3D 애니메이션을 확인하고 있습니다. 8프레임 시트와 엄격 검증을 준비 중입니다.");
    try {
      const health = await refreshProviderHealth();
      if (!health?.available) {
        const missing = Array.isArray(health?.missing_nodes) && health.missing_nodes.length
          ? ` 빠진 노드: ${health.missing_nodes.join(", ")}`
          : "";
        throw new Error(`로컬 ComfyUI가 준비되지 않았습니다. ComfyUI를 먼저 실행하세요.${missing}`);
      }
      const viewer = await waitForViewer();
      let capture;
      try {
        viewer.setPlaying?.(false);
        capture = await viewer.captureAnimationSheet({
          action: state.action,
          frameCount: 8,
          frameWidth: 256,
          frameHeight: 512,
        });
      } finally {
        viewer.setPlaying?.(playing);
      }
      if (token !== generationToken) return;

      const resolution = selectedInteger("pipelineResolution", 64);
      const paletteColors = selectedInteger("pipelinePalette", 24);
      state.singleDirectionReady = false;
      state.directionArtifacts.S = null;
      Core.DIRECTIONS.forEach(direction => { state.directions[direction] = "pending"; });
      state.completedSteps = state.completedSteps.filter(step => step < 3);
      saveState();
      render();
      setGenerating(true, "8개 3D 포즈를 캡처했습니다. 8프레임 전체 시트 생성과 자동 재생성/검증을 진행합니다.");

      const result = await runGenerationJob("/api/local-3d-action-sheet", {
        guide_sheet: capture.dataUrl,
        identity_image: identityImageDataUrl || capture.firstFrameDataUrl,
        direction: "S",
        action: state.action,
        resolution,
        palette_colors: paletteColors,
        style: $("pipelineStyle").value,
        shape_lock: Number($("pipelineShapeLock").value),
        pixel_simplify: Number($("pipelinePixelSimplify").value),
        strict_validation: true,
        max_attempts: 3,
        min_qa_score: 90,
      }, token);
      if (token !== generationToken) return;
      if (!result?.url) throw new Error("로컬 ComfyUI 결과 이미지 URL이 없습니다.");
      const strictQa = normalizeStrictQa(result?.metadata?.qa?.strict || result?.qa?.strict || result?.strictQa);
      state.directionArtifacts.S = {
        url: result.url,
        artifactDigest: result.artifact_digest || "",
        provider: result.provider || "local-comfyui",
        model: result.model || "",
        resolution,
        frameWidth: result.frame_width || resolution,
        frameHeight: result.frame_height || resolution * 2,
        frameCount: result.frame_count || 8,
        frameUrls: result.frame_urls || [],
        previewUrl: result.preview_url || "",
        action: result.action || state.action,
        paletteColors,
        accepted: result.accepted === true,
        strictQa,
      };
      state.singleDirectionReady = true;
      state.selectedDirection = "S";
      state.directions.S = "ready";
      saveState();
      setGenerating(false);
      setPreviewMode("split");
      render();
      showToast(
        state.directionArtifacts.S.accepted
          ? `${state.action.toUpperCase()} S 방향 8프레임 픽셀 시트를 만들고 자동 QA를 통과했습니다.`
          : `${state.action.toUpperCase()} S 방향 8프레임 픽셀 시트를 만들었지만 자동 QA가 아직 승인하지 않았습니다.`
      );
    } catch (error) {
      if (token !== generationToken) return;
      setGenerating(false);
      render();
      showToast(`AI 픽셀화 실패: ${error.message}`);
    }
  }

  function approveSingleDirection() {
    if (!state.singleDirectionReady || !state.directionArtifacts?.S?.url || state.directionArtifacts.S.accepted !== true) return;
    state.directions.S = "approved";
    saveState();
    completeCurrentStep(3);
    showToast("S 방향 품질 기준을 잠갔습니다. 이제 8방향 제작에 같은 규칙이 적용됩니다.");
  }

  async function generateAllDirections() {
    showToast("8방향은 승인된 S 결과와 방향별 3D 렌더를 묶는 다음 실제 생성 단계입니다. 가짜 결과는 만들지 않습니다.");
  }

  function approveDirections() {
    const progress = Core.directionProgress(state);
    if (progress.ready !== progress.total) return;
    Core.DIRECTIONS.forEach(direction => { state.directions[direction] = "approved"; });
    saveState();
    completeCurrentStep(4);
    showToast("8방향 결과를 승인했습니다. 마지막 수작업 검수를 진행하세요.");
  }

  function selectDirection(direction) {
    if (!Core.DIRECTIONS.includes(direction) || state.directions[direction] === "pending") return;
    state.selectedDirection = direction;
    saveState();
    setPreviewMode("pixel");
    renderPixelArtifact();
    renderDirections();
    $("pipelinePixelDirectionBadge").textContent = `${direction} · ${directionLabel(direction)}`;
    showToast(`${direction} 방향 확대 미리보기`);
  }

  function directionLabel(direction) {
    return ({ S: "FRONT", SW: "FRONT LEFT", W: "LEFT", NW: "BACK LEFT", N: "BACK", NE: "BACK RIGHT", E: "RIGHT", SE: "FRONT RIGHT" })[direction] || direction;
  }

  function setPreviewMode(mode) {
    const available = state.singleDirectionReady;
    let target = mode;
    if (["split", "pixel"].includes(target) && !available) target = "model";
    document.querySelectorAll("[data-view-mode]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.viewMode === target)));
    $("pipelineViewport").dataset.preview = target;
    $("pipelineModelPreview").hidden = !state.model || target === "pixel" || target === "directions";
    $("pipelinePixelPreview").hidden = !available || !["split", "pixel"].includes(target);
    $("pipelineDirectionGrid").hidden = target !== "directions";
    $("pipelineEmptyState").hidden = Boolean(state.model);
  }

  function renderDirections() {
    const progress = Core.directionProgress(state);
    $("pipelineDirectionProgress").textContent = `${progress.ready} / ${progress.total}`;
    document.querySelectorAll("#pipelineDirectionGrid [data-direction]").forEach(button => {
      const status = state.directions[button.dataset.direction] || "pending";
      button.dataset.status = status;
      button.setAttribute("aria-pressed", String(button.dataset.direction === state.selectedDirection));
      const label = button.querySelector("small");
      label.textContent = ({ pending: "대기", working: "생성 중", ready: "확인", approved: "승인" })[status];
    });
    $("pipelineApproveDirections").disabled = progress.ready !== progress.total;
  }

  function renderReview() {
    document.querySelectorAll("[data-review-key]").forEach(input => {
      input.checked = Boolean(state.review[input.dataset.reviewKey]);
    });
    $("pipelineFinalApprove").disabled = !Core.reviewComplete(state) || state.finalApproved;
    $("pipelineFinalApprove").textContent = state.finalApproved ? "최종 승인 완료" : "최종 승인 및 제작 완료";
  }

  function renderProject() {
    const model = state.model;
    const animationNames = viewerMetrics?.animations || [];
    const hasIdle = animationNames.some(name => /idle|survey/i.test(name));
    const hasWalk = animationNames.some(name => /walk/i.test(name));
    const hasRun = animationNames.some(name => /run/i.test(name));
    const rigReady = Boolean(viewerMetrics?.bones > 0 && hasIdle && hasWalk && hasRun);
    $("pipelineApproveModel").disabled = !model || !viewerMetrics;
    $("pipelineApproveRig").disabled = !rigReady;
    $("pipelineFormatCheck").textContent = model ? (viewerMetrics ? `${model.type} · 정상` : "검사 중") : "대기";
    $("pipelineMaterialCheck").textContent = model ? (viewerMetrics ? `${viewerMetrics.materials} materials` : "검사 중") : "대기";
    $("pipelineBoneCount").textContent = model ? (viewerMetrics ? String(viewerMetrics.bones) : "—") : "—";
    $("pipelineMeshCount").textContent = model ? (viewerMetrics ? String(viewerMetrics.meshes) : "—") : "—";
    $("pipelineAnimationCount").textContent = viewerMetrics ? String(animationNames.length) : "—";
    $("pipelineRigNotice").classList.toggle("pipeline-notice--good", rigReady);
    $("pipelineRigNoticeTitle").textContent = rigReady ? "리깅 검사 통과" : "필수 리깅·클립 확인 필요";
    $("pipelineRigNoticeDetail").textContent = rigReady
      ? `본 ${viewerMetrics.bones}개 · ${animationNames.join(" · ")}`
      : "Idle(또는 Survey), Walk, Run 클립과 본 구조가 필요합니다.";
    const blendLink = $("pipelineDownloadBlend");
    blendLink.hidden = !model?.blendUrl;
    if (model?.blendUrl) {
      blendLink.href = model.blendUrl;
      blendLink.download = model.blendUrl.split("/").pop() || "character.blend";
      blendLink.textContent = "Blender 원본 작업본 받기 (.blend)";
    } else {
      blendLink.removeAttribute("href");
    }
    $("pipelineModelName").textContent = model?.name || "모델 미선택";
    $("pipelineModelMeta").textContent = model ? `${model.type} · ${formatBytes(model.size)}${model.sample ? " · 샘플" : " · 로컬 파일"}` : "파일을 가져오면 정보가 표시됩니다.";
    $("pipelinePreviewTitle").textContent = model?.name || "모델을 불러오세요";
    $("pipelineEmptyState").hidden = Boolean(model);
    $("pipelineModelPreview").hidden = !model;
  }

  function renderNavigation() {
    const available = Core.availableStep(state);
    const progress = Core.workflowProgress(state);
    $("pipelineProgressLabel").textContent = `${progress.complete} / ${progress.total} 완료`;
    $("pipelineProgressBar").style.width = `${progress.percent}%`;
    $("pipelineGateCount").textContent = `${progress.complete} / ${progress.total}`;
    document.querySelectorAll("[data-pipeline-step]").forEach(button => {
      const step = Number(button.dataset.pipelineStep);
      button.disabled = step > available;
      button.toggleAttribute("aria-current", step === state.currentStep);
      if (step === state.currentStep) button.setAttribute("aria-current", "step");
      button.closest("li")?.classList.toggle("is-complete", state.completedSteps.includes(step));
    });
    document.querySelectorAll("[data-pipeline-panel]").forEach(panel => {
      panel.hidden = Number(panel.dataset.pipelinePanel) !== state.currentStep;
    });
    document.querySelectorAll("[data-gate]").forEach(item => {
      const step = Number(item.dataset.gate);
      item.classList.toggle("is-complete", state.completedSteps.includes(step));
      item.classList.toggle("is-current", step === state.currentStep);
    });
    const copy = STEP_COPY[state.currentStep];
    $("pipelineStepKicker").textContent = copy[0];
    $("pipelineStepTitle").textContent = copy[1];
    $("pipelineStepDescription").textContent = copy[2];
    const next = NEXT_COPY[state.currentStep];
    $("pipelineNextRequirement").textContent = next[0];
    $("pipelineNextDetail").textContent = next[1];
  }

  function renderPreview() {
    $("pipelineModelPreview").classList.toggle("is-playing", playing);
    $("pipelineModelPreview").dataset.action = state.action;
    $("pipelinePixelDirectionBadge").textContent = `${state.selectedDirection} · ${directionLabel(state.selectedDirection)}`;
    const step = state.currentStep;
    if (step >= 4) setPreviewMode("directions");
    else if (step === 3 && state.singleDirectionReady) setPreviewMode("split");
    else setPreviewMode("model");
    $("pipelinePreviewMode").textContent = step >= 4 ? "8-DIRECTION REVIEW" : (step === 3 ? "AI PIXEL TEST" : "3D PREVIEW");
  }

  function render() {
    renderNavigation();
    renderProject();
    renderActionState();
    renderPoseState();
    renderDirections();
    renderReview();
    renderPreview();
    renderProviderState();
    renderIdentityReference();
    renderPixelArtifact();
    $("pipelineApproveSingle").disabled = !state.singleDirectionReady || state.directionArtifacts?.S?.accepted !== true;
    $("pipelineApproveSingle").title = state.directionArtifacts?.S?.accepted === true
      ? ""
      : "자동 QA 통과 결과만 8방향 제작 기준으로 잠글 수 있습니다.";
  }

  function delay(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
  }

  function animateTimeline(now) {
    const durations = { idle: 2000, walk: 800, run: 600 };
    const duration = durations[state.action] || 1000;
    if (playing) {
      const elapsed = (now - playStartedAt) % duration;
      $("pipelineTimelineProgress").style.width = `${(elapsed / duration) * 100}%`;
      const frame = Math.floor((elapsed / duration) * 100);
      $("pipelineTimecode").textContent = `00:00:${String(frame).padStart(2, "0")}`;
    }
    requestAnimationFrame(animateTimeline);
  }

  function bindEvents() {
    document.querySelectorAll("#studioWorkspaceSwitch button").forEach(button => {
      button.addEventListener("click", () => setWorkspace(button.dataset.studioWorkspace));
    });
    $("pipelineSteps").addEventListener("click", event => {
      const button = event.target.closest("[data-pipeline-step]");
      if (button) enterStep(button.dataset.pipelineStep);
    });

    const input = $("pipelineModelInput");
    const dropzone = $("pipelineModelDropzone");
    $("pipelineBrowseModel").addEventListener("click", event => { event.stopPropagation(); input.click(); });
    dropzone.addEventListener("click", event => { if (!event.target.closest("button")) input.click(); });
    dropzone.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); input.click(); }
    });
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      input.value = "";
      useModelFile(file);
    });
    dropzone.addEventListener("dragover", event => { event.preventDefault(); dropzone.classList.add("is-dragging"); });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("is-dragging"));
    dropzone.addEventListener("drop", event => {
      event.preventDefault();
      dropzone.classList.remove("is-dragging");
      useModelFile(event.dataTransfer?.files?.[0]);
    });
    $("pipelineUseSample").addEventListener("click", () => {
      useSampleModel().catch(error => showToast(error.message));
    });
    $("pipelineUseChibiStomp8Dir").addEventListener("click", () => {
      useChibiStomp8DirSample().catch(error => showToast(error.message));
    });
    $("pipelineBrowseIdentity").addEventListener("click", () => $("pipelineIdentityInput").click());
    $("pipelineIdentityInput").addEventListener("change", event => {
      const file = event.target.files?.[0];
      event.target.value = "";
      useIdentityImage(file).catch(error => showToast(error.message));
    });
    $("pipelineApproveModel").addEventListener("click", () => completeCurrentStep(0));
    $("pipelineApproveRig").addEventListener("click", () => completeCurrentStep(1));
    $("pipelineApprovePose").addEventListener("click", () => completeCurrentStep(2));

    document.querySelectorAll("[data-pipeline-action]").forEach(button => {
      button.addEventListener("click", () => selectAction(button.dataset.pipelineAction));
    });
    $("pipelinePoseFrame").addEventListener("input", event => {
      const poseFrame = Number(event.target.value);
      if (state.poseFrame !== poseFrame) invalidatePixelProof();
      state.poseFrame = poseFrame;
      window.AssetStudioPixelPipelineViewer?.seek?.(state.poseFrame);
      renderPoseState();
      saveState();
    });
    $("pipelinePoseCards").addEventListener("click", event => {
      const button = event.target.closest("[data-pose-frame]");
      if (!button) return;
      const poseFrame = Number(button.dataset.poseFrame);
      if (state.poseFrame !== poseFrame) invalidatePixelProof();
      state.poseFrame = poseFrame;
      window.AssetStudioPixelPipelineViewer?.seek?.(state.poseFrame);
      saveState();
      renderPoseState();
    });

    $("pipelineGenerateSingle").addEventListener("click", generateSingleDirection);
    $("pipelineApproveSingle").addEventListener("click", approveSingleDirection);
    $("pipelineGenerateDirections").addEventListener("click", generateAllDirections);
    $("pipelineApproveDirections").addEventListener("click", approveDirections);
    for (const id of ["pipelineResolution", "pipelinePalette", "pipelineStyle", "pipelineShapeLock", "pipelinePixelSimplify"]) {
      $(id).addEventListener("change", () => {
        invalidatePixelProof();
        saveState();
        render();
      });
    }
    $("pipelineDirectionGrid").addEventListener("click", event => {
      const button = event.target.closest("[data-direction]");
      if (button) selectDirection(button.dataset.direction);
    });
    $("pipelineReviewChecklist").addEventListener("change", event => {
      const inputNode = event.target.closest("[data-review-key]");
      if (!inputNode) return;
      state.review[inputNode.dataset.reviewKey] = inputNode.checked;
      state.finalApproved = false;
      saveState();
      renderReview();
    });
    $("pipelineFinalApprove").addEventListener("click", () => {
      if (!Core.reviewComplete(state)) return;
      state.finalApproved = true;
      state = Core.completeStep(state, 5);
      saveState();
      render();
      showToast("수작업 검수까지 완료했습니다. 제작 상태를 최종 승인으로 저장했습니다.");
    });

    document.querySelectorAll("[data-view-mode]").forEach(button => {
      button.addEventListener("click", () => setPreviewMode(button.dataset.viewMode));
    });
    $("pipelinePreviewPlay").addEventListener("click", () => {
      playing = !playing;
      playStartedAt = performance.now();
      window.AssetStudioPixelPipelineViewer?.setPlaying?.(playing);
      $("pipelinePreviewPlay").textContent = playing ? "Ⅱ" : "▶";
      $("pipelineModelPreview").classList.toggle("is-playing", playing);
    });
    $("pipelinePlaybackSpeed").addEventListener("change", event => {
      window.AssetStudioPixelPipelineViewer?.setPlaybackSpeed?.(Number.parseFloat(event.target.value));
    });
    $("pipelineReset").addEventListener("click", () => {
      if (!window.confirm("3D → 픽셀 작업 초안을 초기화할까요?")) return;
      generationToken += 1;
      state = Core.createState();
      viewerMetrics = null;
      identityImageDataUrl = null;
      identityImageName = "";
      window.AssetStudioPixelPipelineViewer?.resetAll?.();
      localStorage.removeItem(STORAGE_KEY);
      setGenerating(false);
      render();
      showToast("작업 초안을 초기화했습니다.");
    });
  }

  window.AssetStudioPixelPipeline = {
    serialize: () => cloneState(state),
    hydrate: incoming => { state = normalizePipelineState(incoming); saveState(); render(); },
    refreshProviderHealth,
  };

  window.addEventListener("asset-studio:3d-loaded", event => {
    viewerMetrics = event.detail;
    renderProject();
  });
  window.addEventListener("asset-studio:3d-error", event => {
    viewerMetrics = null;
    showToast(`3D 로드 오류: ${event.detail?.message || "알 수 없는 오류"}`);
  });

  bindEvents();
  render();
  requestAnimationFrame(animateTimeline);
})();
