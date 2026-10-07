"""Untimed current/historical saturation contract; no archived code imports."""
from copy import deepcopy
from dataclasses import asdict
from itertools import product
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
import cascades as c
import reproduce
import saturation_benchmark as study
from families import make_task, relay_task, changed_costs


def literal_saturation(graph, h):
    # Label-major independent reference, including every edge and zero floor.
    return tuple(max([0] + [h[u] - h[v] for u, v, a in graph.edges if a == label])
                 for label in range(graph.labels))


def reference_partition(graphs, offered):
    # Synchronous Bellman--Ford, not candidate Dijkstra/reuse/saturation.
    residual, result = tuple(offered), []
    for graph in graphs:
        h = [None] * graph.n
        for goal in graph.goals:
            h[goal] = 0
        for _ in range(graph.n - 1):
            old = h[:]
            for u, v, label in graph.edges:
                if old[v] is not None:
                    value = residual[label] + old[v]
                    if h[u] is None or value < h[u]:
                        h[u] = value
            if h == old:
                break
        if any(value is None for value in h):
            raise ValueError('reference graph has an unreachable state')
        h = tuple(h)
        allocation = literal_saturation(graph, h)
        result.append((residual, h, allocation))
        residual = tuple(value - used for value, used in zip(residual, allocation))
    return tuple(result)


def typed(value):
    if type(value) is dict:
        return (dict, tuple((key, typed(item)) for key, item in sorted(value.items())))
    if type(value) in (tuple, list):
        return (type(value), tuple(typed(item) for item in value))
    return (type(value), value)


def same_work_except_validated_scans(all_work, indexed_work, all_count, indexed_count):
    left, right = asdict(all_work), asdict(indexed_work)
    if type(left['saturation_edge_scans']) is not int or left['saturation_edge_scans'] != all_count:
        raise AssertionError('wrong current all-edge count')
    if type(right['saturation_edge_scans']) is not int or right['saturation_edge_scans'] != indexed_count:
        raise AssertionError('wrong historical indexed count')
    right['saturation_edge_scans'] = all_count
    if typed(left) != typed(right):
        raise AssertionError('changed non-saturation work field')


