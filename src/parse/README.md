# src/parse/

Turns what `fetch/` saved, and the `db/` dump, into the facts the site
publishes. Nothing here asks the network. A wrong fact (a vote count, a
sponsor, a committee) is fixed here; a right fact shown wrongly is fixed in
`pages/`.

| Group | Files |
|---|---|
| The day's files and the dump | `build_data`, `bill_text_from_db`, `dayfiles_from_db`, `docket_from_db`, `document_versions_from_db`, `rollcalls_from_db`, `testimony_from_db` |
| Dockets and histories | `narrative`, `narrate_archive`, `docket_vocab`, `docket_era_1989`, `docket_era_1999`, `docket_era_2007`, `referrals`, `later_referrals` (every committee a chamber sent a bill to, in order, where `referrals` reads the first; `learn_numbers` counts with it), `adopted_amendments` (what a passed bill's docket says was done to its text, and which committees reported on it; `learn_numbers` reads it), `plain_action` (a docket line in plain words, beside the clerk's own), `extract_chapters`, `committee_names`, `names`, `committee_details` |
| Votes | `rollcall_parser`, `rollcall_outcomes`, `member_links`, `journal_motions` (what the Journals say a vote on no bill was about: `journal_motions.json`) |
| People and sponsors | `past_members`, `past_sponsors`, `text_sponsors`, `past_roster`, `build_manual_seats`, `past_roll`, `build_past_roster` (1989-1998: a printed sponsor placed by the bill's own sponsor record, two numbers of one surname told apart by the Manual's seat list of the term, the House's call of the roll as a second source, and `generated/past_roster.json`), `build_careers`, `officers`, `build_members_elect`, `parse_sos_results`, `score_members_elect`, `parse_sos_offices` (the Secretary of State's results for the other offices, read into `collected/election_offices_<year>.json` with their tie-out; nothing reads them yet), `parse_sos_primary_results` (the State Primary's House and Senate races, each party's its own, read into `collected/primary_<year>.json`; nothing reads them yet), `parse_sos_primary_offices` (the State Primary's other offices, read into the same file), `parse_sos_specials` (the Secretary of State's special elections for State Representative, October 2019 on, read from its pages as a person saved them into `collected/specials.json`, in the model's contest and candidacy shapes, no address kept; run by a person on the laptop, where the pages are), `election_town_rows` (the town and ward rows of the House and Senate results, kept in `collected/election_town_rows_<year>.csv` and held to the Totals; `parse_sos_results` and `parse_sos_offices` hand it what they read), `parse_sos_questions` (the Secretary of State's count of the ballot questions, read into `collected/ballot_questions.json`; run by a person) |
| The model of people, offices, terms, districts and elections | `build_entities` (the build's last step: writes `data/entities/` from the files above and the hand files, and nothing reads it yet; preflight holds that each of today's files is a view of it), `office_links` (the rule that links a holder of an office the legislature does not fill to a person of its record, and the check that works each link out again; `build_entities` runs it) |
| Texts, versions and topics | `archive_text`, `bill_page`, `bill_blocks`, `build_bill_versions`, `build_version_links` (each amendment's number and where each cited statute links, into the version indexes), `related_bills` (which bills and amendments share their proposed language: `related_bills.json`), `fiscal`, `law_effect`, `topic_model`, `topic_vocabulary` (the category a topic name ends up under, and the chapters a bill's text changes, which split two names; build_site_v2 and request_topics read it), `topics`, `official_topics` (the General Court's own subject code as an archived bill's topic, from `db/past/`), `request_topics` (a bill request's topic from its title, topics.py's classifier, build_lsrs reads it), `tag_rules`, `tag_counts` (tags: the rule engine and its counts and bench samples; nothing in the build reads them yet) |
| Statutes and the Constitution | `rsa` (the General Court's statute table read once, the one reader of statute citations, and `rsa_citations.json`), `parse_constitution` (the Constitution, read into `collected/constitution.json` from the saved pages; run by a person, and read by the builders through `load()`), `constitution_citations` (which bills proposed to change each article, and which bills and statutes cite it: `constitution_citations.json`) |
| Calendars, journals and reports | `extract_calendar_text`, `extract_amendments`, `extract_vetoes`, `journal_bills`, `journal_days`, `resolution_sponsors`, `report_check`, `senate_hearing_reports`, `sos_archives` (the committee files' archive address each saved docket and status page prints, into `collected/sos_archives.json`), `interim_statements` (what each House committee said of the bills it held for interim study, from the autumn House Calendar: `interim_statements.json`) |
| UNH's scanned journals (no step reads them yet) | `unh_extract`, `unh_measure`, `unh_parse`, `unh_repair`, `unh_rollcalls`, `unh_roster` |

Run by: `build_all.py`'s `plan()`, every night, in its order. The rest are
run by a person when a source changes (`generated/careers.json`, for one) and
write a committed file, so the diff is the review.

Does not belong here: a request (`fetch/`), a proceeding's recording or
timing (`hearings/`), shaping a decided fact for display (`pages/`), and the
towns, districts and counties and their officials (`towns/`).

The files moved here in stages 1 to 4 (`src/README.md`), the last of them
`dayfiles_from_db`, the night's database fallback, in stage 4.
