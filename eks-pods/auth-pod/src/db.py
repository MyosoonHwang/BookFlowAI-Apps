"""psycopg3 pool · users upsert on first login."""
import logging
from contextlib import contextmanager

from psycopg_pool import ConnectionPool

from .settings import settings

log = logging.getLogger(__name__)
_pool: ConnectionPool | None = None


def _conninfo() -> str:
    return (
        f"host={settings.rds_host} port={settings.rds_port} "
        f"dbname={settings.rds_db} user={settings.rds_user} password={settings.rds_password}"
    )


def init_pool() -> None:
    global _pool
    pool = ConnectionPool(_conninfo(), min_size=1, max_size=5, open=False)
    try:
        pool.open(wait=True, timeout=5)
        _pool = pool
        log.info("auth-pod DB pool ready")
    except Exception as e:
        log.warning("DB pool init failed: %s", e)
        _pool = None


def close_pool() -> None:
    global _pool
    if _pool:
        _pool.close()
        _pool = None


@contextmanager
def db_conn():
    if _pool is None:
        raise RuntimeError("auth-pod DB pool unavailable")
    with _pool.connection() as conn:
        yield conn


def upsert_user(oid: str, email: str, display_name: str, groups: list[str]) -> dict:
    """First-login: INSERT users with default role · subsequent: keep role/scope (admin can edit)."""
    role, scope_wh_id, scope_store_id = _map_groups_to_role(groups)
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, email, display_name, role, scope_wh_id, scope_store_id, created_at, last_login_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    last_login_at = NOW()
                RETURNING user_id, email, display_name, role, scope_wh_id, scope_store_id
            """, (oid, email, display_name, role, scope_wh_id, scope_store_id))
            row = cur.fetchone()
        conn.commit()
    cols = ("user_id", "email", "display_name", "role", "scope_wh_id", "scope_store_id")
    return dict(zip(cols, row))


def _map_groups_to_role(groups: list[str]) -> tuple[str, int | None, int | None]:
    """Entra group → BookFlow role mapping (BF-Admin / BF-HeadQuarter / BF-Logistics / BF-Branch)."""
    g = set(groups)
    if "BF-Admin" in g or "BF-HeadQuarter" in g:
        return ("hq-admin", None, None)
    if "BF-Logistics" in g:
        return ("wh-manager", 1, None)  # 수도권 default · admin 편집 가능
    if "BF-Branch" in g:
        return ("branch-clerk", None, settings.default_store_id)
    return (settings.default_role, None, settings.default_store_id)
