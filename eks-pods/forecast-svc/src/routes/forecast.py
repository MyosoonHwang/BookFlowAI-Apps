"""forecast routes: GET /forecast/{store_id}/{snapshot_date} · POST /forecast/refresh.

D+1 forecast cache only (D+2~5 lives in BigQuery, accessed by dashboard-bff via VPN).
"""
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import AuthContext, require_auth
from ..db import db_conn
from ..models import (
    ForecastResponse, ForecastRow, RefreshRequest, RefreshResponse,
    InsufficientStockItem, InsufficientStockResponse,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/forecast", tags=["forecast"])


def _check_forecast_store_scope(cur, ctx: AuthContext, store_id: int) -> None:
    """forecast 단건 조회 권한 (권한 매트릭스 · 2026-05-14).

    - hq-admin: 전권
    - wh-manager: scope_wh_id == locations.wh_id (store_id) 만
    - branch-clerk: scope_store_id == store_id 만

    Raises HTTPException 403 on violation.
    """
    if ctx.role == "hq-admin":
        return

    if ctx.role == "branch-clerk":
        if ctx.scope_store_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="branch-clerk scope_store_id 부재 (인증 토큰 손상)")
        if ctx.scope_store_id != store_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"자기 매장만 조회 가능 (scope_store_id={ctx.scope_store_id} · 요청 store_id={store_id})")
        return

    if ctx.role == "wh-manager":
        if ctx.scope_wh_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="wh-manager scope_wh_id 부재 (인증 토큰 손상)")
        cur.execute("SELECT wh_id FROM locations WHERE location_id = %s", (store_id,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"store_id {store_id} locations 미존재")
        if row[0] != ctx.scope_wh_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"자기 권역만 조회 가능 (scope_wh_id={ctx.scope_wh_id} · store wh_id={row[0]})")
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"role '{ctx.role}' 는 forecast 조회 권한 없음")


def _forecast_scope_clause(ctx: AuthContext) -> tuple[str, list]:
    """role/scope → forecast_cache 용 SQL where 절 + params.

    - hq-admin: 빈 절
    - wh-manager + scope_wh_id: f.store_id 가 해당 wh 의 location 인 것만
    - branch-clerk + scope_store_id: f.store_id = scope_store_id

    Returns ("", []) 가 빈 절 (필터 없음).
    """
    if ctx.role == "wh-manager" and ctx.scope_wh_id is not None:
        return (
            "EXISTS (SELECT 1 FROM locations sl WHERE sl.location_id = f.store_id AND sl.wh_id = %s)",
            [ctx.scope_wh_id],
        )
    if ctx.role == "branch-clerk" and ctx.scope_store_id is not None:
        return ("f.store_id = %s", [ctx.scope_store_id])
    return ("", [])


@router.get("/{store_id}/{snapshot_date}", response_model=ForecastResponse)
def get_forecast(store_id: int, snapshot_date: date, ctx: AuthContext = Depends(require_auth)):
    sql = """
        SELECT snapshot_date, isbn13, store_id, predicted_demand,
               confidence_low, confidence_high, model_version, synced_at
          FROM forecast_cache
         WHERE store_id = %s AND snapshot_date = %s
         ORDER BY isbn13
    """
    with db_conn() as conn, conn.cursor() as cur:
        _check_forecast_store_scope(cur, ctx, store_id)
        cur.execute(sql, (store_id, snapshot_date))
        rows = cur.fetchall()

    items = [
        ForecastRow(
            snapshot_date=r[0], isbn13=r[1], store_id=r[2],
            predicted_demand=float(r[3]),
            confidence_low=float(r[4]) if r[4] is not None else None,
            confidence_high=float(r[5]) if r[5] is not None else None,
            model_version=r[6], synced_at=r[7],
        )
        for r in rows
    ]
    return ForecastResponse(snapshot_date=snapshot_date, store_id=store_id, items=items)


