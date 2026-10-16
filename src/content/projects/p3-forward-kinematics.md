---
title: "Forward kinematics, and a humanoid that dances"
summary: "A ROS-style node graph that turns any URDF plus joint angles into every link's pose. I pushed it past the assignment until an open-source humanoid could dance the Rickroll on the beat."
status: published
order: 30
course: "ROB 380 · Project 3"
courseProject: 3
tags: ["forward kinematics", "URDF", "quaternions", "pub/sub", "three.js", "Python"]
featured: true
date: "2026-10"
demo: "p3-rickroll"
highlights:
  - "Full marks on the checkpoint autograder"
  - "42 black-box tests against an independent reference"
  - "Real robots, unmodified: Fetch, a 23-joint humanoid, and descriptions near 1 MiB"
  - "64 keyframes locked to 113 BPM, with no drift"
---

## The problem

A robot arrives as the text of a real [URDF](https://wiki.ros.org/urdf/XML) file, the format ROS robots ship in. My runtime has to answer "where is every part of the robot right now?" as the joints move: parse and validate the description, build its kinematic tree, and turn joint angles into a pose for every link, accurate to 0.1 mm and 0.1 mrad. Kinematics, transform and URDF libraries are not allowed. The rotation math, the tree traversal and the transform composition are all mine, on quaternions.

It runs as a small ROS-like system over the publish/subscribe runtime I built in Project 1. The course autograder talks to it over a TCP/JSON protocol:

<figure class="diagram">
<svg viewBox="0 0 850 300" role="img" aria-label="Node graph: param_server holds robot_description; robot_state_publisher turns joint states into /tf; robot_world_state_publisher composes /tf and the global pose into /xform_world; joint_state_publisher and finite_state_machine drive the dance; the viewer draws /xform_world.">
  <style>
    .n { fill: var(--surface); stroke: var(--line); stroke-width: 1.5; }
    .g { fill: color-mix(in srgb, var(--highlight) 14%, var(--surface)); stroke: var(--highlight); stroke-width: 1.5; }
    .t { fill: var(--text); font: 600 13px var(--font); }
    .s { fill: var(--muted); font: 12px var(--mono); }
    .a { stroke: var(--muted); stroke-width: 1.5; fill: none; marker-end: url(#arrow); }
  </style>
  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 10 5 0 10z" fill="var(--muted)"/></marker></defs>
  <rect class="g" x="20" y="20" width="200" height="54" rx="10"/><text class="t" x="36" y="44">param_server</text><text class="s" x="36" y="62">robot_description</text>
  <rect class="g" x="330" y="20" width="230" height="54" rx="10"/><text class="t" x="346" y="44">robot_state_publisher</text><text class="s" x="346" y="62">parse, validate, FK edges</text>
  <rect class="g" x="330" y="130" width="230" height="54" rx="10"/><text class="t" x="346" y="154">robot_world_state_publisher</text><text class="s" x="346" y="172">compose to global_frame</text>
  <rect class="n" x="670" y="130" width="160" height="54" rx="10"/><text class="t" x="686" y="154">three.js viewer</text><text class="s" x="686" y="172">draws each link</text>
  <rect class="n" x="20" y="130" width="200" height="54" rx="10"/><text class="t" x="36" y="154">joint_state_publisher</text><text class="s" x="36" y="172">servo, beat timing</text>
  <rect class="n" x="20" y="230" width="200" height="54" rx="10"/><text class="t" x="36" y="254">finite_state_machine</text><text class="s" x="36" y="272">choreography</text>
  <path class="a" d="M220 47H326"/><text class="s" x="240" y="39">get_param</text>
  <path class="a" d="M445 74V126"/><text class="s" x="453" y="104">/tf</text>
  <path class="a" d="M560 157H666"/><text class="s" x="571" y="149">/xform_world</text>
  <path class="a" d="M220 145C280 145 290 96 330 84"/><text class="s" x="232" y="118">/joint_states</text>
  <path class="a" d="M120 230V188"/><text class="s" x="128" y="214">/joint_trajectory</text>
  <path class="a" d="M220 170H326"/><text class="s" x="232" y="192">/global_pose</text>
</svg>
<figcaption class="muted">Highlighted nodes are graded. The other two drive the dance, and the viewer is an ordinary client.</figcaption>
</figure>

## Forward kinematics

Each joint contributes `T_joint(q) = T_origin · T_motion(q)`, where `T_origin` comes from the URDF's `xyz` and fixed-axis roll-pitch-yaw. Revolute and continuous joints rotate about their normalized axis. Prismatic joints slide along the axis as written, without normalizing it. Every rotation is a unit quaternion. The root is the one link that is no joint's child, and a link's pose is the product of the edges on the path from the root, parent first. `/xform_world` then adds the robot's global pose and publishes each link as a column-major 4×4 matrix, the layout three.js reads directly.

The less glamorous half is robustness:
- **Real-world XML.** Comments containing markup, entities, CDATA, joints that appear before their links, and hollow `<joint>` elements nested in `<gazebo>` blocks all have to parse.
- **Validation before swap.** A description is checked in full before it touches the running robot. A bad one is reported and the old robot keeps running.
- **Line sizes.** Real descriptions travel as single protocol lines of up to 1 MiB, so every hop reads lines of any length.

## Making a humanoid dance

The assignment asks for a short video of a robot following a choreography. I wanted a full humanoid, so I loaded [Roboparty's RPO](https://github.com/Roboparty/roboto_origin), an open-source 23-joint humanoid. Its URDF passed my validator unmodified. Then I built what a dance needs on top of the graded runtime:

- **On the beat.** The finite state machine got timed states. Each target goes out with a `time_from_start`, and the joint publisher arrives exactly then along a smoothstep. Every deadline is scheduled from the previous deadline, not from when a timer happened to wake, so a long dance never drifts against the music.
- **The whole body moves.** Virtual `base_*` joints drive `/global_pose`, so the robot can bob and step sideways instead of floating in place.
- **A choreography compiler.** I write poses in body parts and degrees, like "left arm forward 22°, right knee 24°", and a per-robot map compiles them to joint angles:
  - **Hip axes.** RPO's hip axes are tilted 30°, so "leg out" is an exact combination of two joints.
  - **Flat feet.** The ankles counter-rotate so the soles stay flat.
  - **Grounding.** The compiler runs my own FK to put the stance sole on the floor and keep a planted foot planted, so side steps actually travel.
  - **Closed loops.** A hovering foot never lands exactly where the pose puts it, so one pass creeps 6.2 cm. The compiler spreads that creep over the 19.1 s loop, about 3 mm/s of slide you can't see.
  - **Limits.** Any pose outside a joint limit is an error that names the joint.
- **The dance.** Rick Astley's moves from *Never Gonna Give You Up* at 113 BPM: the side step-touch, both arms swinging across the body, pointing at the camera, and the forearm roll. There are 64 keyframes in a 36-beat loop. The replay here is silent.

## How I checked it

Tests drive the runtime the way the autograder does, over TCP, and compare against an independent reference written with plain 4×4 matrices and Rodrigues' formula, not my quaternion code:
- general axes, continuous joints past ±π, and prismatic joints under rotated origins;
- each `/joint_states` message replacing the last, with stamps passed through unchanged;
- the publishing rate, late subscribers, and a reload leaving no old links behind;
- the Fetch robot at random configurations within its limits.

The choreography has its own tests. Every keyframe stays within limits, and an independent FK puts the stance soles on the floor to within 0.1 mm. Planted feet stay put, and the loop closes. All 42 pass.

## How this page draws it

The replay above is not an animation I authored. It records one loop of `/xform_world` from the running system as an ordinary client. The browser blends neighbouring frames, lerping positions and slerping rotations, so every pose sits between two poses my runtime published. To keep the page light, the 30 MB of STL meshes were simplified to 250k triangles, a 1.07 MB GLB. During development I use a live viewer instead: a small bridge relays the runtime's TCP stream to the browser as Server-Sent Events.

## What I'd do next

- **Exact foot placement.** The feet are placed by FK plus bookkeeping, not inverse kinematics. Project 4 brings IK, which would let a foot land exactly where a step should go.
- **A second humanoid.** Compiling the same dance for Berkeley Humanoid Lite, a robot with different joint conventions, would show that the choreography format really is robot-independent.

## Credits and AI use

- RPO robot description © Roboparty, [CERN-OHL-W-2.0](https://github.com/Roboparty/roboto_origin). The meshes are simplified for the web.
- Specification, starter kit and autograder: AutoRob (ROB 380), University of Michigan.

<p class="todo">TODO before publishing: state in your own words how you used AI tools on this project. Course policy requires the disclosure, and the course permits the use itself.</p>
