"""Fleet contracts through the parent's shared checks (vendor/fleet_check.py): locks, pins, CI setup, benchmark, Node entry."""
import importlib.util
import sys
from pathlib import Path
import unittest
import hashlib, json, os, re, shutil, tomllib

import pytest


def load_vendored(name, relpath):
    """Load a vendored file by path under a repo-unique name (cli_args README: Loading a vendored copy)."""
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / relpath)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


fleet = load_vendored("ascii_artist_fleet_check", "vendor/fleet_check.py")


ROOT = fleet.repo_root(__file__)
PARENT_WORKFLOW_PIN = "main"  # 🔁 own sources follow main (2026-11-28)
# Node sources and the shared checks stay on accepted upstream commits with exact bytes.
ACCEPTED = {
    "vendor/py_launch.cjs",
    "vendor/fleet_check.py",
}  # 🔁 locked destinations; they follow main
SETUP_UV = "astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2"
JOBS = {
    ("ci.yml", "resolve-vendor"): "3.15",
    ("ci.yml", "test"): "${{ matrix.python-version }}",
    ("ci.yml", "vendor-locked"): "${{ matrix.python-version }}",
    ("pages.yml", "checks"): "3.15",
    ("pages.yml", "build"): "3.15",
    ("runtime-compatibility.yml", "runtime"): "${{ matrix.python }}",
    ("runtime-compatibility.yml", "portability"): "3.11",
}
EXPECTED_REPORTS = [f"junit-py3.{v}/pytest-3.{v}.xml" for v in (11, 12, 13, 14)]
TOOL, ENV_VAR = "ascii_artist.py", "ASCII_ARTIST_PYTHON"
CASES = {
    **{f"tree-invalid-{i}-{charset}": (["tree", "Root", "valid", item, "--charset", charset], "", 2)
       for i, item in enumerate(["", "a\nb", "a\rb", "a\r\nb"]) for charset in ["unicode", "ascii"]},
    "help": (["--help"], "", 0),
    "square": (["square", "3", "--char", "ü"], "", 0),
    "box-stdin": (["box", "--style", "rounded"], "こんにちは\nhi\n", 0),
    "convert-render": (["convert", "--from", "outline", "--to", "render"], "# A\n## B\n", 0),
    "no-command": ([], "", 2),
    "bogus": (["--bogus"], "", 2),
    "bad-input": (["convert", "--from", "json", "--to", "dot"], "{", 2),
    "missing-file": (["box", "no-such-file.txt"], "", 1),
}
# Both primary CI jobs provision Node 26; runtime-compatibility jobs deliberately lack it and skip.
needs_node = pytest.mark.skipif(fleet.node(ci_jobs=("test", "vendor-locked")) is None, reason="Node 26+ not available")


_PARENT_BINDINGS = {
    "vendor/py_launch.cjs": (fleet.PARENT, "py_launch.cjs"),
    "vendor/fleet_check.py": (fleet.PARENT, "fleet_check.py"),
    "vendor/myon-bioinformatics-LICENSE": (fleet.PARENT, "LICENSE"),
}


def _check_vendor_bindings(root):
    # The shared check validates every placed row. Its sources= argument instead
    # freezes membership for each named upstream, which is not this contract.
    entries = json.loads((root / "vendor.lock.json").read_text(encoding="utf-8"))["files"]
    folded = {row["destination"].casefold() for row in entries}
    assert len(folded) == len(entries), "duplicate vendor destination (case-insensitive)"
    rows = fleet.check_lock(root)
    for where, origin in _PARENT_BINDINGS.items():
        assert where in rows, f"missing vendor binding: {where}"
        assert (rows[where]["repository"], rows[where]["source"]) == origin, where


def test_vendor_lock_matches_checked_in_bytes_and_accepted_commits():
    _check_vendor_bindings(ROOT)


