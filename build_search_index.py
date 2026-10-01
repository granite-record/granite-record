#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-01.2
"""
What each bill is about, in its own words, as a file the search can ask.

    python3 build_search_index.py                       # every term; writes site/sidx/
    python3 build_search_index.py --terms 2025-2026     # that term's file only
    python3 build_search_index.py --idx D:/nh/site/idx --bill-text D:/nh/bill_text.json \\
        --archive-text D:/nh/archive_text.json --app app.js --out scratch/sidx
    python3 build_search_index.py --fixture tests/search_cases.json   # preflight's copy

No network. Standard library only. It reads the index build_site_v2 wrote
(site/idx/<term>.json), the text of the bills (bill_text.json for the current
term, archive_text.json for the terms before it) and app.js, and writes one
file per term, site/sidx/<term>.json, plus site/sidx/manifest.json with what
each holds and what it weighs, and site/sidx/words.json: every word the bills
use (EVERY WORD, below).

WHY IT EXISTS

The bill search read a title, a sponsor's name and a committee's name. On 1
October the person asked for a search "smart enough to find what a user is
likely looking for if they don't know the bill number, so that may also include
the bill text itself or the topic". A table of public words (app.js, CONCEPTS)
had just been measured against fifteen searches nobody had written an entry
for, and recovered none of them: a table covers what somebody thought of. The
bills' own text covers what the bills say.

The text cannot go to the reader: 16 MB for one term, 196 MB for the archive.
So the build reduces it, per term, to the words each bill is ABOUT, and the
page fetches that file only when somebody searches.

WHAT COUNTS AS ABOUT

A word used once in a 40-page budget bill is not a bill about that word. For
each word of each bill this works out how central it is, from two things:

  - the drafters' ANALYSIS, the summary printed above the bill. A word there
    is the drafters' own account of the bill, and counts for more;
  - the text under it, with the fiscal note taken off (a third of the text of
    a bill that has one, and about what the bill costs rather than what it
    does). How often the bill uses the word, set against how long the bill
    is. This is the usual measure (BM25's term weight: tf / (tf + k1 * (1 - b
    + b * length / usual length))) and nothing invented here. Twice in a bill
    of ordinary length comes to 0.57; once in the budget trailer to 0.01.

A word is kept for a bill when
  - it is in the analysis (unless the analysis is the budget's, thousands of
    words long); or
  - the text uses it at least twice, and either that comes to CENTRAL or
    more -- about one word in a hundred of the bill -- or it is one of the
    bill's TELLING most telling words: the ones this bill uses and few other
    bills do, which is the same measure times the usual weight for a rare
    word (the logarithm of how few bills use it).
The weight kept is 1 to 9, and the page lists the strongest first. Words in
the bill's own title are left out: the page already has the title and reads
it first.

WHY IT IS THAT STRICT. Read against the bills (1 October). With every word a
text used twice kept, "teachers" listed 60 bills: the cost of an adequate
education (teacher salaries are an element of it), four retirement bills
(teachers are a group in the system). With one mention kept it was worse:
"social media" in a bill about posting election returns, "library" in the
membership of a solid waste working group, "bathroom" in a rent registry
that counts them. Those bills mention the word; they are not about it.

AND ONE MENTION IS SOMETIMES ALL THERE IS. The four vetoed bills the person
called the bathroom bills say "lavatory" once each, in the text and nowhere
else. So for the wording app.js's table names, a mention that is not central
is kept too, at weight 0, and the page counts a weight of 0 only where the
table asks for two things at once and the bill has both (its `with` rule: a
lavatory AND biological sex). On its own a weight of 0 finds nothing.

Phrases are kept only where the page can ask for one: every string of two
words or more in app.js's CONCEPTS and SYN ("gender identity", "risk
protection order"). They are read here exactly as app.js reads them in a
title -- the phrase, with an ending on its last word -- and preflight holds
the two readings together. A phrase has no rank among a bill's words. One a
reader types ("law enforcement") is kept when it is in the analysis or
central; one the table lists as the bills' own wording ("gender transition",
"risk protection order") is chosen for being specific, and is kept when the
text uses it twice and that comes to FLOOR.

Matter a bill removes is printed [in brackets] and is still the bill's text:
HB 712 of 2025 retitles the chapter on "[genital] gender [reassignment]
surgery". The brackets are read as spaces, so the phrase is found.

WHAT THE FILE IS

    {"v": 1, "term": "2025-2026", "n": 2243, "ids": ["HB561", ...],
     "w": {"lavatory": [n, n, ...], ...},     one word, plural read as singular
     "p": {"gender identity": [n, ...], ...}} a phrase the page can ask for

Each n is one bill: (its place in ids, counted from the one before) * 20, plus
10 if the word is in the analysis, plus the weight, 0 to 9. A bill is named by its id,
never by its row in the index, so a file left over from an older build can
only fail to find a bill, never find the wrong one.

EVERY WORD

    {"v": 1, "n": 33000, "words": "aback abandon abandoned ..."}

sidx/words.json is every word of five letters or more in any bill's title,
sponsor, committee, topic or text, in any term, and in the names of members
and towns (careers.json, places.json). The page fetches it only when a search
has listed nothing, to tell a misspelt word ("medicade") from a real one that
no bill of the term is about ("incest", "Syria", a former member's surname).
Only the first is offered as another word. Without it the page read "incest"
as "invest" and said no bill says incest, when three do. A word used once, in
one bill, is in it: the file answers "has any bill said this", not "is any
bill about it".

A WRITER RUN ON A SUBSET DESTROYS THE REST, so this one cannot: a file is one
term's, --terms writes only the terms named, and the manifest is read and
merged rather than rewritten. words.json is every term's, so a run with
--terms leaves it as it is.

SILENCE IS NOT SUCCESS. A term with bills and no text at all is said out
loud; and if the texts were asked for and none could be read for any term the
run fails rather than leave nineteen empty files that look like an index.
"""

