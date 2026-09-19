# Orientation: the scanned journals, 1989 and back

You are working on Granite Record (`D:\nh`), a public record of the New
Hampshire General Court, live at graniterecord.org. Read `CLAUDE.md` first —
all of it. This file does not replace it; it tells you which corner of the
project is yours and which parts belong to somebody else right now.

Your job is one thing, and it is a long one: **get the General Court's
pre-digital record into this site from the scans UNH's library made**, starting
at <https://scholars.unh.edu/senate_house/>.

Work steadily. Nobody is waiting on a deadline. It is better to spend a day
establishing exactly what the source holds than to spend a week parsing the
wrong thing.

---

## The gap you are filling, measured

These are counts from the repository as it stands, not estimates. Re-derive
them yourself before trusting them — they are the reason this work exists, and
a stale number here would point you at the wrong decade.

| term | bills | bills naming a sponsor | proceedings on record |
|---|---|---|---|
| 1989-1990 | 1,632 | **18** | 2,972 |
| 1991-1992 | 1,674 | **16** | 3,454 |
| 1993-1994 | 1,784 | **17** | 4,513 |
| 1995-1996 | 1,586 | **9** | 4,327 |
| 1997-1998 | 1,849 | **19** | 4,784 |
| 1999-2000 | 1,673 | 1,449 | 4,472 |
| 2025-2026 | 2,234 | 2,220 | 11,020 |

So: the bills of 1989-1998 are here and their hearings are here, and almost
nothing knows **who filed them**. Seventy-nine sponsors across 8,525 bills.

Three more holes of the same shape:

- **Roll calls start in 1999.** `rollcalls/` holds `RollCallHistory_1999.txt`
  through 2025 and nothing earlier. Ten years of floor votes — every member's
  name against every question — are not on this site in any form.
- **House journals on disk start at 1997** (`journals/`, 30 year folders).
  **Senate journals start at 2003** (`journals_senate/`, 24 folders). Before
  those, nothing.
- **Floor amendments** of that era are not here at all.

The journals are where all four of those live. A House or Senate Journal is the
chamber's own minute-by-minute record of a sitting day: what was moved, who
spoke, how the House divided, the text of amendments offered from the floor,
and the roll call lists. If the UNH scans go back far enough and are legible
enough, they close the largest remaining gap in this record.

---

## The source

<https://scholars.unh.edu/senate_house/>

**Establish what is actually there before planning anything.** Do not model the
collection from its landing page or from what a repository of that kind usually
looks like. Specifically, find out and write down:

1. What years and which chambers are covered, volume by volume.
2. The file format. Scanned page images? PDF with an OCR text layer already in
   it? If there is a text layer, how good is it — take a page you can check by
   eye and compare.
3. Whether there is a machine route: an OAI-PMH endpoint, a sitemap, an API, a
   bulk export, predictable per-item download addresses. Digital Commons
   repositories often have one; find out whether this one does rather than
   assuming.
4. The terms of use and the licence on the scans, and `robots.txt`. Write down
   what they say. If anything is unclear about whether bulk retrieval is
   permitted, stop and say so — do not decide it yourself.
5. Whether UNH offers a contact for exactly this kind of request. A library
   that has digitised a collection often prefers to hand over a copy rather
   than be crawled, and that is a better outcome for everyone. Say so to the
   person if it looks available; they can send the email.

**Fetching rules.** This is not gc.nh.gov, so the General Court refusal
machinery does not cover it — which means the care has to come from you.
Identify the project in a User-Agent with a contact address. Go slowly, seconds
between requests, never in parallel. Cache everything you retrieve so you never
ask twice. Stop at the first sign you are unwelcome — a 403, a block page, a
rate limit — and tell the person rather than working around it. **Ask the
person before starting any bulk download**, with your estimate of how many
requests and over how long.

---

## Hard boundaries — another session is working in this repository right now

This matters more than anything else here. A second session is actively editing
this repository and will be for some time. Both of you share one working tree.
If you edit what it is editing, one of you loses work.

**Do not edit these files.** They are in flight:

```
build_pages.py   app.css   app.js   preflight.py   seating.py
build_calendar.py   build_indexes.py   bills.html   find.js
```

**Do not run these.**

- `publish` — it deploys to the live site.
- `build_all.py` — it takes a build lock, and two builds at once once destroyed
  seven terms out of `narratives.json`.
- Any `fetch_*.py` that asks gc.nh.gov. A General Court fetch lane is running
  continuously, walking backwards through the archive. This address has been
  blocked by their firewall twice, once for running two fetches at the same
  time. Check `archive/.lock` before assuming nothing is running — a fresh one
  means a fetch is in flight this minute. `watchers/README.md` explains the
  lane.
- `refusal.py --clear`. Clearing a refusal is the person's decision.

