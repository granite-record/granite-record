#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.13
"""The tag rule engine: which tags a bill carries, and the evidence for each.

    python3 src/parse/tag_rules.py --bill 2023-2024 HB1596   # explain one bill
    python3 src/parse/tag_rules.py --check                   # read the registry, report problems

STAGE 1 OF THE TOPICS-AS-TAGS DESIGN (reports/topics-as-tags-design-2026-11.md,
sections 2 to 4), AND WHAT THE SITE READS OF IT (stages 3 and 4, 17 November
2026): in_force(), site_tags() and site_meta(), at the end of this file, which
build_site_v2.py calls, and the cap site_tags applies (best_tags). It asks no
network and writes no file but the build's cache (.build_cache/bill_tags.json.gz,
build_cache.py).

THE REGISTRY is a person's file, corrections/tags.json, which no generator
writes. Where it is absent the committed fixture (tests/tags_fixture.json, key
"registry") is read instead, so that a check always has one, and a clone shows
no real tag. GRANITE_TAGS names another file (the owner's draft, in reports/)
for the bench and the counts; an explicit path argument wins over it.

THE SITE READS corrections/tags.json AND NOTHING ELSE (in_force): not the
fixture, not GRANITE_TAGS, so the owner's copying a draft there is what puts
tags on the pages. Absent, or holding no tag, the build is as it was before
tags, byte for byte: no field in a bill's record or index row, no key in
meta.json, and the scripts and stylesheet published without their TAGS
regions (build_pages.without_tags).
The file is {"tags": {id: entry}} or a bare {id: entry}; an entry is

    name, group, definition (one neutral sentence), asks (the words readers use,
    for search), rule, same_as_topic (topic names the tag would only repeat),
    pair (two real bills of opposite aims that must both attach), neutrality_hard,
    wave, approved, bench, stance_ok (deny-listed words the owner has allowed in
    the name, each with the reason), note.

THE RULE, by what each kind of evidence may claim (design 2.3):

    title             T  a phrase in the bill's title attaches the tag alone
    analysis          A  a phrase in the drafters' analysis, at least
                         `analysis_min_mentions` times (2), or once where the
                         analysis is under `analysis_short_chars` (500) long
    chapters_alone    R  the bill amends a chapter dedicated to the subject and
                         no more than `max_chapters` (3) in all
    chapters_with_words  R  such a chapter AND one of its words in the title
                         or the analysis
    chapters_support  never attaches: a family chapter (every elections bill
                         amends RSA 654 and 659); it is shown by explain only
    not               phrases blanked out of the title and the analysis before
                         any is looked for: "hemp rope" is no cannabis bill, and
                         the rest of the text still counts
    not_bill          phrases that take the whole tag away if the title has one
    provisions        R  a phrase in the heading of a new chapter of the RSA, or of
                         an article of the constitution, that the bill's text writes
                         ("CHAPTER 76-A INCOME TAX", "[Art.] 5-c [Income Tax
                         Prohibited.]"): for a tag that is about one provision of
                         law and not about words, which may have no other tier
    duties            R  an office the bill gives a duty or a power: a phrase that
                         is the subject of a "shall" or a "may" in the title or
                         the text ("the attorney general shall"), or the one a
                         title or analysis "requires", "authorizes" or "directs"
                         to act; `not` phrases are blanked from what was found
                         first ("shall print the question", every CACR's)

The committee and the full text NEVER attach a tag, but for what the text says it
amends -- the chapters, and the headings of the chapters and articles it writes --
and whom it gives a duty or a power.

THE DUTIES (17 Nov 2026, the owner: "having tags for the position like attorney
general, secretary of state, governor, etc for positions that are referenced in
the bill text like an obligation that the role must do"). A bill that merely
names an office is not about it; one whose text says "the secretary of state
shall" or "may" gives that office something to do. duties() reads each "shall"
and "may" (lower case: "May" is a month) back to the start of its clause, sets
aside an aside between commas (", with the consent of the council,") and a
designee, keeps the last six words of the subject and the four words after the
verb, and says nothing for a "shall be" or "may be", whose subject is acted on
or described ("shall be appointed", "shall be paid", "shall be the same"), but
"shall be responsible", "authorized", "required" and their kind. A subject
joined by "and" is read whole, in its parts and from each joint on, so "the
governor and council may" gives both. A rule's phrase must be the whole subject
but for "the", "each" and their kind and "deputy" or "acting": "the
representatives of the governor shall" gives the governor nothing. The drafters'
"requires the secretary of state to", "authorizing the governor to" in a title
or an analysis count as a "shall" and a "may". The text kept is what the bill
prints, amended sections in full, so an office's duty restated beside the change
counts too: the owner's "referenced in the bill text"; a rule's `not` phrases
take out the boilerplate ("the governor is authorized to draw a warrant").

THE PROVISIONS (17 Nov 2026, the owner: a state income tax tag "only for bills
that change that particular provision of law -- whether adding an income tax or
banning one", by "the statute chapter or the Constitution article such bills
amend", "never by title words alone"). A bill that would add an income tax
writes it as a new chapter, CHAPTER 76-A INCOME TAX in 2008 and CHAPTER 77-H in
2018, whose number is the next free one and so says nothing; a CACR that would
ban one writes a new article of Part II, [Art.] 5-c or 6-c or 18-b [Income Tax
Prohibited.]. Each says what it is in its heading, and the heading is what this
reads: a chapter's heading in capitals followed by its own first section (76-A:1),
and an article's in the brackets that follow "[Art.]", with the Part the text
names ("the second part of the constitution").

BY HAND, beside the rule (16 Nov 2026): an entry's "hand" holds the bills a
person decided on the bench that no phrase or chapter can reach, each by its
key with the reason, so a judgment is honoured without a rule bent to fit it:

    hand.attach       H  the tag is on this bill whatever fires ("2021-2022/SB140":
                         "the owner's bench, 15 Nov 2026: partly"); a tier of its
                         own, last, so a bill a phrase also attaches shows the phrase
    hand.detach       the tag is off this bill whatever fires, and is said to be

A hand bill is the person's own answer, so the bench never draws one to ask
again, and the topic-redundancy drop still applies to it.

A PHRASE is plain words: whole words, any case, a space and a hyphen standing
for each other, an apostrophe optional, a plural allowed on the last word
("mental health" never matches "environmental health"): "-s" or "-es", and
since 16 Nov 2026 "-ies" for a consonant and "y" ("public utility" finds
"public utilities") and "-y" for such an "-ies" ("juries" finds "jury"), so a
plural that means another thing wants "re:" ("securities" is no "security"
bill). A trailing * opens the right end ("vaccin*"),
a leading = makes it case-sensitive ("=AI", "=THC"), "re:" begins a regular
expression, used as written. A chapter is "126-X"; a trailing * takes the
chapter and every lettered one under it ("159*").

A tag that equals the bill's assigned topic (same_as_topic) is dropped and
said to be, not attached twice. tag_bill caps nothing: it is the rules'
answer, which the bench and the counts read, and a bill over `GUIDE_TAGS` (5)
is for the caller to report. The site shows at most `MAX_TAGS` (10) of a
bill's tags, its best-matched (best_tags: THE CAP, beside what the site reads).

SYNONYMS (12 Nov 2026). The words a reader types live with the registry, one
source: every tag's name and asks lead to that tag, and the file's own
"synonyms" table ({"school choice": "tag:school-funding", "absentee ballot":
"topic:Elections"}) leads a word that is no tag's name to the tag that
holds its bills or to the closest topic. synonym_table() builds the one table;
a word with no neutral home gets no entry and is searched as typed (the
owner, 13 November 2026, dropping the draft's religion, church and
conscience words, which led to the Discrimination topic);
validate() fails a word that leads to no tag or topic, or to two places. App.js's
CONCEPTS still maps a word to bill WORDING; the search reads this table at the
stage that shows tags. A tag under MIN_BILLS (20) at the title and analysis
tiers is a synonym, not a tag, unless its entry says keep_small and why: a
reference, not a rule, and tag_counts.py lists the tags under it.

Deterministic, standard library, no global state: the same registry and the
same bills give the same answer under any PYTHONHASHSEED.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import json
import os
import re

ROOT = _paths.ROOT
REGISTRY = Path("corrections") / "tags.json"
FIXTURE = Path("tests") / "tags_fixture.json"
GUIDE_TAGS = 5
# THE CAP (the owner, 17 Nov 2026: "17 seems a bit excessive so maybe something like 10 that are the
# best matches"): the most tags the site shows on one bill, its best-matched (best_tags).
MAX_TAGS = 10
# A REFERENCE, NOT A RULE (the owner, 12 Nov 2026): a tag wants a decent number of bills.
# Under this many at the title and analysis tiers across all terms, a tag is a search
# synonym that leads to a topic or another tag, unless its entry says keep_small and why.
MIN_BILLS = 20
# The site's topics as of 17 November 2026, when two were split in two (topic_model.SPLITS) and
# Cannabis drawn from the rest (topic_model.cannabis_topic); site/meta.json's "topics" wins where
# it is on disk.
SITE_TOPICS = (
    "Agriculture", "Animals", "Banking and Finance", "Business and Industry", "Cannabis", "Children", "Civil Actions",
    "Constitutional Amendments", "Corrections", "Counties", "Courts and Procedure", "Crimes and Criminal Procedure",
    "Discrimination", "Domestic Relations", "Education - Finance", "Education - General", "Elections", "Employment",
    "Energy and Utilities", "Environment - Administration", "Environment - Conservation",
    "Federal and International Relations", "Fish & Game", "Gambling", "Housing", "Insurance", "Legislature",
    "Liquor and Beer", "Memorials", "Military & Veterans' Affairs", "Miscellaneous", "Motor Vehicles", "Municipalities",
    "Occupational Regulation", "Personal Property", "Police", "Public and Mental Health", "Real Estate", "Retirement",
    "Right to Know", "State Government", "Study Committees and Commissions", "Taxes - Local", "Taxes - State",
    "Transportation and Highways", "Welfare/Medicare/Medicaid", "Zoning and Planning")
TIERS = ("T", "A", "R", "H")
BILL_KEY = re.compile(r"\d{4}-\d{4}/[A-Z]+\d+")

# Words that argue rather than name. A tag's NAME may not carry one unless the
# owner has allowed it (stance_ok), because the name is what a reader sees; a
# DEFINITION is held to the sharper half. Design section 6.3.
STANCE_NAME = {"reform": r"reform", "ban": r"bans?(?:ned|ning)?(?![a-z])", "rights": r"rights?(?![a-z])",
               "safety": r"safety", "crisis": r"crisis", "extremist": r"extremis", "radical": r"radical",
               "protect": r"protect", "freedom": r"freedom", "choice": r"choice", "pro-": r"pro-",
               "anti-": r"anti-"}
STANCE_DEFINITION = ("reform", "ban", "extremist", "radical", "pro-", "anti-")

_HY = r"[\s\-‐‑–—]"
_AP = "['’]"
_LEFT, _RIGHT = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"
# THE -Y PLURAL (16 Nov 2026). A last word ending in a consonant and "y" takes "-ies" as its plural
# ("utility", "utilities"), and one ending so in "-ies" its "-y" singular ("juries", "jury"), beside
# the "-s" and "-es" every last word takes; a vowel before the "y" keeps the "-s" ("day", "days").
# The two words whose "-ies" is no plural are left as written. A form that means something else in
# the plural ("securities" is no "security" bill) wants its own "re:" phrase.
_CONSONANT = "[b-df-hj-np-tv-xzB-DF-HJ-NP-TV-XZ]"
_CONSONANT_Y = re.compile(rf"(.+{_CONSONANT})(y|Y)")
_CONSONANT_IES = re.compile(rf"(.+{_CONSONANT})(ies|IES)")
_IES_NO_PLURAL = {"series", "species"}


def _word(tok, last):
    """One word of a phrase as a regular expression: an apostrophe optional, and the last word
    (`last`) with its plural (the -y plural above)."""
    esc = lambda s: (_AP + "?").join(re.escape(x) for x in s.split("'"))
    if not last:
        return esc(tok)
    m = _CONSONANT_Y.fullmatch(tok)
    if m:
        ies = "ies" if m.group(2) == "y" else "IES"
        return esc(m.group(1)) + f"(?:{m.group(2)}(?:s|es)?|{ies})"
    m = _CONSONANT_IES.fullmatch(tok)
    if m and tok.lower() not in _IES_NO_PLURAL:
        y = "Y" if m.group(2).isupper() else "y"
        return esc(m.group(1)) + f"(?:{m.group(2)}(?:s|es)?|{y})"
    return esc(tok) + "(?:s|es)?"


def compile_phrase(p):
    """A phrase of the registry as a compiled regular expression."""
    if p.startswith("re:"):
        return re.compile(p[3:], re.I)
    flags = re.I
    if p.startswith("="):
        p, flags = p[1:], 0
    open_end = p.endswith("*")
    if open_end:
        p = p[:-1]
    toks = re.split(r"[\s\-]+", p.strip())
    out = []
    for i, tok in enumerate(toks):
        if i:
            out.append(_HY + "+")
        out.append(_word(tok, i == len(toks) - 1 and not open_end))
    body = "".join(out)
    return re.compile(_LEFT + body + ("" if open_end else _RIGHT), flags)


def chapter_matches(rule_chapter, chapter):
    """RSA chapter `chapter` against a rule's: exact, or "159*" for 159 and 159-B."""
    c = chapter.upper()
    if rule_chapter.endswith("*"):
        base = rule_chapter[:-1].upper()
        return c == base or c.startswith(base + "-")
    return c == rule_chapter.upper()


