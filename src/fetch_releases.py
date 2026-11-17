"""Download every public input once, at low frequency, and save tidy tables in data/processed.

Sources (all official or official copies, no scraping of Trading Economics):
  - BLS Public Data API (CPI, payrolls, unemployment, earnings, PPI)  -> bls_series.csv
  - FRED CSV (current values; daily market series)                    -> fred_monthly.csv, markets_daily.csv
  - ALFRED CSV (FRED's archive of past vintages): what was published on which day, first prints, revisions
        * recent window for the rebuilt calendar                        -> vintages_recent.csv
        * CPI and payrolls since 2016 for the event study               -> event_vintages.csv
  - U.S. Treasury daily par yield curve (cross-check of FRED yields)  -> treasury_par_yields.csv
  - Federal Reserve FOMC calendar                                     -> fomc_meetings.csv
  - BEA and Census official release schedules                         -> schedule_official.csv

Answers are cached in data/raw, so a second run makes no network call. Usage: python src/fetch_releases.py
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (BLS_API_KEY, BLS_SERIES, EVENT_START, EVENTS, EXTRA_MONTHLY, MARKETS, PROCESSED, RAW,  # noqa: E402
                    USER_AGENT)

S = requests.Session()
S.headers["User-Agent"] = USER_AGENT
TODAY = date(2026, 11, 17)           # collection date, fixed so that reruns rebuild the same tables
PAUSE = 0.6                          # seconds between two network calls (polite, low frequency)
ALFRED = "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
MAX_COLS = 12                        # ALFRED returns at most 12 columns per graph


def cached(url: str, params: dict | None = None, method="GET", body: dict | None = None) -> str:
    key = hashlib.sha1(json.dumps([url, params, body], sort_keys=True).encode()).hexdigest()[:20]
    path = RAW / "http" / f"{key}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    for attempt in range(4):
        try:
            r = S.post(url, json=body, timeout=60) if method == "POST" else S.get(url, params=params, timeout=60)
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    time.sleep(PAUSE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(r.text, encoding="utf-8")
    return r.text


def weekdays(start: date, end: date) -> list[date]:
    return [start + timedelta(i) for i in range((end - start).days + 1) if (start + timedelta(i)).weekday() < 5]


# ------------------------------------------------------------------------------------------------ BLS
def fetch_bls() -> None:
    ids, rows = list(BLS_SERIES), []
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/" if BLS_API_KEY else "https://api.bls.gov/publicAPI/v1/timeseries/data/"
    for y0, y1 in ((2015, 2016), (2017, 2026)):          # v1 serves at most 10 years per query
        body = {"seriesid": ids, "startyear": str(y0), "endyear": str(y1)}
        if BLS_API_KEY:
            body["registrationkey"] = BLS_API_KEY
        js = json.loads(cached(url, method="POST", body=body))
        if js.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS API: {js.get('message')}")
        for s in js["Results"]["series"]:
            for d in s["data"]:
                if d["period"].startswith("M") and d["period"] != "M13" and d["value"] not in ("-", ""):
                    rows.append((s["seriesID"], f"{d['year']}-{d['period'][1:]}-01", float(d["value"])))
    df = pd.DataFrame(rows, columns=["series_id", "date", "value"]).sort_values(["series_id", "date"])
    df["label"] = df.series_id.map(BLS_SERIES)
    df.to_csv(PROCESSED / "bls_series.csv", index=False)
    print(f"BLS API          {df.series_id.nunique()} series, {len(df):,} rows, last month {df.date.max()}")


# ------------------------------------------------------------------------------------------------ FRED (current)
def fred_csv(series: str, start="2015-01-01") -> pd.DataFrame:
    txt = cached("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": series, "cosd": start, "coed": str(TODAY)})
    df = pd.read_csv(io.StringIO(txt))
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df.value, errors="coerce")
    return df


def fetch_fred() -> None:
    m = pd.concat([fred_csv(s).assign(series=s) for s in EXTRA_MONTHLY])
    m.dropna(subset=["value"]).to_csv(PROCESSED / "fred_monthly.csv", index=False)
    d = None
    for s in MARKETS:
        x = fred_csv(s).rename(columns={"value": s}).set_index("date")
        d = x if d is None else d.join(x, how="outer")
    d.sort_index().to_csv(PROCESSED / "markets_daily.csv")
    print(f"FRED             {len(EXTRA_MONTHLY)} macro series, {len(MARKETS)} daily market series to {d.index.max()}")


def fetch_treasury() -> None:
    frames = []
    for y in (2025, 2026):
        url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all"
        txt = cached(url, {"type": "daily_treasury_yield_curve", "field_tdr_date_value": str(y), "page": "", "_format": "csv"})
        frames.append(pd.read_csv(io.StringIO(txt))[["Date", "2 Yr", "10 Yr"]])
    t = pd.concat(frames)
    t["Date"] = pd.to_datetime(t.Date, format="%m/%d/%Y").dt.date
    t.rename(columns={"Date": "date", "2 Yr": "tsy_2y", "10 Yr": "tsy_10y"}).sort_values("date").to_csv(
        PROCESSED / "treasury_par_yields.csv", index=False)
    print(f"Treasury         {len(t)} days of par yields")


# ------------------------------------------------------------------------------------------------ ALFRED (vintages)
def alfred(cols: list[tuple[str, date]], cosd: date, coed: date) -> pd.DataFrame:
    """Values of each (series, vintage date) pair, long format. A vintage date returns the data as it stood that day."""
    out = []
    for i in range(0, len(cols), MAX_COLS):
        chunk = cols[i:i + MAX_COLS]
        txt = cached(ALFRED, {"id": ",".join(s for s, _ in chunk), "vintage_date": ",".join(str(v) for _, v in chunk),
                              "cosd": str(cosd), "coed": str(coed)})
        df = pd.read_csv(io.StringIO(txt))
        df = df[pd.to_datetime(df.observation_date) >= pd.Timestamp(cosd)]   # rows before cosd come back blank
        for c in df.columns[1:]:
            s, v = c.rsplit("_", 1)
            vals = pd.to_numeric(df[c], errors="coerce")
            out.append(pd.DataFrame({"series": s, "vintage": pd.to_datetime(v).date(), "date": df.observation_date, "value": vals}))
    return pd.concat(out).dropna(subset=["value"])


def scan_recent() -> None:
    """Every weekday vintage from just before the calendar window: shows each release, first print and revision."""
    days = weekdays(date(2026, 8, 31), TODAY)
    frames = []
    for s in sorted({e[2] for e in EVENTS}):
        start = date(2023, 1, 1) if s in ("A191RL1Q225SBEA",) else date(2024, 6, 1)
        step = MAX_COLS - 1
        for i in range(0, len(days), step):
            v = alfred([(s, d) for d in days[i:i + MAX_COLS]], start, TODAY)
            frames.append(v)
    v = pd.concat(frames).drop_duplicates()
    # keep only vintages that differ from the previous weekday (a new release or a revision)
    keep = []
    for s, g in v.groupby("series"):
        prev = None
        for vin, gg in g.groupby("vintage"):
            cur = gg.set_index("date").value
            if prev is None or not cur.equals(prev):
                keep.append(gg)
            prev = cur
    out = pd.concat(keep).sort_values(["series", "vintage", "date"])
    out.to_csv(PROCESSED / "vintages_recent.csv", index=False)
    print(f"ALFRED recent    {out.series.nunique()} series, {out.groupby('series').vintage.nunique().sum()} distinct vintages")


def month_add(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def first_release(series: str, ref: date, start: date) -> date | None:
    """First weekday on which observation `ref` of `series` exists in ALFRED (= its release date)."""
    base = start
    for _ in range(10):                                  # up to ~5 months of delay (e.g. shutdowns)
        days = [base] + weekdays(base + timedelta(1), base + timedelta(30))[:MAX_COLS - 1]
        v = alfred([(series, d) for d in days], month_add(ref, -1), ref)
        has = v[v.date == str(ref)].vintage.unique()
        if len(has):
            first = min(has)
            if first == days[0]:                          # already published before the window: look earlier
                base = base - timedelta(21)
                continue
            return first
        base = days[-1]
    return None


def scan_events() -> None:
    """CPI and payrolls since 2016: release date, plus the data as it stood the day before and on the day."""
    spec = {"CPI": ("CPIAUCSL", ["CPIAUCSL", "CPILFESL"], 7), "NFP": ("PAYEMS", ["PAYEMS", "UNRATE", "CES0500000003"], 0)}
    last = pd.read_csv(PROCESSED / "fred_monthly.csv")
    rows, out = [], []
    for ind, (main, companions, day0) in spec.items():
        latest = date.fromisoformat(last[last.series == main].date.max())
        ref = date.fromisoformat(EVENT_START)
        while ref <= latest:
            nxt = month_add(ref, 1)
            start = (nxt + timedelta(day0 - 1)) if day0 else (nxt - timedelta(1))
            rel = first_release(main, ref, start)
            if rel is None:
                rows.append((ind, str(ref), None))
                print(f"  {ind} {ref:%Y-%m}: no release found (not published)")
            else:
                rows.append((ind, str(ref), str(rel)))
                before = rel - timedelta(1)
                cols = [(s, d) for s in companions for d in (before, rel)]
                v = alfred(cols, month_add(ref, -5), ref)
                v["role"] = v.vintage.map({before: "before", rel: "release"})
                out.append(v.assign(indicator=ind, ref=str(ref), release_date=str(rel)))
            ref = month_add(ref, 1)
        print(f"ALFRED events    {ind}: {sum(1 for r in rows if r[0] == ind and r[2])} releases located")
    pd.DataFrame(rows, columns=["indicator", "ref", "release_date"]).to_csv(PROCESSED / "event_release_dates.csv", index=False)
    pd.concat(out).drop(columns="vintage").to_csv(PROCESSED / "event_vintages.csv", index=False)


# ------------------------------------------------------------------------------------------------ Fed and schedules
def fetch_fomc() -> None:
    txt = cached("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    rows = []
    for year, block in re.findall(r"(\d{4}) FOMC Meetings</a></h4>(.*?)(?=\d{4} FOMC Meetings</a></h4>|$)", txt, flags=re.S):
        for mon, days in re.findall(r'fomc-meeting__month[^>]*><strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<', block, flags=re.S):
            days = days.strip()
            sep = "*" in days
            d = re.sub(r"[^\d\-]", "", days.split("(")[0])
            if not d:
                continue
            last_day = int(d.split("-")[-1])
            mon_last = mon.split("/")[-1].strip()
            try:
                end = pd.Timestamp(f"{mon_last} {last_day} {year}").date() if "/" in mon else pd.Timestamp(f"{mon.strip()} {last_day} {year}").date()
            except ValueError:
                continue
            rows.append((int(year), mon.strip(), days, str(end), sep))
    df = pd.DataFrame(rows, columns=["year", "month", "days", "decision_date", "projections"]).drop_duplicates("decision_date")
    df = df[~df.days.str.contains("notation|unscheduled", case=False)].sort_values("decision_date")
    df.to_csv(PROCESSED / "fomc_meetings.csv", index=False)
    print(f"Fed              {len(df)} FOMC meetings {df.year.min()}-{df.year.max()}")


def fetch_schedules() -> None:
    rows = []
    js = json.loads(cached("https://apps.bea.gov/API/signup/release_dates.json"))
    for name, info in js.items():
        if not isinstance(info, dict):
            continue
        for dt in info.get("release_dates", []):
            ts = pd.Timestamp(dt).tz_convert("America/New_York")
            rows.append(("BEA", name, ts.date().isoformat(), ts.strftime("%H:%M"), ""))
    pat = r"([A-Z][A-Za-z,'\-\(\) &.]+?) ((?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}) (\d{1,2}:\d{2} [AP]M) (.+?) A\d{12}"
    for page in ("calendar-listview-2026.html", "calendar-listview.html"):
        txt = cached(f"https://www.census.gov/economic-indicators/{page}")
        txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", txt, flags=re.S))))
        for name, d, t, ref in re.findall(pat, txt):
            rows.append(("Census", name.strip(), pd.Timestamp(d).date().isoformat(), pd.Timestamp(t).strftime("%H:%M"), ref.strip()))
    df = pd.DataFrame(rows, columns=["agency", "release", "date", "time_et", "reference"]).drop_duplicates()
    df.sort_values(["date", "time_et"]).to_csv(PROCESSED / "schedule_official.csv", index=False)
    print(f"Schedules        {len(df)} official release dates (BEA {sum(df.agency == 'BEA')}, Census {sum(df.agency == 'Census')})")


if __name__ == "__main__":
    steps = sys.argv[1:] or ["bls", "fred", "treasury", "fomc", "schedules", "recent", "events"]
    fn = {"bls": fetch_bls, "fred": fetch_fred, "treasury": fetch_treasury, "fomc": fetch_fomc, "schedules": fetch_schedules,
          "recent": scan_recent, "events": scan_events}
    for s in steps:
        fn[s]()
    (RAW / "_collected_on.txt").write_text(str(TODAY), encoding="utf-8")
