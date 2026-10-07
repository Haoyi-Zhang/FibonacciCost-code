"""Portable exact regression for current all-edge saturation and exact reuse."""
import itertools
import json
from pathlib import Path
import random
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from cascades import Graph, Work, Table, distances, saturation, unchanged, rebuild, update
from oracle import bellman, partition

graphs = comparisons = 0
costs = list(itertools.product(range(3), repeat=2))
for targets in itertools.product(range(3), repeat=6):
    graph = Graph(3, 2, (2,), tuple((u, targets[2*u+a], a) for u in range(3) for a in range(2)))
    try:
        bellman(3, (2,), graph.edges, (1, 1))
    except ValueError:
        continue
    graphs += 1
    values = {c:bellman(3, (2,), graph.edges, c) for c in costs}
    for offered in costs:
        h = distances(graph, offered)
        expected = tuple(max([0]+[h[u]-h[v] for u,v,a in graph.edges if a==label]) for label in range(2))
        work = Work()
        assert saturation(graph, h, work) == expected
        assert work.saturation_edge_scans == len(graph.edges)
        old = Table(offered, h, expected)
        for changed in costs:
            assert unchanged(graph, old, changed, Work()) == (h == values[changed])
            comparisons += 1
rng = random.Random(91827)
chain_updates = 0
for _ in range(120):
    seq = []
    for _ in range(5):
        edges = [(u, rng.randrange(6), a) for u in range(6) for a in range(4)]
        edges.extend((u, 5, 4) for u in range(6))
        seq.append(Graph(6, 5, (5,), tuple(edges)))
    old, _ = rebuild(seq, tuple(rng.randrange(7) for _ in range(5)))
    for _ in range(12):
        changed = tuple(rng.randrange(7) for _ in range(5))
        tables, _ = update(seq, old, changed)
        assert tuple((t.offered,t.h,t.allocated) for t in tables) == partition(seq, changed)
        old = tables
        chain_updates += 1
print(json.dumps(dict(goal_reachable_graphs=graphs, reuse_comparisons=comparisons,
                      sequential_oracle_agreements=chain_updates, passed=True)))
