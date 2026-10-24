#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.4
"""
The frame every page shares, written once: the head's fonts, icons, share
card, theme script and stylesheet; the header and its sections; the footer;
and the scripts at the foot of the page.

    import chrome
    chrome.head("officials.html")      # fonts, icons, card, theme, app.css, components.js
    chrome.nav("officials.html")       # the header, that section marked as the current one
    chrome.footer()                    # the footer and the line that dates the data
    chrome.scripts()                   # the header search and the theme control's handler
    chrome.fill(template, "bills.html")    # a page's <!-- CHROME:... --> slots, filled

ONE FRAME, TWO KINDS OF PAGE (23 October 2026). The site's pages are written
two ways: shell.page() makes the 34,000 record pages from bills.html, and
build_pages.shell() writes the home page, Officials, About, /search and 404.
Each used to carry its own copy of the header, the nav and the footer --
bills.html by hand, build_pages.py in Python -- and their own comments said
so: "ONE WRAPPER, WRITTEN TWICE BECAUSE THE NAV IS". Data was once added to
one copy's nav and not the other's, and three pages lacked a link the other
34,000 had. preflight's parity checks found such drift after the fact; they
could not stop the second edit being needed.

So both emitters ask this module. bills.html carries four slots --
<!-- CHROME:head -->, <!-- CHROME:nav -->, <!-- CHROME:footer --> and
<!-- CHROME:scripts --> -- which shell.template() fills before any record page
is made from it, and which build_pages fills for the copy it publishes at
/bills; build_pages.shell() puts the same four calls where its own copy was.
A change to the header, the nav, the footer or the head's shared lines is a
change here, and it reaches every page of the site at the next build.
preflight holds that: no emitter writes the frame by hand, and every page
the fixture builds carries it.

WHAT IS NOT HERE: what differs from page to page -- the title, the
description and the canonical address (shell.page, build_pages.shell), the
skip link's words, the page's own scripts. And the stylesheet's contents:
app.css is the one stylesheet, linked here, from the root, so that the 404
page, served at any depth, finds it too.

A change to this file is a change to every page, so build_all.py's
--front-end fast path refuses it (it is a script, not one of the browser's
files): only the page steps of a full build rewrite the pages.

IN EITHER LANGUAGE (23 October 2026). head(), nav(), footer() and
scripts() take the page's language, "en" unless a page says otherwise; the
words are i18n.say()'s, with the English written here as it always was.
Every page's head also carries LANG_HEAD, which decides, before anything is
drawn, whether this reader wants the page in another language and goes
there (i18n says when a language is offered and how a translation stays
current).
"""

import html as _html
import json as _json

import i18n
from components import icon
from i18n import say

# THE SECTIONS, in the header's order, with each one's drawing (Polish 1, 9
# October 2026: the prototype kit's icon before the word, components.icon).
NAV_TABS = (("bills.html", "Bills", "bill"),
            # LAWS, BESIDE BILLS (the person, 11 October 2026: "The top level
            # nav and page urls should say Laws since that's the easiest thing
            # to understand for newcomers"). A bill proposes to change a law;
            # the two are read together. build_rsa.py writes /laws.
            ("laws.html", "Laws", "law"),
            # OFFICIALS, NOT LEGISLATORS, AND RESOURCES, NOT LEARN (the
            # person, 8 October 2026, late evening: "the polish release's five
            # tabs are Bills, Officials, Calendar, Committees, Resources"). The
            # page moved with its tab: /legislators and /learn answer with a
            # 301 to the new addresses (build_pages.MOVED).
            ("officials.html", "Officials", "person"),
            ("calendar.html", "Calendar", "calendar"),
            ("committees.html", "Committees", "committee"),
            ("resources.html", "Resources", "book"))


def tab_words(lang="en"):
    """{href: label} of NAV_TABS in `lang`. The English is NAV_TABS's own,
    written again here so the translation can be checked against it;
    preflight holds the two to one word each (_translations)."""
    return {"bills.html": say(lang, "nav.bills", "Bills"),
            "laws.html": say(lang, "nav.laws", "Laws"),
            "officials.html": say(lang, "nav.officials", "Officials"),
            "calendar.html": say(lang, "nav.calendar", "Calendar"),
            "committees.html": say(lang, "nav.committees", "Committees"),
            "resources.html": say(lang, "nav.resources", "Resources")}

