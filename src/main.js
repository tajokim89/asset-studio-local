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
let spriteSlices = [];
let selectedSpriteSliceId = null;
let spriteSourceLayerId = null;
let animationPreviewTimer = null;
let animationPreviewFrames = [];
const $ = (id) => document.getElementById(id);
const appEl = document.querySelector('.app');
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
const SERIALIZED_PROPS = ['id','name','_originalSrc','_phase4PreservedOriginal','_assetId','_assetName','excludeFromLayers','excludeFromExport','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId'];

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

function directionLabelsForMode(mode = $('pixelDirectionMode')?.value || 'single') {
  if (mode === '8dir') return ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  if (mode === '4dir') return ['S', 'W', 'E', 'N'];
  return [($('pixelTargetDirection')?.value || 'S')];
}

function directionLabel(code) {
  return ({ S:'S/front, face camera', SW:'SW/front-left, body turned toward screen-left', W:'W/left true side profile, face screen-left', NW:'NW/back-left, back turned toward screen-left', N:'N/back', NE:'NE/back-right, back turned toward screen-right', E:'E/right true side profile, face screen-right', SE:'SE/front-right, body turned toward screen-right' })[code] || code;
}

const PIXEL_ACTOR_ASSET_TYPES = new Set(['character', 'monster']);
let lastActorAnimationPreset = 'idle';

function isPixelActorAssetType(type = $('pixelAssetType')?.value || 'character') {
  return PIXEL_ACTOR_ASSET_TYPES.has(type);
}

function effectivePixelAnimationPreset() {
  return isPixelActorAssetType() ? ($('pixelAnimationPreset')?.value || 'idle') : 'ui_static';
}

function requestedPixelFrameCount() {
  if (!isPixelActorAssetType() || effectivePixelAnimationPreset() === 'ui_static') return 1;
  return Math.max(1, Math.min(8, +($('pixelWalkFrames')?.value || 4)));
}

function syncPixelAssetWorkflowUi({ silent = false } = {}) {
  const type = $('pixelAssetType')?.value || 'character';
  const actor = isPixelActorAssetType(type);
  const motionIds = ['pixelMotionControls', 'pixelDirectionControls', 'pixelReferenceControls', 'pixelFrameControls', 'pixelLegacyDirectionControls'];
  motionIds.forEach(id => $(id)?.classList.toggle('hidden', !actor));
  $('pixelStaticModeNotice')?.classList.toggle('hidden', actor);
  $('pixelAdvancedBatch')?.classList.toggle('hidden', !actor);
  $('legacyDirectionalButtons')?.classList.add('hidden');

  if (!actor) {
    const current = $('pixelAnimationPreset')?.value || 'idle';
    if (current !== 'ui_static') lastActorAnimationPreset = current;
    if ($('pixelAnimationPreset')) $('pixelAnimationPreset').value = 'ui_static';
    if ($('pixelDirectionMode')) $('pixelDirectionMode').value = 'single';
    if ($('pixelTargetDirection')) $('pixelTargetDirection').value = 'S';
    if ($('pixelReferenceDirection')) $('pixelReferenceDirection').value = 'S';
    if ($('pixelWalkFrames')) $('pixelWalkFrames').value = '1';
  } else {
    if ($('pixelAnimationPreset')?.value === 'ui_static') $('pixelAnimationPreset').value = lastActorAnimationPreset || 'idle';
    if ($('pixelWalkFrames') && +$('pixelWalkFrames').value < 3) $('pixelWalkFrames').value = '4';
  }

  const typeLabel = ({ character:'캐릭터', monster:'몬스터', item:'아이템', ui_panel:'UI 패널', button:'버튼', icon:'아이콘', tile:'타일' })[type] || type;
  if ($('generatePixelAsset')) $('generatePixelAsset').textContent = actor ? `새 ${typeLabel} 스프라이트 생성` : `${typeLabel} 정적 에셋 생성`;
  if ($('generateFrontIdleFromSelected')) $('generateFrontIdleFromSelected').textContent = actor ? '선택 이미지 기준 방향/동작 생성' : '선택 이미지 스타일로 정적 에셋 생성';
  if ($('runPixelWorkflow')) $('runPixelWorkflow').textContent = actor ? '생성 → 배경 제거 → 그리드 값 맞춤' : '정적 에셋 생성 → 배경 제거';
  if (!silent) setStatus(actor ? `${typeLabel} 모드 · 동작/방향 선택 사용` : `${typeLabel} 모드 · 동작/방향 숨김 · 1프레임 생성`);
  applyPixelWorkflowGridDefaults();
}

function buildDirectionalSpriteSheetContract(anim = effectivePixelAnimationPreset()) {
  const mode = $('pixelDirectionMode')?.value || 'single';
  const dirs = directionLabelsForMode(mode);
  const refDir = $('pixelReferenceDirection')?.value || 'S';
  const targetDir = $('pixelTargetDirection')?.value || 'S';
  const frameCount = anim === 'ui_static' ? 1 : requestedPixelFrameCount();
  const columns = frameCount;
  const directionLine = mode === '8dir'
    ? '8-direction sprite sheet. Row order: N, NE, E, SE, S, SW, W, NW.'
    : (mode === '4dir' ? '4-direction sprite sheet. Row order: S, W, E, N.' : `Single target via one-direction generation. Generate exactly one target direction: ${directionLabel(targetDir)}. Do not generate a direction-candidate sheet, contact sheet, multi-direction atlas, or alternate direction candidates. Do not output all 8 directions; the app requests each direction separately. Screen-space directions: SW/W turn toward screen-left, SE/E turn toward screen-right.`);
  const actionLabel = ({ idle:'idle/breathing', walk4:'walk cycle', walk6:'walk cycle', attack:'attack', jump:'jump', cast:'cast', hurt:'hurt reaction', death:'death/collapse', ui_static:'static asset' })[anim] || anim;
  const frameLine = anim === 'ui_static'
    ? 'Static contract: exactly one clean isolated asset frame.'
    : `${actionLabel} columns: exactly ${frameCount} frames per requested direction, evenly spaced in one horizontal row; keep identity, scale, pivot, baseline, and palette consistent across every frame.`;
  const gridLine = mode === 'single'
    ? `Sheet grid: 1 row x ${columns} columns. The visible character must face ${directionLabel(targetDir)} in every cell.`
    : `Sheet grid: ${dirs.length} rows x ${columns} columns, evenly spaced cells, same scale and pivot in every cell.`;
  const cellSafetyLine = anim === 'ui_static'
    ? 'Cell safety: keep the single asset fully inside the canvas with clear empty margin on all sides.'
    : `Cell safety: treat each animation frame as a separate boxed cell. Put a wide empty transparent/chroma gutter between cells. Every body part, weapon, motion smear, slash arc, VFX, shadow, and silhouette must stay fully inside its own cell with at least 15% empty side margin. Nothing may touch or cross a cell boundary; if the motion would cross, shrink the pose/arc rather than spilling into the next frame.`;
  return `${directionLine}\nReference image direction: ${directionLabel(refDir)}. Use it only as the source view/style identity. Target direction is ${directionLabel(targetDir)}.\n${frameLine}\n${gridLine}\n${cellSafetyLine}`;
}

function buildPixelAssetPrompt() {
  const type = $('pixelAssetType')?.value || 'character';
  const actor = isPixelActorAssetType(type);
  const anim = effectivePixelAnimationPreset();
  const style = $('pixelStylePreset')?.value || '32bit_refined';
  const singleMode = ($('pixelDirectionMode')?.value || 'single') === 'single';
  const direction = singleMode ? directionLabel($('pixelTargetDirection')?.value || 'S') : ($('pixelDirection')?.value || 'front');
  const palette = ($('pixelPalette')?.value || 'limited dark game palette').trim();
  const subject = ($('pixelSubject')?.value || 'game character').trim();
  const typeLine = type === 'ui_panel'
    ? 'UI game asset, clean panel parts, reusable game UI component'
    : `${type} game asset`;
  const frameCount = anim === 'ui_static' ? 1 : requestedPixelFrameCount();
  const animLine = {
    idle: `idle animation, ${frameCount}-frame subtle breathing loop, evenly spaced sprite sheet cells`,
    walk4: `walk cycle, ${frameCount}-frame walking animation, idle -> stepA -> idle -> stepB, real alternating legs and arms, evenly spaced sprite sheet cells`,
    walk6: `walk cycle, ${frameCount}-frame walking animation, idle -> stepA -> idle -> stepB, real alternating legs and arms, evenly spaced sprite sheet cells`,
    attack: `attack animation, ${frameCount} frames, readable anticipation/impact/recovery, evenly spaced sprite sheet cells`,
    jump: `jump animation, ${frameCount} frames, readable crouch/takeoff/air/landing beats, evenly spaced sprite sheet cells`,
    cast: `cast animation, ${frameCount} frames, gather/release/recovery beats, evenly spaced sprite sheet cells`,
    hurt: `hurt animation, ${frameCount} frames, impact recoil and recovery, evenly spaced sprite sheet cells`,
    death: `death animation, ${frameCount} frames, collapse/down/still beats, evenly spaced sprite sheet cells`,
    ui_static: `${type} static single asset, no animation frames, crisp reusable game component`,
  }[anim] || `${frameCount}-frame animation frames`;
  const styleLine = `${style.replaceAll('_', ' ')}, refined pixel art, not chunky NES, clean silhouette, game-ready production quality`;
  const directionalContract = actor ? buildDirectionalSpriteSheetContract(anim) : 'Static asset contract: exactly one isolated reusable game asset, no animation, no direction sheet, no alternate poses.';
  const outputLine = actor
    ? 'Output: pixel-art sprite sheet, transparent background, isolated asset, centered, consistent scale, clean alpha edges, no text, no watermark, no logo, no mockup frame.'
    : 'Output: single transparent PNG-style pixel asset, centered, clean alpha edges, no sprite sheet, no text, no watermark, no logo, no mockup frame.';
  return `${subject}\n${typeLine}\n${animLine}\n${directionalContract}\n${actor ? `Direction hint: ${direction}` : 'Direction hint: not applicable for this asset type.'}\nPalette: ${palette}\nStyle: ${styleLine}\n${outputLine}`;
}

function syncPixelAssetPrompt() {
  // Pixel generator relies on background_mode: 'chroma_green' via generateBtn for transparent-friendly extraction.
  const prompt = buildPixelAssetPrompt();
  if ($('aiPrompt')) $('aiPrompt').value = prompt;
  if ($('aiPreset')) $('aiPreset').value = $('pixelAssetType')?.value === 'ui_panel' ? 'ui' : 'pixel';
  if ($('aiAspect')) $('aiAspect').value = 'square';
  setStatus('도트 에셋 프롬프트 조립 완료.');
  return prompt;
}

function pixelPresetFrameCount() {
  const anim = effectivePixelAnimationPreset();
  if (anim === 'ui_static') return 1;
  return requestedPixelFrameCount();
}

function imageCanvasBounds(img) {
  if (!img) return null;
  const rect = img.getBoundingRect ? img.getBoundingRect(true, true) : null;
  if (rect && Number.isFinite(rect.width) && Number.isFinite(rect.height)) {
    return {
      left: Math.round(rect.left || 0),
      top: Math.round(rect.top || 0),
      w: Math.max(1, Math.round(rect.width)),
      h: Math.max(1, Math.round(rect.height)),
    };
  }
  return {
    left: Math.round(img.left || 0),
    top: Math.round(img.top || 0),
    w: Math.max(1, Math.round(img.getScaledWidth ? img.getScaledWidth() : ((img.width || 0) * (img.scaleX || 1)))),
    h: Math.max(1, Math.round(img.getScaledHeight ? img.getScaledHeight() : ((img.height || 0) * (img.scaleY || 1)))),
  };
}

