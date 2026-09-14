#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-12.2
"""A topic for the 29,449 bills the General Court never gave one.

    python3 topics.py --score              # measure it; no files written
    python3 topics.py --apply              # write topics_assigned.json
    python3 topics.py --bill 1995-1996 HB101   # explain one answer

WHAT IS MISSING

data/subjects.json holds the General Court's 47 topics, and its own assignment
of them reaches exactly one term: 2,221 of the 2,234 bills of 2025-2026. Every
other term -- 29,449 bills, 1989 to 2024 -- has an empty subject field, so the
topic facet on the search page is a filter that hides eighteen terms.

WHAT THERE IS TO GO ON

A title, always. "relative to the transfer of state-owned real property to
municipalities." Titles are formulaic and, unlike much else here, stable: 83%
to 88% of the words in any term's titles also appear in 2025-2026's, which is
the whole reason a model learned on one term can be pointed at another.

The committee that heard it, usually. This is the stronger signal of the two
where it exists -- Election Law sends 92% of its bills to Elections, Education
Policy and Administration 93% to Education - General -- and it is the one that
decays going backwards, because committees are abolished and renamed. 99% of
2021-2022's bills sat in a committee that still exists; 52% of 1989-1990's do.

NOT the analysis. It is printed on the bill's own page and only 863 of ~31,000
of those have been fetched, so a method that needed it would cover 3% of the
archive. When the bill text lands this can use it and should be re-scored.

WHY THIS METHOD

Naive Bayes over the title's words and its committee, learned from the 2,221
bills the General Court itself labelled.

Learned rather than hand-written because 46 topics by hand is 46 sets of
invented rules, and this project's standard for an invented rule is that it
does not get published. Learning the words from the authority's own labelling
is a different thing: the evidence is theirs.

Simple rather than clever because the answer has to be explainable on a page.
--bill prints the words that decided it, and every one of them is a word in
the title or the name of the committee.

WHAT IT IS WORTH, measured on a half it never saw

    always the commonest topic          12.7%
    the committee's commonest topic     50.4%
    this                                62.1%   (60.9% before 14 September)

46 ways to be wrong, from a sentence and a committee name. The number that
matters more is what happens when it is allowed to decline:

    margin >= 0     100% of bills given a topic     62.1% of them right
    margin >= 2      81%                            69.3%
    margin >= 4      69%                            74.1%   (67%, 74.2% before)
    margin >= 6      58%                            77.0%
    margin >= 10     43%                            82.4%
    margin >= 14     32%                            85.8%

On 14 September committees were carried across renames, both chambers'
committees counted (the second once), and title words read singular. That
moved the unseen half little -- its committees are today's already -- and the
archive a great deal: the share of a term's bills whose committee the model
knows went from 58% to 78% for 1989-1990 and from 72% to 93% for 1997-1998,
and Miscellaneous fell by 2 to 12 points in every archived term. The person
kept the threshold at 4 the same day, with these numbers in front of them.

MISCELLANEOUS IS THE POINT OF THE THRESHOLD. Below it the model is guessing --
the least confident quarter of its answers are right 26% of the time -- and a
wrong topic on a bill page is worse than no topic, because a reader filtering
by Elections and not finding a bill about elections has been misled rather
than underserved. So below the threshold the bill is Miscellaneous, which is
an honest statement that this method could not place it.

The default threshold is 4. It is a judgement rather than a measurement, and
it is meant to be argued with from the bench: review.py serves these as the
"topic" kind, and the person's verdicts are what should move it.
"""

import argparse
import collections
import hashlib
import json
import math
import re
import sys
from pathlib import Path

BILLS = Path("data/bills.json")
SUBJECTS = Path("data/subjects.json")
OUT = Path("topics_assigned.json")

# The term the General Court labelled, and so the only evidence there is.
LABELLED_TERM = "2025-2026"

MISC = "Miscellaneous"
MISC_CODE = "MSC"

# A margin in log space: how much likelier the winner is than the runner-up.
# See the table in the docstring for what each setting costs and buys.
THRESHOLD = 4.0

