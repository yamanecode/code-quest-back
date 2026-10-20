"""Authorization headers for API tests."""

from app.core.clock import Clock
from app.infra.db.models import User
from app.infra.security import create_token


def bearer(user: User, clock: Clock) -> dict[str, str]:
    """Header for a user created by the factories, without going through bcrypt and login."""
    return {"Authorization": f"Bearer {create_token(user.id, user.role, clock.now())}"}
