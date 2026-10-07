# Granite Record

A public record of the New Hampshire General Court, live at graniterecord.org.
33,683 bills across 19 terms, 1989 to 2026; 406 sitting legislators and the
2,192 people in `careers.json`, which is everyone with a recorded roll-call
vote since 1999 rather than everyone who has served -- roll calls start in
1999 and the bills start in 1989; hearings on record for all nineteen terms,
each with its own `verification_manifest*.csv`; and for the recorded ones, the
moment in the recording where a chair took the bill up.

Every hand-written document here drifts, this one included; `STATE.md` is
generated and does not, so where a count disagrees, `STATE.md` wins.

Static site: files on a CDN. That constraint is deliberate. There is exactly
one exception: `functions/api/report.js`, the POST endpoint behind the "report
a problem" box. It is write-only, on no page's critical path, and the box falls
back to an email link when it is down, which is why it is acceptable on a site
that is static on purpose.

---

## Do this first, every session

```
python3 inventory.py       # every file and its version
python3 preflight.py       # the checks; builds the whole site on a fixture
python3 handoff.py         # writes STATE.md with current counts
```

A couple of minutes, no network -- `preflight` is nearly all of it, and its
`--code` half alone is about a minute of that. **Trust their output
over anything written in prose, including this file.** If `preflight` is not
green, fix that before anything else.

`STATE.md` is generated. Never edit it. `README.md` is the front door,
`ARCHITECTURE.md` explains how the code and the data work, `DATA.md` what each
published file holds, and `CONTRIBUTING.md` how a change is made and checked.

---

## Never run these without asking

**Any script that asks the General Court.** That is every `fetch_*.py`, and a
few others: `snapshot_gencourt.py`, `resolve_members.py`,
`check_civics_links.py` and the `probe_*.py` scripts that ask the web server.
They hit the New Hampshire General Court's servers. This address has been
blocked twice by their firewall: once for probing filenames that did not
exist, once for running two fetches at the same time. Getting blocked again
costs days and an email to a Clerk's office.

If a fetch is genuinely needed, say so and let the person start it. Never run
two at once. `python3 netcheck.py` diagnoses a refusal without making things
worse.

**Before assuming nothing is running.** `watchers/gc_lane.py` is the scheduled
lane, it works the queue in `watchers/gc_lane.queue`, and it holds
`archive/.lock` with its pid and touches it every minute while it does. A fresh
`archive/.lock` means a General Court fetch is in flight right now;
`logs/gc_lane.log` says which step and `logs/gc_*.log` how far it has got.
`watchers/README.md` explains the lane and carries the one-liner that lists
every fetch process on the machine. Look there before starting anything — a
session that trusted a stale table in a document is how the second block
happened.

**A refusal outlives the run that met it.** `refusal.py` records one in
`archive/refused.json` and holds the fetch lane for 24 hours. It exists because
a drain that met two 403s stopped itself correctly, and a chained run started
asking the same address for a docket twelve seconds later. Clearing it is a
person's decision: `python3 refusal.py --clear`, after `netcheck.py` has said
what kind of refusal it was.

It holds every fetch that asks the General Court. Every script carrying a
literal `gc.nh.gov` URL calls `refusal.check()` straight after parsing its
arguments, and `preflight` fails if one stops; its refusal check reads every
script, so it is the list. That includes `fetch_archive_bills`, which asks
`bill_status/legacy/bs2016/`, the one path their IT office asked this project
to go lightly on.

`fetch_town_clerks` is deliberately outside that set: it asks app.sos.nh.gov,
the Secretary of State, and names gc.nh.gov only to say so. The check tests for
a URL rather than for the words, so that distinction survives.

The `fetch_*_db.py` scripts are the exception worth knowing about: they
read the SQL host the General Court publishes credentials
for at gc.nh.gov/downloads, not the web server that did the blocking. Still
ask -- they are somebody else's server -- but a refusal there is a different
problem with a different cause. `probe_db.py` reports what is in it;
`probe_db.run_to_file` streams an answer too big for the JSON bridge, which is
anything past a few thousand rows.

The `*_from_db.py` scripts -- `docket_from_db.py`,
`document_versions_from_db.py`, `rollcalls_from_db.py` and
`testimony_from_db.py` -- ask nobody anything, despite the name. The
database is already dumped to `db/` on this disk and they reshape it into the
files the parsers read: standard library only, no network, free to run without
asking.

