"""chcflights - Christchurch Airport live flight board (christchurchairport.co.nz), keyless JSON.

Christchurch Airport (CHC) is NZ's South Island gateway. Its public arrivals/departures board
(/travellers/flights/arrivals-and-departures/) is a Vue widget that calls a keyless, same-origin
JSON endpoint, GET /api/flights?flightDirection=<Arrive|Depart>&flightType=<International|Domestic>
&maxFlights=<N>, returning the live board for that quadrant: every flight with its scheduled time,
current estimate, gate, and status. robots.txt has zero Disallow lines (only a Sitemap), and the
endpoint is the one the published page itself calls = sanctioned -> trove, not a private endpoint.
(Auckland Airport sits behind a Cloudflare JS challenge on every request; Wellington's robots fences
/flights/arrivals/ + /flights/departures/ - both skipped. CHC is the open one.)

The timeline value is a *flight's drift from schedule in the hours before it operates*: the estimate
ticking 7:24 -> 7:49 -> 7:59, the gate getting assigned, the status flipping to Delayed/Cancelled/
Landed. Once the flight operates the board drops it and nothing public keeps that minute-by-minute
progression - the snapshot is the only record, which is the whole point of hoarding it.

There is no price in aviation, so the tracked scalar is *delay in minutes* (estimate - scheduled;
negative = early, 0 = currently expected on time). It rides in price_cents so the shared core's
series + `drops` work, with `drops` = a flight that *recovered* (its delay shrank toward 0). Like
geonet/metno's scalar reuse, money() cosmetically renders the delay as dollars in the two
core-hardcoded spots (watchlist + poll DROP line: a +31m delay prints as "$0.31"); the rich item /
search / deal displays show proper minutes. The "deal" (deal_label "delay") is a disruption: a
flight delayed >= 15 min or cancelled.

Model: one Item per flight occurrence. The join key is composite, `<dir>|<type>|<flightNo>|
<scheduled>` (e.g. `Depart|International|QF132|Sat 9:15 PM`) - the board has no by-flight endpoint,
so the id encodes the quadrant + the stable scheduled time, letting fetch/poll rebuild the query and
match the row (same composite-key trick as eventcinemas/turners). flightNumbers[0] is the primary
number; codeshares ride in extra. `search --dir arrivals|departures|all --type intl|domestic|all`
picks which boards to pull (default all = up to 4 polite GETs, memoized per quadrant); the term
filters by flight number / airport / airline.
"""
from __future__ import annotations

from datetime import datetime

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

HOST = "https://www.christchurchairport.co.nz"
REFERER = HOST + "/travellers/flights/arrivals-and-departures/"
MAX_FLIGHTS = 200      # one GET returns a whole board quadrant
DELAY_MIN = 15         # minutes late (or cancelled) = "disruption"
DIRS = {"arrivals": "Arrive", "departures": "Depart"}
TYPES = {"intl": "International", "domestic": "Domestic"}


def _clock(stamp):
    """'Sat 7:24 PM' -> '7:24 PM' (drop the weekday prefix for compact listing)."""
    if not stamp:
        return ""
    p = stamp.strip().rsplit(" ", 2)
    return " ".join(p[-2:]) if len(p) >= 2 else stamp


def _minutes(stamp):
    """'Sat 7:24 PM' -> minutes-of-day (1164), or None. The weekday prefix is ignored; the board
    only spans ~a day, so a midnight wrap is resolved against the scheduled time in _delay()."""
    clock = _clock(stamp)
    if not clock:
        return None
    try:
        t = datetime.strptime(clock, "%I:%M %p")
    except ValueError:
        return None
    return t.hour * 60 + t.minute


def _delay(scheduled, estimate):
    """Signed minutes (estimate - scheduled), wrapped to +-12h. None when scheduled is unparseable;
    0 when there's no estimate yet (the board is currently expecting the flight on time)."""
    s = _minutes(scheduled)
    if s is None:
        return None
    e = _minutes(estimate)
    if e is None:
        return 0
    d = e - s
    if d > 720:
        d -= 1440
    elif d < -720:
        d += 1440
    return d


def _build(fl, dir_val, type_val, last_updated):
    """One flight dict -> (Item, Obs). Returns None without a flight number."""
    nums = [str(n) for n in (fl.get("flightNumbers") or []) if n]
    if not nums:
        return None
    flight_no = nums[0]
    scheduled = fl.get("scheduled", "") or ""
    estimate = fl.get("estimateActual", "") or ""
    status = safe(fl.get("status", "") or "")
    gate = fl.get("gate")
    route = " / ".join(safe(a) for a in (fl.get("airports") or []))
    airline = safe(fl.get("airlineName", "") or "")
    codeshares = nums[1:]
    delay = _delay(scheduled, estimate)
    cancelled = "cancel" in status.lower()
    delayed = "delay" in status.lower() or (delay is not None and delay >= DELAY_MIN)

    iid = f"{dir_val}|{type_val}|{flight_no}|{scheduled}"
    arrow = "from" if dir_val == "Arrive" else "to"
    item = Item(iid, name=f"{flight_no}  {route}".strip(),
                subtitle=f"{airline}  {dir_val.upper()[:3]} {arrow} {route}  sched {_clock(scheduled)}".strip(),
                category=airline,
                extra={"flight_no": flight_no, "codeshares": codeshares, "airline": airline,
                       "airline_code": fl.get("airlineCode", ""), "route": route,
                       "direction": dir_val, "type": type_val, "scheduled": scheduled,
                       "image_url": fl.get("imageUrl", "")})
    obs = Obs(price_cents=delay,
              flags={"status": status, "gate": gate, "estimate": estimate, "scheduled": scheduled,
                     "delay_min": delay, "cancelled": cancelled, "delayed": delayed, "route": route,
                     "direction": dir_val, "type": type_val, "last_updated": last_updated})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._cache = {}   # (dir, type) -> (flights, lastUpdated); one GET serves a whole poll

    def board(self, dir_val, type_val):
        key = (dir_val, type_val)
        if key in self._cache:
            return self._cache[key]
        r = self.s.get(HOST + "/api/flights",
                       params={"maxFlights": MAX_FLIGHTS, "flightDirection": dir_val,
                               "flightType": type_val},
                       headers={"User-Agent": UA, "Accept": "application/json",
                                "X-Requested-With": "XMLHttpRequest", "Referer": REFERER},
                       timeout=40)
        r.raise_for_status()
        d = r.json() or {}
        out = (d.get("flights", []) or [], d.get("lastUpdated", "") or "")
        self._cache[key] = out
        return out


