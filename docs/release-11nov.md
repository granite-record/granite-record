# The owner's walk of the weekend release

The release and backend session wrote this on Saturday 7 November 2026, at about 8 a.m.
Eastern, and has updated it through the day. At about 9 a.m. it was corrected after two checks
of the list itself, and the deeper walks' findings were added. It replaces the 3 a.m. version, which was written against dry run
183.

Sections 1 to 9 and 11 were opened on **dry run 2** (dev e308cee5) at its own address, and
each stop says what that page showed. Section 10 covers the election: the members-elect and
CACR 13's count.
- It was added at about 11 a.m., and given your recounts and CACR 13 at about 2 p.m.
- It came from dry run 4's code and data, read before dry run 4 was up.
- The laptop manager's retest on dry run 4 matched it, and this session's own walk of it is
  under way.

At about 3 p.m. the list took in your answers and dry run 6's three new stops: the directory
in section 3, Hillsborough's sheriff in section 5, and the reworded note in section 8. Those
three were not yet up on any dry run, so they say what the code and your words give.

The list covers every change a reader can see between graniterecord.org today and the weekend
release, the second batch and the election included. A few stops check that a slip seen
on an earlier dry run stays fixed; those say so.

## Where to walk

- **Walk dry run 6 at its own address.** The laptop manager gives it to you tonight.
  - Dry run 6 (dev 953fc547) is dry run 2 plus:
    - Strafford's District 1 commissioner, in section 5 and on the Spanish Officials page in
      section 8 (from dry run 3);
    - the members-elect of 3 November, Rich Green left unlinked, and CACR 13's count, in
      section 10 (from dry run 4);
    - Hillsborough's sheriff, in section 5 (from dry run 5);
    - your two answers of this afternoon: the former-members directory, in section 3, and the
      reworded Spanish note, in section 8.
  - Every other stop reads the same as on dry run 2.
  - Dry runs 3, 4 and 5 were clean, and dry run 6 replaces them.
  - Earlier addresses, for comparison:
    - dry run 4, **https://ff30d1c7.graniterecord.pages.dev**;
    - dry run 2, **https://4e2d47d7.graniterecord.pages.dev**;
    - dry run 183, https://dc501057.graniterecord.pages.dev.
  - Not the alias, dry-run.graniterecord.pages.dev, which can serve a page cached from an
    earlier dry run.
  - If a page looks wrong, reload it. On a stop whose address has no ? or # in it, adding
    `?v=1` to the end also fetches it fresh. Don't add it to an address that has either: it
    changes what the page shows.
- **Each stop is an address to put after the deployment address.**
- **Laptop first, phone last.** Sections 1 to 10 are at laptop width. Section 11 is on your
  phone itself: a narrowed laptop window types a straight apostrophe, and section 11's
  searches need the phone's curly one.
- **The whole list takes about an hour and twenty minutes.** With forty minutes, walk the ★
  sections 1, 2 and 3, and the ★ stops in sections 5 and 10.

## 1. HB 703, and Back to the search ★ (about 12 minutes)

- `/bills`. Choose All Terms and search **HB 703**. It says "10 matching across all terms":
  2025's HB 703-FN-A-LOCAL first, then HB 703-FN (2020), down to HB 703 (1989). Click
  **HB 703-FN (2020)**.
  - The address is `/bill/2020/hb703`.
  - It is the prescription-drug bill: Rep. Edward Butler (D - Carr 7), House Commerce and
    Consumer Affairs, Chapter 4, Laws of 2020.
  - Click **Cite this page**. Its MLA line reads "HB 703-FN (2020): relative to providing
    notice of the introduction of new high-cost prescription drugs."
  - On live, clicking the 2020 result opens 2025's school-meals bill.
  - Its tracker's last step, Law, is dated Jan 1, 2020, the act's effective date. That is
    earlier than the Governor's step before it, Feb 10, 2020. Live shows the same. It is one
    of the 253 laws to sample after the webinar, not part of this release.
