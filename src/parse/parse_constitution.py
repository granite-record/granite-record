#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-17.1
"""
New Hampshire's Constitution, read into collected/constitution.json from the
pages nh.gov publishes it on.

    python3 src/parse/parse_constitution.py           # collected/constitution.json
    python3 src/parse/parse_constitution.py --check   # compare again; write nothing

    import parse_constitution as PC
    PC.load()                   # the file, or None where there is none
    PC.cacr_targets(body, PC.load())
        [{"verb": "amend", "part": 2, "art": "78", "href": "/laws#part2-art78",
          "label": "Part Second, Article 78"}]

WHAT IT READS. records/sources/constitution/, saved on 17 October 2026 at the
person's ask ("Can you fetch the constitution at least so we can present that
on the laws page"): index.txt, the state portal's own list of the
Constitution's pages, and one file for each page that list names -- Part
First, the Bill of Rights, on one page, and Part Second, the Form of
Government, on eleven, one a division. The host answered a script with 403, so
each page was read in a browser, and each file holds the page's table of
contents and every article its online book holds, as the page's own data
had them, under a comment naming the address, the day and the sha256 of what
follows. Nothing here asks the network, and nothing re-reads the portal: the
text changes only when an amendment is ratified, and then a person saves the
page again.

WHAT IT WRITES. Every article, numbered as the Constitution numbers them --
Part First 1 to 39 with the lettered ones (2-a, 2-b, 12-a, 28-a, 36-a), Part
Second 1 to 101 with theirs -- each with its heading as printed, its title,
its text a paragraph to an entry, and the portal's notes under it (the day
it was adopted, then every amendment) as printed. "toc" is each page's own
list, which the counts are held to; "repairs" says in words what the reading
put right, so that nothing it did is silent.

THE SOURCE, AS IT WAS ON 17 OCTOBER 2026, read before a line of this was
written. An article is a heading, "[Art.] 2-a. [The Bearing of Arms.]", and a
content block: the text, then <br>, then the notes, each a <span> of class
ml-5 (the adoption) or "ml-5 small" (an amendment). Four things in it are not
that shape, and each is handled by a rule rather than by naming the article:

  1. Part Second, Article 49-a's date opens a span with an unclosed quote,
     class="ml-5>November 28, 1984, and the browser read everything to the
     next quote as the attribute -- Article 50's whole row. So 49-a's block
     holds 50's heading and text. An article whose block holds a heading is
     two articles, and a class missing its closing quote is closed.
  2. Article 71's 1792 and 1877 notes are run together by markup the page
     escaped (&lt;/span&gt;&lt;br&gt;). The block is unescaped once before it
     is read, which makes the escaped markup markup again.
  3. Article 26 of Part Second is on the Senate page with its text and notes
     but missing from that page's own list. The counts say so by name.
  4. Article 61's number is printed "6l", with a letter l, in its heading and
     in the list. The number is read as 61 and the repair says so; the
     heading stays as printed.

Notes are kept as printed, typos and all ("June 2, 178", "19l2", "$l00"),
because they are the portal's words, and the oddities are listed.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import hashlib
import html
import json
import re

SOURCES = _paths.ROOT / "records" / "sources" / "constitution"
OUT = _paths.ROOT / "collected" / "constitution.json"
INDEX_URL = "https://www.nh.gov/glance/state-constitution"
PART_NAMES = {1: "Part First", 2: "Part Second"}

# A heading as the portal prints it: "Article 1. [Name.]", "[Art.] 2-a.
# [Title.]", "[Art.] 24 [Title.]" with no period, "[Art.] 54. [Title." with no
# closing bracket, and "[Art.] 6l." with a letter l for the 1.
HEADING = re.compile(r"^\s*(?:Article|\[Art\.\])\s+([0-9lI]+)(?:-([a-z]))?\.?\s*\[(.*?)\]?\.?\s*$", re.S)
OPTION = re.compile(r'<option value="([^"]*)">(.*?)</option>', re.S)
ARTICLE = re.compile(r'<article id="page-id-(\d+)" data-section="(\d*)">(.*?)</article>', re.S)
H4 = re.compile(r"<h4>(.*?)</h4>", re.S)
CONTENT = re.compile(r'<div class="content">\n(.*)\n</div>\s*$', re.S)
# The content block of an article that rode in inside another's (rule 1).
INNER_CONTENT = re.compile(r'<div class="online__book__page__content">(.*)$', re.S)
# A span class with no closing quote before its ">" (rule 1): class="ml-5>.
UNCLOSED = re.compile(r'class="(ml-\d[^"<>]*?)>')
NOTE = re.compile(r'<span\b[^>]*\bml-\d[^>]*>(.*?)</span>', re.S)
CELL = re.compile(r"<td>[^<]*</td>")           # the online book's number columns
TOP = re.compile(r'<div class="online__book__jump__to__top">.*?</div>', re.S)
NOTE_MARK = "\x01"
# A note the portal printed with a letter l among a number's digits ("19l2",
# "$l00") or a year cut short ("June 2, 178"): kept as printed, and listed.
ODD_NOTE = re.compile(r"\b\d+l\d*\b|\$l\d|\b[A-Z][a-z]+ \d{1,2}, \d{1,3}\b(?![\d,])")


def _num(raw):
    """("61", True) for the "6l" the portal prints; (raw, False) otherwise."""
    fixed = raw.replace("l", "1").replace("I", "1")
    return fixed, fixed != raw


def heading_parts(h):
    """(number, letter, title, repaired) from a heading, or None.

    "[Art.] 2-a. [The Bearing of Arms.]" -> ("2", "a", "The Bearing of Arms", False)."""
    m = HEADING.match(html.unescape(h))
    if not m:
        return None
    n, fixed = _num(m.group(1))
    title = re.sub(r"\s+", " ", m.group(3)).strip()
    # The heading's closing period goes, but not the one "etc." is spelled with.
    if not title.lower().endswith("etc."):
        title = title.rstrip(".").strip()
    return n, m.group(2) or "", title, fixed


def art_key(n, letter):
    return f"{n}-{letter}" if letter else n


def anchor(part, key):
    """The id an article carries on the Laws page: part1-art2-a."""
    return f"part{part}-art{key}"


def href(part, key=""):
    """/laws#part2-art78, or /laws#part2 for a whole part. The page's own path,
    never a bare '#': every page carries <base href="/">, and a bare hash
    resolves against the site's root."""
    return f"/laws#{anchor(part, key) if key else f'part{part}'}"


