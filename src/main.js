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
let temporaryPanPreviousTool = null;
let activeDrawingLayerId = null;
let selectedLayerId = null;
let isCropDragging = false;
let cropStart = null;
let cropPreview = null;
let isMaskDragging = false;
let maskStart = null;
let maskPreview = null;
let maskRegions = [];
let maskLockedObjects = false;
let maskDrawMode = 'brush';
let regionSelectionMode = 'rect';
let isRegionSelecting = false;
let regionSelectionStart = null;
let regionSelectionPreview = null;
let replacementGripAnchor = null;
let pendingInpaintResult = null;
let pendingChatAction = null;
let regionClipboard = null;
let regionPasteCount = 0;
const $ = (id) => document.getElementById(id);
const appEl = document.querySelector('.app');
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
const SERIALIZED_PROPS = ['id','name','_originalSrc','_phase4PreservedOriginal','excludeFromLayers','excludeFromExport','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId'];

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

function historyJson() {
  const exportFlags = canvas.getObjects().map(o => ({ obj: o, id: o.id, excludeFromExport: o.excludeFromExport }));
  const flagsById = new Map(exportFlags.map(({ id, excludeFromExport }) => [id, excludeFromExport]));
  exportFlags.forEach(({ obj }) => { obj.excludeFromExport = false; });
  try {
    const json = canvas.toDatalessJSON(SERIALIZED_PROPS);
    (json.objects || []).forEach(o => {
      if (flagsById.has(o.id)) o.excludeFromExport = flagsById.get(o.id);
    });
    return JSON.stringify(json);
  } finally {
    exportFlags.forEach(({ obj, excludeFromExport }) => { obj.excludeFromExport = excludeFromExport; });
  }
}

function labelHistoryEntry(label = '') {
  const clean = String(label || '').trim();
  if (clean) return clean;
  const count = canvas.getObjects().filter(o => !o.excludeFromLayers).length;
  const obj = active();
  if (obj) return `${nameOf(obj)} 변경`;
  if (count <= 1) return '초기 상태';
  return `캔버스 변경 · 레이어 ${count}`;
}

function renderHistory() {
  const list = $('historyList');
  if (!list) return;
  list.innerHTML = '';
  if ($('historyCount')) $('historyCount').textContent = `${historyIndex + 1}/${history.length}`;
  if ($('undoBtn')) $('undoBtn').disabled = historyIndex <= 0;
  if ($('redoBtn')) $('redoBtn').disabled = historyIndex >= history.length - 1;
  history.forEach((entry, idx) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'history-item' + (idx === historyIndex ? ' active' : '');
    item.dataset.historyIndex = String(idx);
    const label = entry.label || `History ${idx + 1}`;
    const time = entry.at ? new Date(entry.at).toLocaleTimeString() : '';
    item.innerHTML = `<span class="history-index">${idx + 1}</span><span class="history-label">${label}</span><span class="history-time">${time}</span>`;
    item.onclick = () => jumpToHistory(idx);
    list.appendChild(item);
  });
}

function saveHistory(label = '') {
  if (suppressHistory) return;
  const json = historyJson();
  if (history[historyIndex]?.json === json) { renderHistory(); return; }
  history = history.slice(0, historyIndex + 1);
  history.push({ json, label: labelHistoryEntry(label), at: new Date().toISOString() });
  historyIndex = history.length - 1;
  if (history.length > 80) { history.shift(); historyIndex--; }
  renderLayers();
  renderHistory();
}

function loadHistory(idx) {
  if (idx < 0 || idx >= history.length) return;
  suppressHistory = true;
  canvas.loadFromJSON(history[idx].json, () => {
    canvas.renderAll();
    historyIndex = idx;
    suppressHistory = false;
    refreshMaskStateFromCanvas();
    syncProps();
    renderLayers();
    renderHistory();
    refreshAiChatState();
    setStatus(`History: ${history[idx].label || idx + 1}`);
  });
}

function jumpToHistory(idx) {
  loadHistory(idx);
}

function undoHistory() {
  loadHistory(historyIndex - 1);
}

function redoHistory() {
  loadHistory(historyIndex + 1);
}