@router.get("/insufficient-stock", response_model=InsufficientStockResponse)
def insufficient_stock(
    limit: int = 2000,
    ctx: AuthContext = Depends(require_auth),
):
    """P1-4b 시연 trigger: 안전재고 5일치 (predicted_demand × 5) > 가용재고 인 도서 list.

    매일 배치성 처리 가정 (사용자 결정 2026-05-13) — limit default 2000 = 전수 검사.
    안전재고 = 익일 forecast × 5 (forecast 는 권/일 단위 · 5일치를 안전선).
    suggested_qty = gap × 1.2 (min 30, max 500 · 5일치라 더 큰 발주 허용).

    권한 (2026-05-14 백엔드 필터 추가):
    - hq-admin: 전 매장
    - wh-manager + scope_wh_id: 자기 권역 store 만
    - branch-clerk + scope_store_id: 자기 매장만
    """
    # 시연 의도: '익일 (CURRENT_DATE + 1) 지점·물류센터별 수요예측 × 5 vs 현재 가용재고' 비교.
    # 출판사 발주는 매장 직접 X · WH 경유 (사용자 결정 2026-05-13) — recommend_target = store_id 의 WH location.
    scope_clause, scope_params = _forecast_scope_clause(ctx)
    scope_sql = f" AND {scope_clause}" if scope_clause else ""
    sql = f"""
        WITH target AS (
            SELECT MIN(snapshot_date) AS d FROM forecast_cache WHERE snapshot_date > CURRENT_DATE
        ),
        wh_loc AS (
            -- 권역별 WH location_id (location_type='WH')
            SELECT wh_id, location_id AS wh_location_id FROM locations WHERE location_type = 'WH'
        )
        SELECT f.isbn13, b.title, f.store_id,
               f.predicted_demand,
               COALESCE(SUM(GREATEST(i.on_hand - i.reserved_qty, 0)), 0)::int AS available,
               COALESCE(wh.wh_location_id, f.store_id) AS recommend_target
          FROM forecast_cache f
          LEFT JOIN books b ON b.isbn13 = f.isbn13
          LEFT JOIN inventory i ON i.isbn13 = f.isbn13 AND i.location_id = f.store_id
          LEFT JOIN locations sl ON sl.location_id = f.store_id
          LEFT JOIN wh_loc wh ON wh.wh_id = sl.wh_id
          CROSS JOIN target
         WHERE f.snapshot_date = target.d{scope_sql}
         GROUP BY f.isbn13, b.title, f.store_id, f.predicted_demand, wh.wh_location_id
        HAVING f.predicted_demand * 5 > COALESCE(SUM(GREATEST(i.on_hand - i.reserved_qty, 0)), 0)
         ORDER BY (f.predicted_demand * 5 - COALESCE(SUM(GREATEST(i.on_hand - i.reserved_qty, 0)), 0)) DESC
         LIMIT %s
    """
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (*scope_params, limit))
        rows = cur.fetchall()
        cur.execute("SELECT MIN(snapshot_date) FROM forecast_cache WHERE snapshot_date > CURRENT_DATE")
        snapshot = cur.fetchone()[0]

    items: list[InsufficientStockItem] = []
    for r in rows:
        isbn13, title, store_id, pred, avail = r[0], r[1], r[2], float(r[3]), int(r[4])
        recommend_target = int(r[5])
        safety_5d = int(pred * 5)
        gap = max(0, safety_5d - avail)
        # gap × 1.2 buffer, min 30, max 500 (5일치 기준)
        suggested = max(30, min(500, int(gap * 1.2)))
        items.append(InsufficientStockItem(
            isbn13=isbn13, title=title, store_id=store_id,
            recommend_target_location_id=recommend_target,
            predicted_demand=pred, safety_stock_5days=safety_5d,
            available=avail, gap=gap, suggested_qty=suggested,
        ))

    return InsufficientStockResponse(snapshot_date=snapshot or date.today(), items=items)


@router.post("/refresh", response_model=RefreshResponse)
def refresh(req: RefreshRequest, ctx: AuthContext = Depends(require_auth)):
    """Bulk UPSERT (idempotent). Phase 2 stub - real BQ -> RDS sync wired later."""
    if ctx.role != "hq-admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="hq-admin only")

    sql = """
        INSERT INTO forecast_cache
            (snapshot_date, isbn13, store_id, predicted_demand,
             confidence_low, confidence_high, model_version, synced_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_date, isbn13, store_id) DO UPDATE
        SET predicted_demand = EXCLUDED.predicted_demand,
            confidence_low   = EXCLUDED.confidence_low,
            confidence_high  = EXCLUDED.confidence_high,
            model_version    = EXCLUDED.model_version,
            synced_at        = EXCLUDED.synced_at
    """
    now = datetime.now(timezone.utc)
    with db_conn() as conn:
        with conn.cursor() as cur:
            for it in req.items:
                cur.execute(sql, (
                    it.snapshot_date, it.isbn13, it.store_id, it.predicted_demand,
                    it.confidence_low, it.confidence_high, it.model_version, now,
                ))
        conn.commit()

    return RefreshResponse(
        snapshot_date=req.snapshot_date,
        store_id=req.store_id,
        inserted=len(req.items),
    )