**`publish`, and anything that changes `main`.** `publish` deploys to the live
site from this machine. GitHub's nightly builds `main` and publishes it, so a
merge to `main` goes live the next night. `cloud.py seed-kit` and
`cloud.py push` change the private bucket the nightly builds from.

Everything else — builds, checks, parsers, the site build — is fine to run
freely.

---

## The rules that produced the good results

**Read the artefact before modelling it.** Every good result here came from
opening real data first. The timestamp method that scores one second was built
by reading actual transcripts and collecting the phrases chairs really use. Its
predecessor was built from an assumption about how meetings run and scores 1m
27s against the same hand-marked times. When tempted to write a parser from a
description, open the file.

**Measure against something you did not generate.** `ground_truth.csv` holds 35
proceedings a person timed by watching the video, and `review/checked.jsonl`
holds whatever the bench has added since — `python3 src/checks/review.py`
serves one sample at a time and appends a judgment. Any timestamp method is scored with:

```
python3 src/hearings/probe_alignment.py --truth --candidate candidate_segments.json
```

The candidate median is **0m 01s**, against 1m 27s for the clustering model and
17m 05s for the schedule alone. **Nothing about
timestamps goes on the site before that comparison has been run and the median
has not regressed.** This matters more in an agentic loop, not less: it is the
guard against tuning a pattern until the number looks right.

**Silence is not success.** A build that finishes having published nothing; a
fetch killed at fifteen minutes that looks like a hang; a step that prints one
line in twenty minutes. Five separate instances in a week. If a step can
produce nothing and still exit zero, it needs a guard that says so.

**A writer of a derived file, run on a subset, destroys the rest.** The
manifest lost the 35 hand-marked times twice. `segment_markers --transcript X`
once discarded 842 recordings' results. Writers merge; a full rebuild is an
explicit flag; anything a person made by hand lives where no generator writes.

