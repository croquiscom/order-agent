"""시나리오 파싱 로직 테스트."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from executor.execute_scenario import (
    parse_scenario,
    ScenarioCommand,
    _validate_control_flow,
    _eval_condition,
)


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
        / "checkout"
        / "alpha_direct_buy_complete_normal.scn"
    )
    commands = parse_scenario(scn_path)

    assert len(commands) > 10
    assert commands[0].action == "ENSURE_LOGIN_ZIGZAG_ALPHA"
    assert any(c.action == "CHECK_NEW_ORDER_SHEET" for c in commands)
    assert any(c.action == "CLICK_SNAPSHOT_TEXT" for c in commands)


def test_parse_quoted_value():
    path = _write_scn('FILL product_search_box "원하는상품명"\n')
    commands = parse_scenario(path)
    assert len(commands) == 1
    assert commands[0].args == ["product_search_box", "원하는상품명"]


def test_include_basic(tmp_path):
    """INCLUDE inlines commands from another file."""
    inc = tmp_path / "common.scn"
    inc.write_text("NAVIGATE https://example.com\nCLICK login_btn\n", encoding="utf-8")
    main = tmp_path / "main.scn"
    main.write_text(
        "CHECK_URL /home\n"
        "INCLUDE common.scn\n"
        "PRESS Escape\n",
        encoding="utf-8",
    )
    commands = parse_scenario(main)
    assert len(commands) == 4
    assert commands[0].action == "CHECK_URL"
    assert commands[0].source_file is None
    assert commands[1].action == "NAVIGATE"
    assert commands[1].source_file == inc
    assert commands[2].action == "CLICK"
    assert commands[2].source_file == inc
    assert commands[3].action == "PRESS"
    assert commands[3].source_file is None


def test_include_relative_path(tmp_path):
    """INCLUDE resolves paths relative to the including file's directory."""
    common_dir = tmp_path / "_blocks"
    common_dir.mkdir()
    inc = common_dir / "login.scn"
    inc.write_text("NAVIGATE https://example.com\n", encoding="utf-8")

    sub_dir = tmp_path / "scenarios"
    sub_dir.mkdir()
    main = sub_dir / "main.scn"
    main.write_text("INCLUDE ../_blocks/login.scn\nCLICK btn\n", encoding="utf-8")

    commands = parse_scenario(main)
    assert len(commands) == 2
    assert commands[0].action == "NAVIGATE"
    assert commands[0].source_file == inc


def test_include_nested(tmp_path):
    """Nested INCLUDE works up to depth limit."""
    leaf = tmp_path / "leaf.scn"
    leaf.write_text("CHECK_URL /done\n", encoding="utf-8")
    mid = tmp_path / "mid.scn"
    mid.write_text("INCLUDE leaf.scn\n", encoding="utf-8")
    top = tmp_path / "top.scn"
    top.write_text("NAVIGATE https://example.com\nINCLUDE mid.scn\n", encoding="utf-8")

    commands = parse_scenario(top)
    assert len(commands) == 2
    assert commands[0].action == "NAVIGATE"
    assert commands[1].action == "CHECK_URL"
    # Leaf command gets source_file = leaf (set when parsed within mid)
    assert commands[1].source_file == leaf


def test_include_circular_raises(tmp_path):
    """Circular INCLUDE raises ValueError."""
    a = tmp_path / "a.scn"
    b = tmp_path / "b.scn"
    a.write_text("INCLUDE b.scn\n", encoding="utf-8")
    b.write_text("INCLUDE a.scn\n", encoding="utf-8")

    with pytest.raises(ValueError, match="circular INCLUDE"):
        parse_scenario(a)


def test_include_self_circular(tmp_path):
    """File including itself is detected as circular."""
    a = tmp_path / "self.scn"
    a.write_text("INCLUDE self.scn\n", encoding="utf-8")

    with pytest.raises(ValueError, match="circular INCLUDE"):
        parse_scenario(a)


