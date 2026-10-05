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

Two files are neither code nor derived text. ground_truth.csv and
review/checked.jsonl are measurements a person made by watching recordings with
a stopwatch. They are included under the same terms, and are worth naming
separately only because they cannot be regenerated: if they are lost, somebody
has to sit down and watch the videos again.

One file holds figures from outside the General Court's record.
ballot_results.json is the statewide Yes and No vote on each constitutional
amendment both chambers sent to the voters, copied by hand from Ballotpedia's
list of New Hampshire ballot measures; each row names the page and the day it
was read, and says which CACR it is and why. The counts are facts, and no
claim is made over them; the page they came from is Ballotpedia's and is not
reproduced here. Like the files above, a person writes it and no script does.

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
at those sizes. Both live in brand/ and assets/ on the machine that builds the
site, gitignored, and reach the nightly build through the project's private
kit. The one file of assets/ that is tracked is site.webmanifest, which is
text and is MIT like the code.

The clipart was in the repository until it was removed on 1 October 2026, so
commits from before the removal carry it: the images in brand/, the copies of
them at the root (Icon.png, Logo Black.png and Logo White.png), and what
build_brand.py drew from them into assets/. The history was not rewritten.
Those files were never offered under the MIT licence and are not now; that an
old commit still holds them is not a licence to use them.

A fork of this project should bring its own. The code that draws the icons,
build_brand.py, is MIT like the rest of the code, and says what to put in
brand/ when it is run without them; or put finished files in assets/ under the
names build_pages.py lists as BRAND_FILES, and a mask named mark.png for a
mark in the header. Without them the build still runs: it says once which
files are missing, sets the home page's heading as text and the header as the
site's name alone, and leaves the icon links in each page's head pointing at
nothing -- which check_site.py reports as one error, so that a site without
its icons is not published by accident.

Two things in the code are this project's and a fork changes them with its
logo. The footer of every page and the About page credit Debra Caplan for the
logo, as her licence asks; that credit is written in bills.html and in
build_pages.py (shell() and ABOUT), it is printed whether or not her files are
there, and a site that does not carry her drawing should not carry it. And
.gitignore keeps every image out of brand/ and assets/, because this
repository may hold none: a fork that wants its own logo in its own repository
takes those lines out. preflight's _logo_licence check holds both in place for
this project -- the credit present, the images untracked -- and is the check
to change with them.
