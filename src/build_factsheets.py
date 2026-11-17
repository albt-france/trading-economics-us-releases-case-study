"""Rebuild the economic calendar (calendar/us_calendar.csv) and one fact sheet per release (factsheets/<date>_<bundle>.md
and .json) from the tidy public tables. Every figure is computed inside the vintage that was public on the day, so
"previous" means what readers had seen the day before and "revised" what the release changed.

Usage: python src/build_factsheets.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CAL, CAL_END, CAL_START, EVENT_COLS, EVENTS, FACTS, OUT, PROCESSED  # noqa: E402

TODAY = date(2026, 11, 17)
EV = pd.DataFrame(EVENTS, columns=EVENT_COLS).set_index("key")
VIN = pd.read_csv(PROCESSED / "vintages_recent.csv", parse_dates=["date"])
CUR = pd.read_csv(PROCESSED / "fred_monthly.csv", parse_dates=["date"])
BLS = pd.read_csv(PROCESSED / "bls_series.csv", parse_dates=["date"])
MK = pd.read_csv(PROCESSED / "markets_daily.csv", parse_dates=["date"]).set_index("date")
FOMC = pd.read_csv(PROCESSED / "fomc_meetings.csv", parse_dates=["decision_date"])
SCHED = pd.read_csv(PROCESSED / "schedule_official.csv", parse_dates=["date"])
NSA_SERIES = {"CPIAUCNS", "CPILFENS"}

# Release bundles: which calendar events go into one fact sheet (one commentary).
BUNDLES = {
    "cpi": ["cpi_mom", "cpi_yoy", "core_cpi_mom", "core_cpi_yoy"],
    "jobs": ["nfp", "unrate", "ahe_mom"],
    "retail": ["retail_mom", "retail_xauto"],
    "ppi": ["ppi_mom"],
    "gdp": ["gdp"],
    "pce": ["pce_yoy", "core_pce_mom", "core_pce_yoy", "spending_mom"],
    "jolts": ["jolts"],
    "claims": ["claims"],
    "indpro": ["indpro_mom"],
    "starts": ["starts"],
    "durables": ["durables"],
    "newhomes": ["new_homes"],
    "trade": ["trade"],
}
BUNDLE_NAME = {"cpi": "Consumer Price Index", "jobs": "Employment Situation", "retail": "Advance retail sales",
               "ppi": "Producer Price Index", "gdp": "GDP (advance estimate)", "pce": "Personal income and outlays (PCE)",
               "jolts": "Job openings (JOLTS)", "claims": "Weekly jobless claims", "indpro": "Industrial production",
               "starts": "Housing starts", "durables": "Durable goods orders", "newhomes": "New home sales",
               "trade": "International trade", "fomc": "FOMC rate decision"}
KEYWORDS = {
    "cpi_mom": ["CPI", "consumer prices", "consumer price index", "headline", "headline CPI", "inflation", "prices", "headline inflation"],
    "cpi_yoy": ["CPI", "consumer prices", "consumer price index", "headline", "headline CPI", "inflation", "prices", "headline inflation", "annual inflation"],
    "core_cpi_mom": ["core", "core CPI", "core prices", "core inflation", "underlying inflation", "excluding food and energy"],
    "core_cpi_yoy": ["core", "core CPI", "core prices", "core inflation", "underlying inflation", "excluding food and energy"],
    "nfp": ["payrolls", "non-farm payrolls", "nonfarm payrolls", "jobs", "employers", "employment", "hiring", "job gains", "job growth"],
    "unrate": ["unemployment", "unemployment rate", "jobless rate"],
    "ahe_mom": ["earnings", "hourly earnings", "average hourly earnings", "wages", "wage growth", "pay"],
    "ppi_mom": ["PPI", "producer prices", "producer price index", "wholesale prices", "final demand"],
    "jolts": ["job openings", "openings", "vacancies", "JOLTS"],
    "claims": ["claims", "jobless claims", "initial claims", "initial jobless claims", "applications"],
    "retail_mom": ["retail sales", "sales", "retail", "consumer spending at retailers", "headline sales"],
    "retail_xauto": ["excluding autos", "ex-autos", "ex autos", "excluding motor vehicles", "outside autos", "excluding cars"],
    "starts": ["housing starts", "starts", "homebuilding", "groundbreaking"],
    "durables": ["durable goods", "durable goods orders", "orders", "durables"],
    "new_homes": ["new home sales", "new homes", "home sales"],
    "trade": ["trade deficit", "trade balance", "deficit", "trade gap", "gap"],
    "gdp": ["GDP", "gross domestic product", "economy", "growth", "output"],
    "pce_yoy": ["PCE", "PCE price index", "headline PCE", "PCE inflation", "inflation", "prices"],
    "core_pce_mom": ["core PCE", "core", "core inflation", "core prices", "underlying inflation"],
    "core_pce_yoy": ["core PCE", "core", "core inflation", "core prices", "underlying inflation"],
    "spending_mom": ["spending", "consumer spending", "personal spending", "personal consumption", "consumption"],
    "indpro_mom": ["industrial production", "production", "output", "industrial output", "factory output"],
}
MARKET_FACTS = [  # id, label, column, how, unit, keywords
    ("y2_bp", "2-year Treasury yield, daily change", "DGS2", "bp", "bp", ["2-year", "two-year", "2-year yield", "two-year yield", "2-year Treasury yield", "short-dated yields", "2-year note"]),
    ("y2_lvl", "2-year Treasury yield, close", "DGS2", "level", "%", ["2-year", "two-year", "2-year yield", "two-year yield", "2-year Treasury yield", "2-year note"]),
    ("y10_bp", "10-year Treasury yield, daily change", "DGS10", "bp", "bp", ["10-year", "ten-year", "10-year yield", "ten-year yield", "10-year Treasury yield", "long-dated yields", "10-year note"]),
    ("y10_lvl", "10-year Treasury yield, close", "DGS10", "level", "%", ["10-year", "ten-year", "10-year yield", "ten-year yield", "10-year Treasury yield", "10-year note"]),
    ("usd_pct", "Broad dollar index, daily % change", "DTWEXBGS", "pct", "%", ["dollar", "dollar index", "greenback", "broad dollar", "US dollar"]),
    ("eur_pct", "EUR/USD, daily % change", "DEXUSEU", "pct", "%", ["euro", "EUR/USD"]),
    ("eur_lvl", "EUR/USD, noon rate", "DEXUSEU", "level4", "", ["euro", "EUR/USD"]),
    ("spx_pct", "S&P 500, daily % change", "SP500", "pct", "%", ["S&P 500", "S&P", "stocks", "equities", "Wall Street", "shares"]),
    ("spx_lvl", "S&P 500, close", "SP500", "level", "", ["S&P 500", "S&P", "stocks", "equities", "Wall Street"]),
    ("ndq_pct", "Nasdaq Composite, daily % change", "NASDAQCOM", "pct", "%", ["Nasdaq", "Nasdaq Composite", "tech stocks"]),
    ("wti_pct", "WTI crude oil, daily % change", "DCOILWTICO", "pct", "%", ["oil", "WTI", "crude", "oil prices", "crude oil"]),
    ("wti_lvl", "WTI crude oil, USD per barrel", "DCOILWTICO", "level", "$", ["oil", "WTI", "crude", "oil prices", "crude oil"]),
]


# ------------------------------------------------------------------------------------------------ computations
def vintage(series: str, vin: str) -> pd.Series:
    """The series as it stood on vintage date `vin` (latest vintage on or before that date)."""
    v = VIN[VIN.series == series]
    ok = sorted(x for x in v.vintage.unique() if x <= vin)
    s = v[v.vintage == ok[-1]].set_index("date").value.sort_index()
    return s


def full_history(series: str, vin: str) -> pd.Series:
    """Release vintage, completed with older current-vintage data (for 'highest since' notes only)."""
    s = vintage(series, vin)
    old = CUR[(CUR.series == series) & (CUR.date < s.index.min())].set_index("date").value
    return pd.concat([old, s]).sort_index()


def transform(s: pd.Series, kind: str, ref: pd.Timestamp, scale=1.0) -> float | None:
    if ref not in s.index:
        return None
    i = s.index.get_loc(ref)
    if kind == "level":
        return s.iloc[i] / scale
    if kind == "yoy":
        back = ref - pd.DateOffset(years=1)
        return 100 * (s.iloc[i] / s[back] - 1) if back in s.index else None
    if i == 0:
        return None
    if kind == "mom":
        return 100 * (s.iloc[i] / s.iloc[i - 1] - 1)
    return (s.iloc[i] - s.iloc[i - 1]) / scale            # diff


def series_t(s: pd.Series, kind: str, scale=1.0) -> pd.Series:
    return pd.Series({d: transform(s, kind, d, scale) for d in s.index}).dropna()


def releases(series: str) -> list[dict]:
    """Each vintage that added an observation = one release (vintages that only changed old values = revisions)."""
    v = VIN[VIN.series == series]
    vins = sorted(v.vintage.unique())
    out = []
    for a, b in zip(vins, vins[1:]):
        old, new = set(v[v.vintage == a].date), set(v[v.vintage == b].date)
        added = sorted(new - old)
        out.append(dict(before=a, date=b, ref=added[-1] if added else None, revision_only=not added))
    return out


def model_forecast(s_before: pd.Series, kind: str, model: str, ref: pd.Timestamp, scale=1.0) -> float | None:
    t = series_t(s_before, kind, scale)
    t = t[t.index < ref]
    if t.empty:
        return None
    return float(t.iloc[-3:].mean()) if model == "avg3" else float(t.iloc[-1])


def period_label(ref: pd.Timestamp, series: str) -> str:
    if series == "A191RL1Q225SBEA":
        return f"Q{(ref.month - 1) // 3 + 1} {ref.year}"
    if series == "ICSA":
        return f"week to {ref:%b} {ref.day}"
    return f"{ref:%b %Y}"


MONTHS3 = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"}


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def fmt(x, dec, unit=""):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    s = f"{x:,.{dec}f}"
    return s + unit if unit in ("%", "K", "M") else s + (" " + unit if unit else "")


def extreme_note(hist: pd.Series, ref: pd.Timestamp, val: float, dec: int) -> str:
    """'highest since Mar 2025' when the print is the highest (or lowest) for at least 6 periods."""
    if val is None:
        return ""
    h = hist[hist.index < ref].round(dec)
    v = round(val, dec)
    for word, test in (("highest", h >= v), ("lowest", h <= v)):
        prior = h[test]
        if prior.empty:
            return f"{word} in the data shown (since {h.index.min():%b %Y})" if len(h) >= 6 else ""
        last = prior.index.max()
        n_between = (h.index > last).sum()
        if n_between >= 5:
            return f"{word} since {last:%b %Y}"
    return ""


def market_moves(day: pd.Timestamp) -> dict:
    out = {}
    for col in ["DGS2", "DGS10", "DTWEXBGS", "DEXUSEU", "SP500", "NASDAQCOM", "DCOILWTICO"]:
        s = MK[col].dropna()
        if day not in s.index:
            out[col] = (None, None)
            continue
        i = s.index.get_loc(day)
        prev = s.iloc[i - 1]
        chg = (s.iloc[i] - prev) * 100 if col in ("DGS2", "DGS10") else 100 * (s.iloc[i] / prev - 1)
        out[col] = (float(s.iloc[i]), float(chg))
    return out


# ------------------------------------------------------------------------------------------------ calendar
def calendar_rows() -> pd.DataFrame:
    rows = []
    for key, e in EV.iterrows():
        for r in releases(e.series):
            d = pd.Timestamp(r["date"])
            if r["revision_only"] or not (pd.Timestamp(CAL_START) <= d <= pd.Timestamp(TODAY)):
                continue
            ref = r["ref"]
            sb, sa = vintage(e.series, r["before"]), vintage(e.series, r["date"])
            ref_prev = sa.index[sa.index.get_loc(ref) - 1]
            actual = transform(sa, e.kind, ref, e.scale)
            prev_before = transform(sb, e.kind, ref_prev, e.scale)
            prev_rev = transform(sa, e.kind, ref_prev, e.scale)
            fc = model_forecast(sb, e.kind, e.model, ref, e.scale)
            revised = prev_rev if (prev_before is not None and round(prev_rev, e.dec) != round(prev_before, e.dec)) else None
            note = []
            if actual is None:
                rows.append(dict(date=d.date(), time_et=e.time, country="United States", event=e.event, key=key,
                                 reference=period_label(ref, e.series), actual=None,
                                 previous=round(prev_before, e.dec) if prev_before is not None else None, revised_previous=None,
                                 forecast_model=None, unit=e.unit, importance=e.importance, source=e.source, status="released",
                                 note=f"Not computable from published indexes: the {ref - pd.DateOffset(years=1):%b %Y} index was "
                                      "not published (2025 lapse in appropriations); see the BLS release text"))
                continue
            if revised is not None:
                note.append(f"previous revised from {fmt(prev_before, e.dec, e.unit)} to {fmt(prev_rev, e.dec, e.unit)}")
            if e.kind in ("level", "yoy") and key != "trade":
                ex = extreme_note(series_t(full_history(e.series, r["date"]), e.kind, e.scale), ref, actual, e.dec)
                if ex:
                    note.append(ex)
            if fc is not None and not note:
                diff = round(actual, e.dec) - round(fc, e.dec)
                note.append("in line with the model forecast" if abs(diff) < 10 ** -e.dec / 2 else
                            f"{'above' if diff > 0 else 'below'} the model forecast")
            rows.append(dict(date=d.date(), time_et=e.time, country="United States", event=e.event, key=key,
                             reference=period_label(ref, e.series), actual=round(actual, e.dec),
                             previous=round(prev_before, e.dec) if prev_before is not None else None,
                             revised_previous=round(revised, e.dec) if revised is not None else None,
                             forecast_model=round(fc, e.dec) if fc is not None else None, unit=e.unit,
                             importance=e.importance, source=e.source, status="released", note=cap("; ".join(note))))
    # FOMC decisions in the window
    for _, m in FOMC[(FOMC.decision_date >= CAL_START) & (FOMC.decision_date <= CAL_END)].iterrows():
        d = m.decision_date
        hi, lo = MK.DFEDTARU.dropna(), MK.DFEDTARL.dropna()
        if d.date() <= TODAY:
            after_hi, after_lo = hi[hi.index > d].iloc[0], lo[lo.index > d].iloc[0]
            bef_hi, bef_lo = hi[hi.index <= d].iloc[-1], lo[lo.index <= d].iloc[-1]
            move = round((after_hi - bef_hi) * 100)
            note = "held" if move == 0 else (f"cut by {-move} bp" if move < 0 else f"raised by {move} bp")
            rows.append(dict(date=d.date(), time_et="14:00", country="United States", event="Fed interest rate decision (upper bound)",
                             key="fomc", reference=f"{d:%b %Y}", actual=after_hi, previous=bef_hi, revised_previous=None,
                             forecast_model=bef_hi, unit="%", importance="high", source="Fed", status="released",
                             note=f"Target range {note}: {after_lo:.2f}%-{after_hi:.2f}%"
                                  + ("; with projections" if m.projections else "")))
        else:
            rows.append(dict(date=d.date(), time_et="14:00", country="United States", event="Fed interest rate decision (upper bound)",
                             key="fomc", reference=f"{d:%b %Y}", actual=None, previous=hi.iloc[-1], revised_previous=None,
                             forecast_model=hi.iloc[-1], unit="%", importance="high", source="Fed", status="scheduled",
                             note="Model = no change (illustrative)"))
    rows += upcoming_rows()
    cal = pd.DataFrame(rows).sort_values(["date", "time_et", "importance", "event"]).reset_index(drop=True)
    return cal


UPCOMING_MAP = {  # official schedule name -> calendar keys
    "Advance Monthly Sales for Retail and Food Services": ["retail_mom", "retail_xauto"],
    "New Residential Construction (Building Permits, Housing Starts, and Housing Completions)": ["starts"],
    "Advance Report on Durable Goods--Manufacturers' Shipments, Inventories, and Orders": ["durables"],
    "New Residential Sales": ["new_homes"],
    "Gross Domestic Product": ["gdp"],
    "Personal Income and Outlays": ["pce_yoy", "core_pce_mom", "core_pce_yoy", "spending_mom"],
}


def upcoming_rows() -> list[dict]:
    """Scheduled releases after the collection date (or released today but not yet in the public archive)."""
    rows = []
    done = {(r["key"], pd.Timestamp(r["date"])) for r in []}
    sch = SCHED[(SCHED.date >= pd.Timestamp(TODAY)) & (SCHED.date <= CAL_END) & SCHED.release.isin(UPCOMING_MAP)]
    for _, s in sch.drop_duplicates(["release", "date"]).iterrows():
        for key in UPCOMING_MAP[s.release]:
            e = EV.loc[key]
            cur = vintage(e.series, str(TODAY))
            last = cur.index.max()
            if (key, s.date) in done:
                continue
            nxt_ref = last + (pd.DateOffset(months=3) if e.series == "A191RL1Q225SBEA" else pd.DateOffset(months=1))
            if e.series == "A191RL1Q225SBEA" and "Second" not in s.release:
                nxt_ref = last   # BEA's second estimate revises the quarter already published
            prev = transform(cur, e.kind, last, e.scale)
            fc = model_forecast(cur, e.kind, e.model, last + pd.DateOffset(days=1), e.scale)
            status = "released, not yet in archive" if s.date.date() == TODAY else "scheduled"
            note = ("Published 17 Nov 08:30 ET; not yet in the public archive when collected" if status != "scheduled"
                    else "Second estimate of Q3" if e.series == "A191RL1Q225SBEA" else "")
            rows.append(dict(date=s.date.date(), time_et=s.time_et, country="United States", event=e.event, key=key,
                             reference=pd.Timestamp(s.reference).strftime("%b %Y") if isinstance(s.reference, str) and s.reference[:3] in MONTHS3 else period_label(last if e.series == "A191RL1Q225SBEA" else nxt_ref, e.series),
                             actual=None, previous=round(prev, e.dec), revised_previous=None,
                             forecast_model=round(fc, e.dec) if fc is not None and e.series != "A191RL1Q225SBEA" else round(prev, e.dec),
                             unit=e.unit, importance=e.importance, source=e.source, status=status, note=note))
    # weekly claims: every Thursday at 08:30 (Wednesday in Thanksgiving week, Labor Department practice)
    cur = vintage("ICSA", str(TODAY))
    fc = model_forecast(cur, "level", "avg3", cur.index.max() + pd.DateOffset(days=1), 1000)
    for d, note in ((date(2026, 11, 19), ""), (date(2026, 11, 25), "Wednesday release in Thanksgiving week (usual practice; confirm)")):
        rows.append(dict(date=d, time_et="08:30", country="United States", event="Initial jobless claims", key="claims",
                         reference=f"week to {pd.Timestamp(d) - pd.Timedelta(days=5 if d.weekday() == 3 else 4):%b} "
                                   f"{(pd.Timestamp(d) - pd.Timedelta(days=5 if d.weekday() == 3 else 4)).day}",
                         actual=None, previous=round(cur.iloc[-1] / 1000) if d == date(2026, 11, 19) else None,
                         revised_previous=None, forecast_model=round(fc), unit="K", importance="medium", source="DOL",
                         status="scheduled", note=note))
    return rows


# ------------------------------------------------------------------------------------------------ fact sheets
def fact(id_, label, value, family, unit_txt, role, month, keywords, measure=None, basis=None, prev=None, dec=1, signed_level=False):
    return dict(id=id_, label=label, value=None if value is None else round(float(value), dec), family=family, unit_txt=unit_txt,
                role=role, month=month, keywords=keywords, measure=measure, basis=basis,
                prev=None if prev is None else round(float(prev), dec), signed_level=signed_level)


def family_of(e) -> tuple[str, str]:
    if e.unit == "%":
        return "pct", "%"
    if e.unit in ("K", "M"):
        return "count", "K"
    return "money", " USD bn"


def bundle_facts(bundle: str, rel_date: str) -> tuple[list[dict], dict]:
    """Facts for every event of the bundle, in the vintage published on rel_date."""
    facts, info = [], {}
    for key in BUNDLES[bundle]:
        e = EV.loc[key]
        r = next(r for r in releases(e.series) if r["date"] == rel_date)
        sb, sa = vintage(e.series, r["before"]), vintage(e.series, r["date"])
        ref = r["ref"]
        ref_prev = sa.index[sa.index.get_loc(ref) - 1]
        scale = 1 if e.unit == "K" and e.series != "ICSA" else e.scale        # counts kept in thousands
        if e.series in ("JTSJOL", "HOUST", "HSN1F"):
            scale = 1
        dec = e.dec if e.unit in ("%",) else (0 if e.series not in ("BOPGSTB",) else 1)
        act, pb, pr = (transform(sa, e.kind, ref, scale), transform(sb, e.kind, ref_prev, scale), transform(sa, e.kind, ref_prev, scale))
        fc = model_forecast(sb, e.kind, e.model, ref, scale)
        fam, ut = family_of(e)
        meas = {"mom": "mom", "yoy": "yoy"}.get(e.kind, "ann" if key == "gdp" else None)
        basis = "NSA" if e.series in NSA_SERIES else ("SA" if e.kind in ("mom", "diff") else None)
        mon, mon_p = ref.strftime("%B").lower(), ref_prev.strftime("%B").lower()
        if key == "gdp":
            mon, mon_p = f"q{(ref.month - 1) // 3 + 1}", f"q{(ref_prev.month - 1) // 3 + 1}"
        kw = KEYWORDS[key]
        sign_lvl = key == "trade"
        facts.append(fact(key, f"{e.event}, {period_label(ref, e.series)}", act, fam, ut, "current", mon, kw, meas, basis, pr, dec, sign_lvl))
        facts.append(fact(key, f"{e.event}, {period_label(ref_prev, e.series)} (revised)", pr, fam, ut, "previous", mon_p, kw, meas, basis, None, dec, sign_lvl))
        if pb is not None and round(pb, dec) != round(pr, dec):
            facts.append(fact(key + "_first", f"{e.event}, {period_label(ref_prev, e.series)} (as first reported)", pb, fam, ut,
                              "previous_first", mon_p, kw, meas, basis, None, dec, sign_lvl))
        if fc is not None:
            facts.append(fact(key + "_model", f"{e.event}, model forecast (illustrative)", fc, fam, ut, "forecast", mon, kw, meas, basis, None, dec, sign_lvl))
        hist = series_t(full_history(e.series, r["date"]), e.kind, scale)
        info[key] = dict(event=e.event, ref=ref, ref_prev=ref_prev, actual=act, prev_before=pb, prev_revised=pr, forecast=fc,
                         dec=dec, unit=ut.strip(), series=e.series, avg3=hist[hist.index < ref].iloc[-3:].mean(),
                         avg12=hist[hist.index < ref].iloc[-12:].mean(), hist=hist, sa=sa, sb=sb, kind=e.kind,
                         extreme=extreme_note(hist, ref, act, dec) if e.kind in ("level", "yoy") and key != "trade" else "")
        if key == "unrate":
            facts.append(fact("unrate_pp", "Unemployment rate, change on previous month", act - pr, "pp", " pp", "current", mon, kw, None, None, None, 1))
        if key == "nfp":
            avg = sa.diff().loc[:ref].iloc[-3:].mean()
            facts.append(fact("nfp_avg3", "Payrolls, 3-month average change", avg, "count", "K", "current", mon,
                              ["three-month average", "3-month average", "average"], None, None, None, 0))
            ref2 = sa.index[sa.index.get_loc(ref) - 2]
            ref3 = sa.index[sa.index.get_loc(ref) - 3]
            # revision to the two monthly *changes* = revision to the last revised level minus revision to the level
            # three months back (adding the two level revisions would count the earlier month twice)
            two = (sa[ref_prev] - sb[ref_prev]) - (sa[ref3] - sb.get(ref3, sa[ref3]))
            facts.append(fact("nfp_rev2", "Payrolls, combined revision to the two previous months", two, "count", "K", "current", mon,
                              ["revisions", "combined revisions", "net revisions", "revisions to"], None, None, None, 0))
            info["nfp"]["rev2"] = two
            info["nfp"]["ref2"] = ref2
        if key in ("ahe_mom",):
            y = transform(sa, "yoy", ref)
            facts.append(fact("ahe_yoy", f"Average hourly earnings YoY, {period_label(ref, e.series)}", y, "pct", "%", "current", mon, kw, "yoy", None, None, 1))
            lvl = sa[ref]
            facts.append(fact("ahe_lvl", "Average hourly earnings, USD", lvl, "level", "", "current", mon, kw, None, None, None, 2))
            info[key]["yoy"] = y
        if key in ("retail_mom", "ppi_mom", "spending_mom", "indpro_mom"):
            y = transform(sa, "yoy", ref)
            if y is not None:
                facts.append(fact(key.replace("_mom", "_yoy"), f"{e.event.replace('MoM', 'YoY')}, {period_label(ref, e.series)}", y, "pct", "%", "current", mon, kw, "yoy", None, None, 1))
                info[key]["yoy"] = y
        if key == "pce_yoy":
            m = transform(sa, "mom", ref)
            facts.append(fact("pce_mom", f"PCE price index MoM, {period_label(ref, e.series)}", m, "pct", "%", "current", mon, kw, "mom", "SA", None, 1))
            info[key]["mom"] = m
        if key in ("starts", "new_homes", "jolts", "claims"):
            # also accept the level written in millions (e.g. "1.31 million"); checker converts units
            pass
    return facts, info


CPI_COMPONENTS = {"CUSR0000SA0E": ("energy", ["energy", "energy prices", "gasoline", "fuel"]),
                  "CUSR0000SAF1": ("food", ["food", "food prices", "groceries"]),
                  "CUSR0000SAH1": ("shelter", ["shelter", "housing costs", "rents", "rent"]),
                  "CUSR0000SASLE": ("services less energy", ["services", "core services", "services excluding energy"]),
                  "CUSR0000SACL1E": ("core goods", ["goods", "core goods", "goods prices"])}


def bls_mom(series_id: str, ref: pd.Timestamp) -> float | None:
    s = BLS[BLS.series_id == series_id].set_index("date").value.sort_index()
    return transform(s, "mom", ref)


def markets_facts(d: pd.Timestamp, month: str) -> tuple[list[dict], dict]:
    mv = market_moves(d)
    facts = []
    for id_, label, col, how, unit, kw in MARKET_FACTS:
        lvl, chg = mv[col]
        if lvl is None:
            continue
        if how == "bp":
            facts.append(fact(id_, label, chg, "bp", " bp", "market", month, kw, None, None, None, 0))
        elif how == "pct":
            facts.append(fact(id_, label, chg, "pct", "%", "market", month, kw, None, None, None, 2))
        elif how == "level4":
            facts.append(fact(id_, label, lvl, "level", "", "market", month, kw, None, None, None, 4))
        else:
            facts.append(fact(id_, label, lvl, "pct" if unit == "%" else "level", unit, "market", month, kw, None, None, None, 2))
    return facts, mv


WATCH = {
    "cpi": ["Core CPI month-on-month: the measure the Fed and markets watch for underlying inflation (0.17% a month is about 2% a year).",
            "Shelter and core services: the slow-moving part of inflation.",
            "Energy: moves headline CPI, usually not core.",
            "2-year Treasury yield: the market rate most sensitive to Fed expectations."],
    "jobs": ["Payroll change vs the 3-month average and the revisions to the two previous months.",
             "Unemployment rate: a rise of 0.1-0.2 point can matter more than the payroll number.",
             "Average hourly earnings: wage pressure feeding services inflation.",
             "2-year yield and dollar: they price the path of Fed rates."],
    "retail": ["Headline vs ex-autos sales: car sales and gasoline prices swing the headline.",
               "Retail sales are nominal: compare with CPI goods prices before talking about volumes.",
               "Revisions to the previous month are frequent and sometimes large."],
    "ppi": ["Final demand PPI month-on-month; parts of PPI feed into the core PCE price index."],
    "gdp": ["Annualised quarterly growth (BEA headline) vs the previous quarter.",
            "Advance estimate: revised twice (second and third estimates) and in annual updates."],
    "pce": ["Core PCE price index: the Fed's preferred inflation gauge; its target is 2% for headline PCE over time.",
            "Personal spending month-on-month (nominal)."],
    "jolts": ["Job openings level vs the previous month (revised); openings lag the payroll report by a month."],
    "claims": ["Weekly initial claims vs the 4-week trend; holiday weeks are noisy."],
    "indpro": ["Industrial production month-on-month; manufacturing vs utilities (weather) and mining."],
    "starts": ["Housing starts (annual rate) are volatile: compare with the 3-month average."],
    "durables": ["Durable goods orders swing with aircraft orders: look at the ex-transportation figure in the release."],
    "newhomes": ["New home sales are volatile and revised heavily."],
    "trade": ["Trade deficit in billions of dollars; goods vs services."],
    "fomc": ["Decision vs the target range in force; vote split; changes in the statement; projections at Mar/Jun/Sep/Dec meetings."],
}


def write_sheet(bundle: str, rel_date: str) -> str:
    d = pd.Timestamp(rel_date)
    release = f"{rel_date}_{bundle}"
    mk_facts, mv = markets_facts(d, d.strftime("%B").lower())
    lines, extra = [], []
    if bundle == "fomc":
        facts, head = fomc_facts(d)
        lines += head
    else:
        facts, info = bundle_facts(bundle, rel_date)
        k0 = BUNDLES[bundle][0]
        ref = info[k0]["ref"]
        lines.append(f"| Indicator | {period_label(ref, info[k0]['series'])} | Previous as first reported | Previous revised "
                     f"| 3-period avg | 12-period avg | Model forecast (illustrative) |")
        lines.append("|---|---|---|---|---|---|---|")
        for key in BUNDLES[bundle]:
            i = info[key]
            u = i["unit"]
            lines.append(f"| {i['event']} | **{fmt(i['actual'], i['dec'], u) or 'n/a'}** | {fmt(i['prev_before'], i['dec'], u)} | "
                         f"{fmt(i['prev_revised'], i['dec'], u)} | {fmt(i['avg3'], i['dec'], u)} | {fmt(i['avg12'], i['dec'], u)} | "
                         f"{fmt(i['forecast'], i['dec'], u)} |")
        notes = []
        for key in BUNDLES[bundle]:
            i = info[key]
            if i["actual"] is None:
                notes.append(f"{i['event']}: not computable from published indexes - the {i['ref'] - pd.DateOffset(years=1):%B %Y} "
                             "index was never published (2025 lapse in appropriations). Do not estimate it; check the BLS release text.")
            if i["extreme"]:
                notes.append(f"{i['event']}: {i['extreme']}.")
            if i["prev_before"] is not None and round(i["prev_before"], i["dec"]) != round(i["prev_revised"], i["dec"]):
                notes.append(f"{i['event']}: {i['ref_prev']:%B} revised from {fmt(i['prev_before'], i['dec'], i['unit'])} "
                             f"to {fmt(i['prev_revised'], i['dec'], i['unit'])}.")
            if "yoy" in i and i.get("yoy") is not None:
                notes.append(f"{i['event'].replace('MoM', 'YoY')}: {fmt(i['yoy'], 1, '%')}.")
            if "mom" in i:
                notes.append(f"PCE price index MoM: {fmt(i['mom'], 1, '%')}.")
        if bundle == "jobs":
            i = info["nfp"]
            notes.append(f"Payrolls, combined revision to {i['ref2']:%B} and {i['ref_prev']:%B}: {i['rev2']:+,.0f}K.")
            avg = i["sa"].diff().loc[:i["ref"]].iloc[-3:].mean()
            notes.append(f"Payrolls, 3-month average change (incl. this release): {avg:,.0f}K.")
            notes.append(f"Average hourly earnings: USD {i['sa'][i['ref']]:.2f}." if False else "")
        if bundle == "cpi":
            comp = []
            for sid, (name, kw) in CPI_COMPONENTS.items():
                m = bls_mom(sid, ref)
                prevm = bls_mom(sid, info[k0]["ref_prev"])
                if m is None:
                    continue
                facts.append(fact(f"cpi_{name.replace(' ', '_')}", f"CPI {name} MoM, SA, {ref:%b %Y}", m, "pct", "%", "current",
                                  ref.strftime("%B").lower(), kw, "mom", "SA", prevm, 1))
                comp.append(f"| {name.capitalize()} | {m:+.1f}% | {prevm:+.1f}% |")
            nsa = bls_mom("CUUR0000SA0", ref)
            facts.append(fact("cpi_mom_nsa", f"CPI MoM, not seasonally adjusted, {ref:%b %Y}", nsa, "pct", "%", "current",
                              ref.strftime("%B").lower(), KEYWORDS["cpi_mom"], "mom", "NSA", None, 1))
            extra += ["", "**Components (month-on-month, seasonally adjusted, BLS API)**", "",
                      f"| Component | {ref:%b %Y} | {info[k0]['ref_prev']:%b %Y} |", "|---|---|---|", *comp,
                      "", f"All-items CPI month-on-month, not seasonally adjusted: {nsa:+.1f}% (BLS headline year-on-year rates are NSA)."]
        lines += [""] + [f"- {n}" for n in notes if n]
        lines = [f"Reference period: **{period_label(ref, info[k0]['series'])}** · released {d:%a %d %b %Y} at "
                 f"{EV.loc[k0].time} ET · source: {EV.loc[k0].source} (PUBLIC DATA)", ""] + lines
    facts += mk_facts
    facts.append(fact("fed_target", "Fed inflation goal (PCE, over time)", 2.0, "pct", "%", "context", "", ["target", "goal", "Fed's target",
                      "Fed's goal", "inflation target", "2% target"], None, None, None, 1))
    mtab = ["", f"**Markets on the day ({d:%d %b %Y}, daily closes vs previous day, PUBLIC DATA)**", "",
            "| Market | Level | Change |", "|---|---|---|"]
    for col, name, unit in (("DGS2", "2-year Treasury yield", "%"), ("DGS10", "10-year Treasury yield", "%"),
                            ("DTWEXBGS", "Broad dollar index", ""), ("DEXUSEU", "EUR/USD", ""), ("SP500", "S&P 500", ""), ("NASDAQCOM", "Nasdaq Composite", ""),
                            ("DCOILWTICO", "WTI crude (USD/bbl)", "")):
        lvl, chg = mv[col]
        if lvl is None:
            mtab.append(f"| {name} | n/a | no data that day |")
            continue
        c = f"{chg:+.0f} bp" if col in ("DGS2", "DGS10") else f"{chg:+.2f}%"
        mtab.append(f"| {name} | {lvl:,.{4 if col == 'DEXUSEU' else 2}f}{unit} | {c} |")
    title = f"# Fact sheet - {BUNDLE_NAME[bundle]} - released {d:%d %b %Y}"
    md = [title, "", *lines, *extra, *mtab, "", "**What markets were watching**", "", *[f"- {w}" for w in WATCH[bundle]], "",
          "_Model forecast (illustrative) = simple rule on data known the day before (3-period average of changes, or the "
          "previous value for levels and rates). Not a consensus. No consensus figures are used in this study._",
          "", f"_Machine-readable facts for the number checker: `{release}.json` ({len(facts)} facts)._"]
    (FACTS / f"{release}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (FACTS / f"{release}.json").write_text(json.dumps(dict(release=release, bundle=bundle, release_date=rel_date, facts=facts),
                                                      indent=1, default=float), encoding="utf-8")
    return release


def fomc_facts(d: pd.Timestamp) -> tuple[list[dict], list[str]]:
    hi, lo = MK.DFEDTARU.dropna(), MK.DFEDTARL.dropna()
    a_hi, a_lo = hi[hi.index > d].iloc[0], lo[lo.index > d].iloc[0]
    b_hi, b_lo = hi[hi.index <= d].iloc[-1], lo[lo.index <= d].iloc[-1]
    move = round((a_hi - b_hi) * 100)
    kw = ["Fed", "Federal Reserve", "FOMC", "target range", "policy rate", "federal funds", "fed funds", "interest rates",
          "rates", "benchmark rate", "the committee", "policymakers"]
    mon = d.strftime("%B").lower()
    facts = [fact("ff_upper", "Fed funds target range, upper bound after the meeting", a_hi, "pct", "%", "current", mon, kw, None, None, b_hi, 2),
             fact("ff_lower", "Fed funds target range, lower bound after the meeting", a_lo, "pct", "%", "current", mon, kw, None, None, b_lo, 2),
             fact("ff_upper_prev", "Fed funds target range, upper bound before", b_hi, "pct", "%", "previous", mon, kw, None, None, None, 2),
             fact("ff_lower_prev", "Fed funds target range, lower bound before", b_lo, "pct", "%", "previous", mon, kw, None, None, None, 2),
             fact("ff_move", "Change in the target range", move, "bp", " bp", "current", mon, kw, None, None, None, 0),
             fact("ff_move_pp", "Change in the target range (percentage points)", move / 100, "pp", " pp", "current", mon, kw, None, None, None, 2)]
    m = FOMC[FOMC.decision_date == d].iloc[0]
    head = [f"Decision date: **{d:%a %d %b %Y}**, statement at 14:00 ET · source: Federal Reserve (PUBLIC DATA)", "",
            "| | Before | After |", "|---|---|---|",
            f"| Target range for the federal funds rate | {b_lo:.2f}%-{b_hi:.2f}% | **{a_lo:.2f}%-{a_hi:.2f}%** |", "",
            f"- Decision: {'held' if move == 0 else ('cut' if move < 0 else 'raised')}"
            + (f" by {abs(move)} bp" if move else "") + ".",
            f"- Summary of Economic Projections at this meeting: {'yes' if m.projections else 'no'}.",
            "- Statement text, vote and press conference: read on federalreserve.gov (not reproduced here)."]
    return facts, head


def main():
    cal = calendar_rows()
    # same fields as a public economic-calendar row (format only): reference date, UTC timestamp, consensus, 1-3 importance
    et = pd.to_datetime(cal.date.astype(str) + " " + cal.time_et).dt.tz_localize("America/New_York")
    cal.insert(0, "datetime_utc", et.dt.tz_convert("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
    cal["consensus"] = None                      # no free, reliable public consensus: left empty on purpose
    cal["importance"] = cal.importance.map({"high": 3, "medium": 2, "low": 1})
    cal = cal[["datetime_utc", "date", "time_et", "country", "event", "key", "reference", "actual", "previous", "revised_previous",
               "consensus", "forecast_model", "unit", "importance", "source", "status", "note"]]
    out = CAL / "us_calendar.csv"
    cal.to_csv(out, index=False)
    print(f"Calendar         {len(cal)} rows {cal.date.min()} -> {cal.date.max()} "
          f"({(cal.status == 'released').sum()} released, {(cal.status != 'released').sum()} scheduled/pending) -> {out.name}")
    made = []
    for bundle, keys in BUNDLES.items():
        for r in releases(EV.loc[keys[0]].series):
            if not r["revision_only"] and CAL_START <= r["date"] <= str(TODAY):
                made.append(write_sheet(bundle, r["date"]))
    for d in FOMC[(FOMC.decision_date >= CAL_START) & (FOMC.decision_date <= pd.Timestamp(TODAY))].decision_date:
        made.append(write_sheet("fomc", str(d.date())))
    pd.Series(sorted(made), name="release").to_csv(OUT / "factsheets_index.csv", index=False)
    print(f"Fact sheets      {len(made)} releases -> factsheets/")


if __name__ == "__main__":
    main()
