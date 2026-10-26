# Contributing

Thank you for looking. `README.md` says what this project is; this says how to
work on it without breaking anything that matters.

## The one rule that protects somebody else

**Do not point a `fetch_*.py` script at the General Court without asking
first** — <contact@graniterecord.org>.

This is not caution for its own sake. The address this project runs from has
been blocked by the General Court's firewall **twice**: once for probing
filenames that did not exist, once for running two fetches at the same time.
Getting blocked a third time costs days of work and an email to a Clerk's
office.

Three things follow, and they are not negotiable:

1. **One fetch at a time.** `watchers/gc_lane.py` is the scheduled lane; it
   holds `archive/.lock` and touches it every minute while it works. A fresh
   lock means a fetch is in flight right now. `watchers/README.md` has the
   one-liner that lists every fetch process on the machine. Look before you
   start anything.
2. **A refusal ends the run.** `refusal.py` records one in
   `archive/refused.json`. A fetch started by hand that consults it stops for
   24 hours and then resumes on its own; the lane, `build_all.py`'s General
   Court steps and the nightly test only whether a refusal is on file, so they
   stay stopped for as long as it is. Clearing it --
   `python3 refusal.py --clear`, or `python3 src/ops/cloud.py clear-refusal` for the
   copy the nightly keeps in its bucket -- is the maintainer's decision, after
   `python3 netcheck.py` has said what kind of refusal it was.
3. **Every fetcher that asks the General Court consults it.** All 16
   `fetch_*.py` scripts carrying a literal `gc.nh.gov` URL -- they live in
   `src/fetch/gc_web/` -- call `refusal.check()` straight after parsing their
   arguments, and so does every other script that asks it, the probes among
   them, but `netcheck.py`, which is what diagnoses a refusal. `preflight`
   fails if one stops, and holds the count in this sentence to the scripts it
   reads, so it is the list:

   ```bash
   python3 preflight.py --code
   ```

   Ten of them did not until 18 September, and any of the ten, started by
   hand, would have walked straight through a standing refusal.
   `fetch_town_clerks.py` is deliberately outside the set, in
   `src/fetch/other/`: it asks app.sos.nh.gov, the Secretary of State, and
   names gc.nh.gov only to say so.

   And each records a refusal it meets. One refusal, a second dropped
   connection, or the firewall's block page served as a 200 -- as
   `refusal.classify()` reads them -- goes on file with `refusal.note()`, and
   the run stops with status 2, so every other fetch stops too. Fifteen
   scripts consulted a refusal and recorded none until 7 October 2026, and
   `preflight` fails a script that calls `refusal.check()` and never
   `refusal.note()`.

The `fetch_*_db.py` scripts in `src/fetch/gc_db/` are the exception worth
knowing: they read the SQL host the General Court publishes credentials for at
gc.nh.gov/downloads, not the web server that did the blocking. Still ask — it
is still somebody else's server — but a refusal there is a different problem
with a different cause.

## Branches: work goes to `dev`, `main` is what is live

The site is rebuilt from `main` every night on GitHub's machines and published
from it, so `main` holds exactly what graniterecord.org runs, and a commit that
reaches it goes live with the next night's build. Work happens on `dev`: open
pull requests against `dev`, not `main`.

A release is `dev` merged into `main` once the whole of it has been proven,
as *How a change is proven* below says, and the night after it lands
publishes it. Releases are batched on purpose: fewer, complete updates rather
than one per fix.

### Undoing a bad publish

