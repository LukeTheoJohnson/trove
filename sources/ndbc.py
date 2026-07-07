"""ndbc - live offshore marine conditions from NOAA's National Data Buoy Center, keyless.

NDBC operates the US (and partner) network of moored weather buoys and coastal stations, publishing
their real-time observations as keyless flat files (`www.ndbc.noaa.gov`; robots disallows only a
couple of named bad crawlers, never `User-agent: *` - the data files are open; NOAA official data =
sanctioned -> trove). Pairs with `noaatides` in the **marine & coastal** genre - buoys are the
offshore complement to the coastal tide gauges.

The tracked value is the live **significant wave height** (WVHT, metres) - the sea state, rising with
storms/swell and falling as it passes. `price_cents` = wave height * 100 (centi-metre), so the core's
`drops` = the seas *calming*; `is_deal` ("bigswell") = WVHT >= 3 m (a large swell / heavy-surf sea).
`qty` = wind speed (m/s). The full obs (dominant wave period, wave direction, water + air temp,
pressure, gust) ride in flags. Honest hoard value low-med: NDBC archives the historical files
(rebuildable), so the draw is opening the marine domain + the live sea-state signal.

One bulk file - `data/latest_obs/latest_obs.txt` - carries **every station's latest observation in a
single GET** (~890 stations), so a whole search/poll pass is one memoized request; station names come
from `activestations.xml` (also memoized). Missing readings are the sentinel `MM`. Join key = the NDBC
station id (e.g. `46026`, globally unique). `search <term>` filters by id or name (pass "" to list all,
biggest seas first); `item`/`poll` read one station's row from the same memoized bulk file. `--cc` is
unused.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

LATEST = "https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt"
STATIONS = "https://www.ndbc.noaa.gov/activestations.xml"
BIG_SWELL = 3.0        # WVHT >= 3 m = a large swell / heavy-surf sea state
# column index -> field, per the latest_obs.txt header
COLS = {"lat": 1, "lon": 2, "wdir": 8, "wspd": 9, "gst": 10, "wvht": 11, "dpd": 12,
        "apd": 13, "mwd": 14, "pres": 15, "atmp": 17, "wtmp": 18, "dewp": 19}


def _f(v):
    try:
        return None if v in ("MM", "") else float(v)
    except (TypeError, ValueError):
        return None


def _row(cols, names):
    stn = cols[0]
    g = lambda k: _f(cols[COLS[k]]) if COLS[k] < len(cols) else None
    wvht = g("wvht")
    wspd = g("wspd")
    when = f"{cols[3]}-{cols[4]}-{cols[5]} {cols[6]}:{cols[7]} UTC" if len(cols) > 7 else ""
    name = names.get(stn) or stn
    bits = []
    if wvht is not None:
        bits.append(f"waves {wvht} m")
    if g("wtmp") is not None:
        bits.append(f"sea {g('wtmp')}C")
    if wspd is not None:
        bits.append(f"wind {wspd} m/s")
    item = Item(stn, name=safe(name), subtitle=safe(", ".join(bits) or "no current obs"),
                category="buoy",
                extra={"lat": g("lat"), "lon": g("lon"), "name": safe(name),
                       "url": f"https://www.ndbc.noaa.gov/station_page.php?station={stn}"})
    obs = Obs(price_cents=(round(wvht * 100) if wvht is not None else None),
              qty=(round(wspd) if wspd is not None else None),
              flags={"wvht_m": wvht, "dom_period_s": g("dpd"), "wave_dir_deg": g("mwd"),
                     "wind_ms": wspd, "gust_ms": g("gst"), "wind_dir_deg": g("wdir"),
                     "water_temp_c": g("wtmp"), "air_temp_c": g("atmp"), "pressure_hpa": g("pres"),
                     "time": when})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._rows = None
        self._names = None

    def names(self):
        if self._names is None:
            try:
                r = self.s.get(STATIONS, headers={"User-Agent": UA}, timeout=45)
                r.raise_for_status()
                root = ET.fromstring(r.content)
                self._names = {st.get("id"): st.get("name") for st in root.iter("station") if st.get("id")}
            except Exception:
                self._names = {}
        return self._names

    def rows(self):
        if self._rows is None:
            r = self.s.get(LATEST, headers={"User-Agent": UA}, timeout=45)
            r.raise_for_status()
            out = {}
            for line in r.text.splitlines():
                if not line or line.startswith("#"):
                    continue
                cols = line.split()
                if cols:
                    out[cols[0]] = cols
            self._rows = out
        return self._rows


class NdbcSource(Source):
    name = "ndbc"
    id_label = "STATION"
    cc_default = "us"          # unused; global buoy network
    deal_label = "bigswell"    # WVHT >= 3 m
    search_limit_default = 25
    search_header = f"{'WAVE':>7}  {'SEA':>5}  {'WIND':>6}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = cl.rows()
        return bool(rows), f"({len(rows)} NDBC buoys reporting; keyless latest_obs bulk file)"

    def search(self, cl, term, args):
        t = (term or "").strip().lower()
        names = cl.names()
        out = []
        for stn, cols in cl.rows().items():
            item, obs = _row(cols, names)
            if not t or t == stn.lower() or t in item.name.lower():
                out.append((item, obs))
        # biggest seas first; buoys without a wave reading sort last
        out.sort(key=lambda io: -(io[1].flags.get("wvht_m") if io[1].flags.get("wvht_m") is not None else -1))
        return out

    def fetch(self, cl, item_id):
        cols = cl.rows().get(str(item_id))
        if not cols:
            return None
        return _row(cols, cl.names())

    def is_deal(self, obs):
        w = obs.flags.get("wvht_m")
        return w is not None and w >= BIG_SWELL

    def deal_line(self, item, obs):
        f = obs.flags
        return (f"{item.name}  waves {f.get('wvht_m')} m @ {f.get('dom_period_s')}s  "
                f"wind {f.get('wind_ms')} m/s  (big swell)")

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        wv = f"{f.get('wvht_m')}m" if f.get("wvht_m") is not None else "-"
        sea = f"{f.get('water_temp_c')}C" if f.get("water_temp_c") is not None else "-"
        wind = f"{f.get('wind_ms')}m/s" if f.get("wind_ms") is not None else "-"
        return f"{wv:>7}  {sea:>5}  {wind:>6}  {item.name[:52]}"

    def format_item(self, item, obs):
        e = item.extra
        lines = []
        if obs:
            f = obs.flags
            lines.append(f"  waves    : {f.get('wvht_m')} m sig. height @ {f.get('dom_period_s')}s period"
                         f"  dir {f.get('wave_dir_deg')} deg")
            lines.append(f"  wind     : {f.get('wind_ms')} m/s  gust {f.get('gust_ms')}  dir {f.get('wind_dir_deg')} deg")
            lines.append(f"  temp     : sea {f.get('water_temp_c')}C  air {f.get('air_temp_c')}C  pressure {f.get('pressure_hpa')} hPa")
            lines.append(f"  observed : {f.get('time')}")
        lines.append(f"  station  : NDBC {item.id}  {e.get('lat')}, {e.get('lon')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = NdbcSource()
