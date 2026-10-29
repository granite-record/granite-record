# corrections/

What a person corrects or adds to the record by hand. No script writes here:
`preflight.py` fails if a `build_` or `fetch_` script opens one of these files
for writing, or writes into this folder at all. Each file says inside it whose
it is, what it is for and how an entry is added.

| File | What a person put in it | Read by |
|---|---|---|
| `docket_corrections.json` | dates the docket states wrongly, and rows it files under the wrong bill, with the journal and roll call that settle each | `src/parse/narrative.py` |
| `rollcall_corrections.json` | roll calls the roll-call file files under the wrong bill, put under the bill they were on, with the Journal page, the docket rows and the roll call's own fields that settle each | `src/parse/rollcall_parser.py` (`roll_call_bill`, for `rollcalls.json`, for every ballot `build_data.py` keys and for `build_floor_index.py`) |
| `member_corrections.json` | a member's name or party a generator got wrong, with the evidence | `src/parse/build_data.py` |
| `place_corrections.json` | a polling place the Secretary of State's list states wrongly, and the second source | `src/towns/parse_clerks_csv.py` |
| `bill_notes.json` | what a recurring bill number means: HB 1 has been the budget since 1993 | `src/pages/build_site_v2.py` |
| `ballot_results.json` | the statewide vote on each constitutional amendment, from the source each row names | `src/pages/build_site_v2.py`, `learn_numbers.py`, `build_exports.py` |
| `officials.json` | the Governor, the Executive Councillors and the members of Congress, from four official sources; since October 2026 also the Secretary of State, the State Treasurer, the Attorney General, the county officers, the heads of the executive departments and the Supreme and Superior Courts' justices, each with the page it was read from, and a seat's successor with the day they take office (below) | `src/parse/build_members_elect.py`'s `read_officials`, the one reader: the Officials page, the town pages, the district map and `src/parse/officers.py` |
| `members_elect.json` | who a general election's winners are where the name alone cannot say, which races are not final, and a winner held off the pages | `src/parse/build_members_elect.py` |
| `status/status.txt` | the state of the session -- session days, deadlines, sine die -- which no published file carries | `src/pages/build_site_v2.py` |
| `vote_lines.json` | the one-line summary of a vote that names a member (a reprimand, a censure, an expulsion, a member's privileges; shown as a "Misc vote"), approved against the Journal's page; such a vote shows only the Journal's words until a line is here. Empty when it was made, 23 October 2026 | `src/parse/journal_motions.py` |

## A successor in `officials.json`

Since 23 October 2026 any office or seat in `officials.json` may name who
takes it next, under `"elect"`, and every page shows them as the holder from
the day they take office, by the build's own day: nobody edits the file on
the day. Add one once the result is certified, or once the legislature has
chosen (the Secretary of State and the Treasurer, in December). The names,
numbers and day here are made up:

```json
"2": {
  "name": "Jane Roe", "party": "D", "phone": "",
  "official_url": "https://www.council.nh.gov/district-2",
  "elect": {
    "name": "John Doe", "party": "R", "phone": "(603) 555-0100",
    "official_url": "https://www.council.nh.gov/district-2",
    "source": "https://www.sos.nh.gov/...", "read": "2026-11-20",
    "takes_office": "2027-01-07"
  }
}
```

The successor has the fields a holder of that record has, a name first, the
page it was read from, and `takes_office`, the day as `YYYY-MM-DD`. Before
that day the Officials page says under the holder who takes the office and
when; from it the successor is the holder. Nothing of the holder's is carried
over -- a phone, an email, an address -- so give the successor every way to
reach them, the office's own address included where the record has one, as
the Governor's and a councillor's do. What the record says of the office
stays: `office`, `scope`, `about`, `district`, `title`, `department`. A
holder re-elected to their own seat needs no entry. A successor with no name
or no day stops the build rather than guess one, and `preflight` also asks
for the page it was read from, and for an `official_url` where the holder's
record has one.

The day is entered by hand, because nothing on this disk states it for every
office: Congress turns over on 3 January (the US Constitution's Twentieth
Amendment); the state Constitution (Part Second, Articles 42 and 60) has the
votes for Governor and Council laid before the House and Senate on the first
Wednesday after the first Tuesday of January, and names no day for the oath.

Then set `_checked` to the day of that reading. From a week after a general
election, a `_checked` dated before that week was out is a reminder in
`preflight` (`_officials_rechecked`), which on the night warns and never
holds the site.

An entry that corrects the General Court's own record is applied only while
the record still says what the entry says it says, and one that has stopped
matching is reported by the step that reads it rather than kept quietly.
