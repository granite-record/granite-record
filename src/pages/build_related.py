#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-10.1
"""
Related bills: what a bill's Related tab lists, and what the bench is asked
to judge before anything more is listed there.

THE PLAN (ROADMAP.md and LAUNCH.md of September 2026, as the person set it
out): a tab of its own, holding bills that amend the same RSA across the
years and bills whose text was amended into another during a session --
minimum wage, bathroom bans and red flag laws were the worked examples. The
hard part is the whole problem, and the person named it: two bills can touch
the same RSA for unrelated purposes, and two can do the same thing through
different RSAs. So an RSA overlap is a signal, not an answer, and "related
bills -- after a checked sample at the bench, never before".

So this writes two things, and only one of them is published:

  site/related/<term>.json   {bill: [related, ...]} -- what the tab lists. Only
                             what the record itself states: today, the next
                             term's bill a clerk's LSR note on an interim
                             study report names (build_site_v2.next_term_bill,
                             1991-1998), both ways -- "filed again as" on the
                             studied bill and "filed again from" on the new
                             one. Nothing here is inferred.

  data/related_candidates.json   the pairs that amend the same sections of
                             the RSA, ranked, for the bench (review.py's
                             "related" kind). NOT published: no page reads
                             it. Publishing them is a decision for after the
                             bench has measured how many are right, and it is
                             a change to this file's PUBLISHED, not a flag.

"AMENDED INTO" IS NOT HERE YET, on purpose. It is in the docket, but no line
of this disk's copy of the repository holds one, and a reader written from a
guess at the clerk's wording is the failure CLAUDE.md's first rule is about.
src/checks/bill_mentions.py counts the words around another bill's number in
every docket row, on the machine that has narratives.json, so the patterns
can be written from what the clerks actually wrote.

READS every bill's record: site/bills/<year>/<id>.json, or the record inside
its page where build_bill_pages has already taken the file away -- so this
reads every bill whichever has run, and never a subset (a writer run on a
subset destroys the rest). Every term's index (site/idx/<term>.json) names
the bills. Writes the whole of site/related/ and the candidates file on
every run; there is no --term. Asks nobody anything.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import math
import re
from collections import defaultdict

# The kinds the tab lists. A kind is added here only once what it claims has
# been checked (the module docstring): "same_rsa" waits on the bench.
PUBLISHED = ("filed_again_as", "filed_again_from")

# THE SAME SECTIONS, NOT THE SAME TITLE. RSA_CITE is build_site_v2's, so a
# citation reads here as it links on the page.
RSA_CITE = re.compile(
    r"\bRSA\s+(\d{1,3}(?:-[A-Z]{1,2})?)(?![\d-])"
    r"(?::(\d{1,4}(?:-[a-z0-9]{1,3})?(?:\.\d{1,2})?)(?!\d))?",
    re.I)
# A section amended by more bills than this is a statute everything passes
# through -- the definitions of a title, a fee schedule -- and sharing it says
# nothing about two bills. Counted, not weighed, so the bench sees what is cut.
COMMON = 150
# A bill amending a chapter without naming a section ("Amend RSA 674 by
# inserting after section 80 the following new subdivision") shares the
# chapter with every other bill of it: a quarter of a section's weight.
CHAPTER_WEIGHT = 0.25
# The candidates kept for each bill, strongest first.
PER_BILL = 8

BILL_LINK = re.compile(r"^bill/(\d{4})/([a-z]+\d+)\.html$", re.I)


def sections(amends):
    """{"674:81", "674", ...} -- the sections (or bare chapters) a bill's
    record says its text amends, from the keys of its `amends`."""
    out = set()
    for cite in (amends or {}):
        for m in RSA_CITE.finditer(cite):
            ch = m.group(1).upper()
            out.add(f"{ch}:{m.group(2).lower()}" if m.group(2) else ch)
    return out


def stated(rec):
    """[(kind, (year, id), why)] the record itself states about another bill:
    the study report's "filed again as" link (build_site_v2.study_ending)."""
    out = []
    for s in ((rec or {}).get("journey") or {}).get("steps") or []:
        link = s.get("link") or {}
        m = BILL_LINK.match(str(link.get("href") or ""))
        if s.get("act") == "study_report" and m:
            queried = "question mark" in str(s.get("text") or "")
            out.append(("filed_again_as", (int(m.group(1)), m.group(2).upper()), queried))
    return out


def same_rsa(secs_of, common=COMMON, per_bill=PER_BILL):
    """{bill key: [(other key, score, [shared sections])]} for every pair of
    bills that amend a section in common, strongest first, at most
    `per_bill` each. A shared section counts 1/log2(1 + how many bills amend
    it), so the rarer the section the more it says; a shared bare chapter a
    quarter of that. A section more than `common` bills amend is left out."""
    by_sec = defaultdict(list)
    for k, secs in secs_of.items():
        for s in secs:
            by_sec[s].append(k)
    score = defaultdict(lambda: defaultdict(float))
    shared = defaultdict(lambda: defaultdict(list))
    for s, ks in by_sec.items():
        if len(ks) < 2 or len(ks) > common:
            continue
        w = (CHAPTER_WEIGHT if ":" not in s else 1.0) / math.log2(1 + len(ks))
        for a in ks:
            for b in ks:
                if a != b:
                    score[a][b] += w
                    shared[a][b].append(s)
    out = {}
    for a, row in score.items():
        best = sorted(row.items(), key=lambda kv: (-kv[1], kv[0]))[:per_bill]
        out[a] = [(b, round(v, 3), sorted(shared[a][b])) for b, v in best]
    return out


