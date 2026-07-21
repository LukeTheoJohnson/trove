"""bmkg - Indonesian earthquakes via BMKG's keyless open data feed (TEWS).

BMKG (Badan Meteorologi, Klimatologi, dan Geofisika - Indonesia's met/geophysics agency) publishes its
earthquake feed as keyless JSON under `data.bmkg.go.id/DataMKG/TEWS/`: `gempaterkini.json` (the recent
felt/significant events) and `autogempa.json` (the single latest event), each with magnitude, depth,
coordinates, region (Wilayah) and a tsunami-potential note (Potensi). robots.txt is 404 (unfenced) and
the feed is official open data = sanctioned -> trove. Opens **Indonesia** (one of the most seismically
active countries on Earth), twinning `geonet`/`usgsquakes`/`eqcanada` on the quake-magnitude shape.

Honest hoard value is low (BMKG keeps the catalogue - the usgsquakes class); the mildly ephemeral part
is the as-reported magnitude and the tsunami assessment. `price_cents` = magnitude * 100 (centi-
magnitude, the geonet scalar) so the core's `drops` = an event *downgraded* on review; `qty` = None. A
"deal" ("strong") = magnitude >= 5.0 or the event carries tsunami potential.

Model: one Item per event (join key = the event `DateTime`, ISO with offset). One memoized GET over
gempaterkini serves search; `fetch` scans that feed (an event ageing off -> fetch None -> series ends).
`--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

TERKINI = "https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json"
STRONG = 5.0


def _f(v):
    try:
        return float(str(v).split()[0])
    except (TypeError, ValueError, IndexError):
        return None


def _coords(s):
    try:
        lat, lon = str(s).split(",")
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None


def _has_tsunami(potensi):
    p = (potensi or "").lower()
    return "tsunami" in p and "tidak" not in p


def _build(gm):
    mag = _f(gm.get("Magnitude"))
    lat, lon = _coords(gm.get("Coordinates"))
    dt = gm.get("DateTime") or f"{gm.get('Tanggal', '')} {gm.get('Jam', '')}"
    tsunami = _has_tsunami(gm.get("Potensi"))
    item = Item(dt, name=safe(gm.get("Wilayah") or dt), subtitle=f"M{gm.get('Magnitude')} {gm.get('Kedalaman', '')}".strip(),
                category="quake", extra={"lat": lat, "lon": lon, "depth": safe(gm.get("Kedalaman") or "")})
    obs = Obs(price_cents=(round(mag * 100) if mag is not None else None), qty=None,
              flags={"mag": mag, "region": safe(gm.get("Wilayah") or ""), "depth": safe(gm.get("Kedalaman") or ""),
                     "time": dt, "potensi": safe(gm.get("Potensi") or ""), "tsunami": tsunami,
                     "felt": safe(gm.get("Dirasakan") or "")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = None

    def feed(self):
        if self._feed is None:
            r = self.s.get(TERKINI, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._feed = ((r.json() or {}).get("Infogempa") or {}).get("gempa") or []
        return self._feed


class BmkgSource(Source):
    name = "bmkg"
    id_label = "DATETIME"
    cc_default = "id"        # unused
    deal_label = "strong"    # magnitude >= 5.0 or tsunami potential
    search_limit_default = 20
    search_header = f"{'MAG':>5}  {'WHEN':<20}  REGION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        fs = cl.feed()
        return bool(fs), f"({len(fs)} recent ID events; keyless BMKG TEWS feed)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for gm in cl.feed():
            item, obs = _build(gm)
            if not t or t in safe(obs.flags.get("region") or "").lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        for gm in cl.feed():
            dt = gm.get("DateTime") or f"{gm.get('Tanggal', '')} {gm.get('Jam', '')}"
            if dt == str(item_id):
                return _build(gm)
        return None

    def is_deal(self, obs):
        m = obs.flags.get("mag")
        return (isinstance(m, (int, float)) and m >= STRONG) or bool(obs.flags.get("tsunami"))

    def deal_line(self, item, obs):
        f = obs.flags
        tsu = "  TSUNAMI" if f.get("tsunami") else ""
        return f"M{f.get('mag')} {item.name}  ({f.get('time') or '?'}){tsu}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        m = f.get("mag")
        return f"{(m if m is not None else '?'):>5}  {(f.get('time') or '')[:20]:<20}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  region   : {item.name}"]
        if obs:
            f = obs.flags
            lines.append(f"  magnitude: M{f.get('mag')}   depth {f.get('depth')}")
            lines.append(f"  time     : {f.get('time') or '?'}")
            lines.append(f"  tsunami  : {f.get('potensi') or '?'}")
            if f.get("felt"):
                lines.append(f"  felt     : {f.get('felt')}")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        return lines


SOURCE = BmkgSource()
