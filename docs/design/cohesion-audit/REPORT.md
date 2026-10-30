# Cohesion audit — the 1 November release candidate

Read-only audit of https://dry-run.graniterecord.pages.dev, 30 October 2026.
Nothing on the site was changed. Screenshots are in `shots/`, named
`<page>-<width>-<theme>-<what>.jpg`.

## For the owner: the ten fixes that would show the most

The site is in good shape on the things that are hardest to fix late: no text
anywhere fails contrast, in light or dark; no page scrolls sideways at phone,
tablet or desktop width; and every colour on every page is one of the site's
own colours. What is left is the same thing drawn in different ways on
different pages. Ten fixes would close most of it:

1. **Give each heading level one look.** A bill page's tabs use five different
   heading styles; on the guides the step titles are bigger than the section
   they sit in; on Learn and /data a section and its subsection look identical.
2. **Write a term's years one way: "2025–2026".** About half the site writes
   "2025-2026" with a hyphen, sometimes on the same page as the dash.
3. **Write times one way: "6:30 PM".** The guides and the home page's webinar
   say "6:30 p.m."; everything else says "10:00 AM".
4. **Let people scroll the Learn tables on a phone.** Fourteen tables on
   *By the Numbers* run off the right edge with no sign there is more, and a
   keyboard cannot reach them. /data already does this right; copy it.
5. **Name the town on a town's page.** /town/concord is titled "Officials" in
   the browser tab, in a shared link and to search engines, and tells search
   engines it is the Officials page.
6. **One "selected" look for buttons that switch views.** Officials shows a
   solid green "selected" and a pale green one on the same page, and the
   Calendar adds round pill buttons next to square ones.
7. **One search box.** Seven hint wordings ("Bill number or key words",
   "Bill number or title words", "HB 1442, or words"…), three heights and two
   colours.
8. **The same buttons on every record page.** "Report a problem" is missing on
   study committees and session days, and "Testify" looks pressed or switched
   off when it is neither.
9. **Fix the citation dates.** The APA and Chicago forms borrow MLA's
   "30 Oct. 2026"; both should read "October 30, 2026".
10. **Same words for the same thing.** A recording with no marked moment is
    described two ways; a bill that ended is "Died" on a chip and "Killed" on a
    committee's page; the play button has three labels.

The release session (app.css, app.js, the shell and the builders) owns most of
these. The guides session owns 4 and shares 1, 3, 6, 7 and 10. Most are small:
a style rule or one word list, not a redesign.

---

## How this was done

- Every kind of page, at 390 and 1280 wide (768 where the layout changes:
  home, Bills, a bill, Officials, Calendar), light and dark, with Playwright
  in Chromium. One page at a time, GET only; nothing was posted to the follow
  or report endpoints.
- Each page and each of its tabs was measured: sideways scroll, clipped
  text, contrast of every piece of text against its real background, tap
  targets under 24 px, colours not among the `:root` tokens, font sizes not on
  the type scale, heading levels, and every date, time, count, empty state and
  "as of" line in the text. Then the screenshots were read by eye.
- Judged against `src/pages/components.js` (one date helper, month first, and
  `clock()` giving "1:30 PM"; one chip), the tokens in `app.css` and the
  shell.
- 126 page-width-theme views, 34 pages (list at the end).

**What came out clean.** 0 text below 4.5:1 (3:1 for large) in either theme.
0 pages wider than the screen at 390, 768 or 1280. Every colour is a token
apart from the browser's own default form controls. Fonts all on the scale
except the 12 px tab counts (I-5).

**Limits.** No committee page I sampled (H34, S10, ss57, ss1727, House
Session Days) had a Videos tab, so it is not covered. Live Now did not appear
(out of session), so nothing is reported for the live layer. The follow
sign-up endpoint answers GET with 405, so only the manage page was seen, and
only without a valid link. The Spanish pages were not audited.

