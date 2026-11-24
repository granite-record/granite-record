#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.10
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

THE SAME MODEL, ITS TITLE HALF. topics.py learns which words of a title go with
which topic and answers from a title and a committee. A request has no
committee, so the model is trained on the titles alone (the committee tokens
left out, not merely unseen: a model trained with a committee token and asked
without one is measured in a regime it was not scored in).

FROM EVERY TERM'S OFFICIAL CODE, THE CURRENT TERM'S COUNTED THREE TIMES (the
owner, 15 November 2026: "Start polishing the topic and tag matcher"). It
learned from the 2,221 bills of 2025-2026 alone, the only term the General
Court had labelled when it was written. The archived terms carry the General
Court's own codes too now (official_topics.adopt, the decision of 1 October
2026, built on 11 November): 24,525 more titles with an official topic. They
are added, and the current term's labels are counted CURRENT_WEIGHT times,
since its coding is the one the next session's bills will be coded by.
Measured title only, in the site's categories (what a request shows), on two
sets the model never saw (--score):

    the 1,088-bill held-out half of 2025-2026      margin >= 6
        2025-2026's other half alone (before)         40% given one, 77.1% right
        that half x3 and every archived term          60% given one, 77.1% right
    2023-2024's 1,959 bills, trained without them   margin >= 6
        2025-2026 alone (before)                      41% given one, 80.5% right
        2025-2026 x3 and every other term             60% given one, 81.6% right

The weight was chosen on the first set (1, 2, 3, 5, 8 tried: 3 kept the first
set's accuracy and gave the most coverage that did) and held on the second.
Tried and left out, so they are not tried again: the archive from 2013 alone
(no better than all of it); the newest earlier bill of the identical title
(build_lsrs.title_key) taking its code (74% right on the 73 held-out bills that
have one, no better than the model, and no help beside it: of the six where the
two disagree, each was right three times); and keeping a topic where the
2025-2026-only model clears the threshold and agrees with this one's first
choice (four points more coverage, but those extra answers were 67% right).
Where the past tables are not on the machine (db/past), the model learns from
the current term alone, as before, and build_lsrs says so.

BELOW THE THRESHOLD A REQUEST IS MISCELLANEOUS (the owner, 14 November 2026:
"assign topics not yet assigned to misc"), as an archived bill below topics.py's
threshold is. It is never a guess at a named topic: below the threshold the
model is guessing, and a wrong topic is worse than none -- a reader filtering
by Elections who finds a request about something else has been misled
(topics.py, the same reasoning). So the Topic filter lists every request, the
ones the title does not place under Miscellaneous, and a card or a request's
page prints no topic for those, as a bill's prints none for the topic model's
Miscellaneous (app.js cardTopic). Until that day a request below the threshold
had no topic at all, and the filter could not find it.

WHAT COULD PLACE THEM, MEASURED (16 November 2026, the matcher polish the
owner queued). 178 of the 492 requests of 15 November are Miscellaneous, and
nothing their titles give places any of them as well as the 314 are placed
(77.1% and 81.6% right on the two sets above). --score prints, beneath the
threshold: margin 5 to 6, 62.5% and 68.1% right; 4 to 5, 46.3% and 55.7%;
the official topic of the newest earlier bill of the identical title, 55.0%
of 20 and 58.8% of 51. By the model's first choice, no topic held on both
sets and on three more terms scored the same way (2017-2018 to 2021-2022,
each trained without itself): Energy and Utilities, right on 20 of 24 on the
two, was right on 1 of 9 on the three; Employment, the nearest (38 of 46 at a
margin of 2 or more over the five), would have placed 3 requests and was found
by looking at the sets it would be scored on. So they stay Miscellaneous, and
--score says why each time it is run.

TWO TITLE RULES FIRST, the site's own and exact: a study (topic_model.is_study)
is Study Committees and Commissions, and a housing title (is_housing) is
Housing, as they are for every bill.

THE SITE'S CATEGORY, NEVER A NEW ONE. The model answers in the General Court's
own names; topic_vocabulary.vocabulary_of turns each into the category the site
shows (the folds, the renamed name, the two split in two), the one path every
term's topics take. A name the site retired comes out as None and the request is
Miscellaneous. THE TWO SPLIT IN TWO (17 November 2026, topic_model.SPLITS) are
split for a request by the title half of their rule, a request having no text
to say which statutes it changes: a Crimes answer whose title names prisons,
jails, inmates, prisoners, parole, probation or corrections is Corrections, and
a Property answer whose title names personal property, unclaimed property and
the like is Personal Property. Nothing here is retrained for them: the model
answers the General Court's name, as it always has, and is measured in it.
CANNABIS (17 November 2026, topic_model.cannabis_topic) is filed by the title
for a request and a bill alike: whatever the model answers, a title whose first
subject is cannabis is Cannabis, but a constitutional amendment's or a study's.
A CONSTITUTIONAL AMENDMENT IS NOT A TOPIC (the owner, 18 November 2026): the
model does not learn CACR, so a CACR request takes the topic its title's
subject gives, as a CACR bill does.

THE OWNER'S OWN WORD, OVER THE TITLE'S (24 November 2026). The owner asked
for the requests the title leaves Miscellaneous to go on the bench "with your
best guess so I can judge them". The guess is the claim on a topic card and
never reaches the site by itself; her verdict, once she has merged it into
review/checked.jsonl (bench_pull.py), is the request's topic: the guess where
she said it is right, the topic she chose instead where she said it is wrong
and named one, read through the site's vocabulary where she chose a General
Court name (owner_topics, owner_assign). `topic_by` says "owner". Her line
alone counts (bench_ledger.who "hand"); a contributor's answer, merged or not,
changes no request's topic. Unsure, or wrong with nothing named, changes
nothing.

WHAT IS WRITTEN. `topic` and `topic_by = "title"` on the row of every request
not yet a bill: the topic its title gives, or Miscellaneous. The card and the
page print the topic by its name alone, as a bill's (the owner, 14 November
2026: "remove the topic from title label"). When the request is filed as a
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
import re

