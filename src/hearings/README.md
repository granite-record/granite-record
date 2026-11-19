# src/hearings/

Which hearings and floor debates each bill had (`build_manifest`,
`build_floor_index`, and `build_proceedings`, which writes
`proceedings.csv`), which recording each one is in, the moment the chair
took the bill up (`segment_markers`), and the scorer and hand-timed truth
that check those moments (`probe_alignment`, `ground_truth`,
`verify_batch`). `gap_excerpts` writes the caption text around each
proceeding no boundary was found for into `logs/`, for reading; it quotes
captions, so it is never published. `calendar_meetings` reads the
calendars: it is the independent check, and the only source for a hearing
the docket never recorded.

Four more, which the rest lean on:

- `docket_parser`: the docket read into scheduled proceedings, the input
  `build_manifest` and `calendar_meetings` take;
- `caption_span`: whether a recording's captions reach its end
  (`caption_spans.json`), which `segment_markers`, the record builder and
  the night read before they trust a recording's captions;
- `floor_markers`: a floor session cut where the clerk reads each
  committee report, the first stated-boundary reader, whose patterns
  `segment_markers` took over;
- `apply_markers`: the older step that wrote stated boundaries into
  `segments.json`; `build_all.py` keeps it as a superseded step that runs
  only with `--with-superseded`, because `segment_markers` does its work
  and the record builder reads that directly.

**Nothing about timestamps goes on the site until
`python3 src/hearings/probe_alignment.py --truth --candidate candidate_segments.json`
has been run and the median has not regressed** on the proceedings both the
old and the new results place (`livestreams.worse`). Add a phrase to
`tests/test_markers.py` only if it was actually spoken.

Asks nobody. Does not belong here: downloading captions or audio
(`fetch/youtube/`); `proceedings.py`, which every stage reads (`lib/`); the
bench, `review.py` (`checks/`).

The files moved here in stages 1 to 4 (`src/README.md`), the last of them
`probe_alignment`, which the laptop's evening job ran by name, in stage 4.
The night's `src/ops/livestreams.py --markers` runs it by name now, as the
guard on what it reads.
