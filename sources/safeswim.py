"""safeswim - NZ beach water-quality + safety traffic-lights (Safeswim), keyless JSON.

Safeswim (safeswim.org.nz, run by Auckland Council + partner councils) publishes live swimming
water-quality and safety information for ~300 NZ beaches. Its map app calls a keyless, same-origin
JSON endpoint, `GET safeswim.org.nz/api/locations`, returning every beach with a current water-quality
traffic-light (`state.quality`: GREEN = suitable, RED = water-quality alert, etc.). The site has no
real robots.txt (the Next.js app 404s it), the endpoint is the one the page itself calls, keyless =
sanctioned -> trove. The NZ twin of `beachwatch` (NSW), completing the beach-water genre across the
Tasman.

The timeline value is ephemeral: each beach's water-quality status changes with rainfall and
stormwater overflows (a green beach flips red after heavy rain, then recovers) and is not archived in
a queryable per-beach series. `price_cents` = a safety ordinal * 100 (GREEN=300 .. RED=100 .. BLACK=0,
so the core's `drops` = water quality *worsening*); a "deal" ("alert") = the beach carries a
water-quality alert (RED / BLACK / long-term), i.e. don't-swim. money() renders the centi-ordinal as
dollars in the two core-hardcoded spots; the rich views show the colour word.

Model: one Item per beach (join key = the Safeswim `slug`). `search <term>` filters beaches by name
substring (pass "" to list them all); `fetch` scans the memoized list by slug. One GET returns every
beach, memoized. `--cc` is unused.
"""
from __future__ import annotations

import ast

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

FEED = "https://safeswim.org.nz/api/locations"
# water-quality colour -> safety ordinal (higher = safer, so core `drops` = worsening).
# Safeswim's live values: GREEN (suitable), RED (current alert), RED+ (long-term alert),
# BLACK (permanent alert / very poor); None = no current grading.
QUALITY_ORD = {"GREEN": 3, "AMBER": 2, "RED": 2, "RED+": 1, "BLACK": 0}
ALERT = {"RED", "RED+", "BLACK", "AMBER"}   # a water-quality alert = don't-swim


def _coerce(v):
    """A field that may arrive as a native dict/list or as its str repr -> the native value."""
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        try:
            return ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return v
    return v


def _quality(loc):
    st = _coerce(loc.get("state"))
    return (st.get("quality") if isinstance(st, dict) else None) or None


def _pos(loc):
    p = _coerce(loc.get("position"))
    if isinstance(p, (list, tuple)) and len(p) == 2:
        return p[0], p[1]
    return None, None


def _build(loc):
    slug = str(loc.get("slug", ""))
    q = (_quality(loc) or "").upper()
    ordv = QUALITY_ORD.get(q)
    lat, lon = _pos(loc)
    item = Item(slug, name=safe(loc.get("name", "")),
                subtitle="NZ Safeswim beach", category="beach",
                extra={"slug": slug, "patrolled": loc.get("patrolled"),
                       "alt_name": safe(loc.get("alternative_name", "")), "lat": lat, "lon": lon,
                       "url": f"https://safeswim.org.nz/beach/{slug}"})
    obs = Obs(price_cents=(ordv * 100 if ordv is not None else None),
              flags={"quality": q or None, "patrolled": loc.get("patrolled")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._locs = None

    def locations(self):
        if self._locs is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            d = r.json()
            self._locs = d if isinstance(d, list) else (d.get("locations") or d.get("data") or [])
        return self._locs


class SafeswimSource(Source):
    name = "safeswim"
    id_label = "BEACH"
    cc_default = "nz"        # unused; one NZ set
    deal_label = "alert"     # a water-quality alert (don't-swim)
    search_limit_default = 30
    search_header = f"{'QUALITY':>8}  {'PATROL':<7}  BEACH"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        locs = cl.locations()
        return bool(locs), f"({len(locs)} NZ beaches; keyless Safeswim locations API)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for loc in cl.locations():
            item, obs = _build(loc)
            if not t or t in item.name.lower():
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 99, io[0].name.lower()))
        return out

    def fetch(self, cl, item_id):
        for loc in cl.locations():
            if str(loc.get("slug")) == str(item_id):
                return _build(loc)
        return None

    def is_deal(self, obs):
        return (obs.flags.get("quality") or "") in ALERT

    def deal_line(self, item, obs):
        return f"water quality {obs.flags.get('quality')}  {item.name}  (avoid swimming)"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        patrol = "yes" if str(f.get("patrolled")).lower() in ("true", "1") else "no"
        return f"{(f.get('quality') or '-'):>8}  {patrol:<7}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  beach    : {item.name}",
                 f"  location : {e.get('lat', '?')}, {e.get('lon', '?')}",
                 f"  patrolled: {e.get('patrolled')}"]
        if obs:
            lines.append(f"  quality  : {obs.flags.get('quality') or '?'}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = SafeswimSource()
