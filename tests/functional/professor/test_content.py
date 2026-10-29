import copy
import re
from collections.abc import Callable

import pytest

from tests.functional.helpers import (
    TYPES,
    Account,
    assert_error,
    challenge_payload,
    create_challenge,
    fail,
    join,
    new_classroom,
    new_mission,
    turma_with_mission,
    unique,
)

pytestmark = pytest.mark.functional

SENT_FIELDS = ("title", "statement", "type", "content", "explanation")


def own_challenges(professor: Account) -> dict[int, dict]:
    response = professor.client.get("/api/professor/challenges")
    assert response.status_code == 200, response.text
    return {challenge["id"]: challenge for challenge in response.json()}


def get_challenge(professor: Account, challenge_id: int) -> dict:
    response = professor.client.get(f"/api/professor/challenges/{challenge_id}")
    assert response.status_code == 200, response.text
    return response.json()


def update(professor: Account, challenge_id: int, payload: dict):
    return professor.client.put(f"/api/professor/challenges/{challenge_id}", json=payload)


def payload_of(challenge: dict) -> dict:
    return {field: copy.deepcopy(challenge[field]) for field in SENT_FIELDS}


def broken(challenge_type: str, change: Callable[[dict], None]) -> dict:
    payload = challenge_payload(challenge_type)
    change(payload)
    return payload


def _items(count: int) -> list[dict]:
    return [{"id": chr(ord("a") + i), "text": f"Item número {i + 1}"} for i in range(count)]


def _set(path: tuple, value) -> Callable[[dict], None]:
    def change(payload: dict) -> None:
        target = payload
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _ordering_items(count: int) -> Callable[[dict], None]:
    def change(payload: dict) -> None:
        payload["content"]["items"] = _items(count)
        payload["content"]["solution"] = [item["id"] for item in _items(count)]

    return change


def _grouping_items(count: int) -> Callable[[dict], None]:
    def change(payload: dict) -> None:
        payload["content"]["items"] = _items(count)
        payload["content"]["solution"] = {
            item["id"]: ("g1" if i % 2 else "g2") for i, item in enumerate(_items(count))
        }

    return change


def _filtering_items(count: int) -> Callable[[dict], None]:
    def change(payload: dict) -> None:
        payload["content"]["items"] = _items(count)
        payload["content"]["solution"] = ["a"]

    return change


def _pattern_options(count: int) -> Callable[[dict], None]:
    def change(payload: dict) -> None:
        payload["content"]["options"] = [
            {"id": chr(ord("a") + i), "text": str(10 + i)} for i in range(count)
        ]
        payload["content"]["solution"] = "a"

    return change


def _duplicate_texts(payload: dict) -> None:
    payload["content"]["items"][1]["text"] = payload["content"]["items"][0]["text"]


def _empty_group(payload: dict) -> None:
    payload["content"]["groups"].append({"id": "g3", "text": "Depois da viagem"})


BROKEN_PAYLOADS = {
    "title_too_long": broken("pattern", _set(("title",), "T" * 81)),
    "statement_too_short": broken("pattern", _set(("statement",), "Curto demais")),
    "statement_too_long": broken("pattern", _set(("statement",), "x" * 601)),
    "explanation_too_long": broken("pattern", _set(("explanation",), "e" * 401)),
    "unknown_type": broken("pattern", _set(("type",), "quiz")),
    "ordering_two_items": broken("ordering", _ordering_items(2)),
    "ordering_nine_items": broken("ordering", _ordering_items(9)),
    "ordering_solution_not_permutation": broken(
        "ordering", _set(("content", "solution"), ["a", "b", "c", "d"])
    ),
    "ordering_text_too_long": broken("ordering", _set(("content", "items", 0, "text"), "t" * 121)),
    "ordering_duplicate_texts": broken("ordering", _duplicate_texts),
    "grouping_one_group": broken(
        "grouping",
        lambda p: p["content"].update(
            groups=[{"id": "g1", "text": "Tudo"}],
            solution={k: "g1" for k in p["content"]["solution"]},
        ),
    ),
    "grouping_three_items": broken("grouping", _grouping_items(3)),
    "grouping_eleven_items": broken("grouping", _grouping_items(11)),
    "grouping_item_without_group": broken("grouping", lambda p: p["content"]["solution"].pop("d")),
    "grouping_group_without_item": broken("grouping", _empty_group),
    "filtering_all_relevant": broken(
        "filtering", _set(("content", "solution"), ["a", "b", "c", "d"])
    ),
    "filtering_none_relevant": broken("filtering", _set(("content", "solution"), [])),
    "filtering_three_items": broken("filtering", _filtering_items(3)),
    "filtering_question_too_short": broken("filtering", _set(("content", "question"), "Quanto?")),
    "pattern_three_options": broken("pattern", _pattern_options(3)),
    "pattern_six_options": broken("pattern", _pattern_options(6)),
    "pattern_two_terms": broken("pattern", _set(("content", "sequence"), ["2", "4"])),
    "pattern_unknown_solution": broken("pattern", _set(("content", "solution"), "z")),
}


