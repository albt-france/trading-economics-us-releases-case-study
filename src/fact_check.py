"""Number checker for release commentaries.

Every number in a commentary must be traceable to the release's fact sheet (factsheets/<release>.json), with the
right subject, measure (MoM / YoY / annualised), seasonal basis (SA / NSA), reference period, sign and unit.
A previous-period figure must be the *revised* one unless the text says it was "initially reported".
The text is rejected if any number fails; each failure says what is wrong and what the fact sheet says.

Usage:  python src/fact_check.py commentary/2026-10-14_cpi.md      (exit code 1 if a number is rejected)
        python src/fact_check.py --all                              (every commentary that has a fact sheet)
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "factsheets"
COMM = ROOT / "commentary"

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
MONTH_RE = r"\b(" + "|".join(m.capitalize() for m in MONTHS) + r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b"
SHORT = {"jan": "january", "feb": "february", "mar": "march", "apr": "april", "jun": "june", "jul": "july",
         "aug": "august", "sep": "september", "sept": "september", "oct": "october", "nov": "november", "dec": "december"}

UP = r"rose|rise|rises|rising|increased|increase|increases|climbed|climb|gained|gain|gains|added|adding|grew|grow|growth|expanded|jumped|jump|accelerated|accelerate|rebounded|advanced|up|higher|firmed|strengthened|strengthen|beat|surged|picked up|edged up|ticked up"
DOWN = r"fell|fall|falls|falling|declined|decline|declines|dropped|drop|drops|decreased|decrease|slipped|slid|lost|loss|losses|shed|contracted|contraction|shrank|eased|ease|easing|cooled|slowed|slowdown|retreated|weakened|weaken|down|lower|edged down|ticked down"
NEUTRAL = r"unchanged|flat|steady|held|stable"

YOY = r"year[- ]on[- ]year|year[- ]over[- ]year|from a year (?:earlier|ago|before)|over the (?:past|last) (?:year|12 months)|12[- ]month|y/y|yoy|annual (?:rate of )?(?:inflation|increase|gain|pace)|on the year|in the (?:year|12 months) to|year[- ]ago"
MOM = r"month[- ]on[- ]month|month[- ]over[- ]month|m/m|mom|from (?:the )?(?:previous|prior) month|on the month|monthly|in the month"
ANN = r"annuali[sz]ed|annual rate|saar"
NSA = r"not seasonally adjusted|unadjusted|before seasonal adjustment|\bnsa\b|non-seasonally adjusted"
SA = r"(?<!not )seasonally adjusted|\bsa\b"
PREV_CUE = r"after|previous|prior|a month earlier|last month|preceding|revised|from (?=\d)"
FIRST_CUE = r"initially|originally|first reported|previously reported|first estimate|before revision|first print"
FCST_CUE = r"forecast|model|expected|expectation|projection|projected"

NUM = re.compile(
    r"(?P<sign>[-−–]|minus )?(?P<cur>\$)?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<suf>\s?(?:%|percent\b|per cent\b|percentage points?\b|pp\b|bps?\b|basis points?\b|K\b|k\b|thousand\b|"
    r"million\b|mn\b|M\b|billion\b|bn\b|B\b|points?\b|pts\b))?")


@dataclass
class Claim:
    raw: str
    value: float          # value as written, in the written unit
    decimals: int
    family: str           # pct | pp | bp | count | money | level
    scale: float          # multiply by this to get the fact sheet unit (counts: thousands; money: billions)
    sign: int             # -1 if the text says the change was negative
    level_claim: bool     # "to 4.4%", "at 4.4%": the number is a level, not a change
    direction: int        # +1 / -1 / 0 from the verb (used for level claims)
    measure: str | None   # mom | yoy | ann | None
    basis: str | None     # SA | NSA | None
    period: str | None    # month name, "previous" or None
    first_cue: bool
    fcst_cue: bool
    subject: str | None
    sentence: str
    start: int


@dataclass
class Finding:
    claim: Claim
    ok: bool
    error: str = ""
    message: str = ""
    fact: dict | None = None


@dataclass
class Report:
    release: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(f.ok for f in self.findings)

    def errors(self) -> list[Finding]:
        return [f for f in self.findings if not f.ok]

    def text(self) -> str:
        n_ok = sum(f.ok for f in self.findings)
        out = [f"{self.release}: {n_ok}/{len(self.findings)} numbers verified -> {'PASS' if self.passed else 'REJECTED'}"]
        for f in self.errors():
            out.append(f"  [{f.error}] '{f.claim.raw}' in: {f.claim.sentence.strip()[:110]}\n      {f.message}")
        return "\n".join(out)


def _decimals(s: str) -> int:
    s = s.replace(",", "")
    return len(s.split(".")[1]) if "." in s else 0


def _last(pattern: str, text: str) -> re.Match | None:
    m = None
    for m in re.finditer(rf"\b(?:{pattern})\b", text, flags=re.I):
        pass
    return m


def _ignored(text: str, m: re.Match) -> bool:
    a, b = m.start("num"), m.end()
    before, after = text[max(0, a - 12):a], text[b:b + 12]
    n = m.group("num")
    if m.group("suf"):
        return False
    if re.match(r"\s?-?\s?(?:year|month|week|day|yr|quarter)s?\b", after, flags=re.I) or re.match(r"-(?:year|month|week|day)", after):
        return True                                            # "2-year", "12 months", "3-month"
    if re.search(r"S&P\s?$", before) and n == "500":
        return True
    if re.match(r":\d", after) or re.search(r"\d:$", before) or re.match(r"\s?(?:a\.m\.|p\.m\.|am\b|pm\b|ET\b|EST\b)", after, flags=re.I):
        return True                                            # times
    if re.search(r"\bQ$", before) or re.match(r"(?:st|nd|rd|th)\b", after):
        return True                                            # Q3, 3rd
    if re.fullmatch(r"(?:19|20)\d\d", n):
        return True                                            # years
    if n.isdigit() and int(n) <= 31 and (re.search(MONTH_RE + r"\.?\s$", before) or re.match(r"\s" + MONTH_RE, after)):
        return True                                            # "October 14", "Nov. 6", "6 November"
    if re.search(r"(?:Section|Table|page|Chart)\s$", before, flags=re.I):
        return True
    return False


QUARTERS = {"first": "q1", "second": "q2", "third": "q3", "fourth": "q4"}
PERIOD = (r"January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|"
          r"Jul|Aug|Sep|Sept|Oct|Nov|Dec|Q[1-4]|(?:first|second|third|fourth) quarter")


def _norm_period(p: str) -> str:
    p = p.lower()
    if re.fullmatch(r"q[1-4]", p):
        return p
    if p.endswith("quarter"):
        return QUARTERS[p.split()[0]]
    return SHORT.get(p, p)


def _period(before: str, after: str) -> str | None:
    """Reference period the text gives a number: a month/quarter right after it ('0.4% in September'), else a
    'previous' cue right before it ('after 0.4%', 'from 4.2%', 'revised up to'), else the last period named before it."""
    m_after = re.match(rf"[^.;\d]{{0,30}}?\b(?:in|for|during)\s+(?:the\s+)?({PERIOD})\b", after, flags=re.I)
    if m_after:
        return _norm_period(m_after.group(1))
    if re.search(rf"\b(?:{PREV_CUE}|from)\b[^.;\d]{{0,25}}$", before, flags=re.I):
        return "previous"
    mb = re.findall(rf"\b({PERIOD})\b", before, flags=re.I)
    return _norm_period(mb[-1]) if mb else None


def extract(text: str, keywords: dict[str, list[str]]) -> list[Claim]:
    """All numbers of the text that must be verified, with what the sentence says about each of them."""
    sentences = [(m.start(), m.group()) for m in re.finditer(r"(?:[^.!?\n]|\.(?=\d))+(?:[.!?](?!\d)|$)", text, flags=re.M)]
    matches = [m for m in NUM.finditer(text) if not _ignored(text, m)]
    kw_pos = []                                                 # (end position, keyword) of every subject keyword
    for kw in {k for ks in keywords.values() for k in ks}:
        for km in re.finditer(rf"(?<![\w-]){re.escape(kw)}(?![\w])", text, flags=re.I):
            kw_pos.append((km.end(), km.start(), kw))
    claims = []
    for i, m in enumerate(matches):
        s0, sent = next(((s, t) for s, t in sentences if s <= m.start() < s + len(t)), (0, text))
        prev_end = max(s0, matches[i - 1].end() if i else 0)
        next_start = min(s0 + len(sent), matches[i + 1].start() if i + 1 < len(matches) else len(text))
        before, after = text[prev_end:m.start()], text[m.end():next_start]
        local = before + " " + after
        suf = (m.group("suf") or "").strip().lower()
        num = float(m.group("num").replace(",", ""))
        dec = _decimals(m.group("num"))
        family, scale = "level", 1.0
        if suf in ("%", "percent", "per cent"):
            family = "pct"
        elif suf.startswith("percentage point") or suf == "pp":
            family = "pp"
        elif suf in ("bp", "bps") or suf.startswith("basis point"):
            family = "bp"
        elif suf in ("k", "thousand"):
            family = "count"
        elif suf in ("million", "mn", "m"):
            family, scale = ("money", 0.001) if m.group("cur") else ("count", 1000.0)
        elif suf in ("billion", "bn", "b"):
            family, scale = ("money", 1.0) if m.group("cur") else ("count", 1e6)
        elif suf in ("point", "points", "pts"):
            family = "level"
        elif m.group("cur"):
            family = "level"
        elif "," in m.group("num") and num >= 1000:
            family, scale = "count_or_level", 0.001
        # sign and direction: last verb before the number, otherwise a noun just after it ("a 22K loss")
        vb = _last(f"{UP}|{DOWN}|{NEUTRAL}", before)
        va = re.match(rf"\s*(?:\w+\s){{0,2}}?\b({UP}|{DOWN})\b", after, flags=re.I)
        word = (vb.group() if vb else (va.group(1) if va else "")).lower()
        direction = 1 if re.fullmatch(UP, word) else -1 if re.fullmatch(DOWN, word) else 0
        level_claim = bool(re.search(r"\b(?:to|at|was|were|is|stood at|held at|remained at|of just|reading of)\s*$", before, flags=re.I)) \
            and not re.search(rf"\b(?:{UP}|{DOWN})\s+of\s*$", before, flags=re.I)
        explicit_neg = bool(m.group("sign")) and not re.search(r"[\d%]\s?$", text[:m.start()])   # "3.75%-4.00%" is a range
        sign = -1 if explicit_neg or (direction < 0 and not level_claim) else 1
        # measure: cues in the number's own clause; basis: anywhere around it; period: see _period
        clause = re.split(r";|,\s|\band\b|\bwhile\b|\bbut\b|\bafter\b|\bfrom\b(?! a year| the previous| the prior)", before)[-1]
        mlocal = clause + " " + after
        meas = "yoy" if re.search(YOY, mlocal, flags=re.I) else "ann" if re.search(ANN, mlocal, flags=re.I) else \
            "mom" if re.search(MOM, mlocal, flags=re.I) else None
        basis = "NSA" if re.search(NSA, local, flags=re.I) else "SA" if re.search(SA, local, flags=re.I) else None
        period = _period(before, after)
        # subject: nearest keyword before the number (longest wins on ties), else first keyword after it
        cands = [k for k in kw_pos if k[0] <= m.start()]
        right = [k for k in kw_pos if k[1] >= m.end() and re.fullmatch(r"[ \t]+", text[m.end():k[1]])]   # same line only
        if right:                                               # "the 2% target": keyword right after the number
            subj = min(right, key=lambda k: (k[1], -(k[0] - k[1])))[2]
        elif cands:
            subj = max(cands, key=lambda k: (k[0], k[0] - k[1]))[2]
        else:
            after_k = [k for k in kw_pos if k[1] >= m.end()]
            subj = min(after_k, key=lambda k: (k[1], -(k[0] - k[1])))[2] if after_k else None
        claims.append(Claim(raw=m.group().strip(), value=num, decimals=dec, family=family, scale=scale, sign=sign,
                            level_claim=level_claim, direction=direction, measure=meas, basis=basis, period=period,
                            first_cue=bool(re.search(FIRST_CUE, local, flags=re.I)),
                            fcst_cue=bool(re.search(FCST_CUE, before[-45:] + after[:25], flags=re.I)),
                            subject=subj.lower() if subj else None, sentence=sent, start=m.start()))
    return claims


def _family_ok(c: Claim, f: dict) -> bool:
    fam = f["family"]
    if c.family == "count_or_level":
        return fam in ("count", "level")
    return c.family == fam


def _value(c: Claim, f: dict, signed=True, factor=1.0) -> bool:
    """Does the fact, written with the same unit and decimals as the text, give the text's number?"""
    if f.get("value") is None:
        return False
    scale = c.scale if not (c.family == "count_or_level" and f["family"] == "level") else 1.0
    if c.family == "count_or_level" and f["family"] == "count":
        scale = 0.001
    v = c.value * (c.sign if signed and not c.level_claim else 1) * scale * factor
    target = abs(f["value"]) if f.get("signed_level") else f["value"]
    if f.get("signed_level"):
        v = abs(v)
    tol = 0.5 * 10 ** (-c.decimals) * scale * abs(factor) + 1e-9
    return abs(v - target) <= tol


