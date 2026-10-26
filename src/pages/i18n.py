#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.18
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
#
# THE HOW-TO GUIDES (the owner, 24 October 2026: "The how to pages are the
# next important section I think is worth translating."): the Resources hub,
# whose How-To Guides are in Spanish at /es/resources, and every guide,
# civics.py's three pages that became guides among them. A guide named here
# is translated piece by piece (say_html, guides.page_words); one added to
# guides.py and not here is English to everybody until it is added.
GUIDE_PAGES = tuple(f"guides/{s}.html" for s in (
    "your-representatives", "contact-your-legislators", "attend-a-hearing", "submit-testimony",
    "testifying", "read-a-bill", "using-this-site", "how-to-vote", "run-for-office",
    "renew-drivers-license", "register-a-car", "real-id", "new-to-new-hampshire",
    "food-and-health-assistance", "file-for-unemployment", "wage-rights",
    "heating-and-electric-help",
    "property-tax-abatement", "property-tax-relief", "public-records", "vital-records",
    "tour-the-state-house", "town-warrant-article", "child-care-scholarship",
    "domestic-violence-help", "homelessness-help",
    "storms-and-emergencies", "trash-and-recycling", "passport",
    "medicare-and-social-security", "disability-help", "who-to-contact",
    "fishing-license", "hunting-license", "boating"))
# THE LEARN PAGES (the person, 25 October 2026: "start on the Learn pages"),
# each named here as its Spanish is written, keyed learn.<slug>.* (guides.
# page_words). One not named is English to everybody and the hub links the
# English page. The pages whose figures are only numbers came first; those
# that draw a chart or a timeline follow once the figure is drawn in Spanish.
LEARN_PAGES = tuple(f"learn/{s}.html" for s in (
    "the-courts", "state-agencies", "administrative-rules", "local-government",
    "county-government", "city-and-town-government",
    "general-court", "how-a-bill-becomes-law", "governor-and-council", "the-constitution",
    "legislative-year"))
# THE OFFICIALS PAGE (the person, 25 October 2026: "Start on the Officials
# page and My Town in Spanish"): its own words, its tabs' and the words of
# corrections/officials.json that the tabs say (officials_tabs.data_words).
PAGES = {"es": ("index.html", "learn/glossary.html", "resources.html", "officials.html")
         + GUIDE_PAGES + LEARN_PAGES}

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


# THE GLOSSARY IN ANOTHER LANGUAGE (the owner, 24 October 2026: "The
# glossary should also be translated into spanish if it hasn't been
# already"). words/glossary.json is one table, read by the glossary page and
# by the term pop-ups: each term's name in full and what it means, keyed by
# the term ("ITL", "Public hearing"). Its translations are keyed by the term
# and the field, gloss.<term>.name and gloss.<term>.says, and each keeps the
# English it was made from, so an entry whose English changes is said in
# English again, and named by preflight, until its translation catches up.
def gloss_key(term, field):
    """"gloss.itl.name", "gloss.public-hearing.says"."""
    return f"gloss.{re.sub(r'[^a-z0-9]+', '-', term.lower()).strip('-')}.{field}"


def gloss_entries():
    """{term: {"name", "says", ...}} of words/glossary.json, its notes left out."""
    d = json.loads((HERE / "words" / "glossary.json").read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if not k.startswith("_")}


def say_gloss(lang, term, field, en):
    """A glossary entry's `field` ("name" or "says") in `lang`."""
    return say(lang, gloss_key(term, field), en) if lang != DEFAULT else en


def gloss_js(lang):
    """A script that sets window.GR_GLOSS to each term's name and meaning in
    `lang`, which the term pop-ups read (components.js). A term either of
    whose words is missing or stale is left out, and its pop-up says the
    English. Empty for English."""
    if lang == DEFAULT:
        return ""
    out = {}
    for term, e in gloss_entries().items():
        got, need = {}, [f for f in ("name", "says") if e.get(f)]
        for field in need:
            key, en = gloss_key(term, field), e[field]
            SAID.add((lang, key, en))
            t = lookup(lang, key, en)
            if t is None:
                MISSES.add((lang, key, "stale" if catalog(lang).get("strings", {}).get(key)
                            else "missing"))
            else:
                got[field] = t
        if len(got) == len(need):
            out[term] = got
    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "window.GR_GLOSS=" + body.replace("</", "<\\/") + ";"


# THE HOW-TO GUIDES IN ANOTHER LANGUAGE (the owner, 24 October 2026: "The
# how to pages are the next important section I think is worth
# translating."). A guide's words are data -- guides.py's steps and notes,
# and civics.py's three pages that became guides -- written as HTML a
# paragraph or a list item at a time, so they are translated a PIECE at a
# time: a run of words, with the markup inside a sentence (<b>, <a>, <em>),
# between the tags that lay a page out (<p>, <li>, <td>, <span>, <h2>). A
# change to one sentence re-opens the one piece it is in: the page says that
# piece in English, marked lang="en", until its translation is brought up
# to the new English, and every other piece stays translated. guides.py
# says which pieces each page has, and their keys (page_words).
INLINE = frozenset("a abbr b bdi br cite code em i kbd mark q s small strong sub sup time u wbr"
                   .split())
