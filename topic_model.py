#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-16.4
"""A topic for the 29,449 bills the General Court never gave one -- second model.

    python3 topic_model.py --apply              # write topics_assigned.json
    python3 topic_model.py --bill 1995-1996 HB101   # explain one answer

THIS SITS BESIDE topics.py, IT DOES NOT REPLACE IT. It imports that module for
its stop list, its singular(), its committee canonicalisation and its loaders,
so topics.py stays where it is and stays runnable. What changes is the
classifier and, through build_all.py, which of the two writes
topics_assigned.json. The file written is byte-for-byte the same SHAPE as
before -- build_site_v2.merge_guessed_topics and review.py read it unchanged.

THREE DIFFERENCES FROM topics.py

1.  EVIDENCE, NOT LIKELIHOOD. topics.py is multinomial naive Bayes: it adds
    log P(feature | topic). This adds log P(topic | feature) / P(topic) -- the
    same arithmetic rearranged, but smoothed toward the prior PER FEATURE
    rather than toward a flat vocabulary. A feature whose topics look like the
    prior contributes ~0 instead of a large number that happens to cancel.
    That is what neutralises Judiciary (23 topics, commonest 12%) without
    neutralising Election Law (92% Elections), and RSA 541-A (rulemaking,
    every subject) without neutralising RSA 659 (93% Elections).

2.  THE BILL TEXT, WHERE THERE IS ANY. The ANALYSIS paragraph the drafters
    write, and the RSA chapters the bill amends. Available for 97-100% of
    2017-2026 and ~1% before 2013, so the model is tuned twice -- once with
    those families, once without -- and a bill is answered under whichever
    regime it is in. The archive is answered by the no-text weights. This is
    the thing topics.py's own docstring said it could not do: "only 863 of
    ~31,000 of those have been fetched ... when the bill text lands this can
    use it and should be re-scored."

3.  A CALIBRATED DECISION. topics.py declines below a log-margin of 4. Margins
    from an independence assumption are not comparable between a three-word
    title and a 600-word analysis, so this declines on a temperature-scaled
    probability instead, with a floor fitted per regime.

WHAT IT IS WORTH, on topics.py's own deterministic half/half split -- 1,133
trained on, 1,088 never seen -- in the General Court's own 46 categories, so
the numbers below sit beside the baseline's without adjustment.

                         argmax   at 69.5% coverage   no-twin argmax
    topics.py             62.1%        74.1%              61.2%
    this, with text       67.2%        79.5%              66.3%
    this, without text    62.8%        74.2%              61.8%

The "with text" row is what the five terms from 2017 get; the "without text"
row is what the fourteen terms from 1989 to 2016 get, measured by blanking the
text on the same 1,088 bills. IT IS A TIE WITHOUT TEXT. What changes there is
where the accuracy sits:

    accuracy by how many training bills the gold category has
                     0-9    10-24   25-59   60-149
    topics.py         26%     45%     67%     79%
    this, text        42%     54%     74%     76%
    this, no text     36%     47%     66%     77%

The starved categories go up and the largest band goes down by 2 to 3 points.

MEASURED AND REJECTED, so they are not tried again:

  * logistic regression over exactly these features -- 63.3% against 66.1% on
    the same folds, and 100% training accuracy at every regularisation tried.
    1,133 examples over 46 classes is not enough to fit discriminatively.
  * a one-versus-one run-off between the top two. It loses monotonically from
    the smallest weight upward: 66.1% -> 64.9% -> 64.0% -> 63.1%.
  * the bill's kind, which topics.py also rejected for the same reason. Here
    the shrinkage found it by itself: m[k] went to 200, the largest offered,
    at all four fold sizes tried, which is the estimator saying the feature
    carries nothing.
  * the flags (fiscal note, local impact). They exist in the labelled term and
    in no other, so learning on them would have raised the held-out number and
    done nothing whatever for the archive.

TWO LABEL SPACES, AND WHY --apply USES A BY DEFAULT

  A  the General Court's own 46 categories, untouched. Every answer is a name
     from data/subjects.json and carries that list's own code. This is the
     space the table above was measured in, and the only one directly
     comparable with topics.py.
  B  the site's own vocabulary: five starved categories folded into their
     parents, Regular Meeting retired, and Housing and Study Committees and
     Commissions added. build_all.py runs `--apply --space B`, so this is
     what the site publishes.

     The objection that kept it off is answered rather than waived. It was
     that two names would enter the archive's eighteen terms which
     data/subjects.json has no code for, while 2025-2026 kept the General
     Court's own labels, so a reader filtering Parks and Recreation would find
     the current term and none of the archive. build_site_v2.unify_vocabulary
     closes that by folding every term including the labelled one, so one
     vocabulary covers all nineteen; ADDED_CODES below gives the two additions
     their codes on both sides.

     Measured on the same held-out half, both models trained on the training
     half only: space A 609/1,087 = 56.0% with 28.9% declined to
     Miscellaneous; space B 664/1,087 = 61.1% with 25.1% declined. It reaches
     654 Housing bills and 2,103 Study bills across the whole record.

MISCELLANEOUS IS STILL THE POINT OF THE FLOOR. Below it the model is guessing,
and a wrong topic on a bill page is worse than no topic, because a reader
filtering by Elections and not finding a bill about elections has been misled
rather than underserved.

NUMPY. This module needs numpy; topics.py does not. Importing it costs about
0.11s per process, against a --apply run of several minutes, so the pipeline
cannot feel it.
"""