function imageDisplayedSize(img) {
  const bounds = imageCanvasBounds(img);
  return bounds ? { w: bounds.w, h: bounds.h } : null;
}

function updateGridCellSizeFromSelectedLayer({ renderExisting = false } = {}) {
  const target = activeSpriteTarget();
  const bounds = imageCanvasBounds(target);
  if (!target || !bounds) return null;
  const cols = Math.max(1, +($('gridCols')?.value || 1));
  const rows = Math.max(1, +($('gridRows')?.value || 1));
  const cellW = Math.max(1, Math.floor(bounds.w / cols));
  const cellH = Math.max(1, Math.floor(bounds.h / rows));
  if ($('gridCellW')) $('gridCellW').value = String(cellW);
  if ($('gridCellH')) $('gridCellH').value = String(cellH);
  if ($('gridGapX')) $('gridGapX').value = '0';
  if ($('gridGapY')) $('gridGapY').value = '0';
  if (renderExisting && spriteSlices.some(s => s.grid)) {
    spriteSlices = buildGridSpriteSlices();
    selectedSpriteSliceId = spriteSlices[0]?.id || null;
    renderSpriteGuides();
  }
  spriteSummary(`그리드 셀 자동 계산 · 이미지 ${bounds.w}×${bounds.h} / ${cols}×${rows} → 셀 ${cellW}×${cellH}`);
  return { cols, rows, cellW, cellH, bounds };
}

function applyPixelWorkflowGridDefaults(targetImg = null) {
  const frames = pixelPresetFrameCount();
  const dirs = directionLabelsForMode();
  const rows = Math.max(1, dirs.length);
  const img = targetImg || activeSpriteTarget() || selectedLayerObject();
  const size = img?.type === 'image' ? imageDisplayedSize(img) : null;
  const frameW = size ? Math.max(1, Math.round(size.w / frames)) : Math.max(1, +($('pixelFrameW')?.value || 32));
  const frameH = size ? Math.max(1, Math.round(size.h / rows)) : Math.max(1, +($('pixelFrameH')?.value || 32));
  if ($('gridCols')) $('gridCols').value = String(frames);
  if ($('gridRows')) $('gridRows').value = String(rows);
  if ($('gridCellW')) $('gridCellW').value = String(frameW);
  if ($('gridCellH')) $('gridCellH').value = String(frameH);
  if ($('pixelFrameW')) $('pixelFrameW').value = String(frameW);
  if ($('pixelFrameH')) $('pixelFrameH').value = String(frameH);
  if ($('gridGapX')) $('gridGapX').value = '0';
  if ($('gridGapY')) $('gridGapY').value = '0';
  if ($('animFrameCount')) $('animFrameCount').value = String(frames);
  if ($('animFps')) $('animFps').value = $('pixelAnimationPreset')?.value?.startsWith('walk') ? '10' : '8';
  return { frames, rows, frameW, frameH, autoSized: !!size };
}

function recordPixelAssetResult(url, label = 'generated') {
  const slots = $('pixelResultSlots');
  if (!slots || !url) return;
  const card = document.createElement('div');
  card.className = 'pixel-result-slot filled';
  const anim = effectivePixelAnimationPreset();
  const type = $('pixelAssetType')?.value || 'character';
  card.innerHTML = `<img alt="pixel asset result" src="${url}"><span>${type} · ${anim} · ${label}</span>`;
  slots.prepend(card);
  while (slots.children.length > 6) slots.removeChild(slots.lastElementChild);
}

function withCacheBust(url) {
  if (!url) return url;
  if (url.startsWith('data:') || url.startsWith('blob:')) return url;
  return `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`;
}

function canvasJsonSnapshot() {
  const exportFlags = canvas.getObjects().map(o => ({ obj: o, id: o.id, excludeFromExport: o.excludeFromExport }));
  const flagsById = new Map(exportFlags.map(({ id, excludeFromExport }) => [id, excludeFromExport]));
  exportFlags.forEach(({ obj }) => { obj.excludeFromExport = false; });
  try {
    const json = canvas.toDatalessJSON(SERIALIZED_PROPS);
    (json.objects || []).forEach(o => {
      if (flagsById.has(o.id)) o.excludeFromExport = flagsById.get(o.id);
    });
    return json;
  } finally {
    exportFlags.forEach(({ obj, excludeFromExport }) => { obj.excludeFromExport = excludeFromExport; });
  }
}

function historyJson() {
  return JSON.stringify(canvasJsonSnapshot());
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

function parseCanvasJson(jsonOrString) {
  if (!jsonOrString) return null;
  return typeof jsonOrString === 'string' ? JSON.parse(jsonOrString) : jsonOrString;
}

function projectModulesSkeleton() {
  return {
    sprite: { sheets: [], extractions: [], animations: [] },
    ui: { components: [], themes: [], nineSlice: [] },
    map: { tilesets: [], tilemaps: [], collision: [], layers: [] },
  };
}

function currentEditorState() {
  return {
    selectedLayerId,
    activeDrawingLayerId,
    currentTool,
    currentDrawTool,
    canvasSize: { width: canvas.width, height: canvas.height },
    background: canvas.backgroundColor || null,
    checkerboard: $('canvasShell')?.classList.contains('checker') || false,
    view: { scale: viewScale, pan: { ...canvasPanOffset } },
    mask: { drawMode: maskDrawMode, regionSelectionMode },
  };
}

function applyEditorState(state = {}) {
  selectedLayerId = state.selectedLayerId || null;
  activeDrawingLayerId = state.activeDrawingLayerId || activeDrawingLayerId;
  if (state.canvasSize?.width && state.canvasSize?.height) setCanvasSize(+state.canvasSize.width, +state.canvasSize.height);
  if ('background' in state) canvas.backgroundColor = state.background || null;
  if ($('canvasBg') && state.background) $('canvasBg').value = state.background;
  $('canvasShell')?.classList.toggle('checker', !!state.checkerboard);
  if (state.mask?.drawMode) maskDrawMode = state.mask.drawMode;
  if (state.mask?.regionSelectionMode) regionSelectionMode = state.mask.regionSelectionMode;
  if ($('regionMode') && state.mask?.regionSelectionMode) $('regionMode').value = state.mask.regionSelectionMode;
  if (state.view?.pan) canvasPanOffset = { x: +state.view.pan.x || 0, y: +state.view.pan.y || 0 };
  if (state.view?.scale) viewScale = clamp(+state.view.scale || 1, 0.1, 6);
  updateCanvasTransform();
}

async function srcToDataUrl(src) {
  if (!src) throw new Error('empty image src');
  if (src.startsWith('data:image/')) return src;
  const res = await fetch(src);
  if (!res.ok) throw new Error(`image fetch failed: ${res.status}`);
  const blob = await res.blob();
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error('image read failed'));
    reader.readAsDataURL(blob);
  });
}

async function imageObjectDataUrl(obj) {
  const src = obj?.getSrc?.() || obj?.src || obj?._originalSrc || '';
  if (src.startsWith('data:image/')) return src;
  const el = obj?._element || obj?._originalElement;
  if (!el) return srcToDataUrl(src);
  const w = el.naturalWidth || el.videoWidth || el.width || obj.width || 1;
  const h = el.naturalHeight || el.videoHeight || el.height || obj.height || 1;
  const tmp = document.createElement('canvas');
  tmp.width = w; tmp.height = h;
  tmp.getContext('2d').drawImage(el, 0, 0, w, h);
  return tmp.toDataURL('image/png');
}

async function collectEmbeddedImageAssets(canvasJsons = []) {
  const assets = [];
  const byObjectKey = new Map();
  const bySrc = new Map();
  const registerAsset = (asset, keys = [], src = '') => {
    if (!asset) return asset;
    if (!assets.some(a => a.id === asset.id)) assets.push(asset);
    keys.filter(Boolean).forEach(k => byObjectKey.set(k, asset));
    if (src) bySrc.set(src.split('?')[0], asset);
    return asset;
  };
  const imageObjects = canvas.getObjects().filter(o => o.type === 'image');
  for (const obj of imageObjects) {
    const src = obj.getSrc?.() || obj.src || obj._originalSrc || '';
    try {
      const dataUrl = await imageObjectDataUrl(obj);
      const asset = {
        id: obj._assetId || uid('asset_img'),
        name: nameOf(obj),
        source: src.startsWith('/assets/generated') ? 'generated' : src.startsWith('/assets/processed') ? 'processed' : 'embedded',
        mime: (dataUrl.match(/^data:([^;]+);/) || [])[1] || 'image/png',
        dataUrl,
        width: obj.width || obj._element?.naturalWidth || null,
        height: obj.height || obj._element?.naturalHeight || null,
      };
      obj._assetId = asset.id;
      registerAsset(asset, [obj.id, obj.layerId, obj._assetId], src);
    } catch (err) {
      console.warn('Project image embed failed', err);
    }
  }
  for (const json of canvasJsons) {
    for (const o of (json?.objects || [])) {
      if (o.type !== 'image') continue;
      const src = o.src || o._originalSrc || '';
      const cleanSrc = src.split('?')[0];
      if (!src || bySrc.has(cleanSrc) || byObjectKey.has(o.id) || byObjectKey.has(o.layerId) || byObjectKey.has(o._assetId)) continue;
      try {
        const dataUrl = await srcToDataUrl(src);
        const asset = {
          id: o._assetId || uid('asset_img'),
          name: o.name || 'Embedded image',
          source: src.startsWith('/assets/generated') ? 'generated' : src.startsWith('/assets/processed') ? 'processed' : 'embedded',
          mime: (dataUrl.match(/^data:([^;]+);/) || [])[1] || 'image/png',
          dataUrl,
          width: o.width || null,
          height: o.height || null,
        };
        registerAsset(asset, [o.id, o.layerId, o._assetId], src);
      } catch (err) {
        console.warn('Project history image embed failed', err);
      }
    }
  }
  const embedJson = (json) => {
    (json?.objects || []).forEach(o => {
      if (o.type !== 'image') return;
      const cleanSrc = (o.src || '').split('?')[0];
      const asset = byObjectKey.get(o.id) || byObjectKey.get(o.layerId) || byObjectKey.get(o._assetId) || bySrc.get(cleanSrc);
      if (!asset) return;
      o._assetId = asset.id;
      o._assetName = asset.name;
      o.src = asset.dataUrl;
      if (o._originalSrc) o._originalSrc = asset.dataUrl;
    });
  };
  canvasJsons.forEach(embedJson);
  return assets;
}

async function buildProjectV2() {
  const canvasJson = canvasJsonSnapshot();
  const historyEntries = history.map((entry, idx) => ({
    label: entry.label || `History ${idx + 1}`,
    at: entry.at || null,
    canvasJson: parseCanvasJson(entry.json),
  }));
  const jsons = [canvasJson, ...historyEntries.map(e => e.canvasJson).filter(Boolean)];
  const assets = await collectEmbeddedImageAssets(jsons);
  const now = new Date().toISOString();
  return {
    app: 'asset-studio-local',
    version: 2,
    kind: 'project',
    createdAt: now,
    updatedAt: now,
    document: {
      name: 'Untitled Project',
      mode: 'image-editor',
      canvas: {
        width: canvas.width,
        height: canvas.height,
        background: canvas.backgroundColor || null,
        checkerboard: $('canvasShell')?.classList.contains('checker') || false,
      },
    },
    assets: { images: assets },
    editor: {
      canvasJson,
      history: historyEntries,
      historyIndex,
      state: currentEditorState(),
    },
    modules: projectModulesSkeleton(),
  };
}

