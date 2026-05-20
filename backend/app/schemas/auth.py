from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    username: str = Field(..., max_length=50, examples=["ops_manager_2026"])
    email: EmailStr = Field(..., examples=["manager@retail-aios.com"])
    role: str = Field(default="OPERATOR", description="ADMIN, MANAGER, or OPERATOR")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, examples=["SecurePass123!"])

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

class TokenData(BaseModel):
    username: Optional[str] = None