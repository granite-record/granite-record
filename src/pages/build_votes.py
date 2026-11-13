#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.4
"""
Every roll call since 1999, a file a term, for the votes search to read.

    python3 src/pages/build_votes.py --site site

WHAT IT WRITES (the data stage of reports/votes-search-design-2026-11.md; the
/votes page, app.js's votes block, reads it, and build_votes_page.py writes
the page):

    votes/index.json             {"from", "terms" (newest first), "close"
                                 {"H", "S"}: the bars below, "counts": {term:
                                 {"H", "S"}}}: what the page reads first
    votes/<term>.json           {"term", "rolls": [row, ...]}: one row a roll
                                 call, oldest first, both chambers, a vote on
                                 no bill included as "Procedural"
    votes/ballots-<term>.json    {"term", "legend", "chambers": {"H"|"S":
                                 {"m": [member id, ...], "r": {roll call:
                                 "YNEX.."}}}}: one character a member of that
                                 chamber's list, in the order of "m"

A term is a file so that the page loads only the terms in view and a term
added later (an earlier one, once older roll calls are found) is a file added,
nothing rewritten. The roll call's id is the one rollcalls_index.json keys
it by ("2026-H-311").

A ROW: id, d (day), c (H or S), b (the bill, "" on none), q (the question in
plain words where the parser made them, else the record's own), mk (the
motion's key, as motions.classify gives it, "" where the words are none of
them), k (the kind of question: Committee report, Amendment, Conference
report, Veto override, Passage, Motion on a bill, Procedural, Other), p (1 if
it passed), y and n (the COUNTED yeas and nays: the members' ballots, which
rollcalls.json already carries as its headline), e (excused), a (not
excused), pd (presiding, where any), nr (no vote recorded, where any);
ys and ns where the clerk's summary STATED another tally than the ballots
count (14 roll calls: shown, never hidden; the site shows the counted one,
the owner's rule of 16 September 2026); f and cl (below); nd (the yeas the
question needed, where the record names more than a majority); oc (1 where
the record's outcome and the count disagree); pc ([Democratic yeas, nays,
Republican yeas, nays], plain figures and nothing said of them); w (what a
vote on no bill was about, in the Journal's words, vote_passage); nb (1 where
no member's ballot is on file for it).

A CLOSE VOTE (the owner, 12 November 2026): 5 or fewer voters in the House,
2 or fewer in the Senate (CLOSE_HOUSE, CLOSE_SENATE), who would have had to
switch to change the outcome. `f` is that number, worked out with the
rule the elections' ballot cards use (build_elections.flip_majority and
flip_two_thirds: a voter who changes sides moves one vote and leaves the
total where it was) against the roll call's own threshold: a majority where
the record names none (a tie is not a majority), two thirds of those voting
where the record says so, and a fixed number of yeas where it says three
fifths of the members in office (the denominator is the members, not the
voters, so a switch leaves the number to reach where it was). `cl` is 1
where f is within the chamber's bar. WHERE THE THRESHOLD IS UNKNOWN there is no f and no cl,
and `fu` is 1: the Journal says a question needed more than a majority and
not how many, or the record's outcome is not one its own count allows and no
threshold explains it. A vote is never marked close on a guess.

NOTHING HERE SAYS ANYTHING OF A PARTY'S POSITION (the owner, 12 November
2026): a vote is not labelled by how the parties divided, and no member is
said to have voted against theirs. `pc` is the figures.

THE BALLOTS come from data/member_votes.json, 560 MB, which is read one
ballot at a time (stream_array) rather than loaded: this step runs beside
others on a machine that cannot hold it. Everything else comes from
rollcalls.json, through vote_passage.move_on_bills as every other reader of it
does. A ballot is one of Y (yea), N (nay), E (not voting, excused), X (not
voting, not excused), P (presiding), R (no vote recorded) and . (the member
was not on this roll call). The members of a chamber are listed in a term's
file once, in id order.

Asks nobody anything: it reads files on this disk.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import gzip
import json
from collections import defaultdict

import build_elections as BE
import motions as MO
import vote_passage as VP
from components import WORDBOOK

FOLDER = "votes"
INDEX = "index.json"        # {"from", "terms", "close", "counts"}: what the page reads first
# A CLOSE VOTE, PER CHAMBER (the owner, 12 November 2026): this many voters or
# fewer who would have had to switch to change the outcome. The Senate has 24
# members, so the House's 5 would call a 17-7 vote close there; its bar is 2.
CLOSE_HOUSE = 5
CLOSE_SENATE = 2
CLOSE = {"H": CLOSE_HOUSE, "S": CLOSE_SENATE}
LEGEND = {"Y": "Yea", "N": "Nay", "E": "Not voting, excused", "X": "Not voting, not excused",
          "P": "Presiding", "R": "No vote recorded", ".": "Not on this roll call"}
CODE = {"Yea": "Y", "Nay": "N", "Not Voting/Excused": "E", "Not Voting/Not Excused": "X",
        "Presiding": "P", "No vote recorded": "R", "": "R"}
# The kind of question, from the motion's key. A vote on no bill is "Procedural"
# whatever it was, and a motion on a bill that is none of these is "Motion on a bill".
KIND = {
    "Committee report": ("otp", "otp_finance", "otpa", "otpa_finance", "itl", "is",
                         "ought_not_to_pass", "refer", "rerefer", "vacate_referral",
                         "waive_referral", "recommit"),
    "Amendment": ("committee_amendment", "floor_amendment", "amendment", "enrolled_amendment",
                  "concur", "nonconcur", "nonconcur_conference", "table_amendment"),
    "Conference report": ("conference_report", "conference_no_agreement", "request_conference",
                          "accede", "refuse_accede"),
    "Veto override": ("override_first", "override_second"),
    "Passage": ("final_passage", "third_reading", "order_third_reading", "adopt", "introduce",
                "introduce_adopt"),
    "Motion on a bill": ("table", "table_motion", "untable", "reconsider", "postpone",
                         "special_order", "suspend_rules", "previous_question", "limit_debate",
                         "divide", "part", "withdraw", "print_debate", "uphold_ruling"),
}
KIND_OF = {mk: k for k, mks in KIND.items() for mk in mks}
KINDS = tuple(KIND) + ("Procedural", "Other")


def stream_array(path, chunk=1 << 24):
    """The objects of a JSON file holding one array, one at a time, in file
    order -- so that a 560 MB file costs the memory of one chunk."""
    dec = json.JSONDecoder()
    buf, pos, eof = "", 0, False
    with open(path, encoding="utf-8") as fh:
        while True:
            while pos < len(buf) and buf[pos] in " \t\r\n,[":
                pos += 1
            if pos >= len(buf):
                if eof:
                    return
            elif buf[pos] == "]":
                return
            else:
                try:
                    obj, end = dec.raw_decode(buf, pos)
                except ValueError:
                    if eof:
                        raise
                    obj = None
                if obj is not None:
                    yield obj
                    pos = end
                    continue
            more = fh.read(chunk)
            if not more:
                eof = True
            buf = buf[pos:] + more
            pos = 0


def fixed_flip(yeas, need):
    """Voters who would have had to switch from yes to no (to undo a question
    that reached `need` yeas) or from no to yes (to carry one that fell
    short), where `need` is a number of yeas that a switch leaves where it
    was."""
    return yeas - need + 1 if yeas >= need else need - yeas


def flips(r):
    """The roll call's flip count, or None where its threshold is not known:
    see the module's docstring for the rule and for why a guess is no flip."""
    y, n = r.get("yeas"), r.get("nays")
    if not isinstance(y, int) or not isinstance(n, int) or y + n == 0:
        return None
    if r.get("threshold_unknown"):
        return None
    need, rule = r.get("threshold_needed"), r.get("threshold_rule") or ""
    carried = bool(r.get("passed"))
    if need is None:
        # A majority, which is what the record names none other than.
        return BE.flip_majority(y, n) if carried == (y > n) else None
    if carried != (y >= need) or need > y + n:
        return None                 # or no switch could carry it
    if rule.startswith("two thirds"):
        f = BE.flip_two_thirds(y, n)
        return f if f == fixed_flip(y, need) else None
    return fixed_flip(y, need)


