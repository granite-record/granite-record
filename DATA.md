# What this licence covers, and what it does not

`LICENSE` is the MIT licence, and it is kept to the canonical text so that
GitHub and the usual tooling can recognise it. This file is the part that
does not fit in a standard licence: what the MIT terms apply to here, and
what they cannot apply to.

WHAT THIS COVERS, AND WHAT IT DOES NOT

The MIT licence above applies to the SOFTWARE in this repository: the scripts
that fetch, parse, measure and build, the checks, the front end, and the
documentation.

It does not, and cannot, apply to the underlying public record. The bills,
votes, calendars, journals and recordings of the New Hampshire General Court
are the State of New Hampshire's, published by them, and this project makes no
claim over them. Facts are not copyrightable and nothing here tries to make
them so.

Between those two sit the derived texts this project writes: the plain-English
bill histories in narratives.json, the explanatory pages under /learn, and the
editorial notes on particular bills. Those are authored. They are offered under
the same terms as the code above, so a person building on this does not have to
reason about which sentence came from where.

Two files are neither code nor derived text. review/ground_truth.csv and
review/checked.jsonl are measurements a person made by watching recordings with
a stopwatch. They are included under the same terms, and are worth naming
separately only because they cannot be regenerated: if they are lost, somebody
has to sit down and watch the videos again.

One file holds figures from outside the General Court's record.
corrections/ballot_results.json is the statewide Yes and No vote on each constitutional
amendment both chambers sent to the voters. Each row names its source, where
the count is printed and the day it was read, and says which CACR it is and
why. For every amendment the voters have decided the source is the Secretary
of State: its results pages on sos.nh.gov from 2016, and before that the
Department of State's Manual for the General Court, read from NHPR's scans of
it. Ballotpedia's figures stay on each of those rows as a cross-check. They
differ on two No counts, CACR 7 of 1992 and CACR 41 of 2006, where the file
takes the Secretary of State's. The one amendment still to go to the voters,
CACR 13 of 2025-2026, names Ballotpedia's list of New Hampshire ballot
measures until its count is in. Every page that shows one of these counts
names whose it is from that row's own source. The counts are facts, and no
claim is made over them; no source's page is reproduced here. Like the files
above, no script writes it.

One more is from outside the record, and is drawn rather than read. The
district map's boundaries (generated/district_geometry.json, published inside
/district_map.json) are NH GRANIT's 2022 district layers and its town
outlines, from the University of New Hampshire, made small by
src/towns/build_district_geometry.py. GRANIT's metadata states no access
constraints and "Not for legal use", and the map says so under it: the
Secretary of State's published district definitions are the legal text. The
shapes are GRANIT's; nothing here is claimed over them.

WHAT EACH PUBLISHED FILE HOLDS

The site's own JSON and feeds are listed, with what each holds, in README.md
under "The data". The bulk downloads describe themselves: /data/manifest.json
names every CSV with its rows, size and columns, every term's bill index
(/idx/<term>.json) with its address, bills and size, and a coverage table by
term, so the counts are read from the file rather than from a document.
/index.json, which held every bill of every term in one file, was retired on
5 October 2026; the files under /idx/ are the same rows, a term at a time.

THE DATA API

