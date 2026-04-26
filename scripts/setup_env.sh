#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "[setup] created .env from .env.example"
fi

if [[ -d .githooks ]]; then
  current_hooks_path="$(git config --local --get core.hooksPath || true)"
  if [[ "$current_hooks_path" == ".githooks" ]]; then
    : # already set correctly
  elif [[ -n "$current_hooks_path" ]]; then
    echo "[setup] WARNING: core.hooksPath is already set to '${current_hooks_path}' — skipping .githooks registration"
    echo "[setup]   to override: git config --local core.hooksPath .githooks"
  else
    git config --local core.hooksPath .githooks
    echo "[setup] registered .githooks/ as git hooks path"
  fi
fi

STRICT_MODE="${ORDER_AGENT_SETUP_STRICT:-0}"
DOCTOR_ARGS=()

if [[ "${1:-}" == "--strict" ]]; then
  STRICT_MODE=1
  shift
fi

if [[ "$STRICT_MODE" == "1" ]]; then
  DOCTOR_ARGS+=("--strict")
fi

python3 executor/doctor.py "${DOCTOR_ARGS[@]}" "$@"

echo "[setup] next steps:"
echo "  1. Fill ZIGZAG_ALPHA_USERNAME / ZIGZAG_ALPHA_PASSWORD in .env"
echo "  2. Re-run ./scripts/doctor.sh until all FAIL items are cleared"
echo "     - strict mode: ./scripts/setup_env.sh --strict"
echo "     - JSON output: python3 executor/doctor.py --json"
echo "  3. Run ./scripts/run_scenario_chrome.sh <scenario.scn>"
