"""mdcrivers - live Marlborough river flow/level via the district council's keyless Hilltop server.

Marlborough District Council publishes its real-time hydrology telemetry through a public Hilltop
server (hydro.marlborough.govt.nz/data.hts) - the top of the South Island: the Wairau, Pelorus,
Awatere and their tributaries. No key, no robots.txt (404 = nothing fenced), official council open
data = sanctioned -> trove.

The model and semantics live in trove/hilltop.py - the shared Hilltop class driver; this file is
the Marlborough instance.
"""
from __future__ import annotations

from trove.hilltop import HilltopRiversSource


class MDCRiversSource(HilltopRiversSource):
    name = "mdcrivers"
    host = "https://hydro.marlborough.govt.nz/data.hts"
    council = "Marlborough"


SOURCE = MDCRiversSource()
