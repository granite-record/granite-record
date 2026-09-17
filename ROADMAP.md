# Granite Record — roadmap

> **Read `LAUNCH.md` first.** It was written on 9 September by measuring the
> site, and it supersedes this file wherever the two disagree. What is kept
> here is the reasoning behind decisions — why the committees page was cheap,
> why the testimony form cannot be deep-linked, what the probes found — which
> is still worth having and does not go stale the way a task list does.
>
> Two things below are now wrong and are left in place because the reasoning
> around them is not: the file cap is 100,000 rather than 20,000 and the site
> uses far more of it than the 40% this line used to state -- `python3
> check_site.py` prints the file count and warns at 90,000, so take the share
> from it -- and the archived terms have full pages rather than cards.
>
> **Read through on 17 September**, against the code and the data on disk.
> Where something here was measurably wrong it is corrected in place and
> dated; the reasoning is untouched, including the reasoning behind decisions
> since taken the other way. `LAUNCH.md` has been kept current since the 9th
> and now runs to the 17th, so it is still the newer answer.

Written 6 September 2026, from a list of everything outstanding. Ordered by
what blocks what, not by size. `ARCHITECTURE.md` has the reasoning behind the
structural items; this places them among the rest.

Three things worth saying before the list.

**The consolidation has already paid for one of the biggest items.** The
committees page described below was expensive a week ago and is nearly free
now: `proceedings.csv` holds one row per (bill, date, kind, recording) with
committee, times and boundaries on it, which is exactly the shape that page
needs. It did not exist on Thursday.

**The archive probe belongs early, not late.** Two past terms and a handful of
gentle requests — though the script that asks the structural question has yet
to be written, so it is a short build plus the requests, not requests alone.
It tells you whether bill numbers, docket shapes and URL
patterns have held since 2005 — and both of the two big archive decisions
(term keying and the file cap) are being made on assumptions that probe would
confirm or destroy. Doing it after building is how you build twice.

**Nothing here should go out before `probe_alignment --truth` is clean.** That
rule has not changed and gets easier to forget as the work moves away from
timestamps.

---

## A committee's day as one session

Not built. Recorded because the timestamp work now underway is what it is
built on, and one decision there was made for its sake.

The idea: a committee page shows a day's livestream once, and under it the
bills in the order the committee took them, each with its start and its end,
and a short account of what the committee did that day across its hearings,
executive sessions and work sessions. Someone following a committee could then
find the twenty minutes they care about in a five-hour recording, instead of
scrubbing or opening five separate bill pages.

What it needs is the recording seen as a whole rather than as a set of
per-bill lookups: the order, and the gaps between items. `candidate_segments.json`
was `{video: {bill: [...]}}`, which carries neither. It now also carries
`_sequence`: per recording, the spans in the order they happened, with the
bill, what kind of proceeding it was, and how the boundary was found. That is
the whole input this view needs, and it cost nothing to write while the
segmentation was being computed anyway.

The rest is a page. It needs `committees.json`, which fetch_committees.py has
never been run to produce -- see the committee pages item above.

**`committees.json` has been on disk since 7 September** -- 41 committees, 27
House and 14 Senate, each with chair, vice chair, aide, room and phone -- and
the committee pages below were built on it. This view of a recording as a
whole is the part still not built.


## Idea box: following a session live

Not feasible in the short term, and parked rather than dropped.

The idea: on a session day, a page that lists the bills in the order they are
being taken, says which one is on the floor now, marks one "just voted" and the
next "coming up", and fills in roll calls as they are read out -- so somebody
tuning into the livestream partway through can tell what they are watching. The
committee version is the same thing around a hearing or an executive session.

What makes it hard is not the display. It is that this site is files on a CDN
with no runtime, deliberately, and a live view is the one feature that cannot be
a static file. It would need a second, small, live surface -- one endpoint the
page polls -- which is a different operational commitment from a nightly build:
something has to be running, watched, and correct while nobody is looking at it.

What was measured on 6 September, before parking it:

  The database DOES carry the vote's real clock time. The House's VoteDate is
  the moment of the vote (15:37:01 on roll call 329), and sequence numbers run
  in order within a day.

  Publish latency CANNOT be measured from the data. rollcallhistory has a
  DateModified but it is null on every House row, so nothing records when a row
  was written. The claim that GenCourt publishes within seconds of the vote
  being read is plausible and untested; it can only be checked by watching
  during a session, which needs a session to be sitting.

  There is nothing to watch right now. The last roll call was 19 August 2026,
  the last hearing sign-in 4 May, the last committee report 15 June. The
  earliest this could be observed is the next session day.

  VHearings carries CommitteeMeetingID, HearingTypeID, cname, starttime,
  endtime, ChamberCode and LegislationID -- which is the "what is scheduled,
  and is it a hearing or an executive session" half, already available.

