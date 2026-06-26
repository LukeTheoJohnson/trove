"""nzski - live NZ ski-field snow reports via NZSki's own page-called JSON feed.

NZSki runs Coronet Peak, The Remarkables and Mt Hutt. Each resort's weather/snow-report page
(e.g. coronetpeak.co.nz/weather-report) is a Webflow site whose Alpine.js widget
(`weather-app.iife.js`) fetches a per-resort JSON the page itself calls:
`https://webcams-<...>.azurefd.net/<mountain-slug>-data.json`, where the slug is read from the page
`<body>` class. Page-called + keyless + robots-clean (nzski.com fences only /bin/ and
/aspnet_client/) = sanctioned -> trove.

Why it's a good hoard: a snow report is pure ephemeral state - base depth, which lifts/trails are
spinning, road/chain status, the mountain open/closed flag - overwritten through the day and gone once
the season ends. Polling captures the fill of the season (base building, then melting out) and the
daily open/closed churn that nobody archives.

Model: one Item per resort (join key = the data slug, e.g. `coronet-peak-winter`). `price_cents` =
headline base depth in cm * 100 (so `drops` = the base *melting* since first seen); `qty` = number of
lifts currently open. A "deal" (`open`) = the mountain is Open (lifts spinning, you can ski today).
`search` lists the resorts (filter by name); `item`/`poll` fetch one by slug or a friendly alias.
`--cc` is unused.
"""
from __future__ import annotations

import json

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source

UA = "Mozilla/5.0 (trove/0.1; +github.com/LukeTheoJohnson/trove)"
BASE = "https://webcams-awb2e0ceg7cccsba.a02.azurefd.net"

# alias -> (display, data-slug). The slug is what the resort page's <body> class resolves to.
RESORTS = {
    "coronet":      ("Coronet Peak",   "coronet-peak-winter"),
    "coronetpeak":  ("Coronet Peak",   "coronet-peak-winter"),
    "remarkables":  ("The Remarkables", "the-remarkables"),
    "theremarkables": ("The Remarkables", "the-remarkables"),
    "hutt":         ("Mt Hutt",        "mt-hutt"),
    "mthutt":       ("Mt Hutt",        "mt-hutt"),
}
SLUG_NAMES = {slug: name for name, slug in RESORTS.values()}


def _safe(s):
    return (str(s) if s is not None else "").strip().encode("cp1252", "replace").decode("cp1252")


def _i(x):
    return int(x) if isinstance(x, (int, float)) else None


def _resolve(token):
    """A friendly alias or a raw data-slug -> (display_name, slug), or None."""
    t = (token or "").strip()
    tl = t.lower().replace(" ", "").replace("_", "").replace("-", "")
    for alias, (name, slug) in RESORTS.items():
        if tl == alias:
            return name, slug
    if t in SLUG_NAMES:                       # raw slug
        return SLUG_NAMES[t], t
    return None


def _count(rows, status="Open"):
    return sum(1 for r in (rows or []) if str(r.get("status", "")).strip().lower() == status.lower())


