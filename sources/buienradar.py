"""buienradar - live Dutch weather-station observations via Buienradar's open feed, keyless.

Buienradar (a Netherlands weather service) publishes its national station network as a keyless JSON
feed `data.buienradar.nl/2.0/feed/json`: ~40 stations, each with temperature, feels-like and ground
temperature, wind speed/gusts/direction, air pressure, visibility and a weather description. The feed's
own terms explicitly permit free reuse with attribution, and robots.txt is 404 (unfenced) =
sanctioned -> trove. Opens **Netherlands** weather (pairing with `luchtmeetnet` air quality) and is the
metno/ipma present-state twin over the low countries.

The tracked scalar is the live station temperature: `price_cents` = temperature in centi-degrees C (so
the core's `drops` = a station *cooling*); `qty` = wind speed (m/s, rounded). A "deal" ("rain") = the
station's weather description indicates precipitation (a Dutch "regen"/"bui" shower/rain term). Wind
gusts, pressure, feels-like and visibility ride in flags. money() renders centi-degrees as '$'.

Model: one Item per station (join key = `stationid`). One memoized GET serves a whole pass; `search
<term>` filters by station/region name, `fetch` scans the board. `--cc` is unused (one NL network).
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://data.buienradar.nl/2.0/feed/json"
RAIN_WORDS = ("regen", "bui", "buien", "motregen", "hagel")


def _f(v):
    return float(v) if isinstance(v, (int, float)) else None


def _is_rain(desc):
    d = (desc or "").lower()
    return any(w in d for w in RAIN_WORDS)


def _build(st):
    sid = str(st.get("stationid"))
    temp = _f(st.get("temperature"))
    wind = _f(st.get("windspeed"))
    desc = safe(st.get("weatherdescription") or "")
    item = Item(sid, name=safe(st.get("stationname") or st.get("regio") or sid),
                subtitle=safe(st.get("regio") or ""), category="NL",
                extra={"regio": safe(st.get("regio") or ""), "lat": _f(st.get("lat")), "lon": _f(st.get("lon"))})
    obs = Obs(price_cents=(round(temp * 100) if temp is not None else None),
              qty=(round(wind) if wind is not None else None),
              flags={"temp_c": temp, "feels_c": _f(st.get("feeltemperature")),
                     "ground_c": _f(st.get("groundtemperature")), "wind_ms": wind,
                     "gust_ms": _f(st.get("windgusts")), "pressure_hpa": _f(st.get("airpressure")),
                     "visibility_m": _f(st.get("visibility")), "weather": desc,
                     "is_rain": _is_rain(desc), "measured": st.get("timestamp") or ""})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._stations = None

    def stations(self):
        if self._stations is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._stations = ((r.json() or {}).get("actual") or {}).get("stationmeasurements") or []
        return self._stations


class BuienradarSource(Source):
    name = "buienradar"
    id_label = "STATION"
    cc_default = "nl"        # unused
    deal_label = "rain"      # weather description indicates precipitation
    search_limit_default = 30
    search_header = f"{'TEMP':>5}  {'WIND':>4}  {'WEATHER':<24}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        st = cl.stations()
        return bool(st), f"({len(st)} NL weather stations; keyless Buienradar feed)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for st in cl.stations():
            item, obs = _build(st)
            if not t or t in safe(item.name).lower() or t in safe(item.extra.get("regio")).lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents if io[1].price_cents is not None else -10 ** 9))
        return out

    def fetch(self, cl, item_id):
        for st in cl.stations():
            if str(st.get("stationid")) == str(item_id):
                return _build(st)
        return None

    def is_deal(self, obs):
        return bool(obs.flags.get("is_rain"))

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('weather')}  {f.get('temp_c')}C, wind {f.get('wind_ms')} m/s"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return (f"{(str(f.get('temp_c')) if f.get('temp_c') is not None else '?'):>5}  "
                f"{(str(round(f.get('wind_ms'))) if f.get('wind_ms') is not None else '?'):>4}  "
                f"{safe(f.get('weather') or '?')[:24]:<24}  {item.name}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  station  : {item.name}  ({e.get('regio') or '?'})   [{e.get('lat')}, {e.get('lon')}]"]
        if obs:
            f = obs.flags
            lines.append(f"  temp     : {f.get('temp_c')} C  (feels {f.get('feels_c')}, ground {f.get('ground_c')})")
            lines.append(f"  weather  : {f.get('weather')}")
            lines.append(f"  wind     : {f.get('wind_ms')} m/s  gusts {f.get('gust_ms')}   pressure {f.get('pressure_hpa')} hPa")
            lines.append(f"  measured : {f.get('measured')}")
        return lines


SOURCE = BuienradarSource()
