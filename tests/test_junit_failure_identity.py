"""Contract tests for the pinned shared xprobe JUnit importer."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import xprobe


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("junit", [False, True])
def test_real_child_failure_evidence(tmp_path, junit):
    """Domain integration; generic classification/receipt coverage lives in xprobe."""
    (tmp_path / "test_shapes.py").write_text('''import sys
import pytest
import ascii_artist

@pytest.mark.parametrize("expected", ["SECRET_PARAM_ONE", "SECRET_PARAM_TWO"])
def test_square_wrong_expectation(expected):
    print("SECRET_STDOUT")
    print("SECRET_STDERR", file=sys.stderr)
    assert ascii_artist.generate_square(2) == expected, "SECRET_MESSAGE"

@pytest.fixture
def wrong_setup():
    assert ascii_artist.generate_triangle(1) == "SECRET_SETUP"

def test_setup(wrong_setup): pass

def test_pass():
    assert ascii_artist.generate_square(2) == "**\\n**"

@pytest.mark.skip(reason="SECRET_SKIP")
def test_skip(): pass
''', encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    env.pop("PYTEST_ADDOPTS", None)
    command = [sys.executable, "-m", "pytest", "-q"]
    if junit:
        command += ["--junitxml=junit.xml", "-o", "junit_logging=all"]
    result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True,
                            text=True, timeout=30)
    directory = None
    destination = os.environ.get("ASCII_FAILURE_EVIDENCE") if junit else None
    if destination:
        directory = Path(destination)
        directory.mkdir(parents=True)  # Reject reuse rather than mix old evidence.
        (directory / "child-exit.json").write_text(
            json.dumps({"returncode": result.returncode}) + "\n", encoding="utf-8")
        if (tmp_path / "junit.xml").exists():
            shutil.copyfile(tmp_path / "junit.xml", directory / "junit.xml")
    if junit:
        xml = (tmp_path / "junit.xml").read_text(encoding="utf-8")
        report = xprobe.cases_from_junit(
            xml, repository="myon-bioinformatics/ascii_artist",
            commit_sha=None, report_id="controlled-child")
        compact = xprobe.corpus_to_json(report["cases"], jsonl=True)
        if directory is not None:
            (directory / "failures.jsonl").write_text(compact, encoding="utf-8")
        assert report["truncated"] is False
        assert sorted((r["value"]["test"], r["value"]["kind"]) for r in report["cases"]) == [
            ("test_setup", "error"),
            ("test_square_wrong_expectation", "failure"),
            ("test_square_wrong_expectation", "failure")]
        assert all(r["context"]["commit_sha"] is None for r in report["cases"])
        assert all(token in xml for token in (
            "SECRET_PARAM_ONE", "SECRET_PARAM_TWO", "SECRET_MESSAGE",
            "SECRET_SETUP", "SECRET_STDOUT", "SECRET_STDERR"))
        assert "SECRET_" not in compact
        assert "Traceback" not in compact
    assert result.returncode == 1
    assert "2 failed, 1 passed, 1 skipped, 1 error" in result.stdout


def test_junit_failure_identity_redacts_failure_details() -> None:
    xml = """<?xml version="1.0"?>
<testsuite name="demo" tests="2" failures="1">
  <testcase classname="tests.test_demo" name="test_ok[param-secret]" />
  <testcase classname="tests.test_demo" name="test_bad[token=secret]">
    <failure message="credential=do-not-publish">traceback do-not-publish</failure>
    <system-out>stdout do-not-publish</system-out>
  </testcase>
</testsuite>
"""
    report = xprobe.cases_from_junit(
        xml,
        repository="myon-bioinformatics/ascii_artist",
        commit_sha=None,
        report_id="fixture",
    )
    assert report["truncated"] is False
    assert len(report["cases"]) == 1
    case = report["cases"][0]
    assert case["context"] == {
        "repository": "myon-bioinformatics/ascii_artist",
        "commit_sha": None,
        "report_id": "fixture",
    }
    assert case["value"] == {
        "test": "test_bad",
        "class": "tests.test_demo",
        "kind": "failure",
    }
    encoded = json.dumps(case, sort_keys=True)
    assert "param-secret" not in encoded
    assert "token=secret" not in encoded
    assert "credential=do-not-publish" not in encoded
    assert "traceback do-not-publish" not in encoded
    assert "stdout do-not-publish" not in encoded


def test_failure_identity_jsonl_is_compact_and_stable() -> None:
    xml = """<testsuite><testcase classname="a" name="b"><error>hidden</error></testcase></testsuite>"""
    cases = xprobe.cases_from_junit(
        xml,
        repository="myon-bioinformatics/ascii_artist",
        commit_sha=None,
        report_id="fixture",
    )["cases"]
    encoded = xprobe.corpus_to_json(cases, jsonl=True)
    assert encoded.count("\n") == 1
    assert json.loads(encoded)["context"]["commit_sha"] is None
    assert "hidden" not in encoded
