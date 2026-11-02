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
from scripts.ascii_artist_repository_diagnostics import WEB_UI_BASE, write_favicon


def sample_output() -> str:
    return art.branch("Request <&>", ["Parse", "Render"], target="Done", charset="ascii") + "\n\n" + art.get_template("cat")


def write_sample(site: Path) -> str:
    write_favicon(site)
    output = sample_output()
    document = art.to_web_ui_v1_html(output, title="ASCII output evidence")
    links = "\n".join(f'<link rel="stylesheet" href="{WEB_UI_BASE}/css/{name}.css">'
                      for name in ("tokens", "base", "components", "themes/modern"))
    links += '\n<link rel="icon" type="image/png" href="./favicon.png">'
    links += '\n<link rel="apple-touch-icon" href="./icon.png">'
    (site / "ascii-output.html").write_text(document.replace("</head>", links + "</head>").replace('<h1', '<img src="./icon.png" width="80" height="80" alt="ascii_artist icon"><h1', 1), encoding="utf-8")
    return output



CARD_CAPTURES = tuple(f"flow-{theme}-{width}.png"
                      for theme in ("github-like", "modern") for width in (320, 1280))


def card_sample() -> dict:
    """Exercise HTML escaping, empty notes and Unicode code-point boundaries."""
    return {"title": '入力 <&> "Build"', "sources_label": "入力ソース",
            "sources": [{"title": "😀" * 120, "note": ""},
                        {"title": "Python <script>not executable</script>", "note": "入力"}],
            "steps": [{"title": "検査", "note": "界" * 240}]}


def write_card_samples(site: Path) -> dict:
    spec = card_sample()
    for theme in ("github-like", "modern"):
        (site / f"flow-{theme}.html").write_text(art.flow_document(spec, theme=theme), encoding="utf-8")
    return spec


def capture_card_flows(page, base: str, results: Path, spec: dict) -> None:
    """Actual Chromium checks; the browserless fixture tests cannot replace these."""
    from playwright.sync_api import expect

    for theme, background in (("github-like", "rgb(255, 255, 255)"),
                              ("modern", "rgb(13, 17, 23)")):
        for width in (320, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(base + f"/flow-{theme}.html")
            expect(page.locator(".ui-flow-card")).to_have_count(3)
            expect(page.locator(".ui-flow-card-note")).to_have_count(2)
            expect(page.locator("script")).to_have_count(0)
            assert page.locator(".ui-flow-caption").text_content() == spec["title"]
            assert page.locator(".ui-flow-card-title").all_text_contents() == [
                card["title"] for card in spec["sources"] + spec["steps"]]
            assert page.locator(".ui-flow-step .ui-flow-card-note").text_content() == "界" * 240
            style = page.locator("body").evaluate("el => getComputedStyle(el).backgroundColor")
            assert style == background, (theme, style)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "flow overflows viewport"
            for box in page.locator(".ui-flow-card").all():
                assert box.evaluate("el => getComputedStyle(el).boxSizing") == "border-box"
            sources = page.locator(".ui-flow-source").evaluate_all(
                "els => els.map(el => ({x:el.getBoundingClientRect().x,y:el.getBoundingClientRect().y}))")
            if width == 320:
                assert sources[0]["x"] == sources[1]["x"] and sources[1]["y"] > sources[0]["y"]
            else:
                assert sources[0]["y"] == sources[1]["y"] and sources[1]["x"] > sources[0]["x"]
            page.screenshot(path=results / f"flow-{theme}-{width}.png", full_page=True, animations="disabled")
    # The fragment is independently usable with the in-memory stylesheet.
    page.set_content('<style>' + art.flow_css() + '</style>' + art.flow_html(spec))
    expect(page.locator("figure.ui-flow")).to_have_count(1)
    expect(page.locator("script, link")).to_have_count(0)
    assert page.locator(".ui-flow-sources").evaluate("el => getComputedStyle(el).display") == "grid"
    assert page.locator(".ui-flow-card-title").first.text_content() == "😀" * 120
    page.set_viewport_size({"width": 1280, "height": 900})


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
    expected_cards = write_card_samples(site)
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
                logo = page.locator('img[src="./icon.png"]')
                expect(logo).to_be_visible()
                assert logo.evaluate("el => el.complete && el.naturalWidth > 0"), "project icon did not decode"
                output = page.locator("pre.ui-output")
                expect(output).to_have_text(expected_output, use_inner_text=False)
                assert output.text_content() == expected_output, "ASCII spacing/escaping changed"
                assert output.evaluate("el => getComputedStyle(el).whiteSpace") in {"pre", "pre-wrap", "break-spaces"}
                colors = output.evaluate("el => ({color: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor})")
                assert colors == {"color": "rgb(22, 27, 34)", "background": "rgb(216, 222, 228)"}, colors
                assert_in_view(output, page)
                page.screenshot(path=results / "ascii-output.png", animations="disabled")
                page.goto(base + "/repository-diagnostics.html")
                logo = page.locator('img[src="./icon.png"]')
                expect(logo).to_be_visible()
                assert logo.evaluate("el => el.complete && el.naturalWidth > 0"), "project icon did not decode"
                metadata = page.locator("#metadata")
                expect(metadata).to_contain_text(canonical["repository"]["full_name"])
                expect(metadata).to_contain_text(canonical["head"]["short_sha"])
                expect(metadata).to_contain_text(canonical["head"]["timestamp"])
                expect(page.locator("#summary")).to_contain_text("Auth: anonymous")
                assert_in_view(metadata, page)
                page.screenshot(path=results / "repository-diagnostics.png", animations="disabled")
                capture_card_flows(page, base, results, expected_cards)
                for filename in ("ascii-output.png", "repository-diagnostics.png", *CARD_CAPTURES):
                    data = (results / filename).read_bytes()
                    viewport = {"width": int(filename.rsplit("-", 1)[1].split(".")[0]), "height": 900} if filename in CARD_CAPTURES else receipt["viewport"]
                    receipt["captures"].append({"file": filename, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "viewport": viewport})
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
