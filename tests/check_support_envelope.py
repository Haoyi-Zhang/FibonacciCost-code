"""Finite arithmetic checks for the support-two Fibonacci envelope.

This checker is deliberately independent of the planning-task generators.  It
uses only the difference update

    e_i = d_i - mu  (i in B),   e_i = d_i  (i not in B),

where min_B d <= mu <= max_B d.  Allowing every integer mu in that interval is
an over-approximation of realizable minimum changes, so passing the checks is a
strong finite sanity test; the unbounded real-valued claim is proved in the
supplement, not by enumeration.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from platform_support import require_supported_environment
resource = require_supported_environment('tests/check_support_envelope.py')


def fibonacci(index: int) -> int:
    if index < 1:
        raise ValueError('Fibonacci index must be positive')
    left, right = 0, 1
    for _ in range(index):
        left, right = right, left + right
    return left


def normalize(values: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    """Drop zero coordinates and quotient by coordinate permutations."""
    return tuple(sorted(value for value in values if value != 0))


def vector_type(state: tuple[int, ...]) -> str:
    if not state or all(value > 0 for value in state) or all(value < 0 for value in state):
        return 'P'
    if len(state) == 2 and state[0] < 0 < state[1]:
        return 'N'
    raise AssertionError(f'noncanonical support-two state: {state!r}')


def measures(state: tuple[int, ...]) -> tuple[int, int]:
    return max((abs(value) for value in state), default=0), sum(abs(value) for value in state)


def overapprox_successors(state: tuple[int, ...]) -> set[tuple[int, ...]]:
    """Enumerate support-two successors in the interval over-approximation.

    There are at most two nonzero coordinates.  Selecting more than two zero
    coordinates can only violate the outgoing support bound when mu != 0, and
    is redundant when mu == 0, so zero_count in {0,1,2} is complete here.
    """
    values = list(state)
    result: set[tuple[int, ...]] = set()
    for mask in range(1 << len(values)):
        selected = [index for index in range(len(values)) if mask >> index & 1]
        for zero_count in range(3):
            if not selected and zero_count == 0:
                continue
            selected_values = [values[index] for index in selected] + [0] * zero_count
            lower, upper = min(selected_values), max(selected_values)
            for mu in range(lower, upper + 1):
                outgoing = [
                    value - mu if index in selected else value
                    for index, value in enumerate(values)
                ]
                outgoing.extend([-mu] * zero_count)
                successor = normalize(outgoing)
                if len(successor) <= 2:
                    result.add(successor)
    return result


def check_transition_inequalities(limit: int) -> tuple[int, dict[str, int]]:
    """Check the four one-step inequalities on a symmetric integer grid."""
    states = {()}
    for first in range(-limit, limit + 1):
        if first:
            states.add((first,))
        for second in range(first, limit + 1):
            candidate = normalize((first, second))
            if len(candidate) <= 2:
                states.add(candidate)

    checked = 0
    by_transition = {'P->P': 0, 'P->N': 0, 'N->P': 0, 'N->N': 0}
    for state in sorted(states):
        source_type = vector_type(state)
        source_max, source_l1 = measures(state)
        for successor in overapprox_successors(state):
            target_type = vector_type(successor)
            target_max, target_l1 = measures(successor)
            transition = f'{source_type}->{target_type}'
            if transition == 'P->P':
                valid = target_max <= source_max and target_l1 <= 2 * source_max
            elif transition == 'P->N':
                valid = target_max <= source_max and target_l1 <= source_l1
            elif transition == 'N->P':
                valid = target_max <= source_l1 and target_l1 <= source_l1 + source_max
            elif transition == 'N->N':
                valid = target_max <= source_l1 and target_l1 <= source_l1
            else:  # pragma: no cover - vector_type rules make this unreachable
                raise AssertionError(transition)
            assert valid, (state, successor, transition, (source_max, source_l1), (target_max, target_l1))
            by_transition[transition] += 1
            checked += 1
    return checked, by_transition


def check_induction_arithmetic(max_k: int) -> int:
    """Check every scalar Fibonacci inequality used by the parity induction."""
    checks = 0
    for k in range(max_k + 1):
        # Odd-to-even steps.
        assert 2 * fibonacci(k + 2) <= fibonacci(k + 4)
        assert 4 * fibonacci(k + 2) <= fibonacci(k + 5)
        assert fibonacci(k + 4) <= 2 * fibonacci(k + 3)
        # Even-to-odd steps.
        assert fibonacci(k + 4) <= 2 * fibonacci(k + 3)
        assert 2 * fibonacci(k + 3) <= fibonacci(k + 5)
        assert 4 * fibonacci(k + 3) <= fibonacci(k + 6)
        checks += 6
    return checks


def check_reachable_envelope(horizon: int) -> tuple[list[dict[str, int | bool]], int]:
    """Enumerate an over-approximating reachable set from one unit decrease."""
    reachable = {(-1,)}
    rows: list[dict[str, int | bool]] = []
    transition_visits = 0
    for tables in range(1, horizon + 1):
        following: set[tuple[int, ...]] = set()
        for state in reachable:
            successors = overapprox_successors(state)
            transition_visits += len(successors)
            following.update(successors)
        reachable = following
        maximum = max(max((abs(value) for value in state), default=0) for state in reachable)
        row: dict[str, int | bool] = {
            'tables': tables,
            'reachable_normalized_states': len(reachable),
            'maximum_infinity_norm': maximum,
        }
        if tables % 2:
            k = (tables - 1) // 2
            expected = fibonacci(k + 2)
            row['proved_odd_stage_bound'] = expected
            row['bound_attained_in_overapproximation'] = maximum == expected
            assert maximum == expected, (tables, maximum, expected)
        rows.append(row)
    return rows, transition_visits


def main(output: str, limit: int, horizon: int, max_k: int) -> None:
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    transition_checks, by_transition = check_transition_inequalities(limit)
    induction_checks = check_induction_arithmetic(max_k)
    envelope, transition_visits = check_reachable_envelope(horizon)
    result = {
        'status': 'passed',
        'scope': 'finite integer over-approximation; symbolic proof is in proofs/results.tex',
        'transition_grid_limit': limit,
        'transition_inequality_checks': transition_checks,
        'transition_counts': by_transition,
        'induction_arithmetic_checks': induction_checks,
        'induction_max_k': max_k,
        'reachable_horizon_tables': horizon,
        'reachable_transition_visits': transition_visits,
        'reachable_envelope': envelope,
        'cpu_seconds': time.process_time() - cpu_start,
        'wall_seconds': time.perf_counter() - wall_start,
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'workers': 1,
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'reachable_envelope'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='results/support_envelope.json')
    parser.add_argument('--limit', type=int, default=8)
    parser.add_argument('--horizon', type=int, default=17)
    parser.add_argument('--max-k', type=int, default=1000)
    arguments = parser.parse_args()
    main(arguments.out, arguments.limit, arguments.horizon, arguments.max_k)