def kind_of(mk, bill):
    if not bill:
        return "Procedural"
    return KIND_OF.get(mk) or ("Other" if not mk or mk == "unnamed" else "Motion on a bill")


def row_of(r, bid, motions):
    """The term file's row for one roll call (ballots not yet counted)."""
    key = f'{r.get("year")}-{r.get("body")}-{r.get("number")}'
    bill = "" if bid == "_procedural" else bid
    mk = MO.classify(r.get("question"), bid, r.get("body") or "", motions).get("mk") or ""
    row = {"id": key, "d": r.get("date") or "", "c": r.get("body") or "", "b": bill,
           "q": (r.get("question_plain") or r.get("question") or "").strip(),
           "mk": mk, "k": kind_of(mk, bill), "p": 1 if r.get("passed") else 0,
           "y": r.get("yeas"), "n": r.get("nays"),
           "e": r.get("excused") or 0, "a": r.get("not_excused") or 0}
    if r.get("presiding"):
        row["pd"] = r["presiding"]
    if r.get("no_vote_recorded"):
        row["nr"] = r["no_vote_recorded"]
    if "yeas_stated" in r:
        row["ys"], row["ns"] = r["yeas_stated"], r["nays_stated"]
    f = flips(r)
    if f is None:
        row["fu"] = 1
    else:
        row["f"] = f
        if f <= CLOSE.get(row["c"], CLOSE_HOUSE):
            row["cl"] = 1
    if r.get("threshold_needed"):
        row["nd"] = r["threshold_needed"]
    if r.get("outcome_conflict"):
        row["oc"] = 1
    if not bill:
        w = VP.short(VP.entry(key))
        if w:
            row["w"] = w
    return row


