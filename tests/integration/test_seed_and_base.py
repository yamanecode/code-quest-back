import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.badges import BADGES
from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Origin, Role
from app.infra.db.models import Base, Challenge, Mission, MissionChallenge, User
from app.services.base_content_service import BaseContentService
from app.services.exceptions import Conflict, ValidationFailed
from tests.integration.answers import as_student
from tests.integration.auth_helpers import bearer
from tests.integration.factories import make_mission, make_user, submit

BASE_DIR = Path(__file__).resolve().parents[2] / "content" / "base"


def row_counts(session: Session) -> dict[str, int]:
    return {
        table.name: session.scalar(select(func.count()).select_from(table))
        for table in Base.metadata.sorted_tables
    }


def test_T_BASE_02_load_creates_base_missions_visible_to_a_fresh_student(client, session, clock):
    report = BaseContentService(session).load(BASE_DIR)

    assert len(report.created) == 5
    assert report.updated == []
    assert report.kept == []
    student = make_user(session, "nova_aluna")
    response = client.get("/api/missions", headers=bearer(student, clock))
    base = response.json()["base"]
    assert [mission["title"] for mission in base] == report.created
    assert [mission["total"] for mission in base] == [6, 6, 6, 6, 4]
    assert all(mission["solved"] == 0 for mission in base)


def test_T_BASE_02_challenges_are_published_and_owned_by_the_system_account(client, session):
    BaseContentService(session).load(BASE_DIR)

    system = session.scalar(select(User).where(User.username == "codequest"))
    assert system.role == Role.SYSTEM
    challenges = list(session.scalars(select(Challenge)))
    assert len(challenges) == 28
    assert {c.owner_id for c in challenges} == {system.id}
    assert {c.origin for c in challenges} == {Origin.BASE}
    assert {c.status for c in challenges} == {ContentStatus.PUBLISHED}
    assert {c.type for c in challenges} == set(ChallengeType)
    assert row_counts(session)["badges"] == 26
    login = client.post("/api/auth/login", json={"username": "codequest", "password": "!"})
    assert login.status_code == 401


def test_T_BASE_02_username_codequest_taken_by_a_student_aborts(session):
    make_user(session, "codequest")
    session.commit()

    with pytest.raises(Conflict) as raised:
        BaseContentService(session).load(BASE_DIR)

    assert raised.value.code == "system_username_taken"
    assert row_counts(session)["missions"] == 0


def test_T_BASE_03_loading_twice_changes_nothing(session):
    BaseContentService(session).load(BASE_DIR)
    before = row_counts(session)

    report = BaseContentService(session).load(BASE_DIR)

    assert report.created == []
    assert report.updated == []
    assert len(report.kept) == 5
    assert row_counts(session) == before


def test_T_BASE_03_new_file_is_added_next_to_existing_missions(session, tmp_path):
    shutil.copy(BASE_DIR / "01-algoritmos.json", tmp_path)
    BaseContentService(session).load(tmp_path)
    shutil.copy(BASE_DIR / "02-decomposicao.json", tmp_path)

    report = BaseContentService(session).load(tmp_path)

    assert report.created == ["Trilha: Decomposição"]
    assert report.kept == ["Trilha: Pensamento algorítmico"]


def test_T_BASE_04_invalid_file_aborts_and_stores_nothing(session, tmp_path):
    shutil.copy(BASE_DIR / "01-algoritmos.json", tmp_path)
    broken = (BASE_DIR / "02-decomposicao.json").read_text(encoding="utf-8")
    broken = broken.replace('"type": "grouping"', '"type": "sorting"', 1)
    (tmp_path / "02-quebrado.json").write_text(broken, encoding="utf-8")

    with pytest.raises(ValidationFailed) as raised:
        BaseContentService(session).load(tmp_path)

    assert len(raised.value.errors) == 1
    assert raised.value.errors[0].startswith("02-quebrado.json, desafio 1 «")
    session.rollback()
    assert set(row_counts(session).values()) == {0}


# Keys (spec 11: load-base is idempotent by key)


def copy_base(directory: Path, *names: str) -> None:
    for name in names:
        shutil.copy(BASE_DIR / name, directory)


def edit_file(path: Path, change) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def by_key(session: Session, model, key: str):
    return session.scalar(select(model).where(model.base_key == key))


