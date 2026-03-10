"""시나리오 파싱 로직 테스트."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from executor.execute_scenario import parse_scenario, ScenarioCommand


def _write_scn(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".scn", delete=False, encoding="utf-8")
    f.write(content)
    f.flush()
    f.close()
    return Path(f.name)


def test_parse_basic_commands():
    path = _write_scn(
        "NAVIGATE https://www.zigzag.kr\n"
        "CLICK login_button\n"
        "FILL email testuser@example.com\n"
        "WAIT_FOR product_search_box\n"
        "CHECK order_complete_message\n"
    )
    commands = parse_scenario(path)

    assert len(commands) == 5
    assert commands[0].action == "NAVIGATE"
    assert commands[0].args == ["https://www.zigzag.kr"]
    assert commands[1].action == "CLICK"
    assert commands[1].args == ["login_button"]
    assert commands[2].action == "FILL"
    assert commands[2].args == ["email", "testuser@example.com"]
    assert commands[3].action == "WAIT_FOR"
    assert commands[4].action == "CHECK"


def test_parse_skips_comments_and_blank_lines():
    path = _write_scn(
        "# 로그인 단계\n"
        "NAVIGATE https://www.zigzag.kr\n"
        "\n"
        "# 빈 줄 위아래\n"
        "CLICK login_button\n"
    )
    commands = parse_scenario(path)
    assert len(commands) == 2
    assert commands[0].action == "NAVIGATE"
    assert commands[1].action == "CLICK"


def test_parse_empty_file():
    path = _write_scn("")
    commands = parse_scenario(path)
    assert commands == []


def test_parse_unknown_action_raises():
    path = _write_scn("SUBMIT\n")
    with pytest.raises(ValueError, match="unknown action 'SUBMIT'"):
        parse_scenario(path)


def test_parse_real_scenario_file():
    scn_path = (
        Path(__file__).resolve().parents[1]
        / "scenarios"
        / "zigzag"
        / "alpha_direct_buy_complete_normal.scn"
    )
    commands = parse_scenario(scn_path)

    assert len(commands) > 10
    assert commands[0].action == "ENSURE_LOGIN_ALPHA"
    assert any(c.action == "CHECK_NEW_ORDER_SHEET" for c in commands)
    assert any(c.action == "CLICK_SNAPSHOT_TEXT" for c in commands)


def test_parse_quoted_value():
    path = _write_scn('FILL product_search_box "원하는상품명"\n')
    commands = parse_scenario(path)
    assert len(commands) == 1
    assert commands[0].args == ["product_search_box", "원하는상품명"]


def test_parse_press_and_check_url():
    path = _write_scn(
        "PRESS Escape\n"
        "CHECK_URL /checkout/order-sheets/\n"
        "WAIT_URL /checkout/order-sheets/\n"
        "DUMP_STATE before_zero_pay\n"
        "CHECK_NEW_ORDER_SHEET\n"
        "SAVE_ORDER_DETAIL_ID\n"
        "CHECK_ORDER_DETAIL_ID_CHANGED\n"
        "SAVE_ORDER_NUMBER\n"
        "CHECK_ORDER_NUMBER_CHANGED\n"
        "ENSURE_LOGIN_ALPHA https://alpha.zigzag.kr/checkout/orders\n"
        "EVAL document.title\n"
        "CLICK_SNAPSHOT_TEXT 포인트 전액사용\n"
        "SELECT_CART_ITEM_BY_TEXT 마이스토어 테스트 상세페이지로 이동\n"
        "PRINT_ACTIVE_MODAL\n"
        "CHECK_PAYMENT_RESULT\n"
    )
    commands = parse_scenario(path)
    assert len(commands) == 15
    assert commands[0].action == "PRESS"
    assert commands[1].action == "CHECK_URL"
    assert commands[2].action == "WAIT_URL"
    assert commands[3].action == "DUMP_STATE"
    assert commands[4].action == "CHECK_NEW_ORDER_SHEET"
    assert commands[5].action == "SAVE_ORDER_DETAIL_ID"
    assert commands[6].action == "CHECK_ORDER_DETAIL_ID_CHANGED"
    assert commands[7].action == "SAVE_ORDER_NUMBER"
    assert commands[8].action == "CHECK_ORDER_NUMBER_CHANGED"
    assert commands[9].action == "ENSURE_LOGIN_ALPHA"
    assert commands[10].action == "EVAL"
    assert commands[11].action == "CLICK_SNAPSHOT_TEXT"
    assert commands[12].action == "SELECT_CART_ITEM_BY_TEXT"
    assert commands[13].action == "PRINT_ACTIVE_MODAL"
    assert commands[14].action == "CHECK_PAYMENT_RESULT"
