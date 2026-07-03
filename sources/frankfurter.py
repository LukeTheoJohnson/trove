"""frankfurter - ECB daily reference FX rates (keyless open-source API): the instant-depth hoard.

Frankfurter (api.frankfurter.dev, open source, keyless, robots `Allow: /`) republishes the European
Central Bank's daily reference exchange rates - ~30 currencies, one fixing per CET working day,
back to 1999-01-04. Its range endpoint hands over the *entire* daily series for a pair in one GET
(~7,000 rows, ~200 KB), which is exactly what the Obs.history channel exists for: the first `item`
call seeds 27 years of daily rates into the obs log with their real dates (tag `hist`), and every
later fetch appends only the unseen tail. One poll = decades of history, zero scrape loop.

Honest hoard value: **low (PoC / capability)** - ECB reference rates are permanently archived, so
the series is rebuildable anytime. The draw is (1) the instant-depth ingestion pattern itself, and
(2) a genuinely useful daily signal for anyone paying USD invoices from NZD: is the rate favourable
right now, against the last year?

Model: one Item per directed currency pair (join key = `BASE:QUOTE`, e.g. `NZD:USD`). `price_cents`
= rate * 10,000 (ten-thousandths, pip-style: 0.56709 stores as 5671), so the core's `drops` = the
base currency *weakening* - and with the 1999 epoch seeded as first-seen, `drops` literally means
"below its 1999-01-04 level". money() cosmetically renders the scaled rate as dollars in the two
core-hardcoded spots (geonet/metno precedent); rich displays show the proper 4-dp rate. `qty` = the
current rate's percentile (0-100) within the trailing year, and the deal "high" = percentile >= 90
(the base is stronger than ~all of the past year - a good moment to convert). Dates are ECB CET
fixing dates stored as `YYYY-MM-DD 00:00:00`; no intraday resolution exists or is implied.

`search` lists pairs from the base currency picked by `--cc` (default nz -> NZD) via the one-GET
`/latest` snapshot; `item` pulls the full-epoch series (the deep seed); `poll` uses a lean trailing
~400-day window - enough to compute the 1y percentile and extend the tail without re-shipping the
whole epoch every day.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from trove.db import Item, Obs
from trove.session import retry_session, UA

from trove.tracker import Source

BASE = "https://api.frankfurter.dev/v1"
EPOCH = "1999-01-04"        # first ECB reference-rate date; the range endpoint's floor
SCALE = 10000               # price_cents = rate * SCALE (ten-thousandths of the quote unit)
POLL_WINDOW_DAYS = 400      # lean refresh window: covers the trailing year + holiday slack
HIGH_PCTILE = 90            # deal "high" = current rate at/above this trailing-1y percentile


def _cents(rate):
    try:
        return round(float(rate) * SCALE)
    except (TypeError, ValueError):
        return None


def _rate_s(cents):
    """Render the stored ten-thousandths scalar as a proper 4-dp rate for the rich displays."""
    return "?" if cents is None else f"{cents / SCALE:.4f}"


def _pair(item_id):
    base, _, quote = str(item_id).upper().partition(":")
    return (base.strip(), quote.strip()) if base.strip() and quote.strip() else (None, None)


def _pair_item(base, quote, names):
    return Item(f"{base}:{quote}", name=f"{base}/{quote}",
                subtitle=f"{names.get(base, base)} -> {names.get(quote, quote)} (ECB reference rate)",
                category="fx",
                extra={"base": base, "quote": quote,
                       "base_name": names.get(base, base), "quote_name": names.get(quote, quote)})


def _series_obs(rates, quote):
    """A pair's dated series {date: {QUOTE: rate}} -> current Obs + full backdated history."""
    dated = sorted((d, r.get(quote)) for d, r in rates.items() if r.get(quote) is not None)
    if not dated:
        return None
    hist = [Obs(price_cents=_cents(v), ts=f"{d} 00:00:00") for d, v in dated]
    last_date, cur = dated[-1]
    cutoff = (datetime.strptime(last_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
    window = [v for d, v in dated if d >= cutoff]
    pctile = round(100 * sum(1 for v in window if v <= cur) / len(window))
    return Obs(price_cents=_cents(cur), qty=pctile,
               flags={"rate": cur, "date": last_date, "pctile_1y": pctile,
                      "lo_1y": min(window), "hi_1y": max(window),
                      "n_days": len(dated), "since": dated[0][0], "src": "series"},
               history=hist)


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._cache = {}

    def _get(self, path, params=None):
        key = (path, tuple(sorted((params or {}).items())))
        if key not in self._cache:
            r = self.s.get(f"{BASE}/{path}", params=params or {},
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=60)
            r.raise_for_status()
            self._cache[key] = r.json() or {}
        return self._cache[key]

    def currencies(self):
        return self._get("currencies")

    def latest(self, base):
        return self._get("latest", {"base": base})

    def series(self, base, quote, start):
        """Every daily fixing for one pair since `start`, in a single GET."""
        return self._get(f"{start}..", {"base": base, "symbols": quote})


class FrankfurterSource(Source):
    name = "frankfurter"
    id_label = "PAIR"
    cc_default = "nzd"      # base currency for `search` (any ECB-covered code)
    deal_label = "high"     # base at/above the 90th percentile of its trailing year
    search_header = f"{'RATE':>10}  PAIR  (quote currency)"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        cur = cl.currencies()
        return bool(cur), f"({len(cur)} currencies; keyless Frankfurter/ECB API, daily since {EPOCH})"

    def search(self, cl, term, args):
        base = str(getattr(args, "cc", self.cc_default) or self.cc_default).upper()
        names = cl.currencies()
        snap = cl.latest(base)
        t = (term or "").lower()
        out = []
        for quote, rate in sorted((snap.get("rates") or {}).items()):
            if t and t not in quote.lower() and t not in names.get(quote, "").lower():
                continue
            out.append((_pair_item(base, quote, names),
                        Obs(price_cents=_cents(rate),
                            flags={"rate": rate, "date": snap.get("date"), "src": "latest"})))
        return out

    def fetch(self, cl, item_id):
        return self._build(cl, item_id, EPOCH)

    def refresh(self, cl, item_id):
        start = (datetime.now(timezone.utc) - timedelta(days=POLL_WINDOW_DAYS)).strftime("%Y-%m-%d")
        return self._build(cl, item_id, start)

    def _build(self, cl, item_id, start):
        base, quote = _pair(item_id)
        if not base or not quote or base == quote:
            return None
        try:
            payload = cl.series(base, quote, start)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (404, 422):
                return None         # unknown currency code -> not a pair Frankfurter serves
            raise
        obs = _series_obs(payload.get("rates") or {}, quote)
        if obs is None:
            return None
        return _pair_item(base, quote, cl.currencies()), obs

    def is_deal(self, obs):
        p = obs.flags.get("pctile_1y")
        return p is not None and p >= HIGH_PCTILE

    def search_row(self, item, obs):
        return (f"{_rate_s(obs.price_cents) if obs else '?':>10}  {item.name}  "
                f"({item.extra.get('quote_name', '')})")

    def deal_line(self, item, obs):
        f = obs.flags
        return (f"{_rate_s(obs.price_cents)}  {item.name}  at {f.get('pctile_1y', '?')}th pctile of 1y "
                f"({f.get('lo_1y', '?')} - {f.get('hi_1y', '?')})")

    def format_item(self, item, obs):
        lines = [f"  pair      : {item.name}  ({item.extra.get('base_name', '')} -> {item.extra.get('quote_name', '')})"]
        if obs:
            f = obs.flags
            lines.append(f"  rate      : {_rate_s(obs.price_cents)}  (ECB fixing, {f.get('date', '?')})")
            if f.get("lo_1y") is not None:
                lines.append(f"  1y range  : {f['lo_1y']:.4f} - {f['hi_1y']:.4f}   (current at {f.get('pctile_1y', '?')}th percentile)")
            if f.get("n_days"):
                lines.append(f"  hoard     : {f['n_days']} daily fixings since {f.get('since', '?')} (seeded into the obs log)")
        return lines


SOURCE = FrankfurterSource()
