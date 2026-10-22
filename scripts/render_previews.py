#!/usr/bin/env python3
"""Render the short looping preview clips shown on the home page.

    python3 scripts/render_previews.py

Each clip is drawn from a recording already in public/, never from new
simulation: P1 replays the /plan_path answers in public/data/p1-astar.json,
P2 the /joint_states in public/data/p2-pendularm.json (its forward kinematics
only turns joint angles into link positions, as the page does), and P3 is cut
from public/videos/p3-rickroll.mp4. Needs Pillow and ffmpeg.

Output: public/previews/<project>.mp4 (800 x 500, silent H.264) and a .jpg
poster frame for each.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public" / "data"
OUT = ROOT / "public" / "previews"
W, H, FPS, SS = 800, 500, 30, 2  # SS: supersampling factor for smooth edges

STAGE = (16, 21, 29)
MUTED = (141, 151, 168)
TEXT = (201, 209, 221)
MAIZE = (255, 203, 5)
GREEN = (76, 194, 122)
RED = (209, 73, 91)
LINKS = [(255, 203, 5), (92, 200, 255), (255, 123, 114)]


def font(size: int) -> ImageFont.ImageFont:
    for name in ("/System/Library/Fonts/SFNSMono.ttf", "/System/Library/Fonts/Menlo.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


class Encoder:
    """Pipe RGB frames to ffmpeg; keep one frame as the poster."""

    def __init__(self, name: str, poster_at: int) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        self.name, self.poster_at, self.count = name, poster_at, 0
        self.proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
             "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "27",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT / f"{name}.mp4")],
            stdin=subprocess.PIPE)

    def add(self, big: Image.Image) -> None:
        frame = big.resize((W, H), Image.LANCZOS)
        if self.count == self.poster_at:
            frame.save(OUT / f"{self.name}.jpg", quality=82)
        self.proc.stdin.write(frame.tobytes())
        self.count += 1

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait()
        size = (OUT / f"{self.name}.mp4").stat().st_size
        print(f"{self.name}: {self.count / FPS:.1f} s, {size / 1e3:.0f} kB")


def label(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.text((18 * SS, 14 * SS), text, fill=TEXT, font=font(17 * SS))


def p1() -> None:
    maps = {m["name"]: m for m in json.loads((DATA / "p1-astar.json").read_text())["maps"]}
    enc = Encoder("p1-astar", poster_at=int(3.5 * FPS))
    for name in ("Maze", "Field"):
        m = maps[name]
        w, h = m["width"], m["height"]
        cell = min((W - 40) * SS / w, (H - 60) * SS / h)
        x0 = (W * SS - cell * w) / 2
        y0 = (H * SS - cell * h) / 2 + 12 * SS
        base = Image.new("RGB", (W * SS, H * SS), STAGE)
        draw = ImageDraw.Draw(base)
        for y in range(h):
            for x in range(w):
                if m["cells"][y * w + x] == "1":
                    top = y0 + (h - 1 - y) * cell  # row 0 is the bottom of the map
                    draw.rectangle([x0 + x * cell, top, x0 + (x + 1) * cell - 1, top + cell - 1], fill=(96, 105, 120))
        label(draw, f"{name}: {len(m['path']) - 1} moves, planned by my runtime")
        center = lambda c: (x0 + (c[0] + 0.5) * cell, y0 + (h - 1 - c[1] + 0.5) * cell)  # noqa: E731
        points = [center(c) for c in m["path"]]
        draw_frames, hold = int(2.4 * FPS), int(1.6 * FPS)
        for i in range(draw_frames + hold):
            frame = base.copy()
            d = ImageDraw.Draw(frame)
            k = min(1.0, i / draw_frames)
            k = k * k * (3 - 2 * k)  # ease in and out
            shown = points[: max(2, math.ceil(k * len(points)))]
            d.line(shown, fill=MAIZE, width=max(3, int(cell * 0.38)), joint="curve")
            r = max(4 * SS, cell * 0.42)
            for (cx, cy), color in ((points[0], GREEN), (points[-1], RED)):
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
            enc.add(frame)
    enc.close()


def p2() -> None:
    rec = json.loads((DATA / "p2-pendularm.json").read_text())
    n, lengths, frames = rec["links"], rec["lengths"], rec["frames"]
    speed = 2.5
    reach = sum(lengths)
    scale = (H - 24) * SS / (2 * reach + 0.1)
    cx, cy = W * SS / 2, H * SS / 2 + 6 * SS
    P = lambda x, y: (cx + x * scale, cy - y * scale)  # noqa: E731
    goals = [e for e in rec["events"] if e["kind"] == "goal"]
    results = [e for e in rec["events"] if e["kind"] == "result"]
    times = [f[0] for f in frames]

    def sample(t: float) -> list[float]:
        i = max(0, min(len(frames) - 2, next((j for j, s in enumerate(times) if s > t), len(times)) - 1))
        a, b = frames[i], frames[i + 1]
        k = 0 if b[0] == a[0] else min(1, max(0, (t - a[0]) / (b[0] - a[0])))
        return [u + (v - u) * k for u, v in zip(a, b)]

    def joints(q: list[float]) -> list[tuple[float, float]]:
        pts, heading, x, y = [P(0, 0)], 0.0, 0.0, 0.0
        for i in range(n):
            heading += q[i]
            x += lengths[i] * math.cos(heading)
            y += lengths[i] * math.sin(heading)
            pts.append(P(x, y))
        return pts

    enc = Encoder("p2-pendularm", poster_at=int(4.5 * FPS))
    total = int(rec["duration"] / speed * FPS)
    for i in range(total):
        t = i * speed / FPS
        img = Image.new("RGB", (W * SS, H * SS), STAGE)
        d = ImageDraw.Draw(img)
        d.ellipse([cx - reach * scale, cy - reach * scale, cx + reach * scale, cy + reach * scale],
                  outline=(40, 47, 58), width=SS)
        frame = sample(t)
        q, setpoint = frame[1:1 + n], frame[1 + n:1 + 2 * n]
        goal = next((g for g in reversed(goals) if g["t"] <= t), None)
        if goal:
            done = any(goal["t"] < r["t"] <= t for r in results)
            ghost = joints(setpoint)
            for a, b in zip(ghost, ghost[1:]):
                d.line([a, b], fill=(70, 78, 92), width=2 * SS)
            gx, gy = P(goal["x"], goal["y"])
            r = 10 * SS
            d.ellipse([gx - r, gy - r, gx + r, gy + r], outline=GREEN if done else MAIZE, width=2 * SS)
            d.line([(gx, gy), (gx + 22 * SS * math.cos(goal["phi"]), gy - 22 * SS * math.sin(goal["phi"]))],
                   fill=GREEN if done else MAIZE, width=2 * SS)
        trail = [joints(sample(s)[1:1 + n])[-1] for s in [t - 1.2 + j * 0.04 for j in range(31)] if s >= 0]
        if len(trail) > 1:
            d.line(trail, fill=(58, 110, 140), width=2 * SS)
        pts = joints(q)
        for j in range(n):
            d.line([pts[j], pts[j + 1]], fill=LINKS[j], width=int(scale * 0.11))
        for x, y in pts:
            r = max(3 * SS, scale * 0.035)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(231, 234, 240))
        label(d, "PID off: falling under gravity" if not goal else
              f"Goal {goals.index(goal) + 1}/{len(goals)} under PID   {speed}x speed")
        enc.add(img)
    enc.close()


def p3() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    src = ROOT / "public" / "videos" / "p3-rickroll.mp4"
    crop = f"crop=ih*16/10:ih,scale={W}:{H}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-vf", crop, "-c:v", "libx264",
                    "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(OUT / "p3-forward-kinematics.mp4")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "4", "-i", str(src), "-frames:v", "1", "-vf", crop,
                    "-q:v", "4", str(OUT / "p3-forward-kinematics.jpg")], check=True)
    size = (OUT / "p3-forward-kinematics.mp4").stat().st_size
    print(f"p3-forward-kinematics: cut from the P3 video, {size / 1e3:.0f} kB")


if __name__ == "__main__":
    p1()
    p2()
    p3()
