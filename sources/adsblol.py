"""adsblol - live aircraft over a region via adsb.lol, a keyless community ADS-B network.

adsb.lol is a community-run, ad-free ADS-B aggregator (volunteer feeders) that publishes live aircraft
positions for public reuse. `GET /v2/lat/<lat>/lon/<lon>/dist/<nm>` returns every aircraft its network
sees within <nm> nautical miles of a point: hex (transponder id), callsign, registration, type,
barometric + geometric altitude (feet), position, ground-speed (kt), vertical rate (ft/min) and squawk.
The API host serves no robots.txt (404 = unfenced, the GBFS/S3 class) and exists to be consumed =
sanctioned -> trove. The keyless-community twin of `opensky` (which rate-limits anonymous callers):
same "everything in the sky over a box right now" shape, different network + coverage.

The timeline value is un-rebuildable for a casual caller: an aircraft's altitude/position at a moment
is ephemeral and adsb.lol keeps no free per-aircraft history. `price_cents` = **barometric altitude
in feet** (so the core's `drops` = an aircraft *losing altitude* = descending on approach); `qty` =
ground speed (kt). A "deal" ("descending") = airborne, below 10,000 ft and sinking (baro_rate < 0) -
a plane on final approach over the region. money() renders the altitude-feet as dollars in the two
core-hardcoded spots (35,000 ft -> "$350.00"); the rich views show altitude/speed/heading.

Model: one Item per aircraft in range (join key = `hex`, the stable ICAO transponder id). `--cc` picks
the region centre+radius from a small table (default `lon`; also `nz`, `au`, `syd`, `nyc`, `la`, `sf`).
`search <term>` filters by callsign/registration/type; `fetch` rescans the region for one hex (an
aircraft that has left = fetch None = its series ends).
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://api.adsb.lol/v2"
# region -> (lat, lon, dist_nm)
REGIONS = {
    "lon": (51.47, -0.45, 40), "nz": (-41.3, 174.8, 60), "au": (-33.9, 151.2, 60),
    "syd": (-33.95, 151.18, 40), "nyc": (40.64, -73.78, 40), "la": (33.94, -118.41, 40),
    "sf": (37.62, -122.38, 40),
}
LOW_FT = 10000   # airborne + below this + sinking = on approach


def _num(v):
    return v if isinstance(v, (int, float)) else None


def _alt_ft(v):
    """alt_baro is feet (int) or the string 'ground'."""
    if isinstance(v, (int, float)):
        return int(v)
    return 0 if str(v).strip().lower() == "ground" else None


def _build(ac):
    hexid = str(ac.get("hex") or "").strip()
    call = safe((ac.get("flight") or "").strip())
    reg = safe((ac.get("r") or "").strip())
    typ = safe((ac.get("t") or "").strip())
    alt = _alt_ft(ac.get("alt_baro"))
    on_ground = str(ac.get("alt_baro")).strip().lower() == "ground"
    gs = _num(ac.get("gs"))
    item = Item(hexid, name=(call or reg or hexid), subtitle=f"{typ or 'aircraft'} {reg}".strip(),
                category="aircraft", extra={"registration": reg, "type": typ, "callsign": call})
    obs = Obs(price_cents=alt,
              qty=(round(gs) if gs is not None else None),
              flags={"callsign": call, "registration": reg, "type": typ,
                     "lat": _num(ac.get("lat")), "lon": _num(ac.get("lon")),
                     "alt_ft": alt, "speed_kt": gs, "heading": _num(ac.get("track")),
                     "baro_rate": _num(ac.get("baro_rate")), "on_ground": on_ground,
                     "squawk": ac.get("squawk"), "dist_nm": _num(ac.get("dst"))})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.region = cc if cc in REGIONS else "lon"
        self.s = retry_session()
        self._ac = None

    def aircraft(self):
        if self._ac is None:
            lat, lon, dist = REGIONS[self.region]
            r = self.s.get(f"{BASE}/lat/{lat}/lon/{lon}/dist/{dist}",
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._ac = (r.json() or {}).get("ac") or []
        return self._ac


class AdsbLolSource(Source):
    name = "adsblol"
    id_label = "HEX"
    cc_default = "lon"
    deal_label = "descending"   # airborne, low and sinking = on approach over the region
    search_limit_default = 40
    search_header = f"{'ALT_FT':>7}  {'KT':>4}  {'CALLSIGN':<9}  TYPE"

    def client(self, args):
        return _Client(getattr(args, "cc", "lon"))

    def doctor(self, cl):
        ac = cl.aircraft()
        return bool(ac), f"({len(ac)} aircraft over '{cl.region}'; keyless adsb.lol community ADS-B)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for ac in cl.aircraft():
            if not ac.get("hex"):
                continue
            item, obs = _build(ac)
            hay = f"{obs.flags.get('callsign', '')} {obs.flags.get('registration', '')} {obs.flags.get('type', '')}".lower()
            if not t or t in hay:
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out

    def fetch(self, cl, item_id):
        for ac in cl.aircraft():
            if str(ac.get("hex") or "").strip() == str(item_id).strip():
                return _build(ac)
        return None

    def is_deal(self, obs):
        f = obs.flags
        alt, br = f.get("alt_ft"), f.get("baro_rate")
        return (not f.get("on_ground")) and alt is not None and 0 < alt < LOW_FT and (br is not None and br < 0)

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name} descending {f.get('alt_ft')}ft @ {f.get('baro_rate')}ft/min  ({f.get('type') or '?'})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        alt = f.get("alt_ft")
        return (f"{(alt if alt is not None else '?'):>7}  "
                f"{(round(f.get('speed_kt')) if f.get('speed_kt') is not None else '?'):>4}  "
                f"{safe(f.get('callsign') or '-'):<9}  {f.get('type') or '?'}")

    def format_item(self, item, obs):
        lines = [f"  aircraft : {item.name}  ({item.id})"]
        if obs:
            f = obs.flags
            lines.append(f"  reg/type : {f.get('registration') or '?'}  {f.get('type') or '?'}")
            lines.append(f"  position : {f.get('lat')}, {f.get('lon')}   heading {f.get('heading')}   {f.get('dist_nm')}nm out")
            lines.append(f"  altitude : {f.get('alt_ft')} ft   speed {f.get('speed_kt')} kt   vrate {f.get('baro_rate')} ft/min")
            lines.append(f"  onground : {f.get('on_ground')}   squawk {f.get('squawk') or '?'}")
        return lines


SOURCE = AdsbLolSource()
