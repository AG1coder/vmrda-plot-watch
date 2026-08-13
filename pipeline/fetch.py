"""
Source adapters for pulling residential plot/land listings.

Each adapter conforms to::

    fetch() -> list[FlatListing]

where ``FlatListing`` is a dataclass with the fields shared by all sources
(see ``Listing``).  Adapters that cannot reach their source (blocked, paywall,
rate-limited, changed markup) should raise ``SourceUnavailable`` *gracefully*,
so the pipeline can skip them and continue with whatever sources succeeded.

Registry
--------
``build_sources()`` lists adapters in preference order.  The pipeline calls each
in turn and merges the results, tagging every listing with its source slug.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class SourceUnavailable(Exception):
    """Raised by an adapter when its source cannot be fetched this run."""


@dataclass
class Listing:
    """A single normalized plot/land listing from any source."""
    source: str            # adapter slug, e.g. "realestateindia"
    locality: str          # raw locality / building / area text from the site
    district_raw: str      # district as stated by the source (may be wrong)
    price_inr: float       # total asking price in INR
    area_sqyd: float       # total area normalized to sq. yards
    price_per_sqyd: float  # derived: price_inr / area_sqyd
    url: str = ""
    title: str = ""
    updated_at: str = ""   # ISO date the listing was last updated (freshness); "" = unknown


# --------------------------------------------------------------------------
# Parsing helpers shared by listing-page adapters
# --------------------------------------------------------------------------

_NUM_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def _parse_inr_price(text: str) -> float | None:
    """Parse an INR amount like '34 Lac', '1.30 Cr', '₹ 2.5 Lac' -> INR float."""
    t = (text or "").lower()
    m = _NUM_RE.search(t)
    if not m:
        return None
    val = float(m.group(0).replace(",", ""))
    if "cr" in t or "crore" in t:
        return val * 10_000_000
    if "lac" in t or "lakh" in t:
        return val * 100_000
    if "k" in t and re.fullmatch(r"[0-9.]+k", t.strip()):
        return val * 1_000
    return val * 1_000_000  # bare number on a real-estate site ~ a million


def _sqyd(area: float, unit: str) -> float:
    unit = (unit or "").lower()
    if "yard" in unit or "yd" in unit:
        return area
    if "acre" in unit or "acr" in unit:
        return area * 4840.0
    if "ft" in unit or "sft" in unit:
        return area / 9.0
    return area


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# --------------------------------------------------------------------------
# Real estate india  (live / working source)
# --------------------------------------------------------------------------

_DETAIL_ANCHOR = re.compile(
    r'<a[^>]*href="(?P<url>[^"]*property-detail/residential-plot-for-sale-in-[^"]*\.htm)"[^>]*>(?P<title>.*?)</a>',
    re.S)
_SLUG_AREA = re.compile(r"-(?P<area>\d+)-(?P<au>sq-?yards|sq-?yds|sq-?ft|sqyds?|acres?|acr)-")
_SLUG_PRICE = re.compile(r"-(?P<price>\d+(?:-\d+)?)-(?P<pu>lac|lakh|crore|cr)-[0-9]+\.htm$")
_PRICE_P = re.compile(r'r-pro-price[^>]*>\s*(.*?)\s*</p>', re.S)
# "Posted on : 01 Jul, 2026" freshness marker on realestateindia cards.
_POSTED_RE = re.compile(r'Posted\s*on\s*:\s*(\d{1,2})\s+([A-Za-z]{3}),?\s+(\d{4})')
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _parse_posted(context: str) -> str:
    """Return an ISO date (YYYY-MM-DD) found in a 'Posted on' marker, or ''."""
    import datetime as _dt
    m = _POSTED_RE.search(context or "")
    if not m:
        return ""
    mon = _MONTHS.get(m.group(2).lower())
    if not mon:
        return ""
    try:
        return _dt.date(int(m.group(3)), mon, int(m.group(1))).isoformat()
    except Exception:
        return ""


class RealEstateIndiaAdapter:
    slug = "realestateindia"
    base = "https://www.realestateindia.com"
    main_url = base + "/visakhapatnam-property/residential-land-for-sale.htm"
    # Extra district-root land pages we also crawl (broader VMRDA coverage).
    district_roots = {
        "vizianagaram": base + "/vizianagaram-property/residential-land-for-sale.htm",
        # Anakapalli listings are mostly tagged under Visakhapatnam on this site.
    }
    # Target-mandal locality page slugs we crawl for depth.
    locality_pages = {
        "bhogapuram": "vizianagaram-property/residential-land-for-sale-in-bhogapuram.htm",
        "vizianagaram": "vizianagaram-property/residential-land-for-sale-in-vizianagaram.htm",
        "kothavalasa": "vizianagaram-property/residential-land-for-sale-in-kothavalasa.htm",
        "anakapalle": "visakhapatnam-property/residential-land-for-sale-in-anakapalle.htm",
        "anandapuram": "visakhapatnam-property/residential-land-for-sale-in-anandapuram.htm",
        "madhurawada": "visakhapatnam-property/residential-land-for-sale-in-madhurawada.htm",
        "pendurthi": "visakhapatnam-property/residential-land-for-sale-in-pendurthi.htm",
        "bheemunipatnam": "visakhapatnam-property/residential-land-for-sale-in-bheemunipatnam.htm",
        "sabbavaram": "visakhapatnam-property/residential-land-for-sale-in-sabbavaram.htm",
        "gajuwaka": "visakhapatnam-property/residential-land-for-sale-in-gajuwaka.htm",
    }

    def __init__(self, session=None, max_pages: int = 4, delay: float = 0.35):
        self.session = session or (requests.Session() if requests else None)
        self.max_pages = max_pages
        self.delay = delay
        self.headers = {"User-Agent": USER_AGENT}
        self._seen: set = set()
        self._out: list[Listing] = []

    def _get(self, url: str) -> str:
        if self.session is None:
            raise SourceUnavailable("requests not installed")
        r = self.session.get(url, headers=self.headers, timeout=30)
        if r.status_code != 200:
            raise SourceUnavailable(f"HTTP {r.status_code} for {url}")
        if len(r.text) < 3000 or "Access Denied" in r.text[:600]:
            raise SourceUnavailable(f"blocked / empty page for {url}")
        return r.text

    # -- slug fallback: price/area encoded directly in the listing URL ------
    @staticmethod
    def _from_slug(url: str):
        tail = url.split("/")[-1]
        pm = _SLUG_PRICE.search(tail)
        am = _SLUG_AREA.search(tail)
        price_inr = area_sqyd = None
        if pm:
            price = float(pm.group("price").replace("-", "."))
            price_inr = _parse_inr_price(f"{price} {'Cr' if pm.group('pu')[0]=='c' else 'Lac'}")
        if am:
            area_sqyd = _sqyd(float(am.group("area")), am.group("au"))
        return price_inr, area_sqyd

    def _ingest_anchor(self, url: str, title_html: str, extra_html: str,
                       context: str = "") -> Listing | None:
        url = url if url.startswith("http") else self.base + url
        if url in self._seen:
            return None
        title = _strip_tags(title_html)
        # locality + district from title
        locality, district_raw = "", ""
        lm = re.search(r"for Sale in\s+(.+?)\s*$", title, re.I)
        if lm:
            parts = [p.strip() for p in lm.group(1).split(",")]
            locality = parts[0]
            district_raw = parts[-1] if len(parts) > 1 else ""

        price, area = self._from_slug(url)
        if price is None:
            pm = _PRICE_P.search(extra_html)
            if pm:
                price = _parse_inr_price(pm.group(1))
        if area is None:
            am = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(sq\.?\s*(?:yards|yds|ft|feet)|sqyds?|sft|acres?|acr)",
                           title, re.I)
            if am:
                area = _sqyd(float(am.group(1)), am.group(2))
        if price is None or area is None or area <= 0:
            return None
        self._seen.add(url)
        lst = Listing(
            source=self.slug,
            locality=locality,
            district_raw=district_raw,
            price_inr=price,
            area_sqyd=area,
            price_per_sqyd=price / area,
            url=url,
            title=title,
            updated_at=_parse_posted(context),
        )
        self._out.append(lst)
        return lst

    def _crawl(self, url: str) -> int:
        """Parse one listing page, ingesting every plot-detail anchor."""
        try:
            html = self._get(url)
        except SourceUnavailable as e:
            print(f"    [realestateindia] skip {url.split('/')[-1]}: {e}")
            return 0
        before = len(self._seen)
        for m in _DETAIL_ANCHOR.finditer(html):
            self._ingest_anchor(m.group("url"), m.group("title"),
                                html[m.end():m.end() + 500],
                                html[max(0, m.start() - 700):])
        return len(self._seen) - before

    def fetch(self) -> list[Listing]:
        if requests is None:
            raise SourceUnavailable("requests not installed")
        self._seen = set()
        self._out = []
        # 1) main Vizag land page, paginated
        for page in range(1, self.max_pages + 1):
            url = self.main_url if page == 1 else \
                self.main_url.replace(".htm", f"-page-{page}.htm")
            self._crawl(url)
            time.sleep(self.delay)
        # 2) extra district roots
        for slug, url in self.district_roots.items():
            self._crawl(url)
            time.sleep(self.delay)
        # 3) per-mandal locality pages for depth
        for slug, path in self.locality_pages.items():
            self._crawl(self.base + "/" + path)
            time.sleep(self.delay)
        print(f"    [realestateindia] collected {len(self._out)} unique listings")
        return self._out


# --------------------------------------------------------------------------
# 1acre.in  (live / working source)
# --------------------------------------------------------------------------
#
# 1acre.in verified lands/plots are served on "map-layers" pages.  The listing
# grid lives in a Next.js flight payload embedded as a double-escaped JSON
# string; the public page carries `initialListingsFirstPage` (JSON API response
# without pagination on the public side).  We fetch the page, unescape the
# embedded JSON, and parse the listing objects.
#
# Listing types:
#   - plot: total_plot_size (sq yd), total_price (₹ absolute),
#           price_per_square_yard (₹/sq yd)
#   - land: total_land_size (acres), price_per_acre (₹ lakhs/acre),
#           total_price (₹ lakhs)
# Locality/district are encoded in the listing slug and in
# payload.seller.seller_location (e.g. district.name).

class OneAcreAdapter:
    slug = "1acre"
    base = "https://1acre.in/map-layers/andhra-pradesh"
    # VMRDA-relevant layer pages (each embeds up to ~32 listings, no public page
    # pagination).  Add more layer slugs here to broaden coverage.
    layer_pages = [
        "lands-in-visakhapatnam-master-plan",
        "lands-near-vizag-airport-road",
        "lands-near-vizag-beach-road-corridor",
    ]

    def __init__(self, session=None, max_pages: int = 4, delay: float = 0.5):
        self.session = session or (requests.Session() if requests else None)
        self.max_pages = max_pages
        self.delay = delay
        self.headers = {"User-Agent": USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
        self._out: list[Listing] = []
        self._seen: set = set()

    def _get(self, url: str) -> str:
        if self.session is None:
            raise SourceUnavailable("requests not installed")
        r = self.session.get(url, headers=self.headers, timeout=35)
        if r.status_code != 200:
            raise SourceUnavailable(f"HTTP {r.status_code} for {url}")
        if len(r.text) < 10000 or "initialListingsFirstPage" not in r.text:
            raise SourceUnavailable(f"no listing payload for {url}")
        return r.text

    # -- embedded JSON helpers -------------------------------------------
    @staticmethod
    def _unescape(html: str) -> str:
        # The flight data JSON string is double-escaped: \" -> " and \\u0026 -> &
        out = html.replace('\\"', '"')
        out = out.replace("\\u0026", "&")
        out = out.replace("\\/", "/")
        return out

    @staticmethod
    def _balanced_json(s: str, start: int):
        stack, i, in_str = [], start, False
        while i < len(s):
            c = s[i]
            if in_str:
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c in "{[":
                    stack.append(c)
                elif c in "}]":
                    stack.pop()
                    if not stack:
                        return s[start:i + 1]
            i += 1
        return None

    def _first_page(self, html: str) -> dict | None:
        import json as _json
        s = self._unescape(html)
        key = '"initialListingsFirstPage":{'
        m = s.find(key)
        if m < 0:
            return None
        obj = self._balanced_json(s, m + len('"initialListingsFirstPage":'))
        if not obj:
            return None
        try:
            return _json.loads(obj)
        except Exception:
            return None

    # -- parse --------------------------------------------------------------
    def _ingest(self, info: dict) -> None:
        lst = info.get("listing") or {}
        slug = lst.get("slug", "") or ""
        if not slug or slug in self._seen:
            return
        locality = slug.replace("-", " ").strip()
        district = (info and info.get("district")) or ""
        # try to pull district from payload seller_location
        payload = lst.get("payload") or {}
        try:
            sl = payload.get("seller", {}).get("seller_location", {})
            district = sl.get("district", {}).get("name", district)
        except Exception:
            pass

        price = area = None
        updated_at = lst.get("updated_at", "") or ""
        if lst.get("total_plot_size") is not None:          # plot, sq yards
            area = float(lst["total_plot_size"])
            price = float(lst["total_price"])                # ₹ absolute
        else:
            # Land type (total_land_size in acres) -> skip: we only surface
            # plots, not big parcels, in this view.
            return
        if price is None or area is None or area <= 0 or price <= 0:
            return
        url = slug
        self._seen.add(slug)
        self._out.append(Listing(
            source=self.slug,
            locality=locality,
            district_raw=district,
            price_inr=price,
            area_sqyd=area,
            price_per_sqyd=price / area,
            url=f"https://1acre.in/lands-for-sale/{url}",
            title=slug.replace("-", " "),
            updated_at=updated_at[:10] if updated_at else "",
        ))

    def fetch(self) -> list[Listing]:
        if requests is None:
            raise SourceUnavailable("requests not installed")
        self._out, self._seen = [], set()
        for slug in self.layer_pages:
            url = f"{self.base}/{slug}"
            try:
                html = self._get(url)
            except SourceUnavailable as e:
                print(f"    [1acre] skip {slug}: {e}")
                continue
            fp = self._first_page(html)
            if not fp:
                print(f"    [1acre] no listings parsed from {slug}")
                continue
            for info in fp.get("results", []):
                self._ingest(info)
            print(f"    [1acre] {slug}: {len(fp.get('results', []))} listings on page")
            if self.delay:
                time.sleep(self.delay)
        print(f"    [1acre] collected {len(self._out)} unique listings")
        return self._out


# --------------------------------------------------------------------------
# Adapter registry
# --------------------------------------------------------------------------

def build_sources():
    return {
        "realestateindia": RealEstateIndiaAdapter,
        "1acre": OneAcreAdapter,
        # The major portals aggressively block datacenter/headless traffic in
        # this environment.  Adapters are declared here so the pipeline has a
        # stable seam to add them when run through a residential proxy or an
        # on-location network.  Add a class with `slug`, `fetch()` and register
        # it below to include another source.
        # "housing": HousingAdapter,
        # "magicbricks": MagicBricksAdapter,
        # "99acres": NineteenAcresAdapter,
        # "squareyards": SquareYardsAdapter,
    }


def fetch_all(max_pages: int = 4) -> tuple[list[Listing], dict]:
    """Fetch from every available source; return (merged listings, per-source counts)."""
    merged: list[Listing] = []
    counts: dict = {}
    sources = build_sources()
    for slug, cls in sources.items():
        try:
            adapter = cls(max_pages=max_pages)
            lst = adapter.fetch()
        except SourceUnavailable as e:
            print(f"    [{slug}] unavailable: {e}")
            counts[slug] = 0
            continue
        merged.extend(lst)
        counts[slug] = len(lst)
    return merged, counts