So the honest order is: observe one session day and measure the real latency
before designing anything, and only then decide whether a live surface is worth
what it costs. Nightly remains frequent enough for amendments, reports and
everything else.


## Upcoming hearings, and submitting testimony: what the probes found

Four requests to gc.nh.gov on 8 September, one at a time. Everything below was
read off the responses, not inferred.

### The testimony form cannot be deep-linked. This is settled, not suspected.

`house/committees/remotetestimony/default.aspx` is the submission form, and it
is five steps: personal details, **a date**, a committee, a bill, a position,
an optional upload.

Step 2 is an ASP.NET `Calendar` control — `pageBody_calHearingDate`, a table of
days whose every cell is
`javascript:__doPostBack('ctl00$pageBody$calHearingDate','V9709')`. Choosing a
day posts back and populates `ddlCommittee`; choosing a committee posts back
and populates `ddlBills`. On a fresh load **both of those selects hold zero
options**, because nothing is chosen yet.

The second request supplied `?committee=10&bill=HB1442&date=2026-02-20&
hearingdate=2026-02-20&lsr=2729`. The page came back **identical**: committee
0 options, bills 0 options, no day selected, name field empty. The query
string is ignored, which is the ordinary behaviour for this page style and is
now measured rather than assumed.

**So no link can pre-fill the calendar, the committee or the bill.** The
honest thing to build is a link to the form with the three values printed
beside it for the reader to choose, and no pretence that it does more.

### The schedule is a JSON web service, and it is the better source

`house/schedule/dailyschedule.aspx` is a FullCalendar page, and its events come
from one AJAX call with no parameters, no ViewState and no postback:

    GET https://gc.nh.gov/house/schedule/CalendarWS.asmx/GetEvents

It answers with every scheduled meeting:

    {"title":"House Ways and Means : GP, Room 234",
     "start":"2026-09-10T10:00:00","end":"2026-09-10T16:30:00",
     "backgroundColor":"#2980B9",
     "url":"eventDetails.aspx?event=3027&et=1","allDay":false}

- `backgroundColor` **is the kind**, per the page's own legend: `#2980B9` blue
  is a hearing, `#66A362` green a meeting, orange an executive session, red a
  committee of conference.
- The title carries `==REVISED==` and `==CANCELLED==` markers inline, which the
  docket has as `==FLAG==` and the site already models.
- `url` is an event id and a type.

And the event page carries the bills, at their times:

    GET house/schedule/eventDetails.aspx?event=3027&et=1

    Date Sep 10, 2026 · Time 10:00 AM - 04:30 PM · Granite Place · Room 234
    HOUSE WAYS AND MEANS
      10:00 AM  HB1648  providing property tax exemptions for qualifying residences.
      10:00 AM  HB1787  modifying the statewide education property tax.
      10:00 AM  HB1800  relative to statewide education property taxes.

Committee, room, date, a time range for the sitting and a time for each bill.
That is the whole of what a committee page needs to show an upcoming day, and
what a calendar view needs to let someone find a hearing worth attending.

**Cost: one request for the whole schedule, then one per event.** Currently
about 40 events are listed; in session it will be tens a week. This is a
nightly job of a few dozen requests, not a crawl.

### What this changes about the plan

The House calendar `COMMITTEE MEETINGS` sections are still worth parsing — they
are the legal notice, they are on disk for 150 calendars already, and they are
what gives a hearing a **publication date**, which is what opens the testimony
window. But they are the *historical* record. For anything upcoming,
`CalendarWS` is better in every way: it is JSON, it is current, it states the
kind, and it names the bills at their times.

So the two sources do different jobs:

| | source | gives |
|---|---|---|
| what is coming | `CalendarWS.asmx/GetEvents` + `eventDetails.aspx` | the schedule, the room, the bills and their times |
| when it was noticed | House calendar `COMMITTEE MEETINGS`, on disk | the publication date the testimony window opens from |
| what happened | the docket, as now | the record |

### And the reason none of it can be seen working yet

No hearing on this disk is in the future. The session adjourned in August, the
newest proceeding anywhere is 2026-09-02, and `ddlCommittee` on the submission
form is empty because nothing is open. Every one of the 3,360 committee
hearings in the record can only be "closed". The three states are buildable and
checkable, but they cannot be *seen* until the next session schedules
something.

**Half of that changed by 17 September.** No *hearing* is in the future still,
but 51 proceedings are -- 23 executive sessions, 17 subcommittee and 11 full
committee work sessions, on 44 bills, running to 13 October -- so the newest
proceeding anywhere is 2026-10-13 rather than 2026-09-02, and a page drawing a
sitting that has not happened yet can now be seen doing it. "3,360" was one
term's count: `proceedings.csv` holds 53,108 hearing rows across all nineteen
terms.

