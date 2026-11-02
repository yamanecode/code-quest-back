from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.repositories.locks import CLASSROOM_LOCK, USER_LOCK, lock_classroom, lock_user


def free(engine, space: int, key: int) -> bool:
    """Whether another connection could take the lock now, without waiting for it."""
    with Session(engine) as other:
        return other.scalar(select(func.pg_try_advisory_xact_lock(space, key)))


def test_T_REPO_LOCK_01_user_lock_is_held_until_the_transaction_ends(engine, session):
    lock_user(session, 5)

    assert not free(engine, USER_LOCK, 5)
    assert free(engine, USER_LOCK, 6)
    session.commit()
    assert free(engine, USER_LOCK, 5)


def test_T_REPO_LOCK_02_user_and_classroom_locks_use_separate_key_spaces(engine, session):
    lock_user(session, 1)
    assert free(engine, CLASSROOM_LOCK, 1)

    lock_classroom(session, 1)
    assert not free(engine, CLASSROOM_LOCK, 1)
    session.rollback()
    assert free(engine, CLASSROOM_LOCK, 1)
