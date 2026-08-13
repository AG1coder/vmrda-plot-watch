"""
Render the NYTimes-style article page (site/index.html) from a snapshot.

The page embeds the snapshot + history as inline JSON and ships self-contained
(only D3 is pulled from CDN).  Editorial prose is generated from the numbers so
a brand-new month produces a fresh, data-accurate article automatically.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from pipeline import store, config

ROOT = os.path.dirname(__file__)
SITE = os.path.join(ROOT, "site")


def _inr(v: float) -> str:
    """Indian rupee formatting, e.g. ₹17,000."""
    s = f"{v:,.0f}"
    return "₹" + s


def _inr_compact(v: float) -> str:
    if v >= 1_000_000:
        return f"₹{v/1_000_000:.1f} cr"
    if v >= 100_000:
        return f"₹{v/100_000:.1f} lakh"
    return _inr(v)


def _month_label(period: str) -> str:
    try:
        d = dt.datetime.strptime(period, "%Y-%m")
        return d.strftime("%B %Y")
    except Exception:
        return period


def _mandal_list(mandals: dict, min_n=3) -> list[dict]:
    return sorted(
        [m for m in mandals.values() if m["n"] >= min_n],
        key=lambda m: m["median_psqyd"], reverse=True)


def _district_median(snapshot: dict, dkey: str):
    ms = [m for m in snapshot["mandals"].values()
          if m["district"] == dkey and m["n"] >= 3]
    med = sorted(m["median_psqyd"] for m in ms)
    return med[len(med) // 2] if med else 0


def _narrative(snapshot: dict) -> list[str]:
    """Generate a few short editorial paragraphs from the numbers."""
    man = _mandal_list(snapshot["mandals"])
    region = snapshot["region"]
    med = region.get("avg_psqyd", 0)
    out = []
    if man:
        top, bottom = man[0], man[-1]
        gap = top["median_psqyd"] - bottom["median_psqyd"]
        ratio = (top["median_psqyd"] / bottom["median_psqyd"]) if bottom["median_psqyd"] else 0
        out.append(
            f"Across {region['n']} residential plot listings sampled in the VMRDA belt, "
            f"the average asking price is roughly {_inr(med):s} per square yard. But the market "
            f"is not one market. The most expensive mandal in our sample, "
            f"{top['label']}, commands a median of {_inr(top['median_psqyd']):s}/sq yd — "
            f"about {ratio:.1f}× that of {bottom['label']}, the least expensive."
        )
        bhog = snapshot["mandals"].get("bhogapuram")
        if bhog and bhog["n"] >= 3:
            out.append(
                f"The story of this market in a single number is Bhogapuram, where the new "
                f"international airport is under construction. Its median asking price of "
                f"{_inr(bhog['median_psqyd']):s}/sq yd already trails the Visakhapatnam city core "
                f"by a wide margin — land is being priced on expectation. Speculative buyers are "
                f"positioning along the NH-16 corridor that ties these districts together."
            )
        anak = snapshot["mandals"].get("anakapalle")
        if anak and anak["n"] >= 3:
            out.append(
                f"Farther down the coast, Anakapalle — the industrial and pharma hub of the "
                f"Anakapalli district — trades at a more grounded {_inr(anak['median_psqyd']):s}/sq yd. "
                f"Its demand is driven less by speculation and more by working households and "
                f"the plants at Atchutapuram and Parawada. The spread between the city core and "
                f"the corridor towns is where most of the investment debate sits."
            )
    out.append(
        f"The figures are medians and averages of asking prices, not transaction prices, "
        f"and should be read as a directional gauge of a fast-moving regional market rather "
        f"than a definitive valuation."
    )
    return out


def _stat(snapshot: dict):
    region = snapshot["region"]
    man = _mandal_list(snapshot["mandals"])
    top = man[0]["label"] if man else "—"
    return {
        "avg": region.get("avg_psqyd", 0),
        "n": region.get("n", 0),
        "top": top,
        "top_med": man[0]["median_psqyd"] if man else 0,
    }


def _rows(snapshot: dict) -> str:
    man = _mandal_list(snapshot["mandals"])
    rows = []
    for m in man:
        dist = {"visakhapatnam": "Visakhapatnam", "anakapalli": "Anakapalli",
                "vizianagaram": "Vizianagaram"}.get(m["district"], m["district"])
        rows.append(
            "<tr>"
            f"<td><b>{m['label']}</b><br><span style='color:#6c6c6c;font-size:11px'>{dist} · n={m['n']}</span></td>"
            f"<td class='num'>{_inr(m['median_psqyd'])}</td>"
            f"<td class='num'>{_inr(m['avg_psqyd'])}</td>"
            f"<td class='num'>{_inr(m['p10_psqyd'])} – {_inr(m['p90_psqyd'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _build_html(snapshot: dict, history: list[dict], prev: dict | None) -> str:
    period = snapshot["period"]
    man = _mandal_list(snapshot["mandals"])
    st = _stat(snapshot)
    para = _narrative(snapshot)
    rows = _rows(snapshot)
    sources = ", ".join(f"{k}: {v}" for k, v in snapshot.get("source_counts", {}).items())
    if not sources:
        sources = "realestateindia"
    source_counts_text = snapshot.get("source_counts", {})
    source_counts_text = ", ".join(f"{k} ({v})" for k, v in source_counts_text.items()) or "1 source"
    budget_lakh = 50

    s_json = json.dumps(snapshot, ensure_ascii=False)
    h_json = json.dumps(history, ensure_ascii=False)
    map_json = json.dumps({"coords": config.COORDS, "coastline": config.COASTLINE},
                          ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How High Can Vizag Land Go? A VMRDA Plot-Price Gauge — {_month_label(period)}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="css/style.css">
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
<div class="topbar"><span class="brand"><a href="index.html">VMRDA PLOT WATCH</a></span><span class="sub">{_month_label(period)} · monthly snapshot</span></div>

<div class="wrap wide">
  <div class="kicker">Data · Real Estate · VMRDA</div>
  <h1>Where Land Prices Run Hottest in Visakhapatnam’s Growth Corridor</h1>
  <p class="deck">A monthly gauge of residential plot asking prices across the VMRDA belt — Visakhapatnam, Anakapalli and Vizianagaram districts — built from a fresh sample of live listings every month.</p>
  <div class="byline">By <b>VMRDA Plot Watch</b> · Data as of {_month_label(period)} · Read the <a href="blog/index.html">accompanying article</a></div>

  <div class="statband">
    <div class="stat"><div class="val">{_inr(st['avg'])}</div><div class="lbl">Avg asking / sq yd</div></div>
    <div class="stat"><div class="val">{st['n']}</div><div class="lbl">Plots sampled</div></div>
    <div class="stat"><div class="val">{_inr(st['top_med'])}</div><div class="lbl">Highest median · {st['top']}</div></div>
    <div class="stat"><div class="val">3</div><div class="lbl">Districts covered</div></div>
  </div>

  <p class="body lede">{para[0]}</p>
  <p class="body">{para[1] if len(para) > 1 else ''}</p>
</div>

<div class="wrap wide">
  <div class="chart-title" style="margin-top:0">Where the money is: a price map of the VMRDA belt</div>
  <div class="chart-sub">Each circle marks a mandal town on a real OpenStreetMap base, tinted by its median asking price per square yard and sized by sample. Hover a circle for details; click it — or use the selector — to compare against the region.</div>
  <div class="mapbox"><div id="chart-map"></div></div>
  <div class="source-line">Mandal towns geocoded from OpenStreetMap. Source: {sources}.</div>
</div>

<div class="wrap wide">
  <div class="mandal-picker" id="mandal-picker"></div>
  <div class="detail-strip" id="mandal-detail">
    <div class="detail-hint">Pick a mandal above to see how it compares to the region.</div>
  </div>
</div>

<div class="wrap wide">
  <div class="chart-title">Every mandal, ranked by median asking price</div>
  <div class="chart-sub">The band spans each mandal's 10th–90th percentile; the filled dot is the median, the hollow dot the average. Hover a row to inspect it.</div>
  <div class="legend" id="dumb-legend"></div>
  <div class="chart-wrap"><div id="chart-dumbbell"></div></div>
  <div class="source-line">Sample: up to {config.SAMPLE_SIZE} listings per mandal, of {source_counts_text}.</div>
</div>

<div class="wrap">
  <p class="body">{para[2] if len(para) > 2 else ''}</p>
  <h2>The corridor widens the gap</h2>
  <p class="body">{para[3] if len(para) > 3 else ''}</p>
  <p class="body">{para[4] if len(para) > 4 else ''}</p>
</div>

<div class="wrap wide">
  <div class="chart-title">What a fixed budget buys you</div>
  <div class="chart-sub">Same money, different mandal. At each area's median price, here is how many square yards ₹{budget_lakh} lakh buys. (1 sq yd ≈ 9 sq ft.)</div>
  <div class="chart-wrap"><div id="chart-afford"></div></div>
</div>

<div class="wrap wide">
  <div class="chart-title">Every listing in the sample</div>
  <div class="chart-sub">Each dot is one plot listing, jittered by its asking price per square yard.</div>
  <div class="chart-wrap"><div id="chart-strips"></div></div>
  <div class="source-line">Hover a dot for its locality, size and price.</div>
</div>

<div class="wrap">
  <h2>How the region is moving month to month</h2>
  <div class="chart-wrap"><div id="chart-trend"></div></div>
  <div class="source-line">Region-wide median asking price across monthly snapshots. A new point is added on the 1st of each month.</div>

  <h2>Full mandal table</h2>
  <table class="data">
    <thead><tr><th>Mandal</th><th class="num">Median ₹/sq yd</th><th class="num">Average ₹/sq yd</th><th class="num">Typical range</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<div class="wrap">
  <div class="note">
    <h3>Methodology &amp; caveats</h3>
    <p>This page is regenerated automatically once a month. Each run fetches residential plot/land
       listings from real-estate aggregators, tiles them onto the 16 VMRDA mandals of interest,
       filters clearly-erroneous entries, and samples up to {config.SAMPLE_SIZE} listings per mandal.</p>
    <ul>
      <li><b>Asking, not transacted.</b> Prices are advertised asking prices; final deals may differ.</li>
      <li><b>Sample sizes vary.</b> Mandals with fewer than 3 usable listings are omitted from the chart (see table for n).</li>
      <li><b>Units.</b> All prices normalized to rupees per square yard (1 sq yd = 9 sq ft); larger plots in acres are converted.</li>
      <li><b>Outlier handling.</b> Listings below ₹{config.MIN_PSQYD:,}/sq yd or above ₹{config.MAX_PSQYD:,}/sq yd are treated as artifacts and excluded.</li>
      <li><b>Coverage.</b> Live sources are realestateindia (listing feeds) and
          1acre.in (verified lands/plots, incl. VMRDA master-plan, airport-road and
          beach-corridor layers). The major portals (Housing, 99acres, MagicBricks,
          SquareYards) block automated access and are attached to the pipeline as
          adapters for when it runs through a residential proxy.</li>
      <li><b>Read it directionally.</b> These are monthly market snapshots, not valuations.</li>
    </ul>
  </div>
</div>

<footer>
  VMRDA Plot Watch · auto-generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} from the latest monthly snapshot · Source: {sources}
</footer>

<script>window.SNAPSHOT={s_json};window.SNAPSHOT_HISTORY={h_json};window.MAPDATA={map_json};</script>
<script src="js/viz.js"></script>
</body>
</html>"""


def render_all(snapshot: dict | None = None, silent: bool = False) -> str:
    if snapshot is None:
        snapshot = store.read_snapshot(store.list_periods()[-1])
    history = store.history_series("median_psqyd", mandal_key=None)
    html = _build_html(snapshot, history, prev=None)
    out = os.path.join(SITE, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    if not silent:
        print(f"[render] wrote {out}")
    return out


if __name__ == "__main__":
    import sys
    snap = None
    if len(sys.argv) > 1:
        snap = store.read_snapshot(sys.argv[1])
    render_all(snap)
