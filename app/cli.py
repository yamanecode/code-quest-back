"""Administration commands: uv run python -m app.cli <command>."""

import argparse
import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.infra.db.session import get_sessionmaker
from app.services.auth_service import AuthService
from app.services.base_content_service import BaseContentService
from app.services.demo_service import DemoService
from app.services.exceptions import ServiceError, ValidationFailed


def open_session() -> Session:
    return get_sessionmaker()()


def _read_password() -> str | None:
    password = get_settings().CODEQUEST_PROFESSOR_PASSWORD
    if password:
        return password
    password = getpass("Senha do professor: ")
    if getpass("Repita a senha: ") != password:
        return None
    return password


def _print_error(error: ServiceError) -> None:
    details = error.errors if isinstance(error, ValidationFailed) else []
    print(error.message, *details, sep="\n", file=sys.stderr)


def create_professor(session: Session, username: str) -> int:
    password = _read_password()
    if password is None:
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    try:
        account = AuthService(session, SystemClock()).create_professor(username, password)
    except ServiceError as error:
        _print_error(error)
        return 1
    print(f"Professor '{account.username}' criado.")
    return 0


def seed_demo(session: Session) -> int:
    try:
        created = DemoService(session).seed(_read_password)
    except ServiceError as error:
        _print_error(error)
        return 1
    if created:
        print("Criado: " + ", ".join(created) + ".")
    else:
        print("Os dados de demonstração já existem; nada foi criado.")
    return 0


def load_base(session: Session, directory: str) -> int:
    try:
        report = BaseContentService(session).load(Path(directory))
    except ServiceError as error:
        _print_error(error)
        return 1
    for title in report.created:
        print(f"Missão criada: {title}")
    for title in report.skipped:
        print(f"Missão já existente, mantida: {title}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    professor = commands.add_parser("create-professor", help="cria uma conta de professor")
    professor.add_argument("username")
    commands.add_parser("seed-demo", help="cria os dados de demonstração")
    base = commands.add_parser("load-base", help="carrega o jogo base a partir de uma pasta")
    base.add_argument("directory")
    args = parser.parse_args(argv)

    with open_session() as session:
        if args.command == "create-professor":
            return create_professor(session, args.username)
        if args.command == "seed-demo":
            return seed_demo(session)
        return load_base(session, args.directory)


if __name__ == "__main__":
    sys.exit(main())
