"""sentry - JPL CNEOS Sentry asteroid impact-risk list: the planetary-defence drift hoard.

Sentry is NASA/JPL's automated collision-monitoring system: every near-Earth asteroid whose orbit
cannot yet rule out an Earth impact sits on the risk list with an impact probability (`ip`), a
cumulative Palermo scale (`ps_cum`, log10 of risk relative to background - almost always negative),
a Torino scale (`ts_max`, the public 0-10 hazard colour), and a count of potential impacts
(`n_imp`). `ssd-api.jpl.nasa.gov` serves the official, keyless, documented Sentry API with no
robots.txt (404 = unfenced) = sanctioned -> trove. New domain for trove: planetary defence.

The ephemeral thing this source hoards is the **risk list as issued**: as new observations arrive,
an object's ps/ip/ts get revised and most objects are eventually *removed* from the list entirely
(impact ruled out). CNEOS publishes the current list and a bare list of removed objects, but not the
*revision trajectory* - how 2000 SG344's Palermo scale drifted week by week, or when an object
appeared and retired - so the as-issued series is un-rebuildable (metno/spaceweather class) = high.

Model: one Item per object (join key = the Sentry designation `des`, e.g. `101955` or `2000 SG344`).
`price_cents` = **cumulative Palermo scale * 100** (centi-Palermo, negative), so the core's `drops`
= an object's risk revised *down* (the threat receding); an object vanishing from the list = fetch
returns None and its obs series simply ends (the retirement event). `qty` = the number of potential
impacts. Deal "risk" = an object that merits attention: Torino >= 1 or Palermo >= -2. money()
cosmetically renders centi-Palermo as (negative) dollars in the two core-hardcoded spots
(geonet/metno/volcano/chcflights precedent); the rich views show the proper scales.

`search` pulls the list at a Palermo floor (`--psmin`, default -4 = the ~40 most significant
objects; the full list is ~2200) and filters by name; `item`/`poll` use the by-designation detail
endpoint, whose summary adds observation counts, mass/energy, and the computed-date stamp. The
query is built with %20 (not `+`) for designations with spaces - the gwrivers/Hilltop lesson.
"""
from __future__ import annotations

from urllib.parse import quote, urlencode

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

FEED = "https://ssd-api.jpl.nasa.gov/sentry.api"
PS_MIN_DEFAULT = -4     # search floor: within 4 orders of magnitude of background risk
ATTENTION_PS = -2.0     # Palermo >= -2 ("merits monitoring") ...
ATTENTION_TS = 1.0      # ... or Torino >= 1 = the "risk" deal


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ip_s(ip):
    return f"{ip:.1e}" if isinstance(ip, (int, float)) else "?"