function finishProjectLoad(message) {
  ensureDefaultDrawingLayer();
  refreshMaskStateFromCanvas();
  syncProps();
  renderLayers();
  renderHistory();
  refreshAiChatState();
  canvas.renderAll();
  setStatus(message);
}

function loadLegacyProjectV1(project) {
  suppressHistory = true;
  canvas.loadFromJSON(project, () => {
    suppressHistory = false;
    history = [];
    historyIndex = -1;
    saveHistory('불러온 v1 프로젝트');
    finishProjectLoad('Legacy v1 프로젝트를 불러왔습니다.');
  });
}

function loadProjectV2(project) {
  const editor = project.editor || {};
  const entries = Array.isArray(editor.history) ? editor.history : [];
  const idx = clamp(Number.isInteger(editor.historyIndex) ? editor.historyIndex : entries.length - 1, 0, Math.max(0, entries.length - 1));
  const targetJson = entries[idx]?.canvasJson || editor.canvasJson;
  if (!targetJson) throw new Error('프로젝트에 canvasJson이 없습니다.');
  suppressHistory = true;
  canvas.loadFromJSON(targetJson, () => {
    history = entries.map((entry, i) => ({
      json: JSON.stringify(entry.canvasJson || editor.canvasJson || targetJson),
      label: entry.label || `History ${i + 1}`,
      at: entry.at || new Date().toISOString(),
    }));
    if (!history.length) history = [{ json: JSON.stringify(targetJson), label: '불러온 프로젝트', at: new Date().toISOString() }];
    historyIndex = clamp(idx, 0, history.length - 1);
    applyEditorState(editor.state || {});
    suppressHistory = false;
    finishProjectLoad(`Project v2 불러오기 완료 · 히스토리 ${historyIndex + 1}/${history.length}`);
  });
}

function loadProjectFileObject(project) {
  if (project?.app === 'asset-studio-local' && project.version === 2) return loadProjectV2(project);
  return loadLegacyProjectV1(project);
}

