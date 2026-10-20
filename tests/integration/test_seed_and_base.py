import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Origin, Role
from app.infra.db.models import Base, Challenge, User
from app.services.base_content_service import BaseContentService
from app.services.exceptions import Conflict, ValidationFailed
from tests.integration.auth_helpers import bearer
from tests.integration.factories import make_user

BASE_DIR = Path(__file__).resolve().parents[2] / "content" / "base"


def row_counts(session: Session) -> dict[str, int]:
    return {
        table.name: session.scalar(select(func.count()).select_from(table))
        for table in Base.metadata.sorted_tables
    }


def test_T_BASE_02_load_creates_base_missions_visible_to_a_fresh_student(client, session, clock):
    report = BaseContentService(session).load(BASE_DIR)

    assert len(report.created) == 5
    assert report.skipped == []
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
    assert row_counts(session)["badges"] == 30
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
    assert len(report.skipped) == 5
    assert row_counts(session) == before


def test_T_BASE_03_new_file_is_added_next_to_existing_missions(session, tmp_path):
    shutil.copy(BASE_DIR / "01-algoritmos.json", tmp_path)
    BaseContentService(session).load(tmp_path)
    shutil.copy(BASE_DIR / "02-decomposicao.json", tmp_path)

    report = BaseContentService(session).load(tmp_path)

    assert report.created == ["Trilha: Decomposição"]
    assert report.skipped == ["Trilha: Pensamento algorítmico"]


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