import argparse
import gzip
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

VERSION = 1

# A word the text uses is central to the bill from this much: three times in
# a bill of half the ordinary length, nine in one of ordinary length.
CENTRAL = 0.7
# Or it is one of this many of the bill's most telling words, and comes to at
# least FLOOR: twice in a bill of ordinary length is 0.57; twice in one three
# times that length is 0.32 and is not kept.
TELLING = 12
FLOOR = 0.36
# A word in the analysis is kept from this much: once in an analysis of up to
# about 190 words. HB 2's analysis is 5,900 words and one mention there is
# 0.01.
FLOOR_ANALYSIS = 0.2
# A mention in the text of wording the table names that is not central: kept
# at weight 0 from this much, which is one mention in a bill of up to about
# twice the ordinary length.
FLOOR_ONCE = 0.25
# A word that this share of a term's bills use is boilerplate -- "shall",
# "section", "amend" -- and names no bill.
COMMON = 0.30
# A word in the text of more than this share of a term's bills -- "court",
# "town", "health", "school" -- is kept for a bill only where its analysis
# has it, or the text leans on it harder still (VERY_CENTRAL: about one word
# in forty). Used that widely, how often a text uses it tells one bill from
# another badly: "court" listed 216 bills of 2025-2026 with the text counted
# as for any other word, and 46 by title.
BROAD = 0.10
VERY_CENTRAL = 0.85
# Neither share means anything among a handful of bills, where a word in two
# of eight would be "boilerplate": a word is common or broad only when at
# least this many bills use it. A term has 1,500 to 2,200.
FEW = 25
K1, B = 1.5, 0.75
# The analysis counts for more than the text: it is the drafters' summary.
ANALYSIS_WORTH = 1.6
# An analysis of ordinary length is about 27 words. HB 2's is 5,900.
USUAL_ANALYSIS = 27

# The same marks build_site_v2.bill_text_block cuts on, with the resolving
# clause added: a CACR opens "Be it Resolved by the House of Representatives",
# which that split does not know, so the 31 constitutional amendments of
# 2025-2026 have their analysis read as text there. Here it only decides how
# much a word counts for, and a word in the analysis must count as one.
ENACTING = re.compile(
    r"^\s*(?:Be it (?:Enacted|Resolved)|That the following|Whereas\b|RESOLVED\b)",
    re.M | re.I)
