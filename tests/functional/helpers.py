"""Helpers for the functional tests. They act only through the public HTTP API."""

import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("FUNCTIONAL_BASE_URL", "http://127.0.0.1:8001")
FAKE_LLM_LOG = Path(
    os.environ.get("FAKE_LLM_LOG", REPO_ROOT / "docs" / "evidence" / "fake-llm.jsonl")
)
PROFESSOR_PASSWORD = os.environ.get("CODEQUEST_PROFESSOR_PASSWORD", "")
SAO_PAULO = ZoneInfo("America/Sao_Paulo")

TYPES = ("ordering", "grouping", "filtering", "pattern")
STUDENT_PASSWORD = "senha-segura-123"

# Common English words: a Portuguese error message must not contain them.
ENGLISH_WORDS = re.compile(
    r"\b(the|is|not|field|required|invalid|error|found|must|value|missing)\b", re.IGNORECASE
)


def unique(prefix: str = "ft") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def new_client(token: str | None = None) -> httpx.Client:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.Client(base_url=BASE_URL, headers=headers, timeout=30)


@dataclass
class Account:
    username: str
    password: str
    role: str
    token: str
    client: httpx.Client


def login(username: str, password: str) -> Account:
    with new_client() as anonymous:
        response = anonymous.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
    assert response.status_code == 200, response.text
    body = response.json()
    return Account(
        username, password, body["role"], body["access_token"], new_client(body["access_token"])
    )


def signup_student() -> Account:
    username = unique()
    with new_client() as anonymous:
        response = anonymous.post(
            "/api/auth/register", json={"username": username, "password": STUDENT_PASSWORD}
        )
    assert response.status_code == 201, response.text
    return login(username, STUDENT_PASSWORD)


def assert_error(response: httpx.Response, status: int, detail: str | None = None) -> dict:
    """The error body has a string code in `detail` and a Portuguese `message`."""
    assert response.status_code == status, response.text
    body = response.json()
    assert isinstance(body.get("detail"), str) and body["detail"], body
    if detail is not None:
        assert body["detail"] == detail, body
    message = body.get("message")
    assert isinstance(message, str) and message.strip(), body
    assert message != body["detail"], body
    assert not ENGLISH_WORDS.search(message), body
    return body


# ---- challenge content -------------------------------------------------------------------


def challenge_payload(challenge_type: str, tag: str | None = None) -> dict:
    """A valid challenge of `challenge_type`; every text carries `tag` so prompts can be traced."""
    tag = tag or uuid.uuid4().hex[:8]
    builders = {
        "ordering": _ordering,
        "grouping": _grouping,
        "filtering": _filtering,
        "pattern": _pattern,
    }
    return builders[challenge_type](tag)


def _ordering(tag: str) -> dict:
    texts = {
        "a": "Pegar o livro na estante",
        "b": "Ler a primeira página",
        "c": "Abrir a porta do quarto",
        "d": "Sentar na cadeira",
        "e": "Acender a luz",
    }
    return {
        "title": f"Hora da leitura {tag}",
        "statement": f"Coloque os passos em ordem para começar a ler um livro ({tag}).",
        "type": "ordering",
        "content": {
            "items": [{"id": key, "text": f"{text} {tag}"} for key, text in texts.items()],
            "solution": ["c", "e", "a", "d", "b"],
        },
        "explanation": f"Primeiro é preciso entrar e enxergar, depois pegar o livro ({tag}).",
    }


def _grouping(tag: str) -> dict:
    return {
        "title": f"Planejar a viagem {tag}",
        "statement": f"Separe as tarefas entre antes e durante a viagem ({tag}).",
        "type": "grouping",
        "content": {
            "groups": [
                {"id": "g1", "text": f"Antes da viagem {tag}"},
                {"id": "g2", "text": f"Durante a viagem {tag}"},
            ],
            "items": [
                {"id": "a", "text": f"Fazer a mala {tag}"},
                {"id": "b", "text": f"Comprar a passagem {tag}"},
                {"id": "c", "text": f"Mostrar o bilhete ao motorista {tag}"},
                {"id": "d", "text": f"Olhar a paisagem pela janela {tag}"},
            ],
            "solution": {"a": "g1", "b": "g1", "c": "g2", "d": "g2"},
        },
        "explanation": f"Mala e passagem se resolvem em casa ({tag}).",
    }


