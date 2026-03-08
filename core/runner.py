"""agent-browser 공통 실행기."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import shlex
import socket
import subprocess
import time
from typing import Sequence
import urllib.parse
import urllib.request


class AgentBrowserError(RuntimeError):
    """agent-browser 실행 실패 예외."""

    def __init__(
        self,
        message: str,
        returncode: int,
        cmd: Sequence[str],
        stdout: str,
        stderr: str,
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.cmd = list(cmd)
        self.stdout = stdout
        self.stderr = stderr


_CDP_TABS_SANITIZED = False


def _is_truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_browser_executable() -> str | None:
    explicit = os.getenv("AGENT_BROWSER_EXECUTABLE_PATH", "").strip()
    if explicit and Path(explicit).exists():
        return explicit

    if _is_truthy(os.getenv("ORDER_AGENT_DISABLE_BROWSER_PATH_RESOLVE")):
        return None

    candidates: list[str] = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    ]
    for binary in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(binary)
        if found:
            candidates.append(found)

    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def _build_agent_browser_env() -> dict[str, str]:
    env = os.environ.copy()

    # openclaw-like behavior: try attaching to an existing browser first.
    if "AGENT_BROWSER_AUTO_CONNECT" not in env:
        env["AGENT_BROWSER_AUTO_CONNECT"] = env.get("ORDER_AGENT_BROWSER_AUTO_CONNECT", "1")

    if not env.get("AGENT_BROWSER_EXECUTABLE_PATH"):
        resolved = _resolve_browser_executable()
        if resolved:
            env["AGENT_BROWSER_EXECUTABLE_PATH"] = resolved

    return env


def _cdp_port() -> int:
    raw = os.getenv("ORDER_AGENT_CDP_PORT", "9222").strip()
    try:
        return int(raw)
    except ValueError:
        return 9222


def _cdp_ready(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.8)
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _should_manage_browser() -> bool:
    if _is_truthy(os.getenv("ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP")):
        return False
    return True


def _browser_profile_dir() -> str:
    return os.getenv(
        "ORDER_AGENT_BROWSER_PROFILE_DIR",
        str(Path.home() / ".order-agent" / "browser" / "agent-browser-profile"),
    )


def _launch_browser_for_cdp() -> bool:
    executable = _resolve_browser_executable()
    if not executable:
        return False

    port = _cdp_port()
    profile_dir = _browser_profile_dir()
    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    launch_args = [
        executable,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
    ]
    if not _is_truthy(os.getenv("ORDER_AGENT_BROWSER_ENABLE_EXTENSIONS")):
        launch_args.extend(
            [
                "--disable-extensions",
                "--disable-component-extensions-with-background-pages",
                "--disable-background-networking",
            ]
        )
    if _is_truthy(os.getenv("ORDER_AGENT_BROWSER_HEADLESS")):
        launch_args.extend(["--headless=new", "--disable-gpu"])
    if _is_truthy(os.getenv("ORDER_AGENT_BROWSER_NO_SANDBOX")):
        launch_args.extend(["--no-sandbox", "--disable-setuid-sandbox"])

    extra_raw = os.getenv("ORDER_AGENT_BROWSER_EXTRA_ARGS", "").strip()
    if extra_raw:
        launch_args.extend(shlex.split(extra_raw))
    elif not _is_truthy(os.getenv("ORDER_AGENT_BROWSER_HEADLESS")):
        # Keep at least one visible window so macOS doesn't immediately hide/close it.
        launch_args.extend(["--new-window", "about:blank"])

    subprocess.Popen(
        launch_args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    for _ in range(15):
        time.sleep(0.7)
        if _cdp_ready(port):
            return True
    return False


def _ensure_cdp_browser_ready() -> bool:
    if not _should_manage_browser():
        return _cdp_ready(_cdp_port())
    port = _cdp_port()
    if _cdp_ready(port):
        return True
    if _is_truthy(os.getenv("ORDER_AGENT_BROWSER_ATTACH_ONLY")):
        return False
    return _launch_browser_for_cdp()


def _should_inject_cdp(args: Sequence[str]) -> bool:
    if _is_truthy(os.getenv("ORDER_AGENT_DISABLE_CDP_INJECTION")):
        return False
    if "--cdp" in args or "--auto-connect" in args:
        return False
    if not args:
        return True
    if args[0] in {"install", "--help", "--version", "-V"}:
        return False
    return True


def _is_no_running_browser_error(stderr: str) -> bool:
    s = (stderr or "").lower()
    return "no running chrome instance with remote debugging found" in s


def _is_transient_context_error(stderr: str) -> bool:
    s = (stderr or "").lower()
    return "execution context was destroyed" in s


def _agent_browser_timeout_sec() -> float:
    raw = os.getenv("ORDER_AGENT_AGENT_BROWSER_TIMEOUT_SEC", "").strip()
    if not raw:
        return 20.0
    try:
        value = float(raw)
    except ValueError:
        return 20.0
    if value <= 0:
        return 20.0
    return value


def _is_timeout_error(result: subprocess.CompletedProcess[str]) -> bool:
    if result.returncode == 124:
        return True
    return "timeout expired" in (result.stderr or "").lower()


def _run_agent_browser(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    timeout_sec = _agent_browser_timeout_sec()
    try:
        return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", errors="ignore") if exc.stdout else "")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else "")
        stderr = (stderr + f"\nagent-browser timeout expired after {timeout_sec:.1f}s").strip()
        return subprocess.CompletedProcess(cmd, 124, stdout, stderr)


def _sanitize_cdp_tabs_once(port: int) -> None:
    global _CDP_TABS_SANITIZED
    if _CDP_TABS_SANITIZED:
        return
    if _is_truthy(os.getenv("ORDER_AGENT_DISABLE_CDP_TAB_SANITIZE")):
        return

    base = f"http://127.0.0.1:{port}"
    try:
        resp = urllib.request.urlopen(f"{base}/json", timeout=2.5)
        pages = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return
    if not isinstance(pages, list):
        return

    page_targets = [p for p in pages if isinstance(p, dict) and p.get("type") == "page" and p.get("id")]
    if len(page_targets) <= 1:
        _CDP_TABS_SANITIZED = True
        return

    keep = page_targets[0]
    for p in page_targets:
        url = str(p.get("url", "") or "")
        if "alpha.zigzag.kr" in url or url == "about:blank":
            keep = p
            break

    for p in page_targets:
        target_id = str(p.get("id", "") or "")
        if not target_id or target_id == keep.get("id"):
            continue
        try:
            encoded = urllib.parse.quote(target_id, safe="")
            urllib.request.urlopen(f"{base}/json/close/{encoded}", timeout=1.5)
        except Exception:
            pass
    _CDP_TABS_SANITIZED = True


def agent_browser(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run agent-browser command with optional error check."""
    port = _cdp_port()
    browser_ready = _ensure_cdp_browser_ready()
    cmd = ["agent-browser"]
    inject_cdp = browser_ready and _should_inject_cdp(args)
    if inject_cdp:
        _sanitize_cdp_tabs_once(port)
        cmd.extend(["--cdp", str(port)])
    cmd.extend(args)
    env = _build_agent_browser_env()
    if inject_cdp:
        env["AGENT_BROWSER_AUTO_CONNECT"] = "0"
    result = _run_agent_browser(cmd, env=env)

    # openclaw-like fallback: attach(auto-connect) 실패 시 launch 경로로 1회 재시도
    if result.returncode != 0 and env.get("AGENT_BROWSER_AUTO_CONNECT", "1") == "1":
        if _is_no_running_browser_error(result.stderr):
            retry_env = env.copy()
            retry_env["AGENT_BROWSER_AUTO_CONNECT"] = "0"
            result = _run_agent_browser(cmd, env=retry_env)

    # page lifecycle race 대응 (navigation context destroyed)
    if result.returncode != 0 and _is_transient_context_error(result.stderr):
        result = _run_agent_browser(cmd, env=env)

    # agent-browser 내부 대기 무한루프 대응: timeout 1회 재시도
    if result.returncode != 0 and _is_timeout_error(result):
        result = _run_agent_browser(cmd, env=env)

    if check and result.returncode != 0:
        raise AgentBrowserError(
            message=f"agent-browser failed with code {result.returncode}",
            returncode=result.returncode,
            cmd=cmd,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    return result
