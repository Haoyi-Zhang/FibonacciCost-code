"""Owned regressions for campaign coverage, failure gates and table claims.

No Linux resource measurements are taken here. Temporary inputs are derived
from the supplied synthetic records and stay under the requested output root.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import summarize


def main(output: Path) -> None:
    if sys.flags.optimize:
        raise SystemExit('run without -O; assertions are checks')
    output = output.resolve()
    if output.exists():
        raise SystemExit('output exists; choose a fresh regression directory')
    output.mkdir(parents=True)
    started = time.perf_counter()
    config = json.loads((ROOT / 'inputs/campaign.json').read_text())
    records = [json.loads((ROOT / 'results/campaign' / (s['id'] + '.json')).read_text())
               for s in config['cases']]
    tests = []

    def run_variant(name, mutate, *, reject=False):
        destination = output / name
        campaign = destination / 'campaign'
        campaign.mkdir(parents=True, exist_ok=True)
        cases = copy.deepcopy(records)
        mutate(cases)
        for index, case in enumerate(cases):
            (campaign / f'{index}.json').write_text(json.dumps(case), encoding='utf-8')
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = summarize.summarize(campaign, destination / 'summary')
        except ValueError:
            if not reject:
                raise
        else:
            if reject:
                raise AssertionError(name + ': invalid campaign accepted')
            return destination, result
        tests.append(name)

    original, result = run_variant('retained-complete', lambda cases: None)
    assert result == json.loads((ROOT / 'results/summary.json').read_text())
    tests.append('retained summary unchanged')
    run_variant('duplicate-case', lambda cases: cases.append(copy.deepcopy(cases[0])), reject=True)
    run_variant('changed-spec', lambda cases: cases[0]['spec'].update(seed=12345), reject=True)
    run_variant('duplicate-repeat', lambda cases: cases[0]['runs'][5].update(repeat=0), reject=True)
    run_variant('unknown-method', lambda cases: cases[0]['runs'].append(
        dict(copy.deepcopy(cases[0]['runs'][0]), method='unmeasured')), reject=True)

    def disagree(cases):
        cases[0]['runs'][0]['search']['cost'] += 1
    run_variant('different-solution', disagree, reject=True)
    def different_search(cases):
        cases[0]['runs'][5]['search']['generated'] += 1
    run_variant('different-repeat-search', different_search, reject=True)
    def different_work(cases):
        cases[0]['runs'][5]['work']['written_entries'] += 1
    run_variant('different-repeat-work', different_work, reject=True)

    def limit_one(cases):
        cases[0]['runs'][0]['search'].update(status='limit', cost=None)
    incomplete, result = run_variant('one-owned-limit', limit_one)
    assert result['failures'] == 1 and result['timed_searches'] == 900
    tests.append('limited run retained, not filtered')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, '-B', str(ROOT / 'summarize.py'), '--root',
               str(incomplete / 'campaign'), '--out', str(incomplete / 'cli-summary')]
    limited = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                             text=True, timeout=15)
    (incomplete / 'summary-cli.stdout.txt').write_text(limited.stdout, encoding='utf-8')
    (incomplete / 'summary-cli.stderr.txt').write_text(limited.stderr, encoding='utf-8')
    assert limited.returncode != 0, 'limited campaign exited successfully'
    assert (incomplete / 'cli-summary/summary.json').exists(), 'failure evidence lost'
    tests.append('limited summary CLI fails after saving evidence')

    def table_command(source, destination):
        command = [sys.executable, '-B', str(ROOT / 'make_tables.py'),
                   '--results', str(source), '--out', str(destination)]
        done = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=15)
        return done
    valid = table_command(original / 'summary', original / 'tables')
    assert valid.returncode == 0, valid.stderr
    if (ROOT.parent / 'paper/figures/results.tex').exists():
        assert (original / 'tables/results.tex').read_text() == (ROOT.parent / 'paper/figures/results.tex').read_text()
    tests.append('complete retained numerical table unchanged')
    family_table = (original / 'tables/family-results.tex').read_text()
    assert family_table.startswith('\\begin{landscape}\n\\begin{table}[p]\n')
    assert family_table.endswith('\\end{table}\n\\end{landscape}\n')
    if (ROOT.parent / 'paper/figures/family-results.tex').exists():
        assert family_table == (ROOT.parent / 'paper/figures/family-results.tex').read_text()
    tests.append('current landscape family table preserved by regeneration')
    invalid = table_command(incomplete / 'summary', incomplete / 'tables')
    (incomplete / 'tables.stdout.txt').write_text(invalid.stdout, encoding='utf-8')
    (incomplete / 'tables.stderr.txt').write_text(invalid.stderr, encoding='utf-8')
    assert invalid.returncode != 0, 'limited campaign generated all-solved caption'
    assert not (incomplete / 'tables/family-results.tex').exists()
    tests.append('limited campaign cannot generate all-solved caption')
    linux_driver = 'not run: Linux benchmark/resource contract is unavailable on this platform'
    if sys.platform.startswith('linux'):
        fixture = output / 'bounded-driver'
        fixture.mkdir()
        tiny = copy.deepcopy(config)
        tiny['cases'] = [dict(id='owned-tiny-limit', family='independent', mode='sparse', q=2, seed=0)]
        tiny['replicates'] = 1
        tiny['limits']['astar_expansions'] = 0
        (fixture / 'config.json').write_text(json.dumps(tiny), encoding='utf-8')
        command = [sys.executable, '-B', str(ROOT / 'benchmark.py'), '--config',
                   str(fixture / 'config.json'), '--start', '0', '--stop', '1',
                   '--out', str(fixture / 'campaign')]
        for attempt in ('new-case', 'existing-case'):
            done = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                  text=True, timeout=15)
            (fixture / (attempt + '.stdout.txt')).write_text(done.stdout, encoding='utf-8')
            (fixture / (attempt + '.stderr.txt')).write_text(done.stderr, encoding='utf-8')
            assert done.returncode != 0
            raw = json.loads((fixture / 'campaign/owned-tiny-limit.json').read_text())
            assert len(raw['runs']) == 5 and all(r['search']['status'] == 'limit' for r in raw['runs'])
            tests.append('benchmark ' + attempt + ' fails while preserving five limited runs')
        linux_driver = 'two bounded benchmark CLI failure gates checked on owned q=2 inputs'
    report = dict(status='passed', checks=len(tests), tests=tests,
                  scope='owned data/reporting regressions; not a timing reproduction',
                  linux_driver_checks=linux_driver,
                  wall_seconds=time.perf_counter() - started)
    (output / 'evaluation_checks.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    main(Path(parser.parse_args().out))
