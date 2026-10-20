from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_llm_client
from app.core.clock import FixedClock
from app.core.config import get_settings
from app.domain.badges import BADGES
from app.infra.db.models import Base
from app.infra.db.session import get_session
from app.infra.llm.fake import FakeLLMClient
from app.infra.repositories.badges import BadgeRepository
from app.main import create_app
from tests.integration.factories import NOON

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = get_settings().TEST_DATABASE_URL
    if not url:
        raise RuntimeError("TEST_DATABASE_URL must point to the test database")
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    test_engine = create_engine(url)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def badge_catalog(session: Session) -> None:
    """The 30 badge rows; the seed and base-game commands create them outside tests."""
    BadgeRepository(session).sync(BADGES)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOON)


@pytest.fixture
def llm() -> FakeLLMClient:
    """Scripted model: tests add replies to `llm.replies`; with none left it fails."""
    return FakeLLMClient(replies=[])


@pytest.fixture
def client(session: Session, clock: FixedClock, llm: FakeLLMClient) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_llm_client] = lambda: llm
    with TestClient(app) as test_client:
        yield test_client
