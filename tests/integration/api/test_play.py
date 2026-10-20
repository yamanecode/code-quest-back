from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.domain.challenge_types import SKILL_LABELS, ChallengeType
from app.domain.enums import ContentStatus
from app.domain.gamification import daily_pick
from app.infra.db.models import Submission, UserBadge, XPEvent
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    CORRECT_ANSWER,
    NOON,
    WRONG_ANSWER,
    add_member,
    first_solve,
    link,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
)

pytestmark = pytest.mark.usefixtures("badge_catalog")

DRAFT = ContentStatus.DRAFT
ORDERING = ChallengeType.ORDERING


@pytest.fixture
def student(session):
    return make_user(session, "aluna")


@pytest.fixture
def headers(student, clock):
    return bearer(student, clock)


def answer(client, headers, challenge, payload):
    return client.post(
        f"/api/challenges/{challenge.id}/submissions", json={"answer": payload}, headers=headers
    )


def solve(client, headers, challenge):
    return answer(client, headers, challenge, CORRECT_ANSWER[challenge.type])


def miss(client, headers, challenge):
    return answer(client, headers, challenge, WRONG_ANSWER[challenge.type])


def rows(session, model, **filters):
    query = select(func.count()).select_from(model).filter_by(**filters)
    return session.scalar(query)


