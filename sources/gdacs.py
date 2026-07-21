"""gdacs - global multi-hazard disaster alerts via GDACS, keyless.

GDACS (the Global Disaster Alert and Coordination System, run by the EU JRC + UN OCHA) fuses live feeds
for earthquakes, tropical cyclones, floods, volcanoes, droughts and wildfires into one alert list,
scored Green/Orange/Red by expected humanitarian impact. `gdacsapi/api/events/geteventlist/EVENTS4APP`
returns the current events keyless as GeoJSON (robots.txt has no Disallow; the API feeds GDACS's own
apps = sanctioned -> trove). Fills a gap trove has circled for a while (NASA EONET was too flaky): a
single **global all-hazards** watch board with an alert-lifecycle mechanic.

The tracked scalar is the alert *state*: `price_cents` = the alert-level ordinal * 100 (GREEN=100,
ORANGE=200, RED=300) so the core's `drops` = an event being **downgraded** (impact revised down), the
volcano/nzroads de-escalation pattern; `qty` = the rounded severity value (magnitude, wind, etc). A
"deal" ("alert") = the alert level is ORANGE or RED (a significant event worth attention). The hazard
type, country, severity text and dates ride in flags.

Model: one Item per event (join key = composite `eventtype:eventid`, since ids repeat across hazard
types). One memoized GET serves a pass; an event ageing off the list -> fetch None -> its series ends
(the retirement pattern). `--cc` is unused; `search <term>` filters by country/name/hazard type.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP"
LEVEL = {"GREEN": 1, "ORANGE": 2, "RED": 3}
DEAL_LEVELS = {"ORANGE", "RED"}
HAZARD = {"EQ": "earthquake", "TC": "tropical cyclone", "FL": "flood", "VO": "volcano",
          "DR": "drought", "WF": "wildfire", "TS": "tsunami"}


def _round(v):
    return round(v) if isinstance(v, (int, float)) else None


def _build(feat):
    p = (feat or {}).get("properties") or {}
    etype = (p.get("eventtype") or "").upper()
    level = (p.get("alertlevel") or "").upper()
    ordv = LEVEL.get(level)
    sev = (p.get("severitydata") or {})
    iid = f"{etype}:{p.get('eventid')}"
    item = Item(iid, name=safe(p.get("name") or p.get("eventname") or iid),
                subtitle=f"{HAZARD.get(etype, etype)} - {level}".strip(" -"),
                category=HAZARD.get(etype, etype),
                extra={"country": safe(p.get("country") or ""), "hazard": HAZARD.get(etype, etype),
                       "url": p.get("url") or "", "iso3": p.get("iso3") or ""})
    obs = Obs(price_cents=(ordv * 100 if ordv else None), qty=_round(sev.get("severity")),
              flags={"level": level, "alertscore": p.get("alertscore"), "hazard": HAZARD.get(etype, etype),
                     "country": safe(p.get("country") or ""), "severity": safe(sev.get("severitytext") or ""),
                     "from": p.get("fromdate") or "", "to": p.get("todate") or "",
                     "current": p.get("iscurrent") or ""})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = None

    def feed(self):
        if self._feed is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._feed = (r.json() or {}).get("features") or []
        return self._feed


class GdacsSource(Source):
    name = "gdacs"
    id_label = "EVENT"
    cc_default = "world"     # unused
    deal_label = "alert"     # alert level ORANGE or RED
    search_limit_default = 40
    search_header = f"{'LEVEL':>7}  {'HAZARD':<16}  EVENT"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        fs = cl.feed()
        return bool(fs), f"({len(fs)} current global events; keyless GDACS EVENTS4APP)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for feat in cl.feed():
            item, obs = _build(feat)
            hay = f"{obs.flags.get('country', '')} {item.name} {obs.flags.get('hazard', '')}".lower()
            if not t or t in hay:
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        for feat in cl.feed():
            item, obs = _build(feat)
            if item.id == str(item_id):
                return item, obs
        return None

    def is_deal(self, obs):
        return obs.flags.get("level") in DEAL_LEVELS

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('level')} {f.get('hazard')}  {item.name}  ({f.get('country') or '?'}; {f.get('severity') or '?'})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{str(f.get('level') or '?'):>7}  {str(f.get('hazard') or '?'):<16}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  event    : {item.name}  ({e.get('hazard')})"]
        if obs:
            f = obs.flags
            lines.append(f"  level    : {f.get('level')}   score {f.get('alertscore')}")
            lines.append(f"  country  : {f.get('country') or '?'}   severity {f.get('severity') or '?'}")
            lines.append(f"  window   : {f.get('from') or '?'} -> {f.get('to') or '?'}   current {f.get('current')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = GdacsSource()
