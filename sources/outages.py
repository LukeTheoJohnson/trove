"""outages - live electricity-network outages via keyless ArcGIS Feature Services.

Distributors publish their live outage maps from **ArcGIS Feature Services** - the documented,
keyless ArcGIS REST query standard (a data standard built for client reuse = sanctioned -> trove).
This is the multi-network driver for that class: one shared model, one network = one NETWORKS row
plus a small field adapter (the shared query mechanics live in trove/arcgis.py). `--cc` picks the
network. Gate records:

- **powercor** (Powercor, VIC AU): `services7.arcgis.com` serves no robots.txt (403 "Invalid URL" =
  missing object = no rules = unfenced, the GBFS/S3 class); the feature service is exactly what the
  public outage map queries. Point geometry.
- **mbhydro** (Manitoba Hydro, CA, ~600k customers): layer owned by the utility's own GIS staff on
  `services2.arcgis.com` (no robots.txt), marked public; what the public outage map queries. Polygon
  geometry in NAD83/UTM14N reprojected via `outSR=4326`; first ring vertex = the coord. Epoch-ms
  dates rendered as UTC `YYYY-MM-DD HH:MMZ`; a `11111111` sentinel/test feature is skipped.
- **energex** (Energex, SE QLD AU, ~1.6m customers): `VwEnergexOutages` service owned by
  `AGOL_ENERGEX_ADMIN` on `services.arcgis.com` (robots 403=missing=unfenced); two layers, point
  (id 1) picked by geometry. `EVENT_ID` = join key, `TYPE` PLANNED/UNPLANNED is the explicit planned
  flag, `STATUS` (Scheduled/Awaiting/In Progress/Cancelled) the crew ordinal, `EXTRACTED` epoch-ms =
  the snapshot time. Point geometry already WGS84 (wkid 4326).

The timeline value is the **lifecycle of an outage**: it appears when reported, its crew status
progresses, its estimated restoration time (ETR) drifts, the customers-affected count falls as power
comes back in stages, and then it **drops off the feed** once restored. Nobody archives that
per-outage progression - the snapshot is the only record = high hoard value.

There is no price on an outage, so the tracked scalar is **customers affected** * 100 in
`price_cents` (centi-customer), so the core's `drops` = an outage *shrinking* - customers restored
in stages. `qty` = the crew-status ordinal (reported 1 -> assigned 2 -> attending 3 -> partially
restored 4 -> restored 5). money() cosmetically renders centi-customers as dollars in the two
core-hardcoded spots (geonet/nzroads precedent); the rich displays show real counts. The "deal"
(deal_label "major") = an **unplanned outage affecting >= MAJOR customers**.

Model: one Item per outage; join key = composite `network:<outage id>` so a multi-network watchlist
stays coherent (the appcharts/bikeshare pattern). A network's whole live-outage set comes in one
memoized query, so a full search/fetch/poll pass is one polite request; there is no by-id endpoint,
so fetch scans the memoized feed (petrolspy/nzroads pattern) and an id gone from the feed =
restored = its series ends. **Gate a new network on liveness** before adding its row - a public
layer can be a dead demo (Westpower 2022+TEST, PNM frozen; see ROADMAP).
"""
from __future__ import annotations

from trove.arcgis import FeatureBoard, coords, epoch_ms, to_int
from trove.db import Item, Obs
from trove.tracker import Source, safe


def _powercor(a):
    """Powercor field adapter: raw attributes -> the common outage dict."""
    oid = a.get("ORDER_ID")
    if not oid:
        return None
    town = safe(a.get("TOWN") or "")
    area = safe(a.get("AREA") or "")
    street = safe(a.get("PRIVATISED") or "")
    lga = safe(a.get("LGA_NAME") or "")
    cause = (a.get("CAUSE") or "").strip()
    return {"oid": str(oid),
            "customers": to_int(a.get("CUSTOMERS")),
            "status": (a.get("CREW_STATUS") or "").strip(),
            "cause": cause,
            "planned": "planned" in cause.lower(),
            "etr": a.get("ETR") or "",
            "start": a.get("START_TIME") or "",
            "updated": a.get("createDateTime") or "",
            "where": " - ".join(p for p in (town or area, street) if p),
            "extra": {"town": town, "area": area, "postcode": a.get("POSTCODE") or "",
                      "lga": lga, "street": street},
            "flags": {"town": town, "lga": lga}}


