#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-14.4
"""
A docket line in plain words, for a reader who does not know the clerk's
shorthand -- the email digest and the Documents tab (the person's choices of
14 October 2026). The clerk's own line is never replaced: it stays beside
these words as the citation, and where a line is of a kind this does not
know, the answer is "" and the reader is shown the line as written.

    import plain_action as PA
    PA.plain("Ought to Pass: MA, VV; OT3rdg; 02/19/2026")
    # "Bill passed, on a voice vote"
    PA.plain("Majority Committee Report: Ought to Pass with Amendment # 2025-2969h 10/01/2025 (Vote 12-3; RC)")
    # "Majority committee report: pass the bill with changes (amendment 2025-2969h), 12–3"
    PA.plain("Executive Session: 06/15/2026 10:30 am GP 159")
    # "Executive session, 10:30 a.m., Granite Place 159"

THE WORDS ARE ALREADY APPROVED. A floor vote's are votes.json's -- the head
the Votes tab gives the same motion ("Bill Passed with Changes", "Sent to
Interim Study"), in sentence case -- read through motions.classify, the one
place the record's motions are recognised. A line's kind is
narrative.classify's, the reader the stories are written from. Nothing here
decides what a motion is.

NO DATE IN THE WORDS. Every place that shows these shows the line's date
beside them, and the clerk wrote it in a form ("06/15/2026") the site does not
use, so it is dropped here rather than said twice.

Standard library only, beside narrative.py and motions.py.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import json
import re

import motions as M
import narrative as N

VOTES = json.loads((_paths.ROOT / "src/pages/words/votes.json").read_text(encoding="utf-8"))

# The buildings the clerk abbreviates, as the calendar and the site name them.
BUILDINGS = {"LOB": "Legislative Office Building", "SH": "State House", "GP": "Granite Place"}

_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", re.I)
_ROOM = re.compile(r"\bRoom\s+([\w][\w .\-]*?)\s*,\s*([A-Z]{2,3})\b", re.I)
_BLDG = re.compile(r"\b(LOB|SH|GP)\s+([0-9][0-9A-Za-z\-]*)\b")
_TALLY = re.compile(r"\b(RC|DV|VV)\b\s*=?\s*(?:(\d+)\s*Y?\s*-\s*(\d+)\s*N?)?", re.I)
_VOTE = re.compile(r"\bVote\s+(\d+)\s*-\s*(\d+)", re.I)
_AMD = re.compile(r"#\s*((?:\d{4}-)?\d+[a-z]*)", re.I)
_CHAPTER = re.compile(r"\bChapter\s*(\d+)", re.I)


def _clock(m):
    h, mi, ap = int(m.group(1)), m.group(2), m.group(3).lower()
    return f"{h}:{mi} {ap}.m."


def _where(raw):
    """", 10:30 a.m., Granite Place 159" from what follows a meeting's date."""
    bits = []
    t = _TIME.search(raw)
    if t:
        bits.append(_clock(t))
    r = _ROOM.search(raw)
    if r:
        bits.append(f"Room {r.group(1).strip()}, {BUILDINGS.get(r.group(2).upper(), r.group(2))}")
    else:
        b = _BLDG.search(raw)
        if b:
            bits.append(f"{BUILDINGS[b.group(1)]} {b.group(2)}")
    return "".join(", " + x for x in bits)


def _how(raw):
    """", 193–143 on a roll call" / ", on a voice vote" / "" from a vote's codes."""
    m = _TALLY.search(raw)
    if not m:
        return ""
    kind = m.group(1).upper()
    if kind == "VV":
        return ", on a voice vote"
    words = {"RC": "on a roll call", "DV": "on a division vote"}[kind]
    if m.group(2) and m.group(3):
        return f", {m.group(2)}–{m.group(3)} {words}"
    return f", {words}"


def _sentence(s):
    s = s.replace("{Bill} ", "Bill ").replace("{Bill}", "Bill").strip()
    return s[:1].upper() + s[1:].lower() if s else s


def _motion_words(raw, carried, bill="", body=""):
    """The approved head for a floor motion's outcome, or "" for one the
    words do not name (then the caller falls back to the clerk's line)."""
    got = M.classify(raw, bill, body)
    row = VOTES["motions"].get(got.get("mk") or "")
    if not row:
        return ""
    said = row.get("passed" if carried else "failed") or ""
    if said and "{" not in said.replace("{Bill}", ""):
        return _sentence(said)
    gloss = (row.get("gloss") or "").strip()
    if not gloss or "{" in gloss:
        return ""
    return f"Motion to {gloss[:1].lower() + gloss[1:]} {'carried' if carried else 'failed'}"


# A committee's recommendation, in the gloss of the motion it recommends --
# but interim study by its name, the words a reader meets on every page.
def _rec(rec):
    got = M.classify(rec or "")
    if got.get("mk") == "is":
        return "send the bill to interim study"
    row = VOTES["motions"].get(got.get("mk") or "")
    gloss = (row or {}).get("gloss") or ""
    return gloss[:1].lower() + gloss[1:] if gloss and "{" not in gloss else ""


