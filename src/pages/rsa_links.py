#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-09.2
"""
Where a statute citation links: the readers every bill text shares.

RSA_CITE finds "RSA 91-A:4" in words, rsa_url says where it links (the site's
own /laws page where the statute table holds it, the General Court's else, or
nowhere), and rsa_links makes the {citation as written: url} map a page links
from. They were build_site_v2's; they live here so that the version indexes
(build_bill_versions.py), which are written before that script runs, link the
texts of every version and amendment the same way, from the same code.
"""

import re

# --------------------------------------------------------------------- RSA --
# A statute cites as "RSA 91-A:4", and its page lives at
#
#     /rsa/html/VI/91-A/91-A-4.htm
#             ^^ the TITLE, which the citation does not carry
#
# So the chapter has to be resolved to a title first. The General Court's own
# table of contents at /rsa/html/nhtoc.htm lists every title with the chapters
# it covers, and that is the table below, read from it on 4 September 2026.
#
# Chapters sort as (number, suffix), which is what makes the awkward pairs come
# out right: chapter 361 is Title XXXIII and 361-A is XXXIII-A; 227-F ends Title
# XIX and 227-G begins XIX-A. Comparing the pair handles both without a special
# case. A chapter in none of the ranges -- 251 to 258 exist in no title -- is
# not linked at all, because a citation link that 404s is worse than plain text.
RSA_TITLES = [
    ("I", "1", "21-V"), ("II", "22", "30-B"), ("III", "31", "53-G"),
    ("IV", "54", "70"), ("V", "71", "90"), ("VI", "91", "103"),
    ("VII", "104", "106-R"), ("VIII", "107", "119"), ("IX", "120", "124-A"),
    ("X", "125", "149-R"), ("XI", "150", "152"), ("XII", "153", "174"),
    ("XIII", "175", "180"), ("XIV", "183", "185"), ("XV", "186", "200-O"),
    ("XVI", "201", "202-B"), ("XVII", "203", "205-D"), ("XVIII", "206", "215-D"),
    ("XIX", "216", "227-F"), ("XIX-A", "227-G", "227-M"), ("XX", "228", "250"),
    ("XXI", "259", "269"), ("XXII", "270", "272"), ("XXIII", "273", "283"),
    ("XXIV", "284", "287-J"), ("XXV", "288", "288"), ("XXVI", "289", "291-A"),
    ("XXVII", "292", "303"), ("XXVIII", "304", "305-A"), ("XXIX", "306", "308"),
    ("XXX", "309", "332-N"), ("XXXI", "333", "359-U"), ("XXXII", "360", "360"),
    ("XXXIII", "361", "361"), ("XXXIII-A", "361-A", "361-E"),
    ("XXXIV", "362", "382"), ("XXXIV-A", "382-A", "382-A"),
    ("XXXV", "383", "397-B"), ("XXXVI", "398", "399-G"), ("XXXVII", "400", "420-Q"),
    ("XXXVIII", "421", "421-B"), ("XXXIX", "422", "424"), ("XL", "425", "439-A"),
    ("XLI", "444", "454-C"), ("XLII", "455", "456-B"), ("XLIII", "457", "461-B"),
    ("XLIV", "462", "465"), ("XLV", "466", "470"), ("XLVI", "471", "471-D"),
    ("XLVII", "472", "476"), ("XLVIII", "477", "479-B"), ("XLIX", "480", "480"),
    ("L", "481", "489-C"), ("LI", "490", "505"), ("LII", "506", "513"),
    ("LIII", "514", "526"), ("LIV", "527", "533"), ("LV", "534", "546-C"),
    ("LVI", "547", "567-A"), ("LVII", "568", "569"), ("LVIII", "570", "591"),
    ("LIX", "592", "614"), ("LX", "615", "623-C"), ("LXI", "624", "624"),
    ("LXII", "625", "651-F"), ("LXIII", "652", "671"), ("LXIV", "672", "679"),
]

