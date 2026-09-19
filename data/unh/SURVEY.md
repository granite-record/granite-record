# The scanned journals: what is there, what is legible, what is reachable

Written 18-19 September 2026, from the collection rather than about it. Every
number here came from a command named beside it, and every command reads
either this repository or a file cached under `archive/unh/raw/`. Re-run them
rather than quoting this file; it will drift and they will not.

---

## The short version

The collection is real, it is deep, and its terms are clear. The whole of the
gap this project has — 1989 to 1998, both chambers — is covered, save one
volume. The books were scanned by the Internet Archive, which publishes them
with an OCR text layer and a documented API, so nothing needs to be crawled
out of the university's repository.

**The OCR text layer as published cannot be used for roll calls.** It carries
the names, and it carries the results exactly, but it loses which side of the
vote a name was on.

**The geometry beside it can.** Every item also publishes a `_djvu.xml` with a
bounding box per word. Rebuilding the printed reading order from those boxes
— group into lines by y, sort each line by x, and nothing cleverer — takes the
yea/nay split from 7% correct to 87%, and name agreement from 85.26% to
95.74%. A repair pass against the General Court's own list of past members
then takes them further. Sections 4 and 6.

**The number to quote is 96.81%, and 99% on the split** — the 1998 House
volume, fetched after the work was finished and measured once, on the largest
sample of the five. Everything else was developed against, and reads 1.7
points higher.

**And the roster comes out of the same book.** A volume that organises a new
House opens with the CALL OF THE ROLL, and reading 1997's yields 400 seats
against 400 the journal declares, no district disagreeing. Section 5.

**Five volumes, and both chambers.** 1991 scored 0% on the split until four
patterns quietly fitted to 1997 were found and generalised; it now scores 98%.
The Senate does none of what the House does — it writes a sentence rather than
four columns, and contains the word YEAS zero times — so it needed its own
reader, and scores 100% on the split. 1993, the volume UNH lacks, came from a
different depositor and needed two more parser changes; 94% first time.

---

## 1. What the collection holds

`https://scholars.unh.edu/senate_house/` — "Journals of the Senate and the
House of Representatives of NH", in the University of New Hampshire's
Digital Commons repository.

**145 volumes, numbered 1 to 145, no gaps**, spanning **1881 to 2006**. One of
the 145 is an index rather than a journal. By chamber: 77 Senate, 51 House, 16
bound with both, 1 index.

    python3 unh_parse.py --catalogue     # writes data/unh/catalogue.csv
    python3 unh_parse.py --coverage      # year by year, both chambers

A volume is a bound book, not a sitting day, and its title says what is bound
into it. Reading the list as one volume per year is wrong and produces three
phantom gaps: the House appears to have nothing for 1990, 1993 or 1996, and
two of those three are an artefact of binding. 1990 sits in the volume that
opens with the special session of December 1989; 1996 in the one that opens
with the recall session of November 1995.

### The decade this project needs

    python3 unh_parse.py --gap

| year | House | Senate |
|------|-------|--------|
| 1989 | 71, 72 | 114 |
| 1990 | 72, 73 | 115 |
| 1991 | 73 | 116, 117 |
| 1992 | 74 | 118, 119 |
| **1993** | **absent** | 120, 121 |
| 1994 | 75, 76 | 122 |
| 1995 | 76, 77 | 123 |
| 1996 | 77, 78 | 124 |
| 1997 | 78 | 125, 126 |
| 1998 | 79, 80 | 127, 128, 129 |

**One volume is missing from the collection: the 1993 House Journal.** The
Senate has 1993 in two volumes; the House jumps from the 1992 session to the
1994 session. It is not a binding artefact — no title names 1993.

It is, however, on the Internet Archive under a different upload
(`vol1993journalofthehouseofrepresentativesofthestateofnewhampshireattheirsession`),
deposited in 2019 by `lawlibrary@courts.state.nh.us` rather than scanned for
UNH in 2009 — so the gap is in that repository rather than in the world. It is
fetched, reflowed and measured: 1,106 pages, 96 roll calls, 94% on the split.

