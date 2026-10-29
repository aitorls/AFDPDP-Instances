"""
[L5] Paper-format tables and figures of the revised manuscript (decision D1: v2 soft time windows), from the L2 summary.

Same data and conventions as make_tables.py (verified cost, `solved` and common subset), but written with the layout
of the manuscript and in red (revision markup). Runs that are not in the summary yet are shown as "n/a" (pending).

Usage (cwd = repo root):
  1. Per-call data of WS-MILP and MILP (Table 6, Figs. 5 and 6), where the output JSON files are:
       python tools/make_paper_tables.py extract-calls input/AFDPDP-Instances results/revision/campaign/calls.csv
  2. Tables and figures:
       python tools/make_paper_tables.py tables results/revision/campaign/summary.csv paper/ECAI_2025 \
           [--calls results/revision/campaign/calls.csv]
Writes <paper>/tables/revision/*.tex, <paper>/figures/revision/*.png and prints the figures quoted in the text.
Without --calls, Table 6 and Figs. 5 and 6 are not generated.
"""
import argparse
import glob
import json
import os

import numpy as np
import pandas as pd

from make_tables import load, TIME_LIMIT

ALGS = {'SCFI': 'SCFI-v2-soft', 'MCFI': 'MCFI-v2-soft', 'MCFI+R': 'MCFIR-v2-soft', 'MILP': 'MILP-v2-soft',
        'WS-MILP': 'WS-v2-soft'}
GRAPHS = ['Random', 'Polar', 'SparseGrid', 'DenseGrid']
GRIDS = ['SparseGrid', 'DenseGrid']
KEY = ['graph', 'tw', 'robots', 'seed']
CELL = ['graph', 'tw', 'robots']


def frame(df, data_set, algs=ALGS):
    """instance x (column, algorithm) for the algorithms of the revised paper; absent rows = run pending"""
    sub = df[(df['set'] == data_set) & df['algorithm'].isin(algs.values())]
    names = {p: n for n, p in algs.items()}
    sub = sub.assign(alg=sub['algorithm'].map(names))
    wide = sub.pivot_table(index=KEY, columns='alg', aggfunc='first', dropna=False,
                           values=['cost', 'time_per_request', 'solved', 'delay', 'late_visits', 'optimal_calls_pct',
                                   'backup_used'])
    universe = df[df['set'] == data_set][KEY].drop_duplicates().set_index(KEY).index
    return wide.reindex(universe).sort_index()


def run(w, a):
    return w['solved'][a].notna()


def solved(w, a):
    return w['solved'][a].fillna(False).astype(bool)


def fmt(v, digits=1):
    return '--' if v is None or (isinstance(v, float) and np.isnan(v)) else f'{v:.{digits}f}'


def red_table(body):
    return '{\\color{red}\n' + body + '}\n'


# ---------------------------------------------------------------------------------------------------------------------

