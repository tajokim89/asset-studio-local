#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export HERMES_REPO="${HERMES_REPO:-$HOME/.hermes/hermes-agent}"

PYTHON_BIN="${ASSET_STUDIO_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
  elif [[ -x "$HERMES_REPO/venv/bin/python" ]]; then
    PYTHON_BIN="$HERMES_REPO/venv/bin/python"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

usage() {
  printf 'Usage: %s {static|focused <test...>|full}\n' "$0" >&2
}

run_static_checks() {
  while IFS= read -r -d '' file; do
    "$PYTHON_BIN" -m py_compile "$file"
  done < <(rg --files -0 -g '*.py')
  printf 'python: PASS\n'

  node --check src/main.js
  printf 'javascript: PASS\n'

  "$PYTHON_BIN" - <<'PY'
from html.parser import HTMLParser
from pathlib import Path

parser = HTMLParser(convert_charrefs=True)
parser.feed(Path("index.html").read_text(encoding="utf-8"))
parser.close()
PY
  printf 'html: PASS\n'

  bash -n scripts/run_server.sh scripts/verify_repo.sh
  printf 'shell: PASS\n'

  git diff --check
  printf 'diff: PASS\n'
}

require_pytest() {
  if ! "$PYTHON_BIN" -c 'import pytest' >/dev/null 2>&1; then
    printf 'pytest is not installed for %s; install requirements-dev.txt first\n' "$PYTHON_BIN" >&2
    exit 3
  fi
}

mode="${1:-}"
if [[ -z "$mode" ]]; then
  usage
  exit 2
fi
shift

case "$mode" in
  static)
    if [[ "$#" -ne 0 ]]; then
      usage
      exit 2
    fi
    run_static_checks
    ;;
  focused)
    if [[ "$#" -eq 0 ]]; then
      printf 'focused mode requires at least one test path\n' >&2
      exit 2
    fi
    require_pytest
    "$PYTHON_BIN" -m pytest "$@"
    run_static_checks
    ;;
  full)
    if [[ "$#" -ne 0 ]]; then
      usage
      exit 2
    fi
    require_pytest
    "$PYTHON_BIN" -m pytest -q
    run_static_checks
    ;;
  *)
    usage
    exit 2
    ;;
esac
