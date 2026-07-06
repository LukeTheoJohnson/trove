"""eafloods - England Environment Agency live flood warnings + alerts, keyless (OGL v3.0).

The Environment Agency publishes the real-time flood-monitoring API at environment.data.gov.uk under
the Open Government Licence. `GET /flood-monitoring/id/floods` returns every flood warning/alert
currently *in force* across England, each with a `severityLevel` (1 = Severe Flood Warning -
danger to life, 2 = Flood Warning, 3 = Flood Alert, 4 = warning no longer in force), the flood-area
name, a tidal flag, a free-text `message`, and the timestamps it was raised / last changed. robots.txt
fences some other products (`/data/`, `/doc/`, `/water-quality`, ...) but **not** `/flood-monitoring/`,
and the licence explicitly invites reuse = sanctioned -> trove. The weather/geohazard genre-mate to the
NZ river gauges (`gwrivers` et al.) - but where those hoard a *level*, this hoards the EA's *assessment*
(the warning and its escalation), the un-rebuildable part.

The timeline value is the warning's lifecycle: an area escalates Alert -> Warning -> Severe and then
stands down, and the EA serves only the currently-in-force set - no queryable per-area history of the
escalate/ease/resolve arc. `price_cents` = an **impact ordinal** * 100 (Severe=400, Warning=300,
Alert=200, no-longer-in-force=100; = `(5 - severityLevel) * 100`), so the core's `drops` = an area's
warning *de-escalating*; a warning vanishing from the feed = stood down = the area's series ends
(the `nzroads`/`volcano` retirement contract). A "deal" ("flood") = a live Flood Warning or Severe
Flood Warning (severityLevel <= 2, i.e. flooding expected, not just possible). money() renders the
centi-ordinal as dollars in the two core-hardcoded spots; the rich views show the severity words.

The feed is event-driven and often empty in a dry spell (like `avalanche` off-season) - that is
correct, not a fault: `search` returns the in-force set (may be 0) and `doctor` reports the feed is
healthy with its current count. Model: one Item per flood area (join key = `floodAreaID`). `search
<term>` filters by area/description (pass "" to list all in force); `fetch` scans the feed by id.
`--cc` is unused - England is one set of areas.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://environment.data.gov.uk/flood-monitoring/id/floods"
SEV_LABEL = {1: "Severe Flood Warning", 2: "Flood Warning", 3: "Flood Alert",
             4: "No longer in force"}


def _sev(f):
    try:
        return int(f.get("severityLevel"))
    except (TypeError, ValueError):
        return None


def _build(f):
    sev = _sev(f)
    area = f.get("floodArea") or {}
    aid = str(f.get("floodAreaID") or area.get("notation") or f.get("@id", ""))
    name = safe(f.get("description") or area.get("description") or aid)
    impact = (5 - sev) if sev is not None else None
    item = Item(aid, name=name, subtitle="EA flood area (England)", category="floodarea",
                extra={"area_id": aid, "county": safe(area.get("county", "")),
                       "river": safe(area.get("riverOrSea", "")), "tidal": f.get("isTidal"),
                       "url": f.get("@id", "")})
    obs = Obs(price_cents=(impact * 100 if impact is not None else None),
              flags={"severity": sev, "severity_label": f.get("severity") or SEV_LABEL.get(sev),
                     "message": safe(f.get("message", ""))[:200], "tidal": f.get("isTidal"),
                     "raised": f.get("timeRaised"), "changed": f.get("timeSeverityChanged")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._floods = None

    def floods(self):
        if self._floods is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._floods = (r.json() or {}).get("items") or []
        return self._floods


class EaFloodsSource(Source):
    name = "eafloods"
    id_label = "AREA"
    cc_default = "uk"        # unused; England is one set
    deal_label = "flood"     # a live Flood Warning / Severe Flood Warning (severity <= 2)
    search_limit_default = 40
    search_header = f"{'SEV':>3}  {'SEVERITY':<20}  AREA"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        fl = cl.floods()
        return True, f"({len(fl)} flood warnings in force; keyless EA flood-monitoring API [OGL])"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for f in cl.floods():
            item, obs = _build(f)
            if not t or t in item.name.lower() or t in item.extra.get("county", "").lower():
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 999,
                                 io[0].name.lower()))
        return out

    def fetch(self, cl, item_id):
        for f in cl.floods():
            area = f.get("floodArea") or {}
            aid = str(f.get("floodAreaID") or area.get("notation") or "")
            if aid == str(item_id):
                return _build(f)
        return None

    def is_deal(self, obs):
        sev = obs.flags.get("severity")
        return sev is not None and sev <= 2

    def deal_line(self, item, obs):
        return f"{obs.flags.get('severity_label') or '?'}  {item.name}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(f.get('severity') if f.get('severity') is not None else '?'):>3}  {safe(f.get('severity_label') or '-'):<20}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  area     : {item.name}",
                 f"  county   : {e.get('county') or '?'}   river/sea: {e.get('river') or '?'}   tidal: {e.get('tidal')}"]
        if obs:
            lines.append(f"  severity : {obs.flags.get('severity_label') or '?'}  (level {obs.flags.get('severity')})")
            if obs.flags.get("message"):
                lines.append(f"  message  : {obs.flags.get('message')}")
            lines.append(f"  raised   : {obs.flags.get('raised') or '?'}")
        return lines


SOURCE = EaFloodsSource()