def table3(w, out):
    algs = list(ALGS)
    common = solved(w, 'MILP') & solved(w, 'WS-MILP')
    lines = []
    prev_graph = prev_tw = None
    for graph in GRAPHS:
        for tw in ('narrow', 'wide'):
            for robots in (3, 6, 9):
                idx = w.xs((graph, tw, robots), level=CELL, drop_level=False).index
                c = common.loc[idx]
                cells = [graph if graph != prev_graph else '', tw if (graph, tw) != prev_tw else '', str(robots),
                         str(len(idx)), str(int(c.sum()))]
                prev_graph, prev_tw = graph, (graph, tw)
                for a in algs:
                    ran = run(w, a).loc[idx]
                    if not ran.all():
                        cells += ['n/a', 'n/a'] + (['n/a'] if a in ('MILP', 'WS-MILP') else [])
                        continue
                    cost = w['cost'][a].loc[idx][c.values].mean() if c.any() else np.nan
                    time = w['time_per_request'][a].loc[idx].where(solved(w, a).loc[idx], TIME_LIMIT).mean()
                    cells += [fmt(cost), fmt(time, 2)]
                    if a in ('MILP', 'WS-MILP'):
                        cells.append(str(int(solved(w, a).loc[idx].sum())))
                lines.append(' & '.join(cells) + r' \\')
            lines[-1] += r' \cline{2-20}' if tw == 'narrow' else r' \cline{1-20}'
    body = r"""\begin{table}[tbp]
\caption{Aggregated benchmark results (soft time windows). Each row corresponds to a combination of graph topology (Graph), time-window width (TW), and number of robots (Robots); $\#$ is the number of instances and $\#_c$ the number of instances solved by both MILP and WS-MILP. Cost is the mean cumulative cost over these $\#_c$ common instances; Time is the mean computation time per replanning event (s) over all instances, with the time limit imputed to unsolved instances; Solved is the number of instances with a complete solution. MCFI+R denotes MCFI with reassignment (Section~\ref{sec:mcfi_reassignment}).}
\label{tab:all_results}
\resizebox{\textwidth}{!} {
\begin{tabular}{llccc|rr|rr|rr|rrr|rrr}
\toprule
 & & & & & \multicolumn{2}{c|}{SCFI} & \multicolumn{2}{c|}{MCFI} & \multicolumn{2}{c|}{MCFI+R} & \multicolumn{3}{c|}{MILP} & \multicolumn{3}{c}{WS-MILP} \\
Graph & TW & Robots & $\#$ & $\#_c$ & Cost & Time & Cost & Time & Cost & Time & Cost & Time & Solved & Cost & Time & Solved \\
\midrule
""" + '\n'.join(lines).replace(r'\cline{2-20}', r'\cline{2-17}').replace(r'\cline{1-20}', r'\cline{1-17}') + r"""
\bottomrule
\end{tabular}
}
\end{table}
"""
    write(out, 'table3.tex', red_table(body))


def instance_rows(w, graph, tws, with_tw):
    algs = ['SCFI', 'MCFI', 'MILP', 'WS-MILP']
    lines = []
    for tw in tws:
        for robots in (3, 6, 9):
            for seed in range(10):
                key = (graph, tw, robots, seed)
                costs = {a: w['cost'][a].get(key, np.nan) if solved(w, a).get(key, False) else np.nan for a in algs}
                best = np.nanmin(list(costs.values()))
                cells = ([tw if robots == 3 and seed == 0 else ''] if with_tw else []) + \
                        [str(robots) if seed == 0 else '', str(seed)]
                for a in algs:
                    if not run(w, a).get(key, False):
                        cells += ['n/a', 'n/a']
                    elif not solved(w, a).get(key, False):
                        cells += ['--', '--']
                    else:
                        cost = fmt(costs[a])
                        cells += [r'\textbf{' + cost + '}' if costs[a] == best else cost,
                                  fmt(w['time_per_request'][a].get(key), 2)]
                lines.append(' & '.join(cells) + r' \\')
            lines[-1] += r' \hline' if robots < 9 else ''
    return lines


HEADER = (r" & Algorithm & \multicolumn{2}{c|}{SCFI} & \multicolumn{2}{c|}{MCFI} & \multicolumn{2}{c|}{MILP} & "
          r"\multicolumn{2}{c}{WS-MILP} \\")
CAPTION_TAIL = ("For each number of robots and instance index, the table reports the cumulative cost (Cost) and the mean "
                "computation time per replanning event in seconds (Time) achieved by each algorithm. The lowest cost "
                "per instance is highlighted in bold, while ``--'' denotes that the algorithm failed to produce a "
                "complete solution within the time limit per event.")


