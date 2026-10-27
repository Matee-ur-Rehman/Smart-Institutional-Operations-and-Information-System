"""Application settings, read from environment variables / backend/.env.

TEMPORARY STUB written by Member 2 so the repo runs before Member 1's core lands.
Owner: Member 1 (Faizan). When his app/core/ is merged, take his version of this file.
The setting names below are the ones listed in docs/INTEGRATION_GUIDE.md section 7.
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg2://school_user:CHANGE_ME@localhost:5432/school_db"
    jwt_secret_key: str = "CHANGE_ME_DEV_ONLY"
    jwt_access_minutes: int = 30
    jwt_refresh_days: int = 7
    cors_origins: str = "http://localhost:5000,http://localhost:3000"
    seed_default_password: str = ""

    # Member 2
    upload_dir: str = "./uploads"
    max_upload_mb: int = 5
    fcm_enabled: bool = False
    fcm_credentials_file: str = ""

    @model_validator(mode="after")
    def _refuse_default_secret_in_production(self):
        if self.app_env.lower() == "production" and self.jwt_secret_key.startswith("CHANGE_ME"):
            raise ValueError("JWT_SECRET_KEY must be set to a real secret when APP_ENV=production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
