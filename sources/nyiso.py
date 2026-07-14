"""nyiso - New York ISO real-time zonal electricity price (LBMP), keyless CSV.

The New York Independent System Operator publishes its real-time market data as keyless public CSV
files under `mis.nyiso.com/public/csv/` (the data host serves no robots.txt = 404 = unfenced; the
files exist for public reuse = sanctioned -> trove). The real-time zonal file
`realtime/YYYYMMDDrealtime_zone.csv` accumulates the day's 5-minute Locational-Based Marginal Price
($/MWHr) for each NY load zone (WEST, GENESE, CENTRL, N.Y.C., LONGIL, ...) plus the proxy interfaces
(PJM, H Q, NPX, O H). The US wholesale-electricity twin of `em6` (NZ) / `aemo` (AU), extending the
deepest genre into the US.

The tracked scalar is the *ephemeral dispatch price*: the LBMP resets every 5-minute interval and,
while NYISO archives settled prices, the live per-zone snapshot is the cheap-to-capture record this
hoards (honest hoard value low-med - the realized series is rebuildable from NYISO's own archive, the
octopus/awattar class; it earns its place by completing US electricity). `price_cents` = LBMP ($/MWHr)
* 100 so the core's `drops` = the price *falling* (NY zonal prices can spike hard in summer);
`qty` = None. A "deal" = the zone is at or below the average across all zones this interval (a cheaper
place to draw power right now); the loss + congestion components ride in flags.

Model: one Item per zone (join key = the zone Name). One GET returns the whole day; the latest
interval per zone is the current price. `--cc` is unused - the NY market is one set of zones.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "http://mis.nyiso.com/public/csv/realtime"
C_TS, C_ZONE, C_PTID = "Time Stamp", "Name", "PTID"
C_LBMP = "LBMP ($/MWHr)"
C_LOSS = "Marginal Cost Losses ($/MWHr)"
C_CONG = "Marginal Cost Congestion ($/MWHr)"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _latest_by_zone(rows):
    """CSV rows -> {zone: the row with the newest Time Stamp} (the current 5-min interval)."""
    out = {}
    for r in rows:
        z = (r.get(C_ZONE) or "").strip()
        if not z:
            continue
        prev = out.get(z)
        if prev is None or (r.get(C_TS) or "") > (prev.get(C_TS) or ""):
            out[z] = r
    return out


def _avg_cents(zone_rows):
    vals = [round(p * 100) for p in (_f(r.get(C_LBMP)) for r in zone_rows.values()) if p is not None]
    return round(sum(vals) / len(vals)) if vals else None


def _build(r, avg):
    z = (r.get(C_ZONE) or "").strip()
    lbmp = _f(r.get(C_LBMP))
    item = Item(z, name=z, subtitle="NYISO real-time zonal LBMP ($/MWHr)", category="zone",
                extra={"zone": z, "ptid": (r.get(C_PTID) or "").strip()})
    obs = Obs(price_cents=(round(lbmp * 100) if lbmp is not None else None),
              qty=None,
              flags={"unit": "$/MWHr", "lbmp": lbmp, "losses": _f(r.get(C_LOSS)),
                     "congestion": _f(r.get(C_CONG)), "timestamp": (r.get(C_TS) or "").strip(),
                     "ny_avg": avg})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._zones = None

    def _fetch_day(self, d):
        url = f"{BASE}/{d.strftime('%Y%m%d')}realtime_zone.csv"
        r = self.s.get(url, headers={"User-Agent": UA}, timeout=40)
        if r.status_code != 200 or not r.text.strip():
            return {}
        return _latest_by_zone(csv.DictReader(io.StringIO(r.text)))

    def zones(self):
        if self._zones is None:
            # the file is named by US-Eastern date (~UTC-4/5); try today then yesterday.
            eastern = datetime.now(timezone.utc) - timedelta(hours=4)
            self._zones = self._fetch_day(eastern) or self._fetch_day(eastern - timedelta(days=1))
        return self._zones


class NyisoSource(Source):
    name = "nyiso"
    id_label = "ZONE"
    cc_default = "ny"        # unused; the NY market is one set of zones
    deal_label = "deal"      # at/below the all-zone average this interval
    search_header = f"{'$/MWHr':>8}  ZONE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        z = cl.zones()
        return bool(z), f"({len(z)} zones priced now; keyless NYISO realtime_zone CSV)"

    def search(self, cl, term, args):
        zones = cl.zones()
        avg = _avg_cents(zones)
        t = (term or "").lower()
        out = [_build(r, avg) for z, r in zones.items() if not t or t in z.lower()]
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out

    def fetch(self, cl, item_id):
        zones = cl.zones()
        avg = _avg_cents(zones)
        r = zones.get(str(item_id))
        return _build(r, avg) if r else None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("ny_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        avg = obs.flags.get("ny_avg")
        gap = (f"  ({(obs.price_cents - avg) / 100:+.2f} vs NY avg)"
               if avg is not None and obs.price_cents is not None else "")
        return f"{money(obs.price_cents)}/MWHr{gap}  {item.name}"

    def search_row(self, item, obs):
        pc = obs.price_cents if obs else None
        return f"{(money(pc)):>8}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  zone     : {item.name}  (PTID {item.extra.get('ptid', '?')})"]
        if obs:
            f = obs.flags
            lines.append(f"  LBMP     : {money(obs.price_cents)} / MWHr")
            lines.append(f"  losses   : {f.get('losses', '?')}   congestion {f.get('congestion', '?')}")
            avg = f.get("ny_avg")
            if avg is not None and obs.price_cents is not None:
                lines.append(f"  NY avg   : {money(avg)} / MWHr   (this zone {(obs.price_cents - avg) / 100:+.2f})")
            lines.append(f"  interval : {f.get('timestamp', '?')}")
        return lines


SOURCE = NyisoSource()
