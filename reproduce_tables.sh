#!/usr/bin/env bash
# Rebuild the tables and figures of the revised paper from the output JSON files (cwd = repo root).
# Needs Python 3 with pandas, numpy, matplotlib and seaborn. Writes results/summary.csv, results/calls.csv,
# results/tables/revision/*.tex and results/figures/revision/*.png.
set -euo pipefail
PY="${PY:-python3}"
PREFIXES=""
for m in SCFI MCFI MCFIR MILP WS; do
    for s in "" -T10 -T60 -dp10 -dp200; do PREFIXES="$PREFIXES $m-v2-soft$s"; done
done
mkdir -p results
# 1. Verify every solution against its instance and recompute its cost
ROOTS="original=."
for r in tw_0.5=delay/tw_0.5 tw_0.25=delay/tw_0.25 hetero=heterogeneous; do [ -d "${r#*=}" ] && ROOTS="$ROOTS $r"; done
"$PY" scripts/summarize_runs.py results/summary.csv $ROOTS --prefixes $PREFIXES
# 2. Per-call data of MILP and WS-MILP (Table 6, Figs. 5 and 6)
"$PY" scripts/make_paper_tables.py extract-calls . results/calls.csv
# 3. Tables and figures
"$PY" scripts/make_paper_tables.py tables results/summary.csv results --calls results/calls.csv
