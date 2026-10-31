from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.domain.enums import ContentStatus, Origin, Role
from app.infra.db.models import Submission, XPEvent
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    NOON,
    add_member,
    first_solve,
    link,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
    submit,
)

pytestmark = pytest.mark.usefixtures("badge_catalog")

DRAFT = ContentStatus.DRAFT
DAY = timedelta(days=1)


@pytest.fixture
def student(session):
    return make_user(session, "aluna")


@pytest.fixture
def headers(student, clock):
    return bearer(student, clock)


@pytest.fixture
def turma(session, student):
    classroom = make_classroom(session)
    add_member(session, student, classroom)
    return classroom


def solved(session, student, *challenges):
    for challenge in challenges:
        submit(session, student, challenge, True)
        first_solve(session, student, challenge)


def base_challenge(session, mission, position=0):
    challenge = make_challenge(session, origin=Origin.BASE, published_at=NOON - 90 * DAY)
    link(session, mission, challenge, position)
    return challenge


def next_up(client, headers):
    response = client.get("/api/me/continue", headers=headers)
    assert response.status_code == 200
    return response.json()


# Continuar card


def test_T_STU_CONT_01_continues_the_mission_of_the_latest_answer(
    client, session, student, headers
):
    first = make_mission(session, position=0)
    second = make_mission(session, position=1)
    base_challenge(session, first)
    answered = base_challenge(session, second, position=0)
    after = base_challenge(session, second, position=1)
    submit(session, student, answered, False)

    assert next_up(client, headers) == {
        "mission_id": second.id,
        "mission_title": second.title,
        "challenge_id": answered.id,
        "challenge_title": answered.title,
        "is_new": False,
    }

    solved(session, student, answered)
    assert next_up(client, headers)["challenge_id"] == after.id


def test_T_STU_CONT_02_turma_missions_come_before_the_base_newest_first(
    client, session, student, headers, turma
):
    base = make_mission(session)
    base_challenge(session, base)
    older = make_mission(session, turma, published_at=NOON - 5 * DAY)
    newer = make_mission(session, turma, published_at=NOON - 2 * DAY, position=3)
    make_challenge(session, missions=(older,), published_at=NOON - 5 * DAY)
    newest_challenge = make_challenge(session, missions=(newer,), published_at=NOON - 2 * DAY)

    body = next_up(client, headers)

    assert (body["mission_id"], body["challenge_id"]) == (newer.id, newest_challenge.id)
    assert body["is_new"] is True


def test_T_STU_CONT_03_base_game_in_mission_order_after_turma_work(
    client, session, student, headers, turma
):
    later = make_mission(session, position=1)
    sooner = make_mission(session, position=0)
    base_challenge(session, later)
    first_base = base_challenge(session, sooner)
    turma_challenge = make_challenge(session, missions=(make_mission(session, turma),))
    solved(session, student, turma_challenge)

    assert next_up(client, headers)["challenge_id"] == first_base.id


def test_T_STU_CONT_04_nothing_left_answers_204(client, session, student, headers, turma):
    assert client.get("/api/me/continue", headers=headers).status_code == 204

    mission = make_mission(session)
    challenge = base_challenge(session, mission)
    solved(session, student, challenge)

    response = client.get("/api/me/continue", headers=headers)
    assert (response.status_code, response.content) == (204, b"")


def test_T_STU_CONT_05_asking_changes_no_xp_and_stores_nothing(client, session, student, headers):
    base_challenge(session, make_mission(session))
    before = client.get("/api/me", headers=headers).json()["xp"]

    for _ in range(3):
        next_up(client, headers)

    assert client.get("/api/me", headers=headers).json()["xp"] == before
    assert session.scalar(select(func.count()).select_from(XPEvent)) == 0
    assert session.scalar(select(func.count()).select_from(Submission)) == 0


def test_T_STU_CONT_06_only_visible_published_content_counts(client, session, student, headers):
    left = make_classroom(session)
    add_member(session, student, left)
    old_turma_challenge = make_challenge(session, missions=(make_mission(session, left),))
    submit(session, student, old_turma_challenge, False)
    client.delete(f"/api/classrooms/{left.id}/membership", headers=headers)
    make_challenge(session, missions=(make_mission(session, make_classroom(session)),))
    make_challenge(session, missions=(make_mission(session, status=DRAFT),))
    base = make_mission(session)
    make_challenge(session, status=DRAFT, missions=(base,))
    visible = base_challenge(session, base, position=1)

    assert next_up(client, headers)["challenge_id"] == visible.id


