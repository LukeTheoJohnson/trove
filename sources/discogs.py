"""Discogs - official REST API (api.discogs.com), keyless reads. Requires a descriptive UA.
fetch uses /releases (rich); refresh uses /marketplace/stats (lean, NZD-correct)."""
from __future__ import annotations

import os

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money

BASE = "https://api.discogs.com"


class _Client:
    def __init__(self, curr):
        self.curr = curr
        self.s = retry_session()
        self.token = os.environ.get("DISCOGS_TOKEN")

    def _get(self, path, params=None):
        h = {"Accept": "application/json", "User-Agent": UA}
        if self.token:
            h["Authorization"] = f"Discogs token={self.token}"
        r = self.s.get(f"{BASE}/{path}", params=params or {}, headers=h, timeout=30)
        r.raise_for_status()
        return r.json()

    def search(self, term, per_page=20):
        return self._get("database/search", {"q": term, "type": "release", "per_page": per_page}).get("results", []) or []

    def release(self, rid):
        return self._get(f"releases/{rid}", {"curr_abbr": self.curr})

    def stats(self, rid):
        return self._get(f"marketplace/stats/{rid}", {"curr_abbr": self.curr})


def _cents(lowest):
    v = lowest.get("value") if isinstance(lowest, dict) else lowest
    return round(v * 100) if isinstance(v, (int, float)) else None


class DiscogsSource(Source):
    name = "discogs"
    id_label = "RELEASE"
    cc_default = "NZD"
    deal_label = "for-sale"

    def client(self, args):
        return _Client(args.cc)

    def doctor(self, cl):
        s = cl.stats(249504)
        return ("num_for_sale" in s), f"(num_for_sale={s.get('num_for_sale')})"

    def search(self, cl, term, args):
        out = []
        for i in cl.search(term):
            if not i.get("id"):
                continue
            fmt = i.get("format") or []
            out.append((Item(i["id"], i.get("title", ""), subtitle=str(i.get("year") or ""),
                             category=",".join(fmt) if isinstance(fmt, list) else str(fmt)), None))
        return out

    def fetch(self, cl, rid):
        d = cl.release(rid)
        arts = d.get("artists") or [{}]
        comm = d.get("community") or {}
        item = Item(d.get("id"), d.get("title", ""), subtitle=arts[0].get("name", "") if arts else "",
                    category=",".join(f.get("name", "") for f in (d.get("formats") or [])),
                    extra={"year": d.get("year"), "have": comm.get("have"), "want": comm.get("want")})
        obs = Obs(price_cents=_cents(d.get("lowest_price")), qty=d.get("num_for_sale"))
        return item, obs

    def refresh(self, cl, rid):
        s = cl.stats(rid)
        return Item(rid), Obs(price_cents=_cents(s.get("lowest_price")), qty=s.get("num_for_sale"))

    def is_deal(self, obs):
        return (obs.qty or 0) > 0

    def deal_line(self, item, obs):
        return f"{money(obs.price_cents)}  ({obs.qty} for sale)  {item.name}"

    def format_item(self, item, obs):
        return [f"  artist   : {item.subtitle}", f"  year     : {item.extra.get('year')}",
                f"  format   : {item.category}",
                f"  for sale : {obs.qty if obs else '?'}  (lowest {money(obs.price_cents) if obs else '?'})",
                f"  community: {item.extra.get('have')} have / {item.extra.get('want')} want"]


SOURCE = DiscogsSource()
