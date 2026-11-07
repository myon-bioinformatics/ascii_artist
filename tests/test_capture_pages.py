"""Test screenshot content and reject offscreen targets without browser deps."""
import importlib.util
from pathlib import Path; from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capture_pages", ROOT / "scripts/capture_pages.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def test_sample_uses_real_renderer_and_escapes_html(tmp_path):
    text = capture.write_sample(tmp_path)
    assert "Request <&>" in text and "Parse" in text and "Render" in text and "Done" in text
    assert "( o.o )" in text
    html = (tmp_path / "ascii-output.html").read_text()
    assert "Request &lt;&amp;&gt;" in html
    assert "Request <&>" not in html
    assert '<pre class="ui-output">' in html
    assert capture.WEB_UI_BASE + "/css/themes/modern.css" in html
    assert '<link rel="icon" type="image/png" href="./favicon.png">' in html
    assert '<link rel="apple-touch-icon" href="./icon.png">' in html
    assert 'src="./icon.png"' in html
    assert (tmp_path / "icon.png").read_bytes() == (ROOT / "docs/brand/icon.png").read_bytes()
    assert (tmp_path / "favicon.png").read_bytes() == (ROOT / "docs/brand/favicon.png").read_bytes()


def test_generic_export_does_not_inherit_pages_branding():
    html = capture.art.to_web_ui_v1_html("Consumer output", title="Consumer page")
    assert 'rel="icon"' not in html
    assert "docs/brand" not in html
    assert "favicon.png" not in html


@pytest.mark.parametrize("box", [None, {"x": 0, "y": 0, "width": 0, "height": 10},
    {"x": -1, "y": 0, "width": 10, "height": 10},
    {"x": 0, "y": 899, "width": 10, "height": 10},
    {"x": 1275, "y": 0, "width": 10, "height": 10}])
def test_visibility_alone_cannot_satisfy_viewport_assertion(box):
    locator = SimpleNamespace(scroll_into_view_if_needed=lambda: None, bounding_box=lambda: box)
    with pytest.raises(AssertionError):
        capture.assert_in_view(locator, SimpleNamespace(viewport_size={"width": 1280, "height": 900}))


def test_complete_box_in_view():
    locator = SimpleNamespace(scroll_into_view_if_needed=lambda: None,
                             bounding_box=lambda: {"x": 0, "y": 0, "width": 1280, "height": 900})
    capture.assert_in_view(locator, SimpleNamespace(viewport_size={"width": 1280, "height": 900}))


def test_card_samples_use_canonical_renderer_and_preserve_boundaries(tmp_path):
    data = capture.write_card_samples(tmp_path)
    assert len(data["sources"][0]["title"]) == 120
    assert data["sources"][0]["note"] == ""
    assert len(data["steps"][0]["note"]) == 240
    for theme in ("github-like", "modern"):
        document = (tmp_path / f"flow-{theme}.html").read_text(encoding="utf-8")
        assert document == capture.art.flow_document(data, theme=theme)
        assert '<script>' not in document and '<link ' not in document
        assert '&lt;script&gt;not executable&lt;/script&gt;' in document
        assert '<style>' in document
    assert len(capture.CARD_CAPTURES) == 4


def test_pages_lane_requires_original_and_card_evidence():
    workflow = (ROOT / ".github/workflows/pages.yml").read_text()
    captures = 'ascii-output.png,repository-diagnostics.png,' + ','.join(capture.CARD_CAPTURES)
    assert '--captures ' + captures in workflow
    assert 'python scripts/capture_pages.py' in workflow
    # Both push and PR path filters must execute the changed browser helper.
    assert workflow.count('- "scripts/capture_pages.py"') == 2
