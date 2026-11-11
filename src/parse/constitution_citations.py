#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-11.1
"""
Which bills proposed to change each article of the Constitution, and which bills
and statutes cite it.

    python3 src/parse/constitution_citations.py            # writes constitution_citations.json
    python3 src/parse/constitution_citations.py --dry-run  # counts, writes nothing

Asks nobody: it reads archive_text.json and bill_text.json (every CACR and every
other bill), db/NH_RSA.psv (every statute section) and collected/constitution.json.
Standard library only. Written beside rsa_citations.json and whole every time (a
writer of a derived file run on a subset destroys the rest).

WHAT IT WRITES, constitution_citations.json at the root:

    {"asof": {...counts...},
     "articles": {"2:11": {"proposed": [[term, bill, verb], ...],
                           "bills": [[term, bill], ...],
                           "rsa": ["662-A:1", ...]}, ...}}

The key is "<part>:<article>". `proposed` is every CACR aimed at the article, from
the clause that says so (parse_constitution.cacr_targets); a CACR naming several
articles is listed under each (the person, 11 November 2026). verb is amend,
repeal, insert_after (a new article proposed to follow this one), reenact_part, or
new (the article this CACR would add, where its text numbers it and the Constitution
holds that number). `bills` and `rsa` are the non-CACR bills and the statute sections
whose text cites the article with a part named (parse_constitution.cited_articles);
a bare "Article 11" is not counted. The fate of each CACR is not here: it is the bill
page's own, read from the site's index when the Laws page is built.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json

import parse_constitution as PC
import rsa

ROOT = _paths.ROOT
OUT = ROOT / "constitution_citations.json"


def key(part, art):
    return f"{part}:{art}"


def build(con, texts, sections):
    """The file's content from {(term, bill): text} and {address: text}."""
    arts = {}

    def slot(part, art):
        return arts.setdefault(key(part, art), {"proposed": [], "bills": [], "rsa": []})

    n_cacr = n_targeted = 0
    for (term, bill), text in sorted(texts.items()):
        if bill.startswith("CACR"):
            n_cacr += 1
            ts = PC.cacr_targets(text, con)
            n_targeted += bool(ts)
            for t in ts:
                slot(t["part"], t["art"])["proposed"].append([term, bill, t["verb"]])
                if t.get("new"):
                    slot(t["part"], t["new"])["proposed"].append([term, bill, "new"])
        else:
            for part, art in PC.cited_articles(text, con):
                slot(part, art)["bills"].append([term, bill])
    for addr, text in sections.items():
        for part, art in PC.cited_articles(text, con):
            slot(part, art)["rsa"].append(addr)
    for v in arts.values():
        v["proposed"] = [list(x) for x in dict.fromkeys(map(tuple, v["proposed"]))]
    return {"asof": {"cacrs": n_cacr, "cacrs_targeted": n_targeted,
                     "bills_scanned": len(texts) - n_cacr, "rsa_sections_scanned": len(sections)},
            "articles": dict(sorted(arts.items()))}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--dry-run", action="store_true", help="count, write nothing")
    a = ap.parse_args()
    con = PC.load()
    if not con:
        print("constitution_citations: collected/constitution.json is not on this disk; nothing written")
        return 0
    texts = rsa.bill_texts()
    table = rsa.load()
    sections = {} if table is None else {k: s.text for k, s in table.sections.items() if not s.repealed}
    if not texts:
        print("constitution_citations: no bill text on this disk; nothing written")
        return 0
    data = build(con, texts, sections)
    asof = data["asof"]
    print(f"constitution_citations: {asof['cacrs']:,} CACRs, {asof['cacrs_targeted']:,} aimed at an article; "
          f"{sum(len(v['proposed']) for v in data['articles'].values()):,} listings under "
          f"{sum(bool(v['proposed']) for v in data['articles'].values())} articles; cited by "
          f"{sum(len(v['bills']) for v in data['articles'].values()):,} bill citations and "
          f"{sum(len(v['rsa']) for v in data['articles'].values()):,} statute citations"
          + ("" if table is not None else " (no statute table here: none of the second)"))
    assert asof["cacrs_targeted"], "no CACR was aimed at an article: the texts or the reader are wrong"
    if a.dry_run:
        return 0
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"  wrote {OUT.name}, {OUT.stat().st_size / 1e3:.0f} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