# THE REPOSITORY, NAMED ONCE. The footer links it, and so do the Data page
# and "How this is made" -- three places for three different readers, and one
# constant so a move cannot leave two of them pointing at nothing.
REPO = "https://github.com/granite-record/granite-record"

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600'
         '&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Playfair+Display:wght@600'
         '&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">')

# THE CARD A SHARED LINK UNFURLS INTO, by kind of page (build_brand.py draws
# them); the plain logo card for every page not named here. shell.page()
# puts each record's own kind's card in place of the template's, which is the
# bills section's.
CARDS = {"officials.html": ("og-legislator.png", "legislators and their voting records"),
         "bills.html": ("og-bill.png", "bills, votes and hearings")}

# THE MARK. assets/ holds the files and build_pages.py copies them into
# site/. The og tags name the card above; shell.page() replaces them per page.
_BRAND = """<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="icon" href="/icon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/icon-180.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#E9EAEC" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#171B1C" media="(prefers-color-scheme: dark)">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{alt}">
<meta name="twitter:image" content="{img}">"""

# THE PAGE'S LANGUAGE, BEFORE THE FIRST PAINT (23 October 2026; i18n.py says
# how the languages are kept and when one is offered). First in the head, so
# a reader who is going elsewhere is sent before anything is fetched or
# drawn. OFFER is the languages offered to everyone; LANGS every language
# the site is built in.
#
# WHICH LANGUAGE THIS READER WANTS, AND WHETHER THIS PAGE HAS IT. The
# reader's choice (Settings, kept as gr-lang) wins; without one, the first
# of the browser's languages the site has. A page in another language names
# itself on <html> as data-alt-<code>, and a reader who wants that language
# is sent there -- from a chosen language always, from the browser's only
# off an English page, since a reader who opens a Spanish page they were
# sent has asked for it. A language not yet offered to everyone moves nobody
# until the reader has opened one of its pages (gr-lang-seen), which is how
# the person and the proofreader try it. html.langs shows the language
# control and the footer's list. A link marked data-setlang makes its
# language the reader's choice as it is followed; so does a language chosen
# in the footer's list (data-footlang, 24 October 2026), which then goes to
# this page in that language, or that language's home page. The comments are
# here and not in the script, which is on every one of 34,000 pages.
LANG_HEAD = """<script>
(function(){
  var r=document.documentElement,K="gr-lang",here=r.lang||"en",OFFER=__OFFER__,LANGS=__LANGS__;
  function get(k){try{return localStorage.getItem(k)||"";}catch(e){return "";}}
  if(here!=="en")try{localStorage.setItem("gr-lang-seen","1");}catch(e){}
  document.addEventListener("click",function(e){
    var a=e.target&&e.target.closest&&e.target.closest("[data-setlang]");
    if(a)try{localStorage.setItem(K,a.getAttribute("data-setlang"));}catch(x){}
  },true);
  document.addEventListener("change",function(e){
    var s=e.target;if(!s||!s.hasAttribute||!s.hasAttribute("data-footlang"))return;
    var o=s.options[s.selectedIndex];if(!o||o.value===here)return;
    try{localStorage.setItem(K,o.value);}catch(x){}
    location.href=o.getAttribute("data-href");
  });
  if(OFFER.length<2&&here==="en"&&get("gr-lang-seen")!=="1")return;
  window.GR_NOTICE=__NOTICE__;
  var ls=navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||""];
  var browser="",chosen=get(K);
  for(var i=0;i<ls.length&&!browser;i++){var c=String(ls[i]||"").slice(0,2).toLowerCase();
    if(LANGS.indexOf(c)>=0)browser=c;}
  if(LANGS.indexOf(chosen)<0)chosen="";
  var want=chosen||browser||"en";
  window.GR_PREF={here:here,want:want,chosen:chosen,browser:browser};
  r.classList.add("langs");
  var to=r.getAttribute("data-alt-"+want);
  if(want!==here&&to&&(chosen||here==="en")&&to!==location.pathname)
    location.replace(to+location.search+location.hash);
})();
</script>"""


