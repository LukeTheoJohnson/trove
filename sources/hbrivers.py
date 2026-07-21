"""hbrivers - live Hawke's Bay river flow/level via the regional council's keyless Hilltop server.

Hawke's Bay Regional Council publishes its real-time hydrology telemetry through a public Hilltop
server (data.hbrc.govt.nz/EnviroData/EMAR.hts) - the east-coast catchments that flood Napier and
Hastings: the Tutaekuri, Ngaruroro, Tukituki and their tributaries, the rivers that came down in
Cyclone Gabrielle. robots.txt carries only content-signal boilerplate (no path Disallow), official
council open data = sanctioned -> trove.

The model and semantics live in trove/hilltop.py - the shared Hilltop class driver; this file is the
Hawke's Bay instance. Note the endpoint filename is EnviroData/EMAR.hts (not the classic data.hts).
"""
from __future__ import annotations

from trove.hilltop import HilltopRiversSource


class HawkesBayRiversSource(HilltopRiversSource):
    name = "hbrivers"
    host = "https://data.hbrc.govt.nz/EnviroData/EMAR.hts"
    council = "Hawke's Bay"


SOURCE = HawkesBayRiversSource()
