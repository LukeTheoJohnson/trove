"""paralelobo - Bolivia's parallel-market (black-market) USD/BOB exchange rate, keyless.

Bolivia pegs its official USD rate at ~6.96 BOB, but dollars trade far higher on the parallel market;
paralelo.bo aggregates that street/P2P rate from crypto-exchange order books (Binance, Bybit, OKX...).
`GET /api/rate` returns the current aggregated buy/sell/median rate + spread + the per-source
breakdown. robots fences only `/api/admin/` (never `/api/rate`), and the endpoint is the one the site's
own page calls = sanctioned -> trove. Opens **LatAm macro** and a genuinely novel signal.

This is a rare **un-rebuildable** currency series: unlike ECB/official rates (the frankfurter class,
which are a permanent public record), nobody archives the *parallel* rate - the snapshot is the only
record, and it's exactly the number that reveals the real cost of a dollar in Bolivia. `price_cents` =
the median parallel rate * 100 (centi-BOB per USD; 10.53 -> 1053), so the core's `drops` = the parallel
rate *easing* (the boliviano strengthening / dollars getting cheaper on the street); `qty` = the count
of P2P sources aggregated. A "deal" ("premium") = the parallel rate sits >= 40% above the official
6.96 peg (a severe black-market premium - dollars scarce/expensive). buy/sell/spread + the per-exchange
medians ride in flags. money() renders the centi-BOB as $ (it's BOB, ~10.5 per USD).

Model: one Item, the Bolivia USD parallel rate (join key = the constant `usd`); `search`/`fetch`/`poll`
all read the same aggregate. `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://paralelo.bo/api/rate"
OFFICIAL_PEG = 6.96      # Bolivia's long-pegged official USD/BOB rate
PREMIUM_DEAL = 1.40      # parallel >= 40% over the peg = "premium"
ITEM_ID = "usd"


def _f(v):
    return float(v) if isinstance(v, (int, float)) else None


def _build(d):
    median = _f(d.get("median"))
    srcs = [s for s in (d.get("sources") or []) if s.get("source")]
    premium = round(median / OFFICIAL_PEG, 4) if median else None
    item = Item(ITEM_ID, name="Bolivia parallel USD/BOB", subtitle="black-market USD rate (P2P aggregate)",
                category="fx", extra={"official_peg": OFFICIAL_PEG})
    obs = Obs(price_cents=(round(median * 100) if median else None), qty=len(srcs),
              flags={"buy": _f(d.get("buy")), "sell": _f(d.get("sell")), "median": median,
                     "spread_pct": _f(d.get("spreadPct")), "premium": premium,
                     "official_peg": OFFICIAL_PEG, "timestamp": d.get("timestamp") or "",
                     "sources": ",".join(safe(s.get("source")) for s in srcs)})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._d = None

    def rate(self):
        if self._d is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._d = r.json() or {}
        return self._d


class ParaleloBoSource(Source):
    name = "paralelobo"
    id_label = "PAIR"
    cc_default = "bo"        # unused
    deal_label = "premium"   # parallel >= 40% over the official peg
    search_header = f"{'RATE':>7}  {'PREM':>5}  PAIR"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        d = cl.rate()
        m = d.get("median")
        return m is not None, f"(parallel USD/BOB {m}; {len(d.get('sources') or [])} P2P sources; keyless paralelo.bo)"

    def search(self, cl, term, args):
        return [_build(cl.rate())]

    def fetch(self, cl, item_id):
        return _build(cl.rate())

    def is_deal(self, obs):
        p = obs.flags.get("premium")
        return isinstance(p, (int, float)) and p >= PREMIUM_DEAL

    def deal_line(self, item, obs):
        f = obs.flags
        prem = f.get("premium")
        pct = f"+{round((prem - 1) * 100)}% over peg" if isinstance(prem, (int, float)) else "?"
        return f"USD/BOB {f.get('median')}  ({pct})  vs official {f.get('official_peg')}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        prem = f.get("premium")
        return f"{str(f.get('median') or '?'):>7}  {(f'{prem:.2f}' if isinstance(prem,(int,float)) else '?'):>5}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  pair     : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  parallel : buy {f.get('buy')}  sell {f.get('sell')}  median {f.get('median')} BOB/USD")
            prem = f.get("premium")
            if isinstance(prem, (int, float)):
                lines.append(f"  premium  : {prem:.2f}x  (+{round((prem - 1) * 100)}% over official {f.get('official_peg')})")
            lines.append(f"  spread   : {f.get('spread_pct')}%   sources: {f.get('sources') or '?'}")
            lines.append(f"  as of    : {f.get('timestamp') or '?'}")
        return lines


SOURCE = ParaleloBoSource()
