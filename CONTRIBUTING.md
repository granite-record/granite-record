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
   `archive/refused.json` and `build_all.py` then skips its General Court steps
   for 24 hours. Clearing it (`python3 refusal.py --clear`) is the maintainer's
   decision, after `netcheck.py` has said what kind of refusal it was.
3. **The machinery does not yet cover every fetcher.** Twelve of the
   thirty-two `fetch_*.py` scripts consult `refusal.py`. The rest would walk
   through a recorded refusal if started by hand:

   ```bash
   grep -l refusal fetch_*.py
   ```

   Closing that gap is a genuinely useful first contribution.

The eight `fetch_*_db.py` scripts are the exception worth knowing: they read
the SQL host the General Court publishes credentials for at gc.nh.gov/downloads,
not the web server that did the blocking. Still ask — it is still somebody
else's server — but a refusal there is a different problem with a different
cause.

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

Please keep them lazy. Tidying them to the top of the file turns four optional
packages into four hard requirements.

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
than here — this table has already been wrong once by being a copy.

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
