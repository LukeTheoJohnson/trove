"""Scryfall - official MTG card API (api.scryfall.com), keyless. Asks for a descriptive UA.
Prices are per-card market prices (strings) updated ~daily. --cc picks the denomination:
usd (default) | eur | tix. The source 'deal' is the known MTG signal: foil <= nonfoil."""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source, money

UA = "trove/0.1 (+https://github.com/LukeTheoJohnson/trove)"
BASE = "https://api.scryfall.com"
# cc -> (nonfoil price key, foil price key)
KEYS = {"usd": ("usd", "usd_foil"), "eur": ("eur", "eur_foil"), "tix": ("tix", None)}


def _cents(s):
    try:
        return round(float(s) * 100)
    except (TypeError, ValueError):
        return None


class _Client:
    def __init__(self, cc):
        self.cc = cc if cc in KEYS else "usd"
        self.s = retry_session()

    def _get(self, path, params=None):
        r = self.s.get(f"{BASE}/{path}", params=params or {},
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def search(self, term):
        d = self._get("cards/search", {"q": term, "unique": "cards"})
        return (d or {}).get("data", []) or []

    def card(self, cid):
        return self._get(f"cards/{cid}")


class ScryfallSource(Source):
    name = "scryfall"
    id_label = "CARD"
    cc_default = "usd"
    deal_label = "foil-deal"

    def _obs(self, prices):
        nf_key, foil_key = KEYS[self._cc]
        nf, foil = _cents(prices.get(nf_key)), _cents(prices.get(foil_key)) if foil_key else None
        return Obs(price_cents=nf, flags={"foil_cents": foil})

    def client(self, args):
        self._cc = args.cc if args.cc in KEYS else "usd"
        return _Client(args.cc)

    def doctor(self, cl):
        rows = cl.search("Ragavan, Nimble Pilferer")
        return bool(rows), f"({len(rows)} results, cc={self._cc})"

    def _to_pair(self, c):
        item = Item(c.get("id"), c.get("name", ""),
                    subtitle=f"{c.get('set_name', '')} #{c.get('collector_number', '')}",
                    category=c.get("type_line", ""),
                    extra={"set": c.get("set"), "rarity": c.get("rarity"),
                           "released": c.get("released_at")})
        return item, self._obs(c.get("prices") or {})

    def search(self, cl, term, args):
        return [self._to_pair(c) for c in cl.search(term)]

    def fetch(self, cl, cid):
        c = cl.card(cid)
        return self._to_pair(c) if c else None

    def is_deal(self, obs):
        foil, nf = obs.flags.get("foil_cents"), obs.price_cents
        return foil is not None and nf is not None and 0 < foil <= nf

    def deal_line(self, item, obs):
        return f"foil {money(obs.flags.get('foil_cents'))} <= {money(obs.price_cents)} nonfoil  {item.name}"

    def format_item(self, item, obs):
        foil = obs.flags.get("foil_cents") if obs else None
        return [f"  set      : {item.subtitle}  ({item.extra.get('rarity')})",
                f"  type     : {item.category}",
                f"  released : {item.extra.get('released')}",
                f"  price    : {money(obs.price_cents) if obs else '?'} nonfoil"
                + (f" / {money(foil)} foil" if foil is not None else "")]


SOURCE = ScryfallSource()