def rows_by_term(rollcalls, motions):
    """{term: [row, ...]} oldest first, and {id: (term, chamber)}."""
    out, where = {}, {}
    for term, bills in sorted((rollcalls or {}).items()):
        if not isinstance(bills, dict):
            continue
        rows = [row_of(r, bid, motions) for bid, rcs in bills.items() for r in rcs]
        rows.sort(key=lambda x: (x["d"], x["c"], int(x["id"].rsplit("-", 1)[1])))
        out[term] = rows
        for x in rows:
            where[x["id"]] = (term, x["c"])
    return out, where


def member_sort(i):
    return (0, int(i), "") if str(i).isdigit() else (1, 0, str(i))


def encode_ballots(ballots, where):
    """({term: {chamber: {"m": [ids], "r": {id: string}}}}, {id: [dy, dn, ry,
    rn]}, unmatched): one pass over the ballots, nothing kept but a byte a
    ballot."""
    cols = defaultdict(dict)                    # (term, chamber) -> member id -> column
    rolls = {}                                  # roll call id -> bytearray, columns by first sight
    party = {}
    unmatched = 0
    for v in ballots:
        key = f'{v.get("year")}-{v.get("body")}-{v.get("vote_number")}'
        at = where.get(key)
        if at is None:
            unmatched += 1
            continue
        c = cols[at]
        mid = str(v.get("member_id"))
        col = c.setdefault(mid, len(c))
        buf = rolls.get(key)
        if buf is None:
            buf = rolls[key] = bytearray()
        if col >= len(buf):
            buf.extend(b"." * (col + 1 - len(buf)))
        code = CODE.get(v.get("vote") or "")
        if code is None:
            raise ValueError(f"{key}: a ballot of {v.get('vote')!r}, which this file has no letter for")
        if buf[col] != ord("."):
            raise ValueError(f"{key}: member {mid} has two ballots")
        buf[col] = ord(code)
        if code in "YN":
            pc = party.setdefault(key, [0, 0, 0, 0])
            p = v.get("party")
            if p in ("D", "R"):
                pc[(0 if p == "D" else 2) + (0 if code == "Y" else 1)] += 1
    out = defaultdict(dict)
    for (term, ch), c in sorted(cols.items()):
        ids = sorted(c, key=member_sort)
        order = [c[i] for i in ids]
        entry = {"m": ids, "r": {}}
        for key in sorted(k for k, (t, h) in where.items() if t == term and h == ch and k in rolls):
            buf = rolls[key]
            buf.extend(b"." * (len(c) - len(buf)))
            entry["r"][key] = bytes(buf[j] for j in order).decode("ascii")
        out[term][ch] = entry
    return out, party, unmatched


def tally(s):
    return s.count("Y"), s.count("N")


