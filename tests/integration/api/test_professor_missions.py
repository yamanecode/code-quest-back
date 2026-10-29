import pytest
from sqlalchemy import func, select

from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Role
from app.infra.db.models import Challenge, Mission
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
    submit,
)

DRAFT = ContentStatus.DRAFT


@pytest.fixture
def teacher(session):
    return make_user(session, "prof_ana", role=Role.PROFESSOR)


@pytest.fixture
def headers(teacher, clock):
    return bearer(teacher, clock)


@pytest.fixture
def classroom(session, teacher):
    return make_classroom(session, teacher)


def create_mission(client, headers, classroom, **fields):
    body = {"title": "Missão", **fields}
    return client.post(
        f"/api/professor/classrooms/{classroom.id}/missions", json=body, headers=headers
    )


def set_challenges(client, headers, mission_id, challenge_ids):
    return client.put(
        f"/api/professor/missions/{mission_id}/challenges",
        json={"challenge_ids": challenge_ids},
        headers=headers,
    )


def test_T_PROF_05_create_mission_in_classroom(client, headers, classroom):
    response = create_mission(client, headers, classroom, title="Rotina", description="Manhã")

    assert response.status_code == 201
    body = response.json()
    assert body["classroom_id"] == classroom.id
    assert body["title"] == "Rotina"
    assert body["description"] == "Manhã"
    assert body["status"] == "draft"
    assert body["challenges"] == []
    assert client.get(f"/api/professor/missions/{body['id']}", headers=headers).json() == body


def test_T_PROF_05_new_missions_go_to_the_end_and_list_follows_position(client, headers, classroom):
    first = create_mission(client, headers, classroom, title="A").json()
    second = create_mission(client, headers, classroom, title="B").json()
    first_place = create_mission(client, headers, classroom, title="C", position=-1).json()

    listed = client.get(
        f"/api/professor/classrooms/{classroom.id}/missions", headers=headers
    ).json()

    assert (first["position"], second["position"]) == (0, 1)
    assert [m["id"] for m in listed] == [first_place["id"], first["id"], second["id"]]


def test_T_PROF_05_edit_mission(client, headers, classroom):
    mission = create_mission(client, headers, classroom).json()

    response = client.put(
        f"/api/professor/missions/{mission['id']}",
        json={"title": "Nova", "description": None, "position": 5},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {**mission, "title": "Nova", "description": None, "position": 5}


def test_T_PROF_05_invalid_mission_is_rejected(client, session, headers, classroom):
    response = create_mission(client, headers, classroom, title="", description="d" * 401)

    assert response.status_code == 422
    assert response.json()["errors"] == [
        "O título da missão deve ter de 1 a 80 caracteres.",
        "A descrição da missão deve ter no máximo 400 caracteres.",
    ]
    assert session.scalar(select(func.count()).select_from(Mission)) == 0


def test_T_PROF_06_set_challenges_defines_membership_and_order(
    client, session, headers, classroom, teacher
):
    mission = create_mission(client, headers, classroom).json()
    first = make_challenge(session, teacher, ChallengeType.PATTERN, status=DRAFT)
    second = make_challenge(session, teacher, ChallengeType.ORDERING)

    response = set_challenges(client, headers, mission["id"], [second.id, first.id])

    assert response.status_code == 200
    assert response.json()["challenges"] == [
        {"id": second.id, "title": second.title, "type": "ordering", "status": "published"},
        {"id": first.id, "title": first.title, "type": "pattern", "status": "draft"},
    ]
    emptied = set_challenges(client, headers, mission["id"], [])
    assert emptied.json()["challenges"] == []


def test_T_PROF_06_duplicate_challenge_ids_are_rejected(
    client, session, headers, classroom, teacher
):
    mission = create_mission(client, headers, classroom).json()
    challenge = make_challenge(session, teacher)

    response = set_challenges(client, headers, mission["id"], [challenge.id, challenge.id])

    assert response.status_code == 422
    assert response.json()["errors"] == ["Cada desafio só pode aparecer uma vez na missão."]


def test_T_PROF_06_only_own_challenges_can_be_added(client, session, headers, classroom, teacher):
    mission = create_mission(client, headers, classroom).json()
    mine = make_challenge(session, teacher)
    theirs = make_challenge(session)

    response = set_challenges(client, headers, mission["id"], [mine.id, theirs.id])

    assert response.status_code == 404
    assert response.json()["detail"] == "challenge_not_found"
    fetched = client.get(f"/api/professor/missions/{mission['id']}", headers=headers).json()
    assert fetched["challenges"] == []


def test_T_PROF_07_empty_mission_cannot_be_published(client, headers, classroom):
    mission = create_mission(client, headers, classroom).json()

    response = client.post(f"/api/professor/missions/{mission['id']}/publish", headers=headers)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "mission_empty",
        "message": "A missão precisa de pelo menos um desafio publicado.",
    }


