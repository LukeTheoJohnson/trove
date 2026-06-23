"""Pokemon TCG - official keyless card API (api.pokemontcg.io/v2). Optional POKEMONTCG_API_KEY
env var lifts the rate limit (X-Api-Key header). The Pokemon sibling to scryfall's MTG.

Prices are per-card market prices (floats) refreshed ~daily. --cc picks the denomination:
usd (default, TCGplayer) | eur (Cardmarket). The tracked price is the card's market/trend price;
the source 'deal' is a listing sitting meaningfully under market (low <= 0.85 * market)."""
from __future__ import annotations

import os

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source, money

UA = "trove/0.1 (+https://github.com/LukeTheoJohnson/trove)"
BASE = "https://api.pokemontcg.io/v2"
# TCGplayer prices nest under a finish; pick the most representative one present.
TCG_VARIANTS = ("normal", "holofoil", "reverseHolofoil", "1stEditionNormal",
                "unlimitedHolofoil", "1stEditionHolofoil")
DEAL_RATIO = 0.85  # a listing at/under 85% of market value counts as underpriced


def _cents(v):
    return round(v * 100) if isinstance(v, (int, float)) else None


def _q(term):
    term = term.strip()
    return f'name:"{term}"' if " " in term else f"name:{term}*"


class _Client:
    def __init__(self, cc):
        self.cc = cc if cc in ("usd", "eur") else "usd"
        self.s = retry_session()
        self.key = os.environ.get("POKEMONTCG_API_KEY")

    def _get(self, path, params=None):
        h = {"Accept": "application/json", "User-Agent": UA}
        if self.key:
            h["X-Api-Key"] = self.key
        r = self.s.get(f"{BASE}/{path}", params=params or {}, headers=h, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def search(self, term, limit):
        d = self._get("cards", {"q": _q(term), "pageSize": min(limit, 250),
                                "select": "id,name,number,rarity,set,tcgplayer,cardmarket"})
        return (d or {}).get("data", []) or []

    def card(self, cid):
        d = self._get(f"cards/{cid}")
        return (d or {}).get("data") if d else None


class PokemonTCGSource(Source):
    name = "pokemontcg"
    id_label = "CARD"
    cc_default = "usd"
    deal_label = "underpriced"

    def _obs(self, card):
        if self._cc == "eur":
            cp = (card.get("cardmarket") or {}).get("prices") or {}
            low = _cents(cp.get("lowPriceExPlus")) or _cents(cp.get("lowPrice"))
            return Obs(price_cents=_cents(cp.get("trendPrice")),
                       flags={"denom": "eur", "low_cents": low,
                              "avg30_cents": _cents(cp.get("avg30")),
                              "avg7_cents": _cents(cp.get("avg7")),
                              "updated": (card.get("cardmarket") or {}).get("updatedAt")})
        tcg = card.get("tcgplayer") or {}
        prices = tcg.get("prices") or {}
        variant = next((v for v in TCG_VARIANTS if v in prices), next(iter(prices), None))
        p = prices.get(variant) or {}
        market = _cents(p.get("market"))
        if market is None:
            market = _cents(p.get("mid"))
        return Obs(price_cents=market,
                   flags={"denom": "usd", "variant": variant, "low_cents": _cents(p.get("low")),
                          "mid_cents": _cents(p.get("mid")), "high_cents": _cents(p.get("high")),
                          "updated": tcg.get("updatedAt")})

    def _to_pair(self, c):
        s = c.get("set") or {}
        item = Item(c.get("id"), c.get("name", ""),
                    subtitle=f"{s.get('name', '')} #{c.get('number', '')}".strip(),
                    category=c.get("rarity", ""),
                    extra={"set": s.get("id"), "series": s.get("series"),
                           "released": s.get("releaseDate")})
        return item, self._obs(c)

    def client(self, args):
        self._cc = args.cc if args.cc in ("usd", "eur") else "usd"
        return _Client(args.cc)

    def doctor(self, cl):
        rows = cl.search("charizard", 1)
        return bool(rows), f"({len(rows)} result for 'charizard', cc={self._cc})"

    def search(self, cl, term, args):
        return [self._to_pair(c) for c in cl.search(term, args.limit) if c.get("id")]

    def fetch(self, cl, cid):
        c = cl.card(cid)
        return self._to_pair(c) if c else None

    def is_deal(self, obs):
        low, market = obs.flags.get("low_cents"), obs.price_cents
        return bool(low and market and low <= DEAL_RATIO * market)

    def deal_line(self, item, obs):
        low, market = obs.flags.get("low_cents"), obs.price_cents
        pct = round((1 - low / market) * 100) if low and market else 0
        return f"{money(low)} listed vs {money(market)} market (-{pct}%)  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  set      : {item.subtitle}  ({item.category})",
                 f"  series   : {item.extra.get('series')}  (released {item.extra.get('released')})"]
        if not obs:
            return lines + ["  price    : (no price)"]
        f = obs.flags
        if f.get("denom") == "eur":
            lines.append(f"  trend    : {money(obs.price_cents)} eur"
                         + f"  (lowEx+ {money(f.get('low_cents'))} / avg30 {money(f.get('avg30_cents'))})")
        else:
            lines.append(f"  variant  : {f.get('variant')} [usd]")
            lines.append(f"  market   : {money(obs.price_cents)}"
                         + f"  (low {money(f.get('low_cents'))} / mid {money(f.get('mid_cents'))}"
                         + f" / high {money(f.get('high_cents'))})")
        lines.append(f"  updated  : {f.get('updated')}")
        return lines


SOURCE = PokemonTCGSource()
