"""Answers as a student sends them: with the per-student item ids of the challenge view."""

from fastapi.testclient import TestClient

from app.domain.challenge_types import ChallengeType
from app.domain.grading import ANSWER_KEYS
from app.infra.db.models import Challenge


def as_student(client: TestClient, headers: dict, challenge: Challenge, answer: object) -> object:
    """Rewrite an answer written with stored ids into the ids this student is shown.

    Items and options are matched by their (unique) text. Anything that is not a well-formed
    answer, or a challenge the student cannot open, is returned unchanged.
    """
    key = ANSWER_KEYS[challenge.type]
    if not isinstance(answer, dict) or set(answer) != {key}:
        return answer
    response = client.get(f"/api/challenges/{challenge.id}", headers=headers)
    if response.status_code != 200:
        return answer
    elements = "options" if challenge.type == ChallengeType.PATTERN else "items"
    shown_by_text = {e["text"]: e["id"] for e in response.json()["content"][elements]}
    shown = {e["id"]: shown_by_text[e["text"]] for e in challenge.content[elements]}

    def rename(item_id: object) -> object:
        return shown.get(item_id, item_id) if isinstance(item_id, str) else item_id

    value = answer[key]
    if isinstance(value, str):
        return {key: rename(value)}
    if isinstance(value, dict):
        return {key: {rename(item): group for item, group in value.items()}}
    if isinstance(value, list):
        return {key: [rename(item) for item in value]}
    return answer
