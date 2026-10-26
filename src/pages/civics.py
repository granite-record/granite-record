#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.64
"""
The topics of the civics section: their order, their names, and their prose.

Read by build_civics.py, which does the rendering. Kept apart from it for one
reason: this file is the writing and that one is the machinery, and the
writing is the part a person who knows the building has to read before it
ships. Anyone can review a list of paragraphs; nobody should have to read a
page builder to check whether a description of a veto override is right.

PROPOSAL-civics.md is the brief. Two things in it govern every line here.

THE FIRST is what makes this worth building on Granite Record rather than
linking to somebody else's explainer: explain a thing, then show it happening,
with the record attached. Every page carries links into this site's own data,
and every number in the prose is one this site can produce.

THE SECOND is the risk. A wrong timestamp is embarrassing; a wrong description
of how an override works is the sort of error that gets quoted, and it
undermines the record it sits beside. So:

  * A number in the prose is one measured from this disk, and the page says
    what it is measuring and when.
  * Anything procedural or constitutional is stated plainly and linked to the
    authority -- the Constitution, the chamber rules, the agency -- so a
    reader who wants to check is one click away.
  * Where this site holds nothing to show, the page is shorter and says so
    rather than padding with prose nobody can verify.
  * Where a thing is genuinely contested, the page says it is debated, gives
    the strongest version of each side in a sentence, and stops.

TONE: plain, short sentences. Explain the mechanism, not whether it is good.
No "did you know", no exclamation marks, and no suggestion that the reader
ought to be more engaged than they already are. Someone looking up how to
testify has decided.
"""

import re

import i18n as I
import legislative_year

# The order is the order of the proposal, and it is the order the "next
# topic" link at the foot of each page walks. Three groups: how the state
# works, how to take part, and the state itself (About New Hampshire, the
# owner's request of 26 October 2026 for pages on the state's symbols and
# its State House). Their names are headings -- on the Resources
# hub's Learn tab and in The Thirteen Pages at the foot of each page -- so
# they are in Title Case, as every heading is (the person, 8 and 9 October
# 2026, item 17).
GROUPS = [
    ("How the State Works",
     "The institutions, in the order they act on a bill."),
    ("How to Take Part",
     "The mechanics, which are more open than most people expect."),
    ("About New Hampshire",
     "The state itself: what its laws name as its own."),
]


def topic(slug, title, group, blurb, body, sources, holds=""):
    return {"slug": slug, "title": title, "group": group, "blurb": blurb,
            "body": body, "sources": sources, "holds": holds}


# ---------------------------------------------------------------------------
# Bodies are filled in below. Each is plain HTML: h2, h3, p, ul, a table, the
# diagrams below, and .l-note for a limit stated plainly. EVERY BODY OPENS
# WITH AN h2, because build_civics cuts each page into sections at its h2s and
# sets each heading in the margin beside its prose (W4, the component plan
# approved on 9 October 2026); a body with words before its first heading
# stops the build. The headings over the opening paragraphs are each taken
# from that paragraph's own words ("In Two Parts", "What a Bill Is"), as the
# approved prototypes drew them.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# THE BODIES.
#
# Every figure below is one this site can produce, and the sentence says what
# it counts and over what period, because "most bills die" is an opinion and
# "855 of 2,234 were killed in the 2025-2026 term" is not.
#
# Where the record holds nothing to show -- the courts, the Executive Council
# -- the page is short and says so. Padding those with prose nobody here can
# check is exactly the failure the proposal warns about.
# ---------------------------------------------------------------------------

# WHAT THE RECORD HOLDS ON THIS SUBJECT, as a section like the others: it
# was a tinted box with a small heading, and is now In the Record in the
# margin, so a page reads as one column of sections (C7).
SHOWS = ('<h2>In the Record</h2>{}')

# WHAT USING THIS SITE SAYS OF EMAIL, BEFORE AND AFTER IT GOES LIVE (17
# October 2026). It said "There is no email option yet" in prose, and would
# have gone on saying it beside the sign-up box from the day email following
# opened; shell.follow_live() decides, as it does for the About and Data
# pages. The first is the text it replaces, unchanged.
FOLLOW_EMAIL = {
    False: "There is no email option yet. No account, no email address, nothing to leak.",
    True: ("A feed needs no account and no email address. Updates can also come by "
           "email: sign up in the same <b>Follow</b> control, and the "
           '<a href="data.html#privacy">Data page</a> says what is kept and for how '
           "long."),
}


# ---------------------------------------------------------------------------
# THE COURSE OF A BILL, AS A DIAGRAM.
#
# Written as data rather than as a wall of HTML so the sequence can be read
# and corrected here, in one place, by somebody who knows the building. It
# renders as nested ordered lists -- see the .flow rules in app.css for why
# that rather than an SVG.
#
# Each step is (name, what happens, mark), where mark is:
#   "stop" -- the bill can die here, and most bills die at one of these
#   "say"  -- a member of the public can speak here
#   ""     -- neither
# The marks are the argument of the diagram. A reader arrives thinking a bill
# moves along a pipeline; the shape they should leave with is a course with
# exits at almost every stage.
# ---------------------------------------------------------------------------
FLOW = [
    ("Before It Is a Bill", [
        ("Filed as a request", "A Legislative Service Request, or LSR: a title "
         "and an idea, filed in the fall. Attorneys at the Office of Legislative "
         "Services draft the text.", ""),
    ]),
    ("The First Chamber", [
        ("Introduced and referred", "It gets a number and goes to a committee "
         "chosen by subject.", ""),
        ("Public hearing", "The sponsor introduces it, then anyone may speak "
         "for or against, or sign in without speaking.", "say"),
        # NOT A PLACE A BILL DIES, and so no mark. The House Rules (Rule 50 in
        # 1995 and 1997, Rule 42 in 2018) and the Senate Rules (4-2 and 4-3,
        # as printed in the Senate Journal of 7 December 2022) both require a
        # committee to report every bill it is given -- with no recommendation
        # if it cannot agree -- so the floor, not the committee, ends a bill.
        ("Executive session", "The committee votes on what to recommend. A "
         "separate meeting from the hearing, often days later. It cannot end "
         "the bill itself: the recommendation goes to the floor.", ""),
        ("Floor vote", "The full chamber decides, and is not bound by the "
         "committee's recommendation.", "stop"),
    ]),
    ("The Second Chamber", [
        ("Referred again", "The whole course repeats. Moving between chambers "
         "is called crossover, and there is a deadline for it.", ""),
        # TWO STEPS AND NOT ONE. Folded together, the diagram showed a single
        # "you may speak here" in the whole course, which is wrong and is
        # wrong in the direction that matters: a bill gets a public hearing in
        # each chamber, so a reader who missed the first has not missed their
        # chance. Splitting it also makes the two chambers read as the same
        # course run twice, which is the point of the page.
        ("Public hearing", "A second committee, a second public hearing. "
         "Missing the first chamber's does not cost you this one.", "say"),
        ("Executive session", "The second committee votes on its own "
         "recommendation, which goes to that chamber's floor.", ""),
        ("Floor vote", "If this chamber changes the bill, the first must "
         "agree to the change.", "stop"),
        ("Committee of conference", "Where it will not agree: members of both "
         "chambers try to write a version each will accept. Both chambers "
         "must then adopt the report unchanged.", "stop"),
    ]),
    ("The Governor", [
        ("Enrollment", "A final check of the text for errors before it is "
         "sent.", ""),
        ("Signed, vetoed, or left unsigned", "A bill left unsigned for five "
         "days, Sundays excepted, becomes law without a signature, unless the "
         "legislature's adjournment prevents its return.", "stop"),
        ("Override", "Two thirds of each chamber, by roll call, or the veto "
         "stands. The House counts the two thirds among the members "
         "voting.", "stop"),
    ]),
]

# THE MARKS. A step's mark says what can happen there, in words and in a
# colour, never in colour alone. It sits under its step as two grid cells --
# the glyph or the fraction in one, the words in the next -- so the one
# cannot run into the other at any width or text size: the constitution's
# "3/5" was one font glyph wider than the box it sat in and ran under its
# words on a phone (the person, 9 October 2026, item 20).
#
# A mark is a key of MARKS, or a (key, words) pair where the words differ
# step by step -- a constitutional threshold is a different number in each
# chamber, and "Needs a threshold" would be a worse sentence than the number
# it stands for:
#   "stop"  -- the bill can die here: the rail's red cross
#   "say"   -- a member of the public can speak here: the hearing's colour
#   "needs" -- a threshold or a time limit, in amber (8 October 2026:
#              "constitution threshold marks keep amber"); where the words
#              name a fraction (FRACTIONS) the fraction is drawn, built of two
#              numbers over a rule rather than a font's fraction glyph
#   "rec"   -- something the record keeps: pine, with a check (a sign-in is
#              counted, which is not a threshold)
#   "sub"   -- no mark at all: a quiet line under a row's name (a floterial
#              is laid over other districts, which is not a threshold either)
#
# THE CLASSES ARE l- ONES, Learn's own prefix. `.stop` is the passage rail's
# class, and reusing it once rendered every marked step as invisible words in
# a grey disc; a new component gets its own prefix.
X_SVG = ('<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3.3 3.3l5.4 5.4M8.7 3.3l-5.4 5.4" '
         'fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>')
CHECK_SVG = ('<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.6 6.3l2.3 2.3 4.6-5" fill="none" '
             'stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>')
SAY_SVG = ('<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.2 2.6h7.6v5H5.4L3.2 9.4V7.6h-1z" '
           'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>')
MARKS = {"stop": ("dies", "Can die here"),
         "say": ("say", "You may speak here"),
         "needs": ("need", ""),
         "rec": ("rec", ""),
         "sub": ("sub", "")}
GLYPHS = {"dies": X_SVG, "say": SAY_SVG, "rec": CHECK_SVG}
# The words a threshold mark carries, and the fraction they name.
FRACTIONS = {"Three fifths of its members": "3/5",
             "Two thirds of those voting on it": "2/3"}
# The key under the constitution's diagram (new wording of the first round's
# prototype, which the person liked on 9 October 2026).
THRESHOLD_KEY = ('<i class="l-capsw" aria-hidden="true"></i>A threshold, in amber: '
                 'the share of votes the step needs.')


def mark_of(mark):
    """(kind, words) for a mark: ("", "") for none."""
    if isinstance(mark, (tuple, list)) and len(mark) == 2:
        kind, _ = MARKS.get(mark[0], ("", ""))
        return kind, mark[1]
    return MARKS.get(mark, ("", ""))


def frac(f, large=False):
    """A fraction built of two numbers over a rule, read aloud by its words."""
    top, bottom = f.split("/")
    return (f'<span class="l-frac{" is-l" if large else ""}" aria-hidden="true">'
            f'<span>{top}</span><span>{bottom}</span></span>')


def mark_html(mark):
    """A step's mark: its glyph (or fraction) and its words, in two cells."""
    kind, words = mark_of(mark)
    if not kind or not words:
        return ""
    if kind == "sub":
        return f'<span class="l-sub">{words}</span>'
    if kind == "need":
        glyph = frac(FRACTIONS[words]) if words in FRACTIONS else ""
    else:
        glyph = f'<span class="l-g is-{kind}" aria-hidden="true">{GLYPHS[kind]}</span>'
    return (f'<span class="l-mk is-{kind}{"" if glyph else " is-bare"}">{glyph}'
            f'<span class="l-mt">{words}</span></span>')


def step_html(step, what, mark):
    kind, _ = mark_of(mark)
    return (f'<li class="l-step{" is-" + kind if kind else ""}">'
            f'<b>{step}</b><span>{what}</span>{mark_html(mark)}</li>')


def wide(html_):
    """A figure that takes the page's whole width under its section's
    heading, where the prose keeps its measure beside the heading.
    build_civics reads the markers; a figure without them stays in the
    reading column."""
    return f"<!--wide-->{html_}<!--/wide-->"


def faq(*pairs):
    """COMMON QUESTIONS (the person, 26 October 2026: "FAQ could be used to
    trim down some of the finer details in the general guides so that people
    who want to know more can view the faq dropdown near the end and the
    guide and learn pages stay more streamlined for a general audience").
    A section of its own, each question a <details> that opens on its answer:
    the finer points a page's steps or sections need not carry, still on the
    page, still searchable, and printed open. `pairs` is [(question, answer
    HTML)], each answer resting on what the page's sources already say."""
    return ('<h2>Common Questions</h2><div class="l-faq">'
            + "".join(f"<details><summary>{q}</summary>{a}</details>" for q, a in pairs)
            + "</div>")


def flow_diagram(flow=FLOW, heading="The course of a bill", level=3, key="", level_names=False):
    """The sequence as nested lists. No image, no script, no SVG but the marks.

    The phases go across the page, a column each, where there is room for
    them (four from 60em, two from 37.5em, one on a phone), with an arrow
    between. level is what the phase names are written at: every diagram
    sits under its section's h2 now, so they are h3 by default. key is a line
    under the diagram that says what its colour means; level_names holds the
    phase names level however many lines one takes, for a diagram whose
    names differ in length (how a rule is made).
    """
    phases = "".join(
        f'<li class="l-phase"><h{level} class="l-phname">{name}</h{level}>'
        f'<ol class="l-steps">{"".join(step_html(*s) for s in steps)}</ol></li>'
        for name, steps in flow)
    cap = f'<figcaption class="l-cap">{key}</figcaption>' if key else ""
    return wide(f'<figure class="l-fig l-flow{" l-level" if level_names else ""}" role="group" '
                f'aria-label="{heading}"><ol class="l-phases">{phases}</ol>{cap}</figure>')


# TWO WAYS OF DOING THE SAME THING, compared stage by stage. flow_diagram draws
# one course; some of these pages are about a choice between two -- a town
# meeting against an SB 2 town, a statute against a constitutional amendment,
# three forms of town government -- and the only honest picture of a choice is
# the two side by side, the same stage on the same line.
#
# A TABLE, because that is what it is. A screen reader announces a cell with
# its row and its column, so "the vote, SB 2 town: by official ballot" arrives
# as one thing rather than as a paragraph the listener has to hold against the
# one before it. Still no image, no script and no SVG: it is right with
# JavaScript off, which is the reader the <noscript> block is failing.
#
# SAME means the two forms do not differ at that stage. The cell spans both
# columns rather than repeating the sentence, because a row that says the same
# thing twice reads as a difference the reader has failed to spot.
#
# A cell is text, or (text, mark) with a mark from MARKS -- "say" on the cell
# where a member of the public can speak is the most useful one here, since
# where you speak and where you vote are the whole difference between the two.
SAME = object()


def compare_diagram(rows, heading, left, right):
    # THE ROLES ARE NOT DECORATION. On a phone the table is restacked, which
    # means changing display on its rows and cells, and a browser that sees a
    # table given display:block may drop it from the accessibility tree
    # altogether -- Safari does -- taking away the one reason it is a table.
    # Explicit roles put the semantics back whatever the layout is doing.
    def cell(v, col, span=""):
        text, mark = (v if isinstance(v, (tuple, list)) else (v, ""))
        kind, _ = mark_of(mark)
        cls = f' class="is-{kind}"' if kind else ""
        return (f'<td role="cell"{span}{cls} data-l="{col}"><span>{text}</span>'
                + mark_html(mark) + "</td>")
    out = [f'<figure class="l-fig l-cmp" role="group" aria-label="{heading}">'
           f'<table class="l-cmptab" role="table">'
           f'<caption class="sr">{heading}</caption>'
           '<thead role="rowgroup"><tr role="row">'
           '<th scope="col" role="columnheader">Stage</th>'
           f'<th scope="col" role="columnheader">{left}</th>'
           f'<th scope="col" role="columnheader">{right}</th>'
           '</tr></thead><tbody role="rowgroup">']
    for stage, a, b in rows:
        out.append(f'<tr role="row"><th scope="row" role="rowheader">'
                   f'{stage}</th>')
        if a is SAME or b is SAME:
            out.append(cell(b if a is SAME else a, f"{left} and {right}", ' colspan="2"'))
        else:
            out.append(cell(a, left) + cell(b, right))
        out.append("</tr>")
    out.append("</tbody></table></figure>")
    return wide("".join(out))


# ---------------------------------------------------------------------------
# THE FIGURES THE APPROVED PAGES DRAW (the person, 9 October 2026: "feel free
# to build out and revise the remaining Learn pages"; the Learn standard asks
# for a diagram wherever a shape is hard to hold in prose). Every one is drawn
# from its own page's sentences or numbers and adds no fact: a count comes in
# as a figure build_civics counted from the record, and the words are the
# paragraph's own, shortened where a box is small. Each is a list, a table or
# a set of boxes, so a screen reader reads what a sighted reader sees, and a
# bar says its numbers in a key beside a swatch, never in colour alone.
# ---------------------------------------------------------------------------

def bar(caption, label, parts):
    """A proportion bar and its key: parts [(n, swatch, words)], n an int,
    or (n, swatch, words, False) for a part the page names without a figure
    of its own ("every other outcome")."""
    segs, key = [], []
    for part in parts:
        n, cls, words = part[:3]
        said = part[3] if len(part) > 3 else True
        if n <= 0:
            continue
        segs.append(f'<i class="{cls}" style="flex:{n}"></i>')
        key.append(f'<li><span class="l-sw {cls}" aria-hidden="true"></span><span>'
                   + (f"<b>{n:,}</b> " if said else "") + f"{words}</span></li>")
    return (f'<figure class="l-fig l-bar" role="group" aria-label="{label}">'
            f'<figcaption>{caption}</figcaption>'
            f'<div class="l-barb" aria-hidden="true">{"".join(segs)}</div>'
            f'<ul class="l-barkey">{"".join(key)}</ul></figure>')


def chain(label, links, n=None, wide_=False):
    """Who acts, in turn: [(who, what)], an arrow between, the last box the
    outcome. On a phone it runs down the page."""
    end = ' class="is-end"'
    lis = "".join(
        f'<li{end if k == len(links) - 1 else ""}><b>{who}</b>'
        + (f"<span>{what}</span>" if what else "") + "</li>"
        for k, (who, what) in enumerate(links))
    html_ = (f'<ol class="l-chain" style="--n:{n or len(links)}" aria-label="{label}">{lis}</ol>')
    return wide(f'<figure class="l-fig l-chainfig">{html_}</figure>') if wide_ else html_


def boxes(label, items):
    """Bodies side by side, each with what it is: [(name, line, [(field, text)])]."""
    out = []
    for name, line, rows in items:
        dl = "".join(f"<div><dt>{f}</dt><dd>{t}</dd></div>" for f, t in rows)
        out.append(f'<section class="l-body"><h3>{name}</h3><p class="l-lbl">{line}</p><dl>{dl}</dl></section>')
    return wide(f'<div class="l-who" style="--n:{len(items)}" role="group" aria-label="{label}">'
                + "".join(out) + "</div>")


def course_diagram(flow=FLOW, heading="The course of a bill"):
    """How a bill becomes law, with the two chambers side by side, step against
    step -- the page's point, "the same course twice" -- the word crossover on
    the arrow between them, and the Governor's three steps across under them
    (the person's answer to the round-two question 9a, as recommended)."""
    (n0, s0), (n1, s1), (n2, s2), (n3, s3) = flow

    def steps(xs, cls=""):
        return f'<ol class="l-steps{cls}">' + "".join(step_html(*s) for s in xs) + "</ol>"
    return wide(
        f'<figure class="l-fig l-course" role="group" aria-label="{heading}"><ol class="l-cphases">'
        f'<li class="l-cp l-cp-a"><h3 class="l-phname">{n0}</h3>{steps(s0)}</li>'
        f'<li class="l-cp l-cp-h1"><h3 class="l-phname">{n1}</h3>{steps(s1)}'
        '<span class="l-cpx" aria-hidden="true">crossover</span></li>'
        f'<li class="l-cp l-cp-h2"><h3 class="l-phname">{n2}</h3>{steps(s2)}</li>'
        f'<li class="l-cp l-cp-g"><h3 class="l-phname">{n3}</h3>{steps(s3, " l-gsteps")}</li>'
        '</ol></figure>')


def yn(yes, words=None):
    return (f'<span class="l-yn {"is-y" if yes else "is-n"}"><span>'
            f'{words or ("Yes" if yes else "No")}</span></span>')


# HOW A CHAMBER VOTES: the paragraph's three definitions set side by side.
WAYS_OF_VOTING = (
    '<div class="l-tablewrap l-stack"><table class="l-table">'
    "<caption>What each way of voting records</caption>"
    '<thead><tr><th scope="col">Way</th><th scope="col">Which side won</th>'
    '<th scope="col">The count</th><th scope="col">Each member&rsquo;s name</th></tr></thead><tbody>'
    + "".join(f'<tr><th scope="row">{way}</th><td data-l="Which side won">{a}</td>'
              f'<td data-l="The count">{b}</td><td data-l="Each name">{c}</td></tr>'
              for way, a, b, c in (
                  ("Voice vote", yn(True, "Which side sounded louder"), yn(False), yn(False)),
                  ("Division", yn(True), yn(True), yn(False)),
                  ("Roll call", yn(True), yn(True), yn(True))))
    + "</tbody></table></div>")

