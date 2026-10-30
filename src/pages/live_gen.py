#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-26.4
"""
What the live Worker (workers/live/) shares with the rest of this repository,
written into workers/live/live.gen.js from where each value is kept.

    python3 src/pages/live_gen.py            # write it
    python3 src/pages/live_gen.py --check    # say whether it is current; write nothing

    CHANNELS       src/fetch/youtube/fetch_channel_index.py CHANNELS: the
                   House's and the Senate's YouTube channel, by chamber
    NIGHT_WINDOWS  refusal.py NIGHT_WINDOWS: the hours, in UTC, the night
                   asks the General Court, which the Worker keeps out of
                   (votes, a later branch: the YouTube half asks YouTube only)
    SESSION_TITLE  here: the beginning of a stream's title stem that makes it
                   a chamber's session stream, "House Session (01/07/2027)"
    SQL_LOGIN      src/fetch/gc_db/probe_db.py DATABASE, USER and PASSWORD:
                   the read-only login the General Court publishes for its
                   public SQL database. Published, so not a secret
                   (SECURITY.md says so). THE HOST IS DELIBERATELY NOT HERE:
                   workers/live/wrangler.toml names it under production
                   alone, so nothing a local run or a test imports can reach it.
    VOTE_WORD      src/fetch/gc_db/fetch_rollcalls_db.py VOTE_WORD: a ballot's
                   code in RollCallHistory, and the record's word for it
    BALLOT_CHAR    VOTE_WORD's codes as the live votes file's one character a
                   ballot (design section 2.5): Y Yea, N Nay, E excused, X not
                   excused, P presiding, and . for no vote recorded. A word
                   VOTE_WORD gains that BALLOT_CHARS below does not know stops
                   this: what a new code means on the page is a decision, not
                   a default.
    DOCKET_OUTCOME records/docket_abbrev.json: the General Court's own key
                   to its docket, the abbreviations whose words are an
                   outcome ("MA" Motion Adopted, "AF" Amendment Failed, ...),
                   which the Worker sets beside a docket tally line. It never
                   works out an outcome of its own (design section 2.4).
    BILL_NUMBER    src/parse/rollcall_parser.py BILL_NO and FLAGS: what makes
                   a roll call's bill field a bill (bill_number): spaces out,
                   upper case, the -FN/-L/-A/-LOCAL flags off, HCACR read as
                   CACR. "SUSPRULE", "RULE 1-2" and "HRULE64" name no bill,
                   and the live file's `bill` is then null, as the record's is.

THE PATTERN WRITTEN WITH ITS STEM. A title's stem is the title without its
date, in lower case, with "&" said as "and" and every run of other
characters made one space (stem() below): "Committee of Conference on SB 534
(05/22/2026" is "committee of conference on sb 534". The Worker's stem
(workers/live/youtube.js) is held to this one on every title in
collected/videos/ by preflight's _live_layer, and SESSION_TITLE is held to
match every title there that begins "House Session" or "Senate Session" and
no other: "Full Committee Work Session" is not a sitting.

READ, NOT IMPORTED. fetch_channel_index.py, probe_db.py and
fetch_rollcalls_db.py are fetchers and refusal.py the fetch lane's guard,
and the Worker needs literals from them; so each file is parsed (ast) and
the assignment read as a literal, and none is imported. A source that no longer assigns its literal where this reads it
stops this with its name rather than writing a file the Worker cannot use.

WHAT A CHANGE TAKES. Change the value where it is kept, run this, and commit
workers/live/live.gen.js with the change. preflight fails while the file
differs from what this would write, and names this command. It is the
workers/follow/site.gen.js pattern (follow_site.py), for the same reason: the
Worker is bundled by wrangler from what git holds, with no build step before
it, so it imports a plain module beside it. Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import ast
import json
import re

OUT = Path("workers/live/live.gen.js")
COMMAND = "python3 src/pages/live_gen.py"

CHANNEL_INDEX = Path("src/fetch/youtube/fetch_channel_index.py")
REFUSAL = Path("refusal.py")
PROBE_DB = Path("src/fetch/gc_db/probe_db.py")
ROLLCALLS_DB = Path("src/fetch/gc_db/fetch_rollcalls_db.py")
DOCKET_ABBREV = Path("records/docket_abbrev.json")
# Every file the written one is made from.
SOURCES = (CHANNEL_INDEX, REFUSAL, PROBE_DB, ROLLCALLS_DB, DOCKET_ABBREV)
# An abbreviation is an outcome when its word says one.
OUTCOME_WORD = re.compile(r"\b(?:Adopted|Failed|Lost)$")

# The record's words for a ballot, as the live file's one character each.
# "" and "No vote recorded" are VOTE_WORD's words for codes 0, 5 and 7.
BALLOT_CHARS = {"Yea": "Y", "Nay": "N", "Not Voting/Excused": "E",
                "Not Voting/Not Excused": "X", "Presiding": "P",
                "": ".", "No vote recorded": "."}

# The chambers by the letter the site and the Worker key them by.
CHAMBER = {"house": "H", "senate": "S"}

# The beginning of a session stream's stem, by chamber: 172 titles in the
# committed indexes on 26 October 2026, Organization Day's among them
# ("House Session (12/04/2024)", "Senate Session (12/04/24)"), and no other
# title begins this way.
SESSION_TITLE = {"H": r"^house session\b", "S": r"^senate session\b"}

# A title's date and everything after it: "(01/07/2027)", "(1/7/27",
# "(5/27/20 - morning session)", "(01/12/2026) (Full Stream)".
_DATE_TAIL = re.compile(r"\(\s*[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}.*$", re.S)
_WORD = re.compile(r"[a-z0-9]+")


class SourceError(ValueError):
    """A source no longer says a value where, or how, this reads it."""


def stem(title):
    """A stream title as comparable words: its date and what follows it
    dropped, lower case, "&" as "and", and any other run of characters one
    space. workers/live/youtube.js's stem() is this one, held to it on every
    committed title."""
    t = _DATE_TAIL.sub("", title or "").lower().replace("&", " and ")
    return " ".join(_WORD.findall(t))


def session_of(title):
    """'H' or 'S' when the title is that chamber's session stream, else None."""
    s = stem(title)
    for chamber, pattern in SESSION_TITLE.items():
        if re.search(pattern, s):
            return chamber
    return None


