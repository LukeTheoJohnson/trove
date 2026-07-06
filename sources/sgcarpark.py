"""sgcarpark - Singapore HDB car-park space availability (live), keyless (data.gov.sg).

The Singapore government open-data platform publishes live HDB car-park availability at
api.data.gov.sg. `GET /v1/transport/carpark-availability` returns, for ~2,000 Housing & Development
Board car parks, the current `lots_available` / `total_lots` per lot type (C = car, H = heavy vehicle,
Y = motorcycle) and each park's own update timestamp. The gateway serves no robots.txt (a 403
missing-object body = no rules = unfenced, the GBFS/S3 class) and data.gov.sg exists to be reused =
sanctioned -> trove. This opens a new **parking** genre - the un-rebuildable fill/empty cycle of a
car park, the structural cousin of `bikeshare` (dock availability) and `eventcinemas` (seats left).

The timeline value is scarcity in motion: a car park drains toward full through the morning and
refills at night, and nobody serves a queryable per-park history of free spaces over time.
`price_cents` = car (`C`) spaces available * 100 (centi-lot), so the core's `drops` = a park *filling
up* (fewer free spaces); `qty` = total car lots (capacity). A "deal" ("fullrisk") = a park down to
<= 10 free car spaces (nearly full - park elsewhere). A park dropping out of the feed = fetch None =
its series pauses. money() renders centi-lots as dollars in the two core-hardcoded spots.

Model: one Item per car park (join key = `carpark_number`, e.g. "HE12"). `search <term>` filters by
car-park number (pass "" to list them all, emptiest first); `fetch` scans the memoized feed by number.
`--cc` is unused - one Singapore set.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money

FEED = "https://api.data.gov.sg/v1/transport/carpark-availability"


def _lots(info):
    """carpark_info is a list of {lot_type, total_lots, lots_available}. Prefer cars (C);
    return (available, total, per_type dict)."""
    per = {}
    for row in info or []:
        lt = row.get("lot_type")
        try:
            per[lt] = {"avail": int(row.get("lots_available")), "total": int(row.get("total_lots"))}
        except (TypeError, ValueError):
            continue
    car = per.get("C")
    if car is None and per:
        # no car row: take the largest lot type by capacity
        car = max(per.values(), key=lambda v: v["total"])
    return (car["avail"] if car else None), (car["total"] if car else None), per


def _build(cp):
    num = str(cp.get("carpark_number", ""))
    avail, total, per = _lots(cp.get("carpark_info"))
    item = Item(num, name=num, subtitle="Singapore HDB car park", category="carpark",
                extra={"carpark_number": num})
    obs = Obs(price_cents=(avail * 100 if avail is not None else None),
              qty=total,
              flags={"available": avail, "total": total, "by_type": per,
                     "updated": cp.get("update_datetime")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._cps = None

    def carparks(self):
        if self._cps is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            items = (r.json() or {}).get("items") or []
            self._cps = (items[0].get("carpark_data") if items else []) or []
        return self._cps


class SgCarparkSource(Source):
    name = "sgcarpark"
    id_label = "CARPARK"
    cc_default = "sg"        # unused; one Singapore set
    deal_label = "fullrisk"  # <= 10 free car spaces = nearly full
    search_limit_default = 30
    search_header = f"{'FREE':>5}  {'TOTAL':>6}  CARPARK"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        cps = cl.carparks()
        return bool(cps), f"({len(cps)} HDB car parks; keyless data.gov.sg carpark-availability)"

    def search(self, cl, term, args):
        t = (term or "").upper()
        out = []
        for cp in cl.carparks():
            item, obs = _build(cp)
            if not t or t in item.name.upper():
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out

    def fetch(self, cl, item_id):
        for cp in cl.carparks():
            if str(cp.get("carpark_number")) == str(item_id):
                return _build(cp)
        return None

    def is_deal(self, obs):
        a = obs.flags.get("available")
        return a is not None and a <= 10

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('available')}/{f.get('total')} car spaces left  {item.name}  (nearly full)"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(f.get('available') if f.get('available') is not None else '?'):>5}  {(f.get('total') if f.get('total') is not None else '?'):>6}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  carpark  : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  free     : {f.get('available')} / {f.get('total')} car spaces")
            per = f.get("by_type") or {}
            extra = {k: v for k, v in per.items() if k != "C"}
            if extra:
                lines.append("  other    : " + ", ".join(f"{k} {v['avail']}/{v['total']}" for k, v in extra.items()))
            lines.append(f"  updated  : {f.get('updated') or '?'}")
        return lines


SOURCE = SgCarparkSource()
