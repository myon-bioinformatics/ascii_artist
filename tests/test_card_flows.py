"""🃏 Card flows: validation, HTML safety, atomic patches, CLI byte budgets and Python/Node parity.

Stdlib unittest (also runs under ``python -S -m unittest``). The Node 26+ adapter is optional:
parity cases skip it, and mixed cases omit its branch, when it is unavailable (``vendor/fleet_check.node``).
"""
import importlib.util
import copy, json, os, subprocess, sys, tempfile, unittest
from html.parser import HTMLParser; from pathlib import Path

from ascii_artist import (FLOW_MAX_INPUT, FLOW_MAX_PATCH, flow_css, flow_document,
                          flow_html, flow_mermaid, from_dict, patch_flow, validate_flow)


def load_vendored(name, relpath):
    """Load a vendored file by path under a repo-unique name (cli_args README: Loading a vendored copy)."""
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / relpath)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


fleet = load_vendored("ascii_artist_fleet_check", "vendor/fleet_check.py")
run_cli = load_vendored("ascii_artist_cli_args", "vendor/cli_args.py").run_cli

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "examples/pr-flow.json").read_text(encoding="utf-8"))
NODE = fleet.node(ci_jobs=("test", "vendor-locked"))
# The documented Node entry: the shared launcher called directly (no per-tool wrapper).
NODE_ENTRY = [NODE, "vendor/py_launch.cjs", "--env-var", "ASCII_ARTIST_PYTHON", "--", "ascii_artist.py"] if NODE else None
RUNNERS = [[sys.executable, "-S", "ascii_artist.py"], *([NODE_ENTRY] if NODE else [])]


