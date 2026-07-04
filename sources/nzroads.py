"""nzroads - NZTA Journeys national highway disruption board (journeys.nzta.govt.nz), keyless JSON.

Waka Kotahi NZTA's Journeys site is the official national road-conditions map. Its robots.txt is
`User-agent: *` + `Crawl-delay: 10` - zero Disallow, no prose ban - and the map's React bundle
fetches all event data from one same-origin, keyless, page-called file:
GET /assets/map-data-cache/delays.json (the bundle joins "/assets/map-data-cache/" + "delays.json"
and splits the result into roadworks/closures/hazards/warnings). Page-called + unfenced = sanctioned
-> trove. (The marketing host www.nzta.govt.nz sits behind an Imperva challenge, but the journeys
host serves plainly; the official InfoConnect feeds need registration - this is the public tier the
published page itself uses.)

The timeline value is the **lifecycle of a road event**: a crash/ice/slip event appears, its impact
escalates or eases (Caution -> Delays -> Road Closed and back), its expected-resolution shifts, and
then it vanishes from the feed when resolved. Nothing public archives that per-event progression -
the snapshot is the only record. One GET returns the whole national board (~100 live events), so a
full poll is a single polite request (memoized per run), well inside the 10s crawl-delay.

There is no price on a road, so the tracked scalar is an **impact-severity ordinal** (Road Closed=4,
Vehicle Restrictions=3, Delays=2, Caution=1, none/info=0) * 100 in `price_cents` (centi-severity,
volcano's pattern), so the core's `drops` = a de-escalation - the road reopening/recovering. Like
geonet/volcano, money() cosmetically renders centi-severity as dollars in the two core-hardcoded
spots (watchlist + poll DROP line); the rich displays show the real impact text. The "deal"
(deal_label "disruption") = an **unplanned, active event at Delays or worse** - a live crash, ice
closure, or slip, as opposed to scheduled roadworks.

Model: one Item per road event (join key = the feed's `id`, NZTA's ExternalId, e.g. 553917). There
is no by-id endpoint, so fetch scans the memoized national feed (petrolspy's pattern); an event gone
from the feed = resolved = its series ends. `qty` = number of regions the event touches. `search`
filters by keyword over name/location/description; `--type` narrows to closures/hazards/roadworks/
warnings, `--island` to north/south. `--cc` is unused (one national feed).
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

HOST = "https://www.journeys.nzta.govt.nz"
FEED = HOST + "/assets/map-data-cache/delays.json"
LIST_URL = HOST + "/highway-conditions/traffic-and-travel-list-view"

SEVERITY = {"Road Closed": 4, "Vehicle Restrictions": 3, "Delays": 2, "Caution": 1}
DISRUPT_CENTS = 200          # Delays or worse
TYPES = ("closures", "hazards", "roadworks", "warnings")


def _coords(feat):
    """Point -> its pair; MultiLineString -> the first vertex. (lon, lat) or (None, None)."""
    geom = (feat or {}).get("geometry") or {}
    c = geom.get("coordinates")
    try:
        if geom.get("type") == "Point":
            return c[0], c[1]
        if geom.get("type") == "MultiLineString":
            return c[0][0][0], c[0][0][1]
    except (IndexError, TypeError):
        pass
    return None, None


def _event(feat):
    """One GeoJSON road-event feature -> (Item, Obs). None without an id."""
    p = (feat or {}).get("properties", {}) or {}
    eid = p.get("id") or p.get("ExternalId")
    if not eid:
        return None
    lon, lat = _coords(feat)
    impact = p.get("Impact") or ""
    sev = SEVERITY.get(impact, 0)
    etype = p.get("type", "") or ""
    desc = safe(p.get("EventDescription", "") or "")
    status = p.get("Status") or ""
    planned = bool(p.get("IsPlanned") or 0)
    item = Item(str(eid),
                name=safe(p.get("Name", "") or f"{etype} {eid}"),
                subtitle=safe(f"{impact or 'Info'} - {desc}".strip(" -")),
                category=etype,
                extra={"event_type": safe(p.get("EventType", "") or ""), "description": desc,
                       "location": safe(p.get("LocationArea", "") or ""),
                       "island": p.get("EventIsland") or "", "planned": planned,
                       "source": p.get("InformationSource") or "",
                       "start": p.get("StartDate") or "", "regions": p.get("regions") or [],
                       "lat": lat, "lon": lon, "url": LIST_URL})
    obs = Obs(price_cents=sev * 100,
              qty=len(p.get("regions") or []) or None,
              flags={"impact": impact, "severity": sev, "type": etype, "status": status,
                     "planned": planned, "critical": bool(p.get("IsCritical") or 0),
                     "description": desc, "comments": safe(p.get("EventComments", "") or "")[:200],
                     "expected": safe(p.get("ExpectedResolutionText", "") or ""),
                     "last_edited": p.get("LastEdited") or ""})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = None    # one GET serves a whole search/fetch/poll pass

    def feed(self):
        if self._feed is None:
            r = self.s.get(FEED, headers={"User-Agent": UA, "Accept": "application/json",
                                          "Referer": HOST + "/journey-planner"}, timeout=40)
            r.raise_for_status()
            d = r.json() or {}
            self._feed = (d.get("features") or [], d.get("lastUpdated"))
        return self._feed


class NzRoadsSource(Source):
    name = "nzroads"
    id_label = "EVENT"
    cc_default = "nz"            # unused; one national feed
    deal_label = "disruption"    # unplanned + active + Delays-or-worse
    search_args = [
        ("--type", {"choices": list(TYPES) + ["all"], "default": "all",
                    "help": "event class (default all)"}),
        ("--island", {"choices": ["north", "south", "all"], "default": "all",
                      "help": "filter by island (default all)"}),
    ]
    search_limit_default = 120   # the national board is bounded (~100 events); list it
    search_header = f"{'IMPACT':<12}  {'TYPE':<9}  {'STATUS':<9}  EVENT"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        feats, updated = cl.feed()
        n = {t: 0 for t in TYPES}
        for f in feats:
            t = (f.get("properties") or {}).get("type")
            if t in n:
                n[t] += 1
        parts = ", ".join(f"{n[t]} {t}" for t in TYPES)
        return bool(feats), f"({len(feats)} live road events: {parts}; keyless page-called delays.json)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        want_type = getattr(args, "type", "all") or "all"
        want_island = getattr(args, "island", "all") or "all"
        rows = []
        for f in cl.feed()[0]:
            built = _event(f)
            if not built:
                continue
            item, obs = built
            if want_type != "all" and obs.flags.get("type") != want_type:
                continue
            if want_island != "all" and not (item.extra.get("island") or "").lower().startswith(want_island):
                continue
            e = item.extra
            hay = f"{item.name} {e.get('location', '')} {e.get('description', '')} {e.get('event_type', '')}".lower()
            if not t or t in hay:
                rows.append((item, obs))
        rows.sort(key=lambda r: (-(r[1].flags.get("severity") or 0),
                                 r[1].flags.get("planned", True), r[0].name))
        return rows

    def fetch(self, cl, item_id):
        for f in cl.feed()[0]:
            p = f.get("properties") or {}
            if str(p.get("id") or p.get("ExternalId") or "") == str(item_id):
                return _event(f)
        return None    # gone from the feed = resolved; the series ends

    def is_deal(self, obs):
        f = obs.flags
        return (not f.get("planned", True) and f.get("status") == "Active"
                and obs.price_cents is not None and obs.price_cents >= DISRUPT_CENTS)

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('impact') or '?'}  {item.name}  [{f.get('expected') or 'no ETA'}]"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return (f"{(f.get('impact') or '-')[:12]:<12}  {(f.get('type') or ''):<9}  "
                f"{(f.get('status') or ''):<9}  {item.name[:70]}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  event    : {e.get('event_type', '')}  ({item.category})",
                 f"  location : {e.get('location', '')}",
                 f"  island   : {e.get('island', '')}  regions {e.get('regions', [])}"]
        if obs:
            f = obs.flags
            lines.append(f"  impact   : {f.get('impact') or '(none)'}  severity {f.get('severity')}/4")
            lines.append(f"  status   : {f.get('status') or '?'}  {'planned' if f.get('planned') else 'UNPLANNED'}")
            lines.append(f"  detail   : {f.get('comments', '')}")
            lines.append(f"  expected : {f.get('expected') or '?'}")
            lines.append(f"  edited   : {f.get('last_edited', '')}")
        lines.append(f"  started  : {e.get('start', '')}  (source: {e.get('source', '')})")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = NzRoadsSource()