import argparse
import collections
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
# topics.py and build_data.py address their files relative to the working
# folder, so this module has to be standing in the repository to read them.
# build_all.py already runs its steps from there; this is for a run that is not.
if not (Path("data") / "bills.json").exists() and (REPO / "data" / "bills.json").exists():
    os.chdir(REPO)

import topics as base   # noqa: E402  (the baseline, imported not replaced)

LABELLED_TERM = base.LABELLED_TERM
MISC = base.MISC
MISC_CODE = base.MISC_CODE
OUT = Path("topics_assigned.json")

# The provenance string build_site_v2 and review.py have always seen. It says
# the site's model answered, as against the General Court; WHICH model is a
# question for this file's version stamp, not for 29,449 records.
SOURCE = "granite-record topic model"

# ----------------------------------------------------------------- vocabulary

# Space B only. See the docstring: proposed, not the default.
FOLD = {
    "Workers' Comp and Unemployment": "Employment",
    "Parks and Recreation": "Environment - Conservation",
    "Waters and Navigation": "Environment - Conservation",
    "Agency Appropriations": "State Government",
    "Corporations/Partnerships": "Business and Industry",
}
RETIRED = {"Regular Meeting"}

HOUSING = "Housing"
STUDY = "Study Committees and Commissions"

# The two names data/subjects.json has no code for, because they are this
# site's additions rather than the General Court's. Defined here, beside the
# names themselves, and imported by build_site_v2.unify_vocabulary so the two
# cannot drift apart.
#
# apply() needs them for a reason that is easy to miss: it writes
# `code_of.get(topic) or MISC_CODE`, and code_of is the General Court's own
# list -- so in space B every Housing bill would have been filed under the
# MISCELLANEOUS code while displaying the name Housing. unify_vocabulary would
# not have caught it either, because it only rewrites a code when it changes
# the NAME, and the name was already right.
ADDED_CODES = {HOUSING: "HSG", STUDY: "STU"}

# The General Court's own definition of a housing bill: the 103 bills its
# House Housing committee heard in 2025-2026. Nothing here is hand-written --
# the seed set is a committee docket.
HOUSING_COMMITTEE = "housing"