**The preview is a step behind `dev`.** `dev`'s last merge (d83e8ac, the
guides/map polish) already fixes two things the preview still shows: the map's
"Fit" button (now the same icon as the seating chart's) and the Laws page's
"New Hampshire laws" (now "New Hampshire Laws"). They are not reported below.
Anything in the guides or map area should be rechecked on `dev` before it is
fixed.

**Owners** follow the brief: *release* = app.js, app.css, the shell, the
session and page builders; *guides* = guides, Learn, Resources, the map;
*API* = /data. The follow pages (`workers/follow/page.js`) are in nobody's
list; I have put them with the release session for the manager to confirm.

**Effort**: S = an hour or two, one place; M = several places or a builder
change; L = a pattern across the site.

---

## BROKEN — wrong, unreadable, cut off or inaccessible

### B-1 Guide steps' titles are bigger than the section they are in
- **Where:** every guide; `guide-vote-390-light-steps.jpg`,
  `guide-vote-390-light-head.jpg` (390 and 1280, both themes).
- **What:** "Step by Step" and "At a Glance" are h2 at 19 px; each step's
  title under them is h3 at 20 px. The outline reads upside down.
- **Fix:** step titles to `--t-h3` below `--t-h2`, as the bill and committee
  pages already do. Recheck on `dev` first: item (d) of the guides/map polish
  split the steps into parts.
- **Owner:** guides. **Effort:** S.

### B-2 Learn's tables run off a phone's screen and a keyboard cannot reach them
- **Where:** /learn/by-the-numbers, 390 both themes;
  `learn-numbers-390-light-table.jpg`.
- **What:** 14 tables (`div.l-tablewrap`) are 428–811 px wide inside a 364 px
  box. They scroll sideways, but with no edge or shadow to say so, and the
  wrapper has no `tabindex`, role or name, so keyboard users cannot scroll it.
  The first table shows three of its columns and cuts the box's right edge.
- **Fix:** /data's `div.covwrap` already does it right: `role="region"`,
  `tabindex="0"`, an `aria-label`. Give `.l-tablewrap` the same, plus the scroll
  edge cue the tab rows are getting in the 11 Nov polish.
- **Owner:** guides. **Effort:** S.

### B-3 The follow page says two things at once
- **Where:** /api/follow/manage without a valid link, all widths and themes;
  `follow-manage-390-light.jpg`, `follow-manage-1280-dark.jpg`.
- **What:** "This link is missing its private part…" and, under it, "Opening
  your page..." which never changes. The page also loads none of the site's
  fonts, so the wordmark and heading fall back to Georgia (Times here) and the
  heading is 26 px, off the scale.
- **Fix:** when the token is missing, hide "Opening your page…" (the `missing`
  branch in `page()`'s script already disables the buttons; hide the line
  too). Load Source Serif 4 and Public Sans as the site does, or name system
  fonts on purpose.
- **Owner:** release (to confirm). **Effort:** S.

### B-4 A town's page calls itself "Officials"
- **Where:** /town/concord (→ /town/concord.html), every town.
- **What:** `<title>Officials | Granite Record</title>`, `og:title`
  "Officials", and `<link rel="canonical" href="https://graniterecord.org/officials">`.
  The sitemap lists all 320 `/town/*` addresses, while each one tells search
  engines it is the Officials page. A shared link to Concord shows "Officials".
- **Fix:** title "Concord — Officials | Granite Record", og:title to match,
  canonical to the town's own address.
- **Owner:** release. **Effort:** S.

### B-5 APA and Chicago citations use MLA's date
- **Where:** "Cite this page" on every page; `bill-390-light-cite-open.jpg`.
- **What:** APA reads "Retrieved 30 Oct. 2026, from …" and Chicago "Accessed
  30 Oct. 2026." Those are MLA's form. APA 7 writes "Retrieved October 30,
  2026, from"; Chicago "Accessed October 30, 2026." MLA's is right as it is.
- **Fix:** `dateWords(iso, "full")` for APA and Chicago.
- **Owner:** release. **Effort:** S.

### B-6 Glossary-term buttons are too small to tap
- **Where:** a bill's suffix ("A", "FN") on the bill page and Learn;
  `abbr.term > button.termbtn` measured 12×30 px (Learn) and 18×31 px (a
  1995 bill) at 390.
- **What:** under the 24 px minimum (WCAG 2.5.8), and right next to the bill
  number, which is itself a target.
- **Fix:** pad the button to at least 24×24 with a transparent hit area
  (`::after` inset), keeping the letter's look.
- **Owner:** release. **Effort:** S.

### B-7 On a member's Votes tab the faded title sits on the next line
- **Where:** a legislator's Votes tab, 390; `legislator-390-light-votes-fade.jpg`.
- **What:** each bill title is cut at two lines with a fade, but the faded
  third line touches "Override the Governor's Veto" below it, so it reads as
  text printed over text.
- **Fix:** clamp with `-webkit-line-clamp` and an ellipsis, as truncation is
  done elsewhere, or keep the fade and add space below it.
- **Owner:** release. **Effort:** S.

---

## INCONSISTENT — two patterns for one thing

### I-1 Section headings: one level, many looks  *(release + guides, L)*
| Page | Level | Look |
|---|---|---|
| Bill, Summary tab | h2 | 19 px serif, Title Case, left column ("How It Got Here") |
| Bill, Bill Text / Reports | h2 | 20 px serif, CAPITALS ("BILL TEXT", "HOUSE FINANCE COMMITTEE") |
| Bill, Sponsors | h2 | 20 px CAPITALS with a bare count ("REPRESENTATIVES 6") |
| Bill, Documents | h3 (no h2) | 14 px sans CAPITALS ("THE BILL", "CALENDARS") |
| Bill, Related | h2 | 16 px sentence case ("Filed before and after") |
| Home, 390 | h2 | as typed: "Coming up" beside "Latest Activity" (CAPITALS at 1280) |
| Committees index | h2 | "HOUSE" 20 px CAPITALS beside "Statutory and study committees" 16 px |
| Learn, /data | h2 and h3 | both 19 px, same weight — cannot be told apart |
| About | h2 | 24 px, stacked (others 19 px in the left column) |
| RSA chapter | h1 → h3 | sections are h3 with no h2 |

Shots: `bill-1280-light-summary-head.jpg`, `bill-1280-light-reports-caps-heading.jpg`,
`bill-1280-light-documents-small-caps-heading.jpg`, `home-390-light-coming-up-case.jpg`,
`committees-390-light-index.jpg`, `learn-bill-1280-light-headings.jpg`, `about-1280-light.jpg`,
`search-390-light.jpg` ("How-To Guides 2" beside "Statutory and study committees 9").

**Fix:** two heading treatments, written down in app.css beside the tokens:
the *section* heading (serif `--t-h2` / `--t-h3`, Title Case, as the bill
Summary and committee pages do) and the *label* (`--t-part`, CAPITALS, letter
spaced) for a group inside a section. Every tab pane opens with a section
heading; labels never stand in for one. Then:
- h1 Title Case everywhere: "Calendars and Journals of the General Court",
  "The Whole Record, as Lists", "Statutory and Study Committees".
- h3 always smaller than h2 (Learn, /data, guides — see B-1).
- Home's section titles typed in Title Case, so 390 matches 1280.

### I-2 A term's years: hyphen or dash  *(release, M)*
- "2025-2026" with a hyphen: the term menu (Bills, a member's page, a
  committee), "2,243 bills in the 2025-2026 term", "No bills prime sponsored
  in the 2025-2026 term.", "591 of 591 recorded votes in 2025-2026", the
  committees index ("34 session days in 2025-2026"), the directory.
- "2025–2026" with an en dash: the breadcrumb, a member's "In the 2025–2026
  Term", Officials, "House, 2015–2026", Learn's tables.
- Shots: `legislator-390-light-head-term.jpg` (both on one screen),
  `bills-1280-light-search-filters.jpg`, `committees-1280-dark-index.jpg`.
- **Fix:** one helper (`termWords`, beside `dateSpan`) that every builder and
  app.js use; en dash, as `dateSpan` already does for days.

### I-3 Times: "10:00 AM" and "6:30 p.m."  *(release + guides, S)*
- `clock()` gives "10:00 AM", and the bills, committees, calendar and
  session days use it.
- "6:30 p.m." on the home page's webinar notice
  (`home-390-light-webinar-time.jpg`); "8:30 a.m.", "4:30 p.m.", "5 p.m." in the
  guides (property tax relief, how to vote).
- **Fix:** guides and notices write "8:30 AM", "5 PM" (decide whether a whole
  hour keeps ":00"; `clock()` keeps it, so "5:00 PM").

### I-4 Dates: the same kind of list, different forms  *(release, M)*
- **Lists of days:** session index rows "Aug 19, 2026"; a committee's
  meetings "Friday, October 23, 2026 10:00 AM"; a study committee's the same
  long form; the home page's "FRI, OCT 23". Pick one for a list of days (the
  long form reads best in a list of a committee's meetings; the medium form
  for a list of session days is fine if that is a rule, but write it down).