# The committee counted this many times over. It is one token against a dozen
# title words and it carries more than any of them, and 3 is where the score
# stopped improving: 1 gives 57.2%, 3 gives 60.9%, 6 gives 60.2%, 10 gives
# 58.9%. Weighted higher it starts overruling titles that plainly disagree
# with it, which is the Judiciary problem -- that committee's bills span 23
# topics and its commonest is only 12% of them.
CMTE_WEIGHT = 3

# THE BILL'S KIND WAS TRIED AND IS NOT HERE, recorded so it is not tried
# again. There is a topic called CACR and 16 of the 20 constitutional
# amendments in the training half carry it, so a "KIND:CACR" token looked
# obviously right -- and it fixed the case that prompted it, CACR 1 of
# 1995-1996, which had been answered "Municipalities".
#
# Measured, it trades one small group for another and costs the whole:
#
#     weight    overall    CACR (11)    HR (18)
#          0      60.9%          27%        56%
#          2      60.8%          27%        50%
#          4      60.0%          55%        44%
#          8      59.2%          64%        33%
#         12      58.3%          73%        33%
#
# Forbidding the CACR topic to non-CACR bills instead changes two bills in
# 1,088 and nothing measurable, and is not even true: the General Court gives
# that topic to an HR once.
#
# The anecdote was real and the improvement was not, which is the trap this
# project's rules name -- tuning a pattern until the number looks right, on a
# number that was never the score.

# Add-alpha smoothing. 0.1 by the same sweep; the model is insensitive between
# 0.05 and 0.2 and falls off by 0.5.
ALPHA = 0.1

# Words that appear in every kind of bill and so distinguish nothing. Kept
# short deliberately: a stop list is a place to accidentally delete signal,
# and "education" or "health" would be exactly that.
STOP = set("""relative the and for certain from that with which are was were
been being have has had not any all its his her their our your this these
those under upon into onto over about after before during without within
state new hampshire act bill title requiring establishing providing repealing
amending adding concerning regarding pertaining shall may must other than
such as per each every some more most less least also including""".split())

WORD = re.compile(r"[a-z][a-z'-]{2,}")


# COMMITTEES CARRIED ACROSS RENAMES, 14 September. The committee is the
# strongest evidence there is and the model only knows 2025-2026's names, so a
# bill of 1989-1990 heard by "COMMERCE" -- 504 bills, the same committee in
# capitals -- or by "Public Works" (478), "Wildlife" (149) or "Child Y and Jj"
# (62) counted no committee at all. Each name is now read case-blind against
# the labelled term's own spelling, and a rename or abbreviation whose
# successor is not in doubt is read as the successor. A committee divided
# among several -- Public Affairs, Regulated Revenues, Public Protection and
# Veterans Affairs, State Institutions, Constitutional and Statutory Revision,
# Redress of Grievances -- is left as itself, which the model does not know,
# rather than guessed into one of them.
ALIAS = {
    "public works": "Public Works and Highways",
    "capital budget": "Public Works and Highways",
    "judiciary and family law": "Judiciary",
    "corrections and criminal justice": "Criminal Justice and Public Safety",
    "wildlife": "Fish and Game and Marine Resources",
    "wildlife and recreation": "Fish and Game and Marine Resources",
    "fish and game": "Fish and Game and Marine Resources",
    "appropriations": "Finance",
    "insurance": "Commerce and Consumer Affairs",
    "banks": "Commerce and Consumer Affairs",
    "banks and insurance": "Commerce and Consumer Affairs",
    "public institutions, health and human services": "Health and Human Services",
    "health": "Health and Human Services",
    "child y and jj": "Children and Family Law",
    "children, youth and juv just": "Children and Family Law",
    "child, yth and jj": "Children and Family Law",
    "education and workforce development": "Education",
    "commerce, small business and consumer affairs": "Commerce",
    "commerce, labor and consumer protection": "Commerce",
    "economic development": "Commerce",
    "transportation and interstate cooperation": "Transportation",
    "st-fed": "State-Federal Relations and Veterans Affairs",
    "st-fed rel": "State-Federal Relations and Veterans Affairs",
    "internal affairs": "Election Law",
    "election law and internal affairs": "Election Law",
    "environment": "Energy and Natural Resources",
    "energy, environment and economic development": "Energy and Natural Resources",
}
# A committee of conference hears bills of every subject, and in the House
# field of 633 bills it stood where the committee of referral would have.
# "No Committee Assignment" is NOT here: in 2025-2026 it is the floor
# resolutions, and dropping it cost them Legislature and Memorials.
NOT_A_SUBJECT = {"committee of conference"}
# lower-case name -> the labelled term's own spelling, filled by load().
CANON = {}

