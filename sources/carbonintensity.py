"""carbonintensity - Great Britain regional grid carbon intensity forecast + generation mix, keyless.

National Grid ESO runs the official Carbon Intensity API at api.carbonintensity.org.uk. `GET /regional`
returns the current half-hour's forecast CO2 intensity (gCO2/kWh) for each of the ~14 GB DNO regions
(North Scotland, London, South Wales, ...) plus a human `index` ("very low" .. "very high") and the
live generation mix (% wind / solar / gas / nuclear / imports / ...). The host serves no robots.txt
(a valid-path error, = unfenced) and the API is documented for public reuse = sanctioned -> trove.
A carbon-flavoured mate for the wholesale-price electricity sources (`em6`/`aemo`/`octopus`): same
half-hourly grid cadence, but the tracked scalar is *how dirty the electrons are*, not their price.

The timeline value is the **forecast as-issued**: each region's intensity is a forward estimate that
is revised as wind/demand shift, and while the API archives *realized* intensity, it does not serve a
queryable per-region history of what each half-hour's forecast *said* at issue - the `metno`/
`spaceweather` revision-drift class. `price_cents` = forecast intensity (gCO2/kWh) * 100, so the core's
`drops` = the grid getting *greener* (lower carbon); `qty` = the renewable share % (wind + solar +
hydro + biomass). A "deal" ("clean") = the region's index is "very low" or "low" (a good moment to run
heavy load). money() renders the centi-intensity as dollars in the two core-hardcoded spots (61 gCO2 ->
$61.00); the rich views show gCO2/kWh + the index + the mix.

Model: one Item per GB region (join key = `regionid`, 1-17). `search <term>` filters the regions by
name (pass "" to list them all, greenest first); `fetch` reads one region from the same memoized call.
`--cc` is unused - GB is one set of regions.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://api.carbonintensity.org.uk"
CLEAN = {"very low", "low"}
RENEWABLE = {"wind", "solar", "hydro", "biomass"}


def _mix(region):
    return {m.get("fuel"): m.get("perc") for m in (region.get("generationmix") or [])}


def _renew_pct(mix):
    return round(sum(v for f, v in mix.items() if f in RENEWABLE and isinstance(v, (int, float))))


def _build(region):
    rid = str(region.get("regionid", ""))
    intensity = region.get("intensity") or {}
    fc = intensity.get("forecast")
    idx = intensity.get("index")
    mix = _mix(region)
    name = safe(region.get("shortname") or region.get("dnoregion") or rid)
    item = Item(rid, name=name, subtitle="GB grid region (carbon intensity)", category="region",
                extra={"dnoregion": safe(region.get("dnoregion", ""))})
    obs = Obs(price_cents=(round(fc * 100) if isinstance(fc, (int, float)) else None),
              qty=_renew_pct(mix),
              flags={"gco2_kwh": fc, "index": idx, "renewable_pct": _renew_pct(mix),
                     "mix": {f: v for f, v in mix.items() if isinstance(v, (int, float)) and v > 0}})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._regions = None

    def regions(self):
        if self._regions is None:
            r = self.s.get(f"{BASE}/regional", headers={"Accept": "application/json", "User-Agent": UA},
                           timeout=40)
            r.raise_for_status()
            data = (r.json() or {}).get("data") or []
            self._regions = (data[0].get("regions") if data else []) or []
        return self._regions


class CarbonIntensitySource(Source):
    name = "carbonintensity"
    id_label = "REGION"
    cc_default = "uk"        # unused; GB is one set of regions
    deal_label = "clean"     # index very low / low = a green moment to run heavy load
    search_limit_default = 20
    search_header = f"{'gCO2':>5}  {'INDEX':<10}  {'REN%':>4}  REGION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rs = cl.regions()
        return bool(rs), f"({len(rs)} GB regions; keyless National Grid ESO Carbon Intensity API)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for region in cl.regions():
            item, obs = _build(region)
            if not t or t in item.name.lower() or t in item.extra.get("dnoregion", "").lower():
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9,
                                 io[0].name.lower()))
        return out

    def fetch(self, cl, item_id):
        for region in cl.regions():
            if str(region.get("regionid")) == str(item_id):
                return _build(region)
        return None

    def is_deal(self, obs):
        return (obs.flags.get("index") or "").lower() in CLEAN

    def deal_line(self, item, obs):
        return f"{obs.flags.get('gco2_kwh')} gCO2/kWh  ({obs.flags.get('index')})  {obs.flags.get('renewable_pct')}% renewable  {item.name}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(f.get('gco2_kwh') if f.get('gco2_kwh') is not None else '?'):>5}  {safe(f.get('index') or '-'):<10}  {(f.get('renewable_pct') if f.get('renewable_pct') is not None else '?'):>4}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  region   : {item.name}  ({item.id})",
                 f"  dno      : {item.extra.get('dnoregion') or '?'}"]
        if obs:
            f = obs.flags
            lines.append(f"  intensity: {f.get('gco2_kwh')} gCO2/kWh   index {f.get('index')}")
            lines.append(f"  renewable: {f.get('renewable_pct')}%")
            mix = f.get("mix") or {}
            if mix:
                top = sorted(mix.items(), key=lambda kv: -kv[1])[:4]
                lines.append("  mix      : " + ", ".join(f"{k} {v}%" for k, v in top))
        return lines


SOURCE = CarbonIntensitySource()