def _period_ok(c: Claim, f: dict) -> bool:
    if c.period is None:
        return f["role"] in ("current", "forecast", "market", "context")
    if c.period == "previous":
        return f["role"] in ("previous", "previous_first")
    return f.get("month", "").lower() == c.period


def check(text: str, sheet: dict) -> Report:
    facts = sheet["facts"]
    keywords = {f["id"]: f["keywords"] for f in facts}
    rep = Report(sheet["release"])
    for c in extract(text, keywords):
        subj = [f for f in facts if c.subject and c.subject in [k.lower() for k in f["keywords"]]] or facts
        ok = None
        for f in subj:
            if not _family_ok(c, f) or not _value(c, f):
                continue
            if f["role"] == "forecast" and not c.fcst_cue:
                continue
            if f["role"] != "forecast" and c.fcst_cue and any(g["role"] == "forecast" for g in subj):
                continue
            if c.measure and f.get("measure") and c.measure != f["measure"]:
                continue
            if c.basis and f.get("basis") and c.basis != f["basis"]:
                continue
            if not _period_ok(c, f):
                continue
            if f["role"] == "previous_first" and not c.first_cue:
                continue
            ok = f
            break
        if ok is not None:
            if c.level_claim and c.direction and ok.get("prev") is not None and ok["role"] == "current":
                moved = ok["value"] - ok["prev"]
                if moved * c.direction < 0 or (moved == 0 and c.direction != 0):
                    rep.findings.append(Finding(c, False, "direction", f"{ok['label']} moved from {ok['prev']} to {ok['value']}: "
                                                                       f"the verb says the opposite.", ok))
                    continue
            rep.findings.append(Finding(c, True, fact=ok))
            continue
        rep.findings.append(_diagnose(c, subj, facts))
    return rep


