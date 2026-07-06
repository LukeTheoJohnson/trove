"""opensky - live aircraft over a region (state vectors) via the OpenSky Network, keyless (anon).

The OpenSky Network is an academic ADS-B receiver network that publishes live aircraft state vectors
for public reuse. `GET /api/states/all?lamin=&lamax=&lomin=&lomax=` returns every aircraft currently in
a bounding box: icao24, callsign, origin country, position, barometric + geometric altitude,
ground-speed, heading, vertical rate, squawk and an on-ground flag. Anonymous access is rate-limited
(a small daily credit budget) but keyless; robots.txt returns an nginx 403 (a missing-object 403 = no
rules = unfenced, the GBFS/S3 class) and OpenSky exists to be consumed = sanctioned -> trove. The
region-wide aviation complement to the single-airport boards `chcflights`/`zqnflights`: not one
airport's schedule but *everything in the sky over a box* right now.

The timeline value is genuinely un-rebuildable for us: an aircraft's position/altitude/velocity at a
moment is ephemeral, and OpenSky's historical track API needs an authenticated (contributor) account -
anonymous callers get only the live snapshot. `price_cents` = barometric altitude in **metres** (so
the core's `drops` = an aircraft *losing altitude* = descending, e.g. on approach); `qty` = ground
speed (m/s). A "deal" ("descending") = airborne, below 3000 m and sinking (vertical rate < 0) - a
plane on final approach over the box. money() renders the altitude-metres as dollars in the two
core-hardcoded spots (10 000 m -> $100.00); the rich views show altitude/speed/heading.

Model: one Item per aircraft currently in the box (join key = `icao24`, the stable transponder id).
`--cc` picks the bounding box from a small region table (default `nz`; also `au`, `uk`, `nyc`, `sf`,
`la`). `search <term>` filters the box's aircraft by callsign/country (pass "" to list them all);
`fetch` scans the box for one icao24 (a plane that has left the box = fetch None = its series ends).
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://opensky-network.org/api/states/all"
# region -> (lamin, lamax, lomin, lomax)
REGIONS = {
    "nz": (-47.5, -34.0, 166.0, 179.0), "au": (-44.0, -10.0, 112.0, 154.0),
    "uk": (49.8, 59.0, -8.2, 2.0), "nyc": (40.4, 41.1, -74.3, -73.6),
    "sf": (37.2, 38.1, -122.6, -121.7), "la": (33.6, 34.4, -118.7, -117.8),
}
# state-vector column indices (OpenSky /states/all)
I_ICAO, I_CALL, I_CTRY, I_LON, I_LAT, I_BALT = 0, 1, 2, 5, 6, 7
I_GROUND, I_VEL, I_TRK, I_VRATE, I_GALT, I_SQUAWK = 8, 9, 10, 11, 13, 14


def _num(v):
    return v if isinstance(v, (int, float)) else None


def _build(st):
    icao = str(st[I_ICAO] or "").strip()
    call = safe(st[I_CALL] or "").strip()
    balt = _num(st[I_BALT])
    galt = _num(st[I_GALT])
    alt = balt if balt is not None else galt
    vel = _num(st[I_VEL])
    item = Item(icao, name=(call or icao), subtitle=f"aircraft {safe(st[I_CTRY] or '')}",
                category="aircraft",
                extra={"country": safe(st[I_CTRY] or ""), "callsign": call})
    obs = Obs(price_cents=(round(alt) if alt is not None else None),
              qty=(round(vel) if vel is not None else None),
              flags={"callsign": call, "country": safe(st[I_CTRY] or ""),
                     "lat": _num(st[I_LAT]), "lon": _num(st[I_LON]),
                     "alt_m": alt, "speed_ms": vel, "heading": _num(st[I_TRK]),
                     "vrate": _num(st[I_VRATE]), "on_ground": bool(st[I_GROUND]),
                     "squawk": st[I_SQUAWK]})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.region = cc if cc in REGIONS else "nz"
        self.s = retry_session()
        self._states = None

    def states(self):
        if self._states is None:
            la1, la2, lo1, lo2 = REGIONS[self.region]
            r = self.s.get(BASE, params={"lamin": la1, "lamax": la2, "lomin": lo1, "lomax": lo2},
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._states = (r.json() or {}).get("states") or []
        return self._states


class OpenSkySource(Source):
    name = "opensky"
    id_label = "ICAO24"
    cc_default = "nz"
    deal_label = "descending"   # airborne, low and sinking = on approach over the box
    search_limit_default = 40
    search_header = f"{'ALT_M':>7}  {'SPD':>4}  {'CALLSIGN':<9}  COUNTRY"

    def client(self, args):
        return _Client(getattr(args, "cc", "nz"))

    def doctor(self, cl):
        sts = cl.states()
        return bool(sts), f"({len(sts)} aircraft over '{cl.region}'; keyless OpenSky state vectors [anon])"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for st in cl.states():
            if not st or not st[I_ICAO]:
                continue
            item, obs = _build(st)
            hay = f"{obs.flags.get('callsign', '')} {obs.flags.get('country', '')}".lower()
            if not t or t in hay:
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out

    def fetch(self, cl, item_id):
        for st in cl.states():
            if str(st[I_ICAO] or "").strip() == str(item_id).strip():
                return _build(st)
        return None

    def is_deal(self, obs):
        f = obs.flags
        alt, vr = f.get("alt_m"), f.get("vrate")
        return (not f.get("on_ground")) and alt is not None and alt < 3000 and (vr is not None and vr < 0)

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name} descending {round(f.get('alt_m') or 0)}m @ {f.get('vrate')}m/s  ({f.get('country')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        alt = f.get("alt_m")
        return f"{(round(alt) if alt is not None else '?'):>7}  {(round(f.get('speed_ms')) if f.get('speed_ms') is not None else '?'):>4}  {safe(f.get('callsign') or '-'):<9}  {f.get('country') or '?'}"

    def format_item(self, item, obs):
        lines = [f"  aircraft : {item.name}  ({item.id})"]
        if obs:
            f = obs.flags
            lines.append(f"  country  : {f.get('country') or '?'}")
            lines.append(f"  position : {f.get('lat')}, {f.get('lon')}   heading {f.get('heading')}")
            lines.append(f"  altitude : {f.get('alt_m')} m   speed {f.get('speed_ms')} m/s   vrate {f.get('vrate')} m/s")
            lines.append(f"  onground : {f.get('on_ground')}   squawk {f.get('squawk') or '?'}")
        return lines


SOURCE = OpenSkySource()
