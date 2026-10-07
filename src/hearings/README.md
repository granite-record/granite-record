# src/hearings/

Which hearings and floor debates each bill had (`build_manifest`,
`build_floor_index`, and `build_proceedings`, which writes
`proceedings.csv`), which recording each one is in, the moment the chair
took the bill up (`segment_markers`), and the scorer and hand-timed truth
that check those moments (`probe_alignment`, `ground_truth`,
`verify_batch`). `calendar_meetings` reads the calendars: it is the
independent check, and the only source for a hearing the docket never
recorded.

**Nothing about timestamps goes on the site until
`python3 src/hearings/probe_alignment.py --truth --candidate candidate_segments.json`
has been run and the median has not regressed.** Add a phrase to
`tests/test_markers.py` only if it was actually spoken.

Asks nobody. Does not belong here: downloading captions or audio
(`fetch/youtube/`); `proceedings.py`, which every stage reads (`lib/`); the
bench, `review.py` (`checks/`).

The files moved here in stages 1 to 4 (`src/README.md`), the last of them
`probe_alignment`, which the laptop's evening job runs by name, in stage 4.
