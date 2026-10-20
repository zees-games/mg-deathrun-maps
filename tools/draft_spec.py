#!/usr/bin/env python3
"""Writes a first tools/imports/<id>.json for a community deathrun .bsp: the part of the spec that
is mechanical (origin, start, activators, one trap per func_button, theme), leaving the judgement
(finish, end arenas, which traps are skipped and why, kill_z) as arguments or later edits.

    tools/draft_spec.py <map.bsp> <id> "<Name>" "<author>" <gamebanana id> "<licence as listed>" \
        --finish=x,y,z [--kill=z] [--end-runners=x,y,z] [--end-activators=x,y,z] [--blurb=...] [--out=file]

Then `plan_route.py` fills `route` and `walkway`, and `bsp_to_course.py` writes the course.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bsp_read  # noqa: E402


def o(e):
    return [float(x) for x in e.get("origin", "0 0 0").split()]


def main(argv):
    pos = [a for a in argv[1:] if not a.startswith("--")]
    opt = dict(a[2:].split("=", 1) for a in argv[1:] if a.startswith("--") and "=" in a)
    path, mid, name, author, gb, lic = pos[:6]
    bsp = bsp_read.Bsp(path).load()
    ents = bsp.entities
    ct = [o(e) for e in ents if e["classname"] == "info_player_counterterrorist"]
    t = [o(e) for e in ents if e["classname"] == "info_player_terrorist"]
    cen = lambda ps: [sum(p[k] for p in ps) / len(ps) for k in range(3)]
    sc, st = cen(ct), cen(t)
    fin = [float(v) for v in opt["finish"].split(",")]
    floor = lambda p: [round(p[0]), round(p[1]), round(min(q[2] for q in (ct if p is sc else t)))]
    sc, st = floor(sc), floor(st)
    traps = []
    for e in ents:
        if e["classname"] == "func_button" and e.get("model", "").startswith("*") and any(k.startswith("On") for k in e):
            idx = e["model"][1:]
            traps.append({"button": e["model"], "id": "t" + idx, "name": "Trap %d" % (len(traps) + 1)})
    kill = float(opt["kill"]) if "kill" in opt else bsp.model_bounds(0)[0][2] + 32
    pt = lambda k, d: [float(v) for v in opt[k].split(",")] if k in opt else d
    spec = {
        "id": mid, "name": name,
        "author_line": "%s (GameBanana)" % author,
        "attribution": ("Converted from %s by %s (https://gamebanana.com/mods/%s, %s as listed there). Geometry only: boxes and traps rebuilt from the map's "
                        "brushes and entities, none of the author's textures, models or sounds. Shipped on the strength of credit and removal on request: "
                        "tell the repository owner and the map is taken out." % (os.path.basename(path), author, gb, lic)),
        "blurb": opt.get("blurb", "A classic deathrun: a course of traps, and the activator watching them."),
        "origin": [round(sc[0]), round(sc[1]), sc[2]],
        "kill_z": kill, "kill_hurts": True,
        "theme": {"sky": [0.55, 0.68, 0.85], "horizon": [0.86, 0.9, 0.95], "void": [0.08, 0.1, 0.16], "sun": [1.0, 0.95, 0.85], "deck": [0.74, 0.78, 0.86]},
        "start": {"at": sc, "size": [9, 3, 8], "face_toward": fin},
        "activators": {"at": st, "size": [9, 3, 6], "face_toward": fin},
        "finish": {"at": fin, "size": [4, 3, 4], "yaw": 0},
        "end": {"runners": {"at": pt("end-runners", fin), "size": [3, 3, 8], "yaw": 180},
                "activators": {"at": pt("end-activators", fin), "size": [3, 3, 8], "yaw": 0}},
        "route": [], "traps": traps, "toys": [],
    }
    out = opt.get("out", os.path.join(HERE, "imports", mid + ".json"))
    with open(out, "w") as fh:
        json.dump(spec, fh, indent=1)
        fh.write("\n")
    print("%s: %d candidate traps, start %s, activators %s" % (out, len(traps), sc, st))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
