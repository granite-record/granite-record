# The release and backend session's board (session_01E3dVhbcYK2W3ZViQknFZyn)

Kept on the session's own branch, `dev-ioxv9i`, for the laptop manager, who reads branches with
`git fetch`. Cloud sessions cannot message it. This page is replaced, not appended to, and each
branch's latest commit message says its own status. Times are Eastern.

## As of Sunday 8 November 2026, about 3 a.m.

Received your message with Alice's walk of dry run 7 (2663f3e0, dev aa4d8582).
**`fix/members-elect-walk` 75c026f6 is READY with all six items**, off aa4d8582, well before
9 a.m. It is not merged. That commit says STATUS READY; the code tip is c1cf71d7, and 75c026f6
adds the README and shots.

`docs/design/members-elect-walk/README.md` has the detail and 79 real-data shots of dry run 7.
They are before and after, at 1280 and 390, light and dark, with Spanish, at 375 where the
walk saw the chip wrap, and at 1024.

| Item | What the branch does |
|---|---|
| 1. Two views | **By last name** and **By county**; By district is gone. The 19 seats not final are said in two places: a fold under Who won the seats ("19 seats not final, in 16 districts"), which names them, and By county's line ("Result not final in District 6 — a recount was requested"). `#pane-edist` and `#tab-edist` open By county; `#of-eld-senate` and `#of-eld-house` are By county's headings. |
| 2. Tab order | My Town · Legislators (406) · Members-Elect (405) · Federal · Executive · Judicial · County. |
| 3. The chip | The Legislators tab's chip, with "Rep.-elect" kept and the word outside it. The lists are in columns of at least 544px, two at 1280, so a chip and its word fit on one line. At 1280 all 405 chips are on one line (dry run 7: 83), with the word beside every chip from 980 to 1440px. At 390, 378 of 405 (dry run 7: 67). |
| 4. The words | RETURNING 230 (206 re-elected to their seat, 24 former); NEW DISTRICT 5; NEW CHAMBER 2 (Creighton, Telerski); NEW 168. A member the rows cannot place gets no word rather than a guess; there are none on dry run 7. The README says what NEW rests on: linked to nobody, against rosters that start in 1999. Spanish drafts: Reelegido/a, Nuevo distrito, Nueva cámara, Nuevo/a. |
| 5. The Senate by county | The Legislators tab's rule, each district under its senator's roster county. Both tabs show the same eight counties with the same counts. |
| 6. A chart on a phone | Each chamber's bar, 10px high, is drawn above its one line in both blocks. The desktop is unchanged. |

**For Alice to say (none blocks the dry run):**
- **The ring** was mocked at 375 and does not read clearly better, so the bar is built. Both
  are in the README's shots.
- **The walk's example of item 4** reads NEW DISTRICT under item 4's own rules, not RETURNING.
  That member-elect sits for one House district and was elected in another. RETURNING there
  would need RETURNING to cover a move within a chamber.
- **The Members-Elect House line on a phone is still two lines** at 390 and below. The options
  are as before.
- **13 chips take two lines at 390** where the Legislators chip takes one. The cause is the
  Secretary of State's longer names ("Mary Ngwanda Georges") and "-elect". The roster's names
  would bring it to 7.
- **On a desktop the lists have two columns** where Legislators has three, so the words fit.
  The page is shorter for it.

**Checks:**
- **Review:** four reviewers, each finding then put to a skeptic on the real data. Six of eleven
  findings were confirmed, and all six are fixed:
  - most words were under their chips on a desktop;
  - "Regresa" told 206 sitting members they were coming back;
  - a reload after picking a view reopened the view the address named;
  - three gaps in the checks.
- **Mutation:** 23 of 24 mutants turn a check red. The one left is a list row as a block, which
  draws the same.
- **`preflight --code`** on c1cf71d7, the code tip: 995 passed, 0 failed, 9 skipped.
- **Stamps:** four files, each one past aa4d8582; `inventory.py` is clean.
- **Sideways scroll:** none from this branch, 320–1280px in both languages. The Spanish
  Presiding Officers case (320–350 and 490–510px) is on dry run 7 too, and is the 11 November
  item.

**Next:**
- The walk list for the next dry run, when you send its address.
- For 11 November, the two pre-existing sideways scrolls, with their verified fixes.

## Earlier, Saturday 7 November, about 10 p.m.

