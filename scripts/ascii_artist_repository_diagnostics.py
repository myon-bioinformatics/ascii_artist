"""Build canonical repository diagnostics JSON/JSONL/HTML for Pages."""
from __future__ import annotations

import importlib.util, json, os, platform, sys
from pathlib import Path; from types import ModuleType; from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "myon-bioinformatics/ascii_artist"
JSON_NAME = "repository-diagnostics.json"
JSONL_NAME = "repository-diagnostics.jsonl"
HTML_NAME = "repository-diagnostics.html"


def _load_vendor(name: str, *, canonical_name: bool = False) -> ModuleType:
    path = ROOT / "vendor" / f"{name}.py"
    module_name = name if canonical_name else f"ascii_artist_vendor_{name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load vendored module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RESOLVER = _load_vendor("github_public_resolver")
GH_IDENTITY = _load_vendor("gh_identity", canonical_name=True)


def _tracked_bytes() -> int:
    observation = GH_IDENTITY.git_ls_files(ROOT)
    if observation["truncated"]:
        raise RuntimeError("tracked-file inventory was truncated")
    total = 0
    for item in observation["paths"]:
        path = ROOT / item
        if path.is_file():
            total += path.stat().st_size
    return total


def build_record(
    env: Mapping[str, str] | None = None,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    env = os.environ if env is None else env
    record = GH_IDENTITY.repository_metadata_v1(
        ROOT,
        repository=REPOSITORY,
        env=env,
        measurements={"working_tree_bytes": _tracked_bytes()},
        tooling={"python": platform.python_version()},
    )
    if generated_at is not None:
        record["generated_at"] = generated_at
        GH_IDENTITY.validate_repository_metadata_v1(record)
    return record


def build_payload(record: dict[str, Any], *, probe: bool = True) -> dict[str, Any]:
    try:
        resolver = RESOLVER.resolve_public_github(
            record["repository"]["full_name"],
            ref=record["head"]["branch"],
            path="README.md",
            probe=probe,
        )
    except ValueError as exc:
        if "ref must be a simple Git ref" not in str(exc):
            raise
        resolver = {
            "repository": record["repository"]["full_name"],
            "ref": record["head"]["branch"],
            "path": "README.md",
            "auth": "anonymous",
            "candidates": [],
            "observations": [],
            "status": "not_checked",
            "reason": "unsupported_ref",
        }
    return {"metadata": record, "resolver": resolver}


def page_html() -> str:
    """The shared diagnostics page from PySaiyanWeBoo (bundled CSS and renderer embedded, nothing from a CDN)."""
    import web_ui  # the pinned git dependency in the dev group

    return web_ui.repository_diagnostics_page(REPOSITORY)


def write_favicon(out_dir: Path) -> None:
    """Copy repository branding for Pages, never for library exports."""
    (out_dir / "favicon.png").write_bytes((ROOT / "docs/brand/favicon.png").read_bytes())
    (out_dir / "icon.png").write_bytes((ROOT / "docs/brand/icon.png").read_bytes())


def write_outputs(out_dir: Path, *, probe: bool = True) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_favicon(out_dir)
    record = build_record()
    payload = build_payload(record, probe=probe)
    (out_dir / JSON_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    GH_IDENTITY.validate_repository_metadata_v1(record)
    (out_dir / JSONL_NAME).write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (out_dir / HTML_NAME).write_text(page_html(), encoding="utf-8")
    return payload


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    target = Path(argv[0]) if len(argv) > 0 else ROOT / "_site"
    write_outputs(target)


if __name__ == "__main__":
    raise SystemExit(main())
