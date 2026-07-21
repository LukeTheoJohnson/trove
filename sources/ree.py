"""ree - Spanish electricity market prices via Red Electrica's apidatos, keyless JSON.

Red Electrica de Espana (REE, the Spanish TSO) publishes real-time market prices through its keyless
open API `apidatos.ree.es/en/datos/mercados/precios-mercados-tiempo-real`: the regulated retail PVPC
price and the wholesale Spot market price for the Iberian peninsula, in EUR/MWh, at hourly / 15-minute
resolution across the day. robots.txt is 404 (unfenced) and the API is published for public reuse =
sanctioned -> trove. The Iberian electricity twin of `em6`/`aeso`/`nyiso`/`energinet`, opening **Spain**
and pairing with `spainfuel` on the energy side.

The tracked scalar is the ephemeral clearing price. The API serves the *whole day* including future
hours (tomorrow's auction shape), so - like `energinet` - the client bounds "current" to the latest
value whose timestamp has already passed. Honest hoard value is low-med (REE archives settled prices);
`price_cents` = the current value (EUR/MWh) * 100 so the core's `drops` = the price *falling*; `qty` =
None. A "deal" ("cheap") = the current price is at or below the day's mean.

Model: one Item per series - `pvpc` (regulated retail) and `spot` (wholesale market). One memoized GET
returns both. `--cc` is unused (one peninsular market); `search`/`fetch` read the same feed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://apidatos.ree.es/en/datos/mercados/precios-mercados-tiempo-real"
# apidatos included[].type -> our item id
SERIES = {"PVPC": ("pvpc", "PVPC regulated retail price"),
          "Spot market price": ("spot", "Spanish wholesale spot price")}


def _now():
    return datetime.now(timezone.utc)


def _parse_dt(s):
    try:
        return datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None


def _current(values):
    """Latest value whose datetime has already passed (bound to now; the feed carries future hours)."""
    now = _now()
    past = [v for v in values if (_parse_dt(v.get("datetime")) or now) <= now]
    pool = past or values
    if not pool:
        return None
    return max(pool, key=lambda v: v.get("datetime") or "")


def _build(sid, subtitle, values):
    cur = _current(values)
    if cur is None:
        return None
    vals = [v.get("value") for v in values if isinstance(v.get("value"), (int, float))]
    mean = round(sum(vals) / len(vals), 2) if vals else None
    price = cur.get("value")
    item = Item(sid, name=subtitle, subtitle="REE Iberian market (EUR/MWh)", category="ES",
                extra={"unit": "EUR/MWh"})
    obs = Obs(price_cents=(round(price * 100) if isinstance(price, (int, float)) else None), qty=None,
              flags={"price": price, "day_mean": mean, "at": cur.get("datetime") or "", "unit": "EUR/MWh"})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._series = None

    def series(self):
        if self._series is None:
            now = _now()
            day = now.strftime("%Y-%m-%d")
            r = self.s.get(BASE, params={"start_date": f"{day}T00:00", "end_date": f"{day}T23:59",
                                         "time_trunc": "hour"},
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            out = {}
            for inc in (r.json() or {}).get("included", []):
                typ = inc.get("type")
                if typ in SERIES:
                    sid, sub = SERIES[typ]
                    out[sid] = (sub, (inc.get("attributes") or {}).get("values") or [])
            self._series = out
        return self._series


class ReeSource(Source):
    name = "ree"
    id_label = "SERIES"
    cc_default = "es"        # unused
    deal_label = "cheap"     # current price at/below the day's mean
    search_header = f"{'EUR/MWh':>9}  SERIES"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        s = cl.series()
        return bool(s), f"({len(s)} price series (pvpc/spot); keyless REE apidatos)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for sid, (sub, values) in cl.series().items():
            if t and t not in sid:
                continue
            built = _build(sid, sub, values)
            if built:
                out.append(built)
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out

    def fetch(self, cl, item_id):
        s = cl.series().get(str(item_id))
        return _build(str(item_id), s[0], s[1]) if s else None

    def is_deal(self, obs):
        p, mean = obs.flags.get("price"), obs.flags.get("day_mean")
        return p is not None and mean is not None and p <= mean

    def deal_line(self, item, obs):
        f = obs.flags
        gap = (f"  ({f['price'] - f['day_mean']:+.2f} vs day mean)"
               if f.get("day_mean") is not None else "")
        return f"{f.get('price')} EUR/MWh{gap}  {item.name}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(str(f.get('price')) if f.get('price') is not None else '?'):>9}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  series   : {item.name}  ({item.id})"]
        if obs:
            f = obs.flags
            lines.append(f"  price    : {f.get('price')} EUR/MWh   (at {f.get('at')})")
            lines.append(f"  day mean : {f.get('day_mean')} EUR/MWh")
        return lines


SOURCE = ReeSource()
