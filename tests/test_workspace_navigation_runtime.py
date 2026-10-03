"""Behavior checks for menu routing without booting the generation engines."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_navigation_preserves_tool_nodes_and_routes_existing_controls():
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.dataset = {}; this.listeners = {}; this.children = []; this.hidden = false; this.clicks = 0; this.classes = new Set(); this.classList = {toggle: (key, value) => value ? this.classes.add(key) : this.classes.delete(key)}; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(node) { if (node.parent) node.parent.children = node.parent.children.filter(child => child !== node); this.children.push(node); node.parent = this; }
  before(node) { node.parent = this.parent; this.parent.children.unshift(node); }
  after(node) { this.parent.append(node); }
  closest() { return this.container || this; }
  click() { this.clicks++; this.listeners.click?.({target: this}); }
  focus() { this.focused = true; }
  querySelector() { return this.summary; }
  querySelectorAll() { return []; }
  setAttribute() {}
}
const ids = Object.fromEntries(['studioWorkspaceSwitch','animationToolsHost','resultsWorkspace','assetResultTray','gallery','assetAiPanel','fitCanvas','rightPanelLayersTab','rightPanelExportTab','stopAnimationPreview','animationImportBtn','topPhotoPickBtn'].map(id => [id, new Element()]));
const app = new Element(), tools = new Element(), home = new Element(), galleryPanel = new Element();
home.append(tools); home.append(ids.assetAiPanel);
ids.gallery.container = galleryPanel;
tools.value = 'existing edited state';
const menus = [new Element(), new Element()];
menus.forEach(menu => { menu.summary = new Element(); });
const document = {getElementById: id => ids[id], querySelector: selector => selector === '.app' ? app : tools, querySelectorAll: () => menus, createComment: () => new Element(), listeners: {}, addEventListener(name, callback) {this.listeners[name] = callback;}};
vm.runInNewContext(fs.readFileSync('src/workspace-navigation.js', 'utf8'), {document, setAssetFamily: () => {}, requestAnimationFrame: callback => callback()});
const select = name => ids.studioWorkspaceSwitch.listeners.click({target:{closest: () => ({dataset:{studioWorkspace:name}})}});
assert.equal(app.dataset.primaryWorkspace, 'canvas');
assert.equal(ids.assetResultTray.parent, ids.resultsWorkspace);
assert.equal(galleryPanel.parent, ids.resultsWorkspace);
select('animation');
assert.equal(tools.parent, ids.animationToolsHost);
assert.equal(ids.animationToolsHost.hidden, false);
assert.equal(ids.resultsWorkspace.hidden, true);
assert.equal(ids.rightPanelLayersTab.clicks, 1);
ids.animationImportBtn.click();
assert.equal(ids.topPhotoPickBtn.clicks, 1);
select('results');
assert.equal(tools.parent, home);
assert.equal(tools.value, 'existing edited state');
assert.equal(ids.resultsWorkspace.hidden, false);
assert.equal(ids.rightPanelExportTab.clicks, 1);
assert.equal(ids.stopAnimationPreview.clicks, 1);
select('canvas');
assert.equal(tools.parent, home);
menus[0].open = true;
menus[1].open = true;
menus[0].listeners.toggle();
assert.equal(menus[1].open, false);
document.listeners.keydown({key:'Escape'});
assert.equal(menus[0].open, false);
assert.equal(menus[0].summary.focused, true);
console.log('navigation behavior passed');
'''
    result = subprocess.run([shutil.which('node'), '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_main_menu_retains_engine_routes_and_unique_controls():
    from html.parser import HTMLParser

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = []
            self.routes = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if 'id' in attrs:
                self.ids.append(attrs['id'])
            if 'data-studio-workspace' in attrs:
                self.routes.append(attrs['data-studio-workspace'])

    parser = Elements()
    parser.feed((ROOT / 'index.html').read_text(encoding='utf-8'))
    assert len(parser.ids) == len(set(parser.ids))
    assert parser.routes == ['canvas', 'animation', 'results']
    for control in ['gridCols', 'animFrameCount', 'animFps', 'buildAnimationPreview', 'assetResultCards', 'gallery', 'exportPng', 'undoBtn']:
        assert control in parser.ids


def test_ai_panel_keeps_main_request_visible_and_optional_settings_closed():
    from html.parser import HTMLParser

    class Tree(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.nodes = {}
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if 'id' in attrs:
                self.nodes[attrs['id']] = (tag, attrs, list(self.stack))
            if tag not in {'input', 'img', 'meta', 'link', 'br', 'hr'}:
                self.stack.append((tag, attrs))
        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
        def handle_endtag(self, tag):
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    self.stack = self.stack[:index]
                    return

    tree = Tree()
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    tree.feed(html)
    for control in ['assetFamilyTabs', 'assetSubtype', 'assetCorePrompt', 'familyGenerateAi']:
        ancestors = tree.nodes[control][2]
        assert any(attrs.get('id') == 'assetAiPanel' for _, attrs in ancestors)
        assert all(tag != 'details' for tag, _ in ancestors)
    groups = {
        'assetStyleDisclosure': ['assetStyleSection', 'assetStylePreset', 'stylePaletteColors'],
        'assetSettingsDisclosure': ['spriteSettings', 'tileSettings', 'uiSettings', 'objectSettings', 'generateFrontIdleFromSelected', 'pixelQaSummary', 'runPixelWorkflow'],
        'assetOutputDisclosure': ['assetOutputSection', 'assetOutputWidth', 'assetBackground'],
    }
    for disclosure, controls in groups.items():
        tag, attrs, _ = tree.nodes[disclosure]
        assert tag == 'details' and 'open' not in attrs
        for control in controls:
            assert any(attrs.get('id') == disclosure for _, attrs in tree.nodes[control][2])
    assert html.index('id="familyGenerateAi"') < html.index('id="assetStyleDisclosure"')
