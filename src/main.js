const DEFAULT_STYLE_PROFILE = {
  schema_version:'asset-studio.style-profile/v1', id:'project-style', name:'Project Style', version:1,
  created_at:'2026-01-01T00:00:00.000Z', updated_at:'2026-01-01T00:00:00.000Z',
  palette:{colors:['#20242c','#d7d9d7'],mode:'limited'}, outline:{mode:'dark',width:1,color:'#20242c'},
  shading:{mode:'cel',steps:3,light_direction:'top-left'}, material_treatment:{mode:'matte',detail:'medium'},
  pixel_density:{mode:'pixel-art',scale:1}, silhouette:{mode:'readable',complexity:'medium'},
  contrast:{mode:'medium',value:0.6}, anti_aliasing:{mode:'off'}, reference_assets:[], forbidden_elements:['text','logo','watermark'],
  family_overrides:{sprite:{},tile:{},ui:{},object:{}}
};
let canonicalProjectStyleProfile = JSON.parse(JSON.stringify(DEFAULT_STYLE_PROFILE));

function normalizeStyleProfile(input) {
  const fail = message => { throw new Error(`Invalid style_profile: ${message}`); };
  const plain = value => value && typeof value === 'object' && !Array.isArray(value) && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
  if (!plain(input)) fail('object required');
  let nodes=0, stringBytes=0; const seen=new Set(), encoder=new TextEncoder();
  const walk=(value,depth=0)=>{
    if(depth>16 || ++nodes>4096) fail('structure budget exceeded');
    if(value===null || typeof value==='boolean') return;
    if(typeof value==='string'){stringBytes+=encoder.encode(value).byteLength;if(stringBytes>65536||value.length>8192)fail('string budget exceeded');return;}
    if(typeof value==='number'){if(!Number.isFinite(value))fail('finite numbers required');return;}
    if(typeof value!=='object'||seen.has(value))fail('JSON-safe acyclic value required');
    if(!Array.isArray(value)&&!plain(value))fail('plain object required');
    if(Array.isArray(value)&&value.length>256)fail('array budget exceeded');
    seen.add(value); for(const key of Object.keys(value)){if(['__proto__','prototype','constructor'].includes(key))fail('unsafe key');walk(value[key],depth+1);} seen.delete(value);
  }; walk(input);
  const exact=(obj,keys,label)=>{if(!plain(obj)||Object.keys(obj).length!==keys.length||Object.keys(obj).some(k=>!keys.includes(k)))fail(`${label} fields`);};
  const top=['schema_version','id','name','version','created_at','updated_at','palette','outline','shading','material_treatment','pixel_density','silhouette','contrast','anti_aliasing','reference_assets','forbidden_elements','family_overrides'];
  exact(input,top,'top-level');
  const str=(v,label,max=200)=>{if(typeof v!=='string'||!v.trim()||v.length>max)fail(label);return v;};
  const enumv=(v,allowed,label)=>{if(!allowed.includes(v))fail(label);return v;};
  const integer=(v,min,max,label)=>{if(!Number.isInteger(v)||v<min||v>max)fail(label);return v;};
  const finite=(v,min,max,label)=>{if(typeof v!=='number'||!Number.isFinite(v)||v<min||v>max)fail(label);return v;};
  if(input.schema_version!=='asset-studio.style-profile/v1')fail('schema_version'); str(input.id,'id');str(input.name,'name',256);integer(input.version,1,2147483647,'version');
  const timestamp=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(v)&&new Date(v).toISOString()===v;
  if(!timestamp(input.created_at)||!timestamp(input.updated_at))fail('timestamps');
  const validateFields=(source,partial=false)=>{
    const allowed=['palette','outline','shading','material_treatment','pixel_density','silhouette','contrast','anti_aliasing'];
    if(!plain(source)||Object.keys(source).some(k=>!allowed.includes(k)))fail('style fields');
    if(!partial&&allowed.some(k=>!(k in source)))fail('missing style field');
    if('palette'in source){const v=source.palette;exact(v,['colors','mode'],'palette');if(!Array.isArray(v.colors)||v.colors.length<1||v.colors.length>32||v.colors.some(c=>typeof c!=='string'||!/^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$/.test(c)))fail('palette colors');enumv(v.mode,['limited','adaptive','full'],'palette mode');}
    if('outline'in source){const v=source.outline;exact(v,['mode','width','color'],'outline');enumv(v.mode,['none','dark','colored','light'],'outline mode');integer(v.width,0,16,'outline width');if(typeof v.color!=='string'||!/^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$/.test(v.color))fail('outline color');}
    if('shading'in source){const v=source.shading;exact(v,['mode','steps','light_direction'],'shading');enumv(v.mode,['none','flat','cel','soft','dithered'],'shading mode');integer(v.steps,1,16,'shading steps');enumv(v.light_direction,['top-left','top','top-right','left','right','bottom-left','bottom','bottom-right','ambient'],'light direction');}
    if('material_treatment'in source){const v=source.material_treatment;exact(v,['mode','detail'],'material_treatment');enumv(v.mode,['matte','glossy','metallic','painted','natural'],'material mode');enumv(v.detail,['low','medium','high'],'material detail');}
    if('pixel_density'in source){const v=source.pixel_density;exact(v,['mode','scale'],'pixel_density');enumv(v.mode,['pixel-art','hybrid','smooth'],'pixel density mode');finite(v.scale,0.25,16,'pixel scale');}
    if('silhouette'in source){const v=source.silhouette;exact(v,['mode','complexity'],'silhouette');enumv(v.mode,['readable','natural','geometric'],'silhouette mode');enumv(v.complexity,['low','medium','high'],'silhouette complexity');}
    if('contrast'in source){const v=source.contrast;exact(v,['mode','value'],'contrast');enumv(v.mode,['low','medium','high'],'contrast mode');finite(v.value,0,1,'contrast value');}
    if('anti_aliasing'in source){const v=source.anti_aliasing;exact(v,['mode'],'anti_aliasing');enumv(v.mode,['off','on','selective'],'anti aliasing mode');}
  }; validateFields(Object.fromEntries(['palette','outline','shading','material_treatment','pixel_density','silhouette','contrast','anti_aliasing'].map(key=>[key,input[key]])));
  if(!Array.isArray(input.reference_assets)||input.reference_assets.length>64)fail('reference_assets');
  input.reference_assets.forEach(v=>{exact(v,['asset_id','weight'],'reference asset');str(v.asset_id,'asset_id');finite(v.weight,0,1,'reference weight');});
  if(!Array.isArray(input.forbidden_elements)||input.forbidden_elements.length>64||input.forbidden_elements.some(v=>typeof v!=='string'||!v.trim()||v.length>200))fail('forbidden_elements');
  exact(input.family_overrides,['sprite','tile','ui','object'],'family_overrides');
  for(const family of ['sprite','tile','ui','object'])validateFields(input.family_overrides[family],true);
  return JSON.parse(JSON.stringify(input));
}

function resolveStyleProfileForFamily(profile, family) {
  if(!['sprite','tile','ui','object'].includes(family))throw new Error('Invalid style profile family');
  const value=normalizeStyleProfile(profile), override=value.family_overrides[family];
  for(const key of Object.keys(override))value[key]=JSON.parse(JSON.stringify(override[key]));
  value.family_overrides={sprite:{},tile:{},ui:{},object:{}};
  return normalizeStyleProfile(value);
}

function styleProfileFromControls() {
  const profile=JSON.parse(JSON.stringify(canonicalProjectStyleProfile));
  const value=(id,fallback='')=>document.getElementById(id)?.value ?? fallback;
  const preset=value('assetStylePreset','32bit_refined'), legacyNotes=String(value('assetStyleNotes','')).trim();
  profile.name=String(value('styleProfileName',legacyNotes||'Project Style')).trim().slice(0,256)||'Project Style';
  profile.palette.colors=String(value('stylePaletteColors',profile.palette.colors.join(','))).split(',').map(v=>v.trim()).filter(Boolean);
  profile.palette.mode=value('stylePaletteMode',profile.palette.mode);
  profile.outline={mode:value('styleOutlineMode',profile.outline.mode),width:Number(value('styleOutlineWidth',profile.outline.width)),color:value('styleOutlineColor',profile.outline.color)};
  profile.shading={mode:value('styleShadingMode',profile.shading.mode),steps:Number(value('styleShadingSteps',profile.shading.steps)),light_direction:value('styleLightDirection',profile.shading.light_direction)};
  profile.material_treatment={mode:value('styleMaterialMode',profile.material_treatment.mode),detail:value('styleMaterialDetail',profile.material_treatment.detail)};
  profile.pixel_density={mode:value('stylePixelMode',preset.includes('pixel')||preset.includes('bit')?'pixel-art':profile.pixel_density.mode),scale:Number(value('stylePixelScale',preset.includes('16bit')?2:profile.pixel_density.scale))};
  profile.silhouette={mode:value('styleSilhouetteMode',profile.silhouette.mode),complexity:value('styleSilhouetteComplexity',profile.silhouette.complexity)};
  profile.contrast={mode:value('styleContrastMode',profile.contrast.mode),value:Number(value('styleContrastValue',profile.contrast.value))};
  profile.anti_aliasing={mode:value('styleAntiAliasing',profile.anti_aliasing.mode)};
  const references=String(value('styleReferenceAssets','')).trim();profile.reference_assets=references?JSON.parse(references):[];
  profile.forbidden_elements=String(value('styleForbiddenElements',profile.forbidden_elements.join(','))).split(',').map(v=>v.trim()).filter(Boolean);
  for(const family of ['sprite','tile','ui','object']){const raw=String(value(`styleOverride-${family}`,'')).trim();if(raw)profile.family_overrides[family]=JSON.parse(raw);}
  return normalizeStyleProfile(profile);
}

function hydrateStyleProfileControls(input) {
  const profile=normalizeStyleProfile(input);
  canonicalProjectStyleProfile=JSON.parse(JSON.stringify(profile));
  const values={styleProfileName:profile.name,stylePaletteColors:profile.palette.colors.join(','),stylePaletteMode:profile.palette.mode,styleOutlineMode:profile.outline.mode,styleOutlineWidth:String(profile.outline.width),styleOutlineColor:profile.outline.color,styleShadingMode:profile.shading.mode,styleShadingSteps:String(profile.shading.steps),styleLightDirection:profile.shading.light_direction,styleMaterialMode:profile.material_treatment.mode,styleMaterialDetail:profile.material_treatment.detail,stylePixelMode:profile.pixel_density.mode,stylePixelScale:String(profile.pixel_density.scale),styleSilhouetteMode:profile.silhouette.mode,styleSilhouetteComplexity:profile.silhouette.complexity,styleContrastMode:profile.contrast.mode,styleContrastValue:String(profile.contrast.value),styleAntiAliasing:profile.anti_aliasing.mode,styleReferenceAssets:profile.reference_assets.length?JSON.stringify(profile.reference_assets):'',styleForbiddenElements:profile.forbidden_elements.join(',')};
  for(const family of ['sprite','tile','ui','object'])values[`styleOverride-${family}`]=Object.keys(profile.family_overrides[family]).length?JSON.stringify(profile.family_overrides[family]):'';
  for(const [id,value] of Object.entries(values)){const element=document.getElementById(id);if(element)element.value=value;}
  return profile;
}

const canvas = new fabric.Canvas('c', {
  preserveObjectStacking: true,
  backgroundColor: '#ffffff',
  selection: true,
});

let history = [];
let historyIndex = -1;
let suppressHistory = false;
let historyLoadInFlight = null;
let currentDrawTool = 'select';
let currentTool = 'select';
let workspaceMode = 'ai';
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
const SERIALIZED_PROPS = ['id','name','_originalSrc','_preservedOriginal','_assetId','_assetName','excludeFromLayers','excludeFromExport','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId','resultId','resultFamily','resultType','replacesLayerId'];
const PROJECT_MAX_BYTES = 64 * 1024 * 1024;