@pytest.mark.parametrize("variant", ["extra", "missing-license", "wrong-source", "duplicate", "case-collision", "wrong-bytes"])
def test_vendor_binding_scope(tmp_path, variant):
    shutil.copytree(ROOT / "vendor", tmp_path / "vendor")
    lock = tmp_path / "vendor.lock.json"
    data = json.loads((ROOT / "vendor.lock.json").read_text(encoding="utf-8"))
    files = data["files"]
    license_row = next(row for row in files if row["destination"] == "vendor/myon-bioinformatics-LICENSE")
    if variant == "extra":
        destination = "vendor/independent-helper.txt"
        content = b"additional independently locked file"
        (tmp_path / destination).write_bytes(content)
        files.append({**license_row, "source": "docs/independent-helper.txt", "destination": destination,
                      "blob_sha": hashlib.sha1(b"blob %d\0" % len(content) + content).hexdigest(),
                      "sha256": hashlib.sha256(content).hexdigest()})
    elif variant == "missing-license":
        files.remove(license_row)
    elif variant == "wrong-source":
        license_row["source"] = "NOTICE"
    elif variant == "duplicate":
        files.append(dict(license_row))
    elif variant == "case-collision":
        files.append({**license_row, "destination": license_row["destination"].upper()})
    elif variant == "wrong-bytes":
        (tmp_path / license_row["destination"]).write_bytes(b"changed license")
    lock.write_text(json.dumps(data), encoding="utf-8")
    if variant == "extra":
        _check_vendor_bindings(tmp_path)
    elif variant in ("duplicate", "case-collision"):
        with pytest.raises(AssertionError, match="duplicate vendor destination"):
            _check_vendor_bindings(tmp_path)
    else:
        with pytest.raises(AssertionError):
            _check_vendor_bindings(tmp_path)


def test_every_action_is_pinned_by_full_sha_with_a_version_comment():
    assert fleet.check_actions(ROOT)


def test_parent_workflow_references_use_reviewed_rollout_commit():
    assert set(fleet.parent_refs(ROOT, skip=(".vendor-sync-tools",))) == {PARENT_WORKFLOW_PIN}


def test_project_and_lock_declare_python311_without_runtime_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    # pyproject and uv.lock agree on the floor, and the runtime matrix starts there (shared check).
    assert fleet.python_floor(ROOT) == ("3.11", ["3.11", "3.12", "3.13", "3.14"])
    assert project["project"]["dependencies"] == []
    assert project["tool"]["uv"].get("package") is not False
    assert project["tool"]["uv"]["dependency-groups"]["dev"]["requires-python"] == ">=3.11"


def test_supported_runtime_versions_keep_existing_os_coverage():
    block = fleet.workflow_job(ROOT, "runtime", "runtime-compatibility.yml")
    matrix = re.search(r"(?ms)^      matrix:\n(.*?)(?=^    steps:)", block)
    assert matrix is not None
    assert matrix.group(1) == '''        os: [ubuntu-latest]
        python: ["3.11", "3.12", "3.13", "3.14"]
        include: ${{ github.event_name == 'pull_request' && fromJSON('[]') || fromJSON('[{"os":"windows-latest","python":"3.11"},{"os":"windows-latest","python":"3.14"},{"os":"macos-latest","python":"3.11"},{"os":"macos-latest","python":"3.14"}]') }}
        exclude: ${{ github.event_name == 'pull_request' && fromJSON('[{"os":"ubuntu-latest","python":"3.11"},{"os":"ubuntu-latest","python":"3.12"},{"os":"ubuntu-latest","python":"3.13"}]') || fromJSON('[]') }}
'''
    assert "runs-on: ${{ matrix.os }}" in block
    assert "fail-fast: false" in block
    assert "python -S -m unittest discover -s tests -p test_ascii_artist.py -v" in block


@pytest.mark.parametrize("workflow,name", JOBS, ids=["/".join(key) for key in JOBS])
def test_selected_python_is_ready_before_any_python_or_uv_command(workflow, name):
    fleet.workflow_job(ROOT, name, workflow, setup=SETUP_UV, inputs=(
        'version: "latest"', f'python-version: "{JOBS[workflow, name]}"', "activate-environment: true", "enable-cache: true",
        "save-cache: ${{ github.event_name == 'push' && github.ref == 'refs/heads/main' }}",  # only main writes
        "prune-cache: true"))


@pytest.mark.skipif(not (ROOT / ".vendor-sync-tools/vendor_stage.py").is_file(), reason="requires the workflow full-SHA parent checkout")
def test_vendor_staging_commands_stage_locked_bytes_and_fail_closed():
    commands = fleet.vendor_staging(ROOT)
    assert all("--kind locked" in command and "--legacy-evidence" not in command for command in commands)


def test_compatibility_matrix_and_required_report_identities_are_preserved():
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'python-version: ["3.11", "3.12", "3.13", "3.14"]' in text
    match = re.search(r"expected-reports: '([^']+)'", fleet.workflow_job(ROOT, "failure-identity"))
    assert match is not None
    assert json.loads(match.group(1)) == EXPECTED_REPORTS


