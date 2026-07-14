"""bikeshare - live dock-based bike-share station availability via the open GBFS standard.

GBFS (General Bikeshare Feed Specification, governed by NABSA) is the open data standard operators
publish so trip planners - Google Maps, Apple Maps, Transit, Citymapper - can show live station
availability. Each system exposes a keyless discovery document (`gbfs.json`) that points at
`station_information.json` (static: name/lat/lon/capacity) and `station_status.json` (live:
bikes/docks free right now). The feed hosts carry no robots.txt (403 = no such object = unfenced),
and the whole point of GBFS is public reuse = sanctioned -> trove. Opened the **shared mobility**
genre.

The timeline value is pure ephemeral *state*: a station's bikes-available count oscillating as riders
take and return bikes through the day. That per-station fill/empty cycle - the morning commuter
station draining to zero, the evening one filling up - is never archived per-station anywhere, so the
snapshot is the only record. Same scarcity shape as eventcinemas (seats) and bookme (spaces): no
price in the feed, the tracked scalar is availability.

Model: one Item per station, join key = composite `system:station_id` (a station id is unique only
within its system, and the prefix lets fetch/poll rebuild the right feed - appcharts' pattern; split
on the first ':' since ids can be UUIDs). `price_cents` = **bikes available * 100** (centi-bike, so
the core's `drops` = a station that has *drained* below where it was first seen - a demand/outflow
signal); `qty` = docks free (the returner's view). Deal "stockout risk" = a renting station running
dry (<=2 bikes left) - grab one now / a rebalancing candidate. money() cosmetically renders
centi-bike as dollars in the two core-hardcoded spots (5 bikes -> "$5.00"; geonet/appcharts
precedent); the rich views show "5 bikes / 8 docks".

`--cc` picks the system (default citibike; also baywheels / capitalbikeshare / divvy / bixi). `search`
filters stations by name substring within the `--cc` system; `item`/`poll` read the system from the
id itself, so a mixed-system watchlist stays coherent. The client resolves each system's official
discovery document (resilient to host/path drift) and memoizes both feeds, so a whole poll of any
number of watched stations costs at most three GETs per system.
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

# system slug -> the operator's official GBFS discovery document (auto-discovers the feed URLs).
SYSTEMS = {
    "citibike":        "https://gbfs.citibikenyc.com/gbfs/gbfs.json",       # New York City
    "baywheels":       "https://gbfs.baywheels.com/gbfs/gbfs.json",         # San Francisco Bay Area
    "capitalbikeshare": "https://gbfs.capitalbikeshare.com/gbfs/gbfs.json",  # Washington DC
    "divvy":           "https://gbfs.divvybikes.com/gbfs/gbfs.json",        # Chicago
    "bixi":            "https://gbfs.velobixi.com/gbfs/gbfs.json",          # Montreal (CA)
}
BIKES_LOW = 2   # <= this many bikes at a renting station = "running dry" (stockout risk)


def _feed_urls(discovery):
    """From a GBFS discovery doc, the station_information + station_status URLs (prefer English)."""
    data = (discovery or {}).get("data") or {}
    lang = "en" if "en" in data else (next(iter(data), None))
    feeds = {f.get("name"): f.get("url") for f in ((data.get(lang) or {}).get("feeds") or [])} if lang else {}
    return feeds.get("station_information"), feeds.get("station_status")


def _merge(info_list, status_list):
    """station_id -> merged {info fields} + {live status fields}. Driven by the live status snapshot."""
    info = {str(s.get("station_id")): s for s in (info_list or []) if s.get("station_id") is not None}
    out = {}
    for st in (status_list or []):
        sid = str(st.get("station_id")) if st.get("station_id") is not None else None
        if sid is None:
            continue
        m = dict(info.get(sid, {}))
        m.update(st)
        out[sid] = m
    return out


def _build(system, sid, m):
    """One merged station record -> (Item, Obs)."""
    bikes = m.get("num_bikes_available")
    ebikes = m.get("num_ebikes_available")
    docks = m.get("num_docks_available")
    name = safe(m.get("name") or m.get("short_name") or sid)
    item = Item(f"{system}:{sid}", name=name,
                subtitle=system, category=system,
                extra={"system": system, "station_id": sid,
                       "short_name": m.get("short_name") or "", "region_id": m.get("region_id") or "",
                       "capacity": m.get("capacity"), "lat": m.get("lat"), "lon": m.get("lon")})
    obs = Obs(price_cents=(bikes * 100 if isinstance(bikes, int) else None),
              qty=(docks if isinstance(docks, int) else None),
              flags={"system": system, "bikes": bikes, "ebikes": ebikes, "docks": docks,
                     "bikes_disabled": m.get("num_bikes_disabled"),
                     "docks_disabled": m.get("num_docks_disabled"),
                     "capacity": m.get("capacity"),
                     "renting": m.get("is_renting"), "returning": m.get("is_returning"),
                     "installed": m.get("is_installed"), "last_reported": m.get("last_reported")})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.cc = cc if cc in SYSTEMS else "citibike"
        self.s = retry_session()
        self._stations = {}   # system slug -> {station_id: merged}; one load serves a whole pass

    def _get(self, url):
        r = self.s.get(url, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or {}

    def stations(self, system):
        if system not in self._stations:
            disc_url = SYSTEMS.get(system)
            if not disc_url:
                self._stations[system] = {}
                return self._stations[system]
            si_url, st_url = _feed_urls(self._get(disc_url))
            info = ((self._get(si_url) if si_url else {}).get("data") or {}).get("stations") or []
            status = ((self._get(st_url) if st_url else {}).get("data") or {}).get("stations") or []
            self._stations[system] = _merge(info, status)
        return self._stations[system]


class BikeShareSource(Source):
    name = "bikeshare"
    id_label = "SYSTEM:STATION"
    cc_default = "citibike"      # GBFS system; --cc baywheels|capitalbikeshare|divvy|bixi
    deal_label = "stockout risk"  # a renting station running dry (<= BIKES_LOW bikes left)
    search_limit_default = 25
    search_header = f"{'BIKES':>5}  {'DOCKS':>5}  {'CAP':>4}  STATION"

    def client(self, args):
        return _Client(args.cc)

    def doctor(self, cl):
        stations = cl.stations(cl.cc)
        return bool(stations), f"({len(stations)} stations in {cl.cc}; keyless GBFS station feed)"

    def search(self, cl, term, args):
        system = args.cc if args.cc in SYSTEMS else self.cc_default
        t = (term or "").lower()
        out = []
        for sid, m in cl.stations(system).items():
            if not t or t in safe(m.get("name") or "").lower():
                out.append(_build(system, sid, m))
        out.sort(key=lambda io: safe(io[0].name).lower())
        return out

    def fetch(self, cl, item_id):
        system, _, sid = str(item_id).partition(":")
        if not sid or system not in SYSTEMS:
            return None
        m = cl.stations(system).get(sid)
        return _build(system, sid, m) if m else None   # station gone from the feed = series ends

    def is_deal(self, obs):
        bikes, renting = obs.flags.get("bikes"), obs.flags.get("renting")
        return bool(renting) and isinstance(bikes, int) and bikes <= BIKES_LOW

    def deal_line(self, item, obs):
        f = obs.flags
        eb = f.get("ebikes")
        etail = f" ({eb} e-bike)" if isinstance(eb, int) and eb > 0 else ""
        return f"{f.get('bikes', '?')} bikes left{etail}, {f.get('docks', '?')} docks free  {item.name}  [{f.get('system')}]"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        cap = item.extra.get("capacity")
        return (f"{str(f.get('bikes', '?')):>5}  {str(f.get('docks', '?')):>5}  "
                f"{str(cap if cap is not None else '?'):>4}  {item.name}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  system   : {e.get('system', '')}",
                 f"  station  : {item.name}  ({e.get('short_name', '') or '?'})",
                 f"  location : {e.get('lat', '?')}, {e.get('lon', '?')}  (region {e.get('region_id', '') or '?'})",
                 f"  capacity : {e.get('capacity', '?')} docks"]
        if obs:
            f = obs.flags
            eb = f.get("ebikes")
            ebtail = f" (incl. {eb} e-bike)" if isinstance(eb, int) and eb > 0 else ""
            lines.append(f"  bikes    : {f.get('bikes', '?')} available{ebtail}")
            lines.append(f"  docks    : {f.get('docks', '?')} free")
            status = "renting" if f.get("renting") else "NOT renting"
            status += ", returning" if f.get("returning") else ", NOT returning"
            lines.append(f"  status   : {status}")
            ts = f.get("last_reported")
            if isinstance(ts, (int, float)):
                when = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                lines.append(f"  reported : {when}")
        return lines


SOURCE = BikeShareSource()