# Whose insides are never words to translate: a drawing is a drawing.
OPAQUE = frozenset("svg script style template math".split())
_MARKUP = re.compile(r"<!--.*?-->|<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>", re.S)
_OPEN = re.compile(r"<([a-z]+)\b[^>]*>")


def norm(s):
    """A piece's English as the catalog keeps it: every run of white space
    one space, so a paragraph re-wrapped in the source is the same piece."""
    return re.sub(r"\s+", " ", s or "").strip()


def _words_in(s):
    """Whether `s` holds a word: a letter outside its tags, entities and
    [[figures]] -- not a dash, a number or a figure alone."""
    import html as _h
    t = re.sub(r"\[\[\w+\]\]|\{[a-z_][a-z0-9_]*\}", " ", re.sub(r"<[^>]+>", " ", s))
    return bool(re.search(r"[^\W\d_]", _h.unescape(t)))


def _unwrap(html, s, e):
    """(s, e) inside any inline tag that wraps the whole of html[s:e]: a
    button's label is the words, and its link stays outside them."""
    while True:
        m = _OPEN.match(html, s)
        if not m or m.group(1) not in INLINE or m.group(1) in ("br", "wbr"):
            return s, e
        name, close = m.group(1), f"</{m.group(1)}>"
        if not html[s:e].endswith(close):
            return s, e
        depth = 0
        for t in re.finditer(rf"<(/?){name}\b[^>]*>", html[s:e]):
            depth += -1 if t.group(1) else 1
            if depth == 0 and s + t.end() != e:
                return s, e              # the first tag closes before the end
        s, e = m.end(), e - len(close)


def pieces(html):
    """[(start, end)] of every piece of words in `html`, in reading order:
    a run of text and inline markup (INLINE) between the tags that lay the
    page out, its outer white space and any tag that wraps the whole of it
    left outside. A comment ends a run; a drawing (OPAQUE) is skipped."""
    html = html or ""
    out, start, depth, pos = [], None, 0, 0

    def flush(end):
        nonlocal start
        if start is not None:
            s, e = start, end
            while s < e and html[s].isspace():
                s += 1
            while e > s and html[e - 1].isspace():
                e -= 1
            s, e = _unwrap(html, s, e)
            if s < e and _words_in(html[s:e]):
                out.append((s, e))
        start = None

    for m in _MARKUP.finditer(html):
        if not depth and start is None and html[pos:m.start()].strip():
            start = pos
        pos = m.end()
        if m.group(0).startswith("<!--"):
            if not depth:
                flush(m.start())
            continue
        close, name, single = m.group(1) == "/", m.group(2).lower(), m.group(3) == "/"
        if depth:
            if name in OPAQUE and not single:
                depth += -1 if close else 1
            continue
        if name in OPAQUE and not close and not single:
            flush(m.start())
            depth = 1
        elif name in INLINE:
            if start is None and not close:
                start = m.start()
        else:
            flush(m.start())
    if not depth and start is None and html[pos:].strip():
        start = pos
    flush(len(html))
    return out


def slug_words(en, n=6, cap=40):
    """A piece's own first words as a key's last part: "you-can-register-if"."""
    import html as _h
    import unicodedata
    t = _h.unescape(re.sub(r"\[\[\w+\]\]|<[^>]+>", " ", en or ""))
    flat = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    s = ""
    for w in re.findall(r"[a-z0-9]+", flat)[:n]:
        if s and len(s) + 1 + len(w) > cap:
            break
        s = f"{s}-{w}" if s else w
    return s or "x"


def _current(lang, key, en):
    """lookup(), with what was asked kept for preflight and what was missed
    for report(), as say() keeps them."""
    SAID.add((lang, key, en))
    got = lookup(lang, key, en)
    if got is None:
        MISSES.add((lang, key, "stale" if catalog(lang).get("strings", {}).get(key) else "missing"))
    return got


def say_piece(lang, key, en):
    """`en`, one piece of a data's words (a guide's title), in `lang`, or
    None where it has no current translation -- the caller says the English
    and marks it so. The English for English."""
    if lang == DEFAULT:
        return en
    return _current(lang, key, en)


