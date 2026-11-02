"""Parallel requests of one student: serialised by the user lock, never a 5xx (RNF-06)."""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.domain.enums import HintSource
from app.infra.db.models import ClassGoalReward, ClassroomMember, HintEvent, Submission, XPEvent
from tests.integration.answers import as_student
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    add_member,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
)
from tests.integration.parallel import run_parallel
from tests.samples import CORRECT_ANSWER, WRONG_ANSWER

pytestmark = pytest.mark.usefixtures("badge_catalog")

SAFE_HINT = "Pense no que precisa acontecer antes de tudo. Qual seria o primeiro passo?"


def count(session, model, **filters) -> int:
    return session.scalar(select(func.count()).select_from(model).filter_by(**filters))


def student_answer(app, headers, challenge, answer) -> dict:
    with TestClient(app) as client:
        return as_student(client, headers, challenge, answer)


def submit_call(challenge, headers, answer):
    url = f"/api/challenges/{challenge.id}/submissions"
    return lambda client: client.post(url, json={"answer": answer}, headers=headers)


def hint_call(challenge, headers):
    return lambda client: client.post(f"/api/challenges/{challenge.id}/hints", headers=headers)


def test_T_CONC_01_parallel_correct_submits_give_xp_once(parallel_app, session, clock):
    student = make_user(session, "aluna")
    challenge = make_challenge(session, missions=(make_mission(session),))
    session.commit()
    headers = bearer(student, clock)
    answer = student_answer(parallel_app, headers, challenge, CORRECT_ANSWER[challenge.type])

    responses = run_parallel(parallel_app, [submit_call(challenge, headers, answer)] * 8)

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200] + [409] * 7
    [winner] = [response.json() for response in responses if response.status_code == 200]
    assert winner["xp_earned"] == 10
    losers = [response.json() for response in responses if response.status_code == 409]
    assert {loser["detail"] for loser in losers} == {"already_solved"}
    assert count(session, XPEvent, user_id=student.id) == 1
    assert count(session, Submission, user_id=student.id) == 1


def test_T_CONC_02_parallel_wrong_answers_store_one_automatic_hint(
    parallel_app, session, clock, llm
):
    llm.replies.extend([SAFE_HINT, SAFE_HINT])
    student = make_user(session, "aluna")
    challenge = make_challenge(session, missions=(make_mission(session),))
    session.commit()
    headers = bearer(student, clock)
    answer = student_answer(parallel_app, headers, challenge, WRONG_ANSWER[challenge.type])

    responses = run_parallel(parallel_app, [submit_call(challenge, headers, answer)] * 2)

    assert [response.status_code for response in responses] == [200, 200]
    hints = sorted((response.json()["hint"] is None) for response in responses)
    assert hints == [False, True]
    assert count(session, Submission, user_id=student.id) == 2
    assert count(session, HintEvent, user_id=student.id, source=HintSource.AFTER_WRONG) == 1


def test_T_CONC_03_parallel_hint_requests_show_one_hint_and_refuse_the_other(
    parallel_app, session, clock, llm
):
    llm.replies.extend([SAFE_HINT, SAFE_HINT])
    student = make_user(session, "aluna")
    challenge = make_challenge(session, missions=(make_mission(session),))
    session.commit()
    headers = bearer(student, clock)

    responses = run_parallel(parallel_app, [hint_call(challenge, headers)] * 2)

    assert sorted(response.status_code for response in responses) == [200, 429]
    [refused] = [response.json() for response in responses if response.status_code == 429]
    assert refused["detail"] == "hint_cooldown"
    assert count(session, HintEvent, user_id=student.id) == 1


def test_T_CONC_04_a_submit_does_not_wait_for_a_slow_hint_of_the_same_student(
    parallel_app, session, clock, llm
):
    llm.replies.append(SAFE_HINT)
    llm.delay_seconds = 2.0
    student = make_user(session, "aluna")
    mission = make_mission(session)
    asked, other = (make_challenge(session, missions=(mission,)) for _ in range(2))
    session.commit()
    headers = bearer(student, clock)
    answer = student_answer(parallel_app, headers, other, CORRECT_ANSWER[other.type])

    with ThreadPoolExecutor(max_workers=1) as pool:
        slow_hint = pool.submit(lambda: hint_call(asked, headers)(TestClient(parallel_app)))
        while not llm.prompts:  # the hint request is now waiting on the model
            time.sleep(0.01)
        started = time.monotonic()
        with TestClient(parallel_app) as client:
            submitted = submit_call(other, headers, answer)(client)
        took = time.monotonic() - started
        assert not slow_hint.done()
        hint = slow_hint.result()

    assert submitted.status_code == 200
    assert took < 1.5
    assert hint.status_code == 200


def test_T_CONC_05_parallel_joins_make_one_membership(parallel_app, session, clock):
    student = make_user(session, "aluna")
    turma = make_classroom(session)
    session.commit()
    headers = bearer(student, clock)

    def join(client):
        return client.post(
            "/api/classrooms/join", json={"join_code": turma.join_code}, headers=headers
        )

    responses = run_parallel(parallel_app, [join] * 4)

    assert [response.status_code for response in responses] == [200] * 4
    assert count(session, ClassroomMember, user_id=student.id) == 1


def test_T_CONC_06_members_reaching_the_goal_together_are_both_rewarded(
    parallel_app, session, clock
):
    ana, bia = make_user(session, "ana"), make_user(session, "bia")
    turma = make_classroom(session, weekly_goal=2)
    for member in (ana, bia):
        add_member(session, member, turma)
    mission = make_mission(session, turma)
    first, second = (make_challenge(session, missions=(mission,)) for _ in range(2))
    session.commit()
    calls = []
    for user, challenge in ((ana, first), (bia, second)):
        headers = bearer(user, clock)
        answer = student_answer(parallel_app, headers, challenge, CORRECT_ANSWER[challenge.type])
        calls.append(submit_call(challenge, headers, answer))

    responses = run_parallel(parallel_app, calls)

    assert [response.status_code for response in responses] == [200, 200]
    rewarded = session.scalars(
        select(ClassGoalReward.user_id).filter_by(classroom_id=turma.id)
    ).all()
    assert sorted(rewarded) == sorted([ana.id, bia.id])
