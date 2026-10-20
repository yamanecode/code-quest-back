import copy

import pytest
from sqlalchemy import func, select

from app.domain.challenge_types import ChallengeType
from app.domain.enums import Role
from app.infra.db.models import Challenge
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
    submit,
)
from tests.samples import CONTENT

URL = "/api/professor/challenges"
STATEMENT = "Coloque os passos na ordem certa para resolver o problema."
SKILLS = {
    "ordering": "Pensamento algorítmico",
    "grouping": "Decomposição",
    "filtering": "Abstração",
    "pattern": "Reconhecimento de padrões",
}
LOCKED = {
    "detail": "challenge_locked",
    "message": "Este desafio já tem respostas. Altere só os textos ou duplique o desafio.",
}


@pytest.fixture
def teacher(session):
    return make_user(session, "prof_ana", role=Role.PROFESSOR)


@pytest.fixture
def headers(teacher, clock):
    return bearer(teacher, clock)


def challenge_body(challenge_type="ordering", **fields):
    body = {
        "title": "Desafio",
        "statement": STATEMENT,
        "type": challenge_type,
        "content": copy.deepcopy(CONTENT[ChallengeType(challenge_type)]),
        "explanation": "Primeiro um, depois dois.",
    }
    return {**body, **fields}


def create(client, headers, **fields):
    return client.post(URL, json=challenge_body(**fields), headers=headers)


def challenge_count(session):
    return session.scalar(select(func.count()).select_from(Challenge))


def answered(session, challenge_id):
    submit(session, make_user(session), session.get(Challenge, challenge_id), correct=False)


