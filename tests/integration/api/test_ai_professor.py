import json

import pytest
from sqlalchemy import func, select

from app.core.ports import LLMError
from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Role
from app.infra.db.models import Challenge, User
from app.services.ai_service import FALLBACK_SUGGESTIONS
from tests.integration.answers import as_student
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    add_member,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
)
from tests.samples import CONTENT, DRAFT_CONTENT, WRONG_ANSWER

pytestmark = pytest.mark.usefixtures("badge_catalog")

DRAFT_URL = "/api/professor/challenges/ai-draft"


@pytest.fixture
def professor(session):
    return make_user(session, "prof_ana", role=Role.PROFESSOR)


@pytest.fixture
def headers(professor, clock):
    return bearer(professor, clock)


STEPS = [item["text"] for item in DRAFT_CONTENT[ChallengeType.ORDERING]["items"]]


def draft_reply(**overrides) -> str:
    """A model answer in the expected format, with ids the backend must rename."""
    draft = {
        "title": "Arroz soltinho",
        "statement": "Coloque os passos para preparar o arroz na ordem em que funcionam.",
        "explanation": "Cada passo usa o resultado do anterior.",
        "content": {
            "items": [{"id": f"x{n}", "text": text} for n, text in enumerate(STEPS, start=1)],
            "solution": [f"x{n}" for n in range(1, len(STEPS) + 1)],
        },
    }
    draft.update(overrides)
    return json.dumps(draft, ensure_ascii=False)


def challenge_count(session) -> int:
    return session.scalar(select(func.count()).select_from(Challenge))


def request_draft(client, headers, **body):
    payload = {"type": "ordering", "topic": "receitas de bolo", **body}
    return client.post(DRAFT_URL, json=payload, headers=headers)


def snapshot(session, challenge) -> tuple:
    session.expire_all()
    row = session.get(Challenge, challenge.id)
    return (row.title, row.statement, row.type, row.content, row.explanation, row.status)


def test_T_AI_REVIEW_01_review_returns_suggestions_and_never_changes_the_challenge(
    client, session, professor, headers, llm
):
    challenge = make_challenge(session, owner=professor, status=ContentStatus.DRAFT)
    before = snapshot(session, challenge)
    llm.replies.append("Troque 'três' por 'terceiro passo' para ficar mais claro.")

    response = client.post(f"/api/professor/challenges/{challenge.id}/ai-review", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "rule_violations": [],
        "suggestions": "Troque 'três' por 'terceiro passo' para ficar mais claro.",
    }
    assert snapshot(session, challenge) == before
    assert challenge.statement in llm.prompts[0].user


def test_T_AI_REVIEW_02_rule_violations_come_from_the_domain_validator(
    client, session, professor, headers, llm
):
    challenge = make_challenge(session, owner=professor)
    challenge.statement = "Curto demais."  # stored before a rule existed, say
    session.flush()
    llm.replies.append("Ok.")

    body = client.post(
        f"/api/professor/challenges/{challenge.id}/ai-review", headers=headers
    ).json()

    assert body["rule_violations"] == ["O enunciado deve ter de 20 a 600 caracteres."]


def test_T_AI_REVIEW_03_other_professors_challenge_is_404(client, session, headers, llm):
    other = make_challenge(session)

    response = client.post(f"/api/professor/challenges/{other.id}/ai-review", headers=headers)

    assert response.status_code == 404
    assert llm.prompts == []


def test_T_AI_FALLBACK_02_review_still_lists_rule_violations_when_the_model_fails(
    client, session, professor, headers, llm
):
    challenge = make_challenge(session, owner=professor)
    challenge.title = ""
    session.flush()
    llm.replies.append(LLMError("down"))

    response = client.post(f"/api/professor/challenges/{challenge.id}/ai-review", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "rule_violations": ["O título deve ter de 1 a 80 caracteres."],
        "suggestions": FALLBACK_SUGGESTIONS,
    }


