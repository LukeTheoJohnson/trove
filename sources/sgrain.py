"""sgrain - live Singapore rainfall per gauge via data.gov.sg realtime environment, keyless.

data.gov.sg publishes Singapore's real-time environment readings keyless (the same official open-data
host behind `sgtaxi` and `sgcarpark`): `api.data.gov.sg/v1/environment/rainfall` returns the latest
5-minute rainfall (mm) at ~77 gauges across the island, with each station's name and coordinates.
robots.txt is a 403 (missing = unfenced, the opensky/S3 class) under the Singapore Open Data Licence =
sanctioned -> trove. Opens **Singapore** weather/environment (beyond the existing taxi + carpark
sources) with a dense rain-gauge network - and Singapore's rain is famously sudden, intense and
hyper-local, so the per-gauge trace is genuinely ephemeral (the downpour over one district that the
next district never sees).

The tracked scalar is the live rainfall: `price_cents` = rainfall in centi-millimetres (so the core's
`drops` = rain *easing* at that gauge); `qty` = None. A "deal" ("raining") = the gauge is currently
recording rain (value > 0 mm). The reading timestamp and coordinates ride in flags. money() renders
centi-mm as '$' in the two hardcoded spots.

Model: one Item per gauge (join key = the station id, e.g. `S77`). One memoized GET merges the station
catalogue with the latest readings; `search <term>` filters by station name, `fetch` scans the board.
`--cc` is unused (one national network).
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://api.data.gov.sg/v1/environment/rainfall"


def _f(v):
    return float(v) if isinstance(v, (int, float)) else None


def _build(station, value, ts):
    sid = str(station.get("id"))
    loc = station.get("location") or {}
    mm = _f(value)
    item = Item(sid, name=safe(station.get("name") or sid), subtitle="Singapore rain gauge (mm/5min)",
                category="SG", extra={"lat": _f(loc.get("latitude")), "lon": _f(loc.get("longitude"))})
    obs = Obs(price_cents=(round(mm * 100) if mm is not None else None), qty=None,
              flags={"rain_mm": mm, "measured": ts, "unit": "mm"})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._board = None       # sid -> (station, value, ts)

    def board(self):
        if self._board is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            d = r.json() or {}
            stations = {str(s.get("id")): s for s in (d.get("metadata") or {}).get("stations") or []}
            item0 = (d.get("items") or [{}])[0]
            ts = item0.get("timestamp") or ""
            readings = {str(rd.get("station_id")): rd.get("value") for rd in (item0.get("readings") or [])}
            self._board = {sid: (st, readings.get(sid), ts) for sid, st in stations.items() if sid in readings}
        return self._board


class SgRainSource(Source):
    name = "sgrain"
    id_label = "STATION"
    cc_default = "sg"        # unused
    deal_label = "raining"   # gauge currently recording rain (> 0 mm)
    search_limit_default = 30
    search_header = f"{'RAIN_MM':>8}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        b = cl.board()
        wet = sum(1 for _, v, _ in b.values() if isinstance(v, (int, float)) and v > 0)
        return bool(b), f"({len(b)} SG rain gauges, {wet} raining now; keyless data.gov.sg)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for sid, (st, value, ts) in cl.board().items():
            item, obs = _build(st, value, ts)
            if not t or t in safe(item.name).lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        b = cl.board().get(str(item_id))
        return _build(b[0], b[1], b[2]) if b else None

    def is_deal(self, obs):
        r = obs.flags.get("rain_mm")
        return isinstance(r, (int, float)) and r > 0

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('rain_mm')} mm rain  ({f.get('measured')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(str(f.get('rain_mm')) if f.get('rain_mm') is not None else '?'):>8}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  gauge    : {item.name}  ({item.id})   [{e.get('lat')}, {e.get('lon')}]"]
        if obs:
            f = obs.flags
            lines.append(f"  rainfall : {f.get('rain_mm')} mm  (last 5 min)")
            lines.append(f"  measured : {f.get('measured')}")
        return lines


SOURCE = SgRainSource()