def _base(root):
    return Path(root) if root is not None else _paths.ROOT


def _literal(path, name):
    """The value of the module-level `name = <literal>` in `path`, read by
    parsing it."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as e:
        raise SourceError(f"{path.as_posix()} could not be read: {e}") from None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name
                                                for t in node.targets):
            try:
                return ast.literal_eval(node.value)
            except ValueError:
                raise SourceError(f"{path.as_posix()} no longer assigns {name} a literal") from None
    raise SourceError(f"{path.as_posix()} no longer assigns {name}")


def channels(root=None):
    raw = _literal(_base(root) / CHANNEL_INDEX, "CHANNELS")
    out = {}
    for name, letter in CHAMBER.items():
        entry = raw.get(name) if isinstance(raw, dict) else None
        cid = entry[0] if isinstance(entry, (tuple, list)) and entry else None
        if not (isinstance(cid, str) and re.fullmatch(r"UC[0-9A-Za-z_-]{22}", cid)):
            raise SourceError(f"{CHANNEL_INDEX.as_posix()} CHANNELS[{name!r}] is not a channel id "
                              f"as YouTube writes one (UC and 22 more): {entry!r}")
        out[letter] = cid
    return out


def night_windows(root=None):
    raw = _literal(_base(root) / REFUSAL, "NIGHT_WINDOWS")
    out = []
    for w in raw:
        try:
            wd, (sh, sm), (eh, em), _what = w
        except (TypeError, ValueError):
            raise SourceError(f"{REFUSAL.as_posix()} NIGHT_WINDOWS has an entry this cannot read: "
                              f"{w!r}") from None
        if (wd is not None and wd not in range(7)) or not all(
                isinstance(x, int) for x in (sh, sm, eh, em)):
            raise SourceError(f"{REFUSAL.as_posix()} NIGHT_WINDOWS has an entry this cannot read: "
                              f"{w!r}")
        out.append([wd, [sh, sm], [eh, em]])
    if not out:
        raise SourceError(f"{REFUSAL.as_posix()} NIGHT_WINDOWS is empty")
    return out


def assigned(path, names, root=None):
    """{name: value} of the top-level `NAME = <literal>` assignments in a
    Python file, read without importing it."""
    p = _base(root) / path
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as e:
        raise SourceError(f"{path.as_posix()} will not read ({e})")
    got = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            try:
                got[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                raise SourceError(f"{path.as_posix()}'s {node.targets[0].id} is not a plain value")
    missing = [n for n in names if n not in got]
    if missing:
        raise SourceError(f"{path.as_posix()} no longer assigns {', '.join(missing)} at the top level")
    return got


def published_login(root=None):
    """probe_db.py's DATABASE, USER and PASSWORD, read as text."""
    v = assigned(PROBE_DB, ("DATABASE", "USER", "PASSWORD"), root)
    if not all(isinstance(x, str) and x for x in v.values()):
        raise SourceError(f"{PROBE_DB.as_posix()}'s DATABASE, USER or PASSWORD is not a word")
    return {"database": v["DATABASE"], "user": v["USER"], "password": v["PASSWORD"]}


