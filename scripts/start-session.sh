#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNNER="$SCRIPT_DIR/start-session.py"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$RUNNER" "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python "$RUNNER" "$@"
fi

if command -v conda >/dev/null 2>&1 && conda run -n base python --version >/dev/null 2>&1; then
  exec conda run -n base python "$RUNNER" "$@"
fi

if command -v mamba >/dev/null 2>&1 && mamba run -n base python --version >/dev/null 2>&1; then
  exec mamba run -n base python "$RUNNER" "$@"
fi

if command -v micromamba >/dev/null 2>&1 && micromamba run -n base python --version >/dev/null 2>&1; then
  exec micromamba run -n base python "$RUNNER" "$@"
fi

printf '%s\n' "No Python launcher was found. Install Python 3 or make sure Conda's Python is on PATH."
exit 1
