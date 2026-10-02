from pathlib import Path
import sys,json,time,itertools,argparse
sys.path.insert(0,str(Path(__file__).parent/'src'))
from platform_support import require_supported_environment
resource = require_supported_environment('pilot.py')
from cascades import *
from oracle import partition
from families import fibonacci, fibonacci_amplifier_task

parser=argparse.ArgumentParser();parser.add_argument('--out',default=str(Path(__file__).parent/'results/pilot.json'));args=parser.parse_args()
t0=time.process_time(); w0=time.perf_counter()
records=[]
for m in (1,2,3,4,8,16,64):
    gs,c=relay(m);old,_=rebuild(gs,c); cnew=(0,)+c[1:]
    new,w=update(gs,old,cnew)
    assert tuple((t.offered,t.h,t.allocated) for t in new)==partition(gs,cnew)
    assert [t.h[0] for t in old]==[1]*m
    assert [t.h[0] for t in new]==[0 if i%2==0 else 2 for i in range(m)]
    records.append(dict(m=m,changed=w.changed_entries,new_values=[t.h[0] for t in new]))
# Small nontrivial Fibonacci amplifier, checked against the independent oracle.
amp_task,amp_last=fibonacci_amplifier_task(4)
amp_graphs=amp_task.abstractions();amp_old,_=rebuild(amp_graphs,amp_task.costs)
amp_costs=(0,)+amp_task.costs[1:];amp_new,amp_work=update(amp_graphs,amp_old,amp_costs)
assert tuple((t.offered,t.h,t.allocated) for t in amp_new)==partition(amp_graphs,amp_costs)
amp_old_res=tuple(x-y for x,y in zip(amp_old[-1].offered,amp_old[-1].allocated))
amp_new_res=tuple(x-y for x,y in zip(amp_new[-1].offered,amp_new[-1].allocated))
amp_terminal=[(a,y-x) for a,(x,y) in enumerate(zip(amp_old_res,amp_new_res)) if x!=y]
assert amp_work.changed_entries==11 and amp_terminal==[(amp_last,fibonacci(7))]
# Counterexample to local Bellman equality without goal-rooted tight reachability.
g=Graph(3,2,(2,),((0,1,0),(1,0,0),(0,2,1)))
old=Table((0,1),(1,1,0),(0,1)); nw=(0,2)
assert all(any(old.h[u]==nw[a]+old.h[v] for x,v,a in g.edges if x==u) for u in (0,1))
assert not unchanged(g,old,nw,Work())
# Feasible NEW allocations with a stale downstream table can overestimate.
gs,c=relay(3);old,_=rebuild(gs,c);new,_=rebuild(gs,(0,2,2,2))
s=(1,0,0); bad=new[0].h[s[0]]+new[1].h[s[1]]+old[2].h[s[2]]
def succ(s):
    out=[]
    for a in range(4):
        t=list(s)
        for i in (a-1,a):
            if 0<=i<3:t[i]=1
        out.append((a,tuple(t)))
    return out
search=astar(s,(1,1,1),succ,(0,2,2,2),lambda s:sum(t.h[x] for t,x in zip(new,s)))
assert bad==3 and search['cost']==2
report=dict(pilot='relay, Fibonacci amplifier, zero-cycle negative control, concrete A* stale-table counterexample',
            relay=records,amplifier=dict(k=4,patterns=11,final_amplification=fibonacci(7),
                terminal_difference=amp_terminal,changed_tables=amp_work.changed_entries),
            stale_value=bad,exact_plan_cost=search['cost'],
            search=search,workers=1,integer_type='Python arbitrary precision',
            cpu_seconds=time.process_time()-t0,wall_seconds=time.perf_counter()-w0,
            peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,failures=0)
p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