def docket_outcomes(root=None):
    try:
        key = json.loads((_base(root) / DOCKET_ABBREV).read_text(encoding="utf-8"))["abbrev"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise SourceError(f"{DOCKET_ABBREV.as_posix()} has no abbrev key this can read ({e})") from None
    out = {k: v for k, v in sorted(key.items()) if isinstance(v, str) and OUTCOME_WORD.search(v)
           and re.fullmatch(r"[A-Z]{2,4}", k)}
    if not {"MA", "MF", "AA", "AF"} <= set(out):
        raise SourceError(f"{DOCKET_ABBREV.as_posix()} no longer gives MA, MF, AA and AF as outcomes")
    return out


def bill_number_rule():
    """rollcall_parser's BILL_NO and FLAGS as RegExp sources. A parser, so
    imported (it asks nobody anything). Its HCACR rule is code, which the
    Worker's billNumber (merge.js) repeats; this stops if it changes."""
    import inspect
    import rollcall_parser as RP
    if not RP.BILL_NO.flags & re.I:
        raise SourceError("rollcall_parser.BILL_NO is no longer case-blind; merge.js's billNumber reads it so")
    src = inspect.getsource(RP.bill_number)
    if 're.sub(r"^HCACR(?=\\d)", "CACR", b)' not in src or "FLAGS.sub" not in src:
        raise SourceError("rollcall_parser.bill_number has changed: bring merge.js's billNumber along, then this")
    return {"pattern": RP.BILL_NO.pattern, "flags_off": RP.FLAGS.pattern}


def values(root=None):
    """{name: (where it comes from, value)}, in the order they are written."""
    words = assigned(ROLLCALLS_DB, ("VOTE_WORD",), root)["VOTE_WORD"]
    if not isinstance(words, dict) or not words or \
            not all(isinstance(k, str) and k.isdigit() and isinstance(w, str) for k, w in words.items()):
        raise SourceError(f"{ROLLCALLS_DB.as_posix()}'s VOTE_WORD is not {{code: word}}")
    unknown = sorted({w for w in words.values() if w not in BALLOT_CHARS})
    if unknown:
        raise SourceError(f"VOTE_WORD has a word the live file has no character for: {unknown}; "
                          f"add it to live_gen.BALLOT_CHARS once its meaning on the page is decided")
    codes = sorted(words.items(), key=lambda kv: int(kv[0]))
    return {
        "CHANNELS": (f"{CHANNEL_INDEX.as_posix()} CHANNELS, by chamber: each one's YouTube "
                     "channel; its uploads playlist is the id with UC made UU",
                     channels(root)),
        "NIGHT_WINDOWS": (f"{REFUSAL.as_posix()} NIGHT_WINDOWS, in UTC: [weekday (0 is Monday) "
                          "or null for every day, [start hour, minute], [end hour, minute]]",
                          night_windows(root)),
        "SESSION_TITLE": ("src/pages/live_gen.py SESSION_TITLE: the beginning of a session "
                          "stream's title stem, by chamber (a RegExp source)",
                          SESSION_TITLE),
        "SQL_LOGIN": (f"{PROBE_DB.as_posix()}: DATABASE, USER and PASSWORD, the read-only login the "
                      f"General Court publishes. The host is not here: wrangler.toml names it under "
                      f"production alone", published_login(root)),
        "VOTE_WORD": (f"{ROLLCALLS_DB.as_posix()}: VOTE_WORD, a ballot's code and the record's word",
                      dict(codes)),
        "BALLOT_CHAR": ("VOTE_WORD's codes as the live file's one character: Y Yea, N Nay, "
                        "E excused, X not excused, P presiding, . no vote recorded "
                        "(src/pages/live_gen.py BALLOT_CHARS)",
                        {k: BALLOT_CHARS[w] for k, w in codes}),
        "DOCKET_OUTCOME": (f"{DOCKET_ABBREV.as_posix()}: the docket's abbreviations whose words are "
                           "an outcome, as the General Court's key writes them", docket_outcomes(root)),
        "BILL_NUMBER": ("src/parse/rollcall_parser.py BILL_NO (case-blind) and FLAGS: a roll call's bill "
                        "field read as a bill, as bill_number reads it", bill_number_rule()),
    }


def render(root=None):
    """The text of workers/live/live.gen.js, from the sources as they stand."""
    lines = [
        "// WRITTEN BY src/pages/live_gen.py FROM THE REPOSITORY'S OWN FILES. Do not edit it:",
        "// change the value where the comment above it says it comes from, then run",
        f"//     {COMMAND}",
        "// and commit this file with the change. preflight fails while it differs from",
        "// what that command would write.",
        "",
    ]
    for name, (source, value) in values(root).items():
        lines += [f"// {source}.", f"export const {name} = {json.dumps(value, ensure_ascii=False)};"]
    return "\n".join(lines) + "\n"


def current(root=None):
    """(whether the committed file is what render() writes, the reason if not)."""
    path = _base(root) / OUT
    if not path.is_file():
        return False, f"{OUT.as_posix()} is not there"
    # read_text reads a checkout's CRLF as LF: autocrlf is on for the laptop.
    if path.read_text(encoding="utf-8") == render(root):
        return True, ""
    return False, f"{OUT.as_posix()} is not what its sources say now"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--check", action="store_true", help="say whether the file is current; write nothing")
    a = ap.parse_args()
    try:
        text = render()
    except SourceError as e:
        print(f"live_gen: {e}", file=sys.stderr)
        return 2
    path = _paths.ROOT / OUT
    if a.check:
        ok, why = current()
        print(f"{OUT.as_posix()} is current" if ok else f"{why}: run {COMMAND}")
        return 0 if ok else 1
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        print(f"{OUT.as_posix()} is current; nothing written")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.as_posix()}: {', '.join(values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