function createAssetResult(input, deps = {}) {
  const fail = message => { throw new Error(`Invalid AssetResult: ${message}`); };
  const clone = (value, label) => {
    const seen = new Set(); let nodes = 0;
    const inspect = (item, depth) => {
      if (depth > 48 || ++nodes > 20000) fail(`${label} budget exceeded`);
      if (item === null || ['string','boolean'].includes(typeof item)) return;
      if (typeof item === 'number') { if (!Number.isFinite(item)) fail(`${label} non-finite number`); return; }
      if (typeof item !== 'object' || seen.has(item)) fail(`${label} is not JSON-safe`);
      seen.add(item);
      if (!Array.isArray(item) && Object.getPrototypeOf(item) !== Object.prototype && Object.getPrototypeOf(item) !== null) fail(`${label} prototype`);
      for (const key of Object.keys(item)) {
        if (key === '__proto__' || key === 'prototype' || key === 'constructor') fail(`${label} unsafe key`);
        inspect(item[key], depth + 1);
      }
      seen.delete(item);
    };
    inspect(value, 0);
    let text; try { text = JSON.stringify(value); } catch (_) { fail(`${label} serialization`); }
    if (text === undefined || text.length > 2097152) fail(`${label} byte budget exceeded`);
    return JSON.parse(text);
  };
  if (!input || typeof input !== 'object' || Array.isArray(input)) fail('object required');
  const families = { sprite:new Set(['character','monster','npc','effect','item']), tile:new Set(['terrain','tile','tileset','autotile','map']), ui:new Set(['button','panel','icon','ui_panel']), object:new Set(['interactable','prop','decoration','item']) };
  const family = input.family, type = input.type;
  if (!families[family]) fail('family');
  if (typeof type !== 'string' || !type.trim() || !families[family].has(type)) fail('family subtype');
  const statuses = new Set(['pending','succeeded','failed']);
  if (!statuses.has(input.status)) fail('status');
  const clock = typeof deps.clock === 'function' ? deps.clock : () => new Date().toISOString();
  const now = input.createdAt || clock();
  const updated = input.updatedAt || now;
  const canonicalTimestamp = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value) && new Date(value).toISOString() === value;
  if (!canonicalTimestamp(now) || !canonicalTimestamp(updated) || Date.parse(updated) < Date.parse(now)) fail('timestamp');
  const id = input.id || (typeof deps.idFactory === 'function' ? deps.idFactory() : `result-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  if (typeof id !== 'string' || !id.trim() || id.length > 200) fail('id');
  const result = clone({ id, family, type, status:input.status, preview:input.preview ?? null,
    sourceRequest:input.sourceRequest, normalizedContract:input.normalizedContract,
    qaSummary:input.qaSummary ?? null, artifacts:input.artifacts ?? [], adopted:input.adopted === true,
    rejected:input.rejected === true, adoptedAt:input.adoptedAt ?? null, rejectedAt:input.rejectedAt ?? null,
    createdAt:now, updatedAt:updated, error:input.error ?? null }, 'result');
  if (!result.sourceRequest || !result.normalizedContract) fail('request/contract');
  if (result.sourceRequest.asset_family !== family || result.sourceRequest.asset_type !== type || result.normalizedContract.asset_family !== family || result.normalizedContract.asset_type !== type) fail('family contract mismatch');
  if (!Array.isArray(result.artifacts)) fail('artifacts');
  if (result.adopted && result.rejected) fail('adopted/rejected conflict');
  if ((result.adoptedAt !== null && !canonicalTimestamp(result.adoptedAt)) || (result.rejectedAt !== null && !canonicalTimestamp(result.rejectedAt))) fail('decision timestamp');
  if (result.adopted !== (result.adoptedAt !== null) || result.rejected !== (result.rejectedAt !== null)) fail('decision timestamp state');
  if (result.status === 'failed' && (!result.error || typeof result.error.message !== 'string')) fail('failed error');
  if (result.status === 'succeeded') {
    const urls = [result.preview?.url, ...result.artifacts.map(a => a?.url)].filter(Boolean);
    if (!urls.some(url => typeof url === 'string' && !url.startsWith('blob:'))) fail('succeeded durable artifact');
  }
  return result;
}

function transitionAssetResult(current, patch, deps = {}) {
  if (!current || !patch || typeof patch !== 'object') throw new Error('AssetResult transition requires objects');
  const nextStatus = patch.status ?? current.status;
  const allowed = current.status === 'pending' ? new Set(['pending','succeeded','failed']) : new Set([current.status]);
  if (!allowed.has(nextStatus)) throw new Error(`Invalid AssetResult status transition: ${current.status} -> ${nextStatus}`);
  if ((current.rejected || patch.rejected === true) && (current.adopted || patch.adopted === true)) throw new Error('AssetResult cannot be adopted and rejected');
  const clock = typeof deps.clock === 'function' ? deps.clock : () => new Date().toISOString();
  const updatedAt=clock(), decisionPatch={...patch};
  if (patch.adopted === true && !current.adopted) decisionPatch.adoptedAt=updatedAt;
  if (patch.rejected === true && !current.rejected) decisionPatch.rejectedAt=updatedAt;
  return createAssetResult({ ...current, ...decisionPatch, id:current.id, createdAt:current.createdAt, updatedAt }, deps);
}

function createAssetResultStore() {
  const values = new Map(), listeners = new Set(); let selectedId = null; const compared = new Set();
  const copy = value => JSON.parse(JSON.stringify(value));
  const notify = () => listeners.forEach(fn => fn(api.list(), api.state()));
  const api = {
    add(value) { if (values.has(value.id)) throw new Error(`Duplicate AssetResult id: ${value.id}`); const safe=createAssetResult(value,{clock:()=>value.updatedAt,idFactory:()=>value.id}); values.set(safe.id,safe); notify(); return copy(safe); },
    update(id, patch, deps={}) { if(!values.has(id)) throw new Error(`Unknown AssetResult id: ${id}`); const safe=transitionAssetResult(values.get(id),patch,deps); values.set(id,safe); notify(); return copy(safe); },
    get(id) { return values.has(id) ? copy(values.get(id)) : null; },
    list() { return Array.from(values.values(),copy); },
    select(id) { if(!values.has(id)) throw new Error(`Unknown AssetResult id: ${id}`); selectedId=id; notify(); return api.state(); },
    toggleCompare(id) { if(!values.has(id)) throw new Error(`Unknown AssetResult id: ${id}`); if(compared.has(id)) compared.delete(id); else { if(compared.size>=2) throw new Error('Compare supports at most 2 results'); compared.add(id); } notify(); return api.state(); },
    state() { return {selectedId, compareIds:Array.from(compared)}; },
    subscribe(fn) { if(typeof fn!=='function') throw new Error('listener required'); listeners.add(fn); return ()=>listeners.delete(fn); },
    snapshot() { return {values:Array.from(values.entries(),([id,value])=>[id,copy(value)]),selectedId,compareIds:Array.from(compared)}; },
    restore(snapshot) {
      if(!snapshot || !Array.isArray(snapshot.values) || !Array.isArray(snapshot.compareIds)) throw new Error('Invalid AssetResultStore snapshot');
      const nextValues=new Map();
      for(const entry of snapshot.values){
        if(!Array.isArray(entry) || entry.length!==2 || typeof entry[0]!=='string' || nextValues.has(entry[0])) throw new Error('Invalid AssetResultStore snapshot values');
        const value=entry[1], safe=createAssetResult(value,{clock:()=>value?.updatedAt,idFactory:()=>value?.id});
        if(safe.id!==entry[0]) throw new Error('AssetResultStore snapshot id mismatch');
        nextValues.set(safe.id,safe);
      }
      const nextSelected=snapshot.selectedId ?? null, nextCompare=snapshot.compareIds.slice();
      if(nextSelected!==null && !nextValues.has(nextSelected)) throw new Error('AssetResultStore snapshot selectedId is dangling');
      if(nextCompare.length>2 || new Set(nextCompare).size!==nextCompare.length || nextCompare.some(id=>!nextValues.has(id))) throw new Error('AssetResultStore snapshot compareIds are invalid');
      values.clear(); nextValues.forEach((value,id)=>values.set(id,copy(value)));
      selectedId=nextSelected; compared.clear(); nextCompare.forEach(id=>compared.add(id)); notify();
    },
  };
  return api;
}

function validateProjectResultState(input) {
  if (input === undefined || input === null) return {results:[],selectedId:null,compareIds:[],library:[]};
  const fail=message=>{throw new Error(`Invalid project Result state: ${message}`);};
  let nodes=0; const seen=new Set();
  const walk=(value,depth=0)=>{
    if(depth>48 || ++nodes>50000) fail('depth/node budget');
    if(value===null || ['string','boolean'].includes(typeof value)) return;
    if(typeof value==='number'){if(!Number.isFinite(value))fail('non-finite number');return;}
    if(typeof value!=='object' || seen.has(value)) fail('not JSON-safe');
    if(!Array.isArray(value) && Object.getPrototypeOf(value)!==Object.prototype && Object.getPrototypeOf(value)!==null) fail('prototype');
    seen.add(value);
    for(const key of Object.keys(value)){if(['__proto__','prototype','constructor'].includes(key))fail('unsafe key');walk(value[key],depth+1);}
    seen.delete(value);
  };
  walk(input); let text; try{text=JSON.stringify(input);}catch(_){fail('serialization');}
  if(new TextEncoder().encode(text).byteLength>64*1024*1024)fail('byte budget');
  const clone=JSON.parse(text);
  if(!Array.isArray(clone.results) || !Array.isArray(clone.compareIds) || !Array.isArray(clone.library)) fail('array contract');
  if(clone.compareIds.length>2) fail('compare limit');
  const results=[], ids=new Set();
  for(const value of clone.results){
    if(ids.has(value?.id))fail('duplicate result id');
    const safe=createAssetResult(value,{clock:()=>value.updatedAt,idFactory:()=>value.id}); ids.add(safe.id); results.push(safe);
  }
  const selectedId=clone.selectedId ?? null;
  if(selectedId!==null && !ids.has(selectedId))fail('dangling selected result');
  if(new Set(clone.compareIds).size!==clone.compareIds.length || clone.compareIds.some(id=>!ids.has(id)))fail('dangling/duplicate compared result');
  const libraryIds=new Set();
  for(const item of clone.library){
    if(!item || typeof item.id!=='string' || libraryIds.has(item.id) || !ids.has(item.resultId))fail('invalid/dangling library item');
    const result=results.find(r=>r.id===item.resultId);
    if(item.family!==result.family || item.type!==result.type)fail('library family mismatch');
    if(typeof item.url!=='string' || item.url.startsWith('blob:'))fail('non-durable library URL');
    libraryIds.add(item.id);
  }
  return JSON.parse(JSON.stringify({results,selectedId,compareIds:clone.compareIds,library:clone.library}));
}

const assetResultStore = createAssetResultStore();
const assetLibrary = [];
const adoptionRecords = [];
const adoptionInFlight = new Set();

async function preflightResultImage(url, limits = {}) {
  const maxBytes=limits.maxBytes || 16*1024*1024, maxDimension=limits.maxDimension || 8192, maxPixels=limits.maxPixels || 33554432, timeout=limits.timeout || 8000;
  if(typeof url !== 'string' || url.startsWith('blob:') || !(/^(data:image\/(png|jpeg|webp);base64,)/i.test(url) || /^(https?:\/\/|\/|\.\/)/.test(url))) throw new Error('Unsafe result image scheme');
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),timeout);
  let response, blob;
  try {
    response=await fetch(url,{signal:controller.signal,credentials:'same-origin'});
    if(!response.ok) throw new Error('Result image fetch failed');
    const mime=(response.headers.get('content-type') || '').split(';')[0].toLowerCase();
    if(!['image/png','image/jpeg','image/webp'].includes(mime)) throw new Error('Unsafe result image MIME');
    const encoded=await response.arrayBuffer();
    if(!encoded.byteLength || encoded.byteLength > maxBytes) throw new Error('Result image encoded bytes exceeded');
    blob=new Blob([encoded],{type:mime});
    const bitmap=await Promise.race([createImageBitmap(blob),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Result image decode timeout')),timeout))]);
    const width=bitmap.width, height=bitmap.height; bitmap.close?.();
    if(!width || !height || width>maxDimension || height>maxDimension || width*height>maxPixels || width*height*4>maxPixels*4) throw new Error('Result image dimensions/pixels/RGBA exceeded');
    return {url,mime,bytes:encoded.byteLength,width,height};
  } finally { clearTimeout(timer); }
}

function loadAdoptionFabricImage(url, timeout=8000) {
  return new Promise((resolve,reject)=>{ let settled=false; const timer=setTimeout(()=>{settled=true;reject(new Error('Result Fabric decode timeout'));},timeout);
    fabric.Image.fromURL(url,img=>{if(settled)return;clearTimeout(timer);if(!img||!img.width||!img.height)reject(new Error('Result Fabric decode failed'));else resolve(img);},{crossOrigin:'anonymous'});
  });
}

async function adoptResult(id, mode) {
  const modes=new Set(['new-layer','replace-source','library']);
  if(!modes.has(mode)) throw new Error('Unknown result adoption mode');
  if(adoptionInFlight.has(id)) throw new Error('Result adoption already in progress');
  const result=assetResultStore.get(id);
  const animationDescriptor=deriveResultSpriteAnimation(result),walkGate=resultWalkQaGate(animationDescriptor,resultWalkReviews.get(id)?.deterministic,resultWalkReviews.get(id)?.manualConfirmed);
  if(!walkGate.allowed) throw new Error(`Result walk QA blocks adoption: ${walkGate.reason}`);
  const qaStatus=String(result?.qaSummary?.status || result?.qaSummary?.direction_qa?.status || '').toUpperCase();
  if(!result || result.status!=='succeeded' || result.rejected || result.adopted || result.error!==null || qaStatus!=='PASS') throw new Error('Result is not adoptable');
  if(result.sourceRequest?.asset_family!==result.family || result.sourceRequest?.asset_type!==result.type || result.normalizedContract?.asset_family!==result.family || result.normalizedContract?.asset_type!==result.type) throw new Error('Result family contract mismatch');
  const durable=[result.preview?.url,...result.artifacts.map(a=>a?.url)].find(url=>typeof url==='string'&&!url.startsWith('blob:'));
  if(!durable) throw new Error('Result has no durable artifact');
  const source=mode==='replace-source' ? canvas.getActiveObject() : null;
  if(mode==='replace-source' && !source) throw new Error('Replace-source requires a selected layer');
  adoptionInFlight.add(id);
  // Generation/result selection is not itself a canvas edit.  Refresh the
  // current entry so undoing adoption returns to an unadopted, re-adoptable result.
  if(history[historyIndex]) Object.assign(history[historyIndex],captureHistoryState());
  const storeSnapshot=assetResultStore.snapshot(), historySnapshot={history:history.slice(),index:historyIndex}, librarySnapshot=assetLibrary.slice(), recordsSnapshot=JSON.parse(JSON.stringify(adoptionRecords));
  const objectsSnapshot=canvas.getObjects().slice(), activeSnapshot=canvas.getActiveObject(), sourceVisible=source?.visible, sourcePreserved=source?._preservedOriginal;
  const rollback=()=>{ canvas.getObjects().slice().forEach(o=>canvas.remove(o)); objectsSnapshot.forEach(o=>canvas.add(o)); if(source){source.visible=sourceVisible;source._preservedOriginal=sourcePreserved;} if(activeSnapshot)canvas.setActiveObject(activeSnapshot);else canvas.discardActiveObject(); assetLibrary.splice(0,assetLibrary.length,...librarySnapshot); adoptionRecords.splice(0,adoptionRecords.length,...recordsSnapshot); history=historySnapshot.history;historyIndex=historySnapshot.index;assetResultStore.restore(storeSnapshot);canvas.renderAll();renderLayers();renderHistory(); };
  try {
    await preflightResultImage(durable);
    if(mode==='library') {
      assetLibrary.push({id:`library-${id}`,resultId:id,family:result.family,type:result.type,url:durable,createdAt:new Date().toISOString()});
    } else {
      const img=await loadAdoptionFabricImage(durable); ensureMeta(img,`${result.family} ${result.type}`);
      img.set({resultId:id,resultFamily:result.family,resultType:result.type,_originalSrc:durable});
      if(mode==='new-layer') { fitToCanvasObject(img); canvas.add(img); }
      else {
        const index=canvas.getObjects().indexOf(source), props=['left','top','originX','originY','scaleX','scaleY','angle','flipX','flipY','skewX','skewY','opacity'];
        const transform={};props.forEach(key=>transform[key]=source[key]); img.set({...transform,replacesLayerId:source.id}); source.visible=false; source._preservedOriginal=true; canvas.insertAt(img,index+1,false);
      }
      canvas.setActiveObject(img); canvas.renderAll();
    }
    assetResultStore.update(id,{adopted:true});
    adoptionRecords.push({resultId:id,mode,libraryId:mode==='library'?`library-${id}`:null,at:new Date().toISOString()});
    saveHistory(mode==='new-layer'?'Result adopted as new layer':mode==='replace-source'?'Result replaced source':'Result adopted to library');
    renderLayers(); return {mode,resultId:id};
  } catch(error) { rollback(); throw error; }
  finally { adoptionInFlight.delete(id); }
}

function assetResultFromGeneration(payload, data) {
  const url = data.url;
  const artifacts = Array.isArray(data.artifacts) && data.artifacts.length ? data.artifacts : [{kind:'image',url}];
  return createAssetResult({ family:payload.asset_family, type:payload.asset_type, status:'succeeded',
    preview:{url}, sourceRequest:payload, normalizedContract:payload, qaSummary:data.qa || null,
    artifacts, adopted:false, rejected:false, error:null });
}

const RESULT_SPRITE_LIMITS=Object.freeze({maxPixels:33554432,maxWorkingBytes:268435456,maxFrames:256});
const resultSpritePlayers=new Map(),resultWalkReviews=new Map();
function deriveResultSpriteAnimation(result) {
  const root=result?.normalizedContract||result?.sourceRequest||{},fallbackRoot=result?.sourceRequest||{},contract=root?.sprite||root,fallback=fallbackRoot?.sprite||fallbackRoot,frameCount=Number(contract.frame_count??contract.walk_frames??fallback.frame_count??fallback.walk_frames),url=result?.preview?.url||result?.artifacts?.find(a=>typeof a?.url==='string')?.url;
  if(result?.status!=='succeeded'||result?.family!=='sprite'||!['character','monster','npc'].includes(result?.type)||!Number.isSafeInteger(frameCount)||frameCount<=1||frameCount>RESULT_SPRITE_LIMITS.maxFrames||typeof url!=='string'||!url)return null;
  const direction=String(contract.target_direction??fallback.target_direction??'S').toUpperCase();if(!['S','N','W','SW','NW','E','SE','NE'].includes(direction))return null;
  let action=String(contract.animation_mode??contract.action??fallback.animation_mode??fallback.action??'').toLowerCase();if(action==='walk'&&frameCount===4)action='walk4';else if(action==='walk'&&frameCount===6)action='walk6';return {url,frameCount,direction,action,fps:Math.min(24,Math.max(1,Number(contract.fps)||8)),autoPlay:true,horizontal:true};
}
function deriveSpriteFrameRectangles(descriptor,image) {
  if(!descriptor||!Number.isSafeInteger(descriptor.frameCount)||!image||!Number.isSafeInteger(image.width)||!Number.isSafeInteger(image.height)||image.width<1||image.height<1)throw new Error('invalid sprite animation geometry');
  const pixels=image.width*image.height,working=pixels*8;if(!Number.isSafeInteger(pixels)||pixels>RESULT_SPRITE_LIMITS.maxPixels||!Number.isSafeInteger(working)||working>RESULT_SPRITE_LIMITS.maxWorkingBytes)throw new Error('sprite animation memory budget exceeded');
  if(image.width%descriptor.frameCount!==0)throw new Error('sprite strip width is inconsistent with frame count');const width=image.width/descriptor.frameCount,height=image.height;if(!Number.isSafeInteger(width)||width<1)throw new Error('invalid sprite frame width');return Array.from({length:descriptor.frameCount},(_,index)=>({index,x:index*width,y:0,width,height}));
}
function deriveWalkBeatLabels(action,count) {if(!Number.isSafeInteger(count)||count<2||count%2)throw new Error('walk frame count must be even');const exact=String(action).toLowerCase()==='walk4'&&count===4,labels=['N','L','N','R'];return Array.from({length:count},(_,i)=>({label:labels[i%4],semantic:exact}));}
function detectRepeatedAnimationFrames(frames) {
  if(!Array.isArray(frames)||frames.length<2)return {status:'UNKNOWN',reason:'insufficient frames'};const bytes=frames.map(f=>f instanceof Uint8Array||f instanceof Uint8ClampedArray?f:null);if(bytes.some(f=>!f||f.length!==bytes[0].length))return {status:'UNKNOWN',reason:'inconsistent pixel buffers'};
  const hash=f=>{let h=2166136261;for(let i=0;i<f.length;i++){h^=f[i];h=Math.imul(h,16777619)}return (h>>>0).toString(16)},hashes=bytes.map(hash),unique=new Set(hashes).size,staticSequence=unique===1||unique<=Math.floor(frames.length/2);return staticSequence?{status:'FAIL',reason:'duplicate or repeated frames',unique,total:frames.length,hashes}:{status:'PASS',reason:'deterministic frames differ',unique,total:frames.length,hashes};
}
function resultWalkQaGate(descriptor,deterministic,manualConfirmed) {const walk=!!descriptor&&String(descriptor.action).startsWith('walk');if(!walk)return {allowed:true,status:'NOT_APPLICABLE'};if(deterministic?.status==='FAIL')return {allowed:false,status:'FAIL',reason:'repeated-frame QA failed'};if(deterministic?.status!=='PASS')return {allowed:false,status:'PENDING',reason:'deterministic motion QA pending'};if(manualConfirmed!==true)return {allowed:false,status:'REVIEW_REQUIRED',reason:'발 교대 확인 필요'};return {allowed:true,status:'PASS'};}
function cleanupResultSpritePlayers(){for(const player of resultSpritePlayers.values()){clearInterval(player.timer);player.image.onload=null;player.image.onerror=null;}resultSpritePlayers.clear()}
function mountResultSpritePlayer(card,result,descriptor,element) {
  const wrap=element('section','result-sprite-animation');wrap.setAttribute('aria-label',`${descriptor.direction} 방향 스프라이트 애니메이션`);const canvas=element('canvas','result-sprite-viewport');canvas.width=320;canvas.height=320;wrap.appendChild(canvas);
  const info=element('div','result-sprite-info',`방향 ${descriptor.direction} · 1/${descriptor.frameCount}`),controls=element('div','result-sprite-controls'),btn=(label,action)=>{const b=element('button','',label);b.type='button';b.dataset.animationAction=action;return b};controls.append(btn('⏮','previous-frame'),btn('일시정지','play-pause'),btn('⏭','next-frame'));const fps=element('input','animation-fps');fps.type='number';fps.min='1';fps.max='24';fps.value=String(descriptor.fps);fps.setAttribute('aria-label','FPS 1에서 24');controls.append(fps);wrap.append(info,controls);card.appendChild(wrap);
  const image=new Image(),player={image,timer:null,playing:true,index:0,fps:descriptor.fps,rects:null};resultSpritePlayers.set(result.id,player);const draw=()=>{if(!player.rects)return;const r=player.rects[player.index],ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,canvas.width,canvas.height);const scale=Math.max(1,Math.floor(Math.min(canvas.width/r.width,canvas.height/r.height))),dw=r.width*scale,dh=r.height*scale;ctx.drawImage(image,r.x,r.y,r.width,r.height,Math.floor((canvas.width-dw)/2),Math.floor((canvas.height-dh)/2),dw,dh);info.textContent=`방향 ${descriptor.direction} · ${player.index+1}/${descriptor.frameCount}`};const start=()=>{clearInterval(player.timer);if(player.playing&&!document.hidden)player.timer=setInterval(()=>{player.index=(player.index+1)%descriptor.frameCount;draw()},1000/player.fps)};
  image.onload=()=>{try{player.rects=deriveSpriteFrameRectangles(descriptor,{width:image.naturalWidth,height:image.naturalHeight});const sample=document.createElement('canvas');sample.width=image.naturalWidth;sample.height=image.naturalHeight;const sx=sample.getContext('2d',{willReadFrequently:true});sx.drawImage(image,0,0);const pixels=player.rects.map(r=>sx.getImageData(r.x,r.y,r.width,r.height).data),qa=detectRepeatedAnimationFrames(pixels),prior=resultWalkReviews.get(result.id)||{};resultWalkReviews.set(result.id,{...prior,deterministic:qa});draw();start();updateResultWalkQaUi(card,result,descriptor)}catch(error){wrap.replaceChildren(element('p','result-sprite-error',`미리보기 차단: ${error.message}`))}};image.onerror=()=>wrap.replaceChildren(element('p','result-sprite-error','스프라이트 이미지를 해독할 수 없습니다.'));image.src=descriptor.url;
  controls.onclick=e=>{const action=e.target.dataset.animationAction;if(!action)return;if(action==='play-pause'){player.playing=!player.playing;e.target.textContent=player.playing?'일시정지':'재생';start()}else{player.playing=false;controls.querySelector('[data-animation-action="play-pause"]').textContent='재생';clearInterval(player.timer);player.index=(player.index+(action==='next-frame'?1:-1)+descriptor.frameCount)%descriptor.frameCount;draw()}};fps.onchange=()=>{player.fps=Math.min(24,Math.max(1,Number(fps.value)||1));fps.value=String(player.fps);start()};
}
function updateResultWalkQaUi(card,result,descriptor){const box=card.querySelector('.result-walk-qa');if(!box)return;const review=resultWalkReviews.get(result.id)||{},gate=resultWalkQaGate(descriptor,review.deterministic,review.manualConfirmed);box.querySelector('.result-walk-qa-status').textContent=gate.allowed?'수동 PASS 완료':gate.status==='FAIL'?'반복 프레임 자동 FAIL':'발 교대 확인 필요';const button=card.querySelector('[data-result-action="manual-walk-pass"]');if(button)button.disabled=review.deterministic?.status!=='PASS';}

function renderAssetResultTray() {
  cleanupResultSpritePlayers();
  const host = $('assetResultCards'), summary = $('assetResultTraySummary'), compareHost=$('assetResultComparison');
  if (!host) return;
  host.replaceChildren();
  const items = assetResultStore.list(), state = assetResultStore.state();
  if (summary) summary.textContent = items.length ? `${items.length}개 결과 · 비교 ${state.compareIds.length}/2` : '결과가 없습니다.';
  const element = (tag, className, text) => { const node=document.createElement(tag); if(className) node.className=className; if(text !== undefined) node.textContent=text; return node; };
  items.slice().reverse().forEach(result => {
    const card=element('article','asset-result-card'+(result.rejected?' rejected':'')); card.setAttribute('role','listitem'); card.setAttribute('aria-selected',String(state.selectedId===result.id)); card.dataset.resultId=result.id;
    const animation=deriveResultSpriteAnimation(result);
    if(animation) mountResultSpritePlayer(card,result,animation,element);
    else if(result.preview?.url) { const img=element('img','asset-result-preview'); img.src=result.preview.url; img.alt=`${result.family} ${result.type} 생성 결과`; card.appendChild(img); }
    const meta=element('div','asset-result-meta'); meta.append(element('strong','',`${result.family} · ${result.type}`),element('span','asset-result-badge',result.status)); card.appendChild(meta);
    const badges=element('div','asset-result-badges');
    if(result.qaSummary) badges.appendChild(element('span','asset-result-badge',`QA ${result.qaSummary.status || result.qaSummary.direction_qa?.status || 'available'}`));
    badges.appendChild(element('span','asset-result-badge',`artifacts ${result.artifacts.length}`)); card.appendChild(badges);
    if(animation&&animation.action.startsWith('walk')){const qa=element('div','result-walk-qa'),status=element('strong','result-walk-qa-status','발 교대 확인 필요'),beats=deriveWalkBeatLabels(animation.action,animation.frameCount).map(x=>x.label).join('→');qa.append(status,element('span','result-walk-beats',`${beats}${animation.action==='walk4'?'':' · 의미 판정 아님'}`));card.appendChild(qa)}
    const actions=element('div','asset-result-actions');
    const button=(label,action,disabled=false)=>{const b=element('button','',label);b.type='button';b.dataset.resultAction=action;b.disabled=disabled;return b;};
    const walkGate=animation?resultWalkQaGate(animation,resultWalkReviews.get(result.id)?.deterministic,resultWalkReviews.get(result.id)?.manualConfirmed):{allowed:true};
    actions.append(button(state.selectedId===result.id?'선택됨':'선택','select'),button(state.compareIds.includes(result.id)?'비교 해제':'비교','compare',!state.compareIds.includes(result.id)&&state.compareIds.length>=2));
    if(animation?.action.startsWith('walk'))actions.append(button('동작/발 교대 수동 PASS','manual-walk-pass',resultWalkReviews.get(result.id)?.deterministic?.status!=='PASS'));
    actions.append(button('채택','adopt',result.adopted||result.rejected||result.status!=='succeeded'||!walkGate.allowed),button('재시도','retry'),button(result.rejected?'거절됨':'거절','reject',result.rejected));
    card.appendChild(actions); host.appendChild(card);
  });
  if(compareHost){
    compareHost.replaceChildren(); compareHost.hidden=state.compareIds.length===0;
    state.compareIds.map(id=>items.find(item=>item.id===id)).filter(Boolean).forEach(result=>{
      const panel=element('article','asset-result-compare-item'); panel.setAttribute('aria-label',`${result.family} ${result.type} 비교`);
      if(result.preview?.url){const img=element('img','asset-result-compare-preview');img.src=result.preview.url;img.alt=`${result.family} ${result.type} 비교 미리보기`;panel.appendChild(img);}
      const qa=result.qaSummary?.status||result.qaSummary?.direction_qa?.status||'없음', dl=element('dl','asset-result-compare-summary');
      panel.appendChild(element('strong','',`${result.family} · ${result.type}`));
      [['상태',result.status],['QA',qa],['아티팩트',String(result.artifacts.length)]].forEach(([key,value])=>dl.append(element('dt','',key),element('dd','',value)));
      panel.appendChild(dl); compareHost.appendChild(panel);
    });
  }
}

async function retryAssetResult(id) {
  const previous=assetResultStore.get(id); if(!previous) throw new Error('Unknown result');
  const payload=previous.sourceRequest, endpoint=payload.reference_image?'/api/generate-reference':'/api/generate';
  const res=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}), data=await res.json();
  if(!res.ok||!data.success) throw new Error(data.error||'generation failed');
  const next=assetResultFromGeneration(payload,data); assetResultStore.add(next); assetResultStore.select(next.id); return next;
}

assetResultStore.subscribe(renderAssetResultTray);
$('assetResultCards')?.addEventListener('click', event => {
  const button=event.target.closest('button[data-result-action]'), card=event.target.closest('[data-result-id]'); if(!button||!card) return;
  const id=card.dataset.resultId, action=button.dataset.resultAction;
  try {
    if(action==='select') assetResultStore.select(id);
    else if(action==='compare') assetResultStore.toggleCompare(id);
    else if(action==='reject') assetResultStore.update(id,{rejected:true});
    else if(action==='adopt') adoptResult(id,$('assetResultAdoptMode')?.value||'new-layer').catch(err=>setStatus(`채택 실패: ${err.message}`));
    else if(action==='manual-walk-pass'){const result=assetResultStore.get(id),descriptor=deriveResultSpriteAnimation(result),prior=resultWalkReviews.get(id)||{};if(prior.deterministic?.status!=='PASS')throw new Error('반복 프레임 QA 통과 후 확인할 수 있습니다');resultWalkReviews.set(id,{...prior,manualConfirmed:true,confirmedAt:new Date().toISOString()});renderAssetResultTray()}
    else if(action==='retry') retryAssetResult(id).catch(err=>setStatus(`재시도 실패: ${err.message}`));
  } catch(err) { setStatus(err.message); }
});
renderAssetResultTray();
document.addEventListener('visibilitychange',()=>{if(document.hidden)for(const player of resultSpritePlayers.values()){clearInterval(player.timer);player.timer=null;}});
window.__assetResultApi = { createAssetResult, transitionAssetResult, createAssetResultStore, store:assetResultStore, render:renderAssetResultTray, retry:retryAssetResult, adoptResult, library:assetLibrary };

function setRightPanelTab(tab) {
  const normalizedTab = ['properties', 'layers', 'export'].includes(tab) ? tab : 'properties';
  const views = {
    properties: $('propertiesPanel'),
    layers: $('layersPanel'),
    export: $('exportPanel'),
  };

  Object.entries(views).forEach(([viewTab, view]) => {
    const isActive = viewTab === normalizedTab;
    view?.classList.toggle('hidden', !isActive);
    view?.classList.toggle('active', isActive);
  });

  document.querySelectorAll('#rightPanelTabs [data-right-panel-tab]').forEach(button => {
    const isActive = button.dataset.rightPanelTab === normalizedTab;
    button.setAttribute('aria-selected', String(isActive));
    button.setAttribute('tabindex', isActive ? '0' : '-1');
    button.classList.toggle('active', isActive);
  });
}

$('rightPanelTabs')?.addEventListener('click', event => {
  const button = event.target.closest('[data-right-panel-tab]');
  if (!button || !event.currentTarget.contains(button)) return;
  setRightPanelTab(button.dataset.rightPanelTab);
});
$('rightPanelTabs')?.addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;

  const tabs = Array.from(event.currentTarget.querySelectorAll('[role="tab"]'));
  const focusedIndex = tabs.indexOf(document.activeElement);
  const selectedIndex = tabs.findIndex(tab => tab.getAttribute('aria-selected') === 'true');
  const currentIndex = focusedIndex >= 0 ? focusedIndex : Math.max(selectedIndex, 0);
  let nextIndex;

  if (event.key === 'Home') nextIndex = 0;
  else if (event.key === 'End') nextIndex = tabs.length - 1;
  else if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
  else nextIndex = (currentIndex + 1) % tabs.length;

  event.preventDefault();
  const nextTab = tabs[nextIndex];
  setRightPanelTab(nextTab.dataset.rightPanelTab);
  nextTab.focus();
});
setRightPanelTab('properties');

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

const PIXEL_ACTOR_ASSET_TYPES = new Set(['character', 'monster', 'npc']);
const PIXEL_EFFECT_ASSET_TYPES = new Set(['effect']);

const ASSET_FAMILY_SUBTYPES = {
  sprite: ['character', 'monster', 'npc', 'effect'],
  tile: ['floor', 'wall', 'corner', 'door', 'terrain', 'decal', 'autotile', 'tileset'],
  ui: ['main_panel', 'inner_panel', 'popup', 'card', 'button', 'slot', 'badge', 'hud_chip', 'gauge', 'icon', 'cursor'],
  object: ['item', 'equipment', 'weapon', 'loot', 'furniture', 'machine', 'prop', 'interactable', 'destructible'],
};
const ASSET_SUBTYPE_LABELS = {
  character:'캐릭터', monster:'몬스터', npc:'NPC', effect:'이펙트', floor:'바닥', wall:'벽', corner:'모서리', door:'문/통로', terrain:'지형', decal:'데칼', autotile:'오토타일', tileset:'타일셋', main_panel:'메인 패널', inner_panel:'내부 패널', popup:'팝업', card:'카드', button:'버튼', slot:'슬롯', badge:'상태 배지', hud_chip:'HUD 칩', gauge:'게이지', icon:'아이콘', cursor:'커서/선택 표시', item:'아이템', equipment:'장비', weapon:'무기', loot:'전리품', furniture:'가구', machine:'기계/도구', prop:'환경 소품', interactable:'상호작용 오브젝트', destructible:'파괴 상태 오브젝트',
};
let selectedAssetFamily = 'sprite';
const ASSET_FAMILY_CREATION_COPY = {
  sprite: { label: '생성할 캐릭터·몬스터·NPC·이펙트', placeholder: '예: 낡은 은빛 갑옷을 입은 해골 기사, 붉은 망토와 녹슨 장검', help: '외형, 역할, 분위기와 반드시 포함할 특징을 적으세요.' },
  tile: { label: '생성할 타일·맵의 재질·환경·용도', placeholder: '예: 이끼 낀 석조 던전 바닥, 습한 지하 묘지용 심리스 타일', help: '재질, 환경, 연결 방식과 실제 맵 용도를 적으세요.' },
  ui: { label: '생성할 UI의 기능·구조·시각 콘셉트', placeholder: '예: 인벤토리 아이템 상세 팝업, 제목·슬롯·확인 버튼 구조', help: '기능, 정보 구조, 상태와 시각적 위계를 적으세요.' },
  object: { label: '생성할 오브젝트의 형태·재질·용도', placeholder: '예: 황동 보물 상자, 모서리가 닳은 참나무 몸체, 던전 전리품 보관용', help: '형태, 재질, 크기감, 상태와 월드 내 용도를 적으세요.' },
};
const ASSET_FAMILY_OUTPUT_DEFAULTS = {
  sprite: { width: 512, height: 512, background: 'transparent' },
  tile: { width: 512, height: 512, background: 'opaque' },
  ui: { width: 1024, height: 512, background: 'transparent' },
  object: { width: 512, height: 512, background: 'transparent' },
};
const assetFamilyDrafts = new Map();
const PROJECT_FAMILIES = ['sprite','tile','ui','object'];
const PROJECT_DRAFT_SHARED_CONTROLS = ['assetCorePrompt','assetOutputWidth','assetOutputHeight','assetBackground'];
const PROJECT_DRAFT_FAMILY_CONTROLS = {
  sprite:['pixelAnimationPreset','pixelDirectionMode','pixelTargetDirection','pixelReferenceDirection','pixelChromaMode','pixelPalette','effectSequenceMode','effectCategory','effectLoop','effectFrameCount','effectFps','effectRows','effectColumns','effectGap','effectEnvelopeWidth','effectEnvelopeHeight','effectSizeBasis','effectPivot','effectPivotX','effectPivotY','effectTrimPolicy'],
  tile:['tileEnvironment','tileMaterial','tileUse','tileWidth','tileHeight','tileShape','tileMargin','tileSpacing','tileMode','tileRows','tileColumns','tileSeamless','tileTopology','tileInnerCorners','tileOuterCorners','tileTransitions','tileTerrainTypes','tileVariants','tileCollision','tileOcclusion','tileNavigation','tileCustomMetadata'],
  ui:['uiPurpose','uiInformationStructure','uiSourceWidth','uiSourceHeight','uiSizingMode','uiSliceMargins','uiSliceTop','uiSliceRight','uiSliceBottom','uiSliceLeft','uiContentSafeArea','uiContentSafeTop','uiContentSafeRight','uiContentSafeBottom','uiContentSafeLeft','uiPadding','uiPaddingTop','uiPaddingRight','uiPaddingBottom','uiPaddingLeft','uiBorder','uiBorderStyle','uiBorderWidth','uiCorner','uiCornerStyle','uiCornerRadius','uiDecorDensity','uiEdgeMode','uiCenterMode','uiOpacity','uiStates','uiTargetWidth','uiTargetHeight','uiDeviceSafeArea','uiDeviceSafeTop','uiDeviceSafeRight','uiDeviceSafeBottom','uiDeviceSafeLeft'],
  object:['objectUsage','objectIdentitySubtype','objectForm','objectMaterial','objectFunction','objectView','objectScaleBasis','objectTileRelativeWidth','objectTileRelativeHeight','objectCharacterRelative','objectFootprintWidth','objectFootprintDepth','objectSourceWidth','objectSourceHeight','objectPaddingTop','objectPaddingRight','objectPaddingBottom','objectPaddingLeft','objectPivotX','objectPivotY','objectGroundX','objectGroundY','objectYSortX','objectYSortY','objectSnapPoints','objectShadowMode','objectShadowBaked','objectStates','objectVariantDefinitions','objectCollision','objectInteraction','objectCustomProperties'],
};
let projectV2Identity = null;

function defaultProjectFamilyDraft(family) {
  const output=ASSET_FAMILY_OUTPUT_DEFAULTS[family];
  return {subtype:ASSET_FAMILY_SUBTYPES[family][0],controls:{assetCorePrompt:'',assetOutputWidth:String(output.width),assetOutputHeight:String(output.height),assetBackground:output.background}};
}

function validateProjectFamilyDrafts(input) {
  const plain=value=>value&&typeof value==='object'&&!Array.isArray(value)&&(Object.getPrototypeOf(value)===Object.prototype||Object.getPrototypeOf(value)===null);
  if(input===undefined)return Object.fromEntries(PROJECT_FAMILIES.map(f=>[f,defaultProjectFamilyDraft(f)]));
  if(!plain(input)||Object.keys(input).length!==4||PROJECT_FAMILIES.some(f=>!Object.prototype.hasOwnProperty.call(input,f)))throw new Error('Invalid familyDrafts: four families required');
  const out={};let bytes=0;
  for(const family of PROJECT_FAMILIES){
    const draft=input[family], allowed=new Set([...PROJECT_DRAFT_SHARED_CONTROLS,...PROJECT_DRAFT_FAMILY_CONTROLS[family]]);
    if(!plain(draft)||Object.keys(draft).some(k=>!['subtype','controls'].includes(k))||!ASSET_FAMILY_SUBTYPES[family].includes(draft.subtype)||!plain(draft.controls))throw new Error(`Invalid familyDrafts.${family}`);
    if(Object.keys(draft.controls).some(id=>!allowed.has(id)))throw new Error(`Invalid familyDrafts.${family}: control allow-list`);
    const controls={};
    for(const [id,value] of Object.entries(draft.controls)){
      if(typeof value!=='string'&&typeof value!=='boolean')throw new Error(`Invalid familyDrafts.${family}.${id}`);
      if(typeof value==='string'&&(value.length>8192||(bytes+=new TextEncoder().encode(value).length)>262144))throw new Error('Invalid familyDrafts: size budget');
      if((id==='assetOutputWidth'||id==='assetOutputHeight') && (typeof value!=='string'||!/^\+?\d+$/.test(value)||Number(value)<1||Number(value)>4096))throw new Error(`Invalid familyDrafts.${family}.${id}: integer 1..4096 required`);
      if(id==='assetBackground' && (typeof value!=='string'||!['transparent','chroma_green','opaque'].includes(value)))throw new Error(`Invalid familyDrafts.${family}.${id}: background`);
      controls[id]=value;
    }
    out[family]={subtype:draft.subtype,controls};
  }
  return JSON.parse(JSON.stringify(out));
}

function serializeProjectFamilyDrafts() {
  saveAssetCreationDraft(currentAssetFamily());
  const result={};
  for(const family of PROJECT_FAMILIES){
    const stored=assetFamilyDrafts.get(family), controls={};
    for(const id of [...PROJECT_DRAFT_SHARED_CONTROLS,...PROJECT_DRAFT_FAMILY_CONTROLS[family]]){
      const element=$(id); let value;
      if(family===currentAssetFamily()&&element)value=element.type==='checkbox'?!!element.checked:(element.dataset.projectHydratedValue??String(element.value));
      else if(stored&&Object.prototype.hasOwnProperty.call(stored,id))value=stored[id];
      else if(stored&&id==='assetCorePrompt')value=stored.core;
      else if(stored&&id==='assetOutputWidth')value=String(stored.width);
      else if(stored&&id==='assetOutputHeight')value=String(stored.height);
      else if(stored&&id==='assetBackground')value=stored.background;
      if(typeof value==='string'||typeof value==='boolean')controls[id]=value;
    }
    result[family]={subtype:family===currentAssetFamily()?(currentAssetSubtype()||ASSET_FAMILY_SUBTYPES[family][0]):(stored?.subtype||ASSET_FAMILY_SUBTYPES[family][0]),controls};
  }
  return validateProjectFamilyDrafts(result);
}

function hydrateProjectFamilyDrafts(drafts,selectedFamily) {
  const valid=validateProjectFamilyDrafts(drafts), family=PROJECT_FAMILIES.includes(selectedFamily)?selectedFamily:'sprite';
  assetFamilyDrafts.clear();
  for(const name of PROJECT_FAMILIES){const d=valid[name],c=d.controls;assetFamilyDrafts.set(name,{...c,subtype:d.subtype,core:c.assetCorePrompt??'',width:c.assetOutputWidth??String(ASSET_FAMILY_OUTPUT_DEFAULTS[name].width),height:c.assetOutputHeight??String(ASSET_FAMILY_OUTPUT_DEFAULTS[name].height),background:c.assetBackground??ASSET_FAMILY_OUTPUT_DEFAULTS[name].background});}
  selectedAssetFamily=family;renderAssetSubtypeOptions(family,valid[family].subtype);
  for(const [id,value] of Object.entries(valid[family].controls)){const element=$(id);if(element){if(element.type==='checkbox')element.checked=value;else {element.value=value;element.dataset.projectHydratedValue=value;if(!element.dataset.projectHydratedListener){element.addEventListener('input',()=>delete element.dataset.projectHydratedValue);element.dataset.projectHydratedListener='1';}}}}
  restoreAssetCreationDraft(family);updateAssetFamilyUi();
}
const controlValue = (id, fallback = '') => $(id)?.value ?? fallback;
const controlNumber = (id, fallback = 0) => {
  const value = Number(controlValue(id, fallback));
  return Number.isFinite(value) ? value : fallback;
};
const clampFamilyNumber = (value, min, max) => Math.min(max, Math.max(min, value));
const controlChecked = (id, fallback = false) => $(id) ? !!$(id).checked : fallback;
let assetGenerationInFlight = null;

function currentAssetFamily() {
  return ASSET_FAMILY_SUBTYPES[selectedAssetFamily] ? selectedAssetFamily : null;
}

function currentAssetSubtype() {
  const family = currentAssetFamily();
  const subtype = $('assetSubtype')?.value;
  return family && ASSET_FAMILY_SUBTYPES[family].includes(subtype) ? subtype : null;
}

function renderAssetSubtypeOptions(family, preferred = '') {
  family = family || currentAssetFamily();
  const select = $('assetSubtype');
  if (!select) return;
  const values = ASSET_FAMILY_SUBTYPES[family] || ASSET_FAMILY_SUBTYPES.sprite;
  select.replaceChildren(...values.map(value => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = ASSET_SUBTYPE_LABELS[value] || value;
    return option;
  }));
  select.value = values.includes(preferred) ? preferred : values[0];
}

function saveAssetCreationDraft(family = currentAssetFamily()) {
  if (!$('assetCorePrompt')) return;
  const defaults = ASSET_FAMILY_OUTPUT_DEFAULTS[family] || ASSET_FAMILY_OUTPUT_DEFAULTS.sprite;
  const draft={
    core: controlValue('assetCorePrompt', ''),
    width: $('assetOutputWidth')?.dataset.projectHydratedValue??controlValue('assetOutputWidth', String(defaults.width)),
    height: $('assetOutputHeight')?.dataset.projectHydratedValue??controlValue('assetOutputHeight', String(defaults.height)),
    background: controlValue('assetBackground', defaults.background),
    subtype:currentAssetSubtype()||ASSET_FAMILY_SUBTYPES[family][0],
  };
  for(const id of PROJECT_DRAFT_FAMILY_CONTROLS[family]||[]){const element=$(id);if(element)draft[id]=element.type==='checkbox'?!!element.checked:String(element.value);}
  assetFamilyDrafts.set(family,draft);
}

function restoreAssetCreationDraft(family = currentAssetFamily()) {
  const copy = ASSET_FAMILY_CREATION_COPY[family] || ASSET_FAMILY_CREATION_COPY.sprite;
  const defaults = ASSET_FAMILY_OUTPUT_DEFAULTS[family] || ASSET_FAMILY_OUTPUT_DEFAULTS.sprite;
  const draft = assetFamilyDrafts.get(family) || { core: '', ...defaults };
  if ($('assetCorePromptLabel')) $('assetCorePromptLabel').textContent = copy.label;
  if ($('assetCorePrompt')) {
    $('assetCorePrompt').placeholder = copy.placeholder;
    $('assetCorePrompt').value = draft.core;
  }
  if ($('assetCorePromptHelp')) $('assetCorePromptHelp').textContent = copy.help;
  if ($('assetOutputWidth')) $('assetOutputWidth').value = String(draft.width);
  if ($('assetOutputHeight')) $('assetOutputHeight').value = String(draft.height);
  if ($('assetBackground')) $('assetBackground').value = draft.background;
  for(const id of PROJECT_DRAFT_FAMILY_CONTROLS[family]||[]){const element=$(id);if(element&&Object.prototype.hasOwnProperty.call(draft,id)){if(element.type==='checkbox')element.checked=!!draft[id];else element.value=draft[id];}}
}

function updateAssetFamilyUi() {
  const family = currentAssetFamily();
  const subtype = currentAssetSubtype();
  ['spriteSettings', 'tileSettings', 'uiSettings', 'objectSettings'].forEach(id => {
    $(id)?.classList.toggle('hidden', id !== `${family}Settings`);
  });
  const actor = ['character', 'monster', 'npc'].includes(subtype);
  const effect = subtype === 'effect';
  ['pixelMotionControls', 'pixelDirectionControls', 'pixelReferenceControls', 'pixelFrameControls', 'pixelLegacyDirectionControls', 'pixelAdvancedBatch'].forEach(id => $(id)?.classList.toggle('hidden', !actor));
  $('effectControls')?.classList.toggle('hidden', !effect);
  $('effectSequencePreviewPanel')?.classList.toggle('hidden', !effect);
  $('tilePreviewPanel')?.classList.toggle('hidden', family !== 'tile');
  $('uiNineSlicePreviewPanel')?.classList.toggle('hidden', family !== 'ui');
  $('objectPlacementPreviewPanel')?.classList.toggle('hidden', family !== 'object');
  document.querySelectorAll('#assetFamilyTabs [data-asset-family]').forEach(tab => {
    const active = tab.dataset.assetFamily === family;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
    tab.setAttribute('tabindex', active ? '0' : '-1');
  });
  const legacy = $('pixelAssetType');
  if (legacy) legacy.value = legacyAssetTypeForFamily(family, subtype);
  syncPixelAssetWorkflowUi({ silent: true });
  syncEffectExportControlsState();
  if ($('familyGenerateAi')) $('familyGenerateAi').textContent = `${ASSET_SUBTYPE_LABELS[subtype] || subtype} AI 생성`;
}

function legacyAssetTypeForFamily(family, subtype) {
  if (family === 'sprite') return ['character', 'monster', 'npc', 'effect'].includes(subtype) ? subtype : 'character';
  if (family === 'tile') return 'tile';
  if (family === 'ui') return ['button', 'icon'].includes(subtype) ? subtype : 'ui_panel';
  if (family === 'object') return 'item';
  return 'character';
}

function setAssetFamily(family, subtype = '') {
  if (!ASSET_FAMILY_SUBTYPES[family]) return;
  saveAssetCreationDraft(currentAssetFamily());
  selectedAssetFamily = family;
  renderAssetSubtypeOptions(family, subtype);
  restoreAssetCreationDraft(family);
  updateAssetFamilyUi();
}

function buildSpriteContract(subtype) {
  if (subtype === undefined) subtype = currentAssetSubtype();
  if (subtype === 'effect') {
    const sequenceMode = controlValue('effectSequenceMode', 'sequence') === 'static' ? 'static' : 'sequence';
    const frameCount = sequenceMode === 'static' ? 1 : clampFamilyNumber(controlNumber('effectFrameCount', 6), 1, 64);
    const rows = clampFamilyNumber(controlNumber('effectRows', 1), 1, 64);
    const requestedColumns = clampFamilyNumber(controlNumber('effectColumns', 6), 1, 64);
    return {
      sequence_mode: sequenceMode,
      animation_mode: sequenceMode === 'static' ? 'static' : 'effect_sequence',
      effect_category: controlValue('effectCategory', 'Slash'),
      loop: controlValue('effectLoop', 'one-shot'),
      frame_count: frameCount,
      fps: clampFamilyNumber(controlNumber('effectFps', 12), 1, 120),
      rows,
      columns: Math.max(requestedColumns, Math.ceil(frameCount / rows)),
      gap: clampFamilyNumber(controlNumber('effectGap', 0), 0, 1024),
      envelope_width: clampFamilyNumber(controlNumber('effectEnvelopeWidth', 64), 1, 4096),
      envelope_height: clampFamilyNumber(controlNumber('effectEnvelopeHeight', 64), 1, 4096),
      size_basis: controlValue('effectSizeBasis', 'actor-relative'),
      pivot: {
        preset: controlValue('effectPivot', 'center'),
        x: clampFamilyNumber(controlNumber('effectPivotX', 0.5), 0, 1),
        y: clampFamilyNumber(controlNumber('effectPivotY', 0.5), 0, 1),
      },
      trim_policy: controlValue('effectTrimPolicy', 'preserve-envelope'),
      no_baked_vfx: false,
    };
  }
  const actorTypes = ['character', 'monster', 'npc'];
  if (!actorTypes.includes(subtype)) throw new Error('Invalid sprite asset subtype');
  const rawAction = controlValue('pixelAnimationPreset', 'idle');
  return {
    animation_mode: rawAction.startsWith('walk') ? 'walk' : rawAction,
    direction_mode: controlValue('pixelDirectionMode', 'single'),
    frame_count: pixelPresetFrameCount(rawAction),
    target_direction: controlValue('pixelTargetDirection', 'S'),
    reference_direction: controlValue('pixelReferenceDirection', 'S'),
    walk_frames: pixelPresetFrameCount(rawAction), chroma_mode: controlValue('pixelChromaMode', 'global'),
    preservation: { identity_lock: true, equipment_lock: true, palette: controlValue('pixelPalette', ''), root_foot_lock: true, silhouette_lock: true },
    no_baked_vfx: true,
  };
}

function buildTileContract() {

  const list = id => controlValue(id, '').split(',').map(value => value.trim()).filter(Boolean);
  const json = (id, label, expected) => {
    let value;
    try { value = JSON.parse(controlValue(id, expected === 'array' ? '[]' : '{}')); }
    catch (_) { throw new Error(`${label}: 올바른 JSON을 입력하세요.`); }
    const valid = expected === 'array' ? Array.isArray(value) : value && typeof value === 'object' && !Array.isArray(value);
    if (!valid) throw new Error(`${label}: JSON ${expected === 'array' ? '배열' : '객체'}이어야 합니다.`);
    return value;
  };
  return {
    environment: controlValue('tileEnvironment', '').trim(), material: controlValue('tileMaterial', '').trim(), use: controlValue('tileUse', '').trim(),
    tile_size: { width: controlNumber('tileWidth', 32), height: controlNumber('tileHeight', 32) }, shape: controlValue('tileShape', 'square'),
    margin: controlNumber('tileMargin', 0), spacing: controlNumber('tileSpacing', 0), mode: controlValue('tileMode', 'single'),
    rows: controlNumber('tileRows', 1), columns: controlNumber('tileColumns', 1), seamless: controlChecked('tileSeamless', true),
    topology: controlValue('tileTopology', 'corner+edge'), inner_corners: controlChecked('tileInnerCorners', true), outer_corners: controlChecked('tileOuterCorners', true),
    transitions: list('tileTransitions'), terrain_types: list('tileTerrainTypes'), variants: json('tileVariants', '변형', 'array'),
    metadata: { collision: json('tileCollision', '충돌 메타데이터', 'object'), occlusion: json('tileOcclusion', '가림 메타데이터', 'object'), navigation: json('tileNavigation', '이동 메타데이터', 'object'), custom: json('tileCustomMetadata', '사용자 메타데이터', 'object') },
  };
}

function buildUiContract() {
  // Ratified limits; names and values mirror server.py and the HTML max attributes.
  const UI_MAX_DIMENSION = 16384, UI_MAX_EDGE = 16384;
  const parse = (id, kind) => { try { const v=JSON.parse(controlValue(id,'')); if ((kind==='array'&&Array.isArray(v))||(kind==='object'&&v&&typeof v==='object'&&!Array.isArray(v))) return v; } catch (_) {} throw new Error(`${id}: malformed JSON/list`); };
  const integer = (value, minimum, maximum, label) => { const n=typeof value==='number'?value:Number(value); if(!Number.isSafeInteger(n)||n<minimum||n>maximum) throw new Error(`${label}: safe integer in ${minimum}..${maximum} required`); return n; };
  const list = id => {
    const fallback = id === 'uiStates' ? 'normal,hover,pressed,disabled' : 'header,content,actions';
    const raw = controlValue(id, fallback), label = id === 'uiStates' ? 'UI states' : 'UI information structure regions';
    const isJson=raw.trim().startsWith('['),source = isJson ? parse(id, 'array') : raw.split(',').filter(value => value.trim());
    if (!source.length && !(id === 'uiStates' && isJson)) throw new Error(`${label}: nonempty list required`);
    if (source.some(value => typeof value !== 'string' || !value.trim())) throw new Error(`${label}: every ID must be a nonempty string`);
    const values=source.map(value=>value.trim()); if(new Set(values).size!==values.length) throw new Error(`${label}: IDs must be unique`); return values;
  };
  const box = (id,prefix,label) => { const raw=$(id)?parse(id,'object'):Object.fromEntries(['top','right','bottom','left'].map(k=>[k,controlValue(`${prefix}${k[0].toUpperCase()+k.slice(1)}`,0)])); return Object.fromEntries(['top','right','bottom','left'].map(k=>[k,integer(raw[k],0,UI_MAX_EDGE,`${label}.${k}`)])); };
  const enumValue=(id,fallback,allowed,label)=>{const value=controlValue(id,fallback);if(!allowed.includes(value))throw new Error(`${label}: invalid enum`);return value;};
  const source={width:integer(controlValue('uiSourceWidth',320),1,UI_MAX_DIMENSION,'source_size.width'),height:integer(controlValue('uiSourceHeight',180),1,UI_MAX_DIMENSION,'source_size.height')};
  const slices=box('uiSliceMargins','uiSlice','slice_margins');
  if(slices.left+slices.right>source.width)throw new Error('slice_margins.left + slice_margins.right exceeds source_size.width');
  if(slices.top+slices.bottom>source.height)throw new Error('slice_margins.top + slice_margins.bottom exceeds source_size.height');
  const border=$( 'uiBorder')?parse('uiBorder','object'):{style:controlValue('uiBorderStyle','solid'),width:controlValue('uiBorderWidth',1)};
  const corner=$( 'uiCorner')?parse('uiCorner','object'):{style:controlValue('uiCornerStyle','rounded'),radius:controlValue('uiCornerRadius',8)};
  if(typeof border.style!=='string'||!border.style.trim())throw new Error('border.style: nonempty string required'); border.width=integer(border.width,0,UI_MAX_EDGE,'border.width');
  if(typeof corner.style!=='string'||!corner.style.trim())throw new Error('corner.style: nonempty string required'); corner.radius=integer(corner.radius,0,UI_MAX_EDGE,'corner.radius');
  const opacity=Number(controlValue('uiOpacity',1)); if(!Number.isFinite(opacity)||opacity<0||opacity>1)throw new Error('opacity: finite number in 0..1 required');
  const purpose=String(controlValue('uiPurpose','reusable interface component')).trim(); if(!purpose)throw new Error('purpose: nonempty string required');
  const states=list('uiStates');
  return {
    purpose, information_structure:list('uiInformationStructure'), source_size:source, sizing_mode:enumValue('uiSizingMode','nine-slice',['fixed','nine-slice'],'sizing_mode'),
    slice_margins:slices, content_safe_area:box('uiContentSafeArea','uiContentSafe','content_safe_area'), padding:box('uiPadding','uiPadding','padding'),
    border:{style:border.style.trim(),width:border.width}, corner:{style:corner.style.trim(),radius:corner.radius},
    decor_density:enumValue('uiDecorDensity','medium',['low','medium','high'],'decor_density'), edge_mode:enumValue('uiEdgeMode','stretch',['stretch','tile'],'edge_mode'), center_mode:enumValue('uiCenterMode','stretch',['stretch','tile'],'center_mode'), opacity, states:states.length?states:['base'],
    target_resolution:{width:integer(controlValue('uiTargetWidth',1920),1,UI_MAX_DIMENSION,'target_resolution.width'),height:integer(controlValue('uiTargetHeight',1080),1,UI_MAX_DIMENSION,'target_resolution.height')}, device_safe_area:box('uiDeviceSafeArea','uiDeviceSafe','device_safe_area'),
    text_free:true, animation_mode:'ui_static', frame_count:1, direction_mode:'none'
  };
}

function buildObjectContract() {
  let nodes=0;
  const safe=(v,p='object',d=0)=>{if(d>16||++nodes>4096)throw new Error(`${p}: JSON complexity limit`);if(typeof v==='string'){if(v.length>8192)throw new Error(`${p}: string too long`);return v;}if(v===null||typeof v==='boolean')return v;if(typeof v==='number'){if(!Number.isFinite(v)||(Number.isInteger(v)&&!Number.isSafeInteger(v)))throw new Error(`${p}: unsafe number`);return v;}if(Array.isArray(v)){if(v.length>256)throw new Error(`${p}: array too long`);return v.map(x=>safe(x,`${p}[]`,d+1));}if(v&&typeof v==='object'){const keys=Object.keys(v);if(keys.length>256||keys.some(k=>['__proto__','prototype','constructor'].includes(k)||k.length>128))throw new Error(`${p}: forbidden keys`);const out=Object.create(null);for(const k of keys)out[k]=safe(v[k],`${p}.${k}`,d+1);return out;}throw new Error(`${p}: JSON-safe value required`);};
  const json = (id, kind) => {
    let value;
    try { value = JSON.parse(controlValue(id, kind === 'array' ? '[]' : '{}')); }
    catch (_) { throw new Error(`${id}: 올바른 JSON이 필요합니다.`); }
    if ((kind === 'array' && !Array.isArray(value)) || (kind === 'object' && (!value || typeof value !== 'object' || Array.isArray(value)))) throw new Error(`${id}: JSON ${kind} required`);
    return safe(value,id);
  };
  const n = (id, fallback, min = -1000000, max = 1000000, integer=false) => { const value=Number(controlValue(id,fallback)); if(!Number.isFinite(value)||value<min||value>max||(integer&&!Number.isSafeInteger(value))) throw new Error(`${id}: finite number in bounds required`); return value; };
  const contract = {
    usage: controlValue('objectUsage','world'),
    identity: { subtype: controlValue('objectIdentitySubtype',currentAssetSubtype()), form:controlValue('objectForm','').trim(), material:controlValue('objectMaterial','').trim(), function:controlValue('objectFunction','').trim() },
    view: controlValue('objectView','three-quarter'),
    scale: { basis:controlValue('objectScaleBasis','tile-relative'), tile_relative:{width:n('objectTileRelativeWidth',1,0),height:n('objectTileRelativeHeight',1,0)}, character_relative:n('objectCharacterRelative',1,0), footprint:{width:n('objectFootprintWidth',1,0),depth:n('objectFootprintDepth',1,0)} },
    source: { canvas:{width:n('objectSourceWidth',512,1,4096,true),height:n('objectSourceHeight',512,1,4096,true)}, padding:{top:n('objectPaddingTop',0,0,4096,true),right:n('objectPaddingRight',0,0,4096,true),bottom:n('objectPaddingBottom',0,0,4096,true),left:n('objectPaddingLeft',0,0,4096,true)} },
    placement: { pivot:{x:n('objectPivotX',0.5),y:n('objectPivotY',1)}, ground_point:{x:n('objectGroundX',0.5),y:n('objectGroundY',1)}, y_sort_point:{x:n('objectYSortX',0.5),y:n('objectYSortY',1)}, snap_points:json('objectSnapPoints','array') },
    shadow:{mode:controlValue('objectShadowMode','contact'),baked:controlChecked('objectShadowBaked',false)}, states:json('objectStates','array'), variants:json('objectVariantDefinitions','array'), collision:json('objectCollision','object'), interaction:json('objectInteraction','object'), custom_properties:json('objectCustomProperties','object')
  };
  if(contract.source.canvas.width*contract.source.canvas.height>16777216||contract.source.padding.left+contract.source.padding.right>contract.source.canvas.width||contract.source.padding.top+contract.source.padding.bottom>contract.source.canvas.height)throw new Error('object source geometry exceeds budget');
  const checked=safe(contract);if(new TextEncoder().encode(JSON.stringify(checked)).length>262144)throw new Error('object JSON byte budget exceeded');return checked;
}

function buildAssetFamilyPrompt(corePrompt = '') {
  const family = currentAssetFamily();
  const subtype = currentAssetSubtype();
  const core = String(corePrompt || controlValue('assetCorePrompt', '')).trim();
  const styleProfile = resolveStyleProfileForFamily(styleProfileFromControls(), family);
  const {family_overrides: _resolvedOverrides, ...promptStyleProfile} = styleProfile;
  const output = { width: clampFamilyNumber(controlNumber('assetOutputWidth', 512), 1, 4096), height: clampFamilyNumber(controlNumber('assetOutputHeight', 512), 1, 4096), background: controlValue('assetBackground', 'transparent') };
  const shared = `STYLE_PROFILE_CANONICAL ${JSON.stringify(promptStyleProfile)}. Requested target/export size: ${output.width}x${output.height}. Background: ${output.background}. The provider raw size may differ; do not imply guaranteed native resolution.`;
  if (family === 'sprite' && ['character', 'monster', 'npc'].includes(subtype)) {
    return `${buildPixelAssetPrompt(core)}\n${shared}`;
  }
  if (family === 'sprite' && subtype === 'effect') {
    const effect = buildSpriteContract(subtype);
    const timing = `${effect.fps} FPS`;
    const effectSemantics = effect.sequence_mode === 'sequence'
      ? `Effect sequence: generate exactly ${effect.frame_count} frames in a ${effect.rows} row x ${effect.columns} column sprite-sheet grid, ${effect.gap}px gap, playback ${effect.loop} at ${timing}.`
      : `Static effect: generate exactly one isolated effect frame; playback metadata ${effect.loop} at ${timing}.`;
    return `${core}\n\nEffect-only ${effect.effect_category} pixel art. ${effectSemantics} Each logical frame envelope is ${effect.envelope_width}x${effect.envelope_height}px; size basis=${effect.size_basis}; pivot=${effect.pivot.preset} (${effect.pivot.x}, ${effect.pivot.y}); trim policy metadata=${effect.trim_policy}. Generate only the isolated effect with clean compositing margins; no actor, caster, target, equipment, direction pose, floor, UI, text, or watermark.\n${shared}`;
  }
  if (family === 'tile') {
    const tile = buildTileContract();
    return `${core}\n\nTile atlas specification: subtype=${subtype}; environment=${tile.environment}; material=${tile.material}; intended map use=${tile.use}; each ${tile.shape} cell is ${tile.tile_size.width}x${tile.tile_size.height}px; atlas margin=${tile.margin}px and cell spacing=${tile.spacing}px; mode=${tile.mode}; arrange ${tile.rows} rows by ${tile.columns} columns; seamless edges=${tile.seamless}. Connectivity topology=${tile.topology}; include inner corners=${tile.inner_corners} and outer corners=${tile.outer_corners}; transition rules=${JSON.stringify(tile.transitions)}; terrain types=${JSON.stringify(tile.terrain_types)}. Variation rules=${JSON.stringify(tile.variants)}. Per-cell metadata: collision=${JSON.stringify(tile.metadata.collision)}, occlusion=${JSON.stringify(tile.metadata.occlusion)}, navigation=${JSON.stringify(tile.metadata.navigation)}, custom=${JSON.stringify(tile.metadata.custom)}. Produce a coherent, grid-aligned map tile atlas with exact cell boundaries, no text or watermark.\n${shared}`;
  }
  if (family === 'ui') {
    const ui = buildUiContract();
    return `${core}\n\nReusable text-free UI component (${subtype}) for ${ui.purpose}. Source ${ui.source_size.width}x${ui.source_size.height}; semantic regions ${ui.information_structure.join(', ')}. Sizing ${ui.sizing_mode}; 9-slice margins ${JSON.stringify(ui.slice_margins)}; content safe area ${JSON.stringify(ui.content_safe_area)}; padding ${JSON.stringify(ui.padding)}. Border ${ui.border.style} ${ui.border.width}px; corners ${ui.corner.style} radius ${ui.corner.radius}px; decor ${ui.decor_density}; edge ${ui.edge_mode}; center ${ui.center_mode}; opacity ${ui.opacity}. States ${ui.states.join(', ')}; target ${ui.target_resolution.width}x${ui.target_resolution.height}; device safe area ${JSON.stringify(ui.device_safe_area)}. Keep every region empty for runtime content. Render no typography or numerals, no branding marks, no device-wide composition, and no depicted figures or scene.\n${shared}`;
  }
  if (family === 'object') {
    const object = buildObjectContract();
    return `${core}\n\nOBJECT_CONTRACT_CANONICAL ${JSON.stringify(object)}. Generate one isolated object image only. Requested states and variants are runtime metadata, not a claim that multiple state images are available. Preserve the declared source canvas, transparent alpha, placement pivot, ground/y-sort/snap points, and metadata. No actor action sheet, animation or direction sheet, UI card/icon mockup, tile atlas, effect sheet, text, scene, or baked VFX.\n${shared}`;
  }
  return core;
}

function assetFamilyPreset() {
  const family = currentAssetFamily();
  const subtype = currentAssetSubtype();
  if (family === 'sprite') return subtype === 'effect' ? 'effect' : 'pixel';
  if (family === 'ui') return 'ui';
  return family === 'tile' || family === 'object' ? 'game' : 'general';
}

function buildAssetGenerationPayload(base = {}) {
  const family = currentAssetFamily();
  const subtype = currentAssetSubtype();
  if (!family || !ASSET_FAMILY_SUBTYPES[family]?.includes(subtype)) throw new Error('Invalid asset family or subtype');
  const prompt = String(controlValue('assetCorePrompt', '')).trim();
  const style_profile = resolveStyleProfileForFamily(styleProfileFromControls(), family);
  const requestedBackground = controlValue('assetBackground', 'transparent');
  const output = {
    width: clampFamilyNumber(controlNumber('assetOutputWidth', 512), 1, 4096),
    height: clampFamilyNumber(controlNumber('assetOutputHeight', 512), 1, 4096),
    background: ['transparent', 'chroma_green', 'opaque'].includes(requestedBackground) ? requestedBackground : 'transparent',
  };
  const payload = {};
  for (const key of ['negative', 'preset', 'aspect_ratio', 'background_mode', 'reference_image', 'image', 'no_baked_vfx']) {
    if (Object.prototype.hasOwnProperty.call(base, key)) payload[key] = base[key];
  }
  Object.assign(payload, { prompt: base.prompt || prompt, asset_family: family, asset_type: subtype, style_profile, output });
  if (family === 'sprite') payload.sprite = buildSpriteContract(subtype);
  if (family === 'tile') payload.tile = buildTileContract();
  if (family === 'ui') payload.ui = buildUiContract();
  if (family === 'object') payload.object = buildObjectContract();
  return payload;
}

$('assetFamilyTabs')?.addEventListener('click', event => {
  const tab = event.target.closest('[data-asset-family]');
  if (tab) setAssetFamily(tab.dataset.assetFamily);
});
$('assetFamilyTabs')?.addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const tabs = [...document.querySelectorAll('#assetFamilyTabs [role="tab"]')];
  const current = Math.max(0, tabs.indexOf(document.activeElement));
  const next = event.key === 'Home' ? 0 : (event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length);
  event.preventDefault();
  setAssetFamily(tabs[next].dataset.assetFamily);
  tabs[next].focus();
});
$('assetSubtype')?.addEventListener('change', () => updateAssetFamilyUi());
$('effectSequenceMode')?.addEventListener('change', () => {
  const isStatic = $('effectSequenceMode')?.value === 'static';
  if ($('effectSequenceHint')) $('effectSequenceHint').textContent = isStatic
    ? '정적 모드는 payload와 그리드/미리보기/내보내기를 1프레임으로 사용하며 시퀀스 공통 설정은 유지합니다.'
    : '시퀀스 프레임 수가 프롬프트, 그리드, 미리보기와 내보내기에 공통 적용됩니다.';
  applyPixelWorkflowGridDefaults();
});
['effectFrameCount', 'effectRows', 'effectColumns', 'effectGap', 'effectEnvelopeWidth', 'effectEnvelopeHeight', 'effectFps', 'effectLoop', 'effectTrimPolicy', 'effectPivotX', 'effectPivotY'].forEach(id => {
  $(id)?.addEventListener('change', () => {
    applyPixelWorkflowGridDefaults();
    if ($('effectPreviewStage')?.querySelector('img')) buildEffectSequencePreview().catch(err => setStatus(`이펙트 미리보기 갱신 실패: ${err.message}`));
  });
});
$('familyGenerateAi')?.addEventListener('click', () => generateAiAsset().catch(err => {
  console.error(err);
  alert(`AI 에셋 생성 실패: ${err.message}`);
}));
window.__assetStudioDebug = { ...(window.__assetStudioDebug || {}), buildAssetGenerationPayload, buildAssetFamilyPrompt, setAssetFamily };
let lastActorAnimationPreset = 'idle';
const PIXEL_ANIMATION_PRESET_DEFAULT_FRAMES = {
  idle: 4,
  walk4: 4,
  walk6: 6,
  attack: 4,
  jump: 4,
  cast: 4,
  hurt: 4,
  death: 4,
  ui_static: 1,
};

function pixelAnimationDefaultFrames(anim = effectivePixelAnimationPreset()) {
  return PIXEL_ANIMATION_PRESET_DEFAULT_FRAMES[anim] || 4;
}

function canonicalActionForAnim(anim) {
  if (anim === 'walk4' || anim === 'walk6') return 'walk';
  return ({ idle:'idle', attack:'attack', jump:'jump', cast:'cast', hurt:'hurt', death:'death', ui_static:'ui_static' })[anim] || anim;
}

const SPRITE_ANIMATION_CORE_LOCKS = [
  ['Reference Identity Lock', 'one accepted reference identity is the global standard for the whole action set; preserve the actor silhouette language, key readable details, proportions, equipment/attachments, palette, outline thickness, pixel scale, and body volume across every frame'],
  ['Full-Frame Pose Lock', 'each frame must be a complete coherent pose of the same actor, not a crop, pasted body part, isolated limb edit, or numeric anchor hack'],
  ['Equipment Lock', 'same equipment/attachments/props remain logically attached and consistently designed; no invented, dropped, swapped, stretched, or redrawn equipment'],
  ['Direction Lock', 'same facing angle/view in every frame; no accidental side/front/back drift unless the requested action explicitly turns'],
  ['Root Lock', 'same root/pivot anchor, head/torso reference center, contact baseline, and scale; the whole actor must not slide inside the cell'],
  ['Motion Read', 'dominant readable motion must be the requested action beats, not a different action, vague fidget, or single-limb fake'],
  ['Loop Read', 'repeated playback must not pop, teleport, jitter, or require bbox-centering/crop tricks to look stable'],
  ['Production Clean', 'correct frame count, clean transparent/chroma cleanup, cell containment, no text/watermark/noise/residue, and no baked VFX in actor sheets'],
];

function spriteAnimationCoreLockContract() {
  const locks = SPRITE_ANIMATION_CORE_LOCKS.map(([name, rule]) => `${name}: ${rule}`).join('; ');
  return `Core animation locks, applied before action-specific PASS: every frame must preserve one accepted reference identity globally while forming real full-frame action poses from a stable root. ${locks}. If any lock fails, mark FAIL even if alpha, frame count, or motion partially pass.`;
}

function actionFrameBeats(anim, frames = pixelAnimationDefaultFrames(anim)) {
  const beats = {
    idle: ['neutral stance', 'subtle breath up', 'neutral stance', 'subtle breath down'],
    walk4: ['neutral crossover/passing stance', 'LEFT leg swing-cross; RIGHT leg planted support', 'neutral crossover/passing stance reused', 'RIGHT leg swing-cross; LEFT leg planted support'],
    walk6: ['contact A', 'down A', 'passing A', 'contact B', 'down B', 'passing B'],
    attack: ['ready pose', 'wind-up, weapon/arm pulled back', 'clean body/weapon strike pose', 'recovery, returns toward stance'],
    jump: ['crouch/anticipation', 'takeoff', 'airborne peak', 'landing/recovery'],
    cast: ['ready pose', 'hand/stance anticipation', 'clean casting/release body pose', 'recover'],
    hurt: ['normal pose', 'impact flinch', 'recoil', 'recovery'],
    death: ['alive/impact', 'collapse', 'down', 'dead/still'],
  }[anim] || Array.from({ length: frames }, (_, i) => `frame ${i + 1}`);
  return beats.slice(0, frames).map((beat, i) => `${i + 1}. ${beat}`).join('; ');
}

function actionVisualAcceptanceGate(anim) {
  const action = canonicalActionForAnim(anim);
  const gates = {
    idle: 'Whitelist visual acceptance gate for idle: PASS only if the sheet reads as an idle/breathing loop: standing in place, planted feet, same facing direction, same pivot/baseline, and only small torso/shoulder/head breathing motion across neutral, breath-up, neutral, breath-down beats. If the dominant readable action is not idle breathing, mark FAIL.',
    walk: 'Whitelist visual acceptance gate for walk: PASS only if the sheet reads as a simple RPG 4-frame crossover walk for the referenced actor: frames 1 and 3 are visually near-identical neutral transition poses with feet close beneath the pelvis. Frame 2: LEFT leg is the lifted swing leg crossing from behind to just ahead beside the RIGHT leg, while RIGHT leg is the planted stance/support leg. Frame 4: RIGHT leg is the lifted swing leg crossing from behind to just ahead beside the LEFT leg, while LEFT leg is the planted stance/support leg. In both crossing frames the swing foot passes beside and visibly overlaps/crosses the planted support leg beneath the pelvis; front/back depth ordering of the legs reverses between frames 2 and 4. Crossing is a natural depth pass, not swapped anatomical left/right identity or an X-locked pose. Root/pivot anchor, head/torso reference center, scale, and contact baseline stay locked; pelvis/root center remains at exactly 50% of each cell width and the same y-coordinate; counter-motion is secondary. Mark FAIL if frames 1 and 3 drift apart, if only one limb/contact point moves, if the same swing foot is repeated in both crossing frames, if the same side boot is enlarged/lifted in both crossing frames, if the legs never pass/cross through each other, if feet/contact points are hidden, if there is progressive left/right root drift, if bbox-centering would be needed to hide drift, or if motion reads as idle tapping, hopping, skating, dancing, a static split stance, or anything other than walking.',
    attack: 'Whitelist visual acceptance gate for attack: PASS only if the sheet reads as an attack: ready stance, readable wind-up, decisive strike pose, and recovery are all present in order, with the weapon/arm/body doing the action and returning toward stance. If the dominant readable action is not an attack, mark FAIL.',
    jump: 'Whitelist visual acceptance gate for jump: PASS only if the sheet reads as a jump: crouch anticipation, takeoff extension, airborne peak with clear vertical lift, and landing/recovery are present in order while the sprite remains contained in its cell. If the dominant readable action is not jumping, mark FAIL.',
    cast: 'Whitelist visual acceptance gate for cast: PASS only if the sheet reads as spell/skill casting body language: ready stance, hands/stance gather power, clear release gesture, and recovery are present in order, with the character pose—not external VFX—communicating the cast. If the dominant readable action is not casting, mark FAIL.',
    hurt: 'Whitelist visual acceptance gate for hurt: PASS only if the sheet reads as a hurt reaction: normal pose, impact flinch, recoil away from the hit, and recovery are present in order while facing direction, identity, palette, and equipment remain stable. If the dominant readable action is not a hurt reaction, mark FAIL.',
    death: 'Whitelist visual acceptance gate for death: PASS only if the sheet reads as death/collapse: alive/impact start, collapse in progress, downed body, and final dead/still pose are present in order; the final pose must be a stable downed/corpse silhouette using the same character identity and palette. If the dominant readable action is not death/collapse, mark FAIL.',
  };
  return gates[action] ? `${spriteAnimationCoreLockContract()} ${gates[action]}` : '';
}

function isPixelActorAssetType(type = $('pixelAssetType')?.value || 'character') {
  return PIXEL_ACTOR_ASSET_TYPES.has(type);
}

function isPixelEffectAssetType(type = $('pixelAssetType')?.value || 'character') {
  return PIXEL_EFFECT_ASSET_TYPES.has(type);
}

function effectivePixelAnimationPreset() {
  if (isPixelActorAssetType()) return $('pixelAnimationPreset')?.value || 'idle';
  if (isPixelEffectAssetType()) {
    return ($('effectSequenceMode')?.value || 'sequence') === 'static' ? 'static' : 'effect_sequence';
  }
  return 'ui_static';
}

function requestedPixelFrameCount() {
  if (isPixelEffectAssetType()) {
    if (($('effectSequenceMode')?.value || 'sequence') === 'static') return 1;
    return Math.max(1, Math.min(64, +($('effectFrameCount')?.value || 6)));
  }
  if (!isPixelActorAssetType() || effectivePixelAnimationPreset() === 'ui_static') return 1;
  const anim = effectivePixelAnimationPreset();
  return pixelAnimationDefaultFrames(anim);
}

function syncPixelAssetWorkflowUi({ silent = false } = {}) {
  const type = $('pixelAssetType')?.value || 'character';
  const actor = isPixelActorAssetType(type);
  const effect = isPixelEffectAssetType(type);
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
    if ($('pixelWalkFrames')) $('pixelWalkFrames').value = String(pixelAnimationDefaultFrames($('pixelAnimationPreset')?.value || 'idle'));
  }

  const typeLabel = ({ character:'캐릭터', monster:'몬스터', item:'아이템', ui_panel:'UI 패널', button:'버튼', icon:'아이콘', tile:'타일', effect:'이펙트' })[type] || type;
  const staticModeNotice = effect
    ? '이펙트 시퀀스 · 1회/반복, 프레임 수와 피벗을 설정합니다. 캐릭터 방향/장비 설정 없음.'
    : '정적 에셋 모드 · 아이템/UI/버튼/아이콘/타일은 동작·방향 선택을 숨기고 1프레임으로 생성합니다.';
  const referenceGenerationHint = effect
    ? '선택한 이미지 레이어의 스타일과 맥락에 맞는 별도 이펙트 시퀀스를 생성합니다. 캐릭터 방향/장비 설정 없음.'
    : (actor
      ? '선택한 이미지 레이어를 기준으로 현재 동작/방향/프레임 수를 생성합니다. 선택 이미지가 없으면 위의 “새 도트 에셋 생성”을 쓰세요.'
      : '선택한 이미지 레이어의 스타일로 정적 에셋을 생성합니다. 선택 이미지가 없으면 위의 “새 도트 에셋 생성”을 쓰세요.');
  const workflowHint = effect
    ? '설정한 1회/반복, 프레임 수와 피벗을 적용하고 배경 제거 후 프레임 시퀀스 유지 상태로 정리합니다.'
    : (actor
      ? '생성 후 배경 제거와 그리드 값을 자동으로 맞춥니다. 애니메이션 확인은 오른쪽 스프라이트 도구에서 실행합니다.'
      : '생성 후 정적 에셋의 배경을 제거합니다.');
  if ($('pixelStaticModeNotice')) $('pixelStaticModeNotice').textContent = staticModeNotice;
  if ($('pixelReferenceGenerationHint')) $('pixelReferenceGenerationHint').textContent = referenceGenerationHint;
  if ($('pixelWorkflowHint')) $('pixelWorkflowHint').textContent = workflowHint;
  if ($('generatePixelAsset')) $('generatePixelAsset').textContent = effect ? `새 ${typeLabel} 생성` : (actor ? `새 ${typeLabel} 스프라이트 생성` : `${typeLabel} 정적 에셋 생성`);
  if ($('generateFrontIdleFromSelected')) $('generateFrontIdleFromSelected').textContent = effect ? '선택 이미지에 맞는 이펙트 생성' : (actor ? '선택 이미지 기준 방향/동작 생성' : '선택 이미지 스타일로 정적 에셋 생성');
  if ($('runPixelWorkflow')) $('runPixelWorkflow').textContent = effect ? '이펙트 생성 → 배경 제거' : (actor ? '생성 → 배경 제거 → 그리드 값 맞춤' : '정적 에셋 생성 → 배경 제거');
  if (!silent) setStatus(effect ? `${typeLabel} 모드 · 선택 레이어 맥락 또는 단독 이펙트 생성` : (actor ? `${typeLabel} 모드 · 동작/방향 선택 사용` : `${typeLabel} 모드 · 동작/방향 숨김 · 1프레임 생성`));
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
    : `${actionLabel} columns: exactly ${frameCount} frames per requested direction, evenly spaced in one horizontal row; frame beats: ${actionFrameBeats(anim, frameCount)}; Walk contract: neutral contact, left-foot stride, neutral contact, right-foot stride; fixed identity and equipment, fixed root baseline, no fake camera motion or whole-body translation. Global reference identity rule: one accepted reference identity is the standard for the whole action set; every frame must be a complete coherent full-frame pose, not a cut/paste/part-slide edit; ${spriteAnimationCoreLockContract()}`;
  const gridLine = mode === 'single'
    ? `Sheet grid: 1 row x ${columns} columns. The visible character must face ${directionLabel(targetDir)} in every cell.`
    : `Sheet grid: ${dirs.length} rows x ${columns} columns, evenly spaced cells, same scale and pivot in every cell.`;
  const cellSafetyLine = anim === 'ui_static'
    ? 'Cell safety: keep the single asset fully inside the canvas with clear empty margin on all sides.'
    : `Cell safety: treat each animation frame as a separate boxed cell. Put a wide empty transparent/chroma gutter between cells. Every body part, weapon, held object, shadow, and silhouette must stay fully inside its own cell with at least 15% empty side margin. Nothing may touch or cross a cell boundary; if the motion would cross, shrink the body/weapon pose rather than spilling into the next frame. No VFX: do not draw slash arcs, hit sparks, magic glows, particles, smoke, shockwaves, detached debris, motion trails, or background effects; those are separate effect-only assets composited in-game.`;
  const visualGateLine = anim === 'ui_static'
    ? ''
    : actionVisualAcceptanceGate(anim);
  return `${directionLine}\nReference image direction: ${directionLabel(refDir)}. Use it only as the source view/style identity. Target direction is ${directionLabel(targetDir)}.\n${frameLine}\n${gridLine}\n${cellSafetyLine}${visualGateLine ? `\n${visualGateLine}` : ''}`;
}

function buildPixelAssetPrompt(corePrompt = '') {
  const type = $('pixelAssetType')?.value || 'character';
  const actor = isPixelActorAssetType(type);
  const anim = effectivePixelAnimationPreset();
  const style = $('assetStylePreset')?.value || '32bit_refined';
  const singleMode = ($('pixelDirectionMode')?.value || 'single') === 'single';
  const direction = singleMode ? directionLabel($('pixelTargetDirection')?.value || 'S') : ($('pixelDirection')?.value || 'front');
  const palette = ($('assetStyleNotes')?.value || 'limited dark game palette').trim();
  const subject = String(corePrompt || $('assetCorePrompt')?.value || '').trim();
  const effect = isPixelEffectAssetType(type);
  const typeLine = type === 'ui_panel'
    ? 'UI game asset, clean panel parts, reusable game UI component'
    : (effect ? 'effect-only game VFX asset for compositing, no caster/target/body/prop included' : `${type} game asset`);
  const frameCount = anim === 'ui_static' ? 1 : requestedPixelFrameCount();
  const animLine = {
    idle: `idle animation, ${frameCount}-frame subtle breathing loop (${actionFrameBeats(anim, frameCount)}), evenly spaced sprite sheet cells`,
    walk4: `simple RPG crossover walk cycle, ${frameCount}-frame neutral-left-cross-neutral-right-cross animation (${actionFrameBeats(anim, frameCount)}). Frames 1 and 3 use the same neutral transition pose with feet close beneath the pelvis. Frame 2: LEFT leg is the lifted swing leg crossing from behind to just ahead beside the planted RIGHT stance/support leg. Frame 4 is the exact inverse: RIGHT leg is the lifted swing leg crossing beside the planted LEFT stance/support leg. The swing foot passes beside and visibly overlaps/crosses the planted support leg beneath the pelvis; leg front/back depth ordering reverses between frames 2 and 4. For S/front-facing, character LEFT = screen-right and character RIGHT = screen-left: frame 2 swing boot on screen-right, frame 4 swing boot on screen-left. Screen coordinates are final: column 2 only screen-right boot advances with knee crossing inward; column 4 only screen-left boot advances with knee crossing inward. Below-belt phases must be opposite/mirrored; reject the same-side front boot in both. Keep pelvis/root center at exactly 50% of each cell width and the same y-coordinate. Natural depth pass only, no X-locked legs or anatomical side swap. Fixed root/pivot anchor, stable head/torso center and contact baseline, coherent counter-motion, no one-limb fake, evenly spaced sprite sheet cells`,
    walk6: `smooth walk cycle, ${frameCount}-frame walking animation (${actionFrameBeats(anim, frameCount)}), fixed root/pivot anchor, stable head/torso reference center and contact baseline, actor-appropriate alternating support/contact phases, connected passing beats, coherent counter-motion, no one-limb fake across all 6 frames, evenly spaced sprite sheet cells`,
    attack: `attack animation, ${frameCount} frames (${actionFrameBeats(anim, frameCount)}), readable ready/wind-up/strike/recovery body and weapon poses, evenly spaced sprite sheet cells`,
    jump: `jump animation, ${frameCount} frames (${actionFrameBeats(anim, frameCount)}), readable crouch/takeoff/airborne/landing beats, evenly spaced sprite sheet cells`,
    cast: `cast animation, ${frameCount} frames (${actionFrameBeats(anim, frameCount)}), readable ready/gather/release/recover casting body-language beats, evenly spaced sprite sheet cells`,
    hurt: `hurt animation, ${frameCount} frames (${actionFrameBeats(anim, frameCount)}), readable normal/impact/recoil/recovery hit-reaction beats, evenly spaced sprite sheet cells`,
    death: `death animation, ${frameCount} frames (${actionFrameBeats(anim, frameCount)}), readable alive/collapse/down/dead-still collapse beats, evenly spaced sprite sheet cells`,
    ui_static: `${type} static single asset, no animation frames, crisp reusable game component`,
  }[anim] || `${frameCount}-frame animation frames`;
  const styleLine = `${style.replaceAll('_', ' ')}, refined pixel art, not chunky NES, clean silhouette, game-ready production quality`;
  const directionalContract = actor ? buildDirectionalSpriteSheetContract(anim) : (effect ? 'Effect asset contract: exactly one isolated reusable game VFX asset, no character/monster/object body, no caster, no target, no floor/environment, no UI frame. The effect must be centered with transparent/chroma margin and be ready to composite over selected or standalone assets.' : 'Static asset contract: exactly one isolated reusable game asset, no animation, no direction sheet, no alternate poses.');
  const outputLine = actor
    ? 'Output: pixel-art sprite sheet, transparent background, isolated asset, centered, consistent scale, clean alpha edges, no text, no watermark, no logo, no mockup frame. Background cleanup contract: true transparent background after postprocess; no visible rectangular cell boxes, dark/green residue, chroma spill, halo, or fringe around sprites.'
    : (effect ? 'Output: single transparent PNG-style effect-only asset, centered, clean alpha edges, no character/monster/object/prop/body, no sprite sheet, no text, no watermark, no logo, no mockup frame.' : 'Output: single transparent PNG-style pixel asset, centered, clean alpha edges, no sprite sheet, no text, no watermark, no logo, no mockup frame. No baked VFX: no slash arcs, hit sparks, magic glows, particles, smoke, shockwaves, detached debris, motion trails, aura, or background effects.');
  return `${subject}\n${typeLine}\n${animLine}\n${directionalContract}\n${actor ? `Direction hint: ${direction}` : 'Direction hint: not applicable for this asset type.'}\nPalette: ${palette}\nStyle: ${styleLine}\n${outputLine}`;
}

function syncPixelAssetPrompt() {
  // Pixel generator relies on background_mode: 'chroma_green' via generateBtn for transparent-friendly extraction.
  const prompt = buildPixelAssetPrompt();
  if ($('aiPrompt')) $('aiPrompt').value = prompt;
  if ($('aiPreset')) $('aiPreset').value = $('pixelAssetType')?.value === 'effect' ? 'effect' : ($('pixelAssetType')?.value === 'ui_panel' ? 'ui' : 'pixel');
  if ($('aiAspect')) $('aiAspect').value = 'square';
  setStatus('도트 에셋 프롬프트 조립 완료.');
  return prompt;
}

function pixelPresetFrameCount(anim = effectivePixelAnimationPreset()) {
  if (isPixelEffectAssetType()) return requestedPixelFrameCount();
  if (anim === 'ui_static') return 1;
  return pixelAnimationDefaultFrames(anim);
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
  const effect = isPixelEffectAssetType();
  const frames = requestedPixelFrameCount();
  const dirs = directionLabelsForMode();
  const rows = effect ? Math.max(1, +($('effectRows')?.value || 1)) : Math.max(1, dirs.length);
  const requestedColumns = effect ? Math.max(1, +($('effectColumns')?.value || frames)) : frames;
  const columns = effect ? Math.max(requestedColumns, Math.ceil(frames / rows)) : frames;
  const img = targetImg || activeSpriteTarget() || selectedLayerObject();
  const size = img?.type === 'image' ? imageDisplayedSize(img) : null;
  const frameW = effect ? Math.max(1, +($('effectEnvelopeWidth')?.value || 64)) : (size ? Math.max(1, Math.round(size.w / frames)) : Math.max(1, +($('pixelFrameW')?.value || 32)));
  const frameH = effect ? Math.max(1, +($('effectEnvelopeHeight')?.value || 64)) : (size ? Math.max(1, Math.round(size.h / rows)) : Math.max(1, +($('pixelFrameH')?.value || 32)));
  const gap = effect ? Math.max(0, +($('effectGap')?.value || 0)) : 0;
  if ($('gridCols')) $('gridCols').value = String(columns);
  if ($('gridRows')) $('gridRows').value = String(rows);
  if ($('gridCellW')) $('gridCellW').value = String(frameW);
  if ($('gridCellH')) $('gridCellH').value = String(frameH);
  if ($('pixelFrameW')) $('pixelFrameW').value = String(frameW);
  if ($('pixelFrameH')) $('pixelFrameH').value = String(frameH);
  if ($('gridGapX')) $('gridGapX').value = String(gap);
  if ($('gridGapY')) $('gridGapY').value = String(gap);
  if ($('animFrameCount')) $('animFrameCount').value = String(frames);
  if ($('animFps')) $('animFps').value = effect ? String(Math.max(1, +($('effectFps')?.value || 12))) : ($('pixelAnimationPreset')?.value?.startsWith('walk') ? '10' : '8');
  if (effect && $('animMode')) {
    const effectLoop = $('effectLoop')?.value || 'one-shot';
    $('animMode').value = effectLoop === 'ping-pong' ? 'pingpong' : (effectLoop === 'loop' ? 'loop' : 'once');
  }
  return { frames, rows, columns, frameW, frameH, autoSized: !!size };
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

function captureHistoryState() {
  return {assetResultSnapshot:assetResultStore.snapshot(),assetLibrary:JSON.parse(JSON.stringify(assetLibrary)),adoptionRecords:JSON.parse(JSON.stringify(adoptionRecords))};
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
    item.onclick = () => jumpToHistory(idx).catch(reportHistoryError);
    list.appendChild(item);
  });
}

function saveHistory(label = '') {
  if (suppressHistory) return;
  const json = historyJson();
  const additive=captureHistoryState();
  if (history[historyIndex]?.json === json && JSON.stringify(history[historyIndex]?.assetResultSnapshot||null)===JSON.stringify(additive.assetResultSnapshot) && JSON.stringify(history[historyIndex]?.assetLibrary||[])===JSON.stringify(additive.assetLibrary) && JSON.stringify(history[historyIndex]?.adoptionRecords||[])===JSON.stringify(additive.adoptionRecords)) { renderHistory(); return; }
  history = history.slice(0, historyIndex + 1);
  history.push({ json, ...additive, label: labelHistoryEntry(label), at: new Date().toISOString() });
  historyIndex = history.length - 1;
  if (history.length > 80) { history.shift(); historyIndex--; }
  renderLayers();
  renderHistory();
}

async function loadHistory(idx) {
  if (idx < 0 || idx >= history.length) return false;
  if (historyLoadInFlight) return false;
  const operation = (async () => {
    const entry=history[idx];
    const canvasBefore=canvas.toJSON(SERIALIZED_PROPS), storeBefore=assetResultStore.snapshot();
    const libraryBefore=JSON.parse(JSON.stringify(assetLibrary)), recordsBefore=JSON.parse(JSON.stringify(adoptionRecords));
    const historyIndexBefore=historyIndex, editorStateBefore=currentEditorState();
    const targetJson=parseCanvasJson(entry.json);
    const targetSnapshot=entry.assetResultSnapshot || storeBefore;
    const targetLibrary=JSON.parse(JSON.stringify(entry.assetLibrary || libraryBefore));
    const targetRecords=JSON.parse(JSON.stringify(entry.adoptionRecords || recordsBefore));
    // Validate the complete destination before the first mutation.
    const targetState=validateProjectResultState({
      results:targetSnapshot.values.map(pair=>pair?.[1]), selectedId:targetSnapshot.selectedId,
      compareIds:targetSnapshot.compareIds, library:targetLibrary,
    });
    validateCanvasResultReferences(targetJson,targetState);
    if(!Array.isArray(targetRecords)) throw new Error('유효하지 않은 채택 기록입니다.');
    suppressHistory=true;
    try {
      assetResultStore.restore(targetSnapshot);
      assetLibrary.splice(0,assetLibrary.length,...targetLibrary);
      adoptionRecords.splice(0,adoptionRecords.length,...targetRecords);
      await loadCanvasJson(targetJson);
      canvas.renderAll();
      historyIndex=idx;
      refreshMaskStateFromCanvas();syncProps();renderLayers();renderHistory();renderAssetResultTray();refreshAiChatState();
      setStatus(`History: ${entry.label || idx + 1}`);
      return true;
    } catch(error) {
      let rollbackError=null;
      try { await loadCanvasJson(canvasBefore); }
      catch(cause) { rollbackError=cause; console.error('History canvas rollback failed',cause); }
      try {
        assetResultStore.restore(storeBefore);
        assetLibrary.splice(0,assetLibrary.length,...libraryBefore);
        adoptionRecords.splice(0,adoptionRecords.length,...recordsBefore);
        historyIndex=historyIndexBefore;
        applyEditorState(editorStateBefore);
        canvas.renderAll();refreshMaskStateFromCanvas();syncProps();renderLayers();renderHistory();renderAssetResultTray();refreshAiChatState();
      } catch(cause) { rollbackError ||= cause; console.error('History state rollback failed',cause); }
      if(rollbackError) error.rollbackError=rollbackError;
      throw error;
    } finally { suppressHistory=false; }
  })();
  historyLoadInFlight=operation;
  try { return await operation; }
  finally { if(historyLoadInFlight===operation) historyLoadInFlight=null; }
}

function jumpToHistory(idx) {
  return loadHistory(idx);
}

function undoHistory() {
  return loadHistory(historyIndex - 1);
}

function redoHistory() {
  return loadHistory(historyIndex + 1);
}

function parseCanvasJson(jsonOrString) {
  if (!jsonOrString) return null;
  return typeof jsonOrString === 'string' ? JSON.parse(jsonOrString) : jsonOrString;
}

function validateCanvasResultReferences(canvasJson, resultState) {
  if(!canvasJson || !Array.isArray(canvasJson.objects)) throw new Error('유효하지 않은 히스토리 canvasJson입니다.');
  const resultById=new Map(resultState.results.map(item=>[item.id,item]));
  const layerIds=new Set(canvasJson.objects.flatMap(o=>[o.id,o.layerId]).filter(id=>typeof id==='string'&&id));
  for(const object of canvasJson.objects){
    const hasProvenance=['resultId','resultFamily','resultType'].some(key=>object[key]!==undefined&&object[key]!==null);
    if(hasProvenance){
      if(typeof object.resultId!=='string'||typeof object.resultFamily!=='string'||typeof object.resultType!=='string') throw new Error('불완전한 Result 레이어 참조입니다.');
      const result=resultById.get(object.resultId);
      if(!result) throw new Error('Result를 참조하는 레이어가 유실되었습니다.');
      if(object.resultFamily!==result.family||object.resultType!==result.type) throw new Error('Result 레이어 family/type이 일치하지 않습니다.');
    }
    if(object.replacesLayerId!==undefined&&object.replacesLayerId!==null&&(typeof object.replacesLayerId!=='string'||!layerIds.has(object.replacesLayerId)||object.replacesLayerId===object.id)) throw new Error('교체 원본 레이어 참조가 유실되었습니다.');
  }
  return true;
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

function updateCanvasTransform() {
  const shell = $('canvasShell');
  if (!shell) return;
  shell.style.transform = `scale(${viewScale})`;
  shell.style.transformOrigin = 'top left';
  updateCanvasStageSize();
  if ($('zoomLabel')) $('zoomLabel').textContent = `${Math.round(viewScale * 100)}%`;
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

async function serializeAssetResultProjectState() {
  const state=assetResultStore.state();
  const results=assetResultStore.list();
  const durable=async url=>{
    if(typeof url!=='string' || url.startsWith('blob:')) throw new Error('프로젝트 Result에 비내구성 URL이 있습니다.');
    return url.startsWith('data:image/') ? url : srcToDataUrl(url);
  };
  for(const result of results){
    if(result.preview?.url) result.preview.url=await durable(result.preview.url);
    for(const artifact of result.artifacts){if(artifact?.url)artifact.url=await durable(artifact.url);}
  }
  const library=JSON.parse(JSON.stringify(assetLibrary));
  for(const item of library)item.url=await durable(item.url);
  return validateProjectResultState({results,selectedId:state.selectedId,compareIds:state.compareIds,library});
}

async function buildProjectV2() {
  const styleProfile = normalizeStyleProfile(styleProfileFromControls());
  const familyDrafts = serializeProjectFamilyDrafts();
  const selectedFamily = currentAssetFamily() || 'sprite';
  const canvasJson = canvasJsonSnapshot();
  const historyEntries = history.map((entry, idx) => ({
    label: entry.label || `History ${idx + 1}`,
    at: entry.at || null,
    canvasJson: parseCanvasJson(entry.json),
    assetResultSnapshot: entry.assetResultSnapshot ? JSON.parse(JSON.stringify(entry.assetResultSnapshot)) : undefined,
    assetLibrary: entry.assetLibrary ? JSON.parse(JSON.stringify(entry.assetLibrary)) : undefined,
    adoptionRecords: entry.adoptionRecords ? JSON.parse(JSON.stringify(entry.adoptionRecords)) : undefined,
  }));
  const jsons = [canvasJson, ...historyEntries.map(e => e.canvasJson).filter(Boolean)];
  const assets = await collectEmbeddedImageAssets(jsons);
  const assetResults = await serializeAssetResultProjectState();
  const now = new Date().toISOString();
  const identity=projectV2Identity||{createdAt:now,updatedAt:now};
  return {
    app: 'asset-studio-local',
    version: 2,
    kind: 'project',
    createdAt: identity.createdAt,
    updatedAt: identity.updatedAt,
    styleProfile,
    familyDrafts,
    selectedFamily,
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
    assetResults,
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

// Fabric 6+ returns a Promise and treats the second argument as an object
// reviver. Fabric 5 and older signal completion through that argument.
async function loadCanvasJson(json) {
  const major = Number.parseInt(String(globalThis.fabric?.version || '0').split('.')[0], 10);
  if (major >= 6) {
    await canvas.loadFromJSON(json);
    return;
  }
  await new Promise((resolve, reject) => {
    try { canvas.loadFromJSON(json, resolve); }
    catch (error) { reject(error); }
  });
}

async function loadLegacyProjectV1(project) {
  const storeBefore=assetResultStore.snapshot(), libraryBefore=JSON.parse(JSON.stringify(assetLibrary)), recordsBefore=JSON.parse(JSON.stringify(adoptionRecords));
  const styleBefore=normalizeStyleProfile(styleProfileFromControls()), draftsBefore=serializeProjectFamilyDrafts(), selectedFamilyBefore=currentAssetFamily(), identityBefore=projectV2Identity?{...projectV2Identity}:null;
  const canvasBefore=canvas.toJSON(SERIALIZED_PROPS), historyBefore=history.slice(), historyIndexBefore=historyIndex, editorStateBefore=currentEditorState();
  suppressHistory = true;
  try {
    await loadCanvasJson(project);
    suppressHistory = false;
    assetLibrary.splice(0,assetLibrary.length);
    adoptionRecords.splice(0,adoptionRecords.length);
    assetResultStore.restore({values:[],selectedId:null,compareIds:[]});
    projectV2Identity=null;
    hydrateStyleProfileControls(DEFAULT_STYLE_PROFILE);
    hydrateProjectFamilyDrafts(undefined,'sprite');
    history = [];
    historyIndex = -1;
    saveHistory('불러온 v1 프로젝트');
    renderAssetResultTray();
    finishProjectLoad('Legacy v1 프로젝트를 불러왔습니다.');
    return project;
  } catch (error) {
    history=historyBefore; historyIndex=historyIndexBefore;
    assetLibrary.splice(0,assetLibrary.length,...libraryBefore); adoptionRecords.splice(0,adoptionRecords.length,...recordsBefore); assetResultStore.restore(storeBefore);
    try {
      await loadCanvasJson(canvasBefore); applyEditorState(editorStateBefore);
      hydrateStyleProfileControls(styleBefore); hydrateProjectFamilyDrafts(draftsBefore,selectedFamilyBefore); projectV2Identity=identityBefore;
      canvas.renderAll(); renderLayers(); renderHistory(); renderAssetResultTray();
    } catch (rollbackError) { console.error('Legacy project rollback failed',rollbackError); }
    finally { suppressHistory = false; }
    throw error;
  }
}

async function loadProjectV2(project) {
  const canonicalTimestamp=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value)&&new Date(value).toISOString()===value;
  let projectCreatedAt=project.createdAt, projectUpdatedAt=project.updatedAt;
  if(projectCreatedAt===undefined&&projectUpdatedAt===undefined){projectCreatedAt=new Date().toISOString();projectUpdatedAt=projectCreatedAt;}
  else if(!canonicalTimestamp(projectCreatedAt)||!canonicalTimestamp(projectUpdatedAt)||Date.parse(projectUpdatedAt)<Date.parse(projectCreatedAt))throw new Error('Invalid project timestamps');
  const editor = project.editor || {};
  const entries = Array.isArray(editor.history) ? editor.history : [];
  const idx = clamp(Number.isInteger(editor.historyIndex) ? editor.historyIndex : entries.length - 1, 0, Math.max(0, entries.length - 1));
  const targetJson = entries[idx]?.canvasJson || editor.canvasJson;
  if (!targetJson) throw new Error('프로젝트에 canvasJson이 없습니다.');
  const resultState=validateProjectResultState(project.assetResults);
  const projectStyleProfile=normalizeStyleProfile(project.styleProfile===undefined?DEFAULT_STYLE_PROFILE:project.styleProfile);
  const projectFamilyDrafts=validateProjectFamilyDrafts(project.familyDrafts);
  const projectSelectedFamily=project.selectedFamily===undefined?'sprite':project.selectedFamily;
  if(!PROJECT_FAMILIES.includes(projectSelectedFamily))throw new Error('Invalid selectedFamily');
  validateCanvasResultReferences(editor.canvasJson||targetJson,resultState);
  const validatedEntries=entries.map(entry=>{
    let state=resultState;
    if(entry.assetResultSnapshot){
      const values=entry.assetResultSnapshot.values;
      state=validateProjectResultState({results:Array.isArray(values)?values.map(pair=>pair?.[1]):null,selectedId:entry.assetResultSnapshot.selectedId,compareIds:entry.assetResultSnapshot.compareIds,library:entry.assetLibrary||[]});
    }
    validateCanvasResultReferences(entry.canvasJson||editor.canvasJson||targetJson,state);
    if(entry.adoptionRecords!==undefined&&!Array.isArray(entry.adoptionRecords)) throw new Error('유효하지 않은 채택 기록입니다.');
    return {entry,state};
  });
  const storeBefore=assetResultStore.snapshot(), libraryBefore=JSON.parse(JSON.stringify(assetLibrary)), recordsBefore=JSON.parse(JSON.stringify(adoptionRecords));
  const styleBefore=normalizeStyleProfile(styleProfileFromControls()), draftsBefore=serializeProjectFamilyDrafts(), selectedFamilyBefore=currentAssetFamily(), identityBefore=projectV2Identity?{...projectV2Identity}:null;
  const canvasBefore=canvas.toJSON(SERIALIZED_PROPS), historyBefore=history.slice(), historyIndexBefore=historyIndex, editorStateBefore=currentEditorState();
  const rollback=async()=>{
    history=historyBefore; historyIndex=historyIndexBefore;
    assetLibrary.splice(0,assetLibrary.length,...libraryBefore); adoptionRecords.splice(0,adoptionRecords.length,...recordsBefore); assetResultStore.restore(storeBefore);
    suppressHistory=true;
    try {
      await loadCanvasJson(canvasBefore);
      applyEditorState(editorStateBefore);
      hydrateStyleProfileControls(styleBefore);hydrateProjectFamilyDrafts(draftsBefore,selectedFamilyBefore);projectV2Identity=identityBefore;
      canvas.renderAll();renderLayers();renderHistory();renderAssetResultTray();
    } finally { suppressHistory=false; }
  };
  suppressHistory = true;
  try {
        await loadCanvasJson(targetJson);
        history = validatedEntries.map(({entry,state}, i) => ({
          json: JSON.stringify(entry.canvasJson || editor.canvasJson || targetJson),
          label: entry.label || `History ${i + 1}`,
          at: entry.at || new Date().toISOString(),
          assetResultSnapshot:entry.assetResultSnapshot||{values:state.results.map(item=>[item.id,item]),selectedId:state.selectedId,compareIds:state.compareIds},
          assetLibrary:entry.assetLibrary||state.library,
          adoptionRecords:entry.adoptionRecords||[],
        }));
        if (!history.length) history = [{ json: JSON.stringify(targetJson), label: '불러온 프로젝트', at: new Date().toISOString() }];
        historyIndex = clamp(idx, 0, history.length - 1);
        applyEditorState(editor.state || {});
        hydrateStyleProfileControls(projectStyleProfile);
        hydrateProjectFamilyDrafts(projectFamilyDrafts,projectSelectedFamily);
        projectV2Identity={createdAt:projectCreatedAt,updatedAt:projectUpdatedAt};
        assetLibrary.splice(0,assetLibrary.length,...resultState.library);
        adoptionRecords.splice(0,adoptionRecords.length,...(history[historyIndex]?.adoptionRecords||[]));
        assetResultStore.restore({values:resultState.results.map(item=>[item.id,item]),selectedId:resultState.selectedId,compareIds:resultState.compareIds});
        suppressHistory = false;
        renderAssetResultTray();
        finishProjectLoad(`Project v2 불러오기 완료 · 히스토리 ${historyIndex + 1}/${history.length}`);
        return project;
  } catch(error) {
    try { await rollback(); }
    catch (rollbackError) { console.error('Project rollback failed', rollbackError); }
    throw error;
  }
}

function validateProjectEnvelope(project) {
  const fail=message=>{throw new Error(`Invalid project: ${message}`);};
  let nodes=0; const seen=new Set();
  const walk=(value,depth=0)=>{
    if(depth>64 || ++nodes>100000)fail('depth/node budget exceeded');
    if(value===null || ['string','boolean'].includes(typeof value))return;
    if(typeof value==='number'){if(!Number.isFinite(value))fail('non-finite number');return;}
    if(typeof value!=='object' || seen.has(value))fail('not JSON-safe');
    if(!Array.isArray(value) && Object.getPrototypeOf(value)!==Object.prototype && Object.getPrototypeOf(value)!==null)fail('prototype');
    seen.add(value);
    for(const key of Object.keys(value)){if(['__proto__','prototype','constructor'].includes(key))fail('unsafe key');walk(value[key],depth+1);}
    seen.delete(value);
  };
  walk(project); const text=JSON.stringify(project);
  if(new TextEncoder().encode(text).byteLength>PROJECT_MAX_BYTES)fail('byte budget exceeded');
  return project;
}

function loadProjectFileObject(project) {
  validateProjectEnvelope(project);
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

// Effect frames use a declared row-major grid, never connected components.
// Kept DOM-free so acceptance tests and the preview execute identical logic.
function sliceEffectImageData(imageData, gridContract, mode = 'full-cell') {
  if (!imageData || !Number.isInteger(imageData.width) || !Number.isInteger(imageData.height) || !imageData.data) throw new Error('RGBA imageData required');
  if (!['full-cell', 'trim'].includes(mode)) throw new Error('effect slice mode must be full-cell or trim');
  const int = (value, name, min = 1) => {
    const number = Number(value);
    if (!Number.isInteger(number) || number < min) throw new Error(`invalid effect grid ${name}`);
    return number;
  };
  const rows = int(gridContract.rows, 'rows'), columns = int(gridContract.columns, 'columns');
  const width = int(gridContract.cell?.width, 'cell.width'), height = int(gridContract.cell?.height, 'cell.height');
  const gap = int(gridContract.gap ?? 0, 'gap', 0);
  const frameCount = int(gridContract.frameCount ?? gridContract.frame_count, 'frameCount');
  if (frameCount > rows * columns || rows * columns > 4096) throw new Error('effect frame count exceeds declared grid');
  const expectedWidth = columns * width + (columns - 1) * gap;
  const expectedHeight = rows * height + (rows - 1) * gap;
  if (imageData.width !== expectedWidth || imageData.height !== expectedHeight) throw new Error(`effect sheet ${imageData.width}x${imageData.height} does not match declared grid ${expectedWidth}x${expectedHeight}`);
  const padding = int(gridContract.trimPadding ?? gridContract.trim_padding ?? 1, 'trimPadding', 0);
  const pivot = gridContract.pivot || { x: .5, y: .5 };
  const pivotX = Number(pivot.x), pivotY = Number(pivot.y);
  if (!Number.isFinite(pivotX) || !Number.isFinite(pivotY) || pivotX < 0 || pivotX > 1 || pivotY < 0 || pivotY > 1) throw new Error('effect pivot must be normalized');
  const source = imageData.data;
  const alphaAt = (x, y) => source[(y * imageData.width + x) * 4 + 3];
  let gutterAlphaPixels = 0;
  for (let y = 0; y < imageData.height; y++) for (let x = 0; x < imageData.width; x++) {
    if ((x % (width + gap) >= width || y % (height + gap) >= height) && alphaAt(x, y) > 0) gutterAlphaPixels++;
  }
  let frameEdgeAlphaPixels = 0, lowAlphaPixels = 0, alphaPixels = 0;
  const nonEmptyFrameIndices = [], frames = [];
  for (let order = 0; order < frameCount; order++) {
    const row = Math.floor(order / columns), column = order % columns;
    const originX = column * (width + gap), originY = row * (height + gap);
    let minX = width, minY = height, maxX = -1, maxY = -1;
    const fullPixels = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      const sourceOffset = ((originY + y) * imageData.width + originX + x) * 4;
      const targetOffset = (y * width + x) * 4;
      fullPixels.set(source.subarray(sourceOffset, sourceOffset + 4), targetOffset);
      const alpha = source[sourceOffset + 3];
      if (alpha > 0) {
        alphaPixels++;
        if (alpha <= 20) lowAlphaPixels++;
        if (x === 0 || x === width - 1 || y === 0 || y === height - 1) frameEdgeAlphaPixels++;
        minX = Math.min(minX, x); minY = Math.min(minY, y); maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
      }
    }
    const nonEmpty = maxX >= 0;
    if (nonEmpty) nonEmptyFrameIndices.push(order);
    const trimRect = mode === 'full-cell'
      ? { x: 0, y: 0, width, height }
      : (nonEmpty ? { x: Math.max(0, minX - padding), y: Math.max(0, minY - padding), width: 0, height: 0 } : { x: 0, y: 0, width: 1, height: 1 });
    if (mode === 'trim' && nonEmpty) {
      trimRect.width = Math.min(width, maxX + 1 + padding) - trimRect.x;
      trimRect.height = Math.min(height, maxY + 1 + padding) - trimRect.y;
    }
    const pixels = new Uint8ClampedArray(trimRect.width * trimRect.height * 4);
    for (let y = 0; y < trimRect.height; y++) {
      const start = ((trimRect.y + y) * width + trimRect.x) * 4;
      pixels.set(fullPixels.subarray(start, start + trimRect.width * 4), y * trimRect.width * 4);
    }
    const commonPixels = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < trimRect.height; y++) {
      const start = y * trimRect.width * 4;
      commonPixels.set(pixels.subarray(start, start + trimRect.width * 4), ((trimRect.y + y) * width + trimRect.x) * 4);
    }
    frames.push({ order, sourceSize: { width, height }, trimRect, pivot: { x: pivotX, y: pivotY, space: 'source-normalized' }, pivotPixels: { x: pivotX * width, y: pivotY * height }, pixels, commonPixels });
  }
  return { mode, frames, validation: { ok: gutterAlphaPixels === 0, reason: gutterAlphaPixels ? 'gutter-alpha-cross-cell-boundary' : null, metrics: { frameCount, nonEmptyFrameCount: nonEmptyFrameIndices.length, nonEmptyFrameIndices, gutterAlphaPixels, frameEdgeAlphaPixels, alphaPixels, lowAlphaPixels } } };
}

function effectConcatBytes(parts) {
  const length = parts.reduce((sum, part) => sum + part.length, 0);
  const output = new Uint8Array(length);
  let offset = 0;
  for (const part of parts) { output.set(part, offset); offset += part.length; }
  return output;
}

function effectPngChunk(type, bytes) {
  const typeBytes = new TextEncoder().encode(type);
  const payload = effectConcatBytes([typeBytes, bytes]);
  const crc = crc32Bytes(payload);
  return effectConcatBytes([
    new Uint8Array(uint32LE(bytes.length).reverse()), payload,
    new Uint8Array(uint32LE(crc).reverse()),
  ]);
}

// A filter-0 RGBA PNG with stored DEFLATE blocks is deterministic in every browser.
function encodeEffectFramePng(width, height, rgba) {
  if (rgba.length !== width * height * 4) throw new Error('effect PNG RGBA size mismatch');
  const scanlines = new Uint8Array(height * (width * 4 + 1));
  for (let y = 0; y < height; y++) scanlines.set(rgba.subarray(y * width * 4, (y + 1) * width * 4), y * (width * 4 + 1) + 1);
  const blocks = [];
  for (let offset = 0; offset < scanlines.length;) {
    const length = Math.min(65535, scanlines.length - offset), final = offset + length === scanlines.length;
    blocks.push(new Uint8Array([final ? 1 : 0, ...uint16LE(length), ...uint16LE((~length) & 0xffff)]), scanlines.subarray(offset, offset + length));
    offset += length;
  }
  let a = 1, b = 0;
  for (const value of scanlines) { a = (a + value) % 65521; b = (b + a) % 65521; }
  const zlib = effectConcatBytes([new Uint8Array([0x78, 0x01]), ...blocks, new Uint8Array([(b >>> 8) & 255, b & 255, (a >>> 8) & 255, a & 255])]);
  const ihdr = new Uint8Array(13);
  ihdr.set(uint32LE(width).reverse(), 0); ihdr.set(uint32LE(height).reverse(), 4);
  ihdr.set([8, 6, 0, 0, 0], 8);
  return effectConcatBytes([
    new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]),
    effectPngChunk('IHDR', ihdr), effectPngChunk('IDAT', zlib), effectPngChunk('IEND', new Uint8Array()),
  ]);
}

function decodeEffectFramePng(bytes, options = {}) {
  // Debug/round-trip validator for our deterministic encoder, not a general
  // PNG importer for untrusted archives.
  const MAX_DEBUG_BYTES = 268435456, MAX_CHUNK_BYTES = 67108864;
  const maxPixels = options.maxPixels ?? 8388608;
  if (!Number.isSafeInteger(maxPixels) || maxPixels < 1) throw new Error('invalid effect PNG pixel budget');
  if (!(bytes instanceof Uint8Array) || bytes.length < 45 || bytes.length > MAX_DEBUG_BYTES) throw new Error('invalid effect frame PNG length');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const read32 = offset => {
    if (!Number.isSafeInteger(offset) || offset < 0 || offset + 4 > bytes.length) throw new Error('invalid effect PNG bounds');
    return view.getUint32(offset, false);
  };
  if (read32(0) !== 0x89504e47 || read32(4) !== 0x0d0a1a0a) throw new Error('invalid effect frame PNG');
  let offset = 8, width = 0, height = 0, sawHeader = false, sawEnd = false;
  const idat = [];
  while (offset < bytes.length) {
    if (offset + 12 > bytes.length) throw new Error('invalid effect PNG chunk bounds');
    const length = read32(offset);
    if (length > MAX_CHUNK_BYTES || offset + 12 + length > bytes.length) throw new Error('invalid effect PNG chunk length');
    const typeBytes = bytes.subarray(offset + 4, offset + 8);
    const type = new TextDecoder().decode(typeBytes), data = bytes.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      if (sawHeader || offset !== 8 || length !== 13) throw new Error('invalid effect PNG IHDR');
      width = read32(offset + 8); height = read32(offset + 12);
      if (!width || !height || width * height > maxPixels || !Number.isSafeInteger(width * height)) throw new Error('invalid effect PNG dimensions');
      if (data[8] !== 8) throw new Error('unsupported effect PNG bit depth');
      if (data[9] !== 6) throw new Error('unsupported effect PNG color type');
      if (data[10] !== 0 || data[11] !== 0 || data[12] !== 0) throw new Error('unsupported effect PNG IHDR method');
      sawHeader = true;
    } else if (!sawHeader) throw new Error('effect PNG IHDR must be first');
    const declaredCrc = read32(offset + 8 + length);
    if (crc32Bytes(effectConcatBytes([typeBytes, data])) !== declaredCrc) throw new Error('invalid effect PNG chunk CRC');
    if (type === 'IDAT') idat.push(data);
    offset += 12 + length;
    if (type === 'IEND') { if (length !== 0) throw new Error('invalid effect PNG IEND'); sawEnd = true; break; }
  }
  if (!sawHeader || !sawEnd || !idat.length) throw new Error('incomplete effect frame PNG');
  const expectedRaw = height * (width * 4 + 1);
  if (!Number.isSafeInteger(expectedRaw) || expectedRaw > maxPixels * 4 + height) throw new Error('invalid effect PNG dimensions');
  const zlib = effectConcatBytes(idat), rawParts = [];
  if (zlib.length < 7 || zlib[0] !== 0x78) throw new Error('invalid effect PNG zlib stream');
  let cursor = 2, sawFinal = false, rawLength = 0;
  while (cursor < zlib.length - 4) {
    const header = zlib[cursor++], blockType = (header >>> 1) & 3;
    if (blockType !== 0) throw new Error('unsupported effect PNG compression');
    if (cursor + 4 > zlib.length - 4) throw new Error('invalid effect PNG block bounds');
    const length = zlib[cursor] | (zlib[cursor + 1] << 8);
    const inverse = zlib[cursor + 2] | (zlib[cursor + 3] << 8);
    cursor += 4;
    if (((length ^ inverse) & 0xffff) !== 0xffff) throw new Error('invalid effect PNG block');
    if (cursor + length > zlib.length - 4) throw new Error('invalid effect PNG block length');
    rawLength += length;
    if (!Number.isSafeInteger(rawLength) || rawLength > expectedRaw) throw new Error('invalid effect PNG inflated size');
    rawParts.push(zlib.subarray(cursor, cursor + length)); cursor += length;
    if (header & 1) { sawFinal = true; break; }
  }
  if (!sawFinal || cursor !== zlib.length - 4) throw new Error('invalid effect PNG zlib termination');
  if (rawLength !== expectedRaw) throw new Error('invalid effect PNG dimensions');
  const raw = effectConcatBytes(rawParts), stride = width * 4 + 1;
  if (!Number.isSafeInteger(stride) || raw.length !== height * stride) throw new Error('invalid effect PNG dimensions');
  const rgba = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    if (raw[y * stride] !== 0) throw new Error('unsupported effect PNG filter');
    rgba.set(raw.subarray(y * stride + 1, (y + 1) * stride), y * width * 4);
  }
  return { width, height, data: rgba };
}

// Effect export intentionally stays below a 192 MiB conservative multi-buffer
// estimate (source/slice/common-canvas/PNG/ZIP copies), and at most 8 Mi RGBA
// pixels. This is an export boundary, not a general image/preview limit.
const EFFECT_EXPORT_LIMITS = Object.freeze({
  maxFrames: 4096,
  maxTotalPixels: 8388608,
  sourceBytesPerPixelEstimate: 4,
  frameBytesPerPixelEstimate: 20,
  maxWorkingBytes: 201326592,
});

function checkEffectExportBudget(imageData, gridContract) {
  const integer = (value, name, min = 1) => {
    const number = Number(value);
    if (!Number.isSafeInteger(number) || number < min) throw new Error(`invalid effect export ${name}`);
    return number;
  };
  if (!imageData || !Number.isSafeInteger(imageData.width) || !Number.isSafeInteger(imageData.height) || imageData.width < 1 || imageData.height < 1 || !imageData.data) throw new Error('RGBA imageData required');
  if (!gridContract || typeof gridContract !== 'object') throw new Error('effect export grid contract required');
  const rows = integer(gridContract.rows, 'rows'), columns = integer(gridContract.columns, 'columns');
  const width = integer(gridContract.cell?.width, 'cell.width'), height = integer(gridContract.cell?.height, 'cell.height');
  const gap = integer(gridContract.gap ?? 0, 'gap', 0);
  const frameCount = integer(gridContract.frameCount ?? gridContract.frame_count, 'frameCount');
  const safeProduct = (left, right, name) => {
    const product = left * right;
    if (!Number.isSafeInteger(product)) throw new Error(`effect export too large: requested ${name} exceeds safe integer; allowed safe integer metadata`);
    return product;
  };
  const gridCells = safeProduct(rows, columns, 'grid cells');
  if (frameCount > gridCells) throw new Error('effect frame count exceeds declared grid');
  if (frameCount > EFFECT_EXPORT_LIMITS.maxFrames || gridCells > EFFECT_EXPORT_LIMITS.maxFrames) throw new Error(`effect export too large: requested ${frameCount} frames (${gridCells} grid cells); allowed ${EFFECT_EXPORT_LIMITS.maxFrames} frames/metadata entries`);
  const expectedWidth = safeProduct(columns, width, 'sheet width') + safeProduct(columns - 1, gap, 'horizontal gaps');
  const expectedHeight = safeProduct(rows, height, 'sheet height') + safeProduct(rows - 1, gap, 'vertical gaps');
  if (!Number.isSafeInteger(expectedWidth) || !Number.isSafeInteger(expectedHeight)) throw new Error('effect export too large: requested sheet dimensions exceed safe integer; allowed safe integer dimensions');
  if (imageData.width !== expectedWidth || imageData.height !== expectedHeight) throw new Error(`effect sheet ${imageData.width}x${imageData.height} does not match declared grid ${expectedWidth}x${expectedHeight}`);
  const framePixels = safeProduct(width, height, 'pixels per frame');
  const totalPixels = safeProduct(framePixels, frameCount, 'total frame pixels');
  const sourcePixels = safeProduct(expectedWidth, expectedHeight, 'source sheet pixels');
  const sourceBytes = safeProduct(sourcePixels, EFFECT_EXPORT_LIMITS.sourceBytesPerPixelEstimate, 'source sheet bytes');
  const frameWorkingBytes = safeProduct(totalPixels, EFFECT_EXPORT_LIMITS.frameBytesPerPixelEstimate, 'frame working bytes');
  const workingBytes = sourceBytes + frameWorkingBytes;
  if (!Number.isSafeInteger(workingBytes)) throw new Error('effect export too large: requested estimated working bytes exceed safe integer; allowed safe integer byte estimate');
  if (totalPixels > EFFECT_EXPORT_LIMITS.maxTotalPixels || workingBytes > EFFECT_EXPORT_LIMITS.maxWorkingBytes) {
    throw new Error(`effect export too large: requested ${totalPixels} RGBA pixels / ${workingBytes} estimated working bytes; allowed ${EFFECT_EXPORT_LIMITS.maxTotalPixels} pixels / ${EFFECT_EXPORT_LIMITS.maxWorkingBytes} bytes`);
  }
  return { rows, columns, width, height, gap, frameCount, gridCells, sourcePixels, totalPixels, workingBytes };
}

function buildEffectExportPackage(imageData, gridContract, mode, options = {}) {
  if (!['full-cell', 'trim'].includes(mode)) throw new Error('effect export mode must be full-cell or trim');
  checkEffectExportBudget(imageData, gridContract);
  const sliced = sliceEffectImageData(imageData, gridContract, mode);
  if (!sliced.validation.ok) throw new Error(`effect export blocked: ${sliced.validation.reason}`);
  const fps = Number(options.fps ?? (gridContract.durationMs ? 1000 / gridContract.durationMs : 12));
  if (!Number.isFinite(fps) || fps <= 0 || fps > 120) throw new Error('effect export FPS must be between 1 and 120');
  const durationMs = Math.round(1000 / fps), sourceSize = { ...sliced.frames[0].sourceSize };
  const manifest = {
    schema_version: 'asset-studio.effect-sequence/v1',
    kind: 'effect_sequence',
    effect_category: String(options.effectCategory || 'Effect'),
    frame_count: sliced.frames.length,
    frame_order: 'row-major',
    source_size: sourceSize,
    logical_frame_size: { ...sourceSize },
    rows: Number(gridContract.rows),
    columns: Number(gridContract.columns),
    cell: { width: sourceSize.width, height: sourceSize.height },
    gap: Number(gridContract.gap || 0),
    padding: Number(gridContract.trimPadding ?? gridContract.trim_padding ?? 1),
    loop: String(options.loop || 'one-shot'),
    fps,
    duration_ms: durationMs,
    total_duration_ms: durationMs * sliced.frames.length,
    pivot: { x: sliced.frames[0].pivot.x, y: sliced.frames[0].pivot.y, coordinate_convention: 'source-normalized-top-left' },
    trim_mode: mode,
    frames: sliced.frames.map(frame => ({
      file: `frame-${String(frame.order).padStart(3, '0')}.png`,
      order: frame.order,
      duration_ms: durationMs,
      trim_rect: { x: frame.trimRect.x, y: frame.trimRect.y, width: frame.trimRect.width, height: frame.trimRect.height },
    })),
  };
  // Reuse the same budget gate immediately before PNG and ZIP buffers fan out.
  checkEffectExportBudget(imageData, gridContract);
  const encoder = new TextEncoder();
  const files = [{ name: 'manifest.json', bytes: encoder.encode(`${JSON.stringify(manifest, null, 2)}\n`) }];
  sliced.frames.forEach((frame, index) => files.push({
    name: manifest.frames[index].file,
    bytes: encodeEffectFramePng(frame.trimRect.width, frame.trimRect.height, frame.pixels),
  }));
  return {
    manifest, files,
    zipBlob: buildStoredZip(files),
    zipName: mode === 'trim' ? 'effect-sequence-trim-metadata.zip' : 'effect-sequence-full-cell.zip',
  };
}

function parseEffectStoredZip(bytes) {
  // Debug/round-trip validator for buildStoredZip output only. It deliberately
  // does not implement a general ZIP central-directory or untrusted importer.
  const MAX_ARCHIVE_BYTES = 268435456, MAX_ENTRIES = 4097;
  if (!(bytes instanceof Uint8Array) || bytes.length < 30 || bytes.length > MAX_ARCHIVE_BYTES) throw new Error('invalid effect ZIP length');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength), files = new Map();
  let offset = 0, totalSize = 0;
  while (offset + 4 <= bytes.length && view.getUint32(offset, true) === 0x04034b50) {
    if (files.size >= MAX_ENTRIES || offset + 30 > bytes.length) throw new Error('effect ZIP entry/header limit exceeded');
    const flags = view.getUint16(offset + 6, true), method = view.getUint16(offset + 8, true);
    const declaredCrc = view.getUint32(offset + 14, true);
    const compressedSize = view.getUint32(offset + 18, true), size = view.getUint32(offset + 22, true);
    const nameLength = view.getUint16(offset + 26, true), extraLength = view.getUint16(offset + 28, true);
    if (flags !== 0) throw new Error('effect ZIP flags/data descriptors unsupported');
    if (method !== 0) throw new Error('effect ZIP must use stored entries');
    if (compressedSize !== size) throw new Error('effect ZIP stored entry size mismatch');
    const nameStart = offset + 30, dataStart = nameStart + nameLength + extraLength, dataEnd = dataStart + size;
    if (!nameLength || dataStart < nameStart || dataEnd < dataStart || dataEnd > bytes.length) throw new Error('effect ZIP entry bounds/size invalid');
    totalSize += size;
    if (!Number.isSafeInteger(totalSize) || totalSize > MAX_ARCHIVE_BYTES) throw new Error('effect ZIP declared size limit exceeded');
    const name = new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(nameStart, nameStart + nameLength));
    if (files.has(name)) throw new Error(`duplicate effect ZIP entry: ${name}`);
    const data = bytes.slice(dataStart, dataEnd);
    if (crc32Bytes(data) !== declaredCrc) throw new Error(`effect ZIP entry CRC mismatch: ${name}`);
    files.set(name, data);
    offset = dataEnd;
  }
  if (!files.size) throw new Error('effect ZIP has no stored entries');
  if (offset + 4 > bytes.length || view.getUint32(offset, true) !== 0x02014b50) throw new Error('effect ZIP local entry bounds invalid');
  return files;
}

async function reconstructEffectExportZip(zipBlob) {
  const bytes = zipBlob instanceof Uint8Array ? zipBlob : new Uint8Array(await zipBlob.arrayBuffer());
  const files = parseEffectStoredZip(bytes);
  if (!files.has('manifest.json')) throw new Error('effect ZIP manifest.json missing');
  const manifest = JSON.parse(new TextDecoder().decode(files.get('manifest.json')));
  const declared = new Set(['manifest.json', ...manifest.frames.map(frame => frame.file)]);
  if (declared.size !== files.size || [...files.keys()].some(name => !declared.has(name))) throw new Error('effect ZIP has undeclared frame entries');
  const frames = manifest.frames.map(frame => {
    const png = files.get(frame.file);
    if (!png) throw new Error(`effect ZIP frame missing: ${frame.file}`);
    const decoded = decodeEffectFramePng(png), source = manifest.source_size, rect = frame.trim_rect;
    if (decoded.width !== rect.width || decoded.height !== rect.height) throw new Error(`effect ZIP trim metadata mismatch: ${frame.file}`);
    const common = new Uint8ClampedArray(source.width * source.height * 4);
    for (let y = 0; y < rect.height; y++) common.set(decoded.data.subarray(y * rect.width * 4, (y + 1) * rect.width * 4), ((rect.y + y) * source.width + rect.x) * 4);
    return { order: frame.order, width: source.width, height: source.height, data: common };
  });
  return { manifest, frames };
}

function effectGridContractFromControls() {
  const sprite = buildSpriteContract('effect');
  return { schemaVersion: 'effect-grid/v1', order: 'row-major', rows: sprite.rows, columns: sprite.columns, cell: { width: sprite.envelope_width, height: sprite.envelope_height }, gap: sprite.gap, frameCount: sprite.frame_count, durationMs: Math.round(1000 / sprite.fps), trimPadding: 1, pivot: { x: sprite.pivot.x, y: sprite.pivot.y, space: 'source-normalized' } };
}

function effectFrameCanvas(frame, previewMode = 'effect-only') {
  const el = document.createElement('canvas');
  el.width = frame.sourceSize.width; el.height = frame.sourceSize.height;
  const ctx = el.getContext('2d');
  if (previewMode === 'actor-composite') {
    ctx.fillStyle = 'rgba(80,100,140,.38)';
    ctx.beginPath(); ctx.arc(el.width / 2, el.height * .32, Math.max(2, el.width * .09), 0, Math.PI * 2); ctx.fill();
    ctx.fillRect(el.width * .43, el.height * .4, el.width * .14, el.height * .42);
  }
  const effectCanvas = document.createElement('canvas');
  effectCanvas.width = frame.sourceSize.width; effectCanvas.height = frame.sourceSize.height;
  effectCanvas.getContext('2d').putImageData(new ImageData(frame.commonPixels, frame.sourceSize.width, frame.sourceSize.height), 0, 0);
  ctx.drawImage(effectCanvas, 0, 0);
  return el;
}

async function buildEffectSequencePreview() {
  if (!isPixelEffectAssetType()) throw new Error('effect preview is only available for effect sequences');
  const target = activeSpriteTarget();
  if (!target) throw new Error('이미지 레이어 선택 필요');
  const contract = effectGridContractFromControls();
  const image = await loadHtmlImage(await imageObjectDataUrl(target));
  const sourceCanvas = document.createElement('canvas');
  sourceCanvas.width = image.naturalWidth || image.width; sourceCanvas.height = image.naturalHeight || image.height;
  const sourceContext = sourceCanvas.getContext('2d', { willReadFrequently: true });
  sourceContext.drawImage(image, 0, 0);
  const trimPolicy = $('effectTrimPolicy')?.value || 'preserve-envelope';
  const trimMode = ['trim', 'tight'].includes(trimPolicy) ? 'trim' : 'full-cell';
  const result = sliceEffectImageData(sourceContext.getImageData(0, 0, sourceCanvas.width, sourceCanvas.height), contract, trimMode);
  const previewMode = $('effectPreviewMode')?.value || 'effect-only';
  const urls = result.frames.map(frame => effectFrameCanvas(frame, previewMode).toDataURL('image/png'));
  const stage = $('effectPreviewStage'), pivot = result.frames[0]?.pivotPixels || { x: 0, y: 0 };
  if (stage) {
    const previewScale = 96 / Math.max(contract.cell.width, contract.cell.height);
    stage.style.setProperty('--effect-frame-width', `${contract.cell.width * previewScale}px`);
    stage.style.setProperty('--effect-frame-height', `${contract.cell.height * previewScale}px`);
    stage.style.setProperty('--effect-pivot-x', `${pivot.x / contract.cell.width * 100}%`);
    stage.style.setProperty('--effect-pivot-y', `${pivot.y / contract.cell.height * 100}%`);
    stage.dataset.previewMode = previewMode;
  }
  const metrics = result.validation.metrics;
  if ($('effectQaSummary')) $('effectQaSummary').textContent = `${result.validation.ok ? 'PASS' : 'FAIL'} · frames ${metrics.frameCount} · non-empty ${metrics.nonEmptyFrameCount} [${metrics.nonEmptyFrameIndices.join(',')}] · gutter α ${metrics.gutterAlphaPixels} · edge ${metrics.frameEdgeAlphaPixels} · low-α(1–20) ${metrics.lowAlphaPixels}/${metrics.alphaPixels}`;
  playEffectSequencePreview(urls);
  return result;
}

function selectedEffectImageTarget() {
  const target = active();
  return target?.type === 'image' && !target.isDrawingLayer && !target.excludeFromLayers ? target : null;
}

function syncEffectExportControlsState() {
  const disabled = !isPixelEffectAssetType() || !selectedEffectImageTarget();
  ['exportEffectFullCellZip', 'exportEffectTrimZip'].forEach(id => {
    const button = $(id);
    if (button) button.disabled = disabled;
  });
}

async function selectedEffectImageData(gridContract = null) {
  const target = selectedEffectImageTarget();
  if (!target) throw new Error('이미지 레이어 선택 필요');
  const image = await loadHtmlImage(await imageObjectDataUrl(target));
  const width = image.naturalWidth || image.width, height = image.naturalHeight || image.height;
  // Preflight before canvas allocation/getImageData; package construction repeats
  // this same gate before slicing and before PNG/ZIP buffer creation.
  if (gridContract) checkEffectExportBudget({ width, height, data: true }, gridContract);
  const sourceCanvas = document.createElement('canvas');
  sourceCanvas.width = width;
  sourceCanvas.height = height;
  const context = sourceCanvas.getContext('2d', { willReadFrequently: true });
  context.drawImage(image, 0, 0);
  return context.getImageData(0, 0, sourceCanvas.width, sourceCanvas.height);
}

async function exportEffectSequenceZip(mode) {
  const buttons = ['exportEffectFullCellZip', 'exportEffectTrimZip'].map(id => $(id)).filter(Boolean);
  buttons.forEach(button => { button.disabled = true; });
  try {
    if (!isPixelEffectAssetType()) throw new Error('effect export is only available for effect sequences');
    const contract = effectGridContractFromControls();
    const imageData = await selectedEffectImageData(contract);
    const packageResult = buildEffectExportPackage(
      imageData, contract, mode,
      { effectCategory: $('effectCategory')?.value || 'Effect', loop: $('effectLoop')?.value || 'one-shot', fps: +($('effectFps')?.value || 12) },
    );
    downloadBlob(packageResult.zipBlob, packageResult.zipName);
    setStatus(`이펙트 ${mode === 'trim' ? 'Trim+metadata' : 'Full-cell'} ZIP 내보내기 완료: ${packageResult.manifest.frame_count} frames`);
    return packageResult;
  } catch (err) {
    console.error(err);
    alert(`이펙트 ZIP 내보내기 실패: ${err.message}`);
    setStatus(`이펙트 ZIP 내보내기 실패: ${err.message}`);
    throw err;
  } finally {
    // Never leave either export action stuck busy after preflight/build errors.
    syncEffectExportControlsState();
  }
}

function playEffectSequencePreview(urls) {
  if (animationPreviewTimer) clearInterval(animationPreviewTimer);
  animationPreviewTimer = true;
  let index = 0, direction = 1;
  const draw = () => {
    if ($('effectPreviewStage')) $('effectPreviewStage').innerHTML = `<span class="effect-frame-viewport"><img alt="effect common-canvas preview" src="${urls[index]}"><i class="effect-pivot-crosshair" aria-label="normalized pivot"></i></span><span>${index + 1}/${urls.length} · ${$('effectPreviewMode')?.value || 'effect-only'}</span>`;
    const loop = $('effectLoop')?.value || 'one-shot';
    if (loop === 'one-shot' && index === urls.length - 1) { if (animationPreviewTimer !== true) clearInterval(animationPreviewTimer); animationPreviewTimer = null; return; }
    if (loop === 'ping-pong') { if (index === urls.length - 1) direction = -1; if (index === 0) direction = 1; index = clamp(index + direction, 0, urls.length - 1); }
    else index = (index + 1) % urls.length;
  };
  draw();
  if (urls.length > 1 && animationPreviewTimer !== null) animationPreviewTimer = setInterval(draw, Math.round(1000 / clamp(+($('effectFps')?.value || 12), 1, 120)));
}

function currentGridSpriteSlices() {
  if (spriteSlices.some(s => s.grid)) return spriteSlices;
  return buildGridSpriteSlices();
}

function currentAnimationSpriteSlices(frameCount = Math.max(1, +($('animFrameCount')?.value || 4))) {
  if (isPixelEffectAssetType()) return buildGridSpriteSlices().slice(0, requestedPixelFrameCount());
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
    if (mode === 'once') {
      if (idx >= frames.length - 1) {
        if (animationPreviewTimer !== null) clearInterval(animationPreviewTimer);
        animationPreviewTimer = null;
        return false;
      }
      idx += 1;
    } else if (mode === 'pingpong') {
      if (idx >= frames.length - 1) dir = -1;
      if (idx <= 0) dir = 1;
      idx = clamp(idx + dir, 0, frames.length - 1);
    } else {
      idx = (idx + 1) % frames.length;
    }
    return true;
  };
  if (draw()) animationPreviewTimer = setInterval(draw, Math.round(1000 / fps));
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
    if (isPixelEffectAssetType()) gridSlices = gridSlices.slice(0, requestedPixelFrameCount());
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
    }, ['id','name','_originalSrc','_preservedOriginal','_assetId','_assetName','excludeFromLayers','isDrawingStroke','isDrawingLayer','layerId','locked','parentLayerName','isMaskOverlay','maskRegionId','maskRole','targetLayerId']);
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

function flipSelected(axis) {
  const obj = selectedLayerObject();
  if (!obj || obj.isDrawingLayer) {
    setStatus('반전할 오브젝트를 선택하세요.');
    return;
  }
  const prop = axis === 'horizontal' ? 'flipX' : 'flipY';
  obj.set(prop, !obj[prop]);
  obj.setCoords?.();
  canvas.renderAll();
  saveHistory(axis === 'horizontal' ? 'Flip horizontal' : 'Flip vertical');
  syncProps();
  renderLayers();
  setStatus(axis === 'horizontal' ? '선택 레이어를 좌우 반전했습니다.' : '선택 레이어를 상하 반전했습니다.');
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

function syncSpriteAfterCanvasResize({ rebuildPreview = true } = {}) {
  const target = activeSpriteTarget();
  if (!target || target.type !== 'image') return;
  spriteSourceLayerId = layerKey(target);

  // Canvas size changes do not change the image source pixels, but they can make
  // the visible Fabric bounds/grid inputs stale. Keep sprite slices in selected
  // image-relative coordinates, then re-render guide boxes from the target's new
  // canvas bounds. For grid-mode slices, rebuild the grid from the selected
  // image's displayed bounds so crop/export/animation preview stay aligned.
  if (spriteSlices.some(s => s.grid)) {
    updateGridCellSizeFromSelectedLayer({ renderExisting: true });
  } else if (spriteSlices.length) {
    renderSpriteGuides();
  } else {
    applyPixelWorkflowGridDefaults(target);
  }

  if (rebuildPreview && animationPreviewFrames.length) {
    buildAnimationPreview().catch(err => {
      console.warn('Animation preview rebuild after canvas resize failed', err);
      spriteSummary(`캔버스 크기 변경 후 미리보기 재생성 실패: ${err.message}`);
    });
  }
}

function setCanvasSize(w, h) {
  const priorSpriteTarget = activeSpriteTarget();
  const priorSpriteLayerId = layerKey(priorSpriteTarget) || spriteSourceLayerId;
  canvas.setWidth(w); canvas.setHeight(h);
  canvas.getObjects().forEach(o => { if (o.isDrawingLayer) o.set({ width: w, height: h }); });
  $('canvasW').value = w; $('canvasH').value = h;
  if (priorSpriteLayerId) spriteSourceLayerId = priorSpriteLayerId;
  syncSpriteAfterCanvasResize();
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
      ...uint16LE(0), ...uint16LE(0x21), ...uint32LE(crc), ...uint32LE(data.length), ...uint32LE(data.length),
      ...uint16LE(nameBytes.length), ...uint16LE(0),
    ]);
    chunks.push(local, nameBytes, data);
    const centralHeader = new Uint8Array([
      ...uint32LE(0x02014b50), ...uint16LE(0x0314), ...uint16LE(20), ...uint16LE(0), ...uint16LE(0),
      ...uint16LE(0), ...uint16LE(0x21), ...uint32LE(crc), ...uint32LE(data.length), ...uint32LE(data.length),
      ...uint16LE(nameBytes.length), ...uint16LE(0), ...uint16LE(0), ...uint16LE(0), ...uint16LE(0),
      ...uint32LE(0x81a40000), ...uint32LE(offset),
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
  setStatus('Mask inverted visually. 반전 미리보기를 적용했습니다.');
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
    target._preservedOriginal = true;
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
  const editOnlyTools = ['crop', 'brush', 'pencil', 'eraser', 'mask', 'text', 'shape', 'upload'];
  if (workspaceMode !== 'edit' && editOnlyTools.includes(tool)) setWorkspaceMode('edit', false);

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

function setWorkspaceMode(mode, activateModeTool = true) {
  workspaceMode = mode === 'edit' ? 'edit' : 'ai';
  const isAiMode = workspaceMode === 'ai';

  $('aiToolGroup')?.classList.toggle('hidden', !isAiMode);
  $('editToolGroup')?.classList.toggle('hidden', isAiMode);
  document.querySelectorAll('#workspaceModeSwitch [data-workspace-mode]').forEach(button => {
    const isActive = button.dataset.workspaceMode === workspaceMode;
    button.setAttribute('aria-pressed', String(isActive));
    button.classList.toggle('active', isActive);
  });

  if (!activateModeTool) return;
  if (isAiMode) {
    activateTool('ai');
    return;
  }

  const currentToolButton = document.querySelector(`.tool-button[data-tool="${currentTool}"]`);
  const currentToolIsAvailable = currentToolButton && !currentToolButton.closest('#aiToolGroup');
  if (currentTool === 'ai' || !currentToolIsAvailable) activateTool('select');
}

$('workspaceModeSwitch')?.addEventListener('click', event => {
  const button = event.target.closest('[data-workspace-mode]');
  if (!button || !event.currentTarget.contains(button)) return;
  setWorkspaceMode(button.dataset.workspaceMode);
});

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
$('flipHorizontal').onclick = () => flipSelected('horizontal');
$('flipVertical').onclick = () => flipSelected('vertical');
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
if ($('buildEffectPreview')) $('buildEffectPreview').onclick = () => buildEffectSequencePreview().catch(err => { console.error(err); alert(`이펙트 미리보기 실패: ${err.message}`); setStatus(`이펙트 미리보기 실패: ${err.message}`); });
if ($('stopEffectPreview')) $('stopEffectPreview').onclick = stopAnimationPreview;
if ($('exportEffectFullCellZip')) $('exportEffectFullCellZip').onclick = () => exportEffectSequenceZip('full-cell').catch(() => {});
if ($('exportEffectTrimZip')) $('exportEffectTrimZip').onclick = () => exportEffectSequenceZip('trim').catch(() => {});
if ($('effectPreviewMode')) $('effectPreviewMode').addEventListener('change', () => {
  if ($('effectPreviewStage')?.querySelector('img')) buildEffectSequencePreview().catch(err => setStatus(`이펙트 미리보기 갱신 실패: ${err.message}`));
});
window.__assetStudioDebug = { ...(window.__assetStudioDebug || {}), sliceEffectImageData, buildEffectExportPackage, reconstructEffectExportZip, effectGridContractFromControls, buildEffectSequencePreview };

// C4 tile packages intentionally have their own schema/parser.  They only share
// the audited byte-level PNG, CRC and ZIP primitives with effect export.
const TILE_EXPORT_LIMITS = Object.freeze({ maxCells:4096, maxFiles:4104, maxSourcePixels:16777216, maxPayloadBytes:67108864, maxWorkingBytes:201326592 });
function tileCanonical(value) {
  if (Array.isArray(value)) return value.map(tileCanonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k=>[k,tileCanonical(value[k])]));
  return value;
}
function tileJson(value) { return `${JSON.stringify(tileCanonical(value),null,2)}\n`; }
function tileSha256(bytes) {
  const K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2], H=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
  const n=bytes.length, padded=((n+9+63)>>6)<<6, msg=new Uint8Array(padded);msg.set(bytes);msg[n]=128;const dv=new DataView(msg.buffer),bits=n*8;dv.setUint32(padded-8,Math.floor(bits/4294967296));dv.setUint32(padded-4,bits>>>0);
  const r=(x,n)=>(x>>>n)|(x<<(32-n)),w=new Uint32Array(64);for(let o=0;o<padded;o+=64){for(let i=0;i<16;i++)w[i]=dv.getUint32(o+i*4);for(let i=16;i<64;i++){const a=w[i-15],b=w[i-2];w[i]=((r(a,7)^r(a,18)^(a>>>3))+w[i-16]+(r(b,17)^r(b,19)^(b>>>10))+w[i-7])>>>0;}let [a,b,c,d,e,f,g,h]=H;for(let i=0;i<64;i++){const t1=(h+(r(e,6)^r(e,11)^r(e,25))+((e&f)^(~e&g))+K[i]+w[i])>>>0,t2=((r(a,2)^r(a,13)^r(a,22))+((a&b)^(a&c)^(b&c)))>>>0;h=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}H[0]=(H[0]+a)>>>0;H[1]=(H[1]+b)>>>0;H[2]=(H[2]+c)>>>0;H[3]=(H[3]+d)>>>0;H[4]=(H[4]+e)>>>0;H[5]=(H[5]+f)>>>0;H[6]=(H[6]+g)>>>0;H[7]=(H[7]+h)>>>0;}return H.map(x=>x.toString(16).padStart(8,'0')).join('');
}
function checkTileExportBudget(imageData,contract) {
  const integer=(v,n,min=1)=>{v=Number(v);if(!Number.isSafeInteger(v)||v<min)throw new Error(`invalid tile export ${n}`);return v;};
  if(!imageData||!Number.isSafeInteger(imageData.width)||!Number.isSafeInteger(imageData.height)||imageData.width<1||imageData.height<1)throw new Error('RGBA imageData required');
  const width=integer(contract?.tile_size?.width,'tile width'),height=integer(contract?.tile_size?.height,'tile height'),rows=integer(contract.rows,'rows'),columns=integer(contract.columns,'columns'),margin=integer(contract.margin??0,'margin',0),spacing=integer(contract.spacing??0,'spacing',0),cells=rows*columns,pixels=imageData.width*imageData.height;
  if(!Number.isSafeInteger(cells)||cells>TILE_EXPORT_LIMITS.maxCells)throw new Error(`tile export too large: requested ${cells} cells; allowed ${TILE_EXPORT_LIMITS.maxCells}`);
  const footprintW=margin*2+columns*width+(columns-1)*spacing,footprintH=margin*2+rows*height+(rows-1)*spacing;
  if(!Number.isSafeInteger(pixels)||pixels>TILE_EXPORT_LIMITS.maxSourcePixels)throw new Error(`tile export too large: requested ${pixels} source pixels; allowed ${TILE_EXPORT_LIMITS.maxSourcePixels}`);
  if(footprintW>imageData.width||footprintH>imageData.height)throw new Error(`tile atlas ${imageData.width}x${imageData.height} truncates declared grid ${footprintW}x${footprintH}`);
  const working=(pixels+cells*width*height)*12;if(!Number.isSafeInteger(working)||working>TILE_EXPORT_LIMITS.maxWorkingBytes)throw new Error(`tile export too large: requested ${working} working bytes; allowed ${TILE_EXPORT_LIMITS.maxWorkingBytes}`);
  return {width,height,rows,columns,margin,spacing,cells,footprintW,footprintH,pixels,working};
}
function tileZipBytes(files) {
  if(files.length>TILE_EXPORT_LIMITS.maxFiles)throw new Error('tile export file-count budget exceeded');const enc=new TextEncoder(),local=[],central=[];let offset=0,total=0;
  for(const file of files){const n=enc.encode(file.name),d=file.bytes,crc=crc32Bytes(d);total+=d.length;if(total>TILE_EXPORT_LIMITS.maxPayloadBytes)throw new Error('tile export archive byte budget exceeded');const h=new Uint8Array([...uint32LE(0x04034b50),...uint16LE(20),...uint16LE(0),...uint16LE(0),...uint16LE(0),...uint16LE(0),...uint32LE(crc),...uint32LE(d.length),...uint32LE(d.length),...uint16LE(n.length),...uint16LE(0)]);local.push(h,n,d);central.push(new Uint8Array([...uint32LE(0x02014b50),...uint16LE(20),...uint16LE(20),...uint16LE(0),...uint16LE(0),...uint16LE(0),...uint16LE(0),...uint32LE(crc),...uint32LE(d.length),...uint32LE(d.length),...uint16LE(n.length),...uint16LE(0),...uint16LE(0),...uint16LE(0),...uint16LE(0),...uint32LE(0),...uint32LE(offset)]),n);offset+=h.length+n.length+d.length;}
  const cs=central.reduce((a,x)=>a+x.length,0),end=new Uint8Array([...uint32LE(0x06054b50),...uint16LE(0),...uint16LE(0),...uint16LE(files.length),...uint16LE(files.length),...uint32LE(cs),...uint32LE(offset),...uint16LE(0)]);return effectConcatBytes([...local,...central,end]);
}
function tileMetadataValidation(metadata,count){const errors=[];const walk=(v,p)=>{if(Array.isArray(v)&&/(indices|tiles|tile_indices)$/i.test(p))v.forEach((n,i)=>{if(!Number.isInteger(n)||n<0||n>=count)errors.push(`${p}[${i}]`);});else if(v&&typeof v==='object')Object.entries(v).forEach(([k,z])=>walk(z,`${p}.${k}`));};walk(metadata,'metadata');return {valid:!errors.length,tile_count:count,invalid_paths:errors};}
function buildTileExportPackage(imageData,contract,assetType='tileset') {
  const b=checkTileExportBudget(imageData,contract);if(!imageData.data||imageData.data.length!==imageData.width*imageData.height*4)throw new Error('tile RGBA data size mismatch');const enc=new TextEncoder(),payload=[];
  const atlas=encodeEffectFramePng(imageData.width,imageData.height,imageData.data);payload.push({name:'atlas.png',bytes:atlas});const tiles=[];
  for(let row=0;row<b.rows;row++)for(let column=0;column<b.columns;column++){const index=row*b.columns+column,x=b.margin+column*(b.width+b.spacing),y=b.margin+row*(b.height+b.spacing),rgba=new Uint8ClampedArray(b.width*b.height*4);for(let yy=0;yy<b.height;yy++)rgba.set(imageData.data.subarray(((y+yy)*imageData.width+x)*4,((y+yy)*imageData.width+x+b.width)*4),yy*b.width*4);const path=`tiles/tile-${String(index).padStart(4,'0')}.png`;payload.push({name:path,bytes:encodeEffectFramePng(b.width,b.height,rgba)});tiles.push({index,row,column,x,y,w:b.width,h:b.height,path});}
  const terrain={schema_version:'asset-studio.tile-terrain/v1',topology:contract.topology??null,inner_corners:!!contract.inner_corners,outer_corners:!!contract.outer_corners,transitions:contract.transitions||[],terrain_types:contract.terrain_types||[],variants:contract.variants||[],mapping:{order:'row-major',tile_count:b.cells,coverage:'declared-only',engine_rule_counts:null}};
  const metadata={schema_version:'asset-studio.tile-engine-metadata/v1',collision:contract.metadata?.collision||{},occlusion:contract.metadata?.occlusion||{},navigation:contract.metadata?.navigation||{},custom:contract.metadata?.custom||{},tile_index_validation:tileMetadataValidation(contract.metadata||{},b.cells)};
  payload.push({name:'terrain-mapping.json',bytes:enc.encode(tileJson(terrain))},{name:'engine-metadata.json',bytes:enc.encode(tileJson(metadata))});const warnings=[];
  if((contract.shape||'square')==='square'){const esc=s=>String(s).replace(/[&<>\x22\x27]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));const tsx=`<?xml version="1.0" encoding="UTF-8"?>\n<tileset version="1.10" tiledversion="1.10.2" name="${esc(assetType)}" tilewidth="${b.width}" tileheight="${b.height}" tilecount="${b.cells}" columns="${b.columns}" margin="${b.margin}" spacing="${b.spacing}"><image source="atlas.png" width="${imageData.width}" height="${imageData.height}"/></tileset>\n`,csv=Array.from({length:b.cells},(_,i)=>i+1).join(','),tmx=`<?xml version="1.0" encoding="UTF-8"?>\n<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" renderorder="right-down" width="${b.columns}" height="${b.rows}" tilewidth="${b.width}" tileheight="${b.height}" infinite="0"><tileset firstgid="1" source="tileset.tsx"/><layer id="1" name="Tiles" width="${b.columns}" height="${b.rows}"><data encoding="csv">${csv}</data></layer></map>\n`;payload.push({name:'tileset.tsx',bytes:enc.encode(tsx)},{name:'map.tmx',bytes:enc.encode(tmx)});}else warnings.push(`Tiled XML omitted: unsupported tile shape ${contract.shape}`);
  const inventory=payload.map(f=>({path:f.name,bytes:f.bytes.length,crc32:crc32Bytes(f.bytes).toString(16).padStart(8,'0'),sha256:tileSha256(f.bytes)}));const manifest={schema_version:'asset-studio.tile-package/v1',family:'tile',type:String(assetType),order:'row-major',atlas:{path:'atlas.png',width:imageData.width,height:imageData.height},contract:tileCanonical(contract),grid:{rows:b.rows,columns:b.columns,tile_width:b.width,tile_height:b.height,margin:b.margin,spacing:b.spacing,footprint_width:b.footprintW,footprint_height:b.footprintH},tiles,artifacts:{terrain_mapping:'terrain-mapping.json',engine_metadata:'engine-metadata.json',tsx:payload.some(f=>f.name==='tileset.tsx')?'tileset.tsx':null,tmx:payload.some(f=>f.name==='map.tmx')?'map.tmx':null},warnings,inventory};const files=[{name:'manifest.json',bytes:enc.encode(tileJson(manifest))},...payload],zipBytes=tileZipBytes(files);return {manifest,files,zipBytes,zipBlob:new Blob([zipBytes],{type:'application/zip'}),zipName:'tile-package.zip'};
}
function parseTileStoredZip(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 52 || bytes.length > TILE_EXPORT_LIMITS.maxPayloadBytes) throw new Error('invalid tile ZIP bounds');
  const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength), dec=new TextDecoder('utf-8',{fatal:true}), eocd=bytes.length-22;
  const safe=(start,length,limit=bytes.length)=>Number.isSafeInteger(start)&&Number.isSafeInteger(length)&&start>=0&&length>=0&&start<=limit&&length<=limit-start;
  if (v.getUint32(eocd,true)!==0x06054b50 || v.getUint16(eocd+20,true)!==0) throw new Error('invalid tile ZIP EOCD/trailing data');
  const disk=v.getUint16(eocd+4,true),centralDisk=v.getUint16(eocd+6,true),diskCount=v.getUint16(eocd+8,true),count=v.getUint16(eocd+10,true),centralSize=v.getUint32(eocd+12,true),centralOffset=v.getUint32(eocd+16,true);
  if (disk||centralDisk||diskCount!==count||!count||count>TILE_EXPORT_LIMITS.maxFiles||count===0xffff||centralSize===0xffffffff||centralOffset===0xffffffff) throw new Error('invalid tile ZIP EOCD count/disk/ZIP64');
  if (!safe(centralOffset,centralSize,eocd)||centralOffset+centralSize!==eocd) throw new Error('invalid tile ZIP central offset/size');
  const central=[], names=new Set(), offsets=new Set(); let o=centralOffset;
  for(let i=0;i<count;i++) {
    if(!safe(o,46,eocd)||v.getUint32(o,true)!==0x02014b50)throw new Error('invalid tile ZIP central directory entry');
    const flags=v.getUint16(o+8,true),method=v.getUint16(o+10,true),crc=v.getUint32(o+16,true),cs=v.getUint32(o+20,true),size=v.getUint32(o+24,true),nl=v.getUint16(o+28,true),xl=v.getUint16(o+30,true),cl=v.getUint16(o+32,true),diskStart=v.getUint16(o+34,true),localOffset=v.getUint32(o+42,true),length=46+nl+xl+cl;
    if(flags||method||!nl||xl||cl||diskStart||cs!==size||cs===0xffffffff||size===0xffffffff||localOffset===0xffffffff||!safe(o,length,eocd))throw new Error('invalid tile ZIP central flags/method/size/extra/comment/ZIP64');
    let name;try{name=dec.decode(bytes.subarray(o+46,o+46+nl));}catch(_){throw new Error('invalid tile ZIP UTF-8 filename');}
    if(name.startsWith('/')||name.includes('\\')||name.split('/').some(p=>p===''||p==='.'||p==='..'))throw new Error(`tile ZIP path traversal: ${name}`);
    if(names.has(name)||offsets.has(localOffset))throw new Error(`duplicate tile ZIP central entry: ${name}`);names.add(name);offsets.add(localOffset);
    central.push({name,flags,method,crc,cs,size,localOffset});o+=length;
  }
  if(o!==eocd)throw new Error('invalid tile ZIP central size/count');
  const files=new Map(), ranges=[];let total=0;
  for(const c of central) {
    o=c.localOffset;if(!safe(o,30,centralOffset)||v.getUint32(o,true)!==0x04034b50)throw new Error(`invalid tile ZIP local offset: ${c.name}`);
    const flags=v.getUint16(o+6,true),method=v.getUint16(o+8,true),crc=v.getUint32(o+14,true),cs=v.getUint32(o+18,true),size=v.getUint32(o+22,true),nl=v.getUint16(o+26,true),xl=v.getUint16(o+28,true),ns=o+30,ds=ns+nl+xl,de=ds+size;
    if(!nl||xl||flags!==c.flags||method!==c.method||crc!==c.crc||cs!==c.cs||size!==c.size||cs!==size||!safe(o,30+nl+xl+size,centralOffset))throw new Error(`tile ZIP central/local mismatch: ${c.name}`);
    let localName;try{localName=dec.decode(bytes.subarray(ns,ns+nl));}catch(_){throw new Error('invalid tile ZIP UTF-8 filename');}
    if(localName!==c.name)throw new Error(`tile ZIP central/local name mismatch: ${c.name}`);
    total+=size;if(!Number.isSafeInteger(total)||total>TILE_EXPORT_LIMITS.maxPayloadBytes)throw new Error('tile ZIP payload budget');
    const data=bytes.slice(ds,de);if(crc32Bytes(data)!==crc)throw new Error(`tile ZIP CRC mismatch: ${c.name}`);files.set(c.name,data);ranges.push([o,de]);
  }
  ranges.sort((a,b)=>a[0]-b[0]);let end=0;for(const range of ranges){if(range[0]!==end)throw new Error('tile ZIP local entries overlap, are missing, or are out of bounds');end=range[1];}if(end!==centralOffset)throw new Error('tile ZIP local/central boundary mismatch');
  return files;
}
function parseTileExportPackage(zipBytes) {const files=parseTileStoredZip(zipBytes),dec=new TextDecoder();if(!files.has('manifest.json'))throw new Error('tile manifest missing');let m;try{m=JSON.parse(dec.decode(files.get('manifest.json')));}catch(_){throw new Error('invalid tile manifest JSON');}if(m.schema_version!=='asset-studio.tile-package/v1'||m.family!=='tile')throw new Error('invalid tile manifest schema/version/family');if(!Array.isArray(m.inventory)||!Array.isArray(m.tiles))throw new Error('invalid tile manifest inventory/grid');const declared=new Set(['manifest.json',...m.inventory.map(x=>x.path)]);if(declared.size!==files.size||[...files.keys()].some(x=>!declared.has(x)))throw new Error('tile file inventory mismatch');for(const x of m.inventory){const d=files.get(x.path);if(!d||d.length!==x.bytes||crc32Bytes(d).toString(16).padStart(8,'0')!==x.crc32||tileSha256(d)!==x.sha256)throw new Error(`tile inventory checksum mismatch: ${x.path}`);}const g=m.grid,count=g.rows*g.columns;if(!Number.isSafeInteger(count)||count!==m.tiles.length||count>TILE_EXPORT_LIMITS.maxCells)throw new Error('tile grid count mismatch');const atlas=decodeEffectFramePng(files.get(m.atlas.path),{maxPixels:TILE_EXPORT_LIMITS.maxSourcePixels});if(atlas.width!==m.atlas.width||atlas.height!==m.atlas.height)throw new Error('tile atlas PNG dimensions mismatch');const reconstructed=new Uint8ClampedArray(atlas.data.length);let compared=0;for(let i=0;i<count;i++){const t=m.tiles[i],row=Math.floor(i/g.columns),column=i%g.columns,x=g.margin+column*(g.tile_width+g.spacing),y=g.margin+row*(g.tile_height+g.spacing);if(t.index!==i||t.row!==row||t.column!==column||t.x!==x||t.y!==y||t.w!==g.tile_width||t.h!==g.tile_height)throw new Error('tile geometry mismatch');const p=decodeEffectFramePng(files.get(t.path));if(p.width!==t.w||p.height!==t.h)throw new Error('tile PNG dimensions mismatch');for(let yy=0;yy<t.h;yy++){const target=((t.y+yy)*atlas.width+t.x)*4,source=yy*t.w*4;reconstructed.set(p.data.subarray(source,source+t.w*4),target);for(let z=0;z<t.w*4;z++)if(p.data[source+z]!==atlas.data[target+z])throw new Error(`tile RGBA round-trip mismatch: ${t.path}`);}compared++;}const terrain=JSON.parse(dec.decode(files.get(m.artifacts.terrain_mapping))),engine=JSON.parse(dec.decode(files.get(m.artifacts.engine_metadata)));if(tileJson(terrain)!==tileJson({schema_version:'asset-studio.tile-terrain/v1',topology:m.contract.topology??null,inner_corners:!!m.contract.inner_corners,outer_corners:!!m.contract.outer_corners,transitions:m.contract.transitions||[],terrain_types:m.contract.terrain_types||[],variants:m.contract.variants||[],mapping:{order:'row-major',tile_count:count,coverage:'declared-only',engine_rule_counts:null}}))throw new Error('tile terrain artifact inconsistent');const expectedEngine={collision:m.contract.metadata?.collision||{},occlusion:m.contract.metadata?.occlusion||{},navigation:m.contract.metadata?.navigation||{},custom:m.contract.metadata?.custom||{}};if(engine.schema_version!=='asset-studio.tile-engine-metadata/v1'||engine.tile_index_validation.tile_count!==count||tileJson(expectedEngine)!==tileJson({collision:engine.collision,occlusion:engine.occlusion,navigation:engine.navigation,custom:engine.custom}))throw new Error('tile engine metadata/index validation mismatch');if(m.artifacts.tsx){const x=dec.decode(files.get(m.artifacts.tsx));for(const token of [`tilewidth="${g.tile_width}"`,`tileheight="${g.tile_height}"`,`tilecount="${count}"`,`columns="${g.columns}"`,`margin="${g.margin}"`,`spacing="${g.spacing}"`,`source="atlas.png"`,`width="${atlas.width}"`,`height="${atlas.height}"`])if(!x.includes(token))throw new Error('tile TSX consistency mismatch');const map=dec.decode(files.get(m.artifacts.tmx));if(!map.includes(`width="${g.columns}" height="${g.rows}"`)||!map.includes(Array.from({length:count},(_,i)=>i+1).join(',')))throw new Error('tile TMX consistency mismatch');}return {manifest:m,atlas,tilesCompared:compared,reconstructed,terrainMapping:terrain,engineMetadata:engine,verified:true};}

