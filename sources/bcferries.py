"""bcferries - live BC Ferries sailing capacity (how full each sailing is), keyless.

BC Ferries runs the passenger/vehicle ferries across coastal British Columbia. The community-run
bcferriesapi.ca wraps its live data: `GET /api/` returns the whole board keyed by departure ->
destination terminal, each with today's sailings and, per sailing, how full it is - overall `fill`,
`carFill`, `oversizeFill` (percent), plus vessel + cancellation status. The host serves no robots.txt
(404 = unfenced) and the API is published for reuse = sanctioned -> trove. A **scarcity** source in
the eventcinemas / parking / bikeshare family, for ferries.

The timeline value is a sailing's **fill trajectory**: a popular summer sailing fills from empty to
100% (bumped to standby) in the hours before departure, and no one archives that per-sailing fill
curve - the snapshot is the only record. `price_cents` = the sailing's **fill percent** (so the core's
`drops` = a sailing *emptying* - a cancellation reshuffle or capacity added); `qty` = the car-deck
fill percent. A "deal" ("fullrisk") = a non-cancelled sailing at >= 80% full (nearly booked out - go
now or risk waiting for the next one). Vessel + oversize/car split + cancellation ride in flags.

Model: one Item per sailing (join key = composite `DEP-DEST:time`, e.g. `TSA-SWB:9:00 am`, so the
scheduled slot's fill is a coherent series); one memoized GET serves the whole board; `fetch` rescans
for the sailing (a sailing gone from today's board = its day ended). `search <term>` filters by
route/terminal (pass "" to list the board); `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

FEED = "https://www.bcferriesapi.ca/api/"
FULL_RISK = 80    # a sailing >= this % full = nearly booked out
# common terminal codes -> readable names (fall back to the code)
TERMINALS = {
    "TSA": "Tsawwassen", "SWB": "Swartz Bay", "HSB": "Horseshoe Bay", "NAN": "Departure Bay",
    "DUK": "Duke Point", "LNG": "Langdale", "BOW": "Bowen Island", "FUL": "Fulford Harbour",
    "OTB": "Otter Bay", "SGI": "Southern Gulf Islands", "POB": "Pender Island", "VES": "Vesuvius Bay",
    "CFT": "Crofton", "CHM": "Chemainus", "THT": "Thetis Island", "PST": "Powell River",
    "CMX": "Comox", "TEX": "Texada Island", "EAR": "Earls Cove", "SLT": "Saltery Bay",
}


def _term(code):
    return TERMINALS.get(code, code)


def _to_pct(v):
    return int(v) if isinstance(v, (int, float)) else None


def _build(dep, dest, s):
    time = str(s.get("time") or "").strip()
    sid = f"{dep}-{dest}:{time}"
    fill = _to_pct(s.get("fill"))
    cancelled = bool(s.get("isCancelled"))
    route = f"{_term(dep)} -> {_term(dest)}"
    item = Item(sid, name=f"{route}  {time}", subtitle=route, category=f"{dep}-{dest}",
                extra={"dep": dep, "dest": dest, "dep_name": _term(dep), "dest_name": _term(dest),
                       "time": time, "arrival": s.get("arrivalTime") or ""})
    obs = Obs(price_cents=fill, qty=_to_pct(s.get("carFill")),
              flags={"fill": fill, "car_fill": _to_pct(s.get("carFill")),
                     "oversize_fill": _to_pct(s.get("oversizeFill")), "cancelled": cancelled,
                     "vessel": safe(s.get("vesselName") or ""), "vessel_status": safe(s.get("vesselStatus") or ""),
                     "time": time, "arrival": s.get("arrivalTime") or "", "route": route})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._sailings = None

    def sailings(self):
        """[(dep, dest, sailing), ...] flattened from the nested board, memoized."""
        if self._sailings is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            board = r.json() or {}
            out = []
            for dep, dests in board.items():
                if not isinstance(dests, dict):
                    continue
                for dest, info in dests.items():
                    for s in ((info or {}).get("sailings") or []):
                        out.append((dep, dest, s))
            self._sailings = out
        return self._sailings


class BcFerriesSource(Source):
    name = "bcferries"
    id_label = "ROUTE:TIME"
    cc_default = "bc"        # unused
    deal_label = "fullrisk"  # non-cancelled sailing >= 80% full
    search_limit_default = 40
    search_header = f"{'FILL':>5}  {'CAR':>4}  SAILING"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        s = cl.sailings()
        return bool(s), f"({len(s)} sailings on the board today; keyless bcferriesapi.ca)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for dep, dest, s in cl.sailings():
            item, obs = _build(dep, dest, s)
            hay = f"{obs.flags.get('route', '')} {dep} {dest} {item.extra.get('time', '')}".lower()
            if not t or t in hay:
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents if io[1].price_cents is not None else -1))
        return out

    def fetch(self, cl, item_id):
        for dep, dest, s in cl.sailings():
            if f"{dep}-{dest}:{str(s.get('time') or '').strip()}" == str(item_id):
                return _build(dep, dest, s)
        return None

    def is_deal(self, obs):
        f = obs.flags
        return (not f.get("cancelled")) and isinstance(f.get("fill"), int) and f["fill"] >= FULL_RISK

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{f.get('fill')}% full ({f.get('car_fill')}% cars)  {item.name}  [{f.get('vessel') or '?'}]"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        if f.get("cancelled"):
            return f"{'CXL':>5}  {'':>4}  {item.name}"
        return f"{(str(f.get('fill')) + '%' if f.get('fill') is not None else '?'):>5}  {(str(f.get('car_fill')) + '%' if f.get('car_fill') is not None else '?'):>4}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  route    : {e.get('dep_name')} -> {e.get('dest_name')}   ({e.get('dep')}-{e.get('dest')})",
                 f"  sailing  : {e.get('time')}  ->  {e.get('arrival') or '?'}"]
        if obs:
            f = obs.flags
            if f.get("cancelled"):
                lines.append("  status   : CANCELLED")
            lines.append(f"  fill     : {f.get('fill')}% overall   {f.get('car_fill')}% car deck   {f.get('oversize_fill')}% oversize")
            lines.append(f"  vessel   : {f.get('vessel') or '?'}   {f.get('vessel_status') or ''}".rstrip())
        return lines


SOURCE = BcFerriesSource()
