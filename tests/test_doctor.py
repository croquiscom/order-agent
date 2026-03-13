"""core.doctor diagnostics tests."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.doctor import (
    DoctorCheck,
    collect_doctor_checks,
    doctor_passed,
    doctor_report_json,
    doctor_report_text,
    doctor_strict_passed,
)


def _check_map(checks):
    return {check.key: check for check in checks}


@patch("core.doctor.Path.mkdir")
@patch("core.doctor.shutil.which", return_value="/tmp/agent-browser")
@patch("core.doctor._resolve_browser_executable", return_value="/tmp/chrome")
@patch("core.doctor._cdp_ready", return_value=True)
@patch("core.doctor.agent_browser", return_value=MagicMock(returncode=0, stdout="about:blank\n", stderr=""))
def test_collect_doctor_checks_pass_path(mock_agent_browser, mock_cdp_ready, mock_resolve, mock_which, mock_mkdir):
    with patch.dict(
        os.environ,
        {
            "ALPHA_USERNAME": "tester@example.com",
            "ALPHA_PASSWORD": "secret-pass",
        },
        clear=False,
    ):
        checks = collect_doctor_checks(launch_browser=False)

    items = _check_map(checks)
    assert doctor_passed(checks) is True
    assert items["agent_browser"].status == "PASS"
    assert items["chrome"].status == "PASS"
    assert items["profile"].status == "PASS"
    assert "Browser profile:" in items["profile"].summary
    assert "default" in items["profile"].summary
    assert items["cdp"].status == "PASS"
    assert items["page"].status == "PASS"


@patch("core.doctor.Path.mkdir")
@patch("core.doctor.shutil.which", return_value=None)
@patch("core.doctor._resolve_browser_executable", return_value=None)
@patch("core.doctor._cdp_ready", return_value=False)
@patch("core.doctor._ensure_cdp_browser_ready", return_value=False)
def test_collect_doctor_checks_reports_failures(mock_ensure, mock_cdp_ready, mock_resolve, mock_which, mock_mkdir):
    with patch.dict(os.environ, {}, clear=True):
        checks = collect_doctor_checks(launch_browser=True)

    items = _check_map(checks)
    assert doctor_passed(checks) is False
    assert items["agent_browser"].status == "FAIL"
    assert items["chrome"].status == "FAIL"
    assert items["alpha_credentials"].status == "WARN"
    assert items["cdp"].status == "FAIL"
    assert doctor_strict_passed(checks) is False


@patch("core.doctor.Path.mkdir")
@patch("core.doctor.shutil.which", return_value="/tmp/agent-browser")
@patch("core.doctor._resolve_browser_executable", return_value="/tmp/chrome")
@patch("core.doctor._cdp_ready", return_value=False)
@patch("core.doctor._ensure_cdp_browser_ready", return_value=False)
def test_collect_doctor_checks_respects_no_launch(mock_ensure, mock_cdp_ready, mock_resolve, mock_which, mock_mkdir):
    with patch.dict(os.environ, {"ORDER_AGENT_BROWSER_ATTACH_ONLY": "1"}, clear=False):
        checks = collect_doctor_checks(launch_browser=False)

    items = _check_map(checks)
    assert items["browser_policy"].detail.startswith("CDP port")
    assert items["cdp"].hint == "Launch Chrome with remote debugging enabled, then rerun doctor."
    mock_ensure.assert_not_called()


def test_doctor_report_json_contains_summary():
    payload = doctor_report_json(
        [
            DoctorCheck("env_file", "PASS", ".env file detected", "/tmp/.env"),
            DoctorCheck("alpha_credentials", "WARN", "Alpha test credentials incomplete", "Missing: ALPHA_PASSWORD"),
        ]
    )

    assert '"total": 2' in payload
    assert '"warn": 1' in payload
    assert '"strict_ok": false' in payload
    assert '"cached": false' in payload


def test_doctor_report_text_quiet_mode_filters_passes():
    rendered = doctor_report_text(
        [
            DoctorCheck("env_file", "PASS", ".env file detected", "/tmp/.env"),
            DoctorCheck("alpha_credentials", "WARN", "Alpha test credentials incomplete", "Missing: ALPHA_PASSWORD"),
        ],
        quiet=True,
    )

    assert "PASS  .env file detected" not in rendered
    assert "WARN" in rendered
    assert "Missing: ALPHA_PASSWORD" in rendered


def test_doctor_report_text_quiet_mode_all_pass():
    rendered = doctor_report_text(
        [DoctorCheck("env_file", "PASS", ".env file detected", "/tmp/.env")],
        quiet=True,
    )

    assert rendered == "PASS  All doctor checks passed.\n"


def test_doctor_report_text_quiet_mode_all_pass_cached():
    rendered = doctor_report_text(
        [DoctorCheck("env_file", "PASS", ".env file detected", "/tmp/.env", cached=True)],
        quiet=True,
    )

    assert rendered == "PASS  All doctor checks passed. [cached]\n"
