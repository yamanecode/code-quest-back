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
