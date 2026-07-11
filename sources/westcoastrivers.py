"""westcoastrivers - live West Coast river flow/level via the regional council's keyless Hilltop server.

West Coast Regional Council publishes its real-time hydrology telemetry through a public Hilltop
server (hilltop.wcrc.govt.nz/data.hts) - the wettest region in NZ, where Southern Alps rainfall
drives the country's flashiest rivers: the Grey, Buller, Hokitika, Taramakau, Ahaura and their
tributaries. No key, no robots.txt (404 = nothing fenced), official council open data = sanctioned
-> trove.

The model and semantics live in trove/hilltop.py - the shared Hilltop class driver; this file is
the West Coast instance (~120 gauge sites).
"""
from __future__ import annotations

from trove.hilltop import HilltopRiversSource


class WestCoastRiversSource(HilltopRiversSource):
    name = "westcoastrivers"
    host = "https://hilltop.wcrc.govt.nz/data.hts"
    council = "West Coast"


SOURCE = WestCoastRiversSource()
