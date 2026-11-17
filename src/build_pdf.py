"""8-page PDF report (16:9): HTML + inline SVG charts, printed by headless Edge. Every number is read from the
pipeline outputs; none is typed in the text. Usage: python src/build_pdf.py
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from jinja2 import Template

sys.path.insert(0, str(Path(__file__).resolve().parent))
import charts as C  # noqa: E402
from config import CAL, COLLECTED_ON, COMM, DOCS, FACTS, FOOTER, OUT, PROCESSED, ROOT, ai_note  # noqa: E402
from fact_check import body_of, check, check_file, load_sheet  # noqa: E402

TMP = ROOT / ".tmp"
PDF = DOCS / "TradingEconomics_US_releases_case_study.pdf"
rd = lambda n: pd.read_csv(OUT / f"{n}.csv")  # noqa: E731

CSS = """
@page { size: 16in 9in; margin: 0 }
* { box-sizing: border-box; margin: 0; padding: 0 }
body { font-family: 'Segoe UI', system-ui, sans-serif; color: #0B0B0B; background: #F4F4F2; }
.page { width: 1536px; height: 864px; padding: 30px 40px 16px; display: flex; flex-direction: column;
        background: #F4F4F2; page-break-after: always; overflow: hidden; position: relative }
header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; min-height: 56px }
h1 { font-size: 24px; font-weight: 700; line-height: 1.2; max-width: 1250px; letter-spacing: -0.2px }
.sub { color: #52514E; font-size: 13.5px; margin-top: 5px; max-width: 1270px; line-height: 1.4 }
.tag { font-size: 11.5px; font-weight: 700; letter-spacing: .8px; color: #52514E; border: 1px solid #C9C7BF;
       border-radius: 4px; padding: 4px 9px; white-space: nowrap; margin-top: 6px; background: #FCFCFB }
.tag.sim { color: #1C5CAB; border-color: #86B6EF } .tag.real { color: #0E7A55; border-color: #8FD3B8 }
.kpis { display: grid; gap: 12px; margin-bottom: 12px }
.card { background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 8px; padding: 12px 16px; display: flex;
        flex-direction: column; min-height: 0; overflow: hidden }
.kpi { padding: 11px 16px }
.klabel { font-size: 11px; font-weight: 700; color: #52514E; letter-spacing: .5px; text-transform: uppercase }
.kval { font-size: 29px; font-weight: 700; margin-top: 2px; line-height: 1.15 } .kval.blue { color: #1C5CAB } .kval.red { color: #D03B3B }
.knote { font-size: 12px; color: #52514E; margin-top: 3px; line-height: 1.35 }
.grid { display: grid; gap: 12px; flex: 1; min-height: 0 }
.card h3 { font-size: 13.5px; font-weight: 600; margin-bottom: 6px }
.ctag { font-size: 9.5px; font-weight: 700; letter-spacing: .6px; padding: 1px 5px; border-radius: 3px; margin-left: 6px; vertical-align: 1px }
.ctag.real { color: #0E7A55; border: 1px solid #8FD3B8 } .ctag.sim { color: #1C5CAB; border: 1px solid #86B6EF }
.body { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; font-size: 12.8px; line-height: 1.42 }
.body svg { width: 100%; height: 100% } .body img { max-width: 100%; max-height: 100% }
.body.text { display: block; overflow: hidden; color: #2B2A28 }
.body.text p { margin-bottom: 6px } .body.text ul { margin: 0 0 5px 17px } .body.text li { margin-bottom: 3px }
table { border-collapse: collapse; width: 100%; font-size: 11.8px }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #C9C7BF; padding: 3px 5px }
td { padding: 3px 5px; border-bottom: 1px solid #EEEDE8; vertical-align: top } td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap }
td.err { color: #B02E2E; font-weight: 600 } td.ok { color: #0E7A55; font-weight: 600 } tr.up td { color: #898781 }
footer { font-size: 10.5px; color: #898781; margin-top: 8px }
b.blue { color: #1C5CAB } b.red { color: #B02E2E }
.lab { font-weight: 700; color: #52514E; font-size: 11.5px; letter-spacing: .4px }
.flow { display: flex; gap: 7px; align-items: stretch; width: 100% }
.flow div.s { flex: 1; border: 1px solid #86B6EF; background: #EEF5FD; border-radius: 6px; padding: 7px; font-size: 12px; text-align: center }
.flow div.s b { display: block; color: #1C5CAB; margin-bottom: 3px } .flow div.a { color: #898781; font-size: 18px; align-self: center }
.flow div.s.gate { border-color: #E3A0A0; background: #FBEFEF } .flow div.s.gate b { color: #B02E2E }
.mono { font-family: Consolas, monospace; font-size: 11px; background: #F1F0EB; padding: 1px 4px; border-radius: 3px }
.ai { border-left: 3px solid #2A78D6; padding: 6px 10px; background: #EEF5FD; font-size: 12.5px; margin-top: 4px }
.q { display: grid; grid-template-columns: 22px 1fr; gap: 3px 6px; font-size: 12.8px } .q b { color: #1C5CAB }
.comm { font-size: 12.3px; line-height: 1.45 } .comm h4 { font-size: 13px; margin-bottom: 3px } .comm .meta { color: #898781; font-size: 10.5px; margin-top: 4px }
"""

PAGE = Template("""
<section class="page">
  <header><div><h1>{{ p.title }}</h1>{% if p.subtitle %}<p class="sub">{{ p.subtitle }}</p>{% endif %}</div>
  {% if p.tag %}<div class="tag {{ p.tag_class }}">{{ p.tag }}</div>{% endif %}</header>
  {% if p.kpis %}<div class="kpis" style="grid-template-columns: repeat({{ p.kpis|length }}, 1fr)">
    {% for k in p.kpis %}<div class="card kpi"><div class="klabel">{{ k[0] }}</div><div class="kval {{ k[3] if k|length > 3 else '' }}">{{ k[1] }}</div><div class="knote">{{ k[2] }}</div></div>{% endfor %}
  </div>{% endif %}
  <div class="grid" style="grid-template-columns: {{ p.cols }}; grid-template-rows: {{ p.rows }}">
    {% for c in p.cards %}<div class="card" style="grid-column: {{ c.col }}; grid-row: {{ c.row }}">
      {% if c.title %}<h3>{{ c.title }}{% if c.tag %}<span class="ctag {{ 'sim' if c.tag == 'SIMULATED' else 'real' }}">{{ c.tag }}</span>{% endif %}</h3>{% endif %}<div class="body {{ 'text' if c.text else '' }}">{{ c.body }}</div></div>{% endfor %}
  </div>
  <footer>{{ p.footer }} · {{ foot }}</footer>
</section>""")


COMMENTARY_NOTE = ("All market commentaries in this repository were written by me; scripts only prepared the fact sheets and "
                   "checked the numbers.")


def comm_note_ok(comm) -> bool:
    """The authorship sentence is printed only once it is true: the README carries it (added by the author)."""
    return COMMENTARY_NOTE in (ROOT / "README.md").read_text(encoding="utf-8") and len(comm) > 0


def card(title, body, col="auto", row="auto", text=False, tag=None):
    return dict(title=title, body=body, col=col, row=row, text=text, tag=tag)


def flow(steps, gates=()):
    return '<div class="flow">' + '<div class="a">→</div>'.join(
        f'<div class="s{" gate" if a in gates else ""}"><b>{a}</b>{b}</div>' for a, b in steps) + "</div>"


def esc(s) -> str:
    return html.escape(str(s))


def commentaries() -> list[dict]:
    """The commentaries written for this study (commentary/*.md), with their checker result and word count."""
    out = []
    for p in sorted(COMM.glob("*.md")):
        if not (FACTS / f"{p.stem}.json").exists():
            continue
        md = p.read_text(encoding="utf-8")
        body = body_of(md).strip()
        lines = [ln for ln in body.splitlines() if ln.strip()]
        rep = check_file(p)
        out.append(dict(release=p.stem, headline=lines[0], text=" ".join(lines[1:]), words=len(re.findall(r"\S+", " ".join(lines))),
                        numbers=len(rep.findings), passed=rep.passed))
    return out


def trap_results() -> tuple[pd.DataFrame, pd.DataFrame]:
    tr = pd.read_csv(ROOT / "data" / "_traps.csv")
    rows = []
    for _, r in tr.iterrows():
        rep = check(r.text, load_sheet(r.release))
        if r.expected == "pass":
            ok = rep.passed
            found = "pass" if rep.passed else ",".join(sorted({f.error for f in rep.errors()}))
        else:
            ok = (not rep.passed) and r.expected in {f.error for f in rep.errors()}
            found = ",".join(sorted({f.error for f in rep.errors()})) or "pass"
        msg = next((f.message for f in rep.errors()), "")
        rows.append(dict(trap_id=r.trap_id, type=r.trap_type, text=r.text, expected=r.expected, found=found, ok=ok, message=msg))
    d = pd.DataFrame(rows)
    names = {"mom_yoy": "month vs year", "revision": "forgotten revision", "sa_nsa": "SA vs NSA", "sign": "sign",
             "unit": "units (K vs M)", "wrong_period": "reference month", "direction": "verb vs direction",
             "not_in_factsheet": "number not in sheet", "control": "control (correct text)"}
    s = d.groupby("type").agg(ok=("ok", "sum"), total=("ok", "size")).reset_index()
    s["type"] = s.type.map(names)
    order = list(names.values())
    s["o"] = s.type.map(order.index)
    return d, s.sort_values("o").drop(columns="o")


def build_pages():
    cal = pd.read_csv(CAL / "us_calendar.csv")
    rel = cal[cal.status == "released"]
    ev, reg, vol, tr, cc = rd("event_releases"), rd("event_regressions"), rd("event_volatility"), rd("trends_monthly"), rd("cross_checks")
    tr["date"] = pd.to_datetime(tr.date)
    traps, trap_sum = trap_results()
    n_traps = int((traps.expected != "pass").sum())
    caught = int(traps[traps.expected != "pass"].ok.sum())
    ctrl_ok = int(traps[traps.expected == "pass"].ok.sum())
    n_ctrl = int((traps.expected == "pass").sum())
    R = lambda ind, m: reg[(reg.indicator == ind) & (reg.market == m)].iloc[0]  # noqa: E731
    c2, n2 = R("CPI", "y2_bp"), R("NFP", "y2_bp")
    V = lambda g, m: vol[(vol.group == g) & (vol.market == m)].iloc[0]  # noqa: E731
    share_830 = (cal.time_et == "08:30").mean()
    n_rev = int(rel.revised_previous.notna().sum())
    comm = commentaries()
    n_comm = len(comm)
    sheets = len(list(FACTS.glob("*.json")))
    pages = []
    foot_src = "Sources: BLS, BEA, Census, Federal Reserve, U.S. Treasury, FRED/ALFRED (St. Louis Fed)"

    # 0 Overview ----------------------------------------------------------------------------------------------
    qs = [("1", "What does the job ask for, and when do U.S. releases land?"),
          ("2", "Can a calendar row be rebuilt from official data, with the previous figure and its revision?"),
          ("3", "Can a script catch the classic number mistakes before a commentary is published?"),
          ("4", "How do the 2-year yield, the dollar and stocks react to CPI and payroll surprises?"),
          ("5", "What does the latest U.S. data say about inflation, jobs and spending?")]
    pages.append(dict(
        title="Trading Economics: covering U.S. data releases fast, clearly and accurately",
        subtitle="Official BLS, BEA, Census and Fed data turned into a release-day workflow, a rebuilt economic calendar, short market "
                 "commentaries with automatic fact-checking, and an event study of how markets react to surprises.",
        tag="PUBLIC DATA + SIMULATED TESTS", tag_class="real",
        kpis=[("Calendar rows rebuilt", f"{len(rel)}", f"released 1 Oct - 17 Nov 2026, {n_rev} with a revised previous figure", "blue"),
              ("Traps caught", f"{caught}/{n_traps}", f"SIMULATED number errors; {ctrl_ok}/{n_ctrl} correct sentences passed", "blue"),
              ("2-year yield per 1 sd", f"{c2.beta:+.1f} bp", f"core CPI surprise; payrolls {n2.beta:+.1f} bp (daily, 2016-2026)", "blue"),
              ("Commentaries", f"{n_comm}", f"real releases, 60-120 words, every number verified; {sheets} fact sheets", "blue")],
        cols="1fr 1fr 1fr", rows="0.7fr 1fr",
        cards=[card("Five questions", '<div class="q">' + "".join(f"<b>{a}</b><span>{esc(b)}</span>" for a, b in qs) + "</div>"
                    "<p style='margin-top:12px' class='lab'>DELIVERABLES</p><ul>"
                    f"<li>Rebuilt calendar: {len(cal)} rows, 1 Oct - 30 Nov 2026 (<span class='mono'>calendar/</span>)</li>"
                    f"<li>{sheets} fact sheets and {n_comm} commentaries (<span class='mono'>factsheets/</span>, <span class='mono'>commentary/</span>)</li>"
                    "<li>Number checker with tests; style guide; release-day playbook</li>"
                    "<li>Event study notebook; offline dashboard (3 tabs)</li></ul>",
                    "1", "1 / 3", text=True),
               card("Approach: the job, done on real releases", flow([
                   ("Prepare", "fact sheet: previous, trend, model forecast, what markets watch"),
                   ("Publish", "calendar row + short commentary"),
                   ("Verify", "every number checked against the source"),
                   ("Explain", "market reaction, with evidence")], gates=("Verify",)), "2 / 4", "1"),
               card("Methods", "<ul>"
                    f"<li><b>Release dates and first prints</b> from ALFRED vintages: the data as it stood the day before and on the day.</li>"
                    f"<li><b>No invented consensus</b>: comparisons with the previous (revised) figure, the trend and a <b>model forecast "
                    f"(illustrative)</b>.</li><li><b>Checker</b>: subject, measure, basis, period, sign and unit of each number.</li>"
                    f"<li><b>Event study</b>: {len(ev)} CPI and payroll releases, daily closes, OLS with robust errors.</li></ul>",
                    "2", "2", text=True),
               card("Answers in one line", "<ul>"
                    f"<li>{share_830:.0%} of calendar rows land at 08:30 ET; the 14:00 slot is the Fed's.</li>"
                    f"<li>{n_rev} of {len(rel)} released rows revised the previous figure: the 'previous' column needs care.</li>"
                    f"<li>The checker caught {caught}/{n_traps} traps and passed {ctrl_ok}/{n_ctrl} correct sentences.</li>"
                    f"<li>A 1 sd core CPI surprise moved the 2-year yield by {c2.beta:+.1f} bp on the day; payrolls {n2.beta:+.1f} bp.</li></ul>",
                    "3", "2", text=True)],
        footer=foot_src))

    # 1 Trading Economics and the job -------------------------------------------------------------------------
    pages.append(dict(
        title=f"The job is a deadline job: {share_830:.0%} of U.S. calendar rows land at 08:30 ET, the Fed decides at 14:00",
        subtitle="What Trading Economics says about itself, what the role asks for, and the rhythm of U.S. releases in the rebuilt calendar.",
        tag="PUBLIC DATA", tag_class="real",
        kpis=[("Countries covered", "196", "as stated by Trading Economics (About page)"),
              ("Indicators", "20M+", "more than 20 million, as stated by Trading Economics"),
              ("Page views", "~2 billion", "'nearly' (About) / 'more than' (Careers), as stated by Trading Economics"),
              ("Rows in 2 months", f"{len(cal)}", f"{cal.event.nunique()} U.S. indicators tracked, 1 Oct - 30 Nov 2026")],
        cols="1fr 1.25fr 1.1fr", rows="1fr 1fr",
        cards=[card("What the role asks for (careers page, paraphrased)", "<ul>"
                    "<li>Short, clear commentary on major releases: inflation, jobs, GDP, retail sales.</li>"
                    "<li>Market reactions across FX, equities, rates and commodities.</li>"
                    "<li>Update the economic calendar right after publication: actual, forecasts, short notes.</li>"
                    "<li>Follow macro and central-bank news; summarise fast; spot trends.</li>"
                    "<li>Availability 14:00-19:00 EST; speed and accuracy under time pressure.</li></ul>"
                    "<p class='lab' style='margin-top:8px'>THE MONTHLY RHYTHM (2026 CALENDAR)</p><ul>"
                    "<li>Jobs report: first Friday, 08:30. CPI: around the 10th-15th, 08:30.</li>"
                    "<li>Retail sales, PPI, industrial production: mid-month.</li>"
                    "<li>GDP and PCE: end of month, 08:30. Jobless claims: every Thursday.</li>"
                    "<li>FOMC: eight meetings a year, statement at 14:00.</li></ul>"
                    "<p>Trading Economics states that its indicator data come from official sources rather than third-party "
                    "providers; this study uses the same kind of sources.</p>", "1", "1 / 3", text=True),
               card("When releases land: calendar rows by time (ET)", C.release_clock(cal), "2", "1", tag="PUBLIC DATA"),
               card("Weekly load: rows per week in the rebuilt calendar", C.weekly_load(cal), "2", "2", tag="PUBLIC DATA"),
               card("A calendar row, field by field", "<table><tr><th>Field</th><th>In this study</th></tr>"
                    "<tr><td>Date, time</td><td>official schedule (BEA, Census, BLS, Fed); UTC and ET</td></tr>"
                    "<tr><td>Actual</td><td>first print, from the vintage published that day</td></tr>"
                    "<tr><td>Previous</td><td>value readers had the day before</td></tr>"
                    "<tr><td>Revised</td><td>new value of 'previous' if the release changed it</td></tr>"
                    "<tr><td>Consensus</td><td>left empty: no free public source</td></tr>"
                    "<tr><td>Forecast</td><td>model forecast (illustrative)</td></tr>"
                    "<tr><td>Importance, note</td><td>1-3; short factual note</td></tr></table>", "3", "1", text=True),
               card("What the 14:00-19:00 window covers", "<ul>"
                    "<li>FOMC statements (14:00 ET) and the Fed Chair's press conference (14:30).</li>"
                    "<li>The U.S. equity close (16:00 ET) and the day's market wrap.</li>"
                    "<li>Calendar upkeep: revisions, next-day previews, late releases.</li>"
                    f"<li>Morning releases (08:30) are where speed matters most: {share_830:.0%} of rows.</li></ul>",
                    "3", "2", text=True)],
        footer="Sources: Trading Economics About, Careers and API documentation pages (read by hand, 17 Nov 2026); BEA, Census, BLS, Fed schedules"))

    # 2 From release to calendar row --------------------------------------------------------------------------
    v = pd.read_csv(PROCESSED / "vintages_recent.csv", parse_dates=["date"])
    p = v[v.series == "PAYEMS"].sort_values(["vintage", "date"])
    p["chg"] = p.groupby("vintage").value.diff()
    p = p.dropna()
    rv = []
    for d in sorted(p.date.unique()):
        g = p[p.date == d]
        if g.vintage.min() <= "2026-08-31":
            continue
        rv.append(dict(month=pd.Timestamp(d).strftime("%b %Y"), first=g[g.vintage == g.vintage.min()].chg.iloc[0],
                       latest=g[g.vintage == g.vintage.max()].chg.iloc[0]))
    rv = pd.DataFrame(rv)
    ex = rel[rel.key.isin(["nfp", "unrate", "cpi_mom", "core_cpi_mom", "retail_mom", "gdp", "core_pce_mom", "jolts", "fomc"])].copy()
    ex = ex.drop_duplicates("key", keep="last")

    def f_(x, u, k):
        if pd.isna(x):
            return "-"
        return f"{x:,.0f}K" if u == "K" else f"{x:.2f}M" if u == "M" else f"{x:.2f}%" if k == "fomc" else f"{x:.1f}%"
    rows = "".join(f"<tr><td>{pd.Timestamp(r.date):%d %b}</td><td>{esc(r.event)}</td><td>{esc(r.reference)}</td>"
                   f"<td class='n'><b>{f_(r.actual, r.unit, r.key)}</b></td><td class='n'>{f_(r.previous, r.unit, r.key)}</td>"
                   f"<td class='n'>{f_(r.revised_previous, r.unit, r.key)}</td><td class='n'>{f_(r.forecast_model, r.unit, r.key)}</td></tr>"
                   for _, r in ex.sort_values("date").iterrows())
    cct = "".join(f"<tr><td>{esc(r.check)}</td><td class='n'>{r.identical:,}/{r.compared:,}</td><td class='n'>{r.max_abs_diff:.3g}</td></tr>"
                  for _, r in cc.iterrows())
    pages.append(dict(
        title=f"From official release to calendar row: {n_rev} of {len(rel)} rows had to show a revised previous figure",
        subtitle="Each release is read from the vintage published that day (ALFRED), so 'actual' is the first print and 'previous' "
                 "is what readers saw the day before. Fact sheets are built from the same tables.",
        tag="PUBLIC DATA", tag_class="real",
        cols="1.25fr 1fr", rows="auto 1fr 1fr",
        cards=[card("Pipeline", flow([("Official sources", "BLS API, ALFRED/FRED vintages, Treasury, Fed, BEA and Census schedules"),
                                      ("Vintages", "data as of the day before and the day of release"),
                                      ("Calendar row", "actual, previous, revised, model forecast, note"),
                                      ("Fact sheet", "components, trend, what markets watch, markets on the day"),
                                      ("Checker", "every number of the text vs the sheet")], gates=("Checker",)), "1 / 3", "1"),
               card("Latest release of each headline indicator in the rebuilt calendar (excerpt)",
                    "<table><tr><th>Date</th><th>Event</th><th>Ref.</th><th class='n'>Actual</th><th class='n'>Previous</th>"
                    f"<th class='n'>Revised</th><th class='n'>Model fcst</th></tr>{rows}</table>"
                    "<p style='margin-top:6px;color:#52514E'>Full calendar: <span class='mono'>calendar/us_calendar.csv</span> "
                    f"({len(cal)} rows). Oct 2026 CPI year-on-year is left empty: the Oct 2025 index was never published.</p>"
                    "<p class='lab' style='margin-top:10px'>NEXT ROWS (SCHEDULED AFTER 17 NOV; PREVIOUS AND MODEL FILLED IN ADVANCE)</p>"
                    "<table><tr><th>Date</th><th>Time</th><th>Event</th><th>Ref.</th><th class='n'>Previous</th><th class='n'>Model fcst</th></tr>"
                    + "".join(f"<tr class='up'><td>{pd.Timestamp(r.date):%d %b}</td><td>{r.time_et}</td><td>{esc(r.event)}</td><td>{esc(r.reference)}</td>"
                              f"<td class='n'>{f_(r.previous, r.unit, r.key)}</td><td class='n'>{f_(r.forecast_model, r.unit, r.key)}</td></tr>"
                              for _, r in cal[cal.status == "scheduled"].drop_duplicates("key").head(7).iterrows()) + "</table>",
                    "1", "2 / 4", text=True, tag="PUBLIC DATA"),
               card("Payroll change by month: first print vs latest (thousands)", C.first_vs_latest(rv), "2", "2", tag="PUBLIC DATA"),
               card("Same number, two official channels", "<table><tr><th>Check</th><th class='n'>Identical</th><th class='n'>Max diff.</th></tr>"
                    f"{cct}</table>", "2", "3", text=True, tag="PUBLIC DATA")],
        footer="Sources: ALFRED and FRED (St. Louis Fed), BLS API, U.S. Treasury, BEA and Census release schedules"))

    # 3 Writing fast without wrong numbers --------------------------------------------------------------------
    ex_trap = traps[traps.trap_id == "T03"].iloc[0]
    trows = "".join(f"<tr><td>{esc(r.trap_id)}</td><td>{esc(r.text)}</td><td class='{'ok' if r.ok else 'err'}'>{esc(r.found)}</td></tr>"
                    for _, r in traps[traps.expected != "pass"].iterrows())
    pages.append(dict(
        title=f"Writing fast without getting numbers wrong: the checker caught {caught} of {n_traps} planted errors",
        subtitle="A style guide keeps texts short and exact; a checker reads every number of a commentary and rejects it unless the "
                 "fact sheet confirms the subject, measure, seasonal basis, period, sign and unit.",
        tag="SIMULATED ERRORS · PUBLIC FACT SHEETS", tag_class="sim",
        cols="1fr 1.1fr 1.15fr", rows="1fr 1fr",
        cards=[card("Style guide in seven rules", "<ol style='margin-left:17px'>"
                    "<li>Headline = the fact: indicator, direction, number, period.</li>"
                    "<li>Number first, then the comparison (previous, revised; model; trend).</li>"
                    "<li>One idea per sentence.</li><li>Exact verbs: rose, fell, eased, beat, missed, revised.</li>"
                    "<li>Say MoM or YoY every time; say NSA when it is not the default.</li>"
                    "<li>Units: thousands for jobs, bp for yield changes, % for prices.</li>"
                    "<li>No consensus we cannot source; no investment advice.</li></ol>"
                    "<p style='margin-top:6px'>Full guide: <span class='mono'>docs/STYLE_GUIDE.md</span>; release-day steps and a one-minute "
                    "checklist: <span class='mono'>docs/RELEASE_DAY_PLAYBOOK.md</span>.</p>", "1", "1", text=True),
               card("How the checker works", "<div style='width:100%'>" + flow([("Extract", "each number with its unit"),
                                                   ("Read the sentence", "subject, MoM/YoY, SA/NSA, month, verb"),
                                                   ("Match", "fact sheet value at the same rounding"),
                                                   ("Diagnose", "name the trap, give the right figure")], gates=("Diagnose",)) +
                    f"<p style='margin-top:10px;font-size:12px'><b>Example (trap {ex_trap.trap_id}).</b> “{esc(ex_trap.text)}”<br>"
                    f"<span class='mono'>{esc(ex_trap.found)}</span> {esc(ex_trap.message)}</p></div>", "2", "1"),
               card("Result by trap type", C.traps_bars(trap_sum), "1", "2", tag="SIMULATED"),
               card(f"The {n_traps} planted errors (data/_traps.csv) and what the checker said",
                    f"<table><tr><th>#</th><th>Text</th><th>Flag</th></tr>{trows}</table>", "3", "1 / 3", text=True, tag="SIMULATED"),
               card("Timing targets for a release (SIMULATED training scenario)", "<table><tr><th>Step</th><th class='n'>Target</th></tr>"
                    "<tr><td>Headline number read from the official release</td><td class='n'>T+1 min</td></tr>"
                    "<tr><td>Calendar row updated (actual, previous revised, note)</td><td class='n'>T+2 min</td></tr>"
                    "<tr><td>Commentary drafted from the fact sheet frame</td><td class='n'>T+6 min</td></tr>"
                    "<tr><td>Checker run, flags fixed</td><td class='n'>T+8 min</td></tr>"
                    "<tr><td>Published</td><td class='n'>T+10 min</td></tr></table>"
                    "<p style='margin-top:6px;color:#52514E'>Rehearsal evening: three releases at 08:30, one at 10:00, FOMC at 14:00. "
                    "Targets show the method; no timing result is claimed.</p>", "2", "2", text=True, tag="SIMULATED")],
        footer="Checker: src/fact_check.py, tested with pytest on every trap and on correct control sentences"))

    # 4 Commentaries --------------------------------------------------------------------------------------------
    pick_order = ["cpi", "jobs", "fomc", "gdp", "retail", "pce", "ppi", "jolts", "indpro", "claims"]
    chosen = sorted(comm, key=lambda c: (pick_order.index(c["release"].split("_")[1]) if c["release"].split("_")[1] in pick_order else 99,
                                         c["release"]))
    seen, six = set(), []
    for c in chosen:
        b = c["release"].split("_")[1]
        if b not in seen:
            six.append(c)
            seen.add(b)
        if len(six) == 6:
            break
    if not six:
        cards = [card("Commentaries", "<p>The commentaries are being written; this page is generated from <span class='mono'>commentary/</span>.</p>",
                      "1 / 4", "1 / 3", text=True)]
    else:
        cards = []
        for i, c in enumerate(six):
            d = pd.Timestamp(c["release"][:10])
            cards.append(card(None, f"<div class='comm'><h4>{esc(c['headline'])}</h4><p>{esc(c['text'])}</p>"
                                    f"<div class='meta'>{d:%d %b %Y} · {c['words']} words · {c['numbers']} numbers checked: "
                                    f"{'all verified' if c['passed'] else 'FLAGGED'} · fact sheet <span class='mono'>{c['release']}</span></div></div>",
                              str(i % 3 + 1), str(i // 3 + 1), text=True))
    n_pass = sum(c["passed"] for c in comm)
    avg_w = sum(c["words"] for c in comm) / n_comm if n_comm else 0
    pages.append(dict(
        title=f"{len(six)} of the {n_comm} commentaries: real releases, number first, every figure checked",
        subtitle=("Written for this study from the fact sheets" if comm_note_ok(comm) else
                  "Trial drafts prepared with the AI-assisted workflow (see Methods), to be reviewed and rewritten by the author")
                 + f"; {n_pass}/{n_comm} pass the checker; average {avg_w:.0f} words. "
                 "Market moves are daily closes on the release day. All texts: commentary/.",
        tag="PUBLIC DATA", tag_class="real", cols="1fr 1fr 1fr", rows="1fr 1fr", cards=cards,
        footer="Sources: fact sheets built from BLS, BEA, Census, Fed and FRED data; markets: FRED daily series"))

    # 5 Event study ---------------------------------------------------------------------------------------------
    e = ev.copy()
    e = e[~e.covid]
    rr = reg.copy()
    rr["label"] = rr.indicator.map({"CPI": "CPI", "NFP": "Payrolls"}) + " · " + rr.market.map(
        {"y2_bp": "2y yield", "y10_bp": "10y yield", "usd_pct": "dollar", "eq_pct": "Nasdaq"})
    vv = vol[vol.market.isin(["y2_bp", "eq_pct"])]
    pages.append(dict(
        title=f"Surprises move short-term rates most: {c2.beta:+.1f} bp on the 2-year yield per 1 sd of core CPI surprise",
        subtitle=f"{len(ev)} CPI and payroll releases since 2016. Surprise = first print minus a real-time model forecast (3-month average known "
                 "the day before), in standard deviations. Daily close-to-close moves; Mar 2020 - Mar 2021 excluded.",
        tag="PUBLIC DATA", tag_class="real",
        kpis=[("Core CPI → 2y yield", f"{c2.beta:+.1f} bp", f"95% CI {c2.ci_low:+.1f} to {c2.ci_high:+.1f}; R² {c2.r2:.2f}; n={int(c2.n)}", "blue"),
              ("Payrolls → 2y yield", f"{n2.beta:+.1f} bp", f"95% CI {n2.ci_low:+.1f} to {n2.ci_high:+.1f}; R² {n2.r2:.2f}; n={int(n2.n)}", "blue"),
              ("CPI days vs other days", f"{V('CPI days', 'y2_bp').ratio:.1f}x", "average absolute 2y yield move", "blue"),
              ("Same direction, |z| ≥ 1", f"{c2.same_sign_big:.0%}", f"of big CPI surprises moved the 2y yield the same way (n={int(c2.n_big)})", "blue")],
        cols="1fr 1fr 1.05fr", rows="1fr 1fr",
        cards=[card("Core CPI surprise (sd) vs 2-year yield (bp)", C.surprise_scatter(e[e.indicator == "CPI"].dropna(subset=["z", "y2_bp"]), c2.beta,
                                                                                     xlabel="core CPI surprise vs model (sd)"), "1", "1 / 3", tag="PUBLIC DATA"),
               card("Payroll surprise (sd) vs 2-year yield (bp)", C.surprise_scatter(e[e.indicator == "NFP"].dropna(subset=["z", "y2_bp"]), n2.beta,
                                                                                     xlabel="payroll surprise vs model (sd)"), "2", "1 / 3", tag="PUBLIC DATA"),
               card("Move per 1 sd of surprise, 95% interval", C.coef_plot(rr), "3", "1", tag="PUBLIC DATA"),
               card("Limits", "<ul><li><b>Daily data</b>: other news of the day is in the move; intraday data would isolate the minute after 08:30.</li>"
                    "<li><b>No true consensus</b>: the model surprise is noisier than a market surprise, so slopes are understated.</li>"
                    "<li>Dollar index: noon New York rates; yields: end of day; stocks: Nasdaq Composite close (FRED serves only 12 months of S&amp;P 500).</li>"
                    "<li>Correlation on the day, not proof of cause.</li></ul>", "3", "2", text=True)],
        footer="Sources: ALFRED vintages (BLS CPI and payrolls), FRED daily series (Treasury yields, Fed broad dollar index, Nasdaq Composite); notebook: notebooks/event_study.ipynb"))

    # 6 Latest data ---------------------------------------------------------------------------------------------
    last = lambda c: tr.dropna(subset=[c]).iloc[-1]  # noqa: E731
    lc, lpce, lu, ln = last("cpi_yoy"), last("core_pce_yoy"), last("unrate"), last("nfp_3m")
    lr = last("retail_yoy")
    lff = last("DFEDTARU")
    pages.append(dict(
        title=f"Latest data: CPI inflation at {lc.cpi_yoy:.1f}% ({lc.date:%b %Y}) stays above the Fed's 2% goal; payrolls average {ln.nfp_3m:,.0f}K a month",
        subtitle="Trends behind the releases of autumn 2026. Year-on-year rates use not-seasonally-adjusted indexes (BLS and BEA convention for "
                 "CPI; PCE indexes are seasonally adjusted).",
        tag="PUBLIC DATA", tag_class="real",
        kpis=[("CPI, YoY", f"{lc.cpi_yoy:.1f}%", f"{lc.date:%b %Y}; core {lc.core_cpi_yoy:.1f}%"),
              ("Core PCE, YoY", f"{lpce.core_pce_yoy:.1f}%", f"{lpce.date:%b %Y}; Fed goal: 2% (headline PCE)"),
              ("Payrolls, 3-month avg", f"{ln.nfp_3m:,.0f}K", f"to {ln.date:%b %Y}; unemployment {lu.unrate:.1f}%"),
              ("Fed funds, upper bound", f"{lff.DFEDTARU:.2f}%", f"held on 28 Oct 2026; retail sales {lr.retail_yoy:+.1f}% YoY ({lr.date:%b %Y})")],
        cols="1fr 1fr", rows="1fr 1fr",
        cards=[card("Inflation, % from a year earlier", C.lines(tr, [("cpi_yoy", "CPI", C.GRAY_D, 1.5, "-"), ("core_cpi_yoy", "core CPI", C.BLUE, 2, "-"),
                                                                     ("core_pce_yoy", "core PCE", C.BLUE_L, 2, "-")], ref=2, ref_label="2%"), "1", "1", tag="PUBLIC DATA"),
               card("Payrolls, monthly change and 3-month average (thousands)", C.payroll_bars(tr), "2", "1", tag="PUBLIC DATA"),
               card("Retail sales, % from a year earlier: nominal vs minus CPI inflation", C.lines(tr, [("retail_yoy", "nominal", C.BLUE, 2, "-"),
                                                                                                      ("retail_real_yoy", "minus CPI", C.GRAY_D, 1.5, "--")],
                                                                                                start="2022-01-01", ref=0, ref_label=""), "1", "2", tag="PUBLIC DATA"),
               card("Fed policy rate, 2-year yield and unemployment rate (%)", C.lines(tr, [("DFEDTARU", "fed funds (upper)", C.GRAY_D, 1.8, "-"),
                                                                                       ("DGS2", "2-year yield", C.BLUE, 1.8, "-"),
                                                                                       ("unrate", "unemployment", C.BLUE_L, 1.8, "-")],
                                                                                   start="2022-01-01"), "2", "2", tag="PUBLIC DATA")],
        footer="Sources: BLS (CPI, payrolls, unemployment), BEA (PCE), Census (retail sales), Federal Reserve and U.S. Treasury via FRED"))

    # 7 Methods, limits, AI note ----------------------------------------------------------------------------------
    note = ai_note()
    pages.append(dict(
        title="Methods, limits and AI note",
        subtitle="Public data only; simulated parts are labelled; nothing here is investment advice.",
        tag="METHODS", tag_class="",
        cols="1.15fr 1fr 1fr", rows="1fr 1fr auto",
        cards=[card("Sources and licences", "<table><tr><th>Source</th><th>Used for</th></tr>"
                    "<tr><td>BLS Public Data API</td><td>CPI, jobs, earnings, PPI (public domain)</td></tr>"
                    "<tr><td>ALFRED / FRED (St. Louis Fed)</td><td>vintages, first prints, revisions; daily markets</td></tr>"
                    "<tr><td>BEA, Census (via FRED/ALFRED)</td><td>GDP, PCE, retail sales, housing, trade</td></tr>"
                    "<tr><td>Federal Reserve</td><td>FOMC dates; target range; dollar index</td></tr>"
                    "<tr><td>U.S. Treasury</td><td>par yields, cross-check of FRED</td></tr>"
                    "<tr><td>BEA, Census, BLS schedules</td><td>release dates and times</td></tr>"
                    "<tr><td>Trading Economics pages</td><td>company facts as stated; calendar field list. No data or text copied.</td></tr></table>"
                    f"<p style='margin-top:6px'>Collected {COLLECTED_ON}; one request at a time, neutral client name, answers cached. "
                    "Detail: <span class='mono'>data/SOURCES.md</span>.</p>", "1", "1 / 3", text=True),
               card("Method choices", "<ul><li><b>Model forecast (illustrative)</b>: average of the last three changes, or the last level, "
                    "computed only from data public the day before.</li><li><b>Surprise</b> = first print minus that model, divided by its "
                    "standard deviation over 2016-2026.</li><li><b>Regression</b>: OLS of the daily move on the surprise, HC1 robust errors, "
                    "95% intervals.</li><li><b>Rounding</b> as published (CPI one decimal); percentage changes computed from published index "
                    "levels.</li><li><b>SIMULATED</b>: the planted errors and the timing scenario only.</li></ul>", "2", "1", text=True),
               card("Limits", "<ul><li>Daily closes, no intraday data: other news of the day is mixed in.</li>"
                    "<li>No free consensus: surprises vs a simple model, not vs expectations.</li>"
                    "<li>Oct 2025 CPI never published (2025 lapse in appropriations): Oct 2026 YoY CPI left empty.</li>"
                    "<li>Census and BEA data read from FRED copies (Census API now needs a key).</li>"
                    "<li>Retail sales for Oct 2026 were not yet in the archive on the collection day.</li>"
                    "<li><b>Not investment advice.</b></li></ul>", "3", "1", text=True),
               card("Reproduce", "<p>No key needed (optional free keys go in a local <span class='mono'>.env</span>).</p><p>"
                    + "<br>".join(f"<span class='mono'>{c}</span>" for c in ("python src/fetch_releases.py", "python src/build_factsheets.py", "pytest",
                                                                             "python src/event_study.py", "python src/make_notebook.py",
                                                                             "python src/build_dashboard.py", "python src/build_pdf.py",
                                                                             "python src/fact_check.py commentary/&lt;release&gt;.md"))
                    + "</p>", "2", "2", text=True),
               card("Checks run on the numbers", "<ul>"
                    f"<li>{int(cc.identical.sum()):,}/{int(cc.compared.sum()):,} values identical between the BLS API and FRED, and between Treasury and FRED yields.</li>"
                    "<li>Release dates found in ALFRED match the BLS, BEA and Census schedules for Oct-Nov 2026.</li>"
                    f"<li>Checker: {caught}/{n_traps} planted errors caught, {ctrl_ok}/{n_ctrl} correct sentences passed (pytest).</li>"
                    f"<li>Commentaries: {sum(c['passed'] for c in comm)}/{n_comm} pass the checker.</li></ul>", "3", "2", text=True),
               card("AI note", f'<div class="ai">AI-assisted workflow: {esc(note)}' + (f"<br>{esc(COMMENTARY_NOTE)}" if comm_note_ok(comm) else "")
                    + "</div>", "1 / 4", "3", text=True)],
        footer="Reproduce: python src/fetch_releases.py · build_factsheets.py · pytest · event_study.py · build_dashboard.py · build_pdf.py"))
    return pages


def edge() -> str:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if Path(p).exists():
            return p
    return shutil.which("msedge") or "msedge"


def wait_file(path: Path, timeout=120):
    last, t0 = -1, time.time()
    while time.time() - t0 < timeout:
        if path.exists() and path.stat().st_size > 0 and path.stat().st_size == last:
            return
        last = path.stat().st_size if path.exists() else -1
        time.sleep(1.5)
    raise TimeoutError(f"{path} not produced")


def clean_pdf(path: Path):
    """Metadata reduced to the title: no author, tool or path."""
    from pypdf import PdfReader, PdfWriter
    r, w = PdfReader(str(path)), PdfWriter()
    for pg in r.pages:
        w.add_page(pg)
    w.add_metadata({"/Title": "Trading Economics: covering U.S. data releases fast, clearly and accurately"})
    for k in ("/Producer", "/Creator", "/Author"):
        w._info.get_object().pop(k, None)
    tmp = path.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as fh:
        w.write(fh)
    tmp.replace(path)


def main():
    TMP.mkdir(exist_ok=True)
    (DOCS / "img").mkdir(parents=True, exist_ok=True)
    prof = TMP / "edge-profile"
    pages = build_pages()
    head = f"<!doctype html><html><head><meta charset='utf-8'><title>U.S. releases case study</title><style>{CSS}</style></head><body>"
    sections = [PAGE.render(p=p, foot=FOOTER) for p in pages]
    src = TMP / "report.html"
    src.write_text(head + "".join(sections) + "</body></html>", encoding="utf-8")
    PDF.unlink(missing_ok=True)
    subprocess.run([edge(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header",
                    f"--user-data-dir={prof}", f"--print-to-pdf={PDF}", src.as_uri()], check=True, capture_output=True, timeout=180)
    wait_file(PDF)
    clean_pdf(PDF)
    names = ["00_overview", "01_the_job", "02_calendar_rows", "03_checker", "04_commentaries", "05_event_study", "06_latest_data", "07_methods"]
    for name, sec in zip(names, sections):
        one = TMP / f"{name}.html"
        one.write_text(head.replace("page-break-after: always", "") + sec + "</body></html>", encoding="utf-8")
        out = DOCS / "img" / f"{name}.png"
        out.unlink(missing_ok=True)
        subprocess.run([edge(), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                        "--window-size=1536,864", f"--screenshot={out}", one.as_uri()], check=True, capture_output=True, timeout=120)
        wait_file(out)
    from pypdf import PdfReader
    print("PDF:", PDF.relative_to(ROOT), f"({PDF.stat().st_size // 1024} KB, {len(PdfReader(str(PDF)).pages)} pages)")


if __name__ == "__main__":
    main()
