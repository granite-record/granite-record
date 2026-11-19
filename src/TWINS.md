# The twins: one rule written in Python and in JavaScript

Some rules are written twice: once in Python, for what the build writes, and
once in JavaScript, for what the browser or a Worker works out. A twin is safe
only while a check holds its two halves to one answer, so each pair is listed
here with where each half is and the check that holds it. A check is named by
its function in `src/checks/suite/`; `python3 preflight.py --changed` runs
every check a change can reach.

Change both halves in one commit, and run the check. A new twin gets a row
here and a check before it is merged; better still, a rule that is a table
becomes data in `src/pages/words/`, which both languages read (below).

Read off the code on 19 November 2026 (the refactor's stage 1, from the list
in stage0-code.md, section 4, checked again against the suite).

## Held by a check

| the rule | Python | JavaScript | held by |
|---|---|---|---|
| A component: a person, a committee, a chip, a date, a time, a record's tab strip | `src/pages/components.py` | `src/pages/components.js` | `_components_agree`: the same helpers in both, each run on every case of `tests/components_cases.json` and compared byte for byte, every line and branch of both reached. `_one_date_formatter`, `_calendar_clock`, `_chips_one_shape` and `_one_record_tab_strip` hold the pages to the components |
| The HTML escape | `src/lib/htmlesc.py`, through `components.esc` | `components.js` `esc` | `_components_agree`; `_shared_helpers_one_home` fails a copy of it anywhere else in Python |
| The order bill numbers are listed in | `src/pages/bill_order.py` `bill_key` | `app.js` `billKey` | `_bill_order_matches_app`, which runs app.js's own `billKey` in node |
| A plural read as its singular, for the search | `src/pages/build_search_index.py` `stem` | `app.js` `stem` | `_search_index_builds` |
| A bill's Status category | `src/pages/member_figures.py` `CAT_OF_CHIP`, `CAT_OF_KIND`, `status_category` | `app.js` `CAT_OF_CHIP`, `CAT_OF_KIND`, `statusCat` | `_member_figures_passed`, over every chip and kind the nineteen terms carry; `_status_categories` holds `statusCat` to every word `build_site_v2.chip_word` gives |
| Which motion a vote was on | `src/pages/motions.py` `classify` | `src/pages/motions.js` `classify` | `_in_short_twin`, over every roll-call question on disk (`tests/live/in_short_twin.mjs`) |
| A vote said in a sentence, for a session day's In short | `src/pages/build_session_pages.py` `vote_said` | `src/pages/live.js` `voteSaid` | `_in_short_twin` |
| A room in words ("Granite Place 231") | `src/parse/plain_action.py` `place` | `app.js` `roomWords` | `_rooms_in_words`; `_state_library_room` |
| A member's On Record line, the 1989-1998 terms included | `src/parse/member_links.py` `record_spans`, `src/pages/build_legislator_pages.py` `record_spans` | `app.js`, in `renderMemberHead` | `_on_record_covers_the_nineties`; `_former_directory_years_are_the_pages` |
| The sitting term on a day (Organization Day starts the next) | `src/lib/proceedings.py` `term_on` | `app.js` `sittingTerm` | `_bug_hunt_terms_and_dates`, which runs `sittingTerm` in node across the turn of each term |
| What a reader's report is | `src/ops/compile_reports.py` | `functions/api/report.js`, and `app.js`'s report box | `_report_agree`; `_report_function` |
| The hearings a Testify button counts, and whether a bill can still be heard | `src/pages/follow_changes.py` `testify_hearings`, `testify_moving` and the rest of its `testify_*` | `app.js` `testifyButton`; `workers/follow/mail.js` | `_testify_email_in_sync`, which draws both on the same records |
| The changes files the email sender reads | `src/pages/follow_changes.py` (writes them) | `workers/follow/changes.js` (reads them) | `_changes_on_fixture` and `_changes_nights`, which run the sender's own reader, `tests/follow/check_changes.js`, over what the build wrote |
| A livestream's title as comparable words | `src/pages/live_gen.py` `stem`, `session_of` | `workers/live/youtube.js` `stem`, `sessionOf` | `_live_layer`, on every committed title. `live.js`'s own `stem` is held to the Worker's by `tests/live/page.test.js` |
| A party's letter, words and colours | 15 copies: `build_pages.party_word`, `build_elections.chamber_block`, three first-letter rules (`RDILU`) and the translations' English; and the readers that moved onto the table (`build_data.PARTY`, `build_site_v2.PARTY_FULL`, `office_links.PARTY_WORDS` and the rest of `_PARTY_READERS`), which read `state_settings.party_words` and `party_lookup` | `app.js` `PARTY_NAME`, `PARTY_WORD`, `PARTY_COLOR`; `build_pages`' `PW`; `map.js` `PARTY`, `NOUN`; `workers/follow/mail.js` `PARTY_WORDS`; `app.css` and `map.css` | `_party_copies_agree`, against the one table in `src/lib/state_settings.json` ("parties"): each copy says what the table says, but the differences `_PARTY_DIFFERS` lists; `_party_readers_read_the_table` holds each reader to the table's view and nothing else |
| A calendar card: its times, rooms, bills and their order | `src/pages/build_pages.py` (`cal_days`, `calendar_html`) | `app.js` `calendarBlock` | in parts: `_calendar_clock` (times, through the components), `_rooms_in_words`, `_calendar_counts_bills` (a bill counted once), `_bill_order_matches_app` (the order); the kinds of meeting are `WORDBOOK`'s (below) |