The files /api describes -- the database (granite-record.sqlite.xz), the bill
files (bills-<term>.jsonl.gz), people.json and people.csv, and schema.json --
carry the same record, and the same line between what is the State's and what
is this project's. The record is the State of New Hampshire's. What this
project adds to it -- the ids it gives (person numbers, and a bill's key,
term and number together), the joins it makes (which numbers are one person,
which report belongs to which bill) and the corrections made here by hand --
is dedicated to the public domain under CC0 1.0
(https://creativecommons.org/publicdomain/zero/1.0/): anyone may use it for
anything, without asking. The plain-English histories (narrative and stages
in a bill's record) stay under the terms above. The times within a recording
are not yet covered by this paragraph: they place a moment in a YouTube
video, and whether they are this project's to dedicate waits on a decision
about YouTube's terms (docs/design/api/DESIGN.md, Q18). schema.json names
the terms of each file.

One file is published for a few weeks every two years and is gone the rest
of the time. /members_elect.json is who a general election sent to the New
Hampshire House and Senate, for the weeks between the election and
Organization Day, the first Wednesday of December, when they take office.
src/parse/build_members_elect.py writes it only in those weeks, and only
while the site's newest term is the one before theirs; it removes the file on
Organization Day and outside them. It is drawn from the Secretary of State's
results, read by a person into collected/election_<year>.json, and from the
person's own settling of names and recounts in corrections/members_elect.json,
of which only the outcome is published. It holds the election's day
("election"), the day they take office ("takes_office"), the term they serve
("term"), the address of the results it was read from ("sources"), and every
State Representative and State Senator race on the district table under
"races", keyed "H|<County>|<district>" and "S|<district>": its "seats"; the
members-elect in "elected", each with their name first name first ("n"), their
party's letters ("p", both of them where a candidate won two nominations,
"R/D", and none where none was printed) and whether they sit now, sat before
or are new ("k") -- with the id ("id") and page ("s", /legislator/<s>) of the
sitting or former member they are only where that match is certain; how many
seats are "not_final", which is every seat until the recount deadline has
passed; "recount", where a recount was asked for; and how many are "held"
back. It holds no vote counts, no contact details and no reason the person
gave. Every page draws a member-elect from this file and from nothing else,
never as a sitting member: /places.json carries the same races for a town's
own districts under "elect" (each place naming its own in "e"), and
/district_map.json under "elect", both only while the file is there. The
Governor, the Executive Council and Congress are not in it. The results are
the Secretary of State's; no claim is made over them.

What the public sends is never published as an individual's. Testimony
sign-ins appear as counts on a bill and its hearings, from the General
Court's database: src/fetch/gc_db/fetch_testimony_db.py counts them in SQL,
so no name, town or written testimony is ever fetched, and
src/parse/testimony_from_db.py counts the archived terms from the dump on
disk, both into testimony_db.json. The scraped testimony.json was retired on
5 October 2026. And the reports readers send through the "report a problem"
box are not published at all.

THE LOGO AND THE ICONS ARE NOT HERE

The logo and the icons are not offered under the MIT licence, or under any
other terms, and they are not in this repository. This project uses them under
licences from their owners, and those licences are not its to pass on to
anyone else.

There are two sets. The logo proper -- the home page's heading, the mark in
the header and the cards a shared link unfurls into -- is drawn by Debra
Caplan, an artist in Peterborough, New Hampshire (linescapesnh.com), and
licensed from her; her files have never been in this repository. The favicon
and the other small icons are clipart the project bought, which reads better
at those sizes. Both live in brand/ and assets/ on the maintainer's machine,
gitignored, and the finished files in assets/ reach the nightly build through
the project's private kit (the list in cloud_kit.json); brand/, which they are
drawn from, goes to the private backup only. The one file of assets/ that is
tracked is site.webmanifest, which is text and is MIT like the code.

The clipart was in the repository until it was removed on 1 October 2026, so
commits from before the removal carry it: the images in brand/, byte-identical
copies of three of them at the root under the names they arrived with
(Icon.png, Logo Black.png and Logo White.png, which no code read), and what
build_brand.py drew from them into assets/. The history was not rewritten.
Those files were never offered under the MIT licence and are not now; that an
old commit still holds them is not a licence to use them.

A fork of this project should bring its own. The code that draws the icons,
src/pages/build_brand.py, is MIT like the rest of the code, and says what to
put in brand/ when it is run without them; or put finished files in assets/
under the names src/pages/build_pages.py lists as BRAND_FILES, and a mask
named mark.png for a mark in the header. Without them the build still runs: it
says once which files are missing, sets the home page's heading as text and
the header as the site's name alone, and leaves the icon links in each page's
head pointing at nothing -- which src/checks/check_site.py reports as one
error, so that a site without its icons is not published by accident.

Two things in the code are this project's and a fork changes them with its
logo. The footer of every page and the About page credit Debra Caplan for the
logo, as her licence asks; that credit is written in bills.html and in
src/pages/build_pages.py (shell() and ABOUT), it is printed whether or not her
files are there, and a site that does not carry her drawing should not carry
it. And .gitignore keeps every image out of brand/ and assets/, because this
repository may hold none: a fork that wants its own logo in its own repository
takes those lines out. preflight's _logo_licence check holds both in place for
this project -- the credit present, the images untracked -- and is the check
to change with them.
