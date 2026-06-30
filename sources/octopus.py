"""octopus - UK Agile Octopus half-hourly electricity unit rates (keyless public API).

Agile Octopus (developer.octopus.energy, an official, documented, keyless REST API) prices
electricity in half-hourly periods that follow the wholesale market: a fresh set of 48 unit rates
for the next day is published each afternoon, and the rate can even go *negative* when there's a
renewables glut ("plunge pricing" - you get paid to use power). This source tracks the current
half-hourly unit rate per GB distribution region.

The genre twin of `em6` (NZ wholesale spot): both hoard an ephemeral half-hourly electricity price
that resets every period. Honest caveat on hoard value: unlike em6, Octopus serves the *full*
realized rate history from the same endpoint (tens of thousands of past periods, paginated), so the
realized series is rebuildable - this is closer to a PoC / genre-completing source than an
un-rebuildable moat. Its draw is the clean per-region current-rate series + the cheap/plunge-window
deal signal, and rounding out the electricity genre across both hemispheres.

Model: one Item per GB region (join key = the single-letter GSP - Grid Supply Point - group
A,B,C,...,P; 14 regions, no I or O), tracking the current half-hourly unit rate (pence/kWh, inc VAT)
as price_cents (rate * 100, so 29.63 p/kWh stores as 2963 and money() renders "$29.63" - the
rate-as-dollars cosmetic shared with em6/geonet/metno; the rich displays show proper p/kWh). A
"deal" = the current period is at or below today's average rate (a cheap half-hour to run the
dishwasher), or a negative rate (plunge pricing, flagged prominently). The half-hourly series the
cache accumulates is the product; the deal flag is the cheap-window signal on top.

`search` lists/filters the 14 regions from one product-detail call (Octopus's headline per-region
rate; obs tagged basis="headline"). `item`/`poll` pull a region's half-hourly series for the precise
current rate (basis="half_hour") + today's average baseline + plunge detection. The current Agile
import product code is discovered at runtime (it's renamed ~yearly), so this keeps working when a new
Agile vintage supersedes the last. `--cc` is unused - GB regions are one set.
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money

BASE = "https://api.octopus.energy/v1"

# GB GSP (Grid Supply Point) groups -> region name. Agile exposes one tariff per group.
REGIONS = {
    "A": "Eastern England", "B": "East Midlands", "C": "London",
    "D": "Merseyside & North Wales", "E": "West Midlands", "F": "North East England",
    "G": "North West England", "H": "Southern England", "J": "South East England",
    "K": "South Wales", "L": "South West England", "M": "Yorkshire",
    "N": "Southern Scotland", "P": "Northern Scotland",
}


def _cents(rate):
    """p/kWh float -> whole centi-pence int (clean money() display + sane drop granularity)."""
    try:
        return round(float(rate) * 100)
    except (TypeError, ValueError):
        return None


def _p(cents):
    """Render the stored scalar as a proper p/kWh string for the rich displays."""
    return "?" if cents is None else f"{cents / 100:.2f} p/kWh"


def _parse(ts):
    """ISO 8601 (trailing Z or numeric offset) -> aware UTC datetime, or None."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return None


def _current(rates, when=None):
    """The half-hourly row covering `when` (default now, UTC); fall back to the newest row."""
    when = when or datetime.now(timezone.utc)
    for r in rates:
        a, b = _parse(r.get("valid_from")), _parse(r.get("valid_to"))
        if a and b and a <= when < b:
            return r
    return rates[0] if rates else None


def _next_period(rates, cur):
    """The period immediately after `cur` (matches its valid_to to a row's valid_from)."""
    vt = cur.get("valid_to") if cur else None
    for r in rates:
        if vt and r.get("valid_from") == vt:
            return r
    return None


def _day_avg_cents(rates, when=None):
    """Average inc-VAT rate over the periods on `when`'s UTC date (today's typical rate)."""
    when = when or datetime.now(timezone.utc)
    day = when.date()
    vals = [c for r in rates
            if (a := _parse(r.get("valid_from"))) and a.date() == day
            for c in (_cents(r.get("value_inc_vat")),) if c is not None]
    return round(sum(vals) / len(vals)) if vals else None


def _region_item(region):
    return Item(region,
                name=REGIONS.get(region, region),
                subtitle="Agile Octopus half-hourly unit rate (p/kWh, inc VAT)",
                category="electricity",
                extra={"gsp_group": "_" + region})


def _headline_obs(node):
    """Browse-list obs from the product-detail headline rate (basis=headline)."""
    dd = (node or {}).get("direct_debit_monthly") or {}
    return Obs(price_cents=_cents(dd.get("standard_unit_rate_inc_vat")),
               flags={"unit": "p/kWh", "basis": "headline"})


