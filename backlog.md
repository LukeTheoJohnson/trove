# trove — tool-drop backlog

Targets for the `/daily-tool-drop` routine. Each run picks the top unused candidate from the Active
queue, gates it (robots + sanctioned-first), and — if it passes — adds a thin `sources/<name>.py`
driver to this repo. Genre filter: **data trapped behind a consumer UI + curl-able JSON + a join key
+ a reason to track it over time.**

## Ported sources

| source     | `sources/…`            | join key   | timeline value                              | path     |
|------------|------------------------|------------|---------------------------------------------|----------|
| steam      | `sources/steam.py`     | appid      | game price + discount %                      | keyless Storefront API |
| discogs    | `sources/discogs.py`   | release id | marketplace lowest price + num for sale      | keyless official API |
| itunes     | `sources/itunes.py`    | trackId    | app/album/song price + going free            | keyless official API |
| scryfall   | `sources/scryfall.py`  | card id    | MTG single price (usd/eur/tix) + foil deal   | keyless official API |
| pokemontcg | `sources/pokemontcg.py`| card id    | Pokemon single market price (usd/eur) + under-market deal | keyless official API (api.pokemontcg.io) |
| ygoprodeck | `sources/ygoprodeck.py`| card id    | Yu-Gi-Oh single price per venue + retailer arbitrage | keyless official API (db.ygoprodeck.com) |

## Active queue

- **CoinGecko** — crypto spot prices, keyless public API, join key = coin id, timeline = price.
  Sanctioned; more finance-API than trapped-behind-UI, but clean.
- **Epic Games Store free-games feed** — `store-site-backend-static.ak.epicgames.com/freeGamesPromotions`
  (the store page's own backend, keyless). Join key = game id, timeline = which games are free each
  week (deal = currently free). Gate Epic robots/ToS before recon.
- **Open Library** — book editions/metadata (`openlibrary.org`), join key = ISBN/OLID. Sanctioned,
  but weak timeline value (metadata rarely changes); only qualifies if a price/availability signal
  is found.
- **BoardGameGeek XML API** — board-game data, join key = thing id. Sanctioned XML API, but pricing
  isn't in the API — weak timeline value unless a marketplace endpoint surfaces.

## Skipped

- **CheapShark** `[skipped] 2026-06-23` — `cheapshark.com/robots.txt` has `Disallow: /api/1.0/`,
  fencing the exact data endpoint. Hard skip for an autonomous tool even though the API is keyless
  and documented (sanctioned-first only applies to an un-fenced path).

## Notes

- **pokemontcg gate (2026-06-23):** `api.pokemontcg.io/robots.txt` is empty (no Disallow). The
  marketing site `pokemontcg.io/robots.txt` carries only Cloudflare content-signal *vocabulary*
  boilerplate — no signal set to `no`, no `Disallow` on `/api`. Official keyless developer API →
  sanctioned-first, recon skipped. Lesson: Cardmarket `lowPrice` is a damaged-copy outlier; use
  `lowPriceExPlus` as the clean EUR floor (read the field, don't trust the obvious name).
- **ygoprodeck gate (2026-06-23):** `db.ygoprodeck.com/robots.txt` → `User-agent: * / Allow: /`
  (no `/api` Disallow) + Cloudflare content-signals `search=yes,ai-train=no`, plus per-UA blocks on
  AI-training crawlers (ClaudeBot, GPTBot, CCBot, Google-Extended...). Passes both skip triggers by
  the letter (no /api Disallow for `*`; vocabulary preamble, not a written access ban; `ai-train=no`
  doesn't apply to a price client that does no training). Proceeded as a personal API client with an
  honest UA, honoring the no-training/no-redistribution posture. Lesson: across-marketplace YGO
  prices mix currencies + resale noise (cardmarket EUR, amazon/ebay inflated) — the only honest
  arbitrage signal compares the two legit US singles retailers, TCGplayer vs CoolStuffInc.