def _filtering(tag: str) -> dict:
    return {
        "title": f"Lanche da tarde {tag}",
        "statement": f"Escolha só as informações necessárias para responder à pergunta ({tag}).",
        "type": "filtering",
        "content": {
            "question": f"Quanto custam uma maçã e um pão juntos? ({tag})",
            "items": [
                {"id": "a", "text": f"Uma maçã custa dois reais {tag}"},
                {"id": "b", "text": f"Um pão custa um real {tag}"},
                {"id": "c", "text": f"A padaria abre cedo {tag}"},
                {"id": "d", "text": f"O mercado tem a fachada azul {tag}"},
            ],
            "solution": ["a", "b"],
        },
        "explanation": f"Só os preços importam para a conta ({tag}).",
    }


def _pattern(tag: str) -> dict:
    return {
        "title": f"Sequência de pares {tag}",
        "statement": f"Descubra a regra da sequência e escolha o próximo termo ({tag}).",
        "type": "pattern",
        "content": {
            "sequence": ["2", "4", "6", "8"],
            "options": [
                {"id": "a", "text": "10"},
                {"id": "b", "text": "12"},
                {"id": "c", "text": "9"},
                {"id": "d", "text": "16"},
            ],
            "solution": "a",
        },
        "explanation": f"A cada passo soma-se dois ({tag}).",
    }


def correct_answer(challenge_type: str, content: dict) -> dict:
    key = {"ordering": "order", "grouping": "assignment", "filtering": "selected"}
    return {key.get(challenge_type, "option"): content["solution"]}


def wrong_answer(challenge_type: str, content: dict) -> dict:
    solution = content["solution"]
    if challenge_type == "ordering":
        order = [item["id"] for item in reversed(content["items"])]
        if order == solution:
            order = order[1:] + order[:1]
        return {"order": order}
    if challenge_type == "grouping":
        group_ids = [group["id"] for group in content["groups"]]
        return {
            "assignment": {
                item: group_ids[(group_ids.index(group) + 1) % len(group_ids)]
                for item, group in solution.items()
            }
        }
    if challenge_type == "filtering":
        return {"selected": [item["id"] for item in content["items"] if item["id"] not in solution]}
    return {"option": next(o["id"] for o in content["options"] if o["id"] != solution)}


def item_texts(content: dict) -> dict[str, str]:
    return {item["id"]: item["text"] for item in content.get("items", [])}


# ---- professor actions -------------------------------------------------------------------


def create_challenge(
    professor: Account, challenge_type: str, *, publish: bool = True, payload: dict | None = None
) -> dict:
    """Create (and by default publish) a challenge; returns the professor view, with solution."""
    response = professor.client.post(
        "/api/professor/challenges", json=payload or challenge_payload(challenge_type)
    )
    assert response.status_code == 201, response.text
    challenge = response.json()
    if publish:
        response = professor.client.post(f"/api/professor/challenges/{challenge['id']}/publish")
        assert response.status_code == 200, response.text
        challenge = response.json()
    return challenge


def new_classroom(professor: Account, weekly_goal: int | None = None) -> dict:
    response = professor.client.post(
        "/api/professor/classrooms",
        json={"name": f"Turma {uuid.uuid4().hex[:10]}", "weekly_goal": weekly_goal},
    )
    assert response.status_code == 201, response.text
    return response.json()


def new_mission(professor: Account, classroom_id: int, challenge_ids: list[int]) -> dict:
    response = professor.client.post(
        f"/api/professor/classrooms/{classroom_id}/missions",
        json={"title": f"Missão {uuid.uuid4().hex[:10]}"},
    )
    assert response.status_code == 201, response.text
    mission = response.json()
    response = professor.client.put(
        f"/api/professor/missions/{mission['id']}/challenges",
        json={"challenge_ids": challenge_ids},
    )
    assert response.status_code == 200, response.text
    return response.json()