def label(part, key):
    return f"{PART_NAMES[part]}, Article {key}"


def _lines(block):
    """The block as (kind, text) lines: "text" for the article's own words,
    "note" for the portal's notes under it."""
    s = CELL.sub("", TOP.sub("", block))
    s = NOTE.sub(lambda m: f"\n{NOTE_MARK}{m.group(1)}\n", s)
    s = re.sub(r"<br\s*/?>|</?p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    out = []
    for raw in s.split("\n"):
        note = raw.startswith(NOTE_MARK)
        t = re.sub(r"\s+", " ", raw.replace(NOTE_MARK, "").replace("\xa0", " ")).strip()
        if not t:
            continue
        # A full stop left outside the span that held its sentence ("in
        # June</span>.<br>", Part Second, Article 25) belongs to that line.
        if out and re.fullmatch(r"[.,;:]+", t):
            out[-1] = (out[-1][0], out[-1][1] + t)
            continue
        out.append(("note" if note else "text", t))
    return out


def _article(part, heading, block, where, oddities):
    got = heading_parts(heading)
    if not got:
        raise ValueError(f"{where}: a heading this cannot read: {heading!r}")
    n, letter, title, fixed = got
    key = art_key(n, letter)
    lines = _lines(block)
    text, notes = [], []
    for kind, t in lines:
        if kind == "note":
            notes.append(t)
        elif notes:
            # The article's words after its notes have begun: kept, and said.
            oddities.append(f"{label(part, key)}: words after the notes, kept as text: {t[:60]}")
            text.append(t)
        else:
            text.append(t)
    if not text:
        raise ValueError(f"{where}: {label(part, key)} has no text")
    art = {"key": key, "num": n, "letter": letter, "anchor": anchor(part, key),
           "heading": re.sub(r"\s+", " ", html.unescape(heading)).strip(), "title": title,
           "text": text, "notes": notes, "repealed": text == ["(Repealed)"]}
    return art, fixed


def read_index(path):
    """(established, [(division, url)]) from index.txt: the portal's own words
    and its list of the Constitution's pages, Part First's first."""
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]
    established = next((ln for ln in lines if ln.startswith("Established")), "")
    pages, part = [], 0
    for ln in lines:
        if ln.startswith("Part First"):
            part = 1
        elif ln.startswith("Part Second"):
            part = 2
        elif " | " in ln and part:
            name, url = ln.split(" | ", 1)
            pages.append((part, name.strip(), url.strip()))
    return established, pages


