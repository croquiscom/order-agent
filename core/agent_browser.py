#!/usr/bin/env python3
"""agent-browser: CDP 직접 구현 기반 브라우저 자동화.

Chrome DevTools Protocol을 직접 사용하여 실제 Chrome을 제어한다.
Playwright 없이 websocket-client + urllib 만으로 동작.

Usage:
    python3 -m core.agent_browser open https://www.naver.com
    python3 -m core.agent_browser click @query
    python3 -m core.agent_browser fill @query "검색어"
    python3 -m core.agent_browser press Enter
    python3 -m core.agent_browser screenshot output.png
    python3 -m core.agent_browser close
"""

from __future__ import annotations

import base64
import json
import socket
import subprocess
import sys
import time
import urllib.request
import os
import shlex
from pathlib import Path
from typing import Any, Optional

import websocket

DEFAULT_CDP_PORT = 9222
DEFAULT_TIMEOUT = 15  # seconds


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default

# JavaScript: 여러 전략으로 요소를 찾아 반환
JS_FIND_ELEMENT = """
(function(hint) {
    const strategies = [
        () => document.getElementById(hint),
        () => document.querySelector(`[name='${hint}']`),
        () => document.querySelector(`[placeholder*='${hint}']`),
        () => document.querySelector(`[aria-label*='${hint}']`),
        () => document.querySelector(`[class*='${hint}']`),
        () => {
            const els = document.querySelectorAll('*');
            for (const el of els) {
                if (el.textContent.trim() === hint) return el;
            }
            return null;
        },
    ];
    for (const fn of strategies) {
        const el = fn();
        if (el) return el;
    }
    return null;
})('%s')
"""

JS_CLICK = """
(function(hint) {
    const el = %s;
    if (!el) throw new Error('Element not found: ' + hint);
    el.scrollIntoView({block: 'center'});
    el.click();
    return 'clicked';
})('%s')
"""

JS_FILL = """
(function(hint, value) {
    const findEl = %s;
    const el = findEl;
    if (!el) throw new Error('Element not found: ' + hint);
    el.scrollIntoView({block: 'center'});
    el.focus();
    el.value = '';
    // 네이티브 input 이벤트 발생
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
    ).set;
    nativeInputValueSetter.call(el, value);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    return 'filled';
})('%s', '%s')
"""

JS_CHECK_VISIBLE = """
(function(hint) {
    const el = %s;
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
})('%s')
"""


def _make_find_js(hint: str) -> str:
    """find element JS 코드 생성."""
    return JS_FIND_ELEMENT % hint


