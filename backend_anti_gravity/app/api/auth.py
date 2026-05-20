"""
api/auth.py — Authentication routes: /auth/signup, /auth/login, /auth/me.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend_anti_gravity.app.api.deps import get_current_user, get_db
from backend_anti_gravity.app.core.config import settings
from backend_anti_gravity.app.core.security import create_access_token, hash_password, verify_password
from backend_anti_gravity.app.models.auth import Role, User, UserRole
from backend_anti_gravity.app.schemas.auth import TokenResponse, UserLogin, UserOut, UserRegister, UserUpdate

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.
    - Validates unique username/email.
    - Hashes password with bcrypt before persistence.
    - Assigns requested roles (defaults to PROCUREMENT_MGR).
    """
    # Uniqueness checks
    existing = await db.execute(
        select(User).where(
            (User.username == payload.username) | (User.email == payload.email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already registered.")

    import uuid
    user = User(
        user_code=f"USR-{str(uuid.uuid4())[:8]}",
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.flush()  # get user.id before assigning roles

    # Assign roles
    for role_name in payload.roles:
        role_result = await db.execute(select(Role).where(Role.role_code == role_name))
        role = role_result.scalar_one_or_none()
        if not role:
            # Auto-create role if missing (first-run scenario)
            role = Role(role_code=role_name, role_name=role_name, role_description=f"Auto-created role: {role_name}")
            db.add(role)
            await db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))

    await db.commit()
    await db.refresh(user)

    # Reload with roles eagerly
    result = await db.execute(
        select(User).options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == user.id)
    )
    user = result.scalar_one()
    user.roles  # trigger property access
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Authenticate and issue a JWT bearer token.
    Updates last_login timestamp on successful authentication.
    """
    result = await db.execute(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.username == payload.username)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")

    roles = [ur.role.name for ur in user.user_roles if ur.role]
    token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "roles": roles}
    )

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user_id=user.id,
        username=user.username,
        roles=roles,
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update mutable fields on the authenticated user's profile."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.email is not None:
        current_user.email = payload.email
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/users", response_model=List[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all registered users (authenticated access)."""
    result = await db.execute(
        select(User).options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    return result.scalars().all()
