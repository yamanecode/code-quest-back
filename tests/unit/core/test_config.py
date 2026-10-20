from app.core.config import Settings


def test_T_CONFIG_01_defaults():
    settings = Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://x", JWT_SECRET="s")

    assert settings.JWT_EXPIRE_HOURS == 8
    assert settings.HINT_CAP == 5
    assert settings.HINT_COOLDOWN_SECONDS == 15
    assert settings.LLM_PROVIDER == "fake"
    assert settings.FAKE_LLM_LOG is None


def test_T_CONFIG_02_environment_overrides_defaults(monkeypatch):
    monkeypatch.setenv("HINT_COOLDOWN_SECONDS", "2")

    settings = Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://x", JWT_SECRET="s")

    assert settings.HINT_COOLDOWN_SECONDS == 2


def test_T_CONFIG_03_professor_password_is_optional_and_read_from_the_env_file(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("CODEQUEST_PROFESSOR_PASSWORD", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("CODEQUEST_PROFESSOR_PASSWORD=senha-do-arquivo\n", encoding="utf-8")
    required = {"DATABASE_URL": "postgresql+psycopg://x", "JWT_SECRET": "s"}

    assert Settings(_env_file=None, **required).CODEQUEST_PROFESSOR_PASSWORD is None
    assert Settings(_env_file=env_file, **required).CODEQUEST_PROFESSOR_PASSWORD == (
        "senha-do-arquivo"
    )
