"""Reusable environment diagnostics for order-agent onboarding and preflight."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Iterable
import urllib.request

from core.runner import (
    _browser_profile_dir,
    _cdp_port,
    _cdp_ready,
    _ensure_cdp_browser_ready,
    _is_truthy,
    _resolve_browser_executable,
    active_profile_name,
    agent_browser,
)


LINE = "─" * 70

_CACHE_DIR = Path.home() / ".order-agent" / "cache"
_CACHE_TTL_SEC = 300  # 5 minutes


def _cache_key() -> str:
    """Generate cache key based on environment state that affects checks."""
    parts = [
        os.getenv("ORDER_AGENT_CDP_PORT", "9222"),
        os.getenv("ORDER_AGENT_BROWSER_PROFILE_DIR", ""),
        os.getenv("ORDER_AGENT_BROWSER_PROFILE_NAME", ""),
        os.getenv("AGENT_BROWSER_EXECUTABLE_PATH", ""),
        str(Path(".env").resolve().exists()),
        shutil.which("agent-browser") or "",
    ]
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]


def _read_cache() -> "list[DoctorCheck] | None":
    """Read cached check results if still valid."""
    cache_file = _CACHE_DIR / f"doctor-{_cache_key()}.json"
    if not cache_file.exists():
        return None
    try:
        age = time.time() - cache_file.stat().st_mtime
        if age > _CACHE_TTL_SEC:
            return None
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return [DoctorCheck(**item) for item in data]
    except Exception:
        return None


def _write_cache(checks: "list[DoctorCheck]") -> None:
    """Cache check results (best-effort)."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = _CACHE_DIR / f"doctor-{_cache_key()}.json"
        data = [check.as_dict() for check in checks]
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def invalidate_cache() -> None:
    """Clear all cached doctor results."""
    try:
        if _CACHE_DIR.exists():
            for f in _CACHE_DIR.glob("doctor-*.json"):
                f.unlink(missing_ok=True)
    except Exception:
        pass


_COLOR_GREEN = "\033[32m"
_COLOR_YELLOW = "\033[33m"
_COLOR_RED = "\033[31m"
_COLOR_RESET = "\033[0m"

_STATUS_COLOR = {
    "PASS": _COLOR_GREEN,
    "WARN": _COLOR_YELLOW,
    "FAIL": _COLOR_RED,
}
_STATUS_ICON = {
    "PASS": "✓",
    "WARN": "⚠",
    "FAIL": "✗",
}


@dataclass
class DoctorCheck:
    key: str
    status: str
    summary: str
    detail: str = ""
    hint: str = ""
    duration_ms: int = 0
    cached: bool = False

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "status": self.status,
            "summary": self.summary,
            "detail": self.detail,
            "hint": self.hint,
            "duration_ms": self.duration_ms,
            "cached": self.cached,
        }


def load_env_file() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def _mask(raw: str) -> str:
    if not raw:
        return ""
    if len(raw) <= 4:
        return "*" * len(raw)
    return raw[:2] + ("*" * (len(raw) - 4)) + raw[-2:]


def _browser_mode_summary() -> str:
    if _is_truthy(os.getenv("ORDER_AGENT_BROWSER_ATTACH_ONLY")):
        return "attach-only"
    if _is_truthy(os.getenv("ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP")):
        return "attach-preferred (auto-launch disabled)"
    return "attach-preferred (auto-launch enabled)"


def _profile_scope_summary(profile_dir: str) -> str:
    name = active_profile_name()
    custom = os.getenv("ORDER_AGENT_BROWSER_PROFILE_DIR", "").strip() or os.getenv("ORDER_AGENT_BROWSER_PROFILE_NAME", "").strip()
    if custom:
        return f"'{name}' (custom)"
    return f"'{name}' (default)"


def _timed_check(fn: "callable") -> "DoctorCheck":
    """Run fn() and stamp the returned DoctorCheck with elapsed duration_ms."""
    t0 = time.monotonic()
    check = fn()
    check.duration_ms = int((time.monotonic() - t0) * 1000)
    return check


