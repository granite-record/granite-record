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
protecting — a boundary the chair stated against one the model inferred are
different claims and are worded differently on purpose: a stated boundary is
shown plainly, an inferred one carries the single word *approximate*. The
earlier wording, *"estimated within ±5 min"*, was taken out as methodology in
the reader's way.

**A third claim of that kind: not knowing which
recording.** Where a committee was filmed on the day of a sitting and more
than one of its recordings could be the one, the page says so in those words
and offers all of them — "nothing in the record says which one took this bill
up, and this site will not pick one". 317 of the site's 104,756 stations are
in that state, mostly Finance, whose divisions stream separately. Nothing
ranks them and nothing calls one likelier; they are listed in the order the
matcher found them and numbered rather than titled. It is the same rule one
level up from the boundary: *approximate* claims the tape is known and the
minute is not, and this claims the opposite, so it cannot borrow that word.

**The vernacular is the source of the palette.** Dockets, roll calls,
calendars, journals, the chamber. Granite. Not a generic civic-tech blue.

---

## The logo and the favicon

Three things about this that are worth knowing before touching it.

**The header mark and the favicon are two different problems.** An intricate
mark resolves to a dark blob at 16px in a tab strip. The favicon does not yet
answer that: `icon.svg`, the first `<link rel="icon">` on every page, is the
header mark's own path out of `brand/old-man.svg` on a `#111514` tile, and the
PNG and `.ico` fallbacks are downscales of the 1000×1000 `brand/icon.png`.
Nothing is drawn at 16px and nothing checks it at 16px. A simplified
silhouette, drawn at that size and checked at it, is still the thing to do.

**A mark has to work on both grounds** — the page is `#171B1C` in dark mode.
Both are handled without a light variant: the profile ships as `mark.svg` and
the home page's heading as `lockup.png`, each used as a CSS mask over
`currentColor`, so one file is right in either scheme.

**`site/` is in `.gitignore`**, so a favicon dropped there works until the next
build and then disappears. It needs a build step. `build_brand.py` derives
`icon.svg`, `icon-32.png`, `favicon.ico`, `icon-180.png` and a manifest from
the checked-in originals in `brand/` into `assets/`, and `build_pages.py`
copies `assets/` into `site/` beside the pages, so nothing has to survive in
the gitignored tree. `build_brand.py`'s own header says the logo is temporary
and that replacing it is meant to be one command rather than an archaeology
exercise.

The `<link>` block is needed in two places, not three — `shell()` in
`build_pages.py` and `bills.html` — because `shell.py` substitutes into
`bills.html`, so every record page inherits it. A `/favicon.ico` at the site
root is the exception that needs no markup at all, because browsers ask for
that address on their own.

On the wordmark: the home page's `h1` *is* the drawn lockup with the slogan
under it, and the nav brand stayed Public Sans 600 at 16px with the 15×24
profile beside it, rather than moving to `--serif` to match the lockup.

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

**Two entries on this list are wanted, on instruction, and are not defects.**
The tracked-out ALL-CAPS label is deliberate — about three dozen rules in
`app.css` set `text-transform:uppercase` — and the arrow appended to link text
stays, as `&#8599;`, where the link leaves the site. The home page's large
centred logo and the line under it are wanted too, but nothing on this list
would have taken them out: the rule they overrule is `design/BRIEF.md`'s
"never centred, never duplicated in a hero". This brief informs what gets
built; it does not overrule a decision already taken.

---

## Dark mode

Both schemes are defined in `app.css`, the light palette
in `:root` and the dark one in a `@media (prefers-color-scheme: dark)` block
directly under it, ending at a `/* PALETTE END */` marker. **Everything above
that marker is the palette**, and `build_pages.py` reads the whole of it into
`style.css` — so the home page, the legislator index, About and 404 get both
schemes from the same definition that the record pages get. Before the marker
existed that reader stopped at the first `}`, which with a second block under
it would have shipped half a scheme: white cards that never went dark, on
four of the pages a reader is most likely to arrive on.

