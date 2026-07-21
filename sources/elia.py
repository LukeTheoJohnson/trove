"""elia - Belgian electricity imbalance price via Elia's Open Data portal, keyless JSON.

Elia (the Belgian TSO) publishes its grid data through an Opendatasoft portal `opendata.elia.be`. The
near-real-time imbalance-price dataset (`ods134`) records, every 15 minutes, the system imbalance (MW),
the ACE, the marginal incremental/decremental prices and the resulting **imbalance price** (EUR/MWh) -
the price a balance-responsible party pays or is paid for being short/long. robots.txt is open and the
ODS API is published for reuse = sanctioned -> trove (the melbped/francefuel Opendatasoft class). Opens
**Belgium** electricity, twinning `em6`/`aeso`/`nyiso`/`energinet`/`ree`.

The imbalance price is genuinely ephemeral and can go **negative** (the system pays you to consume) or
spike hard when the grid is short. `price_cents` = the imbalance price (EUR/MWh) * 100 so the core's
`drops` = the price *falling* (toward/through zero); `qty` = the system imbalance (MW, rounded). A
"deal" ("negative") = the imbalance price is at or below zero - being long (consuming) is being paid.
The marginal increment/decrement prices and ACE ride in flags. money() renders EUR-per-MWh as '$'.

Model: one Item, the Belgian imbalance price (join key = the constant `imbalance`). One memoized GET
(order_by datetime desc, limit 1) gives the latest 15-minute value. `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://opendata.elia.be/api/explore/v2.1/catalog/datasets/ods134/records"
ITEM_ID = "imbalance"


def _f(v):
    return float(v) if isinstance(v, (int, float)) else None


def _build(rec):
    if not rec:
        return None
    price = _f(rec.get("imbalanceprice"))
    si = _f(rec.get("systemimbalance"))
    item = Item(ITEM_ID, name="Belgium imbalance price", subtitle="Elia imbalance settlement (EUR/MWh)",
                category="BE", extra={"market": "Elia", "unit": "EUR/MWh"})
    obs = Obs(price_cents=(round(price * 100) if price is not None else None),
              qty=(round(si) if si is not None else None),
              flags={"price": price, "system_imbalance_mw": si,
                     "marginal_incr": _f(rec.get("marginalincrementalprice")),
                     "marginal_decr": _f(rec.get("marginaldecrementalprice")),
                     "ace": _f(rec.get("ace")), "at": rec.get("datetime") or "",
                     "quality": rec.get("qualitystatus") or "", "unit": "EUR/MWh"})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._rec = None

    def latest(self):
        if self._rec is None:
            r = self.s.get(BASE, params={"limit": 1, "order_by": "datetime desc"},
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            results = (r.json() or {}).get("results") or []
            self._rec = results[0] if results else {}
        return self._rec


class EliaSource(Source):
    name = "elia"
    id_label = "MARKET"
    cc_default = "be"        # unused
    deal_label = "negative"  # imbalance price at or below zero (being long is paid)
    search_header = f"{'EUR/MWh':>9}  MARKET"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rec = cl.latest()
        p = _f(rec.get("imbalanceprice"))
        return p is not None, f"(Belgium imbalance price {p} EUR/MWh; keyless Elia Open Data ods134)"

    def search(self, cl, term, args):
        built = _build(cl.latest())
        return [built] if built else []

    def fetch(self, cl, item_id):
        return _build(cl.latest())

    def is_deal(self, obs):
        p = obs.flags.get("price")
        return p is not None and p <= 0

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('price')} EUR/MWh  (system imbalance {f.get('system_imbalance_mw')} MW)  {item.name}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(str(f.get('price')) if f.get('price') is not None else '?'):>9}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  market   : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  price    : {f.get('price')} EUR/MWh   (at {f.get('at')}, {f.get('quality')})")
            lines.append(f"  imbalance: {f.get('system_imbalance_mw')} MW   ACE {f.get('ace')}")
            lines.append(f"  marginal : +{f.get('marginal_incr')} / -{f.get('marginal_decr')} EUR/MWh")
        return lines


SOURCE = EliaSource()