- On that bill, replace HB 703 in the box with **HB 1** and press Return, then press Back.
  2020's bill comes back whole, with nothing of 2025's in it: no school meals, no Hope Damon.
- **Press Back again, to the search** (new in the second batch).
  - The address is `/bills?q=HB+703&term=all`, and the box says HB 703.
  - The 10 bills are listed, 2020's second, at the place you left.
  - Forward reopens 2020's bill.
  - Dry run 183 and live drop the words (`/bills?term=all`), and Forward goes nowhere.
- `/bill/2020/hb703/text` opens 2020's bill at its Bill Text tab.
- `/bill/2025/hb703/votes` opens 2025's at its Votes tab, with the House's 202–173 roll call
  of Mar 13, 2025.
- `/bills?q=housing`.
  - Tick Passed, choose the order Bill number, and change the words in the box to **dog**.
    The list filters as you type.
  - Open a bill and press Back. The address is `/bills?q=dog&status=Passed&sort=num`, and
    the box, the tick and the order are as you left them. A reload keeps all of it.
  - Dry run 183 loses the words.
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
- **The header search** (the magnifier), on any English page:
  - "Senate Bill 11" puts SB 11 first. Dry run 183 put CACR 11 above it.
  - "H.B. 703" puts 2025's HB 703 first. Dry run 183 found nothing.
  - "LSR 2027-0002" puts the 2027 bill request first. Dry run 183 found nothing.
  - O'Neil and Hart's Location wait for the phone (section 11). Typed on a laptop, they
    already worked on dry run 183.

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
- `/legislator/john-king-sd-18`: its On Record line reads **"Senate, 1999–2000"**.
  - He is the first of six 1999–2000 senators whose pages said they served to 2009.
  - The other five are Richard Russman, James Squires, Mary Brown, Patricia Krueger and Rick
    Trombly.
- `/bill/1999/cacr17/votes`: the Senate's 15–8 roll call ordering it to third reading is dated
  **Oct 22, 1999**. Live dates it 2009. It is 1999-S-109 in your corrections line, but the page
  does not print the number.
- `/directory/former-legislators` (new in dry run 6: "Your answers", item 1).
  - The count line reads **"97 former senators and 1,688 former representatives with a
    recorded roll call vote since 1999, by surname. The 34 who sat in both chambers are under
    each."**
  - Dry run 2 and dry run 4 read 89 and 1,662. Live reads 97 and 1,688, with no sentence
    about the 34, because live still has a page for each chamber.
  - Under its own chamber a joined person's row is as before: "Sen. Jeb Bradley R, SD3 ·
    Senate 2009–2024 · House 1999–2002".
  - Under the other chamber the row has that chamber's title and its years first, and no
    party or seat: "Rep. Jeb Bradley House 1999–2002 · Senate 2009–2024". Both rows link to
    the one page.
  - The Senate list now has Leo Fraser, Edward Gordon and Fenton Groen among its F's and G's,
    with the Senate's years first. Before, they were only in the House list.
- `/legislator/rebecca-hutchinson-rock-73` lands on **Rebecca Hutchinson (D - Rock 8)**. 75
  former members now carry the seat their last term's bills print, and every address a page
  moved from lands on the page it is now.
  - That was checked by machine on dry run 2, for every old address. Nothing for you to do
    here.
- `/session/H/2010-03-03`: Rep. Shannon Chandley reads **(D - Hills 6)** in both places, the
  seat she held that term. Live shows Hills 22, a seat she took in 2016, in one of the two.
- `/session/H/2004-03-17`: "Rep. Frederick King (R - Coos 1)" links his page. Live links him
  the same way. This checks that a slip of dry run 181, which linked Seth King, stays fixed.
- `/session/H/2002-01-31`: "Rep. William Zolla (R - Rock 13) led the Pledge of Allegiance",
  with its capitals and his 2001–2002 seat. Live lowers them, and reads Rock 5.

## 4. A record's head: Cite this page, Testify, Report a problem (about 3 minutes)

