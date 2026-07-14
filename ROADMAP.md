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

_Last mapped: 2026-07-14 (62 source files, 13 genres — **bixi** (Bixi Montréal bike-share) added as a
5th GBFS system on `bikeshare.py` (a single `SYSTEMS` config row, **no new file**), opening **CA
shared-mobility** (CA genres 1→2) and taking the GBFS class 4→5 systems. Prior 2026-07-12:
**northlandrivers + westcoastrivers** added as
Hilltop reskins (NZ rivers 3→5, opening Northland + West Coast); **Alberta ER-waits found
decommissioned → ⛔** on a health re-roll (see §3 #5/#31). Prior 2026-07-11: energex added as a 3rd `outages` NETWORKS row
(utilities = 1 driver, 3 networks; VIC + SE QLD + CA), still no new file, exercising the ArcGIS class
discipline. Prior 2026-07-08 consolidation folded mbhydro into `outages`, made the rivers trio thin
instances of `trove/hilltop.py`, and hoisted the ArcGIS mechanics to `trove/arcgis.py`; that day's full
61-source live doctor sweep: 59 OK, 0 dead — pokemontcg slow/flaky, eventcinemas doctor fixed to probe
tomorrow when today's board is over). Gate notes marked ✅/🟡/⛔ reflect live recon on those dates —
re-verify a host's robots before building; postures drift._

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
| weather, environment & geohazard | geonet, metno, volcano, nzski, gwrivers, avalanche, mdcrivers, horizonsrivers, northlandrivers, westcoastrivers, nswrfs, vicemergency, sacfs, beachwatch, safeswim, eafloods, usgs, wildfire, airquality | deepest (19; +Northland & West Coast rivers 2026-07-12) |
| space | spaceweather, sentry, spacelaunch | medium |
| aviation | chcflights, zqnflights, opensky | medium |
| roads & transport | nzroads, tfl, mbta, swisstransport | medium |
| shared mobility | bikeshare, sgtaxi | thin |
| parking | chcparking, sgcarpark | thin |
| **utilities & outages** | outages *(powercor VIC AU + mbhydro CA + energex SE QLD AU as NETWORKS rows)* | **thin (1 driver, 3 networks)** |
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
| AU | strong | fuel (WA), electricity (NEM), footfall, emergency×3, beach, **outages (VIC + SE QLD)** |
| UK | good | octopus, carbonintensity, tfl, eafloods |
| EU | some | awattar (DE/AT), swisstransport (CH), frankfurter |
| US | **thin vs its open-data richness** | mbta, opensky bbox, bikeshare (4 cities) — NWS is robots-fenced, but USGS/NOAA/Socrata/data.gov are wide open |
| SG | narrow | taxi, carpark |
| CA | **new (2)** | mbhydro (Manitoba Hydro outages, 2026-07-08) + bixi (Bixi Montréal bike-share, 2026-07-14 — 2nd CA genre); huge open-data surface still largely untouched |
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
| **ArcGIS Feature Service** | `/FeatureServer/<n>/query?where=1=1&outFields=*&f=json` via `trove/arcgis.py` | **outages** (powercor + mbhydro + energex NETWORKS rows), **wildfire** (NIFC/WFIGS) | AU/CA/US utility outages (Energex SE QLD ✅ **done 2026-07-11** — a NETWORKS row + field adapter, no new file; next: another distributor e.g. Ergon/SA Power, or water utilities), council hazard/asset layers, hydrant/roadwork/flood layers — discover via `arcgis.com/sharing/rest/search?q=<term> type:Feature Service`. Gotchas handled by FeatureBoard: layer isn't always id 0 (resolved by geometry type from `FeatureServer?f=json`); projected geometry (MB Hydro wkid 26914) reprojected via `outSR=4326`. **Gate on liveness** — a public layer can be a dead demo (Westpower 2022+TEST, PNM frozen dates), check the newest `*_UPDATE`/event timestamp. **Named reskins: §3 2a** (Ergon, SA Power, NSW×3, VIC×4, BC Hydro…) |
| **GBFS** | discovery `gbfs.json` → `station_status` | bikeshare (5 systems — citibike/baywheels/capitalbikeshare/divvy + **bixi** Montréal CA ✅ 2026-07-14) | any dock-mobility operator worldwide (systems.csv registry) — **named picks: §3 2b** (Ecobici/Vélib'/Toronto/US) |
| **Hilltop XML** | `?Request=GetData&Site=&Measurement=Flow` via `trove/hilltop.py` | gwrivers, mdcrivers, horizonsrivers, **northlandrivers**, **westcoastrivers** (each a ~20-line subclass) | every open NZ regional-council hydrology server (gate each host; a new council = name + host + label) — see §3 2c. **Gate lesson (2026-07-12):** the classic open `data.hts` SiteList is the buildable form (Northland `hilltop.nrc.govt.nz` ✅ 1126 sites, West Coast `hilltop.wcrc.govt.nz` ✅ 120 sites); **ECan `data.ecan.govt.nz` ⛔ `Disallow: /`** and **Tasman `envdata.tasman.govt.nz` ⛔** (749 sites but robots-fenced); **Otago/BoP `envdata.*` front Hilltop behind a `/Data` web-app — classic `.hts` SiteList not served** (🟡, needs the app's own AJAX endpoint); **Taranaki `extranet.trc.govt.nz/getdata` serves 325 sites but robots 503** (ambiguous — re-gate). Also: many gauges read **Stage only** and offline gauges return `<Error>No data…</Error>` (handled = skipped) |
| **Opendatasoft Explore** | `/api/explore/v2.1/catalog/datasets/<id>/records` | melbped | any ODS portal (cities, agencies) — `limit`≤100 — **named: §3 2d** (France fuel `data.economie.gouv.fr`, Paris) |
| **CKAN datastore** | `/api/3/action/datastore_search?resource_id=` | — | data.govt.nz, data.gov.au, data.qld live datastore resources — **§3 2d/30** (pick a *live* one, not a quarterly archive) |
| **Socrata** | `/resource/<id>.json` | — | US city/state open-data portals — **named: §3 2d/29** (NYC/Chicago/SF live 311, beach quality, ferry) |

---

## 3. The hitlist (prioritised, gate-vetted)

**Scoring:** *Hoard* = ephemerality × un-rebuildability (H/M/L, the core filter). *Gate* = ✅ verified
clean · 🟡 plausible, needs a recon pass · ⛔ known-fenced (skip/park). *Fills* = the gap it closes.
Pick the **top ✅ row that fills the biggest gap**; drop to 🟡 only with a recon budget.

_2026-07-11 hitlist expansion: Tier 2 fleshed out to **50+ named candidates** so a drop always has a
queue. Four seeded to ✅ via a robots-only gate pass (Alberta ER waits — opens **health** + the
**queue mechanic**; MISO + NYISO — open **US electricity**; Bixi Montréal — a GBFS config row opening
**CA mobility**); **AusTender** added to ⛔. The cheapest builds are the **class-instance reskins**
(§3 2a–2d): each is a config row / ~20-line subclass over §2, not a new file — prefer these when the
value is comparable. The strategic swings are §3 2e (health, streaming, civic listing-lifecycle)._

### Tier 1 — build-ready (gate ✅, fills a gap)

| # | target | class / mechanic | gate (verified 2026-07-07) | hoard | fills |
|---|--------|------------------|----------------------------|-------|-------|
| 1 | ~~**outages — Powercor**~~ | ArcGIS FS / scarcity+status+drift | ✅ services7.arcgis.com robots 403=missing; 21 live outages | **H** | ✅ **DONE this run** — opened utilities genre + the ArcGIS class |
| 2 | **more ArcGIS outage/utility feeds** — ✅ **mbhydro DONE 2026-07-08** (Manitoba Hydro, opened Canada); ✅ **energex DONE 2026-07-11** (Energex SE QLD, `VwEnergexOutages`, 126 live — a NETWORKS row + field adapter, no new file); next ✅ instance: another AU distributor (Ergon regional QLD, SA Power, Endeavour/Ausgrid NSW) or a water utility — discover via `arcgis.com` search, gate on liveness | ArcGIS FS | ✅ per-org (discover + liveness-check each) | **H** | utilities depth + AU/CA/US geography; **exploits the class** (each a config row) |
| 3 | ~~**USGS Water Services**~~ (`sources/usgs.py`) | telemetry / flood-rise | ✅ built 2026-07-07 | L–M | ✅ **DONE** — US rivers, fills US geography |
| 4 | ~~**NOAA Tides & Currents**~~ (`sources/noaatides.py`) | telemetry / tide | ✅ built 2026-07-07 | L–M | ✅ **DONE** — opened marine & coastal (w/ ndbc) |
| 4b | ~~**NDBC buoys**~~ (`sources/ndbc.py`) — added so marine isn't a lone-source genre | telemetry / sea-state | ✅ built 2026-07-07 | L–M | ✅ **DONE** — offshore wave/wind/temp |
| 4c | ~~**wildfire — NIFC/WFIGS**~~ (`sources/wildfire.py`) | ArcGIS FS / lifecycle | ✅ built 2026-07-07 | **H** | ✅ **DONE** — grew the ArcGIS class; US wildfire |
| 4d | ~~**airquality — Sensor.Community**~~ (`sources/airquality.py`) | telemetry / PM | ✅ built 2026-07-07 | L–M | ✅ **DONE** — opened the air-quality domain (global) |
| 5 | ~~**health — Alberta Health Services ER/ED waits**~~ (CA) | queue / wait-time | ⛔ **DEAD 2026-07-12** — robots was clean but the data service is **decommissioned**: `waittimes.alberta.ca` = "Alberta Wait Times Reporting is no longer available"; the AHS page just links the dead host. The Westpower/PNM liveness lesson at the *domain* level (robots ✅ ≠ live data) | — | health still **open** — see the re-roll sweep under #31 |
| 5b | **electricity — MISO real-time LMP** (US RTO) | price / em6 twin | ✅ robots 2026-07-11 (`api.misoenergy.org` robots 404 = unfenced, the S3-missing class; keyless `MISORTWD` JSON) | L–M (the RTO archives settlement — PoC, like octopus) | **US electricity** — opens the US into the deepest genre |
| 5c | ~~**bikeshare — Bixi Montréal**~~ (config row on `bikeshare.py`) | GBFS / scarcity | ✅ **DONE 2026-07-14** — `gbfs.velobixi.com` robots 404 re-verified; 1096 stations live | **H** | ✅ **opened CA shared-mobility** — a single `SYSTEMS` config row, no new file (GBFS 4→5) |
| 5d | **NASA EONET** (global natural-event tracker) | status ordinal / lifecycle | ⛔ **parked** — `/api/v3/events` JSON 503s on nearly every request (rate-limited/flaky, fails the reachability gate) | M | global all-hazards — revisit if the endpoint stabilises |

### Tier 2 — the deep hitlist (50+ named candidates; gate 🟡 unless marked)

The 2026-07-11 pass fleshed this out so a drop never re-derives a target from scratch. Grouped by
**lever**: most rows are **class-instance reskins** (a config row / ~20-line subclass over §2 — the
cheapest possible build), then the **new-domain / new-mechanic swings** (the biggest Axis-A/B gaps),
then breadth twins. Gate posture is a *starting* read — **re-verify robots for the exact data host
before building** (postures drift; the 2026-07-11 marks are robots-only, endpoint recon still owed).

**2a — ArcGIS outage/utility reskins** (grow `outages`; each a NETWORKS row + field adapter, **no new
file** — the energex pattern). Discover + liveness-check via `arcgis.com/sharing/rest/search?q=<term>
type:Feature Service`; gate on the newest event timestamp (Westpower/PNM were dead demos).

| # | target | region | fills |
|---|--------|--------|-------|
| 11 | **Ergon Energy** | regional QLD, AU | all-QLD with energex |
| 12 | **SA Power Networks** | SA, AU | new AU state |
| 13 | **Ausgrid · Endeavour · Essential Energy** | NSW, AU | opens NSW (3 distributors) |
| 14 | **AusNet · United Energy · Jemena · CitiPower** | VIC, AU | VIC depth beyond Powercor |
| 15 | **Western Power** · **Evoenergy** | WA / ACT, AU | opens WA + ACT |
| 16 | **BC Hydro · Hydro One · Hydro-Québec · Toronto Hydro** | CA | CA depth (mbhydro siblings) |
| 17 | **water-utility main-break / burst-main layers** | any | **new utility (water)** on the same class |
| 18 | **council roadworks / road-closure ArcGIS layers** | any | roads depth via the class (US IOUs: gate hard — many are Kubra/private = ⛔) |

**2b — GBFS shared-mobility reskins** (config rows on `bikeshare.py`; resolve `gbfs.json` at runtime —
Bixi ✅ **built 2026-07-14**, opened CA; next cheapest CA pick is Bike Share Toronto, #22). Registry:
MobilityData `systems.csv`.

| # | target | region | fills |
|---|--------|--------|-------|
| 19 | **Ecobici** (Mexico City) | MX | **opens LatAm** |
| 20 | **Tembici / Bike Itaú** (Rio, São Paulo) · **Mibici** (Guadalajara) | BR / MX | LatAm depth |
| 21 | **Vélib' Métropole** (Paris) · **WienMobil Rad** (Vienna) · **Nextbike / Donkey Republic** (multi-city) | EU | EU shared mobility |
| 22 | **Bike Share Toronto** | CA | CA mobility (Bixi sibling) |
| 23 | **Bluebikes** (Boston) · **Indego** (Philadelphia) · **Metro Bike Share** (LA) · **Nice Ride** (Minneapolis) | US | US depth |

**2c — Hilltop NZ regional-council hydrology reskins** (~20-line subclass on `trove/hilltop.py`; gate
each host on the classic `data.hts` SiteList). **Batch gated 2026-07-12** — NZ rivers 3 → 5.

| # | target | gate / outcome |
|---|--------|----------------|
| 24 | ~~**Northland RC**~~ (`sources/northlandrivers.py`) | ✅ **DONE** — `hilltop.nrc.govt.nz` robots 404, 1126 sites; opened the subtropical far north |
| 25 | ~~**West Coast RC**~~ (`sources/westcoastrivers.py`) | ✅ **DONE** — `hilltop.wcrc.govt.nz` robots 404, 120 sites; the wettest NZ region |
| 26 | **Taranaki RC** | 🟡 `extranet.trc.govt.nz/getdata` serves 325 sites but robots **503** (ambiguous) — re-gate then it's a config row |
| 27 | **Otago RC · Bay of Plenty RC** | 🟡 `envdata.*` front Hilltop behind a `/Data` web-app — classic `.hts` SiteList not served; needs the app's own AJAX endpoint (heavier recon) |
| 28 | **Environment Southland · Hawke's Bay · Waikato** | 🟡 hosts up but the `.hts` path is unresolved — discover the endpoint first |
| ⛔ | **ECan** `data.ecan.govt.nz` · **Tasman** `envdata.tasman.govt.nz` | `Disallow: /` (Tasman serves 749 sites but robots-fenced) — do not retry |

**2d — ODS / Socrata / CKAN live-datastore instances** (new class instances; pick a *live* resource,
not a quarterly archive — the melbped precedent).

| # | target | class | fills |
|---|--------|-------|-------|
| 27 | **France fuel — prix-carburants** (`data.economie.gouv.fr`, ODS) | ODS Explore | **EU fuel (spainfuel twin)** — H; 🟡 (local TLS revocation quirk blocked the probe here, not a host verdict) |
| 28 | **Paris Open Data** live counters (parking / footfall) | ODS Explore | EU attention/mobility |
| 29 | **NYC / Chicago / SF** live Socrata resource (311 queue, beach quality, ferry position) | Socrata | US civic/attention |
| 30 | **data.govt.nz · data.gov.au · data.qld** live datastore resource | CKAN | NZ/AU civic |

**2e — new domain / new mechanic** (the strategic swings — biggest gaps):

| # | target | mechanic | gate | hoard | fills |
|---|--------|----------|------|-------|-------|
| 31 | **live ED wait times** — a *keyless, still-live* dashboard (AU TAS/ACT/SA/NSW, or a CA province) | queue / wait-time | 🟡 **and hard** — the 2026-07-12 sweep: AU QLD ⛔ WAF-403, WA host 000; **CA Alberta decommissioned** (#5); **Nova Scotia = surgical/procedure wait-lists, not live ED** (slow, wrong mechanic, low hoard value); **WRHA Winnipeg "My Right Care" page carries no live board**; Sask host NXDOMAIN. Live-ED feeds keep getting retired/moved — needs a fresh, verified-live target | **H** | still the **biggest open domain** (health) + a mechanic trove has zero of |
| 32 | **NHS England A&E / urgent-care live waits** | queue / wait-time | 🟡 | **H** | UK health |
| 33 | **streaming content rotation** (JustWatch "leaving soon") | listing lifecycle | 🟡 GraphQL — check robots + page-called endpoint | **H** | **new domain (content)**; epic-class un-rebuildable rotation |
| 34 | **government tenders** — GETS NZ · TED (EU) · SAM.gov (US) | listing lifecycle | 🟡 (GETS robots targets only Semrush bots — confirm the `*` block; **AusTender ⛔**) | M–H | **civic** listing lifecycle |
| 35 | **court daily lists** (NZ / UK court schedules) | listing lifecycle | 🟡 | M | civic |
| 36 | **building-consent / planning-application queues** (council) | queue | 🟡 | M | civic |
| 37 | **passport / visa / immigration processing times** (published, drifts weekly) | queue / forecast-drift | 🟡 (often a plain page-parse) | M | civic queue |
| 38 | **real-estate listing lifecycle** — a *keyless* market (NZ majors ⛔) | listing lifecycle | 🟡→⛔ (Trade Me, realestate.co.nz, Designer Wardrobe fenced) | **H** | **new domain**; strongest lifecycle hoard if a gate opens |
| 39 | **port vessel arrival/departure schedules** (port-authority feed) | scarcity / lifecycle | 🟡 | M | marine (port congestion) |

**2f — deepen an existing genre** (em6 / spainfuel / opensky / attention twins):

| # | target | mechanic | gate | hoard | fills |
|---|--------|----------|------|-------|-------|
| 40 | **NYISO real-time LMP** (`mis.nyiso.com` CSV) | price | ✅ robots 404 (2026-07-11) | L–M (archived) | US electricity |
| 41 | **ERCOT** (TX) · **CAISO OASIS** (CA) · **Ontario IESO** (CA) | price | 🟡 (CAISO = heavy SOAP) | L–M | US/CA electricity |
| 42 | **Elexon BMRS** UK imbalance price · **Singapore USEP** | price | 🟡 | L–M | UK / SG electricity |
| 43 | **Brazil ANP fuel** · **Austria E-Control Spritpreisrechner** | price | 🟡 | **H** | LatAm / EU fuel |
| 44 | **GTFS-realtime** vehicle positions / trip delays (pick one agency) | delay-drift | 🟡 (protobuf) | **H** | transit depth |
| 45 | **adsb.lol / adsb.fi** community ADS-B (keyless) | telemetry | 🟡 | M | opensky twin |
| 46 | **Steam concurrent players** (`GetNumberOfCurrentPlayers`, keyless) | rank / attention | 🟡 | M | attention & rank |
| 47 | **MetService NZ marine/surf** *(parked)* | forecast-drift | 🟡 robots open, `publicData` paths moved — bundle recon | M–H | NZ marine |
| 48 | **GeoNet Tilde coastal sea level** *(parked)* + more NDBC / CO-OPS stations | telemetry | 🟡 `/v4/data/…` path unresolved; stations are config rows | M | NZ tsunami/coastal + marine breadth |

### Tier 3 — speculative / low-value (park until a steer wants them)

- **seismic / volcano breadth** — **USGS earthquakes** (✅ robots 404, 2026-07-11) · EMSC seismicportal ·
  Earthquakes Canada · Smithsonian GVP / USGS VNS volcano activity. Fully **archived** → **L** hoard
  (PoC/breadth only; the steam/frankfurter class).
- **auction close dynamics** — a keyless auction feed (govt/council surplus, some art/collectible
  houses); hoard the bid trajectory + closing snipe. New mechanic, un-rebuildable once closed.
- **venue busyness / occupancy %** — gym/library live occupancy counters. New mechanic (§1 Axis-B gap).
- **Global Dairy Trade** (NZ dairy auction) — NZ-relevant, but results are periodic + archived → **L**
  hoard (frankfurter class). Build only as a capability / So-NZ flex, tagged honestly.

### ⛔ Do-not-retry (gate-fenced or rebuildable — recorded so a drop doesn't burn a run)

api.weather.gov (NWS, `Disallow: /`) · CoinGecko / crypto (`Disallow: /api`) · BoardGameGeek
(`/xmlapi` + market JSON fenced) · CheapShark · PB Tech (`/search*` fenced) · **AusTender**
(`tenders.gov.au` — `/Search/*` + `/Cn/List*` + `/Son/List*` fenced; the search + contract-notice /
standing-offer list paths are gone = PB Tech class, 2026-07-11) · **Alberta ER wait times**
(`waittimes.alberta.ca` decommissioned — "no longer available"; AHS links a dead host, 2026-07-12) ·
**ECan `data.ecan.govt.nz`** + **Tasman `envdata.tasman.govt.nz`** Hilltop (`Disallow: /`) · Open-Meteo *api* host
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
