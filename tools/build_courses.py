#!/usr/bin/env python3
"""Writes every course in courses/ from the sections below.

A course is a JSON document (see game/dr_course_doc.gd and courses/README.md), and nothing
stops a mapper writing one by hand. These are generated instead because a deathrun course is
two corridors that have to agree with each other along their whole length -- the runners'
floor, the walls, the activators' walkway beside it with a button opposite every trap -- and
a hand-written file is two hundred numbers that drift apart the first time a section is
moved. Here a section is a function that lays its stretch of floor, its trap, its button and
its route points at the cursor, and moves the cursor on.

    tools/build_courses.py            # rewrite every course
    tools/build_courses.py --check    # fail if a file on disk is not what this would write

Every course runs along -Z. The runners' corridor is x -3.25..3.25 with its floor at y 0;
the walls are half a metre thick either side, the left one 3.8 m tall and the right one level
with the activators' walkway beside it at y 3, x 3.75..8.75. Over the right wall is a thin rail
and an invisible clip, so an activator can look straight down into the corridor and cannot
jump into it -- a wall above the walkway, which the first render had, hid the near half of the
corridor from the person whose whole job is watching it. Buttons stand at x 4.6, opposite
their trap.
"""

import json
import os
import sys

HALF = 3.25          # the runners' corridor, either side of x 0
WALL = 0.5           # wall thickness
WALL_TOP = 3.8
WALL_BOTTOM = -7.0   # walls go down past every pit, so a fall is never out of the side
WALK_Y = 3.0         # the walkway's floor
WALK_X0 = HALF + WALL          # 3.75
WALK_X1 = WALK_X0 + 5.0        # 8.75
BUTTON_X = 4.6
PIT_Y = -5.5          # the middle of a spike bed under a gap
POOL_TOP = -0.6       # the top of a pool under ice floes

# White, on the ground's texture: snow, ice that floats. The "safe" role is green, and a tint
# only darkens -- the first render had a field of green snowmen.
SNOW = [0.95, 0.97, 1.0]


def r(v):
    return round(v, 3)


def v3(x, y, z):
    return [r(x), r(y), r(z)]


