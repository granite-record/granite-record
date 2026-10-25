# Translating the site

The site is written in English and is being translated into Spanish, starting
with the home page, the header, the footer and Settings (begun 23 October
2026). This page is for the person proofreading the Spanish and for whoever
changes the site's words afterwards.

## What is translated, and what is not

A page holds three kinds of words, and each stays current its own way.

1. **What the record says** -- a bill's title, a committee's name, a person's
   or a town's, each line of a bill's history, the hand-kept status note.
   These are **not** translated. They change every night, a translation
   would be out of date by morning, and a bill's title is a legal text. The
   Spanish page prints them as the General Court wrote them, marked as
   English for screen readers, and says once, under its opening paragraph,
   that the record is in English.
2. **What the site works out** -- a count, a date, how many days off a
   meeting is. Worked out once, from the same files, for both languages.
   Only the words around a number are translated: "{n} bills" is "{n}
   proyectos de ley". A new night's numbers reach both pages at once.
3. **What the site itself says** -- the menu, a heading, a sentence of help.
   These are translated, once each, in `src/pages/lang/es.json`.

Dates follow the language: "19 de febrero de 2026" and "1:30 p. m." on a
Spanish page.

**The glossary** (24 October 2026) is a table of the record's own words,
`src/pages/words/glossary.json`, and its translations are entries like any
other, keyed `gloss.<term>.name` and `gloss.<term>.says` ("gloss.itl.name").
The Spanish page, `/es/learn/glossary`, gives each term as the record prints
it, in English, with its Spanish name and meaning beside it, because that
English is what a reader meets on a bill's page. The pop-up on a term says
the same on a Spanish page, from the shared words file `/lang/es.js`.

**The how-to guides** (24 October 2026) are in Spanish at `/es/guides/`, every
one `i18n.PAGES` names -- the guides of `src/pages/guides.py` and the three
pages of `civics.HOW_TO` -- with the Resources hub's How-To Guides at
`/es/resources`. A guide's words are data, written as HTML, so they are
translated a **piece** at a time: a paragraph, a list item, a heading, a table
cell, a button's label. Each piece is an entry keyed by its page and a slug of
its own first words, `guide.how-to-vote.you-can-register-if-on-election`, so
a paragraph put in above another leaves the other alone. A piece that several
guides share is keyed once, where it is written: `guide.said.*` for the
paragraphs about hearings that `guides.SAID` writes once, `guide.help.*` for
the Who Can Help entries. The hub's tasks are `guide.task.<slug>.does` and
`.line`.

A piece keeps its markup: a link (`<a href="...">`) keeps its address, and a
`[[figure]]` -- a count the build fills in, such as `[[house_districts]]` --
stays exactly as it is, because the number is the record's, filled in after
the words are translated. Titles and button labels are plain text. Words the
reader should see in English inside a Spanish piece, such as the request a
reader copies to send a New Hampshire office, may be wrapped in
`<span lang="en">`.

The official pages the guides send a reader to are in English, and each guide
says so once under its title. A link to another guide goes to its Spanish page.

**Reporting a mistake in a translation.** Every page in Spanish has a button
in its footer, *¿Ve un error de traducción? Avísenos*, and while words of the
page are selected, a button in the corner offers the same. It opens a box that
sends the page's address, its language, the reader's note and the words they
had selected, to the same place as the record pages' *Report a problem* box.
The reports reach the morning's triage file, under
`src/pages/lang/es.json`, with the reader's words quoted.

## How a translation stays current

The English stays in the code, where the page is written. Each piece of the
site's own words is written with a key beside it, and the catalog keeps, for
each key, the Spanish **and the English it was translated from**. The Spanish
is used only while that English is still the English on the page.

So when somebody changes the English:

- the Spanish page shows the new English in that one place, never the old
  Spanish, which no longer says the same thing;
- `python3 preflight.py --code` fails, naming the key, the old English, the
  new English and the Spanish, until the Spanish is brought up to date;
- bringing it up to date puts it back to **draft**, so the proofreader sees
  it again.

A translation can therefore lag an edit, visibly, but it can never go on
saying something the English page no longer says.

## One Spanish word for each English term