# THE LINES narrative.classify KEEPS AS "other" or reads too coarsely for a
# sentence, read here first (14 October 2026, from 865 docket lines of 89
# bills of 2025-2026, of which these were most of the 13% left as written).
# Each answers (match) -> words, or "" to fall through.
_AMEND = re.compile(
    r"^(?:(?P<who>(?:Sen|Rep)\.\s+[\w.' -]+?)\s+)?(?P<what>Committee Amendment|Floor Amendment|FLAM|"
    r"Enrolled Bill Amendment|Amendment)\s*#?\s*(?P<num>(?:\d{4}-)?\d+[a-z]*)"
    r"(?:\s*\(NT\))?(?:\s*\((?P<by>(?:Rep|Sen)s?\.[^)]*)\))?[\s,:;]*"
    # The Senate's clerk puts a roll call before the outcome: "Sen. Rosenwald
    # Floor Amendment # 2025-2660s, RC 8Y-16N, AF" (15 October 2026); _how
    # reads the count from the whole line either way.
    r"(?:(?:RC|DV)\s*\d+\s*Y?\s*-\s*\d+\s*N?[\s,:;]*)?"
    r"(?P<out>AA|AF|Adopted|Failed)\b", re.I)
_SIMPLE = [
    (re.compile(r"^Died on (?:the )?Table\b", re.I), lambda m, r: "Died on the table when the session ended"),
    # The history's words for the same row (narrative.SENATE_RULE_KILL_RE),
    # and the status chip's, "Died on the table" (15 October 2026).
    (re.compile(r"^Inexpedient\s+to\s+Legislate,?\s*(?:\d{4}\s+Adjournment,?\s*)?Senate\s+Rule\s+3-23\b",
                re.I),
     lambda m, r: "Died on the table under Senate Rule 3-23"),
    (re.compile(r"^Referred to (?!Interim)(?P<c>[A-Z][\w ,&]+?)\s+\d{1,2}/\d{1,2}/\d{4}", re.I),
     lambda m, r: f"Referred to {m.group('c')}"),
    (re.compile(r"^Referral Waived by Committee Chair", re.I),
     lambda m, r: "Its second committee's chair waived the referral"),
    (re.compile(r"Removed from (?:the )?Consent", re.I),
     lambda m, r: "Removed from the consent calendar, to be debated"),
    # The Senate's clerk writes the same meeting the other way round.
    (re.compile(r"^(?:Committee of Conference|Conference Committee) Meeting\s*:", re.I),
     lambda m, r: "Committee of conference meeting" + _where(r)),
    # 15 OCTOBER 2026, from the 1,066 lines of the session's docket still left
    # as written: the kinds below say what lines already said here say, in the
    # same words. The Senate's own forms of a hearing, a conferee change and a
    # resolution's adoption; and a report that recommends nothing.
    (re.compile(r"^Hearing\s*:\s*\d{1,2}/\d{1,2}/\d{4}", re.I),
     lambda m, r: "Public hearing" + _where(r)),
    (re.compile(r"^Introduced and Adopted\b", re.I),
     lambda m, r: "Introduced and adopted" + _how(r)),
    # A veto vote, in the House's form and the Senate's ("Notwithstanding the
    # Governor's Veto, Shall SB 213 Become Law: RC 0Y-24N, Veto Sustained"), in
    # votes.json's words for it -- "Veto Sustained", "Overridden in the
    # {Chamber}" -- without the chamber, which the line does not give; and
    # never "became law", which one chamber's override does not make it.
    (re.compile(r"^(?:Notwithstanding the Governor's Veto\b.*?\b)?Veto\s+(?P<o>Sustained|Overridden)\b",
                re.I),
     lambda m, r: ("Veto sustained" if m.group("o").lower() == "sustained" else "Veto overridden")
     + _how(r)),
    (re.compile(r"^(?:(?P<side>Majority|Minority)\s+)?Committee Report\s*:\s*Without Recommendation",
                re.I),
     lambda m, r: (f"{m.group('side')} committee report" if m.group("side") else "Committee report")
     + ": makes no recommendation"
     + (lambda v: f", {v.group(1)}–{v.group(2)}" if v else "")(_VOTE.search(r))),
    (re.compile(r"^Conference Committee Report\b.*?\b(?P<o>Adopted|Failed|Rejected)\b", re.I),
     lambda m, r: f"Conference committee report {m.group('o').lower()}" + _how(r)),
    (re.compile(r"^Conference Committee Report\b.*?\bNot (?:Signed Off|Filed)\b", re.I),
     lambda m, r: "The committee of conference filed no agreed report"),
    (re.compile(r"^Conference Committee Report\b.*?\bFiled\b", re.I),
     lambda m, r: "Conference committee report filed"),
    (re.compile(r"^Speaker Appoints\s*:\s*(?P<w>.+?)\s*(?:\d{1,2}/\d{1,2}/\d{4}|\(|$)", re.I),
     lambda m, r: f"The Speaker named the House conferees: {m.group('w').strip(' ;,')}"),
    (re.compile(r"^President Appoints\s*:\s*(?P<w>.+?)\s*(?:;|\(|\d{1,2}/\d{1,2}/\d{4}|$)", re.I),
     lambda m, r: f"The Senate President named the Senate conferees: {m.group('w').strip(' ;,')}"),
    (re.compile(r"^Conferee Change\s*[:;]\s*(?P<a>.+?)\s+Replaces\s+(?P<b>.+?)\s*"
                r"(?:;|\s\d{1,2}/\d{1,2}/\d{4}|$)", re.I),
     lambda m, r: f"Conferee changed: {m.group('a')} replaces {m.group('b')}"),
    (re.compile(r"^Interim Study Report\s*:\s*(?:(?P<no>Not )?Recommended for Future Legislation|"
                r"(?P<none>Without Recommendation))", re.I),
     lambda m, r: ("Interim study report: makes no recommendation" if m.group("none") else
                   "Interim study report: does not recommend future legislation" if m.group("no")
                   else "Interim study report: recommends future legislation")
     + (lambda v: f", {v.group(1)}\u2013{v.group(2)}" if v else "")(_VOTE.search(r))),
    (re.compile(r"^(?P<who>(?:Sen|Rep)\.\s+[\w.' -]+?)\s+Moved\s+(?P<m>.+?)\s*;", re.I),
     lambda m, r: (lambda w: f"{m.group('who')} moved to {w[:1].lower() + w[1:]}" if w else "")(_rec(m.group("m")))),
]


