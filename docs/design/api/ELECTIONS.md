# Election results in the data API: design note

Asked by the manager on 5 November 2026: should the 2026 general election's
results (`collected/election_2026.json`, on branch `data/election-2026-sos`)
join the bulk files once they are final? A design only; nothing is built.

**The election model is not this note's.** It is the election results design's
(`docs/design/elections/DESIGN.md` on `design/election-results`, §2): its race
keys, its files, its people rule and its lifecycle (§5). This note is only the
API's view of that model, which means which of its fields reach `/data/` and
when. Where the two disagree, that design wins, and this note follows it.

## The answer in short

Yes, as a few small tables in the database and one spreadsheet, read from the
official file of every election the site has read, a race at a time. A race
is included only when that design's page would say "Elected" for it. Nothing
from the live store is ever included. Three things are the owner's to decide
first: whether vote counts are published at all (the members-elect file
deliberately carries none), whether losing candidates are named, and which
offices come in. Defaults are given below.

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

Today each file holds House and Senate races only. A race (`races`, keyed
`H|<County>|<district>` or `S|<district>`) holds its seats, whether it is
floterial, its towns, the scattered write-ins, and, for each candidate, their
name, party letter, vote total, whether they were written in, and whether they
were elected. `src/parse/parse_sos_results.py` reads the Secretary of State's
files, which the owner saved with each file's address, day and sha256
(`_source`). As the file's `_about` puts it, nothing in it is this project's
decision "but the winners, which the files do not mark". Both years together,
as one table of candidates, come to 1,539 rows and about 106 KB.

The election design widens this file to every office and adds two fields:
`places`, each candidate's count by town in candidate order, and, for a
recounted race, `first_count`. The API reads whatever that file holds and
follows its shape as it grows.

What the site does with them today: `/members_elect.json`, for the weeks
between the election and Organization Day only, and with "No vote counts,
contact details or reasons" (README, *The data*; DATA.md). The owner settles
names and recounts by hand in `corrections/members_elect.json`.

## When a race is included

When the election design's page would say "Elected" for it (its §5), and
never before. That is the rule the members-elect file already uses, from
`docs/ELECTION_WEEK.md`:

- The owner has entered that election's `"recount_deadline"` in
  `corrections/members_elect.json`. Candidates may ask for a recount until
  5 p.m. on the Friday after the election (RSA 660:1, as ELECTION_WEEK.md
  cites it); in 2026 that is 6 November.
- The race is not in `"not_final"`, or its recount's file has been read
  (`"recounted": true`).

A race that is not final is left out entirely, rather than included with a
flag. That way a program that ignores flags still never reads a count that
may change. `elections.csv`'s description and `schema.json` say so.

- **Only the official file.** The live store (`elections/<date>.json` in R2)
  and the page's own night file are not read. Their counts are unofficial,
  and the sources' terms are still open (that design's §1).
- **Certification:** the manager's word was "after certification", but New
  Hampshire sets no deadline for certifying results (that design's §5,
  citing NHPR), and nothing on disk records it. So the recount test above is
  used, as both designs already do; a `certified` date can sit beside it if a
  source for one is ever on hand.
- **2024** comes in the same way: only once the owner has added its
  `2024-11-05` entry, with its recount deadline, to `members_elect.json`. The
  election design's page needs that entry too.

## What would be published

The keys are the election design's, unchanged. An election is named by its
day and kind (`2026-11-03-general`, `2028-06-13-primary`), and a race by that
design's key: `H|Hillsborough|18`, `S|9`, `GOV`, `EC|2`, `S|9#R` for a
primary, `H|Strafford|4@2027-03-14` for a special. The database would hold,
beside the other tables:

```
election_races(election, day, kind, term, race, office, county, district,
               party, seats, floterial, scattered, recounted,
               source_file, source_sha256)
election_candidates(election, race, candidate, party, votes, first_votes,
                    write_in, elected, person)
election_places(election, race, place)
```

`/data/elections.csv` has one row per candidate, with the race's columns
beside it, so a spreadsheet needs no join. Every election goes in one file.
House and Senate come to about 53 KB per general election, far from any
limit.

- **`person`** is filled only through the election design's people rule
  (its §2.2). That means a winner the owner's `"matches"` settles to a member
  id, with that member's person number. It is never a string match. A new
  member has no General Court number until they take office, so their
  `person` stays empty until the night the roster carries them; the people
  join numbers them by the rule that night, and a match can then be made. A
  losing candidate never has one: nothing is issued for someone who never
  served, and `people.json` is everyone with a recorded vote, not everyone
  who ran.
- **`elected`** is the site's reading, since the files mark no winner: the
  candidates with the most votes, as many as the race has seats. A tie for a
  last seat stays empty, and a recount's result is read from the recount's
  own file. The description says so plainly. **`first_votes`** is filled
  only for a recounted race, from that design's `first_count`.
- **Sources**: each race names the saved file it was read from and that
  file's sha256. `manifest.json`'s `sources` gains the Secretary of State's
  results pages as a source outside the General Court's database, and the
  coverage table on `/api` says the same.
- **Terms**: the counts are the State's (the Secretary of State's) and this
  project claims nothing over them, as DATA.md already says of the
  constitutional amendments' counts. What the site adds, the marking of
  winners and the person links, falls under the CC0 line the owner approved.

## Not in the first version, by default

- **Offices other than the State House and Senate** (QE3). The election
  design keys every office, but its official file holds only these two
  today. The API takes what the official file holds, so the default only
  matters once the file widens: carry those offices too, keyed as that
  design keys them, with `person` left empty outside the matched set (that
  design's §2.2).
- **Town-by-town counts** (QE5). Once the election design's `places` field
  is in the official file, these come with no new reader. They would be an
  `election_place_votes(election, race, place, candidate, votes)` table,
  many times larger than the totals. Default: totals only in the first
  version, with that table added once `places` is in the file and the owner
  says yes.
- **Primaries**: none are on disk yet. When one is, it comes in as that
  design keys it (`#R`, `#D`), with no other change.

## Questions for the owner, each with a default

These go to the owner together with the election design's own questions
(that design's §7).

| # | Question | Default |
|---|---|---|
| QE1 | Publish vote counts? The members-elect file deliberately carries none, and every page names a member-elect without a count. | Yes in the bulk files, once a race is final: they are the Secretary of State's public results, and a data file without them answers little. |
| QE2 | Name the candidates who lost? They are in the Secretary of State's public results. | Yes, with their votes, as the results print them, and with no person number. |
| QE3 | Offices beyond the House and Senate, once the official file holds them? | Yes, as the election design keys them. |
| QE4 | "Final" by the recount test, or wait for certification? | The recount test, as both designs already use; New Hampshire sets no certification date. |
| QE5 | Town-by-town counts? | Not in the first version. |
| QE6 | 2024 as well as 2026? | Yes, once its `2024-11-05` recount entry is in `members_elect.json`. |

## What building it would take, later

No build until the owner has answered these questions together with the
election design's. Then it would be a branch after the December train:

- a reader of `collected/election_*.json` and of the owner's
  `corrections/members_elect.json` (for `recount_deadline`, `not_final`,
  `recounted` and `matches`), which fills the tables and `elections.csv`
  through `build_exports.py` and `api_db.py`. It should be the same function
  the election page's night build uses to decide "Elected", not a copy of it;
- the columns in `api_schema.py`;
- a preflight check that no race in `not_final` is ever a row;
- proof against a full build, like the others.

It changes no page. It waits on the 2026 results reaching `dev`.
