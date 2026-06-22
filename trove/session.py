"""Shared retrying HTTP session for all sources."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def retry_session(extra_status: tuple[int, ...] = ()) -> requests.Session:
    """A requests.Session with backoff retries on transient failures.

    extra_status lets a source add codes it wants retried (e.g. iTunes 403 burst-throttle).
    """
    s = requests.Session()
    retry = Retry(total=3, connect=3, read=3, backoff_factor=0.6,
                  status_forcelist=(429, 500, 502, 503, 504, *extra_status),
                  allowed_methods=frozenset({"GET"}),
                  respect_retry_after_header=True, raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s