class Course:
    def __init__(self, cid, name, blurb, theme, author="mg-deathrun", kill_height=-10.0, round_seconds=0.0):
        self.doc = {
            "format": 1, "kind": "course", "id": cid, "name": name, "author": author,
            "blurb": blurb, "theme": theme, "kill_height": kill_height,
        }
        if round_seconds > 0:
            self.doc["round_seconds"] = round_seconds
        self.pieces = []
        self.traps = []
        self.route = []
        # The front of what has been built: the next section starts here and runs toward -Z.
        self.z = 2.0
        self._start()

    # --- Primitives ----------------------------------------------------------

    def box(self, x, y, z, sx, sy, sz, role="deck", **extra):
        piece = {"kind": "box", "at": v3(x, y, z), "size": v3(sx, sy, sz)}
        if role != "deck":
            piece["role"] = role
        piece.update(extra)
        self.pieces.append(piece)

    def floor(self, z0, z1, x0=-HALF, x1=HALF, y=0.0, role="deck"):
        """A slab whose TOP is at y, from z0 down to z1 (z1 < z0)."""
        self.box((x0 + x1) / 2, y - 0.5, (z0 + z1) / 2, x1 - x0, 1.0, z0 - z1, role)

    def kill(self, z0, z1, look="spikes", y=PIT_Y, height=1.0, tint=None, x0=-HALF, x1=HALF):
        piece = {"kind": "kill", "at": v3((x0 + x1) / 2, y, (z0 + z1) / 2),
                 "size": v3(x1 - x0, height, z0 - z1), "look": look}
        if tint:
            piece["tint"] = tint
        self.pieces.append(piece)

    def point(self, x, z, jump=False, reach=None, **flags):
        p = {"at": v3(x, 0.0, z)}
        if jump:
            p["jump"] = True
        if reach is not None:
            p["reach"] = reach
        p.update(flags)
        self.route.append(p)

    def trap(self, tid, name, z, parts, timing, victim, cooldown=0.0):
        trap = {
            "id": tid, "name": name,
            "button": {"at": v3(BUTTON_X, WALK_Y, z), "yaw": 90.0},
            "timing": timing, "parts": parts, "victim": victim,
        }
        if cooldown > 0:
            trap["cooldown"] = cooldown
        for other in self.traps:
            gap = abs(other["button"]["at"][2] - z)
            if gap < 2.6:
                raise SystemExit("%s: buttons %s and %s are %.1f m apart; an activator would press the wrong one"
                                 % (self.doc["id"], other["id"], tid, gap))
        self.traps.append(trap)

    # --- The two ends --------------------------------------------------------

    def _start(self):
        # The start room: z +8 .. +2, the gate across its front at +1.8.
        self.floor(8.0, 2.0)
        self.box(0.0, WALL_TOP / 2, 8.25, 2 * HALF + 2 * WALL, WALL_TOP, 0.5, "pillar")
        self.doc["start"] = {"at": v3(0.0, 0.0, 5.0), "size": v3(2 * HALF, 3.0, 6.0), "yaw": 0.0}
        self.doc["activators"] = {"at": v3((WALK_X0 + WALK_X1) / 2, WALK_Y, 5.0),
                                  "size": v3(4.0, 3.0, 4.0), "yaw": 0.0}

    def run(self, length, role="deck"):
        """Plain floor."""
        z0 = self.z
        self.floor(z0, z0 - length, role=role)
        self.z -= length
        self.point(0.0, self.z + 1.0)

    def finish(self, arena):
        z0 = self.z
        self.floor(z0, z0 - 4.0, role="safe")
        self.doc["finish"] = {"at": v3(0.0, 0.0, z0 - 2.5), "size": v3(2 * HALF, 3.0, 3.0), "yaw": 0.0}
        self.point(0.0, z0 - 2.5)
        self.z -= 4.0
        self.box(0.0, WALL_TOP / 2, self.z - 0.25, 2 * HALF + 2 * WALL, WALL_TOP, 0.5, "pillar")
        self._walls_and_walkway()
        arena(self, self.z - 4.0)

    def _walls_and_walkway(self):
        z0, z1 = 8.5, self.z - 0.5
        length = z0 - z1
        mid = (z0 + z1) / 2
        height = WALL_TOP - WALL_BOTTOM
        y = (WALL_TOP + WALL_BOTTOM) / 2
        self.box(-HALF - WALL / 2, y, mid, WALL, height, length, "pillar")
        right = WALK_Y - WALL_BOTTOM
        self.box(HALF + WALL / 2, (WALK_Y + WALL_BOTTOM) / 2, mid, WALL, right, length, "pillar")
        # The walkway, its outer wall, its two ends, the rail and the clip over the right wall.
        self.box((WALK_X0 + WALK_X1) / 2, WALK_Y - 0.5, mid, WALK_X1 - WALK_X0, 1.0, length)
        self.box(WALK_X1 + 0.25, WALK_Y + 1.9, mid, 0.5, 3.8, length, "pillar")
        self.box((WALK_X0 + WALK_X1) / 2, WALK_Y + 1.9, z0 + 0.25, WALK_X1 - WALK_X0, 3.8, 0.5, "pillar")
        self.box((WALK_X0 + WALK_X1) / 2, WALK_Y + 1.9, z1 - 0.25, WALK_X1 - WALK_X0, 3.8, 0.5, "pillar")
        self.box(HALF + WALL / 2, WALK_Y + 1.0, mid, 0.12, 0.1, length, "cannon")
        self.box(HALF + WALL / 2, WALK_Y + 2.6, mid, WALL, 5.2, length, "pillar", visible=False)

    def write(self, directory):
        self.doc["pieces"] = self.pieces
        self.doc["traps"] = self.traps
        self.doc["route"] = self.route
        path = os.path.join(directory, self.doc["id"] + ".json")
        return path, json.dumps(self.doc, indent="\t") + "\n"

    # --- Traps -----------------------------------------------------------------

    def trapdoor(self, tid, name, length=6.0, look="spikes", tint=None):
        """Two leaves hinged at the walls over a pit. Whoever is on one slides off it."""
        z0, z1 = self.z, self.z - length
        mid = (z0 + z1) / 2
        if look == "liquid":
            self.kill(z0, z1, "liquid", y=-3.0, height=2.0, tint=tint)
        else:
            self.kill(z0, z1, look, tint=tint)
        parts = []
        for side in (-1, 1):
            x = side * HALF / 2
            parts.append({
                "at": v3(x, -0.25, mid), "size": v3(HALF, 0.5, length),
                "turn": {"axis": "z", "degrees": 95.0 * side, "pivot": v3(side * HALF, -0.25, mid)},
            })
        self.trap(tid, name, mid, parts, {"out": 0.25, "hold": 3.0, "back": 1.5}, v3(1.4, 0.0, mid))
        self.z = z1
        self.point(0.0, z1 + 0.5)

    def spike_walls(self, tid, name, sides="both", depth=4.0, height=2.0):
        """Spikes out of the walls, across the corridor. One wall sweeps the whole width; two meet
        in the middle. Taller than a jump: they are not jumped."""
        z0 = self.z
        self.floor(z0, z0 - depth - 2.0)
        mid = z0 - 1.0 - depth / 2
        parts = []
        reach = 2 * HALF - 0.1 if sides != "both" else HALF + 0.05
        for side, face in ((-1, "right"), (1, "left")):
            if sides == "both" or (sides == "left" and side < 0) or (sides == "right" and side > 0):
                parts.append({
                    "at": v3(side * (HALF + WALL / 2), height / 2, mid), "size": v3(0.4, height, depth - 0.2),
                    "look": "spikes", "face": face, "lethal": True, "move": v3(-side * reach, 0.0, 0.0),
                })
        victim_x = -1.5 if sides == "right" else 1.5
        self.trap(tid, name, mid, parts, {"out": 0.35, "hold": 0.8, "back": 1.2}, v3(victim_x, 0.0, mid))
        self.z -= depth + 2.0
        self.point(0.0, self.z + 1.0)

    def crusher(self, tid, name, depth=3.0, out=0.4):
        """A spiked ceiling that comes down to the floor."""
        z0 = self.z
        self.floor(z0, z0 - depth - 2.0)
        mid = z0 - 1.0 - depth / 2
        # The beam it hangs from, across the top of the walls.
        self.box(0.0, WALL_TOP + 0.3, mid, 2 * HALF + 2 * WALL, 0.6, depth + 0.4, "pillar")
        parts = [{"at": v3(0.0, 3.4, mid), "size": v3(2 * HALF, 0.8, depth), "look": "spikes", "face": "down",
                  "lethal": True, "move": v3(0.0, -3.0, 0.0)}]
        self.trap(tid, name, mid, parts, {"out": out, "hold": 0.6, "back": 1.6}, v3(0.5, 0.0, mid))
        self.z -= depth + 2.0
        self.point(0.0, self.z + 1.0)

    def jaws(self, tid, name, depth=3.0):
        """Teeth from above and below that meet at chest height: a monster's mouth."""
        z0 = self.z
        self.floor(z0, z0 - depth - 2.0)
        mid = z0 - 1.0 - depth / 2
        self.box(0.0, WALL_TOP + 0.3, mid, 2 * HALF + 2 * WALL, 0.6, depth + 0.4, "pillar")
        parts = [
            {"at": v3(0.0, 3.4, mid), "size": v3(2 * HALF, 0.8, depth), "look": "spikes", "face": "down",
             "lethal": True, "move": v3(0.0, -2.0, 0.0), "tint": [1.0, 0.92, 0.85]},
            {"at": v3(0.0, -0.5, mid), "size": v3(2 * HALF, 0.8, depth), "look": "spikes", "face": "up",
             "lethal": True, "move": v3(0.0, 1.5, 0.0), "tint": [1.0, 0.92, 0.85]},
        ]
        self.trap(tid, name, mid, parts, {"out": 0.3, "hold": 0.7, "back": 1.4}, v3(-0.5, 0.0, mid))
        self.z -= depth + 2.0
        self.point(0.0, self.z + 1.0)

    def floor_spikes(self, tid, name, depth=4.0, decor=None):
        """Spikes up out of the floor. `decor` is a function that lays still things on the stretch."""
        z0 = self.z
        self.floor(z0, z0 - depth - 2.0)
        mid = z0 - 1.0 - depth / 2
        if decor:
            decor(self, z0 - 1.0, z0 - 1.0 - depth)
        parts = [{"at": v3(0.0, -0.55, mid), "size": v3(2 * HALF, 0.7, depth), "look": "spikes", "face": "up",
                  "lethal": True, "move": v3(0.0, 1.0, 0.0)}]
        self.trap(tid, name, mid, parts, {"delay": 0.15, "out": 0.15, "hold": 1.0, "back": 1.0}, v3(0.0, 0.0, mid))
        self.z -= depth + 2.0
        self.point(0.0, self.z + 1.0)

    def falling(self, tid, name, depth=4.0, count=3):
        """Spikes dropped from above, all at once, faster than a person can see them start."""
        z0 = self.z
        self.floor(z0, z0 - depth - 2.0)
        mid = z0 - 1.0 - depth / 2
        self.box(0.0, WALL_TOP + 0.3, mid, 2 * HALF + 2 * WALL, 0.6, depth + 0.4, "pillar")
        width = 2 * HALF / count
        parts = []
        for i in range(count):
            x = -HALF + width * (i + 0.5)
            parts.append({"at": v3(x, 3.5, mid), "size": v3(width - 0.1, 0.6, depth), "look": "spikes",
                          "face": "down", "lethal": True, "move": v3(0.0, -3.5, 0.0), "tint": [0.85, 0.95, 1.0]})
        self.trap(tid, name, mid, parts, {"out": 0.22, "hold": 0.5, "back": 2.0}, v3(0.0, 0.0, mid))
        self.z -= depth + 2.0
        self.point(0.0, self.z + 1.0)

    def fire(self, tid, name, depth=4.0, half=None, tint=None):
        """A sheet of fire, the whole width or one `half` ("left"/"right") of it."""
        z0 = self.z
        self.floor(z0, z0 - depth - 2.0)
        mid = z0 - 1.0 - depth / 2
        x0, x1 = -HALF, HALF
        if half == "left":
            x1 = 0.0
        elif half == "right":
            x0 = 0.0
        part = {"at": v3((x0 + x1) / 2, 1.0, mid), "size": v3(x1 - x0, 2.0, depth), "look": "fire", "lethal": True}
        if tint:
            part["tint"] = tint
        victim = v3((x0 + x1) / 2, 0.0, mid)
        self.trap(tid, name, mid, [part], {"out": 0.05, "hold": 1.6, "back": 0.05}, victim)
        self.z -= depth + 2.0
        self.point(0.0 if half is None else (-1.6 if half == "right" else 1.6), self.z + 1.0)

    def blades(self, tid, name, depth=3.0):
        """Spinning blades lowered to knee height across the whole corridor."""
        z0 = self.z
        self.floor(z0, z0 - depth - 2.0)
        mid = z0 - 1.0 - depth / 2
        self.box(0.0, WALL_TOP + 0.3, mid, 2 * HALF + 2 * WALL, 0.6, depth + 0.4, "pillar")
        parts = []
        for x in (-2.2, 0.0, 2.2):
            parts.append({"at": v3(x, 5.2, mid), "size": v3(2.3, 0.15, 2.3), "look": "blade", "lethal": True,
                          "move": v3(0.0, -4.3, 0.0), "spin": 900.0 if x != 0.0 else -900.0})
        self.trap(tid, name, mid, parts, {"out": 0.35, "hold": 1.4, "back": 1.0}, v3(0.0, 0.0, mid))
        self.z -= depth + 2.0
        self.point(0.0, self.z + 1.0)

    def blocks(self, tid, name, count=4, look="spikes", tint=None, size=1.8, step=3.0):
        """Blocks over a pit, a jump apart and side to side; the trap drops all of them."""
        z0 = self.z
        length = step * count + 1.5
        if look == "liquid":
            self.kill(z0, z0 - length, "liquid", y=POOL_TOP - 1.0, height=2.0, tint=tint)
        else:
            self.kill(z0, z0 - length, look, tint=tint)
        parts = []
        for i in range(count):
            z = z0 - 1.0 - size / 2 - step * i
            x = -1.0 if i % 2 == 0 else 1.0
            parts.append({"at": v3(x, -0.25, z), "size": v3(size, 0.5, size), "move": v3(0.0, -10.0, 0.0)})
            self.point(x, z, jump=True, reach=0.6)
        victim = parts[1]["at"]
        self.trap(tid, name, z0 - length / 2, parts, {"out": 0.6, "hold": 2.5, "back": 1.5},
                  v3(victim[0], 0.0, victim[2]))
        self.z -= length
        self.floor(self.z, self.z - 2.0)
        self.point(0.0, self.z - 1.2, jump=True)
        self.z -= 2.0

    def floes(self, tid, name, count=4, tint=None):
        """Slabs of ice in a pool: they sink when the button goes, and so does whoever is on one."""
        z0 = self.z
        step = 3.2
        length = step * count + 1.2
        self.kill(z0, z0 - length, "liquid", y=POOL_TOP - 1.0, height=2.0, tint=tint)
        parts = []
        for i in range(count):
            z = z0 - 0.6 - 1.1 - step * i
            x = -0.9 if i % 2 == 0 else 0.9
            parts.append({"at": v3(x, -0.3, z), "size": v3(2.2, 0.6, 2.2),
                          "move": v3(0.0, -2.2, 0.0), "tint": SNOW})
            self.point(x, z, jump=True, reach=0.6)
        victim = parts[0]["at"]
        self.trap(tid, name, z0 - length / 2, parts, {"out": 0.8, "hold": 3.0, "back": 1.5},
                  v3(victim[0], 0.0, victim[2]))
        self.z -= length
        self.floor(self.z, self.z - 2.0)
        self.point(0.0, self.z - 1.2, jump=True)
        self.z -= 2.0

    def roll(self, tid, name, length=8.0, width=1.6, look="spikes", tint=None):
        """A narrow bridge over a pit that rolls over when the button goes."""
        z0, z1 = self.z, self.z - length
        mid = (z0 + z1) / 2
        if look == "liquid":
            self.kill(z0, z1, "liquid", y=-3.0, height=2.0, tint=tint)
        else:
            self.kill(z0, z1, look, tint=tint)
        parts = [{"at": v3(0.0, -0.3, mid), "size": v3(width, 0.6, length),
                  "turn": {"axis": "z", "degrees": 180.0, "pivot": v3(0.0, -0.3, mid)}}]
        self.trap(tid, name, mid, parts, {"out": 0.9, "hold": 2.0, "back": 1.2}, v3(0.0, 0.0, mid))
        self.point(0.0, mid)
        self.z = z1
        self.point(0.0, z1 - 0.5)