def norm_chapter(c):
    return str(c).upper().replace("‑", "-").strip()


# A new chapter's heading, in capitals, as the text prints it before the chapter's own first section
# ("CHAPTER 76-A INCOME TAX 76-A:1 Definitions."); an article's, in the brackets after "[Art.]"
# ("[Art.] 5-c [Income Tax Prohibited.]"), and the Part the text says it amends.
_NEW_CHAPTER = re.compile(r"\bCHAPTER\s+(\d{1,3}-[A-Z]{1,2})\s+([A-Z][A-Z0-9 ,;'’&().\-]{2,120}?)\s+(?=\1:1(?![0-9]))")
_ARTICLE = re.compile(r"\[Art\.\]\s*(\d{1,3}(?:-[a-zA-Z])?)\.?\s*\[([^\]]{3,160})\]")
_PART = re.compile(r"\b(first|second)\s+part\s+of\s+the\s+constitution", re.I)


def provisions(text):
    """The headings of the chapters of the RSA and the articles of the constitution a bill's text
    writes, in their order: "RSA 76-A Income Tax", "Part II, Art. 5-c Income Tax Prohibited"
    (THE PROVISIONS, in the docstring). [] for a text that writes none."""
    t = " ".join((text or "").split())
    out = [f"RSA {m.group(1)} {m.group(2).strip().title()}" for m in _NEW_CHAPTER.finditer(t)]
    part = _PART.search(t)
    where = {"first": "Part I, ", "second": "Part II, "}.get(part.group(1).lower(), "") if part else ""
    out += [f"{where}Art. {m.group(1)} {m.group(2).strip().rstrip('.')}" for m in _ARTICLE.finditer(t)]
    return list(dict.fromkeys(out))


