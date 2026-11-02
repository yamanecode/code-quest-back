# CodeQuest API

Backend of **CodeQuest**, a web platform where students practise the four computational-thinking skills (algorithmic thinking, decomposition, abstraction and pattern recognition) by solving short logic challenges without code. Challenges are grouped in missions; students earn XP, levels, titles and badges, take part in weekly and monthly rankings and a weekly class goal, and can ask for hints written by a language model that never reveal the solution. Professors create classes (turmas), missions and challenges, publish them and follow their students' progress.

Academic prototype developed for an undergraduate thesis (TCC) in Computer Engineering at Facens. The user interface lives in the separate `code-quest-front` repository; all text shown to users is in Brazilian Portuguese.

## Stack

- Python 3.12, [FastAPI](https://fastapi.tiangolo.com/), Pydantic 2 and pydantic-settings
- PostgreSQL 16 (Docker), SQLAlchemy 2.0, Alembic
- bcrypt (password hashes) and PyJWT (HS256 tokens)
- httpx for the language-model adapter (any OpenAI-compatible endpoint)
- [uv](https://docs.astral.sh/uv/) for environments and dependencies
- pytest, pytest-cov, ruff and import-linter

## Getting started

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/), Docker and, on Windows, PowerShell for the scripts.

```
cp .env.example .env                  # then edit the passwords and JWT_SECRET
docker compose up -d db               # PostgreSQL on localhost:5432
uv sync                               # create .venv and install the locked dependencies
uv run alembic upgrade head           # create the tables
uv run python -m app.cli load-base content/base
uv run python -m app.cli seed-demo    # optional demonstration data (add --students for six students)
uv run uvicorn app.main:app --reload  # http://localhost:8000/docs
```

On its first start the database container also creates the `codequest_test` and `codequest_functional` databases (`docker/init-db.sql`).

## Configuration

Settings are read from environment variables or from `.env` (never committed; see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | | Credentials of the database container |
| `DATABASE_URL` | | Application database (`postgresql+psycopg://...`) |
| `TEST_DATABASE_URL` | | Database used by the integration tests; truncated by them |
| `FUNCTIONAL_DATABASE_URL` | | Database recreated by the functional test script |
| `JWT_SECRET` | | Secret used to sign the access tokens |
| `JWT_EXPIRE_HOURS` | `8` | Token lifetime |
| `FRONTEND_ORIGIN` | | The only origin allowed by CORS |
| `HINT_COOLDOWN_SECONDS` | `15` | Minimum time between two requested hints (there is no cap on how many) |
| `LOGIN_MAX_ATTEMPTS` | `5` | Failed logins allowed for one username from one client address inside the window; the next login answers 429 |
| `LOGIN_WINDOW_SECONDS` | `900` | Length of that window, in seconds |
| `LLM_PROVIDER` | `fake` | `fake` (deterministic answers, no network) or `openai_compatible` |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | | Endpoint, model and key for `openai_compatible` |
| `LLM_REASONING_EFFORT` | | Optional `reasoning_effort` sent to reasoning models (e.g. `low`), so hidden reasoning does not use up the reply |
| `FAKE_LLM_LOG` | | When set, the fake provider appends every prompt it receives to this file |
| `LLM_DAILY_LIMIT` | `0` | Model calls allowed per day (America/Sao_Paulo), failed calls included; `0` means no limit. Once reached, hints use the fixed texts, the review lists only the rule violations and drafts answer 503 until midnight |
| `CODEQUEST_PROFESSOR_PASSWORD` | | Password used by `create-professor`, `reset-password` and `seed-demo`; prompted when empty |
| `CODEQUEST_DEMO_PASSWORD` | | Password of the demo students of `seed-demo --students`; prompted when empty in a terminal, an error without one |

When the language model fails or times out, hints fall back to fixed texts, so the application keeps working without a provider.

## Online demo

The `Dockerfile` builds the production image: it installs the locked dependencies (without the development group), runs as a non-root user and, on start, applies the migrations and serves the API on `$PORT` (default `8000`).

```
docker build -t codequest-back .
docker run -p 8000:8000 -e DATABASE_URL=... -e JWT_SECRET=... -e FRONTEND_ORIGIN=... codequest-back
```

Load the base game once from a shell in the container (`python -m app.cli load-base content/base`) and create the professor accounts the same way.

- **Client address behind a proxy.** The server reads `X-Forwarded-For` only when the request comes from an address listed in `FORWARDED_ALLOW_IPS` (uvicorn's setting, default `127.0.0.1`). The login limit counts failures per username and client address, so set `FORWARDED_ALLOW_IPS` on the host to the address range of its proxy. Use `*` only on a host where the container can be reached exclusively through that proxy (check the host's documentation first): with `*`, anyone who reaches the container directly can choose the address the login limit sees.
- **Spending.** Set `LLM_DAILY_LIMIT`, a spending cap in the AI provider's dashboard, or both, before sharing the address.

## Commands

| Command | What it does |
|---|---|
| `uv run python -m app.cli create-professor <username>` | Creates a professor account. There is no public professor sign-up. |
| `uv run python -m app.cli reset-password <username>` | Sets a new password for a professor or a student (for example one who lost both the password and the recovery code). |
| `uv run python -m app.cli load-base content/base` | Loads the base game: the badges, the internal `codequest` account (which cannot log in) and every `content/base/*.json` file as a published mission visible to every student. All files are validated first; any rule violation aborts the load, naming the file and the challenge, and nothing is stored. Every mission and challenge in the files has a `key`; running the command again creates what is new and updates text changes, and it stops (naming the challenge) when the structure of a challenge that students already answered was changed. |
| `uv run python -m app.cli seed-demo` | Creates demonstration data: the badges, professor `prof_demo`, turma "Turma Demo" (join code `DEMO01`) and the published mission "Missão de exemplo" with one challenge of each type. Running it again creates only what is missing. |
| `uv run python -m app.cli seed-demo --students` | Also creates six students, `demo_aluno1` to `demo_aluno6`, members of "Turma Demo", with answers on the demo and base challenges (some after wrong answers) dated between Monday 00:00 of the current week and now, so rankings, badges and the class goal have data. Needs the base game loaded first. The answers go through the normal grading, XP and badge rules; no hint is generated and the model is never called. Students that already exist are left as they are. |
| `uv run alembic upgrade head` | Applies the database migrations. |

### Base game files

Each file in `content/base/` is one mission:

```json
{
  "title": "Trilha: Pensamento algorítmico",
  "description": "...",
  "position": 1,
  "challenges": [
    {"title": "...", "statement": "...", "type": "ordering", "content": {}, "explanation": "..."}
  ]
}
```

`type` is `ordering`, `grouping`, `filtering` or `pattern`, and `content` follows that type's template (items, groups or options, plus the solution). The limits of each template are checked by the same rules used when a professor saves a challenge.

## Architecture

The code follows a layered architecture; each layer only depends on the layers below it, and the rules are checked by `import-linter` (contracts in `pyproject.toml`).

```
app/
  api/        presentation: routers, request/response schemas, auth dependencies, error mapping
  services/   application: one method per use case, owns the transaction, builds the prompts
  domain/     domain: pure Python rules (templates, grading, XP, levels, badges,
              rankings, class goal, Continuar card, "Novo" label, hint leak check)
  infra/      infrastructure: ORM models, repositories, language-model adapters, security
  core/       configuration, clock (America/Sao_Paulo) and the LLMClient port
  cli.py      administration commands
  main.py     application factory
```

- Routers validate the input and call one service method; they never contain game rules or queries.
- Services raise their own exceptions (`app/services/exceptions.py`), which `app/api/errors.py` turns into `{"detail": "<code>", "message": "<texto>"}` responses.
- The domain imports only the standard library and has 100 % test coverage.
- Services talk to the language model only through the `LLMClient` protocol (`app/core/ports.py`); the concrete client is chosen by `LLM_PROVIDER`.
- XP, levels, rankings, class-goal progress, the Continuar challenge and the "Novo" labels are computed from stored submissions and XP events instead of counters.

FastAPI serves the interactive API documentation at `/docs`.

## Tests

There are two kinds of tests, kept in separate folders.

**Internal tests** (`tests/unit`, `tests/integration`) are written with the code and may import it. Unit tests need no database; integration tests use the `TEST_DATABASE_URL` database, a fixed clock and a scripted fake language model.

```
uv run pytest tests/unit -q
uv run pytest tests/unit tests/integration -q
```

**Functional tests** (`tests/functional`) are black-box acceptance tests: they only send HTTP requests to a running server and are derived from the requirements in `docs/requirements.md`, each tagged with the requirement it proves. The script recreates the functional database, loads the base game, starts the server with the fake language model, runs the suite and writes the traceability matrix to `docs/evidence/traceability.md`.

```
powershell -File scripts/functional.ps1
```

With `-Serve` the script only prepares the database and keeps the server running on port 8001 (for the frontend functional suite); it needs `CODEQUEST_PROFESSOR_PASSWORD`, the password of the functional professors `ft_prof` and `ft_prof2`.

No test in the default run or the quality gate calls a real language model. `tests/live` holds an optional manual check against a real provider, excluded by default.

### Quality gate

```
powershell -File scripts/check.ps1
```

Runs `ruff check`, `ruff format --check`, `lint-imports`, `alembic check`, the internal tests with coverage and the 100 % coverage check of `app/domain`. Reports are written to `docs/evidence/`.
