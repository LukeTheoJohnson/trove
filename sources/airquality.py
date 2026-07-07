"""airquality - live citizen air-quality sensors (PM2.5 / PM10) via keyless Sensor.Community.

Sensor.Community (formerly luftdaten.info) runs a global network of low-cost citizen air-quality
sensors and publishes every sensor's latest reading through a keyless open API
(`data.sensor.community`; robots 404 = nothing fenced; an open-data citizen-science project built for
reuse = sanctioned -> trove). Opens the **air-quality domain** (roadmap Axis A white space) - fine
particulate right now, per sensor, filling a gap no existing genre covered.

The tracked value is **PM2.5** (particulate <=2.5 micrometres, `value_type` P2), the health-relevant
pollutant, in micrograms/m3. `price_cents` = PM2.5 * 100 (centi-microgram), so the core's `drops` =
the air *cleaning*; `is_deal` ("unhealthy") = PM2.5 >= 25 ug/m3 (around the WHO 24h guideline - a poor
-air moment). `qty` = PM10 (coarser particulate, `value_type` P1). Honest hoard value low-med:
Sensor.Community archives its own history (rebuildable), and the sensors are noisy citizen hardware -
the draw is opening the domain + the live pollution signal, not un-rebuildability.

`/airrohr/v1/filter/area=<lat>,<lon>,<km>` returns every recent reading in a radius (one memoized GET
per area); `/airrohr/v1/sensor/<id>/` returns one sensor's recent rows (the by-id fetch). A reading
carries `sensor.id` (the join key), `location` (lat/lon/country) and `sensordatavalues` (a list of
`{value_type, value}` - P1/P2 for a dust sensor). `--cc` picks a curated city/area (default stuttgart,
the network's densest); `search <term>` lists that area's PM sensors (worst air first), filtering by
sensor id or country; `item`/`poll` fetch one sensor by id. Only sensors reporting P1/P2 are kept
(temperature/humidity-only nodes are skipped).
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

BASE = "https://data.sensor.community/airrohr/v1"
UNHEALTHY = 25.0        # PM2.5 >= 25 ug/m3 ~ WHO 24h guideline = "unhealthy"
# curated areas: cc -> (lat, lon, radius_km). Europe is dense; AU/NZ sparse but real.
AREAS = {
    "stuttgart": (48.77, 9.18, 4), "berlin": (52.52, 13.40, 6), "hamburg": (53.55, 10.00, 6),
    "london": (51.51, -0.13, 8), "paris": (48.86, 2.35, 8), "losangeles": (34.05, -118.24, 12),
    "delhi": (28.61, 77.21, 12), "sydney": (-33.87, 151.21, 15), "melbourne": (-37.81, 144.96, 15),
    "auckland": (-36.85, 174.76, 20), "christchurch": (-43.53, 172.64, 20),
}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _vals(reading):
    """sensordatavalues -> {value_type: float}."""
    out = {}
    for v in reading.get("sensordatavalues") or []:
        f = _f(v.get("value"))
        if f is not None:
            out[v.get("value_type")] = f
    return out


def _build(reading):
    """One Sensor.Community reading -> (Item, Obs). None if it carries no PM (P1/P2)."""
    vals = _vals(reading)
    pm25 = vals.get("P2")
    pm10 = vals.get("P1")
    if pm25 is None and pm10 is None:
        return None
    sensor = reading.get("sensor") or {}
    sid = str(sensor.get("id") or "")
    stype = ((sensor.get("sensor_type") or {}).get("name")) or ""
    loc = reading.get("location") or {}
    country = loc.get("country") or ""
    lat, lon = loc.get("latitude"), loc.get("longitude")
    headline = pm25 if pm25 is not None else pm10
    item = Item(sid, name=f"sensor {sid}  ({country} {lat},{lon})",
                category=safe(stype or "PM sensor"),
                subtitle=safe(f"PM2.5 {pm25 if pm25 is not None else '?'}  PM10 "
                              f"{pm10 if pm10 is not None else '?'} ug/m3"),
                extra={"sensor_type": safe(stype), "country": country, "lat": lat, "lon": lon,
                       "url": f"https://maps.sensor.community/#14/{lat}/{lon}"})
    obs = Obs(price_cents=round(headline * 100),
              qty=(round(pm10) if pm10 is not None else None),
              flags={"pm25": pm25, "pm10": pm10, "sensor_type": safe(stype), "country": country,
                     "time": reading.get("timestamp") or "",
                     "temperature": vals.get("temperature"), "humidity": vals.get("humidity")})
    return item, obs


def _latest_per_sensor(readings):
    """Keep the freshest reading per sensor id (readings are time-ordered ascending)."""
    by = {}
    for r in readings or []:
        sid = str((r.get("sensor") or {}).get("id") or "")
        if sid:
            by[sid] = r          # later row = newer, overwrites
    return by


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._area = {}

    def _get(self, path):
        r = self.s.get(f"{BASE}/{path}", headers={"User-Agent": UA, "Accept": "application/json"},
                       timeout=45)
        r.raise_for_status()
        return r.json() or []

    def area(self, cc):
        cc = (cc or "stuttgart").lower()
        if cc not in self._area:
            lat, lon, km = AREAS.get(cc, AREAS["stuttgart"])
            self._area[cc] = _latest_per_sensor(self._get(f"filter/area={lat},{lon},{km}"))
        return self._area[cc]

    def sensor(self, sid):
        rows = self._get(f"sensor/{sid}/")
        return rows[-1] if rows else None


class AirQualitySource(Source):
    name = "airquality"
    id_label = "SENSOR"
    cc_default = "stuttgart"    # curated area (see AREAS)
    deal_label = "unhealthy"    # PM2.5 >= 25 ug/m3
    search_limit_default = 25
    search_header = f"{'PM2.5':>6}  {'PM10':>6}  SENSOR"

    def _cc(self, args):
        cc = (getattr(args, "cc", None) or self.cc_default).lower()
        return cc if cc in AREAS else self.cc_default

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        by = cl.area(self.cc_default)
        pm = sum(1 for r in by.values() if _vals(r).get("P2") is not None or _vals(r).get("P1") is not None)
        return bool(by), f"({pm} PM sensors near {self.cc_default}; keyless Sensor.Community API)"

    def search(self, cl, term, args):
        cc = self._cc(args)
        t = (term or "").strip().lower()
        rows = []
        for r in cl.area(cc).values():
            built = _build(r)
            if not built:
                continue
            item, obs = built
            if not t or t == str(item.id) or t in (obs.flags.get("country") or "").lower():
                rows.append((item, obs))
        rows.sort(key=lambda io: -((io[1].flags.get("pm25") if io[1].flags.get("pm25") is not None
                                    else io[1].flags.get("pm10")) or 0))
        return rows

    def fetch(self, cl, item_id):
        r = cl.sensor(str(item_id))
        return _build(r) if r else None

    def is_deal(self, obs):
        pm = obs.flags.get("pm25")
        return pm is not None and pm >= UNHEALTHY

    def deal_line(self, item, obs):
        f = obs.flags
        return f"PM2.5 {f.get('pm25')} ug/m3  sensor {item.id}  ({f.get('country')})  - unhealthy air"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        pm25 = f.get("pm25")
        pm10 = f.get("pm10")
        return (f"{(pm25 if pm25 is not None else '-'):>6}  {(pm10 if pm10 is not None else '-'):>6}  "
                f"{item.name[:56]}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  sensor   : {item.id}  ({e.get('sensor_type', '')})",
                 f"  location : {e.get('country', '')}  {e.get('lat')}, {e.get('lon')}"]
        if obs:
            f = obs.flags
            lines.append(f"  PM2.5    : {f.get('pm25')} ug/m3   PM10 {f.get('pm10')} ug/m3")
            if f.get("temperature") is not None or f.get("humidity") is not None:
                lines.append(f"  weather  : {f.get('temperature')}C  {f.get('humidity')}% RH")
            lines.append(f"  observed : {f.get('time')}")
        lines.append(f"  map      : {e.get('url', '')}")
        return lines


SOURCE = AirQualitySource()
