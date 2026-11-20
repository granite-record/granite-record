#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
A bill's topic, as the bill index files it: the topic model's answer for the
eighteen terms the General Court gave none (merge_guessed_topics), and the
site's one vocabulary of topics applied to every bill of every term, last
(unify_vocabulary).

    import bill_topics as BT
    BT.merge_guessed_topics(bills)   # how many bills the topic model gave a topic
    BT.unify_vocabulary(bills)       # how many bills moved into the site's vocabulary

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: the topic vocabulary). It moved here as
it stood, comments and all, in two pieces: TOPICS_GUESSED to ADDED_CODES,
then unify_vocabulary; the comment between them, which says where
TOPIC_WORDS and vocabulary_of are imported in build_site_v2, stayed there.
The vocabulary itself is src/parse/topic_vocabulary.py's (vocabulary_of) and
topic_model.py's (the codes and the splits). It imports no builder
(_import_cycles_cut). build_site_v2 imports every name here back under its
own, so build_site_v2.unify_vocabulary and the rest answer as they did, for
main and the checks.
"""

import json
from collections import Counter
from pathlib import Path

import topic_model as TM
# The site category a record's topic ends up under (src/parse/topic_vocabulary.py).
from topic_vocabulary import vocabulary_of


TOPICS_GUESSED = Path("topics_assigned.json")


def merge_guessed_topics(bills):
    """Fill a topic for the eighteen terms the General Court gave none.

    Its own assignment reaches 2,221 bills of 2025-2026 and no others, so the
    topic facet has been a filter that hides 29,449 bills. topics.py learns
    from the term they did label and answers for the rest, or says
    Miscellaneous where it cannot -- at the threshold it publishes at, 14 of
    15 of its answers were judged defensible at the bench and none wrong.

    NEVER OVER A TOPIC THE GENERAL COURT GAVE. A record that already carries
    one keeps it, so 2025-2026 is untouched and a later term the General Court
    labels will overwrite nothing.

    AND IT IS MARKED AS OURS. subject_source distinguishes the two on every
    record that has a topic at all, because a reader filtering by Elections
    should be able to find out whether the General Court filed a bill there or
    this site did. That is the same distinction the page already draws between
    a boundary the chair spoke and one a model placed, and between a veto
    message quoted and a bill note written here.

    Absent the file, nothing happens and the site is exactly as it was.
    """
    if not TOPICS_GUESSED.exists():
        return 0
    try:
        guessed = json.loads(TOPICS_GUESSED.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    n = 0
    for term, by_bill in bills.items():
        for bid, rec in by_bill.items():
            # A subject the site retires ("Regular Meeting") is no label: the
            # model's answer for the bill, if there is one, replaces it.
            if rec.get("subject") and not (
                    rec["subject"] in TM.RETIRED
                    and ((guessed.get(term) or {}).get(bid) or {}).get("subject")):
                rec.setdefault("subject_source", "general court")
                continue
            got = (guessed.get(term) or {}).get(bid)
            if not got or not got.get("subject"):
                continue
            rec["subject"] = got["subject"]
            rec["subject_code"] = got.get("subject_code") or ""
            rec["subject_source"] = "granite record"
            n += 1
    if n:
        print(f"  {n:,} bills given a topic by the topic model "
              f"(the General Court gave none); marked subject_source")
    return n


# Codes for the two categories the General Court does not have. Nothing reads
# subject_code -- it is carried through and displayed -- but it must not be
# empty where every other subject has one.
# One definition, in topic_model beside the names themselves: this file had
# its own copy, and two tables of the same two codes are two chances to
# disagree the day a third name is added.
ADDED_CODES = TM.ADDED_CODES


def unify_vocabulary(bills):
    """ONE VOCABULARY ACROSS ALL NINETEEN TERMS, applied last and to everything.

    The topic model predicts in the General Court's own 46 categories, which is
    the vocabulary it was measured in -- 62.1% to 67.2% held out. The site's
    own vocabulary is a different thing: five starved categories folded into
    parents, Regular Meeting retired, Housing and Study Committees added,
    two split in two (TM.SPLITS) and Cannabis drawn from the rest
    (TM.cannabis_topic). Applying it inside the model would have meant
    scoring the model against a vocabulary it was not measured in.

    So it is applied HERE instead, once, to every bill of every term -- the
    General Court's own labels for 2025-2026 as much as the model's answers for
    the archive. That is the point. Fold the archive alone and the two halves of
    the site stop sharing a vocabulary: a reader filtering Parks and Recreation
    would find 2025-2026's bills and none of the eighteen terms before it, and a
    reader filtering Housing would find the archive and not the current term.
    A facet that means different things in different terms is worse than either
    name on its own.

    The rule for the folds is that a category has to carry its own
    weight: measured from the General Court's own labels, these five run at 0.5
    to 6 bills a year against a threshold of ten, and the seven others between 7
    and 9.5 were deliberately left alone.
    """
    moved = Counter()
    for term, by_bill in bills.items():
        for bid, rec in by_bill.items():
            s = (rec.get("subject") or "").strip()
            if not s:
                continue
            new_s = vocabulary_of(s, rec, bid, term)
            if new_s is None:
                rec["subject"], rec["subject_code"] = "", ""
                moved["retired"] += 1
                continue
            if new_s != s:
                rec["subject"] = new_s
                rec["subject_code"] = ADDED_CODES.get(new_s) or rec.get("subject_code") or ""
                moved[f"{s} -> {new_s}"] += 1
    if moved:
        total = sum(moved.values())
        print(f"  {total:,} bills moved into the site's own topic vocabulary")
        for k, v in moved.most_common(8):
            print(f"      {v:>6,}  {k}")
    return sum(moved.values())