**A reader can choose, so the palette is written three
times.** The control in the nav sets `data-theme`, and CSS cannot put one
declaration block behind both a media query and a selector: light in `:root`,
the system's dark in `@media (prefers-color-scheme: dark)` scoped
`:root:not([data-theme="light"])` so an explicit choice of light beats a dark
phone, and the chosen dark again in `:root[data-theme="dark"]`. The two dark
blocks are the same tokens twice — `app.css` sets out at `/* DARK:CHOSEN */`
why every alternative was worse — and `preflight` fails if they ever stop
being identical, so drift is a failed build rather than a page that is subtly
the wrong colour by one of the two routes to it.

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
  These were literals in `build_pages.py`, the last pair outside the palette
  that the theme had to change and so the last pair nothing could re-theme.
  Four bare colours outlived them — the player's `#000` letterboxing and the
  three that make its placeholder look like a still, named on 16 September.
  Those are the same in both schemes on purpose: a video is somebody else's
  pixels, and the black around it is black on a light page too.

`color-scheme` is set in both blocks, so scrollbars, select menus and the
search field's own furniture follow the page instead of staying light
against it.

---

## The version query, gone

Every page named its stylesheet as `app.css?v=1a2b3c4d`, a hash of the bytes
of `app.js` and `app.css` together. It was there for a real reason, and the
reason is still true: measured on the live site with `curl -sI`, Cloudflare
Pages hands out `app.css` as `public, max-age=14400, must-revalidate` — four
hours in which a browser may run yesterday's script against today's page.

What it cost was not visible from the stylesheet. The hash lives *inside the
HTML*, so one changed byte of `app.css` rewrites the asset URL in all 34,000
record pages, and every one of them becomes a file Cloudflare has never seen.
The publish of 12 September had **35,347 of 55,353 files missing** for that
reason and no other — the data had not changed since the build before it —
and wrangler sorts missing files largest-first into three concurrent 40 MB
buckets, so the first three requests of the deploy were the fat ones. Those
three went up fine — 55, 236 and 177 files, in 12s, 12s and 23s. It was every
request after them that hung, each until undici's 300-second default headers
timeout fired at ~301s, and five upload errors anywhere abort a deploy. Two
publishes died that way, both after uploading exactly those 468 real files and
nothing more.

The same `curl` that found the four hours found the fix: Pages already serves
HTML and JSON as `public, max-age=0, must-revalidate` — kept, but revalidated
before reuse, never stale. So `site/_headers` says the same thing about the
three asset files, and the pages name them plainly:

    /app.js
      Cache-Control: public, max-age=0, must-revalidate

The trade, stated plainly: two conditional requests per page view, answered
`304` from the edge in a couple of hundred bytes, on a page that already
makes several. What it buys is that **a page's bytes change when the page
changes and at no other time** — a stylesheet tweak uploads three files
instead of a gigabyte, and the record pages, which are most of the site,
move only when their own record moves. (`python3 check_site.py` prints the
size and the file count at the end of a build, and warns above 90,000 against
Cloudflare Pages Pro's 100,000. The freshness rule covers `find.js`,
`home.json` and `find.json` too, added when the home page's built HTML said
39 hearings and its script, reading a cached `home.json`, said 4.)

Two things to know if this ever looks wrong. It cannot be checked locally:
the header comes from Pages, so the check is `curl -sI
https://graniterecord.org/app.css` after a deploy, and if it does not say
`max-age=0` then Pages is ignoring the file and the query should come back —
one `git revert`. And the first publish after the change is still a big one,
because removing the query from 34,000 pages changes 34,000 pages; the
saving starts with the publish after that.

---

## How a change here gets checked

Screenshots at 360, 768 and 1440 are the floor, not the whole job: **a colour
pair that fails is invisible in a screenshot.** The sweep that catches those
reads the *rendered* colours off every text element — walking up for the first
non-transparent background, compositing alpha — and compares each against its
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
actually drew.** The first sweep reported everything passing while half the
pages were being served a cached copy of the old stylesheet. A pass measured
against the wrong bytes is the "silence is not success" rule wearing a green
tick.

Two checks belonged in `preflight`:

1. The dark palette's pairs. **Done**: the palette check measures both
   schemes — `preflight --code --verbose` prints "42 pairs across both
   schemes" — and fails as well if the dark block leaves out a token the
   light one defines, which is the failure that matters. A missing token is
   not a slightly wrong colour, it is the light value surviving into the dark
   page.
2. `documentElement.scrollWidth` against `clientWidth` at 360, 768 and 1440.
   Every legislator page carrying a two-thirds vote scrolled sideways at
   every width above 720px and nothing caught it. **Still not there.**

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

**The hardest case was a layout question rather than a CSS one.** On a bill
page at 1440 the card is 1132px and the pane 1094px, and the prose inside it is
560px because 560px is 76 characters and the floor above is 80. Those two facts
cannot both be satisfied by a width: the prose cannot fill 1094px, so **the box
should not be 1094px of single column.**