---

## One click to submit testimony

A reader who sees a hearing scheduled next week on something they care about
should be able to say so without learning the General Court's menus. Today that
means going to gc.nh.gov, choosing the committee, then the hearing date, then
the bill, from selects that do not explain themselves -- and the bill they came
for is the one thing they already know.

The feature is a single link on the bill page that opens the General Court's
own sign-in form with the committee, hearing date and bill already chosen, so
what is left is a name and what the person thinks. It sends people TO the
official form rather than collecting anything here.

What it needs first is to know how that form addresses a hearing --
fetch_committee_reports.py's _options()/SELECT_RE already read the same kind of
select from a General Court page, so the shape of the work is known. It is a
small number of requests to one page, not a crawl.

Not started. The counts that make it worth having landed on 6 September:
315,142 sign-ins across 2,019 bills, shown per hearing.


## Now: finish the structure

These are in flight or next, and most other work is easier after them.

**Done, 7 September** — recorded here because the list below assumed they were
outstanding:

- **Term keying is finished.** `bill_status.json`, `bill_text.json` and
  `data/sponsors.json` were the last three flat per-bill files. Only
  `testimony.json` is left and it is superseded by `testimony_db.json`, which
  is keyed already. A search for a prime sponsor works before 2025 as a
  result: 1,865 of the 1,996 bills of 2023-2024 carry one.
- **The second renderer is gone.** `build_bill_pages.py` was 909 lines drawing
  every bill again in Python; it is 259 and draws nothing. A bill's page is
  `bills.html` with one bill open, so the two views cannot disagree. The site
  went from 290.8 MB to 189.2 MB at the same file count.
- **Every voter in the 2023-2024 roll calls is named and has a party**, bar
  two. It was 63,065 votes without one, 32% of the term.

**Split `build_site_v2.main`.** Still outstanding, and now the only one of the
three left: `renderDetail` was split on 6 September and `build_bill_pages.py`
was deleted rather than split on the 7th. The failure mode was a blank page for
someone arriving from a shared link, the worst possible one for a site you are
about to publicise.

**Finish the timestamp work.** Measured 7 September: of 10,810 proceedings,
4,994 carry a boundary the chair or clerk said out loud, 209 a roll call's own
clock time, and 1,427 an inferred start shown as *approximate*. 4,180 carry no
time — 2,522 of those passed on a consent calendar and were never taken up
separately, 1,068 have no recording, and 590 are floor actions the site can
date but not place. Against the 35 hand-timed proceedings: 19 placed, median
out by one second, worst 5m 47s.

The Whisper run for the 19 recordings with no captions finished on the 7th and
those have not been through the marker pass yet, so the next gain is free.
`--gaps` still has room, floor ends are only partly precise, and committees of
conference are not properly modelled.

**Re-measured 17 September.** "10,810 proceedings" was one term's denominator;
`proceedings.csv` is 104,769 rows across all nineteen terms now, and
committees of conference are modelled -- 1,836 of those rows, in every term,
223 against a recording. The gate, run today, reads candidate median **0m 01s,
44 of 63 hand-timed proceedings placed, the schedule alone 14m 46s**. Take
those from `python3 probe_alignment.py --truth --candidate
candidate_segments.json` rather than from this paragraph, which has been the
wrong number twice.

---

## Next: the committees page

**Built.** 53 pages under `site/committee/`, drawn by `build_committees.py`:
composition from `committees.json`, the bills referred, the sessions that
term, and per-committee counts. What follows is why it was worth doing, which
has not changed -- and it was: the first thing General Court staff reported
back, on the 15th, was a wrong roster on some of these pages, which is a
reader using the page for its purpose. `LAUNCH.md` §0c has that.

The single best return on the list, and it needs no new data.

A page per committee, with:

- **Composition** — members, chair, vice chair, aide, room. `fetch_committees.py`
  already returns all of it.
- **Bills referred**, as the same cards the search tab uses.
- **Sessions that term**, oldest or newest first, each as a card with the
  recording embedded and per-bill start and end timestamps beneath it, and a
  summary above in the same shape as the bill narrative. One page per
  committee rendering both views client-side, not a page per session: 29
  pages and 29 JSONs rather than 1,061 files, which keeps this clear of the
  file cap entirely. It says what was heard and what was done —
  which bills, which were executed, which were voted, which went to consent.
  `proceedings.csv` plus `committee_reports.json` has every part of that.
