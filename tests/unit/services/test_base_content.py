import json
from collections import Counter
from pathlib import Path

import pytest

from app.domain.challenge_types import ChallengeType, to_student_view
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
    """Write a mission file; keys are filled in from the file name unless given."""
    key = f"k-{Path(name).stem}"
    mission = {"key": key, "title": "Missão", "description": "Uma missão.", "position": 1}
    mission["challenges"] = [VALID_CHALLENGE]
    mission.update(changes)
    if isinstance(mission["challenges"], list):
        mission["challenges"] = [
            {"key": f"{key}-{number}", **challenge} if isinstance(challenge, dict) else challenge
            for number, challenge in enumerate(mission["challenges"], start=1)
        ]
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
    types = Counter(c.draft.type for mission in missions for c in mission.challenges)
    assert types == {challenge_type: 7 for challenge_type in ChallengeType}


def test_T_BASE_01_files_are_read_in_name_order(tmp_path):
    write_mission(tmp_path, "02-b.json", title="Segunda", position=2)
    write_mission(tmp_path, "01-a.json", title="Primeira", position=1)

    missions = read_base_dir(tmp_path)

    assert [mission.title for mission in missions] == ["Primeira", "Segunda"]
    assert missions[0].challenges[0].draft.content == VALID_CHALLENGE["content"]
    assert missions[0].key == "k-01-a"
    assert missions[0].challenges[0].key == "k-01-a-1"


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
        challenge.draft for mission in read_base_dir(BASE_DIR) for challenge in mission.challenges
    ]
    assert len(challenges) == 28
    for challenge in challenges:
        key = "options" if challenge.type == ChallengeType.PATTERN else "items"
        orders = set()
        for user_id in range(50):
            seed = f"{user_id}:base"
            shown_elements = to_student_view(challenge.type, challenge.content, seed)["content"][
                key
            ]
            shown = [element["id"] for element in shown_elements]
            assert shown == [chr(ord("a") + i) for i in range(len(shown))]
            orders.add(tuple(element["text"] for element in shown_elements))
            if challenge.type == ChallengeType.ORDERING:
                answer = answer_from_student(
                    challenge.type, challenge.content, seed, {"order": shown}
                )
                assert not grade(challenge.type, challenge.content, answer), challenge.title
        assert len(orders) > 1, challenge.title


def test_T_BASE_KEY_01_real_files_have_33_unique_keys():
    missions = read_base_dir(BASE_DIR)
    keys = [m.key for m in missions] + [c.key for m in missions for c in m.challenges]

    assert len(keys) == 33
    assert len(set(keys)) == 33


@pytest.mark.parametrize("key", [None, "", "   ", 7, "k" * 81])
def test_T_BASE_KEY_01_mission_needs_a_key(tmp_path, key):
    write_mission(tmp_path, "01-missao.json", key=key)

    assert errors_of(tmp_path) == [
        "01-missao.json: A chave da missão deve ser um texto de 1 a 80 caracteres."
    ]


@pytest.mark.parametrize("key", [None, "", 7])
def test_T_BASE_KEY_01_challenge_needs_a_key(tmp_path, key):
    write_mission(tmp_path, "01-missao.json", challenges=[{**VALID_CHALLENGE, "key": key}])

    assert errors_of(tmp_path) == [
        "01-missao.json, desafio 1 «Fazer café»: "
        "A chave do desafio deve ser um texto de 1 a 80 caracteres."
    ]


def test_T_BASE_KEY_01_keys_are_unique_across_files(tmp_path):
    write_mission(tmp_path, "01-a.json", title="Primeira")
    write_mission(
        tmp_path,
        "02-b.json",
        title="Segunda",
        challenges=[{**VALID_CHALLENGE, "key": "k-01-a"}, {**VALID_CHALLENGE, "key": "k-01-a-1"}],
    )

    assert errors_of(tmp_path) == [
        "02-b.json: a chave «k-01-a» já foi usada em outra missão ou desafio.",
        "02-b.json: a chave «k-01-a-1» já foi usada em outra missão ou desafio.",
    ]
