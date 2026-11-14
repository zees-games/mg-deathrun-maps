The courses for [mg-deathrun](https://github.com/zees-games/mg-deathrun): long corridors of traps, a walkway beside each with a button for every trap, and an end arena. 20 courses, plus a practice course built into the game.

A course is a JSON document, not a scene. The server reads every `.json` file in its course directory and sends the current course to each client when a round begins, so players need no course files. To add a course, drop one file in the directory. The format is in [courses/README.md](courses/README.md).

## Using it

[dot-bootstrap](https://github.com/modcommunity/dot-bootstrap) clones this repository next to mg-deathrun and links it in as `courses/`. Run `./game.sh` in mg-deathrun and you play these courses. On a server they are delivered as one pack (`deathrun_maps`), which `./game.sh online` and `./game.sh server` build for you.

## Our courses

| Course | What is in it |
| --- | --- |
| `dr_ice_works` (Ice Works) | Ice corridor: closing walls, a rolling bridge, sinking floes, a mouth full of teeth |
| `dr_foundry` (The Foundry) | Fire, saws and a press over lava that the activator can open |
| `dr_temple` (The Temple) | Stone halls where blades swing instead of fall |
| `dr_quarry` (The Quarry) | Two rolling bridges, a rockfall, then blades over the last hops |

## Converted community courses

Each was converted from a Source 1 deathrun map. Only the layout and traps are used; the art is drawn in the game's own prototype grid. Each document carries an `attribution` line with the author, source page and licence.

| Course | Author | Source | Licence |
| --- | --- | --- | --- |
| `dr_aztecan` (Sunstone Causeway) | n1be | [GameBanana](https://gamebanana.com/mods/126828) | CC BY-NC-ND 4.0 |
| `dr_eazy` (Eazy) | Hakita | [GameBanana](https://gamebanana.com/mods/126944) | CC BY-NC-ND 4.0 |
| `dr_family_guy` (Quahog Run) | Severn7 and Matasume | [GameBanana](https://gamebanana.com/mods/126959) | CC BY-NC-ND 4.0 |
| `dr_fogtown` (Fog Town) | Krypt | [GameBanana](https://gamebanana.com/mods/127180) | CC BY-NC-ND 4.0 |
| `dr_death` (Death Row) | Deathmaker192 | [GameBanana](https://gamebanana.com/mods/127338) | CC BY-NC-ND 4.0 |
| `dr_handicap` (Handicap) | Flawless1 | [GameBanana](https://gamebanana.com/mods/126987) | CC BY-NC-ND 4.0 |
| `dr_helix` (Helix) | HyperCUBE | [GameBanana](https://gamebanana.com/mods/126992) | CC BY-NC-ND 4.0 |
| `dr_horror` (Horror House) | mgproductions | [GameBanana](https://gamebanana.com/mods/127000) | CC BY-NC-ND 4.0 |
| `dr_iceworld` (Ice World) | metz10 | [GameBanana](https://gamebanana.com/mods/127005) | CC BY-NC-ND 4.0 |
| `dr_internet` (Internet) | tuomas | [GameBanana](https://gamebanana.com/mods/127024) | CC BY-NC-ND 4.0 |
| `dr_internet_2` (Internet II) | tuomas | [GameBanana](https://gamebanana.com/mods/127024) | CC BY-NC-ND 4.0 |
| `dr_oreo` (Percolate Oreo) | Loller Dan | [GameBanana](https://gamebanana.com/mods/127264) | CC BY-NC-ND 4.0 |
| `dr_parking_garage` (Parking Garage) | Bloodhunter4rc | [GameBanana](https://gamebanana.com/mods/127127) | CC BY-NC-ND 4.0 |
| `dr_ramesses` (Pharaoh's Descent) | RiddlerAJ | [GameBanana](https://gamebanana.com/mods/127386) | CC BY-NC-ND 4.0 |
| `dr_sections` (Sections) | -[Element]- (map deathrun_sections_fix), from the Deathrun MapPack 2008 | [GameBanana](https://gamebanana.com/mods/124076) | CC BY-NC-ND 4.0 |
| `dr_southpark` (South Park) | Linoxi | [GameBanana](https://gamebanana.com/mods/127198) | CC BY-NC-ND 4.0 |

If you made one of these maps and want it removed, open an issue at <https://github.com/zees-games/mg-deathrun-maps/issues> and it goes.

## Building the courses

`tools/build_courses.py` writes the four own courses from lists of sections (a trapdoor, spike walls, a crusher, jaws, falling blocks, floes). Each section lays its floor, trap, button and route together.

```bash
python3 tools/build_courses.py            # rewrite courses/*.json
python3 tools/build_courses.py --check    # exit 1 if a file differs from the builder's output
```

The JSON is committed and CI runs `--check`. Hand-written documents are fine too: any `.json` file in `courses/` loads.

Converted courses come from `tools/bsp_to_course.py <map.bsp> tools/imports/<id>.json`. It turns world brushes into boxes, and a `func_button` plus what its outputs reach (doors, movers, rotators, hurt triggers, lasers, breakable floors) into a trap. The spec in `tools/imports/` holds the per-map choices (start, finish, route, victims, skipped buttons and why). What cannot be ported (wind, fans, physics props, effects, always-on kill triggers) is printed and listed in the spec as a `skip`. The `.bsp` files are not in this repository.

mg-deathrun's `examples/headless_courses.tscn` checks every course: a stand-in runs it to the end, every trap is sprung on its victim spot, an activator reaches every button, and both ends of the arena are stood in.

## Licence

MIT, see [LICENSE](LICENSE). The converted courses keep the licences listed above.
