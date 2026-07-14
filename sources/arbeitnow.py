"""arbeitnow - live job-board listings (Europe / remote) via the keyless Arbeitnow API.

Arbeitnow aggregates developer/tech jobs across Europe and remote, and publishes them through a free
keyless API - `GET /api/job-board-api` returns the latest ~100 postings (slug, title, company,
location, remote flag, tags, job types, created_at), paginated by `?page=`, refreshed hourly. robots
allows the api path (it fences only apply/tracking paths) and the API exists for public reuse =
sanctioned -> trove. Opens the **jobs & labour** domain - a ROADMAP Axis-A white space trove had no
source for.

The timeline value is the **listing lifecycle**: a role is posted, sits on the board, then drops off
when it's filled or expires - and how long it stayed (a time-to-fill proxy) plus what got posted when
is never archived (Arbeitnow serves only the current window). The un-rebuildable hoard is the same
appear->vanish shape as `turners`/`reverb`/`civic311`. There is no price, so `price_cents` = the
posting's **age in hours** since `created_at` (its time-on-board); `qty` = the tag count. A "deal"
("fresh") = a posting created in the last 48 hours (a new opening). money() renders age-hours as $ in
the two core-hardcoded spots; the rich views show company/location/tags.

Model: one Item per posting (join key = `slug`); one memoized GET serves a pass; `fetch` rescans the
feed for a slug (a slug gone from the feed = filled/expired = its series ends). `search <term>` filters
by title/company/tags/location (pass "" to list the latest); `--cc` is unused.
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

FEED = "https://www.arbeitnow.com/api/job-board-api"
FRESH_HRS = 48    # posted within this many hours = "fresh"


def _age_hours(created):
    if not isinstance(created, (int, float)):
        return None
    return max(0, int((datetime.now(timezone.utc).timestamp() - created) // 3600))


def _build(j):
    slug = str(j.get("slug") or "")
    tags = j.get("tags") or []
    jtypes = j.get("job_types") or []
    loc = safe(j.get("location") or "")
    remote = bool(j.get("remote"))
    age = _age_hours(j.get("created_at"))
    item = Item(slug, name=safe(j.get("title") or slug),
                subtitle=safe(j.get("company_name") or ""),
                category=("remote" if remote else (loc or "onsite")),
                extra={"company": safe(j.get("company_name") or ""), "location": loc,
                       "remote": remote, "url": j.get("url") or "",
                       "tags": ",".join(safe(t) for t in tags),
                       "job_types": ",".join(safe(t) for t in jtypes)})
    obs = Obs(price_cents=age, qty=len(tags),
              flags={"company": safe(j.get("company_name") or ""), "location": loc, "remote": remote,
                     "age_hours": age, "created_at": j.get("created_at"),
                     "tags": ",".join(safe(t) for t in tags),
                     "job_types": ",".join(safe(t) for t in jtypes)})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._jobs = None

    def jobs(self):
        if self._jobs is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._jobs = (r.json() or {}).get("data") or []
        return self._jobs


class ArbeitnowSource(Source):
    name = "arbeitnow"
    id_label = "SLUG"
    cc_default = "eu"        # unused
    deal_label = "fresh"     # posted within the last 48 hours
    search_limit_default = 25
    search_header = f"{'AGE_H':>5}  {'REMOTE':<6}  ROLE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        jobs = cl.jobs()
        return bool(jobs), f"({len(jobs)} live postings; keyless Arbeitnow job-board-api)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for j in cl.jobs():
            item, obs = _build(j)
            hay = (f"{item.name} {obs.flags.get('company', '')} {obs.flags.get('location', '')} "
                   f"{obs.flags.get('tags', '')}").lower()
            if not t or t in hay:
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out

    def fetch(self, cl, item_id):
        for j in cl.jobs():
            if str(j.get("slug") or "") == str(item_id):
                return _build(j)
        return None    # gone from the feed = filled/expired; the series ends

    def is_deal(self, obs):
        a = obs.flags.get("age_hours")
        return isinstance(a, int) and a <= FRESH_HRS

    def deal_line(self, item, obs):
        f = obs.flags
        r = " [remote]" if f.get("remote") else ""
        d = (f.get("age_hours") or 0)
        return f"{d}h old  {item.name}  @ {f.get('company') or '?'}{r}  ({f.get('location') or '?'})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        age = f.get("age_hours")
        return (f"{(age if age is not None else '?'):>5}  {('yes' if f.get('remote') else 'no'):<6}  "
                f"{item.name[:52]}  @ {f.get('company') or '?'}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  role     : {item.name}",
                 f"  company  : {e.get('company') or '?'}   ({'remote' if e.get('remote') else e.get('location') or '?'})",
                 f"  tags     : {e.get('tags') or '-'}",
                 f"  types    : {e.get('job_types') or '-'}"]
        if obs:
            a = obs.flags.get("age_hours")
            lines.append(f"  age      : {a if a is not None else '?'} h on board")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = ArbeitnowSource()