- **Dates in capitals:** home's Latest Activity ("FRI, OCT 23"), a bill's
  Reports tab ("JAN 27, 2026"), the Calendar's list view ("MONDAY,
  OCTOBER 26"), while the Calendar's week view says "Monday Oct 26".
  Capitals make a date harder to read; drop `text-transform` on dates.
- **Joining a date and a time:** "Jan 20, 2026 at 11:00 AM" (bill hearings),
  "Friday, October 23, 2026  10:00 AM" (committee meetings, two spaces, no
  word), "House Finance · Friday, October 23, 2026 · executive session"
  (recording caption). Use " at " everywhere.
- Shots: `session-index-1280-light.jpg`, `committee-1280-light-meetings.jpg`,
  `home-390-light-latest-activity-caps-dates.jpg`,
  `bill-1280-light-reports-caps-heading.jpg`, `calendar-390-light-list.jpg`,
  `calendar-390-light-week.jpg`.

### I-5 Counts: five ways to write a number beside a label  *(release, M)*
- "Legislators (406)", "How-To Guides (49)" — tab, in parentheses (Officials,
  Resources).
- "Votes 2", "Meetings 45" — tab, number in a 12 px pill (bill, legislator,
  committee). 12 px is under the 13 px floor (`--t-label`).
- "REPUBLICANS — 16", "Senate — 24" — heading, em dash (Officials).
- "REPRESENTATIVES 6", "Members 24", "Senators 7", "Bills 4,045",
  "House Calendars 1,590" — heading, bare grey number.
