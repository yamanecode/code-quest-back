import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import traceability  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "ruff", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


@pytest.mark.req("QUA-02")
def test_ruff_check_and_format_clean():
    assert _run("check", ".").returncode == 0, _run("check", ".").stdout
    assert _run("format", "--check", ".").returncode == 0, _run("format", "--check", ".").stdout


@pytest.mark.req("SEC-07")
def test_ruff_bandit_rules_enabled():
    config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"S"' in config
    assert _run("check", ".", "--select", "S").returncode == 0


TABLE = """
| ID | Phase | Requirement | Acceptance |
|---|---|---|---|
| AAA-01 | 0 | Has a test with `a|b` pipe | Some test. |
| AAA-02 | 0 | Manual one | MANUAL: inspect. |
| AAA-03 | 2 | Later phase | Some test. |
"""


@pytest.mark.req("QUA-03")
def test_traceability_parses_rows_with_pipes_and_manual():
    reqs = traceability.parse_requirements(TABLE)
    assert set(reqs) == {"AAA-01", "AAA-02", "AAA-03"}
    assert reqs["AAA-01"]["title"] == "Has a test with `a|b` pipe"
    assert reqs["AAA-02"]["manual"] is True


@pytest.mark.req("QUA-03")
def test_traceability_flags_missing_and_unknown():
    reqs = traceability.parse_requirements(TABLE)
    _, errors = traceability.build_report(reqs, {"ZZZ-99": ["t::x"]}, 0, {})
    assert any("AAA-01" in e for e in errors)
    assert any("ZZZ-99" in e for e in errors)
    assert not any("AAA-02" in e or "AAA-03" in e for e in errors)
    _, errors = traceability.build_report(reqs, {"AAA-01": ["t::x"]}, 0, {})
    assert errors == []
