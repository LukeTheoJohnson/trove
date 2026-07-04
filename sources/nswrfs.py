"""nswrfs - NSW Rural Fire Service live 'major incidents' feed (bush/grass fires), keyless GeoJSON.

The NSW RFS publishes its current major-incidents board - the same data behind "Fires Near Me" - as a
keyless GeoJSON feed at `rfs.nsw.gov.au/feeds/majorIncidents.json`. robots.txt fences only marketing
paths (/home, /404, /sitemap), never /feeds = sanctioned -> trove. A geohazard/emergency source,
AU-side, complementing the NZ geohazard set (geonet/volcano/avalanche).

The timeline value is a fire's **lifecycle as issued**: its alert level escalating (Advice -> Watch
and Act -> Emergency Warning) or easing, its size growing, its status changing (Being controlled ->
Under control -> Out), then the incident dropping off the feed once it's resolved. The feed serves
current state only and nobody archives the per-incident progression, so the snapshot is the record.
`price_cents` = the **alert-level ordinal * 100** (Emergency Warning=300, Watch and Act=200, Advice=100,
Planned Burn / N.A.=0), so the core's `drops` = a fire *de-escalating* (volcano/nzroads pattern);
`qty` = size in hectares; a "deal" ("bushfire") = an out-of-control fire at Watch and Act or above -
the newsworthy set. money() cosmetically renders the centi-ordinal as dollars in the two core spots.

Model: one Item per incident (join key = the numeric incident id parsed from the RFS `guid`). The
structured fields live in the RSS-style `description` (ALERT LEVEL / LOCATION / STATUS / TYPE / SIZE
/ RESPONSIBLE AGENCY / UPDATED), parsed out. `search <term>` filters the board by title/location/
council substring (pass "" to list all); `fetch` scans the memoized feed by id (an id gone = resolved
= series ends). `--cc` is unused - one NSW board.
"""
from __future__ import annotations

import re

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

FEED = "https://www.rfs.nsw.gov.au/feeds/majorIncidents.json"
LEVELS = {"emergency warning": 3, "watch and act": 2, "advice": 1}   # else 0 (planned burn / N.A.)
DEAL_MIN = 2   # Watch and Act or above


def _desc_fields(desc):
    """'ALERT LEVEL: x <br />LOCATION: y ...' -> {'alert level': 'x', 'location': 'y', ...}."""
    out = {}
    for part in re.split(r"<br\s*/?>", desc or ""):
        if ":" in part:
            k, _, v = part.partition(":")
            out[k.strip().lower()] = v.strip()
    return out


def _size_ha(f):
    m = re.search(r"([\d,.]+)\s*ha", f.get("size", ""))
    return round(float(m.group(1).replace(",", ""))) if m else None


def _first_point(geom):
    """A Point or GeometryCollection -> (lon, lat) of the first vertex, or (None, None)."""
    if not geom:
        return None, None
    if geom.get("type") == "Point":
        c = geom.get("coordinates") or [None, None]
        return c[0], c[1]
    for g in geom.get("geometries", []):
        if g.get("type") == "Point":
            c = g.get("coordinates") or [None, None]
            return c[0], c[1]
    return None, None


def _id(props):
    guid = props.get("guid") or ""
    m = re.search(r"(\d+)", guid.rsplit("/", 1)[-1])
    return m.group(1) if m else guid


def _build(feat):
    p = feat.get("properties") or {}
    f = _desc_fields(p.get("description", ""))
    level = f.get("alert level", "") or p.get("category", "")
    ordv = LEVELS.get(level.lower(), 0)
    lon, lat = _first_point(feat.get("geometry"))
    iid = _id(p)
    item = Item(iid, name=safe(p.get("title", "")),
                subtitle=safe(f.get("location", "")), category=safe(p.get("category", "")),
                extra={"location": safe(f.get("location", "")), "council": safe(f.get("council area", "")),
                       "agency": safe(f.get("responsible agency", "")), "type": safe(f.get("type", "")),
                       "lat": lat, "lon": lon, "link": p.get("link", "")})
    obs = Obs(price_cents=ordv * 100, qty=_size_ha(f),
              flags={"alert_level": safe(level), "status": safe(f.get("status", "")),
                     "fire": safe(f.get("fire", "")), "type": safe(f.get("type", "")),
                     "size": safe(f.get("size", "")), "council": safe(f.get("council area", "")),
                     "agency": safe(f.get("responsible agency", "")), "updated": safe(f.get("updated", "")),
                     "category": safe(p.get("category", ""))})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feats = None

    def features(self):
        if self._feats is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._feats = (r.json() or {}).get("features") or []
        return self._feats


class NswRfsSource(Source):
    name = "nswrfs"
    id_label = "INCIDENT"
    cc_default = "au"        # unused; one NSW board
    deal_label = "bushfire"  # out-of-control fire at Watch and Act or above
    search_limit_default = 30
    search_header = f"{'ALERT':>17}  {'SIZE':>8}  INCIDENT"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        feats = cl.features()
        return bool(feats), f"({len(feats)} current NSW RFS incidents; keyless majorIncidents feed)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for feat in cl.features():
            item, obs = _build(feat)
            hay = f"{item.name} {item.subtitle} {item.extra.get('council', '')}".lower()
            if not t or t in hay:
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))   # most severe first
        return out

    def fetch(self, cl, item_id):
        for feat in cl.features():
            item, obs = _build(feat)
            if str(item.id) == str(item_id):
                return item, obs
        return None

    def is_deal(self, obs):
        return LEVELS.get(obs.flags.get("alert_level", "").lower(), 0) >= DEAL_MIN and \
            obs.flags.get("fire", "").lower() == "yes"

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('alert_level')}  {item.name}  ({f.get('status')}, {f.get('size') or '? ha'})  {item.subtitle}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(f.get('alert_level') or '-')[:17]:>17}  {(f.get('size') or '-'):>8}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  incident : {item.name}",
                 f"  location : {e.get('location', '')}  ({e.get('council', '')})"]
        if obs:
            f = obs.flags
            lines.append(f"  alert    : {f.get('alert_level')}   status {f.get('status')}")
            lines.append(f"  type     : {f.get('type')}  (fire: {f.get('fire')}, size {f.get('size') or '?'})")
            lines.append(f"  agency   : {f.get('agency')}")
            lines.append(f"  updated  : {f.get('updated')}")
        lines.append(f"  link     : {e.get('link', '')}")
        return lines


SOURCE = NswRfsSource()
