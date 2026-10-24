# Python launcher signal fix adopted

Parent PR #171 is merged at `1116d5c4f55d25af4d21cfe9b3c88f49d3a476fa`.
The production `vendor/py_launch.cjs` and its vendor lock now use that exact commit, with no local source changes.

The adjacent candidate patch and standalone checker are historical reproduction artifacts for the old launcher. Do not apply the patch to the updated vendor file.

The production regression tests now run in `tests/test_ascii_artist_node_entry.py`: two acknowledged SIGINT deliveries followed by SIGTERM, text/JSON diagnostics, bounded process-group cleanup, and no-site interpreter discovery. Run:

```sh
python3 -m pytest -q tests/test_ascii_artist_node_entry.py
```
