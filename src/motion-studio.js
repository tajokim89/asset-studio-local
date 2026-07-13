(function () {
  "use strict";
  const Core = window.MotionStudioCore;
  if (!Core) return;

  const $ = id => document.getElementById(id);
  const STORAGE_KEY = "asset-studio.motion-draft/v1";
  const TIERS = Core.STRATEGIES;
  const MAX_FILE_BYTES = Core.MEDIA_BUDGET_BYTES;
  const IMAGE_TYPES = /^image\/(png|jpeg|webp)$/;
  const clone = value => JSON.parse(JSON.stringify(value));
  const plain = value => !!value && typeof value === "object" && !Array.isArray(value);
  const number = id => Number($(id).value);
  const checked = id => $(id).checked;
  const status = text => { $("motionStatus").textContent = text; };
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));

  const defaults = () => ({
    tier: "static",
    imageName: "",
    sourceDataUrl: "",
    time: 0,
    manualVisualApproval: false,
    drafts: {
      static: {},
      transform_tween: {start:{x:0,y:0,rotation:0,scale:1,opacity:1},end:{x:8,y:0,rotation:0,scale:1,opacity:1},duration:800,easing:"ease_in_out",loop:"loop",pixel_snap:true},
      state_swap: {states:[{id:"idle",image_ref:"source",image_name:"source",default:true,duration:500}]},
      rigid_parts: {duration:1000,loop:"pingpong",parts:[{id:"part_1",parent:null,image_ref:"source",image_name:"source",pivot:{x:0,y:0},socket:{x:0,y:0},offset:{x:0,y:0},rotation_min:-15,rotation_max:15}]},
      limited_frames: {loop:"loop",frames:[{id:"pose_1",image_ref:"source",image_name:"source",duration:160,phase:"start",event:""},{id:"pose_2",image_ref:"source",image_name:"source",duration:160,phase:"contact",event:""}]},
      full_frames: {loop:"loop",frames:[{id:"frame_1",image_ref:"source",image_name:"source",duration:100,phase:"",event:""}]},
      rig_paper_doll: {approved:false,gate:{skins:0,equipment:false,clips:0,rest_pose:false,adapter:false},bones:[{id:"root",parent:null,x:0,y:0,rotation:0}],slots:[{id:"body",bone:"root",image_ref:"source",image_name:"source"}]}
    }
  });

  let state = defaults();
  let sourceImage = null;
  let playing = false;
  let playOrigin = 0;
  let playStart = 0;
  let lastRecommendation = null;
  const imageCache = new Map();

  function deepMerge(base, incoming) {
    if (!plain(incoming)) return clone(base);
    const out = clone(base);
    for (const [key, value] of Object.entries(incoming)) {
      if (Array.isArray(value)) out[key] = clone(value);
      else if (plain(value) && plain(out[key])) out[key] = deepMerge(out[key], value);
      else out[key] = value;
    }
    return out;
  }

  function invalidateMotionQa() {
    $("motionExport").disabled = true;
    $("motionQaResult").removeAttribute("data-status");
    $("motionQaResult").textContent = "설정이 변경되었습니다. QA를 다시 실행하세요.";
  }

  function setWorkspace(name) {
    const motion = name === "motion";
    document.querySelector(".app").classList.toggle("motion-mode", motion);
    $("motionStudioWorkspace").hidden = !motion;
    document.querySelectorAll("#studioWorkspaceSwitch button").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.studioWorkspace === name)));
    if (motion) render();
  }

  function imageForRef(ref) {
    const uri = ref === "source" ? state.sourceDataUrl : ref;
    if (!uri || !Core.validMediaUri(uri)) return null;
    if (imageCache.has(uri)) return imageCache.get(uri);
    const img = new Image();
    imageCache.set(uri, img);
    img.onload = () => render();
    img.onerror = () => { imageCache.delete(uri); status("미디어 참조를 읽을 수 없습니다."); };
    img.src = uri;
    return img;
  }

  function readImageFile(file) {
    return new Promise((resolve, reject) => {
      if (!file || !IMAGE_TYPES.test(file.type)) return reject(new TypeError("PNG/JPG/WebP만 지원합니다."));
      if (file.size > MAX_FILE_BYTES) return reject(new TypeError("이미지는 8 MiB 이하여야 합니다."));
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error || new Error("이미지를 읽을 수 없습니다."));
      reader.readAsDataURL(file);
    });
  }

  async function useImage(file) {
    try {
      status("이미지 읽는 중…");
      const dataUrl = await readImageFile(file);
      state.sourceDataUrl = dataUrl;
      state.imageName = file.name;
      sourceImage = imageForRef("source");
      await new Promise((resolve, reject) => {
        if (sourceImage.complete && sourceImage.naturalWidth) return resolve();
        sourceImage.addEventListener("load", resolve, {once:true});
        sourceImage.addEventListener("error", reject, {once:true});
      });
      $("motionCanvasW").value = sourceImage.naturalWidth;
      $("motionCanvasH").value = sourceImage.naturalHeight;
      $("motionPivotX").value = Math.floor(sourceImage.naturalWidth / 2);
      $("motionPivotY").value = Math.floor(sourceImage.naturalHeight / 2);
      $("motionGroundX").value = Math.floor(sourceImage.naturalWidth / 2);
      $("motionGroundY").value = Math.max(0, sourceImage.naturalHeight - 1);
      status(`${file.name} 로드 완료`);
      invalidateMotionQa(); updateManifest(); render(); saveDraft();
    } catch (error) { status(error.message || "이미지를 읽을 수 없습니다."); }
  }

  function transformEditor() {
    const d = state.drafts.transform_tween;
    const field = (label, path, value, attrs="") => `<label>${label}<input data-transform="${path}" type="number" value="${esc(value)}" ${attrs}></label>`;
    $("motionTransformEditor").innerHTML = ["x","y","rotation","scale","opacity"].map(key => field(`시작 ${key}`,`start.${key}`,d.start[key],key==="opacity"?'min="0" max="1" step=".05"':'step=".1"')).join("")
      + ["x","y","rotation","scale","opacity"].map(key => field(`끝 ${key}`,`end.${key}`,d.end[key],key==="opacity"?'min="0" max="1" step=".05"':'step=".1"')).join("")
      + field("Duration ms","duration",d.duration,'min="1" max="600000"')
      + `<label>Easing<select data-transform="easing">${["linear","ease_in","ease_out","ease_in_out"].map(x=>`<option ${x===d.easing?"selected":""}>${x}</option>`).join("")}</select></label>`
      + `<label>Loop<select data-transform="loop">${["loop","once","pingpong"].map(x=>`<option ${x===d.loop?"selected":""}>${x}</option>`).join("")}</select></label>`
      + `<label class="checkline"><input data-transform="pixel_snap" type="checkbox" ${d.pixel_snap?"checked":""}> 픽셀 스냅</label>`;
  }

  function mediaInput(kind, index, item) {
    const label = item.image_ref === "source" ? "source 사용" : item.image_name ? `업로드: ${esc(item.image_name)}` : "미디어 없음";
    return `<label class="motion-media-field">${label}<input aria-label="${esc(kind)} 이미지" data-media-kind="${kind}" data-index="${index}" type="file" accept="image/png,image/jpeg,image/webp"></label>`;
  }

  function rowHtml(kind, item, index) {
    const del = `<button type="button" data-delete-row="${kind}" data-index="${index}" aria-label="${esc(kind)} ${index+1} 삭제">×</button>`;
    if (kind === "state") return `<div class="motion-row"><input aria-label="상태 ID" data-row="state" data-index="${index}" data-key="id" value="${esc(item.id)}"><input aria-label="이미지 참조" data-row="state" data-index="${index}" data-key="image_ref" value="${item.image_ref?.startsWith("data:")?"":esc(item.image_ref)}" placeholder="source 또는 asset/key.png">${mediaInput(kind,index,item)}<label class="checkline"><input type="checkbox" data-row="state" data-index="${index}" data-key="default" ${item.default?"checked":""}>기본</label><input aria-label="duration" type="number" min="1" max="600000" data-row="state" data-index="${index}" data-key="duration" value="${esc(item.duration||100)}">${del}</div>`;
    if (kind === "part") return `<div class="motion-row"><input aria-label="부품 ID" data-row="part" data-index="${index}" data-key="id" value="${esc(item.id)}"><input aria-label="부모 ID" data-row="part" data-index="${index}" data-key="parent" value="${esc(item.parent||"")}" placeholder="부모">${mediaInput(kind,index,item)}<input aria-label="pivot x,y" data-row="part" data-index="${index}" data-key="pivot" value="${item.pivot?.x||0},${item.pivot?.y||0}"><input aria-label="socket x,y" data-row="part" data-index="${index}" data-key="socket" value="${item.socket?.x||0},${item.socket?.y||0}"><input aria-label="offset x,y" data-row="part" data-index="${index}" data-key="offset" value="${item.offset?.x||0},${item.offset?.y||0}"><input aria-label="최소 회전" type="number" data-row="part" data-index="${index}" data-key="rotation_min" value="${esc(item.rotation_min||0)}"><input aria-label="최대 회전" type="number" data-row="part" data-index="${index}" data-key="rotation_max" value="${esc(item.rotation_max||0)}">${del}</div>`;
    if (kind === "limited" || kind === "full") return `<div class="motion-row"><input aria-label="프레임 ID" data-row="${kind}" data-index="${index}" data-key="id" value="${esc(item.id)}"><input aria-label="duration" type="number" min="1" max="600000" data-row="${kind}" data-index="${index}" data-key="duration" value="${esc(item.duration||100)}"><input aria-label="phase" data-row="${kind}" data-index="${index}" data-key="phase" value="${esc(item.phase||"")}" placeholder="phase"><input aria-label="event" data-row="${kind}" data-index="${index}" data-key="event" value="${esc(item.event||"")}" placeholder="event">${mediaInput(kind,index,item)}<button type="button" data-move-row="${kind}" data-index="${index}" data-direction="-1" aria-label="프레임 ${index+1} 위로 이동">↑</button><button type="button" data-move-row="${kind}" data-index="${index}" data-direction="1" aria-label="프레임 ${index+1} 아래로 이동">↓</button>${del}</div>`;
    if (kind === "bone") return `<div class="motion-row"><input aria-label="Bone ID" data-row="bone" data-index="${index}" data-key="id" value="${esc(item.id)}"><input aria-label="부모 Bone" data-row="bone" data-index="${index}" data-key="parent" value="${esc(item.parent||"")}"><input aria-label="Bone X" type="number" data-row="bone" data-index="${index}" data-key="x" value="${esc(item.x||0)}"><input aria-label="Bone Y" type="number" data-row="bone" data-index="${index}" data-key="y" value="${esc(item.y||0)}"><input aria-label="Bone rotation" type="number" data-row="bone" data-index="${index}" data-key="rotation" value="${esc(item.rotation||0)}">${del}</div>`;
    return `<div class="motion-row"><input aria-label="Slot ID" data-row="slot" data-index="${index}" data-key="id" value="${esc(item.id)}"><input aria-label="Bone ID" data-row="slot" data-index="${index}" data-key="bone" value="${esc(item.bone)}">${mediaInput(kind,index,item)}${del}</div>`;
  }

  function loopField(kind, data) {
    return `<label>Loop<select data-clip-loop="${kind}">${["loop","once","pingpong"].map(x=>`<option ${x===data.loop?"selected":""}>${x}</option>`).join("")}</select></label>`;
  }

  function renderRows() {
    $("motionStateRows").innerHTML = state.drafts.state_swap.states.map((x,i)=>rowHtml("state",x,i)).join("");
    $("motionPartRows").innerHTML = loopField("rigid",state.drafts.rigid_parts) + state.drafts.rigid_parts.parts.map((x,i)=>rowHtml("part",x,i)).join("");
    $("motionLimitedRows").innerHTML = loopField("limited",state.drafts.limited_frames) + state.drafts.limited_frames.frames.map((x,i)=>rowHtml("limited",x,i)).join("");
    $("motionFullRows").innerHTML = loopField("full",state.drafts.full_frames) + state.drafts.full_frames.frames.map((x,i)=>rowHtml("full",x,i)).join("");
    $("motionBoneRows").innerHTML = state.drafts.rig_paper_doll.bones.map((x,i)=>rowHtml("bone",x,i)).join("");
    $("motionSlotRows").innerHTML = state.drafts.rig_paper_doll.slots.map((x,i)=>rowHtml("slot",x,i)).join("");
  }

  function syncRig() {
    const d = state.drafts.rig_paper_doll;
    $("motionRigSkins").value=d.gate.skins; $("motionRigClips").value=d.gate.clips;
    $("motionRigEquipment").checked=d.gate.equipment; $("motionRigRest").checked=d.gate.rest_pose;
    $("motionRigAdapter").checked=d.gate.adapter; $("motionRigApproval").checked=d.approved;
    const gate=Core.rigEligibility(d.gate), button=document.querySelector('[data-motion-tier="rig_paper_doll"]');
    button.disabled=!(gate.eligible&&d.approved);
    button.title=button.disabled?gate.reasons.join(" "):"Rig 편집 가능";
  }

  function selectTier(tier, focus=false) {
    if (!TIERS.includes(tier)) return;
    const tab=document.querySelector(`[data-motion-tier="${tier}"]`); if (!tab || tab.disabled) return;
    state.tier=tier; state.time=0;
    document.querySelectorAll("[data-motion-tier]").forEach(button=>{const on=button.dataset.motionTier===tier;button.setAttribute("aria-selected",String(on));button.tabIndex=on?0:-1;});
    document.querySelectorAll("[data-motion-editor]").forEach(panel=>panel.hidden=panel.dataset.motionEditor!==tier);
    if(focus)tab.focus(); invalidateMotionQa(); updateManifest(); render(); saveDraft();
  }

  function buildManifest() {
    const overlays=[];
    if(checked("motionVfxEnabled")) overlays.push({type:"vfx",enabled:true,trigger:$("motionVfxTrigger").value,anchor:$("motionVfxAnchor").value,offset:{x:number("motionVfxX"),y:number("motionVfxY")},duration:number("motionVfxDuration"),blend:$("motionVfxBlend").value,seed:number("motionVfxSeed")});
    const asset={id:$("motionAssetId").value,canvas:{width:number("motionCanvasW"),height:number("motionCanvasH")},pivot:{x:number("motionPivotX"),y:number("motionPivotY")},ground:{x:number("motionGroundX"),y:number("motionGroundY")},facing:$("motionFacing").value,sampling:$("motionSampling").value};
    if(state.sourceDataUrl)asset.source={name:state.imageName||"source",uri:state.sourceDataUrl};
    return Core.normalizeManifest({asset,primary:{strategy:state.tier,data:state.drafts[state.tier]},overlays,manual_visual_approval:checked("motionManualApproval")});
  }

  function updateManifest() {
    try { $("motionManifestPreview").textContent=Core.stableStringify(buildManifest()); }
    catch(error){$("motionManifestPreview").textContent=`오류: ${error.message}`;$("motionExport").disabled=true;}
  }

  function route() {
    const fd=new FormData($("motionRouterForm")),q={};
    ["motion","silhouette_change","persistent_states","contact_changes","weak_feedback"].forEach(key=>q[key]=fd.has(key));
    q.rigid_parts=Number(fd.get("rigid_parts"));q.meaningful_poses=Number(fd.get("meaningful_poses"));
    lastRecommendation=Core.routeStrategy(q);
    $("motionRecommendation").innerHTML=`<strong>추천: ${esc(lastRecommendation.primary)}</strong><br>${esc(lastRecommendation.reasons.join(" "))}${lastRecommendation.overlays.length?"<br>보조 VFX 권장":""}`;
  }

  function runQA() {
    try {
      const qa=Core.runQA(buildManifest(),{vfx_off:!checked("motionVfxPreview")});
      $("motionQaResult").dataset.status=qa.status;
      $("motionQaResult").textContent=`${qa.status}${qa.reasons.length?" · "+qa.reasons.join(" · "):" · 요구사항 충족"}`;
      $("motionExport").disabled=qa.status==="FAIL";
      updateManifest(); return qa;
    } catch(error){$("motionQaResult").dataset.status="FAIL";$("motionQaResult").textContent=`FAIL · ${error.message}`;$("motionExport").disabled=true;return{status:"FAIL"};}
  }

  function currentDuration(manifest) {
    const base=Core.clipDuration(manifest.primary.strategy,manifest.primary.data);
    const loop=manifest.primary.data?.loop;
    return Math.max(1,loop==="pingpong"?base*2:base);
  }

  function renderTimeline(manifest,duration) {
    const data=manifest.primary.data||{},items=manifest.primary.strategy==="state_swap"?data.states:(["limited_frames","full_frames"].includes(manifest.primary.strategy)?data.frames:[]);
    if(!Array.isArray(items)||!items.length){$("motionTimeline").innerHTML=`<span class="motion-timeline-segment" style="width:100%">${esc(manifest.primary.strategy)} · ${duration}ms</span>`;return;}
    const total=items.reduce((n,item)=>n+(Number(item.duration)||0),0)||1;
    $("motionTimeline").innerHTML=items.map(item=>`<span class="motion-timeline-segment" style="width:${Math.max(4,(item.duration/total)*100)}%">${esc(item.id)}<small>${esc(item.event||item.phase||"")}</small></span>`).join("");
  }

  function drawMedia(ctx,img,x,y,zoom,pivot,rotation=0) {
    if(!img||!img.complete||!img.naturalWidth)return;
    ctx.save();ctx.translate(x,y);ctx.rotate(rotation*Math.PI/180);ctx.drawImage(img,-(pivot?.x||0)*zoom,-(pivot?.y||0)*zoom,img.naturalWidth*zoom,img.naturalHeight*zoom);ctx.restore();
  }

  function drawRigidParts(ctx,scene,cx,cy,zoom) {
    const map=new Map(scene.parts.map(part=>[part.id,part])),drawn=new Set();
    const draw=part=>{if(drawn.has(part.id))return;const parent=part.parent?map.get(part.parent):null;if(parent)draw(parent);let x=cx+part.offset.x*zoom,y=cy+part.offset.y*zoom,rotation=part.rotation;if(parent){x+=parent.offset.x*zoom+parent.socket.x*zoom;y+=parent.offset.y*zoom+parent.socket.y*zoom;rotation+=parent.rotation;}drawMedia(ctx,imageForRef(part.image_ref),x,y,zoom,part.pivot,rotation);drawn.add(part.id);};
    scene.parts.forEach(draw);
  }

  function render() {
    let manifest;try{manifest=buildManifest();}catch(_){return;}
    const canvas=$("motionPreviewCanvas"),ctx=canvas.getContext("2d"),scene=Core.samplePreview(manifest,state.time,{vfx:checked("motionVfxPreview")});
    const zoom=Number($("motionZoom").value),cx=canvas.width/2,cy=canvas.height/2,duration=currentDuration(manifest);
    $("motionScrubber").max=String(duration);if(state.time>duration)state.time=duration;
    ctx.clearRect(0,0,canvas.width,canvas.height);ctx.imageSmoothingEnabled=manifest.asset.sampling==="linear";
    const selectedRef=scene.frame?.image_ref||scene.state?.image_ref||"source",img=imageForRef(selectedRef);
    if(manifest.primary.strategy==="rigid_parts")drawRigidParts(ctx,scene,cx,cy,zoom);
    else if(manifest.primary.strategy==="rig_paper_doll")scene.slots.forEach(slot=>{const b=slot.boneTransform||{};drawMedia(ctx,imageForRef(slot.image_ref),cx+(b.x||0)*zoom,cy+(b.y||0)*zoom,zoom,{x:0,y:0},b.rotation||0);});
    else {
      ctx.save();ctx.translate(cx+scene.transform.x*zoom,cy+scene.transform.y*zoom);ctx.rotate(scene.transform.rotation*Math.PI/180);ctx.scale((manifest.asset.facing==="left"?-1:1)*scene.transform.scale,scene.transform.scale);ctx.globalAlpha=scene.transform.opacity;
      if(img&&img.complete&&img.naturalWidth)ctx.drawImage(img,-manifest.asset.pivot.x*zoom,-manifest.asset.pivot.y*zoom,img.naturalWidth*zoom,img.naturalHeight*zoom);
      else{ctx.fillStyle="#5f7fb8";ctx.fillRect(-32,-32,64,64);ctx.fillStyle="#cfe1ff";ctx.fillText("MEDIA REQUIRED",-48,4);}ctx.restore();
    }
    ctx.strokeStyle="#ff5b82";ctx.beginPath();ctx.moveTo(cx-7,cy);ctx.lineTo(cx+7,cy);ctx.moveTo(cx,cy-7);ctx.lineTo(cx,cy+7);ctx.stroke();
    const gx=cx+(manifest.asset.ground.x-manifest.asset.pivot.x)*zoom,gy=cy+(manifest.asset.ground.y-manifest.asset.pivot.y)*zoom;ctx.strokeStyle="#62e09b";ctx.beginPath();ctx.moveTo(gx-12,gy);ctx.lineTo(gx+12,gy);ctx.stroke();
    for(const particle of scene.vfx){ctx.save();ctx.globalAlpha=Math.max(0,particle.alpha);ctx.globalCompositeOperation={add:"lighter",screen:"screen",multiply:"multiply",normal:"source-over"}[particle.blend]||"source-over";ctx.fillStyle="#78d9ff";ctx.fillRect(cx+particle.x,cy+particle.y,3,3);ctx.restore();}
    const label=scene.frame?.id||scene.state?.id||scene.strategy;$("motionPreviewLabel").textContent=String(label).toUpperCase();$("motionTime").textContent=`${Math.round(state.time)} / ${duration} ms`;$("motionScrubber").value=String(Math.min(duration,state.time));renderTimeline(manifest,duration);
  }

  function tick(now){if(!playing)return;let manifest;try{manifest=buildManifest();}catch(_){playing=false;return;}const duration=currentDuration(manifest),loop=manifest.primary.data?.loop||"loop";state.time=playOrigin+(now-playStart);if(state.time>=duration){if(loop==="once"){state.time=duration;playing=false;render();return;}state.time%=duration;playOrigin=state.time;playStart=now;}render();requestAnimationFrame(tick);}

  async function bindRowImage(file,kind,index){try{const dataUrl=await readImageFile(file),map={state:["state_swap","states"],part:["rigid_parts","parts"],limited:["limited_frames","frames"],full:["full_frames","frames"],slot:["rig_paper_doll","slots"]},spec=map[kind],item=state.drafts[spec[0]][spec[1]][index];item.image_ref=dataUrl;item.image_name=file.name;imageForRef(dataUrl);renderRows();invalidateMotionQa();updateManifest();render();saveDraft();status(`${file.name} 바인딩 완료`);}catch(error){status(error.message);}}

  function exportJson(){if(runQA().status==="FAIL")return;const blob=new Blob([Core.stableStringify(buildManifest())+"\n"],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=`${$("motionAssetId").value}.motion.json`;a.click();URL.revokeObjectURL(url);status("Manifest를 내보냈습니다.");}

  function importJson(file){if(!file)return;if(file.size>MAX_FILE_BYTES){status("가져오기 실패: 8 MiB 파일 제한을 초과했습니다.");return;}status("Manifest 읽는 중…");const reader=new FileReader();reader.onload=()=>{try{const m=Core.importManifest(String(reader.result)),base=defaults();state=deepMerge(base,state);state.drafts[m.primary.strategy]=deepMerge(base.drafts[m.primary.strategy],m.primary.data);state.tier=m.primary.strategy;state.sourceDataUrl=m.asset.source?.uri||"";state.imageName=m.asset.source?.name||"";sourceImage=imageForRef("source");$("motionAssetId").value=m.asset.id;$("motionCanvasW").value=m.asset.canvas.width;$("motionCanvasH").value=m.asset.canvas.height;$("motionPivotX").value=m.asset.pivot.x;$("motionPivotY").value=m.asset.pivot.y;$("motionGroundX").value=m.asset.ground.x;$("motionGroundY").value=m.asset.ground.y;$("motionFacing").value=m.asset.facing;$("motionSampling").value=m.asset.sampling;$("motionManualApproval").checked=m.manual_visual_approval===true;const v=m.overlays[0];$("motionVfxEnabled").checked=!!v;if(v){$("motionVfxTrigger").value=v.trigger;$("motionVfxAnchor").value=v.anchor;$("motionVfxX").value=v.offset.x;$("motionVfxY").value=v.offset.y;$("motionVfxDuration").value=v.duration;$("motionVfxBlend").value=v.blend;$("motionVfxSeed").value=v.seed;}refresh();selectTier(m.primary.strategy);runQA();saveDraft();status("Manifest 가져오기 완료");}catch(error){status(`가져오기 실패: ${error.message}`);}};reader.onerror=()=>status("파일을 읽을 수 없습니다.");reader.readAsText(file);}

  function serializeProjectState(){return{version:1,state:clone(state),canonical:{asset_id:$("motionAssetId").value,canvas_width:number("motionCanvasW"),canvas_height:number("motionCanvasH"),pivot_x:number("motionPivotX"),pivot_y:number("motionPivotY"),ground_x:number("motionGroundX"),ground_y:number("motionGroundY"),facing:$("motionFacing").value,sampling:$("motionSampling").value},vfx:{enabled:checked("motionVfxEnabled"),trigger:$("motionVfxTrigger").value,anchor:$("motionVfxAnchor").value,offset_x:number("motionVfxX"),offset_y:number("motionVfxY"),duration:number("motionVfxDuration"),blend:$("motionVfxBlend").value,seed:number("motionVfxSeed")}};}

  function validateProjectState(raw){if(raw==null)return null;if(!plain(raw)||raw.version!==1)throw new TypeError("Invalid Motion Studio project state");const clean=clone(raw),base=defaults();if(!plain(clean.state)||!TIERS.includes(clean.state.tier)||!plain(clean.state.drafts))throw new TypeError("Invalid Motion Studio draft state");for(const tier of TIERS)if(clean.state.drafts[tier]!==undefined&&!plain(clean.state.drafts[tier]))throw new TypeError(`Invalid Motion Studio ${tier} draft`);const merged=deepMerge(base,clean.state);const collections=[[merged.drafts.state_swap.states,Core.LIMITS.states],[merged.drafts.rigid_parts.parts,Core.LIMITS.parts],[merged.drafts.limited_frames.frames,4],[merged.drafts.full_frames.frames,Core.LIMITS.frames],[merged.drafts.rig_paper_doll.bones,Core.LIMITS.bones],[merged.drafts.rig_paper_doll.slots,Core.LIMITS.slots]];for(const[item,max]of collections)if(!Array.isArray(item)||item.length>max||item.some(x=>!plain(x)))throw new TypeError("Invalid Motion Studio collection");const c=clean.canonical||{};Core.normalizeManifest({asset:{id:c.asset_id,canvas:{width:c.canvas_width,height:c.canvas_height},pivot:{x:c.pivot_x,y:c.pivot_y},ground:{x:c.ground_x,y:c.ground_y},facing:c.facing,sampling:c.sampling,source:merged.sourceDataUrl?{name:merged.imageName||"source",uri:merged.sourceDataUrl}:undefined},primary:{strategy:merged.tier,data:{}},overlays:[]});const v=clean.vfx||{};if(typeof v.enabled!=="boolean"||!Number.isFinite(v.offset_x)||!Number.isFinite(v.offset_y)||!Number.isFinite(v.duration)||!Number.isSafeInteger(v.seed)||typeof v.trigger!=="string"||typeof v.anchor!=="string"||!["normal","add","multiply","screen"].includes(v.blend))throw new TypeError("Invalid Motion Studio VFX draft");clean.state=merged;return clean;}

  function applyProjectControls(clean){const c=clean.canonical,v=clean.vfx;$("motionAssetId").value=c.asset_id;$("motionCanvasW").value=c.canvas_width;$("motionCanvasH").value=c.canvas_height;$("motionPivotX").value=c.pivot_x;$("motionPivotY").value=c.pivot_y;$("motionGroundX").value=c.ground_x;$("motionGroundY").value=c.ground_y;$("motionFacing").value=c.facing;$("motionSampling").value=c.sampling;$("motionVfxEnabled").checked=v.enabled;$("motionVfxTrigger").value=v.trigger;$("motionVfxAnchor").value=v.anchor;$("motionVfxX").value=v.offset_x;$("motionVfxY").value=v.offset_y;$("motionVfxDuration").value=v.duration;$("motionVfxBlend").value=v.blend;$("motionVfxSeed").value=v.seed;$("motionManualApproval").checked=clean.state.manualVisualApproval===true;}

  function hydrateProjectState(raw){const clean=validateProjectState(raw);playing=false;imageCache.clear();if(!clean){state=defaults();sourceImage=null;localStorage.removeItem(STORAGE_KEY);refresh();selectTier("static");status("Motion Studio가 기본 상태로 초기화되었습니다.");return;}state=clean.state;applyProjectControls(clean);sourceImage=imageForRef("source");refresh();selectTier(state.tier);saveDraft();status("프로젝트 모션·미디어 복원 완료");}
  function snapshotRuntimeState(){return{project:serializeProjectState(),sourceImage,playing,playOrigin,playStart};}
  function restoreRuntimeState(snapshot){hydrateProjectState(snapshot?.project||null);sourceImage=snapshot?.sourceImage||sourceImage;playing=false;playOrigin=snapshot?.playOrigin||0;playStart=snapshot?.playStart||0;render();}

  function saveDraft(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(serializeProjectState()));}catch(_){status("자동 저장 공간을 사용할 수 없습니다.");}}
  function loadDraft(){try{const saved=JSON.parse(localStorage.getItem(STORAGE_KEY)||"null");if(saved){const clean=validateProjectState(saved);state=clean.state;applyProjectControls(clean);sourceImage=imageForRef("source");}}catch(_){localStorage.removeItem(STORAGE_KEY);state=defaults();status("손상된 자동 저장 초안을 무시했습니다.");}}
  function refresh(){transformEditor();renderRows();syncRig();updateManifest();render();}

  function setupAccessibility(){document.querySelectorAll("[data-motion-tier]").forEach(button=>{const tier=button.dataset.motionTier,panel=document.querySelector(`[data-motion-editor="${tier}"]`),tabId=`motion-tab-${tier}`,panelId=`motion-panel-${tier}`;button.id=tabId;button.setAttribute("aria-controls",panelId);panel.id=panelId;panel.setAttribute("role","tabpanel");panel.setAttribute("aria-labelledby",tabId);});$("motionPreviewLabel").setAttribute("aria-live","polite");$("motionTime").setAttribute("aria-live","polite");}

  window.AssetStudioMotion={serializeProjectState,validateProjectState,hydrateProjectState,snapshotRuntimeState,restoreRuntimeState};
  setupAccessibility();loadDraft();refresh();route();selectTier(state.tier);

  document.querySelectorAll("#studioWorkspaceSwitch button").forEach(button=>button.addEventListener("click",()=>setWorkspace(button.dataset.studioWorkspace)));
  const drop=$("motionSourceDropzone"),input=$("motionSourceInput");drop.addEventListener("click",()=>input.click());drop.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();input.click();}});input.addEventListener("change",()=>useImage(input.files[0]));drop.addEventListener("dragover",event=>{event.preventDefault();drop.classList.add("is-dragging")});drop.addEventListener("dragleave",()=>drop.classList.remove("is-dragging"));drop.addEventListener("drop",event=>{event.preventDefault();drop.classList.remove("is-dragging");useImage(event.dataTransfer.files[0]);});
  $("motionRouterForm").addEventListener("input",route);$("motionApplyRecommendation").addEventListener("click",()=>{if(lastRecommendation){if(lastRecommendation.overlays.includes("vfx"))$("motionVfxEnabled").checked=true;selectTier(lastRecommendation.primary,true);}});
  $("motionTierTabs").addEventListener("click",event=>{const button=event.target.closest("[data-motion-tier]");if(button)selectTier(button.dataset.motionTier);});$("motionTierTabs").addEventListener("keydown",event=>{if(!["ArrowRight","ArrowLeft","Home","End"].includes(event.key))return;event.preventDefault();const enabled=[...document.querySelectorAll("[data-motion-tier]:not(:disabled)")],at=enabled.indexOf(document.activeElement);let next=event.key==="Home"?0:event.key==="End"?enabled.length-1:(at+(event.key==="ArrowRight"?1:-1)+enabled.length)%enabled.length;selectTier(enabled[next].dataset.motionTier,true);});
  $("motionEditors").addEventListener("input",event=>{const t=event.target;if(t.dataset.transform){const path=t.dataset.transform.split("."),value=t.type==="checkbox"?t.checked:t.type==="number"?Number(t.value):t.value;if(path.length===2)state.drafts.transform_tween[path[0]][path[1]]=value;else state.drafts.transform_tween[path[0]]=value;}if(t.dataset.clipLoop){const tier={limited:"limited_frames",full:"full_frames",rigid:"rigid_parts"}[t.dataset.clipLoop];state.drafts[tier].loop=t.value;}if(t.dataset.row){const map={state:["state_swap","states"],part:["rigid_parts","parts"],limited:["limited_frames","frames"],full:["full_frames","frames"],bone:["rig_paper_doll","bones"],slot:["rig_paper_doll","slots"]},spec=map[t.dataset.row],item=state.drafts[spec[0]][spec[1]][Number(t.dataset.index)],key=t.dataset.key;if(["pivot","socket","offset"].includes(key)){const[x,y]=t.value.split(",").map(Number);item[key]={x,y};}else item[key]=t.type==="checkbox"?t.checked:t.type==="number"?Number(t.value):t.value||null;}invalidateMotionQa();updateManifest();render();saveDraft();});
  $("motionEditors").addEventListener("change",event=>{const t=event.target;if(t.dataset.mediaKind&&t.files?.[0])bindRowImage(t.files[0],t.dataset.mediaKind,Number(t.dataset.index));});
  $("motionEditors").addEventListener("click",event=>{const add=event.target.dataset.addRow,del=event.target.dataset.deleteRow,move=event.target.dataset.moveRow,map={state:["state_swap","states",{id:"state",image_ref:"source",image_name:"source",default:false,duration:100},Core.LIMITS.states],part:["rigid_parts","parts",{id:"part",parent:null,image_ref:"source",image_name:"source",pivot:{x:0,y:0},socket:{x:0,y:0},offset:{x:0,y:0},rotation_min:0,rotation_max:0},4],limited:["limited_frames","frames",{id:"pose",image_ref:"source",image_name:"source",duration:100,phase:"",event:""},4],full:["full_frames","frames",{id:"frame",image_ref:"source",image_name:"source",duration:100,phase:"",event:""},Core.LIMITS.frames],bone:["rig_paper_doll","bones",{id:"bone",parent:null,x:0,y:0,rotation:0},Core.LIMITS.bones],slot:["rig_paper_doll","slots",{id:"slot",bone:"root",image_ref:"source",image_name:"source"},Core.LIMITS.slots]};const kind=add||del||move;if(!kind)return;const spec=map[kind],arr=state.drafts[spec[0]][spec[1]];if(add&&arr.length<spec[3])arr.push(clone(spec[2]));if(del)arr.splice(Number(event.target.dataset.index),1);if(move){const from=Number(event.target.dataset.index),to=from+Number(event.target.dataset.direction);if(to>=0&&to<arr.length)[arr[from],arr[to]]=[arr[to],arr[from]];}invalidateMotionQa();renderRows();updateManifest();render();saveDraft();});
  ["motionRigSkins","motionRigClips","motionRigEquipment","motionRigRest","motionRigAdapter","motionRigApproval"].forEach(id=>$(id).addEventListener("change",()=>{const d=state.drafts.rig_paper_doll;d.gate={skins:number("motionRigSkins"),clips:number("motionRigClips"),equipment:checked("motionRigEquipment"),rest_pose:checked("motionRigRest"),adapter:checked("motionRigAdapter")};d.approved=checked("motionRigApproval");invalidateMotionQa();syncRig();saveDraft();}));
  $("motionPlay").addEventListener("click",()=>{if(window.matchMedia("(prefers-reduced-motion: reduce)").matches){status("감소된 모션 설정으로 자동 재생이 꺼져 있습니다.");return;}if(!playing){playing=true;playOrigin=state.time;playStart=performance.now();requestAnimationFrame(tick);}});$("motionPause").addEventListener("click",()=>{playing=false;saveDraft();});$("motionRestart").addEventListener("click",()=>{state.time=0;playOrigin=0;playStart=performance.now();render();});$("motionScrubber").addEventListener("input",event=>{state.time=Number(event.target.value);playOrigin=state.time;playStart=performance.now();render();});
  $("motionPreviewBg").addEventListener("change",event=>{$("motionPreviewStage").className=`motion-preview-stage ${event.target.value}`;});["motionZoom","motionVfxPreview"].forEach(id=>$(id).addEventListener("change",render));
  document.querySelectorAll("#motionStudioWorkspace input,#motionStudioWorkspace select").forEach(el=>el.addEventListener("change",()=>{if(!["motionZoom","motionPreviewBg","motionVfxPreview","motionScrubber","motionSourceInput","motionImportInput"].includes(el.id)){if(el.id==="motionManualApproval")state.manualVisualApproval=el.checked;invalidateMotionQa();}updateManifest();saveDraft();}));
  $("motionRunQa").addEventListener("click",runQA);$("motionExport").addEventListener("click",exportJson);$("motionImport").addEventListener("click",()=>$("motionImportInput").click());$("motionImportInput").addEventListener("change",event=>importJson(event.target.files[0]));$("motionReset").addEventListener("click",()=>{playing=false;state=defaults();sourceImage=null;imageCache.clear();localStorage.removeItem(STORAGE_KEY);$("motionManualApproval").checked=false;refresh();selectTier("static");status("Motion Studio 상태만 초기화했습니다.");});
})();
