"""Report charts (matplotlib -> inline SVG). House style: light card background,
blue = the data, grey = the comparison, red = errors, dashed lines = thresholds, Segoe UI, one y-axis only."""
from __future__ import annotations

import io
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BLUE, BLUE_L, BLUE_D = "#2A78D6", "#86B6EF", "#1C5CAB"
GRAY, GRAY_D, RED = "#C9C7BF", "#898781", "#D03B3B"
INK, INK2, GRID, CARD = "#0B0B0B", "#52514E", "#E1E0D9", "#FCFCFB"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9.5, "text.color": INK2,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.facecolor": CARD, "figure.facecolor": CARD,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "axes.grid.axis": "x", "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": GRAY_D, "ytick.color": INK2, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "xtick.major.size": 0, "ytick.major.size": 0, "legend.frameon": False, "legend.fontsize": 9,
    "svg.fonttype": "none", "axes.axisbelow": True,
})


def fig(w_px, h_px):
    return plt.subplots(figsize=(w_px / 96, h_px / 96), dpi=96)


def svg(f) -> str:
    buf = io.StringIO()
    f.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.05)
    plt.close(f)
    s = buf.getvalue()
    s = s[s.find("<svg"):]
    s = re.sub(r'width="[\d.]+pt" height="[\d.]+pt"', 'width="100%" height="100%" preserveAspectRatio="xMidYMid meet"', s, 1)
    return re.sub(r"<metadata>.*?</metadata>", "", s, flags=re.S)


# ---------------------------------------------------------------- Carnelian case study charts


# ---------------------------------------------------------------- U.S. releases case study charts
def release_clock(cal: pd.DataFrame, w=560, h=250):
    """Calendar rows by release time (ET), with the posting's 14:00-19:00 window shaded."""
    t = cal.time_et.str.slice(0, 2).astype(int) + cal.time_et.str.slice(3, 5).astype(int) / 60
    cnt = t.value_counts().sort_index()
    f, ax = fig(w, h)
    ax.axvspan(14, 19, color=BLUE_L, alpha=0.25, lw=0)
    ax.text(16.5, cnt.max() * 1.02, "14:00-19:00 ET\nwindow in the posting", ha="center", va="top", fontsize=8.5, color=BLUE_D)
    ax.bar(cnt.index, cnt.values, width=0.35, color=[BLUE if x >= 14 else GRAY_D for x in cnt.index])
    for x, v in cnt.items():
        ax.text(x, v + cnt.max() * 0.02, f"{int(x):02d}:{int(round((x % 1) * 60)):02d}\n{v}", ha="center", va="bottom", fontsize=8)
    ax.set_xlim(7, 20)
    ax.set_ylim(0, cnt.max() * 1.3)
    ax.set_xticks(range(8, 21, 2), [f"{x:02d}:00" for x in range(8, 21, 2)])
    ax.set_yticks([])
    ax.grid(False)
    ax.set_xlabel("Release time, New York (ET)")
    return svg(f)


