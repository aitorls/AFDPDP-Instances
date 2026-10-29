"""
[L2] One row per (instance set, instance, algorithm) with the independently verified cost decomposition (L4) and the
per-call statistics stored in the output JSON.

Usage (cwd = repo root):
  python tools/summarize_runs.py OUTPUT_CSV LABEL=ROOT [LABEL=ROOT ...] [--prefixes P1 P2 ...]
  e.g. python tools/summarize_runs.py results/revision/summary.csv original=input/AFDPDP-Instances \
          tw_0.5=input/AFDPDP-Instances-delay/tw_0.5 tw_0.25=input/AFDPDP-Instances-delay/tw_0.25
Without --prefixes, every output prefix found is summarised (prefix = file name up to the first '_').
The delay penalty used to recompute the cost is 50, or the value of a '-dp<value>' suffix in the prefix.
"""
import argparse
import glob
import json
import os
import re

import pandas as pd

from verify_solutions import load_instance, verify

GRAPH_NAMES = {'random': 'Random', 'mountain': 'Polar', 'asymmetric_grid': 'SparseGrid', 'symmetric_grid': 'DenseGrid'}
REQUESTS = 50


def penalty_of(prefix):
    match = re.search(r'-dp([0-9.]+)$', prefix)
    return float(match.group(1)) if match else 50.0


def latest_by_prefix(output_dir):
    files = {}
    for path in sorted(glob.glob(os.path.join(output_dir, '*.json')), key=os.path.getmtime):
        name = os.path.basename(path)
        if '_iterations_' in name:
            continue
        files[name.split('_')[0]] = path  # the most recent file of each prefix wins
    return files


def call_stats(solution):
    stats = dict(n_calls=None, n_calls_optimal=None, n_calls_no_incumbent=None, mean_solver_time=None,
                 max_solver_time=None, mean_gap=None, n_plan_changes=None, n_reassigned_tasks=None)
    ws = solution.get('warm_start_iteration_stats') or []
    milp = solution.get('solver_stats') or []
    if ws:
        times = [c['MILP_time'] for c in ws]
        stats.update(n_calls=len(ws), mean_solver_time=sum(times) / len(times), max_solver_time=max(times))
        if 'MILP_status' in ws[0]:  # v2
            stats.update(n_calls_optimal=sum(c['MILP_status'] == 'OPTIMAL' for c in ws),
                         n_calls_no_incumbent=sum(c['MILP_sol_count'] == 0 for c in ws),
                         n_plan_changes=sum(bool(c['MILP_plan_changed']) for c in ws),
                         n_reassigned_tasks=sum(c['MILP_reassigned_tasks'] for c in ws))
            gaps = [c['MILP_gap'] for c in ws if c['MILP_gap'] is not None]
            stats['mean_gap'] = sum(gaps) / len(gaps) if gaps else None
    elif milp:
        times = [c['runtime'] for c in milp]
        gaps = [c['gap'] for c in milp if c['gap'] is not None]
        stats.update(n_calls=len(milp), n_calls_optimal=sum(c['status'] == 'OPTIMAL' for c in milp),
                     n_calls_no_incumbent=sum(c['sol_count'] == 0 for c in milp),
                     mean_solver_time=sum(times) / len(times), max_solver_time=max(times),
                     mean_gap=sum(gaps) / len(gaps) if gaps else None)
    elif solution.get('iterations_time'):
        times = solution['iterations_time']
        stats.update(n_calls=len(times), mean_solver_time=sum(times) / len(times), max_solver_time=max(times))
    reassign = solution.get('reassign_stats') or []
    if reassign:
        stats.update(n_plan_changes=sum(s['accepted'] for s in reassign),
                     n_reassigned_tasks=sum(s['moved'] for s in reassign))
    return stats


def instance_metadata(instance):
    match = re.match(r'(\d+)HR_6Q_(\d+)RQT_(\d)q(_bigTW)?_(\d+)$', instance)
    if not match:
        return {}
    return dict(robots=int(match.group(1)), tw='wide' if match.group(4) else 'narrow', seed=int(match.group(5)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output_csv')
    parser.add_argument('roots', nargs='+', help='LABEL=ROOT')
    parser.add_argument('--prefixes', nargs='+')
    parser.add_argument('--pattern', default='*HR_6Q_50RQT_2q_*')
    args = parser.parse_args()

    rows = []
    for item in args.roots:
        label, root = item.split('=', 1)
        for graph in sorted(os.listdir(root)):
            for instance_dir in sorted(glob.glob(os.path.join(root, graph, args.pattern))):
                files = latest_by_prefix(os.path.join(instance_dir, 'output'))
                if args.prefixes:
                    files = {p: f for p, f in files.items() if p in args.prefixes}
                if not files:
                    continue
                robots, requests, distances = load_instance(instance_dir)
                instance = os.path.basename(instance_dir)
                for prefix, path in files.items():
                    row = dict(set=label, graph=GRAPH_NAMES.get(graph, graph), instance=instance,
                               **instance_metadata(instance), algorithm=prefix, file=os.path.basename(path))
                    try:
                        with open(path) as f:
                            solution = json.load(f)
                        row.update(json_cost=solution.get('cost'), feasible_flag=solution.get('feasible'),
                                   computational_time=solution.get('computational_time'),
                                   failed_event_time=solution.get('failed_event_time'))
                        ct = solution.get('computational_time')
                        row['time_per_request'] = ct / REQUESTS if ct is not None else None
                        if 'complete_routes' in solution:
                            result = verify(solution, robots, requests, distances, penalty_of(prefix))
                            result['fixed_cost'] = result['use_cost'] - result['backup_use_cost']
                            row.update({k: v for k, v in result.items() if k != 'details'})
                        else:
                            row['valid'] = False
                        row.update(call_stats(solution))
                    except Exception as error:  # one unreadable or old-format file must not stop the summary
                        row['valid'] = False
                        row['error'] = f"{type(error).__name__}: {error}"
                        print(f"WARNING {path}: {row['error']}")
                    rows.append(row)
    pd.DataFrame(rows).to_csv(args.output_csv, index=False)
    print(f"Summarised {len(rows)} solutions -> {args.output_csv}")


if __name__ == '__main__':
    main()
