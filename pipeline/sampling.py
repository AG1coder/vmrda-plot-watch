"""
Sampling: assign fetched listings to mandals and draw the analysis set.

The user's spec asks for ~20 sampled prices per mandal/area.  We:
  1. Tile the raw listings onto canonical mandals via keyword matching.
  2. Apply light quality filters (drop extreme outliers, tiny parcels).
  3. Sample up to ``config.SAMPLE_SIZE`` listings per mandal (random, no
     replacement), with a deterministic seed so a given month is stable.
  4. Produce per-mandal price distributions for the stats engine.
"""
from __future__ import annotations

import random

from . import config
from .fetch import Listing


def _assign_tile(listings: list[Listing]) -> dict[str, list[Listing]]:
    """Group listings by mandal key. Listings whose locality matches no known
    mandal are dropped (out of VMRDA scope)."""
    tiles: dict[str, list[Listing]] = {m["key"]: [] for m in config.MANDALS}
    unassigned = 0
    for lst in listings:
        mandal = config.mandal_for_locality(lst.locality or lst.title)
        if mandal is None:
            unassigned += 1
            continue
        tiles[mandal["key"]].append(lst)
    print(f"      {unassigned} listings outside known VMRDA mandals (dropped)")
    return tiles


def _qualifies(lst: Listing) -> bool:
    """A listing counts toward a mandal's sample if we trust its numbers."""
    if lst.price_inr <= 0 or lst.area_sqyd <= 0 or lst.price_per_sqyd <= 0:
        return False
    # Drop likely scraping/parse artifacts outside the sane market window.
    if not (config.MIN_PSQYD <= lst.price_per_sqyd <= config.MAX_PSQYD):
        return False
    # Drop implausibly tiny parcels (< ~30 sq.ft) that distort per-sqyd math.
    if lst.area_sqyd < 3:
        return False
    # Plots only: drop big land parcels (farmland / multi-acre sites).
    if lst.area_sqyd > config.MAX_PLOT_AREA_SQYD:
        return False
    return True


def build_samples(
    listings: list[Listing],
    sample_size: int | None = None,
    seed: int = 42,
) -> dict[str, dict]:
    """Return {mandal_key: {"mandal":..., "district":..., "listings":[...], "sampled":[...]}}."""
    sample_size = sample_size or config.SAMPLE_SIZE
    rng = random.Random(seed)
    tiles = _assign_tile(listings)
    result: dict[str, dict] = {}
    for key, bucket in tiles.items():
        mandal = config.MANDAL_BY_KEY[key]
        qualified = [l for l in bucket if _qualifies(l)]
        sampled = rng.sample(qualified, min(sample_size, len(qualified))) \
            if qualified else []
        result[key] = {
            "key": key,
            "label": mandal["label"],
            "district": mandal["district"],
            "raw_count": len(bucket),
            "qualified_count": len(qualified),
            "sampled": sampled,
        }
    return result