DASH_RULE = re.compile(r"^[\s\-\u2013\u2014_=]{10,}$", re.M)
ANALYSIS_HEAD = re.compile(r"^[\s\u2500-\u257F_=-]*(?:[A-Z]+\s+)?ANALYSIS\s*", re.I)
# Where the fiscal note begins: a line reading "LBA" or "LBAO", or one that
# is the note's own heading ("HB 550-FN- FISCAL NOTE", "FISCAL NOTE for an act
# ..." before 2000). fiscal.parse takes off only the table.
FISCAL_NOTE = re.compile(
    r"^[ \t]*(?:LBAO?[ \t]*$|(?:[A-Z]{2,4} ?\d+[^\n]{0,24})?FISCAL NOTE\b)", re.M)
# The drafting legend and the bill's formal opening: about every bill, so
# about none. Their words would be dropped as common anyway; taking the lines
# off keeps them out of the count of how long a bill is.
FURNITURE = re.compile(
    r"^\s*(?:Explanation:.*|Matter (?:removed|added|which is).*|"
    r"\[?\s*in brackets and struck ?through.*|STATE OF NEW HAMPSHIRE|"
    r"In the Year of Our Lord.*|Be it (?:Enacted|Resolved).*)$", re.M | re.I)


def split(text):
    """(analysis, body) of a bill's text, the fiscal note taken off the body."""
    text = text or ""
    cut = ENACTING.search(text)
    head = text[:cut.start()] if cut else ""
    rest = text[cut.start():] if cut else text
    rule = DASH_RULE.search(head)
    if rule:
        rest = head[rule.end():] + "\n" + rest
        head = head[:rule.start()]
    analysis = ANALYSIS_HEAD.sub("", head.strip()).strip()
    note = FISCAL_NOTE.search(rest)
    if note:
        rest = rest[:note.start()]
    return analysis, FURNITURE.sub("", rest)


# --- reading words the way app.js reads them --------------------------------

STEMKEEP = {"news", "arms", "dues"}
# Words that say nothing in any text. Most are dropped as common anyway; this
# is for the few that are not ("upon", "whom"), and for a corpus too small to
# have a common word.
FUNCTION = set("""a about above after again all also am an and any are as at be
because been before being below between both but by can did do does doing down
during each few for from further had has have having he her here hers him his
how if in into is it its itself may more most must my no nor not of off on once
only or other our out over own same shall she should so some such than that the
their them then there these they this those through to too under until up upon
very was we were what when where which while who whom why will with within
without would you your""".split())


def stem(w):
    """app.js's stem(): a plural read as its singular. preflight runs both
    over the same words and fails if they ever differ."""
    if len(w) < 4 or re.search(r"(ss|us|is)$", w) or w in STEMKEEP:
        return w
    if len(w) == 4:
        return w[:-1] if w.endswith("s") else w
    if w.endswith("ies"):
        return w[:-3] + "y"
    if re.search(r"(xes|ches|shes|sses)$", w):
        return w[:-2]
    return w[:-1] if w.endswith("s") else w


SPACES = re.compile(r"[ \t]+")


def norm(s):
    """Text as a title is searched: lower case, hyphens as spaces, a curly
    apostrophe as a straight one. And the brackets round removed matter as
    spaces, with runs of spaces as one, so that what they interrupt reads as
    the phrase it is: "gender [ reassignment ] surgery"."""
    s = (s or "").lower().replace("\u2019", "'").replace("\u2018", "'") \
        .replace("-", " ").replace("[", " ").replace("]", " ")
    return SPACES.sub(" ", s)


WORD = re.compile(r"[a-z][a-z0-9]*(?:'[a-z]+)?")
_KEY = {}


def words(text):
    """The words of normalised text, each as the key it is filed under."""
    out = []
    for w in WORD.findall(text):
        k = _KEY.get(w)
        if k is None:
            k = w[:-2] if w.endswith("'s") else w
            k = k.replace("'", "")
            k = _KEY[w] = stem(k) if len(k) > 1 else ""
        if k:
            out.append(k)
    return out


def phrase_rx(term):
    """app.js's altRx(), for a phrase: the phrase itself, or with an ending
    on its last word."""
    n = len(term) - term.rfind(" ") - 1
    ends = ("s?" if n < 3 else
            ("(?:s|es|ed|ing|ings)?" if re.search(r"[wxy]$", term) else "(?:s|es)?")
            if n == 3 else "(?:s|es|ed|d|ing|ings|er|ers|al)?")
    body = re.escape(term).replace("'", "['\u2019]")
    return re.compile(r"\b" + body + ends + r"\b")


