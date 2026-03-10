"""agent-browser(CDP+Chrome) 기반 시나리오 실행기."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.agent_browser import AgentBrowser, ensure_chrome_debug_running
from core.logger import setup_logger

ALLOWED_ACTIONS = {"NAVIGATE", "CLICK", "FILL", "WAIT_FOR", "CHECK", "PRESS"}


def parse_scenario(path: Path):
    commands = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            tokens = shlex.split(line)
            action = tokens[0]
            if action not in ALLOWED_ACTIONS:
                raise ValueError(f"line {line_no}: unknown action '{action}'")
            commands.append({"line": line_no, "action": action, "args": tokens[1:]})
    return commands


def run_scenario(ab: AgentBrowser, commands: list, logger) -> int:
    failures = 0
    for i, cmd in enumerate(commands, 1):
        action = cmd["action"]
        args = cmd["args"]
        logger.info("[STEP %d/%d] line %d: %s %s",
                    i, len(commands), cmd["line"], action, " ".join(args))
        try:
            if action == "NAVIGATE":
                ab.open(args[0])
            elif action == "CLICK":
                ab.click("@" + args[0])
            elif action == "FILL":
                ab.fill("@" + args[0], " ".join(args[1:]))
            elif action == "WAIT_FOR":
                if args[0].isdigit():
                    ab.wait_for(args[0])
                else:
                    ab.wait_for("@" + args[0])
            elif action == "CHECK":
                ab.check("@" + args[0])
            elif action == "PRESS":
                ab.press(args[0])
            logger.info("  -> OK")
        except Exception as e:
            failures += 1
            logger.error("  FAILED: %s", e)
    return failures


def main():
    # --cdp 플래그: 이미 열린 Chrome에 연결
    use_cdp = "--cdp" in sys.argv
    argv = [a for a in sys.argv[1:] if a != "--cdp"]

    scenario_path = Path(argv[0]) if argv else None
    if not scenario_path or not scenario_path.exists():
        print(f"Usage: python3 {__file__} [--cdp] <scenario.scn>", file=sys.stderr)
        raise SystemExit(1)

    logger = setup_logger("agent-browser-runner")
    commands = parse_scenario(scenario_path)
    logger.info("Loaded %d commands from %s", len(commands), scenario_path)

    if use_cdp:
        logger.info("Connecting to existing Chrome via CDP...")
        if not ensure_chrome_debug_running():
            logger.error("Cannot connect to Chrome CDP on port 9222")
            raise SystemExit(1)

    mode = "cdp" if use_cdp else "launch"
    ab = AgentBrowser(mode=mode)
    ab.launch()
    logger.info("Browser ready (mode=%s)", mode)

    try:
        failures = run_scenario(ab, commands, logger)

        # 결과 스크린샷 저장
        import time
        time.sleep(3)
        screenshot_path = str(REPO_ROOT / "logs" / "result.png")
        try:
            ab.screenshot(screenshot_path)
            logger.info("Screenshot saved: %s", screenshot_path)
        except Exception as e:
            logger.warning("Screenshot failed: %s", e)
    finally:
        ab.close()

    if failures:
        logger.error("Completed with %d failure(s)", failures)
        raise SystemExit(1)

    logger.info("All steps completed successfully!")


if __name__ == "__main__":
    main()
