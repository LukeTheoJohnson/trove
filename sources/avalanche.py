"""avalanche - NZ Avalanche Advisory regional danger ratings (avalanche.net.nz), keyless JSON.

The NZ Avalanche Advisory (run by the NZ Mountain Safety Council) publishes a daily backcountry
avalanche forecast per region through the winter season. Its site is a SilverStripe + Vue app whose
forecast view calls two keyless, page-called, same-origin JSON endpoints - `GET /api/region` (the 13
forecast regions + geometry) and `GET /api/forecast` (every region's current + recent advisory). Both
return one bulk payload; robots.txt fences only `/subscriptions/`, never `/api` - so this is a
page-called, keyless API = sanctioned -> trove, not a reverse-engineered private endpoint.

The timeline value is the **danger rating as issued**: each day's forecast assigns a 1-5 rating
(1 Low - 5 Extreme) to each of three elevation bands (alpine / sub-alpine / below treeline), plus the
avalanche problems (wind slab, persistent slab...) and a trend. That as-issued forecast - and its
revision as observations accrue - is never archived in a queryable per-region series (there is no
public "what was Queenstown's rating last Tuesday"), so the snapshot is the only record: the same
un-rebuildable forecast-drift hoard as `metno`/`spaceweather`, in the NZ geohazard genre alongside
`geonet`/`volcano`/`nzski`.

Model: one Item per region (join key = the region's `urlSegment`, e.g. `queenstown` - stable, matches
the site URL). `price_cents` = the **headline danger** (max rating across the elevation bands) * 100
(centi-danger, so the core's `drops` = the danger *easing*), `qty` = the number of avalanche problems
posted (a complexity signal); the per-band ratings, problems, trend, confidence and forecaster ride in
flags. A "deal" = elevated danger, headline >= 3 (Considerable) - the level at which most avalanche
incidents occur, i.e. the backcountry-travel warning worth catching. money() cosmetically renders
centi-danger as dollars in the two core-hardcoded spots (Considerable prints as "$3.00";
geonet/volcano precedent); the rich views show "Considerable (3/5)".

The advisory is **seasonal** (roughly June-October): off-season the endpoints return no current
forecasts, so `search` is empty and `fetch` returns None (a region's series pauses out of season and
resumes when forecasting restarts). `search` lists the regions (a fixed set, like `nzski`) filtered by
a name substring; one poll of every region costs two memoized GETs.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

BASE = "https://www.avalanche.net.nz/api"
DANGER_NAMES = {1: "Low", 2: "Moderate", 3: "Considerable", 4: "High", 5: "Extreme"}
# NZAA always issues exactly the three standard elevation bands, ordered highest-to-lowest in the
# payload; label by position (the altitude bounds share boundary values and mislabel the lowest band).
BAND_LABELS = ("Alpine", "Sub-alpine", "Below treeline")
DEAL_MIN = 3   # headline danger >= Considerable = the warning worth catching


def _danger_name(d):
    return DANGER_NAMES.get(d, "n/a") if d else "n/a"


def _headline(bands):
    """Max valid (1-5) rating across the elevation bands; negatives are 'not rated' sentinels."""
    vals = [b.get("rating") for b in bands if isinstance(b.get("rating"), int) and b.get("rating") >= 1]
    return max(vals) if vals else None


def _build(region, fc):
    """One region + its current forecast -> (Item, Obs). Returns None without a forecast."""
    slug = region.get("urlSegment")
    if not slug:
        return None
    item = Item(str(slug), name=safe(region.get("title", "")),
                subtitle="NZ Avalanche Advisory", category="avalanche region",
                extra={"region_id": region.get("id"), "urlSegment": slug,
                       "lat": region.get("latitude"), "lon": region.get("longitude"),
                       "url": f"https://www.avalanche.net.nz/region/{slug}",
                       "metservice": region.get("metserviceForecastLink", "")})
    if not fc:
        return item, None
    bands = fc.get("altitudeDanger") or []
    problems = [safe((p.get("character") or {}).get("title", "")) for p in (fc.get("avalancheDangers") or [])]
    problems = [p for p in problems if p]
    primary = (fc.get("avalancheDangers") or [{}])[0]
    head = _headline(bands)
    obs = Obs(price_cents=(head * 100 if head else None),
              qty=len(fc.get("avalancheDangers") or []),
              flags={"danger": head, "danger_name": _danger_name(head),
                     "bands": [{"label": BAND_LABELS[i] if i < len(BAND_LABELS) else f"band {i + 1}",
                                "rating": b.get("rating"), "from": b.get("altitudeFrom"),
                                "to": b.get("altitudeTo")} for i, b in enumerate(bands)],
                     "trend": primary.get("trend"), "problems": problems,
                     "confidence": fc.get("confidenceLevel"), "forecaster": safe(fc.get("forecaster", "")),
                     "valid": fc.get("validPeriod"), "issued": fc.get("created"),
                     "edited": fc.get("lastEdited")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._regions = None
        self._current = None    # regionId -> current forecast (latest issued)

    def _get(self, path):
        r = self.s.get(BASE + path, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or {}

    def regions(self):
        if self._regions is None:
            self._regions = (self._get("/region").get("regions")) or []
        return self._regions

    def current(self):
        """regionId -> the current (latest-issued) forecast, from one bulk GET."""
        if self._current is None:
            cur = {}
            for f in (self._get("/forecast").get("forecasts") or []):
                rid = f.get("regionId")
                key = (f.get("created") or "", f.get("id") or 0)
                if rid is not None and (rid not in cur or key > cur[rid][0]):
                    cur[rid] = (key, f)
            self._current = {rid: v[1] for rid, v in cur.items()}
        return self._current

    def rows(self):
        """(region, current-forecast-or-None) for every region that has a forecast."""
        cur = self.current()
        out = []
        for reg in self.regions():
            fc = cur.get(reg.get("id"))
            if fc:
                out.append((reg, fc))
        return out


class AvalancheSource(Source):
    name = "avalanche"
    id_label = "SLUG"          # the region urlSegment you pass to item/watch
    deal_label = "danger"      # elevated danger (headline >= Considerable)
    search_limit_default = 30  # the region set is small and fixed - list them all
    search_header = f"{'DANGER':>16}  {'TREND':<11}  REGION"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        rows = cl.rows()
        return bool(rows), f"({len(rows)} regions with a current advisory; keyless /api/forecast JSON)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for reg, fc in cl.rows():
            built = _build(reg, fc)
            if built and (not t or t in built[0].name.lower() or t in str(reg.get("urlSegment", "")).lower()):
                out.append(built)
        out.sort(key=lambda io: -(io[1].price_cents or 0) if io[1] else 0)   # most dangerous first
        return out

    def fetch(self, cl, item_id):
        slug = str(item_id).lower()
        cur = cl.current()
        for reg in cl.regions():
            if str(reg.get("urlSegment", "")).lower() == slug:
                fc = cur.get(reg.get("id"))
                return _build(reg, fc) if fc else None   # no current forecast (off-season) = series pauses
        return None

    def is_deal(self, obs):
        d = obs.flags.get("danger")
        return isinstance(d, int) and d >= DEAL_MIN

    def deal_line(self, item, obs):
        f = obs.flags
        trend = f" [{f.get('trend')}]" if f.get("trend") else ""
        probs = f"  problems: {', '.join(f.get('problems') or [])}" if f.get("problems") else ""
        return f"{f.get('danger_name')} ({f.get('danger')}/5)  {item.name}{trend}{probs}"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        d = f.get("danger")
        disp = f"{_danger_name(d)}({d})" if d else "n/a"
        return f"{disp:>16}  {(f.get('trend') or '-'):<11}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  region   : {item.name}",
                 f"  location : {e.get('lat', '?')}, {e.get('lon', '?')}"]
        if obs is None:
            lines.append("  advisory : none current (off-season)")
            return lines
        f = obs.flags
        lines.append(f"  danger   : {f.get('danger_name')} ({f.get('danger')}/5)"
                     + (f"  trend {f.get('trend')}" if f.get("trend") else ""))
        for b in (f.get("bands") or []):
            r = b.get("rating")
            lines.append(f"    {b.get('label'):>10} : {_danger_name(r) if isinstance(r, int) and r >= 1 else 'not rated'}")
        if f.get("problems"):
            lines.append(f"  problems : {', '.join(f['problems'])}")
        lines.append(f"  confidence: {f.get('confidence', '?')}")
        lines.append(f"  issued   : {f.get('issued', '?')}  (valid {f.get('valid', '?')}, forecaster {f.get('forecaster', '?')})")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = AvalancheSource()