# --- what the page's tables can ask for --------------------------------------

def word_keys(alt):
    """app.js's wordKeys(): the keys a word is looked up under -- itself, its
    singular, and itself with the endings a title match allows."""
    n = len(alt)
    ends = ([] if n < 3 else (["ed", "ing"] if re.search(r"[wxy]$", alt) else [])
            if n == 3 else ["ed", "d", "ing", "er", "al"])
    return {alt, stem(alt)} | {alt + e for e in ends}


def table_terms(app_js):
    """(phrases, words, wording phrases) the search's tables name, in app.js.

    phrases: every string of two words or more in SYN and in CONCEPTS -- what
    a reader may type as well as what a bill may say, since a typed phrase is
    looked for in the text too. The page asks this file for a phrase only when
    a table holds it, so those are the phrases worth counting.
    words, wording phrases: what CONCEPTS lists as the record's wording
    (`terms`, `named`, `with`), for which one mention in the text is kept, at
    weight 0.

    Read with regular expressions rather than a JavaScript parser: the tables
    are lists of quoted strings, and preflight asks node for the same lists
    and fails if these differ.
    """
    def block(name):
        m = re.search(r"^const %s=\[\n(.*?)^\];" % name, app_js, re.M | re.S)
        if not m:
            raise SystemExit(f"app.js: no 'const {name}=[' table to read")
        # A comment can hold a quoted word; a table line is never one.
        return "\n".join(l for l in m.group(1).split("\n")
                         if not l.lstrip().startswith("//"))

    def clean(t):
        return " ".join(norm(t).replace(",", " ").split())
    quoted = re.compile(r'"([^"\n]+)"')
    concepts = block("CONCEPTS")
    said = set()
    for part in re.findall(r"\b(?:terms|named|with):\[(.*?)\]", concepts, re.S):
        said.update(clean(t) for t in quoted.findall(part))
    typed = set(clean(t) for t in quoted.findall(block("SYN")))
    for part in re.findall(r"\bask:\[(.*?)\]", concepts, re.S):
        typed.update(clean(t) for t in quoted.findall(part))
    return (sorted(t for t in said | typed if " " in t),
            sorted(t for t in said if t and " " not in t),
            sorted(t for t in said if " " in t))


# --- one term ----------------------------------------------------------------

def centrality(tf, length, usual):
    return tf / (tf + K1 * (1 - B + B * length / usual)) if tf else 0.0


