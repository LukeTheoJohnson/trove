"""petrolspy - NZ per-station fuel prices via PetrolSpy's keyless web-map API.

PetrolSpy's web map (petrolspy.com.au, covers AU + NZ) calls a keyless bounding-box service,
`https://petrolspy.com.au/webservice-1/station/box?neLat=&neLng=&swLat=&swLng=`, that returns every
station in the box with its per-grade prices. robots.txt fences only `/admin-1/`, not the webservice.
This source scopes the box to NZ city bounding boxes, so it tracks NZ forecourt prices - the same
gap Gaspy left (app-only) but reached through the *web* service the map itself calls.

The timeline value is the *ephemeral per-station price*: crowd-sourced forecourt prices that nobody
archives per-station, so the snapshot is the only record. Mirrors the Spain `spainfuel` model for NZ.

Model: one Item per station (join key = PetrolSpy's station id), tracking U91 (regular unleaded) as
price_cents (cents/L, so money() shows $/L), with the full grade board and the city-box average
carried in flags. A "deal" = the station is at or below the box average for U91. `prices.amount` is
whole cents/L (e.g. 337 = $3.37/L); each grade also carries an `updated` epoch + a `relevant` fresh
flag, surfaced so stale crowd reports are visible.

`search` scopes to a city box (--cc, default "auckland"; also wellington/christchurch) and filters by
a brand/suburb/name substring. `item`/`poll` find a station by id across the city boxes; the client
memoizes each box, so a whole poll costs at most one GET per city box.
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://petrolspy.com.au/webservice-1/station/box"
HEADLINE = "U91"   # regular unleaded - the grade tracked as price_cents

# rough metro bounding boxes (neLat, neLng, swLat, swLng)
CITY_BOXES = {
    "auckland":     (-36.66, 175.00, -37.10, 174.55),
    "wellington":   (-41.07, 174.99, -41.36, 174.66),
    "christchurch": (-43.40, 172.78, -43.64, 172.45),
}


def _avg_cents(stations):
    vals = [a for a in (((s.get("prices") or {}).get(HEADLINE) or {}).get("amount")
                        for s in stations) if isinstance(a, (int, float))]
    return round(sum(vals) / len(vals)) if vals else None


def _station(st, avg_cents):
    prices = st.get("prices") or {}
    board, updated, relevant = {}, {}, {}
    for g, info in prices.items():
        amt = info.get("amount")
        if isinstance(amt, (int, float)):
            board[g] = amt
            updated[g] = info.get("updated")
            relevant[g] = info.get("relevant")
    head = (prices.get(HEADLINE) or {}).get("amount")
    loc = st.get("location") or {}
    item = Item(str(st.get("id", "")),
                name=safe(st.get("name", "")) or safe(st.get("brand", "")),
                subtitle=safe(st.get("address", "")),
                category=safe(st.get("brand", "")),
                extra={"suburb": safe(st.get("suburb", "")), "postcode": st.get("postCode", ""),
                       "lat": loc.get("y"), "lon": loc.get("x"), "open24": st.get("open24"),
                       "country": st.get("country", ""), "brand": safe(st.get("brand", ""))})
    obs = Obs(price_cents=(head if isinstance(head, (int, float)) else None),
              flags={"grade": HEADLINE, "board": board, "updated": updated,
                     "relevant": relevant, "area_avg": avg_cents, "unit": "cents/L"})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._cache = {}

    def box(self, name):
        if name not in self._cache:
            b = CITY_BOXES.get(name)
            if not b:
                self._cache[name] = []
            else:
                ne_lat, ne_lng, sw_lat, sw_lng = b
                r = self.s.get(BASE, params={"neLat": ne_lat, "neLng": ne_lng,
                                             "swLat": sw_lat, "swLng": sw_lng},
                               headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
                r.raise_for_status()
                self._cache[name] = ((r.json() or {}).get("message") or {}).get("list") or []
        return self._cache[name]


class PetrolSpySource(Source):
    name = "petrolspy"
    id_label = "STATION"
    cc_default = "auckland"   # city box; --cc wellington|christchurch
    deal_label = "deal"       # deal = at/below the city-box average for U91

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        stations = cl.box(self.cc_default)
        return bool(stations), f"({len(stations)} stations in {self.cc_default} box; keyless PetrolSpy)"

    def search(self, cl, term, args):
        stations = cl.box(args.cc if args.cc in CITY_BOXES else self.cc_default)
        avg = _avg_cents(stations)
        t = term.lower()
        out = []
        for st in stations:
            hay = " ".join(str(st.get(k, "")) for k in ("name", "brand", "suburb", "address")).lower()
            if t in hay:
                out.append(_station(st, avg))
        return out

    def fetch(self, cl, item_id):
        sid = str(item_id)
        for name in CITY_BOXES:
            stations = cl.box(name)
            for st in stations:
                if str(st.get("id")) == sid:
                    return _station(st, _avg_cents(stations))
        return None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("area_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        avg = obs.flags.get("area_avg")
        gap = (f"  ({(obs.price_cents - avg) / 100:+.2f} vs box avg)"
               if avg is not None and obs.price_cents is not None else "")
        return f"{money(obs.price_cents)}/L {HEADLINE}{gap}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  brand    : {item.category}",
                 f"  address  : {item.subtitle}",
                 f"  suburb   : {item.extra.get('suburb', '')} ({item.extra.get('postcode', '')})",
                 f"  open 24h : {item.extra.get('open24')}"]
        if obs:
            board = obs.flags.get("board") or {}
            upd = obs.flags.get("updated") or {}
            for g, amt in board.items():
                ts = upd.get(g)
                when = datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%d") if ts else "?"
                lines.append(f"  {g:<7} : {money(amt)}/L  (updated {when})")
            avg = obs.flags.get("area_avg")
            if avg is not None:
                lines.append(f"  box avg  : {money(avg)}/L ({HEADLINE})")
        return lines


SOURCE = PetrolSpySource()
