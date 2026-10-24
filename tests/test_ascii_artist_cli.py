"""ascii_artist.py command-line entry point: unit tests and real-file mutation checks."""
from __future__ import annotations

import io
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_artist as aa  # noqa: E402


def _cli(argv, stdin="", monkeypatch=None, capsys=None):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    try:
        rc = aa.main(argv)
    except SystemExit as exc:
        rc = exc.code
    out, err = capsys.readouterr()
    return rc, out, err


@pytest.fixture
def run(monkeypatch, capsys):
    return lambda argv, stdin="": _cli(argv, stdin, monkeypatch, capsys)


def _diagram_json() -> str:
    return aa.to_json(aa.diagram(["A", "B"], [("A", "B")]))


@pytest.mark.parametrize("name,func", [("square", aa.generate_square), ("triangle", aa.generate_triangle),
                                       ("diamond", aa.generate_diamond)])
def test_shapes_match_api(run, name, func):
    assert run([name, "3", "--char", "#"]) == (0, func(3, "#") + "\n", "")
    assert run([name, "0"]) == (0, "", "")


def test_box_stdin_dash_and_file(run, tmp_path):
    expected = aa.generate_box("hi\nthere", padding=2, style="ascii") + "\n"
    assert run(["box", "--padding", "2", "--style", "ascii"], "hi\nthere\n") == (0, expected, "")
    assert run(["box", "-", "--padding", "2", "--style", "ascii"], "hi\nthere") == (0, expected, "")
    f = tmp_path / "in.txt"
    f.write_text("hi\nthere\n", encoding="utf-8")
    assert run(["box", str(f), "--padding", "2", "--style", "ascii"]) == (0, expected, "")


def test_flow_tree_templates(run):
    assert run(["flow", "A", "B", "--charset", "ascii"]) == (0, aa.flow(["A", "B"], charset="ascii") + "\n", "")
    assert run(["tree", "R", "a", "b"]) == (0, aa.tree("R", {"a": {}, "b": {}}) + "\n", "")
    assert run(["templates"]) == (0, "\n".join(aa.list_templates()) + "\n", "")
    assert run(["template", "cat"]) == (0, aa.get_template("cat"), "")


@pytest.mark.parametrize("target,expected", [
    ("json", lambda d: aa.to_json(d)), ("mermaid", aa.to_mermaid), ("dot", aa.to_dot),
    ("outline", aa.to_markdown_outline), ("render", lambda d: aa.render_diagram(d, charset="ascii")),
    ("inventory", lambda d: __import__("json").dumps(aa.inventory(d), ensure_ascii=False, indent=2)),
])
def test_convert_targets(run, target, expected):
    d = aa.from_json(_diagram_json())
    want = expected(d)
    assert run(["convert", "--from", "json", "--to", target, "--charset", "ascii"], _diagram_json()) == (
        0, want if want.endswith("\n") else want + "\n", "")


@pytest.mark.parametrize("source,writer", [("mermaid", aa.to_mermaid), ("dot", aa.to_dot),
                                           ("outline", aa.to_markdown_outline)])
def test_convert_sources_roundtrip(run, tmp_path, source, writer):
    f = tmp_path / "d.txt"
    f.write_text(writer(aa.from_json(_diagram_json())), encoding="utf-8")
    rc, out, err = run(["convert", str(f), "--from", source, "--to", "json"])
    assert (rc, err) == (0, "")
    d = aa.from_json(out)
    labels = {n.id: n.label for n in d.nodes}
    assert [(labels[e.source], labels[e.target]) for e in d.edges] == [("A", "B")]


@pytest.mark.parametrize("argv", [[], ["bogus"], ["square"], ["square", "x"], ["square", "2", "--ch", "#"],
                                  ["convert", "--from", "json"], ["convert", "--from", "xml", "--to", "json"],
                                  ["box", "--style", "fancy"], ["template", "no-such"], ["flow"]])
def test_usage_errors_exit_2(run, argv):
    rc, out, err = run(argv)
    assert rc == 2 and out == ""
    assert "error:" in err


@pytest.mark.parametrize("argv,stdin", [(["square", "2", "--char", ""], ""),
                                        (["box", "--padding", "-1"], "x"),
                                        (["convert", "--from", "json", "--to", "dot"], "not json"),
                                        (["flow", "A\nB"], "")])
def test_invalid_input_exit_2_one_line(run, argv, stdin):
    rc, out, err = run(argv, stdin)
    assert (rc, out) == (2, "")
    assert err.startswith("ascii_artist.py: error: ") and err.count("\n") == 1


def test_unreadable_file_exit_1(run, tmp_path):
    rc, out, err = run(["box", str(tmp_path / "missing.txt")])
    assert (rc, out) == (1, "")
    assert err.startswith("ascii_artist.py: error: ") and "missing.txt" in err


def test_main_guard_subprocess():
    p = subprocess.run([sys.executable, "-S", str(ROOT / "ascii_artist.py"), "square", "2"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert (p.returncode, p.stdout, p.stderr) == (0, "**\n**\n", "")


def test_public_api_unchanged():
    assert "main" not in aa.__all__
    assert len(aa.__all__) == 33


CHECK = (
    "import subprocess, sys\n"
    "def run(*a, stdin=''):\n"
    "    p = subprocess.run([sys.executable, '-S', 'ascii_artist.py', *a], input=stdin,"
    " capture_output=True, text=True)\n"
    "    return p.returncode, p.stdout\n"
    "ok = (run('box', '--style', 'ascii', stdin='hi') == (0, '+----+\\n| hi |\\n+----+\\n')\n"
    "      and run('square')[0] == 2 and run() == (2, '')\n"
    "      and run('square', '2', '--char', '') == (2, ''))\n"
    "sys.exit(0 if ok else 1)\n"
)


def _check(tmp_path: Path, old: str | None = None, new: str = "") -> int:
    text = (ROOT / "ascii_artist.py").read_text(encoding="utf-8")
    if old is not None:
        assert old in text
        text = text.replace(old, new, 1)
    (tmp_path / "ascii_artist.py").write_text(text, encoding="utf-8")
    (tmp_path / "check.py").write_text(CHECK, encoding="utf-8")
    return subprocess.run([sys.executable, "check.py"], cwd=tmp_path, timeout=120).returncode


def test_mutation_check_unmutated_passes(tmp_path):
    assert _check(tmp_path) == 0


@pytest.mark.parametrize("old,new", [
    ('if __name__ == "__main__":', 'if __name__ == "__nope__":'),
    ("        return sys.stdin.read()", "        return ''"),
    ("        return 2\n    sys.stdout", "        return 0\n    sys.stdout"),
    ('text.endswith("\\n") else text + "\\n"', 'text.endswith("\\n") else text'),
    ("parser.error(\"command required\")", "return 0"),
])
def test_mutation_of_real_file_fails_check(tmp_path, old, new):
    assert _check(tmp_path, old, new) != 0
