"""mbhydro - live Manitoba Hydro power outages via the keyless ArcGIS Feature Service.

Manitoba Hydro (the provincial electricity utility, ~600k customers) publishes its live outage map
from an **ArcGIS Feature Service** - the documented, keyless ArcGIS REST query standard (the same
class as `outages` (Powercor) and `wildfire` (NIFC): a data standard built for client reuse =
sanctioned -> trove). The layer is owned by `dcarpenter@hydro.mb.ca` (the utility's own GIS staff),
marked public, on `services2.arcgis.com`; the host serves no robots.txt (a 403 on `/robots.txt` = a
missing S3 object = no rules = unfenced, the GBFS/S3 class), and the feature service is exactly what
the public outage map queries. The polygon geometry is stored in NAD83 / UTM 14N (wkid 26914), so
`outSR=4326` reprojects it to clean WGS84 lat/lon on the fly and the affected-area's first vertex is
taken as the representative coord (the nzroads MultiLineString pattern). This opens **Canada** - a
country trove had no coverage of - and takes the utilities genre to two networks.

The timeline value is the **lifecycle of an outage**: it appears when reported, its crew status
progresses (Initial Assessment -> Site Assessed -> ... -> restored), its estimated restoration time
(ETR) drifts (and flips FIELD_VERIFIED_ETR No -> Yes when a crew confirms it), the customers-affected
count falls as power comes back in stages, and then it **drops off the feed** once restored. Nobody
archives that per-outage progression - the snapshot is the only record = high hoard value
(nzroads/reverb retirement + metno ETR-drift).

There is no price on an outage, so the tracked scalar is **customers affected** * 100 in `price_cents`
(centi-customer), so the core's `drops` = an outage *shrinking* - customers restored in stages, a
recovery signal. `qty` = the crew-status ordinal (Initial Assessment 1 -> Site Assessed 2 -> attending
3 -> partially restored 4 -> restored 5), so the response progression is a tracked integer too.
money() cosmetically renders centi-customers as dollars in the two core-hardcoded spots (geonet/nzroads
precedent); the rich displays show real counts. The "deal" (deal_label "major") = an **unplanned
outage affecting >= 100 customers** - the newsworthy, widespread events, not a single-property fault or
scheduled work.

Model: one Item per outage (join key = OUTAGE_ID, stable across the event's life). The whole live set
comes in one memoized query, so a full search/fetch/poll pass is a single polite request. There is no
by-id endpoint, so fetch scans the memoized feed (petrolspy/nzroads pattern); an OUTAGE_ID gone from
the feed = restored = its series ends. The polygon layer id is resolved from the FeatureServer
metadata at runtime (the GBFS discovery pattern). Times are UTC (the payload's epoch-ms dates rendered
as `YYYY-MM-DD HH:MMZ`; Manitoba local is UTC-5/-6).
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

LABEL = "Manitoba Hydro"
FS = ("https://services2.arcgis.com/QoeQkfdOG126FqSi/arcgis/rest/services/"
      "Manitoba_Hydro_Current_Power_Outages/FeatureServer")
MAP_URL = "https://account.hydro.mb.ca/portal/#/outages"

# crew-status -> progression ordinal; unknown = 2 (mid).
CREW = {
    "initial assessment": 1, "reported": 1, "outage reported": 1,
    "crew assigned": 2, "assigned": 2, "en route": 2, "enroute": 2, "site assessed": 2,
    "crew on site": 3, "on site": 3, "assessing": 3, "attending": 3, "repair in progress": 3,
    "partially restored": 4, "restored": 5,
}
MAJOR = 100                       # unplanned outage affecting >= this many customers = "major"
SENTINELS = {"11111111"}          # MB Hydro's test/placeholder marker (far-north point, no times)


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _dt(ms):
    """Epoch-ms ArcGIS date -> 'YYYY-MM-DD HH:MMZ' (UTC). '' when null."""
    n = _int(ms)
    if n is None:
        return ""
    return datetime.fromtimestamp(n / 1000, timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def _build(feat):
    """One ArcGIS polygon feature -> (Item, Obs). None without an OUTAGE_ID (or a sentinel)."""
    a = (feat or {}).get("attributes") or {}
    oid = a.get("OUTAGE_ID")
    if not oid or str(oid) in SENTINELS:
        return None
    oid = str(oid)
    cust = _int(a.get("NUM_CUST_NOPOWER"))
    custtxt = safe(a.get("NUM_CUST_NOPOWERTXT") or "")
    status = (a.get("CREW_STATUS") or "").strip()
    cause = (a.get("CAUSE") or "").strip()
    subcause = (a.get("SUBCAUSE") or "").strip()
    otype = (a.get("OUTAGE_TYPE") or "").strip()
    planned = any("planned" in s.lower() or "scheduled" in s.lower() for s in (otype, cause, subcause))
    etr = _dt(a.get("ETR"))
    verified = (a.get("FIELD_VERIFIED_ETR") or "").strip()
    start = _dt(a.get("TIME_OF_OUTAGE"))
    updated = _dt(a.get("DATA_LAST_UPDATE"))
    # polygon reprojected to WGS84 (outSR=4326): first ring's first vertex = representative coord.
    g = (feat or {}).get("geometry") or {}
    rings = g.get("rings") or []
    lon, lat = (rings[0][0][0], rings[0][0][1]) if rings and rings[0] else (None, None)
    item = Item(oid,
                name=safe(f"Outage {oid}"),
                subtitle=safe(f"{cust if cust is not None else '?'} customers - {status or 'reported'}"),
                category=LABEL,
                extra={"outage_id": oid, "lat": lat, "lon": lon, "url": MAP_URL})
    obs = Obs(price_cents=(cust * 100 if cust is not None else None),
              qty=CREW.get(status.lower(), 2),
              flags={"customers": cust, "custtxt": custtxt, "status": status, "cause": cause,
                     "subcause": subcause, "type": otype, "planned": planned, "etr": etr,
                     "etr_verified": verified, "start": start, "updated": updated})
    return item, obs


class _Client:
    """Memoizes the polygon-layer id and the live feed (one query per run)."""

    def __init__(self):
        self.s = retry_session()
        self._layer = None
        self._feed = None

    def _headers(self):
        return {"User-Agent": UA, "Accept": "application/json"}

    def _poly_layer(self):
        if self._layer is None:
            r = self.s.get(FS, params={"f": "json"}, headers=self._headers(), timeout=40)
            r.raise_for_status()
            layers = (r.json() or {}).get("layers") or []
            pick = next((L["id"] for L in layers if L.get("geometryType") == "esriGeometryPolygon"), None)
            self._layer = pick if pick is not None else (layers[0]["id"] if layers else 0)
        return self._layer

    def feed(self):
        if self._feed is None:
            url = f"{FS}/{self._poly_layer()}/query"
            r = self.s.get(url, params={"where": "1=1", "outFields": "*", "outSR": "4326",
                                        "returnGeometry": "true", "f": "json"},
                           headers=self._headers(), timeout=40)
            r.raise_for_status()
            self._feed = (r.json() or {}).get("features") or []
        return self._feed


class MBHydroSource(Source):
    name = "mbhydro"
    id_label = "OUTAGE"
    cc_default = "mb"
    deal_label = "major"          # unplanned + >= 100 customers
    search_args = [
        ("--planned", {"choices": ["only", "exclude", "all"], "default": "all",
                       "help": "planned outages: only / exclude / all (default all)"}),
    ]
    search_limit_default = 60     # the board is bounded; list it
    search_header = f"{'CUST':>5}  {'STATUS':<18}  OUTAGE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        feats = cl.feed()
        cust = sum((_int(f.get("attributes", {}).get("NUM_CUST_NOPOWER")) or 0) for f in feats)
        return bool(feats), (f"({len(feats)} live outages, {cust} customers affected on "
                             f"{LABEL}; keyless ArcGIS FeatureServer)")

    def search(self, cl, term, args):
        want = getattr(args, "planned", "all") or "all"
        t = (term or "").lower()
        rows = []
        for f in cl.feed():
            built = _build(f)
            if not built:
                continue
            item, obs = built
            planned = obs.flags.get("planned")
            if want == "only" and not planned:
                continue
            if want == "exclude" and planned:
                continue
            hay = f"{item.name} {obs.flags.get('status', '')} {obs.flags.get('cause', '')}".lower()
            if not t or t in hay:
                rows.append((item, obs))
        rows.sort(key=lambda r: -(r[1].flags.get("customers") or 0))
        return rows

    def fetch(self, cl, item_id):
        oid = str(item_id)
        for f in cl.feed():
            if str((f.get("attributes") or {}).get("OUTAGE_ID") or "") == oid:
                return _build(f)
        return None    # gone from the feed = restored; the series ends

    def is_deal(self, obs):
        f = obs.flags
        c = f.get("customers")
        return (not f.get("planned")) and c is not None and c >= MAJOR

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('customers')} customers  {item.name}  [{f.get('status') or '?'}; ETR {f.get('etr') or '?'}]"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        c = f.get("customers")
        return f"{(c if c is not None else '?'):>5}  {(f.get('status') or '')[:18]:<18}  {item.name[:60]}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  network  : {item.category}  (outage {e.get('outage_id', '')})"]
        if obs:
            f = obs.flags
            n = f.get("customers")
            lines.append(f"  customers: {n if n is not None else '?'}  affected  ({f.get('custtxt') or ''})")
            lines.append(f"  status   : {f.get('status') or '?'}  {'planned' if f.get('planned') else 'UNPLANNED'}")
            lines.append(f"  cause    : {f.get('cause') or '?'}  {f.get('subcause') or ''}".rstrip())
            lines.append(f"  started  : {f.get('start') or '?'}   ETR {f.get('etr') or '?'}  (verified: {f.get('etr_verified') or '?'})")
            lines.append(f"  updated  : {f.get('updated') or '?'}")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = MBHydroSource()
