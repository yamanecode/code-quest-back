"""Manual checks against a real provider: `uv run pytest tests/live -m live`.

Needs LLM_BASE_URL, LLM_MODEL and LLM_API_KEY (and LLM_REASONING_EFFORT for reasoning models).
Never part of the default run or the quality gate.
"""

import pytest

from app.core.config import get_settings
from app.domain.challenge_types import ChallengeDraft, ChallengeType
from app.infra.llm.openai_compatible import OpenAICompatibleClient
from app.services.ai_service import DRAFT_MAX_TOKENS, _parse_draft
from app.services.prompts import draft_prompt, hint_prompt
from tests.samples import CONTENT

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client() -> OpenAICompatibleClient:
    settings = get_settings()
    if not (settings.LLM_BASE_URL and settings.LLM_MODEL):
        pytest.fail("set LLM_BASE_URL, LLM_MODEL and LLM_API_KEY to run the live tests")
    return OpenAICompatibleClient(
        settings.LLM_BASE_URL,
        settings.LLM_MODEL,
        settings.LLM_API_KEY,
        settings.LLM_REASONING_EFFORT,
    )


def test_T_AI_LIVE_01_real_provider_answers_a_hint_prompt(client):
    challenge = ChallengeDraft(
        "Contar até três",
        "Coloque os números na ordem em que se conta.",
        ChallengeType.ORDERING,
        CONTENT[ChallengeType.ORDERING],
    )
    prompt = hint_prompt(challenge, level=1, previous_hints=[])

    reply = client.complete(prompt.system, prompt.user, max_tokens=200)

    assert reply.strip()


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_AI_LIVE_02_first_draft_passes_the_template_and_draft_rules(client, challenge_type):
    # One attempt only: the service would retry once, so this is the stricter check.
    prompt = draft_prompt(challenge_type, "organizar uma excursão da escola", [])

    reply = client.complete(prompt.system, prompt.user, max_tokens=DRAFT_MAX_TOKENS)

    draft, errors = _parse_draft(challenge_type, reply)
    assert errors == [], reply
    assert draft is not None
