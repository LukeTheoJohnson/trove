"""GrabOne - NZ's daily-deals marketplace (new.grabone.co.nz), page-published JSON-LD.

GrabOne lists time-limited deals (a sale price, an RRP/strikethrough, a merchant, an expiry window)
for activities, dining, retail and travel across NZ. The data is published in the page's own
`application/ld+json` structured data - a CollectionPage -> ItemList of Product on each region/
category listing, and a Product on each deal's detail page - so this is page-parse (sanctioned),
not a private API. robots.txt fences only /cms /dev /admin /my-stuff /buy, none of the browse data.

The timeline value is *catalog churn*: which deals were offered, at what price and discount, and
when they appeared and vanished. The deal catalog is never archived, so the snapshot is the only
record - the whole point of hoarding it.

Model: one Item per deal (join key = the deal's URL path, e.g.
"weddings-special-occasions-parties/flowers-florists/p/market-flowers-46"), tracking the sale price
as price_cents and the RRP as was_cents (the strikethrough lives on the *listing*; the detail page
instead carries the validFrom/validThrough expiry window). A "deal" = the offer is live and
grabbable right now (in stock and not past its validThrough) - the meaningful ephemeral state for a
flash-deals site; the discount % is shown as enrichment when the RRP is known.

`search` snapshots a region's listing (--cc = region slug, default "auckland") and filters the ~40
deals by a name/merchant substring. `item`/`poll` re-fetch one deal's detail page for its live
price + expiry + availability.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source, money, safe

UA = "trove/0.1 (+https://github.com/LukeTheoJohnson/trove)"
HOST = "https://new.grabone.co.nz"
_LD = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_INSTOCK = "https://schema.org/InStock"


def _cents(s):
    try:
        return round(float(str(s).replace(",", "")) * 100)
    except (TypeError, ValueError):
        return None


def _id_of(url):
    return urlsplit(url or "").path.strip("/")


def _discount(price_c, was_c):
    if price_c and was_c and was_c > price_c:
        return round((1 - price_c / was_c) * 100)
    return None


def _live(obs):
    """Is this deal grabbable right now? In stock and not past validThrough."""
    if obs.flags.get("available") is False:
        return False
    vt = obs.flags.get("valid_through")
    if vt:
        try:
            return datetime.now(timezone.utc) <= datetime.fromisoformat(vt.replace("Z", "+00:00"))
        except ValueError:
            return True
    return True


def _from_listing(prod, region):
    offers = prod.get("offers") or {}
    price_c = _cents(offers.get("price"))
    was_c = _cents((offers.get("priceSpecification") or {}).get("price"))
    brand = safe((prod.get("brand") or {}).get("name", ""))
    item = Item(_id_of(prod.get("url")),
                name=safe(prod.get("name", "")),
                subtitle=brand,
                category=safe(region),
                extra={"url": prod.get("url"), "image": prod.get("image"), "merchant": brand,
                       "region": region})
    obs = Obs(price_cents=price_c, was_cents=was_c,
              flags={"currency": offers.get("priceCurrency", "NZD"), "region": region,
                     "discount_pct": _discount(price_c, was_c),
                     "available": offers.get("availability") in (None, _INSTOCK),
                     "src": "listing"})
    return item, obs


def _from_detail(prod):
    offers = prod.get("offers") or {}
    seller = offers.get("seller") or {}
    region = (seller.get("location") or {}).get("name", "")
    price_c = _cents(offers.get("price"))
    item = Item(_id_of(prod.get("url")),
                name=safe(prod.get("description", "")),
                subtitle=safe(seller.get("name", "")),
                category=safe(prod.get("category", "")),
                extra={"url": prod.get("url"), "image": prod.get("image"),
                       "merchant": safe(seller.get("name", "")), "region": safe(region),
                       "valid_from": offers.get("validFrom")})
    obs = Obs(price_cents=price_c,
              flags={"currency": offers.get("priceCurrency", "NZD"), "region": safe(region),
                     "valid_through": offers.get("validThrough"),
                     "available": offers.get("availability") in (None, _INSTOCK),
                     "src": "detail"})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()

    def _ld(self, url):
        r = self.s.get(url, headers={"Accept": "text/html", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        import json
        out = []
        for blk in _LD.findall(r.text):
            try:
                out.append(json.loads(blk))
            except ValueError:
                continue
        return out

    def listing(self, region):
        for d in self._ld(f"{HOST}/{region}"):
            me = d.get("mainEntity") if d.get("@type") == "CollectionPage" else None
            if me and me.get("@type") == "ItemList":
                return [el.get("item") or {} for el in me.get("itemListElement", [])]
        return []

    def detail(self, path):
        for d in self._ld(f"{HOST}/{path}"):
            if d.get("@type") == "Product":
                return d
        return None


class GrabOneSource(Source):
    name = "grabone"
    id_label = "DEAL"
    cc_default = "auckland"   # region slug; --cc <region> snapshots another region's listing
    deal_label = "live deal"  # deal = the offer is in stock and not expired

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        deals = cl.listing(self.cc_default)
        return bool(deals), f"({len(deals)} deals on /{self.cc_default}; page-published JSON-LD)"

    def search(self, cl, term, args):
        region = args.cc
        t = term.lower()
        out = []
        for prod in cl.listing(region):
            if prod.get("@type") != "Product":
                continue
            hay = f"{prod.get('name', '')} {(prod.get('brand') or {}).get('name', '')}".lower()
            if t in hay:
                out.append(_from_listing(prod, region))
        return out

    def fetch(self, cl, item_id):
        prod = cl.detail(item_id)
        return _from_detail(prod) if prod else None

    def is_deal(self, obs):
        return obs.price_cents is not None and _live(obs)

    def deal_line(self, item, obs):
        disc = obs.flags.get("discount_pct")
        d = f"{disc}% off  " if disc else ""
        was = f"(was {money(obs.was_cents)})  " if obs.was_cents else ""
        vt = obs.flags.get("valid_through")
        ends = f"ends {vt[:10]}  " if vt else ""
        return f"{money(obs.price_cents)}  {d}{was}{ends}{item.name}"

    def format_item(self, item, obs):
        lines = [f"  merchant : {item.subtitle}",
                 f"  category : {item.category}",
                 f"  region   : {item.extra.get('region', '')}"]
        if obs:
            lines.append(f"  price    : {money(obs.price_cents)}")
            if obs.was_cents:
                disc = obs.flags.get("discount_pct")
                lines.append(f"  rrp      : {money(obs.was_cents)}"
                             + (f"  ({disc}% off)" if disc else ""))
            vt = obs.flags.get("valid_through")
            if vt:
                lines.append(f"  ends     : {vt}")
            lines.append(f"  live     : {'yes' if _live(obs) else 'no (sold out / expired)'}")
        lines.append(f"  url      : {item.extra.get('url', '')}")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = GrabOneSource()
