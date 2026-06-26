"""metno - weather *forecast drift* via MET Norway's sanctioned, keyless Locationforecast API.

MET Norway (api.met.no) is the Norwegian Meteorological Institute's public weather API - the same
backend the yr.no consumer weather site/app is built on. It is keyless, global, CC-BY 4.0 / NLOD
licensed, and explicitly sanctioned for programmatic use provided you send an identifying
User-Agent and respect the Expires header. robots.txt fences `/weatherapi/*` only for Googlebot
(anti-search-indexing); for `User-agent: *` the data path is fully allowed. Sanctioned public API
-> trove. (yr.no's robots blocks a list of AI-*training* crawlers - ClaudeBot/GPTBot/CCBot/etc;
this is a personal API client with an honest UA doing no training/redistribution, so that posture is
honoured, not impersonated.)

Why this is *different* from every other trove source: everything else hoards a present-state value
(a price, seats remaining, a fuel cent/L, an earthquake magnitude). This one hoards a **prediction
about the future and how it gets revised**. The free tier serves past *actuals* (the archive API) but
never *past forecasts-as-issued* - so the forecast-evolution series can only exist if you capture it.
Each poll stamps the observation with `target_date` (the day being predicted) and `issued`
(`meta.updated_at`, MET's forecast-run time), so the drift of tomorrow's predicted high/rain across
successive runs is fully reconstructable from the hoard, and un-rebuildable from anywhere else.

Model: one Item per location (join key = a built-in city slug like `auckland`, or an arbitrary
`lat,lon`). `price_cents` = the forecast daytime **high** for the upcoming day in centi-degrees C
(M-style scalar reuse: M22.0 -> 2200), so the core's `drops` = a forecast that **cooled** since the
last poll - the headline drift signal. `qty` = that day's forecast total rain in tenths of a mm.
A "fineday" (the deal analog) = forecast high >= 20.0C and < 1mm rain (a fine, dry day ahead).
`search <name>` filters the built-in city list (or pass `lat,lon` for any point) and fetches each
live; `item`/`poll` re-fetch by id and rebuild the request from it. `--cc` is unused (location is the
key). Locationforecast has no place-name lookup, so discovery rides a curated city list rather than a
geocoder (the geocoder-host api.open-meteo.com is robots-fenced; MET has none).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source

UA = "trove/0.1 weather-source (github.com/LukeTheoJohnson/trove; luketheojohnson@gmail.com)"
HOST = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
FINE_HIGH_CENTS = 2000   # forecast high >= 20.0C ...
FINE_PRECIP_MM = 1.0     # ... and < 1mm rain = a "fine day ahead" (the deal analog)

# Curated discovery list (Locationforecast is lat/lon-only). slug -> (display, lat, lon), <=4dp.
# NZ on-brand + a global spread (incl. Oslo, MET's home) to flex the worldwide coverage.
CITIES = {
    "auckland":     ("Auckland, NZ",     -36.8485, 174.7633),
    "wellington":   ("Wellington, NZ",   -41.2865, 174.7762),
    "christchurch": ("Christchurch, NZ", -43.5321, 172.6362),
    "queenstown":   ("Queenstown, NZ",   -45.0312, 168.6626),
    "sydney":       ("Sydney, AU",       -33.8688, 151.2093),
    "singapore":    ("Singapore",          1.3521, 103.8198),
    "tokyo":        ("Tokyo, JP",         35.6762, 139.6503),
    "london":       ("London, UK",        51.5072,  -0.1276),
    "oslo":         ("Oslo, NO",          59.9139,  10.7522),
    "reykjavik":    ("Reykjavik, IS",     64.1466, -21.9426),
    "newyork":      ("New York, US",      40.7128, -74.0060),
    "sanfrancisco": ("San Francisco, US", 37.7749, -122.4194),
}
COORD_NAMES = {(lat, lon): name for name, lat, lon in CITIES.values()}


def _c(v):
    return f"{v:.1f}C" if isinstance(v, (int, float)) else "?"


def _mm(v):
    return f"{v:g}mm" if isinstance(v, (int, float)) else "?"


def _ms(v):
    return f"{v:g}m/s" if isinstance(v, (int, float)) else "?"


def _f(x):
    return x if isinstance(x, (int, float)) else None


def _resolve(token):
    """A city slug or a `lat,lon` string -> (lat, lon, display_name), or None."""
    t = (token or "").strip()
    tl = t.lower()
    if tl in CITIES:
        name, lat, lon = CITIES[tl]
        return lat, lon, name
    if "," in t:
        try:
            a, b = t.split(",", 1)
            lat, lon = round(float(a), 4), round(float(b), 4)
        except ValueError:
            return None
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon, COORD_NAMES.get((lat, lon), f"{lat},{lon}")
    return None


def _day_temps(ts, date_str):
    vals = [_f(e["data"]["instant"]["details"].get("air_temperature"))
            for e in ts if e["time"][:10] == date_str]
    vals = [v for v in vals if v is not None]
    return (max(vals), min(vals)) if vals else (None, None)


def _day_wind(ts, date_str):
    vals = [_f(e["data"]["instant"]["details"].get("wind_speed"))
            for e in ts if e["time"][:10] == date_str]
    vals = [v for v in vals if v is not None]
    return round(max(vals), 1) if vals else None


def _day_precip(ts, date_str):
    """Sum next_1_hours precip over the date (near-term entries are hourly, so no double-count)."""
    total, seen = 0.0, False
    for e in ts:
        if e["time"][:10] != date_str:
            continue
        nh = e["data"].get("next_1_hours") or {}
        p = _f((nh.get("details") or {}).get("precipitation_amount"))
        if p is not None:
            total += p
            seen = True
    return round(total, 1) if seen else None


def _day_symbol(ts, date_str):
    """Representative symbol_code for the date: the block nearest midday with a summary."""
    best = None
    for e in ts:
        if e["time"][:10] != date_str:
            continue
        sym = None
        for blk in ("next_6_hours", "next_1_hours", "next_12_hours"):
            b = e["data"].get(blk) or {}
            code = (b.get("summary") or {}).get("symbol_code")
            if code:
                sym = code
                break
        if sym:
            dist = abs(int(e["time"][11:13]) - 12)
            if best is None or dist < best[0]:
                best = (dist, sym)
    return best[1] if best else None


def _forecast(payload, item_id, name, lat, lon):
    """The current run's forecast for the *upcoming* day -> (Item, Obs). item_id is used verbatim as
    the join key (so the watch key always matches the stored item)."""
    props = payload.get("properties", {}) or {}
    ts = props.get("timeseries") or []
    if not ts:
        return None
    issued = (props.get("meta") or {}).get("updated_at", "")
    first = ts[0]["time"][:10]
    tgt = (datetime.strptime(first, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
    hi, lo = _day_temps(ts, tgt)
    precip = _day_precip(ts, tgt)
    sym = _day_symbol(ts, tgt)
    wind = _day_wind(ts, tgt)
    cur_t = _f(ts[0]["data"]["instant"]["details"].get("air_temperature"))
    cur_sym = ((ts[0]["data"].get("next_1_hours") or {}).get("summary") or {}).get("symbol_code", "")

    dates = []
    for e in ts:
        d = e["time"][:10]
        if d not in dates:
            dates.append(d)
    outlook = []
    for d in dates[:6]:
        dh, dl = _day_temps(ts, d)
        outlook.append({"date": d, "high_c": dh, "low_c": dl, "symbol": _day_symbol(ts, d)})

    item = Item(item_id, name=name, subtitle=f"forecast for {tgt} (issued {issued})",
                category=sym or "",
                extra={"lat": lat, "lon": lon, "name": name, "issued": issued,
                       "target_date": tgt, "current_c": cur_t, "current_symbol": cur_sym,
                       "outlook": outlook, "url": f"{HOST}?lat={lat}&lon={lon}"})
    obs = Obs(price_cents=(round(hi * 100) if hi is not None else None),
              qty=(round(precip * 10) if precip is not None else None),
              flags={"high_c": hi, "low_c": lo, "precip_mm": precip, "symbol": sym,
                     "wind_ms": wind, "target_date": tgt, "issued": issued})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._cache = {}   # (lat,lon) -> payload; one GET serves a whole pass for a point

    def get(self, lat, lon):
        key = (lat, lon)
        if key not in self._cache:
            r = self.s.get(HOST, params={"lat": lat, "lon": lon},
                           headers={"User-Agent": UA, "Accept": "application/json"}, timeout=40)
            r.raise_for_status()
            self._cache[key] = r.json()
        return self._cache[key]


class MetNoSource(Source):
    name = "metno"
    id_label = "LOCATION"
    cc_default = "global"        # unused; the location is the key
    deal_label = "fineday"       # fineday = forecast high >= 20.0C and < 1mm rain
    search_limit_default = 12
    search_header = f"{'HI/LO':>13}  {'RAIN':>6}  {'SYMBOL':<18}  LOCATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        p = cl.get(-36.8485, 174.7633)
        ts = (p.get("properties", {}) or {}).get("timeseries") or []
        iss = ((p.get("properties", {}) or {}).get("meta") or {}).get("updated_at", "?")
        return bool(ts), f"({len(ts)} steps; issued {iss}; keyless MET Norway Locationforecast)"

    def search(self, cl, term, args):
        import time
        t = (term or "").strip()
        targets = []   # (item_id, name, lat, lon)
        res = _resolve(t)
        if res and ("," in t):                      # explicit point
            lat, lon, name = res
            targets.append((t, name, lat, lon))
        else:                                       # name substring over the city list (empty = all)
            tl = t.lower()
            for slug, (name, lat, lon) in CITIES.items():
                if tl in slug or tl in name.lower():
                    targets.append((slug, name, lat, lon))
        rows = []
        for i, (iid, name, lat, lon) in enumerate(targets[: args.limit]):
            try:
                fc = _forecast(cl.get(lat, lon), iid, name, lat, lon)
            except Exception:
                fc = None
            if fc:
                rows.append(fc)
            if i + 1 < len(targets):
                time.sleep(0.3)                     # polite: one point at a time, never a burst
        return rows

    def fetch(self, cl, item_id):
        res = _resolve(item_id)
        if not res:
            return None
        lat, lon, name = res
        return _forecast(cl.get(lat, lon), item_id, name, lat, lon)

    def is_deal(self, obs):
        pc = obs.price_cents
        precip = obs.flags.get("precip_mm")
        return (pc is not None and pc >= FINE_HIGH_CENTS
                and (precip is None or precip < FINE_PRECIP_MM))

    def deal_line(self, item, obs):
        f = obs.flags
        return (f"high {_c(f.get('high_c'))}  low {_c(f.get('low_c'))}  "
                f"rain {_mm(f.get('precip_mm'))}  {f.get('symbol', '')}  "
                f"({f.get('target_date', '')})  {item.name}")

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        hilo = f"{_c(f.get('high_c'))}/{_c(f.get('low_c'))}"
        return f"{hilo:>13}  {_mm(f.get('precip_mm')):>6}  {(f.get('symbol') or '?'):<18}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  location : {e.get('name', '')}",
                 f"  coords   : {e.get('lat')}, {e.get('lon')}",
                 f"  issued   : {e.get('issued', '')}  (forecast run; re-poll to capture drift)",
                 f"  now      : {_c(e.get('current_c'))}  {e.get('current_symbol', '')}"]
        if obs:
            f = obs.flags
            lines.append(f"  {f.get('target_date', 'next day')} : high {_c(f.get('high_c'))}  "
                         f"low {_c(f.get('low_c'))}  rain {_mm(f.get('precip_mm'))}  "
                         f"wind {_ms(f.get('wind_ms'))}  {f.get('symbol', '')}")
        for d in (e.get("outlook") or []):
            lines.append(f"    {d.get('date')}  {_c(d.get('high_c')):>6} / {_c(d.get('low_c')):>6}  "
                         f"{d.get('symbol', '')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = MetNoSource()
