"""horizonsrivers - live Manawatu-Whanganui river flow/level via Horizons' keyless Hilltop server.

Horizons Regional Council publishes its real-time hydrology telemetry through a public Hilltop
server (hilltopserver.horizons.govt.nz/data.hts) - the flood-prone Manawatu, Whanganui, Rangitikei
and their tributaries. No key, no robots.txt (the host returns its site HTML, nothing fenced),
official council open data = sanctioned -> trove.

The model and semantics live in trove/hilltop.py - the shared Hilltop class driver; this file is
the Horizons instance.
"""
from __future__ import annotations

from trove.hilltop import HilltopRiversSource


class HorizonsRiversSource(HilltopRiversSource):
    name = "horizonsrivers"
    host = "https://hilltopserver.horizons.govt.nz/data.hts"
    council = "Horizons"


SOURCE = HorizonsRiversSource()
