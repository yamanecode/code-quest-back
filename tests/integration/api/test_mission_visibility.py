"""A published mission whose published challenges were all unpublished is hidden (RF-04)."""

from datetime import timedelta

import pytest

from app.domain.enums import ContentStatus, Role
from tests.integration.answers import as_student
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    NOON,
    add_member,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
    submit,
)
from tests.samples import CORRECT_ANSWER

pytestmark = pytest.mark.usefixtures("badge_catalog")

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


@pytest.fixture
def emptied(session, turma):
    """A turma mission published yesterday; its only challenge is published for now."""
    mission = make_mission(session, turma, published_at=NOON - DAY)
    challenge = make_challenge(session, missions=(mission,), published_at=NOON - DAY)
    return mission, challenge


def set_status(session, challenge, status):
    challenge.status = status
    session.flush()


def turma_missions(client, headers):
    response = client.get("/api/missions", headers=headers)
    assert response.status_code == 200
    return [m for turma in response.json()["classrooms"] for m in turma["missions"]]


def solve(client, headers, challenge):
    payload = {"answer": as_student(client, headers, challenge, CORRECT_ANSWER[challenge.type])}
    url = f"/api/challenges/{challenge.id}/submissions"
    response = client.post(url, json=payload, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_T_STU_VIS_01_mission_leaves_the_list_and_comes_back(client, session, headers, emptied):
    mission, challenge = emptied
    assert [m["id"] for m in turma_missions(client, headers)] == [mission.id]

    set_status(session, challenge, ContentStatus.DRAFT)
    assert turma_missions(client, headers) == []

    set_status(session, challenge, ContentStatus.PUBLISHED)
    assert [m["id"] for m in turma_missions(client, headers)] == [mission.id]


def test_T_STU_VIS_02_mission_page_is_404(client, session, headers, emptied):
    mission, challenge = emptied
    set_status(session, challenge, ContentStatus.DRAFT)

    response = client.get(f"/api/missions/{mission.id}", headers=headers)

    assert response.status_code == 404


def test_T_STU_VIS_03_continuar_skips_the_mission(client, session, student, headers, emptied):
    mission, challenge = emptied
    submit(session, student, challenge, correct=False)
    base = make_mission(session)
    other = make_challenge(session, missions=(base,))
    card = client.get("/api/me/continue", headers=headers).json()
    assert card["mission_id"] == mission.id

    set_status(session, challenge, ContentStatus.DRAFT)

    card = client.get("/api/me/continue", headers=headers).json()
    assert (card["mission_id"], card["challenge_id"]) == (base.id, other.id)


def test_T_STU_VIS_04_no_novo_label_for_the_hidden_mission(client, session, headers, emptied):
    mission, challenge = emptied
    assert turma_missions(client, headers)[0]["is_new"] is True
    assert client.get("/api/me/continue", headers=headers).json()["is_new"] is True

    set_status(session, challenge, ContentStatus.DRAFT)

    assert not any(m["is_new"] or m["has_new_challenges"] for m in turma_missions(client, headers))
    assert client.get("/api/me/continue", headers=headers).status_code == 204


def test_T_STU_VIS_05_missions_completed_and_explorer_ignore_the_hidden_base_mission(
    client, session, headers
):
    visited = make_mission(session)
    challenge = make_challenge(session, missions=(visited,))
    emptied = make_mission(session)
    hidden = make_challenge(session, missions=(emptied,))
    set_status(session, hidden, ContentStatus.DRAFT)

    result = solve(client, headers, challenge)

    assert "explorer_base" in {badge["code"] for badge in result["new_badges"]}
    assert client.get("/api/me", headers=headers).json()["missions_completed"] == 1


def test_T_STU_VIS_06_class_goal_counts_only_visible_missions(
    client, session, student, headers, turma, emptied
):
    _, hidden = emptied
    counted = make_challenge(session, missions=(make_mission(session, turma),))
    set_status(session, hidden, ContentStatus.DRAFT)

    goal = client.get("/api/classrooms", headers=headers).json()[0]["goal"]
    assert goal["target"] == 1

    solve(client, headers, counted)
    goal = client.get("/api/classrooms", headers=headers).json()[0]["goal"]
    assert (goal["progress"], goal["completed"]) == (1, True)


def test_T_PROF_VIS_01_professor_mission_says_whether_it_has_a_published_challenge(
    client, session, clock
):
    teacher = make_user(session, "prof_vis", role=Role.PROFESSOR)
    mission = make_mission(session, make_classroom(session, teacher))
    challenge = make_challenge(session, teacher, missions=(mission,))
    headers = bearer(teacher, clock)
    url = f"/api/professor/missions/{mission.id}"

    assert client.get(url, headers=headers).json()["has_published_challenge"] is True

    set_status(session, challenge, ContentStatus.DRAFT)
    assert client.get(url, headers=headers).json()["has_published_challenge"] is False
    listed = client.get(
        f"/api/professor/classrooms/{mission.classroom_id}/missions", headers=headers
    ).json()
    assert listed[0]["has_published_challenge"] is False
