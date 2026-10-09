# corrections/

What a person corrects or adds to the record by hand. No script writes here:
`preflight.py` fails if a `build_` or `fetch_` script opens one of these files
for writing, or writes into this folder at all. Each file says inside it whose
it is, what it is for and how an entry is added.

| File | What a person put in it | Read by |
|---|---|---|
| `docket_corrections.json` | dates the docket states wrongly, and rows it files under the wrong bill, with the journal and roll call that settle each | `src/parse/narrative.py` |
| `member_corrections.json` | a member's name or party a generator got wrong, with the evidence | `src/parse/build_data.py` |
| `place_corrections.json` | a polling place the Secretary of State's list states wrongly, and the second source | `src/towns/parse_clerks_csv.py` |
| `bill_notes.json` | what a recurring bill number means: HB 1 has been the budget since 1993 | `src/pages/build_site_v2.py` |
| `ballot_results.json` | the statewide vote on each constitutional amendment, from the source each row names | `src/pages/build_site_v2.py`, `learn_numbers.py`, `build_exports.py` |
| `officials.json` | the Governor, the Executive Councillors and the members of Congress, from four official sources | `src/pages/build_town_pages.py` |
| `status/status.txt` | the state of the session -- session days, deadlines, sine die -- which no published file carries | `src/pages/build_site_v2.py` |
| `status/officials.txt` | the Governor and the Executive Council, for the status box | `src/pages/build_site_v2.py` |

An entry that corrects the General Court's own record is applied only while
the record still says what the entry says it says, and one that has stopped
matching is reported by the step that reads it rather than kept quietly.
