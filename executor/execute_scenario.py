"""시나리오 파일을 읽어 agent-browser CLI로 실행하는 스크립트."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shlex
import sys
import threading
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.logger import setup_logger
from core.runner import AgentBrowserError, agent_browser

DEFAULT_SCENARIO = REPO_ROOT / "scenarios" / "zigzag" / "alpha_direct_buy_complete_normal.scn"
ALLOWED_ACTIONS = {
    "NAVIGATE",
    "CLICK",
    "FILL",
    "WAIT_FOR",
    "CHECK",
    "PRESS",
    "CHECK_URL",
    "CHECK_NOT_URL",
    "WAIT_URL",
    "DUMP_STATE",
    "CHECK_NEW_ORDER_SHEET",
    "SAVE_ORDER_DETAIL_ID",
    "CHECK_ORDER_DETAIL_ID_CHANGED",
    "SAVE_ORDER_NUMBER",
    "CHECK_ORDER_NUMBER_CHANGED",
    "ENSURE_LOGIN_ALPHA",
    "EVAL",
    "CLICK_SNAPSHOT_TEXT",
    "CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT",
    "SELECT_CART_ITEM_BY_TEXT",
    "CLICK_ORDER_DETAIL_BY_STATUS",
    "CLICK_ORDER_DETAIL_WITH_ACTION",
    "APPLY_ORDER_STATUS_FILTER",
    "SUBMIT_CANCEL_REQUEST",
    "SUBMIT_RETURN_REQUEST",
    "SUBMIT_EXCHANGE_REQUEST",
    "PRINT_ACTIVE_MODAL",
    "CHECK_PAYMENT_RESULT",
    "EXPECT_FAIL",
    "READ_OTP",
}
BLOCKED_CLICK_TARGETS = {"confirm_payment"}
ORDER_SHEET_ID_PATTERN = re.compile(r"/checkout/order-sheets/([a-f0-9-]+)")
LAST_ORDER_SHEET_FILE = REPO_ROOT / "logs" / "last_order_sheet_id.txt"
ORDER_DETAIL_ID_PATTERN = re.compile(r"/checkout/(?:orders|order-completed)/([0-9]+)")
SNAPSHOT_REF_PATTERN = re.compile(r'^\-\s+\w+\s+"([^"]+)"\s+\[ref=([^\]]+)\]')
SNAPSHOT_NODE_PATTERN = re.compile(r'^\-\s+(\w+)(?:\s+"([^"]*)")?\s+\[ref=([^\]]+)\]')
SNAPSHOT_CART_COUNT_PATTERN = re.compile(r"전체선택\s*\((\d+)\s*/\s*(\d+)\)")


@dataclass
class ScenarioCommand:
    line_no: int
    action: str
    args: list[str]


def parse_scenario(path: Path) -> list[ScenarioCommand]:
    commands: list[ScenarioCommand] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                tokens = shlex.split(line)
            except ValueError as exc:
                raise ValueError(f"line {line_no}: invalid quoting - {exc}") from exc
            if not tokens:
                continue
            action = tokens[0]
            if action not in ALLOWED_ACTIONS:
                raise ValueError(f"line {line_no}: unknown action '{action}'")
            commands.append(ScenarioCommand(line_no=line_no, action=action, args=tokens[1:]))
    return commands


def validate_command(command: ScenarioCommand) -> None:
    action = command.action
    args = command.args
    line_no = command.line_no

    if action in {"NAVIGATE", "CLICK", "WAIT_FOR", "CHECK", "PRESS", "CHECK_URL", "CHECK_NOT_URL", "WAIT_URL", "DUMP_STATE", "EVAL", "ENSURE_LOGIN_ALPHA", "CLICK_SNAPSHOT_TEXT", "CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT", "SELECT_CART_ITEM_BY_TEXT", "CLICK_ORDER_DETAIL_BY_STATUS", "CLICK_ORDER_DETAIL_WITH_ACTION", "APPLY_ORDER_STATUS_FILTER", "SUBMIT_CANCEL_REQUEST", "SUBMIT_RETURN_REQUEST", "SUBMIT_EXCHANGE_REQUEST"} and len(args) != 1:
        raise ValueError(f"line {line_no}: {action} requires exactly 1 argument")
    if action == "PRINT_ACTIVE_MODAL" and len(args) != 0:
        raise ValueError(f"line {line_no}: PRINT_ACTIVE_MODAL requires no arguments")
    if action == "CHECK_NEW_ORDER_SHEET" and len(args) != 0:
        raise ValueError(f"line {line_no}: CHECK_NEW_ORDER_SHEET requires no arguments")
    if action in {
        "SAVE_ORDER_DETAIL_ID",
        "CHECK_ORDER_DETAIL_ID_CHANGED",
        "SAVE_ORDER_NUMBER",
        "CHECK_ORDER_NUMBER_CHANGED",
        "PRINT_ACTIVE_MODAL",
        "CHECK_PAYMENT_RESULT",
    } and len(args) != 0:
        raise ValueError(f"line {line_no}: {action} requires no arguments")
    if action == "EXPECT_FAIL" and len(args) > 1:
        raise ValueError(f"line {line_no}: EXPECT_FAIL takes 0 or 1 argument (optional error code pattern)")
    if action == "READ_OTP" and not (1 <= len(args) <= 2):
        raise ValueError(f"line {line_no}: READ_OTP requires 1-2 arguments: <account_name> [var_name]")
    if action == "FILL" and len(args) < 2:
        raise ValueError(f"line {line_no}: FILL requires field_id and value")
    if action == "CLICK" and args and args[0] in BLOCKED_CLICK_TARGETS:
        if os.getenv("ALLOW_REAL_PAYMENT") != "1":
            raise ValueError(
                f"line {line_no}: CLICK {args[0]} blocked by safety guard "
                "(set ALLOW_REAL_PAYMENT=1 to override)"
            )


def normalize_selector(selector: str) -> str:
    """Keep explicit selectors as-is; fallback to @ref style for legacy scenarios."""
    explicit_prefixes = ("@", "#", ".", "[", "/", "xpath=", "text=", "role=")
    if selector.startswith(explicit_prefixes):
        return selector
    # CSS 태그 셀렉터 (예: button[type=submit], input[name=...], div.class)
    if "[" in selector or ">" in selector:
        return selector
    return f"@{selector}"


def to_agent_browser_args(command: ScenarioCommand) -> list[str]:
    action = command.action
    args = command.args

    if action == "NAVIGATE":
        return ["open", args[0]]
    if action == "CLICK":
        return ["click", normalize_selector(args[0])]
    if action == "FILL":
        return ["fill", normalize_selector(args[0]), " ".join(args[1:])]
    if action == "WAIT_FOR":
        if args[0].isdigit():
            return ["wait", args[0]]
        return ["wait", normalize_selector(args[0])]
    if action == "CHECK":
        return ["is", "visible", normalize_selector(args[0])]
    if action == "PRESS":
        return ["press", args[0]]
    if action == "EVAL":
        return ["eval", args[0]]
    raise ValueError(f"Unsupported action: {action}")


def _text_fallback_click_args(selector: str) -> list[str] | None:
    if not selector.startswith("text="):
        return None
    value = selector[len("text="):].strip()
    if not value:
        return None
    return ["find", "text", value, "click"]


def _role_button_fallback_click_args(selector: str) -> list[str] | None:
    if not selector.startswith("text="):
        return None
    value = selector[len("text="):].strip()
    if not value:
        return None
    return ["find", "role", "button", "click", "--name", value]


def _extract_order_sheet_id(url: str) -> str | None:
    match = ORDER_SHEET_ID_PATTERN.search(url)
    if not match:
        return None
    return match.group(1)


def _extract_order_detail_id(url: str) -> str | None:
    match = ORDER_DETAIL_ID_PATTERN.search(url)
    if not match:
        return None
    return match.group(1)


def _cdp_direct_fill(selector: str, value: str) -> None:
    """CDP Input.dispatchKeyEvent를 사용해 한 글자씩 타이핑 (agent-browser CLI 우회).

    agent-browser fill은 특수문자(!, @, # 등)를 이스케이프하는 버그가 있어
    React 등 SPA 폼에서 비밀번호 등이 올바르게 입력되지 않는 문제를 우회한다.
    """
    import json
    import urllib.request
    from core.runner import _cdp_port
    port = _cdp_port()
    # agent-browser로 먼저 포커스 확보
    try:
        agent_browser("click", selector, check=True)
    except AgentBrowserError:
        agent_browser("focus", selector, check=False)
    time.sleep(0.2)
    # CDP 웹소켓으로 직접 타이핑
    try:
        resp = urllib.request.urlopen(f"http://localhost:{port}/json/list", timeout=5)
        targets = json.loads(resp.read().decode())
        # 현재 활성 페이지 찾기 (chrome-extension 제외)
        page = next(
            (t for t in targets if t["type"] == "page"
             and "chrome-extension://" not in t.get("url", "")),
            None,
        )
        if not page:
            raise RuntimeError("CDP page target not found")
        import websocket  # type: ignore
        ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
        msg_id = 1
        try:
            # Ctrl+A (전체 선택)
            ws.send(json.dumps({"id": msg_id, "method": "Input.dispatchKeyEvent", "params": {
                "type": "keyDown", "key": "a", "code": "KeyA", "modifiers": 2,
            }}))
            ws.recv(); msg_id += 1
            ws.send(json.dumps({"id": msg_id, "method": "Input.dispatchKeyEvent", "params": {
                "type": "keyUp", "key": "a", "code": "KeyA", "modifiers": 2,
            }}))
            ws.recv(); msg_id += 1
            # Backspace (삭제)
            ws.send(json.dumps({"id": msg_id, "method": "Input.dispatchKeyEvent", "params": {
                "type": "keyDown", "key": "Backspace", "code": "Backspace",
                "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8,
            }}))
            ws.recv(); msg_id += 1
            ws.send(json.dumps({"id": msg_id, "method": "Input.dispatchKeyEvent", "params": {
                "type": "keyUp", "key": "Backspace", "code": "Backspace",
                "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8,
            }}))
            ws.recv(); msg_id += 1
            # 한 글자씩 keyDown+keyUp 타이핑
            for ch in value:
                ws.send(json.dumps({"id": msg_id, "method": "Input.dispatchKeyEvent", "params": {
                    "type": "keyDown", "key": ch, "text": ch,
                }}))
                ws.recv(); msg_id += 1
                ws.send(json.dumps({"id": msg_id, "method": "Input.dispatchKeyEvent", "params": {
                    "type": "keyUp", "key": ch,
                }}))
                ws.recv(); msg_id += 1
            # 입력 검증: 실제 입력된 값 확인
            ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate", "params": {
                "expression": "document.activeElement?.value || ''"
            }}))
            verify = json.loads(ws.recv())
            actual = verify.get("result", {}).get("result", {}).get("value", "")
            if actual != value:
                import logging as _log
                _log.getLogger(__name__).warning(
                    "CDP fill mismatch: expected=%r actual=%r", value, actual
                )
        finally:
            ws.close()
    except Exception as exc:
        raise RuntimeError(f"CDP direct fill failed: {exc}")


def _is_transient_navigation_error(exc: AgentBrowserError) -> bool:
    err = (exc.stderr or "").lower()
    return (
        "execution context was destroyed" in err
        or "page.goto: timeout" in err
        or "timeout 10000ms exceeded" in err
    )


def _safe_open_url(url: str, retries: int = 5) -> None:
    """Open URL with short retries for transient navigation context errors."""
    last_exc: AgentBrowserError | None = None
    for attempt in range(1, retries + 1):
        try:
            agent_browser("open", url, check=True)
            return
        except AgentBrowserError as exc:
            last_exc = exc
            if attempt == retries or not _is_transient_navigation_error(exc):
                if not _is_transient_navigation_error(exc):
                    raise
                break
            time.sleep(0.9)
    # navigation race는 브라우저에서 실제 이동이 되었을 수 있으므로 다음 단계 URL 체크에 위임
    if last_exc and _is_transient_navigation_error(last_exc):
        return


def _text_exists_fast(text_value: str) -> bool:
    """Fast existence check to avoid expensive 25s fallback when text is absent."""
    escaped = text_value.replace("\\", "\\\\").replace("'", "\\'")
    js = (
        "(function(){"
        "const q='%s';"
        "return [...document.querySelectorAll('*')].some(el=>"
        "((el.textContent||'').includes(q)));"
        "})()"
    ) % escaped
    out = agent_browser("eval", js, check=False)
    return "true" in (out.stdout or "").lower()


def _page_has_upstream_error() -> bool:
    js = (
        "(function(){"
        "const t=((document.body&&document.body.innerText)||'').toLowerCase();"
        "if (t.includes('no healthy upstream') || t.includes('bad gateway')) return true;"
        "if (t.includes('502 bad gateway')) return true;"
        "return false;"
        "})()"
    )
    out = agent_browser("eval", js, check=False)
    return "true" in (out.stdout or "").lower()


def _recover_from_upstream_error(max_retries: int = 3) -> bool:
    for _ in range(max_retries):
        if not _page_has_upstream_error():
            return True
        current_url_out = agent_browser("get", "url", check=False)
        current_url = (current_url_out.stdout or "").strip()
        if not current_url:
            return False
        _safe_open_url(current_url, retries=5)
        time.sleep(1.0)
    return not _page_has_upstream_error()


def _page_has_already_logged_in_notice() -> bool:
    js = (
        "(function(){"
        "const t=((document.body&&document.body.innerText)||'').replace(/\\s+/g,'');"
        "return t.includes('이미로그인이되어있어요');"
        "})()"
    )
    out = agent_browser("eval", js, check=False)
    return "true" in (out.stdout or "").lower()


# ---------------------------------------------------------------------------
# Self-Healing: fuzzy text matching for UI change resilience
# ---------------------------------------------------------------------------
_self_heal_log: list[dict[str, str]] = []  # [{step, old_text, new_text, similarity}]


def _normalize_text(s: str) -> str:
    """Remove all whitespace for comparison."""
    return re.sub(r"\s+", "", s)


def _fuzzy_find_in_snapshot(
    target_text: str, snapshot_out: str, threshold: float = 0.65
) -> list[tuple[str, str, str, float]]:
    """Find snapshot elements by fuzzy text matching.

    Returns list of (label, ref, role, similarity) sorted by similarity desc.
    """
    norm_target = _normalize_text(target_text)
    results: list[tuple[str, str, str, float]] = []
    for line in snapshot_out.splitlines():
        m = SNAPSHOT_NODE_PATTERN.match(line.strip())
        if not m:
            continue
        role = (m.group(1) or "").strip()
        label = (m.group(2) or "").strip()
        ref = (m.group(3) or "").strip()
        if not label:
            continue
        norm_label = _normalize_text(label)
        # Strategy 1: exact substring (score 1.0)
        if target_text in label:
            results.append((label, ref, role, 1.0))
            continue
        # Strategy 2: whitespace-normalized substring
        if norm_target in norm_label:
            results.append((label, ref, role, 0.95))
            continue
        # Strategy 3: difflib similarity
        ratio = difflib.SequenceMatcher(None, norm_target, norm_label).ratio()
        if ratio >= threshold:
            results.append((label, ref, role, ratio))
    results.sort(key=lambda x: x[3], reverse=True)
    return results


def _click_by_snapshot_text(target_text: str, retry_on_overlay: bool = True) -> tuple[str, str]:
    import logging as _logging
    _log = _logging.getLogger("order-agent-exec")
    snapshot_out = agent_browser("snapshot", "-i", check=True).stdout or ""
    # Use NODE_PATTERN to capture role (checkbox detection)
    candidates: list[tuple[str, str, str]] = []  # (label, ref, role)
    fuzzy_healed = False
    for line in snapshot_out.splitlines():
        m = SNAPSHOT_NODE_PATTERN.match(line.strip())
        if not m:
            continue
        role, label, ref = (m.group(1) or "").strip(), (m.group(2) or "").strip(), (m.group(3) or "").strip()
        if label and target_text in label:
            candidates.append((label, ref, role))
    if not candidates:
        # Self-Heal: try fuzzy matching before giving up
        fuzzy_results = _fuzzy_find_in_snapshot(target_text, snapshot_out)
        if fuzzy_results:
            best_label, best_ref, best_role, best_sim = fuzzy_results[0]
            _log.warning(
                "SELF-HEAL: '%s' not found, using fuzzy match '%s' (similarity=%.0f%%)",
                target_text, best_label, best_sim * 100,
            )
            _self_heal_log.append({
                "old_text": target_text,
                "new_text": best_label,
                "similarity": f"{best_sim:.0%}",
            })
            candidates.append((best_label, best_ref, best_role))
            fuzzy_healed = True
        else:
            raise RuntimeError(f"CLICK_SNAPSHOT_TEXT failed: no match for '{target_text}'")
    exact = [c for c in candidates if c[0].strip() == target_text]
    label, ref, role = exact[0] if exact else candidates[0]
    cmd = "check" if role == "checkbox" else "click"
    try:
        agent_browser(cmd, f"@{ref}", check=True)
    except AgentBrowserError as exc:
        if retry_on_overlay and "blocked by another element" in (exc.stderr or "").lower():
            _log.warning("CLICK_SNAPSHOT_TEXT overlay blockage on @%s. Retrying with ESC.", ref)
            agent_browser("press", "Escape", check=False)
            time.sleep(0.3)
            # Re-take snapshot in case refs changed after ESC
            snapshot_out2 = agent_browser("snapshot", "-i", check=True).stdout or ""
            candidates2: list[tuple[str, str, str]] = []
            for line in snapshot_out2.splitlines():
                m2 = SNAPSHOT_NODE_PATTERN.match(line.strip())
                if not m2:
                    continue
                r2_role, l2, r2 = (m2.group(1) or "").strip(), (m2.group(2) or "").strip(), (m2.group(3) or "").strip()
                if l2 and target_text in l2:
                    candidates2.append((l2, r2, r2_role))
            if not candidates2:
                # Self-Heal on overlay retry too
                fuzzy2 = _fuzzy_find_in_snapshot(target_text, snapshot_out2)
                if fuzzy2:
                    b_label, b_ref, b_role, b_sim = fuzzy2[0]
                    _log.warning("SELF-HEAL (overlay retry): fuzzy match '%s' (%.0f%%)", b_label, b_sim * 100)
                    candidates2.append((b_label, b_ref, b_role))
            if candidates2:
                exact2 = [c for c in candidates2 if c[0].strip() == target_text]
                label, ref, role = exact2[0] if exact2 else candidates2[0]
                cmd = "check" if role == "checkbox" else "click"
            agent_browser(cmd, f"@{ref}", check=True)
        else:
            raise
    return label, ref


def _click_prev_checkbox_for_snapshot_text(target_text: str) -> tuple[str, str, str]:
    snapshot_out = agent_browser("snapshot", "-i", check=True).stdout or ""
    nodes: list[tuple[str, str, str]] = []
    for line in snapshot_out.splitlines():
        m = SNAPSHOT_NODE_PATTERN.match(line.strip())
        if not m:
            continue
        role, label, ref = (m.group(1) or "").strip(), (m.group(2) or "").strip(), (m.group(3) or "").strip()
        nodes.append((role, label, ref))
    target_idx = -1
    for i, (role, label, _ref) in enumerate(nodes):
        if target_text in label:
            target_idx = i
            break
    if target_idx < 0:
        raise RuntimeError(f"CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT failed: no match for '{target_text}'")
    for i in range(target_idx - 1, -1, -1):
        role, label, ref = nodes[i]
        if role == "checkbox":
            agent_browser("click", f"@{ref}", check=True)
            target_role, target_label, target_ref = nodes[target_idx]
            return label, ref, target_ref
    raise RuntimeError(
        "CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT failed: "
        f"no previous checkbox for '{target_text}'"
    )


def _click_ref_with_escape_retry(ref: str) -> None:
    try:
        agent_browser("click", f"@{ref}", check=True)
    except AgentBrowserError as exc:
        if "blocked by another element" not in (exc.stderr or "").lower():
            raise
        agent_browser("press", "Escape", check=False)
        agent_browser("click", f"@{ref}", check=True)


def _snapshot_cart_selected_count(snapshot_out: str) -> int | None:
    for line in snapshot_out.splitlines():
        m = SNAPSHOT_CART_COUNT_PATTERN.search(line)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
    return None


def _select_cart_item_by_text(target_text: str) -> tuple[str, str, int | None]:
    snapshot_out = agent_browser("snapshot", "-i", check=True).stdout or ""
    nodes: list[tuple[str, str, str]] = []
    for line in snapshot_out.splitlines():
        m = SNAPSHOT_NODE_PATTERN.match(line.strip())
        if not m:
            continue
        role, label, ref = (m.group(1) or "").strip(), (m.group(2) or "").strip(), (m.group(3) or "").strip()
        nodes.append((role, label, ref))
    target_idx = -1
    for i, (_role, label, _ref) in enumerate(nodes):
        if target_text in label:
            target_idx = i
            break
    if target_idx < 0:
        raise RuntimeError(f"SELECT_CART_ITEM_BY_TEXT failed: no match for '{target_text}'")
    checkbox_ref = None
    checkbox_label = ""
    for i in range(target_idx - 1, -1, -1):
        role, label, ref = nodes[i]
        if role != "checkbox":
            continue
        if "전체선택" in label:
            continue
        checkbox_ref = ref
        checkbox_label = label
        break
    if not checkbox_ref:
        raise RuntimeError(
            "SELECT_CART_ITEM_BY_TEXT failed: "
            f"no item checkbox before '{target_text}'"
        )
    _click_ref_with_escape_retry(checkbox_ref)
    after = agent_browser("snapshot", "-i", check=True).stdout or ""
    selected_count = _snapshot_cart_selected_count(after)
    return checkbox_label, checkbox_ref, selected_count


def _click_order_detail_by_status(status_hint: str) -> str:
    status_hint_norm = (status_hint or "").strip()
    status_hints = [s.strip() for s in status_hint_norm.split("|") if s.strip()]
    js = (
        "(function(){"
        "const norm=(s)=>(s||'').replace(/\\s+/g,'').trim();"
        f"const statuses={json.dumps(status_hints)};"
        "const details=[...document.querySelectorAll('[role=\"button\"][aria-label*=\"주문상세\"],button[aria-label*=\"주문상세\"],a[aria-label*=\"주문상세\"]')];"
        "if(!details.length) throw new Error('no_order_detail_button');"
        "let target=details[0];"
        "if(statuses.length){"
        "const cand=details.find(el=>{"
        "const sec=el.closest('section');"
        "if(!sec) return false;"
        "const txt=norm(sec.textContent);"
        "return statuses.some(st=>txt.includes(norm(st)));"
        "});"
        "if(cand) target=cand;"
        "}"
        "target.click();"
        "const al=target.getAttribute('aria-label')||'';"
        "return 'clicked:' + (al||norm(target.textContent));"
        "})()"
    )
    out = agent_browser("eval", js, check=True).stdout.strip()
    return out.strip()


def _click_order_detail_with_action(action_text: str, max_scan: int = 3) -> str | None:
    action_norm = (action_text or "").strip()
    if not action_norm:
        raise RuntimeError("CLICK_ORDER_DETAIL_WITH_ACTION failed: empty action text")
    filter_statuses: list[str] = []
    if "취소" in action_norm:
        # 취소는 목록에서 결제완료/주문확인중 상태 주문만 대상으로 직접 탐색한다.
        filter_statuses = ["결제완료", "주문확인중"]
    elif "교환" in action_norm or "반품" in action_norm:
        # 교환/반품은 배송완료 상태 주문만 대상으로 탐색한다.
        filter_statuses = ["배송완료"]

    def _scan_current_list(list_url: str) -> str | None:
        for idx in range(max_scan):
            click_js = (
                "(function(){"
                "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
                "const details=[...document.querySelectorAll('[role=\"button\"][aria-label*=\"주문상세\"],button[aria-label*=\"주문상세\"],a[aria-label*=\"주문상세\"]')];"
                f"const statuses={json.dumps(filter_statuses)};"
                "let pool=details;"
                "if(statuses.length){"
                "pool=details.filter(el=>{"
                "const sec=el.closest('section');"
                "const txt=norm(sec?sec.textContent:'');"
                "return statuses.some(st=>txt.includes(norm(st)));"
                "});"
                "}"
                f"const idx={idx};"
                "if(idx>=pool.length) return 'out_of_range';"
                "pool[idx].click();"
                "const al=pool[idx].getAttribute('aria-label')||'';"
                "return 'clicked:' + al;"
                "})()"
            )
            out = agent_browser("eval", click_js, check=True).stdout.strip()
            if "out_of_range" in out:
                break
            time.sleep(0.9)
            check_js = (
                "(function(){"
                "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
                f"const target=norm({json.dumps(action_norm)});"
                "const btns=[...document.querySelectorAll('button,[role=button],a,div.btn')];"
                "const actionSuffixes=['하기','신청'];"
                "const found=btns.some(el=>{"
                "const t=norm(el.textContent);"
                "return t===target || actionSuffixes.some(s=>t===target+s) || actionSuffixes.some(s=>t.includes(target+s));"
                "});"
                "return found;"
                "})()"
            )
            has_action = "true" in (agent_browser("eval", check_js, check=True).stdout or "").lower()
            current_url = agent_browser("get", "url", check=True).stdout.strip()
            if has_action and "/checkout/orders/" in current_url:
                return current_url
            _safe_open_url(list_url, retries=3)
            time.sleep(0.7)
        return None

    start_url = agent_browser("get", "url", check=True).stdout.strip()

    # 교환/반품은 페이지 필터가 부정확할 수 있으므로 기본 목록으로 리셋 후 섹션 텍스트 필터링으로 탐색
    if filter_statuses and ("교환" in action_norm or "반품" in action_norm):
        base_url = "https://alpha.zigzag.kr/checkout/orders"
        if start_url != base_url:
            _safe_open_url(base_url, retries=3)
            time.sleep(1.0)
            start_url = base_url

    found = _scan_current_list(start_url)
    if found:
        return found

    print(
        f"[WARN] CLICK_ORDER_DETAIL_WITH_ACTION: no '{action_norm}' target "
        f"(statuses={filter_statuses}, scanned {max_scan} orders)"
    )
    return None


def _apply_order_status_filter(status_text: str) -> str:
    status_raw = (status_text or "").strip()
    if not status_raw:
        raise RuntimeError("APPLY_ORDER_STATUS_FILTER failed: empty status text")
    statuses = [s.strip() for s in status_raw.split("|") if s.strip()]
    if not statuses:
        raise RuntimeError("APPLY_ORDER_STATUS_FILTER failed: empty status text")

    def _open_filter_modal() -> None:
        js = (
            "(function(){"
            "const btns=[...document.querySelectorAll('button,[role=\"button\"]')];"
            "if(!btns.length) throw new Error('order_status_filter_button_not_found');"
            "btns[0].click();"
            "return 'opened';"
            "})()"
        )
        agent_browser("eval", js, check=True)
        time.sleep(0.45)

    def _find_ref(role_name: str, text_contains: str) -> str | None:
        snapshot_out = agent_browser("snapshot", "-i", check=True).stdout or ""
        nodes: list[tuple[str, str, str]] = []
        for line in snapshot_out.splitlines():
            m = SNAPSHOT_NODE_PATTERN.match(line.strip())
            if not m:
                continue
            role, label, ref = (m.group(1) or "").strip(), (m.group(2) or "").strip(), (m.group(3) or "").strip()
            nodes.append((role, label, ref))
        for role, label, ref in nodes:
            if role != role_name:
                continue
            if text_contains in label:
                return ref
        return None

    def _is_no_order_history() -> bool:
        out = agent_browser(
            "eval",
            "(function(){const t=((document.body&&document.body.innerText)||'').replace(/\\s+/g,'');return t.includes('주문내역이없어요');})()",
            check=False,
        ).stdout or ""
        return "true" in out.lower()

    last_url = agent_browser("get", "url", check=True).stdout.strip()
    missing: list[str] = []
    for i, status in enumerate(statuses):
        radio_ref = _find_ref("radio", status)
        if not radio_ref:
            _open_filter_modal()
            radio_ref = _find_ref("radio", status)
        if not radio_ref:
            missing.append(status)
            continue

        _click_ref_with_escape_retry(radio_ref)
        time.sleep(0.25)

        submit_ref = _find_ref("button", "조회하기")
        if not submit_ref:
            submit_ref = _find_ref("button", "조회")
        if not submit_ref:
            raise RuntimeError("APPLY_ORDER_STATUS_FILTER failed: no submit button '조회하기'")
        _click_ref_with_escape_retry(submit_ref)
        time.sleep(1.2)
        last_url = agent_browser("get", "url", check=True).stdout.strip()

        # 다중 상태 지정 시: 현재 상태에서 주문이 있으면 종료, 없으면 다음 상태 fallback
        if i == len(statuses) - 1 or not _is_no_order_history():
            return last_url

    if missing and len(missing) == len(statuses):
        raise RuntimeError(
            "APPLY_ORDER_STATUS_FILTER failed: no radio for statuses "
            + ", ".join(f"'{s}'" for s in statuses)
        )
    return last_url


def _collect_visible_reason_options() -> list[str]:
    js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const isVisible=(el)=>{if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el); return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        "const isInModal=(el)=>!!(el&&el.closest('[role=\"dialog\"],dialog,[aria-modal=\"true\"],.modal,[class*=\"modal\"],[class*=\"sheet\"],[class*=\"drawer\"]'));"
        "const holder=[...document.querySelectorAll('*')].find(el=>norm(el.textContent)==='사유를선택해주세요'&&isVisible(el)&&!isInModal(el));"
        "if(holder){"
        "const cands=[holder,holder.parentElement,holder.parentElement&&holder.parentElement.parentElement,holder.closest('section,div,li')].filter(Boolean);"
        "for(const el of cands){try{el.scrollIntoView({block:'center'});}catch(e){} try{['pointerdown','mousedown','mouseup','click'].forEach(tp=>el.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));}catch(e){}}"
        "}"
        "const dlg=[...document.querySelectorAll('[role=\"dialog\"],dialog,[aria-modal=\"true\"],.modal,[class*=\"modal\"],[class*=\"sheet\"],[class*=\"drawer\"]')].find(isVisible);"
        "const scope=dlg||document;"
        "const banned=['사유를선택해주세요','선택완료','취소','닫기','사유선택','취소요청하기','취소안내사항을확인했습니다.','0/500','수거해주세요','이미보냈어요','나중에직접보낼게요'];"
        "const items=[...scope.querySelectorAll('[role=\"radio\"],label,li,button')]"
        ".map(el=>norm(el.textContent||''))"
        ".filter(t=>{"
        "if(!t||t.length<2||t.length>32) return false;"
        "if(/[0-9]/.test(t)) return false;"
        "if(/[\\[\\]\\(\\)\\/]/.test(t)) return false;"
        "if(banned.some(b=>t===b||t.includes(b))) return false;"
        "if(!/요$/.test(t)) return false;"
        "if(t.includes('환불')||t.includes('재발급')||t.includes('유효기간')||t.includes('포인트')||t.includes('마일리지')) return false;"
        "return true;"
        "});"
        "const uniq=[...new Set(items)].slice(0,40);"
        "return JSON.stringify(uniq);"
        "})()"
    )
    out = (agent_browser("eval", js, check=False).stdout or "").strip()
    try:
        parsed = json.loads(out)
        if isinstance(parsed, str):
            parsed = json.loads(parsed)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return []


def _ask_choice_from_options(options: list[str], prompt: str) -> str | None:
    if not options:
        raise RuntimeError("ASK_REASON_OPTIONS_EMPTY: no reason options were discovered on this page")

    # 비대화 모드에서는 환경변수 우선, 없으면 첫 번째 선택지 사용
    env_text = os.getenv("ORDER_AGENT_REASON_TEXT", "").strip()
    if env_text:
        for opt in options:
            if env_text.replace(" ", "") in opt.replace(" ", ""):
                return opt

    env_idx = os.getenv("ORDER_AGENT_REASON_INDEX", "").strip()
    if env_idx.isdigit():
        idx = int(env_idx) - 1
        if 0 <= idx < len(options):
            return options[idx]

    if not sys.stdin.isatty():
        import logging as _logging
        _log = _logging.getLogger("order-agent-exec")
        _log.info("Non-interactive mode: auto-selecting first option '%s'", options[0])
        return options[0]

    print("")
    print(f"[askQuestion] {prompt}")
    for i, opt in enumerate(options, 1):
        print(f"{i}. {opt}")
    print("번호를 입력하세요. Enter는 1번 선택")
    try:
        raw = input("> ").strip()
    except EOFError:
        return options[0]
    if not raw:
        return options[0]
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]
    return options[0]


def _select_reason_or_first(reason_text: str) -> None:
    reason_norm = (reason_text or "").strip()
    if reason_norm.upper() in {"ASK", "__ASK__", "ASKQUESTION"}:
        options = _collect_visible_reason_options()
        picked = _ask_choice_from_options(options, "클레임 사유를 선택해 주세요")
        reason_norm = (picked or "").strip()

    # ref 기반 선택 우선: 라디오 항목이 snapshot에 보이는 경우 가장 안정적이다.
    def _try_click_reason_by_snapshot() -> bool:
        snapshot_out = agent_browser("snapshot", "-i", check=False).stdout or ""
        nodes: list[tuple[str, str, str]] = []
        for line in snapshot_out.splitlines():
            m = SNAPSHOT_NODE_PATTERN.match(line.strip())
            if not m:
                continue
            role, label, ref = (m.group(1) or "").strip(), (m.group(2) or "").strip(), (m.group(3) or "").strip()
            nodes.append((role, label, ref))
        wanted = (reason_norm or "").replace(" ", "").strip()
        banned = (
            "사유를선택해주세요",
            "선택완료",
            "취소",
            "닫기",
            "수거해주세요",
            "이미보냈어요",
            "나중에직접보낼게요",
        )
        candidate_ref: str | None = None
        for role, label, ref in nodes:
            if role != "radio":
                continue
            n = (label or "").replace(" ", "").strip()
            if not n:
                continue
            if any(b in n for b in banned):
                continue
            if wanted and wanted in n:
                _click_ref_with_escape_retry(ref)
                return True
            if candidate_ref is None:
                candidate_ref = ref
        if candidate_ref:
            _click_ref_with_escape_retry(candidate_ref)
            return True
        return False

    try:
        if _try_click_reason_by_snapshot():
            time.sleep(0.2)
            return
    except Exception:
        pass

    js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const isVisible=(el)=>{if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el); return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        f"const wanted=norm({json.dumps(reason_norm)});"
        "const banned=['사유를선택해주세요','선택완료','취소','닫기','취소요청하기','취소안내사항을확인했습니다.','0/500','수거해주세요','이미보냈어요','나중에직접보낼게요'];"
        "const labels=[...document.querySelectorAll('label')].filter(isVisible);"
        "let radioLabel=labels.find(el=>{"
        "const t=norm(el.textContent||'');"
        "if(!t) return false;"
        "if(t.length<2||t.length>32) return false;"
        "if(/[0-9]/.test(t)||/[\\[\\]\\(\\)\\/]/.test(t)) return false;"
        "if(banned.some(b=>t.includes(b))) return false;"
        "if(t.includes('환불')||t.includes('재발급')||t.includes('유효기간')||t.includes('포인트')||t.includes('마일리지')) return false;"
        "if(wanted) return t===wanted || t.includes(wanted) || wanted.includes(t);"
        "return true;"
        "});"
        "if(!radioLabel && !wanted){"
        "radioLabel=labels.find(el=>{"
        "const t=norm(el.textContent||'');"
        "if(!t) return false;"
        "if(t.length<2||t.length>32) return false;"
        "if(/[0-9]/.test(t)||/[\\[\\]\\(\\)\\/]/.test(t)) return false;"
        "if(banned.some(b=>t.includes(b))) return false;"
        "return true;"
        "});"
        "}"
        "if(radioLabel){"
        "const inp=radioLabel.querySelector('input[type=\"radio\"]');"
        "if(inp){"
        "try{inp.click();}catch(e){}"
        "try{inp.checked=true;}catch(e){}"
        "inp.dispatchEvent(new Event('input',{bubbles:true}));"
        "inp.dispatchEvent(new Event('change',{bubbles:true}));"
        "return 'reason_selected';"
        "}"
        "const hit=radioLabel.closest('[role=\"radio\"],label,li,button,div,span')||radioLabel;"
        "try{hit.scrollIntoView({block:'center'});}catch(e){}"
        "['pointerdown','mousedown','mouseup','click'].forEach(tp=>hit.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
        "return 'reason_selected';"
        "}"
        "let target=[...document.querySelectorAll('[role=\"radio\"],label,li,button')].find(el=>norm(el.textContent)===wanted&&isVisible(el));"
        "if(!target){"
        "const dlg=[...document.querySelectorAll('[role=\"dialog\"],dialog')].find(isVisible);"
        "const scope=dlg||document;"
        "target=[...scope.querySelectorAll('[role=\"radio\"],label,button,li')].find(el=>{"
        "const t=norm(el.textContent||'');"
        "if(!t) return false;"
        "if(t.length<2||t.length>32) return false;"
        "if(/[0-9]/.test(t)) return false;"
        "if(/[\\[\\]\\(\\)\\/]/.test(t)) return false;"
        "if(banned.some(b=>t.includes(b))) return false;"
        "if(t.includes('환불')||t.includes('재발급')||t.includes('유효기간')||t.includes('포인트')||t.includes('마일리지')) return false;"
        "if(t.includes('품절')||t.includes('매진')) return false;"
        "return isVisible(el);"
        "});"
        "}"
        "if(!target) throw new Error('reason_option_not_found');"
        "const hit=target.closest('[role=\"radio\"],label,button,div,li,span')||target;"
        "try{hit.scrollIntoView({block:'center'});}catch(e){}"
        "['pointerdown','mousedown','mouseup','click'].forEach(tp=>hit.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
        "return 'reason_selected';"
        "})()"
    )
    agent_browser("eval", js, check=True)


def _reason_placeholder_visible() -> bool:
    js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const isVisible=(el)=>{if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el); return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        "const isInModal=(el)=>!!(el&&el.closest('[role=\"dialog\"],dialog,[aria-modal=\"true\"],.modal,[class*=\"modal\"],[class*=\"sheet\"],[class*=\"drawer\"]'));"
        "const holders=[...document.querySelectorAll('*')].filter(el=>norm(el.textContent)==='사유를선택해주세요'&&isVisible(el));"
        "if(!holders.length) return false;"
        "return holders.some(el=>!isInModal(el));"
        "})()"
    )
    out = (agent_browser("eval", js, check=False).stdout or "").lower()
    return "true" in out


def _open_reason_picker() -> None:
    js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const isVisible=(el)=>{if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el); return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        "const isInModal=(el)=>!!(el&&el.closest('[role=\"dialog\"],dialog,[aria-modal=\"true\"],.modal,[class*=\"modal\"],[class*=\"sheet\"],[class*=\"drawer\"]'));"
        "const t=[...document.querySelectorAll('body *')].find(el=>norm(el.textContent)==='사유를선택해주세요'&&isVisible(el)&&!isInModal(el));"
        "if(!t) throw new Error('reason_placeholder_not_found');"
        "const cands=[t,t.parentElement,t.parentElement?.parentElement,t.closest('section')];"
        "for(const el of cands){"
        "if(!el) continue;"
        "try{el.scrollIntoView({block:'center'});['pointerdown','mousedown','mouseup','click'].forEach(tp=>el.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));}catch(e){}"
        "}"
        "return 'reason_opened';"
        "})()"
    )
    agent_browser("eval", js, check=True)


def _confirm_reason_picker_if_present() -> None:
    js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const btn=[...document.querySelectorAll('button,[role=\"button\"],div')].find(el=>norm(el.textContent)==='선택완료');"
        "if(!btn) return 'no_reason_confirm_button';"
        "btn.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));"
        "return 'reason_confirmed';"
        "})()"
    )
    agent_browser("eval", js, check=False)


def _ensure_claim_reason_selected(reason_text: str, claim_code: str) -> None:
    # 사유 플레이스홀더가 보일 때만 선택 프로세스를 수행한다.
    if _reason_placeholder_visible():
        _open_reason_picker()
        time.sleep(0.25)
        _select_reason_or_first(reason_text)
        time.sleep(0.2)
        _confirm_reason_picker_if_present()
        time.sleep(0.35)

    if _reason_placeholder_visible():
        raise RuntimeError(
            f"SUBMIT_{claim_code}_REQUEST failed [{claim_code}_REASON_NOT_SELECTED]: reason is still placeholder"
        )


def _fill_default_required_inputs(default_text: str = "test") -> int:
    js = (
        "(function(){"
        "const norm=s=>(s||'').toLowerCase();"
        "const isVisible=(el)=>{if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el); return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        "const hintKeys=['상세','내용','사유','메모','입력','직접','요청','detail','reason','memo'];"
        f"const dv={json.dumps(default_text)};"
        "const setVal=(el)=>{"
        "if(!el||el.disabled||el.readOnly) return false;"
        "if(!isVisible(el)) return false;"
        "if((el.value||'').trim().length>0) return false;"
        "const meta=((el.placeholder||'')+' '+(el.name||'')+' '+(el.id||'')+' '+(el.getAttribute('aria-label')||'')).toLowerCase();"
        "const hinted=el.required||el.getAttribute('aria-required')==='true'||hintKeys.some(k=>meta.includes(k));"
        "if(!hinted) return false;"
        "el.focus();"
        "el.value=dv;"
        "el.dispatchEvent(new Event('input',{bubbles:true}));"
        "el.dispatchEvent(new Event('change',{bubbles:true}));"
        "el.dispatchEvent(new Event('blur',{bubbles:true}));"
        "return true;"
        "};"
        "const fields=[...document.querySelectorAll('textarea,input[type=\"text\"],input[type=\"search\"],input[type=\"tel\"],input[type=\"email\"],input[type=\"url\"],input[type=\"number\"],input:not([type])')];"
        "let count=0;"
        "for(const el of fields){ if(setVal(el)) count+=1; }"
        "return String(count);"
        "})()"
    )
    out = (agent_browser("eval", js, check=False).stdout or "").strip()
    try:
        return int(out)
    except ValueError:
        return 0


def _collect_claim_page_evidence() -> dict[str, object]:
    current_url = (agent_browser("get", "url", check=False).stdout or "").strip()
    body_text = (
        agent_browser(
            "eval",
            "(function(){return ((document.body&&document.body.innerText)||'').replace(/\\s+/g,' ').trim().slice(0,900);})()",
            check=False,
        ).stdout
        or ""
    ).strip()
    errors_text = (agent_browser("errors", check=False).stdout or "").strip()
    console_text = (agent_browser("console", check=False).stdout or "").strip()
    modal = _collect_active_modal_info()
    modal_guidance = " ".join(str(modal.get("modalText") or "").split()).strip()
    modal_title = " ".join(str(modal.get("modalTitle") or "").split()).strip()
    submit_ui = _collect_inline_submit_guidance()
    return {
        "url": current_url,
        "body": body_text[:240],
        "errors": errors_text[:400],
        "console": console_text[:400],
        "hasModal": bool(modal.get("hasModal")),
        "modalTitle": modal_title[:160],
        "modalGuidanceText": modal_guidance[:600],
        "submitUiMessage": str(submit_ui.get("text") or "")[:400],
        "submitUiSource": str(submit_ui.get("source") or ""),
    }


def _collect_inline_submit_guidance() -> dict[str, str]:
    js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,' ').trim();"
        "const visible=(el)=>{if(!el)return false;const st=getComputedStyle(el);const r=el.getBoundingClientRect();"
        "return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        "const btnTexts=['확인','결제하기','0원 결제하기','구매하기','교환 요청하기','교환요청하기','반품요청하기','취소요청하기','다음단계로이동'];"
        "const buttons=[...document.querySelectorAll('button,[role=\"button\"],a,div,span')].filter(visible);"
        "const target=buttons.reverse().find(el=>{const t=norm(el.textContent); return btnTexts.some(k=>t===k||t.includes(k));});"
        "if(!target) return JSON.stringify({text:'',source:''});"
        "const deny=['불가','없습니다','할 수 없습니다','제한','실패','품절','재고','초과','협찬','프로모션','차단','보류','거부'];"
        "const isMsg=(t)=>{if(!t||t.length<6||t.length>220) return false; if(btnTexts.some(b=>t===b)) return false; return deny.some(k=>t.includes(k));};"
        "const scope=target.closest('[role=\"dialog\"],[aria-modal=\"true\"],dialog,.modal,[class*=\"modal\"],[class*=\"sheet\"],[class*=\"drawer\"],section,article,form,main,div')||target.parentElement||document.body;"
        "const items=[...scope.querySelectorAll('p,div,span,strong,li')].map(el=>norm(el.textContent)).filter(isMsg);"
        "if(items.length) return JSON.stringify({text:items[0],source:'submit_scope'});"
        "const p=target.parentElement;"
        "if(p){"
        "const sib=[...p.children].map(el=>norm(el.textContent)).filter(isMsg);"
        "if(sib.length) return JSON.stringify({text:sib[0],source:'submit_sibling'});"
        "}"
        "const r=target.getBoundingClientRect();"
        "const samples=[[r.left+r.width/2,r.top-40],[r.left+r.width/2,r.top-80],[r.left+r.width/2,r.top-120]];"
        "for(const [x,y] of samples){"
        "const el=document.elementFromPoint(Math.round(x),Math.round(y));"
        "if(!el) continue;"
        "const t=norm(el.textContent);"
        "if(isMsg(t)) return JSON.stringify({text:t,source:'submit_nearby'});"
        "}"
        "return JSON.stringify({text:'',source:''});"
        "})()"
    )
    out = (agent_browser("eval", js, check=False).stdout or "").strip()
    try:
        parsed = json.loads(out)
        if isinstance(parsed, str):
            parsed = json.loads(parsed)
        if isinstance(parsed, dict):
            text = " ".join(str(parsed.get("text") or "").split()).strip()
            # 확인 버튼 라벨이 붙는 경우 안내문 본문만 남긴다.
            if text.endswith("확인") and len(text) > 4:
                text = text[:-2].strip()
            return {
                "text": text,
                "source": str(parsed.get("source") or "").strip(),
            }
    except Exception:
        pass
    return {"text": "", "source": ""}


def _collect_modal_guidance_line() -> str:
    payload = _collect_active_modal_info()
    has_modal = bool(payload.get("hasModal"))
    modal_title = " ".join(str(payload.get("modalTitle") or "").split()).strip()
    modal_text = " ".join(str(payload.get("modalText") or "").split()).strip()
    if has_modal:
        parts: list[str] = []
        if modal_title:
            parts.append(f"title={modal_title[:120]}")
        if modal_text:
            parts.append(f"text={modal_text[:520]}")
        if parts:
            return "MODAL: " + " | ".join(parts)

    submit_ui = _collect_inline_submit_guidance()
    submit_text = str(submit_ui.get("text") or "").strip()
    submit_source = str(submit_ui.get("source") or "").strip()
    if submit_text:
        src = f" ({submit_source})" if submit_source else ""
        return f"SUBMIT_UI{src}: {submit_text[:560]}"
    return "NO_ACTIVE_MODAL_OR_SUBMIT_UI_MESSAGE"


def _print_cli_modal_guidance_message(modal_guidance_line: str) -> None:
    line = (modal_guidance_line or "").strip() or "NO_ACTIVE_MODAL_OR_SUBMIT_UI_MESSAGE"
    print(f"SUBMIT_UI_MESSAGE: {line}", flush=True)


def _submit_cancel_request(reason_text: str) -> str:
    reason_norm = (reason_text or "").strip()
    if not reason_norm:
        raise RuntimeError("SUBMIT_CANCEL_REQUEST failed: empty reason text")

    _ensure_claim_reason_selected(reason_norm, "CANCEL")
    _fill_default_required_inputs("test")

    agent_browser("press", "End", check=False)
    time.sleep(0.3)

    check_notice_js = (
        "(function(){"
        "const label=[...document.querySelectorAll('label')].find(el=>(el.textContent||'').includes('취소 안내사항을 확인했습니다.'));"
        "if(!label) throw new Error('cancel_notice_label_not_found');"
        "label.scrollIntoView({block:'center'});"
        "const cb=label.querySelector('input[type=\"checkbox\"]');"
        "if(!cb) throw new Error('cancel_notice_checkbox_not_found');"
        "if(cb.checked) return 'cancel_notice_checked_already';"
        "label.click();"
        "if(!cb.checked){"
        "cb.checked=true;"
        "cb.dispatchEvent(new Event('input',{bubbles:true}));"
        "cb.dispatchEvent(new Event('change',{bubbles:true}));"
        "}"
        "if(!cb.checked) throw new Error('cancel_notice_checkbox_not_checked');"
        "return 'cancel_notice_checked';"
        "})()"
    )
    notice_ok = False
    for _ in range(3):
        out = (agent_browser("eval", check_notice_js, check=False).stdout or "").strip()
        if "cancel_notice_checked" in out:
            notice_ok = True
            break
        time.sleep(0.2)
    if not notice_ok:
        evidence = _collect_claim_page_evidence()
        raise RuntimeError(
            "SUBMIT_CANCEL_REQUEST failed [CANCEL_NOTICE_CHECK_REQUIRED]: "
            f"unable to check cancel notice within 3 tries; evidence={json.dumps(evidence, ensure_ascii=False)}"
        )

    submit_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const btn=[...document.querySelectorAll('button,[role=\"button\"],div')].find(el=>norm(el.textContent)==='취소요청하기');"
        "if(!btn) throw new Error('cancel_request_button_not_found');"
        "btn.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));"
        "return 'cancel_request_clicked';"
        "})()"
    )
    confirm_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const ok=[...document.querySelectorAll('button,[role=\"button\"],div')].find(el=>norm(el.textContent)==='확인');"
        "if(ok){ok.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); return 'clicked_confirm';}"
        "return 'no_confirm_modal';"
        "})()"
    )

    def _page_text_norm() -> str:
        out = agent_browser(
            "eval",
            "(function(){return ((document.body&&document.body.innerText)||'').replace(/\\s+/g,'');})()",
            check=False,
        ).stdout or ""
        return out.strip().lower()

    max_submit_attempts = 3
    submit_attempts = 1
    agent_browser("eval", submit_js, check=True)
    time.sleep(1.0)
    agent_browser("eval", confirm_js, check=False)
    time.sleep(0.6)

    deadline = time.time() + 8.0
    while time.time() < deadline:
        current_url = agent_browser("get", "url", check=True).stdout.strip()
        if "/request-cancel" not in current_url:
            return current_url

        body_norm = _page_text_norm()
        if "사유를선택해주세요" in body_norm:
            _ensure_claim_reason_selected(reason_norm, "CANCEL")
            time.sleep(0.25)
            continue

        # 잔류 시 재제출/확인 재시도
        if "취소요청하기" in body_norm and "사유를선택해주세요" not in body_norm:
            if submit_attempts >= max_submit_attempts:
                evidence = _collect_claim_page_evidence()
                raise RuntimeError(
                    "SUBMIT_CANCEL_REQUEST failed [CANCEL_SUBMIT_RETRY_EXCEEDED]: "
                    f"submit retry reached {max_submit_attempts}; evidence={json.dumps(evidence, ensure_ascii=False)}"
                )
            agent_browser("eval", submit_js, check=False)
            submit_attempts += 1
            time.sleep(0.4)
            agent_browser("eval", confirm_js, check=False)
            time.sleep(0.6)

    current_url = agent_browser("get", "url", check=True).stdout.strip()
    evidence = _collect_claim_page_evidence()
    raise RuntimeError(
        "SUBMIT_CANCEL_REQUEST failed [CANCEL_REQUEST_STUCK]: "
        f"still on request-cancel page ({current_url}); evidence={json.dumps(evidence, ensure_ascii=False)}"
    )


def _submit_return_request(reason_text: str) -> str:
    reason_norm = (reason_text or "").strip()
    if not reason_norm:
        raise RuntimeError("SUBMIT_RETURN_REQUEST failed: empty reason text")

    _ensure_claim_reason_selected(reason_norm, "RETURN")
    _fill_default_required_inputs("test")

    pickup_select_js = (
        "(function(){"
        "const isVisible=(el)=>{if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el); return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        "const radios=[...document.querySelectorAll('[role=\"radio\"],input[type=\"radio\"]')].filter(el=>isVisible(el) && !el.disabled);"
        "if(!radios.length) return 'no_pickup_option';"
        "const t=radios[0];"
        "const hit=t.tagName==='INPUT'?(t.closest('label,div,[role=\"radio\"]')||t):t;"
        "try{hit.scrollIntoView({block:'center'});}catch(e){}"
        "['pointerdown','mousedown','mouseup','click'].forEach(tp=>hit.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
        "return 'pickup_clicked';"
        "})()"
    )
    pickup_checked_js = (
        "(function(){"
        "if([ ...document.querySelectorAll('input[type=\"radio\"]')].some(r=>r.checked)) return true;"
        "return [...document.querySelectorAll('[role=\"radio\"]')].some(el=>el.getAttribute('aria-checked')==='true');"
        "})()"
    )

    pickup_ok = False
    for _ in range(3):
        agent_browser("eval", pickup_select_js, check=False)
        time.sleep(0.25)
        checked_out = agent_browser("eval", pickup_checked_js, check=False).stdout or ""
        if "true" in checked_out.lower():
            pickup_ok = True
            break
    if not pickup_ok:
        # text 기반 fallback 1회
        agent_browser("click", "text=수거해주세요", check=False)
        time.sleep(0.2)

    agent_browser("press", "End", check=False)
    time.sleep(0.3)

    check_notice_js = (
        "(function(){"
        "const label=[...document.querySelectorAll('label')].find(el=>(el.textContent||'').includes('반품 안내사항을 확인했습니다.'));"
        "if(!label) throw new Error('return_notice_label_not_found');"
        "label.scrollIntoView({block:'center'});"
        "const cb=label.querySelector('input[type=\"checkbox\"]');"
        "if(!cb) throw new Error('return_notice_checkbox_not_found');"
        "if(cb.checked) return 'return_notice_checked_already';"
        "label.click();"
        "if(!cb.checked){"
        "cb.checked=true;"
        "cb.dispatchEvent(new Event('input',{bubbles:true}));"
        "cb.dispatchEvent(new Event('change',{bubbles:true}));"
        "}"
        "if(!cb.checked) throw new Error('return_notice_checkbox_not_checked');"
        "return 'return_notice_checked';"
        "})()"
    )
    notice_ok = False
    for _ in range(3):
        out = (agent_browser("eval", check_notice_js, check=False).stdout or "").strip()
        if "return_notice_checked" in out:
            notice_ok = True
            break
        time.sleep(0.2)
    if not notice_ok:
        evidence = _collect_claim_page_evidence()
        raise RuntimeError(
            "SUBMIT_RETURN_REQUEST failed [RETURN_NOTICE_CHECK_REQUIRED]: "
            f"unable to check return notice within 3 tries; evidence={json.dumps(evidence, ensure_ascii=False)}"
        )

    submit_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const labels=['반품요청하기','반품요청','다음단계로이동'];"
        "const btn=[...document.querySelectorAll('button,[role=\"button\"],div')].find(el=>labels.includes(norm(el.textContent)));"
        "if(!btn) throw new Error('return_request_button_not_found');"
        "try{btn.scrollIntoView({block:'center'});}catch(e){}"
        "['pointerdown','mousedown','mouseup','click'].forEach(tp=>btn.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
        "return 'return_submit_clicked:'+norm(btn.textContent);"
        "})()"
    )
    max_submit_attempts = 3
    submit_attempts = 1
    agent_browser("eval", submit_js, check=True)
    time.sleep(1.1)

    confirm_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const ok=[...document.querySelectorAll('button,[role=\"button\"],div')].find(el=>norm(el.textContent)==='확인');"
        "if(ok){ok.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); return 'clicked_confirm';}"
        "return 'no_confirm_modal';"
        "})()"
    )
    agent_browser("eval", confirm_js, check=False)
    time.sleep(1.3)

    def _page_text_norm() -> str:
        out = agent_browser(
            "eval",
            "(function(){return ((document.body&&document.body.innerText)||'').replace(/\\s+/g,'');})()",
            check=False,
        ).stdout or ""
        return out.strip().lower()

    # 반품 요청 완료는 request-return 화면 이탈(주문상세 복귀)까지를 성공 조건으로 본다.
    deadline = time.time() + 8.0
    while time.time() < deadline:
        current_url = agent_browser("get", "url", check=True).stdout.strip()
        if "/request-return" not in current_url:
            return current_url

        body_norm = _page_text_norm()
        if "사유를선택해주세요" in body_norm:
            _ensure_claim_reason_selected(reason_norm, "RETURN")
            time.sleep(0.25)
            continue

        if "반품수거방법을선택해주세요" in body_norm:
            # 수거방법 누락이면 재선택 후 재제출
            agent_browser("eval", pickup_select_js, check=False)
            time.sleep(0.25)
            if submit_attempts >= max_submit_attempts:
                evidence = _collect_claim_page_evidence()
                raise RuntimeError(
                    "SUBMIT_RETURN_REQUEST failed [RETURN_SUBMIT_RETRY_EXCEEDED]: "
                    f"submit retry reached {max_submit_attempts}; evidence={json.dumps(evidence, ensure_ascii=False)}"
                )
            agent_browser("eval", submit_js, check=False)
            submit_attempts += 1
            time.sleep(0.6)
            continue

        if "1+1상품은구매한옵션을모두반품요청해야합니다" in body_norm:
            raise RuntimeError(
                "SUBMIT_RETURN_REQUEST failed [RETURN_REQUEST_BLOCKED_1P1]: "
                "1+1 option set must be returned together"
            )

        # 확인 모달이 늦게 노출되는 경우를 위해 재클릭 시도
        agent_browser("eval", confirm_js, check=False)
        time.sleep(0.6)

    current_url = agent_browser("get", "url", check=True).stdout.strip()
    evidence = _collect_claim_page_evidence()
    raise RuntimeError(
        "SUBMIT_RETURN_REQUEST failed [RETURN_REQUEST_STUCK]: "
        f"still on request-return page ({current_url}); evidence={json.dumps(evidence, ensure_ascii=False)}"
    )


def _submit_exchange_request(reason_text: str) -> str:
    reason_norm = (reason_text or "").strip()
    if not reason_norm:
        raise RuntimeError("SUBMIT_EXCHANGE_REQUEST failed: empty reason text")

    def _apply_full_points_on_exchange_cost_sheet(url: str) -> None:
        if "/order-sheets/exchange" not in (url or ""):
            return

        # 교환비용결제 화면에서만 동작한다. 비용이 0원이면 아무것도 하지 않는다.
        cost_probe_js = (
            "(function(){"
            "const txt=(el)=>(el&&el.textContent?el.textContent:'').replace(/\\s+/g,' ').trim();"
            "const body=((document.body&&document.body.innerText)||'');"
            "const norm=body.replace(/\\s+/g,'');"
            "const m=(norm.match(/결제금액[:：]?([0-9,]+)원/)||norm.match(/([0-9,]+)원결제/));"
            "const amount=m?parseInt((m[1]||'0').replace(/,/g,''),10):null;"
            "const hasPointFull=[...document.querySelectorAll('button,[role=\"button\"],a,div,span')].some(el=>txt(el).replace(/\\s+/g,'').includes('포인트전액사용'));"
            "return JSON.stringify({amount: Number.isFinite(amount)?amount:null, hasPointFull});"
            "})()"
        )
        probe_raw = (agent_browser("eval", cost_probe_js, check=False).stdout or "").strip()
        try:
            probe = json.loads(probe_raw)
            if isinstance(probe, str):
                probe = json.loads(probe)
        except Exception:
            probe = {}

        amount = probe.get("amount") if isinstance(probe, dict) else None
        has_point_full = bool(probe.get("hasPointFull")) if isinstance(probe, dict) else False

        if isinstance(amount, int) and amount <= 0:
            return

        clicked = False
        for txt in ("포인트 전액사용", "포인트전액사용"):
            try:
                _click_by_snapshot_text(txt)
                clicked = True
                break
            except Exception:
                pass

        if not clicked and has_point_full:
            click_point_js = (
                "(function(){"
                "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
                "const t=[...document.querySelectorAll('button,[role=\"button\"],a,div,span')]"
                ".find(el=>norm(el.textContent||'').includes('포인트전액사용'));"
                "if(!t) return 'no_point_full';"
                "const hit=t.closest('button,[role=\"button\"],a,div,span')||t;"
                "try{hit.scrollIntoView({block:'center'});}catch(e){}"
                "['pointerdown','mousedown','mouseup','click'].forEach(tp=>hit.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
                "return 'clicked_point_full';"
                "})()"
            )
            out = (agent_browser("eval", click_point_js, check=False).stdout or "").strip()
            clicked = "clicked_point_full" in out

        time.sleep(0.35)

        # 비용이 있는 화면인데 포인트 전액사용 컨트롤을 못 찾으면 실패로 분류한다.
        if isinstance(amount, int) and amount > 0 and not clicked:
            raise RuntimeError(
                "SUBMIT_EXCHANGE_REQUEST failed [EXCHANGE_POINT_FULL_NOT_FOUND]: "
                "exchange cost sheet is active but '포인트 전액사용' control was not found/clicked"
            )

    # 이미 교환비용결제 화면에 있는 경우: 포인트 전액사용만 적용하고 종료
    start_url = agent_browser("get", "url", check=True).stdout.strip()
    if "/order-sheets/exchange" in start_url:
        _apply_full_points_on_exchange_cost_sheet(start_url)
        return start_url

    def _snapshot_nodes() -> list[tuple[str, str, str]]:
        snapshot_out = agent_browser("snapshot", "-i", check=True).stdout or ""
        nodes: list[tuple[str, str, str]] = []
        for line in snapshot_out.splitlines():
            m = SNAPSHOT_NODE_PATTERN.match(line.strip())
            if not m:
                continue
            role, label, ref = (m.group(1) or "").strip(), (m.group(2) or "").strip(), (m.group(3) or "").strip()
            nodes.append((role, label, ref))
        return nodes

    def _label_norm(s: str) -> str:
        return (s or "").replace(" ", "").replace("\n", "").replace("\t", "").strip()

    def _find_option_trigger_ref(nodes: list[tuple[str, str, str]]) -> str | None:
        """Snapshot 노드에서 옵션 선택 트리거 ref를 찾는다 (배송메모 영역 제외).

        Phase 1: 정확한 옵션 선택 텍스트 매칭
        Phase 2: '옵션' 포함 버튼 탐색
        배송메모 관련 노드는 모든 단계에서 제외된다.
        """
        memo_refs: set[str] = set()

        # Pass 1: 배송메모 관련 ref 수집
        for _role, label, ref in nodes:
            n = _label_norm(label)
            if "배송메모" in n:
                memo_refs.add(ref)

        # Pass 2: 정확한 옵션 선택 텍스트 매칭
        option_keywords = ("옵션을선택해주세요", "교환옵션을선택해주세요")
        for _role, label, ref in nodes:
            if ref in memo_refs:
                continue
            n = _label_norm(label)
            if "배송메모" in n:
                continue
            if any(kw in n for kw in option_keywords):
                return ref

        # Pass 3: "옵션" 포함 버튼 (배송메모 제외)
        for role, label, ref in nodes:
            if ref in memo_refs:
                continue
            if role != "button":
                continue
            n = _label_norm(label)
            if "배송메모" in n:
                continue
            if "옵션" in n and "선택완료" not in n and "교환요청" not in n:
                return ref

        return None

    def _try_select_exchange_option_by_snapshot() -> bool:
        nodes = _snapshot_nodes()

        # 1) 옵션 트리거 버튼을 우선 탐색한다.
        for _role, label, ref in nodes:
            if _role != "button":
                continue
            n = _label_norm(label)
            if not n:
                continue
            if "옵션" in n and "선택완료" not in n and "교환요청" not in n:
                try:
                    _click_ref_with_escape_retry(ref)
                    time.sleep(0.35)
                except Exception:
                    pass
                break
        else:
            # 2) 라벨 없는 버튼(실제 옵션 트리거일 수 있음)을 제한적으로 시도한다.
            notice_idx = -1
            for i, (_role, label, _ref) in enumerate(nodes):
                if "교환안내사항" in _label_norm(label):
                    notice_idx = i
                    break
            if notice_idx > 0:
                for i in range(notice_idx - 1, -1, -1):
                    role, label, ref = nodes[i]
                    if role != "button":
                        continue
                    n = _label_norm(label)
                    if n in {"", "열기"}:
                        try:
                            _click_ref_with_escape_retry(ref)
                            time.sleep(0.35)
                        except Exception:
                            pass
                        break

        # 3) 옵션 항목 선택
        nodes = _snapshot_nodes()
        banned = {
            "수거해주세요",
            "이미보냈어요",
            "나중에직접보낼게요",
            "바로결제할게요",
            "쇼핑몰계좌로송금할게요",
            "배송지변경",
            "교환요청하기",
            "다음단계로이동",
            "교환안내사항을확인했습니다.",
            "ChooseFile",
            "choosefile",
            "선택완료",
            "취소",
            "닫기",
            "색상",
            "사이즈",
        }
        candidate_ref: str | None = None
        for role, label, ref in nodes:
            if role not in {"radio", "button"}:
                continue
            n = _label_norm(label)
            if not n or n in banned:
                continue
            if "옵션" in n or "사유" in n:
                continue
            if "색상" in n or "사이즈" in n:
                continue
            if "품절" in n or "매진" in n:
                continue
            candidate_ref = ref
            break
        if candidate_ref:
            try:
                _click_ref_with_escape_retry(candidate_ref)
                time.sleep(0.25)
            except Exception:
                candidate_ref = None

        # 4) 선택완료 클릭
        nodes = _snapshot_nodes()
        done_ref: str | None = None
        for role, label, ref in nodes:
            if role != "button":
                continue
            if _label_norm(label) == "선택완료":
                done_ref = ref
                break
        if done_ref:
            try:
                _click_ref_with_escape_retry(done_ref)
                time.sleep(0.4)
            except Exception:
                return candidate_ref is not None
            return True
        return candidate_ref is not None

    option_select_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const bodyNorm=norm((document.body&&document.body.innerText)||'');"
        "if(!bodyNorm.includes('옵션을선택해주세요')&&!bodyNorm.includes('교환옵션을선택해주세요')) return 'already_selected';"
        "const trigger=[...document.querySelectorAll('button,[role=\"button\"],div,span,label')].find(el=>{const t=norm(el.textContent);return t.includes('옵션을선택해주세요')||t.includes('교환옵션을선택해주세요');});"
        "if(!trigger) return 'no_option_trigger';"
        "try{trigger.scrollIntoView({block:'center'});}catch(e){}"
        "['pointerdown','mousedown','mouseup','click'].forEach(tp=>trigger.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
        "return 'opened_option_picker';"
        "})()"
    )
    option_open_exchange_section_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const all=[...document.querySelectorAll('*')];"
        "const anchor=all.find(el=>{"
        "const t=norm(el.textContent||'');"
        "return t.includes('교환옵션')||t.includes('교환할상품')||t.includes('옵션을선택해주세요');"
        "});"
        "if(!anchor) return 'no_exchange_option_anchor';"
        "const root=anchor.closest('section,article,li,div,form')||anchor.parentElement||document.body;"
        "const cands=[...root.querySelectorAll('button,[role=\"button\"],select,input,[tabindex]')];"
        "const banned=['교환요청하기','다음단계로이동','배송지변경','수거해주세요','이미보냈어요','나중에직접보낼게요','교환안내사항'];"
        "const target=cands.find(el=>{"
        "const t=norm(el.textContent||'')||norm(el.getAttribute('aria-label')||'')||norm(el.getAttribute('placeholder')||'');"
        "if(banned.some(k=>t.includes(k))) return false;"
        "if(el.tagName==='INPUT'&&el.type==='file') return false;"
        "const r=el.getBoundingClientRect();"
        "const st=getComputedStyle(el);"
        "if(st.display==='none'||st.visibility==='hidden'||r.width===0||r.height===0) return false;"
        "return true;"
        "});"
        "if(!target) return 'no_exchange_option_control';"
        "try{target.scrollIntoView({block:'center'});}catch(e){}"
        "['pointerdown','mousedown','mouseup','click'].forEach(tp=>target.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
        "return 'opened_by_exchange_section:' + (norm(target.textContent||'')||target.tagName);"
        "})()"
    )
    option_activate_selection_area_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const clickAt=(x,y)=>{"
        "const el=document.elementFromPoint(x,y);"
        "if(!el) return false;"
        "try{['pointerdown','mousedown','mouseup','click'].forEach(tp=>el.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window,clientX:x,clientY:y})));return true;}catch(e){return false;}"
        "};"
        "const wanted=['옵션을선택해주세요.','옵션을선택해주세요'];"
        "const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);"
        "let tn=null;"
        "while((tn=walker.nextNode())){"
        "const txt=norm(tn.textContent||'');"
        "if(!txt) continue;"
        "if(!wanted.includes(txt) && !txt.includes('옵션을선택해주세요')) continue;"
        "const r=(function(){try{const range=document.createRange();range.selectNodeContents(tn.parentElement||tn);return range.getBoundingClientRect();}catch(e){return null;}})();"
        "if(!r||r.width<2||r.height<2) continue;"
        "const cx=Math.round(r.left + Math.min(r.width*0.6, r.width-2));"
        "const cy=Math.round(r.top + r.height/2);"
        "const host=(tn.parentElement||document.body);"
        "try{host.scrollIntoView({block:'center'});}catch(e){}"
        "if(clickAt(cx,cy)){return 'activated_selection_area:text-node';}"
        "}"
        "const all=[...document.querySelectorAll('div,span,p,label,button,[role=\"button\"]')];"
        "const hits=all.filter(el=>{"
        "const t=norm(el.textContent||'');"
        "if(!t) return false;"
        "if(!(t==='옵션을선택해주세요.'||t==='옵션을선택해주세요'||t.includes('옵션을선택해주세요'))) return false;"
        "const r=el.getBoundingClientRect();"
        "if(r.width<8||r.height<8) return false;"
        "const st=getComputedStyle(el);"
        "if(st.display==='none'||st.visibility==='hidden') return false;"
        "return true;"
        "});"
        "if(!hits.length) return 'no_selection_area';"
        "const target=hits.sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height-b.getBoundingClientRect().width*b.getBoundingClientRect().height)[0];"
        "const cands=[target,target.parentElement,target.closest('button,[role=\"button\"],label,li,section,article,div')].filter(Boolean);"
        "for(const el of cands){"
        "try{el.scrollIntoView({block:'center'});}catch(e){}"
        "try{['pointerdown','mousedown','mouseup','click'].forEach(tp=>el.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));return 'activated_selection_area:element';}catch(e){}"
        "}"
        "return 'selection_area_click_failed';"
        "})()"
    )
    option_pick_one_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const dlg=[...document.querySelectorAll('[role=\"dialog\"],dialog')].find(el=>norm(el.textContent||'').includes('교환옵션'));"
        "const isContainerNamed=(el)=>{"
        "if(!el) return false;"
        "const src=[el.className||'',el.id||'',el.getAttribute&&el.getAttribute('name')||'',el.getAttribute&&el.getAttribute('data-testid')||'',el.getAttribute&&el.getAttribute('style')||'']"
        ".join(' ').toLowerCase();"
        "return src.includes('container');"
        "};"
        "const containerInDialog=dlg?[...dlg.querySelectorAll('*')].find(el=>{const r=el.getBoundingClientRect();const st=getComputedStyle(el);return isContainerNamed(el)&&st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;}):null;"
        "const scope=containerInDialog||dlg||document;"
        "const all=[...scope.querySelectorAll('[role=\"option\"],[role=\"radio\"],li,button,div,label,span')];"
        "const banned=['옵션을선택해주세요','선택완료','취소','닫기','수거해주세요','이미보냈어요','나중에직접보낼게요'];"
        "const badWord=['품절','매진'];"
        "const isEnabled=(el)=>{"
        "if(!el) return false;"
        "if(el.disabled) return false;"
        "if(el.getAttribute('aria-disabled')==='true') return false;"
        "const st=getComputedStyle(el);"
        "if(st.pointerEvents==='none') return false;"
        "const cls=(el.className||'').toString().toLowerCase();"
        "if(cls.includes('disabled')) return false;"
        "return true;"
        "};"
        "const target=all.find(el=>{"
        "const t=norm(el.textContent||'');"
        "if(!t||t.length<2) return false;"
        "if(banned.some(k=>t===k||t.includes(k))) return false;"
        "if(badWord.some(k=>t.includes(k))) return false;"
        "const r=el.getBoundingClientRect();"
        "const st=getComputedStyle(el);"
        "if(st.display==='none'||st.visibility==='hidden'||r.width===0||r.height===0) return false;"
        "if(!isEnabled(el)) return false;"
        "return true;"
        "});"
        "if(!target) return 'no_exchange_option_candidate';"
        "try{target.scrollIntoView({block:'center'});}catch(e){}"
        "['pointerdown','mousedown','mouseup','click'].forEach(tp=>target.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
        "return 'picked_exchange_option:' + norm(target.textContent||'');"
        "})()"
    )
    option_confirm_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const btn=[...document.querySelectorAll('button,[role=\"button\"],div')].find(el=>norm(el.textContent)==='선택완료');"
        "if(!btn) return 'no_option_confirm';"
        "btn.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));"
        "return 'option_confirmed';"
        "})()"
    )
    option_needs_selection_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'');"
        "const els=[...document.querySelectorAll('div,span,p,label,button')];"
        "const match=els.find(el=>{"
        "const t=norm(el.textContent||'');"
        "if(!t.includes('옵션을선택해주세요')) return false;"
        "if(t.startsWith('배송메모')) return false;"
        "const p=el.closest('section,div,form')||el.parentElement;"
        "const pt=norm((p&&p.textContent)||'');"
        "if(pt.startsWith('배송메모')) return false;"
        "return true;"
        "});"
        "return !!match;"
        "})()"
    )
    option_modal_opened_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const visible=(el)=>{if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el); return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        "const dlg=[...document.querySelectorAll('[role=\"dialog\"],dialog,[aria-modal=\"true\"],.modal,[class*=\"modal\"],[class*=\"sheet\"],[class*=\"drawer\"]')]"
        ".find(el=>visible(el) && (norm(el.textContent||'').includes('교환옵션') || norm(el.textContent||'').includes('선택완료')));"
        "if(dlg) return true;"
        "const body=norm((document.body&&document.body.innerText)||'');"
        "if(body.includes('선택완료') && body.includes('옵션')) return true;"
        "return false;"
        "})()"
    )

    def _is_option_modal_open() -> bool:
        out = agent_browser("eval", option_modal_opened_js, check=False).stdout or ""
        return "true" in out.lower()

    def _click_text_fallback(text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return False
        # 숫자 1~2글자 토큰(예: 11/22)은 find text 충돌/대기 위험이 높아 JS/ref 우선 경로로 처리한다.
        if len(t) <= 2 and t.isdigit():
            return False
        if not _text_exists_fast(t):
            return False
        out = agent_browser("find", "text", t, "click", check=False)
        return out.returncode == 0

    def _open_option_modal_layered() -> bool:
        if _is_option_modal_open():
            return True

        # Phase 1: Snapshot 기반 — 옵션 트리거를 구조적으로 식별 (배송메모 제외)
        nodes = _snapshot_nodes()
        trigger_ref = _find_option_trigger_ref(nodes)
        if trigger_ref:
            try:
                _click_ref_with_escape_retry(trigger_ref)
                time.sleep(0.35)
                if _is_option_modal_open():
                    return True
            except Exception:
                pass

        # Phase 2: JS fallback — DOM에서 직접 옵션 요소를 찾아 클릭 (배송메모 제외, 면적 최소 요소 우선)
        js = (
            "(function(){"
            "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
            "const clickEl=(el)=>{try{el.scrollIntoView({block:'center'});}catch(e){}"
            "['pointerdown','mousedown','mouseup','click'].forEach(tp=>el.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));return true;};"
            "const els=[...document.querySelectorAll('div,span,p,label,button,[role=\"button\"]')];"
            "const candidates=els.filter(el=>{"
            "const t=norm(el.textContent||'');"
            "if(!(t.includes('옵션을선택해주세요')||t.includes('교환옵션을선택해주세요'))) return false;"
            "if(t.includes('배송메모')) return false;"
            "const p=el.closest('section,div,form')||el.parentElement;"
            "if(p&&norm(p.textContent||'').startsWith('배송메모')) return false;"
            "const r=el.getBoundingClientRect();const st=getComputedStyle(el);"
            "return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;"
            "});"
            "const optEl=candidates.sort((a,b)=>{const ra=a.getBoundingClientRect();const rb=b.getBoundingClientRect();return(ra.width*ra.height)-(rb.width*rb.height);})[0];"
            "if(optEl){clickEl(optEl);return 'clicked_option_element';}"
            "const anchor=els.find(el=>{"
            "const t=norm(el.textContent||'');"
            "return (t.includes('교환옵션')||t.includes('교환할상품'))&&!t.includes('배송메모');"
            "});"
            "if(anchor){"
            "const root=anchor.closest('section,article,li,div,form')||anchor.parentElement||document.body;"
            "const ctl=[...root.querySelectorAll('button,[role=\"button\"],select,input,[tabindex]')].find(el=>{"
            "const t=norm(el.textContent||'')||norm(el.getAttribute('aria-label')||'');"
            "if(!t) return false;"
            "if(t.includes('배송메모')||t.includes('배송지변경')||t.includes('교환요청')||t.includes('선택완료')||t.includes('취소')) return false;"
            "if(el.tagName==='INPUT'&&el.type==='file') return false;"
            "const r=el.getBoundingClientRect();const st=getComputedStyle(el);"
            "return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;"
            "});"
            "if(ctl){clickEl(ctl);return 'clicked_exchange_control';}"
            "}"
            "return 'no_option_trigger';"
            "})()"
        )
        agent_browser("eval", js, check=False)
        time.sleep(0.35)
        return _is_option_modal_open()

    def _pick_option_in_modal_layered() -> bool:
        # 활성화된 옵션 중 첫 번째만 선택한다. (다단계 옵션은 외부 루프에서 반복 처리)
        js = (
            "(function(){"
            "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
            "const visible=(el)=>{if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el); return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
            "const isContainerNamed=(el)=>{"
            "if(!el) return false;"
            "const src=[el.className||'',el.id||'',el.getAttribute&&el.getAttribute('name')||'',el.getAttribute&&el.getAttribute('data-testid')||'',el.getAttribute&&el.getAttribute('style')||'']"
            ".join(' ').toLowerCase();"
            "return src.includes('container');"
            "};"
            "const dlg=[...document.querySelectorAll('[role=\"dialog\"],dialog,[aria-modal=\"true\"],.modal,[class*=\"modal\"],[class*=\"sheet\"],[class*=\"drawer\"]')]"
            ".find(el=>visible(el) && (norm(el.textContent||'').includes('교환옵션') || norm(el.textContent||'').includes('선택완료')));"
            "const anchor=[...document.querySelectorAll('*')].find(el=>norm(el.textContent||'').includes('교환옵션을선택해주세요')||norm(el.textContent||'').includes('옵션을선택해주세요'));"
            "const section=anchor?(anchor.closest('section,article,li,div,form')||anchor.parentElement):null;"
            "const container=(dlg?[...dlg.querySelectorAll('*')]:[]).find(el=>visible(el)&&isContainerNamed(el))"
            "|| (section?[...section.querySelectorAll('*')]:[]).find(el=>visible(el)&&isContainerNamed(el))"
            "|| [anchor, anchor&&anchor.parentElement, section].find(visible);"
            "const scope=container||dlg||section||document;"
            "const banned=['옵션을선택해주세요','선택완료','취소','닫기','교환옵션','수거해주세요','이미보냈어요','나중에직접보낼게요','색상','사이즈'];"
            "const isEnabled=(el)=>{"
            "if(!el) return false;"
            "if(el.disabled) return false;"
            "if(el.getAttribute('aria-disabled')==='true') return false;"
            "const st=getComputedStyle(el);"
            "if(st.pointerEvents==='none') return false;"
            "const cls=(el.className||'').toString().toLowerCase();"
            "if(cls.includes('disabled')) return false;"
            "if(el.matches && el.matches('h1,h2,h3,h4,h5,h6')) return false;"
            "const role=(el.getAttribute&&el.getAttribute('role')||'').toLowerCase();"
            "if(role==='heading') return false;"
            "const classTxt=(el.className||'').toString().toLowerCase();"
            "if(classTxt.includes('title')||classTxt.includes('heading')) return false;"
            "return true;"
            "};"
            "const cand=[...scope.querySelectorAll('[role=\"radio\"],button,label,input[type=\"radio\"],li,div,span')].find(el=>{"
            "const t=norm(el.textContent||'');"
            "let label=t||norm((el.getAttribute('aria-label')||el.getAttribute('value')||''));"
            "if((!label||label.length<1) && el.tagName==='INPUT'){"
            "const p=el.closest('label,li,div,section,article')||el.parentElement;"
            "label=norm((p&&p.textContent)||'');"
            "}"
            "if(!label||label.length<1) return false;"
            "if(banned.some(b=>label.includes(b))) return false;"
            "if(label==='색상'||label==='사이즈') return false;"
            "if(label.includes('품절')||label.includes('매진')) return false;"
            "const r=el.getBoundingClientRect();"
            "if(!(r.width>1&&r.height>1)) return false;"
            "return isEnabled(el);"
            "});"
            "if(!cand) return 'no_option_candidate';"
            "const hit=cand.tagName==='INPUT'?(cand.closest('label,div,[role=\"radio\"]')||cand):cand;"
            "try{hit.scrollIntoView({block:'center'});}catch(e){}"
            "['pointerdown','mousedown','mouseup','click'].forEach(tp=>hit.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
            "return 'selected_candidate';"
            "})()"
        )
        out = agent_browser("eval", js, check=False).stdout or ""
        return "selected_candidate" in out

    def _click_option_done_layered() -> bool:
        # 1) snapshot ref
        for txt in ("선택 완료", "선택완료"):
            try:
                _click_by_snapshot_text(txt)
                time.sleep(0.25)
                return True
            except Exception:
                pass

        # 2) find text
        for txt in ("선택 완료", "선택완료"):
            if _click_text_fallback(txt):
                time.sleep(0.25)
                return True

        # 3) JS fallback
        js = (
            "(function(){"
            "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
            "const dlg=[...document.querySelectorAll('[role=\"dialog\"],dialog')].find(el=>norm(el.textContent||'').includes('교환옵션'))||document;"
            "const btn=[...dlg.querySelectorAll('button,[role=\"button\"],div')].find(el=>norm(el.textContent||'')==='선택완료');"
            "if(!btn) return 'no_done_btn';"
            "['pointerdown','mousedown','mouseup','click'].forEach(tp=>btn.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
            "return 'done_clicked';"
            "})()"
        )
        out = agent_browser("eval", js, check=False).stdout or ""
        return "done_clicked" in out

    def _handle_input_type_option() -> bool:
        """입력형 옵션 모달 처리: 텍스트 입력 + 드롭다운(색상/사이즈 등) 선택.

        검증된 DOM 구조 패턴:
        - 드롭다운 헤더: SVG chevron 포함 div (짧은 텍스트, 적절한 크기)
        - 옵션 리스트: .list-container 클래스 (헤더 클릭 시 나타남)
        - 색상 선택 후 사이즈가 자동으로 열림 → .list-container 반복 처리
        - 品절 옵션 제외, PointerEvent + elementFromPoint 패턴 사용
        Returns True if the input-type option was detected and handled.
        """
        detect_js = (
            "(function(){"
            "var norm=function(s){return(s||'').replace(/\\s+/g,'').trim();};"
            "var body=norm((document.body&&document.body.innerText)||'');"
            "if(!body.includes('\uad50\ud658\uc635\uc158')) return 'no_exchange_option_modal';"
            "var inputs=[].slice.call(document.querySelectorAll('input[type=\"text\"],textarea'));"
            "var hasInput=inputs.some(function(el){"
            "var ph=norm(el.getAttribute('placeholder')||'');"
            "return ph.includes('\uc785\ub825\ud574\uc8fc\uc138\uc694');"
            "});"
            "var excluded=['주문교환','주문반품','주문취소','교환신청','반품신청','취소신청',"
            "'교환요청','반품요청','취소요청','배송메모','배송메모를','사유선택','사유를선택해주세요',"
            "'수거방법','수거방법선택','교환사유','반품사유','취소사유','사진첨부'];"
            "var headers=[].slice.call(document.querySelectorAll('div')).filter(function(el){"
            "var t=norm(el.textContent||'');"
            "if(t.length<1||t.length>6) return false;"
            "if(excluded.indexOf(t)>=0) return false;"
            "var r=el.getBoundingClientRect();"
            "if(r.top<60) return false;"
            "if(r.width<100||r.height<30||r.height>80) return false;"
            "return !!el.querySelector('svg');"
            "});"
            "if(hasInput) return 'input_type:inputs='+hasInput+',dropdowns='+headers.length;"
            "return 'not_input_type';"
            "})()"
        )
        detect_out = (agent_browser("eval", detect_js, check=False).stdout or "").strip()
        if "input_type:" not in detect_out:
            return False

        import logging as _logging
        _log = _logging.getLogger("order-agent-exec")
        _log.info("Input-type option modal detected: %s", detect_out)

        # PointerEvent 클릭 헬퍼 JS — elementFromPoint 사용으로 React 이벤트 정확 전달
        _ptr_click_js = (
            "__TARGET__.scrollIntoView({block:'center'});"
            "var __r=__TARGET__.getBoundingClientRect();"
            "var __cx=__r.left+__r.width/2,__cy=__r.top+__r.height/2;"
            "var __hit=document.elementFromPoint(__cx,__cy)||__TARGET__;"
            "['pointerdown','pointerup','mousedown','mouseup','click'].forEach(function(tp){"
            "__hit.dispatchEvent(new PointerEvent(tp,{bubbles:true,cancelable:true,view:window,"
            "clientX:__cx,clientY:__cy,pointerId:1,pointerType:'mouse'}));"
            "});"
        )

        # 0) 옵션 피커 트리거("교환옵션을선택해주세요")가 닫혀있으면 먼저 열기
        #    클릭 시 색상/사이즈 드롭다운이 인라인 확장됨 (토글이므로 이미 열려있으면 스킵)
        _open_option_picker_js = (
            "(function(){"
            "var norm=function(s){return(s||'').replace(/\\s+/g,'').trim();};"
            # 이미 색상/사이즈 드롭다운이 보이면 피커가 열린 상태 → 스킵
            "var ddHeaders=[].slice.call(document.querySelectorAll('div')).filter(function(el){"
            "var t=norm(el.textContent||'');"
            "return (t==='\uc0c9\uc0c1'||t==='\uc0ac\uc774\uc988')&&el.querySelector('svg')&&el.getBoundingClientRect().height>30;"
            "});"
            "if(ddHeaders.length>0) return 'already_open:dropdowns='+ddHeaders.length;"
            # 피커 트리거를 찾아 클릭
            "var els=[].slice.call(document.querySelectorAll('div'));"
            "var target=null;"
            "for(var i=0;i<els.length;i++){"
            "var t=norm(els[i].textContent||'');"
            "if(t!=='\uad50\ud658\uc635\uc158\uc744\uc120\ud0dd\ud574\uc8fc\uc138\uc694'"
            "&&t!=='\uc635\uc158\uc744\uc120\ud0dd\ud574\uc8fc\uc138\uc694'"
            "&&t!=='\uc635\uc158\uc744\uc120\ud0dd\ud574\uc8fc\uc138\uc694.') continue;"
            "var r=els[i].getBoundingClientRect();"
            "if(r.height<25||r.height>60||r.width<150) continue;"
            "target=els[i]; break;}"
            "if(!target) return 'no_picker_trigger';"
            "target.scrollIntoView({block:'center'});"
            "var rr=target.getBoundingClientRect();"
            "var cx=rr.left+rr.width/2,cy=rr.top+rr.height/2;"
            "var hit=document.elementFromPoint(cx,cy)||target;"
            "['pointerdown','pointerup','mousedown','mouseup','click'].forEach(function(tp){"
            "hit.dispatchEvent(new PointerEvent(tp,{bubbles:true,cancelable:true,view:window,"
            "clientX:cx,clientY:cy,pointerId:1,pointerType:'mouse'}));"
            "});"
            "return 'opened_picker:'+t;"
            "})()"
        )
        picker_out = (agent_browser("eval", _open_option_picker_js, check=False).stdout or "").strip()
        _log.info("Option picker open: %s", picker_out)
        if "no_picker_trigger" not in picker_out and "already_open" not in picker_out:
            time.sleep(0.8)

        # 1) 텍스트 입력 필드 채우기 (snapshot ref 활용)
        nodes = _snapshot_nodes()
        for role, label, ref in nodes:
            n = _label_norm(label)
            if "입력해주세요" in n or "필수" in n:
                try:
                    agent_browser("fill", f"@{ref}", "test", check=True)
                    _log.info("Filled input-type text field @%s", ref)
                    time.sleep(0.3)
                except Exception:
                    pass
                break

        # 2) 드롭다운 순차 처리 — .list-container 패턴 활용
        #    첫 드롭다운 헤더를 클릭하면 .list-container가 나타나고,
        #    옵션 선택 후 다음 드롭다운이 자동으로 열림.
        #    .list-container가 없어질 때까지 반복.
        _pick_from_list_js = (
            "(function(){"
            "var norm=function(s){return(s||'').replace(/\\s+/g,'').trim();};"
            "var lcs=document.querySelectorAll('.list-container');"
            "if(!lcs.length) return 'no_list';"
            "var lc=lcs[lcs.length-1];"
            "var items=[].slice.call(lc.children);"
            "var pick=null;"
            "for(var i=0;i<items.length;i++){"
            "var t=norm(items[i].textContent||'');"
            "if(t.includes('\ud488\uc808')) continue;"  # 품절 제외
            "var st=getComputedStyle(items[i]);"
            "if(st.opacity!==''&&parseFloat(st.opacity)<0.5) continue;"
            "if(st.pointerEvents==='none') continue;"
            "pick=items[i]; break;}"
            "if(!pick) return 'all_soldout';"
            "pick.scrollIntoView({block:'center'});"
            "var r=pick.getBoundingClientRect();"
            "var cx=r.left+r.width/2, cy=r.top+r.height/2;"
            "var hit=document.elementFromPoint(cx,cy)||pick;"
            "['pointerdown','pointerup','mousedown','mouseup','click'].forEach(function(tp){"
            "hit.dispatchEvent(new PointerEvent(tp,{bubbles:true,cancelable:true,view:window,"
            "clientX:cx,clientY:cy,pointerId:1,pointerType:'mouse'}));"
            "});"
            "return 'picked:'+norm(pick.textContent||'');"
            "})()"
        )

        _open_first_closed_dd_js = (
            "(function(){"
            "var norm=function(s){return(s||'').replace(/\\s+/g,'').trim();};"
            "var excluded=['주문교환','주문반품','주문취소','교환신청','반품신청','취소신청',"
            "'교환요청','반품요청','취소요청','배송메모','배송메모를','사유선택','사유를선택해주세요',"
            "'수거방법','수거방법선택','교환사유','반품사유','취소사유','사진첨부'];"
            "var els=[].slice.call(document.querySelectorAll('div'));"
            "for(var i=0;i<els.length;i++){"
            "var t=norm(els[i].textContent||'');"
            "if(t.length<1||t.length>6) continue;"
            "if(excluded.indexOf(t)>=0) continue;"
            "var r=els[i].getBoundingClientRect();"
            "if(r.top<60) continue;"
            "if(r.width<100||r.height<30||r.height>80) continue;"
            "if(!els[i].querySelector('svg')) continue;"
            # 이미 열린 드롭다운(list-container가 형제에 있음)은 건너뜀
            "var parent=els[i].parentElement;"
            "if(parent&&parent.querySelector('.list-container')) continue;"
            "els[i].scrollIntoView({block:'center'});"
            "var rr=els[i].getBoundingClientRect();"
            "var cx=rr.left+rr.width/2,cy=rr.top+rr.height/2;"
            "var hit=document.elementFromPoint(cx,cy)||els[i];"
            "['pointerdown','pointerup','mousedown','mouseup','click'].forEach(function(tp){"
            "hit.dispatchEvent(new PointerEvent(tp,{bubbles:true,cancelable:true,view:window,"
            "clientX:cx,clientY:cy,pointerId:1,pointerType:'mouse'}));"
            "});"
            "return 'opened:'+t;"
            "}"
            "return 'no_closed_dd';"
            "})()"
        )

        # A) 첫 번째 닫힌 드롭다운만 명시적으로 열기 (색상)
        #    이후 드롭다운(사이즈 등)은 옵션 선택 시 자동으로 열림 (cascade)
        open_out = (agent_browser("eval", _open_first_closed_dd_js, check=False).stdout or "").strip()
        _log.info("Dropdown open (initial): %s", open_out)
        if "no_closed_dd" not in open_out:
            time.sleep(0.5)

        # B) .list-container가 존재하는 동안 반복하여 옵션 선택
        #    색상 선택 → 사이즈 자동 열림 → 사이즈 선택 → cascade 종료
        max_dd_rounds = 6
        for _round in range(max_dd_rounds):
            has_list = "list" in (agent_browser("eval",
                "(function(){return document.querySelector('.list-container')?'list':'none';})()",
                check=False).stdout or "")
            if not has_list:
                break
            pick_out = (agent_browser("eval", _pick_from_list_js, check=False).stdout or "").strip()
            _log.info("Dropdown pick [round %d]: %s", _round, pick_out)
            time.sleep(0.5)

        # 2-b) Fallback: native <select> 요소 처리 (list-container가 없는 UI)
        _select_fallback_js = (
            "(function(){"
            "var norm=function(s){return(s||'').replace(/\\s+/g,'').trim();};"
            "var selects=[].slice.call(document.querySelectorAll('select'));"
            "var changed=0;"
            "for(var i=0;i<selects.length;i++){"
            "var opts=selects[i].options;"
            "if(!opts||opts.length<2) continue;"
            "if(selects[i].selectedIndex>0) continue;"
            "for(var j=1;j<opts.length;j++){"
            "if(opts[j].disabled) continue;"
            "var txt=norm(opts[j].text||'');"
            "if(txt.includes('\ud488\uc808')||txt.includes('\ub9e4\uc9c4')) continue;"
            "selects[i].selectedIndex=j;"
            "selects[i].dispatchEvent(new Event('change',{bubbles:true}));"
            "selects[i].dispatchEvent(new Event('input',{bubbles:true}));"
            "changed++; break;}"
            "}"
            "return 'select_fallback:changed='+changed;"
            "})()"
        )
        sel_out = (agent_browser("eval", _select_fallback_js, check=False).stdout or "").strip()
        if "changed=0" not in sel_out:
            _log.info("Select element fallback: %s", sel_out)
            time.sleep(0.5)

        # 3) 선택완료 버튼 클릭
        time.sleep(0.3)
        done_clicked = False
        nodes = _snapshot_nodes()
        for role, label, ref in nodes:
            n = _label_norm(label)
            if n in ("선택완료", "선택 완료"):
                try:
                    _click_ref_with_escape_retry(ref)
                    _log.info("Clicked done button @%s via snapshot", ref)
                    done_clicked = True
                except Exception:
                    pass
                break

        if not done_clicked:
            done_js = (
                "(function(){"
                "var norm=function(s){return(s||'').replace(/\\s+/g,'').trim();};"
                "var btns=[].slice.call(document.querySelectorAll('button,div,[role=\"button\"],span'));"
                "for(var i=0;i<btns.length;i++){"
                "var t=norm(btns[i].textContent||'');"
                "if(t!=='\uc120\ud0dd\uc644\ub8cc') continue;"
                "var r=btns[i].getBoundingClientRect();"
                "if(r.width<30||r.height<15) continue;"
                + _ptr_click_js.replace("__TARGET__", "btns[i]") +
                "return 'done_clicked';"
                "}"
                "return 'no_done_btn';"
                "})()"
            )
            done_out = (agent_browser("eval", done_js, check=False).stdout or "").strip()
            _log.info("Option done result: %s", done_out)
            done_clicked = "done_clicked" in done_out

        time.sleep(0.5)
        return done_clicked or not _needs_option_selection()

    def _needs_option_selection() -> bool:
        out = agent_browser("eval", option_needs_selection_js, check=False).stdout or ""
        return "true" in out.lower()

    def _has_chunk_load_error() -> bool:
        err = (agent_browser("errors", check=False).stdout or "").lower()
        return "loading chunk" in err or "chunkloaderror" in err or ".undefined.js" in err

    def _ensure_exchange_product_selected(max_tries: int = 3) -> bool:
        for _ in range(max_tries):
            if not _needs_option_selection():
                return True

            # 다단계 옵션 대응: 옵션 프롬프트가 사라질 때까지 첫 활성 옵션을 반복 선택
            max_option_levels = 6
            for _level in range(max_option_levels):
                if not _needs_option_selection():
                    return True

                # A) Snapshot 기반으로 옵션 모달 열기 (배송메모 오매칭 방지)
                _open_option_modal_layered()
                time.sleep(0.3)

                # B) 입력형 옵션 모달 우선 처리 (텍스트+드롭다운)
                if _handle_input_type_option():
                    time.sleep(0.3)
                    if not _needs_option_selection():
                        return True
                    continue

                # C) 라디오/버튼형 옵션 선택 (JS → snapshot fallback)
                picked = _pick_option_in_modal_layered()
                if not picked:
                    agent_browser("eval", option_pick_one_js, check=False)
                    time.sleep(0.2)
                    _try_select_exchange_option_by_snapshot()

                # D) 선택완료 클릭
                done = _click_option_done_layered()
                if not done:
                    agent_browser("eval", option_confirm_js, check=False)
                    time.sleep(0.3)

                time.sleep(0.35)
                if not _needs_option_selection():
                    return True

            if _has_chunk_load_error():
                current_url = agent_browser("get", "url", check=False).stdout.strip()
                if current_url and "/request-exchange" in current_url:
                    _safe_open_url(current_url, retries=5)
                    time.sleep(1.0)
        return not _needs_option_selection()

    if not _ensure_exchange_product_selected(max_tries=3):
        current_url = agent_browser("get", "url", check=True).stdout.strip()
        raise RuntimeError(
            "SUBMIT_EXCHANGE_REQUEST failed [EXCHANGE_OPTION_SELECTION_REQUIRED]: "
            f"unable to select first enabled option in exchange modal ({current_url})"
        )

    _ensure_claim_reason_selected(reason_norm, "EXCHANGE")
    _fill_default_required_inputs("test")

    pickup_select_js = (
        "(function(){"
        "const isVisible=(el)=>{if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el); return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        "const radios=[...document.querySelectorAll('[role=\"radio\"],input[type=\"radio\"]')].filter(el=>isVisible(el) && !el.disabled);"
        "if(!radios.length) return 'no_pickup_option';"
        "const t=radios[0];"
        "const hit=t.tagName==='INPUT'?(t.closest('label,div,[role=\"radio\"]')||t):t;"
        "try{hit.scrollIntoView({block:'center'});}catch(e){}"
        "['pointerdown','mousedown','mouseup','click'].forEach(tp=>hit.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
        "return 'pickup_clicked';"
        "})()"
    )
    pickup_checked_js = (
        "(function(){"
        "if([ ...document.querySelectorAll('input[type=\"radio\"]')].some(r=>r.checked)) return true;"
        "return [...document.querySelectorAll('[role=\"radio\"]')].some(el=>el.getAttribute('aria-checked')==='true');"
        "})()"
    )

    pickup_ok = False
    for _ in range(3):
        agent_browser("eval", pickup_select_js, check=False)
        time.sleep(0.25)
        checked_out = agent_browser("eval", pickup_checked_js, check=False).stdout or ""
        if "true" in checked_out.lower():
            pickup_ok = True
            break
    if not pickup_ok:
        agent_browser("click", "text=수거해주세요", check=False)
        time.sleep(0.2)

    agent_browser("press", "End", check=False)
    time.sleep(0.3)

    check_notice_js = (
        "(function(){"
        "const label=[...document.querySelectorAll('label')].find(el=>(el.textContent||'').includes('교환 안내사항을 확인했습니다.'));"
        "if(!label) throw new Error('exchange_notice_label_not_found');"
        "label.scrollIntoView({block:'center'});"
        "const cb=label.querySelector('input[type=\"checkbox\"]');"
        "if(!cb) throw new Error('exchange_notice_checkbox_not_found');"
        "if(cb.checked) return 'exchange_notice_checked_already';"
        "label.click();"
        "if(!cb.checked){"
        "cb.checked=true;"
        "cb.dispatchEvent(new Event('input',{bubbles:true}));"
        "cb.dispatchEvent(new Event('change',{bubbles:true}));"
        "}"
        "if(!cb.checked) throw new Error('exchange_notice_checkbox_not_checked');"
        "return 'exchange_notice_checked';"
        "})()"
    )
    notice_ok = False
    for _ in range(3):
        out = (agent_browser("eval", check_notice_js, check=False).stdout or "").strip()
        if "exchange_notice_checked" in out:
            notice_ok = True
            break
        time.sleep(0.2)
    if not notice_ok:
        evidence = _collect_claim_page_evidence()
        raise RuntimeError(
            "SUBMIT_EXCHANGE_REQUEST failed [EXCHANGE_NOTICE_CHECK_REQUIRED]: "
            f"unable to check exchange notice within 3 tries; evidence={json.dumps(evidence, ensure_ascii=False)}"
        )

    submit_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const labels=['교환요청하기','교환요청','교환요청하기','교환요청','다음단계로이동'];"
        "const btn=[...document.querySelectorAll('button,[role=\"button\"],div')].find(el=>labels.includes(norm(el.textContent)));"
        "if(!btn) return 'no_exchange_submit_button';"
        "try{btn.scrollIntoView({block:'center'});}catch(e){}"
        "['pointerdown','mousedown','mouseup','click'].forEach(tp=>btn.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})));"
        "return 'exchange_submit_clicked:' + norm(btn.textContent);"
        "})()"
    )

    max_submit_attempts = 3
    submit_attempts = 0

    def _attempt_exchange_submit() -> str:
        nonlocal submit_attempts
        if submit_attempts >= max_submit_attempts:
            evidence = _collect_claim_page_evidence()
            raise RuntimeError(
                "SUBMIT_EXCHANGE_REQUEST failed [EXCHANGE_SUBMIT_RETRY_EXCEEDED]: "
                f"submit retry reached {max_submit_attempts}; evidence={json.dumps(evidence, ensure_ascii=False)}"
            )
        submit_attempts += 1
        try:
            _click_by_snapshot_text("교환 요청하기")
            return "exchange_submit_clicked:교환요청하기(snapshot-spaced)"
        except Exception:
            pass
        try:
            _click_by_snapshot_text("교환요청하기")
            return "exchange_submit_clicked:교환요청하기(snapshot)"
        except Exception:
            pass
        return (agent_browser("eval", submit_js, check=False).stdout or "").strip()

    submit_result = _attempt_exchange_submit()
    time.sleep(1.1)
    if "다음단계로이동" in submit_result:
        # 1단계 버튼을 누른 뒤 최종 교환요청 버튼이 노출되는 케이스 처리
        _attempt_exchange_submit()
        time.sleep(0.9)

    # "확인" 버튼 클릭 JS (폴링 루프에서도 사용)
    confirm_js = (
        "(function(){"
        "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
        "const ok=[...document.querySelectorAll('button,[role=\"button\"],div')].find(el=>norm(el.textContent)==='확인');"
        "if(ok){ok.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); return 'clicked_confirm';}"
        "return 'no_confirm_modal';"
        "})()"
    )

    # 제출 후 모달/페이지 변화를 기다린 뒤 폴링 루프에서 결과를 판단한다.
    # "확인" 모달을 여기서 닫지 않아야 폴링 루프에서 정책 차단 메시지를 감지할 수 있다.
    time.sleep(1.5)

    def _page_text_norm() -> str:
        out = agent_browser(
            "eval",
            "(function(){return ((document.body&&document.body.innerText)||'').replace(/\\s+/g,'');})()",
            check=False,
        ).stdout or ""
        return out.strip().lower()

    deadline = time.time() + 8.0
    while time.time() < deadline:
        current_url = agent_browser("get", "url", check=True).stdout.strip()
        if "/request-exchange" not in current_url:
            _apply_full_points_on_exchange_cost_sheet(current_url)
            return current_url

        body_norm = _page_text_norm()
        if "사유를선택해주세요" in body_norm:
            _ensure_claim_reason_selected(reason_norm, "EXCHANGE")
            time.sleep(0.25)
            continue

        if "수거방법을선택해주세요" in body_norm:
            agent_browser("eval", pickup_select_js, check=False)
            time.sleep(0.25)
            _attempt_exchange_submit()
            time.sleep(0.6)
            continue

        if "1+1상품은구매한옵션을모두교환요청해야합니다" in body_norm:
            raise RuntimeError(
                "SUBMIT_EXCHANGE_REQUEST failed [EXCHANGE_REQUEST_BLOCKED_1P1]: "
                "1+1 option set must be exchanged together"
            )

        # 정책 차단 감지 (협찬 프로모션 등)
        _policy_block_keywords = ["협찬프로모션은", "요청을할수없습니다", "취소,반품,교환요청을"]
        if any(kw in body_norm for kw in _policy_block_keywords):
            # "확인" 눌러 모달 닫기
            try:
                _click_by_snapshot_text("확인")
            except Exception:
                agent_browser("eval", confirm_js, check=False)
            # body에서 차단 메시지 추출
            _block_snippet = ""
            for kw in _policy_block_keywords:
                idx = body_norm.find(kw)
                if idx >= 0:
                    _block_snippet = body_norm[max(0, idx):idx + 60]
                    break
            raise RuntimeError(
                f"SUBMIT_EXCHANGE_REQUEST failed [EXCHANGE_POLICY_BLOCKED]: {_block_snippet}"
            )

        if "옵션을선택해주세요" in body_norm:
            _ensure_exchange_product_selected(max_tries=3)
            time.sleep(0.35)
            _attempt_exchange_submit()
            time.sleep(0.55)
            continue

        # 버튼이 남아있으면 재제출을 시도한다.
        submit_visible_js = (
            "(function(){"
            "const norm=s=>(s||'').replace(/\\s+/g,'').trim();"
            "const btn=[...document.querySelectorAll('button,[role=\"button\"],div')].find(el=>['교환요청하기','교환요청','교환요청하기','교환요청','교환요청하기','교환 요청하기','다음단계로이동'].includes(norm(el.textContent)));"
            "return !!btn;"
            "})()"
        )
        submit_visible = "true" in (agent_browser("eval", submit_visible_js, check=False).stdout or "").lower()
        if submit_visible:
            _attempt_exchange_submit()
            time.sleep(0.35)

        try:
            _click_by_snapshot_text("확인")
        except Exception:
            agent_browser("eval", confirm_js, check=False)
        time.sleep(0.6)

    current_url = agent_browser("get", "url", check=True).stdout.strip()
    body_text = agent_browser(
        "eval",
        "(function(){return ((document.body&&document.body.innerText)||'').replace(/\\s+/g,' ').trim().slice(0,600);})()",
        check=False,
    ).stdout.strip()
    errors_text = (agent_browser("errors", check=False).stdout or "").lower()
    chunk_failed = "loading chunk" in errors_text or "chunkloaderror" in errors_text
    option_needed = _needs_option_selection()
    if option_needed and chunk_failed:
        raise RuntimeError(
            "SUBMIT_EXCHANGE_REQUEST failed [EXCHANGE_UI_CHUNK_LOAD]: "
            f"option selector unavailable with chunk load errors; url=({current_url})"
        )
    if option_needed:
        raise RuntimeError(
            "SUBMIT_EXCHANGE_REQUEST failed [EXCHANGE_OPTION_SELECTION_REQUIRED]: "
            f"exchange option still required on page ({current_url})"
        )
    evidence = _collect_claim_page_evidence()
    raise RuntimeError(
        "SUBMIT_EXCHANGE_REQUEST failed [EXCHANGE_REQUEST_STUCK]: "
        f"still on request-exchange page ({current_url}); chunkLoadFailed={chunk_failed}; "
        f"optionSelectionRequired={option_needed}; submitAttempts={submit_attempts}/{max_submit_attempts}; "
        f"body='{body_text[:200]}'; evidence={json.dumps(evidence, ensure_ascii=False)}"
    )


def _collect_active_modal_info() -> dict[str, object]:
    js = (
        "(function(){"
        "const text=(el)=>(el&&el.textContent?el.textContent:'').replace(/\\s+/g,' ').trim();"
        "const visible=(el)=>{if(!el)return false;const st=getComputedStyle(el);const r=el.getBoundingClientRect();"
        "return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0;};"
        "const selectors=['[role=\"dialog\"]','[aria-modal=\"true\"]','dialog','.modal','.MuiDialog-root','.ReactModal__Overlay','[class*=\"modal\"]','[class*=\"sheet\"]','[class*=\"drawer\"]','[data-rsbs-root]'];"
        "const dialogs=[...new Set(selectors.flatMap(sel=>[...document.querySelectorAll(sel)]))].filter(visible);"
        "const target=dialogs.length?dialogs[dialogs.length-1]:null;"
        "const pick=[...document.querySelectorAll('[role=\"alert\"],[class*=\"error\"],[class*=\"toast\"],[class*=\"snackbar\"],[data-testid*=\"error\"]')]"
        ".filter(visible).map(el=>text(el)).filter(Boolean).slice(0,5);"
        "const keyword=['재고','품절','주문','결제','실패','한도','제한','불가'];"
        "const hints=[...new Set([...document.querySelectorAll('p,li,[role=\"status\"]')].map(el=>text(el)).filter(t=>t&&t.length<160&&keyword.some(k=>t.includes(k))))].slice(0,5);"
        "if(!target){return JSON.stringify({hasModal:false,url:location.href,alerts:pick,hints:hints});}"
        "const title=target.querySelector('h1,h2,h3,[class*=\"title\"],[data-testid*=\"title\"]');"
        "const buttons=[...target.querySelectorAll('button,[role=\"button\"]')].map(el=>text(el)).filter(Boolean);"
        "return JSON.stringify({hasModal:true,url:location.href,modalTitle:text(title),modalText:text(target).slice(0,1400),modalButtons:buttons,alerts:pick,hints:hints});"
        "})()"
    )
    out = agent_browser("eval", js, check=False).stdout.strip()
    try:
        parsed = json.loads(out)
        if isinstance(parsed, str):
            return json.loads(parsed)
        if isinstance(parsed, dict):
            return parsed
        return {"hasModal": False, "raw": parsed}
    except Exception:
        return {"hasModal": False, "raw": out}


def _failure_modal_summary() -> str:
    payload = _collect_active_modal_info()
    has_modal = bool(payload.get("hasModal"))
    modal_title = str(payload.get("modalTitle") or "").strip()
    modal_text = str(payload.get("modalText") or "").strip()
    alerts = payload.get("alerts") or []

    modal_text_short = " ".join(modal_text.split())[:300] if modal_text else ""
    alert_short = " | ".join(str(x).strip() for x in alerts[:2] if str(x).strip())

    fields: list[str] = [f"hasModal={has_modal}"]
    if modal_title:
        fields.append(f"title='{modal_title[:120]}'")
    if modal_text_short:
        fields.append(f"guidanceText='{modal_text_short}'")
    if alert_short:
        fields.append(f"alerts='{alert_short[:220]}'")
    return "; ".join(fields)


def _collect_order_sheet_evidence() -> dict[str, object]:
    js = (
        "(function(){"
        "const text=(el)=>(el&&el.textContent?el.textContent:'').replace(/\\s+/g,' ').trim();"
        "const uniq=(arr)=>[...new Set(arr.filter(Boolean))];"
        "const payBtn=[...document.querySelectorAll('button,[role=\"button\"]')].find(el=>{"
        "const t=text(el).replace(/\\s+/g,'');"
        "return t.includes('결제하기')||t.includes('구매하기');"
        "});"
        "const cbs=[...document.querySelectorAll('input[type=\"checkbox\"]')];"
        "const agree=cbs.find(el=>text(el.closest('label,section,div,article')||document.body).includes('주문내용 확인 및 결제 동의'));"
        "const pointInput=[...document.querySelectorAll('input,textarea')].find(el=>(el.getAttribute('placeholder')||'').includes('포인트'));"
        "const alerts=[...document.querySelectorAll('[role=\"alert\"],[class*=\"error\"],[class*=\"toast\"],[class*=\"snackbar\"],[data-testid*=\"error\"]')]"
        ".map(el=>text(el)).filter(Boolean).slice(0,5);"
        "const keys=['재고','품절','주문','결제','실패','한도','제한','불가','초과','오류','잠시','다시'];"
        "const nearby=payBtn?text(payBtn.closest('section,article,div,form')||payBtn.parentElement):'';"
        "const fromLive=[...document.querySelectorAll('[role=\"status\"],[aria-live]')].map(el=>text(el));"
        "const fromAll=[...document.querySelectorAll('p,span,li,div')].map(el=>text(el)).filter(t=>t&&t.length<=180&&keys.some(k=>t.includes(k)));"
        "const messageCandidates=uniq([nearby,...fromLive,...fromAll,...alerts]).slice(0,8);"
        "return JSON.stringify({"
        "url:location.href,"
        "isOrderSheet:location.href.includes('/checkout/order-sheets/'),"
        "payButtonText:payBtn?text(payBtn):null,"
        "zeroPayVisible:[...document.querySelectorAll('button,[role=\"button\"]')].some(el=>text(el).includes('0원')),"
        "agreeChecked:agree?!!agree.checked:null,"
        "pointInputValue:pointInput?(pointInput.value||''):null,"
        "alerts:alerts,"
        "messageCandidates:messageCandidates"
        "});"
        "})()"
    )
    out = agent_browser("eval", js, check=False).stdout.strip()
    try:
        parsed = json.loads(out)
        if isinstance(parsed, str):
            return json.loads(parsed)
        if isinstance(parsed, dict):
            submit_ui = _collect_inline_submit_guidance()
            parsed["submitUiMessage"] = str(submit_ui.get("text") or "")[:400]
            parsed["submitUiSource"] = str(submit_ui.get("source") or "")
            return parsed
        return {"raw": parsed}
    except Exception:
        return {"raw": out}



@dataclass
class _StepResult:
    step: int
    line_no: int
    action: str
    summary: str
    ok: bool
    elapsed_ms: float
    error: str = ""


def _action_summary(action: str, args: list[str], max_len: int = 60) -> str:
    """Return a human-readable one-line summary of a scenario command."""
    if action == "EVAL":
        code = args[0] if args else ""
        if "return" in code:
            last_return = code.rsplit("return ", 1)[-1].split(";")[0].strip("'\" )(")
            tag = last_return[:40]
        else:
            tag = code[:40]
        return f"EVAL [{tag}...]"
    raw = " ".join([action, *args])
    if len(raw) <= max_len:
        return raw
    return raw[:max_len - 3] + "..."


def _print_report(
    scenario_name: str,
    results: list[_StepResult],
    total_elapsed_ms: float,
    dry_run: bool,
    outputs: list[tuple[str, str]] | None = None,
) -> None:
    """Print a formatted execution report to stderr."""
    out = sys.stderr
    passed = sum(1 for r in results if r.ok)
    failed = sum(1 for r in results if not r.ok)
    total = len(results)
    mode = "[DRY-RUN] " if dry_run else ""

    out.write(f"\n{'─'*70}\n")
    out.write(f"  {mode}Report: {scenario_name}\n")
    out.write(f"{'─'*70}\n")

    skipped = sum(1 for r in results if r.error == "SKIP (not executed)")
    for r in results:
        if r.error == "SKIP (not executed)":
            mark = "SKIP"
        elif r.ok:
            mark = "PASS"
        else:
            mark = "FAIL"
        time_str = f"{r.elapsed_ms:7.0f}ms"
        out.write(f"  {mark}  {r.step:>3}/{total}  L{r.line_no:<4}  {time_str}  {r.summary}\n")
        if not r.ok and r.error and r.error != "SKIP (not executed)":
            out.write(f"              ↳ {r.error}\n")

    out.write(f"{'─'*70}\n")
    total_sec = total_elapsed_ms / 1000
    out.write(f"  Steps: {passed} passed")
    if failed:
        out.write(f", {failed - skipped} failed")
    if skipped:
        out.write(f", {skipped} skipped")
    out.write(f" / {total} total")
    out.write(f"  |  Time: {total_sec:.1f}s\n")

    if outputs:
        out.write(f"{'─'*70}\n")
        out.write("  Key outputs:\n")
        for label, value in outputs:
            out.write(f"    {label}: {value}\n")

    # 실패 요약
    failed_results = [r for r in results if not r.ok and r.error and r.error != "SKIP (not executed)"]
    if failed_results:
        out.write(f"{'─'*70}\n")
        out.write("  Failure summary:\n")
        for r in failed_results:
            # [ERROR_CODE] 추출, 없으면 첫 60자
            import re as _re
            code_match = _re.search(r"\[([A-Z_]+)\]", r.error)
            code = code_match.group(1) if code_match else ""
            # 에러 메시지에서 핵심 부분만 추출 (]: 이후 또는 전체)
            msg = r.error
            if "]: " in msg:
                msg = msg.split("]: ", 1)[1]
            msg = msg[:80]
            if code:
                out.write(f"    L{r.line_no} {r.summary[:30]:<30}  [{code}] {msg}\n")
            else:
                out.write(f"    L{r.line_no} {r.summary[:30]:<30}  {msg}\n")

    # Self-Heal 요약
    if _self_heal_log:
        out.write(f"{'─'*70}\n")
        out.write("  Self-Heal (UI 변경 자동 복구):\n")
        for entry in _self_heal_log:
            out.write(f"    '{entry['old_text']}' → '{entry['new_text']}' ({entry['similarity']})\n")
        out.write("  ⚠ 시나리오 파일의 텍스트를 위 매칭 결과로 업데이트하세요.\n")

    out.write(f"{'─'*70}\n\n")



def _preflight_check(logger: "logging.Logger", dry_run: bool = False) -> bool:
    """Run environment checks before scenario execution. Returns True if ready."""
    if dry_run:
        return True

    out = sys.stderr
    out.write(f"\n{'─'*70}\n")
    out.write("  Preflight Check\n")
    out.write(f"{'─'*70}\n")

    # 1. agent-browser CLI
    import shutil
    ab_path = shutil.which("agent-browser")
    if not ab_path:
        out.write("  FAIL  agent-browser CLI not found in PATH\n")
        out.write(f"{'─'*70}\n\n")
        logger.error("Preflight failed: agent-browser not in PATH")
        return False
    out.write(f"  PASS  agent-browser: {ab_path}\n")

    # 2. CDP connection / browser auto-launch
    try:
        from core.runner import _ensure_cdp_browser_ready, _cdp_port
        port = _cdp_port()
        cdp_ok = _ensure_cdp_browser_ready()
        if not cdp_ok:
            out.write(f"  FAIL  CDP port {port}: no browser running\n")
            out.write("        -> Chrome을 CDP 모드로 실행하세요:\n")
            out.write("           ./scripts/run_scenario_chrome.sh <scenario.scn>\n")
            out.write(f"{'─'*70}\n\n")
            logger.error("Preflight failed: CDP not ready on port %s", port)
            return False
        out.write(f"  PASS  CDP port {port}: connected\n")
    except Exception as exc:
        out.write(f"  FAIL  CDP check error: {exc}\n")
        out.write(f"{'─'*70}\n\n")
        logger.error("Preflight failed: %s", exc)
        return False

    # 3. Page availability - open about:blank if no page
    try:
        result = agent_browser("get", "url", check=False)
        if result.returncode != 0 or not result.stdout.strip():
            logger.info("No active page detected. Creating new tab via CDP...")
            import urllib.request
            cdp_url = f"http://127.0.0.1:{port}/json/new?about:blank"
            req = urllib.request.Request(cdp_url, method="PUT")
            try:
                urllib.request.urlopen(req, timeout=5)
                time.sleep(0.5)
            except Exception:
                pass
            result = agent_browser("get", "url", check=False)
            if result.returncode != 0:
                out.write("  FAIL  No page available (tried creating tab via CDP)\n")
                out.write(f"{'─'*70}\n\n")
                logger.error("Preflight failed: cannot open initial page")
                return False
            out.write("  PASS  Page: about:blank (auto-created)\n")
        else:
            url = result.stdout.strip()
            display_url = url if len(url) <= 50 else url[:47] + "..."
            out.write(f"  PASS  Page: {display_url}\n")
    except Exception as exc:
        out.write(f"  WARN  Page check skipped: {exc}\n")

    out.write(f"{'─'*70}\n\n")
    logger.info("Preflight check passed.")
    return True


def run_scenario(
    path: Path,
    dry_run: bool,
    continue_on_error: bool,
    retry_on_overlay: bool = True,
    url_wait_timeout_ms: int = 20000,
    click_fallback_enabled: bool = True,
    keep_browser_alive: bool = False,
    keep_alive_interval_sec: int = 8,
    keep_browser_open: bool = False,
    scenario_vars: dict[str, str] | None = None,
    base_url: str | None = None,
) -> int:
    logger = setup_logger("order-agent-exec")
    _self_heal_log.clear()

    if not _preflight_check(logger, dry_run=dry_run):
        return 1

    logger.info("Loading scenario: %s", path)
    commands = parse_scenario(path)
    if not commands:
        logger.warning("No commands to execute.")
        return 0

    logger.info("Total commands: %s", len(commands))
    last_order_sheet_id: str | None = None
    if LAST_ORDER_SHEET_FILE.exists():
        last_order_sheet_id = LAST_ORDER_SHEET_FILE.read_text(encoding="utf-8").strip() or None
    seen_order_sheet_ids: set[str] = set()
    baseline_order_detail_id: str | None = None

    stop_keep_alive = threading.Event()
    keep_alive_thread: threading.Thread | None = None
    if keep_browser_alive and not dry_run:
        def _keep_alive_loop() -> None:
            while not stop_keep_alive.is_set():
                try:
                    agent_browser("get", "url", check=False)
                except Exception:
                    pass
                stop_keep_alive.wait(max(2, keep_alive_interval_sec))

        keep_alive_thread = threading.Thread(target=_keep_alive_loop, name="order-agent-keepalive", daemon=True)
        keep_alive_thread.start()
        logger.info("Keep-alive mode enabled (interval=%ss).", keep_alive_interval_sec)

    failures = 0
    step_start_times: list[float] = []
    failed_steps: dict[int, str] = {}  # step_idx -> error message
    scenario_outputs: list[tuple[str, str]] = []
    expect_fail_pattern: str | None = None  # EXPECT_FAIL에서 설정, 다음 스텝에서 소비
    expect_fail_target_idx: int = -1  # EXPECT_FAIL이 적용될 스텝 인덱스
    scenario_start = time.time()
    try:
        _vars = {k.lower(): v for k, v in (scenario_vars or {}).items()}
        _default_base_url = "https://alpha.zigzag.kr"
        _base_url = (base_url or "").rstrip("/") if base_url else None
        if _base_url:
            logger.info("Base URL override: %s → %s", _default_base_url, _base_url)
        for idx, command in enumerate(commands, 1):
            step_start_times.append(time.time())
            # {{var}} 치환
            if _vars and any("{{" in a for a in command.args):
                import re as _re
                expanded = []
                for a in command.args:
                    expanded.append(_re.sub(r"\{\{(\w+)\}\}", lambda m: _vars.get(m.group(1).lower(), m.group(0)), a))
                command = ScenarioCommand(line_no=command.line_no, action=command.action, args=expanded)
            # base URL 치환
            if _base_url and any(_default_base_url in a for a in command.args):
                rewritten = [a.replace(_default_base_url, _base_url) for a in command.args]
                command = ScenarioCommand(line_no=command.line_no, action=command.action, args=rewritten)
            validate_command(command)

            # EXPECT_FAIL 미소비 체크: 타겟 스텝이 실패 없이 성공하면 EXPECT_FAIL 위반
            if expect_fail_pattern is not None and idx != expect_fail_target_idx:
                failures += 1
                failed_steps[expect_fail_target_idx] = f"EXPECT_FAIL violated: step succeeded but failure was expected (pattern='{expect_fail_pattern}')"
                logger.error("EXPECT_FAIL violated at step %s: expected failure did not occur (pattern='%s')",
                             expect_fail_target_idx, expect_fail_pattern)
                expect_fail_pattern = None
                if not continue_on_error:
                    break

            # EXPECT_FAIL: 다음 스텝의 기대 실패 패턴을 설정하고 자체는 즉시 PASS
            if command.action == "EXPECT_FAIL":
                expect_fail_pattern = command.args[0] if command.args else ""
                expect_fail_target_idx = idx + 1
                logger.info("[STEP %s/%s] line %s: EXPECT_FAIL %s",
                            idx, len(commands), command.line_no,
                            expect_fail_pattern or "(any error)")
                continue
            cli_args = [] if command.action in {
                "CHECK_URL",
                "CHECK_NOT_URL",
                "WAIT_URL",
                "DUMP_STATE",
                "CHECK_NEW_ORDER_SHEET",
                "SAVE_ORDER_DETAIL_ID",
                "CHECK_ORDER_DETAIL_ID_CHANGED",
                "SAVE_ORDER_NUMBER",
                "CHECK_ORDER_NUMBER_CHANGED",
                "ENSURE_LOGIN_ALPHA",
                "CLICK_SNAPSHOT_TEXT",
                "CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT",
                "SELECT_CART_ITEM_BY_TEXT",
                "CLICK_ORDER_DETAIL_BY_STATUS",
                "CLICK_ORDER_DETAIL_WITH_ACTION",
                "APPLY_ORDER_STATUS_FILTER",
                "SUBMIT_CANCEL_REQUEST",
                "SUBMIT_RETURN_REQUEST",
                "SUBMIT_EXCHANGE_REQUEST",
                "PRINT_ACTIVE_MODAL",
                "CHECK_PAYMENT_RESULT",
                "EXPECT_FAIL",
                "READ_OTP",
            } else to_agent_browser_args(command)
            logger.info("[STEP %s/%s] line %s: %s", idx, len(commands), command.line_no, " ".join([command.action, *command.args]))

            if dry_run:
                if command.action in {"CHECK_URL", "CHECK_NOT_URL", "WAIT_URL", "DUMP_STATE"}:
                    logger.info("[DRY-RUN] %s '%s'", command.action, command.args[0])
                elif command.action in {
                    "CHECK_NEW_ORDER_SHEET",
                    "SAVE_ORDER_DETAIL_ID",
                    "CHECK_ORDER_DETAIL_ID_CHANGED",
                    "SAVE_ORDER_NUMBER",
                    "CHECK_ORDER_NUMBER_CHANGED",
                    "PRINT_ACTIVE_MODAL",
                    "CHECK_PAYMENT_RESULT",
                }:
                    logger.info("[DRY-RUN] %s", command.action)
                elif command.action == "ENSURE_LOGIN_ALPHA":
                    logger.info("[DRY-RUN] ENSURE_LOGIN_ALPHA '%s'", command.args[0])
                elif command.action == "CLICK_SNAPSHOT_TEXT":
                    logger.info("[DRY-RUN] CLICK_SNAPSHOT_TEXT '%s'", command.args[0])
                elif command.action == "CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT":
                    logger.info("[DRY-RUN] CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT '%s'", command.args[0])
                elif command.action == "SELECT_CART_ITEM_BY_TEXT":
                    logger.info("[DRY-RUN] SELECT_CART_ITEM_BY_TEXT '%s'", command.args[0])
                elif command.action == "CLICK_ORDER_DETAIL_BY_STATUS":
                    logger.info("[DRY-RUN] CLICK_ORDER_DETAIL_BY_STATUS '%s'", command.args[0])
                elif command.action == "CLICK_ORDER_DETAIL_WITH_ACTION":
                    logger.info("[DRY-RUN] CLICK_ORDER_DETAIL_WITH_ACTION '%s'", command.args[0])
                elif command.action == "APPLY_ORDER_STATUS_FILTER":
                    logger.info("[DRY-RUN] APPLY_ORDER_STATUS_FILTER '%s'", command.args[0])
                elif command.action == "SUBMIT_CANCEL_REQUEST":
                    logger.info("[DRY-RUN] SUBMIT_CANCEL_REQUEST '%s'", command.args[0])
                elif command.action == "SUBMIT_RETURN_REQUEST":
                    logger.info("[DRY-RUN] SUBMIT_RETURN_REQUEST '%s'", command.args[0])
                elif command.action == "SUBMIT_EXCHANGE_REQUEST":
                    logger.info("[DRY-RUN] SUBMIT_EXCHANGE_REQUEST '%s'", command.args[0])
                elif command.action == "READ_OTP":
                    var_name = command.args[1] if len(command.args) > 1 else "otp"
                    logger.info("[DRY-RUN] READ_OTP '%s' -> {{%s}}", command.args[0], var_name)
                else:
                    logger.info("[DRY-RUN] agent-browser %s", " ".join(cli_args))
                continue

            try:
                if command.action == "READ_OTP":
                    from core.otp_reader import read_otp
                    account_name = command.args[0]
                    var_name = command.args[1] if len(command.args) > 1 else "otp"
                    otp_code = read_otp(account_name)
                    _vars[var_name.lower()] = otp_code
                    logger.info("READ_OTP: account='%s' -> {{%s}} = %s", account_name, var_name, otp_code)
                    continue

                if command.action != "ENSURE_LOGIN_ALPHA" and _page_has_upstream_error():
                    logger.warning("Detected upstream error before line %s. Trying in-place recovery.", command.line_no)
                    if not _recover_from_upstream_error(max_retries=3):
                        raise RuntimeError(
                            "ENV_UPSTREAM_UNHEALTHY: upstream error page persists after recovery retries"
                        )

                if command.action == "ENSURE_LOGIN_ALPHA":
                    target_url = command.args[0]
                    target_path = urllib.parse.urlparse(target_url).path or target_url
                    def _current_url() -> str:
                        return agent_browser("get", "url", check=True).stdout.strip()

                    def _is_login_url(url: str) -> bool:
                        return "/auth/login" in url or "/auth/email-login" in url

                    def _extract_redirect_from_url(url: str) -> str | None:
                        try:
                            parsed = urllib.parse.urlparse(url)
                            qs = urllib.parse.parse_qs(parsed.query)
                            vals = qs.get("redirect") or []
                            if not vals:
                                return None
                            value = vals[0].strip()
                            if not value:
                                return None
                            decoded = urllib.parse.unquote(value)
                            if decoded.startswith("http://") or decoded.startswith("https://"):
                                return decoded
                            return None
                        except Exception:
                            return None

                    _safe_open_url(target_url, retries=5)
                    time.sleep(1.0)
                    for _ in range(3):
                        if not _page_has_upstream_error():
                            break
                        logger.warning("Detected upstream error page. Retrying target open.")
                        _safe_open_url(target_url, retries=5)
                        time.sleep(1.0)
                    if _page_has_upstream_error():
                        raise RuntimeError(
                            "ENV_UPSTREAM_UNHEALTHY: 'no healthy upstream' persisted on target page"
                        )
                    current_url = _current_url()
                    if _is_login_url(current_url):
                        if _page_has_already_logged_in_notice():
                            redirect_url = _extract_redirect_from_url(current_url) or _extract_redirect_from_url(target_url)
                            if redirect_url:
                                _safe_open_url(redirect_url, retries=5)
                                time.sleep(0.8)
                                current_url = _current_url()
                                logger.info("Already-logged-in notice handled. Redirected to: %s", current_url)
                            if not _is_login_url(current_url):
                                logger.info("ENSURE_LOGIN_ALPHA passed via already-logged-in notice: %s", current_url)
                                continue

                        logger.warning("Login required. Running alpha re-login flow.")
                        login_url = "https://alpha.zigzag.kr/auth/email-login" f"?redirect={target_url}"
                        _safe_open_url(login_url, retries=5)
                        time.sleep(0.8)

                        # 로그인 페이지를 벗어나지 않고 동일 화면에서 1~2회만 시도
                        alpha_user = os.environ.get("ALPHA_USERNAME")
                        alpha_pass = os.environ.get("ALPHA_PASSWORD")
                        if not alpha_user or not alpha_pass:
                            raise RuntimeError(
                                "ENSURE_LOGIN_ALPHA failed: ALPHA_USERNAME / ALPHA_PASSWORD 환경변수가 설정되지 않았습니다. "
                                ".env.example을 참고하여 .env 파일을 생성하세요."
                            )

                        login_ok = False
                        for attempt in range(1, 3):
                            agent_browser("fill", "[placeholder*='abc@email.com']", alpha_user, check=True)
                            agent_browser("fill", "[placeholder*='영문, 숫자, 특수문자 포함 8자 이상']", alpha_pass, check=True)
                            login_clicked = False
                            login_btn = agent_browser("find", "role", "button", "click", "--name", "로그인", check=False)
                            if login_btn.returncode == 0:
                                login_clicked = True
                            else:
                                login_fallback = agent_browser("click", "text=로그인", check=False)
                                login_clicked = login_fallback.returncode == 0
                            if not login_clicked:
                                raise RuntimeError("ENSURE_LOGIN_ALPHA failed: unable to click login button")

                            time.sleep(2.2)
                            current_url = _current_url()
                            if "/auth/error" in current_url and "type=login" in current_url:
                                raise RuntimeError(
                                    "ENSURE_LOGIN_ALPHA failed: login blocked by auth/error. "
                                    "Manual login is required in this environment."
                                )
                            if not _is_login_url(current_url):
                                login_ok = True
                                break
                            logger.warning("Login attempt %s did not finish. Retrying once.", attempt)

                        if not login_ok:
                            raise RuntimeError("ENSURE_LOGIN_ALPHA failed: still on login page after retry")

                        # 로그인 성공 후 target으로 1회 이동
                        if target_url not in current_url:
                            _safe_open_url(target_url, retries=5)
                            time.sleep(0.8)
                            current_url = _current_url()
                        if target_path not in current_url:
                            for _ in range(2):
                                _safe_open_url(target_url, retries=5)
                                time.sleep(0.8)
                                current_url = _current_url()
                                if target_path in current_url:
                                    break
                        logger.info("ENSURE_LOGIN_ALPHA passed after re-login: %s", current_url)
                    else:
                        if target_path not in current_url:
                            for _ in range(3):
                                _safe_open_url(target_url, retries=5)
                                time.sleep(0.8)
                                current_url = _current_url()
                                if target_path in current_url:
                                    break
                        logger.info("ENSURE_LOGIN_ALPHA passed (already logged in): %s", current_url)
                    continue

                if command.action == "CLICK_SNAPSHOT_TEXT":
                    label, ref = _click_by_snapshot_text(command.args[0], retry_on_overlay=retry_on_overlay)
                    logger.info("CLICK_SNAPSHOT_TEXT matched '%s' via @%s", label, ref)
                    continue

                if command.action == "CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT":
                    label, checkbox_ref, target_ref = _click_prev_checkbox_for_snapshot_text(command.args[0])
                    logger.info(
                        "CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT clicked @%s before target @%s ('%s')",
                        checkbox_ref,
                        target_ref,
                        label,
                    )
                    continue

                if command.action == "SELECT_CART_ITEM_BY_TEXT":
                    label, ref, selected_count = _select_cart_item_by_text(command.args[0])
                    logger.info(
                        "SELECT_CART_ITEM_BY_TEXT clicked @%s ('%s'), selected_count=%s",
                        ref,
                        label,
                        selected_count,
                    )
                    if selected_count is not None and selected_count < 1:
                        raise RuntimeError(
                            "SELECT_CART_ITEM_BY_TEXT failed: cart selected count is 0 after click"
                        )
                    continue

                if command.action == "CLICK_ORDER_DETAIL_BY_STATUS":
                    output = _click_order_detail_by_status(command.args[0])
                    logger.info("CLICK_ORDER_DETAIL_BY_STATUS result: %s", output)
                    continue

                if command.action == "CLICK_ORDER_DETAIL_WITH_ACTION":
                    result_url = _click_order_detail_with_action(command.args[0])
                    if result_url is None:
                        logger.warning(
                            "CLICK_ORDER_DETAIL_WITH_ACTION: '%s' 액션 가능 주문 없음 — 시나리오 조기 종료 (SKIP)",
                            command.args[0],
                        )
                        print(f"\n[SKIP] '{command.args[0]}' 액션 가능한 주문을 찾지 못했습니다 (최대 3건 탐색). 시나리오를 종료합니다.")
                        return 0
                    current_url = result_url
                    logger.info("CLICK_ORDER_DETAIL_WITH_ACTION picked: %s", current_url)
                    continue

                if command.action == "APPLY_ORDER_STATUS_FILTER":
                    current_url = _apply_order_status_filter(command.args[0])
                    logger.info("APPLY_ORDER_STATUS_FILTER applied: %s", current_url)
                    continue

                if command.action == "SUBMIT_CANCEL_REQUEST":
                    current_url = _submit_cancel_request(command.args[0])
                    logger.info("SUBMIT_CANCEL_REQUEST finished: %s", current_url)
                    pass  # 최종 URL로 대체
                    continue

                if command.action == "SUBMIT_RETURN_REQUEST":
                    current_url = _submit_return_request(command.args[0])
                    logger.info("SUBMIT_RETURN_REQUEST finished: %s", current_url)
                    pass  # 최종 URL로 대체
                    continue

                if command.action == "SUBMIT_EXCHANGE_REQUEST":
                    current_url = _submit_exchange_request(command.args[0])
                    logger.info("SUBMIT_EXCHANGE_REQUEST finished: %s", current_url)
                    pass  # 최종 URL로 대체
                    continue

                if command.action == "PRINT_ACTIVE_MODAL":
                    payload = _collect_active_modal_info()
                    logger.info("PRINT_ACTIVE_MODAL: %s", json.dumps(payload, ensure_ascii=False))
                    continue

                if command.action == "CHECK_PAYMENT_RESULT":
                    deadline = time.time() + 45.0
                    saw_payment_request = False
                    while time.time() < deadline:
                        current_url = agent_browser("get", "url", check=True).stdout.strip()
                        if "/checkout/order-completed/" in current_url:
                            logger.info("CHECK_PAYMENT_RESULT passed: %s", current_url)
                            pass  # 결제 결과 URL은 최종 URL로 대체
                            break
                        if "/api/payment/v1/request/" in current_url:
                            saw_payment_request = True
                            time.sleep(0.6)
                            continue
                        if "/checkout/order-sheets/" in current_url:
                            time.sleep(0.6)
                            continue
                        time.sleep(0.4)
                    else:
                        current_url = agent_browser("get", "url", check=True).stdout.strip()
                        payload = _collect_active_modal_info()
                        evidence = _collect_order_sheet_evidence()
                        has_modal = bool(payload.get("hasModal"))
                        alerts = payload.get("alerts") or []
                        hints = payload.get("hints") or []
                        hint = (hints[0] if hints else "")[:220]
                        msgs = evidence.get("messageCandidates") or []
                        msg = (msgs[0] if msgs else "")[:260]
                        submit_ui_msg = str(evidence.get("submitUiMessage") or "")[:260]
                        logger.error("CHECK_PAYMENT_RESULT evidence: %s", json.dumps(evidence, ensure_ascii=False))
                        if "/checkout/order-sheets/" in current_url:
                            raise RuntimeError(
                                "CHECK_PAYMENT_RESULT failed [STAYED_ON_ORDER_SHEET]: stayed on order-sheet; "
                                f"hasModal={has_modal}; alerts={len(alerts)}; hint='{hint}'; "
                                f"payButton='{evidence.get('payButtonText')}'; agreeChecked={evidence.get('agreeChecked')}; "
                                f"zeroPayVisible={evidence.get('zeroPayVisible')}; pointInputValue='{evidence.get('pointInputValue')}'; "
                                f"message='{msg}'; submitUiMessage='{submit_ui_msg}'"
                            )
                        if saw_payment_request and "/api/payment/v1/request/" in current_url:
                            raise RuntimeError(
                                "CHECK_PAYMENT_RESULT failed [PAYMENT_REQUEST_STUCK]: payment request url did not redirect; "
                                f"url='{current_url}'; hasModal={has_modal}; alerts={len(alerts)}; submitUiMessage='{submit_ui_msg}'"
                            )
                        raise RuntimeError(
                            "CHECK_PAYMENT_RESULT failed [NO_COMPLETION_REDIRECT]: no completion redirect; "
                            f"url='{current_url}'; hasModal={has_modal}; alerts={len(alerts)}; "
                            f"payButton='{evidence.get('payButtonText')}'; submitUiMessage='{submit_ui_msg}'"
                        )
                    continue

                if command.action == "CHECK_NEW_ORDER_SHEET":
                    current_url = agent_browser("get", "url", check=True).stdout.strip()
                    order_sheet_id = _extract_order_sheet_id(current_url)
                    if not order_sheet_id:
                        raise RuntimeError(f"CHECK_NEW_ORDER_SHEET failed: not an order-sheet url ({current_url})")
                    if order_sheet_id in seen_order_sheet_ids:
                        raise RuntimeError(f"CHECK_NEW_ORDER_SHEET failed: duplicated in current run ({order_sheet_id})")
                    if last_order_sheet_id and order_sheet_id == last_order_sheet_id:
                        raise RuntimeError(f"CHECK_NEW_ORDER_SHEET failed: reused previous order-sheet id ({order_sheet_id})")
                    seen_order_sheet_ids.add(order_sheet_id)
                    LAST_ORDER_SHEET_FILE.parent.mkdir(parents=True, exist_ok=True)
                    LAST_ORDER_SHEET_FILE.write_text(order_sheet_id, encoding="utf-8")
                    logger.info("CHECK_NEW_ORDER_SHEET passed: %s", order_sheet_id)
                    pass  # 주문서 ID는 리포트에 포함하지 않음
                    continue

                if command.action in {"SAVE_ORDER_DETAIL_ID", "SAVE_ORDER_NUMBER"}:
                    action_name = command.action
                    current_url = agent_browser("get", "url", check=True).stdout.strip()
                    order_detail_id = _extract_order_detail_id(current_url)
                    if not order_detail_id:
                        raise RuntimeError(f"{action_name} failed: not an order-detail url ({current_url})")
                    baseline_order_detail_id = order_detail_id
                    logger.info("%s saved: %s", action_name, baseline_order_detail_id)
                    continue

                if command.action in {"CHECK_ORDER_DETAIL_ID_CHANGED", "CHECK_ORDER_NUMBER_CHANGED"}:
                    action_name = command.action
                    if not baseline_order_detail_id:
                        raise RuntimeError(f"{action_name} failed: baseline is not set")
                    current_url = agent_browser("get", "url", check=True).stdout.strip()
                    order_detail_id = _extract_order_detail_id(current_url)
                    if not order_detail_id:
                        raise RuntimeError(f"{action_name} failed: not an order-detail url ({current_url})")
                    if order_detail_id == baseline_order_detail_id:
                        raise RuntimeError(
                            f"{action_name} failed: "
                            f"order detail id did not change ({order_detail_id})"
                        )
                    logger.info(
                        "%s passed: baseline=%s current=%s",
                        action_name,
                        baseline_order_detail_id,
                        order_detail_id,
                    )
                    label = "주문번호" if "NUMBER" in action_name else "주문상세 ID"
                    scenario_outputs.append((label, order_detail_id))
                    continue

                if command.action == "CHECK_URL":
                    current_url = agent_browser("get", "url", check=True).stdout.strip()
                    expected = command.args[0]
                    if expected not in current_url:
                        raise RuntimeError(f"CHECK_URL failed: expected '{expected}' in '{current_url}'")
                    logger.info("CHECK_URL passed: %s", current_url)
                    continue

                if command.action == "CHECK_NOT_URL":
                    current_url = agent_browser("get", "url", check=True).stdout.strip()
                    blocked = command.args[0]
                    if blocked in current_url:
                        raise RuntimeError(f"CHECK_NOT_URL failed: blocked '{blocked}' still in '{current_url}'")
                    logger.info("CHECK_NOT_URL passed: %s", current_url)
                    continue

                if command.action == "WAIT_URL":
                    expected = command.args[0]
                    deadline = time.time() + (url_wait_timeout_ms / 1000)
                    while time.time() < deadline:
                        current_url = agent_browser("get", "url", check=True).stdout.strip()
                        if expected in current_url:
                            logger.info("WAIT_URL passed: %s", current_url)
                            break
                        time.sleep(0.5)
                    else:
                        raise RuntimeError(f"WAIT_URL timeout: expected '{expected}'")
                    continue

                if command.action == "DUMP_STATE":
                    tag = command.args[0]
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    base = REPO_ROOT / "logs" / f"diag_{tag}_{ts}"
                    snapshot = agent_browser("snapshot", "-i", check=False)
                    errors = agent_browser("errors", check=False)
                    console = agent_browser("console", check=False)
                    url_out = agent_browser("get", "url", check=False)
                    title_out = agent_browser("get", "title", check=False)
                    screenshot_out = agent_browser("screenshot", f"{base}.png", check=False)
                    with open(f"{base}.txt", "w", encoding="utf-8") as f:
                        f.write("=== URL ===\n")
                        f.write(url_out.stdout or "")
                        f.write("\n=== TITLE ===\n")
                        f.write(title_out.stdout or "")
                        f.write("\n=== SNAPSHOT(-i) ===\n")
                        f.write(snapshot.stdout or "")
                        f.write("\n=== ERRORS ===\n")
                        f.write(errors.stdout or "")
                        f.write("\n=== CONSOLE ===\n")
                        f.write(console.stdout or "")
                    logger.info("DUMP_STATE saved: %s.txt", base)
                    if screenshot_out.returncode == 0:
                        logger.info("DUMP_STATE screenshot saved: %s.png", base)
                    continue

                if command.action == "CHECK" and command.args[0].startswith("text="):
                    selector = normalize_selector(command.args[0])
                    count_out = agent_browser("get", "count", selector, check=True)
                    count_val = int((count_out.stdout or "0").strip() or "0")
                    if count_val < 1:
                        raise RuntimeError(f"CHECK failed: selector '{selector}' count=0")
                    logger.info("CHECK passed by count: %s (count=%s)", selector, count_val)
                    continue

                if command.action == "NAVIGATE":
                    _safe_open_url(command.args[0], retries=5)
                    result = agent_browser("get", "url", check=False)
                elif command.action == "FILL":
                    _cdp_direct_fill(normalize_selector(command.args[0]), " ".join(command.args[1:]))
                    result = type(agent_browser("get", "url", check=False))(
                        args=cli_args, returncode=0, stdout="filled", stderr=""
                    )
                else:
                    result = agent_browser(*cli_args, check=True)
                eval_output = result.stdout.strip()
                if eval_output:
                    logger.debug("stdout: %s", eval_output)
                if result.stderr.strip():
                    logger.debug("stderr: %s", result.stderr.strip())

                # EVAL 결과가 CLAIM_NOT_AVAILABLE: 이면 클레임 불가 — 사유 리포트 후 시나리오 종결
                if command.action == "EVAL" and "CLAIM_NOT_AVAILABLE:" in eval_output:
                    reason = eval_output.split("CLAIM_NOT_AVAILABLE:", 1)[1].strip().strip('"')
                    logger.warning("클레임 불가 감지 — 사유: %s", reason)
                    print(f"\n[CLAIM_NOT_AVAILABLE] 해당 주문은 클레임 처리가 불가합니다.")
                    print(f"  사유: {reason}")
                    print(f"  URL: {agent_browser('get', 'url', check=False).stdout.strip()}")
                    return 0

            except AgentBrowserError as exc:
                retried = False
                text_fallback_retried = False
                role_button_fallback_retried = False

                if retry_on_overlay and "blocked by another element" in (exc.stderr or "").lower():
                    retried = True
                    logger.warning("Overlay blockage detected at line %s. Retrying with ESC.", command.line_no)
                    agent_browser("press", "Escape", check=False)
                    try:
                        result = agent_browser(*cli_args, check=True)
                        if result.stdout.strip():
                            logger.debug("stdout: %s", result.stdout.strip())
                        if result.stderr.strip():
                            logger.debug("stderr: %s", result.stderr.strip())
                        logger.info("Retry succeeded at line %s", command.line_no)
                        continue
                    except AgentBrowserError as retry_exc:
                        exc = retry_exc

                if command.action == "CLICK" and click_fallback_enabled:
                    fallback_args = _text_fallback_click_args(command.args[0])
                    if fallback_args:
                        text_value = command.args[0][len("text="):].strip()
                        if not _text_exists_fast(text_value):
                            logger.warning("Skip text fallback at line %s: text not found quickly.", command.line_no)
                            fallback_args = None
                    if fallback_args:
                        text_fallback_retried = True
                        logger.warning("Primary CLICK failed at line %s. Retrying via text locator fallback.", command.line_no)
                        try:
                            result = agent_browser(*fallback_args, check=True)
                            if result.stdout.strip():
                                logger.debug("stdout: %s", result.stdout.strip())
                            if result.stderr.strip():
                                logger.debug("stderr: %s", result.stderr.strip())
                            logger.info("Text fallback click succeeded at line %s", command.line_no)
                            continue
                        except AgentBrowserError as retry_exc:
                            exc = retry_exc

                    role_fallback_args = _role_button_fallback_click_args(command.args[0])
                    if role_fallback_args:
                        text_value = command.args[0][len("text="):].strip()
                        if not _text_exists_fast(text_value):
                            logger.warning("Skip role fallback at line %s: text not found quickly.", command.line_no)
                            role_fallback_args = None
                    if role_fallback_args:
                        role_button_fallback_retried = True
                        logger.warning("Text locator fallback failed at line %s. Retrying via role=button fallback.", command.line_no)
                        try:
                            result = agent_browser(*role_fallback_args, check=True)
                            if result.stdout.strip():
                                logger.debug("stdout: %s", result.stdout.strip())
                            if result.stderr.strip():
                                logger.debug("stderr: %s", result.stderr.strip())
                            logger.info("Role button fallback click succeeded at line %s", command.line_no)
                            continue
                        except AgentBrowserError as retry_exc:
                            exc = retry_exc

                _ab_err_msg = (exc.stderr or exc.stdout or "").strip()[:120]
                # EXPECT_FAIL: 기대된 실패면 PASS 처리
                if expect_fail_pattern is not None:
                    if expect_fail_pattern == "" or expect_fail_pattern in _ab_err_msg:
                        logger.info("EXPECT_FAIL matched at line %s: %s", command.line_no, _ab_err_msg[:80])
                        expect_fail_pattern = None
                        continue
                    else:
                        logger.error("EXPECT_FAIL mismatch at line %s: expected '%s' but got: %s",
                                     command.line_no, expect_fail_pattern, _ab_err_msg[:80])
                    expect_fail_pattern = None

                failures += 1
                failed_steps[idx] = _ab_err_msg or f"agent-browser exit code {exc.returncode}"
                logger.error("agent-browser command failed at line %s", command.line_no)
                logger.error("command: %s", " ".join(exc.cmd))
                if exc.stdout.strip():
                    logger.error("stdout: %s", exc.stdout.strip())
                if exc.stderr.strip():
                    logger.error("stderr: %s", exc.stderr.strip())
                if retried:
                    logger.error("Retry after ESC also failed at line %s", command.line_no)
                if text_fallback_retried:
                    logger.error("Text locator fallback also failed at line %s", command.line_no)
                if role_button_fallback_retried:
                    logger.error("Role button fallback also failed at line %s", command.line_no)
                logger.error("Failure modal context: %s", _failure_modal_summary())
                submit_ui_line = _collect_modal_guidance_line()
                logger.error("Submit UI message: %s", submit_ui_line)
                _print_cli_modal_guidance_message(submit_ui_line)

                fail_shot = REPO_ROOT / "logs" / f"failed_line_{command.line_no}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                shot_result = agent_browser("screenshot", str(fail_shot), check=False)
                if shot_result.returncode == 0:
                    logger.error("Failure screenshot saved: %s", fail_shot)

                if not continue_on_error:
                    break

            except RuntimeError as exc:
                _rt_err_msg = str(exc)[:120]
                # EXPECT_FAIL: 기대된 실패면 PASS 처리
                if expect_fail_pattern is not None:
                    if expect_fail_pattern == "" or expect_fail_pattern in _rt_err_msg:
                        logger.info("EXPECT_FAIL matched at line %s: %s", command.line_no, _rt_err_msg[:80])
                        expect_fail_pattern = None
                        continue
                    else:
                        logger.error("EXPECT_FAIL mismatch at line %s: expected '%s' but got: %s",
                                     command.line_no, expect_fail_pattern, _rt_err_msg[:80])
                    expect_fail_pattern = None

                failures += 1
                failed_steps[idx] = _rt_err_msg
                logger.error("Runtime command failed at line %s: %s", command.line_no, exc)
                logger.error("Failure modal context: %s", _failure_modal_summary())
                submit_ui_line = _collect_modal_guidance_line()
                logger.error("Submit UI message: %s", submit_ui_line)
                _print_cli_modal_guidance_message(submit_ui_line)
                if not continue_on_error:
                    break

    finally:
        if keep_browser_open and keep_alive_thread is not None:
            logger.info("Keep-browser-open mode enabled. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                logger.info("Keep-browser-open mode stopped by user.")
        if keep_alive_thread is not None:
            stop_keep_alive.set()
            keep_alive_thread.join(timeout=1.5)

    scenario_end = time.time()

    if not dry_run:
        try:
            final_url = agent_browser("get", "url", check=False).stdout.strip()
            if final_url:
                scenario_outputs.append(("최종 URL", final_url))
        except Exception:
            pass

    step_results: list[_StepResult] = []
    executed_count = len(step_start_times)
    for i, cmd in enumerate(commands):
        idx = i + 1
        skipped = i >= executed_count
        start = step_start_times[i] if not skipped else scenario_end
        end = step_start_times[i + 1] if i + 1 < executed_count else scenario_end
        step_results.append(_StepResult(
            step=idx,
            line_no=cmd.line_no,
            action=cmd.action,
            summary=_action_summary(cmd.action, cmd.args),
            ok=False if skipped else (idx not in failed_steps),
            elapsed_ms=0.0 if skipped else (end - start) * 1000,
            error="SKIP (not executed)" if skipped else failed_steps.get(idx, ""),
        ))
    _print_report(path.name, step_results, (scenario_end - scenario_start) * 1000, dry_run, scenario_outputs)

    if failures:
        logger.error("Scenario execution finished with %s failure(s).", failures)
        return 1
    logger.info("Scenario execution complete.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute .scn file via agent-browser")
    parser.add_argument(
        "scenario",
        nargs="*",
        default=[str(DEFAULT_SCENARIO)],
        help="Path(s) to scenario file(s) (.scn). Multiple files are executed sequentially.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print commands without calling agent-browser",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue execution after command failures",
    )
    parser.add_argument(
        "--no-retry-on-overlay",
        action="store_true",
        help="Disable automatic ESC+retry when click is blocked by overlay",
    )
    parser.add_argument(
        "--url-wait-timeout-ms",
        type=int,
        default=20000,
        help="Timeout for WAIT_URL action",
    )
    parser.add_argument(
        "--disable-click-fallback",
        action="store_true",
        help="Disable text/role fallback retries when CLICK fails",
    )
    parser.add_argument(
        "--fast-mode",
        action="store_true",
        help="Favor quick failure: timeout=12000ms and disable click fallback",
    )
    parser.add_argument(
        "--keep-browser-alive",
        action="store_true",
        help="Run a background keep-alive ping while scenario is executing",
    )
    parser.add_argument(
        "--keep-alive-interval-sec",
        type=int,
        default=8,
        help="Keep-alive ping interval (seconds)",
    )
    parser.add_argument(
        "--keep-browser-open",
        action="store_true",
        help="Keep browser session alive after scenario completes until Ctrl+C",
    )
    parser.add_argument(
        "--stop-on-scenario-fail",
        action="store_true",
        help="Stop executing remaining scenarios if one fails (multi-scenario mode)",
    )
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Set scenario variable (e.g. --var order_number=12345). Use {{KEY}} in .scn files.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        metavar="URL",
        help="Override base URL (default: https://alpha.zigzag.kr). All scenario URLs are rewritten.",
    )
    return parser.parse_args()


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # python-dotenv 미설치 시 환경변수 직접 설정 필요

    args = parse_args()
    scenario_paths: list[Path] = []
    for s in args.scenario:
        p = Path(s).expanduser().resolve()
        if not p.exists():
            print(f"[ERROR] Scenario file not found: {p}", file=sys.stderr)
            raise SystemExit(2)
        scenario_paths.append(p)

    effective_timeout = args.url_wait_timeout_ms
    click_fallback_enabled = not args.disable_click_fallback
    if args.fast_mode:
        effective_timeout = min(effective_timeout, 12000)
        click_fallback_enabled = False
    keep_alive_interval_sec = max(2, args.keep_alive_interval_sec)
    keep_browser_alive = args.keep_browser_alive or args.keep_browser_open

    # --var KEY=VALUE 파싱
    scenario_vars: dict[str, str] = {}
    for var_expr in args.var:
        if "=" not in var_expr:
            print(f"[ERROR] Invalid --var format: {var_expr!r} (expected KEY=VALUE)", file=sys.stderr)
            raise SystemExit(2)
        k, v = var_expr.split("=", 1)
        scenario_vars[k.strip()] = v.strip()

    total = len(scenario_paths)
    overall_exit_code = 0
    for seq, scenario_path in enumerate(scenario_paths, 1):
        if total > 1:
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"[SCENARIO {seq}/{total}] {scenario_path.name}", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)

        exit_code = run_scenario(
            path=scenario_path,
            dry_run=args.dry_run,
            continue_on_error=args.continue_on_error,
            retry_on_overlay=not args.no_retry_on_overlay,
            url_wait_timeout_ms=effective_timeout,
            click_fallback_enabled=click_fallback_enabled,
            keep_browser_alive=keep_browser_alive,
            keep_alive_interval_sec=keep_alive_interval_sec,
            keep_browser_open=args.keep_browser_open if seq == total else False,
            scenario_vars=scenario_vars or None,
            base_url=args.base_url,
        )
        if exit_code != 0:
            overall_exit_code = 1
            if args.stop_on_scenario_fail:
                print(f"[STOPPED] Scenario failed: {scenario_path.name} ({seq}/{total})", file=sys.stderr)
                break

    if total > 1:
        passed = total if overall_exit_code == 0 else seq - (1 if exit_code != 0 and args.stop_on_scenario_fail else 0)
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[SUMMARY] {passed}/{total} scenarios passed", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

    raise SystemExit(overall_exit_code)


if __name__ == "__main__":
    main()
