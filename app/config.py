"""Centralized application configuration using Pydantic Settings.

Loads configuration from environment variables and `.env` file with
full validation, type coercion, and sensible defaults.

Usage:
    from app.config import get_settings

    settings = get_settings()  # cached singleton
    print(settings.OPENROUTER_MODEL)
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file.

    Required:
        OPENROUTER_API_KEY: Must be set — the app will refuse to start without it.

    All other fields have sensible defaults and are optional overrides.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # silently ignore unknown env vars
    )

    # ── Flask ──────────────────────────────────────────────────────────
    FLASK_ENV: str = Field(default="development", description="Flask environment (development/production)")
    FLASK_DEBUG: bool = Field(default=True, description="Enable Flask debug mode")
    SECRET_KEY: str = Field(default="change-me-in-production", description="Flask secret key for sessions")

    # ── OpenRouter LLM ────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = Field(..., description="OpenRouter API key (required)")
    OPENROUTER_BASE_URL: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL",
    )
    OPENROUTER_MODEL: str = Field(
        default="google/gemini-2.0-flash-001",
        description="LLM model identifier",
    )

    # ── External API Base URLs ────────────────────────────────────────
    JIKAN_BASE_URL: str = Field(default="https://api.jikan.moe/v4", description="Jikan API v4 base URL")
    TVMAZE_BASE_URL: str = Field(default="https://api.tvmaze.com", description="TV Maze API base URL")
    OPENLIBRARY_BASE_URL: str = Field(default="https://openlibrary.org", description="Open Library API base URL")

    # ── Rate Limiting (seconds between requests) ─────────────────────
    JIKAN_RATE_LIMIT: float = Field(default=1.0, ge=0.0, description="Min delay between Jikan requests (sec)")
    TVMAZE_RATE_LIMIT: float = Field(default=0.5, ge=0.0, description="Min delay between TVMaze requests (sec)")
    OPENLIBRARY_RATE_LIMIT: float = Field(default=1.0, ge=0.0, description="Min delay between Open Library requests (sec)")

    # ── HTTP Client ───────────────────────────────────────────────────
    HTTP_TIMEOUT: int = Field(default=30, ge=1, le=120, description="HTTP request timeout (seconds)")
    HTTP_MAX_RETRIES: int = Field(default=3, ge=0, le=10, description="Max retry attempts for failed HTTP requests")

    # ── Logging ───────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO", description="Logging level (DEBUG/INFO/WARNING/ERROR)")
    LOG_FORMAT: str = Field(default="json", description="Log output format ('json' for prod, 'console' for dev)")

    # ── Conversation / Sessions ───────────────────────────────────────
    MAX_CONVERSATION_HISTORY: int = Field(default=20, ge=1, le=100, description="Max messages to keep per session")
    SESSION_TTL_SECONDS: int = Field(default=3600, ge=60, description="Idle session TTL before cleanup (seconds)")

    # ── Cache ─────────────────────────────────────────────────────────
    CACHE_TTL_SECONDS: int = Field(default=300, ge=0, description="API response cache TTL (seconds)")
    CACHE_MAX_SIZE: int = Field(default=256, ge=1, description="Max number of cached API responses")

    # ── Conversation Logging ─────────────────────────────────────────
    CONVERSATION_LOG_DIR: str = Field(default="logs/conversations", description="Directory for conversation log files")
    CONVERSATION_LOG_ENABLED: bool = Field(default=True, description="Enable conversation logging")

    # ── Vector DB (ChromaDB) ─────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = Field(default="data/chromadb", description="ChromaDB persistence directory")
    CHROMA_COLLECTION_NAME: str = Field(default="conversations", description="ChromaDB collection name")
    CONTEXT_MAX_RESULTS: int = Field(default=3, ge=1, le=10, description="Max context results to retrieve")
    CONTEXT_SIMILARITY_THRESHOLD: float = Field(default=1.2, ge=0.0, le=2.0, description="Max distance for context relevance")

    # ── Validators ────────────────────────────────────────────────────

    @field_validator("OPENROUTER_API_KEY")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Ensure the API key is not empty or a placeholder."""
        v = v.strip()
        if not v or v in ("sk-or-v1-xxxxx", "your-api-key-here", ""):
            raise ValueError(
                "OPENROUTER_API_KEY must be set to a valid API key. "
                "Get one at https://openrouter.ai/keys"
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        """Warn if using the default secret key in production."""
        # info.data contains already-validated fields
        env = info.data.get("FLASK_ENV", "development")
        if env == "production" and v == "change-me-in-production":
            raise ValueError(
                "SECRET_KEY must be changed from the default in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Normalize and validate log level."""
        v = v.upper().strip()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}, got '{v}'")
        return v

    @field_validator("LOG_FORMAT")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        v = v.lower().strip()
        if v not in ("json", "console"):
            raise ValueError("LOG_FORMAT must be 'json' or 'console'")
        return v

    @field_validator("JIKAN_BASE_URL", "TVMAZE_BASE_URL", "OPENLIBRARY_BASE_URL", "OPENROUTER_BASE_URL")
    @classmethod
    def validate_urls(cls, v: str) -> str:
        """Ensure base URLs don't have trailing slashes."""
        return v.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance.

    Uses `lru_cache` so the `.env` file is only read once.
    Call this everywhere instead of instantiating Settings directly.
    """
    return Settings()