Two parser changes were needed and both are worth knowing for any other
volume from that depositor: its files are named after the book rather than
the item (`Vol 1993 Journal of the House ... _djvu.xml`, with spaces), and its
word coordinates carry a fifth number and no confidence attribute. Requiring
exactly four parsed the whole volume to zero words, which the guard in
`reflow()` caught rather than writing out an empty file.

---

## 2. The format, and the machine route

Each item page carries a bepress record. For volume 78, the 1997 House
session:

    File Format          application/pdf
    Rights               http://rightsstatements.org/vocab/NKC/1.0/
    Scanning Information Scanned by Internet Archive, Open Content Alliance (2008)
    Contributor          Typesetting by State of New Hampshire Bureau of
                         Graphic Services, Printing by Michie

**Rights: "No Known Copyright"** (rightsstatements.org NKC). These are the
legislative journals of a US state, which is about as clearly a government
edict as a document gets; the rights statement says the library reached the
same conclusion and could not make it conclusive. Nothing here asserts a
licence over them.

### robots.txt closes the obvious route and opens another

`https://scholars.unh.edu/robots.txt` disallows `/do/` to every agent. That is
where a Digital Commons repository keeps its **OAI-PMH endpoint**, which was
the machine route this survey went looking for. It is closed. `unh_survey.py`
had it in `--recon` until robots.txt said otherwise, and now parses robots.txt
and asks it before every request rather than remembering the rule in prose.

The same file advertises a sitemap, `https://scholars.unh.edu/siteindex.xml`,
which leads to `senate_house/sitemap.xml` and every one of the 145 item
addresses. That is the enumeration route the host offers, and it is what the
catalogue was built from.

Downloads are directly constructible:

    item page   https://scholars.unh.edu/senate_house/<N>/
    the PDF     https://scholars.unh.edu/cgi/viewcontent.cgi?article=<N+999>&context=senate_house

The `+999` is held as a fact, not a guess: it agrees on **all 145** pairs
printed on the two listing pages, and volume 78's own citation metadata names
`article=1077` independently. `unh_parse.py --catalogue` reports the count of
agreeing pairs on every run.

### scholars.unh.edu answered 403, and that is on file

A `HEAD` request for volume 78's PDF returned **HTTP 403**. Nothing else has
been asked of that host since; `archive/unh/refused.scholars.unh.edu.json`
records it and `unh_survey.py` refuses to ask again for 24 hours.

**This may well mean only that the CGI does not implement `HEAD`.** Telling
that apart from a block needs asking the same address again by another method,
which is the definition of working around a refusal, so it was not done. Two
requests in total had been made to that host before the 403 and neither was
refused. It is a person's call.

It also no longer matters much, for the reason in the next section.

---

## 3. The better source, named by UNH's own record

The scanning note points at the Internet Archive, and the volumes are there,
sponsored and contributed by the University of New Hampshire Library:

    python3 unh_ia.py --find '"New Hampshire" AND (title:("journal of the house") OR title:("journal of the senate")) AND year:[1988 TO 2000]'

**36 items for 1988-2000**, identifiers of the form `journalofhouseof1997newh`
and `journalofsenateo1994newh`. archive.org's robots.txt disallows only
`/control/` and `/report/`; `/metadata/`, `/download/` and
`/advancedsearch.php` are open, and the metadata API is documented and
intended for this.

Each item carries derivatives beside the scan. For `journalofhouseof1997newh`:

    python3 unh_ia.py --files journalofhouseof1997newh

| bytes | what |
|-------|------|
| 63,332,252 | Text PDF |
| 98,107,106 | hOCR — **word positions** |
| 51,375,764 | DjVu XML — **word positions** |
| 4,746,829 | DjVuTXT — the flattened text layer |

Item metadata: **1,156 pages**, 400 ppi, Canon 5D, scanned at Boston,
**OCR by ABBYY FineReader 8.0**, public since April 2009.

So the year can be examined for **4.7 MB instead of 63 MB**, and the geometry
is available if the flat text proves insufficient — which it does.

---

## 4. What can actually be got out of a page

    python3 unh_measure.py

