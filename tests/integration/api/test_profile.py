from datetime import datetime

import pytest

from app.domain.badges import BADGES
from app.domain.challenge_types import ChallengeType
from app.domain.enums import Role
from tests.integration.answers import as_student
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    NOON,
    add_member,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
)
from tests.samples import CORRECT_ANSWER, WRONG_ANSWER

pytestmark = pytest.mark.usefixtures("badge_catalog")


@pytest.fixture
def student(session):
    return make_user(session, "aluna")


@pytest.fixture
def headers(student, clock):
    return bearer(student, clock)


def send(client, headers, challenge, answers):
    payload = {"answer": as_student(client, headers, challenge, answers[challenge.type])}
    url = f"/api/challenges/{challenge.id}/submissions"
    return client.post(url, json=payload, headers=headers).json()


def solve(client, headers, challenge):
    return send(client, headers, challenge, CORRECT_ANSWER)


def new_badge_codes(result):
    return {badge["code"] for badge in result["new_badges"]}


def me(client, headers):
    response = client.get("/api/me", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_T_STU_ME_01_profile_values(client, session, headers):
    mission = make_mission(session)
    ordering, grouping, *_ = (
        make_challenge(session, challenge_type=t, missions=(mission,)) for t in ChallengeType
    )
    solve(client, headers, ordering)
    send(client, headers, grouping, WRONG_ANSWER)
    solve(client, headers, grouping)

    profile = me(client, headers)

    badges = profile.pop("badges")
    assert profile == {
        "username": "aluna",
        "role": "student",
        "xp": 15,
        "level": 1,
        "title": "Iniciante",
        "xp_to_next_level": 15,
        "title_steps": [
            {"title": "Iniciante", "min_level": 1, "max_level": 2},
            {"title": "Aprendiz", "min_level": 3, "max_level": 4},
            {"title": "Praticante", "min_level": 5, "max_level": 7},
            {"title": "Especialista", "min_level": 8, "max_level": 10},
            {"title": "Mestre", "min_level": 11, "max_level": None},
        ],
        "missions_completed": 0,
        "solved_by_skill": {"ordering": 1, "grouping": 1, "filtering": 0, "pattern": 0},
        "first_try_solves": 1,
        "profile_public": False,
        "recovery_code_active": False,
        "recovery_code_created_at": None,
        "recovery_code_confirmed": False,
    }
    assert [badge["code"] for badge in badges] == [badge.code for badge in BADGES]
    by_code = {badge["code"]: badge for badge in badges}
    earned = by_code["first_solve"]
    assert earned["earned"] is True
    assert datetime.fromisoformat(earned["earned_at"]) == NOON
    assert by_code["skill_ordering_3"] == {
        "code": "skill_ordering_3",
        "name": "Algoritmos I",
        "description": "Resolva 3 desafios de Pensamento algorítmico.",
        "tier": "bronze",
        "emoji": "🔢",
        "hidden": False,
        "requires_class": False,
        "earned": False,
        "earned_at": None,
    }
    assert by_code["skill_ordering_15"]["requires_class"] is True
    assert by_code["all_types_day"] == {
        "code": "all_types_day",
        "name": "Insígnia secreta",
        "description": "",
        "tier": "gold",
        "emoji": "🌈",
        "hidden": True,
        "requires_class": False,
        "earned": False,
        "earned_at": None,
    }


def test_T_STU_ME_02_missions_completed_counts_visible_missions_only(
    client, session, student, headers
):
    classroom = make_classroom(session)
    add_member(session, student, classroom)
    mission = make_mission(session, classroom)
    first, last = (make_challenge(session, missions=(mission,)) for _ in range(2))

    assert "mission_1" not in new_badge_codes(solve(client, headers, first))
    assert "mission_1" in new_badge_codes(solve(client, headers, last))
    assert me(client, headers)["missions_completed"] == 1

    client.delete(f"/api/classrooms/{classroom.id}/membership", headers=headers)

    profile = me(client, headers)
    assert profile["missions_completed"] == 0
    assert "mission_1" in {b["code"] for b in profile["badges"] if b["earned"]}


def miss_times(client, headers, challenge, times):
    for _ in range(times):
        send(client, headers, challenge, WRONG_ANSWER)


def test_T_STU_BADGE_PERSIST_01_solve_after_three_wrong_answers(client, session, headers):
    mission = make_mission(session)
    after_two, after_three = (make_challenge(session, missions=(mission,)) for _ in range(2))

    miss_times(client, headers, after_two, 2)
    assert "persistent" not in new_badge_codes(solve(client, headers, after_two))

    miss_times(client, headers, after_three, 3)
    assert "persistent" in new_badge_codes(solve(client, headers, after_three))


def test_T_STU_BADGE_EXPLORE_01_one_solve_in_every_base_mission(client, session, student, headers):
    first, second = make_mission(session), make_mission(session)
    one = make_challenge(session, missions=(first,))
    make_challenge(session, missions=(first,))
    two = make_challenge(session, missions=(second,))
    classroom = make_classroom(session)
    add_member(session, student, classroom)
    make_challenge(session, missions=(make_mission(session, classroom),))  # turma: not needed

    assert "explorer_base" not in new_badge_codes(solve(client, headers, one))
    assert "explorer_base" in new_badge_codes(solve(client, headers, two))


def test_T_STU_ME_04_fresh_profile(client, headers):
    profile = me(client, headers)

    assert (profile["xp"], profile["level"], profile["xp_to_next_level"]) == (0, 1, 30)
    assert (profile["missions_completed"], profile["first_try_solves"]) == (0, 0)
    assert "streak" not in profile
    assert not any(badge["earned"] for badge in profile["badges"])


def test_T_STU_PUBLIC_01_settings_toggle(client, headers):
    assert me(client, headers)["profile_public"] is False

    on = client.put("/api/me/settings", json={"profile_public": True}, headers=headers)
    assert on.status_code == 200
    assert on.json() == {"profile_public": True}
    assert me(client, headers)["profile_public"] is True

    off = client.put("/api/me/settings", json={"profile_public": False}, headers=headers)
    assert off.json() == {"profile_public": False}
    assert me(client, headers)["profile_public"] is False


def test_T_STU_PUBLIC_01_settings_reject_other_fields(client, headers):
    response = client.put(
        "/api/me/settings", json={"profile_public": True, "username": "outra"}, headers=headers
    )

    assert response.status_code == 422
    assert me(client, headers)["username"] == "aluna"


def player(client, headers, username):
    return client.get(f"/api/players/{username}", headers=headers)


def test_T_STU_PUBLIC_02_private_profile_is_404(client, session, headers, clock):
    other = make_user(session, "colega")
    make_user(session, "prof", role=Role.PROFESSOR, public=True)  # public, but not a student

    for username in ("colega", "prof", "ninguem"):
        response = player(client, headers, username)
        assert response.status_code == 404
        assert response.json()["detail"] == "player_not_found"
    assert player(client, bearer(other, clock), "aluna").status_code == 404  # default is off


def test_T_STU_PUBLIC_03_public_profile_has_exactly_the_public_fields(
    client, session, headers, clock
):
    mission = make_mission(session)
    for challenge_type in ChallengeType:
        solve(
            client,
            headers,
            make_challenge(session, challenge_type=challenge_type, missions=(mission,)),
        )
    client.put("/api/me/settings", json={"profile_public": True}, headers=headers)
    colleague = bearer(make_user(session, "colega"), clock)

    body = player(client, colleague, "Aluna").json()

    assert body == {
        "username": "aluna",
        "level": 2,
        "title": "Iniciante",
        "badges": [
            {"code": "first_solve", "name": "Primeiro desafio", "tier": "bronze", "emoji": "⭐"},
            {"code": "mission_1", "name": "Primeira missão", "tier": "bronze", "emoji": "🚩"},
            {
                "code": "all_types_day",
                "name": "Pensamento completo",
                "tier": "gold",
                "emoji": "🌈",
            },
            {"code": "explorer_base", "name": "Viajante", "tier": "gold", "emoji": "🗺️"},
        ],
    }


def test_T_STU_PUBLIC_03_any_logged_in_user_can_open_it(client, session, headers, clock):
    client.put("/api/me/settings", json={"profile_public": True}, headers=headers)
    professor = make_user(session, "prof", role=Role.PROFESSOR)

    assert player(client, bearer(professor, clock), "aluna").status_code == 200
    assert client.get("/api/players/aluna").status_code == 401
