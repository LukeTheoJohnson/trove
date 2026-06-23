"""Spain fuel - MINETUR keyless government open-data REST (sedeaplicaciones.minetur.gob.es).

Per-station forecourt prices for every petrol station in Spain, published under the Geoportal de
Gasolineras open-data scheme. Keyless, no auth. The timeline value is the *ephemeral per-station
price*: the snapshot is the only record (nobody archives the per-station history), which is the
whole point of hoarding it.

Model: one Item per station (join key = "<provinceId>-<IDEESS>"), tracking the headline grade
(Gasolina 95 E5) as price_cents, with the full grade board + the province average carried in flags.
A "deal" = the station is at or below the province average for the headline grade. Prices are
euros/litre to 3 decimals; price_cents is whole euro-cents (clean display + sane drop granularity),
with the exact milli-euro values kept in flags so the hoard/export keeps full precision.

Search is scoped to one province (--cc = province id, default 28 = Madrid) and filtered by a
brand/town substring, because the API has no free-text station search - it serves whole provinces.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session
from trove.tracker import Source, money

UA = "trove/0.1 (+https://github.com/LukeTheoJohnson/trove)"
BASE = ("https://sedeaplicaciones.minetur.gob.es"
        "/ServiciosRESTCarburantes/PreciosCarburantes")

# station-record field key -> short grade label (the board shown by `item`). Keys read verbatim
# from a live payload, accents and all; the value lives under each key as a comma-decimal string.
GRADES = {
    "Precio Gasolina 95 E5": "G95E5",
    "Precio Gasolina 98 E5": "G98E5",
    "Precio Gasoleo A": "GOA",
    "Precio Gasoleo Premium": "GOA+",
    "Precio Gases licuados del petróleo": "GLP",
}
HEADLINE = "Precio Gasolina 95 E5"   # the grade tracked as price_cents


def _safe(s):
    """Fold to cp1252 (the Windows console codec) so an exotic char can't crash a print.
    Spanish (Latin-1) survives unchanged; anything rarer degrades to '?' instead of raising."""
    return (s or "").strip().encode("cp1252", "replace").decode("cp1252")


def _eur(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _avg_cents(stations):
    vals = [v for v in (_eur(s.get(HEADLINE)) for s in stations) if v is not None]
    return round(sum(vals) / len(vals) * 100) if vals else None


def _station(prov, st, avg_cents):
    brand = _safe(st.get("Rótulo", ""))
    loc = _safe(st.get("Localidad", ""))
    board, milli = {}, {}
    for key, lab in GRADES.items():
        e = _eur(st.get(key))
        if e is not None:
            board[lab] = f"{e:.3f}"
            milli[lab] = round(e * 1000)
    head = _eur(st.get(HEADLINE))
    item = Item(f"{prov}-{st.get('IDEESS', '')}",
                name=f"{brand} ({loc})" if brand else loc,
                subtitle=_safe(st.get("Dirección", "")),
                category=brand,
                extra={"municipio": loc, "cp": st.get("C.P.", ""),
                       "lat": st.get("Latitud", ""), "lon": st.get("Longitud (WGS84)", ""),
                       "horario": _safe(st.get("Horario", "")), "idees": st.get("IDEESS", "")})
    obs = Obs(price_cents=(round(head * 100) if head is not None else None),
              flags={"grade": "G95E5", "board": board, "milli": milli, "area_avg": avg_cents})
    return item, obs


class _Client:
    def __init__(self):
        self.s = retry_session()

    def _get(self, path):
        r = self.s.get(f"{BASE}/{path}",
                       headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
        r.raise_for_status()
        return r.json()

    def provincias(self):
        return self._get("Listados/Provincias/") or []

    def province(self, prov):
        return (self._get(f"EstacionesTerrestres/FiltroProvincia/{prov}") or {}).get("ListaEESSPrecio") or []


class SpainFuelSource(Source):
    name = "spainfuel"
    id_label = "STATION"
    cc_default = "28"        # province id (28 = Madrid); --cc <id> searches another province
    deal_label = "deal"      # deal = at/below the province average for G95E5

    def client(self, args):
        return _Client()

    def doctor(self, cl):
        provs = cl.provincias()
        return bool(provs), f"({len(provs)} provinces; keyless MINETUR REST)"

    def search(self, cl, term, args):
        stations = cl.province(args.cc)
        avg = _avg_cents(stations)
        t = term.lower()
        out = []
        for st in stations:
            hay = " ".join(str(st.get(k, "")) for k in
                           ("Rótulo", "Localidad", "Municipio", "Dirección")).lower()
            if t in hay:
                out.append(_station(args.cc, st, avg))
        return out

    def fetch(self, cl, item_id):
        prov, _, idees = str(item_id).partition("-")
        if not idees:
            return None
        stations = cl.province(prov)
        avg = _avg_cents(stations)
        for st in stations:
            if str(st.get("IDEESS")) == idees:
                return _station(prov, st, avg)
        return None

    def is_deal(self, obs):
        pc, avg = obs.price_cents, obs.flags.get("area_avg")
        return pc is not None and avg is not None and pc <= avg

    def deal_line(self, item, obs):
        b = obs.flags.get("board") or {}
        eur = b.get("G95E5") or money(obs.price_cents)
        avg = obs.flags.get("area_avg")
        gap = (f"  ({(avg - obs.price_cents) / 100:+.3f} vs area avg)"
               if avg is not None and obs.price_cents is not None else "")
        return f"G95E5 {eur} EUR/L{gap}  {item.name}"

    def format_item(self, item, obs):
        lines = [f"  brand    : {item.category}",
                 f"  address  : {item.subtitle}",
                 f"  town     : {item.extra.get('municipio', '')} ({item.extra.get('cp', '')})",
                 f"  hours    : {item.extra.get('horario', '')}"]
        if obs:
            for lab, val in (obs.flags.get("board") or {}).items():
                lines.append(f"  {lab:<8} : {val} EUR/L")
            avg = obs.flags.get("area_avg")
            if avg is not None:
                lines.append(f"  area avg : {avg / 100:.3f} EUR/L (G95E5)")
        return lines

    def poll_spacing(self):
        return 0.5


SOURCE = SpainFuelSource()