// F1 actor production is deliberately schema-isolated from generic sprite/effect packages.
const ACTOR_EXPORT_LIMITS=Object.freeze({maxFrames:512,maxPixels:16777216,maxWorkingBytes:201326592,maxArchiveBytes:67108864,maxDimension:4096,maxGap:1024});
function normalizeActorProductionContract(raw){
  const fail=m=>{throw new Error(`actor contract: ${m}`)}, pos=(v,n)=>{v=Number(v);if(!Number.isSafeInteger(v)||v<1)fail(`${n} invalid`);return v}, point=(p,n)=>{if(!p||!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x<0||p.x>1||p.y<0||p.y>1)fail(`${n} must be normalized`);return{x:p.x,y:p.y}};
  if(!raw||!['character','monster','npc'].includes(raw.subtype))fail('subtype unsupported');const mode=raw.directions?.mode,canonical=mode==='1dir'?[raw.directions?.requested?.[0]||'S']:mode==='4dir'?['S','W','E','N']:mode==='8dir'?['N','NE','E','SE','S','SW','W','NW']:null;if(!canonical)fail('direction mode must be 1dir/4dir/8dir');
  const requested=[...(raw.directions.requested||[])],order=[...(raw.directions.row_order||[])];if(JSON.stringify(order)!==JSON.stringify(canonical)||requested.some(x=>!canonical.includes(x))||new Set(requested).size!==requested.length)fail('direction row/request order invalid');if(!requested.length)fail('requested directions empty');
  if(!Array.isArray(raw.actions)||!raw.actions.length)fail('actions required');const ids=new Set(),actions=raw.actions.map((a,i)=>{if(!/^[a-z0-9_-]{1,48}$/i.test(a.id)||ids.has(a.id))fail(`action ${i} ID invalid/duplicate`);ids.add(a.id);const frame_count=pos(a.frame_count,'frame_count'),fps=Number(a.fps);if(!Number.isFinite(fps)||fps<=0||fps>120)fail('fps invalid');if(!Array.isArray(a.beats)||a.beats.length!==frame_count)fail('beat count mismatch');return{id:a.id,frame_count,fps,frame_duration_ms:1000/fps,loop:!!a.loop,beats:a.beats.map(String)}});
  const width=pos(raw.grid?.cell?.width,'cell width'),height=pos(raw.grid?.cell?.height,'cell height'),gap=Number(raw.grid?.gap??0);if(!Number.isSafeInteger(gap)||gap<0||gap>ACTOR_EXPORT_LIMITS.maxGap)fail('gap invalid/too large');if(width>ACTOR_EXPORT_LIMITS.maxDimension||height>ACTOR_EXPORT_LIMITS.maxDimension)fail('cell dimensions too large');const sourceSize={width:pos(raw.sourceSize?.width,'source width'),height:pos(raw.sourceSize?.height,'source height')};if(sourceSize.width!==width||sourceSize.height!==height)fail('common canvas/state size mismatch');
  return{subtype:raw.subtype,directions:{mode,requested,row_order:order},actions,grid:{cell:{width,height},gap},sourceSize,anchors:{pivot:point(raw.anchors?.pivot,'pivot'),root:point(raw.anchors?.root,'root'),contact:point(raw.anchors?.contact,'contact')}};
}
function actorArtifactDigest(frames,raw){
  const c=normalizeActorProductionContract(raw),enc=new TextEncoder(),parts=[enc.encode('asset-studio.actor-approval/sha256-v1\0'),enc.encode(tileJson(c))];
  if(!Array.isArray(frames))throw new Error('actor approval digest: frames required');
  for(const f of frames){const data=f?.imageData?.data;if(!data||typeof data.length!=='number')throw new Error('actor approval digest: invalid RGBA');parts.push(enc.encode(tileJson({direction:f.direction,action:f.action,index:f.index,beatId:f.beatId,width:f.imageData.width,height:f.imageData.height,root:f.root??null,contact:f.contact??null,mirrorProvenance:f.mirrorProvenance??null,rgba_bytes:data.length})),new Uint8Array(data.buffer,data.byteOffset,data.byteLength));}
  return tileSha256(effectConcatBytes(parts));
}
function validateActorVisualApproval(approval,digest){
  if(!approval||approval.status!=='APPROVED')return null;const text=(v,max)=>typeof v==='string'&&v.trim().length>0&&v.length<=max;
  const canonicalTimestamp=v=>{if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(v))return false;const ms=Date.parse(v);return Number.isFinite(ms)&&new Date(ms).toISOString()===v};
  if(!text(approval.reviewer,128)||!text(approval.source,128)||!canonicalTimestamp(approval.timestamp))return null;
  if(approval.evidence_id!==undefined&&!text(approval.evidence_id,256))return null;
  if(typeof approval.artifact_digest!=='string'||!/^[0-9a-f]{64}$/.test(approval.artifact_digest))return null;
  return approval.artifact_digest===digest?{status:'APPROVED',reviewer:approval.reviewer.trim(),source:approval.source.trim(),timestamp:approval.timestamp,artifact_digest:digest,...(approval.evidence_id===undefined?{}:{evidence_id:approval.evidence_id.trim()})}:false;
}
function evaluateActorProductionQA(frames,raw,visualApproval=null){
  let c;try{c=normalizeActorProductionContract(raw)}catch(e){return{status:'FAIL',deterministic_status:'FAIL',reasons:[{code:'CONTRACT',severity:'FAIL',message:e.message}],evidence:{motion_read:{status:'UNAVAILABLE'},visual_review:{status:'NOT_REVIEWED'}}}}const reasons=[],expected=c.directions.requested.reduce((n)=>n+c.actions.reduce((s,a)=>s+a.frame_count,0),0),fail=(code,message)=>reasons.push({code,severity:'FAIL',message}),metrics={sequences:[]};
  if(!Array.isArray(frames)||frames.length!==expected)fail('GRID_FRAME_COUNT',`expected ${expected} frames; received ${frames?.length??0}`);const map=new Map();for(const f of frames||[]){const k=`${f.direction}/${f.action}/${f.index}`;if(map.has(k))fail('FRAME_ORDER',`duplicate ${k}`);map.set(k,f)}
  for(const d of c.directions.requested)for(const a of c.actions){const seq=[];for(let i=0;i<a.frame_count;i++){const f=map.get(`${d}/${a.id}/${i}`);if(!f){if(frames?.length===expected)fail('FRAME_ORDER',`missing ${d}/${a.id}/${i}`);continue}if(f.beatId!==a.beats[i])fail('BEAT_ORDER',`${d}/${a.id}/${i} beat mismatch`);if(f.imageData?.width!==c.sourceSize.width||f.imageData?.height!==c.sourceSize.height)fail('COMMON_CANVAS',`${d}/${a.id}/${i} canvas mismatch`);const n=c.sourceSize.width*c.sourceSize.height*4,data=f.imageData?.data;if(!data||data.length!==n){fail('ALPHA_CONTAINMENT',`${d}/${a.id}/${i} RGBA size mismatch`);continue}let opaque=0,minX=c.sourceSize.width,minY=c.sourceSize.height,maxX=-1,maxY=-1,left=0,right=0;for(let p=0;p<n;p+=4)if(data[p+3]){const px=(p/4)%c.sourceSize.width,py=Math.floor(p/4/c.sourceSize.width);opaque++;minX=Math.min(minX,px);maxX=Math.max(maxX,px);minY=Math.min(minY,py);maxY=Math.max(maxY,py);if(py>=c.sourceSize.height*.55){if(px<c.sourceSize.width/2)left++;else right++;}}if(!opaque)fail('ALPHA_CONTAINMENT',`${d}/${a.id}/${i} has no contained alpha`);else if(minX===0||minY===0||maxX===c.sourceSize.width-1||maxY===c.sourceSize.height-1)fail('ALPHA_EDGE_CONTACT',`${d}/${a.id}/${i} alpha touches cell edge`);for(const key of ['root','contact']){const q=f[key]||c.anchors[key],base=c.anchors[key];if(!Number.isFinite(q.x)||!Number.isFinite(q.y)||Math.hypot(q.x-base.x,q.y-base.y)>.125)fail(`${key.toUpperCase()}_DRIFT`,`${d}/${a.id}/${i} ${key} drift`)}seq.push({data,opaque,bbox:[minX,minY,maxX,maxY],support:left-right})}
    if(seq.length===a.frame_count&&seq.length>1){const dif=(x,y,alpha)=>{let z=0,total=alpha?x.length/4:x.length;for(let p=0;p<x.length;p+=alpha?4:1)if(alpha?(x[p+3]!==y[p+3]):(x[p]!==y[p]))z++;return z/total},adj=[];for(let i=0;i<seq.length;i++)adj.push({alpha:dif(seq[i].data,seq[(i+1)%seq.length].data,true),rgba:dif(seq[i].data,seq[(i+1)%seq.length].data,false)});if(adj.every(x=>x.alpha===0))fail(adj.some(x=>x.rgba>0)?'COLOR_ONLY_MOTION':'IDENTICAL_FRAMES',`${d}/${a.id} has no silhouette motion`);if(a.id!=='walk'){const profiles={idle:[.002,2,.15],attack:[.012,3,.35],jump:[.01,3,.3],cast:[.008,3,.25],hurt:[.008,3,.25],death:[.015,4,.4],wave:[.008,3,.25]},p=profiles[a.id]||[.006,3,.2],area=c.sourceSize.width*c.sourceSize.height,maxAlpha=Math.max(...adj.map(x=>x.alpha)),maxRgba=Math.max(...adj.map(x=>x.rgba)),centers=seq.map(x=>[(x.bbox[0]+x.bbox[2])/2,(x.bbox[1]+x.bbox[3])/2]),disp=Math.max(...centers.map((x,i)=>Math.hypot(x[0]-centers[(i+1)%centers.length][0],x[1]-centers[(i+1)%centers.length][1])));if(maxAlpha*area<Math.max(p[1],Math.ceil(area*p[0]))||maxRgba*area*4<8&&disp<p[2])fail('MOTION_TOO_SMALL',`${d}/${a.id} motion is below the action-specific meaningful threshold`)}if(a.id==='walk'&&a.frame_count===4){const neutral=dif(seq[0].data,seq[2].data,true);if(neutral>.02)fail('LOOP_NEUTRAL_MISMATCH',`${d}/${a.id} neutral recurrence mismatch`);if(Math.sign(seq[1].support)===Math.sign(seq[3].support)||!seq[1].support||!seq[3].support)fail('SUPPORT_ALTERNATION',`${d}/${a.id} opposite support evidence missing`)}if(a.loop&&adj[adj.length-1].alpha>Math.max(.45,...adj.slice(0,-1).map(x=>x.alpha*3)))fail('LOOP_TRANSITION',`${d}/${a.id} closing transition discontinuity`);metrics.sequences.push({direction:d,action:a.id,occupancy:seq.map(x=>x.opaque/(c.sourceSize.width*c.sourceSize.height)),bboxes:seq.map(x=>x.bbox),support_balance:seq.map(x=>x.support),transitions:adj})}}
  const uniq=[];for(const r of reasons)if(!uniq.some(x=>x.code===r.code&&x.message===r.message))uniq.push(r);const deterministic_status=uniq.some(x=>x.severity==='FAIL')?'FAIL':'PASS',digest=actorArtifactDigest(frames,c),validated=validateActorVisualApproval(visualApproval,digest),stale=validated===false,approved=!!validated,visualStatus=visualApproval?.status==='FAIL'?'FAIL':approved?'APPROVED':stale?'STALE':'NOT_REVIEWED';if(!approved)uniq.push({code:visualStatus==='FAIL'?'VISUAL_REVIEW_FAILED':stale?'VISUAL_APPROVAL_STALE':'VISUAL_APPROVAL_REQUIRED',severity:'FAIL',message:visualStatus==='FAIL'?'explicit visual review failed':stale?'visual approval does not match the current artifact':'explicit visual approval required'});return{status:deterministic_status==='PASS'&&approved?'PASS':'FAIL',deterministic_status,reasons:uniq,evidence:{motion_read:{status:deterministic_status==='PASS'?'MEASURED_PASS':'MEASURED_FAIL',metrics},visual_review:{status:visualStatus,approval:validated||null}}};
}
function buildActorExportPackage(frames,raw,visualApproval=null){
  const c=normalizeActorProductionContract(raw),count=c.directions.requested.length*c.actions.reduce((n,a)=>n+a.frame_count,0),pixels=c.sourceSize.width*c.sourceSize.height,columns=Math.max(...c.actions.map(a=>a.frame_count)),rows=c.directions.requested.length*c.actions.length,gap=c.grid.gap,W=columns*c.sourceSize.width+(columns-1)*gap,H=rows*c.sourceSize.height+(rows-1)*gap;if(!Number.isSafeInteger(W)||!Number.isSafeInteger(H)||W>ACTOR_EXPORT_LIMITS.maxDimension||H>ACTOR_EXPORT_LIMITS.maxDimension||count>ACTOR_EXPORT_LIMITS.maxFrames||pixels*count>ACTOR_EXPORT_LIMITS.maxPixels||pixels*count*12>ACTOR_EXPORT_LIMITS.maxWorkingBytes)throw new Error('actor export memory/frame/atlas budget exceeded');const qa=evaluateActorProductionQA(frames,c,visualApproval);if(qa.status!=='PASS'){const e=new Error('actor export blocked by hard QA and explicit visual approval');e.qa=qa;throw e}const enc=new TextEncoder(),payload=[],mapping=[],atlas=new Uint8ClampedArray(W*H*4),lookup=new Map(frames.map(f=>[`${f.direction}/${f.action}/${f.index}`,f]));let row=0;
  for(const d of c.directions.requested)for(const a of c.actions){for(let i=0;i<a.frame_count;i++){const f=lookup.get(`${d}/${a.id}/${i}`),x=i*(c.sourceSize.width+gap),y=row*(c.sourceSize.height+gap),path=`frames/${d}/${a.id}-${String(i).padStart(3,'0')}.png`;for(let yy=0;yy<c.sourceSize.height;yy++)atlas.set(f.imageData.data.subarray(yy*c.sourceSize.width*4,(yy+1)*c.sourceSize.width*4),((y+yy)*W+x)*4);payload.push({name:path,bytes:encodeEffectFramePng(c.sourceSize.width,c.sourceSize.height,f.imageData.data)});mapping.push({direction:d,action:a.id,index:i,beat_id:f.beatId,path,atlas:{row,column:i,x,y,w:c.sourceSize.width,h:c.sourceSize.height},pivot:c.anchors.pivot,root:f.root||c.anchors.root,contact:f.contact||c.anchors.contact,mirror_provenance:f.mirrorProvenance||null})}row++}payload.unshift({name:'atlas.png',bytes:encodeEffectFramePng(W,H,atlas)});
  const inventory=payload.map(f=>({path:f.name,bytes:f.bytes.length,crc32:crc32Bytes(f.bytes).toString(16).padStart(8,'0'),sha256:tileSha256(f.bytes)})),manifest={schema_version:'asset-studio.actor-package/v1',family:'actor',subtype:c.subtype,requested_directions:c.directions.requested,actual_directions:[...new Set(mapping.map(x=>x.direction))],directions:c.directions,actions:c.actions,grid:{rows,columns,cell:c.grid.cell,gap},sourceSize:c.sourceSize,anchors:c.anchors,frames:mapping,atlas:{path:'atlas.png',width:W,height:H},qa,inventory_policy:'payload-files-only; manifest.json excluded to avoid self-reference',inventory},files=[{name:'manifest.json',bytes:enc.encode(tileJson(manifest))},...payload];if(files.reduce((n,f)=>n+f.bytes.length,0)>ACTOR_EXPORT_LIMITS.maxArchiveBytes)throw new Error('actor export archive budget exceeded');const zipBytes=tileZipBytes(files);return{manifest,files,zipBytes,zipBlob:new Blob([zipBytes],{type:'application/zip'}),zipName:'actor-package.zip'};
}
function renderActorProductionFrame(){if(typeof window==='undefined')return;const art=window.__actorProductionArtifact,cv=$('actorPreviewCanvas');if(!art||!cv)return;const d=$('actorDirectionSelect').value,a=$('actorActionSelect').value,list=art.frames.filter(f=>f.direction===d&&f.action===a);if(!list.length)return;const f=list[Math.floor(Date.now()/(1000/(art.contract.actions.find(x=>x.id===a)?.fps||8)))%list.length],ctx=cv.getContext('2d'),tmp=document.createElement('canvas');tmp.width=f.imageData.width;tmp.height=f.imageData.height;tmp.getContext('2d').putImageData(new ImageData(f.imageData.data,f.imageData.width,f.imageData.height),0,0);ctx.clearRect(0,0,cv.width,cv.height);ctx.imageSmoothingEnabled=false;ctx.drawImage(tmp,0,0,cv.width,cv.height);const p=art.contract.anchors.pivot,r=f.root||art.contract.anchors.root,k=f.contact||art.contract.anchors.contact;ctx.lineWidth=2;ctx.strokeStyle='#ff4d67';ctx.beginPath();ctx.moveTo(p.x*cv.width-7,p.y*cv.height);ctx.lineTo(p.x*cv.width+7,p.y*cv.height);ctx.moveTo(p.x*cv.width,p.y*cv.height-7);ctx.lineTo(p.x*cv.width,p.y*cv.height+7);ctx.stroke();ctx.strokeStyle='#49d6ff';ctx.beginPath();ctx.arc(r.x*cv.width,r.y*cv.height,6,0,Math.PI*2);ctx.stroke();ctx.strokeStyle='#6dff8a';ctx.beginPath();ctx.moveTo(0,k.y*cv.height);ctx.lineTo(cv.width,k.y*cv.height);ctx.stroke();window.__actorPreviewTimer=requestAnimationFrame(renderActorProductionFrame)}
function resetActorVisualApproval(message='시각 승인이 필요합니다'){if(typeof window==='undefined')return;window.__actorVisualApproval=null;const box=$('actorVisualApproval'),button=$('exportActorPackageZip');if(box)box.checked=false;if(button)button.disabled=true;if(message&&$('actorQaSummary'))$('actorQaSummary').textContent=message}
function buildActorSyntheticArtifact(){const directions=['S','W','E','N'],beats=['contact','down','passing','up'],contract={subtype:'character',directions:{mode:'4dir',requested:directions,row_order:directions},actions:[{id:'walk',frame_count:4,fps:8,loop:true,beats}],grid:{cell:{width:16,height:16},gap:0},sourceSize:{width:16,height:16},anchors:{pivot:{x:.5,y:.75},root:{x:.5,y:.75},contact:{x:.5,y:.75}}},frames=[];for(let d=0;d<4;d++)for(let i=0;i<4;i++){const data=new Uint8ClampedArray(16*16*4),paint=(x,y)=>data.set([80+d*35,150,220,255],(y*16+x)*4);for(let y=3;y<10;y++)for(let x=6;x<10;x++)paint(x,y);if(i===0||i===2){for(let y=10;y<14;y++){paint(6,y);paint(9,y)}}else if(i===1){for(let y=10;y<14;y++){paint(5,y);paint(6,y)}for(let y=10;y<12;y++)paint(9,y)}else{for(let y=10;y<14;y++){paint(9,y);paint(10,y)}for(let y=10;y<12;y++)paint(6,y)}frames.push({direction:directions[d],action:'walk',index:i,beatId:beats[i],imageData:{width:16,height:16,data},root:contract.anchors.root,contact:contract.anchors.contact})}window.__actorProductionArtifact={contract,frames};resetActorVisualApproval('결정적 측정 완료 · 명시적 시각 승인이 필요합니다');const q=evaluateActorProductionQA(frames,contract);$('actorQaSummary').textContent=`deterministic ${q.deterministic_status} · visual ${q.evidence.visual_review.status}`;cancelAnimationFrame(window.__actorPreviewTimer);renderActorProductionFrame()}
if(typeof document!=='undefined'&&$('buildActorSyntheticPreview'))$('buildActorSyntheticPreview').onclick=buildActorSyntheticArtifact;
function actorFramesFromImageData(imageData,contract){const c=normalizeActorProductionContract(contract),out=[];let row=0;for(const d of c.directions.requested)for(const a of c.actions){for(let i=0;i<a.frame_count;i++){const data=new Uint8ClampedArray(c.sourceSize.width*c.sourceSize.height*4),x=i*(c.sourceSize.width+c.grid.gap),y=row*(c.sourceSize.height+c.grid.gap);for(let yy=0;yy<c.sourceSize.height;yy++)data.set(imageData.data.subarray(((y+yy)*imageData.width+x)*4,((y+yy)*imageData.width+x+c.sourceSize.width)*4),yy*c.sourceSize.width*4);out.push({direction:d,action:a.id,index:i,beatId:a.beats[i],imageData:{width:c.sourceSize.width,height:c.sourceSize.height,data},root:c.anchors.root,contact:c.anchors.contact})}row++}return out}
async function exportActorPackageZip(){const button=$('exportActorPackageZip');if(!button)return;button.disabled=true;try{if(!window.__actorProductionArtifact)throw new Error('Actor preview를 먼저 생성하세요');const result=buildActorExportPackage(window.__actorProductionArtifact.frames,window.__actorProductionArtifact.contract,window.__actorVisualApproval);downloadBlob(result.zipBlob,result.zipName);$('actorQaSummary').textContent=`${result.manifest.qa.status} · ${result.manifest.frames.length} actual frames`;}catch(e){if($('actorQaSummary'))$('actorQaSummary').textContent=e.message;throw e}finally{button.disabled=!window.__actorVisualApproval}}
if(typeof document!=='undefined'&&$('exportActorPackageZip'))$('exportActorPackageZip').onclick=()=>exportActorPackageZip().catch(()=>{});
if(typeof document!=='undefined'&&$('actorVisualApproval'))$('actorVisualApproval').onchange=e=>{const button=$('exportActorPackageZip');if(e.target.checked&&window.__actorProductionArtifact){const art=window.__actorProductionArtifact;window.__actorVisualApproval={status:'APPROVED',reviewer:'local-user',source:'manual-browser-review',timestamp:new Date().toISOString(),artifact_digest:actorArtifactDigest(art.frames,art.contract)};if(button)button.disabled=false;$('actorQaSummary').textContent='시각 승인 완료 · 프레임/계약 변경 시 초기화';}else resetActorVisualApproval()};
if(typeof document!=='undefined')for(const id of ['actorDirectionSelect','actorActionSelect'])$(id)?.addEventListener('change',()=>resetActorVisualApproval('방향/동작 변경 · 시각 승인이 초기화되었습니다'));
if(typeof window!=='undefined')window.__assetStudioDebug={...(window.__assetStudioDebug||{}),normalizeActorProductionContract,actorArtifactDigest,evaluateActorProductionQA,buildActorExportPackage,actorFramesFromImageData,normalizeStyleProfile,hydrateStyleProfileControls,validateProjectFamilyDrafts,serializeProjectFamilyDrafts,hydrateProjectFamilyDrafts,buildProjectV2,loadProjectV2};