def build_term(term, rows, texts, table):
    """The file for one term, and a tally of what went into it."""
    phrases, table_words, table_phrases = table
    once_keys = set()
    for t in table_words:
        once_keys |= word_keys(t)
    once_phrases = set(table_phrases)
    ids = [r["id"] for r in rows if r.get("id")]
    docs = {}
    for r in rows:
        rec = texts.get(r.get("id")) or {}
        if rec.get("text"):
            a, b = split(rec["text"])
            docs[r["id"]] = (norm(a), norm(b), norm(r.get("title", "")))
    tally = {"bills": len(ids), "with_text": len(docs)}
    if not docs:
        return {"v": VERSION, "term": term, "n": len(ids), "ids": ids,
                "w": {}, "p": {}}, tally
    tok = {bid: (Counter(words(a)), Counter(words(b)), set(words(t)))
           for bid, (a, b, t) in docs.items()}
    la = {bid: sum(c[0].values()) for bid, c in tok.items()}
    lb = {bid: sum(c[1].values()) for bid, c in tok.items()}
    usual_b = sum(lb.values()) / max(1, sum(1 for v in lb.values() if v)) or 1
    df, df_text = Counter(), Counter()
    for a, b, _t in tok.values():
        df.update(set(a) | set(b))
        df_text.update(set(b))
    n_docs = len(tok)
    broad = {w for w, d in df_text.items() if d > max(BROAD * n_docs, FEW)}
    idf = {w: math.log(1 + n_docs / d) for w, d in df.items()}
    common = {w for w, d in df.items()
              if d > max(COMMON * n_docs, FEW)} - once_keys
    pos = {bid: i for i, bid in enumerate(ids)}
    w_post, p_post = {}, {}

    def weigh(tfa, tfb, bid, telling, once_ok):
        """The weight to keep, 0 to 9, or None for a word that is not kept.
        `telling`: one of the bill's most telling words, or a phrase of the
        table's wording. `once_ok`: the table names it, so a mention that is
        not central is kept at 0."""
        ca = centrality(tfa, max(la[bid], 1), USUAL_ANALYSIS) * ANALYSIS_WORTH
        cb = centrality(tfb, max(lb[bid], 1), usual_b)
        c = min(1.0, ca + cb)
        if (tfa and c >= FLOOR_ANALYSIS) or (
                tfb >= 2 and (cb >= CENTRAL or (telling and cb >= FLOOR))):
            return max(1, min(9, round(c * 9)))
        if once_ok and c >= FLOOR_ONCE:
            return 0
        return None

    for bid, (a, b, title) in tok.items():
        # The bill's most telling words: of those its text uses twice or
        # more, the ones few other bills use.
        ranked = sorted(((centrality(n, max(lb[bid], 1), usual_b) * idf[w], w)
                         for w, n in b.items() if n >= 2 and w not in common),
                        reverse=True)
        telling = {w for _s, w in ranked[:TELLING]}
        for w in set(a) | set(b):
            if w in title or w in common or w in FUNCTION:
                continue
            if w in broad and not a[w] and w not in once_keys and \
                    centrality(b[w], max(lb[bid], 1), usual_b) < VERY_CENTRAL:
                continue
            wt = weigh(a[w], b[w], bid, w in telling, w in once_keys)
            if wt is not None:
                w_post.setdefault(w, []).append((pos[bid], bool(a[w]), wt))
    # Phrases: counted in the text as written, since a phrase is its words in
    # order. A bill is read for a phrase only when it has every word of it
    # but the last, which may carry an ending.
    plan = []
    for p in phrases:
        need = [k[0] for k in (words(x) for x in p.split(" ")[:-1]) if k]
        plan.append((p, phrase_rx(p), need, p in once_phrases))
    for bid, (a, b, t) in docs.items():
        ta, tb, _tt = tok[bid]
        for p, rx, need, once_ok in plan:
            if any(not (ta[k] or tb[k]) for k in need):
                continue
            # The phrase as written is in whatever the pattern finds, and
            # looking for it plainly first is what makes nineteen terms a
            # minute's work rather than seven.
            in_a, in_b = p in a, p in b
            if not (in_a or in_b) or rx.search(t):
                continue          # not there, or the page finds it in the title
            tfa = len(rx.findall(a)) if in_a else 0
            tfb = len(rx.findall(b)) if in_b else 0
            if not (tfa or tfb):
                continue
            wt = weigh(tfa, tfb, bid, once_ok, once_ok)
            if wt is None:
                continue
            p_post.setdefault(p, []).append((pos[bid], bool(tfa), wt))

    def pack(posts):
        out, last = [], 0
        for i, in_a, w in sorted(posts):
            out.append((i - last) * 20 + (10 if in_a else 0) + w)
            last = i
        return out

    data = {"v": VERSION, "term": term, "n": len(ids), "ids": ids,
            "w": {w: pack(p) for w, p in sorted(w_post.items())},
            "p": {w: pack(p) for w, p in sorted(p_post.items())}}
    tally.update(words=len(w_post), phrases=len(p_post),
                 postings=sum(len(p) for p in w_post.values())
                 + sum(len(p) for p in p_post.values()))
    return data, tally


def read_posting(n):
    """(step, in the analysis, weight) -- the reverse of pack(), for checks."""
    return n // 20, n % 20 >= 10, n % 10


def unpack(data):
    """{key: [(bill id, in the analysis, weight), ...]} for "w" and for "p"."""
    out = {}
    for part in ("w", "p"):
        got = out[part] = {}
        for key, posts in (data.get(part) or {}).items():
            i, rows = 0, []
            for n in posts:
                step, in_a, w = read_posting(n)
                i += step
                rows.append((data["ids"][i], in_a, w))
            got[key] = rows
    return out


