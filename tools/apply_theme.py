#!/usr/bin/env python3
"""Writes a converted map's look into its spec: tools/apply_theme.py <spec id> (themes below).

The look is the theme (sky, horizon, void, sun, deck) and `surface`, a texture set the game's
pack carries (mg-deathrun textures/surfaces, CC0 from ambientCG). Layout is the author's; the
look is ours. Re-run bsp_to_course.py afterwards.
"""
import json, os, sys

THEMES = {
    "dr_oreo": dict(sky=[0.62, 0.6, 0.78], horizon=[0.92, 0.86, 0.84], void=[0.12, 0.08, 0.08],
                    sun=[1.0, 0.9, 0.78], deck=[1.0, 0.92, 0.82], surface="tiles"),
    "dr_parking_garage": dict(sky=[0.34, 0.37, 0.46], horizon=[0.58, 0.58, 0.6], void=[0.06, 0.06, 0.08],
                              sun=[1.0, 0.86, 0.6], deck=[0.9, 0.9, 0.92], surface="concrete"),
    "dr_iceworld": dict(sky=[0.55, 0.74, 0.95], horizon=[0.86, 0.93, 1.0], void=[0.06, 0.12, 0.2],
                        sun=[0.88, 0.95, 1.0], deck=[0.92, 0.98, 1.0], surface="snow"),
    "dr_fogtown": dict(sky=[0.42, 0.45, 0.48], horizon=[0.66, 0.66, 0.64], void=[0.07, 0.07, 0.07],
                       sun=[0.82, 0.8, 0.72], deck=[0.8, 0.82, 0.8], surface="asphalt"),
    "dr_southpark": dict(sky=[0.5, 0.7, 0.94], horizon=[0.88, 0.93, 0.98], void=[0.1, 0.14, 0.2],
                         sun=[1.0, 0.97, 0.9], deck=[0.96, 0.98, 1.0], surface="town"),
    "dr_horror": dict(sky=[0.2, 0.17, 0.26], horizon=[0.34, 0.28, 0.32], void=[0.04, 0.03, 0.05],
                      sun=[0.95, 0.72, 0.56], deck=[0.62, 0.56, 0.58], surface="manor"),
    "dr_aztecan": dict(sky=[0.55, 0.72, 0.9], horizon=[0.95, 0.88, 0.74], void=[0.14, 0.1, 0.06],
                       sun=[1.0, 0.92, 0.74], deck=[0.95, 0.88, 0.76], surface="sand"),
}

if __name__ == "__main__":
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imports")
    for cid in sys.argv[1:] or THEMES:
        path = os.path.join(here, cid + ".json")
        spec = json.load(open(path))
        spec["theme"] = {**spec.get("theme", {}), **THEMES[cid]}
        json.dump(spec, open(path, "w"), indent=1)
        open(path, "a").write("\n")
        print("themed", cid)
