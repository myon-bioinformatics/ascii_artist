"""🧰 Tooling: CI vendor-lock workflow, repository diagnostics, Pages screenshot capture and script entry points.

Shared fleet checks (locks, pins, setup-uv, vendor staging, Node parity) live in ``tests/test_fleet.py``; this file keeps the
repository's own CI, ``scripts/`` and Pages expectations. Browser dependencies are never imported here.
"""
import importlib.util
import json, os, platform, shlex, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path; from types import SimpleNamespace; from unittest import mock

import pytest

from scripts import ascii_artist_repository_diagnostics as diagnostics
from scripts import capture_pages


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


# ──── ci vendor lock: vendor-lock-only CI (no promote/update or legacy provenance projection) ────

WORKFLOW = ROOT / ".github/workflows/ci.yml"
VENDOR_SYNC_PIN = "26c442bc51b8a2837fe2556782b2937f396932af"
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
        "python -S .vendor-sync-tools/vendor_sync.py recreate --manifest vendor.lock.json",
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


@pytest.mark.parametrize("job", [TEST_JOB, "vendor-locked"])
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
    job = ci["jobs"]["vendor-locked"]
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


# ──── repository diagnostics: scripts/ascii_artist_repository_diagnostics.py ────

def _metadata_v1_record(**overrides):
    record = {
        "schema_version": "1.0",
        "repository": {"full_name": diagnostics.REPOSITORY},
        "head": {
            "sha": "b" * 40,
            "short_sha": "bbbbbbbb",
            "branch": "main",
            "timestamp": "2026-09-27T20:00:00+09:00",
            "subject": "test",
        },
        "measurements": {
            "github_reported_size_bytes": None,
            "working_tree_bytes": 1,
            "release_artifact_bytes": None,
        },
        "tooling": {"python": "3.12"},
        "generated_at": "2026-09-27T21:00:00+09:00",
    }
    head_overrides = overrides.pop("head", None)
    record.update(overrides)
    if head_overrides:
        record["head"] = {**record["head"], **head_overrides}
        record["head"]["short_sha"] = record["head"]["sha"][:8]
    diagnostics.GH_IDENTITY.validate_repository_metadata_v1(record)
    return record


