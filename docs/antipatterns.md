# ASCII artist anti-patterns

This document is a running catalog of failure modes and design traps observed while keeping `ascii_artist.py` a stdlib-only, single-file library.

The intent follows two sibling-project practices:

- `markdown`: make supported/unsupported boundaries explicit and pin them with tests.
- `mcp-toolcall-lab`: give recurring failure modes stable IDs instead of treating each occurrence as an unrelated bug.

When an anti-pattern is observed in real development or CI, add or update an entry here and add a regression test when practical.

## Catalog

| ID | Anti-pattern | Why it is harmful | Preferred contract |
| --- | --- | --- | --- |
| `ESCAPED_FENCE_FIXTURE` | Test data uses `\`\`\`` instead of a real Markdown fence | The fixture no longer represents real model output, so sanitizer tests fail for the wrong reason | Fixtures must contain literal `~~~` or backtick fences exactly as generated |
| `SDK_COUPLED_GENERATOR` | Public API requires one concrete LLM class or SDK method | A vendored single file stops being standalone | Accept a small callable/protocol boundary; keep SDK adapters outside the module |
| `WRAPPER_LEAK` | Role labels, prose preambles, or Markdown fences survive sanitization | Consumers receive chat protocol noise instead of ASCII content | Strip only documented wrapper lines with narrow regexes and regression tests |
| `OVERBROAD_SANITIZER_REGEX` | Regex removes arbitrary lines merely because they contain words such as `assistant` or `ascii` | Valid artwork can be destroyed silently | Match complete wrapper lines with anchored expressions; preserve unknown content |
| `EMPTY_OR_MULTILINE_TOKEN` | Shape generators accept an empty token or a token containing newlines | Output dimensions become misleading or structurally corrupted | Require a non-empty, single-line string token |
| `DISPLAY_WIDTH_ASSUMPTION` | Python string length/repetition is treated as terminal cell width | Wide Unicode and emoji can visually misalign | Define sizes as token repetition counts; terminal-cell-perfect width is outside the core contract |
| `ASCII_ONLY_BY_ACCIDENT` | Unicode input is rejected merely because the project name says ASCII art | Useful text-art tokens are excluded without a technical need | Preserve Unicode tokens; distinguish byte/ASCII purity from text-art behavior |
| `IRONMATE_ONLY_LIBRARY` | Standalone module only exposes Ironmate-branded examples or interfaces | Extraction does not actually create a reusable library | Keep compatibility examples but include generic templates and generic callable APIs |
| `RUNTIME_ASSET_DEPENDENCY` | Core module needs YAML/JSON/template files next to it | Copy-one-file vendoring no longer works | Built-in defaults required by the core live in the single Python file |
| `NON_STDLIB_RUNTIME_DEPENDENCY` | Core behavior imports Pillow, PyYAML, an LLM SDK, etc. unconditionally | The defining stdlib-only property is lost | Core stays stdlib-only; future optional integrations belong outside the core artifact |
| `DUPLICATE_IMPLEMENTATION` | Vendored/package/application copies evolve independently | Bug fixes and contracts drift across repositories | `ascii_artist.py` is the source of truth; consumers refresh a reviewed snapshot |
| `HAPPY_PATH_ONLY_TESTS` | Tests cover only one square/triangle/diamond example | Sanitizer and input contracts regress unnoticed | Cover invalid input, zero/negative sizes, Unicode, wrappers, generator variants, and failure results |

## Observed incident: escaped Markdown fences

The first CI failure in PR #1 was caused by the test fixture itself:

```text
\`\`\`ascii
 /\_/\
( o.o )
\`\`\`
```

Those backslashes were literal characters in the Python string. Python emitted an invalid-escape warning, and the sanitizer correctly did not classify the lines as Markdown fences.

The fixed fixture contains the actual model-like output:

~~~text
```ascii
 /\_/\
( o.o )
```
~~~

Lesson: sanitizer fixtures should model the external text exactly. Do not escape syntax merely to make the surrounding source visually convenient.

## Regex rules

Sanitization regexes should stay deliberately narrow:

1. Anchor to the whole wrapper line whenever possible.
2. Prefer a small set of known protocol/preamble forms over fuzzy deletion.
3. Treat unmatched text as user/model content and preserve it.
4. Add a regression test before broadening a regex for a newly observed form.
5. Do not grow the sanitizer into a Markdown parser. If Markdown parsing becomes necessary, reuse the sibling `markdown.py` artifact rather than reimplementing it here.

## Single-file rule

The repository may contain documentation, tests, and CI, but the reusable product remains exactly:

```text
ascii_artist.py
```

Copying that file alone must not require repository-local modules, template directories, configuration files, or third-party packages.
