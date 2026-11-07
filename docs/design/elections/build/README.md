# The elections page, as built (branch feat/elections-official)

7 November 2026. Built at the owner's word of that morning, relayed by the
laptop manager: start building now; merge only after this weekend's release is
live; it goes out in a release after the webinar.

## What it is

`src/pages/build_elections.py` writes one page per general election in
`collected/`. Each page is official results only, from the Secretary of State's
files:

- `/elections/<YYYY-MM-DD>-general` for each election;
- `/elections/`, the list of them;
- a map file per election.

Each page has an overview, then a tab per office on file:

- **Overview:**
  - seats won by party, against the majority;
  - the district map, coloured by winners;
  - the closest races;
  - the reader's notes on the files.
- **State Senate.**
- **State House:** grouped by county, with a box to find a town or ward.
- **Ballot Questions,** where `corrections/ballot_results.json` has the
  Secretary of State's counts.

Each race is a card:

- every candidate's votes, as the collected file has them;
- the share of the vote in a one-seat race;
- "Elected" only where final;
- "Result not final", and "a recount was requested" where the owner's file
  says so;
- "Tied for the last seat"; "Unopposed";
- a held winner is not drawn.

## One rule for who is elected

The page decides none of it. It calls `build_members_elect.members_elect`, the
members-elect step's own function, on each election's entry of
`corrections/members_elect.json`. That function decides:

- what is final;
- who won;
- whom to link to a member page.

Losers are shown by name and party only.

## What it does not do

- It has no election-night source, projection or race call.
- It gives no count beyond the collected file.
  - Grafton 9 (2026): the file's printed total leaves out Orange. The card
    says so and shows the towns' sum, which is what the collected file holds.
- It does not show the Governor, the Council, Congress or the county offices:
  their files are saved on `dev` but not read yet (BUILD_PLAN.md 2.4).
- It has no per-town counts: that needs the reader's "places"
  (BUILD_PLAN.md 2.2).
- It needs nothing from the header's new section row. The page lights
  Officials in the navigation, and is in the sitemap.

## Changed outside the new builder

- `src/pages/map.js`: an opt-in `opts.words`, so that the elections map says
  "no final winner shown" where Officials' map says "vacant". Officials' map
  is unchanged.
- `src/pages/app.css`: `.er-*` rules, palette tokens only.
- `build_all.py`: one Step, after the district map.
- `preflight.py`: `_elections_page`.

## Proof so far

- `preflight.py --code`: 986 passed, 0 failed, 9 skipped (cloud session,
  7 November).
- `_elections_page` builds the fixture's made-up election and checks four
  things:
  - every count against the results file;
  - "Elected" against `members_elect`, on two days (before and after the
    deadline);
  - links against that function;
  - the cases: the tie, the recount, the held winner unseen, the
    cross-nomination striped, the bars adding up, and Grafton 9's note.
- One adversarial review found 13 problems; all 13 are fixed in 0117dd45.
- Screenshots: 2024 only, from the real data. They are in this folder,
  overview and House tab at 390 and 1280, light and dark.

## Still to do before READY

1. **Merge `dev` once it carries e10505d2.** It was not on any remote branch
   by the time of this commit. It brings `collected/election_2026.json` and
   the owner's 2026 recount entries.
2. **2026 screenshots** with those entries.
3. **The full preflight again,** after the merge.

## For the owner

- **2024 reads "Result not final" everywhere but the seven recounted races.**
  `corrections/members_elect.json` has no `"2024-11-05"` entry. With
  `"recount_deadline": "2024-11-08"` (NHPR: "Friday, Nov. 8th at 5 p.m."),
  every 2024 race becomes final by the same rule.
- **A held winner.** The design said a held winner is kept off the pages. Here
  their row and count are not drawn, the card says "A winner of this race is
  not shown here yet.", and the race is left out of Closest Races. Default
  kept; say if the whole race should be hidden instead.
