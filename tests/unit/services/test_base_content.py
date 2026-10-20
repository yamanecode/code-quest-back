import json
from collections import Counter
from pathlib import Path

import pytest

from app.domain.challenge_types import SHUFFLED_TYPES, ChallengeType, to_student_view
from app.domain.grading import answer_from_student, grade
from app.services.base_content_service import read_base_dir
from app.services.exceptions import ValidationFailed

BASE_DIR = Path(__file__).resolve().parents[3] / "content" / "base"

VALID_CHALLENGE = {
    "title": "Fazer café",
    "statement": "Coloque os passos para fazer café na ordem certa.",
    "type": "ordering",
    "content": {
        "items": [
            {"id": "a", "text": "Ferver a água"},
            {"id": "b", "text": "Passar o café no filtro"},
            {"id": "c", "text": "Servir na xícara"},
        ],
        "solution": ["a", "b", "c"],
    },
    "explanation": "A água precisa estar quente antes de passar o café.",
}


def write_mission(directory: Path, name: str, **changes) -> Path:
    mission = {"title": "Missão", "description": "Uma missão.", "position": 1}
    mission["challenges"] = [VALID_CHALLENGE]
    mission.update(changes)
    path = directory / name
    path.write_text(json.dumps(mission, ensure_ascii=False), encoding="utf-8")
    return path


def errors_of(directory: Path) -> list[str]:
    with pytest.raises(ValidationFailed) as raised:
        read_base_dir(directory)
    return raised.value.errors


def test_T_BASE_01_real_base_files_pass_the_template_rules():
    missions = read_base_dir(BASE_DIR)

    assert [mission.position for mission in missions] == [1, 2, 3, 4, 5]
    types = Counter(c.type for mission in missions for c in mission.challenges)
    assert types == {challenge_type: 7 for challenge_type in ChallengeType}


def test_T_BASE_01_files_are_read_in_name_order(tmp_path):
    write_mission(tmp_path, "02-b.json", title="Segunda", position=2)
    write_mission(tmp_path, "01-a.json", title="Primeira", position=1)

    missions = read_base_dir(tmp_path)

    assert [mission.title for mission in missions] == ["Primeira", "Segunda"]
    assert missions[0].challenges[0].content == VALID_CHALLENGE["content"]


def test_T_BASE_04_broken_challenge_error_names_file_and_challenge(tmp_path):
    broken = {**VALID_CHALLENGE, "title": "Curto demais", "statement": "Curto."}
    write_mission(tmp_path, "01-ok.json", title="Boa")
    write_mission(tmp_path, "02-quebrado.json", challenges=[VALID_CHALLENGE, broken])

    errors = errors_of(tmp_path)

    assert len(errors) == 1
    assert errors[0].startswith("02-quebrado.json, desafio 2 «Curto demais»:")
    assert "enunciado" in errors[0]


def test_T_BASE_04_invalid_json_names_the_file(tmp_path):
    (tmp_path / "01-ruim.json").write_text("{ não é json", encoding="utf-8")

    assert errors_of(tmp_path) == ["01-ruim.json: o arquivo não é um JSON válido."]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"title": ""}, "título da missão"),
        ({"position": "1"}, "posição"),
        ({"position": True}, "posição"),
        ({"challenges": []}, "pelo menos um desafio"),
        ({"challenges": "nenhum"}, "pelo menos um desafio"),
    ],
)
def test_T_BASE_04_mission_fields_are_checked(tmp_path, changes, message):
    write_mission(tmp_path, "01-missao.json", **changes)

    errors = errors_of(tmp_path)

    assert len(errors) == 1
    assert errors[0].startswith("01-missao.json:")
    assert message in errors[0]


def test_T_BASE_04_file_must_hold_an_object(tmp_path):
    (tmp_path / "01-lista.json").write_text("[]", encoding="utf-8")

    assert errors_of(tmp_path) == ["01-lista.json: o arquivo deve conter um objeto de missão."]


def test_T_BASE_04_challenge_must_be_an_object_with_a_known_type(tmp_path):
    odd_type = {**VALID_CHALLENGE, "type": ["ordering"]}
    write_mission(tmp_path, "01-missao.json", challenges=["texto", odd_type])

    errors = errors_of(tmp_path)

    assert errors[0] == "01-missao.json, desafio 1: o desafio deve ser um objeto."
    assert errors[1].startswith("01-missao.json, desafio 2 «Fazer café»:")
    assert "Tipo de desafio inválido." in errors[1]


def test_T_BASE_04_repeated_mission_title_is_an_error(tmp_path):
    write_mission(tmp_path, "01-a.json", title="Igual")
    write_mission(tmp_path, "02-b.json", title="Igual")

    assert errors_of(tmp_path) == ["02-b.json: já existe outra missão com o título «Igual»."]


def test_T_BASE_04_directory_without_json_files_is_an_error(tmp_path):
    assert errors_of(tmp_path) == [f"Nenhum arquivo .json encontrado em {tmp_path}."]


def test_T_BASE_05_base_answers_cannot_be_read_from_the_student_view():
    # Audit finding: the stored ids and order of the base files give the answer away.
    challenges = [
        challenge
        for mission in read_base_dir(BASE_DIR)
        for challenge in mission.challenges
        if challenge.type in SHUFFLED_TYPES
    ]
    assert len(challenges) == 21
    for challenge in challenges:
        orders = set()
        for user_id in range(50):
            seed = f"{user_id}:base"
            items = to_student_view(challenge.type, challenge.content, seed)["content"]["items"]
            shown = [item["id"] for item in items]
            assert shown == [chr(ord("a") + i) for i in range(len(shown))]
            orders.add(tuple(item["text"] for item in items))
            if challenge.type == ChallengeType.ORDERING:
                answer = answer_from_student(
                    challenge.type, challenge.content, seed, {"order": shown}
                )
                assert not grade(challenge.type, challenge.content, answer), challenge.title
        assert len(orders) > 1, challenge.title