# --- Decoration ------------------------------------------------------------------

def snowmen(course, z0, z1):
    """Snowmen down both sides: a ball on a ball, and in the way of anybody hugging a wall."""
    z = z0 - 0.8
    side = -1
    while z > z1 + 0.6:
        x = side * 2.2
        course.pieces.append({"kind": "ball", "at": v3(x, 0.55, z), "radius": 0.6, "tint": SNOW})
        course.pieces.append({"kind": "ball", "at": v3(x, 1.4, z), "radius": 0.4, "tint": SNOW})
        side = -side
        z -= 1.6


def ice_arena(course, z0):
    """A square of ice with snow blocks to hide behind, like the end room of the old ice maps."""
    size = 24.0
    mid = z0 - size / 2
    course.box(0.0, -0.5, mid, size, 1.0, size)
    for x, z, sx, sz in ((-size / 2 - 0.25, mid, 0.5, size), (size / 2 + 0.25, mid, 0.5, size),
                         (0.0, z0 + 0.25, size + 1.0, 0.5), (0.0, z0 - size - 0.25, size + 1.0, 0.5)):
        course.box(x, 2.5, z, sx, 5.0, sz, "pillar")
    for x, z in ((-6, -7), (6, -7), (0, -12), (-6, -17), (6, -17), (-2.5, -9.5), (2.5, -14.5)):
        course.box(x, 0.75, z0 + z, 2.2, 1.5, 2.2, tint=SNOW)
    course.doc["end"] = {
        "runners": {"at": v3(0.0, 0.0, z0 - 2.5), "size": v3(10.0, 3.0, 3.0), "yaw": 0.0},
        "activators": {"at": v3(0.0, 0.0, z0 - size + 2.5), "size": v3(10.0, 3.0, 3.0), "yaw": 180.0},
    }