import topics

# A margin in the model's log space: 6 gave 77% right (in the site's categories)
# on a held-out half at 60% coverage, title only (the docstring). A judgement,
# to be argued with from the bench like topics.THRESHOLD.
THRESHOLD = 6.0
# The current term's labels counted this many times beside the archive's (the
# docstring: chosen on one held-out set, held on another).
CURRENT_WEIGHT = 3
# What topic_by says: the topic is the title's, not the General Court's.
BY = "title"
# What topic_by says where the owner judged it on the bench (owner_assign).
OWNER_BY = "owner"
# A request's topic card on the bench (the manager's pack of 24 November 2026):
# "topic|2027 requests|LSR 2027-0123", the request's number last.
REQUEST_CARD = re.compile(r"^topic\|(\d{4}) requests\|(LSR \d{4}-\d{4})$")
# A request the title does not place (the docstring).
MISC = topics.MISC


def titles_only(rec):
    """A record as the title-only model sees it: the title and the subject."""
    return {"title": rec.get("title") or "", "subject": rec.get("subject") or ""}


def archived_official(bills, subjects=None, codes=None, skip=()):
    """[(bill, record)] for every archived bill the General Court's own code names,
    titles only: official_topics.adopt on a copy of the archived terms (data/bills.json
    carries a subject for the current term alone), so `bills` is never changed. A term in
    `skip` is left out (a held-out one). Empty where the past tables are not on this
    machine. `subjects` is data/subjects.json's {code: {"name"}}; `codes` is
    official_topics.read_codes()'s, read when not given."""
    import official_topics as OT
    cur = topics.LABELLED_TERM
    arch = {t: {b: dict(r) for b, r in recs.items()} for t, recs in bills.items()
            if t != cur and t not in skip}
    if not arch:
        return []
    if subjects is None:
        subjects = (json.loads(topics.SUBJECTS.read_text(encoding="utf-8"))
                    if topics.SUBJECTS.exists() else {})
    OT.adopt({**arch, cur: {}}, subjects, current=cur, codes=codes)
    return [(b, titles_only(r)) for t in sorted(arch) for b, r in sorted(arch[t].items())
            if r.get("subject") and r.get("subject_source") == "general court"]


def train_on(bills, subjects=None, codes=None):
    """The title-only model, from {term: {bill: record}} (data/bills.json): the term
    the General Court labelled, CURRENT_WEIGHT times, and every archived bill its
    official code names (archived_official). None where there is neither. The model
    says what it learned from in model["from"]."""
    own = [(b, titles_only(r)) for b, r in topics.labelled(bills)]
    past = archived_official(bills, subjects, codes)
    # A constitutional amendment is not learned as one (the owner, 18 November
    # 2026: CACR is retired as a topic, topic_model.RETIRED), so a CACR request
    # is answered by its subject, as the topic model answers a CACR bill.
    rows = [x for x in own * CURRENT_WEIGHT + past if x[1]["subject"] != "CACR"]
    if not rows:
        return None
    model = topics.train(rows)
    model["from"] = {"current": len(own), "archived": len(past)}
    return model