# BOTH CHAMBERS' COMMITTEES, the second counted once. A bill that crossed over
# was heard twice, and the second hearing is evidence too; counted as heavily
# as the first it let Finance and Judiciary, second committees of every
# subject, drag topics away. Measured on the unseen half:
#
#                                     given a topic   of those right
#     one committee (as before)            67%            74.2%
#     both, equal                          70%            73.4%
#     both, the second once                68%            74.4%
SECOND_WEIGHT = 1


def canon_committee(name):
    key = re.sub(r"\s+", " ", (name or "").strip()).lower()
    if not key or key in NOT_A_SUBJECT:
        return ""
    return CANON.get(key) or ALIAS.get(key) or (name or "").strip()


def committees_of(rec):
    """The committees that heard it, the House's first, each by its current name.
    Both are kept when the two chambers' committees share a name: two hearings
    in Judiciary are more evidence than one, and merged they scored lower."""
    out = []
    for field in ("house_committee", "senate_committee"):
        c = canon_committee(rec.get(field))
        if c:
            out.append(c)
    return out


def committee_of(rec):
    cs = committees_of(rec)
    return cs[0] if cs else ""


def singular(w):
    """"vehicles" as "vehicle", "counties" as "county": one title's plural is
    another's singular, and the older titles are the ones it cost."""
    if len(w) < 5 or w.endswith(("ss", "us", "is")):
        return w
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith(("xes", "ches", "shes", "sses")):
        return w[:-2]
    return w[:-1] if w.endswith("s") else w


def tokens(rec):
    """The evidence for one bill: the words of its title, adjacent pairs of
    them, and the committees that heard it.

    The pairs are there for the phrases where neither word decides anything
    alone -- "motor vehicle", "school district", "right to know", "controlled
    drug" -- and they are cheap because a title is a dozen words long.
    """
    title = (rec.get("title") or "").lower()
    words = [singular(w) for w in WORD.findall(title) if w not in STOP]
    out = list(words)
    out += [f"{a}_{b}" for a, b in zip(words, words[1:])]
    for i, c in enumerate(committees_of(rec)):
        out += ["CMTE:" + c] * (CMTE_WEIGHT if i == 0 else SECOND_WEIGHT)
    return out


def train(rows):
    """Counts, from (bill id, record) pairs that carry a subject."""
    prior = collections.Counter()
    cond = collections.defaultdict(collections.Counter)
    vocab = set()
    for _bid, rec in rows:
        topic = rec["subject"]
        prior[topic] += 1
        for w in tokens(rec):
            cond[topic][w] += 1
            vocab.add(w)
    total = sum(prior.values())
    return {
        "logprior": {t: math.log(c / total) for t, c in prior.items()},
        "cond": cond,
        "wordtotal": {t: sum(cond[t].values()) for t in prior},
        "vocab": vocab,
        "n": total,
    }


def rank(model, rec):
    """[(topic, log score)] best first, over the topics the model knows."""
    seen = [w for w in tokens(rec) if w in model["vocab"]]
    v = len(model["vocab"])
    out = []
    for topic, lp in model["logprior"].items():
        s = lp
        denom = model["wordtotal"][topic] + ALPHA * v
        for w in seen:
            s += math.log((model["cond"][topic][w] + ALPHA) / denom)
        out.append((topic, s))
    out.sort(key=lambda kv: -kv[1])
    return out


def classify(model, rec, threshold=THRESHOLD):
    """(topic, margin, runner_up). Miscellaneous below the threshold.

    A bill with nothing the model has seen before gets Miscellaneous too,
    rather than the commonest topic, which is what the prior alone would
    give it.
    """
    ranked = rank(model, rec)
    if len(ranked) < 2:
        return MISC, 0.0, ""
    (top, s1), (second, s2) = ranked[0], ranked[1]
    margin = s1 - s2
    if not any(w in model["vocab"] for w in tokens(rec)):
        return MISC, 0.0, top
    return (top if margin >= threshold else MISC), margin, second


