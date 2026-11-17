"""Event study (PUBLIC DATA): how the 2-year yield, the dollar and the S&P 500 moved on CPI and payroll release days,
as a function of the surprise. No public consensus is available for free, so the surprise is measured against a
simple real-time model: the average of the three previous monthly prints, as they stood the day before the release.

Outputs in data/outputs: event_releases.csv (one row per release), event_regressions.csv, event_volatility.csv,
trends_monthly.csv, cross_checks.csv. Usage: python src/event_study.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUT, PROCESSED  # noqa: E402

COVID = ("2020-03-01", "2021-03-01")       # reference months excluded from the regressions (record swings)
MK = pd.read_csv(PROCESSED / "markets_daily.csv", parse_dates=["date"]).set_index("date")
# stocks: Nasdaq Composite, because FRED serves only the last 12 months of the S&P 500
REACT = {"DGS2": ("y2_bp", "bp"), "DGS10": ("y10_bp", "bp"), "DTWEXBGS": ("usd_pct", "pct"), "NASDAQCOM": ("eq_pct", "pct")}


def daily_changes() -> pd.DataFrame:
    out = {}
    for col, (name, how) in REACT.items():
        s = MK[col].dropna()
        out[name] = s.diff() * 100 if how == "bp" else 100 * s.pct_change()
    return pd.DataFrame(out)


def release_table() -> pd.DataFrame:
    v = pd.read_csv(PROCESSED / "event_vintages.csv", parse_dates=["date"])
    rows = []
    for (ind, ref, rel), g in v.groupby(["indicator", "ref", "release_date"]):
        ref_ts = pd.Timestamp(ref)

        def s(series, role):
            return g[(g.series == series) & (g.role == role)].set_index("date").value.sort_index()

        if ind == "CPI":
            row = {}
            for name, series in (("core", "CPILFESL"), ("headline", "CPIAUCSL")):
                bef, rel_v = s(series, "before"), s(series, "release")
                mom_rel = 100 * rel_v.pct_change()
                mom_bef = 100 * bef.pct_change()
                if ref_ts not in mom_rel.index:
                    continue
                act = round(mom_rel[ref_ts], 1)                      # as published: one decimal
                model = mom_bef[mom_bef.index < ref_ts].iloc[-3:].mean()
                prev = mom_bef[mom_bef.index < ref_ts].iloc[-1]
                row.update({f"{name}_actual": act, f"{name}_model": model, f"{name}_prev": round(prev, 1),
                            f"{name}_surprise": act - model})
            rows.append(dict(indicator=ind, ref=ref, release_date=rel, **row))
        else:
            bef, rel_v = s("PAYEMS", "before"), s("PAYEMS", "release")
            chg_rel, chg_bef = rel_v.diff(), bef.diff()
            if ref_ts not in chg_rel.index:
                continue
            act = chg_rel[ref_ts]
            model = chg_bef[chg_bef.index < ref_ts].iloc[-3:].mean()
            ur_rel, ur_bef = s("UNRATE", "release"), s("UNRATE", "before")
            ur = ur_rel.get(ref_ts, np.nan)
            ur_prev = ur_bef[ur_bef.index < ref_ts].iloc[-1] if len(ur_bef[ur_bef.index < ref_ts]) else np.nan
            prev_first = chg_bef[chg_bef.index < ref_ts].iloc[-1]
            prev_rev = chg_rel[chg_rel.index < ref_ts].iloc[-1]
            rows.append(dict(indicator=ind, ref=ref, release_date=rel, nfp_actual=act, nfp_model=model, nfp_surprise=act - model,
                             nfp_prev_first=prev_first, nfp_prev_revised=prev_rev, unrate=ur, unrate_prev=ur_prev,
                             unrate_surprise=ur - ur_prev))
    t = pd.DataFrame(rows)
    t["release_date"] = pd.to_datetime(t.release_date)
    t["covid"] = t.ref.between(*COVID)
    t["surprise"] = np.where(t.indicator == "CPI", t.core_surprise, t.nfp_surprise)
    for ind in ("CPI", "NFP"):
        m = (t.indicator == ind) & ~t.covid
        t.loc[t.indicator == ind, "z"] = t.surprise / t.loc[m, "surprise"].std()
    ch = daily_changes()
    t = t.join(ch, on="release_date")
    return t


def regressions(t: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ind in ("CPI", "NFP"):
        d = t[(t.indicator == ind) & ~t.covid]
        for y in ("y2_bp", "y10_bp", "usd_pct", "eq_pct"):
            dd = d[["z", y]].dropna()
            X = sm.add_constant(dd.z)
            r = sm.OLS(dd[y], X).fit(cov_type="HC1")
            lo, hi = r.conf_int().loc["z"]
            big = dd[dd.z.abs() >= 1]
            hit = (np.sign(big.z) == np.sign(big[y])).mean() if len(big) else np.nan
            rows.append(dict(indicator=ind, market=y, n=len(dd), beta=r.params["z"], ci_low=lo, ci_high=hi, p_value=r.pvalues["z"],
                             r2=r.rsquared, n_big=len(big), same_sign_big=hit))
    return pd.DataFrame(rows)


def volatility(t: pd.DataFrame) -> pd.DataFrame:
    """Average absolute daily move on release days vs all other days (same period)."""
    ch = daily_changes().dropna(how="all")
    ch = ch[ch.index >= "2016-01-01"]
    fomc = pd.to_datetime(pd.read_csv(PROCESSED / "fomc_meetings.csv").decision_date)
    groups = {"CPI days": set(t[t.indicator == "CPI"].release_date), "Payroll days": set(t[t.indicator == "NFP"].release_date),
              "FOMC days": set(fomc)}
    allev = set().union(*groups.values())
    rows = []
    for col in ch.columns:
        base = ch.loc[~ch.index.isin(allev), col].abs().mean()
        for g, days in groups.items():
            x = ch.loc[ch.index.isin(days), col].abs()
            rows.append(dict(market=col, group=g, n=x.count(), mean_abs=x.mean(), other_days=base, ratio=x.mean() / base))
    return pd.DataFrame(rows)


def trends() -> pd.DataFrame:
    f = pd.read_csv(PROCESSED / "fred_monthly.csv", parse_dates=["date"]).pivot(index="date", columns="series", values="value")
    f = f.drop(columns=["ICSA"])                          # weekly series: not part of the monthly table
    f = f[f.index.day == 1]
    f = f.reindex(pd.date_range("2015-01-01", f.index.max(), freq="MS"))   # keep missing months (Oct 2025) as gaps
    t = pd.DataFrame(index=f.index)
    t["cpi_yoy"] = 100 * (f.CPIAUCNS / f.CPIAUCNS.shift(12) - 1)
    t["core_cpi_yoy"] = 100 * (f.CPILFENS / f.CPILFENS.shift(12) - 1)
    t["pce_yoy"] = 100 * (f.PCEPI / f.PCEPI.shift(12) - 1)
    t["core_pce_yoy"] = 100 * (f.PCEPILFE / f.PCEPILFE.shift(12) - 1)
    t["core_cpi_3m_ann"] = 100 * ((f.CPILFESL / f.CPILFESL.shift(3)) ** 4 - 1)
    t["nfp_chg"] = f.PAYEMS.diff()
    t["nfp_3m"] = t.nfp_chg.rolling(3).mean()
    t["unrate"] = f.UNRATE
    t["retail_yoy"] = 100 * (f.RSAFS / f.RSAFS.shift(12) - 1)
    t["retail_real_yoy"] = t.retail_yoy - t.cpi_yoy
    t["spending_yoy"] = 100 * (f.PCE / f.PCE.shift(12) - 1)
    t["ahe_yoy"] = 100 * (f.CES0500000003 / f.CES0500000003.shift(12) - 1)
    t["jolts"] = f.JTSJOL / 1000
    m = MK[["DFEDTARU", "DGS2", "DGS10"]].resample("MS").last()
    t = t.join(m)
    q = f.A191RL1Q225SBEA.dropna()
    t["gdp_q_ann"] = q
    return t.reset_index().rename(columns={"index": "date"})


def cross_checks() -> pd.DataFrame:
    """Same number, two official channels: BLS API vs FRED (current vintage); Treasury par yields vs FRED."""
    bls = pd.read_csv(PROCESSED / "bls_series.csv", parse_dates=["date"])
    fred = pd.read_csv(PROCESSED / "fred_monthly.csv", parse_dates=["date"])
    pairs = {"CUSR0000SA0": "CPIAUCSL", "CUUR0000SA0": "CPIAUCNS", "CUSR0000SA0L1E": "CPILFESL",
             "CES0000000001": "PAYEMS", "LNS14000000": "UNRATE", "CES0500000003": "CES0500000003", "WPSFD4": "PPIFIS"}
    rows = []
    for b, f in pairs.items():
        x = bls[bls.series_id == b].set_index("date").value
        y = fred[fred.series == f].set_index("date").value
        j = pd.concat([x, y], axis=1, keys=["bls", "fred"]).dropna()
        j = j[j.index >= "2016-01-01"]
        rows.append(dict(check=f"BLS API {b} vs FRED {f}", compared=len(j), identical=int((j.bls.round(3) == j.fred.round(3)).sum()),
                         max_abs_diff=float((j.bls - j.fred).abs().max())))
    tr = pd.read_csv(PROCESSED / "treasury_par_yields.csv", parse_dates=["date"]).set_index("date")
    for c, f in (("tsy_2y", "DGS2"), ("tsy_10y", "DGS10")):
        j = pd.concat([tr[c], MK[f]], axis=1, keys=["tsy", "fred"], sort=True).dropna()
        rows.append(dict(check=f"Treasury {c} vs FRED {f} (2025-26)", compared=len(j), identical=int((j.tsy.round(2) == j.fred.round(2)).sum()),
                         max_abs_diff=float((j.tsy - j.fred).abs().max())))
    return pd.DataFrame(rows)


def main():
    t = release_table()
    t.to_csv(OUT / "event_releases.csv", index=False)
    r = regressions(t)
    r.to_csv(OUT / "event_regressions.csv", index=False)
    v = volatility(t)
    v.to_csv(OUT / "event_volatility.csv", index=False)
    trends().to_csv(OUT / "trends_monthly.csv", index=False)
    cc = cross_checks()
    cc.to_csv(OUT / "cross_checks.csv", index=False)
    print(f"Event study      {len(t)} releases ({(t.indicator == 'CPI').sum()} CPI, {(t.indicator == 'NFP').sum()} payrolls), "
          f"{t.release_date.min():%Y-%m} -> {t.release_date.max():%Y-%m}")
    for _, x in r[r.market == "y2_bp"].iterrows():
        print(f"  {x.indicator}: 2-year yield {x.beta:+.1f} bp per 1 sd of surprise (95% CI {x.ci_low:+.1f} to {x.ci_high:+.1f}), "
              f"R2 {x.r2:.2f}, n={x.n}")
    print(f"Cross-checks     {int(cc.identical.sum())}/{int(cc.compared.sum())} values identical across official channels")


if __name__ == "__main__":
    main()
