# Commentaries

**Status: trial drafts.** The 12 texts below were drafted with the AI-assisted workflow described in the main README (Methods) to test the format and the checker; they are to be reviewed and rewritten by the author.

One file per release, named like its fact sheet (`factsheets/<date>_<release>.md`). Format: a fact headline (`# ...`),
then 60-120 words: the number and its comparison, the main drivers, the market reaction on the day (daily closes), one
line of context. Rules: [docs/STYLE_GUIDE.md](../docs/STYLE_GUIDE.md).

Process: fact sheet prepared from official data -> commentary written -> every number checked with
`python src/fact_check.py commentary/<release>.md` -> wording edits only (concision, exact terms) -> final text kept here.
`pytest` re-checks every commentary and its length.
