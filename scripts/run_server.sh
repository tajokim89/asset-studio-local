#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${ASSET_STUDIO_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
  elif [[ -x "/Users/tajokim/.hermes/hermes-agent/venv/bin/python" ]]; then
    PYTHON_BIN="/Users/tajokim/.hermes/hermes-agent/venv/bin/python"
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
