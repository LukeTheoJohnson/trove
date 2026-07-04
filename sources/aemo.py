"""aemo - Australian National Electricity Market (NEM) real-time regional spot prices, keyless JSON.

AEMO (the Australian Energy Market Operator) drives the public market-transparency dashboards at
visualisations.aemo.com.au, which call a keyless report API. `GET .../aemo/apps/api/report/
ELEC_NEM_SUMMARY` returns the current 5-minute dispatch summary for each of the five NEM regions
(NSW1, QLD1, SA1, TAS1, VIC1): spot price ($/MWh), total demand (MW), scheduled + semi-scheduled
generation, net interchange, and the interconnector flows. The host has no robots.txt (404 =
unfenced) and the endpoint is the one the page itself calls = sanctioned -> trove. The AU twin of
`em6` (NZ), completing the wholesale-electricity genre across the Tasman.

The timeline value is the *ephemeral dispatch price*: the NEM price resets every 5-minute dispatch
interval, and while AEMO archives settled prices, the live per-region snapshot + demand + generation
mix at each interval is the cheap-to-capture record this hoards. `price_cents` = spot price ($/MWh) *
100 (so the core's `drops` = the price *falling*; NEM prices can go **negative** at high renewable
output, a plunge signal), `qty` = total demand (MW). A "deal" = the region is at or below the
five-region average for the current interval (a cheaper place to draw power right now); the demand,
generation split and interconnector flows ride in flags.

Model: one Item per NEM region (join key = REGIONID). `search` lists/filters the five regions by name
substring (one call returns them all; no free-text search). `--cc` is unused - the whole market is one
set of regions.
"""
from __future__ import annotations

import json

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://visualisations.aemo.com.au/aemo/apps/api/report/ELEC_NEM_SUMMARY"
REGION_NAMES = {"NSW1": "New South Wales", "QLD1": "Queensland", "SA1": "South Australia",
                "TAS1": "Tasmania", "VIC1": "Victoria"}


def _cents(price):
    try:
        return round(float(price) * 100)
    except (TypeError, ValueError):
        return None


def _avg_cents(rows):
    vals = [c for c in (_cents(r.get("PRICE")) for r in rows) if c is not None]
    return round(sum(vals) / len(vals)) if vals else None


def _flows(raw):
    """INTERCONNECTORFLOWS arrives as a JSON *string*; parse to [{name, value}] or []."""
    try:
        return [{"name": f.get("name"), "value": round(float(f.get("value")), 1)}
                for f in json.loads(raw)]
    except (TypeError, ValueError):
        return []


def _region(r, avg_cents):
    rid = str(r.get("REGIONID", ""))
    pc = _cents(r.get("PRICE"))
    demand = r.get("TOTALDEMAND")
    item = Item(rid, name=REGION_NAMES.get(rid, rid),
                subtitle="NEM wholesale electricity spot ($/MWh)", category="spot",
                extra={"region_id": rid})
    obs = Obs(price_cents=pc,
              qty=(round(demand) if isinstance(demand, (int, float)) else None),
              flags={"unit": "$/MWh", "price_status": r.get("PRICE_STATUS"),
                     "demand_mw": demand, "settlement": r.get("SETTLEMENTDATE"),
                     "scheduled_gen": r.get("SCHEDULEDGENERATION"),
                     "semischeduled_gen": r.get("SEMISCHEDULEDGENERATION"),
                     "net_interchange": r.get("NETINTERCHANGE"),
                     "interconnectors": _flows(r.get("INTERCONNECTORFLOWS")),
                     "nem_avg": avg_cents})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._rows = None

    def rows(self):
        if self._rows is None:
            r = self.s.get(BASE, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._rows = (r.json() or {}).get("ELEC_NEM_SUMMARY") or []
        return self._rows


class AemoSource(Source):
    name = "aemo"
    id_label = "REGION"
    cc_default = "au"        # unused; the NEM is one set of regions
    deal_label = "deal"      # deal = at/below the five-region average this interval

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = cl.rows()
        return bool(rows), f"({len(rows)} NEM regions; keyless AEMO ELEC_NEM_SUMMARY)"

    def search(self, cl, term, args):
        rows = cl.rows()
        avg = _avg_cents(rows)
        t = (term or "").lower()
        out = []
        for r in rows:
            rid = str(r.get("REGIONID", ""))
            if not t or t in rid.lower() or t in REGION_NAMES.get(rid, "").lower():
                out.append(_region(r, avg))
        return out

    def fetch(self, cl, item_id):
        rows = cl.rows()
        avg = _avg_cents(rows)
        for r in rows:
            if str(r.get("REGIONID")) == str(item_id):
                return _region(r, avg)
        return None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("nem_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        avg = obs.flags.get("nem_avg")
        gap = (f"  ({(obs.price_cents - avg) / 100:+.2f} vs NEM avg)"
               if avg is not None and obs.price_cents is not None else "")
        neg = "  NEGATIVE" if (obs.price_cents is not None and obs.price_cents < 0) else ""
        return f"{money(obs.price_cents)}/MWh{gap}{neg}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  region   : {item.name}  ({item.id})"]
        if obs:
            f = obs.flags
            lines.append(f"  spot     : {money(obs.price_cents)} / MWh  ({f.get('price_status', '?')})")
            lines.append(f"  demand   : {f.get('demand_mw', '?')} MW")
            lines.append(f"  interval : {f.get('settlement', '?')}")
            avg = f.get("nem_avg")
            if avg is not None and obs.price_cents is not None:
                lines.append(f"  NEM avg  : {money(avg)} / MWh   (this region {(obs.price_cents - avg) / 100:+.2f})")
            ic = f.get("interconnectors") or []
            if ic:
                lines.append("  flows    : " + ", ".join(f"{safe(x['name'])} {x['value']}MW" for x in ic))
        return lines


SOURCE = AemoSource()
