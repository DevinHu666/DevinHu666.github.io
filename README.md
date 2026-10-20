# Portfolio site

A personal robotics portfolio for grad-school applications and job hunting. It also serves as
the AutoRob (ROB 380) course portfolio. Static [Astro](https://astro.build) site with three.js
demos, hosted on GitHub Pages.

```bash
npm install          # once
npm run dev          # http://localhost:4321, live reload
npm run build        # static site in dist/
```

Keep this folder outside iCloud Drive (it lives in `~/portfolio-site`), so the iCloud client
doesn't sync `node_modules/`. GitHub is the backup.

## Before publishing

- [ ] `src/site.ts`: your tagline, intro, and links (GitHub, LinkedIn, CV, email if you want it public).
- [ ] `src/pages/about.astro` and the end of each project write-up (P1, P2, P3):
      replace the dashed **TODO** boxes with your own AI-use statement. Course policy requires
      disclosing AI tools, and the text should be something you can defend in an interview.
- [ ] Read the P1, P2 and P3 write-ups and rewrite anything that doesn't sound like you.
- [ ] Ask course staff whether your code may be public. Until then, keep the code repositories private.
      The site itself contains no course solution code, only recordings and write-ups.

## Adding a project

One Markdown file in `src/content/projects/`. The schema is in `src/content.config.ts`:

| `status` | Shows up as |
| --- | --- |
| `published` | a card linking to `/projects/<file name>/`, built from the Markdown body |
| `in-progress` | a card saying "write-up coming", no page |
| `planned` | a dashed roadmap card, no page |

Set `courseProject` to list it on the AutoRob page. Set `demo` to embed an interactive block
above the write-up (`p1-astar`, `p2-pendularm` and `p3-rickroll` exist; add new ones to the enum in
`src/content.config.ts` and render them in `src/pages/projects/[slug].astro`).

## The Project 1 and 2 demos

Both replay recordings of the real runtimes, made by scripts that start a runtime and talk to it
as an ordinary TCP client (`scripts/rosbridge_client.py`, port 9095 must be free). They never
write into the course folders.

- `public/data/p1-astar.json`: four maps and the runtime's `/plan_path` answers. The first map
  is the graded `maps/student_map.json`; the others are generated from fixed seeds.
  Re-record with `PROJECT1_DIR=<path to project1> npm run assets:record-p1`
  (`scripts/record_p1.py`). `src/components/AstarGrid.astro` draws them as SVG.
- `public/data/p2-pendularm.json`: 36 s of `/joint_states` from a 3-link arm falling with PID
  off, then reaching five `/ik_action` goals. Re-record with
  `PROJECT2_DIR=<path to project2-python> npm run assets:record-p2` (`scripts/record_p2.py`).
  `src/components/PendularmReplay.astro` draws links from the joint angles (forward kinematics
  only) and plots each angle against its setpoint.

## The Project 3 demo

The 3D replay is real runtime output, not an animation authored for the page:

- `public/models/rpo.glb`: the RPO humanoid's 24 STL meshes (30 MB) simplified to a 1.07 MB GLB,
  one node per link. Rebuild with `PROJECT3_DIR=<path to project3-python> npm run assets:robot`
  (`scripts/build-robot-glb.mjs`, which reads `$PROJECT3_DIR/viewer/assets/rpo/`).
  The meshes are a modified version of Roboparty's design files, so their license ships with
  them as `rpo.LICENSE.txt` (CERN-OHL-W-2.0).
- `public/data/p3-rickroll.json`: one loop of `/xform_world` (24 links × 202 frames, 250 kB).
  Re-record with `PROJECT3_DIR=<path to project3-python> npm run assets:record`
  (`scripts/record_p3.py`). The script starts that runtime in demo mode (port 9095 must be
  free), loads the robot, deploys `fsm/rpo_rickroll.json`, and keeps the second pass so the
  loop is seamless.
- Both generated files are committed. The course code that produces them is not in this
  repository, so a clone, CI, or a cloud session can build the site but can't regenerate them.
- `src/components/RobotReplay.astro`: puts each link group at the recorded pose, blending
  neighbouring frames (lerp/slerp). It offers orbit, scrub, speed, camera presets and link
  frames, plus **Save video**, which records exactly one loop as WebM with `MediaRecorder`. That
  file can go straight to the course video deliverable (add music while editing).

## Deploying

1. Create a GitHub repository and push this folder as its root. A repository named
   `<user>.github.io` is served at `https://<user>.github.io/`; any other name at
   `https://<user>.github.io/<repo>/`.
2. When you're ready to publish, make the repository public, then open Settings → Pages →
   Source and choose "GitHub Actions". `.github/workflows/deploy.yml` builds on every push
   to `main`, and publishes with the right base path only while the repository is public.
   While it's private, each push is just a build check.
3. Optional: a custom domain (about $10–15 a year). Set it in Settings → Pages, then set
   `SITE_URL` to it and `BASE_PATH` to `/` in the workflow.
