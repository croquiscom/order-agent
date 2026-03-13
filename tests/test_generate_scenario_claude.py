"""generate_scenario_claude validation tests."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from executor.generate_scenario_claude import validate_scenario_text


def test_validate_scenario_text_accepts_extended_actions():
    validate_scenario_text(
        "\n".join(
            [
                "ENSURE_LOGIN_ALPHA https://alpha.zigzag.kr/checkout/orders",
                "SAVE_ORDER_NUMBER",
                "NAVIGATE https://alpha.zigzag.kr/cart",
                "WAIT_FOR 1000",
                "SUBMIT_EXCHANGE_REQUEST __ASK__",
                "EXPECT_FAIL",
                "PRINT_ACTIVE_MODAL",
            ]
        )
    )


def test_validate_scenario_text_blocks_confirm_payment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ALLOW_REAL_PAYMENT", raising=False)
    with pytest.raises(ValueError, match="blocked by safety guard"):
        validate_scenario_text("CLICK confirm_payment\n")
