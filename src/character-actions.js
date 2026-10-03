(() => {
  const options = {
    equipment: {unarmed:'맨손',onehand:'한손 무기',shield:'한손 무기 + 방패',twohand:'양손 무기 하나',dual:'쌍수 무기'},
    attacks: {punch:'주먹',kick:'발차기',slash:'베기',thrust:'찌르기',smash:'내려치기'},
    paths: {'right-left':'오른쪽 → 왼쪽 가로','left-right':'왼쪽 → 오른쪽 가로','down':'위 → 아래 세로','up':'아래 → 위 세로','down-right-left':'오른쪽 위 → 왼쪽 아래','down-left-right':'왼쪽 위 → 오른쪽 아래','up-right-left':'오른쪽 아래 → 왼쪽 위','up-left-right':'왼쪽 아래 → 오른쪽 위',thrust:'몸 앞을 향한 직선'},
  };
  function attackTypes(equipment) {
    if (!(equipment in options.equipment)) throw new Error('장비 구성을 선택하세요.');
    return equipment === 'unarmed' ? ['punch','kick'] : ['slash','thrust','smash'];
  }
  function pathsFor(type) {
    if (['thrust','punch','kick'].includes(type)) return ['thrust'];
    if (type === 'smash') return ['down','down-right-left','down-left-right'];
    if (type === 'slash') return Object.keys(options.paths).filter(path => path !== 'thrust');
    throw new Error('공격 방식을 선택하세요.');
  }
  const choose = (value, allowed, label) => {
    if (!allowed.includes(value)) throw new Error(`${label} 설정이 올바르지 않습니다.`);
    return value;
  };
  function build(input) {
    const c={group:'basic',action:'walk',equipment:'onehand',attack:'slash',path:'right-left',strength:'normal',feet:'in-place',hand:'right',offhand:'retract',weapon:'bow',phase:'fire',bowSupport:'left',grip:'twohand',aim:'level',projectile:'separate',shieldAction:'guard',...input};
    const duration=Number(c.duration);
    if (!Number.isFinite(duration)||duration<1||duration>6) throw new Error('영상 길이는 1~6초로 설정하세요.');
    choose(c.group,['basic','melee','ranged','shield'],'그룹');
    let stages=[],rules=[],loop=false,weights=[.25,.25,.25,.25];
    if(c.group==='basic') {
      choose(c.action,['idle','walk','run','jump'],'기본 동작');
      loop=c.action!=='jump';
      const beats={
        idle:['두 발을 원본 위치에 둔 채 천천히 숨을 들이쉰다.','가슴과 어깨가 미세하게 올라간다.','천천히 숨을 내쉬며 원래 높이로 돌아간다.','발과 장비를 유지하고 다음 호흡으로 연결한다.'],
        walk:['오른발을 원본 방향으로 조금 내딛고 왼발이 몸을 지탱한다.','오른발에 체중을 옮기고 왼발을 낮게 들어 옆 경로로 통과시킨다.','왼발을 내딛고 오른발이 지면을 밀며 떨어진다.','오른발을 앞으로 보내 다음 걸음으로 이어간다.'],
        run:['오른발로 지면을 밀고 반대쪽 무릎을 앞으로 보낸다.','짧은 공중 구간을 지나 왼발로 착지한다.','왼발로 지면을 밀고 오른쪽 무릎을 앞으로 보낸다.','짧은 공중 구간을 지나 오른발 착지와 다음 주행으로 연결한다.'],
        jump:['무릎과 골반을 낮추어 도약을 준비한다.','양발로 지면을 밀고 몸 전체가 수직으로 상승한다.','정점을 지나 같은 위치로 내려온다.','양발로 착지하고 무릎을 굽혀 충격을 흡수한 뒤 안정된다.'],
      };
      stages=beats[c.action];
      rules.push(c.action==='jump'?'Jump vertically with actual upward and downward displacement; keep horizontal position near the source and allow natural compression on landing.':c.action==='idle'?'Keep both feet planted. Subtle breathing only.':'Move in place along the source facing direction, like a treadmill. Feet follow separate parallel tracks without crossing.');
    } else if(c.group==='melee') {
      if(!attackTypes(c.equipment).includes(c.attack)) throw new Error('장비와 맞지 않는 공격 방식입니다.');
      if(!pathsFor(c.attack).includes(c.path)) throw new Error('공격과 맞지 않는 궤적입니다.');
      choose(c.strength,['light','normal','heavy'],'강도');choose(c.feet,['in-place','step'],'발');choose(c.hand,['right','left'],'공격손');choose(c.offhand,['retract','defend'],'방패 팔');
      const hand=c.hand==='right'?'오른손':'왼손';
      const actorObject=c.equipment==='unarmed'?(c.attack==='kick'?'공격할 다리를':hand+' 주먹을'):c.equipment==='twohand'?'하나의 원본 무기를 함께 잡은 두 손을':c.equipment==='dual'?hand+'에 원래 들고 있던 무기를':'원본에서 무기를 든 손을';
      const attackVerb={punch:'주먹을 뻗는다',kick:'발차기를 한다',slash:'벤다',thrust:'찌른다',smash:'내려친다'}[c.attack];
      const path=`캐릭터 자신의 몸 기준 ${options.paths[c.path]} 궤적`;
      const power={light:'짧고 가볍게',normal:'통제된 보통 강도로',heavy:'준비 동작을 크게 하고 무게를 실어'}[c.strength];
      rules.push(`All left/right directions are anatomical character-local directions, NOT screen-left or screen-right. Preserve original weapon hands; never add or swap weapons. Attack ${power}.`);
      if(c.equipment==='twohand')rules.push('Both hands cooperate on the same original weapon; do not create a second weapon.');
      if(c.equipment==='dual')rules.push(`Only the selected ${c.hand} hand attacks; the other weapon stays passive near the torso, without a simultaneous strike.`);
      if(c.equipment==='shield')rules.push(c.offhand==='retract'?'The shield arm remains bent and retracted close to the torso throughout the weapon strike. The shield does NOT attack, thrust or bash simultaneously.':'The shield remains in a stationary defensive guard while the weapon hand attacks. No simultaneous shield attack or bash.');
      rules.push(c.feet==='in-place'?'Keep the feet planted; allow natural hip and torso rotation around the stance.':'Take one short step in the source facing direction during the strike and recover to a stable stance.');
      stages=[`${actorObject} 준비 위치로 가져오고 ${path}을 준비한다.`,`${actorObject} 사용해 ${path}을 따라 ${power} 한 번 ${attackVerb}.`, '공격 궤적을 따라 자연스럽게 감속한다. 반대쪽 장비는 수동적인 위치를 유지한다.', '사용한 팔다리를 회수하고 원래의 준비 자세로 안정된다. 새로운 공격을 시작하지 않는다.'];
      if(c.equipment==='shield' && c.offhand==='retract') {
        stages[0]+=' 방패 팔을 옆구리와 몸통 약간 뒤로 당겨 팔꿈치를 굽힌다.';
        stages[1]+=' 방패 팔은 당긴 위치에 굽힌 채 유지하고 앞으로 뻗거나 공격하지 않는다.';
        stages[2]+=' 무기 공격이 감속하는 동안에도 방패 팔은 뒤로 당긴 위치를 유지한다.';
        stages[3]+=' 무기를 먼저 회수한 뒤에만 방패를 원래 방어 위치로 돌린다.';
      }
      weights=[.3,.15,.2,.35];
    } else if(c.group==='ranged') {
      choose(c.weapon,['bow','crossbow'],'원거리 무기');choose(c.phase,['fire','prepare-fire','reload'],'사격 단계');choose(c.bowSupport,['left','right'],'활 지지손');choose(c.grip,['onehand','twohand'],'석궁 잡기');choose(c.aim,['level','up','down'],'조준');choose(c.projectile,['separate','visible'],'투사체');
      const support=c.bowSupport==='left'?'왼손':'오른손',string=c.bowSupport==='left'?'오른손':'왼손';
      const aim={level:'수평',up:'위쪽',down:'아래쪽'}[c.aim];
      rules.push(`Use only the ${c.weapon} already present in the source. Do not replace it or add another weapon. Aim ${aim} along the source facing direction.`);
      if(c.weapon==='bow')rules.push(`${support} supports the bow grip; ${string} controls the arrow and bowstring. ${c.phase==='reload'?'The string hand loads and nocks the arrow without a firing release.':'The string fingers may open for a real release.'} Preserve the source hand roles; choose matching settings.`);
      else if(c.phase==='reload')rules.push('One hand supports the crossbow stock while the other works the cocking mechanism and loads a bolt; hands explicitly change positions and regrip as needed. No trigger pull or firing motion.');
      else rules.push(c.grip==='onehand'?'During the shot, the original trigger hand holds and fires the crossbow one-handed. The free hand may reposition for reloading.':'During aiming and firing, one hand holds the trigger grip and the other supports the fore-end. During reloading, release the supporting hand as needed; hands explicitly change positions to cock and load.');
      if(c.phase==='reload') {
        rules.push('Reload only: do not fire. Start unloaded and finish loaded. Hands may release and regrip the weapon to perform the mechanism.');
        stages=c.weapon==='bow'?[`${support}이 활을 지지하고 ${string}이 화살 한 발을 가져온다.`,`${string}으로 화살을 활 위에 놓고 시위에 걸어 장전한다.`, '화살과 시위의 결합을 확인하고 사격 준비 위치로 손을 옮긴다.', '장전된 상태로 안정된다. 시위를 놓거나 화살을 발사하지 않는다.']:
        ['방아쇠 손이 석궁 몸체를 지지하고 보조손이 장전 장치로 이동한다.','보조손으로 원본 석궁의 시위나 장전 기구를 당겨 잠근다. 양손의 위치는 작업에 맞게 바뀐다.','보조손이 볼트 한 발을 레일에 넣고 장전한다.','보조손을 원래 지지 위치로 돌려 장전된 석궁을 안정시킨다. 발사하지 않는다.'];
        weights=[.2,.45,.2,.15];
      } else {
        rules.push(c.projectile==='separate'?'Keep the loaded arrow or bolt visible until release. At release it leaves the weapon, but do not render a flying projectile afterwards; the game supplies that separate asset.':'Show the loaded arrow or bolt, then exactly one projectile leaving the weapon and briefly flying along the aim direction.');
        rules.push('Fire one shot only. Do not reload or create a second shot during this clip.');
        const preparation=c.phase==='fire'?'처음부터 장전과 조준이 완료된 자세를 유지한다.':c.weapon==='bow'?`${support}이 활을 들어 ${aim}으로 조준하고 ${string}이 화살과 시위를 당긴다.`:`장전된 석궁을 들어 원본 방향의 ${aim}으로 조준한다.`;
        stages=[preparation,c.weapon==='bow'?`${string}의 손가락을 열어 시위를 놓고 화살 한 발을 발사한다. ${support}은 활을 지지한다.`:'방아쇠를 당겨 볼트 한 발을 발사한다. 원본 석궁의 작은 반동을 표현한다.', '사격 후 자연스러운 반동과 손의 후속 움직임을 표현한다.', '사격 후 자세로 안정된다. 재장전이나 추가 발사는 하지 않는다.'];
        weights=c.phase==='fire'?[.2,.12,.28,.4]:[.3,.15,.2,.35];
      }
    } else {
      choose(c.shieldAction,['guard','bash'],'방패 동작');loop=c.shieldAction==='guard';
      rules.push('Use the shield already present in the source, in its original hand. The weapon hand stays passive close to the torso and does not strike.');
      stages=loop?['방패를 원본의 방어 위치에 유지한다.','팔꿈치를 굽히고 작은 호흡과 체중 변화로 방어 자세를 지탱한다.','방패의 방향과 손잡이를 유지하며 몸을 안정시킨다.','같은 방어 자세로 자연스럽게 이어간다. 공격하지 않는다.']:['방패를 든 팔을 몸 쪽으로 당겨 밀쳐치기를 준비한다.','방패 팔과 어깨로 원본 방향을 향해 한 번 짧게 밀쳐친다. 무기 팔은 수동적으로 유지한다.','방패의 전진을 감속하고 팔꿈치를 굽혀 회수한다.','방패를 원래 방어 위치로 돌려 안정된다.'];
      if(!loop)weights=[.3,.15,.2,.35];
    }
    const common=[c.subject||'원본 이미지의 캐릭터와 실제 장비를 기준으로 한다.',c.style||'원본의 그림체, 외형, 색상과 장비 비율을 유지한다.',c.background||'원본과 같은 단색 배경을 유지한다.',c.camera||'카메라 고정, 전신과 장비가 프레임 안에 보이며 화면 배율을 유지한다.',"Preserve identity and the source's base facing direction. Allow natural torso twist and the vertical or limb displacement required by the chosen action; do not turn to a new viewing angle. Do not invent weapons, extra limbs or unrelated effects.",...rules];
    let elapsed=0;
    const timed=stages.map((stage,i)=>{const start=Number(elapsed.toFixed(3));elapsed=i===stages.length-1?duration:elapsed+duration*weights[i];return `[${start}s-${Number(elapsed.toFixed(3))}s] ${stage}`;});
    return {loop,stages,weights,prompt:`integrated_multimodal_description: ${common.join('\n\n')}\n\n${timed.join('\n\n')}\n\n${loop?'Connect adjacent motion phases seamlessly across the loop boundary without stopping.':'Complete this action once, then settle into its finishing pose. Do not force a loop.'}\n\noverall_soundscape: Silent, no audio content.\n\nnon_diegetic_music: None.`};
  }
  window.CharacterActions={build,attackTypes,pathsFor,options};
})();
