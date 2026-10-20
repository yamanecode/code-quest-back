import pytest

from app.domain.accounts import account_errors, normalize_username

GOOD_PASSWORD = "segredo123"


def test_T_DOM_ACC_01_username_is_stored_lower_case():
    assert normalize_username("Maria_01.Silva") == "maria_01.silva"


def test_T_DOM_ACC_01_valid_account_has_no_errors():
    assert account_errors("ana.b_9", GOOD_PASSWORD) == []
    assert account_errors("abc", GOOD_PASSWORD) == []
    assert account_errors("a" * 30, GOOD_PASSWORD) == []


@pytest.mark.parametrize("username", ["ab", "a" * 31, "ana b", "ana-b", "joão", "Ana", "", "ana!"])
def test_T_DOM_ACC_02_invalid_username(username):
    assert account_errors(username, GOOD_PASSWORD) == [
        "O nome de usuário deve ter de 3 a 30 caracteres: letras minúsculas, números, _ ou ."
    ]


def test_T_DOM_ACC_02_non_text_username_is_invalid():
    assert len(account_errors(None, GOOD_PASSWORD)) == 1


@pytest.mark.parametrize("password", ["a" * 8, "a" * 72, "senha com espaço"])
def test_T_DOM_ACC_03_password_length_accepted(password):
    assert account_errors("ana", password) == []


@pytest.mark.parametrize("password", ["a" * 7, "a" * 73, "", None])
def test_T_DOM_ACC_03_password_length_rejected(password):
    assert account_errors("ana", password) == ["A senha deve ter de 8 a 72 caracteres."]


def test_T_DOM_ACC_03_password_over_72_bytes_rejected():
    # 40 accented characters are 80 bytes in UTF-8, beyond what bcrypt can hash.
    assert account_errors("ana", "ç" * 40) == ["A senha é longa demais. Use menos acentos."]


def test_T_DOM_ACC_03_both_errors_are_listed():
    assert len(account_errors("a", "curta")) == 2
