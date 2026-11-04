"""Compare against the recorded git baseline; emits raw timings and parity."""
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_artist as current


def main():
    baseline_sha = '8e2eb10e4349aba92bfbd8a5f9b2e37a0d2e0546'
    source = subprocess.check_output(['git', 'show', baseline_sha + ':ascii_artist.py'], cwd=ROOT)
    baseline = types.ModuleType('ascii_artist_baseline')
    sys.modules[baseline.__name__] = baseline
    exec(compile(source, 'baseline/ascii_artist.py', 'exec'), baseline.__dict__)
    records = []
    for size in (256, 2048):
        for shape in ('chain', 'wide'):
            ids = [str(i) for i in range(size)]
            edges = [(str(i), str(i+1)) for i in range(size-1)] if shape == 'chain' else []
            values = {name: module.diagram(ids, edges) for name, module in
                      (('baseline', baseline), ('current', current))}
            samples = {'baseline': [], 'current': []}
            expected = baseline._topological_layers(values['baseline'])
            for repetition in range(8):
                order = ('baseline', 'current') if repetition % 2 else ('current', 'baseline')
                for name in order:
                    module = baseline if name == 'baseline' else current
                    start = time.perf_counter_ns()
                    result = module._topological_layers(values[name])
                    elapsed = time.perf_counter_ns() - start
                    assert result == expected
                    if repetition:
                        samples[name].append(elapsed)
            records.append({'nodes':size, 'shape':shape, 'samples_ns':samples,
                            'median_ns':{k:statistics.median(v) for k,v in samples.items()}})
    print(json.dumps({'baseline_sha':baseline_sha, 'python':sys.version,
                      'records':records, 'dependencies_added':0}, indent=2))


if __name__ == '__main__':
    main()
