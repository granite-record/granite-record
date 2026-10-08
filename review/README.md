# review/

A person's checks of the site's own work: the measurements every timestamp
method is scored against. Nothing generates them, and `preflight.py` fails if
a `build_` or `fetch_` script writes here.

- `ground_truth.csv` -- 35 proceedings a person timed with a stopwatch by
  watching the recording, keyed on video, bill and kind. Read by
  `src/hearings/ground_truth.py`, `src/hearings/build_manifest.py` and
  `src/hearings/probe_alignment.py`.
- `checked.jsonl` -- the bench's judgments, one to a line. `src/checks/review.py`
  serves one sample at a time on the loopback address and appends what a
  person decides; a line is never rewritten.
- `.pool-*.json` -- the bench's sample pools, rebuilt by `src/checks/review.py --refresh`.
  Not tracked.

`python3 src/hearings/probe_alignment.py --truth` reads both files and gives
the number to watch, the candidate median.
