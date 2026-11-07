# The owner's walk of the weekend release

The release and backend session wrote this on Saturday 7 November 2026, at about 3 a.m.
Eastern, after its deep walk of dry run 183 (dev 969c27fa). The 11 November walk list was on
no branch, so this one is written fresh. It covers every change a reader can see between
graniterecord.org today and the weekend release, from the release's own commits, each one
opened on the dry run.

## Where to walk

- **Walk on a dry run's own deployment address, not the alias.**
  - Dry run 183: **https://dc501057.graniterecord.pages.dev**.
  - Dry run 2, on Saturday afternoon, will have its own address. It carries the second batch
    (section 10). Walk that one when the laptop manager gives it.
  - The alias, dry-run.graniterecord.pages.dev, can serve a page cached from an earlier dry
    run. `/legislator/carl-johnson-sd-3` answered there with the old "1999 to 2009". If a page
    looks wrong, add `?v=1` to its address.
- **Each stop is an address to put after the deployment address.** Where it says "at phone
  width", narrow the window or use a phone.
- **The whole list takes about an hour.** With twenty minutes, walk the stops marked ★.

## 1. HB 703: two bills of one number ★

- `/bills`. Choose All Terms, search **HB 703**, and click **HB 703-FN (2020)**.
  - The address is `/bill/2020/hb703`.
  - It is the prescription-drug bill: Rep. Edward Butler, House Commerce, Chapter 4 of 2020.
  - Cite reads "HB 703-FN (2020)…".
  - Before the release, the 2020 result could open 2025's school-meals bill, or mix the two.
- On that bill, type **HB 1** in the box and press Return, then press Back. 2020's bill comes
  back whole, with nothing of 2025's in it.
- `/bill/2020/hb703/text` and `/bill/2025/hb703/votes`: each bill on its own tab.
- Not fixed on dry run 183, fixed in dry run 2: Back from the bill to the search drops the
  words from the address (`/bills?term=all`), and Forward goes nowhere. Section 10.

## 2. Members who sat in both chambers, and former members ★

- `/legislator/frederick-king-sd-1` lands on **Former Representative Frederick King (R - Coos
  1)**. Its On Record line reads "Senate, 1999–2000 · House, 2003–2008".
- `/legislator/leo-fraser-sd-4` lands on **Former Representative Leo Fraser (R - Merr 37)**.
- `/legislator/carl-johnson-sd-2` is **Former Senator Carl Johnson (R - SD2)**, 1999 to 2006.
  On live it says "to 2009".
- `/legislator/jeb-bradley-carr-8` lands on Jeb Bradley's one page, which names both chambers:
  "House, 1999–2002 · Senate, 2009–2024". This holds for all 30 people you confirmed on 2
  November. David Pierce of Hills 6 still has his own page.
- `/legislator/john-king-sd-18`, the first of the six senators of 1999–2000, reads **"1999 to
  2000"**, not "to 2009". The other five are Richard Russman, James Squires, Mary Brown,
  Patricia Krueger and Rick Trombly.
- `/bill/1999/cacr17/votes`: roll call 1999-S-109 is on **22 October 1999**, as your line in
  the corrections file says.
- `/directory/former-legislators`: each joined person's row names each chamber with its years,
  for example "Sen. Jeb Bradley R, SD3 · Senate 2009–2024 · House 1999–2002". **See "For you
  to decide" below: eight of these people are now listed under the House only.**
- `/legislator/rebecca-hutchinson-rock-73` lands on **Rebecca Hutchinson (D - Rock 8)**. 75
  former members now carry the seat their last term's bills print.
  - Every address a page moved from redirects to the page it is now.
  - The deep walk tried all 121 recorded addresses: 109 redirect, and the other 12 are still a
    page's own address.
- `/session/H/2010-03-03`: Rep. Shannon Chandley reads **(D - Hills 6)**, the seat she held
  that term. Live shows Hills 22, a seat she took in 2016.
- `/session/H/2004-03-17`: "Rep. Frederick King (R - Coos 1)" links his page. Dry run 181
  linked Seth King, who was not yet in the House.
- `/session/H/2002-01-31`: "Rep. William Zolla (R - Rock 13) led the Pledge of Allegiance",
  with its capitals. Live lowers them.

## 3. The data: /api and the downloads

- `/api` is a new page. It is not linked from anywhere and is not in the sitemap; it carries
  noindex until you announce it.
  - The heading is "The Data API", and it says "A beta until February 1, 2027".
  - Its Count column says what it counts: "43 files", "14 tables", "2,157 people", "33,717
    bills".
  - Up to iPad width the table is a list, as on a phone.
- `/data`: proceedings.csv no longer carries YouTube's titles and times. It lists 13 columns
  and is 10.3 MB.
- `/data/manifest.json` and `/data/schema.json`: the one rights line, in your words of 5
  November. It begins "The record is the State of New Hampshire's".
- `/data/people.json`: one person for each of your 30 pairs, with both numbers.

## 4. Officials and Learn

- `/learn/county-government#s-county-by-county`, and the same under `/es/`: **County by
  County**, ten cards.
  - The representatives total 400.
  - The Strafford card reads "Two years. All three seats are on the ballot at every state
    general election."
  - Its "Who holds these offices now" opens Officials on Strafford County.
- The same page's Common Questions: "Who fills a commissioner's seat that falls vacant?"
- `/officials#of-county-strafford` opens the **County Officials** tab with Strafford near the
  top. Live opens My Town.
