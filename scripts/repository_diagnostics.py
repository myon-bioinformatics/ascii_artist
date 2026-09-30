"""Build canonical repository diagnostics JSON/JSONL/HTML for Pages."""
from __future__ import annotations

from html import escape
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
from types import ModuleType
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "myon-bioinformatics/ascii_artist"
WEB_UI_SHA = "adb23d7ba6ea94672b76457573f6655a081ee054"
WEB_UI_BASE = f"https://cdn.jsdelivr.net/gh/myon-bioinformatics/web-ui@{WEB_UI_SHA}"
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


CONTRACT = _load_vendor("repository_metadata_contract", canonical_name=True)
GENERATOR = _load_vendor("repository_metadata_generator")
RESOLVER = _load_vendor("github_public_resolver")
GIT_INSPECTOR = _load_vendor("git_inspector")


def _tracked_bytes() -> int:
    observation = GIT_INSPECTOR.ls_files(ROOT)
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
    record = GENERATOR.record_from_checkout(
        ROOT,
        REPOSITORY,
        env=env,
        working_tree_bytes=_tracked_bytes(),
        tooling={"python": platform.python_version()},
    )
    if generated_at is not None:
        record["generated_at"] = generated_at
        CONTRACT.validate_repository_record(record)
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
    html = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__REPO__ repository diagnostics</title>
<link rel="stylesheet" href="__BASE__/css/tokens.css">
<link rel="stylesheet" href="__BASE__/css/base.css">
<link rel="stylesheet" href="__BASE__/css/components.css">
<link rel="stylesheet" href="__BASE__/css/themes/modern.css">
<link rel="stylesheet" href="__BASE__/css/repository-diagnostics.css">
</head>
<body data-ui-theme="modern"><main class="ui-page">
<h1 class="ui-title">__REPO__ repository diagnostics</h1>
<p class="ui-muted">Canonical metadata plus anonymous public GitHub observations.</p>
<div id="metadata"></div>
<section class="ui-panel"><h2>Public URL observations</h2>
<p id="summary" class="ui-muted">Loading…</p><div id="observations" class="ui-grid"></div></section>
<p><a href="./repository-diagnostics.json">JSON</a> · <a href="./repository-diagnostics.jsonl">JSONL</a></p>
</main>
<script src="__BASE__/js/repository-diagnostics.js"></script>
<script>
(async function() {
  const root=document.getElementById("metadata"), summary=document.getElementById("summary"),
        observations=document.getElementById("observations");
  try {
    const response=await fetch("./repository-diagnostics.json",{cache:"no-store"});
    if(!response.ok) throw new Error("fetch failed");
    const payload=await response.json();
    root.innerHTML=RepositoryDiagnostics.render(payload.metadata);
    summary.textContent="Auth: "+(payload.resolver.auth||"unknown")+" · Status: "+(payload.resolver.status||"unknown");
    observations.replaceChildren();
    (payload.resolver.observations||[]).forEach(function(item){
      const card=document.createElement("article"); card.className="ui-card";
      const h=document.createElement("h3"); h.textContent=item.kind||"resource";
      const s=document.createElement("p"); s.className="ui-tag"; s.textContent=item.status||"unknown";
      const code=document.createElement("p"); code.className="ui-muted";
      code.textContent=item.http_status==null?"HTTP: not observed":"HTTP: "+item.http_status;
      const a=document.createElement("a"); a.href=item.url; a.target="_blank"; a.rel="noopener"; a.textContent=item.url;
      card.append(h,s,code,a); observations.append(card);
    });
  } catch(error) {
    summary.textContent="Diagnostics could not be loaded.";
    observations.replaceChildren();
  }
})();
</script></body></html>
"""
    return html.replace("__REPO__", escape(REPOSITORY, quote=True)).replace(
        "__BASE__", escape(WEB_UI_BASE, quote=True)
    )


def write_outputs(out_dir: Path, *, probe: bool = True) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    record = build_record()
    payload = build_payload(record, probe=probe)
    (out_dir / JSON_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / JSONL_NAME).write_text(CONTRACT.to_jsonl(record), encoding="utf-8")
    (out_dir / HTML_NAME).write_text(page_html(), encoding="utf-8")
    return payload


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
    write_outputs(target)
