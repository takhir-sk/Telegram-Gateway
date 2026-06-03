from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus, urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_HOSTS = frozenset({"your-domain.com", "example.com"})


class Settings(BaseSettings):
    """
    Единый источник настроек приложения.
    Все значения задаются в файле .env (см. .env.example).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "production"] = "development"

    # --- MySQL (внешний VPS) ---
    SQL_HOST: str
    SQL_PORT: int = Field(default=49294, ge=1, le=65535)
    SQL_DB: str
    SQL_USER: str
    SQL_PASSWORD: str

    REDIS_URL: str

    TELEGRAM_API_URL: str = "https://api.telegram.org"
    GATEWAY_PUBLIC_URL: str

    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/var/log/telegram-gateway/app.log"
    LOG_RETENTION_DAYS: int = Field(default=90, ge=1)

    RATE_LIMIT: str = "100/minute"
    REQUEST_TIMEOUT: float = Field(default=15.0, gt=0)

    ALLOW_HTTP_TARGETS: bool = False


    @field_validator("GATEWAY_PUBLIC_URL")
    @classmethod
    def normalize_gateway_url(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        parsed = urlparse(self.GATEWAY_PUBLIC_URL)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("GATEWAY_PUBLIC_URL must be a valid http(s) URL")

        host = (parsed.hostname or "").lower()
        if "your-domain.com" in host:
            raise ValueError(
                "GATEWAY_PUBLIC_URL contains placeholder 'your-domain.com'. "
                "Set your real public URL in .env"
            )

        if self.APP_ENV == "production":
            if parsed.scheme != "https":
                raise ValueError("GATEWAY_PUBLIC_URL must use https in production")
            if host in _PLACEHOLDER_HOSTS:
                raise ValueError(
                    f"GATEWAY_PUBLIC_URL host '{host}' is not allowed in production"
                )

        if self.ALLOW_HTTP_TARGETS and self.APP_ENV == "production":
            raise ValueError("ALLOW_HTTP_TARGETS cannot be enabled in production")

        return self

    @property
    def DATABASE_URL_ASYNC(self) -> str:
        user = quote_plus(self.SQL_USER)
        password = quote_plus(self.SQL_PASSWORD)
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.SQL_HOST}:{self.SQL_PORT}/{self.SQL_DB}"
        )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
