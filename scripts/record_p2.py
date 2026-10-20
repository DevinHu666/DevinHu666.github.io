#!/usr/bin/env python3
"""Record the Project 2 arm swinging free, then reaching IK goals under PID.

    PROJECT2_DIR=/path/to/project2-python python3 scripts/record_p2.py [--out public/data/p2-pendularm.json]

Starts `$PROJECT2_DIR/src/main.py` with three links (the ROB 380 Project 2
folder, which lives outside this repository; port 9095 must be free) and, as
an ordinary TCP client: resets the arm, lets it fall under gravity with PID
off, enables PID, then sends a sequence of /ik_action goals and waits for each
result. It records /joint_states, the commanded setpoint from
/ik_action/feedback, and every result. Every pose in the output is one the
runtime published: the page draws links from these joint angles (the arm's
forward kinematics) and interpolates between neighbouring frames.

Output: {"lengths": [...], "fps": 30, "duration": s,
         "events": [{"t", "kind": "free"|"goal"|"result", ...}],
         "frames": [[t, q1, q2, q3, s1, s2, s3, e1, e2, e3]]}  (q angle, s setpoint, e effort)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from rosbridge_client import connect, project_dir, start_runtime

HERE = Path(__file__).resolve().parent
FREE_SWING = 3.0  # seconds of simulation time with PID off
GOALS = [  # (x, y, phi): all reachable for unit links
    (1.5, 1.0, 0.3),
    (-1.2, 1.4, 2.2),
    (0.5, 2.0, 1.2),
    (2.2, -0.8, -0.5),
    (1.0, 0.0, -1.57),
]
FPS = 30


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE.parent / "public" / "data" / "p2-pendularm.json")
    parser.add_argument("--project2", default=os.environ.get("PROJECT2_DIR"),
                        help="the project2-python folder (default: $PROJECT2_DIR)")
    options = parser.parse_args()
    runtime_dir = project_dir(options.project2, "PROJECT2_DIR", "project2-python")

    runtime = start_runtime(runtime_dir, {"ARM_SIM_LINKS": "3"})
    states = []  # (sim t, position, effort)
    setpoints = []  # (sim t, commanded positions)
    events = []
    try:
        client = connect()
        params = client.call("/arm_sim/set_params", {})["values"]
        client.call("/pid_controller/enable", {"data": False})
        client.call("/arm_sim/reset", {})
        for topic, kind in (("/joint_states", "sensor_msgs/JointState"),
                            ("/ik_action/feedback", "ik_action/Feedback"),
                            ("/ik_action/result", "ik_action/Result")):
            client.send({"op": "subscribe", "topic": topic, "type": kind})

        now = 0.0
        pending = [("free", None)] + [("goal", g) for g in GOALS]
        waiting_until = None  # sim time for the free swing to end
        waiting_for = None  # goal id
        idle_until = None  # short hold after each result
        print(f"recording {len(GOALS)} goals after {FREE_SWING:.0f} s of free swing...", file=sys.stderr)
        for message in client.messages():
            topic, msg = message["topic"], message["msg"]
            if topic == "/joint_states":
                stamp = msg["header"]["stamp"]
                now = stamp["sec"] + stamp["nanosec"] * 1e-9
                states.append((now, msg["position"], msg["effort"]))
            elif topic == "/ik_action/feedback":
                setpoints.append((now, msg["positions"]))
            elif topic == "/ik_action/result" and msg["goal_id"] == waiting_for:
                events.append({"t": now, "kind": "result", "outcome": msg["outcome"],
                               "distance": round(msg["final_distance"], 4)})
                print(f"  {msg['outcome']} at {now:.2f} s, {msg['final_distance'] * 1000:.1f} mm off",
                      file=sys.stderr)
                waiting_for, idle_until = None, now + 0.8

            busy = waiting_for is not None or (waiting_until and now < waiting_until) or (idle_until and now < idle_until)
            if busy or not states:
                continue
            if not pending:
                break
            kind, goal = pending.pop(0)
            if kind == "free":
                events.append({"t": now, "kind": "free"})
                waiting_until = now + FREE_SWING
            else:
                if not events or events[-1]["kind"] == "free":
                    client.call("/pid_controller/enable", {"data": True})
                x, y, phi = goal
                reply = client.call("/ik_action/send_goal", {"x": x, "y": y, "phi": phi})
                waiting_for = reply["values"]["goal_id"]
                events.append({"t": now, "kind": "goal", "x": x, "y": y, "phi": phi})
    finally:
        runtime.terminate()
        runtime.wait(5)

    t0 = states[0][0]
    frames = []
    next_t = t0
    for t, position, effort in states:
        if t + 1e-9 < next_t:
            continue
        next_t = t + 1 / FPS
        commanded = [s for s in setpoints if s[0] <= t]
        setpoint = commanded[-1][1] if commanded else [0.0] * len(position)
        frames.append([round(t - t0, 4)] + [round(v, 4) for v in [*position, *setpoint, *effort]])
    for event in events:
        event["t"] = round(event["t"] - t0, 3)

    out = {
        "links": len(params["lengths"]),
        "lengths": params["lengths"],
        "gravity": params["gravity"],
        "fps": FPS,
        "duration": frames[-1][0],
        "events": events,
        "frames": frames,
    }
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {options.out}: {len(frames)} frames over {out['duration']:.1f} s, "
          f"{options.out.stat().st_size / 1e3:.0f} kB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
