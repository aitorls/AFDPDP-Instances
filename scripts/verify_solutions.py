"""
[L4] Independent verifier of executed routes. It only uses the instance CSVs and the 'complete_routes' of an output
JSON (same format for BH_, UPVD_, WSD_, URJC_, URJCWOTW_ and the v2 prefixes); no MCFI or MILP code.

Checks per solution:
  - every request is picked up and delivered exactly once, by the same robot, pickup before delivery
  - routes start at the robot's start depot and end at its end depot
  - load (recomputed from 'boxes') within [0, capacity]
  - travelled distance <= autonomy
  - travel times: arrival >= previous departure + distance / speed (speed 1)
  - service: service start = max(arrival, l) and service start + st <= departure; pickups not before event_time
  - delay of each visit = max(0, service start + st - u)   (u = pickup/delivery max time)
Recomputed cost = distance * cost_per_distance + use_cost of robots that serve a request + penalty * total delay.

Usage (cwd = repo root):
  python tools/verify_solutions.py OUTPUT_CSV PREFIX [PREFIX ...] [--root input/AFDPDP-Instances] [--penalty 50]
    Verifies the most recent <PREFIX>*.json of every <root>/<graph>/<instance>/output folder.
"""
import argparse
import glob
import json
import os

import pandas as pd

TOL = 1e-6


def load_instance(instance_dir):
    robots = pd.read_csv(os.path.join(instance_dir, 'robots.csv')).set_index('name')
    requests = pd.read_csv(os.path.join(instance_dir, 'requests.csv')).set_index('name')
    distances = pd.read_csv(os.path.join(instance_dir, 'vid_distances.csv'), index_col=0)
    return robots, requests, distances


def visit_request(node_name):
    """'pickup_request_7' -> ('pickup', 'request_7'); depots -> (None, None)"""
    for kind in ('pickup', 'delivery'):
        if node_name.startswith(kind + '_'):
            return kind, node_name[len(kind) + 1:]
    return None, None


def merge_waits(route):
    """URJC routes encode waiting as consecutive copies of the same stop: merge them into one visit"""
    merged = []
    for stop in route:
        if merged and merged[-1]['node'] == stop['node']:
            merged[-1] = dict(merged[-1], departure_time=stop['departure_time'])
        else:
            merged.append(dict(stop))
    return merged


