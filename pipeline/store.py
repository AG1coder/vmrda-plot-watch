"""
Persistence: write each monthly snapshot to disk and keep the full history.

Layout
------
data/
  latest.json          always the most recent full snapshot (used by the site)
  history/<YYYY-MM>.json   one file per monthly run (append-only archive)
  history/index.json   list of snapshot keys in chronological order

A snapshot is a JSON document containing fetched-at metadata plus per-mandal
and per-district summaries (computed by stats.py).  Raw per-listing numbers are
kept (lightly) so charts can show distribution dots, without bloating the site.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from . import config

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")


def _ensure_dirs():
    os.makedirs(HISTORY_DIR, exist_ok=True)


def snapshot_key(now: dt.datetime | None = None) -> str:
    return (now or dt.datetime.now()).strftime(config.SNAPSHOT_FORMAT)


def write_snapshot(snapshot: dict, now: dt.datetime | None = None) -> str:
    """Persist *snapshot* under data/ and return the snapshot key."""
    _ensure_dirs()
    key = snapshot.get("period") or snapshot_key(now)
    path = os.path.join(HISTORY_DIR, f"{key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    # Refresh history index (excluding the index file itself).
    keys = sorted(p for p in os.listdir(HISTORY_DIR)
                  if p.endswith(".json") and p != "index.json")
    index = {"periods": [k[:-5] for k in keys]}
    with open(os.path.join(HISTORY_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    return key


def read_snapshot(key: str) -> dict:
    path = os.path.join(HISTORY_DIR, f"{key}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_periods() -> list[str]:
    _ensure_dirs()
    keys = sorted(p[:-5] for p in os.listdir(HISTORY_DIR)
                  if p.endswith(".json") and p != "index.json")
    return keys


def history_series(metric: str = "avg_psqyd", mandal_key: str | None = None) -> list[dict]:
    """Return [{period, value}] across all snapshots for a metric/mandal.
    Useful for the trend line in the visualization."""
    series = []
    for period in list_periods():
        snap = read_snapshot(period)
        if mandal_key:
            m = snap["mandals"].get(mandal_key)
            if not m or m.get("n", 0) == 0:
                continue
            v = m.get(metric, 0)
        else:
            v = snap.get("region", {}).get(metric, 0)
        series.append({"period": period, "value": v})
    return series
