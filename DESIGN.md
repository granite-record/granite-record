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
