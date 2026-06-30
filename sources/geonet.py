"""geonet - New Zealand earthquakes via GeoNet's sanctioned, keyless GeoJSON API.

GeoNet (api.geonet.org.nz) is the official GNS Science / Toka Tu Ake EQC geological-hazard network
for Aotearoa New Zealand. Its public API is keyless, documented, CC-BY 3.0 NZ licensed, and is the
canonical data-science-friendly NZ open-data source. robots.txt fences only marketing paths (/p/,
/news/, /assets/, /network/) - never /quake - so this is a sanctioned public API -> trove.

The timeline value is a quake's *preliminary -> reviewed revision drift*. GeoNet auto-detects a quake
within seconds and publishes a `quality:"best"`/`"preliminary"` solution; over the next minutes-to-days
an analyst reviews it and the magnitude, depth, locality and `quality` are revised - or the event is
`"deleted"` outright as a false trigger. The single `GET /quake/{publicID}` always returns the *current*
solution, so polling a watched quake builds our own unified magnitude/quality time-series across the
whole catalogue. (GeoNet also exposes `/quake/history/{id}`, so per-quake revisions are archivable -
this source's draw is the convenient cross-quake series and the data-science fit, not un-rebuildability:
medium hoard value, a capability flex on the textbook NZ science API.)

Model: one Item per quake (join key = `publicID`). `price_cents` = round(magnitude * 100) (centi-
magnitude, so the scalar slot carries the headline number and `drops` = a quake *downgraded* on review,
i.e. a preliminary over-estimate corrected down); `qty` = MMI (Modified Mercalli Intensity, 0-8).
A "notable" event (the deal analog) = magnitude >= 4.0. `search` lists recent quakes at/above `--mmi`
(default 3) and filters by a locality substring; `item`/`poll` fetch one quake by id. `--cc` is unused
(the whole country is one feed).
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

HOST = "https://api.geonet.org.nz"
WWW = "https://www.geonet.org.nz"
ACCEPT = "application/vnd.geo+json;version=2"
NOTABLE_CENTS = 400   # magnitude >= 4.0 = "notable" (moderate quake, felt across a region)


def _num(x):
    return x if isinstance(x, (int, float)) else None


def _mag_cents(mag):
    """magnitude float -> centi-magnitude int (M3.11 -> 311); the scalar slot, sane drop granularity."""
    m = _num(mag)
    return round(m * 100) if m is not None else None


def _when(iso):
    """'2026-06-25T14:01:52.692Z' -> '06-25 14:01' (UTC)."""
    s = iso or ""
    return s[5:16].replace("T", " ") if len(s) >= 16 else s


def _quake(feat):
    """One GeoJSON quake feature -> (Item, Obs)."""
    p = (feat or {}).get("properties", {}) or {}
    coords = ((feat or {}).get("geometry", {}) or {}).get("coordinates") or [None, None]
    lon, lat = (list(coords) + [None, None])[:2]
    pid = str(p.get("publicID", ""))
    mag, mmi, depth = _num(p.get("magnitude")), _num(p.get("mmi")), _num(p.get("depth"))
    locality = safe(p.get("locality", ""))
    quality = p.get("quality", "")
    when = p.get("time", "")
    name = f"M{mag:.1f} {locality}" if mag is not None else (locality or pid)
    item = Item(pid, name=name, subtitle=f"{_when(when)} UTC", category=quality,
                extra={"lat": lat, "lon": lon, "locality": locality, "time": when,
                       "url": f"{WWW}/earthquake/{pid}"})
    obs = Obs(price_cents=_mag_cents(mag),
              qty=(int(mmi) if mmi is not None else None),
              flags={"magnitude": round(mag, 2) if mag is not None else None,
                     "mmi": int(mmi) if mmi is not None else None,
                     "depth_km": round(depth, 1) if depth is not None else None,
                     "quality": quality, "locality": locality, "time": when})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = {}   # min_mmi -> [feature]; one GET serves a whole search/poll pass

    def _get(self, path, params=None):
        r = self.s.get(HOST + path, params=params,
                       headers={"Accept": ACCEPT, "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return (r.json() or {}).get("features") or []

    def feed(self, min_mmi):
        key = int(min_mmi)
        if key not in self._feed:
            self._feed[key] = self._get("/quake", params={"MMI": key})
        return self._feed[key]

    def one(self, pid):
        feats = self._get(f"/quake/{pid}")
        return feats[0] if feats else None


class GeoNetSource(Source):
    name = "geonet"
    id_label = "QUAKE"
    cc_default = "nz"            # unused; GeoNet serves the whole country in one feed
    deal_label = "notable"      # notable = magnitude >= 4.0 (moderate, felt across a region)
    search_args = [("--mmi", {"type": int, "default": 3,
                              "help": "min Modified Mercalli Intensity 0-8 (default 3)"})]
    search_limit_default = 25   # the MMI feed is bounded (<=100 recent); list a useful chunk
    search_header = f"{'MAG':>5}  {'MMI':>3}  {'DEPTH':>6}  {'WHEN':<11}  LOCALITY"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        feats = cl.feed(3)
        return bool(feats), f"({len(feats)} quakes MMI>=3 in the recent feed; keyless GeoNet GeoJSON)"

    def search(self, cl, term, args):
        feats = cl.feed(getattr(args, "mmi", 3))
        t = (term or "").lower()
        rows = [_quake(f) for f in feats]
        if t:
            rows = [(it, ob) for it, ob in rows if t in it.extra.get("locality", "").lower()]
        rows.sort(key=lambda r: r[0].extra.get("time", ""), reverse=True)
        return rows

    def fetch(self, cl, item_id):
        feat = cl.one(str(item_id))
        return _quake(feat) if feat else None

    def is_deal(self, obs):
        return obs.price_cents is not None and obs.price_cents >= NOTABLE_CENTS

    def deal_line(self, item, obs):
        f = obs.flags
        mag = f.get("magnitude")
        depth = f.get("depth_km")
        magstr = f"M{mag:.1f}" if isinstance(mag, (int, float)) else "M?"
        depthstr = f"{depth:g}km deep" if isinstance(depth, (int, float)) else ""
        return f"{magstr}  MMI {f.get('mmi', '?')}  {depthstr}  {_when(f.get('time', ''))}  {f.get('locality', '')}".strip()

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        mag, depth, mmi = f.get("magnitude"), f.get("depth_km"), f.get("mmi")
        magstr = f"M{mag:.1f}" if isinstance(mag, (int, float)) else "?"
        depthstr = f"{depth:g}km" if isinstance(depth, (int, float)) else "?"
        return (f"{magstr:>5}  {(str(mmi) if mmi is not None else '?'):>3}  {depthstr:>6}  "
                f"{_when(f.get('time', '')):<11}  {f.get('locality', '')}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  locality : {e.get('locality', '')}",
                 f"  time     : {e.get('time', '')}"]
        if obs:
            f = obs.flags
            mag = f.get("magnitude")
            lines.append(f"  magnitude: M{mag:.2f}" if isinstance(mag, (int, float)) else "  magnitude: ?")
            lines.append(f"  intensity: MMI {f.get('mmi', '?')}")
            lines.append(f"  depth    : {f.get('depth_km', '?')} km")
            lines.append(f"  quality  : {f.get('quality', '?')}   (preliminary/best/reviewed/deleted)")
        lines.append(f"  coords   : {e.get('lat')}, {e.get('lon')}")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = GeoNetSource()
