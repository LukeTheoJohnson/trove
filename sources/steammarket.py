"""steammarket - Steam Community Market live listings via Valve's keyless market backend.

The Steam Community Market is Steam's player-to-player marketplace for in-game items (CS2 skins,
TF2 hats, trading cards...). Each item is fungible - many identical copies listed at once - so what
churns is the **market state**: the lowest asking price, how many are listed right now (depth), and
the 24h sales volume. That live state is the ephemeral thing this source hoards; Valve exposes the
current snapshot but keeps no convenient public per-item history. The market page itself calls
`steamcommunity.com/market/search/render/` (discovery) and `/market/priceoverview/` (per item),
both keyless (robots fences only /trade, /tradeoffer, /actions, /email - never /market), so this is
a sanctioned, page-called public endpoint -> trove. It's the fungible-goods complement to
reverb/discogs (unique listings): here the signal is lowest-ask + depth + volume, not one vanishing
listing. Honest hoard value low-med: third-party sites archive median prices, so the draw is the
live depth/volume snapshot + completing the marketplace set, not un-rebuildability.

Model: one Item per market good (join key = `appid:market_hash_name`; the hash name is the item's
canonical English name). Two source-tags share the obs log (grabone pattern, see flags.src):
- `search` rows (render): price_cents = `sell_price` (lowest ask, integer cents, USD), qty =
  `sell_listings` (how many are listed = depth).
- `item`/`poll` rows (priceoverview): price_cents = parsed `lowest_price`, qty = parsed 24h
  `volume`, flags.median_cents = parsed `median_price`. Deal "cheap" = lowest ask below the 24h
  median (a good buy moment). The core's `drops` = the lowest ask falling below first seen.

Steam's market search is USD-only without auth (it ignores the currency param), so `--cc` (a Steam
currency code, e.g. 22=NZD) only localises `item`/`poll` via priceoverview; keep the default USD (1)
for a consistent price series. `--app` picks the game (default 730 = Counter-Strike 2).
"""
from __future__ import annotations

from urllib.parse import quote

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://steamcommunity.com/market"


def _cents_from_text(s):
    """Steam price text ('$34.58', 'NZ$ 75.67', '$1,234.56') -> integer cents, or None."""
    if not s:
        return None
    keep = "".join(ch for ch in str(s) if ch.isdigit() or ch in ".,")
    if not keep:
        return None
    if "," in keep and "." in keep:
        keep = keep.replace(",", "")          # comma = thousands separator
    elif "," in keep and "." not in keep:
        keep = keep.replace(",", ".")         # comma = decimal (some locales)
    try:
        return round(float(keep) * 100)
    except ValueError:
        return None


def _int(s):
    try:
        return int(str(s).replace(",", "")) if s not in (None, "") else None
    except ValueError:
        return None


def _url(app, hash_name):
    return f"{BASE}/listings/{app}/{quote(hash_name)}"


def _from_result(r, app):
    """One search/render result -> (Item, Obs). All fields from the live payload."""
    ad = r.get("asset_description") or {}
    appid = ad.get("appid") or app
    hn = r.get("hash_name", "")
    item = Item(f"{appid}:{hn}", name=safe(hn), subtitle=safe(r.get("app_name", "")),
                category=safe(ad.get("type", "")),
                extra={"app": appid, "hash_name": hn, "icon": r.get("app_icon"),
                       "url": _url(appid, hn), "tradable": ad.get("tradable")})
    obs = Obs(price_cents=r.get("sell_price"), qty=r.get("sell_listings"),
              flags={"src": "search", "listings": r.get("sell_listings"), "currency": "USD"})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.cc = str(cc or "1")
        self.s = retry_session()

    def _get(self, path, params):
        r = self.s.get(f"{BASE}/{path}", params=params,
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=30)
        r.raise_for_status()
        return r.json()

    def search(self, term, app, count):
        return self._get("search/render/", {"query": term, "appid": app, "start": 0,
                         "count": max(1, min(count, 100)), "norender": 1}).get("results", []) or []

    def overview(self, app, hash_name):
        return self._get("priceoverview/", {"appid": app, "market_hash_name": hash_name,
                         "currency": self.cc})


class SteamMarketSource(Source):
    name = "steammarket"
    id_label = "APP:HASH"
    cc_default = "1"           # Steam currency code (1=USD default; 22=NZD) - localises priceoverview only
    deal_label = "cheap"       # deal = lowest ask below the 24h median
    search_args = [("--app", {"type": int, "default": 730, "help": "Steam appid (default 730 = CS2)"})]
    search_header = f"{'PRICE':>10}  {'LISTED':>6}  NAME"

    def client(self, args):
        return _Client(args.cc)

    def doctor(self, cl):
        d = cl.overview(730, "AK-47 | Redline (Field-Tested)")
        ok = bool(d and d.get("success"))
        return ok, f"(priceoverview ok: lowest={d.get('lowest_price')}, vol={d.get('volume')})"

    def search(self, cl, term, args):
        app = getattr(args, "app", 730)
        out = []
        for r in cl.search(term, app, args.limit):
            if not r.get("hash_name"):
                continue
            out.append(_from_result(r, app))
        return out

    def fetch(self, cl, item_id):
        appid, _, hn = str(item_id).partition(":")
        if not hn:
            return None
        d = cl.overview(appid, hn)
        if not d or not d.get("success"):
            return None
        low = _cents_from_text(d.get("lowest_price"))
        med = _cents_from_text(d.get("median_price"))
        vol = _int(d.get("volume"))
        if low is None and med is None:
            return None
        item = Item(f"{appid}:{hn}", name=safe(hn),
                    extra={"app": appid, "hash_name": hn, "url": _url(appid, hn)})
        obs = Obs(price_cents=low, qty=vol,
                  flags={"src": "overview", "median_cents": med, "volume": vol,
                         "currency": cl.cc, "median_text": safe(d.get("median_price") or "")})
        return item, obs

    def is_deal(self, obs):
        m = obs.flags.get("median_cents")
        return bool(m) and obs.price_cents is not None and obs.price_cents < m

    def deal_line(self, item, obs):
        m = obs.flags.get("median_cents")
        return f"{money(obs.price_cents)}  (median {money(m)})  {item.name}"

    def search_row(self, item, obs):
        listed = obs.flags.get("listings") if obs else None
        listed = str(listed) if listed is not None else "?"
        return f"{money(obs.price_cents) if obs else '?':>10}  {listed:>6}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  app       : {item.subtitle or e.get('app', '')}",
                 f"  type      : {item.category}"]
        if obs:
            f = obs.flags
            if f.get("src") == "overview":
                lines.append(f"  lowest    : {money(obs.price_cents)}  (cc {f.get('currency')})")
                lines.append(f"  median    : {money(f.get('median_cents'))}")
                lines.append(f"  volume 24h: {f.get('volume')}")
            else:
                lines.append(f"  lowest    : {money(obs.price_cents)}  USD")
                lines.append(f"  listed    : {f.get('listings')}")
        lines.append(f"  url       : {e.get('url', '')}")
        return lines


SOURCE = SteamMarketSource()
