"""ascii_artist.py command-line entry point: unit tests and real-file mutation checks."""
from __future__ import annotations

import argparse, io, shutil, subprocess, sys
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
    # Existing exports remain; card-flow migration adds six explicit APIs.
    original = {'from_dict', 'to_markdown_outline', 'to_adjacency', 'to_dot', 'UNSUPPORTED', 'to_edges', 'from_dot', 'to_web_ui_v1_html', 'to_mermaid', 'Node', 'Diagram', 'from_edges', 'from_mermaid', 'SUPPORTED', 'inventory', 'from_markdown_outline', 'render_diagram', 'generate_diamond', 'from_adjacency', 'diagram', 'to_dict', 'branch', 'render_prompt_ascii', 'flow', 'from_json', 'generate_triangle', 'to_json', 'generate_box', 'list_templates', 'get_template', 'Edge', 'generate_square', 'tree'}
    additions = {"validate_flow", "flow_html", "flow_mermaid", "flow_document", "flow_css", "patch_flow"}
    assert set(aa.__all__) == original | additions
    assert len(aa.__all__) == len(original) + len(additions)


def test_box_new_options_match_api(run):
    expected = aa.generate_box(
        "hello", padding=(1, 1), style="heavy", align="center",
        title="Hi", width=16, shadow=True,
    ) + "\n"
    assert run(
        ["box", "--padding", "1,1", "--style", "heavy", "--align", "center",
         "--title", "Hi", "--width", "16", "--shadow"],
        "hello",
    ) == (0, expected, "")


def test_box_title_longer_than_width_cli(run):
    expected = aa.generate_box("x", padding=0, style="ascii", title="LongTitle", width=5) + "\n"
    assert run(["box", "--padding", "0", "--style", "ascii", "--title", "LongTitle", "--width", "5"], "x") == (
        0, expected, "",
    )


def test_box_cjk_width_and_align_cli(run):
    expected = aa.generate_box("日本語", padding=0, style="ascii", width=6, align="right") + "\n"
    assert run(["box", "--padding", "0", "--style", "ascii", "--width", "6", "--align", "right"], "日本語") == (
        0, expected, "",
    )


@pytest.mark.parametrize("argv", [
    ["box", "--align", "justify"],
    ["box", "--style", "heavyx"],
    ["box", "--padding", "1,2,3"],
    ["box", "--padding", "x"],
    ["box", "--width", "wide"],
])
def test_box_invalid_options_are_argparse_errors(run, argv):
    rc, out, err = run(argv, "x")
    assert rc == 2 and out == ""
    assert "error:" in err


def test_branch_cli_matches_library(run):
    expected = aa.branch("root", ["left", "right"], "end") + "\n"
    assert run(["branch", "root", "left", "right", "--target", "end"]) == (0, expected, "")
    expected_ascii = aa.branch("R", ["a"], charset="ascii") + "\n"
    assert run(["branch", "R", "a", "--charset", "ascii"]) == (0, expected_ascii, "")
    expected_root = aa.branch("only", []) + "\n"
    assert run(["branch", "only"]) == (0, expected_root, "")


def test_branch_rejects_multiline_labels(run):
    rc, out, err = run(["branch", "root", "a\nb"])
    assert (rc, out) == (2, "")
    assert err.startswith("ascii_artist.py: error: ") and err.count("\n") == 1


def test_cli_padding_parser():
    assert aa._cli_padding("2") == 2
    assert aa._cli_padding("-1") == -1
    assert aa._cli_padding("2,3") == (2, 3)
    for value in ("1,2,3", "x", "1,x", "x,1"):
        with pytest.raises(argparse.ArgumentTypeError, match="N or H,V"):
            aa._cli_padding(value)


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
    ("        return 2\n    output =", "        return 0\n    output ="),
    ('text.endswith("\\n") else text + "\\n"', 'text.endswith("\\n") else text'),
    ("parser.error(\"command required\")", "return 0"),
])
def test_mutation_of_real_file_fails_check(tmp_path, old, new):
    assert _check(tmp_path, old, new) != 0


