#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.2
"""
The translation audit: every word the code asks to be translated, read from
the source, and what is wrong with a language's catalog against it.

    import translation_audit as TA
    words, problems = TA.code_words()      # {key: {"en": ..., "where": [...]}}, and what cannot be read
    TA.check("es")                         # lang/es.json against the code, as sentences

Read by preflight (_translations and the checks of the Spanish pages) and by
src/ops/translations.py, the proofreader's tool. It was the end of i18n.py
until 19 November 2026; it moved out because it reads the word lists of the
builders (guides, build_civics, officials_tabs, build_pages,
legislative_year), and i18n is what every one of them imports: the audit made
the base of src/pages import its top, and tied thirty modules into one import
cycle. Nothing a page is built from imports this module.
"""

import json

import _paths
from i18n import (DEFAULT, HERE, LANGS, STATES, _TR, catalog, gloss_entries, gloss_key, has,
                  places, word_key)


# ---- WHAT THE CODE SAYS, READ FROM THE SOURCE --------------------------------
#
# The one list of words a translation must answer, for preflight
# (_translations) and for the proofreader's sheet (src/ops/translations.py):
# every say() written in a Python file of src/pages, every tr() in a script
# (inline/ among them: a builder's own, inline_js) or in a script still held
# in a Python string, and every word of the tables
# say_word() translates. Read from the source, not from a build, so a word on
# a page the fixture never draws is held all the same.

# The tables say_word() reads: (group, the words). meeting_kinds.json's names;
# and since 24 October 2026 what the home page's Latest Activity says a meeting
# did to a bill, each in the words the site already says it in: a
# committee's recommendation in committee_acts' (REC_WORDS, a committee
# page's), an interim study report in study_report.json's, and a sitting's
# motion in votes.json's chip words, with the nouns and chambers they are
# filled with.
def _word_tables():
    import json as _j
    mk = _j.loads((HERE / "words" / "meeting_kinds.json").read_text(encoding="utf-8"))
    kinds = sorted({w for w, _c in mk["kinds"].values()})
    import committee_acts
    recs = sorted(set(committee_acts.REC_WORDS.values()))
    sr = _j.loads((HERE / "words" / "study_report.json").read_text(encoding="utf-8"))
    study = sorted({sr["head"], *sr["said"].values()})
    v = _j.loads((HERE / "words" / "votes.json").read_text(encoding="utf-8"))
    votes = {v["passed"], v["failed"], *v["nouns"], "House", "Senate"}
    for m in [*v["motions"].values(), v["consent"]]:
        votes |= {m[k] for k in ("passed", "failed") if m.get(k)}
    return [("kind", kinds), ("rec", recs), ("study", study), ("vote", sorted(votes))]


def _say_calls(path):
    """[(key, English, line)] of every say(lang, "key", "English") in a
    Python file, and [(line, why)] of the calls whose key or English is not
    written out, which preflight refuses."""
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    out, bad = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if name != "say":
            continue
        args = node.args
        if (len(args) >= 3 and isinstance(args[1], ast.Constant) and isinstance(args[1].value, str)
                and isinstance(args[2], ast.Constant) and isinstance(args[2].value, str)):
            out.append((args[1].value, args[2].value, node.lineno))
        else:
            bad.append((node.lineno, "say() with a key or English that is not written out"))
    return out, bad


def code_words(root=None):
    """{key: {"en": English, "where": [file:line, ...]}} of every word the
    code asks to be translated, and a list of problems: a call that cannot be
    read, or one key given two different Englishes."""
    root = _paths.ROOT / "src" / "pages" if root is None else root
    words, problems = {}, []

    def add(key, en, where):
        w = words.setdefault(key, {"en": en, "where": []})
        if w["en"] != en:
            problems.append(f"{key} is {w['en']!r} at {w['where'][0]} and {en!r} at {where}: "
                            "one key, one English")
        w["where"].append(where)

    for f in sorted(root.glob("*.py")):
        if f.name == "i18n.py":
            continue
        calls, bad = _say_calls(f)
        for key, en, line in calls:
            add(key, en, f"{f.name}:{line}")
        problems += [f"{f.name}:{line}: {why}" for line, why in bad]
    for f in sorted([*root.glob("*.js"), *root.glob("*.py")]) + sorted(root.glob("inline/*.js")):
        if f.name == "i18n.py":
            continue
        text = f.read_text(encoding="utf-8")
        for m in _TR.finditer(text):
            try:
                en = json.loads('"' + m.group(2) + '"')
            except ValueError:
                en = m.group(2)
            add(m.group(1), en, f"{f.name}:{text.count(chr(10), 0, m.start()) + 1}")
    for group, table in _word_tables():
        for en in table:
            add(word_key(group, en), en, f"words/{group}")
    for term, e in gloss_entries().items():
        for field in ("name", "says"):
            if e.get(field):
                add(gloss_key(term, field), e[field], "words/glossary.json")
    # The how-to guides' words, piece by piece, for every guide a language
    # has (guides.page_words): their own words are data, not say() calls.
    import guides
    for key, en, where in guides.translated_words():
        add(key, en, where)
    # The Resources hub's Learn and Official Sources tabs (25 October 2026),
    # whose words are the hub's data, where a language has the hub.
    if any(has(c, "resources.html") for c in LANGS if c != DEFAULT):
        import build_civics
        for key, en, where in build_civics.hub_words():
            add(key, en, where)
    # The Officials page's tabs say the person's own words from
    # corrections/officials.json -- what an office is, a title, a
    # department's name -- where a language has the page.
    if any(has(c, "officials.html") for c in LANGS if c != DEFAULT):
        import officials_tabs
        for key, en, where in officials_tabs.data_words():
            add(key, en, where)
    # The About page's pieces (9 November 2026), as a guide's: its words are
    # build_pages' ABOUT, not say() calls.
    if any(has(c, "about.html") for c in LANGS if c != DEFAULT):
        import build_pages
        for key, en, where in build_pages.about_words():
            add(key, en, where)
    # The legislature's schedule (the Learn pages in Spanish, 25 October
    # 2026): its seasons' and steps' words are legislative_year's data.
    if any(has(c, "learn/legislative-year.html") for c in LANGS if c != DEFAULT):
        import legislative_year
        for key, en, where in legislative_year.year_words():
            add(key, en, where)
    return words, problems


def check(lang, root=None):
    """What is wrong with `lang`'s catalog against the code, as sentences:
    a word with no entry, an entry translated from English the code no
    longer says, an entry no code asks for, a {placeholder} the two do not
    share, a state that is not one of STATES. Empty when all is well."""
    words, problems = code_words(root)
    strings = catalog(lang).get("strings", {})
    for key, w in sorted(words.items()):
        e = strings.get(key)
        if not e or not e.get(lang):
            problems.append(f"{key} has no {lang} words ({w['where'][0]}): {w['en']!r}")
            continue
        if e.get("en") != w["en"]:
            problems.append(f"{key} is stale: translated from {e.get('en')!r}, the English is "
                            f"now {w['en']!r} ({w['where'][0]}); its {lang} is {e[lang]!r}")
        if places(e[lang]) != places(w["en"]):
            problems.append(f"{key}: the {lang} has {sorted(places(e[lang]))} where the English "
                            f"has {sorted(places(w['en']))}")
        if e.get("state") not in STATES:
            problems.append(f"{key}: state {e.get('state')!r} is not one of {STATES}")
    for key in sorted(set(strings) - set(words)):
        problems.append(f"{key} is in lang/{lang}.json and no code asks for it")
    return problems
