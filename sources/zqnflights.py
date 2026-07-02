"""zqnflights - Queenstown Airport live flight board (queenstownairport.co.nz), keyless JSON.

Queenstown (ZQN) is NZ's alpine-resort gateway and its weather-prone runway makes the board the
most disruption-rich in the country - exactly the drift worth hoarding. The public
arrivals/departures page (/flights/arrivals-departures/) is driven by the site's own bundle
(all.bundle.js), which calls two keyless, same-origin JSON endpoints: GET /api/flights/arrivals and
GET /api/flights/departures. robots.txt has zero Disallow lines (only a Sitemap) and the endpoints
are the ones the published page itself calls = sanctioned -> trove. Second aviation source
(chcflights sibling; Auckland = Cloudflare JS challenge, Wellington = robots-fenced data paths,
both previously skipped).

The timeline value is a flight's **delay-drift**: the estimate ticking away from schedule, the
status flipping On Time -> Delayed -> Cancelled, in the hours before it operates - then the board
drops it and nothing public keeps the progression = high. Unlike CHC's weekday-prefixed clock
strings, ZQN serves full ISO date+time pairs (schDate/schTime, estDate/estTime), so the delay is an
honest datetime subtraction with no midnight-wrap heuristic.

No price in aviation, so `price_cents` = **delay in minutes** (estimate - scheduled; signed, 0 =
currently expected on time), the chcflights scalar reuse: the core's `drops` = a flight that
*recovered*. Deal "delay" = a disruption (delayed >= 15 min or cancelled). money() cosmetically
renders the delay as dollars in the two core-hardcoded spots; the rich views show minutes.

Model: one Item per flight occurrence, join key = `<Arrival|Departure>|<flightNo>|<schDate>|
<schTime>` (no by-flight endpoint; the id rebuilds the board query and matches the row -
eventcinemas/turners composite-key trick). flightList[0] is the primary number; codeshares ride in
extra. `search --dir arrivals|departures|all` picks the board(s) (default all = 2 memoized GETs);
the term filters by flight number / city / status.
"""
from __future__ import annotations

from datetime import datetime

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

HOST = "https://www.queenstownairport.co.nz"
REFERER = HOST + "/flights/arrivals-departures/"
DELAY_MIN = 15      # minutes late (or cancelled) = "disruption"
BOARDS = {"arrivals": "Arrival", "departures": "Departure"}


def _dt(date_s, time_s):
    try:
        return datetime.fromisoformat(f"{date_s}T{time_s}")
    except (TypeError, ValueError):
        return None


def _delay(fl):
    """Signed minutes (estimate - scheduled). None when the schedule is unparseable; 0 when there
    is no estimate yet (the board currently expects the flight on time)."""
    s = _dt(fl.get("schDate"), fl.get("schTime"))
    if s is None:
        return None
    e = _dt(fl.get("estDate"), fl.get("estTime"))
    if e is None:
        return 0
    return round((e - s).total_seconds() / 60)


def _hhmm(time_s):
    return (time_s or "")[:5]


def _build(fl, dir_val):
    nums = [str(n) for n in (fl.get("flightList") or []) if n]
    if not nums:
        return None
    flight_no = nums[0]
    sch_date, sch_time = fl.get("schDate") or "", fl.get("schTime") or ""
    status = safe(fl.get("status") or "")
    origin, dest = safe(fl.get("from") or ""), safe(fl.get("destination") or "")
    route = f"{origin} -> {dest}"
    domestic = bool(fl.get("isDomestic"))
    delay = _delay(fl)
    cancelled = "cancel" in status.lower()
    delayed = "delay" in status.lower() or (delay is not None and delay >= DELAY_MIN)

    iid = f"{dir_val}|{flight_no}|{sch_date}|{sch_time}"
    item = Item(iid, name=f"{flight_no}  {route}",
                subtitle=f"{dir_val}  {'domestic' if domestic else 'international'}  sched {sch_date} {_hhmm(sch_time)}",
                category="domestic" if domestic else "international",
                extra={"flight_no": flight_no, "codeshares": nums[1:], "from": origin, "to": dest,
                       "route": route, "direction": dir_val, "domestic": domestic,
                       "scheduled": f"{sch_date} {sch_time}"})
    obs = Obs(price_cents=delay,
              flags={"status": status, "scheduled": f"{sch_date} {sch_time}",
                     "estimate": f"{fl.get('estDate') or ''} {fl.get('estTime') or ''}".strip(),
                     "delay_min": delay, "cancelled": cancelled, "delayed": delayed,
                     "route": route, "direction": dir_val, "domestic": domestic})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._boards = {}   # dir -> flights; one GET serves a whole search/poll pass

    def board(self, dir_val):
        if dir_val not in self._boards:
            path = "arrivals" if dir_val == "Arrival" else "departures"
            r = self.s.get(f"{HOST}/api/flights/{path}",
                           headers={"User-Agent": UA, "Accept": "application/json",
                                    "Referer": REFERER}, timeout=40)
            r.raise_for_status()
            self._boards[dir_val] = r.json() or []
        return self._boards[dir_val]