def publish_mission(professor: Account, classroom_id: int, challenge_ids: list[int]) -> dict:
    mission = new_mission(professor, classroom_id, challenge_ids)
    response = professor.client.post(f"/api/professor/missions/{mission['id']}/publish")
    assert response.status_code == 200, response.text
    return response.json()


@dataclass
class Turma:
    classroom: dict
    mission: dict
    challenges: list[dict]

    @property
    def id(self) -> int:
        return self.classroom["id"]

    @property
    def join_code(self) -> str:
        return self.classroom["join_code"]


def turma_with_mission(
    professor: Account, types: tuple[str, ...] = TYPES, weekly_goal: int | None = None
) -> Turma:
    """A turma with one published mission holding one published challenge per given type."""
    classroom = new_classroom(professor, weekly_goal)
    challenges = [create_challenge(professor, challenge_type) for challenge_type in types]
    mission = publish_mission(professor, classroom["id"], [c["id"] for c in challenges])
    return Turma(classroom, mission, challenges)


# ---- student actions ---------------------------------------------------------------------


def join(student: Account, join_code: str) -> dict:
    response = student.client.post("/api/classrooms/join", json={"join_code": join_code})
    assert response.status_code == 200, response.text
    return response.json()


def submit(student: Account, challenge_id: int, answer: dict) -> httpx.Response:
    return student.client.post(
        f"/api/challenges/{challenge_id}/submissions", json={"answer": answer}
    )


def solve(student: Account, challenge: dict) -> dict:
    response = submit(
        student, challenge["id"], correct_answer(challenge["type"], challenge["content"])
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_correct"] is True
    return response.json()


def fail(student: Account, challenge: dict) -> dict:
    response = submit(
        student, challenge["id"], wrong_answer(challenge["type"], challenge["content"])
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_correct"] is False
    return response.json()


def profile(account: Account) -> dict:
    response = account.client.get("/api/me")
    assert response.status_code == 200, response.text
    return response.json()


def request_hint(student: Account, challenge_id: int) -> httpx.Response:
    return student.client.post(f"/api/challenges/{challenge_id}/hints")


def wait_cooldown(seconds: int) -> None:
    time.sleep(seconds + 0.3)


def my_goal(student: Account, classroom_id: int) -> dict | None:
    response = student.client.get("/api/classrooms")
    assert response.status_code == 200, response.text
    return next(c for c in response.json() if c["id"] == classroom_id)["goal"]


def ranking(account: Account, scope: str, period: str, classroom_id: int | None = None) -> dict:
    params: dict[str, Any] = {"scope": scope, "period": period}
    if classroom_id is not None:
        params["classroom_id"] = classroom_id
    response = account.client.get("/api/rankings", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# ---- inspection --------------------------------------------------------------------------


def has_key(value: Any, key: str) -> bool:
    """True when `key` is a dict key anywhere inside `value`."""
    if isinstance(value, dict):
        return key in value or any(has_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(has_key(v, key) for v in value)
    return False


def monday_sao_paulo(today: date | None = None) -> date:
    today = today or datetime.now(SAO_PAULO).date()
    return today - timedelta(days=today.weekday())


def appears_in_order(text: str, parts: list[str]) -> bool:
    """True when every part occurs in `text`, each one after the previous."""
    position = 0
    for part in parts:
        found = text.find(part, position)
        if found < 0:
            return False
        position = found + len(part)
    return True


def base_files() -> list[dict]:
    """The base game input files that `load-base` reads (test input data, not app code)."""
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((REPO_ROOT / "content" / "base").glob("*.json"))
    ]


def base_challenge(title: str, statement: str) -> dict:
    """The base challenge with this title and statement, as written in the input files."""
    return next(
        challenge
        for mission in base_files()
        for challenge in mission["challenges"]
        if challenge["title"] == title and challenge["statement"] == statement
    )


class LlmLog:
    """Reads the JSON lines the fake language model appends for every prompt it receives."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def mark(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    def since(self, mark: int) -> list[str]:
        if not self.path.exists():
            return []
        with self.path.open("rb") as file:
            file.seek(mark)
            lines = file.read().decode("utf-8").splitlines()
        prompts = []
        for line in lines:
            if line.strip():
                entry = json.loads(line)
                prompts.append(f"{entry['system']}\n{entry['user']}")
        return prompts
