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

## Layout

```text
.
├─ ascii_artist.py
├─ template_store.py
├─ templates_ascii/
└─ templates_prompt/
```

## Vendoring

Consumers that do not want a package dependency may copy `ascii_artist.py` into their own `vendor/` directory and pin the source revision in their normal dependency/update process.

Ironmate uses this repository as the upstream source for its vendored ASCII-art module.

## Direction

Planned improvements include richer generation and conversion helpers, layout utilities, text-based graphics, reusable sanitization, and stronger tests while keeping the public API small and practical.
