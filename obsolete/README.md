# Superseded, and kept on purpose

Nothing here runs, nothing here is imported, and nothing in `build_all.py`
names any of it. It is kept because each of these answered a question, and the
answer is now built into something else — so the thing worth preserving is the
reasoning, not the code. A document can be superseded the same way a script
can, and one is here for the same reason.

This follows the convention `build_all.py` already uses for a superseded step:
kept for a case a newer step does not cover, and never run unasked.

They carry no `GRANITE_VERSION` stamp and are not listed in `versions.json`.
`inventory.py` and `preflight.py` therefore ignore them, which is the point:
a stamp on a file nobody runs is a stamp somebody has to keep true.

---

## `floor_anchors.py`

An experiment, and it succeeded. It asked whether a House roll call's
wall-clock time in `RollCallSummary.txt`, minus the moment the livestream
started, lands on the right point in the recording — no transcription, no
guessing from the calendar.

It does, to within three to seven seconds, and that is now the most
authoritative timestamp this project has. `CLAUDE.md` lists it first, above
anything read from a caption. The experiment is over because its finding is
production.

**It is House-only, and the experiment could not have shown that.** Across the
current `RollCallSummary.txt` and the 27 archived years in `rollcalls/`, 5,363
of the 5,577 House rows carry a clock and all 3,988 Senate rows are stamped
`12:00:00 AM`. So this method places no Senate floor debate at all, and the
answer to "why is there no timestamp on this Senate debate" is here rather than
in the caption code.

## `floor_debates.py`

An early attempt at finding where debate on a bill starts and ends in a floor
session, built on the Speaker's uniform language. `segment_markers.py`
replaced it and does both chambers and committee hearings as well, scored
against `ground_truth.csv` rather than against a reading of how sessions are
supposed to run.

Kept because its description of the shape of a floor session — motion, against,
for, alternating, then the vote — is an accurate account of the room, and is
where the floor patterns in `tests/test_markers.py` came from.

## `senate_check.py`

A one-off diagnostic: the manifest's overall counts are dominated by 5,550
House rows, so a Senate-only failure would be invisible in them. It printed
the Senate rows on their own.

Superseded by `preflight.py`, which checks both chambers as a matter of course
and fails rather than printing. Kept as the record of a real failure mode:
a number that looks healthy because the broken part is a small share of it.

## `LAUNCH-history-2026-09.md`

`LAUNCH.md` as it stood on 17 September, before it was trimmed for the public
release. For nine days it was a running log as well as a list — 2,144 lines of
dated decisions, measurements, bugs with their causes, and the evenings the
person settled things — and a stranger could not tell September's working notes
from the state of the site.

So the list stayed in `LAUNCH.md` and the log came here, the whole file rather
than an extract, which is why a few paragraphs appear in both. Nothing was
summarised, compressed or reworded: the reasoning is the part of it worth
keeping, and this project keeps reasoning.

**It is history, and none of it is a statement about the site today.** Every
count in it was true on the day it was typed. `LAUNCH.md` is the live list;
`STATE.md`, which is generated, beats them both.
