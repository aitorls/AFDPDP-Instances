"""
[WSR] How often MCFI or MCFI+R gives the better plan.

1. Final cost per instance of stand-alone MCFI vs MCFI+R (summary.csv, every set in it).
2. WS-MILP warm-started with the cheaper of the two plans (prefix WSR-v2-soft): per event, which plan was the warm
   start (from reassign_stats in the WSR JSONs); per instance, final cost of WSR vs WS-v2-soft (summary.csv).

Usage (cwd = repo root):
  python tools/count_mcfi_vs_mcfir.py results/revision/campaign/summary.csv input/AFDPDP-Instances \
      [results/revision/campaign/wsr_counts.csv]
"""
import glob
import json
import os
import sys

import pandas as pd

TOL = 1e-6
GRAPHS = {'symmetric_grid': 'DenseGrid', 'asymmetric_grid': 'SparseGrid', 'mountain': 'Polar', 'random': 'Random'}


def compare(summary, a, b, label_a, label_b):
    """Instances where a or b is cheaper, per set and per graph (final verified cost)"""
    p = summary[summary.algorithm.isin([a, b])].pivot_table(index=['set', 'graph', 'instance'], columns='algorithm',
                                                             values='cost')
    if a not in p or b not in p:
        print(f"  {a} or {b} not in the summary")
        return
    p = p[[a, b]].dropna()
    diff = p[b] - p[a]
    p['winner'] = [label_b if d < -TOL else label_a if d > TOL else 'tie' for d in diff]
    for level in (['set'], ['set', 'graph']):
        t = p.groupby(level)['winner'].value_counts().unstack(fill_value=0)
        t['n'] = t.sum(axis=1)
        print(t.to_string(), '\n')


def event_counts(root):
    """Per WSR run: events whose warm start was the MCFI+R plan, the MCFI plan (reassigned plan not cheaper) or the
    MCFI plan because there was nothing to reassign (fewer than two unstarted tasks or reinsertion failed)"""
    rows = []
    for graph, name in GRAPHS.items():
        for path in sorted(glob.glob(os.path.join(root, graph, '*HR_6Q_50RQT_2q*', 'output', 'WSR-v2-soft_*.json'))):
            stats = json.load(open(path)).get('reassign_stats') or []
            tried = [s for s in stats if s['cost_after'] is not None]
            rows.append(dict(graph=name, instance=path.split(os.sep)[-3], events=len(stats),
                             mcfir_better=sum(s['accepted'] for s in stats),
                             tie=sum(abs(s['cost_after'] - s['cost_before']) <= TOL for s in tried),
                             mcfi_better=sum(s['cost_after'] > s['cost_before'] + TOL for s in tried),
                             nothing_to_reassign=len(stats) - len(tried)))
    return pd.DataFrame(rows)


def main():
    summary = pd.read_csv(sys.argv[1])
    print("1. Stand-alone MCFI vs MCFI+R, final cost per instance")
    compare(summary, 'MCFI-v2-soft', 'MCFIR-v2-soft', 'MCFI', 'MCFI+R')

    events = event_counts(sys.argv[2])
    print(f"2. WSR-v2-soft: warm start per event ({len(events)} runs)")
    if len(events):
        cols = ['events', 'mcfir_better', 'tie', 'mcfi_better', 'nothing_to_reassign']
        print(events.groupby('graph')[cols].sum().to_string())
        print('total', events[cols].sum().to_dict())
        print(f"instances with at least one MCFI+R warm start: {(events.mcfir_better > 0).sum()} / {len(events)}\n")
        if len(sys.argv) > 3:
            events.to_csv(sys.argv[3], index=False)

    print("3. WS-MILP warm-started with MCFI (WS-v2-soft) vs with the cheaper plan (WSR-v2-soft), final cost")
    compare(summary[summary.set == 'original'], 'WS-v2-soft', 'WSR-v2-soft', 'WS', 'WSR')


if __name__ == '__main__':
    main()
