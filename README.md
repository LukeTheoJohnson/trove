# trove

Search, watch, and poll data over time for price drops and source-specific signals. Every fetch writes a timestamped row to a local SQLite cache.
The cache is the product: trove is a hoarding engine for proprietary, un-rebuildable time-series, and `export` hands the whole thing
to your other tools as CSV (schema in [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md)).

## Quick start with any source

Every source uses the **same eight commands**

```bash
python trove.py <source> doctor          # is the API reachable? (no args)
python trove.py <source> search <query>  # find items — the LEFT COLUMN is the ID
python trove.py <source> item <id>       # full detail for one item
python trove.py <source> watch add <id>  # start tracking it
python trove.py <source> poll            # re-check watched items, log history, flag drops/deals
python trove.py <source> deals           # watched items that are "good" right now
python trove.py <source> drops           # watched items now lower than first seen
python trove.py <source> export          # dump the cached time-series to CSV
```

 The only
things that vary per source are the **ID format** and whether `search` is free-text or a fixed list:

- **Free-text**:pass a real query — `steam search "elden ring"`.
- **Fixed list** (nzski): the source already knows its set; pass `""` to list them all, or a word to filter — `search ""`.

`python trove.py <source> -h` lists its commands and any extra flags
(`--cc`, `--limit`, `itunes search --entity album`, `eventcinemas --cc 502`). 

## Sources

23 sources in five genres (the same grouping `python trove.py` prints):

### games / media / collectibles
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| steam   | appid               | game price + discount %                | keyless Storefront API       |
| discogs | release id          | marketplace lowest price + num for sale | keyless official API         |
| itunes  | trackId/collectionId| app/album/song price + going free      | keyless official Search API  |
| scryfall| card id             | MTG single price (usd/eur/tix) + foil deal | keyless official API     |
| pokemontcg| card id           | Pokemon single market price (usd/eur) + under-market deal | keyless official API |
| ygoprodeck| card id (passcode) | Yu-Gi-Oh single price per venue + retailer arbitrage | keyless official API |
| epic    | offer id            | free-game rotation: RRP -> Free window + which titles given away | keyless store backend |

### fuel & electricity
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| spainfuel | province-IDEESS     | per-station petrol price (G95E5) + below-area-avg deal | keyless MINETUR open-data REST |
| petrolspy| station id          | NZ per-station fuel price (U91) + below-box-avg deal | keyless PetrolSpy map API |
| em6     | grid_zone_id        | NZ wholesale electricity spot ($/MWh) + below-NZ-avg deal | keyless em6 public tier |
| octopus | GSP group (A-P)     | UK Agile Octopus half-hourly unit rate (p/kWh) + cheap-window/plunge deal | keyless official Octopus API |

### deals, fares & listings
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| grabone | deal URL path       | NZ daily-deal price + RRP/discount + live-until-expiry | page-published JSON-LD |
| grabaseat| ORIGIN-DEST route   | Air NZ cheapest fare per route + standout-dip deal | keyless grabaseat fare API |
| bookme  | activity URL path   | NZ activity deal price + spaces-remaining + steep-discount deal | SSR page-parse |
| turners | car detail path     | NZ used-car asking price + RRP/discount over a listing's life | page-published microdata |
| eventcinemas | cinemaId:date:sessionId | NZ cinema session seats-remaining ticking down to showtime (scarcity) | keyless GetSessions JSON |
| reverb  | listing id          | used-gear marketplace ask price + seller markdown over a listing's life (then it sells and vanishes); deal = on-sale | keyless official Reverb API |

### weather, environment & geohazard
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| geonet  | publicID            | NZ earthquake magnitude + preliminary-to-reviewed quality drift (downgrade signal) | keyless GeoNet GeoJSON API |
| metno   | city slug or lat,lon | weather forecast-drift: upcoming-day high + rain, as-issued (un-rebuildable) | keyless MET Norway Locationforecast |
| volcano | volcanoID           | NZ volcanic alert level (0-5) + unrest escalation | keyless GeoNet VAL API |
| nzski   | resort data-slug    | NZ ski-field base depth + lifts/trails open (open = deal) | page-called NZSki feed |
| gwrivers| gauge site name     | NZ river flow/level + flood-onset rise (1.5x in 24h) | keyless GW Hilltop XML |

### aviation
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| chcflights | dir:type:flightNo:scheduled | Christchurch Airport flight delay-drift (estimate vs schedule) + gate/status churn; deal = delayed/cancelled | keyless christchurchairport.co.nz /api/flights JSON |

Every source runs the same commands: `doctor search item watch poll deals drops export`, plus a few
source-specific search flags (e.g. `itunes search --entity album`).

## Architecture
Pure stdlib plus `requests` (`pip install -r requirements.txt`). No API keys for the bundled sources.

```
trove.py            entrypoint:  python trove.py <source> <command> [args]
trove/
  session.py        retry_session() - shared backoff HTTP session
  db.py             TrackerDB + Item/Obs - the stateful spine (items, timestamped obs, watch)
  tracker.py        Source contract + run_cli (the generic command set lives here, once)
sources/
  steam.py          ~90 lines: endpoints + normalise payload -> Item/Obs + deal semantics
  discogs.py
  itunes.py
  scryfall.py
```

The core owns everything that is stateful and generic: caching, the timestamped observation log, the
watchlist, drop detection, deal transitions. A source owns only what is unique to it: the endpoints,
how to flatten the payload into `Item`/`Obs`, and what "a deal" means.

## Adding a source (~50 lines)

Create `sources/<name>.py` with a `Source` subclass and `SOURCE = <Class>()`:

```python
class FooSource(Source):
    name = "foo"; id_label = "ID"; deal_label = "sale"
    def client(self, args):       ...   # build an API client
    def doctor(self, cl):         return ok, "detail"
    def search(self, cl, term, args) -> list[tuple[Item, Obs|None]]: ...
    def fetch(self, cl, item_id)  -> tuple[Item, Obs] | None: ...   # rich lookup
    def is_deal(self, obs)        -> bool: ...                      # source's "deal" rule
    def deal_line(self, item, obs)-> str: ...
SOURCE = FooSource()
```

Add the name to `SOURCES` in `trove.py`. The whole `doctor/search/item/watch/poll/deals/drops/export`
command set comes for free. Optionally override `refresh()` for a leaner poll endpoint (discogs does
this: rich `/releases` for `item`, lean `/marketplace/stats` for `poll`).

## Etiquette

For personal use only. The bundled sources only hit sanctioned, keyless APIs that the page or app itself calls.
`poll` spaces its requests, the `User-Agent` is real and descriptive, and the cached data stays
local. Please respect the terms of service and `robots.txt` of each source.

## License

MIT (see `LICENSE`). The license covers the code.