- `/bill/2026/hb1123` on a laptop.
  - Cite this page, Testify and Report a problem each open a pane beside their own button,
    level with it, with a small triangle pointing at it.
  - No pane covers the buttons, and Escape closes each.
  - HB 1123 has no Follow button, because it died.
- Testify reads, in your words of 6 November, "Online testimony submissions for this bill have
  closed as of January 13, 2026."
- The facts (prime sponsor, committee) sit just under the title. The space below them, beside
  the buttons and above the tracker, is expected.
- The phone is in section 11.

## 5. Learn and Officials (about 6 minutes)

- `/learn/county-government#s-county-by-county`: **County by County**, ten cards.
  - The representatives on the ten cards add up to 400. No total is printed: 18, 15, 22, 9,
    26, 123, 45, 91, 38 and 13.
  - The Strafford card reads "Two years. All three seats are on the ballot at every state
    general election."
  - Its "Who holds these offices now" opens Officials on Strafford County.
- The same page's Common Questions: open "Who fills a commissioner's seat that falls
  vacant?". It answers "The county convention (RSA 661:9, II)."
- ★ `/officials#of-county-strafford` opens the **County Officials (80)** tab with Strafford at
  the top. Live opens My Town.
  - **New from dry run 3:** Strafford County's Commissioner, District 1 reads **Leslie
    Feliciano (R)**, in Joe Pitre's place. Dry run 2 shows Joe Pitre.
  - Read the line under the last county too: see "Your answers", item 3.
- `/officials#of-county-hillsborough` (new in dry run 5): Hillsborough County's Sheriff reads
  **Brian J. Newcomb**, in Christopher Connelly's place.
  - He took office on March 5, 2025, chosen by the county delegation after Connelly resigned.
    The source is your word and the county's Sheriff's Office page.
  - Like every sheriff on the page, he carries no party. No town is shown, because his is not
    given.
  - Dry run 2 and dry run 4 show Christopher Connelly, as the Secretary of State's roster
    does.
- `/officials`, Legislators, By seat: "Go to a seat" and "Find" each sit above their control.

## 6. The data: /api and the downloads (about 6 minutes)

- `/api` is a new page. On live it is the not-found page.
  - No page links to it; only manifest.json and schema.json name its address. It is not in
    the sitemap, and search engines are told not to list it until you announce it.
  - The heading is "The Data API", and it says "A beta until February 1, 2027".
  - Its Count column says what it counts: "43 files", "14 tables", "2,157 people", "33,717
    bills".
  - The people.json row now says it also has 30 entries for numbers that proved to be one of
    the 2,157 people's.
- `/data`: find proceedings.csv and open "More about proceedings.csv".
  - Its Columns line names 13 columns, from term to end_how. None is a YouTube title or time.
  - The row says 105,476 rows and 10.3 MB.
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
  immediately preceding the election", with RSA 655:29 in the caption.

## 8. Spanish pages (about 6 minutes)

- `/es/`:
  - The search hint, "Proyecto, tema, nombre o municipio", fits its box.
  - **New in the second batch:** one note under the title, "Esta página está en español.
    Algunas partes se quedan en inglés a propósito…". Under it, "Por qué algunas partes están
    en inglés" is folded: open it, and there are four reasons.
- `/es/officials` at laptop width:
  - All six tabs are in view, "Funcionarios del condado (80)" last, and the same note is there,
    once.
  - On dry run 4, Strafford's first commissioner there is Leslie Feliciano too.
- `/es/officials` again: open the note (reworded in dry run 6: your answer to item 4).
  - Its second reason now says, in your words, "Names of people, committees and towns stay as
    the record prints them; where a committee is given a Spanish name, its English name is
    beside it", in Spanish.
  - "Cargos" (offices) is gone, so it no longer contradicts the Poder Ejecutivo tab just
    under it, which reads Gobernador, Consejo Ejecutivo, Secretaría de Estado.
  - The other three reasons are as before. Dry run 4 still has the old second reason.
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
  - Its only links are those two YouTube streams; none goes to a House session.
