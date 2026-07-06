"""tfl - Transport for London line-status board (tube / DLR / Overground / Elizabeth line), keyless.

Transport for London runs the open Unified API at api.tfl.gov.uk. `GET /Line/Mode/{modes}/Status`
returns the current service status of every line on those modes: a `lineStatuses` list carrying a
`statusSeverity` (0-20) + `statusSeverityDescription` ("Good Service", "Minor Delays", "Severe
Delays", "Part Suspended", ...) and, when degraded, a human `reason`. The API host has no robots.txt
(404 = unfenced, the SWPC class) and the endpoint is the documented public one an `app_key` only
raises the rate limit on = sanctioned -> trove. A transit-status genre-mate for `nzroads` (roads) and
the twin-mechanic to `mbta` (which hoards discrete service *alerts*); tfl hoards the per-line *status
ordinal* itself.

The timeline value is ephemeral and un-rebuildable: a line's status flips Good -> Minor Delays ->
Severe Delays -> Part Suspended and back over a day as incidents come and go, and TfL publishes no
queryable per-line historic status series. `price_cents` = a **health ordinal** * 100 (10 = Good
Service down to 1 = suspended/closed; a line takes the *worst* of its statuses), so the core's `drops`
= a line's service *worsening*; `qty` = the count of active (non-good) statuses. A "deal"
("disruption") = the line is anything other than a clean Good Service right now. money() renders the
centi-ordinal as dollars in the two core-hardcoded spots; the rich views show the status words.

Model: one Item per line (join key = the TfL line id, e.g. "victoria", "elizabeth"). `search <term>`
filters the lines by name (pass "" to list them all); `fetch` reads one line's `/Line/{id}/Status`.
`--cc` is unused - the whole network is one set of lines.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

MODES = "tube,dlr,overground,elizabeth-line,tram"
BASE = "https://api.tfl.gov.uk"
# status description -> health ordinal (higher = healthier, so core `drops` = worsening).
# TfL's numeric statusSeverity is non-monotonic (20 = "Service Closed"), so map the words.
HEALTH = {
    "good service": 10, "no issues": 10, "information": 9, "change of frequency": 7,
    "minor delays": 7, "reduced service": 6, "special service": 6, "bus service": 5,
    "diverted": 4, "severe delays": 4, "part closure": 3, "part closed": 3,
    "part suspended": 3, "planned closure": 2, "exit only": 2,
    "not running": 1, "suspended": 1, "closed": 1, "service closed": 1,
}


def _health(desc, severity):
    h = HEALTH.get((desc or "").strip().lower())
    if h is not None:
        return h
    # unknown wording: fall back on the numeric severity (10 = good baseline)
    try:
        return 8 if int(severity) >= 10 else 4
    except (TypeError, ValueError):
        return 5


def _build(line):
    statuses = line.get("lineStatuses") or []
    worst = None
    reasons = []
    for st in statuses:
        desc = st.get("statusSeverityDescription")
        h = _health(desc, st.get("statusSeverity"))
        if worst is None or h < worst[0]:
            worst = (h, desc)
        if st.get("reason"):
            reasons.append(safe(st.get("reason")))
    if worst is None:
        worst = (5, None)
    health, desc = worst
    active = sum(1 for st in statuses
                 if (st.get("statusSeverityDescription") or "").strip().lower() not in ("good service", "no issues"))
    lid = str(line.get("id", ""))
    item = Item(lid, name=safe(line.get("name", lid)),
                subtitle=f"TfL {safe(line.get('modeName', ''))} line", category="line",
                extra={"mode": line.get("modeName"), "url": f"https://tfl.gov.uk/tube/status/"})
    obs = Obs(price_cents=health * 100, qty=active,
              flags={"status": desc, "health": health, "mode": line.get("modeName"),
                     "reasons": reasons})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()

    def _get(self, path):
        r = self.s.get(BASE + path, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json()

    def lines(self):
        return self._get(f"/Line/Mode/{MODES}/Status")

    def line(self, lid):
        d = self._get(f"/Line/{lid}/Status")
        return d[0] if isinstance(d, list) and d else None


class TflSource(Source):
    name = "tfl"
    id_label = "LINE"
    cc_default = "uk"        # unused; one London network
    deal_label = "disruption"
    search_limit_default = 40
    search_header = f"{'HEALTH':>6}  {'STATUS':<16}  LINE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        lines = cl.lines()
        return bool(lines), f"({len(lines)} TfL lines; keyless Unified API line-status)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for line in cl.lines():
            item, obs = _build(line)
            if not t or t in item.name.lower() or t in str(line.get("id", "")).lower():
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents, io[0].name.lower()))
        return out

    def fetch(self, cl, item_id):
        line = cl.line(item_id)
        return _build(line) if line else None

    def is_deal(self, obs):
        h = obs.flags.get("health")
        return h is not None and h < 10

    def deal_line(self, item, obs):
        why = ("  - " + obs.flags["reasons"][0]) if obs.flags.get("reasons") else ""
        return f"{obs.flags.get('status') or '?'}  {item.name}{why}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        h = f.get("health")
        return f"{(h if h is not None else '?'):>6}  {safe(f.get('status') or '-'):<16}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  line     : {item.name}  ({item.id})",
                 f"  mode     : {item.extra.get('mode', '?')}"]
        if obs:
            lines.append(f"  status   : {obs.flags.get('status') or '?'}  (health {obs.flags.get('health')}/10)")
            for r in (obs.flags.get("reasons") or [])[:2]:
                lines.append(f"  reason   : {r}")
        return lines


SOURCE = TflSource()