def foundry_arena(course, z0):
    """A furnace floor: crates of slag to hide behind and a channel of lava down the middle."""
    size = 24.0
    mid = z0 - size / 2
    course.box(-7.0, -0.5, mid, 10.0, 1.0, size)
    course.box(7.0, -0.5, mid, 10.0, 1.0, size)
    # The channel, with two bridges over it.
    course.pieces.append({"kind": "kill", "at": v3(0.0, -2.5, mid), "size": v3(4.0, 2.0, size),
                          "look": "liquid", "tint": [1.0, 0.35, 0.05]})
    for z in (-6.0, -18.0):
        course.box(0.0, -0.5, z0 + z, 4.0, 1.0, 3.0, "deck")
    for x, z, sx, sz in ((-size / 2 - 0.25, mid, 0.5, size), (size / 2 + 0.25, mid, 0.5, size),
                         (0.0, z0 + 0.25, size + 1.0, 0.5), (0.0, z0 - size - 0.25, size + 1.0, 0.5)):
        course.box(x, 2.5, z, sx, 5.0, sz, "pillar")
    for x, z in ((-6, -9), (6, -9), (-6, -15), (6, -15), (-9.5, -12), (9.5, -12)):
        course.box(x, 0.9, z0 + z, 1.8, 1.8, 1.8, "pillar")
    course.doc["end"] = {
        "runners": {"at": v3(-7.0, 0.0, z0 - 2.5), "size": v3(8.0, 3.0, 3.0), "yaw": 0.0},
        "activators": {"at": v3(7.0, 0.0, z0 - size + 2.5), "size": v3(8.0, 3.0, 3.0), "yaw": 180.0},
    }


