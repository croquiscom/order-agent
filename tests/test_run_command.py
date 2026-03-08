"""run_scenario / to_agent_browser_args 테스트 (mock 사용)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.zigzag.scripts.execute_scenario import (
    _role_button_fallback_click_args,
    _text_fallback_click_args,
    ScenarioCommand,
    to_agent_browser_args,
    validate_command,
    run_scenario,
)


class TestToAgentBrowserArgs:
    def test_navigate(self):
        cmd = ScenarioCommand(line_no=1, action="NAVIGATE", args=["https://www.zigzag.kr"])
        assert to_agent_browser_args(cmd) == ["open", "https://www.zigzag.kr"]

    def test_click(self):
        cmd = ScenarioCommand(line_no=2, action="CLICK", args=["login_button"])
        assert to_agent_browser_args(cmd) == ["click", "@login_button"]

    def test_fill(self):
        cmd = ScenarioCommand(line_no=3, action="FILL", args=["email", "testuser@example.com"])
        assert to_agent_browser_args(cmd) == ["fill", "@email", "testuser@example.com"]

    def test_wait_for(self):
        cmd = ScenarioCommand(line_no=4, action="WAIT_FOR", args=["search_results"])
        assert to_agent_browser_args(cmd) == ["wait", "@search_results"]

    def test_check(self):
        cmd = ScenarioCommand(line_no=5, action="CHECK", args=["order_complete_message"])
        assert to_agent_browser_args(cmd) == ["is", "visible", "@order_complete_message"]

    def test_press(self):
        cmd = ScenarioCommand(line_no=6, action="PRESS", args=["Escape"])
        assert to_agent_browser_args(cmd) == ["press", "Escape"]

    def test_eval(self):
        cmd = ScenarioCommand(line_no=7, action="EVAL", args=["document.title"])
        assert to_agent_browser_args(cmd) == ["eval", "document.title"]


class TestClickFallback:
    def test_text_selector_fallback(self):
        assert _text_fallback_click_args("text=포인트 전액사용") == ["find", "text", "포인트 전액사용", "click"]

    def test_non_text_selector_no_fallback(self):
        assert _text_fallback_click_args("@confirm_payment") is None

    def test_role_button_fallback(self):
        assert _role_button_fallback_click_args("text=0원 구매하기") == [
            "find",
            "role",
            "button",
            "click",
            "--name",
            "0원 구매하기",
        ]


class TestValidateCommand:
    def test_navigate_requires_one_arg(self):
        cmd = ScenarioCommand(line_no=1, action="NAVIGATE", args=[])
        with pytest.raises(ValueError, match="requires exactly 1 argument"):
            validate_command(cmd)

    def test_fill_requires_two_args(self):
        cmd = ScenarioCommand(line_no=1, action="FILL", args=["email"])
        with pytest.raises(ValueError, match="FILL requires field_id and value"):
            validate_command(cmd)

    def test_check_url_requires_one_arg(self):
        cmd = ScenarioCommand(line_no=1, action="CHECK_URL", args=[])
        with pytest.raises(ValueError, match="requires exactly 1 argument"):
            validate_command(cmd)

    def test_wait_url_requires_one_arg(self):
        cmd = ScenarioCommand(line_no=1, action="WAIT_URL", args=[])
        with pytest.raises(ValueError, match="requires exactly 1 argument"):
            validate_command(cmd)

    def test_dump_state_requires_one_arg(self):
        cmd = ScenarioCommand(line_no=1, action="DUMP_STATE", args=[])
        with pytest.raises(ValueError, match="requires exactly 1 argument"):
            validate_command(cmd)

    def test_check_new_order_sheet_requires_no_arg(self):
        cmd = ScenarioCommand(line_no=1, action="CHECK_NEW_ORDER_SHEET", args=["unexpected"])
        with pytest.raises(ValueError, match="requires no arguments"):
            validate_command(cmd)

    def test_save_order_detail_id_requires_no_arg(self):
        cmd = ScenarioCommand(line_no=1, action="SAVE_ORDER_DETAIL_ID", args=["unexpected"])
        with pytest.raises(ValueError, match="requires no arguments"):
            validate_command(cmd)

    def test_check_order_detail_id_changed_requires_no_arg(self):
        cmd = ScenarioCommand(line_no=1, action="CHECK_ORDER_DETAIL_ID_CHANGED", args=["unexpected"])
        with pytest.raises(ValueError, match="requires no arguments"):
            validate_command(cmd)

    def test_save_order_number_requires_no_arg(self):
        cmd = ScenarioCommand(line_no=1, action="SAVE_ORDER_NUMBER", args=["unexpected"])
        with pytest.raises(ValueError, match="requires no arguments"):
            validate_command(cmd)

    def test_check_order_number_changed_requires_no_arg(self):
        cmd = ScenarioCommand(line_no=1, action="CHECK_ORDER_NUMBER_CHANGED", args=["unexpected"])
        with pytest.raises(ValueError, match="requires no arguments"):
            validate_command(cmd)

    def test_eval_requires_one_arg(self):
        cmd = ScenarioCommand(line_no=1, action="EVAL", args=[])
        with pytest.raises(ValueError, match="requires exactly 1 argument"):
            validate_command(cmd)

    def test_ensure_login_alpha_requires_one_arg(self):
        cmd = ScenarioCommand(line_no=1, action="ENSURE_LOGIN_ALPHA", args=[])
        with pytest.raises(ValueError, match="requires exactly 1 argument"):
            validate_command(cmd)

    def test_click_snapshot_text_requires_one_arg(self):
        cmd = ScenarioCommand(line_no=1, action="CLICK_SNAPSHOT_TEXT", args=[])
        with pytest.raises(ValueError, match="requires exactly 1 argument"):
            validate_command(cmd)

    def test_select_cart_item_by_text_requires_one_arg(self):
        cmd = ScenarioCommand(line_no=1, action="SELECT_CART_ITEM_BY_TEXT", args=[])
        with pytest.raises(ValueError, match="requires exactly 1 argument"):
            validate_command(cmd)

    def test_print_active_modal_requires_no_arg(self):
        cmd = ScenarioCommand(line_no=1, action="PRINT_ACTIVE_MODAL", args=["unexpected"])
        with pytest.raises(ValueError, match="requires no arguments"):
            validate_command(cmd)

    def test_check_payment_result_requires_no_arg(self):
        cmd = ScenarioCommand(line_no=1, action="CHECK_PAYMENT_RESULT", args=["unexpected"])
        with pytest.raises(ValueError, match="requires no arguments"):
            validate_command(cmd)

    def test_blocked_payment_click(self):
        cmd = ScenarioCommand(line_no=1, action="CLICK", args=["confirm_payment"])
        with pytest.raises(ValueError, match="blocked by safety guard"):
            validate_command(cmd)

    def test_allowed_payment_click_with_env(self):
        cmd = ScenarioCommand(line_no=1, action="CLICK", args=["confirm_payment"])
        with patch.dict(os.environ, {"ALLOW_REAL_PAYMENT": "1"}):
            validate_command(cmd)  # should not raise


class TestDryRun:
    def test_dry_run_does_not_call_browser(self):
        scn_path = (
            Path(__file__).resolve().parents[1]
            / "services" / "zigzag" / "scenarios" / "alpha_pdp_direct_order_complete_100136725.scn"
        )
        with patch.dict(os.environ, {"ALLOW_REAL_PAYMENT": "1"}):
            with patch("services.zigzag.scripts.execute_scenario.agent_browser") as mock_browser:
                exit_code = run_scenario(scn_path, dry_run=True, continue_on_error=False)

        mock_browser.assert_not_called()
        assert exit_code == 0
