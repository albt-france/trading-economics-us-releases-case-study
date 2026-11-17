# Sources (collected 17 November 2026)

All data are public. U.S. government data are in the public domain. No data or text from the Trading Economics website or
API is used: its public pages were read by hand only to describe the company and the format of a calendar row.

| Source | What | Access | Used for |
|---|---|---|---|
| BLS Public Data API v1 (`api.bls.gov`) | CPI (SA/NSA, core, energy, food, shelter, services, core goods), payrolls, unemployment rate, hourly earnings, participation, PPI | JSON API, no key | fact sheets, cross-check |
| ALFRED, Federal Reserve Bank of St. Louis (`alfred.stlouisfed.org`) | Past vintages of BLS, BEA, Census, Labor Department and Fed series | CSV download, no key | release dates, first prints, revisions, real-time model forecasts, event study |
| FRED, Federal Reserve Bank of St. Louis (`fred.stlouisfed.org`) | Current values; daily 2- and 10-year Treasury yields, broad dollar index (Fed H.10), EUR/USD, WTI (EIA), S&P 500, fed funds target range | CSV download, no key | markets on release days, trends |
| U.S. Treasury, Daily Treasury Par Yield Curve Rates | 2- and 10-year yields, 2025-2026 | CSV | cross-check of FRED yields |
| Federal Reserve, FOMC calendar | Meeting dates 2021-2027, projection meetings | web page | calendar, event study |
| BEA release schedule (`apps.bea.gov/API/signup/release_dates.json`) | GDP, personal income and outlays, trade dates and times | JSON | calendar (upcoming rows, times) |
| Census Bureau economic indicator calendar (2026 and 2027 list views) | Retail sales, housing starts, durable goods, new home sales dates and times | web page | calendar (upcoming rows, times) |
| BLS release schedule, November 2026 | Release dates and times | web page read by hand (the site blocks scripts) | check of the dates found in ALFRED |
| Trading Economics, About and Careers pages; public API documentation (calendar endpoint) | Company facts as stated by Trading Economics; field list of a calendar row | read by hand | page 1 of the report; calendar format |

## Notes
- Census API now requires a key: retail sales, housing starts, durable goods and new home sales come from the FRED/ALFRED
  copies of the Census series. BEA series (GDP, PCE, trade) also come from FRED/ALFRED copies. Same numbers, original
  agency credited.
- The **October 2025** CPI index and unemployment rate were never published (2025 lapse in appropriations, BLS footnote):
  year-on-year CPI rates for **October 2026** cannot be computed from published index levels and are left empty.
- Retail sales for October 2026 were published at 08:30 ET on the collection day but were not yet in FRED/ALFRED.
- Trading Economics, as stated on its pages (17 Nov 2026): data for 196 countries and more than 20 million indicators;
  "nearly 2 billion" page views on the About page (source given: Google Analytics) and "more than 2 billion" on the Careers page.
- Market data are daily closes (Treasury yields: end of day; dollar index and EUR/USD: noon New York rates; S&P 500: close).
  No intraday data.
- Requests: neutral User-Agent, one call at a time with a pause, answers cached (`data/raw`, not published).
