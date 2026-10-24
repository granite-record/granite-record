#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.2
"""
The site in more than one language, and how a translation stays current.

    import i18n
    i18n.say("es", "nav.bills", "Bills")                # "Proyectos de ley"
    i18n.say("es", "cal.n_bills", "{n} bills", n=3)      # "3 proyectos de ley"
    i18n.say("en", "nav.bills", "Bills")                # "Bills": English is the code's own
    i18n.page_words("es", HOME_JS, find_js)             # the browser's words, for one page
    i18n.href("es", "index.html")                       # "/es/"

ASKED FOR on 23 October 2026: "begin work on the Spanish language version
of the site with the homepage, navigation, and implementation of an option
to select the language manually in the settings section or to automatically
set it based on the browser. I have someone who will proofread the drafts
when they're ready, and the translation should not go out of date when page
information is updated."

THREE KINDS OF WORDS ARE ON A PAGE, AND EACH STAYS CURRENT ITS OWN WAY.

1. What the record says: a bill's title, a committee's name, a person's, a
   town's, a line of a bill's history, the hand-kept status note. These are
   NOT translated. They change every night, and a translation would be out
   of date by morning, or a machine's guess at a legal title. A Spanish page
   prints them as the record has them, marked lang="en", so a screen reader
   says them in English, and the page says once that the records are in
   English.
2. What the site works out: a count, a date, how many days off a meeting is.
   Worked out once, from the same files, for both languages; only the words
   around the number are translated ("{n} bills", "{n} proyectos de ley").
   A new night's numbers reach both pages at once, because there is one
   number.
3. What the site itself says: the nav, a heading, a sentence of help. These
   are translated, once each, in lang/<code>.json, and this module is how
   they stay true to the English.

HOW A TRANSLATION KNOWS IT HAS GONE STALE. The English stays in the code,
where the page is written and where a person changing it will look, and is
passed beside its key:

    say(lang, "home.lead", "Keep up with New Hampshire legislation, ...")

The catalog keeps, for each key, the Spanish AND the English it was
translated from. say() gives the Spanish only while that English is the
English the code passes now. Change one word of the English and the Spanish
stops answering: the Spanish page says the new English until the Spanish is
brought up to it, and preflight fails meanwhile (_translations), naming the
key, the English it was translated from, the English now, and the Spanish.
So a translation can lag an edit, visibly, and can never go on saying what
the English page no longer says. The browser's words work the same way:
tr("key", "English") in a script, and page_words() hands a page only the
Spanish whose English still matches.

DRAFT, THEN PROOFREAD. Every entry says "state": "draft" until the person's
proofreader has passed it, then "proofread". Bringing an entry up to new
English puts it back to "draft". src/ops/translations.py lists the drafts
for the proofreader and takes their corrections back.

UNLISTED UNTIL OFFERED. While a language's catalog says "offered": false its
pages are built and published at /<code>/ -- so the proofreader and the
person can read them, on the preview or on the live site -- but nothing
links to them, search engines are asked not to index them, no English page
names them as its alternate, and the browser's language moves nobody. A
reader who opens one of them is shown the language control from then on, in
that browser (chrome.LANG_HEAD), so the person can try all of it before
anyone else is shown it. "offered": true is the person's switch.
"""

import json
import re

import _paths

# Where the pages' code is: the catalogs beside it in lang/, and the files
# whose words code_words() reads.
HERE = _paths.ROOT / "src" / "pages"
LANG_DIR = HERE / "lang"

# The site's languages, the first the one it is written in. A language is a
# file in lang/ as well as a code here; preflight holds the two together.
LANGS = ("en", "es")
DEFAULT = "en"
# Each language's own name for itself: what the control offers, and what a
# reader who does not read the page's language looks for.
NAMES = {"en": "English", "es": "Español"}
# The locale a browser formats a date or a clock time in, for each language.
LOCALE = {"en": "en-US", "es": "es-US"}

STATES = ("draft", "proofread")

# The pages each language has, as their English paths. A Spanish page's
# address is its English one under /es/ (href). Only these are built in that
# language; every other page is English to everybody, and a reader who chose
# another language is told so on it (find.js, langNotice).
PAGES = {"es": ("index.html",)}

_CATALOGS = {}
# What a build asked for and could not give: (lang, key, why). report() says
# it at the end of a build, and preflight's _translations fails on any.
MISSES = set()
# Every (lang, key, English) a build asked for: preflight's record of what
# the code says, beside what it can read from the source.
SAID = set()

_PLACE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def catalog(lang):
    """lang/<lang>.json as it stands: {"offered": bool, "strings": {key:
    {"en", lang, "state", "note"?}}}. English has none; an absent file is a
    language with nothing translated, which every say() then reports."""
    if lang == DEFAULT:
        return {"offered": True, "strings": {}}
    if lang not in _CATALOGS:
        f = LANG_DIR / f"{lang}.json"
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {"offered": False, "strings": {}}
        _CATALOGS[lang] = data
    return _CATALOGS[lang]


def offered(lang):
    """Whether the site offers `lang` to everyone (the person's switch)."""
    return lang == DEFAULT or bool(catalog(lang).get("offered"))


def places(s):
    """The {placeholders} a string holds, as a set of names."""
    return set(_PLACE.findall(s or ""))


def fill(s, vals):
    """`s` with each {name} that `vals` holds replaced by its value, as text.
    A brace that names nothing given is left alone."""
    if not vals:
        return s
    return _PLACE.sub(lambda m: str(vals[m.group(1)]) if m.group(1) in vals else m.group(0), s)