# THE DUTIES (in the docstring). A "shall" or "may" in lower case, or "is required to" and its kind; what a
# title or an analysis "requires" or "authorizes" someone to do; an aside between commas and a designee before
# the verb; a "shall be" or "may be", whose subject is acted on or described rather than acting ("shall be
# appointed", "shall be paid", "shall be subject to", "shall be the same"), but for the few that give a duty or
# a power ("shall be responsible for", "shall be authorized to").
_MODAL = re.compile(r"(?<![A-Za-z])(?:(shall|may)|(?:is|are)\s+(?:hereby\s+)?(required|directed|authorized|permitted|"
                    r"allowed|empowered)\s+to)(?![A-Za-z])")
_GRANT = re.compile(r"(?<![A-Za-z])(requir(?:e|es|ed|ing)|direct(?:s|ed|ing)?|authoriz(?:e|es|ed|ing)|"
                    r"permit(?:s|ted|ting)?|allow(?:s|ed|ing)?|enabl(?:e|es|ed|ing)|empower(?:s|ed|ing)?)\s+"
                    r"((?:the|a|an|each|every|any|all|town|city|county|state)\s[^.;:,()]{1,80}?)\s+to\s+(?!the\s)[a-z]",
                    re.I)
_MAY = {"authorized", "permitted", "allowed", "empowered", "authoriz", "permit", "allow", "enabl", "empower"}
_PASSIVE = re.compile(r"\s*(?:not\s+)?be(?![A-Za-z])(?!\s+(?:responsible|authorized|empowered|required|permitted|"
                      r"allowed|directed|entitled|charged)(?![a-z]))")
_CLAUSE = re.compile(r"[.;:!?()\[\]\"“”]")
_ASIDE = re.compile(r"\s*,[^,]{1,100},\s*$")
_DESIGNEE = re.compile(r",?\s*(?:or|and)\s+(?:(?:his or her|his|her|its|their|the)\s+)?(?:designees?|delegates?|"
                       r"deputy|deputies|agents?)\s*,?\s*$", re.I)
