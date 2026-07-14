"""francefuel - per-station French forecourt fuel prices via the official Opendatasoft flux.

The French government publishes every service station's live pump prices as open data. The instant
flux is an Opendatasoft dataset - `data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/
prix-des-carburants-en-france-flux-instantane-v2/records` - keyless (robots fences only /login,
/publish, /backoff, never /api) and built for reuse = sanctioned -> trove. ~9,800 stations, each with
its per-grade price (gazole, SP95, SP98, E10, E85, GPLc), an update timestamp per grade, and any
current stock shortage (`rupture`). The EU twin of `spainfuel` (ES) and `petrolspy`/`fuelwatch`
(NZ/AU), extending the ephemeral per-station forecourt-price hoard into France.

The timeline value is the same high-value one: a forecourt price is overwritten in place and never
archived per-station, so the snapshot is the only record. `--cc` picks the tracked grade (default
`gazole`; also sp95/sp98/e10/e85/gplc); `price_cents` = that grade's price in euro-cents (so the
core's `drops` = the pump getting *cheaper*); `qty` = the count of grades the station currently sells.
A "deal" ("cheap") = the tracked grade is at or below the national sample average for that grade. The
other grades, their update times, and any stock rupture ride in flags. money() renders euro-cents (a
'$' glyph on the cp1252 console, but the value is euros).

Model: one Item per station (join key = the station `id`). ODS caps `limit` at 100 (the melbped
lesson), so `search <term>` filters server-side by ville (text) or postcode/department (digits) and
`fetch` re-queries one station by id; a whole pass is a couple of memoized GETs.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

BASE = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
        "prix-des-carburants-en-france-flux-instantane-v2/records")
GRADES = ("gazole", "sp95", "sp98", "e10", "e85", "gplc")


def _cents(v):
    """A grade price -> euro-cents. The flux serves euros (1.729); guard a millieme form (1729)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x > 10:            # a millieme value (e.g. 1729) rather than euros
        x /= 1000.0
    return round(x * 100)


def _coord(v):
    try:
        return round(float(v) / 100000.0, 6)   # the flux stores lat/lon as integer * 1e5
    except (TypeError, ValueError):
        return None


def _build(rec, grade, avg):
    sid = str(rec.get("id"))
    prices = {g: _cents(rec.get(f"{g}_prix")) for g in GRADES}
    pc = prices.get(grade)
    ville = safe(rec.get("ville") or "")
    item = Item(sid, name=(ville or sid), subtitle=safe(rec.get("adresse") or ""),
                category=safe(rec.get("departement") or "France"),
                extra={"ville": ville, "cp": rec.get("cp") or "", "adresse": safe(rec.get("adresse") or ""),
                       "departement": safe(rec.get("departement") or ""), "region": safe(rec.get("region") or ""),
                       "lat": _coord(rec.get("latitude")), "lon": _coord(rec.get("longitude"))})
    avail = [g for g in GRADES if prices.get(g) is not None]
    obs = Obs(price_cents=pc, qty=len(avail),
              flags={"grade": grade, "unit": "euro-cents", "grade_avg": avg,
                     "prices": prices, "maj": rec.get(f"{grade}_maj") or "",
                     "available": ",".join(avail),
                     "rupture": safe(rec.get("carburants_rupture_temporaire") or "")})
    return item, obs


class _Client:
    def __init__(self, grade):
        self.grade = grade if grade in GRADES else "gazole"
        self.s = retry_session()
        self._avg = {}

    def _get(self, params):
        r = self.s.get(BASE, params=params, headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json() or {}

    def avg(self):
        """National sample average for the tracked grade (one memoized limit-100 pull)."""
        if self.grade not in self._avg:
            fld = f"{self.grade}_prix"
            d = self._get({"select": fld, "where": f"{fld} is not null", "limit": 100})
            vals = [c for c in (_cents(r.get(fld)) for r in (d.get("results") or [])) if c is not None]
            self._avg[self.grade] = round(sum(vals) / len(vals)) if vals else None
        return self._avg[self.grade]

    def records(self, term, limit):
        params = {"limit": min(limit, 100), "order_by": f"{self.grade}_prix"}
        t = (term or "").strip()
        if t:
            params["where"] = (f'cp like "{t}%" or code_departement="{t}"' if t.isdigit()
                               else f'ville like "%{t}%"')
        return self._get(params).get("results") or []

    def by_id(self, sid):
        recs = self._get({"where": f'id="{sid}"', "limit": 1}).get("results") or []
        return recs[0] if recs else None


class FranceFuelSource(Source):
    name = "francefuel"
    id_label = "STATION"
    cc_default = "gazole"       # tracked grade: gazole|sp95|sp98|e10|e85|gplc
    deal_label = "cheap"        # grade at/below the national sample average
    search_limit_default = 25
    search_header = f"{'PRICE':>7}  {'CP':>6}  STATION"

    def client(self, args):
        return _Client(getattr(args, "cc", "gazole"))

    def doctor(self, cl):
        recs = cl.records("", 1)
        return bool(recs), f"(flux live, grade '{cl.grade}'; keyless Opendatasoft prix-carburants v2)"

    def search(self, cl, term, args):
        avg = cl.avg()
        return [_build(r, cl.grade, avg) for r in cl.records(term, self.search_limit_default * 2)]

    def fetch(self, cl, item_id):
        rec = cl.by_id(str(item_id))
        return _build(rec, cl.grade, cl.avg()) if rec else None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("grade_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        avg = obs.flags.get("grade_avg")
        gap = (f"  ({(obs.price_cents - avg) / 100:+.2f} vs avg)"
               if avg is not None and obs.price_cents is not None else "")
        return f"{money(obs.price_cents)}/L {obs.flags.get('grade')}{gap}  {item.name} ({item.extra.get('cp')})"

    def search_row(self, item, obs):
        pc = obs.price_cents if obs else None
        return f"{money(pc):>7}  {str(item.extra.get('cp') or '?'):>6}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  station  : {item.name}  ({e.get('adresse') or '?'})",
                 f"  location : {e.get('cp') or '?'} {e.get('departement') or ''}, {e.get('region') or ''}   [{e.get('lat')}, {e.get('lon')}]"]
        if obs:
            f = obs.flags
            lines.append(f"  {(f.get('grade') or 'grade'):<8} : {money(obs.price_cents)} / L   (national avg {money(f.get('grade_avg'))})")
            prices = f.get("prices") or {}
            others = "  ".join(f"{g}={money(prices[g])}" for g in GRADES if prices.get(g) is not None)
            lines.append(f"  all grades: {others}")
            lines.append(f"  updated  : {f.get('maj') or '?'}")
            if f.get("rupture"):
                lines.append(f"  rupture  : {f.get('rupture')}")
        return lines


SOURCE = FranceFuelSource()