def test_T_BASE_KEY_02_fresh_load_stores_every_key(session):
    BaseContentService(session).load(BASE_DIR)

    mission_keys = set(session.scalars(select(Mission.base_key)))
    challenge_keys = set(session.scalars(select(Challenge.base_key)))
    assert len(mission_keys) == 5 and None not in mission_keys
    assert len(challenge_keys) == 28 and None not in challenge_keys
    assert by_key(session, Mission, "base-padroes").position == 4


def test_T_BASE_KEY_03_db_loaded_by_title_gets_its_keys(session):
    BaseContentService(session).load(BASE_DIR)
    for model in (Mission, Challenge):
        for row in session.scalars(select(model)):
            row.base_key = None
    leftover = make_mission(session, title="Missão antiga sem arquivo")
    session.commit()
    before = row_counts(session)

    report = BaseContentService(session).load(BASE_DIR)

    assert len(report.matched) == 33
    assert report.unmatched == ["Missão antiga sem arquivo"]
    assert report.created == []
    assert report.updated == []
    assert row_counts(session) == before
    assert None not in set(session.scalars(select(Challenge.base_key)))
    assert session.get(Mission, leftover.id).base_key is None


def test_T_BASE_KEY_03_challenge_without_a_title_match_is_reported_and_kept(session, tmp_path):
    copy_base(tmp_path, "05-mistos.json")
    BaseContentService(session).load(tmp_path)
    old = by_key(session, Challenge, "base-mistos-01")
    for model in (Mission, Challenge):
        for row in session.scalars(select(model)):
            row.base_key = None
    old.title = "Título antigo"
    session.commit()

    report = BaseContentService(session).load(tmp_path)

    mission = by_key(session, Mission, "base-mistos")
    assert report.unmatched == [f"{mission.title} / Título antigo"]
    assert len(report.matched) == 1 + 3
    assert report.not_in_files == [f"{mission.title} / Título antigo"]
    assert report.created == [
        f"{mission.title} / {by_key(session, Challenge, 'base-mistos-01').title}"
    ]
    assert session.get(Challenge, old.id).base_key is None


def test_T_BASE_KEY_04_text_edit_reaches_the_database(session, tmp_path):
    copy_base(tmp_path, "01-algoritmos.json")
    BaseContentService(session).load(tmp_path)
    challenge = by_key(session, Challenge, "base-algoritmos-02")
    original_id, solution = challenge.id, challenge.content["solution"]
    mission_title = by_key(session, Mission, "base-algoritmos").title

    def change(data):
        data["description"] = "Descrição revisada da trilha."
        second = data["challenges"][1]
        second["title"] = "Título revisado"
        second["statement"] = "Enunciado revisado com o tamanho mínimo exigido."
        second["explanation"] = "Explicação revisada."
        second["content"]["items"][0]["text"] = "Texto revisado"

    edit_file(tmp_path / "01-algoritmos.json", change)
    report = BaseContentService(session).load(tmp_path)

    session.expire_all()
    challenge = session.get(Challenge, original_id)
    assert challenge.title == "Título revisado"
    assert challenge.statement == "Enunciado revisado com o tamanho mínimo exigido."
    assert challenge.explanation == "Explicação revisada."
    assert challenge.content["items"][0]["text"] == "Texto revisado"
    assert challenge.content["solution"] == solution
    mission = by_key(session, Mission, "base-algoritmos")
    assert mission.description == "Descrição revisada da trilha."
    assert report.updated == [mission_title, f"{mission_title} / Título revisado"]
    assert report.created == []


def _new_sequence(data):
    data["challenges"][0]["content"]["sequence"][0] = "100"


def test_T_BASE_KEY_05_structural_edit_without_submissions_replaces_the_content(session, tmp_path):
    copy_base(tmp_path, "04-padroes.json")
    BaseContentService(session).load(tmp_path)
    before = row_counts(session)

    edit_file(tmp_path / "04-padroes.json", _new_sequence)
    BaseContentService(session).load(tmp_path)

    session.expire_all()
    challenge = by_key(session, Challenge, "base-padroes-01")
    assert challenge.content["sequence"][0] == "100"
    assert row_counts(session) == before


def _new_question(data):
    data["challenges"][0]["content"]["question"] = "Qual informação muda a resposta agora?"


def _new_solution(data):
    content = data["challenges"][0]["content"]
    content["solution"] = list(reversed(content["solution"]))


