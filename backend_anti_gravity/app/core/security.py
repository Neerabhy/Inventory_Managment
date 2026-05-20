"""
core/security.py
================
Cryptographic utilities for the authentication layer:
  - Bcrypt password hashing via Passlib
  - JWT creation and verification via PyJWT
  - Token payload extraction helpers
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import bcrypt
from backend_anti_gravity.app.core.config import settings

def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Constant-time comparison of a plain-text password against its stored hash.
    """
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# ------------------------------------------------------------------ #
# JWT Token Creation
# ------------------------------------------------------------------ #
def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generate a signed JWT access token.

    Args:
        data: Payload dictionary (must include 'sub' = user identifier).
        expires_delta: Custom TTL.  Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: int) -> str:
    """
    Generate a longer-lived refresh token (30-day TTL).
    """
    return create_access_token(
        data={"sub": str(user_id), "type": "refresh"},
        expires_delta=timedelta(days=30),
    )


# ------------------------------------------------------------------ #
# JWT Token Verification & Decoding
# ------------------------------------------------------------------ #
def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises:
        jwt.ExpiredSignatureError: Token TTL has elapsed.
        jwt.InvalidTokenError:     Signature mismatch or malformed payload.
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def extract_token_subject(token: str) -> Optional[str]:
    """
    Safely extract the 'sub' field from a JWT without raising on failure.
    Returns None if the token is invalid or expired.
    """
    try:
        payload = decode_access_token(token)
        return payload.get("sub")
    except (ExpiredSignatureError, InvalidTokenError):
        return None


def extract_token_roles(token: str) -> list[str]:
    """
    Extract the roles list embedded in the JWT payload.
    Returns an empty list if the token is invalid or contains no roles.
    """
    try:
        payload = decode_access_token(token)
        return payload.get("roles", [])
    except (ExpiredSignatureError, InvalidTokenError):
        return []
