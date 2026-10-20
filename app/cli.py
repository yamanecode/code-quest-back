"""Administration commands: uv run python -m app.cli <command>."""

import argparse
import os
import sys
from getpass import getpass

from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.infra.db.session import get_sessionmaker
from app.services.auth_service import AuthService
from app.services.exceptions import ServiceError, ValidationFailed


def open_session() -> Session:
    return get_sessionmaker()()


def _read_password() -> str | None:
    password = os.environ.get("CODEQUEST_PROFESSOR_PASSWORD")
    if password:
        return password
    password = getpass("Senha do professor: ")
    if getpass("Repita a senha: ") != password:
        return None
    return password


def create_professor(session: Session, username: str) -> int:
    password = _read_password()
    if password is None:
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    try:
        account = AuthService(session, SystemClock()).create_professor(username, password)
    except ServiceError as error:
        details = error.errors if isinstance(error, ValidationFailed) else []
        print(error.message, *details, sep="\n", file=sys.stderr)
        return 1
    print(f"Professor '{account.username}' criado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    professor = commands.add_parser("create-professor", help="cria uma conta de professor")
    professor.add_argument("username")
    args = parser.parse_args(argv)

    with open_session() as session:
        return create_professor(session, args.username)


if __name__ == "__main__":
    sys.exit(main())
