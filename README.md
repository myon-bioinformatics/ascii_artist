# ascii_artist

**Python compatibility:** CI-tested on Python 3.10–3.14.

Documentation-only changes use the shared change detector and skip the multi-version Python test matrix; code and workflow changes still run the full matrix.
Python utilities for ASCII art generation, conversion, layout, and text-based graphics, designed for lightweight and reusable workflows.

## Purpose

`ascii_artist` is the standalone home for ASCII-art helpers originally embedded in Ironmate. The repository is intended to evolve independently while remaining easy to vendor into applications that want a pinned, inspectable copy.

## Current API

- `generate_square()`
- `generate_triangle()`
- `generate_diamond()`
- `get_template()`
- `list_templates()`
- `render_prompt_ascii()`
- `diagram()` / `Node` / `Edge` / `Diagram`
- `to_dict()` / `from_dict()`
- `render_diagram()`
- `flow()` / `branch()` / `tree()`
- `to_json()` / `from_json()`
- `to_edges()` / `from_edges()`
- `to_adjacency()` / `from_adjacency()`
- `to_mermaid()` / `from_mermaid()`
- `to_dot()` / `from_dot()`
- `to_markdown_outline()` / `from_markdown_outline()`
- `inventory()`

## Design

The product is a single file: `ascii_artist.py`.

- standard library only
- no runtime dependency on package-specific support modules
- usable by copying one file into another project
- suitable for vendoring as `vendor/ascii_artist.py`


## Diagram IR and transform pipeline

Text diagrams use a small immutable intermediate representation instead of
drawing directly from every public helper:

