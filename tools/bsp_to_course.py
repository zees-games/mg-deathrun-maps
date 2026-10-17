#!/usr/bin/env python3
"""Converts a Source 1 community deathrun .bsp (VBSP 19/20) into an mg-deathrun course document.

    tools/bsp_to_course.py <map.bsp> <spec.json> [--out=courses/<id>.json] [--report]

The spec (tools/imports/<id>.json) is the per-map judgement the importer cannot make: which
brush entity is which trap's victim spot, where the start and finish are, the route a stand-in
runner follows. Everything else is read from the bsp.

What it does, and why:

- The world's brushes become BOXES (a course document has no meshes). `brush_boxes` and its
  helpers are copied from mg-prop-hunt-maps/tools/import_bsp.py: a brush that is not a box is
  a turned box, a vertical prism, or cut into slabs. Boxes that touch end to end are then
  merged, because a document is capped at MAX_PIECES (600) and a ceiling is a hundred slats.
- Scale: 1 unit = 0.0254 m (a true inch, a 72 unit player is 1.83 m), not the 0.01905 of the
  prop-hunt importer: deathrun's buttons need to stay 2.6 m apart and its jumps are measured
  against a 1.2 m standing jump.  Axes: godot = (x, z, -y), as in the other importers.
- Textures are NOT carried. A piece is drawn in the game's own prototype grid under a pastel
  (Kenney's grid, DrTextures): MATERIAL_TINTS says which pastel, by the author's material name.
- A trap is a func_button and what its OnPressed outputs reach: func_door (a move),
  func_door_rotating (a turn), func_rotating (a spin), a trigger_hurt (a lethal box) and an
  env_laser (a lethal beam). `dmg` > 0 on a door or rotator makes its brushes lethal. Anything
  else a button reaches (steam, sparks, explosions, sound, a conveyor, a physbox) is reported
  under `not portable` and left out. The game has ONE timeline per trap, so a button that fires
  the same door three times, or several doors on different delays, becomes one simultaneous
  motion; `--report` lists what was flattened.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bsp_read  # noqa: E402

S = 0.0254
SLAB = 28.0

# author material keyword -> pastel tint (the game draws its own grid under it)
MATERIAL_TINTS = [
    ("BRICK", (1.00, 0.88, 0.82)),
    ("METAL", (0.86, 0.90, 1.00)),
    ("PIPE", (0.86, 0.90, 1.00)),
    ("CONCRETE", (0.90, 0.90, 0.92)),
    ("GLASS", (0.80, 0.92, 1.00)),
    ("CEILING", (0.94, 0.94, 0.96)),
    ("WOOD", (1.00, 0.92, 0.80)),
    ("TILE", (0.92, 0.96, 1.00)),
    ("STONE", (0.92, 0.88, 0.80)),
]


def r(v):
    return round(v, 3)


def vec(s):
    return [float(x) for x in s.split()]


# ---- brushes -> boxes (copied from mg-prop-hunt-maps/tools/import_bsp.py) ---------------------

def planes_of(bsp, index):
    first, count, _ = bsp.brushes[index]
    return [bsp.planes[s[0]][:4] for s in bsp.brushsides[first:first + count] if not s[3]]


def z_range(planes, x, y):
    lo, hi = -1e9, 1e9
    for nx, ny, nz, d in planes:
        if abs(nz) < 1e-6:
            continue
        z = (d - nx * x - ny * y) / nz
        if nz > 0:
            hi = min(hi, z)
        else:
            lo = max(lo, z)
    return lo, hi


def box_in_frame(pts, phi, tol):
    c, sn = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    q = [(p[0] * c + p[1] * sn, -p[0] * sn + p[1] * c, p[2]) for p in pts]
    x0, x1 = min(p[0] for p in q), max(p[0] for p in q)
    y0, y1 = min(p[1] for p in q), max(p[1] for p in q)
    z0, z1 = min(p[2] for p in q), max(p[2] for p in q)
    for p in q:
        if not ((abs(p[0] - x0) < tol or abs(p[0] - x1) < tol) and (abs(p[1] - y0) < tol or abs(p[1] - y1) < tol)
                and (abs(p[2] - z0) < tol or abs(p[2] - z1) < tol)):
            return None
    return (x0, x1), (y0, y1), (z0, z1)


def turned_box(bsp, index, pts):
    first, count, _ = bsp.brushes[index]
    tried = set()
    for sd in bsp.brushsides[first:first + count]:
        if sd[3]:
            continue
        nx, ny, nz, _d = bsp.planes[sd[0]][:4]
        if abs(nz) > 1e-4:
            continue
        phi = round(math.degrees(math.atan2(ny, nx)) % 90.0, 2)
        if phi in tried or phi < 0.05 or phi > 89.95:
            continue
        tried.add(phi)
        box = box_in_frame(pts, phi, 1.5)
        if box is not None:
            return box, phi
    return None


def prism_box(pts):
    zs = sorted({round(p[2], 1) for p in pts})
    if len(zs) != 2:
        return None
    low = {(round(p[0], 1), round(p[1], 1)) for p in pts if abs(p[2] - zs[0]) < 0.15}
    high = {(round(p[0], 1), round(p[1], 1)) for p in pts if abs(p[2] - zs[1]) < 0.15}
    if low != high or len(low) < 3:
        return None
    plan = [(x, y, zs[0]) for x, y in low]
    best = None
    for (ax, ay), (bx_, by) in ((p, q) for p in low for q in low if p != q):
        phi = math.degrees(math.atan2(by - ay, bx_ - ax)) % 90.0
        box = box_in_frame(plan, phi, 1e9)
        area = (box[0][1] - box[0][0]) * (box[1][1] - box[1][0])
        if best is None or area < best[0] - 1e-6:
            best = (area, phi, box)
    _a, phi, box = best
    return (box[0], box[1], (zs[0], zs[1])), phi


def brush_boxes(bsp, index):
    """[((x range), (y range), (z range), phi)] in Source units, and whether it was sliced."""
    pts = bsp.brush_hull(index)
    if len(pts) < 4:
        return [], 0
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    z0, z1 = min(p[2] for p in pts), max(p[2] for p in pts)
    corners = sum(1 for p in pts if (abs(p[0] - x0) < 0.5 or abs(p[0] - x1) < 0.5)
                  and (abs(p[1] - y0) < 0.5 or abs(p[1] - y1) < 0.5)
                  and (abs(p[2] - z0) < 0.5 or abs(p[2] - z1) < 0.5))
    if corners == len(pts):
        return [((x0, x1), (y0, y1), (z0, z1), 0.0)], 0
    tb = turned_box(bsp, index, pts)
    if tb is not None:
        return [tb[0] + (tb[1],)], 0
    pb = prism_box(pts)
    if pb is not None:
        return [pb[0] + (pb[1],)], 0
    pl = planes_of(bsp, index)
    out = []
    if x1 - x0 >= y1 - y0:
        n = max(1, math.ceil((x1 - x0) / SLAB))
        for i in range(n):
            a, b = x0 + (x1 - x0) * i / n, x0 + (x1 - x0) * (i + 1) / n
            lo, hi = z_range(pl, (a + b) / 2, (y0 + y1) / 2)
            lo, hi = max(lo, z0), min(hi, z1)
            if hi - lo > 0.5:
                out.append(((a, b), (y0, y1), (lo, hi), 0.0))
    else:
        n = max(1, math.ceil((y1 - y0) / SLAB))
        for i in range(n):
            a, b = y0 + (y1 - y0) * i / n, y0 + (y1 - y0) * (i + 1) / n
            lo, hi = z_range(pl, (x0 + x1) / 2, (a + b) / 2)
            lo, hi = max(lo, z0), min(hi, z1)
            if hi - lo > 0.5:
                out.append(((x0, x1), (a, b), (lo, hi), 0.0))
    return out, 1


# ---- the conversion ------------------------------------------------------------------------

class Importer:
    def __init__(self, bsp, spec):
        self.bsp, self.spec = bsp, spec
        self.o = spec.get("origin", [0.0, 0.0, 0.0])       # source point that becomes godot 0,0,0
        self.notes = {"not portable": [], "flattened": [], "dropped": []}

    def g(self, p):
        return (r((p[0] - self.o[0]) * S), r((p[2] - self.o[2]) * S), r(-(p[1] - self.o[1]) * S))

    def gv(self, p):
        return [r(v) for v in self.g(p)]

    # entities
    def named(self, name):
        return [e for e in self.bsp.entities if e.get("targetname") == name]

    def model_info(self, e):
        mi = int(e["model"][1:])
        mins, maxs = self.bsp.model_bounds(mi)
        origin = vec(e["origin"]) if "origin" in e else [0.0, 0.0, 0.0]
        return mi, mins, maxs, origin

    def bsp_names(self, bi):
        b = self.bsp
        first, count, _ = b.brushes[bi]
        out = []
        for s in b.brushsides[first:first + count]:
            if s[3] or s[1] < 0:
                continue
            td = int(b.texinfo[s[1]][17])
            if 0 <= td < len(b.texdata):
                out.append(b.texnames[b.texdata[td][3]].upper())
        return out

    def world_boxes(self):
        spec = self.spec
        keep = spec.get("keep")
        out, skipped = [], 0
        for bi in sorted(self.bsp.model_brushes(0)):
            names = self.bsp_names(bi)
            invisible = False
            if names and all(n.startswith("TOOLS/") for n in names):
                joined = " ".join(names)
                if "TOOLSSKYBOX" in joined or "TOOLSNODRAW" in joined or "TRIGGER" in joined or "SKIP" in joined \
                        or "HINT" in joined or "BLOCKLIGHT" in joined or "TOOLSAREAPORTAL" in joined \
                        or "TOOLSOCCLUDER" in joined or "FOG" in joined:
                    skipped += 1
                    continue
                invisible = True
            boxes, _sl = brush_boxes(self.bsp, bi)
            tint = None
            for key, t in MATERIAL_TINTS:
                if any(key in n for n in names):
                    tint = t
                    break
            for (x0, x1), (y0, y1), (z0, z1), phi in boxes:
                if x1 - x0 < 0.05 or y1 - y0 < 0.05 or z1 - z0 < 0.05:
                    continue
                if phi:
                    c, sn = math.cos(math.radians(phi)), math.sin(math.radians(phi))
                    lx, ly = (x0 + x1) / 2, (y0 + y1) / 2
                    cx, cy, cz = lx * c - ly * sn, lx * sn + ly * c, (z0 + z1) / 2
                    box = {"at": self.gv((cx, cy, cz)), "size": [r((x1 - x0) * S), r((z1 - z0) * S), r((y1 - y0) * S)],
                           "yaw": r(phi)}
                else:
                    if keep and not (x1 >= keep[0] and x0 <= keep[1] and y1 >= keep[2] and y0 <= keep[3]
                                     and z1 >= keep[4] and z0 <= keep[5]):
                        continue
                    box = {"at": self.gv(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)),
                           "size": [r((x1 - x0) * S), r((z1 - z0) * S), r((y1 - y0) * S)]}
                box["invisible"] = invisible
                box["tint"] = tint
                box["top"] = z1
                out.append(box)
        self.notes["dropped"].append("%d tool-only brushes (sky box, nodraw, hint, triggers)" % skipped)
        return out

    @staticmethod
    def merge(boxes):
        """Merges boxes that touch end to end with identical cross sections (yaw 0 only)."""
        def key(b):
            return (b.get("yaw", 0.0) == 0.0, b["invisible"], b["tint"])

        changed = True
        eps = 0.012
        while changed:
            changed = False
            boxes.sort(key=lambda b: (b["at"][1], b["at"][2], b["at"][0]))
            for axis in (0, 2, 1):
                other = [a for a in (0, 1, 2) if a != axis]
                i = 0
                boxes.sort(key=lambda b: (round(b["at"][other[0]], 1), round(b["at"][other[1]], 1), b["at"][axis]))
                out = []
                for b in boxes:
                    if out and b.get("yaw", 0.0) == 0.0:
                        a = out[-1]
                        if (a.get("yaw", 0.0) == 0.0 and key(a) == key(b)
                                and all(abs(a["at"][k] - b["at"][k]) < eps and abs(a["size"][k] - b["size"][k]) < eps
                                        for k in other)):
                            a_hi = a["at"][axis] + a["size"][axis] / 2
                            b_lo = b["at"][axis] - b["size"][axis] / 2
                            if abs(a_hi - b_lo) < eps or b_lo < a_hi:
                                lo = a["at"][axis] - a["size"][axis] / 2
                                hi = max(a_hi, b["at"][axis] + b["size"][axis] / 2)
                                a["at"][axis] = r((lo + hi) / 2)
                                a["size"][axis] = r(hi - lo)
                                a["top"] = max(a["top"], b["top"])
                                changed = True
                                continue
                    out.append(b)
                boxes[:] = out
        return boxes

    # ---- traps ----------------------------------------------------------------------------

    def move_dir(self, e):
        p, y, _ = vec(e.get("movedir", "0 0 0"))
        pr, yr = math.radians(p), math.radians(y)
        return (math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), -math.sin(pr))

    def model_boxes_godot(self, e):
        mi, mins, maxs, origin = self.model_info(e)
        boxes = []
        for bi in self.bsp.model_brushes(mi):
            for (x0, x1), (y0, y1), (z0, z1), phi in brush_boxes(self.bsp, bi)[0]:
                if x1 - x0 < 0.05 or y1 - y0 < 0.05 or z1 - z0 < 0.05:
                    continue
                if phi:
                    c, sn = math.cos(math.radians(phi)), math.sin(math.radians(phi))
                    lx, ly = (x0 + x1) / 2, (y0 + y1) / 2
                    ctr = (lx * c - ly * sn + origin[0], lx * sn + ly * c + origin[1], (z0 + z1) / 2 + origin[2])
                    boxes.append({"at": self.gv(ctr), "size": [r((x1 - x0) * S), r((z1 - z0) * S), r((y1 - y0) * S)],
                                  "yaw": r(phi)})
                else:
                    ctr = ((x0 + x1) / 2 + origin[0], (y0 + y1) / 2 + origin[1], (z0 + z1) / 2 + origin[2])
                    boxes.append({"at": self.gv(ctr), "size": [r((x1 - x0) * S), r((z1 - z0) * S), r((y1 - y0) * S)]})
        return boxes

    def lethal(self, e):
        return float(e.get("dmg", e.get("damage", "0")) or 0) > 0

    def parse_outputs(self, e):
        out = []
        for key in ("OnPressed", "OnTrigger", "OnIn", "OnDamaged"):
            val = e.get(key)
            if not val:
                continue
            for line in str(val).replace("\x1b", "\n").split("\n"):
                f = line.strip().split(",")
                if len(f) >= 4:
                    out.append((f[0], f[1], float(f[3] or 0)))
        return out

    def resolve(self, outputs, delay=0.0, depth=0):
        """Follows logic_relay/logic_timer outputs, accumulating delays."""
        res = []
        for target, inp, d in outputs:
            ents = self.named(target)
            relays = [x for x in ents if x["classname"] in ("logic_relay", "logic_branch", "logic_case")]
            if relays and depth < 4:
                for rel in relays:
                    res += self.resolve(self.parse_outputs(rel), delay + d, depth + 1)
                continue
            res.append((target, inp, delay + d, ents))
        return res

    def trap(self, ts):
        """One trap from a spec entry: {"button": "*5", ...}."""
        bsp = self.bsp
        btn = next(e for e in bsp.entities if e.get("model") == ts["button"] and e["classname"] == "func_button")
        bm, bmins, bmaxs, borigin = self.model_info(btn)
        events = self.resolve(self.parse_outputs(btn))
        parts, first_delay, out_t, hold = [], None, None, None
        timing = dict(ts.get("timing", {}))
        flat = []
        per_target = {}
        for target, inp, delay, ents in events:
            per_target.setdefault(target, []).append((inp, delay, ents))
        for target, evs in per_target.items():
            ents = evs[0][2]
            classes = {e["classname"] for e in ents}
            opens = [(i, d) for i, d, _ in evs if i in ("Open", "Toggle", "Start", "Enable", "TurnOn", "Trigger", "Break")]
            if len(opens) > 1:
                flat.append("%s: %d firings of %s, one is kept (%s)" % (target, len(opens), opens[0][0], ts["button"]))
            if not opens:
                continue
            delay = opens[0][1]
            closes = [d for i, d, _ in evs if i in ("Stop", "StopAtStartPos", "Disable", "TurnOff", "Close")]
            for e in ents:
                cls = e["classname"]
                if cls == "func_door":
                    mi, mins, maxs, origin = self.model_info(e)
                    d = self.move_dir(e)
                    size = [maxs[k] - mins[k] for k in range(3)]
                    travel = abs(sum(abs(d[k]) * size[k] for k in range(3))) - float(e.get("lip", 0))
                    mv = [d[0] * travel, d[1] * travel, d[2] * travel]
                    mvg = [r(mv[0] * S), r(mv[2] * S), r(-mv[1] * S)]
                    lethal = self.lethal(e)
                    for b in self.model_boxes_godot(e):
                        b.update({"move": mvg, "lethal": lethal})
                        if lethal:
                            b["look"] = "block"
                        parts.append(b)
                    speed = float(e.get("speed", 100)) or 100
                    t = abs(travel) / speed
                    wait = float(e.get("wait", 4))
                    timing.setdefault("out", r(t))
                    timing.setdefault("hold", wait if wait >= 0 else -1)
                    timing.setdefault("back", r(t))
                elif cls == "func_movelinear":
                    d = self.move_dir(e)
                    dist = float(e.get("movedistance", 100))
                    mvg = [r(d[0] * dist * S), r(d[2] * dist * S), r(-d[1] * dist * S)]
                    lethal = self.lethal(e)
                    # a crusher: blockdamage > 0, or the spec says the wall is lethal where it sweeps. Its
                    # trigger_hurt children (parentname) ride with it, so they are lethal parts on the same
                    # move; the body is lethal too, since the game has no "blocked" damage.
                    lethal = lethal or float(e.get("blockdamage", 0)) > 0 or ts.get("lethal_walls", False)
                    for b in self.model_boxes_godot(e):
                        b.update({"move": mvg, "lethal": lethal})
                        if lethal:
                            b["look"] = "block"
                        parts.append(b)
                    for kid in self.bsp.entities:
                        if kid.get("parentname") == target and kid["classname"] == "trigger_hurt":
                            for b in self.model_boxes_godot(kid):
                                b.update({"move": mvg, "lethal": True, "look": "block"})
                                parts.append(b)
                    t = dist / (float(e.get("speed", 100)) or 100)
                    timing.setdefault("out", r(t))
                    timing.setdefault("back", r(t))
                    if closes:
                        timing.setdefault("hold", max(0.5, min(closes) - delay - t))
                elif cls == "func_breakable":
                    # a floor that breaks: here it drops away and comes back for the next round
                    for b in self.model_boxes_godot(e):
                        b.update({"move": [0.0, -8.0, 0.0], "lethal": False})
                        parts.append(b)
                    timing.setdefault("out", 0.25)
                    self.notes["flattened"].append("%s: %s breaks; here it drops away and comes back" % (ts["id"], target))
                elif cls == "func_door_rotating":
                    mi, mins, maxs, origin = self.model_info(e)
                    fl = int(e.get("spawnflags", 0))
                    axis = "x" if fl & 64 else ("z" if fl & 128 else "y")
                    deg = float(e.get("distance", 90)) * (-1 if fl & 2 else 1)
                    if axis == "z":
                        deg = -deg
                    for b in self.model_boxes_godot(e):
                        b.update({"turn": {"axis": axis, "degrees": r(ts.get("turn_sign", 1) * deg),
                                           "pivot": self.gv(origin)}, "lethal": self.lethal(e)})
                        parts.append(b)
                    speed = float(e.get("speed", 100)) or 100
                    t = abs(float(e.get("distance", 90))) / speed
                    wait = float(e.get("wait", 4))
                    timing.setdefault("out", r(t))
                    timing.setdefault("hold", wait if wait >= 0 else -1)
                    timing.setdefault("back", r(t))
                elif cls == "func_rotating":
                    fl = int(e.get("spawnflags", 0))
                    if fl & (4 | 8):
                        self.notes["not portable"].append("%s rotates about a horizontal axis" % target)
                        continue
                    sp = float(e.get("maxspeed", 100)) * (-1 if fl & 2 else 1)
                    for b in self.model_boxes_godot(e):
                        b.update({"spin": sp, "lethal": self.lethal(e)})
                        parts.append(b)
                    if closes:
                        timing.setdefault("hold", min(closes) - delay)
                    timing.setdefault("out", 0.3)
                    timing.setdefault("back", 0.3)
                elif cls == "trigger_hurt":
                    for b in self.model_boxes_godot(e):
                        b.update({"lethal": True, "look": "fire" if ts.get("look") == "fire" else "block"})
                        parts.append(b)
                    if closes:
                        timing.setdefault("hold", min(closes) - delay)
                elif cls == "env_laser":
                    o = vec(e["origin"])
                    tgt = self.named(e.get("LaserTarget", ""))
                    if not tgt:
                        self.notes["not portable"].append("%s: laser without a target" % target)
                        continue
                    tp = vec(tgt[0]["origin"])
                    mid = [(o[k] + tp[k]) / 2 for k in range(3)]
                    ln = math.dist(o, tp)
                    dx, dy = tp[0] - o[0], tp[1] - o[1]
                    yaw = math.degrees(math.atan2(dy, dx))
                    if abs(dx) < 1 and abs(dy) < 1:
                        # a vertical beam (a laser curtain from ceiling to floor)
                        b = {"at": self.gv(mid), "size": [r(0.3), r(ln * S), r(0.3)], "lethal": True, "look": "fire"}
                    else:
                        b = {"at": self.gv(mid), "size": [r(ln * S), r(0.3), r(0.3)], "yaw": r(yaw), "lethal": True,
                             "look": "fire"}
                    parts.append(b)
                    if closes:
                        timing.setdefault("hold", min(closes) - delay)
                else:
                    self.notes["not portable"].append("%s (%s)" % (target, cls))
                    continue
            if first_delay is None:
                first_delay = delay
        timing.setdefault("delay", ts.get("delay", 0.0))
        for k, v in (("out", 0.3), ("hold", 2.0), ("back", 1.0)):
            timing.setdefault(k, v)
        for f in flat:
            self.notes["flattened"].append("%s: %s" % (ts["id"], f))
        if not parts:
            return None
        if len(parts) > 32:
            parts = parts[:32]
            self.notes["flattened"].append("%s: only the first 32 parts kept" % ts["id"])
        floor = ts.get("button_floor")
        bo = borigin
        at = self.gv((bo[0], bo[1], floor if floor is not None else bo[2] - 1.0 / S * 0.5))
        trap = {
            "id": ts["id"], "name": ts["name"],
            "button": {"at": at, "yaw": ts.get("button_yaw", 0.0)},
            "cooldown": ts.get("cooldown", 0),
            "timing": {k: r(v) for k, v in timing.items()},
            "victim": self.gv(ts["victim"]) if "victim" in ts else self.auto_victim(parts),
            "parts": parts,
        }
        if "spared" in ts:
            trap["spared"] = self.gv(ts["spared"])
        if "sound" in ts:
            trap["sound"] = ts["sound"]
        return trap

    @staticmethod
    def auto_victim(parts):
        """On top of the first solid part, else under the first lethal one's end pose."""
        for p in parts:
            if not p.get("lethal"):
                return [p["at"][0], r(p["at"][1] + p["size"][1] / 2), p["at"][2]]
        p = parts[0]
        if all(not q.get("move") and q["size"][1] < 0.5 for q in parts):
            # beams: stand on the floor under the lowest one (they hang about knee to chest high)
            low = min(q["at"][1] for q in parts)
            return [p["at"][0], r(low - 0.9), p["at"][2]]
        mv = p.get("move", [0, 0, 0])
        return [r(p["at"][0] + mv[0]), r(p["at"][1] + mv[1] - p["size"][1] / 2), r(p["at"][2] + mv[2])]

    def build(self):
        spec = self.spec
        extra = []
        for nm in spec.get("static", []):    # brush entities that are only floor here (never fired)
            for e in self.named(nm):
                extra += [dict(b, tint=None, invisible=False, top=(b["at"][1] + b["size"][1] / 2) / S + self.o[2]) for b in self.model_boxes_godot(e)]
        for f in spec.get("fill", []):       # floor patches for shafts whose fan or push trap is not portable
            x0, x1, y0, y1, top, th = f[:6]
            ghost = len(f) > 6                # a 7th value: an invisible collider (under the drawn finish arch)
            extra.append({"at": self.gv(((x0 + x1) / 2, (y0 + y1) / 2, top - th / 2)),
                          "size": [r((x1 - x0) * S), r(th * S), r((y1 - y0) * S)],
                          "tint": None, "invisible": ghost, "top": top})
            self.notes["flattened"].append("%s over %d..%d" % ("collider" if ghost else "floor patch", y0, y1))
        boxes = self.merge(self.world_boxes() + extra)
        # the panel a button is bolted to: small world brushes right around it. The activator walks
        # straight at the button and the game draws its own, so a panel only gets in the way.
        spots = []
        for ts in spec["traps"]:
            btn = next((e for e in self.bsp.entities if e.get("model") == ts["button"]), None)
            if btn:
                spots.append(self.model_info(btn)[3])
        def panel(b):
            if max(b["size"]) > 1.3:
                return False
            return any(abs(b["at"][0] - self.g(o)[0]) < 1.0 and abs(b["at"][2] - self.g(o)[2]) < 1.0
                       and abs(b["at"][1] - self.g(o)[1]) < 0.9 for o in spots)
        n0 = len(boxes)
        boxes = [b for b in boxes if not panel(b)]
        if n0 != len(boxes):
            self.notes["dropped"].append("%d small brushes of the button panels" % (n0 - len(boxes)))
        pieces = []
        for b in boxes:
            p = {"kind": "box", "at": b["at"], "size": b["size"]}
            if b.get("yaw"):
                p["yaw"] = b["yaw"]
            wide = b["size"][0] >= 1.5 and b["size"][2] >= 1.5 and b["size"][1] <= 1.2
            p["role"] = "deck" if wide else "pillar"
            if b["tint"]:
                p["tint"] = list(b["tint"])
            if b["invisible"]:
                p["visible"] = False
            pieces.append(p)
        traps = []
        for ts in spec["traps"]:
            if ts.get("skip"):
                self.notes["not portable"].append("%s: %s" % (ts["button"], ts["skip"]))
                continue
            t = self.trap(ts)
            if t is None:
                self.notes["not portable"].append("%s (%s): nothing the game can move" % (ts["id"], ts["button"]))
                continue
            traps.append(t)
        for nt in spec.get("not_portable", []):
            self.notes["not portable"].append(nt)

        def area(a):
            yaw = a.get("yaw", 0.0)
            if "face_toward" in a:
                # godot yaw 0 faces -Z; positive turns toward -X
                tx, _ty, tz = self.g(a["face_toward"])
                ax, _ay, az = self.g(a["at"])
                yaw = r(math.degrees(math.atan2(-(tx - ax), -(tz - az))))
            return {"at": self.gv(a["at"]), "size": a["size"], "yaw": yaw}

        doc = {
            "format": 1, "kind": "course", "id": spec["id"], "name": spec["name"], "author": spec["author_line"],
            "attribution": spec["attribution"], "blurb": spec["blurb"],
            "kill_height": r((spec["kill_z"] - self.o[2]) * S), "round_seconds": spec.get("round_seconds", 0),
            "theme": spec["theme"],
            "start": area(spec["start"]), "activators": area(spec["activators"]), "finish": area(spec["finish"]),
            "end": {"runners": area(spec["end"]["runners"]), "activators": area(spec["end"]["activators"])},
            "pieces": pieces, "traps": traps,
            "toys": [dict(t, at=self.gv(t["at"])) for t in spec.get("toys", [])],
            "route": [{"at": self.gv(p["at"]), **{k: v for k, v in p.items() if k != "at"}} for p in spec["route"]],
        }
        return doc


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    out_path = None
    for a in argv[1:]:
        if a.startswith("--out="):
            out_path = a[6:]
    bsp = bsp_read.Bsp(args[0]).load()
    spec = json.load(open(args[1]))
    imp = Importer(bsp, spec)
    doc = imp.build()
    out_path = out_path or os.path.join(HERE, "..", "courses", spec["id"] + ".json")
    text = json.dumps(doc, indent="\t") + "\n"
    with open(out_path, "w") as fh:
        fh.write(text)
    print("%s: %d pieces, %d traps, %d bytes" % (spec["id"], len(doc["pieces"]), len(doc["traps"]), len(text)))
    for k, v in imp.notes.items():
        for line in v:
            print("  %s: %s" % (k, line))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
