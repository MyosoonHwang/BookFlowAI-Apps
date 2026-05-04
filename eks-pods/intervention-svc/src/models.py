"""pydantic models matching V3 order_approvals + returns."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ApprovalSide = Literal["SOURCE", "TARGET", "FINAL"]
Decision = Literal["APPROVED", "REJECTED"]


class QueueItem(BaseModel):
    """A pending_orders row that needs approval (queue view for HQ Approval / WH Approve pages).

    forecast_rationale: decision-svc 가 채운 의사결정 근거 (Stage 1 effective_available 또는
    Stage 2 partner_surplus 등). UI 가 승인 판단 시 참고 자료로 표시 (UX-4 / FR-A5.6).
    """
    order_id: UUID
    order_type: str
    isbn13: str
    source_location_id: int | None
    target_location_id: int | None
    qty: int
    urgency_level: str
    auto_execute_eligible: bool
    status: str
    created_at: datetime
    forecast_rationale: dict | None = None


class QueueResponse(BaseModel):
    items: list[QueueItem]


class ApproveRequest(BaseModel):
    order_id: UUID
    approval_side: ApprovalSide = "FINAL"  # FINAL = single-stage HQ approval; SOURCE/TARGET = 2-stage WH transfer
    note: str | None = None


class RejectRequest(BaseModel):
    order_id: UUID
    approval_side: ApprovalSide = "FINAL"
    reject_reason: str = Field(min_length=1, max_length=50)


class ApprovalResponse(BaseModel):
    approval_id: UUID
    order_id: UUID
    decision: Decision
    decided_at: datetime


class ReturnApproveRequest(BaseModel):
    return_id: UUID
    note: str | None = None


class ReturnApproveResponse(BaseModel):
    return_id: UUID
    status: str
    hq_approved_at: datetime
