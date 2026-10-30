# State sources: getting the state's documents to the sessions

*Phase 1 design, 30 October 2026. Branch `design/state-sources`.*

## The problem

The guides, the Learn pages and the new state budget page rest on state
documents: pages and PDFs on sos.nh.gov, das.nh.gov, revenue.nh.gov, dmv.nh.gov
and the other nh.gov agency sites. None of them can be read by this project's
machines:

- From the cloud containers, sos.nh.gov, app.sos.nh.gov, das.nh.gov,
  www.nh.gov and revenue.nh.gov all answered 403 (measured 29 and 30 October, the manager's brief; the guides' own
  record of the same refusal, from 11 October, is in `guide_sources.py`).
- From the owner's laptop, a script got 403 with 0 bytes from every page it
  asked, on 12 October (`src/fetch/other/guide_sources.py`, lines 17-22).
- On 17 October, the same pages **did** open in the Claude desktop app's
  browser pane on the laptop, one at a time (`guide_sources.py`, the comment
  above `"dmv"`). That is the one measurement that a real browser on the
  laptop gets through. It covers pages, not PDFs: "a PDF downloads there
  rather than displays, so none of the forms was opened".

So the owner downloads each document by hand and sends it on. That is slow
now, and it will make keeping 125 documents current impossible.

The project's rule, the owner's: it **will not pretend to be a browser**. No
faked User-Agent, no hidden automation flags, nothing built to get past a
refusal. And gc.nh.gov is asked only by the project's existing, deliberate
paths (the nightly, and the laptop's fetch lane at the owner's word), never by
anything new; the Legislative Budget Assistant's (LBA) documents live there,
so they are the owner's to save.

## What is already here

- **What the site depends on**: `records/sources/REGISTRY.csv`, new on this
  branch. 137 rows, gathered from `guide_sources.SOURCES`, the printouts'
  `INDEX.csv`, the budget design's request list (branches `design/budget` and
  `sources/budget-pdfs`, not yet in dev) and `docs/ELECTION_WEEK.md`, with the
  2024 results page from preflight's `_SOS_2024`
  (the section *The registry* below).
- **How a reading reaches a session**: `src/ops/state_sources.py`, new on this
  branch, through a `sources/` prefix in the private bucket (the section
  *The hand-over* below). It works the same whichever way of reading is
  chosen, including the owner saving files by hand.

## The options

Each is judged on how it works, what the owner installs or does, the weekly
effort, how reliable it is, what it costs, and whether it is honest under the
rule.

### (a) A Claude session on the laptop, using Claude in Chrome

**How it works.** A Claude session running on the laptop (the Claude desktop
app) uses Claude in Chrome, the browser extension, to open each registered
document in the owner's own Chrome, one at a time. For a page it saves the
page's text; for a PDF it opens the address, and Chrome saves the file. It
files each one under `sources/<id>/<day>`, runs `state_sources.py up`, and
says what changed. On each page that lists documents (the "owner page", say
das.nh.gov/budget/), it also lists any PDF link the registry does not yet
have, for the owner to register or ignore. It never adds a row itself.

It runs on a schedule (weekly) or when asked ("read the DAS budget page now").
Its worklist is `state_sources.py due`, which leaves out every General Court
row by construction.

**What the owner installs or does.** The Claude in Chrome extension in their
Chrome, signed in. Once: Chrome's setting to download PDFs rather than open
them (Settings, Privacy and security, Site settings, PDF documents), so that
opening a PDF's address saves it. Once per site: allow the extension on that
site when it asks (32 state hosts in the registry). Then a scheduled task in the desktop
app, or a sentence to start a run.

**Weekly effort.** None when the schedule runs. The laptop must be awake with
Chrome open; when it was not, the owner starts the run by hand.

**Reliability.** Not measured yet. The evidence is good but indirect: the
desktop app's own browser pane got through on 17 October where a script got
403. Claude in Chrome is the owner's actual Chrome, so it should do at least
as well, and it saves PDFs, which the pane did not. Weak points: the laptop
asleep, Chrome closed, a site permission waiting for a click, the Claude plan's
usage limits on a long run, and a page whose text changes every visit (a date
in its footer), which would show as "changed" every week. **One test settles
whether it passes** (below).

**Cost.** No new money: it runs on the owner's Claude plan. A weekly run of
125 documents is a long session; whether it fits the plan's limits is not
known, and is a guess until the first run.