- **Statistics** — bills referred, hearings held, reports filed, how often the
  committee's recommendation was followed on the floor.

Why it is worth doing now: it is a genuinely different way into the record.
Bill-first search answers "what happened to HB 1442". This answers "what did
Legislative Administration do on 3 March", which is the question a reporter or
a committee member actually asks. It also surfaces the timestamp work, since a
committee day is where the boundaries are densest.

Do it after the `build_site_v2` split, not before — it adds pages to the same
function that is being taken apart.

---

## Then: the archive, re-planned on what the database actually holds

**Two things settled on 7 September, before this section's reasoning.** The
file cap is payable — a Cloudflare paid plan raises it from 20,000 to 100,000,
which fits every term the database can supply with room over. And
`probe_archive_shape.py` sampled a couple of bills from each session year back
to 1989: the status pages serve 1989 in the same shape as 2026, but **sponsors
are absent before the mid-2000s** and are not available from the database or
the LSR files either. So the constraint on how far back a term is worth
publishing as full records is sponsor data, not disk. ARCHITECTURE.md has the
measurements.

Settled 6 September by querying the General Court's own SQL Server, whose
read-only credentials are published at gc.nh.gov/downloads. It exposes 28
views, not the 13 its PDF documents. Coverage, measured:

| era | what exists |
|---|---|
| **1989-2016** | `Docket` only, 292,532 rows, 783 bills in 2005 alone; roll calls from 1999 |
| **2017-2024** | **nothing** |
| **2025-2026** | everything: bill text, committee reports, committee membership, hearings, 402,908 testimony rows of which 128,854 carry text |

The 1989-2016 era is close to the agreed minimum for an archived bill --
number, title, docket, status, and a link out for the rest -- for 28 years,
with no scraping at all. That was going to be the expensive half of this and
it is now a query.

The gap is real and is not hiding elsewhere. `Docket`'s own `[DataBase]`
column reads `BillStatusDB` for 1989-2016 and `NHLMS` for 2025-2026, and the
view unions exactly those two systems. `NHLegislatureDB2` carries none of the
views; `PublicNHLMS` is the live current-session store only.

**1. The 2017-2024 years. Confirmed reachable, two requests a year.**

The Advanced Bill Status Search at `/bill_status/legacy/bs2016/` takes a
session year and says "1989-Current" beside the box. Probed 6 September:
**2019 returns 768 bills**, each carrying its title, general status, House
status, Senate status, last committee, last hearing, and links to its docket,
status, text (HTML and PDF) and history. That is the whole of the agreed
minimum for an archived bill.

It is an ASP.NET WebForm, so it wants a POST carrying `__VIEWSTATE` with the
year in `txtsessionyear` and `sortoption=billnumber`. A GET with invented
query parameters returns HTTP 500, which is what the first attempt did -- the
same mistake as guessing at a filename, and the same useless answer.

The results page also links the identical query as a feed, by GET:

    /rssFeeds/rssQueryResults.aspx?&sortoption=billnumber&txtsessionyear=2019

which is a machine-readable version of a 2.9 MB HTML table and is very likely
what a real fetcher should read. Confirm that before writing a parser against
the table.

Per-bill links are keyed `lsr=0030&sy=2019`, the same key
`fetch_bill_status.py` already uses, so the existing docket fetcher should
work against these years unchanged.

So the gap closes: **1989-2016 from the database, 2017-2024 from this form,
2025-2026 live.** Sixteen requests for the eight missing years, not sixteen
thousand.

**2. Term-keyed identifiers, regardless of the answer.** `(term, bill)`
everywhere. This is now the gate on everything archival and does not depend on
the file-cap decision the way the earlier plan assumed: the database hands
back `SessionYear` on every docket row, so the key exists in the source and
only has to be carried. `build_feeds.py` still has no notion of a term and is
2,233 of the site's files. **Both halves of that sentence are spent:**
`build_feeds.py` keys on `(term, bill)` and says why at `:225-228`, and since
a feed is written only for a bill still moving it emits 811 files, not 2,233.

**3. The file cap.** Unchanged and unaffected by any of this -- it is about
how many files the site emits, not where the data comes from. Cloudflare Pages
allows 20,000; one term is 8,045, three files per bill, so the cap breaks
partway through the THIRD term. An archived term built from `Docket` alone
needs far fewer files per bill than a current one, which makes the cheaper
option easier rather than harder.

**4. Back-fill one term end to end** as the proof. 2005-2006 now, not
2023-2024: the database covers it and the scraping does not.

**What the database does not have, so the PDF path stays:** calendars,
journals, and anything about video or timestamps. The Secretary of State
archive probe is no longer needed for docket or votes -- 2005 and 2023 both
returned 404 on the constructed `/BillHistory/SofS_Archives/` pattern anyway,
with `netcheck.py` clean immediately after, so that URL shape is simply wrong
rather than blocked.

