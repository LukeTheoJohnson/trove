"""eventcinemas - Event Cinemas NZ session seat-availability (eventcinemas.co.nz), keyless JSON.

Event Cinemas is NZ's largest cinema chain. Its site is a legacy jQuery/.NET app whose "session
times" view calls a keyless, page-called JSON endpoint, `GET /Cinemas/GetSessions?cinemaIds=<id>&
date=<YYYY-MM-DD>`, returning every movie -> cinema -> session for that day, each session carrying a
live `SeatsAvailable` count. robots.txt fences only `/ticketing/` and `/tickets/` (the seat-picker /
checkout flow) - not the session listing - so this is a page-called, keyless API = sanctioned -> trove,
not a reverse-engineered private endpoint.

The timeline value is `SeatsAvailable` ticking down for a *specific screening* from on-sale to
showtime, then the session vanishes once it's played. That per-session fill-rate (how fast did the
Friday-night IMAX opening sell out) is never archived - the snapshot is the only record, the point of
hoarding it. There is no price in the feed (ticket prices live behind the fenced /ticketing/ flow), so
this is a pure *scarcity* tracker: `qty` carries seats remaining, and a "deal" = a session close to
selling out (grab it now). Mirrors bookme's spaces-remaining model.

Model: one Item per session. The join key is `cinemaId:date:sessionId` (the session id alone can't be
re-fetched - GetSessions is keyed by cinema+date - so the id encodes both, letting fetch/poll rebuild
the query; same composite-key trick as turners/grabone). `--cc <cinemaId>` picks the cinema (default
502 = Queen Street, Auckland); `search --date YYYY-MM-DD` picks the day (default today). Cinema ids
come from the GetSessions response itself (each CinemaModels entry has Id + Name).
"""
from __future__ import annotations

from datetime import date as _date

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

HOST = "https://www.eventcinemas.co.nz"
SEATS_LOW = 20   # <= this many seats left (and > 0) = "selling fast"


def _today():
    return _date.today().isoformat()


def _hhmm(start):
    """'2026-06-24T15:40' -> '15:40'."""
    return start.split("T", 1)[1] if "T" in (start or "") else (start or "")


def _build(mv, cm, ses, cinema_id, date):
    """One movie/cinema/session triple -> (Item, Obs). Returns None without a session id."""
    sid = ses.get("Id")
    if sid is None:
        return None
    seats = ses.get("SeatsAvailable")
    start = ses.get("StartTime", "")
    stype = safe(ses.get("ScreenTypeName") or ses.get("ScreenType") or "")
    screen = safe(ses.get("ScreenName") or "")
    attrs = [a.get("Code") for a in ses.get("Attributes", []) if a.get("Code")]
    mname = safe(mv.get("Name", ""))
    cname = safe(cm.get("Name", ""))
    iid = f"{cinema_id}:{date}:{sid}"

    name = f"{mname} - {stype}" if stype else mname
    item = Item(iid, name=name,
                subtitle=f"{cname}  {_hhmm(start)}".strip(),
                category=cname,
                extra={"movie": mname, "movie_id": mv.get("Id"),
                       "movie_url": HOST + mv.get("MovieUrl", "") if mv.get("MovieUrl") else "",
                       "rating": mv.get("Rating", ""), "cinema": cname, "cinema_id": cinema_id,
                       "screen_type": stype, "screen": screen, "start": start, "date": date,
                       "attributes": attrs, "booking_url": ses.get("BookingUrl", "")})
    obs = Obs(qty=seats,
              flags={"cinema": cname, "cinema_id": cinema_id, "screen_type": stype,
                     "screen": screen, "start": start, "attributes": attrs,
                     "reserved_seating": ses.get("SeatAllocation"),
                     "sold_out": (seats == 0) if seats is not None else None})
    return item, obs


