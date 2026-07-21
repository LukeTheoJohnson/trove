"""jmaweather - Japanese city weather forecast via the JMA open forecast JSON, keyless.

The Japan Meteorological Agency publishes its forecasts as keyless JSON at
`www.jma.go.jp/bosai/forecast/data/forecast/<office>.json` - per prefecture office, the weather code,
rain probability (pops) and temperature series. robots.txt is 404 (unfenced) and it is official open
data = sanctioned -> trove. Opens **Japan** and is the metno/ipma/hkweather present-forecast twin over
East Asia. The JMA *weather codes* are numeric (language-independent), so the display is fully English
even though the underlying text is Japanese; `--cc` maps a city slug to an office code + an English
label, sidestepping the cp1252 console's inability to render kanji.

The timeline value is the forecast as issued (JMA archives realized weather, not the forecast series).
`price_cents` = the forecast **max temp in centi-degrees C** (so the core's `drops` = a forecast
*cooling*); `qty` = the max rain-probability %. A "deal" ("rain") = a rain-type weather code (3xx) or
rain probability >= 50%. money() renders centi-degrees as '$' in the two hardcoded spots.

Model: one Item per city office (join key = the office code). `--cc` picks the city (default `tokyo`;
also osaka, nagoya, sapporo, fukuoka, sendai, hiroshima, naha, kyoto). One memoized GET per pass.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://www.jma.go.jp/bosai/forecast/data/forecast"
# city slug -> (office code, English label)
CITIES = {
    "tokyo": ("130000", "Tokyo"), "osaka": ("270000", "Osaka"), "nagoya": ("230000", "Nagoya"),
    "sapporo": ("016000", "Sapporo"), "fukuoka": ("400000", "Fukuoka"), "sendai": ("040000", "Sendai"),
    "hiroshima": ("340000", "Hiroshima"), "naha": ("471000", "Naha (Okinawa)"), "kyoto": ("260000", "Kyoto"),
}
SKY = {1: "Sunny/Clear", 2: "Cloudy", 3: "Rain", 4: "Snow"}


def _num(v):
    try:
        return round(float(v))
    except (TypeError, ValueError):
        return None


def _maxnum(seq):
    vals = [n for n in (_num(v) for v in (seq or [])) if n is not None]
    return max(vals) if vals else None


def _minnum(seq):
    vals = [n for n in (_num(v) for v in (seq or [])) if n is not None]
    return min(vals) if vals else None


def _sky(code):
    try:
        return SKY.get(int(code) // 100, f"code {code}")
    except (TypeError, ValueError):
        return "?"


def _build(office, label, doc):
    series = (doc[0].get("timeSeries") if doc else None) or []
    ts_w = series[0] if len(series) > 0 else {"areas": [{}], "timeDefines": [""]}
    ts_p = series[1] if len(series) > 1 else {"areas": [{}]}
    ts_t = series[2] if len(series) > 2 else {"areas": [{}]}
    aw = (ts_w.get("areas") or [{}])[0]
    code = (aw.get("weatherCodes") or [None])[0]
    pops = (ts_p.get("areas") or [{}])[0].get("pops")
    temps = (ts_t.get("areas") or [{}])[0].get("temps")
    tmax = _maxnum(temps)
    pop = _maxnum(pops)
    is_rain = (isinstance(code, str) and code[:1] == "3") or (pop is not None and pop >= 50)
    item = Item(office, name=label, subtitle="JMA next-day forecast", category="JP",
                extra={"office": office, "report_time": (ts_w.get("timeDefines") or [""])[0]})
    obs = Obs(price_cents=(tmax * 100 if tmax is not None else None), qty=pop,
              flags={"max_c": tmax, "min_c": _minnum(temps), "rain_prob": pop,
                     "weather": _sky(code), "weather_code": code, "is_rain": is_rain})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.cc = cc if cc in CITIES else "tokyo"
        self.office, self.label = CITIES[self.cc]
        self.s = retry_session()
        self._doc = None

    def doc(self):
        if self._doc is None:
            r = self.s.get(f"{BASE}/{self.office}.json",
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._doc = r.json() or []
        return self._doc


class JmaWeatherSource(Source):
    name = "jmaweather"
    id_label = "OFFICE"
    cc_default = "tokyo"     # city slug: tokyo|osaka|nagoya|sapporo|fukuoka|sendai|hiroshima|naha|kyoto
    deal_label = "rain"      # rain-type code or rain probability >= 50%
    search_header = f"{'MAX':>4}  {'MIN':>4}  {'RAIN%':>5}  CITY"

    def client(self, args):
        return _Client(getattr(args, "cc", "tokyo"))

    def doctor(self, cl):
        doc = cl.doc()
        return bool(doc), f"(JMA forecast for {cl.label}; keyless open forecast JSON)"

    def search(self, cl, term, args):
        item, obs = _build(cl.office, cl.label, cl.doc())
        t = (term or "").lower()
        return [(item, obs)] if (not t or t in cl.label.lower()) else []

    def fetch(self, cl, item_id):
        return _build(cl.office, cl.label, cl.doc())

    def is_deal(self, obs):
        return bool(obs.flags.get("is_rain"))

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('weather')}, {f.get('rain_prob')}% rain, {f.get('max_c')}C"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return (f"{(str(f.get('max_c')) if f.get('max_c') is not None else '?'):>4}  "
                f"{(str(f.get('min_c')) if f.get('min_c') is not None else '?'):>4}  "
                f"{(str(f.get('rain_prob')) if f.get('rain_prob') is not None else '?'):>5}  {item.name}")

    def format_item(self, item, obs):
        lines = [f"  city     : {item.name}  (office {item.extra.get('office')})"]
        if obs:
            f = obs.flags
            lines.append(f"  weather  : {f.get('weather')}  (JMA code {f.get('weather_code')})")
            lines.append(f"  temp     : {f.get('min_c')} - {f.get('max_c')} C   rain prob {f.get('rain_prob')}%")
            lines.append(f"  issued   : {item.extra.get('report_time') or '?'}")
        return lines


SOURCE = JmaWeatherSource()
