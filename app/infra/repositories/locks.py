"""Transaction-scoped PostgreSQL advisory locks, released by commit or rollback.

The two-number form keeps each kind of lock in its own key space, so the lock of
user 7 and the lock of turma 7 never block each other.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

USER_LOCK = 1
CLASSROOM_LOCK = 2


def lock_user(session: Session, user_id: int) -> None:
    """Serialises the writes of one student; waits while another request holds it."""
    session.execute(select(func.pg_advisory_xact_lock(USER_LOCK, user_id)))


def lock_classroom(session: Session, classroom_id: int) -> None:
    """Serialises the class-goal check of one turma."""
    session.execute(select(func.pg_advisory_xact_lock(CLASSROOM_LOCK, classroom_id)))
