"""Exact updates for ordered, nonnegative saturated cost partitioning.

Finite goal-reachable labelled graphs; all numeric costs are nonnegative integers.
Python integers are unbounded. No external packages or planning systems are used.
The shortest-path optimality test is standard; its labelled composition and the
relay family are the objects of this study, not a new shortest-path algorithm.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from heapq import heappop, heappush
from collections import deque
from typing import Callable, Sequence
import time

@dataclass(frozen=True)
class Graph:
    n: int
    labels: int
    goals: tuple[int, ...]
    edges: tuple[tuple[int, int, int], ...]  # (source, target, label)
    rev: tuple[tuple[tuple[int, int], ...], ...] = field(init=False, repr=False)
    support: tuple[int, ...] = field(init=False)

    def __post_init__(self):
        if self.n < 1 or self.labels < 1 or not self.goals:
            raise ValueError('nonempty graph, label set and goal set required')
        if any(not 0 <= g < self.n for g in self.goals):
            raise ValueError('goal outside graph')
        rev = [[] for _ in range(self.n)]
        support = set()
        for u, v, a in self.edges:
            if not (0 <= u < self.n and 0 <= v < self.n and 0 <= a < self.labels):
                raise ValueError('invalid transition')
            if u != v:
                rev[v].append((u, a))
                support.add(a)
        object.__setattr__(self, 'rev', tuple(tuple(es) for es in rev))
        object.__setattr__(self, 'support', tuple(sorted(support)))

@dataclass
class Work:
    rebuilt_tables: int = 0
    reused_tables: int = 0
    written_entries: int = 0
    certificate_entries: int = 0  # full table size when a reachability check runs
    distance_edge_scans: int = 0
    saturation_edge_scans: int = 0
    certificate_edge_scans: int = 0
    changed_entries: int = 0
    support_skips: int = 0
    decrease_skips: int = 0
    tight_skips: int = 0
    feasibility_failures: int = 0
    reachability_failures: int = 0

@dataclass(frozen=True)
class Table:
    offered: tuple[int, ...]
    h: tuple[int, ...]
    allocated: tuple[int, ...]


def validate_costs(costs: Sequence[int], labels: int) -> tuple[int, ...]:
    c = tuple(costs)
    if len(c) != labels or any(type(x) is not int or x < 0 for x in c):
        raise ValueError('one nonnegative integer cost per label is required')
    return c


def distances(g: Graph, costs: Sequence[int], work: Work | None = None) -> tuple[int, ...]:
    c = validate_costs(costs, g.labels)
    return _distances_validated(g, c, work)


def _distances_validated(g: Graph, c: tuple[int, ...], work: Work | None) -> tuple[int, ...]:
    """Reverse Dijkstra for a cost tuple admitted by the public caller."""
    d: list[int | None] = [None] * g.n
    heap = []
    for goal in set(g.goals):
        d[goal] = 0
        heappush(heap, (0, goal))
    while heap:
        dv, v = heappop(heap)
        if d[v] != dv:
            continue
        for u, a in g.rev[v]:
            if work is not None:
                work.distance_edge_scans += 1
            cand = dv + c[a]
            if d[u] is None or cand < d[u]:
                d[u] = cand
                heappush(heap, (cand, u))
    if any(x is None for x in d):
        raise ValueError('unreachable abstract states are outside the finite-distance model')
    return tuple(d)  # type: ignore[arg-type]


def saturation(g: Graph, h: Sequence[int], work: Work | None = None) -> tuple[int, ...]:
    sat = [0] * g.labels
    for u, v, a in g.edges:
        if work is not None:
            work.saturation_edge_scans += 1
        sat[a] = max(sat[a], h[u] - h[v])
    return tuple(sat)


def build_table(g: Graph, offered: Sequence[int], work: Work) -> Table:
    offered = validate_costs(offered, g.labels)
    h = _distances_validated(g, offered, work)
    sat = saturation(g, h, work)
    if any(x > y for x, y in zip(sat, offered)):
        raise AssertionError('saturation must be feasible')
    work.rebuilt_tables += 1
    work.written_entries += g.n
    return Table(offered, h, sat)


def unchanged(g: Graph, old: Table, offered: Sequence[int], work: Work) -> bool:
    """Necessary and sufficient test that old.h is still the exact distance table.

    The first two exits are sufficient shortcuts to the same exact predicate.
    Reverse reachability includes NEW tight edges and handles zero-cost SCCs.
    """
    c = validate_costs(offered, g.labels)
    changed = [a for a in g.support if c[a] != old.offered[a]]
    if not changed:
        work.support_skips += 1
        return True
    if any(c[a] < old.allocated[a] for a in changed):
        work.feasibility_failures += 1
        return False
    if all(c[a] <= old.offered[a] for a in changed):
        work.decrease_skips += 1
        return True
    work.certificate_entries += g.n
    seen = set(g.goals)
    queue = deque(g.goals)
    while queue:
        v = queue.popleft()
        for u, a in g.rev[v]:
            work.certificate_edge_scans += 1
            if u not in seen and old.h[u] == c[a] + old.h[v]:
                seen.add(u)
                queue.append(u)
    if len(seen) == g.n:
        work.tight_skips += 1
        return True
    work.reachability_failures += 1
    return False


def rebuild(graphs: Sequence[Graph], costs: Sequence[int]) -> tuple[tuple[Table, ...], Work]:
    if not graphs:
        raise ValueError('at least one abstraction required')
    residual = validate_costs(costs, graphs[0].labels)
    tables, work = [], Work()
    for g in graphs:
        t = build_table(g, residual, work)
        tables.append(t)
        residual = tuple(r - a for r, a in zip(residual, t.allocated))
    return tuple(tables), work


def update(graphs: Sequence[Graph], old: Sequence[Table], costs: Sequence[int],
           method: str = 'exact', *, count_changes: bool = True) -> tuple[tuple[Table, ...], Work]:
    if len(graphs) != len(old) or not graphs:
        raise ValueError('graph/table mismatch')
    if method not in ('exact', 'support'):
        raise ValueError('unknown method')
    residual = validate_costs(costs, graphs[0].labels)
    tables, work = [], Work()
    for g, t in zip(graphs, old):
        if method == 'exact':
            reuse = unchanged(g, t, residual, work)
        else:
            reuse = all(residual[a] == t.offered[a] for a in g.support)
            work.support_skips += int(reuse)
        if reuse:
            new = Table(residual, t.h, t.allocated)
            work.reused_tables += 1
        else:
            new = build_table(g, residual, work)
        if count_changes:
            work.changed_entries += sum(x != y for x, y in zip(new.h, t.h))
        tables.append(new)
        residual = tuple(r - a for r, a in zip(residual, new.allocated))
    return tuple(tables), work


def relay(m: int) -> tuple[tuple[Graph, ...], tuple[int, ...]]:
    """Projection of m Boolean goals, action a_j sets its adjacent goals to one.
    All other labels project to self-loops. Pattern i has advancing labels i,i+1.
    """
    if m < 1:
        raise ValueError('m must be positive')
    graphs = []
    for i in range(m):
        edges = tuple((s, 1 if a in (i, i + 1) else s, a)
                      for s in range(2) for a in range(m + 1))
        graphs.append(Graph(2, m + 1, (1,), edges))
    return tuple(graphs), (1,) + (2,) * m


def astar(start: tuple[int, ...], goal: tuple[int, ...],
          successors: Callable[[tuple[int, ...]], Sequence[tuple[int, tuple[int, ...]]]],
          costs: Sequence[int], heuristic: Callable[[tuple[int, ...]], int],
          *, scale_num: int = 1, scale_den: int = 1,
          max_expansions: int = 100_000, seconds: float = 8.0) -> dict:
    """Integer-key A*: tie order (f,-g,state); permits reopening and zero costs.
    A rational scaling n/d is evaluated using d*g+n*h, never floating point.
    A* time includes heuristic evaluation; no search state is shared by methods.
    """
    begin = time.perf_counter()
    heap = [(scale_num * heuristic(start), 0, start)]
    best = {start: 0}
    expanded, generated = 0, 1
    while heap:
        _, ng, s = heappop(heap)
        gs = -ng
        if best.get(s) != gs:
            continue
        if s == goal:
            return dict(status='solved', cost=gs, expansions=expanded, generated=generated,
                        seconds=time.perf_counter() - begin)
        if expanded >= max_expansions or (expanded % 128 == 0 and time.perf_counter()-begin >= seconds):
            return dict(status='limit', cost=None, expansions=expanded, generated=generated,
                        seconds=time.perf_counter() - begin)
        expanded += 1
        for a, t in successors(s):
            cand = gs + costs[a]
            if t not in best or cand < best[t]:
                best[t] = cand
                heappush(heap, (scale_den * cand + scale_num * heuristic(t), -cand, t))
                generated += 1
    return dict(status='unsolvable', cost=None, expansions=expanded, generated=generated,
                seconds=time.perf_counter() - begin)
