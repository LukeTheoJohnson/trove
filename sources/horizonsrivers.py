"""horizonsrivers - live Manawatu-Whanganui river flow/level via Horizons' keyless Hilltop server.

Horizons Regional Council (Manawatu-Whanganui) publishes its real-time hydrology telemetry through a
public Hilltop server (hilltopserver.horizons.govt.nz/data.hts) - the same open-data backend as
`gwrivers` (Wellington) and `mdcrivers` (Marlborough), but a different region: the flood-prone
Manawatu, Whanganui, Rangitikei and their tributaries. No key, no robots.txt (the host returns its
site HTML, nothing fenced), official council open data = sanctioned -> trove.

The data is ephemeral *state*: a river's flow and stage at telemetry cadence, changing with rain and
never archived in a convenient unified per-gauge series. As with the sibling sources the
flood-relevant event is a **rise**, but trove's core only flags price *drops*, so this source computes
the 24h trend at fetch and stores `rising`: `is_deal` ("rising") = latest value >= 1.5x its value 24h
ago (a flood-onset signal), while the core's `drops` = a river *receding*.

Hilltop is XML: `Request=SiteList` lists the gauge sites (join key = site name); `Request=GetData&
Site=<name>&Measurement=Flow&TimeInterval=PT24H/Now` returns the recent `<E><T/><I1/></E>` series.
`fetch` reads Flow (m3/s) where available, else Stage (mm); `price_cents` = latest value * 100. Spaces
are %20-encoded (Hilltop does not decode '+'). `search <term>` fetches live flow for matching gauges;
`--cc` is unused.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

HOST = "https://hilltopserver.horizons.govt.nz/data.hts"
RISE_RATIO = 1.5


def _unit(u):
    u = safe(u)
    return "m3/s" if "/sec" in u or "m\xb3" in (u or "") else u


def _series(root):
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
    u = next(root.iter("Units"), None)
    return u.text if u is not None else ""


def _report(site, measurement, unit, pts):
    t_now, v_now = pts[-1]
    v_first = pts[0][1]
    vals = [v for _, v in pts]
    vmax, vmin = max(vals), min(vals)
    change = round(v_now - v_first, 3)
    pct = round((v_now / v_first - 1) * 100, 1) if v_first else None
    rising = bool(v_first > 0 and v_now >= RISE_RATIO * v_first)
    item = Item(site, name=safe(site),
                subtitle=f"{measurement} {round(v_now, 2)} {unit}  ({'rising' if rising else 'steady/falling'})",
                category=measurement,
                extra={"measurement": measurement, "unit": unit, "url": HOST})
    obs = Obs(price_cents=round(v_now * 100),
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
        for m in ("Flow", "Stage"):
            try:
                pts, unit = self.data(site, m)
            except Exception:
                pts, unit = [], ""
            if pts:
                return _report(site, m, _unit(unit) or ("m3/s" if m == "Flow" else "mm"), pts)
        return None


class HorizonsRiversSource(Source):
    name = "horizonsrivers"
    id_label = "SITE"
    cc_default = "nz"            # unused
    deal_label = "rising"       # rising = latest flow/level >= 1.5x its value 24h ago
    search_limit_default = 6
    search_header = f"{'VALUE':>12}  {'24H':>7}  SITE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        sites = cl.sites()
        return bool(sites), f"({len(sites)} Horizons hydrology gauge sites; keyless Hilltop SiteList)"

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
                time.sleep(0.3)
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
        lines.append(f"  source      : Horizons Regional Council Hilltop  ({e.get('url', '')})")
        return lines


SOURCE = HorizonsRiversSource()
