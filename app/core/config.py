from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET_VALUES = frozenset(
    {
        "change-me",
        "super-secret-admin-token",
        "replace-with-local-dev-secret-key",
        "replace-with-local-dev-admin-token",
    }
)

DEFAULT_ENV_FILES = (
    ".env",
    ".env.example",
)


def get_existing_env_files() -> tuple[str, ...]:
    return tuple(
        env_file for env_file in DEFAULT_ENV_FILES if Path(env_file).exists()
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=get_existing_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Football Analytics Platform")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    secret_key: str = Field(default="change-me")
    admin_token: str = Field(default="super-secret-admin-token")
    database_url: str = Field(
        default=(
            "postgresql+asyncpg://postgres:postgres@localhost:5433/"
            "football_analytics"
        )
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    api_v1_prefix: str = Field(default="/api/v1")
    telegram_bot_token: str | None = Field(default=None)
    enable_telegram_bot: bool = Field(default=False)
    seed_on_startup: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    cache_ttl_seconds: int = Field(default=300)
    cache_fallback_enabled: bool = Field(default=True)

    @model_validator(mode="after")
    def require_production_secrets(self) -> "Settings":
        if self.app_env.lower() != "production":
            return self

        unsafe_fields = []
        if self.secret_key in PLACEHOLDER_SECRET_VALUES:
            unsafe_fields.append("SECRET_KEY")
        if self.admin_token in PLACEHOLDER_SECRET_VALUES:
            unsafe_fields.append("ADMIN_TOKEN")

        if unsafe_fields:
            joined_fields = ", ".join(unsafe_fields)
            raise ValueError(
                f"Production environment requires non-placeholder values for "
                f"{joined_fields}."
            )

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
