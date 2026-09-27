import hashlib
import json
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


if __name__ == "__main__":
    unittest.main()
