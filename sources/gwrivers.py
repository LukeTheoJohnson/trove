"""gwrivers - live Greater Wellington river flow/level via the council's keyless Hilltop server.

Greater Wellington Regional Council publishes its real-time hydrology telemetry through a public
Hilltop server (hilltop.gw.govt.nz/Data.hts) - the same open-data backend LAWA aggregates. No key, no
robots.txt (404 = nothing fenced), official council open data = sanctioned -> trove. This is a new
genre for trove: hydrology / flood watch.

The data is genuinely ephemeral *state*: a river's flow and stage (level) at 5-minute telemetry,
changing constantly with rain and never archived in a convenient unified per-gauge series you can
rebuild cheaply. The flood-relevant event is a **rise**, but trove's core only flags price *drops*, so
this source computes the 24h trend at fetch time and stores `rising` as a flag: `is_deal` ("rising") =
the latest value is >= 1.5x its value 24h ago (a real flood-onset signal), while the core's `drops` =
a river *receding* since the last poll.

Hilltop is XML: `Request=SiteList` lists ~3300 gauge sites (the join key is the site name);
`Request=GetData&Site=<name>&Measurement=Flow&TimeInterval=PT24H/Now` returns the recent series as
`<E><T>time</T><I1>value</I1></E>` points. `fetch` reads Flow (m3/s) where available, else Stage (mm),
takes the latest point as the headline and derives max/min/24h-change/rising from the same response.
`price_cents` = latest value * 100 (centi-cumecs for flow, or mm*100 for stage); the measurement+unit
ride in `flags` so the denomination is interpretable (it is consistent per site over time). `search
<term>` fetches live flow for gauges whose name matches; `item`/`poll` fetch one by site name. `--cc`
is unused.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source

UA = "trove/0.1 (+github.com/LukeTheoJohnson/trove)"
HOST = "https://hilltop.gw.govt.nz/Data.hts"
RISE_RATIO = 1.5    # latest >= 1.5x the value 24h ago = "rising" (flood-onset signal)


def _safe(s):
    return (str(s) if s is not None else "").strip().encode("cp1252", "replace").decode("cp1252")


def _unit(u):
    """'m3/sec' (with a cubed glyph) -> ASCII 'm3/s'; pass mm etc through."""
    u = _safe(u)
    return "m3/s" if "/sec" in u or "m\xb3" in (u or "") else u


def _series(root):
    """Hilltop GetData XML -> [(time_str, float_value)] from <E><T/><I1/></E> points."""
    out = []
    for e in root.iter("E"):
        t = e.find("T")
        v = e.find("I1")
        if t is not None and v is not None and (v.text or "").strip():
            try:
                out.append((t.text, float(v.text)))
            except ValueError:
                pass
    return out


def _measure(root):
    """Units text from the GetData response, if present."""
    u = next(root.iter("Units"), None)
    return u.text if u is not None else ""


def _report(site, measurement, unit, pts):
    """A site's recent series for one measurement -> (Item, Obs). pts = [(t, value)] ascending."""
    t_now, v_now = pts[-1]
    v_first = pts[0][1]
    vals = [v for _, v in pts]
    vmax, vmin = max(vals), min(vals)
    change = round(v_now - v_first, 3)
    pct = round((v_now / v_first - 1) * 100, 1) if v_first else None
    rising = bool(v_first > 0 and v_now >= RISE_RATIO * v_first)
    item = Item(site, name=_safe(site),
                subtitle=f"{measurement} {round(v_now, 2)} {unit}  ({'rising' if rising else 'steady/falling'})",
                category=measurement,
                extra={"measurement": measurement, "unit": unit, "url": HOST})
    obs = Obs(price_cents=round(v_now * 100),
              qty=None,
              flags={"measurement": measurement, "unit": unit, "value": round(v_now, 3),
                     "value_24h_ago": round(v_first, 3), "max_24h": round(vmax, 3),
                     "min_24h": round(vmin, 3), "change_24h": change, "pct_change_24h": pct,
                     "rising": rising, "latest_time": t_now})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._sites = None

    def _xml(self, params):
        # Hilltop wants %20 for spaces (it does not decode '+'); build the query with quote.
        url = f"{HOST}?{urlencode(params, quote_via=quote)}"
        r = self.s.get(url, headers={"User-Agent": UA}, timeout=45)
        r.raise_for_status()
        return ET.fromstring(r.content)

    def sites(self):
        if self._sites is None:
            root = self._xml({"Service": "Hilltop", "Request": "SiteList"})
            self._sites = [s.get("Name") for s in root.iter("Site") if s.get("Name")]
        return self._sites

    def data(self, site, measurement):
        root = self._xml({"Service": "Hilltop", "Request": "GetData", "Site": site,
                          "Measurement": measurement, "TimeInterval": "PT24H/Now"})
        return _series(root), _measure(root)

    def report(self, site):
        """Latest Flow where available, else Stage -> (Item, Obs) or None."""
        for m in ("Flow", "Stage"):
            try:
                pts, unit = self.data(site, m)
            except Exception:
                pts, unit = [], ""
            if pts:
                return _report(site, m, _unit(unit) or ("m3/s" if m == "Flow" else "mm"), pts)
        return None


class GWRiversSource(Source):
    name = "gwrivers"
    id_label = "SITE"
    cc_default = "nz"            # unused
    deal_label = "rising"       # rising = latest flow/level >= 1.5x its value 24h ago
    search_limit_default = 6     # search fetches live for matches; keep the fan-out polite
    search_header = f"{'VALUE':>12}  {'24H':>7}  SITE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        sites = cl.sites()
        return bool(sites), f"({len(sites)} GW hydrology gauge sites; keyless Hilltop SiteList)"

    def search(self, cl, term, args):
        t = (term or "").strip().lower()
        matches = [s for s in cl.sites() if t in s.lower()] if t else []
        rows = []
        for i, site in enumerate(matches[: args.limit]):
            try:
                r = cl.report(site)
            except Exception:
                r = None
            if r:
                rows.append(r)
            if i + 1 < min(len(matches), args.limit):
                time.sleep(0.3)             # polite: one gauge at a time
        return rows

    def fetch(self, cl, item_id):
        return cl.report(str(item_id))

    def is_deal(self, obs):
        return bool(obs.flags.get("rising"))

    def deal_line(self, item, obs):
        f = obs.flags
        pct = f.get("pct_change_24h")
        return (f"{item.name}  {f.get('measurement')} {f.get('value')} {f.get('unit')}  "
                f"up {pct}% in 24h  (24h max {f.get('max_24h')})")

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        val = f"{f.get('value', '?')}{f.get('unit', '')}"
        pct = f.get("pct_change_24h")
        arrow = "up" if (pct is not None and pct > 0) else ("dn" if (pct is not None and pct < 0) else "--")
        return f"{val:>12}  {(arrow + str(abs(pct)) + '%' if pct is not None else '?'):>7}  {item.name}"

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
            lines.append(f"  rising      : {f.get('rising')}  (>= {RISE_RATIO}x 24h-ago = flood-onset)")
        lines.append(f"  source      : Greater Wellington Hilltop  ({e.get('url', '')})")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = GWRiversSource()
