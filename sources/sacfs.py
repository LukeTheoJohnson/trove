"""sacfs - South Australia Country Fire Service live incidents board, keyless JSON.

The SA CFS publishes its current incidents - fires, rescues, hazmat and other emergency responses -
as a keyless JSON feed on the state's emergency-services open-data host
(data.eso.sa.gov.au/prod/cfs/criimson/cfs_current_incidents.json), the data behind the CFS incidents
map. Public open-data host, no key = sanctioned -> trove. AU sibling of `nswrfs` / `vicemergency`
(different state; all incident types, not just fire).

The timeline value is an incident's **lifecycle as issued**: its response Level rising or easing and
its status changing (GOING -> CONTAINED -> COMPLETE), then dropping off the board once closed -
current state only, never archived per-incident. `price_cents` = the response **Level * 100** (so the
core's `drops` = an incident *de-escalating*); `qty` = appliances/resources committed; a "deal"
("active") = an incident still GOING. money() renders the centi-level as dollars in the two
core-hardcoded spots (a Level 2 prints as "$2.00"; geonet precedent).

Model: one Item per incident (join key = `IncidentNo`). `search <term>` filters by type/location/
status substring (pass "" to list all); `fetch` scans the memoized board by id (an id gone = closed =
series ends). `--cc` is unused - one SA board.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

FEED = "https://data.eso.sa.gov.au/prod/cfs/criimson/cfs_current_incidents.json"


def _latlon(s):
    parts = (s or "").split(",")
    if len(parts) == 2:
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            pass
    return None, None


def _build(rec):
    iid = str(rec.get("IncidentNo", ""))
    lat, lon = _latlon(rec.get("Location"))
    try:
        level = int(rec.get("Level"))
    except (TypeError, ValueError):
        level = None
    itype = safe(rec.get("Type", ""))
    loc = safe(rec.get("Location_name", ""))
    item = Item(iid, name=f"{itype} - {loc}".strip(" -"),
                subtitle=safe(f"Region {rec.get('Region', '')}"), category=itype,
                extra={"type": itype, "location": loc, "region": rec.get("Region"),
                       "lat": lat, "lon": lon, "link": safe(rec.get("Message_link", ""))})
    obs = Obs(price_cents=(level * 100 if level is not None else None),
              qty=(rec.get("Resources") if isinstance(rec.get("Resources"), int) else None),
              flags={"type": itype, "status": safe(rec.get("Status", "")), "level": level,
                     "region": rec.get("Region"), "resources": rec.get("Resources"),
                     "aircraft": rec.get("Aircraft"), "date": rec.get("Date"),
                     "time": rec.get("Time"), "message": safe(rec.get("Message", ""))})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._recs = None

    def incidents(self):
        if self._recs is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._recs = r.json() or []
        return self._recs


class SaCfsSource(Source):
    name = "sacfs"
    id_label = "INCIDENT"
    cc_default = "au"        # unused; one SA board
    deal_label = "active"    # incident still GOING
    search_limit_default = 30
    search_header = f"{'LEVEL':>6}  {'STATUS':<10}  INCIDENT"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        recs = cl.incidents()
        return bool(recs), f"({len(recs)} current SA CFS incidents; keyless CFS feed)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for rec in cl.incidents():
            item, obs = _build(rec)
            hay = f"{item.name} {obs.flags.get('status', '')} {item.category}".lower()
            if not t or t in hay:
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        for rec in cl.incidents():
            if str(rec.get("IncidentNo")) == str(item_id):
                return _build(rec)
        return None

    def is_deal(self, obs):
        return obs.flags.get("status", "").upper() == "GOING"

    def deal_line(self, item, obs):
        f = obs.flags
        lv = f.get("level")
        return f"Level {lv if lv is not None else '?'}  {f.get('status')}  {item.name}  ({f.get('resources', 0)} appliances)"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        lv = f.get("level")
        return f"{('L' + str(lv)) if lv is not None else '-':>6}  {(f.get('status') or '-')[:10]:<10}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  incident : {item.name}",
                 f"  location : {e.get('location', '')}  (region {e.get('region', '')})",
                 f"  coords   : {e.get('lat', '?')}, {e.get('lon', '?')}"]
        if obs:
            f = obs.flags
            lines.append(f"  level    : {f.get('level')}   status {f.get('status')}")
            lines.append(f"  resources: {f.get('resources', 0)} appliances, {f.get('aircraft', 0)} aircraft")
            lines.append(f"  reported : {f.get('date')} {f.get('time')}")
            if f.get("message"):
                lines.append(f"  message  : {f.get('message')}")
        return lines


SOURCE = SaCfsSource()