function formatBytes(bytes) {
  const n = Number(bytes) || 0;
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)}MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${n}B`;
}

function projectSizeWarning(bytes) {
  if (bytes >= 50 * 1024 * 1024) return '매우 큰 프로젝트입니다. 브라우저 저장/불러오기가 느릴 수 있어 ZIP/압축 포맷 전환이 필요합니다.';
  if (bytes >= 20 * 1024 * 1024) return '프로젝트 파일이 큽니다. 이미지/히스토리가 많으면 다음 단계에서 압축/ZIP 개선이 필요합니다.';
  return '';
}

function projectSummary(project, bytes = 0) {
  const images = project?.assets?.images?.length || 0;
  const hist = project?.editor?.history?.length || 0;
  const objects = project?.editor?.canvasJson?.objects?.length || 0;
  const size = bytes ? ` · ${formatBytes(bytes)}` : '';
  return `이미지 ${images}개 · 레이어/오브젝트 ${objects}개 · 히스토리 ${hist}개${size}`;
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
  return new Promise((resolve, reject) => {
    fabric.Image.fromURL(url, (img) => {
      try {
        img._originalSrc = url;
        fitToCanvasObject(img);
        addToCanvas(img, label);
        setStatus(`${label} added to canvas.`);
        resolve(img);
      } catch (err) {
        reject(err);
      }
    }, { crossOrigin: 'anonymous' });
  });
}

function addPatchImageUrl(url, bbox, label='AI Patch') {
  return new Promise((resolve, reject) => {
    fabric.Image.fromURL(url, (img) => {
      try {
        img._originalSrc = url;
        const box = bbox || { x: 0, y: 0, width: img.width, height: img.height };
        const pxW = Number(bbox?.patch_width || bbox?.width || img.width);
        const pxH = Number(bbox?.patch_height || bbox?.height || img.height);
        const exactPatch = Math.abs(pxW - img.width) <= 1 && Math.abs(pxH - img.height) <= 1;
        img.set({
          left: box.x,
          top: box.y,
          originX: 'left',
          originY: 'top',
          scaleX: exactPatch ? 1 : box.width / img.width,
          scaleY: exactPatch ? 1 : box.height / img.height,
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

function spriteSummary(msg) {
  if ($('spriteExtractSummary')) $('spriteExtractSummary').textContent = msg;
}

function removeSpriteGuideObjects() {
  canvas.getObjects().filter(o => o.maskRole === 'sprite-guide').forEach(o => canvas.remove(o));
  canvas.renderAll();
}

function clearSpriteGuides() {
  removeSpriteGuideObjects();
  spriteSlices = [];
  selectedSpriteSliceId = null;
  spriteSourceLayerId = null;
  spriteSummary('탐지 박스 없음');
  canvas.renderAll();
}

function activeSpriteTarget() {
  const target = selectedLayerObject();
  if (target && target.type === 'image' && !target.isDrawingLayer && !target.excludeFromLayers) return target;
  const source = objectByLayerId(spriteSourceLayerId);
  if (source && source.type === 'image' && !source.isDrawingLayer && !source.excludeFromLayers) return source;
  return null;
}

function extractImageDataComponents(imgData, minArea = 48, options = {}) {
  const { width, height, data } = imgData;
  const seen = new Uint8Array(width * height);
  const slices = [];
  const bgColors = options.backgroundColors || [];
  const bgTolerance = Math.max(0, options.backgroundTolerance ?? 34);
  const pxOffset = (x, y) => (y * width + x) * 4;
  const alphaAt = (x, y) => data[pxOffset(x, y) + 3];
  const colorNear = (x, y, c) => {
    const i = pxOffset(x, y);
    return Math.abs(data[i] - c.r) <= bgTolerance
      && Math.abs(data[i + 1] - c.g) <= bgTolerance
      && Math.abs(data[i + 2] - c.b) <= bgTolerance
      && Math.abs(data[i + 3] - c.a) <= Math.max(bgTolerance, 48);
  };
  const isBackground = (x, y) => alphaAt(x, y) <= 12 || bgColors.some(c => c.a > 12 && colorNear(x, y, c));
  const isSolid = (x, y) => !isBackground(x, y);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const start = y * width + x;
      if (seen[start] || !isSolid(x, y)) { seen[start] = 1; continue; }
      const q = [[x, y]];
      seen[start] = 1;
      let minX = x, maxX = x, minY = y, maxY = y, area = 0;
      for (let qi = 0; qi < q.length; qi++) {
        const [cx, cy] = q[qi];
        area++;
        if (cx < minX) minX = cx; if (cx > maxX) maxX = cx;
        if (cy < minY) minY = cy; if (cy > maxY) maxY = cy;
        for (const [nx, ny] of [[cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]]) {
          if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue;
          const idx = ny * width + nx;
          if (seen[idx]) continue;
          seen[idx] = 1;
          if (isSolid(nx, ny)) q.push([nx, ny]);
        }
      }
      const w = maxX - minX + 1;
      const h = maxY - minY + 1;
      if (area >= minArea && w >= 2 && h >= 2) {
        slices.push({ id: uid('sprite'), x: minX, y: minY, width: w, height: h, area });
      }
    }
  }
  return slices.sort((a, b) => (a.y - b.y) || (a.x - b.x));
}

async function detectSpriteSlices() {
  const target = activeSpriteTarget();
  if (!target) { spriteSummary('이미지 레이어를 선택해야 합니다.'); setStatus('스프라이트 추출: 이미지 레이어 선택 필요'); return []; }
  spriteSourceLayerId = layerKey(target);
  clearSpriteGuides();
  spriteSourceLayerId = layerKey(target);
  const bounds = imageCanvasBounds(target);
  if (!bounds) { spriteSummary('이미지 레이어 크기 확인 실패'); setStatus('스프라이트 추출: 이미지 레이어 크기 확인 실패'); return []; }

  // Root cause: full-canvas detection let the selected image's canvas position and faint
  // residual backgrounds become part of the slice model. Detect in selected-layer-local
  // pixels only: x=0,y=0 is always the image layer's own top-left.
  const dataUrl = await imageObjectDataUrl(target);
  const img = await loadHtmlImage(dataUrl);
  const el = document.createElement('canvas');
  el.width = bounds.w; el.height = bounds.h;
  const ctx = el.getContext('2d', { willReadFrequently: true });
  ctx.clearRect(0, 0, el.width, el.height);
  ctx.drawImage(img, 0, 0, el.width, el.height);
  const minArea = Math.max(1, +($('spriteMinArea')?.value || 48));
  const imageData = ctx.getImageData(0, 0, el.width, el.height);
  const sampleColor = (x, y) => {
    const sx = clamp(Math.round(x), 0, el.width - 1);
    const sy = clamp(Math.round(y), 0, el.height - 1);
    const i = (sy * el.width + sx) * 4;
    const d = imageData.data;
    return { r: d[i], g: d[i + 1], b: d[i + 2], a: d[i + 3] };
  };
  const inset = Math.min(2, Math.floor(Math.min(el.width, el.height) / 8));
  const bgColors = [
    sampleColor(inset, inset),
    sampleColor(el.width - 1 - inset, inset),
    sampleColor(inset, el.height - 1 - inset),
    sampleColor(el.width - 1 - inset, el.height - 1 - inset),
  ];
  spriteSlices = extractImageDataComponents(imageData, minArea, { backgroundColors: bgColors, backgroundTolerance: 42 })
    .map(slice => ({ ...slice, x: Math.round(slice.x), y: Math.round(slice.y) }))
    .filter(slice => slice.x + slice.width > 0 && slice.y + slice.height > 0 && slice.x < bounds.w && slice.y < bounds.h);

  const cols = Math.max(1, +($('gridCols')?.value || 1));
  const rows = Math.max(1, +($('gridRows')?.value || 1));
  const gridExpected = cols * rows;
  const fallbackToGrid = (reason) => {
    updateGridCellSizeFromSelectedLayer();
    spriteSlices = buildGridSpriteSlices();
    selectedSpriteSliceId = spriteSlices[0]?.id || null;
    renderSpriteGuides();
    const msg = `${reason} → 현재 그리드 ${cols}×${rows} 기준 ${spriteSlices.length}개 프레임으로 분할`;
    spriteSummary(msg); setStatus(`스프라이트 시트 추출: ${msg}`);
    return spriteSlices;
  };
  const giant = spriteSlices.length === 1
    && spriteSlices[0].width >= bounds.w * 0.8
    && spriteSlices[0].height >= bounds.h * 0.8
    && gridExpected > 1;
  if (giant) return fallbackToGrid('큰 배경 덩어리 감지');

  const configuredAsFrameSheet = gridExpected > 1 && (rows === 1 || +($('animFrameCount')?.value || 0) === gridExpected);
  if (configuredAsFrameSheet && spriteSlices.length !== gridExpected) {
    return fallbackToGrid(`프레임 수 불일치 감지(${spriteSlices.length}개 탐지)`);
  }

  selectedSpriteSliceId = spriteSlices[0]?.id || null;
  renderSpriteGuides();
  const msg = spriteSlices.length ? `${spriteSlices.length}개 조각 탐지 · 첫 조각 선택됨` : '조각 없음 · 배경 제거/투명 PNG 상태를 확인하세요';
  spriteSummary(msg); setStatus(`스프라이트 시트 추출: ${msg}`);
  return spriteSlices;
}

function updateSpriteGuideStyles() {
  canvas.getObjects().filter(o => o.maskRole === 'sprite-guide').forEach((guide) => {
    const selected = guide.spriteSliceId === selectedSpriteSliceId;
    guide.set({
      stroke: selected ? '#22c55e' : '#f59e0b',
      strokeWidth: selected ? 3 : 2,
      strokeDashArray: selected ? null : [6, 4],
    });
  });
  canvas.requestRenderAll();
}

function spriteTargetOrigin() {
  const target = activeSpriteTarget();
  const bounds = imageCanvasBounds(target);
  if (!target || !bounds) return null;
  return bounds;
}

function spriteSliceCanvasBox(slice) {
  const origin = spriteTargetOrigin();
  if (!origin || !slice) return null;
  return {
    x: origin.left + Math.round(slice.x || 0),
    y: origin.top + Math.round(slice.y || 0),
    width: Math.round(slice.width || 1),
    height: Math.round(slice.height || 1),
    origin,
  };
}

function syncSpriteSliceFromGuide(guide) {
  const slice = spriteSlices.find(s => s.id === guide.spriteSliceId);
  if (!slice) return null;
  const origin = spriteTargetOrigin() || { left: 0, top: 0 };
  slice.x = Math.round((guide.left || 0) - origin.left);
  slice.y = Math.round((guide.top || 0) - origin.top);
  slice.width = Math.round((guide.width || slice.width) * (guide.scaleX || 1));
  slice.height = Math.round((guide.height || slice.height) * (guide.scaleY || 1));
  slice.area = slice.width * slice.height;
  guide.set({ width: slice.width, height: slice.height, scaleX: 1, scaleY: 1 });
  guide.setCoords();
  return slice;
}

function renderSpriteGuides() {
  removeSpriteGuideObjects();
  const origin = spriteTargetOrigin() || { left: 0, top: 0 };
  spriteSlices.forEach((slice, idx) => {
    const selected = slice.id === selectedSpriteSliceId;
    const rect = new fabric.Rect({
      left: origin.left + slice.x,
      top: origin.top + slice.y,
      width: slice.width,
      height: slice.height,
      fill: 'rgba(0,0,0,0)',
      stroke: selected ? '#22c55e' : '#f59e0b',
      strokeWidth: selected ? 3 : 2,
      strokeDashArray: selected ? null : [6, 4],
      selectable: true,
      evented: true,
      hasControls: true,
      hasRotatingPoint: false,
      lockRotation: true,
      lockScalingFlip: true,
      lockMovementX: false,
      lockMovementY: false,
      name: `Sprite Slice ${idx + 1}`,
      excludeFromLayers: true,
      excludeFromExport: true,
      isMaskOverlay: true,
      maskRole: 'sprite-guide',
      spriteSliceId: slice.id,
    });
    rect.on('mousedown', () => {
      selectedSpriteSliceId = slice.id;
      updateSpriteGuideStyles();
      spriteSummary(`선택 조각 ${idx + 1}/${spriteSlices.length} · ${slice.width}×${slice.height} · area ${slice.area}`);
    });
    rect.on('moving', () => {
      const updated = syncSpriteSliceFromGuide(rect);
      if (updated) spriteSummary(`조각 위치 이동 · rel ${updated.x},${updated.y} · ${updated.width}×${updated.height}`);
    });
    rect.on('scaling', () => {
      const updated = syncSpriteSliceFromGuide(rect);
      if (updated) spriteSummary(`조각 크기 조절 · rel ${updated.x},${updated.y} · ${updated.width}×${updated.height}`);
    });
    rect.on('modified', () => {
      const updated = syncSpriteSliceFromGuide(rect);
      if (updated) spriteSummary(`조각 박스 수정 완료 · rel ${updated.x},${updated.y} · ${updated.width}×${updated.height}`);
    });
    canvas.add(rect);
  });
  canvas.renderAll();
}

function selectedSpriteSlice() {
  return spriteSlices.find(s => s.id === selectedSpriteSliceId) || spriteSlices[0] || null;
}

async function spriteSliceDataUrl(slice = selectedSpriteSlice()) {
  const target = activeSpriteTarget();
  if (!target) throw new Error('이미지 레이어 선택 필요');
  if (!slice) throw new Error('탐지된 조각 없음');
  const bounds = imageCanvasBounds(target);
  if (!bounds) throw new Error('선택 레이어 크기 확인 실패');

  // IMPORTANT: spriteSlices are selected-image-local coordinates, not canvas
  // coordinates. Crop from the source image buffer directly. Cropping from a
  // full-canvas render makes any frame outside the visible 1024 canvas export
  // as a fully transparent PNG (the black_orc 4-frame sheet repro).
  const dataUrl = await imageObjectDataUrl(target);
  const img = await loadHtmlImage(dataUrl);
  const naturalW = img.naturalWidth || img.width || bounds.w || 1;
  const naturalH = img.naturalHeight || img.height || bounds.h || 1;
  const scaleX = naturalW / Math.max(1, bounds.w);
  const scaleY = naturalH / Math.max(1, bounds.h);
  const sx = Math.max(0, Math.round((slice.x || 0) * scaleX));
  const sy = Math.max(0, Math.round((slice.y || 0) * scaleY));
  const sw = Math.max(1, Math.min(naturalW - sx, Math.round((slice.width || 1) * scaleX)));
  const sh = Math.max(1, Math.min(naturalH - sy, Math.round((slice.height || 1) * scaleY)));

  const el = document.createElement('canvas');
  el.width = Math.max(1, Math.round(slice.width || sw));
  el.height = Math.max(1, Math.round(slice.height || sh));
  const ctx = el.getContext('2d');
  ctx.clearRect(0, 0, el.width, el.height);
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, el.width, el.height);
  return el.toDataURL('image/png');
}

async function extractSpriteSliceToLayer() {
  try {
    const slice = selectedSpriteSlice();
    const url = await spriteSliceDataUrl(slice);
    const box = spriteSliceCanvasBox(slice);
    const layer = await addPatchImageUrl(url, { x: box?.x ?? slice.x, y: box?.y ?? slice.y, width: slice.width, height: slice.height, patch_width: slice.width, patch_height: slice.height }, `Sprite Slice ${spriteSlices.indexOf(slice) + 1}`);
    layer._originalSrc = url;
    spriteSummary(`조각 레이어 생성 · ${slice.width}×${slice.height}`);
  } catch (err) {
    console.error(err); alert(`조각 레이어 추출 실패: ${err.message}`); setStatus(`조각 레이어 추출 실패: ${err.message}`);
  }
}

async function exportSpriteSlicePng() {
  try {
    const slice = selectedSpriteSlice();
    const url = await spriteSliceDataUrl(slice);
    downloadDataUrl(url, `sprite-slice-${String(spriteSlices.indexOf(slice) + 1).padStart(2, '0')}.png`);
    spriteSummary(`조각 PNG 내보내기 · ${slice.width}×${slice.height}`);
  } catch (err) {
    console.error(err); alert(`조각 PNG 추출 실패: ${err.message}`); setStatus(`조각 PNG 추출 실패: ${err.message}`);
  }
}

async function exportAllSpriteSlicesZip() {
  try {
    if (!activeSpriteTarget()) throw new Error('이미지 레이어 선택 필요');
    if (!spriteSlices.length) await detectSpriteSlices();
    if (!spriteSlices.length) throw new Error('탐지된 조각 없음');
    const encoder = new TextEncoder();
    const files = [];
    const manifest = {
      sourceLayer: activeSpriteTarget()?.name || 'selected image',
      count: spriteSlices.length,
      slices: [],
    };
    for (let i = 0; i < spriteSlices.length; i++) {
      const slice = spriteSlices[i];
      const filename = `sprite-${String(i + 1).padStart(3, '0')}.png`; // sprite-001.png
      const url = await spriteSliceDataUrl(slice);
      files.push({ name: filename, bytes: dataUrlToBytes(url) });
      const box = spriteSliceCanvasBox(slice) || { x: slice.x, y: slice.y };
      manifest.slices.push({
        file: filename,
        index: i + 1,
        x: slice.x,
        y: slice.y,
        canvasX: box.x,
        canvasY: box.y,
        width: slice.width,
        height: slice.height,
        area: slice.area,
      });
    }
    files.push({ name: 'manifest.json', bytes: encoder.encode(JSON.stringify(manifest, null, 2)) });
    const zipBlob = buildStoredZip(files);
    downloadBlob(zipBlob, 'sprite-slices.zip');
    spriteSummary(`전체 조각 ZIP 내보내기 · ${spriteSlices.length}개 + manifest.json`);
    setStatus(`스프라이트 ZIP 내보내기 완료: ${spriteSlices.length}개`);
  } catch (err) {
    console.error(err); alert(`전체 조각 ZIP 추출 실패: ${err.message}`); setStatus(`전체 조각 ZIP 추출 실패: ${err.message}`);
  }
}

function buildGridSpriteSlices() {
  const target = activeSpriteTarget();
  if (!target) throw new Error('이미지 레이어 선택 필요');
  const cols = Math.max(1, +($('gridCols')?.value || 1));
  const rows = Math.max(1, +($('gridRows')?.value || 1));
  const cellW = Math.max(1, +($('gridCellW')?.value || 32));
  const cellH = Math.max(1, +($('gridCellH')?.value || 32));
  const gapX = Math.max(0, +($('gridGapX')?.value || 0));
  const gapY = Math.max(0, +($('gridGapY')?.value || 0));
  const slices = [];
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      slices.push({
        id: uid('grid-sprite'),
        x: col * (cellW + gapX),
        y: row * (cellH + gapY),
        width: cellW,
        height: cellH,
        area: cellW * cellH,
        row,
        col,
        grid: true,
      });
    }
  }
  return slices;
}

function currentGridSpriteSlices() {
  if (spriteSlices.some(s => s.grid)) return spriteSlices;
  return buildGridSpriteSlices();
}

function currentAnimationSpriteSlices(frameCount = Math.max(1, +($('animFrameCount')?.value || 4))) {
  // User flow: image → 자동 조각 찾기 → 애니메이션 재생.
  // In that flow the detected boxes ARE the frames. Do not rebuild from stale
  // gridCellW/H defaults (32×32), or the preview crops blank top-left pixels.
  if (spriteSlices.length) return spriteSlices.slice(0, frameCount);
  return buildGridSpriteSlices().slice(0, frameCount);
}

async function buildAnimationFramesFromGrid() {
  if (!activeSpriteTarget()) throw new Error('이미지 레이어 선택 필요');
  const frameCount = Math.max(1, +($('animFrameCount')?.value || 4));
  const frames = currentAnimationSpriteSlices(frameCount);
  if (!frames.length) throw new Error('프레임 조각 없음 · 먼저 자동 조각 찾기 또는 그리드 미리보기를 실행하세요');
  const urls = [];
  for (const slice of frames) {
    const dataUrl = await spriteSliceDataUrl(slice);
    const img = await loadHtmlImage(dataUrl);
    const frameCanvas = document.createElement('canvas');
    frameCanvas.width = slice.width;
    frameCanvas.height = slice.height;
    const ctx = frameCanvas.getContext('2d');
    ctx.clearRect(0, 0, frameCanvas.width, frameCanvas.height);
    ctx.drawImage(img, 0, 0);
    urls.push(frameCanvas.toDataURL('image/png'));
  }
  return urls;
}

function animationPreviewStages() {
  return ['animationPreviewStage']
    .map(id => $(id))
    .filter(Boolean);
}

function animationFrameStrips() {
  return ['animationFrameStrip']
    .map(id => $(id))
    .filter(Boolean);
}

function renderAnimationFrameStrip(frames = animationPreviewFrames) {
  const strips = animationFrameStrips();
  if (!strips.length) return;
  strips.forEach(strip => {
    strip.innerHTML = '';
    frames.forEach((url, idx) => {
      const img = document.createElement('img');
      img.src = url;
      img.alt = `animation frame ${idx + 1}`;
      img.dataset.frameIndex = String(idx);
      strip.appendChild(img);
    });
  });
}

function stopAnimationPreview() {
  if (animationPreviewTimer) clearInterval(animationPreviewTimer);
  animationPreviewTimer = null;
  setStatus('애니메이션 미리보기 정지');
}

function playAnimationPreview(frames = animationPreviewFrames) {
  const stages = animationPreviewStages();
  if (!stages.length || !frames.length) return;
  stopAnimationPreview();
  let idx = 0;
  let dir = 1;
  const mode = $('animMode')?.value || 'loop';
  const fps = clamp(+($('animFps')?.value || 8), 1, 30);
  const draw = () => {
    stages.forEach(stage => {
      stage.innerHTML = `<img alt="animation preview frame" src="${frames[idx]}"><span>${idx + 1}/${frames.length} · ${mode}</span>`;
    });
    if (mode === 'pingpong') {
      if (idx >= frames.length - 1) dir = -1;
      if (idx <= 0) dir = 1;
      idx = clamp(idx + dir, 0, frames.length - 1);
    } else {
      idx = (idx + 1) % frames.length;
    }
  };
  draw();
  animationPreviewTimer = setInterval(draw, Math.round(1000 / fps));
}

async function buildAnimationPreview() {
  animationPreviewFrames = await buildAnimationFramesFromGrid();
  renderAnimationFrameStrip(animationPreviewFrames);
  playAnimationPreview(animationPreviewFrames);
  spriteSummary(`애니메이션 미리보기 재생 · ${animationPreviewFrames.length} frames`);
  setStatus(`애니메이션 미리보기: ${animationPreviewFrames.length} frames`);
  return animationPreviewFrames;
}

async function detectGridSpriteSlices() {
  try {
    updateGridCellSizeFromSelectedLayer();
    const target = activeSpriteTarget();
    spriteSlices = buildGridSpriteSlices();
    selectedSpriteSliceId = spriteSlices[0]?.id || null;
    renderSpriteGuides();
    if (target) {
      canvas.setActiveObject(target);
      rememberSelectedLayer(target);
    }
    spriteSummary(`그리드 ${spriteSlices.length}개 미리보기 · ${$('gridCols')?.value || 1}×${$('gridRows')?.value || 1} · 박스는 드래그로 이동/조절 가능`);
    setStatus(`그리드 슬라이스 미리보기: ${spriteSlices.length}개`);
    canvas.requestRenderAll();
    return spriteSlices;
  } catch (err) {
    console.error(err); alert(`그리드 미리보기 실패: ${err.message}`); setStatus(`그리드 미리보기 실패: ${err.message}`);
    return [];
  }
}

async function exportGridSpriteSlicesZip() {
  try {
    if (!activeSpriteTarget()) throw new Error('이미지 레이어 선택 필요');
    let gridSlices = currentGridSpriteSlices();
    spriteSlices = gridSlices;
    if (!selectedSpriteSliceId) selectedSpriteSliceId = spriteSlices[0]?.id || null;
    renderSpriteGuides();
    const encoder = new TextEncoder();
    const files = [];
    const manifest = {
      sourceLayer: activeSpriteTarget()?.name || 'selected image',
      mode: 'grid',
      count: gridSlices.length,
      cols: Math.max(1, +($('gridCols')?.value || 1)),
      rows: Math.max(1, +($('gridRows')?.value || 1)),
      cellWidth: Math.max(1, +($('gridCellW')?.value || 32)),
      cellHeight: Math.max(1, +($('gridCellH')?.value || 32)),
      gapX: Math.max(0, +($('gridGapX')?.value || 0)),
      gapY: Math.max(0, +($('gridGapY')?.value || 0)),
      slices: [],
    };
    for (let i = 0; i < gridSlices.length; i++) {
      const slice = gridSlices[i];
      const filename = `grid-sprite-${String(i + 1).padStart(3, '0')}.png`; // grid-sprite-001.png
      const url = await spriteSliceDataUrl(slice);
      files.push({ name: filename, bytes: dataUrlToBytes(url) });
      const box = spriteSliceCanvasBox(slice) || { x: slice.x, y: slice.y };
      manifest.slices.push({ file: filename, index: i + 1, row: slice.row, col: slice.col, x: slice.x, y: slice.y, canvasX: box.x, canvasY: box.y, width: slice.width, height: slice.height });
    }
    files.push({ name: 'grid-manifest.json', bytes: encoder.encode(JSON.stringify(manifest, null, 2)) });
    const zipBlob = buildStoredZip(files);
    downloadBlob(zipBlob, 'grid-sprite-slices.zip');
    spriteSummary(`그리드 ZIP 내보내기 · ${gridSlices.length}개 + grid-manifest.json`);
    setStatus(`그리드 ZIP 내보내기 완료: ${gridSlices.length}개`);
  } catch (err) {
    console.error(err); alert(`그리드 ZIP 추출 실패: ${err.message}`); setStatus(`그리드 ZIP 추출 실패: ${err.message}`);
  }
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
    }, ['id','name','_originalSrc','_phase4PreservedOriginal','_assetId','_assetName','excludeFromLayers','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId']);
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
  const hasReplacementMask = !!bbox;
  if (!prompt) { alert('새 오브젝트 설명을 입력하세요.'); $('replaceObjectPrompt')?.focus(); return; }
  const btn = $('generateReplacement');
  btn.disabled = true;
  if ($('replaceResult')) $('replaceResult').textContent = hasReplacementMask ? '선택 이미지+마스크를 참고해 오브젝트 치환 중...' : '마스크 없이 새 오브젝트 레이어 생성 중...';
  setStatus(hasReplacementMask ? 'B안: 선택 이미지 crop + 마스크를 AI에 같이 보내 치환 중...' : '새 오브젝트 PNG 생성 중... #00FF00 배경을 강제합니다.');
  try {
    const target = selectedLayerObject();
    if (hasReplacementMask) {
      if (!target || target.type !== 'image' || target.isDrawingLayer || target.excludeFromLayers) {
        const label = target ? `${nameOf(target)} (${target.isDrawingLayer ? 'drawing layer' : target.type})` : '선택 없음';
        throw new Error(`마스크 기반 치환은 이미지 레이어 선택이 필요합니다. 현재 선택: ${label}`);
      }
      const image = await canvasWithOnlyObjectDataUrl(target);
      const mask = await buildMaskDataUrl('edit');
      if (!mask) throw new Error('교체 마스크를 만들 수 없습니다.');
      const res = await fetch('/api/replace-object', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ image, mask, prompt, negative, target_layer_id: layerKey(target) })
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || 'reference object replacement failed');
      const objectUrl = data.url + '?t=' + Date.now();
      addGallery(objectUrl, 'replacement-ref');
      let cleared = false;
      if ($('clearOriginalUnderMask')?.checked) cleared = await createSourceMinusMaskLayer(target, mask);
      const patchBox = { ...data.bbox, patch_width: data.patch_width, patch_height: data.patch_height };
      await addPatchImageUrl(objectUrl, patchBox, `Replacement Ref - ${prompt.slice(0, 28)}`);
      let occluded = false;
      if ($('createOcclusionLayer')?.checked && occlusionMaskOverlays().length) {
        const occMask = await buildMaskDataUrl('occlusion');
        if (occMask) occluded = await createOcclusionLayerFromTarget(target, occMask);
      }
      if ($('replaceResult')) $('replaceResult').textContent = `완료: 선택 이미지/마스크 참고 치환 패치 적용${cleared ? ' + 기존 물체 영역 비움' : ''}${occluded ? ' + 손/앞가림 레이어' : ''} (${data.method}). patch ${data.patch_width || data.bbox.width}×${data.patch_height || data.bbox.height}, bbox ${Math.round(data.bbox.width)}×${Math.round(data.bbox.height)}.`;
      return;
    }

    const contextName = target ? nameOf(target) : 'current canvas';
    const objectPrompt = `${prompt}\n\nGenerate ONLY the replacement/new object as an isolated transparent-friendly game asset. It may later be placed over ${contextName}. Do not include character, hand, body, scene, text, logo, watermark, or full image redraw. Match pixel/game asset style when possible. Negative: ${negative || 'background, character body, text, watermark'}`;
    const gen = await fetch('/api/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ prompt: objectPrompt, preset: 'game', aspect_ratio: 'square', background_mode: 'chroma_green' })
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
        body: JSON.stringify({ image, tolerance: +($('tolerance')?.value || 18), mode: 'chroma_green' })
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
    addImageUrl(objectUrl, `Object - ${prompt.slice(0, 28)}`);
    if ($('replaceResult')) $('replaceResult').textContent = `완료: #00FF00 배경 생성 후 크로마키 제거된 새 오브젝트 레이어를 추가했습니다 (${method}).`;
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

