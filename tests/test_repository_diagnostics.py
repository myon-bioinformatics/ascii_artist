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

from scripts import repository_diagnostics as diagnostics

ROOT = Path(__file__).resolve().parents[1]


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class RepositoryDiagnosticsTests(unittest.TestCase):
    def test_vendor_provenance_matches_bytes(self):
        contract = json.loads((ROOT / "vendor/repository_metadata_contract.provenance.json").read_text())
        resolver = json.loads((ROOT / "vendor/github_public_resolver.provenance.json").read_text())
        self.assertEqual(git_blob_sha(ROOT / "vendor/repository_metadata_contract.py"), contract["blob_sha"])
        self.assertEqual(git_blob_sha(ROOT / "vendor/github_public_resolver.py"), resolver["blob_sha"])

    def test_write_outputs_roundtrips_metadata(self):
        record = diagnostics.CONTRACT.build_repository_record(
            full_name="myon-bioinformatics/ascii_artist",
            sha="b" * 40,
            branch="main",
            timestamp="2026-09-27T20:00:00+09:00",
            subject="test",
            generated_at="2026-09-27T21:00:00+09:00",
            working_tree_bytes=1,
            tooling={"python": "3.12"},
        )
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            diagnostics, "build_record", return_value=record
        ):
            out = Path(tmp)
            payload = diagnostics.write_outputs(out, probe=False)
            self.assertEqual(payload["resolver"]["status"], "not_checked")
            self.assertEqual(json.loads((out / diagnostics.JSONL_NAME).read_text()), record)
            self.assertEqual(json.loads((out / diagnostics.JSON_NAME).read_text())["metadata"], record)
            self.assertTrue((out / diagnostics.HTML_NAME).is_file())

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

    def test_generator_uses_pinned_contract_without_sys_path_mutation(self):
        path = Path(diagnostics.GENERATOR.build_repository_record.__globals__["__file__"])
        self.assertEqual(path.resolve(), (ROOT / "vendor/repository_metadata_contract.py").resolve())
        self.assertNotIn(str(ROOT / "vendor"), sys.path)

    def test_producer_pair_matches_finalized_source(self):
        expected = {
            "repository_metadata_contract": (
                "a61a2949e58a42635b0830289e368b4125b1274b",
                "c8093d806756925b68978b5a40a218e4acd5daf43f2d7fc2e358cabf8dc39e9a",
            ),
            "repository_metadata_generator": (
                "eef572ce64e92bfecf0451235f884aa208044587",
                "a2edc91cc0a269d8b2fc6a9be1cfa0edbfae18604d53a1b9ebdcb72004be9a06",
            ),
        }
        for name, (blob, digest) in expected.items():
            path = ROOT / "vendor" / (name + ".py")
            provenance = json.loads(path.with_suffix(".provenance.json").read_text())
            self.assertEqual(provenance["source_repository"], "myon-bioinformatics/Ironmate")
            self.assertEqual(provenance["source_path"], name + ".py")
            self.assertEqual(provenance["source_commit"], "0aee64da2f8d0119a3ef9b955e5c3818f28aaf92")
            self.assertEqual(provenance["schema_version"], "1.0")
            self.assertEqual(provenance["blob_sha"], blob)
            self.assertEqual(git_blob_sha(path), blob)
            self.assertEqual(provenance["sha256"], digest)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

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
                expected = diagnostics.CONTRACT.build_repository_record(
                    full_name=diagnostics.REPOSITORY,
                    sha=head,
                    branch=branch,
                    timestamp=git("show", "-s", "--format=%cI", "HEAD"),
                    subject="feat: synthetic 日本語",
                    generated_at=now,
                    working_tree_bytes=len((root / "README.md").read_bytes()),
                    tooling={"python": platform.python_version()},
                )
                self.assertEqual(record, expected)
                self.assertEqual(json.loads(diagnostics.CONTRACT.to_jsonl(record)), expected)
            git("checkout", "--detach", "-q")
            with mock.patch.object(diagnostics, "ROOT", root):
                detached = diagnostics.build_record({}, generated_at=now)
                with self.assertRaises(ValueError):
                    diagnostics.build_record({}, generated_at="invalid timestamp")
            self.assertEqual(detached["head"]["branch"], "detached")
            self.assertEqual(detached["head"]["sha"], head)

            standalone = Path(tmp) / "standalone"
            standalone.mkdir()
            for name in ("repository_metadata_contract.py", "repository_metadata_generator.py"):
                shutil.copyfile(ROOT / "vendor" / name, standalone / name)
            output = Path(tmp) / "output"
            env = os.environ.copy()
            for name in ("PYTHONPATH", "GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
                env.pop(name, None)
            subprocess.run(
                [sys.executable, "-S", str(standalone / "repository_metadata_generator.py"),
                 "--root", str(root), "--repository", diagnostics.REPOSITORY,
                 "--output-dir", str(output)],
                cwd=tmp, env=env, check=True,
            )
            direct = json.loads((output / "repository-metadata.json").read_text())
            self.assertEqual(direct["head"], detached["head"])
            self.assertEqual(json.loads((output / "repository-metadata.jsonl").read_text()), direct)
            self.assertIsNone(direct["measurements"]["working_tree_bytes"])

    def test_payload_preserves_resolver_and_unsupported_ref_behavior(self):
        record = diagnostics.CONTRACT.build_repository_record(
            full_name=diagnostics.REPOSITORY, sha="b" * 40, branch="feature/example",
            timestamp="2026-09-29T01:02:03Z", subject="test", generated_at="2026-09-29T01:02:03Z",
        )
        evidence = {"status": "not_checked"}
        with mock.patch.object(diagnostics.RESOLVER, "resolve_public_github", return_value=evidence) as resolver:
            payload = diagnostics.build_payload(record, probe=False)
            resolver.assert_called_once_with(diagnostics.REPOSITORY, ref="feature/example", path="README.md", probe=False)
            self.assertIs(payload["metadata"], record)
            self.assertIs(payload["resolver"], evidence)
        with mock.patch.object(diagnostics.RESOLVER, "resolve_public_github", side_effect=ValueError("ref must be a simple Git ref")):
            self.assertEqual(diagnostics.build_payload(record)["resolver"]["reason"], "unsupported_ref")


if __name__ == "__main__":
    unittest.main()