# A word after which an office is the object of a phrase, not the subject: "a report to the governor shall".
# "of" is not one: "secretary of state", "register of deeds", "commissioner of the department of safety".
_PREPOSITIONS = {"to", "by", "with", "from", "for", "upon", "on", "at", "under", "in", "into", "against", "about",
                 "than", "through", "within", "without", "before", "after", "between", "among", "whom", "which",
                 "who", "that", "whether", "if", "when", "unless"}


def _subject(before):
    """The subject a "shall" or "may" ends, from the words `before` it: its last six, lower case, after the
    clause boundary, the asides and the designee are set aside, and before any preposition that would make an
    office its object ("" where none is left)."""
    w = " ".join(_CLAUSE.split(before)[-1].split())
    while True:
        cut = _ASIDE.sub("", _DESIGNEE.sub("", w))
        if cut == w:
            break
        w = cut
    words = w.rsplit(",", 1)[-1].split()
    at = [i for i, x in enumerate(words) if x.lower() in _PREPOSITIONS]
    if at:
        words = words[:at[0]] if at[0] else words[at[-1] + 1:]
    return " ".join(words[-6:]).lower()


def _parts(subject):
    """A subject whole and, where "and" or "or" joins it, each part and what follows each joint: "the
    authority and the governor and council" gives itself, "the authority", "the governor", "council" and "the
    governor and council"."""
    joints = list(re.finditer(r"\s+(?:and/or|and|or)\s+", subject))
    if not joints:
        return [subject]
    parts = [p.strip() for p in re.split(r"\s+(?:and/or|and|or)\s+", subject) if p.strip()]
    return list(dict.fromkeys([subject] + parts + [subject[j.end():] for j in joints[:-1]]))


def duties(text):
    """Whom a bill gives a duty or a power, in its order: "the attorney general shall investigate any alleged
    violation", "the governor and council may", each a subject, its verb ("shall" or "may") and the four words
    after it (THE DUTIES, in the docstring). [] for a text that gives none."""
    t = " ".join((text or "").split())
    out = []
    for m in _MODAL.finditer(t):
        after = t[m.end():m.end() + 60]
        if m.group(1) and _PASSIVE.match(after):
            continue
        verb = m.group(1) or ("may" if m.group(2) in _MAY else "shall")
        subject = _subject(t[max(0, m.start() - 200):m.start()])
        if not subject:
            continue
        tail = " ".join(re.split(r"[,.;:!?()\[\]]", after)[0].split()[:4]).lower()
        out += [f"{s} {verb} {tail}".rstrip() for s in _parts(subject)]
    for m in _GRANT.finditer(t):
        verb = "may" if any(m.group(1).lower().startswith(k) for k in _MAY) else "shall"
        subject = " ".join(m.group(2).split()[-6:]).lower()
        out += [f"{s} {verb}" for s in _parts(subject)]
    return list(dict.fromkeys(out))


def duty_phrase(p):
    """A registry's duty phrase as a regular expression: the phrase that is the whole subject of a "shall" or
    a "may" in one of duties()'s answers, after "the", "each" and their kind and "deputy" or "acting"
    ("attorney general" finds "the attorney general shall", and never "the representatives of the governor
    shall" nor "a report to the attorney general shall", which duties() does not give)."""
    rx = compile_phrase(p)
    return re.compile(r"^\s*(?:(?:the|a|an|each|any|every|no|such|said)\s+)?(?:(?:deputy|acting|interim)\s+)?"
                      + rx.pattern + r"\s+(?:shall|may)(?![A-Za-z])", rx.flags)


class Rule:
    """One tag's compiled rule."""

    def __init__(self, tid, entry):
        r = entry.get("rule") or {}
        self.id = tid
        self.title = [(p, compile_phrase(p)) for p in r.get("title", [])]
        self.analysis = [(p, compile_phrase(p)) for p in r.get("analysis", [])]
        self.min_mentions = int(r.get("analysis_min_mentions", 2))
        self.short_chars = int(r.get("analysis_short_chars", 500))
        self.alone = list(r.get("chapters_alone", []))
        ww = r.get("chapters_with_words") or {}
        self.with_chapters = list(ww.get("chapters", []))
        self.with_words = [(p, compile_phrase(p)) for p in ww.get("words", [])]
        self.support = list(r.get("chapters_support", []))
        self.max_chapters = int(r.get("max_chapters", 3))
        self.nots = [compile_phrase(p) for p in r.get("not", [])]
        self.not_bill = [compile_phrase(p) for p in r.get("not_bill", [])]
        self.provisions = [(p, compile_phrase(p)) for p in r.get("provisions", [])]
        self.duties = [(p, duty_phrase(p)) for p in r.get("duties", [])]
        self.same_as_topic = {t.strip().lower() for t in entry.get("same_as_topic", [])}
        hand = entry.get("hand") or {}
        self.attach = dict(hand.get("attach") or {})
        self.detach = dict(hand.get("detach") or {})

    def blank(self, text):
        for rx in self.nots:
            text = rx.sub(" ", text)
        return text

    def fire(self, bill):
        """({tier: why} for each tier that fires, support chapters)."""
        title = bill.get("title") or ""
        analysis = bill.get("analysis") or ""
        chapters = [norm_chapter(c) for c in bill.get("chapters") or []]
        out = {}
        if any(rx.search(title) for rx in self.not_bill):
            return out, []
        t = self.blank(title)
        for p, rx in self.title:
            if rx.search(t):
                out["T"] = f"T:{p}"
                break
        a = self.blank(analysis)
        if self.analysis and a.strip():
            counts = [(len(rx.findall(a)), p) for p, rx in self.analysis]
            total = sum(n for n, _p in counts)
            if total >= self.min_mentions or (total >= 1 and len(analysis) < self.short_chars):
                top = max(counts, key=lambda x: (x[0], -self.analysis_index(x[1])))
                out["A"] = f"A:{top[1]}" + (f" x{total}" if total > 1 else "")
        if chapters and len(chapters) <= self.max_chapters:
            hit = next((c for c in chapters for r in self.alone if chapter_matches(r, c)), None)
            if hit:
                out["R"] = f"R:RSA {hit}"
            elif self.with_chapters and self.with_words:
                hit = next((c for c in chapters for r in self.with_chapters if chapter_matches(r, c)), None)
                if hit and any(rx.search(t) or rx.search(a) for _p, rx in self.with_words):
                    out["R"] = f"R:RSA {hit} with a word"
        if "R" not in out and self.provisions:
            hit = next((h for h in bill.get("provisions") or [] for _p, rx in self.provisions if rx.search(h)), None)
            if hit:
                out["R"] = f"R:{hit}"
        if "R" not in out and self.duties:
            hit = next((m.group(0) for d in bill.get("duties") or [] for _p, rx in self.duties
                        for m in [rx.search(self.blank(d))] if m), None)
            if hit:
                out["R"] = f"R:{hit.strip()}"
        support = [c for c in chapters if any(chapter_matches(r, c) for r in self.support)]
        return out, support

    def analysis_index(self, phrase):
        for i, (p, _rx) in enumerate(self.analysis):
            if p == phrase:
                return i
        return 0


