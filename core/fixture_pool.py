"""Fixture order pool manager — 테스트 주문번호 풀 할당/반납.

시나리오 실행 시 `PICK_ORDER_FROM_POOL <status> [var_name]` 액션으로
특정 상태의 주문번호를 자동 할당받습니다.

병렬 실행 시 lock 파일로 충돌을 방지합니다.
"""

from __future__ import annotations

import json
import fcntl
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POOL_PATH = REPO_ROOT / "fixtures" / "order_pool.json"
LOCK_PATH = REPO_ROOT / "fixtures" / ".order_pool.lock"
ALLOCATION_PATH = REPO_ROOT / "fixtures" / ".order_pool_allocated.json"


class OrderPoolError(Exception):
    """주문풀 관련 에러."""


class OrderPool:
    """Thread/process-safe order pool with file-based locking."""

    def __init__(self, pool_path: Path | None = None):
        self.pool_path = pool_path or POOL_PATH
        self.lock_path = self.pool_path.parent / ".order_pool.lock"
        self.alloc_path = self.pool_path.parent / ".order_pool_allocated.json"

    def _load_pool(self) -> dict:
        if not self.pool_path.exists():
            raise OrderPoolError(f"Pool file not found: {self.pool_path}")
        return json.loads(self.pool_path.read_text(encoding="utf-8"))

    def _load_allocated(self) -> dict[str, list[str]]:
        if self.alloc_path.exists():
            return json.loads(self.alloc_path.read_text(encoding="utf-8"))
        return {}

    def _save_allocated(self, allocated: dict[str, list[str]]) -> None:
        self.alloc_path.write_text(
            json.dumps(allocated, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def pick(self, status: str, worker_id: str | None = None) -> str:
        """Pick an available order number for the given status.

        Args:
            status: 주문 상태 (e.g., "배송완료", "결제완료")
            worker_id: 워커 식별자 (병렬 실행 시 추적용)

        Returns:
            주문번호 문자열

        Raises:
            OrderPoolError: 풀이 비었거나 해당 상태가 없을 때
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "w") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            try:
                pool = self._load_pool()
                allocated = self._load_allocated()

                if status not in pool:
                    available_statuses = [
                        k for k in pool if not k.startswith("_")
                    ]
                    raise OrderPoolError(
                        f"Unknown status '{status}'. "
                        f"Available: {available_statuses}"
                    )

                status_data = pool[status]
                all_orders = status_data.get("orders", [])
                used = set(allocated.get(status, []))
                available = [o for o in all_orders if o not in used]

                if not available:
                    raise OrderPoolError(
                        f"No available orders for status '{status}'. "
                        f"Total: {len(all_orders)}, In-use: {len(used)}. "
                        f"Run 'python3 -m core.fixture_pool replenish' or "
                        f"add order numbers to fixtures/order_pool.json"
                    )

                picked = available[0]
                allocated.setdefault(status, []).append(picked)
                self._save_allocated(allocated)

                return picked
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)

    def release(self, status: str, order_no: str) -> None:
        """Release an order number back to the pool."""
        with open(self.lock_path, "w") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            try:
                allocated = self._load_allocated()
                if status in allocated and order_no in allocated[status]:
                    allocated[status].remove(order_no)
                    self._save_allocated(allocated)
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)

    def release_all(self) -> None:
        """Release all allocations (테스트 세션 종료 시 호출)."""
        if self.alloc_path.exists():
            self.alloc_path.unlink()

    def status(self) -> dict[str, dict]:
        """Return pool status summary."""
        pool = self._load_pool()
        allocated = self._load_allocated()
        result = {}
        for key, data in pool.items():
            if key.startswith("_"):
                continue
            all_orders = data.get("orders", [])
            used = allocated.get(key, [])
            result[key] = {
                "total": len(all_orders),
                "in_use": len(used),
                "available": len(all_orders) - len(used),
                "orders": all_orders,
                "allocated": used,
            }
        return result


def analyze_demand(scenario_paths: list[Path]) -> dict[str, int]:
    """시나리오 파일들에서 PICK_ORDER_FROM_POOL 사용량을 분석.

    Args:
        scenario_paths: .scn 파일 경로 리스트

    Returns:
        상태별 필요 주문 수량 dict (e.g., {"배송완료": 5, "결제완료": 2})
    """
    import re
    pick_re = re.compile(r"^PICK_ORDER_FROM_POOL\s+(\S+)", re.MULTILINE)
    demand: dict[str, int] = {}
    for path in scenario_paths:
        content = path.read_text(encoding="utf-8")
        for match in pick_re.finditer(content):
            status = match.group(1)
            demand[status] = demand.get(status, 0) + 1
    return demand


def analyze_demand_per_scenario(
    scenario_paths: list[Path],
    repo_root: Path | None = None,
) -> list[dict]:
    """시나리오별 사전조건(preconditions 메타데이터 + PICK_ORDER_FROM_POOL) 분석.

    Returns:
        [{"file": "...", "preconditions": {"order_status": "배송완료", "claim_type": "교환", ...}}, ...]
    """
    import re
    pick_re = re.compile(r"^PICK_ORDER_FROM_POOL\s+(\S+)", re.MULTILINE)
    results = []
    for path in scenario_paths:
        rel = str(path.relative_to(repo_root)) if repo_root else str(path)
        try:
            from executor.execute_scenario import parse_metadata
            meta = parse_metadata(path)
            preconditions = dict(meta.preconditions)
        except Exception:
            preconditions = {}

        # PICK_ORDER_FROM_POOL이 있으면 order_status 보강
        content = path.read_text(encoding="utf-8")
        for match in pick_re.finditer(content):
            status = match.group(1)
            if "order_status" not in preconditions:
                preconditions["order_status"] = status

        if preconditions:
            results.append({"file": rel, "preconditions": preconditions})
    return results


def preflight_check(
    scenario_paths: list[Path],
    pool: OrderPool | None = None,
) -> tuple[bool, str]:
    """실행 전 주문풀 수요 점검.

    Args:
        scenario_paths: 실행 예정 시나리오 파일 경로 리스트
        pool: OrderPool 인스턴스 (없으면 기본 생성)

    Returns:
        (ok, report): ok=True면 주문풀 충분, report=사람이 읽을 수 있는 점검 결과
    """
    if pool is None:
        pool = OrderPool()

    demand = analyze_demand(scenario_paths)
    if not demand:
        return True, "주문풀 불필요 (PICK_ORDER_FROM_POOL 미사용)"

    pool_status = pool.status()
    lines = ["[주문풀 사전 점검]", ""]
    all_ok = True

    for status, needed in sorted(demand.items()):
        info = pool_status.get(status)
        if info is None:
            lines.append(f"  {status}: 필요 {needed}건, 풀에 상태 미등록 ✗")
            all_ok = False
        else:
            available = info["available"]
            if available >= needed:
                lines.append(f"  {status}: 필요 {needed}건, 보유 {available}건 ✓")
            else:
                shortage = needed - available
                lines.append(f"  {status}: 필요 {needed}건, 보유 {available}건 ✗ → {shortage}건 추가 필요")
                all_ok = False

    lines.append("")
    if all_ok:
        lines.append("결과: PASS — 주문풀 충분")
    else:
        lines.append("결과: FAIL — fixtures/order_pool.json에 주문번호를 추가하세요")

    return all_ok, "\n".join(lines)


def main():
    """CLI: python3 -m core.fixture_pool [status|release-all|check <scn_files...>]"""
    import sys

    pool = OrderPool()

    if len(sys.argv) < 2 or sys.argv[1] == "status":
        st = pool.status()
        if not st:
            print("Pool is empty. Add orders to fixtures/order_pool.json")
            return
        for status, info in st.items():
            print(f"\n  [{status}]")
            print(f"    Total: {info['total']}, Available: {info['available']}, In-use: {info['in_use']}")
            if info["orders"]:
                print(f"    Orders: {', '.join(info['orders'])}")
            if info["allocated"]:
                print(f"    Allocated: {', '.join(info['allocated'])}")
        print()

    elif sys.argv[1] == "release-all":
        pool.release_all()
        print("All allocations released.")

    elif sys.argv[1] == "check":
        scn_files = [Path(p) for p in sys.argv[2:] if p.endswith(".scn")]
        if not scn_files:
            # default: all scenarios
            scn_dir = REPO_ROOT / "scenarios"
            scn_files = sorted(scn_dir.rglob("*.scn"))
        if not scn_files:
            print("No .scn files found")
            return
        ok, report = preflight_check(scn_files, pool)
        print(report)
        sys.exit(0 if ok else 1)

    else:
        print(f"Unknown command: {sys.argv[1]}")
        print("Usage: python3 -m core.fixture_pool [status|release-all|check [scn_files...]]")


if __name__ == "__main__":
    main()
