# Card flows: Python-owned, in-memory output

`ascii_artist.py` now provides the card-flow functionality formerly implemented
in web-ui. This is separate from the existing `Diagram` DAG representation:
`from_dict` does not silently turn a card-flow object into an empty DAG.

```python
from ascii_artist import (validate_flow, flow_html, flow_mermaid,
                          flow_document, flow_css, patch_flow)

spec = {"title": "Build", "sources": [{"title": "Source", "note": "Python"}],
        "steps": [{"title": "Test"}, {"title": "Publish"}]}
normalized = validate_flow(spec)  # detached canonical object
page = flow_document(spec)       # standalone HTML, embedded CSS by default
fragment = flow_html(spec)       # figure only; no styles or scripts
markdown = flow_mermaid(spec)    # fenced Mermaid with source fan-in
changed = patch_flow(spec, [{"path": "/steps/0/note", "value": "Passed"}])
```

All strings are built in memory by Python. No asset reads, browser runtime,
third-party package, Rust runtime, native Node implementation, or JavaScript is
needed. The shared `vendor/py_launch.cjs` forwards CLI arguments to Python; there is
no second implementation. Existing ASCII/DAG APIs remain separate.

## CLI and optional disk output

```sh
python -S ascii_artist.py flow-cards < examples/pr-flow.json > flow.html
python -S ascii_artist.py flow-cards --format fragment < examples/pr-flow.json
python -S ascii_artist.py flow-cards --format mermaid < examples/pr-flow.json
printf '%s' '{"spec":{"title":"Build","sources":[{"title":"Code"}],"steps":[{"title":"Test"}]},"patch":[{"path":"/title","value":"CI"}]}' | python -S ascii_artist.py flow-patch --pretty
node vendor/py_launch.cjs --env-var ASCII_ARTIST_PYTHON -- ascii_artist.py flow-cards --format mermaid < examples/pr-flow.json
```

The Node entry requires Node 26+ and Python; `ASCII_ARTIST_PYTHON` optionally
selects the interpreter. Rendering accepts at most 256 KiB of UTF-8 JSON;
patching accepts a combined `{spec,patch}` envelope of at most 320 KiB, matching
the original limits. Invalid UTF-8, BOM-prefixed JSON and invalid documents fail
with exit 2 and no stdout. CLI output is newline-terminated.

`flow_document(spec, *, theme="github-like", asset_base=".", embed_css=True)`
supports `github-like` and `modern`. For external CSS, explicitly use
`embed_css=False` (CLI `--no-embed-css`) and write `flow_css(theme=...)` to
`asset_base/flow.css`. Asset bases are local paths, not URLs. The generated CSS
is standalone; **do not** point at removed web-ui stylesheets. Card geometry,
responsive stacking and print behavior are retained; the original light/dark palette
and base sizing are retained without copying unrelated web-ui components.

## Validation and editing contract

- Flow objects accept only `title`, optional `sources_label` (default `Sources`),
  `sources`, and `steps`. Both lists contain 1–8 cards.
- Cards accept only `title` and optional `note` (default empty). Required titles
  and source labels are nonblank and at most 120 Unicode code points; notes
  are at most 240. C0 controls, DEL and surrogate code points are rejected.
- HTML escapes user text and attributes. Mermaid uses entity-escaped labels;
  IDs and connections are generated, never supplied by untrusted labels.
- Patches have at most 64 operations, each exactly `{path,value}`. Supported
  paths are `/title`, `/sources_label`, and `/{sources|steps}/{index}/{title|note}`.
  Indices must be canonical nonnegative ASCII decimals and already exist.
- Every operation is applied to a detached normalized copy, with final
  validation before returning. Failure at any point leaves the input intact.
  Empty patches normalize without mutating. This is field replacement, not
  general JSON Patch, graph editing, or image decoding.

## Migration provenance and tests

Validation, card markup, Mermaid conversion, atomic field editing, fixture and
regression cases are adapted from **myon-bioinformatics/web-ui**, commit
`2fafdde9a5f131789318a42b5a6c509af88b9cae`: `tool/flow_diagram.py`,
`tool/flow_patch.py`, `css/flow.css`, `examples/pr-flow.json`,
`tests/test_flow_diagram.py`, `tests/test_flow_patch.py`, `tests/flow.node.cjs`,
and `tests/flow-patch.node.cjs`. These sources are MIT licensed,
Copyright (c) 2026 myon; the identical notice and permission terms are retained
in this repository's `LICENSE`.

The original Python cases are retained under their test filenames with import
and CLI routes updated. The old native Node assertions are exercised through
the canonical Python API and existing thin Node CLI, including all fan-in
edges, unknown properties, Unicode limits, atomic failures, malformed UTF-8,
and byte budgets. `tests/test_flow_contract.py` additionally checks exact
budget boundaries, 64/65-operation limits, standalone isolated single-file
execution, both palettes, and HTML/fragment/Mermaid adapter parity.

```sh
# Node 26+ must be on PATH for adapter cases.
python -S -m unittest discover -s tests -p 'test_flow*.py' -v
```

This does not claim a cross-repository migration is already accepted. Consumers
must pin an accepted ascii_artist source before removing their implementation.

### Hosted browser coverage

The existing Pages Chromium lane preserves its ASCII-output and diagnostics
checks and additionally runs `capture_card_flows`: light/dark standalone pages
at 320px and 1280px, long Unicode titles/notes, empty notes, escaped hostile
text, card counts, computed colors/grid, horizontal overflow, responsive source
stacking, and separately composed fragment/CSS. Four new full-page screenshots
join the original two and are required by the existing evidence validator.
This is actual browser coverage, not a substitution with DOM-string tests.
It runs on matching pull requests and main pushes through the existing Pages
workflow. Local browserless tests verify fixtures/wiring; hosted browser results
must still pass for the published candidate before integration is declared ready.
