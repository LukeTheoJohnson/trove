"""espnscores - live sports scores + game status via ESPN's public scoreboard API, keyless.

ESPN serves its scoreboard data through a keyless public JSON endpoint
`site.api.espn.com/apis/site/v2/sports/<sport>/<league>/scoreboard`: every game in the current window
with its two competitors + scores, and a status (pre / in / post) with clock, period and a
human-readable detail. The api host serves no robots.txt (403 = missing = unfenced, the opensky/S3
class) and it is the same feed espn.com's own pages call = sanctioned -> trove. Deepens **sports &
recreation** (opened by `squiggle`) across many leagues, and hoards the *live game-status trajectory* -
scoreline + clock as a match moves pre -> in-progress -> final - which nobody archives minute by minute.

The tracked scalar is the total points/goals scored: `price_cents` = (home score + away score) * 100 (a
live counter that ratchets up through a match); `qty` = the score margin. A "deal" ("live") = the game
is currently in progress (status state == "in") - i.e. on right now. The individual scores, status
detail, clock and period ride in flags. money() renders the centi-total as '$' in the two hardcoded spots.

Model: one Item per game (join key = the ESPN event id). `--cc` picks the league (default `epl`; also
nba, nfl, mlb, nhl, laliga, ucl, wc). `search <term>` filters by team name; one memoized GET per pass.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://site.api.espn.com/apis/site/v2/sports"
# league slug -> ESPN sport/league path
LEAGUES = {
    "epl": "soccer/eng.1", "laliga": "soccer/esp.1", "seriea": "soccer/ita.1",
    "ucl": "soccer/uefa.champions", "wc": "soccer/fifa.world", "nba": "basketball/nba",
    "nfl": "football/nfl", "mlb": "baseball/mlb", "nhl": "hockey/nhl", "mls": "soccer/usa.1",
}


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _teams(comp):
    """competitors -> {'home': (name, score), 'away': (name, score)}."""
    out = {}
    for c in (comp.get("competitors") or []):
        side = c.get("homeAway") or "?"
        out[side] = (safe((c.get("team") or {}).get("displayName") or ""), _int(c.get("score")))
    return out


def _build(ev):
    comp = (ev.get("competitions") or [{}])[0]
    t = _teams(comp)
    home_n, home_s = t.get("home", ("?", None))
    away_n, away_s = t.get("away", ("?", None))
    status = (ev.get("status") or {}).get("type") or {}
    state = status.get("state") or "?"
    total = (home_s or 0) + (away_s or 0)
    margin = abs((home_s or 0) - (away_s or 0))
    item = Item(str(ev.get("id")), name=safe(ev.get("shortName") or f"{home_n} v {away_n}"),
                subtitle=safe(ev.get("name") or ""), category=state,
                extra={"home": home_n, "away": away_n, "date": ev.get("date") or ""})
    obs = Obs(price_cents=total * 100, qty=margin,
              flags={"home": home_n, "away": away_n, "home_score": home_s, "away_score": away_s,
                     "state": state, "detail": safe(status.get("detail") or status.get("description") or ""),
                     "clock": safe((ev.get("status") or {}).get("displayClock") or ""),
                     "period": (ev.get("status") or {}).get("period"), "completed": status.get("completed")})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.cc = cc if cc in LEAGUES else "epl"
        self.path = LEAGUES[self.cc]
        self.s = retry_session()
        self._events = None

    def events(self):
        if self._events is None:
            r = self.s.get(f"{BASE}/{self.path}/scoreboard",
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._events = (r.json() or {}).get("events") or []
        return self._events


class EspnScoresSource(Source):
    name = "espnscores"
    id_label = "GAME"
    cc_default = "epl"       # league: epl|laliga|seriea|ucl|wc|nba|nfl|mlb|nhl|mls
    deal_label = "live"      # game currently in progress (status state == "in")
    search_limit_default = 30
    search_header = f"{'SCORE':>9}  {'STATE':<5}  GAME"

    def client(self, args):
        return _Client(getattr(args, "cc", "epl"))

    def doctor(self, cl):
        ev = cl.events()
        return bool(ev), f"({len(ev)} {cl.cc} games on the board; keyless ESPN scoreboard)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for ev in cl.events():
            item, obs = _build(ev)
            hay = f"{obs.flags.get('home', '')} {obs.flags.get('away', '')}".lower()
            if not t or t in hay:
                out.append((item, obs))
        return out

    def fetch(self, cl, item_id):
        for ev in cl.events():
            if str(ev.get("id")) == str(item_id):
                return _build(ev)
        return None

    def is_deal(self, obs):
        return obs.flags.get("state") == "in"

    def deal_line(self, item, obs):
        f = obs.flags
        return (f"{f.get('home')} {f.get('home_score')}-{f.get('away_score')} {f.get('away')}  "
                f"{f.get('detail') or f.get('clock') or 'LIVE'}")

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        hs, as_ = f.get("home_score"), f.get("away_score")
        score = f"{hs if hs is not None else '-'}-{as_ if as_ is not None else '-'}"
        return f"{score:>9}  {str(f.get('state') or '?'):<5}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  match    : {e.get('home')} vs {e.get('away')}",
                 f"  date     : {e.get('date')}"]
        if obs:
            f = obs.flags
            lines.append(f"  score    : {f.get('home')} {f.get('home_score')} - {f.get('away_score')} {f.get('away')}")
            lines.append(f"  status   : {f.get('detail') or f.get('state')}   (state {f.get('state')})")
            if f.get("clock"):
                lines.append(f"  clock    : {f.get('clock')}   period {f.get('period')}")
        return lines


SOURCE = EspnScoresSource()