# AND A TITLE RULE, BECAUSE THE COMMITTEE DID NOT EXIST BEFORE 2025. Learning
# housing from the House Housing committee's own docket is the better
# definition where that committee sits -- it is the General Court's opinion
# rather than ours -- but it reaches one term of nineteen. Measured without
# this rule, recall in the archive falls from 90% to 57% and the yield to
# 4-14 bills a year rather than 15-24.
#
# So a bill is housing if the Housing committee heard it, OR if its title says
# so in the vocabulary the General Court has used for thirty-seven years.
# Measured over all 33,683 titles: 638 bills, 16.8 a year, running 10.0 in
# 1999-2000 to 35.5 in 2025-2026 -- the rise is real, housing having become
# the subject it is. Twenty sampled titles were read one by one and all twenty
# are housing bills: landlord and tenant actions, manufactured-housing liens,
# accessory dwelling units, condominium liens, rent increases, the definition
# of a short-term rental.
#
# TWO PHRASES ARE DELIBERATELY ABSENT. "homeless" catches welfare -- "a pilot
# program to provide homeless people with free meals" is not a housing bill --
# and "foreclosure" is a lending matter that belongs with Banking. Both were
# in the list this rule was drawn from and both were dropped after reading
# what they caught.
#
# THE LEADING \b IS LOAD-BEARING. Without it
# "rental" matches inside "parental" and "rents" inside "grandparents", so
# 252 bills were filed under Housing that have nothing to do with it -- almost
# all of them school choice and parental rights: "allowing parents to send
# their children to any school district they choose", "relative to
# grandparents' visitation rights", "relative to parental consent". "tenant"
# matched inside "lieutenant" and "housing" inside "warehousing" as well.
#
# There is deliberately NO trailing \b. "evict" has to reach "eviction" and
# "evicted", and "rental" has to reach "rentals"; a right-hand boundary would
# cut exactly the words this is for.
HOUSING_RE = re.compile(
    r"\b(?:"
    r"housing|landlord|tenant|eviction|evict"
    r"|accessory dwelling|manufactured housing|manufactured home|mobile home"
    r"|condominium|short-?term rental|residential lease"
    r"|rental|rents"
    r")", re.I)


def is_housing(title):
    return bool(HOUSING_RE.search(title or ""))

# THE ONE HAND-WRITTEN RULE IN THIS FILE, and it is a title template rather
# than a judgement about subject matter. The General Court has never labelled
# a study bill, so there is nothing to learn from; what there is instead is a
# formula its drafters have used for thirty-seven years. Two guards, both
# arrived at by reading matches rather than by scoring:
#
#   the article guard  "the sweepstakes commission to study the operation of
#                      bingo games" is a direction to an agency, not a study
#                      committee, so the noun must be preceded by an article
#                      or a body-naming adjective.
#   the position guard  in 269 titles the study committee is the second half
#                      of a compound bill -- "imposing a moratorium on
#                      property reassessments ... and establishing a
#                      commission to study" -- whose business is the first
#                      half. Requiring the phrase inside the first 45
#                      characters keeps the 2,103 whose business it is.
#
# 2,103 bills of 33,683, 55 a year. It fires only in space B, which is the
# only space that has a category for it to answer.
_ART = (r"(?:a|an|the|another|joint|legislative|independent|permanent|citizens?|"
        r"citizen's|house|senate|interim|special|bipartisan|temporary|new)")
_MOD = (r"(?:house|senate|joint|legislative|independent|permanent|special|"
        r"interim|bipartisan|oversight|temporary|state|advisory)")
STUDY_RE = re.compile(
    rf"\b{_ART}\s+(?:and\s+)?(?:{_MOD}\s+(?:and\s+)?){{0,3}}"
    rf"(?:committee|commission|task\s+force)\s+to\s+(?:study|examine|investigate)\b"
    rf"|\bstudy\s+(?:committee|commission)\b", re.I)
STUDY_WITHIN = 45


def is_study(title):
    t = NEWTITLE.sub("", title or "")
    m = STUDY_RE.search(t)
    return bool(m) and m.start() <= STUDY_WITHIN

# ------------------------------------------------------------------- features

WORD = re.compile(r"[a-z][a-z'-]{2,}")
RSA_RE = re.compile(r"\bRSA\s+(\d{1,3}[-‑]?[A-Za-z]{0,2})(:(\d{1,3}[-a-z]{0,3}))?",
                    re.I)
# "(New Title)", "(Second New Title)": a clerk's marker, not subject matter.
NEWTITLE = re.compile(r"^\s*\((?:[0-9A-Za-z]+\s+)?New Title\)\s*", re.I)
# THE CHAPTERS THE BILL ACTUALLY CHANGES, as against those it mentions in
# passing. "shall be exempt from RSA 91-A" is boilerplate in bills of every
# subject; "Amend RSA 674:33" is the bill's business.
OPERATIVE = re.compile(
    r"(?:Amend(?:ing)?|Repealing|repealed)\s+RSA\s+(\d{1,3}[-‑]?[A-Za-z]{0,2})"
    r"|RSA\s+(\d{1,3}[-‑]?[A-Za-z]{0,2})[^.\n]{0,40}?\bis\s+repealed"
    r"|new\s+(?:chapter|subdivision|section|paragraph)[^.\n]{0,70}?"
    r"RSA\s+(\d{1,3}[-‑]?[A-Za-z]{0,2})", re.I)
