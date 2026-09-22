# ascii_artist

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

## Design

The product is a single file: `ascii_artist.py`.

- standard library only
- no runtime dependency on package-specific support modules
- usable by copying one file into another project
- suitable for vendoring as `vendor/ascii_artist.py`

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

Currently supported includes deterministic shape generation, Unicode string tokens, built-in templates, SDK-agnostic generator adapters, narrow wrapper sanitization, and single-file stdlib-only vendoring.

Explicitly unsupported includes terminal-cell-perfect alignment for wide glyphs, ANSI/terminal capability handling, image decoding/rendering, full Markdown parsing, fuzzy prose deletion, and hard dependencies on a specific LLM SDK.

This boundary is intentional: when a new capability is added, update the stance and add a contract/regression test in the same change.

## Failure-mode documentation

Known design traps and real CI failures are recorded in [`docs/antipatterns.md`](docs/antipatterns.md). New recurring failures should get a stable ID and, where practical, a regression test rather than only a prose note.

## Vendoring

Consumers may copy the single `ascii_artist.py` file into their own `vendor/` directory and pin the source revision without pulling additional runtime dependencies.

Ironmate uses this repository as the upstream source for its vendored ASCII-art module.

## Direction

Planned improvements include richer conversion and layout helpers and text-based graphics while keeping the public API small and practical. Sanitization, generator adapters, edge cases, and the single-file contract are covered by the initial test suite.