def collect_doctor_checks(launch_browser: bool = True, use_cache: bool = False) -> list[DoctorCheck]:
    if use_cache:
        cached = _read_cache()
        if cached is not None:
            for check in cached:
                check.cached = True
            return cached

    checks: list[DoctorCheck] = []

    def _check_env_file() -> DoctorCheck:
        env_file = Path(".env").resolve()
        if env_file.exists():
            return DoctorCheck("env_file", "PASS", ".env file detected", str(env_file))
        return DoctorCheck(
            "env_file",
            "WARN",
            ".env file not found",
            "Create .env from .env.example before running real scenarios.",
            "cp .env.example .env",
        )

    def _check_agent_browser() -> DoctorCheck:
        path = shutil.which("agent-browser")
        if path:
            return DoctorCheck("agent_browser", "PASS", "agent-browser CLI ready", path)
        return DoctorCheck(
            "agent_browser",
            "FAIL",
            "agent-browser CLI not found",
            "PATH does not include the agent-browser executable.",
            "npm install -g agent-browser",
        )

    def _check_chrome() -> DoctorCheck:
        chrome_path = _resolve_browser_executable()
        if chrome_path:
            return DoctorCheck("chrome", "PASS", "Chrome executable resolved", chrome_path)
        return DoctorCheck(
            "chrome",
            "FAIL",
            "Chrome executable not found",
            "Automatic browser path resolution failed.",
            "Set AGENT_BROWSER_EXECUTABLE_PATH to your Chrome/Chromium binary.",
        )

    def _check_profile() -> DoctorCheck:
        profile_dir = _browser_profile_dir()
        Path(profile_dir).mkdir(parents=True, exist_ok=True)
        return DoctorCheck(
            "profile",
            "PASS",
            f"Browser profile: {_profile_scope_summary(profile_dir)}",
            profile_dir,
        )

    def _check_browser_policy() -> DoctorCheck:
        return DoctorCheck(
            "browser_policy",
            "PASS",
            f"Browser mode: {_browser_mode_summary()}",
            f"CDP port {_cdp_port()} / extensions {'disabled' if _is_truthy(os.getenv('ORDER_AGENT_BROWSER_DISABLE_EXTENSIONS')) else 'enabled'}",
        )

    def _check_alpha_credentials() -> DoctorCheck:
        alpha_user = os.getenv("ZIGZAG_ALPHA_USERNAME", "").strip()
        alpha_pass = os.getenv("ZIGZAG_ALPHA_PASSWORD", "").strip()
        if alpha_user and alpha_pass:
            return DoctorCheck(
                "alpha_credentials",
                "PASS",
                "Alpha test credentials loaded",
                f"ZIGZAG_ALPHA_USERNAME={_mask(alpha_user)} / ZIGZAG_ALPHA_PASSWORD={_mask(alpha_pass)}",
            )
        missing = []
        if not alpha_user:
            missing.append("ZIGZAG_ALPHA_USERNAME")
        if not alpha_pass:
            missing.append("ZIGZAG_ALPHA_PASSWORD")
        return DoctorCheck(
            "alpha_credentials",
            "WARN",
            "Alpha test credentials incomplete",
            "Missing: " + ", ".join(missing),
            "Populate .env with test-account credentials.",
        )

    checks.append(_timed_check(_check_env_file))
    checks.append(_timed_check(_check_agent_browser))
    checks.append(_timed_check(_check_chrome))
    checks.append(_timed_check(_check_profile))
    checks.append(_timed_check(_check_browser_policy))
    checks.append(_timed_check(_check_alpha_credentials))

    # CDP / browser checks (potentially slow — timed individually)
    def _check_cdp() -> DoctorCheck:
        port = _cdp_port()
        was_ready = _cdp_ready(port)
        cdp_ready = was_ready
        launched = False
        if not cdp_ready and launch_browser:
            cdp_ready = _ensure_cdp_browser_ready()
            launched = cdp_ready and not was_ready
        if cdp_ready:
            detail = f"CDP port {port}: connected"
            if launched:
                detail += " (browser auto-launched)"
            return DoctorCheck("cdp", "PASS", "Browser CDP ready", detail)
        hint = "./scripts/run_scenario_chrome.sh <scenario.scn>"
        if _is_truthy(os.getenv("ORDER_AGENT_BROWSER_ATTACH_ONLY")):
            hint = "Launch Chrome with remote debugging enabled, then rerun doctor."
        return DoctorCheck(
            "cdp",
            "FAIL",
            "Browser CDP unavailable",
            f"CDP port {port} is not reachable.",
            hint,
        )

    cdp_check = _timed_check(_check_cdp)
    checks.append(cdp_check)

    cdp_ready = cdp_check.status == "PASS"
    agent_browser_path = shutil.which("agent-browser")

    if cdp_ready and agent_browser_path:
        def _check_page() -> DoctorCheck:
            port = _cdp_port()
            try:
                result = agent_browser("get", "url", check=False)
                if result.returncode == 0 and result.stdout.strip():
                    return DoctorCheck("page", "PASS", "Active page available", result.stdout.strip())
                cdp_url = f"http://127.0.0.1:{port}/json/new?about:blank"
                req = urllib.request.Request(cdp_url, method="PUT")
                urllib.request.urlopen(req, timeout=5)
                time.sleep(0.5)
                retry = agent_browser("get", "url", check=False)
                if retry.returncode == 0 and retry.stdout.strip():
                    return DoctorCheck("page", "PASS", "Initial page auto-created", retry.stdout.strip())
                return DoctorCheck(
                    "page",
                    "WARN",
                    "Browser page unavailable",
                    "CDP is reachable but no active page could be created automatically.",
                )
            except Exception as exc:
                return DoctorCheck("page", "WARN", "Page check skipped", str(exc))

        checks.append(_timed_check(_check_page))

    if doctor_passed(checks):
        _write_cache(checks)

    return checks


