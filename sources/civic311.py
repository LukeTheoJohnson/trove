"""civic311 - municipal 311 service-request backlog via keyless city Socrata open-data portals.

US cities publish their 311 service requests (potholes, noise, graffiti, downed trees, ...) as keyless
Socrata datasets - open data built for civic reuse = sanctioned -> trove. Each request has an id, a
type, an open/closed status, a created timestamp and a location. This is the multi-city driver for that
class: one shared model, one city = a config row + a small field adapter (Socrata column names differ
per city). `--cc` picks the city. Opens the **civic & government** domain and the **queue / wait-time**
mechanic - a request sitting in the municipal backlog is a job waiting in a queue, a shape trove had no
source for.

The timeline value is the request *lifecycle*: it appears Open, waits in the queue, then flips Closed
when the city resolves it - and the time it spent waiting is un-rebuildable once resolved (the city
serves the current state; no public archive keeps the age-in-queue trajectory). `price_cents` = the
request's **age in hours** since it was created (the wait clock); `qty` = a status ordinal
(open 1 / closed 3), so the core's `drops` never fires - the resolution shows up as the status flipping
in flags on the next poll. A "deal" ("stale") = a request still Open after 7+ days (a job stuck in the
backlog). Default `search` lists the *oldest open* requests - the front of the queue - so the board is
the real backlog; `search <term>` full-text-filters by request type.

Model: one Item per request (join key = composite `city:requestid`); `fetch` re-queries one request by
id (it stays queryable after it closes, so a poll catches the Open->Closed flip). Cities: nyc / chicago
/ sf. A pass is one memoized Socrata GET per city.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

STALE_HRS = 168    # still open after 7 days = a stuck request


def _norm(status):
    return "closed" if str(status or "").strip().lower() in {"closed", "completed"} else "open"


def _nyc(r):
    return {"id": r.get("unique_key"), "type": safe(r.get("complaint_type") or ""),
            "desc": safe(r.get("descriptor") or ""), "status": r.get("status") or "",
            "created": r.get("created_date") or "", "agency": safe(r.get("agency") or ""),
            "where": safe(r.get("incident_address") or r.get("borough") or "")}


def _chicago(r):
    return {"id": r.get("sr_number"), "type": safe(r.get("sr_type") or ""),
            "desc": safe(r.get("sr_short_code") or ""), "status": r.get("status") or "",
            "created": r.get("created_date") or "", "agency": safe(r.get("owner_department") or ""),
            "where": safe(r.get("street_address") or r.get("community_area") or "")}


def _sf(r):
    return {"id": r.get("service_request_id"), "type": safe(r.get("service_name") or ""),
            "desc": safe(r.get("service_subtype") or ""), "status": r.get("status_description") or "",
            "created": r.get("requested_datetime") or "", "agency": safe(r.get("agency_responsible") or ""),
            "where": safe(r.get("address") or r.get("analysis_neighborhood") or "")}


# city -> (label, host, resource, date column, open-clause, id column, field adapter).
CITIES = {
    "nyc":     ("New York City 311", "data.cityofnewyork.us", "erm2-nwe9", "created_date",
                "status='Open'", "unique_key", _nyc),
    "chicago": ("Chicago 311", "data.cityofchicago.org", "v6vf-nfxy", "created_date",
                "status='Open'", "sr_number", _chicago),
    "sf":      ("San Francisco 311", "data.sfgov.org", "vw6y-z8j6", "requested_datetime",
                "status_description='Open'", "service_request_id", _sf),
}


def _age_hours(created):
    try:
        c = datetime.fromisoformat(str(created)[:19]).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return max(0, int((datetime.now(timezone.utc) - c).total_seconds() // 3600))


def _build(city, rec):
    d = CITIES[city][6](rec)
    if not d.get("id"):
        return None
    rid = str(d["id"])
    age = _age_hours(d.get("created"))
    norm = _norm(d.get("status"))
    label = f"{d['type']}{(' - ' + d['desc']) if d.get('desc') else ''}"
    item = Item(f"{city}:{rid}", name=safe(label or rid), subtitle=safe(d.get("where") or ""),
                category=CITIES[city][0],
                extra={"city": city, "request_id": rid, "where": safe(d.get("where") or ""),
                       "agency": d.get("agency") or ""})
    obs = Obs(price_cents=age, qty=(3 if norm == "closed" else 1),
              flags={"city": city, "type": d.get("type") or "", "status": d.get("status") or "",
                     "status_norm": norm, "created": d.get("created") or "",
                     "age_hours": age, "agency": d.get("agency") or ""})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.city = cc if cc in CITIES else "nyc"
        self.s = retry_session()

    def _get(self, city, params):
        _, host, res, *_ = CITIES[city]
        r = self.s.get(f"https://{host}/resource/{res}.json", params=params,
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or []

    def backlog(self, city, term, limit):
        _, _, _, datecol, openc, _, _ = CITIES[city]
        # bound to the last 30 days: the genuine current backlog, not never-closed zombie records.
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
        params = {"$where": f"{openc} AND {datecol} > '{since}'",
                  "$order": f"{datecol} ASC", "$limit": min(limit, 100)}
        if (term or "").strip():
            params["$q"] = term.strip()
        return self._get(city, params)

    def by_id(self, city, rid):
        idcol = CITIES[city][5]
        recs = self._get(city, {"$where": f"{idcol}='{rid}'", "$limit": 1})
        return recs[0] if recs else None


class Civic311Source(Source):
    name = "civic311"
    id_label = "CITY:REQUEST"
    cc_default = "nyc"          # city: nyc|chicago|sf
    deal_label = "stale"        # still open after 7+ days
    search_limit_default = 25
    search_header = f"{'AGE_D':>5}  {'STATUS':<8}  REQUEST"

    def client(self, args):
        return _Client(getattr(args, "cc", "nyc"))

    def doctor(self, cl):
        rows = cl.backlog(cl.city, "", 1)
        return rows is not None, f"(oldest-open backlog live for '{cl.city}'; keyless Socrata 311)"

    def search(self, cl, term, args):
        city = getattr(args, "cc", None) or self.cc_default
        city = city if city in CITIES else self.cc_default
        out = [b for b in (_build(city, r) for r in cl.backlog(city, term, self.search_limit_default * 2)) if b]
        return out

    def fetch(self, cl, item_id):
        city, _, rid = str(item_id).partition(":")
        if not rid or city not in CITIES:
            return None
        rec = cl.by_id(city, rid)
        return _build(city, rec) if rec else None

    def is_deal(self, obs):
        f = obs.flags
        return f.get("status_norm") == "open" and isinstance(f.get("age_hours"), int) and f["age_hours"] >= STALE_HRS

    def deal_line(self, item, obs):
        d = (obs.flags.get("age_hours") or 0) // 24
        return f"open {d}d  {item.name}  [{obs.flags.get('city')}]  {item.extra.get('where') or ''}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        age = f.get("age_hours")
        d = f"{age // 24}" if isinstance(age, int) else "?"
        return f"{d:>5}  {(f.get('status') or '?')[:8]:<8}  {item.name[:56]}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  city     : {item.category}  (request {e.get('request_id')})",
                 f"  type     : {item.name}",
                 f"  where    : {e.get('where') or '?'}   agency {e.get('agency') or '?'}"]
        if obs:
            f = obs.flags
            age = f.get("age_hours")
            wait = f"{age // 24}d {age % 24}h" if isinstance(age, int) else "?"
            lines.append(f"  status   : {f.get('status') or '?'}   (open {wait})")
            lines.append(f"  created  : {f.get('created') or '?'}")
        return lines


SOURCE = Civic311Source()
