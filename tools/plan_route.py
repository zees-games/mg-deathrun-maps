#!/usr/bin/env python3
"""Plans the `route` (runners) and `walkway` (activators) of an imported course, and writes both into its spec.

    tools/plan_route.py <map.bsp> <spec.json> [--dry]

A converted map bends, climbs and drops; the hand-written courses run straight along -Z, which is
all the stand-ins knew. This reads the document the importer WOULD write, rasterises its boxes
(and every trap's solid parts at rest, since a trapdoor is a floor until it is sprung) into a
voxel grid, finds the walkable surfaces (a floor with a standing person's height free above it)
and searches over them:

- **route**: start -> finish for a runner. Moves: walk (a step of at most the controller's 0.4 m),
  jump up (to 1.0 m), drop (to 3.5 m), and a running jump over a gap (to 3.6 m). Each jump becomes a
  `jump` landing, the way mg-deathrun's stand-in expects them. The grid's cost prefers a walk to
  a jump and a jump to a long drop, so the route is the one a person would take.
- **walkway**: the activator's spawn -> every button in the order the route passes them, walking
  only (no jump, no drop: the suite's `bot_walk_toward` does not jump), one point per button
  carrying `"button": <trap id>`.

Both are written to the spec in SOURCE units (the importer converts them), as hand-editable lists,
so a path the planner got wrong is a spec edit, not a re-run. A spec whose `route` already says
`"planned": false` is left alone. A spec's `via` (source points) makes the route pass them in order.
"""
import heapq
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bsp_read  # noqa: E402
import bsp_to_course as C  # noqa: E402

H = 0.3            # horizontal cell, m
V = 0.2            # vertical layer, m
HEAD = 9           # layers a standing person needs free (1.8 m)
STEP = 2           # walk step in layers (0.4 m)
JUMP_UP = 5        # jump-up in layers (1.0 m)
DROP = 21          # drop in layers (4.2 m; there is no fall damage); a spec's `max_drop_m` raises it (a shaft the map hands people down by teleport)
WALK_DROPS = False  # a spec's `walkway_drops`: the activators fall down the same shaft (walking off a ledge is a walk)
GAP = 14           # a running jump over a gap, in cells (4.2 m; a flat jump carries about 4.8 m)
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


