import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = [
    ROOT / "index.html",
    ROOT / "src" / "main.js",
    ROOT / "server.py",
    ROOT / "styles" / "app.css",
]
PHASE_MARKER = re.compile(r"(?i)(?:\bphase[ _-]?\d+|_phase\d+)")


def test_runtime_files_do_not_expose_development_phase_markers():
    offenders = {}
    for path in RUNTIME_FILES:
        matches = sorted(set(PHASE_MARKER.findall(path.read_text(encoding="utf-8"))))
        if matches:
            offenders[str(path.relative_to(ROOT))] = matches
    assert offenders == {}


def test_root_milestone_artifacts_are_archived_under_docs_history():
    root_artifacts = sorted(path.name for path in ROOT.glob("PHASE_*") if path.is_file())
    assert root_artifacts == []
    assert (ROOT / "docs" / "history" / "README.md").is_file()


def test_readme_describes_product_instead_of_an_old_phase_roadmap():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Current milestone:" not in readme
    assert "Next planned phase:" not in readme
    assert "docs/history" in readme
