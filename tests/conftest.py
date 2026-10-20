import os

# Settings are read from the environment; tests must not depend on the developer's .env.
os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-32-bytes")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://codequest:codequest@localhost:5432/codequest"
)
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")
os.environ["LLM_PROVIDER"] = "fake"
os.environ["HINT_CAP"] = "5"
os.environ["HINT_COOLDOWN_SECONDS"] = "15"
