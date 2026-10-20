import pytest

from app.domain.content import (
    JOIN_CODE_ALPHABET,
    JOIN_CODE_LENGTH,
    classroom_errors,
    copy_title,
    mission_errors,
)

NAME_ERROR = "O nome da turma deve ter de 1 a 60 caracteres."
GOAL_ERROR = "A meta semanal deve ser um número de 1 a 1000."
TITLE_ERROR = "O título da missão deve ter de 1 a 80 caracteres."
DESCRIPTION_ERROR = "A descrição da missão deve ter no máximo 400 caracteres."


@pytest.mark.parametrize("name", ["A", "Turma 7B", "a" * 60])
def test_T_DOM_CONTENT_01_classroom_name_accepted(name):
    assert classroom_errors(name, None) == []


@pytest.mark.parametrize("name", ["", "   ", "a" * 61, None, 7])
def test_T_DOM_CONTENT_01_classroom_name_rejected(name):
    assert classroom_errors(name, None) == [NAME_ERROR]


@pytest.mark.parametrize("weekly_goal", [None, 1, 1000])
def test_T_DOM_CONTENT_02_weekly_goal_accepted(weekly_goal):
    assert classroom_errors("Turma", weekly_goal) == []


@pytest.mark.parametrize("weekly_goal", [0, 1001, -5, "10", True])
def test_T_DOM_CONTENT_02_weekly_goal_rejected(weekly_goal):
    assert classroom_errors("Turma", weekly_goal) == [GOAL_ERROR]


def test_T_DOM_CONTENT_02_every_classroom_error_is_reported():
    assert classroom_errors("", 0) == [NAME_ERROR, GOAL_ERROR]


@pytest.mark.parametrize(
    ("title", "description"), [("M", None), ("a" * 80, ""), ("Missão", "d" * 400)]
)
def test_T_DOM_CONTENT_03_mission_fields_accepted(title, description):
    assert mission_errors(title, description) == []


@pytest.mark.parametrize("title", ["", "  ", "a" * 81, None])
def test_T_DOM_CONTENT_03_mission_title_rejected(title):
    assert mission_errors(title, None) == [TITLE_ERROR]


@pytest.mark.parametrize("description", ["d" * 401, 3])
def test_T_DOM_CONTENT_03_mission_description_rejected(description):
    assert mission_errors("Missão", description) == [DESCRIPTION_ERROR]


def test_T_DOM_CONTENT_04_copy_title_adds_suffix():
    assert copy_title("Arrumar a mochila") == "Arrumar a mochila (cópia)"


def test_T_DOM_CONTENT_04_copy_title_keeps_suffix_for_long_titles():
    title = "a" * 80

    copied = copy_title(title)

    assert len(copied) == 80
    assert copied == "a" * 72 + " (cópia)"


def test_T_DOM_CONTENT_04_join_code_alphabet_is_uppercase_letters_and_digits():
    assert JOIN_CODE_LENGTH == 6
    assert set(JOIN_CODE_ALPHABET) == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
