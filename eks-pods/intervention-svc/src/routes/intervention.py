"""intervention routes:
- GET /intervention/queue          - PENDING approval queue view (used by dashboard fan-in)
- POST /intervention/approve       - approve a pending_order (writes order_approvals)
- POST /intervention/reject        - reject
- POST /intervention/returns/approve - approve a return

V3 schema: pending_orders + order_approvals + returns + audit_log.
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import AuthContext, require_auth
from ..db import db_conn, redis_client
from ..models import (
    ApprovalResponse,
    ApproveRequest,
    QueueItem,
    QueueResponse,
    RejectRequest,
    ReturnApproveRequest,
    ReturnApproveResponse,
)

router = APIRouter(prefix="/intervention", tags=["intervention"])

REDIS_CHANNEL_ORDER = "order.pending"


@router.get("/queue", response_model=QueueResponse)
def queue(
    _: AuthContext = Depends(require_auth),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Joins pending_orders + order_approvals to filter rows still needing approval."""
    sql = """
        SELECT po.order_id, po.order_type, po.isbn13,
               po.source_location_id, po.target_location_id, po.qty,
               po.urgency_level, po.auto_execute_eligible, po.status, po.created_at
          FROM pending_orders po
         WHERE po.status = 'PENDING'
         ORDER BY po.urgency_level DESC, po.created_at ASC
         LIMIT %s
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()

    items = [
        QueueItem(
            order_id=r[0], order_type=r[1], isbn13=r[2],
            source_location_id=r[3], target_location_id=r[4],
            qty=r[5], urgency_level=r[6], auto_execute_eligible=r[7],
            status=r[8], created_at=r[9],
        )
        for r in rows
    ]
    return QueueResponse(items=items)


def _record_approval(conn, order_id: str, ctx: AuthContext, side: str, decision: str, reject_reason: str | None) -> tuple[str, datetime]:
    """Insert order_approvals + bump pending_orders.status. Returns (approval_id, decided_at)."""
    approval_id = str(uuid4())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO order_approvals
            (approval_id, order_id, approver_id, approver_role, approver_wh_id,
             approval_side, decision, reject_reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (order_id, approval_side) DO UPDATE
        SET decision = EXCLUDED.decision,
            reject_reason = EXCLUDED.reject_reason,
            decided_at = NOW()
        RETURNING approval_id, decided_at
        """,
        (approval_id, order_id, ctx.user_id, ctx.role, ctx.scope_wh_id,
         side, decision, reject_reason),
    )
    aid, decided_at = cur.fetchone()

    # bump pending_orders status. For 2-stage WH transfer require both SOURCE+TARGET APPROVED.
    if decision == "APPROVED" and side == "FINAL":
        cur.execute(
            "UPDATE pending_orders SET status = 'APPROVED', approved_at = NOW() WHERE order_id = %s",
            (order_id,),
        )
    elif decision == "APPROVED" and side in ("SOURCE", "TARGET"):
        cur.execute(
            """
            UPDATE pending_orders SET status = 'APPROVED', approved_at = NOW()
             WHERE order_id = %s
               AND (SELECT COUNT(*) FROM order_approvals
                     WHERE order_id = %s AND decision = 'APPROVED'
                       AND approval_side IN ('SOURCE', 'TARGET')) >= 2
            """,
            (order_id, order_id),
        )
    elif decision == "REJECTED":
        cur.execute(
            "UPDATE pending_orders SET status = 'REJECTED', reject_reason = %s, reject_count = reject_count + 1 WHERE order_id = %s",
            (reject_reason, order_id),
        )

    cur.execute(
        """
        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, after_state)
        VALUES ('user', %s, 'intervention.%s', 'pending_orders', %s, %s)
        """,
        (ctx.user_id, decision.lower(), order_id, json.dumps({
            "approval_id": str(aid), "side": side, "decision": decision, "reject_reason": reject_reason,
        })),
    )
    return str(aid), decided_at


@router.post("/approve", response_model=ApprovalResponse)
def approve(req: ApproveRequest, ctx: AuthContext = Depends(require_auth)):
    if ctx.role not in ("hq-admin", "wh-manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="hq-admin or wh-manager only")

    with db_conn() as conn:
        aid, decided_at = _record_approval(conn, str(req.order_id), ctx, req.approval_side, "APPROVED", None)
        conn.commit()

    return ApprovalResponse(approval_id=aid, order_id=req.order_id, decision="APPROVED", decided_at=decided_at)


@router.post("/reject", response_model=ApprovalResponse)
def reject(req: RejectRequest, ctx: AuthContext = Depends(require_auth)):
    if ctx.role not in ("hq-admin", "wh-manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="hq-admin or wh-manager only")

    with db_conn() as conn:
        aid, decided_at = _record_approval(conn, str(req.order_id), ctx, req.approval_side, "REJECTED", req.reject_reason)
        conn.commit()

    return ApprovalResponse(approval_id=aid, order_id=req.order_id, decision="REJECTED", decided_at=decided_at)


@router.post("/returns/approve", response_model=ReturnApproveResponse)
def returns_approve(req: ReturnApproveRequest, ctx: AuthContext = Depends(require_auth)):
    if ctx.role != "hq-admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="hq-admin only")

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE returns SET status = 'APPROVED', hq_approved_at = NOW()
                 WHERE return_id = %s AND status = 'PENDING'
                RETURNING status, hq_approved_at
                """,
                (str(req.return_id),),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="return not found or already processed")
            cur.execute(
                """
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, after_state)
                VALUES ('user', %s, 'intervention.returns.approve', 'returns', %s, %s)
                """,
                (ctx.user_id, str(req.return_id), json.dumps({"note": req.note})),
            )
        conn.commit()

    return ReturnApproveResponse(return_id=req.return_id, status=row[0], hq_approved_at=row[1])
