"""
core/config.py
==============
Centralized environment & application configuration parsed via Pydantic BaseSettings.
All values are sourced from the .env file at startup, with type-safe defaults.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import List, Literal, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment variables / .env file.
    Validated at startup — any missing required value raises a clear error.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Server
    # ------------------------------------------------------------------ #
    port: int = Field(default=8000, description="TCP port the server listens on")
    host: str = Field(default="0.0.0.0", description="Bind address")
    environment: Literal["development", "production", "testing"] = "production"
    debug: bool = False

    # ------------------------------------------------------------------ #
    # Security & JWT
    # ------------------------------------------------------------------ #
    jwt_secret_key: str = Field(..., description="HMAC signing secret — keep private")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    database_url: str = Field(
        default="sqlite+aiosqlite:///./electro_inventory_v3.db",
        description="Async SQLAlchemy connection string",
    )

    # ------------------------------------------------------------------ #
    # LLM Provider
    # ------------------------------------------------------------------ #
    llm_provider: Literal["openai", "azure_openai", "gemini", "anthropic"] = "azure_openai"
    llm_model: str = "gpt-4o"

    openai_api_key: str = Field(default="", description="OpenAI API key")
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    anthropic_api_key: str = Field(default="", description="Anthropic Claude API key")

    # Azure OpenAI
    azure_openai_api_key: str = Field(default="", description="Azure OpenAI API key")
    azure_openai_endpoint: str = Field(default="", description="Azure OpenAI endpoint URL")
    azure_openai_deployment: str = Field(default="gpt-4o", description="Azure deployment name")
    azure_openai_api_version: str = Field(default="2024-02-01", description="Azure OpenAI API version")

    # ------------------------------------------------------------------ #
    # Email / Reports
    # ------------------------------------------------------------------ #
    smtp_host: str = Field(default="", description="SMTP host for report emails")
    smtp_port: int = Field(default=587, description="SMTP port for report emails")
    smtp_username: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    smtp_from_email: str = Field(default="reports@ai-inventory-copilot.local", description="Report sender")
    smtp_use_tls: bool = True

    # ------------------------------------------------------------------ #
    # System Baseline
    # ------------------------------------------------------------------ #
    current_year: int = 2026

    # ------------------------------------------------------------------ #
    # CORS — Frontend Origins
    # ------------------------------------------------------------------ #
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

    # ------------------------------------------------------------------ #
    # Business Constants
    # ------------------------------------------------------------------ #
    serviceable_cities: List[str] = [
        "Delhi",
        "Mumbai",
        "Bangalore",
        "Jaipur",
        "Kolkata",
    ]

    # Minimum risk score below which auto-approval is permitted
    return_auto_approve_threshold: float = 0.35

    @field_validator("jwt_secret_key", mode="before")
    def _non_empty_secret(cls, v: str) -> str:
        if not v or len(v) < 16:
            raise ValueError("JWT_SECRET_KEY must be at least 16 characters long.")
        return v

    @field_validator("azure_openai_endpoint", mode="before")
    def _sanitize_endpoint(cls, v: str) -> str:
        """
        Strips trailing slashes from the Azure endpoint. The official OpenAI 
        Python SDK fails with an HTTP 404 if the base URL ends with a trailing slash.
        """
        if isinstance(v, str):
            return v.rstrip("/")
        return v

    @field_validator("allowed_origins", "serviceable_cities", mode="before")
    def _parse_environment_lists(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
