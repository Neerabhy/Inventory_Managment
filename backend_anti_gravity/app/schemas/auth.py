"""
schemas/auth.py — Pydantic v2 request/response models for the authentication layer.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class RoleOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    model_config = {"from_attributes": True}


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=200)
    roles: List[str] = Field(
        default=["PROCUREMENT_MGR"],
        description="List of role codes to assign: SYS_ADMIN | PROCUREMENT_MGR | RETURN_APPROVER",
    )

    @field_validator("roles")
    @classmethod
    def _valid_roles(cls, v: List[str]) -> List[str]:
        allowed = {"SYS_ADMIN", "PROCUREMENT_MGR", "RETURN_APPROVER", "WAREHOUSE_OPS", "SALES_ANALYST", "FRAUD_ANALYST", "ML_ENGINEER"}
        for role in v:
            if role not in allowed:
                raise ValueError(f"Invalid role '{role}'. Allowed: {allowed}")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Expiry in seconds")
    user_id: int
    username: str
    roles: List[str]


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    roles: List[str] = []
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=200)
    email: Optional[EmailStr] = None