def _report(payload, slug, name):
    """One resort -data.json -> (Item, Obs)."""
    name = _safe(payload.get("name") or name)
    snow = payload.get("snow") or {}
    base = snow.get("base") or {}
    base_cm = max([v for v in (_i(base.get("min")), _i(base.get("max"))) if v is not None] or [None]) \
        if (base.get("min") is not None or base.get("max") is not None) else None
    temp = payload.get("temperature") or {}
    lifts, trails = payload.get("lifts") or [], payload.get("trails") or []
    lifts_open, trails_open = _count(lifts), _count(trails)
    status = _safe(payload.get("MountainStatus", ""))
    updated = payload.get("updatedAt", "")
    item = Item(slug, name=name,
                subtitle=f"{status or '?'}  base {base_cm if base_cm is not None else '?'}cm  "
                         f"{lifts_open}/{len(lifts)} lifts",
                category=_safe(payload.get("weatherIcon", "")),
                extra={"slug": slug, "updated": updated,
                       "road_status": _safe(payload.get("RoadStatus", "")),
                       "chain_status": _safe(payload.get("ChainStatus", "")),
                       "weather": _safe(payload.get("weather", ""))[:160],
                       "url": f"https://www.{'coronetpeak' if 'coronet' in slug else ('mthutt' if 'hutt' in slug else 'theremarkables')}.co.nz/weather-report"})
    obs = Obs(price_cents=(base_cm * 100 if base_cm is not None else None),
              qty=lifts_open,
              flags={"base_cm": base_cm, "base_min": _i(base.get("min")), "base_max": _i(base.get("max")),
                     "season_total": _i(snow.get("seasonTotal")), "last7days": _i(snow.get("last7Days")),
                     "lifts_open": lifts_open, "lifts_total": len(lifts),
                     "trails_open": trails_open, "trails_total": len(trails),
                     "status": status, "temp_high": _i(temp.get("high")), "temp_low": _i(temp.get("low")),
                     "updated": updated})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._cache = {}

    def get(self, slug):
        if slug not in self._cache:
            r = self.s.get(f"{BASE}/{slug}-data.json", headers={"User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._cache[slug] = json.loads(r.content.decode("utf-8-sig"))   # feed carries a UTF-8 BOM
        return self._cache[slug]


class NZSkiSource(Source):
    name = "nzski"
    id_label = "RESORT"
    cc_default = "nz"           # unused
    deal_label = "open"         # open = the mountain is Open (lifts spinning)
    search_limit_default = 10
    search_header = f"{'BASE':>6}  {'LIFTS':>6}  {'STATUS':<8}  RESORT"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        d = cl.get("coronet-peak-winter")
        return bool(d.get("name")), f"(Coronet Peak report loaded, updated {d.get('updatedAt', '?')}; keyless NZSki feed)"

    def search(self, cl, term, args):
        t = (term or "").strip().lower()
        seen, rows = set(), []
        for alias, (name, slug) in RESORTS.items():
            if slug in seen:
                continue
            if t and t not in name.lower() and t not in slug:
                continue
            seen.add(slug)
            try:
                rows.append(_report(cl.get(slug), slug, name))
            except Exception:
                pass
        return rows

    def fetch(self, cl, item_id):
        res = _resolve(item_id)
        if not res:
            return None
        name, slug = res
        return _report(cl.get(slug), slug, name)

    def is_deal(self, obs):
        return str(obs.flags.get("status", "")).strip().lower() == "open"

    def deal_line(self, item, obs):
        f = obs.flags
        return (f"OPEN  {item.name}  base {f.get('base_cm', '?')}cm  "
                f"{f.get('lifts_open', '?')}/{f.get('lifts_total', '?')} lifts  "
                f"{f.get('trails_open', '?')}/{f.get('trails_total', '?')} trails")

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        base = f"{f.get('base_cm')}cm" if f.get("base_cm") is not None else "?"
        lifts = f"{f.get('lifts_open', '?')}/{f.get('lifts_total', '?')}"
        return f"{base:>6}  {lifts:>6}  {(f.get('status') or '?'):<8}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = []
        if obs:
            f = obs.flags
            lines.append(f"  status   : {f.get('status', '?')}")
            lines.append(f"  base     : {f.get('base_cm', '?')} cm  (min {f.get('base_min', '?')} / max {f.get('base_max', '?')})")
            lines.append(f"  fresh    : {f.get('last7days', '?')} cm last 7 days   season total {f.get('season_total', '?')} cm")
            lines.append(f"  lifts    : {f.get('lifts_open', '?')} / {f.get('lifts_total', '?')} open")
            lines.append(f"  trails   : {f.get('trails_open', '?')} / {f.get('trails_total', '?')} open")
            lines.append(f"  temp     : {f.get('temp_low', '?')} to {f.get('temp_high', '?')} C")
        lines.append(f"  road     : {e.get('road_status', '?')}   chains: {e.get('chain_status', '?')}")
        lines.append(f"  weather  : {e.get('weather', '')}")
        lines.append(f"  updated  : {e.get('updated', '')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = NZSkiSource()
