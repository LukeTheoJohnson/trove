"""elexon - GB wholesale electricity market index price via Elexon BMRS Insights, keyless JSON.

Elexon runs the GB electricity balancing/settlement system and publishes its market data through the
keyless BMRS Insights API `data.elexon.co.uk/bmrs/api/v1/...`. The Market Index Data endpoint
`.../balancing/pricing/market-index` returns the half-hourly reference price (GBP/MWh) and traded
volume per settlement period from the APX (EPEX) and N2EX exchanges. The data host serves no
robots.txt for the API path (404 = unfenced) and BMRS exists for public/market reuse = sanctioned ->
trove. The GB wholesale-spot twin of `em6`/`aemo`/`nyiso`/`aeso` and the wholesale complement to
`octopus` (GB retail) + `carbonintensity` (GB grid mix).

The tracked scalar is the ephemeral half-hourly clearing price. Honest hoard value is low-med (Elexon
archives settled data - the nyiso/octopus class), but it deepens GB electricity with the wholesale
reference. `price_cents` = the APX market-index price (GBP/MWh) * 100 so the core's `drops` = the price
*falling*; `qty` = traded volume (MWh, rounded). A "deal" ("cheap") = the current period's price is at
or below today's mean so far.

Model: one Item, the GB APX market index (join key = the constant `APXMIDP`). One memoized GET spans
today's periods; the latest settlement period is the current price and today's mean is the deal
baseline. `--cc` is unused - one GB market.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index"
PROVIDER = "APXMIDP"       # the APX (EPEX) reference; N2EXMIDP often has no trades (0.0)
ITEM_ID = "APXMIDP"


def _f(v):
    return float(v) if isinstance(v, (int, float)) else None


def _build(rows):
    """rows = today's APX market-index records. Latest period = current; mean = deal baseline."""
    priced = [r for r in rows if _f(r.get("price")) is not None]
    if not priced:
        return None
    priced.sort(key=lambda r: (r.get("startTime") or "", r.get("settlementPeriod") or 0))
    cur = priced[-1]
    vals = [_f(r.get("price")) for r in priced]
    mean = round(sum(vals) / len(vals), 2)
    price = _f(cur.get("price"))
    vol = _f(cur.get("volume"))
    item = Item(ITEM_ID, name="GB market index (APX)", subtitle="Elexon BMRS half-hourly reference (GBP/MWh)",
                category="GB", extra={"provider": PROVIDER, "unit": "GBP/MWh"})
    obs = Obs(price_cents=round(price * 100), qty=(round(vol) if vol is not None else None),
              flags={"price": price, "day_mean": mean, "volume": vol,
                     "period": cur.get("settlementPeriod"), "start": cur.get("startTime") or "",
                     "settlement_date": cur.get("settlementDate") or "", "unit": "GBP/MWh"})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._rows = None

    def rows(self):
        if self._rows is None:
            now = datetime.now(timezone.utc)
            frm = now.replace(hour=0, minute=0, second=0, microsecond=0)
            to = now + timedelta(minutes=30)
            r = self.s.get(BASE, params={"from": frm.strftime("%Y-%m-%dT%H:%MZ"),
                                         "to": to.strftime("%Y-%m-%dT%H:%MZ")},
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            data = (r.json() or {}).get("data") or []
            self._rows = [d for d in data if (d.get("dataProvider") or "") == PROVIDER]
        return self._rows


class ElexonSource(Source):
    name = "elexon"
    id_label = "MARKET"
    cc_default = "gb"        # unused
    deal_label = "cheap"     # current period at/below today's mean so far
    search_header = f"{'GBP/MWh':>9}  MARKET"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = cl.rows()
        built = _build(rows)
        p = built[1].flags.get("price") if built else None
        return built is not None, f"(GB APX market index {p} GBP/MWh; {len(rows)} periods today; keyless Elexon BMRS)"

    def search(self, cl, term, args):
        built = _build(cl.rows())
        return [built] if built else []

    def fetch(self, cl, item_id):
        return _build(cl.rows())

    def is_deal(self, obs):
        p, mean = obs.flags.get("price"), obs.flags.get("day_mean")
        return p is not None and mean is not None and p <= mean

    def deal_line(self, item, obs):
        f = obs.flags
        gap = (f"  ({f['price'] - f['day_mean']:+.2f} vs day mean)"
               if f.get("day_mean") is not None else "")
        return f"{f.get('price')} GBP/MWh{gap}  (period {f.get('period')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(str(f.get('price')) if f.get('price') is not None else '?'):>9}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  market   : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  price    : {f.get('price')} GBP/MWh   (SP{f.get('period')}, {f.get('start')})")
            lines.append(f"  day mean : {f.get('day_mean')} GBP/MWh   volume {f.get('volume')} MWh")
        return lines


SOURCE = ElexonSource()