def test_locked_baseline_and_pages_venv_sync_are_preserved():
    locked = fleet.workflow_job(ROOT, "vendor-locked")
    assert re.search(r"python-version:\s*\n\s*- '3\.12'", locked)
    assert "name: locked-junit-py${{ matrix.python-version }}" in locked
    for name in ("checks", "build"):
        block = fleet.workflow_job(ROOT, name, "pages.yml")
        sync = "uv sync --locked --group dev --python \"$(python -c 'import sys; print(sys.executable)')\""
        if name == "build":
            sync = sync.replace("--group dev", "--group dev --group browser")
        assert "uv pip install" not in block
        path_export = "python -c \"import os; from pathlib import Path; print(Path('.venv').resolve() / ('Scripts' if os.name == 'nt' else 'bin'))\" >> \"$GITHUB_PATH\""
        assert sync in block and path_export in block
        assert block.index(sync) < block.index(path_export)
        assert "python -m pip" not in block
    assert ".venv/bin/python -m playwright install" in fleet.workflow_job(ROOT, "build", "pages.yml")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["dependency-groups"]["browser"] == ["playwright>=1.64.0"]
    assert "if: github.ref == 'refs/heads/main'" in fleet.workflow_job(ROOT, "deploy", "pages.yml")


def test_incorrect_layers_fail_without_success_json_under_optimization():
    patch = """
import ascii_artist
reference = types.ModuleType('guard_reference')
reference.diagram = ascii_artist.diagram
reference._topological_layers = ascii_artist._topological_layers
sys.modules['guard_reference'] = reference
g['subprocess'].check_output = lambda *a, **kw: b'from guard_reference import diagram, _topological_layers'
ascii_artist._topological_layers = lambda diagram: []
"""
    result = fleet.run_main(ROOT, "scripts/benchmark_dag_frontier.py", patch, optimized=True, timeout=30)
    assert result.returncode != 0, result.stdout
    assert "parity mismatch" in result.stderr
    assert result.stdout == ""


def test_ci_executes_node_parity_instead_of_skipping():
    for job, step in (("test", "Require supported Node in parity CI"), ("vendor-locked", "Require supported Node in locked parity CI")):
        # The guard is run in bash; on Windows a bare "bash" is the WSL launcher, so that lane checks the step only.
        assert step in fleet.workflow_job(ROOT, job, node_floor=None if os.name == "nt" else 26)


def test_no_per_tool_wrapper_and_readme_documents_the_direct_command():
    assert not (ROOT / "ascii_artist.cjs").exists()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"node vendor/py_launch.cjs --env-var {ENV_VAR} -- {TOOL}" in readme
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert pkg["engines"]["node"] == ">=26"


@needs_node
@pytest.mark.parametrize("args,stdin,expected_rc", CASES.values(), ids=CASES)
def test_node_python_parity(args, stdin, expected_rc):
    via_node, via_python = fleet.node_parity(ROOT, TOOL, ENV_VAR, *args, input=stdin)
    assert via_python[0] == expected_rc
    assert via_node == via_python


@needs_node
def test_vendored_launcher_keeps_its_contract():
    fleet.launcher_contract(ROOT, ENV_VAR)


# 🧰 Scripts: 📝 each one describes itself and ⌨️ one that reads sys.argv declares its arguments (argparse /
# cli_args). Read with ast, never run; the portfolio's script catalog reads the same facts.

class ScriptsDescribeThemselves(unittest.TestCase):
    def test_every_script_has_a_description_and_declared_arguments(self):
        fleet.check_scripts(fleet.repo_root(__file__))

    def test_no_top_level_vendor_package_imports(self):
        # 📦 vendored modules load by path under a repo-unique name (cli_args README: Loading a vendored copy)
        self.assertEqual(fleet.check_no_vendor_package_imports(ROOT), [])

    def test_pull_request_ci_stays_quick(self):
        # ⏱ push limited to branches, superseded PR runs cancelled, every job timed (fleet_check.check_ci)
        fleet.check_ci(fleet.repo_root(__file__))

    def test_root_scripts_import_only_the_standard_library(self):
        root = fleet.repo_root(__file__)
        for path in sorted(root.glob("*.py")):
            if path.name != "conftest.py":
                fleet.check_imports(root, path.name)
