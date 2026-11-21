# src/pages/

Reads the record (`data/`, the root JSON, `proceedings.csv`) and writes
`site/`: each bill's payload (`build_site_v2`), every page (`shell.py`) and
the frame around it -- the header, the nav, the footer and the head's shared
lines, written once in `chrome.py` for the record pages and the five pages
`build_pages.py` writes alike -- the feeds and the changes files the email sender reads
beside them (`follow_changes.py`), the CSV downloads and the search index.
The browser's files are here too, since stage 5: `bills.html`, the template
every record page is built from, and the `components.js`, `app.js`, `app.css`
and `find.js` it loads. `build_pages.py` copies all five into `site/`, and
the builders read them here under the folder they run in, so a fixture lays
out its own copies the same way. Edit them here; `site/` holds copies --
`app.css` without its comments (`build_pages.strip_css`), and every script
without its comments (`strip_js.py`, through `build_pages.published_js`),
so the comments here are the documentation and cost a reader nothing. It is the one
stylesheet, linked by every page: a new component's rules go anywhere in it
and reach the record pages and the five pages `build_pages.py` writes alike. The district map is a module of its own: `map.js` and `map.css`,
which `build_district_map.py` copies (`map.js` without its comments) beside `/district_map.json`, the one
file the map draws, and which a page mounts with `GRMap.mount()`: the
Officials overview's map and every town page's Map tab.

The hubs (Polish 3, 10 October 2026). The Officials page, `/officials`
(`/legislators` answers with a 301 to it), is `build_pages.py`'s, in six
tabs; its Federal Delegation, Executive Branch (Statewide Officials until 17
October 2026; `#statewide` still opens it), Judicial Branch and County
Officials are drawn by `officials_tabs.py` from `corrections/officials.json`,
which it reads and never writes. The House and the Senate are each a card at the
top of their column of `/committees`, drawn as a committee's card is, and each
card leads to the chamber's page of session days, `/session/house` and
`/session/senate`, beside the day pages: a term picker over every term, the
latest chosen, and that term's days listed as a committee's meetings are,
each leading to its own page. Both are `build_full_sessions.py`'s, a step
after both chambers' session pages: it fills the slots `build_committees.py`
writes at the top of the columns, because the term files it reads
(`site/session/<H|S>/<term>.json`) are written after the committees.

The statutory and study committees (18 October 2026) are
`build_study_committees.py`'s: a page for each one the General Court lists as
active, at `/committee/ss<CommitteeID>`, read from the database copy in `db/`
(`StatStudDetails`, `StatStudMembers`, `StatStudMeetings`, `vStatStudTemp`),
and `site/study_committees.json`, a line each, for the steps after it. It
runs after the Laws pages, whose
headings name each committee's statute, and shares the Calendar's reading of
each meeting (`build_calendar.statstud` and `study_recordings`), so a card and
the page play the same recording.

The address box's suggestions (24 October 2026) are `build_addr_index.py`'s:
`site/addr/<key>.json`, New Hampshire's streets from
`collected/nh_streets.json` in about 350 files named by a street's first two
letters, which `find.js` fetches as a reader types in the Your town panel and
matches in the browser, so the Census is asked only for the address chosen.

The components are in two files with the same helpers under the same names
(9 October 2026): `components.py`, which the builders draw a person, a
committee, a chip, a date and a time with, and `components.js`, which every
page loads in its head before any script of its own, for what the browser
draws. A helper is pure and thin: a plain value in, a string out. `preflight`
runs both on every case in `tests/components_cases.json` and fails where they
answer differently, where one has a helper the other has not, and where any
part of a helper is reached by no case. The components are one pair of
several: `src/TWINS.md` lists every rule written both here in Python and in a
browser's or a Worker's script, and the check that holds each.