# "1 Disposal of Highway, Federal, or Turnpike Funded Real Estate." -- the
# drafter's own heading for each section of the bill, and a better summary of
# what it touches than any sentence in the body.
HEADING = re.compile(r"(?m)^\s*(\d{1,3})\s+([A-Z][^.\n]{6,90})\.")

STOP = set(base.STOP) | set("""
this bill would allows allow allowed requires require required repeals repeal
repealed establishes establish established amends amend amended provides
provide provided adds add added makes make made changes change changed
section sections chapter chapters shall may must also further additionally
current law existing person persons who whom whose when where while
""".split())


def title_words(title):
    t = NEWTITLE.sub("", title or "")
    return [base.singular(w) for w in WORD.findall(t.lower())
            if w not in STOP]


def analysis_of(text):
    """The drafters' own summary: everything between ANALYSIS and the rule."""
    if not text:
        return ""
    up = text.upper()
    i = up.find("ANALYSIS")
    if i < 0:
        return ""
    rest = text[i + 8:]
    for stop in ("- - - -", "Explanation:", "EXPLANATION:", "STATE OF NEW HAMPSHIRE"):
        j = rest.find(stop)
        if j > 0:
            rest = rest[:j]
    return rest[:4000]


def rsa_chapters(text):
    """(chapters, chapter:sections) with how often each is cited."""
    ch = collections.Counter()
    sec = collections.Counter()
    for m in RSA_RE.finditer(text or ""):
        c = m.group(1).upper().replace("‑", "-")
        ch[c] += 1
        if m.group(3):
            sec[f"{c}:{m.group(3).lower()}"] += 1
    return ch, sec


def operative_chapters(text):
    c = collections.Counter()
    for m in OPERATIVE.finditer(text or ""):
        g = m.group(1) or m.group(2) or m.group(3)
        if g:
            c[g.upper().replace("‑", "-")] += 1
    return c


def headings(text):
    return " ".join(m.group(2) for m in HEADING.finditer(text or ""))


def first_sentence(an):
    """The drafters' one-line summary: 'This bill requires ...'."""
    m = re.search(r"[^.]{20,400}\.", an or "")
    return m.group(0) if m else (an or "")[:300]


def features(rec, text):
    """{family: [(feature, weight)]}. Families absent where the evidence is."""
    out = {}
    tw = title_words(rec.get("title"))
    out["w"] = [(w, 1.0) for w in dict.fromkeys(tw)]
    out["b"] = [(f"{a}_{b}", 1.0)
                for a, b in dict.fromkeys(zip(tw, tw[1:]))]
    out["w1"] = [(w, 1.0) for w in dict.fromkeys(tw[:3])]
    out["sk"] = [(f"{a}~{b}", 1.0) for a, b in dict.fromkeys(
        [(x, y) for i, x in enumerate(tw) for y in tw[i + 2:i + 4]])]
    cm = []
    for i, c in enumerate(base.committees_of(rec)):
        cm.append((c, 1.0 if i == 0 else 0.5))
    out["c"] = cm
    k = re.match(r"[A-Za-z]+", rec.get("bill") or "")
    if k:
        out["k"] = [(k.group(0).upper(), 1.0)]
    an = analysis_of(text)
    if an:
        aw = title_words(an)
        out["a"] = [(w, 1.0) for w in dict.fromkeys(aw)]
        out["ab"] = [(f"{a}_{b}", 1.0)
                     for a, b in dict.fromkeys(zip(aw, aw[1:]))]
        out["a1"] = [(w, 1.0)
                     for w in dict.fromkeys(title_words(first_sentence(an)))]
    hd = headings(text)
    if hd:
        out["h"] = [(w, 1.0) for w in dict.fromkeys(title_words(hd))]
    ch, sec = rsa_chapters(text)
    if ch:
        tot = sum(ch.values())
        out["r"] = [(k, min(1.0, 0.25 + n / tot)) for k, n in ch.items()]
    if sec:
        tot = sum(sec.values())
        out["rs"] = [(k, min(1.0, 0.25 + n / tot)) for k, n in sec.items()]
    op = operative_chapters(text)
    if op:
        tot = sum(op.values())
        out["ro"] = [(k, min(1.0, 0.25 + n / tot)) for k, n in op.items()]
    return out


