"""Portable, untimed exact checks for the Fibonacci proof and its quantities.

The interval-envelope functions over-approximate residual transitions; actual
task witnesses are separately checked against label-major Bellman--Ford.
For tiny Boolean witnesses, exhaustive action-subset coverage computes the
concrete optimum: actions only set bits, commute and are idempotent, and their
costs are nonnegative, so repeating or reordering them cannot improve a plan.
No external command, dataset, planner, archived source or resource shim is used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cascades import rebuild, update
from families import fibonacci, fibonacci_amplifier_task
from oracle import partition
from check_support_envelope import (
    check_induction_arithmetic, check_reachable_envelope,
    check_transition_inequalities,
)
from check_rational_model import (
    check_fractional_onset, check_fractional_reuse_characterization,
    check_fractional_support_bounds,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def subset_optimum(task, costs, start):
    """Exact bounded set-cover enumeration, not SCP or A* agreement."""
    require(task.q == 2, 'Boolean task required')
    require(all(step == 1 for action in task.actions for _, step in action),
            'subset enumeration requires idempotent bit-setting actions')
    full = (1 << task.dims) - 1
    initial = sum(bit << j for j, bit in enumerate(start))
    masks = [sum(1 << j for j, _ in action) for action in task.actions]
    best = None
    for selected in range(1 << len(task.actions)):
        covered, cost = initial, 0
        for label, mask in enumerate(masks):
            if selected & (1 << label):
                covered |= mask
                cost += costs[label]
        if covered == full and (best is None or cost < best):
            best = cost
    require(best is not None, 'witness must be solvable')
    return best


def check_witnesses():
    records = []
    tiny_optimum_checks = 0
    for k in (0, 1, 2, 3, 4, 8, 16, 32, 64):
        task, terminal_label = fibonacci_amplifier_task(k)
        graphs = task.abstractions()
        changed_costs = (0,) + task.costs[1:]
        old, _ = rebuild(graphs, task.costs)
        new, work = update(graphs, old, changed_costs)
        for costs, tables in ((task.costs, old), (changed_costs, new)):
            require(tuple((t.offered, t.h, t.allocated) for t in tables)
                    == partition(graphs, costs), 'independent partition mismatch')

        expected = [-1]
        a = b = 1
        for _ in range(k):
            expected.extend((a, -a))
            a, b = a + b, a
        expected.extend((a, -a))
        differences = [right.h[0] - left.h[0] for left, right in zip(old, new)]
        require(differences == expected, 'initializer/carry/cleanup mismatch')
        support_sizes = []
        for left, right in zip(old, new):
            old_residual = tuple(r - s for r, s in zip(left.offered, left.allocated))
            new_residual = tuple(r - s for r, s in zip(right.offered, right.allocated))
            require(all(0 <= r <= c for r, c in zip(old_residual, task.costs)),
                    'old residual leaves original cost range')
            require(all(0 <= r <= c for r, c in zip(new_residual, changed_costs)),
                    'new residual leaves updated cost range')
            delta = tuple(n - o for o, n in zip(old_residual, new_residual))
            support_sizes.append(sum(value != 0 for value in delta))
        amplitude = fibonacci(k + 3)
        require([(label, value) for label, value in enumerate(delta) if value]
                == [(terminal_label, amplitude)], 'wrong terminal difference')
        require(max(support_sizes) <= 2, 'support-two hypothesis fails')
        require(work.changed_entries == 2 * k + 3, 'a table did not change')
        incidence = max(len(action) for action in task.actions)
        width = max(len(graph.support) for graph in graphs)
        require(incidence <= 3 and width <= 3, 'incidence bound fails')
        require(len(task.costs) == 2 * k + 4 and max(task.costs) == amplitude,
                'label count or largest cost mismatch')

        # A concrete plan certificate: d followed by all fresh z labels.
        plan = (0, *range(3, len(task.costs), 2))
        reached = list(task.start)
        for label in plan:
            for coordinate, step in task.actions[label]:
                reached[coordinate] = min(1, reached[coordinate] + step)
        require(tuple(reached) == task.goal, 'displayed plan misses a goal')
        old_h = task.heuristic(old)(task.start)
        new_h = task.heuristic(new)(task.start)
        require(sum(task.costs[label] for label in plan) == old_h,
                'old plan cost does not match heuristic lower bound')
        require(sum(changed_costs[label] for label in plan) == new_h == old_h - 1,
                'new plan cost/cancellation mismatch')

        if k <= 3:
            require(subset_optimum(task, task.costs, task.start) == old_h,
                    'independent old concrete optimum mismatch')
            require(subset_optimum(task, changed_costs, task.start) == new_h,
                    'independent new concrete optimum mismatch')
            tiny_optimum_checks += 2
        records.append({
            'k': k, 'tables': task.dims, 'labels': len(task.costs),
            'residual_amplitude': amplitude, 'largest_input_cost': max(task.costs),
            'largest_cost_bits': amplitude.bit_length(),
            'max_intermediate_difference_support': max(support_sizes),
            'max_action_incidence': incidence, 'max_advancing_set_size': width,
            'changed_tables': work.changed_entries,
            'table_value_differences': differences,
            'all_zero_start_old_heuristic': old_h,
            'all_zero_start_new_heuristic': new_h,
            'old_matching_plan_cost': old_h, 'new_matching_plan_cost': new_h,
            'independent_subset_optimum_checked': k <= 3,
        })

    task, _ = fibonacci_amplifier_task(0)
    old, _ = rebuild(task.abstractions(), task.costs)
    new_costs = (0,) + task.costs[1:]
    new, _ = rebuild(task.abstractions(), new_costs)
    state = (1, 0, 1)
    contrast = {
        'k': 0, 'state': list(state),
        'old_heuristic': task.heuristic(old)(state),
        'new_heuristic': task.heuristic(new)(state),
        'old_optimum': subset_optimum(task, task.costs, state),
        'new_optimum': subset_optimum(task, new_costs, state),
    }
    require((contrast['old_heuristic'], contrast['new_heuristic'],
             contrast['old_optimum'], contrast['new_optimum']) == (0, 1, 1, 1),
            'state-level contrast mismatch')
    return records, tiny_optimum_checks + 2, contrast


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new JSON result path')
    args = parser.parse_args()
    require(not sys.flags.optimize, 'run without -O; imported checks use assertions')
    require(not args.out.exists(), 'refusing to overwrite existing evidence')
    transitions, transition_counts = check_transition_inequalities(8)
    induction_checks = check_induction_arithmetic(1000)
    envelope, visits = check_reachable_envelope(17)
    fractional_onset = check_fractional_onset()
    fractional_support = check_fractional_support_bounds()
    fractional_reuse = check_fractional_reuse_characterization()
    witnesses, optimum_checks, contrast = check_witnesses()
    result = {
        'status': 'passed', 'scope': 'portable untimed exact arithmetic; no timing reproduction',
        'python_version': sys.version.split()[0], 'platform': sys.platform,
        'integer_transition_checks': transitions, 'integer_transition_counts': transition_counts,
        'induction_arithmetic_checks': induction_checks, 'induction_max_k': 1000,
        'reachable_envelope': envelope, 'reachable_transition_visits': visits,
        **fractional_onset, **fractional_support, **fractional_reuse,
        'actual_fibonacci_witnesses': witnesses,
        'independent_tiny_concrete_optimum_checks': optimum_checks,
        'heuristic_optimum_contrast': contrast,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    summary = {key: value for key, value in result.items()
               if key not in ('actual_fibonacci_witnesses', 'reachable_envelope')}
    summary['actual_fibonacci_witness_count'] = len(witnesses)
    summary['odd_depth_maxima'] = [row['maximum_infinity_norm'] for row in envelope
                                 if row['tables'] % 2]
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
