#!/usr/bin/env python3
"""시나리오 커버리지 맵 자동 생성기.

.scn 파일의 메타데이터와 사용된 액션을 분석하여 커버리지 리포트를 생성합니다.
docs/order_flow_map.md를 자동 갱신하거나, 터미널/JSON 리포트를 출력합니다.

Usage:
    # 터미널 요약 리포트
    python3 scripts/generate_scenario_map.py

    # JSON 리포트 (CI 연동용)
    python3 scripts/generate_scenario_map.py --json

    # docs/order_flow_map.md 자동 갱신
    python3 scripts/generate_scenario_map.py --update-doc

    # 미커버 액션만 표시
    python3 scripts/generate_scenario_map.py --gaps-only
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from executor.execute_scenario import ALLOWED_ACTIONS, parse_metadata

SCENARIOS_DIR = REPO_ROOT / "scenarios"
DOC_PATH = REPO_ROOT / "docs" / "order_flow_map.md"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ScenarioInfo:
    file: str
    title: str
    tier: str
    area: list[str]
    pages: list[str]
    actions_used: list[str]
    action_counts: dict[str, int]
    step_count: int


@dataclass
class CoverageReport:
    generated_at: str
    total_scenarios: int
    by_category: dict[str, list[dict]]
    by_area: dict[str, int]
    by_tier: dict[str, int]
    action_coverage: dict[str, list[str]]  # action -> list of scenario files
    uncovered_actions: list[str]
    area_matrix: dict[str, dict[str, int]]  # area -> {action -> count}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def extract_actions(path: Path) -> tuple[list[str], dict[str, int], int]:
    """Parse a .scn file and return (actions_list, action_counts, step_count)."""
    actions = []
    counts: dict[str, int] = Counter()
    steps = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                parts = shlex.split(stripped)
            except ValueError:
                parts = stripped.split()
            if not parts:
                continue
            action = parts[0].upper()
            if action in ALLOWED_ACTIONS:
                actions.append(action)
                counts[action] += 1
                steps += 1
    return actions, dict(counts), steps


def collect_all_scenarios() -> list[ScenarioInfo]:
    """Collect metadata and action usage from all .scn files."""
    scenarios = []
    for path in sorted(SCENARIOS_DIR.rglob("*.scn")):
        meta = parse_metadata(path)
        actions, counts, steps = extract_actions(path)
        rel = str(path.relative_to(REPO_ROOT))
        scenarios.append(ScenarioInfo(
            file=rel,
            title=meta.title or path.stem,
            tier=meta.tier or "unknown",
            area=meta.area or [],
            pages=meta.pages or [],
            actions_used=sorted(set(actions)),
            action_counts=counts,
            step_count=steps,
        ))
    return scenarios


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

CATEGORY_RULES = [
    ("주문 — 바로구매", lambda f: "zigzag" in f and "direct_buy" in f),
    ("주문 — 장바구니", lambda f: "zigzag" in f and "cart" in f),
    ("클레임 — 취소", lambda f: "zigzag" in f and "claim_cancel" in f),
    ("클레임 — 반품", lambda f: "zigzag" in f and ("claim_return" in f or "return_shipping" in f)),
    ("클레임 — 교환", lambda f: "zigzag" in f and "claim_exchange" in f),
    ("클레임 — 공통", lambda f: "zigzag" in f and ("claim_entry" in f or "claim_completed" in f or "claim_order" in f)),
    ("조회/배송/확정", lambda f: "zigzag" in f and any(k in f for k in ("order_detail", "order_confirm", "shipping"))),
    ("결제/안정성", lambda f: "zigzag" in f and any(k in f for k in ("payment", "insufficient", "relogin", "full_history"))),
    ("Naver", lambda f: "naver" in f),
    ("AWS/Grafana", lambda f: "aws" in f or "grafana" in f),
]


def categorize(file: str) -> str:
    for name, rule in CATEGORY_RULES:
        if rule(file):
            return name
    return "기타"


def build_report(scenarios: list[ScenarioInfo]) -> CoverageReport:
    # Category grouping
    by_category: dict[str, list[dict]] = defaultdict(list)
    for s in scenarios:
        cat = categorize(s.file)
        by_category[cat].append({
            "file": s.file,
            "title": s.title,
            "tier": s.tier,
            "area": s.area,
            "steps": s.step_count,
            "actions": s.actions_used,
        })

    # Area counts
    area_counter: Counter = Counter()
    for s in scenarios:
        for a in s.area:
            area_counter[a] += 1

    # Tier counts
    tier_counter: Counter = Counter()
    for s in scenarios:
        tier_counter[s.tier] += 1

    # Action coverage
    action_coverage: dict[str, list[str]] = defaultdict(list)
    for s in scenarios:
        for action in s.actions_used:
            action_coverage[action].append(s.file)

    uncovered = sorted(a for a in ALLOWED_ACTIONS if a not in action_coverage)

    # Area × Action matrix
    area_matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in scenarios:
        for a in s.area:
            for action, count in s.action_counts.items():
                area_matrix[a][action] += count

    return CoverageReport(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_scenarios=len(scenarios),
        by_category=dict(by_category),
        by_area=dict(area_counter),
        by_tier=dict(tier_counter),
        action_coverage=dict(action_coverage),
        uncovered_actions=uncovered,
        area_matrix={k: dict(v) for k, v in area_matrix.items()},
    )


# ---------------------------------------------------------------------------
# Output: Terminal
# ---------------------------------------------------------------------------

def print_terminal(report: CoverageReport, gaps_only: bool = False) -> None:
    print(f"\n{'='*60}")
    print(f"  시나리오 커버리지 리포트 — {report.generated_at}")
    print(f"{'='*60}\n")

    if not gaps_only:
        # Category summary
        print("## 카테고리별 시나리오 수\n")
        for cat in [r[0] for r in CATEGORY_RULES] + ["기타"]:
            items = report.by_category.get(cat, [])
            if items:
                print(f"  {cat}: {len(items)}개")
                for item in items:
                    tier_mark = {"smoke": "S", "regression": "R", "full": "F"}.get(item["tier"], "?")
                    print(f"    [{tier_mark}] {item['title']}")
        print(f"\n  총 {report.total_scenarios}개\n")

        # Tier distribution
        print("## 티어 분포\n")
        for tier in ["smoke", "regression", "full", "unknown"]:
            count = report.by_tier.get(tier, 0)
            if count:
                print(f"  {tier}: {count}개")

        # Area distribution
        print("\n## 영역 분포\n")
        for area, count in sorted(report.by_area.items(), key=lambda x: -x[1]):
            print(f"  {area}: {count}개")

    # Action coverage
    total_actions = len(ALLOWED_ACTIONS)
    covered_actions = total_actions - len(report.uncovered_actions)
    pct = covered_actions / total_actions * 100 if total_actions else 0

    print(f"\n## 액션 커버리지: {covered_actions}/{total_actions} ({pct:.0f}%)\n")

    if not gaps_only:
        print("  커버된 액션:")
        for action in sorted(report.action_coverage.keys()):
            files = report.action_coverage[action]
            print(f"    {action}: {len(files)}개 시나리오")

    if report.uncovered_actions:
        print(f"\n  ⚠ 미커버 액션 ({len(report.uncovered_actions)}개):")
        for action in report.uncovered_actions:
            print(f"    ✗ {action}")
    else:
        print("\n  ✓ 모든 액션이 1개 이상의 시나리오에서 사용됨")

    print()


# ---------------------------------------------------------------------------
# Output: JSON
# ---------------------------------------------------------------------------

def print_json(report: CoverageReport) -> None:
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Output: Markdown doc update
# ---------------------------------------------------------------------------

AUTO_SECTION_START = "<!-- AUTO-GENERATED: scenario-map-start -->"
AUTO_SECTION_END = "<!-- AUTO-GENERATED: scenario-map-end -->"


def generate_markdown(report: CoverageReport) -> str:
    lines = []
    lines.append(f"\n> 자동 생성: `python3 scripts/generate_scenario_map.py --update-doc` | {report.generated_at}\n")

    # Category tables
    lines.append("### 카테고리별 시나리오 목록\n")
    for cat in [r[0] for r in CATEGORY_RULES] + ["기타"]:
        items = report.by_category.get(cat, [])
        if not items:
            continue
        lines.append(f"**{cat}** ({len(items)}개)\n")
        lines.append("| # | 파일 | 제목 | 티어 | 영역 | 스텝 |")
        lines.append("|---|------|------|------|------|------|")
        for i, item in enumerate(items, 1):
            fname = Path(item["file"]).name
            areas = ", ".join(item["area"])
            lines.append(f"| {i} | `{fname}` | {item['title']} | {item['tier']} | {areas} | {item['steps']} |")
        lines.append("")

    # Summary stats
    lines.append("### 커버리지 요약\n")
    total_actions = len(ALLOWED_ACTIONS)
    covered = total_actions - len(report.uncovered_actions)
    pct = covered / total_actions * 100 if total_actions else 0

    lines.append(f"| 지표 | 값 |")
    lines.append(f"|------|-----|")
    lines.append(f"| 총 시나리오 | {report.total_scenarios}개 |")
    lines.append(f"| 액션 커버리지 | {covered}/{total_actions} ({pct:.0f}%) |")
    for tier in ["smoke", "regression", "full"]:
        count = report.by_tier.get(tier, 0)
        if count:
            lines.append(f"| {tier} 티어 | {count}개 |")
    lines.append("")

    # Uncovered actions
    if report.uncovered_actions:
        lines.append("### 미커버 액션\n")
        lines.append("| 액션 | 설명 |")
        lines.append("|------|------|")
        for action in report.uncovered_actions:
            lines.append(f"| `{action}` | 시나리오 없음 |")
        lines.append("")

    # Area matrix
    lines.append("### 영역별 액션 사용 히트맵\n")
    areas_sorted = sorted(report.area_matrix.keys())
    # Pick top actions by total usage
    action_totals: Counter = Counter()
    for area_data in report.area_matrix.values():
        for action, count in area_data.items():
            action_totals[action] += count
    top_actions = [a for a, _ in action_totals.most_common(12)]

    if areas_sorted and top_actions:
        header = "| 영역 | " + " | ".join(f"`{a[:20]}`" for a in top_actions) + " |"
        sep = "|------|" + "|".join("------" for _ in top_actions) + "|"
        lines.append(header)
        lines.append(sep)
        for area in areas_sorted:
            vals = []
            for action in top_actions:
                c = report.area_matrix.get(area, {}).get(action, 0)
                vals.append(str(c) if c else "-")
            lines.append(f"| {area} | " + " | ".join(vals) + " |")
        lines.append("")

    return "\n".join(lines)


def update_doc(report: CoverageReport) -> bool:
    """Update the auto-generated section in docs/order_flow_map.md."""
    md_content = generate_markdown(report)

    if DOC_PATH.exists():
        existing = DOC_PATH.read_text(encoding="utf-8")
        start_idx = existing.find(AUTO_SECTION_START)
        end_idx = existing.find(AUTO_SECTION_END)

        if start_idx != -1 and end_idx != -1:
            # Replace existing auto-generated section
            new_content = (
                existing[:start_idx]
                + AUTO_SECTION_START
                + "\n"
                + md_content
                + "\n"
                + AUTO_SECTION_END
                + existing[end_idx + len(AUTO_SECTION_END):]
            )
            DOC_PATH.write_text(new_content, encoding="utf-8")
            print(f"✓ {DOC_PATH} 자동생성 섹션 갱신 완료")
            return True

    # Append section at the end
    append_content = f"\n\n{AUTO_SECTION_START}\n{md_content}\n{AUTO_SECTION_END}\n"
    if DOC_PATH.exists():
        with open(DOC_PATH, "a", encoding="utf-8") as f:
            f.write(append_content)
    else:
        DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOC_PATH.write_text(
            "# 주문 플로우 전체 맵 — 시나리오 커버리지 매트릭스\n" + append_content,
            encoding="utf-8",
        )
    print(f"✓ {DOC_PATH} 에 자동생성 섹션 추가 완료")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="시나리오 커버리지 맵 생성기")
    parser.add_argument("--json", action="store_true", help="JSON 리포트 출력")
    parser.add_argument("--update-doc", action="store_true", help="docs/order_flow_map.md 자동 갱신")
    parser.add_argument("--gaps-only", action="store_true", help="미커버 항목만 표시")
    args = parser.parse_args()

    scenarios = collect_all_scenarios()
    report = build_report(scenarios)

    if args.json:
        print_json(report)
    elif args.update_doc:
        update_doc(report)
    else:
        print_terminal(report, gaps_only=args.gaps_only)


if __name__ == "__main__":
    main()
