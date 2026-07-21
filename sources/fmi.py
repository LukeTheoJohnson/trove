"""fmi - live Finnish weather-station observations via the FMI Open Data WFS, keyless.

The Finnish Meteorological Institute publishes station observations through a keyless WFS
`opendata.fmi.fi/wfs` (stored query `fmi::observations::weather::simple`): for a named place it returns
a time series of air temperature (t2m), 10-minute wind speed (ws_10min) and relative humidity (rh).
robots.txt is 404 (unfenced) and the data is CC-BY open data = sanctioned -> trove. Opens **Finland**
and is the metno/ipma/smhi present-state twin over the far north.

The tracked scalar is the live temperature: `price_cents` = the latest t2m in centi-degrees C (so the
core's `drops` = a *cooling*); `qty` = wind speed (m/s, rounded). A "deal" ("warm") = the latest
temperature is at or above 25 C (a notable warm reading at Finnish latitudes). Humidity and the
observation time ride in flags. money() renders centi-degrees as '$' in the two hardcoded spots.

Model: one Item per city (join key = the city slug). `--cc` picks the city (default `helsinki`; also
tampere, turku, oulu, rovaniemi, jyvaskyla, kuopio). One memoized GET (the latest timestamp in the
returned series) serves the pass.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://opendata.fmi.fi/wfs"
CITIES = {"helsinki": "Helsinki", "tampere": "Tampere", "turku": "Turku", "oulu": "Oulu",
          "rovaniemi": "Rovaniemi", "jyvaskyla": "Jyvaskyla", "kuopio": "Kuopio"}
WARM = 25.0


def _f(v):
    try:
        x = float(v)
        return x if x == x else None       # drop NaN
    except (TypeError, ValueError):
        return None


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _latest_params(xml_bytes):
    """Parse the WFS simple response -> the newest timestamp's {parameter: value}."""
    root = ET.fromstring(xml_bytes)
    by_time = {}
    for el in root.iter():
        if _local(el.tag) != "BsWfsElement":
            continue
        t = name = val = None
        for child in el:
            lt = _local(child.tag)
            if lt == "Time":
                t = (child.text or "").strip()
            elif lt == "ParameterName":
                name = (child.text or "").strip()
            elif lt == "ParameterValue":
                val = (child.text or "").strip()
        if t and name:
            by_time.setdefault(t, {})[name] = val
    if not by_time:
        return "", {}
    latest = max(by_time)
    return latest, by_time[latest]


def _build(cc, label, latest, params):
    temp = _f(params.get("t2m"))
    wind = _f(params.get("ws_10min"))
    rh = _f(params.get("rh"))
    item = Item(cc, name=label, subtitle="FMI observation", category="FI", extra={"place": label})
    obs = Obs(price_cents=(round(temp * 100) if temp is not None else None),
              qty=(round(wind) if wind is not None else None),
              flags={"temp_c": temp, "wind_ms": wind, "humidity": rh, "measured": latest})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.cc = cc if cc in CITIES else "helsinki"
        self.label = CITIES[self.cc]
        self.s = retry_session()
        self._parsed = None

    def obs(self):
        if self._parsed is None:
            r = self.s.get(BASE, params={"service": "WFS", "version": "2.0.0", "request": "getFeature",
                                         "storedquery_id": "fmi::observations::weather::simple",
                                         "place": self.label, "parameters": "t2m,ws_10min,rh",
                                         "maxlocations": 1},
                           headers={"User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._parsed = _latest_params(r.content)
        return self._parsed


class FmiSource(Source):
    name = "fmi"
    id_label = "CITY"
    cc_default = "helsinki"  # city slug: helsinki|tampere|turku|oulu|rovaniemi|jyvaskyla|kuopio
    deal_label = "warm"      # latest temperature >= 25 C
    search_header = f"{'TEMP':>5}  {'WIND':>4}  {'RH%':>4}  CITY"

    def client(self, args):
        return _Client(getattr(args, "cc", "helsinki"))

    def doctor(self, cl):
        latest, params = cl.obs()
        return bool(params), f"(FMI obs for {cl.label} at {latest or '?'}; keyless open-data WFS)"

    def search(self, cl, term, args):
        latest, params = cl.obs()
        item, obs = _build(cl.cc, cl.label, latest, params)
        t = (term or "").lower()
        return [(item, obs)] if (not t or t in cl.label.lower()) else []

    def fetch(self, cl, item_id):
        latest, params = cl.obs()
        return _build(cl.cc, cl.label, latest, params)

    def is_deal(self, obs):
        t = obs.flags.get("temp_c")
        return isinstance(t, (int, float)) and t >= WARM

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('temp_c')} C, wind {f.get('wind_ms')} m/s  ({f.get('measured')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return (f"{(str(f.get('temp_c')) if f.get('temp_c') is not None else '?'):>5}  "
                f"{(str(round(f.get('wind_ms'))) if f.get('wind_ms') is not None else '?'):>4}  "
                f"{(str(round(f.get('humidity'))) if f.get('humidity') is not None else '?'):>4}  {item.name}")

    def format_item(self, item, obs):
        lines = [f"  city     : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  temp     : {f.get('temp_c')} C   humidity {f.get('humidity')}%")
            lines.append(f"  wind     : {f.get('wind_ms')} m/s")
            lines.append(f"  measured : {f.get('measured')}")
        return lines


SOURCE = FmiSource()
