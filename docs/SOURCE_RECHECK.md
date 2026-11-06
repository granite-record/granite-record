# Rechecking the guides against fresh readings

When the laptop's weekly run has read the state's pages again
(`docs/STATE_SOURCES_RUNBOOK.md`), each guide's claims are checked against
what those pages now say. This is the order, the tool that lists the work,
and what a finding looks like.

The rule it serves is CLAUDE.md's: *a guide or a Learn page says only what a
source on hand says.* A page that has changed under a guide makes the guide
wrong without anyone touching it.

---

## 1. When to start

Once the readings are in the bucket. `python3 src/ops/state_sources.py report`
lists every reading with its day. The check is worth starting when the pages
of the first group below have readings dated after their claims.

Then, on a machine that holds the bucket's keys (the laptop, or a session the
owner has given them):

```
python3 src/ops/state_sources.py down --into <folder>
python3 src/checks/recheck_sources.py --readings <folder> > recheck.txt
```

`down` only reads from the bucket. A cloud session without the keys cannot
run it, and must be handed the folder.

## 2. The order

`python3 src/checks/recheck_sources.py --order` prints it. The list is the
code's (`recheck_sources.ORDER`). As of 6 November 2026 it is 41 guides, the
ones with at least one claim on an agency page:

1. **Voting**: how-to-vote, run-for-office, election-worker
2. **DMV**: renew-drivers-license, new-to-new-hampshire, real-id,
   register-a-car, motorcycle-license, vanity-and-special-plates
3. **Property tax**: property-tax-relief, property-tax-abatement,
   property-tax-bill
4. **Benefits**: food-and-health-assistance, heating-and-electric-help,
   health-insurance, medicare-and-social-security, disability-help,
   child-care-scholarship, file-for-unemployment
5. **Housing, safety and rights**: tenant-rights, landlord-duties,
   homelessness-help, domestic-violence-help, wage-rights, consumer-rights,
   discrimination
6. **Everything else**: vital-records, public-records, passport,
   storms-and-emergencies, car-insurance, homeowners-insurance,
   renters-insurance, fishing-license, hunting-license, boating,
   building-permits, trash-and-recycling, report-a-road-problem,
   who-to-contact, town-warrant-article

**Why this order.** No traffic figures are on hand. The first four groups
are the ones the manager named as the most read. Within each group, the home
page's Common Questions (`guides.HOME`) come first, then the guides that
rest most on agency pages. The five guides about the General Court itself
(attend-a-hearing, submit-testimony, contact-your-legislators, read-a-bill,
tour-the-state-house) rest on no agency page and are not in the list.
Preflight's `_recheck_order` fails if a guide with an agency claim is left
out.

## 3. The worksheet

For each guide, in order, `recheck_sources.py` lists every claim on an agency
page with one outcome:

| Outcome | Meaning | What to do |
|---|---|---|
| `LOOK` | a figure, phone number, form number, count, time or date in the claim's words is not on the page now | compare first: the most likely change |
| `ANCHORS HOLD` | every one of those is still on the page | read the rest of the claim against the page |
| `READ IT` | the claim has nothing a machine can look for | read the claim against the page |
| `PDF: OPEN IT` | the reading is a PDF this machine cannot turn into text | open the PDF |
| `NOT NEWER` | the page was not read since the claim was | nothing yet |
| `NOT READ` | the page has no reading | nothing yet; say so in the report |
| `NOT IN REGISTRY` | the weekly run does not read this page | it rests on a printout (section 7) |

An anchor that holds does not prove the claim still holds. "Must" can become
"may", or a condition can be added, with every number unchanged. An anchor
that is missing does not prove a change either: the page may write "sixty
days" where the claim has "60 days". The outcome says where to look first.
The reader decides.

To read a guide against its pages:

```
python3 src/checks/fact_sheet.py <slug>
```

This prints the guide as it reads, section by section, then its claims
ledger. For each listed claim, read the reading's file and settle it as one
of the four findings below.

## 4. The four findings

- **SAME**: the page still says what the claim records, in substance. The
  guide does not change.
- **CHANGED**: the page now says something different on a point the guide
  relies on.
- **GONE**: the page no longer says it at all. It has moved, become a
  different page, or answers with an error. The reading shows which.
- **UNCLEAR**: the reading cannot settle it. Sections fold shut in the saved
  text, the text is cut off, or the page now hedges where it did not.