**Do not write** `ground_truth.csv`, `review/checked.jsonl`, `bill_notes.json`,
`officials.json` or `member_corrections.json`. Those five are a person's and no
generator touches them. Do not add anything under `functions/`.

**Where you may work freely.** New files with a distinct prefix, so neither of
us can collide by accident:

```
unh_survey.py, unh_fetch.py, unh_parse.py, ...     your code
archive/unh/                                        what you retrieve
data/unh/                                           what you produce
```

`versions.json` is shared and the other session edits it often. Add your files
to it, but expect it to change under you; run `python3 inventory.py` to see the
current state rather than trusting a copy you read earlier. If a git operation
reports a conflict there, take both sides — it is a flat map of filenames.

**Commit often**, small and described, so a collision is recoverable. Do not
commit anything you have not run.

---

## The interface you are attaching to

You are not building a separate thing. Eventually what you extract has to enter
the site through the shapes it already uses. Learn these early, because they
decide what your parser should aim at.

- **`proceedings.csv` is the one table**, and everything reads it through
  `proceedings.py`. It is built by `build_proceedings.py` from every
  `verification_manifest*.csv` — one per term — plus the floor index. Read the
  comment at the top of `proceedings.py`: five tools once read the sources
  separately and every one of them silently excluded floor debates. **Do not
  add a sixth reader of those files.** If you have new proceedings to
  contribute, they arrive as a `verification_manifest*.csv` for their term.
- **Roll calls** live in `rollcalls/RollCallHistory_<year>.txt` and are shaped
  by `rollcall_parser.py`. Read that parser before designing an extraction: the
  file format it expects is the target your journal extraction should produce,
  unless you have a good reason it cannot, in which case say so rather than
  inventing a second format.
- **Bill records** are keyed `{term: {bill: ...}}`, always. `preflight` refuses
  the old un-keyed shape. Bill numbers repeat every biennium, which is why.
- **Archived bill text** lives under `legislation/<year>/<HB0000>.html`.
  `fetch_legislation.py --parse` reads what is saved and touches no network;
  it is a good model for how to separate retrieval from parsing, and you should
  do the same. A parser must be allowed to be wrong without costing a request.
- **Sponsors** are resolved through `names.py` and `resolve_members.py`, and
  `careers.json` holds everyone with a recorded roll call since 1999. Members
  of the 1989-1998 Houses will largely not be in it; work out what identifying
  a member of that era requires before you rely on being able to.
- **Version stamps.** Every script carries `# GRANITE_VERSION: YYYY-MM-DD.N`
  and `versions.json` lists what each should be. Bump `.N` when you change a
  file; the date is when the file was created.

Run `python3 preflight.py` before and after your work. If it is not green, fix
that before anything else — and if you have broken a check that belongs to the
other session's work, say so rather than editing their file.

---

## How this project works

These are not style preferences; each was learned from something going wrong.

- **Read the artefact before modelling it.** Every good result here came from
  opening real data first. The timestamp method that scores one second was
  built by reading actual transcripts; its predecessor was built from an
  assumption about how meetings run and scores twelve times worse. Open a
  journal page and read it before you write a line of parser.
- **Measure against something you did not generate.** Whatever you extract,
  score it against something independent — a page you transcribed by hand, a
  bill whose sponsor is already known from another source, a roll call that
  overlaps 1999. State the number. An extraction with no measured accuracy
  cannot go on the site.
- **Silence is not success.** A run that finishes having produced nothing, and
  exits zero, is the failure mode this project has hit five times in a week. If
  a step can produce nothing and still succeed, give it a guard that says so.
- **A writer of a derived file, run on a subset, destroys the rest.** Writers
  merge. A full rebuild is an explicit flag.
- **Say when something is a guess.** An invented number stated plainly costs
  more than an admission of not knowing. If the OCR is poor and you are
  estimating coverage, say you are estimating.

---

## What to do first

Do not start downloading. In order:

1. Read `CLAUDE.md`, then `proceedings.py`, then `rollcall_parser.py`.
2. Re-derive the gap table above from the repository so you know it is current.
3. Survey the UNH collection: coverage, format, OCR quality, machine route,
   terms, robots, contact. **Write it up as `data/unh/SURVEY.md`** — what is
   there, what is legible, what is reachable and on what terms.
4. Take **one** journal volume — ideally a 1997 or 1998 House volume, because
   `journals/` already holds those years from the digital source and you can
   check your extraction against a record the site already has — and establish
   what can actually be got out of a page: roll calls, sponsors, amendments.
   Measure it against the known-good copy and state the number.
5. Report back to the person with the survey and that measurement, and a
   proposed order of work. Only then start fetching in volume.

The thing that would make this whole effort worthless is a parser tuned until
its output looked plausible. The thing that would make it valuable is ten years
of floor votes that nobody has been able to search before. Aim at the second,
and prove each step with a number.
