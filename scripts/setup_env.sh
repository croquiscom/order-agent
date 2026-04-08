#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "[setup] created .env from .env.example"
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
