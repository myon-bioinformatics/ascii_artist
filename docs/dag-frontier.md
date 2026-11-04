# DAG frontier performance

DAG validation now uses a deque instead of repeatedly deleting the first element
of a list. Layer construction visits only newly ready nodes instead of scanning
all nodes once per layer. Each next frontier is sorted by original node position,
so sibling order, duplicate-edge handling, validation errors and public output
remain unchanged. No dependency or API changes.

Validation is O(V+E); layer construction is O(V+E+sum(frontier sorting costs)).
Previously a chain required O(V squared) membership/indegree checks in layering.
No bit-width reduction, build acceleration or package-size improvement is claimed.

```sh
python -S -m unittest discover -s tests -p test_dag_frontier.py -v
python -S scripts/benchmark_dag_frontier.py
```

The benchmark requires git and the pinned baseline commit retained in history.
It executes both versions against identical graphs and verifies identical layers.
One warmup plus seven alternating timed repetitions; CPython 3.12.14, Linux x86_64.
Raw samples and the baseline SHA are in `dag-frontier-measurement.json`.

| Nodes | Shape | Baseline median | Frontier median |
|---:|---|---:|---:|
| 256 | chain | 1.681 ms | 0.258 ms |
| 256 | no edges | 0.097 ms | 0.115 ms |
| 2048 | chain | 147.007 ms | 3.456 ms |
| 2048 | no edges | 1.567 ms | 1.372 ms |

These are isolated layer-computation timings including validation, not full render
or CI timings. Small wide graphs can be slightly slower. Tests compare layers
with a separate set-based definition on fixed-seed random DAGs, shuffled node/edge
orders, duplicate edges, chains, empty/wide graphs, and invalid references/cycles.
