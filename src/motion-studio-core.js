(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.MotionStudioCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SCHEMA = "asset-studio.motion-manifest/v1";
  const MEDIA_BUDGET_BYTES = 8 * 1024 * 1024;
  const LIMITS = Object.freeze({ states:64, parts:4, frames:256, bones:128, slots:256 });
  const STRATEGIES = ["static", "transform_tween", "state_swap", "rigid_parts", "limited_frames", "full_frames", "rig_paper_doll"];
  const LOOPS = ["loop", "once", "pingpong"];
  const EASINGS = ["linear", "ease_in", "ease_out", "ease_in_out"];
  const ID = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/;
  const SAFE_ASSET_KEY = /^(?![/.])(?!.*(?:^|\/)\.\.(?:\/|$))[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/;
  const DATA_IMAGE = /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/]*={0,2}$/i;
  const own = (o, k) => Object.prototype.hasOwnProperty.call(o || {}, k);
  const plain = value => !!value && typeof value === "object" && !Array.isArray(value);
  const clone = value => JSON.parse(JSON.stringify(value));
  function fail(message) { throw new TypeError(message); }
  function finite(value, name, min, max) { if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max) fail(`${name}: invalid number`); return value; }
  function safeId(value, name) { if (typeof value !== "string" || !ID.test(value)) fail(`${name}: unsafe id`); return value; }
  function point(value, name, width, height) { if (!plain(value)) fail(`${name}: required`); return {x:finite(value.x,`${name}.x`,0,width),y:finite(value.y,`${name}.y`,0,height)}; }
  function byteLength(value) { const text=typeof value === "string" ? value : JSON.stringify(value); return typeof TextEncoder!=="undefined" ? new TextEncoder().encode(text).byteLength : Buffer.byteLength(text,"utf8"); }
  function validMediaUri(uri) { return typeof uri === "string" && (DATA_IMAGE.test(uri) || SAFE_ASSET_KEY.test(uri)); }
  function mediaRefResolved(ref, source) {
    if (ref === "source") return !!source && validMediaUri(source.uri);
    return validMediaUri(ref);
  }
  function validateSource(raw) {
    if (raw === undefined || raw === null) return null;
    if (!plain(raw) || typeof raw.name !== "string" || !raw.name.trim() || raw.name.length > 255 || !validMediaUri(raw.uri)) fail("asset.source: invalid media source");
    return {name:raw.name,uri:raw.uri};
  }
  function validateAsset(raw) {
    if (!plain(raw)) fail("asset: required");
    const canvas=plain(raw.canvas)?raw.canvas:{};
    const width=finite(canvas.width,"canvas.width",1,16384), height=finite(canvas.height,"canvas.height",1,16384);
    if (!Number.isInteger(width)||!Number.isInteger(height)||width*height>67108864) fail("canvas: out of budget");
    const facing=raw.facing===undefined?"right":raw.facing, sampling=raw.sampling===undefined?"nearest":raw.sampling;
    if (!["left","right","up","down","none"].includes(facing)) fail("facing: invalid");
    if (!["nearest","linear"].includes(sampling)) fail("sampling: invalid");
    const asset={id:safeId(raw.id,"asset.id"),canvas:{width,height},pivot:point(raw.pivot,"pivot",width,height),ground:point(raw.ground,"ground",width,height),facing,sampling};
    const source=validateSource(raw.source); if(source) asset.source=source;
    return asset;
  }

  function rigEligibility(gate) {
    const g=plain(gate)?gate:{}, reasons=[];
    if (!(Number.isInteger(g.skins)&&g.skins>=2)) reasons.push("두 개 이상의 스킨이 필요합니다.");
    if (g.equipment!==true) reasons.push("장비 교체 요구가 필요합니다.");
    if (!(Number.isInteger(g.clips)&&g.clips>=3)) reasons.push("세 개 이상의 재사용 클립이 필요합니다.");
    if (g.rest_pose!==true) reasons.push("정규 rest pose가 필요합니다.");
    if (g.adapter!==true) reasons.push("런타임 어댑터가 필요합니다.");
    return {eligible:!reasons.length,reasons};
  }
  function routeStrategy(input) {
    const q=plain(input)?input:{}; let primary,reason;
    if(q.motion!==true){primary="static";reason="동작이 필요하지 않아 정적 자산이 가장 안전합니다.";}
    else if(q.silhouette_change!==true){primary="transform_tween";reason="실루엣 변화 없이 변환만 필요합니다.";}
    else if(q.persistent_states===true){primary="state_swap";reason="지속되는 시각 상태를 교체합니다.";}
    else if(q.contact_changes===true||q.hitbox_changes===true||q.intermediate_silhouettes===true){primary="full_frames";reason="접점, 히트박스 또는 중간 실루엣 변화가 있습니다.";}
    else if(Number.isInteger(q.rigid_parts)&&q.rigid_parts>=1&&q.rigid_parts<=4){primary="rigid_parts";reason="소수의 강체 부품으로 표현할 수 있습니다.";}
    else if(Number.isInteger(q.meaningful_poses)&&q.meaningful_poses>=2&&q.meaningful_poses<=4){primary="limited_frames";reason="2~4개의 의미 있는 포즈면 충분합니다.";}
    else{primary="full_frames";reason="완전한 프레임 제작이 가장 안전합니다.";}
    const gate=rigEligibility(q.rig), alternatives=STRATEGIES.filter(x=>x!==primary&&x!=="rig_paper_doll");
    if(q.rig_candidate===true&&gate.eligible) alternatives.push("rig_paper_doll");
    return {primary,overlays:q.weak_feedback===true?["vfx"]:[],alternatives,promotion:primary==="full_frames"?null:"요구가 복잡해지면 다음 상위 제작법으로 승격하세요.",requires_approval:q.rig_candidate===true&&gate.eligible,reasons:[reason],rig_gate:gate};
  }

  function collection(data,key,max,label,errors) {
    const value=data[key];
    if(!Array.isArray(value)){errors.push(`${label}: 배열이 필요합니다.`);return [];}
    if(value.length>max){errors.push(`${label}: 최대 ${max}개입니다.`);return value.slice(0,max);}
    const out=[]; value.forEach((v,i)=>{if(!plain(v))errors.push(`${label} ${i+1}: 객체가 필요합니다.`);else out.push(v);}); return out;
  }
  function graphErrors(nodes,label,max) {
    const errors=[]; if(!Array.isArray(nodes))return [`${label}: 배열이 필요합니다.`];
    const bounded=nodes.slice(0,max), ids=new Set(), map=new Map();
    for(const n of bounded){if(!plain(n)||typeof n.id!=="string"||!ID.test(n.id)){errors.push(`${label}: 유효한 ID가 필요합니다.`);continue;}if(ids.has(n.id))errors.push(`${label}: ID가 중복됩니다.`);else{ids.add(n.id);map.set(n.id,n.parent??null);}}
    for(const [id,parent] of map){if(parent!==null&&typeof parent!=="string")errors.push(`${label}: 부모 ID가 올바르지 않습니다.`);else if(parent!==null&&!map.has(parent))errors.push(`${label}: 부모 ${parent}가 없습니다.`);let at=parent,steps=0;const seen=new Set([id]);while(at!==null&&map.has(at)&&steps++<=max){if(seen.has(at)){errors.push(`${label}: 순환 그래프입니다.`);break;}seen.add(at);at=map.get(at);}if(steps>max)errors.push(`${label}: 그래프 탐색 한도를 초과했습니다.`);}
    return errors;
  }
  function durationErrors(items,label){const errors=[];items.forEach((x,i)=>{if(!(typeof x.duration==="number"&&Number.isFinite(x.duration)&&x.duration>0&&x.duration<=600000))errors.push(`${label} ${i+1}: 1~600000ms duration이 필요합니다.`);});return errors;}
  function finitePoint(value){return plain(value)&&Number.isFinite(value.x)&&Number.isFinite(value.y)&&Math.abs(value.x)<=16384&&Math.abs(value.y)<=16384;}
  function validateStrategy(strategy,data) {
    try {
      const errors=[],d=plain(data)?data:{};
      if(!STRATEGIES.includes(strategy))errors.push("알 수 없는 primary 전략입니다.");
      if(strategy==="transform_tween"){
        if(!(Number.isFinite(d.duration)&&d.duration>0&&d.duration<=600000))errors.push("1~600000ms duration이 필요합니다.");
        if(!LOOPS.includes(d.loop))errors.push("loop 방식이 올바르지 않습니다.");if(!EASINGS.includes(d.easing))errors.push("easing이 올바르지 않습니다.");if(typeof d.pixel_snap!=="boolean")errors.push("pixel_snap은 boolean이어야 합니다.");
        for(const end of [d.start,d.end])for(const key of ["x","y","rotation","scale","opacity"])if(!plain(end)||!Number.isFinite(end[key]))errors.push(`transform ${key} 값이 필요합니다.`);
      }else if(strategy==="state_swap"){
        const states=collection(d,"states",LIMITS.states,"상태",errors);if(!states.length)errors.push("상태가 하나 이상 필요합니다.");errors.push(...graphErrors(states.map(s=>({id:s.id,parent:null})),"상태",LIMITS.states),...durationErrors(states,"상태"));if(states.filter(s=>s.default===true).length!==1)errors.push("기본 상태는 정확히 하나여야 합니다.");if(states.some(s=>typeof s.default!=="boolean"))errors.push("상태 default는 boolean이어야 합니다.");
      }else if(strategy==="rigid_parts"){
        const parts=collection(d,"parts",LIMITS.parts,"부품",errors);if(parts.length<1||parts.length>4)errors.push("움직이는 강체 부품은 1~4개여야 합니다.");errors.push(...graphErrors(parts,"부품",LIMITS.parts));parts.forEach(p=>{for(const key of ["pivot","socket","offset"])if(!finitePoint(p[key]))errors.push(`부품 ${key} 좌표가 필요합니다.`);if(Number.isFinite(p.rotation_min)&&Number.isFinite(p.rotation_max)&&p.rotation_min>p.rotation_max)errors.push("회전 제한 순서가 잘못되었습니다.");});
      }else if(strategy==="limited_frames"||strategy==="full_frames"){
        const frames=collection(d,"frames",LIMITS.frames,"프레임",errors);if(strategy==="limited_frames"&&(frames.length<2||frames.length>4))errors.push("제한 프레임은 2~4개여야 합니다.");if(strategy==="full_frames"&&!frames.length)errors.push("전체 프레임이 하나 이상 필요합니다.");errors.push(...graphErrors(frames.map(f=>({id:f.id,parent:null})),"프레임",LIMITS.frames),...durationErrors(frames,"프레임"));if(!LOOPS.includes(d.loop))errors.push("loop 방식이 올바르지 않습니다.");
      }else if(strategy==="rig_paper_doll"){
        const gate=rigEligibility(d.gate);if(!gate.eligible)errors.push(...gate.reasons);if(d.approved!==true)errors.push("명시적 rig 활성화 승인이 필요합니다.");const bones=collection(d,"bones",LIMITS.bones,"bone",errors),slots=collection(d,"slots",LIMITS.slots,"slot",errors);if(!bones.length)errors.push("bone이 하나 이상 필요합니다.");errors.push(...graphErrors(bones,"bone",LIMITS.bones));const ids=new Set(bones.filter(b=>ID.test(b.id||"")).map(b=>b.id));slots.forEach(s=>{if(!ID.test(s.id||"")||!ids.has(s.bone))errors.push("slot은 유효한 ID와 bone이 필요합니다.");});
      }
      return {valid:!errors.length,errors:Array.from(new Set(errors)).sort()};
    } catch (_) { return {valid:false,errors:["전략 데이터가 손상되었습니다."]}; }
  }
  function validateVfx(vfx){try{if(!plain(vfx)||vfx.enabled!==true)return {valid:true,errors:[]};const errors=[];if(!ID.test(vfx.trigger||""))errors.push("VFX trigger가 필요합니다.");if(!ID.test(vfx.anchor||""))errors.push("VFX anchor가 필요합니다.");if(!finitePoint(vfx.offset))errors.push("VFX offset은 유한한 ±16384 좌표여야 합니다.");if(!(Number.isFinite(vfx.duration)&&vfx.duration>0&&vfx.duration<=600000))errors.push("VFX duration은 1~600000ms여야 합니다.");if(!Number.isSafeInteger(vfx.seed))errors.push("VFX seed는 안전한 정수여야 합니다.");if(!["normal","add","multiply","screen"].includes(vfx.blend))errors.push("VFX blend가 올바르지 않습니다.");return {valid:!errors.length,errors:errors.sort()};}catch(_){return {valid:false,errors:["VFX 데이터가 손상되었습니다."]};}}

  function normalizeManifest(raw){
    if(!plain(raw))fail("manifest: object required");
    let source;try{source=clone(raw);}catch(_){fail("manifest: JSON-safe value required");}
    if(byteLength(source)>MEDIA_BUDGET_BYTES)fail("manifest: 8 MiB media budget exceeded");
    const primary=plain(source.primary)?source.primary:{};if(!STRATEGIES.includes(primary.strategy))fail("primary.strategy: unknown");
    if(primary.strategy==="transform_tween"&&own(primary.data,"pixel_snap")&&typeof primary.data.pixel_snap!=="boolean")fail("pixel_snap: boolean required");
    const overlays=source.overlays===undefined?[]:source.overlays;if(!Array.isArray(overlays)||overlays.length>16)fail("overlays: array required");if(overlays.some(v=>!plain(v)||v.type!=="vfx"))fail("overlay: only vfx supported");
    return {schema:SCHEMA,asset:validateAsset(source.asset),primary:{strategy:primary.strategy,data:clone(plain(primary.data)?primary.data:{})},overlays:clone(overlays),manual_visual_approval:source.manual_visual_approval===true};
  }
  function phase(time,duration,loop){const t=Math.max(0,Number.isFinite(time)?time:0);if(!(duration>0))return 0;if(loop==="once")return Math.min(t,duration);if(loop==="pingpong"){const p=t%(duration*2);return p<=duration?p:duration*2-p;}return t%duration;}
  function easing(name,t){if(name==="ease_in")return t*t;if(name==="ease_out")return 1-(1-t)*(1-t);if(name==="ease_in_out")return t*t*(3-2*t);return t;}
  function sampleTransform(data,time){const duration=data.duration,p=easing(data.easing,phase(time,duration,data.loop)/duration),out={progress:p};for(const key of ["x","y","rotation","scale","opacity"])out[key]=data.start[key]+(data.end[key]-data.start[key])*p;if(data.pixel_snap){out.x=Math.round(out.x);out.y=Math.round(out.y);}return out;}
  function sampleFrameClip(data,time){const frames=Array.isArray(data.frames)?data.frames:[],total=frames.reduce((n,f)=>n+(Number.isFinite(f?.duration)?f.duration:0),0);if(!frames.length||!(total>0))return {index:-1,id:null,elapsed:0,image_ref:null};let t=phase(time,total,data.loop),index=frames.length-1,cursor=0;for(let i=0;i<frames.length;i++){if(t<cursor+frames[i].duration){index=i;break;}cursor+=frames[i].duration;}return {index,id:frames[index].id,elapsed:t-cursor,image_ref:frames[index].image_ref||null};}
  function clipDuration(strategy,data){const d=plain(data)?data:{};if(strategy==="transform_tween")return Number.isFinite(d.duration)&&d.duration>0?d.duration:1000;if(strategy==="state_swap")return (Array.isArray(d.states)?d.states:[]).reduce((n,x)=>n+(Number.isFinite(x?.duration)&&x.duration>0?x.duration:0),0)||1000;if(strategy==="limited_frames"||strategy==="full_frames")return (Array.isArray(d.frames)?d.frames:[]).reduce((n,x)=>n+(Number.isFinite(x?.duration)&&x.duration>0?x.duration:0),0)||1000;return 1000;}
  function samplePreview(manifest,time,options){const p=manifest.primary,scene={strategy:p.strategy,time:Math.max(0,Number.isFinite(time)?time:0),transform:{x:0,y:0,rotation:0,scale:1,opacity:1},frame:null,state:null,parts:[],slots:[],vfx:[]};if(p.strategy==="transform_tween")scene.transform=sampleTransform(p.data,time);if(p.strategy==="limited_frames"||p.strategy==="full_frames")scene.frame=sampleFrameClip(p.data,time);if(p.strategy==="state_swap"){const states=Array.isArray(p.data.states)?p.data.states:[],total=states.reduce((n,s)=>n+(Number.isFinite(s.duration)?s.duration:0),0);let t=phase(time,total,"loop"),cursor=0;scene.state=states.find(s=>{cursor+=s.duration;return t<cursor;})||states.find(s=>s.default)||states[0]||null;}if(p.strategy==="rigid_parts")scene.parts=(Array.isArray(p.data.parts)?p.data.parts:[]).map((part,i)=>{const lo=Number.isFinite(part.rotation_min)?part.rotation_min:0,hi=Number.isFinite(part.rotation_max)?part.rotation_max:lo,wave=(Math.sin((Math.max(0,time)/1000+i)*Math.PI*2)+1)/2;return{id:part.id,parent:part.parent??null,image_ref:part.image_ref||null,rotation:lo+(hi-lo)*wave,offset:part.offset||{x:0,y:0},pivot:part.pivot||{x:0,y:0},socket:part.socket||{x:0,y:0}};});if(p.strategy==="rig_paper_doll"){const bones=Array.isArray(p.data.bones)?p.data.bones:[];scene.slots=(Array.isArray(p.data.slots)?p.data.slots:[]).map(slot=>({id:slot.id,bone:slot.bone,image_ref:slot.image_ref||null,boneTransform:bones.find(b=>b.id===slot.bone)||{x:0,y:0,rotation:0}}));}if(options&&options.vfx)(manifest.overlays||[]).filter(v=>v&&v.enabled!==false&&v.type==="vfx"&&v.duration>0).forEach(v=>{for(let i=0;i<6;i++)scene.vfx.push({x:v.offset.x+(((v.seed*17+i*23+Math.floor(time/40))%41+41)%41-20),y:v.offset.y-((i*11+Math.floor(time/30))%31),alpha:1-(time%v.duration)/v.duration,blend:v.blend});});return scene;}
  function mediaErrors(manifest){const errors=[],source=manifest.asset.source;if(!source||!validMediaUri(source.uri))errors.push("정규 source 이미지가 필요합니다.");const d=manifest.primary.data||{},check=(items,label)=>items.forEach((x,i)=>{if(!plain(x)||!mediaRefResolved(x.image_ref,source))errors.push(`${label} ${i+1}: 확인 가능한 image_ref가 필요합니다.`);});if(manifest.primary.strategy==="state_swap")check(Array.isArray(d.states)?d.states:[],"상태");if(manifest.primary.strategy==="rigid_parts")check(Array.isArray(d.parts)?d.parts:[],"부품");if(["limited_frames","full_frames"].includes(manifest.primary.strategy))check(Array.isArray(d.frames)?d.frames:[],"프레임");if(manifest.primary.strategy==="rig_paper_doll")check(Array.isArray(d.slots)?d.slots:[],"slot");return errors;}
  function runQA(manifest,options){let canonical;try{canonical=normalizeManifest(manifest);}catch(error){return{status:"FAIL",reasons:[String(error&&error.message||"manifest invalid")]};}try{const result=validateStrategy(canonical.primary.strategy,canonical.primary.data),reasons=result.errors.concat(mediaErrors(canonical));let status=reasons.length?"FAIL":"WARN";for(const enabled of canonical.overlays.filter(v=>v&&v.type==="vfx"&&v.enabled!==false)){const vv=validateVfx(enabled);if(!vv.valid){status="FAIL";reasons.push(...vv.errors);}else if(options&&options.vfx_off){if(enabled.required_for_readability===true){status="FAIL";reasons.push("VFX를 끄면 동작을 읽을 수 없습니다.");}else if(status!=="FAIL")reasons.push("VFX를 끈 상태에서도 동작 가독성을 확인하세요.");}}if(status!=="FAIL"){if(canonical.manual_visual_approval)status="PASS";else reasons.push("자동 검사는 아트 품질을 보증하지 않습니다. 미리보기를 직접 확인하고 시각 승인하세요.");}return{status,reasons:Array.from(new Set(reasons)).sort()};}catch(_){return{status:"FAIL",reasons:["QA 입력이 손상되었습니다."]};}}
  function stableValue(value){if(Array.isArray(value))return value.map(stableValue);if(plain(value))return Object.keys(value).sort().reduce((o,k)=>{o[k]=stableValue(value[k]);return o;},{});return value;}
  function stableStringify(value){return JSON.stringify(stableValue(value),null,2);}
  function importManifest(text){if(typeof text!=="string"||byteLength(text)>MEDIA_BUDGET_BYTES)fail("manifest: 8 MiB file limit exceeded");let parsed;try{parsed=JSON.parse(text);}catch(_){fail("manifest: invalid JSON");}if(parsed.schema!==SCHEMA)fail("manifest: unsupported schema");const m=normalizeManifest(parsed),qa=runQA(m);if(qa.status==="FAIL")fail(qa.reasons.join(" "));return m;}
  return {SCHEMA,MEDIA_BUDGET_BYTES,LIMITS,STRATEGIES:STRATEGIES.slice(),validMediaUri,normalizeManifest,routeStrategy,rigEligibility,validateStrategy,validateVfx,sampleTransform,sampleFrameClip,clipDuration,samplePreview,runQA,stableStringify,importManifest};
});
