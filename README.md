# AFDPDP-Instances

Instances to test the Agriculture Fleet Dynamic Pickup and Delivery Problem (AFDPDP)


## Dependecies
Works with Python 3.8+ and only depends on pandas.

## Example usage

To read the instances you must import pandas libary for python and following the next procedure:

```python
import pandas as pd

instance_path = os.path.join(experiments_directory, experiment_name, instance_name)

# Read Static benchmark instance and solution
robots   = pd.read_csv(os.path.join(instance_path,  'robots.csv'))
requests  = pd.read_csv(os.path.join(instance_path,  'requests.csv'))
distances = pd.read_csv(os.path.join(instance_path, 'vid_distances.csv'))
```

The `instance` is compose of the set of robots, tasks and distances.

```python
>>> robots.columns.tolist()
['name', 'start_depot', 'end_depot', 'capacity', 'autonomy', 'use_cost', 'cost_per_distance']

>>> requests.columns.tolist()
['name', 'event_time', 'pickup_location', 'delivery_location', 'boxes', 'pickup_min_time', 'pickup_max_time', 'delivery_min_time', 'delivery_max_time', 'pickup_service_time', 'delivery_service_time']
```

The `solution` of each `instance` is a json with the whole information about robots routes.

```python
import json

# Open and read the JSON file
with open(file_solution, 'r') as file:
    solution_json = json.load(file)

>>> solution_kpis.keys()
dict_keys(['instance_name', 'solution_name', 'cost', 'max_time', 'distance_travelled', 'costs_routes', 'distances_routes', 'complete_routes', 'computational_time', 'algorithm', 'execution_time', 'iterations_time', 'pending_tasks', 'ongoing_tasks', 'iteration_cost', 'iteration_cost_2', 'iteration_gaps', 'max_memory_used'])


>>> solution_json
{'instance_name': '3HR_6Q_50RQT_3q_1',
 'solution_name': '3HR_6Q_50RQT_3q_1_solution_20250506_091242',
 'cost': 13890.0,
 'max_time': 8643,
 'distance_travelled': 13860.0,
 'costs_routes': {'robot_1': 3000.0,
  'robot_2': 6080.0,
  'robot_3': 4780.0,
  'extra_robot_1': 0.0},
 'distances_routes': {'robot_1': 3000.0,
  'robot_2': 6080.0,
  'robot_3': 4780.0,
  'extra_robot_1': 0.0},
 'complete_routes': {'robot_1': [{'node': 'start_robot_1',
    'node_id': 'depot_1',
    'arrival_time': 0.0,
    'departure_time': 0.0,
    'current_cost': 0.0,
    'current_load': 0,
    'distance_travelled': 0.0,
    'ongoing_request': []},
   {'node': 'start_robot_1',
    'node_id': 'depot_1',
    'arrival_time': 0.0,
    'departure_time': 41.0,
...
  0.0,
  0.0,
  0.0,
  0.0],
 'max_memory_used': '2.62GB'}

```