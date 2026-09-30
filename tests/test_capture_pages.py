"""Test screenshot content and reject offscreen targets without browser deps."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

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