- A tab with nothing has no count ("Prime sponsored") while its neighbours do —
  fine — but a 1995 bill's **Hearings** tab has no count although it lists
  five hearings (`bill1995-390-light-hearings.jpg`).
- **Fix:** tabs use the pill (at 13 px); headings use the bare grey number
  (`.n` style of "Members 24"). No parentheses, no dashes.

### I-6 Buttons that switch a view: three looks  *(release + guides, S)*
- Solid pine when chosen: Officials' "By last name / By county / By seat",
  Calendar's "List / Week / Day" (`.wbtn.sel`, `.calviews`, `.wkchips`).
- Pale pine-soft with a pine edge: the map's "State House / State Senate…"
  and "Town names / District numbers / No labels" (`.vbtn.sel`, `.vtog.sel`).
  Same page as the solid ones.
- Round pills: the Calendar's "Both chambers / House / Senate" — the only
  999 px-radius buttons on the site, beside the square List/Week/Day.
- Shots: `officials-768-light-map-toggles.jpg`,
  `officials-390-light-legislators-counts.jpg`, `calendar-1280-light-list.jpg`.
- **Fix:** one segmented control, solid pine when chosen; give the map's two
  rows and the Calendar's chamber row the `.wbtn` look.
- **Tab rows** behave two ways on a phone: bill/Officials/committee tabs
  scroll in one line; Resources' tabs wrap onto two centred lines ("How-To /
  Guides (49)", `resources-390-light-tabs.jpg`). Make Resources scroll too.

