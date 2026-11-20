#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
What main adds to the bills' pages after the loop, and the standing notes
one of them reads: a bill's standing note, where its number carries a
meaning across terms (bill_note, from corrections/bill_notes.json, which
check_notes holds to bills that exist); its related bills
(related_entries, add_related, from related_bills.json); the same number in
the other terms its note is true of (same_number_rows, add_same_number); and
the bills' tags while the owner's registry is in force (site_tagging).

    import related as REL
    REL.bill_note(notes, term, bid)              # the note, or None
    REL.add_related(out, index)                  # how many bills have some
    REL.add_same_number(out, index, notes)

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md section 5). It moved here as it stood,
comments and all, nothing inside it edited, in two
pieces in the file's order: bill_note and check_notes; RELATED_GROUPS to
site_tagging. Which bills are related is src/parse/related_bills.py's, and
the tags tag_rules.py's. It imports no builder (_import_cycles_cut). build_site_v2 imports every
name here back under its own, so build_site_v2.<name> answers as it did, for
build_bills, main and the checks.
"""

import json
from pathlib import Path

import proceedings as P


def bill_note(notes, term, bid):
    """The standing note for this bill, if it has one.

    TWO KEY SHAPES, DELIBERATELY. A note in "every_term" is about a number
    that means the same thing term after term -- HB1 has been the budget in
    every term since 1993-1994 -- which is the exact opposite of how the rest
    of this project keys things, and is why the file says so at the top.
    A note in "by_term" is about one bill in one term, which is what the
    ten-year transportation plan needs: it is HB2000, then HB2004, HB2006,
    HB2010, and on to HB2026, a different number every time.

    "from" is what keeps a standing note off the bills that merely share a
    number. HB1 goes back to 1989-1990, but the 1989 bill is a special
    session bill about the public utilities commission and the 1991 one is a
    medicaid enhancement tax. Neither is the budget, and without this both
    would have been published saying they were.
    """
    if not notes:
        return None
    one = ((notes.get("by_term") or {}).get(term) or {}).get(bid)
    if one:
        return one
    n = (notes.get("every_term") or {}).get(bid)
    if not n:
        return None
    if n.get("from") and term < n["from"]:
        return None
    if n.get("until") and term > n["until"]:
        return None
    return n


def check_notes(notes, bills):
    """Every note must name a bill that exists, or say so loudly.

    A note file that matches nothing exits zero having attached nothing,
    which is the silent success this project keeps getting caught by --
    "HB 1" with a space instead of "HB1" would do it, and the only symptom
    would be a page that looks exactly as it did before.
    """
    if not notes:
        return
    have = {(term, bid) for term, bs in bills.items() for bid in bs}
    numbers = {bid for _t, bid in have}
    missing = []
    for bid, n in (notes.get("every_term") or {}).items():
        if bid not in numbers:
            missing.append(f"every_term {bid}")
        elif n.get("from") and not any(t >= n["from"] for t, b in have
                                       if b == bid):
            missing.append(f'every_term {bid} from {n["from"]}')
    for term, bs in (notes.get("by_term") or {}).items():
        for bid in bs:
            if (term, bid) not in have:
                missing.append(f"by_term {term} {bid}")
    if missing:
        raise SystemExit(
            "bill_notes.json names bills that are not in the record: "
            + ", ".join(missing)
            + "\nA note that matches nothing attaches nothing and the build "
              "would exit zero having done it.")


# RELATED BILLS ON A BILL'S PAGE (RELATED_BILLS.md §6; related_bills.py).
# Added after the loop, because an entry names the other bill's number,
# title and status, and the loop has not reached every other bill when it
# writes this one. Only what related_bills.shown passes: a relation at the
# line, and an amendment only with a fate the docket records. Absent file,
# no tab: a night without the statute table skips the step, and that is the
# truth about that night.
RELATED_GROUPS = (("inside_law", "amendment"), ("language_across",), ("language_same",))
RELATED_MAX = 40


def related_entries(term, bid, rows, by_key):
    """[{g, o, n, t, y, c, s}] for one bill: the group (0 where its language
    went, 1 filed before or after, 2 this term's bills with the same text),
    the other bill's key, number, title, year and status, and the sentence
    with "{b}" where the other bill is named, which the page links."""
    import related_bills as RB
    me, out, seen = f"{term}/{bid}", [], set()
    for r in rows:
        o = r.get("other") or ""
        if not RB.shown(r) or o == me or o not in by_key:
            continue
        kind = r["kind"]
        if kind == "language":
            g = 2 if o[:9] == term else 1
        else:
            g = 0
        if kind != "amendment":
            if o in seen:
                continue
            seen.add(o)
        it = {"kind": kind, "a": me, "b": o, "share": r.get("share"), "mine": r.get("mine"),
              "theirs": r.get("theirs"), "order": r.get("order", ""), "amendment": r.get("amendment", ""),
              "direction": r.get("direction", ""), "fate": r.get("fate", ""),
              "fate_vote": r.get("fate_vote", ""), "fate_body": r.get("fate_body", "")}
        x = by_key[o]
        e = {"g": g, "o": o, "n": x.get("n") or o.split("/")[1], "t": x.get("title") or "",
             "y": x.get("year"), "c": x.get("chip") or "", "s": RB.sentence(it, lambda _k: "{b}"),
             "_share": float(r.get("share") or 0)}
        if kind == "amendment":
            # What the History tab needs to say an amendment in a second
            # sentence where the same bill is also listed for its text
            # (the owner's walk of dry run 8, 8 November 2026).
            e.update({"m": it["amendment"], "f": it["fate"], "fb": it["fate_body"], "fv": it["fate_vote"]})
        out.append(e)
    out.sort(key=lambda e: (e["g"], -e["_share"], e["o"]))
    for e in out:
        del e["_share"]
    return out[:RELATED_MAX]


def add_related(out, index, path=None):
    """Puts each bill's related entries into its own JSON. Returns how many
    bills have some."""
    p = Path(path or "related_bills.json")
    if not p.is_file():
        print("  related bills: no related_bills.json here; no related bills on any History tab")
        return 0
    data = json.loads(p.read_text(encoding="utf-8"))
    by_key = {f"{r.get('term')}/{r.get('id')}": r for r in index}
    n_bills = n_rows = 0
    for r in index:
        term, bid = r.get("term"), r.get("id")
        rows = (data.get(term) or {}).get(bid)
        if not rows:
            continue
        rel = related_entries(term, bid, rows, by_key)
        if not rel:
            continue
        f = out / "bills" / str(r.get("year")) / f"{bid}.json"
        if not f.is_file():
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        rec["related"] = rel
        f.write_text(json.dumps(rec), encoding="utf-8")
        n_bills += 1
        n_rows += len(rel)
    print(f"  related bills: {n_rows:,} relations on {n_bills:,} bills' pages")
    return n_bills


def same_number_rows(notes, index):
    """{(term, bid): [{term, y, id, n, t, c}, ...]}: for a bill number corrections/
    bill_notes.json gives a standing meaning (HB 1 is the budget), the same
    number in each OTHER term the note is true of, newest first, each with its
    year, number, title and outcome chip. Only the terms the note holds for
    (bill_note's `from` and `until`): the HB 1 of 1989-1990 is another bill that
    shares the number. Bills the note does not name get nothing."""
    rows = {}
    for r in index:
        n = bill_note(notes, r.get("term"), r.get("id"))
        if n:
            rows.setdefault(r.get("id"), []).append(r)
    out = {}
    for bid, mine in rows.items():
        for r in mine:
            others = sorted((x for x in mine if x["term"] != r["term"]),
                            key=lambda x: x["term"], reverse=True)
            if others:
                out[(r["term"], bid)] = [
                    {"term": x["term"], "y": x.get("year"), "id": bid, "n": x.get("n") or bid,
                     "t": x.get("title") or "", "c": x.get("chip") or ""} for x in others]
    return out


def add_same_number(out, index, notes):
    """Puts each standing-note bill's same-number list into its own JSON, as
    `same_number`, for the History tab's "HB 1 in other terms". Returns how many
    bills have one."""
    by = same_number_rows(notes, index)
    n_bills = 0
    for r in index:
        rows = by.get((r.get("term"), r.get("id")))
        if not rows:
            continue
        f = out / "bills" / str(r.get("year")) / f"{r.get('id')}.json"
        if not f.is_file():
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        rec["same_number"] = rows
        f.write_text(json.dumps(rec), encoding="utf-8")
        n_bills += 1
    print(f"  same number in other terms: {n_bills:,} bills' History tabs")
    return n_bills


def site_tagging(bills, bill_texts, registry=None):
    """The bills' tags, as build_bills and meta.json take them: {} where no
    registry is in force, else {"bills": {(term, bill): {id: why}}, "at":
    {id: its place in meta.json's list}, "names": {id: name}, "meta": the
    keys meta.json gains}.

    TOPICS AS TAGS, STAGES 3 AND 4 (reports/topics-as-tags-design-2026-11.md,
    sections 2.2, 5 and 6), SWITCHED OFF UNTIL THE OWNER APPROVES THE LIST.
    The registry is hers, corrections/tags.json (tag_rules.in_force), which
    she puts in force by copying a draft there. Without it this answers {},
    and the site is the site that was built before tags, byte for byte: no
    bill's record or index row and no key of meta.json changes, and
    build_pages publishes the scripts and app.css without their TAGS regions.
    With it, each bill is read by the engine as it stands (tag_rules), from
    its title, its text (the archived page's where that is all there is) and
    the topic it is filed under, after the site's vocabulary has named that.
    `registry` is the file to read in place of corrections/tags.json, for a
    check.
    """
    import tag_rules as TR
    doc = TR.in_force(registry)
    if not doc:
        return {}
    current = max(bills) if bills else ""
    rows = ((term, bid, rec.get("title") or "",
             ((P.per_term(bill_texts, term, current).get(bid) or {}).get("text") or ""),
             rec.get("subject") or "")
            for term, byb in bills.items() for bid, rec in byb.items())
    tagged = TR.site_tags(rows, doc)
    meta = TR.site_meta(doc, tagged, {r.get("subject") for byb in bills.values()
                                      for r in byb.values() if r.get("subject")})
    at = {t["id"]: i for i, t in enumerate(meta.get("tags") or [])}
    names = {t["id"]: t["name"] for t in meta.get("tags") or []}
    n_bills = sum(len(byb) for byb in bills.values())
    print(f"tags: {len(at)} of the registry's {len(doc['tags'])} on {len(tagged):,} of "
          f"{n_bills:,} bills (corrections/tags.json); {len((meta or {}).get('tag_words') or {}):,} "
          "words a reader may type lead to a tag or a topic")
    if not tagged:
        # SILENCE IS NOT SUCCESS: a registry in force that tags nothing
        # publishes a site with no tags, which looks like no registry at all.
        print("WARNING: corrections/tags.json is in force and no bill carries one of its tags: "
              "check its rules with python3 src/parse/tag_rules.py --bill TERM BILL")
    return {"bills": tagged, "at": at, "names": names, "meta": meta}
