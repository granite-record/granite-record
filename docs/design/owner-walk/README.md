# The owner's preview walk: three changes (for 11 November)

The branch is `owner-walk`, on top of `guides-heads`. Each change comes from the person's walk of the
preview on 30 October 2026, relayed by the manager session.

## How the shots were made

Each shot is `<item>-<view>-<before|after>-<390|1280>-<light|dark>.png`.

- **Before** is `guides-heads` (7b9e68ec) and **after** is this branch.
- **Pages:** each tree built preflight's fixture site, and its own `resources.html`, passport guide,
  `app.css` and `components.js` were served inside the preview's address. The fixture publishes only a few
  guides, so each hub group shows a count of 1.
- **Chips:** the Reports-tab chips are drawn with the tab's own markup (`.repline`, `chip()`, `cstat`) and
  each tree's own `recColour`, read out of its app.js.
- **Requests:** every request to the General Court's servers was blocked.

## 1. The passport guide under the federal section (`w1-hub-passport-*`)

How to Get a U.S. Passport is now listed under **Federal Benefits**, beside Medicare and disability
benefits. It was under Property and Records.

- **Open question:** whether to rename the group "Federal Programs and Services" is with the owner.

## 2. A guide's parts in its index (`w2-guide-otp-*`, `w2-guide-side-*`)

A guide whose steps come in parts (guides.PARTS) lists each part under Step by Step, one level down:

- in "On this page" (390);
- in the index beside the page (1280), which is copied from it.

The passport guide's three parts are "Renewing an adult passport", "Applying in person" and "Either way".
At 1280, a click on the first lands its heading 16px from the top.

- **The addresses:** each part's heading carries `steps-<the part's English words>`, the same on the
  Spanish page.
- **The look:** the rows are indented and in --t-sm, smaller than the sections, as the part's heading
  is under its section's.
- **The checks:** `_guide_parts_in_index` draws every guide in parts. `_guide_parts` reads past the new
  id.

## 3. An interim study report's chip on the Reports tab (`w3-interim-chips-*`)

| The report | Before | After |
|---|---|---|
| Recommended for future legislation | plain | green (`s-law`) |
| Not recommended for future legislation | plain | red (`s-done`) |
| Without recommendation | plain | plain |
| Ought to Pass, Inexpedient to Legislate | green, red | unchanged |

- **Before:** no wording of an interim report matched the colour table, so every one was plain.
- **Wordings read:** the docket's own, and the clerks' variants: "Recommended for Further Legislation",
  "Not Recommended for Legislation" and "Not Recommended for Future Recommendation" (fixed in review).
- **The check:** `_interim_report_chip_colours`.
- **Open question:** the site's other marks for the same report are orange where it recommends: the
  docket line's arrow, a committee meeting card, and `build_pages.STUDY_KIND`. Whether they follow the
  green and red is with the owner, and the manager's default is one rule everywhere. Until then, a bill's
  Summary and its Reports tab can colour one report differently.