FAMILIES = ("w", "b", "w1", "sk", "c", "k", "a", "ab", "a1", "h",
            "r", "rs", "ro")
TEXT_FAMILIES = ("a", "ab", "a1", "h", "r", "rs", "ro")

# ---------------------------------------------------------------------- model


class Model:
    """Per-feature log-odds, shrunk toward the prior."""

    def __init__(self, rows, m, seed_names=0.0, extra_seeds=None,
                 all_topics=None):
        """rows: [(bill_id, rec, text, gold)]. m: {family: shrinkage}.

        The label space is the General Court's own list, not whatever the
        training sample happened to contain: a category with one labelled
        bill must still be an available answer.
        """
        self.topics = sorted({g for _b, _r, _t, g in rows}
                             | set(all_topics or ())
                             | set((extra_seeds or {})))
        self.tix = {t: i for i, t in enumerate(self.topics)}
        T = len(self.topics)
        prior = np.zeros(T)
        for _b, _r, _t, g in rows:
            prior[self.tix[g]] += 1
        # a topic with no labelled bill at all (a new category) still needs a
        # prior; give it the smallest one observed.
        prior[prior == 0] = max(1.0, prior[prior > 0].min())
        self.prior = prior / prior.sum()
        self.logprior = np.log(self.prior)
        self.m = dict(m)

        cnt = {f: collections.defaultdict(lambda: np.zeros(T)) for f in FAMILIES}
        tot = {f: collections.defaultdict(float) for f in FAMILIES}
        for _b, rec, text, g in rows:
            i = self.tix[g]
            for fam, feats in features(rec, text).items():
                for k, w in feats:
                    cnt[fam][k][i] += w
                    tot[fam][k] += w

        # SEEDS. Two kinds, both optional and both measured.
        #  (a) the General Court's own name for the category, as if it had
        #      labelled `seed_names` bills whose title was that name.
        #  (b) extra_seeds: {topic: [(family, feature, weight)]}, used only
        #      for the two categories the General Court has never labelled.
        if seed_names:
            for t in self.topics:
                i = self.tix[t]
                nw = title_words(re.sub(r"[^A-Za-z ]", " ", t))
                for w in dict.fromkeys(nw):
                    cnt["w"][w][i] += seed_names
                    tot["w"][w] += seed_names
                for a, b in dict.fromkeys(zip(nw, nw[1:])):
                    cnt["b"][f"{a}_{b}"][i] += seed_names
                    tot["b"][f"{a}_{b}"] += seed_names
        for t, items in (extra_seeds or {}).items():
            i = self.tix[t]
            for fam, k, w in items:
                cnt[fam][k][i] += w
                tot[fam][k] += w

        self.cnt, self.tot = cnt, tot
        self.set_m(self.m)

    def set_m(self, m):
        self.m = dict(m)
        self.lo = {}
        for fam in FAMILIES:
            mm = self.m.get(fam, 5.0)
            d = {}
            for k, v in self.cnt[fam].items():
                p = (v + mm * self.prior) / (self.tot[fam][k] + mm)
                d[k] = np.log(p) - self.logprior
            self.lo[fam] = d

    def famvec(self, rec, text):
        """{family: (sum of log-odds vectors, total feature weight)}."""
        out = {}
        for fam, feats in features(rec, text).items():
            v = np.zeros(len(self.topics))
            tw = 0.0
            lof = self.lo[fam]
            for k, w in feats:
                a = lof.get(k)
                if a is not None:
                    v += w * a
                    tw += w
            out[fam] = (v, tw)
        return out


def combine(model, fv, W, P, lp=1.0):
    s = lp * model.logprior.copy()
    for fam, (v, tw) in fv.items():
        w = W.get(fam, 0.0)
        if w and tw > 0:
            s = s + w * v / (tw ** P.get(fam, 0.0))
    return s


def decide(model, s, temp, floor):
    """(topic, p_top, runner_up, argmax). Miscellaneous below the floor."""
    z = s / temp
    z = z - z.max()
    p = np.exp(z)
    p /= p.sum()
    order = np.argsort(-s)
    top = model.topics[order[0]]
    second = model.topics[order[1]] if len(order) > 1 else ""
    ptop = float(p[order[0]])
    return (top if ptop >= floor else MISC), ptop, second, top


# ------------------------------------------------------------------- the data

