# What stays in English, and why: one note on every Spanish page

A native Spanish speaker read some of the Spanish pages for the owner on
6 November 2026. He found the translation natural and accurate, and nothing
obviously wrong, and is passing it to the Latino caucus for a detailed
review. What confused him was why some parts were translated and others,
such as a bill's legal text, were not. The pages said it four different ways
(`home.lang_note`, `guides.lang_note`, `guides.hub_lang_note`,
`learn.lang_note`), none of them said why, and Officials and the glossary
said nothing.

## What changed

- `chrome.lang_note(lang)` draws one note: the line under the title, and
  under it an opener, *Por qué algunas partes están en inglés*, with the
  four reasons. It is folded and opens on a tap.
- Every page `i18n.PAGES` names in Spanish carries it once: the home page,
  Officials, Resources, the glossary, each guide and each Learn page. On the
  fixture that is 27 pages. No English page carries it.
- The four old entries are gone from the code and the catalog.
- The inline "(en inglés)" markers, where a list names a page still in
  English, are unchanged.
- The wording is the laptop manager's draft, approved by the owner as
  drafted ("fine as is for now"). It appears word for word in both
  languages; only the site's typographic apostrophes and quotation marks
  are applied. All six entries stay "draft" for the caucus's review, and
  their corrections come back through `src/ops/translations.py`.

## Checks

- `_one_language_note` holds:
  - the note, once, on each Spanish page built on the fixture;
  - none on any English page;
  - the four reasons under the opener;
  - the approved wording, word for word in English and Spanish;
  - every entry still draft;
  - the old keys gone;
  - the "(en inglés)" markers still drawn.
- `_spanish_learn` and `_spanish_guides` now look for this note in place of
  the two they used to look for.

## Shots

Real data: the live `/es/` and `/es/guides/how-to-vote` from
graniterecord.org, with their current one-line note swapped for this
branch's `chrome.lang_note("es")` and drawn with this branch's `app.css`.
This session cannot build the real site, because the data kit is not on it.

- `before-*`: the live page as it is today, light, at 390 and 1280.
- `after-*`: the new note, closed. `after-*-open`: the reasons open.
  Each at 390 and 1280, light and dark.

No horizontal scroll on any of them.