def test_T_PROF_07_mission_with_only_drafts_cannot_be_published(
    client, session, headers, classroom, teacher
):
    mission = create_mission(client, headers, classroom).json()
    draft = make_challenge(session, teacher, status=DRAFT)
    set_challenges(client, headers, mission["id"], [draft.id])

    response = client.post(f"/api/professor/missions/{mission['id']}/publish", headers=headers)

    assert response.status_code == 409


def test_T_PROF_07_publish_and_unpublish_mission(client, session, headers, classroom, teacher):
    mission = create_mission(client, headers, classroom).json()
    set_challenges(client, headers, mission["id"], [make_challenge(session, teacher).id])
    url = f"/api/professor/missions/{mission['id']}"

    published = client.post(f"{url}/publish", headers=headers)
    unpublished = client.post(f"{url}/unpublish", headers=headers)

    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert unpublished.json()["status"] == "draft"


def test_T_PROF_08_mission_with_submissions_cannot_be_deleted(
    client, session, headers, classroom, teacher
):
    mission = create_mission(client, headers, classroom).json()
    challenge = make_challenge(session, teacher)
    set_challenges(client, headers, mission["id"], [challenge.id])
    submit(session, make_user(session), challenge, correct=False)

    response = client.delete(f"/api/professor/missions/{mission['id']}", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "mission_has_submissions"
    assert session.get(Mission, mission["id"]) is not None


def test_T_PROF_08_mission_without_submissions_is_deleted(
    client, session, headers, classroom, teacher
):
    mission = create_mission(client, headers, classroom).json()
    challenge = make_challenge(session, teacher)
    set_challenges(client, headers, mission["id"], [challenge.id])

    response = client.delete(f"/api/professor/missions/{mission['id']}", headers=headers)

    assert response.status_code == 204
    assert (
        client.get(f"/api/professor/missions/{mission['id']}", headers=headers).status_code == 404
    )
    session.expire_all()
    assert session.get(Challenge, challenge.id) is not None


def order_url(classroom):
    return f"/api/professor/classrooms/{classroom.id}/missions/order"


def ids_in_order(client, headers, classroom):
    listed = client.get(
        f"/api/professor/classrooms/{classroom.id}/missions", headers=headers
    ).json()
    return [mission["id"] for mission in listed]


def test_T_PROF_ORDER_01_sets_the_whole_order_and_renumbers_from_zero(client, headers, classroom):
    first, second, third = (
        create_mission(client, headers, classroom, title=name).json() for name in "ABC"
    )
    client.post(f"/api/professor/missions/{second['id']}/unpublish", headers=headers)
    new_order = [third["id"], first["id"], second["id"]]

    response = client.put(order_url(classroom), json={"mission_ids": new_order}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [m["id"] for m in body] == new_order
    assert [m["position"] for m in body] == [0, 1, 2]
    assert [m["status"] for m in body] == ["draft"] * 3
    assert ids_in_order(client, headers, classroom) == new_order


def test_T_PROF_ORDER_02_wrong_lists_are_rejected_and_change_nothing(
    client, session, headers, classroom
):
    first, second = (create_mission(client, headers, classroom, title=n).json() for n in "AB")
    other = make_mission(session, make_classroom(session))
    before = ids_in_order(client, headers, classroom)
    wrong_lists = [
        [first["id"], first["id"]],  # repeated
        [first["id"]],  # missing one
        [second["id"], first["id"], other.id],  # a mission of another turma
        [],  # the turma has missions, so none listed means missing ones
    ]

    for mission_ids in wrong_lists:
        response = client.put(
            order_url(classroom), json={"mission_ids": mission_ids}, headers=headers
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "validation_error"

    assert ids_in_order(client, headers, classroom) == before


def test_T_PROF_ORDER_04_a_turma_without_missions_accepts_the_empty_order(
    client, headers, classroom
):
    response = client.put(order_url(classroom), json={"mission_ids": []}, headers=headers)

    assert response.status_code == 200
    assert response.json() == []