def keys_at_any_depth(value) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(keys_at_any_depth(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(keys_at_any_depth(v) for v in value))
    return set()


def summary(mission, total, solved):
    return {
        "id": mission.id,
        "title": mission.title,
        "description": None,
        "total": total,
        "solved": solved,
    }


# Missions and challenge view


def test_T_STU_01_sees_base_and_member_turma_missions_grouped(client, session, student, headers):
    mine, empty, other = (make_classroom(session) for _ in range(3))
    add_member(session, student, mine)
    add_member(session, student, empty)
    base = make_mission(session)
    make_mission(session, status=DRAFT)
    turma_mission = make_mission(session, mine)
    make_mission(session, mine, status=DRAFT)
    make_mission(session, other)
    solved = make_challenge(session, missions=(base,))
    make_challenge(session, missions=(base,))
    make_challenge(session, status=DRAFT, missions=(base,))
    first_solve(session, student, solved)

    response = client.get("/api/missions", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "base": [summary(base, total=2, solved=1)],
        "classrooms": [
            {"id": mine.id, "name": mine.name, "missions": [summary(turma_mission, 0, 0)]},
            {"id": empty.id, "name": empty.name, "missions": []},
        ],
    }


def test_T_STU_02_after_leaving_a_turma_its_missions_are_404(client, session, student, headers):
    classroom = make_classroom(session)
    add_member(session, student, classroom)
    mission = make_mission(session, classroom)
    challenge = make_challenge(session, missions=(mission,))
    assert client.get(f"/api/missions/{mission.id}", headers=headers).status_code == 200

    client.delete(f"/api/classrooms/{classroom.id}/membership", headers=headers)

    mission_response = client.get(f"/api/missions/{mission.id}", headers=headers)
    assert mission_response.status_code == 404
    assert mission_response.json()["detail"] == "mission_not_found"
    challenge_response = client.get(f"/api/challenges/{challenge.id}", headers=headers)
    assert challenge_response.status_code == 404
    assert challenge_response.json()["detail"] == "challenge_not_found"
    assert solve(client, headers, challenge).status_code == 404
    assert client.get("/api/missions", headers=headers).json()["classrooms"] == []


def test_T_STU_03_mission_detail_in_order_and_any_challenge_opens(
    client, session, student, headers
):
    mission = make_mission(session)
    challenges = [make_challenge(session, challenge_type=t) for t in ChallengeType]
    for position, challenge in enumerate(challenges):
        link(session, mission, challenge, position)
    link(session, mission, make_challenge(session, status=DRAFT), position=9)
    first_solve(session, student, challenges[1])

    detail = client.get(f"/api/missions/{mission.id}", headers=headers)

    assert detail.status_code == 200
    assert detail.json() == {
        "id": mission.id,
        "title": mission.title,
        "description": None,
        "challenges": [
            {
                "id": c.id,
                "title": c.title,
                "type": c.type,
                "skill": SKILL_LABELS[c.type],
                "solved": c is challenges[1],
            }
            for c in challenges
        ],
    }
    last = challenges[-1]
    view = client.get(f"/api/challenges/{last.id}", headers=headers)
    assert view.status_code == 200
    assert view.json() == {
        "id": last.id,
        "title": last.title,
        "statement": last.statement,
        "type": "pattern",
        "skill": "Reconhecimento de padrões",
        "content": {
            "sequence": ["2", "4", "8"],
            "options": last.content["options"],
        },
        "solved": False,
    }


def test_T_STU_03_draft_challenge_in_a_visible_mission_is_404(client, session, headers):
    draft = make_challenge(session, status=DRAFT, missions=(make_mission(session),))

    assert client.get(f"/api/challenges/{draft.id}", headers=headers).status_code == 404
    assert solve(client, headers, draft).status_code == 404


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_STU_CHAL_NOSOL_no_solution_in_any_student_response(
    client, session, headers, challenge_type
):
    mission = make_mission(session)
    challenge = make_challenge(
        session, challenge_type=challenge_type, missions=(mission,), explanation="Porque sim."
    )
    responses = [
        client.get("/api/missions", headers=headers),
        client.get(f"/api/missions/{mission.id}", headers=headers),
        client.get(f"/api/challenges/{challenge.id}", headers=headers),
        client.get("/api/daily-challenge", headers=headers),
        miss(client, headers, challenge),
    ]

    for response in responses:
        assert response.status_code == 200
        assert "solution" not in keys_at_any_depth(response.json())
        assert "Porque sim." not in response.text
    assert responses[-1].json()["explanation"] is None
    assert solve(client, headers, challenge).json()["explanation"] == "Porque sim."


def test_T_STU_CHAL_NOSOL_ordering_items_are_not_sent_in_solution_order(client, session, headers):
    challenge = make_challenge(session, missions=(make_mission(session),))

    content = client.get(f"/api/challenges/{challenge.id}", headers=headers).json()["content"]

    assert [item["id"] for item in content["items"]] != challenge.content["solution"]
    assert sorted(item["id"] for item in content["items"]) == ["a", "b", "c"]


# Submissions


@pytest.fixture
def challenge(session):
    return make_challenge(session, missions=(make_mission(session),))


def test_T_STU_SUBMIT_01_first_try_gives_10(client, session, student, headers, challenge):
    response = solve(client, headers, challenge)

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["xp_earned"] == 10
    assert (body["xp"], body["level"], body["title"], body["level_up"]) == (
        10,
        1,
        "Aprendiz",
        False,
    )
    assert body["hint"] is None
    assert session.scalar(select(XPEvent.amount).filter_by(user_id=student.id)) == 10


@pytest.mark.parametrize(("wrong", "xp"), [(1, 5), (2, 5)])
def test_T_STU_SUBMIT_02_after_one_or_two_wrong_gives_5(client, headers, challenge, wrong, xp):
    for _ in range(wrong):
        miss(client, headers, challenge)

    assert solve(client, headers, challenge).json()["xp_earned"] == xp


@pytest.mark.parametrize("wrong", [3, 6])
def test_T_STU_SUBMIT_03_after_three_or_more_wrong_gives_2(client, headers, challenge, wrong):
    for _ in range(wrong):
        miss(client, headers, challenge)

    assert solve(client, headers, challenge).json()["xp_earned"] == 2


def test_T_STU_SUBMIT_04_solving_again_gives_nothing(client, session, student, headers, challenge):
    solve(client, headers, challenge)
    miss(client, headers, challenge)

    again = solve(client, headers, challenge).json()

    assert again["is_correct"] is True
    assert (again["xp_earned"], again["xp"]) == (0, 10)
    assert rows(session, XPEvent, user_id=student.id) == 1
    assert rows(session, Submission, user_id=student.id) == 3


def test_T_STU_SUBMIT_05_wrong_answer_is_stored_without_xp(
    client, session, student, headers, challenge
):
    for _ in range(5):
        response = miss(client, headers, challenge)
        assert response.status_code == 200

    assert response.json() == {
        "is_correct": False,
        "xp_earned": 0,
        "xp": 0,
        "level": 1,
        "title": "Aprendiz",
        "level_up": False,
        "new_badges": [],
        "explanation": None,
        "hint": None,
    }
    assert rows(session, Submission, user_id=student.id, is_correct=False) == 5
    assert rows(session, XPEvent, user_id=student.id) == 0


@pytest.mark.parametrize(
    "payload",
    [{"order": ["a", "b"]}, {"order": ["a", "b", "z"]}, {"option": "a"}, {}, {"order": "abc"}],
)
def test_T_STU_SUBMIT_06_malformed_answer_is_422_and_not_stored(
    client, session, student, headers, challenge, payload
):
    response = answer(client, headers, challenge, payload)

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid_answer",
        "message": "Resposta em formato inválido.",
    }
    assert rows(session, Submission, user_id=student.id) == 0


