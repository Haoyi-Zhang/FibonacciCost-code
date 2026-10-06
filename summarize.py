"""Summarize all frozen cases, retaining failures and paired timing variability."""
import argparse,csv,json,statistics,sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from evaluation import validate_runs


def summarize(root,output):
    config=json.loads(Path('inputs/campaign.json').read_text())
    expected={s['id']:s for s in config['cases']}
    cases=[json.loads(p.read_text()) for p in sorted(Path(root).glob('*.json'))]
    if len(cases)!=len(expected) or {c['spec']['id'] for c in cases}!=set(expected):
        raise ValueError('missing or unexpected campaign cases')
    rows=[];bycase={}
    for c in cases:
        cid=c['spec']['id'];bycase[cid]={}
        if c['spec'] != expected[cid]:
            raise ValueError('case specification differs from frozen protocol: ' + cid)
        validate_runs(c['runs'], config['methods'], config['replicates'])
        for method in config['methods']:
            runs=[r for r in c['runs'] if r['method']==method]
            if len(runs)!=config['replicates']:
                raise ValueError('repeat count differs from frozen protocol')
            med=lambda key:statistics.median(r[key] for r in runs)
            times=[r['total_seconds'] for r in runs]
            row=dict(case=cid,family=c['spec']['family'],mode=c['spec']['mode'],method=method,
                patterns=c['dimensions']['patterns'],entries=c['dimensions']['abstract_entries'],
                changed_tables=c['exact_changed_tables'],changed_entries=c['exact_changed_entries'],
                written_entries=runs[0]['work']['written_entries'],
                rebuilt_tables=runs[0]['work']['rebuilt_tables'],
                certificate_entries=runs[0]['work']['certificate_entries'],
                edge_scans=sum(runs[0]['work'][k] for k in ('distance_edge_scans','saturation_edge_scans','certificate_edge_scans')),
                update_ms=1000*med('update_seconds'),total_ms=1000*statistics.median(times),
                min_total_ms=1000*min(times),max_total_ms=1000*max(times),
                expansions=runs[0]['search']['expansions'],
                failures=sum(r['search']['status']!='solved' for r in runs))
            rows.append(row);bycase[cid][method]=row
    aggregate=[]
    for group in ['independent','coupled','relay','all']:
        subset=[c for c in cases if group=='all' or c['spec']['family']==group]
        for method in config['methods']:
            rs=[bycase[c['spec']['id']][method] for c in subset]
            pairs=[bycase[c['spec']['id']][method]['total_ms']/bycase[c['spec']['id']]['full']['total_ms'] for c in subset]
            totals=[r['total_ms'] for r in rs]
            aggregate.append(dict(family=group,method=method,cases=len(rs),
                rewritten_percent=100*sum(r['written_entries'] for r in rs)/sum(r['entries'] for r in rs),
                median_rebuilt_tables=statistics.median(r['rebuilt_tables'] for r in rs),
                median_certificate_entries=statistics.median(r['certificate_entries'] for r in rs),
                median_update_ms=statistics.median(r['update_ms'] for r in rs),
                sum_update_ms=sum(r['update_ms'] for r in rs),
                median_total_ms=statistics.median(totals),sum_total_ms=sum(totals),
                total_ratio=sum(totals)/sum(bycase[c['spec']['id']]['full']['total_ms'] for c in subset),
                median_paired_total_ratio=statistics.median(pairs),min_paired_total_ratio=min(pairs),max_paired_total_ratio=max(pairs),
                paired_wins=sum(x<1 for x in pairs),sum_expansions=sum(r['expansions'] for r in rs),
                failures=sum(r['failures'] for r in rs)))
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name,data in [('cases.csv',rows),('aggregate.csv',aggregate)]:
        with (output/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    result=dict(cases=len(cases),timed_searches=sum(len(c['runs']) for c in cases),
        failures=sum(r['failures'] for r in rows),
        case_cpu_seconds=sum(c['cpu_seconds'] for c in cases),
        case_wall_seconds=sum(c['wall_seconds'] for c in cases),
        max_peak_rss_kib=max(c['peak_rss_kib'] for c in cases),
        max_concrete_states=max(c['dimensions']['concrete_states'] for c in cases),
        max_abstract_entries=max(c['dimensions']['abstract_entries'] for c in cases),
        max_labels=max(c['dimensions']['labels'] for c in cases),aggregates=aggregate)
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    for a in aggregate:
        print(a['family'],a['method'],'write%%=%.1f'%a['rewritten_percent'],'update_ms=%.3f'%a['sum_update_ms'],
              'total_ms=%.2f'%a['sum_total_ms'],'ratio=%.3f'%a['total_ratio'],'medratio=%.3f'%a['median_paired_total_ratio'],
              'exp=',a['sum_expansions'])
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='results/campaign');p.add_argument('--out',default='results')
    a=p.parse_args();result=summarize(a.root,a.out)
    if result['failures']:
        raise SystemExit('incomplete searches; diagnostic summary retained, not a completed campaign')
