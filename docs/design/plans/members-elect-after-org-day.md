# Members-elect after Organization Day: plan

The owner's direction, relayed 30 October 2026: members-elect stay visible after
Organization Day, labelled as the new House, until the General Court publishes
its member list. This revises decision 2 of 16 October ("they retire by
themselves" on Organization Day), which `docs/ELECTION_WEEK.md` and
`src/parse/build_members_elect.py` both record. A small branch,
`fix/members-elect-seated`, to land before 25 November.

## Why

Under the 16 October rule, from 2 December to the night the General Court's
member list turns, Officials shows the 2025–2026 roster alone as sitting.
ELECTION_WEEK.md already calls this a gap: members who lost are listed as
serving, and the people who were sworn in are not shown at all.

## What changes

1. **When the file retires** (`build_members_elect.window`). Today there are
   three reasons not to write it: before the election, on or after Organization
   Day, and once the site's newest term is theirs. The second becomes "on or
   after Organization Day *and* the installed roster has turned".
   `freeze_term.roster_turned(root, term)` already gives that signal: it is what
   `own_roster_terms` and `session_roster` use to tell that the night installed
   the next House before the files show the next term. The other two reasons
   stay. The file then retires on the first night the General Court's list
   names the new House, or the night the New term run turns the site, whichever
   comes first.

2. **The file says which phase it is in.** `for_pages()` adds
   `"seated": "2026-12-02"` once the build's day is on or after
   Organization Day. Before that the field is absent and every page reads as
   today. `takes_office` stays as it is.

3. **The words, once seated** (English and Spanish, new keys in
   `lang/es.json`). The approved sentence and the House's wording are the
   owner's, so these are drafts for them to approve:
   - Officials tab label: "Members-Elect" becomes "New House and Senate".
   - Intro: "Sworn in on December 2, 2026, by {the Secretary of State's count}.
     The General Court's own member list does not name them yet; until it does,
     the {Legislators tab} still shows the 2025–2026 roster."
   - Town pages and legislator pages: the member-elect block's heading
     "Elected November 3" becomes "Sworn in December 2". The race lines stay.
   - Legislators tab: one line above the roster while the file is seated, "This
     is the 2025–2026 House and Senate as the General Court still lists them.
     The members sworn in on December 2 are on the New House and Senate tab."
     This answers the gap of members who lost being shown as serving, without
     touching `site/legislators.json` (decision 1 of 16 October stands: a
     member-elect never enters the roster).

4. **The browser no longer hides them by its clock.** Today the panel and its
   content carry `data-until` = Organization Day, and app.js hides them from
   that day. Once seated, the build writes no `data-until` and the label
   changes at build time. Before Organization Day, `data-until` stays, but it
   now swaps the label to the seated words instead of hiding. That way a page
   built on 1 December and read on the 2nd is right without waiting for a
   night.

5. **check_site's guard** (`members_elect()` in `src/checks/check_site.py`).
   Today it refuses the file on or after the day they take office. New rule:
   - refuse on or after Organization Day if `seated` is missing (a build that
     skipped the step);
   - refuse once the installed roster has turned, or the newest term is
     theirs, and the file is still there.

   A file that names no day stays refused, as now.

6. **The Senate.** Both chambers are sworn in on Organization Day, so the same
   rule and words apply to state senators. The tab and intro say "House and
   Senate"; the owner's "the new House" reads as the whole General Court.
   **Question for the owner:** "New House and Senate", or "New General Court"?

## Checks (preflight)

- `build_members_elect.window`, over a calendar: 1 Dec written, not seated;
  2 Dec written, seated; 2 Dec with the roster turned, removed; the New term
  run, removed.
- `for_pages` writes `seated` only from Organization Day.
- The Officials tab, a town page and a legislator page, drawn from a seated
  fixture: the seated words, no `data-until`, and the Legislators tab's line.
  Drawn from an unseated fixture: as today, with `data-until`.
- app.js in node (`dom_stub.js`): a page built on 1 December and read on
  2 December swaps to the seated label and does not hide.
- check_site: seated after Organization Day passes; missing `seated` after it
  fails; roster turned with the file present fails.
- Revert proofs for each.

## Docs

- `docs/ELECTION_WEEK.md`, "2 December, Organization Day": replace "The
  members-elect retire by themselves…" and the 16 October gap paragraph with
  the new rule. On 2 December, check that Officials shows "New House and
  Senate" with the sworn-in wording. Each morning from 3 December, check
  Legislators until the new members are there; the night that installs them
  removes the tab by itself.
- `build_members_elect.py`'s docstring: decision 2 rewritten, dated
  30 October 2026, with the 16 October text kept as the history.

## Size and order

About 6 files plus checks and Spanish: `build_members_elect.py`,
`officials_tabs.py`, `build_town_pages.py` / `components.py` (the block),
`build_legislator_pages.py`, `app.js`, `check_site.py`, `lang/es.json`,
`preflight.py`, `ELECTION_WEEK.md`. It is reader-visible, so two review lenses.
Screenshots at 390/1280, light and dark, from fixtures dated 1 and 2 December.
After the release and Videos; before 25 November.

## Not changed

- `site/legislators.json` is never touched.
- Members-elect for the Governor, Council and Congress stay as they are:
  `corrections/officials.json`'s `"elect"`, which take office in January.
- The New term run and the freeze steps in ELECTION_WEEK.md.
