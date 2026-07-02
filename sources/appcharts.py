"""appcharts - Apple App Store top-chart rank rotation via the keyless marketing-tools RSS.

Apple publishes its App Store top charts as public JSON feeds on `rss.marketingtools.apple.com`
(the successor to the old iTunes RSS), built explicitly for reuse - the host's robots.txt is a
single documentation comment with zero Disallow lines = sanctioned -> trove. Sibling of `itunes`
(same store) but a different mechanic: this tracks **rank**, not price.

The ephemeral thing this source hoards is the **chart as published**: which apps hold which slots
in a country's top-free/top-paid chart, refreshed through the day. Chart *history* is exactly what
Sensor Tower / Appfigures sell subscriptions for - there is no free public archive of "what was #4
in NZ top-free last Tuesday" - so the as-published series is honestly **med-high**.

Model: one Item per chart slot occupant (join key = composite `country:chart:appId`, e.g.
`nz:top-free:6448311069` - the same app can sit in several charts/countries, and the key lets
fetch/poll rebuild the exact feed). `price_cents` = **rank * 100** (centi-rank, rank 1 = the top
slot), so the core's `drops` = an app *climbing* the chart; an app that falls off the chart returns
None from fetch and its series ends (reverb/turners retirement pattern). Deal "top10" = an app in
the top 10. money() cosmetically renders centi-rank as dollars in the two core-hardcoded spots
(rank 4 prints as "$4.00"; geonet/metno precedent); the rich views show "#4".

`--cc` picks the storefront country (default nz), `search --chart top-free|top-paid|all` picks the
chart(s) (default all = 2 memoized GETs); the term filters by app/developer name; `item`/`poll` read
the country+chart from the id itself, so mixed-country watchlists stay coherent.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, safe

FEED = "https://rss.marketingtools.apple.com/api/v2/{cc}/apps/{chart}/{n}/apps.json"
CHARTS = ("top-free", "top-paid")
N = 100             # chart depth per feed (one GET returns the whole chart)
TOP_RANK = 10       # deal = an app in the top 10


def _build(app, cc, chart, rank, updated):
    appid = str(app.get("id") or "")
    if not appid:
        return None
    name = safe(app.get("name") or "")
    artist = safe(app.get("artistName") or "")
    item = Item(f"{cc}:{chart}:{appid}", name=name, subtitle=artist, category=chart,
                extra={"appid": appid, "artist": artist, "chart": chart, "country": cc,
                       "released": app.get("releaseDate") or "", "url": app.get("url") or "",
                       "icon": app.get("artworkUrl100") or ""})
    obs = Obs(price_cents=rank * 100,
              flags={"rank": rank, "chart": chart, "country": cc, "artist": artist,
                     "updated": updated})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.cc = (cc or "nz").lower()
        self.s = retry_session()
        self._feeds = {}    # (cc, chart) -> (results, updated); one GET serves a whole pass

    def feed(self, cc, chart):
        key = (cc, chart)
        if key not in self._feeds:
            r = self.s.get(FEED.format(cc=cc, chart=chart, n=N),
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            f = (r.json() or {}).get("feed") or {}
            self._feeds[key] = (f.get("results") or [], f.get("updated") or "")
        return self._feeds[key]


class AppChartsSource(Source):
    name = "appcharts"
    id_label = "CC:CHART:ID"
    cc_default = "nz"           # storefront country for `search`
    deal_label = "top10"        # an app in the chart's top 10
    search_args = [
        ("--chart", {"choices": [*CHARTS, "all"], "default": "all",
                     "help": "which chart to pull (default all)"}),
    ]
    search_limit_default = 25
    search_header = f"{'RANK':>5}  {'CHART':<9}  {'DEVELOPER':<28}  APP"

    def client(self, args):
        return _Client(args.cc)

    def doctor(self, cl):
        results, updated = cl.feed(cl.cc, "top-free")
        return bool(results), f"({len(results)} apps in {cl.cc} top-free, updated {updated}; keyless Apple RSS)"

    def search(self, cl, term, args):
        t = (term or "").lower()
        chart_arg = getattr(args, "chart", "all") or "all"
        charts = CHARTS if chart_arg == "all" else (chart_arg,)
        rows = []
        for chart in charts:
            results, updated = cl.feed(cl.cc, chart)
            for i, app in enumerate(results):
                hay = f"{app.get('name', '')} {app.get('artistName', '')}".lower()
                if t and t not in hay:
                    continue
                built = _build(app, cl.cc, chart, i + 1, updated)
                if built:
                    rows.append(built)
        return rows

    def fetch(self, cl, item_id):
        parts = str(item_id).split(":")
        if len(parts) != 3:
            return None
        cc, chart, appid = parts
        if chart not in CHARTS:
            return None
        results, updated = cl.feed(cc, chart)
        for i, app in enumerate(results):
            if str(app.get("id") or "") == appid:
                return _build(app, cc, chart, i + 1, updated)
        return None                          # fell off the chart; the series ends here

    def is_deal(self, obs):
        rank = obs.flags.get("rank")
        return rank is not None and rank <= TOP_RANK

    def deal_line(self, item, obs):
        f = obs.flags
        return f"#{f.get('rank', '?')} in {f.get('country', '?')} {f.get('chart', '?')}  {item.name}  ({f.get('artist', '')})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        rank = f.get("rank")
        return (f"{('#' + str(rank)) if rank else '?':>5}  {f.get('chart', item.category):<9}  "
                f"{item.subtitle[:28]:<28}  {item.name}")

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  app      : {item.name}",
                 f"  developer: {e.get('artist', '')}",
                 f"  chart    : {e.get('country', '')} {e.get('chart', '')}  (released {e.get('released', '?')})"]
        if obs:
            f = obs.flags
            lines.append(f"  rank     : #{f.get('rank', '?')}  (chart updated {f.get('updated', '?')})")
        lines.append(f"  url      : {e.get('url', '')}")
        return lines


SOURCE = AppChartsSource()