Received your message with Alice's walk items A to D for Sunday's one dry run. **All four are
READY**, well before 9 a.m. They build on `fix/members-elect-polish` 068ed8b0 and are stacked so
that one merge carries all four:

| Item | Branch and tip | Merges | preflight --code |
|---|---|---|---|
| A. The Presiding Officers' sentence gone | `fix/presiding-line` fb7d3e01 | on its own | 990 passed, 0 failed |
| B and C. Members-Elect like Legislators; the seats at the top | `feat/members-elect-tab` 25890848 | carries A | 992 passed, 0 failed |
| D. The map's party totals for the chamber shown | `feat/map-party-totals` 9740b12a | carries A, B and C | 993 passed, 0 failed (on 5acac99d; 9740b12a adds a README note only) |

**To take all four, merge `feat/map-party-totals`.** If D is not wanted, `feat/members-elect-tab`
is A to C, and if only A is wanted, `fix/presiding-line`. Each branch has its own README under
`docs/design/` (`presiding-line`, `members-elect-tab`, `map-party-totals`) with real-data shots
of dry run 6, before and after, at 1280 and 390, light and dark, and in Spanish.

- **A.** The block is its heading and the three chips, in English and Spanish.
- **B.** The Members-Elect tab has three views under a strip like the Legislators tab's:
  - **The views:**
    - **By last name:** party columns, Senate and House apart with counts.
    - **By county:** the Senate by district, because its races name no county.
    - **By district:** each race whole, as before.
  - **The chips:** each one is the Legislators tab's chip, e.g. "Rep.-elect Kristine Trow
    (D - Rock 13)" or "Sen.-elect David Rochefort (R - SD1)". Each carries a word: **Re-elected**,
    **Returning**, **New**, or **New seat**. "New seat" is proposed for the seven sitting members
    elected to another seat, e.g. Creighton.
  - **The 19 seats not final:** said in every view, and named by county and by district.
  - **Links and contact:** only where the file links them; no contact detail. Spanish drafts.
- **C.** "Who holds the seats" is now under the Presiding Officers.
  - **On a phone:** each chamber is one line: "Senate 16 R · 8 D", "House 212 R · 169 D · 1 I ·
    18 vacant". Those are dry run 6's real numbers, the same as your example.
  - **Members-Elect:** the tab gets "Who won the seats" in the same form, with not final and
    nobody on file counted apart.
- **D.** Under the map's legend, on the State House and State Senate layers:
  - **The line:** "STATEWIDE House: 212 Republicans · 169 Democrats · 1 Independent · 18
    vacant".
  - **Where:** on Officials' My Town tab and on the town pages' Map tab.
  - **Not drawn** on the Executive Council and US House layers.

**Checks:**
- **New checks:** `_presiding_chips_alone` (A); `_elect_tab_like_legislators` and
  `_seat_totals_at_top` (B, C); `_map_party_totals` and `_map_totals_published` (D).
- **Mutation:** 29 of 29 mutants on B and C turn a check red.
- **Review:** an adversarial review of B and C, each finding put to a skeptic who reproduced
  it on the real data, confirmed eleven findings.
  - **Fixed:** chips for members-elect with no page drew their name one word to a line, and
    in Spanish By county a label ran past the page's edge at 590–640px. Also fixed: By
    district's heading levels, the strips without JavaScript, and three check gaps.
  - **After the fixes:** no sideways scroll or chip overrun at any width from 320 to 1280px,
    in either language, in any view.
- **Stamps:** the three branches each raised `preflight.py` from .794. The stacked tip carries
  .797, so the merge is conflict-free.

**For Alice to say (none blocks the dry run):**
- **"New seat"** for a sitting member elected to another seat. The alternative is the seat
  they hold, e.g. "Now Hills 30".
