"""em6 - NZ real-time wholesale electricity spot prices (keyless public tier).

em6 (app.em6.co.nz, a free market-transparency dashboard for the New Zealand electricity market)
serves a deliberately-public, keyless tier of its data API at
`https://api.em6.co.nz/ords/em6/data_api`: the endpoints the page itself calls without a login
(`/region/price/`, `/price`, `/price/free_24hrs`). The richer market views (`/demand`,
`/generation`, raw `/nodes`) sit behind an AWS Cognito login and are 401/403 keyless - this source
never touches them. Only the public, page-called tier is used.

The timeline value is the *ephemeral half-hourly spot price*: the wholesale price resets every
trading period (30 min) and nobody keeps an easily-grabbable per-region history, so the snapshot is
the only record - the whole point of hoarding it.

Model: one Item per grid zone (join key = grid_zone_id; 14 named zones - Auckland, Wellington,
Christchurch, Otago, Southland...), tracking the current spot price ($/MWh, NZD) as price_cents,
with the trading period, the snapshot timestamp, and the national cross-zone average carried in
flags. A "deal" = the zone is at or below the national average for the current trading period
(i.e. one of the cheaper regions to draw power right now). The half-hourly series the cache
accumulates is the real product; the deal flag is the cross-region cheap signal on top of it.

`search` lists/filters the 14 zones by name substring (the public endpoint returns them all in one
call; there is no free-text search). `--cc` is unused - the whole country is one set of zones.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source, money

UA = "trove/0.1 (+https://github.com/LukeTheoJohnson/trove)"
BASE = "https://api.em6.co.nz/ords/em6/data_api"


def _safe(s):
    """Fold to cp1252 (the Windows console codec) so an exotic char can't crash a print.
    The 14 zone names are plain ASCII today; this just future-proofs against a macron'd name."""
    return (s or "").strip().encode("cp1252", "replace").decode("cp1252")


def _cents(price):
    """$/MWh float -> whole cents int (clean money() display + sane drop granularity)."""
    try:
        return round(float(price) * 100)
    except (TypeError, ValueError):
        return None


def _avg_cents(zones):
    vals = [c for c in (_cents(z.get("price")) for z in zones) if c is not None]
    return round(sum(vals) / len(vals)) if vals else None


def _zone(z, avg_cents):
    pc = _cents(z.get("price"))
    item = Item(str(z.get("grid_zone_id", "")),
                name=_safe(z.get("grid_zone_name", "")),
                subtitle="NZ wholesale electricity spot ($/MWh)",
                category="spot",
                extra={"grid_zone_id": z.get("grid_zone_id")})
    obs = Obs(price_cents=pc,
              flags={"unit": "$/MWh",
                     "trading_period": z.get("trading_period"),
                     "timestamp": z.get("timestamp"),
                     "nat_avg": avg_cents})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()

    def regions(self):
        r = self.s.get(f"{BASE}/region/price/",
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return (r.json() or {}).get("items") or []


class Em6Source(Source):
    name = "em6"
    id_label = "ZONE"
    cc_default = "nz"        # unused; em6 serves the whole country in one call
    deal_label = "deal"      # deal = at/below the national average for this trading period

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        zones = cl.regions()
        return bool(zones), f"({len(zones)} grid zones; keyless em6 public tier)"

    def search(self, cl, term, args):
        zones = cl.regions()
        avg = _avg_cents(zones)
        t = term.lower()
        return [_zone(z, avg) for z in zones
                if t in str(z.get("grid_zone_name", "")).lower()]

    def fetch(self, cl, item_id):
        zones = cl.regions()
        avg = _avg_cents(zones)
        for z in zones:
            if str(z.get("grid_zone_id")) == str(item_id):
                return _zone(z, avg)
        return None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("nat_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        avg = obs.flags.get("nat_avg")
        gap = (f"  ({(obs.price_cents - avg) / 100:+.2f} vs NZ avg)"
               if avg is not None and obs.price_cents is not None else "")
        return f"{money(obs.price_cents)}/MWh{gap}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  region   : {item.name}",
                 f"  zone id  : {item.id}"]
        if obs:
            lines.append(f"  spot     : {money(obs.price_cents)} / MWh")
            tp = obs.flags.get("trading_period")
            ts = obs.flags.get("timestamp")
            lines.append(f"  period   : TP{tp}  ({ts})")
            avg = obs.flags.get("nat_avg")
            if avg is not None:
                lines.append(f"  NZ avg   : {money(avg)} / MWh")
                if obs.price_cents is not None:
                    lines.append(f"  vs avg   : {(obs.price_cents - avg) / 100:+.2f} / MWh")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = Em6Source()
