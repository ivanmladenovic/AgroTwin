from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AgroTwin"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:5174"

    storage_backend: str = "local"
    storage_local_path: str = "var/storage"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "auto"

    ai_provider: str = "local"
    ai_api_key: str | None = None
    ai_base_url: str = "https://api.openai.com/v1"
    ai_chat_model: str = "gpt-4o-mini"
    ai_embedding_model: str = "text-embedding-3-small"
    ai_vision_model: str | None = None
    ai_embedding_dim: int = 1536
    # Cross-provider chat/vision fallback when primary (usually Gemini) is overloaded.
    ai_openai_base_url: str = "https://api.openai.com/v1"
    ai_openai_fallback_models: str = "gpt-4.1-mini,gpt-4o"

    # Benchmark providers (developer tool). Keys stay on the server only.
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    openai_benchmark_model: str = "gpt-5"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    openai_benchmark_base_url: str = "https://api.openai.com/v1"
    benchmark_temperature: float = 0.2
    benchmark_max_output_tokens: int = 2048
    benchmark_timeout_seconds: float = 90.0
    benchmark_rate_limit_per_minute: int = 10
    benchmark_max_image_bytes: int = 8 * 1024 * 1024
    benchmark_max_image_edge: int = 4096
    benchmark_gemini_input_usd_per_mtok: float = 0.75
    benchmark_gemini_output_usd_per_mtok: float = 3.75
    benchmark_openai_input_usd_per_mtok: float = 1.25
    benchmark_openai_output_usd_per_mtok: float = 10.0

    yr_user_agent: str = "AgroTwin/1.0 (contact@agrotwin.com)"

    soilgrids_base_url: str = "https://rest.isric.org"
    soilgrids_user_agent: str = "AgroTwin/1.0 (contact@agrotwin.com)"
    soilgrids_timeout_seconds: float = 90
    soilgrids_cache_days: int = 30
    soilgrids_min_interval_seconds: float = 12
    soilgrids_min_refresh_seconds: int = 3600

    postgres_user: str = "agrotwin"
    postgres_password: str = "agrotwin"
    postgres_db: str = "agrotwin"
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    database_url: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return _normalize_database_url(self.database_url)
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


def _normalize_database_url(url: str) -> str:
    """Accept Render/Heroku-style postgres:// URLs for psycopg3."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://") and "+psycopg" not in url.split("://", 1)[0]:
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
