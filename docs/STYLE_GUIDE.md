# Style guide for release commentaries

Short, factual, number first. A reader should know what was published, how it compares and how markets took it, in 20 seconds.

## Format (60-120 words)
1. **Headline = the fact.** Indicator, direction, number, period. No adjectives, no question, no pun.
2. **Sentence 1:** the number and its comparison (previous month, revised; model forecast or trend).
3. **Sentence 2-3:** the main drivers (components, sectors), each with its number.
4. **Sentence 4:** the market reaction on the day (2-year yield in basis points, dollar, S&P 500), from daily closes.
5. **Sentence 5:** one line of context (trend, Fed, what comes next). Optional.

## Rules
- **Number first.** "Consumer prices rose 0.3% in October", not "In a sign of continued pressure, consumer prices...".
- **One idea per sentence.** Split any sentence with two "and" or a semicolon.
- **Exact verbs.** rose / fell / was unchanged; *eased* and *accelerated* only for a rate that moved down or up;
  *beat* / *missed* only against a stated forecast; *revised* up or down for a changed earlier figure.
- **Say the measure.** "from the previous month" or "from a year earlier" every time a percentage could be read both ways.
- **Say the basis when it is not the default.** Monthly changes are seasonally adjusted; CPI year-on-year rates are not
  seasonally adjusted (the BLS convention). Write "not seasonally adjusted" only when you use an NSA monthly figure.
- **Units.** Payrolls in thousands ("119,000" or "119K"); yields in per cent for levels and **basis points** for changes;
  the dollar and stocks in per cent; rates moves in **percentage points**.
- **Previous = revised previous.** Always compare with the revised figure. Mention the revision if it changes the story.
- **No forecast we do not have.** There is no free public consensus here. Compare with the previous print, the trend or
  the "model forecast (illustrative)"; never write "economists expected".
- **Market reaction = daily close-to-close**, so say "on the day" and do not claim causality the data cannot show.
- **No investment advice**, no predictions of prices.
- **Rounding:** as published (CPI and retail sales one decimal; payrolls to the thousand; yields two decimals).
- **Plain words:** "jobs" or "payrolls", "prices", "spending"; spell out an abbreviation the first time (PCE, FOMC).

## Vocabulary
| Use | For | Avoid |
|---|---|---|
| rose / increased | a positive change | soared, skyrocketed (unless it is a record) |
| fell / declined | a negative change | plunged, crashed |
| eased / slowed | a lower rate of change | cooled off sharply |
| accelerated / picked up | a higher rate of change | heated up |
| was unchanged / held at | no change | flatlined |
| beat / missed | vs a stated forecast | surprised (vague) |
| revised up / down | a changed earlier print | corrected |
| basis point (bp) | 0.01 percentage point | "points" for yields |

## Frequent traps (all tested by `src/fact_check.py`)
| Trap | Wrong | Right |
|---|---|---|
| Month vs year | "CPI rose 3.0% in October from the previous month" | 3.0% is the year-on-year rate |
| Forgotten revision | "after 50,000 in September" | September was revised; use the new figure |
| SA vs NSA | an unadjusted monthly change presented as adjusted | say which basis |
| Sign | "fell 0.1%" when it rose 0.1% | read the sign before the verb |
| Units | "119 million jobs" | 119,000 (thousands) |
| Reference month | October data described as September | the release date is not the reference month |