def tables45(w, out):
    for graph, label, name in (('SparseGrid', 'table:grid_wide_results', 'table4.tex'),
                               ('DenseGrid', 'table:symmetric_grid_wide_results', 'table5.tex')):
        body = (r"\begin{table}[htb!]" + "\n\\centering\n" +
                f"\\caption{{Detailed \\textit{{{graph}}}-wide results per instance (soft time windows). {CAPTION_TAIL}}}\n"
                f"\\label{{{label}}}\n\\begin{{tabular}}{{cc|rr|rr|rr|rr}}\n\\toprule\n{HEADER}\n"
                r"Robots & Instance & Cost & Time & Cost & Time & Cost & Time & Cost & Time \\" + "\n\\midrule\n" +
                '\n'.join(instance_rows(w, graph, ['wide'], False)) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
        write(out, name, red_table(body))


def appendix(w, out):
    parts = []
    for graph, label in (('SparseGrid', 'table:grid_results'), ('DenseGrid', 'table:BIG_VID_results')):
        head = (f"{HEADER.replace(' & Algorithm', ' &  & Algorithm')}\n"
                r"TW & Robots & Instance & Cost & Time & Cost & Time & Cost & Time & Cost & Time \\")
        parts.append(
            "\\begin{longtable}{ccc|rr|rr|rr|rr}\n"
            f"\\caption{{Detailed \\textit{{{graph}}} results per instance (soft time windows). {CAPTION_TAIL}}}\n"
            f"\\label{{{label}}} \\\\\n\\toprule\n{head}\n\\midrule\n\\endfirsthead\n"
            f"\\caption*{{Table \\ref{{{label}}} (continued)}} \\\\\n\\toprule\n{head}\n\\midrule\n\\endhead\n"
            "\\midrule\n\\multicolumn{11}{r}{Continues on next page...} \\\\\n\\endfoot\n\\bottomrule\n\\endlastfoot\n" +
            '\n'.join(instance_rows(w, graph, ['narrow', 'wide'], True)) + "\n\\end{longtable}\n")
    write(out, 'appendix_tables.tex', red_table('\n'.join(parts)))


def table7(w, out):
    algs = ['MCFI', 'MCFI+R', 'MILP', 'WS-MILP']
    lines = []
    for graph in GRAPHS:
        for tw in ('narrow', 'wide'):
            for robots in (3, 6, 9):
                idx = w.xs((graph, tw, robots), level=CELL, drop_level=False).index
                cells, any_delay = [graph, tw, str(robots)], False
                for a in algs:
                    if not run(w, a).loc[idx].all():
                        cells += ['n/a', 'n/a']
                        continue
                    delay = w['delay'][a].loc[idx][solved(w, a).loc[idx].values]
                    late = delay[delay > 0]
                    any_delay |= len(late) > 0
                    cells += [str(len(late)), fmt(late.mean() if len(late) else 0.0)]
                if any_delay:
                    lines.append(' & '.join(cells) + r' \\')
    body = (r"\begin{table}[htb]" + "\n\\centering\n"
            r"\caption{Instances with delays (soft time windows): number of instances with a positive total delay "
            r"(Count) and mean total delay of those instances, in time units (Delay). Only the combinations with "
            r"delays are listed.}" + "\n\\label{tab:delayed}\n\\resizebox{\\textwidth}{!}{\n"
            r"\begin{tabular}{lll|rr|rr|rr|rr}" + "\n\\toprule\n" +
            r" & & & \multicolumn{2}{c|}{MCFI} & \multicolumn{2}{c|}{MCFI+R} & \multicolumn{2}{c|}{MILP} & "
            r"\multicolumn{2}{c}{WS-MILP} \\" + "\n"
            r"Graph & TW & Robots & Count & Delay & Count & Delay & Count & Delay & Count & Delay \\" +
            "\n\\midrule\n" + '\n'.join(lines) + "\n\\bottomrule\n\\end{tabular}\n}\n\\end{table}\n")
    write(out, 'table7.tex', red_table(body))


def delay_table(df, out):
    algs = ['MCFI', 'MCFI+R', 'MILP', 'WS-MILP']
    lines = []
    for data_set, alpha in (('tw_0.5', '0.5'), ('tw_0.25', '0.25')):
        w = frame(df, data_set, {a: ALGS[a] for a in algs})
        for graph in GRIDS:
            for robots in (3, 6):
                try:
                    idx = w.xs((graph, 'narrow', robots), level=CELL, drop_level=False).index
                except KeyError:
                    continue
                ok = pd.concat([solved(w, a).loc[idx] for a in algs], axis=1).all(axis=1)
                ref = w['cost']['MILP'].loc[idx][ok.values]
                cells = [alpha, graph, str(robots), str(int(ok.sum()))]
                for a in algs:
                    cost = w['cost'][a].loc[idx][ok.values]
                    cells.append(fmt(cost.mean(), 0))
                    if a != 'MILP':
                        cells.append(fmt((100 * (cost - ref) / ref).mean(), 1))
                cells.append(fmt(w['optimal_calls_pct']['MILP'].loc[idx].mean(), 1))
                cells.append(fmt(100 * (w['delay']['MILP'].loc[idx][ok.values] * 50 / ref).mean(), 1))
                lines.append(' & '.join(cells) + r' \\')
    body = (r"\begin{table}[htb]" + "\n\\centering\n"
            r"\caption{Delay-prone instances: pickup windows of width $\alpha D$ (narrow instances of the grid graphs). "
            r"Mean cumulative cost of each algorithm and, for the heuristics and WS-MILP, mean relative difference "
            r"with respect to MILP, $\Delta$ (\%). \%Opt: percentage of MILP calls solved to optimality (gap below "
            r"1\%). Delay share: percentage of the MILP cost due to delay penalties.}" +
            "\n\\label{tab:delay_experiment}\n\\resizebox{\\textwidth}{!}{\n"
            r"\begin{tabular}{lllc|rr|rr|r|rr|rr}" + "\n\\toprule\n" +
            r" & & & & \multicolumn{2}{c|}{MCFI} & \multicolumn{2}{c|}{MCFI+R} & MILP & \multicolumn{2}{c|}{WS-MILP} & "
            r"\multicolumn{2}{c}{MILP} \\" + "\n"
            r"$\alpha$ & Graph & Robots & $\#$ & Cost & $\Delta$ & Cost & $\Delta$ & Cost & Cost & $\Delta$ & "
            r"\%Opt & Delay share \\" + "\n\\midrule\n" + '\n'.join(lines) +
            "\n\\bottomrule\n\\end{tabular}\n}\n\\end{table}\n")
    write(out, 'table_delay.tex', red_table(body))


def rel(w, a, b, idx):
    """mean relative difference (%) of a with respect to b over the instances of idx solved by both, and their count"""
    ok = (solved(w, a) & solved(w, b)).loc[idx]
    ca, cb = w['cost'][a].loc[idx][ok], w['cost'][b].loc[idx][ok]
    return (100 * (ca - cb) / cb).mean(), int(ok.sum())


def budget_table(df, out):
    """[N4] MILP and WS-MILP with 10, 60 and 300 s per event on the grid instances with wide windows and 6 or 9 robots"""
    algs = {'MCFI': ALGS['MCFI'], 'MCFI+R': ALGS['MCFI+R']}
    for t, suffix in (('10', '-T10'), ('60', '-T60'), ('300', '')):
        algs[f'MILP{t}'] = ALGS['MILP'] + suffix
        algs[f'WS{t}'] = ALGS['WS-MILP'] + suffix
    w = frame(df, 'original', algs)
    w = w[w.index.get_level_values('graph').isin(GRIDS) & (w.index.get_level_values('tw') == 'wide')
          & w.index.get_level_values('robots').isin([6, 9])]
    idx = w.index
    lines = []
    for t in ('10', '60', '300'):
        milp, ws = f'MILP{t}', f'WS{t}'
        d_milp, n_milp = rel(w, ws, milp, idx)
        lines.append(' & '.join([t, f'{int(solved(w, milp).sum())}/{len(idx)}', fmt(w['time_per_request'][milp].mean()),
                                 f'{int(solved(w, ws).sum())}/{len(idx)}', fmt(w['time_per_request'][ws].mean()),
                                 fmt(rel(w, ws, 'MCFI', idx)[0]), fmt(rel(w, ws, 'MCFI+R', idx)[0]),
                                 f'{fmt(d_milp)} ({n_milp})']) + r' \\')
    print(f"budget: MCFI time {w['time_per_request']['MCFI'].mean():.2f} s, MCFI+R time "
          f"{w['time_per_request']['MCFI+R'].mean():.2f} s, d(MCFI+R|MCFI) {rel(w, 'MCFI+R', 'MCFI', idx)[0]:.1f}, "
          f"MILP10 backup {int((w['backup_used']['MILP10'] == True).sum())}")
    body = (r"\begin{table}[htb]" + "\n\\centering\n"
            r"\caption{Computational budget per replanning event, $T$, on the grid instances with wide windows and 6 or 9 "
            r"robots (40 instances). Solved: instances completed by the method. Time: mean computation time per request "
            r"(s). $\Delta$: mean relative cost difference (\%) of WS-MILP with respect to MCFI, MCFI+R and the "
            r"stand-alone MILP with the same budget (number of instances solved by both in parentheses). MCFI and "
            r"MCFI+R take 0.3 and 2.4~s per request.}" +
            "\n\\label{tab:budget}\n"
            r"\begin{tabular}{r|rr|rrrrr}" + "\n\\toprule\n" +
            r" & \multicolumn{2}{c|}{MILP} & \multicolumn{5}{c}{WS-MILP} \\" + "\n"
            r"$T$ (s) & Solved & Time & Solved & Time & $\Delta$ MCFI & $\Delta$ MCFI+R & $\Delta$ MILP \\" +
            "\n\\midrule\n" + '\n'.join(lines) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    write(out, 'table_budget.tex', red_table(body))


def hetero_table(df, out):
    """[N5] heterogeneous fleets: same 40 grid instances (wide windows, 6 or 9 robots) with three robot types"""
    algs = ['MCFI', 'MCFI+R', 'MILP', 'WS-MILP']
    w = frame(df, 'hetero', {a: ALGS[a] for a in algs})
    w0 = frame(df, 'original', {'MILP': ALGS['MILP']})
    lines = []
    for graph in GRIDS:
        for robots in (6, 9):
            try:
                idx = w.xs((graph, 'wide', robots), level=CELL, drop_level=False).index
            except KeyError:
                continue
            lines.append(' & '.join([graph, str(robots), fmt(w['cost']['MCFI'].loc[idx].mean(), 0),
                                     fmt(rel(w, 'MCFI+R', 'MCFI', idx)[0]), fmt(rel(w, 'WS-MILP', 'MCFI', idx)[0]),
                                     f'{int(solved(w, "MILP").loc[idx].sum())}/{len(idx)}',
                                     f'{int(solved(w0, "MILP").loc[idx].sum())}/{len(idx)}']) + r' \\')
    idx = w.index
    print(f"hetero: d(MCFI+R|MCFI) {rel(w, 'MCFI+R', 'MCFI', idx)[0]:.1f}, d(WS|MCFI) "
          f"{rel(w, 'WS-MILP', 'MCFI', idx)[0]:.1f}, d(WS|MCFI+R) {rel(w, 'WS-MILP', 'MCFI+R', idx)[0]:.1f}, "
          f"MILP solved {int(solved(w, 'MILP').sum())}/{len(idx)}, d(WS|MILP) {rel(w, 'WS-MILP', 'MILP', idx)[0]:.1f}, "
          f"d(MCFI|MILP) {rel(w, 'MCFI', 'MILP', idx)[0]:.1f}, MILP backup {int((w['backup_used']['MILP'] == True).sum())}, "
          f"times {w['time_per_request'].mean().round(2).to_dict()}")
    body = (r"\begin{table}[htb]" + "\n\\centering\n"
            r"\caption{Heterogeneous fleets: grid instances with wide windows and 6 or 9 robots, in which the regular "
            r"robots cycle through three types (10 instances per row). Mean MCFI cost and mean relative cost difference "
            r"(\%) of MCFI+R and WS-MILP with respect to MCFI, over all instances. MILP solved: instances completed by "
            r"the stand-alone MILP with the heterogeneous fleets and with the original fleets.}" +
            "\n\\label{tab:hetero}\n"
            r"\begin{tabular}{lr|rrr|rr}" + "\n\\toprule\n" +
            r" & & MCFI & MCFI+R & WS-MILP & \multicolumn{2}{c}{MILP solved} \\" + "\n"
            r"Graph & Robots & Cost & $\Delta$ MCFI & $\Delta$ MCFI & Heterogeneous & Original \\" +
            "\n\\midrule\n" + '\n'.join(lines) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    write(out, 'table_hetero.tex', red_table(body))


# ---------------------------------------------------------------------------------------------------------------------

def figures(w, fig_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns

    grid = w[w.index.get_level_values('graph').isin(GRIDS)]
    rows = []
    for a in ALGS:
        ok = solved(grid, a)
        for key in grid.index[ok.values]:
            rows.append({'Algorithm': a, 'Robots - TW': f'{key[2]}-{key[1]}', 'order': (key[2], key[1]),
                         'Cost': grid['cost'][a][key], 'Time (s)': grid['time_per_request'][a][key]})
    data = pd.DataFrame(rows).sort_values('order')
    for y, name, log in (('Time (s)', 'time_per_request.png', True), ('Cost', 'cost_per_algorithm.png', False)):
        fig, ax = plt.subplots(figsize=(8, 4))
        sns.barplot(data=data, x='Robots - TW', y=y, hue='Algorithm', hue_order=list(ALGS), ax=ax, errorbar=('ci', 95))
        if log:
            ax.set_yscale('log')
        ax.set_title(('Average time per request' if log else 'Average cost') + ' by algorithm (SparseGrid and DenseGrid)')
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        fig.tight_layout()
        fig.savefig(os.path.join(fig_dir, name), dpi=200)
        plt.close(fig)
    # Fig. 7: d(WS-MILP|MCFI) per instance, sorted within each graph, one panel (layout of the original figure)
    both = solved(w, 'WS-MILP') & solved(w, 'MCFI')
    delta = (100 * (w['cost']['WS-MILP'] - w['cost']['MCFI']) / w['cost']['MCFI'])[both]
    fig, ax = plt.subplots(figsize=(10, 5))
    for graph, marker in zip(GRAPHS, ('o', 'X', 's', 'P')):
        values = np.sort(delta[delta.index.get_level_values('graph') == graph].values)
        ax.plot(range(len(values)), values, linestyle='none', marker=marker, markersize=6, label=graph)
    ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
    ax.set_title('WS-MILP vs MCFI cost difference by graph type')
    ax.set_xlabel('Instances (sorted by difference within each graph)')
    ax.set_ylabel('100 (C_WS-MILP - C_MCFI) / C_MCFI (%)')
    ax.legend(title='Graph type', loc='lower right')
    ax.grid(linewidth=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(fig_dir, 'cost_diff_WSMILP_MCFI.png'), dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------------------------------

def numbers(w, df):
    """Figures quoted in the text"""
    grid = w.index.get_level_values('graph').isin(GRIDS)

    def delta(a, b, mask=None):
        ok = solved(w, a) & solved(w, b)
        ok &= mask if mask is not None else True
        x = 100 * (w['cost'][a] - w['cost'][b]) / w['cost'][b]
        x = x[ok]
        return f'mean {x.mean():.1f} median {x.median():.1f} min {x.min():.1f} max {x.max():.1f} n {len(x)}'

    wide_tw = w.index.get_level_values('tw') == 'wide'
    print('runs present:', {a: int(run(w, a).sum()) for a in ALGS})
    print('MILP unsolved (of runs):', int((run(w, 'MILP') & ~solved(w, 'MILP')).sum()), 'of', int(run(w, 'MILP').sum()))
    print('WS unsolved (of runs):', int((run(w, 'WS-MILP') & ~solved(w, 'WS-MILP')).sum()))
    for a, b, m, tag in (('SCFI', 'WS-MILP', None, 'all'), ('WS-MILP', 'SCFI', None, 'all'),
                         ('MCFI', 'MILP', grid, 'grids'), ('MCFI', 'MILP', grid & wide_tw, 'grids wide'),
                         ('MCFI+R', 'MILP', grid, 'grids'), ('WS-MILP', 'MILP', grid, 'grids'),
                         ('WS-MILP', 'MILP', None, 'all'), ('WS-MILP', 'MCFI', grid, 'grids'),
                         ('WS-MILP', 'MCFI', grid & wide_tw, 'grids wide'), ('MCFI+R', 'MCFI', grid, 'grids'),
                         ('WS-MILP', 'MCFI+R', grid, 'grids'), ('MCFI', 'SCFI', grid, 'grids')):
        print(f'd({a}|{b}) {tag}:', delta(a, b, m))
    x = 100 * (w['cost']['SCFI'] - w['cost']['WS-MILP']) / w['cost']['WS-MILP']
    print('argmax d(SCFI|WS):', x.idxmax())
    ok = solved(w, 'WS-MILP') & solved(w, 'MCFI')
    print('WS > MCFI:', int((ok & (w['cost']['WS-MILP'] > w['cost']['MCFI'] + 1e-6)).sum()),
          'WS > MILP:', int((solved(w, 'WS-MILP') & solved(w, 'MILP') &
                             (w['cost']['WS-MILP'] > w['cost']['MILP'] + 1e-6)).sum()))
    for a in ALGS:
        t = w['time_per_request'][a][solved(w, a)]
        print(f'time {a}: min {t.min():.3f} max {t.max():.3f}; backup {int(w["backup_used"][a].fillna(0).sum())}')
    cells = w['time_per_request'].groupby(level=CELL).mean()
    print('max cell speed-up MILP/MCFI %.0f, WS/MCFI %.0f' % ((cells['MILP'] / cells['MCFI']).max(),
                                                               (cells['WS-MILP'] / cells['MCFI']).max()))


# ---------------------------------------------------------------------------------------------------------------------
# Per-call data (Table 6, Figs. 5 and 6)

GRAPH_DIRS = {'asymmetric_grid': 'SparseGrid', 'symmetric_grid': 'DenseGrid', 'random': 'Random', 'mountain': 'Polar'}


def latest(output_dir, prefix):
    files = [p for p in glob.glob(os.path.join(output_dir, f'{prefix}_*.json')) if '_iterations_' not in p]
    return max(files, key=os.path.getmtime) if files else None


def instance_key(name):
    parts = name.split('_')
    return int(parts[0].replace('HR', '')), 'wide' if 'bigTW' in name else 'narrow', int(parts[-1])


def extract_calls(root, out_csv):
    """One row per replanning call of WS-MILP (warm_start_iteration_stats) and MILP (solver_stats)"""
    rows = []
    for graph_dir, graph in GRAPH_DIRS.items():
        for instance_dir in sorted(glob.glob(os.path.join(root, graph_dir, '*HR_6Q_50RQT_2q*'))):
            robots, tw, seed = instance_key(os.path.basename(instance_dir))
            base = dict(graph=graph, tw=tw, robots=robots, seed=seed)
            path = latest(os.path.join(instance_dir, 'output'), ALGS['WS-MILP'])
            if path:
                solution = json.load(open(path))
                for k, c in enumerate(solution.get('warm_start_iteration_stats') or []):
                    rows.append(dict(base, algorithm='WS-MILP', call=k, active_tasks=c.get('active_tasks'),
                                     solver_time=c.get('MILP_runtime', c.get('MILP_time')), gap=c.get('MILP_gap'),
                                     status=c.get('MILP_status'), cost_H=c.get('cost_H'), cost_MILP=c.get('cost_MILP'),
                                     diff=c.get('diff'), final_cost=solution.get('cost')))
            path = latest(os.path.join(instance_dir, 'output'), ALGS['MILP'])
            if path:
                solution = json.load(open(path))
                pending, ongoing = solution.get('pending_tasks') or [], solution.get('ongoing_tasks') or []
                for k, c in enumerate(solution.get('solver_stats') or []):
                    # the call without incumbent (last one of a failed run) has no pending/ongoing entry
                    active = pending[k] + ongoing[k] if k < len(pending) and k < len(ongoing) else None
                    rows.append(dict(base, algorithm='MILP', call=k, active_tasks=active, solver_time=c.get('runtime'),
                                     gap=c.get('gap'), status=c.get('status'), event_time=c.get('event_time')))
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f'{len(rows)} calls -> {out_csv}')


def table6(calls, out):
    """Table 6: WS-MILP against its MCFI warm start, on the same states (trajectory of WS-MILP), grid graphs"""
    ws = calls[(calls['algorithm'] == 'WS-MILP') & calls['graph'].isin(GRIDS)].copy()
    for c in ('cost_H', 'diff', 'final_cost'):
        ws[c] = pd.to_numeric(ws[c], errors='coerce')
    # Improvement actually obtained by the MILP stage: 0 when the call has no incumbent (cost_MILP is a 1e9
    # sentinel) or when the MILP plan is worse than the warm start, since the MCFI plan is kept in both cases
    ws['diff'] = ws['diff'].where(pd.to_numeric(ws['cost_MILP'], errors='coerce') < 1e8, 0.0).fillna(0.0).clip(lower=0)
    ws['rel'] = ws['diff'] / ws['cost_H']
    rows = []
    for key, g in ws.groupby(['graph', 'robots', 'tw', 'seed']):
        improved = (g['diff'] > 0).sum()
        rows.append(dict(graph=key[0], robots=key[1], cost=g['final_cost'].iloc[0],
                         overall=100 * g['diff'].sum() / g['final_cost'].iloc[0],
                         win_rate=100 * improved / len(g), max_adv=100 * g['rel'].max(),
                         cond_adv=100 * g['rel'].sum() / improved if improved else 0.0))
    table = pd.DataFrame(rows).groupby(['graph', 'robots']).mean().reindex(GRIDS, level=0)
    lines = [f"{graph} & {robots} & {fmt(r.cost)} & {fmt(r.overall, 2)} & {fmt(r.win_rate, 2)} & "
             f"{fmt(r.max_adv, 2)} & {fmt(r.cond_adv, 2)} \\\\" for (graph, robots), r in table.iterrows()]
    body = (r"\begin{table}[htb]" + "\n"
            r"\caption{Comparison of mean improvements per instance between MCFI and WS-MILP in the grid graphs "
            r"(soft time windows), computed along the trajectory of WS-MILP.}" + "\n\\label{tab:mean_improvements}\n"
            r"\resizebox{\textwidth}{!} {" + "\n\\begin{tabular}{llrrrrr}\n\\toprule\n"
            r"Graph & Robots & Cost & Overall improvement & Iteration win rate & Max advantage & "
            r"Conditional advantage \\" + "\n\\midrule\n" + '\n'.join(lines) +
            "\n\\bottomrule\n\\end{tabular}\n}\n\\end{table}\n")
    write(out, 'table6.tex', red_table(body))


def call_figures(calls, fig_dir):
    """Figs. 5 and 6: mean time and gap per call against the number of active tasks, grid graphs, each method on
    its own trajectory"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns

    data = calls[calls['graph'].isin(GRIDS) & calls['active_tasks'].notna()].copy()
    data['Active tasks'] = data['active_tasks'].astype(int)
    data = data.rename(columns={'algorithm': 'Method', 'solver_time': 'Time (s)', 'gap': 'Gap'})
    for y, name, title in (('Time (s)', 'time_per_active_tasks.png', 'Mean solver time per call'),
                           ('Gap', 'gap_per_active_tasks.png', 'Mean optimality gap per call')):
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.barplot(data=data.dropna(subset=[y]), x='Active tasks', y=y, hue='Method', hue_order=['WS-MILP', 'MILP'],
                    errorbar=('ci', 95), ax=ax)
        ax.set_title(f'{title} by number of active tasks (SparseGrid and DenseGrid)')
        ax.grid(axis='y', linewidth=0.5)
        fig.tight_layout()
        fig.savefig(os.path.join(fig_dir, name), dpi=200)
        plt.close(fig)
    for a in ('WS-MILP', 'MILP'):
        d = data[data['Method'] == a]
        hit = d[d['Time (s)'] >= TIME_LIMIT - 1]['Active tasks']
        print(f'{a}: calls {len(d)}, optimal {100 * (d["status"] == "OPTIMAL").mean():.1f}%, '
              f'min active tasks of a call at the time limit: {hit.min() if len(hit) else None}')


def write(out, name, text):
    with open(os.path.join(out, name), 'w', encoding='utf-8') as f:
        f.write(text)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    extract = sub.add_parser('extract-calls')
    extract.add_argument('instances_root')
    extract.add_argument('calls_csv')
    tables = sub.add_parser('tables')
    tables.add_argument('summary_csv')
    tables.add_argument('paper_dir')
    tables.add_argument('--calls')
    args = parser.parse_args()
    if args.command == 'extract-calls':
        extract_calls(args.instances_root, args.calls_csv)
        return

    df = load(args.summary_csv)
    tab_dir = os.path.join(args.paper_dir, 'tables', 'revision')
    fig_dir = os.path.join(args.paper_dir, 'figures', 'revision')
    os.makedirs(tab_dir, exist_ok=True)
    os.makedirs(fig_dir, exist_ok=True)
    w = frame(df, 'original')
    table3(w, tab_dir)
    tables45(w, tab_dir)
    appendix(w, tab_dir)
    table7(w, tab_dir)
    delay_table(df, tab_dir)
    budget_table(df, tab_dir)
    hetero_table(df, tab_dir)
    figures(w, fig_dir)
    numbers(w, df)
    if args.calls:
        calls = pd.read_csv(args.calls)
        table6(calls, tab_dir)
        call_figures(calls, fig_dir)


if __name__ == '__main__':
    main()