class Elements(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.feed(source)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


# ──── diagram: validation, HTML safety, CLI and output contracts ────

class FlowDiagramTests(unittest.TestCase):
    def test_html_structure_and_no_js(self):
        source = flow_document(SPEC, embed_css=False)
        tags = Elements(source).tags
        self.assertEqual(sum(tag == "li" for tag, _ in tags), 5)
        self.assertEqual(sum(tag == "script" for tag, _ in tags), 0)
        self.assertIn('flow.css', source)
        self.assertIn('data-ui-theme="github-like"', source)

    def test_untrusted_text_is_escaped(self):
        hostile = '"><script>alert(1)</script>&'
        spec = {"title": hostile, "sources": [{"title": hostile}],
                "steps": [{"title": hostile, "note": hostile}]}
        source = flow_html(spec)
        self.assertNotIn("<script>", source)
        self.assertEqual(sum(tag == "li" for tag, _ in Elements(source).tags), 2)
        markdown = flow_mermaid(spec)
        self.assertEqual(markdown.count("S0 --> T0"), 1)
        self.assertIn("#quot;", markdown)
        self.assertIn("#lt;", markdown)

    def test_invalid_specs_fail(self):
        invalid = [None, {}, {"title": "x", "sources": [], "steps": [{"title": "ok"}]},
                   {"title": "x", "sources": [{"title": "z", "raw_html": "x"}], "steps": [{"title": "ok"}]},
                   {"title": "x", "sources": [{"title": "one" + chr(10) + "two"}], "steps": [{"title": "ok"}]},
                   {"title": "x", "sources": [{"title": "ok"}], "steps": [{"title": ""}]},
                   {"title": "x", "sources": [{"title": "ok"}] * 9, "steps": [{"title": "ok"}]}]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                validate_flow(item)

    def test_cli_mermaid(self):
        run = run_cli("ascii_artist.py", "flow-cards", "--format", "mermaid",
                      python_options=("-S",), stdin=json.dumps(SPEC), cwd=ROOT)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(run.stdout.startswith("```mermaid\nflowchart TB\n"))
        self.assertIn("T0 --> T1", run.stdout)

    def test_embed_css(self):
        source = flow_document(SPEC, embed_css=True)
        self.assertIn("<style>", source)
        self.assertIn("ui-flow-sources", source)
        self.assertNotIn("<script", source)
        self.assertNotIn('<link rel="stylesheet"', source)


# ──── patch: atomic field edits and Python/Node CLI parity ────

class FlowPatchTests(unittest.TestCase):
    def test_roundtrip_and_no_mutation(self):
        before = json.dumps(SPEC, ensure_ascii=False)
        patched = patch_flow(SPEC, [
            {"path": "/sources/0/note", "value": "入力・更新"},
            {"path": "/steps/0/title", "value": "統合 #120"},
        ])
        self.assertEqual(json.dumps(SPEC, ensure_ascii=False), before)
        self.assertEqual(patched["sources"][0]["note"], "入力・更新")
        self.assertEqual(validate_flow(patched), patched)
        self.assertEqual(patch_flow(patched, []), patched)

    def test_invalid_patch_is_atomic(self):
        before = json.dumps(SPEC, ensure_ascii=False)
        for operations in (
            [{"path": "/title", "value": "changed"}, {"path": "/steps/99/title", "value": "bad"}],
            [{"path": "/steps/01/title", "value": "bad"}],
            [{"path": "/sources/0/title", "value": "<script>\n"}],
            [{"path": "/steps/0/html", "value": "x"}],
            [{"path": "/steps/0/title", "value": 42}],
        ):
            with self.subTest(operations=operations), self.assertRaises(ValueError):
                patch_flow(SPEC, operations)
            self.assertEqual(json.dumps(SPEC, ensure_ascii=False), before)

    def test_cli_rejects_malformed_utf8_and_oversize(self):
        for raw in (b"\xff", b" " * (320 * 1024 + 1)):
            with self.subTest(size=len(raw)):
                for command in [[*runner, "flow-patch"] for runner in RUNNERS]:
                    result = subprocess.run(command, input=raw, capture_output=True, cwd=ROOT)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, b"")

    @unittest.skipUnless(NODE, "Node 26+ adapter unavailable")
    def test_python_node_cli_parity(self):
        data = {"spec": SPEC, "patch": [{"path": "/steps/1/note", "value": "CI完了"}]}
        input_text = json.dumps(data, ensure_ascii=False)
        py = run_cli("ascii_artist.py", "flow-patch", python_options=("-S",),
                     stdin=input_text, cwd=ROOT)
        node = subprocess.run([*NODE_ENTRY, "flow-patch"], input=input_text,
                              text=True, encoding="utf-8", capture_output=True, cwd=ROOT)
        self.assertEqual(py.returncode, 0, py.stderr)
        self.assertEqual(node.returncode, 0, node.stderr)
        self.assertEqual(json.loads(py.stdout), json.loads(node.stdout))

    def test_boundary_parity_and_atomic_invalid_batches(self):
        cases = [
            ("/steps/0/note", None, False),
            ("/sources_label", None, False),
            ("/steps/0/title", "😀" * 120, True),
            ("/steps/0/title", "😀" * 121, False),
            ("/sources/0/note", "😀" * 240, True),
            ("/sources/0/note", "😀" * 241, False),
            ("/steps/0/title", "﻿", True),
            ("/steps/0/title", "\x85", False),
            ("/steps/0/title", "　", False),
            ("/steps/0/title", "\ud800", False),
            ("/steps/0/title", "\udfff", False),
        ]
        for path, value, accepted in cases:
            operations = [{"path":"/title", "value":"first valid edit"}, {"path":path,"value":value}]
            original = json.dumps(SPEC)
            data = json.dumps(dict(spec=SPEC, patch=operations)).encode()
            with self.subTest(path=path, value=repr(value)):
                results = [subprocess.run([*runner, "flow-patch"], input=data, capture_output=True, cwd=ROOT)
                           for runner in RUNNERS]
                self.assertEqual([r.returncode for r in results], [0 if accepted else 2] * len(results))
                if accepted:
                    self.assertTrue(all(json.loads(r.stdout) == json.loads(results[0].stdout) for r in results))
                else:
                    self.assertEqual([r.stdout for r in results], [b""] * len(results))
                    with self.assertRaises(ValueError): patch_flow(SPEC, operations)
                self.assertEqual(json.dumps(SPEC), original)

    def test_native_clis_reject_invalid_utf8_inside_valid_json_and_bom(self):
        patch = json.dumps(dict(spec=SPEC, patch=[{"path":"/title","value":"MARKER"}])).encode()
        flow = json.dumps(SPEC).encode()
        for document, command in ((patch, "flow-patch"), (flow, "flow-cards")):
            invalid = document.replace(b'MARKER', b'\xff') if command.endswith('patch') else document.replace(b'"title":', b'"title":"\xff", "title":', 1)
            for raw in (invalid, b"\xef\xbb\xbf" + document):
                for runner in RUNNERS:
                    result = subprocess.run([*runner, command], input=raw, capture_output=True, cwd=ROOT)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, b"")


# ──── contract: migrated Node contracts and standalone single-file regressions ────