class RepositoryDiagnosticsTests(unittest.TestCase):
    def test_vendor_provenance_matches_bytes(self):
        rows = fleet.check_lock(ROOT)  # every lock row: placed bytes match its blob SHA and SHA-256
        self.assertLessEqual({"vendor/github_public_resolver.py", "vendor/gh_identity.py"}, rows.keys())

    def test_write_outputs_roundtrips_metadata(self):
        record = _metadata_v1_record()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            diagnostics, "build_record", return_value=record
        ):
            out = Path(tmp) / "site"
            payload = diagnostics.write_outputs(out, probe=False)
            self.assertEqual(payload["resolver"]["status"], "not_checked")
            self.assertEqual(json.loads((out / diagnostics.JSONL_NAME).read_text(encoding="utf-8")), record)
            self.assertEqual(json.loads((out / diagnostics.JSON_NAME).read_text(encoding="utf-8"))["metadata"], record)
            html = (out / diagnostics.HTML_NAME).read_text(encoding="utf-8")
            self.assertIn('<link rel="icon" type="image/png" href="./favicon.png">', html)
            # ♻️ ./icon.png and ./favicon.png come from CaChereCyCle when Pages is built; no copy is written here
            self.assertFalse((out / "favicon.png").exists() or (out / "icon.png").exists())

    def test_page_is_the_shared_self_contained_renderer(self):
        html = diagnostics.page_html()
        self.assertIn("<title>myon-bioinformatics/ascii_artist repository diagnostics</title>", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertNotIn('<link rel="stylesheet"', html)
        self.assertIn("/* css/repository-diagnostics.css */", html)
        self.assertIn("global.RepositoryDiagnostics = api", html)
        self.assertIn('RepositoryDiagnostics.mount(document, "./repository-diagnostics.json");', html)

    def test_page_rejects_a_repository_name_that_is_not_owner_slash_name(self):
        with mock.patch.object(diagnostics, "REPOSITORY", '<repo & "quoted">'), self.assertRaises(ValueError):
            diagnostics.page_html()

    def test_generator_uses_gh_identity_without_sys_path_mutation(self):
        ghi = diagnostics.GH_IDENTITY
        path = Path(ghi.__file__)
        self.assertEqual(path.resolve(), (ROOT / "vendor/gh_identity.py").resolve())
        self.assertNotIn(str(ROOT / "vendor"), sys.path)

    def test_checkout_identity_equivalence_refs_and_detached_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "checkout"
            root.mkdir()

            def git(*args, env=None):
                return subprocess.check_output(["git", *args], cwd=root, env=env, text=True).strip()

            git("init", "-q")
            git("config", "user.name", "Metadata test")
            git("config", "user.email", "metadata@example.invalid")
            (root / "README.md").write_text("synthetic checkout\n", encoding="utf-8")
            git("add", "README.md")
            env = dict(
                os.environ,
                GIT_AUTHOR_DATE="2026-09-29T01:02:03+00:00",
                GIT_COMMITTER_DATE="2026-09-29T01:02:03+00:00",
            )
            git("commit", "-qm", "feat: synthetic 日本語", env=env)
            git("branch", "-M", "work")
            head = git("rev-parse", "HEAD")
            now = "2026-09-29T12:34:56Z"
            scenarios = [
                ({}, "work"),
                ({"GITHUB_REF_NAME": "99/merge"}, "99/merge"),
                ({
                    "GITHUB_HEAD_REF": "feature/example",
                    "GITHUB_REF_NAME": "99/merge",
                    "GITHUB_SHA": "d" * 40,
                    "REPOSITORY_DIAGNOSTICS_SHA": "c" * 40,
                }, "feature/example"),
            ]
            for context, branch in scenarios:
                with mock.patch.object(diagnostics, "ROOT", root):
                    record = diagnostics.build_record(context, generated_at=now)
                expected = diagnostics.GH_IDENTITY.repository_metadata_v1(
                    root,
                    repository=diagnostics.REPOSITORY,
                    env=context,
                    generated_at=now,
                    measurements={"working_tree_bytes": len((root / "README.md").read_bytes())},
                    tooling={"python": platform.python_version()},
                )
                expected["head"]["branch"] = branch
                diagnostics.GH_IDENTITY.validate_repository_metadata_v1(expected)
                self.assertEqual(record, expected)
                self.assertEqual(
                    json.loads(
                        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    ),
                    expected,
                )
            git("checkout", "--detach", "-q")
            with mock.patch.object(diagnostics, "ROOT", root):
                detached = diagnostics.build_record({}, generated_at=now)
                with self.assertRaises(ValueError):
                    diagnostics.build_record({}, generated_at="invalid timestamp")
            self.assertEqual(detached["head"]["branch"], "detached")
            self.assertEqual(detached["head"]["sha"], head)

            standalone = Path(tmp) / "standalone"
            standalone.mkdir()
            shutil.copyfile(ROOT / "vendor/gh_identity.py", standalone / "gh_identity.py")
            output = Path(tmp) / "output"
            env = os.environ.copy()
            for name in ("PYTHONPATH", "GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
                env.pop(name, None)
            # The CLI emits UTF-8 JSON, including the Japanese commit subject.
            env["PYTHONIOENCODING"] = "utf-8"
            subprocess.run(
                [sys.executable, "-S", str(standalone / "gh_identity.py"), "repo-metadata", "--format", "v1",
                 "--root", str(root), "--repository", diagnostics.REPOSITORY,
                 "--output-dir", str(output)],
                cwd=tmp, env=env, check=True,
            )
            direct = json.loads((output / "repository-metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(direct["head"], detached["head"])
            self.assertEqual(json.loads((output / "repository-metadata.jsonl").read_text(encoding="utf-8")), direct)
            self.assertIsNone(direct["measurements"]["working_tree_bytes"])

    def test_payload_preserves_resolver_and_unsupported_ref_behavior(self):
        record = _metadata_v1_record(
            head={
                "sha": "b" * 40,
                "short_sha": "bbbbbbbb",
                "branch": "feature/example",
                "timestamp": "2026-09-29T01:02:03Z",
                "subject": "test",
            },
            generated_at="2026-09-29T01:02:03Z",
        )
        evidence = {"status": "not_checked"}
        with mock.patch.object(diagnostics.RESOLVER, "resolve_public_github", return_value=evidence) as resolver:
            payload = diagnostics.build_payload(record, probe=False)
            resolver.assert_called_once_with(diagnostics.REPOSITORY, ref="feature/example", path="README.md", probe=False)
            self.assertIs(payload["metadata"], record)
            self.assertIs(payload["resolver"], evidence)
        with mock.patch.object(diagnostics.RESOLVER, "resolve_public_github", side_effect=ValueError("ref must be a simple Git ref")):
            self.assertEqual(diagnostics.build_payload(record)["resolver"]["reason"], "unsupported_ref")

    def test_tracked_bytes_uses_canonical_inspector_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "space 日本語.txt").write_bytes(b"abc")
            with mock.patch.object(diagnostics, "ROOT", root), mock.patch.object(
                diagnostics.GH_IDENTITY,
                "git_ls_files",
                return_value={"paths": ["space 日本語.txt", "missing.txt"], "truncated": False},
            ):
                self.assertEqual(diagnostics._tracked_bytes(), 3)

    def test_tracked_bytes_rejects_incomplete_inventory(self):
        with mock.patch.object(
            diagnostics.GH_IDENTITY,
            "git_ls_files",
            return_value={"paths": ["partial"], "truncated": True},
        ):
            with self.assertRaisesRegex(RuntimeError, "truncated"):
                diagnostics._tracked_bytes()


# ──── pages capture: screenshot content and offscreen targets (scripts/capture_pages.py, no browser) ────

def test_sample_uses_real_renderer_and_escapes_html(tmp_path):
    text = capture_pages.write_sample(tmp_path)
    assert "Request <&>" in text and "Parse" in text and "Render" in text and "Done" in text
    assert "( o.o )" in text
    html = (tmp_path / "ascii-output.html").read_text(encoding="utf-8")
    assert "Request &lt;&amp;&gt;" in html
    assert "Request <&>" not in html
    assert '<pre class="ui-output">' in html
    assert "/* css/themes/modern.css */" in html and "cdn.jsdelivr.net" not in html
    assert '<link rel="icon" type="image/png" href="./favicon.png">' in html
    assert '<link rel="apple-touch-icon" href="./icon.png">' in html
    assert 'src="./icon.png"' in html
    # ♻️ ./icon.png and ./favicon.png come from CaChereCyCle when Pages is built; no copy is written here
    assert not (tmp_path / "icon.png").exists() and not (tmp_path / "favicon.png").exists()


def test_generic_export_does_not_inherit_pages_branding():
    html = capture_pages.art.to_web_ui_v1_html("Consumer output", title="Consumer page")
    assert 'rel="icon"' not in html
    assert "docs/brand" not in html
    assert "favicon.png" not in html


@pytest.mark.parametrize("box", [None, {"x": 0, "y": 0, "width": 0, "height": 10},
    {"x": -1, "y": 0, "width": 10, "height": 10},
    {"x": 0, "y": 899, "width": 10, "height": 10},
    {"x": 1275, "y": 0, "width": 10, "height": 10}])
def test_visibility_alone_cannot_satisfy_viewport_assertion(box):
    locator = SimpleNamespace(scroll_into_view_if_needed=lambda: None, bounding_box=lambda: box)
    with pytest.raises(AssertionError):
        capture_pages.assert_in_view(locator, SimpleNamespace(viewport_size={"width": 1280, "height": 900}))


def test_complete_box_in_view():
    locator = SimpleNamespace(scroll_into_view_if_needed=lambda: None,
                             bounding_box=lambda: {"x": 0, "y": 0, "width": 1280, "height": 900})
    capture_pages.assert_in_view(locator, SimpleNamespace(viewport_size={"width": 1280, "height": 900}))


def test_card_samples_use_canonical_renderer_and_preserve_boundaries(tmp_path):
    data = capture_pages.write_card_samples(tmp_path)
    assert len(data["sources"][0]["title"]) == 120
    assert data["sources"][0]["note"] == ""
    assert len(data["steps"][0]["note"]) == 240
    for theme in ("github-like", "modern"):
        document = (tmp_path / f"flow-{theme}.html").read_text(encoding="utf-8")
        assert document == capture_pages.art.flow_document(data, theme=theme)
        assert '<script>' not in document and '<link ' not in document
        assert '&lt;script&gt;not executable&lt;/script&gt;' in document
        assert '<style>' in document
    assert len(capture_pages.CARD_CAPTURES) == 4


def test_pages_lane_requires_original_and_card_evidence():
    workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    captures = 'ascii-output.png,repository-diagnostics.png,' + ','.join(capture_pages.CARD_CAPTURES)
    assert '--captures ' + captures in workflow
    assert 'python scripts/capture_pages.py' in workflow
    # Both push and PR path filters must execute the changed browser helper.
    assert workflow.count('- "scripts/capture_pages.py"') == 2


# ──── script entry points: callable argv survives integration with the shared page renderer ────

def test_diagnostics_main_accepts_explicit_argv(tmp_path):
    with mock.patch.object(diagnostics, "write_outputs") as write:
        diagnostics.main([str(tmp_path)])
    write.assert_called_once_with(tmp_path)


def test_capture_main_accepts_explicit_argv_without_removed_web_ui(tmp_path):
    site, results = tmp_path / "site", tmp_path / "results"
    with mock.patch.object(capture_pages, "capture") as capture:
        capture_pages.main(["--site", str(site), "--results", str(results), "--sha", "abc123"])
    capture.assert_called_once_with(site.resolve(), results.resolve(), "abc123")


def test_capture_main_preserves_cli_default_argv(tmp_path):
    with mock.patch("sys.argv", ["capture_pages.py", "--sha", "abc123"]), mock.patch.object(capture_pages, "capture") as capture:
        capture_pages.main()
    capture.assert_called_once_with((capture_pages.ROOT / "_site").resolve(), (capture_pages.ROOT / "test-results/pages").resolve(), "abc123")


if __name__ == "__main__":
    unittest.main()
