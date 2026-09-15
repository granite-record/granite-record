# Granite Record — visual direction

Written for whoever does the polishing pass, human or model. This is the
hand-written companion to the mockups in `design/`. Like `HANDOFF.md` it holds
no counts: if you find yourself typing a number, it belongs in a check.

---

## What this pass is for

The site is correct and inconsistent. Every page was built when it was needed,
so each one invented its own spacing, its own way of marking the current item,
and its own use of the accent colour. Nothing here is a redesign. The goal is
that a reader moving from a bill to a committee to a Learn page cannot tell
which page was written first.

Do not change copy. Do not touch `narrative.py`. Do not restructure
`renderDetail` during this pass.

---

## Do these in order

**1. Find out where style lives.** No edits. List every file that sets a
colour, a typeface, a radius or a spacing value, and how many hardcoded values
each holds. Until this exists, any style fix lands in one of the places it
needed to land. This is rule 1 of `HANDOFF.md` applied to our own repository.

**2. Extract tokens, with no visual change intended.** Every hardcoded value
becomes a custom property in one file. The pages should render the same
afterwards; a visible difference is a bug in the extraction, not an
improvement. Verify before moving on.

**3. Add the check.** `preflight` fails if a colour literal appears outside the
token file. This is the only part of this pass that survives it. Everything
else is a tidy; this is what stops the tidy coming undone.

**4. Then the rules below, one at a time, each applied everywhere.** One rule
per commit. A page-by-page pass produces dialects; a rule-by-rule pass produces
unity.

---

## The rules

**The accent means interactive.** Links, the primary button, and the marker on
the current item. It does not mark status, it does not fill a pill, it does not
colour a heading, and it is never a diff colour. Status gets its own muted
hue. Additions and removals get two colours that mean only that.

**Current state is an underline. A control is outlined. Never both.** Today the
current nav item and the theme button are the same object, so a state looks
like a thing you can press. One treatment for "you are here" at every level of
navigation, site nav and bill tabs alike.

**The brand serif carries headings.** It currently appears once, inside an
image, which makes the wordmark look pasted on rather than like the page's
voice. Statute and Learn prose are read rather than scanned and take a serif
body; interface chrome stays sans.

**Chrome belongs to the page that uses it.** The term selector, the search
band, the sort control, the result count and the facet column act on a list. A
bill page, a Learn page and the homepage are not lists. Where a page keeps
search, it keeps the field and nothing else.

**A count that says N of N says nothing.** Show the result count only when a
filter narrows it.

**The brand sits left, at one size, on every page including the home page.**
Never centred, never duplicated in a hero beneath a masthead that already
carries it.

**Numbering is a claim.** Number a list only where the content is genuinely a
sequence. Where it is a grouping, use headings that say what the grouping is.

**Nothing is a black rectangle.** A video with no poster frame on a dark ground
reads as a failure. Either give it a frame or make it a line of text.

---

## The mockups

`design/` holds four reference pages: the home page, the header and navigation
states, the bill-text tab, and Learn. They are self-contained HTML; open them
in a browser. They are specifications for layout, hierarchy and the rules
above, not for copy. Any prose in them that is not quoted from the live site
was written to show the shape of a page and has not been checked. The figures
on the Learn specimen in particular are illustrative and must not ship.

---

## What this pass is not

The dead-zone crashes are a visual problem — a blank page is the worst visual
state the site has — but they are fixed by splitting `renderDetail`, which is
its own job with its own risk. Do it after the token extraction and before the
rules, so the rules land on the split code once rather than on both halves
twice.

Nothing here touches the archive, the file cap or term keys. Those gate what
the site can hold. This gates whether a stranger trusts it on sight.