# --- The courses -----------------------------------------------------------------

def ice_works():
    c = Course(
        "dr_ice_works", "Ice Works",
        "A long corridor of ice: walls that close, a bridge that rolls, floes that sink and a mouth full of teeth.",
        {"sky": [0.62, 0.74, 0.88], "horizon": [0.86, 0.91, 0.96], "void": [0.18, 0.24, 0.32],
         "deck": [0.52, 0.64, 0.80], "fog": 0.006},
    )
    c.run(8.0)
    c.spike_walls("ice_walls", "Closing walls", sides="both")
    c.run(3.0)
    c.trapdoor("ice_trapdoor", "Trapdoor")
    c.run(3.0)
    c.roll("ice_log", "Rolling log")
    c.run(3.0)
    c.floes("ice_floes", "Sinking floes", tint=[0.35, 0.65, 0.9])
    c.floor_spikes("ice_snowmen", "Snowman spikes", depth=5.0, decor=snowmen)
    c.run(2.0)
    c.jaws("ice_jaws", "The jaws")
    c.run(2.0)
    c.falling("ice_icicles", "Icicles")
    c.run(2.0)
    c.blocks("ice_blocks", "Falling blocks", count=4)
    c.spike_walls("ice_last_wall", "Last wall", sides="right")
    c.finish(ice_arena)
    return c


