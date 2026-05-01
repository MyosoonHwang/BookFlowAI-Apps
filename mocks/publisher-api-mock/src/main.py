"""External publisher new-book-request API mock.

Schema source: V6.2 slide 10/30 (publish-watcher CronJob) + sheet 02 RDS new_book_requests.

Real endpoint (per BookFlow): assumed RESTful API per publisher channel.
  GET /api/v1/new-book-requests?since=ISO8601&limit=50
Response:
  [{"request_id": ..., "publisher_id": ..., "isbn13": ..., "title": ...,
    "author": ..., "genre": ..., "expected_pub_date": ..., "estimated_initial_sales": ...,
    "marketing_plan": ..., "similar_books": [...], "target_segments": [...],
    "submitted_at": ISO8601}]

Mock returns 0~5 deterministic new requests per call (rotates by minute) so
publish-watcher CronJob has variety to consume.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, Query
from pydantic import BaseModel

app = FastAPI(title="publisher-api-mock", version="0.1.0")

KST = timezone(timedelta(hours=9))


def _gen_isbn13(seed: int) -> str:
    base = f"979{(seed % 10000000):07d}"
    digits = [int(c) for c in base]
    weights = [1, 3] * 6
    csum = (10 - sum(d * w for d, w in zip(digits, weights)) % 10) % 10
    return base + str(csum)


@app.get("/api/v1/new-book-requests")
def list_new_book_requests(
    since: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    now = datetime.now(KST)
    minute = now.minute
    n = (minute % 6)  # 0~5 each minute
    items: list[dict[str, Any]] = []
    for i in range(n):
        seed = int(hashlib.sha256(f"{now.date()}-{minute}-{i}".encode()).hexdigest()[:8], 16)
        items.append(
            {
                "request_id": f"req-{now.strftime('%Y%m%d%H%M')}-{i:02d}",
                "publisher_id": str((seed % 50) + 1),
                "isbn13": _gen_isbn13(seed),
                "title": f"Mock Forthcoming Title #{minute}-{i}",
                "author": ["김작가", "박작가", "이작가"][i % 3],
                "genre": ["fiction", "nonfiction", "self-help", "tech", "economics"][i % 5],
                "expected_pub_date": (now.date() + timedelta(days=14 + i)).isoformat(),
                "estimated_initial_sales": 1000 + (seed % 9000),
                "marketing_plan": "SNS push + bestseller list submission",
                "similar_books": [],
                "target_segments": ["20s-female", "metro"],
                "submitted_at": (now - timedelta(minutes=i)).isoformat(),
            }
        )
    return items[:limit]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