- **The Members-Elect House line on a phone is two lines** ("... 1 I/D · 1 R/D · / 19 not
  final"). That is at 320–390px in English and at every phone width in Spanish. The options,
  measured:
  - fold the cross-nominations into one count, which fits 390 in English only;
  - say "3 other", which fits everywhere;
  - keep the two lines.
- **The threshold sentences** (three fifths, veto) are not shown on a phone.
- **/officials is 19 KB heavier gzipped** (92.5 → 111.7) until the tab goes on 2 December.

**Found by the review, pre-existing and live today, not fixed here (for 11 November, fixes
verified by injection):**
- **Legislators tab, By county:** the page scrolls sideways at 840–1220px, by up to 108px.
- **Spanish Presiding Officers:** their labels push the page sideways at 320–350 and
  490–510px.

**Next:** the walk list for Sunday's dry run, when you send its address.

## Earlier, about 6:20 p.m.

Received your message with Alice's answers to "From the walk of dry run 4" (about 5 p.m.), and
dry run 6 (7c76e0a0, dev 92247871) clean.

**`fix/members-elect-polish` 068ed8b0 is READY**, on dev 92247871, for Sunday's one dry run.
Its STATUS commit and `docs/design/members-elect-polish/README.md` have the detail and the
before and after shots.

| Alice's item | What the branch does |
|---|---|
| 1. Tabs cut off | Short labels: Federal (4), Executive (26), Judicial (29), County (80); in Spanish Federal, Ejecutivo, Judicial, **Condados** (drafts). Seven tabs on one line at 1280 and 1440 in both languages, 1,016px and about 979px of 1,132. The panels keep the whole names as their headings. The phone is unchanged. |
| 2. "Your rep" | Kept only on a member re-elected to the seat they hold (`own`, the item `elown`). Gone from Creighton's Senate chip and from anyone not now holding that seat, on town pages, the map and the Members-Elect tab. |
| 3. From 2 December | `/officials#members-elect` opens Legislators and writes `#legislators`, whether the tab is retired by the reader's clock or no longer built. The strip is shown to the reader sent there. |
| 4. Spanish heads | "Elección del {day}", "Toma de posesión: {day}.", drafts. |
| Small ones | A long status wraps in its chip (CACR 13). A long-named member's chip gets its width on that row only (Prudhomme-O'Brien). |

- **Checks.**
  - Two new checks, and four others read the short labels.
  - 24 of 25 mutants turn a check red.
  - Two reviews, with experiments in Chromium on dry run 6, found two blocking and three
    should-fix findings; all are fixed.
  - A sweep of all 320 town pages at 700, 820 and 1280 shows no regression.
  - `preflight --code`: 989 passed, 0 failed, 9 skipped.
- **For Alice to say, not done:**
  - Prudhomme-O'Brien's address breaks onto two lines beside her chip at 1280 and 1440.
  - The English strip still scrolls by up to 40px between 1024 and about 1062px.
  - The My Town card still says "under County Officials".
- **Next:** the walk list for Sunday's dry run, when you send its address; Alice's walk
  findings from tonight, through you.

## Earlier, about 3:15 p.m.

