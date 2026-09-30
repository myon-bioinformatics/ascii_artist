"""Contract tests for the pinned shared xprobe JUnit importer."""

from __future__ import annotations

import json

import xprobe


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
