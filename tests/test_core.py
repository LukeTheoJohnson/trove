"""Core-spine tests: money()/safe() formatting and the stateful TrackerDB (obs log, watchlist,
drop detection, export shapes). All offline against a throwaway SQLite file."""
import os
import tempfile

from trove.db import Item, Obs, TrackerDB
from trove.tracker import money, safe


def _fresh_db():
    return TrackerDB(os.path.join(tempfile.mkdtemp(), "t.db"))


def test_money_formats():
    assert money(None) == "?"
    assert money(0) == "Free"
    assert money(1234) == "$12.34"
    assert money(-1500) == "$-15.00"          # negative scalar (octopus plunge / flight recovery)


def test_safe_folds_and_coerces():
    assert safe("plain") == "plain"
    assert safe(None) == ""
    assert safe("  spaced  ") == "spaced"
    assert safe(42) == "42"                    # non-str coerced, not crashed
    assert safe("Taupō") == "Taup?"       # macron -> '?' under the cp1252 console codec


def test_upsert_then_last_obs():
    db = _fresh_db()
    db.upsert_item(Item("a", "Alpha", subtitle="s", category="c", extra={"k": 1}))
    db.log_obs("a", Obs(price_cents=500, flags={"basis": "x"}), "item")
    ob = db.last_obs("a")
    assert ob is not None and ob.price_cents == 500 and ob.flags["basis"] == "x"


def test_log_obs_skips_signalless():
    db = _fresh_db()
    db.upsert_item(Item("a", "Alpha"))
    db.log_obs("a", Obs(), "item")             # no price and no qty -> not logged
    assert db.last_obs("a") is None


def test_drops_detects_decrease_only():
    db = _fresh_db()
    db.upsert_item(Item("a", "Alpha"))
    db.add_watch("a")
    db.log_obs("a", Obs(price_cents=1000), "poll")
    db.log_obs("a", Obs(price_cents=800), "poll")
    assert db.drops() == [("Alpha", 1000, 800)]


def test_drops_ignores_increase():
    db = _fresh_db()
    db.upsert_item(Item("a", "Alpha"))
    db.add_watch("a")
    db.log_obs("a", Obs(price_cents=800), "poll")
    db.log_obs("a", Obs(price_cents=1000), "poll")
    assert db.drops() == []


def test_watch_lifecycle():
    db = _fresh_db()
    db.upsert_item(Item("a", "Alpha"))
    db.log_obs("a", Obs(price_cents=100), "item")
    db.add_watch("a")
    db.add_watch("a")                          # idempotent (INSERT OR IGNORE)
    assert db.watched() == ["a"]
    (iid, name, ob), = db.watchlist()
    assert iid == "a" and name == "Alpha" and ob.price_cents == 100
    db.rm_watch("a")
    assert db.watched() == []


def test_latest_for_watched_returns_newest():
    db = _fresh_db()
    db.upsert_item(Item("a", "Alpha"))
    db.add_watch("a")
    db.log_obs("a", Obs(price_cents=100), "poll")
    db.log_obs("a", Obs(price_cents=140), "poll")
    (item, ob), = db.latest_for_watched()
    assert item.id == "a" and ob.price_cents == 140


def test_export_row_shapes():
    db = _fresh_db()
    db.upsert_item(Item("a", "Alpha", subtitle="s", category="c"))
    db.log_obs("a", Obs(price_cents=100, qty=3, flags={"f": 1}), "item")
    assert db.obs_rows()[0]["item_id"] == "a"
    assert db.obs_rows()[0]["price_cents"] == 100
    assert db.latest_rows()[0]["qty"] == 3
    assert db.items_rows()[0]["name"] == "Alpha"


def test_unmatched_watch_has_no_name():
    """A watch id with no matching item row yields (id, None, None) - the shape behind the
    nzski keying confusion (watch an alias, it never joins to the slug-keyed item)."""
    db = _fresh_db()
    db.add_watch("ghost")
    (iid, name, ob), = db.watchlist()
    assert iid == "ghost" and name is None and ob is None
