"""Explicit legacy-provenance projection from the verified shared vendor lock.

No source acquisition, importing candidate modules, tokens or repository writes.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BINDINGS = [['vendor/git_inspector.provenance.json',
  'vendor/git_inspector.py',
  {'blob_sha': 'blob_sha',
   'sha256': 'sha256',
   'source_commit': 'commit',
   'source_path': 'source',
   'source_repository': 'repository'}],
 ['vendor/github_public_resolver.provenance.json',
  'vendor/github_public_resolver.py',
  {'blob_sha': 'blob_sha',
   'sha256': 'sha256',
   'source_commit': 'commit',
   'source_path': 'source',
   'source_repository': 'repository'}],
 ['vendor/python_artifact_provenance.provenance.json',
  'vendor/python_artifact_provenance.py',
  {'blob_sha': 'blob_sha',
   'sha256': 'sha256',
   'source_commit': 'commit',
   'source_path': 'source',
   'source_repository': 'repository'}],
 ['vendor/repository_metadata_contract.provenance.json',
  'vendor/repository_metadata_contract.py',
  {'blob_sha': 'blob_sha',
   'sha256': 'sha256',
   'source_commit': 'commit',
   'source_path': 'source',
   'source_repository': 'repository'}],
 ['vendor/repository_metadata_generator.provenance.json',
  'vendor/repository_metadata_generator.py',
  {'blob_sha': 'blob_sha',
   'sha256': 'sha256',
   'source_commit': 'commit',
   'source_path': 'source',
   'source_repository': 'repository'}]]
EXPECTED = {('myon-bioinformatics/Ironmate', 'LICENSE', 'vendor/Ironmate-LICENSE'),
 ('myon-bioinformatics/Ironmate',
  'python_artifact_provenance.py',
  'vendor/python_artifact_provenance.py'),
 ('myon-bioinformatics/Ironmate',
  'repository_metadata_contract.py',
  'vendor/repository_metadata_contract.py'),
 ('myon-bioinformatics/Ironmate',
  'repository_metadata_generator.py',
  'vendor/repository_metadata_generator.py'),
 ('myon-bioinformatics/mcp-toolcall-lab', 'LICENSE', 'vendor/mcp-toolcall-lab-LICENSE'),
 ('myon-bioinformatics/mcp-toolcall-lab',
  'src/mcp_toolcall_lab/github_public_resolver.py',
  'vendor/github_public_resolver.py'),
 ('myon-bioinformatics/myon-bioinformatics', 'git_inspector.py', 'vendor/git_inspector.py')}


def records(root):
    lock = json.loads((root / "vendor.lock.json").read_text(encoding="utf-8"))
    if lock["schema"] != "vendor-lock/1":
        raise ValueError("unsupported vendor lock")
    files = lock["files"]
    if len(files) != len(EXPECTED) or {(e["repository"], e["source"], e["destination"]) for e in files} != EXPECTED:
        raise ValueError("unexpected source or destination")
    by_destination = {e["destination"]: e for e in files}
    for e in files:
        if e["ref"] != "refs/heads/main" or not re.fullmatch(r"[0-9a-f]{40}", e["commit"]):
            raise ValueError("invalid source identity")
        data = (root / e["destination"]).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob != e["blob_sha"] or hashlib.sha256(data).hexdigest() != e["sha256"]:
            raise ValueError("locked bytes mismatch: " + e["destination"])
    return by_destination


def project(root):
    entries = records(root)  # Verify every source/LICENSE before writing any metadata.
    pending = {}
    for path, destination, fields in BINDINGS:
        record = json.loads((root / path).read_text(encoding="utf-8"))
        entry = entries[destination]
        old_commit = record.get("commit")
        for target, source in fields.items():
            record[target] = "https://github.com/" + entry["repository"] if source == "repository_url" else entry[source]
        if "date" in record and old_commit != record["commit"]:
            record["date"] = datetime.now(timezone.utc).date().isoformat()
        if "license" in record:
            license_entry = next(e for e in entries.values() if e["repository"] == entry["repository"] and e["source"] == "LICENSE")
            record["license"] = {"source_path": "LICENSE", "vendored_path": license_entry["destination"],
                                 "blob_sha": license_entry["blob_sha"], "sha256": license_entry["sha256"]}
        pending[path] = record
    # All per-file formats are mapped above.
    for path, record in pending.items():
        (root / path).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        project(ROOT)
    except (ValueError, KeyError, OSError) as error:
        print("vendor-provenance: " + str(error), file=sys.stderr)
        raise SystemExit(2)
