"""Stdlib DAG frontier parity against the original full-scan layer definition."""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ascii_artist as art


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


if __name__ == '__main__':
    unittest.main()