**One limit worth deciding before building.** `Sponsors` is 2025-2026 only.
An archived 1995 bill would carry its docket and its roll calls and no
sponsors at all. That constrains what an archived bill page can honestly
claim, and the page should say so rather than leave an empty section that
reads as "nobody sponsored this".

---

## Independent of all of the above

These need no structural work and can fill any gap.

**Cheap, and each removes a visible rough edge:**

- A link to the bill text from the card view.
- RSA links are only partially working on the detail view. A citation that
  silently fails to link is the one place a reader goes to check a
  committee's reasoning against the statute, so this is a defect rather than
  a polish item.
- Bill text and amendment text layout in the detail view.
- Corrections email forwarding, and turning off Cloudflare's Email Address
  Obfuscation, which currently breaks the address on a site whose whole
  invitation is to be told when it is wrong.
- The about and how-it-works pages, which are stale.
- Progress circles on the compressed card — House, committee, Senate,
  Governor — filled, checked or crossed. Communicates status faster than the
  chip does, and is the sort of thing a first-time visitor reads without being
  taught.
- More definition between cards and background; the same for search controls.

**Sharing and navigation, which matter more once the site is publicised:**

- Returning to a search after opening a bill, without a long URL. Every shared
  link carries the search state today. Worth fixing before the site is shared
  widely, because the URLs people paste now are the ones that will circulate.
- RSS and email follows for bills, legislators, committees and calendars. The
  feeds exist; nothing on the site explains they do, and there is no email
  path at all.

**Scaling, mobile and desktop:** text, tabs, search, embeds. Do this after the
card and page changes above, or it gets done twice.

---

## Bill versions, and what each amendment changed

**Shipped**, as the tab the strip labels "Bill Text" -- 9,473 files under
`site/versions/`. It was built the way this section designed it and from route
1 below: `build_bill_versions.py` reads `db/LegislationText.psv`, so no
request was made for any of it. Route 2 was never probed and route 3 never
written. Kept in full because the build was made out of this research, and
because "What it will not be able to say" still holds.

Researched 8 September. The ask: the detail page opens on the bill as it
stands now, and the reader can step back through the versions to see what each
amendment did to it.

### What the record holds today, measured

`bill_text.json` carries **one version of each of the 2,234 current-term
bills** — whichever one was current when it was fetched. The General Court
labels them, and the labels say plainly that the others exist:

| label | bills |
|---|---|
| AS INTRODUCED | 1,187 |
| FINAL VERSION | 686 |
| AS AMENDED BY THE HOUSE | 203 |
| AS AMENDED BY THE SENATE | 138 |
| VERSION ADOPTED BY BOTH BODIES | 3 |
| none stated | 17 |

So for the **861 bills whose text is not the introduced one, the introduced
text is not on this disk**. That is the missing artefact, and everything else
follows from it: a diff is two texts, and the site holds one.

**1,572 bills carry at least one adopted amendment** — 2,478 adopted
amendments in all, against 200 rejected and 181 the docket does not say
either way.

Two things the site already has that are easy to mistake for this feature:

- **`amendments.json` holds 663 amendment texts**, extracted from cached House
  calendars, covering 446 of the 2,478 adopted amendments. An amendment is
  drafting instructions — *"Amend RSA 354-A:1 by replacing it with the
  following: ..."* — so it says what changed in the drafter's words. It is not
  a version of the bill and cannot be diffed against one.
- **The cached bill-text HTML keeps the General Court's own drafting markup**:
  2,161 of 2,234 files carry `line-through` spans and 2,220 carry italics,
  marking what the bill removes from current law and what it adds. The
  extractor flattens both to plain text and the site shows neither. That is a
  different comparison — bill against statute, not version against version —
  but it is free, already fetched, and worth taking on its own.

### Where a second version can come from

**1. `LegislationText` on the public SQL host. This is the one to use.**
Recorded in `ARCHITECTURE.md` on 6 September: it holds the full text of every
version of every bill as HTML — "Introduced", "As Amended by the House",
"Version adopted by both bodies", "CHAPTERED FINAL VERSION". One SELECT, on
the server the General Court publishes credentials for, not the web server
that blocked this address twice. Current term only, like everything else in
that database.

**2. `billText.aspx` with a version parameter.** A search result once showed
`billText.aspx?id=692&txtFormat=pdf&v=current`, so the parameter exists; what
other values it takes is unknown and no page links to one. Worth a single
probe only if route 1 disappoints, and it costs 2,234 requests a version to
the address that has been blocked twice.