class Grid:
    def __init__(self, doc, kill_y):
        boxes = []
        for p in doc["pieces"]:
            if p.get("kind") == "box" or (p.get("kind") == "teleport" and p.get("solid", True)):
                boxes.append((p["at"], p["size"], p.get("yaw", 0.0), False))
        for t in doc["traps"]:
            for pt in t["parts"]:
                if pt.get("lethal") or pt.get("push") or pt.get("pitch"):
                    continue
                boxes.append((pt["at"], pt["size"], pt.get("yaw", 0.0), False))
        self.kills = [p for p in doc["pieces"] if p.get("kind") == "kill"]
        xs0 = min(b[0][0] - max(b[1][0], b[1][2]) for b in boxes)
        xs1 = max(b[0][0] + max(b[1][0], b[1][2]) for b in boxes)
        zs0 = min(b[0][2] - max(b[1][0], b[1][2]) for b in boxes)
        zs1 = max(b[0][2] + max(b[1][0], b[1][2]) for b in boxes)
        self.y0 = max(kill_y, min(b[0][1] - b[1][1] / 2 for b in boxes))
        y1 = max(b[0][1] + b[1][1] / 2 for b in boxes) + 3
        self.x0, self.z0 = xs0, zs0
        self.nx, self.nz = int((xs1 - xs0) / H) + 2, int((zs1 - zs0) / H) + 2
        self.ny = int((y1 - self.y0) / V) + 2
        occ = np.zeros((self.nx, self.nz, self.ny), dtype=bool)
        for at, size, yaw, _ in boxes:
            self._raster(occ, at, size, yaw, True)
        self.occ = occ
        bad = np.zeros_like(occ)
        for k in self.kills:
            self._raster(bad, k["at"], k["size"], k.get("yaw", 0.0), True, grow=0.3)
        # a node: free voxel with a solid one under it and HEAD free voxels above
        solid_below = np.zeros_like(occ)
        solid_below[:, :, 1:] = occ[:, :, :-1]
        c = np.cumsum(np.pad(occ, ((0, 0), (0, 0), (1, 0))).astype(np.int32), axis=2)
        top = np.minimum(np.arange(self.ny) + HEAD, self.ny)
        blocked = c[:, :, top] - c[:, :, np.arange(self.ny)]
        self.node = (~occ) & solid_below & (blocked == 0) & (~bad)
        self.node[:, :, 0] = False
        # a node with floor missing within two cells (0.6 m) of it is an edge: costed, so a route keeps to the middle of a
        # strip instead of hugging its rim (a stand-in that runs the rim falls off it)
        nd = self.node.copy()
        for dy in (1, 2):
            nd[:, :, dy:] |= self.node[:, :, :-dy]
            nd[:, :, :-dy] |= self.node[:, :, dy:]
        edge = np.zeros_like(self.node)
        for ax in (0, 1):
            for sh in (1, 2, 3):
                for sg in (1, -1):
                    edge |= ~np.roll(nd, sg * sh, axis=ax)
        self.edge = self.node & edge
        # teleport pads: a node on one has a single way out, to where the pad sends it (stepping on it is
        # being sent). A pad for the other side is only a floor, so each side has its own mask
        self.padmask = {False: np.zeros(occ.shape, dtype=np.int16), True: np.zeros(occ.shape, dtype=np.int16)}
        self.pad_dest = []
        for i, p in enumerate(q for q in doc["pieces"] if q.get("kind") == "teleport"):
            top = p["at"][1] + p["size"][1] / 2
            zone = np.zeros_like(occ)
            if p.get("solid", True):
                self._raster(zone, (p["at"][0], top + 0.35, p["at"][2]), (p["size"][0], 1.3, p["size"][2]), p.get("yaw", 0.0), True)
            else:
                # a trigger volume catches feet inside the box grown by the body (DrCourseDoc.pad_contains)
                self._raster(zone, (p["at"][0], p["at"][1] - 0.9, p["at"][2]), (p["size"][0] + 0.8, p["size"][1] + 1.8, p["size"][2] + 0.8), p.get("yaw", 0.0), True)
            side = p.get("for", "")
            for walk_only in (False, True):
                if side == "" or side == ("activators" if walk_only else "runners"):
                    self.padmask[walk_only][zone & self.node] = i + 1
            self.pad_dest.append(p["to"])
        self.pad_nodes = {}
        # the head's room matters above a drop's landing too: `occ` itself is kept for that

    def _raster(self, arr, at, size, yaw, val, grow=0.0):
        hx, hy, hz = size[0] / 2 + grow, size[1] / 2 + grow, size[2] / 2 + grow
        r = math.hypot(hx, hz) if yaw else 0
        if yaw:
            xa, xb, za, zb = at[0] - r, at[0] + r, at[2] - r, at[2] + r
        else:
            xa, xb, za, zb = at[0] - hx, at[0] + hx, at[2] - hz, at[2] + hz
        ia, ib = max(0, int((xa - self.x0) / H)), min(self.nx - 1, int((xb - self.x0) / H))
        ja, jb = max(0, int((za - self.z0) / H)), min(self.nz - 1, int((zb - self.z0) / H))
        ka = max(0, int(math.floor((at[1] - hy - self.y0) / V)))
        kb = min(self.ny - 1, int(math.ceil((at[1] + hy - self.y0) / V)) - 1)
        if ia > ib or ja > jb or kb < ka:
            return
        if not yaw:
            arr[ia:ib + 1, ja:jb + 1, ka:kb + 1] = val
            return
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        gx = self.x0 + (np.arange(ia, ib + 1) + 0.5) * H - at[0]
        gz = self.z0 + (np.arange(ja, jb + 1) + 0.5) * H - at[2]
        dx, dz = np.meshgrid(gx, gz, indexing="ij")
        lx, lz = dx * c - dz * s, dx * s + dz * c
        m = (np.abs(lx) <= hx) & (np.abs(lz) <= hz)
        sub = arr[ia:ib + 1, ja:jb + 1, ka:kb + 1]
        sub[m] = val

    def cell(self, p):
        return int((p[0] - self.x0) / H), int((p[2] - self.z0) / H), int(round((p[1] - self.y0) / V))

    def world(self, n):
        return (self.x0 + (n[0] + 0.5) * H, self.y0 + n[2] * V, self.z0 + (n[1] + 0.5) * H)

    def nearest(self, p, radius=40):
        x, z, y = self.cell(p)
        best, bd = None, 1e9
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                xx, zz = x + dx, z + dz
                if not (0 <= xx < self.nx and 0 <= zz < self.nz):
                    continue
                col = self.node[xx, zz]
                if not col.any():
                    continue
                ys = np.nonzero(col)[0]
                k = ys[np.argmin(np.abs(ys - y))]
                d = (dx * dx + dz * dz) * H * H + (abs(k - y) * V * 2) ** 2
                if d < bd:
                    best, bd = (xx, zz, int(k)), d
        return best

    def has(self, x, z, y):
        return 0 <= x < self.nx and 0 <= z < self.nz and 0 <= y < self.ny and self.node[x, z, y]

    def column_node(self, x, z, lo, hi):
        """The node in column (x, z) within layers lo..hi (inclusive), nearest to `lo`'s middle, or None."""
        if not (0 <= x < self.nx and 0 <= z < self.nz):
            return None
        lo, hi = max(lo, 1), min(hi, self.ny - 1)
        if lo > hi:
            return None
        ys = np.nonzero(self.node[x, z, lo:hi + 1])[0]
        return None if len(ys) == 0 else int(ys[0] + lo)

    def pad_target(self, n, walk_only):
        k = int(self.padmask[walk_only][n[0], n[1], n[2]])
        if not k:
            return None
        if k not in self.pad_nodes:
            to = self.pad_dest[k - 1]
            self.pad_nodes[k] = self.nearest((to[0], to[1] + 0.1, to[2]))
        return self.pad_nodes[k]

    def edges(self, n, walk_only):
        pad = self.pad_target(n, walk_only)
        if pad is not None:
            yield pad, 0.5, 3
            return
        yield from self._edges(n, walk_only)

    def _edges(self, n, walk_only):
        x, z, y = n
        for dx, dz in DIRS:
            x2, z2 = x + dx, z + dz
            diag = dx and dz
            step = None
            for dy in (0, 1, -1, 2, -2):
                if self.has(x2, z2, y + dy):
                    step = y + dy
                    break
            if step is not None:
                if diag and not (self._near(x + dx, z, y) and self._near(x, z + dz, y)):
                    pass
                else:
                    yield (x2, z2, step), (math.hypot(dx, dz) * H + abs(step - y) * V + (0.6 if self.edge[x2, z2, step] else 0.0)), 0
                    continue
            dist = math.hypot(dx, dz) * H
            if walk_only and not WALK_DROPS:
                continue
            if walk_only:
                lo = max(1, y - DROP)
                ys = np.nonzero(self.node[x2, z2, lo:y - STEP])[0] if 0 <= x2 < self.nx and 0 <= z2 < self.nz else []
                if len(ys) and not diag:
                    land = int(ys[-1] + lo)
                    if not self.occ[x2, z2, land:y + HEAD].any():
                        yield (x2, z2, land), dist + 1.0 + (y - land) * V * 0.8, 0
                continue
            # jump up
            up = self.column_node(x2, z2, y + STEP + 1, y + JUMP_UP)
            # headroom is checked above the landing, not from the runner's feet: a solid step's own face fills y+1..up, and that
            # is a wall to climb, not a ceiling (Ramesses' 0.94 m stairs were never climbable before)
            if up is not None and not self.occ[x2, z2, up + 1:max(up + 1, y + HEAD + 1)].any():
                yield (x2, z2, up), dist + 3.0, 1
                continue
            # drop: the column free from the ledge's head height down to the landing
            lo = max(1, y - DROP)
            ys = np.nonzero(self.node[x2, z2, lo:y - STEP])[0] if 0 <= x2 < self.nx and 0 <= z2 < self.nz else []
            if len(ys):
                land = int(ys[-1] + lo)
                if not self.occ[x2, z2, land:y + HEAD].any():
                    yield (x2, z2, land), dist + 1.0 + (y - land) * V * 0.8, 0
                    # no `continue`: a pit with a floor far below (a lava room whose stepping stones are the way across) is
                    # also a drop, and the jump over the gap must stay an edge or the stones are never reached
                    # (Ramesses stalled at the first lava room for exactly this once `max_drop_m` let the pit floor count)
            # a running jump over a gap, in the same direction. Straight only: the stand-in aims at the landing's
            # middle, and a diagonal jump across a corner lands on the rim and falls (found on Percolate Oreo)
            if diag:
                continue
            for L in range(2, GAP + 1):
                x3, z3 = x + dx * L, z + dz * L
                far = self.column_node(x3, z3, y - 4, y + 3)
                if far is None:
                    continue
                clear = True
                for q in range(1, L):
                    xq, zq = x + dx * q, z + dz * q
                    if not (0 <= xq < self.nx and 0 <= zq < self.nz) or self.occ[xq, zq, y + 3:y + HEAD].any():
                        clear = False
                        break
                if clear:
                    yield (x3, z3, far), L * H * 2.2 + 6.0, 2
                break_out = True
                if clear:
                    break

    def _near(self, x, z, y):
        return any(self.has(x, z, y + d) for d in (0, 1, -1, 2, -2))