def attach(rows_term, ballots, party):
    """Fill pc and nb, and say which rows' counts the ballots do not give."""
    off = []
    for term, rows in rows_term.items():
        strings = {}
        for ch in (ballots.get(term) or {}).values():
            strings.update(ch["r"])
        for x in rows:
            s = strings.get(x["id"])
            if s is None:
                x["nb"] = 1
                continue
            if tally(s) != (x["y"], x["n"]):
                off.append(x["id"])
            if x["id"] in party:
                x["pc"] = party[x["id"]]
    return off


def size_of(path):
    raw = Path(path).read_bytes()
    return len(raw), len(gzip.compress(raw, 6))


def write(site, rows_term, ballots):
    folder = Path(site) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    made = []
    for term, rows in sorted(rows_term.items()):
        if not rows:
            continue
        f = folder / f"{term}.json"
        f.write_text(json.dumps({"term": term, "rolls": rows}, separators=(",", ":"),
                                ensure_ascii=False), encoding="utf-8")
        made.append(f.name)
        if ballots.get(term):
            b = folder / f"ballots-{term}.json"
            b.write_text(json.dumps({"term": term, "legend": LEGEND, "chambers": ballots[term]},
                                    separators=(",", ":")), encoding="utf-8")
            made.append(b.name)
    # WHAT THE PAGE NEEDS BEFORE IT ASKS FOR A TERM: the terms that have roll
    # calls, newest first, how many a chamber, and the close-vote bars (so the
    # page words the rule from the data and not from a copy of it).
    terms = sorted((t for t, rows in rows_term.items() if rows), reverse=True)
    index = {"from": terms[-1][:4] if terms else "", "terms": terms,
             "close": {"H": CLOSE_HOUSE, "S": CLOSE_SENATE},
             "counts": {t: {c: sum(1 for x in rows_term[t] if x["c"] == c) for c in ("H", "S")}
                        for t in terms}}
    (folder / INDEX).write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    made.append(INDEX)
    # A term an earlier build wrote and this one has no roll call for.
    for stale in folder.glob("*.json"):
        if stale.name not in made:
            stale.unlink()
    return made


def build(rollcalls, ballots, site):
    """Everything: rows and ballots read, checked and written. Returns the
    rows by term, the ballots and a report dict."""
    rollcalls, moved = VP.move_on_bills(rollcalls)
    rows_term, where = rows_by_term(rollcalls, WORDBOOK["votes"]["motions"])
    enc, party, unmatched = encode_ballots(ballots, where)
    off = attach(rows_term, enc, party)
    if off:
        raise SystemExit(f"{len(off)} roll call(s) whose ballots do not count to the tally the "
                         f"row carries: {', '.join(off[:5])}")
    made = write(site, rows_term, enc)
    return rows_term, enc, {"unmatched": unmatched, "files": made, "moved": moved}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--rollcalls", default="rollcalls.json")
    ap.add_argument("--votes", default="data/member_votes.json")
    a = ap.parse_args()
    try:
        rollcalls = json.loads(Path(a.rollcalls).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sys.exit(f"{a.rollcalls} is not here or is not JSON; nothing was written")
    if not Path(a.votes).exists():
        sys.exit(f"{a.votes} is not here; nothing was written")
    rows_term, enc, rep = build(rollcalls, stream_array(a.votes), a.site)
    n = sum(len(v) for v in rows_term.values())
    if not n:
        sys.exit("no roll call was written (rollcalls.json holds none)")
    if rep["unmatched"]:
        print(f"  {rep['unmatched']:,} ballot(s) on a roll call rollcalls.json does not hold, left out")
    for term, rows in sorted(rows_term.items()):
        close = sum(1 for x in rows if x.get("cl"))
        print(f"  {FOLDER}/{term}: {len(rows):,} roll calls "
              f"({sum(1 for x in rows if x['c'] == 'H'):,} House, {sum(1 for x in rows if x['c'] == 'S'):,} Senate), "
              f"{close} close, {sum(1 for x in rows if x['k'] == 'Procedural'):,} procedural")
    raw = gz = 0
    for name in rep["files"]:
        r_, g_ = size_of(Path(a.site) / FOLDER / name)
        raw, gz = raw + r_, gz + g_
    print(f"  {FOLDER}/: {len(rep['files'])} files, {n:,} roll calls, {raw / 1024:,.0f} KB "
          f"({gz / 1024:,.0f} KB gzipped)")


if __name__ == "__main__":
    main()
