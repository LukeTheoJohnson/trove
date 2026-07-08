"""gwrivers - live Greater Wellington river flow/level via the council's keyless Hilltop server.

Greater Wellington Regional Council publishes its real-time hydrology telemetry through a public
Hilltop server (hilltop.gw.govt.nz/Data.hts) - the same open-data backend LAWA aggregates. No key,
no robots.txt (404 = nothing fenced), official council open data = sanctioned -> trove.

The model and semantics (rise detection, centi-cumecs price_cents, display) live in
trove/hilltop.py - the shared Hilltop class driver; this file is the Greater Wellington instance
(~3300 gauge sites).
"""
from __future__ import annotations

from trove.hilltop import HilltopRiversSource


class GWRiversSource(HilltopRiversSource):
    name = "gwrivers"
    host = "https://hilltop.gw.govt.nz/Data.hts"
    council = "Greater Wellington"


SOURCE = GWRiversSource()
