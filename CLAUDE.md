# mg-deathrun-maps

The courses mg-deathrun plays, as JSON documents. Read `../../CLAUDE.md` and `../mg-deathrun/CLAUDE.md` first: the format is defined and validated by mg-deathrun's course document code, and `courses/README.md` is the mapper's copy of it.

**`courses/` is what the game reads**, through a dot-bootstrap link (`mg-deathrun/.gitignore` names it: `# bootstrap-link: mg-deathrun-maps/courses`). The game reads every `.json` there plus the practice course built into it; a refused document is listed by `dr_courses` with the reason, and every other course still plays.

**`tools/build_courses.py` writes every document, and the JSON is committed.** Edit the builder, run it, commit both. `--check` (CI) fails when a committed file differs from what the builder writes. The builder exists because the corridor and the walkway beside it must agree along their whole length: a section lays its floor, trap, button and route points at a cursor, and it refuses two buttons closer than 2.6 m (the nearer would be pressed for the further).

**Split out of mg-deathrun on 2026-10-06**, the way mg-wipeout-maps was split from mg-wipeout; the history of the two courses and the builder before that is in mg-deathrun.

## What a level is here, for the nightly quota

A level is **a course that plays differently from every other**, or a section kind that changes how one plays. In order of preference:

1. **An existing course rebuilt so it plays the way its blurb says.**
2. **A new section kind in the builder**, made of existing part motions (move/turn/spin, solid or lethal), used in at least one course.
3. **A new course** — only with a blurb that says what makes it different, every trap sprung on its victim in `mg-deathrun/examples/headless_courses.tscn`, and a render (`mg-deathrun/tools/shot.sh`).

## Converted community maps

`tools/bsp_to_course.py` (reader: `tools/bsp_read.py`; both derived from mg-prop-hunt-maps' importer) turns a Source 1 .bsp plus `tools/imports/<id>.json` into `courses/<id>.json`; `build_courses.py --check` ignores these. Rules: a map's `attribution` credits the author, names the page and licence as listed, and says it is removed on request; no author texture, model or sound is carried. Download into a fresh empty scratch dir, never into the repo. A map whose floors are `prop_static` models (Source `death_run`) has nothing the importer sees: pick brush-floored maps. Brush entities (func_breakable floors) that are only floor go in the spec's `static`; shafts whose fan/wind trap is not portable get a `fill` patch. Every skipped trap says why in the spec.

## Toys

`Course.toy()` puts one of dot-props' loose toys on the floor: a football in every start room (`_start`) and a pair in each end arena (balls on the ice, barrels on the foundry's banks, a ball each side of the altar), written as the document's `toys`. Loose only: a trampoline would be a way past a trap and anything solid cover in the showdown. mg-deathrun's `headless_courses` checks each stands clear and stays put.

## Publishing

**This repository is a pack of its own, mounted on the server alone.** mg-deathrun's `game.yml` names it under `server_dependencies`; a server mounts it at `res://dot_cloud/<owner>/mg-deathrun-maps/<version>/` and the game adds that mount's `courses/` to its catalogue (`DrModule._add_delivered_courses`). It is never in a client's content sync: a client is sent the one document being played. `.github/workflows/release.yml` runs `build_courses.py --check` and then dot-ci's release with `pack: true` (and `server-compat: false`, because there is no code in it to check).

`project.godot` exists only so dot-ci's release can import this repository and attach the `-pack.zip`; it carries the editor's own header and no comments, because the editor rewrites the file on its first save and a checkout would show it modified.

**Not yet on GitHub** (2026-10-06): the remote is set, the repository is the owner's to create, and nothing is pushed or published.

**`hops` (2026-10-06)** is the first section with no trap: small platforms over a pit, side to side, a running jump apart (2.4 m gaps against a ~4.8 m running jump at mg-deathrun's defaults), so one landing at a time is enough and chaining them (auto_bunny_hop, or timing it) is what it rewards. In both courses, after the falling blocks; mg-deathrun's `headless_courses` stand-in clears both with auto-hop off.

**`swing` and The Temple (2026-10-08)**: the first section whose killer TURNS (a blade on an axle over the corridor, swung 180 degrees down through it and back) and the first that is DODGED rather than jumped: it kills the middle of the corridor and passes over a runner pressed to either wall. A trap may now name a `spared` spot as well as its `victim` (the courses README has it), and mg-deathrun's `headless_courses` stands somebody there and fails the trap if they die. That check found the first blade's design wrong the first time it ran: 5.6 m on an axle 6.4 m up came down through head height at the walls too, because a blade's tip draws a circle, so how low it reaches in the middle and how high it passes at the walls are one number; the builder's docstring has the arithmetic, and the blade is 2.75 m on an axle 3.6 m up. **The Temple** (`dr_temple`) is the course built round it: three blades, a pit, floor spikes, stepping stones over green water, a ceiling, a hop stretch and one closing wall, ending in a sunken court round a three-step altar (`temple_arena`). Every trap is sprung on its victim, every blade misses its spared runner, and a stand-in runs the course to the end; rendered with `tools/shot.sh --view=course --dr-course-ids=dr_temple` and `--view=trap --trap=tp_first_blade --after=0.5`.
