import re

USERNAME_PATTERN = re.compile(r"[a-z0-9_.]{3,30}")
PASSWORD_MIN = 8
PASSWORD_MAX = 72
# bcrypt only reads the first 72 bytes; accented characters take two bytes in UTF-8.
PASSWORD_MAX_BYTES = 72


def normalize_username(raw: str) -> str:
    return raw.lower()


def password_errors(password: object) -> list[str]:
    if not isinstance(password, str) or not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        return [f"A senha deve ter de {PASSWORD_MIN} a {PASSWORD_MAX} caracteres."]
    if len(password.encode()) > PASSWORD_MAX_BYTES:
        return ["A senha é longa demais. Use menos acentos."]
    return []


def account_errors(username: object, password: object) -> list[str]:
    """Rules for an already normalized username and a password (RF-01)."""
    errors = []
    if not isinstance(username, str) or not USERNAME_PATTERN.fullmatch(username):
        errors.append(
            "O nome de usuário deve ter de 3 a 30 caracteres: letras minúsculas, números, _ ou ."
        )
    return errors + password_errors(password)
