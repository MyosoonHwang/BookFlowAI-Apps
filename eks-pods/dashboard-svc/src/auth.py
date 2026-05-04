"""mock auth — same pattern as inventory/forecast/decision pods.

Phase 4: Entra OIDC swap (azure-entra-mock RS256 ready).
"""
from fastapi import Header, HTTPException, status

ROLE_USERS = {
    "hq-admin":     ("00000000-0000-0000-0000-000000000001", "hq-admin",     None, None),
    "wh-manager-1": ("00000000-0000-0000-0000-000000000002", "wh-manager",      1, None),
    "wh-manager-2": ("00000000-0000-0000-0000-000000000003", "wh-manager",      2, None),
    "branch-clerk": ("00000000-0000-0000-0000-000000000004", "branch-clerk", None,    1),
}


class AuthContext:
    __slots__ = ("user_id", "role", "scope_wh_id", "scope_store_id", "token")

    def __init__(self, user_id, role, scope_wh_id, scope_store_id, token):
        self.user_id = user_id
        self.role = role
        self.scope_wh_id = scope_wh_id
        self.scope_store_id = scope_store_id
        self.token = token


def parse_bearer(authorization: str | None) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token.startswith("mock-token-"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="non-mock token")
    role_key = token.removeprefix("mock-token-")
    user = ROLE_USERS.get(role_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"unknown role: {role_key}")
    return AuthContext(*user, token=authorization)


def require_auth(authorization: str | None = Header(default=None)) -> AuthContext:
    return parse_bearer(authorization)


def _check_store_scope(ctx: AuthContext, store_id: int) -> None:
    """FR-A7.3 branch-clerk 매장 스코프 enforce.

    매장 단위 endpoint 진입 시 호출 — branch-clerk 가 자기 매장 외 store_id 조회 시 403.
    hq-admin / wh-manager 는 전사 / 권역 + 타 센터 read 권한 (FR-A7.1 · A7.2) → 통과.
    """
    if ctx.role == "branch-clerk":
        if ctx.scope_store_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="branch-clerk scope_store_id 부재 (인증 토큰 손상)",
            )
        if ctx.scope_store_id != store_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"자기 매장만 조회 가능 (scope_store_id={ctx.scope_store_id} · 요청 store_id={store_id})",
            )
