"""Source registration + contract smoke tests. Offline: every driver must import, register, and
survive the display/deal hooks on a synthetic observation - no client is built, no API is hit.

This is the regression net for refactors of the shared core (a missing import or a renamed helper
in a driver shows up here on every push, instead of the first time someone polls that source)."""
import importlib
import importlib.util
import os

import pytest

from trove.db import Item, Obs
from trove.tracker import Source

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_cli():
    """Load trove.py (the entrypoint) by path - `import trove` resolves to the package, not it."""
    spec = importlib.util.spec_from_file_location("trove_cli", os.path.join(ROOT, "trove.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CLI = _load_cli()
SOURCES = _CLI.SOURCES
SOURCE_GROUPS = _CLI.SOURCE_GROUPS


def test_sources_match_source_dir():
    """Every sources/<name>.py is registered, and every registered name has a file (no drift)."""
    on_disk = {f[:-3] for f in os.listdir(os.path.join(ROOT, "sources"))
               if f.endswith(".py") and f != "__init__.py"}
    assert set(SOURCES) == on_disk


def test_groups_flatten_to_sources_without_dupes():
    flat = tuple(n for g in SOURCE_GROUPS.values() for n in g)
    assert flat == SOURCES
    assert len(set(SOURCES)) == len(SOURCES)


@pytest.mark.parametrize("name", SOURCES)
def test_source_well_formed(name):
    s = importlib.import_module(f"sources.{name}").SOURCE
    assert isinstance(s, Source)
    assert s.name == name                      # SOURCE.name matches its module/registration
    assert s.id_label and s.deal_label
    assert s.poll_spacing() == 0.5             # the centralized default; no driver overrides it


@pytest.mark.parametrize("name", SOURCES)
def test_display_hooks_offline(name):
    """search_row / format_item / is_deal must not raise on a generic obs; deal_line is contract-
    ually only called on a deal, so call it only when is_deal says so."""
    s = importlib.import_module(f"sources.{name}").SOURCE
    item = Item("x", "Test Item", subtitle="sub", category="cat", extra={})
    obs = Obs(price_cents=1000, was_cents=1200, qty=5, flags={})
    s.search_row(item, obs)
    s.search_row(item, None)                   # search yields (Item, Obs|None) - None must be safe
    s.format_item(item, obs)
    assert isinstance(s.is_deal(obs), bool)
    if s.is_deal(obs):
        s.deal_line(item, obs)
