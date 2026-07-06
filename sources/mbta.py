"""mbta - Boston MBTA (the "T") live service alerts, keyless JSON:API.

The Massachusetts Bay Transportation Authority publishes the official V3 API at api-v3.mbta.com (a
JSON:API service; an API key only raises the rate limit above the keyless tier). `GET /alerts` returns
every current service alert across the subway, bus, commuter rail, ferry and access services, each
with a `severity` (0-10), an `effect` (DELAY / SHUTTLE / SUSPENSION / STATION_CLOSURE / DETOUR /
CANCELLATION ...), a `cause`, a `lifecycle` (NEW / ONGOING / UPCOMING), the informed routes/stops, and
the active period. The API host has no robots.txt (404 = unfenced, SWPC class) and the service is
documented for public reuse = sanctioned -> trove. The transit-alert twin of `tfl` (which hoards the
per-line status *ordinal*); mbta hoards the discrete *alerts* themselves.

The timeline value is the alert's lifecycle: a disruption is posted, its severity/effect are revised,
and then it clears - and the MBTA serves only the current set, with no queryable history of an alert's
severity arc or how long it lasted. `price_cents` = `severity` * 100 (0-10, higher = worse), so the
core's `drops` = an alert's severity *easing*; `qty` = the number of routes it informs. An alert
vanishing from the feed = resolved = that alert's series ends (the `nzroads` retirement contract). A
"deal" ("disruption") = a serious effect (suspension / shuttle / cancellation / station or full
closure) or severity >= 7. money() renders the centi-severity as dollars in the two core-hardcoded
spots; the rich views show the effect + header.

Model: one Item per alert (join key = the MBTA alert `id`). `search <term>` filters the current alerts
by header/route (pass "" to list them all, most-severe first); `fetch` reads one alert by id. `--cc`
is unused - the MBTA is one network.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://api-v3.mbta.com"
SERIOUS = {"SUSPENSION", "SHUTTLE", "CANCELLATION", "STATION_CLOSURE", "NO_SERVICE",
           "SERVICE_CHANGE", "SNOW_ROUTE"}


def _routes(attrs):
    out = []
    for ent in attrs.get("informed_entity") or []:
        r = ent.get("route")
        if r and r not in out:
            out.append(r)
    return out


def _build(row):
    aid = str(row.get("id", ""))
    a = row.get("attributes") or {}
    sev = a.get("severity")
    routes = _routes(a)
    item = Item(aid, name=safe(a.get("short_header") or a.get("header") or aid)[:90],
                subtitle="MBTA service alert", category="alert",
                extra={"url": a.get("url") or "https://www.mbta.com/alerts",
                       "service_effect": safe(a.get("service_effect", ""))})
    obs = Obs(price_cents=(sev * 100 if isinstance(sev, int) else None),
              qty=len(routes) or None,
              flags={"severity": sev, "effect": a.get("effect"), "cause": a.get("cause"),
                     "lifecycle": a.get("lifecycle"), "routes": routes[:12],
                     "header": safe(a.get("header", ""))[:200]})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._alerts = None

    def alerts(self):
        if self._alerts is None:
            r = self.s.get(f"{BASE}/alerts", params={"sort": "-severity", "page[limit]": 200},
                           headers={"Accept": "application/vnd.api+json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._alerts = (r.json() or {}).get("data") or []
        return self._alerts

    def alert(self, aid):
        r = self.s.get(f"{BASE}/alerts/{aid}",
                       headers={"Accept": "application/vnd.api+json", "User-Agent": UA}, timeout=40)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return (r.json() or {}).get("data")


class MbtaSource(Source):
    name = "mbta"
    id_label = "ALERT"
    cc_default = "us"        # unused; the MBTA is one network
    deal_label = "disruption"
    search_limit_default = 30
    search_header = f"{'SEV':>3}  {'EFFECT':<16}  {'ROUTES':<18}  ALERT"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        al = cl.alerts()
        return bool(al), f"({len(al)} current MBTA alerts; keyless V3 JSON:API)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for row in cl.alerts():
            item, obs = _build(row)
            hay = f"{item.name} {' '.join(obs.flags.get('routes') or [])}".lower()
            if not t or t in hay:
                out.append((item, obs))
        return out

    def fetch(self, cl, item_id):
        row = cl.alert(item_id)
        return _build(row) if row else None

    def is_deal(self, obs):
        sev = obs.flags.get("severity")
        return (obs.flags.get("effect") in SERIOUS) or (isinstance(sev, int) and sev >= 7)

    def deal_line(self, item, obs):
        rt = ", ".join(obs.flags.get("routes") or [])[:40]
        return f"{obs.flags.get('effect') or '?'} (sev {obs.flags.get('severity')})  {rt}  - {item.name}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        rt = ", ".join(f.get("routes") or [])[:18]
        return f"{(f.get('severity') if f.get('severity') is not None else '?'):>3}  {safe(f.get('effect') or '-'):<16}  {rt:<18}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  alert    : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  effect   : {f.get('effect') or '?'}   severity {f.get('severity')}   ({f.get('lifecycle') or '?'})")
            lines.append(f"  cause    : {f.get('cause') or '?'}")
            if f.get("routes"):
                lines.append(f"  routes   : {', '.join(f.get('routes'))}")
            if f.get("header"):
                lines.append(f"  detail   : {f.get('header')}")
        return lines


SOURCE = MbtaSource()
