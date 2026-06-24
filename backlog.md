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

| source     | `sources/…`            | join key   | ephemeral / archived elsewhere? | hoard value |
|------------|------------------------|------------|----------------------------------|-------------|
| steam      | `sources/steam.py`     | appid      | archived (SteamDB)               | low (PoC) |
| discogs    | `sources/discogs.py`   | release id | **ephemeral** (live listing count + lowest ask, never archived) | **high** |
| itunes     | `sources/itunes.py`    | trackId    | free/price events not archived   | medium |
| scryfall   | `sources/scryfall.py`  | card id    | archived (MTGGoldfish)           | low (PoC) |
| pokemontcg | `sources/pokemontcg.py`| card id    | archived (prices.pokemontcg.io)  | low (PoC) |
| ygoprodeck | `sources/ygoprodeck.py`| card id    | no public cross-venue series      | medium |
| spainfuel  | `sources/spainfuel.py` | province-IDEESS | **ephemeral** (per-station forecourt price, never archived) | **high** |
| em6        | `sources/em6.py`       | grid_zone_id    | **ephemeral** (half-hourly NZ electricity spot, no easy public archive) | **high** |
| grabone    | `sources/grabone.py`   | deal URL path   | **ephemeral** (daily-deal catalog churn + RRP/discount, never archived) | **high** |
| grabaseat  | `sources/grabaseat.py` | ORIGIN-DEST     | **ephemeral** (per-route cheapest airfare, moves daily, never archived) | **high** |
| bookme     | `sources/bookme.py`    | activity path   | **ephemeral** (activity deal price + *spaces remaining* ticking down, never archived) | **high** |
| petrolspy  | `sources/petrolspy.py` | station id      | **ephemeral** (NZ per-station forecourt fuel price, never archived) | **high** |
| turners    | `sources/turners.py`   | car detail path | **ephemeral** (a used car's asking-price markdown history over its listing, then the listing vanishes when it sells) | **high** |

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
3. **Octopus Energy Agile tariff** `[HIGH]` — keyless public API of half-hourly unit rates; ephemeral
   pricing that decays. Join key = tariff/region, timeline = the rate series. (NZ sibling already
   shipped 2026-06-23: `em6` half-hourly wholesale spot — see Ported. Octopus is the UK *retail*
   tariff cut of the same genre.)
4. **Epic Games free-games rotation** `[MED-HIGH]` — `store-site-backend-static.ak.epicgames.com/freeGamesPromotions`
   (the store's own backend, keyless). The weekly free-game rotation is ephemeral and barely archived.
   Deal = currently free. Gate Epic robots/ToS before recon.
5. **A pure listings source** `[HIGH]` — deepen discogs to capture marketplace *inventory churn*, or
   find another marketplace with a keyless listings endpoint. Listings are the canonical ephemeral hoard.
6. **CoinGecko / crypto** `[LOW — PoC only]` — keyless, clean, but full price history is downloadable,
   so low hoard value. Build only as a breadth/PoC demo, not for the corpus.

## Skipped

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

- **The hoard only compounds if `poll` runs on a schedule** — which is exactly the gate
  `/daily-tool-drop` won't cross without a fresh explicit OK. Arming polite scheduled polling per
  source is a conscious, per-source decision (Luke approves).
- **`export` ships the hoard** to other tools as CSV (`python trove.py <source> export`); schema in
  `DATA_DICTIONARY.md`.
- **pokemontcg gate (2026-06-23):** `api.pokemontcg.io/robots.txt` empty; marketing-site robots is
  Cloudflare content-signal *vocabulary* only (no `no`, no `/api` Disallow). Sanctioned keyless API.
  Lesson: Cardmarket `lowPrice` is a damaged-copy outlier; use `lowPriceExPlus` as the clean EUR floor.
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