# ──────────────────────────────────────────────────────────────────────────────
# 신간 편입 결정용 — VertexAI 수요예측 호출 (2026-05-15 사용자 결정)
#
# 흐름:
#   1) 출판사 신청 (new_book_requests PENDING) →
#   2) 본사가 이 endpoint 호출 → VertexAI Pipeline 으로 매장별/wh별 수요예측 받음 →
#   3) 결과를 보고 본사가 가치 판단 후 편입 결정 (/intervention/new-book-requests/{id}/approve)
#
# TODO(GCP 연결 후): vertex AI Endpoint POST 호출로 교체.
#   - GCP_VERTEX_ENDPOINT env var
#   - 입력 instance: {isbn13, publisher_id, category, price, dimensions...}
#   - 출력 predictions: per (location_id) → {predicted_demand_7d, predicted_demand_30d, confidence}
# 현재는 책 메타데이터 기반 mock — 매장 12 + wh 2 (총 14 location).
# ──────────────────────────────────────────────────────────────────────────────
import random as _rnd
from pydantic import BaseModel

class NewBookPredictReq(BaseModel):
    isbn13: str
    publisher_id: int | None = None
    category: str | None = None
    expected_price: int | None = None

class NewBookLocationPred(BaseModel):
    location_id: int
    location_name: str
    location_type: str  # 'STORE_OFFLINE' | 'STORE_ONLINE' | 'WH'
    wh_id: int | None
    predicted_demand_7d: float
    predicted_demand_30d: float
    confidence: float  # 0.0~1.0

class NewBookPredictResp(BaseModel):
    isbn13: str
    model_version: str
    predicted_at: str
    predictions: list[NewBookLocationPred]
    total_7d: float
    total_30d: float
    recommendation: str  # 'STRONG_BUY' | 'BUY' | 'NEUTRAL' | 'PASS'


@router.post("/newbook/predict-demand", response_model=NewBookPredictResp)
def newbook_predict_demand(req: NewBookPredictReq, ctx: AuthContext = Depends(require_auth)):
    """신간 편입 결정용 매장별/wh별 7d/30d 수요예측. hq-admin only.

    GCP 연결 후 Vertex AI Pipeline 호출로 교체될 stub.
    현재 mock 데이터 — 책 메타데이터 (publisher_id 인기도 ranking + category) 기반 분포.
    """
    if ctx.role != "hq-admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="hq-admin only (신간 편입 결정 권한)")

    # 모든 매장 + wh location list (DB 조회)
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT location_id, name, location_type, wh_id "
            "FROM locations WHERE active = TRUE AND COALESCE(is_virtual, FALSE) = FALSE "
            "ORDER BY location_type, location_id"
        )
        loc_rows = cur.fetchall()

    # Mock 분포 — 출판사 id 기반 base demand (실제 GCP 응답 모방)
    base_demand = 30 + (req.publisher_id or 1) % 50  # 30~80 per store / 7d
    rng = _rnd.Random(hash(req.isbn13) & 0xFFFFFFFF)
    predictions: list[NewBookLocationPred] = []
    for lid, name, ltype, wh_id in loc_rows:
        if ltype == "WH":
            # WH = 자기 권역 매장 합산 base × 6 매장
            d7 = base_demand * 6 * rng.uniform(0.7, 1.3)
        elif ltype == "STORE_ONLINE":
            d7 = base_demand * rng.uniform(1.5, 2.5)  # 온라인 보통 더 많음
        else:
            d7 = base_demand * rng.uniform(0.6, 1.4)
        d30 = d7 * 4.2  # 4주 × 약간 누적 효과
        predictions.append(NewBookLocationPred(
            location_id=lid,
            location_name=name,
            location_type=ltype,
            wh_id=wh_id,
            predicted_demand_7d=round(d7, 1),
            predicted_demand_30d=round(d30, 1),
            confidence=round(rng.uniform(0.65, 0.92), 2),
        ))

    total_7d = sum(p.predicted_demand_7d for p in predictions if p.location_type != "WH")
    total_30d = sum(p.predicted_demand_30d for p in predictions if p.location_type != "WH")

    # Recommendation rule (mock):
    #   total_7d ≥ 800 → STRONG_BUY · 400~799 → BUY · 200~399 → NEUTRAL · <200 → PASS
    if total_7d >= 800: rec = "STRONG_BUY"
    elif total_7d >= 400: rec = "BUY"
    elif total_7d >= 200: rec = "NEUTRAL"
    else: rec = "PASS"

    return NewBookPredictResp(
        isbn13=req.isbn13,
        model_version="mock-pending-gcp-vertexai-v0.1",
        predicted_at=datetime.now(timezone.utc).isoformat(),
        predictions=predictions,
        total_7d=round(total_7d, 1),
        total_30d=round(total_30d, 1),
        recommendation=rec,
    )