def test_include_file_not_found(tmp_path):
    """INCLUDE with non-existent file raises FileNotFoundError."""
    main = tmp_path / "main.scn"
    main.write_text("INCLUDE nonexistent.scn\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="INCLUDE file not found"):
        parse_scenario(main)


def test_include_max_depth(tmp_path):
    """INCLUDE depth exceeding max raises ValueError."""
    # Create a chain of 7 files: level0 includes level1, ..., level5 includes level6
    # level0 is at depth 0, so level5->level6 would be depth 6 (exceeds limit of 5)
    files = []
    for i in range(7):
        f = tmp_path / f"level{i}.scn"
        files.append(f)
    # Leaf file has a real command
    files[6].write_text("CHECK_URL /end\n", encoding="utf-8")
    # Each file includes the next
    for i in range(6):
        files[i].write_text(f"INCLUDE level{i+1}.scn\n", encoding="utf-8")

    with pytest.raises(ValueError, match="INCLUDE depth exceeds maximum"):
        parse_scenario(files[0])


def test_include_missing_path_raises(tmp_path):
    """INCLUDE without a path argument raises ValueError."""
    main = tmp_path / "main.scn"
    main.write_text("INCLUDE\n", encoding="utf-8")

    with pytest.raises(ValueError, match="INCLUDE requires a file path"):
        parse_scenario(main)


def test_include_preserves_source_file_in_nested(tmp_path):
    """source_file is set correctly for deeply nested includes."""
    inner = tmp_path / "inner.scn"
    inner.write_text("NAVIGATE https://inner.com\n", encoding="utf-8")
    outer = tmp_path / "outer.scn"
    outer.write_text("INCLUDE inner.scn\n", encoding="utf-8")
    main = tmp_path / "main.scn"
    main.write_text("CLICK btn\nINCLUDE outer.scn\n", encoding="utf-8")

    commands = parse_scenario(main)
    assert len(commands) == 2
    assert commands[0].source_file is None  # Direct command
    assert commands[1].source_file == inner  # From inner, preserved through outer


def test_include_real_exchange_scenario():
    """Refactored exchange scenario with INCLUDEs parses correctly."""
    scn_path = (
        Path(__file__).resolve().parents[1]
        / "scenarios"
        / "zigzag"
        / "claim"
        / "exchange"
        / "alpha_claim_exchange.scn"
    )
    commands = parse_scenario(scn_path)

    # Should have commands from main + 3 included files
    assert len(commands) > 5
    # First commands are from main file
    assert commands[0].action == "PICK_ORDER_FROM_POOL"
    assert commands[0].source_file is None
    # Some commands should have source_file set (from includes)
    included = [c for c in commands if c.source_file is not None]
    assert len(included) > 0


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
        "ENSURE_LOGIN_ZIGZAG_ALPHA https://alpha.zigzag.kr/checkout/orders\n"
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
    assert commands[9].action == "ENSURE_LOGIN_ZIGZAG_ALPHA"
    assert commands[10].action == "EVAL"
    assert commands[11].action == "CLICK_SNAPSHOT_TEXT"
    assert commands[12].action == "SELECT_CART_ITEM_BY_TEXT"
    assert commands[13].action == "PRINT_ACTIVE_MODAL"
    assert commands[14].action == "CHECK_PAYMENT_RESULT"


# ── IF/ELSE_IF/ELSE/ENDIF tests ──────────────────────────────────────


class TestParseIfElse:
    """IF/ELSE_IF/ELSE/ENDIF parsing tests."""

    def test_parse_if_endif(self):
        path = _write_scn(
            'IF {{MODE}} == "fast"\n'
            "NAVIGATE https://example.com/fast\n"
            "ENDIF\n"
        )
        commands = parse_scenario(path)
        assert len(commands) == 3
        assert commands[0].action == "IF"
        assert commands[0].args == ["{{MODE}}", "==", "fast"]
        assert commands[1].action == "NAVIGATE"
        assert commands[2].action == "ENDIF"

    def test_parse_else_if_as_two_words(self):
        """'ELSE IF' is normalised to ELSE_IF."""
        path = _write_scn(
            'IF {{X}} == "a"\n'
            "NAVIGATE https://a.com\n"
            'ELSE IF {{X}} == "b"\n'
            "NAVIGATE https://b.com\n"
            "ENDIF\n"
        )
        commands = parse_scenario(path)
        assert commands[2].action == "ELSE_IF"
        assert commands[2].args == ["{{X}}", "==", "b"]

    def test_parse_else_if_single_word(self):
        """ELSE_IF as a single token works."""
        path = _write_scn(
            'IF {{X}} == "a"\n'
            "NAVIGATE https://a.com\n"
            'ELSE_IF {{X}} == "b"\n'
            "NAVIGATE https://b.com\n"
            "ENDIF\n"
        )
        commands = parse_scenario(path)
        assert commands[2].action == "ELSE_IF"

    def test_parse_if_else_endif(self):
        path = _write_scn(
            'IF {{MODE}} == "fast"\n'
            "NAVIGATE https://fast.com\n"
            "ELSE\n"
            "NAVIGATE https://slow.com\n"
            "ENDIF\n"
        )
        commands = parse_scenario(path)
        assert len(commands) == 5
        assert commands[0].action == "IF"
        assert commands[2].action == "ELSE"
        assert commands[4].action == "ENDIF"

    def test_parse_if_exists(self):
        path = _write_scn(
            "IF {{HAS_COST}} exists\n"
            "NAVIGATE https://cost.com\n"
            "ENDIF\n"
        )
        commands = parse_scenario(path)
        assert commands[0].action == "IF"
        assert commands[0].args == ["{{HAS_COST}}", "exists"]


class TestValidateControlFlow:
    """_validate_control_flow tests."""

    def _cmds(self, *actions):
        return [ScenarioCommand(line_no=i + 1, action=a, args=[]) for i, a in enumerate(actions)]

    def test_balanced_if_endif(self):
        cmds = self._cmds("IF", "NAVIGATE", "ENDIF")
        # Give IF valid args for validation
        cmds[0].args = ["{{X}}", "exists"]
        table = _validate_control_flow(cmds)
        assert 0 in table  # IF -> ENDIF
        assert table[0] == 2

    def test_if_else_endif(self):
        cmds = self._cmds("IF", "NAVIGATE", "ELSE", "NAVIGATE", "ENDIF")
        cmds[0].args = ["{{X}}", "exists"]
        table = _validate_control_flow(cmds)
        assert table[0] == 2  # IF -> ELSE
        assert table[2] == 4  # ELSE -> ENDIF

    def test_if_elseif_else_endif(self):
        cmds = self._cmds("IF", "NAVIGATE", "ELSE_IF", "NAVIGATE", "ELSE", "NAVIGATE", "ENDIF")
        cmds[0].args = ["{{X}}", "==", "a"]
        cmds[2].args = ["{{X}}", "==", "b"]
        table = _validate_control_flow(cmds)
        assert table[0] == 2  # IF -> ELSE_IF
        assert table[2] == 4  # ELSE_IF -> ELSE
        assert table[4] == 6  # ELSE -> ENDIF

    def test_unbalanced_if_raises(self):
        cmds = self._cmds("IF", "NAVIGATE")
        cmds[0].args = ["{{X}}", "exists"]
        with pytest.raises(ValueError, match="IF without matching ENDIF"):
            _validate_control_flow(cmds)

    def test_orphan_endif_raises(self):
        cmds = self._cmds("NAVIGATE", "ENDIF")
        with pytest.raises(ValueError, match="ENDIF without matching IF"):
            _validate_control_flow(cmds)

    def test_orphan_else_raises(self):
        cmds = self._cmds("NAVIGATE", "ELSE")
        with pytest.raises(ValueError, match="ELSE without matching IF"):
            _validate_control_flow(cmds)

    def test_max_nesting_exceeded(self):
        # 4 levels of nesting should fail (max is 3)
        cmds = self._cmds("IF", "IF", "IF", "IF", "NAVIGATE", "ENDIF", "ENDIF", "ENDIF", "ENDIF")
        for c in cmds:
            if c.action == "IF":
                c.args = ["{{X}}", "exists"]
        with pytest.raises(ValueError, match="nesting exceeds maximum"):
            _validate_control_flow(cmds)

    def test_nested_3_levels_ok(self):
        cmds = self._cmds("IF", "IF", "IF", "NAVIGATE", "ENDIF", "ENDIF", "ENDIF")
        for c in cmds:
            if c.action == "IF":
                c.args = ["{{X}}", "exists"]
        table = _validate_control_flow(cmds)
        assert len(table) > 0

    def test_else_after_else_raises(self):
        cmds = self._cmds("IF", "ELSE", "ELSE", "ENDIF")
        cmds[0].args = ["{{X}}", "exists"]
        with pytest.raises(ValueError, match="ELSE after ELSE"):
            _validate_control_flow(cmds)

    def test_elseif_after_else_raises(self):
        cmds = self._cmds("IF", "ELSE", "ELSE_IF", "ENDIF")
        cmds[0].args = ["{{X}}", "exists"]
        cmds[2].args = ["{{X}}", "==", "a"]
        with pytest.raises(ValueError, match="ELSE_IF after ELSE"):
            _validate_control_flow(cmds)


class TestEvalCondition:
    """_eval_condition tests."""

    def test_eq_true(self):
        assert _eval_condition(["exchange", "==", "exchange"], {}) is True

    def test_eq_false(self):
        assert _eval_condition(["exchange", "==", "return"], {}) is False

    def test_neq_true(self):
        assert _eval_condition(["exchange", "!=", "return"], {}) is True

    def test_neq_false(self):
        assert _eval_condition(["exchange", "!=", "exchange"], {}) is False

    def test_contains_true(self):
        assert _eval_condition(["hello world", "contains", "world"], {}) is True

    def test_contains_false(self):
        assert _eval_condition(["hello", "contains", "world"], {}) is False

    def test_not_contains_true(self):
        assert _eval_condition(["hello", "not_contains", "world"], {}) is True

    def test_not_contains_false(self):
        assert _eval_condition(["hello world", "not_contains", "world"], {}) is False

    def test_exists_true(self):
        assert _eval_condition(["somevalue", "exists"], {}) is True

    def test_exists_false_empty(self):
        assert _eval_condition(["", "exists"], {}) is False

    def test_not_exists_true(self):
        assert _eval_condition(["", "not_exists"], {}) is True

    def test_not_exists_false(self):
        assert _eval_condition(["somevalue", "not_exists"], {}) is False

    def test_var_resolution(self):
        """{{VAR}} in args is resolved from _vars."""
        assert _eval_condition(["{{MODE}}", "==", "fast"], {"mode": "fast"}) is True
        assert _eval_condition(["{{MODE}}", "==", "slow"], {"mode": "fast"}) is False

    def test_undefined_var_is_empty(self):
        """Undefined var resolves to empty string."""
        assert _eval_condition(["{{UNDEF}}", "exists"], {}) is False
        assert _eval_condition(["{{UNDEF}}", "not_exists"], {}) is True
        assert _eval_condition(["{{UNDEF}}", "==", ""], {}) is True

    def test_unsupported_operator_raises(self):
        with pytest.raises(ValueError, match="unsupported"):
            _eval_condition(["a", ">=", "b"], {})

    def test_unsupported_2arg_operator_raises(self):
        with pytest.raises(ValueError, match="unsupported"):
            _eval_condition(["a", "defined"], {})