def load_texts():
    """{term: {bill: text}} from the two files that carry a bill's own words.

    bill_text.json wins over archive_text.json where both have a bill: the
    first is the General Court's current page, the second the archive copy.
    """
    out = collections.defaultdict(dict)
    for name, key in (("archive_text.json", "text"), ("bill_text.json", "text")):
        p = Path(name)
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        for term, by_bill in d.items():
            for b, v in by_bill.items():
                t = (v or {}).get(key) or ""
                if t or b not in out[term]:
                    out[term][b] = t
    return out


def dataset():
    bills = base.load()
    texts = load_texts()
    lab = base.labelled(bills)
    rows = []
    for b, r in lab:
        rows.append((b, r, texts.get(LABELLED_TERM, {}).get(b, ""), r["subject"]))
    tr = [x for x in rows if base.split_half(x[0]) == 0]
    te = [x for x in rows if base.split_half(x[0]) == 1]
    return bills, texts, rows, tr, te


# ------------------------------------------------------------------ the answer

CFG_PATH = REPO / "topic_model.json"


def config():
    if not CFG_PATH.exists():
        sys.exit(f"No {CFG_PATH.name}; this model's settings live in it.")
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


def remap_gold(gold, rec):
    """Space B's vocabulary, applied to a label. Not used by space A."""
    if is_study(rec.get("title")):
        return STUDY
    if (rec.get("house_committee") or "").strip().lower() == HOUSING_COMMITTEE:
        return HOUSING
    if is_housing(rec.get("title")):
        return HOUSING
    return FOLD.get(gold, gold)


def new_vocabulary():
    return sorted(({FOLD.get(t, t) for t in base.codes()} - RETIRED)
                  | {HOUSING, STUDY})


def fit(bills=None, texts=None, cfg=None, space="B"):
    """One model on every labelled bill, in space A (gold) or B (the new list)."""
    cfg = cfg or config()
    if bills is None:
        bills, texts, _a, _tr, _te = dataset()
    rows = []
    for b, r in base.labelled(bills):
        t = texts.get(LABELLED_TERM, {}).get(b, "")
        g = remap_gold(r["subject"], r) if space == "B" else r["subject"]
        if g in RETIRED:
            continue
        rows.append((b, r, t, g))
    if not rows:
        sys.exit(f"No labelled bills in {LABELLED_TERM}; nothing to learn from.")
    allt = new_vocabulary() if space == "B" else sorted(base.codes())
    return Model(rows, cfg["m"], seed_names=cfg["seed_names"], all_topics=allt)


def answer(model, rec, text, cfg=None):
    """(topic, confidence, regime, runner-up). Miscellaneous below the floor."""
    cfg = cfg or config()
    # The study template only fires where the vocabulary has a category for it
    # to answer. In space A there is none, and answering STUDY there would name
    # a topic data/subjects.json has never heard of.
    if STUDY in model.tix and is_study(rec.get("title")):
        return STUDY, 1.0, "rule", ""
    regime = "text" if text else "notext"
    c = cfg["regimes"][regime]
    s = combine(model, model.famvec(rec, text), c["W"], cfg["P"], c["lp"])
    topic, conf, second, top = decide(
        model, s, c.get("temp", 2.0), cfg.get("floors", {}).get(regime, 0.0))
    return topic, conf, regime, (second if topic != MISC else top)


def ranked_features(model, rec, text, topic, other, cfg=None):
    """[(score, family, feature)] best first: what argued for this answer.

    Every one of them is a word of the title, a word of the drafters' own
    analysis, the name of the committee, the bill's kind, or an RSA chapter.
    Each is scored against what it would have contributed to the runner-up, so
    a word common to both does not come top of a list claiming to explain the
    difference -- the same rule topics.evidence() follows.
    """
    cfg = cfg or config()
    regime = "text" if text else "notext"
    c = cfg["regimes"][regime]
    ia, ib = model.tix[topic], model.tix.get(other, model.tix[topic])
    out = []
    for fam, feats in features(rec, text).items():
        w = c["W"].get(fam, 0.0)
        if not w:
            continue
        tw = sum(x for _k, x in feats) or 1.0
        nrm = tw ** cfg["P"].get(fam, 0.0)
        for k, x in feats:
            v = model.lo[fam].get(k)
            if v is None:
                continue
            out.append((float(w * x * (v[ia] - v[ib]) / nrm), fam, k))
    out.sort(reverse=True)
    return out


