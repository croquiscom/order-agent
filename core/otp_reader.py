"""CDP를 통해 Authenticator 확장프로그램에서 OTP 코드를 읽는 유틸리티."""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# Authenticator 확장프로그램 (https://authenticator.cc/)
AUTHENTICATOR_EXT_ID = "bhghoamapcdpbohphigoooaddinpkbai"
AUTHENTICATOR_POPUP_PATH = "view/popup.html"


def _cdp_port() -> int:
    import os
    raw = os.getenv("ORDER_AGENT_CDP_PORT", "9222").strip()
    try:
        return int(raw)
    except ValueError:
        return 9222


def read_otp(account_name: str, cdp_port: Optional[int] = None) -> str:
    """Authenticator 확장프로그램에서 특정 계정의 OTP 코드를 읽어 반환한다.

    Args:
        account_name: 매칭할 계정 이름 (대소문자 무시, 부분 일치).
        cdp_port: CDP 포트. None이면 환경변수 또는 기본값 9222.

    Returns:
        6자리 OTP 코드 문자열.

    Raises:
        RuntimeError: 확장프로그램 접근 실패 또는 계정을 찾을 수 없을 때.
    """
    port = cdp_port or _cdp_port()
    cdp_http = f"http://localhost:{port}"
    ext_url = f"chrome-extension://{AUTHENTICATOR_EXT_ID}/{AUTHENTICATOR_POPUP_PATH}"

    try:
        import websocket  # type: ignore
    except ImportError:
        raise RuntimeError(
            "websocket-client 패키지가 필요합니다: pip install websocket-client"
        )

    # 1) 브라우저 타겟에 연결하여 확장프로그램 팝업 탭 생성
    try:
        resp = urllib.request.urlopen(f"{cdp_http}/json/version", timeout=5)
        info = json.loads(resp.read().decode())
        browser_ws = info["webSocketDebuggerUrl"]
    except Exception as exc:
        raise RuntimeError(f"CDP 연결 실패 (port {port}): {exc}")

    ws_browser = websocket.create_connection(browser_ws, timeout=10)
    try:
        ws_browser.send(json.dumps({
            "id": 1,
            "method": "Target.createTarget",
            "params": {"url": ext_url},
        }))
        result = json.loads(ws_browser.recv())
        if "error" in result:
            raise RuntimeError(f"확장프로그램 팝업 열기 실패: {result['error']}")
        target_id = result["result"]["targetId"]
    finally:
        ws_browser.close()

    # 2) 팝업 로딩 대기
    time.sleep(3)

    # 3) 팝업 타겟의 WebSocket URL 획득
    page_ws_url = None
    try:
        resp = urllib.request.urlopen(f"{cdp_http}/json/list", timeout=5)
        targets = json.loads(resp.read().decode())
        for t in targets:
            if t.get("id") == target_id:
                page_ws_url = t["webSocketDebuggerUrl"]
                break
    except Exception as exc:
        raise RuntimeError(f"팝업 타겟 조회 실패: {exc}")

    if not page_ws_url:
        raise RuntimeError("확장프로그램 팝업 타겟을 찾을 수 없습니다")

    # 4) 팝업 페이지에서 OTP 코드 추출
    ws_page = websocket.create_connection(page_ws_url, timeout=10)
    try:
        ws_page.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": "document.body.innerText"},
        }))
        result = json.loads(ws_page.recv())
        body_text = result.get("result", {}).get("result", {}).get("value", "")
    finally:
        ws_page.close()

    # 5) 팝업 탭 닫기
    try:
        urllib.request.urlopen(f"{cdp_http}/json/close/{target_id}", timeout=5)
    except Exception:
        pass  # 닫기 실패는 무시

    if not body_text:
        raise RuntimeError("확장프로그램 팝업에서 내용을 읽을 수 없습니다")

    # 6) 계정 이름으로 OTP 코드 매칭
    # 팝업 텍스트 형식: "인증 도구\nAWS SSO\n737412\nace.f1@...\ndeploy\n293461\n..."
    lines = [line.strip() for line in body_text.strip().split("\n") if line.strip()]
    account_lower = account_name.lower()
    otp_pattern = re.compile(r"^\d{6}$")

    for i, line in enumerate(lines):
        if account_lower in line.lower():
            # 계정 이름 다음 줄들에서 6자리 OTP 코드 찾기
            for j in range(i + 1, min(i + 4, len(lines))):
                if otp_pattern.match(lines[j]):
                    logger.info("OTP 코드 읽기 성공: account=%s", account_name)
                    return lines[j]

    available = [
        line for line in lines
        if not otp_pattern.match(line) and line != "인증 도구"
    ]
    raise RuntimeError(
        f"계정 '{account_name}'을(를) 찾을 수 없습니다. "
        f"사용 가능한 계정: {', '.join(available)}"
    )