def notice_words():
    """{code: {label, text, home, close}}: what a page in English says to a
    reader who wants another language -- the settings row's word for
    "Language", and the notice that the page is not yet in theirs (find.js,
    langNotice) -- each in that language, from its catalog, since the page's
    own words are English."""
    return {c: {"label": say(c, "set.lang", "Language"),
                "text": say(c, "notice.text", "This page is not yet in Spanish."),
                "home": say(c, "notice.home", "Go to the home page in Spanish"),
                "close": say(c, "notice.close", "Close")}
            for c in i18n.LANGS if c != i18n.DEFAULT}


def lang_head():
    """LANG_HEAD with the site's languages, the ones offered to everyone and
    the words a reader of each is shown on an English page."""
    offer = [c for c in i18n.LANGS if i18n.offered(c)]
    notice = _json.dumps(notice_words(), ensure_ascii=False, separators=(",", ":"))
    return (LANG_HEAD.replace("__OFFER__", _json.dumps(offer))
            .replace("__LANGS__", _json.dumps(list(i18n.LANGS)))
            .replace("__NOTICE__", notice.replace("</", "<\\/")))


# THE THEME CONTROL, in three pieces: the script that runs before the first
# paint, the button in the header, and the handler at the foot of the page.
THEMER_HEAD = """<script>
/* BEFORE THE FIRST PAINT, and that is the whole reason this is inline in the
   head rather than in app.js. app.js loads at the end of the body: by the
   time it ran, a reader who had chosen dark would have already been shown a
   white page. Three lines, no dependencies, and wrapped in try/catch because
   localStorage throws outright in a locked-down browser rather than
   returning null. Absent or unrecognised means follow the system, which is
   what the stylesheet does on its own.
   And html.js, set first: a record page carries its record as plain HTML
   for a reader that runs no scripts (shell.page's static), which app.css
   hides once scripts are known to run, so it is never painted over. */
document.documentElement.classList.add("js");
try{var t=localStorage.getItem("gr-theme");
if(t==="dark"||t==="light")document.documentElement.dataset.theme=t;}catch(e){}
</script>"""

THEMER_BTN = ('<button class="themer" id="themer" type="button" hidden><svg class="thsun" '
              'viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="3.6"/><path '
              'd="M10 1.8v2.2M10 16v2.2M1.8 10h2.2M16 10h2.2M4.2 4.2l1.6 1.6M14.2 14.2l1.6 1.6M4.2 '
              '15.8l1.6-1.6M14.2 5.8l1.6-1.6"/></svg><svg class="thmoon" viewBox="0 0 20 20" '
              'aria-hidden="true"><path d="M16.4 12.4A7 7 0 0 1 7.6 3.6a7 7 0 1 0 8.8 8.8z"/></svg>'
              '<span class="thword">Light</span></button>')

