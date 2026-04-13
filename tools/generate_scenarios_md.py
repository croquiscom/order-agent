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
    all_metas: list[tuple[str, object]] = []
    for path in scn_files:
        meta = parse_metadata(path)
        rel = str(path.relative_to(REPO_ROOT))
        tier = meta.tier if meta.tier in by_tier else "full"
        by_tier[tier].append((rel, meta))
        all_metas.append((rel, meta))

    lines = [
        "# Scenarios",
        "",
        "> Auto-generated from `.scn` file headers. Do not edit manually.",
        "> Run `python3 -m tools.generate_scenarios_md` to regenerate.",
        "",
    ]

    # ── Tier별 시나리오 목록 ──
    tier_labels = {"smoke": "Smoke (매 배포)", "regression": "Regression (영향 범위)", "full": "Full (전체/정기)"}

    for tier in ("smoke", "regression", "full"):
        items = by_tier[tier]
        lines.append(f"## {tier_labels[tier]} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_없음_")
            lines.append("")
            continue
        lines.append("| 시나리오 | 설명 | 영역 | 우선순위 | 페이지 |")
        lines.append("|---------|------|------|---------|--------|")
        for rel, meta in items:
            area_str = ", ".join(meta.area) if meta.area else "-"
            pages_str = ", ".join(meta.pages) if meta.pages else "-"
            title = meta.title or "-"
            priority = meta.priority or "-"
            lines.append(f"| `{rel}` | {title} | {area_str} | {priority} | {pages_str} |")
        lines.append("")

    total = sum(len(v) for v in by_tier.values())
    lines.append(f"**Total: {total} scenarios**")
    lines.append("")

    # ── 과제(Task)별 커버리지 ──
    by_task: dict[str, list[tuple[str, object]]] = {}
    for rel, meta in all_metas:
        task = meta.task
        if task:
            by_task.setdefault(task, []).append((rel, meta))

    if by_task:
        lines.append("---")
        lines.append("")
        lines.append("## 과제별 커버리지")
        lines.append("")
        for task in sorted(by_task.keys()):
            items = by_task[task]
            p0 = sum(1 for _, m in items if m.priority == "P0")
            p1 = sum(1 for _, m in items if m.priority == "P1")
            p2 = sum(1 for _, m in items if m.priority == "P2")
            lines.append(f"### {task} ({len(items)}개)")
            lines.append("")
            lines.append(f"P0: {p0} | P1: {p1} | P2: {p2}")
            lines.append("")
            lines.append("| 시나리오 | 설명 | 우선순위 | 상태 |")
            lines.append("|---------|------|---------|------|")
            for rel, meta in items:
                title = meta.title or "-"
                priority = meta.priority or "-"
                lifecycle = meta.lifecycle or "-"
                lines.append(f"| `{rel}` | {title} | {priority} | {lifecycle} |")
            lines.append("")

    # ── 영역(Area)별 커버리지 ──
    by_area: dict[str, list[tuple[str, object]]] = {}
    for rel, meta in all_metas:
        for area in meta.area:
            by_area.setdefault(area, []).append((rel, meta))

    if by_area:
        lines.append("---")
        lines.append("")
        lines.append("## 영역별 커버리지")
        lines.append("")
        lines.append("| 영역 | 시나리오 수 | P0 | P1 | P2 |")
        lines.append("|------|-----------|----|----|-----|")
        for area in sorted(by_area.keys()):
            items = by_area[area]
            p0 = sum(1 for _, m in items if m.priority == "P0")
            p1 = sum(1 for _, m in items if m.priority == "P1")
            p2 = sum(1 for _, m in items if m.priority == "P2")
            lines.append(f"| {area} | {len(items)} | {p0} | {p1} | {p2} |")
        lines.append("")

    # ── 중복 경고 (동일 area+pages 조합) ──
    from collections import Counter
    area_pages_counter: Counter[str] = Counter()
    area_pages_map: dict[str, list[str]] = {}
    for rel, meta in all_metas:
        if meta.area and meta.pages:
            key = "|".join(sorted(meta.area)) + ":" + "|".join(sorted(meta.pages))
            area_pages_counter[key] += 1
            area_pages_map.setdefault(key, []).append(rel)

    duplicates = {k: v for k, v in area_pages_map.items() if len(v) > 1}
    if duplicates:
        lines.append("---")
        lines.append("")
        lines.append("## ⚠ 중복 경고")
        lines.append("")
        lines.append("동일한 `@area` + `@pages` 조합을 가진 시나리오가 발견되었습니다.")
        lines.append("의도적 중복이 아니면 통합을 검토하세요.")
        lines.append("")
        for key, files in sorted(duplicates.items()):
            parts = key.split(":")
            lines.append(f"- **{parts[0]}** / `{parts[1]}` ({len(files)}개)")
            for f in files:
                lines.append(f"  - `{f}`")
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
