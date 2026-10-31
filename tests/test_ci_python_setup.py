"""Stdlib-only contracts for CI Python selection and preserved baselines."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SETUP_UV = "astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2"
JOBS = {
    "ci.yml": {
        "resolve-vendor": "3.15",
        "test": "${{ matrix.python-version }}",
        "test-locked": "${{ matrix.python-version }}"
    },
    "pages.yml": {
        "checks": "3.15",
        "build": "3.15"
    },
    "runtime-compatibility.yml": {
        "runtime": "${{ matrix.python }}",
        "portability": "3.11"
    }
}
EXPECTED_REPORTS = [
    "junit-py3.11/pytest-3.11.xml",
    "junit-py3.12/pytest-3.12.xml",
    "junit-py3.13/pytest-3.13.xml",
    "junit-py3.14/pytest-3.14.xml"
]


def job(workflow, name):
    """Read the bounded job block in our two-space-indented workflows."""
    text = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
    pattern = r"(?ms)^  " + re.escape(name) + r":\n(.*?)(?=^  [\w-]+:\n|\Z)"
    match = re.search(pattern, text)
    if match is None:
        raise AssertionError(f"Missing job {workflow}: {name}")
    return match.group(1)


class CiPythonSetupTests(unittest.TestCase):
    def test_selected_python_is_ready_before_any_python_or_uv_command(self):
        for workflow, jobs in JOBS.items():
            for name, version in jobs.items():
                with self.subTest(workflow=workflow, job=name):
                    block = job(workflow, name)
                    self.assertEqual(block.count("uses: " + SETUP_UV), 1)
                    setup = block.index("uses: " + SETUP_UV)
                    command = re.search(
                        r"(?m)^\s*(?:-\s+)?(?:run:\s*)?(?:python(?:3)?|uv)\s+",
                        block,
                    )
                    self.assertIsNotNone(command, "No interpreter consumer was checked")
                    self.assertLess(setup, command.start(), "Python ran before setup-uv")
                    setup_inputs = block[setup:].split("\n", 7)[:6]
                    inputs = "\n".join(setup_inputs)
                    self.assertIn('version: "0.13.3"', inputs)
                    self.assertIn(f'python-version: "{version}"', inputs)
                    self.assertIn("activate-environment: true", inputs)
                    self.assertIn("enable-cache: false", inputs)

    def test_compatibility_matrix_and_required_report_identities_are_preserved(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("python-version: [\"3.11\", \"3.12\", \"3.13\", \"3.14\"]", text)
        match = re.search(r"expected-reports: '([^']+)'", job("ci.yml", "failure-identity"))
        self.assertIsNotNone(match)
        self.assertEqual(json.loads(match.group(1)), EXPECTED_REPORTS)

    def test_locked_baseline_and_pages_venv_install_are_preserved(self):
        locked = job("ci.yml", "test-locked")
        self.assertRegex(locked, r"python-version:\s*\n\s*- '3\.12'")
        self.assertIn("name: locked-junit-py${{ matrix.python-version }}", locked)
        for name in ("checks", "build"):
            self.assertIn("uv pip install ", job("pages.yml", name))
            self.assertNotIn("python -m pip", job("pages.yml", name))
        self.assertIn("if: github.ref == 'refs/heads/main'", job("pages.yml", "deploy"))


if __name__ == "__main__":
    unittest.main()
