"""TrackerDB - the shared stateful spine: items, a timestamped observation log, and a watchlist.

One generic schema serves every price/listing source. Source-specific fields ride in JSON
`extra`/`flags` columns, so a new source needs no migration. The timestamped `obs` log is the
whole point: it compounds into price/scarcity history as you poll.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Obs:
    """A single observation of an item at a point in time."""
    __slots__ = ("price_cents", "was_cents", "qty", "flags")

    def __init__(self, price_cents=None, was_cents=None, qty=None, flags=None):
        self.price_cents = price_cents
        self.was_cents = was_cents
        self.qty = qty
        self.flags = flags or {}

    def has_signal(self) -> bool:
        return self.price_cents is not None or self.qty is not None


class Item:
    """An item's metadata. id is the join key; extra holds source-specific fields."""
    __slots__ = ("id", "name", "subtitle", "category", "extra")

    def __init__(self, id, name="", subtitle="", category="", extra=None):
        self.id = id
        self.name = name
        self.subtitle = subtitle
        self.category = category
        self.extra = extra or {}


class TrackerDB:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        c = self.conn
        c.execute("""CREATE TABLE IF NOT EXISTS items (
            item_id TEXT PRIMARY KEY, name TEXT, subtitle TEXT, category TEXT,
            extra TEXT, first_seen TEXT, last_seen TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS obs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, ts TEXT,
            price_cents INTEGER, was_cents INTEGER, qty INTEGER, flags TEXT, tag TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS watch (
            item_id TEXT PRIMARY KEY, added_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_obs_item ON obs(item_id, ts)")
        c.commit()

    # -- writes ----------------------------------------------------------- #
    def upsert_item(self, item: Item):
        t = now()
        self.conn.execute("""INSERT INTO items (item_id,name,subtitle,category,extra,first_seen,last_seen)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(item_id) DO UPDATE SET name=excluded.name,
            subtitle=COALESCE(NULLIF(excluded.subtitle,''),items.subtitle),
            category=COALESCE(NULLIF(excluded.category,''),items.category),
            extra=COALESCE(NULLIF(excluded.extra,''),items.extra),
            last_seen=excluded.last_seen""",
            (str(item.id), item.name, item.subtitle, item.category,
             json.dumps(item.extra) if item.extra else "", t, t))
        self.conn.commit()

    def log_obs(self, item_id, obs: Obs, tag: str):
        if obs is None or not obs.has_signal():
            return
        self.conn.execute("""INSERT INTO obs (item_id,ts,price_cents,was_cents,qty,flags,tag)
            VALUES (?,?,?,?,?,?,?)""",
            (str(item_id), now(), obs.price_cents, obs.was_cents, obs.qty,
             json.dumps(obs.flags) if obs.flags else "", tag))
        self.conn.commit()

    def add_watch(self, item_id):
        self.conn.execute("INSERT OR IGNORE INTO watch (item_id,added_at) VALUES (?,?)",
                          (str(item_id), now()))
        self.conn.commit()

    def rm_watch(self, item_id):
        self.conn.execute("DELETE FROM watch WHERE item_id=?", (str(item_id),))
        self.conn.commit()

    # -- reads ------------------------------------------------------------ #
    @staticmethod
    def _obs(row) -> Obs:
        return Obs(row["price_cents"], row["was_cents"], row["qty"],
                   json.loads(row["flags"]) if row["flags"] else {})

    def last_obs(self, item_id) -> Obs | None:
        r = self.conn.execute("SELECT * FROM obs WHERE item_id=? ORDER BY ts DESC LIMIT 1",
                              (str(item_id),)).fetchone()
        return self._obs(r) if r else None

    def watched(self) -> list[str]:
        return [r["item_id"] for r in self.conn.execute("SELECT item_id FROM watch").fetchall()]

    def watchlist(self) -> list[tuple[str, str, Obs | None]]:
        out = []
        rows = self.conn.execute("""SELECT w.item_id, i.name FROM watch w
            LEFT JOIN items i ON i.item_id=w.item_id ORDER BY w.added_at""").fetchall()
        for r in rows:
            out.append((r["item_id"], r["name"], self.last_obs(r["item_id"])))
        return out

    def latest_for_watched(self) -> list[tuple[Item, Obs]]:
        """(Item, latest Obs) for each watched item that has at least one observation."""
        out = []
        for iid in self.watched():
            ir = self.conn.execute("SELECT * FROM items WHERE item_id=?", (iid,)).fetchone()
            ob = self.last_obs(iid)
            if ir and ob:
                out.append((Item(ir["item_id"], ir["name"], ir["subtitle"], ir["category"]), ob))
        return out

    def drops(self) -> list[tuple[str, int, int]]:
        """(name, first_price, last_price) for watched items now cheaper than first seen."""
        out = []
        for iid in self.watched():
            f = self.conn.execute("SELECT price_cents FROM obs WHERE item_id=? AND price_cents IS NOT NULL ORDER BY ts ASC LIMIT 1", (iid,)).fetchone()
            l = self.conn.execute("SELECT price_cents FROM obs WHERE item_id=? AND price_cents IS NOT NULL ORDER BY ts DESC LIMIT 1", (iid,)).fetchone()
            nm = self.conn.execute("SELECT name FROM items WHERE item_id=?", (iid,)).fetchone()
            if f and l and f["price_cents"] is not None and l["price_cents"] is not None and l["price_cents"] < f["price_cents"]:
                out.append((nm["name"] if nm else iid, f["price_cents"], l["price_cents"]))
        return sorted(out, key=lambda x: x[2] - x[1])

    # -- export (the whole hoard, not just the watchlist) ----------------- #
    def items_rows(self):
        return self.conn.execute(
            "SELECT item_id,name,subtitle,category,extra,first_seen,last_seen FROM items ORDER BY item_id"
        ).fetchall()

    def obs_rows(self):
        """Every observation, denormalized with item metadata - the full time-series."""
        return self.conn.execute(
            """SELECT i.item_id,i.name,i.subtitle,i.category,
                      o.ts,o.price_cents,o.was_cents,o.qty,o.tag,o.flags,
                      i.first_seen,i.last_seen
               FROM obs o JOIN items i ON i.item_id=o.item_id
               ORDER BY o.item_id,o.ts,o.id"""
        ).fetchall()

    def latest_rows(self):
        """Latest observation per item (snapshot), all items."""
        return self.conn.execute(
            """SELECT i.item_id,i.name,i.subtitle,i.category,
                      o.ts,o.price_cents,o.was_cents,o.qty,o.tag,o.flags,
                      i.first_seen,i.last_seen
               FROM obs o JOIN items i ON i.item_id=o.item_id
               WHERE o.id=(SELECT id FROM obs o2 WHERE o2.item_id=o.item_id
                           ORDER BY o2.ts DESC,o2.id DESC LIMIT 1)
               ORDER BY i.item_id"""
        ).fetchall()
