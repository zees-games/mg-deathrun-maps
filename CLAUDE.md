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

## Publishing

**This repository is a pack of its own, mounted on the server alone.** mg-deathrun's `game.yml` names it under `server_dependencies`; a server mounts it at `res://dot_cloud/<owner>/mg-deathrun-maps/<version>/` and the game adds that mount's `courses/` to its catalogue (`DrModule._add_delivered_courses`). It is never in a client's content sync: a client is sent the one document being played. `.github/workflows/release.yml` runs `build_courses.py --check` and then dot-ci's release with `pack: true` (and `server-compat: false`, because there is no code in it to check).

**Not yet on GitHub** (2026-10-06): the remote is set, the repository is the owner's to create, and nothing is pushed or published.
