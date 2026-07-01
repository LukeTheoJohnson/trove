"""epic - Epic Games Store free-game rotation via the store's own keyless backend.

The Epic Games Store gives away one or more paid games free every week. That rotation is the
ephemeral state this source hoards: this Thursday's freebie is gone next Thursday, and Epic keeps
no public archive of what was given away, when, or its RRP at the time. The store page itself calls
`store-site-backend-static.ak.epicgames.com/freeGamesPromotions` (keyless; the backend host has no
robots.txt and store.epicgames.com robots fences only /account, /cart, /library and the `*?q=`
search path - never this promo backend), so this is a sanctioned, page-called public endpoint ->
trove. Country/currency come from `--cc` (default nz -> NZD).

Model: one Item per Epic **offer** (join key = the offer `id`; unique per element in the feed).
`price_cents` = the current effective price (`price.totalPrice.discountPrice`) - 0 while the game is
free, back up to its RRP once the giveaway ends - so the core's `drops` = a watched upcoming title
crossing into its free window (RRP -> Free). `was_cents` = the RRP (`originalPrice`). A "deal" = free
right now (a live giveaway window with discountPrice 0). Epic's convention in this feed is
`discountPercentage: 0` == free (100% off).

`search` lists the current rotation - free now (sorted first) + the upcoming free titles Epic has
announced - filtered by a title substring (pass "" for the whole rotation). `item`/`poll` fetch one
offer by `id` from the same one-GET feed (memoized in the client, so a multi-item poll is a single
request). Watch an upcoming title and poll it to catch the exact moment it goes free.
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
STORE = "https://store.epicgames.com/p"


def _date(iso):
    """ISO 8601 -> 'YYYY-MM-DD' (the promo window edges are day-granular in practice)."""
    return (iso or "")[:10]


def _windows(promotions):
    """(current_offer, upcoming_offer): the first promotional-offer dict in each bucket, or None.

    Epic nests them: promotions.promotionalOffers[] -> {promotionalOffers: [ {startDate,endDate,
    discountSetting}, ... ]}. The outer list is a wrapper; the inner list holds the real windows.
    """
    p = promotions or {}

    def first(bucket):
        wrap = p.get(bucket) or []
        inner = (wrap[0].get("promotionalOffers") or []) if wrap else []
        return inner[0] if inner else None

    return first("promotionalOffers"), first("upcomingPromotionalOffers")


def _slug(e):
    for src in ((e.get("catalogNs") or {}).get("mappings") or [], e.get("offerMappings") or []):
        for m in src:
            if m.get("pageSlug"):
                return m["pageSlug"]
    ps = e.get("productSlug")
    return ps.split("/")[0] if ps else None


def _image(e):
    imgs = e.get("keyImages") or []
    for t in ("OfferImageWide", "DieselStoreFrontWide", "Thumbnail"):
        for k in imgs:
            if k.get("type") == t and k.get("url"):
                return k["url"]
    return (imgs[0].get("url") if imgs else None)


def _classify(e):
    """(status, current_offer, upcoming_offer, discount_price, original_price) for an element.

    status in {'free', 'soon', 'none'}: free = a live giveaway window with a $0 price; soon = an
    announced upcoming free window; none = present in the feed but not (yet) a free giveaway.
    """
    price = (e.get("price") or {}).get("totalPrice") or {}
    dp, op = price.get("discountPrice"), price.get("originalPrice")
    cur, up = _windows(e.get("promotions"))
    if cur and dp == 0:
        return "free", cur, up, dp, op
    if up:
        return "soon", cur, up, dp, op
    return "none", cur, up, dp, op


def _element(e):
    """One free-games element -> (Item, Obs). Read every field from the live payload."""
    status, cur, up, dp, op = _classify(e)
    price = (e.get("price") or {}).get("totalPrice") or {}
    fmt = price.get("fmtPrice") or {}
    win = cur if status == "free" else up
    seller = safe((e.get("seller") or {}).get("name", ""))
    slug = _slug(e)
    url = f"{STORE}/{slug}" if slug else ""
    item = Item(str(e.get("id")),
                name=safe(e.get("title", "")),
                subtitle=("free now" if status == "free" else "free soon" if status == "soon" else "in store"),
                category=seller,
                extra={"desc": safe(e.get("description", ""))[:300], "url": url,
                       "image": _image(e), "orig_fmt": fmt.get("originalPrice"),
                       "currency": price.get("currencyCode"), "namespace": e.get("namespace")})
    obs = Obs(price_cents=dp, was_cents=op,
              flags={"free": status == "free", "upcoming": status == "soon",
                     "start": _date((win or {}).get("startDate")),
                     "end": _date((win or {}).get("endDate")),
                     "currency": price.get("currencyCode")})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.country = (cc or "nz").upper()
        self.s = retry_session()
        self._feed = None   # one GET serves a whole search/poll pass

    def feed(self):
        if self._feed is None:
            r = self.s.get(BASE,
                           params={"locale": "en-US", "country": self.country,
                                   "allowCountries": self.country},
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            store = (((r.json() or {}).get("data") or {}).get("Catalog") or {}).get("searchStore") or {}
            self._feed = store.get("elements") or []
        return self._feed


class EpicSource(Source):
    name = "epic"
    id_label = "OFFER"
    cc_default = "nz"          # country/currency for the price node (nz -> NZD)
    deal_label = "free"        # deal = a live giveaway (free right now)
    search_limit_default = 20
    search_header = f"{'STATUS':<7}  {'WAS':>8}  {'UNTIL':<10}  TITLE"

    def client(self, args):
        return _Client(args.cc)

    def doctor(self, cl):
        feed = cl.feed()
        free = sum(1 for e in feed if _classify(e)[0] == "free")
        return bool(feed), f"({len(feed)} promo elements, {free} free now; keyless Epic freeGamesPromotions)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        rows = []
        for e in cl.feed():
            status = _classify(e)[0]
            if status == "none":
                continue
            item, obs = _element(e)
            if t and t not in item.name.lower() and t not in item.id.lower():
                continue
            rows.append((item, obs))
        rows.sort(key=lambda r: (0 if r[1].flags.get("free") else 1, r[1].flags.get("end") or "9999"))
        return rows

    def fetch(self, cl, item_id):
        for e in cl.feed():
            if str(e.get("id")) == str(item_id):
                return _element(e)
        return None

    def is_deal(self, obs):
        return bool(obs.flags.get("free"))

    def deal_line(self, item, obs):
        end = obs.flags.get("end")
        until = f" until {end}" if end else ""
        was = f"  (was {money(obs.was_cents)})" if obs.was_cents else ""
        return f"FREE{until}  {item.name}{was}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        status = "FREE" if f.get("free") else "soon" if f.get("upcoming") else "-"
        until = (f.get("end") if f.get("free") else f.get("start")) or ""
        was = money(obs.was_cents) if obs else "?"
        return f"{status:<7}  {was:>8}  {until:<10}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  publisher : {item.category}",
                 f"  status    : {item.subtitle}"]
        if obs:
            f = obs.flags
            lines.append(f"  price     : {money(obs.price_cents)}  (RRP {e.get('orig_fmt') or money(obs.was_cents)})")
            if f.get("start") or f.get("end"):
                verb = "free" if f.get("free") else "free from" if f.get("upcoming") else "window"
                lines.append(f"  {verb:<9} : {f.get('start') or '?'} -> {f.get('end') or '?'}  (UTC)")
        lines.append(f"  desc      : {e.get('desc', '')}")
        lines.append(f"  url       : {e.get('url', '')}")
        return lines


SOURCE = EpicSource()