def verify(solution, robots, requests, distances, penalty=50):
    violations = {k: 0 for k in ('missing', 'duplicate', 'robot_mismatch', 'precedence', 'start_depot', 'end_depot',
                                 'capacity', 'negative_load', 'autonomy', 'travel_time', 'service', 'early')}
    details = []
    served = {}  # request -> {'pickup': (robot, position), 'delivery': (robot, position)}
    total_distance = 0.0
    travel_cost = 0.0
    use_cost = 0.0
    backup_use_cost = 0.0
    backup_tasks = 0
    total_delay = 0.0
    max_delay = 0.0
    late_visits = 0

    def add(kind, message):
        violations[kind] += 1
        if len(details) < 20:
            details.append(f"{kind}: {message}")

    for robot, route in solution['complete_routes'].items():
        if robot not in robots.index:
            add('robot_mismatch', f"unknown robot {robot}")
            continue
        params = robots.loc[robot]
        if not route:
            continue
        route = merge_waits(route)
        if route[0]['node_id'] != params['start_depot']:
            add('start_depot', f"{robot} starts at {route[0]['node_id']}")
        if route[-1]['node_id'] != params['end_depot']:
            add('end_depot', f"{robot} ends at {route[-1]['node_id']}")

        load, distance, serves_request = 0, 0.0, False
        for k, stop in enumerate(route):
            if k > 0:
                leg = float(distances.loc[route[k - 1]['node_id'], stop['node_id']])
                distance += leg
                if stop['arrival_time'] + TOL < route[k - 1]['departure_time'] + leg:
                    add('travel_time', f"{robot} {stop['node']} arrives at {stop['arrival_time']}")

            kind, request = visit_request(stop['node'])
            if kind is None:
                continue
            serves_request = True
            r = requests.loc[request]
            if kind in served.get(request, {}):
                add('duplicate', f"{kind} of {request}")
            served.setdefault(request, {})[kind] = (robot, k)

            boxes = int(r['boxes'])
            load += boxes if kind == 'pickup' else -boxes
            if load > params['capacity'] + TOL:
                add('capacity', f"{robot} carries {load} after {stop['node']}")
            if load < -TOL:
                add('negative_load', f"{robot} carries {load} after {stop['node']}")

            lower, upper = float(r[f'{kind}_min_time']), float(r[f'{kind}_max_time'])
            service = float(r[f'{kind}_service_time'])
            service_start = max(stop['arrival_time'], lower)
            if kind == 'pickup' and service_start + TOL < float(r['event_time']):
                add('early', f"{stop['node']} served before its event time")
            if k < len(route) - 1 and service_start + service > stop['departure_time'] + TOL:
                add('service', f"{robot} leaves {stop['node']} before the end of service")
            delay = max(0.0, service_start + service - upper)
            if delay > TOL:
                late_visits += 1
                total_delay += delay
                max_delay = max(max_delay, delay)
            if kind == 'pickup' and 'extra' in robot:
                backup_tasks += 1

        if distance > params['autonomy'] + TOL:
            add('autonomy', f"{robot} travels {distance} > {params['autonomy']}")
        total_distance += distance
        travel_cost += distance * float(params['cost_per_distance'])
        if serves_request:
            use_cost += float(params['use_cost'])
            if 'extra' in robot:
                backup_use_cost += float(params['use_cost'])

    for request in requests.index:
        visits = served.get(request, {})
        if 'pickup' not in visits or 'delivery' not in visits:
            add('missing', f"{request} {sorted(visits)}")
            continue
        (robot_p, pos_p), (robot_d, pos_d) = visits['pickup'], visits['delivery']
        if robot_p != robot_d:
            add('robot_mismatch', f"{request} picked by {robot_p}, delivered by {robot_d}")
        elif pos_p >= pos_d:
            add('precedence', f"{request} delivered before pickup")

    return dict(valid=sum(violations.values()) == 0, **violations, distance=total_distance, travel_cost=travel_cost,
                use_cost=use_cost, backup_use_cost=backup_use_cost, delay=total_delay, max_delay=max_delay,
                late_visits=late_visits, delay_cost=penalty * total_delay,
                cost=travel_cost + use_cost + penalty * total_delay, backup_used=backup_tasks > 0,
                backup_tasks=backup_tasks, details=' | '.join(details))


def latest_output(instance_dir, prefix):
    files = sorted(glob.glob(os.path.join(instance_dir, 'output', prefix + '*.json')), key=os.path.getmtime)
    files = [f for f in files if '_iterations_' not in os.path.basename(f)]
    return files[-1] if files else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output_csv')
    parser.add_argument('prefixes', nargs='+')
    parser.add_argument('--root', default=os.path.join('input', 'AFDPDP-Instances'))
    parser.add_argument('--penalty', type=float, default=50)
    parser.add_argument('--pattern', default='*HR_6Q_50RQT_2q_*', help="instance folder glob (default: paper set)")
    args = parser.parse_args()

    rows = []
    for graph in sorted(os.listdir(args.root)):
        graph_dir = os.path.join(args.root, graph)
        if not os.path.isdir(graph_dir):
            continue
        for instance in sorted(os.path.basename(p) for p in glob.glob(os.path.join(graph_dir, args.pattern))):
            instance_dir = os.path.join(graph_dir, instance)
            if not os.path.isfile(os.path.join(instance_dir, 'requests.csv')):
                continue
            robots, requests, distances = None, None, None
            for prefix in args.prefixes:
                path = latest_output(instance_dir, prefix)
                if path is None:
                    continue
                if robots is None:
                    robots, requests, distances = load_instance(instance_dir)
                with open(path) as f:
                    solution = json.load(f)
                row = dict(graph=graph, instance=instance, prefix=prefix, file=os.path.basename(path),
                           json_cost=solution.get('cost'), feasible_flag=solution.get('feasible'))
                if 'complete_routes' not in solution:
                    row['valid'] = None
                else:
                    row.update(verify(solution, robots, requests, distances, args.penalty))
                rows.append(row)
    pd.DataFrame(rows).to_csv(args.output_csv, index=False)
    print(f"Verified {len(rows)} solutions -> {args.output_csv}")


if __name__ == '__main__':
    main()
