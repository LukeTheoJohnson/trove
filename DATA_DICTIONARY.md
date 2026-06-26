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

| source | `price_cents` denomination | `flags` keys | `extra` keys |
|--------|----------------------------|--------------|--------------|
| steam | store currency via `--cc` (final price) | `discount_pct`, `is_free` | `metascore` (search); `release`, `platforms` (item) |
| discogs | `--cc` curr (lowest marketplace price); `qty` = num for sale | _(none)_ | `year`, `have`, `want` |
| itunes | `--cc` country store | _(none)_ | `kind` |
| scryfall | `--cc` = `usd`\|`eur`\|`tix` (nonfoil) | `foil_cents` | `set`, `rarity`, `released` |
| pokemontcg | `--cc` = `usd` (TCGplayer market) \| `eur` (Cardmarket trend) | `denom`, `variant`, `low_cents`, `mid_cents`, `high_cents`, `avg30_cents`, `avg7_cents`, `updated` | `set`, `series`, `released` |
| ygoprodeck | `--cc` = tracked venue (`tcgplayer` default) | `denom`, `tcgplayer_c`, `cardmarket_c`, `ebay_c`, `amazon_c`, `coolstuffinc_c` | `attribute`, `atk`, `def`, `level`, `archetype`, `sets` |
| metno | **not money** — `price_cents` = upcoming-day forecast **high** in centi-degrees C (22.0C -> 2200), so `drops` = a forecast that *cooled*; `qty` = that day's forecast rain in tenths of a mm | `high_c`, `low_c`, `precip_mm`, `symbol`, `wind_ms`, `target_date`, `issued` | `lat`, `lon`, `name`, `issued`, `target_date`, `current_c`, `current_symbol`, `outlook`, `url` |

All money is integer **cents**. `price_cents = 0` means free; `NULL`/empty means the source returned
no price for that observation. Currencies differ by source and `--cc`; the denomination is not stored
per-row, so record which `--cc` a source is polled with if you mix them downstream.
