"""turkeyquake - Turkish earthquakes via AFAD's keyless event filter API.

AFAD (Turkiye's Disaster & Emergency Management Presidency) publishes located events through its keyless
API `deprem.afad.gov.tr/apiv2/event/filter`: a JSON list of recent events with eventID, location,
latitude/longitude, depth, magnitude type/value, province and district. robots.txt is open and the API
is official open data = sanctioned -> trove. Opens **Turkey** (astride the North & East Anatolian
faults - one of the most earthquake-exposed nations), twinning `geonet`/`usgsquakes`/`eqcanada`/`bmkg`.

Honest hoard value is low (AFAD keeps the catalogue - the usgsquakes class); the ephemeral part is the
as-reported magnitude, revised in the hours after an event. `price_cents` = magnitude * 100 (centi-
magnitude, the geonet scalar) so the core's `drops` = an event *downgraded* on review; `qty` = None. A
"deal" ("strong") = magnitude >= 4.0.

Model: one Item per event (join key = the AFAD eventID). One memoized query over the last few days
serves search; `fetch` re-queries by eventID. `--cc` is unused.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://deprem.afad.gov.tr/apiv2/event/filter"
STRONG = 4.0
WINDOW_DAYS = 3


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build(ev):
    mag = _f(ev.get("magnitude"))
    place = safe(ev.get("location") or "")
    item = Item(str(ev.get("eventID")), name=place or str(ev.get("eventID")),
                subtitle=f"M{ev.get('magnitude')} {ev.get('type') or ''}".strip(), category="quake",
                extra={"lat": _f(ev.get("latitude")), "lon": _f(ev.get("longitude")),
                       "depth_km": _f(ev.get("depth")), "province": safe(ev.get("province") or ""),
                       "district": safe(ev.get("district") or "")})
    obs = Obs(price_cents=(round(mag * 100) if mag is not None else None), qty=None,
              flags={"mag": mag, "place": place, "time": (ev.get("date") or "").replace("T", " "),
                     "depth_km": _f(ev.get("depth")), "magType": ev.get("type") or "",
                     "province": safe(ev.get("province") or "")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = None

    def _query(self, params):
        r = self.s.get(BASE, params=params, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or []

    def feed(self):
        if self._feed is None:
            now = datetime.now(timezone.utc)
            start = (now - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            end = now.strftime("%Y-%m-%d %H:%M:%S")
            self._feed = self._query({"start": start, "end": end, "orderby": "timedesc", "limit": 100})
        return self._feed

    def by_id(self, eid):
        for ev in self.feed():
            if str(ev.get("eventID")) == str(eid):
                return ev
        return None


class TurkeyQuakeSource(Source):
    name = "turkeyquake"
    id_label = "EVENTID"
    cc_default = "tr"        # unused
    deal_label = "strong"    # magnitude >= 4.0
    search_limit_default = 30
    search_header = f"{'MAG':>5}  {'WHEN':<19}  PLACE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        fs = cl.feed()
        return bool(fs), f"({len(fs)} TR events (last {WINDOW_DAYS}d); keyless AFAD event filter)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for ev in cl.feed():
            item, obs = _build(ev)
            if not t or t in safe(obs.flags.get("place") or "").lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        ev = cl.by_id(str(item_id))
        return _build(ev) if ev else None

    def is_deal(self, obs):
        m = obs.flags.get("mag")
        return isinstance(m, (int, float)) and m >= STRONG

    def deal_line(self, item, obs):
        f = obs.flags
        return f"M{f.get('mag')} {item.name}  ({f.get('time') or '?'})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        m = f.get("mag")
        return f"{(m if m is not None else '?'):>5}  {(f.get('time') or '')[:19]:<19}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  place    : {item.name}  ({e.get('province') or '?'})"]
        if obs:
            f = obs.flags
            lines.append(f"  magnitude: M{f.get('mag')}  ({e.get('magType') or f.get('magType') or '?'})   depth {e.get('depth_km')} km")
            lines.append(f"  time     : {f.get('time') or '?'}")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        return lines


SOURCE = TurkeyQuakeSource()
