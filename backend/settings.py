"""Environment-based application configuration."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


EnvironmentName = Literal["development", "dev", "staging", "production", "prod"]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    ENVIRONMENT: EnvironmentName = Field(
        default="development",
        description="Deployment environment: development/dev, staging, or production/prod.",
    )
    DATABASE_URL: str = Field(
        description="Postgres connection URL, including SSL mode in production."
    )
    GEMINI_API_KEY: str = Field(
        default="not-configured-yet",
        description="Google Gemini API key for the primary embedding provider."
    )
    OPENAI_API_KEY: str = Field(
        default="not-configured-yet",
        description="OpenAI API key used for LLM and embedding calls.",
    )
    OPENAI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-large",
        description="OpenAI embedding model used for code memory indexing.",
    )
    OPENAI_EMBEDDING_DIMENSIONS: int = Field(
        default=768,
        gt=0,
        description="Embedding dimensionality stored in pgvector. Must match Vector(N) in models.py.",
    )
    GITHUB_APP_ID: int = Field(
        default=0,
        ge=0,
        description="Numeric GitHub App ID used to mint installation access tokens.",
    )
    GITHUB_WEBHOOK_SECRET: str = Field(
        default="not-configured-yet",
        description="Shared secret used to verify GitHub webhook signatures.",
    )
    GITHUB_PRIVATE_KEY_PATH: str = Field(
        default="not-configured-yet",
        description="Filesystem path to the GitHub App private key PEM file.",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for ARQ background jobs.",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Python logging level for application logs.",
    )
    API_HOST: str = Field(
        default="0.0.0.0",
        description="Host interface where the FastAPI server binds.",
    )
    API_PORT: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="TCP port where the FastAPI server listens.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Ensure the database URL targets a Postgres-compatible instance."""
        valid_prefixes = ("postgres://", "postgresql://", "postgresql+asyncpg://", "postgresql+psycopg://")
        if not value.startswith(valid_prefixes):
            raise ValueError(f"DATABASE_URL must start with one of {valid_prefixes}")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize and validate the configured logging level."""
        normalized = value.upper()
        allowed_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if normalized not in allowed_levels:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed_levels)}")
        return normalized


settings = Settings()