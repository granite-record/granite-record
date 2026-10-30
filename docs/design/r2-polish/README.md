# R2 polish batch: what changed, with screenshots (for 11 November)

Branch `fix/r2-polish`, cut from dev 2273166. It carries items 2 to 6 of the
plan in `PLAN.md` (on `design/committee-videos`), with every recommendation
taken (the owner's answer: "defaults"). Item 1, the Laws page's name, reached
dev in the 1 November bundle. One commit per item, plus one follow-up for 5b
and two for the review. The branch also merges `docs/one-finger-note`.

Each shot is `<item>-<view>-<before|after>-<width>-<light|dark>.png`.

- **Before** is dev.
- **After** is this branch. Each shot is the preview's own page with the
  branch's `app.js` or `app.css` routed in. Where a page is built HTML, its
  text is re-said with the branch's rule. Each item below says which.
- **Requests.** Every request to the General Court's servers was blocked
  while the shots were taken.

## 2. A calendar or journal named with a file suffix

`2-picker-*`: the Calendar's picker on Senate Calendars, 2026. `2-list-*`: the
list page.

- **Before:** "SC 36.tagged", and a 2007 House journal "… Veto Day Final.doc".
- **After:** "SC 36" and "… Veto Day Final".
- **The rule:** `clean()` takes `.tagged`, `.doc` and `.docx` only where they
  come before `.pdf`. Every other name stays as the General Court wrote it, as
  decided on 1 October. No address changes.
- **The "after" shots:** the preview's index, with each label read again by
  the branch's `clean()`.

## 3. The clerk's old room codes, in words

| Where | Before | After |
|---|---|---|
| committee/H05, 1997-1998 (`3-committee-*`) | "RM207,LOB :EDUC" | "Legislative Office Building 207 :EDUC" |
| bill/1998/sb456's Hearings (`3-bill-*`) | "RMS205-207,LOB" | "Legislative Office Building 205-207" |
| the Calendar, 9 November 2026 (`3-calendar-*`) | "Executive Council Chambers SH RM 207" | "Executive Council Chambers State House 207" |
| committee/ss117 (`3-study-ss117-*`) | "Room 101 LOB" | "Legislative Office Building 101" |
| committee/ss61 (`3-study-ss61-*`) | "LOB Rooms 306-308" | "Legislative Office Building 306-308" |

- **Committee H05, 1997-1998:** 40 old codes before, none after.
- **ss117:** 233 of its 270 meetings showed an old form; none do after.
- **ss61:** 62 of its 325 meetings did. After, one is left, "State House Room
  100".
  - This is a guess: that is the form `old_room` used to write. If so, the
    one-liner below takes it away on a real build, but the shot cannot show
    that.
- **Both room readers:** `plain_action.place` and app.js's `roomWords` read
  the same new forms, in the same order.
- **Tails:** whatever follows the room stays as written: ":EDUC", "(NOTE TIME
  CHANGE)".
- **The `old_room` one-liner:** a study page's room is now the building code
  and number, so it reads "State House 105-A", as the rest of the site does.
- **Two orders, as planned (Q8d):** "Room 100, SH" still reads "Room 100,
  State House".
- **The "after" shots:**
  - The committee and the bill come from the branch's `app.js`.
  - The Calendar week and the study pages are built HTML, so their room text
    is re-said with the branch's `roomWords`. preflight holds `roomWords` to
    `place`.

## 4. A day of study committees alone says so

The preview's /calendar, 26 to 30 October 2026, which holds 18 study committee
meetings and nothing else.

- **The views:** `4-list-*`, `4-week-*` and `4-day-*` are the script's three
  views. `4-noscript-*` is the page with no script.
- **"Show them":** `4-day-shown-*` and `4-noscript-shown-*` are the same views
  after it is pressed.
- **The "after" shots:** the page's inline script is the branch's
  `lean_js(WEEK_JS)`, swapped in for dev's. Its built day line and its
  `app.css` are the branch's too.

| | Before | After |
|---|---|---|
| each day (List, Week) | "No meetings shown." | "Study committee meetings only. Show them" |
| the Day view | "Nothing on this day matches the filters." | the same as the List |
| the week's line | "None of the 18 meetings this week match. 18 study committee meetings are hidden." | "18 study committee meetings are hidden." |
| the month's cell, to a screen reader | "…, no meetings shown" | "…, study committee meetings only" |
| no script | "No meetings shown." | the same words, "Show them" a label for the week's checkbox |

- **The default stays:** study committees are still hidden.
- **The day's line:** it replaces the old line rather than adding one, and
  carries no count.
