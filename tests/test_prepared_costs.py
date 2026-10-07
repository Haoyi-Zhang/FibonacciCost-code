"""Portable exact regressions for public admission and prepared table costs."""
from dataclasses import asdict
from itertools import product
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import cascades as c
from oracle import bellman, partition


def graphs(module=c):
    for targets in product(range(3), repeat=6):
        graph = module.Graph(3, 2, (2,), tuple((u, targets[2 * u + a], a) for u in range(3) for a in range(2)))
        try:
            bellman(3, (2,), graph.edges, (1, 1))
        except ValueError:
            continue
        yield graph


class PreparedCostTests(unittest.TestCase):
    def test_complete_graph_grid_against_independent_oracle(self):
        count = 0
        for graph in graphs():
            for costs in product(range(3), repeat=2):
                work = c.Work()
                table = c.build_table(graph, list(costs), work)
                self.assertEqual((table.offered, table.h, table.allocated), partition((graph,), costs)[0])
                direct_work = c.Work()
                self.assertEqual(c.distances(graph, costs, direct_work), table.h)
                self.assertEqual(work.distance_edge_scans, direct_work.distance_edge_scans)
                self.assertEqual(work.saturation_edge_scans, len(graph.edges))
                self.assertEqual((work.rebuilt_tables, work.written_entries), (1, graph.n))
                count += 1
        self.assertEqual(count, 4455)

    def test_each_public_boundary_validates_once_and_snapshots(self):
        graph = c.Graph(2, 4, (1, 1), ((0, 1, 0), (0, 0, 3)))
        for entry in ('distances', 'build_table'):
            with patch.object(c, 'validate_costs', wraps=c.validate_costs) as admitted:
                costs = [2, 0, 0, 999]
                work = c.Work()
                result = getattr(c, entry)(graph, costs, work)
                self.assertEqual(admitted.call_count, 1)
                costs[0] = 7
                self.assertEqual(result.h if entry == 'build_table' else result, (2, 0))
                if entry == 'build_table':
                    self.assertEqual(result.offered, (2, 0, 0, 999))
        for costs in ((1, -1, 0, 0), (1, True, 0, 0), (1, 1.0, 0, 0), (1,), (), (1, 2, 3, 4, 5)):
            for entry in (c.distances, c.build_table):
                work = c.Work()
                with self.assertRaisesRegex(ValueError, 'one nonnegative integer cost per label is required'):
                    entry(graph, costs, work)
                self.assertEqual(asdict(work), asdict(c.Work()))
        unreachable = c.Graph(2, 1, (1,), ((0, 0, 0),))
        for entry in (c.distances, c.build_table):
            with self.assertRaisesRegex(ValueError, 'one nonnegative integer cost per label is required'):
                entry(unreachable, (True,), c.Work())
            with self.assertRaisesRegex(ValueError, 'unreachable abstract states'):
                entry(unreachable, (0,), c.Work())

    def test_ordered_updates_all_modes_and_tight_cycle_control(self):
        chain = (c.Graph(3, 2, (2,), ((0, 1, 0), (1, 0, 0), (0, 2, 1))),
                 c.Graph(2, 2, (1,), ((0, 1, 0), (0, 1, 1))))
        old, _ = c.rebuild(chain, (0, 1))
        for costs in product(range(3), repeat=2):
            expected = partition(chain, costs)
            fresh, _ = c.rebuild(chain, costs)
            self.assertEqual(tuple((t.offered, t.h, t.allocated) for t in fresh), expected)
            for method in ('exact', 'support'):
                updated, _ = c.update(chain, old, costs, method)
                self.assertEqual(updated, fresh)
            old = fresh
        one, _ = c.rebuild(chain[:1], (0, 1))
        work = c.Work()
        self.assertFalse(c.unchanged(chain[0], one[0], (0, 2), work))
        self.assertEqual(work.reachability_failures, 1)


if __name__ == '__main__':
    unittest.main()
