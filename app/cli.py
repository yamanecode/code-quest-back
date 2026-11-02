"""Administration commands: uv run python -m app.cli <command>."""

import argparse
import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.infra.db.session import get_sessionmaker
from app.infra.llm.factory import build_llm_client
from app.services.auth_service import AuthService
from app.services.base_content_service import BaseContentService
from app.services.demo_service import DemoService
from app.services.exceptions import ServiceError, ValidationFailed


def open_session() -> Session:
    return get_sessionmaker()()


def _prompt_password() -> str | None:
    password = getpass("Senha: ")
    if getpass("Repita a senha: ") != password:
        return None
    return password


def _read_password() -> str | None:
    return get_settings().CODEQUEST_PROFESSOR_PASSWORD or _prompt_password()


def _read_demo_password() -> str | None:
    password = get_settings().CODEQUEST_DEMO_PASSWORD
    if password:
        return password
    # Without a terminal (a script, a container) a prompt would wait forever.
    if not sys.stdin.isatty():
        raise ValidationFailed(
            "demo_password_missing",
            "Defina CODEQUEST_DEMO_PASSWORD ou rode o comando em um terminal.",
        )
    print("Senha dos estudantes de demonstração.")
    return _prompt_password()


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


def reset_password(session: Session, username: str) -> int:
    password = _read_password()
    if password is None:
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    try:
        AuthService(session, SystemClock()).reset_password_as_admin(username, password)
    except ServiceError as error:
        _print_error(error)
        return 1
    print(f"Senha de '{username.lower()}' alterada.")
    return 0


def seed_demo(session: Session, students: bool = False) -> int:
    # The model is never called: the seeded wrong answers skip the hint step.
    service = DemoService(session, SystemClock(), build_llm_client(get_settings()))
    try:
        created = service.seed(_read_password, _read_demo_password if students else None)
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
    lines = (
        ("Chave associada pelo título", report.matched),
        ("Sem arquivo correspondente, sem chave", report.unmatched),
        ("Criado", report.created),
        ("Atualizado", report.updated),
        ("Mantido", report.kept),
        ("Fora dos arquivos, mantido na missão", report.not_in_files),
    )
    for prefix, names in lines:
        for name in names:
            print(f"{prefix}: {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    professor = commands.add_parser("create-professor", help="cria uma conta de professor")
    professor.add_argument("username")
    reset = commands.add_parser("reset-password", help="define uma nova senha para uma conta")
    reset.add_argument("username")
    demo = commands.add_parser("seed-demo", help="cria os dados de demonstração")
    demo.add_argument(
        "--students",
        action="store_true",
        help="cria também seis estudantes com progresso nesta semana (precisa do jogo base)",
    )
    base = commands.add_parser("load-base", help="carrega o jogo base a partir de uma pasta")
    base.add_argument("directory")
    args = parser.parse_args(argv)

    with open_session() as session:
        if args.command == "create-professor":
            return create_professor(session, args.username)
        if args.command == "reset-password":
            return reset_password(session, args.username)
        if args.command == "seed-demo":
            return seed_demo(session, students=args.students)
        return load_base(session, args.directory)


if __name__ == "__main__":
    sys.exit(main())