# ------------------------------------------------------------------ the registry

def registry_path(path=None):
    """(the file to read, what to call it): an explicit path, then GRANITE_TAGS,
    then corrections/tags.json, then the committed fixture."""
    chosen = path or os.environ.get("GRANITE_TAGS")
    if chosen:
        return Path(chosen), "explicit"
    if (ROOT / REGISTRY).is_file():
        return ROOT / REGISTRY, "corrections"
    return ROOT / FIXTURE, "fixture"


def load_registry(path=None):
    """({id: entry} in the file's order, source) -- source is "corrections",
    "explicit" or "fixture"."""
    p, source = registry_path(path)
    d = json.loads(p.read_text(encoding="utf-8"))
    if source == "fixture" or "registry" in d and "tags" not in d:
        d = d.get("registry", d)
    return dict(d.get("tags", d)), source


def read_doc(path=None):
    """The registry file as written: {"tags": ..., "synonyms": ...}, whichever shape it has."""
    p, source = registry_path(path)
    d = json.loads(p.read_text(encoding="utf-8"))
    if "registry" in d and "tags" not in d:
        reg = d["registry"]
        return {"tags": reg.get("tags", reg), "synonyms": d.get("synonyms", {})}
    return d


def known_topics(root=None):
    """The topic names a synonym may lead to: site/meta.json's where it is on disk, else SITE_TOPICS."""
    p = Path(root or ROOT) / "site" / "meta.json"
    try:
        t = json.loads(p.read_text(encoding="utf-8")).get("topics")
        if t:
            return list(t)
    except (OSError, ValueError):
        pass
    return list(SITE_TOPICS)


def norm_word(w):
    """A search word as the table keys it: lower case, hyphens and runs of space as one space."""
    return " ".join(re.sub(r"[-\u2010\u2011]", " ", str(w).lower().replace("\u2019", "'")).split())


def synonym_table(reg, synonyms=None):
    """({word: target}, [conflicts]): what a reader may type, and where it leads. A target is
    "tag:ID" or "topic:Name". Every tag's name and asks lead to that tag; `synonyms` (the file's
    own table) leads to a tag that holds the bills or, where no tag is kept, to the closest
    topic. A word that would lead to two places is a conflict, not a choice made here."""
    table, bad = {}, []

    def add(word, target, where):
        w = norm_word(word)
        if not w:
            return
        if w in table and table[w] != target:
            bad.append(f"{w!r} leads to {table[w]} and to {target} ({where})")
        else:
            table.setdefault(w, target)
    for tid, e in reg.items():
        add(e.get("name", ""), f"tag:{tid}", tid)
        for a in e.get("asks", []):
            add(a, f"tag:{tid}", tid)
    for w, target in (synonyms or {}).items():
        add(w, target, "synonyms")
    return table, bad


def compile_registry(reg):
    return {tid: Rule(tid, e) for tid, e in reg.items() if isinstance(e, dict) and "rule" in e}