**Put the last good build back first, then fix.** In Cloudflare's dashboard:
Workers & Pages → `graniterecord` → Deployments → *All deployments*; on the
last good Production deployment, the ⋯ menu → **Rollback to this
deployment**, and confirm. It is instant, and any production deployment that
built can be chosen; a preview cannot. Wrangler has no rollback command
(`npx wrangler pages deployment list --project-name=graniterecord
--environment=production` lists the ids); the API's `POST
/accounts/<account>/pages/projects/graniterecord/deployments/<id>/rollback`
does what the button does. (Cloudflare's *Rollbacks* page and Wrangler's
Pages commands, read 25 October 2026.)

**A rollback lasts until the next night publishes**, at 08:17 UTC:

- The night compares its build with what graniterecord.org serves. After a
  rollback production serves an older build, so the night's build counts as
  new and is sent for production.
- It waits for your approval when its code is not the code of the build
  production serves (that build's `build.json` names its commit; one with
  none waits too) -- unless a dry run of the same commit came back clean
  within 48 hours, and then it may go out on its own. So revert the bad
  change on `main` before 08:17 UTC, and do not approve a night that would
  publish it again: the day's data can bring a bad build back as surely as
  code.
- Re-running or approving an older night's publish job is no way back: the
  publish job refuses a night older than the newest night fit for
  production ("NOT DEPLOYED: a newer night ... has built a site fit for
  production since this one").

## Getting set up

```bash
git clone https://github.com/granite-record/granite-record.git
cd granite-record
pip install numpy
python3 preflight.py --code
```

On a fresh clone the summary ends `0 failed`, with a few skipped: those read
the real built `site/` or the record, which a clone does not have, and say so
one by one. That is the expected first run. Take the counts from the summary;
they move as checks are added.

A clone has the code but not the live record —
`README.md` explains what is tracked and what is not, and why.

**Optional dependencies are imported lazily**, inside the functions that need
them, so that a missing one costs you one code path rather than the whole
project:

| package | wanted by |
|---|---|
| `numpy` | `src/parse/topic_model.py` (the only top-level third-party import) |
| `openpyxl` | `src/hearings/build_manifest.py`, `src/hearings/ground_truth.py`, `src/hearings/probe_alignment.py` |
| `pdfplumber` | calendar and PDF text extraction |
| `pypdf` | PDF page handling in `fetch_committee_reports.py` and `extract_calendar_text.py`'s last fallback (not installed by the nightly: when it makes the text of the calendars and journals it fetched, it uses a pinned `pdftotext`, which `nightly.yml` installs and checks by its sha256, and keeps no text a fallback made) |
| `xlrd` | `src/parse/parse_sos_results.py`, for the Secretary of State's older `.xls` results (`xlrd==2.0.2`; the nightly installs it, so its 2024 results check runs there) |
| `PIL` (Pillow) | `src/pages/build_brand.py` (drawing your own icons and link-card images; the project's are not in the repository) |
| `faster_whisper` | `src/fetch/youtube/transcribe_and_align.py` (transcribing a recording that has no captions) |
| `boto3` | `cloud.py` (the nightly's kit and the backup in the project's R2 bucket; `--local-bucket` needs nothing) |

Please keep them lazy. Tidying them to the top of the file turns seven optional
packages into seven hard requirements.

The versions the nightly and the weekly install are pinned once, in
`requirements.txt`; the night's caption tools (`yt-dlp` and its solver) are
pinned in `nightly.yml`'s own step, where preflight's livestream check reads
them; and so is the night's `pdftotext`, a poppler build for Windows pinned
by the sha256 of its zip and installed only while the repository variable
`NIGHT_DOCUMENTS` is not `off` (preflight's check of the night's documents
reads it).

## How work is done here

**Run `preflight.py` before and after.** It is several hundred checks --
`--code` runs the ones that need no data on disk -- and it builds the whole
site on a fixture. It is the test suite. Trust it over anything written in
prose, including this file.

**Bump the version stamp in the same edit.** Every script carries
`# GRANITE_VERSION: YYYY-MM-DD.N` and `versions.json` lists what each should
be; `preflight` fails when they disagree. Increment the `.N` and leave the date
alone — it is when the file was created, not last modified. This is the single
most common way a change here fails its own checks, so one command makes both
edits: `python3 src/ops/inventory.py --bump-changed` bumps every stamped file
changed since the last commit (or since a base you name, such as `origin/dev`,
for a branch of several commits), once, and is safe to run again.

**Add a check when you fix something a check could have caught.** That is how
most of the current ones arrived, and each one's docstring says what went wrong
to cause it. Those docstrings are the useful part; please write them.

**Measure against something you did not generate.** The strongest results here
came from opening real data first and scoring against a hand-made reference.
`review/ground_truth.csv` holds 35 proceedings someone timed with a stopwatch, and:

```bash
python3 src/hearings/probe_alignment.py --truth --candidate candidate_segments.json
```

is the gate every timestamp method has to pass. **Nothing about timestamps
ships before that has been run and the median has not regressed** on the
proceedings both the old and the new results place (`livestreams.worse`).

**Silence is not success.** A step that can produce nothing and still exit zero
needs a guard that says so. This has bitten the project at least five times.

## How a change is proven

Three steps, each catching what the one before cannot.

