from pathlib import Path
import sys,itertools,random,json,time,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from platform_support import require_supported_environment
resource = require_supported_environment('tests/check_all.py')
from cascades import Graph,Table,Work,distances,saturation,unchanged,rebuild,update,relay
from oracle import bellman,partition
from families import make_task,changed_costs

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='results/checks.json');args=parser.parse_args()
    start=time.process_time();wall=time.perf_counter()
    graphs,pairs,chain_updates,states_checked,lipschitz_checks,two_stage_checks=0,0,0,0,0,0
    costs=list(itertools.product(range(3),repeat=2))
    for targets in itertools.product(range(3),repeat=6):
        g=Graph(3,2,(2,),tuple((u,targets[2*u+a],a) for u in range(3) for a in range(2)))
        try:bellman(3,(2,),g.edges,(1,1))
        except ValueError:continue
        graphs+=1
        values={c:bellman(3,(2,),g.edges,c) for c in costs}
        for c in costs:
            d=distances(g,c);assert d==values[c]
            t=Table(c,d,saturation(g,d))
            assert distances(g,t.allocated)==d
            for cp in costs:
                w=Work();b=unchanged(g,t,cp,w)
                assert b==(d==values[cp]),(g,c,cp,d,values[cp],b)
                pairs+=1
    rng=random.Random(91827)
    for trial in range(120):
        gs=[]
        for _ in range(5):
            es=[(u,rng.randrange(6),a) for u in range(6) for a in range(4)]
            # One common reset-to-goal label guarantees finite distances.
            es.extend((u,5,4) for u in range(6))
            gs.append(Graph(6,5,(5,),tuple(es)))
        oldc=tuple(rng.randrange(7) for _ in range(5));old,_=rebuild(gs,oldc)
        for _ in range(12):
            cp=tuple(rng.randrange(7) for _ in range(5))
            got,_=update(gs,old,cp);reference=partition(gs,cp)
            assert tuple((t.offered,t.h,t.allocated) for t in got)==reference
            supp,_=update(gs,old,cp,'support');assert supp==got
            old=got;chain_updates+=1
    # Goal-rootedness, newly tight edges, and ties are individually discriminated.
    zero=Graph(3,2,(2,),((0,1,0),(1,0,0),(0,2,1)))
    old,_=rebuild((zero,),(0,1));w=Work()
    assert not unchanged(zero,old[0],(0,2),w) and w.reachability_failures==1
    ties=Graph(2,2,(1,),((0,1,0),(0,1,1)))
    old,_=rebuild((ties,),(1,2));w=Work()
    assert unchanged(ties,old[0],(2,1),w) and w.tight_skips==1
    old,_=rebuild((ties,),(1,1));assert unchanged(ties,old[0],(2,1),Work())
    # All concrete states on small projected planning tasks: independent oracle.
    for family in ('independent','coupled'):
        for seed in range(4):
            task=make_task(family,2,seed);gs=task.abstractions();old,_=rebuild(gs,task.costs)
            ss=list(itertools.product(range(2),repeat=task.dims));ids={s:i for i,s in enumerate(ss)}
            es=tuple((i,ids[t],a) for i,s in enumerate(ss) for a,t in task.successors(s))
            for mode in ('sparse','mixed'):
                cp=changed_costs(task,mode,seed);new,_=update(gs,old,cp)
                h=task.heuristic(new);exact=bellman(len(ss),(len(ss)-1,),es,cp)
                for s,d in zip(ss,exact):assert h(s)<=d;states_checked+=1
                for u,v,a in es:assert h(ss[u])<=cp[a]+h(ss[v])
    for m in (1,2,3,4,7,8,31,32,127):
        gs,c=relay(m);old,_=rebuild(gs,c);new,w=update(gs,old,(0,)+c[1:])
        assert w.changed_entries==m
        assert [t.h[0] for t in new]==[0 if i%2==0 else 2 for i in range(m)]
    # Exhaustive finite check of Lemma 3 for two-state minimum-subtraction maps.
    vectors=list(itertools.product(range(3),repeat=4))
    for mask in range(1,1<<4):
        selected=tuple(i for i in range(4) if mask>>i & 1)
        def transform(v):
            m=min(v[i] for i in selected)
            return tuple(x-m if i in selected else x for i,x in enumerate(v))
        transformed={v:transform(v) for v in vectors}
        for left in vectors:
            for right in vectors:
                eta=max(abs(x-y) for x,y in zip(left,right))
                out=max(abs(x-y) for x,y in zip(transformed[left],transformed[right]))
                assert out<=2*eta,(selected,left,right,out,eta)
                lipschitz_checks+=1
    # Tight onset lemma: one unit decrease cannot exceed magnitude one
    # after the first two two-state minimum-subtraction tables.
    latency_vectors=list(itertools.product(range(4),repeat=4))
    subsets=[tuple(i for i in range(4) if mask>>i & 1) for mask in range(1,1<<4)]
    def table_map(v,selected):
        m=min(v[i] for i in selected)
        return tuple(x-m if i in selected else x for i,x in enumerate(v))
    for old_vector in latency_vectors:
        for changed in range(4):
            if old_vector[changed]==0:
                continue
            new_vector=list(old_vector);new_vector[changed]-=1;new_vector=tuple(new_vector)
            for first in subsets:
                old_first=table_map(old_vector,first);new_first=table_map(new_vector,first)
                assert max(abs(x-y) for x,y in zip(old_first,new_first))<=1
                for second in subsets:
                    old_second=table_map(old_first,second);new_second=table_map(new_first,second)
                    assert max(abs(x-y) for x,y in zip(old_second,new_second))<=1
                    two_stage_checks+=1
    for bad in ((1,-1),(1,True),(1,1.0),(1,)):
        try:distances(ties,bad)
        except ValueError:pass
        else:raise AssertionError('invalid costs accepted')
    try:distances(Graph(2,1,(1,),((0,0,0),)),(1,))
    except ValueError:pass
    else:raise AssertionError('infinity silently accepted')
    result=dict(status='passed',exhaustive_graphs=graphs,exhaustive_cost_pairs=pairs,
                sequential_mixed_updates=chain_updates,all_state_admissibility_checks=states_checked,
                single_table_lipschitz_checks=lipschitz_checks,
                two_table_unit_decrease_checks=two_stage_checks,
                targeted_controls=['zero tight SCC rejected','new tight edge accepted','tie surviving increase accepted',
                                   'three-table amplification onset is tight','unreachable states rejected','negative/float/bool/length costs rejected'],
                cpu_seconds=time.process_time()-start,wall_seconds=time.perf_counter()-wall,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