# THE TWO VOTES THAT NEED MORE THAN A MAJORITY, side by side, each threshold
# as an amber fraction with what it is counted against, its article and the
# paragraph's example.
THRESHOLDS = (
    '<div class="l-thr" role="group" aria-label="The two votes that need more than a majority">'
    '<div class="l-thrb"><p class="l-thrh">Overriding a veto</p>'
    f'<span class="l-mk is-need">{frac("2/3", True)}<span class="l-mt">two thirds of each chamber, '
    'by roll call</span></span>'
    "<dl><dt>Counted against</dt><dd>the members voting</dd><dt>Authority</dt>"
    "<dd>Part Second, Article 44</dd><dt>Example</dt>"
    "<dd>August 2026: 231 to 88, with 384 members in office</dd></dl></div>"
    '<div class="l-thrb"><p class="l-thrh">Amending the constitution</p>'
    f'<span class="l-mk is-need">{frac("3/5", True)}<span class="l-mt">three fifths of the '
    "members of each chamber</span></span>"
    f'<span class="l-mk is-need">{frac("2/3", True)}<span class="l-mt">then two thirds of those '
    "voting on the question, at the election</span></span>"
    "<dl><dt>Counted against</dt><dd>every member in office: 240 when all 400 House seats are "
    "filled</dd><dt>Authority</dt><dd>Part Second, Article 100</dd></dl></div></div>")


def _end(ok, words):
    return (f'<li class="l-end"><span class="l-g {"is-p" if ok else "is-x"}" aria-hidden="true">'
            f'{CHECK_SVG if ok else X_SVG}</span><span>{words}</span></li>')


# THE GOVERNOR'S THREE ANSWERS, as routes from the page's two paragraphs,
# each ending in the rail's green check or red cross. On a phone the three
# stack, and the second and third are headed "Or": they are alternatives, not
# steps.
GOVERNOR_ROUTES = wide(
    '<figure class="l-fig l-routes" role="group" aria-label="What the Governor may do with a bill">'
    '<p class="l-rstart">A bill has passed both chambers</p><ol class="l-rcols">'
    '<li class="l-rcol"><h3 class="l-rh">The Governor signs it</h3><ul class="l-rends">'
    + _end(True, "It becomes law.") + "</ul></li>"
    '<li class="l-rcol"><span class="l-ror" aria-hidden="true">Or</span>'
    '<h3 class="l-rh">The Governor vetoes it</h3>'
    '<div class="l-rstep l-step is-need"><b>The legislature may override</b>'
    "<span>Starting with the chamber the bill came from.</span>"
    f'<span class="l-mk is-need">{frac("2/3")}<span class="l-mt">Two thirds of each chamber, '
    'by roll call</span></span></div><ul class="l-rends">'
    + _end(True, "<b>Overridden:</b> it becomes law over the Governor&rsquo;s objection.")
    + _end(False, "<b>Not overridden:</b> the veto stands.") + "</ul></li>"
    '<li class="l-rcol"><span class="l-ror" aria-hidden="true">Or</span>'
    '<h3 class="l-rh">The Governor does nothing</h3>'
    '<div class="l-rstep l-step"><b>Five days pass</b><span>Sundays excepted.</span></div>'
    '<ul class="l-rends">'
    + _end(True, "It becomes law without a signature,")
    + _end(False, "unless the legislature&rsquo;s adjournment prevents its return: then it does "
                  "not become law at all.") + "</ul></li></ol></figure>")

# WHO GOVERNS A COUNTY: the three bodies the page names, each with who they
# are and what they do in its own sentences, shortened, with their RSA.
_RSA = '<span class="l-rsa">({})</span>'
COUNTY_BODIES = boxes("Who governs a county", [
    ("The Convention", "The county delegation", [
        ("Who", "The state representatives of the representative districts of the county. "
                "Nobody is elected to it separately. " + _RSA.format("RSA 24:1")),
        ("What it does", "Adopts the budget; raising county taxes and making appropriations "
                         "are its powers. " + _RSA.format("RSA 24:13"))]),
    ("The Commissioners", "Three in every county", [
        ("Who", "One chosen from each of three county commissioner districts. "
                + _RSA.format("RSA 662:4")),
        ("What they do", "The county&rsquo;s executive: they run its departments from day to day "
                         "and prepare the budget the convention votes on.")]),
    ("Five Elected Officers", "On the county part of your ballot", [
        ("Who", "A sheriff, a county attorney, a county treasurer, a register of deeds and a "
                "register of probate."),
        ("Term", "Two years, except in Rockingham and Coos, which moved to four-year terms. "
                 + _RSA.format("RSA 653:1, V"))])])

# THE COUNTY BUDGET, STEP BY STEP: the page's five paragraphs as a numbered
# line, each with the time limit it states as an amber tag.
COUNTY_LIMITS = {
    "The commissioners propose.": "Before December 1 (June 1 on an optional fiscal year)",
    "There is a public hearing.": "5 to 20 days after it is mailed",
    "The executive committee examines it.": "",
    "The delegation votes.": "Not until 28 days after it is mailed",
    "Missing the deadline has a consequence.":
        "Within 90 days of the fiscal year&rsquo;s start (September 1 on an optional fiscal year)",
}


def county_budget(paragraphs):
    """The budget's paragraphs, "<p><b>Step.</b> ...</p>", as the numbered line.
    Stops the build if the paragraphs and the limits stop matching, so a step
    rewritten in the prose cannot lose its tag silently."""
    steps = re.findall(r"<p><b>(.*?)</b>(.*?)</p>", paragraphs, re.S)
    assert [b for b, _ in steps] == list(COUNTY_LIMITS), [b for b, _ in steps]
    lis = "".join(
        f"<li><p><b>{b}</b>{rest}</p>"
        + (mark_html(("needs", COUNTY_LIMITS[b])) if COUNTY_LIMITS[b] else "") + "</li>"
        for b, rest in steps)
    return f'<ol class="l-time" aria-label="How the county budget is decided">{lis}</ol>'


# WHO DECIDES, AND WHO CARRIES IT OUT: the lead's three arrangements side by side.
TOWN_FORMS = boxes("Who decides, and who carries it out", [
    ("A Town", "A meeting and a selectboard", [
        ("Decides", "The voters themselves, assembled at town meeting."),
        ("Carries it out", "The selectmen: one elected each year for a 3-year term, a board of "
                           "three. " + _RSA.format("RSA 41:8"))]),
    ("A City with a Mayor", "A council and a mayor", [
        ("Decides", "The city council, or board of aldermen, which exercises the powers the law "
                    "vests in towns. " + _RSA.format("RSA 47:1")),
        ("Carries it out", "The mayor, the chief executive officer, with a veto the aldermen can "
                           "override only by two thirds of all the aldermen elected. "
                           + _RSA.format("RSA 45:7, 45:9"))]),
    ("A Council and a Manager", "A charter city", [
        ("Decides", "The council, which enacts the policies."),
        ("Carries it out", "A city manager the council appoints, heading the administrative "
                           "branch; the mayor chairs the council. "
                           + _RSA.format("RSA 49-C:16, 49-C:17"))])])

# HOW A CHARTER IS ADOPTED: the page's own sentences, with its two thresholds.
FLOW_CHARTER = [
    ("How It Starts", [
        ("A petition of voters", "25 registered voters, or 2 percent of them, whichever is less "
         "and never fewer than 10. (RSA 49-B:3)", ("needs", "25 voters or 2 percent, at least 10")),
    ]),
    ("The Ballot", [
        ("Shall a charter commission be established?", "The question the voters are asked. "
         "(RSA 49-B:3)", ""),
    ]),
    ("The Commission", [
        ("Nine members, elected", "It writes the charter and reports. (RSA 49-B:4)", ""),
    ]),
    ("The Voters Again", [
        ("The charter goes back to the voters", "It takes effect only if three fifths of the "
         "ballots cast on the question favor it. (RSA 49-B:6)",
         ("needs", "Three fifths of the ballots cast on it")),
    ]),
]


# WHICH MEETINGS YOU MAY ATTEND, AND WHERE YOU MAY SPEAK: the paragraph's rule
# as a table, each meeting by the calendar's own chip, its words and class
# read from the words file the Calendar reads (src/pages/words/), so a reader
# meets the same chip there.
def _meeting_chip(kind):
    import components
    word, cls = components.WORDBOOK["meeting_kinds"]["kinds"][kind]
    # THE ONE CHIP (Polish 1's step 3), with the Calendar's hook beside it.
    return components.chip(word, f"calkind {cls}")


WHERE_TO_SPEAK = (
    '<div class="l-tablewrap l-stack l-speak"><table class="l-table">'
    "<caption>Which meetings you may attend, and where you may speak</caption>"
    '<thead><tr><th scope="col">Meeting</th><th scope="col">Attend</th><th scope="col">Speak</th>'
    "</tr></thead><tbody>"
    + "".join(f'<tr><th scope="row">{_meeting_chip(k)}</th><td data-l="Attend">{yn(True)}</td>'
              f'<td data-l="Speak">{speak}</td></tr>'
              for k, speak in (
                  ("public hearing", yn(True, "Yes: the only meeting at which the public is heard")),
                  ("executive session", yn(False)),
                  ("subcommittee work session", yn(False)),
                  ("work session", yn(False))))
    + "</tbody></table></div>")

# A BILL'S TABS, as a picture of the strip over the list of what each holds:
# the shape before its parts. The names are the list's own; it is a picture,
# so a screen reader is not told about tabs that are not there.
BILL_TABS_PICTURE = (
    '<div class="l-mock" aria-hidden="true"><p class="l-lbl">A bill&rsquo;s tabs</p>'
    '<div class="l-mocktabs">'
    + "".join(('<span class="is-on">' if k == 0 else "<span>") + t + "</span>" for k, t in enumerate(
        ("Summary", "Bill Text", "Votes", "Hearings", "Reports", "Sponsors", "Documents")))
    + "</div></div>")


STUDY_SVG = ('<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M1.6 7.1c1.1-1.9 2.3-1.9 3.4-.5s2.3 '
             '1.4 3.4-.5 1.9-1.6 2-.6" fill="none" stroke="currentColor" stroke-width="1.8" '
             'stroke-linecap="round"/></svg>')


def seats_figure(house, house_sitting, senate, senate_sitting, lang="en"):
    """THE TWO CHAMBERS AS SQUARES, one a seat, a vacant seat hollow: the
    page's "400 representatives and 24 senators" and In the Record's vacancies,
    counted from the district map and the roster. Its words in `lang` (the
    Learn pages in Spanish, 25 October 2026)."""
    hv, sv = max(house - house_sitting, 0), max(senate - senate_sitting, 0)

    def group(name, n, vacant):
        dots = "<i></i>" * (n - vacant) + '<i class="is-v"></i>' * vacant
        return (f'<div class="l-sg"><p class="l-sgh"><b>{name}</b>'
                + I.say(lang, "reps.n_seats", "{n} seats", n=f"{n:,}") + "</p>"
                f'<div class="l-dots" aria-hidden="true">{dots}</div></div>')
    where = (" " + I.say(lang, "learn.and", "and") + " ").join(x for x in (
        I.say(lang, "learn.seats.in_house", "{n} in the House", n=f"{hv:,}") if hv else "",
        I.say(lang, "learn.seats.in_senate", "{n} in the Senate", n=f"{sv:,}") if sv else "") if x)
    label = (I.say(lang, "learn.seats.house_has", "The House has {n} seats", n=f"{house:,}")
             + ((I.say(lang, "learn.seats.vacant_record_one", ", {n} of them vacant as the record "
                       "stands", n=f"{hv:,}") if hv == 1 else
                 I.say(lang, "learn.seats.vacant_record", ", {n} of them vacant as the record stands",
                       n=f"{hv:,}")) if hv else "")
             + I.say(lang, "learn.seats.senate_has", "; the Senate has {n}", n=f"{senate:,}")
             + ((I.say(lang, "learn.seats.vacant_one", ", {n} of them vacant", n=f"{sv:,}") if sv == 1
                 else I.say(lang, "learn.seats.vacant", ", {n} of them vacant", n=f"{sv:,}")) if sv else "")
             + ".")
    cap = ('<i class="l-key is-me" aria-hidden="true"></i>'
           + I.say(lang, "learn.seats.one_square", "One square, one seat.")
           + (' <i class="l-key" aria-hidden="true"></i>'
              + I.say(lang, "learn.seats.hollow", "A hollow square is a vacant seat: {where} as the "
                      "record stands.", where=where) if where else ""))
    return (f'<figure class="l-fig l-seats" role="img" aria-label="{label}">'
            + group(I.say(lang, "learn.seats.house", "House"), house, hv)
            + group(I.say(lang, "learn.seats.senate", "Senate"), senate, sv)
            + f"<figcaption>{cap}</figcaption></figure>")


def term_figure(term, lang="en"):
    """TWO WAYS A BILL OUTLASTS ITS FIRST YEAR, through the term: the two
    paragraphs' facts in the order a term runs, retained against interim study,
    with the rail's orange mark for interim study. The years are the current
    term's, as the page's own example of a term is. Its words in `lang` (the
    Learn pages in Spanish, 25 October 2026)."""
    a, b = (term.split("-") + [""])[:2]
    nxt = (f"{int(b) + 1}&ndash;{int(b) + 2}" if b.isdigit()
           else I.say(lang, "learn.term.next_term", "the next term"))
    first = I.say(lang, "learn.term.first", "First year ({year})", year=a)
    second = I.say(lang, "learn.term.second", "Second year ({year})", year=b)
    then = I.say(lang, "learn.term.then", "The next term ({years})", years=nxt)

    def box(cls, glyph, head, words, go=False):
        g = f'<span class="l-g {glyph}" aria-hidden="true">{GLYPH_OF[glyph]}</span>' if glyph else ""
        return (f'<span class="l-tbox {cls}{" is-go" if go else ""}"><b>{g}{head}</b>{words}</span>')
    none = '<td data-l="{}" class="is-none">&mdash;</td>'
    return wide(
        '<figure class="l-fig l-term" role="group" aria-label="'
        + I.say(lang, "learn.term.label", "Retained or sent to interim study, through a two-year term")
        + '"><div class="l-tablewrap l-stack"><table class="l-table"><caption>'
        + I.say(lang, "learn.term.caption", "Two ways a bill outlasts its first year") + "</caption>"
        '<thead><tr><th scope="col">' + I.say(lang, "learn.term.which", "Which") + "</th>"
        f'<th scope="col">{first}</th>'
        f'<th scope="col">{second}</th><th scope="col">{then}</th></tr></thead><tbody>'
        '<tr><th scope="row" class="is-text">' + I.say(lang, "learn.term.retained", "Retained")
        + '<span class="l-sub">' + I.say(lang, "learn.term.first_only", "first year only")
        + "</span></th>"
        f'<td data-l="{first}">' + box("is-keep", "", I.say(lang, "learn.term.kept", "Kept by the committee"),
                                       I.say(lang, "learn.term.kept_words",
                                             "for more work, and studied over the fall."), True) + "</td>"
        f'<td data-l="{second}">' + box("is-keep", "is-p",
                                        I.say(lang, "learn.term.reported", "Reported and voted on"),
                                        I.say(lang, "learn.term.reported_words",
                                              "like any other bill. It keeps its number, and shows "
                                              "here as carried over.")) + "</td>"
        + none.format(then) + "</tr>"
        '<tr><th scope="row" class="is-text">' + I.say(lang, "learn.term.study", "Interim study")
        + '<span class="l-sub">' + I.say(lang, "learn.term.second_only", "second year only")
        + "</span></th>"
        + none.format(first)
        + f'<td data-l="{second}">' + box("is-study", "is-study",
                                          I.say(lang, "learn.term.studied", "Studied over the fall"),
                                          I.say(lang, "learn.term.studied_words",
                                                "The committee may report on it, but the bill itself "
                                                "dies with the term."), True) + "</td>"
        f'<td data-l="{then}">' + box("is-new", "", I.say(lang, "learn.term.filed", "Filed again"),
                                      I.say(lang, "learn.term.filed_words",
                                            "To come back it has to be a new bill, with a new number."))
        + "</td></tr></tbody></table></div></figure>")


GLYPH_OF = {"is-p": CHECK_SVG, "is-study": STUDY_SVG}


# EVERYONE WHO REPRESENTS ONE ADDRESS, from the most local seat to the whole
# state. The finding-your-representatives page explains in prose that most
# towns and wards have more than one state representative and that a
# floterial district is laid over others; this shows it for one real town,
# where a reader can count.
#
# COUNTED FROM THE RECORD, NOT TYPED. The rows are built from site/districts.json
# at build time by reps_example(), so the next redistricting redraws them rather
# than leaving a page that names districts which no longer exist. build_civics
# computes it into the [[reps_example]] figure the page carries.
#
# A table for the same reason compare_diagram is one: a screen reader reads
# "State House, floterial; district Belknap 8; members 2; elected by ..." as one
# row. Explicit roles because the rows restack on a phone.
def reach(places, town):
    """Under a seat's row, the places that vote for it: by name where there
    are a few, one square each where there are more (the reader's own town
    filled), a band for the whole state. A picture of the row's own count, so
    a screen reader is told the count in the row and not the squares."""
    if places is None:
        return '<span class="l-reach" aria-hidden="true"><b></b></span>'
    if len(places) <= 4:
        return ('<span class="l-reach" aria-hidden="true">' + "".join(
            ('<span class="is-me">' if p == town else "<span>") + f"{p}</span>" for p in places)
            + "</span>")
    return ('<span class="l-reach" aria-hidden="true">' + "".join(
        '<i class="is-me"></i>' if p == town else "<i></i>" for p in places) + "</span>")


def layers_diagram(rows, heading, town="", lang="en"):
    """The table of everyone who represents one town (reps_example), its
    words in `lang` (the owner's guides in Spanish, 24 October 2026)."""
    seat = I.say(lang, "reps.seat", "Seat")
    district_ = I.say(lang, "reps.district_col", "District")
    members_ = I.say(lang, "reps.members", "Members")
    by = I.say(lang, "reps.elected_by", "Elected by")
    out = [f'<figure class="l-fig l-lay" role="group" aria-label="{heading}">'
           f'<div class="l-tablewrap l-stack"><table class="l-table" role="table">'
           f'<caption class="sr">{heading}</caption>'
           '<thead role="rowgroup"><tr role="row">'
           f'<th scope="col" role="columnheader">{seat}</th>'
           f'<th scope="col" role="columnheader">{district_}</th>'
           f'<th scope="col" role="columnheader">{members_}</th>'
           f'<th scope="col" role="columnheader">{by}</th>'
           '</tr></thead><tbody role="rowgroup">']
    for layer, district, members, shared, mark, places in rows:
        out.append(
            f'<tr role="row">'
            f'<th scope="row" role="rowheader" class="is-text">{layer}{mark_html(mark)}</th>'
            f'<td role="cell" data-l="{district_}">{district}</td>'
            f'<td role="cell" data-l="{members_}">{members}</td>'
            f'<td role="cell" data-l="{by}" class="l-by">{shared}{reach(places, town)}</td></tr>')
    out.append("</tbody></table></div><figcaption>" + I.say(
        lang, "reps.caption", "Under each row, one square for each town or city that votes for the "
        'seat: <i class="l-key is-me" aria-hidden="true"></i>{town}, '
        '<i class="l-key" aria-hidden="true"></i>another town or city.', town=town)
        + "</figcaption></figure>")
    return wide("".join(out))


# THE WORKED EXAMPLE IS DANVILLE, chosen by checking every town that has a
# one-town district of its own and exactly one floterial -- 31 of them -- on
# three counts. Its floterial, Rockingham 32, lies exactly over three one-town
# districts, Brentwood (Rockingham 6), Fremont (7) and Danville (8), so the
# lesson is symmetric: each town elects one member of its own and the three
# elect one more together. All three sit in the same Senate, Council and US
# House districts, so every layer nests -- Belmont, the first choice, does not,
# because its floterial crosses into a second Senate district and the picture
# would have lied about nesting. And RSA 662, site/districts.json and the
# Secretary of State's data agree on every layer of its chain.
REPS_EXAMPLE = "Danville"


def _names(xs, lang="en"):
    xs = list(xs)
    return (xs[0] if len(xs) == 1 else ", ".join(xs[:-1])
            + I.say(lang, "reps.and", " and ") + xs[-1])


