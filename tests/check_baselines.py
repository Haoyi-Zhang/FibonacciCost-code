"""Exact owned-state checks for the scaling and maximum baseline claims."""
from __future__ import annotations
import argparse
import itertools
import json
import sys
import time
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from cascades import rebuild, distances
from families import make_task, changed_costs
from oracle import bellman


def check(task, old_costs, new_costs):
    graphs = task.abstractions()
    old, _ = rebuild(graphs, old_costs)
    old_sum = task.heuristic(old)
    gamma = min([Fraction(1)] + [Fraction(new, old) for new, old in zip(new_costs, old_costs) if old > 0])
    assert 0 <= gamma <= 1
    assert all(gamma * old <= new for old, new in zip(old_costs, new_costs))
    maximum = task.heuristic(tuple(distances(g, new_costs) for g in graphs), 'maximum')
    states = list(itertools.product(range(task.q), repeat=task.dims))
    ids = {state:index for index,state in enumerate(states)}
    edges = tuple((index,ids[target],label) for index,state in enumerate(states)
                  for label,target in task.successors(state))
    exact = bellman(len(states), (ids[task.goal],), edges, new_costs)
    scaled = [gamma * old_sum(state) for state in states]
    maxima = [maximum(state) for state in states]
    for values in (scaled, maxima):
        assert values[ids[task.goal]] == 0
        assert all(value <= distance for value,distance in zip(values,exact))
        assert all(values[source] <= new_costs[label]+values[target] for source,target,label in edges)
    return len(states), len(edges), str(gamma)


def main(output):
    if sys.flags.optimize:
        raise SystemExit('run without -O; assertions are checks')
    started = time.perf_counter()
    states = edges = cases = 0
    for family in ('independent', 'coupled'):
        for seed in range(4):
            task = make_task(family, 2, seed)
            for mode in ('sparse', 'mixed'):
                count, scanned, _ = check(task, task.costs, changed_costs(task, mode, seed))
                states += count; edges += scanned; cases += 1
    zero_controls = []
    for family in ('independent', 'coupled'):
        task = make_task(family, 2, 0)
        for name, old in (('all old costs zero', (0,)*len(task.costs)),
                          ('some old costs zero', tuple(0 if i%2==0 else value for i,value in enumerate(task.costs)))):
            count, scanned, gamma = check(task, old, task.costs)
            zero_controls.append(dict(family=family, control=name, states=count, gamma=gamma))
    report = dict(status='passed', ordinary_cases=cases,
                  ordinary_state_checks_per_baseline=states,
                  ordinary_consistency_edges_per_baseline=edges,
                  zero_cost_controls=zero_controls,
                  scope='exact finite owned states and edges; scale uses Fraction, concrete oracle uses Bellman--Ford',
                  wall_seconds=time.perf_counter()-started)
    output = Path(output)
    if output.exists():
        raise SystemExit('output exists; choose a fresh result path')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    main(parser.parse_args().out)
