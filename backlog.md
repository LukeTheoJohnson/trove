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

Grouped by genre (same four sections as the `--help` listing and the data dictionary).

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

### deals, fares & listings
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| grabone    | `sources/grabone.py`   | deal URL path   | **ephemeral** (daily-deal catalog churn + RRP/discount, never archived) | **high** |
| grabaseat  | `sources/grabaseat.py` | ORIGIN-DEST     | **ephemeral** (per-route cheapest airfare, moves daily, never archived) | **high** |
| bookme     | `sources/bookme.py`    | activity path   | **ephemeral** (activity deal price + *spaces remaining* ticking down, never archived) | **high** |
| turners    | `sources/turners.py`   | car detail path | **ephemeral** (a used car's asking-price markdown history over its listing, then the listing vanishes when it sells) | **high** |
| eventcinemas | `sources/eventcinemas.py` | cinemaId:date:sessionId | **ephemeral** (a screening's seats-remaining fill-rate from on-sale to showtime, never archived; session vanishes after it plays) | **high** |
| reverb     | `sources/reverb.py`    | listing id      | **ephemeral** (a used-gear listing's ask + seller markdowns over its life, then it sells and vanishes; Reverb keeps no public per-listing price-history archive) | **high** |

### weather, environment & geohazard
| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| geonet     | `sources/geonet.py`    | publicID        | archived (GeoNet catalogue + `/quake/history` revisions) | low-med (DS capability flex) |
| metno      | `sources/metno.py`     | city slug or `lat,lon` | **ephemeral** (forecast-*as-issued*: the free tier archives past *actuals* but never past *forecasts*, so the forecast-drift series is un-rebuildable) | **high** |
| volcano    | `sources/volcano.py`   | volcanoID       | archived (GeoNet VAL bulletins) | low-med (NZ geohazard suite w/ geonet; clean state series) |
| nzski      | `sources/nzski.py`     | resort data-slug | **ephemeral** (daily base depth + lifts/trails/open-closed churn, overwritten through the day, gone at season end; never archived) | **high** |
| gwrivers   | `sources/gwrivers.py`  | gauge site name | **ephemeral** (5-min river flow/level telemetry; GW archives it but no convenient unified per-gauge series) | med-high (live flood watch) |

### aviation
| source     | `sources/…`              | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|--------------------------|------------|----------------------------------|-------------|
| chcflights | `sources/chcflights.py`  | dir:type:flightNo:scheduled | **ephemeral** (a flight's estimate/gate/status drift from schedule in the hours before it operates; the board drops it once it operates and no public archive keeps the minute-by-minute progression) | **high** |

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
6. **CoinGecko / crypto** `[LOW — PoC only]` — keyless, clean, but full price history is downloadable,
   so low hoard value. Build only as a breadth/PoC demo, not for the corpus.

## Skipped

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