**The answer was a second column.** Above 1100px the
"On the record" panel floats right at 488px with 46px of gutter and the prose
keeps `--measure`: 560 + 46 + 488 is the 1094px pane exactly. Grid was the
obvious tool and was measured out of it — a grid row is as tall as its
tallest item, so the row holding the panel gave a short analysis beside it a
274px dead tail, and no arrangement of spans fixed every bill. A float is out
of flow and therefore cannot push in-flow content down, which is the property
actually wanted. One thing was settled against the mechanism rather than by
it: a floated box has to come first in the DOM to sit at the top of the pane,
and a bill opens with the writing instead — the note, then the General
Court's own analysis — so the panel starts below the prose and sits beside
the story. Below 1100px the pane is one flex column and the panel goes back
under the analysis, which is where a reader on a phone wants it.

---

## One left edge

The nav, the page and the footer were three different columns: at 1440 the
brand began at 130px and the heading under it at 310px on the home page, and
the footer — a column centred in the *window* rather than aligned to the
page — began at 432px on a record page, where it takes the 560px `--measure`.
The footer was the worst of it, because its text is identical on every page of
the site and it was a different width in each stylesheet (476px in one, 560px
in the other).

The measure was never the problem; the alignment was. The band keeps the
page's gutter (`padding: var(--sp-7) max(0px, calc(50% - 590px))`, 590px
being half the 1180px the nav and `.shell` share) and the column inside it
starts where the page starts. `display:grid` was the first attempt and is
worth recording as a trap: it promotes every *child* to a grid item, so "How
this is made" and the full stop after it each took a row of their own.

**And aligning it was half the job.** Left-aligning a 560px column in an
1180px band put its first word under the page's first word and left 620px of
empty footer beside it — the same narrow-measure-in-a-wide-box this file
keeps answering, one band lower. So it is two columns, because the footer is
three short things and not one: what this is, how to report an error, and
where the bulk data is. Multi-column, not grid or flex,
for exactly the trap above — those promote every child to an item, and "How
this is made" is a direct child. One column again below 860px, the width the
facet rail collapses at.

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
middle of the row. Below the split, identity and control take the first line
and the sections take the next.

**Then there were four.** Data and About are pages for somebody who already
knows what they want and both had carried a footer link since the footer was
written, so they lost their tabs and kept their links. Home lost its tab
because the mark and the wordmark beside it are the way home on every site a
reader uses — here they simply were not a link. They are now, with
`aria-current` on the brand at home so a screen reader still hears which page
it is, and the chip that marks a tab scoped to `.navtabs` so the site's name
does not render as one.

Four tabs need **635px** on one row — brand 163 with its mark, strip 331,
control 57, two 18px gaps, 48px gutter — against 783px for seven. So the
split moved from 860 to **720**, which is the width the rest of this site
already breaks at: 86px of slack, and one breakpoint for the nav instead of
two.

| width | now | seven tabs | before all of it |
|---|---|---|---|
| 1440 | 55px, one row | 55px, one row | 56px |
| 768 | 55px, one row | 88px, two zones | 56px |
| 360 | 111px, two zones, tabs on one row | 159px, two rows of tabs | 132px |
| 320 | 159px, tabs wrap | — | — |

The phone ended up 21px *cheaper* than it started, with the current section
unmistakable. Worth recording that the thing which paid for it was cutting
three tabs rather than any cleverness in the CSS: the trade on offer before
that was 27px *more* chrome.

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
figure started life as 872px, added up from label widths in the stylesheet —
89px too high, which would have pushed the split from 860 up to somewhere near
950 and stacked the nav on every 900px window for no reason. Measuring it took
one function call.

---

## The front page, in three columns

**Left** is where the General Court is and what is coming up; **middle**
is the site itself — its name, its search box, its five numbers and the three
ways in; **right** is finding your own legislators and the two chambers' last
floor sessions. Latest activity, the composition charts and the feeds sit
below all three at full width.

**Two of those have since moved, and the middle column is shorter for it.**
The five counts came off: they sat between the search box and the three cards
that are the actual way in, and nobody arrives to be told how many bills
exist. The scale of the record is
said once now, in the footer's link to the data. `.statgrid` and its measured
164px floor are still in `app.css` and no page draws them any more, so the
measurement below is the record of why that floor is what it is rather than a
rule in force. The chambers and the vacant seats went with them, to the
legislators page, where somebody looking for who holds a seat already is;
what sits below the columns is Latest activity and the executive branch, and
the feeds are two `<link rel="alternate">` in the head rather than a block on
the page.

