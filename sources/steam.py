"""Steam - keyless public Storefront API (store.steampowered.com/api). Prices in cents."""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source, money

UA = "trove/0.1 (+https://github.com/LukeTheoJohnson/trove)"
BASE = "https://store.steampowered.com/api"


class _Client:
    def __init__(self, cc):
        self.cc = cc
        self.s = retry_session()

    def _get(self, path, params):
        r = self.s.get(f"{BASE}/{path}", params={**params, "cc": self.cc, "l": "en"},
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=30)
        r.raise_for_status()
        return r.json()

    def search(self, term):
        return self._get("storesearch/", {"term": term}).get("items", []) or []

    def appdetails(self, appid):
        d = self._get("appdetails", {"appids": appid,
                      "filters": "basic,price_overview,release_date,genres,platforms"})
        node = (d or {}).get(str(appid)) or {}
        return node.get("data") if node.get("success") else None


def _obs_from_price(po, is_free):
    if is_free:
        return Obs(price_cents=0, flags={"is_free": True})
    if not po:
        return Obs()
    return Obs(price_cents=po.get("final"), was_cents=po.get("initial"),
               flags={"discount_pct": po.get("discount_percent", 0)})


class SteamSource(Source):
    name = "steam"
    id_label = "APPID"
    cc_default = "nz"
    deal_label = "sale"

    def client(self, args):
        return _Client(args.cc)

    def doctor(self, cl):
        items = cl.search("portal")
        return bool(items), f"({len(items)} results for 'portal')"

    def search(self, cl, term, args):
        out = []
        for i in cl.search(term):
            if i.get("type") != "app":
                continue
            plat = i.get("platforms") or {}
            price = i.get("price") or {}
            item = Item(i.get("id"), i.get("name", ""), subtitle="app",
                        category=",".join(k for k in ("windows", "mac", "linux") if plat.get(k)),
                        extra={"metascore": i.get("metascore")})
            obs = Obs(price_cents=price.get("final"), was_cents=price.get("initial")) if price else None
            out.append((item, obs))
        return out

    def fetch(self, cl, appid):
        data = cl.appdetails(appid)
        if data is None:
            return None
        plat = data.get("platforms") or {}
        item = Item(appid, data.get("name", ""), subtitle=data.get("type", ""),
                    category=",".join(g.get("description", "") for g in (data.get("genres") or [])),
                    extra={"release": (data.get("release_date") or {}).get("date", ""),
                           "platforms": ",".join(k for k in ("windows", "mac", "linux") if plat.get(k))})
        return item, _obs_from_price(data.get("price_overview"), data.get("is_free"))

    def is_deal(self, obs):
        return (obs.flags.get("discount_pct") or 0) > 0

    def deal_line(self, item, obs):
        was = f" (was {money(obs.was_cents)})" if obs.was_cents else ""
        return f"-{obs.flags.get('discount_pct')}%  {money(obs.price_cents)}{was}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  type     : {item.subtitle}", f"  genres   : {item.category}",
                 f"  released : {item.extra.get('release', '')}"]
        if obs and obs.flags.get("is_free"):
            lines.append("  price    : Free")
        elif obs:
            d = obs.flags.get("discount_pct") or 0
            extra = f"  (was {money(obs.was_cents)}, -{d}%)" if d else ""
            lines.append(f"  price    : {money(obs.price_cents)}{extra}")
        return lines


SOURCE = SteamSource()
