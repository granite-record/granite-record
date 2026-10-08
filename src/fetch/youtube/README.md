# src/fetch/youtube/

The channel index (`fetch_channel_index`, which `src/ops/livestreams.py`
imports every night, and which writes into `collected/videos/`) and the
by-hand caption and audio tools. YouTube
refuses GitHub's machines and has refused this laptop too, and the evening
caption job needs the laptop not to be refused (`livestreams.py` keeps the
record in `archive/youtube.refused.json`). So a long run here is a
decision, not a routine.

Does not belong here: reading captions already in `work/` (`hearings/`).
`livestreams.py` is in `src/ops/`, where the nightly workflow runs it and
tests for it by that path, and preflight lets it ask YouTube from there.

The by-hand tools moved here in stage 1 (`src/README.md`), and
`fetch_channel_index`, a `build_all` network step, in stage 3.
