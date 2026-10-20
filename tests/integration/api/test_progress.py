from datetime import timedelta

import pytest

from app.domain.enums import ContentStatus, HintSource, Role
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    NOON,
    add_member,
    first_solve,
    hint,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
    submit,
)

DRAFT = ContentStatus.DRAFT


@pytest.fixture
def professor(session):
    return make_user(session, "prof", role=Role.PROFESSOR)


def progress(client, clock, professor, classroom):
    url = f"/api/professor/classrooms/{classroom.id}/progress"
    response = client.get(url, headers=bearer(professor, clock))
    assert response.status_code == 200
    return response.json()


def test_T_PROF_PROGRESS_01_values_per_student_and_completion(client, session, clock, professor):
    turma = make_classroom(session, professor)
    ana, bia, caio = (make_user(session, name) for name in ("ana", "bia", "caio"))
    for student in (caio, ana, bia):
        add_member(session, student, turma)
    first_mission, second_mission = make_mission(session, turma), make_mission(session, turma)
    c1, c2 = (make_challenge(session, missions=(first_mission,)) for _ in range(2))
    make_challenge(session, status=DRAFT, missions=(first_mission,))
    c3 = make_challenge(session, missions=(second_mission,))
    in_draft_mission = make_challenge(session, missions=(make_mission(session, turma, DRAFT),))
    base = make_challenge(session, missions=(make_mission(session),))

    first_solve(session, ana, c1, amount=10)
    submit(session, ana, c2, correct=False)
    first_solve(session, ana, c2, amount=5)
    first_solve(session, ana, c3, amount=10)
    first_solve(session, ana, in_draft_mission, amount=10)
    first_solve(session, ana, base, amount=30, at=NOON - timedelta(days=1))
    hint(session, ana, c1)
    hint(session, ana, c1)
    hint(session, ana, c2, HintSource.AFTER_WRONG)
    hint(session, ana, base)
    first_solve(session, bia, c1, amount=10)

    body = progress(client, clock, professor, turma)

    assert body == {
        "completed_all_pct": 33,
        "students": [
            {
                "username": "ana",
                "xp_in_class": 35,
                "level": 2,
                "solved_in_class": 3,
                "missions_completed_in_class": 2,
                "hints_used": 2,
                "streak": 2,
            },
            {
                "username": "bia",
                "xp_in_class": 10,
                "level": 1,
                "solved_in_class": 1,
                "missions_completed_in_class": 0,
                "hints_used": 0,
                "streak": 1,
            },
            {
                "username": "caio",
                "xp_in_class": 0,
                "level": 1,
                "solved_in_class": 0,
                "missions_completed_in_class": 0,
                "hints_used": 0,
                "streak": 0,
            },
        ],
    }


def test_T_PROF_PROGRESS_02_empty_turmas_have_zero_completion(client, session, clock, professor):
    no_members = make_classroom(session, professor)
    make_challenge(session, missions=(make_mission(session, no_members),))
    no_missions = make_classroom(session, professor)
    add_member(session, make_user(session, "ana"), no_missions)

    assert progress(client, clock, professor, no_members) == {
        "completed_all_pct": 0,
        "students": [],
    }
    assert progress(client, clock, professor, no_missions)["completed_all_pct"] == 0


def test_T_PROF_PROGRESS_03_other_professors_turma_is_404(client, session, clock, professor):
    turma = make_classroom(session)
    url = f"/api/professor/classrooms/{turma.id}/progress"

    response = client.get(url, headers=bearer(professor, clock))

    assert response.status_code == 404
    assert response.json()["detail"] == "classroom_not_found"
