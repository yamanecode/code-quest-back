"""Build the traceability matrix: requirement -> functional tests -> result.

Usage: uv run python tools/traceability.py [--junit PATH] [--out PATH]
Exits with 1 when a non-manual requirement has no functional test or a test is
tagged with an unknown requirement ID.
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "docs" / "requirements.md"
FUNCTIONAL_DIR = ROOT / "tests" / "functional"
JUNIT = ROOT / "docs" / "evidence" / "functional-junit.xml"
OUTPUT = ROOT / "docs" / "evidence" / "traceability.md"

ID_PATTERN = re.compile(r"^[A-Z]+-\d+$")
STATUSES = ("passed", "failed", "MISSING", "manual")


@dataclass
class Requirement:
    id: str
    phase: str
    requirement: str
    acceptance: str

    @property
    def manual(self) -> bool:
        return self.acceptance.startswith("MANUAL:")


@dataclass
class Row:
    id: str
    requirement: str
    tests: list[str]
    status: str


@dataclass
class Report:
    rows: list[Row]
    errors: list[str] = field(default_factory=list)


def split_row(line: str) -> list[str]:
    """Split a markdown table row; `\\|` and pipes inside `code` are part of the text."""
    cells, current, in_code, i = [], "", False, 0
    while i < len(line):
        char = line[i]
        if char == "\\" and line[i + 1 : i + 2] == "|":
            current += "|"
            i += 2
            continue
        if char == "`":
            in_code = not in_code
        if char == "|" and not in_code:
            cells.append(current.strip())
            current = ""
        else:
            current += char
        i += 1
    cells.append(current.strip())
    return cells[1:-1]


def parse_requirements(markdown: str) -> list[Requirement]:
    requirements = []
    for line in markdown.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = split_row(line.strip())
        if len(cells) < 4 or not ID_PATTERN.match(cells[0]):
            continue
        requirements.append(Requirement(cells[0], cells[1], cells[2], cells[3]))
    return requirements


class _MarkerCollector:
    def __init__(self) -> None:
        self.tests: dict[str, list[str]] = {}

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        for item in session.items:
            self.tests[item.nodeid] = [m.args[0] for m in item.iter_markers("req")]


def collect_tagged_tests(directory: Path) -> dict[str, list[str]]:
    """Map node id -> requirement IDs of every functional test under `directory`."""
    collector = _MarkerCollector()
    args = [
        "--collect-only",
        "-qq",
        "-m",
        "functional",
        "-p",
        "no:cacheprovider",
        "--rootdir",
        str(ROOT),
        "-c",
        str(ROOT / "pyproject.toml"),
        str(directory),
    ]
    exit_code = pytest.main(args, plugins=[collector])
    if exit_code not in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
        raise RuntimeError(f"collecting functional tests failed (pytest exit code {exit_code})")
    return collector.tests


def junit_key(node_id: str) -> tuple[str, str]:
    """The (classname, name) pair pytest writes to JUnit XML for a node id."""
    path, *names = node_id.split("::")
    parts = path.removesuffix(".py").replace("/", ".").split(".") + names
    return ".".join(parts[:-1]), parts[-1]


def read_results(junit_path: Path, node_ids: Iterable[str]) -> dict[str, str]:
    if not junit_path.exists():
        return {}
    outcomes = {}
    for case in ET.parse(junit_path).iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        outcomes[(case.get("classname", ""), case.get("name", ""))] = outcome
    return {
        node_id: outcomes[junit_key(node_id)]
        for node_id in node_ids
        if junit_key(node_id) in outcomes
    }


def requirement_status(requirement: Requirement, tests: list[str], results: dict[str, str]) -> str:
    if requirement.manual:
        return "manual"
    if not tests:
        return "MISSING"
    if all(results.get(test) == "passed" for test in tests):
        return "passed"
    return "failed"


def build_report(
    requirements: list[Requirement], tests: dict[str, list[str]], results: dict[str, str]
) -> Report:
    known = {r.id for r in requirements}
    errors = [
        f"{test} is tagged with unknown requirement {req_id}"
        for test, req_ids in tests.items()
        for req_id in req_ids
        if req_id not in known
    ]
    rows = []
    for requirement in requirements:
        covering = [test for test, req_ids in tests.items() if requirement.id in req_ids]
        status = requirement_status(requirement, covering, results)
        if status == "MISSING":
            errors.append(f"{requirement.id} has no functional test")
        rows.append(Row(requirement.id, requirement.requirement, covering, status))
    return Report(rows, errors)


def render_markdown(report: Report) -> str:
    totals = " · ".join(
        f"{status}: {sum(row.status == status for row in report.rows)}" for status in STATUSES
    )
    lines = [
        "# Traceability matrix",
        "",
        "Requirements of `docs/requirements.md` and the functional tests that prove them.",
        "",
        totals,
        "",
        "| ID | Requirement | Tests | Status |",
        "|---|---|---|---|",
    ]
    for row in report.rows:
        tests = "<br>".join(f"`{test}`" for test in row.tests) or "—"
        requirement = row.requirement.replace("|", "\\|")
        lines.append(f"| {row.id} | {requirement} | {tests} | {row.status} |")
    if report.errors:
        lines += ["", "## Errors", ""] + [f"- {error}" for error in report.errors]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--requirements", type=Path, default=REQUIREMENTS)
    parser.add_argument("--functional", type=Path, default=FUNCTIONAL_DIR)
    parser.add_argument("--junit", type=Path, default=JUNIT)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    requirements = parse_requirements(args.requirements.read_text(encoding="utf-8"))
    tests = collect_tagged_tests(args.functional)
    results = read_results(args.junit, tests)
    report = build_report(requirements, tests, results)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(report), encoding="utf-8")
    print(f"Traceability matrix written to {args.out}")
    for error in report.errors:
        print(f"ERROR: {error}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
