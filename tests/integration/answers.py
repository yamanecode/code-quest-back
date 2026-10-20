"""Answers as a student sends them: with the per-student item ids of the challenge view."""

from fastapi.testclient import TestClient

from app.infra.db.models import Challenge

ANSWER_KEYS = {"ordering": "order", "grouping": "assignment", "filtering": "selected"}


def as_student(client: TestClient, headers: dict, challenge: Challenge, answer: object) -> object:
    """Rewrite an answer written with stored ids into the ids this student is shown.

    Items are matched by their (unique) text. Anything that is not a well-formed answer of a
    shuffled type, or a challenge the student cannot open, is returned unchanged.
    """
    key = ANSWER_KEYS.get(challenge.type)
    if key is None or not isinstance(answer, dict) or set(answer) != {key}:
        return answer
    response = client.get(f"/api/challenges/{challenge.id}", headers=headers)
    if response.status_code != 200:
        return answer
    shown_by_text = {item["text"]: item["id"] for item in response.json()["content"]["items"]}
    shown = {item["id"]: shown_by_text[item["text"]] for item in challenge.content["items"]}

    def rename(item_id: object) -> object:
        return shown.get(item_id, item_id) if isinstance(item_id, str) else item_id

    value = answer[key]
    if isinstance(value, dict):
        return {key: {rename(item): group for item, group in value.items()}}
    if isinstance(value, list):
        return {key: [rename(item) for item in value]}
    return answer
