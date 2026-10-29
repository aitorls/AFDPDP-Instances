# AFDPDP-Instances

Instances and solutions for the Agricultural Fleet Dynamic Pickup and Delivery Problem (AFDPDP), together with the
scripts that rebuild every table and figure of the paper from the solution files.

## Contents

```
<graph>/<instance>/                 main experiments: 4 graphs x 60 instances = 240 instances
    robots.csv  requests.csv  vid_distances.csv
    output/<prefix>_*.json          one solution file per algorithm
delay/tw_0.5/<graph>/<instance>/    narrower pickup windows (0.5 D), 40 instances
delay/tw_0.25/<graph>/<instance>/   narrower pickup windows (0.25 D), 40 instances
heterogeneous/<graph>/<instance>/   heterogeneous fleets, 40 instances
scripts/                            solution checker and table/figure scripts
reproduce_tables.sh                 rebuilds results/ from the solution files
results/                            summary.csv, calls.csv, tables and figures, as produced by reproduce_tables.sh
```

Graph folders and their names in the paper:

| Folder | Paper |
|---|---|
| `random` | Random |
| `mountain` | Polar |
| `asymmetric_grid` | SparseGrid |
| `symmetric_grid` | DenseGrid |

### Instances

Instance names follow `<R>HR_6Q_50RQT_2q[_bigTW]_<seed>`: `R` regular robots (3, 6 or 9) of capacity 6, 50 requests
of 2 boxes each, narrow time windows (or wide ones with `_bigTW`), and seeds 0 to 9. Every instance also has one backup
robot (`extra_robot_*`, use cost x1000).

- **Main experiments:** the 60 instances of each graph folder (3 fleet sizes x 2 window widths x 10 seeds).
- **Narrower pickup windows** (`delay/`): the narrow-window instances of the two grids with 3 and 6 robots, with
  `pickup_max_time = pickup_min_time + alpha * D`, where `D` is the largest distance of the graph and `alpha` is 0.5
  or 0.25. Everything else is unchanged.
- **Heterogeneous fleets** (`heterogeneous/`): the wide-window instances of the two grids with 6 and 9 robots. The
  regular robots cycle through three types; the backup robot and the requests are unchanged.

  | Type | Capacity | Cost per distance | Use cost | Autonomy |
  |---|---|---|---|---|
  | small | 4 | 0.8 | 5 | 1.2 W |
  | medium | 6 | 1.0 | 10 | W |
  | large | 8 | 1.2 | 20 | W |

  `W` is the autonomy of the original instance.

### Solutions

`output/<prefix>_*.json` holds the final routes of one algorithm on one instance (`complete_routes`: every stop with
arrival and departure times, load and distance), the cost, the computational time and, for MILP and WS-MILP, solver
statistics per call.

| Prefix | Algorithm |
|---|---|
| `SCFI-v2-soft` | SCFI |
| `MCFI-v2-soft` | MCFI |
| `MCFIR-v2-soft` | MCFI+R (MCFI with reassignment) |
| `MILP-v2-soft` | MILP re-solved at every event |
| `WS-v2-soft` | WS-MILP (MILP warm-started with the MCFI plan) |
| suffix `-T10`, `-T60` | MILP and WS-MILP with a time limit of 10 or 60 s per call (default 300 s) |
| suffix `-dp10`, `-dp200` | delay penalty of 10 or 200 per time unit (default 50), on `delay/tw_0.5` |

All of these use soft time windows: a late visit is allowed and its delay is penalised in the cost. Files with other
prefixes (`BH_`, `UPVD_`, `URJC_`, `WSD_`, `WST_`, ...) and the notebooks and `results.csv` at the repo root belong to
the first version of the paper.

## Reproducing the tables

```bash
bash reproduce_tables.sh
```

Requires Python 3 with pandas, numpy, matplotlib and seaborn. The script:

1. checks every solution against its instance (precedence, capacity, autonomy, travel times, time windows) and
   recomputes its cost: `results/summary.csv`;
2. collects the per-call statistics of MILP and WS-MILP: `results/calls.csv`;
3. writes the LaTeX tables to `results/tables/revision/` and the figures to `results/figures/revision/`, and prints the
   figures quoted in the text.

See `scripts/README.md` for details.

## Reading an instance

Reading an instance only needs pandas:

```python
import glob
import json
import os

import pandas as pd

instance_path = os.path.join('symmetric_grid', '3HR_6Q_50RQT_2q_0')
robots = pd.read_csv(os.path.join(instance_path, 'robots.csv'))
requests = pd.read_csv(os.path.join(instance_path, 'requests.csv'))
distances = pd.read_csv(os.path.join(instance_path, 'vid_distances.csv'), index_col=0)
```

```python
>>> robots.columns.tolist()
['name', 'start_depot', 'end_depot', 'capacity', 'autonomy', 'use_cost', 'cost_per_distance']

>>> requests.columns.tolist()
['name', 'event_time', 'pickup_location', 'delivery_location', 'boxes', 'pickup_min_time', 'pickup_max_time',
 'delivery_min_time', 'delivery_max_time', 'pickup_service_time', 'delivery_service_time']
```

`event_time` is the time at which a request becomes known. `vid_distances.csv` is the distance matrix between the nodes
of the graph. All robots travel at speed 1, so distances are also travel times.

Reading a solution:

```python
path = glob.glob(os.path.join(instance_path, 'output', 'SCFI-v2-soft_*.json'))[0]
with open(path) as f:
    solution = json.load(f)

>>> solution['complete_routes']['robot_1'][0]
{'node': 'start_robot_1', 'node_id': 'depot_8', 'arrival_time': 0.0, 'departure_time': 0.0, 'current_cost': 0.0,
 'current_load': 0, 'distance_travelled': 0.0, 'ongoing_request': []}
```
