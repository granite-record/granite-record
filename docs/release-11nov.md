# The owner's walk of the weekend release

The release and backend session wrote this on Saturday 7 November 2026, at about 8 a.m.
Eastern. It replaces the 3 a.m. version, which was written against dry run 183. Every stop
below was opened on **dry run 2** (dev e308cee5) at its own address, and each says what that
page showed. It covers every change a reader can see between graniterecord.org today and the
weekend release, the second batch included.

## Where to walk

- **Walk dry run 3 at its own address.** The laptop manager gives it to you tonight.
  - Dry run 3 is dry run 2 plus one change: Strafford's District 1 commissioner (section 5).
    Every other stop reads the same on both.
  - Dry run 2 is **https://4e2d47d7.graniterecord.pages.dev**, and dry run 183 is
    https://dc501057.graniterecord.pages.dev.
  - Not the alias, dry-run.graniterecord.pages.dev, which can serve a page cached from an
    earlier dry run. If a page looks wrong, add `?v=1` to its address.
- **Each stop is an address to put after the deployment address.**
- **Laptop first, phone last.** Sections 1 to 9 are at laptop width. Section 10 is on a phone,
  or a window narrowed to phone width, so you resize once.
- **The whole list takes about an hour.** With twenty minutes, walk sections 1, 2 and 3,
  marked ★.

## 1. HB 703, and Back to the search ★ (about 12 minutes)

