"""Fixtures of the functional suite: a running server reached only over HTTP."""

from collections.abc import Callable, Iterator

import httpx
import pytest

from tests.functional.helpers import (
    BASE_URL,
    FAKE_LLM_LOG,
    PROFESSOR_PASSWORD,
    Account,
    LlmLog,
    login,
    new_client,
    signup_student,
)


@pytest.fixture(scope="session", autouse=True)
def server_is_up() -> None:
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5)
    except httpx.HTTPError as error:
        pytest.exit(f"No server at {BASE_URL} ({error}); run scripts/functional.ps1", returncode=2)
    if response.status_code != 200:
        pytest.exit(f"{BASE_URL}/health answered {response.status_code}", returncode=2)


@pytest.fixture(scope="session")
def professor() -> Iterator[Account]:
    account = login("ft_prof", PROFESSOR_PASSWORD)
    yield account
    account.client.close()


@pytest.fixture(scope="session")
def other_professor() -> Iterator[Account]:
    account = login("ft_prof2", PROFESSOR_PASSWORD)
    yield account
    account.client.close()


@pytest.fixture
def new_student() -> Iterator[Callable[[], Account]]:
    accounts: list[Account] = []

    def create() -> Account:
        account = signup_student()
        accounts.append(account)
        return account

    yield create
    for account in accounts:
        account.client.close()


@pytest.fixture
def student(new_student: Callable[[], Account]) -> Account:
    return new_student()


@pytest.fixture
def anonymous() -> Iterator[httpx.Client]:
    with new_client() as client:
        yield client


@pytest.fixture(scope="session")
def llm_log() -> LlmLog:
    return LlmLog(FAKE_LLM_LOG)