def _amendment(raw):
    m = _AMEND.search(raw)
    if not m:
        return ""
    kind = {"committee amendment": "Committee amendment", "floor amendment": "Floor amendment",
            "flam": "Floor amendment", "enrolled bill amendment": "Enrolled bill amendment"}.get(
        m.group("what").lower(), "Amendment")
    who = m.group("who") or m.group("by")
    out = "adopted" if m.group("out").upper() in ("AA", "ADOPTED") else "failed"
    return f"{kind} {m.group('num')}" + (f" ({who.strip()})" if who else "") + f" {out}" + _how(raw)


def plain(raw, bill="", body=""):
    """The line in plain words, or "" where it is of a kind not known here."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.upper().startswith("==CANCELLED=="):
        return ""
    words = _amendment(raw)
    if words:
        return words
    for pat, say in _SIMPLE:
        m = pat.search(raw)
        if m:
            words = say(m, raw)
            if words:
                return words
    d = N.classify(raw)
    k = d.get("_type")
    if k == "introduced":
        return f"Introduced and referred to {d['committee'].strip()}"
    if k in ("hearing", "nongermane_hearing"):
        return "Public hearing" + _where(raw)
    if k == "exec":
        return "Executive session" + _where(raw)
    if k == "worksession":
        kind = re.sub(r"\s+", " ", d.get("kind") or "Work Session").strip()
        return kind[:1].upper() + kind[1:].lower() + _where(raw)
    if k == "report":
        side = (d.get("side") or "").lower()
        side = "Majority " if side.startswith("major") else "Minority " if side.startswith("minor") else ""
        what = _rec(d.get("rec"))
        if not what:
            return ""
        amd = _AMD.search(raw)
        v = _VOTE.search(raw)
        out = f"{side}committee report: {what}"
        out = out[:1].upper() + out[1:]
        if amd and "amend" in (d.get("rec") or "").lower():
            out += f" (amendment {amd.group(1)})"
        if v:
            out += f", {v.group(1)}–{v.group(2)}"
        if re.search(r"[;,(]\s*CC\b", raw):
            out += ", for the consent calendar"
        return out
    if k == "floor":
        carried = (d.get("motion") or "").upper() == "MA"
        head = _motion_words(d.get("action") or raw, carried, bill, body)
        return head + _how(raw) if head else ""
    if k == "governor":
        w = (d.get("what") or "").lower()
        if w.startswith("signed"):
            ch = _CHAPTER.search(raw)
            return "Signed by the Governor" + (f", chapter {int(ch.group(1))}" if ch else "")
        if w.startswith("vetoed"):
            return "Vetoed by the Governor"
        if w.startswith("sent"):
            return "Sent to the Governor"
        return ""
    if k == "enrolled":
        return "Enrolled: the final text checked before it goes to the Governor"
    if k == "retained":
        return "Retained in committee"
    return ""


if __name__ == "__main__":
    for line in sys.argv[1:] or sys.stdin.read().splitlines():
        print(f"{line}\n  -> {plain(line) or '(as written)'}")
