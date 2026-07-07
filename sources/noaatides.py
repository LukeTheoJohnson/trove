"""noaatides - live US coastal water level via the keyless NOAA Tides & Currents API.

NOAA's CO-OPS (Center for Operational Oceanographic Products and Services) publishes real-time
water-level telemetry from ~300 coastal stations through a keyless, official, documented REST service
(`api.tidesandcurrents.noaa.gov`). Its `/robots.txt` 403s (a missing object = no rules = unfenced, the
GBFS/S3 class) and NOAA open data is sanctioned -> trove. This **opens the marine & coastal domain**
(roadmap Axis A white space), alongside `ndbc` (offshore buoys).

The tracked value is the live water level (feet above the MLLW tidal datum) at 6-minute telemetry -
the tide rising and falling, plus storm-surge departures from prediction. `price_cents` = level * 100
(centi-feet), so the core's `drops` = the water *falling* (ebb tide). The interesting event is a
*rise*, so the 24h window is pulled at fetch time and the flood/ebb trend + 24h max are stored in
flags: `is_deal` ("hightide") = the level is rising and within 5% of its 24h max (at/approaching high
tide - the surge/coastal-flood-relevant moment). Honest hoard value is low-med: NOAA archives the full
record (rebuildable, the octopus/frankfurter class), so the draw is opening the domain + the live
tide/surge signal, not un-rebuildability.

Two endpoints: `mdapi/prod/webapi/stations.json?type=waterlevels` lists the stations (id/name/state/
lat/lng - the join key is the 7-digit station id); `api/prod/datagetter?product=water_level&
station=<id>&range=24&datum=MLLW&units=english&format=json` returns the recent series as
`data:[{t, v, s, f, q}]` (v = level ft, q = 'p' preliminary / 'v' verified). `search` filters the
station list and fetches live level for the matches (polite fan-out, gwrivers pattern); `item`/`poll`
fetch one station. `--cc` is unused (one US network).
"""
from __future__ import annotations

import time

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

STATIONS = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels"
DATA = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NEAR_HIGH = 0.95        # rising and within 5% of the 24h max = "hightide"


def _series(data):
    """datagetter data list -> [(t, level_ft)] ascending, blanks/'MM' dropped."""
    out = []
    for row in data or []:
        v = (row.get("v") or "").strip()
        if not v:
            continue
        try:
            out.append((row.get("t"), float(v)))
        except ValueError:
            pass
    return out


def _build(station, pts):
    """A station dict + its 24h series -> (Item, Obs). None if the series is empty."""
    if not pts:
        return None
    sid = str(station.get("id"))
    name = safe(station.get("name") or sid)
    state = station.get("state") or ""
    t_now, v_now = pts[-1]
    vals = [v for _, v in pts]
    vmax, vmin = max(vals), min(vals)
    v_prev = pts[-2][1] if len(pts) > 1 else v_now
    rising = v_now > v_prev
    near_high = bool(vmax and v_now >= NEAR_HIGH * vmax)
    item = Item(sid, name=f"{name}{f', {state}' if state else ''}",
                subtitle=f"water level {round(v_now, 2)} ft MLLW  ({'flood/rising' if rising else 'ebb/falling'})",
                category="tide gauge",
                extra={"state": state, "lat": station.get("lat"), "lon": station.get("lng"),
                       "url": f"https://tidesandcurrents.noaa.gov/stationhome.html?id={sid}"})
    obs = Obs(price_cents=round(v_now * 100),
              qty=None,
              flags={"level_ft": round(v_now, 3), "datum": "MLLW", "rising": rising,
                     "near_high": near_high, "max_24h": round(vmax, 3), "min_24h": round(vmin, 3),
                     "range_24h": round(vmax - vmin, 3), "time": t_now, "state": state})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._stations = None

    def stations(self):
        if self._stations is None:
            r = self.s.get(STATIONS, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=45)
            r.raise_for_status()
            self._stations = (r.json() or {}).get("stations") or []
        return self._stations

    def level(self, sid):
        r = self.s.get(DATA, params={"product": "water_level", "application": "trove-personal",
                                     "station": str(sid), "range": "24", "datum": "MLLW",
                                     "time_zone": "lst_ldt", "units": "english", "format": "json"},
                       headers={"User-Agent": UA, "Accept": "application/json"}, timeout=45)
        r.raise_for_status()
        return _series((r.json() or {}).get("data") or [])

    def report(self, sid):
        st = next((s for s in self.stations() if str(s.get("id")) == str(sid)), None)
        if st is None:
            st = {"id": sid, "name": sid}
        try:
            pts = self.level(sid)
        except Exception:
            pts = []
        return _build(st, pts)


class NoaaTidesSource(Source):
    name = "noaatides"
    id_label = "STATION"
    cc_default = "us"          # unused; one US network
    deal_label = "hightide"    # rising and within 5% of the 24h max
    search_limit_default = 8    # search fetches live per match; keep the fan-out polite
    search_header = f"{'LEVEL':>12}  {'TREND':<12}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        st = cl.stations()
        return bool(st), f"({len(st)} NOAA water-level stations; keyless CO-OPS datagetter)"

    def search(self, cl, term, args):
        t = (term or "").strip().lower()
        matches = [s for s in cl.stations()
                   if not t or t in (s.get("name") or "").lower()
                   or t == str(s.get("id")) or t == (s.get("state") or "").lower()]
        rows = []
        for i, st in enumerate(matches[: args.limit]):
            try:
                pts = cl.level(str(st.get("id")))
            except Exception:
                pts = []
            built = _build(st, pts)
            if built:
                rows.append(built)
            if i + 1 < min(len(matches), args.limit):
                time.sleep(0.3)
        return rows

    def fetch(self, cl, item_id):
        return cl.report(str(item_id))

    def is_deal(self, obs):
        f = obs.flags
        return bool(f.get("rising") and f.get("near_high"))

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('level_ft')} ft (24h max {f.get('max_24h')})  rising = high tide/surge"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        lvl = f"{f.get('level_ft', '?')} ft"
        trend = "flood/up" if f.get("rising") else "ebb/down"
        return f"{lvl:>12}  {trend:<12}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = []
        if obs:
            f = obs.flags
            lines.append(f"  level    : {f.get('level_ft')} ft above {f.get('datum')}   at {f.get('time')}")
            lines.append(f"  trend    : {'flood/rising' if f.get('rising') else 'ebb/falling'}"
                         f"{'  (near high)' if f.get('near_high') else ''}")
            lines.append(f"  24h range: {f.get('min_24h')} .. {f.get('max_24h')} ft  (span {f.get('range_24h')})")
        lines.append(f"  station  : {e.get('state', '')}  {e.get('lat')}, {e.get('lon')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = NoaaTidesSource()
