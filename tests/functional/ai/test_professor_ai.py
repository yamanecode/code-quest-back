import uuid

import pytest

from tests.functional.helpers import (
    TYPES,
    Account,
    LlmLog,
    assert_error,
    challenge_payload,
    create_challenge,
    join,
    turma_with_mission,
)

pytestmark = pytest.mark.functional


def draft(professor: Account, challenge_type: str, topic: str, mission_id: int | None = None):
    return professor.client.post(
        "/api/professor/challenges/ai-draft",
        json={"type": challenge_type, "topic": topic, "mission_id": mission_id},
    )


def own_ids(professor: Account) -> set[int]:
    return {
        challenge["id"] for challenge in professor.client.get("/api/professor/challenges").json()
    }


@pytest.mark.req("RF-14")
def test_FT_AI_06_review_suggests_and_never_changes_the_challenge(professor: Account):
    challenge = create_challenge(professor, "grouping")
    before = professor.client.get(f"/api/professor/challenges/{challenge['id']}").json()

    response = professor.client.post(f"/api/professor/challenges/{challenge['id']}/ai-review")

    assert response.status_code == 200, response.text
    review = response.json()
    assert review["rule_violations"] == []
    assert isinstance(review["suggestions"], str) and review["suggestions"].strip()
    after = professor.client.get(f"/api/professor/challenges/{challenge['id']}").json()
    assert after == before


@pytest.mark.req("RF-15")
@pytest.mark.parametrize("challenge_type", TYPES)
def test_FT_AI_07_draft_is_saved_as_an_ai_draft(professor: Account, challenge_type: str):
    response = draft(professor, challenge_type, f"frutas da feira {uuid.uuid4().hex[:6]}")

    assert response.status_code == 201, response.text
    created = response.json()
    assert (created["type"], created["status"], created["origin"]) == (
        challenge_type,
        "draft",
        "ai",
    )
    assert created["id"] in own_ids(professor)


@pytest.mark.req("RF-15")
def test_FT_AI_08_draft_request_holds_up_to_three_published_examples_of_the_professor(
    professor: Account, other_professor: Account, llm_log: LlmLog
):
    def tagged(owner: Account, challenge_type: str, publish: bool) -> str:
        tag = f"exemplo{uuid.uuid4().hex[:8]}"
        payload = challenge_payload(challenge_type, tag)
        create_challenge(owner, challenge_type, publish=publish, payload=payload)
        return tag

    other_professor_tag = tagged(other_professor, "filtering", True)
    published = [tagged(professor, "filtering", True) for _ in range(4)]
    draft_tag = tagged(professor, "filtering", False)
    other_type_tag = tagged(professor, "pattern", True)
    mark = llm_log.mark()

    assert draft(professor, "filtering", "contas de padaria").status_code == 201

    prompts = llm_log.since(mark)
    assert len(prompts) == 1
    prompt = prompts[0]
    assert [tag in prompt for tag in published] == [False, True, True, True]
    for tag in (draft_tag, other_type_tag, other_professor_tag):
        assert tag not in prompt


@pytest.mark.req("RF-15")
def test_FT_AI_09_invalid_ai_answer_returns_422_and_stores_nothing(professor: Account):
    before = own_ids(professor)

    response = draft(professor, "ordering", "[fake:invalid] rotina da manhã")

    assert_error(response, 422)
    assert own_ids(professor) == before


@pytest.mark.req("SG-05")
def test_FT_AI_12_draft_stays_hidden_from_students_until_published(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("pattern",))
    join(student, turma.join_code)
    mission_path = f"/api/missions/{turma.mission['id']}"

    response = draft(professor, "ordering", "preparar um sanduíche", turma.mission["id"])
    assert response.status_code == 201, response.text
    created = response.json()

    shown = [c["id"] for c in student.client.get(mission_path).json()["challenges"]]
    assert created["id"] not in shown
    assert_error(student.client.get(f"/api/challenges/{created['id']}"), 404)
    in_mission = professor.client.get(f"/api/professor/missions/{turma.mission['id']}").json()
    assert created["id"] in [c["id"] for c in in_mission["challenges"]]

    published = professor.client.post(f"/api/professor/challenges/{created['id']}/publish")
    assert published.status_code == 200, published.text
    shown = [c["id"] for c in student.client.get(mission_path).json()["challenges"]]
    assert created["id"] in shown
    assert student.client.get(f"/api/challenges/{created['id']}").status_code == 200
