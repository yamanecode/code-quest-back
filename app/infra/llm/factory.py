from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.ports import LLMClient
from app.infra.llm.daily_limit import DailyLimitedLLMClient
from app.infra.llm.fake import FakeLLMClient
from app.infra.llm.openai_compatible import OpenAICompatibleClient


def build_llm_client(
    settings: Settings,
    sessions: sessionmaker[Session] | None = None,
    clock: Clock | None = None,
) -> LLMClient:
    """The configured client; with LLM_DAILY_LIMIT > 0 it counts its calls in `sessions`."""
    client = _provider_client(settings)
    if settings.LLM_DAILY_LIMIT <= 0:
        return client
    if sessions is None or clock is None:
        raise ValueError("LLM_DAILY_LIMIT needs a session factory and a clock")
    return DailyLimitedLLMClient(client, settings.LLM_DAILY_LIMIT, sessions, clock)


def _provider_client(settings: Settings) -> LLMClient:
    if settings.LLM_PROVIDER == "fake":
        return FakeLLMClient(log_path=settings.FAKE_LLM_LOG or None)
    if settings.LLM_PROVIDER == "openai_compatible":
        return OpenAICompatibleClient(
            settings.LLM_BASE_URL,
            settings.LLM_MODEL,
            settings.LLM_API_KEY,
            settings.LLM_REASONING_EFFORT,
        )
    raise ValueError(f"unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