A difference is a CHANGED finding only if a reader who followed the guide
would now do something wrong, or miss something they are owed:

- a fee, a deadline, an age, a count of days;
- who qualifies, or what disqualifies;
- a document to bring or a form's number;
- a phone number, an email, an address or office hours;
- "must" becoming "may", or the other way round;
- a step that no longer exists, or a new one before it;
- a link that now leads somewhere else.

A change of wording that the guide does not repeat and that changes nothing
a reader does is not a finding. Record it as SAME, with a note.

## 5. What a CHANGED finding looks like

One block per finding, in the report and in the fix branch's commit
message. The example is made up: it is not a real finding.

```
CHANGED  renew-drivers-license, Step 4 "Pay the fee" (and At a Glance)
  The claim (read 2026-10-17, dmv-licensing-fees):
      "$50 operator, $60 REAL ID operator, $20 non-driver ID"
  The page now (sources/dmv-licensing-fees/2026-11-08.txt):
      "Operator License ... $55"
  Kind:        fee
  The guide prints it: yes (Step 4), held to RSA 263:42 (a guides.FIGURE)
  Statute and page disagree: yes. The guide's figure stays the statute's
               until the law changes; the page is reported to the owner
  Spanish:     guide.renew-drivers-license.* entries that carry it
  Proposed:    the claim's words to the page's; no change to the printed
               figure; a note to the owner that the DMV page and RSA 263:42
               differ
  Needs a printout: yes, before the claim's date moves (section 6)
```

Every CHANGED block names:

- the guide and the place on it;
- the claim's recorded words and the day they were read;
- the reading's file and the words that differ, quoted, not paraphrased;
- the kind of change;
- whether the guide prints it, and whether a statute holds it;
- the Spanish entries that carry it;
- the edit proposed;
- whether a printout is needed first.

A GONE or UNCLEAR finding uses the same block with "The page now" saying
what the reading shows instead.

## 6. What happens next

- **SAME.** Nothing on the page changes. Whether a text reading may move a
  claim's `checked` date is the owner's decision (the runbook's rule 6: "a
  printout or the page itself settles it"). Until they decide, the date
  stays, and the report says "reread <day>, unchanged".
- **CHANGED.** A fix branch off dev, one guide or one theme at a time. In
  the same commit:
  - the claim's words become the page's;
  - the guide's text and its Spanish entries change, the Spanish marked
    draft;
  - `checked` becomes the day of the evidence the owner accepts: the
    reading's day if a text reading is accepted, otherwise the printout's.

  Then the full preflight, as for any change.
- **A change that could cost a reader** (a missed deadline, a wrong fee, a
  lost benefit) while a printout is awaited: tell the manager the same day.
  Holding the guide back is the owner's call. Unsetting the claim's
  `checked` does it, because `guide_ready` holds back a guide with an
  unchecked claim.
- **GONE.** The page's new address comes from the registry or the owner,
  never from a web search. Until then the claim is reported and left as it
  is.
- **UNCLEAR.** The owner prints the page; the printout settles it.

## 7. Pages the weekly run does not read

As of 6 November 2026, 74 of the agency pages the guides rest on are not in
`records/sources/REGISTRY.csv`. The weekly run will never refresh them, and
they still rest on the owner's printouts. They are on 29 hosts, most of
them federal or nonprofit:

| Pages | Host | Guides |
|---|---|---|
| 12 | ecfr.gov | child-care-scholarship, disability-help, medicare-and-social-security, passport |
| 9 | medicare.gov | disability-help, medicare-and-social-security |
| 8 | healthcare.gov | health-insurance |
| 6 | nhcadsv.org | domestic-violence-help, homelessness-help |
| 6 | travel.state.gov | passport |
| 4 | ssa.gov | disability-help, medicare-and-social-security |
| 29 | 23 other hosts, 1 to 3 pages each | |

So passport (12 of 12 agency claims), medicare-and-social-security (17 of
19) and disability-help (11 of 16) get little from the weekly run.
`recheck_sources.py` lists those claims as `NOT IN REGISTRY`. Whether to add
rows for them is the manager's and the owner's call. The registry's rows
are state pages today.

## 8. The report

To the manager:

- one line per guide: its counts of SAME, CHANGED, GONE, UNCLEAR and NOT READ;
- every CHANGED, GONE and UNCLEAR block in full;
- any finding that could cost a reader, flagged at the top.
