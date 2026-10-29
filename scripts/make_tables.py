"""
[L5] Tables and figures for the revised paper and the response letter, from the L2 summary (summarize_runs.py).

Every cost is the independently verified cost (L4). Formal metrics, always with the same denominator:
    delta(A|B)    = 100 * (C_A - C_B) / C_B          (per instance, then averaged)
    speed-up(A|B) = mean time per request of B / mean time per request of A
Averages that compare algorithms use the COMMON subset of instances solved by all of them (no survivorship bias).

Usage (cwd = repo root):
  python tools/make_tables.py results/revision/campaign/summary.csv results/revision/tables
Writes <out>/<name>.csv and <name>.tex for every table it has data for, plus fig7_*.pdf/png, and prints a list.
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd

PAPER_GRAPHS = ['Random', 'Polar', 'SparseGrid', 'DenseGrid']
GRAPH_DIRS = {'Random': 'random', 'Polar': 'mountain', 'SparseGrid': 'asymmetric_grid', 'DenseGrid': 'symmetric_grid'}
CELL = ['graph', 'tw', 'robots']
TIME_LIMIT = 300

# Algorithm groups: display name -> output prefix
GROUPS = {
    'paper': {'SCFI': 'BH', 'MCFI': 'UPVD', 'MILP': 'URJC', 'WS-MILP': 'WSD'},
    'v2-hard': {'SCFI': 'BH', 'MCFI': 'MCFI-v2-hard', 'MCFI+R': 'MCFIR-v2-hard', 'MILP': 'MILP-v2-hard',
                'WS-MILP': 'WS-v2-hard'},
    'v2-soft': {'MCFI': 'MCFI-v2-soft', 'MCFI+R': 'MCFIR-v2-soft', 'MILP': 'MILP-v2-soft', 'WS-MILP': 'WS-v2-soft'},
}
# delta(A|B) pairs reported in the comparison tables
PAIRS = [('MCFI', 'MILP'), ('MCFI+R', 'MILP'), ('WS-MILP', 'MILP'), ('WS-MILP', 'MCFI'), ('SCFI', 'WS-MILP')]

written = []


# ---------------------------------------------------------------------------------------------------------------------
# Output helpers

def to_latex(table, caption):
    """Minimal booktabs table (pandas.to_latex needs jinja2)"""
    table = table.reset_index() if not isinstance(table.index, pd.RangeIndex) else table
    columns = [' / '.join(str(p) for p in c if str(p) and not str(p).startswith('Unnamed')) if isinstance(c, tuple)
               else str(c) for c in table.columns]

    def fmt(value):
        if isinstance(value, (float, np.floating)):
            return '--' if np.isnan(value) else f"{value:,.2f}".replace(',', '{,}')
        return str(value).replace('_', r'\_').replace('%', r'\%')

    lines = [r'\begin{table}[ht]', r'\centering', r'\small', f'\\caption{{{caption}}}',
             r'\begin{tabular}{' + 'l' * len(columns) + '}', r'\toprule',
             ' & '.join(fmt(c) for c in columns) + r' \\', r'\midrule']
    lines += [' & '.join(fmt(v) for v in row) + r' \\' for row in table.itertuples(index=False)]
    lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
    return '\n'.join(lines) + '\n'


def save(table, out_dir, name, caption):
    table.to_csv(os.path.join(out_dir, name + '.csv'))
    with open(os.path.join(out_dir, name + '.tex'), 'w', encoding='utf-8') as f:
        f.write(to_latex(table, caption))
    written.append(name)


# ---------------------------------------------------------------------------------------------------------------------
# Data

def load(summary_csv):
    df = pd.read_csv(summary_csv)
    df = df[df['graph'].isin(PAPER_GRAPHS)].copy()
    feasible = df['feasible_flag'].astype(str).str.lower() != 'false' if 'feasible_flag' in df else True
    complete = sum(df[c].fillna(1) for c in ('missing', 'duplicate', 'robot_mismatch', 'precedence')) == 0
    # solved: complete solution (every request served once, by one robot, in order); valid: also no violation
    df['solved'] = complete & df['failed_event_time'].isna() & feasible
    df['invalid'] = df['solved'] & ~df['valid'].fillna(False).astype(bool)
    df['optimal_calls_pct'] = 100 * df['n_calls_optimal'] / df['n_calls']
    return df


def wide(df, data_set, group, column):
    """instance x algorithm table of `column` for the algorithms of `group` present in `data_set`"""
    algorithms = {name: prefix for name, prefix in GROUPS[group].items()
                  if ((df['set'] == data_set) & (df['algorithm'] == prefix)).any()}
    sub = df[(df['set'] == data_set) & df['algorithm'].isin(algorithms.values())]
    table = sub.pivot_table(index=CELL + ['seed'], columns='algorithm', values=column, aggfunc='first',
                            dropna=False)
    # reindex: all-NaN columns (e.g. no solver statistics in the paper outputs) are dropped by pivot_table
    return table.reindex(columns=list(algorithms.values())).rename(columns={p: n for n, p in algorithms.items()})


def common_subset(solved):
    """Instances solved by the MILP-based algorithms (the only ones that can end without a solution)"""
    exact = [a for a in ('MILP', 'WS-MILP') if a in solved.columns]
    return solved[exact or list(solved.columns)].all(axis=1)


def instance_universe(df, data_set):
    """All instances of a set (seen with any algorithm): missing outputs count as unsolved"""
    return df[df['set'] == data_set][CELL + ['seed']].drop_duplicates().set_index(CELL + ['seed']).index


# ---------------------------------------------------------------------------------------------------------------------
# Tables

def table3(df, data_set, group, out_dir):
    """Table 3 revised: costs and times on the common solved subset, solved counts, imputed times"""
    solved = wide(df, data_set, group, 'solved').reindex(instance_universe(df, data_set)).fillna(False).astype(bool)
    if solved.shape[1] < 2:
        return
    cost = wide(df, data_set, group, 'cost').reindex(solved.index)
    time = wide(df, data_set, group, 'time_per_request').reindex(solved.index)
    optimal = wide(df, data_set, group, 'optimal_calls_pct').reindex(solved.index)
    invalid = wide(df, data_set, group, 'invalid').reindex(solved.index).fillna(False).astype(bool)
    common = common_subset(solved)
    rows = {}
    for cell, idx in solved.groupby(level=CELL).groups.items():
        row = {('', 'n'): len(idx), ('', 'common'): int(common.loc[idx].sum())}
        for a in solved.columns:
            in_common = idx[common.loc[idx].values]
            row[(a, 'cost')] = cost.loc[in_common, a].mean()
            row[(a, 'time')] = time.loc[in_common, a].mean()
            row[(a, 'solved')] = int(solved.loc[idx, a].sum())
            if invalid[a].any():
                row[(a, 'invalid')] = int(invalid.loc[idx, a].sum())
            # time with TIME_LIMIT per request imputed to unsolved instances
            row[(a, 'time_imp')] = time.loc[idx, a].where(solved.loc[idx, a], TIME_LIMIT).mean()
            if optimal[a].notna().any():
                row[(a, '%opt_calls')] = optimal.loc[idx, a].mean()
        for a in ('WS-MILP', 'MCFI', 'MCFI+R'):  # algorithms that always solve: mean over all instances too
            if a in solved.columns:
                row[(a, 'cost_all')] = cost.loc[idx, a][solved.loc[idx, a]].mean()
        rows[cell] = row
    table = pd.DataFrame.from_dict(rows, orient='index')
    table.index.names = CELL
    save(table, out_dir, f'table3_{group}_{data_set}',
         f'Mean cost and time per request ({group}, {data_set}). cost/time: common subset of instances solved by '
         f'the MILP-based algorithms; solved: complete solution (every request served); invalid: complete but '
         f'violating a constraint (L4 verifier); time\\_imp: {TIME_LIMIT} s per request imputed to unsolved '
         f'instances; cost\\_all: all solved instances; \\%opt\\_calls: share of solver calls ending OPTIMAL.')


def deltas(df, data_set, group, out_dir):
    """delta(A|B) per cell and overall, on the instances solved by both A and B; speed-ups"""
    cost = wide(df, data_set, group, 'cost')
    solved = wide(df, data_set, group, 'solved').reindex(cost.index).fillna(False).astype(bool)
    time = wide(df, data_set, group, 'time_per_request').reindex(cost.index)
    pairs = [(a, b) for a, b in PAIRS if a in cost and b in cost]
    if not pairs:
        return
    columns = {}
    for a, b in pairs:
        both = solved[a] & solved[b]
        delta = (100 * (cost[a] - cost[b]) / cost[b])[both]
        key = f'd({a}|{b})'
        columns[(key, 'mean')] = delta.groupby(level=CELL).mean()
        columns[(key, 'min')] = delta.groupby(level=CELL).min()
        columns[(key, 'max')] = delta.groupby(level=CELL).max()
        columns[(key, 'n')] = delta.groupby(level=CELL).size()
        columns[(f'speed-up({a}|{b})', '')] = (time[b][both].groupby(level=CELL).mean()
                                               / time[a][both].groupby(level=CELL).mean())
    table = pd.DataFrame(columns)
    overall = {}
    for (key, stat), series in columns.items():
        if key.startswith('d('):
            a, b = key[2:-1].split('|')
            both = solved[a] & solved[b]
            values = (100 * (cost[a] - cost[b]) / cost[b])[both]
            overall[(key, stat)] = {'mean': values.mean(), 'min': values.min(), 'max': values.max(),
                                    'n': len(values)}[stat]
    table.loc[('All', '', ''), list(overall)] = pd.Series(overall)
    save(table, out_dir, f'deltas_{group}_{data_set}',
         f'Relative cost differences d(A|B) = 100 (C_A - C_B) / C_B (\\%) on the instances solved by both, and '
         f'speed-up(A|B) = mean time per request of B / of A ({group}, {data_set}). Negative d: A cheaper.')


def claims(df, out_dir):
    """Numbers quoted in the text (Section 5.2, abstract): recomputed with explicit formulas"""
    rows = []
    for group in ('paper', 'v2-hard', 'v2-soft'):
        cost = wide(df, 'original', group, 'cost')
        solved = wide(df, 'original', group, 'solved').reindex(cost.index).fillna(False).astype(bool)
        grids = cost.index.get_level_values('graph').isin(['SparseGrid', 'DenseGrid'])

        def add(claim, a, b, mask, stat):
            if a not in cost or b not in cost:
                return
            both = solved[a] & solved[b] & mask
            values = 100 * (cost[a] - cost[b]) / cost[b]
            value = getattr(values[both], stat)()
            where = values[both].idxmax() if stat == 'max' else (values[both].idxmin() if stat == 'min' else '')
            rows.append(dict(group=group, claim=claim, formula=f'{stat} 100(C_{a}-C_{b})/C_{b}', value=value,
                             n=int(both.sum()), instance=where))

        add('SCFI excess over WS-MILP (paper: "up to 100% reduction")', 'SCFI', 'WS-MILP', grids | True, 'max')
        add('Reduction of WS-MILP w.r.t. SCFI', 'WS-MILP', 'SCFI', grids | True, 'min')
        add('MCFI vs MILP on grids (paper: "18.33%")', 'MCFI', 'MILP', grids, 'mean')
        add('MCFI vs MILP, all graphs', 'MCFI', 'MILP', grids | True, 'mean')
        add('WS-MILP vs MCFI on grids (paper: "about 20%")', 'WS-MILP', 'MCFI', grids, 'mean')
        add('MCFI+R vs MILP on grids', 'MCFI+R', 'MILP', grids, 'mean')
        if 'MILP' in solved:
            universe = instance_universe(df, 'original')
            milp = solved['MILP'].reindex(universe).fillna(False)
            rows.append(dict(group=group, claim='Instances without a complete MILP solution', formula='count',
                             value=int((~milp).sum()), n=len(universe), instance=''))
    if rows:
        save(pd.DataFrame(rows), out_dir, 'claims', 'Figures quoted in the text, recomputed from the verified costs.')


def backup_stats(df, out_dir):
    """R1.3: backup robot activations per cell and algorithm"""
    sub = df[df['backup_tasks'].notna()]
    table = sub.groupby(['set', 'algorithm'] + CELL).agg(
        instances=('instance', 'size'), with_backup=('backup_used', 'sum'), backup_tasks=('backup_tasks', 'sum'))
    table = table[table.groupby(level=['set', 'algorithm'])['with_backup'].transform('sum') > 0]
    if len(table):
        save(table, out_dir, 'backup_stats',
             'Backup robot (use cost x1000): instances where it serves at least one task, and tasks it serves.')


def anomalies(df, out_dir):
    """Instances where WS-MILP ends with a higher cost than MILP or than the MCFI it starts from"""
    rows = []
    for group in ('paper', 'v2-hard', 'v2-soft'):
        for data_set in df['set'].unique():
            cost = wide(df, data_set, group, 'cost')
            solved = wide(df, data_set, group, 'solved').reindex(cost.index).fillna(False).astype(bool)
            for other in ('MILP', 'MCFI'):
                if 'WS-MILP' not in cost or other not in cost:
                    continue
                worse = solved['WS-MILP'] & solved[other] & (cost['WS-MILP'] > cost[other] + 1e-6)
                for idx in cost.index[worse]:
                    rows.append(dict(group=group, set=data_set, **dict(zip(CELL + ['seed'], idx)),
                                     comparison=f'WS-MILP > {other}', ws_cost=cost.loc[idx, 'WS-MILP'],
                                     other_cost=cost.loc[idx, other],
                                     delta=100 * (cost.loc[idx, 'WS-MILP'] - cost.loc[idx, other])
                                     / cost.loc[idx, other]))
    if rows:
        save(pd.DataFrame(rows), out_dir, 'anomalies', 'Instances where WS-MILP ends with a higher cost.')


def budget_table(df, out_dir):
    """R3.7: MILP and WS-MILP with 10, 60 and 300 s per event (stage budget)"""
    for mode in ('hard', 'soft'):
        algorithms = {(name, budget): f'{prefix}-v2-{mode}' + ('' if budget == 300 else f'-T{budget}')
                      for name, prefix in (('MILP', 'MILP'), ('WS-MILP', 'WS')) for budget in (10, 60, 300)}
        sub = df[(df['set'] == 'original') & df['algorithm'].isin(algorithms.values())]
        if not sub['algorithm'].str.contains('-T').any():
            continue
        sub = sub[sub['algorithm'].map({v: k for k, v in algorithms.items()}).notna()].copy()
        sub['key'] = sub['algorithm'].map({v: k for k, v in algorithms.items()})
        instances = sub[sub['algorithm'].str.contains('-T')][CELL + ['seed']].drop_duplicates()
        sub = sub.merge(instances, on=CELL + ['seed'])
        reference = sub[sub['key'] == ('MILP', 300)].set_index(CELL + ['seed'])['cost']
        rows = {}
        for key, part in sub.groupby('key'):
            part = part.set_index(CELL + ['seed'])
            both = part['solved'] & reference.reindex(part.index).notna()
            delta = 100 * (part['cost'] - reference.reindex(part.index)) / reference.reindex(part.index)
            rows[key] = {'instances': len(part), 'solved': int(part['solved'].sum()),
                         'd(vs MILP 300s) mean %': delta[both].mean(), 'mean cost (solved)': part['cost'][part['solved']].mean(),
                         '%opt_calls': part['optimal_calls_pct'].mean(), 'time/request': part['time_per_request'].mean(),
                         'no-incumbent calls': part['n_calls_no_incumbent'].sum()}
        table = pd.DataFrame.from_dict(rows, orient='index')
        table.index.names = ['algorithm', 'T (s)']
        save(table, out_dir, f'budget_{mode}',
             f'Computational budget per event ({mode} time windows; grids, wide windows, 6 and 9 robots). '
             f'd: 100 (C - C_MILP,300s) / C_MILP,300s on instances solved by both.')


def symmetry_table(df, out_dir):
    """N7: MILP and WS-MILP with and without symmetry breaking on the same instances"""
    for mode in ('hard', 'soft'):
        rows = {}
        for name, prefix in (('MILP', 'MILP'), ('WS-MILP', 'WS')):
            base, sb = f'{prefix}-v2-{mode}', f'{prefix}-v2-{mode}-sb'
            sub = df[(df['set'] == 'original') & df['algorithm'].isin([base, sb])]
            if not (sub['algorithm'] == sb).any():
                continue
            instances = sub[sub['algorithm'] == sb][CELL + ['seed']].drop_duplicates()
            sub = sub.merge(instances, on=CELL + ['seed'])
            for variant, part in sub.groupby('algorithm'):
                for robots, p in part.groupby('robots'):
                    rows[(name, 'with N7' if variant == sb else 'without', robots)] = {
                        'instances': len(p), 'solved': int(p['solved'].sum()),
                        'mean cost (solved by both)': np.nan, '%opt_calls': p['optimal_calls_pct'].mean(),
                        'mean gap': p['mean_gap'].mean(), 'mean solver time/call': p['mean_solver_time'].mean(),
                        'no-incumbent calls': p['n_calls_no_incumbent'].sum()}
            cost = sub.pivot_table(index=CELL + ['seed'], columns='algorithm', values='cost')
            ok = sub.pivot_table(index=CELL + ['seed'], columns='algorithm', values='solved').fillna(0).astype(bool)
            if base in cost and sb in cost:
                both = ok[base] & ok[sb]
                for variant in (base, sb):
                    for robots, values in cost[variant][both].groupby(level='robots'):
                        rows[(name, 'with N7' if variant == sb else 'without', robots)]['mean cost (solved by both)'] = values.mean()
        if rows:
            table = pd.DataFrame.from_dict(rows, orient='index')
            table.index.names = ['algorithm', 'variant', 'robots']
            save(table, out_dir, f'symmetry_{mode}', f'Symmetry breaking (N7), {mode} time windows, grids.')


def set_comparison(df, out_dir):
    """Delay-prone and heterogeneous sets: cost decomposition and delta vs MILP per set"""
    for data_set in [s for s in df['set'].unique() if s != 'original']:
        for group in ('v2-hard', 'v2-soft'):
            cost = wide(df, data_set, group, 'cost')
            if cost.shape[1] < 2:
                continue
            algorithms = GROUPS[group]
            sub = df[(df['set'] == data_set) & df['algorithm'].isin(algorithms.values())].copy()
            sub['name'] = sub['algorithm'].map({p: n for n, p in algorithms.items()})
            table = sub.groupby(['graph', 'robots', 'name']).agg(
                cost=('cost', 'mean'), travel=('travel_cost', 'mean'), fixed=('fixed_cost', 'mean'),
                backup=('backup_use_cost', 'mean'), delay=('delay_cost', 'mean'), late_visits=('late_visits', 'mean'),
                max_delay=('max_delay', 'mean'), solved=('solved', 'sum'), opt_calls=('optimal_calls_pct', 'mean'),
                time_per_request=('time_per_request', 'mean'))
            if 'MILP' in cost:
                solved = wide(df, data_set, group, 'solved').reindex(cost.index).fillna(False).astype(bool)
                for a in cost.columns:
                    both = solved[a] & solved['MILP']
                    delta = (100 * (cost[a] - cost['MILP']) / cost['MILP'])[both].groupby(level=['graph', 'robots']).mean()
                    for (graph, robots), value in delta.items():
                        table.loc[(graph, robots, a), 'd(vs MILP) %'] = value
            save(table, out_dir, f'set_{group}_{data_set}',
                 f'Cost decomposition (means) and d(A|MILP) on instance set {data_set} ({group}).')


# ---------------------------------------------------------------------------------------------------------------------
# Figure 7

def figure7(df, out_dir):
    """Fig. 7 revised: d(WS-MILP|MCFI) per instance, sorted, one series per graph"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    colors = {'Random': '#2a78d6', 'Polar': '#eb6834', 'SparseGrid': '#1baf7a', 'DenseGrid': '#eda100'}
    markers = {'Random': 'o', 'Polar': 's', 'SparseGrid': '^', 'DenseGrid': 'D'}
    for group in ('paper', 'v2-hard', 'v2-soft'):
        cost = wide(df, 'original', group, 'cost')
        if 'WS-MILP' not in cost or 'MCFI' not in cost:
            continue
        solved = wide(df, 'original', group, 'solved').reindex(cost.index).fillna(False).astype(bool)
        delta = (100 * (cost['WS-MILP'] - cost['MCFI']) / cost['MCFI'])[solved['WS-MILP'] & solved['MCFI']]
        # One panel per graph (Random and Polar overlap at 0 in a single panel)
        fig, axes = plt.subplots(1, len(PAPER_GRAPHS), figsize=(9, 3.2), sharey=True)
        for ax, graph in zip(axes, PAPER_GRAPHS):
            values = np.sort(delta[delta.index.get_level_values('graph') == graph].values)
            ax.plot(range(len(values)), values, linestyle='none', marker=markers[graph], markersize=4.5,
                    color=colors[graph], markeredgecolor='#fcfcfb', markeredgewidth=0.6)
            ax.axhline(0, color='#6b6b66', linewidth=1)
            ax.set_title(f'{graph} ({len(values)})', fontsize=9)
            ax.set_xlabel('Instances, sorted', fontsize=8)
            ax.grid(axis='y', color='#e4e3df', linewidth=0.6)
            ax.tick_params(labelsize=8)
            for side in ('top', 'right'):
                ax.spines[side].set_visible(False)
        axes[0].set_ylabel(r'$100\,(C_{WS} - C_{MCFI})\,/\,C_{MCFI}$ (%)', fontsize=8)
        fig.suptitle('WS-MILP vs MCFI cost difference per instance (negative: WS-MILP cheaper)', fontsize=9,
                     x=0.01, ha='left', color='#4a4a46')
        fig.tight_layout()
        for ext in ('pdf', 'png'):
            fig.savefig(os.path.join(out_dir, f'fig7_{group}.{ext}'), dpi=200)
        plt.close(fig)
        written.append(f'fig7_{group}')


