"""decision routes: POST /decide · GET /pending-orders.

Phase 2 stub - real 3-stage logic (rebalance -> WH transfer -> EOQ order)
implemented in Phase 3 with forecast-svc + inventory data inputs.
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import AuthContext, require_auth
from ..db import db_conn, redis_client
from ..models import (
    DecideRequest,
    DecideResponse,
    PendingOrder,
    PendingOrdersResponse,
)

router = APIRouter(prefix="/decision", tags=["decision"])

REDIS_CHANNEL_ORDER = "order.pending"


@router.post("/decide", response_model=DecideResponse)
def decide(req: DecideRequest, ctx: AuthContext = Depends(require_auth)):
    """Create a pending_orders row + Redis publish (notification-svc fan-out)."""
    if ctx.role not in ("hq-admin", "wh-manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="hq-admin or wh-manager only")

    order_id = uuid4()
    sql = """
        INSERT INTO pending_orders
            (order_id, order_type, isbn13, source_location_id, target_location_id,
             qty, urgency_level, auto_execute_eligible, forecast_rationale, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
        RETURNING created_at
    """
    audit_sql = """
        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, after_state)
        VALUES ('user', %s, 'decision.create', 'pending_orders', %s, %s)
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                str(order_id), req.order_type, req.isbn13,
                req.source_location_id, req.target_location_id, req.qty,
                req.urgency_level, req.auto_execute_eligible,
                json.dumps(req.forecast_rationale) if req.forecast_rationale else None,
            ))
            created_at = cur.fetchone()[0]
            cur.execute(audit_sql, (
                ctx.user_id,
                str(order_id),
                json.dumps({
                    "order_type": req.order_type,
                    "isbn13": req.isbn13,
                    "qty": req.qty,
                    "urgency": req.urgency_level,
                }),
            ))
        conn.commit()

    redis_client().publish(REDIS_CHANNEL_ORDER, json.dumps({
        "order_id": str(order_id),
        "isbn13": req.isbn13,
        "qty": req.qty,
        "urgency_level": req.urgency_level,
    }))

    return DecideResponse(order_id=order_id, status="PENDING", created_at=created_at)


@router.get("/pending-orders", response_model=PendingOrdersResponse)
def list_pending(
    _: AuthContext = Depends(require_auth),
    limit: int = Query(default=50, ge=1, le=500),
):
    sql = """
        SELECT order_id, order_type, isbn13, source_location_id, target_location_id,
               qty, urgency_level, status, created_at
          FROM pending_orders
         WHERE status = 'PENDING'
         ORDER BY urgency_level DESC, created_at ASC
         LIMIT %s
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()

    items = [
        PendingOrder(
            order_id=r[0], order_type=r[1], isbn13=r[2],
            source_location_id=r[3], target_location_id=r[4],
            qty=r[5], urgency_level=r[6], status=r[7], created_at=r[8],
        )
        for r in rows
    ]
    return PendingOrdersResponse(items=items)
