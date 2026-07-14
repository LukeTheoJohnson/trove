# trove — tool-drop backlog

Targets for the `/daily-tool-drop` routine. trove is a **hoarding engine**: the product isn't a
deal-finder, it's the *owned, proprietary, un-rebuildable time-series* the cache compounds into —
data that feeds other work and proves the capability.

**The filter is ephemerality, not keyless.** Anyone can wrap a keyless API; the question that decides
hoard value is: **can you rebuild this history later, or is the snapshot the only record?**

- **High hoard value** — ephemeral *state* with no public archive: live listings, inventory/availability,
  per-station fuel prices, "free this week" rotations, half-hourly tariffs. Gone tomorrow if you don't
  capture it.
- **Low hoard value (PoC-only)** — commodity prices whose history is already downloadable (crypto,
  mainstream card prices via MTGGoldfish/TCGplayer charts, Steam prices via SteamDB). You can backfill
  these anytime, so capturing them yourself is redundant. Fine for a capability demo; not a moat.

Genre still holds (UI-trapped JSON + a join key), gated the same way (robots + sanctioned-first), and
each pass adds a thin `sources/<name>.py`. But pick **ephemeral-first**.

## Ported sources

Grouped by genre (same sections as the `--help` listing and the data dictionary).

### games / media / collectibles
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| steam      | `sources/steam.py`     | appid      | archived (SteamDB)               | low (PoC) |
| discogs    | `sources/discogs.py`   | release id | **ephemeral** (live listing count + lowest ask, never archived) | **high** |
| itunes     | `sources/itunes.py`    | trackId    | free/price events not archived   | medium |
| scryfall   | `sources/scryfall.py`  | card id    | archived (MTGGoldfish)           | low (PoC) |
| pokemontcg | `sources/pokemontcg.py`| card id    | archived (prices.pokemontcg.io)  | low (PoC) |
| ygoprodeck | `sources/ygoprodeck.py`| card id    | no public cross-venue series      | medium |
| epic       | `sources/epic.py`      | offer id   | **ephemeral** (weekly free-game rotation + RRP-at-giveaway; no public archive of what was given away) | **med-high** |
| steammarket | `sources/steammarket.py` | appid:hash_name | **ephemeral** (live lowest-ask + listing depth + 24h volume; snapshot only) | low-med (PoC; third-party sites archive median prices) |

