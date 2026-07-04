"""fuelwatch - Western Australia per-station fuel prices via the government FuelWatch RSS feed.

FuelWatch is a WA Government price-transparency scheme (run by Consumer Protection): every WA service
station must notify the next day's price by 2pm and hold it for 24 hours. FuelWatch publishes those
prices as a keyless RSS feed - `GET fuelwatch.wa.gov.au/fuelwatch/fuelWatchRSS?Product=<n>` returns
every station's price for a fuel product in one call. robots.txt fences only account paths
(/subscription, /login...), never /fuelwatch = sanctioned -> trove. The AU (WA) sibling of `petrolspy`
(NZ/AU crowd-sourced) and `spainfuel` (Spain), but from the official regulator rather than a crowd.

The timeline value is the *ephemeral per-station forecourt price*: a legally-fixed daily price that is
overwritten each day and never archived per-station in a queryable series, so the snapshot is the only
record. `price_cents` = the pump price in whole cents/L (so money() shows $/L; the exact tenth-cent
rides in `flags.price_c`), and a "deal" = the station is at or below its **suburb** average today
(cheaper than its neighbours). One GET returns the whole state (~940 stations), memoized, so search
and a full poll share a single request.

Model: one Item per station. FuelWatch's RSS carries no station id, so the join key is composite
`SUBURB|ADDRESS` (unique per forecourt, stable day to day); `fetch` scans the memoized board for it.
`Product=1` (unleaded 91) is the tracked product; `search <term>` filters the board by
brand/suburb/trading-name substring (pass "" to list them all). `--cc` is unused - WA is one board.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://www.fuelwatch.wa.gov.au/fuelwatch/fuelWatchRSS"
PRODUCT = "1"       # 1 = Unleaded 91 (the tracked headline grade)
PRODUCT_NAME = "ULP"


def _txt(item, tag):
    el = item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def _parse(xml_bytes):
    """FuelWatch RSS bytes -> list of station dicts (raw fields read from the live feed)."""
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.iter("item"):
        price = _txt(it, "price")
        try:
            pc = round(float(price))
        except ValueError:
            pc = None
        out.append({"brand": _txt(it, "brand"), "trading": _txt(it, "trading-name"),
                    "suburb": _txt(it, "location"), "address": _txt(it, "address"),
                    "phone": _txt(it, "phone"), "features": _txt(it, "site-features"),
                    "restrictions": _txt(it, "restrictions"), "date": _txt(it, "date"),
                    "lat": _txt(it, "latitude"), "lon": _txt(it, "longitude"),
                    "price_c": (float(price) if price else None), "price_cents": pc})
    return out


def _key(st):
    return f"{st.get('suburb', '')}|{st.get('address', '')}"


def _suburb_avgs(board):
    """suburb -> mean whole-cent price across its stations."""
    acc = {}
    for st in board:
        pc = st.get("price_cents")
        if pc is not None:
            acc.setdefault(st.get("suburb", ""), []).append(pc)
    return {sub: round(sum(v) / len(v)) for sub, v in acc.items() if v}


def _station(st, avgs):
    avg = avgs.get(st.get("suburb", ""))
    item = Item(_key(st), name=safe(st.get("trading") or st.get("brand") or _key(st)),
                subtitle=safe(f"{st.get('address', '')}, {st.get('suburb', '')}"),
                category=safe(st.get("brand", "")),
                extra={"brand": safe(st.get("brand", "")), "suburb": safe(st.get("suburb", "")),
                       "address": safe(st.get("address", "")), "phone": st.get("phone", ""),
                       "features": safe(st.get("features", "")), "lat": st.get("lat"),
                       "lon": st.get("lon")})
    obs = Obs(price_cents=st.get("price_cents"),
              flags={"product": PRODUCT_NAME, "unit": "cents/L", "price_c": st.get("price_c"),
                     "brand": safe(st.get("brand", "")), "suburb": safe(st.get("suburb", "")),
                     "suburb_avg": avg, "date": st.get("date"),
                     "restrictions": safe(st.get("restrictions", ""))})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._board = None

    def board(self):
        if self._board is None:
            r = self.s.get(FEED, params={"Product": PRODUCT},
                           headers={"User-Agent": UA, "Accept": "application/rss+xml"}, timeout=45)
            r.raise_for_status()
            self._board = _parse(r.content)
        return self._board


class FuelWatchSource(Source):
    name = "fuelwatch"
    id_label = "SUBURB|ADDRESS"
    cc_default = "wa"        # unused; FuelWatch is one WA board
    deal_label = "deal"      # deal = at/below the station's suburb average today
    search_limit_default = 20

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        board = cl.board()
        return bool(board), f"({len(board)} WA stations, {PRODUCT_NAME}; keyless FuelWatch RSS)"

    def search(self, cl, term, args):
        board = cl.board()
        avgs = _suburb_avgs(board)
        t = (term or "").lower()
        out = []
        for st in board:
            hay = " ".join(str(st.get(k, "")) for k in ("brand", "trading", "suburb", "address")).lower()
            if not t or t in hay:
                out.append(_station(st, avgs))
        out.sort(key=lambda io: (io[1].price_cents is None, io[1].price_cents or 0))  # cheapest first
        return out

    def fetch(self, cl, item_id):
        board = cl.board()
        avgs = _suburb_avgs(board)
        for st in board:
            if _key(st) == str(item_id):
                return _station(st, avgs)
        return None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("suburb_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        avg = obs.flags.get("suburb_avg")
        gap = (f"  ({(obs.price_cents - avg) / 100:+.2f} vs {obs.flags.get('suburb')} avg)"
               if avg is not None and obs.price_cents is not None else "")
        return f"{money(obs.price_cents)}/L {PRODUCT_NAME}{gap}  {item.name}"

    def search_row(self, item, obs):
        pc = obs.price_cents if obs else None
        return f"{(money(pc) + '/L') if pc is not None else '?':>10}  {item.category[:10]:<10}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  brand    : {e.get('brand', '')}",
                 f"  address  : {e.get('address', '')}, {e.get('suburb', '')}",
                 f"  phone    : {e.get('phone', '')}",
                 f"  features : {e.get('features', '')}"]
        if obs:
            f = obs.flags
            lines.append(f"  price    : {money(obs.price_cents)}/L {PRODUCT_NAME}  (as at {f.get('date', '?')})")
            avg = f.get("suburb_avg")
            if avg is not None:
                lines.append(f"  suburb avg: {money(avg)}/L  ({e.get('suburb', '')}; this station {(obs.price_cents - avg) / 100:+.2f})")
            if f.get("restrictions"):
                lines.append(f"  note     : {f.get('restrictions')}")
        return lines


SOURCE = FuelWatchSource()