def _item_obs(row, src, detail=None):
    """One list row or detail summary -> (Item, Obs). Both share the core field names."""
    des = str(row.get("des") or "")
    if not des:
        return None
    ps_cum, ps_max = _num(row.get("ps_cum")), _num(row.get("ps_max"))
    ts_max, ip = _num(row.get("ts_max")), _num(row.get("ip"))
    n_imp = int(_num(row.get("n_imp")) or 0)
    diameter = _num(row.get("diameter"))
    fullname = safe(row.get("fullname") or "").strip() or des
    extra = {"diameter_km": diameter, "h_mag": _num(row.get("h")),
             "last_obs": row.get("last_obs") or "", "range": row.get("range") or "",
             "v_inf_kms": _num(row.get("v_inf"))}
    if detail is not None:
        s, vis = detail
        extra.update({"first_obs": s.get("first_obs") or "", "n_obs": s.get("nobs"),
                      "mass_kg": _num(s.get("mass")), "energy_mt": _num(s.get("energy")),
                      "v_imp_kms": _num(s.get("v_imp")), "computed": s.get("pdate") or "",
                      "method": s.get("method") or "", "n_vi": len(vis),
                      "nearest_imp": min((v.get("date") or "" for v in vis), default="")[:10]})
    ts_s = f"{ts_max:g}" if ts_max is not None else "?"
    item = Item(des, name=fullname,
                subtitle=f"Palermo {ps_cum if ps_cum is not None else '?'}  Torino {ts_s}",
                category=f"Torino {ts_s}", extra=extra)
    obs = Obs(price_cents=(round(ps_cum * 100) if ps_cum is not None else None), qty=n_imp,
              flags={"ps_cum": ps_cum, "ps_max": ps_max, "ts_max": ts_max, "ip": ip,
                     "n_imp": n_imp, "diameter_km": diameter,
                     "last_obs": row.get("last_obs") or "", "src": src})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._list = {}     # ps_min -> rows; one GET serves a whole search pass
        self._detail = {}   # des -> (summary, vis)

    def _get(self, params):
        url = FEED + "?" + urlencode(params, quote_via=quote)   # %20, never '+' (Hilltop lesson)
        r = self.s.get(url, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or {}

    def risk_list(self, ps_min):
        if ps_min not in self._list:
            self._list[ps_min] = self._get({"ps-min": ps_min}).get("data") or []
        return self._list[ps_min]

    def detail(self, des):
        if des not in self._detail:
            d = self._get({"des": des})
            self._detail[des] = (d.get("summary") or {}, d.get("data") or [])
        return self._detail[des]


class SentrySource(Source):
    name = "sentry"
    id_label = "DES"
    cc_default = "global"       # unused; the designation is the key
    deal_label = "risk"         # an object meriting attention (Torino >= 1 or Palermo >= -2)
    search_args = [
        ("--psmin", {"type": int, "default": PS_MIN_DEFAULT,
                     "help": f"Palermo-scale floor for the list (default {PS_MIN_DEFAULT}; the full list is ~2200 objects)"}),
    ]
    search_limit_default = 20
    search_header = f"{'PALERMO':>8}  {'TORINO':>6}  {'IMP PROB':>9}  {'KM':>7}  {'IMPACTS':<9}  NAME"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = cl.risk_list(PS_MIN_DEFAULT)
        return bool(rows), f"({len(rows)} objects at Palermo >= {PS_MIN_DEFAULT}; keyless JPL Sentry API)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        rows = []
        for r in cl.risk_list(getattr(args, "psmin", PS_MIN_DEFAULT)):
            hay = f"{r.get('des', '')} {r.get('fullname', '')}".lower()
            if t and t not in hay:
                continue
            built = _item_obs(r, "list")
            if built:
                rows.append(built)
        rows.sort(key=lambda io: -(io[1].flags.get("ps_cum") or -99))
        return rows

    def fetch(self, cl, des):
        summary, vis = cl.detail(str(des))
        if not summary.get("des"):
            return None                      # not on the risk list (never was, or retired)
        return _item_obs(summary, "detail", detail=(summary, vis))

    def is_deal(self, obs):
        ts, ps = obs.flags.get("ts_max"), obs.flags.get("ps_cum")
        return ((ts is not None and ts >= ATTENTION_TS)
                or (ps is not None and ps >= ATTENTION_PS))

    def deal_line(self, item, obs):
        f = obs.flags
        ts = f.get("ts_max")
        return (f"Palermo {f.get('ps_cum', '?')}  Torino {f'{ts:g}' if ts is not None else '?'}  "
                f"ip {_ip_s(f.get('ip'))}  {item.name}  (impacts {item.extra.get('range', '?')})")

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        ps, ts, dia = f.get("ps_cum"), f.get("ts_max"), f.get("diameter_km")
        return (f"{ps if ps is not None else '?':>8}  {f'{ts:g}' if ts is not None else '?':>6}  "
                f"{_ip_s(f.get('ip')):>9}  {f'{dia:g}' if dia is not None else '?':>7}  "
                f"{item.extra.get('range', '') or '?':<9}  {item.name}")

    def format_item(self, item, obs):
        e = item.extra
        dia = e.get("diameter_km")
        lines = [f"  object    : {item.name}  [{item.id}]",
                 f"  size      : {f'{dia:g}' if isinstance(dia, (int, float)) else '?'} km  (H {e.get('h_mag', '?')})",
                 f"  observed  : {e.get('first_obs', '?')} -> {e.get('last_obs', '?')}  ({e.get('n_obs', '?')} obs)"]
        if obs:
            f = obs.flags
            ts = f.get("ts_max")
            lines.append(f"  palermo   : {f.get('ps_cum', '?')} cum / {f.get('ps_max', '?')} max")
            lines.append(f"  torino    : {f'{ts:g}' if ts is not None else '?'}")
            lines.append(f"  imp prob  : {_ip_s(f.get('ip'))}  over {f.get('n_imp', '?')} potential impacts")
        if e.get("nearest_imp"):
            lines.append(f"  nearest   : {e.get('nearest_imp')}  ({e.get('n_vi', '?')} virtual impactors)")
        if e.get("energy_mt") is not None:
            lines.append(f"  energy    : {e.get('energy_mt'):g} Mt  v_imp {e.get('v_imp_kms', '?')} km/s")
        if e.get("computed"):
            lines.append(f"  computed  : {e.get('computed')}  ({e.get('method', '')})")
        return lines


SOURCE = SentrySource()