def _region_obs(rates):
    """Tracked obs from a region's half-hourly series: the exact current period (basis=half_hour)."""
    cur = _current(rates)
    if cur is None:
        return Obs()
    pc = _cents(cur.get("value_inc_vat"))
    nxt = _next_period(rates, cur)
    return Obs(price_cents=pc,
               flags={"unit": "p/kWh", "basis": "half_hour",
                      "valid_from": cur.get("valid_from"), "valid_to": cur.get("valid_to"),
                      "day_avg": _day_avg_cents(rates),
                      "next_rate": _cents(nxt.get("value_inc_vat")) if nxt else None,
                      "plunge": pc is not None and pc < 0})


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._product = None  # cached Agile import product code

    def _get(self, path, params=None):
        r = self.s.get(f"{BASE}/{path}", params=params or {},
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json()

    def product(self):
        """Current Agile import product code (renamed ~yearly; discover, don't hardcode)."""
        if self._product:
            return self._product
        data = self._get("products/", {"brand": "OCTOPUS_ENERGY"})
        agile = [p for p in data.get("results", [])
                 if p.get("display_name") == "Agile Octopus" and p.get("direction") == "IMPORT"]
        if not agile:
            raise RuntimeError("no Agile import product in Octopus catalogue")
        now = datetime.now(timezone.utc)
        started = [p for p in agile if (_parse(p.get("available_from")) or now) <= now]
        self._product = sorted(started or agile, key=lambda p: p.get("available_from") or "")[-1]["code"]
        return self._product

    def headline_rates(self):
        """One call: every region's headline current unit rate (from the product detail)."""
        code = self.product()
        d = self._get(f"products/{code}/")
        return code, d.get("single_register_electricity_tariffs") or {}

    def region_rates(self, region):
        """A region's recent half-hourly series (newest first, ~2 days)."""
        code = self.product()
        tariff = f"E-1R-{code}-{region}"
        d = self._get(f"products/{code}/electricity-tariffs/{tariff}/standard-unit-rates/",
                      {"page_size": 96})
        return d.get("results") or []


class OctopusSource(Source):
    name = "octopus"
    id_label = "GSP"
    cc_default = "gb"        # unused; GB regions are one set served by one product
    deal_label = "cheap"     # deal = at/below today's average rate, or a negative (plunge) rate
    search_header = f"{'RATE':>12}  REGION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        code, tariffs = cl.headline_rates()
        return bool(tariffs), f"({len(tariffs)} regions; Agile product {code}; keyless Octopus API)"

    def search(self, cl, term, args):
        _code, tariffs = cl.headline_rates()
        t = term.lower()
        out = []
        for region, region_name in REGIONS.items():
            if t and t not in region_name.lower() and t != region.lower():
                continue
            out.append((_region_item(region), _headline_obs(tariffs.get("_" + region))))
        return out

    def fetch(self, cl, item_id):
        region = str(item_id).upper().lstrip("_")
        if region not in REGIONS:
            return None
        rates = cl.region_rates(region)
        if not rates:
            return None
        return _region_item(region), _region_obs(rates)

    def is_deal(self, obs):
        pc = obs.price_cents
        if pc is None:
            return False
        if pc < 0:                       # plunge pricing - paid to use power
            return True
        avg = obs.flags.get("day_avg")
        return avg is not None and pc <= avg

    def search_row(self, item, obs):
        return f"{(_p(obs.price_cents) if obs else '?'):>12}  {item.name}"

    def deal_line(self, item, obs):
        pc = obs.price_cents
        if pc is not None and pc < 0:
            tag = "  PLUNGE (paid to use)"
        else:
            avg = obs.flags.get("day_avg")
            tag = (f"  ({(pc - avg) / 100:+.2f} vs day avg)"
                   if avg is not None and pc is not None else "")
        return f"{_p(pc)}{tag}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  region   : {item.name}  (GSP group {item.extra.get('gsp_group', '_' + str(item.id))})",
                 "  tariff   : Agile Octopus"]
        if obs:
            pc = obs.price_cents
            lines.append(f"  rate now : {_p(pc)}  ({obs.flags.get('valid_from', '')} -> {obs.flags.get('valid_to', '')})")
            nxt = obs.flags.get("next_rate")
            if nxt is not None:
                lines.append(f"  next 30m : {_p(nxt)}")
            avg = obs.flags.get("day_avg")
            if avg is not None:
                lines.append(f"  day avg  : {_p(avg)}")
                if pc is not None:
                    lines.append(f"  vs avg   : {(pc - avg) / 100:+.2f} p/kWh")
            if obs.flags.get("plunge"):
                lines.append("  PLUNGE   : negative price - you're paid to use power")
        return lines


SOURCE = OctopusSource()