`src/pages/lang/terms.es.json` (25 October 2026) gives each recurring
English term its one Spanish rendering: *hearing* is *audiencia*, *town or
city clerk* is *el secretario de su municipio o ciudad*, *eligible* and
*qualify* are *reunir los requisitos*, *fee* is *cuota*, on every page.
`python3 preflight.py --code` fails on any entry whose English uses a listed
term and whose Spanish does not use its rendering, and names the entry.

To change a term, change it in the list first; preflight then names every
entry to bring along, and `python3 src/ops/translations.py --set` brings each one back to
draft. A program's or an office's name follows the agency's own Spanish
where it publishes one (Medicare's *Ayuda Adicional*, the Postal Service's
*oficina postal*); ordinary words follow the list even where one agency
phrases them differently. The file's `_about` says how a term is matched.

## Draft and proofread

Every entry is a **draft** until the proofreader passes it, and then it is
**proofread**. The first drafts were written on 23 October 2026, in the
formal *usted*, for US Spanish readers. A few choices the proofreader may
want to make differently carry a note beside the entry; the main ones:

- the General Court is "la Legislatura de New Hampshire", named "el General
  Court" once in the footer ("Corte General" reads as a court of law);
- a town is "municipio" and a city's ward "barrio electoral";
- New Hampshire stays "New Hampshire".

## Not shown to everyone yet

While `"offered"` is `false` in `src/pages/lang/es.json`, the Spanish pages
are built and published at `/es/`, but:

- nothing links to them and search engines are asked not to index them;
- the English pages do not offer Spanish, and a reader's browser language
  sends nobody there.

Anyone who opens `/es/` directly is shown the language choice in Settings
from then on, in that browser. That is how the proofreader and the site's
owner can try the whole of it -- the switch, the browser-language behaviour,
the notice on English-only pages -- before anybody else sees it.

Setting `"offered": true` is the owner's decision. From then on Spanish is
in Settings for everyone, a reader whose browser prefers Spanish is taken to
the Spanish page of any page that has one, the footer offers "Español", and
the home page is in the sitemap and names its Spanish twin to search
engines.

## The language choice

Settings (the gear in the header; on a phone, the menu) has a **Language ·
Idioma** row: the browser's language, English or Español. The choice is kept
in that browser only. With no choice, the first of the browser's languages
the site has decides, and it only ever moves a reader from an English page to
a Spanish one -- someone who opens a Spanish link was sent it on purpose.

A page that is not yet in Spanish says so, in Spanish, at its top, with the
way back to the Spanish home page.

## For the proofreader: the sheet

```
python3 src/ops/translations.py --sheet es.csv --drafts
```

writes a spreadsheet of every entry still a draft: its key, where the code
says it, the English, the Spanish, its state and any note. Two columns are
the proofreader's:

- **corrected** -- the Spanish as it should read, only where it should
  change;
- **ok** -- "yes" to pass the entry, with the correction if there is one.

Keep anything in `{braces}` exactly as it is: it is where a number, a date or
a name goes. Words in `<b>` or `&rsquo;` are markup and entities; a plain
character (’, —, …) is fine instead.

```
python3 src/ops/translations.py --take es.csv
```

takes the sheet back. It refuses -- and changes nothing -- if any row's
English changed while the sheet was out, or a correction lost a `{brace}`.

## For whoever changes the code

- A new piece of the site's own words is written `say(lang, "key", "English")`
  in Python, or `tr("key", "English")` in a script, with the key and the
  English written out in the call. Then
  `python3 src/ops/translations.py --set key "Spanish"` adds its draft.
- Changing the English of an existing key: the same `--set`, with the Spanish
  brought up to the new English.
- `python3 src/ops/translations.py` says how many entries are drafts and
  what, if anything, is missing or stale.
- A word that is the record's own (a title, a name, a docket line) is not
  translated: print it as it is, marked `lang="en"` on a page in another
  language.
- Translating another page: add it to `i18n.PAGES["es"]`, build its words
  with `say()`, and have its builder write the page for each language it has,
  as `build_pages.py` does for the home page.
- A new how-to guide is English to everybody until it is added to
  `i18n.GUIDE_PAGES`; from then on preflight asks for every piece of it.
- Changing a guide's English: the piece you changed shows in English on the
  Spanish page, and preflight names it -- stale, where the change is past its
  first words; missing, with its old key named as unused, where the change is
  in them. `python3 src/ops/translations.py --set` the new key, or the stale
  one, and `--drop-unused` the old.

`src/pages/i18n.py` explains the machinery in full.
