#!/usr/bin/env python3
"""trove - personal price/listing intelligence over many sources, one shared core.

    python trove.py <source> <command> [args]

Examples:
    python trove.py steam search "elden ring"
    python trove.py discogs release 249504        # 'item' alias per source below
    python trove.py itunes watch add 1713845538
    python trove.py steam poll

Run `python trove.py` to list sources, or `python trove.py <source> -h` for its commands.
Each source keeps its own history in data/<source>.db.
"""
from __future__ import annotations

import importlib
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")

# Sources grouped by genre. This grouping is the single source of truth: it drives
# the `--help` listing, and the flat SOURCES tuple (membership + dispatch) is derived
# from it. Adding a source = drop its name into the right group below.
SOURCE_GROUPS = {
    "games / media / collectibles":     ("steam", "discogs", "itunes", "scryfall", "pokemontcg", "ygoprodeck", "epic", "steammarket"),
    "fuel & electricity":               ("spainfuel", "petrolspy", "em6", "octopus", "aemo", "fuelwatch", "awattar", "carbonintensity"),
    "currency & macro":                 ("frankfurter",),
    "deals, fares & listings":          ("grabone", "grabaseat", "bookme", "turners", "eventcinemas", "reverb"),
    "attention & rank":                 ("hackernews", "appcharts", "melbped"),
    "weather, environment & geohazard": ("geonet", "metno", "volcano", "nzski", "gwrivers", "avalanche", "mdcrivers", "nswrfs", "beachwatch", "vicemergency", "horizonsrivers", "northlandrivers", "westcoastrivers", "sacfs", "safeswim", "eafloods", "usgs", "wildfire", "airquality"),
    "space":                            ("spaceweather", "sentry", "spacelaunch"),
    "aviation":                         ("chcflights", "zqnflights", "opensky"),
    "roads & transport":                ("nzroads", "tfl", "mbta", "swisstransport"),
    "shared mobility":                  ("bikeshare", "sgtaxi"),
    "parking":                          ("chcparking", "sgcarpark"),
    "utilities & outages":              ("outages",),
    "marine & coastal":                 ("noaatides", "ndbc"),
}
SOURCES = tuple(name for group in SOURCE_GROUPS.values() for name in group)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("sources:")
        w = max(len(label) for label in SOURCE_GROUPS)
        for label, names in SOURCE_GROUPS.items():
            print(f"  {label:<{w}}  {', '.join(names)}")
        return 0
    name = argv[0]
    if name not in SOURCES:
        print(f"unknown source '{name}'. available: {', '.join(SOURCES)}", file=sys.stderr)
        return 2
    sys.path.insert(0, ROOT)
    mod = importlib.import_module(f"sources.{name}")
    from trove.tracker import run_cli
    return run_cli(mod.SOURCE, argv[1:], DATA_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
