"""
Generate the long-form blog article (site/blog/index.html) from a snapshot.

Every monthly pipeline run regenerates this: the narrative is recomputed from
the latest numbers, so the article is always current and data-accurate.  When
more than one snapshot exists, it also reports month-over-month movement.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from pipeline import store, config
from render_site import _inr, _inr_compact, _month_label, _mandal_list, _district_median

ROOT = os.path.dirname(__file__)
BLOG = os.path.join(ROOT, "site", "blog")


def _movement(mandal_key: str, history: list[dict]) -> tuple[float | None, float | None]:
    """Return (latest, previous) median for a mandal across snapshots, if available."""
    vals = {h["period"]: h["value"] for h in history}
    periods = sorted(vals.keys())
    if len(periods) < 2:
        return None, None
    return vals[periods[-1]], vals[periods[-2]]


def _section_corridor(snapshot: dict, history: list[dict]) -> str:
    man = _mandal_list(snapshot["mandals"])
    city = snapshot["mandals"].get("visakhapatnam-urban")
    bhog = snapshot["mandals"].get("bhogapuram")
    ana = snapshot["mandals"].get("anakapalle")
    vzm = snapshot["mandals"].get("vizianagaram")
    parts = [f"""<p class="body lede">There is a simple way to read the Visakhapatnam Metropolitan Region's
        residential land market this month: priced to promise. The Bhogapuram international airport,
        under construction a little north of the city, has turned a once-sleepy stretch of the NH-16
        corridor into the region's most watched speculation play.</p>"""]
    if bhog and bhog["n"] >= 3:
        parts.append(f"""<p class="body">Bhogapuram's median asking price of <b>{_inr(bhog['median_psqyd'])}</b> per square
            yard is already well above the Vizianagaram district average of
            <b>{_inr(_district_median(snapshot, 'vizianagaram'))}/sq yd</b>. That premium is not about buildings
            — it is about a runway. Land here is being bought on the expectation of the airport's
            opening, its special economic zone, and the hotels and logistics that follow.</p>""")
    if ana and ana["n"] >= 3:
        parts.append(f"""<p class="body">The contrast with Anakapalle, the industrial anchor of the Anakapalli district, is
            instructive. There the median sits at <b>{_inr(ana['median_psqyd'])}/sq yd</b> — roughly
            {ana['median_psqyd']/bhog['median_psqyd']:.1f}× cheaper than Bhogapuram. Its buyers are owners
            and workers tied to the Atchutapuram and Parawada plants, not speculators. One corridor,
            two entirely different demand curves.</p>""")
    return "\n".join(parts)


def _section_rankings(snapshot: dict, history: list[dict]) -> str:
    man = _mandal_list(snapshot["mandals"])
    top = man[0]
    rows = []
    for i, m in enumerate(man[:6], 1):
        rows.append(
            f"<tr><td>{i}</td><td><b>{m['label']}</b></td>"
            f"<td class='num'>{_inr(m['median_psqyd'])}</td>"
            f"<td class='num'>{_inr(m['avg_psqyd'])}</td>"
            f"<td class='num'>{_inr(m['p10_psqyd'])} – {_inr(m['p90_psqyd'])}</td></tr>")
    return f"""<h2>The pecking order</h2>
    <p class="body">Ranked by median asking price, {top['label']} leads the pack this month at
        {_inr(top['median_psqyd'])}/sq yd. The table below shows the top placements; the full
        ranking is in the companion data page.</p>
    <table class="data">
      <thead><tr><th>#</th><th>Mandal</th><th class="num">Median ₹/sq yd</th><th class="num">Avg ₹/sq yd</th><th class="num">Range</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""


def _section_districts(snapshot: dict, history: list[dict]) -> str:
    ds = snapshot["districts"]
    cell = lambda k: (f"<b>{_inr(ds[k]['avg_psqyd'])}</b> <span style='color:#6c6c6c;font-size:12px'>(n={ds[k]['n']})</span>")
    return f"""<h2>Three districts, three speeds</h2>
    <p class="body">Rolled up by district, the picture is of an axis that cools as it moves away from the sea.
       Visakhapatnam proper carries the highest prices; Anakapalli anchors the value end; Vizianagaram
       — including the airport zone — sits in between, and is the one to watch.</p>
    <table class="data">
      <thead><tr><th>District</th><th class="num">Avg ₹/sq yd</th><th class="num">Mandals sampled</th></tr></thead>
      <tbody>
        <tr><td>Visakhapatnam</td><td class="num">{cell('visakhapatnam')}</td><td class="num">{len(ds['visakhapatnam']['mandals'])}</td></tr>
        <tr><td>Vizianagaram</td><td class="num">{cell('vizianagaram')}</td><td class="num">{len(ds['vizianagaram']['mandals'])}</td></tr>
        <tr><td>Anakapalli</td><td class="num">{cell('anakapalli')}</td><td class="num">{len(ds['anakapalli']['mandals'])}</td></tr>
      </tbody>
    </table>"""


def _section_trend(snapshot: dict, history: list[dict]) -> str:
    if len(history) < 2:
        return """<h2>Where it goes from here</h2>
        <p class="body">This is the first snapshot in the series, so there is no trend to measure yet.
        Check back next month: the monthly pipeline will add a data point and start tracking how the
        corridor's land market moves — whether Bhogapuram's premium widens, whether city-core prices
        hold, and whether the value segment in Anakapalli catches up.</p>"""
    latest, prev = history[-1], history[-2]
    chg = ((latest["value"] - prev["value"]) / prev["value"] * 100) if prev["value"] else 0
    dirn = "rose" if chg > 0 else ("fell" if chg < 0 else "held steady")
    return f"""<h2>Where it goes from here</h2>
    <p class="body">Tracked since {_month_label(history[0]['period'])}, the region-wide average asking price
        {dirn} from <b>{_inr(prev['value'])}</b> to <b>{_inr(latest['value'])}/sq yd</b> this month
        ({chg:+.1f}%). The real test will come over the next few months, as the airport moves closer to
        opening and the corridor's premium either firms up or cools.</p>"""


