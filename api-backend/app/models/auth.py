"""
models/auth.py — Role, User, UserRole ORM models.
Mapped to the actual inventory-database schema.
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column("role_id", Integer, primary_key=True, autoincrement=True)
    role_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    role_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())

    user_roles: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="role")

    # Frontend compatibility
    @property
    def name(self) -> str:
        return self.role_code

    @property
    def description(self) -> Optional[str]:
        return self.role_description

    def __repr__(self) -> str:
        return f"<Role id={self.id} code={self.role_code!r}>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column("user_id", Integer, primary_key=True, autoincrement=True)
    user_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_login: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user_roles: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="user")

    # Frontend compatibility
    @property
    def hashed_password(self) -> str:
        return self.password_hash

    @property
    def is_superuser(self) -> bool:
        return any(ur.role.role_code == "SYS_ADMIN" for ur in self.user_roles if ur.role)

    @property
    def roles(self) -> List[str]:
        return [ur.role.role_code for ur in self.user_roles if ur.role]

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id: Mapped[int] = mapped_column("user_role_id", Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False, index=True)
    granted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    granted_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())
    expires_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="user_roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")

    @property
    def assigned_at(self) -> str:
        return self.granted_at
