"""psycopg3 connection pool + Redis client. Initialized at app startup."""
from contextlib import contextmanager

import psycopg
import redis
from psycopg_pool import ConnectionPool

from .settings import settings

_pool: ConnectionPool | None = None
_redis: redis.Redis | None = None


def init_pool() -> None:
    global _pool, _redis
    conninfo = (
        f"host={settings.rds_host} port={settings.rds_port} "
        f"dbname={settings.rds_db} user={settings.rds_user} "
        f"password={settings.rds_password}"
    )
    _pool = ConnectionPool(conninfo, min_size=2, max_size=10, open=True, timeout=10)
    _redis = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)


def close_pool() -> None:
    global _pool, _redis
    if _pool:
        _pool.close()
        _pool = None
    if _redis:
        _redis.close()
        _redis = None


@contextmanager
def db_conn():
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    with _pool.connection() as conn:
        yield conn


def redis_client() -> redis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    return _redis
