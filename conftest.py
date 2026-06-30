"""Put the repo root on sys.path so tests can import the `trove` package, the `sources`
package, and the `trove.py` entrypoint by path.

All tests in this repo are deliberately **offline** - none build a source client or hit a
network. CI runs them on every push, so they must never touch a third-party API (that would be
the exact "rude volume" the tool is careful to avoid). They exercise the stateful core and the
pure display/deal hooks against synthetic Item/Obs only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
