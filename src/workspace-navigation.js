(() => {
  const app = document.querySelector('.app');
  const navigation = document.getElementById('studioWorkspaceSwitch');
  const animationHost = document.getElementById('animationToolsHost');
  const results = document.getElementById('resultsWorkspace');
  const spriteTools = document.querySelector('.sprite-tools-panel');
  const spriteHome = document.createComment('스프라이트 도구 원래 위치');
  spriteTools.before(spriteHome);
  const aiPanel = document.getElementById('assetAiPanel');
  const aiHome = document.createComment('생성 화면 원래 위치');
  aiPanel.before(aiHome);

  // 같은 DOM을 옮겨 기존 이벤트와 편집 상태를 유지합니다.
  results.append(document.getElementById('assetResultTray'));
  results.append(document.getElementById('gallery').closest('.panel'));

  const menus = [...document.querySelectorAll('.topbar .toolbar-menu')];
  function closeMenus() {
    menus.forEach(menu => { menu.open = false; });
  }
  menus.forEach(menu => menu.addEventListener('toggle', () => {
    if (menu.open) menus.filter(other => other !== menu).forEach(other => { other.open = false; });
  }));
  document.addEventListener('click', event => {
    if (!event.target.closest('.toolbar-menu')) closeMenus();
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const openMenu = menus.find(menu => menu.open);
    closeMenus();
    openMenu?.querySelector('summary').focus();
  });

  navigation.addEventListener('click', event => {
    const button = event.target.closest('[data-studio-workspace]');
    if (!button) return;
    const name = button.dataset.studioWorkspace;
    const animation = name === 'animation';
    app.dataset.primaryWorkspace = name;
    animationHost.hidden = !animation;
    results.hidden = name !== 'results';
    navigation.querySelectorAll('[data-studio-workspace]').forEach(tab => tab.setAttribute('aria-pressed', String(tab === button)));
    if (animation) {
      animationHost.append(aiPanel);
      animationHost.append(spriteTools);
      setAssetFamily('sprite');
      document.getElementById('rightPanelLayersTab').click();
    } else {
      spriteHome.after(spriteTools);
      aiHome.after(aiPanel);
      document.getElementById('stopAnimationPreview').click();
      if (name === 'results') document.getElementById('rightPanelExportTab').click();
    }
    if (name !== 'results') requestAnimationFrame(() => document.getElementById('fitCanvas').click());
    closeMenus();
  });
  document.getElementById('animationImportBtn').addEventListener('click', () => {
    document.getElementById('topPhotoPickBtn').click();
  });
  app.dataset.primaryWorkspace = 'canvas';
})();
