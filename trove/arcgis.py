"""Shared client for the keyless ArcGIS Feature Service class (ROADMAP §2).

One mechanic serves every instance (outages networks, wildfire, future utility/hazard layers):
resolve the right layer from FeatureServer metadata (unless the URL already pins one), query the
whole board with `where=1=1&outSR=4326`, and memoize per run - one polite request per board.
An instance should be a config row + field adapter over this client, not a copied driver.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .session import retry_session, UA


def to_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def epoch_ms(v):
    """ArcGIS epoch-ms date -> 'YYYY-MM-DD HH:MMZ' (UTC); '' when null/garbage."""
    n = to_int(v)
    if n is None:
        return ""
    return datetime.fromtimestamp(n / 1000, timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def coords(geometry):
    """(lat, lon) from a WGS84 feature geometry: point x/y, or a polygon's first ring vertex,
    or a polyline's first path vertex. (None, None) when absent."""
    g = geometry or {}
    if g.get("x") is not None and g.get("y") is not None:
        return g["y"], g["x"]
    for key in ("rings", "paths"):
        seq = g.get(key) or []
        if seq and seq[0]:
            return seq[0][0][1], seq[0][0][0]
    return None, None


class FeatureBoard:
    """Memoized whole-board reader for ArcGIS Feature Services.

    feed() takes a FeatureServer URL (layer resolved from metadata by preferred geometry type -
    layers aren't always id 0) or a pinned .../FeatureServer/<n> URL, and returns the layer's
    features. Each board is fetched at most once per run.
    """

    def __init__(self, timeout: int = 60):
        self.s = retry_session()
        self.timeout = timeout
        self._layer: dict[str, str] = {}   # fs_url -> layer url
        self._feed: dict[str, list] = {}   # layer url -> [features]

    def _headers(self):
        return {"User-Agent": UA, "Accept": "application/json"}

    def _layer_url(self, fs_url: str, geometry: str) -> str:
        if fs_url.rstrip("/").rsplit("/", 1)[-1].isdigit():
            return fs_url                   # already pinned to a layer
        if fs_url not in self._layer:
            r = self.s.get(fs_url, params={"f": "json"}, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            layers = (r.json() or {}).get("layers") or []
            want = f"esriGeometry{geometry.capitalize()}"
            pick = next((L["id"] for L in layers if L.get("geometryType") == want), None)
            if pick is None:
                pick = next((L["id"] for L in layers if geometry in (L.get("name") or "").lower()), None)
            if pick is None:
                pick = layers[0]["id"] if layers else 0
            self._layer[fs_url] = f"{fs_url}/{pick}"
        return self._layer[fs_url]

    def feed(self, fs_url: str, geometry: str = "point", out_fields: str = "*") -> list:
        url = self._layer_url(fs_url, geometry)
        if url not in self._feed:
            r = self.s.get(f"{url}/query",
                           params={"where": "1=1", "outFields": out_fields, "outSR": "4326",
                                   "returnGeometry": "true", "f": "json"},
                           headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            self._feed[url] = (r.json() or {}).get("features") or []
        return self._feed[url]
