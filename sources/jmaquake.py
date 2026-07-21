"""jmaquake - Japanese earthquakes (hypocentre + seismic intensity) via JMA's keyless feed.

The Japan Meteorological Agency publishes its earthquake reports as keyless JSON at
`www.jma.go.jp/bosai/quake/data/list.json`: a list of recent bulletins, each with the origin time,
epicentre name, magnitude, coordinates (packed `cod`) and the JMA maximum seismic intensity (`maxi`,
the shindo scale 1..7 incl. 5-/5+/6-/6+). robots.txt is 404 (unfenced) and it is official open data =
sanctioned -> trove. Opens **Japan** on the seismic side (twinning `geonet`/`usgsquakes`/`eqcanada`/
`bmkg`) and carries the distinctive JMA intensity scale, which measures *shaking* felt at the surface
rather than energy released.

Honest hoard value is low (JMA keeps the catalogue); the ephemeral part is the as-reported magnitude
and intensity of a fresh event. `price_cents` = magnitude * 100 (centi-magnitude, the geonet scalar) so
the core's `drops` = an event *downgraded* on review; `qty` = None. A "deal" ("strong") = magnitude
>= 4.5 or a JMA intensity of 5- or above (strong shaking). Epicentre names are Japanese and fold to
'?' on the cp1252 console (safe()), so the item name leads with magnitude + intensity.

Model: one Item per bulletin that carries a magnitude (join key = the JMA event id `eid`; pure
intensity-only speed reports are skipped). One memoized GET serves search/fetch. `--cc` is unused.
"""
from __future__ import annotations

import re

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://www.jma.go.jp/bosai/quake/data/list.json"
STRONG_MAG = 4.5
STRONG_INT = {"5-", "5+", "6-", "6+", "7"}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _coords(cod):
    """cod like '+43.4+146.2-80000/' -> (lat, lon, depth_km)."""
    parts = re.findall(r"[+-]\d+(?:\.\d+)?", str(cod or ""))
    lat = _f(parts[0]) if len(parts) > 0 else None
    lon = _f(parts[1]) if len(parts) > 1 else None
    depth_km = abs(_f(parts[2]) / 1000) if len(parts) > 2 and _f(parts[2]) is not None else None
    return lat, lon, depth_km


def _build(q):
    mag = _f(q.get("mag"))
    maxi = str(q.get("maxi") or "").strip()
    lat, lon, depth = _coords(q.get("cod"))
    epi = safe(q.get("anm") or "")
    name = f"M{q.get('mag')} intensity {maxi or '?'}" + (f"  {epi}" if epi and epi != "?" * len(epi) else "")
    item = Item(str(q.get("eid")), name=name.strip(), subtitle=safe(q.get("anm") or ""),
                category="quake", extra={"lat": lat, "lon": lon, "depth_km": depth, "epicentre": epi})
    obs = Obs(price_cents=(round(mag * 100) if mag is not None else None), qty=None,
              flags={"mag": mag, "max_intensity": maxi, "time": (q.get("at") or "").replace("T", " ")[:19],
                     "epicentre": epi, "depth_km": depth})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = None

    def feed(self):
        if self._feed is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            # keep bulletins that carry a magnitude (skip pure intensity speed-reports)
            self._feed = [q for q in (r.json() or []) if _f(q.get("mag")) is not None and q.get("eid")]
        return self._feed


class JmaQuakeSource(Source):
    name = "jmaquake"
    id_label = "EVENTID"
    cc_default = "jp"        # unused
    deal_label = "strong"    # magnitude >= 4.5 or JMA intensity 5- and above
    search_limit_default = 30
    search_header = f"{'MAG':>5}  {'INT':>4}  {'WHEN':<19}  EPICENTRE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        fs = cl.feed()
        return bool(fs), f"({len(fs)} recent JP quake bulletins; keyless JMA quake list)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        seen, out = set(), []
        for q in cl.feed():
            if q.get("eid") in seen:
                continue
            seen.add(q.get("eid"))
            item, obs = _build(q)
            if not t or t in safe(obs.flags.get("epicentre") or "").lower() or t in str(obs.flags.get("max_intensity")):
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        for q in cl.feed():
            if str(q.get("eid")) == str(item_id):
                return _build(q)
        return None

    def is_deal(self, obs):
        m = obs.flags.get("mag")
        return (isinstance(m, (int, float)) and m >= STRONG_MAG) or (obs.flags.get("max_intensity") in STRONG_INT)

    def deal_line(self, item, obs):
        f = obs.flags
        return f"M{f.get('mag')} JMA intensity {f.get('max_intensity') or '?'}  ({f.get('time') or '?'})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        m = f.get("mag")
        return (f"{(m if m is not None else '?'):>5}  {str(f.get('max_intensity') or '?'):>4}  "
                f"{(f.get('time') or '')[:19]:<19}  {safe(f.get('epicentre') or '?')}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  event    : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  magnitude: M{f.get('mag')}   JMA max intensity {f.get('max_intensity') or '?'}")
            lines.append(f"  time     : {f.get('time') or '?'}   depth {e.get('depth_km')} km")
            lines.append(f"  epicentre: {f.get('epicentre') or '?'}")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        return lines


SOURCE = JmaQuakeSource()
