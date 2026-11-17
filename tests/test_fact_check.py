"""The number checker must catch every trap in data/_traps.csv (SIMULATED errors) and pass the control sentences."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fact_check import check, check_file, load_sheet  # noqa: E402

TRAPS = pd.read_csv(ROOT / "data" / "_traps.csv")


@pytest.mark.parametrize("row", TRAPS.to_dict("records"), ids=list(TRAPS.trap_id))
def test_trap(row):
    rep = check(row["text"], load_sheet(row["release"]))
    if row["expected"] == "pass":
        assert rep.passed, rep.text()
    else:
        assert not rep.passed, f"{row['trap_id']} not detected"
        assert row["expected"] in {f.error for f in rep.errors()}, rep.text()


def test_every_trap_type_covered():
    assert set(TRAPS.trap_type) >= {"mom_yoy", "revision", "sa_nsa", "sign", "unit", "wrong_period"}


def test_ignores_dates_times_and_maturities():
    rep = check("On October 14 at 08:30 ET, the 10-year and 2-year notes and the S&P 500 index in 2026.", load_sheet("2026-10-14_cpi"))
    assert rep.findings == []


COMMENTARIES = sorted(p for p in (ROOT / "commentary").glob("*.md") if (ROOT / "factsheets" / f"{p.stem}.json").exists())


@pytest.mark.parametrize("path", COMMENTARIES, ids=[p.stem for p in COMMENTARIES])
def test_commentary_numbers(path):
    rep = check_file(path)
    assert rep.passed, rep.text()


@pytest.mark.parametrize("path", COMMENTARIES, ids=[p.stem for p in COMMENTARIES])
def test_commentary_length(path):
    from fact_check import body_of
    words = len(body_of(path.read_text(encoding="utf-8")).split())
    assert 60 <= words <= 120, f"{path.name}: {words} words (target 60-120)"