Every chip but a person's is `chip(word, classes, size)`: a bill's status, a
meeting's kind, a vote's result, a party's letter, the sign-ins, the finder's
kind and a version of the text, in the person chip's frame (3px corners, a
1px edge, a 3px bar in the chip's ink) at 14px, or 16px in a head (`"m"`).
`app.css` draws it once; the classes beside `chip` are
the family that colours it and the hook a page places it by. Its words are in
Title Case, written so where they are made, and a record's own capitals go
through `title_words`, which keeps the record's own abbreviations in capitals
(`chips.json`'s `capitals`). `preflight` fails a chip written by hand and any rule
that gives one a shape of its own.

The words the pages say are in `words/`, one JSON file to a kind (9 October
2026): `chips.json` (the chip's words and the class that colours each, and
the Status filter's categories), `meeting_kinds.json` (the kinds of meeting and
their colours), `votes.json` (the vote words the person approved) and
`glossary.json` (the record's shorthand, for the term popovers). Each keeps
its reasons under `_about`. `components.py` reads them as `WORDBOOK`, and the
build writes the same into `site/components.js` between its `WORDBOOK:START`
and `WORDBOOK:END` lines (`build_pages.with_words`), so the copy here holds
none of them and nothing types a table of words twice. Change a word in its
file; `preflight` holds the browser's `WORDBOOK` to Python's.

The site in Spanish (23 October 2026) is `i18n.py` and `lang/es.json`. A
piece of the site's own words is written `say(lang, "key", "English")` in a
builder or `tr("key", "English")` in a script; the catalog keeps each key's
Spanish beside the English it was translated from, and a page uses it only
while that English is still the code's, so a translation can never outlive an
edit to its English. The record's own words (titles, names, docket lines) are
not translated. The home page is built at `/` and `/es/` from the same data;
the header, footer and Settings speak the page's language; the language
choice is a row of Settings (`find.js`, `langMount`) and the browser's
language is read before the first paint (`chrome.lang_head`). Spanish stays
unlisted until `"offered"` is set in the catalog. `docs/TRANSLATING.md` is the
walk-through, and `src/ops/translations.py` the proofreader's sheet.

A bill's print sheet is `print.js` and `print.css` (9 October 2026): a
reference sheet of the bill's record for paper, composed in the reader's
browser from the record the page already holds, beside a short menu of
settings, with a QR code to the bill's page and each change to the text
numbered by the amendment that made it. A bill's page mounts it with one
call, `GRPrint.open(record, row)`, from its Print button; `print.css` is
loaded the first time it opens. The bill's text is an option, unticked every
time it opens (the person, 10 October 2026); ticked, it prints whole, and the
menu says how many pages the sheet prints on Letter and on A4, counted by
laying the sheet out again in columns a printed page's size. It draws with
`components.js` and reads
`app.js`'s own tables, so it formats nothing of its own; `preflight` composes
it in node on the real records of `tests/print_cases.json` with every
section present and absent.

Run by: `build_all.py`'s `plan()`, after the record is built. A new page is
`build_<page>.py` on `shell.py` plus one `Step()`.

`front_end.py` is the fast path, `python3 build_all.py --front-end`: a change
to `app.css`, `components.js` (and the words in `words/`), `app.js` or
`find.js` alone, put into the site the last full
build made in seconds, through `build_pages.front_end`, the function the
build itself calls. It refuses, naming the file, when anything else the
build reads has moved since that build (`src/lib/build_inputs.py` keeps the
record), and it refuses a change to `bills.html`, which every page is built
from. A builder that starts making something of one of those three files is
taught to `front_end.py` and named in preflight's `FAST_PATH_READERS`.

## Every file here, by kind

One line each (the refactor's stage 1, 19 November 2026; each file's own
docstring or head comment says the rest). A `build_*` file is a step
`build_all.py` runs by name unless its line says otherwise; the rest are
imported. The folder is flat, so the groups are only here.

The record and its own pages:

- `build_site_v2`: the record builder -- each bill's payload and the bill
  index, and the legislators', towns' and committees' files the pages after
  it read (there was never a v1 here); its journey, a bill's status, the
  proceedings' stations, the members, the conferences, the amendments, the
  rail's endings, the committee and hearing reports, the sponsors, a bill's
  topic, what a bill amends, its roll calls, a CACR's ballot, the database's
  statuses, its documents, the docket lines it tells, its disposition, the
  session's panel and the related bills are modules of their own beside it
  since 20 November 2026 (the next nineteen lines), and it imports every
  name of theirs back;
- `journey`: the passage rail and the journey -- the four stops a bill passes
  (`passage`) and what each chamber decided and when (`journey`,
  `journey_rail` and the `_j_` readers), read from the docket for the rail's
  dated stops and How it got here; a section of `build_site_v2` until 20
  November 2026, which imports every name of it back;
- `status`: a bill's status -- the General Court's status words read against
  what a bill of each kind has to clear, the docket where the status page
  does not cover a bill (`classify`), a closing paragraph for an ending the
  docket never tells (`closing_stage`) and what happens next (`next_step`); a
  section of `build_site_v2` until 20 November 2026, which imports every name
  of it back;
- `stations`: a proceeding as the station a bill's page draws -- a committee
  sitting or a floor appearance placed on its recording by the chair's stated
  boundary, the clustering estimate or the schedule -- and the caption times
  out of step with their recording withheld first (`withhold_late_captions`);
  a section of `build_site_v2` until 20 November 2026, which imports every
  name of it back;
- `members`: a member as the site has them -- the one way of naming a
  member (`member_labels`), the address of their page (`member_slug`,
  `own_slug`) and the names a record prints read into one form
  (`person_name`, `sort_name`); the roll calls and the floor as a member's
  record reads them (`write_rollcall_index`, `term_seats`,
  `write_floor_record`); and the members' own files: former members and
  their kept addresses, attendance, the officers and the legislator pages'
  files (`build_legislators`); sections of `build_site_v2` until 20 November
  2026, which imports every name of them back;
- `conferences`: what the two chambers did with each other's version of a
  bill -- a concurrence, a committee of conference and how it ended -- read
  from the docket; a section of `build_site_v2` until 20 November 2026, which
  imports every name of it back;
- `amendments`: a bill's amendments and its text -- the amendments the docket
  moved, in the order it took them up, with what each says it changes
  (`bill_amendments`, `amendment_targets`), and the text the General Court
  printed, its analysis told apart from the bill (`bill_text_block`); a
  section of `build_site_v2` until 20 November 2026, which imports every name
  of it back;
- `endings`: the rail's endings -- a bill the session's end killed with no
  vote, left on the table (`table_death`) or held for interim study
  (`study_ending`, with the study committee's report, `interim_report`) --
  and the days each chamber sat, which date them (`chamber_sittings`); a
  section of `build_site_v2` until 20 November 2026, which imports every name
  of it back;
- `hearing_reports`: what a bill's committees reported and who spoke at its
  hearings -- the committee reports the calendars printed, read beside the
  docket (`committee_reports`), the interim study statements as cards
  (`interim_cards`), a public hearing's sign-ins (`hearing_testimony`) and
  the Senate's written hearing reports, their speakers matched to members
  (`attach_hearing_reports`); a section of `build_site_v2` until 20 November
  2026, which imports every name of it back;
- `sponsors`: the members a bill's record names -- its sponsors, each with the
  seat and the party the term's Manual gives where the General Court's own
  record has none (`bill_sponsor_list`, `manual_seats`, `manual_parties`),
  and the members its docket names: each ballot's voter (`vote_member`), a
  motion's mover (`mover_member`), a committee report's author
  (`report_authors`); a section of `build_site_v2` until 20 November 2026,
  which imports every name of it back;
- `bill_topics`: a bill's topic as the bill index files it -- the topic
  model's answer for the terms the General Court gave none
  (`merge_guessed_topics`) and the site's one vocabulary applied to every
  bill last (`unify_vocabulary`); a section of `build_site_v2` until 20
  November 2026, which imports every name of it back;
- `bill_statutes`: what a bill's text says it changes -- the statutes its
  clauses amend or repeal (`bill_amends`), as against every statute it
  mentions, and the articles a CACR amends (`constitution_targets`); a
  section of `build_site_v2` until 20 November 2026, which imports every
  name of it back;
- `bill_votes`: a bill's roll calls as its Votes tab draws them -- a day's
  votes in the order they happened with the amendments named
  (`vote_chronology`), every recorded vote on one bill (`bill_rollcalls`)
  and the note above the table -- and the card of a roll call on no bill,
  a term to a file (`write_nobill_cards`); a section of `build_site_v2`
  until 20 November 2026, which imports every name of it back;
- `cacr_ballots`: a constitutional amendment's ballot -- the election its
  text names, the voters' answer where the docket records none
  (`corrections/ballot_results.json`, `load_ballots`), its line of How it
  got here and its card (`ballot_step`, `ballot_card`) and what a CACR both
  chambers passed now says (`cacr_to_the_voters`); a section of
  `build_site_v2` until 20 November 2026, which imports every name of it
  back;
- `db_status`: the General Court database's status codes where the status
  page states nothing -- the dump's codes in the page's words, a term read
  from whichever dump holds it (`db_statuses`), the terms no dump holds
  (`no_dump_for`) and a record's blank fields filled from it
  (`fill_status_from_db`); a section of `build_site_v2` until 20 November
  2026, which imports every name of it back;
- `documents`: what a bill's page cites and lists of its record -- a docket
  line's citation and plain words (`_cite`, `_with_plain`), the documents a
  reader can open (`bill_documents`), the story of a bill whose record is
  the House Journal's (`journal_story`) and the notes on where a record
  comes from (`record_notes`); a section of `build_site_v2` until 20
  November 2026, which imports every name of it back;
- `docket_told`: a bill's docket lines and the stages its history tells --
  the routine rows (`is_routine`), the days it was acted on
  (`action_dates`, `carried_over`), the stages told (`stages_told`), the
  lines its page lists (`docket_lines`), the status box once a term has
  closed (`settled_step`) and its chapter of the session laws
  (`chapter_of`); a section of `build_site_v2` until 20 November 2026,
  which imports every name of it back;
- `disposition`: what became of a bill and where that answer came from --
  its disposition (`bill_disposition`, a `Disposition`), the chamber it
  started in (`origin_of`), a measure of a finished term that cannot still
  be moving (`ended_with_the_term`) and the test that its journey, status
  and rail tell one story (`journey_disagrees`); a section of
  `build_site_v2` until 20 November 2026, which imports every name of it
  back;
- `session_status`: where the session is -- the day the current term ran
  out of session days, as `corrections/status/status.txt` states it
  (`session_over`, `session_over_in`), and the site's panel of where the
  session is (`build_status`); a section of `build_site_v2` until 20
  November 2026, which imports every name of it back;
- `related`: what `main` adds to the bills' pages after the loop -- a
  standing note where a bill's number carries a meaning across terms
  (`bill_note`, `check_notes`), the related bills (`add_related`), the same
  number in other terms (`add_same_number`) and the tags while the owner's
  registry is in force (`site_tagging`); a section of `build_site_v2`
  until 20 November 2026, which imports every name of it back;
- `sponsor_roster`: the members the bill search's Sponsor filter lists, a
  file a term (`site/sponsors/`), which `build_site_v2` collects and writes;
- `build_bill_pages`: an address for every bill, `/bill/<year>/<bill>.html`,
  and their sitemap;
- `build_legislator_pages`: an address for every sitting legislator;
- `build_committees`: a page for every committee;
- `build_study_committees`: a page for every active statutory and study
  committee, from the database copy in `db/`;
- `build_town_pages`: a page per town and ward, everyone who represents it;
- `town_elections`: each town page's Elections tab, every race on the town's
  ballot by year, from the results files the elections pages read;
- `build_lsrs`: next session's bill requests, as a term the bill search can
  open;
- `build_request_pages`: a page for each of those bill requests;
- `build_elect_pages`: a provisional page for each member-elect;
- `build_elections`: each general election's official results, a page each,
  under Officials;
- `build_member_elections`: the Elections tab of each member's own file.
- `election_margin`: a race's margin, defined once: the label, band and figures every
  election card, filter, order and summary takes.

The hubs and the sections:

- `build_pages`: the home page, Officials, the town lookup, how it works and
  about; it copies the browser's files into `site/`, holds the fast path's
  function, and is a library some builders import;
- `officials_tabs`: the Officials page's tabs that are not the legislators',
  which `build_pages` draws;
- `officials_overview`: the Officials overview, the page the section opens
  on -- the Legislature's seat bars (the incoming legislature's while there
  are members-elect), the map and a block a branch -- which `build_pages`
  draws first;
- `build_calendar`: the General Court's week, a page a week;
- `build_session_pages`: a page for every day the House or the Senate sat;
- `build_full_sessions`: the House and the Senate as committees of the
  whole, `/session/house` and `/session/senate`;
- `build_nobill_votes`: a page a term of the votes not on a bill;
- `build_votes`: every roll call since 1999, a file a term, for the votes
  search;
- `build_votes_page`: `/votes`, the page that search is drawn on;
- `build_rsa`: the statutes, `/laws` and a page a chapter;
- `build_civics`: the Learn hub and its pages, and the How-To guides;
- `build_district_map`: the district map's data, with `map.js` and
  `map.css` copied beside it;
- `build_addr_index`: the address box's street suggestions, `site/addr/`;
- `build_indexes`: the whole record as plain lists a crawler can follow;
- `build_search_index`: what each bill is about, in its own words, for the
  search (`site/sidx/`).

The downloads, the feeds and the data API:

- `build_exports`: the CSV downloads and `data.html`, and the data API
  through the four `api_*` modules;
- `api_db`: the API's SQLite database of every table;
- `api_records`: the API's records, a file each, under `/api/`;
- `api_schema`: `/data/schema.json`, what every API file holds;
- `api_page`: `/api`, the API's documentation page;
- `build_feeds`: the RSS feeds;
- `follow_changes`: the nightly changes files the email sender reads, and
  the first-seen ledger (`build_feeds` calls it).

The live layer, and the Workers' generated files:

- `build_live`: Live Now, `/live`, and its schedule;
- `build_live_session`: the session days' side of the live layer;
- `live_hook`: the live-stream slot at the top of a committee's page;
- `live_gen`: writes `workers/live/live.gen.js` from where each value is
  kept (run by a person; `--check` says whether it is current), and holds
  the Worker's rules `build_live` and `build_live_session` import;
- `follow_site`: writes `workers/follow/site.gen.js`, the site's colours
  and words for the email sender (run by a person; `--check` likewise).

The words, kept as Python data:

- `guides`: the How-To guides, their sources and what each was checked
  against;
- `civics`: the Learn pages' order, names and prose;
- `learn_numbers`: the Learn page of the record in numbers;
- `legislative_year`: the legislature's year as a timeline, a Learn page;
- `key_dates`: elections, town meeting day and the legislature's deadlines,
  each with its source;
- `about_figures`: the figures `about.html` states, counted.

The helpers the builders share:

- `parts`: what more than one builder draws with -- a day of the Calendar's
  cards and what one meeting is (`cal_days`, `meeting_key`), Latest
  activity's sizes, a party's word, a district's tag, a number, address or
  link that works, the tab strip's script, and the pieces of `build_site_v2`
  the modules split from it share (what a bill of each kind has to clear, a
  bill's letters, the chip's six words, the docket line) -- named where each
  was too;
- `shell`: the page every record's own address is, `bills.html` with one
  record open;
- `chrome`: the frame every page shares -- the head, the header with its
  second row of each section's pages (`ROWS`) and the phone's menu, the
  footer with its map of the site, and the closing scripts;
- `components`: what the builders draw a person, a committee, a chip, a
  date and a time with (the twin of `components.js`), and `WORDBOOK`;
- `i18n`: the site in Spanish, and how a translation stays current;
- `translation_audit`: every word the code asks to be translated, read from
  the source, and each catalog checked against it (preflight's and
  `src/ops/translations.py`'s; no builder imports it);
- `strip_js`: the browser's scripts as published, without their comments;
- `inline_js`: a builder's own scripts, read from `inline/` with their
  holes filled, for the builder to write into its pages;
- `structured`: what a search engine is told a page is about (schema.org);
- `bill_order`: the order bill numbers are listed in;
- `ballot_source`: whose count a ballot result is, in words;
- `member_figures`: the figures a member's page heads a term with;
- `motions`: which motion a vote was on (the twin of `motions.js`);
- `committee_acts`: what a committee did to each bill at each meeting;
- `session_days`: a sitting day of either chamber, assembled from what is
  already parsed;
- `vote_passage`: the Journal's words for a vote on no bill;
- `latest_activity`: what the home page's Latest Activity holds;
- `calendar_documents`: the calendar and journal PDFs the Calendar's picker
  lists;
- `queue_links`: those PDFs' addresses, found in the drain's queue;
- `rsa_links`: where a statute citation links;
- `constitution_tab`: the Constitution as a tab of the Laws page;
- `constitution_history`: an article's History and citations fold there;
- `seating`: the House floor's seats, as a diagram.

Run by a person, not by a step:

- `front_end`: the fast path, `build_all.py --front-end`;
- `app_parts`: `app.js` written from its parts in `app/` (and an edit made
  in `app.js` carried back into them with `--split`);
- `build_brand`: the drawn logo and icon into `assets/`, once.

The browser's files, copied into `site/` (scripts without their comments):

- `bills.html`: the template every record page is built from;
- `app.js`: the bill search and every record page's script, written from
  its parts (below);
- `app.css`: the one stylesheet;
- `components.js`: the browser's components, loaded first on every page;
- `find.js`: Find anything, from the header; the phone's menu, the row's
  mark on a hub's open tab (`rowMount`), and the footer's map folding on a
  phone (`smapMount`);
- `print.js` and `print.css`: a bill's print sheet;
- `map.js` and `map.css`: the district map;
- `live.js` and `live.css`: Live Now;
- `motions.js`: which motion a vote was on, for the live session page.

`app.js`'s parts (20 November 2026):

- `app/`: `app.js` in the pieces its own headers mark -- the bill's
  facts, versions, report a problem, member and committee, the videos,
  boot, the votes page -- each a file named `NNN-what.js`, and each
  `BILLMATCH` region, the lines `site/billmatch.js` is cut from, a part of
  its own (`NNN-billmatch-what.js`). `app.js` is its first line, its
  version stamp, and then the parts in the order of their names, byte for
  byte, and stays in the repository: edit the part, then run
  `python3 src/pages/app_parts.py`. Everything reads `app.js`, never a
  part (preflight's `_app_js_is_its_parts`); the parts carry no stamp of
  their own, so a part changed is `app.js` changed.

A builder's own scripts, written into its pages (20 November 2026):

- `inline/`: what was a JavaScript string in a builder -- a filter, a tab
  strip, `chrome`'s theme and language scripts -- a `.js` file each, named
  for the builder: `<builder>.js`, or `<builder>.<what>.js` where it has
  more than one. The builder has it through `inline_js.script(name)`, which
  fills each hole written `__NAME__` and refuses one left empty, and writes
  it into its page exactly as the string held it, comments and all: so a
  file carries no version stamp, and no comment the page should not carry.
  Nothing copies these into `site/`, and no bare name finds one. Each is
  read by its own builder alone (preflight's `_inline_scripts_read_once`);
  `src/checks/inline/` holds the bench's page script and `drawn_pages`'
  driver the same way. Three strings stay where they are, each a patch
  or a head rather than a page's script, with its reason in preflight's
  `_INLINE_KEPT`: the Spanish pieces of the Calendar's script and of its
  picker (`build_calendar.WEEK_ES`, `calendar_documents.PICKER_ES`) and the
  head of `site/billmatch.js` (`build_pages.BILLMATCH_HEAD`).

The data beside the code:

- `words/`: the words the pages say, one JSON file to a kind --
  `chips.json`, `meeting_kinds.json`, `votes.json`, `glossary.json`,
  `closing.json` (a session day's closing line), `study_report.json` (an
  interim study committee's report) and `follow_beta.json` (the email
  following's beta note);
- `lang/es.json`: the Spanish catalog;
- `lang/terms.es.json`: one Spanish word for each English term, which
  preflight holds the catalog to.

Asks nobody. Does not belong here: deciding a fact (`parse/`). This folder is
the code; `site/` at the root is what it writes. (Not `src/site/`: the
`site/` line of `.gitignore` would hide a folder of that name at any depth.)

The files moved here in stages 2, 3 and 5 (`src/README.md`): the helpers the
page builders import in stage 2, the fourteen builders `build_all` runs as
steps in stage 3, and the browser's four files in stage 5.
