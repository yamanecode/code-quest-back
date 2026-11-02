from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGE_FILES = {
    "app",
    "alembic",
    "alembic.ini",
    "content",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
}


def test_T_DEPLOY_01_image_trusts_proxy_headers_only_from_the_env_and_leaves_secrets_out():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    command = next(line for line in dockerfile.splitlines() if line.startswith("CMD"))
    rules = [
        line
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]

    assert "alembic upgrade head" in command
    assert "--proxy-headers" in command
    # The trusted proxy addresses come from FORWARDED_ALLOW_IPS on the host.
    assert "--forwarded-allow-ips" not in dockerfile
    assert "USER " in dockerfile
    # Everything is ignored except the files the server needs (.env, tests, .git stay out).
    assert rules[0] == "*"
    assert {rule[1:] for rule in rules if rule.startswith("!")} == IMAGE_FILES
