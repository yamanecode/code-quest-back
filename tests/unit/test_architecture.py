import ast
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINT_IMPORTS_CODE = "from importlinter.cli import lint_imports_command; lint_imports_command()"


def run_lint_imports(cwd: Path) -> subprocess.CompletedProcess:
    command = [sys.executable, "-c", LINT_IMPORTS_CODE, "--no-cache"]
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def is_app_module(name: str | None) -> bool:
    return name is not None and (name == "app" or name.startswith("app."))


def imports_app(source: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import) and any(is_app_module(a.name) for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.level == 0 and is_app_module(node.module):
            return True
    return False


def test_T_ARCH_01_layer_contracts_are_kept():
    result = run_lint_imports(ROOT)

    assert result.returncode == 0, result.stdout + result.stderr


def test_T_ARCH_01_violating_import_breaks_the_contracts(tmp_path):
    shutil.copytree(ROOT / "app", tmp_path / "app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    (tmp_path / "app" / "domain" / "leaky.py").write_text("import fastapi\n", encoding="utf-8")

    result = run_lint_imports(tmp_path)

    assert result.returncode != 0
    assert "Domain is pure Python BROKEN" in result.stdout


def test_T_ARCH_02_detector_recognises_app_imports():
    assert imports_app("import app")
    assert imports_app("from app.services import play_service")
    assert imports_app("import os\nif True:\n    import app.main as main\n")
    assert not imports_app("import httpx\nfrom apps import x\nfrom . import helpers\n")


def test_T_ARCH_02_functional_tests_never_import_app():
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "tests" / "functional").rglob("*.py")
        if imports_app(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []
