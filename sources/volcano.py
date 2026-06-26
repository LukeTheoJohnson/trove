"""volcano - New Zealand volcanic alert levels via GeoNet's sanctioned, keyless GeoJSON API.

Sibling of the `geonet` quake source on the same official GNS Science / Toka Tu Ake network
(api.geonet.org.nz, keyless, CC-BY 3.0 NZ). robots fences only marketing paths (/p/, /news/,
/assets/, /network/) - never /volcano - so this is a sanctioned public API -> trove.

Where `geonet` tracks individual quake events, this tracks the **current Volcanic Alert Level (VAL)
of each NZ volcano** - a different, slowly-moving ephemeral state. `GET /volcano/val` returns every
monitored volcano (Ruapehu, Tongariro, Taupo, Whakaari/White Island, Taranaki, ...) with its `level`
(0-5: 0 no unrest, 1 minor, 2 moderate/heightened, 3-5 eruption), aviation `acc` colour
(Green/Yellow/Orange/Red), and a plain-English `activity`/`hazards` summary. Polling builds our own
per-volcano alert-level time-series so we can see an escalation (the `deal`/notable signal) or a
de-escalation back to calm (the core's `drops` = a level revised *down*). GeoNet publishes VAL
bulletins, so this is rebuildable (low-med hoard value) - the draw is the clean unified state series
and the geohazard-suite fit alongside `geonet`.

Model: one Item per volcano (join key = `volcanoID`). `price_cents` = level * 100 (centi-level, so the
scalar slot carries the headline number and `drops` = a de-escalation); `qty` = the raw level (0-5).
A "notable" event (the deal analog) = level >= 1 (any unrest above background). `search` lists all
volcanoes (filter by a title substring); `item`/`poll` fetch one by `volcanoID`. `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source

UA = "trove/0.1 (+https://github.com/LukeTheoJohnson/trove)"
HOST = "https://api.geonet.org.nz"
WWW = "https://www.geonet.org.nz"
ACCEPT = "application/vnd.geo+json;version=2"
UNREST_CENTS = 100   # level >= 1 = "unrest" (minor or greater; above background)


def _safe(s):
    """Fold to cp1252 so a macron'd title (Taupo/Taupo, Tongariro) degrades to '?' rather than
    crashing a print - trove.py does not reconfigure stdout to UTF-8."""
    return (str(s) if s is not None else "").strip().encode("cp1252", "replace").decode("cp1252")


def _int(x):
    return int(x) if isinstance(x, (int, float)) else None


def _volcano(feat):
    """One GeoJSON volcano feature -> (Item, Obs)."""
    p = (feat or {}).get("properties", {}) or {}
    coords = ((feat or {}).get("geometry", {}) or {}).get("coordinates") or [None, None]
    lon, lat = (list(coords) + [None, None])[:2]
    vid = str(p.get("volcanoID", ""))
    title = _safe(p.get("volcanoTitle", "") or vid)
    level = _int(p.get("level"))
    acc = _safe(p.get("acc", ""))
    activity = _safe(p.get("activity", ""))
    hazards = _safe(p.get("hazards", ""))
    item = Item(vid, name=title, subtitle=f"alert level {level if level is not None else '?'} ({acc})",
                category=acc,
                extra={"lat": lat, "lon": lon, "activity": activity, "hazards": hazards,
                       "url": f"{WWW}/volcano/{vid}"})
    obs = Obs(price_cents=(level * 100 if level is not None else None),
              qty=level,
              flags={"level": level, "acc": acc, "activity": activity, "hazards": hazards})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feed = None   # one GET serves a whole search/poll pass

    def feed(self):
        if self._feed is None:
            r = self.s.get(HOST + "/volcano/val",
                           headers={"Accept": ACCEPT, "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._feed = (r.json() or {}).get("features") or []
        return self._feed


class VolcanoSource(Source):
    name = "volcano"
    id_label = "VOLCANO"
    cc_default = "nz"            # unused; one national feed
    deal_label = "unrest"       # unrest = alert level >= 1
    search_limit_default = 20
    search_header = f"{'LEVEL':>5}  {'COLOUR':<7}  {'VOLCANO':<22}  ACTIVITY"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        feats = cl.feed()
        return bool(feats), f"({len(feats)} NZ volcanoes; keyless GeoNet /volcano/val GeoJSON)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        rows = [_volcano(f) for f in cl.feed()]
        if t:
            rows = [(it, ob) for it, ob in rows if t in it.name.lower() or t in it.id.lower()]
        rows.sort(key=lambda r: (-(r[1].qty if r[1].qty is not None else -1), r[0].name))
        return rows

    def fetch(self, cl, item_id):
        for f in cl.feed():
            if str((f.get("properties") or {}).get("volcanoID", "")) == str(item_id):
                return _volcano(f)
        return None

    def is_deal(self, obs):
        return obs.price_cents is not None and obs.price_cents >= UNREST_CENTS

    def deal_line(self, item, obs):
        f = obs.flags
        return f"level {f.get('level', '?')} ({f.get('acc', '?')})  {item.name}  - {f.get('activity', '')}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        lvl = f.get("level")
        return (f"{(str(lvl) if lvl is not None else '?'):>5}  {(f.get('acc') or '?'):<7}  "
                f"{item.name:<22}  {(f.get('activity') or '')[:48]}")

    def format_item(self, item, obs):
        e = item.extra
        lines = []
        if obs:
            f = obs.flags
            lines.append(f"  alert level : {f.get('level', '?')}  (0 calm - 5 major eruption)")
            lines.append(f"  colour code : {f.get('acc', '?')}")
        lines.append(f"  activity    : {e.get('activity', '')}")
        lines.append(f"  hazards     : {e.get('hazards', '')}")
        lines.append(f"  coords      : {e.get('lat')}, {e.get('lon')}")
        lines.append(f"  url         : {e.get('url', '')}")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = VolcanoSource()
