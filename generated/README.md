# generated/

What this project computes from its own record ahead of time, and git keeps
because it takes a run a person starts to make. Each is rewritten whole by
the run named beside it, never edited by hand.

- `careers.json` -- one record per person across every term they served,
  joining the General Court's employee numbers into people
  (`src/parse/build_careers.py`).
- `places.json` -- one list of New Hampshire's places, reconciling the five
  that count them differently (`src/towns/build_places.py`).
- `topic_model.json` -- the settings `src/parse/topic_model.py` runs with,
  the ones that won its scored comparison of 16 September 2026; a new
  comparison writes new ones.
- `alignment_score.json` -- the timestamp methods scored against the
  hand-timed truth, which the About page states
  (`python3 src/hearings/probe_alignment.py --truth --score-out`).

What the nightly build writes is not here. It is rebuilt on every run and
not tracked: `site/`, `data/` and the JSON beside them at the root, which
`.gitignore` names.
