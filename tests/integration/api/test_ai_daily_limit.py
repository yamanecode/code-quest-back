import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_llm_client
from app.core.clock import TIMEZONE
from app.core.ports import LLMError, LLMLimitReached
from app.domain.challenge_types import ChallengeType
from app.domain.enums import Role
from app.infra.db.models import Challenge, LLMUsage, User
from app.infra.llm.daily_limit import DailyLimitedLLMClient
from app.services.ai_service import FALLBACK_HINTS, FALLBACK_SUGGESTIONS
from tests.integration.answers import as_student
from tests.integration.auth_helpers import bearer
from tests.integration.factories import make_challenge, make_mission, make_user
from tests.samples import WRONG_ANSWER

pytestmark = pytest.mark.usefixtures("badge_catalog")

LIMIT = 2
REPLY = "Pense no objetivo final. Qual passo vem antes de todos?"


@pytest.fixture
def sessions(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def limited(llm, sessions, clock) -> DailyLimitedLLMClient:
    return DailyLimitedLLMClient(llm, LIMIT, sessions, clock)


@pytest.fixture
def limited_client(client, limited):
    client.app.dependency_overrides[get_llm_client] = lambda: limited
    return client


def use_up_today(session, clock, count: int = LIMIT) -> None:
    session.add(LLMUsage(day=clock.today(), count=count))
    session.commit()


def calls_today(sessions, clock) -> int:
    with sessions() as fresh:
        return fresh.scalar(select(LLMUsage.count).where(LLMUsage.day == clock.today())) or 0


def complete(client: DailyLimitedLLMClient) -> str:
    return client.complete("sistema", "usuario", max_tokens=10)


def test_T_AI_LIMIT_01_limit_reached_gives_fixed_hints_without_calling_the_model(
    limited_client, session, sessions, clock, llm
):
    student = make_user(session, "aluna")
    challenge = make_challenge(session, missions=(make_mission(session),))
    use_up_today(session, clock)
    headers = bearer(student, clock)
    fixed = FALLBACK_HINTS[ChallengeType.ORDERING][1]

    answer = as_student(limited_client, headers, challenge, WRONG_ANSWER[ChallengeType.ORDERING])
    wrong = limited_client.post(
        f"/api/challenges/{challenge.id}/submissions", json={"answer": answer}, headers=headers
    )
    requested = limited_client.post(f"/api/challenges/{challenge.id}/hints", headers=headers)

    assert wrong.status_code == 200
    assert wrong.json()["hint"] in fixed
    assert requested.status_code == 200
    assert requested.json()["hint"] in fixed
    assert llm.prompts == []
    assert calls_today(sessions, clock) == LIMIT


def test_T_AI_LIMIT_02_limit_reached_review_still_lists_the_rules(
    limited_client, session, clock, llm
):
    professor = make_user(session, "prof_ana", role=Role.PROFESSOR)
    challenge = make_challenge(session, owner=professor)
    challenge.title = ""
    use_up_today(session, clock)

    response = limited_client.post(
        f"/api/professor/challenges/{challenge.id}/ai-review", headers=bearer(professor, clock)
    )

    assert response.status_code == 200
    assert response.json() == {
        "rule_violations": ["O título deve ter de 1 a 80 caracteres."],
        "suggestions": FALLBACK_SUGGESTIONS,
    }
    assert llm.prompts == []


def test_T_AI_LIMIT_03_limit_reached_draft_is_503_and_nothing_is_saved(
    limited_client, session, clock, llm
):
    professor = make_user(session, "prof_ana", role=Role.PROFESSOR)
    use_up_today(session, clock)

    response = limited_client.post(
        "/api/professor/challenges/ai-draft",
        json={"type": "ordering", "topic": "receitas de bolo"},
        headers=bearer(professor, clock),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "ai_unavailable"
    assert session.scalar(select(func.count()).select_from(Challenge)) == 0
    assert llm.prompts == []


def test_T_AI_LIMIT_04_the_count_restarts_at_local_midnight(llm, sessions, clock, session):
    one_call = DailyLimitedLLMClient(llm, 1, sessions, clock)
    llm.replies.extend([REPLY, REPLY])
    # 23:59 in Sao Paulo is already the next day in UTC.
    clock.set(datetime(2026, 10, 14, 23, 59, tzinfo=TIMEZONE))

    assert complete(one_call) == REPLY
    with pytest.raises(LLMLimitReached):
        complete(one_call)
    clock.advance(timedelta(minutes=2))
    assert complete(one_call) == REPLY


def test_T_AI_LIMIT_05_a_failed_call_still_counts(llm, limited, sessions, clock, session):
    llm.replies.append(LLMError("down"))
    use_up_today(session, clock, count=LIMIT - 1)

    with pytest.raises(LLMError) as failure:
        complete(limited)
    assert not isinstance(failure.value, LLMLimitReached)
    with pytest.raises(LLMLimitReached):
        complete(limited)
    assert calls_today(sessions, clock) == LIMIT


def test_T_AI_LIMIT_06_two_parallel_calls_at_the_last_slot_let_one_through(
    llm, limited, sessions, clock, session
):
    llm.replies.extend([REPLY, REPLY])
    use_up_today(session, clock, count=LIMIT - 1)
    barrier = Barrier(2)

    def call(_: int) -> str:
        barrier.wait()
        try:
            return complete(limited)
        except LLMLimitReached:
            return "limit"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(call, range(2)))

    assert results == sorted([REPLY, "limit"])
    assert len(llm.prompts) == 1
    assert calls_today(sessions, clock) == LIMIT


def test_T_AI_LIMIT_07_reaching_the_limit_is_logged_once_per_day(
    limited_client, session, clock, caplog
):
    student = make_user(session, "aluna")
    challenge = make_challenge(session, missions=(make_mission(session),))
    use_up_today(session, clock)
    headers = bearer(student, clock)
    url = f"/api/challenges/{challenge.id}/hints"

    with caplog.at_level(logging.WARNING):
        limited_client.post(url, headers=headers)
        clock.advance(timedelta(seconds=20))
        limited_client.post(url, headers=headers)
        same_day = [record.getMessage() for record in caplog.records]
        clock.advance(timedelta(days=1))
        use_up_today(session, clock)
        limited_client.post(url, headers=bearer(student, clock))  # the old token expired
        next_day = [record.getMessage() for record in caplog.records]

    assert len(same_day) == 1
    assert "limit" in same_day[0]
    assert next_day == [same_day[0], same_day[0]]


def test_T_AI_LIMIT_08_the_count_is_committed_on_its_own_session(
    llm, limited, sessions, clock, session
):
    llm.replies.append(REPLY)
    make_user(session, "pendente")  # flushed, not committed

    complete(limited)
    session.rollback()

    assert session.scalar(select(func.count()).select_from(User)) == 0
    assert calls_today(sessions, clock) == 1
