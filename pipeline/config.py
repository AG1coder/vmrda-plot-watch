"""
vmrda-plot-watch configuration.

Defines the VMRDA region's target districts and mandals, plus the keywords used
to map a raw real-estate listing's locality text onto a canonical mandal.

VMRDA (Visakhapatnam Metropolitan Region Development Authority) covers areas in
three districts of Andhra Pradesh:
  - Visakhapatnam district (the urban core + northern/eastern mandals)
  - Anakapalli district  (industrial corridor / NH-16 south-west)
  - Vizianagaram district (north, incl. Bhogapuram -- new int'l airport site)
"""
from __future__ import annotations

# How many listings to sample per mandal to build the price distribution.
SAMPLE_SIZE = 20

# Outlier-sanity window for asking price per sq. yard (₹).  Realistic open-plot
# prices across VMRDA run from cheap fringe farmland (~₹800/sq.yd) to prime
# GVMC/main-road frontage (~₹1,00,000/sq.yd).  Values outside this window are
# almost always scraping/parse artifacts (inconsistent URL slugs, tiny parcels,
# wrong unit conversion) rather than genuine market listings, so they are
# excluded from a mandal's sample.
MIN_PSQYD = 800
MAX_PSQYD = 100_000

# Plots only: exclude large land parcels (farmland / multi-acre plots) from the
# sample.  A "plot" is a residential building plot, well under ~1 acre.  Bigger
# parcels trade on a different per-area curve (₹/acre) that skews the ₹/sq.yd
# view, so anything above this many square yards is treated as a big parcel and
# dropped.  1 acre = 4840 sq yd.
MAX_PLOT_AREA_SQYD = 4840

# Freshness window: a listing counts as "fresh" if it was last updated within
# this many days of the snapshot date.
FRESHNESS_DAYS = 90

# One canonical snapshot per month is stored in data/history/.
SNAPSHOT_FORMAT = "%Y-%m"

DISTRICTS = [
    {
        "key": "visakhapatnam",
        "label": "Visakhapatnam district",
    },
    {
        "key": "anakapalli",
        "label": "Anakapalli district",
    },
    {
        "key": "vizianagaram",
        "label": "Vizianagaram district",
    },
]