1997 was chosen because the site already holds it: `journals/1997/` has
sixteen sitting days of the House in text from the General Court's own digital
copy. That is a source this project did not generate, covering the same roll
calls, so it can score the scan. Nothing about 1997 is needed — 1989 to 1996
is, and there is nothing there to check against, so a number measured on 1997
is the only honest claim available about them.

### The scan holds more of 1997 than this site does

The bound volume contains **all 25 sitting days**. `journals/1997/` holds
**16**. Nine days of the 1997 House — HJ002, 004, 010, 012, 014, 017, 020, 022
and 024 — exist in the scan and nowhere in this repository.

### Results: exact

Every roll call the digital copy records appears in the scan with an
**identical tally**. 53 of 53, zero discrepancies. The scan has 82 in the full
volume, the extra 29 being the nine missing days.

### Names: 85.27%, and that is a floor on the extractor, not on the scan

Of **14,588 member votes** the General Court's copy records across the 41 roll
calls present in both, the scan carries **12,439 under the same name —
85.27%**. A further **2.46%** are present but damaged, in the way 2009 OCR
damages this typeface:

    adler, rudolf      read as   adier, rudolf
    cushing, robert    read as   gushing, robert
    macintyre, doris   read as   maclntyre, doris
    vogl, john         read as   vogi, john
    coes, betsy        read as   goes, betsy

Those are l/i, C/G and I/l confusions against a **closed set of 400 known
members**, so a repair pass against the roster of that House should recover
nearly all of them. 87.73% is where such a pass starts, not where it ends.

One thing tried and reverted, recorded so it is not tried again: the scan
drops commas (`McCarthy  William`, `Reidy  Frank`), so the name pattern was
relaxed to accept two spaces in place of the comma. Agreement fell from 85.27%
to **51.29%**, because the digital copy is column-aligned and "Gordon Boyce"
out of "Bartlett, Gordon Boyce, Robert" became a name. The comma stays
required. Dropped commas turn out to account for only 3.2% of what is missing
anyway.

### And then the finding that decides everything

    python3 unh_measure.py --split

| | |
|---|---|
| roll calls whose **total** names are within 3 of yeas+nays | **51 of 82 (62%)** |
| roll calls where **each side** is within 3 of its own heading | **9 of 82 (11%)** |

**The names are there. Which side they are on is not.** A roll call the House
decided 186-185 comes out of the flattened text as 232 names under YEAS and
137 under NAYS.

The cause is structural rather than a matter of OCR quality. The journals set
roll calls in four columns under county headings; the General Court's text
flattens them row by row, and the DjVu text flattens them column by column.
Under column-major reading the `NAYS 114` heading is just another object on
the page with a position, and it does not land between the two lists.

A parser built on `_djvu.txt` would therefore produce roll calls that look
entirely plausible and put named members on the wrong side of votes. That is
the failure this project's rules are written against, and it is worse than
publishing nothing, because a wrong vote attributed to a named legislator is a
factual error of the first kind on a site whose readers include those
legislators.

**The flattened text can say what a roll call decided. It cannot say how a
member voted.**

### The geometry fixes it, and the fix is small

    python3 unh_rollcalls.py --reflow journalofhouseof1997newh
    python3 unh_measure.py --ocr data/unh/reflow/journalofhouseof1997newh.txt

The `_djvu.xml` carries a bounding box per word. Page 85 of the 1997 volume
states the layout with no inference required:

    y 1131   [823]YEAS [986]186 [1082]NAYS [1243]185
    y 1210   [949]YEAS [1114]186
    y 1305   [939]BELKNAP
    y 1384   [61]Laflam, [197]Robert   [560]Veazey, [701]John

Four columns at x of roughly 60, 561, 1062 and 1566, headings centred over
them, rows running across. So the reading order is: group words into lines by
y, sort each line by x, take pages in order. That is the whole of it — no
column detection and no heuristics, because the geometry already says it.

Scored by the **same extractor**, so the only difference is reading order --
and then again after `unh_repair.py`, for which see section 6:

| 1997 House | flat `_djvu.txt` | reflowed | repaired |
|---|---|---|---|
| names carried exactly | 85.26% | 95.74% | **98.54%** |
| **each side within 3 of its heading** | **7%** | **87%** | **96%** |

