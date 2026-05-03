"""Fan-in routes: GET /dashboard/inventory|forecast|pending|overview."""
import asyncio
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import AuthContext, require_auth
from fastapi import Body
from fastapi.responses import JSONResponse

from ..clients import (
    get_forecast,
    get_intervention_queue,
    get_notifications_recent,
    get_pending_orders,
    get_warehouse_inventory,
    post_decision_decide,
    post_intervention_approve,
    post_intervention_reject,
    post_notification_send,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/inventory/{wh_id}")
async def inventory(wh_id: int, ctx: AuthContext = Depends(require_auth)) -> Any:
    data = await get_warehouse_inventory(wh_id, ctx.token)
    if data is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="inventory-svc unavailable")
    return data


@router.get("/forecast/{store_id}/{snapshot_date}")
async def forecast(store_id: int, snapshot_date: date, ctx: AuthContext = Depends(require_auth)) -> Any:
    data = await get_forecast(store_id, str(snapshot_date), ctx.token)
    if data is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="forecast-svc unavailable")
    return data


@router.get("/pending")
async def pending(ctx: AuthContext = Depends(require_auth), limit: int = 50) -> Any:
    data = await get_pending_orders(ctx.token, limit=limit)
    if data is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="decision-svc unavailable")
    return data


@router.get("/interventions")
async def interventions(ctx: AuthContext = Depends(require_auth)) -> dict:
    data = await get_intervention_queue(ctx.token)
    if data is None:
        return {"items": [], "_source": "intervention-svc unavailable (Phase 3 deploy 전)"}
    return data


@router.get("/notifications")
async def notifications(ctx: AuthContext = Depends(require_auth), limit: int = 50) -> dict:
    data = await get_notifications_recent(ctx.token, limit=limit)
    if data is None:
        return {"items": [], "_source": "notification-svc unavailable (Phase 3 deploy 전)"}
    return data


@router.post("/intervene/approve")
async def intervene_approve(body: dict = Body(...), ctx: AuthContext = Depends(require_auth)):
    """HQ Approval / WH Approve 버튼 → intervention-svc /intervention/approve 프록시.
    .pen 시나리오: C-1~C-4 권역이동 · HQ Approval · WH Approve."""
    sc, data = await post_intervention_approve(body, ctx.token)
    return JSONResponse(status_code=sc, content=data or {"detail": "intervention-svc unavailable"})


@router.post("/intervene/reject")
async def intervene_reject(body: dict = Body(...), ctx: AuthContext = Depends(require_auth)):
    sc, data = await post_intervention_reject(body, ctx.token)
    return JSONResponse(status_code=sc, content=data or {"detail": "intervention-svc unavailable"})


@router.post("/notify/send")
async def notify_send(body: dict = Body(...), ctx: AuthContext = Depends(require_auth)):
    sc, data = await post_notification_send(body, ctx.token)
    return JSONResponse(status_code=sc, content=data or {"detail": "notification-svc unavailable"})


@router.post("/decide")
async def decide(body: dict = Body(...), ctx: AuthContext = Depends(require_auth)):
    """HQ Decision 페이지 - 의사결정 1건 생성 (decision-svc /decide proxy)."""
    sc, data = await post_decision_decide(body, ctx.token)
    return JSONResponse(status_code=sc, content=data or {"detail": "decision-svc unavailable"})


@router.get("/overview/{wh_id}")
async def overview(wh_id: int, ctx: AuthContext = Depends(require_auth)) -> dict:
    """5-way fan-in (.pen Service Mesh + Call Graph 명세).

    intervention-svc + notification-svc 는 Phase 3 까지 미배포 → None tolerated.
    """
    today = date.today().isoformat()
    inv, fcst, pend, intv, noti = await asyncio.gather(
        get_warehouse_inventory(wh_id, ctx.token),
        get_forecast(wh_id, today, ctx.token),
        get_pending_orders(ctx.token, limit=20),
        get_intervention_queue(ctx.token),
        get_notifications_recent(ctx.token, limit=20),
    )
    return {
        "wh_id": wh_id,
        "inventory": inv,
        "forecast": fcst,
        "pending_orders": pend,
        "interventions": intv,
        "notifications": noti,
        "_partial_failures": [
            name for name, val in [
                ("inventory", inv), ("forecast", fcst), ("pending", pend),
                ("intervention", intv), ("notification", noti),
            ] if val is None
        ],
    }
