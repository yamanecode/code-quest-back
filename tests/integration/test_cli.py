from sqlalchemy import func, select

from app import cli
from app.domain.enums import Role
from app.infra.db.models import User
from app.infra.security import verify_password

PASSWORD = "senha-do-professor"


def test_T_CLI_01_create_professor_with_password_from_env(session, monkeypatch, capsys):
    monkeypatch.setenv("CODEQUEST_PROFESSOR_PASSWORD", PASSWORD)

    exit_code = cli.create_professor(session, "Prof_Ana")

    assert exit_code == 0
    professor = session.scalar(select(User).where(User.username == "prof_ana"))
    assert professor.role == Role.PROFESSOR
    assert verify_password(PASSWORD, professor.password_hash)
    assert PASSWORD not in capsys.readouterr().out


def test_T_CLI_01_password_is_prompted_without_env(session, monkeypatch):
    monkeypatch.delenv("CODEQUEST_PROFESSOR_PASSWORD", raising=False)
    monkeypatch.setattr(cli, "getpass", lambda prompt: PASSWORD)

    assert cli.create_professor(session, "prof_bia") == 0


def test_T_CLI_01_prompted_passwords_must_match(session, monkeypatch):
    monkeypatch.delenv("CODEQUEST_PROFESSOR_PASSWORD", raising=False)
    answers = iter([PASSWORD, "outra-senha"])
    monkeypatch.setattr(cli, "getpass", lambda prompt: next(answers))

    assert cli.create_professor(session, "prof_bia") == 1
    assert session.scalar(select(User)) is None


def test_T_CLI_02_duplicate_username_fails(session, monkeypatch, capsys):
    monkeypatch.setenv("CODEQUEST_PROFESSOR_PASSWORD", PASSWORD)
    cli.create_professor(session, "prof_ana")

    exit_code = cli.create_professor(session, "prof_ana")

    assert exit_code == 1
    assert "já está em uso" in capsys.readouterr().err
    assert session.scalar(select(func.count()).select_from(User)) == 1


def test_T_CLI_02_invalid_password_fails(session, monkeypatch, capsys):
    monkeypatch.setenv("CODEQUEST_PROFESSOR_PASSWORD", "curta")

    assert cli.create_professor(session, "prof_ana") == 1
    assert "8 a 72 caracteres" in capsys.readouterr().err


def test_T_CLI_03_main_parses_create_professor(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "create_professor", lambda session, name: calls.append(name) or 0)
    monkeypatch.setattr(cli, "open_session", lambda: _NullSession())

    assert cli.main(["create-professor", "prof_ana"]) == 0
    assert calls == ["prof_ana"]


class _NullSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