def read_page(path):
    """(url, read, sha_ok, toc, articles) from one saved page."""
    t = path.read_text(encoding="utf-8")
    head, body = t.split("-->\n", 1)
    url = re.search(r"Source: (\S+)", head).group(1)
    read = re.search(r"Read: (\d{4}-\d{2}-\d{2})", head).group(1)
    want = re.search(r"sha256 of the body[^:]*: ([0-9a-f]{64})", head).group(1)
    sha_ok = hashlib.sha256(body.encode("utf-8")).hexdigest() == want
    nav = body[:body.index("</nav>")]
    toc = [(v, re.sub(r"\s+", " ", html.unescape(h)).strip()) for v, h in OPTION.findall(nav)]
    rows = []
    for pid, sec, inner in ARTICLE.findall(body):
        h = H4.search(inner)
        c = CONTENT.search(inner)
        if not h:
            continue                      # the online book's empty first row
        rows.append((pid, sec, h.group(1), c.group(1) if c else ""))
    return url, read, sha_ok, toc, rows


def parse(src=SOURCES):
    """The Constitution as collected/constitution.json holds it."""
    established, pages = read_index(src / "index.txt")
    by_url = {}
    for f in sorted(src.glob("*.html")):
        url, read, sha_ok, toc, rows = read_page(f)
        by_url[url] = (f.name, read, sha_ok, toc, rows)
    missing = [u for _, _, u in pages if u not in by_url]
    if missing:
        raise ValueError(f"the index names pages with no saved file: {missing}")
    parts = {1: [], 2: []}
    repairs, oddities, tocs, reads = [], [], [], set()
    for part, name, url in pages:
        fname, read, sha_ok, toc, rows = by_url[url]
        if not sha_ok:
            raise ValueError(f"{fname} is not what was read: its body's sha256 differs from its header")
        reads.add(read)
        arts = []
        for pid, _sec, heading, content in rows:
            block = UNCLOSED.sub(r'class="\1">', html.unescape(content))
            # Rule 1: a block that holds a heading is two articles.
            pieces = H4.split(block)
            art, fixed = _article(part, heading, pieces[0], fname, oddities)
            arts.append(art)
            if block != html.unescape(content):
                repairs.append(f"{fname}: in {label(part, art['key'])}, a note's span opened with no "
                               "closing quote on its class, and is closed")
            if fixed:
                repairs.append(f"{fname}: {label(part, art['key'])} is printed "
                               f"“{art['heading']}”; its number is read as {art['key']}")
            for k in range(1, len(pieces), 2):
                inner = INNER_CONTENT.search(pieces[k + 1])
                rider, fixed = _article(part, pieces[k], inner.group(1) if inner else "", fname, oddities)
                arts.append(rider)
                repairs.append(f"{fname}: {label(part, rider['key'])} was inside the row of "
                               f"{label(part, art['key'])} and is read as its own article")
                if fixed:
                    repairs.append(f"{fname}: {label(part, rider['key'])} number read as {rider['key']}")
        listed = []
        for _v, h in toc:
            got = heading_parts(h)
            if not got:
                raise ValueError(f"{fname}: a list entry this cannot read: {h!r}")
            listed.append(art_key(got[0], got[1]))
        have = [a["key"] for a in arts]
        tocs.append({"part": part, "page": name, "url": url, "file": fname, "listed": listed,
                     "not_listed": [k for k in have if k not in listed],
                     "listed_not_found": [k for k in listed if k not in have]})
        parts[part].append({"name": name, "url": url, "slug": "part%d-%s" % (part, _slug(name)),
                            "articles": arts})
    for t in tocs:
        for k in t["not_listed"]:
            oddities.append(f"{t['file']}: {label(t['part'], k)} is on the page but not in the "
                            "page's own list")
    for p, divs in parts.items():
        for d in divs:
            for a in d["articles"]:
                for nt in a["notes"]:
                    if ODD_NOTE.search(nt):
                        oddities.append(f"{label(p, a['key'])}: a note printed “{nt}”")
    return {
        "_source": {"index": INDEX_URL, "read": sorted(reads), "established": established,
                    "files": sorted(by_url[u][0] for _, _, u in pages)},
        "parts": [{"part": p, "name": PART_NAMES[p],
                   "title": "Bill of Rights" if p == 1 else "Form of Government",
                   "divisions": parts[p]} for p in (1, 2)],
        "counts": {f"part{p}": sum(len(d["articles"]) for d in parts[p]) for p in (1, 2)},
        "toc": tocs,
        "repairs": repairs,
        "oddities": oddities,
    }


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("etc.", "")).strip("-")


def articles(con):
    """[(part, article)] in the Constitution's order."""
    return [(p["part"], a) for p in (con or {}).get("parts", []) for d in p["divisions"]
            for a in d["articles"]]


def gaps(con):
    """{part: [numbers missing from 1..last]}: a number the Constitution has
    that the reading does not, which would be an article lost."""
    out = {}
    for p in (1, 2):
        nums = {int(a["num"]) for q, a in articles(con) if q == p}
        if nums:
            out[p] = [n for n in range(1, max(nums) + 1) if n not in nums]
    return out


