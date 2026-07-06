"""awattar - Germany/Austria EPEX day-ahead wholesale electricity price, keyless (+ deep backfill).

aWATTar (a German/Austrian dynamic-tariff retailer) exposes the EPEX day-ahead spot price at
api.awattar.de (Germany) and api.awattar.at (Austria). `GET /v1/marketdata` returns the hourly market
price (Eur/MWh) for the current and upcoming delivery hours, and accepts `?start=&end=` epoch-ms to
return any past range. Neither host serves a robots.txt (Express "Cannot GET /robots.txt" = unfenced)
and the feed is published for exactly this reuse = sanctioned -> trove. The European mate for the
wholesale-electricity set (`em6` NZ, `aemo` AU) - the same market cadence a third continent over,
where the price can go **negative** when renewables overproduce.

Honest hoard value is **low**: like `frankfurter`/`octopus`, the same endpoint serves the full realized
history (paginated by `start`/`end`), so the series is rebuildable. What this build demonstrates is the
core's **backdated-history channel** (`Obs.history`, merged idempotently as tag `hist`): the first
`item` seeds ~90 days of hourly prices in one GET (each row backdated to its delivery hour), and each
`poll` appends only the new tail. `price_cents` = the current hour's price (Eur/MWh) * 100, so the core's
`drops` = the spot price *falling* (negative = a plunge); `qty` is unused. A "deal" ("cheap") = the
current hour is at or below the trailing window average (a cheaper hour to run load), negative flagged.
money() renders the centi-euro price as dollars in the two core-hardcoded spots.

Model: one Item per market (join key = the country code, `de` / `at`, chosen by `--cc`; default `de`).
`search` lists the market with its current price (there is no free-text search); `fetch` seeds the deep
history, `refresh` (poll) appends the recent window.
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money

HOSTS = {"de": "https://api.awattar.de", "at": "https://api.awattar.at"}
NAMES = {"de": "Germany", "at": "Austria"}
DAY_MS = 86_400_000


def _ts(epoch_ms):
    return datetime.fromtimestamp(epoch_ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _cents(mp):
    try:
        return round(float(mp) * 100)
    except (TypeError, ValueError):
        return None


class _Client:
    def __init__(self, cc):
        self.cc = cc if cc in HOSTS else "de"
        self.s = retry_session()

    def marketdata(self, start_ms=None, end_ms=None):
        # aWATTar returns the current + next day by default; a past range needs BOTH start AND end.
        params = {}
        if start_ms is not None:
            params["start"] = int(start_ms)
        if end_ms is not None:
            params["end"] = int(end_ms)
        r = self.s.get(f"{HOSTS[self.cc]}/v1/marketdata", params=params,
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return (r.json() or {}).get("data") or []


def _build(cc, rows):
    """rows = hourly EPEX slots (each: start_timestamp ms, marketprice Eur/MWh). Head obs = the hour
    covering 'now' (fallback: first row); history = every row backdated to its delivery hour."""
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    prices = [c for c in (_cents(r.get("marketprice")) for r in rows) if c is not None]
    avg = round(sum(prices) / len(prices)) if prices else None
    cur = None
    for r in rows:
        st = r.get("start_timestamp")
        if st is not None and st <= now_ms < r.get("end_timestamp", st + 3_600_000):
            cur = r
            break
    if cur is None and rows:
        cur = rows[0]
    hist = [Obs(price_cents=_cents(r.get("marketprice")), ts=_ts(r.get("start_timestamp")),
                flags={"unit": "Eur/MWh"})
            for r in rows if r.get("start_timestamp") is not None]
    item = Item(cc, name=f"{NAMES.get(cc, cc)} (EPEX day-ahead)",
                subtitle="wholesale electricity spot (Eur/MWh)", category="market",
                extra={"market": cc})
    obs = Obs(price_cents=_cents(cur.get("marketprice")) if cur else None,
              flags={"unit": "Eur/MWh", "window_avg": avg, "hours": len(rows),
                     "current_from": _ts(cur.get("start_timestamp")) if cur else None},
              history=hist)
    return item, obs


class AwattarSource(Source):
    name = "awattar"
    id_label = "MARKET"
    cc_default = "de"
    deal_label = "cheap"     # current hour at/below the trailing window average
    search_header = f"{'PRICE':>9}  MARKET"

    def client(self, args):
        return _Client(getattr(args, "cc", "de"))

    def doctor(self, cl):
        rows = cl.marketdata()
        return bool(rows), f"({NAMES.get(cl.cc)}: {len(rows)} hourly slots; keyless aWATTar EPEX marketdata)"

    def search(self, cl, term, args):
        rows = cl.marketdata()
        return [_build(cl.cc, rows)]

    def fetch(self, cl, item_id):
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        rows = cl.marketdata(start_ms=now_ms - 90 * DAY_MS, end_ms=now_ms + DAY_MS)
        return _build(item_id if item_id in HOSTS else cl.cc, rows)

    def refresh(self, cl, item_id):
        rows = cl.marketdata()
        return _build(item_id if item_id in HOSTS else cl.cc, rows)

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("window_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        avg = obs.flags.get("window_avg")
        gap = f"  ({(obs.price_cents - avg) / 100:+.2f} vs window avg)" if avg is not None and obs.price_cents is not None else ""
        neg = "  NEGATIVE" if (obs.price_cents is not None and obs.price_cents < 0) else ""
        return f"{money(obs.price_cents)}/MWh{gap}{neg}  {item.name}"

    def search_row(self, item, obs):
        return f"{money(obs.price_cents) if obs else '?':>9}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  market   : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  price    : {money(obs.price_cents)} / MWh   (hour from {f.get('current_from') or '?'} UTC)")
            avg = f.get("window_avg")
            if avg is not None and obs.price_cents is not None:
                lines.append(f"  window   : avg {money(avg)} / MWh over {f.get('hours')} slots   (now {(obs.price_cents - avg) / 100:+.2f})")
        return lines


SOURCE = AwattarSource()
