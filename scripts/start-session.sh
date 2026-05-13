#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNNER="$SCRIPT_DIR/start-session.py"

export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export PYTHONUTF8="${PYTHONUTF8:-1}"

run_base_python() {
  tool=$1
  shift
  base=$("$tool" info --base 2>/dev/null || true)
  [ -n "$base" ] || return 1
  for candidate in "$base/bin/python3" "$base/bin/python" "$base/python.exe"; do
    if [ -x "$candidate" ]; then
      exec "$candidate" "$RUNNER" "$@"
    fi
  done
  return 1
}

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$RUNNER" "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python "$RUNNER" "$@"
fi

if command -v conda >/dev/null 2>&1; then
  run_base_python conda "$@"
fi

if command -v mamba >/dev/null 2>&1; then
  run_base_python mamba "$@"
fi

if command -v micromamba >/dev/null 2>&1; then
  run_base_python micromamba "$@"
fi

printf '%s\n' "No Python launcher was found. Install Python 3 or make sure Conda's Python is on PATH."
exit 1