def _fv(f: dict, signed=False) -> str:
    """A fact's value written the way a reader expects it (60K, 0.4%, 5 bp, $105.0 billion)."""
    v, fam = f["value"], f["family"]
    sg = "+" if signed and v > 0 else ""
    if fam == "count":
        return f"{sg}{v:,.0f}K"
    if fam == "money":
        return f"{sg}${v:,.1f} billion"
    if fam == "bp":
        return f"{sg}{v:,.0f} bp"
    if fam == "pp":
        return f"{sg}{v:.1f} pp"
    if fam == "pct":
        return f"{sg}{v:g}%"
    return f"{sg}{v:,g}"


def _diagnose(c: Claim, subj: list[dict], facts: list[dict]) -> Finding:
    """Name the most likely mistake by testing the usual traps one by one."""
    def any_fact(pool, **kw):
        for f in pool:
            if not _family_ok(c, f) and kw.get("family", True):
                continue
            if _value(c, f, signed=kw.get("signed", True), factor=kw.get("factor", 1.0)):
                if kw.get("test", lambda f: True)(f):
                    return f
        return None

    cur = [f for f in subj if f["role"] == "current"]
    if c.measure:
        f = any_fact(cur, test=lambda f: f.get("measure") and f["measure"] != c.measure and (not c.basis or f.get("basis") in (None, c.basis)))
        if f:
            want = next((g for g in cur if g.get("measure") == c.measure and g["family"] == f["family"]), None)
            return Finding(c, False, "mom_yoy", f"{c.raw} is the {f['measure'].upper()} figure, but the text calls it {c.measure.upper()}"
                           + (f"; the {c.measure.upper()} figure is {_fv(want)}." if want else "."), f)
    if c.basis:
        f = any_fact(cur, test=lambda f: f.get("basis") and f["basis"] != c.basis)
        if f:
            want = next((g for g in cur if g.get("basis") == c.basis and g.get("measure") == f.get("measure")), None)
            return Finding(c, False, "sa_nsa", f"{c.raw} is the {f['basis']} figure, but the text says {c.basis}"
                           + (f"; the {c.basis} figure is {_fv(want)}." if want else "."), f)
    f = any_fact(subj, test=lambda f: f["role"] == "previous_first")
    if f and not c.first_cue:
        rev = next((g for g in subj if g["role"] == "previous" and g["id"] == f["id"].replace("_first", "")), None)
        return Finding(c, False, "revision", f"{c.raw} is the first estimate for {f['month'].capitalize()}; it was revised to "
                       f"{_fv(rev) if rev else '?'}. Use the revised figure (or say 'initially reported').", f)
    f = any_fact(subj, test=lambda f: not _period_ok(c, f) and f["role"] in ("current", "previous"))
    if f:
        return Finding(c, False, "wrong_period", f"{c.raw} is the {f['month'].capitalize()} figure, but the text dates it "
                       f"{c.period.capitalize() if c.period not in (None, 'previous') else ('the previous period' if c.period else 'the current period')}.", f)
    f = any_fact(subj, signed=False, test=lambda f: f["value"] != 0)
    if f and not c.level_claim:
        return Finding(c, False, "sign", f"{f['label']} was {_fv(f, signed=True)}: the text gives the opposite sign.", f)
    for factor in (1000.0, 0.001):
        f = any_fact(subj, factor=factor, family=False, test=lambda f: f["family"] in ("count", "money"))
        if f:
            return Finding(c, False, "unit", f"{c.raw}: unit error (thousands vs millions); the fact sheet says {_fv(f)}.", f)
    f = any_fact(facts)
    if f:
        return Finding(c, False, "wrong_subject", f"{c.raw} matches '{f['label']}', not the subject of the sentence ({c.subject}).", f)
    near = sorted((f for f in subj if _family_ok(c, f) and f["role"] in ("current", "market") and f["value"] is not None),
                  key=lambda f: abs(f["value"] - c.value * c.sign * c.scale))
    hint = f" Closest fact: {near[0]['label']} = {_fv(near[0])}." if near else ""
    return Finding(c, False, "not_in_factsheet", f"{c.raw} cannot be traced to the fact sheet.{hint}")


def load_sheet(release: str) -> dict:
    return json.loads((FACTS / f"{release}.json").read_text(encoding="utf-8"))


def body_of(md: str) -> str:
    """The commentary itself: the headline and text, without the metadata block and the word-count line."""
    md = re.sub(r"^<!--.*?-->\s*", "", md, flags=re.S)
    return "\n".join(ln.lstrip("# ").strip() for ln in md.splitlines() if not ln.startswith(">"))


def check_file(path: Path) -> Report:
    return check(body_of(path.read_text(encoding="utf-8")), load_sheet(path.stem))


def main(argv: list[str]) -> int:
    paths = sorted(p for p in COMM.glob("*.md") if (FACTS / f"{p.stem}.json").exists()) if argv == ["--all"] else [Path(a) for a in argv]
    bad = 0
    for p in paths:
        rep = check_file(p)
        print(rep.text())
        bad += not rep.passed
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
