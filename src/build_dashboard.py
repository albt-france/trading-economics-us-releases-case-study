"""Stand-alone HTML dashboard (dashboard/us_releases.html): three tabs, Plotly embedded (works offline).
Calendar = rebuilt two-month calendar; Indicators = CPI, payrolls, retail sales, GDP with revisions;
Market reactions = event study. Usage: python src/build_dashboard.py  (open ...html#1 to #3)
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CAL, COLLECTED_ON, DASH, FOOTER, OUT, PROCESSED  # noqa: E402

BLUE, BLUE_L, BLUE_D, GRAY, GRAY_D, RED, INK2 = "#2A78D6", "#86B6EF", "#1C5CAB", "#C9C7BF", "#898781", "#D03B3B", "#52514E"
LAYOUT = dict(font=dict(family="Segoe UI, sans-serif", size=12, color=INK2), paper_bgcolor="#FCFCFB",
              plot_bgcolor="#FCFCFB", margin=dict(l=10, r=10, t=44, b=10), hoverlabel=dict(font_size=12))
_first = [True]


def div(fig):
    fig.update_layout(**LAYOUT)
    inc = _first[0]
    _first[0] = False
    return pio.to_html(fig, full_html=False, include_plotlyjs=True if inc else False, config={"displayModeBar": False, "responsive": True})


def table(df, cols, cls=None):
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols.values())
    body = ""
    for _, r in df.iterrows():
        k = f' class="{cls(r)}"' if cls else ""
        body += f"<tr{k}>" + "".join(f"<td>{html.escape('' if pd.isna(r[c]) else str(r[c]))}</td>" for c in cols) + "</tr>"
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def num(v, unit, dec=1):
    if pd.isna(v):
        return ""
    if unit == "K":
        return f"{v:,.0f}K"
    if unit == "M":
        return f"{v:,.2f}M"
    if unit == "USD B":
        return f"{v:,.1f}B"
    return f"{v:.{dec}f}%"


def page_calendar():
    cal = pd.read_csv(CAL / "us_calendar.csv")
    for c in ("actual", "previous", "revised_previous", "forecast_model"):
        cal[c + "_s"] = [num(v, u, 2 if k == "fomc" else 1) for v, u, k in zip(cal[c], cal.unit, cal.key)]
    cal["when"] = pd.to_datetime(cal.date).dt.strftime("%a %d %b") + " " + cal.time_et
    imp = {3: "●●●", 2: "●●○", 1: "●○○"}
    cal["imp"] = cal.importance.map(imp)
    n_rel = int((cal.status == "released").sum())
    kp = [(f"{n_rel}", "calendar rows released, Oct 1 - Nov 17"), (f"{int((cal.status != 'released').sum())}", "scheduled or pending rows"),
          (f"{int(cal.revised_previous.notna().sum())}", "rows where the release revised the previous figure"),
          (f"{(cal.time_et == '08:30').mean():.0%}", "of rows at 08:30 ET")]
    t = table(cal, {"when": "Date (ET)", "event": "Event", "reference": "Ref.", "actual_s": "Actual", "previous_s": "Previous",
                    "revised_previous_s": "Revised", "forecast_model_s": "Model fcst*", "imp": "Imp.", "source": "Source",
                    "note": "Note"}, cls=lambda r: "up" if r.status != "released" else "")
    by = cal.groupby("time_et").size().reset_index(name="n")
    f = go.Figure(go.Bar(x=by.time_et, y=by.n, marker_color=[BLUE if t_ == "14:00" else GRAY for t_ in by.time_et], text=by.n, textposition="outside"))
    f.update_layout(height=260, title="Calendar rows by release time (ET)", yaxis_visible=False, xaxis_type="category")
    body = (f'<div class="two">{div(f)}<div class="note"><b>How to read it.</b> One row per indicator, as on an economic calendar: '
            "the figure published (<i>actual</i>), the figure readers had the day before (<i>previous</i>), the new value of that "
            "previous figure if the release changed it (<i>revised</i>) and a <b>model forecast (illustrative)</b>: the average of the "
            "last three prints for changes, the last value for levels. No consensus is shown: there is no free, reliable public source. "
            "Greyed rows are scheduled.</div></div>" + t)
    return ("Calendar", "Rebuilt U.S. economic calendar, 1 Oct - 30 Nov 2026", "PUBLIC DATA", kp, body)


def page_indicators():
    t = pd.read_csv(OUT / "trends_monthly.csv", parse_dates=["date"])
    t = t[t.date >= "2019-01-01"]
    v = pd.read_csv(PROCESSED / "vintages_recent.csv", parse_dates=["date"])
    f1 = go.Figure()
    for c, n, col in (("cpi_yoy", "CPI, headline", GRAY_D), ("core_cpi_yoy", "CPI, core", BLUE), ("core_pce_yoy", "PCE price index, core", BLUE_L)):
        f1.add_scatter(x=t.date, y=t[c], name=n, mode="lines", line=dict(color=col, width=2 if "core" in c else 1.5))
    f1.add_hline(y=2, line_dash="dot", line_color=GRAY_D, annotation_text="Fed target (PCE) 2%", annotation_position="bottom right")
    f1.update_layout(height=330, title="Inflation, % change from a year earlier", legend=dict(orientation="h", y=-0.15), yaxis_ticksuffix="%")
    f2 = go.Figure()
    f2.add_bar(x=t.date, y=t.nfp_chg, name="Monthly change (K)", marker_color=GRAY)
    f2.add_scatter(x=t.date, y=t.nfp_3m, name="3-month average", line=dict(color=BLUE))
    f2.update_layout(height=330, title="Non-farm payrolls, monthly change (thousands), 2021 onwards", legend=dict(orientation="h", y=-0.15),
                     yaxis_range=[-100, 1000], xaxis_range=["2021-01-01", t.date.max()])
    # revisions: payroll change by month, first print vs each later vintage
    p = v[v.series == "PAYEMS"].sort_values(["vintage", "date"])
    p["chg"] = p.groupby("vintage").value.diff()
    p = p.dropna()
    first = p.groupby("date").vintage.min()
    rows = []
    for d in sorted(p.date.unique())[-6:]:
        g = p[p.date == d]
        if g.vintage.min() <= "2026-08-31":
            continue
        rows.append(dict(month=pd.Timestamp(d).strftime("%b %Y"), first=g[g.vintage == first[d]].chg.iloc[0], latest=g[g.vintage == g.vintage.max()].chg.iloc[0]))
    rv = pd.DataFrame(rows)
    f3 = go.Figure()
    f3.add_bar(x=rv.month, y=rv["first"], name="As first reported", marker_color=GRAY)
    f3.add_bar(x=rv.month, y=rv.latest, name="Latest (17 Nov 2026)", marker_color=BLUE)
    f3.update_layout(height=300, title="Payroll change, first print vs latest (thousands)", barmode="group", legend=dict(orientation="h", y=-0.2))
    f4 = go.Figure()
    f4.add_scatter(x=t.date, y=t.retail_yoy, name="Retail sales, nominal", line=dict(color=BLUE))
    f4.add_scatter(x=t.date, y=t.retail_real_yoy, name="Minus CPI inflation (rough real)", line=dict(color=GRAY_D, dash="dot"))
    f4.update_layout(height=300, title="Retail sales, % change from a year earlier", legend=dict(orientation="h", y=-0.2), yaxis_ticksuffix="%",
                     xaxis_range=["2022-01-01", t.date.max()])
    g = t.dropna(subset=["gdp_q_ann"])
    f5 = go.Figure(go.Bar(x=g.date.dt.year.astype(str) + " Q" + ((g.date.dt.month - 1) // 3 + 1).astype(str), y=g.gdp_q_ann,
                          marker_color=[BLUE if x >= 0 else RED for x in g.gdp_q_ann]))
    f5.update_layout(height=300, title="Real GDP, % change at an annualized rate (BEA)", yaxis_ticksuffix="%", yaxis_range=[-10, 10])
    f6 = go.Figure()
    f6.add_scatter(x=t.date, y=t.unrate, name="Unemployment rate", line=dict(color=BLUE))
    f6.add_scatter(x=t.date, y=t.DFEDTARU, name="Fed funds target, upper bound", line=dict(color=GRAY_D, shape="hv"))
    f6.add_scatter(x=t.date, y=t.DGS2, name="2-year Treasury yield", line=dict(color=BLUE_L))
    f6.update_layout(height=300, title="Unemployment, Fed policy rate and 2-year yield (%)", legend=dict(orientation="h", y=-0.2),
                     xaxis_range=["2022-01-01", t.date.max()])
    last = t.dropna(subset=["core_cpi_yoy"]).iloc[-1]
    kp = [(f"{last.core_cpi_yoy:.1f}%" if pd.notna(last.core_cpi_yoy) else "n/a", f"core CPI YoY, {last.date:%b %Y}"),
          (f"{t.dropna(subset=['unrate']).iloc[-1].unrate:.1f}%", "unemployment rate, latest"),
          (f"{t.dropna(subset=['nfp_3m']).iloc[-1].nfp_3m:,.0f}K", "payrolls, 3-month average"),
          (f"{g.iloc[-1].gdp_q_ann:.1f}%", "real GDP, latest quarter (annualized)")]
    body = f'<div class="two">{div(f1)}{div(f2)}</div><div class="two">{div(f3)}{div(f4)}</div><div class="two">{div(f5)}{div(f6)}</div>'
    return ("Indicators", "CPI, payrolls, retail sales and GDP, with revisions", "PUBLIC DATA", kp, body)


def page_markets():
    e = pd.read_csv(OUT / "event_releases.csv", parse_dates=["release_date"])
    r = pd.read_csv(OUT / "event_regressions.csv")
    vol = pd.read_csv(OUT / "event_volatility.csv")
    figs = []
    for ind, name in (("CPI", "Core CPI surprise"), ("NFP", "Payroll surprise")):
        d = e[(e.indicator == ind) & ~e.covid].dropna(subset=["z", "y2_bp"])
        rr = r[(r.indicator == ind) & (r.market == "y2_bp")].iloc[0]
        f = go.Figure()
        f.add_scatter(x=d.z, y=d.y2_bp, mode="markers", marker=dict(color=BLUE, size=7, opacity=0.7), name="Release day",
                      text=d.ref.str[:7], hovertemplate="%{text}: surprise %{x:.2f} sd, 2y %{y:+.0f} bp<extra></extra>")
        xs = np.linspace(d.z.min(), d.z.max(), 20)
        a = d.y2_bp.mean() - rr.beta * d.z.mean()
        f.add_scatter(x=xs, y=a + rr.beta * xs, mode="lines", line=dict(color=RED), name=f"Fit: {rr.beta:+.1f} bp per sd")
        f.update_layout(height=340, title=f"{name} (sd) vs 2-year yield change on the day (bp)", legend=dict(orientation="h", y=-0.2))
        figs.append(f)
    rr = r.copy()
    rr["label"] = rr.indicator.map({"CPI": "CPI", "NFP": "Payrolls"}) + " · " + rr.market.map(
        {"y2_bp": "2y yield (bp)", "y10_bp": "10y yield (bp)", "usd_pct": "Dollar (%)", "eq_pct": "Nasdaq (%)"})
    f3 = go.Figure(go.Scatter(x=rr.beta, y=rr.label, mode="markers", marker=dict(color=BLUE, size=9),
                              error_x=dict(type="data", symmetric=False, array=rr.ci_high - rr.beta, arrayminus=rr.beta - rr.ci_low, color=BLUE_L)))
    f3.add_vline(x=0, line_color=GRAY_D)
    f3.update_layout(height=340, title="Move per 1 sd of surprise, with 95% interval", yaxis_autorange="reversed")
    v = vol[vol.market == "y2_bp"]
    f4 = go.Figure(go.Bar(x=v.group, y=v.ratio, marker_color=BLUE, text=[f"{x:.1f}x" for x in v.ratio], textposition="outside"))
    f4.update_layout(height=340, title="Average absolute 2-year yield move vs other days", yaxis_visible=False)
    c = r[(r.indicator == "CPI") & (r.market == "y2_bp")].iloc[0]
    n = r[(r.indicator == "NFP") & (r.market == "y2_bp")].iloc[0]
    kp = [(f"{len(e)}", "CPI and payroll releases since 2016"), (f"{c.beta:+.1f} bp", "2y yield per 1 sd core CPI surprise"),
          (f"{n.beta:+.1f} bp", "2y yield per 1 sd payroll surprise"), (f"{v.ratio.max():.1f}x", "largest 2y move ratio vs other days")]
    body = (f'<div class="two">{div(figs[0])}{div(figs[1])}</div><div class="two">{div(f3)}{div(f4)}</div>'
            '<div class="note"><b>Limits.</b> Daily closes, not intraday: other news the same day is in the move. The surprise is '
            "measured against a simple model (3-month average known the day before), not a market consensus, so it is noisier "
            "than a true surprise and the slopes are understated. Reference months Mar 2020 - Mar 2021 excluded.</div>")
    return ("Market reactions", "Event study: CPI and payroll surprises vs market moves on the day", "PUBLIC DATA", kp, body)


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>U.S. data releases</title><style>
:root{--bg:#F4F4F2;--card:#FCFCFB;--ink:#0B0B0B;--ink2:#52514E;--line:#E1E0D9;--blue:#1C5CAB}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:'Segoe UI',system-ui,sans-serif}
nav{display:flex;flex-wrap:wrap;gap:6px;padding:12px 16px;background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
nav .brand{font-weight:700;margin-right:12px;align-self:center}
nav button{border:1px solid var(--line);background:var(--bg);padding:7px 12px;border-radius:6px;cursor:pointer;font:inherit;color:var(--ink2)}
nav button.on{background:var(--blue);color:#fff;border-color:var(--blue)}
.page{display:none;max-width:1400px;margin:0 auto;padding:16px}.page.on{display:block}
header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}h1{font-size:21px;margin:4px 0 12px}
.tag{font-size:11px;font-weight:700;letter-spacing:.6px;color:#0E7A55;border:1px solid #8FD3B8;border-radius:4px;padding:4px 8px;white-space:nowrap}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px}.kpi b{display:block;font-size:24px;color:var(--blue)}
.kpi span{font-size:12px;color:var(--ink2)}.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:12px;margin-bottom:12px}
.note{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;font-size:13px;line-height:1.5;color:var(--ink2);margin-bottom:12px}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card);font-size:12.5px}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td:last-child{white-space:normal;min-width:220px}th{color:var(--ink2);position:sticky;top:0;background:var(--card)}tr.up td{color:#898781}
footer{text-align:center;color:#898781;font-size:12px;padding:16px}@media(max-width:600px){.two{grid-template-columns:1fr}h1{font-size:18px}}
</style></head><body><nav><span class="brand">U.S. data releases</span>{{NAV}}</nav>{{SECTIONS}}<footer>{{FOOTER}} · data collected {{DATE}} · model forecasts are illustrative, not a consensus · not investment advice</footer>
<script>
function show(n){document.querySelectorAll('.page').forEach((s,i)=>s.classList.toggle('on',i==n-1));
document.querySelectorAll('nav button').forEach((b,i)=>b.classList.toggle('on',i==n-1));
document.querySelectorAll('#p'+n+' .plotly-graph-div').forEach(d=>{if(window.Plotly)Plotly.Plots.resize(d)});}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{location.hash=b.dataset.p;show(+b.dataset.p)});
show(+(location.hash.slice(1))||1);
</script></body></html>"""


def main():
    pages = [page_calendar(), page_indicators(), page_markets()]
    nav = "".join(f'<button data-p="{i + 1}">{html.escape(p[0])}</button>' for i, p in enumerate(pages))
    secs = ""
    for i, (name, title, tag, kp, body) in enumerate(pages):
        k = "".join(f'<div class="kpi"><b>{html.escape(a)}</b><span>{html.escape(b)}</span></div>' for a, b in kp)
        secs += f'<section class="page" id="p{i + 1}"><header><h1>{html.escape(title)}</h1><span class="tag">{tag}</span></header><div class="kpis">{k}</div>{body}</section>'
    out = DASH / "us_releases.html"
    out.write_text(TEMPLATE.replace("{{NAV}}", nav).replace("{{SECTIONS}}", secs).replace("{{FOOTER}}", FOOTER)
                   .replace("{{DATE}}", COLLECTED_ON), encoding="utf-8")
    print(f"Dashboard        {out.relative_to(DASH.parent)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
