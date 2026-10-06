"""Check the measured run inventory without discarding unsuccessful searches."""
from __future__ import annotations


def validate_runs(runs, methods, replicates):
    expected = {(method, repeat) for method in methods for repeat in range(replicates)}
    observed = [(run['method'], run['repeat']) for run in runs]
    if len(observed) != len(expected) or set(observed) != expected:
        raise ValueError('missing, duplicate or unexpected method/repeat record')
    solved = set()
    failures = 0
    for run in runs:
        search = run['search']
        if search['status'] == 'solved':
            if type(search['cost']) is not int or search['cost'] < 0:
                raise ValueError('solved search requires a nonnegative integer cost')
            solved.add(search['cost'])
        elif search['status'] in ('limit', 'unsolvable') and search['cost'] is None:
            failures += 1
        else:
            raise ValueError('invalid search outcome')
    if len(solved) > 1:
        raise ValueError('different returned solution costs')
    # Successful deterministic searches and work counts must agree across
    # repetitions. A limited run can stop at a different point on a slow host.
    for method in methods:
        completed = [run for run in runs if run['method'] == method
                     and run['search']['status'] == 'solved']
        if completed:
            reference = completed[0]
            for run in completed[1:]:
                if any(run['search'][key] != reference['search'][key]
                       for key in ('cost', 'expansions', 'generated')):
                    raise ValueError('successful deterministic repeats differ')
                if run['work'] != reference['work']:
                    raise ValueError('deterministic work counters differ across repeats')
    exact = [run for run in runs if run['method'] in ('full', 'exact', 'support')
             and run['search']['status'] == 'solved']
    if len({(run['search']['expansions'], run['search']['generated']) for run in exact}) > 1:
        raise ValueError('identical exact heuristics produced different searches')
    return failures
