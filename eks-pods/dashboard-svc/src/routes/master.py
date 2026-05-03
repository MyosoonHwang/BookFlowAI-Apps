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


@router.get("/books")
def books(
    _: AuthContext = Depends(require_auth),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
):
    """books 카탈로그 (1000책) - HQ Books 페이지."""
    where = "WHERE active = TRUE"
    params: list = []
    if q:
        where += " AND (title ILIKE %s OR author ILIKE %s OR isbn13 = %s)"
        params.extend([f"%{q}%", f"%{q}%", q])
    params.extend([limit, offset])

    sql = f"""
        SELECT isbn13, title, author, publisher, pub_date, category_name,
               price_standard, price_sales, discontinue_mode, expected_soldout_at
          FROM books
          {where}
         ORDER BY isbn13
         LIMIT %s OFFSET %s
    """
    count_sql = f"SELECT count(*) FROM books {where}"
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(count_sql, params[:-2])
        total = cur.fetchone()[0]
        cur.execute(sql, params)
        rows = cur.fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "isbn13": r[0], "title": r[1], "author": r[2], "publisher": r[3],
                "pub_date": r[4].isoformat() if r[4] else None,
                "category": r[5],
                "price_standard": r[6], "price_sales": r[7],
                "discontinue_mode": r[8],
                "expected_soldout_at": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ],
    }


@router.get("/spike-events")
def spike_events(
    _: AuthContext = Depends(require_auth),
    limit: int = Query(default=20, ge=1, le=100),
):
    """spike_events 최근 N건 (spike-detect Lambda 가 INSERT 한 row).

    Phase 3.5 데모: cross-ISBN z-score · z>=0.5 위 인기 도서 자동 검출.
    """
    sql = """
        SELECT s.event_id, s.detected_at, s.isbn13, s.z_score, s.mentions_count,
               b.title, b.author, b.category_name
          FROM spike_events s
          LEFT JOIN books b ON b.isbn13 = s.isbn13
         ORDER BY s.detected_at DESC
         LIMIT %s
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()

    return {
        "items": [
            {
                "event_id":       str(r[0]),
                "detected_at":    r[1].isoformat() if r[1] else None,
                "isbn13":         r[2],
                "z_score":        float(r[3]) if r[3] is not None else None,
                "mentions_count": r[4],
                "title":          r[5],
                "author":         r[6],
                "category":       r[7],
            }
            for r in rows
        ],
    }


@router.get("/returns")
def returns(
    _: AuthContext = Depends(require_auth),
    limit: int = Query(default=50, ge=1, le=500),
):
    """returns 큐 (HQ Returns 페이지)."""
    sql = """
        SELECT r.return_id, r.isbn13, r.location_id, r.qty, r.reason,
               r.status, r.requested_at, r.hq_approved_at, r.executed_at,
               b.title, b.author
          FROM returns r
          LEFT JOIN books b ON b.isbn13 = r.isbn13
         ORDER BY r.requested_at DESC
         LIMIT %s
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()

    return {
        "items": [
            {
                "return_id":       str(r[0]),
                "isbn13":          r[1],
                "location_id":     r[2],
                "qty":             r[3],
                "reason":          r[4],
                "status":          r[5],
                "requested_at":    r[6].isoformat() if r[6] else None,
                "hq_approved_at":  r[7].isoformat() if r[7] else None,
                "executed_at":     r[8].isoformat() if r[8] else None,
                "title":           r[9],
                "author":          r[10],
            }
            for r in rows
        ],
    }


@router.get("/new-book-requests")
def new_book_requests(
    _: AuthContext = Depends(require_auth),
    limit: int = Query(default=50, ge=1, le=500),
):
    """new_book_requests (HQ Requests · 출판사 신간 신청 큐)."""
    sql = """
        SELECT id, isbn13, publisher_id, title, status, requested_at, fetched_at, approved_at
          FROM new_book_requests
         ORDER BY requested_at DESC
         LIMIT %s
    """
    with db_conn() as conn, conn.cursor() as cur:
        try:
            cur.execute(sql, (limit,))
        except Exception:
            # fallback if some columns missing in schema variant
            cur.execute(
                "SELECT id, isbn13, publisher_id, title, status, requested_at FROM new_book_requests ORDER BY requested_at DESC LIMIT %s",
                (limit,),
            )
        rows = cur.fetchall()

    return {
        "items": [
            {
                "id":           r[0],
                "isbn13":       r[1],
                "publisher_id": r[2],
                "title":        r[3],
                "status":       r[4],
                "requested_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ],
    }


@router.get("/sales-by-store")
def sales_by_store(_: AuthContext = Depends(require_auth)):
    """매장별 매출 1h - HQ KPI 차트용."""
    sql = """
        SELECT store_id,
               count(*) AS transactions,
               COALESCE(sum(revenue), 0) AS revenue,
               count(*) FILTER (WHERE channel LIKE 'ONLINE%') AS online_count
          FROM sales_realtime
         WHERE event_ts > NOW() - INTERVAL '1 hour'
         GROUP BY store_id
         ORDER BY revenue DESC
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    return {
        "items": [
            {
                "store_id":     r[0],
                "transactions": r[1],
                "revenue":      int(r[2]),
                "online_count": r[3],
            }
            for r in rows
        ],
    }
