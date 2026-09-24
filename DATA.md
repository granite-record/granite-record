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

THE LOGO IS NOT COVERED

The logo is the one part of this repository that is not offered under the MIT
licence, or under any other terms. It is used by this project under a licence
from its owner, and that licence is not passed on to anyone else.

That covers the images in brand/, the copies of them at the root of the
repository (Icon.png, Logo Black.png and Logo White.png), and everything
build_brand.py draws from them into assets/: the mark, the lockup, the icons,
the favicon and the link-preview cards. The logo is drawn by Debra Caplan, an
artist in Peterborough, New Hampshire (linescapesnh.com), and licensed from
her; her files are not in this repository at all, because the licence is not
the project's to pass on. They live in brand/licensed/ and assets/licensed/ on
the machine that builds the site, both gitignored. The favicon and the other
small icons are still the clipart the project bought, which reads better at
those sizes; the same terms apply to it.

A fork of this project should bring its own logo. The code that draws one,
build_brand.py, is MIT like the rest of the code; the pictures it draws are not.