- `/committee/H43` draws to its end on a weekend, with no live box. It is the longest stop,
  and can take several seconds to draw.

## 10. The 3 November election: members-elect and CACR 13 ★ (dry run 4; about 15 minutes)

Dry run 4 adds the members-elect of the 3 November election, by the Secretary of State's
count:
- 405 elected: 213 sitting members re-elected, 24 former members returning, and 168 new;
- 19 seats "Result not final", in the 16 races being recounted.

Every block says "Elected November 3, 2026" and "Takes office December 2, 2026.", and all of
it disappears on 2 December. Town and legislator pages are in English only.

**How these stops were made.** They come from dry run 4's code and data (dev 9052784d: the
results, your 16 recounts and Rich Green), read before dry run 4 was up. A build of the
members-elect from them gives your counts exactly: 405, 213, 24, 168 and 19. Dry run 4's own
file says the same. The laptop manager's retest on dry run 4 matched these stops, and this
session's own walk of each one is under way.

- ★ `/town/derry`, the Representatives tab, which the page opens on.
  - Rockingham district 13, 10 seats: "Serving now" sits over the ten sitting members.
  - Under them is a shaded block: "Elected November 3, 2026", "Takes office December 2,
    2026.", and eight winners, most votes first: Kristine Trow (D), Jamie Carreau (D), Matthew
    Glavin (D), Hollie Hesse (D), Charles Foote (R), Jim Marshall (D), Haley Carreau (D) and
    David Provencher (D).
  - Charles Foote is re-elected and links to his page. The seven others are new, with no link.
  - Rockingham 13 is being recounted, and you held its two closest seats. So the two winners
    with the fewest votes are left out, and the block ends "Result not final — a recount was
    requested". It does not say how many seats are held.
  - `/town/salem`, Rockingham 25, has the same shape: 8 of its 9 winners, one seat held.
  - State Senate — district 19: "Serving now" Sen. Regina Birdsell, then "Regina Birdsell
    (R)", re-elected, linked.
- `/town/derry`, the Vote tab: its heading reads "Last election: November 3, 2026".
  - `/town/salem` reads "Where you vote", because the Secretary of State's clerk list names no
    election for Salem. That is not new.
- `/town/derry#map`: the map opens on Rockingham 13.
  - Its panel shows "Serving now", the sitting members, and the same block, the "Result not
    final" line included.
  - The district's colour is still the sitting members' party.
  - Switch to the State Senate layer and pick 19: Regina Birdsell.
- ★ A single-seat recount: `/town/hebron`, Grafton district 11, 1 seat.
  - "Serving now" Rep. Lex Berezhny, then a block that names nobody: "Elected November 3,
    2026", "Takes office December 2, 2026.", "Result not final — a recount was requested".
  - Below it, Grafton 18 (floterial) is final: Marko Kloos (D), new, with no link.
  - Its Vote tab reads "Last election: November 3, 2026".
  - `/town/hollis`, Hillsborough 45 (floterial), is the other single-seat recount, in the same
    shape. Hollis's own Hillsborough 35 is final: Ben Ming (D), returning, and Kat McGhee (D),
    re-elected, both linked.
- A former member returning: `/legislator/benjamin-baroody-hills-39`.
  - The heading stays "Former Representative Benjamin Baroody (D - Hills 39)".
  - Under it: "Elected November 3, 2026, for Hillsborough district 16. Takes office December
    2, 2026." The line names the seat he won, not the one in the heading.
  - His chip on the town page reads "Ben Baroody (D)", as the ballot spells it.
  - One returning to the same seat: `/legislator/charlotte-dilorenzo-rock-10`, "… for
    Rockingham district 10 …".
- A new member-elect with no link: `/town/nashua-ward-5`, Hillsborough district 9.
  - "Rich Green (D)" is a plain chip. Santosh D. Salvi and Sanjeev K. Manohar, re-elected,
    link to their pages.
  - As you said, he is not former Sen. Richard Green: `/legislator/richard-green-sd-6` carries
    no "Elected" line.
  - A new member has no page, and the header search does not find one. "Rich Green" there
    finds former Sen. Richard Green.