def only(data, keep):
    """The same file for a subset of its bills: what tests/search_index.json
    is, so that preflight can run real searches over real bills' own words
    without the 16 MB their text comes to."""
    ids = [i for i in data["ids"] if i in keep]
    pos = {b: i for i, b in enumerate(ids)}
    out = {"v": data["v"], "term": data["term"], "n": len(ids), "ids": ids}
    for part, posts in unpack(data).items():
        got = out[part] = {}
        for key, rows in posts.items():
            last, packed = 0, []
            for bid, in_a, w in rows:
                if bid in pos:
                    packed.append((pos[bid] - last) * 20 + (10 if in_a else 0) + w)
                    last = pos[bid]
            if packed:
                got[key] = packed
    return out


def pretty(o, depth=0):
    """JSON a person can read and a diff can show: one key to a line, and a
    short list of ids or words on one line rather than twenty."""
    pad = " " * depth
    if isinstance(o, dict) and o:
        return "{\n" + ",\n".join(
            f"{pad} {json.dumps(k, ensure_ascii=False)}: {pretty(v, depth + 1)}"
            for k, v in o.items()) + f"\n{pad}}}"
    if isinstance(o, list) and o:
        flat = json.dumps(o, ensure_ascii=False)
        if len(flat) <= 400 and not any(isinstance(x, dict) for x in o):
            return flat
        return "[\n" + ",\n".join(f"{pad} {pretty(x, depth + 1)}" for x in o) \
            + f"\n{pad}]"
    return json.dumps(o, ensure_ascii=False)