def astar(grid, a, b, walk_only):
    openq = [(0.0, 0, a)]
    came, cost = {a: None}, {a: 0.0}
    tie = 0
    bx, bz, by = b
    while openq:
        _, _, cur = heapq.heappop(openq)
        if cur == b:
            break
        c0 = cost[cur]
        for nxt, w, kind in grid.edges(cur, walk_only):
            nc = c0 + w
            if nc < cost.get(nxt, 1e18):
                cost[nxt] = nc
                came[nxt] = (cur, kind)
                h = math.hypot(nxt[0] - bx, nxt[1] - bz) * H * 0.9
                tie += 1
                heapq.heappush(openq, (nc + h, tie, nxt))
    if b not in came:
        astar.last = came
        return None
    path, cur = [], b
    while cur is not None:
        prev = came[cur]
        path.append((cur, prev[1] if prev else 0))
        cur = prev[0] if prev else None
    path.reverse()
    return path


def compress(grid, path, max_leg=9.0):
    """Waypoints for a path: straight runs collapse, every jump keeps its take-off and landing."""
    pts = []
    i = 0
    n = len(path)
    while i < n:
        node, kind = path[i]
        if kind == 3:
            # a teleport: the pad is a point to reach, then the landing a point to carry on from
            if not pts or pts[-1][0] != path[i - 1][0]:
                pts.append((path[i - 1][0], False))
            pts.append((node, False))
            i += 1
            continue
        if kind:
            # the landing of a jump (the take-off was the previous point)
            if not pts or pts[-1][0] != path[i - 1][0]:
                pts.append((path[i - 1][0], False))
            pts.append((node, True))
            i += 1
            continue
        j = i
        far = i
        while j + 1 < n and path[j + 1][1] == 0 and j - i < 40:
            j += 1
            if self_line(grid, path, i, j, max_leg):
                far = j
        pts.append((path[far][0], False))
        i = far + 1 if far > i else i + 1
    # tidy: drop an immediate duplicate
    out = []
    for p in pts:
        if out and out[-1][0] == p[0] and out[-1][1] == p[1]:
            continue
        out.append(p)
    return out


