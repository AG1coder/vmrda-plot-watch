# VMRDA Plot Watch

A monthly, automated snapshot of residential **plot / land asking prices** across the
VMRDA belt — **Visakhapatnam, Anakapalli and Vizianagaram districts** of Andhra Pradesh —
rendered as an NYTimes-style interactive article and a data-backed blog post.

Every month the pipeline:
1. **Fetches** live plot/land listings from real-estate aggregators.
2. **Tiles** them onto the 16 target mandals (GVMC core, Bheemunipatnam, Anandapuram,
   Pendurthi, Sabbavaram, Devarapalli · Anakapalle, Atchutapuram, Kasimkota, Nakkapalli,
   Elamanchili, Parawada · Vizianagaram, Bhogapuram, Gajapathinagaram, Denkada).
3. **Samples** up to 20 listings per mandal, **normalizes** every price to ₹/sq yd, and
   **filters** clearly-erroneous entries.
4. **Computes** range + average + median + 10th/90th-percentile metrics per mandal,
   plus district and region roll-ups.
5. **Persists** the monthly snapshot to `data/history/`.
6. **Regenerates** the visualization (`site/index.html`) and the blog (`site/blog/index.html`).

## Quick start

```bash
pip install -r requirements.txt

# Full run: fetch + sample + stats + persist + render site + blog
python -m pipeline.run --render

# Inspect without persisting
python -m pipeline.run --dry-run

# Regenerate site/blog from the latest snapshot only (no re-fetch)
python render_site.py
python generate_blog.py

# Or use the runner script
bash scripts/run_monthly.sh
```

## Output

| Path | What it is |
|------|-----------|
| `site/index.html` | NYTimes-style interactive article: a **price map** of the VMRDA belt (geographic bubbles), a ranked **range + median + average** dumbbell chart, a **"what a budget buys you"** affordability chart, a per-listing jitter plot, and a monthly trend line. A clickable **mandal selector** cross-highlights the map, rankings and trend, with a comparison detail panel. |
| `site/blog/index.html` | Long-form editorial blog regenerated from the latest numbers, embedding the same interactive charts. |
| `data/latest.json` | Most recent snapshot |
| `data/history/YYYY-MM.json` | Append-only monthly archive |

Open `site/index.html` directly in a browser (only D3 is loaded from CDN; all data is
embedded in the page, so it works from `file://`).

## Scheduling

The pipeline is wired to run **once a month** as a Hermes cron job (1st of each month).
The job runs `scripts/run_monthly.sh` from the repo and reports the finished snapshot.
You can re-run manually with:

```bash
bash scripts/run_monthly.sh
```

## Architecture

```
pipeline/
  config.py     target districts/mandals + locality→mandal keyword map + tuning
  fetch.py      source adapters (Listing schema, SourceUnavailable, registry)
  sampling.py   tile raw listings to mandals, quality-filter, sample N
  stats.py      per-mandal + district/region metrics
  store.py      monthly snapshot persistence + history series
  run.py        orchestrator (fetch → sample → stats → persist → render)
render_site.py    builds the article page
generate_blog.py  builds the blog page
scripts/run_monthly.sh
```

### Sources & the adapter seam

`fetch.build_sources()` registers adapters. Two are **live**: **realestateindia**
(listing feeds, slugs encode locality + area + price) and **1acre.in** (verified
lands/plots parsed from the VMRDA map-layer pages — master-plan, airport-road and
beach-corridor). The major portals — **Housing, 99acres, MagicBricks, SquareYards** —
block datacenter/headless traffic from this environment, so their adapters are declared
as commented placeholders. To add one, implement a class with `slug` and
`fetch() -> list[Listing]` and register it; the pipeline merges results from every
adapter that succeeds and skips those that raise `SourceUnavailable` gracefully.

### Methodology & caveats

- Prices are **asking** prices, not transactions.
- Mandals with < 3 usable listings are omitted from the charts (n is shown in the table).
- Outliers outside ₹800–₹100,000/sq yd are treated as scrape artifacts and excluded.
- These are directional monthly snapshots, not valuations.

## Monitoring the pipeline

Because the monthly run runs unattended, `run.py` prints concise status lines (raw fetched,
dropped, per-mandal sample sizes, region stats) and the cron job relays the final summary
back here. Check `data/history/index.json` for the list of completed months.