Only above **1180px**, which is where the 1180px column can give 300 and 290
to the sides and still leave the middle the widest of the three. Below that
the page is the single column it has always been, in document order.

**The middle column is written first in the markup**, and the grid places it
second. A reader on a screen reader should meet the page's own name and its
search box before a fortnight of hearings, and a reader on a keyboard should
not have to tab past the calendar to reach the search field. The cost is that
the second tab stop is the left column rather than where the eye starts. The
two side columns are labelled regions — an `aria-label` on a `<section>` each
— and the middle is the opening content of `<main>` rather than a region of
its own, so a landmark list reads main and then the two named panels, in the
order the markup sets. Each column is self-contained. Burying the h1 under the
calendar to make the tab order left-to-right would be the worse trade, and it
is worth saying out loud that this is a trade rather than a solution.

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
filter and the ranked list does the rest, because "Hampton" is five real
towns — Hampton, Hampton Falls, New Hampton, North Hampton and South
Hampton — and choosing one for the reader would be a guess. The town has to be
set *before* the list is drawn — `list()` is what marks the chosen row — and
getting that order wrong the first time left Dover's seats on the page with
nothing in the list looking chosen.

### Two things the measurement found

**"2,303,047" was being clipped.** `.statgrid` was `auto-fit` with a 120px
floor and `overflow: hidden`, and the number is 132px of 24px type: in a
143px cell with 32px of padding it did not fit, so on a 768px screen the last
stat read "2,303,0". It is now flex-wrap with a **164px** floor, measured,
which also fixes what grid does with a wrapped row — five cells in the two
columns the 720px breakpoint forced, or in the three `auto-fit` gave the 482px
middle column, leave a last row of one cell of content beside one of bare
`--rule` background, a hole. Flex items grow into the space, so the last row
is always full at every width. The entry cards had the same fault and the same
fix.

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

## The town page, and one way in

Two decisions worth keeping, both from the same instruction: a reader who
opens a page called "who represents me" is looking up their own government,
not reading an index of what this site covers.

**The order is the content.** The page opened with the General Court, because
the General Court is what the rest of the site is about. It now runs the way
a resident holds it — Executive Branch, Federal Delegation, Legislative
Branch, Town Officials, senator before representative — and what they came
for most often is first of all: "How to Vote (Next Election: November 3rd)",
with where they vote, the town website and the clerk to ring. The heading
says "Next Election" only while the date is ahead of the build and "Election
on file" after it, because a page still promising "next" in December is wrong
about the one thing it was opened for.

Eight towns are one page here and several voting wards on the Secretary of
State's list — Berlin, Derry, Farmington, Goffstown, Hudson, Merrimack, Salem
and Walpole — so there is no ward for the page to be about. Four addresses in
a row was the first answer and it is three too many: the count goes on the
line and the addresses go behind it. That is the third place on this site
using the same shape — the chapter list on a bill, the filter panel on a
phone, the polling places here — and it is worth naming as the shape: **the
answer on the line, the rest on request.**

**The finder is a way in, not a destination.** Picking a town used to draw
that town's seats inside the legislators page — which is what a town page
does, better, and has done since it was written. A click now goes to the
town's own page instead, and about half of that script went away with the
in-place rendering: `wardsOf`, `houseOf`, `reps`, `senators`, `people` and
`show` all existed to draw something a page already draws.

**And nothing else about it changed, on instruction.** The first attempt at
this replaced the browsable list with a type-ahead that listed every ward as
its own match — twelve rows in front of somebody who typed "manch". Only the
destination of a click was meant to change; the list itself was wanted as it
was. So the list is back: all 259 towns, scrollable, ranked as you
type, one row per town with its ward count, and the wards appearing under a
town when you pick it. A town without wards is a link; a town with them is a
button that opens them, because there is no page for Concord -- only Concord
Ward 1 through 10 -- so the wards are the links, as the chips the live page
put in a card below the list. The one field also matches members, because a
name typed into it has to go somewhere.

Three labels came off those rows: "Town" on a row in a list of towns, "Go" on
a link, and "who represents it" on every one of them, on a page whose heading
already asks the question. What is left is the name, and the ward count where
a name is not the whole answer.

The lesson is the one this file keeps recording in other forms: an
instruction to change where a click goes is not an instruction to redesign
the thing that was clicked. The roster below it does fold by county now, shut
until asked, because 406 members under ten open headings is not a list
anybody reads in order — and that was asked for.

