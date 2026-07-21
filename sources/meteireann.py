"""meteireann - live Irish weather-station observations via Met Eireann's public API, keyless.

Met Eireann (the Irish national met service) exposes its station observations keyless at
`prodapi.metweb.ie/observations/<station>/today` - the day's hourly readings for a station (air
temperature, weather description + symbol, wind speed/gust/direction, humidity, 1-hour rainfall). The
prodapi host serves no robots.txt (404 = unfenced) and Met Eireann's data is published under CC-BY =
sanctioned -> trove. Opens **Ireland** and is the metno/ipma present-state twin over the north Atlantic
approaches.

The tracked scalar is the latest station temperature: `price_cents` = temperature in centi-degrees C
(so the core's `drops` = a station *cooling*); `qty` = relative humidity %. A "deal" ("wet") = the
latest reading has rainfall > 0 mm. Wind, gust, weather description and observation time ride in flags.
money() renders centi-degrees as '$' in the two hardcoded spots.

Model: one Item per station (join key = the station slug). Like the Hilltop river sources, `search`
fetches the requested stations live (one GET each, politely spaced) and `fetch` re-requests a single
station's board. `--cc` is unused.
"""
from __future__ import annotations

import time

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://prodapi.metweb.ie/observations"
STATIONS = {
    "dublin": "Dublin (Phoenix Park)", "cork": "Cork", "athenry": "Athenry", "shannon": "Shannon",
    "knock": "Knock", "casement": "Casement", "mullingar": "Mullingar", "gurteen": "Gurteen",
    "claremorris": "Claremorris", "belmullet": "Belmullet", "valentia": "Valentia", "roches-point": "Roches Point",
}


def _f(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _build(slug, label, latest):
    temp = _f(latest.get("temperature"))
    rh = _f(latest.get("humidity"))
    rain = _f(latest.get("rainfall"))
    item = Item(slug, name=safe(latest.get("name") or label), subtitle="Met Eireann observation", category="IE",
                extra={"station": label})
    obs = Obs(price_cents=(round(temp * 100) if temp is not None else None),
              qty=(round(rh) if rh is not None else None),
              flags={"temp_c": temp, "humidity": rh, "rain_mm": rain,
                     "weather": safe(latest.get("weatherDescription") or ""),
                     "wind_kt": _f(latest.get("windSpeed")), "wind_dir": safe(latest.get("cardinalWindDirection") or ""),
                     "gust": safe(latest.get("windGust") or ""), "measured": latest.get("reportTime") or latest.get("date") or ""})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._cache = {}

    def latest(self, slug):
        """The day's newest hourly observation for a station, or None."""
        if slug not in self._cache:
            try:
                r = self.s.get(f"{BASE}/{slug}/today", headers={"Accept": "application/json", "User-Agent": UA}, timeout=30)
                r.raise_for_status()
                rows = r.json() or []
                self._cache[slug] = rows[-1] if rows else None
            except Exception:
                self._cache[slug] = None
        return self._cache[slug]


class MetEireannSource(Source):
    name = "meteireann"
    id_label = "STATION"
    cc_default = "ie"        # unused
    deal_label = "wet"       # latest reading has rainfall > 0 mm
    search_limit_default = 12
    search_header = f"{'TEMP':>5}  {'RH%':>4}  {'RAIN':>5}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        latest = cl.latest("dublin")
        return latest is not None, f"({len(STATIONS)} IE stations; keyless Met Eireann prodapi)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        slugs = [s for s in STATIONS if not t or t in s or t in STATIONS[s].lower()]
        out = []
        for i, slug in enumerate(slugs[: args.limit]):
            latest = cl.latest(slug)
            if latest:
                out.append(_build(slug, STATIONS[slug], latest))
            if i + 1 < min(len(slugs), args.limit):
                time.sleep(0.3)
        out.sort(key=lambda io: -(io[1].price_cents if io[1].price_cents is not None else -10 ** 9))
        return out

    def fetch(self, cl, item_id):
        slug = str(item_id)
        latest = cl.latest(slug)
        return _build(slug, STATIONS.get(slug, slug), latest) if latest else None

    def is_deal(self, obs):
        r = obs.flags.get("rain_mm")
        return isinstance(r, (int, float)) and r > 0

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('rain_mm')}mm rain, {f.get('temp_c')}C  ({f.get('weather')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return (f"{(str(f.get('temp_c')) if f.get('temp_c') is not None else '?'):>5}  "
                f"{(str(round(f.get('humidity'))) if f.get('humidity') is not None else '?'):>4}  "
                f"{(str(f.get('rain_mm')) if f.get('rain_mm') is not None else '?'):>5}  {item.name}")

    def format_item(self, item, obs):
        lines = [f"  station  : {item.name}  ({item.id})"]
        if obs:
            f = obs.flags
            lines.append(f"  temp     : {f.get('temp_c')} C   humidity {f.get('humidity')}%")
            lines.append(f"  weather  : {f.get('weather')}")
            lines.append(f"  wind     : {f.get('wind_kt')} kt {f.get('wind_dir')}  gust {f.get('gust')}")
            lines.append(f"  rain     : {f.get('rain_mm')} mm   measured {f.get('measured')}")
        return lines


SOURCE = MetEireannSource()