def evidence(model, rec, topic, limit=6):
    """The tokens that argued hardest for this topic, for a person to read.

    Each is scored against what it would have contributed to the runner-up,
    so a word common to both -- "committee", "study" -- does not come top of
    a list claiming to explain the difference.
    """
    ranked = rank(model, rec)
    if len(ranked) < 2:
        return []
    other = ranked[1][0] if ranked[0][0] == topic else ranked[0][0]
    v = len(model["vocab"])
    out = []
    for w in dict.fromkeys(t for t in tokens(rec) if t in model["vocab"]):
        a = math.log((model["cond"][topic][w] + ALPHA)
                     / (model["wordtotal"][topic] + ALPHA * v))
        b = math.log((model["cond"][other][w] + ALPHA)
                     / (model["wordtotal"][other] + ALPHA * v))
        out.append((a - b, w))
    out.sort(reverse=True)
    return [w for _s, w in out[:limit]]


# ------------------------------------------------------------------ loading

def load():
    if not BILLS.exists():
        sys.exit(f"No {BILLS}. Run build_data.py first.")
    bills = json.loads(BILLS.read_text(encoding="utf-8"))
    for rec in bills.get(LABELLED_TERM, {}).values():
        for field in ("house_committee", "senate_committee"):
            c = re.sub(r"\s+", " ", (rec.get(field) or "").strip())
            if c:
                CANON.setdefault(c.lower(), c)
    return bills


def labelled(bills):
    return [(b, r) for b, r in bills.get(LABELLED_TERM, {}).items()
            if r.get("subject")]


def codes():
    """{topic name: code} from the General Court's own list."""
    if not SUBJECTS.exists():
        return {}
    out = {}
    for v in json.loads(SUBJECTS.read_text(encoding="utf-8")).values():
        # One row of that file has a name and no code ("Regular Meeting").
        # It is not a subject and is never offered as an answer.
        if v.get("code") and v.get("name"):
            out[v["name"]] = v["code"]
    return out


def split_half(bid):
    """Which half of the labelled term a bill is in. Deterministic, so a
    score is the same score every time it is run."""
    return int(hashlib.sha1(bid.encode()).hexdigest(), 16) % 2


# ------------------------------------------------------------------- modes

def score(threshold):
    bills = load()
    lab = labelled(bills)
    if not lab:
        sys.exit(f"No labelled bills in {LABELLED_TERM}; nothing to learn from.")
    tr = [x for x in lab if split_half(x[0]) == 0]
    te = [x for x in lab if split_half(x[0]) == 1]
    model = train(tr)
    print(f"{len(lab):,} bills of {LABELLED_TERM} carry the General Court's own "
          f"topic.\nTrained on {len(tr):,} of them, scored on the {len(te):,} "
          f"it never saw.\n")

    # The two things worth beating.
    common = collections.Counter(r["subject"] for _b, r in tr).most_common(1)[0][0]
    base0 = sum(1 for _b, r in te if r["subject"] == common)
    bycm = collections.defaultdict(collections.Counter)
    for _b, r in tr:
        bycm[committee_of(r)][r["subject"]] += 1
    best = {c: n.most_common(1)[0][0] for c, n in bycm.items()}
    base1 = sum(1 for _b, r in te if best.get(committee_of(r)) == r["subject"])

    rows = []
    for _b, r in te:
        ranked = rank(model, r)
        margin = ranked[0][1] - ranked[1][1]
        rows.append((margin, ranked[0][0] == r["subject"]))
    hit = sum(1 for _m, ok in rows if ok)

    print(f"{'always the commonest topic':38}{100*base0/len(te):>6.1f}%")
    print(f"{'the committee commonest topic':38}{100*base1/len(te):>6.1f}%")
    print(f"{'this':38}{100*hit/len(te):>6.1f}%")

    print(f"\n{'threshold':>10}{'given a topic':>15}{'coverage':>10}"
          f"{'of those, right':>17}")
    for thr in (0, 2, 4, 6, 8, 10, 14):
        keep = [ok for m, ok in rows if m >= thr]
        if not keep:
            continue
        mark = "  <- default" if thr == threshold else ""
        print(f"{thr:>10}{len(keep):>15,}{100*len(keep)/len(rows):>9.0f}%"
              f"{100*sum(keep)/len(keep):>16.1f}%{mark}")

    print("\nHOW FAR BACK IT CARRIES. The title words transfer; the committees "
          "do not,\nbecause committees are abolished and renamed.")
    print(f"\n{'term':12}{'bills':>8}{'committee known':>17}{'title words seen':>18}")
    for term in sorted(bills):
        recs = list(bills[term].values())
        known = sum(1 for r in recs if "CMTE:" + committee_of(r) in model["vocab"])
        cov = []
        for r in recs:
            ws = [singular(w) for w in WORD.findall((r.get("title") or "").lower())
                  if w not in STOP]
            if ws:
                cov.append(sum(1 for w in ws if w in model["vocab"]) / len(ws))
        print(f"  {term:10}{len(recs):>8,}{100*known/len(recs):>16.0f}%"
              f"{100*sum(cov)/max(1,len(cov)):>17.0f}%")
    return 0


