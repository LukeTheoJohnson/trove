"""italyfuel - per-station Italian forecourt fuel prices via the MIMIT Osservaprezzi open data, keyless.

The Italian Ministry of Enterprise (MIMIT, ex-MISE) publishes every service station's pump prices as
daily open CSV under `mimit.gov.it/images/exportCSV/`: `prezzo_alle_8.csv` (pipe-delimited
`idImpianto|descCarburante|prezzo|isSelf|dtComu` - a row per fuel type x self/served) and
`anagrafica_impianti_attivi.csv` (the station registry: operator, brand, name, address, comune,
provincia, lat, lon). robots.txt carries no Disallow for the export path and the data is published for
reuse (Osservaprezzi Carburanti) = sanctioned -> trove. The EU twin of `spainfuel`/`francefuel`/
`fuelwatch`, extending the ephemeral per-station forecourt-price hoard into **Italy**.

A forecourt price is overwritten in place and never archived per-station, so the snapshot is the only
record. `--cc` picks the tracked grade (default `benzina`; also `gasolio`, `gpl`, `metano`);
`price_cents` = that grade's self-service price in euro-cents (so the core's `drops` = the pump getting
*cheaper*); `qty` = the count of grades the station sells. A "deal" ("cheap") = the grade is at or below
the national sample average. Served-vs-self and the other grades ride in flags. money() renders
euro-cents (a '$' glyph on the cp1252 console; the value is euros).

Model: one Item per station (join key = `idImpianto`); the two CSVs are fetched once and merged by id.
`search <term>` filters by comune/provincia (pass "" to list); `fetch` scans the merged board.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

PRICES = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
REGISTRY = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
# tracked grade -> the descCarburante substring that identifies it
GRADES = {"benzina": "benzina", "gasolio": "gasolio", "gpl": "gpl", "metano": "metano"}


def _cents(v):
    try:
        return round(float(str(v).replace(",", ".")) * 100)
    except (TypeError, ValueError):
        return None


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _build(sid, reg, grades_prices, grade, avg):
    """grades_prices = {grade_key: cents (self-service preferred)}; reg = registry fields dict."""
    pc = grades_prices.get(grade)
    name = safe(reg.get("nome") or reg.get("comune") or sid)
    item = Item(sid, name=name, subtitle=safe(reg.get("indirizzo") or ""),
                category=safe(reg.get("provincia") or "IT"),
                extra={"comune": safe(reg.get("comune") or ""), "provincia": safe(reg.get("provincia") or ""),
                       "brand": safe(reg.get("bandiera") or ""), "lat": _f(reg.get("lat")),
                       "lon": _f(reg.get("lon"))})
    avail = [g for g, c in grades_prices.items() if c is not None]
    obs = Obs(price_cents=pc, qty=len(avail),
              flags={"grade": grade, "unit": "euro-cents", "grade_avg": avg,
                     "prices": grades_prices, "available": ",".join(avail),
                     "comune": safe(reg.get("comune") or "")})
    return item, obs


class _Client:
    def __init__(self, grade):
        self.grade = grade if grade in GRADES else "benzina"
        self.s = retry_session()
        self._board = None       # sid -> {"reg": {...}, "prices": {grade: cents}}
        self._avg = None

    def _get(self, url):
        r = self.s.get(url, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        return r.content.decode("utf-8", "replace").splitlines()

    def board(self):
        if self._board is None:
            prices = {}
            for ln in self._get(PRICES)[2:]:              # skip "Estrazione..." + header
                p = ln.split("|")
                if len(p) < 4:
                    continue
                sid, desc, prezzo, is_self = p[0].strip(), (p[1] or "").lower(), p[2], p[3].strip()
                grade = next((g for g, needle in GRADES.items() if needle in desc), None)
                if not grade:
                    continue
                cents = _cents(prezzo)
                if cents is None:
                    continue
                slot = prices.setdefault(sid, {})
                # prefer the self-service price (is_self == '1'); else keep the served price
                if grade not in slot or is_self == "1":
                    slot[grade] = cents
            reg = {}
            for ln in self._get(REGISTRY)[2:]:
                p = ln.split("|")
                if len(p) < 10:
                    continue
                reg[p[0].strip()] = {"nome": p[4], "indirizzo": p[5], "comune": p[6],
                                     "provincia": p[7], "lat": p[8], "lon": p[9], "bandiera": p[2]}
            self._board = {sid: {"reg": reg.get(sid, {}), "prices": pr} for sid, pr in prices.items()}
        return self._board

    def avg(self):
        if self._avg is None:
            vals = [b["prices"].get(self.grade) for b in self.board().values()]
            vals = [c for c in vals if c is not None]
            self._avg = round(sum(vals) / len(vals)) if vals else None
        return self._avg


class ItalyFuelSource(Source):
    name = "italyfuel"
    id_label = "STATION"
    cc_default = "benzina"      # grade: benzina|gasolio|gpl|metano
    deal_label = "cheap"        # grade at/below the national sample average
    search_limit_default = 25
    search_header = f"{'PRICE':>7}  {'PROV':>4}  STATION"

    def client(self, args):
        return _Client(getattr(args, "cc", "benzina"))

    def doctor(self, cl):
        board = cl.board()
        return bool(board), f"({len(board)} IT stations, grade '{cl.grade}'; keyless MIMIT Osservaprezzi CSV)"

    def search(self, cl, term, args):
        avg = cl.avg()
        t = (term or "").lower()
        out = []
        for sid, b in cl.board().items():
            reg = b["reg"]
            hay = f"{reg.get('comune', '')} {reg.get('provincia', '')} {reg.get('nome', '')}".lower()
            if b["prices"].get(cl.grade) is None:
                continue
            if not t or t in hay:
                out.append(_build(sid, reg, b["prices"], cl.grade, avg))
        out.sort(key=lambda io: (io[1].price_cents if io[1].price_cents is not None else 10 ** 9))
        return out[: self.search_limit_default * 4]

    def fetch(self, cl, item_id):
        b = cl.board().get(str(item_id))
        return _build(str(item_id), b["reg"], b["prices"], cl.grade, cl.avg()) if b else None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("grade_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        avg = obs.flags.get("grade_avg")
        gap = (f"  ({(obs.price_cents - avg) / 100:+.3f} vs avg)" if avg is not None and obs.price_cents is not None else "")
        return f"{money(obs.price_cents)}/L {obs.flags.get('grade')}{gap}  {item.name} ({item.extra.get('comune')})"

    def search_row(self, item, obs):
        pc = obs.price_cents if obs else None
        return f"{money(pc):>7}  {str(item.extra.get('provincia') or '?'):>4}  {item.name}"

    def format_item(self, item, obs):
        e = item.extra
        lines = [f"  station  : {item.name}  ({e.get('brand') or '?'})",
                 f"  location : {e.get('comune') or '?'} ({e.get('provincia') or '?'})   [{e.get('lat')}, {e.get('lon')}]"]
        if obs:
            f = obs.flags
            lines.append(f"  {(f.get('grade') or 'grade'):<8} : {money(obs.price_cents)} / L   (national avg {money(f.get('grade_avg'))})")
            prices = f.get("prices") or {}
            others = "  ".join(f"{g}={money(prices[g])}" for g in GRADES if prices.get(g) is not None)
            lines.append(f"  all grades: {others}")
        return lines


SOURCE = ItalyFuelSource()
