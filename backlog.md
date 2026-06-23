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

## Active queue

- **CheapShark** — PC game deals aggregated across ~30 stores. Official keyless deals API
  (`cheapshark.com/api`), join key = `gameID`, timeline = cheapest price + `savings` %. Strong
  sanctioned fit; overlaps steam but aggregates many stores.
- **CoinGecko** — crypto spot prices, keyless public API, join key = coin id, timeline = price.
  Sanctioned; more finance-API than trapped-behind-UI, but clean.
- **Open Library** — book editions/metadata (`openlibrary.org`), join key = ISBN/OLID. Sanctioned,
  but weak timeline value (metadata rarely changes); only qualifies if a price/availability signal
  is found.
- **BoardGameGeek XML API** — board-game data, join key = thing id. Sanctioned XML API, but pricing
  isn't in the API — weak timeline value unless a marketplace endpoint surfaces.

## Skipped

_(none yet)_

## Notes

- **pokemontcg gate (2026-06-23):** `api.pokemontcg.io/robots.txt` is empty (no Disallow). The
  marketing site `pokemontcg.io/robots.txt` carries only Cloudflare content-signal *vocabulary*
  boilerplate — no signal set to `no`, no `Disallow` on `/api`. Official keyless developer API →
  sanctioned-first, recon skipped. Lesson: Cardmarket `lowPrice` is a damaged-copy outlier; use
  `lowPriceExPlus` as the clean EUR floor (read the field, don't trust the obvious name).
