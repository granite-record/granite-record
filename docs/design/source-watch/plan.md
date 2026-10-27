# Source watch: keeping the guides true to their pages without printouts

A design, 27 October 2026. Nothing here is built. Build after 10 November
(the guides are locked for the webinar); live by the 9 December release.

**The ask** (the person, 27 October 2026): "Is there any way we could make
it so that you could access the guide source webpages periodically to verify
that the information is up to date and that I don't have to manually print
out the sheets? It doesn't have to be daily and could require my computer be
on similar to how I believe the captions system now operates."

**The answer in one line.** Once a month, a browser on the laptop reads every
page the guides cite, at a person's pace and saying what it is. A cloud
session compares each claim's recorded words with the new page. A claim whose
words are still there is re-dated. A claim whose words changed becomes one
line in a report for the person to say yes or no to. Nothing on the site
changes without that yes.

---

## What we are checking

As of 27 October 2026 (`src/checks/fact_sheet.py` reads the same ledger):

| | count |
|---|---|
| guide claims resting on a web page | 242 |
| distinct pages they cite | 162 |
| sites those pages are on | 56 |
| claims on nh.gov agency sites | 133 |

The busiest sites are dmv.nh.gov (27 claims), sos.nh.gov (18), dhhs.nh.gov
(14), ecfr.gov (12), wildlife.nh.gov (11) and medicare.gov (10).

Statute claims (RSA sections) are not in scope here. The build already reads
them every night from the statute table, which the weekly takes fresh, and it
holds a guide back the day a figure's words leave the law.

## What we know about the sites

- **nh.gov agencies refuse a script.** Akamai sits in front of sos, dmv, doj,
  energy and the other nh.gov agencies. It refused cloud machines (11 October
  2026) and the honest script `src/fetch/other/guide_sources.py` from the
  laptop's own home connection (12 October: every page 403, 0 bytes).
- **A real browser was let through.** On 17 October, about a dozen of those
  pages were read in the Claude desktop app's built-in browser pane, one at a
  time, from the laptop (guide_sources.py records which).
- **Some sites refuse this project's cloud machines:** ssa.gov and
  travel.state.gov.
- **Others have never been tried from a cloud machine:** ecfr.gov, govinfo.gov,
  medicare.gov, healthcare.gov, usa.gov, nhla.org, 603legalaid.org and the
  rest. One honest request each would tell us.
- **The captions system is the pattern to copy.** A Windows Task Scheduler job
  on the laptop does the asking (`livestreams.py --to-inbox`, 7:30 pm). It
  only ever adds files to the private bucket's inbox (`cloud.py inbox_add`),
  and the night takes them from there. An evening the laptop is off is simply
  skipped.

## Hard rules

1. **Never the General Court.** No gc.nh.gov page in any form. The reader
   refuses that host by name, as guide_sources.py's `main()` does, and the
   assistant guard denies it as well.
2. **No getting around a bot check.** No stealth plugins, no faked user agent
   to hide automation, no patching `navigator.webdriver`, no CAPTCHA solving,
   no rotating addresses. Three things count as a refusal:
   - a 403;
   - a challenge page;
   - a page whose text is a block notice.

   The first refusal from a host stops that host for the run, and it is
   recorded, like `refusal.py`, against the host rather than the run. A host
   that refuses twice in a row goes to the fallback list for good, until the
   person says otherwise.
3. **Say what it is.** Where the browser lets us set it, the user agent carries
   "GraniteRecord source check (graniterecord.org)" after the browser's own
   string, never in place of it.
4. **A person's pace.**
   - One page at a time.
   - 20 to 40 seconds apart.
   - At most 30 pages from any one host in a run.
   - Nothing retried within the run.
5. **Nothing changes on the site without the person's yes.** Re-dating an
   unchanged claim is the only automatic edit. It changes no word a reader
   sees, and it goes to the manager as an ordinary commit on `guides`.

## 1. How the laptop reads the pages

Three ways, in the order I would try them.

**(b) First: a scheduled Claude task on the laptop, reading in the desktop
app's browser** (or Claude in Chrome).
- **Why first:** this is the only way that has already read the nh.gov pages
  (17 October). It is the person's own browser on the person's own
  connection, reading the pages a person would read, one at a time. Nothing
  here hides what it is.