function isEditableTextField(el = document.activeElement) {
  const tag = el?.tagName;
  const type = (el?.type || '').toLowerCase();
  return tag === 'TEXTAREA' || (tag === 'INPUT' && ['text','search','url','email','password','tel'].includes(type));
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
function rememberSelectedLayer(obj) {
  if (!obj || obj.isMaskOverlay || obj.excludeFromLayers) return;
  selectedLayerId = layerKey(obj);
}

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

function isLayerLocked(obj) {
  return !!obj?.locked;
}

function enforceLayerInteractivity(obj) {
  if (!obj || obj.excludeFromLayers || obj.isMaskOverlay) return;
  if (obj.isDrawingLayer) {
    obj.selectable = false;
    obj.evented = false;
    return;
  }
  obj.selectable = obj.visible !== false && !isLayerLocked(obj);
  obj.evented = obj.visible !== false && !isLayerLocked(obj);
}

function setLayerLocked(obj, locked) {
  if (!obj) return;
  obj.locked = !!locked;
  enforceLayerInteractivity(obj);
}

function toggleLayerVisibility(obj) {
  if (!obj) return;
  obj.visible = !obj.visible;
  if (obj.isDrawingLayer) applyDrawingLayerVisibility(obj);
  enforceLayerInteractivity(obj);
  if (obj.visible === false && active() === obj) canvas.discardActiveObject();
  canvas.renderAll();
  saveHistory(obj.visible === false ? 'Hide layer' : 'Show layer');
  renderLayers();
  refreshAiChatState();
  setStatus(`${nameOf(obj)} ${obj.visible === false ? '숨김' : '표시'} 처리됨.`);
}

function canSelectLayer(obj) {
  return !!obj && obj.visible !== false && !isLayerLocked(obj);
}

function htmlEscape(value) {
  return String(value ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
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

function positiveRegionSelectionOverlays() {
  return positiveEditMaskOverlays();
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
  if ($('layerOpacity')) $('layerOpacity').value = obj.opacity ?? 1;
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

function deleteLogicalLayer(obj) {
  if (!obj) return;
  if (isLayerLocked(obj)) { setStatus('레이어가 잠겨 있습니다. 삭제하려면 먼저 Unlock 하세요.'); return; }
  const members = layerMembers(obj);
  members.forEach(o => canvas.remove(o));
  if (activeDrawingLayerId === (obj.layerId || obj.id)) activeDrawingLayerId = null;
  selectedLayerId = null;
  if (!canvas.getObjects().some(o => o.isDrawingLayer)) ensureDefaultDrawingLayer();
  canvas.discardActiveObject();
  canvas.renderAll();
  saveHistory('Delete layer');
  syncProps();
  renderLayers();
  refreshAiChatState();
  setStatus(`${nameOf(obj)} 삭제됨.`);
}

function duplicateLogicalLayer(obj) {
  if (!obj) return;
  if (isLayerLocked(obj)) { setStatus('레이어가 잠겨 있습니다. 복제하려면 먼저 Unlock 하세요.'); return; }
  if (obj.isDrawingLayer) {
    const newLayer = createDrawingLayer(`${nameOf(obj)} copy`);
    const sourceId = obj.layerId || obj.id;
    const newId = newLayer.layerId || newLayer.id;
    const strokes = canvas.getObjects().filter(o => o.isDrawingStroke && o.layerId === sourceId);
    let pending = strokes.length;
    if (!pending) { saveHistory('Duplicate drawing layer'); renderLayers(); return; }
    strokes.forEach(stroke => stroke.clone((clone) => {
      ensureMeta(clone, stroke.name || 'Stroke copy');
      clone.id = uid('stroke');
      clone.layerId = newId;
      clone.parentLayerName = newLayer.name;
      clone.visible = newLayer.visible !== false;
      clone.excludeFromLayers = true;
      clone.isDrawingStroke = true;
      clone.selectable = false;
      clone.evented = false;
      canvas.add(clone);
      pending -= 1;
      if (pending === 0) { canvas.renderAll(); saveHistory('Duplicate drawing layer'); renderLayers(); }
    }, SERIALIZED_PROPS));
    return;
  }
  obj.clone((clone) => {
    ensureMeta(clone, `${nameOf(obj)} copy`);
    clone.id = uid(clone.type || 'layer');
    clone.name = `${nameOf(obj)} copy`;
    clone.set({ left: (obj.left || 0) + 24, top: (obj.top || 0) + 24 });
    clone.locked = false;
    enforceLayerInteractivity(clone);
    canvas.add(clone);
    canvas.setActiveObject(clone);
    rememberSelectedLayer(clone);
    canvas.renderAll();
    saveHistory('Duplicate layer');
    syncProps();
    renderLayers();
    refreshAiChatState();
    setStatus(`${nameOf(obj)} 복제됨.`);
  }, SERIALIZED_PROPS);
}

function selectedMergeableLayers() {
  const sel = active();
  if (!sel || sel.type !== 'activeSelection') return [];
  const selected = sel.getObjects().filter(o => o && !o.isDrawingLayer && !o.excludeFromLayers && !o.isMaskOverlay && o.visible !== false && !isLayerLocked(o));
  const order = canvas.getObjects();
  return selected.sort((a, b) => order.indexOf(a) - order.indexOf(b));
}

function toggleLayerPanelMultiSelect(obj) {
  if (!obj || obj.isDrawingLayer || !canSelectLayer(obj)) {
    setStatus(obj?.isDrawingLayer ? 'Drawing Layer는 병합 선택 대상에서 제외됩니다.' : '숨김/잠금 레이어는 다중 선택할 수 없습니다.');
    return;
  }
  const sel = active();
  const current = sel && sel.type === 'activeSelection' ? sel.getObjects() : (sel && sel !== obj ? [sel] : []);
  const next = current.includes(obj) ? current.filter(o => o !== obj) : [...current, obj];
  if (next.length <= 0) {
    canvas.discardActiveObject();
  } else if (next.length === 1) {
    canvas.setActiveObject(next[0]);
    rememberSelectedLayer(next[0]);
  } else {
    const ordered = next.sort((a, b) => canvas.getObjects().indexOf(a) - canvas.getObjects().indexOf(b));
    const multi = new fabric.ActiveSelection(ordered, { canvas });
    canvas.setActiveObject(multi);
    selectedLayerId = null;
  }
  canvas.renderAll();
  syncProps();
  renderLayers();
  setStatus(`병합 선택: ${Math.max(1, next.length)}개 레이어`);
}

function mergeSelectedLayers() {
  const layers = selectedMergeableLayers();
  if (layers.length < 2) {
    setStatus('Merge는 레이어 두 개 이상 선택되어야 실행됩니다. 레이어 패널에서 Shift/Cmd/Ctrl 클릭으로 여러 레이어를 선택하세요.');
    return;
  }
  const sel = new fabric.ActiveSelection(layers, { canvas });
  canvas.setActiveObject(sel);
  const group = sel.toGroup();
  const label = layers.map(nameOf).join(' + ');
  ensureMeta(group, label);
  group.name = label;
  group.locked = false;
  enforceLayerInteractivity(group);
  canvas.setActiveObject(group);
  rememberSelectedLayer(group);
  canvas.renderAll();
  saveHistory('Merge selected layers');
  syncProps();
  renderLayers();
  refreshAiChatState();
  setStatus(`${layers.length}개 선택 레이어를 병합했습니다.`);
}

function handleLayerAction(act, obj, item) {
  if (act === 'rename') { beginRenameLayer(item, obj); return; }
  if (act === 'up') { moveLogicalLayer(obj, 'up'); return; }
  if (act === 'down') { moveLogicalLayer(obj, 'down'); return; }
  if (act === 'vis') { toggleLayerVisibility(obj); return; }
  if (act === 'lock') {
    setLayerLocked(obj, !isLayerLocked(obj));
    canvas.discardActiveObject(); canvas.renderAll(); saveHistory(isLayerLocked(obj) ? 'Lock layer' : 'Unlock layer'); renderLayers(); refreshAiChatState(); return;
  }
  if (act === 'duplicate') { duplicateLogicalLayer(obj); return; }
  if (act === 'merge') { mergeSelectedLayers(); return; }
  if (act === 'delete') { deleteLogicalLayer(obj); return; }
}

function renderLayers() {
  const box = $('layers');
  box.innerHTML = '';
  const objs = [...canvas.getObjects()].filter(obj => !obj.excludeFromLayers).reverse();
  const a = active();
  objs.forEach((obj, idx) => {
    const item = document.createElement('div');
    const selectedObjects = a && a.type === 'activeSelection' ? a.getObjects() : [];
    const isSelected = obj === a || selectedObjects.includes(obj) || (!a && layerKey(obj) === selectedLayerId);
    item.className = 'layer-item' + (isSelected ? ' active' : '') + (obj.visible === false ? ' is-hidden' : '') + (isLayerLocked(obj) ? ' is-locked' : '');
    const icon = obj.visible === false ? '🙈' : (obj.isDrawingLayer ? '✎' : '👁');
    const visibilityIcon = obj.visible === false ? '👁️‍🗨️' : '👁️';
    const visibilityLabel = obj.visible === false ? 'Show layer' : 'Hide layer';
    const visibilityTitle = visibilityLabel;
    const lockLabel = isLayerLocked(obj) ? 'Unlock' : 'Lock';
    const lockTitle = isLayerLocked(obj) ? 'Unlock layer' : 'Lock layer';
    const stateBadges = `${obj.visible === false ? '<span class="layer-badge">Hidden</span>' : ''}${isLayerLocked(obj) ? '<span class="layer-badge">Locked</span>' : ''}`;
    item.innerHTML = `<div class="layer-main-row"><span class="layer-icon">${icon}</span><span class="layer-name" title="Double-click to rename">${htmlEscape(nameOf(obj))}</span><span class="layer-state-badges">${stateBadges}</span></div><div class="layer-action-row"><button data-act="rename" draggable="false" title="Rename layer" aria-label="Rename layer">✎</button><button data-act="up" draggable="false" title="Move layer up" aria-label="Move layer up">↑</button><button data-act="down" draggable="false" title="Move layer down" aria-label="Move layer down">↓</button><button data-act="vis" draggable="false" title="${visibilityTitle}" aria-label="${visibilityTitle}" aria-pressed="${obj.visible !== false}">${visibilityIcon}</button><button data-act="lock" draggable="false" title="${lockTitle}" aria-label="${lockTitle}">${lockLabel}</button><button data-act="duplicate" draggable="false" title="Duplicate layer" aria-label="Duplicate layer">Dup</button><button data-act="merge" draggable="false" title="Merge selected layers" aria-label="Merge selected layers">Merge</button><button data-act="delete" draggable="false" title="Delete layer" aria-label="Delete layer">Del</button></div>`;
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
    item.querySelectorAll('button[data-act]').forEach(btn => {
      btn.addEventListener('pointerdown', (e) => e.stopPropagation());
      btn.addEventListener('mousedown', (e) => e.stopPropagation());
      btn.addEventListener('dragstart', (e) => e.preventDefault());
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const act = btn.dataset.act;
        handleLayerAction(act, obj, item);
      });
    });
    item.onclick = (e) => {
      if (e.shiftKey || e.metaKey || e.ctrlKey) {
        toggleLayerPanelMultiSelect(obj);
        return;
      }
      if (!canSelectLayer(obj)) {
        setStatus(obj.visible === false ? '레이어가 숨김 상태입니다. Show 후 선택하세요.' : '레이어가 잠겨 있습니다. Unlock 후 편집하세요.');
        canvas.discardActiveObject();
        canvas.renderAll();
        renderLayers();
        return;
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

function zoomBy(delta, anchorEvent = null) {
  setViewScale(viewScale * delta, anchorEvent);
}

function beginWorkspacePan(e) {
  if (e.button !== 0 && e.button !== 1) return false;
  e.preventDefault();
  isPanning = true;
  $('workspace')?.classList.add('is-panning');
  canvas.defaultCursor = 'grabbing';
  panStart = {
    x: e.clientX,
    y: e.clientY,
    offsetX: canvasPanOffset.x,
    offsetY: canvasPanOffset.y,
  };
  return true;
}

function updateWorkspacePan(e) {
  if (!isPanning || !panStart) return;
  e.preventDefault();
  canvasPanOffset.x = panStart.offsetX + (e.clientX - panStart.x);
  canvasPanOffset.y = panStart.offsetY + (e.clientY - panStart.y);
  updateCanvasStageSize();
}

function endWorkspacePan() {
  if (isPanning && currentTool === 'pan') canvas.defaultCursor = 'grab';
  $('workspace')?.classList.remove('is-panning');
  isPanning = false;
  panStart = null;
}

function startTemporaryPan() {
  if (temporaryPanPreviousTool || currentTool === 'pan') return;
  temporaryPanPreviousTool = currentTool;
  activateTool('pan');
  setStatus('임시 Pan: Space를 놓으면 이전 도구로 돌아갑니다.');
}

function endTemporaryPan() {
  if (!temporaryPanPreviousTool) return;
  const tool = temporaryPanPreviousTool;
  temporaryPanPreviousTool = null;
  activateTool(tool);
}

function toggleDrawingTool() {
  activateTool(currentTool === 'brush' ? 'pencil' : 'brush');
}

function toggleShapeTool() {
  activateTool('shape');
  const shapeOrder = ['addRect', 'addCircle', 'addLine', 'addRoundRect'];
  const current = localStorage.getItem('assetStudio.lastShapeButton') || 'addRect';
  const nextId = shapeOrder[(shapeOrder.indexOf(current) + 1) % shapeOrder.length] || 'addRect';
  localStorage.setItem('assetStudio.lastShapeButton', nextId);
  setStatus(`도형 도구: R을 다시 누르면 다음 기본 도형으로 전환됩니다. 현재 빠른 도형 ${nextId}.`);
}

function handleToolShortcut(e) {
  if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return false;
  if (isEditableTextField() || ['SELECT'].includes(document.activeElement?.tagName)) return false;
  const key = e.key.toLowerCase();
  switch (key) {
    case 'a': activateTool('region'); break;
    case 'v': activateTool('select'); break;
    case 'c': activateTool('crop'); break;
    case 'e': activateTool('eraser'); break;
    case 'm': activateTool('mask'); break;
    case 't': activateTool('text'); break;
    case 'b': toggleDrawingTool(); break;
    case 'r': toggleShapeTool(); break;
    default: return false;
  }
  e.preventDefault();
  return true;
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

function cropValues() {
  const x = clamp(Math.round(+$('cropX')?.value || 0), 0, canvas.width - 1);
  const y = clamp(Math.round(+$('cropY')?.value || 0), 0, canvas.height - 1);
  const w = clamp(Math.round(+$('cropW')?.value || canvas.width), 1, canvas.width - x);
  const h = clamp(Math.round(+$('cropH')?.value || canvas.height), 1, canvas.height - y);
  return { x, y, w, h };
}

function setCropInputs(x, y, w, h) {
  const cx = clamp(Math.round(x), 0, canvas.width - 1);
  const cy = clamp(Math.round(y), 0, canvas.height - 1);
  const cw = clamp(Math.round(w), 1, canvas.width - cx);
  const ch = clamp(Math.round(h), 1, canvas.height - cy);
  $('cropX').value = cx;
  $('cropY').value = cy;
  $('cropW').value = cw;
  $('cropH').value = ch;
  return { x: cx, y: cy, w: cw, h: ch };
}

function clearCropPreview() {
  if (cropPreview) canvas.remove(cropPreview);
  cropPreview = null;
  cropStart = null;
  isCropDragging = false;
  canvas.renderAll();
}

function beginCropSelection(opt) {
  const p = canvas.getPointer(opt.e);
  clearCropPreview();
  isCropDragging = true;
  cropStart = { x: clamp(p.x, 0, canvas.width), y: clamp(p.y, 0, canvas.height) };
  cropPreview = new fabric.Rect({
    left: cropStart.x,
    top: cropStart.y,
    width: 1,
    height: 1,
    fill: 'rgba(250,204,21,0.16)',
    stroke: '#facc15',
    strokeWidth: 2,
    strokeDashArray: [10, 6],
    selectable: false,
    evented: false,
    excludeFromLayers: true,
    excludeFromExport: true,
    objectCaching: false,
  });
  cropPreview.name = '크롭 선택영역';
  cropPreview.isCropPreview = true;
  canvas.add(cropPreview);
  canvas.bringToFront(cropPreview);
  canvas.renderAll();
}

function updateCropSelection(opt) {
  if (!isCropDragging || !cropPreview || !cropStart) return;
  const p = canvas.getPointer(opt.e);
  const x = clamp(p.x, 0, canvas.width);
  const y = clamp(p.y, 0, canvas.height);
  const left = Math.min(cropStart.x, x);
  const top = Math.min(cropStart.y, y);
  const width = Math.abs(x - cropStart.x);
  const height = Math.abs(y - cropStart.y);
  cropPreview.set({ left, top, width, height });
  cropPreview.setCoords();
  setCropInputs(left, top, Math.max(1, width), Math.max(1, height));
  canvas.renderAll();
}

function finishCropSelection() {
  if (!isCropDragging) return;
  isCropDragging = false;
  if (cropPreview) {
    const r = {
      left: cropPreview.left || 0,
      top: cropPreview.top || 0,
      width: (cropPreview.width || 0) * (cropPreview.scaleX || 1),
      height: (cropPreview.height || 0) * (cropPreview.scaleY || 1),
    };
    if (r.width < 4 || r.height < 4) clearCropPreview();
    else {
      setCropInputs(r.left, r.top, r.width, r.height);
      setStatus(`크롭 영역 선택: ${Math.round(r.width)}×${Math.round(r.height)}. 캔버스 크롭 또는 선택 이미지 크롭을 누르세요.`);
    }
  }
  cropStart = null;
}

function applyCanvasCrop() {
  const { x, y, w, h } = cropValues();
  clearCropPreview();
  canvas.getObjects().forEach(o => {
    if (typeof o.left === 'number') o.left -= x;
    if (typeof o.top === 'number') o.top -= y;
    if (o.isDrawingLayer) o.set({ width: w, height: h });
    o.setCoords?.();
  });
  setCanvasSize(w, h);
  $('canvasW').value = w; $('canvasH').value = h;
  $('cropX').value = 0; $('cropY').value = 0; $('cropW').value = w; $('cropH').value = h;
  canvas.renderAll();
  saveHistory('Canvas crop');
  syncProps(); renderLayers(); fitView();
  setStatus(`캔버스를 ${w}×${h}로 크롭했습니다.`);
}

function cropSelectedImage() {
  const obj = selectedLayerObject();
  if (!obj || obj.type !== 'image') { alert('이미지 레이어를 선택하세요.'); return; }
  const { x, y, w, h } = cropValues();
  clearCropPreview();
  const states = canvas.getObjects().map(o => ({ obj: o, visible: o.visible }));
  const bg = canvas.backgroundColor;
  canvas.getObjects().forEach(o => { o.visible = o === obj; });
  canvas.backgroundColor = null;
  canvas.discardActiveObject();
  canvas.renderAll();
  const url = canvas.toDataURL({ format: 'png', left: x, top: y, width: w, height: h, multiplier: 1 });
  states.forEach(s => { s.obj.visible = s.visible; });
  canvas.backgroundColor = bg;
  fabric.Image.fromURL(url, (img) => {
    img.set({ left: x, top: y, originX: 'left', originY: 'top', opacity: obj.opacity ?? 1 });
    img._originalSrc = obj._originalSrc || obj.getSrc();
    ensureMeta(img, `${nameOf(obj)} crop`);
    const idx = canvas.getObjects().indexOf(obj);
    canvas.remove(obj);
    canvas.insertAt(img, Math.max(0, idx), false);
    canvas.setActiveObject(img); rememberSelectedLayer(img);
    canvas.renderAll();
    saveHistory('Selected image crop');
    syncProps(); renderLayers();
    setStatus('선택 이미지 크롭을 새 투명 이미지 레이어로 적용했습니다.');
  }, { crossOrigin: 'anonymous' });
}

function resizeCanvasFitObjects() {
  const objs = canvas.getObjects().filter(o => !o.excludeFromExport && !o.isMaskOverlay);
  if (!objs.length) return;
  let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
  objs.forEach(o => {
    const r = o.getBoundingRect(true, true);
    left = Math.min(left, r.left); top = Math.min(top, r.top);
    right = Math.max(right, r.left + r.width); bottom = Math.max(bottom, r.top + r.height);
  });
  const pad = 8;
  left = Math.floor(left - pad); top = Math.floor(top - pad);
  right = Math.ceil(right + pad); bottom = Math.ceil(bottom + pad);
  $('cropX').value = Math.max(0, left); $('cropY').value = Math.max(0, top);
  $('cropW').value = clamp(right - Math.max(0, left), 1, canvas.width);
  $('cropH').value = clamp(bottom - Math.max(0, top), 1, canvas.height);
  applyCanvasCrop();
}

async function selectedImageAsFullCanvasDataUrl(obj) {
  const states = canvas.getObjects().map(o => ({ obj: o, visible: o.visible }));
  const bg = canvas.backgroundColor;
  canvas.getObjects().forEach(o => { o.visible = o === obj; });
  obj.visible = true;
  canvas.backgroundColor = null;
  canvas.discardActiveObject();
  canvas.renderAll();
  const url = canvas.toDataURL({ format: 'png', multiplier: 1 });
  states.forEach(s => { s.obj.visible = s.visible; });
  canvas.backgroundColor = bg;
  canvas.renderAll();
  return url;
}

function maskImageToAlphaCanvas(maskImg, width, height, drawFn = null) {
  const alpha = document.createElement('canvas');
  alpha.width = width;
  alpha.height = height;
  const actx = alpha.getContext('2d');
  actx.imageSmoothingEnabled = false;
  if (drawFn) drawFn(actx, maskImg);
  else actx.drawImage(maskImg, 0, 0, width, height);
  const data = actx.getImageData(0, 0, width, height);
  for (let i = 0; i < data.data.length; i += 4) {
    const lum = Math.max(data.data[i], data.data[i + 1], data.data[i + 2]);
    data.data[i] = 255;
    data.data[i + 1] = 255;
    data.data[i + 2] = 255;
    data.data[i + 3] = lum;
  }
  actx.putImageData(data, 0, 0);
  return alpha;
}

async function selectedRegionAsFullCanvasDataUrl(target, maskDataUrl) {
  const [sourceImg, maskImg] = await Promise.all([
    loadImageForCanvas(await selectedImageAsFullCanvasDataUrl(target)),
    loadImageForCanvas(maskDataUrl),
  ]);
  const out = document.createElement('canvas');
  out.width = canvas.width;
  out.height = canvas.height;
  const ctx = out.getContext('2d');
  ctx.clearRect(0, 0, out.width, out.height);
  ctx.drawImage(sourceImg, 0, 0, out.width, out.height);
  const alphaMask = maskImageToAlphaCanvas(maskImg, out.width, out.height);
  ctx.globalCompositeOperation = 'destination-in';
  ctx.drawImage(alphaMask, 0, 0, out.width, out.height);
  ctx.globalCompositeOperation = 'source-over';
  return out.toDataURL('image/png');
}

async function eraseSelectedImageOnCanvasWithMask(obj, maskDataUrl, historyLabel = 'Cut selected region') {
  if (!obj || obj.type !== 'image') return false;
  if (!obj._originalSrc) obj._originalSrc = obj.getSrc();
  const [sourceImg, maskImg] = await Promise.all([
    loadImageForCanvas(await selectedImageAsFullCanvasDataUrl(obj)),
    loadImageForCanvas(maskDataUrl),
  ]);
  const out = document.createElement('canvas');
  out.width = canvas.width;
  out.height = canvas.height;
  const ctx = out.getContext('2d');
  ctx.clearRect(0, 0, out.width, out.height);
  ctx.drawImage(sourceImg, 0, 0, out.width, out.height);
  const alphaMask = maskImageToAlphaCanvas(maskImg, out.width, out.height);
  ctx.globalCompositeOperation = 'destination-out';
  ctx.drawImage(alphaMask, 0, 0, out.width, out.height);
  ctx.globalCompositeOperation = 'source-over';
  await replaceImageWithCroppedCanvasLayer(obj, out.toDataURL('image/png'), `${nameOf(obj)} cut`, historyLabel);
  setStatus('선택영역 cut: 캔버스 좌표 기준으로 원본 이미지의 해당 영역만 투명 처리했습니다.');
  return true;
}

function regionBoundsFromMaskOverlays() {
  const overlays = positiveEditMaskOverlays();
  if (!overlays.length) return null;
  const rects = overlays.map(o => o.getBoundingRect(true, true));
  const left = clamp(Math.floor(Math.min(...rects.map(r => r.left))), 0, canvas.width - 1);
  const top = clamp(Math.floor(Math.min(...rects.map(r => r.top))), 0, canvas.height - 1);
  const right = clamp(Math.ceil(Math.max(...rects.map(r => r.left + r.width))), left + 1, canvas.width);
  const bottom = clamp(Math.ceil(Math.max(...rects.map(r => r.top + r.height))), top + 1, canvas.height);
  const width = Math.max(1, right - left);
  const height = Math.max(1, bottom - top);
  return { x: left, y: top, left, top, width, height };
}

async function putSelectedRegionOnClipboard({ cut = false } = {}) {
  const target = selectedLayerObject();
  if (!target || target.type !== 'image' || target.isDrawingLayer || target.excludeFromLayers) {
    alert('먼저 부분 복사/잘라내기 할 이미지 레이어를 선택하세요.');
    return null;
  }
  const maskDataUrl = await buildMaskDataUrl('edit');
  const regionBounds = regionBoundsFromMaskOverlays();
  if (!maskDataUrl || !regionBounds) {
    alert('먼저 영역 선택 도구에서 사각형/원형/올가미로 이미지 부분을 선택하세요.');
    return null;
  }
  const regionUrl = await selectedRegionAsFullCanvasDataUrl(target, maskDataUrl);
  const regionCroppedUrl = await cropCanvasDataUrlToBounds(regionUrl, regionBounds);
  regionClipboard = {
    kind: 'region-image',
    url: regionCroppedUrl,
    bounds: regionBounds,
    sourceLayerId: layerKey(target),
    sourceName: nameOf(target),
    cut,
  };
  regionPasteCount = 0;
  if (cut) await eraseSelectedImageOnCanvasWithMask(target, maskDataUrl, 'Cut selected region');
  clearRegionSelectionVisuals();
  setStatus(cut ? '선택영역을 잘라내서 내부 클립보드에 보관했습니다. Ctrl+V로 붙여넣으세요.' : '선택영역을 내부 클립보드에 복사했습니다. Ctrl+V로 붙여넣으세요.');
  return regionClipboard;
}

async function pasteRegionClipboard() {
  if (!regionClipboard || regionClipboard.kind !== 'region-image') {
    setStatus('붙여넣을 선택영역 클립보드가 없습니다.');
    return null;
  }
  const baseX = regionClipboard.bounds.x ?? regionClipboard.bounds.left;
  const baseY = regionClipboard.bounds.y ?? regionClipboard.bounds.top;
  const offset = regionPasteCount * 12;
  const pasteBounds = {
    ...regionClipboard.bounds,
    x: baseX + offset,
    y: baseY + offset,
    left: baseX + offset,
    top: baseY + offset,
  };
  const layer = await addPatchImageUrl(regionClipboard.url, pasteBounds, `${regionClipboard.sourceName || 'Image'} ${regionClipboard.cut ? '잘라낸 영역' : '복사 영역'}`);
  regionPasteCount += 1;
  setStatus('클립보드 선택영역을 새 이미지 레이어로 붙여넣었습니다.');
  return layer;
}

async function copySelectedRegionToLayer({ cut = false } = {}) {
  return putSelectedRegionOnClipboard({ cut });
}

function clippedObjectBounds(obj) {
  const rect = obj.getBoundingRect(true, true);
  const left = clamp(Math.floor(rect.left), 0, canvas.width);
  const top = clamp(Math.floor(rect.top), 0, canvas.height);
  const right = clamp(Math.ceil(rect.left + rect.width), 0, canvas.width);
  const bottom = clamp(Math.ceil(rect.top + rect.height), 0, canvas.height);
  return {
    left,
    top,
    width: Math.max(1, right - left),
    height: Math.max(1, bottom - top),
  };
}

async function cropCanvasDataUrlToBounds(url, bbox) {
  const sourceImg = await loadImageForCanvas(url);
  const crop = document.createElement('canvas');
  crop.width = bbox.width;
  crop.height = bbox.height;
  const cctx = crop.getContext('2d');
  cctx.drawImage(sourceImg, bbox.left, bbox.top, bbox.width, bbox.height, 0, 0, bbox.width, bbox.height);
  return crop.toDataURL('image/png');
}

async function replaceImageWithCroppedCanvasLayer(obj, url, label, historyLabel) {
  const bbox = clippedObjectBounds(obj);
  const croppedUrl = await cropCanvasDataUrlToBounds(url, bbox);
  return new Promise(resolve => fabric.Image.fromURL(croppedUrl, (img) => {
    img.set({ left: bbox.left, top: bbox.top, width: bbox.width, height: bbox.height, originX: 'left', originY: 'top', opacity: obj.opacity ?? 1 });
    img._originalSrc = obj._originalSrc || obj.getSrc();
    ensureMeta(img, label || nameOf(obj));
    const idx = canvas.getObjects().indexOf(obj);
    canvas.remove(obj);
    canvas.insertAt(img, Math.max(0, idx), false);
    canvas.setActiveObject(img); rememberSelectedLayer(img);
    canvas.renderAll();
    saveHistory(historyLabel);
    syncProps(); renderLayers();
    resolve(img);
  }, { crossOrigin: 'anonymous' }));
}

function imageElementSize(obj) {
  const el = obj.getElement?.();
  return {
    width: Math.max(1, Math.round(el?.naturalWidth || el?.videoWidth || obj.width || 1)),
    height: Math.max(1, Math.round(el?.naturalHeight || el?.videoHeight || obj.height || 1)),
  };
}

async function eraseImageAtNativeResolution(obj, maskDataUrl) {
  const currentImg = await loadImageForCanvas(obj.getSrc());
  const maskImg = await loadImageForCanvas(maskDataUrl);
  const native = imageElementSize(obj);
  const out = document.createElement('canvas');
  out.width = native.width;
  out.height = native.height;
  const octx = out.getContext('2d');
  octx.imageSmoothingEnabled = false;
  octx.drawImage(currentImg, 0, 0, native.width, native.height);

  const bbox = clippedObjectBounds(obj);
  const localMask = maskImageToAlphaCanvas(maskImg, native.width, native.height, (mctx, img) => {
    mctx.drawImage(img, bbox.left, bbox.top, bbox.width, bbox.height, 0, 0, native.width, native.height);
  });

  octx.globalCompositeOperation = 'destination-out';
  octx.drawImage(localMask, 0, 0);
  octx.globalCompositeOperation = 'source-over';
  return out.toDataURL('image/png');
}

function replaceImagePreservingTransform(obj, url, label, historyLabel) {
  return new Promise(resolve => fabric.Image.fromURL(url, (img) => {
    img.set({
      id: obj.id,
      name: label || nameOf(obj),
      left: obj.left,
      top: obj.top,
      originX: obj.originX,
      originY: obj.originY,
      scaleX: obj.scaleX,
      scaleY: obj.scaleY,
      angle: obj.angle,
      opacity: obj.opacity ?? 1,
      flipX: obj.flipX,
      flipY: obj.flipY,
      skewX: obj.skewX,
      skewY: obj.skewY,
      selectable: obj.selectable,
      evented: obj.evented,
    });
    img._originalSrc = obj._originalSrc || obj.getSrc();
    ensureMeta(img, label || nameOf(obj));
    const idx = canvas.getObjects().indexOf(obj);
    canvas.remove(obj);
    canvas.insertAt(img, Math.max(0, idx), false);
    canvas.setActiveObject(img); rememberSelectedLayer(img);
    canvas.renderAll();
    saveHistory(historyLabel);
    syncProps(); renderLayers();
    resolve(img);
  }, { crossOrigin: 'anonymous' }));
}

function showTransparentCanvasPreview() {
  canvas.backgroundColor = null;
  $('canvasShell')?.classList.add('checker');
}

async function eraseImageWithMaskDataUrl(obj, maskDataUrl, historyLabel = 'Alpha erase by mask') {
  if (!obj || obj.type !== 'image') return false;
  if (!obj._originalSrc) obj._originalSrc = obj.getSrc();
  const erasedUrl = await eraseImageAtNativeResolution(obj, maskDataUrl);
  await replaceImagePreservingTransform(obj, erasedUrl, `${nameOf(obj)} alpha erased`, historyLabel);
  setStatus('선택한 이미지 레이어에만 적용: 원본 해상도를 유지한 채 픽셀을 alpha=0 투명으로 지웠습니다.');
  return true;
}

function pathToMaskDataUrl(path) {
  const maskCanvas = new fabric.StaticCanvas(null, { width: canvas.width, height: canvas.height, backgroundColor: null });
  const maskPath = fabric.util.object.clone(path);
  maskPath.set({ stroke: '#ffffff', fill: null, opacity: 1, globalCompositeOperation: 'source-over', selectable: false, evented: false });
  maskCanvas.add(maskPath);
  maskCanvas.renderAll();
  const dataUrl = maskCanvas.toDataURL({ format: 'png', multiplier: 1 });
  maskCanvas.dispose();
  return dataUrl;
}

async function eraseSelectedByMask() {
  const obj = selectedLayerObject();
  if (!obj || obj.type !== 'image') { alert('이미지 레이어를 선택하세요.'); return; }
  const mask = await buildMaskDataUrl('edit');
  if (!mask) { alert('먼저 Mask로 지울 영역을 칠하세요.'); return; }
  await eraseImageWithMaskDataUrl(obj, mask, 'Alpha erase by mask');
}

async function restoreSelectedByMask() {
  const obj = selectedLayerObject();
  if (!obj || obj.type !== 'image') { alert('이미지 레이어를 선택하세요.'); return; }
  const mask = await buildMaskDataUrl('edit');
  if (!mask) { alert('먼저 Mask로 복원 영역을 칠하세요.'); return; }
  const originalSrc = obj._originalSrc;
  if (!originalSrc) { alert('복원할 원본 이미지가 없습니다.'); return; }
  const [currentImg, originalImg, maskImg] = await Promise.all([loadImageForCanvas(await selectedImageAsFullCanvasDataUrl(obj)), loadImageForCanvas(originalSrc), loadImageForCanvas(mask)]);
  const originalCanvas = document.createElement('canvas'); originalCanvas.width = canvas.width; originalCanvas.height = canvas.height;
  const octx = originalCanvas.getContext('2d');
  octx.save();
  octx.translate(obj.left || 0, obj.top || 0);
  octx.rotate((obj.angle || 0) * Math.PI / 180);
  octx.scale(obj.scaleX || 1, obj.scaleY || 1);
  octx.drawImage(originalImg, 0, 0);
  octx.restore();
  octx.globalCompositeOperation = 'destination-in';
  octx.drawImage(maskImg, 0, 0, canvas.width, canvas.height);
  octx.globalCompositeOperation = 'source-over';
  const tmp = document.createElement('canvas'); tmp.width = canvas.width; tmp.height = canvas.height;
  const ctx = tmp.getContext('2d');
  ctx.drawImage(currentImg, 0, 0, tmp.width, tmp.height);
  ctx.drawImage(originalCanvas, 0, 0);
  await replaceImageWithCroppedCanvasLayer(obj, tmp.toDataURL('image/png'), `${nameOf(obj)} restored`, 'Restore by mask');
  saveHistory('Restore by mask');
  setStatus('마스크 영역을 원본 픽셀로 복원했습니다.');
}

async function restoreSelectedOriginal() {
  const obj = selectedLayerObject();
  if (!obj || obj.type !== 'image' || !obj._originalSrc) { alert('원본이 있는 이미지 레이어를 선택하세요.'); return; }
  fabric.Image.fromURL(obj._originalSrc, (img) => {
    img.set({ id: obj.id, name: obj.name, left: obj.left, top: obj.top, scaleX: obj.scaleX, scaleY: obj.scaleY, angle: obj.angle, opacity: obj.opacity, originX: obj.originX, originY: obj.originY });
    img._originalSrc = obj._originalSrc;
    const idx = canvas.getObjects().indexOf(obj);
    canvas.remove(obj); canvas.insertAt(ensureMeta(img, obj.name), Math.max(0, idx), false);
    canvas.setActiveObject(img); rememberSelectedLayer(img);
    canvas.renderAll(); saveHistory('Restore original image'); syncProps(); renderLayers();
    setStatus('선택 이미지를 원본으로 복원했습니다.');
  }, { crossOrigin: 'anonymous' });
}

function applyLayerOpacity() {
  const obj = selectedLayerObject();
  if (!obj) return;
  obj.set('opacity', clamp(+$('layerOpacity').value || 0, 0, 1));
  canvas.renderAll(); saveHistory('Layer opacity'); syncProps(); renderLayers();
}

function groupSelection() {
  const sel = active();
  if (!sel || sel.type !== 'activeSelection') { alert('여러 레이어를 선택한 뒤 그룹을 누르세요.'); return; }
  const group = sel.toGroup();
  ensureMeta(group, 'Group');
  canvas.setActiveObject(group); rememberSelectedLayer(group);
  canvas.renderAll(); saveHistory('Group selection'); syncProps(); renderLayers();
}

function ungroupSelection() {
  const obj = active();
  if (!obj || obj.type !== 'group') { alert('그룹 레이어를 선택하세요.'); return; }
  obj.toActiveSelection();
  canvas.renderAll(); saveHistory('Ungroup selection'); syncProps(); renderLayers();
}

function exportActiveLayer() {
  const obj = selectedLayerObject();
  if (!obj) { alert('내보낼 레이어를 선택하세요.'); return; }
  canvas.setActiveObject(obj);
  exportSelectedOnly();
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
    const url = data.url.startsWith('data:') ? data.url : data.url + '?t=' + Date.now();
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
      canvas.setActiveObject(cutout);
      rememberSelectedLayer(cutout);
      canvas.renderAll();
      saveHistory(); syncProps(); renderLayers();
      addGallery(url, 'cutout');
      setStatus(`${mode === 'sheet' ? 'Asset Sheet BG' : 'AI Cutout'} complete (${data.method}). 선택한 이미지 레이어에만 적용했습니다. 원본은 숨김 처리했고 Cutout 레이어를 새로 만들었습니다.`);
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
  if ($('regionSelectionInfo')) $('regionSelectionInfo').textContent = `선택영역: ${editCount}`;
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
    fill: path.type === 'path' && role === 'selection-mask' ? 'rgba(239,68,68,0.18)' : null,
    stroke: isErase ? 'rgba(34,197,94,0.78)' : (isOcclusion ? 'rgba(59,130,246,0.68)' : 'rgba(239,68,68,0.62)'),
    strokeLineCap: 'round',
    strokeLineJoin: 'round',
    strokeDashArray: path.type === 'path' && role === 'selection-mask' ? [8, 5] : (isErase ? [6, 6] : null),
  });
  canvas.bringToFront(path);
  canvas.renderAll();
  saveHistory('Mask brush stroke');
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
  saveHistory('Mask rectangle');
  updateMaskInfo();
  setStatus(`교체 마스크 사각 추가: ${Math.round(w)}×${Math.round(h)}.`);
  return overlay;
}

function ensureRegionSelectionTarget() {
  const target = selectedLayerObject();
  if (!target || target.type !== 'image' || target.isDrawingLayer || target.excludeFromLayers) {
    const label = target ? `${nameOf(target)} (${target.isDrawingLayer ? 'drawing layer' : target.type})` : '선택 없음';
    setStatus(`부분 선택은 이미지 레이어에서만 가능합니다. 현재 선택: ${label}`);
    return null;
  }
  return target;
}

function addRegionEllipse(left, top, width, height) {
  const target = ensureRegionSelectionTarget();
  if (!target) return null;
  const x = Math.max(0, Math.min(left, left + width));
  const y = Math.max(0, Math.min(top, top + height));
  const w = Math.min(canvas.width - x, Math.abs(width));
  const h = Math.min(canvas.height - y, Math.abs(height));
  if (w < 4 || h < 4) return null;
  const ellipse = new fabric.Ellipse({ left: x, top: y, rx: w / 2, ry: h / 2, fill: 'rgba(239,68,68,0.28)', stroke: '#ff3b3b', strokeWidth: 2, strokeDashArray: [8, 5], selectable: false, evented: false, excludeFromLayers: true, excludeFromExport: true, objectCaching: false });
  decorateMaskOverlay(ellipse, 'selection-mask');
  ellipse.maskRole = 'selection-mask';
  ellipse.targetLayerId = layerKey(target);
  canvas.add(ellipse);
  canvas.bringToFront(ellipse);
  maskRegions.push({ id: ellipse.maskRegionId, left: x, top: y, width: w, height: h, targetLayerId: layerKey(target), shape: 'ellipse' });
  canvas.renderAll();
  saveHistory('Region ellipse selection');
  updateMaskInfo();
  setStatus(`선택 이미지 부분 타원 추가: ${Math.round(w)}×${Math.round(h)}.`);
  return ellipse;
}

function closeLassoPath(path) {
  if (!path) return path;
  const commands = path.path || [];
  const last = commands[commands.length - 1];
  if (commands.length && last?.[0] !== 'Z' && last?.[0] !== 'z') commands.push(['Z']);
  path.set({
    path: commands,
    fill: 'rgba(239,68,68,0.18)',
    stroke: '#ff3b3b',
    strokeWidth: 2,
    strokeDashArray: [8, 5],
    selectable: false,
    evented: false,
    excludeFromLayers: true,
    excludeFromExport: true,
    objectCaching: false,
  });
  path.setCoords();
  return path;
}

function addRegionPath(path) {
  const target = ensureRegionSelectionTarget();
  if (!target) { canvas.remove(path); return null; }
  closeLassoPath(path);
  addMaskPath(path, 'selection-mask');
  path.maskRole = 'selection-mask';
  path.targetLayerId = layerKey(target);
  setStatus('선택 이미지 부분 올가미 영역을 추가했습니다.');
  return path;
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
  saveHistory('Grip anchor');
  updateMaskInfo();
  setStatus(`손잡이 앵커 지정: ${Math.round(replacementGripAnchor.x)}, ${Math.round(replacementGripAnchor.y)}. 새 오브젝트의 grip %가 이 점에 맞춰집니다.`);
  return c;
}

function setRegionOverlayInteractivity(editable) {
  positiveEditMaskOverlays().forEach(o => {
    o.selectable = editable;
    o.evented = editable;
    o.hasControls = editable;
    o.hasBorders = editable;
    o.lockRotation = true;
    o.excludeFromLayers = true;
    o.excludeFromExport = true;
    o.setCoords();
  });
}

function updateRegionInfoFromOverlay(overlay) {
  if (!overlay || !overlay.isMaskOverlay || overlay.maskRole !== 'selection-mask') return;
  const rect = overlay.getBoundingRect(true, true);
  const region = maskRegions.find(r => r.id === overlay.maskRegionId);
  if (region) {
    region.left = rect.left;
    region.top = rect.top;
    region.width = rect.width;
    region.height = rect.height;
    region.targetLayerId = overlay.targetLayerId || region.targetLayerId;
  }
  updateMaskInfo();
}

function clearRegionSelectionVisuals(message = 'Selection cleared') {
  const overlays = positiveEditMaskOverlays();
  overlays.forEach(o => canvas.remove(o));
  maskRegions = maskRegions.filter(r => !overlays.some(o => o.maskRegionId === r.id));
  canvas.discardActiveObject();
  canvas.renderAll();
  updateMaskInfo();
  setStatus(message);
}

function clearMask() {
  const overlays = maskOverlays();
  overlays.forEach(o => canvas.remove(o));
  maskRegions = [];
  replacementGripAnchor = null;
  canvas.renderAll();
  saveHistory('Clear mask');
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
  saveHistory('Invert mask');
  updateMaskInfo();
  setStatus('Mask inverted visually. Phase 3A에서는 반전 미리보기까지 지원합니다.');
}

function clearRegionSelectionOnly() {
  clearRegionSelectionVisuals('선택영역을 해제했습니다.');
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
      fill: isErase ? '#000' : '#fff',
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

async function exportRegionSelectionPng() {
  const target = selectedLayerObject();
  if (!target || target.type !== 'image' || target.isDrawingLayer || target.excludeFromLayers) {
    alert('먼저 PNG로 내보낼 이미지 레이어를 선택하세요.');
    return;
  }
  const maskDataUrl = await buildMaskDataUrl('edit');
  const regionBounds = regionBoundsFromMaskOverlays();
  if (!maskDataUrl || !regionBounds) {
    alert('먼저 영역 선택 도구에서 사각형/원형/올가미로 이미지 부분을 선택하세요.');
    return;
  }
  const regionUrl = await selectedRegionAsFullCanvasDataUrl(target, maskDataUrl);
  const regionCroppedUrl = await cropCanvasDataUrlToBounds(regionUrl, regionBounds);
  downloadDataUrl(regionCroppedUrl, 'asset-studio-region-selection.png');
  setStatus('선택영역 PNG를 투명 배경 crop으로 내보냈습니다.');
}

function selectedRegionEditState() {
  const target = selectedLayerObject();
  const overlays = positiveEditMaskOverlays();
  const bbox = regionBoundsFromMaskOverlays();
  if (!target || target.type !== 'image' || target.isDrawingLayer || target.excludeFromLayers) {
    return { ok: false, reason: '먼저 AI 수정할 이미지 레이어를 선택하세요.', target, overlays, bbox };
  }
  if (!overlays.length || !bbox) {
    return { ok: false, reason: '먼저 영역 선택 도구에서 수정할 이미지 부분을 선택하세요.', target, overlays, bbox };
  }
  return { ok: true, target, overlays, bbox };
}

function prepareSelectedRegionAiEdit() {
  const state = selectedRegionEditState();
  if (!state.ok) {
    setStatus(state.reason);
    alert(state.reason);
    return false;
  }
  const summary = `선택영역 AI 수정 준비: ${nameOf(state.target)} · ${Math.round(state.bbox.width)}×${Math.round(state.bbox.height)}`;
  if ($('directInpaintDetails')) $('directInpaintDetails').open = true;
  if ($('aiMaskSummary')) $('aiMaskSummary').textContent = summary;
  if ($('inpaintResult')) $('inpaintResult').textContent = '프롬프트 입력 후 선택영역 직접 재생성을 누르세요.';
  $('aiEditPanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  $('inpaintPrompt')?.focus();
  setStatus('선택영역 AI 수정 준비 완료: 프롬프트 입력 후 직접 재생성을 누르세요.');
  return true;
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

function configureRegionSelectionTool() {
  if (currentTool !== 'region') return;
  regionSelectionMode = $('regionMode')?.value || regionSelectionMode || 'rect';
  const count = positiveEditMaskOverlays().length;
  canvas.selection = false;
  canvas.isDrawingMode = regionSelectionMode === 'lasso' && count === 0;
  canvas.defaultCursor = regionSelectionMode === 'lasso' && count === 0 ? 'crosshair' : 'crosshair';
  if (canvas.isDrawingMode) {
    canvas.freeDrawingBrush = new fabric.PencilBrush(canvas);
    canvas.freeDrawingBrush.width = 3;
    canvas.freeDrawingBrush.color = 'rgba(239,68,68,0.78)';
  }
  setRegionOverlayInteractivity(true);
  if ($('regionSelectionInfo')) $('regionSelectionInfo').textContent = `선택영역: ${count}`;
}

function beginRegionSelection(opt) {
  if (regionSelectionMode === 'lasso') return;
  const target = ensureRegionSelectionTarget();
  if (!target) return;
  const p = canvas.getPointer(opt.e);
  isRegionSelecting = true;
  regionSelectionStart = { x: clamp(p.x, 0, canvas.width), y: clamp(p.y, 0, canvas.height) };
  const common = { left: regionSelectionStart.x, top: regionSelectionStart.y, fill: 'rgba(239,68,68,0.18)', stroke: '#ff3b3b', strokeWidth: 2, strokeDashArray: [8, 5], selectable: false, evented: false, excludeFromLayers: true, excludeFromExport: true, objectCaching: false };
  regionSelectionPreview = regionSelectionMode === 'ellipse'
    ? new fabric.Ellipse({ ...common, rx: 1, ry: 1 })
    : new fabric.Rect({ ...common, width: 1, height: 1 });
  regionSelectionPreview.isMaskOverlay = true;
  regionSelectionPreview.maskRole = 'preview';
  regionSelectionPreview.name = '영역 선택 미리보기';
  canvas.add(regionSelectionPreview);
  canvas.bringToFront(regionSelectionPreview);
}

function updateRegionSelection(opt) {
  if (!isRegionSelecting || !regionSelectionPreview || !regionSelectionStart) return;
  const p = canvas.getPointer(opt.e);
  const x = clamp(p.x, 0, canvas.width);
  const y = clamp(p.y, 0, canvas.height);
  const left = Math.min(regionSelectionStart.x, x);
  const top = Math.min(regionSelectionStart.y, y);
  const width = Math.abs(x - regionSelectionStart.x);
  const height = Math.abs(y - regionSelectionStart.y);
  if (regionSelectionMode === 'ellipse') regionSelectionPreview.set({ left, top, rx: width / 2, ry: height / 2 });
  else regionSelectionPreview.set({ left, top, width, height });
  regionSelectionPreview.setCoords();
  canvas.renderAll();
}

function finishRegionSelection() {
  if (!isRegionSelecting) return;
  isRegionSelecting = false;
  if (regionSelectionPreview) {
    const left = regionSelectionPreview.left || 0;
    const top = regionSelectionPreview.top || 0;
    const width = regionSelectionMode === 'ellipse' ? (regionSelectionPreview.rx || 0) * 2 : (regionSelectionPreview.width || 0);
    const height = regionSelectionMode === 'ellipse' ? (regionSelectionPreview.ry || 0) * 2 : (regionSelectionPreview.height || 0);
    canvas.remove(regionSelectionPreview);
    regionSelectionPreview = null;
    if (regionSelectionMode === 'ellipse') addRegionEllipse(left, top, width, height);
    else {
      const target = ensureRegionSelectionTarget();
      const overlay = target ? addMaskRect(left, top, width, height) : null;
      if (overlay && target) {
        overlay.maskRole = 'selection-mask';
        overlay.targetLayerId = layerKey(target);
        setStatus(`선택 이미지 부분 사각 추가: ${Math.round(width)}×${Math.round(height)}.`);
      }
    }
  }
  regionSelectionStart = null;
  configureRegionSelectionTool();
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
  const regionCount = positiveRegionSelectionOverlays().length;
  const regionBbox = regionBoundsFromMaskOverlays();
  return {
    canvas: { width: canvas.width, height: canvas.height, background: canvas.backgroundColor || 'transparent' },
    selectedLayer: target ? { id: layerKey(target), name: nameOf(target), type: target.isDrawingLayer ? 'drawing' : target.type, visible: target.visible !== false, locked: !!target.locked } : null,
    layerCount: visibleLayers.length,
    layers: visibleLayers.map(o => ({ id: layerKey(o), name: nameOf(o), type: o.isDrawingLayer ? 'drawing' : o.type, visible: o.visible !== false })).slice(0, 20),
    mask: { count: editCount + occCount, editCount, occlusionCount: occCount },
    regionSelection: { count: regionCount, bbox: regionBbox },
  };
}

function refreshAiChatState() {
  const state = $('aiChatState');
  if (!state) return;
  const ctx = canvasChatContext();
  const selected = ctx.selectedLayer ? `${ctx.selectedLayer.name} / ${ctx.selectedLayer.type}` : '선택 없음';
  state.textContent = `선택: ${selected} · 레이어 ${ctx.layerCount} · 마스크 ${ctx.mask.count} · 선택영역 ${ctx.regionSelection.count}`;
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
    case 'activate_region':
      activateTool('region');
      done('실행됨: 영역 도구로 전환했습니다. 이미지 위에서 수정할 부분을 선택하세요.');
      break;
    case 'activate_text':
      activateTool('text');
      done('실행됨: 텍스트 도구로 전환했습니다.');
      break;
    case 'select_image_needed':
      activateTool(params.tool || 'select');
      done('안내: 이미지 레이어를 선택한 뒤 다시 명령하세요. 선택 도구로 전환했습니다.');
      break;
    case 'prepare_region_inpaint': {
      if ($('inpaintPrompt')) $('inpaintPrompt').value = params.prompt || '';
      const prepared = prepareSelectedRegionAiEdit();
      if (prepared) done('준비됨: 선택영역 AI 수정 패널로 연결했습니다. 프롬프트 확인 후 실행하세요.');
      else done('안내: 이미지 레이어와 선택영역을 먼저 준비하세요.');
      break;
    }
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
  const toolNames = { select:'선택', region:'영역 선택', pan:'작업영역 이동', crop:'크롭', brush:'브러시', pencil:'펜슬', eraser:'지우개', mask:'마스크', text:'텍스트', shape:'도형', upload:'이미지 가져오기', ai:'AI' };
  $('toolModeLabel').textContent = `${toolNames[tool] || tool} 도구`;
  $('workspace').classList.toggle('pan-mode', tool === 'pan');
  canvas.getObjects().forEach(o => {
    if (o.__lockedByPan && tool !== 'pan') { o.selectable = true; delete o.__lockedByPan; }
    if (o.__lockedByCrop && tool !== 'crop') { o.selectable = true; delete o.__lockedByCrop; }
    if (o.__lockedByRegion && tool !== 'region') { o.selectable = true; delete o.__lockedByRegion; }
  });
  if (tool !== 'crop') clearCropPreview();
  if (tool !== 'region' && regionSelectionPreview) { canvas.remove(regionSelectionPreview); regionSelectionPreview = null; isRegionSelecting = false; }
  if (tool !== 'region') setRegionOverlayInteractivity(false);
  if (['brush','pencil','eraser'].includes(tool)) { setMaskMode(false); setDrawingTool(tool); }
  else { setDrawingTool('select'); setMaskMode(tool === 'mask'); }
  if (tool === 'region') {
    canvas.selection = false;
    canvas.getObjects().forEach(o => {
      if (o.isMaskOverlay) return;
      if (o.selectable !== false) o.__lockedByRegion = true;
      o.selectable = false;
    });
    configureRegionSelectionTool();
    canvas.renderAll();
  } else if (tool === 'pan') {
    canvas.selection = false;
    canvas.discardActiveObject();
    canvas.getObjects().forEach(o => {
      if (o.selectable !== false) o.__lockedByPan = true;
      o.selectable = false;
    });
    canvas.defaultCursor = 'grab';
    canvas.renderAll();
  } else if (tool === 'crop') {
    canvas.selection = false;
    canvas.discardActiveObject();
    canvas.getObjects().forEach(o => {
      if (o.selectable !== false) o.__lockedByCrop = true;
      o.selectable = false;
    });
    canvas.defaultCursor = 'crosshair';
    canvas.renderAll();
  } else if (tool !== 'mask') {
    canvas.selection = true;
    canvas.defaultCursor = 'default';
  }
  const notes = {
    select:'선택 모드. 레이어 선택/이동/리사이즈 가능.',
    region:'영역 선택 모드. 선택 이미지 레이어 위에서 사각형/원형/올가미로 특정 부분을 선택합니다.',
    pan:'작업영역 이동 모드. 캔버스 판을 자유롭게 드래그합니다.',
    crop:'크롭 모드. 캔버스 위에서 드래그해 영역을 잡은 뒤 캔버스 크롭/선택 이미지 크롭을 누르세요.',
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
if ($('applyCanvasCrop')) $('applyCanvasCrop').onclick = applyCanvasCrop;
if ($('cropSelectedImage')) $('cropSelectedImage').onclick = cropSelectedImage;
if ($('resizeFitObjects')) $('resizeFitObjects').onclick = resizeCanvasFitObjects;
$('fitCanvas').onclick = fitView;
$('zoomIn').onclick = () => zoomBy(1.12);
$('zoomOut').onclick = () => zoomBy(1 / 1.12);
$('workspace').addEventListener('wheel', (e) => {
  const shell = $('canvasShell');
  if (!shell.contains(e.target) && e.target !== $('workspace')) return;
  e.preventDefault();
  zoomBy(e.deltaY < 0 ? 1.12 : 1 / 1.12, e);
}, { passive: false });
$('canvasBg').oninput = () => { canvas.backgroundColor = $('canvasBg').value; $('canvasShell')?.classList.remove('checker'); canvas.renderAll(); saveHistory(); };
$('transparentBg').onclick = () => { showTransparentCanvasPreview(); canvas.renderAll(); saveHistory(); };
$('whiteBg').onclick = () => { canvas.backgroundColor = '#ffffff'; $('canvasBg').value = '#ffffff'; $('canvasShell')?.classList.remove('checker'); canvas.renderAll(); saveHistory(); };
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
  const middleMouse = e.button === 1;
  if (currentTool !== 'pan' && !middleMouse) return;
  beginWorkspacePan(e);
});
window.addEventListener('mousemove', updateWorkspacePan);
window.addEventListener('mouseup', endWorkspacePan);

$('addText').onclick = () => addToCanvas(new fabric.Textbox($('newText').value || 'Text', { left: 160, top: 160, width: 420, fontSize: 72, fontFamily: 'Inter, Arial', fill: '#111111' }), 'Text');
$('addTitle').onclick = () => addToCanvas(new fabric.Textbox('BIG TITLE', { left: 140, top: 140, width: 620, fontSize: 112, fontFamily: 'Inter, Arial', fontWeight: 800, fill: '#111111', stroke: '#ffffff', strokeWidth: 0 }), 'Title');
$('addRect').onclick = () => addToCanvas(new fabric.Rect({ left: 160, top: 160, width: 320, height: 200, fill: '#7c5cff', rx: 0, ry: 0 }), 'Rectangle');
$('addRoundRect').onclick = () => addToCanvas(new fabric.Rect({ left: 160, top: 160, width: 340, height: 210, fill: '#ffffff', stroke: '#111111', strokeWidth: 4, rx: 28, ry: 28 }), 'Round Rectangle');
$('addCircle').onclick = () => addToCanvas(new fabric.Circle({ left: 180, top: 180, radius: 110, fill: '#22c55e' }), 'Circle');
$('addLine').onclick = () => addToCanvas(new fabric.Line([120,120,460,120], { left: 160, top: 220, stroke: '#111111', strokeWidth: 8 }), 'Line');
$('addLayer').onclick = () => createDrawingLayer();
$('addImageLayer').onclick = addBlankImageLayer;
if ($('layerOpacity')) $('layerOpacity').oninput = applyLayerOpacity;
if ($('groupSelection')) $('groupSelection').onclick = groupSelection;
if ($('ungroupSelection')) $('ungroupSelection').onclick = ungroupSelection;
if ($('exportLayer')) $('exportLayer').onclick = exportActiveLayer;
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
if ($('eraseSelectedByMask')) $('eraseSelectedByMask').onclick = eraseSelectedByMask;
if ($('restoreSelectedByMask')) $('restoreSelectedByMask').onclick = restoreSelectedByMask;
if ($('restoreSelectedOriginal')) $('restoreSelectedOriginal').onclick = restoreSelectedOriginal;
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
if ($('regionMode')) $('regionMode').onchange = () => { configureRegionSelectionTool(); setStatus(`영역 선택: ${$('regionMode').value}`); };
if ($('copyRegionSelection')) $('copyRegionSelection').onclick = () => putSelectedRegionOnClipboard({ cut: false });
if ($('cutRegionSelection')) $('cutRegionSelection').onclick = () => putSelectedRegionOnClipboard({ cut: true });
if ($('pasteRegionSelection')) $('pasteRegionSelection').onclick = () => pasteRegionClipboard().catch(err => { console.error(err); alert(`붙여넣기 실패: ${err.message}`); });
if ($('regionAiEdit')) $('regionAiEdit').onclick = prepareSelectedRegionAiEdit;
if ($('clearRegionSelection')) $('clearRegionSelection').onclick = clearRegionSelectionOnly;
if ($('exportRegionSelection')) $('exportRegionSelection').onclick = exportRegionSelectionPng;
$('exportPng').onclick = exportFull; $('exportPng2').onclick = exportFull; $('exportSelected').onclick = exportSelectedOnly;
$('undoBtn').onclick = undoHistory;
$('redoBtn').onclick = redoHistory;

$('saveProject').onclick = () => {
  const blob = new Blob([JSON.stringify(canvas.toDatalessJSON(SERIALIZED_PROPS), null, 2)], {type:'application/json'});
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

canvas.on('selection:created', () => { if (active() && !canSelectLayer(active())) { canvas.discardActiveObject(); setStatus(active()?.visible === false ? '레이어가 숨김 상태입니다. Show 후 선택하세요.' : '레이어가 잠겨 있습니다. Unlock 후 편집하세요.'); } rememberSelectedLayer(active()); syncProps(); renderLayers(); refreshAiChatState(); });
canvas.on('selection:updated', () => { if (active() && !canSelectLayer(active())) { canvas.discardActiveObject(); setStatus(active()?.visible === false ? '레이어가 숨김 상태입니다. Show 후 선택하세요.' : '레이어가 잠겨 있습니다. Unlock 후 편집하세요.'); } rememberSelectedLayer(active()); syncProps(); renderLayers(); refreshAiChatState(); });
canvas.on('selection:cleared', () => { syncProps(); renderLayers(); refreshAiChatState(); });
canvas.on('mouse:down', (opt) => {
  if (currentTool === 'region') {
    if (opt.target?.isMaskOverlay && opt.target.maskRole === 'selection-mask') return;
    beginRegionSelection(opt);
    return;
  }
  if (currentTool === 'crop') {
    beginCropSelection(opt);
    return;
  }
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
  if (currentTool === 'region') {
    updateRegionSelection(opt);
    return;
  }
  if (currentTool === 'crop') {
    updateCropSelection(opt);
    return;
  }
  if (currentTool !== 'mask' || maskDrawMode !== 'rect' || !isMaskDragging || !maskPreview || !maskStart) return;
  const p = canvas.getPointer(opt.e);
  const x = clamp(p.x, 0, canvas.width);
  const y = clamp(p.y, 0, canvas.height);
  maskPreview.set({ left: Math.min(maskStart.x, x), top: Math.min(maskStart.y, y), width: Math.abs(x - maskStart.x), height: Math.abs(y - maskStart.y) });
  maskPreview.setCoords();
  canvas.renderAll();
});
canvas.on('mouse:up', () => {
  if (currentTool === 'region') {
    finishRegionSelection();
    return;
  }
  if (currentTool === 'crop') {
    finishCropSelection();
    return;
  }
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
  if (currentTool === 'region') {
    if (regionSelectionMode === 'lasso') addRegionPath(path);
    else canvas.remove(path);
    configureRegionSelectionTool();
    return;
  }
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
    const target = selectedLayerObject();
    canvas.remove(path);
    if (!target || target.type !== 'image') {
      setStatus('지우개는 선택 이미지 레이어에만 적용됩니다. 먼저 이미지 레이어를 선택하세요.');
      canvas.isDrawingMode = false;
      activateTool('select');
      return;
    }
    const maskDataUrl = pathToMaskDataUrl(path);
    eraseImageWithMaskDataUrl(target, maskDataUrl, 'Freehand erase').catch(err => {
      console.error(err);
      alert(`지우개 적용 실패: ${err.message}`);
    });
    return;
  }
  path.selectable = false;
  path.evented = false;
  saveHistory('Brush stroke');
  renderLayers();
  setStatus('Stroke added to drawing surface. 레이어 목록에는 개별 선을 쌓지 않습니다.');
});
canvas.on('object:modified', (e) => {
  if (e.target?.isMaskOverlay && e.target.maskRole === 'selection-mask') updateRegionInfoFromOverlay(e.target);
  saveHistory(); syncProps(); renderLayers(); refreshAiChatState();
});
canvas.on('object:moving', (e) => { if (isLayerLocked(e.target)) { setStatus('레이어가 잠겨 있습니다. Unlock 후 이동하세요.'); e.target.setCoords(); canvas.discardActiveObject(); canvas.renderAll(); } });
canvas.on('object:added', (e) => { if (e.target) enforceLayerInteractivity(e.target); if (!suppressHistory) renderLayers(); updateEmptyCanvasHint(); refreshAiChatState(); });
canvas.on('object:removed', () => { if (!suppressHistory) renderLayers(); updateEmptyCanvasHint(); refreshAiChatState(); });

function handleEscapeShortcut(e) {
  if (e.key !== 'Escape') return false;
  if (isEditableTextField()) return false;
  if (regionSelectionPreview || positiveEditMaskOverlays().length) {
    if (regionSelectionPreview) { canvas.remove(regionSelectionPreview); regionSelectionPreview = null; isRegionSelecting = false; }
    clearRegionSelectionVisuals('Selection cleared');
    e.preventDefault();
    return true;
  }
  return false;
}

function handleClipboardShortcut(e) {
  if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey) return false;
  if (isEditableTextField()) return false;
  const key = e.key.toLowerCase();
  if (key === 'c') {
    putSelectedRegionOnClipboard({ cut: false }).catch(err => { console.error(err); alert(`선택영역 복사 실패: ${err.message}`); });
    e.preventDefault();
    return true;
  }
  if (key === 'x') {
    putSelectedRegionOnClipboard({ cut: true }).catch(err => { console.error(err); alert(`선택영역 잘라내기 실패: ${err.message}`); });
    e.preventDefault();
    return true;
  }
  if (key === 'v') {
    pasteRegionClipboard().catch(err => { console.error(err); alert(`붙여넣기 실패: ${err.message}`); });
    e.preventDefault();
    return true;
  }
  return false;
}

function handleHistoryShortcut(e) {
  if (!(e.metaKey || e.ctrlKey)) return false;
  const key = e.key.toLowerCase();
  const isUndoKey = key === 'z';
  const isRedoKey = key === 'y';
  if (!isUndoKey && !isRedoKey) return false;
  if (isEditableTextField()) return false;
  if (isUndoKey && e.shiftKey) redoHistory();
  else if (isUndoKey) undoHistory();
  else if (isRedoKey) redoHistory();
  e.preventDefault();
  return true;
}

window.addEventListener('resize', fitView);
window.addEventListener('keydown', (e) => {
  if (handleEscapeShortcut(e)) return;
  if (handleClipboardShortcut(e)) return;
  if (handleHistoryShortcut(e)) return;
  if ((e.metaKey || e.ctrlKey) && ['+','=','-','0'].includes(e.key)) {
    if (e.key === '0') fitView();
    else zoomBy(e.key === '-' ? 1 / 1.12 : 1.12);
    e.preventDefault();
    return;
  }
  if (handleToolShortcut(e)) return;
  const tag = document.activeElement?.tagName;
  if (['INPUT','TEXTAREA','SELECT'].includes(tag)) return;
  if (e.code === 'Space' && !e.repeat) { startTemporaryPan(); e.preventDefault(); }
  if (e.key === 'Delete' || e.key === 'Backspace') { $('deleteObj').click(); e.preventDefault(); }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'd') { $('duplicateObj').click(); e.preventDefault(); }
});
window.addEventListener('keyup', (e) => {
  const tag = document.activeElement?.tagName;
  if (['INPUT','TEXTAREA','SELECT'].includes(tag)) return;
  if (e.code === 'Space') endTemporaryPan();
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
