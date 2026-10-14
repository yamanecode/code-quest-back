import os

from sqlalchemy.engine import make_url


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    from dotenv import dotenv_values

    base = os.environ.get("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
    if not base:
        raise RuntimeError("Set DATABASE_URL or TEST_DATABASE_URL to run the tests")
    url = make_url(base)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


# Must run before importing the app so the engine binds to the test database.
TEST_DB_URL = _test_database_url()
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["LLM_PROVIDER"] = "fake"
os.environ["ENVIRONMENT"] = "test"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.clock import FixedClock  # noqa: E402
from app.database import engine  # noqa: E402
from app.models.models import Base  # noqa: E402
from main import app  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "req(id): requirement ID proven by this test")


def _ensure_database() -> None:
    url = make_url(TEST_DB_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))  # noqa: S608
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    _ensure_database()
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def _clean_tables(_database: None) -> None:
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))  # noqa: S608


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()
