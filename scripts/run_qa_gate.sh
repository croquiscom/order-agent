#!/usr/bin/env bash
# QA Gate: P0 시나리오 실행 후 실패 시 슬랙 알림
#
# 사용법:
#   # P0만 실행 + 실패 시 슬랙 알림
#   ./scripts/run_qa_gate.sh
#
#   # 특정 과제만
#   ./scripts/run_qa_gate.sh --tag task=ORDER-11850
#
#   # P1까지 포함
#   ./scripts/run_qa_gate.sh --tag priority=P1
#
#   # dry-run 검증
#   ./scripts/run_qa_gate.sh --dry-run
#
# 환경변수:
#   ORDER_QA_SLACK_WEBHOOK  — 슬랙 Incoming Webhook URL
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 기본: P0 + 실패 시 슬랙
python3 scripts/run_regression.py \
    --tier regression \
    --tag priority=P0 \
    --slack-on-fail \
    "$@"
