"""sgtaxi - Singapore roaming-taxi supply (available-taxi count), keyless (data.gov.sg).

data.gov.sg publishes the live positions of every available (for-hire, roof-light on) taxi in
Singapore. `GET /v1/transport/taxi-availability` returns a GeoJSON MultiPoint of the roaming fleet plus
a `properties.taxi_count` - the number of taxis available across the island right now. The gateway
serves no robots.txt (a 403 missing-object body = no rules = unfenced, the GBFS/S3 class) and
data.gov.sg exists to be reused = sanctioned -> trove. The shared-mobility supply-index complement to
`bikeshare` (per-station docks): where bikeshare tracks one station, this tracks the *whole fleet's*
availability as a single scalar.

The timeline value is the supply curve: the roaming-taxi count swings with time of day, weather and
demand (it collapses in a downpour or at rush hour), and no one serves a queryable per-minute history
of it. `price_cents` = the available-taxi count * 100 (centi-taxi), so the core's `drops` = the fleet
*thinning* (fewer taxis free = harder to hail); `qty` = the raw count. A "deal" ("scarce") = the count
falls below 2,000 (a tight-supply moment - surge conditions). money() renders the centi-count as
dollars in the two core-hardcoded spots.

Model: one Item, the Singapore fleet (join key = the constant `sg`). `search`/`fetch`/`poll` all read
the same one aggregate. `--cc` is unused.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money

FEED = "https://api.data.gov.sg/v1/transport/taxi-availability"
SCARCE = 2000
ITEM_ID = "sg"


def _build(feature):
    props = (feature or {}).get("properties") or {}
    geom = (feature or {}).get("geometry") or {}
    count = props.get("taxi_count")
    if count is None:
        coords = geom.get("coordinates") or []
        count = len(coords)
    item = Item(ITEM_ID, name="Singapore available taxis", subtitle="roaming for-hire taxi fleet",
                category="fleet", extra={})
    obs = Obs(price_cents=(count * 100 if isinstance(count, int) else None), qty=count,
              flags={"taxi_count": count, "timestamp": props.get("timestamp")})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()
        self._feat = None

    def feature(self):
        if self._feat is None:
            r = self.s.get(FEED, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            feats = (r.json() or {}).get("features") or []
            self._feat = feats[0] if feats else {}
        return self._feat


class SgTaxiSource(Source):
    name = "sgtaxi"
    id_label = "FLEET"
    cc_default = "sg"        # unused
    deal_label = "scarce"    # count below 2,000 = tight supply
    search_header = f"{'TAXIS':>6}  FLEET"

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        f = cl.feature()
        n = ((f.get("properties") or {}).get("taxi_count"))
        return f is not None, f"({n} taxis available now; keyless data.gov.sg taxi-availability)"

    def search(self, cl, term, args):
        return [_build(cl.feature())]

    def fetch(self, cl, item_id):
        return _build(cl.feature())

    def is_deal(self, obs):
        n = obs.flags.get("taxi_count")
        return isinstance(n, int) and n < SCARCE

    def deal_line(self, item, obs):
        return f"{obs.flags.get('taxi_count')} taxis available  (tight supply)"

    def search_row(self, item, obs):
        n = obs.flags.get("taxi_count") if obs else None
        return f"{(n if n is not None else '?'):>6}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  fleet    : {item.name}"]
        if obs:
            lines.append(f"  available: {obs.flags.get('taxi_count')} taxis")
            lines.append(f"  as of    : {obs.flags.get('timestamp') or '?'}")
        return lines


SOURCE = SgTaxiSource()
