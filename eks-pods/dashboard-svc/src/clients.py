"""httpx-based async clients for fan-in to other Pods.

Auth header forwarded as-is to downstream (mock token Phase 2 / real JWT Phase 4).
Per-route timeout · gather() for parallel fan-in · partial failure tolerated.
"""
import logging
from typing import Any

import httpx

from .settings import settings

log = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def init_client() -> None:
    global _client
    _client = httpx.AsyncClient(timeout=settings.fan_in_timeout_seconds)


async def close_client() -> None:
    if _client:
        await _client.aclose()


async def _safe_get(url: str, token: str) -> Any:
    try:
        r = await _client.get(url, headers={"Authorization": token})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("fan-in GET %s failed: %s", url, e)
        return None


async def get_warehouse_inventory(wh_id: int, token: str) -> dict | None:
    # NOTE: .pen Service Mesh spec is `/inventory/store/{id}`. Phase 3 path-alignment.
    return await _safe_get(f"{settings.inventory_svc_url}/inventory/current/{wh_id}", token)


async def get_forecast(store_id: int, snapshot_date: str, token: str) -> dict | None:
    return await _safe_get(f"{settings.forecast_svc_url}/forecast/{store_id}/{snapshot_date}", token)


async def get_pending_orders(token: str, limit: int = 50) -> dict | None:
    # NOTE: .pen says `/decision/pending`. Phase 3 path-alignment.
    return await _safe_get(f"{settings.decision_svc_url}/decision/pending-orders?limit={limit}", token)


async def get_intervention_queue(token: str) -> dict | None:
    """intervention-svc 가 관리하는 승인 대기 큐 (`order_approvals` SOURCE/TARGET 진행 + returns 승인 대기).
    Phase 3 까지 pod 미배포 → _safe_get 이 None 반환 (정상 BFF 거동).
    """
    return await _safe_get(f"{settings.intervention_svc_url}/intervention/queue", token)


async def get_notifications_recent(token: str, limit: int = 50) -> dict | None:
    """notification-svc 의 최근 알림 (`notifications_log`). Phase 3 까지 None."""
    return await _safe_get(f"{settings.notification_svc_url}/notification/recent?limit={limit}", token)


async def _safe_post(url: str, body: dict, token: str) -> tuple[int, Any]:
    """POST 프록시. (status_code, body_or_None) 반환. downstream pod 미배포면 503."""
    try:
        r = await _client.post(url, json=body, headers={"Authorization": token})
        return r.status_code, r.json() if r.content else None
    except Exception as e:
        log.warning("fan-in POST %s failed: %s", url, e)
        return 503, None


async def post_intervention_approve(body: dict, token: str) -> tuple[int, Any]:
    return await _safe_post(f"{settings.intervention_svc_url}/intervention/approve", body, token)


async def post_intervention_reject(body: dict, token: str) -> tuple[int, Any]:
    return await _safe_post(f"{settings.intervention_svc_url}/intervention/reject", body, token)


async def post_notification_send(body: dict, token: str) -> tuple[int, Any]:
    return await _safe_post(f"{settings.notification_svc_url}/notification/send", body, token)


async def post_decision_decide(body: dict, token: str) -> tuple[int, Any]:
    return await _safe_post(f"{settings.decision_svc_url}/decision/decide", body, token)
