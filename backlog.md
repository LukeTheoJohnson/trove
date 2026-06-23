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

## Notes

- **The hoard only compounds if `poll` runs on a schedule** — which is exactly the gate
  `/daily-tool-drop` won't cross without a fresh explicit OK. Arming polite scheduled polling per
  source is a conscious, per-source decision (Luke approves).
- **`export` ships the hoard** to other tools as CSV (`python trove.py <source> export`); schema in
  `DATA_DICTIONARY.md`.
- **pokemontcg gate (2026-06-23):** `api.pokemontcg.io/robots.txt` empty; marketing-site robots is
  Cloudflare content-signal *vocabulary* only (no `no`, no `/api` Disallow). Sanctioned keyless API.
  Lesson: Cardmarket `lowPrice` is a damaged-copy outlier; use `lowPriceExPlus` as the clean EUR floor.
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