def validate(reg, topics=None, synonyms=None):
    """Problems with a registry, as a list of sentences (empty: none)."""
    bad = []
    seen = set()
    for tid, e in reg.items():
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", tid):
            bad.append(f"{tid}: an id is lower-case words joined by hyphens")
        if tid in seen:
            bad.append(f"{tid}: repeated")
        seen.add(tid)
        name, dfn = e.get("name") or "", e.get("definition") or ""
        if not name:
            bad.append(f"{tid}: no name")
        if not dfn:
            bad.append(f"{tid}: no definition")
        elif len(dfn) > 300 or len(re.findall(r"[.!?](?:\s|$)", dfn)) != 1:
            bad.append(f"{tid}: the definition is one sentence of at most 300 characters")
        ok = {w.lower() for w in e.get("stance_ok", [])}
        for w, rx in STANCE_NAME.items():
            if w not in ok and re.search(r"(?<![a-z])" + rx, name.lower()):
                bad.append(f"{tid}: the name {name!r} carries {w!r}, which argues; the owner may allow it in stance_ok")
        for w in STANCE_DEFINITION:
            if w not in ok and re.search(r"(?<![a-z])" + STANCE_NAME[w], dfn.lower()):
                bad.append(f"{tid}: the definition carries {w!r}, which argues")
        r = e.get("rule")
        if not isinstance(r, dict) or not (r.get("title") or r.get("analysis") or r.get("chapters_alone")
                                           or r.get("provisions") or r.get("duties")):
            bad.append(f"{tid}: a rule needs a title, analysis, chapters_alone, provisions or duties list")
            continue
        for key in ("title", "analysis", "not", "not_bill", "provisions", "duties"):
            for p in r.get(key, []):
                try:
                    compile_phrase(p)
                except re.error as ex:
                    bad.append(f"{tid}: {key} phrase {p!r} does not compile: {ex}")
        for p in (r.get("chapters_with_words") or {}).get("words", []):
            try:
                compile_phrase(p)
            except re.error as ex:
                bad.append(f"{tid}: chapters_with_words phrase {p!r} does not compile: {ex}")
        if topics is not None:
            for t in e.get("same_as_topic", []):
                if t not in topics:
                    bad.append(f"{tid}: same_as_topic {t!r} is no topic of the site")
        pair = e.get("pair")
        if pair is not None and not (isinstance(pair, list) and len(pair) == 2
                                     and all(re.fullmatch(r"\d{4}-\d{4}/[A-Z]+\d+", x) for x in pair)):
            bad.append(f"{tid}: a pair is two keys like 2023-2024/HB1596")
        if e.get("neutrality_hard") and not pair:
            bad.append(f"{tid}: neutrality is hard for this tag and it has no opposite-aim pair")
        hand = e.get("hand")
        if hand is not None:
            lists = {w: hand.get(w) or {} for w in ("attach", "detach")} if isinstance(hand, dict) else {}
            if not isinstance(hand, dict) or set(hand) - set(lists) or not all(isinstance(v, dict) for v in lists.values()):
                bad.append(f"{tid}: hand is {{\"attach\": {{bill: why}}, \"detach\": {{bill: why}}}}")
            else:
                for w, bills in lists.items():
                    for k, why in bills.items():
                        if not BILL_KEY.fullmatch(k):
                            bad.append(f"{tid}: hand {w} names {k!r}, which is no bill key like 2023-2024/HB1596")
                        if not (isinstance(why, str) and why.strip()):
                            bad.append(f"{tid}: hand {w} {k} says no reason")
                for k in sorted(set(lists["attach"]) & set(lists["detach"])):
                    bad.append(f"{tid}: hand both attaches and takes off {k}")
    table, conflicts = synonym_table(reg, synonyms)
    bad += conflicts
    for w, target in (synonyms or {}).items():
        kind, _, name = str(target).partition(":")
        if kind == "tag" and name not in reg:
            bad.append(f"synonym {w!r} leads to the tag {name!r}, which the registry does not have")
        elif kind == "topic" and topics is not None and name not in topics:
            bad.append(f"synonym {w!r} leads to the topic {name!r}, which the site does not have")
        elif kind not in ("tag", "topic"):
            bad.append(f"synonym {w!r} leads nowhere: a target is tag:ID or topic:Name, not {target!r}")
    return bad


# ------------------------------------------------------------------ the answer

def tag_bill(rules, bill, topic=None):
    """What the registry says of one bill.

    {"tags": {id: {"tier": best of T/A/R/H, "why": the evidence, "fired": [tiers]}},
     "dropped": {id: why}, "support": {id: [chapters]}}

    in registry order. `bill` carries title, analysis, chapters and, optionally,
    topic (the bill's assigned topic, for the redundancy drop), and term and bill,
    which a hand list names it by."""
    topic = (topic if topic is not None else bill.get("topic") or "").strip().lower()
    tags, dropped, support = {}, {}, {}
    key = f"{bill.get('term')}/{bill.get('bill')}"
    for tid, rule in rules.items():
        fired, sup = rule.fire(bill)
        if key in rule.detach:
            if fired:
                dropped[tid] = f"taken off by hand: {rule.detach[key]}"
            continue
        if key in rule.attach:
            fired["H"] = f"H:{rule.attach[key]}"
        if not fired:
            if sup:
                support[tid] = sup
            continue
        if topic and topic in rule.same_as_topic:
            dropped[tid] = f"the bill's topic is {bill.get('topic')}"
            continue
        best = next(t for t in TIERS if t in fired)
        tags[tid] = {"tier": best, "why": fired[best], "fired": [t for t in TIERS if t in fired]}
    return {"tags": tags, "dropped": dropped, "support": support}


# ------------------------------------------------------------------ the data

def load_bills(root=None):
    """Every bill of every term as the engine reads it, newest term first:
    {term, bill, title, analysis, chapters, topic, provisions, duties}. From data/bills.json, the two
    text files (bill_text.json wins over archive_text.json, as topic_model reads
    them) and topics_assigned.json; the analysis and the chapters the bill amends
    are found as topic_model finds them."""
    root = Path(root) if root else ROOT
    bills = json.loads((root / "data" / "bills.json").read_text(encoding="utf-8"))
    texts = load_texts(root)
    ap = root / "topics_assigned.json"
    assigned = json.loads(ap.read_text(encoding="utf-8")) if ap.is_file() else {}
    out = []
    for term in sorted(bills, reverse=True):
        for bid, rec in bills[term].items():
            topic = rec.get("subject") or (assigned.get(term, {}).get(bid) or {}).get("subject") or ""
            out.append(engine_bill(term, bid, rec.get("title"), texts.get(term, {}).get(bid, ""), topic))
    return out


def engine_bill(term, bid, title, text, topic):
    """One bill as the engine reads it, from its title, its text and its topic: {term, bill, title,
    analysis, chapters, topic, provisions, duties}, the analysis and the chapters it amends found as
    topic_model finds them. load_bills and site_tags both read a bill through this."""
    import topic_model as TM
    text = text or ""
    ch = TM.operative_chapters(text)
    if not ch:
        ch = TM.rsa_chapters(text)[0]
    title = TM.NEWTITLE.sub("", title or "")
    return {"term": term, "bill": bid, "title": title, "analysis": TM.analysis_of(text).strip(),
            "chapters": sorted(norm_chapter(c) for c in ch), "topic": topic or "",
            "provisions": provisions(text), "duties": duties(f"{title}. {text}")}


