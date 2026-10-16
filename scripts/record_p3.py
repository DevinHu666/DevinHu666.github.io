#!/usr/bin/env python3
"""Record one loop of the RPO Rickroll from the Project 3 runtime.

    PROJECT3_DIR=/path/to/project3-python python3 scripts/record_p3.py [--out public/data/p3-rickroll.json]

Starts `$PROJECT3_DIR/src/main.py --demo` (the ROB 380 Project 3 folder, which
lives outside this repository; port 9095 must be free), loads
the RPO robot, deploys fsm/rpo_rickroll.json, and records /xform_world and
/fsm/status as an ordinary TCP client. It keeps the second pass of the loop,
so the recording starts and ends in the same steady motion and replays
seamlessly. Every pose in the output is one the runtime published: the page
only interpolates between consecutive frames.

Output: {"links": [...], "states": [...], "fps": 10, "duration": s,
         "frames": [[t, state, x, y, z, qx, qy, qz, qw, (x, y, z, ...) per link]]}
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FSM = "rpo_rickroll"


class Client:
    def __init__(self) -> None:
        self.sock = socket.create_connection(("127.0.0.1", 9095), timeout=10)
        self.stream = self.sock.makefile("rwb")
        self.ids = itertools.count()
        self.backlog: list[dict] = []

    def send(self, message: dict) -> None:
        self.stream.write((json.dumps(message) + "\n").encode())
        self.stream.flush()

    def call(self, service: str, args: dict, check: bool = True) -> dict:
        call_id = f"rec-{next(self.ids)}"
        self.send({"op": "call_service", "service": service, "id": call_id, "args": args})
        for line in self.stream:
            reply = json.loads(line)
            if reply.get("op") == "service_response" and reply.get("id") == call_id:
                if check and not reply["result"]:
                    raise SystemExit(f"{service} failed: {reply['status']}")
                return reply["values"]
            if reply.get("op") == "publish":
                self.backlog.append((time.monotonic(), reply))
        raise SystemExit("runtime closed the connection")

    def messages(self):
        while self.backlog:
            yield self.backlog.pop(0)
        for line in self.stream:
            message = json.loads(line)
            if message.get("op") == "publish":
                yield time.monotonic(), message


def quaternion(m: list[float]) -> tuple[float, float, float, float]:
    """Column-major 4x4 -> unit quaternion (x, y, z, w), four-branch (stable near 180°)."""
    r = lambda row, col: m[4 * col + row]  # noqa: E731
    trace = r(0, 0) + r(1, 1) + r(2, 2)
    if trace > 0:
        s = 2 * math.sqrt(trace + 1)
        q = ((r(2, 1) - r(1, 2)) / s, (r(0, 2) - r(2, 0)) / s, (r(1, 0) - r(0, 1)) / s, s / 4)
    elif r(0, 0) > r(1, 1) and r(0, 0) > r(2, 2):
        s = 2 * math.sqrt(1 + r(0, 0) - r(1, 1) - r(2, 2))
        q = (s / 4, (r(0, 1) + r(1, 0)) / s, (r(0, 2) + r(2, 0)) / s, (r(2, 1) - r(1, 2)) / s)
    elif r(1, 1) > r(2, 2):
        s = 2 * math.sqrt(1 + r(1, 1) - r(0, 0) - r(2, 2))
        q = ((r(0, 1) + r(1, 0)) / s, s / 4, (r(1, 2) + r(2, 1)) / s, (r(0, 2) - r(2, 0)) / s)
    else:
        s = 2 * math.sqrt(1 + r(2, 2) - r(0, 0) - r(1, 1))
        q = ((r(0, 2) + r(2, 0)) / s, (r(1, 2) + r(2, 1)) / s, s / 4, (r(1, 0) - r(0, 1)) / s)
    norm = math.sqrt(sum(v * v for v in q))
    return tuple(v / norm for v in q)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE.parent / "public" / "data" / "p3-rickroll.json")
    parser.add_argument("--project3", type=Path, default=os.environ.get("PROJECT3_DIR"),
                        help="the project3-python folder (default: $PROJECT3_DIR)")
    options = parser.parse_args()
    if options.project3 is None:
        raise SystemExit("set PROJECT3_DIR (or pass --project3) to your project3-python folder")
    runtime_dir = options.project3.expanduser().resolve()
    urdf = runtime_dir / "viewer" / "assets" / "rpo" / "urdf" / "rpo.urdf"

    try:
        socket.create_connection(("127.0.0.1", 9095), timeout=0.5).close()
        raise SystemExit("port 9095 is busy: stop the running runtime first, so the recording starts clean")
    except OSError:
        pass
    runtime = subprocess.Popen([sys.executable, str(runtime_dir / "src" / "main.py"), "--demo"],
                               stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                client = Client()
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise SystemExit("runtime did not start")

        version = client.call("/param_server/set_param",
                              {"name": "robot_description", "value": urdf.read_text(encoding="utf-8")})["version"]
        while True:
            status = client.call("/param_server/get_param",
                                 {"name": "/robot_state_publisher/description_status"}, check=False).get("value")
            if status and status["version"] >= version:
                break
            time.sleep(0.05)
        if not status["accepted"]:
            raise SystemExit(f"RPO rejected: {status['error']}")
        time.sleep(0.6)  # joint_state_publisher reads the robot on its own schedule

        document = client.call("/fsm/load_from_file", {"identifier": FSM})
        timed = [s for s in document["states"] if "duration" in s]
        loop = sum(s["duration"] for s in timed)
        first = timed[0]["name"]
        client.send({"op": "subscribe", "topic": "/xform_world", "type": "xform_world/MatrixTransformArray"})
        client.send({"op": "subscribe", "topic": "/fsm/status", "type": "fsm/Status"})
        client.call("/fsm/update_logic", document)
        print(f"recording {FSM}: one {loop:.2f} s loop after a warm-up pass...", file=sys.stderr)

        entries = []  # (entry time, state)
        xforms = []  # (arrival time, msg)
        passes = 0
        start = end = None
        last_state = None
        for arrived, message in client.messages():
            msg = message["msg"]
            if message["topic"] == "/fsm/status":
                state = msg["current_state"]
                if state != last_state:
                    entered = arrived - msg["time_in_state"]
                    entries.append((entered, state))
                    last_state = state
                    if state == first:
                        passes += 1
                        if passes == 2:  # the first pass started from rest
                            start, end = entered, entered + loop
            elif start is not None or passes >= 1:
                xforms.append((arrived, msg))
            if end is not None and arrived > end + 0.3:
                break
    finally:
        runtime.terminate()
        runtime.wait(5)

    links = [e["child_frame_id"] for e in xforms[0][1]["transforms"]]
    names = [s["name"] for s in timed]
    frames = []
    for arrived, msg in xforms:
        t = arrived - start
        if not -0.15 <= t < loop + 0.15:  # a frame either side, to interpolate across the seam
            continue
        state = max((e for e in entries if e[0] <= arrived), default=(0, first))[1]
        by_link = {e["child_frame_id"]: e["matrix"] for e in msg["transforms"]}
        row = [round(t, 3), names.index(state) if state in names else -1]
        for link in links:
            m = by_link[link]
            row += [round(v, 5) for v in (m[12], m[13], m[14])]
            row += [round(v, 5) for v in quaternion(m)]
        frames.append(row)

    out = {
        "robot": "RPO (Roboparty, CERN-OHL-W-2.0)",
        "choreography": FSM,
        "bpm": 113,
        "duration": round(loop, 4),
        "links": links,
        "states": [name.split("_", 1)[1] for name in names],
        "frames": frames,
    }
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    rate = len(frames) / (frames[-1][0] - frames[0][0])
    print(f"wrote {options.out}: {len(frames)} frames ({rate:.1f} Hz), {len(links)} links, "
          f"{options.out.stat().st_size / 1e3:.0f} kB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
