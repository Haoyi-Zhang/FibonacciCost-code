"""Generate LaTeX tables from retained aggregate data, not hand-entered numbers."""
from pathlib import Path
import argparse,json

NAMES={'full':'Full SCP','exact':'Exact reuse','support':'Support only','scale':'Scaled old','maximum':'New maximum'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',default='results');p.add_argument('--out',required=True)
    a=p.parse_args();data=json.loads((Path(a.results)/'summary.json').read_text())
    if data['failures'] != 0 or any(row['failures'] != 0 for row in data['aggregates']):
        raise SystemExit('incomplete campaign: refusing all-solved manuscript tables; retain raw results')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    rows=[r for r in data['aggregates'] if r['family']=='all']
    lines=[r'\begin{tabular}{lrrrr}',r'\toprule',r'Method & W\% & U(ms) & Nodes & T(ms)\\',r'\midrule']
    for r in rows:
        lines.append(f"{NAMES[r['method']]} & {r['rewritten_percent']:.1f} & {r['sum_update_ms']:.2f} & {r['sum_expansions']:,} & {r['sum_total_ms']:.2f}"+r'\\')
    lines += [r'\bottomrule',r'\end{tabular}']
    (out/'results.tex').write_text('\n'.join(lines)+'\n')
    lines=[r'\begin{landscape}',r'\begin{table}[p]',r'\centering',r'\begin{tabular}{llrrrrrr}',r'\toprule',r'Family & Method & Cases & Written (\%) & Update (ms) & Update+A* (ms) & Ratio to full & Expansions\\',r'\midrule']
    for family in ('independent','coupled','relay'):
        for idx,r in enumerate(x for x in data['aggregates'] if x['family']==family):
            lines.append(f"{family.title() if idx==0 else ''} & {NAMES[r['method']]} & {r['cases']} & {r['rewritten_percent']:.1f} & {r['sum_update_ms']:.3f} & {r['sum_total_ms']:.2f} & {r['total_ratio']:.3f} & {r['sum_expansions']:,}"+r'\\')
        lines.append(r'\midrule')
    lines[-1]=r'\bottomrule'
    lines += [r'\end{tabular}',r'\caption{Primary synthetic campaign by family. Times sum per-instance medians; repetitions are not independent tasks. Ratios use the summed update-plus-search times within a family. Written percentages are weighted by table size. All methods solve every case.}',r'\label{tab:families}',r'\end{table}',r'\end{landscape}']
    (out/'family-results.tex').write_text('\n'.join(lines)+'\n')
    print('generated results.tex and family-results.tex')
if __name__=='__main__':main()