def write_fixture(cases_path, a, table, texts):
    """Refresh what preflight's search checks read, from the real record.

    tests/search_cases.json names real bills of one term. This copies each
    one's title, sponsor, committees and topic from the index as it stands
    (a title is never typed into that file), writes the slice of the term's
    search index for those bills beside it as search_index.json, and the
    text of the few bills the file lists under "texts" as search_texts.json,
    which is what the check that builds an index reads.
    """
    cases_path = Path(cases_path)
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    term = cases["term"]
    rows = json.loads((Path(a.idx) / f"{term}.json").read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows}
    named = set(cases.get("bills") or {})
    for c in cases["cases"]:
        # "near": bills a case names as tempting a wrong reading, carried so
        # that the fixture can be wrong in the way the real index could.
        for k in ("first", "must", "never", "near"):
            named.update(c.get(k) or [])
    named.update(cases.get("texts") or [])
    missing = sorted(named - set(by_id))
    if missing:
        raise SystemExit(f"{cases_path}: not bills of {term}: {', '.join(missing)}")
    cases["bills"] = {
        bid: {"n": by_id[bid].get("n", ""), "title": by_id[bid].get("title", ""),
              "sponsor": by_id[bid].get("sponsor", ""),
              "committees": by_id[bid].get("committees") or [],
              "topic": by_id[bid].get("topic", "")}
        for bid in sorted(named, key=lambda b: [r["id"] for r in rows].index(b))}
    cases_path.write_text(pretty(cases) + "\n", encoding="utf-8", newline="\n")
    data, _tally = build_term(term, rows, texts.get(term) or {}, table)
    part = only(data, named)
    (cases_path.parent / "search_index.json").write_text(
        dumps(part) + "\n", encoding="utf-8", newline="\n")
    want = cases.get("texts") or []
    (cases_path.parent / "search_texts.json").write_text(json.dumps({
        "_about": "The General Court's own text of a few real bills of "
                  + term + ", copied from bill_text.json by build_search_index.py "
                  "--fixture. preflight builds a search index from them and "
                  "holds what it says about each.",
        "term": term,
        "bills": {bid: {"title": by_id[bid].get("title", ""),
                        "text": (texts.get(term) or {}).get(bid, {}).get("text", "")}
                  for bid in want}}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print(f"fixture: {len(named)} bills of {term} refreshed in {cases_path}; "
          f"search_index.json holds {sum(len(v) for v in part['w'].values()) + sum(len(v) for v in part['p'].values()):,} "
          f"entries for them; search_texts.json holds {len(want)} texts")


# --- the texts ----------------------------------------------------------------

def load_texts(bill_text, archive_text):
    """{term: {bill: {"text": ...}}}: the current term's own text, and under
    it -- never over it -- the archived pages. archive_text.merge_into is the
    rule; it is repeated here in its ten lines so that this script imports
    nothing that could ask the General Court."""
    texts, said = {}, []
    for path, what in ((bill_text, "bill_text.json"),
                       (archive_text, "archive_text.json")):
        p = Path(path) if path else None
        if not p or not p.exists():
            said.append(f"{what}: not here ({path})")
            continue
        try:
            got = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            said.append(f"{what}: unreadable ({e})")
            continue
        n = 0
        for term, by_bill in got.items():
            if not isinstance(by_bill, dict):
                continue
            have = texts.setdefault(term, {})
            for bid, rec in by_bill.items():
                if isinstance(rec, dict) and rec.get("text") \
                        and not (have.get(bid) or {}).get("text"):
                    have[bid] = rec
                    n += 1
        said.append(f"{what}: {n:,} bill texts")
    return texts, said


def dumps(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


# --- every word the bills use -------------------------------------------------

# A word as the page reads a typed one: a run of letters. Five or more,
# because the page never offers another spelling for a shorter word.
KNOWN_WORD = re.compile(r"[a-z]{5,}")
# Fewer words than this and the file is not a vocabulary: one term's texts
# alone come to fifteen thousand.
WORDS_FEWEST = 10_000


def known_words(text):
    """The words of five letters or more in a string, as the page would read
    them if typed: lower case, a hyphen as a space."""
    return set(KNOWN_WORD.findall(norm(text)))


def strings(o):
    """Every string in a JSON value, keys included."""
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def name_words(paths):
    """The words in the names of members and towns, and what was read.

    careers.json is everyone with a recorded vote; places.json every town and
    ward. A former member who was never a bill's prime sponsor is in no
    index, and a surname is not a misspelling: for one day the header
    answered the name of a former senator with 2,052 bills about "house"."""
    got, said = set(), []
    for path in paths or ():
        p = Path(path)
        if not p.exists():
            said.append(f"{p.name}: not here")
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            said.append(f"{p.name}: unreadable ({e})")
            continue
        mine = set()
        for s in strings(data):
            mine |= known_words(s)
        got |= mine
        said.append(f"{p.name}: {len(mine):,} words")
    return got, said


def words_file(words):
    """sidx/words.json: {"v": 1, "n": N, "words": "a b c"}, in order."""
    ws = sorted(words)
    return {"v": VERSION, "n": len(ws), "words": " ".join(ws)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--idx", default="site/idx",
                    help="the folder of per-term bill indexes build_site_v2 wrote")
    ap.add_argument("--out", default="site/sidx")
    ap.add_argument("--bill-text", default="bill_text.json")
    ap.add_argument("--archive-text", default="archive_text.json")
    ap.add_argument("--app", default="app.js",
                    help="where the search's tables are, for the phrases it can ask for")
    ap.add_argument("--terms", nargs="*",
                    help="only these terms (the others' files are left alone)")
    ap.add_argument("--allow-no-text", action="store_true",
                    help="write the files even when no text at all could be read")
    ap.add_argument("--names", nargs="*", default=["careers.json", "places.json"],
                    help="files whose strings are names -- of members, of towns "
                         "-- and so are words, for sidx/words.json")
    ap.add_argument("--fixture", metavar="CASES",
                    help="refresh tests/search_cases.json's bills, and the "
                         "search_index.json and search_texts.json beside it, "
                         "from the real record; writes nothing else")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if a.fixture:
        table = table_terms(Path(a.app).read_text(encoding="utf-8"))
        texts, said = load_texts(a.bill_text, a.archive_text)
        for s in said:
            print("  " + s)
        write_fixture(a.fixture, a, table, texts)
        return

    idx = Path(a.idx)
    files = sorted(idx.glob("*.json"))
    if not files:
        raise SystemExit(f"{idx}: no bill index here -- run the site data "
                         "step (build_site_v2.py) first")
    if a.terms:
        want = set(a.terms)
        missing = want - {f.stem for f in files}
        if missing:
            raise SystemExit(f"{idx}: no index for {', '.join(sorted(missing))}")
        files = [f for f in files if f.stem in want]
    table = table_terms(Path(a.app).read_text(encoding="utf-8"))
    texts, said = load_texts(a.bill_text, a.archive_text)
    for s in said:
        print("  " + s)
    print(f"  {len(table[0])} phrases and {len(table[1])} single words of "
          "wording in the search's tables")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    man_path = out / "manifest.json"
    try:
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
        if not isinstance(manifest.get("terms"), dict):
            manifest = {"terms": {}}
    except (OSError, ValueError):
        manifest = {"terms": {}}
    manifest.update(v=VERSION, central=CENTRAL, telling=TELLING, floor=FLOOR)
    total_text = 0
    known = set()
    for f in files:
        term = f.stem
        rows = json.loads(f.read_text(encoding="utf-8"))
        rows = [r for r in rows if isinstance(r, dict)
                and (not r.get("term") or r["term"] == term)]
        if not a.terms:
            for r in rows:
                known |= known_words(" ".join(
                    [str(r.get("title") or ""), str(r.get("sponsor") or ""),
                     str(r.get("topic") or ""), *map(str, r.get("committees") or [])]))
            for rec in (texts.get(term) or {}).values():
                known |= known_words(rec.get("text") or "")
        data, tally = build_term(term, rows, texts.get(term) or {}, table)
        raw = dumps(data).encode("utf-8")
        (out / f"{term}.json").write_bytes(raw)
        tally.update(bytes=len(raw), gzip=len(gzip.compress(raw, 9, mtime=0)))
        manifest["terms"][term] = tally
        total_text += tally["with_text"]
        note = "" if tally["with_text"] else \
            "  -- NO TEXT for this term: its bills are found by title and topic only"
        print(f"  {term}: {tally['bills']:,} bills, {tally['with_text']:,} with "
              f"text, {tally.get('words', 0):,} words, "
              f"{tally.get('postings', 0):,} entries, {len(raw):,} bytes "
              f"({tally['gzip']:,} gzipped){note}")
    # EVERY WORD THE BILLS USE, for the page to tell a misspelt word from a
    # real one (app.js, A SEARCH THAT LISTS NOTHING). It is every term's, so
    # it is written only by a run over every term: one made from a subset
    # would call the rest of the record's words misspellings.
    words_path = out / "words.json"
    thin = False
    if a.terms:
        print(f"  words.json: left as it is ({'there' if words_path.exists() else 'NOT THERE'}"
              ") -- it is every term's words, and this run read "
              f"{len(files)} of them")
    else:
        names, said = name_words(a.names)
        for s in said:
            print("  names, " + s)
        known |= names
        thin = len(known) < WORDS_FEWEST
        if thin and not a.allow_no_text:
            # Not written: with a thin list every word it lacks would be
            # offered as some other word. With none the page offers nothing.
            if words_path.exists():
                words_path.unlink()
            manifest.pop("words", None)
        else:
            raw = dumps(words_file(known)).encode("utf-8")
            words_path.write_bytes(raw)
            manifest["words"] = {"n": len(known), "bytes": len(raw),
                                 "gzip": len(gzip.compress(raw, 9, mtime=0))}
            print(f"  words.json: {len(known):,} words the bills, members and "
                  f"towns use, {len(raw):,} bytes "
                  f"({manifest['words']['gzip']:,} gzipped) -- fetched only "
                  "when a search lists nothing")
    man_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
    t = manifest["terms"]
    print(f"search index: {len(files)} term files written to {out}; all "
          f"{len(t)} on record come to {sum(v['bytes'] for v in t.values()):,} "
          f"bytes, {sum(v['gzip'] for v in t.values()):,} gzipped")
    if not total_text and not a.allow_no_text:
        raise SystemExit(
            "search index: NOT ONE bill text was read, so every file written "
            "is empty and the search would read titles only. bill_text.json "
            "and archive_text.json are what it reads; --allow-no-text says "
            "that is expected.")
    if thin and not a.allow_no_text:
        raise SystemExit(
            f"search index: only {len(known):,} words were read from every "
            f"term's bills, fewer than {WORDS_FEWEST:,}, so words.json was "
            "NOT written and a misspelt search will be offered nothing. The "
            "texts are what it is read from; --allow-no-text says that is "
            "expected.")


if __name__ == "__main__":
    main()
