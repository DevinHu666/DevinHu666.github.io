"""A minimal client for the course runtimes' newline-delimited TCP/JSON protocol.

Shared by the Project 1 and Project 2 recorders. It only speaks the public
protocol (spec/ROSBRIDGE_PROTOCOL.md in each course project), so it records a
runtime exactly the way the autograder sees it.
"""

from __future__ import annotations

import itertools
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

PORT = 9095


class Client:
    def __init__(self) -> None:
        self.sock = socket.create_connection(("127.0.0.1", PORT), timeout=15)
        self.stream = self.sock.makefile("rwb")
        self.ids = itertools.count()
        self.backlog: list[dict] = []

    def send(self, message: dict) -> None:
        self.stream.write((json.dumps(message) + "\n").encode())
        self.stream.flush()

    def call(self, service: str, args: dict, check: bool = True) -> dict:
        """Call a service; publishes that arrive meanwhile are kept for messages()."""
        call_id = f"rec-{next(self.ids)}"
        self.send({"op": "call_service", "service": service, "id": call_id, "args": args})
        for line in self.stream:
            reply = json.loads(line)
            if reply.get("op") == "service_response" and reply.get("id") == call_id:
                if check and not reply["result"]:
                    raise SystemExit(f"{service} failed: {reply.get('status')}")
                return reply
            if reply.get("op") == "publish":
                self.backlog.append(reply)
        raise SystemExit("runtime closed the connection")

    def messages(self):
        """Yield every publish, oldest first, including ones that arrived during calls."""
        while self.backlog:
            yield self.backlog.pop(0)
        for line in self.stream:
            message = json.loads(line)
            if message.get("op") == "publish":
                yield message


def start_runtime(project_dir: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
    """Start `<project_dir>/src/main.py` on a free port 9095 without writing bytecode there."""
    try:
        socket.create_connection(("127.0.0.1", PORT), timeout=0.5).close()
        raise SystemExit(f"port {PORT} is busy: stop the running runtime first, so the recording starts clean")
    except OSError:
        pass
    return subprocess.Popen(
        [sys.executable, str(project_dir / "src" / "main.py")],
        cwd=project_dir,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(env or {})},
        stderr=subprocess.DEVNULL,
    )


def connect() -> Client:
    for _ in range(100):
        try:
            return Client()
        except OSError:
            time.sleep(0.05)
    raise SystemExit("runtime did not start")


def project_dir(value: str | Path | None, variable: str, folder: str) -> Path:
    if value is None:
        raise SystemExit(f"set {variable} (or pass the option) to your {folder} folder")
    path = Path(value).expanduser().resolve()
    if not (path / "src" / "main.py").is_file():
        raise SystemExit(f"{path} has no src/main.py; is it your {folder} folder?")
    return path
