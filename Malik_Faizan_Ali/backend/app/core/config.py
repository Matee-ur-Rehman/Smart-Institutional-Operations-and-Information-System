"""Application settings, read from environment variables / backend/.env (never committed)."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://school_user:CHANGE_ME@localhost:5432/school_db"
    TEST_DATABASE_URL: str = "postgresql+psycopg2://school_user:CHANGE_ME@localhost:5432/school_test_db"
    JWT_SECRET_KEY: str = "CHANGE_ME_LONG_RANDOM_STRING"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_MINUTES: int = 30
    JWT_REFRESH_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5000,http://localhost:3000"
    APP_ENV: str = "development"
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    SEED_ADMIN_PASSWORD: str = ""
    SEED_USER_PASSWORD: str = ""

    # Member 2
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 5
    FCM_ENABLED: bool = False
    FCM_CREDENTIALS_FILE: str = ""

    @field_validator("FCM_ENABLED", mode="before")
    @classmethod
    def _bool(cls, v):  # tolerate "" in .env
        return False if v in ("", None) else v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
