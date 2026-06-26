# trove data dictionary

trove is a hoarding engine: every fetch appends a **timestamped observation** to a local SQLite
store, so the cache compounds into a proprietary time-series you can't buy or backfill. This file
documents the store and the `export` output so the hoard is consumable by other tools.

## Store (SQLite, `data/<source>.db`)

One generic schema serves every source. Source-specific fields ride in JSON columns (`extra` on
items, `flags` on observations), so a new source needs no migration.

### `items` — one row per tracked entity
| column | type | meaning |
|--------|------|---------|
| `item_id` | TEXT (PK) | the **join key** (appid, release id, card id, station id...) |
| `name` | TEXT | display name |
| `subtitle` | TEXT | source-defined secondary label (artist, set, card type...) |
| `category` | TEXT | source-defined class (genre, format, rarity...) |
| `extra` | TEXT (JSON) | source-specific metadata (see per-source table below) |
| `first_seen` / `last_seen` | TEXT (UTC `YYYY-MM-DD HH:MM:SS`) | first/most-recent time the item was written |

### `obs` — the time-series (one row per observation; **never updated, only appended**)
| column | type | meaning |
|--------|------|---------|
| `id` | INTEGER (PK) | autoincrement |
| `item_id` | TEXT | FK to `items` |
| `ts` | TEXT (UTC) | observation timestamp |
| `price_cents` | INTEGER | headline price in cents, in the source's denomination (see below); `0` = free, `NULL` = no price |
| `was_cents` | INTEGER | reference/list price where the source provides one |
| `qty` | INTEGER | quantity/availability signal (e.g. discogs `num_for_sale`) |
| `flags` | TEXT (JSON) | source-specific signals (see per-source table) |
| `tag` | TEXT | what wrote the row: `search` / `item` / `poll` |

### `watch` — the watchlist
| column | meaning |
|--------|---------|
| `item_id` | FK to `items` |
| `added_at` | UTC timestamp |

## `export` command

```bash
python trove.py <source> export                 # full obs time-series -> data/<source>_obs.csv
python trove.py <source> export --what latest    # newest row per item (snapshot)
python trove.py <source> export --what items     # the item catalog
python trove.py <source> export --out merged.csv # custom path
```

UTF-8 CSV, fully offline. Every row is prefixed with a `source` column so exports from multiple
sources concatenate cleanly into one hoard. `obs`/`latest` columns:
`source,item_id,name,subtitle,category,ts,price_cents,was_cents,qty,tag,flags,first_seen,last_seen`.
`items` columns: `source,item_id,name,subtitle,category,extra,first_seen,last_seen`. The `flags` and
`extra` cells are raw JSON strings — parse them per the table below.

## Per-source semantics (denomination, `flags`, `extra`)

Grouped by genre (same four sections as the `--help` listing and the backlog).

### games / media / collectibles
| source | `price_cents` denomination | `flags` keys | `extra` keys |
|--------|----------------------------|--------------|--------------|
| steam | store currency via `--cc` (final price) | `discount_pct`, `is_free` | `metascore` (search); `release`, `platforms` (item) |
| discogs | `--cc` curr (lowest marketplace price); `qty` = num for sale | _(none)_ | `year`, `have`, `want` |
| itunes | `--cc` country store | _(none)_ | `kind` |
| scryfall | `--cc` = `usd`\|`eur`\|`tix` (nonfoil) | `foil_cents` | `set`, `rarity`, `released` |
| pokemontcg | `--cc` = `usd` (TCGplayer market) \| `eur` (Cardmarket trend) | `denom`, `variant`, `low_cents`, `mid_cents`, `high_cents`, `avg30_cents`, `avg7_cents`, `updated` | `set`, `series`, `released` |
| ygoprodeck | `--cc` = tracked venue (`tcgplayer` default) | `denom`, `tcgplayer_c`, `cardmarket_c`, `ebay_c`, `amazon_c`, `coolstuffinc_c` | `attribute`, `atk`, `def`, `level`, `archetype`, `sets` |