**Section 10 has been walked on dry run 4** (https://ff30d1c7.graniterecord.pages.dev).
Two agents covered every stop, at 1280 and 390. Nothing holds the release.

- **The data held everywhere it was checked:**
  - all 320 town pages' 814 blocks match members_elect.json;
  - all 237 linked members' pages carry one right "Elected" line;
  - all 227 races on the Members-Elect tab add up;
  - no Senate block says "Result not final";
  - CACR 13's status, How It Got Here, Votes card, Learn answer (in English and Spanish) and
    by-the-numbers row are right.
- **No regressions against dry run 2.** Every JS and CSS file is byte-identical, and every
  other difference traces to CACR 13, the members-elect or Feliciano. That includes `/bills`'
  Status filter losing "In Progress" (CACR 13 is now under Died, 1,333) and `/data`'s 1,128 →
  1,130 checks.
- **The list's words are corrected where the page differs:**
  - the map's Senate layer needs two clicks on 19 (as on dry run 2);
  - a member page's heading is the name, with party and seat under it; "(D - Hills 39)" is
    only the browser tab's title. Section 3's four quotes are fixed the same way;
  - Hollis is one of four single-seat recounts, and six blocks name nobody;
  - Baroody's chip is on `/town/manchester-ward-6`;
  - CACR 13's words are in How It Got Here, not the tracker, which shows a red ✕. The Votes
    card is added, and the by-the-numbers line reads "5 of the 18";
  - section 8's "six tabs in view" is now seven, the last cut off;
  - Laura Telerski is the second representative elected to the Senate.
- **New, for Alice to decide**, in the list's new section "From the walk of dry run 4":
  1. **Should-fix:** the Members-Elect tab is cut off to an "M" at 1280 and 1440, in English
     and Spanish, and the tab row scrolls sideways. The fix is a design choice: shorter
     labels, a wrapping row, or the tab after Legislators.
  2. **Should-fix:** with a town saved, find.js's ytMark puts "Your rep" / "Your senator" on
     member-elect chips that link a sitting member's page. In Derry it marks Foote alone of
     eight, and in Antrim Creighton's Senate chip reads "Your rep". The one-selector fix is
     `.elect a::after` in the existing `content:none` rule.
  3. **Should-fix, for the 2 December switch night:** from the reader's midnight,
     `/officials#members-elect` shows six tabs, none selected, and nothing under them. The
     fix: a hidden tab in the address opens Legislators.
  4. **Spanish drafts:** the Mi municipio card's "Elegidos el" (plural) heads one senator, and
     "Asume el cargo" (singular) heads a list. A neutral wording is suggested for the
     translation work.
- **On your word, this session can have 2 and 3 ready on a branch today**, and 1 once a
  design is chosen. Each would come with a check and a browser walk.

## Earlier, about 3 p.m.

Received your message with Alice's answers, and dry run 4 (ff30d1c7, dev 9052784d) clean.

- **The walk list now targets dry run 6** (953fc547):
  - "Where to walk" names dry run 6, and keeps dry run 4's address for comparison.
  - Section 3 has the directory's new count line: 97 and 1,688, "The 34 who sat in both
    chambers are under each."
  - Section 5 has `/officials#of-county-hillsborough`, Sheriff Brian J. Newcomb.
  - Section 8 has the reworded second reason, in Alice's words.
  - "For you to decide" becomes "Your answers", with each answer.
  - Those three stops come from the code and Alice's words. 953fc547 and cfbdccbf were not
    on GitHub yet at this commit; 2e884fc1 was.
- **Section 10 is being walked on dry run 4 itself.** Two agents are on it: one on every
  members-elect stop, the other on CACR 13 and the code map's open checks (the Spanish
  Members-Elect tab, the 'Your rep' pill, the header search, regressions against dry run 2).
  The result follows in a commit of its own.
- **Logged for 24 November:**
  - Michael Downing's party by chamber, on a branch off dev after the release (task 33);
  - the County Officials source line, naming Feliciano's and Newcomb's rows, with the
    Spanish line as a draft (task 34). The Spanish line is es.json's, which this session had
    been told not to touch. It takes your message as the go-ahead for that one draft line
    only.
- **`fix/former-directory-both`** is merged as 953fc547. Thank you for the stamp note: .792
  on dev, with build_indexes .26.

## Earlier, about 2 p.m.

- **dev reached 9052784d** at about 1:40 p.m. That is e10505d2 plus CACR 13's count.
- **Section 10 is now drawn from that data.**
  - A scratch build of the members-elect with your real recount list gives exactly 405
    elected (213 sitting, 24 returning, 168 new) and 19 not final. It used dry run 2's roster,
    and nothing under corrections/ was written.
  - Rockingham 13 holds two seats, which answers the question below. So Derry shows 8
    winners: Trow, J. Carreau, Glavin, Hesse, Foote, Marshall, H. Carreau and Provencher.
  - The four returning winners held are the four close ones named below.
  - No stop in the list depends on a held winner.
- **CACR 13 joins section 10**, in three places:
  - `/bill/2026/cacr13`: "Passed both chambers, not ratified by the voters", and the Voters
    step "Not ratified, 365,359–198,791";
  - `/learn/county-government` and `/es/learn/county-government`, "What does the register of
    probate still do?": "… it did not reach the two thirds it needed: 64.8% of those voting
    on it voted yes.";
  - `/learn/by-the-numbers`: a Not Ratified row.

  These come from the code, before dry run 4 was up. "What cannot be walked yet" loses the
  register of probate paragraph and the members-elect.
- **Next:** walk section 10 on dry run 4's own address when you send it, then correct the
  list and push.

## Earlier, about 11 a.m.

Received the laptop manager's messages of 7 November, through the one saying members-elect
joins this weekend's release at Alice's word.
- Dry run 3 (6e462616) is clean but superseded. Dry run 4 of dev e10505d2 will be the walk
  candidate.
- e10505d2 is d2a8e027 plus three things:
  - Rich Green unlinked;
  - data/election-2026-sos merged;
  - the recount deadline 2026-11-06, with the 16 recounts holding 19 seats.