def lookup(lang, key, en):
    """The `lang` words for `key`, or None where the catalog has none for
    THIS English: no entry, or one translated from English the code no
    longer says (stale)."""
    e = catalog(lang).get("strings", {}).get(key)
    if not e or not e.get(lang):
        return None
    return e[lang] if e.get("en") == en else None


def say(lang, key, en, **vals):
    """`en` in `lang`, with `vals` put in its {placeholders}.

    `key` and `en` are written in the call as plain strings, so preflight can
    read every call from the source. Where the catalog has no current words
    for it, the English is given -- never words translated from English the
    page no longer says -- and the miss is kept for report()."""
    lang = lang or DEFAULT
    if lang != DEFAULT:
        SAID.add((lang, key, en))
        got = lookup(lang, key, en)
        if got is None:
            e = catalog(lang).get("strings", {}).get(key)
            MISSES.add((lang, key, "stale" if e else "missing"))
        else:
            en = got
    return fill(en, vals)


def word_key(group, en):
    """The key of a word from a table of words (words/meeting_kinds.json):
    the group and the English itself, lower case, its spaces as underscores.
    A word changed in the table is a new key, so it asks for its own
    translation rather than taking the old word's."""
    return f"{group}." + re.sub(r"[^a-z0-9]+", "_", (en or "").lower()).strip("_")


def say_word(lang, group, en):
    """`en`, a word from a table of words, in `lang` (word_key)."""
    return say(lang, word_key(group, en), en) if lang != DEFAULT else en


def report(out=print):
    """Say what a build could not translate, once each, and how many."""
    if not MISSES:
        return 0
    for lang, key, why in sorted(MISSES):
        out(f"  {lang}: {key} is {why} in lang/{lang}.json; the page says it in English")
    return len(MISSES)


# THE BROWSER'S WORDS. A script says tr("key", "English"), or with values
# tr("key", "In {n} days", {n: 3}); components.js's tr() answers from
# window.GR_WORDS, which a page in another language carries, and with the
# English otherwise. The key and the English are double-quoted strings
# written in the call, so this can read them, and preflight can too.
_TR = re.compile(r'\btr\(\s*"([a-z0-9_.\-]+)"\s*,\s*"((?:[^"\\\n]|\\.)*)"')


def tr_calls(js):
    """[(key, English)] of every tr() call in a script's text, in order."""
    out = []
    for m in _TR.finditer(js or ""):
        try:
            en = json.loads('"' + m.group(2) + '"')
        except ValueError:
            en = m.group(2)
        out.append((m.group(1), en))
    return out


def words_js(lang, *scripts):
    """A script that adds to window.GR_WORDS the `lang` words the scripts
    ask tr() for -- only those, and only where they are current, so no page
    carries a dictionary of the whole site or a stale word. Empty for
    English, which is the scripts' own."""
    if lang == DEFAULT:
        return ""
    words = {}
    for js in scripts:
        for key, en in tr_calls(js):
            SAID.add((lang, key, en))
            got = lookup(lang, key, en)
            if got is None:
                MISSES.add((lang, key, "stale" if catalog(lang).get("strings", {}).get(key)
                            else "missing"))
            else:
                words[key] = got
    body = json.dumps(words, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    # A word holding "</" would end an inline <script>; "<\/" is the same string.
    body = body.replace("</", "<\\/")
    return f"window.GR_WORDS=Object.assign(window.GR_WORDS||{{}},{body});"


# THE FILE OF THE SHARED SCRIPTS' WORDS. components.js and find.js are on
# every page and change on their own (the fast path, front_end.py, puts a
# change to either into a built site without building a page), so the words
# they ask tr() for are not written into a page: build_pages.front_end
# writes them, for each language, to site/lang/<code>.js, which a page in
# that language loads in its head. A page's own scripts' words are in the
# page (page_words).
SHARED_SCRIPTS = ("components.js", "find.js")


def shared_words_path(lang):
    """The address of `lang`'s shared words, from the root."""
    return f"/lang/{lang}.js"


def page_words(lang, *scripts):
    """The lines a page in `lang` carries in its head, before components.js:
    its language and locale, the words its own scripts ask tr() for, and the
    file of the shared scripts' words. Empty for English."""
    if lang == DEFAULT:
        return ""
    return (f'<script>window.GR_LANG="{lang}";window.GR_LOCALE="{LOCALE.get(lang, lang)}";'
            f'{words_js(lang, *scripts)}</script>\n'
            f'<script src="{shared_words_path(lang)}"></script>')


def href(lang, page):
    """The address of `page` (an English path, "index.html", "about.html")
    in `lang`: the English address under /<lang>/ where that page is one
    `lang` has, the English one otherwise. Absolute, from the root."""
    p = "/" + page.lstrip("/")
    if lang == DEFAULT or page not in PAGES.get(lang, ()):
        return p
    p = f"/{lang}{p}"
    return p[: -len("index.html")] if p.endswith("/index.html") else p


def has(lang, page):
    """Whether `page` (an English path) is built in `lang`."""
    return lang == DEFAULT or page in PAGES.get(lang, ())


# ---- WHAT THE CODE SAYS, READ FROM THE SOURCE --------------------------------
#
# The one list of words a translation must answer, for preflight
# (_translations) and for the proofreader's sheet (src/ops/translations.py):
# every say() written in a Python file of src/pages, every tr() in a script
# or in a script held in a Python string, and every word of the tables
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
    for f in sorted([*root.glob("*.js"), *root.glob("*.py")]):
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
