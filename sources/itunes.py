"""iTunes / App Store - official keyless Search API (itunes.apple.com). Retries 403 (throttle).
id/name/price coalesced across entity types. Deal = went free."""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source

UA = "trove/0.1 (+https://github.com/LukeTheoJohnson/trove)"
BASE = "https://itunes.apple.com"


class _Client:
    def __init__(self, country):
        self.country = country
        self.s = retry_session(extra_status=(403,))

    def _get(self, path, params):
        r = self.s.get(f"{BASE}/{path}", params={**params, "country": self.country},
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=30)
        r.raise_for_status()
        return r.json()

    def search(self, term, entity, limit):
        return self._get("search", {"term": term, "entity": entity, "limit": limit}).get("results", []) or []

    def lookup(self, iid):
        res = self._get("lookup", {"id": iid}).get("results", []) or []
        for r in res:
            if r.get("trackId") == iid or r.get("collectionId") == iid:
                return r
        return res[0] if res else None


def _id(r):
    return r.get("trackId") or r.get("collectionId")


def _price(r):
    for k in ("trackPrice", "price", "collectionPrice"):
        v = r.get(k)
        if isinstance(v, (int, float)):
            return v
    return None


def _to(r):
    item = Item(_id(r), r.get("trackName") or r.get("collectionName") or "",
                subtitle=r.get("artistName", ""), category=r.get("primaryGenreName", ""),
                extra={"kind": r.get("kind") or r.get("wrapperType") or ""})
    v = _price(r)
    obs = Obs(price_cents=round(v * 100)) if v is not None else None
    return item, obs


class ITunesSource(Source):
    name = "itunes"
    id_label = "ID"
    cc_default = "nz"
    deal_label = "free"
    search_args = [("--entity", {"default": "software",
                    "help": "software|album|song|movie|ebook|podcast (default software)"})]

    def client(self, args):
        return _Client(args.cc)

    def doctor(self, cl):
        res = cl.search("the beatles", "album", 1)
        return bool(res), f"({len(res)} result for 'the beatles' album)"

    def search(self, cl, term, args):
        return [_to(r) for r in cl.search(term, args.entity, args.limit) if _id(r)]

    def fetch(self, cl, iid):
        try:
            iid = int(iid)
        except (TypeError, ValueError):
            pass
        r = cl.lookup(iid)
        return _to(r) if r else None

    def is_deal(self, obs):
        return obs.price_cents == 0

    def deal_line(self, item, obs):
        return f"Free   {item.name}"

    def format_item(self, item, obs):
        return [f"  kind   : {item.extra.get('kind')}", f"  artist : {item.subtitle}",
                f"  genre  : {item.category}",
                f"  price  : {'Free' if obs and obs.price_cents == 0 else (f'${obs.price_cents/100:.2f}' if obs else '(no price)')}"]


SOURCE = ITunesSource()
