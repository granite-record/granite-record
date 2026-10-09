# src/parse/

Turns what `fetch/` saved, and the `db/` dump, into the facts the site
publishes. Nothing here asks the network. A wrong fact (a vote count, a
sponsor, a committee) is fixed here; a right fact shown wrongly is fixed in
`pages/`.

| Group | Files |
|---|---|
| The day's files and the dump | `build_data`, `dayfiles_from_db`, `docket_from_db`, `document_versions_from_db`, `rollcalls_from_db`, `testimony_from_db` |
| Dockets and histories | `narrative`, `narrate_archive`, `docket_vocab`, `docket_era_1989`, `docket_era_1999`, `docket_era_2007`, `referrals`, `extract_chapters`, `committee_names`, `names`, `committee_details` |
| Votes | `rollcall_parser`, `rollcall_outcomes`, `member_links` |
| People and sponsors | `past_members`, `past_sponsors`, `text_sponsors`, `build_careers` |
| Texts, versions and topics | `archive_text`, `bill_blocks`, `build_bill_versions`, `fiscal`, `topic_model`, `topics` |
| Calendars, journals and reports | `extract_calendar_text`, `extract_amendments`, `extract_vetoes`, `journal_bills`, `journal_days`, `report_check`, `senate_hearing_reports` |
| UNH's scanned journals (no step reads them yet) | `unh_extract`, `unh_measure`, `unh_parse`, `unh_repair`, `unh_rollcalls`, `unh_roster` |

Run by: `build_all.py`'s `plan()`, every night, in its order. The rest are
run by a person when a source changes (`generated/careers.json`, for one) and
write a committed file, so the diff is the review.

Does not belong here: a request (`fetch/`), a proceeding's recording or
timing (`hearings/`), shaping a decided fact for display (`pages/`), and the
towns, districts and counties and their officials (`towns/`).

The files moved here in stages 1 to 4 (`src/README.md`), the last of them
`dayfiles_from_db`, the night's database fallback, in stage 4.
