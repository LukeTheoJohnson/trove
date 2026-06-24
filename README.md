# trove

A personal price and listing tracker across several sources, built on one shared core with thin
per-source drivers. Search, watch, and poll any source over time for price drops and source-specific
deal signals. Every fetch writes a timestamped row to a local SQLite cache, so the longer it runs the
more it knows.

Reading today's price is easy; anyone can do that. The point is that trove started caching three
months ago, so it can tell you today's price is actually a bad one. The cache is the product: trove
is a hoarding engine for proprietary, un-rebuildable time-series, and `export` hands the whole thing
to your other tools as CSV (schema in [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md)).

```bash
python trove.py steam   search "elden ring"
python trove.py discogs item 249504
python trove.py itunes  watch add 1713845538
python trove.py steam   poll        # log prices, report DROPs + sales
python trove.py steam   deals        # on-sale now
python trove.py steam   drops        # cheaper than first seen
python trove.py steam   export       # dump the cached time-series to CSV (see DATA_DICTIONARY.md)
```

Pure stdlib plus `requests` (`pip install -r requirements.txt`). No API keys for the bundled
sources. State lives in `data/<source>.db`, one file per source.

## Sources

| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| steam   | appid               | game price + discount %                | keyless Storefront API       |
| discogs | release id          | marketplace lowest price + num for sale | keyless official API         |
| itunes  | trackId/collectionId| app/album/song price + going free      | keyless official Search API  |
| scryfall| card id             | MTG single price (usd/eur/tix) + foil deal | keyless official API     |
| pokemontcg| card id           | Pokemon single market price (usd/eur) + under-market deal | keyless official API |
| ygoprodeck| card id (passcode) | Yu-Gi-Oh single price per venue + retailer arbitrage | keyless official API |
| spainfuel | province-IDEESS     | per-station petrol price (G95E5) + below-area-avg deal | keyless MINETUR open-data REST |
| em6     | grid_zone_id        | NZ wholesale electricity spot ($/MWh) + below-NZ-avg deal | keyless em6 public tier |
| grabone | deal URL path       | NZ daily-deal price + RRP/discount + live-until-expiry | page-published JSON-LD |
| grabaseat| ORIGIN-DEST route   | Air NZ cheapest fare per route + standout-dip deal | keyless grabaseat fare API |
| bookme  | activity URL path   | NZ activity deal price + spaces-remaining + steep-discount deal | SSR page-parse |
| petrolspy| station id          | NZ per-station fuel price (U91) + below-box-avg deal | keyless PetrolSpy map API |
| turners | car detail path     | NZ used-car asking price + RRP/discount over a listing's life | page-published microdata |

Every source runs the same commands: `doctor search item watch poll deals drops export`, plus a few
source-specific search flags (e.g. `itunes search --entity album`).

## Architecture

```
trove.py            entrypoint:  python trove.py <source> <command> [args]
trove/
  session.py        retry_session() - shared backoff HTTP session
  db.py             TrackerDB + Item/Obs - the stateful spine (items, timestamped obs, watch)
  tracker.py        Source contract + run_cli (the generic command set lives here, once)
sources/
  steam.py          ~90 lines: endpoints + normalize payload -> Item/Obs + deal semantics
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

## Scope and etiquette

Personal use. The bundled sources hit sanctioned, keyless APIs that the page or app itself calls.
`poll` spaces its requests, the `User-Agent` is real and descriptive, and the cached data stays
local. Respect each source's terms of service and `robots.txt`. Any keys come from env vars, never
hardcoded.

## License

MIT (see `LICENSE`). The license covers the code. The "data stays local" note above is about the
cached price observations, not the source.
