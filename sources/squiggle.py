"""squiggle - Squiggle AFL live games and predictions (api.squiggle.com.au), keyless JSON.

Squiggle (api.squiggle.com.au) is a community-maintained Australian Football League (AFL) stats API
serving real-time game scores, predictions, and historical data. The API is keyless and documented
at https://api.squiggle.com.au/ — robots.txt is open (content signals for search/ai use are not
restricted), and the API is published for reuse. Sanctioned -> trove.

The timeline value is a *game's completion progress and score drift*: a match from 0% complete (pre-
game) to 100% (final), with score estimates that may change as games progress. The shared scalar
(price_cents) is the completion percentage * 100 (centi-percent), so `drops` = a game *completing*
(100% reached); for incomplete games it tracks the away/home score difference as a tiebreaker. Once a
game is final, it rides in the feed for 1-2 rounds before aging out, so the per-game progression is
ephemeral — nobody archives the minute-by-minute completion trajectory.

Model: one Item per game occurrence. Join key is composite `{year}|{round}|{id}` (e.g.
`2026|1|38499`), letting search/fetch reconstruct queries. The API returns all games matching
`?q=games;year=Y;round=R`, memoized per (year, round). `search --year YYYY --round NN --team NAME`
picks which game(s) to inspect; the term filters by team (home/away). The is_deal flag marks games
where the status changed (in-progress, final) or score changed significantly.
"""
from __future__ import annotations

from datetime import datetime

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source, safe

HOST = "https://api.squiggle.com.au"
UA_SQUIGGLE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CURRENT_YEAR = 2026
CURRENT_ROUND = 1
COMPLETION_THRESHOLD = 50  # mark deal if completion % crosses this


def _build(game, year, round_num):
    """One game dict -> (Item, Obs). Returns None without required fields."""
    game_id = game.get("id")
    if game_id is None:
        return None

    hteam = safe(game.get("hteam", "") or "")
    ateam = safe(game.get("ateam", "") or "")
    hscore = game.get("hscore", 0) or 0
    ascore = game.get("ascore", 0) or 0
    hgoals = game.get("hgoals", 0) or 0
    agoals = game.get("agoals", 0) or 0
    hbehinds = game.get("hbehinds", 0) or 0
    abehinds = game.get("abehinds", 0) or 0
    complete = game.get("complete", 0) or 0
    venue = safe(game.get("venue", "") or "")
    date_str = game.get("date", "") or ""
    timestr = game.get("timestr", "") or ""
    updated = game.get("updated", "") or ""
    is_final = game.get("is_final", 0)
    is_grand_final = game.get("is_grand_final", 0)
    roundname = game.get("roundname", f"Round {round_num}") or f"Round {round_num}"

    iid = f"{year}|{round_num}|{game_id}"
    item = Item(iid, name=f"{hteam} vs {ateam}".strip(),
                subtitle=f"{venue}  {roundname}".strip(),
                category="AFL",
                extra={"hteam": hteam, "ateam": ateam, "venue": venue,
                       "round": round_num, "year": year, "game_id": game_id,
                       "date": date_str, "roundname": roundname,
                       "is_grand_final": is_grand_final})

    # Completion % as the primary scalar (price_cents = completion * 100)
    completion_pct = int(complete)
    score_diff = abs(hscore - ascore)

    obs = Obs(price_cents=completion_pct,
              qty=score_diff,
              flags={"hscore": hscore, "ascore": ascore, "hgoals": hgoals, "agoals": agoals,
                     "hbehinds": hbehinds, "abehinds": abehinds, "complete": complete,
                     "timestr": timestr, "venue": venue, "date": date_str,
                     "is_final": is_final, "is_grand_final": is_grand_final,
                     "updated": updated, "roundname": roundname})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._cache = {}  # (year, round) -> games list; one GET serves a whole round

    def games(self, year, round_num):
        key = (year, round_num)
        if key in self._cache:
            return self._cache[key]
        url = f"{HOST}/?q=games;year={year};round={round_num}"
        r = self.s.get(url,
                       headers={"User-Agent": UA_SQUIGGLE},
                       timeout=40)
        r.raise_for_status()
        d = r.json() or {}
        games = d.get("games", []) or []
        self._cache[key] = games
        return games


def _rows(cl, year, round_num, team_filter=None):
    out = []
    games = cl.games(year, round_num)
    for game in games:
        # Filter by team if provided
        if team_filter:
            t_lower = team_filter.lower()
            hteam = (game.get("hteam") or "").lower()
            ateam = (game.get("ateam") or "").lower()
            if t_lower not in hteam and t_lower not in ateam:
                continue

        built = _build(game, year, round_num)
        if built:
            out.append(built)
    return out


