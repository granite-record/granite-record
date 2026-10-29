# R2 polish batch: the plan

Branch `fix/r2-polish`. Cut it from `dev` after the Videos and outage-recovery work is merged. Release after 11 Nov. All five items are front-end only: no data, no network and no General Court address.

I read every file:line below myself at dev cfbee9f, except where a line says "scout". I changed no tracked file.

My own measurements are on the preview at 390px. The scripts and screenshots are in `/tmp/claude-0/-home-user-granite-record/1a33c740-9bc7-5686-b8d9-66b7dd06a714/scratchpad/r2plan/plan-verify/`.

Left out because they are done elsewhere:
- the Reports tab's "and the vote" sentence
- the seating chart's Zoom-to-fit icon
- the map's zoom-to-fit icon

**Python note** (corrected by the main session): run `inventory.py` and `preflight.py` with `/tmp/claude-0/py314/python3` (3.14), as every other branch here does; the bare `python3` is 3.11 and too old for `narrative.py`.

---

## Build order (one commit each)

Files no other item touches go first. `app.css` is shared by three items, so its commits go last.

| # | Commit | Files | Size |
|---|---|---|---|
| 1 | Laws: one name, "New Hampshire Laws" | build_rsa.py, constitution_tab.py | xs |
| 2 | Calendar documents: drop ".tagged"/".doc" from labels | calendar_documents.py | xs |
| 3 | Old room codes read in words | plain_action.py, app.js (optional: build_study_committees.py) | s |
| 4 | Calendar: a study-only day says so | build_calendar.py, app.css (one selector) | s, close to m because many checks pin the old words |
| 5 | Openers: every mark points right, then down | app.css | s |
| 5b | (if the owner says yes) The debate's opening sentences show while it is shut | build_session_pages.py, app.css | xs |
| 6 | Tab strips on phones: a stronger edge | app.css | s |

Every commit also touches `preflight.py` and `versions.json`. For each one:
1. Run `python3.13 src/ops/inventory.py --bump-changed`.
2. Run `python3.13 preflight.py --code`, which must be green.
3. Commit.

At the end, run the full `preflight.py` and then `handoff.py`. After the next dry run, re-run the scouts' Playwright scripts against the preview. Commit 6 goes last for three reasons:
- the town-directory work (in progress) also touches `.twntabs`
- it has an open dark-mode question
- it changes an existing preflight rule

---

## 1. Laws page: "New Hampshire laws" vs "New Hampshire Laws" (xs)

**Seen now (scout).** On /laws, the browser tab title reads "New Hampshire Laws — every chapter of the RSA". The H1, the link-preview headline (og:title), the tab strip's aria-label and all four citation forms read "New Hampshire laws". Headings elsewhere on the site are Title Case (civics.py:49-50, check at preflight.py:65113).

**Cause (read).** The name is typed in two cases:
- build_rsa.py:1652 has `title = "New Hampshire laws"`. It feeds the H1 (:1673), og:title (:1660) and the citation (:1674).
- build_rsa.py:1655 has `S.title_of("New Hampshire Laws", …)`, a second literal.
- constitution_tab.py:140 hard-codes `aria-label="New Hampshire laws"`.