def _build_html(snapshot: dict, history: list[dict]) -> str:
    period = snapshot["period"]
    sources = ", ".join(f"{k}: {v}" for k, v in snapshot.get("source_counts", {}).items()) or "realestateindia"
    s_json = json.dumps(snapshot, ensure_ascii=False)
    h_json = json.dumps(history, ensure_ascii=False)
    map_json = json.dumps({"coords": config.COORDS, "coastline": config.COASTLINE}, ensure_ascii=False)
    body = "\n".join([_section_corridor(snapshot, history),
                      '<div class="chart-title">Where the money is: the VMRDA price map</div>'
                      '<div class="chart-sub">Mandal towns on a real OpenStreetMap base, tinted by median asking price per sq yd and sized by sample. Click a circle or use the selector.</div>'
                      '<div class="mapbox"><div id="chart-map"></div></div>',
                      '<div class="mandal-picker" id="mandal-picker"></div>'
                      '<div class="detail-strip" id="mandal-detail"><div class="d-hint">Pick a mandal to compare it with the region.</div></div>',
                      '<div class="chart-title">What a fixed budget buys you</div>'
                      '<div class="chart-sub">Square yards of open plot ₹50 lakh buys at each mandal\'s median price.</div>'
                      '<div class="chart-wrap"><div id="chart-afford"></div></div>',
                      _section_rankings(snapshot, history),
                      _section_districts(snapshot, history),
                      '<div class="chart-title">Region-wide median, month to month</div>'
                      '<div class="chart-wrap"><div id="chart-trend"></div></div>',
                      _section_trend(snapshot, history)])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The VMRDA Land Market, One Month at a Time — {_month_label(period)}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="../css/style.css">
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
<div class="topbar"><span class="brand"><a href="../index.html">VMRDA PLOT WATCH</a></span><span class="sub">{_month_label(period)} · blog</span></div>
<div class="wrap wide">
  <div class="kicker">Analysis · Real Estate · VMRDA</div>
  <h1>A Monthly Read on Visakhapatnam's Land Market</h1>
  <div class="byline">By <b>VMRDA Plot Watch</b> · {_month_label(period)} · Data-backed, auto-generated monthly</div>
  {body}
  <div class="note">
    <h3>Methodology</h3>
    <p>Each month the pipeline fetches residential plot/land listings, samples up to
       {config.SAMPLE_SIZE} per mandal, normalizes prices to ₹/sq yd, and drops outliers outside
       ₹{config.MIN_PSQYD:,}–₹{config.MAX_PSQYD:,}/sq yd. Figures are <b>asking prices</b>, not
       transactions, and are directional. Source feeds: {sources}.</p>
  </div>
  <p style="margin-top:30px"><a href="../index.html">← Back to the interactive data page</a></p>
</div>
<footer>VMRDA Plot Watch · auto-generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}</footer>
<script>window.SNAPSHOT={s_json};window.SNAPSHOT_HISTORY={h_json};window.MAPDATA={map_json};</script>
<script src="../js/viz.js"></script>
</body>
</html>"""


def generate_blog(snapshot: dict | None = None, silent: bool = False) -> str:
    if snapshot is None:
        snapshot = store.read_snapshot(store.list_periods()[-1])
    history = store.history_series("median_psqyd")
    os.makedirs(BLOG, exist_ok=True)
    html = _build_html(snapshot, history)
    out = os.path.join(BLOG, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    if not silent:
        print(f"[blog] wrote {out}")
    return out


if __name__ == "__main__":
    generate_blog()
