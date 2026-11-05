# Election results in the data API: design note

Asked by the manager on 5 November 2026: should the 2026 general election's
results (`collected/election_2026.json`, on branch `data/election-2026-sos`)
join the bulk files once they are final? A design only; nothing is built.

## The answer in short

Yes, as two small tables in the database and one spreadsheet, for every
general election the site has read (2024 and 2026 today), a race at a time
and only once that race is final by the same test the members-elect file
already uses. Three things are the owner's to decide first: whether vote
counts are published at all (the members-elect file deliberately carries
none), whether losing candidates are named, and whether the statewide
offices come in too. Defaults are given below.

## What is on hand

Read on 5 November 2026 (`measure_elections.py` in the scratchpad; figures
are the files', not this note's):

| | 2026 (`data/election-2026-sos`) | 2024 (`dev`) |
|---|---|---|
| Election, term it elects | 2026-11-03, 2027-2028 | 2024-11-05, 2025-2026 |
| State Representative and State Senate races | 227 | 227 |
| Seats | 424 | 424 |
| Candidates | 760 | 779 |
| Marked elected | 424 | 424 |
| Ties for a last seat (elected `null`) | 0 | 0 |
| Saved Secretary of State files it was read from | 25 | 11 |
| Reader's notes on what the files write their own way | 5 | 6 |

Each race (`races`, keyed `H|<County>|<district>` or `S|<district>`) holds its
seats, whether it is floterial, its towns, the scattered write-ins, and each
candidate's name, party letter, vote total, whether written in, and whether
elected. The files are the Secretary of State's, saved by the owner with each
file's address, day and sha256 (`_source`); `src/parse/parse_sos_results.py`
reads them, and nothing in the file is this project's decision "but the
winners, which the files do not mark" (its `_about`). Both years together, as
one table of candidates, are 1,539 rows and about 106 KB.

What the site does with them today: `/members_elect.json`, for the weeks
between the election and Organization Day only, and with "No vote counts,
contact details or reasons" (README, *The data*; DATA.md). The owner settles
names and recounts by hand in `corrections/members_elect.json`.

## When a race is final

By the rule `docs/ELECTION_WEEK.md` already sets for the members-elect file,
not a new one. Candidates may ask for a recount until 5 p.m. on the Friday
after the election (RSA 660:1, as ELECTION_WEEK.md cites it: 6 November in
2026). Until the owner enters `"recount_deadline"` together with the list of
races being recounted, every race is not final; a race being recounted stays
not final until its recount's file is read (`"recounted": true`) and it leaves
`"not_final"`.

Proposed: **a race enters the bulk files the night it is final by that test,
and never before.** A race that is not final is not a row, rather than a row
with a flag, so that a program that ignores flags still never reads a count
that may change. `elections.csv`'s description and `schema.json` say so.

The manager's word was "after certification". The Secretary of State's
certification is a later, separate step that nothing on disk records yet.
Default (QE4): the recount test above, which the site already trusts for
naming members-elect; a `certified` date per election can be added beside it
when a source for it is on hand.

## What would be published

In the database, beside the other tables:

```
election_races(election, term, race, chamber, county, district, seats,
               floterial, scattered, recounted, source_file, source_sha256)
election_candidates(election, race, candidate, party, votes, write_in,
                    elected, person)
election_places(election, race, place)
```

And `/data/elections.csv`, one row a candidate with the race's columns
beside it, so that a spreadsheet needs no join. Every year in one file: about
53 KB a general election, far from any limit.

- **`person`** is filled only for a winner the owner's
  `corrections/members_elect.json` matches to a sitting or former member with
  certainty (its `"matches"`), with that member's person number. A new member
  has no General Court number until they take office; their `person` stays
  empty until the night the roster carries them, when the people join numbers
  them by the rule and a match can be made. A losing candidate never has one:
  `people.json` is everyone with a recorded vote, not everyone who ran.
- **`elected`** is the site's reading, since the files mark no winner: the most
  votes, as many as the race has seats. A tie for a last seat stays empty, and
  a recount's result is read from the recount's own file. The description
  says so plainly.
- **Sources**: each race names the saved file and its sha256 it was read from;
  `manifest.json`'s `sources` gains the Secretary of State's results pages as
  a source outside the General Court's database, and the coverage table on
  `/api` says the same.
- **Terms**: the counts are the State's (the Secretary of State's) and this
  project claims nothing over them, as DATA.md already says of the
  constitutional amendments' counts. What the site adds, the winners' marking
  and the person links, falls under the CC0 line the owner approved.

## Not in the first version, by default

- **The Governor, the Executive Council and Congress** (QE3). The branch holds
  their 2026 results too, but the site keeps those offices by hand in
  `corrections/officials.json`, not from results, and they are not
  legislators. Default: out, until there is a reason.
- **Town-by-town counts** (QE5). The saved spreadsheets count each race by
  town; the results file keeps the race's totals and its list of towns. A town
  table would be far larger and is a new reader. Default: totals only.
- **Primaries.** Nothing on disk.

## Questions for the owner, each with a default

| # | Question | Default |
|---|---|---|
| QE1 | Publish vote counts? The members-elect file deliberately carries none, and every page names a member-elect without a count. | Yes in the bulk files, once a race is final: they are the Secretary of State's public results, and a data file without them answers little. The pages stay as they are. |
| QE2 | Name the candidates who lost? They are in the Secretary of State's public results. | Yes, with their votes, as the results print them; no person number, no page, nothing beyond the results' own words. |
| QE3 | The Governor, the Council and Congress too? | Not in the first version. |
| QE4 | "Final" as the recount test, or wait for certification? | The recount test, as members-elect uses; a certification date added when it has a source. |
| QE5 | Town-by-town counts? | Not in the first version. |
| QE6 | 2024 as well as 2026? | Yes: it is read and settled, and two elections make the table useful. |

## What building it would take, later

A branch after the December train: a reader of `collected/election_*.json`
and of the owner's `corrections/members_elect.json` (for `not_final`,
`recounted` and `matches`) into the three tables and `elections.csv`, in
`build_exports.py` and `api_db.py`; their columns in `api_schema.py`; a
preflight check that no race in `not_final` is ever a row; proven against a
full build like the others. It changes no page. It waits on the 2026 results
reaching `dev`, which ELECTION_WEEK.md ties to the recount deadline.