**3. Reconstructing a version by applying the amendment.** Of the 663
amendment texts on disk, 55 open *"Amend the bill by replacing all after the
enacting clause with the following"* — those carry a complete replacement body
and could be applied exactly. The rest amend a section, an RSA or the title,
and applying them means matching the drafter's target inside the bill. That is
a parser against prose where a wrong answer is a fabricated bill text. Not
worth doing while route 1 exists.

### The offline win that is available either way

`extract_amendments.py` reads `calendars/` only. The 204 Senate calendars
fetched for the veto messages print amendments in the same shape — number,
bracket, proposer, instructions — and hold **902 of the adopted amendments
whose text is not yet extracted**. A further **388 are in the House calendars
already on disk** and were missed. Reading both would take amendment-text
coverage from 446 to about 1,736 of 2,478, **with no network at all**. 744
appear in no cached calendar.

**Taken on 11 September, and it paid more than this predicted.**
`amendments.json` holds **4,577 amendment texts, 2011-2024**, against the 663
here; `LAUNCH.md` §6a records the run. `extract_amendments.py` still defaults
to `--calendars calendars` and is pointed at `calendars_senate` for the Senate
side -- which is 1,604 PDFs on disk now, not the 204 fetched for the veto
messages.

### The design

**Versions, not diffs, are the unit.** Store each version's text once, in
order, with the label the General Court gave it and the amendments its own
header names — `bill_text.json` already parses that header, so
`2026-1054h at 5 March` is on file for HB 1442 without any new parsing.

**A step is the gap between two consecutive versions**, and that is what the
reader is shown: the word-level difference, computed at build time, stored as
operations rather than as two marked-up copies. The site already has the
vocabulary for it — `.cut` renders removed text struck through in red, added
in the ordinary ink.

**The check that makes it honest**: applying a step's operations to version *k*
must reproduce version *k+1* byte for byte. A diff that does not reconstruct is
a wrong diff, and `preflight` can say so without a network or a judgement call.

**The page**: the text tab opens on the current version, as now. A row of
version buttons above it, in order, with the amendment number under each. The
URL takes the version, so a link to what one amendment changed is shareable —
the same argument as `/bill/2026/hb1442`.

**Cost**: one version of every bill is 14.8 MB of text; the second version for
the 861 amended bills is about 5.7 MB more. Nothing here needs a new file per
bill.

### What it will not be able to say

Where `LegislationText` holds fewer versions than the bill had amendments —
two amendments adopted on the same day and published as one version — the
step covers both and **the page must say so** rather than attributing the
whole change to one of them. That is the same rule as the timestamps: name
what the claim rests on.

And the archived term gets none of it. `LegislationText` is 2025-2026, so
2023-2024 bills keep a link to the General Court, which is what the archive
does everywhere else.

---

## Needs data not yet fetched

Each is a fetch plus a parser plus a place to put it. None blocks anything
else, and each is worth doing when the structure around it is settled.

| | Notes |
|---|---|
| Senate committee reports | The House side is done; the Senate is not |
| Public hearing testimony | 565 of 1,237 fetched |
| Permanent journal speeches | **The largest content addition available.** The House journal records what members actually said. Nothing else on the site carries a member's own words |
| Fiscal notes | Already inside the bill text, at the bottom, not parsed |
| Amendment text | **Done, 11 September.** 4,577 texts, 2011-2024, out of the House and Senate calendars already on disk, no network. Was 446 of 2,478. See **Bill versions** above |
| Committees of conference | **Modelled**, since the archive landed: 1,836 proceedings across all nineteen terms, 223 of them against a recording |
| Executive Council, Governor | `officials.json` replaced `status/officials.txt` and is filled by hand; the Governor and the Council print on all 320 town pages. Pages of their own are still not built |
| Rules and executive departments | Not started |

**Amendment text is the one I would do first** of these, and most of it
needs no fetch at all -- the calendars holding it are already on this
disk. Versions of the bill itself are a different artefact and come from
`LegislationText`; **Bill versions** above sets both out.

*Both were done, on the 11th, and neither cost a request -- which is the part
worth remembering when the next item of this shape comes up.*

---

## Legislator pages

Grouped separately because the list has several items that are really one job.

Sponsored bills are missing, roll call votes are hard to read or compare, the
layout is not parsable, and the legislators index page is poorly formatted.
That is one redesign, not four fixes, and it wants doing in a single pass
after the `build_site_v2` split — the same reason as the committees page.

