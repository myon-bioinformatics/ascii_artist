import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import ascii_artist_repository_diagnostics as diagnostics


def _locked(destination):
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "vendor.lock.json").read_text(encoding="utf-8"))
    return next(e for e in lock["files"] if e["destination"] == destination)

ROOT = Path(__file__).resolve().parents[1]


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


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
        resolver = _locked("vendor/github_public_resolver.py")
        self.assertEqual(git_blob_sha(ROOT / "vendor/github_public_resolver.py"), resolver["blob_sha"])
        ghi = _locked("vendor/gh_identity.py")
        self.assertEqual(git_blob_sha(ROOT / "vendor/gh_identity.py"), ghi["blob_sha"])
        self.assertEqual(hashlib.sha256((ROOT / "vendor/gh_identity.py").read_bytes()).hexdigest(), ghi["sha256"])

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
            source = (ROOT / "docs/brand/favicon.png").read_bytes()
            self.assertTrue(source.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual((out / "favicon.png").read_bytes(), source)
            # Rebuilding replaces an old icon rather than preserving stale assets.
            (out / "favicon.png").write_bytes(b"old icon")
            diagnostics.write_outputs(out, probe=False)
            self.assertEqual((out / "favicon.png").read_bytes(), source)

    def test_page_uses_pinned_renderer(self):
        html = diagnostics.page_html()
        self.assertIn(diagnostics.WEB_UI_SHA, html)
        self.assertIn("RepositoryDiagnostics.render(payload.metadata)", html)
        self.assertNotIn("__REPO__", html)
        self.assertNotIn("__BASE__", html)

    def test_page_escapes_template_constants(self):
        with mock.patch.object(diagnostics, "REPOSITORY", '<repo & "quoted">'), mock.patch.object(
            diagnostics, "WEB_UI_BASE", 'https://example.test/a?x=1&y="2"'
        ):
            html = diagnostics.page_html()
        self.assertIn('&lt;repo &amp; &quot;quoted&quot;&gt;', html)
        self.assertIn('https://example.test/a?x=1&amp;y=&quot;2&quot;', html)
        self.assertNotIn('<repo & "quoted">', html)

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


if __name__ == "__main__":
    unittest.main()