def via_points(grid, legs):
    """Waypoints leg by leg, so every via point is one. A via that lies just past a jump's landing
    becomes the landing: the first node across a gap is the far floor's edge, and a bot that comes
    down on the edge of a small pad slides off it, where one aimed at the pad's middle does not."""
    out = []
    for leg in legs:
        pts = compress(grid, leg)
        if len(pts) >= 2 and pts[-1][0] == leg[-1][0] and not pts[-1][1] and pts[-2][1]:
            a, b = pts[-2][0], pts[-1][0]
            if math.hypot(b[0] - a[0], b[1] - a[1]) * H < 2.0 and abs(b[2] - a[2]) <= 1:
                pts[-2:] = [(b, True)]
        for p in pts:
            if not out or out[-1][0] != p[0]:
                out.append(p)
    return out


def self_line(grid, path, i, j, max_leg):
    a, b = path[i][0], path[j][0]
    d = math.hypot(b[0] - a[0], b[1] - a[1]) * H
    if d > max_leg:
        return False
    steps = max(2, int(d / (H * 0.5)))
    for s in range(1, steps):
        t = s / steps
        x = a[0] + (b[0] - a[0]) * t
        z = a[1] + (b[1] - a[1]) * t
        y = a[2] + (b[2] - a[2]) * t
        xi, zi = int(round(x)), int(round(z))
        if not any(grid.has(xi, zi, int(round(y)) + d2) for d2 in (-2, -1, 0, 1, 2)):
            return False
        # corner-cutting: the straight line must stay inside the path's own corridor
    for k in range(i, j + 1):
        n = path[k][0]
        # distance of node k from the segment a-b in the plane
        ax, az, bx, bz = a[0], a[1], b[0], b[1]
        dx, dz = bx - ax, bz - az
        L2 = dx * dx + dz * dz
        t = 0 if L2 == 0 else max(0, min(1, ((n[0] - ax) * dx + (n[1] - az) * dz) / L2))
        px, pz = ax + dx * t, az + dz * t
        if math.hypot(n[0] - px, n[1] - pz) * H > 1.2:
            return False
    return True


