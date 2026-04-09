"""Lint .scn files for required @tag metadata headers.

Usage:
    python3 -m tools.lint_scenario_headers [scenarios_dir]

Exit code 0 = all pass, 1 = lint errors found.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from executor.execute_scenario import parse_metadata

REQUIRED_TAGS = {"title", "tier", "area"}
VALID_TIERS = {"smoke", "regression", "full"}


def lint_file(path: Path) -> list[str]:
    errors: list[str] = []
    meta = parse_metadata(path)

    if not meta.title:
        errors.append("missing @title")
    if not meta.tier:
        errors.append("missing @tier")
    elif meta.tier not in VALID_TIERS:
        errors.append(f"invalid @tier '{meta.tier}' (must be: {', '.join(sorted(VALID_TIERS))})")
    if not meta.area:
        errors.append("missing @area")

    return errors


def main(scenarios_dir: Path | None = None) -> int:
    if scenarios_dir is None:
        scenarios_dir = REPO_ROOT / "scenarios"

    scn_files = sorted(scenarios_dir.rglob("*.scn"))
    if not scn_files:
        print(f"No .scn files found in {scenarios_dir}")
        return 1

    total_errors = 0
    for path in scn_files:
        rel = path.relative_to(REPO_ROOT)
        errors = lint_file(path)
        if errors:
            total_errors += len(errors)
            for err in errors:
                print(f"  FAIL  {rel}: {err}")
        else:
            print(f"  OK    {rel}")

    print()
    if total_errors:
        print(f"Found {total_errors} error(s) in {len(scn_files)} files.")
        return 1
    else:
        print(f"All {len(scn_files)} files passed.")
        return 0


if __name__ == "__main__":
    dir_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(main(dir_arg))
