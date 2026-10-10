#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-10.1
"""
Which motion a vote was on, read once from the record's own words, so that
both languages draw its head and its chip in the words the person approved
(src/pages/words/votes.json, the rule of 8 October 2026).

    import motions as M
    M.classify("Ought to Pass with Amendment 2026-0998h", "HB1681", "H")
    # {"mk": "otpa", "mf": {...}}            the key and what fills its words
    M.classify("House Concurs with Senate Amendment 2026-1709s", "HB1681", "H")
    # {"mk": "concur", "mf": {...}, "mrec": "House Concurs with Senate Amendment 2026-1709s"}

THE DECIDING HAPPENS HERE, ONCE (the component plan's C4): a bill's Votes tab
(app.js, drawing the record build_site_v2 writes) and a session day (built
here in Python) both draw components.vote_head and vote_chip with the key
this gives. A key is a row of votes.json's "motions" (otp, itl, table,
concur ...), or "" where the words are no motion the rows name: the head is
then the record's own words as they are, never a long docket code
reworded by guess.

"mrec" IS THE RECORD'S OWN WORDS, where they differ from the head by more
than case and an amendment number -- the person's rule: they "go on one
small line under it, after 'record'". "Laid on Table" under "Lay on the
Table (Set the bill aside)", "House Concurs with Senate Amendment
2026-1709s" under "Concur with the Amendment (Accept the other chamber's
changes)".

THE WORDS THE RECORD USES were read off every vote of the built site before
this was written (10 October 2026): 216 forms of a roll call's or a docket
vote's question across 2025-2026, from "Ought to Pass" (964) and
"Inexpedient to Legislate" (875) to "Lay HB1046 on Table" and "Reconsider
the following action taken by this Body: ...". The older terms' clerks wrote
"OTP/A", "ITL" and "LOT" for the same motions, and those are read too.

Standard library only; imports nothing of the project's.
"""

import re

# The order matters: a longer motion is asked before the shorter one inside it
# ("Nonconcur ... and Request a Committee of Conference" before "Nonconcur",
# "Remove from the Table" before "Lay on the Table", "Ought to Pass with
# Amendment" before "Ought to Pass").
_PATTERNS = (
    ("reconsider", r"\breconsider"),
    ("untable", r"\b(?:remove|take|taken)\s+(?:\w+\s+){0,3}?from\s+(?:the\s+)?table\b|\bRFT\b"),
    ("table_amendment", r"\b(?:lay|laid)\b.*\bamendment\b.*\btable\b|\btable\b.*\bamendment\b"),
    ("table", r"\b(?:lay|laid)\b.*\btable\b|^\s*(?:LOT|table)\b|\btabled?\s*$"),
    ("nonconcur_conference", r"\bnon-?\s*concur\w*\b.*\b(?:request|req\.?|ask)\w*\b.*"
                             r"\b(?:c\s*of\s*c|committee\s+of\s+conference|conference)\b"),
    ("nonconcur", r"\bnon-?\s*concur"),
    ("refuse_accede", r"\brefus\w*\s+to\s+accede"),
    ("accede", r"\baccede"),
    ("request_conference", r"\brequest\w*\s+(?:a\s+)?(?:c\s*of\s*c|committee\s+of\s+conference)"),
    ("concur", r"\bconcur"),
    ("conference_report", r"\bconference\s+(?:committee\s+)?report\b|\bc\s*of\s*c\s+report\b"),
    ("enrolled_amendment", r"\benrolled\s+bill\s+amendment\b"),
    ("committee_amendment", r"\bcommittee\s+amendment\b|\bCAM\b"),
    ("floor_amendment", r"\bfloor\s+amendment\b|\bFLAM\b"),
    ("otpa", r"\bought\s+to\s+pass\s*(?:with|w/)\s*am|\bOTP\s*/\s*A\b|\bOTPA\b"),
    ("ought_not_to_pass", r"\bought\s+not\s+to\s+pass\b"),
    ("otp", r"\bought\s+to\s+pass\b|\bOTP\b"),
    ("itl", r"\binexpedient\b|\bITL\b"),
    ("is", r"\binterim\s+study\b|\bRFIS\b|\bRFS\b"),
    ("postpone", r"\bindefinitely\s+postpone"),
    ("recommit", r"\brecommit"),
    ("vacate_referral", r"\bvacate"),
    ("rerefer", r"\bre-?\s*refer"),
    ("refer", r"\brefer(?:red)?\s+to\s+(?:the\s+)?(?:committee\s+on\s+)?"
              r"(?P<c>finance|ways\s+and\s+means|[A-Z][\w ,&]+?)\b(?:\s+committee)?\s*$"),
    ("override", r"\boverride\b|\bveto\b"),
    ("special_order", r"\bspecial\s+order"),
    ("suspend_rules", r"\bsuspen\w*\b.*\brules?\b"),
    ("previous_question", r"\bprevious\s+question\b"),
    ("limit_debate", r"\blimit\w*\s+(?:the\s+)?debate\b"),
    ("order_third_reading", r"\border\w*\s+(?:to\s+)?(?:a\s+)?third\s+reading\b"),
    ("final_passage", r"\bfinal\s+passage\b"),
    ("third_reading", r"\bthird\s+reading\b"),
    ("divide", r"^\s*divide\b|\bdivi(?:de|sion\s+of)\s+the\s+question\b"),
    ("withdraw", r"^\s*withdraw"),
    ("uphold_ruling", r"\bruling\s+of\s+the\s+chair\b|\bupheld\b|\buphold\b"
                      r"|\brule\s+of\s+(?:the\s+)?chair\b"
                      r"|\bdecision\s+of\s+the\s+(?:chair|president|speaker)\b"),
    ("member_continue", r"\bshall\s+the\s+member\s+continue\b"),
    ("print_debate", r"\bprint\w*\b.*\b(?:debate|remarks|journal)\b"),
    ("reprimand", r"\breprimand"),
    ("introduce_adopt", r"\bintroduc\w*\s+and\s+adopt"),
    ("introduce", r"\bintroduc"),
    ("amendment", r"\bamendment\b|^\s*AM\b"),
    ("adopt", r"^\s*adopt(?:ed|ion)?\b"),
)
_COMPILED = tuple((k, re.compile(p, re.I)) for k, p in _PATTERNS)