def load(path=OUT):
    """collected/constitution.json, or None where there is none."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# WHAT A CACR SAYS IT CHANGES, read from its own resolving clauses (17 October
# 2026). Every CACR of 2025-2026 states its target in one of three forms:
#
#   I. That article 78 of the second part of the constitution be amended to
#      read as follows:                                   -> amend 2:78
#   II. That article 72-a of the second part of the constitution, relative to
#      the supreme and superior courts, be repealed.      -> repeal 2:72-a
#   I. That the first part of the constitution be amended by inserting after
#      article 2-b the following new article:             -> new after 1:2-b
#
# and "That articles 41, 42, 49, and 49-a of the second part ..." for several.
# A clause in any other wording -- "That the following new article of part I
# of the constitution after article 2-b:" (CACR 16) -- names nothing here: a
# link is drawn only where the clause leaves no doubt, and only to an article
# the Constitution as read holds.
_ARTS = r"(\d{1,3}(?:-[a-z])?(?:(?:,\s*(?:and\s+)?|\s+and\s+)\d{1,3}(?:-[a-z])?)*)"
_WHICH = {"first": 1, "second": 2}
CLAUSE_CHANGE = re.compile(
    r"\bThat\s+articles?\s+" + _ARTS + r"\s+of\s+the\s+(first|second)\s+part\s+of\s+the\s+constitution"
    r"(?:,[^,:.]{0,120},)?\s+(?:shall\s+)?be\s+(amended|repealed)\b", re.I)
CLAUSE_INSERT = re.compile(
    r"\bThat\s+the\s+(first|second)\s+part\s+of\s+the\s+constitution\s+(?:shall\s+)?be\s+amended\s+by\s+"
    r"inserting\s+after\s+article\s+(\d{1,3}(?:-[a-z])?)\s+the\s+following\b", re.I)
CLAUSE_PART = re.compile(
    r"\bThat\s+the\s+(first|second)\s+part\s+of\s+the\s+constitution\s+(?:shall\s+)?be\s+repealed\s+and\s+"
    r"reenacted\b", re.I)


def cacr_targets(body, con):
    """[{verb, part, art, href, label}] for the articles a CACR's text says it
    changes, in the order it says them; [] where it says none in a form above
    or names an article the Constitution as read does not hold."""
    have = {(p, a["key"]) for p, a in articles(con)}
    if not body or not have:
        return []
    out, seen = [], set()

    def add(verb, part, key):
        if key and (part, key) not in have:
            return
        k = (verb, part, key)
        if k in seen:
            return
        seen.add(k)
        out.append({"verb": verb, "part": part, "art": key, "href": href(part, key),
                    "label": label(part, key) if key else PART_NAMES[part]})

    found = []
    for m in CLAUSE_CHANGE.finditer(body):
        verb = "repeal" if m.group(3).lower() == "repealed" else "amend"
        for key in re.findall(r"\d{1,3}(?:-[a-z])?", m.group(1)):
            found.append((m.start(), verb, _WHICH[m.group(2).lower()], key))
    for m in CLAUSE_INSERT.finditer(body):
        found.append((m.start(), "insert_after", _WHICH[m.group(1).lower()], m.group(2)))
    for m in CLAUSE_PART.finditer(body):
        found.append((m.start(), "reenact_part", _WHICH[m.group(1).lower()], ""))
    for _, verb, part, key in sorted(found, key=lambda x: x[0]):
        add(verb, part, key)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--check", action="store_true", help="compare with the committed file; write nothing")
    a = ap.parse_args()
    con = parse()
    g = gaps(con)
    print(f"parse_constitution: {con['counts']['part1']} articles in Part First, "
          f"{con['counts']['part2']} in Part Second, from {len(con['_source']['files'])} pages read "
          f"{', '.join(con['_source']['read'])}")
    for p, missing in g.items():
        if missing:
            print(f"  {PART_NAMES[p]} has no article numbered {', '.join(map(str, missing))}")
    for r in con["repairs"]:
        print(f"  repaired: {r}")
    for o in con["oddities"]:
        print(f"  as printed: {o}")
    text = json.dumps(con, ensure_ascii=False, indent=1) + "\n"
    if a.check:
        same = OUT.is_file() and OUT.read_text(encoding="utf-8") == text
        print("parse_constitution: " + ("the committed file is what the source gives"
                                        if same else f"{OUT.name} differs from what the source gives"))
        return 0 if same else 1
    if any(g.values()):
        print("parse_constitution: an article number is missing; nothing written")
        return 1
    OUT.write_text(text, encoding="utf-8")
    print(f"parse_constitution: wrote {OUT.relative_to(_paths.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
