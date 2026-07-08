"""wildfire - live US wildland fire incidents via the keyless NIFC/WFIGS ArcGIS Feature Service.

The National Interagency Fire Center publishes the authoritative US current-wildfire layer through the
Wildland Fire Interagency Geospatial Services (WFIGS) program as a public ArcGIS Online Feature Service
(`services3.arcgis.com/.../WFIGS_Incident_Locations_Current`) - the same keyless, documented ArcGIS
REST query standard the `outages` source uses (WFIGS is built for public/interagency reuse =
sanctioned -> trove). Reuses the ArcGIS class (roadmap §2) for a new hazard; fills US geography.

The timeline value is the **lifecycle of a fire incident**: it is discovered, its acreage grows, its
containment % climbs as crews work it, and then - once controlled/out - it drops off the *current*
layer. Nobody serves a queryable per-incident growth/containment history, so the snapshot is the
record (the nzroads/outages retirement + a growth curve). `price_cents` = incident size (acres) * 100
so the core's `drops` = a fire whose size was revised *down* (or superseded); `qty` = percent
contained. `is_deal` ("major") = an active wildfire (type WF) >= 1,000 acres and < 50% contained - a
large, uncontained fire. money() renders centi-acres as $ in the two hardcoded spots (geonet/outages
precedent); the rich display shows real acres.

Model: one Item per incident (join key = `IrwinID`, the IRWIN GUID; falls back to `OBJECTID`). One
query returns the whole current board (~700 incidents) with `outSR=4326` for clean lat/lon; fetch
scans the memoized feed (petrolspy/outages pattern), and an IrwinID gone from the layer = out =
series ends. `search <term>` filters by name/state/county; `--planned` splits wildfire (WF) vs
prescribed burns (RX). `--cc` is unused (one US layer).
"""
from __future__ import annotations

from trove.arcgis import FeatureBoard, epoch_ms
from trove.db import Item, Obs
from trove.tracker import Source, safe

LAYER = ("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
         "WFIGS_Incident_Locations_Current/FeatureServer/0")
OUT = ("IrwinID,OBJECTID,IncidentName,IncidentSize,PercentContained,FireCause,POOState,"
       "POOCounty,IncidentTypeCategory,IncidentTypeKind,FireDiscoveryDateTime")
MAJOR_ACRES = 1000       # >= this and < 50% contained (type WF) = a "major" active fire


def _feed(cl):
    return cl.feed(LAYER, out_fields=OUT)


def _build(feat):
    """One WFIGS incident feature -> (Item, Obs). None without a usable key."""
    a = (feat or {}).get("attributes") or {}
    key = a.get("IrwinID") or (str(a.get("OBJECTID")) if a.get("OBJECTID") is not None else None)
    if not key:
        return None
    name = safe(a.get("IncidentName") or key)
    size = a.get("IncidentSize")
    contained = a.get("PercentContained")
    cat = a.get("IncidentTypeCategory") or ""
    state = (a.get("POOState") or "").replace("US-", "")
    county = safe(a.get("POOCounty") or "")
    g = (feat or {}).get("geometry") or {}
    lon, lat = g.get("x"), g.get("y")
    try:
        acres = float(size) if size is not None else None
    except (TypeError, ValueError):
        acres = None
    item = Item(str(key),
                name=name,
                subtitle=safe(f"{int(acres) if acres is not None else '?'} acres, "
                              f"{int(contained) if contained is not None else '?'}% contained - "
                              f"{county}{', ' if county and state else ''}{state}"),
                category=("prescribed burn" if cat == "RX" else "wildfire"),
                extra={"state": state, "county": county, "type": cat,
                       "kind": a.get("IncidentTypeKind") or "", "lat": lat, "lon": lon,
                       "url": "https://www.nifc.gov/fire-information/maps"})
    obs = Obs(price_cents=(round(acres * 100) if acres is not None else None),
              qty=(int(contained) if contained is not None else None),
              flags={"acres": acres, "contained_pct": contained, "cause": a.get("FireCause") or "",
                     "type": cat, "state": state, "county": county,
                     "discovered": epoch_ms(a.get("FireDiscoveryDateTime"))})
    return item, obs


class WildfireSource(Source):
    name = "wildfire"
    id_label = "IRWIN"
    cc_default = "us"          # unused; one US layer
    deal_label = "major"       # active WF >= 1000 acres and < 50% contained
    search_args = [
        ("--planned", {"choices": ["only", "exclude", "all"], "default": "all",
                       "help": "prescribed burns (RX): only / exclude / all (default all)"}),
    ]
    search_limit_default = 30
    search_header = f"{'ACRES':>9}  {'CONT%':>5}  INCIDENT"

    def client(self, args):
        return FeatureBoard()

    def doctor(self, cl):
        feats = _feed(cl)
        wf = sum(1 for f in feats if (f.get("attributes") or {}).get("IncidentTypeCategory") == "WF")
        return bool(feats), f"({len(feats)} current incidents, {wf} wildfires; keyless NIFC/WFIGS ArcGIS FS)"

    def search(self, cl, term, args):
        t = (term or "").strip().lower()
        want = getattr(args, "planned", "all") or "all"
        rows = []
        for f in _feed(cl):
            built = _build(f)
            if not built:
                continue
            item, obs = built
            rx = obs.flags.get("type") == "RX"
            if want == "only" and not rx:
                continue
            if want == "exclude" and rx:
                continue
            hay = f"{item.name} {obs.flags.get('state', '')} {obs.flags.get('county', '')}".lower()
            if not t or t in hay:
                rows.append((item, obs))
        rows.sort(key=lambda r: -(r[1].flags.get("acres") or 0))
        return rows

    def fetch(self, cl, item_id):
        for f in _feed(cl):
            a = f.get("attributes") or {}
            if str(a.get("IrwinID") or a.get("OBJECTID") or "") == str(item_id):
                return _build(f)
        return None    # gone from the current layer = out; the series ends

    def is_deal(self, obs):
        f = obs.flags
        a, c = f.get("acres"), f.get("contained_pct")
        return (f.get("type") == "WF" and a is not None and a >= MAJOR_ACRES
                and (c is None or c < 50))

    def deal_line(self, item, obs):
        f = obs.flags
        return (f"{int(f.get('acres') or 0)} acres  {item.name}  ({f.get('contained_pct')}% contained; "
                f"{f.get('county')}, {f.get('state')})")

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        a = f.get("acres")
        c = f.get("contained_pct")
        return (f"{(int(a) if a is not None else '?'):>9}  {(int(c) if c is not None else '?'):>5}  "
                f"{item.name[:52]}{'  [RX]' if f.get('type') == 'RX' else ''}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  incident : {item.name}  ({item.category})",
                 f"  location : {e.get('county', '')}  {e.get('state', '')}  ({e.get('lat')}, {e.get('lon')})"]
        if obs:
            f = obs.flags
            lines.append(f"  size     : {f.get('acres')} acres   {f.get('contained_pct')}% contained")
            lines.append(f"  cause    : {f.get('cause') or '?'}   kind {e.get('kind') or '?'}")
            lines.append(f"  discovered: {f.get('discovered') or '?'}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = WildfireSource()
