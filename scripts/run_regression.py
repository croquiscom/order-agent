#!/usr/bin/env python3
"""Parallel regression runner with worker pool and tier/area filtering.

Usage:
    # Smoke tier (default, 매 배포)
    python3 scripts/run_regression.py

    # Specific tier
    python3 scripts/run_regression.py --tier regression
    python3 scripts/run_regression.py --tier full

    # Filter by area
    python3 scripts/run_regression.py --area claim
    python3 scripts/run_regression.py --tier regression --area exchange

    # Control parallelism
    python3 scripts/run_regression.py --workers 5

    # Dry run (validate without executing)
    python3 scripts/run_regression.py --dry-run

    # Pass extra args to execute_scenario.py
    python3 scripts/run_regression.py -- --fast-mode --var ORDER_NO=12345
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from executor.execute_scenario import parse_metadata

SCENARIOS_DIR = REPO_ROOT / "scenarios"
LOGS_DIR = REPO_ROOT / "logs"
BASE_CDP_PORT = 9222


@dataclass
class ScenarioResult:
    file: str
    title: str
    tier: str
    area: list[str]
    task: str
    priority: str
    passed: bool
    exit_code: int
    duration_sec: float
    worker_id: int
    error: str = ""
    manual_steps: list[str] = field(default_factory=list)


@dataclass
class RegressionReport:
    timestamp: str
    tier_filter: str
    area_filter: str
    workers: int
    total: int
    passed: int
    failed: int
    duration_sec: float
    results: list[dict] = field(default_factory=list)


def collect_scenarios(tier: str, area: str | None, tag_filters: dict[str, str] | None = None) -> list[Path]:
    """Collect .scn files matching tier, optional area, and tag filters."""
    matched = []
    for path in sorted(SCENARIOS_DIR.rglob("*.scn")):
        meta = parse_metadata(path)
        if not meta.tier:
            continue

        # tier filtering: "smoke" runs smoke only, "regression" runs smoke+regression,
        # "full" runs everything
        tier_order = {"smoke": 0, "regression": 1, "full": 2}
        file_tier_level = tier_order.get(meta.tier, 2)
        requested_tier_level = tier_order.get(tier, 0)
        if file_tier_level > requested_tier_level:
            continue

        if area and area not in meta.area:
            continue

        # --tag filtering
        if tag_filters:
            skip = False
            for fk, fv in tag_filters.items():
                tag_val = meta.tags.get(fk, "")
                if fk == "area":
                    if fv not in [a.lower() for a in meta.area]:
                        skip = True
                        break
                elif tag_val.lower() != fv:
                    skip = True
                    break
            if skip:
                continue

        matched.append(path)
    return matched


def extract_manual_steps(path: Path) -> list[str]:
    """Extract human-readable test steps from .scn comments and key actions."""
    import re
    steps = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        # Numbered comment steps: # 1) ..., # 2) ...
        if re.match(r"^#\s*\d+\)", line):
            steps.append(line.lstrip("# ").strip())
        # Key actions as supplementary info
        elif line.startswith("NAVIGATE "):
            steps.append(f"  → {line}")
        elif line.startswith("ENSURE_LOGIN_"):
            steps.append(f"  → 로그인: {line.split()[0].replace('ENSURE_LOGIN_', '')}")
        elif line.startswith("PICK_ORDER_FROM_POOL "):
            parts = line.split()
            steps.append(f"  → 주문풀: {parts[1]} 상태 주문 할당")
        elif line.startswith("CHECK ") or line.startswith("CHECK_URL ") or line.startswith("CHECK_NOT_URL "):
            steps.append(f"  → 검증: {line}")
        elif line.startswith("SUBMIT_"):
            action = line.split("_", 1)[1].split("_REQUEST")[0].lower()
            steps.append(f"  → 제출: {action} 요청")
        elif line.startswith("DUMP_STATE "):
            steps.append(f"  → 결과 캡처: {line.split()[1]}")
    return steps


def run_one_scenario(
    path: Path, worker_id: int, extra_args: list[str], dry_run: bool
) -> ScenarioResult:
    """Run a single scenario in a worker with isolated CDP port and profile."""
    meta = parse_metadata(path)
    rel = str(path.relative_to(REPO_ROOT))
    start = time.monotonic()

    cdp_port = BASE_CDP_PORT + worker_id
    profile_dir = str(REPO_ROOT / "logs" / f"worker_profile_{worker_id}")

    env = os.environ.copy()
    env["ORDER_AGENT_CDP_PORT"] = str(cdp_port)
    env["ORDER_AGENT_BROWSER_PROFILE_DIR"] = profile_dir

    cmd = [
        sys.executable,
        str(REPO_ROOT / "executor" / "execute_scenario.py"),
        str(path),
        "--continue-on-error",
    ]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend(extra_args)

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min per scenario
            cwd=str(REPO_ROOT),
        )
        exit_code = result.returncode
        error = ""
        if exit_code != 0:
            # Extract last meaningful error line from stderr
            stderr_lines = [l for l in result.stderr.strip().splitlines() if l.strip()]
            error = stderr_lines[-1] if stderr_lines else "unknown error"
    except subprocess.TimeoutExpired:
        exit_code = -1
        error = "timeout (300s)"
    except Exception as exc:
        exit_code = -2
        error = str(exc)

    elapsed = time.monotonic() - start
    return ScenarioResult(
        file=rel,
        title=meta.title,
        tier=meta.tier,
        area=meta.area,
        task=meta.task,
        priority=meta.priority,
        passed=exit_code == 0,
        exit_code=exit_code,
        duration_sec=round(elapsed, 1),
        worker_id=worker_id,
        error=error,
        manual_steps=extract_manual_steps(path),
    )


def send_slack_notification(report: RegressionReport, webhook_url: str) -> bool:
    """Send regression result to Slack via webhook. Returns True on success."""
    import urllib.request
    import urllib.error

    passed_all = report.failed == 0
    emoji = ":white_check_mark:" if passed_all else ":x:"
    status = "PASS" if passed_all else "FAIL"
    color = "#36a64f" if passed_all else "#e01e5a"

    failed_lines = ""
    if report.failed > 0:
        for r in report.results:
            if not r["passed"]:
                err = f" — {r['error']}" if r.get("error") else ""
                failed_lines += f"  `{r['file']}`{err}\n"

    tag_info = ""
    if hasattr(report, "tag_filter") and report.tag_filter:
        tag_info = f" | Tags: {report.tag_filter}"

    payload = {
        "attachments": [{
            "color": color,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{emoji} QA Gate {status}: {report.passed}/{report.total} passed"}
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Tier:* {report.tier_filter} | *Area:* {report.area_filter or 'all'}{tag_info}\n"
                            f"*Duration:* {report.duration_sec}s | *Workers:* {report.workers}\n"
                            f"*Time:* {report.timestamp}"
                        ),
                    },
                },
            ],
        }]
    }

    if failed_lines:
        payload["attachments"][0]["blocks"].append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Failed scenarios:*\n{failed_lines}"},
        })

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError) as exc:
        print(f"[WARN] Slack notification failed: {exc}", file=sys.stderr)
        return False


def print_summary(report: RegressionReport) -> None:
    """Print human-readable summary to stderr."""
    w = sys.stderr.write
    w(f"\n{'=' * 60}\n")
    w(f"  REGRESSION RESULT: {'PASS' if report.failed == 0 else 'FAIL'}\n")
    w(f"{'=' * 60}\n")
    w(f"  Tier: {report.tier_filter} | Area: {report.area_filter or 'all'}\n")
    w(f"  Workers: {report.workers} | Duration: {report.duration_sec}s\n")
    w(f"  Passed: {report.passed}/{report.total}")
    if report.failed > 0:
        w(f" | FAILED: {report.failed}")
    w("\n")

    if report.failed > 0:
        w(f"\n  Failed scenarios:\n")
        for r in report.results:
            if not r["passed"]:
                w(f"    FAIL  {r['file']} ({r['duration_sec']}s)\n")
                if r["error"]:
                    w(f"          {r['error']}\n")

    w(f"\n  Results: {report.results_path if hasattr(report, 'results_path') else 'see logs/'}\n")
    w(f"{'=' * 60}\n\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Parallel regression runner")
    parser.add_argument("--tier", default="smoke", choices=["smoke", "regression", "full"],
                        help="Tier level to run (default: smoke)")
    parser.add_argument("--area", default=None, help="Filter by area (e.g., claim, cart, order)")
    parser.add_argument("--tag", action="append", default=[], metavar="KEY=VALUE",
                        help="Filter by metadata tag (e.g. --tag priority=P0 --tag task=ORDER-11850)")
    parser.add_argument("--workers", type=int, default=3, help="Number of parallel workers (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Validate scenarios without executing")
    parser.add_argument("--slack", action="store_true",
                        help="Send result to Slack (requires ORDER_QA_SLACK_WEBHOOK env var)")
    parser.add_argument("--task-title", default="",
                        help="Epic/task title for HTML report header (e.g. '장바구니 옵션 변경')")
    parser.add_argument("--slack-on-fail", action="store_true",
                        help="Send Slack notification only on failure")
    parser.add_argument("extra_args", nargs="*", help="Extra args passed to execute_scenario.py (after --)")

    args = parser.parse_args()

    # --tag KEY=VALUE 파싱
    tag_filters: dict[str, str] = {}
    for tag_expr in args.tag:
        if "=" not in tag_expr:
            print(f"[ERROR] Invalid --tag format: {tag_expr!r} (expected KEY=VALUE)", file=sys.stderr)
            return 2
        k, v = tag_expr.split("=", 1)
        tag_filters[k.strip().lower()] = v.strip().lower()

    scenarios = collect_scenarios(args.tier, args.area, tag_filters or None)
    if not scenarios:
        print(f"No scenarios found for tier={args.tier}, area={args.area}", file=sys.stderr)
        return 1

    # Pre-flight: 주문풀 수요 점검
    from core.fixture_pool import preflight_check, analyze_demand_per_scenario
    pool_ok, pool_report = preflight_check(scenarios)
    print(pool_report, file=sys.stderr)
    if not pool_ok and not args.dry_run:
        print("[ERROR] 주문풀 부족 — 실행을 중단합니다. fixtures/order_pool.json을 확인하세요.", file=sys.stderr)
        return 2

    workers = min(args.workers, len(scenarios))
    print(f"Running {len(scenarios)} scenarios with {workers} workers (tier={args.tier}, area={args.area or 'all'})",
          file=sys.stderr)
    for i, s in enumerate(scenarios):
        print(f"  [{i+1}] {s.relative_to(REPO_ROOT)}", file=sys.stderr)
    print(file=sys.stderr)

    start = time.monotonic()
    results: list[ScenarioResult] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for idx, path in enumerate(scenarios):
            worker_id = idx % workers
            fut = pool.submit(run_one_scenario, path, worker_id, args.extra_args, args.dry_run)
            futures[fut] = path

        for fut in as_completed(futures):
            result = fut.result()
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {result.file} ({result.duration_sec}s)", file=sys.stderr)
            results.append(result)

    total_duration = round(time.monotonic() - start, 1)
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    # Sort results by original order
    scenario_order = {str(s.relative_to(REPO_ROOT)): i for i, s in enumerate(scenarios)}
    results.sort(key=lambda r: scenario_order.get(r.file, 999))

    report = RegressionReport(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        tier_filter=args.tier,
        area_filter=args.area or "",
        workers=workers,
        total=len(results),
        passed=passed,
        failed=failed,
        duration_sec=total_duration,
        results=[asdict(r) for r in results],
    )

    # Save JSON report
    LOGS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = LOGS_DIR / f"regression_result_{ts}.json"
    report_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")

    report.results_path = str(report_path.relative_to(REPO_ROOT))  # type: ignore[attr-defined]
    report.tag_filter = ", ".join(f"{k}={v}" for k, v in tag_filters.items()) if tag_filters else ""  # type: ignore[attr-defined]
    print_summary(report)

    # HTML report generation
    try:
        from tools.generate_report_html import generate_html
        report_data = asdict(report)
        report_data["tag_filter"] = ", ".join(f"{k}={v}" for k, v in tag_filters.items()) if tag_filters else ""
        report_data["task_title"] = args.task_title
        report_data["scenario_demands"] = analyze_demand_per_scenario(scenarios, REPO_ROOT)
        html = generate_html(report_data)
        html_path = LOGS_DIR / f"qa_report_{ts}.html"
        html_path.write_text(html, encoding="utf-8")
        print(f"[INFO] HTML report: {html_path.relative_to(REPO_ROOT)}", file=sys.stderr)
    except Exception as exc:
        print(f"[WARN] HTML report generation failed: {exc}", file=sys.stderr)

    # Slack notification
    slack_webhook = os.environ.get("ORDER_QA_SLACK_WEBHOOK", "")
    if slack_webhook and (args.slack or args.slack_on_fail):
        should_send = args.slack or (args.slack_on_fail and failed > 0)
        if should_send:
            ok = send_slack_notification(report, slack_webhook)
            if ok:
                print("[INFO] Slack notification sent", file=sys.stderr)
    elif (args.slack or args.slack_on_fail) and not slack_webhook:
        print("[WARN] --slack requested but ORDER_QA_SLACK_WEBHOOK env var not set", file=sys.stderr)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