# "Novo" label


def mission_list_entry(client, headers, mission):
    body = client.get("/api/missions", headers=headers).json()
    entries = body["base"] + [m for c in body["classrooms"] for m in c["missions"]]
    return next(entry for entry in entries if entry["id"] == mission.id)


def challenge_entry(client, headers, mission, challenge):
    body = client.get(f"/api/missions/{mission.id}", headers=headers).json()
    return next(entry for entry in body["challenges"] if entry["id"] == challenge.id)


def novelty(client, headers, mission, challenge):
    listed = mission_list_entry(client, headers, mission)
    return (
        listed["is_new"],
        listed["has_new_challenges"],
        challenge_entry(client, headers, mission, challenge)["is_new"],
        client.get(f"/api/challenges/{challenge.id}", headers=headers).json()["is_new"],
    )


def test_T_STU_NEW_01_turma_content_published_a_day_ago_is_new(client, session, headers, turma):
    mission = make_mission(session, turma, published_at=NOON - DAY)
    challenge = make_challenge(session, missions=(mission,), published_at=NOON - DAY)

    assert novelty(client, headers, mission, challenge) == (True, False, True, True)


def test_T_STU_NEW_02_first_answer_removes_the_label(client, session, student, headers, turma):
    mission = make_mission(session, turma, published_at=NOON - DAY)
    challenge = make_challenge(session, missions=(mission,), published_at=NOON - DAY)
    submit(session, student, challenge, False)

    assert novelty(client, headers, mission, challenge) == (False, False, False, False)


def test_T_STU_NEW_03_eight_days_later_it_is_not_new(client, session, student, turma, clock):
    mission = make_mission(session, turma, published_at=NOON - DAY)
    challenge = make_challenge(session, missions=(mission,), published_at=NOON - DAY)
    clock.advance(7 * DAY)
    headers = bearer(student, clock)

    assert novelty(client, headers, mission, challenge) == (False, False, False, False)


def test_T_STU_NEW_04_base_content_is_never_new(client, session, headers):
    mission = make_mission(session, published_at=NOON)
    challenge = make_challenge(session, missions=(mission,), published_at=NOON, origin=Origin.BASE)

    assert novelty(client, headers, mission, challenge) == (False, False, False, False)


def test_T_STU_NEW_05_started_mission_shows_it_has_new_challenges(
    client, session, student, headers, turma
):
    mission = make_mission(session, turma, published_at=NOON - 30 * DAY)
    old = make_challenge(session, missions=(mission,), published_at=NOON - 30 * DAY)
    recent = make_challenge(session, missions=(mission,), published_at=NOON - DAY)
    assert novelty(client, headers, mission, recent) == (False, False, True, True)

    submit(session, student, old, True)

    assert novelty(client, headers, mission, recent) == (False, True, True, True)
    assert novelty(client, headers, mission, old)[2:] == (False, False)


def test_T_STU_NEW_06_publish_date_is_set_once(client, session, clock):
    professor = make_user(session, role=Role.PROFESSOR)
    prof = bearer(professor, clock)
    mission = make_mission(session, make_classroom(session, professor), status=DRAFT)
    challenge = make_challenge(session, professor, status=DRAFT, missions=(mission,))
    first = clock.now()

    assert client.post(f"/api/professor/challenges/{challenge.id}/publish", headers=prof).is_success
    assert client.post(f"/api/professor/missions/{mission.id}/publish", headers=prof).is_success
    clock.advance(3 * DAY)
    prof = bearer(professor, clock)
    for path in (f"challenges/{challenge.id}", f"missions/{mission.id}"):
        assert client.post(f"/api/professor/{path}/unpublish", headers=prof).is_success
    for path in (f"challenges/{challenge.id}", f"missions/{mission.id}"):
        assert client.post(f"/api/professor/{path}/publish", headers=prof).is_success

    session.expire_all()
    assert (challenge.published_at, mission.published_at) == (first, first)
