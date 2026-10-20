import string

from app.domain.challenge_types import TITLE_MAX

CLASSROOM_NAME_MAX = 60
WEEKLY_GOAL_MIN = 1
WEEKLY_GOAL_MAX = 1000
MISSION_DESCRIPTION_MAX = 400
JOIN_CODE_LENGTH = 6
JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits
COPY_SUFFIX = " (cópia)"


def _text_ok(value: object, high: int) -> bool:
    return isinstance(value, str) and value.strip() != "" and len(value) <= high


def classroom_errors(name: object, weekly_goal: object) -> list[str]:
    errors = []
    if not _text_ok(name, CLASSROOM_NAME_MAX):
        errors.append(f"O nome da turma deve ter de 1 a {CLASSROOM_NAME_MAX} caracteres.")
    # bool is a subclass of int, so True must be rejected explicitly.
    if weekly_goal is not None and (
        isinstance(weekly_goal, bool)
        or not isinstance(weekly_goal, int)
        or not WEEKLY_GOAL_MIN <= weekly_goal <= WEEKLY_GOAL_MAX
    ):
        errors.append(
            f"A meta semanal deve ser um número de {WEEKLY_GOAL_MIN} a {WEEKLY_GOAL_MAX}."
        )
    return errors


def mission_errors(title: object, description: object) -> list[str]:
    errors = []
    if not _text_ok(title, TITLE_MAX):
        errors.append(f"O título da missão deve ter de 1 a {TITLE_MAX} caracteres.")
    if description is not None and (
        not isinstance(description, str) or len(description) > MISSION_DESCRIPTION_MAX
    ):
        errors.append(
            f"A descrição da missão deve ter no máximo {MISSION_DESCRIPTION_MAX} caracteres."
        )
    return errors


def copy_title(title: str) -> str:
    """Title of a duplicated challenge; the original is shortened so the suffix always fits."""
    return title[: TITLE_MAX - len(COPY_SUFFIX)] + COPY_SUFFIX