1. **`python3 preflight.py`**, before and after. `--code` alone needs no data
   on disk and takes a few minutes; with no flag it adds the checks that read
   the record and the built site. The summary must end `0 failed`. A check
   written ahead of the change that will make it pass is marked
   `expect_fail` with that change named: it still runs and prints what it
   found, it is counted apart (`N expected to fail`), and the run in which it
   passes fails until the mark comes off.
2. **A date-fixed build, compared file by file.** The day a build is made is
   in every page, so two builds made on different days differ everywhere.
   `GRANITE_BUILD_DATE=2026-10-02` (or a moment, `2026-10-02T01:22:13`) states
   the day for every builder, and `build_all.py` records it in
   `site/build.json`. For a change meant to leave the site alone, build before
   and after with the same date, keeping the first build's `site/` aside, and
   compare a sha256 of every file; build the baseline twice first, under
   different `PYTHONHASHSEED` values, to prove the output is deterministic
   rather than assume it. For a change meant to move the site, the same diff
   says exactly which files moved. Then `python3 src/checks/check_site.py` on the result,
   and `python3 src/hearings/probe_alignment.py --truth` wherever a timestamp
   moved. `ARCHITECTURE.md` (*Comparing two builds*) has the detail. For a
   change to how pages look, `python3 src/checks/rendered_sweep.py` on the
   build before and after (the second with `--compare` and the first's
   report): it has headless Chrome draw a fixed list of page types at three
   widths, in both themes, in forced colours and at a 24px browser text size,
   measures every text's size and contrast, every sideways overflow and any
   text drawn over other text, and saves a screenshot of each. Look at the
   screenshots, not only the numbers.
