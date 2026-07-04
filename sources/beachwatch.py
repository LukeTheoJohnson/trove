"""beachwatch - NSW Beachwatch live beach water-quality + pollution forecast, keyless GeoJSON.

The NSW Government's Beachwatch programme monitors swimming water quality at ~250 beaches and
estuarine sites and publishes it as a keyless GeoJSON API (api.beachwatch.nsw.gov.au/public/sites/
geojson). robots.txt is open, and the /public/ path is an explicit public API = sanctioned -> trove.
A weather/environment source, AU-side.

The timeline value is ephemeral: each site's **daily pollution forecast** (Unlikely / Possible /
Likely, driven by rainfall + stormwater) and its latest star rating (1-4), updated day to day and not
archived in a queryable per-site series. `price_cents` = the latest water-quality star rating * 100
(1=Poor .. 4=Good, so the core's `drops` = water quality *worsening*); a "deal" ("pollution") = the
site's pollution forecast is Possible or Likely (a don't-swim advisory - the health signal worth
catching). money() cosmetically renders the centi-rating as dollars in the two core-hardcoded spots
(a 4-star rating prints as "$4.00"; geonet precedent); the rich views show "Good (4/4)".

Model: one Item per monitoring site (join key = the Beachwatch site `id`, a UUID). `search <term>`
filters sites by name substring (pass "" to list them all); `fetch` scans the memoized feed by id.
One GET returns every site, memoized, so a whole poll is a single request. `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

FEED = "https://api.beachwatch.nsw.gov.au/public/sites/geojson"
RATINGS = {"1": "Poor", "2": "Fair", "3": "Good", "4": "Good"}   # star -> label (per Beachwatch)
POLLUTION_DEAL = {"possible", "likely"}   # forecast that warrants a swim advisory


def _rating_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _build(feat):
    p = feat.get("properties") or {}
    sid = str(p.get("id", ""))
    coords = (feat.get("geometry") or {}).get("coordinates") or [None, None]
    rating = _rating_int(p.get("latestResultRating"))
    item = Item(sid, name=safe(p.get("siteName", "")),
                subtitle="NSW Beachwatch water quality", category="beach",
                extra={"site_id": sid, "lon": coords[0], "lat": coords[1]})
    obs = Obs(price_cents=(rating * 100 if rating is not None else None),
              flags={"pollution_forecast": safe(p.get("pollutionForecast", "")),
                     "forecast_at": p.get("pollutionForecastTimeStamp"),
                     "latest_result": safe(p.get("latestResult", "")),
                     "rating": rating, "observed": p.get("latestResultObservationDate")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feats = None

    def features(self):
        if self._feats is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._feats = (r.json() or {}).get("features") or []
        return self._feats


class BeachwatchSource(Source):
    name = "beachwatch"
    id_label = "SITE"
    cc_default = "au"        # unused; one NSW network
    deal_label = "pollution"  # pollution forecast Possible/Likely = swim advisory
    search_limit_default = 30
    search_header = f"{'RATING':>10}  {'FORECAST':<10}  BEACH"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        feats = cl.features()
        return bool(feats), f"({len(feats)} NSW beach/estuary sites; keyless Beachwatch GeoJSON)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        out = []
        for feat in cl.features():
            item, obs = _build(feat)
            if not t or t in item.name.lower():
                out.append((item, obs))
        out.sort(key=lambda io: io[0].name.lower())
        return out

    def fetch(self, cl, item_id):
        for feat in cl.features():
            item, obs = _build(feat)
            if str(item.id) == str(item_id):
                return item, obs
        return None

    def is_deal(self, obs):
        return obs.flags.get("pollution_forecast", "").lower() in POLLUTION_DEAL

    def deal_line(self, item, obs):
        f = obs.flags
        return f"pollution {f.get('pollution_forecast')}  {item.name}  (water {f.get('latest_result') or '?'})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        r = f.get("rating")
        disp = f"{f.get('latest_result') or '-'}({r})" if r else "-"
        return f"{disp:>10}  {(f.get('pollution_forecast') or '-'):<10}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  beach    : {item.name}",
                 f"  location : {e.get('lat', '?')}, {e.get('lon', '?')}"]
        if obs:
            f = obs.flags
            r = f.get("rating")
            lines.append(f"  forecast : pollution {f.get('pollution_forecast')}  (as at {f.get('forecast_at', '?')})")
            lines.append(f"  latest   : {f.get('latest_result')}  ({r}/4 star)  sampled {f.get('observed', '?')}")
        return lines


SOURCE = BeachwatchSource()