def test_T_STU_SUBMIT_06_answer_must_be_an_object(client, session, student, headers, challenge):
    response = client.post(
        f"/api/challenges/{challenge.id}/submissions", json={"answer": "abc"}, headers=headers
    )

    assert response.status_code == 422
    assert rows(session, Submission, user_id=student.id) == 0


def test_T_STU_SUBMIT_07_new_badges_are_returned_once(client, session, student, headers):
    mission = make_mission(session)
    first, second = (make_challenge(session, missions=(mission,)) for _ in range(2))

    earned = solve(client, headers, first).json()["new_badges"]
    later = solve(client, headers, second).json()["new_badges"]

    assert earned == [
        {
            "code": "first_solve",
            "name": "Primeiro desafio",
            "description": "Resolva seu primeiro desafio.",
            "tier": "bronze",
            "emoji": "⭐",
        }
    ]
    assert "first_solve" not in {badge["code"] for badge in later}
    assert rows(session, UserBadge, user_id=student.id) == len(earned) + len(later)


def test_T_STU_SUBMIT_08_level_up_when_crossing_100_xp(client, session, student, headers):
    first_solve(session, student, make_challenge(session), amount=50)
    first_solve(session, student, make_challenge(session), amount=45)
    mission = make_mission(session)
    crossing, after = (make_challenge(session, missions=(mission,)) for _ in range(2))

    body = solve(client, headers, crossing).json()

    assert (body["xp"], body["level"], body["title"], body["level_up"]) == (
        105,
        3,
        "Explorador(a)",
        True,
    )
    assert "level_3" in {badge["code"] for badge in body["new_badges"]}
    assert solve(client, headers, after).json()["level_up"] is False


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_STU_SUBMIT_09_grading_per_type_through_the_api(client, session, headers, challenge_type):
    challenge = make_challenge(
        session, challenge_type=challenge_type, missions=(make_mission(session),)
    )

    assert miss(client, headers, challenge).json()["is_correct"] is False
    assert miss(client, headers, challenge).json()["is_correct"] is False
    assert solve(client, headers, challenge).json()["is_correct"] is True


# Daily challenge


def daily(client, headers):
    response = client.get("/api/daily-challenge", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_T_STU_DAILY_01_same_challenge_all_day_even_after_solving(
    client, session, student, headers, clock
):
    mission = make_mission(session)
    challenges = {c.id: c for c in (make_challenge(session, missions=(mission,)) for _ in range(5))}

    first = daily(client, headers)
    picked = challenges[first["challenge"]["id"]]
    assert first == {
        "challenge": {
            "id": picked.id,
            "title": picked.title,
            "type": "ordering",
            "skill": "Pensamento algorítmico",
            "solved": False,
        },
        "all_solved": False,
    }

    solve(client, headers, picked)
    clock.advance(timedelta(hours=11))
    headers = bearer(student, clock)  # the 8 h token has expired by now

    again = daily(client, headers)
    assert again["challenge"]["id"] == picked.id
    assert again["challenge"]["solved"] is True


def test_T_STU_DAILY_02_excludes_challenges_solved_before_today(client, session, student, headers):
    mission = make_mission(session)
    yesterday, today = (make_challenge(session, missions=(mission,)) for _ in range(2))
    first_solve(session, student, yesterday, at=NOON - timedelta(days=1))
    first_solve(session, student, today, at=NOON - timedelta(hours=1))

    # Solved today still counts: only solves before the day's start are excluded.
    assert daily(client, headers)["challenge"]["id"] == today.id


def test_T_STU_DAILY_03_all_solved_when_nothing_is_left(client, session, student, headers):
    assert daily(client, headers) == {"challenge": None, "all_solved": True}

    challenge = make_challenge(session, missions=(make_mission(session),))
    first_solve(session, student, challenge, at=NOON - timedelta(days=2))

    assert daily(client, headers) == {"challenge": None, "all_solved": True}


def test_T_STU_DAILY_04_different_students_may_get_different_challenges(client, session, clock):
    mission = make_mission(session)
    ids = [make_challenge(session, missions=(mission,)).id for _ in range(10)]
    students = [make_user(session) for _ in range(10)]

    picks = {s.id: daily(client, bearer(s, clock))["challenge"]["id"] for s in students}

    assert len(set(picks.values())) > 1
    assert picks == {s.id: daily_pick(s.id, clock.today(), ids) for s in students}
