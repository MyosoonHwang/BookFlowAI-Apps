"""decision-svc cascade 정밀화 단위 테스트.

FR-A5.1 (Stage 1 effective available):
  effective_available = on_hand - reserved_qty - incoming_qty - expected_demand_14d

incoming_qty: pending_orders APPROVED 중 target_location_id == self · executed_at IS NULL 합
expected_demand_14d: forecast_cache 의 향후 14일 SUM(predicted_demand)

Stage 1 source picker 가 effective_available >= qty 인 location 만 선택해야 함.
"""
import pytest

from src.routes.decision import _effective_available


# ─── pure formula tests (FR-A5.1 정의) ──────────────────────────────────
def test_effective_available_basic():
    """on_hand 100, reserved 20, incoming 30, demand 15 → 35"""
    assert _effective_available(on_hand=100, reserved_qty=20, incoming_qty=30, expected_demand=15) == 35


def test_effective_available_no_reserve_no_incoming_no_demand():
    """only on_hand → on_hand 그대로"""
    assert _effective_available(on_hand=50, reserved_qty=0, incoming_qty=0, expected_demand=0) == 50


def test_effective_available_can_go_negative():
    """예상수요 > on_hand → 음수 (부족 표시 · 의사결정 입력으로 사용)"""
    assert _effective_available(on_hand=50, reserved_qty=0, incoming_qty=0, expected_demand=100) == -50


def test_effective_available_negative_demand_clamped_to_zero():
    """예상수요 음수 (이상치 / NULL) → 0 으로 clamp · on_hand 만큼 사용 가능"""
    assert _effective_available(on_hand=50, reserved_qty=0, incoming_qty=0, expected_demand=-5) == 50


def test_effective_available_all_components():
    """100 - 10 - 5 - 30 = 55"""
    assert _effective_available(on_hand=100, reserved_qty=10, incoming_qty=5, expected_demand=30) == 55


def test_effective_available_zero_when_balanced():
    """100 - 100 - 0 - 0 = 0"""
    assert _effective_available(on_hand=100, reserved_qty=100, incoming_qty=0, expected_demand=0) == 0


def test_effective_available_handles_none_reserved_as_zero():
    """reserved_qty None (DB NULL) → 0"""
    assert _effective_available(on_hand=50, reserved_qty=None, incoming_qty=0, expected_demand=0) == 50


def test_effective_available_handles_none_incoming_demand():
    """incoming_qty / expected_demand None → 0"""
    assert _effective_available(on_hand=50, reserved_qty=10, incoming_qty=None, expected_demand=None) == 40
