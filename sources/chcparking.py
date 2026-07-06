"""chcparking - Christchurch (NZ) parking-building live space availability, keyless (CCC SmartView).

Christchurch City Council runs SmartView (smartview.ccc.govt.nz), an official "realtime information"
public service. Its parking view calls a keyless, same-origin endpoint, `GET /api/parking.php`,
returning each central-city parking building with its live `free` (spaces available) + `occupied`
count, an online/offline `status`, and a `park_id`. SmartView is a riot.js SPA that serves no real
robots.txt (the shell 404s it) and the endpoint is the one the council's own page calls = sanctioned
-> trove (the safeswim/avalanche page-called-same-origin class). The NZ member of the **parking**
genre alongside `sgcarpark` (Singapore) - and the NZ live-parking source that's actually keyless
(Auckland Transport's is behind a keyed developer API; most other councils use the private Frogparking
vendor app).

The timeline value is the same un-rebuildable scarcity as sgcarpark: a building drains toward full
through the day and refills at night, and CCC serves only the current snapshot - no queryable per-park
history of free spaces. `price_cents` = `free` spaces * 100 (centi-space), so the core's `drops` = a
building *filling up*; `qty` = capacity (`free` + `occupied`, when both are sane). A "deal" ("fullrisk")
= a reliable building down to <= 20 free spaces (nearly full - park elsewhere). money() renders the
centi-space count as dollars in the two core-hardcoded spots.

The feed is a little rough: it repeats some buildings across several rows (collapsed by `park_id`, first
kept) and an offline/failing sensor can report nonsense (negative `occupied`, an absurd `free`) - those
rows are still logged faithfully but flagged `reliable=False` so they never register as a deal. Model:
one Item per building (join key = `park_id`). `search <term>` filters by building name (pass "" to list
them all, emptiest first); `fetch` scans the memoized feed by id. `--cc` is unused - one Christchurch set.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

FEED = "https://smartview.ccc.govt.nz/api/parking.php"


def _int(v):
    return v if isinstance(v, int) else None


def _build(row):
    pid = str(row.get("park_id", ""))
    free = _int(row.get("free"))
    occ = _int(row.get("occupied"))
    status = row.get("status")
    cap = (free + occ) if (free is not None and occ is not None and occ >= 0) else None
    # a sane reading: non-negative free, non-negative occupied, and free within capacity
    reliable = (free is not None and free >= 0 and occ is not None and occ >= 0
                and (cap is None or free <= cap))
    item = Item(pid, name=safe(row.get("name", pid)).strip() or pid,
                subtitle="Christchurch parking building", category="carpark",
                extra={"park_id": pid})
    obs = Obs(price_cents=(free * 100 if free is not None else None), qty=cap,
              flags={"free": free, "occupied": occ, "capacity": cap,
                     "status": status, "reliable": reliable})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._rows = None

    def parks(self):
        if self._rows is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            rows = r.json()
            # collapse repeated rows per park_id (the feed lists some buildings several times), keep first
            seen, out = set(), []
            for row in (rows if isinstance(rows, list) else []):
                pid = str(row.get("park_id", ""))
                if pid and pid not in seen:
                    seen.add(pid)
                    out.append(row)
            self._rows = out
        return self._rows


class ChcParkingSource(Source):
    name = "chcparking"
    id_label = "CARPARK"
    cc_default = "nz"        # unused; one Christchurch set
    deal_label = "fullrisk"  # <= 20 free spaces (nearly full)
    search_limit_default = 20
    search_header = f"{'FREE':>5}  {'CAP':>5}  {'STATUS':<8}  CARPARK"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        parks = cl.parks()
        return bool(parks), f"({len(parks)} Christchurch parking buildings; keyless CCC SmartView /api/parking)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for row in cl.parks():
            item, obs = _build(row)
            if not t or t in item.name.lower():
                out.append((item, obs))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out

    def fetch(self, cl, item_id):
        for row in cl.parks():
            if str(row.get("park_id")) == str(item_id):
                return _build(row)
        return None

    def is_deal(self, obs):
        f = obs.flags
        return bool(f.get("reliable")) and f.get("free") is not None and f.get("free") <= 20

    def deal_line(self, item, obs):
        f = obs.flags
        cap = f"/{f.get('capacity')}" if f.get("capacity") is not None else ""
        return f"{f.get('free')}{cap} spaces left  {item.name}  (nearly full)"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(f.get('free') if f.get('free') is not None else '?'):>5}  {(f.get('capacity') if f.get('capacity') is not None else '?'):>5}  {safe(f.get('status') or '-'):<8}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  carpark  : {item.name}  ({item.id})"]
        if obs:
            f = obs.flags
            lines.append(f"  free     : {f.get('free')} spaces   capacity {f.get('capacity') if f.get('capacity') is not None else '?'}")
            lines.append(f"  occupied : {f.get('occupied')}   status {f.get('status') or '?'}")
            if not f.get("reliable"):
                lines.append("  note     : sensor reading looks unreliable (flagged, not a deal)")
        return lines


SOURCE = ChcParkingSource()
