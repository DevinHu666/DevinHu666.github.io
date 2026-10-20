---
title: "Pendularm: simulating and controlling an arm"
summary: "A planar two- or three-link arm simulated from its Lagrangian dynamics, with four numerical integrators, per-joint PID control and closed-form inverse kinematics, all running live behind the same TCP runtime. Standard library only: no physics engine, no ODE solver, no NumPy."
status: published
order: 20
course: "ROB 380 · Project 2"
courseProject: 2
tags: ["dynamics", "integrators", "PID", "inverse kinematics", "concurrency", "Python"]
date: "2026-09"
demo: "p2-pendularm"
highlights:
  - "RK4 energy drift over 2 s: 5.1e-9 J, against 2.1e-1 J for Euler"
  - "Settles in 2.4 s (2 links) and 3.3 s (3 links) at the shipped gains"
  - "IK round-trip error at most 2.9e-14 over 40,000 targets"
  - "319 tests; 82 of 83 deliberate bugs caught by mutation testing"
---

## The problem

A robot arm, simulated well enough to control. Each link is a uniform rod hinged to the one before, gravity pulls along −y, and the joints move by the manipulator equation `M(q) q̈ + C(q, q̇) q̇ + G(q) = τ`. The runtime has to derive and integrate that motion live, publish the joint states at 60 Hz, hold the arm at a setpoint with PID, and move the hand to a requested point with inverse kinematics. Everything is exposed as topics and services on the publish/subscribe runtime from [Project 1](../p1-astar/), and the autograder drives it over TCP. Only the standard library is allowed.

## Dynamics

I derived `M`, `C` and `G` for a general `n`-link arm and solve for `q̈` with my own Gauss–Jordan elimination with partial pivoting. A sign error in a Christoffel symbol still gives a plausible-looking swing, so five independent checks guard the derivation. The sharpest is that `Ṁ − 2C` must be skew-symmetric. With zero torque, total energy must also stay constant. A 3-link forward-dynamics call takes about 38 µs, so RK4 at a 1 ms step runs in real time on about 15% of one core.

## Four integrators

Euler, midpoint, Verlet and RK4 share one implementation between the integrator checkpoint service and the live arm. Halving the step should shrink the error by `2^order`, and it does:

| Method | Error, dt = 0.02 | dt = 0.01 | Ratio | Order |
| --- | ---: | ---: | ---: | ---: |
| Euler | 2.8e-2 | 1.4e-2 | 2.00 | 1 |
| Midpoint | 4.3e-5 | 1.1e-5 | 4.03 | 2 |
| Verlet | 9.7e-5 | 2.4e-5 | 4.00 | 2 |
| RK4 | 2.6e-10 | 1.6e-11 | 16.00 | 4 |

On the free-swinging arm the difference is energy: over 2 s at a 1 ms step, Euler’s total energy drifts by up to 0.21 J on two links, and RK4’s by 5e-9 J. Too large a step diverges, as it should. The arm is then left diverged until a reset, while every service keeps answering.

## PID: tuning against the plant

Each joint has its own PID loop with a clamped integral. My planned gains (50/10/15) settled the 2-link arm in 9.8 s and never settled the 3-link arm within 10 s. The shipped gains (200/100/30) settle within 0.05 rad in 2.4 s and 3.3 s under all four integrators. Two numbers shaped that choice:
- **Stability.** With `kd = 30`, the fastest damping mode on three links is about 780 per second, a 2.6× margin under Euler's limit of 2000 per second at a 1 ms step. Doubling `kd` would leave only 1.3×.
- **Why the integral term.** Gravity is a constant load, so with `ki = 0` the arm comes to rest 0.095 rad (2 links) or 0.21 rad (3 links) short of its setpoint. The integral removes that offset to about 1e-3 rad within 8 s.

## Inverse kinematics and goals

`/ik/solve` is closed-form: the law of cosines for two links and, for three, kinematic decoupling, which subtracts the last link to find the wrist point. Feeding 40,000 solutions back through forward kinematics reproduces the targets to within 2.9e-14. A goal action on top commands the solution as a PID setpoint and reports "reached" only after the hand has stayed within 2 cm for 0.25 s of simulation time. A new reachable goal preempts the current one.

## Threads without deadlocks

The physics loop, the 60 Hz publisher and four nodes all share one process, and the bus delivers messages on the publisher's own thread. A subscriber can therefore call straight back into the node that published. The rule that keeps this safe: a node takes its lock, copies what it needs, and releases the lock before it publishes or calls. The one deliberate exception is the goal action. It needs a reentrant lock held across its own publishes to keep the handout's ordering guarantees, and mutation testing showed that a plain lock there deadlocks.

## How I checked it

319 tests cover each module on its own, each node in process, and the whole runtime over TCP. One black-box test makes 600 `/ik/solve` round trips across 30 arm shapes. Then I mutation-tested every step: I broke the code on purpose, for example dropping `C`, flipping gravity or putting the mass at the tip, and checked that a test failed. Of 83 mutants, 82 were caught. The survivor removes a lock from `set_params`, a race that no deterministic test can force.

## How this page draws it

The replay above comes from a script that starts my runtime with three links and acts as an ordinary client. It resets the arm, lets it fall with PID off, enables PID, sends five goals and waits for each result. It records `/joint_states` and the commanded setpoints. The page turns each set of joint angles into link positions with the arm's forward kinematics, and draws nothing else of its own. During development I used a live dashboard built the same way, which calls the runtime's services directly.

## What I'd do next

- **Model-based control.** Adding the gravity term `G(q)` as a feedforward would remove most of what the integral now has to do, and allow gentler gains.
- **Trajectories, not steps.** The servo jumps straight to each setpoint. A smooth joint-space trajectory would avoid the large initial efforts.

## Credits and AI use

- Specification, protocol, starter kit and autograder: AutoRob (ROB 380), University of Michigan.

**AI use.** I built this project with Claude Code (Anthropic's coding agent, using Claude Opus and Sonnet models). Claude Code wrote the dynamics, integrators, controller, inverse kinematics and tests under my direction, in the same plan → implement → audit → test loop as Project 1, with the plan, decisions and measurements kept in the repository. Every commit is co-authored by Claude, and the mutation checks were run with the agent. This write-up and statement were drafted with Claude Code from my project notes, and reviewed by me.
