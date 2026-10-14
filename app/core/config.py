from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["dev", "test", "prod"] = "dev"
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, gt=0)
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    ENABLE_DOCS: bool | None = None
    PROFESSOR_INVITE_CODE: str = ""
    APP_TIMEZONE: str = "America/Sao_Paulo"
    REDIS_URL: str = ""
    LOG_LEVEL: str = "INFO"

    # LLM / embeddings (see docs/spec-ai.md section 2); unused until phase 03.
    LLM_PROVIDER: str = "fake"
    LLM_MODEL: str = ""
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_TIMEOUT_SECONDS: float = 30
    LLM_MAX_RETRIES: int = 2
    EMBEDDING_PROVIDER: str = ""
    EMBEDDING_MODEL: str = ""
    EMBEDDING_DIM: int = 768
    GEMINI_API_KEY: str = ""  # deprecated: removed in phase 03 in favour of LLM_API_KEY

    AI_DAILY_QUOTA_STUDENT: int = 30
    AI_DAILY_QUOTA_PROFESSOR: int = 100
    AI_FEEDBACK_ENABLED: bool = True
    AI_RUBRIC_EVALUATION_ENABLED: bool = False
    AGENT_MAX_ITERATIONS: int = 2
    AGENT_CRITIC_ENABLED: bool = True
    SURPRISE_BONUS_PROBABILITY: float = Field(0.25, ge=0, le=1)
    DEMO_PASSWORD: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("APP_TIMEZONE")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value

    @model_validator(mode="after")
    def _apply_defaults_and_checks(self) -> "Settings":
        if self.ENABLE_DOCS is None:
            self.ENABLE_DOCS = self.ENVIRONMENT != "prod"
        if self.ENVIRONMENT == "prod":
            self.validate_production()
        return self

    def validate_production(self) -> None:
        """Hook for production checks (SEC-01, SEC-02); implemented in phase 02."""


settings = Settings()
