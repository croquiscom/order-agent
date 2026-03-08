"""core/runner.py 테스트."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runner import agent_browser, AgentBrowserError


@patch("core.runner.subprocess.run")
def test_agent_browser_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
    with patch.dict(
        "os.environ",
        {
            "ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP": "1",
            "ORDER_AGENT_DISABLE_CDP_INJECTION": "1",
        },
        clear=False,
    ):
        result = agent_browser("open", "https://example.com")

    assert mock_run.call_count == 1
    called_cmd = mock_run.call_args.args[0]
    called_kwargs = mock_run.call_args.kwargs
    assert called_cmd == ["agent-browser", "open", "https://example.com"]
    assert called_kwargs["capture_output"] is True
    assert called_kwargs["text"] is True
    assert "env" in called_kwargs
    assert result.returncode == 0


@patch("core.runner.subprocess.run")
def test_agent_browser_failure_raises(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")

    with pytest.raises(AgentBrowserError) as exc_info:
        with patch.dict(
            "os.environ",
            {
                "ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP": "1",
                "ORDER_AGENT_DISABLE_CDP_INJECTION": "1",
            },
            clear=False,
        ):
            agent_browser("click", "@button")

    assert exc_info.value.returncode == 1
    assert "agent-browser failed" in str(exc_info.value)


@patch("core.runner.subprocess.run")
def test_agent_browser_no_check(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="err")
    with patch.dict(
        "os.environ",
        {
            "ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP": "1",
            "ORDER_AGENT_DISABLE_CDP_INJECTION": "1",
        },
        clear=False,
    ):
        result = agent_browser("click", "@button", check=False)
    assert result.returncode == 1  # no exception raised


@patch("core.runner.subprocess.run")
@patch("core.runner._resolve_browser_executable", return_value="/tmp/chrome")
def test_agent_browser_sets_default_env(mock_resolve, mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    with patch.dict(
        "os.environ",
        {"ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP": "1", "ORDER_AGENT_DISABLE_CDP_INJECTION": "1"},
        clear=False,
    ):
        agent_browser("snapshot")
    env = mock_run.call_args.kwargs["env"]
    assert env["AGENT_BROWSER_AUTO_CONNECT"] == "1"
    assert env["AGENT_BROWSER_EXECUTABLE_PATH"] == "/tmp/chrome"


@patch("core.runner.subprocess.run")
def test_agent_browser_respects_existing_auto_connect(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    with patch.dict(
        "os.environ",
        {
            "AGENT_BROWSER_AUTO_CONNECT": "0",
            "ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP": "1",
            "ORDER_AGENT_DISABLE_CDP_INJECTION": "1",
        },
        clear=False,
    ):
        agent_browser("snapshot")
    env = mock_run.call_args.kwargs["env"]
    assert env["AGENT_BROWSER_AUTO_CONNECT"] == "0"


@patch("core.runner.subprocess.run")
def test_agent_browser_attach_failure_retries_with_launch(mock_run):
    mock_run.side_effect = [
        MagicMock(
            returncode=1,
            stdout="",
            stderr="No running Chrome instance with remote debugging found.",
        ),
        MagicMock(returncode=0, stdout="ok", stderr=""),
    ]
    with patch.dict(
        "os.environ",
        {
            "AGENT_BROWSER_AUTO_CONNECT": "1",
            "ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP": "1",
            "ORDER_AGENT_DISABLE_CDP_INJECTION": "1",
        },
        clear=False,
    ):
        result = agent_browser("open", "https://example.com")

    assert result.returncode == 0
    assert mock_run.call_count == 2
    first_env = mock_run.call_args_list[0].kwargs["env"]
    second_env = mock_run.call_args_list[1].kwargs["env"]
    assert first_env["AGENT_BROWSER_AUTO_CONNECT"] == "1"
    assert second_env["AGENT_BROWSER_AUTO_CONNECT"] == "0"


@patch("core.runner.subprocess.run")
def test_agent_browser_transient_context_error_retries_once(mock_run):
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="", stderr="page.title: Execution context was destroyed"),
        MagicMock(returncode=0, stdout="ok", stderr=""),
    ]
    with patch.dict(
        "os.environ",
        {
            "ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP": "1",
            "ORDER_AGENT_DISABLE_CDP_INJECTION": "1",
        },
        clear=False,
    ):
        result = agent_browser("open", "https://example.com")
    assert result.returncode == 0
    assert mock_run.call_count == 2


@patch("core.runner.subprocess.run")
def test_agent_browser_injects_cdp_when_ready(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
    with patch("core.runner._ensure_cdp_browser_ready", return_value=True):
        with patch("core.runner._sanitize_cdp_tabs_once") as mock_sanitize:
            with patch.dict("os.environ", {"ORDER_AGENT_CDP_PORT": "9333"}, clear=False):
                agent_browser("snapshot")
    called_cmd = mock_run.call_args.args[0]
    assert called_cmd[:3] == ["agent-browser", "--cdp", "9333"]
    mock_sanitize.assert_called_once_with(9333)
