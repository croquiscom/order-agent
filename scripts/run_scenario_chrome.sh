#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIO_PATH="${1:-scenarios/zigzag/alpha_direct_buy_complete_normal.scn}"

export AGENT_BROWSER_HEADED="${AGENT_BROWSER_HEADED:-1}"
export ORDER_AGENT_BROWSER_AUTO_CONNECT="${ORDER_AGENT_BROWSER_AUTO_CONNECT:-1}"

cd "$ROOT_DIR"
python3 executor/execute_scenario.py "$SCENARIO_PATH"