const OBJECT_PREVIEW_BUDGETS = Object.freeze({maxDimension:16384,maxPixels:16777216,maxStates:128,maxPreviewPixels:4194304,maxStateIdLength:64,maxSnapPoints:128,maxPolygonPoints:64,maxLabelLength:256});
function normalizeObjectPreviewContract(contract) {
  const fail=s=>{throw new Error(`object preview contract: ${s}`);};
  if(!contract||typeof contract!=='object'||Array.isArray(contract))fail('object required');
  const finite=(v,n,positive=false)=>{if(!Number.isFinite(v)||(positive&&v<=0))fail(`${n} must be ${positive?'positive ':''}finite`);return v;};
  const normalized=(v,n)=>{finite(v,n);if(v<0||v>1)fail(`${n} must be normalized`);return v;};
  const point=(v,n,norm=true)=>{if(!v||typeof v!=='object'||Array.isArray(v))fail(`${n} point required`);return {x:(norm?normalized:finite)(v.x,`${n}.x`),y:(norm?normalized:finite)(v.y,`${n}.y`)};};
  const scale=contract.scale,placement=contract.placement,source=contract.source,collision=contract.collision,interaction=contract.interaction;if(!scale||!placement||!source||!collision||!interaction)fail('nested fields required');if(!source.canvas||!Number.isSafeInteger(source.canvas.width)||!Number.isSafeInteger(source.canvas.height)||source.canvas.width<1||source.canvas.height<1||source.canvas.width>OBJECT_PREVIEW_BUDGETS.maxDimension||source.canvas.height>OBJECT_PREVIEW_BUDGETS.maxDimension)fail('source.canvas dimensions invalid');
  const tile_relative={width:finite(scale.tile_relative?.width,'scale.tile_relative.width',true),height:finite(scale.tile_relative?.height,'scale.tile_relative.height',true)},footprint={width:finite(scale.footprint?.width,'scale.footprint.width',true),depth:finite(scale.footprint?.depth,'scale.footprint.depth',true)};finite(scale.character_relative,'scale.character_relative',true);
  const pivot=point(placement.pivot,'placement.pivot'),ground_point=point(placement.ground_point,'placement.ground_point'),y_sort_point=point(placement.y_sort_point,'placement.y_sort_point');if(!Array.isArray(placement.snap_points)||placement.snap_points.length>OBJECT_PREVIEW_BUDGETS.maxSnapPoints)fail('snap point count exceeded');
  const snap_points=placement.snap_points.map((q,i)=>{if(typeof q.id!=='string'||q.id.length>OBJECT_PREVIEW_BUDGETS.maxStateIdLength)fail(`snap_points.${i}.id invalid`);return {...point(q,`snap_points.${i}`),id:q.id};});if(!['box','polygon'].includes(collision.shape))fail('collision shape unsupported');const offset=point(collision.offset||{x:0,y:0},'collision.offset',false);let cleanCollision;
  if(collision.shape==='box')cleanCollision={shape:'box',offset,size:{width:finite(collision.size?.width,'collision.size.width',true),depth:finite(collision.size?.depth,'collision.size.depth',true)}};else{
    if(!Array.isArray(collision.points)||collision.points.length<3||collision.points.length>OBJECT_PREVIEW_BUDGETS.maxPolygonPoints)fail('polygon point count invalid');
    const points=collision.points.map((q,i)=>point(q,`collision.points.${i}`,false)),epsilon=1e-9,edgeCount=points.length;
    const cross=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
    const onSegment=(a,b,q)=>Math.abs(cross(a,b,q))<=epsilon&&q.x>=Math.min(a.x,b.x)-epsilon&&q.x<=Math.max(a.x,b.x)+epsilon&&q.y>=Math.min(a.y,b.y)-epsilon&&q.y<=Math.max(a.y,b.y)+epsilon;
    const intersects=(a,b,c,d)=>{const abC=cross(a,b,c),abD=cross(a,b,d),cdA=cross(c,d,a),cdB=cross(c,d,b);if(((abC>epsilon&&abD<-epsilon)||(abC<-epsilon&&abD>epsilon))&&((cdA>epsilon&&cdB<-epsilon)||(cdA<-epsilon&&cdB>epsilon)))return true;return onSegment(a,b,c)||onSegment(a,b,d)||onSegment(c,d,a)||onSegment(c,d,b);};
    let area=0;
    for(let i=0;i<edgeCount;i++){const a=points[i],b=points[(i+1)%edgeCount],dx=a.x-b.x,dy=a.y-b.y;if(dx*dx+dy*dy<=epsilon*epsilon)fail('polygon zero-length edge');area+=a.x*b.y-b.x*a.y;}
    if(Math.abs(area)<epsilon)fail('polygon degenerate');
    for(let i=0;i<edgeCount;i++)for(let j=i+1;j<edgeCount;j++){if(j===i+1||(i===0&&j===edgeCount-1))continue;if(intersects(points[i],points[(i+1)%edgeCount],points[j],points[(j+1)%edgeCount]))fail('polygon self-intersection');}
    cleanCollision={shape:'polygon',offset,points};
  }
  return {...contract,scale:{...scale,tile_relative,footprint},placement:{...placement,pivot,ground_point,y_sort_point,snap_points},collision:cleanCollision,interaction:{point:point(interaction.point,'interaction.point'),radius:finite(interaction.radius,'interaction.radius',true)}};
}
function validateObjectPreviewBudget(width,height,stateCount=1,previewWidth=512,previewHeight=384) {
  const fail=message=>{throw new Error(`object preview budget: ${message}`)};
  for(const [name,value] of Object.entries({width,height,stateCount,previewWidth,previewHeight}))if(!Number.isSafeInteger(value)||value<1)fail(`${name} must be a positive safe integer`);
  if(width>OBJECT_PREVIEW_BUDGETS.maxDimension||height>OBJECT_PREVIEW_BUDGETS.maxDimension)fail('source dimension exceeded');
  if(width>Math.floor(OBJECT_PREVIEW_BUDGETS.maxPixels/height))fail('source pixel allocation exceeded');
  if(stateCount>OBJECT_PREVIEW_BUDGETS.maxStates)fail('state allocation exceeded');
  if(previewWidth>Math.floor(OBJECT_PREVIEW_BUDGETS.maxPreviewPixels/previewHeight))fail('preview allocation exceeded');
  return {sourcePixels:width*height,stateCount,previewPixels:previewWidth*previewHeight};
}
function analyzeObjectPlacement(imageData,contract,states=[]) {
  const stateList=Array.isArray(states)?states:[];validateObjectPreviewBudget(imageData.width,imageData.height,Math.max(1,stateList.length));
  if(typeof normalizeObjectPreviewContract==='function')contract=normalizeObjectPreviewContract(contract);
  if(!contract||typeof contract!=='object'||!contract.scale||!contract.source||!contract.placement)throw new Error('object preview: nested object contract required');
  const reasons=[],fail=[],scale=contract.scale||{},place=contract.placement||{},eps=.001,footprint=scale.footprint||{},relative=scale.tile_relative||{};
  if(Math.abs(Number(footprint.width)-Number(relative.width))>eps)reasons.push('wrong-footprint');const ground=place.ground_point||{},pivot=place.pivot||{};
  if(Math.abs(Number(ground.y)-1)>eps)reasons.push('floating-ground');if(Math.abs(Number(pivot.x)-Number(ground.x))>eps||Math.abs(Number(pivot.y)-Number(ground.y))>eps)reasons.push('pivot-mismatch');
  const sourceCanvas=contract.source.canvas||{};if(stateList.some(state=>state.canvas&&(state.canvas.width!==sourceCanvas.width||state.canvas.height!==sourceCanvas.height)||state.pivot&&(Math.abs(state.pivot.x-pivot.x)>eps||Math.abs(state.pivot.y-pivot.y)>eps)))reasons.push('state-size-drift');
  const collision=contract.collision||{},offset=collision.offset||{},size=collision.size||{},collisionOut=collision.shape==='polygon'?(collision.points||[]).some(q=>Math.abs(q.x+offset.x)>footprint.width/2||Math.abs(q.y+offset.y)>footprint.depth/2):(Math.abs(Number(offset.x)||0)+(Number(size.width)||0)/2>footprint.width/2||Math.abs(Number(offset.y)||0)+(Number(size.depth)||0)/2>footprint.depth/2);if(collisionOut){reasons.push('collision-out-of-bounds');fail.push('collision-out-of-bounds');}
  const data=imageData.data,expected=imageData.width*imageData.height*4;if(!data||data.length!==expected)throw new Error('object preview: RGBA data size mismatch');let minX=imageData.width,minY=imageData.height,maxX=-1,maxY=-1,opaque=0;for(let y=0;y<imageData.height;y++)for(let x=0;x<imageData.width;x++)if(data[(y*imageData.width+x)*4+3]>0){opaque++;if(x<minX)minX=x;if(x>maxX)maxX=x;if(y<minY)minY=y;if(y>maxY)maxY=y;}
  if(!opaque){reasons.push('transparent-image');fail.push('transparent-image');}else if(maxY<Math.floor((ground.y||0)*imageData.height)-1&&!reasons.includes('floating-ground'))reasons.push('floating-ground');
  return {status:fail.length?'FAIL':reasons.length?'WARN':'PASS',reasons,metrics:{sourceWidth:imageData.width,sourceHeight:imageData.height,stateCount:stateList.length,opaquePixels:opaque,opaqueBounds:opaque?{minX,minY,maxX,maxY}:null}};
}
function buildObjectPlacementModel(imageData,contract,sourceMode='result',states=[],shadowMode='contract',usageMode='contract',iconMode='contain') {
  const qa=analyzeObjectPlacement(imageData,contract,states),usage=usageMode==='contract'?(contract.usage==='icon'?'icon':'world'):usageMode,tileSize=32;
  const width=usage==='world'?Number(contract.scale.tile_relative.width)*tileSize:96,height=usage==='world'?Number(contract.scale.tile_relative.height)*tileSize:96;
  const ground={x:256,y:288},pivot=contract.placement.pivot||{x:.5,y:1},effectiveShadow=contract.shadow?.baked?'none':(shadowMode==='contract'?(contract.shadow?.mode||'none'):shadowMode);
  return {sourceMode,usage,stateIds:(states||[]).map(s=>s.id),shadowMode:effectiveShadow,shadow:{mode:effectiveShadow,baked:Boolean(contract.shadow?.baked),suppressed:Boolean(contract.shadow?.baked)},grid:{tileSize,columns:8,rows:6},character:{height:tileSize*2,relativeScale:Number(contract.scale.character_relative),drawHeight:tileSize*2*Number(contract.scale.character_relative)},object:{widthTiles:Number(contract.scale.tile_relative.width),heightTiles:Number(contract.scale.tile_relative.height),drawWidth:width,drawHeight:height,ground,origin:{x:ground.x-pivot.x*width,y:ground.y-pivot.y*height}},icon:{mode:iconMode,frame:{x:192,y:112,width:128,height:128}},overlays:['pivot','ground','y-sort','snap','collision','interaction'],qa};
}
function renderObjectPlacement(ctx,image,model,contract) {
  const W=ctx.canvas.width,H=ctx.canvas.height,t=model.grid.tileSize,o=model.object,p=contract.placement||{};ctx.fillStyle='#18202d';ctx.fillRect(0,0,W,H);ctx.imageSmoothingEnabled=false;
  if(model.usage==='world'){ctx.strokeStyle='#344155';ctx.lineWidth=1;for(let x=0;x<=W;x+=t){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke()}for(let y=0;y<=H;y+=t){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke()}ctx.fillStyle='#8fa3bd';ctx.fillRect(56,o.ground.y-model.character.drawHeight,24,model.character.drawHeight)}
  if(model.shadowMode!=='none'){ctx.save();ctx.fillStyle=model.shadowMode==='contact'?'rgba(0,0,0,.55)':'rgba(0,0,0,.28)';ctx.filter=model.shadowMode==='soft'?'blur(7px)':'none';ctx.beginPath();ctx.ellipse(o.ground.x,o.ground.y+2,o.drawWidth*.38,Math.max(3,o.drawHeight*.08),0,0,Math.PI*2);ctx.fill();ctx.restore()}
  if(model.usage==='icon'){const f=model.icon.frame,sw=image.naturalWidth||image.width||contract.source.canvas.width,sh=image.naturalHeight||image.height||contract.source.canvas.height;if(model.icon.mode==='crop'){const side=Math.min(sw,sh);ctx.drawImage(image,(sw-side)/2,(sh-side)/2,side,side,f.x,f.y,f.width,f.height)}else{const s=model.icon.mode==='fit'?Math.min(f.width/sw,f.height/sh):Math.min(1,f.width/sw,f.height/sh),dw=sw*s,dh=sh*s;ctx.strokeStyle='#607089';ctx.strokeRect(f.x,f.y,f.width,f.height);ctx.drawImage(image,f.x+(f.width-dw)/2,f.y+(f.height-dh)/2,dw,dh)}}else ctx.drawImage(image,o.origin.x,o.origin.y,o.drawWidth,o.drawHeight);
  const point=(q,color,shape='arc')=>{if(!q)return;const x=o.origin.x+q.x*o.drawWidth,y=o.origin.y+q.y*o.drawHeight;ctx.strokeStyle=color;ctx.fillStyle=color;ctx.beginPath();if(shape==='rect')ctx.rect(x-4,y-4,8,8);else ctx.arc(x,y,shape==='small'?3:5,0,Math.PI*2);ctx.stroke()};
  point(p.pivot,'#ff4d6d');point(p.ground_point,'#4dff88','rect');point(p.y_sort_point,'#ffd84d','small');(p.snap_points||[]).forEach(q=>point(q,'#53c8ff','rect'));
  const c=contract.collision||{};ctx.save();ctx.strokeStyle='#ff8c42';ctx.setLineDash([6,3]);if(c.shape==='polygon'&&Array.isArray(c.points)){ctx.beginPath();c.points.forEach((q,i)=>{const x=o.ground.x+(q.x+(c.offset?.x||0))*t,y=o.ground.y+(q.y+(c.offset?.y||0))*t;i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.closePath();ctx.stroke()}else{const s=c.size||{},off=c.offset||{};ctx.strokeRect(o.ground.x+(off.x-(s.width||0)/2)*t,o.ground.y+(off.y-(s.depth||0)/2)*t,(s.width||0)*t,(s.depth||0)*t)}ctx.restore();
  const interaction=contract.interaction||{};if(interaction.point){const x=o.origin.x+interaction.point.x*o.drawWidth,y=o.origin.y+interaction.point.y*o.drawHeight;ctx.strokeStyle='#bd70ff';ctx.beginPath();ctx.arc(x,y,Number(interaction.radius||0)*t,0,Math.PI*2);ctx.stroke();point(interaction.point,'#bd70ff','small')}
}
function buildObjectPlacementPreview() {
  const object=canvas.getActiveObject(),source=object?._element;if(!source)throw new Error('Object preview requires a selected image');
  const metadata=object.objectFamilyMetadata,contract=normalizeObjectPreviewContract(metadata?.family_contract);if(metadata?.asset_family!=='object')throw new Error('Selected image has no nested Object family_contract metadata');
  const sourceMode=$('objectPreviewSource').value,resultStates=metadata?.object_result?.states||[],requested=contract.states||metadata?.object_source?.states||[];if(!Array.isArray(resultStates)||!Array.isArray(requested)||resultStates.length>OBJECT_PREVIEW_BUDGETS.maxStates||requested.length>OBJECT_PREVIEW_BUDGETS.maxStates)throw new Error('object preview budget: state allocation exceeded');for(const item of resultStates){if(!item||typeof item.id!=='string'||item.id.length>OBJECT_PREVIEW_BUDGETS.maxStateIdLength)throw new Error('object preview budget: result state ID invalid');}
  const selector=$('objectPreviewState'),selected=selector.value,state=resultStates.find(s=>s.id===selected),display=sourceMode==='source'?(metadata.object_source?.image||source):(state?.image||metadata.object_result?.image||source),W=display.naturalWidth||display.width,H=display.naturalHeight||display.height;
  validateObjectPreviewBudget(W,H,Math.max(1,resultStates.length));const options=[{id:'base',label:'base'}];for(const item of requested){const id=typeof item==='string'?item:item?.id;if(typeof id!=='string'||id.length>OBJECT_PREVIEW_BUDGETS.maxStateIdLength)throw new Error('object preview budget: state ID invalid');const label=`${id} ${resultStates.some(r=>r.id===id)?'':'(requested-only)'}`;if(label.length>OBJECT_PREVIEW_BUDGETS.maxLabelLength)throw new Error('object preview budget: label exceeded');options.push({id,label});}
  selector.replaceChildren();for(const s of options){const option=document.createElement('option');option.value=s.id;option.textContent=s.label;selector.appendChild(option);}selector.value=options.some(s=>s.id===selected)?selected:'base';
  const input=document.createElement('canvas');input.width=W;input.height=H;const ix=input.getContext('2d',{willReadFrequently:true});ix.drawImage(display,0,0,W,H);const imageData=ix.getImageData(0,0,W,H),model=buildObjectPlacementModel(imageData,contract,sourceMode,resultStates,$('objectPreviewShadow').value,$('objectPreviewUsage').value,$('objectPreviewIconMode').value),out=$('objectPlacementPreviewCanvas');out.width=512;out.height=384;renderObjectPlacement(out.getContext('2d'),display,model,contract);
  const summary=$('objectPlacementQaSummary');summary.dataset.status=model.qa.status;summary.textContent=`${model.qa.status} · ${model.qa.reasons.join(', ')||'placement valid'} · ${selector.options[selector.selectedIndex]?.textContent}`;return model;
}

const OBJECT_EXPORT_LIMITS=Object.freeze({maxDimension:8192,maxPixels:16777216,maxStates:128,maxFiles:140,maxPayloadBytes:134217728,maxWorkingBytes:268435456,maxIconPixels:1048576,maxContractDepth:24,maxContractNodes:10000,maxContractKeys:10000,maxStringBytes:262144,maxManifestBytes:1048576});
function objectExportStatePath(id,used=new Set()){if(typeof id!=='string'||id.length<1||id.length>64||!/^[a-z0-9][a-z0-9_-]*$/.test(id)||id==='manifest')throw new Error(`object export state path traversal/unsafe ID: ${String(id)}`);const key=id.toLowerCase();if(used.has(key))throw new Error(`duplicate object state ID/path: ${id}`);used.add(key);return `states/${id}.png`;}
function auditObjectExportContract(value){const fail=s=>{throw new Error(`object export budget: contract ${s}`)},enc=new TextEncoder(),stack=[{value,depth:0}],seen=new Set();let nodes=0,keys=0,stringBytes=0;while(stack.length){const item=stack.pop(),v=item.value;if(++nodes>OBJECT_EXPORT_LIMITS.maxContractNodes)fail('node complexity exceeded');if(item.depth>OBJECT_EXPORT_LIMITS.maxContractDepth)fail('depth complexity exceeded');if(typeof v==='string'){stringBytes+=enc.encode(v).length;if(stringBytes>OBJECT_EXPORT_LIMITS.maxStringBytes)fail('UTF8 string bytes exceeded');continue;}if(!v||typeof v!=='object')continue;if(seen.has(v))fail('cycle complexity exceeded');seen.add(v);const names=Object.keys(v);keys+=names.length;if(keys>OBJECT_EXPORT_LIMITS.maxContractKeys)fail('key complexity exceeded');for(const k of names){stringBytes+=enc.encode(k).length;if(stringBytes>OBJECT_EXPORT_LIMITS.maxStringBytes)fail('UTF8 key/string bytes exceeded');stack.push({value:v[k],depth:item.depth+1});}}let serialized;try{serialized=enc.encode(JSON.stringify(value)).length;}catch(_){fail('serialization invalid');}if(!Number.isSafeInteger(serialized)||serialized>OBJECT_EXPORT_LIMITS.maxManifestBytes)fail('serialized byte complexity exceeded');return serialized;}
function checkObjectExportBudget(imageData,rawContract,options={}){const fail=s=>{throw new Error(`object export budget: ${s}`)},W=imageData?.width,H=imageData?.height;if(!Number.isSafeInteger(W)||!Number.isSafeInteger(H)||W<1||H<1||W>OBJECT_EXPORT_LIMITS.maxDimension||H>OBJECT_EXPORT_LIMITS.maxDimension)fail('source geometry/dimension exceeded');const contractBytes=auditObjectExportContract(rawContract),pixels=W*H,states=Array.isArray(options.states)?options.states:[],iw=options.icon?.width??64,ih=options.icon?.height??64;if(!Number.isSafeInteger(pixels)||pixels>OBJECT_EXPORT_LIMITS.maxPixels)fail('source pixels exceeded');if(states.length+1>OBJECT_EXPORT_LIMITS.maxStates)fail('state count exceeded');const used=new Set(['base']);for(const state of states){if(!state||typeof state!=='object')fail('result descriptor invalid');objectExportStatePath(state.id,used);if(!state.imageData||state.imageData.width!==W||state.imageData.height!==H)fail('result descriptor geometry invalid');}if(!Number.isSafeInteger(iw)||!Number.isSafeInteger(ih)||iw<1||ih<1||!Number.isSafeInteger(iw*ih)||iw*ih>OBJECT_EXPORT_LIMITS.maxIconPixels)fail('icon geometry exceeded');const files=4+states.length+(options.shadow?.imageData?1:0),manifestEstimate=contractBytes+4096+states.length*512,work=(pixels*(states.length+3)+iw*ih)*8+manifestEstimate,archive=(pixels*(states.length+2)+iw*ih)*5+65536+manifestEstimate;if(files>OBJECT_EXPORT_LIMITS.maxFiles)fail('file count exceeded');if(!Number.isSafeInteger(manifestEstimate)||manifestEstimate>OBJECT_EXPORT_LIMITS.maxManifestBytes)fail('estimated manifest bytes exceeded');if(!Number.isSafeInteger(work)||work>OBJECT_EXPORT_LIMITS.maxWorkingBytes)fail('working bytes exceeded');if(!Number.isSafeInteger(archive)||archive>OBJECT_EXPORT_LIMITS.maxPayloadBytes)fail('archive bytes exceeded');return {W,H,pixels,states,iw,ih,files,work,archive,manifestEstimate};}
function objectNearestDerivative(imageData,width,height,mode='contain'){if(!['contain','fit','crop'].includes(mode))throw new Error('object icon recipe mode invalid');const sw=imageData.width,sh=imageData.height,out=new Uint8ClampedArray(width*height*4);let sx0=0,sy0=0,sxSpan=sw,sySpan=sh,dx0=0,dy0=0,dw=width,dh=height;if(mode==='crop'){const scale=Math.max(width/sw,height/sh);sxSpan=width/scale;sySpan=height/scale;sx0=(sw-sxSpan)/2;sy0=(sh-sySpan)/2;}else{let scale=Math.min(width/sw,height/sh);if(mode==='contain')scale=Math.min(1,scale);dw=Math.max(1,Math.round(sw*scale));dh=Math.max(1,Math.round(sh*scale));dx0=Math.floor((width-dw)/2);dy0=Math.floor((height-dh)/2);}for(let y=0;y<dh;y++)for(let x=0;x<dw;x++){const sx=Math.min(sw-1,Math.floor(sx0+(x+.5)*sxSpan/dw)),sy=Math.min(sh-1,Math.floor(sy0+(y+.5)*sySpan/dh)),si=(sy*sw+sx)*4,di=((dy0+y)*width+dx0+x)*4;out.set(imageData.data.subarray(si,si+4),di);}return {width,height,data:out};}
function buildObjectExportPackage(imageData,rawContract,options={}){
  const budget=checkObjectExportBudget(imageData,rawContract,options),contract=normalizeObjectPreviewContract(rawContract),actual=[{id:'base',imageData},...(options.states||[])],used=new Set(),seen=new Set();for(const state of actual){if(!state||!state.imageData)throw new Error('object state RGBA source required');if(seen.has(state.id))throw new Error(`duplicate object state ID/path: ${state.id}`);seen.add(state.id);objectExportStatePath(state.id,used);if(state.imageData.width!==budget.W||state.imageData.height!==budget.H)throw new Error('object state common canvas/sourceSize drift');}
  const requested=(contract.states||[]).map(x=>typeof x==='string'?x:x?.id),requestedUsed=new Set();for(const id of requested)objectExportStatePath(id,requestedUsed);const requestedOnly=requested.filter(id=>!seen.has(id)),rgbaSize=budget.pixels*4;for(const state of actual)if(!state.imageData.data||state.imageData.data.length!==rgbaSize)throw new Error(`object state RGBA size mismatch: ${state.id}`);const shadowData=!contract.shadow?.baked?options.shadow?.imageData:null;if(shadowData&&(shadowData.width!==budget.W||shadowData.height!==budget.H||shadowData.data?.length!==rgbaSize))throw new Error('object separate shadow sourceSize/RGBA mismatch');
  const enc=new TextEncoder(),payload=[],states=actual.map((state,index)=>{const path=`states/${state.id}.png`;payload.push({name:path,bytes:encodeEffectFramePng(budget.W,budget.H,state.imageData.data)});return {id:state.id,order:index,path,width:budget.W,height:budget.H,pivot:{...contract.placement.pivot},ground_point:{...contract.placement.ground_point},y_sort_point:{...contract.placement.y_sort_point}};}),atlasData=new Uint8ClampedArray(budget.W*actual.length*budget.H*4);for(let y=0;y<budget.H;y++)actual.forEach((s,i)=>atlasData.set(s.imageData.data.subarray(y*budget.W*4,(y+1)*budget.W*4),(y*budget.W*actual.length+i*budget.W)*4));payload.push({name:'atlas.png',bytes:encodeEffectFramePng(budget.W*actual.length,budget.H,atlasData)});const iconMode=options.icon?.mode||'contain',icon=objectNearestDerivative(imageData,budget.iw,budget.ih,iconMode);payload.push({name:'inventory/icon.png',bytes:encodeEffectFramePng(icon.width,icon.height,icon.data)});let shadowPath=null;if(shadowData){shadowPath='shadow/separate.png';payload.push({name:shadowPath,bytes:encodeEffectFramePng(budget.W,budget.H,shadowData.data)});}
  const inventory=payload.map(f=>({path:f.name,bytes:f.bytes.length,crc32:crc32Bytes(f.bytes).toString(16).padStart(8,'0'),sha256:tileSha256(f.bytes)})),anchor=q=>({...q,coordinate_convention:'source-normalized-top-left'}),manifest={schema_version:'asset-studio.object-package/v1',family:'object',inventory_policy:'payload-files-only; manifest.json excluded to avoid self-reference',coordinate_convention:'source-pixel-top-left; normalized anchors; world ground x-right/y-depth-down',sourceSize:{width:budget.W,height:budget.H},state_order:'base-then-result-order',states,requested_only_states:requestedOnly,atlas:{path:'atlas.png',width:budget.W*actual.length,height:budget.H,layout:'horizontal',cell:{width:budget.W,height:budget.H}},placement:{pivot:anchor(contract.placement.pivot),ground_point:anchor(contract.placement.ground_point),y_sort_point:anchor(contract.placement.y_sort_point),snap_points:contract.placement.snap_points.map(q=>({...q,coordinate_convention:'source-normalized-top-left'}))},scale:tileCanonical(contract.scale),collision:tileCanonical(contract.collision),interaction:{...tileCanonical(contract.interaction),coordinate_convention:'point source-normalized; radius world-tile-units'},custom_properties:tileCanonical(contract.custom_properties||contract.custom||{}),icon:{path:'inventory/icon.png',width:icon.width,height:icon.height,recipe:{mode:iconMode,resampling:'nearest-neighbor',alignment:'center',alpha:'straight RGBA'}},shadow:{mode:contract.shadow?.mode||'none',baked:!!contract.shadow?.baked,separate_file:shadowPath},inventory};const manifestBytes=enc.encode(tileJson(manifest));if(manifestBytes.length>OBJECT_EXPORT_LIMITS.maxManifestBytes)throw new Error('object export budget: actual manifest bytes exceeded');const files=[{name:'manifest.json',bytes:manifestBytes},...payload],zipBlob=buildStoredZip(files);if(!Number.isSafeInteger(zipBlob.size)||zipBlob.size>OBJECT_EXPORT_LIMITS.maxPayloadBytes)throw new Error('object export budget: actual final archive bytes exceeded');return {manifest,files,zipBlob,zipName:'object-package.zip'};
}
const TILE_PREVIEW_BUDGETS = Object.freeze({ maxDimension: 16384, maxSourcePixels: 16777216, maxWorkPixels: 16777216, maxCells: 4096, maxPreviewPixels: 4194304 });

// D3 is preview-only: these pure routines never touch Fabric, history, or exports.
const UI_NINE_SLICE_BUDGETS = Object.freeze({ maxDimension:16384, maxSourcePixels:16777216, maxTargetPixels:16777216, maxWorkPixels:67108864, maxAnalysisAuxiliaryBytes:67108864, maxOutputBackingBytes:67108864 });
function normalizeUiPreviewContract(contract) {
  const fail=reason=>{throw new Error(`UI contract: ${reason}`);};
  if(!contract||typeof contract!=='object'||Array.isArray(contract))fail('object required');
  const integer=(value,label,minimum=0)=>{if(!Number.isSafeInteger(value)||value<minimum||value>UI_NINE_SLICE_BUDGETS.maxDimension)fail(`${label} must be an integer in ${minimum}..${UI_NINE_SLICE_BUDGETS.maxDimension}`);return value;};
  const box=(value,label)=>{if(!value||typeof value!=='object'||Array.isArray(value))fail(`${label} object required`);return Object.fromEntries(['top','right','bottom','left'].map(key=>[key,integer(value[key],`${label}.${key}`)]));};
  const source=contract.source_size;if(!source||typeof source!=='object'||Array.isArray(source))fail('source_size object required');
  const source_size={width:integer(source.width,'source_size.width',1),height:integer(source.height,'source_size.height',1)};
  const slice_margins=box(contract.slice_margins,'slice_margins'),content_safe_area=box(contract.content_safe_area,'content_safe_area'),padding=box(contract.padding,'padding');
  if(slice_margins.left+slice_margins.right>source_size.width||slice_margins.top+slice_margins.bottom>source_size.height)fail('slice margins exceed source dimensions');
  const enumValue=(value,label,allowed)=>{if(typeof value!=='string'||!allowed.includes(value))fail(`${label} invalid enum`);return value;};
  if(!Array.isArray(contract.states)||contract.states.some(x=>typeof x!=='string'||!x.trim()))fail('states must be a list of nonempty strings');
  const states=contract.states.length?contract.states.map(x=>x.trim()):['base'];if(new Set(states).size!==states.length)fail('states must be unique');
  return {...contract,source_size,slice_margins,content_safe_area,padding,states,sizing_mode:enumValue(contract.sizing_mode,'sizing_mode',['fixed','nine-slice']),edge_mode:enumValue(contract.edge_mode,'edge_mode',['stretch','tile']),center_mode:enumValue(contract.center_mode,'center_mode',['stretch','tile'])};
}
function validateUiNineSliceBudget(imageWidth,imageHeight,contract,targetW=imageWidth,targetH=imageHeight) {
  contract=normalizeUiPreviewContract(contract);
  const fail=s=>{throw new Error(`UI nine-slice budget: ${s}`);},ints={imageWidth,imageHeight,targetW,targetH,sourceWidth:contract?.source_size?.width,sourceHeight:contract?.source_size?.height};
  for(const [k,v] of Object.entries(ints))if(!Number.isSafeInteger(v)||v<1)fail(`${k} must be a positive safe integer`);
  if(Object.values(ints).some(v=>v>UI_NINE_SLICE_BUDGETS.maxDimension))fail(`dimension exceeds ${UI_NINE_SLICE_BUDGETS.maxDimension}`);
  const mul=(a,b,n)=>{if(a&&b>Math.floor(Number.MAX_SAFE_INTEGER/a))fail(`${n} overflow`);return a*b;},sourcePixels=mul(imageWidth,imageHeight,'source pixels'),targetPixels=mul(targetW,targetH,'target pixels'),workPixels=sourcePixels+targetPixels*3;
  const analysisPixels=mul(contract.source_size.width,contract.source_size.height,'analysis pixels'),analysisAuxiliaryBytes=mul(analysisPixels,5,'analysis auxiliary bytes');
  if(sourcePixels>UI_NINE_SLICE_BUDGETS.maxSourcePixels)fail('source pixels exceed 16777216');if(targetPixels>UI_NINE_SLICE_BUDGETS.maxTargetPixels)fail('target pixels exceed 16777216');if(workPixels>UI_NINE_SLICE_BUDGETS.maxWorkPixels)fail('pixel work exceeds 67108864');if(analysisAuxiliaryBytes>UI_NINE_SLICE_BUDGETS.maxAnalysisAuxiliaryBytes)fail(`analysis auxiliary bytes exceed ${UI_NINE_SLICE_BUDGETS.maxAnalysisAuxiliaryBytes}`);
  return {sourcePixels,targetPixels,workPixels,analysisAuxiliaryBytes};
}
function validateUiPreviewBudget(imageWidth,imageHeight,contract,targetW,targetH,viewCount=1) {
  contract=normalizeUiPreviewContract(contract);const fail=s=>{throw new Error(`UI preview budget: ${s}`);};
  if(!Number.isSafeInteger(viewCount)||viewCount<1)fail('view count must be a positive safe integer');
  const single=validateUiNineSliceBudget(imageWidth,imageHeight,contract,targetW,targetH),mul=(a,b,n)=>{if(a&&b>Math.floor(Number.MAX_SAFE_INTEGER/a))fail(`${n} overflow`);return a*b;};
  const sw=contract.source_size.width,sh=contract.source_size.height,uniqueAnalysisCount=imageWidth===sw&&imageHeight===sh?1:viewCount;
  const viewPixels=mul(single.targetPixels,viewCount,'view pixels'),rgbaBytes=mul(viewPixels,4,'RGBA bytes'),canvasBackingBytes=mul(viewPixels,4,'canvas backing bytes'),outputBackingBytes=rgbaBytes+canvasBackingBytes;
  const analysisPixels=mul(mul(sw,sh,'analysis pixels'),uniqueAnalysisCount,'analysis work pixels'),analysisAuxiliaryBytes=mul(analysisPixels,5,'analysis auxiliary bytes'),workPixels=single.sourcePixels+analysisPixels+mul(viewPixels,3,'render work pixels');
  if(viewPixels>UI_NINE_SLICE_BUDGETS.maxTargetPixels)fail(`view pixels exceed ${UI_NINE_SLICE_BUDGETS.maxTargetPixels}`);
  if(outputBackingBytes>UI_NINE_SLICE_BUDGETS.maxOutputBackingBytes)fail(`output/backing bytes exceed ${UI_NINE_SLICE_BUDGETS.maxOutputBackingBytes}`);
  if(analysisAuxiliaryBytes>UI_NINE_SLICE_BUDGETS.maxAnalysisAuxiliaryBytes)fail(`analysis auxiliary bytes exceed ${UI_NINE_SLICE_BUDGETS.maxAnalysisAuxiliaryBytes}`);
  if(workPixels>UI_NINE_SLICE_BUDGETS.maxWorkPixels)fail(`pixel work exceeds ${UI_NINE_SLICE_BUDGETS.maxWorkPixels}`);
  return {viewCount,uniqueAnalysisCount,viewPixels,rgbaBytes,canvasBackingBytes,outputBackingBytes,analysisPixels,analysisAuxiliaryBytes,workPixels};
}
function uiNineSliceGeometry(contract,W,H) {
  contract=normalizeUiPreviewContract(contract);
  const s=contract?.slice_margins||{},box=n=>{const v=Number(s[n]??0);if(!Number.isSafeInteger(v)||v<0)throw new Error(`invalid slice_margins.${n}`);return v;},top=box('top'),right=box('right'),bottom=box('bottom'),left=box('left');
  if(left+right>contract.source_size.width||top+bottom>contract.source_size.height)throw new Error('invalid nine-slice margins');
  if(contract.sizing_mode==='nine-slice'){
    if(W<left+right||H<top+bottom)throw new Error('target smaller than fixed margins');
    if(W>contract.source_size.width&&left+right===contract.source_size.width)throw new Error('zero-width nine-slice stretch span cannot expand');
    if(H>contract.source_size.height&&top+bottom===contract.source_size.height)throw new Error('zero-height nine-slice stretch span cannot expand');
  }return {top,right,bottom,left};
}
function resolveUiPreviewRenderDimensions(contract,targetW,targetH) {
  contract=normalizeUiPreviewContract(contract);
  return contract.sizing_mode==='fixed'?[contract.source_size.width,contract.source_size.height]:[targetW,targetH];
}
function preflightUiPreview(imageWidth,imageHeight,contract,mode='source',options={}) {
  contract=normalizeUiPreviewContract(contract);if(typeof mode!=='string'||!['source','guides','small','medium','large','assembly','state-comparison','integer-scale'].includes(mode))throw new Error('UI preview mode: invalid enum');
  const safeInsets=contract.content_safe_area||{},padding=contract.padding||{},sw=contract.source_size.width,sh=contract.source_size.height,minW=Math.max(contract.slice_margins.left+contract.slice_margins.right,(safeInsets.left||0)+(safeInsets.right||0)+(padding.left||0)+(padding.right||0)+1),minH=Math.max(contract.slice_margins.top+contract.slice_margins.bottom,(safeInsets.top||0)+(safeInsets.bottom||0)+(padding.top||0)+(padding.bottom||0)+1),presets={small:[minW,minH],medium:[sw*2,sh*2],large:[sw*3,sh*3]},states=contract.states?.length||1;let viewCount=1,targetSize;
  if(['small','medium','large'].includes(mode))targetSize=presets[mode];else if(mode==='state-comparison'){targetSize=presets.medium;viewCount=states;}else if(mode==='assembly')targetSize=presets.medium;else targetSize=[sw,sh];
  const scale=mode==='integer-scale'?Math.max(1,Math.floor(Math.min((options.viewportWidth||sw*3)/sw,(options.viewportHeight||sh*3)/sh))):1,targetW=options.targetW??options.viewportWidth,targetH=options.targetH??options.viewportHeight,integerWarning=mode==='integer-scale'&&((targetW&&targetW%sw)||(targetH&&targetH%sh));
  if(mode==='integer-scale')targetSize=[sw*scale,sh*scale];else if(options.targetW!==undefined&&options.targetH!==undefined)targetSize=[options.targetW,options.targetH];
  const renderContract=mode==='source'||mode==='guides'?{...contract,sizing_mode:'fixed'}:contract,effectiveSize=resolveUiPreviewRenderDimensions(renderContract,targetSize[0],targetSize[1]);
  // Geometry is a pure gate: every effective view is resolved and rejected before RGBA analysis or canvas allocation.
  for(let index=0;index<viewCount;index++)uiNineSliceGeometry(renderContract,effectiveSize[0],effectiveSize[1]);
  const budget=validateUiPreviewBudget(imageWidth,imageHeight,contract,effectiveSize[0],effectiveSize[1],viewCount),targets=Array.from({length:viewCount},()=>effectiveSize);
  return {contract,renderContract,sw,sh,minW,minH,viewCount,targets,scale,integerWarning:!!integerWarning,budget};
}
function analyzeUiComponentImageData(imageData,contract) {
  contract=normalizeUiPreviewContract(contract);
  const W=imageData?.width,H=imageData?.height,sw=contract?.source_size?.width,sh=contract?.source_size?.height,states=Array.isArray(contract?.states)&&contract.states.length?contract.states:['base'];validateUiNineSliceBudget(W,H,contract,sw,sh);const d=imageData?.data;
  if(!d||d.length!==W*H*4)throw new Error('UI RGBA data size mismatch');let layout='drift',count=0;if(W===sw&&H===sh){layout='base-reused';count=1;}else if(W===sw*states.length&&H===sh){layout='horizontal-strip';count=states.length;}else if(H===sh*states.length&&W===sw){layout='vertical-strip';count=states.length;}
  const safe=contract.content_safe_area||{},pad=contract.padding||{},safeWidth=sw-(safe.left||0)-(safe.right||0)-(pad.left||0)-(pad.right||0),safeHeight=sh-(safe.top||0)-(safe.bottom||0)-(pad.top||0)-(pad.bottom||0),g=uiNineSliceGeometry(contract,sw,sh),edgeMode=contract.edge_mode||'stretch';
  const analyzeFrame=(stateIndex,stateId)=>{const reasons=[],frame=layout==='base-reused'?0:stateIndex,ox=layout==='horizontal-strip'?frame*sw:0,oy=layout==='vertical-strip'?frame*sh:0,off=(x,y)=>((oy+y)*W+ox+x)*4,eq=(a,b)=>d[a]===d[b]&&d[a+1]===d[b+1]&&d[a+2]===d[b+2]&&d[a+3]===d[b+3];let edgeMismatch=0,edgeComparisons=0;
    if(edgeMode==='tile'){
      const compare=(x1,y1,x2,y2)=>{edgeComparisons++;if(!eq(off(x1,y1),off(x2,y2)))edgeMismatch++;};
      const firstX=g.left,lastX=sw-g.right-1,firstY=g.top,lastY=sh-g.bottom-1;
      if(sw-g.left-g.right>0){
        for(let y=0;y<g.top;y++)compare(firstX,y,lastX,y);
        for(let y=sh-g.bottom;y<sh;y++)compare(firstX,y,lastX,y);
      }
      if(sh-g.top-g.bottom>0){
        for(let x=0;x<g.left;x++)compare(x,firstY,x,lastY);
        for(let x=sw-g.right;x<sw;x++)compare(x,firstY,x,lastY);
      }
      if(edgeMismatch)reasons.push('non-seamless-tiled-edge');
    }
    if(safeWidth<1||safeHeight<1)reasons.push('safe-area-violation');
    // Advisory only: 4-neighbour high-contrast components, 2..64 px, thin (<=3 px minimum axis), in content bounds.
    let glyphComponents=0;const x0=Math.max(0,safe.left||0),y0=Math.max(0,safe.top||0),x1=Math.min(sw,sw-(safe.right||0)),y1=Math.min(sh,sh-(safe.bottom||0)),seen=new Uint8Array(sw*sh),queue=new Uint32Array(sw*sh),fg=(x,y)=>{const i=off(x,y),a=d[i+3],lum=(d[i]*299+d[i+1]*587+d[i+2]*114)/1000;return a>0&&(lum<48||lum>207);};for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){const si=y*sw+x;if(seen[si]||!fg(x,y))continue;let head=0,tail=1,area=0,minX=x,maxX=x,minY=y,maxY=y;queue[0]=si;seen[si]=1;while(head<tail){const index=queue[head++],cx=index%sw,cy=Math.floor(index/sw);area++;minX=Math.min(minX,cx);maxX=Math.max(maxX,cx);minY=Math.min(minY,cy);maxY=Math.max(maxY,cy);const visit=(nx,ny)=>{if(nx>=x0&&nx<x1&&ny>=y0&&ny<y1){const ni=ny*sw+nx;if(!seen[ni]&&fg(nx,ny)){seen[ni]=1;queue[tail++]=ni;}}};visit(cx-1,cy);visit(cx+1,cy);visit(cx,cy-1);visit(cx,cy+1);}const cw=maxX-minX+1,ch=maxY-minY+1;if(area>=2&&area<=64&&Math.min(cw,ch)<=3&&Math.max(cw,ch)>=3)glyphComponents++;}if(glyphComponents>=2)reasons.push('baked-text-advisory');
    const fail=reasons.includes('safe-area-violation');return {stateId,stateIndex,sourceFrame:frame,status:fail?'FAIL':reasons.length?'WARN':'PASS',reasons,text_free:true,metrics:{stateId,stateIndex,sourceFrame:frame,edgeMismatch,edgeComparisons,edgeMismatchRate:edgeComparisons?edgeMismatch/edgeComparisons:0,safeWidth,safeHeight,glyphComponents,bakedTextHeuristic:glyphComponents>=2,analysisAuxiliaryBytes:sw*sh*5}};};
  if(layout==='drift')return {status:'FAIL',reasons:['state-size-drift'],stateLayout:layout,stateCount:count,declaredStateCount:states.length,stateReuse:states.map((id,index)=>({id,index,sourceFrame:index,label:'drift'})),stateQas:[],text_free:true,metrics:{edgeMismatch:0,edgeComparisons:0,edgeMismatchRate:0,safeWidth,safeHeight,glyphComponents:0,bakedTextHeuristic:false}};
  const stateQas=layout==='base-reused'?(()=>{const base=analyzeFrame(0,states[0]);return states.map((id,index)=>index===0?base:{...base,stateId:id,stateIndex:index,reasons:[...base.reasons],metrics:{...base.metrics,stateId:id,stateIndex:index}});})():states.map((id,index)=>analyzeFrame(index,id)),aggregateQas=layout==='base-reused'?stateQas.slice(0,1):stateQas,reasons=[];for(const q of aggregateQas)for(const reason of q.reasons)if(!reasons.includes(reason))reasons.push(reason);const status=aggregateQas.some(q=>q.status==='FAIL')?'FAIL':aggregateQas.some(q=>q.status==='WARN')?'WARN':'PASS',metrics={edgeMismatch:aggregateQas.reduce((n,q)=>n+q.metrics.edgeMismatch,0),edgeComparisons:aggregateQas.reduce((n,q)=>n+q.metrics.edgeComparisons,0),safeWidth,safeHeight,glyphComponents:aggregateQas.reduce((n,q)=>n+q.metrics.glyphComponents,0),bakedTextHeuristic:aggregateQas.some(q=>q.metrics.bakedTextHeuristic),analysisAuxiliaryBytes:sw*sh*5,uniqueAnalysisCount:layout==='base-reused'?1:stateQas.length,states:stateQas.map(q=>q.metrics)};metrics.edgeMismatchRate=metrics.edgeComparisons?metrics.edgeMismatch/metrics.edgeComparisons:0;
  return {status,reasons,stateLayout:layout,stateCount:count,declaredStateCount:states.length,stateReuse:layout==='base-reused'?states.map((id,index)=>({id,index,sourceFrame:0,label:'base reused'})):states.map((id,index)=>({id,index,sourceFrame:index,label:layout.replace('-strip',' strip')})),stateQas,text_free:true,metrics};
}
function renderUiNineSliceImageData(imageData,contract,targetW,targetH,stateIndex=0,precomputedQa=null) {
  contract=normalizeUiPreviewContract(contract);
  const W=imageData?.width,H=imageData?.height,sw=contract?.source_size?.width,sh=contract?.source_size?.height,effective=resolveUiPreviewRenderDimensions(contract,targetW,targetH);targetW=effective[0];targetH=effective[1];validateUiNineSliceBudget(W,H,contract,targetW,targetH);const g=uiNineSliceGeometry(contract,targetW,targetH),qa=precomputedQa||analyzeUiComponentImageData(imageData,contract);if(qa.stateLayout==='drift')throw new Error('state-size-drift');const fixed=contract.sizing_mode==='fixed',out=new Uint8ClampedArray(targetW*targetH*4),frame=Math.max(0,Math.min(qa.stateCount-1,Math.floor(stateIndex)||0)),ox=qa.stateLayout==='horizontal-strip'?frame*sw:0,oy=qa.stateLayout==='vertical-strip'?frame*sh:0;
  const map=(p,dstLen,a,b,srcLen,mode)=>p<a?p:p>=dstLen-b?srcLen-(dstLen-p):(mode==='tile'?a+(p-a)%Math.max(1,srcLen-a-b):a+Math.min(srcLen-a-b-1,Math.floor((p-a)*Math.max(1,srcLen-a-b)/Math.max(1,dstLen-a-b))));
  for(let y=0;y<targetH;y++)for(let x=0;x<targetW;x++){const sx=fixed?x:map(x,targetW,g.left,g.right,sw,(y<g.top||y>=targetH-g.bottom)?contract.edge_mode:contract.center_mode),sy=fixed?y:map(y,targetH,g.top,g.bottom,sh,(x<g.left||x>=targetW-g.right)?contract.edge_mode:contract.center_mode),si=((oy+sy)*W+ox+sx)*4,di=(y*targetW+x)*4;out[di]=imageData.data[si];out[di+1]=imageData.data[si+1];out[di+2]=imageData.data[si+2];out[di+3]=imageData.data[si+3];}
  let cornerMismatch=0;for(const [dx,dy,sx,sy,w,h] of [[0,0,0,0,g.left,g.top],[targetW-g.right,0,sw-g.right,0,g.right,g.top],[0,targetH-g.bottom,0,sh-g.bottom,g.left,g.bottom],[targetW-g.right,targetH-g.bottom,sw-g.right,sh-g.bottom,g.right,g.bottom]])for(let y=0;y<h;y++)for(let x=0;x<w;x++)for(let c=0;c<4;c++)if(out[((dy+y)*targetW+dx+x)*4+c]!==imageData.data[((oy+sy+y)*W+ox+sx+x)*4+c])cornerMismatch++;
  const stateQas=Array.isArray(qa.stateQas)?qa.stateQas:[],selectedQa=stateQas[Math.max(0,Math.min(stateQas.length-1,Math.floor(stateIndex)||0))]||qa,safe=contract.content_safe_area||{},pad=contract.padding||{},safeWidth=targetW-(safe.left||0)-(safe.right||0)-(pad.left||0)-(pad.right||0),safeHeight=targetH-(safe.top||0)-(safe.bottom||0)-(pad.top||0)-(pad.bottom||0),safeViolation=safeWidth<1||safeHeight<1,reasons=[...selectedQa.reasons];if(cornerMismatch)reasons.unshift('stretched-corners');if(safeViolation&&!reasons.includes('safe-area-violation'))reasons.push('safe-area-violation');
  return {width:targetW,height:targetH,data:out,qa:{status:cornerMismatch||safeViolation?'FAIL':selectedQa.status,reasons,metrics:{...selectedQa.metrics,safeWidth,safeHeight,cornerMismatch}}};
}
function buildUiPreviewModel(imageData,contract,mode='source',options={}) {
  const preflight=preflightUiPreview(imageData?.width,imageData?.height,contract,mode,options),{renderContract,sw,sh,minW,minH,viewCount,targets,scale,integerWarning,budget}=preflight;contract=preflight.contract;
  const qa=analyzeUiComponentImageData(imageData,contract),views=targets.map((z,i)=>renderUiNineSliceImageData(imageData,renderContract,z[0],z[1],mode==='state-comparison'?i:0,qa));
  const safe={left:contract.content_safe_area.left||0,top:contract.content_safe_area.top||0,right:sw-(contract.content_safe_area.right||0),bottom:sh-(contract.content_safe_area.bottom||0)},p=contract.padding||{};
  const guideCoordinates=mode==='guides'?{slice:{x:[contract.slice_margins.left,sw-contract.slice_margins.right],y:[contract.slice_margins.top,sh-contract.slice_margins.bottom]},contentSafe:safe,padding:{left:safe.left+(p.left||0),top:safe.top+(p.top||0),right:safe.right-(p.right||0),bottom:safe.bottom-(p.bottom||0)},sourceScale:1}:null;
  let assembly=null;if(mode==='assembly'){const safeArea={left:(contract.content_safe_area.left||0)+(p.left||0),top:(contract.content_safe_area.top||0)+(p.top||0),right:targets[0][0]-(contract.content_safe_area.right||0)-(p.right||0),bottom:targets[0][1]-(contract.content_safe_area.bottom||0)-(p.bottom||0)},safeWidth=safeArea.right-safeArea.left,safeHeight=safeArea.bottom-safeArea.top,possible=safeWidth>0&&safeHeight>0&&safeWidth*safeHeight>=3;let placeholders=[];if(possible){const types=['icon','text','content'];if(safeHeight>=3){placeholders=types.map((type,index)=>{const top=safeArea.top+Math.floor(index*safeHeight/3),bottom=safeArea.top+Math.floor((index+1)*safeHeight/3);return {type,x:safeArea.left,y:top,width:safeWidth,height:bottom-top};});}else{placeholders=types.map((type,index)=>{const left=safeArea.left+Math.floor(index*safeWidth/3),right=safeArea.left+Math.floor((index+1)*safeWidth/3);return {type,x:left,y:safeArea.top,width:right-left,height:safeHeight};});}}assembly={temporary:true,placeholders,safeArea,possible,reason:possible?'temporary-preview-only':'safe-area-violation'};}
  return {mode,views,qa,budget,guides:mode==='guides',guideCoordinates,assembly,stateLabels:qa.stateReuse,resizeReason:mode==='small'?(minW===sw&&minH===sh?'degenerate-source-already-minimum':'resized-to-minimum'):null,integerScale:{scale,warning:!!integerWarning,reason:integerWarning?'noninteger-target':'integer-scale'}};
}
function renderUiPreviewModel(model,contract,stage,summary) {
  contract=normalizeUiPreviewContract(contract);stage.replaceChildren();const reasons=new Set(model.qa.reasons),viewMetrics=[];let status=model.qa.status;
  model.views.forEach((view,index)=>{const card=document.createElement('div'),label=document.createElement('div'),out=document.createElement('canvas'),ctx=out.getContext('2d');card.className='ui-nine-slice-preview-view';label.className='ui-nine-slice-preview-label';const state=model.stateLabels?.[index];label.textContent=state?`${state.id} · ${state.label}`:`${view.width}×${view.height}`;out.width=view.width;out.height=view.height;ctx.imageSmoothingEnabled=false;ctx.putImageData(new ImageData(view.data,view.width,view.height),0,0);
    if(model.guides){const c=model.guideCoordinates;ctx.setLineDash([4,3]);ctx.strokeStyle='#ff3b81';for(const x of c.slice.x){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,view.height);ctx.stroke();}for(const y of c.slice.y){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(view.width,y);ctx.stroke();}ctx.strokeStyle='#52d9ff';ctx.strokeRect(c.contentSafe.left,c.contentSafe.top,c.contentSafe.right-c.contentSafe.left,c.contentSafe.bottom-c.contentSafe.top);ctx.strokeStyle='#ffd166';ctx.strokeRect(c.padding.left,c.padding.top,c.padding.right-c.padding.left,c.padding.bottom-c.padding.top);}
    if(model.assembly){const a=model.assembly.safeArea;ctx.fillStyle='rgba(20,20,30,.65)';ctx.fillRect(a.left,a.top,Math.max(0,a.right-a.left),Math.max(0,a.bottom-a.top));const colors={icon:'#52d9ff',text:'#ffd166',content:'#ff3b81'};for(const placeholder of model.assembly.placeholders){const left=Math.max(a.left,placeholder.x),top=Math.max(a.top,placeholder.y),right=Math.min(a.right,placeholder.x+placeholder.width),bottom=Math.min(a.bottom,placeholder.y+placeholder.height);if(right>left&&bottom>top){ctx.fillStyle=colors[placeholder.type];ctx.fillRect(left,top,right-left,bottom-top);}}}
    for(const reason of view.qa.reasons)reasons.add(reason);viewMetrics.push({...view.qa.metrics});if(view.qa.status==='FAIL')status='FAIL';else if(view.qa.status==='WARN'&&status==='PASS')status='WARN';card.appendChild(label);card.appendChild(out);stage.appendChild(card);});
  const uniqueBySourceFrame=new Map();viewMetrics.forEach((m,index)=>{const key=Number.isSafeInteger(m.sourceFrame)?`frame:${m.sourceFrame}`:`view:${index}`;if(!uniqueBySourceFrame.has(key))uniqueBySourceFrame.set(key,m);});const uniqueMetricRecords=[...uniqueBySourceFrame.values()],sum=key=>uniqueMetricRecords.reduce((n,m)=>n+(Number.isFinite(m[key])?m[key]:0),0),minimum=key=>{const values=viewMetrics.map(m=>m[key]).filter(Number.isFinite);return values.length?Math.min(...values):null;},edgeMismatch=sum('edgeMismatch'),edgeComparisons=sum('edgeComparisons'),metrics={edgeMismatch,edgeComparisons,edgeMismatchRate:edgeComparisons?edgeMismatch/edgeComparisons:0,safeWidth:minimum('safeWidth'),safeHeight:minimum('safeHeight'),glyphComponents:sum('glyphComponents'),bakedTextHeuristic:uniqueMetricRecords.some(m=>m.bakedTextHeuristic),uniqueMetricRecords,views:viewMetrics};
  if(model.assembly&&!model.assembly.possible){reasons.add(model.assembly.reason||'safe-area-violation');status='FAIL';}if(model.integerScale.warning){reasons.add('noninteger-target');if(status==='PASS')status='WARN';}summary.dataset.status=status;summary.textContent=`${status} · ${[...reasons].join(', ')||'no issues'}\n${JSON.stringify(metrics)}\nintegerScale ${model.integerScale.scale}× · ${model.integerScale.reason}${model.resizeReason?`\nresize · ${model.resizeReason}`:''}`;return {status,reasons:[...reasons],metrics};
}
window.__assetStudioDebug={...(window.__assetStudioDebug||{}),validateUiNineSliceBudget,validateUiPreviewBudget,analyzeUiComponentImageData,renderUiNineSliceImageData,buildUiPreviewModel,renderUiPreviewModel};
async function buildUiNineSlicePreview(){const object=canvas.getActiveObject(),source=object?._element;if(!source)throw new Error('이미지 레이어를 선택하세요.');const W=source.naturalWidth||source.width,H=source.naturalHeight||source.height,contract=normalizeUiPreviewContract(buildUiContract()),mode=$('uiPreviewMode')?.value||'source',options={viewportWidth:320,viewportHeight:180};preflightUiPreview(W,H,contract,mode,options);const input=document.createElement('canvas');input.width=W;input.height=H;const ix=input.getContext('2d',{willReadFrequently:true});ix.drawImage(source,0,0,W,H);const imageData=ix.getImageData(0,0,W,H),model=buildUiPreviewModel(imageData,contract,mode,options);renderUiPreviewModel(model,contract,$('uiNineSlicePreviewStage'),$('uiNineSliceQaSummary'));return model;}
if($('buildUiNineSlicePreview'))$('buildUiNineSlicePreview').onclick=()=>buildUiNineSlicePreview().catch(e=>setStatus(`UI 미리보기 실패: ${e.message}`));

