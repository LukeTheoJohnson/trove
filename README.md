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

43 sources in nine genres (the same grouping `python trove.py` prints):

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
| steammarket | appid:market_hash_name | Steam Community Market lowest ask + listing depth + 24h volume; deal = below 24h median | keyless market backend |

### fuel & electricity
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| spainfuel | province-IDEESS     | per-station petrol price (G95E5) + below-area-avg deal | keyless MINETUR open-data REST |
| petrolspy| station id          | NZ per-station fuel price (U91) + below-box-avg deal | keyless PetrolSpy map API |
| em6     | grid_zone_id        | NZ wholesale electricity spot ($/MWh) + below-NZ-avg deal | keyless em6 public tier |
| octopus | GSP group (A-P)     | UK Agile Octopus half-hourly unit rate (p/kWh) + cheap-window/plunge deal | keyless official Octopus API |
| aemo    | NEM region (NSW1...)| AU National Electricity Market 5-min spot price ($/MWh) + demand + interconnector flows; deal = below the 5-region avg (or negative) | keyless AEMO visualisations API |
| fuelwatch | suburb:address    | WA per-station fuel price (ULP cents/L, legally fixed daily) + below-suburb-avg deal | keyless WA Govt FuelWatch RSS |

### currency & macro
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| frankfurter | BASE:QUOTE (e.g. NZD:USD) | ECB daily FX fixing — one `item` call seeds the full daily series since 1999 into the obs log; deal = base at/above the 90th percentile of its trailing year (a strong moment to convert) | keyless open-source Frankfurter/ECB API |

### deals, fares & listings
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| grabone | deal URL path       | NZ daily-deal price + RRP/discount + live-until-expiry | page-published JSON-LD |
| grabaseat| ORIGIN-DEST route   | Air NZ cheapest fare per route + standout-dip deal | keyless grabaseat fare API |
| bookme  | activity URL path   | NZ activity deal price + spaces-remaining + steep-discount deal | SSR page-parse |
| turners | car detail path     | NZ used-car asking price + RRP/discount over a listing's life | page-published microdata |
| eventcinemas | cinemaId:date:sessionId | NZ cinema session seats-remaining ticking down to showtime (scarcity) | keyless GetSessions JSON |
| reverb  | listing id          | used-gear marketplace ask price + seller markdown over a listing's life (then it sells and vanishes); deal = on-sale | keyless official Reverb API |

### attention & rank
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| hackernews | story id         | HN front-page rank/points trajectory (rank 27 -> 3 -> gone); deal = top-10 | keyless official HN Firebase API |
| appcharts | country:chart:appId | App Store top-chart rank rotation as published (history is paywalled commercially); deal = top-10 | keyless Apple marketing RSS |
| melbped | Melbourne sensor id | City of Melbourne live per-minute pedestrian footfall per street sensor; deal = busier than the current network median | keyless Melbourne Opendatasoft API |

### weather, environment & geohazard
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| geonet  | publicID            | NZ earthquake magnitude + preliminary-to-reviewed quality drift (downgrade signal) | keyless GeoNet GeoJSON API |
| metno   | city slug or lat,lon | weather forecast-drift: upcoming-day high + rain, as-issued (un-rebuildable) | keyless MET Norway Locationforecast |
| volcano | volcanoID           | NZ volcanic alert level (0-5) + unrest escalation | keyless GeoNet VAL API |
| nzski   | resort data-slug    | NZ ski-field base depth + lifts/trails open (open = deal) | page-called NZSki feed |
| gwrivers| gauge site name     | NZ river flow/level + flood-onset rise (1.5x in 24h) | keyless GW Hilltop XML |
| spaceweather | UTC forecast date | planetary Kp forecast: per-day peak + storm/aurora drift (Kp>=5 = aurora australis) | keyless NOAA SWPC feed |
| sentry  | Sentry designation  | asteroid impact-risk drift: Palermo/Torino/impact-probability revisions, then retirement from the risk list | keyless JPL/CNEOS Sentry API |
| avalanche | region slug       | NZ backcountry avalanche danger rating (1-5) per elevation band, as-issued daily + its revision (drift); deal = Considerable+ (>=3) | keyless page-called avalanche.net.nz /api/forecast |
| mdcrivers | gauge site name   | Marlborough (NZ) river flow/level + flood-onset rise (1.5x in 24h) | keyless MDC Hilltop XML |
| horizonsrivers | gauge site name | Manawatu-Whanganui (NZ) river flow/level + flood-onset rise | keyless Horizons Hilltop XML |
| nswrfs  | incident id         | NSW (AU) bush/grass fire lifecycle: alert level escalating (Advice->Watch and Act->Emergency Warning) + size, then resolution; deal = out-of-control fire at Watch and Act+ | keyless RFS majorIncidents feed |
| vicemergency | event id        | Victoria (AU) all-hazards warnings/incidents: alert-level lifecycle across fire/flood/storm; deal = Watch and Act+ | keyless VicEmergency GeoJSON |
| sacfs   | incident id         | South Australia (AU) CFS incidents: response level + status (GOING->CONTROLLED); deal = still GOING | keyless SA CFS feed |
| beachwatch | site id (uuid)   | NSW (AU) beach water-quality star rating + daily pollution forecast; deal = pollution Possible/Likely (swim advisory) | keyless NSW Beachwatch GeoJSON |
| safeswim | beach slug        | NZ beach water-quality traffic-light (GREEN/RED/RED+/BLACK), flips with rainfall; deal = a water-quality alert | keyless page-called Safeswim API |

### aviation
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| chcflights | dir:type:flightNo:scheduled | Christchurch Airport flight delay-drift (estimate vs schedule) + gate/status churn; deal = delayed/cancelled | keyless christchurchairport.co.nz /api/flights JSON |
| zqnflights | dir:flightNo:schDate:schTime | Queenstown Airport delay-drift + status churn (NZ's most disruption-prone board); deal = delayed/cancelled | keyless queenstownairport.co.nz /api/flights JSON |

### roads & transport
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| nzroads | NZTA event id       | national highway disruption lifecycle: impact escalating/easing (Caution/Delays/Road Closed), then resolution (the event vanishes); deal = an unplanned active disruption | keyless page-called journeys.nzta.govt.nz delays.json |

### shared mobility
| source  | join key            | timeline value                         | API                          |
|---------|---------------------|----------------------------------------|------------------------------|
| bikeshare | system:station_id | dock-based bike-share station availability: bikes/docks free oscillating through the day (the fill/empty cycle), never archived per-station; deal = a renting station running dry (<=2 bikes) | keyless open GBFS station feed |

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