**A way to the next ward.** Dover has six wards and eleven
representatives, and a resident of ward 2 is shown ward 2 — which is the
whole point of these pages, and it left the next question with nowhere to go:
*and who represents the rest of the town?* The only route was back to the
finder, to pick Dover again.

So a warded town's page carries a picker under its heading, reading **Ward 2
· 6 wards in Dover ▸**, which opens to all six as links with the current one
marked and not a link. A control that offers you where you already are is a
control that does nothing once.

A disclosure, not a `<select>`: a select needs script to navigate, and hands
a screen reader a list of options with no addresses. These are five links that
work with the keyboard, survive with JavaScript off, and are the fifth place
on this site with the same shape — the chapter list on a bill, the filter
panel on a phone, the polling places on a town page, the ward chips in the
finder, and now this. Measured: the summary is 44px on a phone and 39 on a
desktop, the six chips wrap to two rows at 360px and sit on one at 1440, and
in dark mode the links are 11.45:1 on their ground and the marked ward 5.7:1.

**And the box at the top was somebody else's.** Only four pages on this site
are built by hand — the home page, About, the legislator index and 404. Every
other one is `bills.html` with a record substituted into it, or a list built
on the same shell, so every one of them inherited bills.html's search row — a
town page opened with "Search all bills" printed above the name of the town,
and so did a member's page, a committee's, and all eleven civics pages —
thirteen topics now, and a by-the-numbers page beside them. It is the same
fault as the order
of the sections, one line higher up: the first thing on the page was about
the site rather than about the page.

It is hidden now wherever the page is not a bill or a list of them. A bill's
own page keeps it, because there the next bill is a plausible next thought
rather than a change of subject, and the Bills tab is one click from
everywhere else.

Hidden, not removed, and the reason is worth keeping: `app.js` binds seven
ids in that row when it loads and `shell.py` asserts every one of them is
present in the template, because a missing `#q` once drew 33,683 blank
pages. `[hidden]` on the wrapper takes the row out of the layout and out of
the accessibility tree and leaves every binding where it was — and the rule
is declared as `.searchrow[hidden]{display:none}`, the way `.fbody`,
`.cbody` and `.pane` are, since the base rule sets no display and this file
has four rules that assume one.

One note on method. The first check of this reported the old behaviour on
two page types, because the browser served the pages out of its own cache:
the addresses were the same, and the `?v=` hash that would have told it
otherwise is inside the HTML it had already stored. Every visual check of a
rebuilt page now loads it with a throwaway query on the end.

---

## A former member's page says so once

Every person in the record has a page of their own, and 1,785 of those pages
belong to somebody who holds no seat now. Such a
page says so in one quiet line under the heading — `.pformer`, the secondary
ink at UI size with a rule down its left edge — and it is the only place on
the site that says it. In a roll call or a sponsor list a former member is
drawn exactly like a sitting one, same honorific, party and seat, because
that is the seat they held when the record was made.

**Not a coloured badge, and silent about why.** The site does not distinguish
a member who resigned from one who lost, retired or died, and must not start
here: people who served alongside them read these pages. The line is a
statement of tenure for a reader who arrived cold, which is a different thing
from a flag on a person. Two rows do come off — the towns they represent and
the contact address — because neither is true any more, and a directory entry
for somebody who holds no seat is the one thing the page must not look like.

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
Where a component is used at two depths — the `.shows` box carries the first
heading after the hub's `h1`, above every section, and sits under a section on
a topic page — the rule matches both and the level follows the page.

Measured rather than looked at: every heading on two bill pages and a
committee page was captured before and after with its tag, class, text,
font-size, weight, colour, transform, letter-spacing and margins. **38
headings moved from `h3` to `h2` and not one of the other properties changed
on any of them.** The same capture proved the first attempt meaningless — the
pages still asked for the previous `app.js?v=`, so the browser served what it
already had and the comparison came back identical because *nothing had been
reloaded*. Load a rebuilt page with a throwaway query, as the town-page note
above says.

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
leave with is a course with exits almost everywhere — seven of the thirteen
stages can end it.

**It is three diagrams now, from one function.** `civics.flow_diagram` also
draws how the constitution is amended, where the per-step label is the
threshold rather than a generic mark, and how to testify. The heading level
is an argument to it rather than a property of the diagram, for the reason
*A level is not a size* gives: on *How a bill becomes law* the four phases
are that page's own sections and are `h2`, and on the two pages where the
diagram sits under a section heading they are `h3`.

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