def _energex(a):
    """Energex (SE QLD) field adapter: raw attributes -> the common outage dict."""
    oid = a.get("EVENT_ID")
    if not oid:
        return None
    suburb = safe(a.get("SUBURBS") or "")
    street = safe(a.get("STREETS") or "")
    otype = (a.get("TYPE") or "").strip()
    return {"oid": str(oid),
            "customers": to_int(a.get("CUSTOMERS_AFFECTED")),
            "status": (a.get("STATUS") or "").strip(),
            "cause": (a.get("REASON") or "").strip(),
            "planned": otype.upper() == "PLANNED",
            "etr": epoch_ms(a.get("EST_FIX_TIME")),
            "start": epoch_ms(a.get("START")),
            "updated": epoch_ms(a.get("EXTRACTED")),
            "where": " - ".join(p for p in (suburb, street) if p),
            "extra": {"town": suburb, "street": street},
            "flags": {"type": otype, "finish": epoch_ms(a.get("FINISH"))}}


def _mbhydro(a):
    """Manitoba Hydro field adapter: raw attributes -> the common outage dict."""
    oid = a.get("OUTAGE_ID")
    if not oid or str(oid) in {"11111111"}:    # MB Hydro's test/placeholder marker
        return None
    cause = (a.get("CAUSE") or "").strip()
    subcause = (a.get("SUBCAUSE") or "").strip()
    otype = (a.get("OUTAGE_TYPE") or "").strip()
    return {"oid": str(oid),
            "customers": to_int(a.get("NUM_CUST_NOPOWER")),
            "status": (a.get("CREW_STATUS") or "").strip(),
            "cause": cause,
            "planned": any("planned" in s.lower() or "scheduled" in s.lower()
                           for s in (otype, cause, subcause)),
            "etr": epoch_ms(a.get("ETR")),
            "start": epoch_ms(a.get("TIME_OF_OUTAGE")),
            "updated": epoch_ms(a.get("DATA_LAST_UPDATE")),
            "where": "",
            "extra": {},
            "flags": {"custtxt": safe(a.get("NUM_CUST_NOPOWERTXT") or ""), "subcause": subcause,
                      "type": otype, "etr_verified": (a.get("FIELD_VERIFIED_ETR") or "").strip()}}


# network code -> (label, FeatureServer URL, public outage-map URL, geometry, field adapter).
NETWORKS = {
    "powercor": ("Powercor",
                 "https://services7.arcgis.com/si70weKpzPSa0BGV/arcgis/rest/services/Powercor_Outages/FeatureServer",
                 "https://www.powercor.com.au/outages-and-faults/current-outages/",
                 "point", _powercor),
    "mbhydro": ("Manitoba Hydro",
                "https://services2.arcgis.com/QoeQkfdOG126FqSi/arcgis/rest/services/Manitoba_Hydro_Current_Power_Outages/FeatureServer",
                "https://account.hydro.mb.ca/portal/#/outages",
                "polygon", _mbhydro),
    "energex": ("Energex",
                "https://services.arcgis.com/bfVzktoY0OhzQCDj/arcgis/rest/services/VwEnergexOutages/FeatureServer",
                "https://www.energex.com.au/outages/current-outages",
                "point", _energex),
}

# crew-status -> progression ordinal (all networks share the 1-5 scheme); unknown = 2 (mid).
CREW = {
    "outage reported": 1, "reported": 1, "initial assessment": 1,
    "scheduled": 1, "awaiting": 1,
    "crews assigned": 2, "crew assigned": 2, "assigned": 2, "en route": 2, "enroute": 2,
    "site assessed": 2,
    "crews attending": 3, "crew on site": 3, "on site": 3, "assessing": 3, "attending": 3,
    "repair in progress": 3, "in progress": 3,
    "partially restored": 4, "restored": 5, "cancelled": 5,
}
MAJOR = 100    # unplanned outage affecting >= this many customers = a "major" event


