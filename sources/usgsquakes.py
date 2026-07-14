"""usgsquakes - global earthquakes via the USGS FDSN event API, keyless official feed.

The USGS publishes every located earthquake worldwide through the keyless FDSN event web service
`earthquake.usgs.gov/fdsnws/event/1/query?format=geojson` (robots.txt 404 = unfenced; an official
open-data service = sanctioned -> trove). One GeoJSON query returns recent events with magnitude,
place, origin time, depth, felt reports, shaking intensity (MMI/CDI), PAGER alert level and a tsunami
flag. The global complement to `geonet` (NZ-only): same quake-magnitude shape, worldwide coverage.

Honest hoard value is **low** (the octopus/frankfurter class): USGS keeps the full authoritative
catalogue and revises events, so the series is rebuildable from the same API - this is a breadth /
data-science source, not an un-rebuildable moat. What is mildly ephemeral is the *as-reported* state:
a fresh event's magnitude and felt count get revised in the hours after it happens, and capturing the
first-reported value vs the final is the small hoard here. `price_cents` = magnitude * 100
(centi-magnitude, the geonet scalar) so the core's `drops` = an event *downgraded* on review; `qty` =
the USGS "significance" score. A "deal" ("strong") = magnitude >= 4.5 or a tsunami flag.

Model: one Item per event (join key = the USGS event `id`, e.g. `us7000abcd`). One memoized query
serves a whole pass; `fetch` re-queries by `eventid` for the precise current state (a very old event
drops off the recent feed - fetch then returns None and the series ends). `--cc` is unused; `search
<term>` filters the recent feed by place substring (pass "" to list the recent set).
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://earthquake.usgs.gov/fdsnws/event/1/query"
FEED_MINMAG = 2.5     # recent feed floor (keeps the board meaningful, not every micro-quake)
FEED_LIMIT = 50
STRONG = 4.5          # deal threshold


def _epoch(ms):
    if not isinstance(ms, (int, float)):
        return ""
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def _build(feat):
    p = (feat or {}).get("properties") or {}
    g = (feat or {}).get("geometry") or {}
    coords = g.get("coordinates") or [None, None, None]
    mag = p.get("mag")
    item = Item(str(feat.get("id")), name=safe(p.get("place") or feat.get("id")),
                subtitle=f"M{mag} {p.get('magType') or ''}".strip(), category="quake",
                extra={"lon": coords[0], "lat": coords[1], "depth_km": coords[2],
                       "url": p.get("url") or "", "magType": p.get("magType") or ""})
    obs = Obs(price_cents=(round(mag * 100) if isinstance(mag, (int, float)) else None),
              qty=(p.get("sig") if isinstance(p.get("sig"), int) else None),
              flags={"mag": mag, "place": safe(p.get("place") or ""), "time": _epoch(p.get("time")),
                     "updated": _epoch(p.get("updated")), "mmi": p.get("mmi"), "cdi": p.get("cdi"),
                     "felt": p.get("felt"), "alert": p.get("alert"), "tsunami": p.get("tsunami"),
                     "sig": p.get("sig"), "depth_km": coords[2], "status": p.get("status")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = None

    def _query(self, params):
        r = self.s.get(BASE, params={"format": "geojson", **params},
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or {}

    def feed(self):
        if self._feed is None:
            d = self._query({"orderby": "time", "limit": FEED_LIMIT, "minmagnitude": FEED_MINMAG})
            self._feed = d.get("features") or []
        return self._feed

    def by_id(self, eventid):
        d = self._query({"eventid": eventid})
        if d.get("type") == "Feature":       # eventid query returns a bare Feature
            return d
        fs = d.get("features") or []
        return fs[0] if fs else None


class UsgsQuakesSource(Source):
    name = "usgsquakes"
    id_label = "EVENTID"
    cc_default = "world"      # unused
    deal_label = "strong"     # magnitude >= 4.5 or a tsunami flag
    search_limit_default = 30
    search_header = f"{'MAG':>5}  {'WHEN':<17}  PLACE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        fs = cl.feed()
        return bool(fs), f"({len(fs)} recent M>={FEED_MINMAG} events; keyless USGS FDSN event feed)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for feat in cl.feed():
            item, obs = _build(feat)
            if not t or t in safe(obs.flags.get("place") or "").lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        feat = cl.by_id(str(item_id))
        return _build(feat) if feat else None

    def is_deal(self, obs):
        m = obs.flags.get("mag")
        return (isinstance(m, (int, float)) and m >= STRONG) or bool(obs.flags.get("tsunami"))

    def deal_line(self, item, obs):
        f = obs.flags
        tsu = "  TSUNAMI" if f.get("tsunami") else ""
        return f"M{f.get('mag')} {item.name}  ({f.get('time') or '?'}){tsu}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        m = f.get("mag")
        return f"{(m if m is not None else '?'):>5}  {(f.get('time') or '')[:17]:<17}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  place    : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  magnitude: M{f.get('mag')}  ({e.get('magType') or '?'})   depth {e.get('depth_km')} km")
            lines.append(f"  time     : {f.get('time') or '?'}   (updated {f.get('updated') or '?'})")
            felt = f"  felt     : {f.get('felt') or 0} reports   MMI {f.get('mmi') or '?'}   sig {f.get('sig') or '?'}"
            lines.append(felt + (f"   ALERT {str(f['alert']).upper()}" if f.get("alert") else ""))
            if f.get("tsunami"):
                lines.append("  tsunami  : flagged")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = UsgsQuakesSource()
