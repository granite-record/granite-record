# Granite Record — handoff

For whoever picks this up next, human or model. Read this once; it changes
slowly. For the current numbers, run `python3 handoff.py` and read `STATE.md`,
which is generated and always right.

---

## How this working relationship runs

**The repository is on the person's machine, not the assistant's.** The
assistant cannot list files, run scripts or read anything it was not given.
Everything it knows comes from what is pasted into the conversation. If it
needs to see a file, it must ask.

So the loop is:

1. The person runs a command and pastes the output.
2. The assistant reads it, works out what to change, and **ships whole updated
   files** as downloadable artifacts.
3. The person downloads them into the working folder, runs the next command,
   and pastes that.

A few things follow from this that are easy to get wrong:

- **The assistant should ask for a file rather than reconstruct it.** Guessing
  at a file's contents has been the single biggest source of wasted turns:
  argument names invented, JSON shapes assumed, functions patched at anchors
  that did not exist. One paste settles what a paragraph of inference cannot.
- **Ship the whole file, never a diff or a snippet to hand-apply.** Patches
  applied by hand drift, and half-applied edits have shipped twice.
- **Say when a command needs a file downloaded first.** Three times a command
  was given that used a flag only present in a file not yet downloaded.
- **Windows `cmd`.** Paths use backslashes, `^` continues a line rather than
  `\`, wildcards are not expanded by the shell, and `<` and `>` are
  redirection. Give commands as one line, ready to paste.

## Start here, before anything else

The person runs these; the assistant reads the output.

```
python3 inventory.py
python3 preflight.py
python3 handoff.py
```

Under a minute, no network. `inventory` lists every file and its version,
`preflight` runs the checks and builds the whole site on a fixture, and
`handoff` writes `STATE.md` with the current counts.

**Trust their output over anything written in prose, including this file.**
Documents go stale; those three read the disk.

If `preflight` is not green, stop and fix that first. It caught three stamp
mismatches, a dead-zone crash and a hung build in one week, and every one of
them would otherwise have reached the site.

## Versions and stamps

Every script carries `# GRANITE_VERSION: YYYY-MM-DD.N` and `versions.json`
lists what each should be. `preflight` fails when they disagree, which has
caught three silent half-applied edits.

The date in a stamp is when that file was **created**, not when it was last
touched: `preflight.py` at `2026-09-04.12` has been edited many times since 4
September. Do not read a stamp as a modification date, and do not conclude
that a file with an earlier date predates one with a later date.

---

## What this is

graniterecord.org: a public record of the New Hampshire General Court. 2,234
bills, 406 legislators, 131,199 votes, every committee hearing and floor debate
linked to the moment in the recording where it happened.

It is a static site. Files on a CDN, no runtime, nothing to go down. That is a
constraint worth keeping.

---

## The five rules

These were learned expensively. Breaking them is how the bad days happened.

**1. Read the artefact before modelling it.** Every good result here came from
looking at real data first. The timestamp method that scores one second was
built by reading actual transcripts and collecting the phrases chairs really
use. The one it replaced was built from an assumption about how meetings run,
and was twelve times worse. When tempted to write a parser from a description,
open the file instead.

**2. Measure against something you did not generate.** `ground_truth.csv` holds
35 proceedings a person timed by watching the video. `probe_alignment.py
--truth --candidate FILE` scores any method against it. Nothing about
timestamps goes on the site before that comparison exists. The tolerances the
site published for months were never checked against anything; when they
finally were, they happened to be honest, but that was luck.

**3. Silence is not success.** A build that finishes having published nothing;
a fetch killed at fifteen minutes that looks like a hang; a step that prints
one progress line in twenty minutes. Five separate instances in a week. If a
step can produce nothing and still exit zero, it needs a guard that says so.

**4. A writer of a derived file, run on a subset, destroys the rest.** The
manifest lost the hand-marked times twice. `segment_markers --transcript X`
once discarded 842 recordings' results. Writers merge; a full rebuild is an
explicit flag; anything a person made by hand lives where no generator writes.

**5. One fetch at a time.** The address has been blocked twice by the General
Court's firewall: once for probing filenames that did not exist, once for
running two fetches at once. Every fetcher now reads a list rather than
guessing. `python3 netcheck.py` says whether a refusal is the address, the
client or the site.

---

## How the timestamps work

