"""outages - live electricity-network outages via keyless ArcGIS Feature Services.

Electricity distributors publish their live outage map from an **ArcGIS Feature Service** - the
documented, keyless ArcGIS REST query standard (the WFS/GBFS class: a data standard built for client
reuse = sanctioned -> trove). Powercor (the Victorian, AU distributor) serves its live outages on
ArcGIS Online (`services7.arcgis.com`); the host serves no robots.txt (a 403 "Invalid URL" on
`/robots.txt` = a missing object = no rules = unfenced, the GBFS/S3 class), and the feature service is
exactly what the public outage map queries. `outSR=4326` reprojects the point geometry to clean
WGS84 lat/lon on the fly.

The timeline value is the **lifecycle of an outage**: it appears when reported, its crew status
progresses (Outage Reported -> Crews Attending -> Partially Restored -> restored), its estimated
restoration time (ETR) drifts, the customers-affected count falls as power comes back in stages, and
then it **drops off the feed** once restored. Nobody archives that per-outage progression - the
snapshot is the only record = high hoard value (nzroads/reverb retirement + metno ETR-drift).

There is no price on an outage, so the tracked scalar is **customers affected** * 100 in `price_cents`
(centi-customer), so the core's `drops` = an outage *shrinking* - customers restored in stages, a
recovery signal. `qty` = the crew-status ordinal (Reported 1 -> assigned/en-route 2 -> attending 3 ->
partially restored 4), so the response progression is a tracked integer too. money() cosmetically
renders centi-customers as dollars in the two core-hardcoded spots (geonet/nzroads precedent); the
rich displays show real counts. The "deal" (deal_label "major") = an **unplanned outage affecting
>= 100 customers** - the newsworthy, widespread events, not a single-property fault or scheduled work.

Model: one Item per outage (join key = composite `network:ORDER_ID`, split on the first ':' so a
multi-network watchlist stays coherent - the appcharts/bikeshare pattern; the prefix lets fetch/poll
rebuild the right feed). A network's whole live-outage set comes in one query (memoized per network),
so a full search/fetch/poll pass is a single polite request. There is no by-id endpoint, so fetch
scans the memoized feed (petrolspy/nzroads pattern); an ORDER_ID gone from the feed = restored = its
series ends. The point layer id is resolved from the FeatureServer metadata at runtime (GBFS
discovery pattern), so a new network only needs its FeatureServer URL added to NETWORKS. `--cc` picks
the network (default powercor).
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

# network code -> (label, FeatureServer URL, public outage-map URL).
NETWORKS = {
    "powercor": ("Powercor",
                 "https://services7.arcgis.com/si70weKpzPSa0BGV/arcgis/rest/services/Powercor_Outages/FeatureServer",
                 "https://www.powercor.com.au/outages-and-faults/current-outages/"),
}

# crew-status -> progression ordinal (Reported -> ... -> Partially Restored); unknown = 2 (mid).
CREW = {
    "outage reported": 1, "reported": 1,
    "crews assigned": 2, "en route": 2, "enroute": 2, "assigned": 2,
    "crews attending": 3, "on site": 3, "assessing": 3, "attending": 3,
    "partially restored": 4, "restored": 5,
}
MAJOR = 100    # unplanned outage affecting >= this many customers = a "major" event


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _net_of(item_id):
    return str(item_id).split(":", 1)[0]


def _build(net, feat):
    """One ArcGIS point feature -> (Item, Obs). None without an ORDER_ID."""
    a = (feat or {}).get("attributes") or {}
    oid = a.get("ORDER_ID")
    if not oid:
        return None
    label = NETWORKS[net][0]
    cust = _int(a.get("CUSTOMERS"))
    status = (a.get("CREW_STATUS") or "").strip()
    cause = (a.get("CAUSE") or "").strip()
    planned = "planned" in cause.lower()
    town = safe(a.get("TOWN") or "")
    area = safe(a.get("AREA") or "")
    street = safe(a.get("PRIVATISED") or "")
    lga = safe(a.get("LGA_NAME") or "")
    g = (feat or {}).get("geometry") or {}
    lon, lat = g.get("x"), g.get("y")
    key = f"{net}:{oid}"
    where = " - ".join(p for p in (town or area, street) if p) or f"outage {oid}"
    item = Item(key,
                name=safe(where),
                subtitle=safe(f"{cust if cust is not None else '?'} customers - {status or 'reported'}"),
                category=label,
                extra={"network": net, "order_id": str(oid), "town": town, "area": area,
                       "postcode": a.get("POSTCODE") or "", "lga": lga, "street": street,
                       "lat": lat, "lon": lon, "url": NETWORKS[net][2]})
    obs = Obs(price_cents=(cust * 100 if cust is not None else None),
              qty=CREW.get(status.lower(), 2),
              flags={"customers": cust, "status": status, "cause": cause, "planned": planned,
                     "etr": a.get("ETR") or "", "start": a.get("START_TIME") or "",
                     "town": town, "lga": lga, "network": net,
                     "updated": a.get("createDateTime") or ""})
    return item, obs


class _Client:
    """Memoizes each network's point-layer id and live feed (one query per network per run)."""

    def __init__(self):
        self.s = retry_session()
        self._layer = {}    # net -> layer id
        self._feed = {}     # net -> [features]

    def _headers(self):
        return {"User-Agent": UA, "Accept": "application/json"}

    def _point_layer(self, net):
        if net not in self._layer:
            r = self.s.get(NETWORKS[net][1], params={"f": "json"}, headers=self._headers(), timeout=40)
            r.raise_for_status()
            layers = (r.json() or {}).get("layers") or []
            pick = next((L["id"] for L in layers if L.get("geometryType") == "esriGeometryPoint"), None)
            if pick is None:
                pick = next((L["id"] for L in layers if "point" in (L.get("name") or "").lower()), None)
            self._layer[net] = pick if pick is not None else (layers[0]["id"] if layers else 0)
        return self._layer[net]

    def feed(self, net):
        if net not in self._feed:
            lid = self._point_layer(net)
            url = f"{NETWORKS[net][1]}/{lid}/query"
            r = self.s.get(url, params={"where": "1=1", "outFields": "*", "outSR": "4326",
                                        "returnGeometry": "true", "f": "json"},
                           headers=self._headers(), timeout=40)
            r.raise_for_status()
            self._feed[net] = (r.json() or {}).get("features") or []
        return self._feed[net]


