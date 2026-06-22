"""trove - a personal price and listing tracker: a compounding local price history
across several sources. One shared core, thin per-source drivers.

See the README for the design. A new source is a ~50-line driver in sources/ that
implements the Source hooks in trove.tracker.
"""
__version__ = "0.1.0"