# ---------------------------------------------------------------------------------------------------------------------
# Instance tables (Section 5.1, R1.3 and R4.5)

def instance_tables(input_root, out_dir):
    params, arrivals = [], []
    for graph, directory in GRAPH_DIRS.items():
        for tw, suffix in (('narrow', ''), ('wide', '_bigTW')):
            folders = sorted(glob.glob(os.path.join(input_root, directory, f'*HR_6Q_50RQT_2q{suffix}_[0-9]')))
            if not folders:
                continue
            widths, gaps, notice, autonomy = [], [], [], []
            for folder in folders:
                requests = pd.read_csv(os.path.join(folder, 'requests.csv')).sort_values('event_time')
                robots = pd.read_csv(os.path.join(folder, 'robots.csv'))
                widths += list(requests['pickup_max_time'] - requests['pickup_min_time'])
                gaps += list(requests['event_time'].diff().dropna())
                notice += list(requests['pickup_min_time'] - requests['event_time'])
                autonomy += list(robots.loc[~robots['name'].str.contains('extra'), 'autonomy'])
            distances = pd.read_csv(os.path.join(folders[0], 'vid_distances.csv'), index_col=0)
            gaps = np.array(gaps)
            params.append({'graph': graph, 'tw': tw, 'D (max distance = max travel time)': distances.values.max(),
                           'window width min': min(widths), 'window width mean': np.mean(widths),
                           'window width max': max(widths), 'autonomy min': min(autonomy),
                           'autonomy max': max(autonomy)})
            arrivals.append({'graph': graph, 'tw': tw, 'inter-arrival mean': gaps.mean(),
                             'inter-arrival sd': gaps.std(), 'inter-arrival CV': gaps.std() / gaps.mean(),
                             'advance notice mean': np.mean(notice), 'advance notice max': max(notice)})
    if params:
        save(pd.DataFrame(params).set_index(['graph', 'tw']), out_dir, 'instance_parameters',
             'Instance parameters per graph and time-window width. All instances: speed 1, cost per distance 1, '
             'capacity 6, demand 2, service time 1, use cost 10 (backup 10000), delay penalty 50.')
        save(pd.DataFrame(arrivals).set_index(['graph', 'tw']), out_dir, 'arrival_process',
             'Arrival process: inter-arrival times of consecutive requests and advance notice '
             '(pickup earliest time - appearance time).')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('summary_csv')
    parser.add_argument('out_dir')
    parser.add_argument('--input-root', default=os.path.join('input', 'AFDPDP-Instances'))
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    df = load(args.summary_csv)
    for group in GROUPS:
        for data_set in df['set'].unique():
            table3(df, data_set, group, args.out_dir)
            deltas(df, data_set, group, args.out_dir)
    claims(df, args.out_dir)
    backup_stats(df, args.out_dir)
    anomalies(df, args.out_dir)
    budget_table(df, args.out_dir)
    symmetry_table(df, args.out_dir)
    set_comparison(df, args.out_dir)
    figure7(df, args.out_dir)
    instance_tables(args.input_root, args.out_dir)
    print(f"Written to {args.out_dir}:\n  " + "\n  ".join(written))


if __name__ == '__main__':
    main()
