"""pydantic models matching V3 pending_orders.

V3 columns: order_id · order_type · isbn13 · source_location_id · target_location_id
            qty · est_lead_time_hours · est_cost · forecast_rationale (jsonb)
            urgency_level · auto_execute_eligible · stock_days_remaining
            demand_confidence_ratio · demand_cv · status · execution_reason
            reject_reason · reject_count · created_at · approved_at · executed_at
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


OrderType = Literal["REBALANCE", "WH_TRANSFER", "PUBLISHER_ORDER"]
Urgency = Literal["NORMAL", "URGENT", "CRITICAL"]
OrderStatus = Literal["PENDING", "APPROVED", "REJECTED", "EXECUTED", "CANCELLED"]


class DecideRequest(BaseModel):
    order_type: OrderType
    isbn13: str = Field(min_length=13, max_length=13)
    source_location_id: int | None = None
    target_location_id: int | None = None
    qty: int = Field(gt=0)
    urgency_level: Urgency = "NORMAL"
    auto_execute_eligible: bool = False
    forecast_rationale: dict | None = None


class DecideResponse(BaseModel):
    order_id: UUID
    status: OrderStatus
    created_at: datetime


class PendingOrder(BaseModel):
    """Response model - order_type kept as str so seed data with legacy types ('MANUAL') passes."""
    order_id: UUID
    order_type: str
    isbn13: str
    source_location_id: int | None
    target_location_id: int | None
    qty: int
    urgency_level: str
    status: str
    created_at: datetime


class PendingOrdersResponse(BaseModel):
    items: list[PendingOrder]
