import textwrap

import pytest

from tools import traceability as tr

REQUIREMENTS_MD = textwrap.dedent(
    r"""
    # Requirements

    | ID | Phase | Requirement | Acceptance |
    |---|---|---|---|
    | RF-01 | 3 | Sign-up | Returns 201 for `a\|b` input. |
    | RF-09 | 6 | Rankings | `scope=global|classroom` and `period=week|month` work. |
    | SG-11 | 5 | Game elements | MANUAL: inspect the screens. |

    ## Non-functional

    | ID | Phase | Requirement | Acceptance |
    |---|---|---|---|
    | RNF-05 | 0 | Errors in Portuguese | Every error has `detail` and `message`. |
    """
)


def requirement_ids(requirements):
    return [r.id for r in requirements]


def test_T_TRACE_01_parser_reads_every_table_and_handles_pipes():
    requirements = tr.parse_requirements(REQUIREMENTS_MD)

    assert requirement_ids(requirements) == ["RF-01", "RF-09", "SG-11", "RNF-05"]
    rf01, rf09, sg11, rnf05 = requirements
    assert rf01.acceptance == "Returns 201 for `a|b` input."
    assert rf09.requirement == "Rankings"
    assert rf09.acceptance == "`scope=global|classroom` and `period=week|month` work."
    assert sg11.manual and not rf01.manual
    assert rnf05.phase == "0"


def test_T_TRACE_01_parser_reads_the_real_requirements_file():
    requirements = tr.parse_requirements(tr.REQUIREMENTS.read_text(encoding="utf-8"))

    ids = requirement_ids(requirements)
    assert len(ids) == len(set(ids))
    assert {"RF-01", "RF-22", "SG-13", "RNF-05"} <= set(ids)


def test_T_TRACE_02_requirement_without_test_is_missing():
    requirements = tr.parse_requirements(REQUIREMENTS_MD)
    tests = {"tests/functional/auth/test_auth.py::test_FT_AUTH_01": ["RF-01"]}
    results = {"tests/functional/auth/test_auth.py::test_FT_AUTH_01": "passed"}

    report = tr.build_report(requirements, tests, results)

    status = {row.id: row.status for row in report.rows}
    assert status == {"RF-01": "passed", "RF-09": "MISSING", "SG-11": "manual", "RNF-05": "MISSING"}
    assert report.errors == ["RF-09 has no functional test", "RNF-05 has no functional test"]


def test_T_TRACE_03_tag_with_unknown_id_is_an_error():
    requirements = tr.parse_requirements(REQUIREMENTS_MD)
    tests = {
        "t.py::test_a": ["RF-01", "RF-99"],
        "t.py::test_b": ["RF-09"],
        "t.py::test_c": ["RNF-05"],
    }

    report = tr.build_report(requirements, tests, {})

    assert report.errors == ["t.py::test_a is tagged with unknown requirement RF-99"]


def test_T_TRACE_04_status_comes_from_the_results():
    requirements = tr.parse_requirements(REQUIREMENTS_MD)
    tests = {"t.py::ok": ["RF-01", "RF-09"], "t.py::bad": ["RF-09"], "t.py::not_run": ["RNF-05"]}
    results = {"t.py::ok": "passed", "t.py::bad": "failed"}

    report = tr.build_report(requirements, tests, results)

    status = {row.id: row.status for row in report.rows}
    assert status["RF-01"] == "passed"
    assert status["RF-09"] == "failed"
    assert status["RNF-05"] == "failed"
    assert report.errors == []


def test_T_TRACE_04_junit_results_are_keyed_by_node_id(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
        <testsuites><testsuite name="pytest">
          <testcase classname="tests.functional.auth.test_auth" name="test_FT_AUTH_01_ok"/>
          <testcase classname="tests.functional.auth.test_auth.TestLogin" name="test_FT_AUTH_02">
            <failure message="boom"/>
          </testcase>
          <testcase classname="tests.functional.auth.test_auth" name="test_FT_AUTH_03">
            <skipped message="skip"/>
          </testcase>
        </testsuite></testsuites>""",
        encoding="utf-8",
    )
    node_ids = [
        "tests/functional/auth/test_auth.py::test_FT_AUTH_01_ok",
        "tests/functional/auth/test_auth.py::TestLogin::test_FT_AUTH_02",
        "tests/functional/auth/test_auth.py::test_FT_AUTH_03",
    ]

    results = tr.read_results(junit, node_ids)

    assert results == {
        node_ids[0]: "passed",
        node_ids[1]: "failed",
        node_ids[2]: "skipped",
    }


def test_T_TRACE_05_collects_req_markers_of_functional_tests(tmp_path):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(
        textwrap.dedent(
            """
            import pytest

            pytestmark = pytest.mark.functional


            @pytest.mark.req("RF-01")
            @pytest.mark.req("SG-09")
            def test_FT_AUTH_01_sign_up():
                pass


            def test_FT_AUTH_02_untagged():
                pass
            """
        ),
        encoding="utf-8",
    )

    tests = tr.collect_tagged_tests(tmp_path)

    tagged = {node.split("::")[-1]: sorted(ids) for node, ids in tests.items()}
    assert tagged == {"test_FT_AUTH_01_sign_up": ["RF-01", "SG-09"], "test_FT_AUTH_02_untagged": []}


def test_T_TRACE_06_markdown_lists_every_requirement_and_totals():
    requirements = tr.parse_requirements(REQUIREMENTS_MD)
    report = tr.build_report(requirements, {"t.py::ok": ["RF-01"]}, {"t.py::ok": "passed"})

    markdown = tr.render_markdown(report)

    assert "| RF-01 | Sign-up | `t.py::ok` | passed |" in markdown
    assert "| SG-11 | Game elements | — | manual |" in markdown
    assert "passed: 1" in markdown and "MISSING: 2" in markdown and "manual: 1" in markdown


@pytest.mark.parametrize(("errors", "code"), [([], 0), (["RF-09 has no functional test"], 1)])
def test_T_TRACE_07_exit_code_follows_errors(tmp_path, monkeypatch, errors, code):
    monkeypatch.setattr(tr, "collect_tagged_tests", lambda directory: {})
    monkeypatch.setattr(tr, "build_report", lambda *args: tr.Report(rows=[], errors=list(errors)))
    out = tmp_path / "traceability.md"

    exit_code = tr.main(["--junit", str(tmp_path / "none.xml"), "--out", str(out)])

    assert exit_code == code
    assert out.exists()
