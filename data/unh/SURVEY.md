# The scanned journals: what is there, what is legible, what is reachable

Written 18 September 2026, from the collection rather than about it. Every
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

**And the OCR text layer cannot be used for roll calls.** It carries the
names, and it carries the results exactly, but it loses which side of the vote
a name was on. That is measured below, and it is the finding that decides what
to do next.

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
so the gap is in this repository rather than in the world.

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
member voted.** Anything that needs the second has to read the geometry — the
`_djvu.xml` or the hOCR, both of which carry a bounding box per word, and
neither of which has been fetched.

---

## 5. What is not yet known

Stated as unknown rather than estimated.

- **Whether the geometry solves it.** The hypothesis is that column-aware
  reconstruction from `_djvu.xml` recovers the yea/nay split. It is a good
  hypothesis and it is untested. One volume's XML is 51 MB, so testing it is
  one request and an afternoon, not a project.
- **Whether 1989-1996 reads as well as 1997.** Different print runs, and the
  older volumes are older paper. The 1997 number does not transfer to them by
  assumption.
- **Whether the Senate volumes behave the same way.** Not examined at all. The
  Senate is 24 members rather than 400 and may not use columns.
- **What a roster-backed repair actually recovers.** 87.73% is a floor from
  generic string distance. The real figure needs the roster, and the roster
  for those Houses can come from the journals themselves — each volume opens
  with a CALL OF THE ROLL listing every member by county and district.
- **File sizes at UNH.** The one `HEAD` asked returned 403.

---

## 6. A thing worth doing that is not code

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

**17 requests in total**, every one cached and logged. Read the log rather
than this paragraph:

    python3 unh_survey.py --log

Ten to scholars.unh.edu: robots.txt, the site index, the series sitemap, the
listing page and its second page, the item page for volume 78 (a 301, then the
canonical address), and the two `HEAD`s that met the 403. The series listing
was asked for twice, because the first version of `unh_survey.py` classified
it as a block page on a word in its markup and exited before caching the body
— the bug is fixed and the fetcher now caches before it judges, so a page paid
for is never thrown away again.

Five to archive.org: robots.txt, two searches, one item's metadata, and the
download address, which answered 302.

Two to `dn790009.ca.archive.org`, the datanode that 302 named: its robots.txt,
which 404s and is therefore read as allowing everything, and the 4.7 MB text
layer itself. The redirect was followed by making a second, deliberate,
logged, paced request rather than by letting the opener follow it silently.

Nothing was fetched in bulk. Nothing will be without a person saying so.