const UI_EXPORT_LIMITS=Object.freeze({maxStates:256,maxOutputPixels:16777216,maxPayloadBytes:134217728});
function checkUiExportBudget(imageData,contract){
  contract=normalizeUiPreviewContract(contract);const W=imageData?.width,H=imageData?.height,sw=contract.source_size.width,sh=contract.source_size.height,count=contract.states.length;
  validateUiNineSliceBudget(W,H,contract,sw,sh);
  const fail=reason=>{throw new Error(`UI export budget: ${reason}`);};
  if(count<1||count>UI_EXPORT_LIMITS.maxStates)fail('state count exceeds allowed limit');
  const outputPixels=sw*sh*count;if(!Number.isSafeInteger(outputPixels)||outputPixels>UI_EXPORT_LIMITS.maxOutputPixels)fail('output pixels exceed allowed limit');
  const estimatedPayload=outputPixels*4+count*(sh+256)+65536;if(!Number.isSafeInteger(estimatedPayload)||estimatedPayload>UI_EXPORT_LIMITS.maxPayloadBytes)fail('payload bytes exceed allowed limit');
  return {outputPixels,estimatedPayload};
}
function uiExportStateFilename(id,used){
  if(typeof id!=='string'||id.length>64||!/^[a-z0-9][a-z0-9_-]*$/.test(id)||id==='manifest'||id==='.'||id==='..')throw new Error(`UI export state filename is unsafe: ${String(id)}`);
  const key=id.toLowerCase();if(used.has(key))throw new Error(`UI export state filename collision: ${id}`);used.add(key);return `states/${id}.png`;
}
function extractUiStateFrames(imageData,contract){
  contract=normalizeUiPreviewContract(contract);checkUiExportBudget(imageData,contract);const qa=analyzeUiComponentImageData(imageData,contract);
  if(qa.stateLayout==='drift')throw new Error('UI export state-size-drift');
  const W=imageData.width,sw=contract.source_size.width,sh=contract.source_size.height;
  return contract.states.map((id,index)=>{const frame=qa.stateLayout==='base-reused'?0:index,ox=qa.stateLayout==='horizontal-strip'?frame*sw:0,oy=qa.stateLayout==='vertical-strip'?frame*sh:0,data=new Uint8ClampedArray(sw*sh*4);for(let y=0;y<sh;y++){const start=((oy+y)*W+ox)*4;data.set(imageData.data.subarray(start,start+sw*4),y*sw*4);}return {id,index,sourceFrame:frame,width:sw,height:sh,data};});
}
function buildUiExportPackage(imageData,rawContract){
  const contract=normalizeUiPreviewContract(rawContract);checkUiExportBudget(imageData,contract);const frames=extractUiStateFrames(imageData,contract),used=new Set(),paths=frames.map(frame=>uiExportStateFilename(frame.id,used));
  const manifest={schema_version:'asset-studio.ui-state-package/v1',family:'ui',text_free:true,sourceSize:{...contract.source_size},sliceMargins:{...contract.slice_margins},safeArea:{...contract.content_safe_area},padding:{...contract.padding},modes:{sizing:contract.sizing_mode,edge:contract.edge_mode,center:contract.center_mode},stateLayout:analyzeUiComponentImageData(imageData,contract).stateLayout,states:frames.map((frame,index)=>({id:frame.id,file:paths[index],sourceFrame:frame.sourceFrame,width:frame.width,height:frame.height}))};
  const encoder=new TextEncoder(),files=[{name:'manifest.json',bytes:encoder.encode(`${JSON.stringify(manifest,null,2)}\n`)}];frames.forEach((frame,index)=>files.push({name:paths[index],bytes:encodeEffectFramePng(frame.width,frame.height,frame.data)}));
  return {manifest,files,zipBlob:buildStoredZip(files),zipName:'ui-state-package.zip'};
}
async function selectedUiSourceImageData(){const object=canvas.getActiveObject(),source=object?._element;if(!source)throw new Error('이미지 레이어를 선택하세요.');const W=source.naturalWidth||source.width,H=source.naturalHeight||source.height;const contract=normalizeUiPreviewContract(buildUiContract());checkUiExportBudget({width:W,height:H},contract);const input=document.createElement('canvas');input.width=W;input.height=H;const context=input.getContext('2d',{willReadFrequently:true});context.drawImage(source,0,0,W,H);return {imageData:context.getImageData(0,0,W,H),contract};}
async function exportUiStatePackageZip(){const button=$('exportUiStateZip');if(button)button.disabled=true;try{const {imageData,contract}=await selectedUiSourceImageData(),packageResult=buildUiExportPackage(imageData,contract);downloadBlob(packageResult.zipBlob,packageResult.zipName);if($('uiExportSummary'))$('uiExportSummary').textContent=`완료 · ${packageResult.manifest.states.length} states + manifest`;setStatus(`UI 상태 ZIP 내보내기 완료: ${packageResult.manifest.states.length} states`);return packageResult;}catch(error){if($('uiExportSummary'))$('uiExportSummary').textContent=`실패 · ${error.message}`;setStatus(`UI 상태 ZIP 내보내기 실패: ${error.message}`);throw error;}finally{if(button)button.disabled=false;}}
if($('exportUiStateZip'))$('exportUiStateZip').onclick=()=>exportUiStatePackageZip().catch(()=>{});
window.__assetStudioDebug={...(window.__assetStudioDebug||{}),checkUiExportBudget,extractUiStateFrames,buildUiExportPackage,exportUiStatePackageZip};