@pytest.mark.parametrize("item", ["", "a\nb", "a\rb", "a\r\nb"])
@pytest.mark.parametrize("charset", ["unicode", "ascii"])
def test_tree_rejects_invalid_items_without_partial_output(run, item, charset):
    assert run(["tree", "Root", "valid", item, "--charset", charset]) == (
        2, "", "ascii_artist.py: error: tree items must be non-empty single-line strings\n"
    )


def test_tree_keeps_spaces_and_unicode(run):
    assert run(["tree", "根", "two words", "葉"]) == (
        0, aa.tree("根", {"two words": {}, "葉": {}}) + "\n", ""
    )


def test_layered_layout_resolves_duplicates_joins_and_rank_skipping(tmp_path):
    value = aa.diagram(
        [aa.Node("sink", "Join"), aa.Node("left", "Same"),
         aa.Node("middle", "Middle"), aa.Node("right", "Same"), "isolated"],
        [("left", "middle"), ("right", "middle"), ("middle", "sink"),
         ("left", "sink")],
    )
    expected = (
        "Layer 1\n  [2] Same\n  [4] Same\n  [5] isolated\n"
        "  [2] > [3]\n  [4] > [3]\n  [2] > [1]\n\n"
        "Layer 2\n  [3] Middle\n  [3] > [1]\n\n"
        "Layer 3\n  [1] Join"
    )
    assert aa.render_diagram(value, layout="layered", charset="ascii") == expected
    assert aa.render_diagram(value, layout="layered") == expected.replace(">", "→")
    assert aa.render_diagram(value) == aa.render_diagram(value, layout="adjacency")
    assert aa.render_diagram(value).startswith("Join\nSame\n")
    assert aa.render_diagram(aa.diagram([]), layout="layered") == ""

    module = tmp_path / "ascii_artist.py"
    shutil.copyfile(ROOT / "ascii_artist.py", module)
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(module), "convert",
         "--from", "json", "--to", "render", "--layout", "layered", "--charset", "ascii"],
        input=aa.to_json(value), text=True, encoding="utf-8",
        capture_output=True, check=True,
    )
    assert (result.stdout, result.stderr) == (expected + "\n", "")


def test_layered_layout_requires_valid_dag_and_render_target(run):
    cyclic = aa.Diagram((aa.Node("a", "A"), aa.Node("b", "B")),
                        (aa.Edge("a", "b"), aa.Edge("b", "a")))
    with pytest.raises(ValueError, match="acyclic"):
        aa.render_diagram(cyclic, layout="layered")
    with pytest.raises(ValueError, match="layout"):
        aa.render_diagram(aa.diagram([]), layout="unknown")
    code, out, err = run(["convert", "--from", "json", "--to", "dot", "--layout", "layered"],
                         _diagram_json())
    assert (code, out) == (2, "")
    assert "--layout requires --to render" in err


