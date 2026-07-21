"""eqcanada - Canadian earthquakes via the NRCan FDSN event service, keyless official feed.

Natural Resources Canada (Earthquakes Canada / Seismes Canada) publishes located events through the
standard keyless FDSN event web service `earthquakescanada.nrcan.gc.ca/fdsnws/event/1/query` (robots
allows the path - it fences only /cgi-bin and a couple of image dirs; an official open-data service =
sanctioned -> trove). The `format=text` response is a pipe-delimited table:
`EventID|Time|Latitude|Longitude|Depth/km|MagType|Magnitude|EventLocationName`. The Canadian complement
of `geonet` (NZ) and `usgsquakes` (global): same quake-magnitude shape, national coverage (BC/Yukon +
the St Lawrence + the Arctic), deepening CA geohazard.

Honest hoard value is **low** (the usgsquakes/frankfurter class): NRCan keeps the authoritative
catalogue and revises events, so the series is rebuildable from the same API - a breadth / geography
source. The mildly ephemeral part is the *as-reported* magnitude, revised in the hours after an event.
`price_cents` = magnitude * 100 (centi-magnitude, the geonet scalar) so the core's `drops` = an event
*downgraded* on review; `qty` = None. A "deal" ("strong") = magnitude >= 4.0 or the event was felt
(the location name carries "felt"/"ressenti").

Model: one Item per event (join key = the NRCan EventID). One memoized query serves a whole pass;
`fetch` re-queries by eventid (an event ageing off the recent feed -> fetch None -> series ends).
`--cc` is unused; `search <term>` filters the recent feed by place substring.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = "https://earthquakescanada.nrcan.gc.ca/fdsnws/event/1/query"
FEED_MINMAG = 1.5
FEED_LIMIT = 60
STRONG = 4.0


def _place(name):
    """Names are bilingual 'English/Francais' - keep the English half."""
    n = safe(name or "")
    return n.split("/")[0].strip() if "/" in n else n


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build(row):
    # row = [EventID, Time, Lat, Lon, Depth, MagType, Magnitude, EventLocationName]
    eid, t, lat, lon, depth, magtype, mag, name = (row + [""] * 8)[:8]
    m = _f(mag)
    place = _place(name)
    felt = "felt" in (name or "").lower() or "ressenti" in (name or "").lower()
    item = Item(eid.strip(), name=place or eid.strip(), subtitle=f"M{mag} {magtype}".strip(),
                category="quake", extra={"lat": _f(lat), "lon": _f(lon), "depth_km": _f(depth),
                                         "magType": magtype.strip()})
    obs = Obs(price_cents=(round(m * 100) if m is not None else None), qty=None,
              flags={"mag": m, "place": place, "time": t.strip().replace("T", " ")[:19],
                     "depth_km": _f(depth), "magType": magtype.strip(), "felt": felt})
    return item, obs


def _parse(text):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) >= 8:
            rows.append(parts)
    return rows


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = None

    def _query(self, params):
        r = self.s.get(BASE, params={"format": "text", **params},
                       headers={"User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.text

    def feed(self):
        if self._feed is None:
            self._feed = _parse(self._query({"orderby": "time", "limit": FEED_LIMIT,
                                             "minmagnitude": FEED_MINMAG}))
        return self._feed

    def by_id(self, eid):
        rows = _parse(self._query({"eventid": eid}))
        return rows[0] if rows else None


class EqCanadaSource(Source):
    name = "eqcanada"
    id_label = "EVENTID"
    cc_default = "ca"        # unused
    deal_label = "strong"    # magnitude >= 4.0 or a felt event
    search_limit_default = 30
    search_header = f"{'MAG':>5}  {'WHEN':<19}  PLACE"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = cl.feed()
        return bool(rows), f"({len(rows)} recent M>={FEED_MINMAG} CA events; keyless NRCan FDSN feed)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for row in cl.feed():
            item, obs = _build(row)
            if not t or t in safe(obs.flags.get("place") or "").lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        row = cl.by_id(str(item_id))
        return _build(row) if row else None

    def is_deal(self, obs):
        m = obs.flags.get("mag")
        return (isinstance(m, (int, float)) and m >= STRONG) or bool(obs.flags.get("felt"))

    def deal_line(self, item, obs):
        f = obs.flags
        felt = "  (felt)" if f.get("felt") else ""
        return f"M{f.get('mag')} {item.name}  ({f.get('time') or '?'}){felt}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        m = f.get("mag")
        return f"{(m if m is not None else '?'):>5}  {(f.get('time') or '')[:19]:<19}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  place    : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  magnitude: M{f.get('mag')}  ({e.get('magType') or '?'})   depth {e.get('depth_km')} km")
            lines.append(f"  time     : {f.get('time') or '?'}")
            if f.get("felt"):
                lines.append("  felt     : reported felt")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        return lines


SOURCE = EqCanadaSource()