def read_records(site, rows):
    """{(year, id): record} for every row of the indexes, from its file or
    from inside its page (build_bill_pages.embedded)."""
    import build_bill_pages as BBP
    out, missing = {}, 0
    for r in rows:
        yr = str(r.get("year") or "")
        if not yr:
            continue
        f = site / "bills" / yr / f"{r['id']}.json"
        raw = (f.read_text(encoding="utf-8") if f.exists()
               else BBP.embedded(site / "bill" / yr / f"{r['id'].lower()}.html"))
        if raw is None:
            missing += 1
            continue
        try:
            out[(int(yr), r["id"])] = json.loads(raw)
        except ValueError:
            missing += 1
    return out, missing


def entry(row, kind, why, **more):
    """One related bill as the tab draws it: the index's own fields for its
    number, title and chip (app.js chipOf), what relates it, and why."""
    keep = ("id", "n", "year", "term", "title", "chip", "status", "passage", "kind")
    e = {k: row[k] for k in keep if row.get(k) not in (None, "")}
    e["rel"], e["why"] = kind, why
    e.update({k: v for k, v in more.items() if v})
    return e


def build(site, data):
    site, data = Path(site), Path(data)
    rows = []
    for f in sorted((site / "idx").glob("*.json")):
        if not re.fullmatch(r"\d{4}-\d{4}", f.stem):
            continue      # the requests: no bill yet, nothing to relate
        rows += [r for r in json.loads(f.read_text(encoding="utf-8")) if r.get("id")]
    if not rows:
        raise SystemExit("build_related: no bill index under site/idx -- run the site data first")
    row_of = {(int(r["year"]), r["id"]): r for r in rows if r.get("year")}
    recs, missing = read_records(site, rows)

    related = defaultdict(list)          # (year, id) -> [entry]
    n_stated = 0
    for k, rec in recs.items():
        for kind, other, queried in stated(rec):
            if other not in row_of:
                continue
            q = " The clerk's note carries a question mark." if queried else ""
            related[k].append(entry(row_of[other], kind,
                                    "Filed again as this bill after an interim study; the "
                                    "clerk noted it on the committee's report." + q))
            related[other].append(entry(row_of[k], "filed_again_from",
                                        "Held for interim study in the term before, and filed "
                                        "again as this bill; the clerk noted it on that "
                                        "committee's report." + q))
            n_stated += 1

    # The bench's pairs, never the page's (PUBLISHED).
    secs = {k: sections(rec.get("amends")) for k, rec in recs.items()}
    secs = {k: s for k, s in secs.items() if s}
    cands = same_rsa(secs)
    pairs, seen_pair = [], set()
    for a0, lst in cands.items():
        for b0, score, shared in lst:
            # each pair once, whichever bill's list it was kept on (the score
            # is the same both ways)
            a, b = sorted((a0, b0))
            if (a, b) in seen_pair:
                continue
            seen_pair.add((a, b))
            ra, rb = row_of.get(a, {}), row_of.get(b, {})
            pairs.append({"key": f"{a[0]}/{a[1]}|{b[0]}/{b[1]}", "score": score,
                          "sections": shared,
                          "a": {"id": a[1], "year": a[0], "term": ra.get("term", ""),
                                "n": ra.get("n", a[1]), "title": ra.get("title", "")},
                          "b": {"id": b[1], "year": b[0], "term": rb.get("term", ""),
                                "n": rb.get("n", b[1]), "title": rb.get("title", "")}})
    pairs.sort(key=lambda p: (-p["score"], p["key"]))
    data.mkdir(parents=True, exist_ok=True)
    (data / "related_candidates.json").write_text(
        json.dumps({"_what": "Pairs of bills whose texts amend a section of the RSA in "
                             "common, ranked. For the bench (review.py, kind 'related'); "
                             "not published. build_related.py writes it whole on every run.",
                    "common": COMMON, "pairs": pairs}, ensure_ascii=False),
        encoding="utf-8")

    # THE WHOLE OF site/related/, every run, ONE FILE FOR EVERY TERM -- {} where
    # nothing in it is related, so a bill's page never asks for a file that is
    # not there -- and a file left from an earlier build for a term no index
    # names goes.
    out = site / "related"
    out.mkdir(parents=True, exist_ok=True)
    by_term = {r["term"]: {} for r in rows if r.get("term")}
    for k, lst in related.items():
        lst = [e for e in lst if e["rel"] in PUBLISHED]
        if not lst or k not in row_of:
            continue
        seen, uniq = set(), []
        for e in lst:
            key = (e["rel"], e.get("year"), e.get("id"))
            if key not in seen:
                seen.add(key)
                uniq.append(e)
        by_term.setdefault(row_of[k]["term"], {})[k[1]] = uniq
    for old in out.glob("*.json"):
        if old.stem not in by_term:
            old.unlink()
    for term, bills in by_term.items():
        (out / f"{term}.json").write_text(json.dumps(bills, ensure_ascii=False,
                                                     separators=(",", ":")), encoding="utf-8")
    n_listed = sum(len(b) for b in by_term.values())
    n_terms = sum(1 for b in by_term.values() if b)
    # SAID, NOT SILENT: a run that lists nothing says so and why.
    print(f"  {len(recs):,} records read ({missing:,} with none); {n_stated} stated "
          f"links, {n_listed:,} bills with a Related tab in {n_terms} of {len(by_term)} terms")
    print(f"  {len(secs):,} bills amend a section of the RSA; {len(pairs):,} pairs sharing "
          f"one are held for the bench in {data / 'related_candidates.json'}, not published")
    return by_term, pairs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", default="site")
    ap.add_argument("--data", default="data")
    a = ap.parse_args()
    build(a.site, a.data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
