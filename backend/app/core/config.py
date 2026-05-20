import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl

class Settings(BaseSettings):
    # Read environment structures from root .env configuration mapping
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    # Server Operational Parameters
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    # Security Constraints
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database Mappings
    DATABASE_URL: str

    # Azure OpenAI Core Configuration
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT_NAME: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Business Engine Invariant Metrics
    CURRENT_YEAR: int = 2026
    
    # Global Allowed CORS Domains Core Array
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",  # Standard Vite Local Front-End URL
        "http://127.0.0.1:5173",
        "http://localhost:3000"
    ]

settings = Settings()