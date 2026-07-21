"""usgsvolcano - US volcanoes currently at an elevated alert level via USGS HANS, keyless.

The USGS Volcano Hazards Program publishes its notification service (HANS) keyless at
`volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes` - the list of US volcanoes currently
*above* background (i.e. not GREEN/NORMAL), each with its aviation colour code (GREEN/YELLOW/ORANGE/RED),
its ground alert level (NORMAL/ADVISORY/WATCH/WARNING), the reporting observatory, the volcano number
(vnum) and the notice timestamp. robots.txt is 404 (unfenced) and it is official open data = sanctioned
-> trove. The US complement of `volcano` (NZ GeoNet levels): a status-ordinal hoard on volcanic unrest.

The tracked scalar is the alert *state*: `price_cents` = the aviation colour ordinal * 100
(GREEN=100, YELLOW=200, ORANGE=300, RED=400) so the core's `drops` = a volcano being **downgraded**
(unrest easing), the volcano/nzroads de-escalation pattern; `qty` = None. A "deal" ("elevated") = the
colour code is ORANGE or RED (significant unrest / eruption likely or underway). The ground alert level,
observatory and notice link ride in flags. money() renders the ordinal as '$' in the two hardcoded spots.

Model: one Item per elevated volcano (join key = `vnum`). The feed lists only elevated volcanoes, so a
volcano dropping back to GREEN vanishes (fetch None -> its series ends, the retirement pattern). One
memoized GET serves a pass; `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes"
COLOUR = {"GREEN": 1, "YELLOW": 2, "ORANGE": 3, "RED": 4}
DEAL_COLOURS = {"ORANGE", "RED"}


def _build(v):
    vnum = str(v.get("vnum"))
    colour = (v.get("color_code") or "").upper()
    ordv = COLOUR.get(colour)
    item = Item(vnum, name=safe(v.get("volcano_name") or vnum),
                subtitle=f"{colour} / {v.get('alert_level') or ''}".strip(" /"), category="volcano",
                extra={"observatory": safe(v.get("obs_fullname") or ""), "vnum": vnum,
                       "url": v.get("notice_url") or ""})
    obs = Obs(price_cents=(ordv * 100 if ordv else None), qty=None,
              flags={"colour": colour, "alert_level": (v.get("alert_level") or "").upper(),
                     "observatory": safe(v.get("obs_abbr") or ""), "notice_type": v.get("notice_type_cd") or "",
                     "sent": v.get("sent_utc") or ""})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = None

    def feed(self):
        if self._feed is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._feed = r.json() or []
        return self._feed


class UsgsVolcanoSource(Source):
    name = "usgsvolcano"
    id_label = "VNUM"
    cc_default = "us"        # unused
    deal_label = "elevated"  # aviation colour ORANGE or RED
    search_limit_default = 30
    search_header = f"{'COLOUR':>7}  {'ALERT':<9}  VOLCANO"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        fs = cl.feed()
        return bool(fs), f"({len(fs)} US volcanoes above background; keyless USGS HANS)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for v in cl.feed():
            item, obs = _build(v)
            if not t or t in safe(item.name).lower() or t in obs.flags.get("colour", "").lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        for v in cl.feed():
            if str(v.get("vnum")) == str(item_id):
                return _build(v)
        return None

    def is_deal(self, obs):
        return obs.flags.get("colour") in DEAL_COLOURS

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  {f.get('colour')} / {f.get('alert_level')}  ({f.get('observatory')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{str(f.get('colour') or '?'):>7}  {str(f.get('alert_level') or '?'):<9}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  volcano  : {item.name}  (vnum {e.get('vnum')})"]
        if obs:
            f = obs.flags
            lines.append(f"  colour   : {f.get('colour')}   alert level {f.get('alert_level')}")
            lines.append(f"  observatory: {e.get('observatory') or '?'}   ({f.get('observatory')})")
            lines.append(f"  notice   : {f.get('notice_type')}   {f.get('sent') or '?'}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = UsgsVolcanoSource()