@pytest.mark.parametrize(
    ("name", "key", "change"),
    [
        ("04-padroes.json", "base-padroes-01", _new_sequence),
        ("03-abstracao.json", "base-abstracao-01", _new_question),
        ("01-algoritmos.json", "base-algoritmos-01", _new_solution),
    ],
)
def test_T_BASE_KEY_06_structural_edit_with_submissions_stops(session, tmp_path, name, key, change):
    copy_base(tmp_path, name)
    BaseContentService(session).load(tmp_path)
    challenge = by_key(session, Challenge, key)
    submit(session, make_user(session, "respondeu"), challenge, correct=False)
    session.commit()
    content, title = challenge.content, challenge.title

    edit_file(tmp_path / name, change)
    with pytest.raises(Conflict) as raised:
        BaseContentService(session).load(tmp_path)

    assert raised.value.code == "base_challenge_locked"
    assert f"«{title}»" in raised.value.message
    session.expire_all()
    assert by_key(session, Challenge, key).content == content


def test_T_BASE_KEY_07_renamed_mission_is_updated_not_duplicated(session, tmp_path):
    copy_base(tmp_path, "01-algoritmos.json")
    BaseContentService(session).load(tmp_path)

    edit_file(tmp_path / "01-algoritmos.json", lambda data: data.update(title="Novo nome"))
    report = BaseContentService(session).load(tmp_path)

    assert report.updated == ["Novo nome"]
    assert list(session.scalars(select(Mission.title))) == ["Novo nome"]


def test_T_BASE_KEY_08_new_challenge_is_added_and_a_removed_one_is_kept_at_the_end(
    session, tmp_path
):
    copy_base(tmp_path, "05-mistos.json")
    BaseContentService(session).load(tmp_path)
    removed = by_key(session, Challenge, "base-mistos-01")

    def change(data):
        first = data["challenges"].pop(0)
        data["challenges"].append({**first, "key": "base-mistos-novo", "title": "Desafio novo"})

    edit_file(tmp_path / "05-mistos.json", change)
    report = BaseContentService(session).load(tmp_path)

    mission = by_key(session, Mission, "base-mistos")
    ordered = session.scalars(
        select(MissionChallenge.challenge_id)
        .where(MissionChallenge.mission_id == mission.id)
        .order_by(MissionChallenge.position)
    ).all()
    added = by_key(session, Challenge, "base-mistos-novo")
    assert ordered[-2:] == [added.id, removed.id]
    assert report.created == [f"{mission.title} / Desafio novo"]
    assert report.not_in_files == [f"{mission.title} / {removed.title}"]


def test_T_BASE_KEY_08_key_moved_to_another_mission_stops(session, tmp_path):
    copy_base(tmp_path, "01-algoritmos.json", "02-decomposicao.json")
    BaseContentService(session).load(tmp_path)

    def take_first_key(data):
        data["challenges"][0]["key"] = "base-algoritmos-01"

    edit_file(tmp_path / "01-algoritmos.json", lambda data: data["challenges"].pop(0))
    edit_file(tmp_path / "02-decomposicao.json", take_first_key)
    with pytest.raises(Conflict) as raised:
        BaseContentService(session).load(tmp_path)

    assert raised.value.code == "base_key_moved"


ANSWER_SHAPE = {"ordering": "order", "grouping": "assignment", "filtering": "selected"}


def answer_key(challenge: Challenge) -> dict:
    return {ANSWER_SHAPE.get(challenge.type, "option"): challenge.content["solution"]}


def test_T_BASE_ALL_01_base_game_alone_reaches_level_10_without_turma_badges(
    client, session, clock
):
    BaseContentService(session).load(BASE_DIR)
    session.commit()
    student = make_user(session, "completa")
    headers = bearer(student, clock)
    challenges = session.scalars(select(Challenge).order_by(Challenge.id)).all()

    for challenge in challenges:
        body = {"answer": as_student(client, headers, challenge, answer_key(challenge))}
        result = client.post(
            f"/api/challenges/{challenge.id}/submissions", json=body, headers=headers
        )
        assert result.json()["xp_earned"] == 10

    profile = client.get("/api/me", headers=headers).json()
    earned = {badge["code"] for badge in profile["badges"] if badge["earned"]}
    out_of_reach = {badge.code for badge in BADGES if badge.requires_class} | {"persistent"}

    assert (len(challenges), profile["xp"], profile["level"]) == (28, 280, 10)
    assert profile["title"] == "Especialista"
    assert earned == {badge.code for badge in BADGES} - out_of_reach