@pytest.mark.req("RF-03")
def test_FT_PROF_01_professor_creates_class_mission_and_four_types(professor: Account):
    name = f"Turma {unique()}"
    response = professor.client.post(
        "/api/professor/classrooms", json={"name": name, "weekly_goal": None}
    )
    assert response.status_code == 201, response.text
    classroom = response.json()
    assert re.fullmatch(r"[A-Z0-9]{6}", classroom["join_code"])
    assert classroom["name"] == name
    assert classroom["weekly_goal"] is None

    title = f"Missão {unique()}"
    response = professor.client.post(
        f"/api/professor/classrooms/{classroom['id']}/missions",
        json={"title": title, "description": "Quatro habilidades"},
    )
    assert response.status_code == 201, response.text
    mission = response.json()
    payloads = {challenge_type: challenge_payload(challenge_type) for challenge_type in TYPES}
    created = [
        create_challenge(professor, t, publish=False, payload=p) for t, p in payloads.items()
    ]
    response = professor.client.put(
        f"/api/professor/missions/{mission['id']}/challenges",
        json={"challenge_ids": [c["id"] for c in created]},
    )
    assert response.status_code == 200, response.text

    listed = professor.client.get("/api/professor/classrooms").json()
    assert {"id": classroom["id"], "name": name} in [
        {"id": c["id"], "name": c["name"]} for c in listed
    ]
    missions = professor.client.get(f"/api/professor/classrooms/{classroom['id']}/missions")
    assert [(m["id"], m["title"]) for m in missions.json()] == [(mission["id"], title)]
    detail = professor.client.get(f"/api/professor/missions/{mission['id']}").json()
    assert detail["description"] == "Quatro habilidades"
    assert [c["id"] for c in detail["challenges"]] == [c["id"] for c in created]
    challenges = own_challenges(professor)
    for challenge in created:
        stored = challenges[challenge["id"]]
        assert payload_of(stored) == payloads[stored["type"]]
        assert stored["status"] == "draft"
        assert stored["origin"] == "professor"


@pytest.mark.req("RF-04")
@pytest.mark.parametrize("case", list(BROKEN_PAYLOADS))
def test_FT_PROF_02_rule_breaking_challenge_returns_422_and_is_not_stored(
    professor: Account, case: str
):
    payload = BROKEN_PAYLOADS[case]

    response = professor.client.post("/api/professor/challenges", json=payload)

    assert_error(response, 422)
    titles = {challenge["title"] for challenge in own_challenges(professor).values()}
    assert payload["title"] not in titles


@pytest.mark.req("RF-04")
def test_FT_PROF_03_update_and_publish_are_validated(professor: Account):
    challenge = create_challenge(professor, "pattern", publish=False)
    invalid = payload_of(challenge)
    invalid["content"]["options"] = invalid["content"]["options"][:3]

    assert_error(update(professor, challenge["id"], invalid), 422)
    assert payload_of(get_challenge(professor, challenge["id"])) == payload_of(challenge)

    response = professor.client.post(f"/api/professor/challenges/{challenge['id']}/publish")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"
    assert payload_of(response.json()) == payload_of(challenge)


@pytest.mark.req("RF-04")
def test_FT_PROF_04_mission_without_a_published_challenge_cannot_be_published(
    professor: Account,
):
    classroom = new_classroom(professor)
    empty = new_mission(professor, classroom["id"], [])
    assert_error(
        professor.client.post(f"/api/professor/missions/{empty['id']}/publish"),
        409,
        "mission_empty",
    )

    draft = create_challenge(professor, "ordering", publish=False)
    with_draft = new_mission(professor, classroom["id"], [draft["id"]])
    assert_error(
        professor.client.post(f"/api/professor/missions/{with_draft['id']}/publish"),
        409,
        "mission_empty",
    )

    professor.client.post(f"/api/professor/challenges/{draft['id']}/publish")
    response = professor.client.post(f"/api/professor/missions/{with_draft['id']}/publish")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"