- `/officials`, Legislators, By seat: "Go to a seat" and "Find" each sit above their control.

## 5. A record's head: Cite, Testify, Follow, Report

- `/bill/2026/hb1123` on a laptop: each pane opens beside its own button, level with it, with
  a small triangle pointing at it, and never covers the buttons. At phone width each pane drops
  under its own button. Escape closes it.
- Testify on HB 1123 reads, in your words of 6 November, "Online testimony submissions for this
  bill have closed as of January 13, 2026."
- The facts under the title (prime sponsor, committee) sit just under it, with no empty band.

## 6. The guides

- `/guides/how-to-vote`: the date line reads "Sources last checked October 26, 2026. Check each
  step against the official page it links before you rely on it." 30 guides change date.
- `/guides/run-for-office`: the qualifications say "domiciled in New Hampshire at least 7 years
  immediately preceding the election", in RSA 655:29's words, with RSA 655:29 in the caption.
- `/learn/by-the-numbers` at phone width: every bar shows its value, and the line above says
  "Each term's value is at the end of its bar."
- `/guides/how-to-vote`, "Show the laws passed in": choose 2025, and the 2026 laws that are
  passed but not yet in effect drop out.

## 7. Spanish pages

- `/es/`: the search hint, "Proyecto, tema, nombre o municipio", fits its box.
- `/es/officials` at laptop width: all six tabs are in view, "Funcionarios del condado (80)"
  last.
- The header search on a Spanish page, typing Concord: "10 barrios electorales · Condado de
  Merrimack".

## 8. Live Now

- `/live` is a new page, linked from nowhere yet. With nothing streaming it says "No stream
  found right now" and names the House's and Senate's own streams. It has no
  `/session/H/today` link.
- `/committee/H43` draws to its end on a weekend, with no live box.

## 9. Small things

- `/no-such-page` shows one heading, with no "NO PAGE AT THIS ADDRESS" box above it.
- `/bill/2026/sb400/documents` reads "Committee report, House Calendar 16 (2026)".
- `/bill/1995/hb1/hearings` reads "Committee of Conference", with a small "of".
- `/bill/2018/hb1500/reports`: the interim study report is dated Nov 9, 2018.

## 10. Coming in dry run 2 (walk on its own address)

- **Back keeps the search**, `fix/bill-back-notfound`:
  - Search HB 703 in All Terms, open 2020's, and press Back. The address is
    `/bills?q=HB+703&term=all`, the box says HB 703, and 10 bills are listed. Forward reopens
    the bill.
  - Back also keeps ticked filters, the order chosen, and words typed but not run, and comes
    back to the same place after a reload.
- **The not-found page finds the bill, and the town**:
  - `/bill/2026/hb703` says "Looking for HB 703 in the 2025–2026 term…", then goes to
    `/bill/2025/hb703`.
  - `/bill/2026/hb9999` offers "Search for HB 9999 in every term".
  - `/town/manchster` asks "Did you mean Manchester?".
  - `/town/dover-ward-9` asks "Did you mean Dover? It has wards 1 to 6."
  - `/town/harts-location` goes to Hart's Location.
- **Search reads what people type**, `fix/search-forms`: "Senate Bill 11", "H.B. 703", "O'Neil"
  with a curly apostrophe, "Hart's Location", "LSR 2027-0002".
- **Each Spanish page says once what stays in English, and why**, `guides-es-language-note`:
  `/es/`, `/es/officials` and `/es/guides/how-to-vote`.
- `sources/strafford-officials` changes no page.

## For you to decide

The deep walk found nothing that holds the release. These two are new with it, and both
come from joining the 30 people's two pages into one:

1. **The former-members directory lists eight people under one chamber only.**
   - `/directory/former-legislators` lists each joined person once, under the chamber of the
     page kept. Cilley, Leo Fraser, Edward (Ned) Gordon, Fenton Groen, Frederick King, Amanda
     Merrill, Andrew Peterson and Frank Sapareto sat in the Senate, but appear only under the
     House.
   - So its count line says 89 former senators and 1,662 former representatives. The record
     has 97 and 1,688, and live says so.
   - Each person's row and page are right. It is the lists and the count that are short.
   - The fix is in one function of the directory builder, small enough for dry run 2 if you
     want it there.
2. **Michael Downing's one page calls him a Republican throughout.**
   - He sat in the House in 1999–2002 as a Democrat, as your note on the pair says.
   - His old House address now lands on that page, and his 1999 bill still names him "(D -
     Rock 26)".
   - He is the only one of the 30 whose party differs between chambers. The fix, a party for
     each chamber's years, is larger, and fits 24 November better.

## Already on live, and still there (for 24 November)

- `/session/H/2006-04-19`, and `/bill/2006/hb1724`, credit a motion to "Rep. Seth King". It was
  Frederick King's: Seth King's record starts in 2023.
- Some House days credit a former member's motion to a sitting member of the same name who was
  not yet in the House: Butler in 2014, Grossman in 2014, Schultz in 2012.
- `/bills#2020/HB703`, an address naming an older term only in its fragment, opens 2025's HB
  703.
- A tab clicked on a bill opened from such an address writes `/bills/votes?…`, which is not a
  page.
- A bill opened from the search keeps the search's tab title in the browser tab.

## Small things the walk noted (nits)

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
