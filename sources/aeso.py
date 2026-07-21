"""aeso - Alberta wholesale electricity pool price via the AESO public market report, keyless CSV.

The Alberta Electric System Operator runs a single-price energy-only market and publishes the live
System Marginal / Pool Price as a keyless public CSV:
`ets.aeso.ca/ets_web/ip/Market/Reports/SMPriceReportServlet?contentType=csv` returns the recent hourly
pool price ($/MWh), its 30-hour rolling average, and the Alberta Internal Load (AIL) demand, newest
hour first. The data host serves no robots.txt (404 = unfenced) and the report exists for public reuse
= sanctioned -> trove. The Canadian wholesale-electricity twin of `em6` (NZ) / `aemo` (AU) / `nyiso`
(US), opening **Alberta** and deepening the electricity genre.

The tracked scalar is the ephemeral dispatch price: Alberta's pool price is volatile (it can spike to
the ~$1000/MWh cap or sit near $0). Honest hoard value is low-med - AESO archives settled prices, the
octopus/nyiso class - but it completes CA electricity and the live snapshot is cheap to capture.
`price_cents` = pool price ($/MWh) * 100 so the core's `drops` = the price *falling*; `qty` = AIL demand
(MW, rounded). A "deal" ("cheap") = the current price is at or below its 30-hour rolling average.

Model: one Item, the Alberta pool price (join key = the constant `AB`). One memoized GET serves
search/fetch/poll; the latest *completed* hour (a numeric price, not the "-" placeholder for the hour in
progress) is the current value. `--cc` is unused - Alberta is a single-price market.
"""
from __future__ import annotations

import csv
import io

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

REPORT = "http://ets.aeso.ca/ets_web/ip/Market/Reports/SMPriceReportServlet?contentType=csv"
ITEM_ID = "AB"


def _f(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _latest(rows):
    """rows newest-first: the first with a numeric price is the last settled hour."""
    for r in rows:
        price = _f(r.get("price"))
        if price is not None:
            return r, price
    return None, None


def _build(rows):
    r, price = _latest(rows)
    if r is None:
        return None
    avg = _f(r.get("avg"))
    ail = _f(r.get("ail"))
    item = Item(ITEM_ID, name="Alberta pool price", subtitle="AESO wholesale electricity ($/MWh)",
                category="AB", extra={"market": "AESO", "unit": "$/MWh"})
    obs = Obs(price_cents=round(price * 100), qty=(round(ail) if ail is not None else None),
              flags={"price": price, "avg_30h": avg, "ail_mw": ail,
                     "hour": (r.get("date") or "").strip(), "unit": "$/MWh"})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._rows = None

    def rows(self):
        if self._rows is None:
            r = self.s.get(REPORT, headers={"User-Agent": UA}, timeout=45)
            r.raise_for_status()
            self._rows = self._parse(r.text)
        return self._rows

    @staticmethod
    def _parse(text):
        lines = text.splitlines()
        start = next((i for i, ln in enumerate(lines) if ln.startswith("Date (HE)")), None)
        if start is None:
            return []
        out = []
        for row in csv.reader(io.StringIO("\n".join(lines[start + 1:]))):
            if len(row) >= 4 and row[0].strip():
                out.append({"date": row[0], "price": row[1], "avg": row[2], "ail": row[3]})
        return out


class AesoSource(Source):
    name = "aeso"
    id_label = "MARKET"
    cc_default = "ab"        # unused
    deal_label = "cheap"     # current price at/below its 30-hour rolling average
    search_header = f"{'$/MWh':>8}  MARKET"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = cl.rows()
        r, price = _latest(rows)
        return price is not None, f"(Alberta pool price ${price}/MWh; {len(rows)} hours; keyless AESO SMP report)"

    def search(self, cl, term, args):
        built = _build(cl.rows())
        return [built] if built else []

    def fetch(self, cl, item_id):
        return _build(cl.rows())

    def is_deal(self, obs):
        p, avg = obs.flags.get("price"), obs.flags.get("avg_30h")
        return p is not None and avg is not None and p <= avg

    def deal_line(self, item, obs):
        f = obs.flags
        gap = (f"  ({f['price'] - f['avg_30h']:+.2f} vs 30h avg)"
               if f.get("avg_30h") is not None else "")
        return f"${f.get('price')}/MWh{gap}  (AIL {f.get('ail_mw')} MW)"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(str(f.get('price')) if f.get('price') is not None else '?'):>8}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  market   : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  price    : ${f.get('price')} / MWh   (hour ending {f.get('hour')})")
            lines.append(f"  30h avg  : ${f.get('avg_30h')} / MWh")
            lines.append(f"  demand   : {f.get('ail_mw')} MW  (Alberta Internal Load)")
        return lines


SOURCE = AesoSource()
