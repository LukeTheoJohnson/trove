"""northlandrivers - live Northland river flow/level via the regional council's keyless Hilltop server.

Northland Regional Council publishes its real-time hydrology telemetry through a public Hilltop
server (hilltop.nrc.govt.nz/data.hts) - the subtropical, flood-prone far north: the Awanui, Kaeo,
Waitangi, Utakura and their tributaries, the catchments that flood Kaitaia and the Bay of Islands in
an ex-tropical-cyclone deluge. No key, no robots.txt (404 = nothing fenced), official council open
data = sanctioned -> trove.

The model and semantics live in trove/hilltop.py - the shared Hilltop class driver; this file is
the Northland instance (~1100 gauge sites).
"""
from __future__ import annotations

from trove.hilltop import HilltopRiversSource


class NorthlandRiversSource(HilltopRiversSource):
    name = "northlandrivers"
    host = "https://hilltop.nrc.govt.nz/data.hts"
    council = "Northland"


SOURCE = NorthlandRiversSource()
