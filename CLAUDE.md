# Portfolio site: notes for Claude

Personal robotics portfolio for grad-school applications and job hunting. It also hosts the
user's AutoRob (UMich ROB 380) course portfolio pages, which course staff grade. It's an
Astro 7 static site with three.js demos, deployed to GitHub Pages by
`.github/workflows/deploy.yml`. Read `README.md` first: it covers the structure, adding a
project, the P3 demo pipeline, and deploying.

## Commands

- `npm run dev`: dev server on http://localhost:4321 with live reload.
- `npm run build`: must pass before any commit. Then check pages at desktop and 375 px widths,
  in light and dark mode.
- `PROJECT3_DIR=… npm run assets:robot` / `assets:record`: regenerate the P3 model or recording.
  `PROJECT1_DIR=… npm run assets:record-p1` and `PROJECT2_DIR=… npm run assets:record-p2` do
  the same for P1 and P2. These need the user's local course folder (paths in `CLAUDE.local.md`
  when present). Cloud
  sessions can't run them; the generated files in `public/` are committed.

## Rules

- **The user writes their own voice.** Never invent biography, claims, links or the AI-use
  statement. Leave the dashed `.todo` boxes for them and keep `src/site.ts` TODOs as TODOs.
- **Course policy.** AI use must be disclosed. Whether course solution code may be public is
  still being asked of course staff, so never copy course solution source into this repo.
  Recordings, models and write-ups only.
- **Demos show real output.** Every interactive visual replays data recorded from the user's
  own runtimes (see `scripts/record_p*.py`). Don't re-implement course algorithms in the
  browser to fake a demo.
- **Credit third-party assets** next to where they appear: the RPO robot is CERN-OHL-W-2.0 by
  Roboparty (license in `public/models/`); Fetch would be CC BY-NC-SA 4.0. Don't publish
  copyrighted music in videos on the public site.
- **Keep it small.** No CSS framework, no client-side framework; three.js only where a demo
  needs it.
- **The site is public** at https://devinhu666.github.io/ (repository
  `DevinHu666/DevinHu666.github.io`), and course staff grade it there. Every push to `main`
  deploys, so commit and push only what the user has approved, after `npm run build` and the
  page checks above.
