import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import cli
from app.core.config import get_settings
from app.domain.enums import Role
from app.infra.db.models import Mission, User
from app.infra.security import verify_password

PASSWORD = "senha-do-professor"
BASE_DIR = Path(__file__).resolve().parents[2] / "content" / "base"


@pytest.fixture(autouse=True)
def fresh_settings(monkeypatch, tmp_path):
    """Settings are cached and read .env from the working directory; each test sets its own."""
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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


def test_T_CLI_03_main_parses_seed_demo_and_load_base(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "seed_demo", lambda session: calls.append("seed") or 0)
    monkeypatch.setattr(cli, "load_base", lambda session, path: calls.append(path) or 0)
    monkeypatch.setattr(cli, "open_session", lambda: _NullSession())

    assert cli.main(["seed-demo"]) == 0
    assert cli.main(["load-base", "content/base"]) == 0
    assert calls == ["seed", "content/base"]


def test_T_SEED_01_cli_seeds_once_with_password_from_env(session, monkeypatch, capsys):
    monkeypatch.setenv("CODEQUEST_PROFESSOR_PASSWORD", PASSWORD)

    assert cli.seed_demo(session) == 0
    assert "Criado: professor prof_demo" in capsys.readouterr().out
    assert cli.seed_demo(session) == 0
    assert "nada foi criado" in capsys.readouterr().out


def test_T_SEED_01_cli_reports_a_seed_error(session, monkeypatch, capsys):
    monkeypatch.setenv("CODEQUEST_PROFESSOR_PASSWORD", "curta")

    assert cli.seed_demo(session) == 1
    assert "8 a 72 caracteres" in capsys.readouterr().err


def test_T_BASE_02_cli_loads_the_base_game(session, capsys):
    assert cli.load_base(session, str(BASE_DIR)) == 0

    out = capsys.readouterr().out
    assert "Missão criada: Trilha: Pensamento algorítmico" in out
    assert session.scalar(select(func.count()).select_from(Mission)) == 5
    assert cli.load_base(session, str(BASE_DIR)) == 0
    assert "Missão já existente, mantida: Desafios mistos" in capsys.readouterr().out


def test_T_BASE_04_cli_names_the_broken_file_and_exits_1(session, capsys, tmp_path):
    shutil.copy(BASE_DIR / "01-algoritmos.json", tmp_path / "09-sem-desafios.json")
    broken = tmp_path / "09-sem-desafios.json"
    text = broken.read_text(encoding="utf-8").replace('"challenges"', '"x"', 1)
    broken.write_text(text, encoding="utf-8")

    assert cli.load_base(session, str(tmp_path)) == 1
    err = capsys.readouterr().err
    assert "09-sem-desafios.json: A missão deve ter pelo menos um desafio." in err
    assert session.scalar(select(func.count()).select_from(Mission)) == 0


class _NullSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_T_CLI_04_password_is_read_from_the_env_file_without_prompting(
    session, monkeypatch, tmp_path
):
    monkeypatch.delenv("CODEQUEST_PROFESSOR_PASSWORD", raising=False)
    env_line = f"CODEQUEST_PROFESSOR_PASSWORD={PASSWORD}\n"
    # The autouse fixture already made tmp_path the working directory.
    (tmp_path / ".env").write_text(env_line, encoding="utf-8")

    def no_prompt(prompt):
        raise AssertionError("the password in .env must be used")

    monkeypatch.setattr(cli, "getpass", no_prompt)

    assert cli.create_professor(session, "prof_arquivo") == 0

    user = session.scalar(select(User).filter_by(username="prof_arquivo"))
    assert verify_password(PASSWORD, user.password_hash)
