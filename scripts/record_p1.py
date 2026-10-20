#!/usr/bin/env python3
"""Record A* plans from the Project 1 runtime.

    PROJECT1_DIR=/path/to/project1 python3 scripts/record_p1.py [--out public/data/p1-astar.json]

Starts `$PROJECT1_DIR/src/main.py` (the ROB 380 Project 1 folder, which lives
outside this repository; port 9095 must be free) and, as an ordinary TCP
client, publishes a few maps on /map and calls /plan_path on each. The maps
are inputs: my graded map from the project, plus a maze, a cluttered field
and a walled-off goal generated here from fixed seeds. Every path in the
output is the runtime's own /plan_path answer, checked against the /path it
publishes; the page only draws it.

Output: {"maps": [{"name", "note", "width", "height", "cells": "0/1 per cell,
         row 0 first", "start": [x, y], "goal": [x, y], "result": bool,
         "path": [[x, y], ...], "ms": round-trip time}]}
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from pathlib import Path

from rosbridge_client import connect, project_dir, start_runtime

HERE = Path(__file__).resolve().parent
IDENTITY = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}


def occupancy(width: int, height: int, blocked: set[tuple[int, int]], resolution=1.0, origin=(0.0, 0.0)) -> dict:
    return {
        "header": {"frame_id": "map"},
        "info": {"resolution": resolution, "width": width, "height": height,
                 "origin": {"position": {"x": origin[0], "y": origin[1], "z": 0.0}, "orientation": IDENTITY}},
        "data": [100 if (x, y) in blocked else 0 for y in range(height) for x in range(width)],
    }


def maze(width: int, height: int, seed: int) -> set[tuple[int, int]]:
    """A perfect maze (randomized depth-first carving) on odd cells; everything else is wall."""
    rng = random.Random(seed)
    walls = {(x, y) for x in range(width) for y in range(height)}
    stack = [(1, 1)]
    walls.discard((1, 1))
    while stack:
        x, y = stack[-1]
        options = [(dx, dy) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))
                   if 0 < x + dx < width - 1 and 0 < y + dy < height - 1 and (x + dx, y + dy) in walls]
        if not options:
            stack.pop()
            continue
        dx, dy = rng.choice(options)
        walls.discard((x + dx // 2, y + dy // 2))
        walls.discard((x + dx, y + dy))
        stack.append((x + dx, y + dy))
    # A few extra openings make loops, so the shortest route is a real choice, not the only one.
    inner = sorted(c for c in walls if 0 < c[0] < width - 1 and 0 < c[1] < height - 1 and (c[0] + c[1]) % 2 == 1)
    for cell in rng.sample(inner, len(inner) // 12):
        walls.discard(cell)
    return walls


def field(width: int, height: int, seed: int, density: float, keep: list[tuple[int, int]]) -> set[tuple[int, int]]:
    rng = random.Random(seed)
    blocked = {(x, y) for x in range(width) for y in range(height) if rng.random() < density}
    return blocked - set(keep)


def pose(map_msg: dict, cell: tuple[int, int]) -> dict:
    info = map_msg["info"]
    res, origin = info["resolution"], info["origin"]["position"]
    return {"header": {"frame_id": "map"},
            "pose": {"position": {"x": origin["x"] + (cell[0] + 0.5) * res,
                                  "y": origin["y"] + (cell[1] + 0.5) * res, "z": 0.0},
                     "orientation": IDENTITY}}


def cell(map_msg: dict, position: dict) -> list[int]:
    info = map_msg["info"]
    res, origin = info["resolution"], info["origin"]["position"]
    return [math.floor((position["x"] - origin["x"]) / res), math.floor((position["y"] - origin["y"]) / res)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE.parent / "public" / "data" / "p1-astar.json")
    parser.add_argument("--project1", default=os.environ.get("PROJECT1_DIR"),
                        help="the project1 folder (default: $PROJECT1_DIR)")
    options = parser.parse_args()
    runtime_dir = project_dir(options.project1, "PROJECT1_DIR", "project1")

    mine = json.loads((runtime_dir / "maps" / "student_map.json").read_text(encoding="utf-8"))
    w, h = 41, 25
    gx, gy = w - 2, h - 2
    walled = maze(w, h, seed=7) | {(gx - 1, gy), (gx + 1, gy), (gx, gy - 1), (gx, gy + 1)}
    cases = [
        ("My map", "The map I submitted: a wall with one gap, and two unknown (−1) cells, which count as blocked.",
         mine, (0, 0), (0, 7)),
        ("Maze", "41 × 25 cells. A few extra openings give it loops, so A* has competing routes to rank.",
         occupancy(w, h, maze(w, h, seed=7)), (1, 1), (w - 2, h - 2)),
        ("Field", "60 × 36 cells, 30% randomly blocked, 0.25 m cells with the origin at (−3, −2) m.",
         occupancy(60, 36, field(60, 36, seed=11, density=0.3, keep=[(0, 0), (59, 35)]), 0.25, (-3.0, -2.0)),
         (0, 0), (59, 35)),
        ("Unreachable", "The same maze with the goal sealed off. The runtime answers result:false and publishes no /path.",
         occupancy(w, h, walled), (1, 1), (w - 2, h - 2)),
    ]

    runtime = start_runtime(runtime_dir)
    out = []
    try:
        client = connect()
        client.send({"op": "advertise", "topic": "/map", "type": "nav_msgs/OccupancyGrid"})
        client.send({"op": "subscribe", "topic": "/path", "type": "nav_msgs/Path"})
        for name, note, map_msg, start, goal in cases:
            client.send({"op": "publish", "topic": "/map", "msg": map_msg})
            time.sleep(0.2)  # publish has no acknowledgement; this connection's messages arrive in order
            begin = time.perf_counter()
            reply = client.call("/plan_path", {"start": pose(map_msg, start), "goal": pose(map_msg, goal),
                                               "tolerance": 0.0}, check=False)
            ms = (time.perf_counter() - begin) * 1000
            path = []
            if reply["result"]:
                path = [cell(map_msg, p["pose"]["position"]) for p in reply["values"]["plan"]["poses"]]
                published = next(m for m in client.messages() if m["topic"] == "/path")["msg"]
                if [cell(map_msg, p["pose"]["position"]) for p in published["poses"]] != path:
                    raise SystemExit(f"{name}: /path differs from the /plan_path response")
            info = map_msg["info"]
            out.append({
                "name": name,
                "note": note,
                "width": info["width"],
                "height": info["height"],
                "cells": "".join("0" if 0 <= v < 50 else "1" for v in map_msg["data"]),
                "start": list(start),
                "goal": list(goal),
                "result": reply["result"],
                "path": path,
                "ms": round(ms, 1),
            })
            moves = f"{len(path) - 1} moves" if path else reply.get("status", "no path")
            print(f"{name}: result={reply['result']}, {moves}, {ms:.1f} ms", file=sys.stderr)
    finally:
        runtime.terminate()
        runtime.wait(5)

    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(json.dumps({"maps": out}, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {options.out}: {options.out.stat().st_size / 1e3:.0f} kB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
