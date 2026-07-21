"""imgw - live Polish weather-station observations via IMGW-PIB open data, keyless.

IMGW-PIB (Instytut Meteorologii i Gospodarki Wodnej - Poland's national met + hydrology institute)
publishes its synoptic-station observations as keyless open data:
`danepubliczne.imgw.pl/api/data/synop` returns the whole national network (~62 stations) in one GET,
each with air temperature, wind speed/direction, relative humidity, precipitation total and pressure.
robots.txt is 404 (unfenced) and the data is published for reuse ("dane publiczne" = public data) =
sanctioned -> trove. Opens **Poland** and is the metno/ipma present-state twin over central Europe.

The tracked scalar is the live station temperature: `price_cents` = air temperature in centi-degrees C
(so the core's `drops` = a station *cooling*); `qty` = relative humidity %. A "deal" ("wet") = the
station is currently recording precipitation (suma_opadu > 0 mm). Wind, pressure and the measurement
hour ride in flags. money() renders centi-degrees as '$' in the two core-hardcoded spots (the geonet
scalar-reuse cosmetic; the rich views show degrees C).

Model: one Item per station (join key = `id_stacji`). One memoized GET serves a whole pass; `search
<term>` filters by station name (pass "" to list them), `fetch` scans the board for one station id.
`--cc` is unused - the synop feed is one national set.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://danepubliczne.imgw.pl/api/data/synop"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build(rec):
    sid = str(rec.get("id_stacji"))
    temp = _f(rec.get("temperatura"))
    rh = _f(rec.get("wilgotnosc_wzgledna"))
    rain = _f(rec.get("suma_opadu"))
    when = f"{rec.get('data_pomiaru') or ''} {rec.get('godzina_pomiaru') or ''}:00".strip()
    item = Item(sid, name=safe(rec.get("stacja") or sid), subtitle="IMGW synoptic station", category="PL",
                extra={"station": safe(rec.get("stacja") or "")})
    obs = Obs(price_cents=(round(temp * 100) if temp is not None else None),
              qty=(round(rh) if rh is not None else None),
              flags={"temp_c": temp, "humidity": rh, "rain_mm": rain,
                     "wind_ms": _f(rec.get("predkosc_wiatru")), "wind_dir": _f(rec.get("kierunek_wiatru")),
                     "pressure_hpa": _f(rec.get("cisnienie")), "measured": when})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._rows = None

    def rows(self):
        if self._rows is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._rows = r.json() or []
        return self._rows


class ImgwSource(Source):
    name = "imgw"
    id_label = "STATION"
    cc_default = "pl"        # unused
    deal_label = "wet"       # station currently recording precipitation
    search_limit_default = 30
    search_header = f"{'TEMP':>5}  {'RH%':>4}  {'RAIN':>5}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = cl.rows()
        return bool(rows), f"({len(rows)} PL synoptic stations; keyless IMGW dane publiczne)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for rec in cl.rows():
            item, obs = _build(rec)
            if not t or t in safe(item.name).lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents if io[1].price_cents is not None else -10 ** 9))
        return out

    def fetch(self, cl, item_id):
        for rec in cl.rows():
            if str(rec.get("id_stacji")) == str(item_id):
                return _build(rec)
        return None

    def is_deal(self, obs):
        r = obs.flags.get("rain_mm")
        return isinstance(r, (int, float)) and r > 0

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('rain_mm')}mm rain, {f.get('temp_c')}C  ({f.get('measured')})"

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
            lines.append(f"  rain     : {f.get('rain_mm')} mm   pressure {f.get('pressure_hpa')} hPa")
            lines.append(f"  wind     : {f.get('wind_ms')} m/s  dir {f.get('wind_dir')} deg")
            lines.append(f"  measured : {f.get('measured')}")
        return lines


SOURCE = ImgwSource()