### I-7 Search boxes  *(release + guides, M)*
- **Hint text, one per page:** "Bill number, topic, name or town" (home),
  "Bill number or a few words" (Bills, 390), "Bill number or key words"
  (Bills, 1280), "Bill number or title words" (a bill's page), "HB 1442, or
  words" (a member's Votes), "HB 1234, or Judiciary" (Calendar), "Your town or
  a legislator" (Officials), "For example: renew my license" (Resources),
  "Chapter, section or key words" (Laws), "Name, county or seat" (seating).
  The Bills page says it two ways depending on width.
- **Size and colour:** Officials' box is 20 px text and ~52 px tall; the
  others are 16 px and ~44 px; a member's Votes box is grey-filled where the
  rest are white.
- **Example bill numbers:** HB 1, HB 1234, HB 1442.
- Shots: `bills-390-light-search-cards.jpg`, `bills-1280-light-search-filters.jpg`,
  `bill-1280-light-summary-head.jpg`, `legislator-390-light-votes-fade.jpg`,
  `officials-390-light-town-search.jpg`, `calendar-1280-light-list.jpg`.
- **Fix:** one box (white, 16 px, 44 px); hint words from one list in
  `words/`, "Bill number or words" for every bill search, one example bill.

### I-8 The buttons on a record's page  *(release, M)*
- **Which buttons:** a bill has Cite / Follow / Testify / Print / Share /
  Report; a committee and a member have Cite / Follow / Share / Report; a
  study committee, a session index and a session day have only Cite / Share;
  Learn, Laws, Calendar only Cite. About says "use the *Report a problem*
  button on a bill's, legislator's or committee's page" — so a mistake on a
  session day has no button. Add Report a problem to every record page (study
  committee, session day, RSA chapter).
- **Where Cite sits:** right column beside the title (bill, committee, session
  day); top right above the h1 (/data); under the lead (Learn, Laws, Calendar);
  beside "On this page" (guides) (`data-1280-light.jpg`,
  `session-day-1280-light.jpg`, `guide-vote-390-light-head.jpg`). On an RSA chapter at 390, Cite and Follow are
  pushed to opposite edges rather than the bill's two-column grid
  (`rsa-91a-390-light.jpg`).
- **Testify:** grey-filled while its siblings are outlined, so it reads as
  pressed or switched off; it is a working opener that says testimony has
  closed (`bill-1280-light-summary-head.jpg`). Draw it like the others, and say
  "Testimony closed" on the button if that is the point.
- **Other button looks:** "Email the 24 members of this committee" is a small
  pine-text outline found nowhere else (`committee-1280-light-head.jpg`).
- **Menus:** the term and order menus are ~30 px tall on desktop (committee,
  session index, Bills' sort) beside 40–44 px menus and buttons.
- **Checkboxes:** native 13 px boxes on Bills and Laws filters; custom
  coloured boxes on the Calendar.

### I-9 Cards that are links, and the line under a title  *(release + guides, M)*
- Three link-card looks: home's (icon, sans pine title), the committees
  index's (ink sans title, not coloured as a link), Resources' (grey round
  icon, underlined serif title). Shots: `home-1280-dark-top.jpg`,
  `committees-1280-dark-index.jpg`, `resources-390-light-tabs.jpg`.
- The line under a page's title is serif `--t-lead` on Officials, a committee,
  a bill, Learn, Laws; it is 16 px sans on the Committees index
  (`committees-1280-dark-index.jpg`). Laws then adds a second paragraph at the
  same lead size under its search box, competing with the first
  (`laws-1280-light.jpg`).
- **Fix:** one `.linkcard` (home's is the most complete); the Committees lead
  in `--t-lead` serif.

### I-10 Where you are: breadcrumbs and "On this page"  *(release + guides, M)*
- **Breadcrumbs, three styles:** 16 px with chevron icons and a rule under it
  (bill, committee, session day); 14 px with "›" and no rule (RSA chapter,
  `rsa-91a-1280-light.jpg`); a crumb merged into a tab row (Learn and guides:
  "Resources › How-To Guides | Learn | Official Sources",
  `learn-bill-1280-light-headings.jpg`).
- **The last crumb** is the page's name on a bill ("HB 1710-FN") but a type
  on a committee ("House Committee"), a member ("Representative") and a
  study committee ("Statutory Committee"). The session index's crumb says
  "House" while its title says "House Session Days".
- **"On this page," three ways:** a sticky left list (Learn), a fold-out card
  with counts (session day, "On this page 25 bills"), a dropdown button
  (guides, /data).
- **Fix:** one breadcrumb (the bill's); last crumb = the page's own name. Pick
  the dropdown for "On this page" on phones and the sticky list on desktop, for
  every long page.

### I-11 Same thing, different words  *(release + guides, S each)*
| Thing | Wording A | Wording B |
|---|---|---|
| A recording with no marked moment | "Play from the start · scheduled 10:00 AM (exact moment not found)" — bill Hearings | "no moment in this recording has been identified yet" — committee meeting, lower case, no full stop |
| The play button | "Play" (home) | "Play the recording" (committee, session) / "Play public hearing on this bill — from 01:14:38" (bill) |
| A bill that ended | chip "Died" (Bills) | "Killed:" (committee meeting card) / "stopped here" (rail) |
| A kind of meeting | chip "Executive Session" | "executive session" in the same card's caption; Learn's cards "Public hearing", "Executive session" |
| A guide's name | h1 "How to Vote in New Hampshire", search "How to Get a Hunting License…" | Resources and home "How to vote" |
| A source date | "Checked against its sources October 11, 2026." (guides) | "read October 9, 2026" (Officials), "Taken from the General Court's database on October 26, 2026." (Laws), "Data rebuilt October 30, 2026." (footer) |
| Nothing to show | "No meetings shown." / "No report is on file." | "Nothing on this day matches the filters." / "None of the 18 meetings this week match." / the heading "NO BILLS OR MEETINGS ON RECORD" |
| Phone numbers | "603-271-3165" (committee) | "(603) 271-2121" (Officials) |
| Apostrophes | curly "Court’s" (footer, cite note) | straight "General Court's" (Laws, About, /data), "Secretary of State's" (guide lead) |

Shots: `bill-1280-light-hearings.jpg`, `committee-1280-light-meetings.jpg`,
`home-390-light-coming-up-case.jpg`, `learn-bill-1280-light-headings.jpg`,
`guide-vote-390-light-head.jpg`, `officials-1280-dark-executive.jpg`,
`committee-390-light-head.jpg`, `laws-1280-light.jpg`.

**Fix:** a short word list in `src/pages/words/` for the recording and outcome
lines, the "as of" line ("Checked October 11, 2026" is the plainest) and the
empty state ("No [things] [when]."); a typographic-apostrophe pass in the
builders (source text quoted from the General Court left as it is).

### I-12 Chips that are not the chip  *(release + guides, S)*
- Learn's "You may speak here" is a rounded blue tag with a round icon, not
  the chip (`learn-bill-1280-light-headings.jpg`).
- A study committee's head carries a magenta "Committee" chip; a standing
  committee's has none (`study-committee-1280-light.jpg`).
- (Checked and consistent: the CHAIR / SPEAKER / ALTERNATE role badge is the
  same on Officials, committees and study committees.)

---

## POLISH

| # | Where | What | Fix | Owner | Effort |
|---|---|---|---|---|---|
| P-1 | Footer, 390 | "What do you think?" button sits flush on the line below it (`home-390-light-footer.jpg`) | margin below the button, `--sp-4` | release | S |
| P-2 | Bill head, 1280 | ~90 px empty band between the title and PRIME SPONSOR, set by the action column's height (`bill-1280-light-summary-head.jpg`) | let the facts row start under the title; actions span rows | release | S |
| P-3 | Bills cards and bill head, 390 | committee line starts with a bullet: "· House Finance" | draw the separator before each item but the first | release | S |
| P-4 | Cite panel, 390 | the URL wraps and leaves a lone "." on its own line (MLA, Chicago) | `overflow-wrap:anywhere` on the URL, no space before the full stop | release | S |
| P-5 | Old bills' Hearings | "Committee Of Conference" — `titleWords` missed "of" (`bill1995-390-light-hearings.jpg`) | lower-case small words after the first | release | S |
| P-6 | Learn by the numbers | chart says "Hover over a term to see its value." — no hover on a phone (`learn_numbers.py:155`) | "Tap or hover…" or print the value on each bar | guides | S |
| P-7 | 404 | a label box "NO PAGE AT THIS ADDRESS" over the h1 "Nothing is published here": says it twice (`404-390-light.jpg`) | drop the label box | release | S |
| P-8 | Senate committee meetings | "No report is dated this meeting; the docket dates the committee's report May 14, 2026." | "The committee's report is dated May 14, 2026." | release | S |
| P-9 | Calendar week view | each day heading's accessible name is "Monday Oct 26 : open this day" (space before colon) | "Monday, Oct 26: open this day" | release | S |
| P-10 | Committee addresses | the index links `committee/s42`, `committee/ss61` in lower case, `committee/H34` in capitals | one case for every code | release | S |
| P-11 | Home, 390 | two full-width black video players back to back push the Calendar and Latest Activity far down | one player, or a "Play" link per day | release | S |
| P-12 | Bill Documents tab | "House Calendar 12, 2026, committee report" reads as a date (December 2026) beside "House Calendar 6, page 10" | "House Calendar 12 (2026), committee report" | release | S |
| P-13 | Seating chart | "Seat number..." with three dots; "FIND" label beside the box where every other form puts it above (`seating-390-light.jpg`) | "Seat number…"; label above | release | S |
| P-14 | Every page, preview | the console logs a CORS error for `cloudflareinsights.com/cdn-cgi/rum` | check on graniterecord.org; if it happens there, the analytics beacon is not loading | release | S |
| P-15 | Small links, 390 | date links in "House Session (Aug 19, 2026)" and in a member's Votes table are 16 px tall; RSA breadcrumb links 16 px | 24 px line box or padding on these links | release | S |

---

## Already known — checked, still present

All six are still on the preview, as expected (they are in the 11 Nov polish):

- Calendar labels showing file names — still there: "Daily Journal No 22
  9-5-07 Veto Day Final.doc (PDF)" on /calendar/documents. Its neighbours also
  read "No 9 February 27 2026" and "January 08 2026" (no comma, a leading
  zero), and "HJ 16 August 19, 2026" beside "SJ 15 — August 19, 2026"; worth
  fixing in the same pass.
- Old room codes — still there on 1995 hearings: "RM103,ST HOUSE",
  "RMS210-211,LOB", and a raw "-5:00 & 7:00-9:00PM REPS HALL".
- "No meetings shown" on study-committee-only days — still there; the Day view
  says "Nothing on this day matches the filters." for the same case (I-11).
- Openers that turn differently — still ▸, ▾, ›, ⌄ and ▶ across Bills
  filters, committee meetings, Laws and a member's votes.
- Faint scroll edges on tab rows on phones — still faint (bill, Officials).
- Ward map picking Ward 1 — Concord's map still outlines Merrimack 15, Ward 1's
  district (`town-390-light-map-scrolled.jpg`).

---

## Pages walked

Home; Bills (and a search); a 2026 bill and a 1995 bill (every tab); Officials
(every tab, the map, the seating chart); a town (Concord, and its map); a
House and a Senate member (every tab); Committees; House Finance (Bills,
Meetings); Senate Judiciary; two statutory/study committees (Fiscal Committee,
Carbon Sequestration); House Session Days; a House and a Senate session day;
the Calendar (list, week, day; the month grid); Calendars and Journals; Learn
(How a Bill Becomes Law, By the Numbers, Glossary); Resources (every tab); two
guides (How to Vote, Property Tax Relief); Laws (both tabs); RSA 91-A; /data;
About; Search; the directory; a 404; the follow manage page.