function objectCanvasBounds(obj) {
  if (!obj) return null;
  obj.setCoords?.();
  const rect = obj.getBoundingRect ? obj.getBoundingRect(true, true) : null;
  if (rect && Number.isFinite(rect.left) && Number.isFinite(rect.top)) {
    return {
      left: rect.left || 0,
      top: rect.top || 0,
      width: Math.max(1, rect.width || 1),
      height: Math.max(1, rect.height || 1),
    };
  }
  return {
    left: obj.left || 0,
    top: obj.top || 0,
    width: obj.getScaledWidth ? obj.getScaledWidth() : ((obj.width || 1) * (obj.scaleX || 1)),
    height: obj.getScaledHeight ? obj.getScaledHeight() : ((obj.height || 1) * (obj.scaleY || 1)),
  };
}

function moveObjectBoundingTopLeft(obj, left, top) {
  const bounds = objectCanvasBounds(obj);
  if (!obj || !bounds) return;
  obj.set({
    left: (obj.left || 0) + (left - bounds.left),
    top: (obj.top || 0) + (top - bounds.top),
  });
  obj.setCoords?.();
}

function syncProps() {
  const obj = selectedLayerObject();
  $('selectedName').textContent = obj ? `${nameOf(obj)} (${obj.isDrawingLayer ? 'drawing layer' : obj.type})` : '선택 없음';
  for (const id of ['propX','propY','propW','propH','propRot','propOpacity','textContent']) $(id).value = '';
  if (!obj || obj.isDrawingLayer) return;
  const bounds = objectCanvasBounds(obj);
  $('propX').value = Math.round(bounds.left);
  $('propY').value = Math.round(bounds.top);
  $('propW').value = Math.round(bounds.width);
  $('propH').value = Math.round(bounds.height);
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

function fitView(showStatus = true) {
  const workspace = $('workspace');
  const shell = $('canvasShell');
  if (!workspace || !shell) return;
  const margin = 72;
  const baseW = shell.offsetWidth || (canvas.width + 36);
  const baseH = shell.offsetHeight || (canvas.height + 36);
  const availableW = Math.max(120, workspace.clientWidth - margin);
  const availableH = Math.max(120, workspace.clientHeight - margin);
  const scale = clamp(Math.min(availableW / baseW, availableH / baseH, 1), 0.05, 4);
  viewScale = scale;
  canvasPanOffset = { x: 0, y: 0 };
  shell.style.transform = `scale(${viewScale})`;
  shell.style.transformOrigin = 'top left';
  updateCanvasStageSize();
  if ($('zoomLabel')) $('zoomLabel').textContent = `${Math.round(viewScale * 100)}%`;
  if (showStatus) setStatus?.(`캔버스를 화면 중앙에 맞췄습니다 · ${Math.round(viewScale * 100)}%`);
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

function downloadBlob(blob, name) {
  const a = document.createElement('a');
  const url = URL.createObjectURL(blob);
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function dataUrlToBytes(dataUrl) {
  const base64 = dataUrl.split(',', 2)[1] || '';
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

let crc32Table = null;
function crc32Bytes(bytes) {
  if (!crc32Table) {
    crc32Table = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
      crc32Table[n] = c >>> 0;
    }
  }
  let crc = 0xffffffff;
  for (const b of bytes) crc = crc32Table[(crc ^ b) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function uint16LE(n) { return [n & 0xff, (n >>> 8) & 0xff]; }
function uint32LE(n) { return [n & 0xff, (n >>> 8) & 0xff, (n >>> 16) & 0xff, (n >>> 24) & 0xff]; }

function buildStoredZip(files) {
  const encoder = new TextEncoder();
  const chunks = [];
  const central = [];
  let offset = 0;
  for (const file of files) {
    const nameBytes = encoder.encode(file.name);
    const data = file.bytes instanceof Uint8Array ? file.bytes : encoder.encode(String(file.bytes || ''));
    const crc = crc32Bytes(data);
    const local = new Uint8Array([
      ...uint32LE(0x04034b50), ...uint16LE(20), ...uint16LE(0), ...uint16LE(0),
      ...uint16LE(0), ...uint16LE(0), ...uint32LE(crc), ...uint32LE(data.length), ...uint32LE(data.length),
      ...uint16LE(nameBytes.length), ...uint16LE(0),
    ]);
    chunks.push(local, nameBytes, data);
    const centralHeader = new Uint8Array([
      ...uint32LE(0x02014b50), ...uint16LE(20), ...uint16LE(20), ...uint16LE(0), ...uint16LE(0),
      ...uint16LE(0), ...uint16LE(0), ...uint32LE(crc), ...uint32LE(data.length), ...uint32LE(data.length),
      ...uint16LE(nameBytes.length), ...uint16LE(0), ...uint16LE(0), ...uint16LE(0), ...uint16LE(0),
      ...uint32LE(0), ...uint32LE(offset),
    ]);
    central.push(centralHeader, nameBytes);
    offset += local.length + nameBytes.length + data.length;
  }
  const centralSize = central.reduce((sum, chunk) => sum + chunk.length, 0);
  const centralOffset = offset;
  const eocd = new Uint8Array([
    ...uint32LE(0x06054b50), ...uint16LE(0), ...uint16LE(0), ...uint16LE(files.length), ...uint16LE(files.length),
    ...uint32LE(centralSize), ...uint32LE(centralOffset), ...uint16LE(0),
  ]);
  return new Blob([...chunks, ...central, eocd], { type: 'application/zip' });
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

async function removeBgSelected(mode='ai', chromaMode = $('pixelChromaMode')?.value || 'global') {
  const obj = selectedLayerObject();
  if (!obj || obj.type !== 'image') {
    const label = obj ? `${nameOf(obj)} (${obj.isDrawingLayer ? 'drawing layer' : obj.type})` : '없음';
    alert(`Remove BG는 이미지 레이어에서만 가능합니다. 현재 선택: ${label}`);
    return null;
  }
  const btn = mode === 'sheet' ? $('removeSheetBg') : $('removeBg');
  if (btn) btn.disabled = true;
  setStatus(mode === 'sheet' ? 'Asset Sheet BG running... 여러 아이템을 보존하는 테두리 배경 제거 중입니다.' : 'AI Cutout running... 첫 실행은 모델 다운로드 때문에 오래 걸릴 수 있습니다.');
  try {
    if (!obj._originalSrc) obj._originalSrc = obj.getSrc();
    const image = imageObjectToDataUrl(obj);
    const res = await fetch('/api/remove-bg', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ image, tolerance: +$('tolerance').value || (mode === 'sheet' ? 24 : 36), mode, chroma_mode: chromaMode })
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || 'remove-bg failed');
    const url = data.url.startsWith('data:') ? data.url : data.url + '?t=' + Date.now();
    const cutout = await new Promise((resolve, reject) => {
      fabric.Image.fromURL(url, (loaded) => {
        if (!loaded) { reject(new Error('cutout image load failed')); return; }
        resolve(loaded);
      }, { crossOrigin: 'anonymous' });
    });
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
    if ($('pixelQaSummary') && data.qa) $('pixelQaSummary').textContent = `QA alpha ${data.qa.alpha_min}-${data.qa.alpha_max} · corners ${data.qa.corner_alpha.join('/')} · green ${data.qa.green_pixels}`;
    setStatus(`${mode === 'sheet' ? 'Asset Sheet BG' : 'AI Cutout'} complete (${data.method}). 선택한 이미지 레이어에만 적용했습니다. 원본은 숨김 처리했고 Cutout 레이어를 새로 만들었습니다.`);
    return { url, cutout, data };
  } catch (err) {
    setStatus('Remove BG failed: ' + err.message);
    alert('Remove BG 실패: ' + err.message);
    return null;
  } finally {
    if (btn) btn.disabled = false;
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
  if ($('generateReplacement')) $('generateReplacement').disabled = false;
  if ($('replaceResult') && editCount === 0) {
    const currentReplaceText = $('replaceResult').textContent || '';
    const isActiveOrCompleted = /생성 중|치환 중|완료|실패/.test(currentReplaceText);
    if (!isActiveOrCompleted) $('replaceResult').textContent = '마스크가 있으면 교체 배치, 없으면 새 오브젝트 레이어로 생성합니다.';
  }
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
    const patchBox = { ...pendingInpaintResult.bbox, patch_width: pendingInpaintResult.patch_width, patch_height: pendingInpaintResult.patch_height };
    await addPatchImageUrl(pendingInpaintResult.url, patchBox, `${pendingInpaintResult.label} patch`);
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
  const image = await canvasWithOnlyObjectDataUrl(target);
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
  text.textContent = `${action.title || action.type}\n실행 방식: ${action.type}\n${JSON.stringify(action.params || {})}`;
  panel.classList.remove('hidden');
  if (!action.requires_confirm) executeChatAction(action);
}

async function sendAiChat() {
  const input = $('aiChatInput');
  const negativeInput = $('aiChatNegative');
  const message = (input?.value || '').trim();
  const negative = (negativeInput?.value || '').trim();
  if (!message) return;
  appendChatMessage('user', negative ? `${message}\nNEGATIVE: ${negative}` : message);
  pendingChatAction = null;
  $('aiChatAction')?.classList.add('hidden');
  if ($('sendAiChat')) $('sendAiChat').disabled = true;
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, negative, context: canvasChatContext() }),
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
    case 'execute_inpaint':
    case 'prepare_region_inpaint': {
      if ($('inpaintPrompt')) $('inpaintPrompt').value = params.prompt || '';
      if ($('inpaintNegative')) $('inpaintNegative').value = params.negative || '';
      const prepared = prepareSelectedRegionAiEdit();
      if (prepared) {
        appendChatMessage('assistant', '실행 시작: 선택영역 직접 재생성 요청을 보냅니다. 결과는 미리보기로 뜹니다.');
        await runSelectedAreaAiEdit();
        done('실행됨: 선택영역 AI 재생성 요청 완료. 미리보기에서 새 레이어/교체/재시도를 선택하세요.');
      } else done('안내: 이미지 레이어와 선택영역을 먼저 준비하세요.');
      break;
    }
    case 'prepare_inpaint':
      if ($('inpaintPrompt')) $('inpaintPrompt').value = params.prompt || '';
      if ($('inpaintNegative')) $('inpaintNegative').value = params.negative || '';
      if ($('directInpaintDetails')) $('directInpaintDetails').open = true;
      appendChatMessage('assistant', '실행 시작: 마스크 영역 직접 재생성 요청을 보냅니다. 결과는 미리보기로 뜹니다.');
      await runSelectedAreaAiEdit();
      done('실행됨: 선택영역 AI 재생성 요청 완료. 미리보기에서 적용 방식을 선택하세요.');
      break;
    case 'execute_generate':
    case 'prepare_generate':
      activateTool('ai');
      if ($('aiPrompt')) $('aiPrompt').value = params.negative ? `${params.prompt || ''}\n\nNegative: ${params.negative}` : (params.prompt || '');
      appendChatMessage('assistant', '실행 시작: AI 에셋 생성을 요청합니다.');
      $('generateBtn')?.click();
      done('실행됨: AI 에셋 생성 요청을 시작했습니다.');
      break;
    case 'execute_replace_object':
    case 'prepare_replace_object':
      if ($('replaceObjectPrompt')) {
        $('replaceObjectPrompt').value = params.prompt || '';
        $('replaceObjectPrompt').focus();
      }
      if ($('replaceObjectNegative')) $('replaceObjectNegative').value = params.negative || '';
      document.getElementById('aiEditPanel')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      appendChatMessage('assistant', '실행 시작: 내부 오브젝트 치환 파이프라인을 호출합니다. 마스크가 있으면 참고 치환, 없으면 새 오브젝트 레이어로 생성합니다.');
      await generateReplacementObject();
      done('실행됨: 오브젝트 치환/생성 요청을 완료했습니다. 결과는 캔버스와 상태 메시지를 확인하세요.');
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
  const targetX = +$('propX').value || 0;
  const targetY = +$('propY').value || 0;
  const curW = obj.getScaledWidth(); const curH = obj.getScaledHeight();
  obj.set({ angle:+$('propRot').value || 0, opacity: Math.max(0, Math.min(1, +$('propOpacity').value || 0)) });
  if (+$('propW').value > 0) obj.scaleX *= (+$('propW').value / curW);
  if (+$('propH').value > 0) obj.scaleY *= (+$('propH').value / curH);
  obj.setCoords?.();
  moveObjectBoundingTopLeft(obj, targetX, targetY);
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
if ($('detectSprites')) $('detectSprites').onclick = () => detectSpriteSlices().catch(err => { console.error(err); alert(`조각 탐지 실패: ${err.message}`); setStatus(`조각 탐지 실패: ${err.message}`); });
if ($('clearSprites')) $('clearSprites').onclick = clearSpriteGuides;
if ($('extractSpriteLayer')) $('extractSpriteLayer').onclick = extractSpriteSliceToLayer;
if ($('exportSpritePng')) $('exportSpritePng').onclick = exportSpriteSlicePng;
if ($('exportAllSpritesZip')) $('exportAllSpritesZip').onclick = exportAllSpriteSlicesZip;
if ($('detectGridSprites')) $('detectGridSprites').onclick = detectGridSpriteSlices;
['gridCols','gridRows'].forEach(id => {
  if ($(id)) ['input','change'].forEach(evt => $(id).addEventListener(evt, () => updateGridCellSizeFromSelectedLayer({ renderExisting: true })));
});
if ($('exportGridSpritesZip')) $('exportGridSpritesZip').onclick = exportGridSpriteSlicesZip;
if ($('buildAnimationPreview')) $('buildAnimationPreview').onclick = () => buildAnimationPreview().catch(err => { console.error(err); alert(`애니메이션 미리보기 실패: ${err.message}`); setStatus(`애니메이션 미리보기 실패: ${err.message}`); });
if ($('stopAnimationPreview')) $('stopAnimationPreview').onclick = stopAnimationPreview;
if ($('buildPixelPrompt')) $('buildPixelPrompt').onclick = syncPixelAssetPrompt;
if ($('generatePixelAsset')) $('generatePixelAsset').onclick = () => { syncPixelAssetPrompt(); generateAiAsset().catch(err => { console.error(err); alert(`도트 에셋 생성 실패: ${err.message}`); setStatus(`도트 에셋 생성 실패: ${err.message}`); }); };
if ($('generateFrontIdleFromSelected')) $('generateFrontIdleFromSelected').onclick = () => generateFrontIdleFromSelected();
if ($('runPixelWorkflow')) $('runPixelWorkflow').onclick = () => runPixelWorkflow().catch(err => { console.error(err); alert(`도트 워크플로우 실패: ${err.message}`); setStatus(`도트 워크플로우 실패: ${err.message}`); });
if ($('runPixelSamplePack')) $('runPixelSamplePack').onclick = () => runPixelSamplePack().catch(err => { console.error(err); alert(`샘플팩 생성 실패: ${err.message}`); setStatus(`샘플팩 생성 실패: ${err.message}`); });
if ($('generate8DirIdle')) $('generate8DirIdle').onclick = () => runDirectionalPixelWorkflow('idle').catch(err => { console.error(err); alert(`8방향 idle 생성 실패: ${err.message}`); setStatus(`8방향 idle 생성 실패: ${err.message}`); });
if ($('generate8DirWalk')) $('generate8DirWalk').onclick = () => runDirectionalPixelWorkflow('walk').catch(err => { console.error(err); alert(`8방향 walk 생성 실패: ${err.message}`); setStatus(`8방향 walk 생성 실패: ${err.message}`); });
if ($('runDirectionalPixelPack')) $('runDirectionalPixelPack').onclick = () => runDirectionalPixelPack().catch(err => { console.error(err); alert(`8방향 통합 생성 실패: ${err.message}`); setStatus(`8방향 통합 생성 실패: ${err.message}`); });
['pixelFrameW','pixelFrameH','pixelAnimationPreset','pixelDirectionMode','pixelTargetDirection','pixelWalkFrames'].forEach(id => {
  if ($(id)) $(id).addEventListener('change', () => applyPixelWorkflowGridDefaults());
});
if ($('pixelAssetType')) $('pixelAssetType').addEventListener('change', () => { syncPixelAssetWorkflowUi(); syncPixelAssetPrompt(); });
['pixelAnimationPreset','pixelStylePreset','pixelDirection','pixelDirectionMode','pixelTargetDirection','pixelReferenceDirection','pixelWalkFrames','pixelChromaMode','pixelPalette','pixelSubject'].forEach(id => {
  if ($(id)) $(id).addEventListener(id === 'pixelSubject' || id === 'pixelPalette' ? 'input' : 'change', () => syncPixelAssetPrompt());
});
syncPixelAssetWorkflowUi({ silent: true });
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

$('saveProject').onclick = async () => {
  try {
    setStatus('프로젝트 v2 저장 준비 중... 이미지/히스토리를 포함합니다.');
    const project = await buildProjectV2();
    const text = JSON.stringify(project, null, 2);
    const blob = new Blob([text], {type:'application/json'});
    const warning = projectSizeWarning(blob.size);
    const summary = projectSummary(project, blob.size);
    if (warning) setStatus(`${warning} · ${summary}`);
    const a = document.createElement('a');
    a.download = 'asset-studio-project-v2.json';
    a.href = URL.createObjectURL(blob);
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus(`Project v2 저장 완료 · ${summary}${warning ? ' · 압축/ZIP 개선 필요' : ''}`);
  } catch (err) {
    console.error(err);
    alert(`프로젝트 저장 실패: ${err.message}`);
    setStatus(`프로젝트 저장 실패: ${err.message}`);
  }
};
$('loadProjectBtn').onclick = () => $('loadProject').click();
$('loadProject').onchange = e => {
  const f = e.target.files[0]; if(!f) return;
  const warning = projectSizeWarning(f.size);
  setStatus(`프로젝트 파일 읽는 중... ${f.name} · ${formatBytes(f.size)}${warning ? ' · ' + warning : ''}`);
  const r = new FileReader();
  r.onload = () => {
    try {
      const project = JSON.parse(r.result);
      loadProjectFileObject(project);
      setStatus(`프로젝트 파일 파싱 완료 · ${projectSummary(project, f.size)}${warning ? ' · 큰 파일' : ''}`);
    } catch (err) {
      console.error(err);
      alert(`프로젝트 불러오기 실패: ${err.message}`);
      setStatus(`프로젝트 불러오기 실패: ${err.message}`);
    } finally {
      e.target.value = '';
    }
  };
  r.onerror = () => {
    const msg = r.error?.message || '파일 읽기 오류';
    alert(`프로젝트 불러오기 실패: ${msg}`);
    setStatus(`프로젝트 불러오기 실패: ${msg}`);
    e.target.value = '';
  };
  r.readAsText(f);
};

async function generateAiAsset() {
  let prompt = ($('aiPrompt')?.value || '').trim();
  if (!prompt) prompt = buildPixelAssetPrompt().trim();
  if (!prompt) { alert('프롬프트를 입력하세요.'); return null; }
  const preset = $('aiPreset')?.value || ($('pixelAssetType')?.value === 'ui_panel' ? 'ui' : 'pixel');
  const aspect = $('aiAspect')?.value || 'square';
  const backgroundMode = preset === 'background' ? 'none' : 'chroma_green';
  const wantedReference = !!$('pixelUseReference')?.checked && preset === 'pixel';
  const selectedReferenceObj = wantedReference ? selectedLayerObject() : null;
  const useReference = !!(wantedReference && selectedReferenceObj && selectedReferenceObj.type === 'image');
  const referenceObj = useReference ? selectedReferenceObj : null;
  const generateBtn = $('generateBtn') || $('generatePixelAsset');
  if (generateBtn) generateBtn.disabled = true;
  setStatus(useReference ? '기준 이미지 기반 AI 에셋 생성 중... 선택 레이어의 캐릭터/스타일을 참조합니다.' : (backgroundMode === 'chroma_green' ? 'AI 에셋 생성 중... 배경은 #00FF00 크로마키로 고정합니다.' : 'AI 배경 이미지 생성 중... 30~90초 정도 걸릴 수 있습니다.'));
  try {
    const endpoint = useReference ? '/api/generate-reference' : '/api/generate';
    const directionMode = $('pixelDirectionMode')?.value || 'single';
    const targetDirection = $('pixelTargetDirection')?.value || 'S';
    const referenceDirection = $('pixelReferenceDirection')?.value || 'S';
    const rawAnimPreset = effectivePixelAnimationPreset();
    const animationMode = rawAnimPreset.startsWith('walk') ? 'walk' : rawAnimPreset;
    const payload = {
      prompt,
      preset,
      aspect_ratio: aspect,
      background_mode: backgroundMode,
      target_direction: targetDirection,
      reference_direction: referenceDirection,
      direction_mode: directionMode,
      animation_mode: animationMode,
      frame_count: pixelPresetFrameCount(),
      walk_frames: pixelPresetFrameCount(),
      chroma_mode: $('pixelChromaMode')?.value || 'global'
    };
    if (useReference) payload.reference_image = imageObjectToDataUrl(referenceObj);
    const res = await fetch(endpoint, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'generation failed');
    const url = withCacheBust(data.url);
    addGallery(url, data.method || data.model || 'generated');
    const img = await addImageUrl(url, useReference ? `참조 생성 - ${nameOf(referenceObj)}` : 'AI 생성 에셋');
    if ($('pixelQaSummary') && data.qa) {
      const dqa = data.qa.direction_qa || {};
      $('pixelQaSummary').textContent = `QA direction ${dqa.status || 'n/a'} ${dqa.target_direction || ''} slot ${dqa.selected_slot ?? '-'} · alpha ${data.qa.alpha_min}-${data.qa.alpha_max} · corners ${data.qa.corner_alpha?.join('/') || '-'} · green ${data.qa.green_pixels ?? '-'}`;
    }
    recordPixelAssetResult(url, data.method || data.model || 'generated');
    setStatus(useReference ? `Reference AI generated: ${data.model || ''}` : `AI generated: ${data.model || ''}`);
    return { url, img, data, referenceObj: referenceObj || null };
  } catch (err) { setStatus('AI generation failed: ' + err.message); throw err; }
  finally { if (generateBtn) generateBtn.disabled = false; }
}

function setFrontIdleGridForImage(img, frames = 4) {
  const defaults = applyPixelWorkflowGridDefaults(img);
  if ($('gridRows')) $('gridRows').value = '1';
  if ($('gridCellH')) $('gridCellH').value = String(imageDisplayedSize(img)?.h || defaults.frameH);
  if ($('pixelFrameH')) $('pixelFrameH').value = $('gridCellH')?.value || String(defaults.frameH);
  if ($('animFps')) $('animFps').value = '5';
  if ($('animMode')) $('animMode').value = 'loop';
}

function animationPresetSpec(presetRaw) {
  const preset = presetRaw || 'idle';
  const frameCount = requestedPixelFrameCount();
  const specs = {
    idle: {
      key: `idle${frameCount}`, label: 'Idle', frames: frameCount,
      frameOrder: `${frameCount} subtle breathing frames in one loop`,
      motion: 'restrained breathing only; feet planted on the same baseline; no stepping, no turning'
    },
    walk4: {
      key: `walk${frameCount}`, label: 'Walk', frames: frameCount,
      frameOrder: `${frameCount} evenly spaced walk-cycle phases with opposite contacts`,
      motion: 'readable walk cycle with alternating arms and legs; consistent foot baseline and pivot'
    },
    walk6: {
      key: `walk${frameCount}`, label: 'Walk', frames: frameCount,
      frameOrder: `${frameCount} evenly spaced walk-cycle phases with opposite contacts`,
      motion: 'smooth walk cycle with real alternating limbs; no duplicate idle frames'
    },
    attack: {
      key: `attack${frameCount}`, label: 'Attack', frames: frameCount,
      frameOrder: `${frameCount} readable attack beats from ready/wind-up through impact/recovery`,
      motion: 'clear attack silhouette while preserving the chosen facing direction and body identity'
    },
    jump: {
      key: `jump${frameCount}`, label: 'Jump', frames: frameCount,
      frameOrder: `${frameCount} readable jump beats from crouch/takeoff through air/landing`,
      motion: 'vertical jump arc in place; no sideways travel unless direction pose requires it'
    },
    cast: {
      key: `cast${frameCount}`, label: 'Cast', frames: frameCount,
      frameOrder: `${frameCount} readable cast beats from ready/gather through release/recover`,
      motion: 'spell-cast gesture with restrained effect pixels; keep character readable and consistent'
    },
    hurt: {
      key: `hurt${frameCount}`, label: 'Hurt', frames: frameCount,
      frameOrder: `${frameCount} readable hurt/recoil/recovery beats`,
      motion: 'small hit reaction; do not change costume, species, or facing direction'
    },
    death: {
      key: `death${frameCount}`, label: 'Death', frames: frameCount,
      frameOrder: `${frameCount} readable collapse beats ending down/still`,
      motion: 'short collapse animation; keep readable silhouette and consistent outfit colors'
    },
    ui_static: {
      key: 'static1', label: 'Static', frames: 1,
      frameOrder: 'single clean static frame',
      motion: 'no animation; one isolated game asset frame'
    }
  };
  return specs[preset] || specs.idle;
}

function buildSelectedActionSpritePrompt(referenceObj, spec) {
  const baseSubject = ($('pixelSubject')?.value || '').trim();
  const palette = ($('pixelPalette')?.value || 'limited dark fantasy palette').trim();
  const type = $('pixelAssetType')?.value || 'character';
  const actor = isPixelActorAssetType(type);
  if (!actor) {
    return `${baseSubject ? baseSubject + '\n\n' : ''}Create one static ${type} pixel-art game asset using the selected image only as a visual style/color reference.
No character animation, no directional sheet, no alternate poses, no multiple frames.
Preserve the reference's pixel density, outline weight, palette mood, and production style, but create the requested ${type} asset.
Refined 32-bit game-ready pixel art, crisp hard pixels, clean silhouette, ${palette}.
Flat exact #00FF00 chroma green background edge-to-edge.
No text, labels, numbers, watermark, mockup frame, scenery, extra characters, or sprite sheet.`;
  }
  const targetDirection = $('pixelTargetDirection')?.value || 'S';
  const referenceDirection = $('pixelReferenceDirection')?.value || 'S';
  const directionText = directionLabel(targetDirection);
  const referenceText = directionLabel(referenceDirection);
  const frameText = spec.frames === 1
    ? 'Exactly one isolated sprite frame.'
    : `Exactly one horizontal row of ${spec.frames} evenly spaced frames.`;
  return `${baseSubject ? baseSubject + '\n\n' : ''}Create a ${spec.label.toLowerCase()} pixel-art sprite from the selected reference character.
Target direction: ${directionText}. Keep the visible character facing this target direction in every frame.
Reference image direction: ${referenceText}. Use it only for identity, costume, colors, proportions, pixel density, outline weight, and scale.
${frameText}
Frame order: ${spec.frameOrder}.
Motion rule: ${spec.motion}.
Preserve the same identity, face/species, costume, colors, silhouette, pixel density, outline weight, scale, and pivot across all frames. No color drift between frames.
Refined 32-bit dark fantasy pixel art, crisp hard pixels, clean outline, ${palette}.
Flat exact #00FF00 chroma green background edge-to-edge.
No text, labels, numbers, watermark, mockup frame, scenery, extra characters, multiple rows, contact sheet, or alternate directions.`;
}

async function generateFrontIdleFromSelected() {
  const referenceObj = selectedLayerObject();
  const type = $('pixelAssetType')?.value || 'character';
  const actor = isPixelActorAssetType(type);
  if (!referenceObj || referenceObj.type !== 'image') {
    alert(actor ? '먼저 캔버스에서 캐릭터/몬스터 이미지 레이어를 선택하세요.' : '선택 이미지 스타일 생성은 먼저 이미지 레이어를 선택해야 합니다.');
    setStatus('선택 이미지 기준 생성 실패: 이미지 레이어 선택 필요');
    return null;
  }
  const btn = $('generateFrontIdleFromSelected');
  if (btn) btn.disabled = true;
  const preset = effectivePixelAnimationPreset();
  const spec = animationPresetSpec(preset);
  const targetDirection = $('pixelTargetDirection')?.value || 'S';
  const referenceDirection = $('pixelReferenceDirection')?.value || 'S';
  const prompt = buildSelectedActionSpritePrompt(referenceObj, spec);
  const statusPrefix = actor ? `선택 ${type} 기준 ${directionLabel(targetDirection)} ${spec.label} ${spec.frames}프레임` : `선택 이미지 스타일 기준 ${type} 정적 에셋`;
  try {
    setStatus(`${statusPrefix} 자동 생성 중...`);
    const res = await fetch('/api/generate-reference', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        reference_image: imageObjectToDataUrl(referenceObj),
        prompt,
        negative: actor ? 'wrong facing direction, alternate directions, turntable, contact sheet, multiple rows, labels, text, numbers, watermark, different character per frame, color drift, costume changes, white background, scenery, cropped feet, malformed limbs, fake walk cycle, duplicate frames' : 'animation frames, sprite sheet, character pose sheet, directional views, labels, text, numbers, watermark, white background, scenery, mockup frame',
        preset: 'pixel',
        aspect_ratio: 'square',
        background_mode: 'chroma_green',
        direction_mode: 'single',
        target_direction: targetDirection,
        reference_direction: referenceDirection,
        animation_mode: spec.key,
        frame_count: spec.frames,
        chroma_mode: $('pixelChromaMode')?.value || 'global',
      })
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || 'direction/action generation failed');
    const url = withCacheBust(data.url);
    const resultLabel = actor ? `${targetDirection} ${spec.label} ${spec.frames}f` : `${type} static`;
    addGallery(url, data.method || data.model || resultLabel);
    const img = await addImageUrl(url, `${resultLabel} - ${nameOf(referenceObj)}`);
    canvas.setActiveObject(img);
    rememberSelectedLayer(img);
    setFrontIdleGridForImage(img, spec.frames);
    if (spec.frames > 1) {
      removeSpriteGuideObjects();
      spriteSlices = buildGridSpriteSlices();
      selectedSpriteSliceId = null;
      await buildAnimationPreview();
    }
    if ($('pixelQaSummary') && data.qa) {
      $('pixelQaSummary').textContent = `${resultLabel} 자동 · alpha ${data.qa.alpha_min}-${data.qa.alpha_max} · corners ${data.qa.corner_alpha?.join('/') || '-'} · green ${data.qa.green_pixels ?? '-'}`;
    }
    recordPixelAssetResult(url, data.method || data.model || resultLabel);
    setStatus(actor ? `${directionLabel(targetDirection)} ${spec.label} ${spec.frames}프레임 자동 생성 완료 · grid/preview 연결됨` : `${type} 정적 에셋 자동 생성 완료 · 1프레임 그리드 연결됨`);
    return { url, img, data };
  } catch (err) {
    console.error(err);
    alert(`방향/동작 자동 생성 실패: ${err.message}`);
    setStatus(`방향/동작 자동 생성 실패: ${err.message}`);
    return null;
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function runPixelWorkflow() {
  syncPixelAssetPrompt();
  const defaults = applyPixelWorkflowGridDefaults();
  setStatus(`도트 워크플로우 시작 · ${defaults.frames} frames · ${defaults.frameW}×${defaults.frameH}`);
  const result = await generateAiAsset();
  if (!result?.img) return null;
  canvas.setActiveObject(result.img);
  rememberSelectedLayer(result.img);
  let finalUrl = result.url;
  let finalImg = result.img;
  if ($('pixelWorkflowCleanBg')?.checked) {
    const cleaned = await removeBgSelected('chroma_green', $('pixelChromaMode')?.value || 'global');
    if (cleaned?.cutout) {
      finalUrl = cleaned.url;
      finalImg = cleaned.cutout;
      recordPixelAssetResult(finalUrl, `cleaned · ${cleaned.data?.method || 'sheet'}`);
    }
  }
  canvas.setActiveObject(finalImg);
  rememberSelectedLayer(finalImg);
  applyPixelWorkflowGridDefaults(finalImg);
  removeSpriteGuideObjects();
  spriteSlices = buildGridSpriteSlices();
  selectedSpriteSliceId = null;
  setStatus(`도트 워크플로우 완료 · ${pixelPresetFrameCount()} frames · 그리드 값 자동 설정됨`);
  return { ...result, finalUrl, finalImg };
}

async function runDirectionalPixelWorkflow(animationMode = 'idle') {
  if ($('pixelAssetType')) $('pixelAssetType').value = 'character';
  if ($('pixelDirectionMode')) $('pixelDirectionMode').value = '8dir';
  if ($('pixelAnimationPreset')) $('pixelAnimationPreset').value = animationMode === 'walk' ? 'walk4' : 'idle';
  if ($('pixelDirection')) $('pixelDirection').value = '8dir';
  syncPixelAssetPrompt();
  return runPixelWorkflow();
}

async function runDirectionalPixelPack() {
  const baseReference = $('pixelUseReference')?.checked ? selectedLayerObject() : null;
  if ($('pixelUseReference')?.checked && (!baseReference || baseReference.type !== 'image')) {
    const label = baseReference ? `${nameOf(baseReference)} (${baseReference.type})` : '없음';
    throw new Error(`8방향 통합 생성은 기준 이미지 레이어를 먼저 선택해야 합니다. 현재 선택: ${label}`);
  }
  const results = [];
  for (const mode of ['idle', 'walk']) {
    if (baseReference) {
      canvas.setActiveObject(baseReference);
      rememberSelectedLayer(baseReference);
    }
    const result = await runDirectionalPixelWorkflow(mode);
    if (result) results.push(result);
  }
  setStatus(`8방향 Idle+Walk 통합 생성 완료 · ${results.length}/2`);
  return results;
}

async function runPixelSamplePack() {
  const baseReference = $('pixelUseReference')?.checked ? selectedLayerObject() : null;
  if ($('pixelUseReference')?.checked && (!baseReference || baseReference.type !== 'image')) {
    const label = baseReference ? `${nameOf(baseReference)} (${baseReference.type})` : '없음';
    throw new Error(`샘플팩은 기준 이미지 레이어를 먼저 선택해야 합니다. 현재 선택: ${label}`);
  }
  const subjectBase = ($('pixelSubject')?.value || 'same reference character, dark fantasy game asset').trim();
  const style = $('pixelStylePreset')?.value || '32bit_refined';
  const direction = $('pixelDirection')?.value || 'front';
  const palette = ($('pixelPalette')?.value || 'limited dark game palette').trim();
  const jobs = [
    { type: 'character', anim: 'idle', subject: `${subjectBase}, idle animation sprite sheet` },
    { type: 'character', anim: 'walk4', subject: `${subjectBase}, walking animation sprite sheet, same character design` },
    { type: 'ui_panel', anim: 'ui_static', subject: 'dark game UI panel and button asset sheet, muted brass trim, black plate, reusable interface parts' },
  ];
  const packBtn = $('runPixelSamplePack');
  if (packBtn) packBtn.disabled = true;
  try {
    const results = [];
    for (const [idx, job] of jobs.entries()) {
      $('pixelAssetType').value = job.type;
      $('pixelAnimationPreset').value = job.anim;
      $('pixelStylePreset').value = style;
      $('pixelDirection').value = direction;
      $('pixelPalette').value = palette;
      $('pixelSubject').value = job.subject;
      if (baseReference) {
        canvas.setActiveObject(baseReference);
        rememberSelectedLayer(baseReference);
      }
      setStatus(`샘플팩 생성 중 ${idx + 1}/${jobs.length} · ${job.anim}`);
      const result = await runPixelWorkflow();
      if (result) results.push(result);
    }
    setStatus(`샘플팩 완료 · ${results.length}/${jobs.length}개를 페이지에서 생성했습니다.`);
    return results;
  } finally {
    if (packBtn) packBtn.disabled = false;
  }
}

if ($('generateBtn')) $('generateBtn').onclick = () => generateAiAsset();

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

window.addEventListener('resize', () => fitView(false));
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
