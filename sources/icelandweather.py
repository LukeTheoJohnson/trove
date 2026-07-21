"""icelandweather - live Icelandic weather-station observations via Vedurstofan (IMO), keyless XML.

The Icelandic Met Office (Vedurstofa Islands) publishes station observations as a keyless XML feed
`xmlweather.vedur.is/?op_w=xml&type=obs&lang=en&ids=<ids>`: for each requested station, the current
temperature (T), wind speed (F) + gust (FG) + direction (D), and 1-hour precipitation (R). robots.txt
is 404 (unfenced) and it is an official public feed = sanctioned -> trove. Opens **Iceland** and is the
metno/ipma present-state twin over the north Atlantic (a place where the weather genuinely matters).

The tracked scalar is the live station temperature: `price_cents` = temperature in centi-degrees C (so
the core's `drops` = a station *cooling*); `qty` = wind speed (m/s, rounded). A "deal" ("wet") = the
station is recording precipitation (R > 0 mm) - rain/sleet at that gauge now. Gust, direction and
observation time ride in flags. money() renders centi-degrees as '$' in the two hardcoded spots.

Model: one Item per station (join key = the station id). A single memoized GET returns the whole
requested set; `search <term>` filters by station name, `fetch` scans it. `--cc` is unused.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://xmlweather.vedur.is/"
# a spread of Icelandic synoptic stations (Reykjavik, Akureyri, Egilsstadir, Keflavik, coasts, highlands)
STATION_IDS = "1;422;571;2738;178;990;1352;620;6015;2481;1483;3471;31572;54"


def _f(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _txt(el, tag):
    c = el.find(tag)
    return (c.text or "").strip() if c is not None and c.text else ""


def _build(st):
    sid = st.get("id")
    temp = _f(_txt(st, "T"))
    wind = _f(_txt(st, "F"))
    rain = _f(_txt(st, "R"))
    item = Item(str(sid), name=safe(_txt(st, "name") or sid), subtitle="Vedurstofan observation", category="IS",
                extra={"link": _txt(st, "link")})
    obs = Obs(price_cents=(round(temp * 100) if temp is not None else None),
              qty=(round(wind) if wind is not None else None),
              flags={"temp_c": temp, "wind_ms": wind, "gust_ms": _f(_txt(st, "FX")) or _f(_txt(st, "FG")),
                     "wind_dir": safe(_txt(st, "D")), "rain_mm": rain, "measured": _txt(st, "time")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._stations = None

    def stations(self):
        if self._stations is None:
            r = self.s.get(BASE, params={"op_w": "xml", "type": "obs", "lang": "en",
                                         "view": "xml", "ids": STATION_IDS},
                           headers={"User-Agent": UA}, timeout=40)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            self._stations = [st for st in root.iter("station")]
        return self._stations


class IcelandWeatherSource(Source):
    name = "icelandweather"
    id_label = "STATION"
    cc_default = "is"        # unused
    deal_label = "wet"       # station recording precipitation (R > 0)
    search_limit_default = 20
    search_header = f"{'TEMP':>5}  {'WIND':>4}  {'RAIN':>5}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        st = cl.stations()
        return bool(st), f"({len(st)} IS stations; keyless Vedurstofan xmlweather)"

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
            if str(st.get("id")) == str(item_id):
                return _build(st)
        return None

    def is_deal(self, obs):
        r = obs.flags.get("rain_mm")
        return isinstance(r, (int, float)) and r > 0

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('rain_mm')}mm rain, {f.get('temp_c')}C, wind {f.get('wind_ms')} m/s"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return (f"{(str(f.get('temp_c')) if f.get('temp_c') is not None else '?'):>5}  "
                f"{(str(round(f.get('wind_ms'))) if f.get('wind_ms') is not None else '?'):>4}  "
                f"{(str(f.get('rain_mm')) if f.get('rain_mm') is not None else '?'):>5}  {item.name}")

    def format_item(self, item, obs):
        lines = [f"  station  : {item.name}  ({item.id})"]
        if obs:
            f = obs.flags
            lines.append(f"  temp     : {f.get('temp_c')} C")
            lines.append(f"  wind     : {f.get('wind_ms')} m/s  gust {f.get('gust_ms')}  dir {f.get('wind_dir')}")
            lines.append(f"  rain     : {f.get('rain_mm')} mm   measured {f.get('measured')}")
        return lines


SOURCE = IcelandWeatherSource()
