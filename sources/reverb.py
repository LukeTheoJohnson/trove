"""reverb - Reverb.com used-gear marketplace listings via the official keyless API.

Reverb is the eBay of musical instruments: individual sellers post used guitars, synths, pedals
and amps, each a single for-sale listing that lives until it sells and then vanishes. That live
listing state - the asking price, the seller's markdowns, whether it's still available - is the
ephemeral thing this source hoards; Reverb keeps no public archive of a listing's price history
or the moment it sold. The site's own frontend calls `reverb.com/api/listings` (keyless; robots
leaves /api/listings open, fencing only /api/my and a few per-listing sub-paths), so this is a
sanctioned, page-called public endpoint -> trove. It's the musical-gear twin of the turners used-car
source (one listing, markdown history, then gone). Display currency comes from `--cc` (default NZD)
via the X-Display-Currency header; set REVERB_TOKEN to send an OAuth bearer, but reads work keyless.

Model: one Item per Reverb **listing** (join key = the listing `id`; unique per for-sale post).
`price_cents` = the effective checkout price (`buyer_price`) - so the core's `drops` = a watched
listing the seller marked down. `was_cents` = the pre-sale list price (`price`) when it's higher.
`qty` = `inventory`. A "sale" deal = the seller has an active markdown (buyer_price < price, i.e.
Reverb's `sale_ribbon`) on a still-live listing.

`search` lists live listings matching a query (add `--sale` for only on-sale ones); `item`/`poll`
fetch one listing by `id`. Watch a listing and poll it to catch a markdown or the day it sells.
"""
from __future__ import annotations

import os

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://reverb.com/api"


def _cents(node):
    return node.get("amount_cents") if isinstance(node, dict) else None


def _link(l, key):
    return ((l.get("_links") or {}).get(key) or {}).get("href", "")


def _listing(l):
    """One Reverb listing dict -> (Item, Obs). Every field read from the live payload."""
    cond = l.get("condition") or {}
    state = l.get("state") or {}
    list_cents = _cents(l.get("price"))
    eff_cents = _cents(l.get("buyer_price"))
    if eff_cents is None:
        eff_cents = list_cents
    was = list_cents if (list_cents and eff_cents and list_cents > eff_cents) else None
    ribbon = (l.get("sale_ribbon") or {}).get("display", "")
    on_sale = was is not None or bool(ribbon)
    cur = (l.get("price") or {}).get("currency") or ""
    item = Item(str(l.get("id")),
                name=safe(l.get("title", "")),
                subtitle=safe(cond.get("display_name", "")),
                category=safe(l.get("make", "")),
                extra={"model": safe(l.get("model", "")), "year": safe(l.get("year", "")),
                       "finish": safe(l.get("finish", "")), "shop": safe(l.get("shop_name", "")),
                       "url": _link(l, "web"), "image": _link(l, "photo"), "currency": cur})
    obs = Obs(price_cents=eff_cents, was_cents=was, qty=l.get("inventory"),
              flags={"state": state.get("slug", ""), "condition": cond.get("slug", ""),
                     "sale": on_sale, "ribbon": safe(ribbon), "currency": cur,
                     "offers": bool(l.get("offers_enabled")), "auction": bool(l.get("auction"))})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.cur = (cc or "NZD").upper()
        self.s = retry_session()
        self.token = os.environ.get("REVERB_TOKEN")

    def _get(self, path, params=None):
        h = {"Accept": "application/hal+json", "Accept-Version": "3.0",
             "X-Display-Currency": self.cur, "User-Agent": UA}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        r = self.s.get(f"{BASE}/{path}", params=params or {}, headers=h, timeout=30)
        r.raise_for_status()
        return r.json()

    def search(self, term, limit, on_sale):
        params = {"query": term, "per_page": max(1, min(limit, 50))}
        if on_sale:
            params["on_sale"] = "true"
        return self._get("listings", params).get("listings", []) or []

    def listing(self, lid):
        return self._get(f"listings/{lid}")


class ReverbSource(Source):
    name = "reverb"
    id_label = "LISTING"
    cc_default = "NZD"          # display currency (X-Display-Currency header)
    deal_label = "sale"        # deal = a live seller markdown
    search_args = [("--sale", {"action": "store_true", "help": "only listings on sale (seller markdown)"})]
    search_header = f"{'PRICE':>10}  {'COND':<10}  {'STATE':<5}  TITLE"

    def client(self, args):
        return _Client(args.cc)

    def doctor(self, cl):
        items = cl.search("stratocaster", 2, False)
        return bool(items), f"({len(items)} live listings for 'stratocaster'; keyless Reverb /api/listings)"

    def search(self, cl, term, args):
        out = []
        for l in cl.search(term, args.limit, getattr(args, "sale", False)):
            if not l.get("id"):
                continue
            out.append(_listing(l))
        return out

    def fetch(self, cl, lid):
        l = cl.listing(lid)
        if not l or not l.get("id"):
            return None
        return _listing(l)

    def is_deal(self, obs):
        return bool(obs.flags.get("sale")) and obs.flags.get("state") == "live"

    def deal_line(self, item, obs):
        ribbon = obs.flags.get("ribbon") or "on sale"
        was = f" (was {money(obs.was_cents)})" if obs.was_cents else ""
        return f"{ribbon}  {money(obs.price_cents)}{was}  {item.name}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        cond = (item.subtitle or "")[:10]
        state = (f.get("state") or "")[:5]
        return f"{money(obs.price_cents) if obs else '?':>10}  {cond:<10}  {state:<5}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  make/model: {item.category} {e.get('model', '')}".rstrip(),
                 f"  year      : {e.get('year', '')}",
                 f"  finish    : {e.get('finish', '')}",
                 f"  condition : {item.subtitle}",
                 f"  seller    : {e.get('shop', '')}"]
        if obs:
            f = obs.flags
            cur = f.get("currency") or ""
            price = f"  price     : {money(obs.price_cents)} {cur}".rstrip()
            if obs.was_cents:
                price += f"  (was {money(obs.was_cents)}, {f.get('ribbon') or 'on sale'})"
            lines.append(price)
            lines.append(f"  state     : {f.get('state', '')}  (inventory {obs.qty})"
                         + ("  offers ok" if f.get("offers") else ""))
        lines.append(f"  url       : {e.get('url', '')}")
        return lines


SOURCE = ReverbSource()
