"""Callable argv entrypoints survive integration with the shared page renderer."""
from pathlib import Path
from unittest.mock import patch

from scripts import ascii_artist_repository_diagnostics as diagnostics
from scripts import capture_pages


def test_diagnostics_main_accepts_explicit_argv(tmp_path):
    with patch.object(diagnostics, "write_outputs") as write:
        diagnostics.main([str(tmp_path)])
    write.assert_called_once_with(tmp_path)


def test_capture_main_accepts_explicit_argv_without_removed_web_ui(tmp_path):
    site, results = tmp_path / "site", tmp_path / "results"
    with patch.object(capture_pages, "capture") as capture:
        capture_pages.main(["--site", str(site), "--results", str(results), "--sha", "abc123"])
    capture.assert_called_once_with(site.resolve(), results.resolve(), "abc123")


def test_capture_main_preserves_cli_default_argv(tmp_path):
    with patch("sys.argv", ["capture_pages.py", "--sha", "abc123"]), patch.object(capture_pages, "capture") as capture:
        capture_pages.main()
    capture.assert_called_once_with((capture_pages.ROOT / "_site").resolve(), (capture_pages.ROOT / "test-results/pages").resolve(), "abc123")