- `/bills`. Choose All Terms and search **HB 703**. It says "10 matching across all terms":
  2025's HB 703-FN-A-LOCAL first, then HB 703-FN (2020), down to HB 703 (1989). Click
  **HB 703-FN (2020)**.
  - The address is `/bill/2020/hb703`.
  - It is the prescription-drug bill: Rep. Edward Butler (D - Carr 7), House Commerce and
    Consumer Affairs, Chapter 4, Laws of 2020.
  - Cite reads "HB 703-FN (2020): relative to providing notice of the introduction of new
    high-cost prescription drugs."
  - Before the release, the 2020 result could open 2025's school-meals bill, or mix the two.
  - Its tracker shows the Law step (Jan 1, 2020, the act's effective date) before the
    Governor's (Feb 10, 2020). Live shows the same. It is one of the 253 laws to sample after
    the webinar, not part of this release.
- On that bill, type **HB 1** in the box and press Return, then press Back. 2020's bill comes
  back whole, with nothing of 2025's in it: no school meals, no Hope Damon.
- **Press Back again, to the search** (new in the second batch).
  - The address is `/bills?q=HB+703&term=all`, the box says HB 703, and the 10 bills are
    listed, with 2020's card shaded where you left it.
  - Forward reopens 2020's bill.
  - Dry run 183 and live drop the words (`/bills?term=all`), and Forward goes nowhere.
- `/bill/2020/hb703/text` and `/bill/2025/hb703/votes`: each bill on its own tab. 2025's
  Votes tab shows the House's 202–173 roll call of Mar 13, 2025.
- `/bills?q=housing`.
  - Tick Passed, choose the order Bill number, and change the words in the box to **dog**.
    The list filters as you type.
  - Open a bill and press Back. The address is `/bills?q=dog&status=Passed&sort=num`, and
    the box, the tick and the order are as you left them. A reload keeps all of it. Dry run
    183 loses the words.
- `/bills?q=housing` again. Scroll well down, open a bill, reload the page, then press Back.
  - The same search (138 of 2,243 bills) comes back at the same place in the list.
  - Dry run 183 gives bare `/bills`, at the top.

## 2. The not-found page and the header search ★ (about 6 minutes)

- `/bill/2026/hb703` lands on `/bill/2025/hb703` within a second.
  - The line "Looking for HB 703 in the 2025–2026 term…" shows for about a third of a second,
    if you see it at all. Watch the address change instead.
- `/bill/2026/hb9999`: "No page for HB 9999 of 2026. Search for HB 9999 in every term". The
  link opens the search across all terms, which finds none.
- `/town/manchster`: "No town or ward has a page at this address. Did you mean Manchester?"
  The link goes where `/town/manchester` goes, Officials on Manchester.
- `/town/dover-ward-9`: "Did you mean Dover? It has wards 1 to 6."
- `/town/harts-location`: a moment later, Hart's Location's own page.
- **The header search** (the magnifier), on any English page. Dry run 183 found nothing for
  the last three.
  - "Senate Bill 11" puts SB 11 first. Dry run 183 put CACR 11 above it.
  - "H.B. 703" puts 2025's HB 703 first.
  - "Hart's Location" puts the town first.
  - "LSR 2027-0002" puts the 2027 bill request first.
  - O'Neil waits for the phone (section 10), where the apostrophe types curly.

## 3. Members who sat in both chambers, and former members ★ (about 12 minutes)

The session pages are long: use Find for the names.

- `/legislator/frederick-king-sd-1` lands on **Former Representative Frederick King (R - Coos
  1)**. Its On Record line reads "Senate, 1999–2000 · House, 2003–2008".
- `/legislator/leo-fraser-sd-4` lands on **Former Representative Leo Fraser (R - Merr 37)**,
  with "Senate, 1999–2000 · House, 2001–2004".
- `/legislator/carl-johnson-sd-2` is **Former Senator Carl Johnson (R - SD2)**. Its On Record
  line reads "Senate, 1999–2006". Live says 1999 to 2009.
- `/legislator/jeb-bradley-carr-8` lands on Jeb Bradley's one page, which names both chambers:
  "House, 1999–2002 · Senate, 2009–2024".
  - This holds for all 30 people you confirmed on 2 November.
  - `/legislator/david-pierce-hills-6` is still a page of its own, apart from David Pierce of
    SD5.
- `/legislator/john-king-sd-18`, the first of the six senators of 1999–2000: its On Record
  line reads **"Senate, 1999–2000"**, not to 2009. The other five are Richard Russman, James
  Squires, Mary Brown, Patricia Krueger and Rick Trombly.
- `/bill/1999/cacr17/votes`: the Senate's 15–8 roll call ordering it to third reading is dated
  **Oct 22, 1999**. Live dates it 2009. It is 1999-S-109 in your corrections line, but the page
  does not print the number.
- `/directory/former-legislators`: each joined person's row names each chamber with its years,
  for example "Sen. Jeb Bradley R, SD3 · Senate 2009–2024 · House 1999–2002". **The count line
  still reads 89 former senators and 1,662 former representatives: see "For you to decide",
  item 1.**
- `/legislator/rebecca-hutchinson-rock-73` lands on **Rebecca Hutchinson (D - Rock 8)**. 75
  former members now carry the seat their last term's bills print.
  - Every address a page moved from redirects to the page it is now.
  - On dry run 2 all 631 redirect rules answer as written. On dry run 183 the walk tried all
    121 recorded moved addresses: 109 redirect, and the other 12 are still a page's own
    address. The second batch changes no data.
- `/session/H/2010-03-03`: Rep. Shannon Chandley reads **(D - Hills 6)** in both places, the
  seat she held that term. Live shows Hills 22, a seat she took in 2016, in one of the two.
- `/session/H/2004-03-17`: "Rep. Frederick King (R - Coos 1)" links his page. Dry run 181
  linked Seth King, who was not yet in the House.
- `/session/H/2002-01-31`: "Rep. William Zolla (R - Rock 13) led the Pledge of Allegiance",
  with its capitals. Live lowers them.

## 4. A record's head: Cite, Testify, Report (about 3 minutes)

- `/bill/2026/hb1123` on a laptop: Cite, Testify and Report each open a pane beside its own
  button, level with it, with a small triangle pointing at it. No pane covers the buttons, and
  Escape closes each. HB 1123 has no Follow button, because it died.
- Testify reads, in your words of 6 November, "Online testimony submissions for this bill have
  closed as of January 13, 2026."
- The facts under the title (prime sponsor, committee) sit just under it, with no empty band.
- The phone is in section 10.

## 5. Learn and Officials (about 6 minutes)

- `/learn/county-government#s-county-by-county`: **County by County**, ten cards.
  - The representatives on the ten cards add up to 400. No total is printed: 18, 15, 22, 9,
    26, 123, 45, 91, 38 and 13.
  - The Strafford card reads "Two years. All three seats are on the ballot at every state
    general election."
  - Its "Who holds these offices now" opens Officials on Strafford County.
- The same page's Common Questions: "Who fills a commissioner's seat that falls vacant?"
- `/officials#of-county-strafford` opens the **County Officials (80)** tab with Strafford at
  the top. Live opens My Town.
  - **Dry run 3's one change:** Strafford County's Commissioner, District 1 reads **Leslie
    Feliciano (R)**, in Joe Pitre's place. Dry run 2 shows Joe Pitre.
  - Read the line under the last county too: see "For you to decide", item 3.
- `/officials`, Legislators, By seat: "Go to a seat" and "Find" each sit above their control.

## 6. The data: /api and the downloads (about 6 minutes)

- `/api` is a new page. It is not linked from anywhere and is not in the sitemap. It carries
  noindex until you announce it.
  - The heading is "The Data API", and it says "A beta until February 1, 2027".
  - Its Count column says what it counts: "43 files", "14 tables", "2,157 people", "33,717
    bills".
  - The people.json row now says it also has 30 entries for numbers that proved to be one of
    the 2,157 people's.
  - Up to iPad width the table is a list, as on a phone.
- `/data`, under proceedings.csv: it no longer carries YouTube's titles and times. It lists 13
  columns, 105,476 rows, and is 10.3 MB.
- `/data/manifest.json` and `/data/schema.json`, Find "rights": the one rights line, in your
  words of 5 November. It begins "The record is the State of New Hampshire's".
- `/data/people.json` (0.8 MB; Find "Jeb Bradley"): one person for each of your 30 pairs, with
  both numbers. Jeb Bradley's entry lists employee numbers 374827 and 209078.

## 7. The guides (about 4 minutes)

- `/guides/how-to-vote`: the date line reads "Sources last checked October 26, 2026. Check
  each step against the official page it links before you rely on it." 30 guides change date.
- The same page, In the Record near the bottom, "Show the laws passed in": choose 2025, and
  the 2026 laws passed but not yet in effect (HB 481, HB 1541-FN) drop out.
- `/guides/run-for-office`: the qualifications say "domiciled in New Hampshire at least 7 years
  immediately preceding the election", in RSA 655:29's words, with RSA 655:29 in the caption.

## 8. Spanish pages (about 6 minutes)

- `/es/`:
  - The search hint, "Proyecto, tema, nombre o municipio", fits its box.
  - **New in the second batch:** one note under the title, "Esta página está en español.
    Algunas partes se quedan en inglés a propósito…". Under it, "Por qué algunas partes están
    en inglés" is folded: open it, and there are four reasons.
- `/es/officials` at laptop width: all six tabs are in view, "Funcionarios del condado (80)"
  last, and the same note is there, once.
- `/es/guides/how-to-vote`: the same note, once. No English page carries it.
- The header search on a Spanish page, typing Concord: "10 barrios electorales · Condado de
  Merrimack". Live reads "10 wards · Merrimack County".
- `/es/learn/county-government#s-county-by-county`: "Condado por condado", ten cards.
  - Strafford's reads "Dos años. Los tres cargos están en la boleta en cada elección general
    estatal."
  - Its link opens `/es/officials#of-county-strafford`.

## 9. Small things, and Live Now (about 4 minutes)

- `/no-such-page` shows one heading, "Nothing is published here", and "The address may be
  mistyped.", with no box above it.
- `/bill/2026/sb400/documents` reads "Committee report, House Calendar 16 (2026)".
- `/bill/1995/hb1/hearings` reads "Committee of Conference", with a small "of".
- `/bill/2018/hb1500/reports`: the interim study report is dated Nov 9, 2018.
- `/live` is a new page, linked from nowhere yet.
  - Give it a few seconds. With nothing streaming it says "No stream found right now
    (checked …)" and names the House's and Senate's own streams.
  - It has no `/session/H/today` link.
- `/committee/H43` draws to its end on a weekend, with no live box. It is the slowest and
  longest stop, about six seconds.

## 10. On a phone (about 6 minutes)

- `/bill/2026/hb1123`: each pane drops under its own button. It lies over the buttons below
  it (Print, Share, Report) until you close it. See the nits.
- `/learn/by-the-numbers`: the Became Law chart is several screens down. Every bar shows its
  value, and the line above it says "Each term's value is at the end of its bar."
- `/api`: the table is a list.
- The header search: **O'Neil**, with the phone's curly apostrophe, lists Candice, William and
  James O'Neil. "O Neil" gives the same. Dry run 183 found nothing.
- `/legislator/melanie-levesque-sd-12`, for the nit below.

## For you to decide

The walk of dry run 2 found nothing that holds the release. These three are new with it.

1. **The former-members directory lists eight people under one chamber only.**
   - It is still so on dry run 2, and will be on dry run 3. `/directory/former-legislators`
     lists each joined person once, under the chamber of the page kept.
   - Cilley, Leo Fraser, Edward (Ned) Gordon, Fenton Groen, Frederick King, Amanda Merrill,
     Andrew Peterson and Frank Sapareto sat in the Senate, but appear only under the House.
   - So its count line says 89 former senators and 1,662 former representatives. The record
     has 97 and 1,688, and live says so.
   - **The fix is ready**, on `fix/former-directory-both`, and is in neither dry run 2 nor 3.
     - With it the count line reads "97 former senators and 1,688 former representatives…
       The 34 who sat in both chambers are under each."
     - Under the other chamber a person's row has that chamber's title and its years first,
       and no party or seat. For example: "Rep. Jeb Bradley House 1999–2002 · Senate
       2009–2024".
     - Decide whether it goes into this release, which would mean another dry run, or waits
       for 24 November.
2. **Michael Downing's one page calls him a Republican throughout.**
   - He sat in the House in 1999–2002 as a Democrat, as your note on the pair says.
   - His old House address now lands on that page, and his 1999 bill still names him "(D -
     Rock 26)".
   - He is the only one of the 30 whose party differs between chambers. The fix, a party for
     each chamber's years, is larger, and fits 24 November better.
