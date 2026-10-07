"""Optional matched current all-edge and historical self-loop-elision study.

Graph construction is outside timing. Full rebuild and exact reuse both use
the selected kernel. All table, allocation and search outputs must agree.
The frozen Linux campaign remains a separate all-edge implementation baseline.
This driver does not replay the frozen Windows timings. Their exact original
sources are retained under results/saturation/sources, not imported here.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import random
import statistics
import sys
import time
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
import cascades as c
from families import make_task, relay_task, changed_costs


def all_edges(graph, h, work=None):
    sat = [0] * graph.labels
    for u, v, label in graph.edges:
        if work is not None:
            work.saturation_edge_scans += 1
        sat[label] = max(sat[label], h[u] - h[v])
    return tuple(sat)


class HistoricalIndexedSaturation:
    """Explicit non-self-edge index for this optional study, not production.

    Index construction is outside every measured arm. Retaining the graph
    objects prevents identity reuse; no Graph.active_edges interface is needed.
    """
    def __init__(self, graphs):
        self._index = {id(g): (g, tuple(e for e in g.edges if e[0] != e[1]))
                       for g in graphs}

    def edges_for(self, graph):
        entry = self._index.get(id(graph))
        if entry is None or entry[0] is not graph:
            raise ValueError('graph was not prepared for the historical index')
        return entry[1]

    def __call__(self, graph, h, work=None):
        sat = [0] * graph.labels
        for u, v, label in self.edges_for(graph):
            if work is not None:
                work.saturation_edge_scans += 1
            sat[label] = max(sat[label], h[u] - h[v])
        return tuple(sat)


@contextmanager
def selected_kernel(kernel):
    """Restore the production function even on an unsuccessful optional arm."""
    original = c.saturation
    try:
        c.saturation = kernel
        yield
    finally:
        c.saturation = original


def check_random():
    rng = random.Random(582713)
    for _ in range(2000):
        n, labels = rng.randrange(1, 10), rng.randrange(1, 8)
        edges = tuple((rng.randrange(n), rng.randrange(n), rng.randrange(labels))
                      for _ in range(rng.randrange(0, 100)))
        graph = c.Graph(n, labels, (n-1,), edges)
        h = tuple(rng.randrange(-100, 101) for _ in range(n))
        historical = HistoricalIndexedSaturation((graph,))
        assert historical(graph, h) == c.saturation(graph, h) == all_edges(graph, h)
    return 2000


def pin():
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        process = kernel.GetCurrentProcess()
        allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
        assert kernel.GetProcessAffinityMask(process, ctypes.byref(allowed), ctypes.byref(system))
        selected = allowed.value & -allowed.value
        assert kernel.SetProcessAffinityMask(process, selected)
        actual = ctypes.c_size_t()
        assert kernel.GetProcessAffinityMask(process, ctypes.byref(actual), ctypes.byref(system))
        assert actual.value == selected
        return hex(selected)
    selected = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {selected})
    assert os.sched_getaffinity(0) == {selected}
    return hex(1 << selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'select a fresh measurement directory'
    args.out.mkdir(parents=True)
    affinity = pin()
    current_all_edges = c.saturation
    assert check_random() == 2000
    config = json.loads((ROOT / 'inputs/campaign.json').read_text())
    records = []
    for index, spec in enumerate(config['cases']):
        task = (relay_task(spec['m'], spec['delta']) if spec['family'] == 'relay'
                else make_task(spec['family'], spec['q'], spec['seed']))
        costs = changed_costs(task, spec['mode'], spec.get('seed', 0), spec.get('delta'))
        graphs = task.abstractions()
        historical = HistoricalIndexedSaturation(graphs)
        old, _ = c.rebuild(graphs, task.costs)
        reference, _ = c.rebuild(graphs, costs)
        expected = tuple((t.h, t.allocated) for t in reference)
        samples = []
        arms = (('all-full', current_all_edges, 'full'), ('elided-full', historical, 'full'),
                ('all-exact', current_all_edges, 'exact'), ('elided-exact', historical, 'exact'))
        # Same old tables and inputs in all arms; rotate order over eleven pairs.
        for rep in range(11):
            shift = (index + rep) % len(arms)
            for name, kernel, method in arms[shift:] + arms[:shift]:
                with selected_kernel(kernel):
                    tick = time.perf_counter_ns()
                    for _ in range(16):
                        tables, work = (c.rebuild(graphs, costs) if method == 'full'
                                        else c.update(graphs, old, costs, count_changes=False))
                        heuristic = task.heuristic(tables)
                    update_ns = time.perf_counter_ns() - tick
                assert tuple((t.h, t.allocated) for t in tables) == expected
                outcome = c.astar(task.start, task.goal, task.successors, costs, heuristic)
                assert outcome['status'] == 'solved'
                samples.append(dict(arm=name, pair=rep, batch=16, update_ns=update_ns,
                                    search=outcome, saturation_edge_scans=work.saturation_edge_scans))
        outcomes = {(s['search']['cost'], s['search']['expansions'], s['search']['generated']) for s in samples}
        assert len(outcomes) == 1
        ratios = {}
        for method in ('full', 'exact'):
            pairs = [next(s for s in samples if s['pair']==rep and s['arm']=='all-'+method)['update_ns'] /
                     next(s for s in samples if s['pair']==rep and s['arm']=='elided-'+method)['update_ns']
                     for rep in range(11)]
            ratios[method] = dict(median=statistics.median(pairs), minimum=min(pairs),
                                  maximum=max(pairs), slower_pairs=sum(x < 1 for x in pairs))
        records.append(dict(case=spec['id'], family=spec['family'], ratios=ratios,
                            edges=sum(len(g.edges) for g in graphs),
                            active_edges=sum(len(historical.edges_for(g)) for g in graphs), samples=samples))
    groups = {}
    for family in ('independent', 'coupled', 'relay', 'all'):
        rows = [r for r in records if family == 'all' or r['family']==family]
        groups[family] = {method:dict(
            case_median_range=[min(r['ratios'][method]['median'] for r in rows), max(r['ratios'][method]['median'] for r in rows)],
            slower_cases=[r['case'] for r in rows if r['ratios'][method]['median'] < 1])
            for method in ('full', 'exact')}
    result = dict(cases=60, random_saturation_agreements=2000, timed_searches=60*11*4,
                  environment=dict(os=platform.platform(), python=platform.python_version(),
                                   cpu=os.environ.get('PROCESSOR_IDENTIFIER', platform.processor()), affinity=affinity),
                  scope='Matched implementation kernel timings; construction excluded, both algorithms use the same selected kernel. No production planner claim.',
                  groups=groups, records=records)
    (args.out/'saturation.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(cases=60, timed_searches=result['timed_searches'], groups=groups), indent=2))


if __name__ == '__main__':
    main()
