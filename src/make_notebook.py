"""Write and execute notebooks/event_study.ipynb (the study's single notebook). Usage: python src/make_notebook.py"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "event_study.ipynb"

cells = [
    ("md", "# Event study: how markets react to U.S. CPI and payroll surprises (PUBLIC DATA)\n\n"
           "Question: on the day of a CPI or payroll release, do the 2-year Treasury yield, the dollar and the S&P 500 move with the "
           "size of the surprise?\n\n"
           "- **Releases**: every CPI and Employment Situation report since January 2016, dated with ALFRED vintages.\n"
           "- **Surprise**: the first print minus a *model forecast (illustrative)*, the average of the three previous prints as "
           "they stood the day before. No consensus is used: there is no free, reliable public source.\n"
           "- **Market move**: daily close-to-close change on the release day (FRED).\n"
           "- **Limits**: daily data (other news the same day), a model instead of a consensus (noisier surprise), COVID months excluded."),
    ("code", "import sys, pandas as pd, numpy as np\nsys.path.insert(0, '../src')\nimport event_study as es\n"
             "pd.set_option('display.precision', 2)\nt = es.release_table()\nt.groupby('indicator').agg(releases=('ref', 'size'), "
             "first=('release_date', 'min'), last=('release_date', 'max'))"),
    ("md", "## 1. What a surprise looks like\nCore CPI: published month-on-month change (one decimal) minus the model. "
           "Payrolls: monthly change (thousands) minus the model."),
    ("code", "t.groupby('indicator').surprise.describe()"),
    ("code", "cols = ['ref', 'release_date', 'core_actual', 'core_model', 'z', 'y2_bp', 'usd_pct', 'eq_pct']\n"
             "t[t.indicator == 'CPI'].sort_values('z').iloc[[0, 1, 2, -3, -2, -1]][cols]"),
    ("md", "## 2. Regressions: move on the day = a + b × surprise (in standard deviations)\nOLS with HC1 robust standard errors, "
           "reference months Mar 2020 - Mar 2021 excluded."),
    ("code", "r = es.regressions(t)\nr"),
    ("md", "## 3. Are release days more volatile than other days?\nAverage absolute daily move on event days divided by the "
           "average on all other days since 2016."),
    ("code", "v = es.volatility(t)\nv.pivot(index='group', columns='market', values='ratio')"),
    ("md", "## 4. Robustness: surprise measured against the previous print instead of the model"),
    ("code", "import statsmodels.api as sm\nd = t[(t.indicator == 'CPI') & ~t.covid].copy()\n"
             "d['s_prev'] = d.core_actual - d.core_prev\nd['z_prev'] = d.s_prev / d.s_prev.std()\ndd = d[['z_prev', 'y2_bp']].dropna()\n"
             "fit = sm.OLS(dd.y2_bp, sm.add_constant(dd.z_prev)).fit(cov_type='HC1')\n"
             "print(f\"core CPI vs previous print: {fit.params['z_prev']:+.2f} bp per sd, 95% CI \"\n"
             "      f\"{fit.conf_int().loc['z_prev', 0]:+.2f} to {fit.conf_int().loc['z_prev', 1]:+.2f}, n={len(dd)}\")"),
    ("code", "d = t[(t.indicator == 'NFP')].copy()\nd['rev1'] = d.nfp_prev_revised - d.nfp_prev_first\n"
             "print(f\"payrolls: previous month revised by {d.rev1.abs().mean():.0f}K on average (absolute), \"\n"
             "      f\"{(d.rev1.abs() >= 25).mean():.0%} of releases revised it by 25K or more\")"),
    ("md", "## 5. Reading\n- The 2-year yield is the market that moves most with the surprise: it prices the path of Fed rates.\n"
           "- The effect is real but noisy on daily data: R² is low because other news moves markets the same day.\n"
           "- A true consensus would give larger and cleaner slopes; the model surprise is a conservative lower bound.\n"
           "- Revisions to the previous month are large enough that 'previous' must always be the revised figure."),
]


def main():
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(s) if k == "md" else nbf.v4.new_code_cell(s) for k, s in cells]
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    NB.parent.mkdir(exist_ok=True)
    NotebookClient(nb, timeout=300, kernel_name="python3", resources={"metadata": {"path": str(NB.parent)}}).execute()
    nbf.write(nb, NB)
    print(f"Notebook         {NB.relative_to(ROOT)} executed ({len(nb.cells)} cells)")


if __name__ == "__main__":
    main()
