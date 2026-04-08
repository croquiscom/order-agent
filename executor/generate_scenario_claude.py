"""Claude API를 통해 시나리오를 자동 생성하는 스크립트."""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

import anthropic

from executor.execute_scenario import (
    ALLOWED_ACTIONS,
    BLOCKED_CLICK_TARGETS,
    ScenarioCommand,
    validate_command,
)

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios" / "zigzag"
DEFAULT_OUTPUT = SCENARIO_DIR / "generated_zigzag.scn"
DEFAULT_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """\
You are a test scenario generator for the Zigzag e-commerce platform.
Generate scenarios using the order-agent DSL only.

Allowed actions:
- NAVIGATE <url>
- CLICK <selector>
- FILL <selector> <value>
- WAIT_FOR <selector|ms>
- CHECK <selector>
- PRESS <key>
- CHECK_URL <substring>
- CHECK_NOT_URL <substring>
- WAIT_URL <substring>
- DUMP_STATE <tag>
- CHECK_NEW_ORDER_SHEET
- SAVE_ORDER_DETAIL_ID
- CHECK_ORDER_DETAIL_ID_CHANGED
- SAVE_ORDER_NUMBER
- CHECK_ORDER_NUMBER_CHANGED
- ENSURE_LOGIN_ZIGZAG_ALPHA <url>
- ENSURE_LOGIN_GRAFANA [url]
- ENSURE_LOGIN_AWS_SSO [url]
- EVAL <javascript>
- CLICK_SNAPSHOT_TEXT <text>
- CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT <text>
- SELECT_CART_ITEM_BY_TEXT <text>
- CLICK_ORDER_DETAIL_BY_STATUS <status>
- CLICK_ORDER_DETAIL_WITH_ACTION <action>
- APPLY_ORDER_STATUS_FILTER <status>
- SUBMIT_CANCEL_REQUEST <reason>
- SUBMIT_RETURN_REQUEST <reason>
- SUBMIT_EXCHANGE_REQUEST <reason>
- PRINT_ACTIVE_MODAL
- CHECK_PAYMENT_RESULT
- EXPECT_FAIL [pattern]
- READ_OTP <account> [var]

Rules:
- Base test domain must be https://alpha.zigzag.kr/
- Use test accounts only
- ENSURE_LOGIN_ZIGZAG_ALPHA target must be an authenticated page such as https://alpha.zigzag.kr/checkout/orders
- ENSURE_LOGIN_GRAFANA handles Keycloak-OAuth + OTP login using GRAFANA_USERNAME/GRAFANA_PASSWORD env vars
- ENSURE_LOGIN_AWS_SSO handles AWS SSO portal login with OTP using AWS_SSO_USERNAME/AWS_SSO_PASSWORD env vars
- Prefer stable selectors: role=..., button[type=submit], input[name=...], #fixed-id
- Do not use dynamic ids such as #awsui-input-0
- Never trigger real payments; zero-payment flows only by default
- Do not output CLICK confirm_payment
- Include short # comments for major steps when useful
- Output only the scenario commands, one per line
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Zigzag scenario with Claude")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="https://alpha.zigzag.kr/에서 특정 상품을 검색하고 주문하는 시나리오를 생성해줘",
        help="Prompt for Claude scenario generation",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output scenario file path",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Anthropic model id",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="Max output tokens for Claude response",
    )
    return parser.parse_args()


def validate_scenario_text(scenario: str) -> None:
    lines = scenario.splitlines()
    if not lines:
        raise ValueError("generated scenario is empty")
    for line_no, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        tokens = shlex.split(line)
        action = tokens[0] if tokens else ""
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"line {line_no}: unknown action '{action}'")
        validate_command(ScenarioCommand(line_no=line_no, action=action, args=tokens[1:]))


def generate_scenario(prompt: str, model: str, max_tokens: int) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text_blocks = [block.text for block in message.content if getattr(block, "type", "") == "text"]
    scenario = "\n".join(text_blocks).strip()
    if not scenario:
        raise RuntimeError("Claude response did not include text content")
    return scenario


def main() -> None:
    args = parse_args()
    output_path = Path(args.output).expanduser().resolve()

    print(f"[INFO] Generating scenario with model={args.model}")
    scenario = generate_scenario(prompt=args.prompt, model=args.model, max_tokens=args.max_tokens)
    validate_scenario_text(scenario)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(scenario.rstrip() + "\n")

    print(f"[INFO] Scenario saved to: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
