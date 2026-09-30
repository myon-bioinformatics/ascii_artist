"""Capture asserted ASCII output and canonical diagnostics with Chromium.

Browser dependencies belong to this CI tool, never to ascii_artist.py.
Shared web-ui assets are served from a separately pinned checkout for offline CI.
"""
from __future__ import annotations

import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sys
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_artist as art
from scripts.repository_diagnostics import WEB_UI_BASE


def sample_output() -> str:
    return art.branch("Request <&>", ["Parse", "Render"], target="Done", charset="ascii") + "\n\n" + art.get_template("cat")


def write_sample(site: Path) -> str:
    output = sample_output()
    document = art.to_web_ui_v1_html(output, title="ASCII output evidence")
    links = "\n".join(f'<link rel="stylesheet" href="{WEB_UI_BASE}/css/{name}.css">'
                      for name in ("tokens", "base", "components", "themes/modern"))
    (site / "ascii-output.html").write_text(document.replace("</head>", links + "</head>"), encoding="utf-8")
    return output


def assert_in_view(locator, page) -> None:
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    viewport = page.viewport_size
    assert box and viewport, "target has no visible box"
    assert box["width"] > 0 and box["height"] > 0
    assert box["x"] >= 0 and box["y"] >= 0
    assert box["x"] + box["width"] <= viewport["width"]
    assert box["y"] + box["height"] <= viewport["height"]


def capture(site: Path, results: Path, web_ui: Path, expected_sha: str) -> None:
    from playwright.sync_api import expect, sync_playwright

    # Do not let a previous attempt's complete receipt satisfy current coverage.
    if results.exists():
        shutil.rmtree(results)
    results.mkdir(parents=True)
    canonical = json.loads((site / "repository-diagnostics.json").read_text(encoding="utf-8"))["metadata"]
    assert canonical["head"]["sha"] == expected_sha, "canonical SHA differs from checkout"
    (results / "canonical.json").write_text(json.dumps(canonical, indent=2) + "\n", encoding="utf-8")
    expected_output = write_sample(site)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(site)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    receipt = {
        "stage": "started", "project": "chromium", "sha": expected_sha,
        "committed_at": canonical["head"]["timestamp"], "generated_at": canonical["generated_at"],
        "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "viewport": {"width": 1280, "height": 900}, "captures": [],
    }
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport=receipt["viewport"])
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page()
            receipt["browser_version"] = browser.version
            def asset(route):
                relative = route.request.url.removeprefix(WEB_UI_BASE + "/")
                target = (web_ui / relative).resolve()
                target.relative_to(web_ui.resolve())
                route.fulfill(path=target)
            page.route(WEB_UI_BASE + "/**", asset)
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                page.goto(base + "/ascii-output.html")
                output = page.locator("pre.ui-output")
                expect(output).to_have_text(expected_output, use_inner_text=False)
                assert output.text_content() == expected_output, "ASCII spacing/escaping changed"
                assert output.evaluate("el => getComputedStyle(el).whiteSpace") in {"pre", "pre-wrap", "break-spaces"}
                assert_in_view(output, page)
                page.screenshot(path=results / "ascii-output.png", animations="disabled")
                page.goto(base + "/repository-diagnostics.html")
                metadata = page.locator("#metadata")
                expect(metadata).to_contain_text(canonical["repository"]["full_name"])
                expect(metadata).to_contain_text(canonical["head"]["short_sha"])
                expect(metadata).to_contain_text(canonical["head"]["timestamp"])
                expect(page.locator("#summary")).to_contain_text("Auth: anonymous")
                assert_in_view(metadata, page)
                page.screenshot(path=results / "repository-diagnostics.png", animations="disabled")
                for filename in ("ascii-output.png", "repository-diagnostics.png"):
                    data = (results / filename).read_bytes()
                    receipt["captures"].append({"file": filename, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
                receipt["stage"] = "complete"
            except Exception as exc:
                receipt["stage"] = "failed"
                receipt["error"] = str(exc)
                try:
                    page.screenshot(path=results / "failure.png", animations="disabled")
                except Exception:
                    pass  # Preserve the original assertion/capture exception.
                raise
            finally:
                try:
                    context.tracing.stop(path=results / "trace.zip")
                except Exception as exc:
                    (results / "trace-error.txt").write_text(str(exc), encoding="utf-8")
                browser.close()
    finally:
        (results / "evidence.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "_site")
    parser.add_argument("--results", type=Path, default=ROOT / "test-results/pages")
    parser.add_argument("--web-ui", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    capture(args.site.resolve(), args.results.resolve(), args.web_ui.resolve(), args.sha)
