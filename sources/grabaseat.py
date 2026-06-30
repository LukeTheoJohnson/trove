"""grabaseat - Air NZ's cheap-fares site (grabaseat.co.nz), keyless same-origin fare API.

The page's own fare-finder calls `https://www.grabaseat.co.nz/api/v3/lowfarefinder/{origin}/{dest}`
(keyless, robots `allow: /`) and gets back the cheapest fare per day for the next ~30 days on that
route, plus the headline `lowestPrice` across the window. The timeline value is the *ephemeral
cheapest fare*: airfares move daily and nobody archives the per-route low, so the snapshot is the
only record - the whole point of hoarding it, and the engine's drop detection turns a watched route
into a "the fare just dropped" alert.

Model: one Item per route (join key = "ORIGIN-DEST", e.g. "AKL-WLG"), tracking the window's
`lowestPrice` as price_cents (NZD), with the cheapest date, the 30-day fare board, and its
average/min/max carried in flags. A "deal" = the cheapest fare is a standout dip - at least 20%
under the route's own 30-day average (a genuine cheap day, not a flatly-priced board).

`search` takes a destination code with `--cc` as the origin (default AKL), or a full "AKL-WLG"
route; `item`/`poll` re-fetch one route. The fare-finder is per-route, so there is no list-all
endpoint - the route is always explicit.
"""
from __future__ import annotations

import re

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money

BASE = "https://www.grabaseat.co.nz/api/v3/lowfarefinder"


def _route(term, cc):
    """Parse 'AKL-WLG' / 'AKL WLG' / (dest, --cc origin) into (origin, dest) upper-case codes."""
    toks = [t for t in re.split(r"[-/,\s]+", (term or "").strip().upper()) if t]
    if len(toks) >= 2:
        return toks[0], toks[1]
    if len(toks) == 1:
        return cc.strip().upper(), toks[0]
    return None, None


def _build(origin, dest, data):
    fares = data.get("lowFares") or []
    prices = [f.get("farePrice") for f in fares if isinstance(f.get("farePrice"), (int, float))]
    low = data.get("lowestPrice")
    if low is None and prices:
        low = min(prices)
    if low is None:
        return None
    avg_c = round(sum(prices) / len(prices) * 100) if prices else None
    cheapest = min(fares, key=lambda f: f.get("farePrice", 1e9)) if fares else {}
    rid = f"{origin}-{dest}"
    item = Item(rid, name=f"{origin}->{dest}",
                subtitle="Air NZ grabaseat lowest fare",
                category=f"from {origin}",
                extra={"origin": origin, "destination": dest, "book_url": cheapest.get("bookUrl")})
    obs = Obs(price_cents=round(low * 100),
              flags={"currency": "NZD",
                     "lowest_date": cheapest.get("outboundDate"),
                     "avg_cents": avg_c,
                     "min_cents": round(min(prices) * 100) if prices else None,
                     "max_cents": round(max(prices) * 100) if prices else None,
                     "n_fares": len(prices),
                     "board": [{"d": f.get("outboundDate"), "p": f.get("farePrice")} for f in fares]})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()

    def route(self, origin, dest):
        r = self.s.get(f"{BASE}/{origin}/{dest}",
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        if r.status_code != 200:
            return None
        try:
            return r.json()
        except ValueError:
            return None


class GrabaSeatSource(Source):
    name = "grabaseat"
    id_label = "ROUTE"
    cc_default = "AKL"        # origin airport when search gets only a destination code
    deal_label = "fare deal"  # deal = cheapest fare >= 20% under the route's 30-day average

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        d = cl.route("AKL", "WLG")
        ok = bool(d and d.get("lowestPrice") is not None)
        return ok, "(keyless grabaseat lowfarefinder; AKL-WLG probe)" if ok else "(no fare data)"

    def search(self, cl, term, args):
        origin, dest = _route(term, args.cc)
        if not origin or not dest:
            return []
        d = cl.route(origin, dest)
        built = _build(origin, dest, d) if d else None
        return [built] if built else []

    def fetch(self, cl, item_id):
        origin, _, dest = str(item_id).upper().partition("-")
        if not origin or not dest:
            return None
        d = cl.route(origin, dest)
        return _build(origin, dest, d) if d else None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("avg_cents")
        return pc is not None and avg is not None and pc <= round(0.8 * avg)

    def deal_line(self, item, obs):
        avg = obs.flags.get("avg_cents")
        pct = f"  ({round((1 - obs.price_cents / avg) * 100)}% under 30d avg {money(avg)})" \
            if avg else ""
        when = obs.flags.get("lowest_date")
        return f"{money(obs.price_cents)}  {item.name}  cheapest {when}{pct}"

    def format_item(self, item, obs):
        lines = [f"  route    : {item.extra.get('origin', '')} -> {item.extra.get('destination', '')}"]
        if obs:
            f = obs.flags
            lines.append(f"  lowest   : {money(obs.price_cents)}  on {f.get('lowest_date')}")
            if f.get("avg_cents"):
                lines.append(f"  30d board: avg {money(f.get('avg_cents'))}  "
                             f"min {money(f.get('min_cents'))}  max {money(f.get('max_cents'))}  "
                             f"({f.get('n_fares')} days)")
            board = sorted((f.get("board") or []), key=lambda x: x.get("p", 1e9))[:3]
            for b in board:
                lines.append(f"    {b.get('d')}   ${b.get('p')}")
        lines.append(f"  book     : {item.extra.get('book_url', '')}")
        return lines


SOURCE = GrabaSeatSource()