def test_T_AI_DRAFT_01_valid_reply_is_saved_as_ai_draft_with_canonical_ids(
    client, session, headers, llm
):
    llm.replies.append(draft_reply())

    response = request_draft(client, headers)

    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["origin"], body["type"]) == ("draft", "ai", "ordering")
    assert body["title"] == "Arroz soltinho"
    assert body["content"] == {
        "items": [
            {"id": letter, "text": text} for letter, text in zip("abcde", STEPS, strict=True)
        ],
        "solution": list("abcde"),
    }
    assert session.get(Challenge, body["id"]).origin == "ai"
    assert "Tema: receitas de bolo" in llm.prompts[0].user


def test_T_AI_DRAFT_01b_reply_inside_a_code_fence_is_accepted(client, headers, llm):
    llm.replies.append("```json\n" + draft_reply() + "\n```")

    assert request_draft(client, headers).status_code == 201


def test_T_AI_DRAFT_02_invalid_twice_is_422_and_nothing_is_saved(client, session, headers, llm):
    too_few = {"items": [{"id": "a", "text": "Só um passo"}], "solution": ["a"]}
    llm.replies.extend(["isto não é JSON", draft_reply(content=too_few)])

    response = request_draft(client, headers)

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "invalid_draft"
    assert "O desafio precisa ter de 3 a 8 itens." in body["errors"]
    assert challenge_count(session) == 0
    assert len(llm.prompts) == 2
    assert "A resposta da IA não é um JSON válido." in llm.prompts[1].user


def test_T_AI_DRAFT_02b_retry_with_the_errors_can_succeed(client, session, headers, llm):
    llm.replies.extend([json.dumps(["lista"]), draft_reply()])

    assert request_draft(client, headers).status_code == 201
    assert challenge_count(session) == 1


def test_T_AI_DRAFT_07_too_easy_twice_is_422_and_the_retry_names_the_rules(
    client, session, headers, llm
):
    three_steps = {
        "items": [{"id": letter, "text": text} for letter, text in zip("abc", STEPS, strict=False)],
        "solution": ["a", "b", "c"],
    }
    llm.replies.extend([draft_reply(content=three_steps)] * 2)

    response = request_draft(client, headers)

    assert response.status_code == 422
    assert response.json()["errors"] == ["Fácil demais: use pelo menos 5 passos."]
    assert "Fácil demais: use pelo menos 5 passos." in llm.prompts[1].user
    assert challenge_count(session) == 0


def test_T_AI_DRAFT_07b_a_too_easy_draft_can_be_fixed_on_the_retry(client, session, headers, llm):
    cued = json.loads(draft_reply())
    cued["content"]["items"][0]["text"] = "Primeiro, lavar o arroz"
    llm.replies.extend([json.dumps(cued, ensure_ascii=False), draft_reply()])

    assert request_draft(client, headers).status_code == 201
    assert "começar com uma palavra ou número que indique a ordem" in llm.prompts[1].user


def test_T_AI_DRAFT_03_prompt_has_at_most_3_published_examples_of_same_type_and_professor(
    client, session, professor, headers, llm
):
    published = [make_challenge(session, owner=professor) for _ in range(4)]
    hidden = [
        make_challenge(session, owner=professor, status=ContentStatus.DRAFT),
        make_challenge(session, owner=professor, challenge_type=ChallengeType.PATTERN),
        make_challenge(session),  # another professor
    ]
    llm.replies.append(draft_reply())

    request_draft(client, headers)

    prompt = llm.prompts[0].user
    newest_first = sorted(published, key=lambda c: c.id, reverse=True)
    for example in newest_first[:3]:
        assert f'"title": "{example.title}"' in prompt
    for left_out in [newest_first[3], *hidden]:
        assert f'"title": "{left_out.title}"' not in prompt


