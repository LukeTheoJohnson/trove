"""dolarapi - Argentina (and other LatAm) parallel/official USD exchange rates, keyless.

Argentina runs a thicket of USD rates: the official rate, the "blue" (street/black-market) rate, the
financial MEP/CCL rates, plus mayorista/cripto/tarjeta. dolarapi.com aggregates them live from market
sources; `GET /v1/dolares` returns every casa (oficial, blue, bolsa, contadoconliquidacion, mayorista,
cripto, tarjeta) with its buy/sell (compra/venta) and update time. robots.txt is content-signal
boilerplate only (no path Disallow), and the endpoint is the one the site's own page calls =
sanctioned -> trove. Opens **LatAm FX macro** breadth alongside `paralelobo` (Bolivia).

Like the parallel Bolivia rate, the *gap* between the blue and official rate is a genuinely
un-rebuildable macro signal that no one archives per-minute. `price_cents` = the casa's **venta (sell)
rate * 100** (centi-ARS per USD; so the core's `drops` = the peso strengthening / dollars getting
cheaper); `qty` = None. The official rate travels in each obs's flags as `official`, and `premium` =
casa venta / official venta. A "deal" ("premium") = the casa trades >= 10% above the official rate (a
parallel-market gap worth noting - dollars scarce/expensive on that channel). money() renders the
centi-ARS as '$' (it is pesos, ~1500 per USD).

Model: one Item per casa (join key = the casa slug). `--cc` picks the country host (default `ar`;
also `ve` Venezuela, `uy` Uruguay, `cl` Chile, `br` Brazil - each `<cc>.dolarapi.com`, `ar` is the
bare host). `search`/`fetch` read the same memoized feed.
"""
from __future__ import annotations

from trove.db import Item, Obs
from trove.session import retry_session, UA
from trove.tracker import Source, money, safe

HOSTS = {"ar": "https://dolarapi.com", "ve": "https://ve.dolarapi.com",
         "uy": "https://uy.dolarapi.com", "cl": "https://cl.dolarapi.com",
         "br": "https://br.dolarapi.com"}
PATH = "/v1/dolares"
PREMIUM_DEAL = 1.10      # casa venta >= 110% of the official rate = a notable parallel-market gap


def _f(v):
    return float(v) if isinstance(v, (int, float)) else None


def _official(rows):
    for r in rows:
        if (r.get("casa") or "").lower() == "oficial":
            return _f(r.get("venta")) or _f(r.get("promedio"))
    return None


def _build(r, official):
    casa = (r.get("casa") or "").strip()
    venta = _f(r.get("venta"))
    if venta is None:
        venta = _f(r.get("promedio"))       # some casas (VE) publish only promedio
    premium = round(venta / official, 4) if (venta and official) else None
    item = Item(casa, name=safe(r.get("nombre") or casa), subtitle=f"{r.get('moneda') or 'USD'} - {casa}",
                category="fx", extra={"moneda": r.get("moneda") or "USD"})
    obs = Obs(price_cents=(round(venta * 100) if venta else None), qty=None,
              flags={"casa": casa, "compra": _f(r.get("compra")), "venta": venta,
                     "promedio": _f(r.get("promedio")), "official": official, "premium": premium,
                     "updated": r.get("fechaActualizacion") or ""})
    return item, obs


class _Client:
    def __init__(self, cc):
        self.cc = cc if cc in HOSTS else "ar"
        self.s = retry_session()
        self._rows = None

    def rows(self):
        if self._rows is None:
            r = self.s.get(HOSTS[self.cc] + PATH,
                           headers={"Accept": "application/json", "User-Agent": UA}, timeout=40)
            r.raise_for_status()
            self._rows = r.json() or []
        return self._rows


class DolarApiSource(Source):
    name = "dolarapi"
    id_label = "CASA"
    cc_default = "ar"        # country host: ar|ve|uy|cl|br
    deal_label = "premium"   # casa venta >= 10% above the official rate
    search_header = f"{'VENTA':>9}  {'PREM':>5}  CASA"

    def client(self, args):
        return _Client(getattr(args, "cc", "ar"))

    def doctor(self, cl):
        rows = cl.rows()
        return bool(rows), f"({len(rows)} USD rates for '{cl.cc}'; keyless dolarapi.com)"

    def search(self, cl, term, args):
        rows = cl.rows()
        official = _official(rows)
        t = (term or "").lower()
        out = []
        for r in rows:
            item, obs = _build(r, official)
            if not t or t in item.id.lower() or t in safe(item.name).lower():
                out.append((item, obs))
        out.sort(key=lambda io: -(io[1].price_cents or 0))
        return out

    def fetch(self, cl, item_id):
        rows = cl.rows()
        official = _official(rows)
        for r in rows:
            if (r.get("casa") or "").strip() == str(item_id):
                return _build(r, official)
        return None

    def is_deal(self, obs):
        p = obs.flags.get("premium")
        return isinstance(p, (int, float)) and p >= PREMIUM_DEAL

    def deal_line(self, item, obs):
        f = obs.flags
        prem = f.get("premium")
        pct = f"+{round((prem - 1) * 100)}% over official" if isinstance(prem, (int, float)) else "?"
        return f"{item.name}  {f.get('venta')} ({pct})"

    def search_row(self, item, obs):
        f = obs.flags if obs else {}
        prem = f.get("premium")
        return (f"{str(f.get('venta') or '?'):>9}  "
                f"{(f'{prem:.2f}' if isinstance(prem, (int, float)) else '?'):>5}  {item.name}")

    def format_item(self, item, obs):
        lines = [f"  casa     : {item.name}  ({item.id})"]
        if obs:
            f = obs.flags
            lines.append(f"  rate     : compra {f.get('compra')}  venta {f.get('venta')} {item.extra.get('moneda')}")
            prem = f.get("premium")
            if isinstance(prem, (int, float)):
                lines.append(f"  premium  : {prem:.2f}x  (+{round((prem - 1) * 100)}% vs official {f.get('official')})")
            lines.append(f"  updated  : {f.get('updated') or '?'}")
        return lines


SOURCE = DolarApiSource()