# A motion named only by a bare date, a fragment, nothing at all.
_UNNAMED = re.compile(r"^\s*(?:\d{1,2}/\d{1,2}/\d{2,4}|[\W\d_]*)\s*$")
# An amendment's number, and a mover in brackets, which the head drops and
# a comparison of the record's words with it ignores.
_AMD = re.compile(r"#?\s*\b\d{4}-\d{3,4}[a-z]?\b|\{\d{3,4}\}|#\s*\d{3,4}[a-z]?\b|\(\s*(?:Rep|Sen)s?\.[^)]*\)",
                  re.I)
_RESOLUTION = re.compile(r"^(?:HR|SR|HCR|SCR|HJR|SJR|CACR|SSHR|SSHCR)\d", re.I)
_SECOND_CMTE = {"finance": "Finance", "ways and means": "Ways and Means"}


def _plain(s):
    """Words for comparing a head with the record's: no amendment number, no
    mover, no case, no punctuation, one space."""
    s = _AMD.sub(" ", s or "")
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


def classify(text, bill="", body="", motion_words=None):
    """{"mk": key, "mf": {...}, "mrec": words?} for a vote on `text`, the
    motion's words as the record gives them, on `bill` ("HB1681") in `body`
    ("H" or "S"). `motion_words` is votes.json's "motions", for the record
    line's comparison; without it the record line is left out."""
    t = (text or "").strip()
    out = {"mk": "", "mf": {}}
    if _UNNAMED.match(t):
        out["mk"] = "unnamed"
        return out
    for key, rx in _COMPILED:
        m = rx.search(t)
        if not m:
            continue
        if key == "adopt" and not _RESOLUTION.match(bill or ""):
            continue
        if key == "table" and re.search(r"\breconsider|\bmotion\b", t, re.I):
            key = "table_motion"
        if key == "override":
            # The chamber the bill began in takes up a veto first, and its
            # vote does not make the bill law (votes.json rows 18).
            own = (bill or "")[:1].upper()
            key = "override_first" if body and own == body.upper()[:1] else "override_second"
        if key == "refer":
            c = (m.group("c") or "").strip()
            if not c or re.search(r"\binterim\b|\bcommittee\s*$", c, re.I):
                key = "rerefer"
            else:
                out["mf"] = {"Committee": _SECOND_CMTE.get(c.lower(), c.title())}
        if key in ("otp", "otpa"):
            second = re.search(r"\bref(?:er(?:red)?)?\.?\s+to\s+(?:the\s+)?(finance|ways\s+and\s+means)\b",
                               t, re.I)
            if second:
                key += "_finance"
                out["mf"] = {"Committee": _SECOND_CMTE.get(re.sub(r"\s+", " ", second.group(1).lower()),
                                                           second.group(1).title())}
        if key == "untable" or key.startswith("override"):
            out["mf"]["Chamber"] = "House" if (body or "").upper()[:1] == "H" else "Senate"
        out["mk"] = key
        break
    if out["mk"] and motion_words is not None:
        row = motion_words.get(out["mk"]) or {}
        head = row.get("motion") or ""
        for k, v in out["mf"].items():
            head = head.replace("{" + k + "}", v)
        if not head or _plain(head) != _plain(t):
            out["mrec"] = t
    return out