def foundry():
    lava = [1.0, 0.35, 0.05]
    c = Course(
        "dr_foundry", "The Foundry",
        "Fire, saws and a press, over a floor of lava that the activator can open.",
        {"sky": [0.46, 0.32, 0.28], "horizon": [0.86, 0.62, 0.42], "void": [0.35, 0.10, 0.02],
         "deck": [0.80, 0.70, 0.62], "sun": [1.0, 0.86, 0.70], "fog": 0.008},
    )
    c.run(8.0)
    c.fire("fd_jets", "Fire jets")
    c.run(2.0)
    c.blades("fd_saws", "Saws")
    c.run(3.0)
    c.trapdoor("fd_lava_door", "Lava door", look="liquid", tint=lava)
    c.run(3.0)
    c.fire("fd_left", "Left burner", half="left")
    c.fire("fd_right", "Right burner", half="right")
    c.run(2.0)
    c.crusher("fd_press", "The press", depth=4.0, out=0.3)
    c.run(3.0)
    c.roll("fd_bridge", "Tipping bridge", look="liquid", tint=lava)
    c.run(3.0)
    c.blocks("fd_steps", "Slag steps", count=3, look="liquid", tint=lava)
    c.floor_spikes("fd_grate", "The grate", depth=4.0)
    c.run(2.0)
    c.spike_walls("fd_walls", "Closing walls", sides="both")
    c.finish(foundry_arena)
    return c


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "courses")
    check = "--check" in sys.argv
    stale = []

    for build in (ice_works, foundry):
        path, text = build().write(root)

        if check:
            with open(path) as handle:
                if handle.read() != text:
                    stale.append(path)
            continue

        with open(path, "w") as handle:
            handle.write(text)
        print("wrote", os.path.relpath(path))

    if stale:
        print("not what tools/build_courses.py writes:", ", ".join(stale))
        sys.exit(1)


if __name__ == "__main__":
    main()
