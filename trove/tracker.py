"""The Source contract + run_cli: one generic command set (doctor/search/item/watch/poll/
deals/drops) that every source plugs into by implementing a handful of hooks.

A source subclasses Source and implements: client, doctor, search, fetch, and the deal
semantics (is_deal/deal_line). Everything stateful (caching, timestamped obs, watch, drop
detection) is handled here against TrackerDB. A new source is ~50 lines.
"""
from __future__ import annotations

import argparse
import os
import time

from .db import Item, Obs, TrackerDB


def money(cents) -> str:
    if cents is None:
        return "?"
    if cents == 0:
        return "Free"
    return f"${cents / 100:.2f}"


class Source:
    name = "source"
    id_label = "ID"
    cc_default = "nz"          # store/currency code; each source interprets it
    deal_label = "deal"        # noun for the `deals` command + poll tag
    search_args: list[tuple] = []   # extra argparse args for `search`: [("--entity", {...})]

    # -- hooks a source implements --------------------------------------- #
    def client(self, args):
        raise NotImplementedError

    def doctor(self, client) -> tuple[bool, str]:
        raise NotImplementedError

    def search(self, client, term, args) -> list[tuple[Item, Obs | None]]:
        raise NotImplementedError

    def fetch(self, client, item_id) -> tuple[Item, Obs] | None:
        """Rich lookup for `item`; also the default for `poll`."""
        raise NotImplementedError

    def refresh(self, client, item_id) -> tuple[Item, Obs] | None:
        """Lean lookup for `poll`. Defaults to fetch; override for a cheaper endpoint."""
        return self.fetch(client, item_id)

    def is_deal(self, obs: Obs) -> bool:
        return False

    def deal_line(self, item: Item, obs: Obs) -> str:
        return f"{money(obs.price_cents)}  {item.name}"

    def format_item(self, item: Item, obs: Obs | None) -> list[str]:
        lines = [f"  subtitle : {item.subtitle}", f"  category : {item.category}"]
        if obs:
            lines.append(f"  price    : {money(obs.price_cents)}")
        return lines

    def poll_spacing(self) -> float:
        return 0.4


# -- the generic CLI -------------------------------------------------------- #
def _db_for(source: Source, data_dir: str) -> TrackerDB:
    return TrackerDB(os.path.join(data_dir, f"{source.name}.db"))


def run_cli(source: Source, argv: list[str], data_dir: str) -> int:
    p = argparse.ArgumentParser(prog=f"trove {source.name}",
                                description=f"{source.name} price/listing intelligence (personal use).")
    p.add_argument("--cc", default=source.cc_default, help=f"store/currency code (default {source.cc_default})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check the API is reachable")
    sp = sub.add_parser("search", help="search the source")
    sp.add_argument("term")
    sp.add_argument("--limit", type=int, default=15)
    for flag, kw in source.search_args:
        sp.add_argument(flag, **kw)
    sp = sub.add_parser("item", help="look up one item"); sp.add_argument("item_id")
    sp = sub.add_parser("watch", help="manage the watchlist")
    sp.add_argument("action", choices=["add", "rm", "list"]); sp.add_argument("item_id", nargs="?")
    sub.add_parser("poll", help="refresh watched items, log prices, report drops/" + source.deal_label)
    sub.add_parser("deals", help=f"watched items that are a {source.deal_label} now")
    sub.add_parser("drops", help="watched items cheaper than first seen")

    args = p.parse_args(argv)
    cl = source.client(args)
    db = _db_for(source, data_dir)

    if args.cmd == "doctor":
        t = time.time()
        try:
            ok, detail = source.doctor(cl)
        except Exception as e:
            print(f"BROKEN {source.name}  {type(e).__name__}: {e}"); return 1
        ms = int((time.time() - t) * 1000)
        print(f"{'OK  ' if ok else 'EMPTY'} {source.name}  {ms}ms  {detail}")
        return 0 if ok else 1

    if args.cmd == "search":
        rows = source.search(cl, args.term, args)
        for item, obs in rows:
            db.upsert_item(item)
            db.log_obs(item.id, obs, "search")
        if not rows:
            print("no results."); return 0
        print(f"{source.id_label:>12}  {'PRICE':>8}  NAME")
        for item, obs in rows[: args.limit]:
            print(f"{str(item.id):>12}  {money(obs.price_cents) if obs else '?':>8}  {item.name}")
        return 0

    if args.cmd == "item":
        res = source.fetch(cl, args.item_id)
        if res is None:
            print(f"{args.item_id}: not found."); return 1
        item, obs = res
        db.upsert_item(item); db.log_obs(item.id, obs, "item")
        print(f"{item.name}  [{item.id}]")
        for ln in source.format_item(item, obs):
            print(ln)
        return 0

    if args.cmd == "watch":
        if args.action == "add":
            db.add_watch(args.item_id); print(f"watching {args.item_id}")
        elif args.action == "rm":
            db.rm_watch(args.item_id); print(f"unwatched {args.item_id}")
        else:
            wl = db.watchlist()
            if not wl:
                print(f"watchlist empty. add one: trove {source.name} watch add <id>")
            for iid, name, obs in wl:
                print(f"  {iid:>12}  {money(obs.price_cents) if obs else '?':>8}  {name or '(unknown - item/poll to fetch)'}")
        return 0

    if args.cmd == "poll":
        watched = db.watched()
        if not watched:
            print(f"watchlist empty. add one: trove {source.name} watch add <id>"); return 0
        drops, deals = [], []
        for iid in watched:
            prev = db.last_obs(iid)
            res = source.refresh(cl, iid)
            if res is None:
                continue
            item, obs = res
            db.upsert_item(item); db.log_obs(iid, obs, "poll")
            if obs.price_cents is not None and prev and prev.price_cents is not None and obs.price_cents < prev.price_cents:
                drops.append((item.name or iid, prev.price_cents, obs.price_cents))
            if source.is_deal(obs) and not (prev and source.is_deal(prev)):
                deals.append((item, obs))
            time.sleep(source.poll_spacing())
        from .db import now as _now
        print(f"polled {len(watched)} watched item(s) at {_now()}Z")
        for name, old, new in drops:
            print(f"  DROP  {name}  {money(old)} -> {money(new)}")
        for item, obs in deals:
            print(f"  {source.deal_label.upper():<5} {source.deal_line(item, obs)}")
        if not drops and not deals:
            print(f"  no new drops or {source.deal_label}s.")
        return 0

    if args.cmd == "deals":
        hits = [(it, ob) for it, ob in db.latest_for_watched() if source.is_deal(ob)]
        if not hits:
            print(f"no watched item is a {source.deal_label} now. (run poll first)"); return 0
        print(f"Watched {source.deal_label}s:")
        for item, obs in hits:
            print(f"  {source.deal_line(item, obs)}")
        return 0

    if args.cmd == "drops":
        hits = db.drops()
        if not hits:
            print("no watched item is cheaper than first seen yet. (history builds as you poll)"); return 0
        print("Cheaper than first seen:")
        for name, f, l in hits:
            print(f"  {money(f)} -> {money(l)}  {name}")
        return 0

    return 2
