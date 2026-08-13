"""
Orchestrator: fetch -> tile -> sample -> stats -> persist -> optionally render.

Usage (from repo root):
    python -m pipeline.run            # fetch + sample + stats + persist
    python -m pipeline.run --dry-run  # fetch + compute, print, don't persist
    python -m pipeline.run --max-pages N
    python -m pipeline.run --render   # also regenerate site + blog
"""
from __future__ import annotations

import argparse
import datetime as dt
import json

from . import config
from .fetch import fetch_all, Listing
from .sampling import build_samples
from .stats import mandal_stats, district_rollup, freshness_stats
from . import store


def _serialize(snapshot: dict) -> dict:
    """Convert any Listing objects in nested structures to plain dicts."""
    def clean(o):
        if isinstance(o, Listing):
            return {
                "locality": o.locality,
                "district_raw": o.district_raw,
                "price_inr": round(o.price_inr, 0),
                "area_sqyd": round(o.area_sqyd, 1),
                "price_per_sqyd": round(o.price_per_sqyd, 0),
                "source": o.source,
                "url": o.url,
                "updated_at": o.updated_at,
            }
        if isinstance(o, list):
            return [clean(i) for i in o]
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        return o
    return clean(snapshot)


def build_snapshot(max_pages: int = 3, seed: int = 42, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now()
    print(f"[vmrda-plot-watch] fetching listings (max_pages={max_pages}) ...")
    listings, source_counts = fetch_all(max_pages=max_pages)
    print(f"  total raw listings fetched: {len(listings)}  ({source_counts})")

    samples = build_samples(listings, seed=seed)

    mandals_out = {}
    district_data = {k: [] for k in config.districts_in_order()}
    for key, s in samples.items():
        stats = mandal_stats(s["sampled"], key, s["label"], s["district"])
        stats["raw_count"] = s["raw_count"]
        stats["qualified_count"] = s["qualified_count"]
        stats["freshness"] = freshness_stats(s["sampled"], now)
        stats["sample_listings"] = [
            {"locality": l.locality, "price_per_sqyd": round(l.price_per_sqyd, 0),
             "price_inr": round(l.price_inr, 0), "area_sqyd": round(l.area_sqyd, 1),
             "url": l.url, "source": l.source, "updated_at": l.updated_at}
            for l in s["sampled"]
        ]
        mandals_out[key] = stats
        district_data[stats["district"]].append(stats)

    districts_out = {}
    for dkey, mstats in district_data.items():
        roll = district_rollup(mstats)
        districts_out[dkey] = {
            **roll,
            "mandals": [m["key"] for m in mstats if m["n"] > 0],
        }

    region = district_rollup([s for s in mandals_out.values()])

    # Region-wide median + freshness over the actual sampled listings.
    import statistics as _st
    all_samples = [l for s in samples.values() for l in s["sampled"]]
    all_psqyd = [l.price_per_sqyd for l in all_samples]
    region["median_psqyd"] = _st.median(all_psqyd) if all_psqyd else 0.0
    region["freshness"] = freshness_stats(all_samples, now)

    snapshot = {
        "period": store.snapshot_key(now),
        "fetched_at": now.isoformat(timespec="seconds"),
        "sample_size": config.SAMPLE_SIZE,
        "source_counts": source_counts,
        "region": region,
        "districts": districts_out,
        "mandals": mandals_out,
    }
    return _serialize(snapshot)


def main():
    ap = argparse.ArgumentParser(description="VMRDA plot-price pipeline")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--render", action="store_true", help="regenerate site after persist")
    args = ap.parse_args()

    snapshot = build_snapshot(max_pages=args.max_pages, seed=args.seed)
    print(json.dumps({k: snapshot[k] for k in ("period", "region", "source_counts")},
                     indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[dry-run] not persisting.")
        return

    key = store.write_snapshot(snapshot)
    print(f"[vmrda-plot-watch] persisted snapshot {key} -> data/")

    if args.render:
        from render_site import render_all
        render_all(snapshot)
        from generate_blog import generate_blog
        generate_blog(snapshot)


if __name__ == "__main__":
    main()
