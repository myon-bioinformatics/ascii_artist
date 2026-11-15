"""📈 DAG frontier: stdlib layering parity against the original full-scan definition, and the benchmark guard.

The benchmark parity checks must run even with Python optimization enabled (``vendor/fleet_check.run_main``).
"""
import json, random, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_artist as art
from vendor import fleet_check as fleet


def reference(value):
    ids = [node.id for node in value.nodes]
    remaining = set(ids)
    layers = []
    while remaining:
        layer = [node for node in ids if node in remaining and not any(
            edge.target == node and edge.source in remaining for edge in value.edges)]
        if not layer:
            raise ValueError('cycle')
        layers.append(layer)
        remaining.difference_update(layer)
    return layers


class FrontierTests(unittest.TestCase):
    def test_random_dags_preserve_input_order_and_duplicate_edges(self):
        rng = random.Random(20261104)
        for size in range(40):
            ids = [str(i) for i in range(size)]
            edges = [(str(i), str(j)) for i in range(size) for j in range(i+1,size)
                     if rng.randrange(5) == 0]
            edges += edges[:5]
            rng.shuffle(ids)
            rng.shuffle(edges)
            value = art.diagram(ids, edges)
            self.assertEqual(art._topological_layers(value), reference(value))

    def test_chain_wide_and_empty(self):
        for ids, edges in (([], []), (['a','b','c'], []),
                           (['c','b','a'], [('a','b'),('b','c')])):
            value = art.diagram(ids, edges)
            self.assertEqual(art._topological_layers(value), reference(value))

    def test_rejects_invalid_graphs(self):
        for ids, edges in ((['a','a'], []), (['a'], [('a','a')]),
                           (['a'], [('a','missing')]),
                           (['a','b'], [('a','b'),('b','a')])):
            with self.assertRaises(ValueError):
                art.diagram(ids, edges)


class BenchmarkParityTests(unittest.TestCase):
    def run_benchmark(self, optimized, mismatch):
        patch = (
            "g['subprocess'].check_output = lambda *a, **kw: "
            "b'def diagram(*args): return None\\ndef _topological_layers(value): return [[\"expected\"]]\\n'\n"
            f"g['current']._topological_layers = lambda value: {([] if mismatch else [['expected']])!r}\n"
        )
        return fleet.run_main(ROOT, "scripts/benchmark_dag_frontier.py", patch, optimized=optimized, timeout=30)

    def test_mismatch_exits_without_publishing_measurements(self):
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                result = self.run_benchmark(optimized, mismatch=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("DAG layering parity mismatch: current", result.stderr)
                self.assertIn("nodes=256, shape=chain, repetition=0", result.stderr)

    def test_matching_results_still_publish_measurements(self):
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                result = self.run_benchmark(optimized, mismatch=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(len(report["records"]), 4)
                for record in report["records"]:
                    for samples in record["samples_ns"].values():
                        self.assertEqual(len(samples), 7)


if __name__ == '__main__':
    unittest.main()
