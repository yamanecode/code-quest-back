"""Manual check against a real provider: `uv run pytest tests/live -m live`.

Needs LLM_BASE_URL, LLM_MODEL and LLM_API_KEY. Never part of the default run or the phase gate.
"""

import pytest

from app.core.config import get_settings
from app.domain.challenge_types import ChallengeType
from app.infra.llm.openai_compatible import OpenAICompatibleClient
from app.services.prompts import ChallengeText, hint_prompt
from tests.samples import CONTENT

pytestmark = pytest.mark.live


def test_T_AI_LIVE_01_real_provider_answers_a_hint_prompt():
    settings = get_settings()
    if not (settings.LLM_BASE_URL and settings.LLM_MODEL):
        pytest.fail("set LLM_BASE_URL, LLM_MODEL and LLM_API_KEY to run the live test")
    client = OpenAICompatibleClient(settings.LLM_BASE_URL, settings.LLM_MODEL, settings.LLM_API_KEY)
    challenge = ChallengeText(
        ChallengeType.ORDERING,
        "Contar até três",
        "Coloque os números na ordem em que se conta.",
        CONTENT[ChallengeType.ORDERING],
    )
    prompt = hint_prompt(challenge, level=1, previous_hints=[])

    reply = client.complete(prompt.system, prompt.user, max_tokens=200)

    assert reply.strip()
