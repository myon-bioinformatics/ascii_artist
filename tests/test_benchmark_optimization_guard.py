from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OptimizedBenchmarkTests(unittest.TestCase):
    def test_incorrect_layers_fail_without_success_json(self):
        code = '''
import runpy, sys, types, ascii_artist
reference = types.ModuleType('guard_reference')
reference.diagram = ascii_artist.diagram
reference._topological_layers = ascii_artist._topological_layers
sys.modules['guard_reference'] = reference
ns = runpy.run_path('scripts/benchmark_dag_frontier.py')['main'].__globals__
ns['subprocess'].check_output = lambda *a, **kw: b'from guard_reference import diagram, _topological_layers'
ascii_artist._topological_layers = lambda diagram: []
ns['main']()
'''
        result = subprocess.run([sys.executable, '-O', '-S', '-c', code],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('layer mismatch', result.stderr)
        self.assertEqual(result.stdout, '')
