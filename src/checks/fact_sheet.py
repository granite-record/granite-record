#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-26.1
"""
A How-To guide's or a Learn page's every word, beside its evidence: for a
person, or an assistant, checking that the page says nothing its sources do
not.

    python3 src/checks/fact_sheet.py how-to-vote            # one page, to the screen
    python3 src/checks/fact_sheet.py --all logs/fact-sheets # every page, a file each
    python3 src/checks/fact_sheet.py --list                 # the slugs

WHY (26 October 2026). The person asked for the guides and Learn pages to be
reviewed "to make sure that information is backed up by the official
sources, and that future updates are able to maintain that level of
accuracy". The checks in preflight hold what a machine can hold -- every
dollar, share and count to its statute (guides.FIGURE, COUNT), every phone
number, email, hour, address and date to a claim (guides.unsourced_contacts),
every claim to a reading date (guide_ready) -- but not whether a sentence
says more than its source: "must" where the page said "may", a condition
dropped, a general truth nobody sourced. That takes a reader. This is what
the reader reads: the page as it prints, section by section, then the
FIGURES with the statute words that state them and the CLAIMS LEDGER, what
each source was recorded as saying and the day it was read.

The audit of that day ran eight reviewers over these sheets; it checked
1,904 statements and found 172 to put right. Run it again after any large
change to a page: a statement with no line of the ledger, no section of a
cited statute and no printout behind it is a finding.

No network: it reads the code and nothing else.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import html
import re

import civics
import guides


def plain(s):
    """Markup off, links kept as [link: address], one line per paragraph."""
    s = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 [link: \1]", s or "", flags=re.S)
    s = re.sub(r"</(p|li|h2|h3|tr|summary|details|div)>", "\n", s)
    s = re.sub(r"<li[^>]*>", "- ", s)
    s = re.sub(r"<(td|th)[^>]*>", " | ", s)
    s = re.sub(r"<summary[^>]*>", "\nQ: ", s)
    s = re.sub(r"<h2[^>]*>", "\n## ", s)
    s = re.sub(r"<h3[^>]*>", "\n### ", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t\xa0]+", " ", s)).strip()


def guide_sheet(g):
    out = [f"# GUIDE {g['slug']}: {g['title']}", f"BLURB: {plain(g.get('blurb', ''))}", "",
           "## AT A GLANCE", plain(g["glance"]), "", "## FLOW DIAGRAM"]
    for n in g["flow"]:
        if n[0] == "box":
            out.append("- " + plain(n[1]))
        else:
            out.append("- ASK " + plain(n[1]) + " -> " +
                       " / ".join(f"{a}: {plain(b)}" for a, b in n[2]))
    for i, s in enumerate(g["steps"], 1):
        out += ["", f"## STEP {i}: {plain(s['title'])}", plain(s["text"])]
        if s["note"]:
            out.append("NOTE: " + plain(s["note"]))
        out += [f"BUTTON: {plain(a)} -> {u}" for a, u in s["actions"]]
        if s["law"]:
            out.append("LAW CITED: " + ", ".join(s["law"]))
    out += ["", "## MORE (Common Questions and the rest)", plain(g["more"]), "",
            "## WHERE THIS COMES FROM"] + [f"- {a} -> {u}" for a, u in g["sources"]]
    out += ["", "## SEE ALSO"] + [f"- {a} -> {u}" for a, u in g["see"]]
    out += ["", "## FIGURES (as printed | the section or claim | its words)"]
    out += [f"- {f['text']} | {f['ref']} | {f['says']}" for f in g.get("figures") or []]
    out += ["", "## CLAIMS LEDGER ([day read] source :: what it was recorded as saying)"]
    for c in g["claims"]:
        extra = f" | its words: {c['words']}" if c.get("words") else ""
        tag = " (OBSERVED PRACTICE)" if c.get("observed") else ""
        out.append(f"- [{c['checked']}] {c['source']} :: {c['says']}{extra}{tag}")
    loose = guides.unsourced_contacts(g)
    if loose:
        out += ["", "## CONTACT DETAILS NO CLAIM RECORDS", "; ".join(loose)]
    return "\n".join(out) + "\n"


def learn_sheet(t):
    out = [f"# LEARN {t['slug']}: {t['title']}", f"BLURB: {plain(t['blurb'])}", "",
           plain(t["body"]), "", "## SOURCES"] + [f"- {s}" for s in t["sources"]]
    return "\n".join(out) + "\n"


def pages():
    return ([(g["slug"], "guide", guide_sheet, g) for g in guides.GUIDES]
            + [(t["slug"], "learn", learn_sheet, t) for t in civics.TOPICS])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", metavar="DIR", help="write every page's sheet into DIR")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    every = pages()
    if a.list:
        for slug, kind, _f, _p in every:
            print(f"{kind:6} {slug}")
        return 0
    if a.all:
        d = Path(a.all)
        d.mkdir(parents=True, exist_ok=True)
        for slug, kind, f, p in every:
            (d / f"{kind}-{slug}.md").write_text(f(p), encoding="utf-8")
        print(f"{len(every)} sheets in {d}")
        return 0
    hit = [(f, p) for slug, _k, f, p in every if slug == a.slug]
    if not hit:
        print(f"no guide or Learn page {a.slug!r}; --list names them")
        return 1
    for f, p in hit:
        sys.stdout.write(f(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
