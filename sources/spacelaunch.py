"""spacelaunch - upcoming orbital rocket launches + their slipping schedule, keyless (LL2).

The Space Devs run Launch Library 2, the community launch database behind most launch apps, at
ll.thespacedevs.com. `GET /2.2.0/launch/upcoming/` returns the next launches worldwide, each with a
`status` (Go / TBC / TBD / Hold / Success / Failure ...), the `net` (No Earlier Than launch instant)
and its `net_precision`, the pad + location, the mission + orbit, and the launch-service provider.
robots.txt carries only the Cloudflare content-signal *vocabulary* boilerplate (no signal set to `no`,
no Disallow) and the API is a documented public service built for exactly this reuse = sanctioned ->
trove. A new domain for the "space" genre alongside `spaceweather` (Kp) and `sentry` (asteroid risk).

The hoard is the **schedule as-issued and its slip**: a launch's `net` gets pushed back (or the flight
scrubs / goes Hold) repeatedly in the days before it flies, and LL2 serves only the current best
estimate - there is no queryable per-launch history of "when they *said* it would launch, and when".
This is the `metno`/`sentry` revision-drift model applied to launch schedules. `price_cents` = a
**readiness ordinal** * 100 (Go=40, TBC=30, TBD=20, Hold=10; terminal/flown = None), so the core's
`drops` = a launch slipping *off* readiness (Go -> Hold); `qty` = whole hours until `net` (the live
countdown, which the slip visibly resets). Every obs stamps `net` + `net_precision` in flags, so the
as-scheduled series is captured for export even though the core doesn't flag the slip directly. A
"deal" ("go") = a launch that is Go and within 24 hours (imminent, watch tonight). A launch dropping
out of `upcoming` (it flew) ends its series (the `nzroads` retirement contract). money() renders the
centi-ordinal as dollars in the two core-hardcoded spots; the rich views show the status + net.

Model: one Item per launch (join key = the LL2 launch `id`, a UUID). `search <term>` filters the
upcoming set by rocket/mission/provider (pass "" to list them all); `fetch` reads one launch's detail.
`--cc` is unused - launches are global.
"""
from __future__ import annotations

from datetime import datetime, timezone

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://ll.thespacedevs.com/2.2.0/launch"
READY = {"Go": 40, "Go for Launch": 40, "TBC": 30, "To Be Confirmed": 30,
         "TBD": 20, "To Be Determined": 20, "Hold": 10, "On Hold": 10}


def _hours_to(net):
    try:
        dt = datetime.fromisoformat(str(net).replace("Z", "+00:00"))
        return round((dt - datetime.now(timezone.utc)).total_seconds() / 3600)
    except (TypeError, ValueError):
        return None


def _name(v):
    """A field that is a nested object in detail mode but a bare name string in list mode."""
    if isinstance(v, dict):
        return v.get("name") or ""
    return v or ""


def _build(l):
    lid = str(l.get("id", ""))
    status = l.get("status") or {}
    sname = status.get("name") or status.get("abbrev") or ""
    ready = READY.get(status.get("abbrev")) or READY.get(sname)
    net = l.get("net")
    pad = l.get("pad")
    loc = pad.get("location") if isinstance(pad, dict) else l.get("location")
    mission = l.get("mission")
    orbit = _name(mission.get("orbit")) if isinstance(mission, dict) else ""
    provider = l.get("lsp_name") or _name(l.get("launch_service_provider"))
    item = Item(lid, name=safe(l.get("name", lid)), subtitle="orbital launch", category="launch",
                extra={"provider": safe(provider),
                       "pad": safe(_name(pad)), "location": safe(_name(loc)),
                       "url": f"https://thespacedevs.com/launch/{l.get('slug', lid)}"})
    obs = Obs(price_cents=(ready * 100 if ready is not None else None),
              qty=_hours_to(net),
              flags={"status": sname, "abbrev": status.get("abbrev"), "net": net,
                     "net_precision": _name(l.get("net_precision")) or l.get("net_precision"),
                     "provider": safe(provider), "orbit": safe(orbit)})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()

    def _get(self, url):
        r = self.s.get(url, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json()

    def upcoming(self, limit=40):
        return self._get(f"{BASE}/upcoming/?limit={limit}&mode=list").get("results") or []

    def launch(self, lid):
        return self._get(f"{BASE}/{lid}/")


class SpaceLaunchSource(Source):
    name = "spacelaunch"
    id_label = "LAUNCH"
    cc_default = "nz"        # unused; launches are global
    deal_label = "go"        # a launch that is Go and within 24 hours
    search_limit_default = 20
    search_header = f"{'READY':>5}  {'STATUS':<8}  {'~HRS':>5}  LAUNCH"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        ups = cl.upcoming(5)
        return bool(ups), f"({len(ups)}+ upcoming launches; keyless Launch Library 2)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for l in cl.upcoming(args.limit if hasattr(args, "limit") else 40):
            item, obs = _build(l)
            hay = f"{item.name} {item.extra.get('provider', '')}".lower()
            if not t or t in hay:
                out.append((item, obs))
        return out

    def fetch(self, cl, item_id):
        l = cl.launch(item_id)
        return _build(l) if l else None

    def is_deal(self, obs):
        hrs = obs.qty
        return (obs.flags.get("abbrev") in ("Go", "TBC")) and hrs is not None and 0 <= hrs <= 24

    def deal_line(self, item, obs):
        return f"{obs.flags.get('status') or '?'} in ~{obs.qty}h  {item.name}  ({item.extra.get('provider', '?')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        hrs = obs.qty if obs else None
        r = obs.price_cents // 100 if (obs and obs.price_cents is not None) else "?"
        return f"{r:>5}  {safe(f.get('abbrev') or '-'):<8}  {(hrs if hrs is not None else '?'):>5}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  launch   : {item.name}",
                 f"  provider : {e.get('provider') or '?'}",
                 f"  pad      : {e.get('pad') or '?'}  ({e.get('location') or '?'})"]
        if obs:
            lines.append(f"  status   : {obs.flags.get('status') or '?'}")
            lines.append(f"  net      : {obs.flags.get('net') or '?'}  ({obs.flags.get('net_precision') or '?'})   ~{obs.qty}h out")
            if obs.flags.get("orbit"):
                lines.append(f"  orbit    : {obs.flags.get('orbit')}")
        return lines


SOURCE = SpaceLaunchSource()
