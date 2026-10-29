import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.domain.recovery_code import ALPHABET, CODE_LENGTH, normalize_recovery_code

BCRYPT_ROUNDS = 12
BCRYPT_MAX_BYTES = 72
ALGORITHM = "HS256"


class InvalidToken(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    role: str
    issued_at: int = 0


def hash_password(password: str) -> str:
    raw = password.encode()
    if len(raw) > BCRYPT_MAX_BYTES:
        raise ValueError("password longer than 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


# Checked when a username does not exist, so a wrong login takes as long as for a real account.
DUMMY_PASSWORD_HASH = hash_password("senha-que-ninguem-usa")


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode())
    except ValueError:
        # Not a bcrypt hash, e.g. the "!" of the system account.
        return False


def generate_recovery_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def hash_recovery_code(code: str) -> str:
    # Plain SHA-256 is enough here: the code has 80 random bits, unlike a human-chosen password.
    return hashlib.sha256(normalize_recovery_code(code).encode()).hexdigest()


def recovery_code_matches(code: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_recovery_code(code), stored_hash)


def create_token(user_id: int, role: str, now: datetime) -> str:
    settings = get_settings()
    expires = now + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    claims = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str, now: datetime) -> TokenClaims:
    # Expiry is checked against the injected clock instead of PyJWT's system time.
    options = {"verify_exp": False, "verify_iat": False, "require": ["sub", "role", "exp"]}
    try:
        claims = jwt.decode(token, get_settings().JWT_SECRET, [ALGORITHM], options=options)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError) as error:
        raise InvalidToken from error
    if now.timestamp() >= claims["exp"]:
        raise InvalidToken
    # Tokens issued before "iat" existed have none; 0 makes them older than any password change.
    return TokenClaims(user_id=user_id, role=claims["role"], issued_at=claims.get("iat", 0))
