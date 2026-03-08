"""Claude API를 통해 시나리오를 자동 생성하는 스크립트."""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

import anthropic

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"
DEFAULT_OUTPUT = SCENARIO_DIR / "generated_zigzag.scn"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
ALLOWED_ACTIONS = {"NAVIGATE", "CLICK", "FILL", "WAIT_FOR", "CHECK"}
BLOCKED_CLICK_TARGETS = {"confirm_payment"}

SYSTEM_PROMPT = """\
You are a test scenario generator for the Zigzag e-commerce platform.
Generate scenarios using these commands:
- NAVIGATE <url>
- CLICK <element_id>
- FILL <field_id> <value>
- WAIT_FOR <element_id>
- CHECK <element_id>

Rules:
- Base test domain must be https://alpha.zigzag.kr/
- Use test accounts only (testuser@example.com / correct_password)
- Never trigger real payments
- Use test_card_info for payment fields
- Do not output CLICK confirm_payment
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
        args = tokens[1:]
        if action in {"NAVIGATE", "CLICK", "WAIT_FOR", "CHECK"} and len(args) != 1:
            raise ValueError(f"line {line_no}: {action} requires exactly 1 argument")
        if action == "FILL" and len(args) < 2:
            raise ValueError(f"line {line_no}: FILL requires field_id and value")
        if action == "CLICK" and args[0] in BLOCKED_CLICK_TARGETS:
            raise ValueError(f"line {line_no}: CLICK {args[0]} is blocked by safety policy")


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
