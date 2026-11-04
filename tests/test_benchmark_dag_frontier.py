"""Benchmark parity checks must run even with Python optimization enabled."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_dag_frontier.py"


class BenchmarkParityTests(unittest.TestCase):
    def run_benchmark(self, optimized, mismatch):
        source = f"""
import runpy
from unittest.mock import patch

benchmark = runpy.run_path({str(SCRIPT)!r})
baseline_source = b'def diagram(*args): return None\\ndef _topological_layers(value): return [["expected"]]\\n'
with patch.object(benchmark['subprocess'], 'check_output', return_value=baseline_source), \\
     patch.object(benchmark['current'], '_topological_layers', return_value={([] if mismatch else [['expected']])!r}):
    benchmark['main']()
"""
        return subprocess.run(
            [sys.executable, "-S", *(["-O"] if optimized else []), "-c", source],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )

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


if __name__ == "__main__":
    unittest.main()
