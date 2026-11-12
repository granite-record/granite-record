#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.2
"""The tag rule engine: which tags a bill carries, and the evidence for each.

    python3 src/parse/tag_rules.py --bill 2023-2024 HB1596   # explain one bill
    python3 src/parse/tag_rules.py --check                   # read the registry, report problems

STAGE 1 OF THE TOPICS-AS-TAGS DESIGN (reports/topics-as-tags-design-2026-11.md,
sections 2 to 4). NOTHING IN THE BUILD READS THIS YET: no page, no index and no
export shows a tag until the owner has copied a registry into corrections/ and
a later stage reads this module. It asks no network and writes no file.

THE REGISTRY is a person's file, corrections/tags.json, which no generator
writes. Where it is absent the committed fixture (tests/tags_fixture.json, key
"registry") is read instead, so that a build and a check always have one, and a
clone shows no real tag. GRANITE_TAGS names another file (the owner's draft, in
reports/) for the bench and the counts; an explicit path argument wins over it.
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

The committee and the full text NEVER attach a tag.

A PHRASE is plain words: whole words, any case, a space and a hyphen standing
for each other, an apostrophe optional, a plural allowed ("mental health" never
matches "environmental health"). A trailing * opens the right end ("vaccin*"),
a leading = makes it case-sensitive ("=AI", "=THC"), "re:" begins a regular
expression, used as written. A chapter is "126-X"; a trailing * takes the
chapter and every lettered one under it ("159*").

A tag that equals the bill's assigned topic (same_as_topic) is dropped and
said to be, not attached twice. Nothing here caps the number of tags; a bill
over `GUIDE_TAGS` (5) is for the caller to report.

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
TIERS = ("T", "A", "R")

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
    out = []
    for i, tok in enumerate(re.split(r"[\s\-]+", p.strip())):
        if i:
            out.append(_HY + "+")
        out.append((_AP + "?").join(re.escape(x) for x in tok.split("'")))
    body = "".join(out)
    return re.compile(_LEFT + body + ("" if open_end else "(?:s|es)?" + _RIGHT), flags)


def chapter_matches(rule_chapter, chapter):
    """RSA chapter `chapter` against a rule's: exact, or "159*" for 159 and 159-B."""
    c = chapter.upper()
    if rule_chapter.endswith("*"):
        base = rule_chapter[:-1].upper()
        return c == base or c.startswith(base + "-")
    return c == rule_chapter.upper()


def norm_chapter(c):
    return str(c).upper().replace("‑", "-").strip()


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
        self.same_as_topic = {t.strip().lower() for t in entry.get("same_as_topic", [])}

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


def compile_registry(reg):
    return {tid: Rule(tid, e) for tid, e in reg.items() if isinstance(e, dict) and "rule" in e}


def validate(reg):
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
        if not isinstance(r, dict) or not (r.get("title") or r.get("analysis") or r.get("chapters_alone")):
            bad.append(f"{tid}: a rule needs a title, analysis or chapters_alone list")
            continue
        for key in ("title", "analysis", "not", "not_bill"):
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
        pair = e.get("pair")
        if pair is not None and not (isinstance(pair, list) and len(pair) == 2
                                     and all(re.fullmatch(r"\d{4}-\d{4}/[A-Z]+\d+", x) for x in pair)):
            bad.append(f"{tid}: a pair is two keys like 2023-2024/HB1596")
        if e.get("neutrality_hard") and not pair:
            bad.append(f"{tid}: neutrality is hard for this tag and it has no opposite-aim pair")
    return bad


# ------------------------------------------------------------------ the answer

def tag_bill(rules, bill, topic=None):
    """What the registry says of one bill.

    {"tags": {id: {"tier": best of T/A/R, "why": the evidence, "fired": [tiers]}},
     "dropped": {id: why}, "support": {id: [chapters]}}

    in registry order. `bill` carries title, analysis, chapters and, optionally,
    topic (the bill's assigned topic, for the redundancy drop)."""
    topic = (topic if topic is not None else bill.get("topic") or "").strip().lower()
    tags, dropped, support = {}, {}, {}
    for tid, rule in rules.items():
        fired, sup = rule.fire(bill)
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
    {term, bill, title, analysis, chapters, topic}. From data/bills.json, the two
    text files (bill_text.json wins over archive_text.json, as topic_model reads
    them) and topics_assigned.json; the analysis and the chapters the bill amends
    are found as topic_model finds them."""
    import topic_model as TM
    root = Path(root) if root else ROOT
    bills = json.loads((root / "data" / "bills.json").read_text(encoding="utf-8"))
    texts = load_texts(root)
    ap = root / "topics_assigned.json"
    assigned = json.loads(ap.read_text(encoding="utf-8")) if ap.is_file() else {}
    out = []
    for term in sorted(bills, reverse=True):
        for bid, rec in bills[term].items():
            text = texts.get(term, {}).get(bid, "")
            ch = TM.operative_chapters(text)
            if not ch:
                ch = TM.rsa_chapters(text)[0]
            title = TM.NEWTITLE.sub("", rec.get("title") or "")
            topic = rec.get("subject") or (assigned.get(term, {}).get(bid) or {}).get("subject") or ""
            out.append({"term": term, "bill": bid, "title": title, "analysis": TM.analysis_of(text).strip(),
                        "chapters": sorted(norm_chapter(c) for c in ch), "topic": topic})
    return out


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


# ------------------------------------------------------------------ the command

def explain(rules, bill):
    r = tag_bill(rules, bill)
    print(f"{bill['term']} {bill['bill']}  topic: {bill.get('topic') or '-'}")
    print(f"  title:    {bill['title']}")
    print(f"  analysis: {(bill['analysis'] or '-')[:300]}")
    print(f"  chapters: {', '.join(bill['chapters']) or '-'}")
    for tid, v in r["tags"].items():
        print(f"  TAG {tid:30} {v['tier']}  {v['why']}   (fired: {', '.join(v['fired'])})")
    for tid, why in r["dropped"].items():
        print(f"  dropped {tid}: {why}")
    for tid, ch in r["support"].items():
        print(f"  supporting only {tid}: RSA {', '.join(ch)}")
    if len(r["tags"]) > GUIDE_TAGS:
        print(f"  over the guide of {GUIDE_TAGS} tags: {len(r['tags'])}")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bill", nargs=2, metavar=("TERM", "BILL"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--registry")
    ap.add_argument("--root", help="where data/bills.json and the text files are (default: the repository)")
    a = ap.parse_args()
    reg, source = load_registry(a.registry)
    print(f"registry: {len(reg)} tags, from {source}")
    if a.check or not a.bill:
        bad = validate(reg)
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
