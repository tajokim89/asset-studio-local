(() => {
  const $=id=>document.getElementById(id), core=window.CharacterActions;
  let lastImportedPrompt=null;
  function setOptions(id,values,labels) {
    const select=$(id), previous=select.value;
    select.replaceChildren(...values.map(value=>{const option=document.createElement('option');option.value=value;option.textContent=labels[value];return option;}));
    select.value=values.includes(previous)?previous:values[0];
  }
  function read() {
    return {group:$('caGroup').value,action:$('caBasicAction').value,equipment:$('caEquipment').value,attack:$('caAttack').value,path:$('caPath').value,strength:$('caStrength').value,feet:$('caFeet').value,hand:$('caHand').value,offhand:$('caOffhand').value,weapon:$('caWeapon').value,phase:$('caPhase').value,bowSupport:$('caBowSupport').value,grip:$('caGrip').value,aim:$('caAim').value,projectile:$('caProjectile').value,shieldAction:$('caShieldAction').value,subject:$('caSubject').value,style:$('caStyle').value,background:$('caBackground').value,camera:$('caCamera').value,duration:Number($('spriteVideoDuration').value)};
  }
  function sync() {
    for(const section of document.querySelectorAll('[data-action-group]'))section.hidden=section.dataset.actionGroup!==$('caGroup').value;
    setOptions('caAttack',core.attackTypes($('caEquipment').value),core.options.attacks);
    setOptions('caPath',core.pathsFor($('caAttack').value),core.options.paths);
    $('caHandField').hidden=!['unarmed','dual'].includes($('caEquipment').value)||$('caAttack').value==='kick';
    $('caOffhandField').hidden=$('caEquipment').value!=='shield';
    $('caBowRole').hidden=$('caWeapon').value!=='bow';
    $('caGripField').hidden=$('caWeapon').value!=='crossbow';
    $('caAimField').hidden=$('caPhase').value==='reload';
    $('caProjectileField').hidden=$('caPhase').value==='reload';
    try { const result=core.build(read());$('characterActionSummary').textContent=`${$('spriteVideoDuration').value}초 · ${result.loop?'반복 동작':'한 번 동작'} · 출력 ${$('spriteVideoFrames').value}프레임 설정`; }
    catch(error){$('characterActionSummary').textContent=error.message;}
  }
  function open() { $('characterActionError').textContent='';sync();$('characterActionDialog').showModal(); }
  $('characterActionClose').addEventListener('click',()=>$('characterActionDialog').close());
  $('characterDirectPrompt').addEventListener('click',()=>{$('assetCorePrompt').focus();$('assetCorePrompt').scrollIntoView({block:'nearest'});});
  for(const id of ['caGroup','caBasicAction','caEquipment','caAttack','caPath','caStrength','caFeet','caHand','caOffhand','caWeapon','caPhase','caBowSupport','caGrip','caAim','caProjectile','caShieldAction'])$(id).addEventListener('change',sync);
  $('characterActionApply').addEventListener('click',()=>{
    try {
      const result=core.build(read()), final=$('assetCorePrompt');
      if(final.value.trim() && final.value!==lastImportedPrompt && final.value!==result.prompt && !window.confirm('현재 편집한 최종 프롬프트를 새 액션 문장으로 바꿀까요?'))return;
      final.value=result.prompt;lastImportedPrompt=result.prompt;
      final.dispatchEvent(new Event('input',{bubbles:true}));
      $('characterActionDialog').close();final.focus();
    } catch(error){$('characterActionError').textContent=error.message;}
  });
  window.CharacterActionBuilder={open};
})();