**Say when something is a guess.** An invented number stated plainly ("whisper
takes about six hours" — it took forty minutes) costs more than an admission of
not knowing.

---

## How the code is arranged

**`proceedings.csv` is the one table.** Built by `build_proceedings.py` from
every `verification_manifest*.csv` — one per term — plus the floor index, and
read through `proceedings.py` by everything. It globs them all on every run so
that no writer here ever sees a subset (`manifest_paths()` in
`build_proceedings.py`). It
exists because those sources used to be read separately and five tools in one
day were found to silently exclude floor debates — each presenting as a
different bug. **Do not add a sixth reader
of the old files, and do not give it a `--term` flag.**

**Some files are a person's and no generator writes them.** Among them
`ground_truth.csv` (35 proceedings timed with a stopwatch),
`review/checked.jsonl` (the bench's judgments, append-only), `bill_notes.json`
(what a recurring bill number means — HB1 has been the budget since 1993),
`officials.json` (offices filled by hand from four official sources) and
`member_corrections.json` (a name or party a generator got wrong, with the
evidence for the correction beside it).
`preflight` fails if any `build_*` or `fetch_*` script opens one for writing,
and the check is named for the category rather than for one file, because while
it named only `ground_truth.csv` three of the others had no guard at all. The
list lives in `preflight.py`'s `HANDMADE`; read it there rather than here,
because it has grown more than once.

**`build_all.py` is the pipeline.** `--local` skips the network steps,
`--dry-run` shows the plan. A step marked `superseded=True` is kept for a case
a newer step does not cover and does not run unasked.

**`preflight.py` is the test suite**, and it asks no network. `--code` runs
the checks that need no data on disk. It builds the whole site on a
fixture, loads `app.js` (the script `bills.html` pulls in) in node against
`dom_stub.js` and calls `render()` and `renderDetail()`, and runs
`tests/test_markers.py`. Add a check whenever something breaks in a way a check
could have caught — that is how most of the current ones got there.

**Verifying a refactor.** Build the site into a scratch tree and compare a
sha256 manifest of every file against a baseline -- and build the baseline
twice first, under different `PYTHONHASHSEED` values, to prove the output is
deterministic rather than assume it.

**Timestamps, in order of what they can claim.** A roll call's clock time from
`RollCallSummary.txt` (no captions involved, hand-checked at 3–7 seconds, and
House only — all 3,988 Senate rows across the current file and the 27 archived
years in `rollcalls/` are stamped midnight, so this method places no Senate
floor debate at all, while 5,363 of the 5,577 House rows carry a clock); a
boundary the chair stated, found by `segment_markers.py`; the clustering model
where neither fires. The page says which by what it does *not* qualify: a
stated boundary is shown plainly, and an inferred one carries one word,
*approximate*.

**Marker patterns.** `python3 src/hearings/segment_markers.py --all --gaps` prints what the chair
says where no boundary was found; `--phrases` counts those across every
recording so a shared convention appears as a number rather than a hunch. Add
a phrase to `tests/test_markers.py` **only if it was actually spoken** — the
floor patterns once spent a day being validated against sentences typed out of
a document rather than against a floor caption file.

**Captions are not quoted on the site.** They render "HB 1381" as "HP 1381" and
"HB 1444" as "HB1 1444". A garbled quote presented as what someone said is a
transcription error wearing the clothes of a citation. The timestamp is the
claim; the recording is the evidence.

**The calendars are the independent check**, and the only source for a
hearing the docket never recorded. The House and Senate calendar PDFs are on
disk with text, and `python3 src/hearings/calendar_meetings.py --check` reads the bill-days out of
them at no cost. Run it rather than quoting a count.

**A constructible archive path.**
`gc.nh.gov/legislation/<year>/<HB0000>.html` is built from a year and a
padded number — no search, no session — and carries the sponsor with their
district, the committee of referral, the title, the analysis and the full
text. `fetch_legislation.py` fetches and saves; `--parse` reads what is saved
and touches no network, because the labels change with the decades and a
parser must be allowed to be wrong without costing a request. It is also how
the labels get caught changing: the 1993 pages say `INTRODUCED BY:` and
`REFERRED TO:` where later ones say `SPONSORS:` and `COMMITTEE:`. `--parse`
prints the pages that yield no sponsor -- the rules resolutions, budget bills
and enacted chapter texts, documents that name none.

**The bench.** `review.py` serves one sample at a time on the loopback
address, takes a verdict and a note, and appends to `review/checked.jsonl`.
`python3 src/hearings/probe_alignment.py --truth` reads the timed ones alongside
`ground_truth.csv`'s 35, and `--no-bench` gives the number comparable with
anything recorded before the bench existed. **Take the counts from the
command's own header**, not from a document.

**Settled, and no longer worth revisiting.** The file cap: records travel
inside their own pages, so a bill is one file. Term keying: every per-bill file
is `{term: {bill: ...}}` and `preflight` refuses the old shape.

The deploy's file count is still worth watching before anything adds a file
per record: Cloudflare Pages Pro allows 100,000, and `check_site` warns at
90,000. Run `python3 src/checks/check_site.py` rather than quoting a count.

---

## Branches, the nightly and the kit

`dev` is where work is committed and `main` is what is live: GitHub's nightly
(`.github/workflows/nightly.yml`, `nightly.py`) builds `main` every night and
publishes it. Its machine starts empty. The code comes from a clone; everything
else the build reads -- the General Court's day files, the database dump, the
caption results, the logo and icons -- comes from a private Cloudflare R2
bucket, through the list in `cloud_kit.json`, which `cloud.py` reads. Anything
the build reads that git does not hold must be on that list.

The logo and icons are not part of the open-source release and are not in the
repository (`DATA.md` says what a fork does instead). No secret is ever
tracked, and `preflight` fails if one is.

---

## Version stamps

Every script carries `# GRANITE_VERSION: YYYY-MM-DD.N`, and `versions.json`
lists what each should be. `preflight` fails when they disagree — this has
caught three silently half-applied edits.

**When you change a file, bump its stamp and update `versions.json` in the same
edit.** The date is when the file was *created*, not last modified:
`preflight.py` at `2026-09-04.190` had been edited a hundred and ninety times
since 4 September. Increment the `.N`; leave the date alone. `python3
inventory.py` prints the current stamp of every file; take one from there and
do not copy one into prose. A stamp quoted in a document goes stale, and then
points at whichever other file has since grown into that number.

---

## Environment

Windows. The assistant has PowerShell and a Git Bash shell, and a heredoc in
either eats backslash escapes -- write patch scripts with the editor tool and
copy them in. Python 3.14 as `python3`. Node is installed and `preflight` uses
it. The working folder is the repository root; `work/` holds the caption files,
about 34 GB of them, and `site/` is the built output.

`publish` is a local command that builds, checks and deploys with wrangler.
