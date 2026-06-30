"""BookMe - NZ's discounted activities/experiences marketplace (bookme.co.nz), SSR page-parse.

BookMe lists last-minute deals on NZ tourism activities (cruises, jet boats, gondolas, spas...) by
region. Each region page server-renders ~24 deal cards with the from-price, the discount, the deal
window, and - the distinctive bit - the number of *spaces remaining*. There is no JSON API and no
robots.txt fence; the data is in the page's own HTML (page-parse = sanctioned = trove).

The timeline value is doubly ephemeral: the discounted price *and* the spaces-remaining count, which
ticks down as the deal sells out and is never archived. The snapshot is the only record - so the
spaces-left series the cache accumulates is genuinely un-rebuildable. `qty` carries spaces-remaining.

Model: one Item per activity (join key = the activity-ref URL path, e.g.
"things-to-do/queenstown/activity/milford-sound-cruise-mitre-peak-cruises/4291"; the path encodes the
region, so one card-parser serves both search and fetch). price_cents = the from-price, was_cents =
from-price + advertised saving, qty = spaces remaining. A "deal" = a steep discount (>= 40% off).

`search` parses a region's listing (--cc = region slug, default "queenstown") filtered by a name
substring; `item`/`poll` re-parse the activity's region listing to find it.
"""
from __future__ import annotations

import html as _html
import re

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

HOST = "https://www.bookme.co.nz"

_CARD = re.compile(r'activity-ref="([^"]+)"\s+class="dealCard\s*">(.*?)'
                   r'(?=activity-ref="|<div class="deals-list__wrapper|$)', re.S)
_NAME = re.compile(r'<h3>(.*?)</h3>', re.S)
_PRICE = re.compile(r'<div class="right">\$([0-9,]+)(?:<sup>(\d+)</sup>)?')
_DISC = re.compile(r'hd_dealDiscount[^>]*>(?:<span>[^<]*</span>)?\s*([0-9]+)%')
_SPACES = re.compile(r'hd_dealSpaces">\s*([0-9]+)')
_SAVE = re.compile(r'Save up to \$([0-9,.]+)')
_DATES = re.compile(r'hd_dealDates"><span>([^<]+)</span><span>([^<]+)</span>')
_RATING = re.compile(r'stars-wrapper__rating">([0-9.]+)</span>'
                     r'<span class="stars-wrapper__count">([0-9,]+)')


def _safe(s):
    """Unescape HTML entities, then fold to the cp1252 console codec (see trove.tracker.safe)."""
    return safe(_html.unescape(s or ""))


def _money_cents(dollars, cents):
    try:
        return int(dollars.replace(",", "")) * 100 + (int(cents) if cents else 0)
    except (TypeError, ValueError):
        return None


def _save_cents(s):
    try:
        return round(float(s.replace(",", "")) * 100)
    except (TypeError, ValueError):
        return None


def _card(ref, c):
    rid = ref.strip("/")
    region = rid.split("/")[1] if "/" in rid and len(rid.split("/")) > 1 else ""
    name = _NAME.search(c)
    pm = _PRICE.search(c)
    price_c = _money_cents(pm.group(1), pm.group(2)) if pm else None
    if price_c is None:
        return None
    disc = _DISC.search(c)
    disc_pct = int(disc.group(1)) if disc else None
    save_c = _save_cents(_SAVE.search(c).group(1)) if _SAVE.search(c) else None
    spaces = _SPACES.search(c)
    qty = int(spaces.group(1)) if spaces else None
    dates = _DATES.search(c)
    rating = _RATING.search(c)
    item = Item(rid, name=_safe(name.group(1)) if name else rid,
                subtitle=_safe(region.replace("-", " ").title()),
                category="activity",
                extra={"url": f"{HOST}/{rid}", "region": region,
                       "rating": rating.group(1) if rating else None,
                       "reviews": rating.group(2) if rating else None})
    obs = Obs(price_cents=price_c,
              was_cents=(price_c + save_c) if save_c else None, qty=qty,
              flags={"currency": "NZD", "discount_pct": disc_pct, "save_cents": save_c,
                     "region": region,
                     "date_from": dates.group(1).strip() if dates else None,
                     "date_to": dates.group(2).strip() if dates else None})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()

    def region(self, region):
        r = self.s.get(f"{HOST}/things-to-do/{region}",
                       headers={"Accept": "text/html", "User-Agent": UA}, timeout=40)
        if r.status_code != 200:
            return []
        return [(ref, c) for ref, c in _CARD.findall(r.text)]


class BookMeSource(Source):
    name = "bookme"
    id_label = "ACTIVITY"
    cc_default = "queenstown"   # region slug; --cc <region> snapshots another region
    deal_label = "deal"         # deal = >= 40% off

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        cards = cl.region(self.cc_default)
        return bool(cards), f"({len(cards)} deals on /{self.cc_default}; SSR page-parse)"

    def search(self, cl, term, args):
        t = term.lower()
        out = []
        for ref, c in cl.region(args.cc):
            built = _card(ref, c)
            if built and t in built[0].name.lower():
                out.append(built)
        return out

    def fetch(self, cl, item_id):
        rid = str(item_id).strip("/")
        parts = rid.split("/")
        if len(parts) < 2:
            return None
        for ref, c in cl.region(parts[1]):
            if ref.strip("/") == rid:
                return _card(ref, c)
        return None

    def is_deal(self, obs):
        d = obs.flags.get("discount_pct")
        return d is not None and d >= 40

    def deal_line(self, item, obs):
        d = obs.flags.get("discount_pct")
        disc = f"{d}% off  " if d else ""
        sp = f"{obs.qty} spaces  " if obs.qty is not None else ""
        return f"{money(obs.price_cents)}  {disc}{sp}{item.name}"

    def format_item(self, item, obs):
        lines = [f"  region   : {item.subtitle}",
                 f"  rating   : {item.extra.get('rating', '?')} ({item.extra.get('reviews', '?')} reviews)"]
        if obs:
            f = obs.flags
            lines.append(f"  from     : {money(obs.price_cents)}"
                         + (f"  (was {money(obs.was_cents)}, {f.get('discount_pct')}% off)"
                            if obs.was_cents else ""))
            if obs.qty is not None:
                lines.append(f"  spaces   : {obs.qty} remaining")
            if f.get("date_from"):
                lines.append(f"  window   : {f.get('date_from')} - {f.get('date_to')}")
        lines.append(f"  url      : {item.extra.get('url', '')}")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = BookMeSource()
