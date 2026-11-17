"""Shared paths, constants and the indicator catalogue used by every script."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"              # cached API answers, never published (see .gitignore)
PROCESSED = ROOT / "data" / "processed"  # tidy tables built from the raw answers (published)
OUT = ROOT / "data" / "outputs"          # analysis results (published)
FACTS = ROOT / "factsheets"
CAL = ROOT / "calendar"
COMM = ROOT / "commentary"
DOCS = ROOT / "docs"
DASH = ROOT / "dashboard"

for _p in (RAW, PROCESSED, OUT, FACTS, CAL, COMM, DOCS, DASH):
    _p.mkdir(parents=True, exist_ok=True)

# Neutral client name: no personal contact in any request.
USER_AGENT = "us-releases-case-study/1.0 (research script)"

# Optional free keys, read from .env only (never committed).
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
BLS_API_KEY = os.getenv("BLS_API_KEY", "")

COLLECTED_ON = "17 November 2026"
CAL_START, CAL_END = "2026-10-01", "2026-11-30"   # the rebuilt two-month calendar
EVENT_START = "2016-01-01"                         # event study: reference months from here

FOOTER = "Independent case study based on public data · not affiliated with or endorsed by Trading Economics"

# ---------------------------------------------------------------------------------------------------------------
# Calendar events. One row = one line of the economic calendar.
#   series     FRED/ALFRED id (ALFRED keeps every past vintage, so we know what was published on which day)
#   kind       how the headline number is computed from the series, inside one vintage:
#              mom = % change on previous period, yoy = % change on 12 months earlier,
#              diff = change in level, level = the value itself
#   scale      the series value is divided by this before display (e.g. claims in people -> thousands)
#   unit       displayed unit; dec = decimals as published
#   model      'avg3' = mean of the last three prints known before release; 'last' = previous value (no change)
# ---------------------------------------------------------------------------------------------------------------
EVENTS = [
    # key            event name                              series             kind    scale  unit  dec time    source    imp     model
    ("cpi_mom",      "CPI MoM",                               "CPIAUCSL",        "mom",  1,     "%",  1, "08:30", "BLS",     "high", "avg3"),
    ("cpi_yoy",      "CPI YoY",                               "CPIAUCNS",        "yoy",  1,     "%",  1, "08:30", "BLS",     "high", "last"),
    ("core_cpi_mom", "Core CPI MoM",                          "CPILFESL",        "mom",  1,     "%",  1, "08:30", "BLS",     "high", "avg3"),
    ("core_cpi_yoy", "Core CPI YoY",                          "CPILFENS",        "yoy",  1,     "%",  1, "08:30", "BLS",     "high", "last"),
    ("nfp",          "Non-farm payrolls",                     "PAYEMS",          "diff", 1,     "K",  0, "08:30", "BLS",     "high", "avg3"),
    ("unrate",       "Unemployment rate",                     "UNRATE",          "level", 1,    "%",  1, "08:30", "BLS",     "high", "last"),
    ("ahe_mom",      "Average hourly earnings MoM",           "CES0500000003",   "mom",  1,     "%",  1, "08:30", "BLS",     "medium", "avg3"),
    ("ppi_mom",      "PPI final demand MoM",                  "PPIFIS",          "mom",  1,     "%",  1, "08:30", "BLS",     "medium", "avg3"),
    ("jolts",        "JOLTS job openings",                    "JTSJOL",          "level", 1000, "M",  2, "10:00", "BLS",     "medium", "last"),
    ("claims",       "Initial jobless claims",                "ICSA",            "level", 1000, "K",  0, "08:30", "DOL",     "medium", "avg3"),
    ("retail_mom",   "Retail sales MoM",                      "RSAFS",           "mom",  1,     "%",  1, "08:30", "Census",  "high", "avg3"),
    ("retail_xauto", "Retail sales ex autos MoM",             "RSFSXMV",         "mom",  1,     "%",  1, "08:30", "Census",  "medium", "avg3"),
    ("starts",       "Housing starts",                        "HOUST",           "level", 1000, "M",  3, "08:30", "Census",  "medium", "last"),
    ("durables",     "Durable goods orders MoM",              "DGORDER",         "mom",  1,     "%",  1, "08:30", "Census",  "medium", "avg3"),
    ("new_homes",    "New home sales",                        "HSN1F",           "level", 1000, "M",  3, "10:00", "Census",  "medium", "last"),
    ("trade",        "Trade balance",                         "BOPGSTB",         "level", 1000, "USD B", 1, "08:30", "BEA",   "medium", "last"),
    ("gdp",          "GDP growth rate QoQ annualized",        "A191RL1Q225SBEA", "level", 1,    "%",  1, "08:30", "BEA",     "high", "last"),
    ("pce_yoy",      "PCE price index YoY",                   "PCEPI",           "yoy",  1,     "%",  1, "08:30", "BEA",     "high", "last"),
    ("core_pce_mom", "Core PCE price index MoM",              "PCEPILFE",        "mom",  1,     "%",  1, "08:30", "BEA",     "high", "avg3"),
    ("core_pce_yoy", "Core PCE price index YoY",              "PCEPILFE",        "yoy",  1,     "%",  1, "08:30", "BEA",     "high", "last"),
    ("spending_mom", "Personal spending MoM",                 "PCE",             "mom",  1,     "%",  1, "08:30", "BEA",     "medium", "avg3"),
    ("indpro_mom",   "Industrial production MoM",             "INDPRO",          "mom",  1,     "%",  1, "09:15", "Fed",     "medium", "avg3"),
]
EVENT_COLS = ["key", "event", "series", "kind", "scale", "unit", "dec", "time", "source", "importance", "model"]

# BLS API series (latest values and components for the fact sheets).
BLS_SERIES = {
    "CUSR0000SA0": "CPI all items, SA",
    "CUUR0000SA0": "CPI all items, NSA",
    "CUSR0000SA0L1E": "CPI less food and energy, SA",
    "CUUR0000SA0L1E": "CPI less food and energy, NSA",
    "CUSR0000SA0E": "CPI energy, SA",
    "CUSR0000SAF1": "CPI food, SA",
    "CUSR0000SAH1": "CPI shelter, SA",
    "CUSR0000SASLE": "CPI services less energy services, SA",
    "CUSR0000SACL1E": "CPI core goods (commodities less food and energy), SA",
    "CES0000000001": "Total non-farm payrolls, thousands, SA",
    "LNS14000000": "Unemployment rate, %, SA",
    "CES0500000003": "Average hourly earnings, private, USD, SA",
    "LNS11300000": "Labour force participation rate, %, SA",
    "CES0500000002": "Average weekly hours, private, SA",
    "WPSFD4": "PPI final demand, SA",
}

# Daily market series from FRED (public copies of Treasury, Fed H.10, EIA and S&P data).
MARKETS = {
    "DGS2": "2-year Treasury yield (%)",
    "DGS10": "10-year Treasury yield (%)",
    "DTWEXBGS": "Broad US dollar index (Fed, Jan 2006 = 100)",
    "DEXUSEU": "USD per EUR",
    "DCOILWTICO": "WTI crude oil (USD/bbl)",
    "SP500": "S&P 500 index (FRED serves the last 12 months only)",
    "NASDAQCOM": "Nasdaq Composite index (full history; used for stocks in the event study)",
    "DFEDTARU": "Fed funds target range, upper bound (%)",
    "DFEDTARL": "Fed funds target range, lower bound (%)",
}

# Extra monthly series used in the fact sheets and trends (current vintage only).
EXTRA_MONTHLY = ["CPIAUCSL", "CPILFESL", "CPIAUCNS", "CPILFENS", "PAYEMS", "UNRATE", "CES0500000003", "RSAFS", "RSFSXMV",
                 "PCEPI", "PCEPILFE", "PCE", "A191RL1Q225SBEA", "ICSA", "JTSJOL", "PPIFIS", "INDPRO", "HOUST", "DGORDER",
                 "HSN1F", "BOPGSTB", "RSNSR", "RSXFS", "PI"]


def ai_note() -> str:
    """The AI-use statement is written once, in the README (Methods); the PDF quotes it from there."""
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    out = [ln.split("**: ", 1)[1].strip() for ln in lines if ln.startswith("- **AI-assisted workflow**")]
    if not out:
        raise ValueError("AI note not found in README.md")
    return out[0]
