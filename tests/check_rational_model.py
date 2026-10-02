"""Exact-rational finite checks for the real-valued statements.

The production artifact intentionally accepts only nonnegative Python integers.
The proofs, however, are stated for finite nonnegative real costs.  This checker
uses :class:`fractions.Fraction` and does not import the candidate implementation.
It targets three places where an integer-only test suite could otherwise conceal
an integrality assumption:

* the two-table unit-decrease onset bound;
* the support-two one-step inequalities used by the Fibonacci envelope; and
* the tight-goal-path characterization of exact distance-table reuse.

Finite checks are regression evidence, not substitutes for the symbolic proofs in
``proofs/results.tex``.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from collections import deque
from fractions import Fraction
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from platform_support import require_supported_environment
resource = require_supported_environment('tests/check_rational_model.py')

Q = Fraction


def infinity_norm(values: Iterable[Fraction]) -> Fraction:
    return max((abs(value) for value in values), default=Q(0))


def l1_norm(values: Iterable[Fraction]) -> Fraction:
    return sum((abs(value) for value in values), Q(0))


def residual_map(values: tuple[Fraction, ...], selected: tuple[int, ...]) -> tuple[Fraction, ...]:
    """Subtract the selected minimum, exactly as a Boolean singleton table does."""
    if not selected:
        raise ValueError("selected set must be nonempty")
    minimum = min(values[index] for index in selected)
    chosen = set(selected)
    return tuple(value - minimum if index in chosen else value for index, value in enumerate(values))


def vector_type(values: tuple[Fraction, ...]) -> str:
    nonzero = [value for value in values if value]
    if len(nonzero) <= 1 or all(value > 0 for value in nonzero) or all(value < 0 for value in nonzero):
        return "P"
    if len(nonzero) == 2 and nonzero[0] * nonzero[1] < 0:
        return "N"
    raise AssertionError(f"not a support-two P/N vector: {values!r}")


def masks(width: int) -> list[tuple[int, ...]]:
    return [tuple(index for index in range(width) if mask & (1 << index))
            for mask in range(1, 1 << width)]


def check_fractional_onset() -> dict[str, int]:
    """Check Lemma 4 on a half-integer grid using actual minimum maps."""
    grid = tuple(Q(n, 2) for n in range(5))  # 0, 1/2, 1, 3/2, 2
    selections = masks(4)
    changed_inputs = 0
    first_stage_checks = 0
    second_stage_checks = 0
    boundary_ties = 0

    for old in itertools.product(grid, repeat=4):
        for changed in range(4):
            if old[changed] < 1:
                continue
            new = list(old)
            new[changed] -= 1
            new_tuple = tuple(new)
            changed_inputs += 1
            for first in selections:
                old_first = residual_map(old, first)
                new_first = residual_map(new_tuple, first)
                difference = tuple(n - o for o, n in zip(old_first, new_first))
                assert infinity_norm(difference) <= 1
                assert max(difference) - min(difference) <= 1
                assert min(difference) <= 0 <= max(difference)
                first_stage_checks += 1
                old_minimisers = [i for i in first if old[i] == min(old[j] for j in first)]
                new_minimisers = [i for i in first if new_tuple[i] == min(new_tuple[j] for j in first)]
                boundary_ties += int(len(old_minimisers) > 1 or len(new_minimisers) > 1)
                for second in selections:
                    old_second = residual_map(old_first, second)
                    new_second = residual_map(new_first, second)
                    difference_second = tuple(n - o for o, n in zip(old_second, new_second))
                    assert infinity_norm(difference_second) <= 1, (
                        old, changed, first, second, difference_second
                    )
                    second_stage_checks += 1

    return {
        "rational_unit_decrease_inputs": changed_inputs,
        "rational_first_stage_checks": first_stage_checks,
        "rational_two_stage_checks": second_stage_checks,
        "cases_with_old_or_new_minimum_tie": boundary_ties,
    }


def canonical(values: Iterable[Fraction]) -> tuple[Fraction, ...]:
    return tuple(sorted((value for value in values if value)))


def fractional_overapprox_successors(state: tuple[Fraction, ...]) -> set[tuple[Fraction, ...]]:
    """Quarter-grid interval over-approximation of support-two difference maps."""
    values = list(state)
    result: set[tuple[Fraction, ...]] = set()
    for mask in range(1 << len(values)):
        selected = [index for index in range(len(values)) if mask & (1 << index)]
        for zero_count in range(3):
            if not selected and zero_count == 0:
                continue
            selected_values = [values[index] for index in selected] + [Q(0)] * zero_count
            lower, upper = min(selected_values), max(selected_values)
            # Every quarter-grid point in the minimum-change interval.
            start = lower * 4
            stop = upper * 4
            assert start.denominator == stop.denominator == 1
            for numerator in range(start.numerator, stop.numerator + 1):
                mu = Q(numerator, 4)
                outgoing = [
                    value - mu if index in selected else value
                    for index, value in enumerate(values)
                ]
                outgoing.extend([-mu] * zero_count)
                successor = canonical(outgoing)
                if len(successor) <= 2:
                    result.add(successor)
    return result


def check_fractional_support_bounds(limit_quarters: int = 8) -> dict[str, object]:
    """Check all four Lemma 5 rows on a symmetric quarter-grid."""
    values = [Q(n, 4) for n in range(-limit_quarters, limit_quarters + 1) if n]
    states: set[tuple[Fraction, ...]] = {()}
    states.update((value,) for value in values)
    states.update(canonical((left, right)) for left in values for right in values)
    states = {state for state in states if len(state) <= 2}

    transition_counts = {"P->P": 0, "P->N": 0, "N->P": 0, "N->N": 0}
    for state in sorted(states):
        source_type = vector_type(state)
        source_max = infinity_norm(state)
        source_l1 = l1_norm(state)
        for successor in fractional_overapprox_successors(state):
            target_type = vector_type(successor)
            target_max = infinity_norm(successor)
            target_l1 = l1_norm(successor)
            transition = f"{source_type}->{target_type}"
            if transition == "P->P":
                valid = target_max <= source_max and target_l1 <= 2 * source_max
            elif transition == "P->N":
                valid = target_max <= source_max and target_l1 <= source_l1
            elif transition == "N->P":
                valid = target_max <= source_l1 and target_l1 <= source_l1 + source_max
            elif transition == "N->N":
                valid = target_max <= source_l1 and target_l1 <= source_l1
            else:  # pragma: no cover
                raise AssertionError(transition)
            assert valid, (state, successor, transition)
            transition_counts[transition] += 1

    return {
        "fractional_support_states": len(states),
        "fractional_transition_inequality_checks": sum(transition_counts.values()),
        "fractional_transition_counts": transition_counts,
        "fractional_grid_denominator": 4,
        "fractional_grid_max_absolute_value": str(Q(limit_quarters, 4)),
    }


def graph_reaches_goal(successors: tuple[tuple[int, int], ...], goal: int = 2) -> bool:
    reverse = [[] for _ in range(3)]
    for source, destinations in enumerate(successors):
        for target in destinations:
            reverse[target].append(source)
    seen = {goal}
    queue = deque([goal])
    while queue:
        vertex = queue.popleft()
        for predecessor in reverse[vertex]:
            if predecessor not in seen:
                seen.add(predecessor)
                queue.append(predecessor)
    return len(seen) == 3


def rational_distances(successors: tuple[tuple[int, int], ...], costs: tuple[Fraction, Fraction],
                       goal: int = 2) -> tuple[Fraction, Fraction, Fraction]:
    """Synchronous Bellman--Ford on a fixed three-state deterministic graph."""
    distance: list[Fraction | None] = [None, None, None]
    distance[goal] = Q(0)
    for _ in range(2):
        previous = distance[:]
        for source in range(3):
            candidates = [previous[target] + costs[label]
                          for label, target in enumerate(successors[source])
                          if previous[target] is not None]
            if source == goal:
                candidates.append(Q(0))
            if candidates:
                best = min(candidates)
                if distance[source] is None or best < distance[source]:
                    distance[source] = best
    if any(value is None for value in distance):
        raise AssertionError("topologically goal-reachable graph has no finite distance")
    return tuple(distance)  # type: ignore[return-value]


def rational_saturation(successors: tuple[tuple[int, int], ...],
                        distances: tuple[Fraction, Fraction, Fraction]) -> tuple[Fraction, Fraction]:
    result = [Q(0), Q(0)]
    for source, destinations in enumerate(successors):
        for label, target in enumerate(destinations):
            result[label] = max(result[label], distances[source] - distances[target])
    return tuple(result)  # type: ignore[return-value]


def tight_goal_reachability(successors: tuple[tuple[int, int], ...],
                            offered: tuple[Fraction, Fraction],
                            old_distances: tuple[Fraction, Fraction, Fraction],
                            goal: int = 2) -> bool:
    reverse = [[] for _ in range(3)]
    for source, destinations in enumerate(successors):
        for label, target in enumerate(destinations):
            if old_distances[source] == offered[label] + old_distances[target]:
                reverse[target].append(source)
    seen = {goal}
    queue = deque([goal])
    while queue:
        vertex = queue.popleft()
        for predecessor in reverse[vertex]:
            if predecessor not in seen:
                seen.add(predecessor)
                queue.append(predecessor)
    return len(seen) == 3


def check_fractional_reuse_characterization() -> dict[str, int]:
    """Exhaust the 3-state/2-label topology set on a rational cost grid."""
    cost_values = (Q(0), Q(1, 2), Q(1))
    cost_vectors = tuple(itertools.product(cost_values, repeat=2))
    graph_count = 0
    pair_count = 0
    unchanged_count = 0
    changed_count = 0
    feasible_but_not_exact = 0

    # successors[source][label]; 3^(3*2) total deterministic labelled graphs.
    for flat in itertools.product(range(3), repeat=6):
        successors = tuple((flat[2 * source], flat[2 * source + 1]) for source in range(3))
        if not graph_reaches_goal(successors):
            continue
        graph_count += 1
        for old_costs in cost_vectors:
            old_distances = rational_distances(successors, old_costs)
            allocation = rational_saturation(successors, old_distances)
            assert all(allocated <= offered for allocated, offered in zip(allocation, old_costs))
            for new_costs in cost_vectors:
                new_distances = rational_distances(successors, new_costs)
                exact = new_distances == old_distances
                feasible = all(allocated <= offered for allocated, offered in zip(allocation, new_costs))
                certificate = feasible and tight_goal_reachability(
                    successors, new_costs, old_distances
                )
                assert certificate == exact, (
                    successors, old_costs, new_costs, old_distances,
                    new_distances, allocation, feasible, certificate
                )
                pair_count += 1
                unchanged_count += int(exact)
                changed_count += int(not exact)
                feasible_but_not_exact += int(feasible and not exact)

    assert graph_count == 495
    assert pair_count == 40_095
    return {
        "rational_reuse_graphs": graph_count,
        "rational_reuse_old_new_cost_pairs": pair_count,
        "rational_reuse_exactly_unchanged": unchanged_count,
        "rational_reuse_changed": changed_count,
        "rational_reuse_feasible_but_not_exact": feasible_but_not_exact,
    }


def main(output: str) -> None:
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    onset = check_fractional_onset()
    support = check_fractional_support_bounds()
    reuse = check_fractional_reuse_characterization()
    result = {
        "status": "passed",
        "scope": (
            "exact Fraction finite grids; symbolic real-valued proofs remain in "
            "proofs/results.tex; candidate integer implementation is not imported"
        ),
        **onset,
        **support,
        **reuse,
        "cpu_seconds": time.process_time() - cpu_start,
        "wall_seconds": time.perf_counter() - wall_start,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "workers": 1,
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="results/rational_checks.json")
    arguments = parser.parse_args()
    main(arguments.out)
