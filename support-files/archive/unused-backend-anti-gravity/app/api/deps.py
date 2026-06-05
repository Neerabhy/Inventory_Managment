"""
api/deps.py — FastAPI shared dependency injection: DB session, current user, RBAC guards.
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend_anti_gravity.app.core.database import get_db
from backend_anti_gravity.app.core.security import decode_access_token
from app.models.auth import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extracts and validates the JWT bearer token from the Authorization header.
    Returns the authenticated User ORM object with roles eagerly loaded.
    Raises HTTP 401 on any token validation failure.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or malformed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: int = int(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or disabled.",
        )
    return user


def require_roles(allowed_roles: List[str]):
    """
    RBAC guard factory.  Returns a FastAPI dependency that enforces role membership.
    Usage:
        @router.post("/admin-only", dependencies=[Depends(require_roles(["SYS_ADMIN"]))])
    """
    async def _guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user
        user_roles = {ur.role.name for ur in current_user.user_roles if ur.role}
        if not user_roles.intersection(set(allowed_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {allowed_roles}",
            )
        return current_user
    return _guard


# ── Convenience role guards ──────────────────────────────────────────
require_admin = require_roles(["SYS_ADMIN"])
require_procurement = require_roles(["SYS_ADMIN", "PROCUREMENT_MGR"])
require_returns = require_roles(["SYS_ADMIN", "RETURN_APPROVER"])
