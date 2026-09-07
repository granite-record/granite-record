# Granite Record — roadmap

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

**Split `build_site_v2.main`.** `renderDetail` is done — split 6 September
into nine hoisted functions, one per tab, output verified byte-identical
against the pre-split page over ten renders covering every station state.
`build_site_v2.main` remains. The failure mode was a blank page for someone
arriving from a shared link, the worst possible one for a site you are about
to publicise.

**Finish the timestamp work.** Coverage is at 66% of proceedings actually
taken up. `--gaps` and `--phrases` still have room, floor ends are only
partly precise, and committees of conference are not properly modelled.
Everything on the site that points at a recording depends on this.

---

## Next: the committees page

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
2,233 of the site's files.

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

## Needs data not yet fetched

Each is a fetch plus a parser plus a place to put it. None blocks anything
else, and each is worth doing when the structure around it is settled.

| | Notes |
|---|---|
| Senate committee reports | The House side is done; the Senate is not |
| Public hearing testimony | 565 of 1,237 fetched |
| Permanent journal speeches | **The largest content addition available.** The House journal records what members actually said. Nothing else on the site carries a member's own words |
| Fiscal notes | Already inside the bill text, at the bottom, not parsed |
| Amendment text | `billtext.aspx?txtFormat=amend&id=2026-1054H` reaches it directly; would replace the current 40% ceiling and make diffing possible |
| Committees of conference | 133 recordings exist and are linked, but the proceeding is not modelled |
| Executive Council, Governor | `status/officials.txt` is unedited, so neither appears |
| Rules and executive departments | Not started |

**Amendment text is the one I would do first** of these: it unblocks amendment
diffing, which is on the list separately, and the endpoint is already known.

---

## Legislator pages

Grouped separately because the list has several items that are really one job.

Sponsored bills are missing, roll call votes are hard to read or compare, the
layout is not parsable, and the legislators index page is poorly formatted.
That is one redesign, not four fixes, and it wants doing in a single pass
after the `build_site_v2` split — the same reason as the committees page.

---

## What I would not do yet

**Bill indexing.** The sitemap has never been submitted, so nothing is indexed
at all. Submitting it before the URL and sharing scheme is retooled means
search engines index URLs that are about to change.

**Publicising widely.** The `renderDetail` crash class is fixed but the
function is still 472 lines, and a blank page for an arriving visitor is worse
than no visitor. After the split.
