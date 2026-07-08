"""Polite, cadence-aware trove poller for Windows Task Scheduler.

Wake this every ~30 min from Task Scheduler. Each source has a polite interval matched
to how fast its data actually refreshes; a source is polled only when its most recent
logged observation is older than that interval. So slow sources are never hammered, and
you schedule *one* task instead of juggling a cron per source. Output is appended to
data/poll.log.

To add a source: seed its watchlist once (`python trove.py <src> watch add <id>`), then
add a line to CADENCE_MIN below. To pause everything: disable the "trove-poll" task
(`schtasks /Change /TN trove-poll /DISABLE`) - the watchlists and hoard stay intact.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Minutes between polls, matched to each source's real refresh rate. Polling faster than
# this just re-logs identical rows - wasted requests, no new signal.
CADENCE_MIN = {
    "em6": 30,        # half-hourly wholesale electricity spot
    "gwrivers": 60,   # river gauges update ~15-60 min
    "metno": 180,     # weather forecast drifts over hours
    "nzroads": 30,    # national highway disruption board; full-board sweep (see SWEEP)
    "outages": 30,    # outage lifecycles move in minutes; both networks swept (see SWEEP)
    "wildfire": 360,  # acreage/containment revisions land ~daily; 4 board snapshots/day
}
GAP_S = 20            # spacing between sources that fire in the same wake

# Sources whose hoard is the whole feed rather than a hand-picked watchlist run a
# full-board `search ""` instead of `poll` - still one GET per board (the client memoizes
# the feed), but new events auto-enter the hoard and a resolved event's absence bounds its
# lifetime. A watchlist would go stale as event ids retire. Each entry is a list of runs,
# so a multi-network source sweeps every board in one wake.
SWEEP = {
    "nzroads":  [["search", "", "--limit", "5"]],   # log all ~110 events; show top-severity 5 in the log
    "outages":  [["search", "", "--limit", "3"],    # powercor (default network)
                 ["--cc", "mbhydro", "search", "", "--limit", "3"]],
    "wildfire": [["search", "", "--limit", "3"]],   # ~600-incident US board; log all, show top 3
}


def _last_obs_age_min(src: str) -> float:
    """Minutes since the newest observation for a source; inf if it has none yet."""
    db = DATA / f"{src}.db"
    if not db.exists():
        return float("inf")
    try:
        con = sqlite3.connect(str(db))
        row = con.execute("SELECT MAX(ts) FROM obs").fetchone()
        con.close()
        if not row or not row[0]:
            return float("inf")
        last = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (sqlite3.Error, ValueError):
        return float("inf")
    return (datetime.now(timezone.utc) - last).total_seconds() / 60


def main() -> None:
    DATA.mkdir(exist_ok=True)
    due = [s for s, mins in CADENCE_MIN.items() if _last_obs_age_min(s) >= mins]
    if not due:
        return
    with (DATA / "poll.log").open("a", encoding="utf-8") as f:
        for i, src in enumerate(due):
            if i:
                time.sleep(GAP_S)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
            out = []
            for cmd in SWEEP.get(src, [["poll"]]):
                r = subprocess.run([sys.executable, "trove.py", src, *cmd],
                                   cwd=str(ROOT), capture_output=True, text=True)
                out.append((r.stdout + r.stderr).strip())
            f.write(f"[{stamp}] {src}\n" + "\n".join(out) + "\n")


if __name__ == "__main__":
    main()