def _rows(cl, dirs, types):
    out = []
    for dv in dirs:
        for tv in types:
            flights, lu = cl.board(dv, tv)
            for fl in flights:
                built = _build(fl, dv, tv, lu)
                if built:
                    out.append(built)
    return out


class ChcFlightsSource(Source):
    name = "chcflights"
    id_label = "FLIGHT"
    cc_default = "chc"      # not used; the board is Christchurch-only
    deal_label = "delay"    # a disrupted flight (delayed >= 15 min or cancelled)
    search_args = [
        ("--dir", {"choices": ["arrivals", "departures", "all"], "default": "all",
                   "help": "which board to pull (default all)"}),
        ("--type", {"choices": ["intl", "domestic", "all"], "default": "all",
                    "help": "international / domestic (default all)"}),
    ]
    search_limit_default = 300   # a board is bounded (~100-200 flights); list it, don't truncate
    search_header = f"{'SCHED':>10}  {'EST':>8}  {'STATUS':<11}  AIRPORT"

    def client(self, args):
        return _Client()

    def _dirs(self, args):
        d = getattr(args, "dir", "all") or "all"
        return list(DIRS.values()) if d == "all" else [DIRS[d]]

    def _types(self, args):
        t = getattr(args, "type", "all") or "all"
        return list(TYPES.values()) if t == "all" else [TYPES[t]]

    def doctor(self, cl):
        flights, lu = cl.board("Arrive", "Domestic")
        return bool(flights), f"({len(flights)} domestic arrivals on the board, updated {lu}; keyless /api/flights JSON)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for item, obs in _rows(cl, self._dirs(args), self._types(args)):
            e = item.extra
            hay = f"{e.get('flight_no', '')} {e.get('route', '')} {e.get('airline', '')} {' '.join(e.get('codeshares', []))}".lower()
            if not t or t in hay:
                out.append((item, obs))
        return out

    def fetch(self, cl, item_id):
        parts = str(item_id).split("|")
        if len(parts) != 4:
            return None
        dir_val, type_val, flight_no, scheduled = parts
        flights, lu = cl.board(dir_val, type_val)
        for fl in flights:
            nums = [str(n) for n in (fl.get("flightNumbers") or []) if n]
            if nums and nums[0] == flight_no and (fl.get("scheduled", "") or "") == scheduled:
                return _build(fl, dir_val, type_val, lu)
        return None

    def is_deal(self, obs):
        if obs.flags.get("cancelled") or obs.flags.get("delayed"):
            return True
        d = obs.price_cents
        return d is not None and d >= DELAY_MIN

    def deal_line(self, item, obs):
        f = obs.flags
        if f.get("cancelled"):
            tag = "CANCELLED"
        else:
            d = obs.price_cents
            tag = f"+{d}m late" if (d is not None and d > 0) else (f.get("status") or "delayed")
        est = f.get("estimate") or ""
        when = f"sched {_clock(f.get('scheduled', ''))}" + (f" -> est {_clock(est)}" if est else "")
        return f"{item.name}  {when}  {tag}".strip()

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        sched = f.get("scheduled", "") or item.extra.get("scheduled", "")
        status = f.get("status") or ""
        if not status:
            d = obs.price_cents if obs else None
            status = (f"+{d}m late" if d > 0 else "on time") if d is not None else ""
        return f"{_clock(sched):>10}  {_clock(f.get('estimate', '')):>8}  {status[:11]:<11}  {item.extra.get('route', '')}"

    def format_item(self, item, obs):
        e = item.extra
        cs = e.get("codeshares") or []
        lines = [f"  flight   : {e.get('flight_no', '')}" + (f"  (codeshare: {', '.join(cs)})" if cs else ""),
                 f"  airline  : {e.get('airline', '')}",
                 f"  route    : {e.get('route', '')}  ({'from' if e.get('direction') == 'Arrive' else 'to'})",
                 f"  board    : {e.get('direction', '')}  {e.get('type', '')}",
                 f"  scheduled: {e.get('scheduled', '')}"]
        if obs:
            f = obs.flags
            lines.append(f"  estimate : {f.get('estimate') or '(none yet)'}")
            d = obs.price_cents
            delay = "n/a" if d is None else ("on time" if d == 0 else (f"{d} min late" if d > 0 else f"{-d} min early"))
            lines.append(f"  delay    : {delay}")
            lines.append(f"  gate     : {f.get('gate') or '-'}")
            lines.append(f"  status   : {f.get('status') or '(scheduled)'}")
            lines.append(f"  updated  : {f.get('last_updated', '')}")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = ChcFlightsSource()
