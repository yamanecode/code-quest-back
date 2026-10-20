from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.ports import LLMError
from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, HintSource, Role
from app.domain.hint_leak import hint_reveals_solution
from app.infra.db.models import HintEvent
from app.services.ai_service import FALLBACK_HINTS, NEUTRAL_HINT
from tests.integration.answers import as_student
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
)
from tests.samples import CONTENT, CORRECT_ANSWER, WRONG_ANSWER

pytestmark = pytest.mark.usefixtures("badge_catalog")

COOLDOWN = timedelta(seconds=15)
SAFE_HINT = "Pense no que precisa acontecer antes de tudo. Qual seria o primeiro passo?"


@pytest.fixture
def student(session):
    return make_user(session, "aluna")


@pytest.fixture
def headers(student, clock):
    return bearer(student, clock)


@pytest.fixture
def challenge(session):
    return make_challenge(session, missions=(make_mission(session),))


def ask_hint(client, headers, challenge):
    return client.post(f"/api/challenges/{challenge.id}/hints", headers=headers)


def view(client, headers, challenge) -> dict:
    return client.get(f"/api/challenges/{challenge.id}", headers=headers).json()


def submit(client, headers, challenge, answer):
    url = f"/api/challenges/{challenge.id}/submissions"
    return client.post(
        url, json={"answer": as_student(client, headers, challenge, answer)}, headers=headers
    )


def hint_events(session, student) -> list[HintEvent]:
    query = select(HintEvent).filter_by(user_id=student.id).order_by(HintEvent.id)
    return list(session.scalars(query))


def test_T_AI_HINT_01_returns_level_1_hint_and_decrements_hints_left(
    client, session, student, headers, challenge, llm, clock
):
    llm.replies.append(SAFE_HINT)
    before = view(client, headers, challenge)
    assert (before["hints_left"], before["cooldown_seconds_left"]) == (5, 0)

    response = ask_hint(client, headers, challenge)

    assert response.status_code == 200
    assert response.json() == {
        "hint": SAFE_HINT,
        "level": 1,
        "hints_left": 4,
        "cooldown_seconds": 15,
    }
    [event] = hint_events(session, student)
    assert (event.source, event.level, event.text, event.discarded_count) == (
        HintSource.REQUEST,
        1,
        SAFE_HINT,
        0,
    )
    clock.advance(timedelta(seconds=10))
    shown = view(client, headers, challenge)
    assert (shown["hints_left"], shown["cooldown_seconds_left"]) == (4, 5)


def test_T_AI_HINT_02_levels_go_1_2_3_3_and_previous_hints_reach_the_prompt(
    client, headers, challenge, llm, clock
):
    texts = [f"Dica {n}: pense com calma. O que vem antes?" for n in range(1, 5)]
    llm.replies.extend(texts)

    bodies = []
    for _ in texts:
        bodies.append(ask_hint(client, headers, challenge).json())
        clock.advance(COOLDOWN)

    assert [b["level"] for b in bodies] == [1, 2, 3, 3]
    assert [b["hints_left"] for b in bodies] == [4, 3, 2, 1]
    assert "Nível da dica: 3" in llm.prompts[3].user
    for earlier in texts[:3]:
        assert earlier in llm.prompts[3].user


def test_T_AI_HINT_CAP_sixth_request_is_refused(client, headers, challenge, llm, clock):
    llm.replies.extend([SAFE_HINT] * 6)
    for _ in range(5):
        assert ask_hint(client, headers, challenge).status_code == 200
        clock.advance(COOLDOWN)

    response = ask_hint(client, headers, challenge)

    assert response.status_code == 409
    assert response.json()["detail"] == "hint_cap_reached"
    assert len(llm.prompts) == 5
    assert view(client, headers, challenge)["hints_left"] == 0


def test_T_AI_HINT_COOL_request_inside_the_wait_is_429_then_allowed(
    client, headers, challenge, llm, clock
):
    llm.replies.extend([SAFE_HINT, SAFE_HINT])
    ask_hint(client, headers, challenge)
    clock.advance(timedelta(seconds=5))

    early = ask_hint(client, headers, challenge)

    assert early.status_code == 429
    assert early.headers["Retry-After"] == "10"
    assert early.json()["detail"] == "hint_cooldown"
    assert early.json()["retry_after"] == 10
    assert len(llm.prompts) == 1
    clock.advance(timedelta(seconds=10))
    assert ask_hint(client, headers, challenge).status_code == 200


def test_T_AI_HINT_03_leaking_hint_retried_strictly_then_fallback(
    client, session, student, headers, challenge, llm
):
    # The sample ordering solution is "um", "dois", "três".
    llm.replies.extend(["Faça um, depois dois e por fim três.", "um, dois, três. Viu?"])

    response = ask_hint(client, headers, challenge)

    assert response.status_code == 200
    assert response.json()["hint"] == FALLBACK_HINTS[ChallengeType.ORDERING][1]
    assert response.json()["hints_left"] == 4
    assert "foi descartada" not in llm.prompts[0].user
    assert "foi descartada" in llm.prompts[1].user
    [event] = hint_events(session, student)
    assert (event.text, event.discarded_count) == (FALLBACK_HINTS[ChallengeType.ORDERING][1], 2)