def to_source(grid, imp, node):
    gx, gy, gz = grid.world(node)
    o = imp.o
    sx, sy, sz = round(gx / C.S + o[0], 1), round(-gz / C.S + o[1], 1), round(gy / C.S + o[2], 1)
    for f in imp.spec.get("folds", []):         # a folded level's points go back where the map has them
        x0, x1, y0, y1 = f["xy"]
        if x0 <= sx <= x1 and y0 <= sy <= y1 and sz >= f.get("min_z", -1e9):    # `min_z` (after the move): a level stacked ABOVE another shares its footprint
            return [sx, sy, round(sz - f["dz"], 1)]
    return [sx, sy, sz]


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    dry = "--dry" in argv
    bsp = bsp_read.Bsp(args[0]).load()
    spec_path = args[1]
    spec = json.load(open(spec_path))
    global DROP, WALK_DROPS, GAP
    DROP = int(spec.get("max_drop_m", DROP * V) / V)
    GAP = int(round(spec.get("max_gap_m", GAP * H) / H))      # a spec's `max_gap_m`: a running jump the map demands (up to ~4.8 m)
    WALK_DROPS = bool(spec.get("walkway_drops", False))
    imp = C.Importer(bsp, spec)
    doc = imp.build()
    grid = Grid(doc, doc["kill_height"])
    print("grid %d x %d x %d, %d walkable nodes" % (grid.nx, grid.nz, grid.ny, int(grid.node.sum())))

    def area_pt(a):
        return (a["at"][0], a["at"][1] + 0.1, a["at"][2])

    start = grid.nearest(area_pt(doc["start"]))
    fin = grid.nearest(area_pt(doc["finish"]))
    act = grid.nearest(area_pt(doc["activators"]))
    if not start or not fin or not act:
        print("start/finish/activators not on a walkable surface:", start, fin, act)
        return 1
    # `via`: source points the route must pass in order. A map whose runners loop round a hub they
    # could cut straight across (the activators' plaza is the same floor) is planned leg by leg.
    # A via written {"at": [x, y, z], "jump": true} is a hand-placed jump: the route runs straight
    # from the point before it and jumps at the edge, for a take-off the grid search would take
    # from a corner it had to turn on (no run-up, and the bot falls short).
    path, cur, legs = [], start, []
    for v in spec.get("via", []):
        hand = isinstance(v, dict)
        node = grid.nearest(imp.gv(v["at"] if hand else v), radius=8)
        if node is None:
            print("via point %s is not on a walkable surface" % (v,))
            return 1
        if hand and v.get("jump"):
            path.append((cur, 0))
            legs.append([(cur, 0), (node, 1)])
            cur = node
            continue
        leg = astar(grid, cur, node, False)
        if leg is None:
            print("NO ROUTE to via point %s: %d nodes reachable" % (v, len(astar.last)))
            return 1
        path += leg[:-1]
        legs.append(leg)
        cur = node
    leg = astar(grid, cur, fin, False)
    path = None if leg is None else path + leg
    legs.append(leg)
    if path is None:
        print("NO ROUTE start -> finish: %d nodes reachable" % len(astar.last))
        w = grid.world(fin)
        near = min(astar.last, key=lambda n: (grid.world(n)[0] - w[0]) ** 2 + (grid.world(n)[2] - w[2]) ** 2 + (grid.world(n)[1] - w[1]) ** 2)
        if os.environ.get("PLAN_PLOT"):
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            walk = grid.node.any(axis=2)
            occ2 = grid.occ[:, :, 8:30].any(axis=2)
            img = np.zeros((grid.nx, grid.nz, 3))
            img[occ2] = (0.3, 0.3, 0.3)
            img[walk] = (0.8, 0.8, 0.5)
            for n in astar.last:
                img[n[0], n[1]] = (0.2, 0.8, 0.2)
            for n, c in ((start, (1, 0, 0)), (fin, (0, 0, 1))):
                img[max(0, n[0] - 3):n[0] + 4, max(0, n[1] - 3):n[1] + 4] = c
            plt.figure(figsize=(12, 12))
            plt.imshow(np.transpose(img, (1, 0, 2)), origin="upper")
            plt.savefig(os.environ["PLAN_PLOT"], dpi=70)
        print("closest reachable to the finish: source %s (finish %s)" % (to_source(grid, imp, near), to_source(grid, imp, fin)))
        return 1
    pts = compress(grid, path) if len(legs) < 2 else via_points(grid, legs)
    jumps = sum(1 for p in pts if p[1])
    print("route: %d nodes -> %d points, %d jumps, length %.0f m" % (
        len(path), len(pts), jumps, len(path) * H))
    route = []
    for node, jump in pts:
        e = {"at": to_source(grid, imp, node)}
        if jump:
            e["jump"] = True
        route.append(e)

    # walkway: the buttons in route order
    def prog(t):
        b = t["button"]["at"]
        best, bd = 0, 1e9
        for k, (node, _) in enumerate(pts):
            w = grid.world(node)
            d = math.hypot(w[0] - b[0], w[2] - b[2]) + 2 * abs(w[1] - b[1])
            if d < bd:
                best, bd = k, d
        return best

    order = sorted(doc["traps"], key=prog)
    walkway, cur, failed = [], act, []
    for t in order:
        b = t["button"]["at"]
        goal = grid.nearest((b[0], b[1] + 0.1, b[2]), radius=8)
        if goal is None:
            failed.append(t["id"])
            continue
        seg = astar(grid, cur, goal, True)
        if seg is None:
            failed.append(t["id"])
            continue
        wp = compress(grid, seg, 6.0)
        for k, (node, _) in enumerate(wp):
            e = {"at": to_source(grid, imp, node)}
            if k == len(wp) - 1:
                e["button"] = t["id"]
            walkway.append(e)
        cur = goal
    print("walkway: %d points, buttons unreachable on foot: %s" % (len(walkway), failed or "none"))
    spec["route"] = route
    if len(route) > 1:
        # runners and activators face the way the route first goes (the suite checks it), not the finish
        spec["start"]["face_toward"] = route[1]["at"]
    spec["walkway"] = walkway
    spec.setdefault("unwalkable", failed)
    if not dry:
        with open(spec_path, "w") as fh:
            json.dump(spec, fh, indent=1)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
