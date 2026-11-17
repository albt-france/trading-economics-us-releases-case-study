# Release-day playbook (U.S. session, 14:00-19:00 New York time)

Goal: calendar row updated in **under 2 minutes**, commentary published in **under 10 minutes**, zero wrong numbers.

## Before (the day before or at the start of the shift)
- [ ] Check the week's calendar: event, reference period, time (ET), importance. Official schedules: BLS, BEA, Census, Fed, Labor Department.
- [ ] Build the fact sheet for each release: previous figure (and whether it may be revised), 3- and 12-month averages,
      model forecast (illustrative), key components, what markets were watching (`python src/build_factsheets.py`).
- [ ] Pre-write the frame: headline pattern, the comparison sentence, the components to look at first.
- [ ] Note the market levels before the release (2-year and 10-year yields, dollar index, S&P 500 futures if available).

## During (release minute = T)
| Step | Target | What |
|---|---|---|
| 1 | T + 1 min | Read the headline number from the official release (not from a secondary source). |
| 2 | T + 2 min | Update the calendar row: actual, previous **revised**, note. |
| 3 | T + 6 min | Write the commentary from the frame: fact headline, comparison, drivers, context. |
| 4 | T + 8 min | Run the number checker (`python src/fact_check.py commentary/<release>.md`); fix every flag. |
| 5 | T + 10 min | Publish. Add the market reaction when the close is in (daily data) or update later. |

### One-minute checklist before publishing
- [ ] Right reference month (October data, released in November)?
- [ ] Month-on-month vs year-on-year said explicitly?
- [ ] Previous figure = revised figure?
- [ ] Seasonally adjusted unless stated otherwise?
- [ ] Sign and verb agree (rose / fell)?
- [ ] Units: thousands, per cent, basis points?
- [ ] No forecast or consensus we cannot source?

## After
- Update the previous row if the release revised it; note large revisions in the next commentary.
- Follow markets to the close: 2-year yield, dollar, S&P 500. Daily data cannot separate the release from other news.
- Archive the fact sheet and the final text.

## If something goes wrong
- **Source late or site down:** keep the calendar row as "scheduled", do not use unofficial figures, check the agency's
  status page or alternative official channel (API, PDF, press feed), publish a one-line delay note if long.
- **Release postponed or cancelled** (e.g. a government shutdown): mark the row, keep the old date in the note, re-date it
  once the agency publishes a new schedule.
- **A published number is wrong:** correct it at once, say "corrected" in the note, keep a log of the correction.
- **Agency correction after publication:** update the row and the commentary, mark "revised by the agency".

## Training scenario (SIMULATED)
A heavy evening to rehearse the method (times ET; targets, not measured results):

| Time | Release | Calendar row | Commentary |
|---|---|---|---|
| 08:30 | CPI, retail sales, jobless claims | 3 rows in 3 min | CPI first (< 10 min), then retail sales |
| 10:00 | JOLTS job openings | < 2 min | short note (< 6 min) |
| 14:00 | FOMC decision and statement | < 2 min | decision + statement changes (< 10 min) |
| 14:30 | Fed Chair press conference | - | add 1-2 lines when quotes are confirmed |
