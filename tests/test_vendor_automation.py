"""Vendor-lock-only CI regression (no promote/update or legacy provenance projection)."""
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
VENDOR_SYNC_PIN = "f907560c2b9b3f7a0f78f4434f547f91cb2ef954"
TEST_JOB = "test"


def _workflow():
    import yaml

    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_ci_excludes_auto_vendor_updates_and_legacy_provenance():
    text = WORKFLOW.read_text(encoding="utf-8")
    forbidden = (
        "vendor_sync.py promote",
        "vendor_sync.py update",
        "sync_vendor_provenance",
        "provenance.json",
        "vendor-promotion.json",
        "vendor-mode",
    )
    for token in forbidden:
        assert token not in text
    ci = _workflow()
    assert {"push", "pull_request"} <= set(ci["on"])
    assert "schedule" not in ci["on"]
    jobs = ci["jobs"]
    resolve = jobs["resolve-vendor"]["steps"]
    test = jobs[TEST_JOB]["steps"]
    assert jobs["resolve-vendor"]["permissions"] == jobs[TEST_JOB]["permissions"] == {"contents": "read"}
    recreate = next(s for s in resolve if s.get("name") == "Recreate locked vendor files from GitHub")
    assert recreate["shell"] == "bash"
    assert recreate["run"].splitlines() == [
        "python -S - <<'PY'",
        "import json",
        "from pathlib import Path",
        "for entry in json.loads(Path('vendor.lock.json').read_text(encoding='utf-8'))['files']:",
        "    Path(entry['destination']).unlink()",
        "PY",
        "python -S .vendor-sync-tools/vendor_sync.py materialize --manifest vendor.lock.json",
        "python -S .vendor-sync-tools/vendor_sync.py check --manifest vendor.lock.json",
    ]
    needs = jobs[TEST_JOB]["needs"]
    assert "resolve-vendor" in ([needs] if isinstance(needs, str) else needs)
    download = next(i for i, s in enumerate(test) if s.get("name") == "Download resolved vendor snapshot")
    verify = next(i for i, s in enumerate(test) if s.get("name") == "Verify resolved vendor snapshot")
    tests = [i for i, s in enumerate(test) if "pytest " in s.get("run", "")]
    assert tests and download < verify < min(tests)
    assert test[download]["with"]["name"] == "vendor-snapshot"
    assert test[verify]["run"].splitlines() == [
        "python -S .vendor-sync-tools/vendor_sync.py check --manifest vendor.lock.json"
    ]
    pins = [
        s["with"]["ref"]
        for steps in (resolve, test)
        for s in steps
        if s.get("with", {}).get("repository") == "myon-bioinformatics/myon-bioinformatics"
    ]
    assert pins == [VENDOR_SYNC_PIN] * 2
    for steps in (resolve, test):
        for step in steps:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] == "false"
            assert not any(
                x in step.get("run", "") for x in ("|| true", "|| :", "set +e", "git push", "git commit", "gh pr")
            )
            assert "continue-on-error" not in step
    assert not any(x in text for x in ("secrets.", "VENDOR_UPDATE_TOKEN", "VENDOR_UPDATES_ENABLED", "GH_TOKEN"))


@pytest.mark.parametrize("job", [TEST_JOB, "test-locked"])
def test_enrolled_ghi_loads_with_stdlib_after_verification(job):
    steps = _workflow()["jobs"][job]["steps"]
    load = next(
        i for i, step in enumerate(steps) if step.get("name") == "Verify enrolled GHI is stdlib-loadable"
    )
    checked = [i for i, step in enumerate(steps) if "vendor_sync.py check" in step.get("run", "")]
    tests = [i for i, step in enumerate(steps) if "pytest " in step.get("run", "")]
    assert checked and tests and max(checked) < load < min(tests)
    command = steps[load]["run"]
    assert command.startswith("python -S ")
    assert "'vendor/gh_identity.py'" in command
    result = subprocess.run(
        shlex.split(command.replace("python -S ", shlex.quote(sys.executable) + " -S ", 1)),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_locked_baseline_runs_without_candidate_snapshot():
    ci = _workflow()
    job = ci["jobs"]["test-locked"]
    assert job["permissions"] == {"contents": "read"}
    assert "continue-on-error" not in job
    assert job.get("needs") == ci["jobs"]["resolve-vendor"].get("needs")
    assert job.get("if") == ci["jobs"]["resolve-vendor"].get("if")
    matrix = job.get("strategy", {}).get("matrix", {})
    assert all(len(values) == 1 for values in matrix.values())
    steps = job["steps"]
    assert not any(
        command in s.get("run", "")
        for s in steps
        for command in ("vendor_sync.py update", "vendor_sync.py promote", "sync_vendor_provenance")
    )
    assert not any(s.get("uses", "").startswith("actions/download-artifact@") for s in steps)
    verify = next(i for i, s in enumerate(steps) if s.get("name") == "Verify checked-in vendor copies")
    recreate = next(i for i, s in enumerate(steps) if s.get("name") == "Recreate locked vendor files from GitHub")
    tests = [i for i, s in enumerate(steps) if "pytest " in s.get("run", "")]
    assert tests and verify < recreate < min(tests)
    original = next(
        s for s in ci["jobs"]["resolve-vendor"]["steps"] if s.get("name") == "Recreate locked vendor files from GitHub"
    )
    assert steps[recreate] == original
    tool = next(s for s in steps if s.get("name") == "Fetch pinned shared vendor tool")
    assert tool["with"]["ref"] == VENDOR_SYNC_PIN
    for step in steps:
        assert "continue-on-error" not in step
        if step.get("uses", "").startswith("actions/checkout@"):
            assert step["with"]["persist-credentials"] == "false"
        if step.get("uses", "").startswith("actions/upload-artifact@"):
            assert step["with"]["name"].startswith("locked-")
            if step["with"]["name"].startswith(("locked-vendor-", "locked-junit-", "locked-controlled-")):
                assert step["if"] == "always()"
            assert step["with"]["if-no-files-found"] == "error"
    lock = next(s for s in steps if s.get("name") == "Preserve vendor lock used by this run")
    assert lock["with"]["path"] == "build/vendor-evidence-locked"
