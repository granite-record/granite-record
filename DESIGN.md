# Granite Record — design brief

The standing brief for anything visual. Read this before changing CSS, markup
or colour. `CLAUDE.md` covers the data rules; this covers the page.

---

## What this is, and who reads it

A public record of the New Hampshire General Court. The audience is a resident
looking up a bill they heard about, a reporter checking what a committee did
on a particular day, and a legislator or staffer checking a vote. None of them
is a design enthusiast. All of them are trying to find one specific thing.

New Hampshire's House has 400 members, is one of the largest legislative
bodies in the English-speaking world, and pays $100 a year. There is very
little professional coverage of it. The site exists because the record is
public but almost unusable in its native form.

**The design job is legibility under scrutiny.** Someone may quote this site
in an argument, or in print. It should look like a record, not like a product.

---

## The visual floor, which is not negotiable

These are checked, not judged. A change that breaks one of them is wrong even
if it looks better.

- **Contrast meets WCAG AA** — 4.5:1 for body text, 3:1 for large text and for
  the boundary of any control. Measure it; do not eyeball it.
- **Colour never carries meaning alone.** The status chips are green, red,
  yellow, orange. Roughly one man in twelve cannot separate those reliably.
  Every one needs its word or a shape as well.
- **Keyboard focus is visible everywhere**, on every tab, card, jump button
  and link. Never `outline: none` without a replacement.
- **`prefers-reduced-motion` is respected.**
- **Semantics carry the structure.** Headings in order, landmarks, real
  `<button>` and `<a>` elements, `aria-expanded` on anything that opens.
- **Line length under 80 characters** for reading text.
- Everything works at 360px wide.

---

## The direction

**Spend the boldness in one place.** One element should be the memorable
thing; everything around it stays quiet. Currently the best candidate is the
progress indicator on the card — House, committee, Senate, Governor, filled,
checked or crossed. That is a real sequence, so a stepped treatment is earned
rather than decorative.

**Structure should encode information, not decorate.** A border, a rule or a
number is worth adding when it tells the reader something: that these two
things are different kinds, that this is third of five, that this claim is
weaker than that one. The site already does this in one place worth
protecting — *"the chair opens it at 1:08:43"* against *"estimated within ±5
min"* are different claims and are worded differently on purpose.

**The vernacular is the source of the palette.** Dockets, roll calls,
calendars, journals, the chamber. Granite. Not a generic civic-tech blue.

---

## The logo and the favicon — not settled, and nothing shipped

Still open as of 11 September, and **deliberately not built**. Permission is
being sought from the artist, so no asset is in the repository and no
`<link rel="icon">` has been added. What is on file is the intended
direction: a high-contrast ink drawing of the Old Man of the Mountain beside
"Granite Record" set in a high-contrast serif.

Three things follow from it that are worth writing down before anyone builds
the favicon:

- **The drawing and the favicon are two different problems.** It is an
  intricate ink mark; at 16px in a tab strip that resolves to a dark blob.
  The header logo can be the drawing; the favicon needs a simplified
  silhouette derived from it, drawn at 16px and checked at 16px.
- **It has to work on both grounds.** The mark is black on white, and the
  page is now `#171B1C` in dark mode. Either a light variant, or a mark that
  carries its own ground.
- **The wordmark is a serif and the nav brand is not.** The brand is
  currently Public Sans 600 at 16px. If the wordmark ships as drawn, the
  brand should move to `--serif` to match it — one decision, made when the
  logo lands, not before.

**`site/` is in `.gitignore`.** A favicon dropped there works until the next
build and then disappears, so it cannot simply be committed as a file: it
needs a build step to write it and a `<link>` in three places — the `shell()`
head in `build_pages.py`, `bills.html`, and `shell.py`. A `/favicon.ico` at
the site root is the exception that needs no markup, because browsers ask for
that address on their own.

---

## Defaults to avoid

These are the current tells of a generated page. Each is legitimate for some
brief and a default for none, and none of them was chosen for this one.

- Warm cream background (near `#F4F1EA`), high-contrast serif display, and a
  terracotta accent near `#D97757`.
- Near-black background with a single acid-green or vermilion accent.
- Identical rounded cards with one border-radius on everything regardless of
  hierarchy, the same soft grey shadow under each, gradient washes as
  decoration.
- Tracked-out ALL-CAPS eyebrow labels above headings.
- Meta strings joined with middle dots — `A · B · C`.
- `WORD — fragment` labels with a spaced em dash.
- Tinted near-black (`#0B0B0B`, `#111`) standing in for black.
- A monospace face for small data labels.
- `→` appended to link and button text.
- Fade-and-slide-up entrances on every section, hover transitions on every
  card. Motion answering a person's action is welcome; ambient motion is not.

