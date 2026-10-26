#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.7
"""
The site's translations: what is translated, what has gone stale, and the
proofreader's sheet out and back. src/pages/i18n.py says how a translation
is kept current; this is how a person works on one.

    python3 src/ops/translations.py                     # each language: drafts, proofread, problems
    python3 src/ops/translations.py --sheet es.csv      # the proofreader's sheet, every entry
    python3 src/ops/translations.py --sheet es.csv --drafts   # only what is still a draft
    python3 src/ops/translations.py --take es.csv       # their corrections and approvals, back in
    python3 src/ops/translations.py --set KEY "words"   # one entry, brought up to the code's English
    python3 src/ops/translations.py --drop-unused       # entries no code asks for any more

--lang names the language (es, the one there is so far). No network.

THE SHEET is a CSV a spreadsheet opens: the key, where on the site it is, the
English, the Spanish, its state, a note, and two columns for the proofreader
-- "corrected", the Spanish as it should read where it should change, and
"ok", where "yes" passes the entry (its Spanish, or the corrected one, as it
then stands). --take reads those two columns and nothing else, and refuses a
row whose English is no longer the code's -- the English changed while the
sheet was out -- rather than pass a translation of words the page no longer
says. Every row it changes is printed, and the catalog is written once, at
the end, only if every row it read was one it could take.

AN ENTRY BROUGHT UP TO NEW ENGLISH (--set) takes the code's English as it
stands and goes back to "draft": the proofreader has not seen it.

lang/<code>.json is the catalog. It is a person's file as well as the code's:
the drafts were written for the proofreader, and what they pass is theirs. No
build step writes it (preflight's HANDMADE rule holds that for corrections/
and review/; this file is in src/pages/lang/ because the code reads it beside
the words it translates).
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import json

import i18n

COLUMNS = ("key", "on the site", "english", "translation", "state", "note", "corrected", "ok")

# Where on the site a key's words are, by the key's first part: what the
# proofreader is told, in place of the file and line the code says it at.
AREAS = {"nav": "the header", "page": "the header", "theme": "Settings", "set": "Settings",
         "notice": "an English page, to a reader who chose Spanish",
         "home": "the home page", "card": "the home page's cards",
         "web": "the home page's webinar box", "state": "the home page's status box",
         "fresh": "the home page, under Coming up: a warning that the data is stale",
         "sess": "the home page's Recent Session Days: the floor sessions' players",
         "gloss": "the Glossary page, and the pop-up on a term", "cal": "Coming up (the week's meetings)",
         "kind": "Coming up: a kind of meeting", "find": "the search box's results",
         "search": "the search box", "yt": "Settings: Your town", "foot": "the footer",
         # The how-to guides (24 October 2026): a guide's own words keyed by
         # its page (guide.how-to-vote.*), and what the guides' pages say
         # around them.
         "guide": "the how-to guides (the page is the key's second part)",
         "guides": "the how-to guides, around the guide's own words",
         # The Learn pages (25 October 2026), keyed as the guides are, and
         # what Learn's pages say around their own words.
         "learn": "the Learn pages (the page is the key's second part)",
         "reps": "Finding Your Representatives: the worked example",
         "trrep": "the box for reporting a mistake in the translation",
         # Every first part the code uses has its place here (26 October
         # 2026): fifteen had none, so their rows went to the proofreader
         # with the column blank. preflight's _translations holds the two
         # lists the same.
         "rec": "the home page's Latest Activity: a committee's recommendation",
         "study": "the home page's Latest Activity: an interim study report",
         "vote": "the home page's Latest Activity: what a sitting did with a bill",
         "hub": "the Resources page's Learn and Official Sources tabs",
         "year": "the Learn page on the legislative year",
         "of": "the Officials page: its title, its tabs' names and their headings",
         "lf": "the Officials page: what Find Your Town finds, and the roster by county",
         "map": "the district map, on the Officials page's My Town tab",
         "off": "the Officials page's tabs: each office and who holds it",
         "elect": "the members-elect: the Officials page's Members-Elect tab, and Your Town",
         "comp": "the Officials page's Legislators tab: who holds the seats",
         "roster": "the Officials page's Legislators tab: the roster",
         "party": "the Officials page's Legislators tab: a party's name",
         "seat": "the Officials page's Legislators tab: the House seating chart",
         "sc": "the Officials page's Legislators tab: the line under the seating chart"}


def area(key):
    return AREAS.get(key.split(".")[0], "")


def path(lang):
    return i18n.LANG_DIR / f"{lang}.json"


def load(lang):
    return json.loads(path(lang).read_text(encoding="utf-8"))


def save(lang, data):
    """The catalog, keys in order, one entry to a few lines, so a change to
    one is a change to those lines in a diff."""
    data["strings"] = dict(sorted(data["strings"].items()))
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    path(lang).write_text(text, encoding="utf-8", newline="\n")
    i18n._CATALOGS.pop(lang, None)


def status(lang):
    data = load(lang)
    words, _p = i18n.code_words()
    st = [e.get("state") for e in data["strings"].values()]
    problems = i18n.check(lang)
    print(f"{lang} ({i18n.NAMES.get(lang, lang)}): {len(words)} words in the code; "
          f"{st.count('proofread')} proofread, {st.count('draft')} drafts; "
          f"{'offered to everyone' if data.get('offered') else 'not yet offered (unlisted)'}")
    for p in problems:
        print(f"  {p}")
    return 1 if problems else 0


def sheet(lang, out, drafts_only=False):
    data = load(lang)
    words, _p = i18n.code_words()
    n = 0
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for key in sorted(words):
            e = data["strings"].get(key, {})
            if drafts_only and e.get("state") == "proofread":
                continue
            w.writerow([key, area(key), words[key]["en"],
                        e.get(lang, ""), e.get("state", "missing"), e.get("note", ""), "", ""])
            n += 1
    print(f"{out}: {n} entries for the proofreader")


def take(lang, src):
    data = load(lang)
    words, _p = i18n.code_words()
    changed, refused = [], []
    with open(src, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get("key") or "").strip()
            fixed = (row.get("corrected") or "").strip()
            ok = (row.get("ok") or "").strip().lower() in ("yes", "y", "ok", "x", "sí", "si")
            if not key or not (fixed or ok):
                continue
            if key not in words:
                refused.append(f"{key}: no code asks for it any more")
                continue
            if row.get("english") != words[key]["en"]:
                refused.append(f"{key}: the English changed while the sheet was out "
                               f"(now {words[key]['en']!r})")
                continue
            e = data["strings"].setdefault(key, {"en": words[key]["en"], lang: "", "state": "draft"})
            new = fixed or e.get(lang) or ""
            if not new:
                refused.append(f"{key}: passed with no {lang} to pass")
                continue
            if i18n.places(new) != i18n.places(words[key]["en"]):
                refused.append(f"{key}: {new!r} has {sorted(i18n.places(new))} where the English "
                               f"has {sorted(i18n.places(words[key]['en']))}")
                continue
            before = (e.get(lang), e.get("state"))
            e["en"] = words[key]["en"]
            e[lang] = new
            e["state"] = "proofread" if ok else "draft"
            if before != (e[lang], e["state"]):
                changed.append(f"{key}: {before[0]!r} ({before[1]}) -> {new!r} ({e['state']})")
    for c in changed:
        print("  " + c)
    if refused:
        print(f"{len(refused)} rows could not be taken, so nothing was written:")
        for r in refused:
            print("  " + r)
        return 1
    save(lang, data)
    print(f"{path(lang)}: {len(changed)} entries changed")
    return 0


def set_one(lang, key, text):
    data = load(lang)
    words, _p = i18n.code_words()
    if key not in words:
        print(f"{key}: no code asks for it")
        return 1
    en = words[key]["en"]
    if i18n.places(text) != i18n.places(en):
        print(f"{key}: {text!r} has {sorted(i18n.places(text))} where the English has "
              f"{sorted(i18n.places(en))}")
        return 1
    e = data["strings"].setdefault(key, {})
    e.update({"en": en, lang: text, "state": "draft"})
    save(lang, data)
    print(f"{key}: {text!r}, a draft of {en!r}")
    return 0


def drop_unused(lang):
    data = load(lang)
    words, _p = i18n.code_words()
    gone = sorted(set(data["strings"]) - set(words))
    for k in gone:
        print(f"  {k}: {data['strings'][k].get(lang)!r}")
        del data["strings"][k]
    save(lang, data)
    print(f"{len(gone)} entries no code asks for, dropped")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lang", default="es")
    ap.add_argument("--sheet", metavar="CSV")
    ap.add_argument("--drafts", action="store_true", help="with --sheet: the drafts only")
    ap.add_argument("--take", metavar="CSV")
    ap.add_argument("--set", nargs=2, metavar=("KEY", "TEXT"))
    ap.add_argument("--drop-unused", action="store_true")
    a = ap.parse_args(argv)
    if a.lang == i18n.DEFAULT or a.lang not in i18n.LANGS:
        ap.error(f"--lang is one of {', '.join(c for c in i18n.LANGS if c != i18n.DEFAULT)}")
    if a.sheet:
        sheet(a.lang, a.sheet, a.drafts)
        return 0
    if a.take:
        return take(a.lang, a.take)
    if a.set:
        return set_one(a.lang, *a.set)
    if a.drop_unused:
        return drop_unused(a.lang)
    return status(a.lang)


if __name__ == "__main__":
    sys.exit(main())