def topic_of(model, title, site_name=None):
    """(the site's topic for a request titled `title`, or "" where none is
    confident; the margin). `site_name` is topic_vocabulary.vocabulary_of, passed
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
    import topic_vocabulary
    return lambda s, rec: topic_vocabulary.vocabulary_of(s, rec, "")


def assign(rows, model, site_name=None):
    """Put `topic` and `topic_by` on each request row: the topic its title
    gives, or Miscellaneous where it gives none (the docstring). Returns
    {topic: n}, Miscellaneous among them. A row that is already a bill (it has
    `introduced`) is left alone: its topic is the bill's."""
    got = collections.Counter()
    fn = site_name or _vocabulary_of()
    for r in rows:
        if r.get("introduced"):
            continue
        t, _m = topic_of(model, r.get("title") or "", fn)
        r["topic"], r["topic_by"] = t or MISC, BY
        got[r["topic"]] += 1
    return dict(got)


def owner_topics(path=None):
    """{request number ("LSR 2027-0123"): the topic the owner gave it on the bench}, from
    the bench's ledger (review/checked.jsonl, read by bench_ledger's rules): for each
    request's topic card, the line that counts, where it is hers -- its claim where she
    said correct, the better topic she named where she said wrong. A contributor's line,
    unsure, and wrong with no topic named give nothing. {} where the ledger is not here."""
    import bench_ledger as BL
    p = Path(path) if path else _paths.ROOT / BL.LEDGER
    if not p.exists():
        return {}
    out = {}
    for (kind, key), lines in BL.judged(p).items():
        m = REQUEST_CARD.match(str(key or ""))
        if kind != "topic" or not m or not lines:
            continue
        last = lines[-1]
        if BL.who(last) != "hand":
            continue
        verdict = last.get("verdict")
        topic = ((last.get("shown") or {}).get("topic") if verdict == "correct" else
                 (last.get("fields") or {}).get("better_topic") if verdict == "wrong" else None)
        if topic and str(topic).strip():
            out[m.group(2)] = str(topic).strip()
    return out


def owner_assign(rows, judged, names=None, site_name=None):
    """Give each request row the owner judged (owner_topics) her topic, `topic_by`
    OWNER_BY: as she gave it where it is one of the site's own topics (`names`,
    tag_rules.known_topics), and through the site's vocabulary where it is a General Court
    name (vocabulary_of, with the request's title). A name the vocabulary retires, and a
    row already a bill, are left as they were. Returns how many rows took hers."""
    if not judged:
        return 0
    if names is None:
        import tag_rules
        names = set(tag_rules.known_topics())
    fn = site_name or _vocabulary_of()
    n = 0
    for r in rows:
        if r.get("introduced") or r.get("n") not in judged:
            continue
        t = judged[r["n"]]
        if t not in names:
            t = fn(t, {"title": r.get("title") or "", "subject": "", "bill": ""}) or ""
        if t:
            r["topic"], r["topic_by"] = t, OWNER_BY
            n += 1
    return n


def _scored(model, test, site):
    """[(margin, right)] for each held-out (bill, record), right in the site's
    categories (what a request shows); a title with nothing the model knows has no
    margin."""
    out = []
    for bid, r in test:
        rec = {"title": r.get("title") or "", "subject": "", "bill": bid}
        ranked = topics.rank(model, rec)
        known = any(w in model["vocab"] for w in topics.tokens(rec))
        gold = site(r["subject"], {**rec, "subject": r["subject"]})
        out.append(((ranked[0][1] - ranked[1][1]) if known else -1.0,
                    bool(gold) and site(ranked[0][0], rec) == gold))
    return out


def below(got, threshold=THRESHOLD, bands=((5, 6), (4, 5), (2, 4), (0, 2))):
    """[(lo, hi, right, n)]: the held-out answers beneath the threshold by margin band,
    what lowering it would place and how many of those would be right. `got` is
    _scored's [(margin, right)]; a title with nothing the model knows is in no band."""
    out = []
    for lo, hi in bands:
        hi = min(hi, threshold)
        band = [ok for m, ok in got if lo <= m < hi]
        out.append((lo, hi, sum(band), len(band)))
    return out


