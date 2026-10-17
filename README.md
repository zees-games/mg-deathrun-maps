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