def _net_of(item_id):
    return str(item_id).split(":", 1)[0]


def _feed(cl, net):
    label, fs, url, geometry, adapt = NETWORKS[net]
    return cl.feed(fs, geometry)


def _build(net, feat):
    """One ArcGIS feature -> (Item, Obs) via the network's adapter. None for non-outage rows."""
    label, fs, url, geometry, adapt = NETWORKS[net]
    d = adapt((feat or {}).get("attributes") or {})
    if d is None:
        return None
    lat, lon = coords((feat or {}).get("geometry"))
    cust = d.get("customers")
    status = d.get("status") or ""
    item = Item(f"{net}:{d['oid']}",
                name=safe(d.get("where") or f"Outage {d['oid']}"),
                subtitle=safe(f"{cust if cust is not None else '?'} customers - {status or 'reported'}"),
                category=label,
                extra={"network": net, "outage_id": d["oid"], **d.get("extra", {}),
                       "lat": lat, "lon": lon, "url": url})
    obs = Obs(price_cents=(cust * 100 if cust is not None else None),
              qty=CREW.get(status.lower(), 2),
              flags={"customers": cust, "status": status, "cause": d.get("cause") or "",
                     "planned": bool(d.get("planned")), "etr": d.get("etr") or "",
                     "start": d.get("start") or "", "updated": d.get("updated") or "",
                     "network": net, **d.get("flags", {})})
    return item, obs


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
        return FeatureBoard(timeout=40)

    def doctor(self, cl):
        parts, alive = [], False
        for net in NETWORKS:
            rows = [b for b in (_build(net, f) for f in _feed(cl, net)) if b]
            cust = sum((ob.flags.get("customers") or 0) for _, ob in rows)
            alive = alive or bool(rows)
            parts.append(f"{NETWORKS[net][0]}: {len(rows)} outages, {cust} customers")
        return alive, "(" + "; ".join(parts) + "; keyless ArcGIS FeatureServer)"

    def search(self, cl, term, args):
        net = self._net(args)
        want = getattr(args, "planned", "all") or "all"
        t = (term or "").lower()
        rows = []
        for f in _feed(cl, net):
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
            hay = (f"{item.name} {e.get('lga', '')} {e.get('postcode', '')} "
                   f"{obs.flags.get('status', '')} {obs.flags.get('cause', '')}").lower()
            if not t or t in hay:
                rows.append((item, obs))
        rows.sort(key=lambda r: -(r[1].flags.get("customers") or 0))
        return rows

    def fetch(self, cl, item_id):
        net = _net_of(item_id)
        if net not in NETWORKS:
            return None
        oid = str(item_id).split(":", 1)[-1]
        for f in _feed(cl, net):
            built = _build(net, f)
            if built and built[0].extra.get("outage_id") == oid:
                return built
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
        lines = [f"  network  : {item.category}  (outage {e.get('outage_id') or e.get('order_id', '')})"]
        loc = "  ".join(p for p in (e.get("town", ""), e.get("lga", ""), e.get("postcode", "")) if p)
        if loc:
            lines.append(f"  location : {loc}")
        if e.get("street"):
            lines.append(f"  street   : {e.get('street')}")
        if obs:
            f = obs.flags
            n = f.get("customers")
            cust = f"  customers: {n if n is not None else '?'}  affected"
            lines.append(cust + (f"  ({f['custtxt']})" if f.get("custtxt") else ""))
            lines.append(f"  status   : {f.get('status') or '?'}  {'planned' if f.get('planned') else 'UNPLANNED'}")
            lines.append(f"  cause    : {f.get('cause') or '?'}  {f.get('subcause') or ''}".rstrip())
            etr = f"  started  : {f.get('start') or '?'}   ETR {f.get('etr') or '?'}"
            lines.append(etr + (f"  (verified: {f['etr_verified']})" if f.get("etr_verified") else ""))
            lines.append(f"  updated  : {f.get('updated') or '?'}")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = OutagesSource()