def doctor_passed(checks: Iterable[DoctorCheck]) -> bool:
    return not any(check.status == "FAIL" for check in checks)


def doctor_strict_passed(checks: Iterable[DoctorCheck]) -> bool:
    return not any(check.status in {"FAIL", "WARN"} for check in checks)


def doctor_summary(checks: Iterable[DoctorCheck]) -> dict[str, int | bool]:
    items = list(checks)
    pass_count = sum(1 for check in items if check.status == "PASS")
    warn_count = sum(1 for check in items if check.status == "WARN")
    fail_count = sum(1 for check in items if check.status == "FAIL")
    return {
        "total": len(items),
        "pass": pass_count,
        "warn": warn_count,
        "fail": fail_count,
        "ok": fail_count == 0,
        "strict_ok": fail_count == 0 and warn_count == 0,
        "cached": any(check.cached for check in items),
    }


def print_doctor_report(
    checks: Iterable[DoctorCheck],
    *,
    stream: object | None = None,
    title: str = "Order Agent Doctor",
    use_color: bool | None = None,
) -> None:
    out = stream if stream is not None else sys.stderr
    if use_color is None:
        use_color = getattr(out, "isatty", lambda: False)()
    write = out.write

    def _colorize(status: str, text: str) -> str:
        if not use_color:
            return text
        color = _STATUS_COLOR.get(status, "")
        return f"{color}{text}{_COLOR_RESET}"

    items = list(checks)
    write(f"\n{LINE}\n")
    write(f"  {title}\n")
    write(f"{LINE}\n")
    for check in items:
        icon = _STATUS_ICON.get(check.status, " ")
        label = f"{icon} {check.status:<4}"
        timing = f"  [{check.duration_ms}ms]" if check.duration_ms >= 500 else ""
        cached_note = "  [cached]" if check.cached else ""
        write(f"  {_colorize(check.status, label)}  {check.summary}{timing}{cached_note}\n")
        if check.detail:
            write(f"        {check.detail}\n")
        if check.hint:
            write(f"        -> {check.hint}\n")

    # Summary line
    pass_count = sum(1 for c in items if c.status == "PASS")
    warn_count = sum(1 for c in items if c.status == "WARN")
    fail_count = sum(1 for c in items if c.status == "FAIL")
    parts = [
        _colorize("PASS", f"{pass_count} passed"),
        _colorize("WARN", f"{warn_count} warning{'s' if warn_count != 1 else ''}"),
        _colorize("FAIL", f"{fail_count} failed"),
    ]
    write(f"{LINE}\n")
    write(f"  {', '.join(parts)}\n\n")


def auto_fix_checks(checks: list[DoctorCheck]) -> list[str]:
    """Attempt browser auto-launch remediation only."""
    actions: list[str] = []
    for check in checks:
        if check.status not in {"WARN", "FAIL"}:
            continue

        if check.key == "cdp" and check.status == "FAIL":
            try:
                ok = _ensure_cdp_browser_ready()
                if ok:
                    actions.append("Browser auto-launch succeeded for CDP.")
                else:
                    actions.append("Browser auto-launch failed; manual browser start is still required.")
            except Exception as exc:
                actions.append(f"Browser auto-launch failed: {exc}")

    return actions


def doctor_report_json(checks: Iterable[DoctorCheck]) -> str:
    items = list(checks)
    payload = {
        "summary": doctor_summary(items),
        "checks": [check.as_dict() for check in items],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def doctor_report_text(
    checks: Iterable[DoctorCheck],
    *,
    title: str = "Order Agent Doctor",
    quiet: bool = False,
) -> str:
    items = list(checks)
    if quiet:
        filtered = [check for check in items if check.status != "PASS"]
        if not filtered:
            summary = "PASS  All doctor checks passed."
            if any(check.cached for check in items):
                summary += " [cached]"
            return summary + "\n"
        lines = [f"{check.status:<4}  {check.summary}" for check in filtered]
        for check in filtered:
            if check.detail:
                lines.append(f"      {check.detail}")
            if check.hint:
                lines.append(f"      -> {check.hint}")
        return "\n".join(lines) + "\n"

    lines = ["", LINE, f"  {title}", LINE]
    for check in items:
        lines.append(f"  {check.status:<4}  {check.summary}")
        if check.detail:
            lines.append(f"        {check.detail}")
        if check.hint:
            lines.append(f"        -> {check.hint}")
    lines.extend([LINE, ""])
    return "\n".join(lines)
