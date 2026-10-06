"""Run a bounded shard of the frozen campaign; no external dependencies.

Timers exclude construction of the unchanged abstractions, old tables, exact
reference tables and accounting-only comparisons. All update methods pay for
creating the new heuristic evaluator. A* and update timings are recorded per run.
The same inputs recur for three timing repeats, not three independent samples.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
from fractions import Fraction
from dataclasses import asdict
sys.path.insert(0, str(Path(__file__).resolve().parent/'src'))
from platform_support import require_supported_environment
resource = require_supported_environment('benchmark.py')
from cascades import rebuild, update, distances, Work, astar
from families import make_task, relay_task, changed_costs
from evaluation import validate_runs


def run_case(spec, config, index):
    wall0,cpu0 = time.perf_counter(),time.process_time()
    task = relay_task(spec['m'],spec['delta']) if spec['family']=='relay' else make_task(spec['family'],spec['q'],spec['seed'])
    costs = changed_costs(task,spec['mode'],spec.get('seed',0),spec.get('delta'))
    graphs = task.abstractions()
    old,_ = rebuild(graphs,task.costs)
    setup_s = time.perf_counter()-wall0
    reference,_ = rebuild(graphs,costs)
    expected_h = tuple(t.h for t in reference)
    changed = sum(x!=y for a,b in zip(old,reference) for x,y in zip(a.h,b.h))
    changed_tables = sum(a.h!=b.h for a,b in zip(old,reference))
    runs=[]
    for rep in range(config['replicates']):
        methods = config['methods']
        shift = (index+rep)%len(methods)
        for method in methods[shift:]+methods[:shift]:
            tick = time.perf_counter()
            num,den=1,1
            if method=='full':
                tables,work=rebuild(graphs,costs)
                h=task.heuristic(tables)
            elif method in ('exact','support'):
                tables,work=update(graphs,old,costs,method,count_changes=False)
                h=task.heuristic(tables)
            elif method=='scale':
                gamma=min([Fraction(1)]+[Fraction(n,o) for n,o in zip(costs,task.costs) if o>0])
                num,den=gamma.numerator,gamma.denominator
                work=Work();tables=old
                h=task.heuristic(old)
            elif method=='maximum':
                work=Work()
                tables=tuple(distances(g,costs,work) for g in graphs)
                work.rebuilt_tables=len(graphs)
                work.written_entries=sum(g.n for g in graphs)
                h=task.heuristic(tables,'maximum')
            else:
                raise ValueError(method)
            update_s=time.perf_counter()-tick
            result=astar(task.start,task.goal,task.successors,costs,h,
                         scale_num=num,scale_den=den,
                         max_expansions=config['limits']['astar_expansions'],
                         seconds=config['limits']['astar_seconds'])
            # These comparisons are deliberately outside both measured intervals.
            if method in ('full','exact','support'):
                assert tuple(t.h for t in tables)==expected_h
                assert tuple(t.allocated for t in tables)==tuple(t.allocated for t in reference)
            record=dict(method=method,repeat=rep,update_seconds=update_s,
                        total_seconds=update_s+result['seconds'],scale=[num,den],
                        search=result,work=asdict(work))
            runs.append(record)
    # Outcome/agreement gates run in main after saving the complete raw case.
    # Time-limited searches may stop at different expansion counts; the shared
    # validator compares successful deterministic searches and rejects every
    # incomplete case without discarding its measurements.
    return dict(spec=spec,inputs=dict(q=task.q,dims=task.dims,actions=task.actions,
                    old_costs=task.costs,new_costs=costs,patterns=task.patterns,start=task.start),
                dimensions=dict(concrete_states=task.q**task.dims,labels=len(costs),patterns=len(graphs),
                    abstract_entries=sum(g.n for g in graphs),abstract_edges=sum(len(g.edges) for g in graphs)),
                exact_changed_entries=changed,exact_changed_tables=changed_tables,
                setup_seconds=setup_s,runs=runs,cpu_seconds=time.process_time()-cpu0,
                wall_seconds=time.perf_counter()-wall0,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config',default='inputs/campaign.json')
    p.add_argument('--out',default='results/campaign')
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--stop',type=int,default=60)
    p.add_argument('--replace',action='store_true')
    args=p.parse_args()
    config=json.loads(Path(args.config).read_text())
    if not 0<=args.start<=args.stop<=len(config['cases']):
        raise SystemExit('invalid shard')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    campaign_cpu=sum(json.loads(p.read_text()).get('cpu_seconds',0) for p in out.glob('*.json'))
    completed=[];start_cpu=time.process_time()
    for i in range(args.start,args.stop):
        spec=config['cases'][i];dest=out/(spec['id']+'.json')
        if dest.exists() and not args.replace:
            previous=json.loads(dest.read_text())
            if previous['spec']!=spec or len(previous['runs'])!=len(config['methods'])*config['replicates']:
                raise SystemExit('existing result does not match frozen specification')
            if validate_runs(previous['runs'],config['methods'],config['replicates']):
                raise SystemExit('existing case has incomplete searches; raw output retained')
            continue
        if campaign_cpu+time.process_time()-start_cpu>=config['limits']['cpu_campaign_seconds']*0.75:
            raise SystemExit('campaign repair reserve reached')
        result=run_case(spec,config,i)
        tmp=dest.with_suffix('.tmp')
        tmp.write_text(json.dumps(result,indent=2)+'\n');tmp.replace(dest)
        completed.append(spec['id'])
        print(spec['id'], 'cpu=%.3f'%result['cpu_seconds'], 'failures='+str(sum(r['search']['status']!='solved' for r in result['runs'])),flush=True)
        if validate_runs(result['runs'],config['methods'],config['replicates']):
            raise SystemExit('case has incomplete searches; raw output retained, no completion claim')
    print(json.dumps(dict(completed=len(completed),shard_cpu_seconds=time.process_time()-start_cpu,
                          peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))

if __name__=='__main__':main()
