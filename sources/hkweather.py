"""hkweather - Hong Kong Observatory 9-day weather forecast + active warnings, keyless.

The Hong Kong Observatory publishes its open weather data through a keyless endpoint,
`data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=<t>&lang=en`: `fnd` is the 9-day
forecast (per-day max/min temp, wind, weather text, probability of significant rain) and `warnsum` is
the current warning summary (the typhoon/rainstorm signals). robots fences only `/aviat/,/cis/,...` -
never `/weatherAPI/opendata/` - and the feed is published for reuse = sanctioned -> trove. **Opens
Asia** for trove, and is a forecast-drift twin of `metno`.

The timeline value is the forecast *as issued* and its revision: HKO archives realized weather but not
the past forecast series, so tracking each day's max-temp forecast (and how it drifts as the day
approaches) is un-rebuildable. `price_cents` = the day's **forecast max temp in centi-degrees C** (30C
-> 3000), so the core's `drops` = a forecast *cooling*; `qty` = the forecast min temp. A "deal" ("hot")
= forecast max >= 33 C (HK's very-hot-weather threshold) **or** any HKO warning currently in force. The
weather text, wind, rain probability and the live warning list ride in flags.

Model: one Item per forecast day (join key = the `YYYYMMDD` forecast date, the metno/spaceweather
pattern); one pass is two memoized GETs (forecast + warnings). `search <term>` filters the 9 days by
date/weekday (pass "" to list them); `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
HOT_C = 33    # HK "very hot weather" threshold


def _val(d):
    v = (d or {}).get("value")
    return v if isinstance(v, (int, float)) else None


def _fmt_date(ymd):
    s = str(ymd or "")
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else s


def _build(day, warnings):
    ymd = str(day.get("forecastDate") or "")
    mx = _val(day.get("forecastMaxtemp"))
    mn = _val(day.get("forecastMintemp"))
    week = safe(day.get("week") or "")
    item = Item(ymd, name=f"{_fmt_date(ymd)} ({week})", subtitle="HKO 9-day forecast", category="forecast",
                extra={"date": _fmt_date(ymd), "week": week})
    obs = Obs(price_cents=(round(mx * 100) if mx is not None else None), qty=mn,
              flags={"max_c": mx, "min_c": mn, "weather": safe(day.get("forecastWeather") or ""),
                     "wind": safe(day.get("forecastWind") or ""), "psr": safe(day.get("PSR") or ""),
                     "max_rh": _val(day.get("forecastMaxrh")), "min_rh": _val(day.get("forecastMinrh")),
                     "week": week, "warnings": warnings})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._fc = None
        self._warn = None

    def _get(self, dt):
        r = self.s.get(BASE, params={"dataType": dt, "lang": "en"},
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or {}

    def forecast(self):
        if self._fc is None:
            self._fc = self._get("fnd").get("weatherForecast") or []
        return self._fc

    def warnings(self):
        """List of the descriptions of any warnings currently in force ([] when quiet)."""
        if self._warn is None:
            w = self._get("warnsum") or {}
            self._warn = ", ".join(safe((v or {}).get("name") or k) for k, v in w.items() if v)
        return self._warn


class HkWeatherSource(Source):
    name = "hkweather"
    id_label = "DATE"
    cc_default = "hk"        # unused
    deal_label = "hot"       # forecast max >= 33 C, or a warning in force
    search_limit_default = 9
    search_header = f"{'MAX':>4}  {'MIN':>4}  DATE                WEATHER"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        fc = cl.forecast()
        w = cl.warnings()
        tail = f"; warnings: {w}" if w else "; no warnings"
        return bool(fc), f"({len(fc)}-day HK forecast{tail}; keyless HKO opendata)"

    def search(self, cl, term, args):
        w = cl.warnings()
        t = (term or "").lower()
        out = []
        for day in cl.forecast():
            item, obs = _build(day, w)
            if not t or t in item.name.lower():
                out.append((item, obs))
        return out

    def fetch(self, cl, item_id):
        w = cl.warnings()
        for day in cl.forecast():
            if str(day.get("forecastDate") or "") == str(item_id):
                return _build(day, w)
        return None

    def is_deal(self, obs):
        mx = obs.flags.get("max_c")
        return (isinstance(mx, (int, float)) and mx >= HOT_C) or bool(obs.flags.get("warnings"))

    def deal_line(self, item, obs):
        f = obs.flags
        w = f"  [WARNING: {f.get('warnings')}]" if f.get("warnings") else ""
        return f"{f.get('max_c')}C max  {item.name}  {f.get('weather') or ''}"[:90] + w

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return (f"{(str(f.get('max_c')) if f.get('max_c') is not None else '?'):>4}  "
                f"{(str(f.get('min_c')) if f.get('min_c') is not None else '?'):>4}  "
                f"{item.name:<18}  {(f.get('weather') or '')[:34]}")

    def format_item(self, item, obs):
        lines = [f"  date     : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  temp     : {f.get('min_c')} - {f.get('max_c')} C   humidity {f.get('min_rh')} - {f.get('max_rh')}%")
            lines.append(f"  weather  : {f.get('weather') or '?'}")
            lines.append(f"  wind     : {f.get('wind') or '?'}")
            lines.append(f"  rain prob: {f.get('psr') or '?'}")
            if f.get("warnings"):
                lines.append(f"  WARNINGS : {f.get('warnings')}")
        return lines


SOURCE = HkWeatherSource()