### fuel & electricity
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| spainfuel  | `sources/spainfuel.py` | province-IDEESS | **ephemeral** (per-station forecourt price, never archived) | **high** |
| petrolspy  | `sources/petrolspy.py` | station id      | **ephemeral** (NZ per-station forecourt fuel price, never archived) | **high** |
| em6        | `sources/em6.py`       | grid_zone_id    | **ephemeral** (half-hourly NZ electricity spot, no easy public archive) | **high** |
| octopus    | `sources/octopus.py`   | GSP group (A-P) | archived (the official API serves the **full** realized half-hourly rate history, paginated) | low-med (PoC; UK retail twin of em6, completes the electricity genre both hemispheres) |
| aemo       | `sources/aemo.py`      | NEM region      | **ephemeral** (5-min NEM dispatch price + demand + interconnector flow snapshot; AEMO archives settled prices but not the convenient live per-region series) | med (AU twin of em6; NEM prices can go negative) |
| fuelwatch  | `sources/fuelwatch.py` | suburb:address  | **ephemeral** (WA's legally-fixed daily forecourt price per station, overwritten each day, never archived per-station) | **high** (AU/WA twin of petrolspy/spainfuel; official regulator feed) |
| awattar    | `sources/awattar.py`   | market (de/at)  | archived (the marketdata endpoint serves the full realized hourly history by `start`/`end`) | low-med (PoC; EU EPEX twin of em6/aemo — demonstrates the `Obs.history` backfill (~90d hourly in one `item`); negative-price plunge flex) |
| carbonintensity | `sources/carbonintensity.py` | GB region (1-17) | **ephemeral** (the per-region carbon-intensity *forecast as issued*; NG ESO archives realized intensity but not the as-issued regional forecast series) | med-high (forecast-drift class; carbon twin of the electricity-price set) |
| nyiso      | `sources/nyiso.py`     | NY zone         | ephemeral 5-min spot *state* but **archived** (NYISO archives settlement) | low-med (US electricity; em6/aemo twin; keyless realtime_zone CSV; 2026-07-14 batch) |
| francefuel | `sources/francefuel.py`| station id      | **ephemeral** (per-station French forecourt pump price, overwritten in place, never archived per-station) | **high** (EU fuel; spainfuel/petrolspy twin; keyless Opendatasoft prix-carburants v2; 2026-07-14 batch) |

### currency & macro
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| frankfurter | `sources/frankfurter.py` | BASE:QUOTE (e.g. NZD:USD) | archived (ECB reference rates are a permanent public record; the whole series re-downloads in one GET) | low (PoC) — the draw is the **instant-depth ingestion capability** (`Obs.history` backfill, built for this source) + the daily buy-USD percentile signal |

### deals, fares & listings
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| grabone    | `sources/grabone.py`   | deal URL path   | **ephemeral** (daily-deal catalog churn + RRP/discount, never archived) | **high** |
| grabaseat  | `sources/grabaseat.py` | ORIGIN-DEST     | **ephemeral** (per-route cheapest airfare, moves daily, never archived) | **high** |
| bookme     | `sources/bookme.py`    | activity path   | **ephemeral** (activity deal price + *spaces remaining* ticking down, never archived) | **high** |
| turners    | `sources/turners.py`   | car detail path | **ephemeral** (a used car's asking-price markdown history over its listing, then the listing vanishes when it sells) | **high** |
| eventcinemas | `sources/eventcinemas.py` | cinemaId:date:sessionId | **ephemeral** (a screening's seats-remaining fill-rate from on-sale to showtime, never archived; session vanishes after it plays) | **high** |
| reverb     | `sources/reverb.py`    | listing id      | **ephemeral** (a used-gear listing's ask + seller markdowns over its life, then it sells and vanishes; Reverb keeps no public per-listing price-history archive) | **high** |

### attention & rank
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| hackernews | `sources/hackernews.py`| story id   | **ephemeral-ish** (the minute-level rank/points trajectory is served current-state-only; third parties snapshot front-page membership and final scores, not the climb) | med |
| appcharts  | `sources/appcharts.py` | country:chart:appId | **ephemeral** (the chart as published rotates through the day; chart *history* is exactly what Sensor Tower/Appfigures sell — no free public archive) | med-high |
| melbped    | `sources/melbped.py`   | Melbourne sensor id | **ephemeral** (per-minute street footfall right now, rising/falling through the day; no convenient live per-sensor archive) | med (AU attention/foot-traffic) |

### weather, environment & geohazard
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| geonet     | `sources/geonet.py`    | publicID        | archived (GeoNet catalogue + `/quake/history` revisions) | low-med (DS capability flex) |
| metno      | `sources/metno.py`     | city slug or `lat,lon` | **ephemeral** (forecast-*as-issued*: the free tier archives past *actuals* but never past *forecasts*, so the forecast-drift series is un-rebuildable) | **high** |
| volcano    | `sources/volcano.py`   | volcanoID       | archived (GeoNet VAL bulletins) | low-med (NZ geohazard suite w/ geonet; clean state series) |
| nzski      | `sources/nzski.py`     | resort data-slug | **ephemeral** (daily base depth + lifts/trails/open-closed churn, overwritten through the day, gone at season end; never archived) | **high** |
| gwrivers   | `sources/gwrivers.py`  | gauge site name | **ephemeral** (5-min river flow/level telemetry; GW archives it but no convenient unified per-gauge series) | med-high (live flood watch) |
| avalanche  | `sources/avalanche.py` | region slug        | **ephemeral** (the NZ backcountry avalanche danger rating *as issued* daily per region + its revision; NZAA serves the current advisory only, no public per-region danger-history series) | **high** (un-rebuildable forecast-drift; NZ geohazard, seasonal) |
| mdcrivers  | `sources/mdcrivers.py` | gauge site name    | **ephemeral** (Marlborough NZ river flow/level telemetry; no convenient unified per-gauge series) | med-high (NZ flood watch; gwrivers sibling, different region) |
| horizonsrivers | `sources/horizonsrivers.py` | gauge site name | **ephemeral** (Manawatu-Whanganui NZ river flow/level telemetry) | med-high (NZ flood watch; flood-prone region) |
| northlandrivers | `sources/northlandrivers.py` | gauge site name | **ephemeral** (Northland NZ river flow/level telemetry; subtropical, flood-prone far north) | med-high (NZ flood watch; gwrivers class, ~1100 sites) |
| westcoastrivers | `sources/westcoastrivers.py` | gauge site name | **ephemeral** (West Coast NZ river flow/level telemetry; wettest region, flashy alpine rivers) | med-high (NZ flood watch; gwrivers class, ~120 sites) |
| nswrfs     | `sources/nswrfs.py`    | incident id        | **ephemeral** (a NSW bush/grass fire's alert-level + size + status lifecycle, then it drops off the board once resolved; feed serves current state only) | **high** (un-rebuildable incident progression; AU geohazard) |
| vicemergency | `sources/vicemergency.py` | event id       | **ephemeral** (a Victorian all-hazards warning's alert-level lifecycle across fire/flood/storm, then resolved) | **high** (un-rebuildable; AU all-hazards) |
| sacfs      | `sources/sacfs.py`     | incident id        | **ephemeral** (an SA CFS incident's response level + status lifecycle, then closed) | med-high (AU emergency; all incident types) |
| beachwatch | `sources/beachwatch.py`| site id (uuid)     | **ephemeral** (NSW beach daily pollution forecast + water-quality rating, changes with rainfall, not archived per-site) | **high** (AU beach water quality) |
| safeswim   | `sources/safeswim.py`  | beach slug         | **ephemeral** (NZ beach water-quality traffic-light flipping GREEN/RED with stormwater; no per-beach live archive) | **high** (NZ twin of beachwatch) |
| eafloods   | `sources/eafloods.py`  | flood-area id      | **ephemeral** (England flood warnings *in force*: the Alert->Warning->Severe escalate/ease/resolve lifecycle; the EA serves only the current set, no queryable per-area warning history) | **high** (event-driven, often empty in dry spells — avalanche pattern; OGL sanctioned) |
| usgs       | `sources/usgs.py`      | USGS site number   | ephemeral *state* but **archived** (USGS keeps the full record; rebuildable, the octopus/frankfurter class) | low-med (fills US geography; US twin of gwrivers; live flood flex; 2026-07-07 batch) |
| wildfire   | `sources/wildfire.py`  | IrwinID            | **ephemeral** (a US wildfire's acreage-growth + containment-% lifecycle, then it's out and drops off the *current* WFIGS layer; no queryable per-incident growth history) | **high** (reused the ArcGIS FS class for a new hazard; US geography; 2026-07-07 batch) |
| airquality | `sources/airquality.py`| sensor id          | ephemeral PM reading but **archived** (Sensor.Community keeps its own history; noisy citizen sensors) | low-med (opened the air-quality domain; global; 2026-07-07 batch) |
| usgsquakes | `sources/usgsquakes.py`| USGS event id      | ephemeral as-reported *state* but **archived** (USGS keeps the authoritative catalogue + revisions) | low (global earthquakes; geonet twin, worldwide; 2026-07-14 batch) |

### space
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| spaceweather | `sources/spaceweather.py` | UTC forecast date | **ephemeral** (the Kp/storm forecast *as issued* + its drift toward each target date; SWPC archives realized Kp but not the forecast-revision series) | **high** (un-rebuildable forecast-drift, aurora-australis signal) |
| sentry     | `sources/sentry.py`    | Sentry designation | **ephemeral** (the risk list *as issued*: ps/ip/ts revisions + when objects appear/retire; CNEOS publishes the current list and a bare removed-objects list, never the revision trajectory) | **high** (un-rebuildable revision drift; planetary defence) |
| spacelaunch | `sources/spacelaunch.py` | LL2 launch id | **ephemeral** (an upcoming launch's readiness + `net` *as scheduled*: the slip/scrub drift in the days before it flies; LL2 serves the current best estimate only, no as-issued schedule history) | med-high (un-rebuildable schedule-drift; metno/sentry class) |

### aviation
| source     | `sources/…`              | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|--------------------------|------------|----------------------------------|-------------|
| chcflights | `sources/chcflights.py`  | dir:type:flightNo:scheduled | **ephemeral** (a flight's estimate/gate/status drift from schedule in the hours before it operates; the board drops it once it operates and no public archive keeps the minute-by-minute progression) | **high** |
| zqnflights | `sources/zqnflights.py`  | dir:flightNo:schDate:schTime | **ephemeral** (same class as chcflights — and ZQN's weather-prone alpine runway makes its board NZ's most disruption-rich) | **high** |
| opensky    | `sources/opensky.py`   | icao24 (in a bbox) | **ephemeral** (live aircraft state vectors over a region; anonymous OpenSky serves the live snapshot only — history needs a contributor account) | med-high (un-rebuildable for anon; region-wide complement to the single-airport boards) |
| adsblol    | `sources/adsblol.py`   | icao hex (in range)| **ephemeral** (live aircraft near a point; adsb.lol keeps no free per-aircraft history) | med (keyless-community opensky twin, different network/coverage; 2026-07-14 batch) |

### roads & transport
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| nzroads    | `sources/nzroads.py`   | NZTA event id | **ephemeral** (a road event's impact escalation/easing + resolution lifecycle; the feed serves current state only and no public archive keeps the per-event progression) | **high** |
| tfl        | `sources/tfl.py`       | line id       | **ephemeral** (each London line's status ordinal flipping Good->Minor/Severe Delays->Part Suspended through the day; TfL serves current state only, no queryable per-line status history) | **high** (transit-status drift; London) |
| mbta       | `sources/mbta.py`      | alert id      | **ephemeral** (a Boston MBTA service alert's severity/effect lifecycle then it clears; only the current set is served) | med-high (transit alerts; twin mechanic to tfl) |
| swisstransport | `sources/swisstransport.py` | station\|line\|to\|schedTs | **ephemeral** (a Swiss rail/tram departure's delay drift in the minutes before it leaves, then it's gone; only the live board is served) | med-high (rail delay-drift; twin of chc/zqnflights) |

### shared mobility
| source     | `sources/…`             | join key          | ephemeral / archived elsewhere? | hoard value |
|------------|-------------------------|-------------------|----------------------------------|-------------|
| bikeshare  | `sources/bikeshare.py`  | system:station_id | **ephemeral** (a dock-based station's live bikes/docks-free count oscillating through the day — the fill/empty rebalancing cycle; GBFS serves current state only and no public archive keeps the per-station availability series). **16 systems**, each a config row (no new file): citibike/baywheels/capitalbikeshare/divvy/bluebikes/indego/metrobike/madison/boulder (US) + bixi/torontobike (CA) + **ecobici (MX — opened LatAm)** + oslobike/bergenbike/trondheimbike (NO) + warsawbike (PL). +11 added 2026-07-14 | **high** |
| sgtaxi     | `sources/sgtaxi.py`    | sg (whole fleet) | **ephemeral** (Singapore's island-wide roaming-taxi count swinging with demand/weather; data.gov.sg serves the live count only, no per-minute history) | med-high (shared-mobility supply index; complements bikeshare's per-station view) |

### parking
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| chcparking | `sources/chcparking.py` | park id   | **ephemeral** (Christchurch parking buildings' free-space counts through the day; CCC SmartView serves the live snapshot only, no per-park history) | **high** (NZ member of the parking genre; the keyless NZ live-parking source — AT is keyed, other councils use the private Frogparking app) |
| sgcarpark  | `sources/sgcarpark.py` | carpark number | **ephemeral** (~2,000 HDB car parks' free-space counts draining/refilling through the day; data.gov.sg serves current state only, no per-park availability history) | **high** (opened the parking genre; scarcity twin of bikeshare/eventcinemas) |

### utilities & outages
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| outages    | `sources/outages.py`   | network:outage id | **ephemeral** (a live electricity outage's customers-affected + crew-status + ETR-drift lifecycle, restored in stages then dropped off the feed; nobody archives the per-outage progression) | **high** (opened the utilities genre via the reusable keyless-ArcGIS-FeatureService class; **five networks** as NETWORKS rows: Powercor VIC AU 2026-07-07 + Manitoba Hydro CA 2026-07-08 + Energex SE QLD AU 2026-07-11 + **Western Power WA AU + BC Hydro British Columbia CA (both 2026-07-14)** — the mbhydro build **opened Canada** and was folded from its own clone file into a network row in the 2026-07-08 consolidation; energex/westernpower/bchydro added as pure NETWORKS rows + field adapters, no new file. WA/BC deepen AU + CA) |

### civic & government
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| civic311   | `sources/civic311.py`  | city:request id | **ephemeral** (a 311 request's age-in-queue + Open→Closed lifecycle; the city serves current state, no public archive keeps the wait-in-queue trajectory) | med-high (**opened the civic & government domain + the queue/wait-time mechanic** trove lacked; 3 US cities nyc/chicago/sf as config rows + Socrata field adapters; 2026-07-14 batch) |

### marine & coastal
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| noaatides  | `sources/noaatides.py` | station id | ephemeral tide *state* but **archived** (NOAA keeps the record) | low-med (opened the marine genre; US coastal water level + surge; 2026-07-07 batch) |
| ndbc       | `sources/ndbc.py`      | buoy id    | ephemeral sea *state* but **archived** (NDBC keeps the files) | low-med (marine genre; offshore wave/wind/temp; 2026-07-07 batch) |

The TCG trio is a fun capability flex but mostly **low hoard value** — their price history is already
public. The real moat in the current set is **discogs' marketplace state**. New sources should aim
high on this column.

## Active queue (ephemeral-first)

1. **UK fuel — CMA open data** `[RECLASSIFIED 2026-06-23 — no longer a keyless daily-drop]` — the
   interim voluntary scheme that published keyless per-retailer JSON feeds **closed 1 May 2026** and
   gov.uk withdrew the feed listing (`gov.uk/guidance/access-fuel-price-data` is now [Withdrawn]). Some
   retailer feeds still serve (Asda, Morrisons 200; Tesco 403, Sainsbury's dead), but they're no longer
   sanctioned-by-listing. The permanent replacement, **Fuel Finder** (Motor Fuel Price (Open Data)
   Regulations 2025, operated by VE3 Global), is **OAuth-gated**: GOV.UK One Login + OAuth 2.0 client
   credentials (`developer.fuel-finder.service.gov.uk`), plus twice-daily CSV bulk downloads. So UK fuel
   is now a *register-an-app + env-keys* build like trademe-cli — not a one-run keyless drop. Park until
   Luke wants to register a One Login developer account; then it's a clean OGL-v3.0 sanctioned source.
2. ~~**Spain fuel — MINETUR API**~~ `[DONE 2026-06-23]` → `sources/spainfuel.py`. Keyless MINETUR REST
   (`sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes`); every station's per-grade prices. Built
   as the keyless realization of the fuel-pipeline intent after UK's keyless path closed (see #1).
3. ~~**Octopus Energy Agile tariff**~~ `[DONE 2026-06-30, reclassified low-med]` → `sources/octopus.py`.
   Keyless official Octopus REST API (`api.octopus.energy`, robots 404 = unfenced; sanctioned →
   trove). Built as em6's UK *retail* twin: per-GB-region (GSP group A-P) half-hourly Agile unit rate
   (p/kWh inc VAT) in `price_cents`, deal = at/below today's avg or a **negative** plunge rate.
   **Hoard-value correction:** the backlog tagged this `[HIGH]`, but on inspection the
   `standard-unit-rates/` endpoint serves the **full** realized history (31k+ periods, paginated), so
   the realized series is *rebuildable* from the same API — closer to PoC/genre-completing than an
   un-rebuildable moat (same class as steam/scryfall). Built anyway: clean sanctioned source, completes
   the electricity genre across both hemispheres, and the negative-rate "plunge" signal is a fun
   capability flex. The product code is renamed ~yearly so it's discovered at runtime (currently
   `AGILE-24-10-01`).
4. ~~**Epic Games free-games rotation**~~ `[DONE 2026-07-01, med-high]` → `sources/epic.py`. Keyless
   store backend (`store-site-backend-static.ak.epicgames.com/freeGamesPromotions`; backend host has no
   robots, store.epicgames.com robots fences only `/account /cart /library` + `*?q=` search — never the
   promo backend → sanctioned → trove). One memoized GET returns the whole rotation; join key = offer
   `id`. `price_cents` = effective price (`0` while free, RRP once the window ends → core `drops` =
   an upcoming title crossing RRP→Free), `was_cents` = RRP, is_deal "free" = a live giveaway window.
   `--cc` picks country/currency (default nz → NZD).
5. ~~**A pure listings source**~~ `[DONE 2026-07-02, high]` → `sources/reverb.py`. Realized as
   **Reverb** (used musical-gear marketplace): official keyless `reverb.com/api/listings` (robots
   leaves `/api/listings` open, fencing only `/api/my` + a few per-listing sub-paths → sanctioned →
   trove). One Item per **listing** (join key = listing `id`) — the structural twin of `turners`
   (one listing, markdown history, then sold-and-vanished). `price_cents` = effective checkout price
   (`buyer_price`), `was_cents` = list `price` when marked down, `qty` = inventory; deal "sale" = a
   live seller markdown (`buyer_price` < `price`, Reverb's `sale_ribbon`). `--cc` display currency
   (default NZD via `X-Display-Currency`); `search --sale` filters to on-sale listings. Two candidates
   ahead of it this run were **BoardGameGeek** (skipped — `Disallow: /xmlapi` + a `# GeekMarket JSON
   endpoints` block fence both the XML API and the marketplace JSON). Deepening discogs' inventory
   churn is still open as a separate follow-up.
6. ~~**CoinGecko / crypto**~~ `[SKIPPED 2026-07-03 — robots-fenced]` — was queued as a LOW/PoC
   breadth demo, but the gate failed before politeness even came up: `api.coingecko.com/robots.txt`
   has `Disallow: /api/v3` (plus `/api/v1`, `/api/v2`, `/api/mobile`) — the exact data path fenced
   for `User-agent: *`. CheapShark skip class (sanctioned-first only applies to an un-fenced path).
   Hard skip, not even as a PoC.

## Skipped

- **NASA EONET (global natural events)** `[parked] 2026-07-07` — gate is fine (eonet.gsfc.nasa.gov
  robots 200/open, keyless official NASA), but the `/api/v3/events` JSON endpoint **returns 503 on
  nearly every request from here** (aggressive rate-limit / flaky) — a source that fails most calls
  isn't a viable interactive build (the nswair latency-gate lesson: gate on reachability, not just
  permission). Park; revisit if the endpoint stabilises (one memoized GET/run should be within limits).
- **Health / ED wait times (AU states)** `[parked] 2026-07-07` — highest-value open *new domain*
  (health + a queue/wait-time mechanic trove lacks), but the gate hunt stalled: QLD Health is Akamai
  WAF-403, WA EDWA host is unreachable (000), and the ACT/SA ED-dashboard page URLs 404 (moved). Needs
  a dedicated recon pass to find a state serving a keyless page-called wait-time feed (TAS/ACT/SA/NSW).
  Stays 🟡 on ROADMAP #6.
- **NWS / weather.gov alerts (US)** `[skipped] 2026-07-06` — `api.weather.gov/robots.txt` is
  `User-agent: * / Disallow: /` — the **entire** official API is robots-fenced. Hard skip (CheapShark
  class), even though it's keyless + documented and the active-alerts feed would have been a nice
  ephemeral-warning source. A US weather-warning hoard needs a differently-served provider.
- **FAA airport status (ASWS)** `[skipped] 2026-07-06` — `soa.smext.faa.gov` (the Airport Status Web
  Service host) does not resolve from here (NXDOMAIN) — dead or geo/DNS-blocked. Couldn't even reach
  robots; re-roll. (The old `services.faa.gov/airport/status/{code}` was retired years ago.)
- **Wikipedia most-read / pageviews** `[dropped] 2026-07-06` — gate is fine (api.wikimedia.org serves
  no real robots), but the daily most-read ranking is **rebuildable** from the public Pageviews API /
  dumps (frankfurter class) *and* it would be a fourth low-value entry in attention & rank. Not worth
  building over a higher-value ephemeral source.
- **GitHub trending / top repos** `[dropped] 2026-07-06` — `api.github.com/robots.txt` 404 (unfenced)
  and the search API is keyless, but per-repo star history is **rebuildable** from GH Archive
  (gharchive.org records every WatchEvent) → low hoard value. Dropped for the same reason as Wikipedia.
- **CoinGecko** `[skipped] 2026-07-03` — `api.coingecko.com/robots.txt` fences the data paths
  outright: `Disallow: /api/v1`, `/api/v2`, `/api/v3`, `/api/mobile`. The exact endpoints the
  keyless tier serves are disallowed for `User-agent: *` = CheapShark skip class. Closes Active
  queue #6 — the "LOW/PoC breadth demo" idea dies at the gate, which is tidier than building it.
- **MET Norway oceanforecast (NZ waves)** `[skipped] 2026-07-03` — the host gate is fine (same
  api.met.no as metno, `User-agent: *` fully allowed) but the *product* is geographically fenced:
  `oceanforecast/2.0` returns **422 "Oceanforecast is only available for Northern/Western Europe"**
  for NZ coordinates. New skip shape: a sanctioned host can still capability-fence one product by
  geography — gate the product's coverage, not just the host's robots. A NZ swell/marine source
  needs a different provider.
- **MetService (NZ marine/surf re-roll)** `[parked] 2026-07-03` — `www.metservice.com/robots.txt`
  is open (`User-agent: *`, zero Disallow), but the community-known `publicData/webdata/...` path
  scheme appears to have moved (two probed paths 404). Needs a page-bundle recon pass to find the
  current call sites before it's a real candidate; parked rather than skipped.
- **BoardGameGeek marketplace** `[skipped] 2026-07-02` — `boardgamegeek.com/robots.txt` fences both
  read paths for `User-agent: *`: `Disallow: /xmlapi` prefix-matches the official `/xmlapi2/thing?...
  marketplace=1` XML endpoint, **and** a dedicated `# GeekMarket JSON endpoints` block explicitly
  disallows `/api/market/products/saleitem` (listings) + `/api/market/products/pricehistory` (price
  series) — the exact marketplace data. Sanctioned API but the specific data paths are fenced, so it's
  the CheapShark skip class (sanctioned-first only applies to an un-fenced path). Hard skip.
- **CheapShark** `[skipped] 2026-06-23` — `cheapshark.com/robots.txt` has `Disallow: /api/1.0/`,
  fencing the exact data endpoint. Hard skip for an autonomous tool even though the API is keyless
  and documented (sanctioned-first only applies to an un-fenced path).

## Skipped (continued)

- **PB Tech** `[skipped] 2026-06-23` — `pbtech.co.nz/robots.txt` has `Disallow: /search*` for the
  general `User-agent: *` (only Adsbot/Mediapartners are allowed `/search*`). Product detail pages
  (price data) are allowed, but the discovery/search query path is fenced - one of the skill's
  explicit skip triggers - so an autonomous tool with a `search` command would hit a disallowed path.
  Skip rather than ship a search-crippled or robots-pushing retail source. (Supersedes the old
  playbook note that tagged PB Tech as a page-parse trove candidate - that predated reading the
  `/search` disallow.)

## Notes

- **"20 new" width batch (2026-07-14, second drop of the day after bixi; +20 boards, +5 source files,
  +1 genre; 67 sources / 88 boards / 14 genres):** the biggest single batch — leaned hard on the
  reusable classes (each new board a config row / thin adapter, the ROADMAP §2 payoff) plus 5 new-file
  sources across 6 genres. **Boards:** 11 GBFS cities (bikeshare 5→16: torontobike/ecobici[**opens
  LatAm**]/bluebikes/indego/metrobike/madison/boulder/oslobike/bergenbike/trondheimbike/warsawbike —
  US/CA/MX/EU) + 2 outages networks (westernpower WA + bchydro BC, both live) + nyiso (US electricity,
  em6/aemo twin) + francefuel (**EU fuel**, spainfuel twin, high) + adsblol (opensky twin) + usgsquakes
  (global geonet twin) + **civic311** (nyc/chicago/sf — **opened the civic & government domain + the
  queue/wait-time mechanic** the ROADMAP flagged as trove's biggest Axis-B gap). **Gate records:** all
  keyless, robots-gated first — GBFS feed hosts 404/missing (S3 class), `services*.arcgis.com` 403=missing,
  `api.misoenergy.org`/`mis.nyiso.com`/`earthquake.usgs.gov`/`api.adsb.lol` robots 404, France ODS fences
  only /login,/publish,/backoff (not /api), city Socrata `/resource/` open. **Field/liveness lessons:**
  Western Power polygon wkid 102100, join `INCIDENTREF`, explicit `PLANNEDOUTAGE`, no crew-status field
  (ordinal defaults mid), start/ETR are **local date strings** not epoch-ms — liveness confirmed by
  newest `TIMEADDED`=today (a sample feature can be an old planned outage; check the max, not the first).
  BC Hydro point layer, join `GlobalID`, `CREW_STATUS` dispatched/en_route/arrived added to the shared
  CREW map. France flux stores lat/lon as **int×10⁵** and price in euros (guard a millième form); ODS
  caps `limit` at 100 (melbped lesson). civic311: NYC/Chicago/SF Socrata columns **all differ** (per-city
  adapter, outages-NETWORKS style); the naive oldest-open board surfaced **6-year zombie records** (311s
  never formally closed) → bounded to the **last 30 days** for the genuine current backlog. adsb.lol
  altitude is **feet** and `alt_baro` can be the string "ground". **Skipped/dropped:** MISO real-time
  (`getLMPConsolidatedTable` returned "no data" — NYISO covers US electricity cleanly instead); Ergon
  Energy (no clean separate public outage FS — the Ergon org publishes network/structures, not outages;
  the Energex org's SE feed is Energex's own); Ausgrid/Endeavour/Essential/SA Power (stale or no public
  ArcGIS FS per the recon); GBFS niceride/velib/wienmobil (bad/blocked discovery URLs or near-empty).
  **Process lesson (recorded in [[reference_consumer_api_cli_playbook]]):** parallel recon subagents did
  the discovery work but **buried their raw payloads in closing summaries** (their final message is the
  only return value, and `SendMessage` wasn't available to pull the rest) — direct batched curl/python
  recon in the main thread was faster and kept every field. If delegating recon, the agent's *final
  message must be the raw data itself*, not a recap.

- **bixi gate (2026-07-14, Bixi Montréal bike-share — ROADMAP #5c, GBFS class reskin; shared-mobility
  4→5 systems, opened CA shared-mobility):** the cheapest possible build — the GBFS class already
  resolves each system's discovery doc at runtime and reads the feed URLs from it, so a new operator is
  a **single `SYSTEMS` config row, no new file** (the bikeshare twin of the energex NETWORKS-row
  discipline). Gate: `gbfs.velobixi.com/robots.txt` **404 = unfenced** (the S3 missing-object class, as
  with the other GBFS hosts); GBFS is published-for-reuse (trip planners) = sanctioned → trove. Recon:
  discovery `https://gbfs.velobixi.com/gbfs/gbfs.json` → `en`/`fr` language blocks; `_feed_urls` prefers
  `en`. The `en` `station_information` (1096 stations: `station_id`/`name`/`short_name`/`lat`/`lon`/
  `capacity`) + `station_status` (`num_bikes_available`/`num_ebikes_available`/`num_docks_available`/
  `is_renting`/`last_reported`) match the existing `_merge`/`_build` schema **exactly** — zero adapter.
  Verified live: doctor 1096 stations; search "Berri" → 11 stations (Berri / Jarry 1 bike / 26 docks =
  a live stockout-risk candidate). is_deal wiring proven offline (renting + ≤2 bikes → deal; 14 bikes or
  not-renting → not). **Note:** Montréal's French names carry accents (`Métro`) — `safe()` folds to
  cp1252 (which includes `é`) so trove's cp1252 console renders them and never crashes; the first
  French-accented GBFS system, exercising exactly the path `safe()` was built for. CA is now 2 genres
  (outages + shared mobility).

- **Hilltop NZ councils batch + Alberta/health re-roll (2026-07-12, "recon+build Alberta ER waits, then
  daily-tool-drop Hilltop NZ councils"):** two rivers reskins shipped (NZ rivers 3→5), and a health
  target that died on the liveness gate.
  - **Alberta ER waits (ROADMAP #5) is DEAD.** robots was clean (`albertahealthservices.ca` fences only
    `/org/`+`/rls/`), but the AHS wait-times page is now just a landing page linking
    `waittimes.alberta.ca` — which serves **"Alberta Wait Times Reporting is no longer available"** (443
    hangs from here; http 200 returns the retired-service notice). The **Westpower/PNM liveness lesson at
    the domain level**: a robots-clean gate does not prove the data service still exists. → ⛔.
  - **Health re-roll sweep (all failed to open the domain):** **Nova Scotia** `waittimes.novascotia.ca`
    is robots-clean + reachable but is a **surgical/procedure wait-list** site (pick a surgeon/procedure —
    hip replacement, MRI, cataract), slow-moving + wrong mechanic + low hoard value, not the live ED queue.
    **WRHA Winnipeg** `/wait-times/` ("My Right Care") is a WordPress page with **no live ED board on it**
    (the feed is elsewhere). **Saskatchewan** host NXDOMAIN. Lesson: live-ED-wait feeds keep getting
    decommissioned/moved — health needs a *verified-live* target, not just a robots-clean one. Health
    stays the biggest open domain (ROADMAP #31).
  - **Hilltop reskins (the win):** gated the classic `data.hts` SiteList across 16 candidate hosts. **Live
    + robots-unfenced → built:** **Northland** `hilltop.nrc.govt.nz` (robots 404, 1126 sites,
    `sources/northlandrivers.py`), **West Coast** `hilltop.wcrc.govt.nz` (robots 404, 120 sites,
    `sources/westcoastrivers.py`) — both pure ~22-line subclasses over `trove/hilltop.py`, zero new logic.
    Verified: Northland "Awanui at School Cut" Flow 6.36 m3/s (−16.6%/24h, receding); West Coast "Buller Rv
    @ Longford" 1417 mm. **Skip records:** ECan `data.ecan.govt.nz` + Tasman `envdata.tasman.govt.nz` =
    `Disallow: /` ⛔ (Tasman *does* serve 749 sites, but robots-fenced — respect it). **New sub-pattern
    (🟡):** Otago/BoP `envdata.*` **front Hilltop behind a `/Data` web-app** — the classic `.hts` SiteList
    isn't served (`data.hts`→404 Otago / 200-but-empty BoP); cracking them needs the app's own AJAX
    endpoint. Taranaki `extranet.trc.govt.nz/getdata` serves 325 sites but robots **503** (ambiguous —
    re-gate). Data lessons for future reskins: gauges are often **Stage-only** (no Flow); offline gauges
    return `<HilltopServer><Error>No data…</Error></HilltopServer>` (200 OK, handled → skipped, so a busy
    term can look empty — pick a live gauge for the demo).

- **mbhydro gate (2026-07-08, Manitoba Hydro outages — ROADMAP #2 "more ArcGIS outage/utility feeds";
  utilities 1->2, opened Canada):** the reusable ArcGIS FS class's own discovery mechanism did the
  target-finding — `www.arcgis.com/sharing/rest/search?q=<term> type:Feature Service` over "power/
  unplanned/electricity outage" returned public outage layers worldwide, ranked by views. Gate:
  `services2.arcgis.com/robots.txt` 403 (missing-object = unfenced, the S3 class); the layer is owned
  by `dcarpenter@hydro.mb.ca` (the utility's own GIS) + `access:public` = sanctioned -> trove.
  **The real gate here was liveness, not permission** (the nswair reachability lesson): two clean-looking
  public NZ/US layers were **dead** — **Westpower** (`WestpowerUnplannedOutageLayer`, NZ West Coast)
  newest event 2022 + a literal `TEST` feature; **PNM** (New Mexico) frozen at "November 18" dates.
  Manitoba Hydro's `DATA_LAST_UPDATE` was minutes old (13 live outages) — check the newest timestamp
  before building an ArcGIS layer, a public item can be an abandoned demo. Findings: (1) single polygon
  layer (id 0), geometry in **NAD83/UTM 14N (wkid 26914)** — request `outSR=4326` to get WGS84 lat/lon,
  first ring vertex = the coord (nzroads pattern). (2) rich schema: `NUM_CUST_NOPOWER` (int) +
  `NUM_CUST_NOPOWERTXT` (banded "Less than 5"), `CREW_STATUS` (Initial Assessment -> Site Assessed ->
  restored) = the qty ordinal, `ETR` + `FIELD_VERIFIED_ETR` (No->Yes flip) = the drift, `CAUSE`/
  `SUBCAUSE`. Join key = `OUTAGE_ID` (single network, no prefix). (3) dates are epoch-ms -> rendered UTC
  `YYYY-MM-DD HH:MMZ`; an `11111111` sentinel/test point (far-north, no times) is skipped. Kept as a
  **separate source** (not a Powercor `--cc`) because each utility's ArcGIS schema differs — the
  gwrivers/mdcrivers/horizonsrivers precedent (one source per class instance). **Energex (SE QLD, AU)**
  — `VwEnergexOutages`, 126 live events, also clean/live — is the obvious next ArcGIS-FS reskin, parked
  on ROADMAP.
- **energex gate (2026-07-11, Energex SE QLD outages — ROADMAP #2 "more ArcGIS outage/utility feeds",
  utilities 2->3 networks, deepens AU):** the reskin the mbhydro note flagged. Gate: `services.arcgis.com/
  robots.txt` 403 (missing = unfenced, the S3 class); service `VwEnergexOutages` owned by
  `AGOL_ENERGEX_ADMIN` (the utility's own admin) = sanctioned -> trove. 126 live events, fresh
  `EXTRACTED` timestamps (liveness confirmed, the Westpower/PNM lesson). **Added as a pure NETWORKS row
  + ~20-line field adapter in the existing `sources/outages.py` — no new file** (the class-instance
  discipline: count networks, not files; contrast the mbhydro build, which predated consolidation and
  arrived as a clone). Findings: two layers (`OutageArea` polygon id 0 / `OutagePoint` id 1) — the
  FeatureBoard picks the point layer by geometry; point geometry is **already WGS84 (wkid 4326)**, no
  reprojection. Schema: `EVENT_ID` (join key, `energex:INCD-xxxxxx-g`), `TYPE` PLANNED/UNPLANNED is an
  **explicit** planned flag (cleaner than powercor's cause-text sniff), `STATUS` (Scheduled/Awaiting/In
  Progress/Cancelled) the crew ordinal, `CUSTOMERS_AFFECTED`, `REASON` (Planned Maintenance/Emergency
  Repairs) the cause, `START`/`EST_FIX_TIME`/`FINISH`/`EXTRACTED` epoch-ms. Feed was 125 planned + 1
  unplanned at build (quiet period) — deal/major wiring proven offline against synthetic unplanned
  >=100 features.
- **ANZ width batch (2026-07-05, "10 new daily-tool-drops, NZ + AU relevant" — 10 sources in one pass,
  3 NZ / 7 AU):** all keyless, robots-gated first, no new genre (they fill fuel/electricity,
  attention & rank, and weather/geohazard). Gate records & lessons:
  - **aemo** (AU electricity): `visualisations.aemo.com.au` robots 404 = unfenced; `ELEC_NEM_SUMMARY`
    is the page-called report API → sanctioned. em6's AU twin (5 NEM regions, 5-min spot price + demand
    + interconnector flows; price can go negative).
  - **fuelwatch** (AU/WA fuel): `fuelwatch.wa.gov.au` robots fences only account paths, never
    `/fuelwatch`. **`Product=1` alone returns the whole state (~940 stations) in one RSS GET** — no
    station id in the feed, so the join key is composite `SUBURB|ADDRESS`; deal = below the station's
    suburb average. Official WA-Govt regulator feed (petrolspy/spainfuel twin).
  - **melbped** (AU foot-traffic): City of Melbourne migrated Socrata→**Opendatasoft**; the ODS Explore
    API (`/api/explore/v2.1/.../records`) is keyless (robots fences only /login,/publish). Live
    `past-hour-counts-per-minute` + `sensor-locations`, joined on `location_id`. **ODS caps `limit` at
    100** (a 200 → HTTP 400). centi-count scalar; deal = above the network median.
  - **mdcrivers / horizonsrivers** (NZ rivers): Marlborough (`hydro.marlborough.govt.nz`, robots 404)
    and Horizons (`hilltopserver.horizons.govt.nz`, no robots) run open Hilltop servers — gwrivers
    clones for two new regions. **Tasman (`envdata.tasman.govt.nz`) was skipped — robots `Disallow: /`**
    (a fenced Hilltop, unlike GW/MDC/Horizons); several other councils' hosts don't resolve.
  - **nswrfs / vicemergency / sacfs** (AU emergency): keyless GeoJSON/JSON incident feeds
    (`rfs.nsw.gov.au/feeds/majorIncidents.json`, `emergency.vic.gov.au/public/osom-geojson.json`,
    `data.eso.sa.gov.au/.../cfs_current_incidents.json`). Alert-level/response-level ordinal × 100 →
    `drops` = de-escalation (volcano/nzroads pattern); an incident off the feed = resolved. NSW RFS
    packs its fields into an RSS-style `description` (ALERT LEVEL / STATUS / SIZE...) — parsed out.
  - **beachwatch / safeswim** (AU + NZ beach water quality): `api.beachwatch.nsw.gov.au/public/sites/
    geojson` (245 NSW sites, star rating + pollution forecast) and `safeswim.org.nz/api/locations`
    (315 NZ beaches, GREEN/RED/RED+/BLACK traffic-light; Next.js app, no real robots.txt → the
    page-called same-origin API is keyless). safeswim is beachwatch's NZ twin; deal = a water-quality
    alert. safeswim's `state`/`position` can arrive as native or str-repr — coerce with literal_eval.
  - **Dropped/skipped this batch:** **nswair** (NSW air quality) — the `get_Observations` POST is
    unusably slow (39s for 10 sites, >90s for all) and date-fragile; built then removed. **Tilde**
    (GeoNet coastal/tsunami sea level) — `/v4/domains` + `/v4/dataSummary/{domain}` work but the
    `/v4/data/...` path format wouldn't resolve ("path error 7"); parked. **BOM** — bot-blocked.
    **OpenElectricity** keyless export is stale (Dec 2024). **GA earthquakes** — Angular SPA, API base
    obscured. **SharkSmart** — data behind a third-party map embed. **WaterNSW realtime** — WAF 403.
- **avalanche gate (2026-07-04, NZ Avalanche Advisory — invented, NZ-specific re-roll; weather/geohazard
  genre):** `avalanche.net.nz` 301s to `www.avalanche.net.nz`, whose robots is open (`User-agent: *`,
  `Disallow: /subscriptions/` only — the advisory/forecast data isn't fenced, no prose ban). SilverStripe
  + Vue app (`NZAA-Model-ForecastRegion` in the sitemap gave the 14 region slugs). The forecast data
  isn't embedded in the page (Vue shell) — grepping the bundle `forecast/dist/main.js` found the API
  wrapper `fetch(t) → GET /api/<t>`, called as `fetch("region")` + `fetch("forecast")`. Both are
  keyless, same-origin, page-called → **sanctioned → trove**. Findings: (1) `GET /api/region` →
  `{regions:[{id,title,urlSegment,latitude,longitude,...}]}` (13 forecast regions + a placeholder
  "outside-forecast-region"); `GET /api/forecast` → `{forecasts:[…]}` — **all regions' current + prior
  advisory in one GET** (26 forecasts for 13 regions), so the current one per region = max by `created`;
  one poll = 2 memoized GETs. (2) Join key = region `urlSegment` (e.g. `queenstown`; stable, matches the
  site URL). (3) Each forecast carries `altitudeDanger` = **three elevation bands** (rating 1-5, ordered
  high→low: Alpine / Sub-alpine / Below treeline) — label by *position*, not the altitude bounds (they
  share boundary values and mislabel the lowest band); **negative ratings (-1/-2) are "not rated"
  sentinels**, excluded from the headline. Headline danger = max valid band rating; `price_cents` =
  headline × 100 (centi-danger) so `drops` = the danger *easing* (geonet/volcano scalar reuse), `qty` =
  number of avalanche problems, deal "danger" = headline ≥ 3 (Considerable — where most incidents occur).
  (4) `avalancheDangers[]` = the problems (`character.title` = Wind Slab / Loose Wet / Persistent Slab…,
  plus `trend` Increasing/NoChange/Decreasing, likelihood, size, aspects); `confidenceLevel`,
  `forecaster`, `validPeriod` (24/48/72hrs) ride in flags. (5) **Seasonal**: off-season the payload has no
  current forecasts → search empty, fetch None (series pauses, resumes when forecasting restarts). Build
  snapshot (2026-07-04, mid-season): 13 regions live, 3 at Considerable & Increasing (Arthur's Pass,
  Aoraki/Mt Cook, Aspiring). **High** hoard value — the as-issued daily danger + its revision is
  un-rebuildable (NZAA archives no queryable per-region danger series).
- **bikeshare gate (2026-07-04, GBFS bike-share availability — invented, both queues empty; opened the
  shared mobility genre):** GBFS (General Bikeshare Feed Specification, governed by NABSA) is the open
  data standard operators publish for trip-planner reuse (Google/Apple Maps, Transit, Citymapper) —
  keyless, published-for-reuse = textbook sanctioned → trove. Gate findings: (1) the feed hosts
  (`gbfs.citibikenyc.com`, the shared data host `gbfs.lyft.com`, and the other systems' discovery hosts)
  all return **403 AccessDenied on `/robots.txt`** — an S3 "no such object" response = *no robots file =
  unfenced* (the SWPC 404-unfenced class, just a different HTTP code for a missing object). (2) The
  design resolves each system's **official discovery document** (`gbfs.json`) at runtime and reads the
  `station_information` + `station_status` feed URLs from it (prefer the `en` language block) rather than
  hardcoding Lyft paths — resilient to host/path drift and works for any GBFS operator. Verified four
  systems live: citibike (NYC, default), baywheels (SF), capitalbikeshare (DC), divvy (Chicago). (3)
  station_information is static (name/lat/lon/capacity), station_status is the ephemeral truth
  (`num_bikes_available`, `num_ebikes_available`, `num_docks_available`, `is_renting`, `last_reported`) —
  merged by `station_id`; the merge is driven by the live status list. (4) Scarcity tracker, same shape
  as eventcinemas: no price in the feed, the tracked scalar is availability. `price_cents` = bikes
  available × 100 (centi-bike, so `drops` = a station draining below first-seen), `qty` = docks free,
  deal "stockout risk" = a renting station with ≤2 bikes (running dry — grab one now / rebalancing
  candidate). Composite join key `system:station_id` (split on the first `:` since ids are UUIDs; the
  prefix lets fetch/poll rebuild the right feed — appcharts pattern). (5) A station gone from the feed =
  fetch returns None = the series ends (reverb/turners/nzroads retirement pattern). Honest hoard value
  **high**: the per-station fill/empty cycle is genuinely un-rebuildable — no public archive keeps
  historic availability per station. Build snapshot: citibike 2459 stations; 65 St & Broadway sat at 2
  bikes (both e-bikes) / 14 docks = a live stockout risk.
- **nzroads gate (2026-07-04, NZTA Journeys highway disruptions — invented, both queues empty):**
  `www.journeys.nzta.govt.nz/robots.txt` is `User-agent: *` + `Crawl-delay: 10` — zero Disallow, no
  prose ban (honoured trivially: one memoized GET serves a whole run). The marketing host
  `www.nzta.govt.nz` sits behind an Imperva/Incapsula challenge, but the journeys host serves
  plainly — gate the host you'll actually hit, not the brand's front door. The map's React bundle
  joins `"/assets/map-data-cache/" + "delays.json"` → one keyless page-called GET returns the whole
  national board (~109 events: closures/hazards/roadworks/warnings + a top-level `lastUpdated`
  epoch). Page-called + unfenced = sanctioned → trove; opened the **roads & transport** genre. Key
  findings: (1) join key = `properties.id` (NZTA ExternalId), stable across the event's life; no
  by-id endpoint, so fetch scans the memoized feed (petrolspy pattern) and a vanished event =
  resolved = the series ends — that retirement is half the hoard. (2) scalar = **impact ordinal**
  (Road Closed=4, Vehicle Restrictions=3, Delays=2, Caution=1) * 100 in `price_cents`, so core
  `drops` = a de-escalation (the volcano pattern pointed at roads). (3) the honest deal split is
  `IsPlanned==0 and Status=="Active" and >= Delays` — 89 of 109 events are scheduled roadworks; the
  4 live unplanned disruptions at build (SH 5 ice closure, SH 8 crash, SH 94 Milford vehicle
  restrictions, SH 29 closure) were exactly the newsworthy set. (4) geometry mixes Point and
  MultiLineString — take the first vertex as the representative coord. (5) 2 of 109 features are
  "News" items with null Impact/Status — severity 0, handled, never a deal.
- **frankfurter gate (2026-07-03, ECB FX — invented for the "lots of historic data in one poll"
  steer):** both `api.frankfurter.dev` and `frankfurter.dev` robots are `User-agent: * / Allow: /`
  (zero Disallow), and Frankfurter is an official, open-source (lineofflight/frankfurter), keyless,
  documented public API over ECB reference rates = sanctioned -> trove. Opened the **currency &
  macro** genre. Key findings: (1) the range endpoint (`/v1/1999-01-04..?base=NZD&symbols=USD`)
  returns the **entire 27-year daily series in one GET** — 7,040 rows, ~200 KB — shape
  `{amount, base, start_date, end_date, rates:{"YYYY-MM-DD":{SYM: float}}}`; `/latest` swaps
  `start_date`/`end_date` for a single `date`. (2) This run added the generic backfill channel the
  steer needed to `trove/db.py`: `Obs.ts` (backdated stamp) + `Obs.history` (backdated rows), merged
  idempotently under tag `hist` (only unseen `ts` values insert), so the first fetch seeds decades
  and every later poll appends just the new tail — backwards-compatible, no existing source touched.
  (3) The `fetch`/`refresh` split finally earns its keep as a *window* split: `fetch` (item) pulls
  the full epoch, `refresh` (poll) a trailing ~400 days — enough for the 1y percentile without
  re-shipping the epoch daily. (4) `price_cents` = rate * 10,000 (pips) — centi-units would be
  uselessly coarse for a ~0.56 rate; `qty` = trailing-1y percentile; deal "high" = >=90th pctile
  (base strong = a good conversion moment). At build, NZD/USD 0.5671 sat at the **8th** percentile
  (weak NZD — correctly not a deal). (5) Honest hoard value **low**: the steer inherently selects
  for archived data (you can only get deep history in one poll if someone archived it); the
  capability + signal are the point, stated up front in the backlog row.
- **Width batch (2026-07-03, "dramatically extend the width" — 4 drops, a new genre, 3 gate
  records):** four sources in one pass, opening **attention & rank** (a genre where the tracked
  scalar is *where the crowd's eyeballs are*, not a price) plus planetary defence and a second
  airport. All keyless, all robots-gated first. The centi-rank trick (rank * 100 in `price_cents`,
  so the core's `drops` = *climbing*) is the geonet scalar-reuse pattern pointed at position
  instead of magnitude, and works unchanged.
  - **sentry gate:** `ssd-api.jpl.nasa.gov` robots is **404 = unfenced**, and the Sentry API is
    official, documented, keyless NASA/JPL = sanctioned -> trove. Key findings: (1) list mode
    (`?ps-min=-4` -> 39 objects; the full list is ~2163) and detail mode (`?des=`) share field
    names, so one builder serves both; detail adds a `summary` block + per-virtual-impactor rows.
    (2) **every number arrives as a string** ("-2.77", "300") — parse defensively; `ts_max` can be
    JSON null (Bennu/1950 DA have no Torino rating). (3) designations contain spaces
    (`2000 SG344`) so the query is built with `%20` not `+` — the gwrivers/Hilltop lesson applied
    preemptively. (4) removal from the risk list = fetch returns None = the series ends; that
    *retirement event* is half the hoard's point. Deal "risk" = Torino >= 1 or Palermo >= -2.
  - **hackernews gate:** `hacker-news.firebaseio.com/robots.txt` is `Allow: /*.json$` +
    `Disallow: /` — the *allow-list matches exactly the official API's paths*, the cleanest
    possible sanction (the vendor whitelisted their own API shape). Key findings: (1) there is
    no rank field; rank = position in the `topstories.json` id list, memoized so one GET ranks a
    whole poll. (2) `search` scans the top-30 (one lightweight GET per story, 0.1s spacing) —
    bounded, never a crawl. (3) a story off the top-500 has rank None; obs ride on `qty` =
    comment count so the tail of a story's life still logs.
  - **appcharts gate:** `rss.marketingtools.apple.com/robots.txt` is a single documentation
    comment, zero Disallow = open; the marketing-tools RSS is Apple's own built-for-reuse feed =
    sanctioned -> trove. Key findings: (1) depth 100 works per chart (`/api/v2/nz/apps/top-free/
    100/apps.json`); (2) the same app sits in several charts/countries, so the join key is
    composite `country:chart:appId` and fetch/poll read the country from the *id*, not `--cc` —
    mixed-country watchlists stay coherent; (3) `feed.updated` timestamps the rotation.
  - **zqnflights gate:** `queenstownairport.co.nz` robots has zero Disallow (only a Sitemap), and
    grepping the site's own `all.bundle.js` gave the same-origin, keyless
    `/api/flights/arrivals` + `/api/flights/departures` = page-called + unfenced = sanctioned ->
    trove (chcflights precedent; AKL's Cloudflare wall and WLG's fenced paths keep them skipped).
    Key findings: (1) ZQN serves **full ISO date+time pairs** (`schDate`/`schTime` +
    `estDate`/`estTime`) — the delay is an honest datetime subtraction, no CHC midnight-wrap
    heuristic; (2) codeshares ride in `flightList[1:]`; (3) no by-flight endpoint, so the
    composite key `dir|flightNo|schDate|schTime` rebuilds the board query.
- **NZ-specific batch (2026-06-27, "3 drops to round out the repo"):** three distinct NZ genres
  trove lacked - geohazard alert state, ski recreation, and hydrology/flood.
  - **volcano** - GeoNet `/volcano/val` (sibling of `geonet`, same sanctioned keyless network; robots
    fences only marketing paths). One GET returns all 12 NZ volcanoes with `level` (0-5 VAL), `acc`
    aviation colour, `activity`/`hazards`. Join key = `volcanoID`. `price_cents`=level*100 so `drops`=a
    de-escalation; is_deal "unrest"=level>=1. (At build: Whakaari/White Island L2 Yellow, Ruapehu L1.)
  - **nzski** - NZSki snow reports (Coronet Peak / The Remarkables / Mt Hutt). Recon chain: resort
    weather-report pages are **Webflow + Alpine.js** (`x-text="snow.baseMin"`), data fetched by
    `weather-app.iife.js` as `https://webcams-<...>.azurefd.net/${slug}-data.json` where `${slug}` is a
    **mountain slug read from the page `<body>` class** ("Unrecognized mountain slug on <body>" was the
    tell). Slugs are irregular: `coronet-peak-winter`, `the-remarkables`, `mt-hutt` (probe per resort).
    Feed is **UTF-8-BOM JSON** (decode `utf-8-sig`; `/webcams-json/<Resort>.json` is a *different* feed -
    webcam images only, a red herring). Page-called + keyless + robots-clean = sanctioned -> trove.
    Join key = the data-slug. `price_cents`=base depth cm*100 (`drops`=melt); `qty`=lifts open;
    is_deal "open"=`MountainStatus`=="Open".
  - **gwrivers** - Greater Wellington Hilltop server (`hilltop.gw.govt.nz/Data.hts`), official council
    open hydrology, **no robots.txt (404)** = unfenced, keyless. `Request=SiteList` -> ~3335 gauge sites
    (join key = site name); `Request=GetData&Site=&Measurement=Flow&TimeInterval=PT24H/Now` ->
    `<E><T/><I1/></E>` 5-min series. **Gotcha: Hilltop does NOT decode `+` for spaces - `requests`
    encodes spaces as `+` and the server reads `Hutt+River+at+Taita+Gorge` literally ("No data for
    site"). Build the query with `urlencode(..., quote_via=quote)` so spaces become `%20`.** New genre =
    flood watch: the alerting event is a *rise* but the core only flags *drops*, so the 24h trend is
    computed at fetch and stored as `rising` (is_deal "rising"=latest>=1.5x the 24h-ago value); the
    core's `drops`=a river receding. (At build: Hutt River at Taita Gorge flow 47->341 m3/s, +620% =
    a live flood.) Page-parse/XML = sanctioned -> trove.
  - **Skipped this batch:** **Open-Meteo** (api host robots-fenced - see metno note); **Vector outages**
    (its ArcGIS Hub `data-vector.opendata.arcgis.com` has *zero* outage datasets - the live map uses a
    bundled/private feed = would be hoard, not trove); **Safeswim** (beach water quality - ideal genre,
    but the live feed is hidden in Next.js chunks behind `maps.safeswim.org.nz`, 404 on every probed
    path; heavy RE, possibly private - parked). **GeoNet felt-intensity** (`/intensity?type=reported`)
    works keyless but was rejected as a poor model fit: it's an aggregated MMI heatmap with **no stable
    join key** (grid points shift), unlike volcano/quake by-id.
- **spaceweather gate (2026-07-02, NOAA SWPC space weather - invented, new domain):**
  `services.swpc.noaa.gov` has **no robots.txt (404 = unfenced)** and serves keyless, official NOAA
  product JSON = sanctioned -> trove. Opened a brand-new domain (space weather / aurora) that no
  existing genre covered; filed under weather/environment. Used
  `products/noaa-planetary-k-index-forecast.json` (a flat list of `{time_tag, kp, observed, noaa_scale}`
  3-hourly rows spanning ~10 past observed + 3 predicted days) over the sibling `noaa-scales.json`
  (whose G/R/S storm scales sit at 0 most days = little signal). Model = the **metno forecast-drift
  pattern**: aggregate per UTC date, join key = `YYYY-MM-DD`, `price_cents` = that day's **peak Kp** *
  100 (centi-Kp) so core `drops` = a day's peak forecast revised *down* (storm calming), `qty` = count
  of 3-hour periods at Kp>=5; is_deal "aurora" = peak Kp>=5 (geomagnetic storm, aurora australis
  threshold for southern NZ). The stable date key with a shifting target is what makes the obs log the
  **un-rebuildable as-issued forecast series** (SWPC archives realized Kp, not the revision history).
  Key findings: (1) the JSON's first element is real data, **not** a header row (unlike some SWPC CSV
  products) - iterate all rows. (2) times are **UTC** (no tz), so a "date" is a UTC calendar day -
  honest for the drift hoard, documented like metno. (3) most days are quiet (peak Kp 2-4, 0 storm
  periods); the hoard's whole point is catching the rare escalation (build day had 2026-07-03 forecast
  at peak Kp 6.0 / G2 = a live aurora deal). money() renders centi-Kp as $ in the 2 hardcoded spots
  (geonet/metno/volcano precedent).
- **metno gate (2026-06-27, weather forecast-drift - "something different"):** picked deliberately
  off-genre - everything else in trove hoards a *present-state* value (price/seats/fuel/magnitude);
  this hoards a **prediction about the future and its revision**. First pick **Open-Meteo** was
  **skipped**: `open-meteo.com` robots is `Allow: /` but the data host **`api.open-meteo.com` robots is
  `Disallow: /`** - the exact endpoint fenced, same shape as the CheapShark skip (keyless+documented but
  robots-fenced data path). Re-rolled to **MET Norway** (api.met.no, the backend behind the yr.no
  consumer weather site): `api.met.no/robots.txt` `Disallow: /weatherapi/*` applies **only to
  Googlebot** (anti-index); for `User-agent: *` the path is fully allowed. Keyless, global, CC-BY 4.0 /
  NLOD, official = sanctioned -> trove. Gate is just an **identifying User-Agent** (generic UAs get
  403; MET's ToS requires app+contact) + respect the `Expires` header. `yr.no` robots `Disallow: /`s a
  list of AI-*training* crawlers (ClaudeBot/GPTBot/CCBot/...) - the ygoprodeck lesson: that's not a ban
  on a personal API client with an honest UA doing no training/redistribution; posture honoured, not
  impersonated. Key findings: (1) `GET /weatherapi/locationforecast/2.0/compact?lat=&lon=` returns
  `properties.meta.updated_at` (the **forecast-run time** = the drift anchor) + `.units` +
  `.timeseries[]` (`instant.details.air_temperature/wind_speed/...` + `next_1_hours/6_hours/12_hours`
  with `summary.symbol_code` + `details.precipitation_amount`). (2) Scalar reuse like geonet:
  `price_cents` = upcoming-day **high** in centi-degrees C (so `drops` = a forecast that *cooled*),
  `qty` = that day's rain in tenths-mm, is_deal "fineday" = high>=20C & <1mm. Every obs stamps
  `target_date`+`issued`, so the forecast-evolution series is fully in the hoard and **un-rebuildable**
  elsewhere = genuine high value. (3) No place-name lookup in the API (and the obvious geocoder host
  `api.open-meteo.com` is robots-fenced), so discovery rides a **curated city list** (slug or
  arbitrary `lat,lon`); the id is used verbatim as the join key so the watch key always matches the
  stored item. (4) Cosmetic quirk inherited from the scalar reuse: `money()` renders the centi-degree
  high as dollars in the two core-hardcoded spots (watch-list + poll DROP line) - same as geonet's
  `$3.11` magnitude; the rich displays show proper `C`. (5) Times are **UTC** (no tz in payload) so
  "upcoming day" + the midday symbol are UTC-defined - an NZ winter high can carry a `_night` symbol;
  honest and harmless for the drift hoard.
- **geonet gate (2026-06-27, NZ earthquakes - the DS-friendly ask):** `api.geonet.org.nz` robots
  disallows only marketing paths (`/p/ /news/ /assets/ /network/`) - never `/quake`. GeoNet is the
  official GNS Science / Toka Tu Ake EQC network and ships a keyless, documented, CC-BY 3.0 NZ GeoJSON
  API = sanctioned -> trove. `GET /quake?MMI=<n>` returns the recent feed (<=100) at/above a Modified
  Mercalli Intensity floor; `GET /quake/{publicID}` is a clean *by-id* endpoint (no composite key needed,
  unlike turners/grabone). Accept header is `application/vnd.geo+json;version=2`. Key findings: (1) the
  scalar mapping reuses `price_cents` = round(magnitude * 100) (centi-magnitude, em6/petrolspy pattern)
  and `qty` = MMI, so the `drops` command = a quake *downgraded* on review (preliminary over-estimate
  corrected down - a real DS signal); is_deal = M>=4.0 ("notable"). (2) The ephemeral angle is the
  **preliminary -> reviewed `quality` drift** (`best`/`preliminary` -> `reviewed`, or `deleted` as a
  false trigger) - the single `/quake/{id}` always returns the *current* solution, so polling builds our
  own cross-quake magnitude/quality series. Honest hoard value is **low-med**: GeoNet archives both the
  catalogue and `/quake/history/{id}`, so the revisions are rebuildable - this source's draw is the
  data-science fit (the user's explicit ask) and the convenient unified series, not un-rebuildability.
  (3) `/volcano/val` (current volcanic alert levels) and `/intensity?type=reported` (live felt reports,
  genuinely ephemeral) are sibling keyless feeds left for a future extension; kept the source thin on the
  one clean dimension (quakes).


- **chcflights gate (2026-06-27, NZ aviation - "a new category, ideally nz specific"):** opened a
  genuinely new genre (aviation - none of the four existing genres covers transport). Airport gate
  sweep: **Auckland** sits behind a **Cloudflare "Just a moment..." JS challenge on every request**
  incl. `/robots.txt` (interactive anti-bot wall = edge fence, same skip class as the Noel Leeming
  WAF / DOC TLS refusal) -> **skip**; **Wellington** robots `Disallow: /flights/arrivals/` +
  `/flights/departures/` (the exact data paths fenced) -> **skip**; **Christchurch** robots is wide
  open (`User-agent: *`, only a Sitemap line, zero Disallow) -> proceed. The CHC arrivals/departures
  board (`/travellers/flights/arrivals-and-departures/`) is a Vue widget; grepping its `main-*.js`
  bundle for the call site gave `buildUrl: "/api/flights?maxFlights=&flightDirection=&flightType="`
  - a keyless, same-origin, page-called JSON endpoint = sanctioned -> **trove**. Key findings: (1)
  the **param values are words, not codes**: `flightDirection=Arrive|Depart`, `flightType=
  International|Domestic` (read from the page's `data-flight-direction="Arrive"` attrs + the radio
  `value="International"`). First probe with `A`/`I` returned 200 but the *default* board (arrivals
  and departures looked identical) - the server silently falls back on an unrecognised value, the
  tell that the params were wrong. (2) flight objects carry **no direction/type field** (so the
  server *must* filter by quadrant) and **no by-flight endpoint**, so the join key is composite
  `dir|type|flightNo|scheduled` (eventcinemas/turners trick) - the stable `scheduled` string
  disambiguates a recurring flight number and lets fetch/poll rebuild the query. (3) **no price in
  aviation** -> tracked scalar = *delay minutes* (`estimate - scheduled`, signed, wrapped ±12h; `0`
  when no estimate = expected on time) in `price_cents`, so the core's `drops` = a flight that
  *recovered*; is_deal "delay" = delayed ≥15 min or cancelled. money() cosmetically renders the delay
  as dollars in the 2 core-hardcoded spots (geonet/metno precedent). (4) `scheduled`/`estimateActual`
  are clock strings with a weekday prefix (`"Sat 7:24 PM"`) and **no date/tz** - parse time-of-day
  only and wrap the diff; the board only spans ~a day so this is safe. Lift image + codeshares
  (`flightNumbers[1:]`) ride in extra.
- **The hoard only compounds if `poll` runs on a schedule** — which is exactly the gate
  `/daily-tool-drop` won't cross without a fresh explicit OK. Arming polite scheduled polling per
  source is a conscious, per-source decision (Luke approves).
- **`export` ships the hoard** to other tools as CSV (`python trove.py <source> export`); schema in
  `DATA_DICTIONARY.md`.
- **pokemontcg gate (2026-06-23):** `api.pokemontcg.io/robots.txt` empty; marketing-site robots is
  Cloudflare content-signal *vocabulary* only (no `no`, no `/api` Disallow). Sanctioned keyless API.
  Lesson: Cardmarket `lowPrice` is a damaged-copy outlier; use `lowPriceExPlus` as the clean EUR floor.
- **eventcinemas gate (2026-06-24, NZ cinema seats):** `eventcinemas.co.nz` robots disallows only
  `/ticketing/` + `/tickets/` (the seat-picker/checkout flow) - **not** the session listing. The site
  is a legacy jQuery/.NET app; its "session times" view calls a keyless, page-called JSON endpoint
  `GET /Cinemas/GetSessions?cinemaIds=<id>&date=<YYYY-MM-DD>` (found by grepping the `site-*.js` bundle
  for the `EVO.sessions.getSessions` AJAX url) returning every movie -> `CinemaModels` -> `Sessions`
  for that day, each session carrying a live **`SeatsAvailable`** count. Keyless + page-called +
  not-fenced = sanctioned -> **trove**. Key findings: (1) **no price in the feed** (ticket prices live
  behind the fenced `/ticketing/` flow) - so this is a pure *scarcity* tracker: `qty` = seats
  remaining, "deal" = a session near sellout (<= 20 seats). Mirrors bookme. (2) GetSessions is keyed
  by cinema+date with no by-session-id endpoint, so the **join key is composite** `cinemaId:date:
  sessionId` (turners/grabone trick) - fetch/poll rebuild the query from the id. (3) `--cc <id>` picks
  the cinema (default 502 = Queen Street, Auckland), `search --date` picks the day; cinema ids come
  from the response itself (`CinemaModels[].Id/Name`). The `_Client` memoizes per (cinema,date) so a
  multi-session poll of one day is a single GET.
- **DOC bookings (Great Walks hut/campsite availability)** `[skipped] 2026-06-24` -
  `booking.doc.govt.nz` **rejects the TLS handshake itself** (`SSLV3_ALERT_HANDSHAKE_FAILURE` on both
  TLS 1.2 and 1.3, across openssl/curl/Python, while `www.doc.govt.nz` fetches fine) = a
  TLS-fingerprint (JA3) WAF deliberately refusing non-browser clients at the transport layer. Reading
  it would need browser-TLS impersonation (curl_cffi/uTLS) = detection-evasion of an anti-bot control,
  off-brand. Same call as the Noel Leeming WAF. Hard skip. (New abstracted skip pattern: a host that
  *refuses the TLS handshake* for non-browser clients is an edge fence, even with no robots/HTTP block.)
- **ChargeNet NZ (EV-charger availability)** `[skipped] 2026-06-24` - `map.charge.net.nz` (Vite/React
  SPA, no robots fence) calls a keyless JSON API `https://api.charge.net.nz/v1/sites` (base host built
  in-bundle as `window.location.hostname` with the first label swapped to `api`). But the endpoint's
  **entire universe is 3 placeholder sites** (all `UnderConstruction`/`Planned`, owner "Firstlight
  Network Ltd"): unfiltered = 3, and `?status=<SiteStatus>` only narrows (a no-op once the enum value
  is valid; the param binds a single `Optional<SiteStatus>` by enum NAME, so a CSV or a non-member
  400s). The real ~300-charger network is baked into **Mapbox vector tiles** (`mapbox://tiles/`) with
  live status over an **SSE stream** (`/v1/sites/{id}/chargers/outlets/stream`) - neither is a clean
  list-and-track JSON source. Shipping it would be a 3-site stub. Skip. (Lesson: confirm the keyless
  JSON endpoint actually *holds the bulk data* before building - a map's pins can live in a tileset,
  not the API.)
- **InterCity coach fares** `[skipped] 2026-06-24` - `intercity.co.nz` robots `Disallow: /book/`, and
  the fare-search/booking data lives exactly under `/book/`. The skill's "robots fences the data path
  you'd hit" skip trigger. Skip rather than push a fenced booking path.
- **turners gate (2026-06-24, NZ used cars):** `turners.co.nz` robots is `User-agent: * / Allow: /`
  (only a sitemap line) - no `/api` or search fence, no automation ban. The cars listing is an
  EPiServer/Optimizely page behind an F5/BIG-IP edge, but the result grid is **server-rendered**: each
  `<div class="product-block block-type-(buy-now|live-auction)" data-goodnumber="...">` carries
  schema.org/Car microdata + an `analytics-seg-info` span with
  `data-seg-{goodNumber,make,model,year,price,isDiscounted,responsibleBranch,salesChannel}`, plus a
  visible "Was $X / You Save $Y" and an odometer. **Page-parse = sanctioned -> trove**, no private call.
  Key findings: (1) the same `analytics-seg-info` span + schema.org itemprops appear on **both** the
  listing card and the single-car detail page, so one extractor serves both - the detail page even adds
  `data-seg-salesChannel="BuyNow"` as the clean auction/buy-now flag. (2) There is **no by-id endpoint**:
  `/-/-/<goodnumber>` soft-404s ("Page Not Found"); the real detail URL needs the make/model slug, so
  the **join key is the detail path tail** `make/model/goodnumber` (grabone's pattern) and `fetch` GETs
  `/Cars/Used-Cars-for-Sale/{id}` directly. (3) `?pagesize=110` returns 110 cards in one polite GET;
  keyword query params (`keyword=/searchfor=/q=`) are **ignored**, so `search` filters client-side
  (make-path first, fall back to the latest 110). (4) Detail-page odometer must be read from the
  `itemprop="mileageFromOdometer" ... content="196500"` microdata - a loose `N km` text scan grabs a
  fuel-economy figure instead. is_deal = discounted below RRP (`isDiscounted=True` and was>price).
- **petrolspy gate (2026-06-23, NZ fuel - fills the Gaspy gap):** `petrolspy.com.au` (covers AU+NZ)
  robots disallows only `/admin-1/`. The web map calls a keyless service
  `webservice-1/station/box?neLat=&neLng=&swLat=&swLng=` (gzipped; needs `--compressed`/Accept-Encoding)
  returning every station in the box with `{name, brand, suburb, address, location{x:lng,y:lat},
  country, prices:{GRADE:{amount(cents/L), updated(epoch ms), relevant}}}`. Keyless + robots-allowed +
  page-called = sanctioned -> trove. Scoped to NZ city bounding boxes (auckland/wellington/christchurch)
  so it tracks NZ forecourt prices - the gap Gaspy left (app-only, Firebase-leak skip). NZ twin of
  spainfuel. By-id endpoint is dead, so fetch scans the city boxes; the client memoizes each box so a
  whole poll is <=1 GET per box. Caveat: crowd-sourced, freshness varies per grade (`updated`/`relevant`
  surfaced).
- **Designer Wardrobe** `[skipped] 2026-06-23` — NZ second-hand fashion marketplace (Nuxt + Laravel).
  Empty robots, but the listings aren't a clean page-parse: the `apiBaseUrl=/api` backend is Laravel and
  key routes are auth-gated (`/api/feed` -> 401 invalid-auth-header = reverse-engineered private =
  hoard, not trove), and the `__NUXT__` SSR state is minified with hoisted value-refs (`price_nzd` values
  aren't literal) - too fragile for a thin source. Confirms the "NZ retail is fenced" lesson extends to
  NZ marketplaces (gated/auth'd). Revisit only as a hoard source if the listings API turns out keyless.
- **bookme gate (2026-06-23, NZ activity deals):** `bookme.co.nz` has no robots.txt (404), older
  jQuery-era SSR site (`/things-to-do/<region>`). No JSON/JSON-LD - the deals are in the page HTML
  as `dealCard` blocks (page-parse = sanctioned = trove). Each `<div activity-ref="/things-to-do/
  <region>/activity/<slug>/<id>" class="dealCard ">` carries h3 name, `$NNN<sup>cc</sup>` from-price,
  `N% Off`, `hd_dealSpaces` (spaces remaining = a scarcity time-series, stored as Obs.qty), deal
  window, and `Save up to $X`. The activity-ref path encodes the region so one card-parser serves
  both search and fetch. Distinct from grabone: tracks *spaces remaining* ticking down, not just
  price.
- **TAB NZ (api.tab.co.nz affiliates) `[assessed, deferred 2026-06-23]`** — robots only fences
  `/*?s=`; `api.tab.co.nz/affiliates/v1/racing/meetings` returns 200 keyless (a *sanctioned*
  affiliates API). But the content is **global racing** (meetings[0] = Munich DEU), the model is
  3-level nested (meetings->races->runners, odds on a separate call), entities resolve within hours,
  and it's a gambling source on a public repo - weak on the "NZ-specific" ask and off-brand for
  public trove. Park: revisit as a *hoard* odds-drift hoard (opening->closing line) if Luke wants it.
- **grabaseat gate (2026-06-23, Air NZ cheap fares):** `grabaseat.co.nz` robots `allow: /` (only a
  sitemap line), CloudFront-fronted React app (gas001 theme). Deals aren't embedded in the homepage;
  the fare-finder bundle (`lowFareFinder.js`) calls a keyless same-origin endpoint
  `https://www.grabaseat.co.nz/api/v3/lowfarefinder/{ORIGIN}/{DEST}` -> `{lowestPrice, lowFares:[{farePrice,
  outboundDate, bookUrl}]}` (cheapest fare per day for ~30 days). Page-called + robots-allowed =
  **sanctioned -> trove**. Lesson: a React deals grid with no embedded JSON usually means the data is
  a client-side fetch - grep the *named* bundle (lowFareFinder.js), not the loader stub (dealList.js),
  for the path. Endpoint is per-route (no list-all), so the route is the explicit join key.
- **grabone gate (2026-06-23, NZ daily deals):** `grabone.co.nz` 302s to the `new.grabone.co.nz`
  Next.js rebuild; its robots `Allow: /` with only `/cms /dev /admin` (and the old host's `/my-stuff
  /buy /gocount.php`) disallowed - none fence the browse data. Key finding: the deal data is in the
  page's own `application/ld+json` (CollectionPage -> ItemList of Product on a region listing; a
  Product on each deal page) = **page-parse = sanctioned = trove**, no private call. Field split to
  remember: the *listing* ld+json carries the RRP/strikethrough (priceSpecification StrikethroughPrice)
  but no expiry; the *detail* ld+json carries validFrom/validThrough + seller location but **no**
  strikethrough. So `search` (listing) captures price+RRP+discount, `item`/`poll` (detail) capture
  price+expiry+availability; is_deal = live-and-grabbable (in stock, not past validThrough), discount
  shown as enrichment. Short `/p/<slug>` URLs 404 - the full category path is the join key.
- **em6 gate (2026-06-23, NZ electricity spot):** `www.em6.co.nz` robots empty → 302 to the
  `app.em6.co.nz` React SPA (no robots fence). The SPA's bundle calls
  `https://api.em6.co.nz/ords/em6/data_api` (Oracle ORDS) and bundles AWS Cognito (user pool
  `ap-southeast-2_Zo8h88J4v`). Key finding: em6 ships a **deliberately-public keyless tier** — the
  page-called endpoints `/region/price/`, `/price`, `/price/free_24hrs` answer 200 with no token,
  while `/demand`, `/generation`, raw `/nodes` are 401/403 behind the Cognito login. Used only the
  keyless public tier (sanctioned = page-called) → trove, not the gated endpoints. Lesson: an
  endpoint literally named `free_24hrs` next to a Cognito wall is the vendor signposting its public
  vs members tier — take the free tier, leave the walled one.
- **ygoprodeck gate (2026-06-23):** `db.ygoprodeck.com` → `User-agent: * / Allow: /` (no `/api`
  Disallow) + content-signals `search=yes,ai-train=no` + per-UA blocks on AI-training crawlers
  (ClaudeBot, GPTBot...). Passes both skip triggers by the letter; proceeded as a personal API client
  with an honest UA, no training/redistribution. Lesson: cross-marketplace prices mix currencies +
  resale noise — only TCGplayer-vs-CoolStuffInc is an honest arbitrage signal.
- **steammarket gate (2026-07-02, Steam Community Market — invented, Active queue was thin):**
  `steamcommunity.com/robots.txt` for `User-agent: *` disallows only `/actions/ /linkfilter/
  /tradeoffer/ /trade/ /email/` — **`/market/` is open** (the trade-offer flow is fenced, not the
  market data). Both endpoints the market page itself calls are keyless 200: `/market/search/render/
  ?query=&appid=&norender=1` (discovery: `sell_price` integer cents, `sell_listings` depth,
  `hash_name`) and `/market/priceoverview/?appid=&market_hash_name=&currency=` (per item:
  `lowest_price`/`median_price` **text**, `volume`). Page-called + keyless + `/market` unfenced =
  sanctioned -> trove. Key findings: (1) **search render is USD-only without auth** — it silently
  ignores `&currency=22`, so `--cc` (a Steam currency *integer*, 22=NZD) localises priceoverview
  only; default `--cc 1` (USD) keeps search and item/poll in one currency for a clean series. (2) the
  two endpoints carry different secondary metrics, so they share the obs log via `flags.src` (grabone
  precedent): `search` rows log `qty`=listing depth, `item`/`poll` rows log `qty`=24h volume +
  `flags.median_cents`. (3) no by-id endpoint and hash names repeat across games, so the join key is
  composite `appid:market_hash_name` (split on the first `:`; appid is the numeric prefix). is_deal
  "cheap" = lowest ask below the 24h median. Honest hoard value **low-med**: third-party sites
  (pricempire/csgobackpack) archive median prices, so the draw is the live depth/volume snapshot +
  completing the marketplace set (fungible-goods complement to reverb/discogs), not un-rebuildability.