_WORD = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
# The same small numbers in the languages the guides are in (i18n.PAGES):
# a number word is a form of the number, like a date's month.
_WORDS = {"en": _WORD, "es": {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis"}}


def reps_example(districts, town=REPS_EXAMPLE, lang="en"):
    """Every figure the page states about its worked example, from
    site/districts.json: the diagram itself, and the few facts the prose
    beside it names -- which floterial, what it is laid over, how many. They
    are figures rather than typed text for the diagram's own reason: typed
    beside a diagram that redraws itself, they would be the half of the page
    that went stale at the next redistricting.

    Stops the build where the diagram would be wrong or pointless: the town
    gone, split into wards, or no longer in exactly one floterial district. A
    redistricting that did that silently would publish a page teaching
    floterials with an example that has none. Where the town merely comes to
    share its own district with neighbours the diagram still tells the truth,
    so it says so and warns rather than stopping."""
    wards = districts.get(town)
    if not wards or list(wards) != ["0"]:
        raise SystemExit(f"reps_example: {town} is missing from districts.json "
                         "or is split into wards; choose another REPS_EXAMPLE")
    rec = wards["0"]
    own = [h for h in rec.get("house") or [] if not h.get("floterial")]
    flot = [h for h in rec.get("house") or [] if h.get("floterial")]
    if len(own) != 1 or len(flot) != 1:
        raise SystemExit(
            f"reps_example: {town} now has {len(own)} district(s) of its own "
            f"and {len(flot)} floterial(s); the diagram needs exactly one of "
            "each. Choose another REPS_EXAMPLE.")

    def others(match):
        """Every other town or city with a ward that matches, and whether any
        of them is a city -- which decides 'towns' against 'towns and
        cities' in the sentence."""
        hit = sorted(t for t, ws in districts.items()
                     if t != town and any(match(w) for w in ws.values()))
        city = any(list(districts[t]) != ["0"] for t in hit)
        return hit, ("towns and cities" if city else "towns")

    def in_house(h):
        key = (h["county"], h["district"])
        return lambda w: any((x.get("county"), x.get("district")) == key
                             for x in w.get("house") or [])

    o, f = own[0], flot[0]
    own_with, _ = others(in_house(o))
    flot_with, _ = others(in_house(f))
    # How many districts the floterial is laid over: every non-floterial
    # district of the same county that one of its places also belongs to.
    under = {(x["county"], x["district"])
             for t in [town] + flot_with for w in districts[t].values()
             if in_house(f)(w)
             for x in w.get("house") or [] if not x.get("floterial")}
    if own_with:
        print(f"  reps_example: {town} now shares its own district with "
              f"{_names(own_with)}; the diagram says so, but a one-town "
              "district teaches the point more cleanly")

    def wide(n, kind):
        if kind == "towns":
            return I.say(lang, "reps.and_towns", "{town} and {n} other towns", town=town, n=f"{n:,}")
        return I.say(lang, "reps.and_places", "{town} and {n} other towns and cities",
                     town=town, n=f"{n:,}")

    sen, sk = others(lambda w: w.get("senate") == rec.get("senate"))
    cou, ck = others(lambda w: w.get("council") == rec.get("council"))
    con, nk = others(lambda w: w.get("congress") == rec.get("congress"))
    def together(names):
        return I.say(lang, "reps.together", "{names} together", names=_names(names, lang))

    def district(n):
        return I.say(lang, "reps.district", "District {n}", n=n)
    rows = [
        (I.say(lang, "reps.own", "State House &mdash; {town}'s own district", town=town),
         f"{o['county']} {o['district']}", str(o.get("seats") or 1),
         I.say(lang, "reps.alone", "{town} voters alone", town=town) if not own_with
         else together([town] + own_with), "", [town] + own_with),
        (I.say(lang, "reps.floterial", "State House &mdash; floterial"),
         f"{f['county']} {f['district']}", str(f.get("seats") or 1),
         together([town] + flot_with),
         ("sub", I.say(lang, "reps.laid_over", "Laid over {n} districts", n=len(under))),
         [town] + flot_with),
        (I.say(lang, "reps.senate", "State Senate"), district(rec.get("senate")), "1",
         wide(len(sen), sk), "", [town] + sen),
        (I.say(lang, "reps.council", "Executive Council"), district(rec.get("council")), "1",
         wide(len(cou), ck), "", [town] + cou),
        (I.say(lang, "reps.us_house", "US House"), district(rec.get("congress")), "1",
         wide(len(con), nk), "", [town] + con),
        (I.say(lang, "reps.us_senate", "US Senate"), I.say(lang, "reps.whole", "The whole state"), "2",
         I.say(lang, "reps.every", "Every voter in New Hampshire"), "", None),
    ]
    beneath = sorted(d for c, d in under)

    def seats(n):
        return (I.say(lang, "reps.one_seat", "{n} seat", n=n) if n == 1
                else I.say(lang, "reps.n_seats", "{n} seats", n=n))

    # THE FLOTERIAL LAID OVER THE DISTRICTS BENEATH IT: each of them by its
    # name, its places and its seats, the reader's own town marked. The page
    # says "Rockingham 32 is Rockingham 6, 7 and 8 combined"; this draws it.
    base = []
    for c, d in sorted(under, key=lambda cd: (cd[0], int(cd[1]) if str(cd[1]).isdigit() else 0)):
        key = (c, d)
        places = sorted(t for t, ws in districts.items() for w in ws.values()
                        if any((x.get("county"), x.get("district")) == key
                               for x in w.get("house") or []))
        n = next((x.get("seats") or 1 for t in places for w in districts[t].values()
                  for x in w.get("house") or [] if (x.get("county"), x.get("district")) == key), 1)
        base.append((f"{c} {d}", places, n))
    order = [p for _, ps, _ in base for p in ps]
    flot = f'{f["county"]} {f["district"]}'
    flot_under = f'{f["county"]} {_names([str(d) for d in beneath], lang)}'
    band = ('<figure class="l-flot" role="group" aria-label="'
            + I.say(lang, "reps.band_label", "{flot}, laid over {under}", flot=flot, under=flot_under)
            + '"><p class="l-fband">'
            + I.say(lang, "reps.band", "<b>{flot}</b>, floterial: {seats}, elected by {names} together",
                    flot=flot, seats=seats(f.get("seats") or 1), names=_names(order, lang))
            + '</p><ol class="l-fbase">' + "".join(
                ('<li class="is-me">' if town in ps else "<li>") + f'<b>{name}</b>{_names(ps, lang)}'
                f'<span class="l-sub">{seats(n)}</span></li>' for name, ps, n in base)
            + "</ol></figure>")
    return {
        "reps_town": town,
        "reps_example": layers_diagram(
            rows, I.say(lang, "reps.heading", "Everyone who represents a voter in {town}", town=town),
            town, lang),
        "reps_band": band,
        "reps_flot": flot,
        "reps_flot_under": flot_under,
        "reps_under_n": _WORDS.get(lang, _WORD).get(len(beneath), str(len(beneath))),
    }


# ---------------------------------------------------------------------------
# AMENDING THE CONSTITUTION. Every step and every threshold here is one the
# prose on that page already states and cites to the Constitution itself; the
# diagram reorganises it rather than adding to it. The thresholds ARE the
# teaching point -- three fifths of the members in office in each chamber,
# then two thirds of those voting on the question, and no part for the
# Governor at any stage -- so they are the per-step labels rather than a
# generic mark.
#
# THE MEMBERS IN OFFICE, NOT THE SEATS. This said "240 of the 400 House
# seats" until 23 September 2026, and the record says otherwise: in March
# 2012 CACR 26 failed in the House at 237-115 and passed later that day at
# 239-114 "By Necessary Three-Fifths Vote", with 397 members on the ballots
# of both roll calls (Docket_db_2011-2012.txt; votes-2011-2012.csv). Three
# fifths of the members on the ballots explains all 104 CACR roll calls whose
# docket line names three fifths; three fifths of the seats explains 101.
# ---------------------------------------------------------------------------
FLOW_CACR = [
    ("How It Starts", [
        ("Filed as a CACR", "A Constitutional Amendment Concurrent "
         "Resolution, which may start in the House or the Senate. Statutes "
         "change by bill; the constitution does not.",
         ""),
    ]),
    ("The First Chamber", [
        ("Three fifths of the members in office", "Not three fifths of those "
         "voting: an absent member counts against it, a vacant seat does "
         "not. In 2012 the House carried CACR 26 with 239 votes, when 397 "
         "members were in office: three fifths of 397 is 238.2, so 239 was "
         "enough, where 240 would have been needed with every seat filled.",
         ("needs", "Three fifths of its members")),
    ]),
    ("The Second Chamber", [
        ("The same threshold again", "Three fifths of the other chamber's "
         "members in office, on the same terms: 240 when all 400 House seats "
         "are filled, and 15 of a full Senate of 24.",
         ("needs", "Three fifths of its members")),
    ]),
    ("The Voters", [
        ("At the next general election", "Put to the people, where it takes "
         "effect only if two thirds of those voting on the question approve "
         "it.",
         ("needs", "Two thirds of those voting on it")),
        ("The Governor has no part", "No signature and no veto, at any point "
         "in this course.", ""),
    ]),
]

# ---------------------------------------------------------------------------
# TESTIFYING, in the order a person actually does it. Same source as the
# prose beside it: the chamber rules and the General Court's own sign-in
# system. The two things worth separating are that signing in and speaking
# are different acts, and that the second chamber gives a second chance.
# ---------------------------------------------------------------------------
FLOW_TESTIFY = [
    ("Find Out", [
        ("The calendar", "Hearings are announced in the chamber's weekly "
         "calendar and on the General Court's meeting schedule. The median "
         "notice in the [[term]] term was [[notice_median]] days; some give one.",
         ""),
    ]),
    ("Sign In", [
        # BOTH CHAMBERS (17 October 2026): the Senate's guidance and its
        # calendars name its own online form, which this said nothing of.
        ("Online, for or against", "In either chamber, on its own form: "
         "your name and town, whether you are a member of the public or "
         "representing an organization, and which side. In the House you may "
         "attach written testimony.",
         ("rec", "Counted, and part of the record")),
        ("Before the day ends", "The window opens once the hearing is "
         "scheduled and, in practice, closes at midnight at the end of the "
         "day of the hearing.", ""),
    ]),
    ("At the Hearing", [
        ("Speaking is separate", "A different act from signing in, and the "
         "chambers ask for it differently: a pink card in the House, the "
         "sign-up sheet in the Senate's committee room. The sponsor speaks "
         "first, and the chair decides whether to limit everyone after.", "say"),
        ("You need not speak", "A sign-in without a word said is in the "
         "record and is counted.", ""),
    ]),
    ("Afterwards", [
        # A SEPARATE MEETING, NOT ALWAYS A LATER DAY (the fact-check of 17
        # October 2026): Senate notices often end "executive session may
        # follow", and House Rule 44(b) as amended on Convening Day 2025 lets
        # one follow a noticed hearing without further notice.
        ("Executive session", "The committee votes on its recommendation at "
         "a separate meeting, which may follow the hearing directly. Testimony "
         "is not taken at it.", ""),
        ("The other chamber", "If the bill passes, it gets a hearing in the "
         "second chamber and a second sign-in window on the same terms.",
         "say"),
    ]),
]

# HOW A RULE IS MADE. Every step and every number here was read out of RSA
# 541-A itself -- the chapter is on this disk in db/NH_RSA.psv, all 51
# sections of it -- rather than from anybody's memory of how rulemaking works.
# RSA 541-A:3 gives the sequence in the statute's own words: "Except for
# interim or emergency rules, an agency shall adopt a rule by" filing a notice
# under :6, filing the text under :10, holding a public hearing under :11,
# filing a final proposal under :12, responding to the committee under :13,
# and adopting and filing under :14. The phases below are that list, with the
# deadlines from the sections it points at.
#
# THE EXCEPTION IS IN THE FIRST FIVE WORDS and is deliberately not drawn here.
# Interim rules (:19) and emergency rules (:18) skip most of this, last 180
# days, and are a different route rather than a branch of this one; the page's
# prose carries them. Drawing them inside the sequence would misdescribe the
# sequence.
#
# TWO CORRECTIONS WORTH KEEPING, both caught by checking the draft against the
# statute a second time. There is no bare "amend" in this chapter: the actions
# are adoption, readoption, readoption with amendment, and repeal. And part I,
# article 28-a protects political subdivisions generally -- counties, cities,
# towns and school districts -- not towns alone.
#
# THREE MORE, 23 October 2026, when each number was held to its section
# (preflight's LEARN_STATUTE_CLAIMS): notice is at least 20 days before the
# hearing, not 20 (541-A:6); a board or commission may shorten the comment
# period in its notice (541-A:11, I(b)); and a rule being readopted stays in
# force past its ten years, which never bind an agency's rules of organization
# and procedure (541-A:14-a, 541-A:17). Each step that states a number now
# names its section.
FLOW_RULES = [
    ("Before Anyone Can Comment", [
        ("The statute hands it over", "A bill says the agency \"shall adopt "
         "rules\" about something, and stops. Everything it left open is "
         "settled from here on, by the agency rather than by the "
         "legislature.", ""),
        ("Notice in the register", "The agency sends the director of "
         "legislative services notice of what it means to do &mdash; adopt a "
         "rule, readopt one, readopt it with a change, or repeal it. The "
         "notice carries a fiscal impact statement and a statement that the "
         "rule lays no unfunded obligation on a county, city, town or school "
         "district. (RSA 541-A:6)", ("needs", "At least 20 days before the hearing")),
        ("The full text, not a summary", "At least one complete section of "
         "the rules as they would read, filed with the same office.", ""),
    ]),
    ("The Public's Turn", [
        ("A public hearing", "At least one, on every proposed rule. Anyone "
         "may speak, and anyone may send data, views or arguments in writing "
         "instead.", "say"),
        ("Comment stays open after it", "Written comment is taken for a "
         "further period once the hearing is over. A board or commission may "
         "set a shorter one in its notice; an agency official may not. "
         "(RSA 541-A:11, I(b))",
         ("needs", "At least 5 business days")),
    ]),
    ("The Legislature's Turn", [
        ("The final proposal", "The agency weighs the comment, settles the "
         "text, and files it. (RSA 541-A:12)",
         ("needs", "21 to 180 days after the notice")),
        ("The committee has 60 days", "The Joint Legislative Committee on "
         "Administrative Rules &mdash; JLCAR, legislators from both chambers "
         "&mdash; may approve the rule, approve it on a stated condition, or "
         "object to it. (RSA 541-A:13)", ""),
        ("Silence is approval", "If the 60 days pass with no notice of "
         "approval, conditional approval or objection, the statute deems the "
         "rule approved. A rule can take effect without anyone having voted "
         "for it. (RSA 541-A:13, II(e))", ("needs", "No vote required")),
        ("An objection is not a veto", "To actually stop a rule the "
         "committee has to sponsor a joint resolution, and that has to pass "
         "both chambers and go to the Governor like any other bill.", ""),
    ]),
    ("In Force, and Not for Ever", [
        ("Effective the next day", "Once adopted and filed the rule binds "
         "whoever it covers, exactly as a statute would.", ""),
        ("Ten years, then it lapses", "No rule is effective for longer than "
         "ten years. To keep it, the agency runs the whole course again, and "
         "the rule stays in force while it does; an agency's own rules of "
         "organization and procedure do not lapse. (RSA 541-A:17, "
         "541-A:14-a)",
         "stop"),
    ]),
]

# A TRADITIONAL TOWN MEETING AND AN SB 2 TOWN, one row per stage. Read out of
# RSA 39, 40 and 32 on this disk, thirteen extractions each checked twice, and
# then a third pass whose only job was to ask whether each row compares the
# same thing on both sides. Its answer shaped what is here as much as the
# statute did:
#
# ADOPTING THE FORM IS NOT A ROW. The traditional meeting is the default and is
# never adopted, so a row for it would set "how a town adopts SB 2" against
# "how a town rescinds it" -- two different acts dressed as one. It is in the
# prose instead.
#
# "IF THE BUDGET FAILS" IS NOT A ROW EITHER, for a better reason: nothing in
# these sections says what happens when a traditional meeting votes its budget
# down, and a row would have to invent the left-hand cell. "The budget" is the
# honest comparison -- set in the room against printed on a ballot with a
# fallback -- and the page claims nothing about the case the law is silent on.
#
# "say" marks the two cells where a member of the public speaks. Where it sits
# is the whole difference: in the traditional meeting it is the same room as
# the vote, and in an SB 2 town it is a different day from it.
CMP_TOWN = [
    ("The Warrant",
     "The selectmen, the town's elected board, sign a warrant listing each "
     "question to be decided, "
     "called an article, for a single meeting. Voters can add an article by "
     "petition, due five Tuesdays before the meeting.",
     "The same warrant, except that it sets a day for each of two sessions, "
     "and petitions are due earlier &mdash; the second Tuesday in January for "
     "a March vote."),
    ("Debate and Amendment",
     ("At the meeting itself. Each article is debated and may be amended from "
      "the floor, and the meeting may vote more or less than the sum an "
      "article asks for.", "say"),
     ("At a first session held weeks before the vote, usually called the "
      "deliberative session. Articles are debated and may be amended, and "
      "this is the only place a sum of money can be changed &mdash; but no "
      "article is passed or defeated there.", "say")),
    ("The Vote",
     "In the same room, straight after the debate. Five voters can ask in "
     "writing for a secret ballot (three in a town of 500 or fewer).",
     "At the polls, by official ballot, with absentee voting as in an "
     "election. There is no debate, and each article reads as the first "
     "session left it."),
    ("The Budget",
     "Set in the room, where it can be amended up or down. There is no "
     "default budget.",
     ("Printed on the ballot beside a second figure, the default budget. If "
      "the proposed budget fails the default takes effect, unless the "
      "governing body calls one special meeting to try a revised budget.",
      ("needs", "Voters cannot amend the default"))),
]


# THE MOTIONS A COMMITTEE MOST OFTEN RECOMMENDS, in the vote cards' words
# (VOTE_WORDS, 8 October 2026: the motion's name, the four common
# abbreviations, and a plain gloss), read from the words file the vote cards
# read, so Learn teaches the words a reader meets on a bill. Two rows are
# Learn's own: interim study's line is decision 131's ("the bill goes no
# further this term; the study committee may recommend new legislation"),
# and retaining, which no vote card names, keeps the page's words.
def _motions():
    import components
    m = components.WORDBOOK["votes"]["motions"]
    rows = [(m[k]["abbr"], m[k]["motion"], m[k]["gloss"]) for k in ("otp", "otpa", "itl")]
    rows.append((m["is"]["abbr"], m["is"]["motion"],
                 "The bill goes no further this term; the study committee may recommend "
                 "new legislation"))
    rows.append(("Retain", "Retain", "Hold the bill in the committee: first year only, "
                 "and it returns in the second"))
    return ('<div class="l-tablewrap l-stack"><table class="l-table">'
            '<caption class="sr">The motions a committee most often recommends</caption>'
            '<thead><tr><th scope="col">Written</th><th scope="col">The motion</th>'
            '<th scope="col">What it does</th></tr></thead><tbody>'
            + "".join(f'<tr><th scope="row">{a}</th><td data-l="The motion">{b}</td>'
                      f'<td data-l="What it does">{c}</td></tr>' for a, b, c in rows)
            + "</tbody></table></div>")


MOTIONS = _motions()


# THE SEATS ARE THE DISTRICT MAP'S (23 October 2026): 400 and 24 were typed
# here beside [[house_seats]] and [[senate_districts]] lower down, which
# build_civics counts from records/districts/. preflight holds the count to
# Part Second's Articles 9 and 25; the blurb in TOPICS, which is not filled,
# keeps its typed numbers and is held to the same articles.
BODY_GENERAL_COURT = """
<h2>The Largest State Legislature</h2>
<p>New Hampshire's legislature is called the <b>General Court</b>, the name the
state constitution gives it. It is made up of [[house_seats]] representatives and
[[senate_districts]] senators. It is the largest state legislature in the country: the last
redistricting drew House districts to <b>3,444 residents a seat</b>.</p>

<p>The House's [[house_seats]] is the number of seats, not the number of members. Seats fall
vacant and are filled at special elections through the term, so the working size of
the House moves.</p>
[[fig_seats]]

<h2>A Term Is Two Years</h2>
<p>The General Court sits in two-year terms beginning in odd years. A term
begins on <b>Organization Day</b>, the first Wednesday of December after the
November election, when the newly elected members are sworn in and elect the
Speaker and the Senate President. [[org_day]] Bill
numbers are unique across the whole term, so there is only ever one HB 84 in
2025&ndash;2026, and there will be another in the next term. That is why every
address on this site carries the year.
<a href="learn/legislative-year.html">NH Legislative Schedule</a> lays a term out
date by date.</p>
<p>Most bills are either passed or killed in the year they are filed. Two
things can happen to the rest, and they are not the same thing, though they
are easily confused because both leave a bill unfinished at the end of a
year.</p>
<p><b>Retaining</b> happens in the first year only. A committee keeps the bill
for more work, studies it over the fall, and reports it to the chamber in
the second year, where it is voted on like any other bill. A retained bill
survives into the second year and keeps its number.</p>
<p><b>Interim study</b> happens in the second year only, and it ends the
bill. The committee studies it over the fall and may report on it, but the
bill itself dies with the term. To come back it has to be filed again in the
next term, where it will be a new bill with a new number &mdash; so a bill
sent to interim study is not waiting to be taken up again, whatever the name
suggests.</p>
[[fig_term]]

<h2>Every Bill Gets a Public Hearing</h2>
<p>This is unusual. In most states a committee chair can decline to hear a
bill and it dies without anyone speaking on it. In New Hampshire every bill
introduced is referred to a committee and given a public hearing that anyone
may attend and speak at.</p>

<h2>Bills and Resolutions Are Not the Same Thing</h2>
<table><caption>The kinds of measure</caption><tbody>
<tr><th scope="row"><b>HB</b></th><td><b>House Bill:</b> a proposed change to New
Hampshire law. Begins in the House, must pass both chambers, goes to the
Governor.</td></tr>
<tr><th scope="row"><b>SB</b></th><td><b>Senate Bill:</b> begins in the Senate, otherwise
the same as a House Bill.</td></tr>
<tr><th scope="row"><b>HR</b> / <b>SR</b></th><td><b>House or Senate Resolution:</b> a
formal, non-binding expression of opinion, policy preference, or internal
rule. It does not go to the other chamber or the Governor and does not change
any law.</td></tr>
<tr><th scope="row"><b>HCR</b> / <b>SCR</b></th><td><b>House/Senate Concurrent
Resolution:</b> similar to an HR or SR, but voted on by both chambers.</td></tr>
<tr><th scope="row"><b>CACR</b></th><td><b>Constitutional Amendment Concurrent
Resolution:</b> a proposed change to the state constitution, requiring a
three-fifths vote in both chambers and a two-thirds majority of voters. See
<a href="learn/the-constitution.html">The Constitution</a>.</td></tr>
</tbody></table>

<h2>How Committees Work</h2>
<p>Every bill is referred to a committee chosen by subject, and the committee
holds the public hearing, votes on a recommendation in an executive
session, and writes a report explaining its reasoning. If the committee is
split on what action to recommend, there are separate reports from the
majority and the minority. The full chamber is not bound by those
recommendations, but [[follows_committee]]% of the bills it decided in the
[[term]] term went the way its committee recommended.</p>

<p>The motions a committee most often recommends are these:</p>
""" + MOTIONS + """
<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>What are legislators paid?</summary>
<p>Members are paid <b>$200 for the two-year term</b> plus mileage &mdash; one
payment, in January of the first year, less withholding. It is often quoted as
$100 a year, which is the same money divided by two. Almost none have staff.
Most have other jobs, and the session is arranged around that: the House meets
on a small number of full days, and committee work fills the rest.</p>
</details>
<details><summary>Why can&rsquo;t I find a bill that was filed last year?</summary>
<p>If it was retained, it survived into the second year and kept its number. Those show as <b>carried over</b> here, and they are the ones people most often fail to find, because they search the current year for a bill filed in the previous one.</p>
</details>
<details><summary>Which chamber does a bill start in?</summary>
<p>Which chamber a measure starts in follows from its prime sponsor: a
representative's bill begins in the House, a senator's in the Senate.</p>
</details>
</div>
""" + SHOWS.format("""
<p>In the [[term]] term, members filed <b>[[bills]] bills and resolutions</b>: [[hb]] House
bills, [[sb]] Senate bills, [[cacr]] constitutional amendments and [[resolutions]] resolutions.</p>
<p>The House is <b>[[house_seats]] seats and [[house_sitting]] sitting members</b> as
the record stands, with [[house_vacant]] vacant. The record shows that moving:
roll calls of the [[term]] term were taken with as many as [[seated_most]] members seated
and as few as [[seated_fewest]].</p>
<p>There are <b>[[house_districts]] House districts and [[senate_districts]] Senate
districts</b>. [[floterial]] of those House districts are floterial districts:
each is laid over two or more neighboring districts and elects a representative
of its own, whom their voters elect as well as their own district's &mdash; see
<a href="guides/your-representatives.html">Finding your
representatives</a>.</p>
<p><a href="committees.html">Every committee</a>, who sits on it, and what it
did on each day it met. <a href="officials.html">Every member</a>, with how
they voted.</p>""")


BODY_BILL = """
<h2>What a Bill Is</h2>
<p>A bill is a proposed change to New Hampshire law. It becomes law when both
chambers have passed it in identical form and the Governor has signed it. A
bill the Governor does not sign can still become law, either without a
signature or over a veto.</p>

<h2>The Course of a Bill</h2>
<p>It has to clear the same course twice, once in each chamber, and it can
stop at any point on it. Most do.</p>
""" + course_diagram() + """
<h2>Two Meetings Often Confused</h2>
<p>A public hearing and an executive session are different meetings, and they
are the two most often confused. A <b>public hearing</b> is where anyone may
speak, and the committee takes no decision at it. An <b>executive session</b>
is where the committee votes on what to recommend, usually days later and
usually covering several bills at once. A committee cannot end a bill there:
the rules of both chambers require it to report every bill it is given, with
no recommendation if it cannot agree on one, and the full chamber decides.
See
<a href="guides/testifying.html">How public hearings work</a> for what happens
at each, and
<a href="learn/governor-and-council.html">The Governor and the Executive
Council</a> for the last stage.</p>

<h2>How Most Bills End</h2>
<p>Of the [[bills]] bills and resolutions filed in the [[term]] term,
<b>[[killed]] were killed</b> on a motion of Inexpedient to Legislate, written <b>ITL</b>, and
<b>[[signed]] were signed into law</b>. Among the rest, [[study]] were sent
for interim study (the committee studies the subject after the session, and
the bill goes no further), [[tabled]] died on the table (set aside by a vote
and never taken up again), and [[session_end]] died when the session ended
without a final vote. Dying is the ordinary outcome, not a
failure of the bill or its sponsor.</p>
[[fig_ends]]

<h2>How a Chamber Votes, and What Is Recorded</h2>
<p>A chamber can put a question three ways. A <b>voice vote</b> records only
which side sounded louder. A <b>division</b> records the count but not who
voted which way. A <b>roll call</b> records every member by name. In the House
one is taken when a member moves for it and the required number of other
members second the motion. A vote to override a veto is always a roll call,
because the constitution requires one.</p>
""" + WAYS_OF_VOTING + """
<p>Across the [[all_bills]] bills in this record, <b>[[all_rollcall]] have at
least one recorded roll call and [[all_no_rollcall]] have none</b>. Of those,
[[pre_rollcall_bills]] are from before [[rollcall_first_year]], where this
record's roll calls begin: roll calls were taken then too, and printed in the
journals, but this site does not hold them. For most of the rest there is no
answer to "how did my representative vote", because the bill was decided by
voice vote or division and no record of names was made.</p>
[[fig_rollcalls]]

<h2>Two Bills, Followed All the Way</h2>
<p>Both went through both chambers, and on each the closest roll call in the
House did not split cleanly along party lines: a majority of Republicans voted
one way and a majority of Democrats the other, but a substantial minority of
each party voted against its own side.</p>

<h3>HB 1002 (2024): What a Public Record May Cost</h3>
<p>A town or agency answering a
right-to-know request may charge for the copies. The question was whether it
may also charge for the staff time spent finding and reviewing the records.
Supporters said small towns without full-time staff absorb real cost for
requests that can run to thousands of pages. Opponents said a fee that tracks
staff time can be set high enough to price an ordinary resident out of
oversight.</p>
<p>It shows how little a first vote settles. The House Judiciary Committee
heard it on January 17, 2024 and split 12&ndash;8 for passing it with an
amendment, and on February 1 the House agreed, <b>193 to 179</b>: 63
Republicans for and 125 against, 128 Democrats for and 53 against. A week
later the House voted 195 to 183 to reopen that vote, and sent the bill back
to the committee, which now split 11&ndash;9 for referring it to interim
study, a recommendation that would have ended it for the term. The House
refused, 105 to 266, adopted an amendment offered from the floor rather than
by the committee, 345 to 24, and passed the bill 268 to 106. The Senate passed
it on a voice vote, and Governor Sununu signed it into law on June 14, 2024.
Five of its proceedings are on video: the House hearing, both House executive
sessions, the work session between them, and the Senate hearing.</p>

<h3>HB 1215 (2024): A Bill That Went to a Committee of Conference</h3>
<p>The longer road at the end of the course. It went to a Special Committee on
Housing, then to a second chamber that changed it. On the motion to accept
that change the House divided <b>172 to 180</b>, and the bill went to a
<b>committee of conference</b>. It dealt with how long an approved development
keeps the rules it was approved under, and where a building code dispute may
be appealed: local control of what gets built against the time and cost of
getting anything built. Six of its proceedings are on video, the conference
among them. The House then rejected the conference report <b>102 to 261</b>,
and the bill did not become law.</p>
<p class="l-note">Both are offered as examples of the process and not as
settled questions. The site takes no position on either. The arguments above
are summarized from what was said for and against, and the recordings are
there so you can check whether that summary is fair.</p>

<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>Why can a measure win a majority and still fail?</summary>
<p>Overriding a veto takes two thirds of each chamber, by roll call, under
Part Second, Article 44 of the state constitution. The article says two thirds
"of that house", and the House counts it among the members voting rather than
against its whole membership: in August 2026 it overrode a veto 231 to 88
when 384 members were in office. Amending the constitution takes three fifths
of the members of each chamber, and then two thirds of those voting on the
question at the election, under Part Second, Article 100. The chambers count
that three fifths against every member in office rather than against those
present &mdash; 240 when all 400 House seats are filled &mdash; so a measure
can win a clear majority of those voting and fail anyway.</p>
""" + THRESHOLDS + """
</details>
<details><summary>What is the consent calendar?</summary>
<p>A committee decides in executive session whether to send a bill to the
consent calendar, and in both chambers that decision must be unanimous. It is
a separate vote from the committee's recommendation: a recommendation carried
on a divided vote can still go to the consent calendar, and this
site&rsquo;s record holds thousands of House reports marked that way, among
them reports carried 15&ndash;3. The calendar is then decided in a single
vote, without floor debate. What that vote adopts is the committee's
recommendation on each bill, which for some of them is to kill it. A bill can
be taken off first, and one that comes off is debated and voted on by itself
at the end of the regular calendar. Taking one off has needed ten members in
the House since January 2023, and two senators in the Senate since April
2026; before that, one member's request was enough in either chamber.</p>
</details>
<details><summary>When will the House vote on a bill?</summary>
<p><b>The House does not schedule its votes to a time.</b> Its calendar lists
the bills for the day grouped by the committee that reported them, or on some
days, such as a veto day, in order by number, and that is the order they are
taken up in unless the House votes to take one up at a set point in the day,
which is called making it a special order. In practice a session day runs like
this:</p>
<ol>
<li><b>The consent calendar</b>, first. The bills taken off it are announced,
and the rest are decided in one vote.</li>
<li><b>The regular calendar</b>, committee by committee, sometimes broken by a
lunch recess, with the rest of it after lunch.</li>
<li><b>The bills taken off the consent calendar</b>, each debated and voted on
by itself.</li>
<li><b>Adjournment</b>, followed by <b>unanimous consent speeches</b>: any
member may speak on something that matters to them, a constituent's story or
a holiday, in remarks meant to be non-partisan. No vote is usually taken,
unless a member objects to a speaker continuing; then the House votes on
whether the member may go on, as it did a few times in 2026.</li>
</ol>
<p>A motion to reprimand or censure a member can be brought up at any point in
the day. So a vote you are waiting for has no set time: the calendar tells you
only where in the day's order its bill falls.</p>
</details>
</div>
""" + SHOWS.format("""
<p>Follow the two worked examples through the record:
<a href="bill/2024/hb1002.html">HB 1002 (2024)</a> and
<a href="bill/2024/hb1215.html">HB 1215 (2024)</a>, with each hearing, each
committee vote, each floor vote, and the recording of each.</p>
<p><b>Killed:</b>
<a href="bill/2025/hb66.html">HB 66</a>, on what counts as material a public
body must disclose under the right-to-know law. Two roll calls before it
died.</p>
<p><b>Signed into law:</b>
<a href="bill/2025/hb2.html">HB 2</a>, the budget trailer bill, which carries
the statutory changes the state budget needs, with [[hb2_rollcalls]] recorded
votes. The letters after its number say it has a fiscal note (FN), an
appropriation (A) and a local fiscal impact (LOCAL).</p>
<p><b>Vetoed, and the override failed:</b>
<a href="bill/2026/hb349.html">HB 349</a>, on whether optometrists may perform
ophthalmic laser procedures. It passed both chambers and was vetoed, and the
override fell at 145 to 206 where two thirds of those voting was needed.</p>
<p><b>Vetoed, and overridden anyway:</b>
<a href="bill/2026/hb2026.html">HB 2026</a>, on the ten-year transportation
plan.</p>
<p><b>Carried over</b> into the second year:
<a href="bill/2026/hb649.html">HB 649</a>, on the maintenance obligations of
motor vehicle operators, which passed in the second year and became law.</p>
<p>Of the [[law]] bills that became law in the [[term]] term,
[[law_no_rollcall]] did so without a roll call on the floor of either
chamber.</p>
<p>Of the [[narrated]] bills with a narrative in the [[term]] term, <b>[[both_chambers]]
reached both chambers</b> and <b>[[conference]] went to a committee of
conference</b>. [[law]] became law: [[signed]] signed, [[unsigned]] without a
signature, and [[overridden]] over a veto.</p>""")


# THE LEGISLATURE'S YEAR (the person, 17 October 2026: "a diagram or page
# explaining the schedule of the legislature with the various deadlines like
# crossover and interim study season, which links to the homepage status").
# Answer first: where the term stands on the day the page was built, then the
# shape any term has, then this term's dates, then what each deadline means.
# The three figures are legislative_year.py's, which holds every date with the
# calendar it was read from; this is the prose around them, and it states no
# date of its own, so that every date on the page sits beside its source.
# THE SCHEDULE, SIMPLIFIED (the person, 22 October 2026: "the page should be
# significantly simplified and streamlined for easier readability"). Where
# the legislature is and the next eight dates first; the usual year in two
# bars; the full schedule folded by season. The table of what each deadline
# means is the Glossary's now ("Second committee" and "Veto day" were added
# to it from the table's words), and In the Record is three links.
BODY_YEAR = """
<h2>Right Now</h2>
[[year_now]]

<h2>The Term at a Glance</h2>
<p>The legislature is elected for two years, and each year is one session:
it opens in January, runs through the deadlines below and ends by June. A new
term begins on <b>Organization Day</b>, the first Wednesday of December after
the November election.</p>
[[year_shape]]

<h2 id="s-dates">The Full Schedule</h2>
[[year_dates]]
<p>What the deadlines mean -- crossover, interim study, a committee of
conference -- is in <a href="learn/glossary.html">the Glossary</a>.</p>
""" + SHOWS.format("""
<p><a href="calendar.html">The Calendar</a> for this week's hearings and
sessions; the days each chamber sat, <a href="session/house.html">the
House's</a> and <a href="session/senate.html">the Senate's</a>; and how a bill
moves, in <a href="learn/how-a-bill-becomes-law.html">How a Bill Becomes
Law</a>.</p>""")


BODY_GOVERNOR = """
<h2>The Governor</h2>
<p>The New Hampshire governor serves as the state's head of government and
supreme executive magistrate, responsible for enforcing state laws, proposing
the biennial state budget, and commanding the New Hampshire National
Guard.</p>

<p>The Governor is elected for two years, at the same election as the whole
legislature. When a bill has passed both chambers the Governor may sign it,
veto it, or do nothing; Part Second, Article 44 of the state constitution sets
out what follows each.</p>
""" + GOVERNOR_ROUTES + """

<h2>A Veto Is Not Always the End</h2>
<p>The legislature can override a veto, but it takes two thirds of each
chamber, by roll call, starting with the chamber the bill came from. The
constitution says two thirds "of that house", and the House counts that among
the members voting. That is a high bar and most attempts fail.</p>
<p>Across the [[terms]] terms on this site there are <b>[[vetoed]] vetoed bills</b>.
In <b>[[veto_failed]]</b> the veto stood. In <b>[[veto_overridden]]</b> it was
overridden and the bill became law over the Governor's objection.[[veto_pending]]</p>
[[fig_vetoes]]

<h2>The Executive Council</h2>
<p>Five councilors, each elected by district, meeting with the Governor.
Almost no state has anything like it, and not many people can describe what it
does.</p>
<p>Its approval is required for a great deal of what the executive branch
does: state contracts above a threshold, the appointment of commissioners and
judges, and pardons. A commissioner nominated by the Governor takes office
only when the Council confirms them, and a Governor who has the legislature
and not the Council cannot simply proceed.</p>
""" + chain("How a commissioner or a judge is appointed", [
    ("The Governor nominates", "a commissioner, or a judge."),
    ("The Executive Council confirms", ""),
    ("The nominee takes office", "only when the Council confirms them.")]) + """
<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>What happens if the Governor does nothing with a bill?</summary>
<p>It becomes law without a signature after five days, Sundays excepted &mdash;
unless the legislature's adjournment prevents the Governor from returning it, and
then it does not become law at all (Part Second, Article 44).</p>
</details>
<details><summary>Where can I read why the Governor vetoed a bill?</summary>
<p>When the Governor vetoes a bill, the reasons are set out in a message
entered in the journal of the chamber the bill came from. Those messages are printed
in the House and Senate calendars, and this site carries [[veto_messages]] of the
[[vetoed]].</p>
</details>
<details><summary>Why is the Executive Council debated?</summary>
<p>The Council is genuinely debated. Supporters say it is a check on
executive power that no single elected officer should be without. Critics say
it gives five people a veto over routine administration and slows work that
has already been authorized. Both are arguments about the same fact.</p>
</details>
</div>
"""

BODY_GOVERNOR_HOLDS = """This site indexes the legislature, and it holds
almost nothing about the Executive Council: no agendas, no contract votes, no
nominations. What it does hold is the legislative half &mdash; the vetoes and
the override votes, on each bill's own page: <a href="bill/2026/hb349.html">HB
349</a>, whose veto stood, and <a href="bill/2026/hb2026.html">HB 2026</a>,
whose veto was overridden. For the Council's own record, go to the
Council."""


BODY_COURTS = """
<h2>Three Courts</h2>
<p>New Hampshire has three courts.</p>
<ol class="l-courts" aria-label="The three courts">
<li>The <b>Supreme Court</b> hears appeals and is the final word on what a state
law means.</li>
<li>The <b>Superior Court</b> holds jury trials and hears the more serious civil
and criminal cases.</li>
<li>The <b>Circuit Court</b> handles the highest volume of cases each year,
including misdemeanors, small claims, probate, and family cases such as
divorce and custody.</li>
</ol>

<h2>How a Judge Gets the Job</h2>
""" + chain("How a judge gets the job", [
    ("The Governor nominates", "No judicial election, at any level."),
    ("The Executive Council confirms", "The same route as a commissioner."),
    ("The judge serves", "Until the age of seventy at most: Part Second, Article 78.")]) + """
<p>The Governor nominates and the Executive Council confirms &mdash; the same
route as a commissioner, which is the clearest illustration of what the
Council is for. There is no judicial election in New Hampshire at any level.
No one may serve as a judge after the age of seventy, which is set by the
constitution itself: Part Second, Article 78. Raising it to seventy-five has
been tried. A 2023 amendment to do so passed both chambers and went to the
voters in November 2024, where 65.6% voted yes, short of the two thirds an
amendment needs; and a 2026 proposal to make the same change, which
failed in the House, still described the limit as seventy.</p>

<h2>Where the Courts and the Legislature Meet</h2>
<p>The legislature writes statutes, and the courts decide what they mean when
that is disputed, and whether they are
permitted by the state or federal constitution. A decision striking down or
narrowing a statute is sometimes followed by bills amending the language
around the new standard, and those bills are in the record here like any
other.</p>
"""

BODY_COURTS_HOLDS = """This site holds no court records: no opinions, no
dockets, no filings. Judicial nominations go to the Executive Council rather
than the legislature, so they are not here either. This page is here because
you cannot follow a statute's life without knowing who else acts on it, and
it links out for anything more."""


BODY_CONSTITUTION = """
<h2>In Two Parts</h2>
<p>New Hampshire's constitution took effect in 1784 and is among the oldest
still in force anywhere. It is in two parts. <b>Part First</b> is the Bill of
Rights &mdash; forty-four articles on what the state may not do. <b>Part
Second</b> is the Form of Government: the House, the Senate, the Governor, the
Council, the courts, and how each is chosen. The whole text, article by
article, is on <a href="/laws#constitution">the Laws page</a>.</p>

<h2>It Is Not Amended the Way Statutes Are</h2>
<p>A statute changes when a bill passes both chambers and the Governor signs
it. The constitution does not. A change starts as a <b>CACR</b> &mdash; a
Constitutional Amendment Concurrent Resolution &mdash; and it has to clear
three thresholds, none of which involves the Governor.</p>
""" + flow_diagram(FLOW_CACR, "How the constitution is amended",
                 key=THRESHOLD_KEY) + """

<h2>Why Almost None Get Through</h2>
<p>[[cacr_hurdle]]</p>
""" + SHOWS.format("""
<p>[[cacr_lead]]</p>
[[cacr_table]]
<p>They sit in <a href="bills.html">the bill list</a> beside ordinary bills.
A CACR that shows "Passed one chamber" has a much longer way to go than a bill
with the same words beside it.</p>""")


BODY_AGENCIES = """
<h2>Where Statutes Get Applied</h2>
<p>The legislature passes a law. An agency carries it out. Health and Human
Services, Transportation, Environmental Services, Education, Safety, Revenue
Administration and the rest are where statutes get applied around New
Hampshire.</p>
""" + chain("From statute to rule", [
    ("The legislature passes a law", "Departments may request legislation, but the bill "
     "itself has to be filed by a legislator."),
    ("An agency carries it out", "Its commissioner is nominated by the Governor and "
     "confirmed by the Executive Council, for a fixed term."),
    ("The agency decides the detail", "It cannot give itself powers the statute does not "
     "grant. It writes administrative rules."),
    ("A legislative committee reviews it", "The Joint Legislative Committee on "
     "Administrative Rules (JLCAR) reviews every rule except an emergency rule, before "
     "it is adopted: approve, approve on a condition, or object. No action within 60 days and the rule is "
     "treated as approved.")], wide_=True) + """

<h2>How a Commissioner Gets the Job</h2>
<p>Nominated by the Governor, confirmed by the Executive Council. That is the
same route as a judge, and it is the most concrete answer to
<a href="learn/governor-and-council.html">what the Council does</a>. A
commissioner serves a fixed term.</p>

<h2>What an Agency Cannot Do</h2>
<p>It cannot give itself powers the statute does not grant. What it can do is
decide the detail, and it does that by writing
<a href="learn/administrative-rules.html">administrative rules</a>. Every
rule except an emergency rule goes to JLCAR before it is adopted. JLCAR, the
Joint Legislative Committee on Administrative Rules, is a committee of
legislators from both chambers, and it may approve the rule, approve it on a
condition, or object.</p>
<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>Why do department staff speak at hearings?</summary>
<p>A department is usually among the first bodies asked what a bill would
actually do, and often the body that would have to do it, so agency staff
appear at hearings regularly. An agency may support a bill, oppose it, or
appear as neutral and simply explain the effect.</p>
<p>If you have watched a hearing on this site and heard a department's staff
explain how a bill would be administered, or ask for a technical change, that
is what you were listening to. Departments may request legislation, but the
bill itself has to be filed by a legislator.</p>
</details>
<details><summary>Can a commissioner be reappointed?</summary>
<p>Yes. A commissioner serves a fixed term and can be reappointed the same way: nominated by the Governor, confirmed by the Executive Council.</p>
</details>
<details><summary>What happens if JLCAR objects to a rule?</summary>
<p>For a rule made in the ordinary course, an objection does not by itself stop the rule, though the committee can hold it back for a time while it asks the legislature to block it by joint resolution; and if the committee takes no action within 60 days, the rule is treated as approved.</p>
</details>
</div>
""" + SHOWS.format("""
<p>Where a hearing was recorded &mdash; [[hearing_video_bills]]
bills[[hearing_video_since]] &mdash; the bill's Hearings tab links the
recording, opened where the bill was taken up when that moment has been
found. <a href="committees.html">Committee pages</a> list
every day a committee met and what it heard.</p>""")


BODY_RULES = """
<h2>What a Rule Is</h2>
<p>An administrative rule is a requirement a state agency writes to carry out a
statute. Rules are made under RSA 541-A, the Administrative Procedure Act.</p>

<p>A statute rarely says how. The detail &mdash; the form, the threshold, the
deadline, the license conditions &mdash; is left to the rule, and an
<a href="learn/state-agencies.html">agency</a> writes it, not the legislature.
A bill often says so in as many words: "the department shall adopt rules under
RSA 541-A". [[rules_delegated]] of the [[bills]] bills and resolutions filed in the
[[term]] term carry a sentence of that kind.</p>

<h2>How a Rule Is Made</h2>
<p>RSA 541-A:3 sets out the course, and the deadlines below come from the
sections it points at.</p>
""" + flow_diagram(FLOW_RULES, "How a rule is made", level_names=True) + """

<h2>How the Legislature Reviews a Rule</h2>
<p>The <b>Joint Legislative Committee on Administrative Rules</b>, or JLCAR,
has members from both chambers and meets at least once a month. The final
proposal goes to it before the rule can be adopted. It may approve the rule,
approve it on condition of a stated change, or object to it.</p>

<h2>After the Bill Becomes Law</h2>
<p>The law is often not the whole answer. What the statute left open is settled
in the rule, and the rule's hearing is announced in the rulemaking register,
not in a chamber calendar.</p>
<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>Where do I find a proposed rule?</summary>
<p>The whole of it happens in the rulemaking register &mdash; a free bulletin the legislature's own staff publish online each week &mdash; and not in a chamber calendar, which is why a rulemaking can run its full course without ever appearing where people look for legislation.</p>
</details>
<details><summary>Can a rule take effect without all those steps?</summary>
<p>Two routes skip most of that. An <b>emergency rule</b> (RSA 541-A:18) takes
effect at once where the agency finds an imminent peril to public health or
safety, or a risk of substantial fiscal harm to the state or its citizens,
with only whatever notice the agency finds practicable; an
<b>interim rule</b> (RSA 541-A:19) is a fast track for matching a new statute,
a court decision or a federal requirement. Neither lasts more than 180 days,
so both end in the ordinary course above or they end altogether.</p>
</details>
<details><summary>What can JLCAR object to, and does an objection stop the rule?</summary>
<p>The grounds for an objection are set out at RSA 541-A:13, IV, and include a rule beyond the agency's authority and one contrary to the intent of the legislature.</p>
<p>An objection does not by itself stop the rule. To block it the committee sponsors a joint resolution, which has to pass both chambers and go to the Governor <a href="learn/how-a-bill-becomes-law.html">like any other legislation</a>.</p>
</details>
</div>
"""

BODY_RULES_HOLDS = """This site does not carry administrative rules
themselves, and does not track a rulemaking after a bill becomes law. The
rulemaking register and JLCAR's own dockets are where that continues, linked
below."""


BODY_LOCAL = """
<h2>Three Kinds of Local Government</h2>
<p>Local government in New Hampshire is the city or town, the school district
and the county. There are [[municipalities]] cities and towns. A city has an
elected council or board of aldermen. Most towns have no council: the
legislative body is the town meeting, and the registered voters adopt the
budget themselves.</p>

<h2>Two Ways to Hold a Town Meeting</h2>
<p>A town settles its business once a year, and there are two ways it can do
it. At a <b>traditional town meeting</b> the voters debate each question and
decide it in the same room on the same day. A town, school district or village
district may instead adopt the <b>official ballot referendum form of
meeting</b> (RSA 40:13), called <b>SB 2</b> after
<a href="bill/1995/sb2.html">the 1995 bill</a> that created it. Under SB 2 the
debate and the vote happen weeks apart, and the vote is cast at the polls.</p>
""" + compare_diagram(CMP_TOWN, "A traditional town meeting and an SB 2 town, "
                      "compared", "Traditional Town Meeting", "SB 2 Town") + """

<h2>The Traditional Town Meeting</h2>
<p><b>Warrant:</b> the notice of the meeting and the list of business to be
decided at it. Nothing done at a town meeting except electing its officers is
valid unless the subject was stated in the warrant (RSA 39:2). A <b>petitioned
article</b> is one the selectmen must put on the warrant on the written
application of 25 registered voters, or of 2 percent of the town's registered
voters, whichever is fewer, and never fewer than 10 (RSA 39:3). The articles
are debated and amended from the floor, and the budget is decided in the
room: where an article asks
for a sum of money the meeting may vote more or less than it asks (RSA 39:2).</p>

<h2>How SB 2 Towns Vote</h2>
<p>The meeting is held in two sessions. The first is usually called the
<b>deliberative session</b>, though the statute calls it only the first
session, and it handles everything except the ballot. Each article is
explained and debated and may be amended, and the session votes on those
amendments &mdash; so a great deal is decided there, even though no article
is passed or defeated.</p>
<p>At the second session every article goes on the official ballot, worded as
the first session left it, and is voted on at the polls with absentee voting
as in an election. It passes by a simple majority unless a law, contract or
written agreement requires two thirds, and nothing decided at the second
session can be reconsidered (RSA 40:13, XIII and XV).</p>

<h2>The Default Budget</h2>
<p><b>Default budget:</b> the figure an SB 2 town or district falls back on if
the operating budget on the ballot is defeated. It starts from last year's
operating budget, is raised or lowered for debt service, contracts and other
obligations already incurred or required by law, and is reduced by one-time
spending and by the cost of positions the proposed budget eliminates (RSA
40:13, IX). If the proposed budget fails the default takes effect, unless the
governing body instead calls one special meeting to try a revised budget.</p>
<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>Can a town meeting spend more than the budget committee recommends?</summary>
<p>In a town under the municipal budget law, the meeting may not raise the total more than 10 percent above what the budget committee recommends, with some exceptions (RSA 32:18).</p>
</details>
<details><summary>Can the deliberative session change an article however it likes?</summary>
<p>No. An amendment may not remove an article's subject, though changing a sum of money does not count as doing so, and an article whose wording is set by law cannot be amended at all (RSA 40:13, IV).</p>
</details>
<details><summary>How does a town adopt SB 2, or go back?</summary>
<p>A town or district adopts SB 2 by three fifths of those voting on the
question, after a public hearing, and can return to a traditional meeting by
the same three-fifths vote (RSA 40:14).</p>
</details>
<details><summary>Can voters change the default budget?</summary>
<p>The voters cannot amend the default budget. The governing body &mdash; the
selectmen or the school board &mdash; can adjust it, on relevant new
information and only until the ballots are printed (RSA 40:13, XI(b)). That is
why the argument at a deliberative session is so often about the default
rather than the proposed budget.</p>
</details>
</div>
"""

BODY_LOCAL_HOLDS = """This site covers the state legislature only. It holds no
town meeting warrants, no local budgets and no municipal votes. This page is
here because bills about towns are in the record constantly and the words in
them assume you already know all of this."""

# ---------------------------------------------------------------------------
# COUNTY AND MUNICIPAL GOVERNMENT, asked for by the person on 17 September:
# "pages to explain the various elected officials at the county and municipal
# level and their roles, how some towns have a mayor and city council and
# other towns have a select board".
#
# They are two pages rather than one because the two levels answer different
# questions and share almost nothing: a county is run by a body nobody is
# elected to, and a town or city is run by whichever of five or six forms its
# voters adopted. Both sit after "local-government", which already holds town
# meeting, SB 2 and the default budget, and neither repeats it -- each links
# it instead.
#
# The citations were first read on gc.nh.gov/rsa on 17 September 2026, and
# that reading checked that each section existed rather than that it said
# what the sentence beside it said. On 23 September every citation in both
# bodies was re-read clause by clause against the General Court's own RSA
# table (db/NH_RSA.psv), and ten sentences were corrected: the budget deadline
# of an optional-fiscal-year county (24:14 II), the Supreme Court's exception
# from bailiff security (104:5 III), recording cited to 478:1 rather than
# 477:3-a and 478:4, the register of probate (490-F:13, 548:5, and 2026 CACR
# 13), RSA 611 called "the coroners chapter" (it was the medical examiners'),
# the manager-form petition (37:12, not 37:11), a village district's manager
# (37:14), the treasurer and highway agents who may be appointed (669:15),
# a charter amendment put "by the same route" as a new charter (49-B:5, 49-B:6)
# and a charter repeal open to "a municipality" where 49-B:12 says any town.
# Where a sentence could not be tied to a section it carries no citation
# rather than a guessed one. preflight holds each corrected claim to its
# section, in both directions.
# ---------------------------------------------------------------------------

# THE REGISTER OF PROBATE PARAGRAPH ENDS ON A VOTE STILL TO COME. CACR 13
# (2026) would strike the office out of the constitution, and it is on the
# ballot of the general election of 3 November 2026; the paragraph below that
# begins "Register of probate:" says so in the future tense, and the "Five
# county officers" sentence above it counts the register among the offices on
# the ballot. CACR 13's own page will say how the vote went once the docket
# records it, as it recorded the referendums of 1992 and 1998.
#
# THE PARAGRAPH'S LAST SENTENCE TELLS THE VOTE BY THE DAY (17 October 2026):
# [[probate_vote]], which build_civics.probate_vote writes from the build's
# day and CACR 13's row of corrections/ballot_results.json -- the election
# ahead, then "the vote was on November 3, 2026" with the count not yet on
# the site, then the count once a person has entered it. So the page reads
# true on 4 November without a hand on it, and the reminder below waits for
# the result rather than the date.
#
# Once the count is in, reread the paragraph -- if two thirds said yes, its
# "still elected" and the county officers sentence are no longer true -- and
# set this to the date of that review, as "2026-11-20". preflight's reminder
# (_probate_after_the_vote) fails from the day the count is entered, or from
# 2 December 2026 if it never is, until this holds a date on or after it.
REGISTER_OF_PROBATE_REVIEWED = ""

BODY_COUNTY = """
<h2>Ten Counties</h2>
<p>New Hampshire has ten counties: Belknap, Carroll, Cheshire, Coos, Grafton,
Hillsborough, Merrimack, Rockingham, Strafford and Sullivan. Each is a unit of
government with its own budget, its own elected officers and its own line on
your property tax bill. Title II of the Revised Statutes is the law that
governs them.</p>

<p>A county has no council and no mayor. Its legislative body is a group of
people you already elected to something else.</p>
""" + COUNTY_BODIES + """

<h2>The County Convention, Which Is the County Delegation</h2>
<p><b>County convention:</b> the legislative body of a county. It consists of
the state representatives of the representative districts of the county
(RSA 24:1). Nobody is elected to it separately. A representative elected to
the House from a district in Grafton County is, by that fact alone, a member
of the Grafton County convention.</p>

<div class="yt" data-yt="county" hidden></div>

<p>A House district carries its county in its name &mdash; Rockingham 13,
Hillsborough 44 &mdash; and that name is what places its members. In the
present map every House district, floterial districts included, lies within a
single county, so each representative sits in exactly one delegation.</p>

<p>At its first regular meeting the convention elects a chairperson, a
vice-chairperson, a clerk and an <b>executive committee</b>, whose party
balance has to reflect the balance of the convention itself (RSA 24:2). The
first meeting is held during the week of the second Wednesday of December in
each even-numbered year, after the general election (RSA 24:9-a). Later
meetings are called by the chairperson or by a majority of the members, and
the chairperson has to call one when the county commissioners ask in writing
(RSA 24:9-c). Notice of the time, place and purpose goes to every member and
to a newspaper circulating in the county at least 7 days beforehand
(RSA 24:9-d).</p>

<h2>How the County Budget Is Decided</h2>
<p>The budget is the delegation's main business, and RSA 24 sets out the
sequence. Two bodies act, in turn, and the order is what decides who can
change what.</p>

""" + county_budget("""<p><b>The commissioners propose.</b> Before December 1 each year they deliver
their recommended budget to every member of the convention, to the chair of
the selectmen of every town and the mayor of every city in the county, and to
the Secretary of State (RSA 24:21-a, I). A county on an optional fiscal year
does this before June 1 instead (RSA 24:21-a, II).</p>

<p><b>There is a public hearing.</b> It is held not earlier than 5 nor later
than 20 days after that statement is mailed, and the clerk of the convention
publishes notice of it, with a summary of the budget, in a newspaper at least
3 days ahead (RSA 24:23).</p>

<p><b>The executive committee examines it.</b> The convention may designate
the executive committee to sit as a subcommittee on the budget and report
recommendations back to the full convention (RSA 24:2). That is where a county
budget is gone through line by line, but the committee recommends: it does not
appropriate.</p>

<p><b>The delegation votes.</b> Raising county taxes and making appropriations
are the convention's powers, not the commissioners' (RSA 24:13), so the figure
the convention adopts may be above or below the one the commissioners
recommended. The vote cannot be taken until 28 days have passed since the
recommendations were mailed (RSA 24:21-a, III). Appropriations are itemized in
detail and the clerk keeps the record of them (RSA 24:14, I).</p>

<p><b>Missing the deadline has a consequence.</b> The convention must adopt
the budget within 90 days after the fiscal year begins if the county runs on a
calendar year, or by September 1 if it is on an optional fiscal year. A
convention that has not adopted one by then does not get an extension. The
budget as recommended by the commissioners takes effect as the county budget
(RSA 24:14, II).</p>""") + """

<h2>What Happens After the Budget Is Adopted</h2>
<p>The delegation is still the body that has to be asked. Commissioners and
county officers may not pay out money that has not been appropriated, or
exceed what was appropriated (RSA 24:15).</p>

<p>These are the same people this site already holds pages for. A state
representative has a second job most residents never see: the member who voted
on a bill in Concord in the morning may spend the evening setting a county
budget that arrives on the same property tax bill as the town's.</p>

<h2>The County Commissioners</h2>
<p><b>County commissioners:</b> the county's executive, and the body that
runs it day to day. RSA 662:4 divides each of the ten counties into three
county commissioner districts, and one commissioner is chosen from each, so
every county has three. In most counties each is elected by the voters of that
district alone; in Carroll and Sullivan, each is elected from a district but by
the voters of the whole county (RSA 653:1, VI).</p>

<p>They choose a chairman and a clerk from among themselves (RSA 28:1). They
have the custody and care of all property belonging to the county (RSA 28:4),
run its departments from day to day, and prepare the budget the convention
votes on. The county treasurer pays money out only on their orders
(RSA 29:1).</p>

<h2>The Officers on the County Part of Your Ballot</h2>
<p>Five county officers are elected by the voters of the county at the state
general election: a <b>sheriff</b>, a <b>county attorney</b>, a <b>county
treasurer</b>, a <b>register of deeds</b> and a <b>register of probate</b>.
The term is two years, except in Rockingham County, which moved to four-year
terms in 2022, and Coos County, which did so in 2024 (RSA 653:1, V).</p>

<p><b>Sheriff:</b> the sheriff and the sheriff's deputies serve and execute
writs and other process directed to the department, and the department's
bailiffs provide security in every state court except the Supreme Court
(RSA 104:5). Sheriffs and
deputies have the same authority throughout the state as in their own county
to serve process, investigate crimes and apprehend, and may enforce civil
orders issued by any court (RSA 104:6).</p>

<p><b>County attorney:</b> the county's prosecutor. The office acts under the
direction of the Attorney General, performs the Attorney General's duties for
the county in the Attorney General's absence, and prosecutes or defends suits
in which the county has an interest (RSA 7:34).</p>

<p><b>County treasurer:</b> has custody of all money belonging to the county,
pays it out only on the commissioners' orders, keeps the account of what comes
in and goes out, and reports at the end of the fiscal year (RSA 29:1).</p>

<p><b>Register of deeds:</b> keeps the registry of deeds, which is the
county's record of who owns which land. Deeds, mortgages and the other
documents that affect title to land are recorded there, and a deed that has
not been recorded does not hold against a later buyer who paid for the land in
good faith (RSA 477:3-a, 478:4). The register keeps the records safe in the
office the county provides (RSA 478:1).</p>

<h2>What the County Pays For, and Where the Money Comes From</h2>
<p>Two things dominate a county budget. A county may provide, keep and
maintain facilities for the confinement of prisoners, administered by a county
department of corrections (RSA 30-B:1); that is the jail. And long-term care is
a county liability: counties reimburse the state for nursing home and other
long-term care Medicaid spending on the residents each county is answerable
for, to the extent of the whole non-federal share of it, subject to a limit on
how fast that bill may rise (RSA 167:18-a). Counties also run nursing homes of
their own. No chapter of Title II creates them, but the statutes treat them as
a given: the commissioners of each county appoint an administrator for the
county nursing home (RSA 28:11). The registry of deeds, the
sheriff's department and the county attorney's office are on the county payroll
as well.</p>

<p>No county collects a tax directly. The county treasurer issues a warrant to
the selectmen of each town in the county, requiring them to assess and collect
that town's share of the county tax and pay it over (RSA 29:11). The town
raises it in the property tax. That is why a tax bill carries a county line
beside the town, school and state education lines, and why a budget the
delegation adopts turns up on a tax bill months later.</p>

<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>Why is it called both a convention and a delegation?</summary>
<p>You will meet it under two names. The statutes say convention; legislators,
county staff and county budget papers usually say <b>delegation</b>. They are
the same body, and the statute itself uses both words in one sentence:
RSA 24:9-a gives the chair of the county delegation the job of setting the
time and place of the first meeting of the county convention.</p>
</details>
<details><summary>Can the county spend more after its budget is adopted?</summary>
<p><b>Supplemental appropriation:</b> a further appropriation made after the
annual budget has been adopted. The commissioners may apply to the convention
for one, or the convention may take one up on its own initiative. It needs
notice to the members, towns and cities, a public hearing within 30 days of
that notice, and its own vote of the convention (RSA 24:14-a). A narrower
emergency route runs through the executive committee, again after a public
hearing (RSA 24:15).</p>
</details>
<details><summary>Who sets the county officers&rsquo; pay?</summary>
<p>The convention also sets what the elected county officers are paid. It
establishes their salaries, benefits and other compensation every two years,
acting on the executive committee's recommendation, before the filing period
for the next election (RSA 23:7).</p>
</details>
<details><summary>What does the register of probate still do?</summary>
<p>The register of probate is still elected, though almost all of the duties
are gone. On July 1, 2011 the probate court became the probate division of the
Circuit Court (RSA 490-F:3), and the registers' duties passed to the circuit
court clerks, apart from a few the statute leaves with the register
(RSA 490-F:13). Among those, the register works with the Secretary of State
and the administrative judge of the Circuit Court on preserving closed files
that may be of historical significance, and keeps an index of any files
removed from the court (RSA 548:5). The office is named in the constitution,
in articles 71 and 81 of Part Second, so removing it takes an amendment and
not a bill: <a href="bill/2022/cacr21.html">CACR 21 (2022)</a> would have
struck it out, passed both chambers, and went to the voters, where it did not
reach the <a href="learn/the-constitution.html">two thirds of those
voting</a> an amendment needs. [[probate_vote]]</p>
</details>
<details><summary>Does New Hampshire elect a coroner?</summary>
<p>No. New Hampshire elects none. Sudden, unexpected or unnatural
deaths are investigated by medical examiners of the Office of the Chief
Medical Examiner, a state office within the Department of Justice, rather than
by a county officer (RSA 611-B:2, 611-B:11). RSA 611-B replaced RSA 611, the
earlier medical examiners chapter, which was repealed in 2007.</p>
</details>
</div>
""" + SHOWS.format("""
<p><a href="officials.html">Every member of both chambers</a> has a page
here, with the county and district they were elected from. The House members
from a county are that county's convention, so the roster is the membership
list.</p>
<p><a href="directory/towns.html">Every town and ward</a> is listed by county,
with the districts that cover it.</p>""")

BODY_COUNTY_HOLDS = """This site is the record of the state legislature, and
county government is not in it. There are no county budgets here, no minutes
or warrants of a county convention, no county election results and no county
officers' accounts. What it does hold is the roster: the representatives who
make up each county's delegation have pages here because of the other office
they were elected to. The county's own record is kept by the county."""


BODY_TOWNS = """
<h2>City or Town</h2>
<p>There are [[municipalities]] cities and towns in New Hampshire, and Title
III of the Revised Statutes governs all of them. The difference between a city
and a town is not size, and not the word on the sign. In most places it is who
the legislative body is &mdash; who adopts the budget and passes the
ordinances.</p>

<p>In most towns, the legislative body is the voters themselves, assembled at
<a href="learn/local-government.html">town meeting</a>. In a city it is an
elected council, and so it is in a town whose charter replaced the meeting
with a town council (RSA 49-D:3). Nearly everything else follows from that one
difference.</p>
<div class="yt" data-yt="town" hidden></div>
""" + TOWN_FORMS + """

<h2>A Town: The Meeting Decides, the Selectboard Carries It Out</h2>
<p><b>Selectmen:</b> the executive of a town. The statutes say selectmen
(RSA 41:8); selectboard is the term in common use now for the same body. A
town elects one selectman each year for a 3-year term, which makes a board of
three (RSA 41:8). On the written application of 25 registered voters, or 2
percent of them, whichever is less and never fewer than 10, the question of
increasing the board to 5 goes on the ballot (RSA 41:8-b).</p>

<p>The board's first job is to carry out what the meeting voted: it manages
the town's day-to-day business between meetings (RSA 41:8) and puts together
the warrant for the next one. It has some powers of its own &mdash; it may
regulate the use of the town's highways, sidewalks and commons (RSA 41:11),
and it manages the town's land and buildings unless the town has handed that
to other officers or another statute governs it (RSA 41:11-a) &mdash; but the
money it spends is the money the meeting appropriated.</p>

<p><b>Moderator:</b> presides at the meeting, regulates its business, decides
questions of order and declares every vote passed. The moderator may postpone
a session for a weather warning, or for an emergency that makes the place
unsafe (RSA 40:4).</p>

<h2>A City: A Council Decides, a Mayor or a Manager Carries It Out</h2>
<p>A city has no town meeting. The powers the law vests in towns, or in the
inhabitants of them, are exercised by the city council (RSA 47:1). The council
may be called a <b>city council</b> or a <b>board of aldermen</b>; the name is
the city's and the function is the same. How many members there are, and
whether they are elected by ward or at large or both, is set by the city's
charter.</p>

<p><b>Mayor:</b> under the general law the mayor is the chief executive
officer of the city (RSA 45:7), presides in the board of aldermen, and has a
veto the aldermen can override only by two thirds of all the aldermen elected
(RSA 45:9).</p>

<p><b>Council-manager:</b> the other common arrangement, set out for charter
cities at RSA 49-C. The charter names either the mayor or an appointed
<b>city manager</b> as chief administrative officer, heading the
administrative branch, supervising the city's administrative affairs and
carrying out the policies the elected body enacts (RSA 49-C:16). The council
appoints the manager for an indefinite term and fixes the salary, by a vote of
at least a majority of the council, and the charter sets out how the manager
may be removed (RSA 49-C:17). Where a city runs this way, the mayor chairs the
council and the manager runs the administration.</p>

<h2>Town Managers</h2>
<p>A town may adopt the town manager form under RSA 37. It takes a vote: the
chapter does not operate in a town until a majority of the voters present and
voting at an annual meeting adopt it (RSA 37:11), and on the written
application of 10 or more voters the selectmen must put the question in the
warrant (RSA 37:12). Once adopted, the selectmen
appoint the manager (RSA 37:2), who becomes the administrative head of all
departments of the town and is responsible for administering them (RSA 37:5).
The manager appoints and dismisses subordinate staff, examines the affairs of
any department under the manager's control, and prepares the year's
expenditure and revenue estimates (RSA 37:6). What the manager does not get
are the things the meeting and the selectmen keep, among them warning town
meetings, making bylaws, borrowing money, assessing or collecting taxes,
granting licenses and laying out highways; nor does the manager supervise the
town clerk or the town treasurer (RSA 37:5).</p>


<h2>The Other Names on a Town Ballot</h2>
<p>Some offices every town governed by selectmen elects by ballot: the
selectmen themselves, the moderator, the supervisors of the checklist and the
town clerk. The town treasurer and highway agents are elected the same way
unless the town has provided for appointing them (RSA 669:15). A town whose
charter gives the selectmen's powers to a town council has no selectmen, but it
still elects its town clerk (RSA 41:16, 49-D:3).</p>

<p>Others a town elects only if it has voted to: the tax collector, town
assessors, constables or police officers, the fire chief or firewards, and the
elected members of a planning board, zoning board of adjustment, budget
committee or conservation commission (RSA 669:17).</p>

<table><tbody>
<tr><th scope="row"><b>Town clerk</b></th><td>Keeps the town's records, issues the
licenses and registrations, and runs the mechanics of elections. A town may
vote to make the term 3 years (RSA 41:16-b).</td></tr>
<tr><th scope="row"><b>Tax collector</b></th><td>Collects the taxes the selectmen commit,
remits them to the treasurer at least weekly, and daily once receipts reach
$3,500, keeps the account of what was collected
and abated, and reports at year end (RSA 41:35).</td></tr>
<tr><th scope="row"><b>Clerk/tax collector</b></th><td>Many towns have combined the two
into one office. It takes a petitioned article and a majority at the annual
meeting, and the combined officer is then elected for a term of one year or
three (RSA 41:45-a).</td></tr>
<tr><th scope="row"><b>Treasurer</b></th><td>Has custody of the town's money, pays it out
on the selectmen's orders, keeps the accounts, and invests what is not
immediately needed under the selectmen's investment policy
(RSA 41:29).</td></tr>
<tr><th scope="row"><b>Supervisors of the checklist</b></th><td>Three legal voters of the
town, who keep the voter checklist. One is elected every even-numbered year
for 6 years, unless the town has adopted 3-year terms
(RSA 41:46-a).</td></tr>
<tr><th scope="row"><b>Trustees of trust funds</b></th><td>Three, or five if the town has
voted for five, administering the funds held in trust for the town. The term
is three years, and on a board of three one trustee is elected each year
(RSA 31:22).</td></tr>
<tr><th scope="row"><b>Library trustees</b></th><td>Any odd number the town decides on,
elected at town meeting for staggered 3-year terms (RSA 202-A:6).</td></tr>
<tr><th scope="row"><b>Cemetery trustees</b></th><td>Elected by ballot at the annual town
meeting to replace those whose terms expire; in a city, chosen as the city's
ordinance provides (RSA 289:6).</td></tr>
</tbody></table>

<h2>Planning Board and Zoning Board of Adjustment</h2>
<p>These two decide what may be built and where, and whether a particular
property is let off a rule. In some towns you elect them and in others you do
not, and which it is was a choice the town made.</p>

<p>A <b>planning board</b> has 5 or 7 members in most towns, 7 or 9 in a town
with a council, and 9 in a city. In a town governed by a meeting, one
selectman or administrative official of the town sits on it ex officio and the
selectmen appoint the rest, unless the town meeting has voted that those
members be elected; a town that has voted for election may later vote to go
back (RSA 673:2).</p>

<p>A <b>zoning board of adjustment</b> has 5 members, either elected in the
manner RSA 669 prescribes or appointed in the manner the local legislative
body prescribes (RSA 673:3).</p>

<h2>School Boards and the SAU</h2>
<p>A school district is a body separate from the town, with its own meeting,
its own budget and its own ballot. Its <b>school board</b> has 3, 5, 7 or 9
members as the district votes, and 3 if it has not voted, elected for three
years with an equal number elected each year where that can be done
(RSA 671:4). A cooperative school district covers more than one town, and its
articles of agreement decide how its board is chosen. The statute allows
several methods, among them electing all members at large, electing them from
districts drawn by population, or electing them at large with at least one
member living in each of the districts that formed it (RSA 195:19-a).</p>

<p><b>School administrative unit:</b> the SAU, the administrative body serving
one district or several together. Its board is made up of the school board
members of the districts in it, each district's members sharing that
district's votes (RSA 194-C:7). That board arranges superintendent services,
sets the salaries of the administrative staff and apportions the cost among
the member districts, and it has the power to remove the superintendent
(RSA 194-C:5). This is why the superintendent answers to a board you did not
vote for directly: you elected your district's school board, and your
district's school board sits on the SAU board.</p>

<h2>Changing the Form of Government: The Charter</h2>
<p><b>Charter:</b> a municipality's own written constitution, adopted by its
voters. Any incorporated town or city, whatever its population, may draw one
up under RSA 49-B, the home rule chapter. A charter prepared under RSA 49-C
establishes a city government; one prepared under RSA 49-D establishes a town
government (RSA 49-B:2).</p>

<p>It starts with a question on the ballot. On the petition of 25 registered
voters, or 2 percent of them, whichever is less and never fewer than 10, the
voters are asked whether a charter commission shall be established
(RSA 49-B:3). If they say yes, a commission of nine is elected (RSA 49-B:4),
it reports, and the charter it writes goes back to the voters, where it takes
effect only if three fifths of the ballots cast on the question favor it
(RSA 49-B:6).</p>
""" + flow_diagram(FLOW_CHARTER, "How a charter is adopted", level_names=True) + """



<p>This is why two towns of the same size, ten miles apart, can be run in
entirely different ways, and why the offices on your ballot are not the
offices on your neighbor's.</p>

<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>Is a town administrator the same as a town manager?</summary>
<p>A <b>town administrator</b> is a different thing, and the difference
matters when you are working out who decides. There is no statutory office of
town administrator. The selectmen hire one to help them run the town's
business, and the administrator works under their direct supervision. Adopting
RSA 37 moves authority from the elected board to an appointed officer; hiring
an administrator does not, and needs no vote of the meeting.</p>
</details>
<details><summary>What is a village district?</summary>
<p><b>Village district:</b> a smaller unit inside one or more towns, formed to
provide one service or a few. On the petition of 10 or more voters domiciled
in a village the selectmen fix the district's bounds, and the statute lists
the purposes one may be formed for: fire protection, street lighting, water
supply, sidewalks and drains, sewage, parks, police, roads and ambulance
service among them (RSA 52:1). Once formed it is a body corporate and politic,
with the same powers a town has in relation to the same objects
(RSA 52:3).</p>

<p>A district holds its own meeting and has its own moderator, clerk,
treasurer and commissioners, who have the same powers over the district's
business as a town's moderator, clerk, treasurer and selectmen have over the
town's (RSA 52:8). A village district may adopt the manager form too, but
only once the town it lies in (or, if it spans towns, the one holding most of
its taxable value) has adopted it, and it must then appoint that town's
manager as its own (RSA 37:14). If you live in one, it is a separate line on
your tax bill.</p>
</details>
<details><summary>How does a charter already in force change?</summary>
<p>A charter already in force changes by one of two routes. A revision, which
changes the form of government, goes through a charter commission of its own:
the question of establishing one reaches the ballot by order of the municipal
officers or on a petition of voters numbering at least 20 percent of the
ballots cast at the last regular municipal election, and the revised charter
too needs three fifths (RSA 49-B:4-d, 49-B:4-e, 49-B:6). Any other change is
an amendment: the municipal officers, or a petition of voters numbering at
least 15 percent of those ballots, put it on the ballot with no commission,
and a majority adopts it (RSA 49-B:5, 49-B:6). A town may also repeal its
charter and return to the form of government it had before, on a petition of
its voters put to the ballot the same way as an amendment (RSA 49-B:12).</p>
</details>
<details><summary>Does a town charter have to end town meeting?</summary>
<p>A town charter does not have to abolish the town meeting. RSA 49-D:3 sets
out the forms a town charter may choose between: a town council; an official
ballot town council; a budgetary town meeting, which keeps the meeting but
limits it to the operating budget and bonds; an official ballot town meeting;
and a representative town meeting, where members elected from districts vote
in place of the whole electorate. A charter may also make a <b>town
manager</b> the chief administrative officer, under the town council-town
manager form (RSA 49-D:2).</p>
</details>
</div>
""" + SHOWS.format("""
<p><a href="directory/towns.html">Every town and ward</a> is listed here with
the House and Senate districts that cover it, which is the route from where
you live to the legislators who represent it.</p>
<p>Bills changing what towns and cities may do arrive in the record
constantly. They are in <a href="bills.html">the bill list</a> with everything
else, and a bill's page names the committee that heard it.</p>""")

BODY_TOWNS_HOLDS = """This site holds the state legislature's record and
nothing municipal. There are no town or city budgets here, no warrants, no
minutes of a selectboard or a council, no local ordinances and no municipal
election results. Your town or city clerk keeps those. This page is here
because bills about towns and cities arrive in the record every week, written
as though you already knew all of this."""


# NEW HAMPSHIRE'S STATE SYMBOLS (the owner, 26 October 2026: "Another fun
# learn page could be listing all of the state designated things like the
# state bird and state gem and the various proposed official state things
# that didn't pass"). Every symbol is read from RSA chapter 3 on this site's
# own Laws page (/laws/3) on 26 October 2026: its section, what the section
# names, and the earliest year its source note gives; a bill is linked where
# the source note names one. The proposals that did not pass are the bill
# record's (idx/<term>.json, read the same day), each by its number, year,
# title and status exactly as the record gives them. A Learn page has no
# claim check to hold it back, so nothing here goes past those two.
def _bill_link(year, number):
    """HB 776-FN of 2025 -> its page in this site's record."""
    slug = number.split("-")[0].replace(" ", "").lower()
    return f'<a href="bill/{year}/{slug}.html">{number}</a>'


def _symbols(caption, rows):
    """A table of symbols: what each is, the law's words for it, its section
    on the Laws page and the year it was named, with the bill where the
    record has one. `rows` is [(symbol, words, section, year, bill)], bill
    None or (year, number)."""
    def enacted(year, bill):
        return year if not bill else f"{year} &middot; {_bill_link(*bill)}"
    return ('<div class="l-tablewrap l-stack"><table class="l-table">'
            f'<caption class="sr">{caption}</caption>'
            '<thead><tr><th scope="col">Symbol</th><th scope="col">What the law names</th>'
            '<th scope="col">Section</th><th scope="col">Named</th></tr></thead><tbody>'
            + "".join(f'<tr><th scope="row">{sym}</th><td data-l="What the law names">{words}</td>'
                      f'<td class="l-rsa" data-l="Section"><a href="/laws/3#s{sec.lower()}">RSA 3:{sec}</a></td>'
                      f'<td class="l-rsa" data-l="Named">{enacted(year, bill)}</td></tr>'
                      for sym, words, sec, year, bill in rows)
            + "</tbody></table></div>")


def _proposals(caption, rows):
    """The record's bills that did not pass: [(year, number, title, how it
    ended)], each as the bill index gives it."""
    return ('<div class="l-tablewrap l-stack"><table class="l-table">'
            f'<caption class="sr">{caption}</caption>'
            '<thead><tr><th scope="col">Bill</th><th scope="col">Year</th>'
            '<th scope="col">Its title</th><th scope="col">How it ended</th></tr></thead><tbody>'
            + "".join(f'<tr><th scope="row">{_bill_link(year, n)}</th><td data-l="Year">{year}</td>'
                      f'<td data-l="Its title">{title}</td><td data-l="How it ended">{end}</td></tr>'
                      for year, n, title, end in rows)
            + "</tbody></table></div>")


SYMBOLS_EMBLEMS = _symbols("The emblems of the state", [
    ("Motto", "&ldquo;Live Free or Die,&rdquo; written by General John Stark, July 31, 1809",
     "8", "1945", None),
    ("Seal", "The frigate Raleigh on the stocks, the sun rising over the sea, a laurel border "
     "and the date 1776", "9", "1931", None),
    ("Flag", "A blue field with the state seal at its center, in a wreath of laurel leaves "
     "with nine stars", "2", "1909", None),
    ("Emblem", "The Old Man of the Mountain in an elliptical panel, with the motto below and "
     "the words New Hampshire above", "1", "1945", None),
    ("Songs", "Ten songs, from &ldquo;Old New Hampshire&rdquo; to &ldquo;Live Free or "
     "Die&rdquo;", "7", "1949", None),
    ("Tartan", "A sett of green, black, white, purple and red", "21", "1995",
     ("1995", "HB 631")),
])

SYMBOLS_LIVING = _symbols("The plants and animals the law names", [
    ("Flower", "Purple lilac, <i>Syringa vulgaris</i>", "5", "1919", None),
    ("Tree", "White birch, <i>Betula papyrifera</i>", "6", "1947", None),
    ("Bird", "Purple finch", "10", "1957", None),
    ("Insect", "Ladybug, also known as the ladybird and the lady beetle", "11", "1977", None),
    ("Animal", "White tail deer", "12", "1983", None),
    ("Amphibian", "Spotted newt, <i>Notophthalmus viridescens</i>", "16", "1985", None),
    ("Wildflower", "Pink lady&rsquo;s slipper, <i>Cypripedium acaule</i>", "17", "1991",
     ("1991", "SB 40")),
    ("Butterfly", "Karner Blue, <i>Lycaeides melissa</i>, subspecies <i>samuelis</i>", "18",
     "1992", ("1992", "HB 1210")),
    ("Saltwater game fish", "Striped bass, <i>Roccus saxatilis</i>", "19", "1994",
     ("1994", "HB 1438")),
    ("Freshwater fish", "Brook trout, <i>Salvelinus fontinalis</i>", "20", "1994",
     ("1994", "SB 538")),
    ("Dog", "Chinook", "25", "2009", ("2009", "SB 13")),
    ("Wildcat", "Bobcat, <i>Lynx rufus</i>", "28", "2015", ("2015", "HB 423")),
    ("Poultry", "New Hampshire Red", "29", "2018", ("2018", "HB 1474")),
    ("Raptor", "Red-tailed hawk, <i>Buteo jamaicensis</i>", "30", "2019", ("2019", "HB 280")),
    ("Spider", "Daring jumping spider, <i>Phidippus audax</i>", "31", "2021", ("2021", "HB 318")),
    ("Marsupial", "Virginia opossum, <i>Didelphis virginiana</i>", "32", "2025",
     ("2025", "HB 776-FN")),
])

SYMBOLS_OTHER = _symbols("The stones, foods and sport the law names", [
    ("Rock", "Granite", "13", "1985", None),
    ("Mineral", "Beryl", "14", "1985", None),
    ("Gem", "Smoky quartz", "15", "1985", None),
    ("Sport", "Skiing", "22", "1998", ("1998", "SB 412")),
    ("Fruit", "Pumpkin", "24", "2006", ("2006", "HB 1111")),
    ("Beverage", "Apple cider", "26", "2010", ("2010", "HB 1206")),
    ("Vegetable", "White potato", "27", "2013", ("2013", "HB 535")),
])

PROPOSED_SYMBOLS = _proposals("Proposed state symbols that did not pass", [
    ("2011", "HB 41", "designating purple as the official state color.", "Killed"),
    ("2012", "HB 1430", "designating the Thompson/Center Contender pistol as the official "
     "state firearm of New Hampshire.", "Killed"),
    ("2012", "SB 302", "relative to the Honor and Remember Flag as an official symbol to "
     "recognize and honor fallen members of the armed forces and relative to certain "
     "maintenance at the rotary in the town of Epsom.",
     "Died: the chambers did not agree on a version"),
    ("2013", "HB 420", "establishing orange, red, and yellow as the state colors.",
     "Died on the table"),
    ("2015", "HB 113", "designating the mastodon as the official state fossil.", "Killed"),
    ("2015", "HB 152", "establishing a state poem.", "Killed"),
    ("2015", "HB 373", "establishing the red-tailed hawk as the New Hampshire state raptor.",
     "Killed"),
    ("2020", "SB 42", "declaring Old Hampshire Applejack the state spirit of New Hampshire.",
     "Killed"),
    ("2025", "HB 89", "designating &ldquo;Within the Crystal Hills&rdquo; as the official "
     "animated film of New Hampshire.", "Killed"),
    ("2025", "SB 30", "proclaiming the Virginia opossum the state marsupial of New Hampshire "
     "and relative to the penalty for incorrect application of fertilizers.",
     "Died: the chambers did not agree on a version"),
    ("2026", "HB 1020", "proclaiming Lake Winnipesaukee the official state lake of New "
     "Hampshire.", "Killed"),
    ("2026", "HB 1390", "designating the apple cider doughnut the official doughnut of the "
     "state of New Hampshire.", "Killed"),
])

# The bills in the record that proposed to change the flag or to study it:
# the nine the flag section's own Laws page lists as bills whose text says
# they change RSA 3:2, and the two studies, which change no section.
PROPOSED_FLAGS = _proposals("Proposals to change or study the state flag", [
    ("1996", "HB 552-FN", "relative to the design and the display of the state flag.",
     "Referred for interim study"),
    ("1997", "HB 138-FN", "relative to the design and the display of the state flag.", "Killed"),
    ("2000", "SB 423-FN-LOCAL", "relative to the New Hampshire state flag.", "Killed"),
    ("2001", "SB 94-FN-LOCAL", "relative to the New Hampshire state flag.", "Killed"),
    ("2004", "HB 1231-FN", "relative to the state flag.", "Killed"),
    ("2004", "SB 319-FN-LOCAL", "relative to the New Hampshire state flag.", "Killed"),
    ("2005", "HB 123", "relative to the New Hampshire state flag.", "Killed"),
    ("2018", "HB 1242", "establishing a committee to study redesigning the state flag.",
     "Killed"),
    ("2024", "HB 1016", "relative to the New Hampshire state flag.", "Killed"),
    ("2025", "HB 176-FN", "relative to changing the state flag design.", "Killed"),
    ("2025", "HB 210", "establishing a commission to study the state flag and its history.",
     "Killed"),
])

BODY_SYMBOLS = """
<h2>What the Law Names</h2>
<p>New Hampshire&rsquo;s symbols are named in its statutes, in chapter 3 of
the Revised Statutes Annotated, headed &ldquo;State Emblems, Flag, Etc.&rdquo;
Twenty-nine of its sections each name one: a motto, a seal, a flag, an
emblem, ten songs, a tartan, and the plants, animals, stones, foods and sport
below. Each section links to <a href="/laws/3">the chapter</a> on this site.</p>
<p>The year beside each is the earliest year the section&rsquo;s source note
gives. Where the law is from 1989 or later, the bill that made it is linked to
its page in this site&rsquo;s record.</p>

<h2>The Emblems of the State</h2>
<p>The motto is the words &ldquo;Live Free or Die,&rdquo; written by General
John Stark on July 31, 1809. The flag is blue, with the state seal at its
center inside a wreath of laurel leaves and nine stars. The seal is two inches
across, and the law sets out its detail &ldquo;and no other&rdquo;: the frigate
Raleigh on the stocks, the sun rising over the sea, a granite boulder, and the
date 1776 between two stars. The emblem may be placed on the state&rsquo;s
printed material about developing its recreational, industrial and
agricultural resources.</p>
""" + SYMBOLS_EMBLEMS + """
<p>The seal&rsquo;s source note opens with entries that name no year, so 1931
is the first year it gives. The tartan&rsquo;s colors each stand for
something, its section says: purple for the purple finch and the purple
lilac, the state bird and the state flower; green for the forests; black for
the granite mountains; white for the snow; and red for all state heroes.</p>

<h2>Plants and Animals</h2>
<p>Sixteen of the sections name a living thing. The first was the purple
lilac, in 1919. The most recent is the Virginia opossum, in 2025, and its
section adds that opossums found within the state&rsquo;s borders &ldquo;shall
be known as &lsquo;New Hampshire opossums.&rsquo;&rdquo;</p>
""" + SYMBOLS_LIVING + """

<h2>Stone, Food and Sport</h2>
<p>Granite, beryl and smoky quartz were named by the same law, in 1985. The
foods came later: the pumpkin in 2006, apple cider in 2010 and the white
potato in 2013.</p>
""" + SYMBOLS_OTHER + """

<h2>The Flag Over the State House</h2>
<p>The state flag is displayed above the State House whenever the legislature
is in session, during meetings of the Governor and Council when expedient,
and on other occasions the Governor designates
(<a href="/laws/3#s3">RSA 3:3</a>). The Governor may make rules for its use
and display, and the law is to be read &ldquo;to encourage the display of the
state flag on public buildings&rdquo; (<a href="/laws/3#s4">RSA 3:4</a>).</p>
<p>The POW-MIA flag is displayed above the State House, all state facilities
and the state&rsquo;s military facilities whenever the flag of the United
States is flown (<a href="/laws/3#s3-a">RSA 3:3-a</a>). Only flags officially
recognized by the federal government may be flown over the State House. A
state, United States or POW-MIA flag bought with state funds or displayed in a
state facility must be made in the United States, if it was acquired after
that section took effect (<a href="/laws/3#s4-a">RSA 3:4-a</a>).</p>

<h2>Proposed Symbols That Did Not Pass</h2>
<p>This site&rsquo;s bill record goes back to 1989, and some of its bills
proposed a symbol that never became law. Each line is the record&rsquo;s own: the
bill&rsquo;s number, its year, its title and how it ended.</p>
""" + PROPOSED_SYMBOLS + """
<p>Two of them came back. The red-tailed hawk, killed as HB 373 in 2015,
became the state raptor as <a href="bill/2019/hb280.html">HB 280</a> in 2019.
The Virginia opossum&rsquo;s own bill, SB 30, died in 2025 when the chambers
did not agree on a version; the same designation passed that year inside
<a href="bill/2025/hb776.html">HB 776-FN</a>, a bill about the crime of
aggravated driving while intoxicated.</p>
<h3>Changing the Flag</h3>
<p>The flag&rsquo;s section was last changed in 1931, by its source note.
Every bill in the record that proposed to change it, or to study it, has died
or gone to interim study.</p>
""" + PROPOSED_FLAGS + """

<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>What are the ten state songs?</summary>
<p>The law lists them in this order (<a href="/laws/3#s7">RSA 3:7</a>):</p>
<ul>
<li>&ldquo;Old New Hampshire,&rdquo; words by Dr. John F. Holmes, music by Maurice Hoffmann</li>
<li>&ldquo;New Hampshire, my New Hampshire,&rdquo; words by Julius Richelson, music by Walter P. Smith</li>
<li>&ldquo;New Hampshire Hills,&rdquo; words by Paul Scott Mowrer, music by Tom Powers</li>
<li>&ldquo;Autumn in New Hampshire,&rdquo; words and music by Leo Austin</li>
<li>&ldquo;New Hampshire&rsquo;s Granite State,&rdquo; words and music by Anne B. Currier</li>
<li>&ldquo;Oh, New Hampshire (you&rsquo;re my home),&rdquo; words and music by Brownie McIntosh</li>
<li>&ldquo;The Old Man of the Mountain,&rdquo; words and music by Paul Belanger</li>
<li>&ldquo;The New Hampshire State March,&rdquo; words and music by Rene Richards</li>
<li>&ldquo;New Hampshire Naturally,&rdquo; words and music by Rick Shaw and Ron Shaw</li>
<li>&ldquo;Live Free or Die,&rdquo; words and music by Barry Palmer</li>
</ul>
<p>The last was added in 2007, by <a href="bill/2007/hb482.html">HB 482</a>.</p>
</details>
<details><summary>Who counts as a New Hampshire native?</summary>
<p>Someone born in New Hampshire, or born to a mother domiciled in New
Hampshire at the time of the birth. The section says it does not affect
official records, and that no one who in good faith proclaims themselves a
native under it may be charged with perjury
(<a href="/laws/3#s23">RSA 3:23</a>, added in 2002 by
<a href="bill/2002/hb1175.html">HB 1175</a>).</p>
</details>
<details><summary>Why are there two state flowers and two state fish?</summary>
<p>The law names them as different symbols. The purple lilac is the state
flower and the pink lady&rsquo;s slipper the state wildflower. The striped
bass is the state saltwater game fish and the brook trout the state
freshwater fish; both fish were named in 1994.</p>
</details>
<details><summary>Can I put the state seal on something I sell?</summary>
<p>Not without the Secretary of State&rsquo;s authorization. The seal is the
property of the state, and no one may make or sell merchandise bearing a
likeness of it, or put it on anything used to advertise or promote services,
unless the Secretary of State has authorized that use (<a href="/laws/3#s9-a">RSA 3:9-a</a>). Doing so
is a misdemeanor for a natural person and a felony for any other person
(<a href="/laws/3#s9-b">RSA 3:9-b</a>), and the Attorney General may go to
court to stop the articles being distributed
(<a href="/laws/3#s9-c">RSA 3:9-c</a>).</p>
</details>
<details><summary>How does something become a state symbol?</summary>
<p>By a bill, like any other law. Each of the sixteen sections added to the
chapter since 1991 came from a bill the record shows signed into law, and this
page links each one. <a href="learn/how-a-bill-becomes-law.html">How a
bill becomes law</a> follows the course every one of them took.</p>
</details>
</div>
"""

BODY_SYMBOLS_HOLDS = """This site's bill record begins in 1989, so a symbol
named before then has no bill page here; its year is the one its section's
source note gives. The proposals that did not pass were found by their
titles, so a symbol proposed inside a bill titled for something else would
not be among them."""


# WHAT THE GUIDES ALSO SAY IS THEIRS (the person's approval of 23 October
# 2026). This page and the guides to attending a hearing and to submitting
# testimony said the same things in copied paragraphs, and the copies had
# begun to drift. Each such paragraph is written once now, in guides.SAID,
# beside the claims that source it, and a <!-- guides:NAME --> here marks
# where it goes; build_civics writes it in (guides.reused). The rest of the
# page is its own.
BODY_TESTIFYING = """
<h2>Open to the Public</h2>
<p><b>Every legislative meeting and hearing is open to the public.</b> You may
attend in person, and most are live streamed and archived, so you can watch
one later. Where you may <i>speak</i> is narrower: a public hearing is the
meeting for that, and it is the only one at which members of the public are
heard. You may attend any other meeting &mdash; an executive session, a
subcommittee, a work session &mdash; but not speak at it.</p>
""" + WHERE_TO_SPEAK + """
<p>A public hearing is the meeting at which a committee hears a bill before it
votes on what to recommend. Every bill introduced gets one, and anyone may
speak at it.</p>
<p>You do not need to be invited, and you do not need to speak: signing in for
or against is itself part of the record, and it is counted. Nor does a bill
have to affect you. Committees hear bills for the whole state rather than for
a district, so anyone may speak on any bill, whoever they are and wherever
they live.</p>

<h2>How Hearings Are Announced</h2>
<!-- guides:announced -->
<p>The calendars are published weekly, and the General Court keeps a meeting
schedule online as well. Across the [[notice_hearings]] hearings those
calendars announced in the [[term]] term, the median notice is
<b>[[notice_median]] days</b>. That is the gap between the day the calendar is
published and the day of the hearing.</p>
<p>Notices name the room by building:</p>
<table><caption class="sr">The buildings a notice names</caption><tbody>
<tr><th scope="row"><b>SH</b></th><td><b>State House:</b> 107 North Main Street,
Concord.</td></tr>
<tr><th scope="row"><b>LOB</b></th><td><b>Legislative Office Building:</b> 33 North State
Street, Concord. Out of use for hearings while it is being worked on, and
named in older notices.</td></tr>
<tr><th scope="row"><b>GP</b></th><td><b>Granite Place:</b> 1 Granite Place, Concord, where
House committee meetings are now held.</td></tr>
</tbody></table>
<p>The Legislative Office Building is expected back in service around the
start of the next term, and Granite Place to drop out of the rotation when it is.
<b>Go by the notice for the
hearing you are attending</b> &mdash; it names the building and the room, and
it is right about the day it was published whatever this page says.</p>

<h2>Signing In</h2>
<p><b>Both chambers take sign-ins online</b>, each through its own form on the
General Court's website, linked below.</p>
<!-- guides:forms -->
<p>In the House the committee is given the counts, and the sign-ins are
published after the hearing.</p>
<p>The window is not open indefinitely. <!-- guides:window --> If the bill
passes one chamber and gets a hearing in the other, there is a second window
on the same terms.</p>

<h2>The Steps, in Order</h2>
""" + flow_diagram(FLOW_TESTIFY, "How to testify, in order") + """

<h2>When a Hearing Starts</h2>
<!-- guides:starts-late -->

<h2>Speaking at the Hearing</h2>
<!-- guides:ask-to-speak -->
<p>The committee hears the sponsor and then anyone who has asked to speak. In
practice:</p>
<ul>
<!-- guides:sponsor-first -->
<!-- guides:chair-time -->
<!-- guides:notes -->
<!-- guides:props -->
<!-- guides:last-call -->
</ul>
<p>You do not have to be an expert. The most useful testimony is the most
concrete: what this bill would do to you, in your town, said in particulars
rather than in general &mdash; the cost, the date it would take effect, the
number of people it would reach, whatever the specific is in your case.</p>

<h2>Written Testimony</h2>
<p>You can give a committee your testimony in writing, as well as or instead
of speaking, and on the House's online form you can attach it to your
sign-in.</p>
<!-- guides:email -->
<!-- guides:paper -->

<h2>What Happens After the Hearing</h2>
<!-- guides:exec-session -->
<!-- guides:throughout-the-day -->
<p>The committee then reports its recommendation to the chamber, and
where it was split the majority and the minority each write a report. Whether
you spoke or only signed in, the counts and any written testimony stay in the
record.</p>

<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>Can I watch a hearing instead of going?</summary>
<p>Both chambers live stream the hearings of their standing committees, the
permanent committees bills are referred to, so a hearing can be watched as it
happens.</p>
</details>
<details><summary>Where are the sign-ins kept?</summary>
<p>The sign-ins are not part of the bill's docket, the General Court's list of
every action on it, and no link on the docket leads to them. They are kept in the General Court's own sign-in records, which
its website offers as a lookup of its own.</p>
</details>
<details><summary>Can I speak at an executive session?</summary>
<p>No testimony is taken at an executive session, and one can be hard to
catch.</p>
</details>
</div>
""" + SHOWS.format("""
<p>This site holds <b>[[hearings]] public hearings</b>, each with the committee
and the day. Every bill's page shows its own hearings. Where a hearing was
recorded &mdash; [[hearing_video_bills]] bills[[hearing_video_since]]
&mdash; the bill's Hearings tab links it, opened where the bill
was taken up when that moment has been found.
<a href="committees.html">A committee's page</a> lists every day it met and
what it heard.</p>
<p>Bills also carry the House's online sign-in counts: how many people
registered supporting, opposing and neutral. The Senate's online sign-ins are
not among the General Court's tables this site reads. Names and written
testimony are not published here.</p>""")


BODY_REPS = """
<h2>House and Senate Districts</h2>
<div class="yt" data-yt="reps" hidden></div>
<p>New Hampshire is divided into [[house_districts]] House districts and
[[senate_districts]] Senate districts. Every resident lives in one Senate
district and in at least one House district, set by the town or ward they live
in.</p>
<p>Most places have more than one state representative: [[multi_rep_places]]
of the [[all_places]] towns and city wards, either because their own district
elects several members, or because a floterial district is laid over it, or
both. The districts are built from whole towns and wards &mdash; the
constitution forbids the legislature to divide a town, ward or place when it
draws them &mdash; and within that limit representation is to be "as equal as
circumstances will admit" (Part II, Article 9).</p>

<h2>Everyone Who Represents One Town</h2>
<p>This is every seat a voter in one town elects, from the most local to the
whole state. The town is [[reps_town]], because its layers nest cleanly and
show a floterial district plainly.</p>
[[reps_example]]
<p>Who holds each of those seats today is on <a href="[[reps_town_url]]">
[[reps_town]]'s own page</a>, and every other town and ward has one like
it.</p>

<h2>What the District Numbering Means</h2>
<p>A House district is written as a county and a number: Rockingham 13,
Hillsborough 44, or abbreviated to <b>Rock 13</b>. The number is not a rank or
a size. It is an index within that county, and the map is redrawn every ten
years after the federal census.</p>
<p>Senate districts are numbered 1 to [[senate_districts]] across the whole
state rather than by county, and many cross county lines. Each elects one
senator, and district 22 is written <b>SD22</b>.</p>

<h2>What a Floterial District Is</h2>
<p>A floterial district is a House district laid exactly over two or more
neighboring House districts in the same county, each of which already elects
its own members. It elects one or more additional members across all of them
together. [[reps_town]]'s is laid over [[reps_under_n]] districts.</p>
[[reps_band]]
<p>A town's population is rarely an exact multiple of what one seat is worth,
and the constitution will not let the legislature split a town to even it out.
A floterial is where those remainders are pooled instead.</p>
<p>If you live in one of those towns or wards, you are represented by both: the
members of your own district, and the floterial members you share with the
towns or wards around you. [[floterial]] of the [[house_districts]] House
districts are floterial, and they account for [[floterial_seats]] of the
[[house_seats]] seats.</p>

<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>Are a district&rsquo;s members elected one to each town?</summary>
<p>A district may be a single town, one or more wards of a city, several towns
together, or a city's wards joined with neighboring towns. Where it has more
than one seat, its members are elected at large across the whole of it, not
one to each town. The largest elects [[largest]] representatives.</p>
</details>
<details><summary>Where does the law say which districts are floterial?</summary>
<p>The statute that sets out the districts, RSA 662:5, never uses the word
<i>floterial</i>. It simply lists each district's towns and its seats. A
floterial shows up there as a district covering exactly the same towns as two
or more of the county's other districts put together &mdash; [[reps_flot]] is
[[reps_flot_under]] combined. Every one of the [[floterial]] districts this
site marks as floterial passes that test against the statute.</p>
</details>
<details><summary>Will a representative read my email?</summary>
<p>[[members_email]] of the [[members_sitting]] sitting members publish an
email address in the General Court's directory. Almost none have staff, so a
message to a representative is read by that representative. Most have other
jobs.</p>
</details>
</div>
""" + SHOWS.format("""
<p><a href="officials.html">Every member of both chambers</a>, with their
district, party and county, and every recorded vote they have cast.</p>
<p>Every <a href="committees.html">committee page</a> lists its members and
has a button that opens an email to all of them at once.</p>""")


# READING THE SHORTHAND, FROM THE GLOSSARY (the person's approval of 23
# October 2026). Using This Site's table was typed beside
# src/pages/words/glossary.json, which /learn/glossary and the term popovers
# draw from, and the two had come to define VV, DV, A, OT3rdg, Retain and OTPA
# differently. Its rows are the glossary's entries now, as _motions() takes
# its rows from votes.json, so where the two disagreed the glossary's words
# stand: the person reviewed them on 17 October 2026. The table keeps its own
# choice of terms and their order, the hyphen that FN, A and LOCAL carry
# after a bill's number, and one note of its own: the docket's other ways of
# writing OTPA (OTP/AM in the General Court's own key, records/docket_abbrev.json).
SHORTHAND = ("OTP", "OTPA", "ITL", "IS", "Retain", "MA", "MF", "VV", "DV", "RC", "CC", "OT3rdg",
             "HJ", "SJ", "FN", "A", "LOCAL")
SHORTHAND_SUFFIXES = ("FN", "A", "LOCAL")
SHORTHAND_NOTES = {"OTPA": "the docket also writes OTP/A or OTP/AM"}


def _shorthand():
    import components
    g, E = components.WORDBOOK["glossary"], components.esc

    def row(k):
        e = g[k]
        says = E(e["says"]) + (f" ({SHORTHAND_NOTES[k]})" if k in SHORTHAND_NOTES else "")
        return (f'<tr><th scope="row"><b>{"-" if k in SHORTHAND_SUFFIXES else ""}{E(k)}</b></th>'
                f'<td><b>{E(e["name"])}{":" if says else ""}</b>{" " + says if says else ""}</td></tr>')
    return "<table><tbody>\n" + "\n".join(row(k) for k in SHORTHAND) + "\n</tbody></table>"


SHORTHAND_TABLE = _shorthand()


def shorthand_table(lang="en"):
    """The shorthand table in `lang` (the owner's guides in Spanish, 24
    October 2026): each term as the record prints it, and its name and
    meaning in the glossary's own translations (i18n.say_gloss), so the
    table and the glossary never say a term two ways in either language."""
    if lang == I.DEFAULT:
        return SHORTHAND_TABLE
    import components
    g, E = components.WORDBOOK["glossary"], components.esc
    notes = {"OTPA": I.say(lang, "reps.otpa_note", "the docket also writes OTP/A or OTP/AM")}

    def row(k):
        e = g[k]
        name = I.say_gloss(lang, k, "name", e["name"])
        says = I.say_gloss(lang, k, "says", e["says"]) if e.get("says") else ""
        says = E(says) + (f" ({notes[k]})" if k in notes else "")
        own = f' ({E(name)})' if name != e["name"] else ""
        return (f'<tr><th scope="row"><b lang="en">{"-" if k in SHORTHAND_SUFFIXES else ""}{E(k)}</b></th>'
                f'<td><b><span lang="en">{E(e["name"])}</span>{own}{":" if says else ""}</b>'
                f'{" " + says if says else ""}</td></tr>')
    return "<table><tbody>\n" + "\n".join(row(k) for k in SHORTHAND) + "\n</tbody></table>"


BODY_SITE = """
<h2>What This Site Is</h2>
<p>Granite Record is an index of the New Hampshire General Court's own record:
[[all_bills]] bills across [[terms]] two-year terms, back to [[first_year]],
with what each bill does, who sponsored it, when it was heard, how it was
voted on, and where in the recording that happened. It is built by machine
from the General Court's published files, and this page was last built on
[[built_on]].</p>


<h2>How to Find a Bill, a Member or a Town</h2>
<p>The <b>Search</b> button in the header, drawn as a magnifier, finds
legislators, committees, towns and this site's own pages: typing Litchfield
offers both the town and the
representative of that name. Anything else goes to
<a href="bills.html">the bill search</a>, which takes a bill number, several
separated by commas, or words from a title, sponsor or committee. It covers
one term, or all of them at once, and narrows by committee, topic, prime
sponsor, status, bill type and floor vote day. <a href="officials.html">Every sitting member</a> and
<a href="committees.html">every committee</a> has a page of their own.</p>

<h2>What a Bill's Page Holds</h2>
""" + BILL_TABS_PICTURE + """
<ul>
<li><b>Summary</b> &mdash; the General Court's own analysis, the current
status, and a narrative of what has happened, in order, with each action
linked to the journal or calendar that recorded it.</li>
<li><b>Bill Text</b> &mdash; the text and its amendments, where more than one
was published.</li>
<li><b>Votes</b> &mdash; every roll call this record holds, by member, from
[[rollcall_first_year]] on, and each voice or division vote on the bill, a
division with its count.</li>
<li><b>Hearings</b> &mdash; each meeting that took the bill up, with its day,
time and room, and the recording where there is one, opened at the moment
the bill was taken up.</li>
<li><b>Reports</b> &mdash; what the committee recommended and why, in the
committee's own words, and the Governor's message where a bill was
vetoed.</li>
<li><b>Sponsors</b> &mdash; the member who filed the bill and those who signed
on to it.</li>
<li><b>Documents</b> &mdash; the official pages this all comes from.</li>
<li><b>Related</b>, where there is any &mdash; bills and amendments that share
most of its language: the same text filed in another year, or carried into
another bill or an amendment to one, with what became of it. Found by
comparing the texts, so a match can be missed.</li>
</ul>

<h2>What a Timestamp Claims</h2>
<p>Not all of them claim the same thing, and the page says which.</p>
<ul>
<li>Where the chair can be heard taking the bill up, that is the time.</li>
<li>Where a roll call has a clock time in the official record, that is
used.</li>
<li>Otherwise the time is estimated from where the bill falls in the recording
and marked <b>approximate</b>. It can be several minutes out.</li>
<li>Where no moment has been found, the page says so and offers the whole
recording.</li>
</ul>

<h2>Reading the Shorthand</h2>
""" + SHORTHAND_TABLE + """

<h2>Following a Bill</h2>
<p>A bill still moving through the General Court carries an RSS feed, and so
does every sitting member, every current committee, and every topic. The
<b>Follow</b> control on a record's page gives the address where there is one.
There are also feeds for the record's newest actions and for hearings coming
up. A bill's feed ends once the bill is settled. [[follow_email]]</p>

<h2>How to Report an Error</h2>
<p>Every bill's, legislator's and committee's page carries a <b>Report a problem</b>
button beside its heading, because this will be wrong somewhere. It sends nothing that identifies you,
which also means we cannot reply. For an answer, or for an error on these
explanatory pages, write to
<a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a>.</p>

<h2>Common Questions</h2>
<div class="l-faq">
<details><summary>Does every term hold as much?</summary>
<p>Older terms hold less, and every bill's page says what its term carries and
what is not on the site yet.</p>
</details>
<details><summary>Why do some votes show no names?</summary>
<p>A voice or division vote has no member-by-member
record to show, because none was made.</p>
</details>
<details><summary>Why are captions never quoted?</summary>
<p>Captions are never quoted here. Automatic transcription renders "HB 1381"
as "HP 1381" often enough that a quotation would be a transcription error
wearing the clothes of a citation. The timestamp is the claim. The recording
is the evidence.</p>
</details>
</div>
"""

# The official addresses these pages send a reader to. Kept in one place
# because every one of them is a promise that something is there, and a
# promise made eleven times in eleven files is one nobody checks.
#
# check_civics_links.py verifies them over the network when somebody asks it
# to. Nothing here has been verified by this file, and preflight only checks
# that they are well formed and on a state domain -- so a link that has moved
# will read as fine until that script is run.
GC = "https://gc.nh.gov"
RSA = GC + "/rsa/html"
NH = "https://www.nh.gov"

# NOT on gc.nh.gov. The address this pointed at answers 404, and the state
# publishes the constitution under nh.gov rather than the General Court.
SRC_CONSTITUTION = ("The New Hampshire Constitution",
                    "https://www.nh.gov/glance/state-constitution")
# Both chambers publish their rules as a PDF now; the .aspx pages both of
# these named answer 404, which is how a source link rots quietly.
SRC_HOUSE_RULES = ("House Rules", GC + "/house/aboutthehouse/houseRules.pdf")
SRC_SENATE_RULES = ("Senate Rules", GC + "/senate/about_senate/senate_rules.pdf")
SRC_RSA = ("New Hampshire Revised Statutes Annotated", RSA)
# THIS SITE, not the General Court. Their address-lookup page answers 404,
# and the record already holds what it was there to give: a town page
# names that town's House and Senate districts, its Executive Councillor
# and its member of Congress, and the directory lists every town. A link
# to our own pages cannot rot without us noticing, because preflight
# resolves every internal link the builders write.
# My Town since the audit before the November webinar (25 October 2026):
# the finder and the map, and everyone who represents the town, on one tab.
SRC_FIND_MEMBER = ("Find your legislators, by town",
                   "/officials.html#my-town")
# THIS SITE's own Laws page and bill record, which the state symbols page
# reads (26 October 2026): chapter 3 as the Laws pages carry it, and the
# bills since 1989.
SRC_LAWS_3 = ("RSA 3, State Emblems, Flag, Etc., on this site's Laws pages", "/laws/3")
SRC_BILL_RECORD = ("This site's bill record, 1989 to 2026", "/bills.html")
SRC_TESTIFY = ("House online testimony sign-in",
               GC + "/house/committees/remotetestimony/")
# The Senate's own sign-in form. The person supplied the address on 17
# October 2026, and Senate Calendar No. 20 of May 8, 2025 prints it beside
# the budget hearing's notice; the Senate's guidance of 2021 gives the same
# path on the General Court's old host. Linked, never fetched from here.
SRC_SENATE_TESTIFY = ("Senate online sign-in",
                      GC + "/remotecommittee/senate.aspx")
# TWO SOURCES WITH NO ADDRESS (17 October 2026). The Senate's written
# guidance for the public is saved byte for byte in records/sources/, and no
# address of it is known that this project has read, so it is named and not
# linked. The other is the person's own account of how hearings and session
# days run, which says plainly whose it is: the pages state it as practice
# ("in practice", "usually"), never as a rule. build_civics.sources_list draws
# a source with no address as a row with no link.
SRC_SENATE_GUIDANCE = ("Public Guidance for Committee Meetings, September 7, 2021 "
                       "(New Hampshire Senate)", "")
SRC_OBSERVED = ("Observed practice, reported by the site's editor, October 2026", "")
SRC_SCHEDULE = ("House meeting schedule", GC + "/house/schedule/dailyschedule.aspx")
SRC_SENATE_SCHEDULE = ("Senate meeting schedule",
                       GC + "/senate/schedule/dailyschedule.aspx")
SRC_CALENDARS = ("House calendars and journals",
                 GC + "/house/calendars_journals/")
# The Senate's own list of the same, the index page fetch_senate_calendars.py
# reads (17 October 2026, for The Legislature's Year, whose Senate dates are
# printed in the Senate calendars).
SRC_SENATE_CALENDARS = ("Senate calendars and journals",
                        GC + "/senate/calendars_journals/")
# The three below were NH + "/council", "/governor" and "/agencies" until
# 11 September, when a browser found each one a "Page Not Found" on nh.gov.
# The replacements are the addresses nh.gov itself links to: the governor
# from its front page, the council from its agency list, and the list
# from its front page's "State Agency" link.
SRC_COUNCIL = ("The Executive Council", "https://www.council.nh.gov/")
SRC_GOVERNOR = ("The Governor's office", "https://www.governor.nh.gov/")
SRC_COURTS = ("New Hampshire Judicial Branch", "https://www.courts.nh.gov")
SRC_RULES = ("Administrative rules, RSA 541-A",
             RSA + "/NHTOC/NHTOC-LV-541-A.htm")
SRC_JLCAR = ("Joint Legislative Committee on Administrative Rules",
             GC + "/rules")
SRC_AGENCIES = ("State agencies, A to Z",
                NH + "/government/state-government-agencies")
SRC_SOS = ("Secretary of State", "https://www.sos.nh.gov")
# Neither of the two below is an authority, and both are labelled so, the way
# SRC_BALLOT_LIST is. They are here because each is the place the officials
# themselves send a resident next, and neither the state nor the counties
# publish an equivalent in one place.
SRC_COUNTIES = ("County government, county by county (New Hampshire "
                "Association of Counties, a membership body)",
                "https://www.nhcounties.org")
SRC_NHMA = ("Guidance for towns and cities (New Hampshire Municipal "
            "Association, a membership body)",
            "https://www.nhmunicipal.org")
# Not an authority, and labelled so. Every other source on these pages is
# the body that made the thing; this is a third party's list, included
# because it carries the vote share each amendment got at the polls and
# the Secretary of State does not publish those in one place.
SRC_BALLOT_LIST = ("Past amendments and their vote shares (Ballotpedia, "
                   "a third party)",
                   "https://ballotpedia.org/List_of_New_Hampshire_ballot_measures")
# The office that answers for a court decision on a statute, which is
# where a reader of the courts page most often wants to go next.
SRC_DOJ = ("New Hampshire Department of Justice", "https://www.doj.nh.gov")
# THE GENERAL COURT'S OWN SITE, WHOLE (17 October 2026). The Resources hub's
# section on other ways to follow legislation names the legislature's own
# site first, before any tracker. Linked, never fetched from here: it is one
# of guides.GENERAL_COURT_LINKS, which check_civics_links.py asks after only
# when a person starts it.
SRC_GENERAL_COURT = ("The General Court", GC + "/")
# The State House Visitor Center's own page, which the guide to touring the
# State House links for arranging a tour (17 October 2026). Linked, never
# fetched from here, for the same reason, and one of the same list.
SRC_VISITOR_CENTER = ("State House Visitor Center", GC + "/nh_visitorcenter/")

# THE RESOURCES HUB'S OFFICIAL SOURCES TAB: every outside source these pages
# cite, grouped by who publishes it (the groups' names are the approved
# prototype's, 9 October 2026). build_civics stops the build where a page
# cites a source that is in no group and not set aside below, or a group
# lists one no page cites, so the tab and the pages cannot disagree. The
# Secretary of State's results pages that The Record in Numbers cites are
# added to ELECTIONS_GROUP from the rows its table shows.
ELECTIONS_GROUP = "Elections and the Constitution"
SOURCE_GROUPS = [
    ("The General Court", [SRC_RSA, SRC_RULES, SRC_HOUSE_RULES, SRC_SENATE_RULES,
                           SRC_CALENDARS, SRC_SENATE_CALENDARS, SRC_SCHEDULE,
                           SRC_SENATE_SCHEDULE, SRC_TESTIFY, SRC_SENATE_TESTIFY, SRC_JLCAR]),
    ("The Governor and State Agencies", [SRC_GOVERNOR, SRC_COUNCIL, SRC_AGENCIES, SRC_DOJ]),
    ("The Courts", [SRC_COURTS]),
    (ELECTIONS_GROUP, [SRC_SOS, SRC_CONSTITUTION]),
    ("Towns and Counties", [SRC_NHMA, SRC_COUNTIES]),
]
# Cited, and not official: a third party's list, labelled so where it is
# cited. The hub's tab lists the state's own sites and the two membership
# bodies the officials themselves send a resident to.
NOT_OFFICIAL = [SRC_BALLOT_LIST]


# ---------------------------------------------------------------------------
# The eleven. Order is the proposal's order and it is what the "next topic"
# link walks; the hub and the sitemap read the same list.
# ---------------------------------------------------------------------------
HOW = GROUPS[0][0]
PART = GROUPS[1][0]
ABOUT = GROUPS[2][0]

TOPICS = [
    topic("general-court", "The General Court", HOW,
          "400 representatives and 24 senators, paid $200 for the two-year "
          "term. The largest state legislature in the country.",
          BODY_GENERAL_COURT,
          [SRC_CONSTITUTION, SRC_HOUSE_RULES, SRC_SENATE_RULES,
           SRC_FIND_MEMBER]),

    topic("how-a-bill-becomes-law", "How a Bill Becomes Law", HOW,
          "From an idea filed in the fall to a law that takes effect, and "
          "the several places along the way where a bill can stop.",
          BODY_BILL,
          [SRC_HOUSE_RULES, SRC_SENATE_RULES, SRC_CALENDARS,
           SRC_CONSTITUTION, SRC_OBSERVED]),

    # NEXT AFTER HOW A BILL BECOMES LAW, which ends at the Governor: this is
    # the same course laid on the calendar, and the home page's status box
    # links here (legislative_year.SLUG).
    topic(legislative_year.SLUG, legislative_year.TITLE, HOW,
          "When the House and Senate sit, and the deadlines a bill must meet.",
          BODY_YEAR,
          [SRC_CALENDARS, SRC_SENATE_CALENDARS, SRC_HOUSE_RULES,
           SRC_SENATE_RULES, SRC_CONSTITUTION]),

    topic("governor-and-council", "The Governor and the Executive Council",
          HOW,
          "The Governor signs or vetoes. The Council -- five members, elected "
          "by district -- approves contracts, nominations and pardons.",
          BODY_GOVERNOR,
          [SRC_CONSTITUTION, SRC_GOVERNOR, SRC_COUNCIL],
          BODY_GOVERNOR_HOLDS),

    topic("the-courts", "The Courts", HOW,
          "Supreme, Superior and Circuit; how judges are appointed and how "
          "long they serve; and where the legislature and the courts meet.",
          BODY_COURTS,
          [SRC_COURTS, SRC_CONSTITUTION, SRC_DOJ],
          BODY_COURTS_HOLDS),

    topic("the-constitution", "The Constitution", HOW,
          "One of the oldest still in force, and it is not amended the way "
          "statutes are: a CACR needs three fifths of both chambers and then "
          "the voters.",
          BODY_CONSTITUTION,
          [SRC_CONSTITUTION, SRC_SOS, SRC_BALLOT_LIST]),

    topic("state-agencies", "State Agencies", HOW,
          "Who actually carries out what the legislature passes, and how a "
          "commissioner gets the job.",
          BODY_AGENCIES,
          [SRC_AGENCIES, SRC_COUNCIL, SRC_CONSTITUTION]),

    topic("administrative-rules", "Administrative Rules", HOW,
          "A statute says what shall happen; the rules say how, and the "
          "agency writes them. This is the least visible part of the process "
          "and one of the most consequential.",
          BODY_RULES,
          [SRC_RULES, SRC_JLCAR, SRC_RSA],
          BODY_RULES_HOLDS),

    topic("local-government", "Town Meeting and Local Government", HOW,
          "Where warrant articles, default budgets and \u201cSB 2 towns\u201d "
          "come from.",
          BODY_LOCAL,
          [SRC_RSA, SRC_SOS],
          BODY_LOCAL_HOLDS),

    topic("county-government", "County Government", HOW,
          "Ten counties, and the body that sets each one's budget is the "
          "state representatives you already elected, meeting under a second "
          "name.",
          BODY_COUNTY,
          [SRC_RSA, SRC_COUNTIES, SRC_SOS],
          BODY_COUNTY_HOLDS),

    topic("city-and-town-government", "Cities, Towns and Who Runs Them", HOW,
          "A town meeting and a selectboard, or a council and a mayor, or a "
          "council and a manager.",
          BODY_TOWNS,
          [SRC_RSA, SRC_NHMA, SRC_SOS],
          BODY_TOWNS_HOLDS),

    topic("state-symbols", "New Hampshire\u2019s State Symbols", ABOUT,
          "The purple finch, the purple lilac, granite and smoky quartz: every "
          "symbol the law names, and the ones proposed that did not pass.",
          BODY_SYMBOLS,
          [SRC_LAWS_3, SRC_BILL_RECORD],
          BODY_SYMBOLS_HOLDS),

    topic("testifying", "How Public Hearings Work", PART,
          "The most open part of the process and the least known. Anyone may "
          "speak on any bill, and you do not need to be invited.",
          BODY_TESTIFYING,
          [SRC_TESTIFY, SRC_SENATE_TESTIFY, SRC_SCHEDULE, SRC_SENATE_SCHEDULE, SRC_CALENDARS,
           SRC_SENATE_CALENDARS, SRC_SENATE_GUIDANCE, SRC_OBSERVED]),

    topic("your-representatives", "Finding Your Representatives", PART,
          "By town and by district, and what the district numbering means.",
          BODY_REPS,
          [SRC_FIND_MEMBER, SRC_SOS]),

    topic("using-this-site", "Using This Site", PART,
          "What the tabs hold, what a timestamp claims and what it does not, "
          "how to follow a bill, and how to tell us we are wrong.",
          BODY_SITE,
          [SRC_CALENDARS, SRC_RSA]),
]


# THREE PAGES ARE HOW-TO GUIDES NOW (the person, 17 October 2026: "Certain
# pages currently on learn can move to how to like using this site, finding
# your representatives, how to testify or attend meetings, while the learn
# page should focus more on educational content while still linking to those
# other guides when applicable"). They are the How to Take Part group, the
# pages a reader opens to do something rather than to understand something.
# Their words stay here, with the other pages', so every check that reads
# civics.TOPICS still reads them; build_civics writes them at
# /guides/<slug>, lists them on the How-To Guides tab and leaves them out of
# Learn's own order, and build_pages.MOVED sends their old /learn/ addresses
# to the new ones, so nothing already indexed or bookmarked breaks.
HOW_TO = ("your-representatives", "testifying", "using-this-site")

# THE GUIDES A LEARN PAGE POINTS TO (17 October 2026, the same request):
# where a page explains something a reader may then want to do, it ends with
# the guides that do it. Slugs of guides.py's guides or of HOW_TO; a guide
# that is held back is left off the page that would have linked it.
GUIDES_FOR = {
    "general-court": ("your-representatives", "contact-your-legislators"),
    "how-a-bill-becomes-law": ("attend-a-hearing", "submit-testimony", "read-a-bill"),
    legislative_year.SLUG: ("attend-a-hearing", "submit-testimony"),
    "the-constitution": ("how-to-vote",),
    "state-agencies": ("public-records", "renew-drivers-license", "food-and-health-assistance"),
    "local-government": ("how-to-vote", "run-for-office"),
    "county-government": ("your-representatives",),
    "city-and-town-government": ("property-tax-abatement", "public-records", "run-for-office"),
}


# ---------------------------------------------------------------------------
# OTHER WAYS TO FOLLOW NEW HAMPSHIRE LEGISLATION (the person, 17 October
# 2026: official sources first, then the independent trackers, each with a
# neutral line on what it offers, nonpartisan ones only, no logos, no
# ranking and no word of endorsement). The Resources hub draws them at the
# foot of its Official Sources tab, the General Court's own site first.
#
# Each line says what the site offers in its own terms, read on its own
# front page on 17 October 2026, one page each. Who runs each, as far as the
# site says: Citizens Count's footer names the Live Free or Die Alliance, a
# 501(c)(3) nonprofit; FastDemocracy's page names FastDemocracy Corp. of
# St. Louis; LegiScan's own page asked for a bot check, which is not ours to
# pass, so its line rests on the description it publishes of itself ("the
# nation's first impartial real-time legislative tracking service", every
# bill in the fifty states and Congress, registration free); Citizen in a
# Republic and Granite Docket name no operator, and neither states a party,
# a cause or a mission beyond "independent". None states a party or a
# policy position, which is the test for being listed; the person was told
# of the two that name no operator. Listed in alphabetical order, which is
# no ranking.
# ---------------------------------------------------------------------------
FOLLOW_OFFICIAL = [
    (SRC_GENERAL_COURT[0], SRC_GENERAL_COURT[1],
     "The legislature&rsquo;s own site, which publishes every bill, the House and Senate "
     "calendars and journals, and each chamber&rsquo;s pages."),
]
FOLLOW_INDEPENDENT = [
    ("Citizen in a Republic", "https://citizeninarepublic.com/",
     "Reporting on the State House, with a briefing page for each bill, a tracker of bills "
     "being drafted, and a search of written testimony to the House."),
    ("Citizens Count", "https://www.citizenscount.org/",
     "Plain-language summaries of New Hampshire bills, legislators&rsquo; voting records and "
     "candidates&rsquo; positions, from the Live Free or Die Alliance, a nonprofit."),
    ("FastDemocracy", "https://fastdemocracy.com/states/nh",
     "Bill tracking with a daily or weekly email when the bills you follow move, free; paid "
     "plans add real-time alerts."),
    ("Granite Docket", "https://granitedocket.com/",
     "A guide to New Hampshire&rsquo;s public records, among them bills, committees and roll "
     "calls, free to read."),
    ("LegiScan", "https://legiscan.com/NH",
     "Every bill in the fifty state legislatures and Congress, with bill tracking for "
     "registered users."),
]
