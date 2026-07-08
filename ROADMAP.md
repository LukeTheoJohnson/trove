# trove — landscape map + source roadmap

This is the **forward** planning doc for `/daily-tool-drop`: a map of the digital landscape trove
already captures, an honest read of the **white space**, and a **scoped, gate-vetted hitlist** of
future sources ranked so a drop can pick the top unblocked item instead of re-deriving a target from
scratch each run.

- **`backlog.md`** = the *retrospective* log (ported sources, gate records, skip rulings). Look there
  for "what did we build and why did we skip X".
- **`ROADMAP.md`** (this file) = the *prospective* hitlist ("what to build next and where the gaps
  are"). `/daily-tool-drop` should read this first and pick from Tier 1 unless the steer says otherwise.

The filter is unchanged (`backlog.md`): **ephemerality, not keyless** — hoard un-rebuildable *state*;
skip commodity data whose history is already downloadable. Gate order unchanged: **robots.txt first,
then sanctioned-first**.

_Last mapped: 2026-07-08 (60 source files, 13 genres, coverage unchanged — the consolidation pass folded
mbhydro into `outages` as a NETWORKS row (utilities = 1 driver, 2 networks, CA coverage kept), made the
rivers trio thin instances of `trove/hilltop.py`, and hoisted the ArcGIS mechanics to `trove/arcgis.py`.
A full 61-source live doctor sweep that day: 59 OK, 0 dead — pokemontcg slow/flaky, eventcinemas doctor
fixed to probe tomorrow when today's board is over). Gate notes marked ✅/🟡/⛔ reflect live recon on
that date — re-verify a host's robots before building; postures drift._

---

## 1. The landscape trove captures today

trove's coverage is best read on **three axes**: domain (genre), signal *mechanic* (the shape of the
ephemeral thing being hoarded), and geography. A gap on *any* axis is a drop target.

### Axis A — domain / genre (12)

| genre | sources | depth |
|-------|---------|-------|
| games / media / collectibles | steam, discogs, itunes, scryfall, pokemontcg, ygoprodeck, epic, steammarket | deep |
| fuel & electricity | spainfuel, petrolspy, em6, octopus, aemo, fuelwatch, awattar, carbonintensity | deep |
| currency & macro | frankfurter | **thin (1)** |
| deals, fares & listings | grabone, grabaseat, bookme, turners, eventcinemas, reverb | good |
| attention & rank | hackernews, appcharts, melbped | medium |
| weather, environment & geohazard | geonet, metno, volcano, nzski, gwrivers, avalanche, mdcrivers, horizonsrivers, nswrfs, vicemergency, sacfs, beachwatch, safeswim, eafloods, usgs, wildfire, airquality | deepest (17; +US rivers/wildfire + global air quality 2026-07-07) |
| space | spaceweather, sentry, spacelaunch | medium |
| aviation | chcflights, zqnflights, opensky | medium |
| roads & transport | nzroads, tfl, mbta, swisstransport | medium |
| shared mobility | bikeshare, sgtaxi | thin |
| parking | chcparking, sgcarpark | thin |
| **utilities & outages** | outages *(powercor VIC AU + mbhydro CA as NETWORKS rows)* | **thin (1 driver, 2 networks)** |
| **marine & coastal** | noaatides, ndbc *(new 2026-07-07)* | **new (2) — opened this batch** |

**Domain white space (no coverage):** health / hospitals (ED wait times, capacity) · real estate &
rentals (listing lifecycle) · jobs / labour market · streaming & content availability (leaving/arriving)
· marine / maritime (AIS vessel tracking, port congestion — coastal tides + offshore buoys now covered)
· sports (scores, odds-drift — gambling, off-brand for a public repo) · agriculture / commodities (dairy,
livestock) · telecom / internet status
· civic / government (tenders, court lists, consents, processing queues) · retail in-stock flips ·
dining / reservation availability.

### Axis B — signal mechanic (the "data type")

| mechanic | what it hoards | sources |
|----------|----------------|---------|
| price (per-entity) | an item's price over time | steam, discogs, itunes, TCG trio, all fuel/electricity, frankfurter, grabone/grabaseat, reverb, steammarket |
| scarcity / availability count | units left, filling/draining | eventcinemas, bikeshare, sgcarpark, chcparking, sgtaxi, bookme, **outages (customers)** |
| status / alert ordinal | a state escalating/easing | volcano, nzroads, tfl, mbta, nswrfs, vicemergency, sacfs, avalanche, beachwatch, safeswim, eafloods, **outages (crew status)** |
| forecast-drift | a prediction + its revision | metno, spaceweather, carbonintensity, sentry, spacelaunch, **outages (ETR)** |
| delay-drift | estimate vs schedule | chcflights, zqnflights, swisstransport |
| rank / attention | where eyeballs/crowds are | hackernews, appcharts, melbped |
| magnitude / telemetry | a measured live value | geonet, gwrivers/mdcrivers/horizonsrivers, opensky (altitude) |
| listing lifecycle | appear → markdown → vanish | turners, reverb, discogs, grabone |

**Mechanic white space (under-exploited even where a domain exists):**
- **auction dynamics** — opening→closing price, bid velocity, sniping. Nothing tracks a *live auction
  clock*. (turners has live-auction cars but hoards the asking price, not the bid trajectory.)
- **queue / wait-time** — people/jobs ahead of you (ED wait, passport/visa processing, support queue).
  Zero coverage; a genuinely new scalar shape.
- **occupancy / utilisation %** — gym/library/venue busyness, crowd density (beyond parking & docks).

### Axis C — geography

| region | strength | notes |
|--------|----------|-------|
| NZ | **very deep** | fuel, electricity, rivers×3, ski, avalanche, beaches, roads, flights×2, parking, quakes, volcano |
| AU | strong | fuel (WA), electricity (NEM), footfall, emergency×3, beach, **outages (VIC)** |
| UK | good | octopus, carbonintensity, tfl, eafloods |
| EU | some | awattar (DE/AT), swisstransport (CH), frankfurter |
| US | **thin vs its open-data richness** | mbta, opensky bbox, bikeshare (4 cities) — NWS is robots-fenced, but USGS/NOAA/Socrata/data.gov are wide open |
| SG | narrow | taxi, carpark |
| CA | **new (1)** | mbhydro (Manitoba Hydro outages) — opened 2026-07-08; huge open-data surface untouched |
| rest of world | **none** | Japan, wider Asia, LatAm, Africa untouched |

---

## 2. Reusable source *classes* (the multiplier)

The highest-leverage insight the roadmap makes explicit: several sources aren't one-offs, they're
**instances of a keyless data standard**. Once the pattern exists, a new instance is a **config row or
a ~20-line subclass over the shared class module — never a copied driver file**. (Learned the hard way:
the first "reskins" were 175-220-line clones because the source-file count was the scoreboard; the
2026-07-08 consolidation removed ~700 lines of clone code. Count networks/boards hoarded, not files.)
Shared class modules live in `trove/`: `trove/arcgis.py` (FeatureBoard client, epoch-ms/coords helpers),
`trove/hilltop.py` (client + HilltopRiversSource base). Prefer expanding a proven class before inventing
a new mechanic.

| class | query shape | built instance | more instances available |
|-------|-------------|----------------|--------------------------|
| **ArcGIS Feature Service** | `/FeatureServer/<n>/query?where=1=1&outFields=*&f=json` via `trove/arcgis.py` | **outages** (powercor + mbhydro NETWORKS rows), **wildfire** (NIFC/WFIGS) | AU/CA/US utility outages (Energex QLD next — `VwEnergexOutages`, 126 live: a NETWORKS row + field adapter in `sources/outages.py`, not a new file), council hazard/asset layers, hydrant/roadwork/flood layers — discover via `arcgis.com/sharing/rest/search?q=<term> type:Feature Service`. Gotchas handled by FeatureBoard: layer isn't always id 0 (resolved by geometry type from `FeatureServer?f=json`); projected geometry (MB Hydro wkid 26914) reprojected via `outSR=4326`. **Gate on liveness** — a public layer can be a dead demo (Westpower 2022+TEST, PNM frozen dates), check the newest `*_UPDATE`/event timestamp |
| **GBFS** | discovery `gbfs.json` → `station_status` | bikeshare (4 systems) | any dock-mobility operator worldwide (systems.csv registry) |
| **Hilltop XML** | `?Request=GetData&Site=&Measurement=Flow` via `trove/hilltop.py` | gwrivers, mdcrivers, horizonsrivers (each a ~20-line subclass) | every open NZ regional-council hydrology server (gate each host; a new council = name + host + label) |
| **Opendatasoft Explore** | `/api/explore/v2.1/catalog/datasets/<id>/records` | melbped | any ODS portal (cities, agencies) — `limit`≤100 |
| **CKAN datastore** | `/api/3/action/datastore_search?resource_id=` | — | data.govt.nz, data.gov.au, data.qld live datastore resources |
| **Socrata** | `/resource/<id>.json` | — | US city/state open-data portals |

---

## 3. The hitlist (prioritised, gate-vetted)

**Scoring:** *Hoard* = ephemerality × un-rebuildability (H/M/L, the core filter). *Gate* = ✅ verified
clean · 🟡 plausible, needs a recon pass · ⛔ known-fenced (skip/park). *Fills* = the gap it closes.
Pick the **top ✅ row that fills the biggest gap**; drop to 🟡 only with a recon budget.

### Tier 1 — build-ready (gate ✅, fills a gap)

| # | target | class / mechanic | gate (verified 2026-07-07) | hoard | fills |
|---|--------|------------------|----------------------------|-------|-------|
| 1 | ~~**outages — Powercor**~~ | ArcGIS FS / scarcity+status+drift | ✅ services7.arcgis.com robots 403=missing; 21 live outages | **H** | ✅ **DONE this run** — opened utilities genre + the ArcGIS class |
| 2 | **more ArcGIS outage/utility feeds** — ✅ **mbhydro DONE 2026-07-08** (Manitoba Hydro, opened Canada; now a NETWORKS row in `sources/outages.py`); **Energex** (SE QLD, `VwEnergexOutages`, 126 live) is the next ✅ instance — a NETWORKS row + ~30-line field adapter, **not a new file**; then water utilities / council hazard layers | ArcGIS FS | ✅ per-org (Energex verified live 2026-07-08; discover more via `arcgis.com` search) | **H** | utilities depth + AU/CA/US geography; **exploits the class** (each a config row) |
| 3 | ~~**USGS Water Services**~~ (`sources/usgs.py`) | telemetry / flood-rise | ✅ built 2026-07-07 | L–M | ✅ **DONE** — US rivers, fills US geography |
| 4 | ~~**NOAA Tides & Currents**~~ (`sources/noaatides.py`) | telemetry / tide | ✅ built 2026-07-07 | L–M | ✅ **DONE** — opened marine & coastal (w/ ndbc) |
| 4b | ~~**NDBC buoys**~~ (`sources/ndbc.py`) — added so marine isn't a lone-source genre | telemetry / sea-state | ✅ built 2026-07-07 | L–M | ✅ **DONE** — offshore wave/wind/temp |
| 4c | ~~**wildfire — NIFC/WFIGS**~~ (`sources/wildfire.py`) | ArcGIS FS / lifecycle | ✅ built 2026-07-07 | **H** | ✅ **DONE** — grew the ArcGIS class; US wildfire |
| 4d | ~~**airquality — Sensor.Community**~~ (`sources/airquality.py`) | telemetry / PM | ✅ built 2026-07-07 | L–M | ✅ **DONE** — opened the air-quality domain (global) |
| 5 | **NASA EONET** (global natural-event tracker) | status ordinal / lifecycle | ⛔ **parked** — `/api/v3/events` JSON 503s on nearly every request (rate-limited/flaky, fails the reachability gate) | M | global all-hazards — revisit if the endpoint stabilises |

### Tier 2 — high value, gate 🟡 (needs a recon pass first)

| # | target | mechanic | gate posture | hoard | fills |
|---|--------|----------|--------------|-------|-------|
| 6 | **health / ED wait times** (ACT / SA / TAS / NSW live dashboards) | **queue / wait-time (new mechanic)** | 🟡 QLD ⛔ WAF-403, WA unreachable — recon a state with a keyless page-called feed | **H** | **new domain (health)** + new mechanic |
| 7 | **streaming content rotation** (JustWatch / "leaving soon") | listing lifecycle / rotation | 🟡 GraphQL, check robots + page-called endpoint | **H** | **new domain**; epic-class un-rebuildable rotation |
| 8 | **MetService NZ marine/surf** *(parked)* | forecast-drift | 🟡 robots open, `publicData` paths moved — bundle recon | M–H | NZ marine (the oceanforecast geo-fence re-roll) |
| 9 | **GeoNet Tilde coastal sea level** *(parked)* | telemetry | 🟡 `/v4/domains` works, `/v4/data/…` path format unresolved | M | NZ tsunami/coastal; sibling of geonet |
| 10 | **real-estate listing lifecycle** (homes.co.nz / oneroof / realestate.com.au) | listing lifecycle | 🟡→⛔ NZ majors fenced (Trade Me, Designer Wardrobe) — find a keyless market | **H** | **new domain**; strongest listing-lifecycle hoard if a gate opens |

### Tier 3 — new-mechanic / speculative (park until a steer wants them)

- **auction close dynamics** — a keyless auction feed (govt/council surplus, some art/collectible
  houses); hoard the bid trajectory + closing snipe. New mechanic, un-rebuildable once closed.
- **passport / visa / immigration processing times** — the published "current processing time"
  drifts weekly; queue mechanic, forecast-drift cousin. Often a plain page-parse.
- **venue busyness / occupancy %** — gym/library live occupancy counters. New mechanic.
- **Global Dairy Trade** (NZ dairy auction) — NZ-relevant, but results are periodic + archived → **L**
  hoard (frankfurter class). Build only as a capability/So-NZ flex, tagged honestly.
- **CKAN / Socrata live datastore** — pick a *live* (not quarterly) resource to avoid the archived trap.

### ⛔ Do-not-retry (gate-fenced or rebuildable — recorded so a drop doesn't burn a run)

api.weather.gov (NWS, `Disallow: /`) · CoinGecko / crypto (`Disallow: /api`) · BoardGameGeek
(`/xmlapi` + market JSON fenced) · CheapShark · PB Tech (`/search*` fenced) · Open-Meteo *api* host
(`Disallow: /`) · DOC bookings (TLS-fingerprint WAF) · Auckland Airport (Cloudflare JS challenge) ·
Wellington Airport (`/flights/*` fenced) · **OpenAQ** (v3 now requires an API key — 401) · **QLD
Health** (Akamai WAF 403) · **Powerco self-hosted `gis.powerco.co.nz`** (403 — use the ArcGIS Online
copy, #1) · **Westpower NZ ArcGIS outage layer** (`WestpowerUnplannedOutageLayer` — gate clean/public
but **dead**: newest event 2022 + a `TEST` feature; abandoned demo) · **PNM (New Mexico) outages**
(public + live-ish but **stale** — dates frozen ~Nov, only ~2 tiny outages; not actively maintained) ·
equities / crypto spot (archived) · Wikipedia most-read / GitHub trending (rebuildable
from dumps / GH Archive) · **NASA EONET** (JSON endpoint 503s on nearly every request — flaky/
rate-limited, fails the reachability gate; open gate but unbuildable interactively 2026-07-07).

---

## 4. How `/daily-tool-drop` uses this file

1. Read §3. Take the **top Tier-1 ✅ row that fills the biggest open gap** (Axis A/B/C in §1). If a
   steer names a domain, jump to the matching row/tier.
2. Prefer **expanding a proven class** (§2) over a fresh mechanic when value is comparable — it's a
   ~30-line build and grows a genre's depth.
3. Re-verify the gate live (robots for the exact data host) before building — postures drift; §3's
   ✅/🟡 is a *starting* read, not a guarantee.
4. On completion: move the row to `backlog.md` (Ported), update §1 counts + the Axis tables, and add
   any newly-discovered target (or a fresh ⛔ ruling) back into §3 so the roadmap compounds.
