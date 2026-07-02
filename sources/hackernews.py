"""hackernews - Hacker News front-page rank drift via the official keyless Firebase API.

Hacker News is the tech industry's attention market; a story's life is a few hours of climbing and
sliding down the front page. The official API (github.com/HackerNews/API) is keyless and served
from `hacker-news.firebaseio.com`, whose robots.txt explicitly allows exactly the paths the API
uses (`Allow: /*.json$`) = sanctioned -> trove. New genre for trove: attention & rank - the tracked
value is *where the crowd's eyeballs are*, not a price.

The ephemeral thing this source hoards is a story's **rank/points trajectory**: rank 27 -> 9 -> 3
-> gone, with score and comment count riding along. The API only ever serves the *current* state;
nothing official archives the minute-by-minute climb (third parties snapshot front-page membership
or final scores, not the trajectory), so the series is honestly **med** - partially reconstructable
elsewhere, but the fine-grained drift is yours alone.

Model: one Item per story (join key = the HN story id). `price_cents` = **rank * 100** (centi-rank,
rank 1 = the top slot), so the core's `drops` = a story *climbing* the front page; when it falls off
the top-500 list the rank goes None and the obs ride on `qty` = comment count (`descendants`).
Deal "front" = a story in the top 10. money() cosmetically renders centi-rank as dollars in the two
core-hardcoded spots (rank 3 prints as "$3.00"; geonet/metno precedent); the rich views show "#3".

`search` scans the current top-30 (the front page) and filters by title/author/domain - each story
is one lightweight GET, spaced politely and memoized so a pass is bounded; `item`/`poll` re-fetch
one story by id plus the memoized rank list.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

V0 = "https://hacker-news.firebaseio.com/v0"
SCAN = 30           # the front page: how deep `search` looks
FRONT_RANK = 10     # deal = a story in the top 10


def _build(story, rank):
    sid = story.get("id")
    if sid is None:
        return None
    title = safe(story.get("title") or "")
    by = story.get("by") or ""
    url = story.get("url") or ""
    domain = urlparse(url).netloc.removeprefix("www.") if url else "news.ycombinator.com"
    posted = story.get("time")
    age_h = round((time.time() - posted) / 3600, 1) if posted else None
    score = story.get("score")
    comments = story.get("descendants")
    item = Item(str(sid), name=title, subtitle=f"by {by}", category=domain,
                extra={"title": title, "by": by, "url": url, "domain": domain,
                       "posted": (datetime.fromtimestamp(posted, timezone.utc).strftime("%Y-%m-%d %H:%M")
                                  if posted else ""),
                       "hn_url": f"https://news.ycombinator.com/item?id={sid}"})
    obs = Obs(price_cents=(rank * 100 if rank else None), qty=comments,
              flags={"rank": rank, "score": score, "comments": comments, "by": by,
                     "age_h": age_h, "type": story.get("type") or ""})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._top = None    # the ranked id list; one GET serves a whole search/poll pass
        self._items = {}    # id -> story dict

    def _get(self, path):
        r = self.s.get(f"{V0}/{path}", headers={"Accept": "application/json", "User-Agent": UA},
                       timeout=40)
        r.raise_for_status()
        return r.json()

    def top(self):
        if self._top is None:
            self._top = self._get("topstories.json") or []
        return self._top

    def rank(self, sid):
        try:
            return self.top().index(int(sid)) + 1
        except (ValueError, TypeError):
            return None

    def story(self, sid):
        sid = int(sid)
        if sid not in self._items:
            self._items[sid] = self._get(f"item/{sid}.json")
        return self._items[sid]


class HackerNewsSource(Source):
    name = "hackernews"
    id_label = "STORY"
    cc_default = "global"       # unused; the story id is the key
    deal_label = "front"        # a story in the top 10
    search_limit_default = 30
    search_header = f"{'RANK':>5}  {'SCORE':>6}  {'CMTS':>5}  {'AGE':>6}  TITLE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        top = cl.top()
        return bool(top), f"({len(top)} ranked stories; keyless official HN Firebase API)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        rows = []
        for i, sid in enumerate(cl.top()[:SCAN]):
            story = cl.story(sid)
            if not story:
                continue
            built = _build(story, i + 1)
            if not built:
                continue
            item, obs = built
            hay = f"{item.extra.get('title', '')} {item.extra.get('by', '')} {item.extra.get('domain', '')}".lower()
            if not t or t in hay:
                rows.append(built)
            time.sleep(0.1)                 # polite: one lightweight GET per story, never a burst
        return rows

    def fetch(self, cl, item_id):
        try:
            story = cl.story(item_id)
        except ValueError:
            return None
        if not story:
            return None
        return _build(story, cl.rank(item_id))

    def is_deal(self, obs):
        rank = obs.flags.get("rank")
        return rank is not None and rank <= FRONT_RANK

    def deal_line(self, item, obs):
        f = obs.flags
        return (f"#{f.get('rank', '?')}  score {f.get('score', '?')}  "
                f"{f.get('comments', '?')} comments  ({f.get('age_h', '?')}h)  {item.name}")

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        rank = f.get("rank")
        age = f.get("age_h")
        return (f"{('#' + str(rank)) if rank else '-':>5}  {f.get('score', '?'):>6}  "
                f"{f.get('comments') if f.get('comments') is not None else '-':>5}  "
                f"{(f'{age:g}h' if age is not None else '?'):>6}  {item.name}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  title    : {item.name}",
                 f"  by       : {e.get('by', '')}  posted {e.get('posted', '')} UTC",
                 f"  domain   : {e.get('domain', '')}"]
        if obs:
            f = obs.flags
            rank = f.get("rank")
            lines.append(f"  rank     : {('#' + str(rank)) if rank else 'off the top-500'}")
            lines.append(f"  score    : {f.get('score', '?')}  comments {f.get('comments', '?')}  age {f.get('age_h', '?')}h")
        if e.get("url"):
            lines.append(f"  url      : {e.get('url')}")
        lines.append(f"  hn       : {e.get('hn_url', '')}")
        return lines


SOURCE = HackerNewsSource()