- The ask: add the members-elect stops to the walk list.

### The members-elect stops: walk list section 10, a draft for dry run 4

- **Written before dry run 4 was up**, and marked so in the list. Two agents prepared it.
  - One mapped every element a reader sees from the code. The data branch changes no page
    code, so this holds for e10505d2.
  - The other built the members-elect file in a scratch tree from d2a8e027 and
    data/election-2026-sos (58b8c6fc), with dry run 2's roster JSON. It applied your two
    unpushed changes in memory only: the deadline 2026-11-06, and Rich Green null.
- **Its counts, with no recounts entered:** 424 elected, as 215 sitting, 28 returning and 181
  new.
  - Your 405 / 213 / 24 / 168 differs by exactly the 19 held seats.
  - So the held winners are 2 sitting, 4 returning and 13 new.
  - The 16 recounts are not in git anywhere, so which seats are held is unseen until dry run
    4.
- **The stops:**
  - `/town/derry`: Rockingham 13, 10 seats, recounted and part held, with sitting, returning
    and new in one block. Senate 19, and "Last election: November 3, 2026" on its Vote tab.
  - `/town/derry#map`.
  - `/town/hebron`: Grafton 11, a single-seat recount, 6 votes apart. `/town/hollis` is the
    other one, Hillsborough 45.
  - `/legislator/benjamin-baroody-hills-39`: returning, and the line names Hillsborough 16.
  - `/legislator/charlotte-dilorenzo-rock-10`: returning to the same seat.
  - `/town/nashua-ward-5`: Rich Green as a plain chip; `/legislator/richard-green-sd-6` has no
    "Elected" line.
  - `/officials#members-elect`: Members-Elect (405).
  - The Senate side: `/town/amherst` (Chandley returning) and `/town/antrim` (Creighton, a
    representative elected to the Senate). No Senate race says "Result not final".
- **To ask you:** does Rockingham 13 hold one seat or two?
  - With one, Brian Chirichiello (returning, +12) shows. With two, he is held too.
  - The four returning winners within 18 votes are Chirichiello, W. Packy Campbell, Andrew
    Dorsett and Stephen Spratt. They may well be the four held returning winners, so the
    list avoids them as examples.
- **Things a reader may ask about.** These are as the code draws them, not faults:
  - a single-seat recount's block heads "Elected November 3, 2026" over nobody;
  - a part-held recount does not say how many seats are held;
  - chips use the ballot's spelling;
  - "Serving now" can sit over "1 seat vacant" (`/town/new-castle`).
- **Also, from the code map, to check on dry run 4:**
  - In Spanish, "Elegidos el" (plural) heads a single senator, and "Asume el cargo"
    (singular) a list. The `/es/` Members-Elect tab is unlisted while es.json says
    `offered: false`.
  - The 'Your rep' pill may land on a member-elect chip that links a saved town's member's
    page. This was not seen in a browser.
  - A new member-elect is not in the header search: "Green" finds former Sen. Richard Green.
- **On dry run 3 itself** (6e462616), Feliciano's row sits under the roster's source line, as
  item 3 of "For you to decide" said. That was first seen by building the code; now it is
  seen on the deployment.
- **Next:** walk section 10 on dry run 4's own address when you send it, then correct the
  list and push.

## Earlier on 7 November, about 9 a.m.

Received the laptop manager's messages of 7 November, through the one saying:
- dry run 2 (run 42368200550, dev e308cee5) is clean;
- dry run 3 (run 42372029110, dev d2a8e027) is running, as the release candidate for the
  owner's walk tonight;
- please write the walk list against dry run 2's preview.

### The owner's walk list: `docs/release-11nov.md`, rewritten

- Every stop was opened on dry run 2's own address, **https://4e2d47d7.graniterecord.pages.dev**,
  never the alias, and each says what that page showed.
- The second batch is folded into the stops where a reader meets it, not kept in a section of
  its own.
- The order is laptop first and phone last, so the window is resized once. There are ten
  sections, with times; the ★ stops are the half-hour walk.
- Dry run 3's one change, Leslie Feliciano as Strafford's District 1 commissioner, is a ★ stop
  in section 5.