- ★ `/officials#members-elect`: the last tab, **Members-Elect (405)**.
  - It says "Elected November 3, 2026, by the Secretary of State's count. They take office on
    December 2, 2026; until then the Legislators tab lists who holds each seat."
  - State Senate comes first, District 1 to 24, then State House by county.
  - There is no "Serving now" here, and no contact details.
- **The Senate side is names only.** No Senate race is being recounted, so no Senate block says
  "Result not final".
  - `/town/amherst`, State Senate — district 11: "Serving now" Sen. Tim McGough, then "Shannon
    E. Chandley (D)", a former senator returning, linked to her page.
  - `/town/antrim`, district 8: "Jim Creighton (R)", a sitting representative elected to the
    Senate, linked to his House page. That page's line reads "… for Senate District 8 …".
  - The new senators are plain chips: Kurt Webber (2), Rebecca Harned (7), Matthew McLaughlin
    (9), Carryl L. Roy (12), Dian McCarthy (16) and Leonard Bell (18).
- **CACR 13, the register of probate amendment.** Its count is in: 365,359 yes and 198,791 no,
  64.8%, short of two thirds.
  - `/bill/2026/cacr13`: the status reads "Passed both chambers, not ratified by the voters".
    The tracker's Voters step reads "Not ratified, 365,359–198,791", with whose count it is.
    Dry run 2 reads "went to the voters in November 2026".
  - `/learn/county-government`, Common Questions, open "What does the register of probate
    still do?": the answer ends
    "… as CACR 13 (2026), and on November 3, 2026 it did not reach the two thirds it needed:
    64.8% of those voting on it voted yes." The same is on `/es/learn/county-government`.
    Dry run 2 says the count is not on the site yet.
  - `/learn/by-the-numbers`, Constitutional Amendments Sent to the Voters: a CACR 13 of
    2025–2026 row, Nov 3, 2026, 365,359, 198,791, 64.8%, Not Ratified. The line saying its
    count is not on the site yet is gone.
- Things a reader may ask about. These are as the code draws them, not faults found:
  - A single-seat recount's block heads "Elected November 3, 2026" over nobody.
  - A part-held recount does not say how many seats are held, or name the winners held back.
  - Chips use the ballot's spelling ("Ben Baroody", "Jim Creighton"); the pages use the
    record's (Benjamin, James).
  - `/town/new-castle`: Rockingham 22 has no sitting member, so "Serving now" sits over "1 seat
    vacant", then Rebecca Audet (D), new.

## 11. On your phone (about 6 minutes)

- `/bill/2026/hb1123`: tap Cite this page, then Testify.
  - Each pane opens under its own row of buttons.
  - Each hides Print, Share and Report a problem until you tap the same button again to close
    it. See the nits.
  - Report a problem is the last button, so its pane covers nothing.
- `/learn/by-the-numbers`: the Became Law chart, under "Became Law, as a Share of the Bills
  Filed", is about a screen and a half down. Every bar shows its value, and the line above
  it says "Each term's value is at the end of its bar."
- `/api`: the table is a list.
- **The header search** (the magnifier). Read the list under the box, without pressing Go,
  which jumps straight to the first result.
  - **O'Neil**, with the phone's curly apostrophe: five O'Neils, Candice first.
  - **Hart's Location**, with the curly apostrophe: the town first.
  - Dry run 183 found nothing for either with the curly apostrophe. With a straight one, or as
    "O Neil", they already worked.
- `/legislator/melanie-levesque-sd-12`, for the nit below.

## Your answers (7 November, about 2:30 p.m.)

The walk of dry run 2 found nothing that holds the release. You answered the four items it
raised:

1. **The former-members directory: in this release.** It is in dry run 6, and section 3 has
   its stop.
   - Before, each of the 34 people who sat in both chambers was listed under one chamber only.
     Eight who sat in the Senate (Jacalyn Cilley, Leo Fraser, Edward Gordon, Fenton Groen,
     Frederick King, Amanda Merrill, Andrew Peterson, Frank Sapareto) were under the House
     alone, and 26 who sat in the House, Jeb Bradley among them, were under the Senate alone.
   - So its count line said 89 and 1,662.
2. **Michael Downing's party: for 24 November.**
   - His one page calls him a Republican throughout. He sat in the House in 1999–2002 as a
     Democrat, and his 1999 bill still names him "(D - Rock 26)".
   - The fix, a party for each chamber's years, will be built on a branch after the release.
3. **The source line under County Officials: for 24 November.** It will name the two rows read
   from somewhere other than the Secretary of State's roster:
   - Strafford's Leslie Feliciano, from the county's own list, read 6 November;
   - Hillsborough's Sheriff Brian J. Newcomb, from your word and the county's Sheriff's Office
     page.

   Until then, the one line below names only the roster. The detail as found:
   - The line under the counties reads "Kept by hand, read from the Secretary of State's
     county roster for 2025–2026, dated December 5, 2024; read October 9, 2026. Most of these
     seats were on the ballot on November 3, 2026; this is the roster read before it."
   - Her row comes from Strafford County's own list, read on 6 November 2026. The roster names
     Joe Pitre.
   - This was seen first by building the County Officials tab from dry run 3's code and
     corrections file. It was then seen on dry run 3 itself, https://6e462616.graniterecord.pages.dev.
   - The page draws one source line for all 80 rows, and never a row's own source. The fix
     adds a sentence, with its Spanish line as a draft.
4. **The Spanish note: reworded, in dry run 6.** Section 8 has its stop.
   - The second reason said names stay as the record prints them, "people, committees, towns
     and offices". But `/es/officials` gives every office in Spanish.
   - It now reads, in your words, "Names of people, committees and towns stay as the record
     prints them; where a committee is given a Spanish name, its English name is beside it."
     It is still a draft for the caucus's review.
   - Two smaller gaps stay for the caucus's review:
     - Its fourth reason lists the pages still in English as if the list were complete. The
       footer's About and Data, the town pages, the House and Senate session lists and the
       towns directory are English too, linked from Spanish pages, and are neither named nor
       marked.
     - On `/es/resources`, the Learn tab's card "El registro en cifras" goes to the English
       page with no "(en inglés)" mark. That was so before the note, and live is the same.

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
- A bill opened from the search and left with Back stays drawn open inside its card in the
  list. After a reload it does not. Dry run 183 and live do the same.
- The status box on `/es/` has an English sentence, "The 2026 session ended Aug 19 (veto
  day)…", which none of the new note's four reasons covers.
- **Typing a place's apostrophe drops its bills.** `/search?q=Wentworth's Location` says "no
  bill in any of the 19 terms", and `/bills` on All Terms finds 0. "Wentworths Location"
  finds 4, among them SB 77 of 2003, whose text names "Wentworth's Location".
  - Crawford's Purchase, Green's Grant, Chandler's Purchase, Bean's Grant and others do the
    same.
  - The second batch now puts the place itself first, where dry run 183 and live found
    nothing at all, but the bills still go missing.
  - It is the one should-fix on live that this walk found.

## Small things the walk noted (nits)

- **"U.S. 3" now finds nothing**, new with the release.
  - In the bill search on All Terms and on `/search`, "U.S. 3" finds no bill. Dry run 183 and
    live find 6.
  - The same goes for U.S. 1 (7 before), U.S. 2 (4), U.S. 202 and U.S. 302. "U.S. Route 3"
    still works.
  - The search change reads letters with full stops before a number as a bill's kind, as in
    "H.B. 703". Its review knew of this and left it.
  - The fix is small: fold the full stops only for a kind of bill the General Court uses, as
    the header search already does.
- At phone width, Cite's and Testify's panes lie over the buttons below until they are closed.
  This is new with the release, and dry run 183 is the same. Live puts the pane below the whole
  group of buttons.
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