@pytest.mark.req("RF-22")
def test_FT_PROF_05_structure_is_locked_once_students_answered(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("ordering",))
    challenge = turma.challenges[0]
    join(student, turma.join_code)
    fail(student, challenge)

    text_edit = payload_of(challenge)
    text_edit["title"] = f"Novo título {unique()}"
    text_edit["statement"] = "Enunciado reescrito depois das respostas dos estudantes."
    text_edit["explanation"] = "Explicação revisada."
    text_edit["content"]["items"][0]["text"] = "Texto do primeiro passo revisado"
    response = update(professor, challenge["id"], text_edit)
    assert response.status_code == 200, response.text
    assert payload_of(get_challenge(professor, challenge["id"])) == text_edit
    assert get_challenge(professor, challenge["id"])["locked"] is True

    new_type = challenge_payload("pattern")
    new_type["title"] = text_edit["title"]
    more_items = copy.deepcopy(text_edit)
    more_items["content"]["items"].append({"id": "f", "text": "Fechar o livro"})
    more_items["content"]["solution"].append("f")
    new_solution = copy.deepcopy(text_edit)
    new_solution["content"]["solution"] = list(reversed(text_edit["content"]["solution"]))
    renamed_id = copy.deepcopy(text_edit)
    renamed_id["content"]["items"][0]["id"] = "z"
    renamed_id["content"]["solution"] = [
        "z" if item == "a" else item for item in text_edit["content"]["solution"]
    ]
    for payload in (new_type, more_items, new_solution, renamed_id):
        assert_error(update(professor, challenge["id"], payload), 409, "challenge_locked")
    assert payload_of(get_challenge(professor, challenge["id"])) == text_edit


@pytest.mark.req("RF-22")
def test_FT_PROF_06_duplicate_is_a_draft_copy_that_can_change_freely(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("ordering",))
    original = turma.challenges[0]
    join(student, turma.join_code)
    fail(student, original)

    response = professor.client.post(f"/api/professor/challenges/{original['id']}/duplicate")

    assert response.status_code == 201, response.text
    copy_ = response.json()
    assert copy_["id"] != original["id"]
    assert copy_["status"] == "draft"
    assert copy_["origin"] == "professor"
    assert copy_["title"] == f"{original['title']} (cópia)"
    assert copy_["content"] == original["content"]
    assert copy_["locked"] is False

    changed = payload_of(copy_)
    changed["content"]["solution"] = list(reversed(original["content"]["solution"]))
    changed["content"]["items"].append({"id": "f", "text": "Fechar o livro"})
    changed["content"]["solution"].append("f")
    response = update(professor, copy_["id"], changed)
    assert response.status_code == 200, response.text
    assert payload_of(response.json()) == changed
    assert payload_of(get_challenge(professor, original["id"])) == payload_of(original)


@pytest.mark.req("RF-22")
def test_FT_PROF_10_everything_can_change_before_any_answer(professor: Account):
    challenge = create_challenge(professor, "ordering")
    changed = challenge_payload("pattern")

    response = update(professor, challenge["id"], changed)

    assert response.status_code == 200, response.text
    assert payload_of(response.json()) == changed


@pytest.mark.req("RF-03")
def test_FT_PROF_11_missions_are_reordered_in_one_request(professor: Account):
    classroom = new_classroom(professor)
    first, second, third = (new_mission(professor, classroom["id"], []) for _ in range(3))
    url = f"/api/professor/classrooms/{classroom['id']}/missions"

    reordered = professor.client.put(
        f"{url}/order", json={"mission_ids": [third["id"], first["id"], second["id"]]}
    )
    incomplete = professor.client.put(f"{url}/order", json={"mission_ids": [first["id"]]})

    assert reordered.status_code == 200, reordered.text
    expected = [(third["id"], 0), (first["id"], 1), (second["id"], 2)]
    assert [(m["id"], m["position"]) for m in reordered.json()] == expected
    assert_error(incomplete, 422)
    listed = professor.client.get(url).json()
    assert [m["id"] for m in listed] == [third["id"], first["id"], second["id"]]
