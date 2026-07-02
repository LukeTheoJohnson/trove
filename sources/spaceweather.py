"""spaceweather - NOAA SWPC planetary K-index (Kp) forecast: the aurora-australis drift hoard.

Space weather - geomagnetic storms driven by the Sun - is what lights the aurora. NOAA's Space
Weather Prediction Center publishes a keyless, official 3-day planetary K-index forecast (Kp 0-9;
Kp>=5 is a geomagnetic storm, the threshold where aurora australis becomes visible from southern
NZ). The ephemeral thing this source hoards is the **forecast as issued**: SWPC keeps the realized
Kp archive, but not a convenient record of *what each day's storm was predicted to be, and how that
prediction drifted* as the day approached - un-rebuildable, like the metno forecast-drift source.
`services.swpc.noaa.gov` serves keyless product JSON with no robots.txt (404 = unfenced) = sanctioned
-> trove. New domain for trove (space weather), NZ-relevant for aurora watchers.

Model: one Item per **UTC forecast date** (join key = `YYYY-MM-DD`), aggregated from the 3-hourly
`planetary-k-index-forecast.json`. `price_cents` = the day's **peak forecast Kp * 100** (centi-Kp,
so 0-900); the core's `drops` = a day's peak-Kp forecast revised *down* (storm calming). `qty` = the
count of 3-hour periods that day at storm level (Kp>=5). Deal "aurora" = peak Kp >= 5 (a storm day;
aurora australis likely for southern NZ). Re-polling re-logs each date, so the obs log is the
un-rebuildable as-issued forecast series. money() cosmetically renders centi-Kp as dollars in the two
core-hardcoded spots (geonet/metno/volcano precedent); the rich views show `Kp`.

`search` lists every date in the current forecast window (a fixed set, like nzski - pass "" for all,
or a date substring to filter); `item`/`poll` fetch one date (the feed is memoized, so a multi-date
poll is a single GET). Times are UTC (SWPC's tz), so a "date" is a UTC calendar day.
"""
from __future__ import annotations

from collections import defaultdict

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source

FEED = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
STORM_KP = 5.0


def _aggregate(rows):
    """[{time_tag,kp,observed,noaa_scale}] -> {UTC date: aggregate dict} (peak Kp etc.)."""
    by = defaultdict(list)
    for r in rows:
        date = (r.get("time_tag") or "")[:10]
        if date and r.get("kp") is not None:
            by[date].append(r)
    out = {}
    for date, rs in by.items():
        kps = [float(r["kp"]) for r in rs]
        peak_row = max(rs, key=lambda r: float(r["kp"]))
        states = {r.get("observed") for r in rs}
        status = ("observed" if states == {"observed"}
                  else "predicted" if states == {"predicted"} else "mixed")
        out[date] = {"peak_kp": max(kps), "peak_time": (peak_row.get("time_tag") or "")[11:16],
                     "storm_periods": sum(1 for k in kps if k >= STORM_KP), "n_periods": len(kps),
                     "status": status, "scale": peak_row.get("noaa_scale") or ""}
    return out


def _item_obs(date, a):
    peak = a["peak_kp"]
    storm = peak >= STORM_KP
    item = Item(date, name=f"Kp forecast {date}", subtitle=f"peak Kp {peak:g}",
                category=a["status"],
                extra={"peak_time_utc": a["peak_time"], "scale": a["scale"], "n_periods": a["n_periods"]})
    obs = Obs(price_cents=round(peak * 100), qty=a["storm_periods"],
              flags={"peak_kp": peak, "peak_time_utc": a["peak_time"], "status": a["status"],
                     "storm_periods": a["storm_periods"], "scale": a["scale"], "aurora": storm})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._agg = None            # one GET serves a whole search/poll pass

    def agg(self):
        if self._agg is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._agg = _aggregate(r.json() or [])
        return self._agg


class SpaceWeatherSource(Source):
    name = "spaceweather"
    id_label = "DATE"
    deal_label = "aurora"          # deal = a storm day (peak Kp >= 5)
    search_limit_default = 20
    search_header = f"{'PEAK Kp':>8}  {'STORMS':>6}  {'STATUS':<9}  PEAK@UTC / SCALE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        a = cl.agg()
        return bool(a), f"({len(a)} forecast dates; keyless SWPC planetary-k-index-forecast)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        rows = []
        for date, a in sorted(cl.agg().items()):
            if t and t not in date.lower():
                continue
            rows.append(_item_obs(date, a))
        return rows

    def fetch(self, cl, date):
        a = cl.agg().get(str(date))
        return _item_obs(str(date), a) if a else None

    def is_deal(self, obs):
        return bool(obs.flags.get("aurora"))

    def deal_line(self, item, obs):
        f = obs.flags
        kp = f.get("peak_kp")
        kp_s = f"{kp:g}" if isinstance(kp, (int, float)) else "?"
        return f"Kp {kp_s} storm ({f.get('storm_periods')}x3h)  {item.id}  peak {f.get('peak_time_utc')} UTC"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        kp = f.get("peak_kp")
        kp_s = f"{kp:.2f}" if isinstance(kp, (int, float)) else "?"
        tail = f.get("peak_time_utc", "") + (f"  {f.get('scale')}" if f.get("scale") else "")
        return f"{kp_s:>8}  {f.get('storm_periods', 0):>6}  {f.get('status', ''):<9}  {tail}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  date (UTC): {item.id}", f"  status    : {item.category}"]
        if obs:
            f = obs.flags
            kp = f.get("peak_kp")
            kp_s = f"{kp:g}" if isinstance(kp, (int, float)) else "?"
            lines.append(f"  peak Kp   : {kp_s}  at {f.get('peak_time_utc', '?')} UTC"
                         + (f"  ({f.get('scale')})" if f.get("scale") else ""))
            lines.append(f"  storm 3h  : {f.get('storm_periods', 0)} of {e.get('n_periods', '?')} periods >= Kp5")
            lines.append(f"  aurora    : {'likely (storm)' if f.get('aurora') else 'unlikely'}")
        return lines


SOURCE = SpaceWeatherSource()
