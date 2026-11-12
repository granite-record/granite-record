#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.1
"""
An initial topic for a bill request, from its title.

    python3 src/parse/request_topics.py --score               # what it is worth, title only; writes nothing
    python3 src/parse/request_topics.py --sample 20           # titles and their topics, for a person to read
    python3 src/parse/request_topics.py --sample 20 --lsrs lsrs.json

No network. A bill request has a title, a prime sponsor and a kind, and nothing
else: no committee, no text, no General Court subject code. The owner (12
November 2026): "assign an initial topic to LSRs based on the title as best we
can since that information is helpful". The site already has the classifier
that gave the archived bills their topics before the General Court's own codes
were adopted (topics.py), so this is that, not a second one.

THE SAME MODEL, ITS TITLE HALF. topics.py learns, from the 2,221 bills of
2025-2026 the General Court itself labelled, which words of a title go with
which topic, and answers from a title and a committee. A request has no
committee, so the model is trained on the titles alone (the committee tokens
left out, not merely unseen: a model trained with a committee token and asked
without one is measured in a regime it was not scored in). Measured on a half
it never saw, title only, 1,088 bills (--score):

    margin >= 0    every bill given a topic         49% right
    margin >= 4    51% given one                    70% right
    margin >= 6    40% given one                    75% right    <- THRESHOLD
    margin >= 8    32% given one                    79% right

Those are against the General Court's 46 names; against the site's categories
(a few folded into parents) a few more are right.

BELOW THE THRESHOLD A REQUEST HAS NO TOPIC. Not "Miscellaneous", which would
be a statement that the title was read and fits nowhere: below the threshold
the model is guessing, and a wrong topic is worse than none -- a reader
filtering by Elections who finds a request about something else has been
misled, one who finds fewer has only been underserved (topics.py, the same
reasoning). A title the model's honest answer for is Miscellaneous gets none.

TWO TITLE RULES FIRST, the site's own and exact: a study (topic_model.is_study)
is Study Committees and Commissions, and a housing title (is_housing) is
Housing, as they are for every bill.

THE SITE'S CATEGORY, NEVER A NEW ONE. The model answers in the General Court's
own names; build_site_v2.vocabulary_of turns each into the category the site
shows (the folds, the two renamed names), the one path every term's topics take.
A name the site retired comes out as None and the request gets no topic.

WHAT IS WRITTEN. `topic` and `topic_by = "title"` on a request's row, which the
bill search shows as "from the title" (app.js). When the request is filed as a
bill, the bill's own topic (the General Court's code) is the one shown: the
request's page forwards to the bill's, and nothing here carries over.
Deterministic: the same bills and titles give the same answers under any
PYTHONHASHSEED.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import json
import random

import topics

# A margin in the model's log space: 6 gave 75% right on a held-out half at
# 40% coverage, title only (the docstring). A judgement, to be argued with from
# the bench like topics.THRESHOLD.
THRESHOLD = 6.0
# What topic_by says: the topic is the title's, not the General Court's.
BY = "title"


def titles_only(rec):
    """A record as the title-only model sees it: the title and the subject."""
    return {"title": rec.get("title") or "", "subject": rec.get("subject") or ""}


def train_on(bills):
    """The title-only model, from {term: {bill: record}} (data/bills.json): every
    bill of the term the General Court labelled. None where there are none."""
    rows = [(b, titles_only(r)) for b, r in topics.labelled(bills)]
    return topics.train(rows) if rows else None


def topic_of(model, title, site_name=None):
    """(the site's topic for a request titled `title`, or "" where none is
    confident; the margin). `site_name` is build_site_v2.vocabulary_of, passed
    in so a caller that has it loaded is not made to load it twice."""
    import topic_model as TM
    rec = {"title": title, "subject": "", "bill": ""}
    if TM.is_study(title):
        gold = TM.STUDY
    elif TM.is_housing(title):
        gold = TM.HOUSING
    elif model is None:
        return "", 0.0
    else:
        gold, margin, _second = topics.classify(model, rec, THRESHOLD)
        if gold == topics.MISC:
            return "", margin
        return (site_name or _vocabulary_of())(gold, rec) or "", margin
    return (site_name or _vocabulary_of())(gold, rec) or "", 99.0


def _vocabulary_of():
    import build_site_v2
    return lambda s, rec: build_site_v2.vocabulary_of(s, rec, "")


def assign(rows, model, site_name=None):
    """Put `topic` and `topic_by` on each request row that gets one, and keep
    them empty on the rest. Returns {topic: n}. A row that is already a bill
    (it has `introduced`) is left alone: its topic is the bill's."""
    got = collections.Counter()
    fn = site_name or _vocabulary_of()
    for r in rows:
        if r.get("introduced"):
            continue
        t, _m = topic_of(model, r.get("title") or "", fn)
        r["topic"], r["topic_by"] = (t, BY) if t else ("", "")
        if t:
            got[t] += 1
    return dict(got)


def score():
    """Held-out accuracy of the title-only model, as topics.score measures the
    full one: train on one half of 2025-2026's labelled bills, ask the other."""
    bills = topics.load()
    lab = [(b, titles_only(r)) for b, r in topics.labelled(bills)]
    tr = [x for x in lab if topics.split_half(x[0]) == 0]
    te = [x for x in lab if topics.split_half(x[0]) == 1]
    model = topics.train(tr)
    rows = []
    for _b, r in te:
        ranked = topics.rank(model, r)
        rows.append((ranked[0][1] - ranked[1][1], ranked[0][0] == r["subject"]))
    print(f"{len(lab):,} labelled bills; trained on {len(tr):,}, scored on the "
          f"{len(te):,} it never saw, titles only.\n")
    print(f"{'margin':>8}{'given a topic':>15}{'coverage':>10}{'of those, right':>17}")
    for thr in (0, 2, 4, 6, 8, 10, 14):
        keep = [ok for m, ok in rows if m >= thr]
        if keep:
            mark = "  <- THRESHOLD" if thr == THRESHOLD else ""
            print(f"{thr:>8}{len(keep):>15,}{100 * len(keep) / len(rows):>9.0f}%"
                  f"{100 * sum(keep) / len(keep):>16.1f}%{mark}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--sample", type=int, default=0, help="print this many requests with their topic")
    ap.add_argument("--lsrs", default="lsrs.json")
    ap.add_argument("--bills", default=str(topics.BILLS))
    a = ap.parse_args()
    topics.BILLS = Path(a.bills)
    if a.score:
        return score()
    bills = topics.load()
    model = train_on(bills)
    reqs = json.loads(Path(a.lsrs).read_text(encoding="utf-8"))
    rows = [{"title": r.get("title"), "n": r.get("lsr")} for r in reqs]
    tally = assign(rows, model)
    n = sum(tally.values())
    print(f"{n} of {len(rows)} requests get a topic from the title "
          f"({100 * n / max(1, len(rows)):.0f}%); the rest stay without one.")
    for t, c in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {c:>4}  {t}")
    if a.sample:
        rnd = random.Random(2026_11_12)
        for r in rnd.sample(rows, min(a.sample, len(rows))):
            print(f"{r['n']}  {r['topic'] or '-':38}  {r['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