**Honest?** Yes. It is the owner's real browser, with its own headers, the
owner's own sign-in and the owner's address, reading public pages the owner
asked to have read. Chrome shows that it is being driven. Nothing is faked
or hidden, and when a site refuses, the run stops and says so rather than
trying another way. It is the same thing the owner does by hand, done on the
owner's behalf.

### (b) A laptop script driving the owner's Chrome with Playwright

**How it works.** A script on the laptop starts the installed Chrome through
Playwright (Chrome itself, not Playwright's bundled browser), opens each
registered address, saves the page as PDF and each PDF as a download, and
runs `state_sources.py up`. A Windows scheduled task starts it weekly. No
model is involved: it is deterministic, and it knows each file's address
for certain.

**What the owner installs or does.** Python's Playwright package on the
laptop, a Chrome profile kept for it, and a scheduled task (the laptop
already runs one, the 7:30 pm captions task). About an hour to set up.

**Weekly effort.** None, if it passes.

**Reliability.** Doubtful. It sends Chrome's real headers, but Chrome under
automation tells every page so (`navigator.webdriver` is true), and bot
filters of the kind in front of nh.gov look for exactly that signal. The
usual ways past it hide that signal, which the rule forbids. So if a site
refuses it, it stops there; nothing can be done about it honestly. Untested.

**Cost.** Free.

**Honest?** Yes, as long as nothing is hidden: it is a real browser telling
the truth about being automated. But it is the closest of the options to the
line, because it is a script, and the 12 October refusal was of a script. **It
is the owner's decision whether this counts as pretending.** My reading is
that it does not, and that it will probably be refused anyway.

### (c) Asking the agencies

**How it works.** The owner, as a legislator, asks for what the site needs:

- **The LBA**: its revenue reports and budget documents by email as they are
  issued (the LBA serves legislators; whether it keeps a mailing list is not
  known).
- **The Department of Administrative Services' budget office**: the budget
  book and the other budget documents, and word when new ones are posted.
- **The Secretary of State's elections division**: the 2026 general election
  results spreadsheets when they are final.
- **The state's web team (the Department of Information Technology)**: to let
  an honestly identified reader through. `guide_sources.py` already says who it
  is ("GraniteRecord/1.0 (graniterecord.org; ...)"); if the state agreed to
  let that through from one address, the script that exists would simply work.
  This is the only option that fixes the cause rather than working round it.

**What the owner does.** A few emails, once. Filing what comes back
(`state_sources.py` files it like any other reading).

**Weekly effort.** Filing what arrives: minutes.

**Reliability.** Depends on people. Good for the budget and election
documents; it does not cover 125 guide pages. The web team may say no; asking
costs nothing.

**Cost.** Free.

**Honest?** Entirely.

### (d) The Wayback Machine, as a dated fallback

**How it works.** When a registered document cannot be read, look for its
latest snapshot on web.archive.org and file it with the snapshot's own date,
saying it is a snapshot. The manager's brief reports das.nh.gov/budget/ there
from November 2025 (not checked from here).

**What the owner does.** Nothing.

**Reliability.** The archive has what it has. Its snapshots are irregular
and often months old: fine for "what did this page say in March", not for
"what does it say now", which is what a guide states.

**Cost.** Free.

**Honest?** Reading a snapshot, yes. Asking the archive to take a new one
("Save Page Now") to get a page this project cannot reach is getting round a
refusal through someone else's machines, and I recommend against it.

### (e) Better ideas found along the way

1. **The owner clicks, a filer files** (the manual mode of (a)). `state_sources.py
   due` lists what is due; the owner opens each link in Chrome, saves it, and
   one command files the downloads by their source address, which Windows
   records on every file Chrome downloads (its "Zone.Identifier" note; to be
   confirmed on the laptop). About 10-20 minutes a week for the documents that
   are due, rather than all of them. Always works, and is the fallback for (a)
   on any week it does not run.
2. **The web team's allowance** in (c), which would retire the problem.
3. **Read less, more often.** The registry gives every document a guess at
   how often it changes, so a weekly run reads only what is due: election
   pages weekly, fee pages monthly, forms quarterly. After a couple of months
   the change reports measure it, and the guesses are replaced.

### Side by side

| | How | Owner installs | Weekly effort | Reliable? | Cost | Honest? |
|---|---|---|---|---|---|---|
| **(a) Claude in Chrome** | A session on the laptop drives the owner's Chrome | Extension, a PDF setting, site permissions once | None when scheduled | Likely; untested | Owner's plan | Yes |
| (b) Playwright | A script drives the installed Chrome | Playwright, a scheduled task | None | Doubtful | Free | Yes if nothing is hidden; **owner's call** |
| (c) Ask the agencies | Emails, and the web team's allowance | Nothing | Minutes | Depends on people; budget and elections only | Free | Yes |
| (d) Wayback | Old snapshots, dated as such | Nothing | None | Stale | Free | Yes (not Save Page Now) |
| (e1) Click and file | The owner opens what is due; a filer files it | Nothing | 10-20 min | Always works | Free | Yes |

## Recommendation

**(a), Claude in Chrome on the laptop, weekly, with (e1) as its manual mode
and (c) in parallel.**

- (a) is the only option that is both likely to work and needs nothing from
  the owner week to week. It is honest by the rule's own terms: the owner's
  real browser, with nothing faked.
- (e1) is the same pipeline with the owner's hands instead of the session's,
  so no week is lost when the laptop was asleep or a site refused.
- (c) costs a few emails and covers what (a) must never touch, the LBA's
  documents on gc.nh.gov, and the web team's answer could retire the problem.
- (d) stays as a labelled fallback. (b) is not recommended unless (a) fails
  and the owner decides it is acceptable.

### What the owner would do

1. **One test, about two minutes** (on the manager's go: one request per host).
   In the Claude desktop app on the laptop, with Claude in Chrome on, ask it to
   open `https://www.sos.nh.gov/elections/register-vote` and the DAS budget
   book (`https://www.das.nh.gov/budget/Budget2028-2029/FY28-29-Final-Statewide-Agency-Budget-Book.pdf`).
   If the page shows and the PDF saves, (a) works.
2. **Once**: Chrome's PDF setting; allow the extension on each state site when
   it first asks.
3. **Weekly**: nothing. The run's change report reaches the manager, who says
   in a line what changed.
4. **The LBA's documents**: save them by hand as now (into Downloads; the filer
   files them), and, if willing, ask the LBA and DAS for email copies.

## The registry

`records/sources/REGISTRY.csv`, one row per document, columns:

| Column | What it holds |
|---|---|
| `id` | The name it is filed under: `sources/<id>/` locally and in the bucket |
| `url` | Its address; blank for a *wanted* row |
| `kind` | `page`, `pdf`, `app` (a lookup or a form: its front page only), `data`, or `wanted` (needed, address not known) |
| `title`, `publisher` | From the printouts index where it has them |
| `owner_page` | The page it is found on: itself for a page; for a linked document, the pages on its host listed before it in its list, which is a guess and its `note` says so (17 rows); blank where none is on its host |
| `changes` | A guess at how often it changes: `live`, `election`, `budget`, `yearly`, `rarely`, `unknown`. Every value is a guess until the change reports measure it |
| `read_by` | `browser` (an automated reader may open it), `owner-only` (the General Court's: no automated reader, ever), `find` (a wanted row) |
| `used_by` | The guides and Learn pages that cite it (`guide:...`, `learn:...`), or the `guide_sources` list it is in (`guide-list:...`) |
| `listed_in` | Which of the four lists it came from |
| `note` | Anything else |

Counts on this branch: 137 rows; 99 pages, 21 PDFs, 7 apps, 10 wanted;
125 for a browser, 2 the owner's alone (the LBA's budget page and revenue
report), 10 to find. Only state hosts are listed (nh.gov and its
subdomains, and readynh.gov); the federal pages the guides cite can be read
from a session and stay in `guide_sources.OTHER`. The 40 printouts in
`INDEX.csv` with no address (state and federal) are not rows: a row without an address cannot be
read again. Most printouts carry their address in the footer, so the state
ones can become rows once someone reads it off (the guides session's). The registry was assembled once from the four lists; from here it
is kept by hand, and `state_sources.py check` and preflight hold it to its
shape.

**Not settled, for the guides session**: whether `guide_sources.SOURCES`
should in time be generated from the registry, or the registry from it.
Two lists of the same thing drift; that is the guides session's call.

## The hand-over

`src/ops/state_sources.py`, also run as `cloud.py sources-up` and
`sources-down` (a hook of a few lines that hands over to it, agreed with the
manager on 30 October; `cloud.py` is the release session's file). The backup
leaves `sources/` out, since the bucket's `sources/` already holds it.

**On disk.** `sources/<id>/<YYYY-MM-DD>.<ext>`, one file per reading, named by
the day it was read; a second reading the same day is `<YYYY-MM-DD>-2.<ext>`.
git ignores `sources/`.

**In the bucket.** `sources/<id>/<file>` as on disk, and
`sources/manifest.json`: for each id, every distinct version (file, sha256,
size, day read), each reading that matched the latest version (a check), and
the last day it was read at all. Each run that recorded something leaves its
change report at `sources/reports/<stamp>.json`.

**Commands.**

| Command | Who | What |
|---|---|---|
| `check` | anyone | The registry reads; every file in `sources/` is filed under an id it names |
| `up [--dry-run]` | the laptop | Sends each new version; records a reading identical to the latest as a check, sending nothing; prints and stores the change report |
| `down [--into FOLDER]` | a session | Takes every version, checks each against its sha256, and says what changed since this machine last took them |
| `report [--since DAY]` | anyone | Every version in the bucket's record, with its day and sha256 |
| `due` | the laptop | What a browser should read now: never read, or not read within its `changes` interval. Leaves out the General Court's rows |

**The change report.** For each reading: `changed` (its sha256 differs from
the id's latest version, with the old one beside it), `new` (the first
version), or `unchanged` (read again, the same). Each row carries the id,
the file, the day read, the sha256 and the address.

**What it will not do.**

- Replace or remove a reading. A file whose bytes differ from the bucket's
  copy under the same name stops the run and says to name the new one `-2`.
- Take an older reading as a newer version.
- Carry a file the registry does not name, or a file named for a wanted row.
- Report success with nothing done: a folder with nothing in it is a failure.
- Reach anything but the bucket. It asks no state site and never the General
  Court; the General Court's hosts appear in it only so that every such row
  must say `owner-only`.

**Apart from the nightly.** The kit is `cloud_kit.json`'s list, and kit-down
reads `kit/` alone. A new preflight check fails if any entry of the kit, the
state or the dry-run lists could match a path under `sources/`, or if the
nightly or its workflows name the hand-over, and it runs a round trip through
a folder standing in for the bucket.

## How often (guesses, to be measured)

| `changes` | Read again after | Why (guess) |
|---|---|---|
| `live` | 7 days | Lookups and front pages of apps |
| `election` | 7 days | Election pages move around each election |
| `budget` | 14 days | Budget documents arrive in waves in a budget year |
| `yearly`, `unknown` | 30 days | Fees, eligibility, most agency pages |
| `rarely` | 90 days | Forms and PDFs |

## Phase 2, after the owner's OK

1. The guard (`.claude/hooks/guard.py`) asks the owner before `cloud.py push`,
   `seed-kit` and `state-up`, but not yet before `sources-up` or
   `state_sources.py up`, which also write the real bucket. Adding them is the
   owner's decision.
2. The filer: `state_sources.py file ~/Downloads`, which files each download by
   the address Windows recorded for it, and asks about any it cannot place.
3. The laptop runbook (`docs/STATE_SOURCES_RUNBOOK.md`): the one-time setup,
   the scheduled task's prompt for the desktop app, what to do when a site
   refuses (stop, note it, no retry), and the manual mode.
4. A page's text, saved as `.txt`, beside or instead of a printout: the guides
   rest on "the person's printout" today, so whether a text capture counts is
   the guides session's and the owner's decision.
5. Pages read one section at a time: five addresses have two or three
   printouts each, one per section opened (vehicle registrations, the two
   motorcycle pages, boat registrations, landlord and tenant). Under one id per
   address, each reading would look "changed" against another section's. Either
   one reading of the whole page, or an id per section.
6. Owner-page link discovery: on each owner page, the PDF links the registry
   lacks, reported for the owner to register.

## Open questions for the owner

1. Approve the recommendation, (a) with (e1) and (c)?
2. Go for the one test in step 1 (one request per host, from the laptop)?
3. Is (b) acceptable under the rule, if (a) fails? My reading: honest, but
   likely refused.
4. Willing to write to the LBA, DAS and the web team (c)?