THEMER_JS = """<script>
/* The control, as the person set it out on 13 September. The page follows the
   reader's system until they choose; the button names the theme on screen,
   Light or Dark, and swaps to the other; the choice is kept, so it is made
   once. There is no Auto to cycle through: following the system is what
   happens before anyone chooses, and a third state was a click nobody asked
   for. A value this control no longer writes ("auto", from the one before)
   reads as no choice.
   It starts hidden and is revealed here, so a reader with JavaScript off is
   not shown a control that cannot do anything -- the stylesheet still
   follows their system, which is the sensible default and needs no script. */
(function(){
  var b=document.getElementById("themer"); if(!b) return;
  var K="gr-theme", r=document.documentElement;
  var mq=window.matchMedia?window.matchMedia("(prefers-color-scheme: dark)"):null;
  function chosen(){ try{ var v=localStorage.getItem(K); return v==="light"||v==="dark"?v:""; }
                     catch(e){ return r.dataset.theme||""; } }
  function shown(){ return chosen()||(mq&&mq.matches?"dark":"light"); }
  function draw(){
    var v=shown();
    // NAME THE DESTINATION, NOT THE STATE. It read "Light" while the page was
    // light, which is a label describing what you are already looking at --
    // so the one thing a reader wants from it, what happens if I press this,
    // was the one thing it did not say. The aria-label has always named the
    // destination; the visible word now agrees with it.
    // AN ICON SINCE 24 SEPTEMBER, at the person's request: a sun or a moon
    // for the theme a press will give, the same destination the word named.
    // The word stays in the markup -- hidden beside the icon on a desktop,
    // shown in the phone's Sections panel, where nothing else says "theme".
    var to=v==="dark"?"light":"dark";
    b.setAttribute("data-to",to);
    var w=b.querySelector(".thword"); if(w) w.textContent=to==="light"?tr("theme.light","Light"):tr("theme.dark","Dark");
    b.title=to==="light"?tr("theme.to_light","Switch to the light theme"):tr("theme.to_dark","Switch to the dark theme");
    b.setAttribute("aria-label",v==="dark"
      ?tr("theme.now_dark","Color theme: dark. Activate to switch to light.")
      :tr("theme.now_light","Color theme: light. Activate to switch to dark."));
  }
  b.hidden=false; draw();
  b.addEventListener("click",function(){
    var next=shown()==="dark"?"light":"dark";
    r.dataset.theme=next;
    try{ localStorage.setItem(K,next); }catch(e){}
    draw();
  });
  // The system changing while nothing is chosen -- a laptop turning to its
  // evening setting -- changes the page through the stylesheet; the label
  // follows it.
  if(mq){ var f=function(){ if(!chosen()) draw(); };
    if(mq.addEventListener) mq.addEventListener("change",f);
    else if(mq.addListener) mq.addListener(f); }
})();
</script>"""

# The menu button a phone header carries. The SEARCH button is not here --
# find.js mounts its own, and a second one would be two controls doing one job.
MENU_BTN = ('<button class="navmenu" id="navmenu" type="button" aria-expanded="false" '
            'aria-controls="navdrop" aria-label="Sections"><svg viewBox="0 0 20 20" fill="none" '
            'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true">'
            '<path d="M3.2 6h13.6M3.2 10h13.6M3.2 14h13.6"/></svg></button>')


def menu_btn(lang="en"):
    """MENU_BTN, named in `lang`."""
    return MENU_BTN.replace('aria-label="Sections"',
                            f'aria-label="{_html.escape(say(lang, "nav.sections", "Sections"))}"', 1)

# WHAT A POWER USER NEEDS, IN THE FOOTER, WHERE THEY WILL LOOK FOR IT. The
# line says when the data was last rebuilt: a reader deciding whether to trust
# a status should not have to go to the home page to find out how old it is.
# Read from build.json rather than baked in, because the page steps run before
# build.json is written -- a baked stamp would always be a few minutes early
# and would differ page to page. It is one small cached request, and the line
# simply does not appear if the fetch fails.
FOOT_JS = (
    '<script>fetch(new URL("build.json",location.origin+"/").href)'
    '.then(r=>r.json()).then(B=>{'
    'var e=document.getElementById("built");'
    'if(!e||!B.finished)return;'
    'e.textContent=" "+tr("foot.rebuilt","Data rebuilt {date}.",{date:new Date(B.finished)'
    '.toLocaleDateString(window.GR_LOCALE||"en-US",{year:"numeric",month:"long",day:"numeric"})});'
    '}).catch(function(){});</script>')

def tr_report(lang):
    """On a page in another language, the button that reports a mistake in
    its translation (the owner, 24 October 2026: "We should also add a
    report button for translation inaccuracy."). Hidden as written:
    components.js shows it, and opens the box it sends from, so a page read
    without JavaScript keeps the address above it instead."""
    if lang == i18n.DEFAULT:
        return ""
    return ('\n<p class="trrep"><button type="button" class="trbtn" data-trreport hidden>'
            + say(lang, "foot.tr_report", "See a mistake in the translation? Tell us")
            + "</button></p>")