This is the part that took the longest and matters most. Three sources, in
order of what they can claim.

**A roll call's clock.** `RollCallSummary.txt` records the wall-clock time of
every House roll call. Subtract the livestream's start and you have the moment
a floor debate ended, from a source with no captions in it. Hand-checked at
seven seconds, three seconds, and exact.

**A boundary the chair stated.** `segment_markers.py` reads caption files and
finds the sentence opening or closing each proceeding, then matches the bill it
names against what the docket scheduled that day. Every pattern was read out of
a real transcript; `tests/test_markers.py` holds all 40 cases and `preflight`
runs them. Scores **one second** at the median against the hand-marked times,
with ends at four seconds.

**The clustering model**, still there, still used where neither of the above
fires. It is not bad -- twelve times better than the schedule -- it is just
outclassed by a quotation.

The site says which: *"the chair opens it at 1:08:43"* against *"estimated
within ±5 min"*. Those are different claims. The chair's words are deliberately
not published, because captions render "HB 1381" as "HP 1381" and a garbled
quote presented as what someone said is a transcription error wearing the
clothes of a citation.

---

## The shape of the code

**One table for proceedings.** `proceedings.csv`, built by
`build_proceedings.py` from the committee manifest and the floor index, read
through `proceedings.py` by everything. This exists because those two sources
used to be read separately, and five tools in one day were found to silently
exclude the floor. Do not add a sixth reader of the old files.

**One record for ground truth.** `ground_truth.csv`, edited by hand only.
`preflight` fails if any `build_*` or `fetch_*` script opens it for writing.

**`build_all.py` is the pipeline.** 14 steps, `--local` to skip network ones,
`--dry-run` to see the plan. A step marked `superseded=True` is kept for a case
a newer step does not cover and does not run unasked.

**`preflight.py` is the test suite.** It builds the whole site on a fixture,
loads `bills.html` in node and calls `render()` and `renderDetail()`, and runs
the marker cases. Add a check whenever something breaks in a way a check could
have caught.

---

## What to do next

In order. The first two are consolidation; the last two gate the archive.
`ARCHITECTURE.md` has the reasoning.

**1. Split `build_site_v2.main`.** `renderDetail` was the other half and was
split on 6 September into nine hoisted functions, one per tab, its output
verified byte-identical against the pre-split page over ten renders.
`build_site_v2.main` is where the floor-marker miss lived, because the
committee and floor station code sit 90 lines apart in one function. One
function per tab, each small enough that declaration order is obvious.

**2. More marker patterns.** `segment_markers.py --all --gaps` prints what the
chair says where no boundary was found; `--phrases` counts those across every
recording so a shared convention appears as a number. That loop took coverage
from 40% to 71% in an evening and is not exhausted. Add a phrase to
`tests/test_markers.py` only if it was actually spoken.

**3. The file cap.** Cloudflare Pages allows 20,000 files; one term already
occupies 8,045. It is three files per bill, not two -- `bill/`, `bills/` and
`feed/bill/` -- which is 6,701 a term, so the cap breaks partway through the
THIRD term. Decide before term-keying is built: fewer static pages for older
terms, or per-bill data in R2 behind a Worker. The two imply different keying
paths, which is why this one comes first.

**4. Term-keyed identifiers.** Bill numbers repeat every two years and nothing
outside `proceedings.csv` knows it. `committee_reports.json`, `bill_text.json`,
`narratives.json`, the per-bill site files and the 2,233 feeds under
`site/feed/bill/` are all keyed on `HB396` alone; `build_feeds.py` has no
notion of a term at all. Fetch anything from 2024 today and it merges into
2026. This gates the archive.

---

## Keeping the documents true

`STATE.md` is generated -- run `python3 handoff.py`. Never edit it.

`HANDOFF.md` (this file), `ARCHITECTURE.md` and `TESTING_QUEUE.md` are written
by a person and should stay short enough to reread. When one of them says
something the code no longer does, that is a bug in the document; fix it in the
same session, because a document that is wrong once is not trusted again.

Numbers do not belong in the hand-written files. If you find yourself typing a
count, it belongs in `handoff.py` instead.

---

## Starting a new session

Paste `HANDOFF.md` and a freshly generated `STATE.md`. Then say what you want
to work on. The person you are working with knows this system well, has caught
several wrong answers, and prefers being told when something is a guess.