def load_texts(root=None):
    """{term: {bill: text}}, archive_text.json under bill_text.json."""
    root = Path(root) if root else ROOT
    out = collections.defaultdict(dict)
    for name in ("archive_text.json", "bill_text.json"):
        p = root / name
        if not p.is_file():
            continue
        for term, by_bill in json.loads(p.read_text(encoding="utf-8")).items():
            for b, v in by_bill.items():
                t = (v or {}).get("text") or ""
                if t or b not in out[term]:
                    out[term][b] = t
    return out


def tag_all(rules, bills):
    """{term/bill: result of tag_bill} over `bills`, in their order."""
    return {f"{b['term']}/{b['bill']}": tag_bill(rules, b) for b in bills}


# ------------------------------------------------------------------ the site
#
# WHAT THE PAGES SHOW (stages 3 and 4 of the design, 17 November 2026), and
# ONLY ONCE THE OWNER HAS APPROVED THE LIST: the switch is her copying a
# registry to corrections/tags.json. build_site_v2 asks in_force() and, where
# it answers, puts each bill's tags in its record ("tags": [{id, name, why}])
# and its index row (positions in meta.json's list), and meta.json the list
# and the words that lead to it (site_meta). A tag's name and definition are
# the registry's words and the page adds none of its own (design 6.3).

SITE_CACHE = "bill_tags"


def in_force(path=None):
    """The registry the site shows: {"tags": {id: entry}, "synonyms": {word: target}, "digest": sha256
    of the file}, or None where corrections/tags.json -- under the folder the build runs in -- is not
    there or holds no tag. Never the fixture and never GRANITE_TAGS. A registry validate() finds a
    problem with stops the build, saying each, rather than putting half a list on the pages."""
    import hashlib
    p = Path(path) if path else REGISTRY
    if not p.is_file():
        return None
    raw = p.read_bytes()
    try:
        d = json.loads(raw.decode("utf-8"))
    except ValueError as e:
        raise SystemExit(f"{p} is not JSON: {e}")
    if not isinstance(d, dict):
        raise SystemExit(f"{p}: a registry is a JSON object of tags")
    if "tags" in d:
        reg, syn = d.get("tags") or {}, d.get("synonyms") or {}
    else:
        reg, syn = {k: v for k, v in d.items() if isinstance(v, dict)}, {}
    if not isinstance(reg, dict) or not isinstance(syn, dict):
        raise SystemExit(f"{p}: \"tags\" and \"synonyms\" are each a JSON object")
    if not reg:
        return None
    bad = validate(reg, None, syn)
    if bad:
        raise SystemExit(f"{p} has {len(bad)} problem(s), and no tag is put on a page until it has "
                         "none: " + "; ".join(bad[:10]) + (" ..." if len(bad) > 10 else ""))
    return {"tags": reg, "synonyms": syn, "digest": hashlib.sha256(raw).hexdigest()}


# THE CAP (the owner, 17 November 2026: "we should potentially cap the number of total tags that a bill can
# have since 17 seems a bit excessive so maybe something like 10 that are the best matches"). A bill the
# rules give more than MAX_TAGS keeps its best-matched MAX_TAGS on the site. site_tags is the one place that
# applies it, so the record, the index row (the page's foot list, the Tags filter, the tag search) and
# meta.json's list all take the same tags. Best is the engine's own evidence, strongest first:
#
#     hand                 a person's word on the bench (H), which a count never takes off
#     title                a phrase of the tag's in the bill's title (T)
#     analysis             one in the drafters' analysis (A)
#     provision            the bill writes a chapter or an article of that name (R)
#     chapter with a word  it amends a chapter dedicated to the subject and says one of its words (R)
#     chapter              it amends such a chapter (R)
#     duty                 it gives the office a duty or a power (R): last, since a duty the text restates
#                          beside the change counts too
#
# and between two of one kind, first the one more kinds of evidence attach (a title, an analysis and a
# chapter beat a title alone), then the one the bill names more often -- its words in the title and the
# analysis, and the duties the text gives its office (without the duties, 18 of the record's 21 bills over
# ten had the line drawn by the registry's order, between offices the title and analysis never name) --
# then the registry's order. A tag is weighed on the bill alone, never by how many bills it has elsewhere, so a
# bill's tags move only when it or the registry does. What is kept stays in the registry's order.

_STRENGTH = ("hand", "title", "analysis", "provision", "chapter with a word", "chapter", "duty")


def evidence(rule, bill, v):
    """(the kind of evidence one tag of tag_bill's answer, `v`, rests on, as _STRENGTH names it; how many
    kinds attach it; how many times the bill names it: its words in the title and the analysis, and the duties
    the text gives its office), for best_tags.
    `bill` is the engine's (engine_bill), `rule` the tag's."""
    fired, why = v["fired"], v["why"][2:]
    if "H" in fired:
        kind = "hand"
    elif "T" in fired:
        kind = "title"
    elif "A" in fired:
        kind = "analysis"
    elif why in (bill.get("provisions") or []):
        kind = "provision"
    elif why.startswith("RSA ") and why.endswith(" with a word"):
        kind = "chapter with a word"
    elif why.startswith("RSA ") and why[4:] in {norm_chapter(c) for c in bill.get("chapters") or []}:
        kind = "chapter"
    else:
        kind = "duty"
    t, a = rule.blank(bill.get("title") or ""), rule.blank(bill.get("analysis") or "")
    words = {p: rx for p, rx in rule.title + rule.analysis + rule.with_words}
    said = sum(len(rx.findall(t)) + len(rx.findall(a)) for rx in words.values())
    said += sum(1 for d in bill.get("duties") or [] if any(rx.search(rule.blank(d)) for _p, rx in rule.duties))
    return kind, len(fired), said


