"""turners - NZ used-car prices from Turners (turners.co.nz), page-published microdata.

Turners is NZ's largest used-vehicle retailer/auction house. Each car's listing is server-rendered
into the page with schema.org/Car microdata plus a per-card `analytics-seg-info` span carrying
make/model/year/price/discount/branch/salesChannel. robots.txt is `Allow: /` with no /api or search
fence, and the data sits in the published HTML (no private call) - so this is page-parse (sanctioned),
not a reverse-engineered API.

The timeline value is the *per-car price as it moves over a listing's life*: Turners drops prices and
flips cars in/out of "discounted" while a car sits on the lot, then the listing vanishes when it
sells. That per-car markdown history is never archived, so the snapshot is the only record - the
point of hoarding it. (Mirrors grabone's URL-path-as-join-key, but for a car's own price series.)

Model: one Item per car (join key = the detail path tail, e.g. "subaru/forester/28148184", whose last
segment is the stock/good number), tracking the asking price as price_cents and the RRP as was_cents
(when the car is marked down). A "deal" = the car is currently discounted below its RRP. The full
spec (year/make/model/odometer/branch/fuel/body/sale channel) rides in flags + extra.

`search` snapshots a make's listing (or the latest 110) and filters by a make/model/year substring;
`item`/`poll` re-fetch one car's detail page for its live price + discount + availability.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source, money

UA = "trove/0.1 (+https://github.com/LukeTheoJohnson/trove)"
HOST = "https://www.turners.co.nz"
LIST_PATH = "/Cars/Used-Cars-for-Sale/"
PAGE_SIZE = 110   # Turners' max page size: one polite GET covers a whole make / the latest listings

_CARD = re.compile(r'<div class="product-block block-type-([\w-]+)"')
_HREF = re.compile(r'itemprop="url"\s+href="([^"]+)"', re.I)
_SAVE = re.compile(r'You Save \$([0-9,]+)', re.I)
_WAS = re.compile(r'(?:buyNowOrigPrice"?>?\s*)?Was \$([0-9,]+)', re.I)
_ODO = re.compile(r'mileageFromOdometer.{0,260}?(?:content="(\d+)"|>\s*([0-9]{1,3}(?:,[0-9]{3})+)\s*km)', re.I | re.S)
_KM = re.compile(r'([0-9]{1,3}(?:,[0-9]{3})+|\d{4,})\s*km', re.I)
_AVAIL = re.compile(r'availability"\s+content="(\w+)"', re.I)
_FUEL = re.compile(r'itemprop="fuelType">([^<]+)<', re.I)
_BODY = re.compile(r'itemprop="bodyType">([^<]+)<', re.I)


def _safe(s):
    """Fold to cp1252 (the Windows console codec); a Maori macron or rarer char degrades to '?'
    instead of crashing a print, since trove.py does not reconfigure stdout to UTF-8."""
    return (s or "").strip().encode("cp1252", "replace").decode("cp1252")


def _cents(s):
    try:
        return round(float(str(s).replace(",", "")) * 100)
    except (TypeError, ValueError):
        return None


def _seg(frag, key):
    """Pull a `data-seg-<key>="value"` attr (Turners is loose with the `= "..."` spacing)."""
    m = re.search(r'data-seg-' + key + r'=\s*"([^"]*)"', frag, re.I)
    return m.group(1).strip() if m else ""


def _path_tail(href):
    """/Cars/Used-Cars-for-Sale/subaru/forester/28148184 -> subaru/forester/28148184."""
    p = urlsplit(href or "").path
    i = p.lower().find(LIST_PATH.lower())
    return (p[i + len(LIST_PATH):] if i >= 0 else p).strip("/")


def _discount(price_c, was_c):
    if price_c and was_c and was_c > price_c:
        return round((1 - price_c / was_c) * 100)
    return None


def _parse(frag, block_type, item_id=None):
    """Turn one card fragment (a listing block or a whole detail page) into (Item, Obs)."""
    gn = _seg(frag, "goodNumber") or (item_id.split("/")[-1] if item_id else "")
    if not gn:
        return None
    make, model = _safe(_seg(frag, "make")), _safe(_seg(frag, "model"))
    year = _seg(frag, "year")
    price_c = _cents(_seg(frag, "price"))
    branch = _safe(_seg(frag, "responsibleBranch"))
    channel = _seg(frag, "salesChannel") or (block_type or "").replace("-", "").title() or "BuyNow"
    discounted = _seg(frag, "isDiscounted").lower() == "true"

    href = _HREF.search(frag)
    iid = item_id or (_path_tail(href.group(1)) if href else gn)

    was_c = _cents(_WAS.search(frag).group(1)) if _WAS.search(frag) else None
    if was_c is None and discounted:
        sm = _SAVE.search(frag)
        if sm and price_c is not None:
            was_c = price_c + _cents(sm.group(1))

    odo = None
    mo = _ODO.search(frag)
    if mo:
        odo = int((mo.group(1) or mo.group(2)).replace(",", ""))
    elif _KM.search(frag):
        odo = int(_KM.search(frag).group(1).replace(",", ""))
    avail = (_AVAIL.search(frag).group(1) if _AVAIL.search(frag) else "") or ""
    fuel = _safe(_FUEL.search(frag).group(1)) if _FUEL.search(frag) else ""
    body = _safe(_BODY.search(frag).group(1)) if _BODY.search(frag) else ""

    name = _safe(" ".join(x for x in (year, make, model) if x)) or f"car {gn}"
    item = Item(iid, name=name,
                subtitle=f"{branch}{('  ' + format(odo, ',') + 'km') if odo is not None else ''}".strip(),
                category=make,
                extra={"make": make, "model": model, "year": year, "odometer_km": odo,
                       "branch": branch, "fuel": fuel, "body": body, "channel": channel,
                       "url": HOST + LIST_PATH + iid})
    obs = Obs(price_cents=price_c, was_cents=was_c,
              flags={"currency": "NZD", "channel": channel, "discounted": discounted,
                     "discount_pct": _discount(price_c, was_c), "odometer_km": odo,
                     "branch": branch, "availability": avail})
    return item, obs


def _cards(html):
    """Split a listing page into (block_type, fragment) per car card."""
    bounds = [(m.start(), m.group(1)) for m in _CARD.finditer(html)]
    out = []
    for n, (start, bt) in enumerate(bounds):
        end = bounds[n + 1][0] if n + 1 < len(bounds) else len(html)
        out.append((bt, html[start:end]))
    return out


def _slug(term):
    return re.sub(r"[^a-z0-9-]+", "-", (term or "").lower().strip()).strip("-")


class _Client:
    def __init__(self):
        self.s = retry_session()

    def _get(self, path):
        r = self.s.get(HOST + path, headers={"Accept": "text/html", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.text

    def listing(self, make_slug=""):
        path = f"{LIST_PATH}{make_slug + '/' if make_slug else ''}?pagesize={PAGE_SIZE}&sortby=6,DESC"
        return [_parse(frag, bt) for bt, frag in _cards(self._get(path))]

    def detail(self, item_id):
        html = self._get(LIST_PATH + item_id)
        if "analytics-seg-info" not in html:
            return None
        return _parse(html, None, item_id=item_id)


def _match(rows, term):
    t = (term or "").lower()
    out = []
    for r in rows:
        if not r:
            continue
        item, _ = r
        hay = f"{item.name} {item.category} {item.extra.get('model', '')}".lower()
        if not t or t in hay:
            out.append(r)
    return out


class TurnersSource(Source):
    name = "turners"
    id_label = "STOCK#"
    cc_default = "nz"
    deal_label = "discount"   # deal = the car is marked down below its RRP

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = [r for r in cl.listing("") if r]
        return bool(rows), f"({len(rows)} cars on the latest page; page-published microdata)"

    def search(self, cl, term, args):
        hits = _match(cl.listing(_slug(term)), term)   # try the make path first
        if not hits:
            hits = _match(cl.listing(""), term)         # fall back to the latest listings
        return hits

    def fetch(self, cl, item_id):
        return cl.detail(item_id)

    def is_deal(self, obs):
        return bool(obs.flags.get("discounted")) and obs.was_cents is not None \
            and obs.price_cents is not None and obs.was_cents > obs.price_cents

    def deal_line(self, item, obs):
        pct = obs.flags.get("discount_pct")
        was = f"(was {money(obs.was_cents)}{', -' + str(pct) + '%' if pct else ''})  " if obs.was_cents else ""
        odo = obs.flags.get("odometer_km")
        km = f"{odo:,}km  " if odo is not None else ""
        return f"{money(obs.price_cents)}  {was}{km}{item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  vehicle  : {e.get('year', '')} {e.get('make', '')} {e.get('model', '')}".rstrip(),
                 f"  odometer : {format(e['odometer_km'], ',') + ' km' if e.get('odometer_km') is not None else '?'}"]
        drive = f"{e.get('fuel', '')} {e.get('body', '')}".strip()
        if drive:
            lines.append(f"  drivetrain: {drive}")
        lines += [f"  branch   : {e.get('branch', '')}",
                  f"  channel  : {e.get('channel', '')}"]
        if obs:
            lines.append(f"  price    : {money(obs.price_cents)}")
            if obs.was_cents:
                pct = obs.flags.get("discount_pct")
                lines.append(f"  rrp      : {money(obs.was_cents)}" + (f"  ({pct}% off)" if pct else ""))
            lines.append(f"  status   : {obs.flags.get('availability') or '?'}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = TurnersSource()