class OutagesSource(Source):
    name = "outages"
    id_label = "OUTAGE"
    cc_default = "powercor"       # picks the network (see NETWORKS)
    deal_label = "major"          # unplanned + >= 100 customers
    search_args = [
        ("--planned", {"choices": ["only", "exclude", "all"], "default": "all",
                       "help": "planned outages: only / exclude / all (default all)"}),
    ]
    search_limit_default = 60     # a network's board is bounded; list it
    search_header = f"{'CUST':>5}  {'STATUS':<18}  OUTAGE"

    def _net(self, args):
        cc = getattr(args, "cc", None) or self.cc_default
        return cc if cc in NETWORKS else self.cc_default

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        net = self.cc_default
        feats = cl.feed(net)
        cust = sum((_int(f.get("attributes", {}).get("CUSTOMERS")) or 0) for f in feats)
        return bool(feats), (f"({len(feats)} live outages, {cust} customers affected on "
                             f"{NETWORKS[net][0]}; keyless ArcGIS FeatureServer)")

    def search(self, cl, term, args):
        net = self._net(args)
        want = getattr(args, "planned", "all") or "all"
        t = (term or "").lower()
        rows = []
        for f in cl.feed(net):
            built = _build(net, f)
            if not built:
                continue
            item, obs = built
            planned = obs.flags.get("planned")
            if want == "only" and not planned:
                continue
            if want == "exclude" and planned:
                continue
            e = item.extra
            hay = f"{item.name} {e.get('lga', '')} {e.get('postcode', '')} {obs.flags.get('status', '')}".lower()
            if not t or t in hay:
                rows.append((item, obs))
        rows.sort(key=lambda r: -(r[1].flags.get("customers") or 0))
        return rows

    def fetch(self, cl, item_id):
        net = _net_of(item_id)
        if net not in NETWORKS:
            return None
        oid = str(item_id).split(":", 1)[-1]
        for f in cl.feed(net):
            if str((f.get("attributes") or {}).get("ORDER_ID") or "") == oid:
                return _build(net, f)
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
        lines = [f"  network  : {item.category}  (order {e.get('order_id', '')})",
                 f"  location : {e.get('town', '')}  {e.get('lga', '')}  {e.get('postcode', '')}",
                 f"  street   : {e.get('street', '')}"]
        if obs:
            f = obs.flags
            lines.append(f"  customers: {f.get('customers')}  affected")
            lines.append(f"  status   : {f.get('status') or '?'}  {'planned' if f.get('planned') else 'UNPLANNED'}")
            lines.append(f"  cause    : {f.get('cause') or '?'}")
            lines.append(f"  started  : {f.get('start') or '?'}   ETR {f.get('etr') or '?'}")
            lines.append(f"  updated  : {f.get('updated') or '?'}")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = OutagesSource()
