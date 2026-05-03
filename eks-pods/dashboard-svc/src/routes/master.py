"""Master/aggregate read routes via direct RDS (dashboard_svc SELECT-only).

.pen Service Mesh: dashboard-bff/svc reads books/kpi_mart/sales master tables directly,
not via inventory-svc. These pages don't need transactional consistency.
"""
from fastapi import APIRouter, Depends, Query

from ..auth import AuthContext, require_auth
from ..db import db_conn

router = APIRouter(prefix="/dashboard", tags=["dashboard-master"])


@router.get("/recent-sales")
def recent_sales(
    _: AuthContext = Depends(require_auth),
    limit: int = Query(default=20, ge=1, le=200),
):
    """sales_realtime 최근 N건 (POS 트랜잭션 실시간 흐름 모니터링).

    pos-ingestor Lambda 가 INSERT 한 row 가 그대로 보임.
    """
    sql = """
        SELECT txn_id, event_ts, isbn13, store_id, channel, qty, revenue
          FROM sales_realtime
         ORDER BY event_ts DESC
         LIMIT %s
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()

    return {
        "items": [
            {
                "txn_id":   str(r[0]),
                "event_ts": r[1].isoformat() if r[1] else None,
                "isbn13":   r[2],
                "store_id": r[3],
                "channel":  r[4],
                "qty":      r[5],
                "revenue":  r[6],
            }
            for r in rows
        ],
    }


@router.get("/sales-summary")
def sales_summary(_: AuthContext = Depends(require_auth)):
    """집계 요약 - 최근 1시간 매출 합 + 트랜잭션 수 + 채널별 비중."""
    sql = """
        SELECT
            count(*)                       AS n,
            COALESCE(sum(revenue), 0)      AS total_revenue,
            count(*) FILTER (WHERE channel LIKE 'ONLINE%')  AS online_count,
            count(*) FILTER (WHERE channel = 'OFFLINE')     AS offline_count
          FROM sales_realtime
         WHERE event_ts > NOW() - INTERVAL '1 hour'
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        n, total_revenue, online_count, offline_count = cur.fetchone()

    return {
        "window": "1h",
        "transactions":   n,
        "total_revenue":  int(total_revenue or 0),
        "online_count":   online_count,
        "offline_count":  offline_count,
    }