function validateTilePreviewBudget(imageWidth, imageHeight, contract, mode='analysis') {
  const c=contract||{}, values={imageWidth,imageHeight,tileWidth:c.tile_size?.width,tileHeight:c.tile_size?.height,rows:c.rows,columns:c.columns,margin:c.margin,spacing:c.spacing};
  const fail=reason=>{throw new Error(`tile preview budget: ${reason}`);};
  for(const [name,value] of Object.entries(values)) if(!Number.isSafeInteger(value)||value<0)fail(`${name} must be a nonnegative safe integer`);
  if(imageWidth<1||imageHeight<1||values.tileWidth<1||values.tileHeight<1||values.rows<1||values.columns<1)fail('image, tile, rows, and columns must be positive');
  if(Object.values(values).some(value=>value>TILE_PREVIEW_BUDGETS.maxDimension))fail(`dimension exceeds ${TILE_PREVIEW_BUDGETS.maxDimension}`);
  const multiply=(a,b,label)=>{if(a!==0&&b>Math.floor(Number.MAX_SAFE_INTEGER/a))fail(`${label} arithmetic overflow`);return a*b;};
  const add=(a,b,label)=>{if(b>Number.MAX_SAFE_INTEGER-a)fail(`${label} arithmetic overflow`);return a+b;};
  const sourcePixels=multiply(imageWidth,imageHeight,'source pixels');
  const cellCount=multiply(values.rows,values.columns,'cell count');
  const tilePixels=multiply(values.tileWidth,values.tileHeight,'tile pixels');
  const workPixels=multiply(cellCount,tilePixels,'pixel work');
  let footprintWidth=add(multiply(2,values.margin,'footprint width'),multiply(values.columns,values.tileWidth,'footprint width'),'footprint width');
  footprintWidth=add(footprintWidth,multiply(values.columns-1,values.spacing,'footprint width'),'footprint width');
  let footprintHeight=add(multiply(2,values.margin,'footprint height'),multiply(values.rows,values.tileHeight,'footprint height'),'footprint height');
  footprintHeight=add(footprintHeight,multiply(values.rows-1,values.spacing,'footprint height'),'footprint height');
  if(sourcePixels>TILE_PREVIEW_BUDGETS.maxSourcePixels)fail(`source pixels exceed ${TILE_PREVIEW_BUDGETS.maxSourcePixels}`);
  if(cellCount>TILE_PREVIEW_BUDGETS.maxCells)fail(`cells exceed ${TILE_PREVIEW_BUDGETS.maxCells}`);
  if(workPixels>TILE_PREVIEW_BUDGETS.maxWorkPixels)fail(`pixel work exceeds ${TILE_PREVIEW_BUDGETS.maxWorkPixels}`);
  let previewWidth=imageWidth,previewHeight=imageHeight;
  if(mode==='repeat-3x3'){previewWidth=values.tileWidth*3;previewHeight=values.tileHeight*3;}
  else if(mode==='random-repeat'||mode==='terrain-brush'){previewWidth=values.tileWidth*12;previewHeight=values.tileHeight*8;}
  else if(mode==='rule-coverage'){previewWidth=Math.min(8,cellCount)*values.tileWidth;previewHeight=Math.ceil(cellCount/Math.min(8,cellCount))*values.tileHeight;}
  else if(mode==='overlay'){previewWidth=values.columns*values.tileWidth;previewHeight=values.rows*values.tileHeight;}
  else if(mode==='variant-distribution'){previewWidth=320;previewHeight=Math.max(48,(c.variants?.length||0)*24+8);}
  if(mode!=='analysis'&&multiply(previewWidth,previewHeight,'preview pixels')>TILE_PREVIEW_BUDGETS.maxPreviewPixels)fail(`preview pixels exceed ${TILE_PREVIEW_BUDGETS.maxPreviewPixels}`);
  return {sourcePixels,cellCount,workPixels,footprintWidth,footprintHeight,previewWidth,previewHeight};
}
function analyzeTileAtlasImageData(imageData, tileContract) {
  const W=imageData?.width,H=imageData?.height,c=tileContract||{},budget=validateTilePreviewBudget(W,H,c,'analysis'),d=imageData?.data||[];
  const tw=c.tile_size.width,th=c.tile_size.height,rows=c.rows,cols=c.columns,m=c.margin,s=c.spacing,count=budget.cellCount;
  const footprint={width:budget.footprintWidth,height:budget.footprintHeight},cells=[],hashes=new Set();
  const px=(x,y)=>x<0||y<0||x>=W||y>=H?null:Array.from(d.slice((y*W+x)*4,(y*W+x)*4+4)),eq=(a,b)=>!!a&&!!b&&a.every((v,i)=>v===b[i]);
  const pitchX=tw+s,pitchY=th+s;
  const inside=(x,y)=>{const localX=x-m,localY=y-m;if(localX<0||localY<0)return false;const column=Math.floor(localX/pitchX),row=Math.floor(localY/pitchY);return column<cols&&row<rows&&localX%pitchX<tw&&localY%pitchY<th;};
  let outOfGrid=0,seamMismatch=0,seamComparisons=0,badCorners=0;
  for(let y=0;y<H;y++)for(let x=0;x<W;x++)if(d[(y*W+x)*4+3]>0&&!inside(x,y))outOfGrid++;
  for(let r=0;r<rows;r++)for(let q=0;q<cols;q++){let x=m+q*pitchX,y=m+r*pitchY,h=2166136261>>>0;
    for(let yy=0;yy<th;yy++)for(let xx=0;xx<tw;xx++)for(const v of(px(x+xx,y+yy)||[0,0,0,0])){h^=v;h=Math.imul(h,16777619)>>>0;}
    if(c.seamless){for(let yy=0;yy<th;yy++){seamComparisons++;if(!eq(px(x,y+yy),px(x+tw-1,y+yy)))seamMismatch++;}for(let xx=0;xx<tw;xx++){seamComparisons++;if(!eq(px(x+xx,y),px(x+xx,y+th-1)))seamMismatch++;}}
    const C=[[px(x,y),px(x+Math.min(1,tw-1),y),px(x,y+Math.min(1,th-1))],[px(x+tw-1,y),px(x+Math.max(0,tw-2),y),px(x+tw-1,y+Math.min(1,th-1))],[px(x,y+th-1),px(x+Math.min(1,tw-1),y+th-1),px(x,y+Math.max(0,th-2))],[px(x+tw-1,y+th-1),px(x+Math.max(0,tw-2),y+th-1),px(x+tw-1,y+Math.max(0,th-2))]];
    if((c.inner_corners||c.outer_corners)&&C.some(z=>!eq(z[0],z[1])||!eq(z[0],z[2])))badCorners++;
    const hash=h.toString(16).padStart(8,'0');hashes.add(hash);cells.push({index:r*cols+q,x,y,width:tw,height:th,hash});}
  const declarations=[...(c.terrain_types||[]),...(c.transitions||[]),...(c.topology?[c.topology]:[]),...(c.inner_corners?['inner-corner']:[]),...(c.outer_corners?['outer-corner']:[])],truncated=footprint.width>W||footprint.height>H,missingRule=Math.max(0,declarations.length-count)+(truncated?(declarations.length||1):0);
  const metadataMismatch=[];const walk=(v,p)=>{if(Array.isArray(v)&&/(indices|tiles|tile_indices)$/i.test(p))v.forEach((n,i)=>{if(!Number.isInteger(n)||n<0||n>=count)metadataMismatch.push(`${p}[${i}]`);});else if(v&&typeof v==='object')Object.entries(v).forEach(([k,z])=>walk(z,p+'.'+k));};walk(c.metadata||{},'metadata');
  const variants=(c.variants||[]).map((v,i)=>({id:String(v?.id??i),weight:Number.isFinite(+v?.weight)?+v.weight:0})),positive=variants.map(v=>Math.max(0,v.weight)),total=positive.reduce((a,b)=>a+b,0);variants.forEach((v,i)=>v.normalized=variants.length?(total?positive[i]/total:1/variants.length):0);
  const duplicateCount=count-hashes.size,reasons=[];if(truncated)reasons.push('declared-grid-truncated');if(seamMismatch)reasons.push('seam-mismatch');if(missingRule)reasons.push('missing-rule');if(badCorners)reasons.push('bad-corner');if(count>1&&duplicateCount/count>=.5)reasons.push('repeated-pattern');if(outOfGrid)reasons.push('out-of-grid');if(metadataMismatch.length)reasons.push('metadata-mismatch');
  return {status:reasons.some(x=>x==='declared-grid-truncated'||x==='metadata-mismatch')?'FAIL':reasons.length?'WARN':'PASS',reasons,footprint,cells,variants,metadataMismatch,metrics:{tileCount:count,seamMismatch,seamComparisons,seamMismatchRate:seamComparisons?seamMismatch/seamComparisons:0,badCorners,uniqueHashes:hashes.size,duplicateCount,duplicateRatio:duplicateCount/count,outOfGrid,missingRule,metadataMismatchCount:metadataMismatch.length}};
}
function buildTilePreviewModel(imageData,c,mode='source') {
  const budget=validateTilePreviewBudget(imageData?.width,imageData?.height,c,mode),qa=analyzeTileAtlasImageData(imageData,c),tw=qa.cells[0]?.width||1,th=qa.cells[0]?.height||1,n=Math.max(1,qa.cells.length);let columns=c.columns||1,rows=c.rows||1,sequence=qa.cells.map(x=>x.index),overlays=[],distributionBars=[],width=budget.previewWidth,height=budget.previewHeight,seed=2166136261>>>0;
  for(const z of qa.cells)for(const ch of z.hash){seed^=ch.charCodeAt(0);seed=Math.imul(seed,16777619)>>>0;}const rnd=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;};
  if(mode==='repeat-3x3'){columns=rows=3;sequence=Array(9).fill(0);}else if(mode==='random-repeat'||mode==='terrain-brush'){columns=12;rows=8;sequence=Array.from({length:96},(_,i)=>mode==='terrain-brush'?(i+Math.floor(i/12))%n:Math.floor(rnd()*n));}else if(mode==='rule-coverage'){columns=Math.max(1,Math.min(8,n));rows=Math.ceil(n/columns);overlays=[...(c.terrain_types||[]),...(c.transitions||[]),c.topology,c.inner_corners?'inner-corner':null,c.outer_corners?'outer-corner':null].filter(Boolean);}else if(mode==='overlay'){overlays=['collision','occlusion','navigation'].filter(k=>c.metadata?.[k]!=null);}else if(mode==='variant-distribution'){columns=1;rows=Math.max(1,qa.variants.length);sequence=[];overlays=qa.variants;distributionBars=qa.variants.map((v,i)=>({id:v.id,normalized:v.normalized,percent:`${(v.normalized*100).toFixed(1)}%`,widthRatio:v.normalized,y:8+i*24,height:16}));}
  return {mode,width,height,columns,rows,sequence,overlays,distributionBars,qa,seed:seed>>>0};
}
function fitTilePreview(sourceWidth, sourceHeight, viewportWidth, viewportHeight) {
  const sw=Math.max(1,Number(sourceWidth)||1),sh=Math.max(1,Number(sourceHeight)||1),vw=Math.max(1,Math.floor(Number(viewportWidth)||1)),vh=Math.max(1,Math.floor(Number(viewportHeight)||1));
  const availableScale=Math.min(vw/sw,vh/sh),scale=availableScale>=1?Math.max(1,Math.floor(availableScale)):availableScale;
  const width=Math.min(vw,sw*scale),height=Math.min(vh,sh*scale);
  return {x:(vw-width)/2,y:(vh-height)/2,width,height,scale};
}
window.__assetStudioDebug = { ...(window.__assetStudioDebug || {}), validateTilePreviewBudget, analyzeTileAtlasImageData, buildTilePreviewModel, fitTilePreview };
async function buildTileAtlasPreview() {
  const object=canvas.getActiveObject(),source=object?._element;
  if(!source)throw new Error('이미지 레이어를 선택하세요.');
  const sw=source.naturalWidth||source.width,sh=source.naturalHeight||source.height,contract=buildTileContract(),mode=$('tilePreviewMode')?.value||'source';
  validateTilePreviewBudget(sw,sh,contract,mode);
  const input=document.createElement('canvas');input.width=sw;input.height=sh;
  const ix=input.getContext('2d',{willReadFrequently:true});ix.drawImage(source,0,0,sw,sh);
  const imageData=ix.getImageData(0,0,sw,sh),model=buildTilePreviewModel(imageData,contract,mode),preview=document.createElement('canvas');
  preview.width=model.width;preview.height=model.height;const px=preview.getContext('2d');px.imageSmoothingEnabled=false;px.clearRect(0,0,preview.width,preview.height);
  if(model.mode==='source')px.drawImage(input,0,0);else model.sequence.forEach((index,i)=>{const cell=model.qa.cells[index];if(!cell)return;px.drawImage(input,cell.x,cell.y,cell.width,cell.height,(i%model.columns)*cell.width,Math.floor(i/model.columns)*cell.height,cell.width,cell.height);});
  if(model.mode==='variant-distribution'){
    px.font='12px sans-serif';px.textBaseline='middle';
    for(const bar of model.distributionBars){const label=`${bar.id} · ${bar.percent}`,barX=112,barMax=preview.width-barX-8;px.fillStyle='#263247';px.fillRect(barX,bar.y,barMax,bar.height);px.fillStyle='#7c5cff';px.fillRect(barX,bar.y,barMax*bar.widthRatio,bar.height);px.fillStyle='#fff';px.fillText(label,6,bar.y+bar.height/2);}
  }else if(model.overlays.length){px.fillStyle='rgba(0,0,0,.62)';px.fillRect(0,0,preview.width,Math.min(preview.height,18));px.fillStyle='#fff';px.font='10px sans-serif';px.fillText(model.overlays.map(x=>typeof x==='string'?x:x.id).join(' · '),3,12);}
  const out=$('tilePreviewCanvas'),stage=$('tilePreviewStage'),viewportWidth=stage?.clientWidth||320,viewportHeight=stage?.clientHeight||180,fit=fitTilePreview(model.width,model.height,viewportWidth,viewportHeight),ctx=out.getContext('2d');out.width=viewportWidth;out.height=viewportHeight;ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,out.width,out.height);ctx.drawImage(preview,fit.x,fit.y,fit.width,fit.height);
  const summary=$('tileQaSummary');summary.dataset.status=model.qa.status;summary.textContent=`${model.qa.status} · ${model.qa.reasons.join(', ')||'no issues'}\n${JSON.stringify(model.qa.metrics)}`;return model;
}
if($('buildObjectPlacementPreview'))$('buildObjectPlacementPreview').onclick=()=>{try{buildObjectPlacementPreview()}catch(e){setStatus(`오브젝트 미리보기 실패: ${e.message}`)}};
const rerenderObjectPlacement=()=>{try{buildObjectPlacementPreview()}catch(e){setStatus(`오브젝트 미리보기 실패: ${e.message}`)}};
if($('objectPreviewSource'))$('objectPreviewSource').onchange=rerenderObjectPlacement;
if($('objectPreviewState'))$('objectPreviewState').onchange=rerenderObjectPlacement;
if($('objectPreviewShadow'))$('objectPreviewShadow').onchange=rerenderObjectPlacement;
if($('objectPreviewUsage'))$('objectPreviewUsage').onchange=rerenderObjectPlacement;
if($('objectPreviewIconMode'))$('objectPreviewIconMode').onchange=rerenderObjectPlacement;
if($('buildTilePreview'))$('buildTilePreview').onclick=()=>buildTileAtlasPreview().catch(e=>setStatus(`타일 미리보기 실패: ${e.message}`));
async function selectedTileImageData(contract=null) {
  const source=canvas.getActiveObject()?._element;if(!source)throw new Error('이미지 레이어를 선택하세요.');const width=source.naturalWidth||source.width,height=source.naturalHeight||source.height;
  if(contract)checkTileExportBudget({width,height},contract);const el=document.createElement('canvas');el.width=width;el.height=height;const ctx=el.getContext('2d',{willReadFrequently:true});ctx.drawImage(source,0,0,width,height);return ctx.getImageData(0,0,width,height);
}
async function exportTilePackageZip() {
  const button=$('exportTileZip');if(button)button.disabled=true;try{if(currentAssetFamily()!=='tile')throw new Error('tile export is only available in the tile family');const contract=buildTileContract(),data=await selectedTileImageData(contract),result=buildTileExportPackage(data,contract,currentAssetSubtype()||'tileset');downloadBlob(result.zipBlob,result.zipName);if($('tilePackageSummary'))$('tilePackageSummary').textContent=`PASS · ${result.manifest.tiles.length} tiles · ${result.files.length} files`;return result;}catch(e){if($('tilePackageSummary'))$('tilePackageSummary').textContent=`FAIL · ${e.message}`;setStatus(`타일 ZIP 내보내기 실패: ${e.message}`);throw e;}finally{if(button)button.disabled=false;}
}
async function verifyTilePackageFile(file) {
  const input=$('importTileZip'),button=$('verifyTileZip');if(button)button.disabled=true;try{if(!file)throw new Error('ZIP 파일을 선택하세요.');const result=parseTileExportPackage(new Uint8Array(await file.arrayBuffer()));if($('tilePackageSummary'))$('tilePackageSummary').textContent=`PASS · verified ${result.tilesCompared} tiles · atlas ${result.atlas.width}×${result.atlas.height}`;return result;}catch(e){if($('tilePackageSummary'))$('tilePackageSummary').textContent=`FAIL · ${e.message}`;throw e;}finally{if(button)button.disabled=false;if(input)input.value='';}
}
if($('exportTileZip'))$('exportTileZip').onclick=()=>exportTilePackageZip().catch(()=>{});
if($('verifyTileZip'))$('verifyTileZip').onclick=()=>$('importTileZip')?.click();
if($('importTileZip'))$('importTileZip').onchange=e=>verifyTilePackageFile(e.target.files?.[0]).catch(()=>{});
window.__assetStudioDebug = { ...(window.__assetStudioDebug || {}), buildTileAtlasPreview, buildTileExportPackage, parseTileExportPackage, checkTileExportBudget, exportTilePackageZip, verifyTilePackageFile };
async function objectElementImageData(element){const W=element.naturalWidth||element.width,H=element.naturalHeight||element.height;checkObjectExportBudget({width:W,height:H},{},{states:[]});const c=document.createElement('canvas');c.width=W;c.height=H;const x=c.getContext('2d',{willReadFrequently:true});x.drawImage(element,0,0,W,H);return x.getImageData(0,0,W,H);}
async function exportObjectPackageZip(){const button=$('exportObjectPackageZip');if(button)button.disabled=true;try{if(currentAssetFamily()!=='object')throw new Error('object export is only available in the object family');const object=canvas.getActiveObject(),source=object?._element,metadata=object?.objectFamilyMetadata;if(!source||metadata?.asset_family!=='object')throw new Error('Object result image metadata required');const contract=metadata.family_contract,resultStates=metadata.object_result?.states||[],baseElement=metadata.object_result?.image||source,basePlan={width:baseElement.naturalWidth||baseElement.width,height:baseElement.naturalHeight||baseElement.height},statePlan=resultStates.map(state=>({id:state?.id,imageData:{width:state?.image?.naturalWidth||state?.image?.width,height:state?.image?.naturalHeight||state?.image?.height}})),shadowElement=metadata.object_result?.shadow?.image,shadowPlan=shadowElement?{imageData:{width:shadowElement.naturalWidth||shadowElement.width,height:shadowElement.naturalHeight||shadowElement.height}}:null;checkObjectExportBudget(basePlan,contract,{states:statePlan,icon:{mode:$('objectPreviewIconMode')?.value||'contain',width:64,height:64},shadow:shadowPlan});const normalizedContract=normalizeObjectPreviewContract(contract),base=await objectElementImageData(baseElement);const states=[];for(const state of resultStates)if(state?.image)states.push({id:state.id,imageData:await objectElementImageData(state.image)});const shadow=shadowElement?{imageData:await objectElementImageData(shadowElement)}:null,result=buildObjectExportPackage(base,normalizedContract,{states,icon:{mode:$('objectPreviewIconMode')?.value||'contain',width:64,height:64},shadow});downloadBlob(result.zipBlob,result.zipName);if($('objectExportSummary'))$('objectExportSummary').textContent=`PASS · ${result.manifest.states.length} states · ${result.files.length} files`;return result;}catch(e){if($('objectExportSummary'))$('objectExportSummary').textContent=`FAIL · ${e.message}`;setStatus(`오브젝트 ZIP 내보내기 실패: ${e.message}`);throw e;}finally{if(button)button.disabled=false;}}
if($('exportObjectPackageZip'))$('exportObjectPackageZip').onclick=()=>exportObjectPackageZip().catch(()=>{});
window.__assetStudioDebug={...(window.__assetStudioDebug||{}),checkObjectExportBudget,objectNearestDerivative,buildObjectExportPackage,exportObjectPackageZip};
if ($('buildPixelPrompt')) $('buildPixelPrompt').onclick = syncPixelAssetPrompt;
if ($('generatePixelAsset')) $('generatePixelAsset').onclick = () => { syncPixelAssetPrompt(); generateAiAsset().catch(err => { console.error(err); alert(`도트 에셋 생성 실패: ${err.message}`); setStatus(`도트 에셋 생성 실패: ${err.message}`); }); };
if ($('generateFrontIdleFromSelected')) $('generateFrontIdleFromSelected').onclick = () => generateFrontIdleFromSelected();
if ($('runPixelWorkflow')) $('runPixelWorkflow').onclick = () => runPixelWorkflow().catch(err => { console.error(err); alert(`도트 워크플로우 실패: ${err.message}`); setStatus(`도트 워크플로우 실패: ${err.message}`); });
if ($('runPixelSamplePack')) $('runPixelSamplePack').onclick = () => runPixelSamplePack().catch(err => { console.error(err); alert(`샘플팩 생성 실패: ${err.message}`); setStatus(`샘플팩 생성 실패: ${err.message}`); });
if ($('generate8DirIdle')) $('generate8DirIdle').onclick = () => runDirectionalPixelWorkflow('idle').catch(err => { console.error(err); alert(`8방향 idle 생성 실패: ${err.message}`); setStatus(`8방향 idle 생성 실패: ${err.message}`); });
if ($('generate8DirWalk')) $('generate8DirWalk').onclick = () => runDirectionalPixelWorkflow('walk').catch(err => { console.error(err); alert(`8방향 walk 생성 실패: ${err.message}`); setStatus(`8방향 walk 생성 실패: ${err.message}`); });
if ($('runDirectionalPixelPack')) $('runDirectionalPixelPack').onclick = () => runDirectionalPixelPack().catch(err => { console.error(err); alert(`8방향 통합 생성 실패: ${err.message}`); setStatus(`8방향 통합 생성 실패: ${err.message}`); });
['pixelFrameW','pixelFrameH','pixelAnimationPreset','pixelDirectionMode','pixelTargetDirection','pixelWalkFrames'].forEach(id => {
  if ($(id)) $(id).addEventListener('change', () => {
    if (id === 'pixelAnimationPreset' && $('pixelWalkFrames')) $('pixelWalkFrames').value = String(pixelAnimationDefaultFrames($('pixelAnimationPreset')?.value || 'idle'));
    applyPixelWorkflowGridDefaults();
  });
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
function reportHistoryError(error){console.error(error);setStatus(`히스토리 복원 실패: ${error.message}`);}
const handleHistoryAction=action=>()=>action().catch(reportHistoryError);
$('undoBtn').onclick = handleHistoryAction(undoHistory);
$('redoBtn').onclick = handleHistoryAction(redoHistory);

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
  if(f.size > PROJECT_MAX_BYTES){alert('프로젝트 파일이 허용 크기를 초과했습니다.');e.target.value='';return;}
  const warning = projectSizeWarning(f.size);
  setStatus(`프로젝트 파일 읽는 중... ${f.name} · ${formatBytes(f.size)}${warning ? ' · ' + warning : ''}`);
  const r = new FileReader();
  r.onload = async () => {
    try {
      const project = JSON.parse(r.result);
      await loadProjectFileObject(project);
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

function generateAiAsset() {
  if (assetGenerationInFlight) return assetGenerationInFlight;
  const family = currentAssetFamily();
  const subtype = currentAssetSubtype();
  const corePrompt = ($('assetCorePrompt')?.value || '').trim();
  if (!corePrompt) { alert('생성할 내용을 입력하세요.'); return Promise.resolve(null); }
  const prompt = corePrompt;
  const preset = assetFamilyPreset();
  const aspect = $('aiAspect')?.value || 'square';
  const requestedBackground = $('assetBackground')?.value || 'transparent';
  const backgroundMode = requestedBackground === 'chroma_green' ? 'chroma_green' : 'none';
  const wantedReference = family === 'sprite' && !!$('pixelUseReference')?.checked;
  const selectedReferenceObj = wantedReference ? selectedLayerObject() : null;
  const useReference = !!(wantedReference && selectedReferenceObj && selectedReferenceObj.type === 'image');
  const referenceObj = useReference ? selectedReferenceObj : null;
  const generateBtn = $('familyGenerateAi') || $('generateBtn') || $('generatePixelAsset');
  if (generateBtn) generateBtn.disabled = true;
  setStatus(useReference ? '기준 이미지 기반 AI 에셋 생성 중...' : 'AI 에셋 생성 중...');

  const request = (async () => {
    try {
      const endpoint = useReference ? '/api/generate-reference' : '/api/generate';
      const payload = buildAssetGenerationPayload({ prompt, preset, aspect_ratio: aspect, background_mode: backgroundMode });
      // Temporary flat compatibility remains actor-only. Effects declare only their own sequence mode.
      if (family === 'sprite' && ['character', 'monster', 'npc'].includes(subtype)) {
        const sprite = payload.sprite;
        Object.assign(payload, {
          direction_mode: sprite.direction_mode,
          reference_direction: sprite.reference_direction,
          target_direction: sprite.target_direction,
          animation_mode: sprite.animation_mode,
          frame_count: sprite.frame_count,
          walk_frames: sprite.walk_frames,
          chroma_mode: sprite.chroma_mode,
          no_baked_vfx: sprite.no_baked_vfx,
        });
      }
      if (useReference) payload.reference_image = imageObjectToDataUrl(referenceObj);
      const res = await fetch(endpoint, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || 'generation failed');
      const url = withCacheBust(data.url);
      if ($('pixelQaSummary') && data.qa) {
        const dqa = data.qa.direction_qa || {};
        $('pixelQaSummary').textContent = `QA direction ${dqa.status || 'n/a'} ${dqa.target_direction || ''} slot ${dqa.selected_slot ?? '-'} · alpha ${data.qa.alpha_min}-${data.qa.alpha_max} · corners ${data.qa.corner_alpha?.join('/') || '-'} · green ${data.qa.green_pixels ?? '-'}`;
      }
      const artifacts = Array.isArray(data.artifacts) && data.artifacts.length ? data.artifacts : [{kind:'image',url}];
      const result = createAssetResult({ family:payload.asset_family, type:payload.asset_type, status:'succeeded',
        preview:{url}, sourceRequest:payload, normalizedContract:payload, qaSummary:data.qa || null,
        artifacts, adopted:false, rejected:false, error:null });
      assetResultStore.add(result);
      assetResultStore.select(result.id);
      setStatus(useReference ? `Reference AI generated: ${data.model || ''}` : `AI generated: ${data.model || ''}`);
      return { url, result, data, referenceObj: referenceObj || null };
    } catch (err) {
      setStatus('AI generation failed: ' + err.message);
      throw err;
    } finally {
      if (generateBtn) generateBtn.disabled = false;
    }
  })();
  assetGenerationInFlight = request;
  request.finally(() => {
    if (assetGenerationInFlight === request) assetGenerationInFlight = null;
  }).catch(() => {});
  return request;
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
  const frames = pixelPresetFrameCount(preset);
  const effectFrames = ['static', 'effect_sequence'].includes(preset)
    ? requestedPixelFrameCount()
    : frames;
  const specs = {
    idle: {
      key: 'idle4', label: 'Idle', frames,
      frameOrder: actionFrameBeats('idle', frames),
      motion: 'idle/breathing loop: standing in place, planted feet, same facing/pivot/baseline, small torso/shoulder/head breathing motion only',
      acceptance: actionVisualAcceptanceGate('idle')
    },
    walk4: {
      key: 'walk4', label: 'Walk', frames,
      frameOrder: actionFrameBeats('walk4', frames),
      motion: 'simple RPG walk4: neutral crossover -> LEFT leg swing-cross -> same neutral crossover -> RIGHT leg swing-cross. Frames 1 and 3 repeat the same neutral transition pose with feet close beneath pelvis. In frame 2 the LEFT swing foot travels from behind the planted support leg, passes beside/overlaps it beneath the pelvis, and emerges ahead while the RIGHT stance/support foot stays planted; frame 4 is the exact inverse. Reverse leg front/back depth ordering between frames 2 and 4. For S/front-facing, character LEFT = screen-right and character RIGHT = screen-left: frame 2 swing boot on screen-right, frame 4 swing boot on screen-left. Keep pelvis/root center at exactly 50% of each cell width and identical y. Never swap anatomical side identity or make an X-locked pose. Keep head/torso/contact baseline fixed; held tool stays on the same hand/side',
      acceptance: actionVisualAcceptanceGate('walk4')
    },
    walk6: {
      key: preset === 'walk6' ? 'walk6' : `walk${frames}`, label: 'Walk', frames,
      frameOrder: actionFrameBeats('walk6', frames),
      motion: 'six-phase walk cycle: alternating left/right foot contacts, connected down/passing beats, opposite arm/leg phases, implied locomotion while centered, held tool stays on same hand/side across all frames',
      acceptance: actionVisualAcceptanceGate('walk6')
    },
    attack: {
      key: 'attack4', label: 'Attack', frames,
      frameOrder: actionFrameBeats('attack', frames),
      motion: 'attack: ready stance, readable wind-up, decisive strike pose, recovery toward stance, with body/weapon motion carrying the action',
      acceptance: actionVisualAcceptanceGate('attack')
    },
    jump: {
      key: 'jump4', label: 'Jump', frames,
      frameOrder: actionFrameBeats('jump', frames),
      motion: 'jump: crouch anticipation, takeoff extension, airborne peak with clear vertical lift, landing/recovery while contained in cell',
      acceptance: actionVisualAcceptanceGate('jump')
    },
    cast: {
      key: 'cast4', label: 'Cast', frames,
      frameOrder: actionFrameBeats('cast', frames),
      motion: 'cast: ready stance, gather/anticipation with hands or stance, clear release gesture, recovery; character pose communicates the cast',
      acceptance: actionVisualAcceptanceGate('cast')
    },
    hurt: {
      key: 'hurt4', label: 'Hurt', frames,
      frameOrder: actionFrameBeats('hurt', frames),
      motion: 'hurt reaction: normal pose, impact flinch, recoil away from hit, recovery while preserving facing, identity, palette, and equipment',
      acceptance: actionVisualAcceptanceGate('hurt')
    },
    death: {
      key: 'death4', label: 'Death', frames,
      frameOrder: actionFrameBeats('death', frames),
      motion: 'death/collapse: alive/impact start, collapse in progress, downed body, final dead/still downed pose using the same identity and palette',
      acceptance: actionVisualAcceptanceGate('death')
    },
    static: {
      key: 'static', label: 'Static effect', frames: 1,
      frameOrder: 'one isolated effect frame',
      motion: 'static effect with no animation'
    },
    effect_sequence: {
      key: 'effect_sequence', label: 'Effect sequence', frames: effectFrames,
      frameOrder: `${effectFrames} effect frames in playback order`,
      motion: 'effect-only animation sequence'
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
    if (isPixelEffectAssetType(type)) {
      const effect = buildSpriteContract('effect');
      const generationSemantics = effect.sequence_mode === 'static'
        ? 'Generate exactly one isolated static effect frame.'
        : `Generate exactly ${effect.frame_count} effect frames in a ${effect.rows} row x ${effect.columns} column sprite-sheet grid with ${effect.gap}px gaps.`;
      return `${baseSubject ? baseSubject + '\n\n' : ''}Create an effect-only pixel-art game VFX asset that visually matches the selected reference layer's scale, palette, lighting, and game style.
${generationSemantics}
Use the selected image only as context for what the effect should fit; do not redraw, include, copy, cover, or modify the selected character/monster/object.
Effect-only output: slash, impact spark, magic burst, smoke puff, aura, projectile, hit marker, glow, or particle cluster as requested.
No caster, no target, no character body, no monster body, no object/prop body, no floor, no environment, no UI panel, no text, no numbers, no watermark.
Keep every logical frame in a ${effect.envelope_width}x${effect.envelope_height}px envelope with clean compositing margins.
Refined 32-bit game-ready pixel art, crisp hard pixels, clean silhouette, ${palette}.
Flat exact #00FF00 chroma green background edge-to-edge.`;
    }
    return `${baseSubject ? baseSubject + '\n\n' : ''}Create one static ${type} pixel-art game asset using the selected image only as a visual style/color reference.
No character animation, no directional sheet, no alternate poses, no multiple frames.
No baked VFX: do not include slash arcs, hit sparks, magic glows, particles, smoke, shockwaves, detached debris, motion trails, aura, or background effects.
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
${spec.acceptance ? `${spec.acceptance}\n` : ''}Preserve the same identity, face/species, costume, colors, silhouette, pixel density, outline weight, scale, and pivot across all frames. No color drift between frames.
Refined 32-bit dark fantasy pixel art, crisp hard pixels, clean outline, ${palette}.
Flat exact #00FF00 chroma green background edge-to-edge.
No text, labels, numbers, watermark, mockup frame, scenery, extra characters, multiple rows, contact sheet, or alternate directions.
Background cleanup contract: after removal there must be true transparent background only; no visible rectangular cell boxes, dark/green residue, chroma spill, halo, or fringe around sprites.`;
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
  const effect = isPixelEffectAssetType(type);
  const statusPrefix = actor
    ? `선택 ${type} 기준 ${directionLabel(targetDirection)} ${spec.label} ${spec.frames}프레임`
    : `선택 이미지 스타일 기준 ${type} ${spec.label}`;
  const referenceImage = imageObjectToDataUrl(referenceObj);
  const effectNegative = 'caster, target, character, monster, object body, prop body, floor, environment, UI frame, text, numbers, watermark, white background, full scene, copied reference image';
  const requestPayload = effect
    ? buildAssetGenerationPayload({
        reference_image: referenceImage,
        prompt,
        negative: effectNegative,
        preset: 'effect',
        aspect_ratio: 'square',
        background_mode: 'chroma_green',
        no_baked_vfx: false,
      })
    : {
        reference_image: referenceImage,
        prompt,
        negative: actor ? 'wrong facing direction, alternate directions, turntable, contact sheet, multiple rows, labels, text, numbers, watermark, different character per frame, color drift, costume changes, white background, scenery, cropped feet, malformed limbs, fake walk cycle, same swing foot repeated in both crossing frames, same side boot enlarged/lifted in both crossing frames, legs never pass/cross through each other, static split stance, X-locked crossed legs, anatomical left/right identity swap, four unrelated walk poses, root slide, progressive left/right root drift, hopping, skating, dancing, slash arcs, hit sparks, magic glows, particles, smoke, shockwaves, detached debris, motion trails, aura' : 'animation frames, sprite sheet, character pose sheet, directional views, labels, text, numbers, watermark, white background, scenery, mockup frame, slash arcs, hit sparks, magic glows, particles, smoke, shockwaves, detached debris, motion trails, aura',
        preset: type === 'effect' ? 'effect' : 'pixel',
        aspect_ratio: 'square',
        background_mode: 'chroma_green',
        direction_mode: 'single',
        target_direction: targetDirection,
        reference_direction: referenceDirection,
        animation_mode: spec.key,
        frame_count: spec.frames,
        chroma_mode: $('pixelChromaMode')?.value || 'global',
        asset_type: type,
        no_baked_vfx: true,
      };
  try {
    setStatus(`${statusPrefix} 자동 생성 중...`);
    const res = await fetch('/api/generate-reference', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(requestPayload)
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || 'direction/action generation failed');
    const url = withCacheBust(data.url);
    const resultLabel = actor ? `${targetDirection} ${spec.label} ${spec.frames}f` : `${type} ${preset} ${spec.frames}f`;
    addGallery(url, data.method || data.model || resultLabel);
    const img = await addImageUrl(url, `${resultLabel} - ${nameOf(referenceObj)}`);
    canvas.setActiveObject(img);
    rememberSelectedLayer(img);
    if (effect) applyPixelWorkflowGridDefaults(img);
    else setFrontIdleGridForImage(img, spec.frames);
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
    setStatus(actor ? `${directionLabel(targetDirection)} ${spec.label} ${spec.frames}프레임 자동 생성 완료 · grid/preview 연결됨` : `${type} ${preset} 자동 생성 완료 · ${spec.frames}프레임 그리드 연결됨`);
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

canvas.on('selection:created', () => { if (active() && !canSelectLayer(active())) { canvas.discardActiveObject(); setStatus(active()?.visible === false ? '레이어가 숨김 상태입니다. Show 후 선택하세요.' : '레이어가 잠겨 있습니다. Unlock 후 편집하세요.'); } rememberSelectedLayer(active()); syncProps(); renderLayers(); refreshAiChatState(); syncEffectExportControlsState(); });
canvas.on('selection:updated', () => { if (active() && !canSelectLayer(active())) { canvas.discardActiveObject(); setStatus(active()?.visible === false ? '레이어가 숨김 상태입니다. Show 후 선택하세요.' : '레이어가 잠겨 있습니다. Unlock 후 편집하세요.'); } rememberSelectedLayer(active()); syncProps(); renderLayers(); refreshAiChatState(); syncEffectExportControlsState(); });
canvas.on('selection:cleared', () => { syncProps(); renderLayers(); refreshAiChatState(); syncEffectExportControlsState(); });
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
  if (isUndoKey && e.shiftKey) redoHistory().catch(reportHistoryError);
  else if (isUndoKey) undoHistory().catch(reportHistoryError);
  else if (isRedoKey) redoHistory().catch(reportHistoryError);
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
setAssetFamily('sprite', 'character');
ensureDefaultDrawingLayer();
setupPanelResize();
updateMaskInfo();
updateEmptyCanvasHint();
saveHistory();
fitView();
setStatus('B안 오브젝트 치환 UI 적용됨. Mask로 영역을 잡고 새 오브젝트만 별도 레이어로 생성/배치하세요.');
setWorkspaceMode('ai');
