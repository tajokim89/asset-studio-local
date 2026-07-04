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
const FREE_PAN_PAD = 1800;
const FREE_PAN_EDGE = 80;
let canvasPanOffset = { x: 0, y: 0 };
let activeDrawingLayerId = null;
let selectedLayerId = null;
let isMaskDragging = false;
let maskStart = null;
let maskPreview = null;
let maskRegions = [];
let maskLockedObjects = false;
let maskDrawMode = 'brush';
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
  const json = JSON.stringify(canvas.toDatalessJSON(['id','name','_originalSrc','excludeFromLayers','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId']));
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
function nameOf(obj) { return obj?.name || obj?.text || obj?.type || 'Layer'; }
function layerKey(obj) { return obj ? (obj.layerId || obj.id) : null; }
function active() { return canvas.getActiveObject(); }
function objectByLayerId(id) { return canvas.getObjects().find(o => layerKey(o) === id); }
function selectedLayerObject() { return active() || objectByLayerId(selectedLayerId); }
function rememberSelectedLayer(obj) { selectedLayerId = layerKey(obj); }

function ensureMeta(obj, name) {
  obj.id ||= uid(obj.type || 'layer');
  obj.name ||= name || `${obj.type || 'Layer'} ${canvas.getObjects().length}`;
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
  setStatus(`${layer.name} added and selected.`);
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

function addGallery(url, label='asset') {
  const card = document.createElement('div');
  card.className = 'asset-card';
  card.innerHTML = `<img src="${url}"><span>${label}</span>`;
  card.onclick = () => addImageUrl(url, label);
  $('gallery').prepend(card);
}

function syncProps() {
  const obj = selectedLayerObject();
  $('selectedName').textContent = obj ? `${nameOf(obj)} (${obj.isDrawingLayer ? 'drawing layer' : obj.type})` : 'No selection';
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
}

function setCanvasSize(w, h) {
  canvas.setWidth(w); canvas.setHeight(h);
  canvas.getObjects().forEach(o => { if (o.isDrawingLayer) o.set({ width: w, height: h }); });
  $('canvasW').value = w; $('canvasH').value = h;
  canvas.renderAll();
  fitView();
  saveHistory();
}

function updateCanvasStageSize() {
  const workspace = $('workspace');
  const stage = $('canvasStage');
  const shell = $('canvasShell');
  if (!workspace || !stage || !shell) return { left: 0, top: 0, scaledW: 0, scaledH: 0 };
  const baseW = shell.offsetWidth || (canvas.width + 36);
  const baseH = shell.offsetHeight || (canvas.height + 36);
  const scaledW = baseW * viewScale;
  const scaledH = baseH * viewScale;
  const freePad = FREE_PAN_PAD;
  const stageW = Math.ceil(Math.max(workspace.clientWidth, scaledW + freePad * 2));
  const stageH = Math.ceil(Math.max(workspace.clientHeight, scaledH + freePad * 2));
  const baseLeft = Math.round((stageW - scaledW) / 2);
  const baseTop = Math.round((stageH - scaledH) / 2);
  const maxOffsetX = Math.max(0, baseLeft - FREE_PAN_EDGE);
  const maxOffsetY = Math.max(0, baseTop - FREE_PAN_EDGE);
  canvasPanOffset.x = clamp(canvasPanOffset.x, -maxOffsetX, maxOffsetX);
  canvasPanOffset.y = clamp(canvasPanOffset.y, -maxOffsetY, maxOffsetY);
  const left = Math.round(baseLeft + canvasPanOffset.x);
  const top = Math.round(baseTop + canvasPanOffset.y);
  stage.style.width = `${stageW}px`;
  stage.style.height = `${stageH}px`;
  shell.style.left = `${left}px`;
  shell.style.top = `${top}px`;
  return { left, top, scaledW, scaledH, stageW, stageH, baseLeft, baseTop };
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
  let contentX = null;
  let contentY = null;
  if (anchorEvent) {
    const wsRect = workspace.getBoundingClientRect();
    anchorX = anchorEvent.clientX - wsRect.left;
    anchorY = anchorEvent.clientY - wsRect.top;
  }
  contentX = (workspace.scrollLeft + anchorX - prevLeft) / previous;
  contentY = (workspace.scrollTop + anchorY - prevTop) / previous;

  viewScale = next;
  shell.style.transform = `scale(${viewScale})`;
  shell.style.transformOrigin = 'top left';
  const pos = updateCanvasStageSize();
  if ($('zoomLabel')) $('zoomLabel').textContent = `${Math.round(viewScale * 100)}%`;

  workspace.scrollLeft = pos.left + contentX * viewScale - anchorX;
  workspace.scrollTop = pos.top + contentY * viewScale - anchorY;
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
  setStatus('Full PNG exported.');
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
  setStatus('Selected PNG exported.');
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
    setStatus('Color background removed on selected image.');
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
    setStatus('Image reset to original.');
  }, { crossOrigin: 'anonymous' });
}