3. **A dry run of the nightly on `dev`.** In GitHub's Actions tab, "nightly",
   "Run workflow", choose `dev` and leave "Dry run" ticked: the same night
   GitHub runs on `main`, on an empty machine with the kit from R2, built and
   checked by the same gates, and nothing goes to production. "Take the
   day's data" is unticked by default, so it builds from the kit and asks the
   General Court nothing; tick it only when the change is to the fetch. It
   can be started at any time, a night waiting for approval included: its
   verdict is kept apart, in `archive/last-dry-run.json`, and the waiting
   night stays approvable (until 7 October 2026 a dry run's verdict became
   the newest and that night's deploy was refused), and its preview goes to
   `dry-run.graniterecord.pages.dev`, never to the night's preview that a
   waiting night is approved from. It sends back to the
   bucket only what it fetched and its logs, so nothing `dev`'s code made is
   built from by `main`'s next night. Since 7 October 2026 every run of a
   branch other than `main` is a dry run whatever its boxes say -- unticking
   "Dry run" on `dev` changes nothing, a weekly run on `dev` proves the
   weekly's code and keeps nothing it fetched, a New term run there is
   refused, and no dry run pings Healthchecks -- so only a run of `main` can
   publish, or keep what it took for the next night. Dry runs wait for each
   other: one started while another is running waits behind it (and replaces
   any dry run already waiting there), so that it cannot cancel a scheduled
   night waiting for the running one to finish.

The first runs on a bare clone. The second needs the record on disk and the
third the repository's own secrets, so for a pull request from outside they
are the maintainer's to run; say in the request what you expect the second to
show.

### Iterating without waiting on the whole of it

Three tools for the time between those proofs, none of which replaces one.

- **A change to the browser's files alone** -- `src/pages/app.css`,
  `components.js`, `app.js` or `find.js` -- goes into the site the last full
  build made with `python3 build_all.py --front-end`, in seconds, through the
  same function
  the build calls (`src/pages/front_end.py`); `--dry-run` says what it would
  write. It refuses, and names the file, when anything else the build reads
  has moved since that build -- a script, a data file, a fetch, `bills.html`
  (which every page is built from) -- because the rest of `site/` would then
  not be what a build makes. Where app.js's search tables or data.html's
  counts moved it runs the one step that makes them, as the build does. It is
  for looking at a change; `publish` builds in full.
- **The checks a change can reach.** `python3 preflight.py --changed` runs
  the always-run guards (version stamps, control bytes, credentials and
  addresses, the refusal and hand-made-file guards and the rest, named in
  every run) and the checks related to what changed since the merge base
  with `dev` -- or since `--changed <commit>` -- and `--verbose` says why
  each was chosen. It says, every time, that it is not the full suite: the
  full suite is what runs before a merge into `dev`.
- **A baseline once per commit.** `src/checks/site_manifest.py` keeps the
  sha256 manifest of a build, keyed by its commit, its stated day, its
  options and the data under it, so the "build before" of step 2 is made
  once for a base commit rather than once for each step of a piece of work.
  In `cmd`, on the base commit:

  ```
  git switch --detach <base commit>
  set GRANITE_BUILD_DATE=2026-10-09
  set PYTHONHASHSEED=0
  python3 build_all.py --local
  python3 src/checks/site_manifest.py record
  set PYTHONHASHSEED=1
  python3 build_all.py --local
  python3 src/checks/site_manifest.py record
  git switch <your branch>
  ```

  The second `record` compares the two seeds' builds file by file and says
  the baseline is deterministic, or names what moved. Then, for every step
  of the work, with the same day stated and the same options:

  ```
  python3 build_all.py --local
  python3 src/checks/site_manifest.py compare
  ```

  which compares `site/` with the merge base's kept manifest, names every
  file changed, added or removed, and exits 0 only when nothing moved. It
  refuses a comparison across different data or options, and says how to
  make a baseline where there is none. `python3 src/checks/site_manifest.py
  list` shows what is kept, in `logs/site-manifests/`.

## Where new code goes

Code that is not an entry point lives under `src/`; `src/README.md` has the
tree, says what each folder is for, and is the longer version of this. The
short one:

- **The root** holds what something outside the repository runs by name -- a
  workflow, Task Scheduler, `publish.bat`, `preflight` -- and the few the
  maintainer chose to keep there, with the config and the docs. A new script
  goes at the root only for one of those reasons. The data git keeps is in
  five folders beside it (README.md's "What's where").
- **`src/ops/`** for a tool that keeps the site running rather than builds
  it, run by its path by a workflow, the morning triage or a person: the
  bucket (`cloud.py`), the night's livestreams, the reader reports and the
  session's first commands (`inventory`, `handoff`).
- **`src/fetch/<whose server>/`** for anything that asks another server:
  `gc_web/` for gc.nh.gov (it calls `refusal.check()` straight after its
  arguments, and `refusal.note()` on a refusal it meets), `gc_db/` for the
  General Court's SQL host, `youtube/`, and `other/` for everyone else. The
  folder is decided by whose server it asks.
- **`src/parse/`** if it decides a fact from what is on disk, **`src/towns/`**
  if that fact is about a town, a district, a county or their officials,
  **`src/hearings/`** if it is about a proceeding or its recording,
  **`src/pages/`** if it writes what a reader gets in `site/`,
  **`src/checks/`** if it only looks and reports, and **`src/lib/`** only for
  a module several folders import that belongs to none of them.
- **`functions/api/`** for a request handler on graniterecord.org, and
  **`workers/<name>/`** for a Cloudflare Worker deployed on its own.

Wherever it goes, a new script:

1. **Has a name no other code file has.** Every import and every launch is by
   bare name, and `_paths.py` puts every code folder on the import path, so a
   file can move between folders without anything that names it changing.
2. **Starts with the bootstrap** -- the five lines after the docstring of any
   runnable script, `_paths.BOOTSTRAP` -- before it imports anything of this
   project's.
3. **Is started by its bare name.** A build step is a `Step()` in
   `build_all.plan()` naming `"your_script.py"`; anything else that starts a
   script as a process does it through `_paths.script("your_script.py")`.
4. **Finds the repository through `_paths.ROOT`**, never through
   `Path(__file__).parent`, which is the root only while the file sits there.

`preflight` holds all four -- the third wherever it can see how the script's
path was made, in the launch itself or in what the file assigns to the
variable it launches -- and fails on a `python3 -c` written in the code or the
docs that imports a module of ours before `_paths`, and on a command the code
or the docs give that names a script under `src/` without its folder
(`python3 x.py`, or a backticked `x.py --flag` in a document), which typed
from the root would answer "can't open file". It also holds each
`src/fetch/` folder to its network: a `refusal.check()` outside `gc_web/`, the
SQL host outside `gc_db/`, yt-dlp outside `youtube/`, or a request from any
folder under `src/` outside `fetch/` (but `checks/` asking graniterecord.org)
fails it.

## Recipes for the common changes

Each is the whole list of places one kind of change touches, in order, so
that nothing is found missing a session later. Every one ends the same way:
`python3 src/ops/inventory.py --bump-changed`, then `python3 preflight.py
--code`, which must end `0 failed`.

**Add a check to preflight.**
1. Write a function under `@check(group, "what it holds, as a sentence",
   needs=("module", ...))` beside the checks of the same subject; `needs`
   names the project modules it imports, and the check is skipped, saying
   so, where one will not import.
2. Its docstring says what went wrong that it exists for, with the date and
   the real case. That is the useful part.
3. Return `("ok", "what it found")`, or `("skip", "why")` where its input is
   not on this machine; fail with `assert`.
4. A check that reads a built site uses `_fixture_site_shared()` (read only)
   or `_fixture_site_whole(root)` (a copy it may write), rather than building
   its own.
5. A data check runs on the night after the build unless it is named in
   `NOT_ON_THE_NIGHT` with its reason; one that compares against the
   official record goes in `RECORD_CHECKS`, so it warns rather than holds
   the night.
6. A check written ahead of the change that makes it pass carries
   `expect_fail="the change"`.

**Add a build step, or give one a new input.**
1. A `Step("what it does", ["script.py", ...], needs=[...], produces=[...])`
   in `build_all.plan()`, after the steps that make its inputs. The script
   is named by its bare name and starts with the bootstrap (*Where new code
   goes*).
2. An input git does not track and no step produces is named in preflight's
   `ic_SOURCES`, with what writes it -- and in `cloud_kit.json`, so the
   nightly's empty machine is given it. A file the step reads and then
   rewrites goes in `build_all.CARRIED` and the kit.
3. A step that can finish having made nothing gets a guard that says so.
4. `python3 build_all.py --dry-run` shows the plan with it in place.

**Show a new fact on a bill's page.**
1. `src/pages/build_site_v2.py` puts it in the bill's record; if it comes
   from a new file, declare that file in the step's `needs`.
2. `src/pages/app.js` draws it, in the tab's `render…` function (`BILL_TABS`
   maps each tab's address to its function). A person, a committee, a date
   or a time is drawn with `components.js`'s helper for it, never by hand.
3. If the bills list or the search needs it too, the index row (the
   function near `idx/<term>.json` in build_site_v2) -- every visitor loads
   that file, so keep it small and run `src/checks/check_site.py`.
4. If it belongs in the downloads, `src/pages/build_exports.py`;
   `/data/manifest.json` lists the columns by itself.
5. If a published file's shape changed, README's *The data*.
6. A check: preflight loads `app.js` in node against `tests/dom_stub.js` and
   calls `render()` and `renderDetail()` on the fixture, so a check can hold
   what the tab draws.

**Change a word the site says in many places.** The approved wording lives
once, in `src/pages/words/` (`votes.json`, `chips.json`, `glossary.json`,
`meeting_kinds.json`, `study_report.json`). `components.py` reads it for the
pages built in Python and the build writes it into `components.js` for the
browser, so an edit there reaches both. A word that is not there yet goes
there, rather than into a page's own code.

**Change how something looks.** There is one stylesheet,
`src/pages/app.css`, and every page links it (since 23 October 2026).
1. A colour or a size is a token in the palette at the top (`:root`, and
   its dark twin below it); change the token rather than a rule that uses it.
2. A new rule goes wherever it reads best and reaches every page. Two scopes
   remain, written into the selector: `:where(body.pg)` for the five pages
   `build_pages.py` writes (home, Officials, About, `/search`, 404), and
   `:where(body:not(.pg))` for a record page's rule that must not reach them.
   The note at the top of `app.css` says so.
3. If the colour is one an email shares (an ink, a status chip, the vote
   ring), run `python3 src/pages/follow_site.py` too (the email recipe below).
4. `python3 build_all.py --front-end` puts it into the last full build in
   seconds, to look at; `python3 src/checks/rendered_sweep.py`, before and
   after with `--compare`, measures every page type's text, contrast and
   overflow at three widths in both themes.

**Change or add words the site says in its own voice, on a page that is
also in Spanish** (the home page, the header, the footer, Settings, the
search box). Write the English as it always was, inside `say(lang, "key",
"English")` in Python or `tr("key", "English")` in a script, the key and the
English written out. Then `python3 src/ops/translations.py --set key
"Spanish"` adds or brings up the Spanish, as a draft for the proofreader.
Preflight fails until every key the code says has Spanish translated from
the English it says now. A title, a name or a docket line is the record's
and is not translated. `docs/TRANSLATING.md` has the rest.

**Change the header, the nav, the footer, the fonts or the icons.** One
place: `src/pages/chrome.py`. Both kinds of page ask it -- record pages
through the `<!-- CHROME:... -->` slots in `bills.html`, the five pages
`build_pages.py` writes through the same four calls -- so an edit reaches
every page at the next full build (`--front-end` refuses it, since every page
is rewritten). A new section of the site is a row of `chrome.NAV_TABS`.
Preflight fails if any page writes the frame by hand.

**Add a kind of page.**
1. A builder in `src/pages/`, with a name no other file has, that makes each
   page with `shell.page(shell.template(), path=..., title=...,
   description=..., base=...)`, so it gets the frame, the stylesheet, the
   citation and the share card.
2. Its addresses go in the sitemap through `shell.sitemap_merge(site, base,
   urls, owns="/your-folder")`, so an address it stops writing is dropped.
3. A `Step` in `build_all.plan()` after the steps it reads (the build step
   recipe above), and a stamp and a `versions.json` entry for the new file.
4. If it is a new section, a row of `chrome.NAV_TABS`.
5. `python3 src/checks/check_site.py` on a build: the deploy allows 100,000
   files and it warns at 90,000, so a page per record is a decision.

**Change what an email says, or how it looks.** The email sender is the
Worker in `workers/follow/` (its README has the whole of it), deployed on its
own rather than by the nightly.
1. A colour, a status chip's word, a study report's words, a testimony form
   or the mark -- anything an email shares with the site -- is changed where
   the site keeps it (`app.css`, `src/pages/words/`, `app.js`,
   `build_brand.py`). Then `python3 src/pages/follow_site.py` rewrites
   `workers/follow/site.gen.js`, which is committed with the change; preflight
   fails until it is, and names what moved.
2. An email's own sentences are in `workers/follow/mail.js`.
3. The tests: `node --test tests/follow/index.js` (preflight runs them too). A
   new `*.test.js` is listed in `tests/follow/index.js`, or preflight fails.
4. To see one without sending it: `node tests/follow/preview_digest.js`
   writes a digest's HTML and text to `preview-mail/`.
5. To have one in your own inbox at once, the preview sender's test send:
   `workers/follow/README.md`, "Sending yourself a test email (preview only)".
6. It reaches readers only when the person deploys the Worker, after the
   change is on `main`: `npx wrangler deploy --config
   workers/follow/wrangler.toml` (with `--env preview` for the preview
   sender), as `workers/follow/README.md` says.

## Files no generator may write

These are a person's work, and they are in two folders: `corrections/`, what
a person corrects or adds to the record by hand, and `review/`, a person's
checks of the site's own work. `preflight` fails if any `build_*` or
`fetch_*` script opens one of their files for writing or writes into either
folder. Among them:

| file | what it is |
|---|---|
| `review/ground_truth.csv` | 35 proceedings timed by watching the recording |
| `review/checked.jsonl` | the bench's judgments, append-only |
| `corrections/bill_notes.json` | what a recurring bill number means |
| `corrections/officials.json` | offices filled by hand from official sources |
| `corrections/member_corrections.json` | a name or party a generator got wrong, with the evidence |
| `corrections/docket_corrections.json` | dates the docket states wrongly and rows it files under the wrong bill, with the evidence |
| `corrections/place_corrections.json` | values the Secretary of State's clerk-and-polling list states wrongly, with the second source |
| `corrections/ballot_results.json` | the statewide vote on each constitutional amendment, copied by hand from the source each row names |
| `corrections/status/` | the state of the session, which no published file carries |

The folders are the authoritative list: `preflight.py`'s `HANDMADE` reads
them as they stand, so a file put in either is guarded the day it is put
there. A copied list went stale twice -- `CLAUDE.md` spent a day saying four
after the fifth file was added, and this table said five while the list held
nine.

## What not to do

- **Do not run `publish`.** It deploys to the live site.
- **Do not edit `STATE.md`.** It is generated by `handoff.py`.
- **Do not add an endpoint under `functions/` without asking first.** The
  report box's and email following's are deliberate exceptions on a site
  that is static on purpose, and each one more is a server to keep up.
- **Do not reformat a file you are not otherwise changing.** A reformat hides
  the real diff, and this repository is read by people trying to work out why
  something is the way it is.

## Data, and what it is not ours to license

The underlying record is the New Hampshire General Court's, and this project
claims nothing over it. The code is MIT (`LICENSE`); `DATA.md` separates the
software from the state's record from the texts generated here. If you are
redistributing the data, cite gc.nh.gov rather than this site — every page here
links what it was drawn from, for exactly that reason.

## Reporting a problem rather than fixing one

Wrong data on the site goes through the report box on the page it is wrong on.
Security issues go to `SECURITY.md`. Everything else:
<contact@graniterecord.org>.
