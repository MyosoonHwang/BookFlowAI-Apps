"""inventory routes: /current/{wh_id} · /adjust · /reserve.

Single-writer pod: all inventory mutations flow through here. Redis pub on stock.changed.
"""
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import AuthContext, require_auth
from ..db import db_conn, redis_client
from ..models import (
    AdjustRequest,
    AdjustResponse,
    InventoryItem,
    ReserveRequest,
    ReserveResponse,
    WarehouseInventoryResponse,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])

REDIS_CHANNEL_STOCK = "stock.changed"


@router.get("/current/{wh_id}", response_model=WarehouseInventoryResponse)
def get_warehouse_inventory(wh_id: int, ctx: AuthContext = Depends(require_auth)):
    if ctx.role == "wh-manager" and ctx.scope_wh_id is not None and ctx.scope_wh_id != wh_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="out of warehouse scope")

    sql = """
        SELECT i.isbn13, i.location_id, i.on_hand, i.reserved_qty,
               COALESCE(i.safety_stock, 0) AS safety_stock, i.updated_at
        FROM inventory i
        JOIN locations l ON l.location_id = i.location_id
        WHERE l.wh_id = %s
        ORDER BY i.location_id, i.isbn13
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (wh_id,))
        rows = cur.fetchall()

    items = [
        InventoryItem(
            isbn13=r[0],
            location_id=r[1],
            on_hand=r[2],
            reserved_qty=r[3],
            safety_stock=r[4],
            available=r[2] - r[3],
            updated_at=r[5],
        )
        for r in rows
    ]
    return WarehouseInventoryResponse(wh_id=wh_id, items=items)


@router.post("/adjust", response_model=AdjustResponse)
def adjust(req: AdjustRequest, ctx: AuthContext = Depends(require_auth)):
    """Atomic on_hand adjust + audit_log + Redis publish stock.changed."""
    if ctx.role == "branch-clerk":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="branch-clerk cannot adjust inventory")

    update_sql = """
        UPDATE inventory
           SET on_hand = on_hand + %s,
               updated_at = NOW(),
               updated_by = %s
         WHERE isbn13 = %s AND location_id = %s
        RETURNING on_hand - %s, on_hand
    """
    audit_sql = """
        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, before_state, after_state)
        VALUES ('user', %s, 'inventory.adjust', 'inventory', %s, %s, %s)
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(update_sql, (req.delta, ctx.user_id, req.isbn13, req.location_id, req.delta))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory row not found")
            on_hand_before, on_hand_after = row
            if on_hand_after < 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="on_hand would go negative")
            entity_id = f"{req.isbn13}:{req.location_id}"
            cur.execute(
                audit_sql,
                (
                    ctx.user_id,
                    entity_id,
                    json.dumps({"on_hand": on_hand_before}),
                    json.dumps({"on_hand": on_hand_after, "delta": req.delta, "reason": req.reason}),
                ),
            )
        conn.commit()

    payload = json.dumps({
        "isbn13": req.isbn13,
        "location_id": req.location_id,
        "available": on_hand_after,  # caller may further subtract reserved_qty
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    redis_client().publish(REDIS_CHANNEL_STOCK, payload)
    redis_client().delete(f"stock:{req.isbn13}", f"stock:{req.isbn13}:{req.location_id}")

    return AdjustResponse(
        isbn13=req.isbn13,
        location_id=req.location_id,
        on_hand_before=on_hand_before,
        on_hand_after=on_hand_after,
    )


@router.post("/reserve", response_model=ReserveResponse)
def reserve(req: ReserveRequest, ctx: AuthContext = Depends(require_auth)):
    """Reserve qty (subtracts from available). reservations row + inventory.reserved_qty bump."""
    reservation_id = uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=req.ttl_seconds)

    bump_sql = """
        UPDATE inventory
           SET reserved_qty = reserved_qty + %s,
               updated_at = NOW(),
               updated_by = %s
         WHERE isbn13 = %s AND location_id = %s
           AND on_hand - reserved_qty >= %s
        RETURNING on_hand, reserved_qty
    """
    insert_sql = """
        INSERT INTO reservations (reservation_id, isbn13, location_id, qty, reason, status, ttl, created_by)
        VALUES (%s, %s, %s, %s, %s, 'ACTIVE', %s, %s)
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(bump_sql, (req.qty, ctx.user_id, req.isbn13, req.location_id, req.qty))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="insufficient available stock")
            cur.execute(insert_sql, (str(reservation_id), req.isbn13, req.location_id, req.qty, req.reason, expires_at, ctx.user_id))
        conn.commit()

    return ReserveResponse(
        reservation_id=reservation_id,
        isbn13=req.isbn13,
        location_id=req.location_id,
        qty=req.qty,
        expires_at=expires_at,
    )
