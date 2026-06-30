"""Yu-Gi-Oh! - official keyless card API (db.ygoprodeck.com/api/v7), the YGO sibling to scryfall
(MTG) and pokemontcg. Completes trove's TCG trio. Polite use only: real UA, low volume, personal.
The site blocks AI-training crawlers and sets ai-train=no; this is a personal price client, not a
crawler, and does no training/redistribution.

Each card carries one price per marketplace. --cc picks the tracked venue (the price-over-time
series): tcgplayer (default) | cardmarket | ebay | amazon | coolstuffinc. The source 'deal' is
retailer arbitrage between the two legit US singles retailers (TCGplayer vs CoolStuffInc): one is
>=15% cheaper than the other. ebay/amazon are resale-noisy and cardmarket is EUR, so they stay out
of the deal rule (but show in the price board)."""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money

BASE = "https://db.ygoprodeck.com/api/v7"
VENUES = ("tcgplayer", "cardmarket", "ebay", "amazon", "coolstuffinc")
DEAL_RATIO = 0.85  # one retailer at/under 85% of the other = an arbitrage buy


def _cents(s):
    try:
        v = round(float(s) * 100)
    except (TypeError, ValueError):
        return None
    return v or None  # treat 0.00 (no price) as missing


class _Client:
    def __init__(self):
        self.s = retry_session()

    def _get(self, params):
        r = self.s.get(f"{BASE}/cardinfo.php", params=params,
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=30)
        if r.status_code == 400:      # API uses 400 + {"error":...} for "no match"
            return None
        r.raise_for_status()
        return r.json()

    def by_name(self, name):
        d = self._get({"name": name})
        return (d or {}).get("data", []) or []

    def search(self, term):
        d = self._get({"fname": term})
        return (d or {}).get("data", []) or []

    def by_id(self, cid):
        d = self._get({"id": cid})
        rows = (d or {}).get("data", []) or []
        return rows[0] if rows else None


class YgoprodeckSource(Source):
    name = "ygoprodeck"
    id_label = "CARD"
    cc_default = "tcgplayer"
    deal_label = "arbitrage"

    def _venues(self, card):
        p = (card.get("card_prices") or [{}])[0]
        return {v: _cents(p.get(f"{v}_price")) for v in VENUES}

    def _obs(self, card):
        v = self._venues(card)
        return Obs(price_cents=v.get(self._cc), flags={"denom": self._cc, **{f"{k}_c": c for k, c in v.items()}})

    def _to_pair(self, c):
        item = Item(c.get("id"), c.get("name", ""), subtitle=c.get("type", ""),
                    category=c.get("race", ""),
                    extra={"attribute": c.get("attribute"), "atk": c.get("atk"),
                           "def": c.get("def"), "level": c.get("level"),
                           "archetype": c.get("archetype"), "sets": len(c.get("card_sets") or [])})
        return item, self._obs(c)

    def client(self, args):
        self._cc = args.cc if args.cc in VENUES else "tcgplayer"
        return _Client()

    def doctor(self, cl):
        rows = cl.by_name("Dark Magician")
        return bool(rows), f"({len(rows)} result for 'Dark Magician', cc={self._cc})"

    def search(self, cl, term, args):
        return [self._to_pair(c) for c in cl.search(term)[: args.limit] if c.get("id") is not None]

    def fetch(self, cl, cid):
        c = cl.by_id(cid)
        return self._to_pair(c) if c else None

    @staticmethod
    def _arb(obs):
        """(cheaper_venue, cheap_cents, dear_cents) across the two legit US retailers, or None."""
        tcg, csi = obs.flags.get("tcgplayer_c"), obs.flags.get("coolstuffinc_c")
        if not (tcg and csi):
            return None
        return ("tcgplayer", tcg, csi) if tcg <= csi else ("coolstuffinc", csi, tcg)

    def is_deal(self, obs):
        a = self._arb(obs)
        return bool(a and a[1] <= DEAL_RATIO * a[2])

    def deal_line(self, item, obs):
        venue, cheap, dear = self._arb(obs)
        pct = round((1 - cheap / dear) * 100)
        return f"{money(cheap)} on {venue} vs {money(dear)} (-{pct}%)  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  type     : {item.subtitle}  ({item.category} / {e.get('attribute')})"]
        if e.get("level") is not None:
            lines.append(f"  stats    : ATK {e.get('atk')} / DEF {e.get('def')} / LV {e.get('level')}")
        if e.get("archetype"):
            lines.append(f"  archetype: {e.get('archetype')}")
        if obs:
            f = obs.flags
            board = " | ".join(f"{v[:4]} {money(f.get(v + '_c'))}" for v in VENUES if f.get(v + "_c"))
            lines.append(f"  tracked  : {money(obs.price_cents)} [{f.get('denom')}]")
            lines.append(f"  board    : {board}")
        lines.append(f"  printings: {e.get('sets')} sets")
        return lines


SOURCE = YgoprodeckSource()