class CardFlowContractTests(unittest.TestCase):
    def test_mermaid_fan_in_and_all_steps(self):
        result = flow_mermaid(SPEC)
        self.assertTrue(result.startswith('```mermaid\nflowchart TB\n'))
        self.assertTrue(result.endswith('\n```\n'))
        for index in range(len(SPEC['sources'])):
            self.assertIn(f'S{index} --> T0', result)
        for index in range(1, len(SPEC['steps'])):
            self.assertIn(f'T{index-1} --> T{index}', result)

    def test_detached_canonical_and_unknown_shape(self):
        result = validate_flow(SPEC)
        result['sources'][0]['title'] = 'changed'
        self.assertNotEqual(result['sources'][0]['title'], SPEC['sources'][0]['title'])
        with self.assertRaises(ValueError):
            from_dict(SPEC)
        with self.assertRaises(ValueError):
            validate_flow({'nodes': [], 'edges': []})

    def test_patch_operation_bounds_and_paths(self):
        before = copy.deepcopy(SPEC)
        operation = {'path': '/title', 'value': 'changed'}
        self.assertEqual(patch_flow(SPEC, [operation] * 64)['title'], 'changed')
        invalid = [[operation] * 65, None, {}, [dict(operation, extra=1)]]
        for path in ('/steps/-1/title', '/steps/01/title', '/steps/１/title',
                     '/steps/1.0/title', '/steps/0/title/extra', '/nodes/0/title'):
            invalid.append([operation, {'path': path, 'value': 'bad'}])
        for batch in invalid:
            with self.subTest(batch=str(batch)[:100]), self.assertRaises(ValueError):
                patch_flow(SPEC, batch)
            self.assertEqual(SPEC, before)

    def test_stylesheet_is_in_memory_and_linked_output_explicit(self):
        for theme in ('modern', 'github-like'):
            css = flow_css(theme=theme)
            result = flow_document(SPEC, theme=theme)
            self.assertIn('<style>' + css + '</style>', result)
            self.assertNotIn('<link', result)
            self.assertNotIn('<script', result)
            self.assertIn('@media(max-width:520px)', css)
            self.assertIn('@media print', css)
        linked = flow_document(SPEC, embed_css=False, asset_base='assets')
        self.assertIn('href="assets/flow.css"', linked)
        self.assertNotIn('<style>', linked)
        for base in ('https://evil', '//evil', 'x?y', 'x#y', 'x\\y', 'x\x00y', 'x\ty', 'x"y'):
            with self.subTest(base=base), self.assertRaises(ValueError):
                flow_document(SPEC, asset_base=base)
        with self.assertRaises(ValueError):
            flow_css(theme='unknown')

    def test_single_file_stdlib_render_without_repo_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'ascii_artist.py'
            target.write_bytes((ROOT / 'ascii_artist.py').read_bytes())
            result = subprocess.run([sys.executable, '-I', '-S', str(target), 'flow-cards'],
                                    input=json.dumps(SPEC).encode(), capture_output=True, cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b'<style>', result.stdout)
            self.assertEqual(result.stdout.decode(), flow_document(SPEC))

    def test_python_node_render_and_budget_boundaries(self):
        env = dict(os.environ, ASCII_ARTIST_PYTHON=sys.executable)
        documents = [('flow-cards', SPEC, FLOW_MAX_INPUT),
                     ('flow-patch', {'spec': SPEC, 'patch': []}, FLOW_MAX_INPUT + FLOW_MAX_PATCH)]
        for command, document, budget in documents:
            raw = json.dumps(document).encode()
            for size, code in ((budget, 0), (budget + 1, 2)):
                data = raw + b' ' * (size - len(raw))
                outputs = []
                for runner in RUNNERS:
                    result = subprocess.run([*runner, command], input=data, capture_output=True, cwd=ROOT, env=env)
                    self.assertEqual(result.returncode, code, result.stderr)
                    if code:
                        self.assertEqual(result.stdout, b'')
                    outputs.append(result.stdout)
                self.assertTrue(all(output == outputs[0] for output in outputs))
        for fmt in ('html', 'fragment', 'mermaid'):
            results = [subprocess.run([*runner, 'flow-cards', '--format', fmt], input=json.dumps(SPEC).encode(),
                                      capture_output=True, cwd=ROOT, env=env)
                       for runner in RUNNERS]
            self.assertEqual([r.returncode for r in results], [0] * len(results))
            self.assertTrue(all(r.stdout == results[0].stdout for r in results))

    def test_deep_invalid_json_has_clean_failure(self):
        for runner in RUNNERS:
            for command in ('flow-cards', 'flow-patch'):
                result = subprocess.run([*runner, command], input=b'[' * 10000 + b']' * 10000,
                                        capture_output=True, cwd=ROOT)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, b'')
                self.assertNotIn(b'Traceback', result.stderr)

    def test_flow_cli_utf8_independent_of_stdout_locale(self):
        env = dict(os.environ, PYTHONIOENCODING="cp1252", ASCII_ARTIST_PYTHON=sys.executable)
        for command, document in (("flow-cards", SPEC), ("flow-patch", {"spec": SPEC, "patch": []})):
            for runner in RUNNERS:
                result = subprocess.run([*runner, command], input=json.dumps(document).encode("utf-8"),
                                        capture_output=True, cwd=ROOT, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = flow_document(SPEC) if command == "flow-cards" else json.dumps(validate_flow(SPEC), ensure_ascii=False) + "\n"
                self.assertEqual(result.stdout, expected.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