function maskOverlays() {
  return canvas.getObjects().filter(o => o.isMaskOverlay);
}

function refreshMaskStateFromCanvas() {
  maskRegions = maskOverlays().map(o => ({
    id: o.maskRegionId || o.id || uid('maskRegion'),
    left: o.left || 0,
    top: o.top || 0,
    width: Math.max(0, (o.width || 0) * (o.scaleX || 1)),
    height: Math.max(0, (o.height || 0) * (o.scaleY || 1)),
    targetLayerId: o.targetLayerId || selectedLayerId || null,
  }));
  updateMaskInfo();
}

function updateMaskInfo() {
  const count = maskOverlays().filter(o => o.maskRole !== 'inverted-hole' && o.maskRole !== 'preview').length;
  const label = `Mask marks: ${count}`;
  if ($('maskInfo')) $('maskInfo').textContent = label;
  if ($('aiMaskSummary')) $('aiMaskSummary').textContent = count ? `${count} mask mark(s) ready for Phase 4 inpaint.` : 'No mask selected';
}

function decorateMaskOverlay(obj, role = 'selection-mask') {
  const target = selectedLayerObject();
  obj.id ||= uid(role === 'mask-eraser' ? 'maskErase' : 'mask');
  obj.name = role === 'mask-eraser' ? 'Mask Eraser Stroke' : (obj.type === 'path' ? 'Mask Brush Stroke' : 'Mask Rectangle');
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
  path.set({
    fill: null,
    stroke: role === 'mask-eraser' ? 'rgba(34,197,94,0.78)' : 'rgba(239,68,68,0.62)',
    strokeLineCap: 'round',
    strokeLineJoin: 'round',
    strokeDashArray: role === 'mask-eraser' ? [6, 6] : null,
  });
  canvas.bringToFront(path);
  canvas.renderAll();
  saveHistory();
  updateMaskInfo();
  setStatus(role === 'mask-eraser' ? 'Mask eraser stroke added. Export PNG에서는 이 부분이 보호 영역(black)으로 빠집니다.' : 'Brush mask stroke added. Phase 4 inpaint 입력으로 쓸 수 있습니다.');
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
  setStatus(`Mask rectangle added: ${Math.round(w)}×${Math.round(h)}. Phase 4 inpaint 입력으로 쓸 수 있습니다.`);
  return overlay;
}

function clearMask() {
  const overlays = maskOverlays();
  overlays.forEach(o => canvas.remove(o));
  maskRegions = [];
  canvas.renderAll();
  saveHistory();
  updateMaskInfo();
  setStatus('Mask cleared.');
}

