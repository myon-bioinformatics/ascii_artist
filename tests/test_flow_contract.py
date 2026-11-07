"""Additional migrated Node contracts and standalone single-file regressions."""
import copy, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from flow_test_support import NODE

from ascii_artist import (FLOW_MAX_INPUT, FLOW_MAX_PATCH, flow_css, flow_document,
                          flow_html, flow_mermaid, from_dict, patch_flow, validate_flow)

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / 'examples/pr-flow.json').read_text(encoding="utf-8"))


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
                for runner in ([[sys.executable, '-S', 'ascii_artist.py']] + ([[NODE, 'ascii_artist.cjs']] if NODE else [])):
                    result = subprocess.run([*runner, command], input=data, capture_output=True, cwd=ROOT, env=env)
                    self.assertEqual(result.returncode, code, result.stderr)
                    if code:
                        self.assertEqual(result.stdout, b'')
                    outputs.append(result.stdout)
                self.assertTrue(all(output == outputs[0] for output in outputs))
        for fmt in ('html', 'fragment', 'mermaid'):
            results = [subprocess.run([*runner, 'flow-cards', '--format', fmt], input=json.dumps(SPEC).encode(),
                                      capture_output=True, cwd=ROOT, env=env)
                       for runner in ([[sys.executable, '-S', 'ascii_artist.py']] + ([[NODE, 'ascii_artist.cjs']] if NODE else []))]
            self.assertEqual([r.returncode for r in results], [0] * len(results))
            self.assertTrue(all(r.stdout == results[0].stdout for r in results))

    def test_deep_invalid_json_has_clean_failure(self):
        for runner in ([[sys.executable, '-S', 'ascii_artist.py']] + ([[NODE, 'ascii_artist.cjs']] if NODE else [])):
            for command in ('flow-cards', 'flow-patch'):
                result = subprocess.run([*runner, command], input=b'[' * 10000 + b']' * 10000,
                                        capture_output=True, cwd=ROOT)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, b'')
                self.assertNotIn(b'Traceback', result.stderr)

    def test_flow_cli_utf8_independent_of_stdout_locale(self):
        env = dict(os.environ, PYTHONIOENCODING="cp1252", ASCII_ARTIST_PYTHON=sys.executable)
        for command, document in (("flow-cards", SPEC), ("flow-patch", {"spec": SPEC, "patch": []})):
            for runner in ([[sys.executable, '-S', 'ascii_artist.py']] + ([[NODE, 'ascii_artist.cjs']] if NODE else [])):
                result = subprocess.run([*runner, command], input=json.dumps(document).encode("utf-8"),
                                        capture_output=True, cwd=ROOT, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = flow_document(SPEC) if command == "flow-cards" else json.dumps(validate_flow(SPEC), ensure_ascii=False) + "\n"
                self.assertEqual(result.stdout, expected.encode("utf-8"))
