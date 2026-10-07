# src/fetch/youtube/

The channel index (`fetch_channel_index`, which `livestreams.py` at the
root imports every night) and the by-hand caption and audio tools. YouTube
refuses GitHub's machines and has refused this laptop too, and the evening
caption job needs the laptop not to be refused (`livestreams.py` keeps the
record in `archive/youtube.refused.json`). So a long run here is a
decision, not a routine.

Does not belong here: reading captions already in `work/` (`hearings/`).
`livestreams.py` stays at the root, because the nightly workflow tests for
it by that path.

The scripts move here in stages 1 and 4 (`src/README.md`); until a script's
stage, it is still at the repository root.