def test_T_AI_DRAFT_04_draft_is_invisible_to_students_until_published(
    client, session, professor, headers, llm, clock
):
    classroom = make_classroom(session, professor)
    mission = make_mission(session, classroom)
    make_challenge(session, owner=professor, missions=(mission,))
    student = make_user(session)
    add_member(session, student, classroom)
    student_headers = bearer(student, clock)
    llm.replies.append(draft_reply())

    draft_id = request_draft(client, headers, mission_id=mission.id).json()["id"]

    mission_view = client.get(f"/api/missions/{mission.id}", headers=student_headers).json()
    assert draft_id not in [c["id"] for c in mission_view["challenges"]]
    assert client.get(f"/api/challenges/{draft_id}", headers=student_headers).status_code == 404
    client.post(f"/api/professor/challenges/{draft_id}/publish", headers=headers)
    assert client.get(f"/api/challenges/{draft_id}", headers=student_headers).status_code == 200


def test_T_AI_DRAFT_05_mission_id_appends_the_draft_to_an_own_mission(
    client, session, professor, headers, llm
):
    mission = make_mission(session, make_classroom(session, professor))
    existing = make_challenge(session, owner=professor, missions=(mission,))
    foreign_mission = make_mission(session, make_classroom(session))
    llm.replies.append(draft_reply())

    created = request_draft(client, headers, mission_id=mission.id).json()
    foreign = request_draft(client, headers, mission_id=foreign_mission.id)

    listed = client.get(f"/api/professor/missions/{mission.id}", headers=headers).json()
    assert [c["id"] for c in listed["challenges"]] == [existing.id, created["id"]]
    assert foreign.status_code == 404
    assert len(llm.prompts) == 1


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ({"topic": "ab"}, "O tema deve ter de 3 a 200 caracteres."),
        ({"topic": "x" * 201}, "O tema deve ter de 3 a 200 caracteres."),
        ({"type": "drawing"}, "Tipo de desafio inválido."),
    ],
)
def test_T_AI_DRAFT_06_bad_topic_or_type_is_422_before_calling_the_model(
    client, session, headers, llm, body, error
):
    response = request_draft(client, headers, **body)

    assert response.status_code == 422
    assert error in response.json()["errors"]
    assert llm.prompts == []
    assert challenge_count(session) == 0


def test_T_AI_FALLBACK_03_model_failure_on_draft_is_503_and_nothing_is_saved(
    client, session, headers, llm
):
    llm.replies.append(LLMError("timeout"))

    response = request_draft(client, headers)

    assert response.status_code == 503
    assert response.json() == {
        "detail": "ai_unavailable",
        "message": "A IA não está disponível agora. Tente de novo mais tarde.",
    }
    assert challenge_count(session) == 0
    assert len(llm.prompts) == 1


def test_T_AI_PROMPT_03_no_prompt_carries_personal_data_or_turma_names(
    client, session, professor, headers, llm, clock
):
    student = User(id=987654, username="joana_q7", password_hash="x", role=Role.STUDENT)
    session.add(student)
    session.flush()
    classroom = make_classroom(session, professor)
    classroom.name = "Turma Girassol Secreta"
    mission = make_mission(session, classroom)
    challenge = make_challenge(session, owner=professor, missions=(mission,))
    add_member(session, student, classroom)
    student_headers = bearer(student, clock)
    llm.replies.extend(["Pense no início. Qual vem antes?"] * 2 + ["Ok.", draft_reply()])

    url = f"/api/challenges/{challenge.id}"
    client.post(
        f"{url}/submissions",
        json={
            "answer": as_student(client, student_headers, challenge, WRONG_ANSWER[challenge.type])
        },
        headers=student_headers,
    )
    client.post(f"{url}/hints", headers=student_headers)
    client.post(f"/api/professor/challenges/{challenge.id}/ai-review", headers=headers)
    request_draft(client, headers, mission_id=mission.id)

    assert len(llm.prompts) == 4
    for prompt in llm.prompts:
        text = prompt.system + prompt.user
        for secret in ("joana_q7", "987654", "Turma Girassol Secreta", "prof_ana"):
            assert secret not in text
    assert CONTENT[challenge.type]["items"][0]["text"] in llm.prompts[0].user
