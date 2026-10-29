# Reproducing the tables of the revised paper

    bash reproduce_tables.sh        # cwd = repo root; Python 3 with pandas, numpy, matplotlib, seaborn

1. `summarize_runs.py` re-verifies every solution in `output/` against its instance (precedence, capacity, autonomy,
   travel times, time windows) with `verify_solutions.py` and recomputes its cost -> `results/summary.csv`.
2. `make_paper_tables.py extract-calls` collects the per-call statistics of MILP and WS-MILP -> `results/calls.csv`.
3. `make_paper_tables.py tables` writes the LaTeX tables (`results/tables/revision/`) and figures
   (`results/figures/revision/`), and prints the figures quoted in the text.

Data sets and output prefixes (`<graph>/<instance>/output/<prefix>_*.json`):

| Set | Folder | Prefixes |
|---|---|---|
| Main experiments (240 instances) | `<graph>/` | `SCFI-v2-soft`, `MCFI-v2-soft`, `MCFIR-v2-soft` (MCFI+R), `MILP-v2-soft`, `WS-v2-soft` (WS-MILP) |
| Time budget of 10 and 60 s per call | `<graph>/` | `MILP-v2-soft-T10`, `-T60`, `WS-v2-soft-T10`, `-T60` |
| Narrower pickup windows | `delay/tw_0.5`, `delay/tw_0.25` | as the main experiments; delay penalty 10 and 200: suffixes `-dp10`, `-dp200` |
| Heterogeneous fleets | `heterogeneous/` | `MCFI-v2-soft`, `MCFIR-v2-soft`, `MILP-v2-soft`, `WS-v2-soft` |

Graph folders: `asymmetric_grid` = SparseGrid, `symmetric_grid` = DenseGrid, `mountain` = Polar, `random` = Random.
Files with other prefixes (`BH_`, `UPVD_`, `URJC_`, `WSD_`, ...) are the outputs of the first version of the paper.