class ZqnFlightsSource(Source):
    name = "zqnflights"
    id_label = "FLIGHT"
    cc_default = "zqn"      # not used; the board is Queenstown-only
    deal_label = "delay"    # a disrupted flight (delayed >= 15 min or cancelled)
    search_args = [
        ("--dir", {"choices": ["arrivals", "departures", "all"], "default": "all",
                   "help": "which board to pull (default all)"}),
    ]
    search_limit_default = 300   # a board is bounded (~40-80 flights/day); list it, don't truncate
    search_header = f"{'SCHED':>16}  {'EST':>5}  {'STATUS':<12}  ROUTE"

    def client(self, args):
        return _Client()

    def _dirs(self, args):
        d = getattr(args, "dir", "all") or "all"
        return list(BOARDS.values()) if d == "all" else [BOARDS[d]]

    def doctor(self, cl):
        flights = cl.board("Arrival")
        return bool(flights), f"({len(flights)} arrivals on the board; keyless /api/flights JSON)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        rows = []
        for dv in self._dirs(args):
            for fl in cl.board(dv):
                built = _build(fl, dv)
                if not built:
                    continue
                item, obs = built
                e = item.extra
                hay = (f"{e.get('flight_no', '')} {e.get('route', '')} "
                       f"{' '.join(e.get('codeshares', []))} {obs.flags.get('status', '')}").lower()
                if not t or t in hay:
                    rows.append(built)
        return rows

    def fetch(self, cl, item_id):
        parts = str(item_id).split("|")
        if len(parts) != 4 or parts[0] not in BOARDS.values():
            return None
        dir_val, flight_no, sch_date, sch_time = parts
        for fl in cl.board(dir_val):
            nums = [str(n) for n in (fl.get("flightList") or []) if n]
            if (nums and nums[0] == flight_no and (fl.get("schDate") or "") == sch_date
                    and (fl.get("schTime") or "") == sch_time):
                return _build(fl, dir_val)
        return None                          # operated (or dropped); the series ends here

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
        when = f"sched {f.get('scheduled', '')}" + (f" -> est {est}" if est else "")
        return f"{item.name}  {when}  {tag}".strip()

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        sched = f.get("scheduled") or item.extra.get("scheduled", "")
        est = (f.get("estimate") or "").split(" ")[-1]
        return (f"{sched[:16]:>16}  {_hhmm(est):>5}  {(f.get('status') or '')[:12]:<12}  "
                f"{item.extra.get('route', '')}")

    def format_item(self, item, obs):
        e = item.extra
        cs = e.get("codeshares") or []
        lines = [f"  flight   : {e.get('flight_no', '')}" + (f"  (codeshare: {', '.join(cs)})" if cs else ""),
                 f"  route    : {e.get('route', '')}  ({e.get('direction', '')}, {'domestic' if e.get('domestic') else 'international'})",
                 f"  scheduled: {e.get('scheduled', '')}"]
        if obs:
            f = obs.flags
            lines.append(f"  estimate : {f.get('estimate') or '(none yet)'}")
            d = obs.price_cents
            delay = "n/a" if d is None else ("on time" if d == 0 else (f"{d} min late" if d > 0 else f"{-d} min early"))
            lines.append(f"  delay    : {delay}")
            lines.append(f"  status   : {f.get('status') or '(scheduled)'}")
        return lines


SOURCE = ZqnFlightsSource()
