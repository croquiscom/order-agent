"""Generate docs/scenarios.md from .scn file @tag headers.

Usage:
    python3 -m tools.generate_scenarios_md [--check]

--check: verify docs/scenarios.md is up-to-date without overwriting (exit 1 if stale).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from executor.execute_scenario import parse_metadata

OUTPUT_PATH = REPO_ROOT / "docs" / "scenarios.md"


def generate() -> str:
    scenarios_dir = REPO_ROOT / "scenarios"
    scn_files = sorted(scenarios_dir.rglob("*.scn"))

    by_tier: dict[str, list[tuple[str, object]]] = {"smoke": [], "regression": [], "full": []}
    for path in scn_files:
        meta = parse_metadata(path)
        rel = str(path.relative_to(REPO_ROOT))
        tier = meta.tier if meta.tier in by_tier else "full"
        by_tier[tier].append((rel, meta))

    lines = [
        "# Scenarios",
        "",
        "> Auto-generated from `.scn` file headers. Do not edit manually.",
        "> Run `python3 -m tools.generate_scenarios_md` to regenerate.",
        "",
    ]

    tier_labels = {"smoke": "Smoke (매 배포)", "regression": "Regression (영향 범위)", "full": "Full (전체/정기)"}

    for tier in ("smoke", "regression", "full"):
        items = by_tier[tier]
        lines.append(f"## {tier_labels[tier]} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_없음_")
            lines.append("")
            continue
        lines.append("| 시나리오 | 설명 | 영역 | 페이지 |")
        lines.append("|---------|------|------|--------|")
        for rel, meta in items:
            area_str = ", ".join(meta.area) if meta.area else "-"
            pages_str = ", ".join(meta.pages) if meta.pages else "-"
            title = meta.title or "-"
            lines.append(f"| `{rel}` | {title} | {area_str} | {pages_str} |")
        lines.append("")

    total = sum(len(v) for v in by_tier.values())
    lines.append(f"**Total: {total} scenarios**")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    content = generate()
    check_mode = "--check" in sys.argv

    if check_mode:
        if OUTPUT_PATH.exists() and OUTPUT_PATH.read_text(encoding="utf-8") == content:
            print(f"OK: {OUTPUT_PATH.relative_to(REPO_ROOT)} is up-to-date.")
            return 0
        else:
            print(f"STALE: {OUTPUT_PATH.relative_to(REPO_ROOT)} needs regeneration.")
            print("Run: python3 -m tools.generate_scenarios_md")
            return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