# "RSA 91-A:4" / "RSA 638:26-a" / "RSA 91-A" / "RSA 91-A:2, III" -- the roman
# numeral after a comma is a paragraph within the section, not part of the
# address, so it is left out of the link and left in the sentence.
# FIVE WAYS THIS SENT A READER TO THE WRONG STATUTE, all of them from a class
# that was one character too narrow. These are LINKS, so a mis-parse does not
# lose a citation -- it publishes a different law under the right words.
#
#   RSA 2025, 141:389  ->  chapter 202   a SESSION LAW, not an RSA chapter at
#                                        all; \d{1,3} took "202" out of "2025"
#                                        and linked RSA 202, Public Libraries
#   RSA 126-AA:2       ->  126-A         -[A-Z] is one letter; 126-AA and
#                                        126-A are different chapters
#   RSA 21-I:19-ff     ->  21-I:19-f     likewise for the section suffix
#   RSA 383-A:6-602    ->  383-A:6       a hyphenated section number, truncated
#   RSA 293-A:10.01    ->  293-A:10      a dotted section number, truncated
#
# The trailing lookaheads are what make the first case give NOTHING rather than
# something wrong: "2025" cannot end after three digits, so the whole match
# fails and the session-law citation is left as plain words. Refusing to link
# is the right answer where the target is not an RSA chapter.
RSA_CITE = re.compile(
    r"\bRSA\s+(\d{1,3}(?:-[A-Z]{1,2})?)(?![\d-])"
    r"(?::(\d{1,4}(?:-[a-z0-9]{1,3})?(?:\.\d{1,2})?)(?!\d))?",
    re.I)


def _chapter_key(ch):
    m = re.match(r"(\d+)(?:-([A-Za-z]+))?$", ch.strip())
    return (int(m.group(1)), (m.group(2) or "").upper()) if m else None


_STATUTES = []


def _statutes():
    """The statute table (rsa.py), read once a run, or None where
    db/NH_RSA.psv is not on this disk."""
    if not _STATUTES:
        try:
            import rsa
            _STATUTES.append(rsa.load())
        except Exception:                                        # noqa: BLE001
            _STATUTES.append(None)
    return _STATUTES[0]


def rsa_url(chapter, section=None):
    """Where a citation links: the site's own statute page where the table
    holds it, else the General Court's, else "" (no link).

    THE SITE'S OWN PAGE FIRST (RSA_PAGE.md §7; the person, 11 October 2026:
    "the RSA pages should be linked throughout the site to the Granite
    Record pages as an interlinked system"). Where the statute table is on
    disk, a section it holds links to its anchor, /rsa/91-a#s4; a section it
    does not hold -- one a bill would create, or one repealed and gone --
    links to its chapter's page where the chapter is held; and an address
    the table does not hold at all is left as words, because a link built
    from the title table to gc.nh.gov for it may well 404 (RSA_PAGE.md §2:
    20,358 of the bill texts' section citations name an address the table
    lacks). Without the table, the General Court's page, as before."""
    table = _statutes()
    if table is not None:
        ch = (chapter or "").upper()
        kind, target = table.resolve(ch, section) if section else table.resolve(ch)
        # The chapter's address as build_rsa writes it, RSA 404's with its
        # slash (build_rsa.chapter_path, the sitemap audit, 16 October 2026).
        import build_rsa
        if kind in ("section", "range"):
            c, _, sec = target.partition(":")
            return build_rsa.chapter_path(c, sec)
        if kind == "chapter" or (section and table.resolve(ch)[0] == "chapter"):
            return build_rsa.chapter_path(ch)
        return ""
    key = _chapter_key(chapter)
    if not key:
        return ""
    for title, lo, hi in RSA_TITLES:
        klo, khi = _chapter_key(lo), _chapter_key(hi)
        if klo and khi and klo <= key <= khi:
            ch = chapter.upper()
            if section:
                return (f"https://gc.nh.gov/rsa/html/{title}/{ch}/"
                        f"{ch}-{section}.htm")
            return f"https://gc.nh.gov/rsa/html/NHTOC/NHTOC-{title}-{ch}.htm"
    return ""


def rsa_links(*texts):
    """{citation as written: url} for every statute cited in these strings.

    A map rather than rewritten text: the renderers escape what they print, and
    handing them HTML to escape would show the tags. They substitute after
    escaping, which is safe because a citation contains nothing to escape.
    """
    out = {}
    for txt in texts:
        for m in RSA_CITE.finditer(txt or ""):
            url = rsa_url(m.group(1), m.group(2))
            if url:
                out[m.group(0)] = url
    return out
