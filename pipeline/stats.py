"""
Statistical summary for a mandal's sampled price distribution.

Every metric is computed on ``price_per_sqyd`` (₹ per sq. yard) -- the standard
unit of comparison for open plots in Andhra Pradesh residential markets -- and
also exposed as RANGE [min, max] for total plot prices.

Metrics per mandal:
  - n                     sample size
  - range_total [min,max] total asking price range (₹)
  - range_psqyd [min,max] ₹/sq.yd range
  - avg_psqyd, median_psqyd
  - p10 / p90 percentile ₹/sq.yd  (robust spread, less sensitive than min/max)
  - std_psqyd
  - avg_total              average total asking price
"""
from __future__ import annotations

import statistics


def _pct(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def mandal_stats(sampled: list, key: str, label: str, district: str) -> dict:
    """Compute the summary dict for one mandal's sample."""
    psqyd = sorted(p.price_per_sqyd for p in sampled)
    totals = sorted(p.price_inr for p in sampled)
    out = {
        "key": key,
        "label": label,
        "district": district,
        "n": len(psqyd),
        "range_psqyd": [psqyd[0], psqyd[-1]] if psqyd else [0, 0],
        "range_total": [totals[0], totals[-1]] if totals else [0, 0],
        "avg_psqyd": (sum(psqyd) / len(psqyd)) if psqyd else 0.0,
        "median_psqyd": statistics.median(psqyd) if psqyd else 0.0,
        "p10_psqyd": _pct(psqyd, 0.10),
        "p90_psqyd": _pct(psqyd, 0.90),
        "std_psqyd": statistics.pstdev(psqyd) if len(psqyd) > 1 else 0.0,
        "avg_total": (sum(totals) / len(totals)) if totals else 0.0,
    }
    return out


def district_rollup(mandal_stats_list: list[dict]) -> dict:
    """Aggregate a district across its mandals (weighted by sample size)."""
    m = [s for s in mandal_stats_list if s["n"] > 0]
    wsum = sum(s["avg_psqyd"] * s["n"] for s in m)
    n = sum(s["n"] for s in m)
    lo = min((s["p10_psqyd"] for s in m), default=0)
    hi = max((s["p90_psqyd"] for s in m), default=0)
    return {
        "n": n,
        "avg_psqyd": (wsum / n) if n else 0.0,
        "p10_psqyd": lo,
        "p90_psqyd": hi,
    }


def freshness_stats(sample: list, now) -> dict:
    """Freshness summary for a sample of listings that carry an updated_at date.

    Returns count, % updated within FRESHNESS_DAYS, and min/median/max age (days)
    of the listings that have a date.  Listings without a date are counted in
    ``n`` but excluded from the age statistics (``dated_n`` = how many had a date).
    """
    import datetime as _dt
    from . import config
    ages = []
    for p in sample:
        upd = getattr(p, "updated_at", "") or ""
        if not upd:
            continue
        try:
            d = _dt.date.fromisoformat(upd)
        except Exception:
            continue
        ages.append((now.date() - d).days)
    if not ages:
        return {"dated_n": 0, "pct_fresh": 0.0, "median_age_days": None,
                "min_age_days": None, "max_age_days": None}
    ages_sorted = sorted(ages)
    fresh = sum(1 for a in ages if a <= config.FRESHNESS_DAYS)
    return {
        "dated_n": len(ages),
        "pct_fresh": round(fresh / len(ages) * 100, 1),
        "median_age_days": int(_pct([float(a) for a in ages_sorted], 0.50)),
        "min_age_days": ages_sorted[0],
        "max_age_days": ages_sorted[-1],
    }
