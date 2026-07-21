"""smhi - live Swedish air-temperature observations via SMHI Open Data (metobs), keyless.

SMHI (Sweden's meteorological & hydrological institute) publishes station observations as keyless open
data. The metobs station-set endpoint
`opendata-download-metobs.smhi.se/api/version/1.0/parameter/1/station-set/all/period/latest-hour/data.json`
returns the latest air temperature (parameter 1, degrees C) for every reporting station in one GET.
robots.txt is 404 (unfenced) and the data is CC-licensed open data = sanctioned -> trove. Opens
**Sweden** and is the metno/ipma present-state twin over Scandinavia.

The tracked scalar is the live station temperature: `price_cents` = temperature in centi-degrees C (so
the core's `drops` = a station *cooling*); `qty` = None. A "deal" ("warm") = the station is at or above
25 C (a notable warm reading at Swedish latitudes). The measurement time and coordinates ride in flags.
money() renders centi-degrees as '$' in the two hardcoded spots.

Model: one Item per station (join key = the SMHI station key). One memoized GET serves a whole pass;
`search <term>` filters by station name, `fetch` scans the board. `--cc` is unused (one national set).
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = ("https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/1/"
        "station-set/all/period/latest-hour/data.json")
WARM = 25.0


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _epoch(ms):
    if not isinstance(ms, (int, float)):
        return ""
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def _build(st):
    values = st.get("value") or []
    latest = values[-1] if values else {}
    temp = _f(latest.get("value"))
    key = str(st.get("key"))
    item = Item(key, name=safe(st.get("name") or key), subtitle="SMHI air temperature", category="SE",
                extra={"lat": _f(st.get("latitude")), "lon": _f(st.get("longitude"))})
    obs = Obs(price_cents=(round(temp * 100) if temp is not None else None), qty=None,
              flags={"temp_c": temp, "measured": _epoch(latest.get("date")), "unit": "C"})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._stations = None

    def stations(self):
        if self._stations is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=45)
            r.raise_for_status()
            data = r.json() or {}
            self._stations = [s for s in (data.get("station") or []) if s.get("value")]
        return self._stations


class SmhiSource(Source):
    name = "smhi"
    id_label = "STATION"
    cc_default = "se"        # unused
    deal_label = "warm"      # temperature >= 25 C
    search_limit_default = 30
    search_header = f"{'TEMP':>5}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        st = cl.stations()
        return bool(st), f"({len(st)} SE stations reporting temp; keyless SMHI metobs)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for st in cl.stations():
            item, obs = _build(st)
            if not t or t in safe(item.name).lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents if io[1].price_cents is not None else -10 ** 9))
        return out

    def fetch(self, cl, item_id):
        for st in cl.stations():
            if str(st.get("key")) == str(item_id):
                return _build(st)
        return None

    def is_deal(self, obs):
        t = obs.flags.get("temp_c")
        return isinstance(t, (int, float)) and t >= WARM

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('temp_c')} C  ({f.get('measured')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(str(f.get('temp_c')) if f.get('temp_c') is not None else '?'):>5}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  station  : {item.name}   [{e.get('lat')}, {e.get('lon')}]"]
        if obs:
            f = obs.flags
            lines.append(f"  temp     : {f.get('temp_c')} C")
            lines.append(f"  measured : {f.get('measured')}")
        return lines


SOURCE = SmhiSource()
