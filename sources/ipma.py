"""ipma - Portuguese city weather forecast (next day) via IPMA open data, keyless.

IPMA (Instituto Portugues do Mar e da Atmosfera) publishes Portugal's official forecasts as keyless
open data: `api.ipma.pt/open-data/forecast/meteorology/cities/daily/hp-daily-forecast-day1.json` is
tomorrow's forecast for each district capital + islands (max/min temp, precipitation probability, wind
direction/class, weather type). robots.txt is 404 (unfenced) and it's published for reuse = sanctioned
-> trove. The EU/Iberian forecast-drift twin of `metno` (and `spainfuel`'s weather-side neighbour).

The timeline value is the forecast as issued: IPMA archives realized weather, not the forecast series,
so tracking tomorrow's max-temp forecast per city (and its revision as tomorrow approaches) is
un-rebuildable. `price_cents` = the forecast **max temp in centi-degrees C** (so the core's `drops` = a
forecast *cooling*); `qty` = the precipitation probability %. A "deal" ("rain") = precipitation
probability >= 70% (a wet-day forecast). Min temp, weather type, wind dir/class ride in flags.

Model: one Item per location (join key = IPMA `globalIdLocal`; names resolved from the memoized
`distrits-islands` list); one pass is two memoized GETs. `search <term>` filters by city name (pass ""
to list them); `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FORECAST = "https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/hp-daily-forecast-day1.json"
LOCATIONS = "https://api.ipma.pt/open-data/distrits-islands.json"
RAIN_DEAL = 70   # precipitation probability % that counts as a wet-day forecast
WEATHER_TYPES = {
    0: "No info", 1: "Clear", 2: "Partly cloudy", 3: "Sunny intervals", 4: "Cloudy", 5: "Cloudy (high)",
    6: "Showers/rain", 7: "Light showers", 8: "Heavy showers", 9: "Rain/showers", 10: "Light rain",
    11: "Heavy rain", 12: "Intermittent rain", 13: "Intermittent light rain", 14: "Intermittent heavy rain",
    15: "Drizzle", 16: "Mist", 17: "Fog", 18: "Snow", 19: "Thunderstorms", 20: "Showers + storms",
    21: "Hail", 22: "Frost", 23: "Rain + storms", 24: "Convective clouds", 25: "Partly cloudy", 27: "Cloudy",
}


def _num(v):
    try:
        return round(float(v))
    except (TypeError, ValueError):
        return None


def _build(rec, names, fdate):
    gid = str(rec.get("globalIdLocal"))
    tmax = _num(rec.get("tMax"))
    prob = _num(rec.get("precipitaProb"))
    wt = rec.get("idWeatherType")
    item = Item(gid, name=safe(names.get(gid, gid)), subtitle="IPMA next-day forecast", category="PT",
                extra={"lat": rec.get("latitude"), "lon": rec.get("longitude"), "forecast_date": fdate})
    obs = Obs(price_cents=(tmax * 100 if tmax is not None else None), qty=prob,
              flags={"max_c": tmax, "min_c": _num(rec.get("tMin")), "rain_prob": prob,
                     "weather": WEATHER_TYPES.get(wt, f"type {wt}"), "wind_dir": safe(rec.get("predWindDir") or ""),
                     "wind_class": rec.get("classWindSpeed"), "forecast_date": fdate})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._fc = None
        self._names = None

    def _get(self, url):
        r = self.s.get(url, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or {}

    def names(self):
        if self._names is None:
            self._names = {str(d.get("globalIdLocal")): d.get("local")
                           for d in (self._get(LOCATIONS).get("data") or [])}
        return self._names

    def forecast(self):
        if self._fc is None:
            self._fc = self._get(FORECAST)
        return self._fc


class IpmaSource(Source):
    name = "ipma"
    id_label = "LOCAL"
    cc_default = "pt"        # unused
    deal_label = "rain"      # precipitation probability >= 70%
    search_limit_default = 30
    search_header = f"{'MAX':>4}  {'MIN':>4}  {'RAIN%':>5}  CITY"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        fc = cl.forecast()
        data = fc.get("data") or []
        return bool(data), f"({len(data)} PT locations, forecast {fc.get('forecastDate', '?')}; keyless IPMA open-data)"

    def search(self, cl, term, args):
        fc = cl.forecast()
        names = cl.names()
        fdate = fc.get("forecastDate", "")
        t = (term or "").lower()
        out = []
        for rec in (fc.get("data") or []):
            item, obs = _build(rec, names, fdate)
            if not t or t in safe(item.name).lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        fc = cl.forecast()
        names = cl.names()
        fdate = fc.get("forecastDate", "")
        for rec in (fc.get("data") or []):
            if str(rec.get("globalIdLocal")) == str(item_id):
                return _build(rec, names, fdate)
        return None

    def is_deal(self, obs):
        p = obs.flags.get("rain_prob")
        return isinstance(p, int) and p >= RAIN_DEAL

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('rain_prob')}% rain, {f.get('max_c')}C  {item.name}  ({f.get('weather')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return (f"{(str(f.get('max_c')) if f.get('max_c') is not None else '?'):>4}  "
                f"{(str(f.get('min_c')) if f.get('min_c') is not None else '?'):>4}  "
                f"{(str(f.get('rain_prob')) if f.get('rain_prob') is not None else '?'):>5}  {item.name}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  city     : {item.name}   [{e.get('lat')}, {e.get('lon')}]"]
        if obs:
            f = obs.flags
            lines.append(f"  forecast : {e.get('forecast_date', '?')}  (as issued)")
            lines.append(f"  temp     : {f.get('min_c')} - {f.get('max_c')} C")
            lines.append(f"  weather  : {f.get('weather')}   rain prob {f.get('rain_prob')}%")
            lines.append(f"  wind     : {f.get('wind_dir') or '?'}  (class {f.get('wind_class')})")
        return lines


SOURCE = IpmaSource()
