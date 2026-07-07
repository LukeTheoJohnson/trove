"""usgs - live US river streamflow / gauge height via the keyless USGS Water Services API.

The U.S. Geological Survey publishes real-time national water telemetry through a keyless, official,
documented REST service (`waterservices.usgs.gov`, robots 404 = nothing fenced; USGS open data =
sanctioned -> trove). This is the **US twin of gwrivers/mdcrivers/horizonsrivers** - the same
hydrology / flood-watch mechanic, filling the thin US geography (roadmap Axis C).

Like the NZ Hilltop gauges, the tracked value is genuinely ephemeral *state* - a river's discharge
and stage at 5-15 minute telemetry, changing with rain/snowmelt. The flood-relevant event is a
**rise**, but trove's core only flags price *drops*, so the 24h trend is computed at fetch time and
stored as `rising` (`is_deal` "rising" = latest >= 1.5x its value 24h ago = a flood-onset signal),
while the core's `drops` = a river *receding*. Honest hoard value is low-med: USGS archives the full
record (rebuildable, the octopus/frankfurter class), so the draw is genre/geography completion + the
live flood flex, not un-rebuildability.

The Instantaneous Values service returns JSON: `/nwis/iv/?stateCd=<st>&parameterCd=00060,00065` gives
every active gauge in a state (00060 = Streamflow ft3/s, 00065 = Gage height ft), each `timeSeries`
carrying `sourceInfo` (siteName + siteCode) and a `values[].value` list of `{value, qualifiers,
dateTime}`. USGS's no-data sentinel is **-999999** (excluded). `search` (by `--cc` = a US state code,
default co) lists a state's gauges from one memoized GET (latest value); `item`/`poll` fetch one site
by code with `period=P1D` for the 24h series + rising flag. Join key = the USGS site number (globally
unique, no state prefix needed). `price_cents` = latest value * 100 (centi-ft3/s for flow, or ft*100
for stage); the measurement + unit ride in flags so the denomination stays interpretable.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

BASE = "https://waterservices.usgs.gov/nwis/iv/"
RISE_RATIO = 1.5          # latest >= 1.5x the value 24h ago = "rising" (flood-onset)
NODATA = -999998          # USGS uses -999999 as the no-data sentinel
VAR = {"00060": ("Streamflow", "ft3/s"), "00065": ("Gage height", "ft")}
HEADLINE = ("00060", "00065")     # prefer flow, fall back to stage


def _points(ts):
    """A USGS timeSeries -> [(dateTime, value)] ascending, no-data sentinels dropped."""
    out = []
    for vblock in ts.get("values") or []:
        for p in vblock.get("value") or []:
            try:
                v = float(p.get("value"))
            except (TypeError, ValueError):
                continue
            if v <= NODATA:
                continue
            out.append((p.get("dateTime"), v))
    return out


def _code(ts):
    si = ts.get("sourceInfo") or {}
    sc = si.get("siteCode") or [{}]
    return (sc[0].get("value") if sc else None), safe(si.get("siteName") or "")


def _param(ts):
    v = ts.get("variable") or {}
    vc = v.get("variableCode") or [{}]
    return vc[0].get("value") if vc else None


def _build(code, name, per):
    """per = {param_code: [(t, v)...]}. Headline = Flow else Stage -> (Item, Obs) or None."""
    m = next((p for p in HEADLINE if per.get(p)), None)
    if not m:
        return None
    pts = per[m]
    label, unit = VAR[m]
    t_now, v_now = pts[-1]
    v_first = pts[0][1]
    vals = [v for _, v in pts]
    change = round(v_now - v_first, 3)
    pct = round((v_now / v_first - 1) * 100, 1) if v_first else None
    rising = bool(v_first > 0 and v_now >= RISE_RATIO * v_first)
    other = next((p for p in HEADLINE if p != m and per.get(p)), None)
    other_v = round(per[other][-1][1], 3) if other else None
    item = Item(str(code), name=name or str(code),
                subtitle=f"{label} {round(v_now, 2)} {unit}  ({'rising' if rising else 'steady/falling'})",
                category=label,
                extra={"measurement": label, "unit": unit, "site": str(code),
                       "url": f"https://waterdata.usgs.gov/monitoring-location/{code}/"})
    obs = Obs(price_cents=round(v_now * 100),
              qty=None,
              flags={"measurement": label, "unit": unit, "value": round(v_now, 3),
                     "value_24h_ago": round(v_first, 3), "max_24h": round(max(vals), 3),
                     "min_24h": round(min(vals), 3), "change_24h": change, "pct_change_24h": pct,
                     "rising": rising, "latest_time": t_now,
                     "other": (VAR[other][0] if other else None), "other_value": other_v})
    return item, obs


def _group(series):
    """List of timeSeries -> {code: (name, {param: points})}, points ascending."""
    by = {}
    for ts in series:
        code, name = _code(ts)
        param = _param(ts)
        if not code or param not in VAR:
            continue
        pts = _points(ts)
        if not pts:
            continue
        slot = by.setdefault(code, [name, {}])
        slot[0] = slot[0] or name
        slot[1][param] = pts
    return by


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._state = {}     # state code -> grouped feed

    def _iv(self, params):
        params = {"format": "json", "parameterCd": "00060,00065", "siteStatus": "active", **params}
        r = self.s.get(BASE, params=params, headers={"User-Agent": UA, "Accept": "application/json"},
                       timeout=60)
        r.raise_for_status()
        return ((r.json() or {}).get("value") or {}).get("timeSeries") or []

    def state(self, st):
        st = (st or "co").lower()
        if st not in self._state:
            self._state[st] = _group(self._iv({"stateCd": st}))
        return self._state[st]

    def site(self, code):
        """One site with a 24h window (period=P1D) for the rising flag."""
        return _group(self._iv({"sites": str(code), "period": "P1D"}))


class UsgsSource(Source):
    name = "usgs"
    id_label = "SITE"
    cc_default = "co"           # a US state code; picks which state's gauges search lists
    deal_label = "rising"       # latest flow/level >= 1.5x its value 24h ago (flood-onset)
    search_limit_default = 25
    search_header = f"{'VALUE':>14}  {'MEAS':<10}  SITE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        by = cl.state(self.cc_default)
        return bool(by), f"({len(by)} active gauges in {self.cc_default.upper()}; keyless USGS Water Services IV)"

    def search(self, cl, term, args):
        st = (getattr(args, "cc", None) or self.cc_default)
        t = (term or "").strip().lower()
        rows = []
        for code, (name, per) in cl.state(st).items():
            built = _build(code, name, per)
            if not built:
                continue
            item, obs = built
            if not t or t in item.name.lower() or t == str(code):
                rows.append((item, obs))
        rows.sort(key=lambda r: -(r[1].flags.get("value") or 0))
        return rows

    def fetch(self, cl, item_id):
        by = cl.site(str(item_id))
        slot = by.get(str(item_id))
        if not slot:
            return None
        return _build(str(item_id), slot[0], slot[1])

    def is_deal(self, obs):
        return bool(obs.flags.get("rising"))

    def deal_line(self, item, obs):
        f = obs.flags
        return (f"{item.name}  {f.get('measurement')} {f.get('value')} {f.get('unit')}  "
                f"up {f.get('pct_change_24h')}% in 24h  (24h max {f.get('max_24h')})")

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        val = f"{f.get('value', '?')} {f.get('unit', '')}"
        return f"{val:>14}  {(f.get('measurement') or '')[:10]:<10}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = []
        if obs:
            f = obs.flags
            lines.append(f"  measurement : {f.get('measurement')}  ({f.get('unit')})")
            lines.append(f"  latest      : {f.get('value')} {f.get('unit')}   at {f.get('latest_time')}")
            lines.append(f"  24h ago     : {f.get('value_24h_ago')} {f.get('unit')}")
            lines.append(f"  24h change  : {f.get('change_24h')} {f.get('unit')}  ({f.get('pct_change_24h')}%)")
            lines.append(f"  24h max/min : {f.get('max_24h')} / {f.get('min_24h')} {f.get('unit')}")
            if f.get("other"):
                lines.append(f"  also        : {f.get('other')} {f.get('other_value')}")
            lines.append(f"  rising      : {f.get('rising')}  (>= {RISE_RATIO}x 24h-ago = flood-onset)")
        lines.append(f"  site        : USGS {e.get('site')}  ({e.get('url', '')})")
        return lines


SOURCE = UsgsSource()