BOX_CHECK = r"""
import argparse, importlib.util, subprocess, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('ascii_artist', Path('ascii_artist.py'))
aa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aa)

def cli(*argv, stdin='x'):
    p = subprocess.run([sys.executable, '-S', 'ascii_artist.py', *argv], input=stdin,
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

ok = True
ok = ok and aa.generate_box('Hello') == '┌───────┐\n│ Hello │\n└───────┘'
ok = ok and aa.generate_box('Hello') == aa.generate_box('Hello', padding=(1, 0))
ok = ok and aa.generate_box('Hi', padding=(1, 1), style='ascii') == (
    '+----+\n|    |\n| Hi |\n|    |\n+----+')
ok = ok and aa.generate_box('日本\nab', padding=0, style='ascii', align='center') == (
    '+----+\n|日本|\n| ab |\n+----+')
ok = ok and aa.generate_box('日本\nab', padding=0, style='ascii', align='right') == (
    '+----+\n|日本|\n|  ab|\n+----+')
ok = ok and aa.generate_box('ab', padding=0, style='ascii', align='center', width=7) == (
    '+-----+\n| ab  |\n+-----+')
ok = ok and aa.generate_box('Hi', padding=0, style='heavy') == '┏━━┓\n┃Hi┃\n┗━━┛'
titled = aa.generate_box('x', padding=0, style='ascii', title='LongTitle', width=5)
ok = ok and titled == '+- LongTitle -+\n|x            |\n+-------------+'
ok = ok and aa.generate_box('hello', title='') == aa.generate_box('hello')
ok = ok and aa.generate_box('hello world', padding=0, style='ascii', width=10) == (
    '+--------+\n|hello   |\n|world   |\n+--------+')
ok = ok and aa.generate_box('hello', padding=0, style='ascii', width=4) == (
    '+--+\n|he|\n|ll|\n|o |\n+--+')
ok = ok and aa.generate_box('ab', padding=2, style='ascii', width=3) == (
    '+-----+\n|  a  |\n|  b  |\n+-----+')
ok = ok and aa.generate_box('ab', padding=1, style='ascii', width=4) == (
    '+---+\n| a |\n| b |\n+---+')
ok = ok and aa.generate_box('Hi', padding=0, style='ascii', shadow=True) == (
    '+--+#\n|Hi|#\n+--+#\n ####')
ok = ok and aa.generate_box('Hi', padding=0, shadow=True).endswith('░')
ok = ok and '░' in aa.generate_box('Hi', padding=0, shadow=True)
rc, out, err = cli('box', '--padding', '1,1', '--style', 'ascii', stdin='Hi')
ok = ok and (rc, out) == (0, aa.generate_box('Hi', padding=(1, 1), style='ascii') + '\n')
rc, out, err = cli('branch', 'root', 'left', 'right', '--target', 'end')
ok = ok and (rc, out) == (0, aa.branch('root', ['left', 'right'], 'end') + '\n')
rc, out, err = cli('box', '--align', 'justify', stdin='x')
ok = ok and rc == 2 and out == '' and 'error:' in err
try:
    aa._cli_padding('1,2,3')
    ok = False
except argparse.ArgumentTypeError:
    pass
sys.exit(0 if ok else 1)
"""


def _box_check(tmp_path: Path, old: str | None = None, new: str = "") -> int:
    text = (ROOT / "ascii_artist.py").read_text(encoding="utf-8")
    if old is not None:
        assert text.count(old) == 1, old
        text = text.replace(old, new, 1)
    (tmp_path / "ascii_artist.py").write_text(text, encoding="utf-8")
    (tmp_path / "box_check.py").write_text(BOX_CHECK, encoding="utf-8")
    return subprocess.run([sys.executable, "box_check.py"], cwd=tmp_path, timeout=120).returncode


def test_box_mutation_unmutated_passes(tmp_path):
    assert _box_check(tmp_path) == 0


@pytest.mark.parametrize("old,new", [
    ("        return padding, 0", "        return padding, padding"),
    ("        return padding[0], padding[1]", "        return padding[1], padding[0]"),
    ("        left = gap // 2", "        left = (gap + 1) // 2"),
    ('        return " " * gap + text', '        return text + " " * gap'),
    ('        "tl": "┏", "tr": "┓", "bl": "┗", "br": "┛", "h": "━", "v": "┃"',
     '        "tl": "┏", "tr": "┓", "bl": "┗", "br": "┛", "h": "━", "v": "│"'),
    ("        inner = max(inner, display_width(title) + 4)", "        inner = max(inner, display_width(title) + 0)"),
    ("    if title is None:", "    if title is not None:"),
    ("        if current and display_width(trial) > width:", "        if current and display_width(trial) >= width:"),
    ("            if len(broken) == 2:", "            if len(broken) == 3:"),
    ("        if wrap_at < 1:", "        if wrap_at < 0:"),
    ('    mark = "#" if ascii_style else "░"', '    mark = "░"'),
    ('    shadowed.append(" " + mark * width)', "    pass"),
    (
        "            text = branch(args.root, args.items, args.target, charset=args.charset)",
        "            text = branch(args.root, args.items, charset=args.charset)",
    ),
    ("        lines = [part for line in lines for part in _wrap_display(line, wrap_at)]", "        pass"),
    ("        if not title:\n            title = None", "        if False:\n            title = None"),
    ("    if len(parts) == 2:", "    if len(parts) == 3:"),
    ('        return _box_shadow(box, ascii_style=style == "ascii")',
     "        return _box_shadow(box, ascii_style=False)"),
])
def test_box_mutation_of_real_file_fails_check(tmp_path, old, new):
    assert _box_check(tmp_path, old, new) != 0