def evidence(model, rec, text, topic, other, cfg=None, limit=8):
    """The top features, labelled by family, for --bill to print."""
    return [(f"{fam}:{k}", round(s, 2))
            for s, fam, k in ranked_features(model, rec, text, topic,
                                             other, cfg)[:limit]]


def feature_string(fam, key):
    """One feature as the plain token the file has always carried.

    topics.py wrote bare words, underscore-joined pairs and "CMTE:Name", and
    review.py renders those by replacing "CMTE:" and "_". The families this
    model added keep to the same spelling rather than inventing a second one:
    a committee is still CMTE:, a word pair is still joined by an underscore,
    and an RSA chapter reads as an RSA chapter.
    """
    if fam == "c":
        return "CMTE:" + key
    if fam == "k":
        return "KIND:" + key
    if fam in ("r", "rs", "ro"):
        return "RSA " + key
    if fam == "sk":
        return key.replace("~", "_")
    return key


def why_for(model, rec, text, topic, other, cfg=None, regime="", limit=6):
    """The `why` list: short plain strings, deduped, strongest first.

    Deliberately the same SHAPE topics.py wrote -- a flat list of feature
    tokens, not a structure. Nothing downstream itemises them.
    """
    if regime == "rule":
        return ["study committee in the title"]
    ranked = ranked_features(model, rec, text, topic, other, cfg)
    # Prefer the features that actually favour this answer over the runner-up.
    # For nine bills of 31,449 there are none -- a Labor committee bill whose
    # committee points at Workers' Comp and Unemployment slightly harder than
    # at Employment, which the prior then wins -- and for those the top
    # features are listed anyway, unfiltered, which is what topics.py did for
    # every bill. An empty why on a bill that WAS given a topic reads as a
    # defect on the bench, and the list is the strongest evidence either way.
    pos = [x for x in ranked if x[0] > 0] or ranked
    seen, out = set(), []
    for _s, fam, k in pos:
        f = feature_string(fam, k)
        if f in seen:
            continue
        seen.add(f)
        out.append(f)
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------- the modes

def apply(space="A", limit_terms=None, cfg=None):
    """Write a topic for every bill that has none. Newest term first.

    THE SAME FILE topics.py --apply wrote, key for key:

        {term: {bill: {subject, subject_code, margin, source, why}}}

    with two things worth saying plainly about what the values now mean.

    `margin` is this model's confidence in its answer -- the calibrated
    probability the decision is actually made on, between 0 and 1 -- where
    topics.py wrote a log-margin over the runner-up compared against 4. It is
    still a rounded float and still "how sure is this", and nothing computes
    on it; review.py prints it and says "below 4", which is stale text on the
    bench page and wants a line changed there.

    `why` is still a flat list of short feature tokens. There is no new
    explanation format here and none is wanted.
    """
    cfg = cfg or config()
    t0 = time.time()
    bills = base.load()
    texts = load_texts()
    # SILENCE IS NOT SUCCESS, the first of three guards here. With neither
    # text file on disk every bill falls to the weaker no-text weights and the
    # run still prints a tidy table -- a five-point loss that looks like a
    # success.
    if not any(t for by_bill in texts.values() for t in by_bill.values()):
        sys.exit("No bill text on disk (bill_text.json, archive_text.json), so "
                 "every bill would be answered by the weaker no-text weights. "
                 "Fix those files or run topics.py, which never used them.")
    model = fit(bills, texts, cfg, space)
    code_of = base.codes()
    if not code_of:
        sys.exit("No data/subjects.json, so no subject codes; refusing to "
                 "write a file whose every code would be MSC.")
    out, tally = {}, collections.Counter()
    # NEWEST FIRST, the standing order for a backfill, and doubly right here:
    # the recent terms are the ones the committees still match and the ones
    # whose bill text exists, so they are both the most useful and the most
    # accurate.
    terms = sorted(bills, reverse=True)
    if limit_terms:
        terms = terms[:limit_terms]
    for term in terms:
        if term == LABELLED_TERM:
            continue
        got = {}
        by_text = texts.get(term, {})
        for bid, rec in bills[term].items():
            if rec.get("subject"):
                continue
            text = by_text.get(bid, "")
            topic, conf, regime, other = answer(model, rec, text, cfg)
            got[bid] = {
                "subject": topic,
                "subject_code": (ADDED_CODES.get(topic)
                                 or code_of.get(topic) or MISC_CODE),
                "margin": round(conf, 2),
                "source": SOURCE,
                "why": (why_for(model, rec, text, topic, other, cfg, regime)
                        if topic != MISC else []),
            }
            tally[term if topic != MISC else term + " (misc)"] += 1
            if text:
                tally[term + " (text)"] += 1
        if got:
            out[term] = got

    total = sum(len(v) for v in out.values())
    placed = sum(n for k, n in tally.items()
                 if not k.endswith(("(misc)", "(text)")))
    # SILENCE IS NOT SUCCESS. A run that answered nothing, or declined
    # everything, exits non-zero rather than printing a tidy zero and letting
    # build_all carry on to a site with an empty topic facet.
    if not out or total == 0:
        sys.exit("Wrote nothing: no bill in any term lacks a subject. That is "
                 "either a data/bills.json with only the labelled term in it "
                 "or a bug; either way the old file is left alone.")
    if placed == 0:
        sys.exit(f"All {total:,} bills came back Miscellaneous. The floors in "
                 f"{CFG_PATH.name} or the model are wrong; the old file is "
                 f"left alone.")
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{total:,} bills across {len(out)} terms -> {OUT}")
    print(f"  {placed:,} given a topic, {total-placed:,} Miscellaneous "
          f"({100*placed/total:.0f}% placed, label space {space})")
    print(f"\n{'term':12}{'placed':>9}{'miscellaneous':>15}{'with text':>11}")
    for term in sorted(out, reverse=True):
        p = tally.get(term, 0)
        m = tally.get(term + " (misc)", 0)
        t = tally.get(term + " (text)", 0)
        print(f"  {term:10}{p:>9,}{m:>15,}{100*t/max(1,p+m):>10.0f}%")
    print(f"\n  {time.time()-t0:.1f}s")
    return 0


