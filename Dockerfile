FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

RUN useradd --create-home codequest
WORKDIR /app
RUN chown codequest /app
USER codequest

# Dependencies first: this layer is rebuilt only when the lock file changes.
COPY --chown=codequest pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=codequest . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Shell form so that ${PORT} is expanded; exec hands the signals from the host to uvicorn.
# Trusted proxy addresses come from FORWARDED_ALLOW_IPS, set on the host (default 127.0.0.1).
CMD alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
