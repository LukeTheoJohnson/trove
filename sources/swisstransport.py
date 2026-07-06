"""swisstransport - Swiss public-transport departure board with live delays, keyless.

transport.opendata.ch is the community Swiss public-transport API (a wrapper over the official SBB
timetable). `GET /v1/stationboard?station=<name>` returns the next departures from a station: the line
(`IC 1`, `S3`, tram/bus number), destination, scheduled `departure`, real-time `delay` (minutes),
platform, and a `prognosis` (the live estimate). robots.txt is `User-agent: * / Disallow:` (empty =
allow all) and the API is published for reuse = sanctioned -> trove. The rail/tram twin of the airport
boards `chcflights`/`zqnflights`: a departure board whose value is the *delay drift* in the minutes
before a service leaves.

The timeline value is un-rebuildable: a departure's delay grows and shrinks in the minutes before it
runs, then the service leaves and the row is gone - and the API serves only the live board, no queryable
per-departure delay history. `price_cents` = the **delay in minutes** (signed; 0 = on time, following
`chcflights`), so the core's `drops` = a departure that *recovered* (delay fell); `qty` = whole minutes
until the scheduled departure (the countdown). A "deal" ("delayed") = a departure running >= 3 minutes
late. money() renders the delay-minutes as dollars in the two core-hardcoded spots. A departure leaving
the board = its series ends (the retirement contract).

Model: one Item per scheduled departure (composite join key = `station|line|to|schedTs`, station read
back from the key on refresh - the `appcharts` pattern). `search <station>` reads that station's board
(defaults to "Zurich HB" when passed ""); `fetch` re-reads the station in the key and matches the
departure. `--cc` is unused - stations are named directly.
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "http://transport.opendata.ch/v1/stationboard"
DEFAULT_STATION = "Zurich HB"
KEY_SEP = "|"


def _mins_until(ts):
    if not ts:
        return None
    try:
        return round((int(ts) - datetime.now(timezone.utc).timestamp()) / 60)
    except (TypeError, ValueError):
        return None


def _build(station, dep):
    stop = dep.get("stop") or {}
    cat, num = dep.get("category") or "", dep.get("number") or ""
    line = safe(f"{cat} {num}".strip() or dep.get("name") or "")
    to = safe(dep.get("to") or "")
    sched_ts = stop.get("departureTimestamp")
    delay = stop.get("delay")
    key = KEY_SEP.join([station, line, to, str(sched_ts)])
    item = Item(key, name=f"{line} -> {to}", subtitle=f"departure from {station}", category="departure",
                extra={"station": station, "line": line, "to": to})
    obs = Obs(price_cents=(int(delay) if isinstance(delay, (int, float)) else None),
              qty=_mins_until(sched_ts),
              flags={"delay": delay, "platform": safe(stop.get("platform") or ""),
                     "departure": stop.get("departure"), "line": line, "to": to, "station": station})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()

    def board(self, station, limit=25):
        r = self.s.get(BASE, params={"station": station, "limit": limit},
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        d = r.json() or {}
        name = ((d.get("station") or {}).get("name")) or station
        return name, (d.get("stationboard") or [])


class SwissTransportSource(Source):
    name = "swisstransport"
    id_label = "DEPARTURE"
    cc_default = "ch"        # unused; stations named directly
    deal_label = "delayed"   # running >= 3 minutes late
    search_limit_default = 25
    search_header = f"{'DELAY':>5}  {'~MIN':>4}  {'PLAT':<5}  DEPARTURE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        name, board = cl.board(DEFAULT_STATION, limit=5)
        return bool(board), f"({len(board)} departures from {name}; keyless transport.opendata.ch stationboard)"

    def search(self, cl, term, args):
        station = (term or "").strip() or DEFAULT_STATION
        name, board = cl.board(station, limit=args.limit if hasattr(args, "limit") else 25)
        return [_build(name, dep) for dep in board]

    def fetch(self, cl, item_id):
        parts = str(item_id).split(KEY_SEP)
        if len(parts) < 4:
            return None
        station = parts[0]
        name, board = cl.board(station, limit=40)
        for dep in board:
            item, obs = _build(name, dep)
            if item.id == str(item_id):
                return item, obs
        return None

    def is_deal(self, obs):
        d = obs.flags.get("delay")
        return isinstance(d, (int, float)) and d >= 3

    def deal_line(self, item, obs):
        return f"+{obs.flags.get('delay')} min  {item.name}  (plat {obs.flags.get('platform') or '?'})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        d = f.get("delay")
        return f"{(f'+{d}' if isinstance(d, (int, float)) and d else (d if d is not None else '?')):>5}  {(obs.qty if obs and obs.qty is not None else '?'):>4}  {safe(f.get('platform') or '-'):<5}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  departure: {item.name}",
                 f"  station  : {e.get('station')}"]
        if obs:
            f = obs.flags
            lines.append(f"  scheduled: {f.get('departure') or '?'}   platform {f.get('platform') or '?'}")
            lines.append(f"  delay    : {f.get('delay') if f.get('delay') is not None else 'no live data'} min   (~{obs.qty} min out)")
        return lines


SOURCE = SwissTransportSource()
