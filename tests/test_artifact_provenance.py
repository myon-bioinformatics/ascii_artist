import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


def _locked(destination):
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "vendor.lock.json").read_text(encoding="utf-8"))
    return next(e for e in lock["files"] if e["destination"] == destination)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "ascii_artist.py"
VALIDATOR = ROOT / "vendor" / "python_artifact_provenance.py"
PROVENANCE = ROOT / "vendor" / "python_artifact_provenance.provenance.json"
EXPECTED_SOURCE_COMMIT = _locked('vendor/python_artifact_provenance.py')['commit']
EXPECTED_SOURCE_BLOB = _locked('vendor/python_artifact_provenance.py')['blob_sha']
EXPECTED_SOURCE_SHA256 = _locked('vendor/python_artifact_provenance.py')['sha256']
EXPECTED_ARTIFACT_BASE_SHA = "7c21bacfac7b60327b77f9b31a87869ef7838a7e"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "vendored_python_artifact_provenance",
        VALIDATOR,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load vendored provenance validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR_MODULE = _load_validator()


class ArtifactProvenanceTests(unittest.TestCase):
    def test_vendored_validator_matches_recorded_provenance(self):
        record = json.loads(PROVENANCE.read_text(encoding="utf-8"))
        data = VALIDATOR.read_bytes()

        self.assertEqual(record["source_repository"], "myon-bioinformatics/Ironmate")
        self.assertEqual(record["source_path"], "python_artifact_provenance.py")
        self.assertEqual(record["source_commit"], EXPECTED_SOURCE_COMMIT)
        self.assertEqual(record["blob_sha"], EXPECTED_SOURCE_BLOB)
        self.assertEqual(record["sha256"], EXPECTED_SOURCE_SHA256)
        self.assertEqual(hashlib.sha256(data).hexdigest(), EXPECTED_SOURCE_SHA256)

        git_blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
        self.assertEqual(hashlib.sha1(git_blob).hexdigest(), EXPECTED_SOURCE_BLOB)

    def test_ascii_artist_passes_canonical_validator(self):
        metadata = VALIDATOR_MODULE.validate_source_header(
            ARTIFACT.read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["all_count"], 32)
        self.assertEqual(metadata["base_sha"], EXPECTED_ARTIFACT_BASE_SHA)


if __name__ == "__main__":
    unittest.main()
