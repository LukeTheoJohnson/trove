"""luchtmeetnet - official Netherlands air quality (PM2.5) per station, keyless (RIVM/Luchtmeetnet).

Luchtmeetnet is the Dutch national air-quality portal (run by RIVM with the provinces); it publishes
every official monitoring station's live readings through a keyless open API (`api.luchtmeetnet.nl`;
robots.txt is 403-missing = unfenced, and it exists for public reuse = sanctioned -> trove). The
government-grade twin of `airquality` (which reads noisy citizen Sensor.Community nodes): same "fine
particulate right now, per station" shape, but calibrated reference monitors over the Netherlands
instead of hobbyist sensors.

The tracked value is **PM2.5** (particulate <=2.5 micrometres, the health-relevant pollutant) in
micrograms/m3. `price_cents` = PM2.5 * 100 (centi-microgram) so the core's `drops` = the air
*cleaning*; `is_deal` ("unhealthy") = PM2.5 >= 25 ug/m3 (around the WHO 24h guideline - a poor-air
moment). `qty` = None. Honest hoard value low-med: RIVM archives its own validated history
(rebuildable), and the draw is the live official signal + a calibrated counterpart to the citizen
network, not un-rebuildability.

Model: one Item per station (join key = the station `number`, e.g. NL10643; names from the memoized
`/stations` list). A pass reads the newest hour of `/measurements?formula=PM25` (desc, first-seen per
station = that station's most recent reading) plus the station-name pages - all memoized, so search is
one bounded burst of small GETs, not a loop. `--cc` is unused - the network is one country.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

BASE = "https://api.luchtmeetnet.nl/open_api"
FORMULA = "PM25"
UNHEALTHY = 25.0        # PM2.5 >= 25 ug/m3 ~ WHO 24h guideline = "unhealthy"
_MEAS_PAGES = 6         # newest ~150 rows -> each reporting station's most recent PM2.5


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build(number, value, ts, names):
    num = str(number)
    pm = _f(value)
    item = Item(num, name=safe(names.get(num, num)), subtitle="Luchtmeetnet PM2.5 (ug/m3)",
                category="NL station", extra={"station": num})
    obs = Obs(price_cents=(round(pm * 100) if pm is not None else None), qty=None,
              flags={"pm25": pm, "station": num, "location": safe(names.get(num, "")), "time": ts or ""})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._names = None
        self._latest = None      # {station_number: (value, timestamp)}

    def _get(self, path):
        r = self.s.get(f"{BASE}/{path}", headers={"User-Agent": UA, "Accept": "application/json"},
                       timeout=45)
        r.raise_for_status()
        return r.json() or {}

    def names(self):
        if self._names is None:
            first = self._get("stations?page=1")
            last = int(((first.get("pagination") or {}).get("last_page")) or 1)
            out = {}
            for pg in range(1, last + 1):
                data = (first if pg == 1 else self._get(f"stations?page={pg}")).get("data") or []
                for s in data:
                    out[str(s.get("number"))] = safe(s.get("location") or s.get("number") or "")
            self._names = out
        return self._names

    def latest(self):
        if self._latest is None:
            out = {}
            for pg in range(1, _MEAS_PAGES + 1):
                data = self._get(f"measurements?formula={FORMULA}"
                                 f"&order_by=timestamp_measured&order_direction=desc&page={pg}").get("data") or []
                if not data:
                    break
                for row in data:
                    sn = str(row.get("station_number") or "")
                    if sn and sn not in out:      # desc order: first-seen = that station's newest
                        out[sn] = (row.get("value"), row.get("timestamp_measured"))
            self._latest = out
        return self._latest

    def station_latest(self, number):
        data = self._get(f"measurements?formula={FORMULA}&station_number={number}"
                         f"&order_by=timestamp_measured&order_direction=desc&page=1").get("data") or []
        return (data[0].get("value"), data[0].get("timestamp_measured")) if data else (None, None)


class LuchtmeetnetSource(Source):
    name = "luchtmeetnet"
    id_label = "STATION"
    cc_default = "nl"           # unused; the network is one country
    deal_label = "unhealthy"    # PM2.5 >= 25 ug/m3
    search_limit_default = 25
    search_header = f"{'PM2.5':>6}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        latest = cl.latest()
        return bool(latest), f"({len(latest)} NL stations reporting PM2.5; keyless Luchtmeetnet open API)"

    def search(self, cl, term, args):
        names = cl.names()
        t = (term or "").strip().lower()
        out = []
        for num, (val, ts) in cl.latest().items():
            item, obs = _build(num, val, ts, names)
            if not t or t == num.lower() or t in safe(item.name).lower():
                out.append((item, obs))
        out.sort(key=lambda io: -((io[1].flags.get("pm25")) if io[1].flags.get("pm25") is not None else -1))
        return out

    def fetch(self, cl, item_id):
        val, ts = cl.station_latest(str(item_id))
        if val is None:
            return None
        return _build(str(item_id), val, ts, cl.names())

    def is_deal(self, obs):
        pm = obs.flags.get("pm25")
        return pm is not None and pm >= UNHEALTHY

    def deal_line(self, item, obs):
        f = obs.flags
        return f"PM2.5 {f.get('pm25')} ug/m3  {item.name}  ({item.id})  - unhealthy air"

    def search_row(self, item, obs):
        pm = obs.flags.get("pm25") if obs else None
        return f"{(pm if pm is not None else '-'):>6}  {item.name}  ({item.id})"

    def format_item(self, item, obs):
        lines = [f"  station  : {item.name}  ({item.id})"]
        if obs:
            f = obs.flags
            lines.append(f"  PM2.5    : {f.get('pm25')} ug/m3")
            lines.append(f"  observed : {f.get('time')}")
        return lines


SOURCE = LuchtmeetnetSource()
