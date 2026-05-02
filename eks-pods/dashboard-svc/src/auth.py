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