class SaturationContractTests(unittest.TestCase):
    def test_historical_raw_bindings_without_imports(self):
        bindings = {
            'results/saturation/sources/cascades.py':
                '2ba4323e6f1cc07e490711deaedb2f01f905ebe59cd39346786a1a488656b912',
            'results/saturation/sources/saturation_benchmark.py':
                '186acde40f1ffaff1b8551bd88532f6bd86669809717dae0483b7d30e3d00e92',
            'results/saturation/saturation.json':
                '5a16b0274386b66d1c79513756c0ee90e4d5d25edbba246e78801c70ef9a2c56',
            'inputs/campaign.json':
                'a909793d26a27ccf9b5622d4fc1cc2ed649c76a2665e0ab3c72b319f95032ce1',
        }
        for name, expected in bindings.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)

    def test_literal_grid_and_both_independent_scan_counts(self):
        checked = 0
        for targets in product(range(3), repeat=6):
            graph = c.Graph(3, 2, (2,), tuple((u, targets[2*u+a], a)
                                            for u in range(3) for a in range(2)))
            indexed = study.HistoricalIndexedSaturation((graph,))
            for heights in product((-1, 0, 1), repeat=3):
                full_work, old_work = c.Work(saturation_edge_scans=7), c.Work(saturation_edge_scans=7)
                self.assertEqual(c.saturation(graph, heights, full_work), literal_saturation(graph, heights))
                self.assertEqual(indexed(graph, heights, old_work), literal_saturation(graph, heights))
                same_work_except_validated_scans(full_work, old_work, 7 + len(graph.edges),
                                                7 + sum(u != v for u, v, _ in graph.edges))
                checked += 1
        self.assertEqual(checked, 19683)
        empty = c.Graph(1, 2, (0,), ())
        self.assertEqual(study.HistoricalIndexedSaturation((empty,))(empty, (-9,)), (0, 0))
        foreign = c.Graph(1, 2, (0,), ())
        with self.assertRaisesRegex(ValueError, 'not prepared'):
            study.HistoricalIndexedSaturation((empty,))(foreign, (0,))

    def test_ordered_all_fields_negative_controls_and_kernel_restoration(self):
        chain = (c.Graph(3, 2, (2,), ((0, 1, 0), (1, 0, 0), (0, 2, 1), (2, 2, 1))),
                 c.Graph(2, 2, (1,), ((0, 1, 0), (0, 1, 1), (0, 0, 0))))
        indexed = study.HistoricalIndexedSaturation(chain)
        current = c.saturation
        old, _ = c.rebuild(chain, (0, 1))
        constructor = c.build_table

        def exercise(kernel, operation):
            built = []
            def tracked(graph, offered, work):
                built.append(graph)
                return constructor(graph, offered, work)
            with study.selected_kernel(kernel), patch.object(c, 'build_table', side_effect=tracked):
                tables, work = operation()
            self.assertIs(c.saturation, current)
            return tables, work, built

        checked = 0
        for costs in product(range(3), repeat=2):
            for method, count_changes in product(('full', 'exact', 'support'), (False, True)):
                operation = (lambda: c.rebuild(chain, costs)) if method == 'full' else (
                    lambda: c.update(chain, old, costs, method, count_changes=count_changes))
                full, fw, built = exercise(current, operation)
                historic, hw, old_built = exercise(indexed, operation)
                self.assertEqual(typed(tuple((t.offered, t.h, t.allocated) for t in full)),
                                 typed(reference_partition(chain, costs)))
                self.assertEqual(typed(tuple(asdict(t) for t in full)), typed(tuple(asdict(t) for t in historic)))
                self.assertEqual(tuple(map(id, built)), tuple(map(id, old_built)))
                same_work_except_validated_scans(fw, hw, sum(len(g.edges) for g in built),
                                                sum(u != v for g in built for u, v, _ in g.edges))
                checked += 1
        self.assertEqual(checked, 54)
        zero_work = c.Work()
        self.assertFalse(c.unchanged(chain[0], old[0], (0, 2), zero_work))
        self.assertEqual(zero_work.reachability_failures, 1)
        feasibility = c.Work()
        valid, _ = c.rebuild(chain, (1, 1))
        self.assertFalse(c.unchanged(chain[0], valid[0], (0, 0), feasibility))
        self.assertEqual(feasibility.feasibility_failures, 1)
        for kernel in (current, indexed):
            with study.selected_kernel(kernel):
                for costs in ((True, 0), (-1, 0), (1.0, 0), (), (1, 2, 3)):
                    with self.assertRaises(ValueError):
                        c.rebuild(chain, costs)
                with self.assertRaisesRegex(ValueError, 'graph/table mismatch'):
                    c.update(chain, (), (1, 1))
                with self.assertRaisesRegex(ValueError, 'unknown method'):
                    c.update(chain, old, (1, 1), 'invalid')
        with self.assertRaisesRegex(RuntimeError, 'owned failure'):
            with study.selected_kernel(indexed):
                raise RuntimeError('owned failure')
        self.assertIs(c.saturation, current)

    def test_reconciliation_keeps_each_counter_and_scientific_field(self):
        self.assertEqual(reproduce.MEASUREMENTS, {
            'seconds', 'cpu_seconds', 'wall_seconds', 'peak_rss_kib',
            'setup_seconds', 'update_seconds', 'total_seconds'})
        record = {'costs': [0, 2], 'work': asdict(c.Work(saturation_edge_scans=6)),
                  'search': {'status': 'solved', 'cost': 2, 'expansions': 3, 'generated': 4, 'seconds': 1.0},
                  'table': {'offered': [0, 2], 'h': [2, 0], 'allocated': [0, 2]}}
        for key in record['work']:
            changed = deepcopy(record)
            changed['work'][key] += 1
            self.assertNotEqual(reproduce.stable(record), reproduce.stable(changed), key)
        for key, value in (('status', 'limit'), ('cost', None), ('expansions', 9), ('generated', 10)):
            changed = deepcopy(record)
            changed['search'][key] = value
            self.assertNotEqual(reproduce.stable(record), reproduce.stable(changed))
        for key in ('offered', 'h', 'allocated'):
            changed = deepcopy(record)
            changed['table'][key][0] += 1
            self.assertNotEqual(reproduce.stable(record), reproduce.stable(changed))
        changed = deepcopy(record)
        changed['costs'][0] = 1
        self.assertNotEqual(reproduce.stable(record), reproduce.stable(changed))
        changed = deepcopy(record)
        changed['search']['seconds'] = 999
        self.assertEqual(reproduce.stable(record), reproduce.stable(changed))
        full, historic = c.Work(saturation_edge_scans=6), c.Work(saturation_edge_scans=2)
        same_work_except_validated_scans(full, historic, 6, 2)
        for changed, expected_error in ((c.Work(saturation_edge_scans=5), 'current'),
                                        (c.Work(saturation_edge_scans=True), 'current')):
            with self.assertRaisesRegex(AssertionError, expected_error):
                same_work_except_validated_scans(changed, historic, 6, 2)
        with self.assertRaisesRegex(AssertionError, 'historical'):
            same_work_except_validated_scans(full, c.Work(saturation_edge_scans=1), 6, 2)
        with self.assertRaisesRegex(AssertionError, 'non-saturation'):
            same_work_except_validated_scans(full, c.Work(saturation_edge_scans=2, reused_tables=1), 6, 2)

    def test_frozen_cohort_scan_counts_from_inputs_not_timings(self):
        config = json.loads((ROOT / 'inputs/campaign.json').read_text(encoding='utf-8'))
        retained = json.loads((ROOT / 'results/saturation/saturation.json').read_text(encoding='utf-8'))
        specs = {spec['id']: spec for spec in config['cases']}
        self.assertEqual(len(specs), 60)
        self.assertEqual(retained['cases'], 60)
        self.assertEqual(retained['timed_searches'], 2640)
        self.assertEqual(retained['random_saturation_agreements'], 2000)
        self.assertEqual({r['case'] for r in retained['records']}, set(specs))
        self.assertEqual(len(retained['records']), 60)
        sample_count = 0
        for record in retained['records']:
            spec = specs[record['case']]
            task = relay_task(spec['m'], spec['delta']) if spec['family'] == 'relay' else (
                make_task(spec['family'], spec['q'], spec['seed']))
            graphs = task.abstractions()
            costs = changed_costs(task, spec['mode'], spec.get('seed', 0), spec.get('delta'))
            old, fresh = reference_partition(graphs, task.costs), reference_partition(graphs, costs)
            rebuilt = tuple(g for g, left, right in zip(graphs, old, fresh) if left[1] != right[1])
            expected = {'all-full': sum(len(g.edges) for g in graphs),
                        'elided-full': sum(u != v for g in graphs for u, v, _ in g.edges),
                        'all-exact': sum(len(g.edges) for g in rebuilt),
                        'elided-exact': sum(u != v for g in rebuilt for u, v, _ in g.edges)}
            self.assertEqual(record['family'], spec['family'])
            self.assertEqual(typed(record['edges']), typed(expected['all-full']))
            self.assertEqual(typed(record['active_edges']), typed(expected['elided-full']))
            samples = record['samples']
            self.assertEqual(len(samples), 44)
            self.assertEqual({(s['arm'], s['pair']) for s in samples}, set(product(expected, range(11))))
            outcome = None
            for sample in samples:
                self.assertEqual(typed(sample['saturation_edge_scans']), typed(expected[sample['arm']]))
                self.assertEqual(typed(sample['batch']), typed(16))
                search = sample['search']
                self.assertEqual(set(search), {'status', 'cost', 'expansions', 'generated', 'seconds'})
                self.assertEqual(search['status'], 'solved')
                for name in ('cost', 'expansions', 'generated'):
                    self.assertIs(type(search[name]), int)
                    self.assertGreaterEqual(search[name], 0)
                scientific = typed({key: value for key, value in search.items() if key != 'seconds'})
                if outcome is None:
                    outcome = scientific
                self.assertEqual(scientific, outcome)
                sample_count += 1
        self.assertEqual(sample_count, 2640)


if __name__ == '__main__':
    unittest.main()