**Done, and not in one pass, and not after the split.** Sponsored bills landed
on the 14th, every member's list now equalling the records that resolve to
them; the roll call rows name the bill, the question in plain English, the
tally and whether the member took their own party's side. On **17 September
the 1,785 members who have left got pages of their own**, from
`site/former.json`, which turned 34,303 sponsor mentions from plain text into
links; the sitting roster, `site/legislators.json`, was deliberately left
alone and still holds exactly 406. The split this was said to wait on has
still not happened, so it was never the blocker it is written up as here.

---

## What I would not do yet

**Bill indexing.** The sitemap has never been submitted, so nothing is indexed
at all. Submitting it before the URL and sharing scheme is retooled means
search engines index URLs that are about to change.

**Publicising widely.** The `renderDetail` crash class is fixed but the
function is still 472 lines, and a blank page for an arriving visitor is worse
than no visitor. After the split.

**Both were overtaken, 14-15 September, and the caution was right about what
had to come first.** The URL and sharing scheme was retooled on the 14th --
every tab has an address and the sitemap's lastmod is the day a bill last
moved -- and `renderDetail` is **102 lines** now, not 472. The site went, as
it stands, to General Court staff and legislators as its first power users on
the 15th; wide publicity is a separate decision and is still the person's.

---

# 9 September: a read-through of the live site

A list from someone reading the site rather than building it, so it is ordered
here by what it costs against what it fixes, not by the order it arrived in.
Two items on it were already done and are recorded as such so they are not
done twice.

## Already done

**Archived bills reading as in progress.** Fixed in `434dc76` -- it was
`fe147fa` until the history rewrite of 17 September changed every hash: 1,954 bills
across eighteen terms said "In committee" or "Laid on the table" because the
General Court stops updating the status field when a term closes. The word the
record gave them is unchanged; the kind that drives the colour and the rail is
not. 107 bills are active now, all current-term.

**Interim study and laid-on-the-table indicators.** Shipped. The refinement
asked for on 9 September is new and is in "the rail" below: a pending mark
whose Law stop is struck through once the term ends without the bill being
taken back up.

## The one that unblocks three others: a review tool

Asked for as a way to spot-check timestamps quickly. It is worth more than
that and should go first among the feature work.

**Built, as `review.py`, and it did unblock them.** Nine kinds rather than the
three below, **165 judgments** on file in `review/checked.jsonl`, and
`probe_alignment.py --truth` scores against them beside `ground_truth.csv`'s
35 -- 63 hand-timed proceedings between them today, against the 35 this
paragraph called thin.

`ground_truth.csv` holds 35 proceedings somebody timed by watching. It is the
only independent measure this project has, `CLAUDE.md` requires every
timestamp method be scored against it, and it is thin — thin enough that a
method can be tuned to it without anyone noticing. The same problem is about
to appear twice more: related bills and narrative quality both need a
judgment no generator can make.

So: a local page, not published, that pulls up one sample with the thing being
measured already open — the recording at the published timestamp, or two bills
proposed as related, or a narrative beside its docket — takes a verdict and a
short note, writes it to a hand-edited file no generator may touch, and moves
to the next. Same shape for all three, one keystroke per sample.

That turns "35 proceedings" into as many as somebody has patience for, and it
is the difference between claiming a median and knowing one. Build it before
related bills, not after, because related bills cannot be evaluated without
it.

## Capitalisation and naming, one pass

Cheap, visible, and all the same class of defect.

- Committee names arriving ALL CAPS from older terms — "Senate WILDLIFE &
  RECREATION". `_name()` in `calendar_meetings.py` already title-cases with a
  small-word list; the committee pages need the same function rather than
  their own.
- "Prime sponsor" to "Prime Sponsor", "Year filed" to "Year Filed".
- The term selector should read "2001-2002 Term".
- "How it works" becomes "Learn". The pages already live at `/learn/`; only
  the label and the nav entry are wrong.
- A bill on a card should carry its year — "HB1123 (2026)" — rather than a
  filed-or-carried-over phrase.

## Correctness, in rough order of how wrong each one is

**Narratives are written entirely in the past tense**, so a work session that
is merely scheduled reads as "The committee held a work session on September
20th, 2026." That is the site stating as fact something that has not happened.
It is the worst item on this list and should be fixed first: `describe()` needs
the event date against today, and future events need their own wording.

**Roll calls on legislator pages cannot be read.** Date, bill number, motion,
vote — and no way to see what the bill was, how the vote came out, or how the
member voted against their party. It needs the bill's title, the tally, a
party-line comparison, and grouping by session day.

**Committee reports carry page furniture mid-sentence** — "13 FEBRUARY2026
HOUSERECORD 23" dropped into the middle of Rep. Walsh's reasoning. Same class
as the veto-message runaway fixed last week: a page header inside a text
block. `is_whole()` in `extract_vetoes.py` is the pattern to copy.

