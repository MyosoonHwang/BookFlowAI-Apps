"""intervention routes - V6.2 3-stage decision authority enforcement.

Stage / order_type / approval_side 행렬 (시트10 + 시트04 12 events):

| Stage | order_type        | approval_side    | 권한                                                    |
|-------|-------------------|------------------|-------------------------------------------------------|
| 1     | REBALANCE         | FINAL only       | wh-manager (SOURCE/TARGET 같은 wh - 자기 wh 만)            |
| 2     | WH_TRANSFER       | SOURCE / TARGET  | wh-manager (SOURCE 면 source location 의 wh, 동일)         |
| 3     | PUBLISHER_ORDER   | FINAL only       | hq-admin 만                                             |

Stage 2 양쪽 (SOURCE+TARGET) 모두 APPROVED → status=APPROVED 자동 전환.
hq-admin 은 모든 stage 의 FINAL 권한 가짐 (escalation).

승인/거절 후 notification-svc /notification/send 호출 (시트04 12 events 정합):
  - approve → OrderApproved
  - reject  → OrderRejected
  - returns/approve → ReturnPending (승인 시점에 알림)
  - new-book/approve → NewBookRequest (승인 시점에 알림)
"""
import json
import logging
import os
from datetime import datetime
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import AuthContext, require_auth
from ..db import db_conn
from ..models import (
    ApprovalResponse,
    ApproveRequest,
    QueueItem,
    QueueResponse,
    RejectRequest,
    ReturnApproveRequest,
    ReturnApproveResponse,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/intervention", tags=["intervention"])

NOTIFICATION_SVC_URL = os.environ.get(
    "INTERVENTION_NOTIFICATION_SVC_URL",
    "http://notification-svc.bookflow.svc.cluster.local",
)


def _notify(token: str, event_type: str, severity: str, payload: dict, correlation_id: str | None = None) -> None:
    """notification-svc /send 호출 (실패 비치명 · log only)."""
    body = {
        "event_type": event_type,
        "severity": severity,
        "recipients": [],
        "channels": "redis,websocket" if event_type == "OrderPending" else "websocket,logic-apps",
        "payload_summary": payload,
    }
    if correlation_id:
        body["correlation_id"] = correlation_id
    try:
        with httpx.Client(timeout=2.0) as c:
            c.post(
                f"{NOTIFICATION_SVC_URL}/notification/send",
                headers={"Authorization": token},
                json=body,
            )
    except Exception as e:
        log.warning("notification-svc /send (%s) failed (non-fatal): %s", event_type, e)


def _location_wh(cur, location_id: int | None) -> int | None:
    """location_id → wh_id JOIN. None 입력 시 None (PUBLISHER_ORDER source 등)."""
    if location_id is None:
        return None
    cur.execute("SELECT wh_id FROM locations WHERE location_id = %s", (location_id,))
    row = cur.fetchone()
    return row[0] if row else None


def _validate_authority(cur, ctx: AuthContext, order_id: str, side: str) -> tuple[str, int | None, int | None]:
    """승인 권한 검증.

    Returns (order_type, source_wh, target_wh) for valid case. Raises 403 on violation.

    Rules:
    - REBALANCE  : approval_side='FINAL' only · approver wh == source/target wh (둘 다 같음)
    - WH_TRANSFER: approval_side in ('SOURCE','TARGET') · approver wh == 해당 side 의 wh
    - PUBLISHER_ORDER: approval_side='FINAL' only · role='hq-admin' only
    - hq-admin escalation: 어느 stage 의 FINAL 도 가능 (override)
    """
    cur.execute(
        "SELECT order_type, source_location_id, target_location_id FROM pending_orders WHERE order_id = %s",
        (order_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
    order_type, source_loc, target_loc = row
    source_wh = _location_wh(cur, source_loc)
    target_wh = _location_wh(cur, target_loc)

    if order_type == "REBALANCE":
        if side != "FINAL":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="REBALANCE 는 approval_side='FINAL' 만 허용 (단일 승인)")
        if ctx.role == "hq-admin":
            return order_type, source_wh, target_wh
        if ctx.role != "wh-manager" or ctx.scope_wh_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="REBALANCE 는 wh-manager 또는 hq-admin 만 승인 가능")
        if ctx.scope_wh_id not in (source_wh, target_wh):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"본인 창고 외 주문 승인 불가 (scope wh_id={ctx.scope_wh_id} · order wh_id={source_wh}/{target_wh})")

    elif order_type == "WH_TRANSFER":
        if side not in ("SOURCE", "TARGET"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="WH_TRANSFER 는 approval_side in ('SOURCE','TARGET') 만 허용 (양쪽 승인 필요)")
        if ctx.role == "hq-admin":
            return order_type, source_wh, target_wh
        if ctx.role != "wh-manager" or ctx.scope_wh_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="WH_TRANSFER 는 wh-manager 또는 hq-admin 만 승인 가능")
        my_side_wh = source_wh if side == "SOURCE" else target_wh
        if ctx.scope_wh_id != my_side_wh:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"{side} 사이드 권한 없음 (scope wh_id={ctx.scope_wh_id} · {side} wh_id={my_side_wh})")

    elif order_type == "PUBLISHER_ORDER":
        if side != "FINAL":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="PUBLISHER_ORDER 는 approval_side='FINAL' 만 허용")
        if ctx.role != "hq-admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="PUBLISHER_ORDER 는 hq-admin 만 승인 가능 (외부 발주 비용)")

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"unknown order_type: {order_type}")

    return order_type, source_wh, target_wh