def explain(term, bid, space="A"):
    bills, texts, _a, _tr, _te = dataset()
    rec = bills.get(term, {}).get(bid)
    if not rec:
        sys.exit(f"No {bid} in {term}.")
    cfg = config()
    model = fit(bills, texts, cfg, space)
    text = texts.get(term, {}).get(bid, "")
    topic, conf, regime, other = answer(model, rec, text, cfg)
    print(f"{bid} of {term}")
    print(f"  title      {rec.get('title','')}")
    print(f"  committee  {base.committee_of(rec) or '(none)'}")
    print(f"  given      {rec.get('subject') or '(none by the General Court)'}")
    how = {"text": "title, committee, the drafters' analysis and the RSA "
                   "chapters the bill amends",
           "notext": "title and committee only -- this bill has no text on disk",
           "rule": "the study-committee title template"}[regime]
    print(f"  evidence   {how}")
    print(f"\n  this says  {topic}   (confidence {conf:.2f}, runner-up {other})")
    print(f"  code       {base.codes().get(topic) or MISC_CODE}")
    if regime != "rule":
        for k, s in evidence(model, rec, text, topic, other, cfg):
            print(f"     {k:<34} {s:+6.2f}")
        s = combine(model, model.famvec(rec, text),
                    cfg["regimes"][regime]["W"], cfg["P"],
                    cfg["regimes"][regime]["lp"])
        print("\n  the three it weighed:")
        for i in np.argsort(-s)[:3]:
            print(f"     {model.topics[i]:38} {s[i]:9.2f}")
    print(f"  why        {', '.join(why_for(model, rec, text, topic, other, cfg, regime))}")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="The second topic model. --apply writes topics_assigned.json.")
    ap.add_argument("--apply", action="store_true", help=f"write {OUT}")
    ap.add_argument("--bill", nargs=2, metavar=("TERM", "BILL"),
                    help="explain one bill's answer")
    ap.add_argument("--space", default="A", choices=("A", "B"),
                    help="A: the General Court's own 46 categories (default). "
                         "B: the proposed vocabulary, which two of data/"
                         "subjects.json's codes do not cover")
    ap.add_argument("--terms", type=int, default=0,
                    help="with --apply, only the newest N terms")
    a = ap.parse_args()
    if a.bill:
        return explain(a.bill[0], a.bill[1], a.space)
    if a.apply:
        return apply(a.space, a.terms or None)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