3. **The source line under County Officials does not cover Leslie Feliciano's row** (dry run
   3 only).
   - The line under the counties reads "Kept by hand, read from the Secretary of State's
     county roster for 2025–2026, dated December 5, 2024; read October 9, 2026. Most of these
     seats were on the ballot on November 3, 2026; this is the roster read before it."
   - Her row comes from Strafford County's own list, read on 6 November 2026. The roster names
     Joe Pitre.
   - This was seen by building that tab from dry run 3's code; dry run 3 itself was not up
     yet. The page draws one source line for all 80 rows, and never a row's own source.
   - A fix would add a sentence naming the rows read from another source. It needs a Spanish
     line in the translation file, which is the translation work's to add, not this session's.

## Already on live, and still there (for 24 November)

- `/session/H/2006-04-19`, and `/bill/2006/hb1724`, credit a motion to "Rep. Seth King". It was
  Frederick King's: Seth King's record starts in 2023.
- Some House days credit a former member's motion to a sitting member of the same name who was
  not yet in the House: Butler in 2014, Grossman in 2014, Schultz in 2012.
- `/bills#2020/HB703`, an address naming an older term only in its fragment, does not open
  2020's HB 703.
  - It shows the 2025–2026 list, on dry run 2 and on live. The 3 a.m. version of this list
    said it opened 2025's bill.
  - `/bills?q=HB+703&term=all#2020/HB703` opens 2020's bill.
