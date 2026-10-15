# Public vendor placement in CI

Ordinary push/PR CI restores locked files from explicit commit pins in
`vendor.lock.json`, verifies bytes with the shared `vendor_sync.py` tool, and
runs the existing Python test matrix against the verified snapshot. Existing
documentation-only change detection is retained.

`vendor.lock.json` is the only provenance record for vendored files (schema
`vendor-lock/1`). Each entry pins `repository`, full 40-hex `ref` and `commit`,
`source`, `destination`, Git `blob_sha`, and `sha256`. No per-file
`*.provenance.json` sidecars or local projection scripts are used.

The pinned shared stdlib tool is checked out from
`myon-bioinformatics/myon-bioinformatics` at commit
`b000e5967cb7596f6f9f20fe396a686fdc700c16`. CI runs
`vendor_sync.py check --manifest vendor.lock.json` and, in `resolve-vendor`,
removes allowlisted destinations and `materialize`s them again before staging
evidence. Checkout credentials are not persisted; source acquisition uses
anonymous public Git.

Lock-derived evidence is staged with `vendor_stage.py` from the same parent
checkout (`--kind locked`). Artifacts retain `vendor-evidence.json` and copied
lock members; staging runs with `if: always()` and fails closed on missing or
modified bytes.

## Enrolled GHI

`vendor/gh_identity.py` and `vendor/gh_identity-LICENSE` are locked to reviewed
GHI commit `c6b52a29d8cd1dce0ebe0c4288cd16b0e4b84b96`. Their exact source and
LICENSE bytes remain protected by `.gitattributes` `-text` entries. GHI is
enrolled in the allowlist without becoming an `ascii_artist.py` runtime
dependency.

Both the primary Python matrix and the independent `test-locked` job load the
verified `vendor/gh_identity.py` with `python -S` before running tests.

ALM agents can reproduce verification in a disposable checkout:

```bash
set -euo pipefail
git clone https://github.com/myon-bioinformatics/myon-bioinformatics.git .vendor-sync-tools
git -C .vendor-sync-tools checkout --detach b000e5967cb7596f6f9f20fe396a686fdc700c16
python -S .vendor-sync-tools/vendor_sync.py check --manifest vendor.lock.json
python -S .vendor-sync-tools/vendor_sync.py materialize --manifest vendor.lock.json
python -S .vendor-sync-tools/vendor_sync.py check --manifest vendor.lock.json
```

Run the existing Python suite with its test-only dependencies after verification.

## What a green run covers

The primary Python job tests the materialized snapshot from `resolve-vendor`. The
separate `test-locked` job tests the checked-in baseline on Python 3.12: verify,
materialize, verify again, then run the suite. Locked evidence uses a
`locked-` artifact prefix.

Pages/Docker continue shipping checked-in bytes; no source is written back to
main.