def same_title(rows, test, got, site, threshold=THRESHOLD):
    """(right, n): beneath the threshold, how often the official topic of the newest
    training bill of the identical title (build_lsrs.title_key) is the held-out bill's
    own. `rows` are the training (bill, record) pairs, oldest term first, so the newest
    of a title is the one kept; `test` and `got` are _scored's input and answer, in step."""
    import build_lsrs
    newest = {}
    for _b, r in rows:
        k = build_lsrs.title_key(r.get("title"))
        if k:
            newest[k] = r["subject"]
    right = n = 0
    for (bid, r), (m, _ok) in zip(test, got):
        k = build_lsrs.title_key(r.get("title"))
        if m < threshold and k in newest:
            rec = {"title": r.get("title") or "", "subject": "", "bill": bid}
            gold = site(r["subject"], {**rec, "subject": r["subject"]})
            n += 1
            right += bool(gold) and site(newest[k], rec) == gold
    return right, n


def score():
    """Held-out accuracy of the title-only model on two sets it never saw (the
    docstring's table): 2025-2026's held-out half (the half topics.split_half marks 1)
    and 2023-2024's bills; each against the model as it was, the current term's labels
    alone. Then, for the model build_lsrs trains, what the bills beneath the threshold
    would give (below, same_title: the docstring's WHAT COULD PLACE THEM)."""
    bills = topics.load()
    site = _vocabulary_of()
    lab = [(b, titles_only(r)) for b, r in topics.labelled(bills)]
    half = [x for x in lab if topics.split_half(x[0]) == 0]
    test1 = [x for x in lab if topics.split_half(x[0]) == 1]
    past = archived_official(bills)
    if not past:
        print("  no past tables on this machine (db/past): the archive cannot be scored")
    other = archived_official(bills, skip=("2023-2024",))
    import official_topics as OT
    held = {"2023-2024": {b: dict(r) for b, r in bills.get("2023-2024", {}).items()}}
    OT.adopt({**held, topics.LABELLED_TERM: {}}, json.loads(topics.SUBJECTS.read_text(encoding="utf-8"))
             if topics.SUBJECTS.exists() else {}, current=topics.LABELLED_TERM)
    test2 = [(b, r) for b, r in held["2023-2024"].items() if r.get("subject_source") == "general court"]
    sets = [(f"2025-2026's held-out half, {len(test1):,} bills", test1,
             [("the current term's other half alone", half),
              (f"that half x{CURRENT_WEIGHT} and every archived term", half * CURRENT_WEIGHT + past)], past + half),
            (f"2023-2024, {len(test2):,} bills, trained without them", test2,
             [("2025-2026 alone", lab),
              (f"2025-2026 x{CURRENT_WEIGHT} and every other term", lab * CURRENT_WEIGHT + other)], other + lab)]
    for name, test, models, oldest_first in sets:
        if not test:
            continue
        print(f"\n{name}, titles only, right in the site's categories:")
        print(f"  {'trained on':48}{'margin':>7}{'coverage':>10}{'right':>8}")
        for label, rows in models:
            got = _scored(topics.train(rows), test, site)
            for thr in (4, 6, 8):
                keep = [ok for m, ok in got if m >= thr]
                mark = "  <- THRESHOLD" if thr == THRESHOLD else ""
                print(f"  {label:48}{thr:>7}{100 * len(keep) / len(got):>9.0f}%"
                      f"{100 * sum(keep) / max(1, len(keep)):>7.1f}%{mark}")
        print(f"  beneath the threshold, {models[-1][0]}:")
        for lo, hi, right, n in below(got):
            print(f"    margin {lo:g} to {hi:g}: {n:>5} bills, {100 * right / max(1, n):5.1f}% right")
        right, n = same_title(oldest_first, test, got, site)
        print(f"    the official topic of an identical earlier title: {n:>5} bills, "
              f"{100 * right / max(1, n):5.1f}% right")
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
    if model:
        print(f"learned from {model['from']['current']:,} titles of the current term "
              f"(x{CURRENT_WEIGHT}) and {model['from']['archived']:,} archived titles with an official code")
    reqs = json.loads(Path(a.lsrs).read_text(encoding="utf-8"))
    rows = [{"title": r.get("title"), "n": r.get("lsr")} for r in reqs]
    tally = assign(rows, model)
    n = sum(c for t, c in tally.items() if t != MISC)
    print(f"{n} of {len(rows)} requests get a topic from the title "
          f"({100 * n / max(1, len(rows)):.0f}%); the other {tally.get(MISC, 0)} are {MISC}.")
    for t, c in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {c:>4}  {t}")
    if a.sample:
        rnd = random.Random(2026_11_12)
        for r in rnd.sample(rows, min(a.sample, len(rows))):
            print(f"{r['n']}  {r['topic']:38}  {r['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
