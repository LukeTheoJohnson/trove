"""vicemergency - Victoria (AU) live emergency warnings + incidents, keyless GeoJSON.

Emergency Management Victoria publishes the state's live all-hazards board - warnings and incidents
across fire, flood, storm and more - as a keyless GeoJSON feed at
`emergency.vic.gov.au/public/osom-geojson.json` (the data behind the VicEmergency app/map). robots is
open and /public/ is an explicit public feed = sanctioned -> trove. AU sibling of `nswrfs` but
broader (all hazards, not just RFS fire) and a different state; a geohazard/emergency source.

The timeline value is a warning's **lifecycle as issued**: its alert level escalating (Advice ->
Watch and Act -> Emergency Warning) or easing, its status changing, then dropping off the feed once
resolved - current state only, never archived per-event. `price_cents` = the **alert-level ordinal *
100** (Emergency Warning=300, Watch and Act=200, Advice=100, else 0), so the core's `drops` = a
warning *de-escalating* (nzroads/volcano/nswrfs pattern); a "deal" ("warning") = an active warning at
Watch and Act or above. money() renders the centi-ordinal as dollars in the two core-hardcoded spots.

Model: one Item per warning/incident (join key = the feed `id`). `search <term>` filters by
name/location/hazard substring (pass "" to list all); `fetch` scans the memoized feed by id (an id
gone = resolved = series ends). `--cc` is unused - one Victorian board.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

FEED = "https://emergency.vic.gov.au/public/osom-geojson.json"
LEVELS = {"emergency warning": 3, "watch and act": 2, "advice": 1}   # else 0
DEAL_MIN = 2   # Watch and Act or above


def _first_point(geom):
    if not geom:
        return None, None
    if geom.get("type") == "Point":
        c = geom.get("coordinates") or [None, None]
        return c[0], c[1]
    for g in geom.get("geometries", []) or []:
        if g.get("type") == "Point":
            c = g.get("coordinates") or [None, None]
            return c[0], c[1]
    return None, None


def _build(feat):
    p = feat.get("properties") or {}
    level = (p.get("category1") or "").strip()
    ordv = LEVELS.get(level.lower(), 0)
    lon, lat = _first_point(feat.get("geometry"))
    iid = str(p.get("id") or p.get("sourceId") or "")
    name = safe(p.get("name") or p.get("webHeadline") or p.get("sourceTitle") or "")
    item = Item(iid, name=name, subtitle=safe(p.get("location", "")),
                category=safe(p.get("category2", "")),
                extra={"hazard": safe(p.get("category2", "")), "feed_type": p.get("feedType"),
                       "source_org": p.get("sourceOrg"), "location": safe(p.get("location", "")),
                       "lat": lat, "lon": lon})
    obs = Obs(price_cents=ordv * 100,
              flags={"alert_level": safe(level), "hazard": safe(p.get("category2", "")),
                     "status": safe(p.get("status", "")), "action": safe(p.get("action", "")),
                     "feed_type": p.get("feedType"), "statewide": p.get("statewide"),
                     "source_org": p.get("sourceOrg"), "updated": p.get("updated")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feats = None

    def features(self):
        if self._feats is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=45)
            r.raise_for_status()
            self._feats = (r.json() or {}).get("features") or []
        return self._feats


class VicEmergencySource(Source):
    name = "vicemergency"
    id_label = "EVENT"
    cc_default = "au"        # unused; one Victorian board
    deal_label = "warning"   # active warning at Watch and Act or above
    search_limit_default = 30
    search_header = f"{'ALERT':>17}  {'HAZARD':<10}  EVENT"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        feats = cl.features()
        return bool(feats), f"({len(feats)} current VIC warnings/incidents; keyless VicEmergency feed)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for feat in cl.features():
            item, obs = _build(feat)
            hay = f"{item.name} {item.subtitle} {item.extra.get('hazard', '')}".lower()
            if not t or t in hay:
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        for feat in cl.features():
            item, obs = _build(feat)
            if str(item.id) == str(item_id):
                return item, obs
        return None

    def is_deal(self, obs):
        return LEVELS.get(obs.flags.get("alert_level", "").lower(), 0) >= DEAL_MIN

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('alert_level')}  {f.get('hazard')}  {item.name}  ({f.get('status') or '?'})  {item.subtitle}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(f.get('alert_level') or '-')[:17]:>17}  {(f.get('hazard') or '-')[:10]:<10}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  event    : {item.name}",
                 f"  hazard   : {e.get('hazard', '')}   ({e.get('feed_type', '')})",
                 f"  location : {e.get('location', '')}"]
        if obs:
            f = obs.flags
            lines.append(f"  alert    : {f.get('alert_level')}   status {f.get('status') or '?'}")
            lines.append(f"  action   : {f.get('action') or '?'}")
            lines.append(f"  source   : {f.get('source_org', '')}   updated {f.get('updated', '')}")
        return lines


SOURCE = VicEmergencySource()