def _rows(data, cinema_id, date):
    """Walk the GetSessions Data block (Movies -> CinemaModels -> Sessions) into (Item, Obs)."""
    out = []
    for mv in (data or {}).get("Movies", []):
        for cm in mv.get("CinemaModels", []):
            for ses in cm.get("Sessions", []):
                built = _build(mv, cm, ses, cinema_id, date)
                if built:
                    out.append(built)
    return out


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._cache = {}   # (cinema, date) -> Data block; one GET serves a whole poll of that day

    def sessions(self, cinema_id, date):
        key = (str(cinema_id), str(date))
        if key in self._cache:
            return self._cache[key]
        r = self.s.get(HOST + "/Cinemas/GetSessions",
                       params=[("cinemaIds", str(cinema_id)), ("date", str(date))],
                       headers={"User-Agent": UA, "Accept": "application/json",
                                "X-Requested-With": "XMLHttpRequest",
                                "Referer": HOST + "/sessions"}, timeout=50)
        r.raise_for_status()
        d = r.json()
        data = d.get("Data", {}) if d.get("Success") else {}
        self._cache[key] = data
        return data


class EventCinemasSource(Source):
    name = "eventcinemas"
    id_label = "SESSION"
    cc_default = "502"          # cinema id; --cc <id> picks another (502 = Queen Street, Auckland)
    deal_label = "sellout risk"  # a session close to selling out
    search_args = [("--date", {"default": None, "help": "session date YYYY-MM-DD (default today)"})]
    search_limit_default = 300  # a cinema-day is bounded (~60 sessions); list the whole day, don't truncate
    search_header = f"{'TIME':>5}  {'SCREEN':<11}  {'SEAT':>4}  MOVIE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = _rows(cl.sessions(self.cc_default, _today()), self.cc_default, _today())
        return bool(rows), f"({len(rows)} sessions at cinema {self.cc_default} today; keyless GetSessions JSON)"

    def search(self, cl, term, args):
        date = getattr(args, "date", None) or _today()
        cinema = args.cc
        t = (term or "").lower()
        out = []
        for item, obs in _rows(cl.sessions(cinema, date), cinema, date):
            hay = f"{item.extra.get('movie', '')} {item.extra.get('screen_type', '')} {item.name}".lower()
            if not t or t in hay:
                out.append((item, obs))
        return out

    def fetch(self, cl, item_id):
        parts = str(item_id).split(":")
        if len(parts) != 3:
            return None
        cinema, date, _sid = parts
        for item, obs in _rows(cl.sessions(cinema, date), cinema, date):
            if str(item.id) == str(item_id):
                return item, obs
        return None

    def is_deal(self, obs):
        q = obs.qty
        return q is not None and 0 < q <= SEATS_LOW

    def deal_line(self, item, obs):
        q = obs.qty
        seats = f"{q} seats left  " if q is not None else ""
        when = (obs.flags.get("start") or "").replace("T", " ")
        return f"{seats}{when}  {item.name}".strip()

    def search_row(self, item, obs):
        """time + screen + seats + movie, so `search` lists a whole day without a per-session item call."""
        e = item.extra
        q = obs.qty if obs else None
        seats = "SOLD" if q == 0 else (str(q) if q is not None else "?")
        screen = e.get("screen_type") or "Original"
        return f"{_hhmm(e.get('start', '')):>5}  {screen:<11}  {seats:>4}  {e.get('movie', '')}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  movie    : {e.get('movie', '')}  ({e.get('rating', '')})".rstrip(),
                 f"  cinema   : {e.get('cinema', '')}",
                 f"  screen   : {e.get('screen_type', '') or e.get('screen', '') or '?'}",
                 f"  start    : {e.get('start', '')}"]
        at = e.get("attributes") or []
        if at:
            lines.append(f"  tags     : {', '.join(at)}")
        if obs:
            q = obs.qty
            seats = "SOLD OUT" if q == 0 else (f"{q} available" if q is not None else "?")
            lines.append(f"  seats    : {seats}")
        lines.append(f"  booking  : {e.get('booking_url', '')}")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = EventCinemasSource()
