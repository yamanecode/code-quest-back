from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings

BCRYPT_ROUNDS = 12
BCRYPT_MAX_BYTES = 72
ALGORITHM = "HS256"


class InvalidToken(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    role: str


def hash_password(password: str) -> str:
    raw = password.encode()
    if len(raw) > BCRYPT_MAX_BYTES:
        raise ValueError("password longer than 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode())
    except ValueError:
        # Not a bcrypt hash, e.g. the "!" of the system account.
        return False


def create_token(user_id: int, role: str, now: datetime) -> str:
    settings = get_settings()
    expires = now + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    claims = {"sub": str(user_id), "role": role, "exp": int(expires.timestamp())}
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str, now: datetime) -> TokenClaims:
    # Expiry is checked against the injected clock instead of PyJWT's system time.
    options = {"verify_exp": False, "require": ["sub", "role", "exp"]}
    try:
        claims = jwt.decode(token, get_settings().JWT_SECRET, [ALGORITHM], options=options)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError) as error:
        raise InvalidToken from error
    if now.timestamp() >= claims["exp"]:
        raise InvalidToken
    return TokenClaims(user_id=user_id, role=claims["role"])
