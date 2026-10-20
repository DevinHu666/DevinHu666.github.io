---
title: "Pathfinding: A* over my own pub/sub runtime"
summary: "A ROS-like publish/subscribe and service runtime written from scratch, with an A* planner for occupancy grids on top. I built it in Python, then again in dependency-free Rust, and a one-line tie-break fix cut the work on large maps by about 500×."
status: published
order: 10
course: "ROB 380 · Project 1"
courseProject: 1
tags: ["A*", "pub/sub", "TCP/JSON", "concurrency", "Python", "Rust"]
date: "2026-09"
demo: "p1-astar"
highlights:
  - "1000 × 1000 open grid: 1,000,000 → 1,999 frontier pops after the tie-break fix"
  - "Autograder A* optimality test: 0/8 → full marks"
  - "78 tests in Python and 81 in Rust, many over real TCP"
  - "Rust version: standard library only, hand-written JSON parser"
---

## The problem

Robot software is usually a set of small programs passing messages: one publishes a map, another plans on it, a third drives along the plan. ROS provides that plumbing. This project builds it from nothing. One process listens on a TCP port and speaks a newline-delimited JSON protocol, the same shape as rosbridge, to any number of clients at once. Clients can advertise and publish topics, subscribe to them, and offer or call services.

On top of that runtime sits the robotics part: a planner node that subscribes to `/map`, an occupancy grid, and answers `/plan_path` with the shortest 4-connected route between two world positions, then publishes it on `/path`. No ROS libraries, no graph libraries.

## Design

- **One bus for everyone.** External TCP connections and in-process nodes go through the same bus, so the planner sees exactly what an outside client would. It has no back door into the transport.
- **A slow client only hurts itself.** Each connection gets its own reader thread and a writer thread fed by a bounded queue. A subscriber that stops reading can't stall a publisher or anyone else. A test sends 300 messages of 200 KB each at a subscriber that never reads and checks that a third client still gets prompt answers.
- **Services across clients.** A client can offer a service. The bus rewrites call IDs on the way to the provider and back, so concurrent callers never see each other's answers, and a provider that disconnects fails its pending calls instead of leaving them hanging.
- **The graded part stays frozen.** The heap services from the checkpoint are unchanged since that submission, and a regression check confirms it after every change.

## A*, and the bug that cost 8 points

The planner is A* with the Manhattan distance, which is consistent on a 4-connected grid with unit costs. The assignment requires the frontier to be ordered through my own `/heap_sort` service. Sorting every frontier entry on every expansion would be slow in Python, so the frontier groups cells into buckets by their `f` value and only sorts the handful of distinct `f` values.

After submission, the autograder gave the optimality test 0 of 8 points. My paths were optimal: they agreed with a BFS oracle on more than 370 hand-made and random maps, sent through the real TCP pipeline. The bug turned out to be speed, not correctness. My buckets broke ties first-in, first-out. On an open map almost every cell has the same `f`, so FIFO sweeps that whole bucket, like breadth-first search, before reaching the goal. Taking the newest cell first (LIFO) keeps extending the most recent path toward the goal instead:

| Open grid, corner to corner | Frontier pops, FIFO | LIFO | Time, FIFO | LIFO |
| --- | ---: | ---: | ---: | ---: |
| 100 × 100 | 10,000 | 199 | ~14 ms | <1 ms |
| 500 × 500 | 250,000 | 999 | ~470 ms | ~2 ms |
| 1000 × 1000 | 1,000,000 | 1,999 | ~1.9 s | ~3 ms |

Path lengths are identical before and after. A consistent heuristic makes A* optimal however ties are broken, so tie-breaking changes only the work done and which optimal route comes back. After resubmitting, the test scored full marks. A regression test now bounds the number of frontier pops on a 300 × 300 grid. It counts pops rather than timing the run, so it doesn't depend on how fast the machine is.

The autograder also caught a protocol gap: any client could publish to any topic. Publishing now requires a prior `advertise`, and stops after `unadvertise`.

## Twice: Python, then Rust

I then wrote the whole system again in Rust, with no third-party crates because the grader builds offline. That meant a hand-written JSON parser and serializer, a bus behind one mutex that is never held while a message is delivered, and the same per-connection reader and writer threads. The Python version served as the behavioural reference. The Rust suite has 81 tests, unit tests per module plus black-box tests over TCP. Even a debug build answers the 1000 × 1000 open-grid case in 0.15 s, counting the time to send the 4 MB map and the round trip of the plan.

## How I checked it

78 tests in the Python version cover every map validation rule, the spec's worked geometry example, nonzero origins and non-unit resolutions, unreachable and blocked endpoints, `start == goal`, and optimality against BFS on random grids. About 30 of them talk to a live server over TCP, the way the autograder does. Others check that the server shuts down within 2 s of `SIGTERM` and `SIGINT` and leaves no process on the port.

## How this page draws it

The maps above are inputs. The first is the map I submitted; the others are generated from fixed seeds by a recording script. The script starts my runtime, publishes each map on `/map` as an ordinary client, calls `/plan_path`, and checks that `/path` carries the same route. The page draws the cells it got back and plans nothing itself.

## What I'd do next

- **8-connected moves and weighted costs**, with octile distance as the heuristic, for maps closer to a real robot's.
- **Show the search, not just the result.** Publishing each expansion on a debug topic would let this page animate the frontier and make the FIFO-versus-LIFO difference visible.

## Credits and AI use

- Specification, protocol, starter kit and autograder: AutoRob (ROB 380), University of Michigan.

**AI use.** I built this project with Claude Code (Anthropic's coding agent, using Claude Opus and Sonnet models). Claude Code wrote code and tests under my direction, in a plan → implement → audit → test loop whose plan, decisions and test results are kept in the repository, and every commit is co-authored by Claude. The Rust version was made the same way. The FIFO tie-break bug behind the failed optimality test is one I found myself, after an audit with the agent had found nothing. This write-up and statement were drafted with Claude Code from my project notes, and reviewed by me.
