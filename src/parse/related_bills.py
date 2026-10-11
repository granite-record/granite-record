#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.3
"""
Related bills: which bills and amendments share their proposed language.

    python3 src/parse/related_bills.py              # writes related_bills.json
    python3 src/parse/related_bills.py --dry-run    # counts only

Asks nobody. Reads the bill texts (bill_text.json, archive_text.json), the
amendment texts (db/past/PastAmendments.jsonl, amendments.json, and the
current term's site/versions/<year>/*.aN.txt where a build has written
them), the statute table through rsa.py, and chapters.json for which bills
became law. numpy, which the nightly already pins, does the arithmetic.

THE DESIGN IS RELATED_BILLS.md (7 October 2026), and the method is its
prototype's, moved here unchanged in what it decides:

- A document is a bill's body (after "Be it Enacted ... convened:", before
  any fiscal note) or an amendment's (after its "Amendment to HB n"
  heading). Text in [brackets] is old law a bill strikes, and is dropped.
- Every run of five words is hashed to 64 bits, the same on every machine
  and under every PYTHONHASHSEED (CRC32 word ids, a fixed polynomial,
  splitmix64). A run in more than 40 documents is boilerplate ("this act
  shall take effect 60 days after its passage") and is dropped.
- Candidates share at least three runs from a consistent one-in-eight
  sample; every candidate is then compared exactly.
- QUOTED LAW IS NOT SHARED LANGUAGE. A New Hampshire bill reprints the
  paragraph it amends, so two bills amending one paragraph look alike while
  proposing nothing in common. A run that is in today's statute text counts
  only where the later document could have put it there: the earlier one did
  not become law, the later one did (or is an amendment to one that did),
  and the section has changed since the earlier year.

WHAT IT WRITES, related_bills.json, keyed {term: {bill: [...]}}, as preflight
requires of every per-bill file. Each entry:

    {"kind": "language", "other": "2023-2024/HB106", "share": 0.97}
        -- the two bills' proposed language: "share" is how much of the
           smaller bill's is in the other (containment, not Jaccard: a
           refile that adds sections still holds the whole of the first)
    {"kind": "amendment", "other": "2023-2024/HB2", "amendment": "2023-1333h",
     "direction": "bill_in_amendment", "share": 0.91}
        -- this bill's language inside an amendment offered to another bill,
           or ("amendment_in_bill") an amendment's language inside this one
    {"kind": "inside_law", "other": "2025-2026/HB377", "share": 0.86}
        -- this bill mostly inside a bill at least three times its size that
           became law

and a "band" of "line" (share >= 0.8, the starting line RELATED_BILLS.md
decision 1 proposes) or "below" (0.6 to 0.8, kept only for the bench's
seventh stratum and shown nowhere).

WHAT IS SHOWN. The bench judged a sample of each kind (review.py's
"related" kind; tests/related_judged_2026-10-11.json), and a bill's Related
tab shows only what shown() passes: a relation at the line, and an amendment
only with a fate the docket records (build_site_v2.add_related).
An amendment relation also waits for the amendment's fate from the docket:
"offered as an amendment to HB 2, which the House rejected 72-300" is the
fact, and "added to HB 2" would be false (RELATED_BILLS.md §2.2).
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import html
import json
import re
import time
import zlib

import rsa

ROOT = _paths.ROOT
OUT = ROOT / "related_bills.json"

K = 5            # words a shingle
DF_CUT = 40      # in more documents than this, a shingle is boilerplate
SAMPLE = 8       # the consistent sample that finds candidates
MIN_SAMPLED = 3  # sampled shingles two documents must share to be compared
MIN_PROP = 25    # proposed shingles the smaller side needs, about thirty words
LINE = 0.8       # the starting line for "the same language"
BELOW = 0.6      # the bench's lower band, shown nowhere
LAW_RATIO = 3    # "inside a law": the law at least this many times the bill
# THE JUDGED SAMPLE OF 11 OCTOBER 2026 (the person asked for it to be judged
# here; 210 pairs, seven strata of thirty). Nearly every wrong pair was one of
# two things, and these three rules remove them:
#  - a short bill and a far larger one, in different terms, sharing a reprinted
#    statute paragraph or a budget's boilerplate: HB 2 of 2023 "filed again" as
#    SB 662, a three-sentence appropriation. A refiling across terms needs the
#    shared language to be at least REFILE_BIG_SHARE of the larger bill too.
#  - "became law as part of" a law passed before the bill was filed (a 2007 bill
#    inside a 2003 law), or decades after it: the later document reprinting the
#    statute the earlier one wrote. The law must come in the bill's year or up
#    to LAW_GAP years after.
#  - an amendment and a bill years apart sharing a statute paragraph both
#    reprint (1999 and 2021, 2005 and 2024). Every right pair of the sample was
#    within AMEND_GAP years; every one further apart was wrong.
REFILE_BIG_SHARE = 0.10
LAW_GAP = 2
AMEND_GAP = 3
# THE SECOND JUDGED SAMPLE (206 more pairs, drawn after the rules above):
#  - LAW_GAP was 4; every pair four years apart was wrong or doubtful, every
#    one two years apart right, so a law must come in the bill's term or the
#    next.
#  - a short appropriation ("there is hereby appropriated to the department
#    of environmental services the sum of ...") matched the next term's
#    budget, which appropriates to the same department in the same words. A
#    short document that is mostly an appropriation is related only within
#    its own term: APPROP_SHORT words or fewer.
#  - redistricting: each decade's House and Senate district tables (RSA 662:3,
#    662:5) list most of the same towns in the same words, so two of them look
#    like one bill filed again. They are never related to each other.
APPROP_SHORT = 200
APPROP = re.compile(r"\bis hereby appropriated\b|\bthe sum of \$?\d", re.I)
DISTRICTS = re.compile(r"\brsa\s+662[:\s]+(?:3|5)\b", re.I)

ENACT = re.compile(r"be\s+it\s+(?:enacted|resolved)\b[^:]{0,160}:", re.I)
RESOLVED = re.compile(r"\b(?:that\s+the\s+constitution|resolved\b)", re.I)
FISCAL = re.compile(r"\n\s*(?:LBAO?\b|LBA\s|FISCAL NOTE\b|REVISED FISCAL NOTE)", re.I)
TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
HEAD_BILL = re.compile(r"amendment\s+to\s+(hb|sb|cacr|hcr|scr|hr|sr|hjr|sjr)\s*(\d+)", re.I)
AM_HEAD = re.compile(r"amendment\s+to\s+(?:hb|sb|cacr|hcr|scr|hr|sr|hjr|sjr)\s*\d+[^\n]*", re.I)
STRUCK = re.compile(r"\[[^\[\]]{0,4000}\]")
AMEND_NO = re.compile(r"\b(\d{4}-\d{3,5}[a-zA-Z]{0,2})\b")


# WHAT A PAGE SHOWS (RELATED_BILLS.md §6 and the judged sample of 11 October
# 2026): a relation at the line, and an amendment only where the docket
# records what became of it -- "added to HB 2" for an amendment the House
# rejected 72-300 would be false.
SHOWN_FATES = ("adopted", "failed", "withdrawn")


def shown(r):
    if r.get("band") != "line":
        return False
    return r.get("kind") != "amendment" or r.get("fate") in SHOWN_FATES


def sentence(it, label):
    """The sentence a bill page prints for one relation, and the bench shows
    beside it (RELATED_BILLS.md §6: plain words, not percentages; an
    amendment's fate always stated, "added" only for one adopted). `it` is
    the relation with this bill's key as "a" and the other's as "b";
    `label` names the other bill -- "HB 106 (2023-2024)" at the bench, a
    placeholder the page turns into a link."""
    other, share = label(it.get("b")), float(it.get("share") or 0)
    words = ("the same text" if share >= 0.95 else "most of its text" if share >= 0.8
             else "some of its text")
    if it["kind"] == "language":
        ta, tb = (it.get("a") or "")[:9], (it.get("b") or "")[:9]
        # WHICH WAY THE TEXT WENT (the judged sample, 11 October 2026): a share
        # measured on the smaller bill alone called SB 124's appropriation
        # "most of the text" of HB 2. "mine" is how much of this bill is in
        # the other, "theirs" how much of the other is in this one.
        mine, theirs = it.get("mine"), it.get("theirs")
        if mine is not None and theirs is not None:
            if mine >= 0.8 and theirs < 0.6:
                return (f"Its text is also in {other}, a longer bill." if ta == tb else
                        f"Its text was filed again as part of {other}, a longer bill." if tb > ta else
                        f"Its text was part of {other}, a longer bill filed before it.")
            if theirs >= 0.8 and mine < 0.6:
                return (f"It contains the text of {other}, a shorter bill." if ta == tb else
                        f"Part of its text was filed again as {other}." if tb > ta else
                        f"It contains the text of {other}, filed before it.")
            words = ("the same text" if min(mine, theirs) >= 0.9 else "much the same text"
                     if min(mine, theirs) >= 0.6 else words)
        if ta == tb:
            return f"This term's {other} has {words}."
        return (f"Filed before as {other}, with {words}." if tb < ta
                else f"Filed again as {other}, with {words}.")
    if it["kind"] == "inside_law":
        return f"Nearly all of its text became law as part of {other}."
    num, on = it.get("amendment") or "", label(it.get("b"))
    house = {"H": "House", "S": "Senate"}.get(it.get("fate_body") or "", "chamber")
    vote = f", {it['fate_vote']}" if it.get("fate_vote") else ""
    fate = {"adopted": f"the {house} adopted it{vote}",
            "failed": f"the {house} rejected it{vote}",
            "withdrawn": "it was withdrawn",
            "recommended": "its committee recommended it, and no vote on it is on record"}.get(
                it.get("fate"), "")
    if it.get("direction") == "bill_in_amendment":
        if not fate:
            return (f"Its language was in amendment {num} to {on}, whose fate the docket does not "
                    "record. (Not shown on the site.)")
        if it.get("order") == "before":
            return f"Its language had been offered before, as amendment {num} to {on}; {fate}."
        return f"Its language was offered as amendment {num} to {on}; {fate}."
    if not fate:
        return f"Amendment {num} to {on} carries language this bill has. (No fate on record: not shown.)"
    if it.get("order") == "after":
        return f"Amendment {num} to {on}, offered later, carries language this bill had; {fate}."
    return f"Amendment {num} to {on} carries language this bill has; {fate}."



def term_of_year(y):
    y = int(y)
    a = y if y % 2 else y - 1
    return f"{a}-{a + 1}"


def bill_body(text):
    t = text or ""
    m = ENACT.search(t)
    if m:
        t = t[m.end():]
    else:
        m = RESOLVED.search(t)
        if m:
            t = t[m.start():]
    f = FISCAL.search(t)
    if f and f.start() > 200:
        t = t[:f.start()]
    return t


def amend_body(text):
    t = text or ""
    m = AM_HEAD.search(t[:600])
    if m:
        t = t[m.end():]
    f = FISCAL.search(t)
    if f and f.start() > 200:
        t = t[:f.start()]
    return t


def words_of(t):
    return TOKEN.findall(STRUCK.sub(" ", t or "").lower())


class Shingler:
    """Five-word runs as 64-bit hashes, identical on every machine."""

    C = None

    def __init__(self, np):
        self.np = np
        self.vocab = {}
        if Shingler.C is None:
            Shingler.C = np.array([0x9E3779B97F4A7C15, 0xC2B2AE3D27D4EB4F, 0x165667B19E3779F9,
                                   0xD6E8FEB86659FD93, 0xFF51AFD7ED558CCD], dtype=np.uint64)

    def word(self, w):
        v = self.vocab.get(w)
        if v is None:
            v = self.vocab[w] = zlib.crc32(w.encode()) | (len(w) << 32)
        return v

    def __call__(self, words):
        np = self.np
        if len(words) < K:
            return np.zeros(0, dtype=np.uint64)
        ids = np.fromiter((self.word(w) for w in words), dtype=np.uint64, count=len(words))
        n = len(ids) - K + 1
        h = np.zeros(n, dtype=np.uint64)
        with np.errstate(over="ignore"):
            for j in range(K):
                h += ids[j:j + n] * Shingler.C[j]
            h = h ^ (h >> np.uint64(30))
            h = h * np.uint64(0xBF58476D1CE4E5B9)
            h = h ^ (h >> np.uint64(27))
            h = h * np.uint64(0x94D049BB133111EB)
            h = h ^ (h >> np.uint64(31))
        return np.unique(h)


# ------------------------------------------------------------------ documents

def documents(root=None):
    """[{kind, term, year, bill | num, on, body}]: every bill text and every
    amendment text on this disk, each once."""
    root = Path(root or ROOT)
    docs = []
    for name in ("bill_text.json", "archive_text.json"):
        p = root / name
        if not p.is_file():
            continue
        seen = {(d["term"], d["bill"]) for d in docs if d["kind"] == "bill"}
        for term, bills in json.loads(p.read_text(encoding="utf-8")).items():
            for bill, rec in bills.items():
                if (term, bill) in seen:
                    continue
                docs.append({"kind": "bill", "term": term, "year": int(term[:4]), "bill": bill,
                             "body": bill_body((rec or {}).get("text") or "")})
    seen = set()
    past = root / "db" / "past" / "PastAmendments.jsonl"
    if past.is_file():
        with open(past, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                num = (r.get("AmendmentNo") or "").strip()
                raw = html.unescape(r.get("LegislationText") or "")
                hm = HEAD_BILL.search(raw[:800])
                if not num or num in seen:
                    continue
                y = int(r["sessionyear"])
                docs.append({"kind": "amend", "term": term_of_year(y), "year": y, "num": num,
                             "on": (hm.group(1) + hm.group(2)).upper() if hm else None,
                             "body": amend_body(raw)})
                seen.add(num)
    cal = root / "amendments.json"
    if cal.is_file():
        for num, r in json.loads(cal.read_text(encoding="utf-8")).items():
            m = re.match(r"(\d{4})-", num)
            if not m or num in seen:
                continue
            y = int(m.group(1))
            on = re.sub(r"-(FN|L|A|LOCAL)\b.*$", "", (r.get("heading") or "").upper().replace(" ", ""))
            docs.append({"kind": "amend", "term": term_of_year(y), "year": y, "num": num,
                         "on": on or None, "body": amend_body(r.get("text") or "")})
            seen.add(num)
    for yr in sorted(p.name for p in (root / "site" / "versions").glob("[0-9][0-9][0-9][0-9]")
                     if p.is_dir()):
        for p in sorted((root / "site" / "versions" / yr).glob("*.a*.txt")):
            m = re.match(r"(.+)\.a(\d+)\.txt$", p.name)
            if not m:
                continue
            body = p.read_text(encoding="utf-8", errors="replace")
            mm = AMEND_NO.search(body[:800])
            num = mm.group(1) if mm else f"{yr}:{m.group(1)}.a{m.group(2)}"
            if num in seen:
                continue
            docs.append({"kind": "amend", "term": term_of_year(yr), "year": int(yr), "num": num,
                         "on": m.group(1).upper(), "body": amend_body(body)})
            seen.add(num)
    return docs


def law_shingles(np, sh, table):
    """(hashes, years): each shingle of today's statute text with the year
    since which some section holding it has stood unchanged -- the latest
    year its source note names, 1955 where it names none."""
    hs, ys = [], []
    for s in table.sections.values():
        if s.repealed:
            continue
        years = [y for y, _l, _b in rsa.history(s.note, {})]
        h = sh(words_of(s.text))
        hs.append(h)
        ys.append(np.full(len(h), max(years) if years else 1955, dtype=np.int16))
    H, Y = np.concatenate(hs), np.concatenate(ys)
    o = np.lexsort((Y, H))
    H, Y = H[o], Y[o]
    first = np.concatenate([[True], H[1:] != H[:-1]])
    return H[first], Y[first]


# ------------------------------------------------------- what became of each

# An amendment's fate as its bill's docket records it (RELATED_BILLS.md §2.2:
# "offered as amendment 2023-1333h to HB 2; the House rejected it, 72-300",
# never "added to HB 2"). The docket's own words, read clause by clause:
#   "Amendment #2023-1247h : AA DV 351-38"          adopted
#   "FLAM #2023-1333h (Reps. Hoell, ...): AF DV 72-300"   failed
#   "Ought to Pass with Amendment 2023-1247h ... : MA VV"  adopted with the bill
#   "Majority Committee Report: Ought to Pass with Amendment #2023-1247h"  recommended
# The last decisive line wins: adopted, then reconsidered and withdrawn, is
# withdrawn. A recommendation alone is not an outcome.
FATE_NUM = re.compile(r"(?:(19|20)(\d\d)-\s?)?(\d{4})\s?([hs])\b", re.I)
FATE_BRACE = re.compile(r"[#{<]\s*(?:(19|20)(\d\d)-\s?)?(\d{3,4})\s?([hs]?)\s*[}>]?", re.I)
F_ADOPT = re.compile(r"\bAA\b|(?<!NOT )\bADOPTED\b", re.I)
F_FAIL = re.compile(r"\bAF\b|\bAL\b|\bFAILED\b|NOT\s+ADOPTED|\bLOST\b", re.I)
F_WITHDRAWN = re.compile(r"WITHDR", re.I)
F_PASS_MA = re.compile(r"(?:OUGHT\s+TO\s+PASS|\bOTP)\b[^:;]*?AM\w*[^:;]*[:,]?\s*\bMA\b", re.I)
F_REPORT = re.compile(r"COMMITTEE\s+REPORT|\bREPORT\b|\bREP\b", re.I)
F_VOTE = re.compile(r"\b(RC|DV|DIV|VV|SV)\b\s*\(?\s*(\d{1,3})\s*[-–]\s*(\d{1,3})")


def _fate_nums(clause, year, body):
    out = set()
    for rx in (FATE_NUM, FATE_BRACE):
        for m in rx.finditer(clause):
            yy = f"{m.group(1)}{m.group(2)}" if m.group(2) else str(year)
            suf = (m.group(4) or ("h" if body == "H" else "s")).lower()
            out.add(f"{yy}-{int(m.group(3)):04d}{suf}")
    return out


def amendment_fates(narratives):
    """{"2023-1333h": {"outcome", "body", "date", "vote", "words"}} from every
    bill's docket in narratives.json. outcome is adopted, failed, withdrawn,
    or recommended (a committee's report, no floor action read)."""
    fates = {}
    rank = {"recommended": 0, "adopted": 1, "failed": 1, "withdrawn": 1}
    for term, bills in (narratives or {}).items():
        for bill, rec in bills.items():
            for e in (rec or {}).get("events") or []:
                raw, body = e.get("raw") or "", (e.get("body") or "")[:1].upper()
                date = e.get("date") or ""
                year = int(date[:4]) if date[:4].isdigit() else int(term[:4])
                for clause in re.split(r";", raw):
                    nums = _fate_nums(clause, year, body)
                    if not nums:
                        continue
                    if F_WITHDRAWN.search(clause):
                        outcome = "withdrawn"
                    elif F_FAIL.search(clause) and not F_ADOPT.search(clause):
                        outcome = "failed"
                    elif F_ADOPT.search(clause) or F_PASS_MA.search(clause):
                        outcome = "adopted"
                    elif e.get("type") == "report" or F_REPORT.search(clause):
                        outcome = "recommended"
                    else:
                        continue
                    v = F_VOTE.search(clause)
                    fate = {"outcome": outcome, "body": body, "date": date,
                            "vote": f"{v.group(2)}-{v.group(3)}" if v else "",
                            "words": clause.strip()[:160]}
                    for n in nums:
                        old = fates.get(n)
                        if old is None or rank[outcome] >= rank[old["outcome"]]:
                            fates[n] = fate
    return fates


# ------------------------------------------------------------------ the run

def relate(docs, table, became_law, fates=None):
    import numpy as np
    sh = Shingler(np)
    for d in docs:
        n = len(words_of(d["body"]))
        d["_approp"] = n <= APPROP_SHORT and bool(APPROP.search(d["body"]))
        d["_districts"] = bool(DISTRICTS.search(d["body"]))
        # An amendment's own number names its year (2021-2222s), whatever
        # record it was read from.
        m = re.match(r"(\d{4})-", str(d.get("num") or ""))
        d["_year"] = int(m.group(1)) if d["kind"] == "amend" and m else d["year"]
    sets = [sh(words_of(d.pop("body"))) for d in docs]
    allh = np.concatenate(sets)
    u, cnt = np.unique(allh, return_counts=True)
    boiler = u[cnt > DF_CUT]
    sets = [s[~np.isin(s, boiler, assume_unique=True)] if len(s) else s for s in sets]
    LH, LY = law_shingles(np, sh, table) if table else (np.zeros(0, np.uint64), np.zeros(0, np.int16))

    # candidates: documents sharing sampled shingles
    hs, ds = [], []
    for i, s in enumerate(sets):
        smp = s[(s % np.uint64(SAMPLE)) == 0]
        hs.append(smp)
        ds.append(np.full(len(smp), i, dtype=np.int32))
    H, D = np.concatenate(hs), np.concatenate(ds)
    o = np.argsort(H, kind="stable")
    H, D = H[o], D[o]
    br = np.flatnonzero(np.diff(H)) + 1
    starts, ends = np.concatenate([[0], br]), np.concatenate([br, [len(H)]])
    pc = collections.Counter()
    for g in np.flatnonzero(ends - starts >= 2):
        grp = sorted(set(D[starts[g]:ends[g]].tolist()))
        for a in range(len(grp)):
            for b in range(a + 1, len(grp)):
                pc[(grp[a], grp[b])] += 1

    law_years = {}

    def lyof(i):
        if i not in law_years:
            s = sets[i]
            if not len(LH):
                law_years[i] = np.full(len(s), -1, dtype=np.int16)
            else:
                k = np.searchsorted(LH, s)
                k[k >= len(LH)] = len(LH) - 1
                law_years[i] = np.where(LH[k] == s, LY[k], -1).astype(np.int16)
        return law_years[i]

    def enacted(d):
        if d["kind"] == "bill":
            return (d["term"], d["bill"]) in became_law
        return (d["term"], d.get("on")) in became_law

    def split(i, j):
        """(shared proposed, proposed of i, proposed of j): RELATED_BILLS.md §3's rule."""
        di, dj = docs[i], docs[j]
        e = di if (di["year"], di["kind"] == "amend") <= (dj["year"], dj["kind"] == "amend") else dj
        later = dj if e is di else di
        ye, en = e["year"], e["kind"] == "bill" and enacted(e)
        ln = enacted(later)
        li, lj = lyof(i), lyof(j)
        mi = (li >= 0) & ~(np.bool_(not en) & np.bool_(ln) & (li >= ye))
        mj = (lj >= 0) & ~(np.bool_(not en) & np.bool_(ln) & (lj >= ye))
        _, ia, _jb = np.intersect1d(sets[i], sets[j], assume_unique=True, return_indices=True)
        return int((~mi[ia]).sum()), int((~mi).sum()), int((~mj).sum())

    out = collections.defaultdict(lambda: collections.defaultdict(list))

    def key(d):
        return f"{d['term']}/{d['bill']}"

    def add(d, entry):
        out[d["term"]][d["bill"]].append(entry)

    for (i, j), c in sorted(pc.items()):
        if c < MIN_SAMPLED:
            continue
        di, dj = docs[i], docs[j]
        kinds = (di["kind"], dj["kind"])
        if kinds == ("amend", "amend"):
            continue
        if di["_districts"] and dj["_districts"]:
            continue       # two district tables (DISTRICTS)
        if (di["_approp"] or dj["_approp"]) and di["term"] != dj["term"]:
            continue       # a short appropriation and another term (APPROP_SHORT)
        if kinds == ("bill", "bill"):
            if (di["term"], di["bill"]) == (dj["term"], dj["bill"]):
                continue
            n, la, lb = split(i, j)
            if min(la, lb) < MIN_PROP:
                continue
            share = n / min(la, lb)
            if share < BELOW:
                continue
            band = "line" if share >= LINE else "below"
            # How much of each is in the other: "mine" is this bill's own
            # share, so a sentence can say which way the text went.
            mine_i, mine_j = n / la, n / lb
            if di["term"] == dj["term"] or min(mine_i, mine_j) >= REFILE_BIG_SHARE:
                add(di, {"kind": "language", "other": key(dj), "share": round(share, 2), "band": band,
                         "mine": round(mine_i, 2), "theirs": round(mine_j, 2)})
                add(dj, {"kind": "language", "other": key(di), "share": round(share, 2), "band": band,
                         "mine": round(mine_j, 2), "theirs": round(mine_i, 2)})
            small, big, ls, lbg = (di, dj, la, lb) if la <= lb else (dj, di, lb, la)
            if share >= LINE and lbg >= LAW_RATIO * ls and enacted(big) and not enacted(small) \
                    and 0 <= big["year"] - small["year"] <= LAW_GAP:
                add(small, {"kind": "inside_law", "other": key(big), "share": round(share, 2),
                            "band": "line"})
            continue
        am, bl = (i, j) if di["kind"] == "amend" else (j, i)
        A, B = docs[am], docs[bl]
        if A.get("on") == B["bill"] and A["term"] == B["term"]:
            continue       # its own amendment
        if not A.get("on") or abs(A["_year"] - B["year"]) > AMEND_GAP:
            continue       # no bill to name it by, or years apart (AMEND_GAP)
        n, pa, pb = split(am, bl)
        if min(pa, pb) < MIN_PROP:
            continue
        b_in_a, a_in_b = n / pb, n / pa
        if max(b_in_a, a_in_b) < LINE:
            continue
        direction = "bill_in_amendment" if b_in_a >= LINE else "amendment_in_bill"
        share = b_in_a if direction == "bill_in_amendment" else a_in_b
        fate = (fates or {}).get(A["num"].lower()) or {}
        add(B, {"kind": "amendment", "other": f"{A['term']}/{A['on']}" if A.get("on") else "",
                "amendment": A["num"], "direction": direction, "share": round(share, 2),
                # Which came first: an amendment of 2019 whose language was
                # filed as a bill in 2021 reads the other way round.
                "order": "before" if A["_year"] < B["year"] else "after" if A["_year"] > B["year"] else "same",
                "band": "line", "fate": fate.get("outcome", "unknown"),
                **({"fate_vote": fate["vote"]} if fate.get("vote") else {}),
                **({"fate_body": fate["body"]} if fate.get("body") else {})})
    result = {}
    for term in sorted(out):
        result[term] = {}
        for bill in sorted(out[term]):
            rows = out[term][bill]
            rows.sort(key=lambda e: (e["kind"], -e["share"], e["other"], e.get("amendment", "")))
            result[term][bill] = rows
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--dry-run", action="store_true", help="count, write nothing")
    a = ap.parse_args()
    t0 = time.time()
    docs = documents()
    bills = sum(1 for d in docs if d["kind"] == "bill")
    if not bills:
        print("related: no bill texts on this disk; related_bills.json not written")
        return 0
    table = rsa.load()
    if table is None:
        # The quoted-law rule needs today's statute text. Without it the
        # method finds every pair of bills that reprint one paragraph, so it
        # writes nothing rather than that.
        print("related: db/NH_RSA.psv is not on this disk, and without the statute text quoted "
              "law reads as shared language; related_bills.json not written")
        return 0
    chp = ROOT / "chapters.json"
    chapters = json.loads(chp.read_text(encoding="utf-8")) if chp.is_file() else {}
    became_law = {(t, b) for t, bs in chapters.items() for b, r in bs.items() if r.get("chapter")}
    nar = ROOT / "narratives.json"
    fates = amendment_fates(json.loads(nar.read_text(encoding="utf-8"))) if nar.is_file() else {}
    data = relate(docs, table, became_law, fates)
    count = collections.Counter(e["kind"] + ("" if e["band"] == "line" else " (below)")
                                for bs in data.values() for rows in bs.values() for e in rows)
    fated = collections.Counter(e.get("fate", "unknown") for bs in data.values()
                                for rows in bs.values() for e in rows if e["kind"] == "amendment")
    with_line = sum(1 for bs in data.values() for rows in bs.values()
                    if any(e["band"] == "line" for e in rows))
    print(f"related: {bills:,} bills and {len(docs) - bills:,} amendments read; "
          f"{with_line:,} bills with a relation at the line; "
          + ", ".join(f"{n:,} {k}" for k, n in sorted(count.items()))
          + f" ({time.time() - t0:.0f}s)")
    print("  amendments' fates from the docket: " + ", ".join(f"{n:,} {k}" for k, n in sorted(fated.items())))
    # SILENCE IS NOT SUCCESS: on 8 September 2026's table, 5,139 pairs of
    # bills shared most of their language. A run that finds none read nothing.
    assert count.get("language", 0) > 1000, "almost no shared language found: the texts did not load"
    if a.dry_run:
        return 0
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                   encoding="utf-8")
    print(f"  wrote {OUT.name}, {OUT.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
