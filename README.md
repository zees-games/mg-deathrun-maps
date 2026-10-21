The courses for [**mg-deathrun**](https://github.com/zees-games/mg-deathrun): long corridors of traps, a walkway beside each with a button for every trap, and an end arena. Two courses to start with, plus the practice course built into the game.

Every course is a **JSON document**, not a scene. A server reads the documents in its course directory and sends the one it is playing to every client as the round begins, so players need no course files at all and a new course is one file dropped into a directory. [`courses/README.md`](courses/README.md) is the format.

## Using it
[dot-bootstrap](https://github.com/modcommunity/dot-bootstrap) clones this repository next to mg-deathrun and links it into the game as `courses/`, so `./game.sh` in mg-deathrun plays these courses with nothing else to do. On a server they are delivered as a pack of their own (`deathrun_maps`), which mg-deathrun's `./game.sh online` and `./game.sh server` build for you.

## The courses

| Course | What it is |
| --- | --- |
| `dr_ice_works` (Ice Works) | A long corridor of ice: walls that close, a bridge that rolls, floes that sink and a mouth full of teeth |
| `dr_foundry` (The Foundry) | Fire, saws and a press, over a floor of lava that the activator can open |
| `dr_temple` (The Temple) | Stone halls where the blades swing instead of fall: stay off the middle, and jump the rest |
| `dr_quarry` (The Quarry) | Two rolling bridges and a rockfall between them, then a blade over the last hops: the rhythm never lets up |
| `dr_sections` (Sections) | Converted from the community map `deathrun_sections_fix` (see below): six rooms in a row, lasers, a falling floor and a sinking floor, a very long run |
| `dr_aztecan` (Sunstone Causeway) | A sandstone causeway over a pit: a ring of deck tiles with four traps, converted from the community map `deathrun_aztecan_finalb3` by n1be ([GameBanana 126828](https://gamebanana.com/mods/126828)); credit and removal on request, as below |
| `dr_internet` (Internet) | A space and internet themed run down one long straight corridor with four traps worked from the walkway beside it, converted from the community map `deathrun_internet` by tuomas ([GameBanana 127024](https://gamebanana.com/mods/127024), CC BY-NC-ND 4.0 as listed); credit and removal on request, as below |
| `dr_internet_2` (Internet II) | The second corridor of the same community map `deathrun_internet` by tuomas ([GameBanana 127024](https://gamebanana.com/mods/127024), CC BY-NC-ND 4.0 as listed): the same straight dash with two traps worked from the walkway beside it; credit and removal on request, as below |
| `dr_handicap` (Handicap) | A catwalk over a deadly floor, converted from the community map `deathrun_hadicap_v6` by Flawless1 ([GameBanana 126987](https://gamebanana.com/mods/126987), CC BY-NC-ND 4.0 as listed): a 4 m gap, a spinning door across the corner and two stretches of whirling blades on the long run west, three traps worked from the walkway beside it; credit and removal on request, as below |
| `dr_eazy` (Eazy) | A hall of rooms over a pit, converted from the community map `Deathrun_Eazy` by Hakita ([GameBanana 126944](https://gamebanana.com/mods/126944), CC BY-NC-ND 4.0 as listed): a bridge that drops out under the runners, a ceiling-high push over two platforms, a hammer, a crusher, a wall of blocks, four explosions and a floor that rolls over. Geometry only; credit to the author, and we remove it on request. |

### Converted community maps

`tools/bsp_to_course.py <map.bsp> tools/imports/<id>.json` rebuilds a Source 1 deathrun map (VBSP 19/20) as a course document: world brushes become boxes, and a `func_button` plus what its outputs reach (`func_door`, `func_movelinear`, `func_door_rotating`, `func_rotating`, `trigger_hurt`, `env_laser`, a `func_breakable` floor) becomes a trap. The spec in `tools/imports/` is the per-map judgement (start, finish, route, victims, which buttons are skipped and why). Textures, models and sounds are never carried: the pieces are drawn in the game's own prototype grid. What cannot be ported (wind, fans, physics props, fire and steam effects, kills that are a separate always-on `trigger_hurt`) is printed by the importer and listed in the spec as a `skip` with its reason.

Each converted course carries an `attribution` line (author, source page, the licence as listed there, and that the map is removed on request). The `.bsp` is not in this repository.

## How they are made

`tools/build_courses.py` writes every document in `courses/` from a list of **sections** per course (a trapdoor, spike walls, a crusher, jaws, falling blocks, floes), each of which lays its floor, its trap, the button opposite it and the route a stand-in follows together, then lays the walls and the walkway the length of what was built.

```bash
python3 tools/build_courses.py            # rewrite courses/*.json
python3 tools/build_courses.py --check    # exit 1 if a file differs from what the builder writes
```

The JSON is still what the game reads and is committed; CI runs `--check`, so a hand edit to a built document is caught instead of being lost on the next build. Hand-written documents the builder does not produce are fine too: anything in `courses/` with a `.json` extension is loaded.

Every course is checked by mg-deathrun's `examples/headless_courses.tscn`: a stand-in runs it to the end, every trap is sprung on somebody standing at its `victim` spot, an activator walks to every button, and both ends of the arena are stood in.

## License

MIT. See [LICENSE](LICENSE).
