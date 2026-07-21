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

_Last mapped: 2026-07-21 (**100 sources / 129 boards / 16 genres**. Latest: the **100-source push**
(2026-07-21) — a `/goal`-driven +25 batch to reach 100 registered sources, live-reconned direct and
gated ✅-clean: 4 electricity (**aeso** Alberta / **elexon** GB wholesale / **ree** Spain / **elia**
Belgium), 2 EU fuel (**italyfuel** / **austriafuel**), 8 national weather opening **Japan / Ireland /
Netherlands / Finland / Sweden / Poland / Iceland** + **sgrain** (SG rainfall), 4 seismic opening
**Canada / Indonesia / Turkey / Japan** (eqcanada / bmkg / turkeyquake / jmaquake), **usgsvolcano** +
**gdacs** (global all-hazards — the NASA-EONET gap), **hbrivers** (NZ Hilltop), **adsbfi** (ADS-B twin),
**uktides** (UK marine), **dolarapi** (Argentina blue-dollar FX), **espnscores** (live sports). New ⛔
this run: EMSC/IRIS (robots-fenced fdsnws), Steam player-count (`Disallow:/`), BART (`/api/` fenced),
Nord Pool, GVP RSS; parked 🟡: EirGrid (503), IESO stale table, BOM (prior bot-block stands), Taranaki
Hilltop (robots 503). Prior: the **"10 new" batch** (2026-07-15) —
8 GBFS cities (bikeshare 16→24, opening **6 new countries**: vienna AT / milan IT / barcelona ES +
**deep LatAm** rio·saopaulo BR / santiago CL / baires AR / bogota CO) built by teaching the GBFS class
**v3.0** (`data.feeds` shape + `num_vehicles_available` + localised names; §2) — plus 2 new-file
public-apis survivors: **energinet** (EU/Nordic day-ahead electricity, em6/aemo/nyiso twin; used the
live `DayAheadPrices` after finding `Elspotprices` frozen at 2025-09-30) and **luchtmeetnet** (official
NL/RIVM air quality, calibrated twin of the citizen `airquality`). Prior 2026-07-14: the `public-apis`
funnel harvest (§3 2g) built **5 survivors** — `arbeitnow` (**opened jobs & labour domain**), `hkweather`
(**opened Asia**), `ipma` (EU weather), `bcferries` (ferry scarcity, CA), `paralelobo` (un-rebuildable
Bolivia parallel USD/BOB, LatAm macro). Earlier the "20 new" width batch — 20
boards in one pass: 11 GBFS cities (bikeshare 5→16, **ecobici opens LatAm**), 2 outages networks
(westernpower WA + bchydro BC → 5 networks), and 5 new-file sources: **nyiso** (US electricity),
**francefuel** (EU fuel), **adsblol** (opensky twin), **usgsquakes** (global), **civic311** (nyc/
chicago/sf — **opened the civic & government domain + the queue/wait-time mechanic**). Leaned on the
reusable classes (GBFS/ArcGIS/ODS/Socrata — each board a config row/adapter). Earlier 2026-07-14:
**bixi** added as the 5th GBFS system (opened CA shared-mobility). Prior 2026-07-12:
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

### Axis A — domain / genre (15)

| genre | sources | depth |
|-------|---------|-------|
| games / media / collectibles | steam, discogs, itunes, scryfall, pokemontcg, ygoprodeck, epic, steammarket | deep |
| fuel & electricity | spainfuel, petrolspy, em6, octopus, aemo, fuelwatch, awattar, carbonintensity, nyiso, francefuel, energinet | deep (11; +US electricity + EU fuel 2026-07-14; +DK/Nordic electricity 2026-07-15) |
| currency & macro | frankfurter, paralelobo *(Bolivia parallel USD)* | thin (2; +LatAm parallel FX 2026-07-14) |
| deals, fares & listings | grabone, grabaseat, bookme, turners, eventcinemas, reverb | good |
| attention & rank | hackernews, appcharts, melbped | medium |
| weather, environment & geohazard | geonet, metno, volcano, nzski, gwrivers, avalanche, mdcrivers, horizonsrivers, northlandrivers, westcoastrivers, nswrfs, vicemergency, sacfs, beachwatch, safeswim, eafloods, usgs, wildfire, airquality, usgsquakes, hkweather, ipma, luchtmeetnet | deepest (23; +HK & Portugal forecast 2026-07-14; +official NL air quality 2026-07-15) |
| space | spaceweather, sentry, spacelaunch | medium |
| aviation | chcflights, zqnflights, opensky, adsblol | medium |
| roads & transport | nzroads, tfl, mbta, swisstransport, bcferries *(ferry scarcity)* | medium (+ferries 2026-07-14) |
| shared mobility | bikeshare *(24 GBFS systems US/CA/MX/EU/LatAm)*, sgtaxi | good (2026-07-14: 5→16; 2026-07-15: 16→24, +LatAm depth + GBFS v3) |
| parking | chcparking, sgcarpark | thin |
| **utilities & outages** | outages *(powercor VIC + energex SE QLD + westernpower WA + mbhydro CA + bchydro BC as NETWORKS rows)* | **1 driver, 5 networks (AU×3 + CA×2)** |
| **marine & coastal** | noaatides, ndbc | (2) |
| **civic & government** | civic311 *(nyc + chicago + sf 311 backlogs)* | **new (1) — opened 2026-07-14 (queue mechanic)** |
| **jobs & labour** | arbeitnow *(EU/remote job board)* | **new (1) — opened 2026-07-14 (listing lifecycle)** |

**Domain white space (no coverage):** health / hospitals (ED wait times, capacity) · real estate &
rentals (listing lifecycle) · ~~jobs / labour market~~ ✅ **opened 2026-07-14** (`arbeitnow`, §3 2g) ·
streaming & content availability (leaving/arriving)
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
| queue / wait-time | age-in-queue + resolve | **civic311 (311 backlog, opened 2026-07-14)** |

**Mechanic white space (under-exploited even where a domain exists):**
- **auction dynamics** — opening→closing price, bid velocity, sniping. Nothing tracks a *live auction
  clock*. (turners has live-auction cars but hoards the asking price, not the bid trajectory.)
- **queue / wait-time** — people/jobs ahead of you (ED wait, passport/visa processing, support queue).
  **Opened 2026-07-14 by `civic311`** (a 311 request's age-in-queue + Open→Closed lifecycle); still no
  ED-wait / processing-queue source — the highest-value remaining queue targets (ROADMAP #31/#32/#37).
- **occupancy / utilisation %** — gym/library/venue busyness, crowd density (beyond parking & docks).

### Axis C — geography

| region | strength | notes |
|--------|----------|-------|
| NZ | **very deep** | fuel, electricity, rivers×3, ski, avalanche, beaches, roads, flights×2, parking, quakes, volcano |
| AU | strong | fuel (WA), electricity (NEM), footfall, emergency×3, beach, **outages (VIC + SE QLD + WA)** |
| UK | good | octopus, carbonintensity, tfl, eafloods |
| EU | **deeper (2026-07-15)** | awattar (DE/AT), swisstransport (CH), frankfurter, **francefuel (FR fuel)**, **energinet (DK/Nordic electricity)**, **luchtmeetnet (NL air quality)**, bikeshare (Oslo/Bergen/Trondheim NO + Warsaw PL + **Vienna AT + Milan IT + Barcelona ES**) |
| US | **much deeper (2026-07-14)** | mbta, opensky/adsblol bbox, bikeshare (9 US cities), **nyiso (electricity)**, usgsquakes (global), noaatides/ndbc/usgs, **civic311 (nyc/chicago/sf)** — still room (USGS/NOAA/Socrata/data.gov wide open) |
| SG | narrow | taxi, carpark |
| CA | **(3 genres)** | mbhydro + bchydro (outages), bixi + torontobike (bikeshare), 2026-07-14; huge open-data surface still largely untouched |
| LatAm | **much deeper (2026-07-15)** | ecobici (Mexico City) + **rio·saopaulo (BR) + santiago (CL) + baires (AR) + bogota (CO)** bike-share (Bike Itau/PBSC GBFS v3) + paralelobo (Bolivia parallel-market USD macro); more GBFS reskins still named in §3 2b |
| Asia | **new (1) — opened 2026-07-14** | hkweather (HK Observatory forecast + warnings); wider Asia + Japan still untouched |
| rest of world | **none** | Japan, wider Asia, Africa untouched |

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
| **ArcGIS Feature Service** | `/FeatureServer/<n>/query?where=1=1&outFields=*&f=json` via `trove/arcgis.py` | **outages** (powercor + energex + **westernpower** + mbhydro + **bchydro** — 5 NETWORKS rows), **wildfire** (NIFC/WFIGS) | more AU/CA/US utility outages — discover via `arcgis.com/sharing/rest/search?q=<term> type:Feature Service`. **⛔ found dead/absent 2026-07-14:** Ergon (no separate public outage FS — the Ergon org serves network/structures only), Ausgrid/Endeavour/Essential/SA Power (stale or no public FS). Gotchas handled by FeatureBoard: layer isn't always id 0; projected geometry (wkid 26914/102100) reprojected via `outSR=4326`. Field quirks: Western Power has **no crew-status field** + local date **strings** (not epoch-ms); BC Hydro join key = `GlobalID`. **Gate on liveness** — check the newest `*_UPDATE`/`TIMEADDED` timestamp (a sample feature can be an old planned outage; check the *max*). **Named reskins: §3 2a** |
| **GBFS** | discovery `gbfs.json` → `station_status` | **bikeshare — 24 systems** (US×9 + CA: bixi/torontobike + MX: **ecobici** + EU: oslobike/bergenbike/trondheimbike/warsawbike/**vienna/milan/barcelona** + LatAm: **rio/saopaulo/santiago/baires/bogota**); +11 on 2026-07-14, +8 on 2026-07-15 | any dock-mobility operator worldwide (systems.csv registry) — **named picks: §3 2b**. **Now handles GBFS v2 + v3.0** (2026-07-15): v3 drops the language layer (`data.feeds` directly), renames `num_bikes_available`→`num_vehicles_available`, and makes `name` a localised `[{text,language}]` list — a `_feed_urls` v3 branch + `num_vehicles_available` fallback + `_localized()` cover all three. Gate lesson: operator-branded hosts (bcycle_*/urbansharing/nextbike/PBSC/publicbikesystem.net) work; some Lyft/Smovengo hosts 403 or DNS-fail (niceride/velib/helsinki skipped). Pull discovery URLs from the MobilityData `systems.csv` registry (one fetch), don't guess hosts. Norwegian/Italian feeds have no `en` — the client falls back to the first language |
| **Hilltop XML** | `?Request=GetData&Site=&Measurement=Flow` via `trove/hilltop.py` | gwrivers, mdcrivers, horizonsrivers, **northlandrivers**, **westcoastrivers** (each a ~20-line subclass) | every open NZ regional-council hydrology server (gate each host; a new council = name + host + label) — see §3 2c. **Gate lesson (2026-07-12):** the classic open `data.hts` SiteList is the buildable form (Northland `hilltop.nrc.govt.nz` ✅ 1126 sites, West Coast `hilltop.wcrc.govt.nz` ✅ 120 sites); **ECan `data.ecan.govt.nz` ⛔ `Disallow: /`** and **Tasman `envdata.tasman.govt.nz` ⛔** (749 sites but robots-fenced); **Otago/BoP `envdata.*` front Hilltop behind a `/Data` web-app — classic `.hts` SiteList not served** (🟡, needs the app's own AJAX endpoint); **Taranaki `extranet.trc.govt.nz/getdata` serves 325 sites but robots 503** (ambiguous — re-gate). Also: many gauges read **Stage only** and offline gauges return `<Error>No data…</Error>` (handled = skipped) |
| **Opendatasoft Explore** | `/api/explore/v2.1/catalog/datasets/<id>/records` | melbped, **francefuel** (`data.economie.gouv.fr` ✅ 2026-07-14) | any ODS portal (cities, agencies) — `limit`≤100; use `where=` ODSQL for server-side filter — **named: §3 2d** (Paris counters, more EU fuel) |
| **CKAN datastore** | `/api/3/action/datastore_search?resource_id=` | — | data.govt.nz, data.gov.au, data.qld live datastore resources — **§3 2d/30** (pick a *live* one, not a quarterly archive) |
| **Socrata** | `/resource/<id>.json` | **civic311** (NYC + Chicago + SF 311 ✅ 2026-07-14) | more US city/state portals — beach quality, ferry position, restaurant inspections; per-city columns differ (a field adapter each, outages-NETWORKS style) — **named: §3 2d/29** |

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
| 5b | **electricity — MISO real-time LMP** (US RTO) | price / em6 twin | 🟡→ **parked 2026-07-14**: `getLMPConsolidatedTable&returnType=json` returned `{"error":"no data"}` (wrong messageType / off-market-hours). robots 404 clean; revisit with the right broker path. **NYISO (#40) built instead** for US electricity | L–M (PoC, like octopus) | US electricity |
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
| 15 | ~~**Western Power**~~ ✅ **DONE 2026-07-14** (WA, `WP_Outage_Prod` polygon, 145 live) · **Evoenergy** ⛔ (private Sitecore, not ArcGIS) | WA / ACT, AU | opened WA |
| 16 | ~~**BC Hydro**~~ ✅ **DONE 2026-07-14** (`BC_Hydro_Power_Outages` point, live) · Hydro One / Hydro-Québec / Toronto Hydro (Toronto Hydro FS returned no features — re-gate) | CA | CA outage depth (mbhydro siblings) |
| 17 | **water-utility main-break / burst-main layers** | any | **new utility (water)** on the same class |
| 18 | **council roadworks / road-closure ArcGIS layers** | any | roads depth via the class (US IOUs: gate hard — many are Kubra/private = ⛔) |

**2b — GBFS shared-mobility reskins** (config rows on `bikeshare.py`; resolve `gbfs.json` at runtime —
Bixi ✅ **built 2026-07-14**, opened CA; next cheapest CA pick is Bike Share Toronto, #22). Registry:
MobilityData `systems.csv`.

| # | target | region | fills |
|---|--------|--------|-------|
| 19 | ~~**Ecobici** (Mexico City)~~ ✅ **DONE 2026-07-14** (677 stations, `gbfs.mex.lyftbikes.com`) | MX | **opened LatAm** |
| 20 | ~~**Bike Itaú** (Rio, São Paulo)~~ ✅ **DONE 2026-07-15** (`rio`, `saopaulo` — PBSC GBFS v3) + ~~**Santiago** (CL) · **Buenos Aires** (AR) · **Bogotá** (CO)~~ ✅ **DONE 2026-07-15**; Mibici (Guadalajara) + more still open | BR/CL/AR/CO | ✅ **deep LatAm** (5 cities, 4 countries) |
| 21 | ~~**WienMobil Rad** (Vienna)~~ ✅ **DONE 2026-07-15** (`vienna`, nextbike v2) + ~~**Milan BikeMi** (IT)~~ ✅ + ~~**Barcelona Bicing** (ES)~~ ✅ **DONE 2026-07-15**; Vélib' Paris (Smovengo — 403 from here) + Nextbike/Donkey multi-city still open | EU | ✅ **+AT/IT/ES** (3 metros) |
| 22 | ~~**Bike Share Toronto**~~ ✅ **DONE 2026-07-14** (`torontobike`, 1050 stations, PBSC) | CA | CA mobility (Bixi sibling) |
| 23 | ~~**Bluebikes** (Boston) · **Indego** (Philadelphia) · **Metro Bike Share** (LA)~~ ✅ **DONE 2026-07-14** (+ madison + boulder BCycle); **Nice Ride** ⛔ (Lyft/host discovery failed here) | US | US depth (5 cities added) |

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
| 27 | ~~**France fuel — prix-carburants**~~ ✅ **DONE 2026-07-14** (`francefuel`, 9805 stations; ODS robots opens /api; earlier TLS quirk was transient) | ODS Explore | **EU fuel (spainfuel twin)** — H |
| 28 | **Paris Open Data** live counters (parking / footfall) | ODS Explore | EU attention/mobility |
| 29 | ~~**NYC / Chicago / SF** 311 queue~~ ✅ **DONE 2026-07-14** (`civic311`, opened civic domain + queue mechanic); next Socrata: beach quality, ferry position, restaurant inspections | Socrata | US civic/attention |
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
| 40 | ~~**NYISO real-time LMP** (`mis.nyiso.com` CSV)~~ ✅ **DONE 2026-07-14** (`nyiso`, 15 zones, `realtime_zone.csv`) | price | ✅ robots 404 | L–M (archived) | US electricity |
| 41 | **ERCOT** (TX) · **CAISO OASIS** (CA) · **Ontario IESO** (CA) | price | 🟡 (CAISO = heavy SOAP) | L–M | US/CA electricity |
| 42 | **Elexon BMRS** UK imbalance price · **Singapore USEP** | price | 🟡 | L–M | UK / SG electricity |
| 43 | **Brazil ANP fuel** · **Austria E-Control Spritpreisrechner** | price | 🟡 | **H** | LatAm / EU fuel |
| 44 | **GTFS-realtime** vehicle positions / trip delays (pick one agency) | delay-drift | 🟡 (protobuf) | **H** | transit depth |
| 45 | ~~**adsb.lol**~~ ✅ **DONE 2026-07-14** (`adsblol`, robots 404, alt in feet, `alt_baro`="ground"); adsb.fi still open | telemetry | ✅ | M | opensky twin |
| 46 | **Steam concurrent players** (`GetNumberOfCurrentPlayers`, keyless) | rank / attention | 🟡 | M | attention & rank |
| 47 | **MetService NZ marine/surf** *(parked)* | forecast-drift | 🟡 robots open, `publicData` paths moved — bundle recon | M–H | NZ marine |
| 48 | **GeoNet Tilde coastal sea level** *(parked)* + more NDBC / CO-OPS stations | telemetry | 🟡 `/v4/data/…` path unresolved; stations are config rows | M | NZ tsunami/coastal + marine breadth |

**2g — `public-apis` funnel harvest** (mined 2026-07-14). `github.com/public-apis/public-apis` (the
~330k-star curated directory) is a recurring **Phase-0 sourcing funnel** — a *menu* of endpoints, not a
capture engine (a different lane: it discovers, trove hoards). Parse its README, keep `Auth=No` +
`HTTPS=Yes` (~680 rows), then **most die at trove's filters**: keyed after all, *not* ephemeral (jokes/
dictionaries/reference), archived-elsewhere (crypto / official FX = frankfurter class / defunct COVID
trackers), or robots-fenced. Its 65 **Government** + 23 **Open Data** rows are national **CKAN/Socrata/
ArcGIS portals** = funnels for §2, not single sources. Survivors after triage + a live robots+liveness
gate (re-run the funnel any time targets run low):

| # | target | mechanic | gate (2026-07-14) | hoard | fills |
|---|--------|----------|-------------------|-------|-------|
| 49 | ~~**Arbeitnow**~~ ✅ **DONE 2026-07-14** (`arbeitnow`, 100 postings/GET) | listing lifecycle | ✅ | M–H | **opened the jobs & labour domain** (Axis-A white space) |
| 50 | ~~**Hong Kong Observatory**~~ ✅ **DONE 2026-07-14** (`hkweather`, 9-day forecast + warnsum) | forecast-drift / warning | ✅ | M–H | **opened Asia** (weather + warnings) |
| 51 | ~~**IPMA** (Portugal weather)~~ ✅ **DONE 2026-07-14** (`ipma`, day1 city forecast) | forecast-drift | ✅ | M–H | EU metno twin |
| 52 | ~~**Luchtmeetnet**~~ ✅ **DONE 2026-07-15** (`luchtmeetnet`; PM2.5 per RIVM station, paginated /stations + /measurements) | telemetry | ✅ robots 403-missing | M | **official NL air quality** (calibrated twin of citizen `airquality`) |
| 53 | ~~**Energinet**~~ ✅ **DONE 2026-07-15** (`energinet`; used live **`DayAheadPrices`** — `Elspotprices` was **frozen at 2025-09-30**; zones DK1/DK2/DE/NO2/SE3/SE4) | price | ✅ robots 404 | low-med | **EU/Nordic electricity** (em6/aemo/nyiso twin) |
| 54 | ~~**BC Ferries**~~ ✅ **DONE 2026-07-14** (`bcferries`; the whole board is at `/api/` root — the advertised `/api/v2/capacity/` was a dead end) | **scarcity** | ✅ robots 404 | **H** | **opened ferry sailing-capacity** (new transport sub-domain, CA) |
| 55 | ~~**paralelo.bo** (Bolivia parallel USD/BOB)~~ ✅ **DONE 2026-07-14** (`paralelobo`; endpoint = `/api/rate`) | price / macro | ✅ | **H** | **un-rebuildable black-market FX**; opened LatAm macro |
| — | ~~Luchtmeetnet · Energinet~~ ✅ **both DONE 2026-07-15** (see #52/#53) — the public-apis survivor queue is now exhausted; **re-run the funnel (§3 2g / §4.5) to refill** | — | — | — |

### Tier 3 — speculative / low-value (park until a steer wants them)

- **seismic / volcano breadth** — ~~**USGS earthquakes**~~ ✅ **DONE 2026-07-14** (`usgsquakes`, global geonet twin) · EMSC seismicportal ·
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
5. **When the hitlist runs low, re-run a sourcing funnel** to refill it. The standing funnel is
   `github.com/public-apis/public-apis` (§3 2g): parse its README, keep `Auth=No`+`HTTPS=Yes`, drop the
   non-ephemeral / archived / portal rows, then robots+liveness-gate the survivors into §3. It's a
   *discovery* menu, not a capture engine — a different lane from trove; it feeds Phase 0, it doesn't
   replace the gate.
