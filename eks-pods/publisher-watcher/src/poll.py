"""publisher-watcher CronJob entry point.

Schedule: */1 * * * * (every 1 minute · k8s CronJob).
1. GET publisher API stub → list of NewBookRequest objects
2. INSERT new_book_requests (ON CONFLICT DO NOTHING — idempotent on isbn13)
3. Redis pub `newbook.request` for each new row → notification-svc subscriber

Real publisher API: 출판사 신간 신청 endpoint (Phase 4 + ALB external entry).
Phase 2-3: synthesized stub via env (or no-op if URL unset).
"""
import json
import logging
import os
import sys

import httpx
import psycopg
import redis
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(level=os.environ.get("PUBWATCH_LOG_LEVEL", "INFO"))
log = logging.getLogger("publisher-watcher")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PUBWATCH_", case_sensitive=False)

    rds_host: str
    rds_port: int = 5432
    rds_db: str = "bookflow"
    rds_user: str
    rds_password: str

    redis_host: str
    redis_port: int = 6379

    publisher_api_url: str = ""  # empty = skip polling (no-op cron)
    publisher_api_timeout_seconds: float = 10.0

    log_level: str = "INFO"


def fetch_pending(api_url: str, timeout: float) -> list[dict]:
    if not api_url:
        log.info("PUBWATCH_PUBLISHER_API_URL empty — skip (no-op cron)")
        return []
    try:
        r = httpx.get(f"{api_url}/new-book-requests", timeout=timeout)
        r.raise_for_status()
        body = r.json()
        return body.get("items", body if isinstance(body, list) else [])
    except Exception as e:
        log.warning("publisher API GET failed: %s", e)
        return []


def main() -> int:
    s = Settings()
    items = fetch_pending(s.publisher_api_url, s.publisher_api_timeout_seconds)
    if not items:
        log.info("no new requests")
        return 0

    conninfo = (
        f"host={s.rds_host} port={s.rds_port} dbname={s.rds_db} "
        f"user={s.rds_user} password={s.rds_password}"
    )
    rds = redis.Redis(host=s.redis_host, port=s.redis_port, decode_responses=True)
    inserted = 0
    with psycopg.connect(conninfo) as conn:
        for it in items:
            isbn13 = it.get("isbn13")
            publisher_id = it.get("publisher_id")
            title = it.get("title")
            if not isbn13:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO new_book_requests
                        (isbn13, publisher_id, title, status, requested_at)
                    VALUES (%s, %s, %s, 'NEW', NOW())
                    ON CONFLICT (isbn13) DO NOTHING
                    RETURNING id
                    """,
                    (isbn13, publisher_id, title),
                )
                row = cur.fetchone()
                if row is None:
                    continue  # duplicate, already in queue
                request_id = row[0]
                cur.execute(
                    """
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, after_state)
                    VALUES ('cronjob', 'publisher-watcher', 'newbook.discovered', 'new_book_requests', %s, %s)
                    """,
                    (str(request_id), json.dumps({"isbn13": isbn13, "publisher_id": publisher_id})),
                )
                inserted += 1
                try:
                    rds.publish("newbook.request", json.dumps({
                        "request_id": request_id, "publisher_id": publisher_id, "isbn13": isbn13,
                    }))
                except Exception as e:
                    log.warning("redis publish failed: %s", e)
        conn.commit()

    log.info("inserted %d new_book_requests", inserted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