@router.get("/queue", response_model=QueueResponse)
def queue(
    ctx: AuthContext = Depends(require_auth),
    limit: int = Query(default=50, ge=1, le=500),
    order_type: str | None = Query(default=None, description="REBALANCE | WH_TRANSFER | PUBLISHER_ORDER"),
    wh_id: int | None = Query(default=None, description="해당 wh 가 source 또는 target 인 주문만"),
):
    """PENDING 주문 큐. role 기반 자동 필터:

    - hq-admin: 명시적 wh_id/order_type 쿼리 없으면 전체. 보통 PUBLISHER_ORDER 만 보고 싶음 → ?order_type=PUBLISHER_ORDER
    - wh-manager: scope_wh_id 자동 적용 (자기 wh 가 source 또는 target)
    """
    where = ["po.status = 'PENDING'"]
    params: list = []

    # role 자동 scope
    if ctx.role == "wh-manager" and ctx.scope_wh_id is not None:
        where.append(
            "(EXISTS (SELECT 1 FROM locations sl WHERE sl.location_id = po.source_location_id AND sl.wh_id = %s)"
            " OR EXISTS (SELECT 1 FROM locations tl WHERE tl.location_id = po.target_location_id AND tl.wh_id = %s))"
        )
        params.extend([ctx.scope_wh_id, ctx.scope_wh_id])

    # 명시적 wh_id 필터 (hq-admin override)
    if wh_id is not None and ctx.role == "hq-admin":
        where.append(
            "(EXISTS (SELECT 1 FROM locations sl WHERE sl.location_id = po.source_location_id AND sl.wh_id = %s)"
            " OR EXISTS (SELECT 1 FROM locations tl WHERE tl.location_id = po.target_location_id AND tl.wh_id = %s))"
        )
        params.extend([wh_id, wh_id])

    if order_type:
        where.append("po.order_type = %s")
        params.append(order_type)

    params.append(limit)
    sql = f"""
        SELECT po.order_id, po.order_type, po.isbn13,
               po.source_location_id, po.target_location_id, po.qty,
               po.urgency_level, po.auto_execute_eligible, po.status, po.created_at
          FROM pending_orders po
         WHERE {' AND '.join(where)}
         ORDER BY po.urgency_level DESC, po.created_at ASC
         LIMIT %s
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
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
    """order_approvals INSERT + pending_orders status 전환 + audit_log."""
    approval_id = str(uuid4())
    cur = conn.cursor()
    # psycopg3 의 prepared statement 가 ON CONFLICT + NULL 조합에서 타입 추론 실패하는 이슈 회피.
    # SELECT-then-UPSERT 패턴 + 모든 파라미터에 명시적 cast.
    cur.execute(
        "SELECT approval_id FROM order_approvals WHERE order_id = %s::uuid AND approval_side = %s::varchar",
        (order_id, side),
        prepare=False,
    )
    existing = cur.fetchone()
    if existing:
        cur.execute(
            """
            UPDATE order_approvals
               SET approver_id = %s::varchar, approver_role = %s::varchar, approver_wh_id = %s::smallint,
                   decision = %s::varchar, reject_reason = %s::varchar, decided_at = NOW()
             WHERE approval_id = %s::uuid
            RETURNING approval_id, decided_at
            """,
            (ctx.user_id, ctx.role, ctx.scope_wh_id,
             decision, reject_reason, str(existing[0])),
            prepare=False,
        )
    else:
        cur.execute(
            """
            INSERT INTO order_approvals
                (approval_id, order_id, approver_id, approver_role, approver_wh_id,
                 approval_side, decision, reject_reason)
            VALUES (%s::uuid, %s::uuid, %s::varchar, %s::varchar, %s::smallint,
                    %s::varchar, %s::varchar, %s::varchar)
            RETURNING approval_id, decided_at
            """,
            (approval_id, order_id, ctx.user_id, ctx.role, ctx.scope_wh_id,
             side, decision, reject_reason),
            prepare=False,
        )
    aid, decided_at = cur.fetchone()

    # status 전환:
    #  - REBALANCE / PUBLISHER_ORDER: FINAL APPROVED 1번 → APPROVED
    #  - WH_TRANSFER: SOURCE+TARGET 둘 다 APPROVED → APPROVED
    #  - REJECTED: 어느 side 든 한 번 거절 → REJECTED + reject_count++
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
        VALUES ('user', %s, %s, 'pending_orders', %s, %s::jsonb)
        """,
        (
            ctx.user_id,
            f"intervention.{decision.lower()}",
            order_id,
            json.dumps({
                "approval_id": str(aid), "side": side, "decision": decision, "reject_reason": reject_reason,
                "approver_role": ctx.role, "approver_wh_id": ctx.scope_wh_id,
            }),
        ),
        prepare=False,
    )
    return str(aid), decided_at