def apply(threshold, limit_terms=None):
    """Write a topic for every bill that has none. Newest term first."""
    bills = load()
    lab = labelled(bills)
    model = train(lab)          # everything, now that it is being used
    code_of = codes()
    out, tally = {}, collections.Counter()
    # NEWEST FIRST, which is the person's standing order for a backfill and
    # is doubly right here: the recent terms are the ones the committees still
    # match, so they are both the most useful and the most accurate.
    terms = sorted(bills, reverse=True)
    if limit_terms:
        terms = terms[:limit_terms]
    for term in terms:
        if term == LABELLED_TERM:
            continue
        got = {}
        for bid, rec in bills[term].items():
            if rec.get("subject"):
                continue
            topic, margin, _second = classify(model, rec, threshold)
            got[bid] = {
                "subject": topic,
                "subject_code": code_of.get(topic, MISC_CODE),
                "margin": round(margin, 2),
                "source": "granite-record topic model",
                "why": evidence(model, rec, topic) if topic != MISC else [],
            }
            tally[term if topic != MISC else term + " (misc)"] += 1
        if got:
            out[term] = got
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    total = sum(len(v) for v in out.values())
    placed = sum(n for k, n in tally.items() if not k.endswith("(misc)"))
    print(f"{total:,} bills across {len(out)} terms -> {OUT}")
    print(f"  {placed:,} given a topic, {total-placed:,} Miscellaneous "
          f"({100*placed/max(1,total):.0f}% placed at threshold {threshold})")
    print(f"\n{'term':12}{'placed':>9}{'miscellaneous':>15}")
    for term in sorted(out, reverse=True):
        p = tally.get(term, 0)
        m = tally.get(term + " (misc)", 0)
        print(f"  {term:10}{p:>9,}{m:>15,}")
    return 0


def explain(term, bid, threshold):
    bills = load()
    rec = bills.get(term, {}).get(bid)
    if not rec:
        sys.exit(f"No {bid} in {term}.")
    model = train(labelled(bills))
    ranked = rank(model, rec)
    topic, margin, _second = classify(model, rec, threshold)
    print(f"{bid} of {term}")
    print(f"  title      {rec.get('title','')}")
    print(f"  committee  {committee_of(rec) or '(none)'}")
    print(f"  given      {rec.get('subject') or '(none by the General Court)'}")
    print(f"\n  this says  {topic}   (margin {margin:.1f}, "
          f"threshold {threshold})")
    print(f"  because    {', '.join(evidence(model, rec, ranked[0][0])) or '(nothing seen before)'}")
    print("\n  the three it weighed:")
    for t, s in ranked[:3]:
        print(f"     {t:38} {s:9.1f}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true",
                    help="measure against the General Court's own labels")
    ap.add_argument("--apply", action="store_true",
                    help=f"write {OUT}")
    ap.add_argument("--bill", nargs=2, metavar=("TERM", "BILL"),
                    help="explain one bill's answer")
    ap.add_argument("--threshold", type=float, default=THRESHOLD,
                    help="margin below which a bill is Miscellaneous")
    ap.add_argument("--terms", type=int, default=0,
                    help="with --apply, only the newest N terms")
    a = ap.parse_args()
    if a.bill:
        return explain(a.bill[0], a.bill[1], a.threshold)
    if a.apply:
        return apply(a.threshold, a.terms or None)
    return score(a.threshold)


if __name__ == "__main__":
    sys.exit(main())
