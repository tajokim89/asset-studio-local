const canvas = new fabric.Canvas('c', {
  preserveObjectStacking: true,
  backgroundColor: '#ffffff',
  selection: true,
});

let history = [];
let historyIndex = -1;
let suppressHistory = false;
let currentDrawTool = 'select';
let currentTool = 'select';
let viewScale = 1;
let isPanning = false;
let panStart = null;
let canvasPanOffset = { x: 0, y: 0 };
let activeDrawingLayerId = null;
let selectedLayerId = null;
let isMaskDragging = false;
let maskStart = null;
let maskPreview = null;
let maskRegions = [];
let maskLockedObjects = false;
let maskDrawMode = 'brush';
let replacementGripAnchor = null;
let pendingInpaintResult = null;
let pendingChatAction = null;
const $ = (id) => document.getElementById(id);
const appEl = document.querySelector('.app');
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

function setPanelWidth(side, px, persist = true) {
  const maxWidth = Math.max(260, window.innerWidth - 760);
  const value = clamp(Math.round(px), 220, Math.min(560, maxWidth));
  const varName = side === 'left' ? '--left-panel' : '--right-panel';
  appEl.style.setProperty(varName, `${value}px`);
  if (persist) localStorage.setItem(`assetStudio.${side}PanelWidth`, String(value));
}

function restorePanelWidths() {
  const left = +localStorage.getItem('assetStudio.leftPanelWidth');
  const right = +localStorage.getItem('assetStudio.rightPanelWidth');
  if (left) setPanelWidth('left', left, false);
  if (right) setPanelWidth('right', right, false);
}