# The footer. The line under the attribution is the person's own credit, asked
# for on 7 October 2026: who makes the site, quietly, and the way to About.
# In either language (footer_html), and FOOTER is the English, which every
# English page carries.
#
# THE LANGUAGE LINE, under the columns: every language, each in its own
# words, for a reader who does not read this one. It is hidden until
# LANG_HEAD finds the language offered to this reader (html.langs), and on a
# Spanish page it leads to the page's English and back.
#
# A LIST TO CHOOSE FROM (the owner, 24 October 2026: "make the footer
# language change look more interactive like a dropdown to select
# language"): a globe, "Language · Idioma" in every language the site has,
# and a select holding each language by its own name, this page's chosen.
# Choosing one goes to this page in it (data-href), or to that language's
# home page where this page has no version in it, and makes it the reader's
# choice, as Settings' list does (LANG_HEAD).
def footer_html(lang="en", alt=None):
    """The footer in `lang`. `alt` is {code: address} of this page in the
    other languages; a page that has no other is offered the other
    language's home page."""
    opts = []
    for code in i18n.LANGS:
        to = ("" if code == lang
              else (alt or {}).get(code) or i18n.href(code, "index.html"))
        opts.append(f'<option value="{code}" lang="{code}" data-href="{to}"'
                    f'{" selected" if code == lang else ""}>{i18n.NAMES[code]}</option>')
    # "Language" in this page's words, then in each other language's.
    said = [say(lang, "set.lang", "Language")]
    said += [w for w in (say(c, "set.lang", "Language") for c in i18n.LANGS if c != lang)
             if w not in said]
    return f"""<footer><div class="in">
<div class="fcols">
<div class="fcol">
<p class="fcolhead">Granite Record</p>
<p class="attrib">{say(lang, "foot.attrib", "Built from public records published by the <b>New Hampshire General Court</b>. Not affiliated with the General Court, and not a substitute for it &mdash; where this site and the Court&rsquo;s own record disagree, the Court is right and we want to know.")}</p>
<p class="footby">{say(lang, "foot.by", "An independent project by Alice Wade")} &middot; <a href="about.html">{say(lang, "foot.about", "About")}</a></p>
<p class="logocredit">{say(lang, "foot.logo", "Logo drawn by Debra Caplan, an artist in Peterborough, NH")}
&middot; <a href="https://www.linescapesnh.com/" rel="noopener">linescapesnh.com</a></p>
</div>
<div class="fcol">
<p class="fcolhead">{say(lang, "foot.record", "The record")}</p>
<ul class="flinks">
<li><a href="data.html">{say(lang, "foot.data", "Bulk data")}</a></li>
<li><a href="{i18n.href(lang, "learn/glossary.html").lstrip("/")}">{say(lang, "foot.glossary", "Glossary")}</a></li>
<li><a class="out" href="{REPO}" target="_blank" rel="noopener">{say(lang, "foot.source", "Source on GitHub")}</a></li>
</ul>
</div>
<div class="fcol">
<p class="fcolhead">{say(lang, "foot.tell", "Tell us")}</p>
<a class="fbk out" href="https://forms.gle/PYw9c3xgpDDwvX7E9" target="_blank"
 rel="noopener">{say(lang, "foot.think", "What do you think?")}</a>
<p class="fbknote">{say(lang, "foot.new", "The site is new and being tested. Found an error?")}
<a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a></p>{tr_report(lang)}
</div>
</div>
<div class="footlang"><label class="footlangl" for="footlang">{icon("globe")}<span>{" · ".join(said)}</span></label>
<select id="footlang" data-footlang>{"".join(opts)}</select></div>
<p class="footdata"><span id="built"></span><span class="lic">{say(lang, "foot.licence", "Open source (MIT License)")}</span></p>
</div></footer>"""


FOOTER = footer_html("en")

# The one stylesheet, from the root, and the components every page's scripts
# use, loaded before any of them.
STYLESHEET = '<link rel="stylesheet" href="/app.css">'
COMPONENTS_JS = '<script src="/components.js"></script>'
# The header's search, on every page: its own file, deferred.
FIND_JS = '<script src="/find.js" defer></script>'

SLOTS = ("head", "nav", "footer", "scripts")


