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
   `archive/refused.json`. A fetcher that consults it stops for 24 hours and
   then resumes on its own; `build_all.py` tests only whether the file exists,
   so its General Court steps stay skipped for as long as it is on disk.
   Clearing it (`python3 refusal.py --clear`) is the maintainer's decision,
   after `netcheck.py` has said what kind of refusal it was.
3. **Every fetcher that asks the General Court consults it.** All 18
   `fetch_*.py` scripts carrying a literal `gc.nh.gov` URL call
   `refusal.check()` straight after parsing their arguments, and `preflight`
   fails if one stops:

   ```bash
   python3 preflight.py --code
   ```

   Ten of them did not until 18 September, and any of the ten, started by
   hand, would have walked straight through a standing refusal.
   `fetch_town_clerks.py` is deliberately outside the set: it asks
   app.sos.nh.gov, the Secretary of State, and names gc.nh.gov only to say so.

   And each records a refusal it meets. One refusal, a second dropped
   connection, or the firewall's block page served as a 200 -- as
   `refusal.classify()` reads them -- goes on file with `refusal.note()`, and
   the run stops with status 2, so every other fetch stops too. Fifteen
   scripts consulted a refusal and recorded none until 7 October 2026, and
   `preflight` fails a script that calls `refusal.check()` and never
   `refusal.note()`.

The eight `fetch_*_db.py` scripts are the exception worth knowing: they read
the SQL host the General Court publishes credentials for at gc.nh.gov/downloads,
not the web server that did the blocking. Still ask — it is still somebody
else's server — but a refusal there is a different problem with a different
cause.

## Branches: work goes to `dev`, `main` is what is live

The site is rebuilt from `main` every night on GitHub's machines and published
from it, so `main` holds exactly what graniterecord.org runs, and a commit that
reaches it goes live with the next night's build. Work happens on `dev`: open
pull requests against `dev`, not `main`.

A release is `dev` merged into `main` once the whole of it has been checked --
`preflight.py`, a full `build_all.py --local`, `check_site.py`, and
`probe_alignment.py` wherever a timestamp moved -- and the night after it lands
publishes it. Releases are batched on purpose: fewer, complete updates rather
than one per fix.

## Getting set up

```bash
git clone https://github.com/granite-record/granite-record.git
cd granite-record
pip install numpy
python3 preflight.py --code
```

On a fresh clone that prints `114 passed, 0 failed, 8 skipped`. The eight read
the real built `site/`, which a clone does not have. That is the expected first
run.

A clone is about 125 MB and has the code but not the live record —
`README.md` explains what is tracked and what is not, and why.

**Optional dependencies are imported lazily**, inside the functions that need
them, so that a missing one costs you one code path rather than the whole
project:

| package | wanted by |
|---|---|
| `numpy` | `topic_model.py` (the only top-level third-party import) |
| `openpyxl` | `build_manifest.py`, `ground_truth.py`, `probe_alignment.py` |
| `pdfplumber` | calendar and PDF text extraction |
| `pypdf` | PDF page handling |
| `PIL` (Pillow) | `build_brand.py` (drawing your own icons and link-card images; the project's are not in the repository) |
| `faster_whisper` | `transcribe_and_align.py` (transcribing a recording that has no captions) |
| `boto3` | `cloud.py` (the nightly's kit and the backup in the project's R2 bucket; `--local-bucket` needs nothing) |

Please keep them lazy. Tidying them to the top of the file turns seven optional
packages into seven hard requirements.

## How work is done here

**Run `preflight.py` before and after.** It is 161 checks, 122 of which need no
data on disk, and it builds the whole site on a fixture. It is the test suite.
Trust it over anything written in prose, including this file.

**Bump the version stamp in the same edit.** Every script carries
`# GRANITE_VERSION: YYYY-MM-DD.N` and `versions.json` lists what each should
be; `preflight` fails when they disagree. Increment the `.N` and leave the date
alone — it is when the file was created, not last modified. This is the single
most common way a change here fails its own checks.

**Add a check when you fix something a check could have caught.** That is how
most of the current ones arrived, and each one's docstring says what went wrong
to cause it. Those docstrings are the useful part; please write them.

**Measure against something you did not generate.** The strongest results here
came from opening real data first and scoring against a hand-made reference.
`ground_truth.csv` holds 35 proceedings someone timed with a stopwatch, and:

```bash
python3 probe_alignment.py --truth --candidate candidate_segments.json
```

is the gate every timestamp method has to pass. **Nothing about timestamps
ships before that has been run and the median has not regressed.**

**Silence is not success.** A step that can produce nothing and still exit zero
needs a guard that says so. This has bitten the project at least five times.

## Where new code goes

The code is moving out of the root into `src/`, in stages; `src/README.md`
has the tree, says what each folder is for, and is the longer version of
this. The short one:

- **The root** holds what something outside the repository runs by name -- a
  workflow, Task Scheduler, `publish.bat`, the session's first commands
  (`inventory`, `preflight`, `handoff`) -- and the files the person chose to
  keep there, with the config, the docs and all the data. A new script goes
  at the root only for one of those reasons.
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
docs that imports a module of ours before `_paths`. It also holds each
`src/fetch/` folder to its network: a `refusal.check()` outside `gc_web/`, the
SQL host outside `gc_db/`, yt-dlp outside `youtube/`, or a request from any
folder under `src/` outside `fetch/` (but `checks/` asking graniterecord.org)
fails it.

## Five files no generator may write

These are a person's work, and `preflight` fails if any `build_*` or `fetch_*`
script opens one for writing:

| file | what it is |
|---|---|
| `ground_truth.csv` | 35 proceedings timed by watching the recording |
| `review/checked.jsonl` | the bench's judgments, append-only |
| `bill_notes.json` | what a recurring bill number means |
| `officials.json` | offices filled by hand from official sources |
| `member_corrections.json` | a name or party a generator got wrong, with the evidence |

`preflight.py`'s `HANDMADE` is the authoritative list. Read it there rather
than here — the same list in `CLAUDE.md` spent a day saying four after the
fifth file was added, because it was a copy.

## What not to do

- **Do not run `publish`.** It deploys to the live site.
- **Do not edit `STATE.md`.** It is generated by `handoff.py`.
- **Do not add anything under `functions/`.** One endpoint is a deliberate
  exception on a site that is static on purpose; two is a different project.
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
