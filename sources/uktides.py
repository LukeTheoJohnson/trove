"""uktides - live UK coastal tide levels via the Environment Agency flood-monitoring API, keyless.

The Environment Agency publishes real-time water levels (incl. coastal tidal gauges) through its
keyless flood-monitoring API `environment.data.gov.uk/flood-monitoring`. Filtering measures by
`parameter=level&qualifier=Tidal Level` returns each tidal station's latest reading (metres above
Ordnance Datum, mAOD - so values swing negative to positive with the tide). robots.txt explicitly
leaves `/flood-monitoring/` open (it's the same sanctioned Open Government Licence source as `eafloods`)
= sanctioned -> trove. The UK marine twin of `noaatides` (US CO-OPS), deepening the marine & coastal
genre with British tide gauges.

The tracked scalar is the live tide height: `price_cents` = the level in centi-metres mAOD (so the
core's `drops` = the tide *falling*); `qty` = None. Because the tide is cyclical, the interesting event
is a *rise*, invisible to the core's drop logic - so `fetch` pulls the station's last few readings and
sets a `rising` flag; a "deal" ("rising") = the latest level is above the reading ~45 min earlier (an
incoming/flooding tide). money() renders centi-metres as '$' in the two hardcoded spots.

Model: one Item per tidal station (join key = the measure `notation`). One memoized GET lists the board
(latest levels); `fetch` adds one small readings GET for the rising flag. `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

ROOT = "https://environment.data.gov.uk/flood-monitoring"
MEASURES = f"{ROOT}/id/measures"


def _f(v):
    return float(v) if isinstance(v, (int, float)) else None


def _station(label):
    """'Lowestoft - level-tidal_level-Mean-15_min-mAOD' -> 'Lowestoft'."""
    return safe(label or "").split(" - ")[0].strip()


def _build(m, rising=None):
    notation = str(m.get("notation"))
    latest = (m.get("latestReading") or {})
    level = _f(latest.get("value"))
    item = Item(notation, name=_station(m.get("label")), subtitle="UK tidal gauge (mAOD)", category="UK",
                extra={"station_ref": m.get("stationReference") or "", "notation": notation})
    obs = Obs(price_cents=(round(level * 100) if level is not None else None), qty=None,
              flags={"level_m": level, "unit": "mAOD", "measured": latest.get("dateTime") or "",
                     "rising": rising})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._board = None

    def _get(self, url, params=None):
        r = self.s.get(url, params=params, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or {}

    def board(self):
        if self._board is None:
            items = self._get(MEASURES, {"parameter": "level", "qualifier": "Tidal Level",
                                         "_limit": 500}).get("items") or []
            self._board = {str(m.get("notation")): m for m in items if m.get("latestReading")}
        return self._board

    def rising(self, notation):
        """Compare the latest reading to the one ~45 min earlier -> True if the tide is coming in."""
        try:
            rows = self._get(f"{MEASURES}/{notation}/readings",
                             {"_sorted": "", "_limit": 4}).get("items") or []
            vals = [_f(r.get("value")) for r in rows if _f(r.get("value")) is not None]
            if len(vals) >= 2:
                return vals[0] > vals[-1]        # _sorted is newest-first
        except Exception:
            pass
        return None


class UkTidesSource(Source):
    name = "uktides"
    id_label = "STATION"
    cc_default = "uk"        # unused
    deal_label = "rising"    # incoming/flooding tide (latest level above ~45 min earlier)
    search_limit_default = 30
    search_header = f"{'mAOD':>8}  STATION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        b = cl.board()
        return bool(b), f"({len(b)} UK tidal gauges; keyless EA flood-monitoring)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for notation, m in cl.board().items():
            item, obs = _build(m)
            if not t or t in safe(item.name).lower():
                out.append((item, obs))
        out.sort(key=lambda io: safe(io[0].name).lower())
        return out

    def fetch(self, cl, item_id):
        m = cl.board().get(str(item_id))
        if not m:
            return None
        return _build(m, rising=cl.rising(str(item_id)))

    def is_deal(self, obs):
        return bool(obs.flags.get("rising"))

    def deal_line(self, item, obs):
        f = obs.flags
        return f"{item.name}  tide rising, {f.get('level_m')} mAOD  ({f.get('measured')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        return f"{(str(f.get('level_m')) if f.get('level_m') is not None else '?'):>8}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  station  : {item.name}  ({e.get('station_ref') or '?'})"]
        if obs:
            f = obs.flags
            lines.append(f"  level    : {f.get('level_m')} mAOD")
            if f.get("rising") is not None:
                lines.append(f"  tide     : {'rising (incoming)' if f.get('rising') else 'falling/steady'}")
            lines.append(f"  measured : {f.get('measured')}")
        return lines


SOURCE = UkTidesSource()