Five volumes now, and both chambers:

| volume | names | split | roll calls compared | against |
|---|---|---|---|---|
| **1998 House — held out** | **96.81%** | **99%** | 76 | `journals/1998` |
| 1997 House | 98.54% | 96% | 39 | `journals/1997` |
| 1991 House | not measurable | 98% | — | nothing exists |
| 1993 House | not measurable | 94% | — | nothing exists |
| 2003 Senate v.1 | 98.95% | 100% | 13 | `journals_senate/2003` |

**Read the 1998 row first.** Every other figure comes from a volume the
patterns were developed against; 1998 was fetched after the work was finished
and measured once, on the largest sample of the five. It scores 1.7 points
below 1997, which is a fair estimate of how much of the 1997 figure is
fitting rather than method. Its repair gained +2.6 points over the reflow
alone, so the repair generalises.

The name figures are **no longer blind**. They use `past_members.json`, the
General Court's own list of past members, as the authority for spelling, and
are then scored against the General Court's journals — different products,
same institution, so they agree. What stays blind is the split and the
vote-list counts, which never consult a roster.

### A second volume, which found four patterns fitted to the first

Everything above is one book. The 1991 House volume -- in the decade this is
actually for -- scored **0%** on the split when the 1997-shaped patterns were
pointed at it, and now scores **98%**, better than 1997. What was wrong:

* 1991 sets **three** columns where 1997 sets four, and the rule bounding a
  vote list allowed two leftover words per line. Three names with middle
  initials leave three initials behind, so the line read as prose and the
  list ended 623 characters into a 3,372-character block. It is a fraction of
  the line now, which does not care how many names share one.
* 1991 prints the comma as a **full stop** about half the time:
  `Hunt. John B.  Kingsbury, H. Thayer  Met/ger. Kathcrine H.`
* Middle initials became people. `Campbell, Richard H., Jr` yielded a second
  member called `H., Jr`, and `Dodge, A. Gibb, Jr.` yielded `Gibb, Jr.`
* The running head lands inside vote lists in both volumes, and 1991's reads
  `76 HorsK JoruNAi, Fiohruaky 5, 19})1`. It is dropped by geometry now --
  first line, top 7%, set off by 1.5x that page's own line spacing, carrying
  a bare number -- not by matching words that do not survive a decade.

---

## 5. The roster, out of the same book

    python3 unh_roster.py journalofhouseof1997newh --against journals/1997

Every volume opens with the CALL OF THE ROLL: every member by county and
district, with a full name and the party or parties that nominated them.

| | |
|---|---|
| seats the journal declares | 400 |
| seats this reads out of it | **400**, 0 of 195 districts disagreeing |
| named on organisation day | 392 |
| seats held open, "Elected, not sworn" | 8 |

The journal confirms it in its own words: *"With 392 members having answered
the call of the roll, a quorum was declared present."* The eight open seats
are filled later in the volume by a COMMUNICATION from the Secretary of State
— `Grafton 11, Philip Cobbin, r&d, Canaan` — which is why Cobbin cast 77 votes
in 1997 and is not in the December roll. Street addresses printed there are
deliberately not read; the town is.

Against the members who actually cast votes in the General Court's own digital
journals, **347 of 368 surnames — 95.92% of member votes**. The 21 misses are
one name spelled two ways, and the roll is the wrong one:

    Colburn  read as  Colbum        Coes       read as  Goes
    Burnham           Bumham        Fraser              Eraser
    O'Hearn           O'Heam        MacIntyre           Maclntyre
    Letourneau        Letoumeau

which is **rn→m**, C→G, F→E, I→l — the same confusions the vote lists show.

**The useful part: the roll and the roll calls are damaged independently.**
`Colbum` appears once in the roll; `Colburn` appears 58 times in that year's
votes. So the two halves of one book correct each other and no outside roster
is needed — which is exactly what makes 1989–1996 tractable, where no outside
roster exists.

---

## 6. The repair pass

    python3 unh_repair.py journalofhouseof1997newh --vocab
    python3 unh_measure.py --ocr data/unh/repaired/journalofhouseof1997newh.txt

