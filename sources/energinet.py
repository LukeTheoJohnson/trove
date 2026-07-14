"""energinet - Nordic/DE day-ahead electricity price per bidding zone, keyless (Energinet, DK).

Energinet (the Danish national TSO) publishes the Nordic power market as keyless open data through
`api.energidataservice.dk` (the host serves no robots.txt = 404 = unfenced; the service exists for
public reuse = sanctioned -> trove). The `DayAheadPrices` dataset carries the day-ahead auction price
(EUR + DKK per MWh) for each bidding zone Energinet settles against - DK1, DK2 (Denmark), plus the
neighbours the Danish grid couples to: DE (Germany), NO2 (south Norway), SE3/SE4 (Sweden). The
EU/Nordic twin of `em6` (NZ) / `aemo` (AU) / `nyiso` (US), extending the deepest genre into the
Continent's most interconnected market. (Energinet froze the old `Elspotprices` dataset at 2025-09-30
and moved live prices to `DayAheadPrices` at 15-minute resolution - this reads the live one.)

The tracked scalar is the *ephemeral zonal price*: each 15-minute interval clears at its own price and,
while Energinet archives settled prices, the live cross-zone snapshot is the cheap-to-capture record
this hoards (honest hoard value low-med - the realized series is rebuildable from the archive, the
nyiso/octopus class; it earns its place by completing EU electricity + the coupling spread between
zones). `price_cents` = the day-ahead price (EUR/MWh) * 100 so the core's `drops` = the price *falling*
(Nordic zonal prices swing hard and can even go negative on windy oversupply); `qty` = None. A "deal"
= the zone is at or below the average across all zones this interval (the cheaper place to draw power
right now) OR the price is negative (paid to consume); the DKK price + interval ride in flags.

Model: one Item per bidding zone (join key = the PriceArea code). One GET (bounded to the interval
around now) returns every zone's current price; `--cc` is unused - the market is one set of zones.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

BASE = "https://api.energidataservice.dk/dataset/DayAheadPrices"
AREA_NAMES = {
    "DK1": "West Denmark (DK1)", "DK2": "East Denmark (DK2)", "DE": "Germany (DE-LU)",
    "NO2": "South Norway (NO2)", "SE3": "Central Sweden (SE3)", "SE4": "South Sweden (SE4)",
}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _latest_by_area(records):
    """DayAheadPrices rows -> {area: the row with the newest TimeUTC} (the current interval)."""
    out = {}
    for r in records:
        a = (r.get("PriceArea") or "").strip()
        if not a:
            continue
        prev = out.get(a)
        if prev is None or (r.get("TimeUTC") or "") > (prev.get("TimeUTC") or ""):
            out[a] = r
    return out


def _avg_cents(area_rows):
    vals = [round(p * 100) for p in (_f(r.get("DayAheadPriceEUR")) for r in area_rows.values()) if p is not None]
    return round(sum(vals) / len(vals)) if vals else None


def _build(r, avg):
    a = (r.get("PriceArea") or "").strip()
    eur = _f(r.get("DayAheadPriceEUR"))
    item = Item(a, name=AREA_NAMES.get(a, a), subtitle="Energinet day-ahead price (EUR/MWh)",
                category="bidding zone", extra={"area": a})
    obs = Obs(price_cents=(round(eur * 100) if eur is not None else None),
              qty=None,
              flags={"unit": "EUR/MWh", "eur": eur, "dkk": _f(r.get("DayAheadPriceDKK")),
                     "area": a, "time_utc": (r.get("TimeUTC") or "").strip(),
                     "time_dk": (r.get("TimeDK") or "").strip(), "eu_avg": avg})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._areas = None

    def areas(self):
        if self._areas is None:
            # bound to the interval around now (the feed also carries future day-ahead hours;
            # a plain DESC would return tomorrow's prices, not the one clearing right now).
            now = datetime.now(timezone.utc)
            start = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")
            end = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M")
            url = f"{BASE}?start={start}&end={end}&sort=TimeUTC%20DESC&limit=200"
            r = self.s.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=40)
            r.raise_for_status()
            self._areas = _latest_by_area((r.json() or {}).get("records") or [])
        return self._areas


def _eur(cents):
    return "?" if cents is None else f"{cents / 100:,.2f}"


class EnerginetSource(Source):
    name = "energinet"
    id_label = "ZONE"
    cc_default = "dk"        # unused; the market is one set of bidding zones
    deal_label = "cheap"     # at/below the all-zone average this interval (or negative)
    search_header = f"{'EUR/MWh':>10}  ZONE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        a = cl.areas()
        return bool(a), f"({len(a)} bidding zones priced now; keyless Energinet DayAheadPrices)"

    def search(self, cl, term, args):
        areas = cl.areas()
        avg = _avg_cents(areas)
        t = (term or "").lower()
        out = [_build(r, avg) for a, r in areas.items()
               if not t or t in a.lower() or t in AREA_NAMES.get(a, "").lower()]
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out

    def fetch(self, cl, item_id):
        areas = cl.areas()
        avg = _avg_cents(areas)
        r = areas.get(str(item_id).strip().upper())
        return _build(r, avg) if r else None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("eu_avg")
        return pc is not None and ((avg is not None and pc <= avg) or pc < 0)

    def deal_line(self, item, obs):
        avg = obs.flags.get("eu_avg")
        gap = (f"  ({(obs.price_cents - avg) / 100:+.2f} vs zone avg)"
               if avg is not None and obs.price_cents is not None else "")
        neg = "  NEGATIVE (paid to consume)" if (obs.price_cents is not None and obs.price_cents < 0) else ""
        return f"{_eur(obs.price_cents)} EUR/MWh{gap}  {item.name}{neg}"

    def search_row(self, item, obs):
        pc = obs.price_cents if obs else None
        return f"{_eur(pc):>10}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  zone     : {item.name}  ({item.extra.get('area', '?')})"]
        if obs:
            f = obs.flags
            lines.append(f"  price    : {_eur(obs.price_cents)} EUR/MWh   ({f.get('dkk', '?')} DKK)")
            avg = f.get("eu_avg")
            if avg is not None and obs.price_cents is not None:
                lines.append(f"  zone avg : {_eur(avg)} EUR/MWh   (this zone {(obs.price_cents - avg) / 100:+.2f})")
            lines.append(f"  interval : {f.get('time_utc', '?')} UTC   ({f.get('time_dk', '?')} DK)")
        return lines


SOURCE = EnerginetSource()