- **How it runs:**
  - A scheduled task on the laptop, about monthly, with the computer on and
    the person signed in, the same condition the captions job lives with.
  - It takes the month's list from `records/sources/printouts/INDEX.csv` and
    guide_sources.py.
  - For each page it opens the address, waits for the page to finish, and
    saves the page's text and a PDF (print to PDF).
  - It writes one manifest line per page: address asked, address ended at,
    status, title, time, sha256 of each file, bytes.
  - It stops a host at the first refusal.
- **Unknown, which the test answers:** whether a scheduled task, run with no
  one at the keyboard, is let through the way the person's interactive
  session was.

**(a) Second: Playwright driving the person's installed Chrome**
(`channel="chrome"`, a window shown, the person's own profile, honest user
agent).
- **Why second:** it is cheaper to run and easier to make repeatable than (b).
  But a browser driven by Playwright announces itself (`navigator.webdriver`),
  and Akamai's bot manager is built to notice exactly that.
- Under rule 2 we will not hide it. I expect nh.gov to refuse it, and the
  test will say. It may well serve the non-Akamai sites.

**(c) The fallback, always available: a one-click list.**
- A small page on the laptop (or an Artifact) lists every page due this
  month, grouped by site. Each line is a link with a "saved" checkbox.
- The person opens each one and saves it with Ctrl+P → Save as PDF into their
  Downloads folder.
- `src/ops/file_printouts.py` then files them by sha256, as it does today.
- This keeps what works now and makes it quicker: no hunting for addresses, no
  renaming, and the list says what is still missing.

**(d) In addition: a cloud session reads the sites that answer it.** Federal
sites such as ecfr.gov and govinfo.gov, and others yet to be tried, may
answer a plain, honest request from a cloud machine. One polite request each,
once, tells us. Those pages then need no laptop at all.

**The one-evening test (about 10 pages, about an hour, with the person
present):**
- **Ten pages**, chosen to cover the cases:
  - 4 nh.gov behind Akamai: dmv vehicle registrations, sos request for
    certificates, dhhs Medicare savings program, insurance automobile
    insurance;
  - 1 nh.gov PDF: the auto insurance consumer guide on mm.nh.gov;
  - 2 federal sites that refused the cloud: ssa.gov my account,
    travel.state.gov renew by mail;
  - 3 others: medicare.gov parts of Medicare, ecfr.gov 22 CFR 51.42,
    603legalaid.org.
- **Run 1, way (b), with the person watching.** Then the same ten once more as
  a scheduled run, with the person away from the keyboard.
- **Run 2, way (a)**, on the same ten.
- **What it measures, per page and per way:** read or refused; whether the
  saved text is the whole page (not a cookie banner or a shell); and whether
  each existing claim's words are found in it.
- **Passes if** at least 8 of the 10 are read whole by one way, with no
  challenge page shown. Otherwise the plan is (c) for nh.gov plus (d) where it
  works, and we say so.

## 2. What a check compares

**Today a claim's `says` is often a close paraphrase** of its page, not the
page's own words. A machine can only compare words. So, before the first run:

