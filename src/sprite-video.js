(() => {
  const byId = id => document.getElementById(id);
  let health = null;
  let pinnedImageReference = null;
  function getImageReference() {
    return pinnedImageReference ? {...pinnedImageReference} : null;
  }
  function renderImageReference() {
    const reference = pinnedImageReference;
    const preview = byId('imageReferencePreview');
    preview.hidden = !reference;
    if (reference) preview.src = reference.image;
    else preview.removeAttribute('src');
    byId('imageReferenceName').textContent = reference ? `고정 기준 · ${reference.name}` : '기준 없음 · 설명만으로 생성';
    byId('imageReferencePin').textContent = reference ? '기준 변경' : '선택 레이어를 기준으로 지정';
    byId('imageReferencePin').title = reference ? '현재 선택한 전체 이미지로 기준을 바꿉니다.' : '현재 선택한 전체 이미지를 기준으로 고정합니다.';
    byId('imageReferenceClear').hidden = !reference;
  }
  function pinImageReference() {
    try {
      const source = canvas.getActiveObject();
      if (!source || source.type !== 'image' || source.excludeFromLayers || source.isMaskOverlay) throw new Error('전체 이미지 레이어를 먼저 선택하세요.');
      // 마스크와 선택 영역은 읽지 않습니다. 지정 시점의 전체 이미지 바이트를 보관합니다.
      const image = imageObjectToDataUrl(source);
      const element = source.getElement();
      pinnedImageReference = Object.freeze({image, name:nameOf(source), layer_id:source.id || null,
        width:element.naturalWidth || element.width, height:element.naturalHeight || element.height,
        captured_at:new Date().toISOString()});
      renderImageReference();
      updateGenerateAvailability();
      byId('imageReferenceStatus').textContent = '기준을 고정했습니다. 생성 결과는 새 레이어에 추가됩니다.';
    } catch (error) { byId('imageReferenceStatus').textContent = error.message; }
  }
  function clearImageReference() {
    pinnedImageReference = null;
    renderImageReference();
    updateGenerateAvailability();
    byId('imageReferenceStatus').textContent = '기준을 해제했습니다. 설명만으로 생성합니다.';
  }
  const number = (id, min, max, integer = false) => {
    const value = Number(byId(id).value);
    if (!Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) throw new Error(`${byId(id).closest('label').textContent.trim()}: ${min}~${max} 값을 입력하세요.`);
    return value;
  };
  function updateGenerateAvailability() {
    const source = canvas.getActiveObject();
    const sprite = currentAssetFamily() === 'sprite';
    const modelReady = health?.models?.some(model => model.id === byId('spriteVideoModel').value && model.available);
    const imageReady = byId('providerStatus').dataset.state === 'ready';
    const referenceUnsupported = currentAssetFamily() === 'image' && !!pinnedImageReference && byId('providerStatus').dataset.referenceImages !== 'true';
    const sourceReady = source?.type === 'image' && !source.excludeFromLayers;
    byId('familyGenerateAi').disabled = !!assetGenerationInFlight || referenceUnsupported || !byId('assetCorePrompt').value.trim() || (sprite ? (!sourceReady || !modelReady) : !imageReady);
    byId('primaryGenerationHint').textContent = assetGenerationInFlight ? '생성 중입니다. 선택을 바꿔도 요청한 원본은 유지됩니다.' : referenceUnsupported ? '기준 이미지 기능을 사용하려면 서버를 다시 시작하세요.' : !sprite && !imageReady ? (byId('providerStatus').title || '이미지 생성 제공자 연결 확인 중입니다.') : sprite && !sourceReady ? '원본 이미지 레이어를 선택하세요.' : !byId('assetCorePrompt').value.trim() ? '프롬프트를 입력하면 생성할 수 있습니다.' : sprite && !modelReady ? '아래 실행 설정을 열어 선택 모델의 연결을 확인하세요.' : '';
  }
  function syncFamily() {
    const sprite = currentAssetFamily() === 'sprite';
    byId('imageReferenceControls').hidden = currentAssetFamily() !== 'image';
    byId('spriteVideoControls').hidden = !sprite;
    byId('spriteVideoExecution').hidden = !sprite;
    byId('assetCorePromptLabel').textContent = sprite ? '최종 프롬프트' : '만들 이미지 설명';
    updateGenerateAvailability();
    byId('assetCorePromptHelp').textContent = sprite ? '직접 입력하거나 마법사로 작성하세요. 아래 문장을 그대로 모델에 전달합니다.' : '설명한 내용을 그대로 전달합니다. 그림체와 배경도 원하는 대로 적으세요.';
  }
  function syncSource() {
    const object = canvas.getActiveObject();
    const valid = object?.type === 'image' && !object.excludeFromLayers;
    const preview = byId('spriteVideoSourcePreview');
    preview.hidden = !valid;
    byId('spriteVideoSourceName').textContent = valid ? nameOf(object) : '이미지 레이어를 선택하세요';
    if (valid) preview.src = object.getSrc();
    else preview.removeAttribute('src');
    updateGenerateAvailability();
  }
  async function checkHealth() {
    byId('spriteVideoHealth').textContent = 'ComfyUI 연결 확인 중…';
    try {
      const response = await fetch('/api/sprite-video-health', {cache:'no-store'});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('서버를 새 버전으로 다시 시작한 뒤 연결을 확인하세요.');
      health = await response.json();
      if (!response.ok) throw new Error(health.error || '연결 실패');
      byId('spriteVideoHealth').textContent = health.available ? 'ComfyUI 연결됨 · H3 생성 준비 완료' : (health.error || health.message || 'H3 노드와 모델 설치 상태를 확인하세요.');
    } catch (error) { health = null; byId('spriteVideoHealth').textContent = `연결 확인 실패: ${error.message}`; }
    updateGenerateAvailability();
  }
  function buildRequest(prompt, reference) {
    if (!health?.models?.some(model => model.id === byId('spriteVideoModel').value && model.available)) throw new Error('선택한 H3 모델의 연결과 설치 상태를 확인하세요.');
    if (!reference?.startsWith('data:image/')) throw new Error('원본 이미지가 필요합니다.');
    if (!prompt.trim()) throw new Error('최종 프롬프트를 입력하세요.');
    return {
      reference_image:reference, prompt, model:byId('spriteVideoModel').value,
      duration:number('spriteVideoDuration',1,6), frame_count:number('spriteVideoFrames',2,64,true),
      fps:number('spriteVideoFps',1,60,true), name:byId('spriteVideoName').value.trim() || 'animation',
      background_color:byId('spriteVideoBackground').value,
    };
  }
  const motionExamples = {
    walk: '오른발을 조금 앞으로 내딛고 왼발로 몸을 지탱한다. 몸은 원본 방향을 유지한 채 제자리에서 걷는다.\n오른발에 체중을 옮기며 왼발을 들어 앞으로 보낸다. 양발은 서로 다른 경로를 따라 움직이고 교차하지 않는다.\n왼발을 내딛고 오른발을 뒤로 보낸다. 몸은 작게 오르내리고 장비는 가볍게 흔들린다.\n오른발을 다시 앞으로 보내 다음 걸음으로 이어간다. 멈추거나 대기 자세로 돌아가지 않는다.',
    idle: '두 발을 원래 위치에 고정하고 편안하게 서 있다. 천천히 숨을 들이쉬며 가슴과 어깨가 아주 조금 올라간다.\n천천히 숨을 내쉬며 가슴과 어깨가 원래 높이로 내려온다.\n장비를 잡은 손은 유지하고 머리와 몸만 아주 미세하게 움직인다. 걷거나 몸을 돌리지 않는다.\n처음의 호흡으로 자연스럽게 이어간다. 발 위치, 외형과 장비 모양은 유지한다.',
    run: '원본과 같은 방향을 바라보며 제자리에서 빠르게 달린다. 오른발로 강하게 지면을 밀고 왼쪽 무릎을 앞으로 보낸다.\n짧게 두 발이 모두 지면에서 떨어지는 공중 구간을 거친다. 두 다리는 서로 다른 경로를 유지하고 교차하지 않는다.\n왼발로 착지해 체중을 받은 뒤 지면을 밀고 오른쪽 무릎을 앞으로 보낸다. 상체는 조금 기울고 팔은 다리와 반대로 움직인다. 장비는 원래 손에 단단히 유지한다.\n다음 공중 구간을 거쳐 오른발 착지로 이어진다. 같은 속도를 유지하며 멈추지 않는다. 화면 속 전체 위치와 크기는 유지한다.',
    jump: '원본 방향을 유지한 채 무릎과 허리를 살짝 굽혀 점프를 준비한다. 장비는 원래 손에 유지한다.\n두 발로 지면을 밀어 같은 자리에서 위로 뛰어오른다. 몸과 발이 분명하게 위로 이동하고 전신과 장비는 화면 안에 남는다.\n공중에서 정점에 도달한 뒤 자연스럽게 내려온다. 다리는 몸 아래에서 약간 굽히고 좌우로 벌어지거나 꼬이지 않는다.\n출발한 지점에 두 발로 착지하고 무릎을 굽혀 충격을 흡수한 뒤 대기 자세로 돌아온다. 점프는 한 번만 한다.',
    attack: '',

  };
  const attackChoices = {
    unarmed: ['punch', 'custom'],
    onehand: ['slash', 'thrust', 'smash', 'crossbow', 'custom'],
    shield: ['slash', 'thrust', 'smash', 'shield_bash', 'custom'],
    twohand: ['slash', 'thrust', 'smash', 'bow', 'crossbow', 'custom'],
    dual: ['slash', 'thrust', 'smash', 'custom'],
  };
  function syncAttackControls() {
    byId('spriteWizardAttackControls').hidden = byId('spriteWizardAction').value !== 'attack';
    const equipment = byId('spriteWizardEquipment').value || 'onehand';
    const allowed = attackChoices[equipment] || attackChoices.onehand;
    const type = byId('spriteWizardAttackType');
    for (const option of Array.from(type.options || [])) {
      option.hidden = !allowed.includes(option.value);
      option.disabled = option.hidden;
    }
    if (!allowed.includes(type.value)) type.value = allowed[0];
    byId('spriteWizardAttackHandControls').hidden = !['unarmed', 'dual'].includes(equipment);
    byId('spriteWizardAttackCustomControls').hidden = type.value !== 'custom';
  }
  function buildAttackExample(equipment, type, hand = 'right', custom = '') {
    if (!attackChoices[equipment]?.includes(type)) throw new Error('장비 구성에 맞는 공격 방식을 선택하세요.');
    const side = hand === 'left' ? '왼손' : '오른손';
    const grips = {
      unarmed: `양손은 빈손이다. 캐릭터의 ${side}으로 공격하고 반대손은 얼굴과 몸을 방어한다.`,
      onehand: '원본에서 한손 무기를 잡은 손으로 공격하고, 반대손은 빈손으로 균형을 잡는다. 무기를 잡는 손을 바꾸지 않는다.',
      shield: '원본에서 무기를 잡은 손과 방패를 잡은 손을 각각 유지한다. 무기는 한 손으로만 사용하고 방패와 무기를 바꿔 잡지 않는다.',
      twohand: '원본의 하나의 무기를 두 손으로 함께 조작한다. 두 무기로 나누거나 방패를 추가하지 않는다.',
      dual: `원본의 서로 다른 두 무기를 각각 원래 손에 유지한다. 캐릭터의 ${side}에 든 무기로 한 번 공격하고 반대손 무기는 방어 자세로 유지한다. 한 무기를 두 손으로 잡거나 두 무기를 합치지 않는다.`,
    };
    const motions = {
      punch: ['주 공격손의 주먹을 쥐고 팔꿈치를 굽혀 뒤로 당긴다.', '주 공격손의 주먹을 원본이 바라보는 방향으로 곧게 한 번 뻗는다.'],
      slash: ['공격할 무기를 몸 옆으로 당겨 한 번 베기를 준비한다.', '공격할 무기의 날로 앞쪽을 가로질러 한 번 벤다. 무기의 끝이 분명한 호를 그린다.'],
      thrust: ['공격할 무기의 끝을 앞쪽에 맞추고 몸 가까이 당긴다.', '공격할 무기를 원본이 바라보는 방향으로 곧게 한 번 찌른다. 옆으로 휘두르지 않는다.'],
      smash: ['공격할 무기를 위로 들어 내려치기를 준비한다.', '공격할 무기를 앞쪽 아래로 한 번 내려친다. 무게에 맞춰 몸통과 무릎이 함께 움직인다.'],
      bow: ['한 손으로 활을 지지하고 반대손으로 원본의 시위를 당겨 조준한다.', '시위를 놓아 원본 활의 화살을 한 번 발사한다. 활을 휘두르거나 다른 무기로 바꾸지 않는다.'],
      crossbow: ['원본 석궁의 손잡이를 잡고 앞쪽을 조준한다.', '석궁의 방아쇠를 당겨 원본의 볼트를 한 번 발사한다. 석궁을 검처럼 휘두르지 않는다.'],
      shield_bash: ['방패를 몸 앞에 세우고 방패 쪽 팔과 어깨를 살짝 뒤로 당긴다.', '방패를 든 팔과 어깨로 앞쪽을 한 번 밀쳐친다. 무기를 든 손은 몸 옆에서 안전하게 유지한다.'],
      custom: ['사용자가 지정한 공격의 준비 자세를 취한다.', custom.trim().replace(/\s*\n\s*/g, ' ')],
    };
    if (type === 'custom' && !custom.trim()) throw new Error('직접 공격 설명을 입력하세요.');
    const weaponWithShield = equipment === 'shield' && type !== 'shield_bash';
    const shieldPrepare = weaponWithShield ? '방패를 든 팔은 팔꿈치를 굽혀 방패를 같은 쪽 옆구리와 골반 옆, 몸통보다 약간 뒤로 당긴다. 무기 팔의 공격 경로를 비우며 방패는 몸을 관통하거나 사라지지 않는다.' : '';
    const shieldHold = weaponWithShield ? '무기를 든 팔만 앞으로 공격한다. 방패 팔은 접은 채 몸 옆의 뒤쪽 위치에 머물고, 무기 팔을 따라 앞으로 뻗거나 휘두르거나 밀쳐치지 않는다. 방패에 허용되는 움직임은 몸을 따라가는 작은 수동적인 흔들림뿐이다.' : '';
    const shieldRecover = weaponWithShield ? '무기 공격이 끝나고 무기 팔을 거둔 다음에만 방패 팔을 원래 방어 위치로 되돌린다. 두 팔이 함께 앞으로 공격하는 동작은 없다.' : '';
    const twohand = equipment === 'twohand' ? (type === 'bow' ? '활 지지손과 시위를 당기는 손의 역할을 구분한다.' : '두 손은 같은 무기를 함께 지지하며 놓지 않는다.') : '';
    return [
      `원본 방향을 유지하며 공격을 준비한다. ${grips[equipment]} ${motions[type][0]} ${shieldPrepare} ${twohand}`,
      `${motions[type][1]} ${shieldHold} ${twohand} 원본의 손과 장비 연결을 유지한다.`,
      `공격의 끝동작을 분명히 보여주고 몸통과 체중이 힘의 방향을 따른다. 카메라와 캐릭터의 바라보는 방향은 유지한다. 장비가 손에서 떨어지거나 몸을 관통하지 않는다. 새 무기나 장비를 만들지 않는다. 상대 캐릭터와 타격 이펙트는 추가하지 않는다. ${shieldHold}`,
      `공격한 팔과 장비를 천천히 거두고 원래 대기 자세로 돌아온다. 한 번만 공격하며 연속 공격하지 않는다. 원본의 얼굴, 의상, 장비 모양과 잡은 손을 유지한다. ${shieldRecover}`,
    ].join('\n');
  }
  byId('spriteWizardAction').addEventListener('change', syncAttackControls);
  byId('spriteWizardEquipment').addEventListener('change', syncAttackControls);
  byId('spriteWizardAttackType').addEventListener('change', syncAttackControls);
  syncAttackControls();
  function applyExample(kind) {
    if (!Object.prototype.hasOwnProperty.call(motionExamples, kind)) return;
    let example = motionExamples[kind];
    if (kind === 'attack') {
      try {
        example = buildAttackExample(byId('spriteWizardEquipment').value || 'onehand', byId('spriteWizardAttackType').value, byId('spriteWizardAttackHand').value, byId('spriteWizardAttackCustom').value);
      } catch(error) { byId('spriteWizardError').textContent = error.message; return; }
    }
    const beats = byId('spriteWizardBeats');
    if (beats.value.trim() && !window.confirm('현재 적은 동작을 선택한 예시로 바꿀까요? 캐릭터 설명과 다른 설정은 유지됩니다.')) return;
    if (!byId('spriteWizardSubject').value.trim()) byId('spriteWizardSubject').value = '원본 이미지의 캐릭터. 얼굴, 의상과 장비를 그대로 유지하고 원본과 같은 방향을 바라본다.';
    beats.value = example;
    byId('spriteWizardLoop').checked = ['walk', 'idle', 'run'].includes(kind);
    byId('spriteWizardError').textContent = '';
  }
  byId('spriteWizardExampleApply').addEventListener('click', () => applyExample(byId('spriteWizardAction').value));
  function composePrompt({subject, style, background, camera, beats, duration, loop}) {
    const steps = beats.split('\n').map(value => value.trim()).filter(Boolean);
    if (!subject.trim() || !steps.length) throw new Error('대상과 동작 단계를 입력하세요.');
    const time = value => Number(value.toFixed(3));
    return `integrated_multimodal_description: ${subject.trim()} ${style.trim()}\n\nPreserve the source character's identity, proportions, colors and equipment in every frame.\n\n${background.trim()}\n\n${camera.trim()}\n\n${steps.map((step,index) => `[${time(index*duration/steps.length)}s-${time((index+1)*duration/steps.length)}s] ${step}`).join('\n\n')}${loop ? '\n\nConnect the ending and beginning as adjacent phases of one continuous cycle, without a pause or change in orientation.' : ''}\n\noverall_soundscape: Silent, no audio content.\n\nnon_diegetic_music: None.`;
  }
  function showResult(data, payload) {
    byId('gridCols').value = String(data.columns);
    byId('gridRows').value = String(data.rows);
    byId('gridCellW').value = String(data.cell_width);
    byId('gridCellH').value = String(data.cell_height);
    byId('gridGapX').value = '0'; byId('gridGapY').value = '0';
    byId('animFrameCount').value = String(data.frame_count);
    byId('animFps').value = String(payload.fps);
    byId('animMode').value = 'loop';
    document.querySelector('[data-studio-workspace="results"]').click();
  }
  for (const id of ['spriteVideoModel','spriteVideoDuration','spriteVideoFrames','spriteVideoFps']) byId(id).addEventListener('change', () => {
    updateGenerateAvailability();
    byId('spriteVideoExecutionSummary').textContent = `${byId('spriteVideoModel').value === 'h3' ? 'H3' : 'H3 Fast'} · ${byId('spriteVideoDuration').value}초 · ${byId('spriteVideoFrames').value}프레임 · ${byId('spriteVideoFps').value}fps`;
  });
  byId('spriteWizardOpen').addEventListener('click', () => window.CharacterActionBuilder.open());
  byId('spriteWizardClose').addEventListener('click', () => byId('spritePromptWizard').close());
  byId('spriteVideoImport').addEventListener('click', () => byId('topPhotoPickBtn').click());
  byId('spriteVideoRecheck').addEventListener('click', checkHealth);
  byId('spriteWizardApply').addEventListener('click', () => {
    try {
      byId('spriteWizardError').textContent = '';
      byId('assetCorePrompt').value = composePrompt({
        subject:byId('spriteWizardSubject').value, style:byId('spriteWizardStyle').value,
        background:byId('spriteWizardBackground').value, camera:byId('spriteWizardCamera').value,
        beats:byId('spriteWizardBeats').value, duration:number('spriteVideoDuration',1,6), loop:byId('spriteWizardLoop').checked,
      });
      byId('spritePromptWizard').close();
      byId('assetCorePrompt').focus();
      updateGenerateAvailability();
    } catch (error) { byId('spriteWizardError').textContent = error.message; }
  });
  canvas.on('selection:created', syncSource);
  canvas.on('selection:updated', syncSource);
  canvas.on('selection:cleared', syncSource);
  byId('assetCorePrompt').addEventListener('input', updateGenerateAvailability);
  byId('imageReferencePin').addEventListener('click', pinImageReference);
  byId('imageReferenceClear').addEventListener('click', clearImageReference);
  window.SpriteVideo = {buildAttackExample, buildRequest, composePrompt, showResult, syncFamily, updateGenerateAvailability, getImageReference};
  renderImageReference();
  syncFamily(); syncSource(); checkHealth();
})();