function invertMask() {
  const overlays = maskOverlays();
  if (!overlays.length) { alert('반전할 마스크가 없습니다. 먼저 Mask 툴로 영역을 만드세요.'); return; }
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

async function exportMaskPng() {
  const overlays = maskOverlays().filter(o => o.maskRole !== 'inverted-hole' && o.maskRole !== 'preview');
  if (!overlays.length) { alert('Export할 마스크가 없습니다.'); return; }
  const tmp = document.createElement('canvas');
  tmp.width = canvas.width; tmp.height = canvas.height;
  const maskCanvas = new fabric.StaticCanvas(tmp, { backgroundColor: '#000' });
  for (const o of overlays) {
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
  downloadDataUrl(tmp.toDataURL('image/png'), 'asset-studio-mask.png');
  maskCanvas.dispose();
  setStatus('Mask PNG exported: white=selected/edit area, black=protected area.');
}

function configureMaskBrush() {
  if (currentTool !== 'mask') return;
  maskDrawMode = $('maskMode')?.value || maskDrawMode || 'brush';
  const size = +($('maskSize')?.value || 48);
  if ($('maskSizeValue')) $('maskSizeValue').textContent = String(size);
  canvas.isDrawingMode = maskDrawMode !== 'rect';
  canvas.selection = false;
  canvas.defaultCursor = maskDrawMode === 'rect' ? 'crosshair' : 'cell';
  if (canvas.isDrawingMode) {
    canvas.freeDrawingBrush = new fabric.PencilBrush(canvas);
    canvas.freeDrawingBrush.width = size;
    canvas.freeDrawingBrush.color = maskDrawMode === 'erase' ? 'rgba(34,197,94,0.78)' : 'rgba(239,68,68,0.62)';
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

function activateTool(tool) {
  currentTool = tool;
  document.querySelectorAll('.tool-button').forEach(b => b.classList.toggle('active', b.dataset.tool === tool));
  document.querySelectorAll('.option-panel').forEach(p => p.classList.toggle('active', p.dataset.toolPanel === tool));
  $('toolModeLabel').textContent = `${tool[0].toUpperCase()}${tool.slice(1)} mode`;
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
    select:'Select mode. 레이어 선택/이동/리사이즈 가능.',
    pan:'Pan mode. 확대하지 않은 상태에서도 캔버스 판 자체를 자유롭게 드래그해 이동합니다.',
    crop:'Crop mode scaffold. Phase 1에서는 UI 자리만 잡았습니다.',
    brush:'Brush mode. 캔버스에 직접 그립니다.',
    pencil:'Pencil mode. 얇은 선으로 직접 그립니다.',
    eraser:'Eraser mode. 투명 지우개 스트로크를 만듭니다.',
    mask:'Mask mode. 브러시로 칠하거나 사각 선택으로 AI 편집 영역을 만듭니다.',
    text:'Text mode. 텍스트 추가/편집.',
    shape:'Shape mode. 기본 도형 추가.',
    upload:'Upload mode. 이미지 가져오기.',
    ai:'AI mode. 이미지 생성/AI 편집의 시작점.'
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
$('maskMode').onchange = () => { configureMaskBrush(); setStatus(`Mask ${$('maskMode').value} mode.`); };
$('maskSize').oninput = configureMaskBrush;
$('exportPng').onclick = exportFull; $('exportPng2').onclick = exportFull; $('exportSelected').onclick = exportSelectedOnly;
$('undoBtn').onclick = () => loadHistory(historyIndex - 1);
$('redoBtn').onclick = () => loadHistory(historyIndex + 1);

$('saveProject').onclick = () => {
  const blob = new Blob([JSON.stringify(canvas.toDatalessJSON(['id','name','_originalSrc','excludeFromLayers','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId']), null, 2)], {type:'application/json'});
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
  $('generateBtn').disabled = true; setStatus('AI generating... 30~90초 정도 걸릴 수 있습니다.');
  try {
    const res = await fetch('/api/generate', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ prompt, preset:$('aiPreset').value, aspect_ratio:$('aiAspect').value }) });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'generation failed');
    const url = data.url + '?t=' + Date.now();
    addGallery(url, data.model || 'generated');
    addImageUrl(url, 'AI generated');
    setStatus(`AI generated: ${data.model || ''}`);
  } catch (err) { setStatus('AI generation failed: ' + err.message); }
  finally { $('generateBtn').disabled = false; }
};

canvas.on('selection:created', () => { rememberSelectedLayer(active()); syncProps(); renderLayers(); });
canvas.on('selection:updated', () => { rememberSelectedLayer(active()); syncProps(); renderLayers(); });
canvas.on('selection:cleared', () => { syncProps(); renderLayers(); });
canvas.on('mouse:down', (opt) => {
  if (currentTool !== 'mask' || maskDrawMode !== 'rect') return;
  const p = canvas.getPointer(opt.e);
  isMaskDragging = true;
  maskStart = { x: clamp(p.x, 0, canvas.width), y: clamp(p.y, 0, canvas.height) };
  maskPreview = new fabric.Rect({ left: maskStart.x, top: maskStart.y, width: 1, height: 1, fill: 'rgba(239,68,68,0.22)', stroke: '#ff3b3b', strokeWidth: 2, strokeDashArray: [8, 5], selectable: false, evented: false, excludeFromLayers: true, excludeFromExport: true, objectCaching: false });
  maskPreview.isMaskOverlay = true;
  maskPreview.maskRole = 'preview';
  maskPreview.name = 'Mask Preview';
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
    addMaskPath(path, maskDrawMode === 'erase' ? 'mask-eraser' : 'selection-mask');
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
canvas.on('object:modified', () => { saveHistory(); syncProps(); renderLayers(); });
canvas.on('object:added', () => { if (!suppressHistory) renderLayers(); });
canvas.on('object:removed', () => { if (!suppressHistory) renderLayers(); });

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
saveHistory();
fitView();
activateTool('select');
setStatus('Phase 1 editor base ready. Select/Pan/Crop/Brush/Pencil/Eraser/Mask/Text/Shape/Upload/AI tool structure loaded.');
