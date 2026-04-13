#!/usr/bin/env python3
"""기존 시나리오에 @priority, @lifecycle 태그를 일괄 부여하는 일회성 스크립트."""
import re
from pathlib import Path

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios"

# 시나리오별 priority 분류 (파일명 패턴 → priority)
PRIORITY_MAP = {
    # P0: 주문 생성/결제/조회 크리티컬 패스
    "alpha_direct_buy_order_normal": "P0",
    "alpha_direct_buy_order_zigzin": "P0",
    "alpha_direct_buy_complete_normal": "P0",
    "alpha_direct_buy_complete_zigzin": "P0",
    "alpha_cart_order_normal": "P0",
    "alpha_cart_order_zigzin": "P0",
    "alpha_cart_checkout_complete_normal": "P0",
    "alpha_cart_checkout_complete_zigzin": "P0",
    "alpha_claim_cancel": "P0",
    "alpha_claim_cancel_by_order": "P0",
    "alpha_claim_return": "P0",
    "alpha_claim_return_by_order": "P0",
    "alpha_order_detail_view": "P0",
    "alpha_full_history_regression": "P0",
    # P1: CS 우회 가능한 기능
    "alpha_claim_exchange": "P1",
    "alpha_claim_exchange_by_order": "P1",
    "alpha_claim_exchange_input_option": "P1",
    "alpha_claim_exchange_policy_blocked": "P1",
    "alpha_claim_exchange_no_cost": "P1",
    "alpha_claim_exchange_policy_1p1": "P1",
    "alpha_claim_entry_check": "P1",
    "alpha_claim_cancel_unpaid": "P1",
    "alpha_claim_cancel_partial": "P1",
    "alpha_claim_return_partial": "P1",
    "alpha_claim_order_sheet": "P1",
    "alpha_cart_multi_item_single_order": "P1",
    "alpha_order_confirm": "P1",
    "alpha_relogin_recovery": "P1",
    "alpha_insufficient_points": "P1",
    "alpha_payment_blocked_modal": "P1",
    "alpha_payment_stuck": "P1",
    "alpha_shipping_tracking": "P1",
    "alpha_return_shipping_tracking": "P1",
    # P2: 정보 노출/UX
    "alpha_claim_completed_view": "P2",
    "alpha_claim_cancel_info": "P2",
    "alpha_claim_exchange_info": "P2",
    "alpha_claim_return_info": "P2",
    "alpha_shipping_defer": "P2",
    "alpha_shipping_delay_info": "P2",
}

META_TAG_RE = re.compile(r"^#\s*@(\w+):\s*(.+)$")


def add_tags(path: Path) -> bool:
    """Add @priority and @lifecycle tags if missing. Returns True if modified."""
    stem = path.stem
    priority = PRIORITY_MAP.get(stem)
    if not priority:
        return False  # 이미 태그가 있거나 매핑에 없는 파일

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    # 이미 @priority 태그가 있으면 스킵
    existing_tags = set()
    for line in lines:
        m = META_TAG_RE.match(line.strip())
        if m:
            existing_tags.add(m.group(1))

    if "priority" in existing_tags and "lifecycle" in existing_tags:
        return False

    # 마지막 메타 태그 줄 찾기
    last_meta_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and stripped.startswith("#") and META_TAG_RE.match(stripped):
            last_meta_idx = i
        elif stripped and not stripped.startswith("#"):
            break

    if last_meta_idx < 0:
        return False

    # 태그 삽입
    insert_lines = []
    if "priority" not in existing_tags:
        insert_lines.append(f"# @priority: {priority}\n")
    if "lifecycle" not in existing_tags:
        insert_lines.append("# @lifecycle: regression\n")

    if not insert_lines:
        return False

    for offset, tag_line in enumerate(insert_lines):
        lines.insert(last_meta_idx + 1 + offset, tag_line)

    path.write_text("".join(lines), encoding="utf-8")
    return True


def main():
    modified = 0
    skipped = 0
    for path in sorted(SCENARIOS_DIR.rglob("*.scn")):
        if add_tags(path):
            print(f"  [TAGGED] {path.relative_to(SCENARIOS_DIR.parent)}")
            modified += 1
        else:
            skipped += 1
    print(f"\nDone: {modified} tagged, {skipped} skipped")


if __name__ == "__main__":
    main()