def say_html(lang, html, keys):
    """`html` in `lang`, piece by piece (pieces): each piece's words from
    the catalog under keys[its English], or, where the catalog has none
    current for that English, the English in <span lang="en">, so a screen
    reader says it in English and nothing translated from other English is
    ever shown. `keys` is {English: key} for the page (guides.page_keys)."""
    if lang == DEFAULT or not html:
        return html
    out, pos = [], 0
    for s, e in pieces(html):
        en = norm(html[s:e])
        key = keys.get(en)
        got = _current(lang, key, en) if key else None
        if not key:
            MISSES.add((lang, f"(no key for {en[:50]!r})", "unkeyed"))
        out += [html[pos:s], got if got is not None else f'<span lang="en">{html[s:e]}</span>']
        pos = e
    out.append(html[pos:])
    return "".join(out)


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
# map.js too since 25 October 2026: the district map, on the Officials page
# and the town pages, says its words through tr() (the Officials page in
# Spanish), and loads as a file of its own on every page that draws a map.
SHARED_SCRIPTS = ("components.js", "find.js", "map.js")
# The pages a script links to by address, whose address in a language a
# page in it tells its scripts (page_words, window.GR_HREFS).
SCRIPT_LINKS = ("officials.html",)


def shared_words_path(lang):
    """The address of `lang`'s shared words, from the root."""
    return f"/lang/{lang}.js"


def page_words(lang, *scripts):
    """The lines a page in `lang` carries in its head, before components.js:
    its language and locale, the words its own scripts ask tr() for, and the
    file of the shared scripts' words. Empty for English."""
    if lang == DEFAULT:
        return ""
    # Where a script's link to one of SCRIPT_LINKS goes in this language
    # (find.js's Your Town card links the Officials page): the page in
    # `lang` where it has one, so a script never sends a reader from a
    # Spanish page to the English page of something Spanish has.
    # At the address the host serves: /es/officials, not /es/officials.html.
    hrefs = json.dumps({p: re.sub(r"\.html$", "", href(lang, p))
                        for p in SCRIPT_LINKS if has(lang, p)},
                       separators=(",", ":"))
    return (f'<script>window.GR_LANG="{lang}";window.GR_LOCALE="{LOCALE.get(lang, lang)}";'
            f'window.GR_HREFS={hrefs};'
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


def lang_links(html_, lang):
    """`html_` with every link to a page `lang` has sent to that page in
    `lang`; every other link left as it is, to the English page. One
    function for every builder of a translated page (build_civics' guides
    and Learn pages, build_pages' Officials page), so they cannot come to
    disagree about where a link goes."""
    if lang == DEFAULT:
        return html_

    def one(m):
        h = m.group(1)
        if re.match(r"[a-z][a-z0-9+.-]*:|//|#", h):
            return m.group(0)
        path, _, frag = h.partition("#")
        p = path.lstrip("/")
        page = p if p.endswith(".html") else (f"{p}.html" if p else "index.html")
        if p.startswith(f"{lang}/") or not has(lang, page):
            return m.group(0)
        return f'href="{href(lang, page)}' + (f"#{frag}" if frag else "") + '"'
    return re.sub(r'href="([^"]*)"', one, html_)


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


# ONE SPANISH WORD FOR EACH ENGLISH TERM (the person, 25 October 2026: "use
# consistent translations across different pages so that it's easier to
# follow"). lang/terms.<code>.json lists the terms; its _about says how a
# term is matched and how a choice is made. A language with no such file has
# no terms to keep.
def terms_path(lang):
    return LANG_DIR / f"terms.{lang}.json"


def _plain(s):
    """Text as a reader sees it: tags gone, entities read, curly quotes kept."""
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))


def _form_rx(forms):
    """Whole-word matching for any of `forms`: case kept for a form with a
    capital letter, ignored for one without."""
    parts = []
    for f in sorted(forms, key=len, reverse=True):
        body = re.escape(f).replace(r"\ ", r"\s+")
        body = body if any(c.isupper() for c in f) else "(?i:" + body + ")"
        parts.append(r"(?<![\w’'-])" + body + r"(?![\w-])")
    return re.compile("|".join(parts))


def term_faults(lang):
    """Every catalog entry whose English uses a listed term and whose `lang`
    words use none of its forms, as sentences, and every exception that
    names an entry the catalog no longer has. Empty when all is well, or
    when the language has no term list."""
    p = terms_path(lang)
    if not p.is_file():
        return []
    terms = json.loads(p.read_text(encoding="utf-8"))["terms"]
    strings = catalog(lang).get("strings", {})
    faults = []
    for t in terms:
        en_rx, own = _form_rx(t["en"]), _form_rx(t[lang])
        excepted = t.get("except") or {}
        for key in sorted(excepted):
            if key not in strings:
                faults.append(f"the term {t['en'][0]!r} excepts {key}, which is not in the catalog")
        for key, e in sorted(strings.items()):
            if key in excepted or not e.get(lang):
                continue
            en = _plain(e.get("en"))
            for s in t.get("skip") or ():
                en = en.replace(s, " ")
            if en_rx.search(en) and not own.search(_plain(e[lang])):
                faults.append(f"{key} says {en_rx.search(en).group(0)!r} and its {lang} has no "
                              f"{t[lang][0]!r}: {e[lang][:120]!r}")
    return faults