- **One-time move to quoted words.** Each web claim gains `words`, one or
  more phrases copied exactly from the page, the way a `record()` claim on a
  General Court document already does (`guides.record`, read by
  `claim_faults`).
  - The phrases come from the printouts already on hand, matched by an
    assistant and checked by preflight: every phrase must be found in the
    claim's printout or snapshot text.
  - A claim whose printout has no text layer (most of today's are images) gets
    its words from the first snapshot instead, and is marked so.
- **Each month, for each claim on a page that was read:**
  - **Every phrase still on the page** (case, spacing and punctuation folded):
    unchanged. `checked` moves to the snapshot's date. This is a commit on
    `guides`, sent to the manager like any other. Nothing a reader sees moves.
  - **A phrase missing, or the page gone** (404, or a redirect to somewhere
    else): an item in the month's report.
  - **The host refused:** nothing changes. The claim keeps its old date and the
    page goes on the fallback list.
- **The report, one item per changed claim:**
  - the guide and the sentence(s) the claim stands behind (`fact_sheet.py`
    already lays out a guide beside its ledger);
  - the old words as read, with the day;
  - the page's words now, in the same place where they can be found;
  - the page link, and the snapshot;
  - a drafted change to the guide (English and Spanish), or "remove";
  - **yes / no**.

  It is an Artifact page the person opens, with a yes and a no on each item and
  a note box. The answers are stored with the page, so the next session reads
  them. On a yes, a session makes the change on `guides` the ordinary way
  (preflight, Spanish, the manager merges). On a no, the claim keeps its old
  date and words, and the item comes back next month only if the page changes
  again.
- **A claim not re-read for 90 days** (refused, skipped, laptop off) is named
  in the report as stale. Nothing is held back automatically. The person
  decides whether a stale claim matters.

## 3. Can a snapshot stand in for a printout?

**Proposed default: yes, a snapshot can stand in, under three conditions.**

1. It is the page as served: the browser's own PDF of the page, plus its text,
   not a summary.
2. It is kept: address, time and sha256, filed in the printouts archive with
   its row in the index.
3. Its read is recorded: which way read it (b, a or d) and that the run met no
   refusal.

The rule in CLAUDE.md, "a guide says only what a source on hand says", is
met. The snapshot is the source on hand, and it is better evidence than a hand
printout: it carries its own address and time, and a machine can search its
text.

A printout from the person stays equal evidence, never lesser. Where both
exist for a page, the newer one counts. **This is the person's decision.** If
the answer is no, the monthly read still runs, but every change or re-date
waits for a printout.

## 4. Where things live, how often, what runs where

- **Snapshots:**
  - On the laptop under `records/sources/printouts/snapshots/<YYYY-MM>/`.
    Git already ignores PDFs there, and the text files go in the same ignore.
  - Backed up to the private bucket under `sources/snapshots/`, adds only, as
    the captions inbox does. That is a new `cloud.py` command, and a change to
    the R2 kit is the person's word.
  - Size: about 162 pages × 0.3–1 MB is under 160 MB a month. A year is under
    2 GB, which suits the bucket and not git.
  - Git holds only `snapshots.csv`: per page and month, address, status,
    sha256, bytes and how it was read.
- **Cadence:**
  - Monthly, the first weekend, at 7:30 pm like the captions job.
  - On demand before a release.
  - A page a reader reports as wrong can be read the same day.
- **On the laptop:** the reading (b or a, or the person with c), and the
  upload to the bucket's inbox. Nothing else: no git, no comparison, no state.
- **In a cloud session:**
  - takes the inbox down;
  - runs the comparison;
  - writes the re-dating commit and the report;
  - does (d) for the sites that answer a cloud machine.
- **The person sets up, once:**
  - the scheduled task: one line, like the captions job's `schtasks` line in
    `src/ops/README.md`, or the Cowork scheduled task;
  - signing in to the Claude desktop app or the Chrome extension on the
    laptop;
  - leaving the laptop on and signed in on the first weekend evening of the
    month.
- **The person decides, once:**
  - the evidence default (section 3);
  - the bucket prefix.

## 5. Effort, and what it needs from the person

| step | days |
|---|---|
| the one-evening test, and writing up what it found | 0.5 |
| the laptop reader for the way that passed, its manifest, per-host refusal, schtasks or Cowork line | 1.5 |
| one-time move of 242 claims to quoted `words`, with a preflight check | 1.5 |
| the comparison, re-dating, and the report Artifact with yes/no | 1.5 |
| the bucket inbox for snapshots, `snapshots.csv`, the docs (CONTRIBUTING recipe, src/ops/README.md) | 1 |
| **total** | **about 6 days** |

**From the person:**
- one evening for the test;
- the evidence decision (section 3);
- the go-ahead to add a bucket prefix;
- the laptop on, about one evening a month;
- about 15 minutes a month on the report.

**If (b) and (a) are both refused by nh.gov**, the build is about 3 days:
(c) plus (d) plus the comparison and report. The person still saves the
nh.gov pages, but from a ready list, filed automatically, and only the
changed ones need reading.

## Not decided here

- Whether pages a guide only links, without resting a claim on them, are
  read too. My suggestion is no, except to catch a 404.
- Whether the Spanish catalogue's drafts are re-drafted automatically when a
  yes changes an English sentence. Today a stale Spanish entry falls back to
  English on the page and is listed for the proofreader. That stays.
