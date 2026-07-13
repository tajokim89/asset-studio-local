#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${HERMES_REPO:-}" ]]; then
  if [[ -n "${HERMES_HOME:-}" && -f "$HERMES_HOME/hermes-agent/plugins/image_gen/openai-codex/__init__.py" ]]; then
    HERMES_REPO="$HERMES_HOME/hermes-agent"
  elif [[ -n "${HERMES_HOME:-}" && -f "$HERMES_HOME/plugins/image_gen/openai-codex/__init__.py" ]]; then
    HERMES_REPO="$HERMES_HOME"
  else
    HERMES_REPO="$HOME/.hermes/hermes-agent"
    HERMES_BIN="${HERMES_COMMAND:-}"
    if [[ -n "$HERMES_BIN" ]]; then
      SEARCH_DIR="$(cd "$(dirname "$HERMES_BIN")" && pwd -P)"
      for _ in 1 2 3 4 5 6; do
        if [[ -f "$SEARCH_DIR/plugins/image_gen/openai-codex/__init__.py" ]]; then
          HERMES_REPO="$SEARCH_DIR"
          break
        fi
        if [[ -f "$SEARCH_DIR/hermes-agent/plugins/image_gen/openai-codex/__init__.py" ]]; then
          HERMES_REPO="$SEARCH_DIR/hermes-agent"
          break
        fi
        SEARCH_DIR="$(dirname "$SEARCH_DIR")"
      done
    fi
  fi
fi
export HERMES_REPO
export OPENAI_IMAGE_MODEL="${OPENAI_IMAGE_MODEL:-gpt-image-2-high}"

PYTHON_BIN="${ASSET_STUDIO_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
  elif [[ -x "$HERMES_REPO/venv/bin/python" ]]; then
    PYTHON_BIN="$HERMES_REPO/venv/bin/python"
  elif [[ -x "$HERMES_REPO/venv/Scripts/python.exe" ]]; then
    PYTHON_BIN="$HERMES_REPO/venv/Scripts/python.exe"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

"$PYTHON_BIN" - <<'PY'
import importlib.util
import subprocess
import sys
from pathlib import Path

required = {
    "httpx": "httpx>=0.28.0",
    "PIL": "pillow>=12.1.0",
    "numpy": "numpy>=2.3.0",
}
missing = [pkg for module, pkg in required.items() if importlib.util.find_spec(module) is None]
if missing:
    req = Path("requirements.txt")
    print(f"Installing missing runtime dependencies into {sys.executable}: {', '.join(missing)}", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])
PY

exec "$PYTHON_BIN" server.py
