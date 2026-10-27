from app.core.config import Settings
from app.core.ports import LLMClient
from app.infra.llm.fake import FakeLLMClient
from app.infra.llm.openai_compatible import OpenAICompatibleClient


def build_llm_client(settings: Settings) -> LLMClient:
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
