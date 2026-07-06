from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text()
JS = (ROOT / "src" / "main.js").read_text()


def test_phase11_cache_bust_and_v2_save_hooks_exist():
    assert "phase12-ai-chat-exec-router2" in INDEX
    for token in [
        "async function buildProjectV2()",
        "app: 'asset-studio-local'",
        "version: 2",
        "kind: 'project'",
        "assets: { images: assets }",
        "modules: projectModulesSkeleton()",
        "asset-studio-project-v2.json",
    ]:
        assert token in JS


def test_phase11_project_v2_has_future_module_slots():
    fn = JS.split("function projectModulesSkeleton()", 1)[1].split("function currentEditorState", 1)[0]
    for token in [
        "sprite: { sheets: [], extractions: [], animations: [] }",
        "ui: { components: [], themes: [], nineSlice: [] }",
        "map: { tilesets: [], tilemaps: [], collision: [], layers: [] }",
    ]:
        assert token in fn


def test_phase11_embeds_image_assets_into_canvas_and_history_json():
    for token in [
        "async function srcToDataUrl(src)",
        "async function imageObjectDataUrl(obj)",
        "async function collectEmbeddedImageAssets(canvasJsons = [])",
        "o.src = asset.dataUrl",
        "if (o._originalSrc) o._originalSrc = asset.dataUrl",
        "const jsons = [canvasJson, ...historyEntries.map(e => e.canvasJson).filter(Boolean)]",
        "const assets = await collectEmbeddedImageAssets(jsons)",
    ]:
        assert token in JS


def test_phase11_saves_history_index_and_editor_state():
    for token in [
        "function currentEditorState()",
        "selectedLayerId,",
        "activeDrawingLayerId,",
        "canvasSize: { width: canvas.width, height: canvas.height }",
        "checkerboard:",
        "historyIndex,",
        "history: historyEntries",
    ]:
        assert token in JS


def test_phase11_loads_v2_and_keeps_legacy_v1_loader():
    for token in [
        "function loadProjectV2(project)",
        "function loadLegacyProjectV1(project)",
        "function loadProjectFileObject(project)",
        "project?.app === 'asset-studio-local' && project.version === 2",
        "history = entries.map",
        "historyIndex = clamp(idx, 0, history.length - 1)",
        "applyEditorState(editor.state || {})",
        "Legacy v1 프로젝트를 불러왔습니다.",
    ]:
        assert token in JS