### fuel & electricity
| source | `price_cents` denomination | `flags` keys | `extra` keys |
|--------|----------------------------|--------------|--------------|
| spainfuel | EUR cents/L for the headline grade G95E5 | `grade`, `board` (all grades cents/L), `milli`, `area_avg` | `municipio`, `cp`, `lat`, `lon`, `horario`, `idees` |
| petrolspy | NZ/AU cents/L for the headline grade | `grade`, `board`, `updated`, `relevant`, `area_avg`, `unit` | `suburb`, `postcode`, `lat`, `lon`, `open24`, `country`, `brand` |
| em6 | NZ wholesale electricity spot, $/MWh * 100 (so `drops` = price *falling*) | `unit` ($/MWh), `trading_period`, `timestamp`, `nat_avg` | `grid_zone_id` |

### deals, fares & listings
| source | `price_cents` denomination | `flags` keys | `extra` keys |
|--------|----------------------------|--------------|--------------|
| grabone | NZD deal price; `was_cents` = RRP (listing rows) | `currency`, `region`, `discount_pct`, `available`, `src` (`listing`/`detail`), `valid_through` (detail) | `url`, `image`, `merchant`, `region`; detail adds `valid_from` |
| grabaseat | NZD cheapest fare for the route (* 100) | `currency`, `lowest_date`, `avg_cents`, `min_cents`, `max_cents`, `n_fares`, `board` (per-day fares) | `origin`, `destination`, `book_url` |
| bookme | NZD deal price; `was_cents` = price+save; `qty` = spaces remaining | `currency`, `discount_pct`, `save_cents`, `region`, `date_from`, `date_to` | `url`, `region`, `rating`, `reviews` |
| turners | NZD asking price; `was_cents` = RRP where discounted | `currency`, `channel`, `discounted`, `discount_pct`, `odometer_km`, `branch`, `availability` | `make`, `model`, `year`, `odometer_km`, `branch`, `fuel`, `body`, `channel`, `url` |
| eventcinemas | **not money** — `qty` = seats remaining (no price in feed); deal = a session near sellout | `cinema`, `cinema_id`, `screen_type`, `screen`, `start`, `attributes`, `reserved_seating`, `sold_out` | `movie`, `movie_id`, `movie_url`, `rating`, `cinema`, `screen_type`, `screen`, `start`, `date`, `booking_url` |

### weather, environment & geohazard
| source | `price_cents` denomination | `flags` keys | `extra` keys |
|--------|----------------------------|--------------|--------------|
| geonet | **not money** — `price_cents` = magnitude * 100 (centi-magnitude), so `drops` = a quake *downgraded* on review; `qty` = MMI | `magnitude`, `mmi`, `depth_km`, `quality`, `locality`, `time` | `lat`, `lon`, `locality`, `time`, `url` |
| metno | **not money** — `price_cents` = upcoming-day forecast **high** in centi-degrees C (22.0C -> 2200), so `drops` = a forecast that *cooled*; `qty` = that day's forecast rain in tenths of a mm | `high_c`, `low_c`, `precip_mm`, `symbol`, `wind_ms`, `target_date`, `issued` | `lat`, `lon`, `name`, `issued`, `target_date`, `current_c`, `current_symbol`, `outlook`, `url` |
| volcano | **not money** — `price_cents` = Volcanic Alert Level * 100 (centi-level, 0-5), so `drops` = a *de-escalation*; `qty` = raw level 0-5 | `level`, `acc` (colour), `activity`, `hazards` | `lat`, `lon`, `activity`, `hazards`, `url` |
| nzski | **not money** — `price_cents` = headline base depth cm * 100, so `drops` = the base *melting*; `qty` = lifts open count | `base_cm`, `base_min`, `base_max`, `season_total`, `last7days`, `lifts_open`, `lifts_total`, `trails_open`, `trails_total`, `status`, `temp_high`, `temp_low`, `updated` | `slug`, `updated`, `road_status`, `chain_status`, `weather`, `url` |
| gwrivers | **not money** — `price_cents` = latest **Flow** m3/s * 100 (centi-cumecs) **or** Stage mm * 100 (per-site consistent; read `flags.measurement`/`unit`), so `drops` = a river *receding*; deal `rising` is precomputed in flags | `measurement`, `unit`, `value`, `value_24h_ago`, `max_24h`, `min_24h`, `change_24h`, `pct_change_24h`, `rising`, `latest_time` | `measurement`, `unit`, `url` |

All money is integer **cents**. `price_cents = 0` means free; `NULL`/empty means the source returned
no price for that observation. Currencies differ by source and `--cc`; the denomination is not stored
per-row, so record which `--cc` a source is polled with if you mix them downstream.