class AgentBrowser:
    """CDP 직접 구현 브라우저 컨트롤러."""

    def __init__(self, mode: str = "launch"):
        self._mode = mode
        self._chrome_proc: Optional[subprocess.Popen] = None
        self._ws: Optional[websocket.WebSocket] = None
        self._msg_id = 0
        self._owns_browser = False
        self._cdp_port = _env_int("ORDER_AGENT_CDP_PORT", DEFAULT_CDP_PORT)
        self._cdp_http = f"http://localhost:{self._cdp_port}"
        self._attach_only = _env_flag("ORDER_AGENT_BROWSER_ATTACH_ONLY", default=False)
        self._headless = _env_flag("ORDER_AGENT_BROWSER_HEADLESS", default=False)
        self._no_sandbox = _env_flag("ORDER_AGENT_BROWSER_NO_SANDBOX", default=False)
        self._user_data_dir = os.getenv(
            "ORDER_AGENT_BROWSER_PROFILE_DIR",
            str(Path.home() / ".order-agent" / "browser" / "agent-browser-profile"),
        )
        extra_args_raw = os.getenv("ORDER_AGENT_BROWSER_EXTRA_ARGS", "")
        self._extra_args = shlex.split(extra_args_raw) if extra_args_raw.strip() else []

    def launch(self) -> None:
        if self._mode == "launch":
            if self._is_cdp_ready():
                self._owns_browser = False
            else:
                if self._attach_only:
                    raise RuntimeError(
                        f"CDP endpoint not ready on port {self._cdp_port} and attach-only mode is enabled"
                    )
                self._start_chrome()
                self._owns_browser = True
        elif self._mode == "cdp":
            if not self._is_cdp_ready():
                if self._attach_only:
                    raise RuntimeError(
                        f"CDP endpoint not ready on port {self._cdp_port} and attach-only mode is enabled"
                    )
                self._start_chrome()
                self._owns_browser = True

        self._connect_ws()

    def _start_chrome(self) -> None:
        explicit_bin = os.getenv("AGENT_BROWSER_EXECUTABLE_PATH", "").strip()
        chrome_paths = [
            explicit_bin,
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ]
        chrome_bin = None
        for p in chrome_paths:
            if p and Path(p).exists():
                chrome_bin = p
                break

        if not chrome_bin:
            raise RuntimeError("Chrome not found")

        Path(self._user_data_dir).mkdir(parents=True, exist_ok=True)

        launch_args = [
            chrome_bin,
            f"--remote-debugging-port={self._cdp_port}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={self._user_data_dir}",
        ]
        if _env_flag("ORDER_AGENT_BROWSER_DISABLE_EXTENSIONS", default=False):
            launch_args.extend(
                [
                    "--disable-extensions",
                    "--disable-component-extensions-with-background-pages",
                    "--disable-background-networking",
                ]
            )
        if self._headless:
            launch_args.extend(["--headless=new", "--disable-gpu"])
        if self._no_sandbox:
            launch_args.extend(["--no-sandbox", "--disable-setuid-sandbox"])
        if self._extra_args:
            launch_args.extend(self._extra_args)

        self._chrome_proc = subprocess.Popen(
            launch_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Chrome 시작 대기
        for _ in range(15):
            time.sleep(1)
            if self._is_cdp_ready():
                return
        raise RuntimeError(f"Chrome failed to start on port {self._cdp_port}")

    def _is_cdp_ready(self) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(("localhost", self._cdp_port))
            sock.close()
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False

    def _connect_ws(self) -> None:
        """CDP WebSocket 엔드포인트에 연결."""
        # /json 에서 페이지 목록 가져오기
        for _ in range(5):
            try:
                resp = urllib.request.urlopen(f"{self._cdp_http}/json", timeout=5)
                pages = json.loads(resp.read().decode())
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("Cannot fetch CDP page list")

        # page 타입 찾기
        ws_url = None
        for page in pages:
            if page.get("type") == "page":
                ws_url = page["webSocketDebuggerUrl"]
                break

        if not ws_url:
            # 페이지가 없으면 새 탭 생성
            resp = urllib.request.urlopen(f"{self._cdp_http}/json/new", timeout=5)
            new_page = json.loads(resp.read().decode())
            ws_url = new_page["webSocketDebuggerUrl"]

        self._ws = websocket.create_connection(ws_url, timeout=DEFAULT_TIMEOUT)
        # Page 도메인 활성화
        self._send("Page.enable")
        self._send("Runtime.enable")

    def _send(self, method: str, params: Optional[dict] = None) -> dict:
        """CDP 명령 전송 후 응답 대기."""
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method}
        if params:
            msg["params"] = params

        self._ws.send(json.dumps(msg))

        # 응답 대기 (이벤트 무시하고 매칭 id 찾기)
        deadline = time.time() + DEFAULT_TIMEOUT
        while time.time() < deadline:
            raw = self._ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == self._msg_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})
        raise TimeoutError(f"CDP timeout waiting for response to {method}")

    def _wait_for_event(self, event_name: str, timeout: float = None) -> dict:
        """특정 CDP 이벤트 대기."""
        t = timeout or DEFAULT_TIMEOUT
        deadline = time.time() + t
        while time.time() < deadline:
            self._ws.settimeout(max(0.1, deadline - time.time()))
            try:
                raw = self._ws.recv()
                msg = json.loads(raw)
                if msg.get("method") == event_name:
                    return msg.get("params", {})
            except websocket.WebSocketTimeoutException:
                continue
        raise TimeoutError(f"Timeout waiting for event {event_name}")

    def _evaluate(self, expression: str) -> Any:
        """JavaScript 실행 후 결과 반환."""
        result = self._send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        if result.get("exceptionDetails"):
            desc = result["exceptionDetails"].get("text", "JS error")
            raise RuntimeError(f"JS error: {desc}")
        return result.get("result", {}).get("value")

    def _wait_for_element(self, hint: str, timeout: float = None) -> bool:
        """요소가 보일 때까지 폴링."""
        t = timeout or DEFAULT_TIMEOUT
        find_js = _make_find_js(hint)
        check_js = JS_CHECK_VISIBLE % (find_js, hint)
        deadline = time.time() + t
        while time.time() < deadline:
            try:
                visible = self._evaluate(check_js)
                if visible:
                    return True
            except RuntimeError:
                pass
            time.sleep(0.5)
        raise TimeoutError(f"Element not visible within {t}s: {hint}")

    # --- Public API (기존 인터페이스 유지) ---

    @property
    def page(self):
        """호환성을 위한 프로퍼티. CDP에서는 self 반환."""
        return self

    def open(self, url: str) -> None:
        self._send("Page.navigate", {"url": url})
        # 페이지 로드 완료 대기
        self._wait_for_event("Page.loadEventFired")
        title = self._evaluate("document.title") or ""
        print(f"OK: navigated to {url} | title={title}")

    def click(self, selector: str) -> None:
        hint = selector.lstrip("@")
        find_js = _make_find_js(hint)
        js = """
        (function() {
            const el = %s;
            if (!el) throw new Error('Element not found: %s');
            el.scrollIntoView({block: 'center'});
            el.click();
            return 'clicked';
        })()
        """ % (find_js, hint)
        self._evaluate(js)
        print(f"OK: clicked {selector}")

    def fill(self, selector: str, value: str) -> None:
        hint = selector.lstrip("@")
        find_js = _make_find_js(hint)
        # 요소를 찾아 포커스 + 기존 값 클리어
        focus_js = """
        (function() {
            const el = %s;
            if (!el) throw new Error('Element not found: %s');
            el.scrollIntoView({block: 'center'});
            el.focus();
            el.select && el.select();
            return 'focused';
        })()
        """ % (find_js, hint)
        self._evaluate(focus_js)
        # 기존 값 선택 후 삭제
        self._send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "a", "code": "KeyA", "modifiers": 2,
        })
        self._send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "a", "code": "KeyA", "modifiers": 2,
        })
        self._send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "Backspace", "code": "Backspace",
            "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8,
        })
        self._send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "Backspace", "code": "Backspace",
            "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8,
        })
        # CDP Input.insertText로 값 입력 (특수문자 안전, React 호환)
        self._send("Input.insertText", {"text": value})
        print(f"OK: filled {selector} with '{value}'")

    def wait_for(self, selector: str) -> None:
        if selector.strip().isdigit():
            ms = int(selector.strip())
            time.sleep(ms / 1000)
            print(f"OK: waited {ms}ms")
            return
        hint = selector.lstrip("@")
        self._wait_for_element(hint)
        print(f"OK: element {selector} is visible")

    def check(self, selector: str) -> None:
        hint = selector.lstrip("@")
        self._wait_for_element(hint)
        print(f"OK: element {selector} confirmed visible")

    def press(self, key: str) -> None:
        # CDP Input.dispatchKeyEvent 사용
        key_map = {
            "Enter": {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13},
            "Tab": {"key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9, "nativeVirtualKeyCode": 9},
            "Escape": {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27},
            "Backspace": {"key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8},
        }
        if key in key_map:
            key_info = key_map[key]
        elif len(key) == 1:
            code = ord(key.upper())
            key_info = {"key": key, "code": f"Key{key.upper()}", "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code}
        else:
            key_info = {"key": key, "code": key, "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0}

        self._send("Input.dispatchKeyEvent", {
            "type": "keyDown",
            **key_info,
        })
        self._send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            **key_info,
        })

        # 페이지 전환이 발생할 수 있으므로 대기
        try:
            self._wait_for_event("Page.loadEventFired", timeout=DEFAULT_TIMEOUT)
        except TimeoutError:
            pass  # 전환 없는 키 입력도 있음
        print(f"OK: pressed {key}")

    def screenshot(self, path: str) -> None:
        result = self._send("Page.captureScreenshot", {"format": "png"})
        img_data = base64.b64decode(result["data"])
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(img_data)
        print(f"OK: screenshot saved to {path}")

    def close(self) -> None:
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

        if self._owns_browser and self._chrome_proc:
            self._chrome_proc.terminate()
            try:
                self._chrome_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._chrome_proc.kill()
            self._chrome_proc = None

        print("OK: browser closed" if self._owns_browser else "OK: disconnected")


def read_notion_page(url: str, expand_toggles: bool = False, cdp_port: int = None) -> str:
    """Notion 페이지를 CDP로 읽어서 텍스트만 반환.

    /json/new?{url} 로 새 탭을 열고, 렌더링 완료 후 innerText를 추출한다.
    cross-origin 이동 시 WebSocket 끊김 문제를 우회한다.

    Args:
        url: Notion 페이지 URL
        expand_toggles: True이면 토글을 모두 펼친 후 텍스트 추출
        cdp_port: CDP 포트 (기본 9222)

    Returns:
        페이지 텍스트 내용
    """
    port = cdp_port or _env_int("ORDER_AGENT_CDP_PORT", DEFAULT_CDP_PORT)
    cdp_http = f"http://localhost:{port}"

    # 1. 새 탭을 URL과 함께 생성
    try:
        resp = urllib.request.urlopen(f"{cdp_http}/json/new?{url}", timeout=10)
        target = json.loads(resp.read().decode())
    except Exception as e:
        raise RuntimeError(
            f"CDP not available on port {port}. "
            f"Start Chrome with: google-chrome --remote-debugging-port={port}"
        ) from e

    target_id = target["id"]
    ws_url = target["webSocketDebuggerUrl"]

    # 2. SPA 로딩 대기
    time.sleep(8)

    # 3. WebSocket 연결
    ws = websocket.create_connection(ws_url, timeout=30)
    msg_id = 0

    def send_cmd(method: str, params: Optional[dict] = None) -> dict:
        nonlocal msg_id
        msg_id += 1
        msg = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        ws.send(json.dumps(msg))
        deadline = time.time() + 30
        while time.time() < deadline:
            raw = ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == msg_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})
        raise TimeoutError(f"CDP timeout: {method}")

    try:
        send_cmd("Runtime.enable")

        # 4. 토글 확장
        if expand_toggles:
            for _ in range(10):
                result = send_cmd("Runtime.evaluate", {
                    "expression": """
                    (() => {
                        const frame = document.querySelector('.notion-frame');
                        if (!frame) return 0;
                        let clicked = 0;
                        frame.querySelectorAll('[aria-expanded="false"]').forEach(el => {
                            if (el.closest('.notion-sidebar') || el.closest('[class*="sidebar"]')) return;
                            el.click();
                            clicked++;
                        });
                        return clicked;
                    })()
                    """,
                    "returnByValue": True,
                })
                clicked = result.get("result", {}).get("value", 0)
                if clicked == 0:
                    break
                time.sleep(2)

        # 5. 텍스트 추출
        result = send_cmd("Runtime.evaluate", {
            "expression": """
            (() => {
                const scroller = document.querySelector('.notion-frame .notion-scroller');
                if (scroller) return scroller.innerText;
                return document.body.innerText || '';
            })()
            """,
            "returnByValue": True,
        })
        text = result.get("result", {}).get("value", "")
    finally:
        ws.close()
        # 탭 닫기
        try:
            urllib.request.urlopen(f"{cdp_http}/json/close/{target_id}", timeout=5)
        except Exception:
            pass

    return text