\`\`\`text
public input
   |
   v
normalize / validate
   |
   v
Diagram IR
   |
   +--> topology-specific layout
   |
   +--> generic exact edge rendering
   |
   +--> to_dict() / from_dict()
\`\`\`

\`Node\`, \`Edge\`, and \`Diagram\` are intentionally small. Public convenience
helpers such as \`flow()\` and \`branch()\` build on the same graph contract,
while internal helpers keep DAG validation, topology/layout decisions, and
rendering separate.

The first round-trip contract is lossless:

\`\`\`python
d = diagram(["LLM", "MCP", "Python"], [("LLM", "MCP"), ("MCP", "Python")])
assert from_dict(to_dict(d)) == d
\`\`\`

`tree()` uses iterative traversal rather than Python recursion, so deeply nested mapping input is not limited by the interpreter recursion depth.

Text rendering is not claimed to be reversible. Rendering may normalize spacing
and, for generic DAGs, prioritizes exact edge representation over sophisticated
graph routing.

### Examples

\`\`\`python
print(flow(["LLM", "MCP", "Python", "Minecraft Adapter", "Paper/RCON", "Minecraft"]))
\`\`\`

\`\`\`text
LLM
 ↓
MCP
 ↓
Python
 ↓
Minecraft Adapter
 ↓
Paper/RCON
 ↓
Minecraft
\`\`\`

\`\`\`python
print(branch("Python API", ["RCON", "Paper bridge", "mcpi"], "Minecraft"))
\`\`\`

The same topology is also representable independently of rendering:

\`\`\`python
d = diagram(
    ["Python API", "RCON", "Paper bridge", "mcpi", "Minecraft"],
    [
        ("Python API", "RCON"),
        ("Python API", "Paper bridge"),
        ("Python API", "mcpi"),
        ("RCON", "Minecraft"),
        ("Paper bridge", "Minecraft"),
        ("mcpi", "Minecraft"),
    ],
)
print(render_diagram(d))
\`\`\`

The design deliberately does **not** collapse all layouts into one
\`_layout_everything()\` helper. Linear, branch, tree, and future layered-DAG
layouts may remain separate while sharing the same IR and validation contract.


## Converter contracts

All converters pass through the same \`Diagram\` IR instead of converting
formats pairwise.

\`\`\`text
JSON --------\
edge list ----\
adjacency ------> Diagram IR ------> ASCII / Unicode
Mermaid -------/       |            Mermaid
DOT ----------/        |            DOT
Markdown outline       +----------> inventory
\`\`\`

Round-trip categories are explicit:

- **LOSSLESS**: \`dict\`, canonical JSON.
- **NORMALIZED**: edge-list / adjacency when labels are supplied, the supported
  Mermaid flowchart subset, the supported DOT digraph subset, and ATX Markdown
  outlines. Formatting may change while the supported graph meaning is kept.
- **LOSSY**: edge-list / adjacency without a label mapping, rendered text
  layouts, and Markdown outline conversion when original node IDs cannot be
  represented.

Mermaid support is intentionally limited to \`flowchart <direction>\`, explicit
node declarations emitted by this module, and \`A --> B\` edges. DOT support is
limited to the quoted \`digraph G\` form emitted by this module. Markdown input
is an ATX-heading outline subset, not a general Markdown parser.

This mirrors the sibling \`markdown\` library's converter philosophy: declare
the supported subset, centralize the intermediate representation, and test the
round-trip contract instead of claiming full-format compatibility.

## Generator contract

`render_prompt_ascii(prompt, generator)` is intentionally SDK-agnostic. The second argument may be either:

- a callable accepting the final prompt and returning a string (or an object with a string `text` attribute), or
- an object exposing `generate_light(prompt)`, retained for Ironmate compatibility.

The module itself imports no LLM SDK.

## Character/token contract

The `char` argument used by shape generators is a non-empty, single-line **token**. Unicode and multi-code-point tokens are accepted and repeated as-is. Sizes count repetitions, not terminal display cells; perfect alignment for wide Unicode glyphs is outside the stdlib-only contract.

Built-in templates include both Ironmate-derived entries and generic examples such as `cat`, `heart`, and `tree`.

## Capability stance

The module exposes `SUPPORTED` and `UNSUPPORTED` dictionaries so the boundary is machine-readable as well as documented.

Currently supported includes deterministic shape generation, Unicode string tokens, built-in templates, Diagram IR, lossless dict/JSON round trips, edge-list/adjacency adapters, Mermaid/DOT/Markdown-outline subset conversion, inventory, deterministic flow/branch/tree rendering, SDK-agnostic generator adapters, narrow wrapper sanitization, and single-file stdlib-only vendoring.

Explicitly unsupported includes terminal-cell-perfect alignment for wide glyphs, ANSI/terminal capability handling, image decoding/rendering, full Markdown parsing, general-purpose/cyclic graph layout, fuzzy prose deletion, and hard dependencies on a specific LLM SDK.

This boundary is intentional: when a new capability is added, update the stance and add a contract/regression test in the same change.

## Failure-mode documentation

Known design traps and real CI failures are recorded in [`docs/antipatterns.md`](docs/antipatterns.md). New recurring failures should get a stable ID and, where practical, a regression test rather than only a prose note.

Repository diagnostics consume Ironmate's stdlib metadata contract and generator,
both pinned to source commit `0aee64da2f8d0119a3ef9b955e5c3818f28aaf92` with
blob SHA and SHA-256 provenance in `vendor/`. Refresh the pair from the same
explicit commit and update its provenance together; never refresh from moving
`main`. Checkout HEAD owns commit identity; GitHub ref variables only provide
branch context. Tracked-byte measurement, Python tooling, resolver evidence and
Pages presentation remain local. Run `python -m unittest discover -s tests -v`
after refresh. Artifact-header provenance is a separate contract.

## Vendoring

Consumers may copy the single `ascii_artist.py` file into their own `vendor/` directory and pin the source revision without pulling additional runtime dependencies.

Ironmate uses this repository as the upstream source for its vendored ASCII-art module.

## Direction

Planned improvements include richer conversion and layout helpers and text-based graphics while keeping the public API small and practical. Sanitization, generator adapters, edge cases, and the single-file contract are covered by the initial test suite.


## Web UI contract v1

`to_web_ui_v1_html()` renders either a `Diagram` or plain text art into the
stable semantic surface defined by [`myon-bioinformatics/web-ui/contract/v1`](https://github.com/myon-bioinformatics/web-ui/tree/4f43617465a92c912efcd441208e1789b3508d32/contract/v1) (pinned reference: `4f436174`).

The emitted document uses:

- `body[data-ui-theme]`
- `ui-page`
- `ui-title`
- `ui-panel`
- `ui-output`

Text and titles are HTML-escaped, including multi-line art. For `Diagram`
inputs, `charset` currently accepts `unicode` or `ascii`; future charset
extensions can be additive without changing the v1 HTML surface.

The default title remains `ASCII art`; callers can pass an empty string or a
domain-specific title when they want different presentation.

CSS remains consumer-owned, so `ascii_artist.py` keeps its single-file,
standard-library-only runtime contract.


The CI-tested Python versions are **3.12** (baseline) and **3.14** (forward-compatibility check). Python versions outside this tested set are not part of the default CI guarantee.


## Repository diagnostics

GitHub Pages publishes the shared repository metadata contract as
`repository-diagnostics.json`, a one-record `repository-diagnostics.jsonl`,
and `repository-diagnostics.html`. The metadata contract is pinned from
Ironmate, anonymous public GitHub observations are pinned from
mcp-toolcall-lab, and the HTML renderer is pinned to web-ui commit
`adb23d7`. Network failures remain `unverified`; no GitHub token is used
by the public resolver.


## Test-only JUnit collection

Install test dependencies from `tests/requirements.txt`; runtime distribution
remains the single stdlib-only `ascii_artist.py`. The importer contract tests
require a verified `xprobe.py` from commit
`7e7015b2df69ad446b968f6fa49711b5b1dbdd3f` (Git blob
`dbc5b7d55005d6288c072a7612584d6170c216f4`). For local pytest, set
`PYTHONPATH=/path/to/verified/importer-directory`. CI downloads to a temporary
file, verifies the blob, and only then makes it importable.

Each Python job preserves raw JUnit for 14 days, even after a test failure.
The shared collector is pinned to
`myon-bioinformatics/myon-bioinformatics@4dfda95d6573250477f991a0421fa6acb9bc0258`
and runs after all matrix jobs. Its `failure-identity` artifact includes compact
JSONL and a collection completeness summary. Missing/invalid/truncated reports
fail collection explicitly. Commit SHA stays null at this boundary; raw reports
and compact evidence are not added to Pages. Docs-only runs skip collection.

The collector requires the exact five matrix report paths. Keep this set aligned
with the Python matrix; a missing leg cannot be replaced by an extra XML report.