def test_T_AI_HINT_03b_strict_retry_can_succeed(client, session, student, headers, challenge, llm):
    llm.replies.extend(["um, dois, três.", SAFE_HINT])

    response = ask_hint(client, headers, challenge)

    assert response.json()["hint"] == SAFE_HINT
    assert hint_events(session, student)[0].discarded_count == 1


def test_T_AI_HINT_04_first_wrong_answer_gets_a_hint_outside_the_cap(
    client, session, student, headers, challenge, llm
):
    llm.replies.extend(["Confira o que vem primeiro. Qual passo abre a sequência?", SAFE_HINT])

    first = submit(client, headers, challenge, WRONG_ANSWER[ChallengeType.ORDERING]).json()
    second = submit(client, headers, challenge, WRONG_ANSWER[ChallengeType.ORDERING]).json()

    assert first["hint"] == "Confira o que vem primeiro. Qual passo abre a sequência?"
    assert second["hint"] is None
    assert "Ordem enviada: três → dois → um" in llm.prompts[0].user
    assert "Nível da dica: 1" in llm.prompts[0].user
    assert len(llm.prompts) == 1
    shown = view(client, headers, challenge)
    assert (shown["hints_left"], shown["cooldown_seconds_left"]) == (5, 0)
    [event] = hint_events(session, student)
    assert (event.source, event.level) == (HintSource.AFTER_WRONG, 1)
    # No cooldown started, and the automatic hint is passed on as already shown.
    assert ask_hint(client, headers, challenge).json()["level"] == 1
    assert first["hint"] in llm.prompts[1].user


def test_T_AI_HINT_04b_correct_answer_never_calls_the_model(client, headers, challenge, llm):
    body = submit(client, headers, challenge, CORRECT_ANSWER[ChallengeType.ORDERING]).json()

    assert body["hint"] is None
    assert llm.prompts == []


def test_T_AI_HINT_05_solved_challenge_is_409(client, headers, challenge, llm):
    submit(client, headers, challenge, CORRECT_ANSWER[ChallengeType.ORDERING])

    response = ask_hint(client, headers, challenge)

    assert response.status_code == 409
    assert response.json()["detail"] == "already_solved"
    assert llm.prompts == []


def test_T_AI_HINT_06_invisible_challenge_is_404_and_professor_is_403(
    client, session, headers, llm, clock
):
    draft = make_challenge(session, status=ContentStatus.DRAFT, missions=(make_mission(session),))
    other_turma = make_challenge(
        session, missions=(make_mission(session, make_classroom(session)),)
    )
    professor = make_user(session, role=Role.PROFESSOR)

    assert ask_hint(client, headers, draft).status_code == 404
    assert ask_hint(client, headers, other_turma).status_code == 404
    assert ask_hint(client, bearer(professor, clock), draft).status_code == 403
    assert llm.prompts == []


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_AI_FALLBACK_01_model_failure_gives_the_fallback_hint(
    client, session, headers, llm, challenge_type
):
    challenge = make_challenge(
        session, challenge_type=challenge_type, missions=(make_mission(session),)
    )
    llm.replies.append(LLMError("timeout"))

    response = ask_hint(client, headers, challenge)

    assert response.status_code == 200
    assert response.json()["hint"] == FALLBACK_HINTS[challenge_type][1]
    assert response.json()["hints_left"] == 4


def test_T_AI_FALLBACK_01b_empty_reply_and_failure_after_wrong_give_fallbacks(
    client, headers, challenge, llm
):
    llm.replies.extend(["   ", LLMError("down")])

    requested = ask_hint(client, headers, challenge).json()
    automatic = submit(client, headers, challenge, WRONG_ANSWER[ChallengeType.ORDERING]).json()

    assert requested["hint"] == FALLBACK_HINTS[ChallengeType.ORDERING][1]
    assert automatic["hint"] == FALLBACK_HINTS[ChallengeType.ORDERING][1]


def test_T_AI_FALLBACK_01c_every_fallback_hint_is_safe_and_ends_with_a_question():
    assert set(FALLBACK_HINTS) == set(ChallengeType)
    for challenge_type, levels in FALLBACK_HINTS.items():
        assert set(levels) == {1, 2, 3}
        for text in levels.values():
            assert text.endswith("?")
            assert not hint_reveals_solution(challenge_type, CONTENT[challenge_type], text)


def test_T_AI_FALLBACK_04_fallback_matching_the_answer_is_replaced_by_a_neutral_hint(
    client, session, headers, llm
):
    # The level-1 pattern fallback mentions "termo"; here that word is the correct option.
    challenge = make_challenge(
        session, challenge_type=ChallengeType.PATTERN, missions=(make_mission(session),)
    )
    challenge.content = {
        "sequence": ["x", "y", "x"],
        "options": [
            {"id": "a", "text": "termo"},
            {"id": "b", "text": "y"},
            {"id": "c", "text": "z"},
            {"id": "d", "text": "w"},
        ],
        "solution": "a",
    }
    session.flush()
    assert hint_reveals_solution(
        ChallengeType.PATTERN, challenge.content, FALLBACK_HINTS[ChallengeType.PATTERN][1]
    )
    llm.replies.append(LLMError("down"))

    hint = ask_hint(client, headers, challenge).json()["hint"]

    assert hint == NEUTRAL_HINT
    assert not hint_reveals_solution(ChallengeType.PATTERN, challenge.content, hint)