function setupPanelResize() {
  restorePanelWidths();
  const startResize = (side, e) => {
    e.preventDefault();
    const handle = e.currentTarget;
    handle.classList.add('active');
    document.body.classList.add('resizing');
    const startX = e.clientX;
    const startLeft = document.querySelector('.sidebar').getBoundingClientRect().width;
    const startRight = document.querySelector('.props').getBoundingClientRect().width;
    const onMove = (ev) => {
      const dx = ev.clientX - startX;
      if (side === 'left') setPanelWidth('left', startLeft + dx);
      else setPanelWidth('right', startRight - dx);
      fitView();
    };
    const onUp = () => {
      handle.classList.remove('active');
      document.body.classList.remove('resizing');
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      fitView();
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };
  $('leftResize').onmousedown = (e) => startResize('left', e);
  $('rightResize').onmousedown = (e) => startResize('right', e);
}

function setStatus(msg) {
  $('status').textContent = `${new Date().toLocaleTimeString()}  ${msg}`;
}

function saveHistory() {
  if (suppressHistory) return;
  const json = JSON.stringify(canvas.toDatalessJSON(['id','name','_originalSrc','_phase4PreservedOriginal','excludeFromLayers','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId']));
  if (history[historyIndex] === json) return;
  history = history.slice(0, historyIndex + 1);
  history.push(json);
  historyIndex = history.length - 1;
  if (history.length > 50) { history.shift(); historyIndex--; }
  renderLayers();
}

function loadHistory(idx) {
  if (idx < 0 || idx >= history.length) return;
  suppressHistory = true;
  canvas.loadFromJSON(history[idx], () => {
    canvas.renderAll();
    historyIndex = idx;
    suppressHistory = false;
    refreshMaskStateFromCanvas();
    syncProps();
    renderLayers();
  });
}

function uid(prefix='layer') { return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2,7)}`; }
function nameOf(obj) { return obj?.name || obj?.text || obj?.type || '레이어'; }
function layerKey(obj) { return obj ? (obj.layerId || obj.id) : null; }
function active() { return canvas.getActiveObject(); }
function objectByLayerId(id) { return canvas.getObjects().find(o => layerKey(o) === id); }
function selectedLayerObject() {
  const obj = active();
  if (obj && !obj.isMaskOverlay && !obj.excludeFromLayers) return obj;
  return objectByLayerId(selectedLayerId);
}
function rememberSelectedLayer(obj) { selectedLayerId = layerKey(obj); }

function ensureMeta(obj, name) {
  obj.id ||= uid(obj.type || 'layer');
  obj.name ||= name || `${obj.type || '레이어'} ${canvas.getObjects().length}`;
  obj.set({ cornerStyle: 'circle', cornerColor: '#7c5cff', borderColor: '#7c5cff', transparentCorners: false });
  return obj;
}

function addToCanvas(obj, name) {
  ensureMeta(obj, name);
  rememberSelectedLayer(obj);
  canvas.add(obj);
  canvas.setActiveObject(obj);
  canvas.renderAll();
  saveHistory();
  syncProps();
  renderLayers();
}

function createDrawingLayer(name) {
  const layerId = uid('drawLayer');
  const layer = new fabric.Rect({
    left: 0, top: 0, width: canvas.width, height: canvas.height,
    fill: 'rgba(0,0,0,0)', strokeWidth: 0, opacity: 0,
    selectable: false, evented: false, excludeFromExport: false,
  });
  layer.id = layerId;
  layer.layerId = layerId;
  layer.name = name || `Drawing Layer ${canvas.getObjects().filter(o => o.isDrawingLayer).length + 1}`;
  layer.isDrawingLayer = true;
  layer.locked = false;
  canvas.add(layer);
  activeDrawingLayerId = layerId;
  rememberSelectedLayer(layer);
  canvas.discardActiveObject();
  canvas.renderAll();
  saveHistory();
  renderLayers();
  setStatus(`${layer.name} 추가 및 선택됨.`);
  return layer;
}

function ensureDefaultDrawingLayer() {
  const first = canvas.getObjects().find(o => o.isDrawingLayer);
  if (first) { activeDrawingLayerId = first.layerId || first.id; return first; }
  return createDrawingLayer('Drawing Layer 1');
}

function getActiveDrawingLayer() {
  let layer = canvas.getObjects().find(o => o.isDrawingLayer && (o.layerId === activeDrawingLayerId || o.id === activeDrawingLayerId));
  if (!layer) layer = ensureDefaultDrawingLayer();
  return layer;
}

function applyDrawingLayerVisibility(layer) {
  const id = layer.layerId || layer.id;
  canvas.getObjects().forEach(o => {
    if (o.isDrawingStroke && o.layerId === id) o.visible = layer.visible !== false;
  });
}

function layerMembers(layer) {
  if (!layer.isDrawingLayer) return [layer];
  const id = layer.layerId || layer.id;
  return canvas.getObjects().filter(o => o === layer || (o.isDrawingStroke && o.layerId === id));
}

function visibleLayerRoots() {
  return canvas.getObjects().filter(o => !o.excludeFromLayers);
}

function setLogicalLayerOrder(panelRootsTopToBottom) {
  const bottomToTop = [...panelRootsTopToBottom].reverse();
  const ordered = [];
  const used = new Set();
  for (const root of bottomToTop) {
    for (const obj of layerMembers(root)) {
      if (!used.has(obj)) { ordered.push(obj); used.add(obj); }
    }
  }
  for (const obj of canvas.getObjects()) {
    if (!used.has(obj)) ordered.unshift(obj);
  }
  canvas._objects = ordered;
  canvas.renderAll();
  saveHistory();
  renderLayers();
}

function moveLayerByDrag(sourceId, targetId) {
  if (!sourceId || !targetId || sourceId === targetId) return;
  const panelRoots = [...visibleLayerRoots()].reverse();
  const source = panelRoots.find(o => o.id === sourceId || o.layerId === sourceId);
  const target = panelRoots.find(o => o.id === targetId || o.layerId === targetId);
  if (!source || !target) return;
  const next = panelRoots.filter(o => o !== source);
  const targetIndex = next.indexOf(target);
  next.splice(targetIndex, 0, source);
  setLogicalLayerOrder(next);
}

function moveLogicalLayer(layer, direction) {
  const roots = visibleLayerRoots();
  const idx = roots.indexOf(layer);
  const targetIdx = direction === 'up' ? idx + 1 : idx - 1;
  if (idx < 0 || targetIdx < 0 || targetIdx >= roots.length) return;

  const target = roots[targetIdx];
  const moving = new Set(layerMembers(layer));
  const targetMembers = new Set(layerMembers(target));
  const withoutBoth = canvas.getObjects().filter(o => !moving.has(o) && !targetMembers.has(o));
  const movingArr = canvas.getObjects().filter(o => moving.has(o));
  const targetArr = canvas.getObjects().filter(o => targetMembers.has(o));

  const insertBefore = direction === 'up' ? targetArr[0] : movingArr[0];
  const sourceOrder = canvas.getObjects();
  const anchorIndex = sourceOrder.indexOf(insertBefore);
  const beforeAnchorWithout = sourceOrder.slice(0, anchorIndex).filter(o => !moving.has(o) && !targetMembers.has(o));
  const afterAnchorWithout = sourceOrder.slice(anchorIndex).filter(o => !moving.has(o) && !targetMembers.has(o));

  canvas._objects = direction === 'up'
    ? [...beforeAnchorWithout, ...targetArr, ...movingArr, ...afterAnchorWithout]
    : [...beforeAnchorWithout, ...movingArr, ...targetArr, ...afterAnchorWithout];
  canvas.renderAll();
  saveHistory();
  renderLayers();
}

function addBlankImageLayer() {
  const rect = new fabric.Rect({ left: 140, top: 140, width: 420, height: 300, fill: 'rgba(255,255,255,0.01)', stroke: '#7c5cff', strokeDashArray: [10, 8], strokeWidth: 2 });
  addToCanvas(rect, 'Blank Image Layer');
}

function setDrawingTool(tool) {
  currentDrawTool = tool;
  canvas.isDrawingMode = tool !== 'select';
  canvas.selection = tool === 'select';
  canvas.discardActiveObject();
  if (tool === 'select') {
    canvas.getObjects().forEach(o => { if (o.__lockedByDraw) { o.selectable = true; delete o.__lockedByDraw; } });
    canvas.renderAll();
    return;
  }
  canvas.getObjects().forEach(o => { if (o.selectable !== false) o.__lockedByDraw = true; o.selectable = false; });
  const drawLayer = getActiveDrawingLayer();
  if (drawLayer.locked) { canvas.isDrawingMode = false; setStatus(`${drawLayer.name} is locked. 레이어 잠금을 풀어야 그릴 수 있습니다.`); return; }
  const eraserSizeEl = $('eraserSize');
  const brushSizeEl = $('brushSize');
  const brushColorEl = $('brushColor');
  const pencilColorEl = $('pencilColorMirror');
  const baseSize = tool === 'eraser' ? (+(eraserSizeEl?.value || brushSizeEl?.value || 16)) : (+(brushSizeEl?.value || 16));
  const color = tool === 'pencil' ? (pencilColorEl?.value || brushColorEl?.value || '#111111') : (brushColorEl?.value || '#111111');
  canvas.freeDrawingBrush = new fabric.PencilBrush(canvas);
  canvas.freeDrawingBrush.width = tool === 'pencil' ? Math.max(1, Math.round(baseSize * 0.35)) : baseSize;
  canvas.freeDrawingBrush.color = tool === 'eraser' ? 'rgba(0,0,0,1)' : color;
}

function fitToCanvasObject(obj, max=560) {
  const scale = Math.min(max / obj.width, max / obj.height, 1);
  obj.set({ left: canvas.width / 2, top: canvas.height / 2, originX: 'center', originY: 'center', scaleX: scale, scaleY: scale });
}

function addImageUrl(url, label='Image') {
  fabric.Image.fromURL(url, (img) => {
    img._originalSrc = url;
    fitToCanvasObject(img);
    addToCanvas(img, label);
    setStatus(`${label} added to canvas.`);
  }, { crossOrigin: 'anonymous' });
}

function addPatchImageUrl(url, bbox, label='AI Patch') {
  return new Promise((resolve, reject) => {
    fabric.Image.fromURL(url, (img) => {
      try {
        img._originalSrc = url;
        const box = bbox || { x: 0, y: 0, width: img.width, height: img.height };
        img.set({
          left: box.x,
          top: box.y,
          originX: 'left',
          originY: 'top',
          scaleX: box.width / img.width,
          scaleY: box.height / img.height,
        });
        ensureMeta(img, label);
        canvas.add(img);
        canvas.setActiveObject(img);
        rememberSelectedLayer(img);
        saveHistory();
        syncProps();
        renderLayers();
        canvas.renderAll();
        setStatus(`${label} added as masked patch layer.`);
        resolve(img);
      } catch (err) { reject(err); }
    }, { crossOrigin: 'anonymous' });
  });
}

function loadHtmlImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('preview image load failed'));
    img.src = url;
  });
}

function canvasWithOnlyObjectDataUrl(obj) {
  return new Promise((resolve, reject) => {
    const el = document.createElement('canvas');
    el.width = canvas.width;
    el.height = canvas.height;
    const tmp = new fabric.StaticCanvas(el, { backgroundColor: 'rgba(0,0,0,0)' });
    obj.clone((clone) => {
      try {
        clone.set({ selectable: false, evented: false });
        tmp.add(clone);
        tmp.renderAll();
        const dataUrl = el.toDataURL('image/png');
        tmp.dispose();
        resolve(dataUrl);
      } catch (err) {
        tmp.dispose();
        reject(err);
      }
    }, ['id','name','_originalSrc','_phase4PreservedOriginal','excludeFromLayers','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId']);
  });
}

async function buildReplacementImageDataUrl(target, patchUrl, bbox) {
  const baseUrl = await canvasWithOnlyObjectDataUrl(target);
  const [base, patch] = await Promise.all([loadHtmlImage(baseUrl), loadHtmlImage(patchUrl)]);
  const el = document.createElement('canvas');
  el.width = canvas.width;
  el.height = canvas.height;
  const ctx = el.getContext('2d');
  ctx.clearRect(0, 0, el.width, el.height);
  ctx.drawImage(base, 0, 0);
  const box = bbox || { x: 0, y: 0, width: patch.naturalWidth || patch.width, height: patch.naturalHeight || patch.height };
  ctx.drawImage(patch, box.x, box.y, box.width, box.height);
  return el.toDataURL('image/png');
}

function addFullCanvasImageDataUrl(dataUrl, label='AI Edit') {
  return new Promise((resolve, reject) => {
    fabric.Image.fromURL(dataUrl, (img) => {
      try {
        img._originalSrc = dataUrl;
        img.set({ left: 0, top: 0, originX: 'left', originY: 'top', scaleX: 1, scaleY: 1 });
        ensureMeta(img, label);
        canvas.add(img);
        canvas.setActiveObject(img);
        rememberSelectedLayer(img);
        saveHistory();
        syncProps();
        renderLayers();
        canvas.renderAll();
        resolve(img);
      } catch (err) { reject(err); }
    }, { crossOrigin: 'anonymous' });
  });
}

function replacementAnchorOptions() {
  return {
    useGripAnchor: $('useGripAnchor')?.checked !== false,
    anchorX: clamp(+($('replaceAnchorX')?.value || 50), 0, 100) / 100,
    anchorY: clamp(+($('replaceAnchorY')?.value || 50), 0, 100) / 100,
    fitScale: clamp(+($('replaceFitScale')?.value || 1), 0.2, 3),
  };
}

function addReplacementImageUrl(url, bbox, label='Replacement Object') {
  return new Promise((resolve, reject) => {
    fabric.Image.fromURL(url, (img) => {
      try {
        img._originalSrc = url;
        const box = bbox || { x: 0, y: 0, width: img.width, height: img.height };
        const opts = replacementAnchorOptions();
        const fit = Math.min(box.width / img.width, box.height / img.height) * opts.fitScale;
        const scale = Number.isFinite(fit) && fit > 0 ? fit : 1;
        const anchor = replacementGripAnchor && opts.useGripAnchor
          ? replacementGripAnchor
          : { x: box.x + box.width / 2, y: box.y + box.height / 2 };
        img.set({
          left: opts.useGripAnchor ? anchor.x - img.width * scale * opts.anchorX : box.x + (box.width - img.width * scale) / 2,
          top: opts.useGripAnchor ? anchor.y - img.height * scale * opts.anchorY : box.y + (box.height - img.height * scale) / 2,
          originX: 'left',
          originY: 'top',
          scaleX: scale,
          scaleY: scale,
        });
        ensureMeta(img, label);
        canvas.add(img);
        canvas.setActiveObject(img);
        rememberSelectedLayer(img);
        saveHistory();
        syncProps();
        renderLayers();
        canvas.renderAll();
        setStatus(`${label} added as separate object layer. ${opts.useGripAnchor && replacementGripAnchor ? '손잡이 앵커 기준으로 배치했습니다.' : 'bbox 중앙 기준으로 배치했습니다.'}`);
        resolve(img);
      } catch (err) { reject(err); }
    }, { crossOrigin: 'anonymous' });
  });
}

function editMaskOverlays() {
  return maskOverlays().filter(o => ['selection-mask','mask-eraser','inverted-hole'].includes(o.maskRole));
}

function positiveEditMaskOverlays() {
  return maskOverlays().filter(o => o.maskRole === 'selection-mask');
}

function occlusionMaskOverlays() {
  return maskOverlays().filter(o => o.maskRole === 'occlusion-mask');
}

function maskBbox(padding = 8) {
  const overlays = positiveEditMaskOverlays();
  if (!overlays.length) return null;
  let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
  overlays.forEach(o => {
    const r = o.getBoundingRect(true, true);
    left = Math.min(left, r.left);
    top = Math.min(top, r.top);
    right = Math.max(right, r.left + r.width);
    bottom = Math.max(bottom, r.top + r.height);
  });
  left = clamp(left - padding, 0, canvas.width);
  top = clamp(top - padding, 0, canvas.height);
  right = clamp(right + padding, 0, canvas.width);
  bottom = clamp(bottom + padding, 0, canvas.height);
  return { x: left, y: top, width: Math.max(1, right - left), height: Math.max(1, bottom - top) };
}

function urlToDataUrl(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const tmp = document.createElement('canvas');
      tmp.width = img.naturalWidth || img.width;
      tmp.height = img.naturalHeight || img.height;
      const ctx = tmp.getContext('2d');
      ctx.drawImage(img, 0, 0, tmp.width, tmp.height);
      resolve(tmp.toDataURL('image/png'));
    };
    img.onerror = reject;
    img.src = url;
  });
}

async function trimImageUrlToAlphaDataUrl(url, pad = 2) {
  const img = await loadImageForCanvas(url);
  const tmp = document.createElement('canvas');
  tmp.width = img.naturalWidth || img.width;
  tmp.height = img.naturalHeight || img.height;
  const ctx = tmp.getContext('2d');
  ctx.drawImage(img, 0, 0, tmp.width, tmp.height);
  const data = ctx.getImageData(0, 0, tmp.width, tmp.height).data;
  let left = tmp.width, top = tmp.height, right = -1, bottom = -1;
  for (let y = 0; y < tmp.height; y++) {
    for (let x = 0; x < tmp.width; x++) {
      const a = data[(y * tmp.width + x) * 4 + 3];
      if (a > 8) {
        left = Math.min(left, x); top = Math.min(top, y); right = Math.max(right, x); bottom = Math.max(bottom, y);
      }
    }
  }
  if (right < left || bottom < top) return url;
  left = Math.max(0, left - pad); top = Math.max(0, top - pad);
  right = Math.min(tmp.width - 1, right + pad); bottom = Math.min(tmp.height - 1, bottom + pad);
  const w = right - left + 1;
  const h = bottom - top + 1;
  const crop = document.createElement('canvas');
  crop.width = w; crop.height = h;
  crop.getContext('2d').drawImage(tmp, left, top, w, h, 0, 0, w, h);
  return crop.toDataURL('image/png');
}

async function createSourceMinusMaskLayer(target, maskDataUrl) {
  if (!target || target.type !== 'image') return false;
  const states = canvas.getObjects().map(o => ({ obj: o, visible: o.visible }));
  const bg = canvas.backgroundColor;
  canvas.getObjects().forEach(o => { o.visible = o === target; });
  target.visible = true;
  canvas.backgroundColor = null;
  canvas.discardActiveObject();
  canvas.renderAll();
  const sourceUrl = canvas.toDataURL({ format: 'png', multiplier: 1 });
  states.forEach(s => { s.obj.visible = s.visible; });
  canvas.backgroundColor = bg;
  canvas.renderAll();

  const [sourceImg, maskImg] = await Promise.all([loadImageForCanvas(sourceUrl), loadImageForCanvas(maskDataUrl)]);
  const tmp = document.createElement('canvas');
  tmp.width = canvas.width;
  tmp.height = canvas.height;
  const ctx = tmp.getContext('2d');
  ctx.drawImage(sourceImg, 0, 0, tmp.width, tmp.height);
  ctx.globalCompositeOperation = 'destination-out';
  ctx.drawImage(maskImg, 0, 0, tmp.width, tmp.height);
  ctx.globalCompositeOperation = 'source-over';
  const holedUrl = tmp.toDataURL('image/png');
  await new Promise(resolve => fabric.Image.fromURL(holedUrl, (img) => {
    img._originalSrc = holedUrl;
    img.set({ left: 0, top: 0, originX: 'left', originY: 'top', selectable: true, evented: true });
    ensureMeta(img, `Source minus mask - ${nameOf(target)}`);
    const idx = canvas.getObjects().indexOf(target);
    target.visible = false;
    canvas.insertAt(img, Math.max(0, idx + 1), false);
    rememberSelectedLayer(img);
    resolve();
  }, { crossOrigin: 'anonymous' }));
  canvas.renderAll();
  saveHistory();
  renderLayers();
  return true;
}

async function createOcclusionLayerFromTarget(target, maskDataUrl) {
  if (!target || target.type !== 'image') return false;
  const states = canvas.getObjects().map(o => ({ obj: o, visible: o.visible }));
  const bg = canvas.backgroundColor;
  canvas.getObjects().forEach(o => { o.visible = o === target; });
  target.visible = true;
  canvas.backgroundColor = null;
  canvas.discardActiveObject();
  canvas.renderAll();
  const sourceUrl = canvas.toDataURL({ format: 'png', multiplier: 1 });
  states.forEach(s => { s.obj.visible = s.visible; });
  canvas.backgroundColor = bg;
  canvas.renderAll();

  const [sourceImg, maskImg] = await Promise.all([loadImageForCanvas(sourceUrl), loadImageForCanvas(maskDataUrl)]);
  const tmp = document.createElement('canvas');
  tmp.width = canvas.width;
  tmp.height = canvas.height;
  const ctx = tmp.getContext('2d');
  ctx.drawImage(sourceImg, 0, 0, tmp.width, tmp.height);
  ctx.globalCompositeOperation = 'destination-in';
  ctx.drawImage(maskImg, 0, 0, tmp.width, tmp.height);
  ctx.globalCompositeOperation = 'source-over';
  const occlusionUrl = tmp.toDataURL('image/png');
  await new Promise(resolve => fabric.Image.fromURL(occlusionUrl, (img) => {
    img._originalSrc = occlusionUrl;
    img.set({ left: 0, top: 0, originX: 'left', originY: 'top', selectable: true, evented: true });
    ensureMeta(img, `Occlusion - ${nameOf(target)}`);
    canvas.add(img);
    canvas.bringToFront(img);
    rememberSelectedLayer(img);
    resolve();
  }, { crossOrigin: 'anonymous' }));
  canvas.renderAll();
  saveHistory();
  renderLayers();
  return true;
}

function loadImageForCanvas(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}

async function generateReplacementObject() {
  const prompt = ($('replaceObjectPrompt')?.value || '').trim();
  const negative = ($('replaceObjectNegative')?.value || '').trim();
  const bbox = maskBbox(10);
  if (!bbox) { alert('먼저 Mask 툴로 교체할 물체 영역을 칠하세요.'); return; }
  if (!prompt) { alert('새 오브젝트 설명을 입력하세요.'); $('replaceObjectPrompt')?.focus(); return; }
  const btn = $('generateReplacement');
  btn.disabled = true;
  if ($('replaceResult')) $('replaceResult').textContent = '새 오브젝트만 생성 중...';
  setStatus('B안: 원본 보호 + 새 오브젝트 PNG 생성 중...');
  try {
    const target = selectedLayerObject();
    const contextName = target ? nameOf(target) : 'current canvas';
    const objectPrompt = `${prompt}\n\nGenerate ONLY the replacement object as an isolated transparent-friendly game asset. It will be placed over a masked area of ${contextName}. Do not include the original character, hand, body, scene, background panel, text, logo, watermark, or full image redraw. Match pixel/game asset style, scale, outline thickness, angle, and lighting. Negative: ${negative || 'background, character body, text, watermark'}`;
    const gen = await fetch('/api/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ prompt: objectPrompt, preset: 'game', aspect_ratio: 'square' })
    });
    const genData = await gen.json();
    if (!gen.ok || !genData.success) throw new Error(genData.error || 'object generation failed');
    let objectUrl = genData.url + '?t=' + Date.now();
    let method = 'generated-layer';
    try {
      const image = await urlToDataUrl(objectUrl);
      const cut = await fetch('/api/remove-bg', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ image, tolerance: +($('tolerance')?.value || 24), mode: 'sheet' })
      });
      const cutData = await cut.json();
      if (cut.ok && cutData.success) {
        objectUrl = cutData.url + '?t=' + Date.now();
        method = `generated+${cutData.method}`;
      }
    } catch (_cutErr) {
      method = 'generated-layer:bg-removal-skipped';
    }
    objectUrl = await trimImageUrlToAlphaDataUrl(objectUrl, 2);
    addGallery(objectUrl, 'replacement');
    let cleared = false;
    if ($('clearOriginalUnderMask')?.checked && target?.type === 'image') {
      const mask = await buildMaskDataUrl('edit');
      if (mask) cleared = await createSourceMinusMaskLayer(target, mask);
    }
    await addReplacementImageUrl(objectUrl, bbox, `Replacement - ${prompt.slice(0, 28)}`);
    let occluded = false;
    if ($('createOcclusionLayer')?.checked && target?.type === 'image' && occlusionMaskOverlays().length) {
      const occMask = await buildMaskDataUrl('occlusion');
      if (occMask) occluded = await createOcclusionLayerFromTarget(target, occMask);
    }
    const anchorText = replacementGripAnchor && $('useGripAnchor')?.checked !== false ? '앵커 배치 + ' : 'bbox 배치 + ';
    if ($('replaceResult')) $('replaceResult').textContent = `완료: ${cleared ? '기존 물체 영역 비움 + ' : ''}${anchorText}새 오브젝트 레이어 생성${occluded ? ' + 손/앞가림 레이어 생성' : ''} (${method}). 원본 레이어는 숨김 보존됨.`;
  } catch (err) {
    const msg = `오브젝트 치환 실패: ${err.message}`;
    if ($('replaceResult')) $('replaceResult').textContent = msg;
    setStatus(msg);
  } finally {
    btn.disabled = false;
    updateMaskInfo();
  }
}

function exportCanvasWithoutMaskOverlays() {
  const overlays = maskOverlays();
  const states = overlays.map(o => ({ obj: o, visible: o.visible }));
  overlays.forEach(o => { o.visible = false; });
  canvas.discardActiveObject();
  canvas.renderAll();
  const dataUrl = canvas.toDataURL({ format: 'png', multiplier: 1 });
  states.forEach(s => { s.obj.visible = s.visible; });
  canvas.renderAll();
  return dataUrl;
}

function addGallery(url, label='asset') {
  const card = document.createElement('div');
  card.className = 'asset-card';
  card.innerHTML = `<img src="${url}"><span>${label}</span>`;
  card.onclick = () => addImageUrl(url, label);
  $('gallery').prepend(card);
}

function syncProps() {
  const obj = selectedLayerObject();
  $('selectedName').textContent = obj ? `${nameOf(obj)} (${obj.isDrawingLayer ? 'drawing layer' : obj.type})` : '선택 없음';
  for (const id of ['propX','propY','propW','propH','propRot','propOpacity','textContent']) $(id).value = '';
  if (!obj || obj.isDrawingLayer) return;
  $('propX').value = Math.round(obj.left || 0);
  $('propY').value = Math.round(obj.top || 0);
  $('propW').value = Math.round(obj.getScaledWidth());
  $('propH').value = Math.round(obj.getScaledHeight());
  $('propRot').value = Math.round(obj.angle || 0);
  $('propOpacity').value = obj.opacity ?? 1;
  if (obj.type === 'textbox' || obj.type === 'i-text') {
    $('textContent').value = obj.text || '';
    $('fontSize').value = obj.fontSize || 72;
    $('strokeWidth').value = obj.strokeWidth || 0;
    $('fillColor').value = toHex(obj.fill || '#ffffff');
    $('strokeColor').value = toHex(obj.stroke || '#000000');
  } else if (obj.fill) {
    $('fillColor').value = toHex(obj.fill);
    $('strokeColor').value = toHex(obj.stroke || '#000000');
  }
}

function toHex(color) {
  if (!color || typeof color !== 'string') return '#000000';
  if (color.startsWith('#')) return color.slice(0,7);
  const m = color.match(/\d+/g);
  if (!m) return '#000000';
  return '#' + m.slice(0,3).map(n => (+n).toString(16).padStart(2,'0')).join('');
}

function renameLayer(obj, newName) {
  const clean = (newName || '').trim();
  if (!clean) return;
  obj.name = clean;
  if (obj.isDrawingLayer) {
    const id = obj.layerId || obj.id;
    canvas.getObjects().forEach(o => { if (o.isDrawingStroke && o.layerId === id) o.parentLayerName = clean; });
  }
  saveHistory();
  renderLayers();
  setStatus(`Layer renamed to ${clean}.`);
}

function beginRenameLayer(item, obj) {
  const label = item.querySelector('.layer-name');
  if (!label || item.querySelector('.layer-rename-input')) return;
  item.draggable = false;
  const input = document.createElement('input');
  input.className = 'layer-rename-input';
  input.value = nameOf(obj);
  label.replaceWith(input);
  input.focus();
  input.select();
  const finish = (commit) => {
    item.draggable = true;
    if (commit) renameLayer(obj, input.value);
    else renderLayers();
  };
  input.onkeydown = (e) => {
    if (e.key === 'Enter') finish(true);
    if (e.key === 'Escape') finish(false);
  };
  input.onblur = () => finish(true);
}

function renderLayers() {
  const box = $('layers');
  box.innerHTML = '';
  const objs = [...canvas.getObjects()].filter(obj => !obj.excludeFromLayers).reverse();
  const a = active();
  objs.forEach((obj, idx) => {
    const item = document.createElement('div');
    const isSelected = obj === a || (!a && layerKey(obj) === selectedLayerId);
    item.className = 'layer-item' + (isSelected ? ' active' : '');
    const icon = obj.isDrawingLayer ? '✎' : (obj.visible === false ? '🙈' : '👁');
    item.innerHTML = `<span>${icon}</span><span class="layer-name" title="Double-click to rename">${nameOf(obj)}</span><button data-act="rename">✎</button><button data-act="up">↑</button><button data-act="down">↓</button><button data-act="vis">V</button><button data-act="lock">L</button>`;
    item.draggable = true;
    const dragId = obj.layerId || obj.id;
    item.dataset.layerId = dragId;
    item.ondragstart = (e) => {
      e.dataTransfer.setData('text/plain', dragId);
      e.dataTransfer.effectAllowed = 'move';
      item.classList.add('dragging');
    };
    item.ondragend = () => {
      item.classList.remove('dragging');
      document.querySelectorAll('.layer-item.drag-over').forEach(el => el.classList.remove('drag-over'));
    };
    item.ondragover = (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      item.classList.add('drag-over');
    };
    item.ondragleave = () => item.classList.remove('drag-over');
    item.ondrop = (e) => {
      e.preventDefault();
      item.classList.remove('drag-over');
      moveLayerByDrag(e.dataTransfer.getData('text/plain'), dragId);
    };
    item.onclick = (e) => {
      if (e.target.dataset.act === 'rename') { beginRenameLayer(item, obj); return; }
      if (e.target.dataset.act === 'up') { moveLogicalLayer(obj, 'up'); return; }
      if (e.target.dataset.act === 'down') { moveLogicalLayer(obj, 'down'); return; }
      if (e.target.dataset.act === 'vis') {
        obj.visible = !obj.visible;
        if (obj.isDrawingLayer) applyDrawingLayerVisibility(obj);
        canvas.renderAll(); saveHistory(); renderLayers(); return;
      }
      if (e.target.dataset.act === 'lock') {
        if (obj.isDrawingLayer) obj.locked = !obj.locked;
        else obj.selectable = obj.evented = !(obj.selectable !== false);
        canvas.discardActiveObject(); canvas.renderAll(); saveHistory(); renderLayers(); return;
      }
      if (obj.isDrawingLayer) {
        activeDrawingLayerId = obj.layerId || obj.id;
        rememberSelectedLayer(obj);
        canvas.discardActiveObject();
        canvas.renderAll(); syncProps(); renderLayers();
        setStatus(`${obj.name} selected for drawing.`);
        return;
      }
      canvas.setActiveObject(obj); rememberSelectedLayer(obj); canvas.renderAll(); syncProps(); renderLayers();
    };
    item.ondblclick = (e) => {
      if (e.target.classList.contains('layer-name') || e.target === item) beginRenameLayer(item, obj);
    };
    box.appendChild(item);
  });
  updateEmptyCanvasHint();
}

function setCanvasSize(w, h) {
  canvas.setWidth(w); canvas.setHeight(h);
  canvas.getObjects().forEach(o => { if (o.isDrawingLayer) o.set({ width: w, height: h }); });
  $('canvasW').value = w; $('canvasH').value = h;
  canvas.renderAll();
  fitView();
  saveHistory();
}

function canvasStageMetrics(scale = viewScale) {
  const workspace = $('workspace');
  const shell = $('canvasShell');
  const baseW = shell.offsetWidth || (canvas.width + 36);
  const baseH = shell.offsetHeight || (canvas.height + 36);
  const scaledW = baseW * scale;
  const scaledH = baseH * scale;
  const stageW = workspace.clientWidth;
  const stageH = workspace.clientHeight;
  const baseLeft = Math.round((stageW - scaledW) / 2);
  const baseTop = Math.round((stageH - scaledH) / 2);
  return { scaledW, scaledH, stageW, stageH, baseLeft, baseTop };
}

function updateCanvasStageSize() {
  const workspace = $('workspace');
  const stage = $('canvasStage');
  const shell = $('canvasShell');
  if (!workspace || !stage || !shell) return { left: 0, top: 0, scaledW: 0, scaledH: 0 };
  const metrics = canvasStageMetrics();
  const left = Math.round(metrics.baseLeft + canvasPanOffset.x);
  const top = Math.round(metrics.baseTop + canvasPanOffset.y);
  stage.style.width = `${metrics.stageW}px`;
  stage.style.height = `${metrics.stageH}px`;
  shell.style.left = `${left}px`;
  shell.style.top = `${top}px`;
  return { left, top, ...metrics };
}

function setViewScale(scale, anchorEvent = null) {
  const workspace = $('workspace');
  const shell = document.querySelector('.canvas-shell');
  const previous = viewScale;
  const next = Math.max(0.1, Math.min(4, scale));
  const prevLeft = parseFloat(shell.style.left || '0') || 0;
  const prevTop = parseFloat(shell.style.top || '0') || 0;

  let anchorX = workspace.clientWidth / 2;
  let anchorY = workspace.clientHeight / 2;
  if (anchorEvent) {
    const wsRect = workspace.getBoundingClientRect();
    anchorX = anchorEvent.clientX - wsRect.left;
    anchorY = anchorEvent.clientY - wsRect.top;
  }
  const contentX = (anchorX - prevLeft) / previous;
  const contentY = (anchorY - prevTop) / previous;

  viewScale = next;
  shell.style.transform = `scale(${viewScale})`;
  shell.style.transformOrigin = 'top left';
  const nextMetrics = canvasStageMetrics(next);
  canvasPanOffset.x = anchorX - nextMetrics.baseLeft - contentX * next;
  canvasPanOffset.y = anchorY - nextMetrics.baseTop - contentY * next;
  const pos = updateCanvasStageSize();
  if ($('zoomLabel')) $('zoomLabel').textContent = `${Math.round(viewScale * 100)}%`;
  return pos;
}

function fitView() {
  const workspace = $('workspace');
  const scale = Math.min((workspace.clientWidth - 90) / canvas.width, (workspace.clientHeight - 90) / canvas.height, 1);
  setViewScale(scale);
}

function downloadDataUrl(dataUrl, name) {
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = name;
  a.click();
}

function exportFull() {
  canvas.discardActiveObject();
  canvas.renderAll();
  downloadDataUrl(canvas.toDataURL({ format: 'png', multiplier: 1 }), 'asset-studio-export.png');
  setStatus('전체 PNG를 내보냈습니다.');
}

function exportSelectedOnly() {
  const obj = active();
  if (!obj) { alert('먼저 레이어를 선택하세요.'); return; }
  const r = obj.getBoundingRect(true, true);
  const pad = 8;
  const data = canvas.toDataURL({
    format: 'png',
    left: Math.max(0, r.left - pad),
    top: Math.max(0, r.top - pad),
    width: Math.min(canvas.width, r.width + pad * 2),
    height: Math.min(canvas.height, r.height + pad * 2),
    multiplier: 1,
  });
  downloadDataUrl(data, 'selected-layer.png');
  setStatus('선택 PNG를 내보냈습니다.');
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function handleFiles(files) {
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue;
    const dataUrl = await fileToDataUrl(file);
    addGallery(dataUrl, file.name.replace(/\.[^.]+$/, '').slice(0,20));
    addImageUrl(dataUrl, file.name);
  }
  setStatus(`${files.length} file(s) loaded.`);
}

async function removeColor(target) {
  const obj = selectedLayerObject();
  if (!obj || obj.type !== 'image') {
    const label = obj ? `${nameOf(obj)} (${obj.isDrawingLayer ? 'drawing layer' : obj.type})` : '없음';
    alert(`배경 제거는 이미지 레이어에서만 가능합니다. 현재 선택: ${label}`);
    return;
  }
  if (!obj._originalSrc) obj._originalSrc = obj.getSrc();
  const imgEl = obj.getElement();
  const temp = document.createElement('canvas');
  temp.width = imgEl.naturalWidth || imgEl.width;
  temp.height = imgEl.naturalHeight || imgEl.height;
  const ctx = temp.getContext('2d');
  ctx.drawImage(imgEl, 0, 0, temp.width, temp.height);
  const imageData = ctx.getImageData(0, 0, temp.width, temp.height);
  const d = imageData.data;
  const tol = +$('tolerance').value;
  for (let i = 0; i < d.length; i += 4) {
    const dist = Math.hypot(d[i] - target[0], d[i+1] - target[1], d[i+2] - target[2]);
    if (dist <= tol) d[i+3] = 0;
  }
  ctx.putImageData(imageData, 0, 0);
  const url = temp.toDataURL('image/png');
  fabric.Image.fromURL(url, (newImg) => {
    newImg.set({
      id: obj.id, name: obj.name, left: obj.left, top: obj.top, scaleX: obj.scaleX, scaleY: obj.scaleY,
      angle: obj.angle, opacity: obj.opacity, originX: obj.originX, originY: obj.originY, flipX: obj.flipX, flipY: obj.flipY,
    });
    newImg._originalSrc = obj._originalSrc;
    const idx = canvas.getObjects().indexOf(obj);
    canvas.remove(obj);
    canvas.insertAt(ensureMeta(newImg, obj.name), idx, false);
    canvas.setActiveObject(newImg);
    canvas.renderAll();
    saveHistory(); syncProps(); renderLayers();
    setStatus('선택 이미지의 색상 배경을 제거했습니다.');
  });
}

function imageObjectToDataUrl(obj) {
  const imgEl = obj.getElement();
  const temp = document.createElement('canvas');
  temp.width = imgEl.naturalWidth || imgEl.videoWidth || imgEl.width;
  temp.height = imgEl.naturalHeight || imgEl.videoHeight || imgEl.height;
  const ctx = temp.getContext('2d');
  ctx.drawImage(imgEl, 0, 0, temp.width, temp.height);
  return temp.toDataURL('image/png');
}

async function removeBgSelected(mode='ai') {
  const obj = selectedLayerObject();
  if (!obj || obj.type !== 'image') {
    const label = obj ? `${nameOf(obj)} (${obj.isDrawingLayer ? 'drawing layer' : obj.type})` : '없음';
    alert(`Remove BG는 이미지 레이어에서만 가능합니다. 현재 선택: ${label}`);
    return;
  }
  const btn = mode === 'sheet' ? $('removeSheetBg') : $('removeBg');
  btn.disabled = true;
  setStatus(mode === 'sheet' ? 'Asset Sheet BG running... 여러 아이템을 보존하는 테두리 배경 제거 중입니다.' : 'AI Cutout running... 첫 실행은 모델 다운로드 때문에 오래 걸릴 수 있습니다.');
  try {
    if (!obj._originalSrc) obj._originalSrc = obj.getSrc();
    const image = imageObjectToDataUrl(obj);
    const res = await fetch('/api/remove-bg', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ image, tolerance: +$('tolerance').value || (mode === 'sheet' ? 24 : 36), mode })
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || 'remove-bg failed');
    const url = data.url + '?t=' + Date.now();
    fabric.Image.fromURL(url, (cutout) => {
      cutout.set({
        left: obj.left, top: obj.top, scaleX: obj.scaleX, scaleY: obj.scaleY,
        angle: obj.angle, opacity: obj.opacity, originX: obj.originX, originY: obj.originY,
        flipX: obj.flipX, flipY: obj.flipY,
      });
      cutout._originalSrc = url;
      ensureMeta(cutout, `Cutout - ${nameOf(obj)}`);
      const idx = canvas.getObjects().indexOf(obj);
      obj.visible = false;
      canvas.insertAt(cutout, idx + 1, false);
      canvas.backgroundColor = null;
      $('canvasShell').classList.add('checker');
      canvas.setActiveObject(cutout);
      rememberSelectedLayer(cutout);
      canvas.renderAll();
      saveHistory(); syncProps(); renderLayers();
      addGallery(url, 'cutout');
      setStatus(`${mode === 'sheet' ? 'Asset Sheet BG' : 'AI Cutout'} complete (${data.method}). 원본은 숨김 처리했고 Cutout 레이어를 새로 만들었습니다.`);
    }, { crossOrigin: 'anonymous' });
  } catch (err) {
    setStatus('Remove BG failed: ' + err.message);
    alert('Remove BG 실패: ' + err.message);
  } finally {
    btn.disabled = false;
  }
}

function resetImage() {
  const obj = active();
  if (!obj || obj.type !== 'image' || !obj._originalSrc) return;
  const src = obj._originalSrc;
  fabric.Image.fromURL(src, (newImg) => {
    newImg.set({ id: obj.id, name: obj.name, left: obj.left, top: obj.top, scaleX: obj.scaleX, scaleY: obj.scaleY, angle: obj.angle, opacity: obj.opacity, originX: obj.originX, originY: obj.originY });
    newImg._originalSrc = src;
    const idx = canvas.getObjects().indexOf(obj);
    canvas.remove(obj); canvas.insertAt(ensureMeta(newImg, obj.name), idx, false); canvas.setActiveObject(newImg); canvas.renderAll(); saveHistory(); syncProps(); renderLayers();
    setStatus('이미지를 원본으로 복원했습니다.');
  }, { crossOrigin: 'anonymous' });
}

function maskOverlays() {
  return canvas.getObjects().filter(o => o.isMaskOverlay);
}

function refreshMaskStateFromCanvas() {
  const overlays = maskOverlays();
  maskRegions = overlays.filter(o => o.maskRole !== 'grip-anchor').map(o => ({
    id: o.maskRegionId || o.id || uid('maskRegion'),
    left: o.left || 0,
    top: o.top || 0,
    width: Math.max(0, (o.width || 0) * (o.scaleX || 1)),
    height: Math.max(0, (o.height || 0) * (o.scaleY || 1)),
    targetLayerId: o.targetLayerId || selectedLayerId || null,
  }));
  const anchor = overlays.find(o => o.maskRole === 'grip-anchor');
  replacementGripAnchor = anchor ? { x: anchor.left || 0, y: anchor.top || 0 } : null;
  updateMaskInfo();
}

function updateMaskInfo() {
  const editCount = positiveEditMaskOverlays().length;
  const occCount = occlusionMaskOverlays().length;
  const anchorText = replacementGripAnchor ? ` · 앵커 (${Math.round(replacementGripAnchor.x)}, ${Math.round(replacementGripAnchor.y)})` : ' · 앵커 없음';
  const label = `교체 마스크: ${editCount} · 앞가림: ${occCount}${anchorText}`;
  const target = selectedLayerObject();
  const targetText = target ? `${nameOf(target)} (${target.type || 'layer'})` : '대상 레이어 없음';
  if ($('maskInfo')) $('maskInfo').textContent = label;
  if ($('aiMaskSummary')) $('aiMaskSummary').textContent = editCount ? `${label} · 대상: ${targetText}` : '선택된 교체 마스크 없음';
  if ($('runInpaint')) $('runInpaint').disabled = editCount === 0;
  if ($('generateReplacement')) $('generateReplacement').disabled = editCount === 0;
  if ($('replaceResult') && editCount === 0) $('replaceResult').textContent = '교체 마스크+앵커 선택 후 새 오브젝트를 생성합니다.';
  if ($('inpaintResult') && editCount === 0) $('inpaintResult').textContent = '마스크 선택 후 실행할 수 있습니다.';
}

function updateEmptyCanvasHint() {
  const hint = $('emptyCanvasHint');
  if (!hint) return;
  const hasUserVisibleObject = canvas.getObjects().some(o =>
    !o.isDrawingLayer && !o.isMaskOverlay && o.visible !== false && !o.excludeFromExport
  );
  hint.classList.toggle('hidden', hasUserVisibleObject);
}

function decorateMaskOverlay(obj, role = 'selection-mask') {
  const target = selectedLayerObject();
  obj.id ||= uid(role === 'mask-eraser' ? 'maskErase' : role === 'occlusion-mask' ? 'occMask' : role === 'grip-anchor' ? 'gripAnchor' : 'mask');
  const names = {
    'mask-eraser': '교체 마스크 지우개',
    'occlusion-mask': '손/앞가림 마스크',
    'grip-anchor': '손잡이 앵커',
    'selection-mask': obj.type === 'path' ? '교체 마스크 브러시' : '교체 마스크 사각',
  };
  obj.name = names[role] || '마스크';
  obj.isMaskOverlay = true;
  obj.maskRole = role;
  obj.maskRegionId = obj.maskRegionId || obj.id;
  obj.targetLayerId = target ? layerKey(target) : selectedLayerId;
  obj.selectable = false;
  obj.evented = false;
  obj.excludeFromLayers = true;
  obj.excludeFromExport = true;
  obj.objectCaching = false;
  return obj;
}

function makeMaskOverlay(region) {
  const rect = new fabric.Rect({
    left: region.left,
    top: region.top,
    width: region.width,
    height: region.height,
    fill: 'rgba(239,68,68,0.34)',
    stroke: '#ff3b3b',
    strokeWidth: 2,
    strokeDashArray: [8, 5],
    selectable: false,
    evented: false,
    excludeFromLayers: true,
    excludeFromExport: true,
    objectCaching: false,
  });
  return decorateMaskOverlay(rect, 'selection-mask');
}

function addMaskPath(path, role = 'selection-mask') {
  decorateMaskOverlay(path, role);
  const isErase = role === 'mask-eraser';
  const isOcclusion = role === 'occlusion-mask';
  path.set({
    fill: null,
    stroke: isErase ? 'rgba(34,197,94,0.78)' : (isOcclusion ? 'rgba(59,130,246,0.68)' : 'rgba(239,68,68,0.62)'),
    strokeLineCap: 'round',
    strokeLineJoin: 'round',
    strokeDashArray: isErase ? [6, 6] : null,
  });
  canvas.bringToFront(path);
  canvas.renderAll();
  saveHistory();
  updateMaskInfo();
  if (isOcclusion) setStatus('손/앞가림 마스크 추가. 오브젝트 생성 후 원본 손 픽셀을 위 레이어로 복원합니다.');
  else setStatus(isErase ? '교체 마스크 지우개 stroke added. Export PNG에서는 보호 영역으로 빠집니다.' : '교체 영역 마스크 stroke added.');
  return path;
}

function addMaskRect(left, top, width, height) {
  const x = Math.max(0, Math.min(left, left + width));
  const y = Math.max(0, Math.min(top, top + height));
  const w = Math.min(canvas.width - x, Math.abs(width));
  const h = Math.min(canvas.height - y, Math.abs(height));
  if (w < 4 || h < 4) return null;
  const target = selectedLayerObject();
  const region = { id: uid('maskRegion'), left: x, top: y, width: w, height: h, targetLayerId: target ? layerKey(target) : selectedLayerId };
  const overlay = makeMaskOverlay(region);
  overlay.maskRegionId = region.id;
  overlay.targetLayerId = region.targetLayerId;
  canvas.add(overlay);
  canvas.bringToFront(overlay);
  maskRegions.push(region);
  canvas.renderAll();
  saveHistory();
  updateMaskInfo();
  setStatus(`교체 마스크 사각 추가: ${Math.round(w)}×${Math.round(h)}.`);
  return overlay;
}

function setGripAnchorAt(x, y) {
  maskOverlays().filter(o => o.maskRole === 'grip-anchor').forEach(o => canvas.remove(o));
  replacementGripAnchor = { x: clamp(x, 0, canvas.width), y: clamp(y, 0, canvas.height) };
  const c = new fabric.Circle({
    left: replacementGripAnchor.x,
    top: replacementGripAnchor.y,
    radius: 8,
    originX: 'center',
    originY: 'center',
    fill: 'rgba(250,204,21,0.85)',
    stroke: '#111827',
    strokeWidth: 2,
    selectable: false,
    evented: false,
    excludeFromLayers: true,
    excludeFromExport: true,
    objectCaching: false,
  });
  decorateMaskOverlay(c, 'grip-anchor');
  canvas.add(c);
  canvas.bringToFront(c);
  canvas.renderAll();
  saveHistory();
  updateMaskInfo();
  setStatus(`손잡이 앵커 지정: ${Math.round(replacementGripAnchor.x)}, ${Math.round(replacementGripAnchor.y)}. 새 오브젝트의 grip %가 이 점에 맞춰집니다.`);
  return c;
}

function clearMask() {
  const overlays = maskOverlays();
  overlays.forEach(o => canvas.remove(o));
  maskRegions = [];
  replacementGripAnchor = null;
  canvas.renderAll();
  saveHistory();
  updateMaskInfo();
  setStatus('마스크/앵커를 지웠습니다.');
}

function invertMask() {
  const overlays = positiveEditMaskOverlays();
  if (!overlays.length) { alert('반전할 교체 마스크가 없습니다. 먼저 Mask 툴로 영역을 만드세요.'); return; }
  const existing = overlays.map(o => ({ left: o.left || 0, top: o.top || 0, width: (o.width || 0) * (o.scaleX || 1), height: (o.height || 0) * (o.scaleY || 1) }));
  overlays.forEach(o => canvas.remove(o));
  maskRegions = [];
  const full = { id: uid('maskRegion'), left: 0, top: 0, width: canvas.width, height: canvas.height, targetLayerId: selectedLayerId };
  const base = makeMaskOverlay(full);
  base.fill = 'rgba(239,68,68,0.18)';
  base.stroke = '#ff3b3b';
  canvas.add(base);
  existing.forEach(r => {
    const hole = new fabric.Rect({ left: r.left, top: r.top, width: r.width, height: r.height, fill: 'rgba(34,197,94,0.28)', stroke: '#22c55e', strokeWidth: 1, strokeDashArray: [4, 4], selectable: false, evented: false, excludeFromLayers: true, excludeFromExport: true, objectCaching: false });
    hole.id = uid('maskHole'); hole.name = 'Mask Invert Hole'; hole.isMaskOverlay = true; hole.maskRole = 'inverted-hole'; hole.maskRegionId = hole.id; hole.targetLayerId = selectedLayerId;
    canvas.add(hole); canvas.bringToFront(hole);
  });
  maskRegions.push(full);
  canvas.renderAll();
  saveHistory();
  updateMaskInfo();
  setStatus('Mask inverted visually. Phase 3A에서는 반전 미리보기까지 지원합니다.');
}

async function buildMaskDataUrl(kind = 'edit') {
  const overlays = kind === 'occlusion' ? occlusionMaskOverlays() : editMaskOverlays();
  if (!overlays.length) return null;
  const tmp = document.createElement('canvas');
  tmp.width = canvas.width; tmp.height = canvas.height;
  const maskCanvas = new fabric.StaticCanvas(tmp, { backgroundColor: '#000' });
  for (const o of overlays) {
    if (o.maskRole === 'grip-anchor' || o.maskRole === 'preview' || o.maskRole === 'inverted-hole') continue;
    const clone = await new Promise(resolve => o.clone(resolve, ['maskRole','isMaskOverlay']));
    const isErase = o.maskRole === 'mask-eraser';
    clone.set({
      fill: o.type === 'rect' ? (isErase ? '#000' : '#fff') : null,
      stroke: isErase ? '#000' : '#fff',
      opacity: 1,
      selectable: false,
      evented: false,
      shadow: null,
      strokeDashArray: null,
      globalCompositeOperation: 'source-over',
    });
    maskCanvas.add(clone);
  }
  maskCanvas.renderAll();
  const dataUrl = tmp.toDataURL('image/png');
  maskCanvas.dispose();
  return dataUrl;
}

async function exportMaskPng() {
  const dataUrl = await buildMaskDataUrl();
  if (!dataUrl) { alert('Export할 마스크가 없습니다.'); return; }
  downloadDataUrl(dataUrl, 'asset-studio-mask.png');
  setStatus('Mask PNG를 내보냈습니다: 흰색=수정 영역, 검은색=보호 영역.');
}

function setInpaintBusy(isBusy) {
  if ($('runInpaint')) $('runInpaint').disabled = isBusy;
  if ($('applyInpaintNewLayer')) $('applyInpaintNewLayer').disabled = isBusy || !pendingInpaintResult;
  if ($('applyInpaintReplace')) $('applyInpaintReplace').disabled = isBusy || !pendingInpaintResult;
  if ($('retryInpaint')) $('retryInpaint').disabled = isBusy || !pendingInpaintResult;
  if ($('cancelInpaint')) $('cancelInpaint').disabled = isBusy || !pendingInpaintResult;
}

function clearPendingInpaintResult(message='AI 결과 미리보기를 취소했습니다.') {
  pendingInpaintResult = null;
  if ($('inpaintPreviewPanel')) $('inpaintPreviewPanel').classList.add('hidden');
  if ($('inpaintPreviewImg')) $('inpaintPreviewImg').removeAttribute('src');
  if ($('inpaintResult')) $('inpaintResult').textContent = message;
  setInpaintBusy(false);
}

function showPendingInpaintResult(data, prompt, negative, target) {
  const url = data.url + '?t=' + Date.now();
  pendingInpaintResult = {
    ...data,
    url,
    prompt,
    negative,
    targetLayerId: layerKey(target),
    targetName: nameOf(target),
    label: `AI Edit - ${prompt.slice(0, 28) || nameOf(target)}`,
  };
  if ($('inpaintPreviewImg')) $('inpaintPreviewImg').src = url;
  if ($('inpaintPreviewPanel')) $('inpaintPreviewPanel').classList.remove('hidden');
  if ($('inpaintResult')) $('inpaintResult').textContent = `미리보기 생성 완료. 적용 방식을 선택하세요. ${data.method || ''} ${data.model || ''}`.trim();
  setInpaintBusy(false);
}

async function applyPendingInpaintAsLayer() {
  if (!pendingInpaintResult) return;
  setInpaintBusy(true);
  try {
    await addPatchImageUrl(pendingInpaintResult.url, pendingInpaintResult.bbox, `${pendingInpaintResult.label} patch`);
    clearPendingInpaintResult('새 패치 레이어로 적용했습니다. Undo/Redo에 반영됨.');
  } catch (err) {
    if ($('inpaintResult')) $('inpaintResult').textContent = `적용 실패: ${err.message}`;
    setInpaintBusy(false);
  }
}

async function applyPendingInpaintAsReplacement() {
  if (!pendingInpaintResult) return;
  const target = objectByLayerId(pendingInpaintResult.targetLayerId);
  if (!target || target.type !== 'image') {
    if ($('inpaintResult')) $('inpaintResult').textContent = '교체 실패: 원본 이미지 레이어를 찾을 수 없습니다.';
    return;
  }
  setInpaintBusy(true);
  try {
    const dataUrl = await buildReplacementImageDataUrl(target, pendingInpaintResult.url, pendingInpaintResult.bbox);
    target.visible = false;
    target._phase4PreservedOriginal = true;
    await addFullCanvasImageDataUrl(dataUrl, `${pendingInpaintResult.label} replacement`);
    saveHistory();
    renderLayers();
    canvas.renderAll();
    clearPendingInpaintResult('선택 이미지를 교체본 레이어로 적용했습니다. 원본은 숨김 보존됨.');
  } catch (err) {
    if ($('inpaintResult')) $('inpaintResult').textContent = `교체 실패: ${err.message}`;
    setInpaintBusy(false);
  }
}

async function retryPendingInpaint() {
  if (!pendingInpaintResult) return;
  const { prompt, negative } = pendingInpaintResult;
  clearPendingInpaintResult('다시 생성 요청 준비 중...');
  if ($('inpaintPrompt')) $('inpaintPrompt').value = prompt;
  if ($('inpaintNegative')) $('inpaintNegative').value = negative || '';
  await runSelectedAreaAiEdit();
}

async function runSelectedAreaAiEdit() {
  const prompt = ($('inpaintPrompt')?.value || '').trim();
  const negative = ($('inpaintNegative')?.value || '').trim();
  const overlays = maskOverlays().filter(o => o.maskRole !== 'inverted-hole' && o.maskRole !== 'preview');
  if (!overlays.length) { alert('먼저 Mask 툴로 바꿀 영역을 선택하세요.'); return; }
  if (!prompt) { alert('선택영역을 어떻게 바꿀지 프롬프트를 입력하세요.'); $('inpaintPrompt')?.focus(); return; }
  const target = selectedLayerObject();
  if (!target || target.type !== 'image' || target.isDrawingLayer || target.excludeFromLayers) {
    const label = target ? `${nameOf(target)} (${target.isDrawingLayer ? 'drawing layer' : target.type})` : '선택 없음';
    alert(`AI 선택영역 편집은 이미지 레이어만 가능합니다. 현재 선택: ${label}`);
    return;
  }
  const mask = await buildMaskDataUrl();
  const image = exportCanvasWithoutMaskOverlays();
  pendingInpaintResult = null;
  setInpaintBusy(true);
  if ($('inpaintPreviewPanel')) $('inpaintPreviewPanel').classList.add('hidden');
  if ($('inpaintResult')) $('inpaintResult').textContent = '선택영역 AI 수정 요청 중...';
  setStatus('선택영역 AI 수정 요청 중...');
  try {
    const res = await fetch('/api/inpaint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image, mask, prompt, negative, apply_mode: 'preview', target_layer_id: layerKey(target) }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || 'inpaint failed');
    showPendingInpaintResult(data, prompt, negative, target);
    setStatus('선택영역 AI 미리보기 생성 완료. 적용 방식을 선택하세요.');
  } catch (err) {
    const msg = `AI selected-area edit failed: ${err.message}`;
    if ($('inpaintResult')) $('inpaintResult').textContent = msg;
    setStatus(msg);
    setInpaintBusy(false);
  } finally {
    updateMaskInfo();
  }
}

function configureMaskBrush() {
  if (currentTool !== 'mask') return;
  maskDrawMode = $('maskMode')?.value || maskDrawMode || 'brush';
  const size = +($('maskSize')?.value || 48);
  if ($('maskSizeValue')) $('maskSizeValue').textContent = String(size);
  canvas.isDrawingMode = !['rect','anchor'].includes(maskDrawMode);
  canvas.selection = false;
  canvas.defaultCursor = maskDrawMode === 'rect' ? 'crosshair' : (maskDrawMode === 'anchor' ? 'copy' : 'cell');
  if (canvas.isDrawingMode) {
    canvas.freeDrawingBrush = new fabric.PencilBrush(canvas);
    canvas.freeDrawingBrush.width = size;
    canvas.freeDrawingBrush.color = maskDrawMode === 'erase'
      ? 'rgba(34,197,94,0.78)'
      : (maskDrawMode === 'occlusion' ? 'rgba(59,130,246,0.68)' : 'rgba(239,68,68,0.62)');
  }
}

function setMaskMode(enabled) {
  if (enabled) {
    canvas.selection = false;
    canvas.discardActiveObject();
    canvas.getObjects().forEach(o => {
      if (o.isMaskOverlay) return;
      if (o.selectable !== false) o.__lockedByMask = true;
      o.selectable = false;
    });
    maskLockedObjects = true;
    configureMaskBrush();
    updateMaskInfo();
  } else {
    canvas.isDrawingMode = false;
    if (maskLockedObjects) {
      canvas.getObjects().forEach(o => {
        if (o.__lockedByMask) { o.selectable = true; delete o.__lockedByMask; }
      });
      canvas.defaultCursor = 'default';
      maskLockedObjects = false;
    }
  }
}

function appendChatMessage(role, text) {
  const log = $('aiChatLog');
  if (!log) return;
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function canvasChatContext() {
  const target = selectedLayerObject();
  const visibleLayers = canvas.getObjects().filter(o => !o.excludeFromLayers && !o.isMaskOverlay);
  const editCount = positiveEditMaskOverlays().length;
  const occCount = occlusionMaskOverlays().length;
  return {
    canvas: { width: canvas.width, height: canvas.height, background: canvas.backgroundColor || 'transparent' },
    selectedLayer: target ? { id: layerKey(target), name: nameOf(target), type: target.isDrawingLayer ? 'drawing' : target.type, visible: target.visible !== false, locked: !!target.locked } : null,
    layerCount: visibleLayers.length,
    layers: visibleLayers.map(o => ({ id: layerKey(o), name: nameOf(o), type: o.isDrawingLayer ? 'drawing' : o.type, visible: o.visible !== false })).slice(0, 20),
    mask: { count: editCount + occCount, editCount, occlusionCount: occCount },
  };
}

function refreshAiChatState() {
  const state = $('aiChatState');
  if (!state) return;
  const ctx = canvasChatContext();
  const selected = ctx.selectedLayer ? `${ctx.selectedLayer.name} / ${ctx.selectedLayer.type}` : '선택 없음';
  state.textContent = `선택: ${selected} · 레이어 ${ctx.layerCount} · 마스크 ${ctx.mask.count}`;
}

function showChatAction(action) {
  pendingChatAction = action;
  const panel = $('aiChatAction');
  const text = $('aiChatActionText');
  if (!panel || !text) return;
  if (!action || action.type === 'explain') {
    panel.classList.add('hidden');
    return;
  }
  text.textContent = `${action.title || action.type}\n${JSON.stringify(action.params || {})}`;
  panel.classList.remove('hidden');
  if (!action.requires_confirm) executeChatAction(action);
}

async function sendAiChat() {
  const input = $('aiChatInput');
  const message = (input?.value || '').trim();
  if (!message) return;
  appendChatMessage('user', message);
  input.value = '';
  pendingChatAction = null;
  $('aiChatAction')?.classList.add('hidden');
  if ($('sendAiChat')) $('sendAiChat').disabled = true;
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, context: canvasChatContext() }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || 'chat failed');
    appendChatMessage('assistant', data.reply || '명령을 해석했습니다.');
    showChatAction(data.action);
  } catch (err) {
    appendChatMessage('assistant', `AI Chat 오류: ${err.message}`);
  } finally {
    if ($('sendAiChat')) $('sendAiChat').disabled = false;
    refreshAiChatState();
  }
}

async function executeChatAction(action = pendingChatAction) {
  if (!action) return;
  const params = action.params || {};
  const done = (msg) => {
    appendChatMessage('assistant', msg);
    $('aiChatAction')?.classList.add('hidden');
    pendingChatAction = null;
    refreshAiChatState();
  };
  switch (action.type) {
    case 'plan': {
      const actions = params.actions || [];
      appendChatMessage('assistant', `계획 실행 시작: ${actions.length}단계`);
      for (const step of actions) await executeChatAction({ ...step, requires_confirm: false });
      done('계획 실행 요청을 완료했습니다. 비동기 작업은 상태 메시지에서 진행을 확인하세요.');
      break;
    }
    case 'state_summary':
      done(`상태 요약: ${$('aiChatState')?.textContent || '상태 정보 없음'}`);
      break;
    case 'transparent_canvas':
      $('transparentBg')?.click();
      done('실행됨: 캔버스 배경을 투명으로 변경했습니다.');
      break;
    case 'toggle_checker':
      $('toggleChecker')?.click();
      done('실행됨: 체커보드를 토글했습니다.');
      break;
    case 'remove_bg':
      await removeBgSelected(params.mode || 'ai');
      done(`실행됨: ${params.mode === 'sheet' ? '에셋 시트' : 'AI'} 배경 제거 요청을 완료했습니다.`);
      break;
    case 'activate_mask':
      activateTool('mask');
      done('실행됨: 마스크 도구로 전환했습니다.');
      break;
    case 'activate_text':
      activateTool('text');
      done('실행됨: 텍스트 도구로 전환했습니다.');
      break;
    case 'select_image_needed':
      activateTool(params.tool || 'select');
      done('안내: 이미지 레이어를 선택한 뒤 다시 명령하세요. 선택 도구로 전환했습니다.');
      break;
    case 'prepare_inpaint':
      if ($('inpaintPrompt')) $('inpaintPrompt').value = params.prompt || '';
      document.querySelector('details')?.setAttribute('open', '');
      done('준비됨: 직접 재생성 프롬프트를 입력했습니다. 실행 버튼으로 생성하세요.');
      break;
    case 'prepare_generate':
      activateTool('ai');
      if ($('aiPrompt')) $('aiPrompt').value = params.prompt || '';
      done('준비됨: AI 생성 프롬프트를 입력했습니다. 에셋 생성 버튼으로 실행하세요.');
      break;
    case 'export_png':
      exportFull();
      done('실행됨: PNG 내보내기를 시작했습니다.');
      break;
    default:
      done('이 명령은 아직 실행 액션이 없습니다.');
  }
}

function clearAiChat() {
  if ($('aiChatLog')) $('aiChatLog').innerHTML = '<div class="chat-msg assistant">로그를 지웠습니다. 새 편집 명령을 입력하세요.</div>';
  $('aiChatAction')?.classList.add('hidden');
  pendingChatAction = null;
}

function activateTool(tool) {
  currentTool = tool;
  document.querySelectorAll('.tool-button').forEach(b => b.classList.toggle('active', b.dataset.tool === tool));
  document.querySelectorAll('.option-panel').forEach(p => p.classList.toggle('active', p.dataset.toolPanel === tool));
  const toolNames = { select:'선택', pan:'작업영역 이동', crop:'크롭', brush:'브러시', pencil:'펜슬', eraser:'지우개', mask:'마스크', text:'텍스트', shape:'도형', upload:'이미지 가져오기', ai:'AI' };
  $('toolModeLabel').textContent = `${toolNames[tool] || tool} 도구`;
  $('workspace').classList.toggle('pan-mode', tool === 'pan');
  canvas.getObjects().forEach(o => {
    if (o.__lockedByPan && tool !== 'pan') { o.selectable = true; delete o.__lockedByPan; }
  });
  if (['brush','pencil','eraser'].includes(tool)) { setMaskMode(false); setDrawingTool(tool); }
  else { setDrawingTool('select'); setMaskMode(tool === 'mask'); }
  if (tool === 'pan') {
    canvas.selection = false;
    canvas.discardActiveObject();
    canvas.getObjects().forEach(o => {
      if (o.selectable !== false) o.__lockedByPan = true;
      o.selectable = false;
    });
    canvas.defaultCursor = 'grab';
    canvas.renderAll();
  } else if (tool !== 'mask') {
    canvas.defaultCursor = 'default';
  }
  const notes = {
    select:'선택 모드. 레이어 선택/이동/리사이즈 가능.',
    pan:'작업영역 이동 모드. 캔버스 판을 자유롭게 드래그합니다.',
    crop:'크롭 모드. 현재는 자리만 잡혀 있으며 실제 크롭은 다음 단계에서 구현합니다.',
    brush:'브러시 모드. 현재 드로잉 레이어에 그립니다.',
    pencil:'펜슬 모드. 얇은 선으로 현재 드로잉 레이어에 그립니다.',
    eraser:'지우개 모드. 투명 지우개 스트로크를 만듭니다.',
    mask:'마스크 모드. 브러시/사각 선택으로 AI 수정 영역을 만듭니다.',
    text:'텍스트 모드. 문구를 추가하고 스타일을 조정합니다.',
    shape:'도형 모드. 기본 도형을 추가합니다.',
    upload:'이미지 가져오기 모드. 파일을 추가합니다.',
    ai:'AI 모드. 에셋 생성과 선택영역 수정을 시작합니다.'
  };
  setStatus(notes[tool] || `${tool} mode`);
}

for (const b of document.querySelectorAll('.tool-button')) {
  b.onclick = () => activateTool(b.dataset.tool);
}

$('presetSize').onchange = () => {
  if ($('presetSize').value === 'custom') return;
  const [w,h] = $('presetSize').value.split('x').map(Number);
  $('canvasW').value = w; $('canvasH').value = h;
};
$('applyCanvas').onclick = () => setCanvasSize(+$('canvasW').value, +$('canvasH').value);
$('fitCanvas').onclick = fitView;
$('zoomIn').onclick = () => setViewScale(viewScale + 0.1);
$('zoomOut').onclick = () => setViewScale(viewScale - 0.1);
$('workspace').addEventListener('wheel', (e) => {
  const shell = $('canvasShell');
  if (!shell.contains(e.target) && e.target !== $('workspace')) return;
  e.preventDefault();
  const step = e.deltaY < 0 ? 1.12 : 1 / 1.12;
  setViewScale(viewScale * step, e);
}, { passive: false });
$('canvasBg').oninput = () => { canvas.backgroundColor = $('canvasBg').value; canvas.renderAll(); saveHistory(); };
$('transparentBg').onclick = () => { canvas.backgroundColor = null; canvas.renderAll(); saveHistory(); document.getElementById('canvasShell').classList.add('checker'); };
$('whiteBg').onclick = () => { canvas.backgroundColor = '#ffffff'; $('canvasBg').value = '#ffffff'; canvas.renderAll(); saveHistory(); };
$('toggleChecker').onclick = () => document.getElementById('canvasShell').classList.toggle('checker');

$('topPhotoPickBtn').onclick = () => $('topPhotoInput').click();
$('selectPhotoPickBtn').onclick = () => $('topPhotoInput').click();
$('photoPickBtn').onclick = () => $('photoInput').click();
$('filePickBtn').onclick = () => $('uploadInput').click();
$('topPhotoInput').onchange = e => handleFiles([...e.target.files]);
$('photoInput').onchange = e => handleFiles([...e.target.files]);
$('uploadInput').onchange = e => handleFiles([...e.target.files]);
$('workspace').ondragover = e => { e.preventDefault(); };
$('workspace').ondrop = e => { e.preventDefault(); handleFiles([...e.dataTransfer.files]); };
$('workspace').addEventListener('mousedown', e => {
  if (currentTool !== 'pan' || e.button !== 0) return;
  e.preventDefault();
  isPanning = true;
  canvas.defaultCursor = 'grabbing';
  panStart = {
    x: e.clientX,
    y: e.clientY,
    offsetX: canvasPanOffset.x,
    offsetY: canvasPanOffset.y,
  };
});
window.addEventListener('mousemove', e => {
  if (!isPanning || !panStart) return;
  e.preventDefault();
  canvasPanOffset.x = panStart.offsetX + (e.clientX - panStart.x);
  canvasPanOffset.y = panStart.offsetY + (e.clientY - panStart.y);
  updateCanvasStageSize();
});
window.addEventListener('mouseup', () => {
  if (isPanning && currentTool === 'pan') canvas.defaultCursor = 'grab';
  isPanning = false;
  panStart = null;
});

$('addText').onclick = () => addToCanvas(new fabric.Textbox($('newText').value || 'Text', { left: 160, top: 160, width: 420, fontSize: 72, fontFamily: 'Inter, Arial', fill: '#111111' }), 'Text');
$('addTitle').onclick = () => addToCanvas(new fabric.Textbox('BIG TITLE', { left: 140, top: 140, width: 620, fontSize: 112, fontFamily: 'Inter, Arial', fontWeight: 800, fill: '#111111', stroke: '#ffffff', strokeWidth: 0 }), 'Title');
$('addRect').onclick = () => addToCanvas(new fabric.Rect({ left: 160, top: 160, width: 320, height: 200, fill: '#7c5cff', rx: 0, ry: 0 }), 'Rectangle');
$('addRoundRect').onclick = () => addToCanvas(new fabric.Rect({ left: 160, top: 160, width: 340, height: 210, fill: '#ffffff', stroke: '#111111', strokeWidth: 4, rx: 28, ry: 28 }), 'Round Rectangle');
$('addCircle').onclick = () => addToCanvas(new fabric.Circle({ left: 180, top: 180, radius: 110, fill: '#22c55e' }), 'Circle');
$('addLine').onclick = () => addToCanvas(new fabric.Line([120,120,460,120], { left: 160, top: 220, stroke: '#111111', strokeWidth: 8 }), 'Line');
$('addLayer').onclick = () => createDrawingLayer();
$('addImageLayer').onclick = addBlankImageLayer;
$('brushSize').oninput = () => { $('brushSizeValue').textContent = $('brushSize').value; if (['brush','pencil'].includes(currentTool)) setDrawingTool(currentTool); };
$('brushColor').oninput = () => { if (currentTool === 'brush') setDrawingTool('brush'); };
$('pencilColorMirror').oninput = () => { if (currentTool === 'pencil') setDrawingTool('pencil'); };
$('eraserSize').oninput = () => { $('eraserSizeValue').textContent = $('eraserSize').value; if (currentTool === 'eraser') setDrawingTool('eraser'); };

$('applyProps').onclick = () => {
  const obj = active(); if (!obj) return;
  const curW = obj.getScaledWidth(); const curH = obj.getScaledHeight();
  obj.set({ left:+$('propX').value || 0, top:+$('propY').value || 0, angle:+$('propRot').value || 0, opacity: Math.max(0, Math.min(1, +$('propOpacity').value || 0)) });
  if (+$('propW').value > 0) obj.scaleX *= (+$('propW').value / curW);
  if (+$('propH').value > 0) obj.scaleY *= (+$('propH').value / curH);
  canvas.renderAll(); saveHistory(); syncProps(); renderLayers();
};
$('applyStyle').onclick = () => {
  const obj = active(); if (!obj) return;
  if ('fill' in obj) obj.set('fill', $('fillColor').value);
  if ('stroke' in obj) obj.set('stroke', $('strokeColor').value);
  if (obj.type === 'textbox' || obj.type === 'i-text') {
    obj.set({ text: $('textContent').value || obj.text, fontSize:+$('fontSize').value || obj.fontSize, strokeWidth:+$('strokeWidth').value || 0 });
  }
  canvas.renderAll(); saveHistory(); syncProps(); renderLayers();
};
$('toggleBold').onclick = () => { const obj=active(); if(obj && (obj.type==='textbox'||obj.type==='i-text')) { obj.fontWeight = obj.fontWeight === 800 ? 400 : 800; canvas.renderAll(); saveHistory(); } };
$('deleteObj').onclick = () => { const obj=active(); if(obj){ canvas.remove(obj); canvas.discardActiveObject(); canvas.renderAll(); saveHistory(); syncProps(); renderLayers(); } };
$('duplicateObj').onclick = () => { const obj=active(); if(!obj)return; obj.clone(clone => { clone.set({ left: obj.left + 28, top: obj.top + 28, id: uid(obj.type), name: `${nameOf(obj)} copy` }); addToCanvas(clone, clone.name); }); };
$('bringFront').onclick = () => { const obj=active(); if(obj){ canvas.bringToFront(obj); canvas.renderAll(); saveHistory(); renderLayers(); } };
$('sendBack').onclick = () => { const obj=active(); if(obj){ canvas.sendToBack(obj); canvas.renderAll(); saveHistory(); renderLayers(); } };

$('tolerance').oninput = () => $('tolValue').textContent = $('tolerance').value;
$('removeBg').onclick = () => removeBgSelected('ai');
$('removeSheetBg').onclick = () => removeBgSelected('sheet');
$('removeWhite').onclick = () => removeColor([255,255,255]);
$('removeBlack').onclick = () => removeColor([0,0,0]);
$('resetImage').onclick = resetImage;
$('clearMask').onclick = clearMask;
$('invertMask').onclick = invertMask;
$('exportMask').onclick = exportMaskPng;
if ($('previewMask')) $('previewMask').onclick = exportMaskPng;
if ($('runInpaint')) $('runInpaint').onclick = runSelectedAreaAiEdit;
if ($('applyInpaintNewLayer')) $('applyInpaintNewLayer').onclick = applyPendingInpaintAsLayer;
if ($('applyInpaintReplace')) $('applyInpaintReplace').onclick = applyPendingInpaintAsReplacement;
if ($('retryInpaint')) $('retryInpaint').onclick = retryPendingInpaint;
if ($('cancelInpaint')) $('cancelInpaint').onclick = () => clearPendingInpaintResult();
setInpaintBusy(false);
if ($('generateReplacement')) $('generateReplacement').onclick = generateReplacementObject;
if ($('sendAiChat')) $('sendAiChat').onclick = sendAiChat;
if ($('clearAiChat')) $('clearAiChat').onclick = clearAiChat;
if ($('confirmAiChatAction')) $('confirmAiChatAction').onclick = () => executeChatAction();
if ($('cancelAiChatAction')) $('cancelAiChatAction').onclick = () => { pendingChatAction = null; $('aiChatAction')?.classList.add('hidden'); appendChatMessage('assistant', '실행을 취소했습니다.'); };
if ($('aiChatInput')) $('aiChatInput').addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') sendAiChat();
});
refreshAiChatState();
$('maskMode').onchange = () => { configureMaskBrush(); setStatus(`Mask ${$('maskMode').value} mode.`); };
$('maskSize').oninput = configureMaskBrush;
$('exportPng').onclick = exportFull; $('exportPng2').onclick = exportFull; $('exportSelected').onclick = exportSelectedOnly;
$('undoBtn').onclick = () => loadHistory(historyIndex - 1);
$('redoBtn').onclick = () => loadHistory(historyIndex + 1);

$('saveProject').onclick = () => {
  const blob = new Blob([JSON.stringify(canvas.toDatalessJSON(['id','name','_originalSrc','_phase4PreservedOriginal','excludeFromLayers','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId']), null, 2)], {type:'application/json'});
  const a = document.createElement('a'); a.download = 'asset-studio-project.json'; a.href = URL.createObjectURL(blob); a.click(); URL.revokeObjectURL(a.href);
};
$('loadProjectBtn').onclick = () => $('loadProject').click();
$('loadProject').onchange = e => {
  const f = e.target.files[0]; if(!f) return;
  const r = new FileReader();
  r.onload = () => { suppressHistory = true; canvas.loadFromJSON(JSON.parse(r.result), () => { canvas.renderAll(); suppressHistory=false; ensureDefaultDrawingLayer(); refreshMaskStateFromCanvas(); saveHistory(); syncProps(); renderLayers(); }); };
  r.readAsText(f);
};

$('generateBtn').onclick = async () => {
  const prompt = $('aiPrompt').value.trim();
  if (!prompt) { alert('프롬프트를 입력하세요.'); return; }
  $('generateBtn').disabled = true; setStatus('AI 에셋 생성 중... 30~90초 정도 걸릴 수 있습니다.');
  try {
    const res = await fetch('/api/generate', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ prompt, preset:$('aiPreset').value, aspect_ratio:$('aiAspect').value }) });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'generation failed');
    const url = data.url + '?t=' + Date.now();
    addGallery(url, data.model || 'generated');
    addImageUrl(url, 'AI 생성 에셋');
    setStatus(`AI generated: ${data.model || ''}`);
  } catch (err) { setStatus('AI generation failed: ' + err.message); }
  finally { $('generateBtn').disabled = false; }
};

canvas.on('selection:created', () => { rememberSelectedLayer(active()); syncProps(); renderLayers(); refreshAiChatState(); });
canvas.on('selection:updated', () => { rememberSelectedLayer(active()); syncProps(); renderLayers(); refreshAiChatState(); });
canvas.on('selection:cleared', () => { syncProps(); renderLayers(); refreshAiChatState(); });
canvas.on('mouse:down', (opt) => {
  if (currentTool !== 'mask') return;
  if (maskDrawMode === 'anchor') {
    const p = canvas.getPointer(opt.e);
    setGripAnchorAt(p.x, p.y);
    return;
  }
  if (maskDrawMode !== 'rect') return;
  const p = canvas.getPointer(opt.e);
  isMaskDragging = true;
  maskStart = { x: clamp(p.x, 0, canvas.width), y: clamp(p.y, 0, canvas.height) };
  maskPreview = new fabric.Rect({ left: maskStart.x, top: maskStart.y, width: 1, height: 1, fill: 'rgba(239,68,68,0.22)', stroke: '#ff3b3b', strokeWidth: 2, strokeDashArray: [8, 5], selectable: false, evented: false, excludeFromLayers: true, excludeFromExport: true, objectCaching: false });
  maskPreview.isMaskOverlay = true;
  maskPreview.maskRole = 'preview';
  maskPreview.name = '마스크 미리보기';
  canvas.add(maskPreview);
  canvas.bringToFront(maskPreview);
});
canvas.on('mouse:move', (opt) => {
  if (currentTool !== 'mask' || maskDrawMode !== 'rect' || !isMaskDragging || !maskPreview || !maskStart) return;
  const p = canvas.getPointer(opt.e);
  const x = clamp(p.x, 0, canvas.width);
  const y = clamp(p.y, 0, canvas.height);
  maskPreview.set({ left: Math.min(maskStart.x, x), top: Math.min(maskStart.y, y), width: Math.abs(x - maskStart.x), height: Math.abs(y - maskStart.y) });
  maskPreview.setCoords();
  canvas.renderAll();
});
canvas.on('mouse:up', () => {
  if (currentTool !== 'mask' || maskDrawMode !== 'rect' || !isMaskDragging) return;
  isMaskDragging = false;
  if (maskPreview) {
    const r = { left: maskPreview.left || 0, top: maskPreview.top || 0, width: maskPreview.width || 0, height: maskPreview.height || 0 };
    canvas.remove(maskPreview);
    maskPreview = null;
    addMaskRect(r.left, r.top, r.width, r.height);
  }
  maskStart = null;
});
canvas.on('path:created', (e) => {
  const path = e.path;
  if (currentTool === 'mask') {
    const role = maskDrawMode === 'erase' ? 'mask-eraser' : (maskDrawMode === 'occlusion' ? 'occlusion-mask' : 'selection-mask');
    addMaskPath(path, role);
    return;
  }
  ensureMeta(path, currentDrawTool === 'eraser' ? 'Eraser stroke' : (currentDrawTool === 'pencil' ? 'Pencil stroke' : 'Brush stroke'));
  path.isDrawingStroke = true;
  const drawLayer = getActiveDrawingLayer();
  path.layerId = drawLayer.layerId || drawLayer.id;
  path.visible = drawLayer.visible !== false;
  path.excludeFromLayers = true;
  if (currentDrawTool === 'eraser') {
    path.globalCompositeOperation = 'destination-out';
    path.stroke = 'rgba(0,0,0,1)';
    path.name = 'Eraser stroke';
  }
  path.selectable = false;
  path.evented = false;
  saveHistory();
  renderLayers();
  setStatus('Stroke added to drawing surface. 레이어 목록에는 개별 선을 쌓지 않습니다.');
});
canvas.on('object:modified', () => { saveHistory(); syncProps(); renderLayers(); refreshAiChatState(); });
canvas.on('object:added', () => { if (!suppressHistory) renderLayers(); updateEmptyCanvasHint(); refreshAiChatState(); });
canvas.on('object:removed', () => { if (!suppressHistory) renderLayers(); updateEmptyCanvasHint(); refreshAiChatState(); });

window.addEventListener('resize', fitView);
window.addEventListener('keydown', (e) => {
  const tag = document.activeElement?.tagName;
  if (['INPUT','TEXTAREA','SELECT'].includes(tag)) return;
  if (e.code === 'Space') { activateTool('pan'); e.preventDefault(); }
  if (e.key === 'Delete' || e.key === 'Backspace') { $('deleteObj').click(); e.preventDefault(); }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'd') { $('duplicateObj').click(); e.preventDefault(); }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.shiftKey ? loadHistory(historyIndex + 1) : loadHistory(historyIndex - 1); e.preventDefault(); }
});
window.addEventListener('keyup', (e) => {
  const tag = document.activeElement?.tagName;
  if (['INPUT','TEXTAREA','SELECT'].includes(tag)) return;
  if (e.code === 'Space' && currentTool === 'pan') activateTool('select');
});

// Seed gallery with simple in-browser SVG samples
function svgData(label, bg, fg) {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='512' height='512'><rect width='512' height='512' rx='64' fill='${bg}'/><circle cx='256' cy='220' r='110' fill='${fg}'/><text x='256' y='390' text-anchor='middle' font-family='Arial' font-size='48' font-weight='800' fill='white'>${label}</text></svg>`)}`;
}
addGallery(svgData('ICON','#7c5cff','#22c55e'), 'sample icon');
addGallery(svgData('CARD','#111827','#f59e0b'), 'sample card');
ensureDefaultDrawingLayer();
setupPanelResize();
updateMaskInfo();
updateEmptyCanvasHint();
saveHistory();
fitView();
activateTool('select');
setStatus('B안 오브젝트 치환 UI 적용됨. Mask로 영역을 잡고 새 오브젝트만 별도 레이어로 생성/배치하세요.');