## Written once, and copied by the build

Not twins: one source, and a copy the build or a generator writes. Edit the
source, never the copy.

| the source | the copy | held by |
|---|---|---|
| `src/pages/words/*.json` | `components.WORDBOOK`, and `site/components.js` between its `WORDBOOK` markers (`build_pages.with_words`) | `_words_written_once` |
| `app.js` between its `BILLMATCH:BEGIN` and `BILLMATCH:END` lines | `site/billmatch.js`, which `find.js` loads (`build_pages`) | `_search_cases`, which runs the copy |
| `src/pages/live_gen.py`, from where each value is kept | `workers/live/live.gen.js` | `_live_layer` |
| `src/pages/follow_site.py`, from the site's colours and words | `workers/follow/site.gen.js` | `_follow_site_current` |

## Not held by any check

| the rule | where it is written | what holds part of it |
|---|---|---|
| A town's address, its slug and ward | `src/pages/build_town_pages.py` `slug`; `src/fetch/other/fetch_town_clerks.py` `slug`; `src/towns/parse_clerks_csv.py`, which strips a ward's leading zeros; twice inline in `src/pages/build_indexes.py`; `src/pages/map.js` `slugOf` | `_links_resolve` finds a built page for every link `build_indexes` writes; fetch_town_clerks's own `--parse` reports a key that names no page. Nothing reads `map.js`'s links |
| Bill kinds, and their names | `app.js` `TYPE_NAME`, `TYPEORDER`; `build_lsrs.BODY`; `fetch_legislation.KIND_ORDER`; `journal_bills.HOUSE_KINDS`; `state_settings` `BILL_PREFIXES` | `bill_order.KIND_ORDER` through `billKey` (above); `_votes_numbers` holds `app.js`'s `BILL_KINDS` to `find.js`'s `FBILLKIND` and to the kinds the bills carry, a pair within JavaScript |
| The time zone | Python reads `state_settings.TIMEZONE`; "America/New_York" is written in `app.js`, `live.js`, `workers/follow/common.js`, `workers/live/clock.js`, `workers/live/merge.js` and `workers/live/test_mode.js` | `_bug_hunt_clock_and_today` holds the build's own day |
| A `{name}` in the site's words, filled in | `src/pages/i18n.py` `fill`; `components.js` `tr` | none |
| A term worked out from a date, elsewhere in `app.js` | `app.js` (stage0-code.md, section 10, item 8, counted four places on 15 November) | only `sittingTerm` is held (above) |

`app.js`'s `formerName` was the twin of `build_legislator_pages.heading`;
nothing calls it (stage0-code.md, section 3), so it is dead code, not a twin,
and goes with the rest of the dead JavaScript in a later step.