- **A day's "Show them":** it ticks the box exactly as the week line's button
  does, and the day draws its 7 meetings.
  - The focus lands on that day's first meeting, so the reader stays on the
    day. The week line's own button still leaves it on the box beside it.
  - A day says this only under no other filter, the chamber included. Study
    committees have no chamber, so "Show them" could show nothing under
    "House".
  - With no script, the checkbox is named once, by the week line's label.
- **The shots:** these were taken before the review, so they show the
  wording but not the focus change.

## 5. Every opener's mark turns right to down

The views:

- `5-debate-*` is /session/H/2026-05-14.
- `5-learn-otp-*` is the Learn page's "On this page", shown on a phone only.
- `5-resources-topic-*` is /resources.
- `5-data-otp-*` is /data.

Each comes `shut` and `open`.

| Opener | Before (shut / open) | After |
|---|---|---|
| the journal's debate | right / right | right / down |
| Learn "On this page" | down / up | right / down |
| Resources topics | down / up | right / down |
| The Data "On this page" | down / up | right / down |

- **What changed:** app.css only. The marks were read from the computed
  transform after each turn finished.
- **5b, the debate's opening sentences:** they used to sit inside the fold.
  So they never showed while it was shut, and once it was open app.css hid
  them. Now they follow the fold: they show while it is shut and hide when it
  opens.
- **The follow-up commit:** with the sentences now in view, all eight
  debates of 14 May read "Thank you, Mr. Speaker.…". The split took "Mr." for
  the end of a sentence.
  - The opening no longer ends at a title, and it passes over thanks to the
    chair: "I rise today in opposition of Senate Bill 430 as amended …".
  - It is a commit of its own, so it can be left out.
- **The "after" debate shot:** the sentences are moved in the page, and the
  text is what the branch's `debate_opening` writes for each debate.
- **After the review:**
  - An opening that ends its sentence no longer adds "…" after the full stop.
  - In forced colours, the shared triangle was drawn as a square. It is a
    triangle now and turns with the rest (`5-debate-forced-*`, 600px).

## 6. A scrolling tab strip's edge

The strips:

- `6-officials-*` is the Officials strip; town pages use the same strip.
- `6-bill-*` is the record strip on bill/1998/sb456.
- `6-card-*` is an opened card on /bills.

Each was shot at 390 and 360, light and dark.

- **The token:** `--scrolledge` is `--lift`'s .22 in light and on paper, and
  .7 in dark.
  - Today's `--shadow` is .5 in dark.
  - The value .7 was picked by eye against .5 and .6. The comparison is kept
    outside the repository.
- **Every scrolling strip** has 40px covers of its own ground over 32px of
  `--scrolledge`.
- **The Officials and town strip at every width:** it scrolls at every width.
  At 1024 to 1120px it was cut with no edge at all, found in the review. At
  1080px it overflows by 47px (`6-officials-*-1080-light.png`).

The grey levels below are measured 12px inside the right edge, against the
ground beside the strip:

| Strip | Light before | Light after | Dark before | Dark after |
|---|---|---|---|---|
| Officials and town | 5 | 33 | 4 | 12 |
| An opened card | 6 | 35 | 5 | 17 |
| The record strip | 33 | 33 | 4 | 12 |

- **What was hidden at 390:** the Officials strip hid three of its six tabs.
  An opened card hid Reports, Sponsors and Documents.
- **The page itself:** it does not scroll sideways at either width.

## Left as they are, from the two-lens review

- **A strip that overflows by less than 40px** shows a faint edge, or none
  under 8px. Two examples:
  - the record strip at 612 to 644px (a phone held sideways, or 200% zoom);
  - the Officials strip at 992 to 1020px.

  It is the record strip's own design since 14 October: solid 40px covers.
  Fading covers would fix it, but that is a change of look, so it is left
  for a decision.
- **Rooms:**
  - "Legislative Office Building 207 :EDUC" keeps its tail (Q8a).
  - "Executive Council Chambers State House 207" has no comma (Q8b: it is
    free text).
  - ss61 has both "306/308" and "306-308", as the record writes them.
- **The day button's hidden text,** "(the study committee meetings)", stays,
  so a list of buttons read alone still says what each one shows.
- **Two files with one label:** if the General Court ever posts both "SC
  36.pdf" and "SC 36.tagged.pdf" for one date, the index would keep one.
  Nothing on this disk shows whether it does.
- **Debate openings:** they are not attributed to the member who spoke.
  Adding the name is a wording call.
