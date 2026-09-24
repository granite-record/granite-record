#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-17.1
"""
The figures about.html states, counted rather than typed.

    import about_figures
    text = about_figures.fill(ABOUT, about_figures.figures(site="site"))

WHY THIS EXISTS

about.html told a reader how much of the record is timed, how well the timing
does, and against what it was checked, in eight figures somebody had typed into
the prose. On 17 September seven of the eight were wrong, and not slightly:
the page said 10,810 proceedings where the site carries 101,290, and 1,068 with
no recording where the true figure is 78,344. None of them had been wrong when
they were written. The site grew from one term to nineteen underneath them, and
a typed number does not grow with it.

That is worse than an ordinary stale number, because these particular figures
are the site's account of its own accuracy. A reader deciding how much to trust
a timestamp was being handed arithmetic from a smaller site.

WHERE EACH FIGURE COMES FROM

  site/station_census.json   written by build_site_v2.py in the same loop that
                             builds the stations, so it cannot disagree with
                             the pages -- it is the same list, counted.
  alignment_score.json       written by `probe_alignment.py --truth
                             --score-out`, which is the gate every timestamp
                             method has to pass before it ships. The accuracy
                             the page states is therefore the accuracy the gate
                             last measured, and the page says when.

NEITHER FILE IS INVENTED IF IT IS ABSENT. `figures()` returns only what it
could count, and `fill()` raises rather than publishing a sentence with a hole
in it -- the same rule build_civics.py applies to the Learn pages, and for the
same reason: a paragraph that silently loses its numbers still reads like a
statement of fact.
"""

import json
import re
from pathlib import Path

# The date the General Court's YouTube channels begin: the House's first
# upload is of 14 May 2020 and the Senate's of 29 May, as
# channel_index_full.json records them. build_site_v2 imports this rather than
# repeating it, and splits "no recording to link: the sitting is older than
# the channels" from "no recording matched" on it; the About page and app.js
# say the same boundary in words. It is where the recordings this site links
# begin, not a claim that nothing was ever streamed before it -- the House
# Calendars of 2013-2019 announce live streams, and none of those recordings
# is on either channel.
STREAM_START = "2020-05-14"
STREAM_START_WORDS = "May 2020"


def _load(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return default


def _n(v):
    """12345 -> '12,345'."""
    return f"{int(v):,}"


def _mmss(sec):
    """A duration as the page says it: '1 second', '14 minutes'.

    Not the gate's own 0m 01s. That form belongs in a terminal beside three
    other medians; a sentence needs the words.
    """
    sec = float(sec or 0)
    if sec < 1.5:
        return "1 second"
    if sec < 90:
        return f"{round(sec)} seconds"
    m = round(sec / 60)
    return f"{m} minutes" if m != 1 else "1 minute"


def figures(site="site", root="."):
    """Every [[name]] about.html can use, or as many as could be counted."""
    f = {}

    census = _load(Path(site) / "station_census.json")
    if census:
        by = census.get("by_state") or {}
        total = int(census.get("total") or 0)
        placed = int(census.get("placed") or 0)
        rec_only = int(census.get("recording_only") or 0)
        norec = int(census.get("no_recording") or 0)
        consent = int(census.get("consent") or 0)
        f.update({
            "stations": _n(total),
            "station_bills": _n(census.get("bills") or 0),
            "placed": _n(placed),
            "recording_only": _n(rec_only),
            "no_recording": _n(norec),
            # The consent calendar is its own answer and not a failure to
            # find one: the bill was adopted in a block, never read out and
            # never debated, so there is no moment in the recording to open
            # at. Counted apart from the ones the site could not place.
            "consent": _n(consent),
            # Everything a recording was offered for: the two groups that
            # have one at all.
            "recorded": _n(placed + rec_only),
            # Of the recorded ones, the share that lands on the moment. A
            # percentage of the WHOLE record would be a different and much
            # less useful claim -- most of the record is older than streaming
            # and no method can place it.
            "placed_pct": (f"{100 * placed / (placed + rec_only):.0f}%"
                           if (placed + rec_only) else "&mdash;"),
            "prestream": _n(by.get("prestream") or 0),
            "prestream_pct": (f"{100 * (by.get('prestream') or 0) / total:.0f}%"
                              if total else "&mdash;"),
            # The two reasons a streamed-era proceeding has no recording on it,
            # which are different claims and are drawn differently: nothing was
            # matched at all, against "the committee was recorded that day and
            # which of its recordings this is has not been established".
            "unmatched": _n(by.get("novideo") or 0),
            "candidates": _n(by.get("candidates") or 0),
            "stream_start": STREAM_START_WORDS,
        })

    sc = _load(Path(root) / "alignment_score.json")
    cand = (sc or {}).get("candidate") or {}
    sched = (sc or {}).get("schedule") or {}
    if cand:
        within_min = int((cand.get("within") or {}).get("60") or 0)
        f.update({
            "marked": _n(cand.get("marked") or 0),
            "marked_placed": _n(cand.get("placed") or 0),
            "marked_unplaced": _n(cand.get("unplaced") or 0),
            "marked_videos": _n(cand.get("videos") or 0),
            "median": _mmss(cand.get("median")),
            "worst": _mmss(cand.get("worst")),
            "within_minute": _n(within_min),
            "over_ten": _n(cand.get("over_ten_minutes") or 0),
            "measured": (sc or {}).get("measured") or "",
        })
    if sched:
        f["schedule_median"] = _mmss(sched.get("median"))
    return f


def fill(text, figs):
    """[[name]] -> its figure, or stop the build.

    build_civics.fill does this for the Learn pages and raises on a name it
    cannot count. The About page needs the same guard for a stronger reason:
    its figures are claims about how far to trust the rest of the site, and a
    sentence that lost one would still read as a statement of fact.
    """
    want = set(re.findall(r"\[\[(\w+)\]\]", text or ""))
    missing = sorted(want - set(figs))
    if missing:
        raise SystemExit(
            "about.html names figures nothing counted: " + ", ".join(missing)
            + "\n  site/station_census.json comes from build_site_v2.py "
              "(run it first),\n  alignment_score.json from "
              "`python3 probe_alignment.py --truth "
              "--candidate candidate_segments.json --score-out`.")
    return re.sub(r"\[\[(\w+)\]\]", lambda m: str(figs[m.group(1)]), text or "")


if __name__ == "__main__":
    got = figures()
    for k in sorted(got):
        print(f"  {k:<18} {got[k]}")
    print(f"\n{len(got)} figures counted")