# Mandals of interest.  `keywords` are substrings matched (case-insensitive)
# against the listing locality / title to assign a listing to this mandal.
# `variant` keywords catch alternate spellings/aliases.
MANDALS = [
    # ---- Visakhapatnam district -------------------------------------------
    {"key": "visakhapatnam-urban", "district": "visakhapatnam",
     "label": "Visakhapatnam city (GVMC)",
     "keywords": ["visakhapatnam", "vizag", "mvp", "madhurawada", "dondaparthy",
                  "gajuwaka", "kurmannapalem", "gandigundam", "muralinagar",
                  "seethammadhara", "dwarakanagar", "asilmetta", "lawsombagh",
                  "ram nagar", "akkyayyapalem", "akkayyapalem", "kancharapalem"]},
    {"key": "bheemunipatnam", "district": "visakhapatnam",
     "label": "Bheemunipatnam",
     "keywords": ["bheemunipatnam", "bheemili", "bhogapuram-sagar", "sagar nagar"]},
    {"key": "anandapuram", "district": "visakhapatnam",
     "label": "Anandapuram",
     "keywords": ["anandapuram", "anandhapuram", "anandapuram"]},
    {"key": "pendurthi", "district": "visakhapatnam",
     "label": "Pendurthi",
     "keywords": ["pendurthi", "adarsh nagar", "akbayyapalem"]},
    {"key": "sabbavaram", "district": "visakhapatnam",
     "label": "Sabbavaram",
     "keywords": ["sabbavaram", "sabavaram"]},
    {"key": "devarapalli", "district": "visakhapatnam",
     "label": "Devarapalli",
     "keywords": ["devarapalli"]},

    # ---- Anakapalli district ----------------------------------------------
    {"key": "anakapalle", "district": "anakapalli",
     "label": "Anakapalle",
     "keywords": ["anakapalle", "anakapalli", "anakapalle"]},
    {"key": "atchutapuram", "district": "anakapalli",
     "label": "Achyutapuram (Atchutapuram)",
     "keywords": ["atchutapuram", "achutapuram", "atachutapuram"]},
    {"key": "kasimkota", "district": "anakapalli",
     "label": "Kasimkota",
     "keywords": ["kasimkota"]},
    {"key": "nakkapalli", "district": "anakapalli",
     "label": "Nakkapalli",
     "keywords": ["nakkapalli"]},
    {"key": "elamanchili", "district": "anakapalli",
     "label": "Elamanchili",
     "keywords": ["elamanchili", "yelamanchili", "elamanchili"]},
    {"key": "parawada", "district": "anakapalli",
     "label": "Parawada",
     "keywords": ["parawada", "parwada"]},

    # ---- Vizianagaram district --------------------------------------------
    {"key": "vizianagaram", "district": "vizianagaram",
     "label": "Vizianagaram city",
     "keywords": ["vizianagaram", "vzm", "alakananda", "kothavalasa",
                  "vijayanagaram", "vijay nagar"]},
    {"key": "bhogapuram", "district": "vizianagaram",
     "label": "Bhogapuram (airport)",
     "keywords": ["bhogapuram"]},
    {"key": "gajapathinagaram", "district": "vizianagaram",
     "label": "Gajapathinagaram",
     "keywords": ["gajapathinagaram", "gajapathinagaram"]},
    {"key": "denkada", "district": "vizianagaram",
     "label": "Denkada",
     "keywords": ["denkada"]},
]

MANDAL_BY_KEY = {m["key"]: m for m in MANDALS}

# Accurate town-centre coordinates (lat, lng) geocoded from OpenStreetMap
# (Nominatim).  Static reference data -- not scraped.
COORDS = {
    "visakhapatnam-urban": (17.69355, 83.29213),
    "bheemunipatnam":      (17.89139, 83.45087),
    "anandapuram":         (17.90389, 83.37050),
    "pendurthi":           (17.82136, 83.20658),
    "sabbavaram":          (17.79469, 83.09671),
    "devarapalli":         (17.72300, 82.81500),
    "anakapalle":          (17.68897, 83.00348),
    "atchutapuram":        (17.56135, 83.00334),
    "kasimkota":           (17.66645, 82.96535),
    "nakkapalli":          (17.41063, 82.71626),
    "elamanchili":         (17.55239, 82.85220),
    "parawada":            (17.62973, 83.08979),
    "vizianagaram":        (18.11413, 83.41144),
    "bhogapuram":          (17.99487, 83.50314),
    "gajapathinagaram":    (18.29919, 83.34888),
    "denkada":             (18.04436, 83.44468),
}

# Approximate Bay-of-Bengal coastline for the VMRDA fringe, used to tint the
# sea on the map ([lng, lat] pairs, lat 17.2 -> 18.5).
COASTLINE = [
    [82.60, 17.28], [82.72, 17.38], [82.82, 17.52], [82.90, 17.62],
    [82.99, 17.70], [83.10, 17.75], [83.16, 17.83], [83.22, 17.90],
    [83.30, 17.97], [83.38, 18.02], [83.46, 18.10], [83.52, 18.20],
    [83.55, 18.32], [83.58, 18.45],
]


def coords_for(key: str) -> tuple[float, float] | None:
    return COORDS.get(key)


def mandal_for_locality(locality: str) -> dict | None:
    """Return the mandal whose keyword matches *locality*, or None."""
    text = (locality or "").lower()
    if not text:
        return None
    for m in MANDALS:
        for kw in m["keywords"]:
            if kw.lower() in text:
                return m
    return None


def districts_in_order() -> list[str]:
    return [d["key"] for d in DISTRICTS]