Two things survive the reflow, and neither is a lost name:

* **a spelling the scan damaged** — `Adier` for Adler, `goiding` for Golding,
  `feriand` for Ferland in 1997, which is l/i; and `bartlctt`, `paquettc`,
  `grecnglass` in 1991, which is e/c. Different print runs fail differently.
* **a comma the scan dropped** — page 452 prints `Kibbey David`, and the name
  pattern requires the comma for a reason measured earlier.

Both are fixable because the candidate set is **closed**: four hundred members
sat in that House and the journal prints all four hundred in its own roll.

The roll is damaged too, by the same machine on the same day. What saves it is
that the two halves are damaged *independently*, so the canonical spelling is
the one the whole volume prefers, and the roster's job is to say which
surnames are real people rather than how they are spelt.

**The rule and its refusal.** A rare spelling is replaced by a common one when
they are close, the rare one is at most a third as frequent, and **the rare
one is not on the roll**. That last clause was learned the hard way: the first
version refused only when *both* spellings were on the roll, and it rewrote
**Clemons to Clemens**. Jane A. Clemons and Kevin Clemons, Sr. sat in that
House; the scan reads their name as Clemens twenty-six times and Clemons
three, so frequency pointed the wrong way and the pass turned three correct
spellings into none. Putting a real legislator's name wrong is the worst thing
in this project's triage order, so the roll now protects a name absolutely.

It costs repairs: Clemens stays misread in those twenty-six places, because
nothing available here can prove which spelling is right. The per-word
`x-confidence` in the DjVu XML is an independent signal that could settle it
and is not yet used.

Every substitution is printed by `--vocab`. 89 in 1997, 80 in 1991, and none
of them touches a name on the roll.

---

## 7. What is not yet known

Stated as unknown rather than estimated.

- ~~**Whether the geometry solves it.**~~ Tested: it does, and the repair pass
  on top of it. 7% to 96% on the split, 85.26% to 96.31% on names.
- ~~**Whether 1989-1996 reads as well as 1997.**~~ 1991 does, once the
  patterns stopped being fitted to one volume: 98% on the split, better than
  1997. Its name accuracy is NOT measured and cannot be -- there is no digital
  copy of 1991 to check against, which is the whole reason the era needs this.
- **Which spelling is right when the roll and the votes disagree.** Clemons
  and Clemens is the worked example in section 6. The per-word `x-confidence`
  the DjVu XML carries is an unused independent signal and is the obvious
  next thing to try.
- **Whether the Senate volumes behave the same way.** Not examined at all. The
  Senate is 24 members rather than 400 and may not use columns.
- **What a roster-backed repair actually recovers.** 87.73% is a floor from
  generic string distance. The real figure needs the roster, and the roster
  for those Houses can come from the journals themselves — each volume opens
  with a CALL OF THE ROLL listing every member by county and district.
- **A third volume, and a Senate volume.** Two House volumes agree; the Senate
  is 24 members, is scanned at 300 ppi rather than 400, and may not use
  columns at all. Nothing here has been tried on one.
- **File sizes at UNH.** The one `HEAD` asked returned 403.

---

## 8. A thing worth doing that is not code

UNH's library digitised this collection and put it in a repository, and the
Internet Archive scanned it for them. Libraries in that position often prefer
to hand over a copy than to be crawled, and this project would rather ask than
assume. The collection sits under UNH's "NH State Publications"; the
repository's contact route is the one a person should use, not a script.

It is worth an email before any bulk retrieval, whichever host it comes from —
both because it is the courteous order of operations, and because a library
that has already produced derivative files may simply send them.

---

## How everything here was retrieved

This paragraph used to state a total. It was wrong three times -- by 9, then
by 2, then by 5 -- because it is written by hand and the fetching went on
after it. So it no longer states one. The log does, and the log has been
right every time:

    python3 unh_survey.py --log

Everything asked of scholars.unh.edu was asked on 18 September, before the
403; nothing has been asked of it since. Everything after that is the
Internet Archive and the datanodes it redirects to -- searches, item
metadata, and one _djvu.xml per volume examined.

Nothing was fetched in bulk. Nothing will be without a person saying so.