def weekly_load(cal: pd.DataFrame, w=560, h=230):
    d = cal.copy()
    d["week"] = pd.to_datetime(d.date).dt.to_period("W-SUN").dt.start_time
    p = d.pivot_table(index="week", columns="importance", values="event", aggfunc="count").fillna(0)
    f, ax = fig(w, h)
    bottom = np.zeros(len(p))
    for imp, col, lab in ((3, BLUE_D, "high"), (2, BLUE_L, "medium")):
        if imp in p:
            ax.bar(range(len(p)), p[imp], bottom=bottom, color=col, width=0.65, label=f"{lab} importance")
            bottom += p[imp].values
    for i, b in enumerate(bottom):
        ax.text(i, b + 0.3, f"{int(b)}", ha="center", fontsize=8.5)
    ax.set_xticks(range(len(p)), [f"{x:%d %b}" for x in p.index], fontsize=8)
    ax.set_yticks([])
    ax.grid(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    ax.set_ylim(0, bottom.max() * 1.15)
    ax.set_xlabel("Week starting")
    return svg(f)


def first_vs_latest(rv: pd.DataFrame, w=480, h=230, unit="K"):
    f, ax = fig(w, h)
    x = np.arange(len(rv))
    ax.bar(x - 0.18, rv["first"], 0.36, color=GRAY, label="as first reported")
    ax.bar(x + 0.18, rv["latest"], 0.36, color=BLUE, label="latest (17 Nov 2026)")
    for i, (a, b) in enumerate(zip(rv["first"], rv["latest"])):
        ax.text(i - 0.18, a + (3 if a >= 0 else -3), f"{a:,.0f}", ha="center", va="bottom" if a >= 0 else "top", fontsize=8, color=INK2)
        ax.text(i + 0.18, b + (3 if b >= 0 else -3), f"{b:,.0f}", ha="center", va="bottom" if b >= 0 else "top", fontsize=8, color=BLUE_D)
    ax.axhline(0, color=GRID)
    ax.set_xticks(x, rv.month)
    ax.set_yticks([])
    ax.grid(False)
    ax.legend(loc="upper left", ncol=2)
    ax.set_ylim(min(0, rv[["first", "latest"]].min().min() * 1.2), rv[["first", "latest"]].max().max() * 1.3)
    return svg(f)


def traps_bars(res: pd.DataFrame, w=420, h=300):
    """Traps caught by type (SIMULATED errors) and control sentences passed."""
    f, ax = fig(w, h)
    y = np.arange(len(res))[::-1]
    ax.barh(y, res.total, color=GRAY, height=0.6)
    ax.barh(y, res.ok, color=[BLUE if t != "control (correct text)" else "#0E7A55" for t in res.type], height=0.6)
    for yi, (o, t) in zip(y, zip(res.ok, res.total)):
        ax.text(t + 0.1, yi, f"{o}/{t}", va="center", fontsize=8.5)
    ax.set_yticks(y, res.type)
    ax.set_xticks([])
    ax.grid(False)
    ax.set_xlim(0, res.total.max() * 1.2)
    return svg(f)


def surprise_scatter(d: pd.DataFrame, beta: float, w=470, h=270, xlabel="", ylabel="2-year yield, change on the day (bp)"):
    f, ax = fig(w, h)
    ax.axhline(0, color=GRID, lw=1)
    ax.axvline(0, color=GRID, lw=1)
    ax.scatter(d.z, d.y2_bp, s=16, color=BLUE, alpha=0.65, lw=0)
    xs = np.linspace(d.z.min(), d.z.max(), 10)
    a = d.y2_bp.mean() - beta * d.z.mean()
    ax.plot(xs, a + beta * xs, color=RED, lw=1.6)
    ax.text(0.02, 0.96, f"slope {beta:+.1f} bp per 1 sd", transform=ax.transAxes, va="top", fontsize=9, color=RED)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y")
    return svg(f)


def coef_plot(r: pd.DataFrame, w=470, h=270):
    f, ax = fig(w, h)
    y = np.arange(len(r))[::-1]
    sig = r.p_value < 0.05
    ax.axvline(0, color=GRAY_D, lw=1)
    ax.errorbar(r.beta, y, xerr=[r.beta - r.ci_low, r.ci_high - r.beta], fmt="none", ecolor=BLUE_L, elinewidth=2.2, capsize=0)
    ax.scatter(r.beta, y, color=[BLUE_D if s else GRAY_D for s in sig], s=30, zorder=3)
    for yi, b, s in zip(y, r.beta, sig):
        ax.text(b, yi + 0.28, f"{b:+.2f}{'' if s else ' (n.s.)'}", ha="center", fontsize=8, color=INK2)
    ax.set_yticks(y, r.label)
    ax.set_xlabel("move per 1 sd of surprise (bp for yields, % for dollar and S&P 500)")
    return svg(f)


def ratio_bars(v: pd.DataFrame, w=470, h=230):
    """Average absolute daily move on event days / other days, for the 2-year yield and the S&P 500."""
    f, ax = fig(w, h)
    groups = list(v.group.unique())
    x = np.arange(len(groups))
    for k, (m, col, lab) in enumerate((("y2_bp", BLUE, "2-year yield"), ("eq_pct", GRAY_D, "Nasdaq Composite"))):
        vals = [v[(v.group == g) & (v.market == m)].ratio.iloc[0] for g in groups]
        ax.bar(x + (k - 0.5) * 0.36, vals, 0.36, color=col, label=lab)
        for xi, val in zip(x, vals):
            ax.text(xi + (k - 0.5) * 0.36, val + 0.03, f"{val:.1f}x", ha="center", fontsize=8.5)
    ax.axhline(1, color=RED, ls="--", lw=1)
    ax.text(len(groups) - 0.5, 1.03, "other days = 1", color=RED, fontsize=8, ha="right")
    ax.set_xticks(x, groups)
    ax.set_yticks([])
    ax.grid(False)
    ax.legend(loc="upper left", ncol=2)
    ax.set_ylim(0, max(v.ratio) * 1.3)
    return svg(f)


def lines(t: pd.DataFrame, cols, w=470, h=250, start="2019-01-01", ref=None, ref_label="", suffix="%", step=False):
    d = t[t.date >= start]
    f, ax = fig(w, h)
    ends = []
    for c, lab, col, lw, ls in cols:
        s = d[["date", c]].dropna()
        if step:
            ax.step(s.date, s[c], where="post", color=col, lw=lw, ls=ls, label=lab)
        else:
            ax.plot(s.date, s[c], color=col, lw=lw, ls=ls, label=lab)
        ends.append([s[c].iloc[-1], s.date.iloc[-1], col])
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * 0.06                                  # end labels pushed apart so they never overlap
    ends.sort(key=lambda e: e[0])
    ys = [e[0] for e in ends]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + gap)
    x_end = max(e[1] for e in ends)
    for (v, _, col), y in zip(ends, ys):
        ax.text(x_end, y, f"  {v:.1f}{suffix}", color=col, fontsize=8.5, va="center")
    if ref is not None:
        ax.axhline(ref, color=GRAY_D, ls="--", lw=1)
        ax.text(d.date.iloc[0], ref, f"{ref_label}", color=GRAY_D, fontsize=8, va="bottom")
    ax.grid(True, axis="y")
    ax.grid(False, axis="x")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=8.5)
    ax.margins(x=0.08)
    return svg(f)


def payroll_bars(t: pd.DataFrame, w=470, h=250, start="2023-01-01"):
    d = t[t.date >= start].dropna(subset=["nfp_chg"])
    f, ax = fig(w, h)
    ax.bar(d.date, d.nfp_chg, width=20, color=[GRAY if v >= 0 else RED for v in d.nfp_chg])
    ax.plot(d.date, d.nfp_3m, color=BLUE, lw=2, label="3-month average")
    ax.text(d.date.iloc[-1], d.nfp_3m.iloc[-1], f" {d.nfp_3m.iloc[-1]:,.0f}K", color=BLUE, fontsize=8.5, va="center")
    ax.axhline(0, color=GRID)
    ax.grid(True, axis="y")
    ax.grid(False, axis="x")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.set_ylabel("thousands")
    ax.margins(x=0.06)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    return svg(f)
