"""melbped - City of Melbourne live pedestrian foot-traffic via the council's Opendatasoft API.

The City of Melbourne runs a network of automated pedestrian counters and publishes the readings as
keyless open data on its Opendatasoft portal (data.melbourne.vic.gov.au). The
`pedestrian-counting-system-past-hour-counts-per-minute` dataset carries each sensor's per-minute
count for the last hour, and `pedestrian-counting-system-sensor-locations` gives the sensor names +
coordinates. robots.txt fences only account paths (/login, /publish), never the /api/explore data
API = sanctioned -> trove. An `attention & rank` source, AU-side: the tracked scalar is *where the
crowd is on the street right now*, not a price.

The timeline value is ephemeral: a sensor's footfall this minute (Bourke St Mall, Flinders St
Station...) rising and falling through the day, never archived as a convenient per-sensor live series.
`price_cents` = the latest per-minute count * 100 (centi-count, so the core's `drops` = a spot
*quietening*); `qty` = the raw count; a "deal" ("busy") = the sensor is at or above the median of the
current network snapshot (one of the busier spots right now). money() cosmetically renders the
centi-count as dollars in the two core-hardcoded spots (a count of 40 prints as "$40.00"; geonet
precedent); the rich views show "40/min".

Model: one Item per sensor (join key = ODS `location_id`). `search <term>` filters sensors by
description substring (pass "" to list them all); `item`/`poll` read one sensor by id. The client
pulls the sensor list + the freshest reading per sensor in two memoized GETs. `--cc` is unused.
"""
from __future__ import annotations

from statistics import median

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

BASE = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets"
LOCATIONS = "pedestrian-counting-system-sensor-locations"
READINGS = "pedestrian-counting-system-past-hour-counts-per-minute"


def _build(loc, reading, snapshot_median):
    lid = str(loc.get("location_id") if loc else reading.get("location_id"))
    total = reading.get("total_of_directions") if reading else None
    name = safe((loc or {}).get("sensor_description") or lid)
    item = Item(lid, name=name, subtitle="Melbourne pedestrian sensor", category="foot traffic",
                extra={"location_id": lid, "sensor": safe((loc or {}).get("sensor_name") or ""),
                       "lat": (loc or {}).get("latitude"), "lon": (loc or {}).get("longitude"),
                       "type": (loc or {}).get("location_type"), "status": (loc or {}).get("status"),
                       "dir1_label": (loc or {}).get("direction_1"),
                       "dir2_label": (loc or {}).get("direction_2")})
    obs = None
    if reading is not None:
        obs = Obs(price_cents=(total * 100 if isinstance(total, int) else None),
                  qty=(total if isinstance(total, int) else None),
                  flags={"count": total, "dir1": reading.get("direction_1"),
                         "dir2": reading.get("direction_2"), "at": reading.get("sensing_datetime"),
                         "snapshot_median": snapshot_median})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._locs = None
        self._latest = None

    def _records(self, dataset, **params):
        params.setdefault("limit", 100)
        r = self.s.get(f"{BASE}/{dataset}/records", params=params,
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return (r.json() or {}).get("results") or []

    def locations(self):
        if self._locs is None:
            self._locs = {str(l.get("location_id")): l for l in self._records(LOCATIONS, limit=100)}
        return self._locs

    def latest(self):
        """location_id -> freshest per-minute reading (dedupe the time-desc feed)."""
        if self._latest is None:
            out = {}
            for rec in self._records(READINGS, order_by="sensing_datetime desc", limit=100):
                lid = str(rec.get("location_id"))
                if lid not in out:
                    out[lid] = rec
            self._latest = out
        return self._latest

    def snapshot_median(self):
        vals = [r.get("total_of_directions") for r in self.latest().values()
                if isinstance(r.get("total_of_directions"), int)]
        return round(median(vals)) if vals else None


class MelbPedSource(Source):
    name = "melbped"
    id_label = "SENSOR"
    cc_default = "au"        # unused; one Melbourne network
    deal_label = "busy"      # at/above the current network median footfall
    search_limit_default = 25
    search_header = f"{'COUNT/min':>9}  SENSOR"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        latest = cl.latest()
        return bool(latest), f"({len(latest)} sensors reporting this hour; keyless Melbourne ODS)"

    def search(self, cl, term, args):
        locs, latest, med = cl.locations(), cl.latest(), cl.snapshot_median()
        t = (term or "").lower()
        out = []
        for lid, rec in latest.items():
            loc = locs.get(lid)
            name = safe((loc or {}).get("sensor_description") or lid).lower()
            if not t or t in name:
                out.append(_build(loc, rec, med))
        out.sort(key=lambda io: -(io[1].qty or 0) if io[1] else 0)   # busiest first
        return out

    def fetch(self, cl, item_id):
        locs, latest, med = cl.locations(), cl.latest(), cl.snapshot_median()
        lid = str(item_id)
        rec = latest.get(lid)
        loc = locs.get(lid)
        if rec is None and loc is None:
            return None
        return _build(loc, rec, med)

    def is_deal(self, obs):
        c, med = obs.flags.get("count"), obs.flags.get("snapshot_median")
        return isinstance(c, int) and med is not None and c >= med

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('count', '?')}/min  {item.name}  (network median {f.get('snapshot_median', '?')}/min, at {f.get('at', '')})"

    def search_row(self, item, obs):
        c = obs.qty if obs else None
        return f"{(str(c) + '/min') if c is not None else '?':>9}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  sensor   : {item.name}  ({e.get('sensor', '')})",
                 f"  location : {e.get('lat', '?')}, {e.get('lon', '?')}  ({e.get('type', '')})"]
        if obs:
            f = obs.flags
            lines.append(f"  footfall : {f.get('count', '?')} /min  (as at {f.get('at', '')})")
            lines.append(f"  by dir   : {e.get('dir1_label', 'dir1')} {f.get('dir1', '?')}, {e.get('dir2_label', 'dir2')} {f.get('dir2', '?')}")
            med = f.get("snapshot_median")
            if med is not None:
                lines.append(f"  network  : median {med}/min this snapshot")
        return lines


SOURCE = MelbPedSource()