def card(page=""):
    """(image file, its alt text) of the card a link to `page` unfurls into."""
    img, what = CARDS.get(page, ("og.png", ""))
    return img, (f"Granite Record: {what}" if what else "Granite Record")


def head(page="", lang="en", scripts=()):
    """The head's shared lines: the language script, the fonts, the icons
    and theme colours, the share card for `page`'s kind, the theme's
    pre-paint script, the one stylesheet and components.js -- in that order,
    the language first so a reader bound elsewhere goes before anything is
    fetched, and the stylesheet after the theme so a chosen theme is set
    before anything is drawn.

    A page in another language also carries, before components.js, the
    words its scripts ask tr() for (i18n.page_words): `scripts` is the text
    of the page's own scripts, beside the frame's, which are added here; the
    shared scripts' words are a file of their own (i18n.SHARED_SCRIPTS)."""
    img, alt = card(page)
    brand = _BRAND.format(img=f"https://graniterecord.org/{img}", alt=_html.escape(alt, quote=True))
    words = i18n.page_words(lang, THEMER_JS, FOOT_JS, *scripts)
    return "\n".join(x for x in (lang_head(), words, FONTS, brand, THEMER_HEAD, STYLESHEET,
                                 COMPONENTS_JS) if x)


def nav(page="", home=False, lang="en"):
    """The header: the wordmark, the five sections with `page` marked as the
    one a reader is on, the theme control and the phone's menu button.

    THE HOME PAGE HAS NO TAB, so the brand carries the "you are here" for it
    (home=True) -- said to a screen reader, not drawn, because the chip that
    marks a tab is scoped to .navtabs and the brand is not one.

    .navtabs exists so the strip wraps as one unit; .navdrop wraps the
    sections and the theme control so a phone can fold both behind one button
    without the markup being written twice (app.css, THE HEADER TABS).

    In another language the words are that language's and every link is to
    the page in it where there is one (i18n.href), the English page where
    there is not."""
    cur = ' aria-current="page"'
    words = tab_words(lang)
    to = (lambda h: h) if lang == i18n.DEFAULT else (lambda h: i18n.href(lang, h))
    tabs = "\n".join(f'<a href="{to(href)}"{cur if href == page else ""}>{icon(glyph)}{words[href]}</a>'
                     for href, _label, glyph in NAV_TABS)
    brand_cur = cur if home else ""
    sections = _html.escape(say(lang, "nav.sections", "Sections"))
    return (f'<nav class="top" aria-label="{sections}"><div class="in">\n'
            f'<a class="brand" href="{to("index.html")}"{brand_cur} translate="no">Granite Record</a>\n'
            f'<div class="navdrop" id="navdrop"><div class="navtabs">{tabs}</div>\n'
            f'{THEMER_BTN}</div>\n'
            f'{menu_btn(lang)}\n'
            '</div></nav>')


def footer(lang="en", alt=None):
    """The footer, and the script that puts the data's date in it."""
    return f"{FOOTER if lang == i18n.DEFAULT and not alt else footer_html(lang, alt)}\n{FOOT_JS}"


def scripts(lang="en"):
    """The scripts every page ends with: the header search and the theme
    control's handler. A page's own scripts go after them. The same in
    every language: what they say comes from the page's words."""
    return f"{FIND_JS}\n{THEMER_JS}"


def fill(t, page=""):
    """`t` with its <!-- CHROME:... --> slots filled for `page`. A slot that
    is missing raises: a template that has lost one would be a site with no
    header, or no footer, on 34,000 pages, and nothing else would say so. A
    template with none left is returned as it came, so filling twice is
    harmless."""
    if not any(f"<!-- CHROME:{s} -->" in t for s in SLOTS):
        return t
    parts = {"head": head(page), "nav": nav(page), "footer": footer(), "scripts": scripts()}
    for s in SLOTS:
        slot = f"<!-- CHROME:{s} -->"
        assert t.count(slot) == 1, (
            f"the template has {t.count(slot)} of {slot}, not one: every page made from "
            "it would be missing that part of the frame, or carry it twice")
        t = t.replace(slot, parts[s], 1)
    return t
