from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_history_panel_markup_exists():
    assert 'id="historyList"' in INDEX
    assert 'id="historyCount"' in INDEX
    assert '히스토리' in INDEX


def test_history_render_and_jump_are_wired():
    assert "function renderHistory" in JS
    assert "function jumpToHistory" in JS
    assert "history-item" in JS
    assert "historyIndex" in JS


def test_standard_undo_redo_shortcuts_are_handled():
    lower = JS.lower()
    assert "key.tolowercase() === 'z'" in lower
    assert "key.tolowercase() === 'y'" in lower
    assert "e.shiftkey" in lower
    assert "loadhistory(historyindex - 1" in lower
    assert "loadhistory(historyindex + 1" in lower


def test_history_entries_carry_labels():
    assert "labelHistoryEntry" in JS
    assert "saveHistory(" in JS
    assert "label:" in JS