def ranked(rules, bill, tags):
    """The ids of tag_bill's `tags` for `bill`, the best-matched first (THE CAP)."""
    at = {t: i for i, t in enumerate(rules)}

    def key(tid):
        kind, kinds, said = evidence(rules[tid], bill, tags[tid])
        return _STRENGTH.index(kind), -kinds, -said, at[tid]
    return sorted(tags, key=key)


def best_tags(rules, bill, tags, cap=None):
    """tag_bill's `tags` for `bill` as the site shows them: every one where there are `cap` (MAX_TAGS) or
    fewer, else the `cap` best-matched (ranked), still in the registry's order."""
    cap = MAX_TAGS if cap is None else cap
    if len(tags) <= cap:
        return tags
    keep = set(ranked(rules, bill, tags)[:cap])
    return {t: v for t, v in tags.items() if t in keep}


def site_tags(bills, doc, folder=None):
    """{(term, bill): {id: why}}, in the registry's order, for every bill a tag attaches to (tag_bill), at
    most MAX_TAGS a bill, its best-matched (best_tags): `bills` gives (term, bill, title, text, topic) for
    each, `doc` is in_force()'s.

    Each bill's answer is kept in the build's cache (build_cache.py) by the registry's bytes, the
    bill's title, text and topic, and this code, since the rules read every bill's text: about 13 ms
    a bill on the laptop, seven minutes over the record cold, and a night on which neither the
    registry nor a bill moved works out none. `folder` is the cache's (None: the build's own)."""
    import build_cache as BC
    sig = BC.signature("tag_rules.py")
    kept = BC.load(SITE_CACHE, sig, folder)
    rules = compile_registry(doc["tags"])
    used, out = {}, {}
    for term, bid, title, text, topic in bills:
        key = BC.digest(sig, doc["digest"], term, bid, title or "", text or "", topic or "")
        got = kept.get(key)
        if not isinstance(got, dict):
            eb = engine_bill(term, bid, title, text, topic)
            got = {tid: v["why"] for tid, v in best_tags(rules, eb, tag_bill(rules, eb)["tags"]).items()}
        used[key] = got
        if got:
            out[(term, bid)] = got
    BC.save(SITE_CACHE, sig, used, folder)
    return out


def site_meta(doc, tagged, topics):
    """meta.json's keys for the tags: {} where no bill carries one, else

        "tags"       the registry's tags some bill carries, in its order, each {id, name, group,
                     definition} in the registry's words and no others;
        "tag_words"  what a reader may type and where it leads (synonym_table): a tag of that list,
                     "tag:ID", or one of `topics`, "topic:Name". A word leading anywhere else is
                     left out.

    `tagged` is site_tags()'s answer."""
    reg = doc["tags"]
    carried = {t for got in tagged.values() for t in got}
    tags = [{"id": t, "name": e["name"], "group": e.get("group") or "", "definition": e["definition"]}
            for t, e in reg.items() if t in carried]
    if not tags:
        return {}
    ids, topics = {t["id"] for t in tags}, set(topics)
    table, _conflicts = synonym_table(reg, doc.get("synonyms"))
    words = {w: to for w, to in sorted(table.items())
             if (to.startswith("tag:") and to[4:] in ids) or (to.startswith("topic:") and to[6:] in topics)}
    return {"tags": tags, "tag_words": words}


# ------------------------------------------------------------------ the command

def explain(rules, bill):
    r = tag_bill(rules, bill)
    print(f"{bill['term']} {bill['bill']}  topic: {bill.get('topic') or '-'}")
    print(f"  title:    {bill['title']}")
    print(f"  analysis: {(bill['analysis'] or '-')[:300]}")
    print(f"  chapters: {', '.join(bill['chapters']) or '-'}")
    if bill.get("provisions"):
        print(f"  writes:   {'; '.join(bill['provisions'])}")
    if bill.get("duties"):
        print(f"  duties:   {'; '.join(bill['duties'][:12])}" + (" ..." if len(bill["duties"]) > 12 else ""))
    for tid, v in r["tags"].items():
        print(f"  TAG {tid:30} {v['tier']}  {v['why']}   (fired: {', '.join(v['fired'])})")
    for tid, why in r["dropped"].items():
        print(f"  dropped {tid}: {why}")
    for tid, ch in r["support"].items():
        print(f"  supporting only {tid}: RSA {', '.join(ch)}")
    if len(r["tags"]) > GUIDE_TAGS:
        print(f"  over the guide of {GUIDE_TAGS} tags: {len(r['tags'])}")
    if len(r["tags"]) > MAX_TAGS:
        kept = best_tags(rules, bill, r["tags"])
        print(f"  over the cap of {MAX_TAGS}: the site leaves off "
              + ", ".join(t for t in ranked(rules, bill, r["tags"]) if t not in kept))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bill", nargs=2, metavar=("TERM", "BILL"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--registry")
    ap.add_argument("--root", help="where data/bills.json and the text files are (default: the repository)")
    a = ap.parse_args()
    reg, source = load_registry(a.registry)
    syn = read_doc(a.registry).get("synonyms", {})
    print(f"registry: {len(reg)} tags, from {source}; {len(syn)} synonyms")
    if a.check or not a.bill:
        bad = validate(reg, known_topics(a.root), syn)
        for b in bad:
            print("  " + b)
        print("registry ok" if not bad else f"{len(bad)} problem(s)")
        return 1 if bad else 0
    rules = compile_registry(reg)
    for b in load_bills(a.root):
        if (b["term"], b["bill"]) == tuple(a.bill):
            explain(rules, b)
            return 0
    print("no such bill")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