@router.post("/approve", response_model=ApprovalResponse)
def approve(req: ApproveRequest, ctx: AuthContext = Depends(require_auth)):
    with db_conn() as conn:
        with conn.cursor() as cur:
            order_type, source_wh, target_wh = _validate_authority(cur, ctx, str(req.order_id), req.approval_side)
        aid, decided_at = _record_approval(conn, str(req.order_id), ctx, req.approval_side, "APPROVED", None)
        # WH_TRANSFER 양쪽 (SOURCE+TARGET) 모두 APPROVED 됐는지 후-검증 → final notification 보낼지 판단
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM pending_orders WHERE order_id = %s", (str(req.order_id),))
            final_status = cur.fetchone()[0]
        conn.commit()

    # 시트04 ②OrderApproved · 양쪽 다 APPROVED 된 경우만 'final' 알림 (WH_TRANSFER 한쪽만 승인 시 부분 진행)
    _notify(
        ctx.token, "OrderApproved",
        severity="INFO",
        payload={
            "order_id": str(req.order_id),
            "order_type": order_type,
            "approval_side": req.approval_side,
            "approval_id": aid,
            "approver_role": ctx.role,
            "approver_wh_id": ctx.scope_wh_id,
            "final_status": final_status,
        },
        correlation_id=str(req.order_id),
    )
    return ApprovalResponse(approval_id=aid, order_id=req.order_id, decision="APPROVED", decided_at=decided_at)


@router.post("/reject", response_model=ApprovalResponse)
def reject(req: RejectRequest, ctx: AuthContext = Depends(require_auth)):
    with db_conn() as conn:
        with conn.cursor() as cur:
            order_type, source_wh, target_wh = _validate_authority(cur, ctx, str(req.order_id), req.approval_side)
        aid, decided_at = _record_approval(conn, str(req.order_id), ctx, req.approval_side, "REJECTED", req.reject_reason)
        conn.commit()

    # 시트04 ③OrderRejected
    _notify(
        ctx.token, "OrderRejected",
        severity="WARNING",
        payload={
            "order_id": str(req.order_id),
            "order_type": order_type,
            "approval_side": req.approval_side,
            "approval_id": aid,
            "approver_role": ctx.role,
            "approver_wh_id": ctx.scope_wh_id,
            "reject_reason": req.reject_reason,
        },
        correlation_id=str(req.order_id),
    )
    return ApprovalResponse(approval_id=aid, order_id=req.order_id, decision="REJECTED", decided_at=decided_at)


@router.post("/returns/approve", response_model=ReturnApproveResponse)
def returns_approve(req: ReturnApproveRequest, ctx: AuthContext = Depends(require_auth)):
    if ctx.role != "hq-admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="반품 승인은 hq-admin 만 가능")

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

    # 시트04 ⑩ReturnPending (HQ 승인 = 반품 처리 시작 시점 알림)
    _notify(
        ctx.token, "ReturnPending",
        severity="INFO",
        payload={
            "return_id": str(req.return_id),
            "approver_role": ctx.role,
            "note": req.note,
        },
        correlation_id=str(req.return_id),
    )

    return ReturnApproveResponse(return_id=req.return_id, status=row[0], hq_approved_at=row[1])


# ─── New book request approval (HQ Requests page) ─────────────────────────────
@router.post("/new-book-requests/{request_id}/approve")
def approve_new_book_request(
    request_id: int,
    ctx: AuthContext = Depends(require_auth),
):
    """출판사 신간 신청 → HQ 승인. new_book_requests.status='APPROVED' 전환."""
    if ctx.role != "hq-admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="신간 승인은 hq-admin 만 가능")

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE new_book_requests SET status = 'APPROVED', approved_at = NOW() WHERE id = %s AND status IN ('NEW','FETCHED') RETURNING isbn13",
                (request_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="요청 없음 또는 이미 처리됨")
            cur.execute(
                """
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, after_state)
                VALUES ('user', %s, 'intervention.new_book.approve', 'new_book_requests', %s, %s)
                """,
                (ctx.user_id, str(request_id), json.dumps({"isbn13": row[0]})),
            )
        conn.commit()

    # 시트04 ⑨NewBookRequest (publisher-watcher 가 NEW 시점 한 번 발송 + HQ 승인 시 한 번 더)
    _notify(
        ctx.token, "NewBookRequest",
        severity="INFO",
        payload={
            "id": request_id,
            "isbn13": row[0],
            "stage": "APPROVED",
            "approver_role": ctx.role,
        },
    )

    return {"id": request_id, "status": "APPROVED", "isbn13": row[0]}
