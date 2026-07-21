"""austriafuel - cheapest Austrian diesel prices near a city via E-Control Spritpreisrechner, keyless.

E-Control (Austria's energy regulator) runs the statutory Spritpreisrechner: by law only the cheapest
stations must publish their live prices, and the regulator exposes them keyless at
`api.e-control.at/sprit/1.0/search/gas-stations/by-address?latitude=&longitude=&fuelType=DIE` - the
nearest stations to a point with their current diesel price (`prices:[{fuelType, amount, label}]`),
name, address and coordinates. The docs host serves an app shell for /robots.txt (no API Disallow) and
the endpoint is the one the public price calculator calls = sanctioned -> trove. Opens **Austria** on
the fuel side (spainfuel/francefuel/italyfuel twin).

The published set *is* the ephemeral live-price set (only the cheapest publish, and the value is
overwritten in place), so it is a clean per-station hoard. `price_cents` = the station's diesel price in
euro-cents (so the core's `drops` = the pump getting *cheaper*); `qty` = None. A "deal" ("cheap") = the
station is at or below the average of the returned nearby set - i.e. among the cheaper of the live-price
stations around that city. money() renders euro-cents (a '$' glyph on cp1252; the value is euros).

Model: one Item per station (join key = the E-Control station `id`). `--cc` picks a city anchor
(default `wien`; also `graz`, `linz`, `salzburg`, `innsbruck`, `klagenfurt`) whose coordinates seed the
by-address search; diesel (`DIE`) is the tracked grade. `search`/`fetch` read the same memoized set.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://api.e-control.at/sprit/1.0/search/gas-stations/by-address"
FUEL = "DIE"
# city anchor -> (lat, lon)
CITIES = {"wien": (48.2082, 16.3738), "graz": (47.0707, 15.4395), "linz": (48.3069, 14.2858),
          "salzburg": (47.8095, 13.0550), "innsbruck": (47.2692, 11.4041), "klagenfurt": (46.6247, 14.3050)}


def _f(v):
    return float(v) if isinstance(v, (int, float)) else None


def _diesel_cents(station):
    for p in (station.get("prices") or []):
        if (p.get("fuelType") or "").upper() == FUEL:
            a = _f(p.get("amount"))
            return round(a * 100) if a is not None else None
    return None


def _build(st, avg):
    sid = str(st.get("id"))
    loc = st.get("location") or {}
    pc = _diesel_cents(st)
    item = Item(sid, name=safe(st.get("name") or sid),
                subtitle=safe(f"{loc.get('address', '')}, {loc.get('city', '')}".strip(", ")),
                category=safe(loc.get("city") or "AT"),
                extra={"city": safe(loc.get("city") or ""), "postal": loc.get("postalCode") or "",
                       "lat": _f(loc.get("latitude")), "lon": _f(loc.get("longitude"))})
    obs = Obs(price_cents=pc, qty=None,
              flags={"grade": "diesel", "unit": "euro-cents", "set_avg": avg,
                     "open": st.get("open"), "distance_km": _f(st.get("distance"))})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.city = cc if cc in CITIES else "wien"
        self.s = retry_session()
        self._stations = None
        self._avg = None

    def stations(self):
        if self._stations is None:
            lat, lon = CITIES[self.city]
            r = self.s.get(BASE, params={"latitude": lat, "longitude": lon, "fuelType": FUEL,
                                         "includeClosed": "false"},
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._stations = [s for s in (r.json() or []) if _diesel_cents(s) is not None]
        return self._stations

    def avg(self):
        if self._avg is None:
            vals = [_diesel_cents(s) for s in self.stations()]
            vals = [c for c in vals if c is not None]
            self._avg = round(sum(vals) / len(vals)) if vals else None
        return self._avg


class AustriaFuelSource(Source):
    name = "austriafuel"
    id_label = "STATION"
    cc_default = "wien"      # city anchor: wien|graz|linz|salzburg|innsbruck|klagenfurt
    deal_label = "cheap"     # at/below the average of the nearby live-price set
    search_limit_default = 20
    search_header = f"{'PRICE':>7}  {'KM':>5}  STATION"

    def client(self, args):
        return _Client(getattr(args, "cc", "wien"))

    def doctor(self, cl):
        st = cl.stations()
        return bool(st), f"({len(st)} live-price diesel stations near {cl.city}; keyless E-Control Spritpreisrechner)"

    def search(self, cl, term, args):
        avg = cl.avg()
        t = (term or "").lower()
        out = []
        for st in cl.stations():
            item, obs = _build(st, avg)
            if not t or t in safe(item.name).lower() or t in safe(item.extra.get("city")).lower():
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out

    def fetch(self, cl, item_id):
        avg = cl.avg()
        for st in cl.stations():
            if str(st.get("id")) == str(item_id):
                return _build(st, avg)
        return None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("set_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        avg = obs.flags.get("set_avg")
        gap = (f"  ({(obs.price_cents - avg) / 100:+.3f} vs set avg)" if avg is not None and obs.price_cents is not None else "")
        return f"{money(obs.price_cents)}/L diesel{gap}  {item.name} ({item.extra.get('city')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        km = f.get("distance_km")
        return f"{money(obs.price_cents if obs else None):>7}  {(f'{km:.1f}' if km is not None else '?'):>5}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  station  : {item.name}",
                 f"  location : {e.get('postal')} {e.get('city') or '?'}   [{e.get('lat')}, {e.get('lon')}]"]
        if obs:
            f = obs.flags
            lines.append(f"  diesel   : {money(obs.price_cents)} / L   (nearby set avg {money(f.get('set_avg'))})")
            lines.append(f"  distance : {f.get('distance_km')} km   open {f.get('open')}")
        return lines


SOURCE = AustriaFuelSource()
