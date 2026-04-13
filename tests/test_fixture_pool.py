"""Tests for core.fixture_pool — order pool allocation/release."""

import json
import pytest
from pathlib import Path

from core.fixture_pool import OrderPool, OrderPoolError, analyze_demand, preflight_check


@pytest.fixture
def pool_dir(tmp_path):
    """Create a temporary pool with test data."""
    pool_file = tmp_path / "order_pool.json"
    pool_file.write_text(json.dumps({
        "배송완료": {
            "_description": "교환/반품용",
            "orders": ["ORD-001", "ORD-002", "ORD-003"]
        },
        "결제완료": {
            "_description": "취소용",
            "orders": ["ORD-100", "ORD-101"]
        },
        "주문확인중": {
            "_description": "빈 풀",
            "orders": []
        }
    }), encoding="utf-8")
    return pool_file


def test_pick_returns_order(pool_dir):
    pool = OrderPool(pool_dir)
    order = pool.pick("배송완료")
    assert order == "ORD-001"


def test_pick_sequential_no_duplicate(pool_dir):
    pool = OrderPool(pool_dir)
    o1 = pool.pick("배송완료")
    o2 = pool.pick("배송완료")
    assert o1 != o2
    assert o1 == "ORD-001"
    assert o2 == "ORD-002"


def test_pick_exhausted_raises(pool_dir):
    pool = OrderPool(pool_dir)
    pool.pick("결제완료")
    pool.pick("결제완료")
    with pytest.raises(OrderPoolError, match="No available orders"):
        pool.pick("결제완료")


def test_pick_empty_pool_raises(pool_dir):
    pool = OrderPool(pool_dir)
    with pytest.raises(OrderPoolError, match="No available orders"):
        pool.pick("주문확인중")


def test_pick_unknown_status_raises(pool_dir):
    pool = OrderPool(pool_dir)
    with pytest.raises(OrderPoolError, match="Unknown status"):
        pool.pick("존재하지않는상태")


def test_release_makes_order_available(pool_dir):
    pool = OrderPool(pool_dir)
    o1 = pool.pick("결제완료")
    o2 = pool.pick("결제완료")
    # Pool exhausted
    with pytest.raises(OrderPoolError):
        pool.pick("결제완료")
    # Release one
    pool.release("결제완료", o1)
    o3 = pool.pick("결제완료")
    assert o3 == o1


def test_release_all(pool_dir):
    pool = OrderPool(pool_dir)
    pool.pick("배송완료")
    pool.pick("배송완료")
    pool.pick("배송완료")
    with pytest.raises(OrderPoolError):
        pool.pick("배송완료")
    pool.release_all()
    o = pool.pick("배송완료")
    assert o == "ORD-001"


def test_status_report(pool_dir):
    pool = OrderPool(pool_dir)
    pool.pick("배송완료")
    st = pool.status()
    assert st["배송완료"]["total"] == 3
    assert st["배송완료"]["in_use"] == 1
    assert st["배송완료"]["available"] == 2
    assert st["결제완료"]["total"] == 2
    assert st["결제완료"]["available"] == 2


# --- Pre-flight check tests ---

@pytest.fixture
def scn_files(tmp_path):
    """Create test scenario files with PICK_ORDER_FROM_POOL."""
    s1 = tmp_path / "exchange.scn"
    s1.write_text("# @title: test\nPICK_ORDER_FROM_POOL 배송완료 ORDER_NO\nNAVIGATE https://example.com\n")
    s2 = tmp_path / "cancel.scn"
    s2.write_text("# @title: test\nPICK_ORDER_FROM_POOL 결제완료 ORDER_NO\nNAVIGATE https://example.com\n")
    s3 = tmp_path / "view.scn"
    s3.write_text("# @title: test\nNAVIGATE https://example.com\n")
    return [s1, s2, s3]


def test_analyze_demand(scn_files):
    demand = analyze_demand(scn_files)
    assert demand == {"배송완료": 1, "결제완료": 1}


def test_analyze_demand_no_pool_usage(tmp_path):
    s = tmp_path / "simple.scn"
    s.write_text("NAVIGATE https://example.com\n")
    demand = analyze_demand([s])
    assert demand == {}


def test_preflight_check_pass(pool_dir, scn_files):
    pool = OrderPool(pool_dir)
    ok, report = preflight_check(scn_files, pool)
    assert ok is True
    assert "PASS" in report


def test_preflight_check_fail(pool_dir, tmp_path):
    # Need 5 배송완료 but pool only has 3
    scns = []
    for i in range(5):
        s = tmp_path / f"exchange_{i}.scn"
        s.write_text(f"PICK_ORDER_FROM_POOL 배송완료 ORDER_NO\n")
        scns.append(s)
    pool = OrderPool(pool_dir)
    ok, report = preflight_check(scns, pool)
    assert ok is False
    assert "2건 추가 필요" in report


def test_preflight_check_no_pool_needed(pool_dir, tmp_path):
    s = tmp_path / "simple.scn"
    s.write_text("NAVIGATE https://example.com\n")
    pool = OrderPool(pool_dir)
    ok, report = preflight_check([s], pool)
    assert ok is True
    assert "불필요" in report
