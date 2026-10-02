"""Exact checks for the tight Fibonacci support-two construction; one worker."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from platform_support import require_supported_environment
resource = require_supported_environment('tests/check_amplification.py')
from cascades import rebuild, update
from oracle import partition
from families import fibonacci, fibonacci_amplifier_task


def expected_table_differences(k):
    values = [-1]
    A = B = 1
    for _ in range(k):
        values.extend((A, -A))
        A, B = A + B, A
    values.extend((A, -A))
    return values


def main(out):
    start = time.process_time()
    wall = time.perf_counter()
    records = []
    for k in (0, 1, 2, 3, 4, 8, 16, 32, 64):
        task, last = fibonacci_amplifier_task(k)
        graphs = task.abstractions()
        new_costs = (0,) + task.costs[1:]
        old, _ = rebuild(graphs, task.costs)
        fresh, work = update(graphs, old, new_costs)
        independent = partition(graphs, new_costs)
        assert [(t.offered, t.h, t.allocated) for t in fresh] == list(independent)

        table_differences = [nt.h[0] - ot.h[0] for ot, nt in zip(old, fresh)]
        assert table_differences == expected_table_differences(k)

        support_sizes = []
        for ot, nt in zip(old, fresh):
            old_residual = tuple(x - y for x, y in zip(ot.offered, ot.allocated))
            new_residual = tuple(x - y for x, y in zip(nt.offered, nt.allocated))
            support_sizes.append(sum(x != y for x, y in zip(old_residual, new_residual)))
        terminal = [(a, y - x) for a, (x, y) in enumerate(zip(old_residual, new_residual)) if x != y]
        amplitude = fibonacci(k + 3)
        patterns = 2 * k + 3
        tight_support_two_bound = fibonacci((patterns + 3) // 2)
        assert amplitude == tight_support_two_bound
        assert terminal == [(last, amplitude)]
        assert max(support_sizes) <= 2

        action_incidence = max(len(action) for action in task.actions)
        advancing_set_size = max(sum(j in dict(action) for action in task.actions) for j in range(task.dims))
        assert action_incidence <= 3
        assert advancing_set_size <= 3
        assert work.changed_entries == patterns
        assert len(task.costs) == 2 * k + 4
        assert max(task.costs) == amplitude

        records.append({
            'k': k,
            'patterns': patterns,
            'labels': len(task.costs),
            'max_cost': max(task.costs),
            'max_cost_bits': max(task.costs).bit_length(),
            'final_amplification': amplitude,
            'tight_support_two_bound': tight_support_two_bound,
            'attains_tight_support_two_bound': True,
            'max_residual_support': max(support_sizes),
            'max_action_pattern_incidence': action_incidence,
            'max_advancing_set_size': advancing_set_size,
            'table_changes': table_differences,
        })

    result = {
        'status': 'passed',
        'construction': 'tight Fibonacci support-two carry amplifier',
        'records': records,
        'cpu_seconds': time.process_time() - start,
        'wall_seconds': time.perf_counter() - wall,
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'workers': 1,
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'records'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='results/amplification.json')
    args = parser.parse_args()
    main(args.out)