- **Corrected at about 9 a.m. after two checks of the list itself.** One fact-checked 104
  claims against dry run 2, dry run 183 and live. The other followed every stop literally, as
  the owner would.
  - Four statements were wrong, and are fixed:
    - the ★ walk is half an hour, not twenty minutes, and now includes dry run 3's stop;
    - Hart's Location typed on a laptop already worked on dry run 183, so it moved to the
      phone with O'Neil;
    - the directory lists all 34 people under one chamber, not eight (8 missing from the
      Senate list, 26 from the House's);
    - a plain Back, not a reload, leaves a bill drawn open in the list.
  - The rest were steps left out or words that mislead, and are fixed too: the folded
    proceedings.csv columns, the button names, closing a pane on a phone, the `?v=1` advice
    (it breaks an address with ? or #), and which stops only check an earlier dry run's slip.
  - Not taken: "seen by building the tab" in item 3 stands. This session built County
    Officials from d2a8e027's own code and corrections file, which the checker did not find on
    disk.

### Dry run 2 (dev e308cee5): the walk

**Nothing found holds the release.**

- **Every redirect rule: 631 of 631.**
- **Every stop of the walk list holds as written.** The list carries the exact words seen.
- **New from this walk:**
  - At phone width a record's pane (Cite, Testify) lies over the buttons below its own until
    it is closed. Dry run 183 does the same, and live does not. It is a nit.
  - `/bills#2020/HB703` shows the 2025–2026 list, on dry run 2 and on live. It does not open
    2025's bill, as the 3 a.m. list said. This is on live, for 24 November.
  - The status box on `/es/` has an English sentence that none of the new note's four reasons
    covers. Also on live.
- **For dry run 3, seen by building County Officials from d2a8e027's own code:**
  - Leslie Feliciano's row sits under the one source line for all 80 rows: "read from the
    Secretary of State's county roster for 2025–2026, dated December 5, 2024; read October 9,
    2026 … this is the roster read before it."
  - Her row comes from Strafford County's own list, read 6 November, and the roster names Joe
    Pitre.
  - `officials_tabs.county` never draws a row's own source.
  - A fix needs a Spanish line in `es.json`, which is not this session's to edit. It is in
    the walk list as "For you to decide", item 3.
- **The four deeper walks are done.** Each finding was put to a skeptic, and all ten below
  survived; one survived only in part.
  - **Regressions against dry run 183: none.**
    - 34 pages were compared at 1280, and 13 at 390, with no page errors.
    - Headers, CORS, the sitemap, robots.txt, the feeds and the data files were compared too.
    - `/build.json` names e308cee5, and 50 steps match dry run 183's.
  - **Back and the not-found page: every road in the README passes**, at both widths, light
    and dark. 98 not-found addresses were tried, and none ever asks for its own address.
    Two nits, on rare roads:
    - After Back, a term whose bills fail to load reads "Not in the 2019–2020 term" for HB
      703, which is in it. This happened before the batch too.
    - New: a term chosen with a bill open is lost by Back, Forward, Back on a slow network,
      if the bills have not arrived.
  - **Search: one should-fix, on live already, and three nits.**
    - Should-fix: a place's apostrophe drops its bills. "Wentworth's Location" finds no bill,
      and "Wentworths Location" finds 4.
      - The cause: `build_search_index.py`'s `key()` drops the "'s", and app.js's `qnorm`
        keeps it, so a typed possessive matches only a title.
      - The batch made it no worse, and now puts the place first. It is in the walk list's
        "Already on live".
    - New nit: "U.S. 3", "U.S. 1", "U.S. 2", "U.S. 202" and "U.S. 302" now find nothing in the
      bill search and on `/search`. Dry run 183 and live found 6, 7, 4, 1 and 1.
      - `numberForm` folds any dotted letters before a number into a bill kind.
      - a38ffbe8's message names this as known. The fix: fold only a kind in FBILLKIND, as
        the header's `findBill` does.
      - This is the one ordinary search that got worse. It is in the walk list's nits.
    - New nit: two of the batch's patterns keep the quadratic `\s*x?\s*` shape that a38ffbe8
      took out of RSA_PARAGRAPH: the dotted-letters pattern, in app.js and find.js, and
      find.js's FLSR.
      - 16,000 pasted spaces cost 750 ms per keystroke in the header, against 13 ms before.
      - The fix: `\s*(?:\.\s*)?` and `\s*(?:-\s*)?`.
    - Nit, as on live: the bill search's sponsor offer misses "O Neil", "O Connor" and "D
      Allesandro", which the header now reads.
  - **The Spanish note: one should-fix, new, and three nits.**
    - Should-fix: its second reason says offices and committees stay as the record prints
      them. `/es/officials`, right under it, gives every office in Spanish (Gobernador,
      Comisionado(a), …).
      - The wording is the owner's approved draft, so the change is hers. It is in the walk
        list as "For you to decide", item 4, with one way to word it.
    - New nit: its fourth reason reads as a complete list of the pages still in English, but
      leaves out About, Data, town pages, the session lists and the towns directory.
    - Nit, as on live: `/es/resources`' "El registro en cifras" card goes to the English
      page with no "(en inglés)" mark.
    - Nit, mostly refuted: `/es/` search rows for English guides carry English titles. A
      reader who chose Spanish still lands on the Spanish guide.
  - None of these was fixed here.
    - The search and Spanish ones are in other branches' files, and the Spanish wording is the
      owner's.
    - The two Back nits and the patterns are for 24 November, unless you want any of them
      sooner.

### Branches

| What | Branch | Status |
|---|---|---|
| The former-members directory lists a person who sat in both chambers under each | `fix/former-directory-both` 1c740815 | **READY**, offered on your word. It is dev d2a8e027 plus the fix, so it is in neither dry run 2 nor 3. Over dry run 2's `former.json`: 97 former senators and 1,688 former representatives, with 34 people under both. The search groups them 89 / 1,662 / 0. Under the other chamber a row has that chamber's title and its years first, with no party or seat ("Rep. Michael Downing R" would be wrong). Two reviews; every should-fix finding is fixed. `preflight --changed`: 915 passed, 0 failed, 76 skipped. Its README has before and after shots of dry run 183's page. Whether it rides this release or 24 November is the owner's call, in the walk list. |
| Back keeps the search; the not-found page finds the bill and the town | `fix/bill-back-notfound` c7d6041e | Merged by you into dev e308cee5, and walked on dry run 2. |

### Noted from your list for after this weekend

- **CORS for `schema.json` and `people.json`:** already in the release, as you say. Nothing to
  do.
- **Healthchecks noise** (task 28). From reading the code:
  - The preview sender reads `dry-run.graniterecord.pages.dev`. That has a changes file only
    on a night a dry run ran.
  - So at noon it raises `tonight` and pings `/fail` on any day it has been given a
    `HEALTHCHECK_URL`.
  - The plan:
    - the preview sender never pings (`ping()` returns early on a preview-only var in
      `[env.preview.vars]`);
    - the README's secrets table says `HEALTHCHECK_URL` is production's only;
    - a preflight check holds both.
- **The night-warnings check becomes "Night waiting for your approval"** (task 29). Only a
  warning that holds a night for approval pings it (`nightly.py`, `nightly.yml`).
- **After the webinar** (task 30), sample the two groups against the chaptered laws, and bring
  a fix with counts:
  - the 253 laws with a Law date before the Governor's;
  - the 1,618 with none.

  HB 703 of 2020 is one of the 253: its Law step is its effective date, Jan 1, 2020, before
  the Governor's Feb 10.

## Next

- **On your word:** a fix for "U.S. 3" (fold only a real bill kind) and for the two quadratic
  patterns. Both are small, in app.js and find.js. They can be ready for a dry run today if
  you want them in this release; otherwise they wait for 24 November.
- **On your word:** `fix/former-directory-both`.
- **Monday:** the Videos wording.
- **After the weekend:** tasks 28 and 29; task 30 after the webinar.
- **24 November:**
  - night-clock, then lsr-accept;
  - the check_live mode that walks every redirect;
  - the tab-anchor follow-ups;
  - the HB 703 nits;
  - the bill search's tab title;
  - a sitting member's joined number answering 404 as JSON;
  - `careers.json`'s two same-chamber joins of namesakes;
  - Michael Downing's party per chamber;
  - the motion movers credited to namesakes (Seth King 2006, Butler 2014, Grossman, Schultz);
  - `/bills#2020/HB703`;
  - the phone-width pane;
  - the County Officials source line, if it does not go sooner;
  - a place's apostrophe in the bill search; "U.S. 3" and the two patterns, if they do not go
    sooner; the sponsor offer's "O Neil";
  - the two Back nits;
  - the fix/bill-back-notfound deferrals in its README.
- **December:** outage recovery.
