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

    yr_user_agent: str = "AgroTwin/1.0 (contact@agrotwin.com)"

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
            return self.database_url
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