**Fix.**
1. build_rsa.py:1652 becomes `title = "New Hampshire Laws"`.
2. :1655 becomes `S.title_of(title, "every chapter of the RSA")`.
3. `constitution_tab.tabbed` takes a `label` argument (the town pages' `tabbed(label, panels)` pattern) and uses `aria-label="{E(label)}"`.
4. Its only caller, build_rsa.py:1789, passes `title`.
5. Update the usage line at constitution_tab.py:8.

No Spanish change: there is no /es/laws page.

**Check.** Add one check beside `_constitution_tab` (preflight.py:40953). It builds `B.landing_page(...)` as :40965 does, then asserts that these five all equal "New Hampshire Laws":
- the `<title>` text before " — "
- the H1
- og:title
- the tablist's aria-label
- the MLA citation's title

It also asserts that every case-insensitive match of "new hampshire laws" on the page is exactly "New Hampshire Laws", and runs `_title_case_faults` (:65105) on the name. On cfbee9f this check fails, as it should.

---

## 2. Calendar documents labelled with a file suffix (xs)

**Seen now (scout).**
- "The newest listed here" reads "Senate Calendar: SC 36.tagged (PDF)". The picker and the button's aria-label say the same.
- documents.json has two labels ending in a suffix: "SC 36.tagged" and "…Veto Day Final.doc".

**Cause (read).** `clean()` at calendar_documents.py:188-194 strips only a final ".pdf" (:193). Labels are the General Court's file names on purpose (:39-54; preflight.py:49443).

**Fix.** Change :193 to `s = re.sub(r"(?i)(?:\.(?:tagged|docx?))*\.pdf$", "", s.strip())`.
- Addresses are unchanged, because `index()` keeps the recorded URL.
- `number_of` (:245) reads `clean(name)`. `_NUMBER` (:146) finds 36 in both "SC 36.tagged" and "SC 36", so numbering does not change.
- Bare names like "63", "No30 August 14 2026" and "hb0001_final" stay as they are. That rule (1 October) is the owner's (Q7).

**Check.**
- In `_calendar_documents` (preflight.py:49417), add a fixture row for "SC 36.tagged.pdf". Assert the label is "SC 36" and the address tail is byte-for-byte the recorded `Calendars%5C2026%5CSC%2036.tagged.pdf`.
- Sweep: no label in `CD.index(docs)` matches `\.(?:pdf|tagged|docx?)$`.
- On the next preview: 0 such labels in calendar/documents.json, and /calendar reads "Senate Calendar: SC 36 (PDF)".

---

## 3. Old room codes shown raw (s)

**Seen now (scout).**
- Committee Meetings tab: 9,197 of 21,267 one-room entries show the clerk's code, mostly from before 2007. Example: committee/H05, 1997-1998, "1 bill · no votes · RM207,LOB :EDUC".
- Bill Hearings tab: bill/1998/sb456 shows "RMS205-207,LOB".
- Study committee pages: "Room 102 LOB", "LOB Rooms 306/308", "Room 100 SH".
- Calendar, 2026-11-09: "Executive Council Chambers SH RM 207".

**Cause (read).** The site's room rule lives in two copies that preflight holds to the same answers:
- `plain_action.place` (plain_action.py:555-575), used by the Calendar, the feeds, static bill pages and study pages
- app.js `roomWords` (app.js:5392-5408), used by the committee meeting line :8889, the Hearings station :5719, the Calendar :9105/:9116, Meets In :9196 and :4838

Neither copy reads these forms:
- the room-first "RM207,LOB" / "RMs210-211,LOB" / "RM105A,ST HOUSE"
- "Room 102 LOB" with no comma
- "LOB Rooms 306-308" (plural)
- "SH RM 207" (`Rm` is matched case-sensitively, at :555 and :5406)

build_committees.py:983 stores the venue raw. build_study_committees.py has its own reader, `OLD_ROOM`/`old_room` (:453-465), but only for meetings that miss the Calendar. Its output, "LOB Rooms 306-308", is then not read by `place` (:629).

**Fix.** Add the same two changes to both copies, in the same order, before the existing building-first pattern. No new helper.
1. Room-first, ignoring case: `\bRMs?\.?\s*,?\s*(\d+(?:-?[A-Z])?(?:\s*[-/]\s*\d+(?:-?[A-Z])?)?)\s*[,/]?\s*(LOB|ST\.?\s*HOUSE|STATE\s+HOUSE|SH)\b` is rewritten to "LOB n" / "SH n", which the existing rule then words. Also "Room n LOB|SH|GP|SL" with no comma, limited to those four codes.
2. Building-first: widen `(?:Room |Rm\.? ?)?` to `(?:Rooms? |R[Mm][Ss]?\.? ?)?`.

Tails such as ":EDUC", "<Rep X>" and "(NOTE TIME CHANGE)" stay as written after the room.

Scout's score, run in node on the preview's data with app.js's roomWords plus these patterns:
- committee entries still raw: 9,197 → 103
- hearing items still raw: 29,388 → 427

Optional one-liner (Q8): `old_room` returns "LOB n" / "SH n", so study pages say "State House 105-A" as the rest of the site does.

**Check.** Extend the shared table in `_rooms_in_words` (preflight.py:41978-41987), which is checked against both copies, with:

| Input | Expected |
|---|---|
| "RM207,LOB" | "Legislative Office Building 207" |
| "RMs210-211,LOB" | "Legislative Office Building 210-211" |
| "RM105A,ST HOUSE" | "State House 105A" |
| "RM100, St House" | "State House 100" |
| "Rm,208, LOB" | "Legislative Office Building 208" |
| "RM 202LOB" | "Legislative Office Building 202" |
| "RM210-211/LOB" | "Legislative Office Building 210-211" |
| "Room 102 LOB" | "Legislative Office Building 102" |
| "Room 100 SH" | "State House 100" |
| "LOB Rooms 306-308" | "Legislative Office Building 306-308" |
| "Executive Council Chambers SH RM 207" | "Executive Council Chambers State House 207" |

- Keep the cases that must stay unchanged: "302-304" (:41982), and "Room 100, St House", "3RD FLR CONF RM, SH" and "NH Fish & Game Conf Rm" (`_state_library_room`, :42047-42050).
- Widen the fixture Calendar sweep at :42007 to `(?:RMs?\s*\d|(?:LOBO?|SH|GP) ?(?:Rooms? |RMS? ?)?\d)`.
- On the next preview:
  - H05 1997-1998: 0 of 87 entries match `RMS?\d|,LOB`
  - sb456: "Legislative Office Building 205-207"
  - ss61: no "LOB Rooms"
  - ss117: no "Room 101 LOB"

Note: today "Room 100, SH" reads "Room 100, State House" (:41979), while the new "Room 100 SH" would read "State House 100". Both are in words, but they are in different orders (Q8).

---

## 4. Calendar says "No meetings shown." on days that have study committee meetings (s)

**Seen now (scout, preview).**
- /calendar is the week of 26–30 Oct 2026. Every weekday reads "No meetings shown." The week holds 19 study or statutory meetings.
- The only explanation is the count line, "None of the 18 meetings this week match. 18 study committee meetings are hidden.", with "Show them" about 500px away on desktop.
- Day view says "Nothing on this day matches the filters." The month grid shows no dots, and its screen-reader name says "no meetings shown".
- On the preview's data, study committees are the only meetings on 172 of the 409 days that have any meeting. That includes every remaining weekday of 2026.

**Cause (read). This is the design working as built, not missing data.**
- Study Committee starts unticked (build_calendar.py:610-611; the owner, 25 Sep), and `matches()` drops those cards (:773-780).
- On 18 Oct the per-day count was removed on purpose (:901-906): "a day says only that nothing is shown". So `emptyWords()` returns "No meetings shown." (:911). The built page does the same through `STUDY_ONLY` (:2677), added by `study_hidden()` (:2691-2693).
- The why and the how live only in `countLine()` (:808-829) and `#calshowst` (:2602). With nothing seen, the line takes the "None of the N meetings… match." branch (:812-814), although the reader set no filter.
- Three other places word the same day differently:
  - `dayView` returns early with "Nothing on this day matches the filters." (:1454-1455)
  - `peekHtml` says the same (:1092)
  - the grid cell says "no meetings shown" and draws no dot (:1060-1061)

**Fix (keeps the owner's default and the one count a week).** Replace the day's existing line; do not add a line. No count. Draft words: **"Study committee meetings only. Show them"**, where "Show them" is the control (Q1, Q2).
1. `emptyWords` (:911) returns the new words. The List (:1438) and Week (:1475) views pick them up.
   - Draw "Show them" as a small button.
   - Factor the handler at :1958-1966 into a function. Call it from #calshowst and from one delegated click listener on the schedule panel.
2. `dayView`: delete the early return at :1454-1455, so the day falls through to :1456-1457 (emptyWords). The generic Day-view line for other filtered days then becomes "N meetings are hidden by the filters.", the List view's words.
3. `peekHtml` (:1092): when `meetings(day.cards)` is non-empty, use `emptyWords(meetings(day.cards), c.f)`. Otherwise keep today's words.
4. Grid cell (:1061): when every hidden meeting is a study committee's, the screen-reader name says "study committee meetings only".
5. `STUDY_ONLY` (:2677): the same words, with `<label for="calst">Show them</label>`. #calst comes before the days, and app.css:5806 already hides `.calstonly` once it is ticked, so this works with no script. Add `.calstonly label` to the link-style selector at app.css:5796.
6. `countLine` (:812-814): when nothing is seen and every hidden meeting is a study committee's (`t.study===t.total`), say only "18 study committee meetings are hidden." (Q3).

**Check.** The scout listed :63638, :69214-69215, :69279, :69667 and :69736. I found three more that pin the old words or would break:
- **:63609-63610** asserts that no "is hidden." / "are hidden." appears in the built week after the count line. The scout's draft "…, which are hidden." would turn it red. The words above avoid "hidden.".
- **:63506-63507** pins a study-only week, "The one meeting this week does not match. 1 study committee meeting is hidden.". Step 6 changes it.
- **:69261** pins the grid name "…, no meetings shown". Step 4 changes it.
- :63640 is a mixed week ("1 of 3 meetings shown…"), so step 6 does not affect it.

Add four checks to the DOM run (:69663-69668, :69724-69737):
- Day view of 2026-03-13 under the defaults shows the new words, never "matches the filters".
- That day's "Show them" ticks the box and draws the Aging card.
- The grid name of `td[data-d="2026-03-13"]` says study committees.
- The built study-only day (:63604) contains `<label for="calst">`.

On the next preview, re-run `calendar-study/views.cjs` for ?week=2026-W44 and W40 (List, Week, Day, no script, after Show them: 19 cards).

---

## 5. Openers: the journal debate's caret does not turn; three others turn another way (s)

**Seen now (scout, preview).**
- /session/H/2026-05-14 has 8 "Debate printed in the permanent journal · N speeches ▸" openers. The triangle points right both shut and open; the computed transform is `none` both ways.
- The other 18 drawn marks (22 CSS rules) and every browser marker point right while shut and down when open, with three exceptions:
  - Learn "On this page" (`.l-otp`)
  - Resources topics (`.g-topic`)
  - /data "On this page" (`.dponp`)

  These three point down while shut and up when open.

**Cause (read).**
- The shared triangle `:where(body:not(.pg)) .caret` (app.css:3264-3266) has no turn of its own. Each opener adds one: calkd :974, calmeet :989, hrep :2982, docket :3267, cgrp :7957.
- build_session_pages.py:2714 writes `<span class="caret">` into `.sdebate`, and no `.sdebate[open]` rule exists (:6190-6199).
- The three odd ones:
  - `.l-otp`: `rotate(90deg)` shut, `rotate(-90deg)` open (:4570-4571). `--l-chev` points right (:4517, path M9 5.5l6.5 6.5L9 18.5).
  - `.g-topic`: `translateY(-.15rem) rotate(45deg)` shut, `rotate(-135deg)` open (:4956-4957).
  - `.dponp`: `rotate(45deg)` shut, `rotate(225deg)` open (:6546-6548).

**Fix: five edits to app.css, no markup.**
1. After :6194, add `.sdebate[open] > summary .caret{transform:rotate(90deg)}`. The transition is already at :3266.
2. `.l-otp`:
   - Drop `transform:rotate(90deg);` from :4570.
   - :4571 becomes `.l-otp[open] > summary::after{transform:rotate(90deg)}`.
3. `.g-topic`:
   - :4956's transform becomes `rotate(-45deg)`.
   - :4957 becomes `.g-topic[open] > summary::after{transform:translateY(-.15rem) rotate(45deg)}`.
4. `.dponp`:
   - :6545's margin becomes `0 0 0 var(--sp-1)`.
   - :6546 becomes `rotate(-45deg)`.
   - :6548 becomes `.dponp[open] > summary::after{transform:rotate(45deg);margin:0 0 .2em var(--sp-1)}`.

The scout previewed all four by injecting these rules on the preview: `carets/*-fix-*.png`.

**5b (only if the owner says yes, Q5).** The debate's opening sentences (`p.sdopen`, build_session_pages.py:2715) sit inside the `<details>`, so they never show while it is shut. That defeats the stated intent at app.css:6188-6189.
- Move the `<p class="sdopen">` to just after `</details>`.
- Change :6199 to `.sdebate[open] + .sdopen{display:none}`.

The preflight regex at :36081 stops at `<details class="sdebate"`, so it is unaffected.

**Check.** Add a frontend check in the style of `_chip_nowrap` (:27024), using `_css_rules`/`_css_decls` (:24053/:24083):
- (a) Every rule that turns a summary mark (`::before`, `::after`, `.caret`, `.chev`, `.cmcaret`) under `[open]`/`.open` turns it from right to down. It works out the unturned direction from how the mark is drawn: `--l-chev`, ▸ or a border-left triangle point right, and a border-right+bottom corner points 45°.
- (b) Every `<details class="X">` in src/pages that writes a `.caret`/`.chev`/`.cmcaret` has an `X[open]` rule that turns it.

The scout's prototype `carets/proto_check.py` reports 22 right→down, 3 other and 1 unturned on cfbee9f, and 26/0/0 with the edits applied. Build the real check on `_css_can_reach`/`_css_compound_fits` (:71535/:71484) rather than the prototype's class-name pairing.

---

## 6. A cut-off tab on phones (s)

**Seen now (scout, light mode, 390 and 360px).** Strips scroll inside themselves. The only cue that there is more is an edge shadow, and on these strips it is faint:
- Town pages (`.twntabs`): "Services" shows 17 of 89px at 390 and is fully hidden at 360.
- /officials: 3 of 6 tabs are hidden.
- An opened /bills card (`.tabs`): Reports, Sponsors and Documents are hidden.

Bill and member pages already use the deeper "choice A" edge.

**Cause (read).**
- `.twntabs` below 1024px uses fading covers and a 1rem `var(--shadow)` edge (app.css:1627-1631).
- The list card's `.tabs` below 45em uses 24px covers and a 16px `var(--shadow)` edge (:3493-3497).
- The record strip's comment says that edge is "nobody saw it" and uses 40px covers with a 32px `var(--lift)` edge instead (:7088-7096).
- The scroll-into-view scripts already assume a 2rem edge (build_pages.py:2464, build_town_pages.py:1663).

**What I measured myself, in light and dark mode at 390px** (`plan-verify/edge_dark.cjs`, pixel 3px inside the right edge against the ground beside it):

| Strip | Light | Dark |
|---|---|---|
| Town strip today (`--shadow` 16px) | 216 vs 233 (17 levels) | 14 vs 23 (9 levels) |
| Town strip with the proposed `--lift` 32px edge | 186 vs 233 (47 levels) | **19 vs 23 (4 levels): weaker than today** |
| Bill page record strip today | 186 vs 233 | 19 vs 23 |

So the proposed swap is right in light mode and a regression in dark mode. In dark mode `--shadow` is `rgba(0,0,0,.5)` and `--lift` is `rgba(0,0,0,.22)` (app.css:367-368, 423-424). The record strip is already nearly invisible in dark.

**Fix (recommended; the dark value is Q6).**
1. Add one token for scroll edges, for example `--scrolledge`. Its light value is `rgba(0,0,0,.22)`, the same as `--lift`. Its dark value is at least today's `rgba(0,0,0,.5)`. Define it in the three `:root` blocks: :175-180, :365-368 and :421-424, plus :1512 if that block needs it.
2. `.twntabs` at :1627-1631: 40px solid `var(--paper)` covers (local), plus 32px `var(--scrolledge)` shadows.
3. Card `.tabs` at :3493-3497: the same, with `var(--surface)` covers. Optionally also :2633-2637 for the tablet card.
4. Record strip at :7094-7095: `var(--lift)` becomes `var(--scrolledge)`. Light is unchanged; dark gets stronger.
5. preflight.py:102995-102997 requires `var(--shadow)` in `.twntabs`. Change it to the new token, or preflight goes red.

Leave `.l-tablewrap`/`.covwrap` alone unless Q6b says yes. Their own check (:27217-27221) requires `var(--shadow)`.

**Check.**
- Add a static frontend check (style of `_small_visual_s9`, :27181). For each scrolling strip rule (`.twntabs` at max-width:63.9375em, `.tabs` at 45em, the record strip at 68.75em, plus the tablet card if taken), assert:
  - two ` local` covers at least as wide as the two shadows
  - shadows that use the token
  - no `var(--shadow)`
- On the next preview, re-run `cut-off-tab/edge.cjs` in light and dark. **Sample about 12px inside the edge, not 3px.** Where a strip overflows by less than the 40px cover, the cover hides the outermost px: the member strip overflows by 37px and its pixel 3px in reads exactly the ground (233). The page's scrollWidth must equal the viewport.

---

## Questions for the owner (with the answer I recommend)

1. **Calendar default.** Keep study committees hidden by default and let each study-only day say so, or show them automatically on a day or week with nothing else? *Recommend: keep them hidden; change the day's line.* It replaces a line rather than adding one, so it keeps to 18 Oct's "no clutter".
2. **Calendar words.** "Study committee meetings only. Show them", with "Show them" on each such day? *Recommend yes.* No count and no "hidden." (a check forbids that word in the day). Tenseless, so past days read right.
3. **Calendar week line.** In a week of study committees alone, drop "None of the 18 meetings this week match." and say only "18 study committee meetings are hidden."? *Recommend yes.* The reader set no filter, so "match" misleads.
4. **Calendar categories.** The Fiscal Committee, Administrative Rules, Capital Project Overview and Long Range Capital Planning count as "study" and are hidden by default. Is that intended? *Recommend: leave as is in R2; raise as its own item if not.*
5. **Debate opening sentences (5b).** Move them out of the fold so they show while it is shut, as app.css:6188 intends? *Recommend yes,* placed after the fold and hidden once it is open.
6. **Tab edge.**
   - (a) Use one scroll-edge token, with a dark value at least today's `.5` (an exact value to be picked by eye on the preview)? *Recommend yes.* `--lift` alone weakens dark mode (measured above).
   - (b) Also apply it to the `.l-tablewrap`/`.covwrap` table boxes? *Recommend later, not R2.*
   - (c) Member pages: "Votes" is cut at 360 even with the strong edge, because the three labels are 371px. *Recommend leaving it scrolling in R2*, since shortening "Prime sponsored" is a wording call.
   - (d) Is a one-letter sliver acceptable once the edge is strong? *Recommend yes.* Bill pages already work that way by design (app.js:7998-8001).
7. **Document labels.** Strip only ".tagged"/".doc" (this plan), or make every label reader-facing ("No. 30 — August 14, 2026")? *Recommend only the suffixes in R2.* The rest reverses the 1 Oct rule.
8. **Rooms.**
   - (a) Keep ":EDUC", "<Rep X>" and "(NOTE TIME CHANGE)" as written after the room? *Recommend yes for R2.*
   - (b) Read "Executive Council Chambers RM 207" as "… Room 207"? *Recommend no*: it is free text.
   - (c) One order for study pages ("State House 103", not "State House Room 103"), via the `old_room` one-liner? *Recommend yes.*
   - (d) "Room 100, SH" (→ "Room 100, State House") vs "Room 100 SH" (→ "State House 100"): accept two orders for now? *Recommend yes, and note it.*
9. **Openers.**
   - (a) Do the two "On this page" drop-down menus (l-otp, dponp) follow the one rule too? *Recommend yes.* The ask was "every opener".
   - (b) Give a mark to openers with none (the home Coming-up cards, the map's district lists)? *Recommend no.* The home cards are bare on purpose (app.css:3259-3263).
10. **Laws name.**
    - (a) "New Hampshire Laws" (recommended) or bare "Laws"?
    - (b) Same fix for Bills, Committees and The Data? *Recommend a separate later item.* The Bills hidden H1 is matched exactly in shell.py:617 and in preflight.

---

## What the scouts guessed (not measured)

- **Carets:**
  - the new resting positions for g-topic and dponp were picked by eye at 1280 and 390 only
  - "no speeches on a bill's Votes tab" rests on one bill plus a grep
  - nbrep and ytaddr were never seen live
  - the browser-marker directions assume Chromium
  - the prototype pairs rules by class name
- **Calendar:**
  - which week prompted the board item
  - whether a per-day "Show them" counts as the clutter rejected on 18 Oct
  - tense on past days
  - the scout believed no check pins the Day-view words; that is true, but other pins exist (corrected above)
- **Rooms and file names:**
  - the bill-hearing count comes from the committee JSON, not page by page
  - ":EDUC" read as a committee code and "<Rep X>" as a subcommittee chair
  - "302-304" and "1000 am …" read as docket-parse edges
  - `plain_action.place` was not run (Python 3.11); the numbers come from app.js's `roomWords` in node
- **Tab edge:**
  - which strip the board item means
  - the 40-level pass threshold
  - the list card's contrast was computed, not measured
  - `--paper` assumed under every `.twntabs`
  - light mode only (dark measured by me, above)
  - one stray file (`cut-off-tab/generic_load.cjs.tmp`) was made by shell redirect
- **Laws:**
  - why the two cases were written
  - cached link previews keep the old headline for a while
  - the Spanish wording if a page is made later
- **Mine:**
  - that `python3.13` runs preflight here
  - the dark-mode token value (needs an eye on the preview)