@pytest.mark.parametrize("challenge_type", list(SKILLS))
def test_T_PROF_09_create_challenge_of_each_type(client, headers, challenge_type):
    sent = challenge_body(challenge_type)

    response = client.post(URL, json=sent, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert {key: body[key] for key in sent} == sent
    assert body["skill"] == SKILLS[challenge_type]
    assert body["status"] == "draft"
    assert body["origin"] == "professor"
    assert body["locked"] is False
    assert body["solve_stats"] == {"attempted": 0, "solved": 0}
    assert client.get(f"{URL}/{body['id']}", headers=headers).json() == body


def test_T_PROF_09_list_shows_only_own_challenges(client, session, headers):
    make_challenge(session)
    mine = create(client, headers).json()

    listed = client.get(URL, headers=headers).json()

    assert listed == [mine]


def test_T_PROF_09_explanation_is_optional(client, headers):
    body = challenge_body()
    del body["explanation"]

    response = client.post(URL, json=body, headers=headers)

    assert response.status_code == 201
    assert response.json()["explanation"] is None


def _broken(challenge_type, change):
    content = copy.deepcopy(CONTENT[ChallengeType(challenge_type)])
    change(content)
    return content


INVALID = [
    ("ordering", lambda c: c["items"].pop(), "O desafio precisa ter de 3 a 8 itens."),
    ("grouping", lambda c: c["groups"].pop(), "O desafio precisa ter de 2 a 4 etapas."),
    ("filtering", lambda c: c.update(solution=[]), "Marque pelo menos um item relevante"),
    ("pattern", lambda c: c["options"].pop(), "O desafio precisa ter de 4 a 5 opções."),
]


@pytest.mark.parametrize(("challenge_type", "change", "message"), INVALID)
def test_T_PROF_10_invalid_content_is_rejected(
    client, session, headers, challenge_type, change, message
):
    content = _broken(challenge_type, change)

    response = create(client, headers, challenge_type=challenge_type, content=content)

    assert response.status_code == 422
    assert response.json()["detail"] == "validation_error"
    assert any(error.startswith(message) for error in response.json()["errors"])
    assert challenge_count(session) == 0


def test_T_PROF_10_invalid_fields_are_all_reported(client, session, headers):
    body = challenge_body(title="", statement="curto", type="riddle")

    response = client.post(URL, json=body, headers=headers)

    assert response.status_code == 422
    assert response.json()["errors"] == [
        "O título deve ter de 1 a 80 caracteres.",
        "O enunciado deve ter de 20 a 600 caracteres.",
        "Tipo de desafio inválido.",
    ]
    assert challenge_count(session) == 0


def test_T_PROF_11_publish_and_unpublish_challenge(client, headers):
    created = create(client, headers).json()

    published = client.post(f"{URL}/{created['id']}/publish", headers=headers)
    unpublished = client.post(f"{URL}/{created['id']}/unpublish", headers=headers)

    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert unpublished.json()["status"] == "draft"


def test_T_PROF_11_publish_revalidates_the_rules(client, session, headers):
    created = create(client, headers).json()
    # A row that bypassed the API, e.g. stored before a rule existed.
    session.get(Challenge, created["id"]).content = {"items": [], "solution": []}
    session.commit()

    response = client.post(f"{URL}/{created['id']}/publish", headers=headers)

    assert response.status_code == 422
    session.expire_all()
    assert session.get(Challenge, created["id"]).status == "draft"


def test_T_PROF_12_challenge_with_submissions_cannot_be_deleted(client, session, headers):
    created = create(client, headers).json()
    answered(session, created["id"])

    response = client.delete(f"{URL}/{created['id']}", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "challenge_has_submissions"
    assert challenge_count(session) == 1


def test_T_PROF_12_challenge_without_submissions_is_deleted(client, session, headers, teacher):
    created = create(client, headers).json()
    mission = make_mission(session, make_classroom(session, teacher))
    client.put(
        f"/api/professor/missions/{mission.id}/challenges",
        json={"challenge_ids": [created["id"]]},
        headers=headers,
    )

    response = client.delete(f"{URL}/{created['id']}", headers=headers)

    assert response.status_code == 204
    assert challenge_count(session) == 0
    fetched = client.get(f"/api/professor/missions/{mission.id}", headers=headers).json()
    assert fetched["challenges"] == []


def test_T_PROF_EDIT_01_text_edit_allowed_after_a_submission(client, session, headers):
    created = create(client, headers).json()
    answered(session, created["id"])
    edited = challenge_body(title="Novo título", statement=STATEMENT + " Agora!", explanation=None)
    edited["content"]["items"][0]["text"] = "primeiro"

    response = client.put(f"{URL}/{created['id']}", json=edited, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Novo título"
    assert body["explanation"] is None
    assert body["content"]["items"][0]["text"] == "primeiro"
    assert body["locked"] is True


def _reorder_solution(content):
    content["solution"] = ["c", "b", "a"]


def _rename_id(content):
    content["items"][0]["id"] = "z"
    content["solution"][0] = "z"


def _add_item(content):
    content["items"].append({"id": "d", "text": "quatro"})
    content["solution"].append("d")


@pytest.mark.parametrize("change", [_reorder_solution, _rename_id, _add_item])
def test_T_PROF_EDIT_02_structure_change_after_a_submission_is_locked(
    client, session, headers, change
):
    created = create(client, headers).json()
    answered(session, created["id"])
    edited = challenge_body()
    change(edited["content"])

    response = client.put(f"{URL}/{created['id']}", json=edited, headers=headers)

    assert response.status_code == 409
    assert response.json() == LOCKED
    session.expire_all()
    assert session.get(Challenge, created["id"]).content == CONTENT[ChallengeType.ORDERING]


def test_T_PROF_EDIT_02_type_change_after_a_submission_is_locked(client, session, headers):
    created = create(client, headers).json()
    answered(session, created["id"])

    response = client.put(f"{URL}/{created['id']}", json=challenge_body("pattern"), headers=headers)

    assert response.status_code == 409
    assert response.json() == LOCKED


def test_T_PROF_EDIT_03_any_change_allowed_before_submissions(client, headers):
    created = create(client, headers).json()
    edited = challenge_body("pattern", title="Agora é padrão")

    response = client.put(f"{URL}/{created['id']}", json=edited, headers=headers)

    assert response.status_code == 200
    assert response.json()["type"] == "pattern"
    assert response.json()["content"] == CONTENT[ChallengeType.PATTERN]
    assert response.json()["locked"] is False


def test_T_PROF_EDIT_04_duplicate_creates_an_editable_draft_copy(client, session, headers, teacher):
    created = create(client, headers, title="Arrumar a mochila").json()
    client.post(f"{URL}/{created['id']}/publish", headers=headers)
    mission = make_mission(session, make_classroom(session, teacher))
    client.put(
        f"/api/professor/missions/{mission.id}/challenges",
        json={"challenge_ids": [created["id"]]},
        headers=headers,
    )
    answered(session, created["id"])

    response = client.post(f"{URL}/{created['id']}/duplicate", headers=headers)

    assert response.status_code == 201
    copy_ = response.json()
    assert copy_["id"] != created["id"]
    assert copy_["title"] == "Arrumar a mochila (cópia)"
    assert copy_["status"] == "draft"
    assert copy_["origin"] == "professor"
    assert copy_["locked"] is False
    assert {key: copy_[key] for key in ("statement", "type", "content", "explanation")} == {
        key: created[key] for key in ("statement", "type", "content", "explanation")
    }
    fixed = challenge_body(title=copy_["title"])
    _reorder_solution(fixed["content"])
    assert client.put(f"{URL}/{copy_['id']}", json=fixed, headers=headers).status_code == 200
    in_mission = client.get(f"/api/professor/missions/{mission.id}", headers=headers).json()
    assert [c["id"] for c in in_mission["challenges"]] == [created["id"]]


def test_T_PROF_EDIT_04_duplicate_of_an_ai_draft_is_a_professor_challenge(
    client, session, headers, teacher
):
    original = make_challenge(session, teacher)
    original.origin = "ai"
    session.commit()

    response = client.post(f"{URL}/{original.id}/duplicate", headers=headers)

    assert response.json()["origin"] == "professor"


def test_T_PROF_EDIT_05_every_edit_reruns_the_rules(client, session, headers):
    created = create(client, headers).json()
    answered(session, created["id"])
    edited = challenge_body(statement="curto")

    response = client.put(f"{URL}/{created['id']}", json=edited, headers=headers)

    assert response.status_code == 422
    assert response.json()["errors"] == ["O enunciado deve ter de 20 a 600 caracteres."]


def test_T_PROF_STATS_01_solve_stats_count_distinct_students(client, session, headers):
    created = create(client, headers).json()
    challenge = session.get(Challenge, created["id"])
    ana, bia = make_user(session), make_user(session)
    submit(session, ana, challenge, correct=False)
    submit(session, ana, challenge, correct=True)
    submit(session, ana, challenge, correct=True)
    submit(session, bia, challenge, correct=False)
    submit(session, bia, challenge, correct=False)

    listed = client.get(URL, headers=headers).json()

    assert listed[0]["solve_stats"] == {"attempted": 2, "solved": 1}
