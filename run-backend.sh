#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/Backend"

if [[ -f "$ROOT/Backend/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/Backend/.venv/bin/activate"
elif [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.venv/bin/activate"
fi

exec uvicorn main:app --reload --host 0.0.0.0 --port "${PORT:-8000}" "$@"