If a proposal contains one of these, either justify it against this brief in a
sentence or replace it.

---

## Dark mode

Added 11 September. Both schemes are defined in `app.css`, the light palette
in `:root` and the dark one in a `@media (prefers-color-scheme: dark)` block
directly under it, ending at a `/* PALETTE END */` marker. **Everything above
that marker is the palette**, and `build_pages.py` reads the whole of it into
`style.css` — so the home page, the legislator index, About and 404 get both
schemes from the same definition that the record pages get. Before the marker
existed that reader stopped at the first `}`, which with a second block under
it would have shipped half a scheme: white cards that never went dark, on
four of the pages a reader is most likely to arrive on.

**Every token is redefined in the dark block. None is inherited.** A
half-defined scheme is how a white chip ends up with white text on it.

It is measured with the same arithmetic `preflight` uses — 4.5:1 for text,
3:1 for the boundary of a control or a graphic. All 34 pairs pass and the
tightest sits 1.07× its threshold, where the light palette has one pair
exactly on it (`--edge` on `--wash`, 3.00:1).

Two numbers were copied across deliberately rather than left where they fell.
The note at the top of `app.css` records that the page ground was darkened on
purpose to put **1.20:1** between a card and the paper behind it, 1.08:1
being below the level at which most people see an edge at all. Dark mode
hands that straight back if the ground is chosen by eye: the first candidate
here measured 1.13:1. The shipped pair is 1.24:1, and `--rule-2` is set to
2.03:1 on a card against the light palette's 1.99:1. **A card has to look as
much like an object in the dark as in the light.**

Granite in both. The dark ground is a cool grey with the blue left in it, not
a tinted near-black, and pine is the same colour lifted to where it can be
read rather than swapped for a brighter hue — the "near-black background with
a single acid accent" in the list above is the thing being avoided.

Three tokens exist because of dark mode and are worth knowing about:

- `--on-pine` — the ink that goes *on* a solid pine block (the filter badge,
  the skip link, the home page's Search button, a selected ward). It was
  `#fff` in all four, which is right on the light palette and wrong on the
  dark one, where pine is the light colour. "White" was never the claim;
  "readable on pine" was.
- `--shadow` — the lift under an opened card. A dark shadow says nothing on a
  dark ground.
- `--wait` / `--wait-bg` — the home page's session box between sittings.
  These were literals in `build_pages.py`, the last pair of colours outside
  the palette and so the last pair nothing could measure or re-theme.

`color-scheme` is set in both blocks, so scrollbars, select menus and the
search field's own furniture follow the page instead of staying light
against it.

---

## How a change here gets checked

Screenshots at 360, 768 and 1440 are the floor, not the whole job: **a colour
pair that fails is invisible in a screenshot.** The pass on 11 September read
the *rendered* colours off every text element — walking up for the first
non-transparent background, compositing alpha — and compared each against its
own WCAG threshold by font size. 13 page types × 3 widths × 2 schemes, about
26,700 text elements.

That is what found the one real contrast defect in the existing palette:
**the passage rail's unreached stop had its label in `--edge`**, which is the
token specified for the outline of a control and carries a 3:1 requirement.
As 12px words it needs 4.5:1 and had 3.91:1 on white and 3.74:1 on a dark
card. `preflight`'s palette check could not see it, and is not wrong to: it
measures `--edge` against 3:1 because nothing was supposed to set type in it.
The rail's circle already says whether the bill got there — a check, a cross,
a ring or an empty outline — so the state was never the colour's job.

**The lesson worth keeping: check the tokens *and* check what the page
actually drew.** The first sweep of the day reported everything passing while
half the pages were being served a cached copy of the old stylesheet. A pass
measured against the wrong bytes is the "silence is not success" rule wearing
a green tick.

Two checks belong in `preflight` and are not there yet, because that file was
out of scope for this pass:

1. The dark palette's pairs. The light ones are checked; the dark ones are
   measured only by hand.
2. `documentElement.scrollWidth` against `clientWidth` at 360, 768 and 1440.
   Every legislator page carrying a two-thirds vote scrolled sideways at
   every width above 720px and nothing caught it — see below.

---

## Width: the measure belongs to the box, and a table is not prose

This is the rule the top of `app.css` sets out, and two things were breaking
it in ways worth naming, because both are the shape the complaint always
takes — *a narrow column of text inside a much wider painted box*.

- **The home page's session box** was a 772px tinted panel with its
  paragraphs capped at 476px: 296px of empty box beside every line. The cap
  moved to the box, which is the thing with an edge. 548px rather than the
  560px `--measure`, because the text inside it is 14px and 560 would run to
  85 characters; 548 leaves 78.
- **A bill's docket history** was being held to the prose measure. It is not
  prose — it is a date and the General Court's own record line, `21 CAL DAY
  EXTENSION GRANTED (NEW DUE DATE: 03/03/93); HJ22,P430` — and `app.css`
  already says a table fills its pane. It is built from `<ul>`/`<li>` rather
  than `<table>`, which is the only reason it was caught by the default.

**Still open, and it is a layout question rather than a CSS one.** On a bill
page at 1440 the card is 1132px and the pane 1094px, and the prose inside it
is 560px because 560px is 76 characters and the floor above is 80. Those two
facts cannot both be satisfied by a width: the prose cannot fill 1094px, so
**the box should not be 1094px of single column**. The answer is either a
narrower column on the Summary tab or a second column carrying the
structured material — the status panel, the documents, the citations — beside
the prose. Both change markup that `build_site_v2.py` owns, so neither was
done here.

---

## One left edge

The nav, the page and the footer were three different columns: at 1440 on the
home page the brand began at 130px, the heading under it at 310px, and the
footer — a measure-width column centred in the *window* — at 432px. The
footer was the worst of it, because its text is identical on every page of the
site and it was a different width in each stylesheet (476px in one, 560px in
the other).

The measure was never the problem; the alignment was. The band keeps the
page's gutter (`padding: 22px max(0px, calc(50% - 590px))`, 590px being half
the 1180px the nav and `.shell` share) and the column inside it starts where
the page starts. `display:grid` was the first attempt and is worth recording
as a trap: it promotes every *child* to a grid item, so "How this is made"
and the full stop after it each took a row of their own.

One thing stayed deliberately out of line. `/learn/`, the town pages and
`/data` are centred reading columns, and DESIGN.md calls the civics section
the one place where the reading measure *is* the page. They now sit centred
under a left-aligned nav and footer, which is either correct or the last
inconsistency, and it is a preference rather than a defect — so it was left
for a person to call.

---

## The header tabs

Seven sections, and the only thing that said which one you were looking at
was a 2px pine rule under a 14px grey word. The six beside it were the same
word in the same grey, so "where am I" took a second look every time. On a
phone it was worse than quiet: the tap-target minimum makes each anchor 44px
tall around a 17px word, so `box-shadow: 0 2px 0` drew the rule 25px *below*
the label, and a second rule existed in both stylesheets to turn it into a
text underline instead.

Now a section is a box: its own padding, its own hover (`--wash`), and the
current one filled `--pine-soft`, outlined `--pine`, labelled `--pine` at
600. The fill holds at any box height, so the phone needs no special rule at
all and the underline workaround is gone. It is deliberately **not** solid
pine — this site keeps that for "do this" (the search button, the feedback
block), and a tab is where you are, not something to press. 9.34:1 in light
and 5.70:1 in dark for the label; the border is 10.92:1 and 6.60:1 against
the band, so the shape survives on a bad screen in sunlight.

The links gained a wrapper, `.navtabs`, which is the whole reason the layout
works: the strip wraps as one unit instead of the links wrapping through the
middle of the row. One row needs **783px** — brand 113, strip 529, control
57, two 18px gaps, 48px gutter, measured in the browser rather than added up
from the stylesheet — so below 860px the row splits, identity and control on
the first line and the seven sections beneath. 860 is not a new number: the
facet sidebar, the footer, `.ctwo` and the legislator finder already give up
a column there.

| width | nav height | before |
|---|---|---|
| 1440 | 55px, one row | 56px |
| 768 | 88px, two zones | 56px |
| 360 | 159px, two zones | 132px |

The phone costs 27px more chrome than it did. That is the trade and it was
made on purpose: 27px once, against a second look on every page.

**Two traps worth recording.** The nav had been kept by hand in both
stylesheets, like the palette before it, so it moved into app.css's SHARED
region and `build_pages.py` reads it — and the comment left behind in
`build_pages.py` explaining where it went *named the substitution slot*. The
build does not know it is inside a comment: the whole shared region was
pasted into the middle of it, and because a CSS comment does not nest, the
first `*/` in the pasted region ended the comment and the rest was parsed as
live CSS. Nothing errored; `style.css` simply had two copies of everything
and a line of garbage. Grepping the built file for one distinctive rule is
what found it.

The second is the same lesson the rest of this file keeps learning. The 783px
figure started life as 872px, added up from label widths in the stylesheet,
which put the breakpoint 96px too early and would have stacked the nav on
every 800px laptop for no reason. Measuring it took one function call.

---

## The front page, in three columns

Asked for in one sentence: "three columns, center column, upper left status
banner, below the status banner is the coming up sessions readout, on the top
right side should be a town and legislator search bar, and below that the most
recent house and senate sessions stacked on top of each other."

So: **left** is where the General Court is and what is coming up; **middle**
is the site itself — its name, its search box, its five numbers and the three
ways in; **right** is finding your own legislators and the two chambers' last
floor sessions. Latest activity, the composition charts and the feeds sit
below all three at full width.

Only above **1180px**, which is where the 1180px column can give 300 and 290
to the sides and still leave the middle the widest of the three. Below that
the page is the single column it has always been, in document order.

**The middle column is written first in the markup**, and the grid places it
second. A reader on a screen reader should meet the page's own name and its
search box before a fortnight of hearings, and a reader on a keyboard should
not have to tab past the calendar to reach the search field. The cost is that
the second tab stop is the left column rather than where the eye starts. Each
column is a labelled region and self-contained, so that reads as three panels
in an order — which is what they are. Burying the h1 under the calendar to
make the tab order left-to-right would be the worse trade, and it is worth
saying out loud that this is a trade rather than a solution.

The columns are 1130, 790 and 680 tall, because a fortnight of hearings is
longer than a search box. They end ragged, which is what columns do; the rule
under them says the columns have ended and a full-width band has begun, so
the 340px of white to the right of the calendar reads as layout rather than
as something that failed to load.

### The finder is a form, not a script

The box top right is two plain `<form method="get" action="legislators.html">`
rows, which produce exactly the `?town=` and `?q=` the legislators page now
reads. It works with JavaScript off, the browser remembers what was typed,
and the Enter key needs no handler. The type-ahead over all 259 towns stays
on the legislators page, where the data it needs is already being fetched.

An exact town name opens that town; anything else is left in the box as a
filter and the ranked list does the rest, because "Hampton" is three real
towns and choosing one for the reader would be a guess. The town has to be
set *before* the list is drawn — `list()` is what marks the chosen row — and
getting that order wrong the first time left Dover's seats on the page with
nothing in the list looking chosen.

### Two things the measurement found

**"2,303,047" was being clipped.** `.statgrid` was `auto-fit` with a 120px
floor and `overflow: hidden`, and the number is 132px of 24px type: in a
143px cell with 32px of padding it did not fit, so on a 768px screen the last
stat read "2,303,0". It is now flex-wrap with a **164px** floor, measured,
which also fixes what grid does with a wrapped row — five cells in a
four-column grid leave one cell of content and three of bare `--rule`
background, a hole. Flex items grow into the space, so the last row is always
full at every width. The entry cards had the same fault and the same fix.

**Placeholder text was 3.04:1 in dark.** Nothing in either stylesheet had
ever set a `::placeholder` colour, so every search box on the site rendered
its instruction in the browser's own `#757575`: 4.61:1 on white, and 3.04:1
on the dark card. It is text, it is the only instruction those boxes carry,
and it had been below the line on every page for as long as dark mode
existed. `--ink-2` is 7.74:1 and 6.32:1, and `preflight` now names the rule
that has to exist, because a colour a browser picks is invisible to a check
that reads the tokens this file declares.

A note on measuring text, since it wasted twenty minutes: a canvas in the
*harness* page measured "Name or committee" at 145px in a 151px box, and it
was clipped on screen anyway — the harness does not load Public Sans, so
`measureText` had been using a narrower fallback. The reliable way is to make
the element measure itself: put the placeholder in as the field's `value` and
read `scrollWidth - clientWidth`, which uses the same font, kerning and
padding the placeholder will.

---

## A level is not a size

Three sets of pages skipped a heading level, and all three did it for the same
reason: the level had been chosen to get the right *look*.

`app.css` styled its section headings as `.stg h3`, `.bttext h3`, `.mlist h3`,
`.facts h3`, `.rephead h3` — so every section of every tab on a record page
was written at level 3, because that is what the stylesheet drew. A bill page
went from its hidden `h1` to an `h3` with no level 2 anywhere on it, across
sixteen sections. The civics pages did the same one level down: the flow
diagram's phase names were `h3` wherever the diagram sat, and the hub's "If
you read one" was an `h4` because that is what the label looked like.

The fix is to separate the two. Those selectors are now `:is(h2,h3)`, which
has the same specificity as the bare type selector, so a heading can move up
a level without moving a pixel; `flow_diagram` takes the level it is written
at, because that depends on where the diagram sits and not on the diagram.
Where a component is used at two depths — the `.shows` box is the first thing
after the hub's `h1` and sits under a section on a topic page — the rule
matches both and the level follows the page.

Measured rather than looked at: every heading on two bill pages and a
committee page was captured before and after with its tag, class, text,
font-size, weight, colour, transform, letter-spacing and margins. **38
headings moved from `h3` to `h2` and not one of the other properties changed
on any of them.** The same capture is what proved the first attempt was
meaningless: the record pages in `site/` still asked for the previous
`app.js?v=`, so the browser served what it already had and the comparison
came back identical because *nothing had been reloaded*. A cached asset does
not announce itself.

Two things are deliberately still at `h3`. "The bill" and "How it got here"
sit inside the `.btsec` section that now carries the `h2`, which is correct
nesting. The member lists inside a roll call's expansion have no section
heading to sit under, because the Votes pane gives each vote a `<section>`
and no heading — fixing that means giving every vote's question a heading,
which is a markup change to that pane rather than a level change, and it is
recorded here instead of half-done.

---

## Diagrams

The first one is on *How a bill becomes law*, and it is **not an image**. It
is an ordered list of ordered lists — four phases, and the stages inside each
— so a screen reader reads it as the sequence it is, a reader with no CSS
gets the same sequence, and there is nothing to fail to load or to fall out
of step with the prose beside it. SVG was the obvious choice and the wrong
one: a four-lane flow that has to become one column at 360px is a layout
problem, and CSS already solves layout. The only thing actually drawn is the
connector between phases.

**The structure carries the argument**, which is this brief's rule. The
phases are the two chambers and the two ends; the steps are in the order they
happen; and every stage a bill can die at says so and is marked, as is every
stage a member of the public may speak at. That last part is the whole point.
A reader arrives thinking a bill moves along a pipeline, and what they should
leave with is a course with exits almost everywhere — seven of the twelve
stages can end it.

It stacks below 1100px and only goes four-across above, because four
readable columns need about 230px each and the civics measure is 560px: the
first attempt squeezed them to 115px, which is a column of broken words
rather than a diagram. Above 1100px it breaks out of the measure by 230px a
side — the wide thing on a prose page that the note on `.civics` anticipated
and left `.wide` for, which was never actually written.

---

## One class name is one component

Third occurrence, so it belongs in the brief rather than in a comment. The
diagram's "can die here" state was first called `.stop`, which is the
**passage rail's** class, where `.stop b` is an absolutely positioned 15px
circle with `color: transparent` — so every "Executive session" and "Floor
vote" rendered as invisible words inside a small grey disc. Nothing errored.
The contrast sweep found it at **1:1**, which is the signature of text the
same colour as its background.

The file already records the same mistake twice: `.ctitle` was both a card
title and a bill title inside a committee day, and `.p-R` was both a tinted
chip and a solid bar segment. **A new component gets its own prefix**
(`.cal*` for the calendar, `.off*` for the officials rows, `.step`/`.phase`
for the diagram). A check for this would be worth having and does not exist;
what caught all three was reading the rendered page rather than the
stylesheet.

---

## Typography

One family, or two that are clearly distinct. Set a type scale deliberately
rather than accepting a framework's. Give serif body text more line-height
than sans. Do not accent a single word in a heading with italic, bold or
colour.

---

## Copy is design content

Words appear to make the page easier to use. Sentence case. Active voice. A
button says what happens: "Open the full page", not "Submit". The same action
keeps the same name everywhere. Empty states say what to do next; errors say
what went wrong and how to fix it, without apologising and without being
vague.

Name things as a reader would: "Hearings and video", not "Proceedings index".

---

## How to work on this

**Look at what you changed.** Serve the built site and screenshot it:

```
cd site && python3 -m http.server 8000
```

A change that has not been looked at is not finished. Screenshot at 360px,
768px and 1440px.

**Plan before editing.** Write the palette, type scale and layout intent
first, check it against the "defaults to avoid" list above, then build. This
is the same discipline as reading a transcript before writing a parser, and it
exists for the same reason.

**One component at a time**, committed separately, so a regression is one
`git checkout` away.

**Before finishing, remove one thing.** If nothing can go, the design is
probably not finished being simplified.
