from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None
    JWT_SECRET: str
    JWT_EXPIRE_HOURS: int = 8
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    HINT_CAP: int = 5
    HINT_COOLDOWN_SECONDS: int = 15
    LLM_PROVIDER: str = "fake"
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    LLM_API_KEY: str = ""
    FAKE_LLM_LOG: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