class SquiggleSource(Source):
    name = "squiggle"
    id_label = "GAME"
    cc_default = "au"
    deal_label = "update"  # a game status/score change or completion
    search_args = [
        ("--year", {"type": int, "default": CURRENT_YEAR,
                    "help": f"AFL season year (default {CURRENT_YEAR})"}),
        ("--round", {"type": int, "default": CURRENT_ROUND,
                     "help": f"round number (default {CURRENT_ROUND})"}),
        ("--team", {"default": "",
                    "help": "filter by team name (home or away)"}),
    ]
    search_limit_default = 300
    search_header = f"{'HOME':>12}  {'AWAY':>12}  {'SCORE':>10}  {'%':>3}  STATUS"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        games = cl.games(CURRENT_YEAR, CURRENT_ROUND)
        if not games:
            return False, f"(no games for {CURRENT_YEAR} round {CURRENT_ROUND}; API: {HOST})"
        first = games[0]
        return bool(first), f"({len(games)} games, round {first.get('roundname', CURRENT_ROUND)}; keyless /api JSON)"

    def search(self, cl, term, args):
        year = getattr(args, "year", CURRENT_YEAR) or CURRENT_YEAR
        round_num = getattr(args, "round", CURRENT_ROUND) or CURRENT_ROUND
        team_filter = getattr(args, "team", "") or ""

        t = (term or "").lower()
        out = []
        for item, obs in _rows(cl, year, round_num, team_filter):
            e = item.extra
            hay = f"{e.get('hteam', '')} {e.get('ateam', '')} {e.get('venue', '')}".lower()
            if not t or t in hay:
                out.append((item, obs))
        return out

    def fetch(self, cl, item_id):
        parts = str(item_id).split("|")
        if len(parts) != 3:
            return None
        try:
            year, round_num, game_id = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return None

        games = cl.games(year, round_num)
        for game in games:
            if game.get("id") == game_id:
                return _build(game, year, round_num)
        return None

    def is_deal(self, obs):
        # A deal is any status change (in-progress, final) or significant score drift
        if obs.flags.get("is_final"):
            return True
        completion = obs.price_cents
        return completion is not None and completion >= COMPLETION_THRESHOLD

    def deal_line(self, item, obs):
        f = obs.flags
        score_str = f"{f.get('hscore', 0)}.{f.get('hbehinds', 0)} - {f.get('ascore', 0)}.{f.get('abehinds', 0)}"
        status = f.get("timestr") or ("FINAL" if f.get("is_final") else "SCHEDULED")
        return f"{item.name}  {score_str}  {status}".strip()

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        hteam = item.extra.get("hteam", "")[:12]
        ateam = item.extra.get("ateam", "")[:12]
        score_str = f"{f.get('hscore', 0)}.{f.get('hbehinds', 0)}-{f.get('ascore', 0)}.{f.get('abehinds', 0)}"
        completion = f.get("complete", 0) or 0
        status = f.get("timestr") or ("FINAL" if f.get("is_final") else "")
        return f"{hteam:>12}  {ateam:>12}  {score_str:>10}  {int(completion):>3}  {status}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  match    : {e.get('hteam', '')} vs {e.get('ateam', '')}",
                 f"  round    : {e.get('roundname', '')}",
                 f"  venue    : {e.get('venue', '')}",
                 f"  date     : {e.get('date', '')}"]
        if obs:
            f = obs.flags
            hscore = f.get('hscore', 0) or 0
            ascore = f.get('ascore', 0) or 0
            hgoals = f.get('hgoals', 0) or 0
            agoals = f.get('agoals', 0) or 0
            hbehinds = f.get('hbehinds', 0) or 0
            abehinds = f.get('abehinds', 0) or 0
            lines.append(f"  home     : {e.get('hteam', '')} {hgoals}.{hbehinds} ({hscore} pts)")
            lines.append(f"  away     : {e.get('ateam', '')} {agoals}.{abehinds} ({ascore} pts)")
            lines.append(f"  status   : {f.get('timestr') or ('FINAL' if f.get('is_final') else 'scheduled')}")
            lines.append(f"  progress : {int(f.get('complete', 0))}% complete")
            lines.append(f"  updated  : {f.get('updated', '')}")
        return lines


SOURCE = SquiggleSource()