def ensure_chrome_debug_running() -> bool:
    """CDP 포트 열려있는지 확인."""
    cdp_port = _env_int("ORDER_AGENT_CDP_PORT", DEFAULT_CDP_PORT)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(("localhost", cdp_port))
        sock.close()
        return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(1)

    # read-notion 서브커맨드: CDP로 Notion 페이지 텍스트 추출
    if sys.argv[1] == "read-notion":
        notion_args = sys.argv[2:]
        if not notion_args:
            print("Usage: python3 -m core.agent_browser read-notion <notion-url> [--expand-toggles]", file=sys.stderr)
            raise SystemExit(1)
        notion_url = [a for a in notion_args if not a.startswith("--")][0]
        expand = "--expand-toggles" in notion_args
        text = read_notion_page(notion_url, expand_toggles=expand)
        print(text)
        return

    use_cdp = "--cdp" in sys.argv
    args_list = [a for a in sys.argv[1:] if a != "--cdp"]

    command = args_list[0]
    args = args_list[1:]

    ab = AgentBrowser(mode="cdp" if use_cdp else "launch")
    ab.launch()

    try:
        if command == "open":
            ab.open(args[0])
        elif command == "click":
            ab.click(args[0])
        elif command == "fill":
            ab.fill(args[0], " ".join(args[1:]))
        elif command == "wait-for":
            ab.wait_for(args[0])
        elif command == "check":
            ab.check(args[0])
        elif command == "press":
            ab.press(args[0])
        elif command == "screenshot":
            ab.screenshot(args[0])
        elif command == "close":
            ab.close()
            return
        else:
            print(f"ERROR: unknown command '{command}'", file=sys.stderr)
            raise SystemExit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        ab.close()


if __name__ == "__main__":
    main()