**HTML entities are published raw** in bill analysis — `&ldquo;` and `&rdquo;`
appear as themselves in HB2. One unescape at the right point.

**The rail is wrong for resolutions.** A House or Senate resolution that passed
its own chamber never goes to the other one, and the rail draws that as though
it stopped. A resolution's rail has two stops, not four.

**Sponsor party colours are inconsistent** across bill pages, committee pages
and legislator pages. One chip component, used everywhere.

**Legislator names are not uniform.** "Seidel, Sheila" on a committee page
should be "Rep. Sheila Seidel (R-Rock 21)" everywhere, including for members
who have left. Note the standing rule: former members are shown exactly like
sitting ones, never flagged or segregated.

**Committee pages do not name the ranking and deputy ranking members**, which
are conventionally the first two names in the minority. *Answered, and the
answer was no* -- `LAUNCH.md` §5: no source on this disk records the role, and
naming one from list order infers a real person's leadership from an ordering.

## Data the archive does not yet carry

**Topics for older terms.** Bills before the current term have none. Assigning
them by machine is possible and is the kind of thing that invents facts
quietly, so: it must be visibly derived, the method stated on the page, and
scored against a sample somebody checked — the review tool again.

**Done, and on that condition.** `topic_model.py --apply` placed 20,521 bills
and took Miscellaneous from 13,191 to 10,928 (`LAUNCH.md` §0g records the
run); 1989-1990 gives 950 of its 1,632 bills a topic today. It was scored on
the unseen half of the General Court's own labels before it was applied, and
topics are the bench's largest kind, 44 of the 165 judgments.

**One legislator across terms.** A member who served in 2004 and serves now is
two records today. Merging them gives a sponsorship and voting history across
a career, and it is what makes "find the sponsors of a 2004 bill" work.
`DistrictPast` in the database exists precisely because a 1998 member's
district is not today's, and presenting it as though it were is the error to
avoid.

**Done on the 13th** (`member_links.py`, `LAUNCH.md` §6c): twenty members'
earlier chamber joined to their page, on six conditions holding together, with
nothing doubtful left joined. And the error this paragraph warned about was
made and then caught -- on the 16th, 174,119 ballots and 8,610 sponsor rows
were moved onto the seat held when the record was made rather than the seat
held today.

**Special bills need a note.** HB1 and HB2 are the budget and the budget
trailer bill; HB2026 is the ten-year transportation plan. A reader has no way
to know that a bill numbered 2 is the whole state budget. A short standing
note per bill, hand-written, not derived.

**HB1 and HB2 shipped on the 10th**, from `bill_notes.json`, which is one of
the files no generator writes, applied from 1993-1994 onward because the 1989
and 1991 HB1s are not budgets. The transportation plan is a different number
every term and its `by_term` section is still empty.

## Related bills

Wanted as its own tab: bills amending the same RSA across years, and bills
whose text was amended into another bill during a session. Minimum wage,
bathroom bans, red flag laws as the worked examples.

The user has already named the hard part, which is the whole problem: two
bills can touch the same RSA for unrelated purposes, and two bills can do the
same thing through different RSAs. So an RSA overlap is a signal, not an
answer, and this needs the review tool to measure both false positives and
false negatives before any of it is published. "Amended into" is the easier
half and is in the docket already.

## Pages and sections not yet built

- **A session calendar page**: the consent calendar, the regular calendar and
  the committee motions, in order, explained.
- **Committee pages showing upcoming hearings, executive sessions and work
  sessions** with their bills. Half-built: the schedule service is fetched and
  the hearings parser now reaches 1997.
- **A committee's session day as a table** — every bill heard that day, its
  status change, and the report split (SB473: public hearing, then executive
  session, 10-7 OTPA to ITL), with the bill numbers hyperlinked.
- **Executive Council, Governor, CD-1, CD-2 and US Senator pages**, with
  official links and contact details.

## Search

Load 100 bills and fetch more on scroll. Straightforward, and it pairs with
the per-term index split already shipped.

## Carried over, unchanged

Amendment diffing — the data is on this disk and was found on 9 September:
`LegislationText` holds 6,825 rows, every version of every current-term bill
with both HTML and plain text, plus `DocumentVersion.SortOrder` to order them.
No fetching needed for the current term.

Email routing. Accessibility, continuously. Google indexing, which needs the
URLs and titles cleaned up first.

**Since carried:** amendment diffing shipped, from exactly that source --
9,473 files under `site/versions/`. contact@ routing is active. Accessibility
had a first pass on the 11th at 360, 768 and 1440, read from the DOM rather
than by eye, and stays continuous. The URLs and titles were cleaned up on the
14th, so Google indexing now waits only on the person submitting
`sitemap.xml`, which is built.
