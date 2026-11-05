#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.2
"""
A committee page's live stream at the top (the live layer's design, section
1.6): the hook the night writes into every committee and study-committee page,
which live.js fills while the committee's own stream is live.

    import live_hook
    history = live_hook.past()                      # once a run
    html = live_hook.place(html, code="H09", chamber="H", name="Finance",
                           history=history)

build_committees.py and build_study_committees.py call place() on each page's
HTML (workers/live/PATCHES.md 11): one call each, so a later conflict with the
files' owners is trivial.

THE HOOK IS OUTSIDE app.js'S ROOT. place() puts it directly before
<div id="results">, which app.js draws a committee into and draws again, so
no re-render reaches it, and a playing stream is never rebuilt.

ONE SOURCE OF TRUTH FOR WHICH STREAM IS WHOSE. stems() is what /live's
schedule.json calls a committee's `match` (build_live.match_of uses it), so
/live and the committee page cannot disagree: the card's name ("house
finance"), the committee's own ("finance"), and the title stems its past
recordings carried in collected/videos/ (build_live.past_stems). Nothing here
reads the calendar: a stream lights its committee's page whether or not the
meeting was on it.

THE WINDOW IS THE WORKER'S. The hook carries live_gen.WINDOW, the window the
Worker's clock.js imports through live.gen.js, and the page asks for streams
only inside it (weekdays 07:00 to 20:00 New Hampshire time), or while a
stream it is showing is still live.

Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import json

import live_gen as LG
import shell as S

CHAMBER_WORD = {"H": "House", "S": "Senate"}
ROOT = '<div id="results">'


def card_name(chamber, name):
    """build_pages.card_name's rule for a committee: the chamber said first,
    unless the name already starts with it."""
    word = CHAMBER_WORD.get(chamber)
    first = (name.split() or [""])[0]
    return f"{word} {name}" if word and first not in CHAMBER_WORD.values() else name


def stems(chamber, name, history):
    """A committee's stems, in order, each once: what a stream's title stem
    must equal, or begin with followed by a space, to be this committee's."""
    import build_manifest as BM
    out = [LG.stem(card_name(chamber, name)), LG.stem(name)]
    out += sorted((history or {}).get(BM.canon(name), ()))
    return [m for i, m in enumerate(out) if m and m not in out[:i]]


def past():
    """build_live.past_stems(): {canonical committee: {title stems}}."""
    import build_live as BL
    return BL.past_stems()


def longer(chamber, name, others):
    """The stems of the other committees whose names extend this one's.

    A stream's title matches a stem it equals or begins with, followed by a
    space. So the Senate's "Education" would take "Senate Education Finance
    (1/7/2027)" -- another committee's stream (the review of 30 October
    2026). The page refuses a title that matches one of these, the longer
    name winning. `others` is every committee the run writes a page for, as
    (chamber, name); one of the other chamber is not this page's concern."""
    mine = stems(chamber, name, {})
    out = []
    for c2, n2 in others or ():
        if (c2 or "", n2) == (chamber or "", name) or (chamber and c2 and c2 != chamber):
            continue
        for s2 in stems(c2, n2, {}):
            if s2 not in mine and any(s2.startswith(m + " ") for m in mine) and s2 not in out:
                out.append(s2)
    return sorted(out)


def hook(code, chamber, name, history, others=()):
    """The hook's HTML: hidden, empty, and filled by live.js."""
    attrs = {
        "data-committee": code, "data-chamber": chamber or "", "data-name": card_name(chamber, name),
        "data-match": json.dumps(stems(chamber, name, history), ensure_ascii=False),
        "data-not": json.dumps(longer(chamber, name, others), ensure_ascii=False),
        "data-window": json.dumps(LG.WINDOW, sort_keys=True),
    }
    a = "".join(f' {k}="{S.E(v)}"' for k, v in attrs.items())
    return f'<section id="live-now" class="lv lv-committee" hidden{a}></section>'


def place(html, code, chamber, name, history, others=()):
    """The page with the hook directly before app.js's root, and live.js and
    live.css loaded. Stops (ValueError) on a page with no root or a hook
    already in it: a page drawn twice must not carry two. `others`: every
    committee the run writes a page for, as (chamber, name) (longer())."""
    if html.count(ROOT) != 1:
        raise ValueError(f"committee {code}: the page has {html.count(ROOT)} {ROOT} where one is expected")
    if 'id="live-now"' in html:
        raise ValueError(f"committee {code}: the page already has a live hook")
    html = html.replace(ROOT, hook(code, chamber, name, history, others) + ROOT, 1)
    html = html.replace("</head>", '<link rel="stylesheet" href="/live.css">\n</head>', 1)
    return html.replace("</body>", '<script src="/live.js" defer></script>\n</body>', 1)
