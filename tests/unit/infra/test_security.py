from datetime import datetime, timedelta

import jwt
import pytest

from app.core.clock import TIMEZONE
from app.core.config import get_settings
from app.infra.security import (
    InvalidToken,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=TIMEZONE)
SECRET = get_settings().JWT_SECRET


def test_T_SEC_01_hash_is_bcrypt_cost_12_and_verifies():
    hashed = hash_password("segredo123")

    assert hashed.startswith("$2b$12$")
    assert hashed != "segredo123"
    assert verify_password("segredo123", hashed)
    assert not verify_password("outra-senha", hashed)


def test_T_SEC_02_password_over_72_bytes_is_rejected():
    with pytest.raises(ValueError):
        hash_password("ç" * 40)
    assert not verify_password("ç" * 40, hash_password("segredo123"))


def test_T_SEC_03_non_bcrypt_hash_never_verifies():
    # The system account stores "!" so nobody can log in with it.
    assert not verify_password("qualquer-coisa", "!")


def test_T_SEC_04_token_round_trip():
    token = create_token(7, "student", NOW)

    claims = decode_token(token, NOW + timedelta(hours=7, minutes=59))

    assert claims.user_id == 7
    assert claims.role == "student"


def test_T_SEC_05_token_expires_after_8_hours():
    token = create_token(7, "student", NOW)

    with pytest.raises(InvalidToken):
        decode_token(token, NOW + timedelta(hours=8))


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        jwt.encode({"sub": "7", "role": "student", "exp": 9999999999}, "x" * 32, "HS256"),
        jwt.encode({"role": "student", "exp": 9999999999}, SECRET, "HS256"),
        jwt.encode({"sub": "abc", "role": "student", "exp": 9999999999}, SECRET, "HS256"),
    ],
)
def test_T_SEC_06_tampered_or_incomplete_token_is_rejected(token):
    with pytest.raises(InvalidToken):
        decode_token(token, NOW)
