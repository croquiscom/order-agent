"""Standalone doctor CLI for onboarding and environment checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.doctor import (
    auto_fix_checks,
    collect_doctor_checks,
    doctor_passed,
    doctor_report_json,
    doctor_report_text,
    doctor_strict_passed,
    invalidate_cache,
    load_env_file,
    print_doctor_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run order-agent environment diagnostics")
    parser.add_argument(
        "--no-launch-browser",
        action="store_true",
        help="Do not auto-launch Chrome when CDP is not ready",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the text report",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat WARN checks as failures for exit status",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only WARN/FAIL items, or a one-line PASS summary",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write the rendered report to a file as well as stdout",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache and run fresh checks",
    )
    parser.add_argument(
        "--invalidate-cache",
        action="store_true",
        help="Clear cached results",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to auto-remediate WARN/FAIL items, then re-run checks to verify",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file()
    args = parse_args()

    if args.invalidate_cache:
        invalidate_cache()
        print("Cache cleared.")
        if not any([args.json, args.quiet, args.no_launch_browser, args.strict, args.output, args.no_cache, args.fix]):
            return

    if args.fix:
        _run_fix_mode(args)
        return

    checks = collect_doctor_checks(
        launch_browser=not args.no_launch_browser,
        use_cache=not args.no_cache,
    )
    rendered = doctor_report_json(checks) if args.json else doctor_report_text(checks, quiet=args.quiet)
    print(rendered, end="" if rendered.endswith("\n") else "\n")
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + ("" if rendered.endswith("\n") else "\n"), encoding="utf-8")
    ok = doctor_strict_passed(checks) if args.strict else doctor_passed(checks)
    raise SystemExit(0 if ok else 1)


def _run_fix_mode(args: "argparse.Namespace") -> None:
    launch = not args.no_launch_browser

    print("--- Before fix ---", flush=True)
    before_checks = collect_doctor_checks(launch_browser=launch, use_cache=False)
    print_doctor_report(before_checks, stream=sys.stdout, title="Doctor (before fix)")

    actions = auto_fix_checks(before_checks)
    if actions:
        print("\n--- Actions taken ---")
        for action in actions:
            print(f"  {action}")
    else:
        print("\n  No auto-fixable issues found.")

    print("\n--- After fix ---", flush=True)
    after_checks = collect_doctor_checks(launch_browser=launch, use_cache=False)
    print_doctor_report(after_checks, stream=sys.stdout, title="Doctor (after fix)")

    ok = doctor_strict_passed(after_checks) if args.strict else doctor_passed(after_checks)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