- A tab clicked on a bill opened from such an address writes `/bills/votes?…`, which is not a
  page.
- A bill opened from the search keeps the search's tab title in the browser tab.
- After a bill is reloaded, Back to the search leaves that bill drawn open inside its card in
  the list. Dry run 183 and live do the same.
- The status box on `/es/` has an English sentence, "The 2026 session ended Aug 19 (veto
  day)…", which none of the new note's four reasons covers.

## Small things the walk noted (nits)

- At phone width a record's pane (Cite, Testify) lies over the buttons below its own until it
  is closed. This is new with the release, and dry run 183 is the same. Live puts the pane
  below the whole group of buttons.
- At phone width, Melanie Levesque's On Record line breaks inside "2019–2020".
- `/api` says "2,157 people" beside the database's "people (2,187)". Both are right: the 30
  extra are numbers retired by the joins. `people.json`'s own description still says one entry
  per person.
- `/api`'s code examples sit on their box's left edge, and its table names are drawn in
  capitals.
- Four joined members' heads name the county short: "Straf District 6", "Merr District 37".

## What cannot be walked yet

- **The Vacant mark on County Officials:** no vacancy is entered in the corrections file.
- **Testify's "They may open again…":** no bill is moving between chambers in November.
- **Members-elect:** the 2026 results file is not in yet.
- **The register of probate paragraph:** it changes only when CACR 13's count is entered.
