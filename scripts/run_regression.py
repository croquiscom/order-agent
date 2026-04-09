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
    passed: bool
    exit_code: int
    duration_sec: float
    worker_id: int
    error: str = ""


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


def collect_scenarios(tier: str, area: str | None) -> list[Path]:
    """Collect .scn files matching tier and optional area filter."""
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

        matched.append(path)
    return matched


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
        passed=exit_code == 0,
        exit_code=exit_code,
        duration_sec=round(elapsed, 1),
        worker_id=worker_id,
        error=error,
    )


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
    parser.add_argument("--workers", type=int, default=3, help="Number of parallel workers (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Validate scenarios without executing")
    parser.add_argument("extra_args", nargs="*", help="Extra args passed to execute_scenario.py (after --)")

    args = parser.parse_args()

    scenarios = collect_scenarios(args.tier, args.area)
    if not scenarios:
        print(f"No scenarios found for tier={args.tier}, area={args.area}", file=sys.stderr)
        return 1

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
    print_summary(report)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
