#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.3
"""
preflight's checks of the General Court's database and day files, and the fetchers' parsers.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (_Seal, _parsed, _run, _source, check, imp)
from pf_fixture import (_fixture_site_shared)
from pf_shared import (AMENDMENT_PAGE, _DBDAY_VIEWS, _DBGUARD_REAL, _LEFT_OUT,
                       _bill_index_write, _cors_rules, _cors_said, _dbday_bytes,
                       _dbday_expected, _dbday_install, _dbday_views, _docket_rows)


@check("frontend", "an archived bill's analysis is the analysis, not the page's letterhead")
def _front_matter_off():
    """21,914 bill pages published their printing header as the analysis.

    The archive opens a bill with its number, the session, the LSR, the title,
    the sponsor line and the committee, and only then ANALYSIS.
    archive_text.front_matter_off cuts that off -- but it looked for a rule of
    dashes above the label, and the archive draws no such rule before about
    2015. So it found nothing, returned the page unchanged, and
    build_site_v2.bill_text_block cut the analysis at the enacting clause
    instead: everything above it, letterhead included, was published as the
    drafters' summary. 1994 HB 1234's analysis began "HB 1234 1994 SESSION
    3833B 94-2328 01/02 HOUSE BILL AN ACT allowing...".

    Measured when it was fixed: 0 of the 8,853 pages of 1989-1999 had their
    header removed, and 21,914 of the 29,346 on disk overall.

    The sample below is the shape of a real 1994 page -- no rule above the
    label, a spaced rule below it -- so this needs no data on disk and runs
    under --code. The second sample is a resolution, which carries no analysis
    and must be left exactly as it was read rather than cut at a guess.
    """
    at = imp("archive_text")
    if at is None:
        return "skip", "archive_text will not import"
    page = (
        "HB 1234\n\n1994 SESSION 3833B\n\n94-2328\n\n01/02\n\nHOUSE BILL\n\n"
        "AN ACT allowing condominium unit owners to post signs.\n\n"
        "SPONSORS: Rep. Lundborn, Straf 18\n\n"
        "COMMITTEE: Commerce, Small Business and Consumer Affairs\n\n"
        "ANALYSIS\n\nThis bill allows condominium unit owners to post signs.\n\n"
        "- - - - - - - - - - - - - - - - - - - -\n\n"
        "EXPLANATION: Matter added to current law appears in bold italics.\n")
    got = at.front_matter_off(page)
    assert got.startswith("ANALYSIS"), (
        "front_matter_off left the printing header on a 1990s-shaped page, so "
        "every archived bill before about 2015 would publish its letterhead "
        "as its analysis. It begins: " + repr(got[:60]))
    for gone in ("SPONSORS:", "COMMITTEE:", "1994 SESSION", "94-2328"):
        assert gone not in got, (
            f"{gone!r} survived into the analysis of a 1990s-shaped page")

    # A page with no analysis at all is not cut. The label is the boundary and
    # there is no label here, so guessing one would take the resolution's
    # first words off instead.
    res = ("HR 5\n\n1993 SESSION\n\nHOUSE RESOLUTION\n\n"
           "RESOLVED, that the House adopt the rules of the 1992 session.\n")
    assert at.front_matter_off(res) == res, (
        "a page carrying no ANALYSIS label was cut anyway")

    # And the modern shape, which has the rule, still works the old way.
    modern = ("HB 99 - AS INTRODUCED\n\n2021 SESSION\n\n"
              "SPONSORS: Rep. Smith\n\n" + "-" * 40 + "\n\n"
              "ANALYSIS\n\nThis bill does a thing.\n")
    assert at.front_matter_off(modern).startswith("ANALYSIS"), (
        "the rule-above-the-label path stopped working")
    return "ok", "the header comes off with or without a rule above the label"


@check("frontend", "an archived page's text is what a browser shows: no Word "
                   "properties, and no space where a tag met punctuation")
def _archive_text_as_shown():
    """Two ways archive_text.text_of printed what no reader of the page sees.

    2005, 2007, 2009, 2011 and 2013 HR 1 and 2009 HR 2 were saved from Word,
    and their Bill Text opened "Fowler_E Fowler_E 2 3 2004-12-28T20:07:00Z ...
    MicrosoftInternetExplorer4": the document properties Word keeps in a
    comment in the page's head, which stripping tags turned into text. A
    resolution has no analysis, so front_matter_off never cut them.

    And every inline tag became a space, so "made<B><I>, except as provided
    in article 68-a</I></B>." read "made , except ... 68-a ." -- 166,075 times
    across archive_text.json. In the 28,369 bills whose text matches a version
    in PastLegislationText word for word it was 143,195 against the view's own
    14,029, and 13,710 once fixed, with not one word of those bills changed.
    Only a tag that is the sole thing between a character and punctuation
    goes; a tag between two words stays a space, and a space the page itself
    wrote stays.

    The page below is the shape of the real 2005 HR 1 and 1989 CACR 14, so
    this needs no data and runs under --code.
    """
    at = imp("archive_text")
    if at is None:
        return "skip", "archive_text will not import"
    page = (
        '<html xmlns:o="urn:schemas-microsoft-com:office:office">\r\n<head>\r\n'
        "<title>House Resolutions 1-5</title>\r\n"
        "<!--[if gte mso 9]><xml>\r\n <o:DocumentProperties>\r\n"
        "  <o:Author>Fowler_E</o:Author>\r\n"
        "  <o:Created>2004-12-28T20:07:00Z</o:Created>\r\n"
        " </o:DocumentProperties>\r\n</xml><![endif]--><!--[if gte mso 9]><xml>\r\n"
        " <w:WordDocument>\r\n  <w:BrowserLevel>MicrosoftInternetExplorer4"
        "</w:BrowserLevel>\r\n </w:WordDocument>\r\n</xml><![endif]-->\r\n"
        "<style>\r\n<!--\r\n p.MsoNormal {margin:0in;}\r\n-->\r\n</style>\r\n"
        "</head>\r\n<body>\r\n"
        "<p><![if !supportLists]><span>I.<span>&nbsp; </span></span>"
        "<![endif]>All intermediate vacancies may be filled up in the same "
        "manner as biennial elections are made<B><I>, except as provided in "
        "article 68-a</I></B>.</p>\r\n"
        "<p>The <b>house</b><i>clerk</i> shall keep a record (see RSA "
        "<span>14:1</span>) of every vote , and <b>shall</b> publish it.</p>\r\n"
        "</body></html>")
    d = Path(tempfile.mkdtemp())
    try:
        f = d / "HR0001.html"
        f.write_bytes(page.encode("cp1252"))
        got = at.text_of(f, keep_front=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    for gone in ("Fowler_E", "2004-12-28T20:07:00Z", "MicrosoftInternetExplorer4",
                 "MsoNormal"):
        assert gone not in got, (
            f"{gone!r} is in the text of a page Word saved: the document "
            "properties in its conditional comment reached the Bill Text")
    assert "elections are made, except as provided in article 68-a." in got, (
        "a tag between a word and its punctuation still became a space: "
        + repr(got[got.find("elections"):][:80]))
    assert "(see RSA 14:1) of every vote , and" in got, (
        "the text around a tag before ')' or a space the page itself wrote "
        "before ',' came out wrong: " + repr(got[got.find("(see"):][:60]))
    assert "house clerk" in got and "shall publish" in got, (
        "a tag that was the only thing between two words was removed, which "
        "joins them into a word the page does not have: " + repr(got))
    assert got.lstrip().startswith("House Resolutions 1-5") and "I." in got, (
        "the list number Word shows every browser through <![if "
        "!supportLists]> was lost, or the title was: " + repr(got[:80]))
    return "ok", ("Word's properties stay out, and a tag before punctuation "
                  "is no space while a tag between words still is")


@check("frontend", "an archived page's text stops at the bill: the Word binary a converted "
                   "page of 1989-1995 carries after it is not printed")
def _archive_text_no_application_tail():
    """The language sweep of 17 October 2026: 1995 HB 101's Bill Text ran on
    from "This act shall take effect January 1, 1996." into "EB",
    "?\\C:\\PROGRA~1\\MICROS~1\\Office\\wwintl32.dll" and the Legislative
    Services machines' search path -- the binary tail of the Word file the
    page was converted from, on 1,365 saved pages of 1989-1995. The page
    below is the end of the real HB 101 of 1995, so this needs no data.

    Fails if the tail, or the fragments of it above the first program file,
    come back, or if the cut takes a line of the bill."""
    at = imp("archive_text")
    if at is None:
        return "skip", "archive_text will not import"
    page = (
        '<P><FONT FACE="Courier New">I.  No person shall drive a motor vehicle while carrying '
        'a child less than [12] <B><I>18</I></B> years of age.</FONT></P>\r\n'
        '<P><FONT FACE="Courier New">2  Effective Date.  This act shall take effect January 1, '
        '1996.</FONT></P>\r\n</UL><P><FONT FACE="Courier New">EB</FONT></P>\r\n'
        '<P><FONT FACE="Courier New">?\\C:\\PROGRA~1\\MICROS~1\\Office\\wwintl32.dllE '
        '&amp;&amp;)E</FONT> </P>\r\n<P><FONT FACE="Courier New">?\\C:\\PROGRA~1\\MICROS~1'
        '\\Office\\MSO97.DLLll-ECAPITOL\\LSSOFTWARE\\LSNT\\CLIPPIT.ACTT;.;C:\\WINNT\\System32;'
        '</FONT></P>\r\n<P><FONT FACE="Courier New">C:\\PROGRA~1\\MICROS~1\\O</FONT></P>')
    got = at.flatten(page)
    assert got.endswith("This act shall take effect January 1, 1996."), (
        "the Word binary after the bill is printed as its text: " + repr(got[-160:]))
    assert "less than [12] 18 years" in got, repr(got)
    plain = "I. The act shall take effect upon its passage.\nEB\n5"
    assert at.application_tail_off(plain) == plain, (
        "a page with no program file named was cut: " + repr(at.application_tail_off(plain)))
    # ONLY THE BINARY (the review of 17 October 2026): a fiscal note's table
    # above the tail, as 1990 HB 1023's ends, and a sentence sharing its line
    # with the binary, as 1989 SB 175's does -- and "ntdll.dllB", which a \b
    # after "dll" missed.
    hb1023 = ("Balance to state $40,032,000 $37,530,000\n\nDifference = $2,502,000\n\n_%__\n\n"
              "$RNPWinword.exe68C:\\WINNT\\System32\\ntdll.dllB\ufffd7EB\n\n"
              "?\\C:\\PROGRA~1\\MICROS~1\\Office\\wwintl32.dll")
    got = at.application_tail_off(hb1023)
    assert got == "Balance to state $40,032,000 $37,530,000\n\nDifference = $2,502,000", repr(got)
    sb175 = ("FISCAL NOTE for an act making an appropriation.\n\nFISCAL IMPACT: This bill "
             "appropriates $50,000 for FY 1990 to the N.H. Council on the Arts, for "
             "\\\\capitol\\viewlibrary\\prior session bills\\1989\\senate\\SB")
    got = at.application_tail_off(sb175)
    assert got.endswith("to the N.H. Council on the Arts, for") and "viewlibrary" not in got, repr(got)
    nt = "2 Effective Date. This act shall take effect January 1, 1991.\n\nk66\n\nntdll.dllB\ufffdxEB"
    assert at.application_tail_off(nt).endswith("January 1, 1991."), repr(at.application_tail_off(nt))
    return "ok", ("1995 HB 101 ends at its effective date, a fiscal note's table and a sentence "
                  "beside the binary are kept, and a page with no tail is untouched")


@check("data", "on every saved page of 1989-1999 carrying a Word file's tail, the cut takes the "
       "binary and never a line of text: a run of four words, a sum of money, FISCAL")
def _archive_text_tail_on_disk():
    """The review of 17 October 2026: the first cut of the Word binary
    (archive_text.application_tail_off) deleted real fiscal-note text on 19
    pages -- tables, and sentences sharing a line with the binary -- and
    left it on 34 that wrote "ntdll.dllB". Over every saved page that names a
    program file: each line of text, or the text before the binary starts
    in its line, is still there, and no program file is left. Fails if the
    cut is undone either way."""
    at = imp("archive_text")
    FL = imp("fetch_legislation")
    root = Path("legislation")
    if at is None or FL is None:
        return "skip", "archive_text or fetch_legislation will not import"
    years = sorted(p for p in root.glob("19[89]?") if p.is_dir()) if root.is_dir() else []
    if not years:
        return "skip", "no legislation/ of 1989-1999 here"
    raw = re.compile(rb"PROGRA~|WINNT|\.dll|\.exe|MSO97|CLIPPIT|CAPITOL|viewlibrary", re.I)
    texty = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?(?=[\s,.;:)]|$)|FISCAL|"
                       r"[A-Za-z]+(?:[ ,;:]+[A-Za-z]+){3}")
    cut, pages, lost, left = at.application_tail_off, 0, [], []
    try:
        for y in years:
            for f in sorted(y.glob("*.html")):
                b = f.read_bytes()
                if not raw.search(b):
                    continue
                html = FL.decode(b)
                at.application_tail_off = lambda t: t
                whole = at.flatten(html)
                at.application_tail_off = cut
                out = at.flatten(html)
                if not at.APPLICATION.search(whole):
                    continue
                pages += 1
                got = set(out.split("\n"))
                for line in whole.split("\n"):
                    m = at.BINARY_STARTS.search(line)
                    keep = line[:m.start()].rstrip() if m else line
                    if keep and texty.search(keep) and keep not in got:
                        lost.append(f"{f}: {keep[:60]!r}")
                if at.APPLICATION.search(out):
                    left.append(str(f))
    finally:
        at.application_tail_off = cut
    assert not lost, f"{len(lost)} lines of text cut with the binary: " + "; ".join(lost[:5])
    assert not left, f"{len(left)} pages keep a program file: " + ", ".join(left[:5])
    return "ok", f"{pages:,} pages cut to their text, no line of text lost and no program file left"


def _printing(label, marks, lsr, number, title, analysis, sections, law=None,
              approved=None):
    """(html, text) of one printing of a 2018 bill, in the shapes the archive's
    page and the database's two columns have: the HTML opens with the version
    line and the text column does not. `law` is a chapter's number, which the
    chaptered text puts before each section's."""
    n = f"{law}:" if law else ""
    lines = (label + marks + ["2018 SESSION", lsr, number, f"AN ACT {title}",
                              "-" * 65, "ANALYSIS", analysis, "- " * 40,
                              "Explanation: Matter added to current law appears in "
                              "bold italics."]
             + marks + [lsr, "STATE OF NEW HAMPSHIRE",
                        "In the Year of Our Lord Two Thousand Eighteen", f"AN ACT {title}",
                        "Be it Enacted by the Senate and House of Representatives in "
                        "General Court convened:"]
             + [f"{n}{s}" if re.match(r"\d+ ", s) else s for s in sections]
             + ([approved] if approved else []))
    html = "<html><body>" + "".join(f"<p><span>{x}</span></p>" for x in lines) + \
           "</body></html>"
    return html, "\r\n".join(lines[len(label):])


def _sb421(label, marks, after, new, lsr="18-2993", **kw):
    """2018 SB 421, whose new section the enrolled bill amendment renumbered."""
    return _printing(
        label, marks, lsr, "SENATE BILL 421",
        "relative to insurance coverage for prescription contraceptives.",
        "This bill clarifies insurance coverage for prescription contraceptive drugs "
        "and prescription contraceptive devices and for contraceptive services.",
        ["1 New Section; Coverage for Prescription Contraceptive Devices and for "
         "Contraceptive Services. Amend RSA 415 by inserting after section "
         f"{after} the following new section:",
         f"{new} Coverage for Prescription Contraceptive Drugs and Prescription "
         "Contraceptive Devices and for Contraceptive Services. Each insurer that "
         "issues or renews any individual policy of accident or health insurance "
         "shall provide coverage for outpatient contraceptive services under the "
         "same terms and conditions as for other outpatient services.",
         "2 Effective Date. This act shall take effect January 1, 2019."], **kw)


def _hb1474(label, **kw):
    """2018 HB 1474, whose page is its version adopted by both bodies."""
    return _printing(
        label, [], "18-2424", "HOUSE BILL 1474",
        "designating the New Hampshire Red as the official state poultry.",
        "This bill designates the New Hampshire Red as the official state poultry.",
        ["1 New Section; State Poultry. Amend RSA 3 by inserting after section 28 "
         "the following new section:",
         "3:29 State Poultry. The New Hampshire Red is hereby designated as the "
         "official state poultry of New Hampshire.",
         "2 Effective Date. This act shall take effect upon its passage."], **kw)


@check("frontend", "an archived bill's final version is the General Court's own, "
                   "not an earlier printing that says it is", needs=("archive_text",))
def _final_version_from_db(at):
    """Twenty-three 2018 pages printed VERSION ADOPTED BY BOTH BODIES over an
    earlier printing, and the Bill Text tab showed each as the final version.

    The pages are the House's or the Senate's amended text, or a committee of
    conference's, without the enrolled bill amendment of 23 May 2018 that the
    version adopted by both bodies carries -- and the enacted section numbers
    come from that amendment. 2018 SB 421's page inserts an RSA 415:6-v, word
    for word the House's printing under a new heading; chapter 361 enacted
    415:6-w. PastLegislationText, the General Court's own copy of every
    printing, holds the version adopted by both bodies (VersionID 13 or 14)
    and the chaptered law (48, 52, 53), and archive_text.final_versions shows
    the former wherever it is not the page and is at least as near the law.

    The fixture is SB 421 cut down to its first section -- the House's
    printing, the page that relabels it, the version adopted by both bodies and
    chapter 361 -- so this runs under --code. What else it holds to:
      - 2018 HB 1474, whose page is its final version word for word, and the
        same SB 421 page a session later, keep their pages: 2018 alone was
        measured, so FINAL_FROM_DB is 2018 alone;
      - if the database's copy were the earlier printing, the page would stay;
      - with no view on disk -- GitHub's nightly, whose kit does not carry it
        -- every page stands as it was and the tally says why;
      - a veto note the page carries goes with the text, before a fiscal note.
    """
    import io
    import contextlib
    adopted = ["SB 421 - VERSION ADOPTED BY BOTH BODIES"]
    eba = ["2May2018... 1753h", "05/23/2018 2097EBA"]
    house = _sb421(["SB 421 - AS AMENDED BY THE HOUSE"], eba[:1], "6-u", "415:6-v")
    page = _sb421(adopted, eba[:1], "6-u", "415:6-v")
    final = _sb421(adopted, eba, "6-u", "415:6-w")
    law = _sb421(["CHAPTER 361", "SB 421 - FINAL VERSION"], eba, "6-v", "415:6-w",
                 law=361, approved="Approved: July 02, 2018")
    poultry = _hb1474(["HB 1474 - VERSION ADOPTED BY BOTH BODIES"])
    poultry_law = _hb1474(["CHAPTER 268", "HB 1474 - FINAL VERSION"], law=268,
                          approved="Approved: June 18, 2018")
    # The same three printings a session later, each printing that session's LSR,
    # so that nothing but FINAL_FROM_DB keeps them from the rule.
    page19, final19, law19 = (_sb421(adopted, eba[:1], "6-u", "415:6-v", lsr="19-2993"),
                              _sb421(adopted, eba, "6-u", "415:6-w", lsr="19-2993"),
                              _sb421(["CHAPTER 9", "SB 421 - FINAL VERSION"], eba, "6-v",
                                     "415:6-w", lsr="19-2993", law=9,
                                     approved="Approved: July 02, 2019"))

    def row(id_, year, lsr, bill, vid, doc):
        return json.dumps({"id": id_, "BillNbr": bill, "html": doc[0], "sessionyear": year,
                           "VersionID": vid, "text": doc[1],
                           "legislationID": int(f"{lsr}{year}"), "lsr": lsr,
                           "FullDescription": None})

    title = "relative to insurance coverage for prescription contraceptives."
    bills = {"2017-2018": {
                 "SB421": {"bill": "SB421", "lsr": "2018-2993", "lsr_year": "2018",
                           "lsr_num": "2993", "title": title},
                 "HB1474": {"bill": "HB1474", "lsr": "2018-2424", "lsr_year": "2018",
                            "lsr_num": "2424", "title": "designating the New Hampshire "
                            "Red as the official state poultry."}},
             "2019-2020": {
                 "SB421": {"bill": "SB421", "lsr": "2019-2993", "lsr_year": "2019",
                           "lsr_num": "2993", "title": title}}}
    root = Path(tempfile.mkdtemp())
    here = os.getcwd()
    view = root / "db" / "past" / "PastLegislationText.jsonl"

    def lay(sb421_page, rows):
        for year, name, doc in (("2018", "SB0421", sb421_page), ("2018", "HB1474", poultry[0]),
                                ("2019", "SB0421", page19[0])):
            (root / "legislation" / year).mkdir(parents=True, exist_ok=True)
            (root / "legislation" / year / f"{name}.html").write_text(doc, encoding="utf-8")
        view.parent.mkdir(parents=True, exist_ok=True)
        view.write_text("\n".join(rows) + "\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            return at.build(bills)

    try:
        os.chdir(root)
        got, tally, _ = lay(page[0], [
            row(77295, 2018, 2993, "SB421", 6, house),
            row(77294, 2018, 2993, "SB421", 13, final),
            row(77293, 2018, 2993, "SB421", 48, law),
            row(78100, 2018, 2424, "HB1474", 14, poultry),
            row(78101, 2018, 2424, "HB1474", 48, poultry_law),
            row(90001, 2019, 2993, "SB421", 13, final19),
            row(90002, 2019, 2993, "SB421", 48, law19)])
        sb = got["2017-2018"]["SB421"]
        assert "415:6-w Coverage" in sb["text"] and "415:6-v Coverage" not in sb["text"], (
            "2018 SB 421 still shows the House's printing as the version adopted by "
            "both bodies -- RSA 415:6-v, where chapter 361 enacted 415:6-w: "
            + repr(sb["text"][sb["text"].find("415:6"):][:60]))
        assert sb.get("version") == "Version adopted by both bodies", (
            f"the page's own label for the version was not kept: {sb.get('version')!r}")
        assert sb["text"].startswith("ANALYSIS") and "2097EBA" in sb["text"] \
            and sb.get("source") == "PastLegislationText 77294", (
            "the final version's text did not arrive whole from its own row: "
            f"{sb.get('source')!r}, {sb['text'][:40]!r}")
        assert got["2017-2018"]["HB1474"].get("source") == "archive page", (
            "a page that is its final version word for word was replaced")
        later = got["2019-2020"]["SB421"]
        assert "415:6-v Coverage" in later["text"] and later.get("source") == "archive page", (
            "a session nobody measured took the database's text: FINAL_FROM_DB "
            "names the sessions that were checked, and only those")

        # The database's copy the EARLIER printing, the page the later: the
        # page is the nearer the law, so it stays.
        got, _, _ = lay(final[0], [
            row(77294, 2018, 2993, "SB421", 13, house),
            row(77293, 2018, 2993, "SB421", 48, law)])
        assert got["2017-2018"]["SB421"].get("source") == "archive page", (
            "a page nearer the chaptered law than the database's copy was replaced")

        # No view on disk, as on GitHub's machine: every page as it was.
        view.unlink()
        (root / "legislation" / "2018" / "SB0421.html").write_text(page[0], encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            got, tally, _ = at.build(bills)
        sb = got["2017-2018"]["SB421"]
        assert "415:6-v Coverage" in sb["text"] and sb.get("source") == "archive page", (
            "without the view a page's text changed")
        assert any("not checked" in k for k in tally), (
            "without the view the build said nothing about the pages it could not "
            f"check: {sorted(tally)}")
    finally:
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)

    noted = at.with_veto_note(
        "ANALYSIS\nThis bill does a thing.\n2 Effective Date. Upon passage.\nLBAO\n"
        "18-2993\nFISCAL IMPACT: none",
        "ANALYSIS\nThis bill does a thing.\n2 Effective Date. Upon passage.\n\n"
        "VETOED: June 18, 2018\n\nVeto Overridden: September 13, 2018\n\nLBAO")
    assert "Upon passage.\n\nVETOED: June 18, 2018\n\nVeto Overridden: September 13, " \
           "2018\n\nLBAO\n18-2993" in noted, (
        "a veto note on the page was lost with the page's text, or put after the "
        f"fiscal note: {noted!r}")
    return "ok", ("2018 SB 421 shows chapter 361's 415:6-w with its own label; a page "
                  "that is its final version, another session, a nearer page and a "
                  "missing view all keep the page, and a veto note stays")


@check("status", "a bill takes the status page of its own term, and a term with no slice "
                 "takes none", needs=("build_data",))
def _status_own_term(build_data):
    """build_data laid bill_status.json's newest term onto the current
    session's bills by number. The first night of 2027-2028 that newest term
    is still 2025-2026, and every 2027 bill numbered like a 2025 one would
    have taken its title, committee, chapter, text address and sponsors --
    HB 1, the budget every term since 1993, with 2025's sponsors.
    status_for_session takes each bill's record from the term its LSR year
    names, and nothing for a term the file has no slice for."""
    SFS = build_data.status_for_session
    raw = {"2023-2024": {"HB1": {"title": "the 2023 budget"}},
           "2025-2026": {"HB1": {"title": "the 2025 budget"}, "HB2": {"title": "2025's HB2"}}}
    new = {"HB1": {"lsr_year": "2027"}, "HB2": {"lsr_year": "2027"}}
    assert SFS(raw, new) == ({}, ["2027-2028"]), SFS(raw, new)
    raw["2027-2028"] = {"HB1": {"title": "the 2027 budget"}}
    assert SFS(raw, new) == ({"HB1": {"title": "the 2027 budget"}}, []), SFS(raw, new)
    got, missing = SFS(raw, {"HB1": {"lsr_year": "2025"}, "HB2": {"lsr_year": "2026"}})
    assert {b: v["title"] for b, v in got.items()} == {
        "HB1": "the 2025 budget", "HB2": "2025's HB2"} and not missing, (got, missing)
    flat = {"HB1": {"title": "flat"}}
    assert SFS(flat, new) == (flat, []), "a flat file is the current session's"
    assert not hasattr(build_data.P, "for_term"), (
        "proceedings.for_term is back: its newest-term default is the fault this check is about")
    src = _source(_paths.locate("build_data.py"))
    assert "status_for_session(raw, bills)" in src, \
        "build_data no longer reads bill_status.json through status_for_session"
    return "ok", "2027 bills take nothing from 2025-2026, and their own slice once it exists"


@check("status", "a bill keeps the day its request was made a bill: the database's DateLSRBill as "
                 "a day, through bill_status.json onto the bill's own term's record and no other's",
       needs=("fetch_status_db", "build_data"))
def _status_made_bill(fetch_status_db, build_data):
    """The owner, 15 November 2026: a bill request's Filed stop is dated by
    the day its bill was made one, Legislation.DateLSRBill, which the day
    files leave out (dayfiles_from_db.LSR_MAP) as the General Court's export
    does. Held: fetch_status_db selects it as a day, YYYY-MM-DD with a blank
    for none, in the place COLS gives made_bill; record() carries it into
    bill_status.json's shape, a blank as a blank; it is one of the FILLS, so
    a blank is filled and a day on file stays. build_data's fill_from_status,
    which main() gives status_for_session's records, puts it on the bill's
    record where the record has none, from the bill's own term's status
    record: a 2027 bill numbered like a 2025 one takes nothing of 2025's, a
    blank gives nothing, and a day the record has stays."""
    FS, BD = fetch_status_db, build_data
    # The SELECT's columns, in order: split at the commas outside brackets.
    sel = FS.SQL.split("SELECT", 1)[1].split("FROM Legislation", 1)[0]
    cols, depth, cur = [], 0, ""
    for ch in sel:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and not depth:
            cols.append(re.sub(r"\s+", "", cur))
            cur = ""
        else:
            cur += ch
    cols.append(re.sub(r"\s+", "", cur))
    assert len(cols) == len(FS.COLS) and "made_bill" in FS.COLS, (
        f"fetch_status_db selects {len(cols)} columns and COLS names {len(FS.COLS)}: {FS.COLS}")
    said = cols[FS.COLS.index("made_bill")]
    assert said == "ISNULL(FORMAT(DateLSRBill,'yyyy-MM-dd'),'')", (
        f"made_bill is selected as {said!r}, not DateLSRBill as a yyyy-MM-dd day, blank for none")
    assert "made_bill" in FS.FILLS, "made_bill is not one of the fields fetch_status_db fills"
    row = dict(dict.fromkeys(FS.COLS, ""), bill="HB45", year="2027", body="H",
               made_bill="2026-12-01")
    assert FS.record(row, {}, {}).get("made_bill") == "2026-12-01" \
        and FS.record({**row, "made_bill": ""}, {}, {}).get("made_bill") == "", (
        "fetch_status_db's record() does not carry the column's day as made_bill, or not a blank as one")
    raw = {"2025-2026": {"HB1": {"title": "the 2025 budget", "made_bill": "2024-12-19"},
                         "HB2": {"made_bill": "2025-11-20"}},
           "2027-2028": {"HB2": {"made_bill": "2026-12-01"}, "HB3": {"made_bill": ""},
                         "HB4": {"made_bill": "2026-12-05"}}}
    bills = {"HB1": {"lsr_year": "2027", "title": "the 2027 budget"}, "HB2": {"lsr_year": "2027"},
             "HB3": {"lsr_year": "2028"}, "HB4": {"lsr_year": "2027", "made_bill": "2026-11-30"}}
    st, missing = BD.status_for_session(raw, bills)
    took = BD.fill_from_status(bills, st)
    got = {b: r.get("made_bill") for b, r in bills.items()}
    assert got == {"HB1": None, "HB2": "2026-12-01", "HB3": None, "HB4": "2026-11-30"} \
        and took["made_bill"] == 1 and not missing, (
        f"the bills' made_bill after the fill: {got} ({dict(took)}); wanted 2027's HB 2 to take its "
        "own term's day and nothing of 2025's, a blank to give none, and a day on file to stay")
    assert not BD.fill_from_status({}, {"HB9": {"made_bill": "2026-12-01"}}), (
        "a status record of a bill the session does not hold filled something")
    src = _source(_paths.locate("build_data.py"))
    i = src.find("st, no_slice = status_for_session(raw, bills)")
    assert 0 <= i < src.find("took = fill_from_status(bills, st)"), (
        "build_data's main no longer fills the bills through fill_from_status from status_for_session's records")
    return "ok", ("DateLSRBill selected as a yyyy-MM-dd day and carried as made_bill, one of the FILLS; "
                  "a bill takes its own term's day where it has none, never another term's, never a blank")


@check("build", "the database's printings fill only the bills bill_text.json has no web record of, "
       "with the record the web page gives and the bill's current printing, and never touch a "
       "web record", needs=("bill_text_from_db", "bill_page", "fetch_bill_text"))
def _bill_text_from_db(BT, BP, FB):
    """bill_text_from_db.py, on a fixture dump of five bills. Measured on the
    dump of 8 September: the printing it chooses is the web page's version for
    all 2,234 bills of 2025-2026, and the record bill_page.parse_text reads off
    it is the web's for 2,192 and the same words for the other 42 (--check says
    it again on any dump). This holds the rules that measurement rests on: the
    order of printings, the records it may write, and that it asks nobody; and
    (16 October 2026) that a printing whose own heading names another bill --
    an old term's text filed under a new term's id -- is skipped and counted:
    with the dump's ids moved one bill along, 2,218 of 2,234 were."""
    assert FB.parse_text is BP.parse_text and FB.text_of is BP.text_of, \
        "fetch_bill_text reads the web's pages with another parser than bill_page's"
    src = _source(_paths.locate("bill_text_from_db.py"))
    assert not re.search(r"^\s*(?:import|from)\s+(?:urllib|socket|http|subprocess|probe_db|"
                         r"refusal|child|fetch_\w+)\b", src, re.M), \
        "bill_text_from_db.py imports something that could ask the network"
    src = _source(_paths.locate("bill_page.py"))
    assert not re.search(r"^\s*(?:import|from)\s+(?:urllib|socket|http|subprocess|refusal)\b",
                         src, re.M), "bill_page.py imports something that could ask the network"

    def page(bill, version, body="This bill does a thing."):
        return (f"<p>{bill[:2]} {bill[2:]} - {version}</p><p>2025 SESSION</p>"
                f"<p>AN ACT relative to {bill}.</p><p>SPONSORS: Rep. Smith, Hills. 1</p>"
                "<p>COMMITTEE: Finance</p><p>------------------------------</p>"
                f"<p>ANALYSIS</p><p>{body}</p><p>{'Be it Enacted. ' * 40}</p>")
    lt = ["LegislationID", "HTMLText", "DocumentVersion", "DateTimeStamp"]
    rows = [  # (id, html, version, stamp)
        ("1", page("HB1", "AS AMENDED BY THE HOUSE"), "As Amended by the House", "03/01/2025 10:00:00"),
        ("2", page("HB2", "AS INTRODUCED"), "Introduced", "01/05/2025 10:00:00"),
        ("2", page("HB2", "AS AMENDED BY THE HOUSE", "Amended."), "As Amended by the House",
         "03/01/2025 10:00:00"),
        ("2", "<p>Amendment 2025-0001h</p>", "OLS Release", "04/01/2025 10:00:00"),
        ("3", page("HB3", "FINAL VERSION"), "CHAPTERED FINAL VERSION", "07/23/2025 09:13:13"),
        ("3", page("HB3", "VERSION ADOPTED BY BOTH BODIES"), "Version adopted by both bodies",
         "07/23/2025 14:19:34"),
        ("4", page("HB4", "AS INTRODUCED"), "Introduced", "01/05/2025 10:00:00"),
        # An amendment the OLS released after the bill's only printing: read as
        # a printing it would be the latest, and no bill at all.
        ("6", page("HB6", "AS INTRODUCED"), "Introduced", "01/05/2025 10:00:00"),
        ("6", "<p>Amendment 2025-0002h</p>", "OLS Release", "02/01/2025 10:00:00"),
        # A PRINTING NAMES ITS OWN BILL (16 October 2026): filed under HB 7 by
        # an id that starts again every term, its heading -- 2026 HB 1442's,
        # as printed -- names another bill, and it is skipped; SB 290's real
        # heading names no number at all, and says nothing either way.
        ("7", page("HB1442-FN", "AS INTRODUCED"), "Introduced", "01/05/2025 10:00:00"),
        ("8", page("SB", "AS INTRODUCED"), "Introduced", "01/05/2025 10:00:00"),
    ]
    web = {"bill": "HB1", "year": "2025", "version": "AS INTRODUCED", "text": "ANALYSIS\nweb's"}
    tmp = Path(tempfile.mkdtemp(prefix="gr-btdb-"))
    try:
        (tmp / "db").mkdir()
        (tmp / "data").mkdir()

        def dump(text_rows):
            (tmp / "db" / "_columns.json").write_text(json.dumps({
                "Legislation": ["sessionyear", "CondensedBillNo", "legislationID"],
                "LegislationText": lt}), encoding="utf-8")
            (tmp / "db" / "Legislation.psv").write_text(
                "".join(f"2025|HB {i}|{i}\r\n" for i in "123467") + "2025|SB 290|8\r\n",
                encoding="utf-8")
            (tmp / "db" / "LegislationText.psv").write_text(
                "".join("|".join(r) + "\r\n" for r in text_rows), encoding="utf-8")
        dump(rows)
        (tmp / "data" / "bills.json").write_text(json.dumps(
            {"2025-2026": {b: {} for b in ("HB1", "HB2", "HB3", "HB5", "HB6", "HB7", "SB290")}}),
            encoding="utf-8")
        ours = {"bill": "HB5", "source": BT.SOURCE, "text": "a bill the view no longer prints"}
        ours7 = {"bill": "HB7", "source": BT.SOURCE, "text": "HB 7's own earlier printing"}
        out = tmp / "bill_text.json"
        out.write_text(json.dumps({"2025-2026": {"HB1": web, "HB5": ours, "HB7": ours7}}),
                       encoding="utf-8")
        added, refreshed, kept, said = BT.fill(tmp)
        got = json.loads(out.read_text(encoding="utf-8"))["2025-2026"]
        assert got.get("HB7") == ours7, \
            ("a printing whose own heading names HB 1442 was filed under HB 7", got.get("HB7"))
        assert "1 printings whose own heading names another bill, skipped (HB7's names HB1442)" \
            in said, said
        assert got.get("SB290", {}).get("version") == "AS INTRODUCED", \
            ("a printing whose heading names no number was skipped", got.get("SB290"))
        assert (BT.heading_bill("<p>CACR 19 - AS INTRODUCED</p><p>2025 SESSION</p>"),
                BT.heading_bill(page("SB", "AS AMENDED BY THE SENATE")),
                BT.names_another("HB0007", {"HTMLText": page("HB7", "AS INTRODUCED")}),
                BT.names_another("SB7", {"HTMLText": page("HB7", "AS INTRODUCED")})) == \
            ("CACR19", "", "", "HB7"), "a heading's bill is not read by its kind and its number"
        assert got["HB1"] == web and kept == 1, \
            ("a web record was replaced by the database's newer printing", got["HB1"])
        assert got["HB2"]["version"] == "AS AMENDED BY THE HOUSE" and \
            got["HB2"]["source"] == BT.SOURCE and got["HB2"]["printed"] == "2025-03-01T10:00:00" \
            and "Amended." in got["HB2"]["text"], \
            ("the latest amended printing was not taken, or an OLS release was", got["HB2"])
        assert got["HB3"]["version"] == "FINAL VERSION", \
            ("the later-stamped printing adopted by both bodies beat the chaptered text",
             got["HB3"].get("version"))
        assert got.get("HB6", {}).get("version") == "AS INTRODUCED", \
            ("an OLS release was read as the bill's latest printing", got.get("HB6"))
        assert "HB4" not in got, "a printing of a bill data/bills.json does not have was added"
        assert "HB5" not in got, "a record of the database's whose bill the view dropped was kept"
        assert got["HB2"] == {**BP.parse_text(rows[2][1], "HB2", "2025"),
                              "source": BT.SOURCE, "printed": "2025-03-01T10:00:00"}, \
            "the record is not bill_page.parse_text's of the printing"
        assert (added, refreshed) == (4, 0), (added, refreshed, said)
        before = out.read_bytes()
        assert BT.fill(tmp)[:2] == (0, 0) and out.read_bytes() == before, \
            "a second run over the same dump wrote the file again"
        # A newer printing replaces the database's own record of the bill.
        dump(rows + [("2", page("HB2", "AS AMENDED BY THE SENATE", "Later."),
                      "As Amended by the Senate", "05/01/2025 10:00:00")])
        assert BT.fill(tmp)[:2] == (0, 1), "a newer printing did not refresh the database's record"
        got = json.loads(out.read_text(encoding="utf-8"))["2025-2026"]
        assert got["HB2"]["version"] == "AS AMENDED BY THE SENATE" and got["HB1"] == web
        # A dump of another shape writes nothing and says so.
        before = out.read_bytes()
        (tmp / "db" / "LegislationText.psv").write_text("only|three|fields\r\n", encoding="utf-8")
        try:
            BT.fill(tmp)
            raise AssertionError("a dump with no row as wide as its columns was read as empty")
        except SystemExit as e:
            assert "STOP" in str(e) and out.read_bytes() == before, str(e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a web record is kept over a newer printing; a missing bill gets its chaptered, "
                  "then both-bodies, then latest amended printing, never an OLS release, as "
                  "bill_page.parse_text reads it; a newer printing refreshes only the database's "
                  "own record; a bill not in data/bills.json is left out; a printing headed with "
                  "another bill is skipped and counted; a second run writes nothing; a dump of "
                  "another shape stops; neither file asks the network")


@check("build", "every address the data manifest names may be read from another origin: "
                "_headers gives each Access-Control-Allow-Origin: *")
def _data_cors():
    """A MANIFEST A BROWSER CANNOT FOLLOW (5 November 2026, the API session's
    review). /data/manifest.json is where the Data page sends a program, and
    _headers let a page on another origin read it, the CSVs and the term
    indexes -- but not the public data API's files the manifest also lists:
    people.json, each term's bills-<term>.jsonl.gz, the database, and
    schema.json once the API's branch writes it. Cloudflare Pages sends the
    header on every response today, so nothing failed; the rules are there so
    that the promise does not rest on the host's default (build_pages'
    _headers says why), and a list of rules kept by hand had already missed
    four files.

    So every address the manifest names -- the manifest itself, each table,
    each of its "files", each term index -- is held to a rule, on the
    fixture's whole build. The fixture's record is too small to write the
    register, the database or a second term's bills, so those are named here
    as their writers name them (people.py, api_db.NAME, build_exports'
    bills-<term>.jsonl.gz); and schema.json, which nothing on this branch
    writes yet: the API's branch adds its writer, and from then on the
    fixture writes and lists it too. And where a site/ built from the real
    record is here, as on the laptop, its manifest's addresses are held to
    the same rules. So a file the API adds later is caught by --code when the
    fixture writes it, and otherwise only by a preflight run beside a real
    build (the laptop's), or by adding it to the five named here: the night
    runs --code before it builds, and this is not among its built checks.

    The rules are the ones the build writes now (the fixture's _headers), not
    a site/'s, which may be an older build's. Each address must be given the
    header by exactly one rule, and as "*": Pages appends a header a second
    matching rule names again, and "*, *" is a value a browser refuses, so
    widening to /data/* beside the rules already there would break every
    file it meant to open. They stay narrow, as build_pages says they must:
    none may cover /_headers, /_redirects or the pages. And the reading of a
    _headers text is tested first, so that a reader that matched everything,
    or read the lines otherwise than Pages does, cannot pass this."""
    from urllib.parse import urlsplit
    import api_db

    toy = _cors_rules("/a/*.csv\n  Access-Control-Allow-Origin: *\n"
                      "/b/:x/c\n  Access-Control-Allow-Origin: *\n"
                      "/c\n  Cache-Control: public\n"
                      "/d\n  Access-Control-Allow-Origin: https://example.org\n"
                      "/e/*\n  Access-Control-Allow-Origin: *\n"
                      "/e/f\n  Access-Control-Allow-Origin: *\n"
                      "/g\n  Access-Control-Allow-Origin: *\n  Access-Control-Allow-Origin: *\n"
                      "/h\n  Cache-Control: public\n  /i\n  Access-Control-Allow-Origin: *\n"
                      "/j\nAccess-Control-Allow-Origin: *\n")
    for p, want in (("/a/x.csv", ["*"]), ("/a/x/y.csv", ["*"]), ("/a/x.json", []),
                    ("/b/q/c", ["*"]), ("/b/q/r/c", []), ("/c", []),
                    ("/d", ["https://example.org"]), ("/a/x.csv/", []),
                    ("/e/g", ["*"]), ("/e/f", ["*", "*"]), ("/g", ["*", "*"]),
                    ("/h", []), ("/i", ["*"]), ("/j", ["*"])):
        got = _cors_said(toy, p)
        assert got == want, f"_cors_rules reads {p!r} as sent {got}, not {want}"

    shared, _base, _ran, _days = _fixture_site_shared()
    built = shared / "site"
    rules = _cors_rules((built / "_headers").read_text(encoding="utf-8"))
    assert rules, "the fixture's _headers gives no address Access-Control-Allow-Origin"

    wide = [p for p in ("/_headers", "/_redirects", "/", "/bills", "/bill/2026/hb1")
            if _cors_said(rules, p)]
    assert not wide, ("_headers lets another origin read " + ", ".join(wide)
                      + ": a rule is wider than the record's files (build_pages' _headers)")

    def judge(paths, where):
        none = [p for p in paths if not _cors_said(rules, p)]
        assert not none, (f"{where} names " + ", ".join(none[:6]) + ", and _headers gives no "
                          "rule Access-Control-Allow-Origin: * that covers it (build_pages' "
                          "_headers text)")
        twice = [f"{p} ({', '.join(_cors_said(rules, p))})" for p in paths
                 if len(_cors_said(rules, p)) > 1]
        assert not twice, (f"{where} names " + "; ".join(twice[:6]) + ": more than one "
                           "_headers rule gives it Access-Control-Allow-Origin, and Pages sends "
                           "them joined, a value a browser refuses")
        other = [f"{p} ({_cors_said(rules, p)[0]})" for p in paths
                 if _cors_said(rules, p) != ["*"]]
        assert not other, (f"{where} names " + "; ".join(other[:6]) + ": _headers gives it "
                           "Access-Control-Allow-Origin other than *")

    def addresses(site):
        man = json.loads((site / "data" / "manifest.json").read_text(encoding="utf-8"))
        out = ["/data/manifest.json"]
        out += [f"/data/{t['file']}" for t in man.get("tables") or []]
        out += [str(f.get("path") or "") for f in man.get("files") or []]
        out += [urlsplit(t["url"]).path
                for t in (man.get("bill_indexes") or {}).get("terms") or []]
        return man, sorted(set(out))

    _man, paths = addresses(built)
    real_only = ["/data/people.json", "/data/people.csv", f"/data/{api_db.NAME}",
                 "/data/schema.json", "/data/bills-1989-1990.jsonl.gz"]
    judge(paths + real_only, "the data manifest")
    said = f"the fixture's {len(paths)} and {len(real_only)} only a real record writes"

    real = Path("site") / "data" / "manifest.json"
    if real.is_file():
        man, got = addresses(real.parent.parent)
        judge(got, f"site/data/manifest.json (generated {man.get('generated')}), against the "
                   "_headers this code writes,")
        said += f", and site/'s {len(got)}"
    return "ok", (f"{len(rules)} rules give every address the data manifest names "
                  f"Access-Control-Allow-Origin: *, once each ({said}), and none covers "
                  "/_headers, /_redirects or a page")


@check("build", "the data API's schema.json describes every column it publishes, with the types "
                "the database stores, its keys hold, its names are unique, and no file carries "
                "YouTube's metadata")
def _api_schema():
    """docs/design/api/DESIGN.md, 2.2. The fixture build writes no database
    and no people files (it has no roster), so the paths that describe them
    run only in a full build; this builds a small database with api_db and
    runs the schema over it. Each part is a finding of the review of 5
    November 2026 that no check had caught."""
    import csv as _csv_
    import lzma
    import sqlite3
    import tempfile
    import api_db
    import api_schema as AS

    def put(d, name, cols, rows):
        with (d / name).open("w", encoding="utf-8", newline="") as fh:
            w = _csv_.writer(fh)
            w.writerow(cols)
            w.writerows(rows)

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        put(d, "bills.csv", list(AS.CSV["bills.csv"]),
            [["2025-2026", "2025", "HB1", "a title", "", "", "", "", "", "", "0", "", ""],
             ["2025-2026", "2025", "HB2", "a title", "", "", "", "", "", "", "0", "", ""]])
        put(d, "rollcalls.csv", list(AS.CSV["rollcalls.csv"]),
            [["2025-H-1", "2025-2026", "2025", "H", "1", "2025-01-08", "HR", "q", "", "200", "100",
              "0", "1", "1", "", "", "count"]])
        put(d, "votes-2025-2026.csv", list(AS.CSV["votes-<term>.csv"]),
            [["2025-H-1", "2025-2026", "2025-01-08", "", "q", "m1", "A Member", "R", "House", "Yea"]])
        put(d, "sponsors.csv", list(AS.CSV["sponsors.csv"]),
            [["2025-2026", "HB1", "m1", "A Member", "R", "H", "1", "", "the sponsor file", "1"]])
        put(d, "legislators.csv", list(AS.CSV["legislators.csv"]),
            [["m1", "A Member", "House", "R", "1", "Belknap", "", "", "3", "120", "1"]])
        put(d, "proceedings.csv", list(AS.CSV["proceedings.csv"]),
            [["2025-2026", "HB1", "H", "public hearing", "2025-01-09", "10:00", "Finance", "LOB 210",
              "abc", "100", "620.5", "stated", "", ][:len(AS.CSV["proceedings.csv"])],
             ["2025-2026", "HB2", "H", "public hearing", "2025-01-09", "11:00", "Finance", "LOB 210",
              "abc", "20", "", "stated", ""][:len(AS.CSV["proceedings.csv"])]])
        people = [{"person": "1", "name": "A Member", "member_ids": ["m1"], "employee_numbers": ["m1"]}]
        row = api_db.write(d, api_db.Collector(), people, meetings_path=d / "none.json")
        cols = row["columns"]
        # Every table and column the database holds is described, with the
        # type it is stored as, and no description names a column it lacks.
        assert set(cols) == set(AS.DB_TABLES), f"tables {sorted(set(cols) ^ set(AS.DB_TABLES))} are in one and not the other"
        assert not AS.undescribed_columns([], [], cols), AS.undescribed_columns([], [], cols)
        for t, spec in AS.DB_COLUMNS.items():
            extra = set(spec) - set(cols[t])
            assert not extra, f"api_schema describes {t}.{sorted(extra)}, which the database does not hold"
        raw = d / "db.sqlite"
        raw.write_bytes(lzma.decompress((d / api_db.NAME).read_bytes()))
        con = sqlite3.connect(raw)
        stored = {(t, c): ty for t in cols for (_, c, ty, *_r) in con.execute(f'PRAGMA table_info("{t}")')}
        want = {"integer": "INT", "number": "REAL"}
        wrong = [f"{t}.{c} is {stored[(t, c)] or 'untyped'}, described {f[0]}"
                 for t in cols for c, f in AS.db_spec(t).items()
                 if (t, c) in stored and f[0] in want
                 and not (stored[(t, c)] or "").startswith(want[f[0]])]
        assert not wrong, "the database stores numbers as text: " + "; ".join(wrong)
        order = [r[0] for r in con.execute("SELECT start_seconds FROM proceedings ORDER BY start_seconds")]
        assert order == [20.0, 100.0], f"start_seconds sorts as text: {order}"
        assert dict(con.execute("SELECT key, value FROM meta"))["rights"] == api_db.RIGHTS
        con.close()

        tables = [{"file": f, "rows": 1, "bytes": 1, "what": "",
                   "columns": next(_csv_.reader((d / f).open(encoding="utf-8")))}
                  for f in ("bills.csv", "rollcalls.csv", "votes-2025-2026.csv", "sponsors.csv",
                            "legislators.csv", "proceedings.csv")]
        assert not AS.broken_keys(d, tables), AS.broken_keys(d, tables)
        # A sponsor of a bill bills.csv has no row for breaks a declared key.
        put(d, "sponsors.csv", list(AS.CSV["sponsors.csv"]),
            [["2025-2026", "HB9", "m1", "A Member", "R", "H", "1", "", "the sponsor file", "1"]])
        assert AS.broken_keys(d, tables), "a sponsor of a bill bills.csv lacks passed the keys"
        # YouTube's metadata coming back in a column is described nowhere.
        yt = [dict(t, columns=t["columns"] + ["video_title", "scheduled_seconds"])
              if t["file"] == "proceedings.csv" else t for t in tables]
        assert {c for _, c in AS.undescribed_columns(yt)} == {"video_title", "scheduled_seconds"}
        for spec in list(AS.CSV.values()) + list(AS.DB_COLUMNS.values()) + [AS.BILL_FIELDS, AS.STATION_FIELDS]:
            assert not {"video_title", "scheduled_seconds", "predicted", "watch"} & set(spec), \
                "api_schema describes one of YouTube's own fields, which no file may carry"

        files = [{"path": "/data/people.json", "rows": 1, "bytes": 1},
                 {"path": "/data/people.csv", "rows": 1, "bytes": 1},
                 dict(row, path="/data/" + api_db.NAME)]
        pkg = AS.package(tables, files, "", "2026-11-05", (), (), cols, list(AS.CSV["people.csv"]))
        names = [r["name"] for r in pkg["resources"]]
        assert len(names) == len(set(names)), f"two resources share a name: {names}"
        assert all(r.get("licenses") == AS.LICENSES for r in pkg["resources"]), "a file names no terms"
        assert pkg["x-rights"] == api_db.RIGHTS
        assert not any(fk["reference"]["resource"] == "bills"
                       for r in pkg["resources"] if r["name"] == "rollcalls"
                       for fk in r["schema"].get("foreignKeys", [])), "rollcalls.bill is declared to join bills"
    return "ok", ("a small database is built and every table and column of it described, numbers "
                  "stored as numbers; a broken key and a YouTube column are each caught; names are "
                  "unique and every file names its terms")


@check("reports", "an amendment ends where the next one's heading or the "
                  "calendar's own business begins", needs=("extract_amendments",))
def _amendment_ends(extract_amendments):
    """Amendment texts ran on past their end and into other bills' amendments.

    An amendment ran from its number to the next number, and pdftotext prints
    153 of those numbers as "2023- 0533h", which the marker could not see. So
    2023-0471h on HB 610 was published at 80,199 characters, carrying HB 614's
    and HB 639's amendments; PastAmendments has it at 978. The last amendment
    in a calendar ran on into whatever came next -- HR 15 of 2022 into the
    next day's parking and health screening.

    Measured against PastAmendments (joined by billText id + year and checked
    against the database copy's own heading): 46 of the 2,068 texts of
    2016-2024 shown on a bill page, on 45 pages, were more than 20% longer
    than the General Court's own copy, and 1 is now. That one, 2017-2453h on
    HB 407, is not a run-on: the calendar printed a different, complete
    amendment under that number. 50 shown texts of all years carried another
    bill's heading; none does now.

    The page below needs no data, so this runs under --code. It also holds the
    two cases a cut must NOT make: a sentence that quotes another bill's
    "Amendment to HB 25-A", and a bill's own NOTICE form in capitals.
    """
    EA = extract_amendments
    got = EA.amendments_in(EA.repair_hyphens(AMENDMENT_PAGE), "HC012.pdf")
    assert "2023-0533h" in got, (
        "the number printed '2023- 0533h' opened no amendment: " + str(sorted(got)))
    a, b = got["2023-0471h"]["text"], got["2023-0533h"]["text"]
    assert "HB 614" not in a and "Kidney" not in a and "0533h" not in a, (
        "2023-0471h ran on into the next amendment: ..." + a[-120:])
    assert "HB 174" not in a and "Transportation" not in a and "mobile" not in a, (
        "2023-0471h ran on through a heading whose number no marker reads, "
        "which only the heading itself can end: ..." + a[-160:])
    # The bill each was printed under, which a bill page checks it against.
    assert (got["2023-0471h"].get("heading"), got["2023-0533h"].get("heading")) == (
        "HB610", "HB614"), (got["2023-0471h"].get("heading"),
                            got["2023-0533h"].get("heading"))
    assert "in Amendment to HB 25-A as passed" in a and a.rstrip().endswith(
        "therapeutic cannabis program."), (
        "an amendment that quotes another bill's heading in a sentence was cut "
        "there, or lost its analysis: ..." + a[-160:])
    assert "SESSION DAY" not in b and "park" not in b, (
        "the last amendment ran on into the calendar's session-day notice: ..."
        + b[-120:])
    assert "HOMESTEAD EXEMPTION" in b and b.rstrip().endswith("July 1, 2023."), (
        "a bill's own NOTICE form ended the amendment early: ..." + b[-160:])
    assert got["2023-0533h"]["proposed_by"].startswith("the Committee on Health"), (
        got["2023-0533h"]["proposed_by"])
    return "ok", ("a broken number still opens its amendment, and each ends at "
                  "the next heading, readable number or not, or the calendar's "
                  "own business")


@check("reports", "an amendment's text is its earliest printing unless a later "
                  "one is that printing whole, and is not shown under another "
                  "bill's heading", needs=("extract_amendments", "build_site_v2"))
def _amendment_printing(extract_amendments, build_site_v2):
    """2017 HB 407's page showed the Finance committee's amendment under
    2017-2453h, which is the Labor committee's number.

    House Calendar 52 of 2017 prints 2017-2453h, the Labor committee's; House
    Calendar 11 of 2018 printed the Finance committee's under the same number,
    and the longest printing won. Now the earliest stands, and a later one
    replaces it only where it opens with the earlier one's words -- the
    earlier was cut short. Both 2017-2453h texts open "Amend the bill by
    replacing all after the enacting clause with the following", as most
    amendments do, so the test reads forty words; and House Calendar 15 of
    2016 prints 2016-0539h's "189:18" as ":18", so near enough counts. Over
    the 1,580 calendars this moves 2017-2453h and no other shown text.

    And HB 1180's docket of 2022 moves 2022-0996h, which House Calendar 10A
    prints -- and the database files -- under "Amendment to HB 1347", HB
    1347's committee's amendment. The heading is recorded, and a page leaves
    the text off where the heading names another bill whose docket names the
    number too; not where the calendar misprinted the heading itself --
    2022-1160h under "HB 1160", its own number, and 2026-0976h under "HB
    16678".
    """
    EA, B = extract_amendments, build_site_v2
    boiler = "Amend the bill by replacing all after the enacting clause with the following: "
    labor = {"text": boiler + "1 Workers' Compensation; Medical, Hospital, and Remedial "
             "Care. Amend RSA 281-A:23, VI to read as follows: VI. An employer subject "
             "to this chapter may furnish testing for the presence of a bloodborne disease."}
    finance = {"text": boiler + "1 New Paragraph; Workers' Compensation; Definitions. "
               "Amend RSA 281-A:2 by inserting after paragraph I-a the following new "
               "paragraph: I-aa. Airborne disease means pathogenic microorganisms that "
               "may be discharged through respiratory secretions. 2 Workers' Compensation; "
               "Medical, Hospital, and Remedial Care. Amend RSA 281-A:23, VI to read as "
               "follows: VI. An employer subject to this chapter may furnish testing."}
    assert not EA.replaces(labor, finance), (
        "a longer amendment printed later under the same number replaced the "
        "earlier one, though it opens differently")
    cut = {"text": "Amend RSA 189:18 as inserted by section 1 of the bill by replacing it "
           "with the following: :18 Patriotic Exercises. In all public schools of the "
           "state one session shall be devoted to exercises of a patriotic nature."}
    whole = {"text": "Amend RSA 189:18 as inserted by section 1 of the bill by replacing "
             "it with the following: 189:18 Patriotic Exercises. In all public schools "
             "of the state one session shall be devoted to exercises of a patriotic "
             "nature, which shall include a discussion of the Pledge of Allegiance."}
    assert EA.replaces(cut, whole) and not EA.replaces(whole, cut), (
        "a fuller printing of the same amendment did not replace a shorter one")

    def narr(bill, num):
        return {"bill": bill, "events": [{
            "type": "amendment", "body": "H", "date": "2022-03-16",
            "raw": f"Amendment #{num} : AF DV 170-170 03/16/2022", "amendment": num,
            "amend_kind": "Amendment", "motion": "AF", "vote_kind": "DV",
            "mover": "", "cancelled": False}]}
    texts = {"2022-0996h": {"text": "Amend the title of the bill.", "heading": "HB1347",
                            "source": "HC010A.pdf", "proposed_by": "Rep. Cushman"},
             "2022-1160h": {"text": "Amend the bill by replacing section 1.",
                            "heading": "HB1160", "source": "HC012.pdf"}}
    claims = {"2022-0996h": {"HB1180", "HB1347"}, "2022-1160h": {"HB1604"}}
    got = B.bill_amendments(narr("HB1180", "2022-0996h"), texts, claims)
    assert [(a["num"], a["text"], a["source"], a["proposed_by"]) for a in got] == [
        ("2022-0996h", "", "", "")], (
        "an amendment printed under another bill's heading, whose docket names "
        "it too, was shown on this bill: " + str(got))
    got = B.bill_amendments(narr("HB1347", "2022-0996h"), texts, claims)
    assert got[0]["text"] == "Amend the title of the bill.", got
    got = B.bill_amendments(narr("HB1604", "2022-1160h"), texts, claims)
    assert got[0]["text"] == "Amend the bill by replacing section 1.", (
        "a heading the calendar misprinted took the text off its own bill: "
        + str(got))
    return "ok", ("the earliest printing stands unless a later one is it whole; "
                  "another bill's amendment is left off its page")


# A House listing block and a committee's own page, in the shapes the General
# Court prints them: the listing separates a label from its value with a
# literal &nbsp;, and the committee page runs its duty straight into the
# site's navigation. Made up, and read by the real parsers.
_CMTE_LISTING = (
    "<h3><a href='committeedetails.aspx?id=43'>Fixture Affairs</a></h3>"
    "<p>Chairman:&nbsp;Jane Doe<br />Vice Chairman:&nbsp;John Roe<br />"
    "Committee Assistant:&nbsp;Pat Aide<br /><br />"
    "Location:&nbsp;<span title='Legislative Office Building'>LOB&nbsp;Room&nbsp;302</span>"
    "<br />Phone:&nbsp;603-271-3334</p>" + "<!-- the committee's section -->" * 6)
_CMTE_PAGE = (
    "<html><body><div>Chairman:&nbsp;Old Chair<br />Clerk:&nbsp;Kim Clerk<br />"
    "Researcher:&nbsp;Rae Search<br /></div><p>Pursuant to House Rule 99: It shall "
    "be the duty of the Committee on Fixture Affairs to consider matters relating "
    "to fixtures, their care and their testing, and such other matters as may be "
    "referred to it.</p><div>HELPFUL LINKS Committees of Conference</div></body></html>")


@check("build", "a weekly committees.json and committee_details.json still give a committee page its purpose and clerk",
       needs=("committee_details", "fetch_committees", "fetch_committee_details"))
def _committee_details_survive_the_weekly(CD, FC, FCD):
    """GitHub's weekly job swaps committees.json in whole, from the two pages
    that list the committees, and those pages carry no clerk and no purpose.
    Until 26 September fetch_committee_details.py wrote both INTO
    committees.json, and build_committees read them from there, so the first
    Sunday the weekly ran would have taken the clerk off 22 committee pages
    and the purpose off 23, with nothing failing: a page without a purpose
    renders perfectly.

    So the details have their own file, committee_details.json, and
    build_committees joins the two. This builds one committee page from a
    committees.json made by fetch_committees.py's own parser -- so it holds
    exactly what the weekly writes -- and a committee_details.json made the
    way fetch_committee_details.py makes it, and asks the page for its
    purpose and its clerk. And again without the details file, which must
    warn and build rather than stop, and whose page must lack them: that half
    is what shows the first half can see the loss.

    Which file gives a field both pages carry is held too: committees.json
    alone. The listing's chair stands over the detail page's (the listing is
    read weekly, the detail pages when a person asks), and since 26 September
    the detail page's researcher no longer fills in where the listing has
    none, so the details file is a source of the clerk, the purpose and the
    roster and of nothing else.

    And a details file that is here and will not read stops the build with a
    sentence saying what to do, rather than building every page without them.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_committees.py").exists() or not (here / "src/pages/bills.html").exists():
        return "skip", "build_committees.py or bills.html not here"
    rows = FC.parse(_CMTE_LISTING, "H")
    assert len(rows) == 1 and rows[0]["chair"] == "Jane Doe", (
        f"fetch_committees.parse no longer reads the fixture's listing: {rows}")
    carried = sorted({k for r in rows for k in r} & set(CD.ONLY_HERE))
    assert not carried, (f"fetch_committees.py now writes {carried} itself, so "
                         "committee_details.json is no longer the only source of "
                         "them; say which file wins in committee_details.py")
    rec = FCD.parse(_CMTE_PAGE)
    assert rec.get("clerk") == "Kim Clerk" and (rec.get("purpose") or {}).get(
        "rule") == "House Rule 99", f"fetch_committee_details.parse misread the page: {rec}"
    duty = rec["purpose"]["text"]
    book = {}
    CD.put(book, "H", rows[0], rec, "2026-09-26")

    root = Path(tempfile.mkdtemp(prefix="gr-cmte-details-"))
    try:
        (root / "site").mkdir()
        (root / "data").mkdir()
        (root / "src" / "pages").mkdir(parents=True, exist_ok=True)
        shutil.copy2(here / "src/pages/bills.html", root / "src/pages/bills.html")
        (root / "data" / "committees.json").write_text(json.dumps(
            {"H43": {"code": "H43", "name": "Fixture Affairs", "abbr": "FIXTURE"}}),
            encoding="utf-8")
        _bill_index_write(root / "site", [
            {"id": "HB1", "n": "HB 1", "term": "2025-2026", "year": "2026",
             "title": "A fixture bill", "status": "In committee", "kind": "bill",
             "committee": "House Fixture Affairs",
             "committees": ["House Fixture Affairs"]}])
        (root / "committees.json").write_text(json.dumps({"H": rows}), encoding="utf-8")
        CD.write_details(book, root / "committee_details.json")

        def build(stops=False):
            r = _run([sys.executable, _paths.script("build_committees.py"), "--site", "site",
                      "--data", "data", "--base", "https://graniterecord.org"],
                     cwd=root, capture_output=True, text=True, timeout=180)
            out = (r.stdout or "") + (r.stderr or "")
            if stops:
                return r.returncode, out
            assert r.returncode == 0, f"build_committees stopped: {out.strip()[-200:]}"
            page = root / "site" / "committee" / "H43.json"
            assert page.exists(), "build_committees wrote no page for the fixture's committee"
            return (json.loads(page.read_text(encoding="utf-8")),
                    (root / "site" / "committee" / "H43.html").read_text(encoding="utf-8"),
                    out)

        got, html, _ = build()
        assert (got.get("purpose") or {}).get("text") == duty, (
            "with committee_details.json beside a weekly committees.json, the page "
            f"has no purpose: {got.get('purpose')!r}")
        assert got.get("clerk") == "Kim Clerk" and any(
            o.get("role") == "Clerk" and o.get("name") == "Kim Clerk"
            for o in got.get("officers") or []), (
            f"the page lost its clerk: clerk={got.get('clerk')!r}, "
            f"officers={got.get('officers')}")
        assert duty in html, "the page's noscript no longer quotes the committee's duty"
        assert got.get("chair") == "Jane Doe", (
            f"the chair is {got.get('chair')!r}: the detail page's reading won over "
            "the listing's, which the weekly job keeps current")
        assert not got.get("researcher"), (
            f"the page's researcher is {got.get('researcher')!r}, which only the "
            "details file carries: it is filling a field both pages carry, which "
            "is committees.json's alone")

        good = (root / "committee_details.json").read_bytes()
        (root / "committee_details.json").write_bytes(good[:len(good) // 2])
        shutil.rmtree(root / "site" / "committee")
        rc, out = build(stops=True)
        assert rc != 0 and "will not read" in out and "move it aside" in out, (
            "a committee_details.json cut off half way did not stop the build with "
            f"a sentence saying what to do (exit {rc}): {out.strip()[-200:]}")
        assert not (root / "site" / "committee" / "H43.json").exists(), (
            "the build stopped on an unreadable committee_details.json but wrote pages first")

        (root / "committee_details.json").unlink()
        shutil.rmtree(root / "site" / "committee", ignore_errors=True)
        got, html, out = build()
        assert "committee_details.json is not here" in out, (
            "a build without committee_details.json said nothing about it")
        assert not got.get("purpose") and not got.get("clerk") and duty not in html, (
            "without committee_details.json the page still carries a purpose or a "
            "clerk, so this check could not tell the join from its absence")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("a committees.json of what the weekly writes, and committee_details.json, "
                  "give a page its purpose, clerk and the listing's chair and nothing "
                  "else; an unreadable details file stops the build, and without one "
                  "the build warns and the page goes without")


@check("build", "with committee_details.json here, committees.json is no second source of a clerk, a purpose or a roster",
       needs=("committee_details",))
def _committee_details_one_source(CD):
    """committees.json on the laptop, and the copy the first seed-kit put in
    the bucket, still carry the clerk, the purpose and the web roster that
    fetch_committee_details.py merged into it before 26 September. The join
    used to start each row from committees.json and lay only the details'
    non-empty values over it, so those old values were a hidden second
    source: a clerk taken out of committee_details.json -- by hand, or by a
    fetch of a page that no longer names one -- stayed on the committee page.

    So, with a details file: the three come from it alone, and a row it has
    nothing for goes without, with a warning that names the committee. The
    details give no other field, not even to fill a gap. Only with no details
    file at all does a row keep committees.json's values, and that warns too.
    A details file that is here and will not read stops the reader with a
    sentence saying what to do; an empty one is a file that says nothing.
    """
    import contextlib
    import io
    old_duty = {"rule": "House Rule 1", "text": "The old duty, which the details no longer say."}
    new_duty = {"rule": "House Rule 99", "text": "The duty the committee's page says today."}
    web = {"H": [
        {"chamber": "H", "code": "43", "name": "Fixture Affairs", "chair": "Jane Doe",
         "clerk": "Old Clerk", "purpose": old_duty,
         "web_members": [{"name": "Jane Doe", "party_code": "R", "pid": "1"}]},
        {"chamber": "H", "code": "44", "name": "Second Fixtures", "chair": "Sam Roe",
         "clerk": "Also Old"}]}
    details = {"H": {"43": {"name": "Fixture Affairs", "purpose": new_duty,
                            "chair": "Old Chair", "researcher": "Rae Search",
                            "fetched": "2026-09-26"}}}
    frozen = json.dumps([web, details], sort_keys=True)
    root = Path(tempfile.mkdtemp(prefix="gr-cmte-source-"))
    try:
        cj, dj = root / "committees.json", root / "committee_details.json"
        cj.write_text(json.dumps(web), encoding="utf-8")

        def read():
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                got = CD.read(str(cj), str(dj))
            return {r["code"]: r for r in got["H"]}, err.getvalue()

        dj.write_text(json.dumps(details), encoding="utf-8")
        rows, said = read()
        h43, h44 = rows["43"], rows["44"]
        assert "clerk" not in h43 and "clerk" not in h44, (
            f"a clerk committees.json still carries reached the page past a details "
            f"file that names none: {h43.get('clerk')!r}, {h44.get('clerk')!r}")
        assert h43.get("purpose") == new_duty and "purpose" not in h44, (
            f"the purpose did not come from the details alone: {h43.get('purpose')}, "
            f"{h44.get('purpose')}")
        assert "web_members" not in h43, (
            "committees.json's old web roster stood where the details have none")
        assert h43.get("chair") == "Jane Doe" and "researcher" not in h43, (
            f"the details gave a field both pages carry: chair {h43.get('chair')!r}, "
            f"researcher {h43.get('researcher')!r}; those are committees.json's alone")
        named = [ln for ln in said.splitlines() if "no record in" in ln]
        assert named and named[0].split("purpose: ")[-1].split(".")[0] == "H44", (
            f"a committee with no details record was not named in a warning: {said!r}")
        assert json.dumps([web, details], sort_keys=True) == frozen, (
            "the join changed the rows it was given")

        dj.write_text("{}", encoding="utf-8")
        rows, said = read()
        assert not any(r.get(k) for r in rows.values() for k in CD.ONLY_HERE), (
            "an empty committee_details.json let committees.json's clerk or purpose through")
        assert "H43" in said and "H44" in said, f"an empty details file named nobody: {said!r}"

        dj.unlink()
        rows, said = read()
        assert rows["43"].get("clerk") == "Old Clerk" and rows["43"].get("purpose") == old_duty, (
            "with no details file, the build no longer falls back to committees.json")
        assert "is not here" in said, "a build with no details file said nothing about it"

        dj.write_text('{"H": {"43": {"clerk": "Kim', encoding="utf-8")
        try:
            read()
        except SystemExit as e:
            why = str(e.code)
        else:
            raise AssertionError("a committee_details.json that will not read was built from")
        assert "will not read" in why and "Mend it" in why and "move it aside" in why, (
            f"the stop on an unreadable details file does not say what to do: {why!r}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("with a details file, clerk, purpose and roster come from it alone and a "
                  "committee without a record is named; no file falls back and warns; "
                  "a file that will not read stops")


@check("build", "committee_details.json is written whole or not at all", needs=("committee_details",))
def _committee_details_atomic(CD):
    """write_details wrote the file in place, so a write that stopped half way
    -- a full disk, a killed process -- left a file that will not read, and a
    build meeting that file now stops. It writes a sibling and moves it into
    place: stopped before the move, the old file is untouched."""
    root = Path(tempfile.mkdtemp(prefix="gr-cmte-atomic-"))
    real = os.replace
    try:
        dj = root / "committee_details.json"
        CD.write_details({"H": {"43": {"clerk": "Kim Clerk"}}}, dj)
        first = dj.read_bytes()

        def refused(*a, **k):
            raise OSError("the move was stopped")
        os.replace = refused
        try:
            CD.write_details({"H": {"43": {"clerk": "Someone Else"}}}, dj)
        except OSError:
            pass
        finally:
            os.replace = real
        assert dj.read_bytes() == first, (
            "committee_details.json changed although the write was stopped before "
            "it finished: write_details writes the file in place")
        CD.write_details({"S": {"30": {"clerk": "B"}}, "H": {"9": {}, "10": {}}}, dj)
        assert json.loads(dj.read_text(encoding="utf-8")) == {
            "H": {"10": {}, "9": {}}, "S": {"30": {"clerk": "B"}}}
        assert list(json.loads(dj.read_text(encoding="utf-8"))) == ["H", "S"]
        assert [p.name for p in root.iterdir()] == ["committee_details.json"], (
            f"write_details left something beside the file: {[p.name for p in root.iterdir()]}")
    finally:
        os.replace = real
        shutil.rmtree(root, ignore_errors=True)
    return "ok", "a write stopped before the move leaves the old file; a finished one leaves nothing beside it"


@check("build", "a committee page read as one replaces its clerk, purpose and roster; a failed or empty one changes nothing",
       needs=("committee_details", "fetch_committee_details"))
def _committee_fetch_replaces(CD, FCD):
    """The fetch merged into committee_details.json and set only non-empty
    values, so no fetch could ever take off a clerk the General Court had
    removed: a stale clerk stayed on the committee's page for good.

    So a page that parses as a committee's -- a purpose or a roster came out
    of it -- replaces that committee's clerk, purpose and roster with exactly
    what it says, and the record carries the day it was read. A page that
    failed, or parsed as nothing, changes nothing: an empty parse is a parser
    that stopped matching. And a run that would take a field off every
    committee it read that had one is refused, because a purpose pattern that
    stopped matching while the roster still parses looks exactly like that.
    --probe writes nothing, so it does not stop on a file that will not read.

    Run through fetch_committee_details.main with get() stubbed and
    urlopen made to fail: nothing is asked of anybody. Its refusal.check()
    reads a refusal record in a temp folder, never this machine's -- whose
    standing refusal, or GitHub's night window on a stood-down laptop, would
    otherwise stop the test -- and a refusal there stops the fetch before it
    asks for anything.
    """
    import contextlib
    import datetime
    import io
    import time as _time
    import urllib.error
    rows = [{"chamber": "H", "code": str(c), "name": f"Fixture {c}",
             "url": f"https://example.invalid/committee/{c}"} for c in (41, 42, 43, 44)]
    duty = ("It shall be the duty of the Committee on Fixtures to consider matters "
            "relating to fixtures, and such other matters as may be referred to it.")
    on_file = {"H": {str(c): {"name": f"Fixture {c}", "clerk": f"Clerk {c}",
                              "purpose": {"rule": "House Rule 9", "text": duty},
                              "web_members": [{"name": "Old Member", "party_code": "D",
                                               "pid": "9"}]}
                     for c in (41, 42, 43, 44)}}
    page = ("<html><body><div>Chairman:&nbsp;Jane Doe<br />Clerk:&nbsp;<br />"
            "Researcher:&nbsp;Rae Search</div>"
            "<a href='member.aspx?pid=1'>Jane Doe</a> (R) "
            "<a href='member.aspx?pid=2'>John Roe</a> (D) "
            f"<p>Pursuant to House Rule 31: {duty}</p>"
            "<div>HELPFUL LINKS Committees of Conference</div></body></html>")
    real_get, real_open, real_mark = FCD.get, FCD.urllib.request.urlopen, FCD.refusal.MARK

    def no_network(*a, **k):
        raise AssertionError("fetch_committee_details opened a connection in preflight")
    root = Path(tempfile.mkdtemp(prefix="gr-cmte-fetch-"))
    try:
        cj, dj = root / "committees.json", root / "committee_details.json"
        cj.write_text(json.dumps({"H": rows}), encoding="utf-8")
        FCD.urllib.request.urlopen = no_network
        (root / "archive").mkdir()
        FCD.refusal.MARK = root / "archive" / "refused.json"

        def run(args, answer):
            asked = []

            def get(url):
                asked.append(url)
                return answer(url)
            FCD.get = get
            argv = sys.argv
            sys.argv = ["fetch_committee_details.py", "--file", str(cj), "--out", str(dj),
                        "--delay", "0"] + args
            out = io.StringIO()
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                    rc = FCD.main()
            except SystemExit as e:
                rc = e.code
            finally:
                sys.argv = argv
            return rc, out.getvalue(), asked

        def failed(url):
            raise urllib.error.HTTPError(url, 500, "Server Error", {}, None)

        CD.write_details(on_file, dj)
        days = {datetime.date.today().isoformat()}
        rc, out, asked = run(["--only", "H41"], lambda url: page)
        days.add(datetime.date.today().isoformat())
        got = json.loads(dj.read_text(encoding="utf-8"))["H"]
        assert rc == 0 and asked == [rows[0]["url"]], f"the H41 run did not write: {out[-300:]}"
        assert "clerk" not in got["41"], (
            f"a committee page that names no clerk left the old one on file: {got['41']}")
        assert got["41"].get("fetched") in days, f"the record is not stamped: {got['41']}"
        assert got["41"]["purpose"]["rule"] == "House Rule 31" and [
            m["name"] for m in got["41"]["web_members"]] == ["Jane Doe", "John Roe"], (
            f"the purpose or roster is not what the page says: {got['41']}")
        assert all(got[c] == on_file["H"][c] for c in ("42", "43", "44")), (
            "an --only run changed another committee's record")

        snap = dj.read_bytes()
        rc, out, _ = run(["--only", "H42"], failed)
        assert dj.read_bytes() == snap, "a page that failed changed committee_details.json"
        rc, out, _ = run(["--only", "H42"], lambda url: "<html><body>Unavailable</body></html>")
        assert json.loads(dj.read_text(encoding="utf-8"))["H"]["42"] == on_file["H"]["42"], (
            "a page that parsed as nothing changed its committee's record")

        snap = dj.read_bytes()
        no_duty = page.replace("Pursuant to House Rule 31:", "Nothing to see:").replace(
            "Clerk:&nbsp;<br />", "Clerk:&nbsp;A Clerk<br />")
        rc, out, _ = run([], lambda url: no_duty)
        assert rc == 1 and dj.read_bytes() == snap and "had a purpose on file would lose" in out, (
            "a run that took the purpose off every committee it read was written: "
            f"{out.strip()[-300:]}")

        dj.write_bytes(snap[:40])
        rc, out, _ = run(["--probe", "--only", "H43"], lambda url: page)
        assert rc == 0 and dj.read_bytes() == snap[:40], (
            f"--probe stopped on, or wrote to, a file that will not read: {out.strip()[-200:]}")
        rc, out, asked = run(["--only", "H43"], lambda url: page)
        assert rc not in (0, None) and not asked and dj.read_bytes() == snap[:40], (
            "a fetch that will write went ahead over a committee_details.json that will not read")

        # A standing refusal stops it before the first request, --probe too.
        FCD.refusal.MARK.write_text(json.dumps({"at": "t", "epoch": _time.time(),
                                                "where": "fixture", "why": "403"}),
                                    encoding="utf-8")
        for args in (["--only", "H44"], ["--probe", "--only", "H44"]):
            rc, out, asked = run(args, lambda url: page)
            assert rc == 2 and not asked and "refused" in out, (
                f"{args}: a standing refusal did not stop the committee pages fetch "
                f"(exit {rc}, asked {asked})")
    finally:
        FCD.get, FCD.urllib.request.urlopen, FCD.refusal.MARK = real_get, real_open, real_mark
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("a page read as a committee's takes off a clerk it no longer names and is "
                  "stamped; a failed or empty page changes nothing; a run emptying a field "
                  "everywhere is refused; --probe reads past a broken file; a standing "
                  "refusal stops it before it asks")


@check("cloud", "a county officer the record names and the county's own page does not is "
       "flagged for the owner, and nothing writes the officials file",
       needs=("state_sources",))
def _state_sources_officials(SS):
    """The owner found Strafford County's commissioners stale after a
    resignation between elections (5 November 2026), and wants such offices
    checked regularly. state_sources.py officials reads the latest reading of
    each county's registered officers' pages and says, for each person on
    record, whether a page names them beside their office. A flag is a
    question for the owner, never an edit: corrections/officials.json is the
    owner's file, read through its one reader.

    Held here, on pages written the way county sites write them (the review
    of 5 November): every county on record has a page registered or wanted;
    "Board of Commissioners", plural, names the office; a person named
    without their middle initial, or by a common short form of their first
    name, is the same person; one named beside "resigned" is flagged; a
    first name and a surname that appear apart are not the person; a
    deputy's title is not the office; a page naming no office raises no flag;
    a county's home page, whose menu names every office and no one, is never
    checked; and the officials file is the same after the run as before.
    """
    import build_members_elect as BME
    reg = SS.load_registry(_paths.ROOT)
    hand = _paths.ROOT / "corrections" / ("officials" + ".json")
    hand_before = hand.read_bytes()
    doc = json.loads(json.dumps(BME.read_officials()))
    on_record = SS.officials_on_record(doc)
    covered = {r["jurisdiction"].split(":", 1)[1] for r in reg.values()
               if r["jurisdiction"].startswith("county:")
               and {"officials:county", "officials:county-site"} & set(r["used_by"].split())}
    missing = sorted(set(on_record) - covered)
    assert not missing, (f"these counties' officers are on record and no page of theirs is "
                         f"registered, not even as wanted: {missing}")
    sites = [i for i, r in reg.items() if "officials:county-site" in r["used_by"].split()]
    # The fixture's officers, so that it does not rest on who holds office today.
    c = doc["county"]["counties"]["Strafford"]
    c["commissioners"] = {
        "1": {"name": "Joseph Q. Pitman", "office": "County Commissioner, District 1"},
        "2": {"name": "Georgia Maglor", "office": "County Commissioner, District 2"},
        "3": {"name": "Sean M. Lovell", "office": "County Commissioner, District 3"}}
    c["sheriff"] = {"name": "William Wrightson", "office": "Sheriff"}
    c["treasurer"] = {"name": "Pamela Arnet", "office": "County Treasurer"}
    c["county_attorney"] = {"name": "Emily Garrod", "office": "County Attorney"}
    c["register_of_deeds"] = {"name": "Mary Deedham", "office": "Register of Deeds"}
    c["register_of_probate"] = {"name": "Jan Probert", "office": "Register of Probate"}
    pid = next(i for i, r in reg.items() if r["jurisdiction"] == "county:Strafford"
               and "officials:county" in r["used_by"].split())
    t = Path(tempfile.mkdtemp(prefix="granite-officials-"))
    try:
        (t / "records" / "sources").mkdir(parents=True)
        shutil.copy(_paths.ROOT / SS.REGISTRY, t / SS.REGISTRY)
        d = t / SS.FOLDER / pid
        d.mkdir(parents=True)
        (d / "2026-11-05.txt").write_text(
            "Board of Commissioners\n"
            "Georgia Maglor, Chair\nSean Lovell, Vice Chair\n"
            "Commissioner Joe Pitman resigned in October; the seat is vacant.\n"
            "Sheriff's Office: Sheriff Bill Wrightson\n"
            "Deputy Treasurer: Robin Hood\n"
            "County Attorney's Office\n"
            "Emily is our clerk. Garrod Road is closed.\n", encoding="utf-8")
        # A newer file that cannot be read must not hide the reading.
        (d / "2026-11-05-2.png").write_bytes(b"not a page")
        for site in sites[:1]:
            (t / SS.FOLDER / site).mkdir(parents=True)
            (t / SS.FOLDER / site / "2026-11-05.txt").write_text(
                "Commissioners | Sheriff | County Attorney | Treasurer | Registry of Deeds",
                encoding="utf-8")
        lines, n = SS.check_officials(t, SS.load_registry(t), None, doc)
        mine = {}
        for county, ln in lines:
            m = re.match(r"(FLAG|SAME|NAMED|NOT ON THE PAGES)\s+(.+?): ", ln)
            if county == "Strafford" and m:
                mine[m.group(2)] = m.group(1).split()[0]
        out = "\n".join(f"{c} {ln}" for c, ln in lines)
        want = {"County Commissioner, District 1": "FLAG",      # beside "resigned"
                "County Commissioner, District 2": "SAME",      # plural board heading
                "County Commissioner, District 3": "SAME",      # no middle initial
                "Sheriff": "SAME",                              # Bill for William
                "County Treasurer": "NOT",                      # a deputy's title only
                "County Attorney": "FLAG",                      # named apart, not her
                "Register of Deeds": "NOT", "Register of Probate": "NOT"}
        assert mine == want, (f"the officers' judgements are not as written: {mine}", out)
        site_counties = {reg[s]["jurisdiction"].split(":", 1)[1] for s in sites[:1]}
        for county, ln in lines:
            if county in site_counties:
                assert not ln.startswith(("FLAG", "SAME")), (
                    "a county's home page was checked as a list of its officers", out)
        assert n == sum(1 for v in want.values() if v == "FLAG") + sum(
            1 for c, ln in lines if c != "Strafford" and ln.startswith("FLAG")), out
        assert not (t / "corrections").exists(), "the check wrote into a corrections folder"
    finally:
        shutil.rmtree(t, ignore_errors=True)
    assert hand.read_bytes() == hand_before, "the officials file changed during the check"
    src = _source(_paths.locate("state_sources.py"))
    code = re.sub(r'"""[\s\S]*?"""|#[^\n]*', "", src)
    assert "corrections" not in code.replace('HAND_FILE = "the officials file in corrections/"',
                                             ""), (
        "state_sources.py names a corrections path in its code, beyond the words of a message")
    return "ok", (f"{len(on_record)} counties' officers, each county with a page registered "
                  "or wanted; a plural heading, a short first name and a missing initial "
                  "matched, a resignation and a name split apart flagged, a deputy's title "
                  "not taken for the office, a home page's menu left unchecked, and the "
                  "officials file left as it was")


@check("cloud", "a browser's downloads are filed by the address each came from, copied "
       "and never moved, and a state document that cannot be placed is named",
       needs=("state_sources",))
def _state_sources_file(SS):
    """state_sources.py file reads the folder Chrome saved into on the laptop
    (30 October 2026). Windows records each download's address in a stream
    beside it, which reads as "<name>:Zone.Identifier". It is written here the
    way Chrome writes it, with the built-in open of that name: on Windows (the
    nightly's machine, and the laptop) that is the stream itself, and on Linux
    an ordinary file of that name. Where the stream cannot be written and read
    back -- a Windows folder whose file system has no streams -- the parts that
    rest on a recorded address are skipped, and the check says so; everywhere
    else that is a failure. A file is
    placed by that address, else by a name only one registered address ends
    in ("name (1).pdf" being Chrome's second copy); --as names one by hand and
    is refused where the recorded address says otherwise. Nothing is moved or
    deleted, a document filed once is not filed again, and a state document
    the registry lacks is named with the row it would need, not filed.
    """
    import contextlib
    import io
    reg = SS.load_registry(_paths.ROOT)
    pdfs = [(i, r) for i, r in reg.items() if r["kind"] == "pdf" and r["read_by"] == "browser"]
    leaves = {}
    for i, r in pdfs:
        leaves.setdefault(SS.leaf(r["url"]), []).append(i)
    (a_id, a_row), = pdfs[:1]
    b_id, b_row = next((i, r) for i, r in pdfs[1:] if len(leaves[SS.leaf(r["url"])]) == 1)
    t = Path(tempfile.mkdtemp(prefix="granite-file-"))
    try:
        root, dl = t / "root", t / "Downloads"
        (root / "records" / "sources").mkdir(parents=True)
        dl.mkdir()
        shutil.copy(_paths.ROOT / SS.REGISTRY, root / SS.REGISTRY)

        def run(*argv):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = SS.main(["file", *argv, "--root", str(root)])
            return code, out.getvalue()

        def zone(name, url):
            with open(str(dl / name) + ":Zone.Identifier", "w", encoding="utf-8") as fh:
                fh.write(f"[ZoneTransfer]\r\nZoneId=3\r\nHostUrl={url}\r\n")

        (dl / "download.pdf").write_bytes(b"by address")
        try:
            zone("download.pdf", a_row["url"])
            streams = SS.downloaded_from(dl / "download.pdf") == a_row["url"]
        except OSError:
            streams = False
        assert streams or os.name == "nt", (
            "the recorded address of a download, written as Chrome writes it, did not read "
            "back here, and only a Windows folder without streams excuses that")
        stem, ext = SS.leaf(b_row["url"]).rsplit(".", 1)
        (dl / f"{stem} (1).{ext}").write_bytes(b"by name")
        (dl / "holiday.jpg").write_bytes(b"not a document")
        if streams:
            (dl / "unknown.pdf").write_bytes(b"not registered")
            zone("unknown.pdf", "https://www.das.nh.gov/budget/not-in-the-registry.pdf")
            code, out = run(str(dl), "--day", "2026-10-29", "--dry-run")
            assert code == 1 and not (root / "sources").exists(), (
                "a dry run wrote, or did not say a document was not placed", out)
            code, out = run(str(dl), "--day", "2026-10-29")
            assert code == 1 and "could not be placed" in out, (
                "a state document that could not be placed went unremarked", out)
            assert (root / "sources" / a_id / "2026-10-29.pdf").read_bytes() == b"by address", out
            assert "NOT PLACED unknown.pdf" in out and "not-in-the-registry.pdf,pdf," in out, out
            # Out of the way. On Windows its stream goes with it; on Linux the
            # stand-in for the stream is a file of its own, moved after it.
            (dl / "unknown.pdf").rename(t / "unknown.pdf")
            if os.path.isfile(str(dl / "unknown.pdf") + ":Zone.Identifier"):
                os.replace(str(dl / "unknown.pdf") + ":Zone.Identifier",
                           str(t / "unknown.pdf") + ":Zone.Identifier")
        else:
            (dl / "download.pdf").unlink()
            code, out = run(str(dl), "--day", "2026-10-29", "--dry-run")
            assert code == 0 and not (root / "sources").exists(), ("a dry run wrote", out)
            code, out = run(str(dl), "--day", "2026-10-29")
            assert code == 0, out
        assert (root / "sources" / b_id / "2026-10-29.pdf").read_bytes() == b"by name", out
        assert (dl / f"{stem} (1).{ext}").exists(), ("the filer moved a download rather "
                                                     "than copy it")
        n = sorted(p.relative_to(root).as_posix() for p in (root / "sources").rglob("*")
                   if p.is_file())
        code, out = run(str(dl), "--day", "2026-10-29")
        assert code == 0 and "ALREADY" in out, out
        assert sorted(p.relative_to(root).as_posix() for p in (root / "sources").rglob("*")
                      if p.is_file()) == n, "a document already filed that day was filed again"
        # The same bytes read on a later day are a reading that found no
        # change: filed, so that up records the check and due moves on.
        code, out = run(str(dl), "--day", "2026-10-30")
        assert code == 0 and (root / "sources" / b_id / "2026-10-30.pdf").is_file(), (
            "a later reading with no change was not filed, so due would list it forever", out)
        if streams:
            code, out = run(str(dl / "download.pdf"), "--as", b_id)
            assert code == 1 and "not from" in out, ("--as filed a download under an id its "
                                                     "recorded address contradicts", out)
        empty = t / "empty"
        empty.mkdir()
        code, out = run(str(empty))
        assert code == 0 and "Nothing new to file" in out, out
    finally:
        shutil.rmtree(t, ignore_errors=True)
    if not streams:
        return "ok", ("placed by name, copied not moved, filed once; the parts resting on "
                      "a download's recorded address skipped: this Windows folder has no "
                      "streams to record one in")
    return "ok", ("placed by recorded address and by name, copied not moved, filed once, "
                  "--as checked against the address, an unregistered state document named")


@check("build", "a journal record joins the record only where nothing else has the bill",
       needs=("build_data", "build_all"))
def _journal_into_data(BD, BA):
    """build_data.add_journal_bills puts a withdrawn bill into data/bills.json
    only in a term already there, and never over a bill the General Court's
    files carry. A term it created would read to the archive merge as "built
    from session files" and the real term would be skipped -- 2025-2026 nine
    bills long. A missing file is said, loudly, and adds nothing.

    The sponsors are the journal's, in its order, the first prime and marked
    inferred, under source "House Journal"; each is labelled with the seat the
    roster gives -- Sellers prints "Graf. 18", his 2023-2024 seat, and sits
    for Grafton 10 -- a member who has left from their own votes, and a name
    nobody fits as printed. And the step runs before build_data reads it.
    """
    import contextlib
    import io
    steps = [s.name for s in BA.plan(type("A", (), {
        "key": None, "session": "2026", "base": "https://graniterecord.org",
        "archive": "nh-archive"})())]
    at = {n: i for i, n in enumerate(steps)}
    assert at["bills the House withdrew, from its journals"] < at["build data (first pass)"], (
        "the journal step runs after build_data has read its output")
    root = Path(tempfile.mkdtemp())
    try:
        mine = {"bill": "HB10", "lsr": "2025-0042", "lsr_year": "2025",
                "lsr_num": "0042", "title": "the General Court's own"}
        by_term = {"2025-2026": {"HB10": mine},
                   "2023-2024": {"HB1": {"bill": "HB1", "lsr_year": "2023",
                                         "archived": True}}}
        rec = {"bill": "HB476", "designation": "HB 476-FN", "suffix": "-FN",
               "title": "relative to restrictions on elective abortion.", "chamber": "H",
               "year": "2025", "committee": "Judiciary",
               "sponsors": ["Peternel, Carr. 6"],
               "introduced": {"date": "2025-01-09", "journal": "HJ 3", "page": 12},
               "withdrawn": {"date": "2025-02-06", "journal": "HJ 4", "page": 1,
                             "how": "motion", "vote": "335-18, division"}}
        p = root / "journal_bills.json"
        p.write_text(json.dumps({
            "2025-2026": {"HB476": rec, "HB10": {**rec, "bill": "HB10"}},
            "2027-2028": {"HB1001": {**rec, "bill": "HB1001", "year": "2027"}}}),
            encoding="utf-8")
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            added = BD.add_journal_bills(by_term, p)
        assert sorted(by_term) == ["2023-2024", "2025-2026"], (
            f"a journal record created a term: {sorted(by_term)}")
        assert by_term["2025-2026"]["HB10"] is mine and "journal" not in mine, (
            "a journal record was put over a bill the General Court's files carry")
        got = by_term["2025-2026"].get("HB476") or {}
        assert added == {"2025-2026": {"HB476": got}}, added
        assert (got.get("lsr"), got.get("lsr_num"), got.get("lsr_year"),
                got.get("house_committee"), got.get("designation")) == (
            "", "", "2025", "Judiciary", "HB 476-FN"), got
        assert got["journal"]["withdrawn"]["how"] == "motion", got.get("journal")
        assert "HB1001" in said.getvalue(), "a record left out was not named"
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            assert BD.add_journal_bills({"2025-2026": {}}, root / "absent.json") == {}
        assert "NO " in said.getvalue() and "journal_bills.py" in said.getvalue(), (
            "a missing journal_bills.json went unsaid")

        import text_sponsors as TS
        sat = TS.Sat([
            {"member_id": "10579", "name": "Peternel, Katy", "party": "R", "year": "2025",
             "body": "H", "label": "Rep. Katy Peternel (R - Carr 6)"},
            {"member_id": "10651", "name": "Seidel, Sheila", "party": "R", "year": "2025",
             "body": "H", "label": "Seidel, Sheila(R) Hillsborough 29"},
            {"member_id": "10620", "name": "Sellers, John", "party": "R", "year": "2025",
             "body": "H", "label": "Rep. John Sellers (R - Graf 10)"}])
        legs = {
            "10579": {"id": "10579", "name": "Peternel, Katy", "party_code": "R",
                      "chamber": "H", "county_abbr": "Carr", "district": "6",
                      "label": "Rep. Katy Peternel (R - Carr 6)"},
            "10620": {"id": "10620", "name": "Sellers, John", "party_code": "R",
                      "chamber": "H", "county_abbr": "Graf", "district": "10",
                      "label": "Rep. John Sellers (R - Graf 10)"}}
        rows = BD.journal_sponsor_rows(["Peternel, Carr. 6", "Seidel, Hills. 29",
                                        "Sellers, Graf. 18", "Nobody, Rock. 99"],
                                       "2025-2026", sat, legs)
        assert [r["member_id"] for r in rows] == ["10579", "10651", "10620", ""], rows
        assert [r["prime"] for r in rows] == [True, False, False, False], rows
        assert all(r["source"] == "House Journal" and r["prime_inferred"] for r in rows)
        assert [r["sequence"] for r in rows] == [0, 1, 2, 3]
        assert rows[1]["label"] == "Rep. Sheila Seidel (R - Hills 29)", rows[1]
        assert (rows[2]["label"], rows[2]["district"], rows[2]["as_printed"]) == (
            "Rep. John Sellers (R - Graf 10)", "10", "Sellers, Graf. 18"), rows[2]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("added into its term only, never over a docket bill, never a term of "
                  "its own; sponsors in the journal's order, seats from the roster")


# ---- the nightly ---------------------------------------------------------------

@check("build", "the daily snapshot stops when told no, and installs all of tonight's files or none",
       needs=("snapshot_gencourt",))
def _snapshot_stops(SG):
    """snapshot_gencourt.py is the one fetch meant to run every night unwatched.

    Until 12 September it retried every failure three times, a 403 included;
    took no lock; paused between nothing; saved whatever came back; and never
    put what it fetched where the build reads -- the build's Docket.txt was ten
    days old. Driven here on fake answers through its run(): one 403 ends it
    with nothing installed; the block page served as 200 is not stored; one
    broken file means none installed; a truncated Docket cannot replace a good
    one; under the nightly's lock it runs and leaves the lock alone.
    """
    import argparse
    import contextlib
    import io
    import time
    import types
    import urllib.error
    import refusal
    saved = (refusal.MARK, refusal.LOCK, SG.get, SG.time)
    n = len(SG.targets())
    data = b"2026|0001|12/4/2024 10:44:26 AM|SR1|S|Introduced and Adopted, VV\n" * 3
    tmps = []
    # The Dynamic Data Files page, which rebuilds the files when it is opened:
    # as it answers when all is well, and as it answered on 28 September.
    healthy = (b"<html><body><h1>DYNAMIC DATA FILES</h1><a href='LSRs.txt?x=20260930'>LSR "
               b"Table</a><br/><a href='Docket.txt?x=20260930'>Docket</a></body></html>")
    failed = (b"<html><body><h1>DYNAMIC DATA FILES</h1><span>Error Generating Members File : "
              b"Execution Timeout Expired.  The timeout period elapsed prior to completion of "
              b"the operation or the server is not responding.\r\nOperation cancelled by user."
              b"</span><br/><a href='LSRs.txt?x=20260928031030'>LSR Table</a></body></html>")
    page, seen = [healthy], {}

    def run(answers, installed=None, lock=None):
        tmp = Path(tempfile.mkdtemp())
        tmps.append(tmp)
        refusal.MARK, refusal.LOCK = tmp / "refused.json", tmp / ".lock"
        root = tmp / "root"
        root.mkdir()
        for name, body in (installed or {}).items():
            (root / name).write_bytes(body)
        if lock is not None:
            refusal.LOCK.write_text(str(lock))
        it, asked, order = iter(answers), [], []
        seen.update(order=order, arch=tmp / "arch")

        def fake(url, timeout=120):
            if url == SG.PAGE:
                order.append("page")
                if isinstance(page[0], BaseException):
                    raise page[0]
                return page[0]
            order.append("file")
            asked.append(url)
            a = next(it)
            if isinstance(a, BaseException):
                raise a
            return a
        SG.get = fake
        a = argparse.Namespace(dir=str(tmp / "arch"), into=str(root), allow_shrink=False,
                               delay=0.0, plan=False)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                refusal.check("t")
                with refusal.hold("t") as held:
                    rc = SG.run(a, held)
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
        return rc, asked, root

    try:
        SG.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time)
        rc, asked, root = run([data] * n)
        assert rc == 0 and len(asked) == n and (root / "Docket.txt").read_bytes() == data, rc
        rc, asked, root = run([data, urllib.error.HTTPError("u", 403, "no", {}, None)] + [data] * n)
        assert rc == 2 and len(asked) == 2 and refusal.MARK.exists(), (rc, len(asked))
        assert not any(root.iterdir()), "a refused night installed files"
        rc, asked, root = run([b"<h1>Web Page Blocked</h1> Attack ID: 3"] + [data] * n)
        assert rc == 2 and not any(root.iterdir()), rc
        rc, asked, root = run([data, b"<!DOCTYPE html><html>Server Error</html>"] + [data] * n)
        assert rc == 1 and not any(root.iterdir()) and not refusal.MARK.exists(), rc
        good = data * 50
        rc, asked, root = run([b"2026|1|x|HB1|H|short\n"] + [data] * n, installed={"Docket.txt": good})
        assert rc == 1 and (root / "Docket.txt").read_bytes() == good, "a truncated Docket replaced a good one"
        rc, asked, root = run([data] * n, lock=os.getppid())
        assert rc == 0 and refusal.LOCK.read_text() == str(os.getppid()), "the nightly's lock was disturbed"
        rc, asked, root = run([data] * n, lock=99999999)
        assert rc == 3 and not asked, rc

        # The page first, once, and what it said kept for the verdict; a page
        # reporting a failed rebuild does not stop the files; a refused page
        # stops everything, as a refused file does.
        def said():
            return json.loads(next(seen["arch"].glob("snapshots/*/page.json")).read_text(encoding="utf-8"))
        rc, asked, root = run([data] * n)
        assert rc == 0 and seen["order"][0] == "page" and seen["order"].count("page") == 1, seen["order"][:3]
        assert said()["status"] == "ok", said()
        page[0] = failed
        rc, asked, root = run([data] * n)
        assert rc == 0 and len(asked) == n and (root / "Docket.txt").read_bytes() == data, \
            "a page reporting a failed rebuild kept whole files from being installed"
        assert said()["status"] == "error" and said()["said"].startswith(
            "Error Generating Members File : Execution Timeout Expired."), said()
        page[0] = urllib.error.HTTPError("u", 403, "no", {}, None)
        rc, asked, root = run([data] * n)
        assert rc == 2 and not asked and refusal.MARK.exists() and not any(root.iterdir()), \
            "a refused page went on to ask for the files"
        page[0] = TimeoutError("timed out")
        rc, asked, root = run([data] * n)
        assert rc == 0 and said()["status"] == "slow" and (root / "Docket.txt").read_bytes() == data, \
            "a page slow to answer counted as a refusal, or kept the files from being taken"
        page[0] = healthy
        assert SG.page_said(healthy) == "", "a page with no error was read as reporting one"
        src = _source(_paths.locate("snapshot_gencourt.py"))
        m = re.search(r'"--delay", type=float, default=([\d.]+)', src)
        assert m and float(m.group(1)) >= 3, "the snapshot's pause between files fell under 3 s"
        return "ok", ("the page first, its error kept and the files still taken; one 403 stops it, "
                      "block page and broken files not stored, all-or-none install, shrink guard, "
                      "nightly lock respected")
    finally:
        refusal.MARK, refusal.LOCK, SG.get, SG.time = saved
        for t in tmps:
            shutil.rmtree(t, ignore_errors=True)


@check("build", "no fact of 2025-2026 reaches a 2027 bill by its number: the sign-ins are the "
       "database's by term, the Legislation fill keeps to the bill's own term, and titles are "
       "read by term", needs=("build_data", "build_site_v2", "build_all", "testimony_from_db"))
def _no_leak_by_number(BD, BSV, BA, TF):
    """The three leaks of 2025-2026 onto 2027 bills the design found
    (private/NEW_TERM_DESIGN.md, 5 October 2026), each a file or a join keyed
    on the bill number alone: testimony.json, 565 bills read by number for
    the current term (retired, at the person's word, once every count the
    site showed was shown to be testimony_db.json's); the db/Legislation.psv
    fill, which joined on number and LSR and ignored the session year (0 to 5
    bills share both between consecutive terms); and bill_titles.json, read
    by number when it is there. And the sign-ins stay retrievable: a finished
    term's are rebuilt from its freeze."""
    src = _source(BSV.__file__)
    assert not re.search(r'load\(\s*"testimony\.json"', src), "build_site_v2 reads testimony.json"
    kit = _source("cloud_kit.json")
    assert '"testimony.json"' not in kit, "the kit still carries testimony.json"
    bd = _source(BD.__file__)
    assert "P.term_of(f[2].strip()) != P.term_of(str(rec.get(\"lsr_year\") or \"\"))" in bd, \
        "the Legislation fill no longer keeps to the bill's own term"
    assert "if P.term_keyed(_titles):" in bd, "bill_titles.json is read by number again"
    assert hasattr(TF, "frozen_terms") and "only" in _source(TF.__file__), \
        "testimony_from_db no longer rebuilds a finished term from its freeze"
    return "ok", ("testimony.json read by nothing and carried by no kit; the Legislation fill by "
                  "term; bill_titles.json by term or not at all; a finished term's sign-ins from "
                  "its freeze")


@check("build", "a database night takes a changed roster when tonight's Members.txt names it, "
       "and stops on one it does not", needs=("dayfiles_from_db",))
def _db_roster_named(DF):
    """Organization Day seats a new House, and from that day the database's
    roster is past every ceiling of the database night's guards: every such
    night would stop until an export installed it. The person decided on
    5 October 2026 that the night may take it when tonight's Members.txt --
    the website's, which arrives when the export does not -- names the same
    people. A third of the roster new: stopped on with the old Members.txt,
    taken with the new, and the joined and the left are named either way."""
    def leg(i, last, mail):
        return f"{i}|{last}|Pat||H|{1000 + i}|06|{i % 9 + 1}|R||1 Main St|Concord|NH|03301|{mail}"
    old = [leg(i, f"Old{i}", f"old{i}@gc.nh.gov") for i in range(30)]
    new = [leg(900 + i, f"New{i}", f"new{i}@gc.nh.gov") if i % 3 == 0 else old[i]
           for i in range(30)]
    head = "LastName\tFirstName\tWorkEmail\telectedStatus"

    def members(rows):
        return (head + "\n" + "\n".join(
            f"{f[1]}\t{f[2]}\t{f[14]}\tIncumbent" for f in (r.split("|") for r in rows))).encode()
    assert DF._hold_roster(old, new)[0], "a third of the House new was not stopped on"
    stops, held, told = DF._hold_roster(old, new, True)
    assert not stops and held["joined"] == 10 and held["left"] == 10 and \
        any("not on the database's roster" in k for k in told), (stops, held, told)
    ok, why = DF.roster_named(new, members(new))
    assert ok, why
    ok, why = DF.roster_named(new, members(old))
    assert not ok and "does not name 10" in why, why
    assert not DF.roster_named(new, None)[0]
    # Five people more than the roster is a Members.txt of another roster.
    extra = [leg(950 + i, f"Extra{i}", f"extra{i}@gc.nh.gov") for i in range(5)]
    ok, why = DF.roster_named(new, members(new + extra))
    assert not ok and "names 5 people" in why, why
    ok, why = DF.roster_named(new, members(new + extra[:4]))
    assert ok, why
    # THROUGH judge(), AND ONLY OVER THE TERM'S FROZEN ROSTER (the review of 5
    # October 2026): the term is still the session's, and its members are
    # named from its own frozen roster once the installed one is not it.
    empty = {n: [] for n in DF.DAY_FILES}
    for frozen, taken in ((True, True), (False, False)):
        r = DF.judge({**empty, "legislators.txt": new}, {**empty, "legislators.txt": old},
                     {"members": members(new), "roster_frozen": frozen})
        roster_stops = [s for s in r["stops"] if "roster" in s or "legislators.txt" in s]
        assert (not roster_stops) == taken and \
            (taken or any("not frozen" in s for s in roster_stops)), (frozen, r["stops"])
    # ... and with nothing said, asked of the folder the night installs into.
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-dbroster-"))
    try:
        os.chdir(tmp)
        Path("Docket.txt").write_text("2026|0001|1/7/2026 10:00:00 AM|HB1|H|Introduced|x\n",
                                      encoding="utf-8")
        for frozen in (False, True):
            if frozen:
                (Path("frozen") / "2025-2026" / "day").mkdir(parents=True)
                (Path("frozen") / "2025-2026" / "day" / "legislators.txt").write_text(
                    "\n".join(old) + "\n", encoding="utf-8")
            r = DF.judge({**empty, "legislators.txt": new}, {**empty, "legislators.txt": old},
                         {"members": members(new)})
            roster_stops = [s for s in r["stops"] if "roster" in s or "legislators.txt" in s]
            assert (not roster_stops) == frozen, ("asked of the folder", frozen, r["stops"])
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a third of the roster new stops a database night unless tonight's Members.txt "
                  "names it, and no more than four people besides, and the term's own roster is "
                  "frozen; then its joined and left are named")

# The export of the same state, as it would be installed. In another order
# than the views give, as the real one is; the docket's seventh column is when
# a row was last changed, which the view does not carry; and SB 416's Senate
# status code differs, as 29 bills' do in every real export.
#
# SB 532 as the two sources had it on 2 October 2026, for a bill record the
# installed file does not hold yet: one of the 29. The Senate killed it 16-8
# on 19 February; the export says 09, INEXPEDIENT TO LEGISLATE, and the view
# 02, IN COMMITTEE.
_DBDAY_SB532_VIEW = (
    "0532|SB|2026|2136|increasing the requirements of the education freedom savings account "
    "oversight committee and modifying the purpose of the committee.|True|S|2|False|False|False|"
    "26-2136|STG|SB  0532|SB532|11/21/2025 14:39:00||R||||||||0|S05|S05|01/07/2026 00:00:00|02|"
    "05/08/2026||02/19/2026 00:00:00|0|03||||False|PublicNHLMS||8|S05|02/10/2026 09:15:00|"
    "SL Room Map Room|False|NHLMS|1327")
_DBDAY_SB532_EXPORT = (
    "2026|2136|increasing the requirements of the education freedom savings account oversight "
    "committee and modifying the purpose of the committee.|S|2|0|0|0|26-2136|SB  0532|SB532||STG|"
    "|||||||0|S05|S05|1/7/2026 12:00:00 AM|09|05/08/2026||2/19/2026 12:00:00 AM|0|03|S05|"
    "2/10/2026 9:15:00 AM|SL Room Map Room||||0|0|")


@check("build", "the day's seven changing files are rebuilt from the database's views in the "
       "export's shapes and the installed file's order, all seven or none, asking nobody",
       needs=("dayfiles_from_db",))
def _dayfiles_rebuild(DF):
    """dayfiles_from_db.py, on a fixture of a few rows per view and the
    export's lines for the same state, written here by hand from real rows:

      - each of the seven comes out as the export has it: dates the export's
        way, a chapter padded, a bit as 1 or 0, a senator's two address lines
        the other way round, county and district without leading zeros, the
        ballot as a word and the member by PersonID, sponsors only once signed
        off, and LsrsOnly only for a sitting member on this session's request
      - rows of another session year, and a member who has left, stay out
      - LSRs.txt's Senate status code is never the view's, which has it wrong
        on 29 real bills: the installed file's for a bill record it holds,
        none for a new one
      - the order is the installed file's for every row both hold, whatever
        order the views came in, and a new row goes after them; a row gone
        from the view is gone; a docket row the clerk reworded keeps its
        place, as it does in the export
      - a view that wrote more rows than the server had counted is whole, and
        said: a row entered while it was read
      - a newer session year in the views is left out and said, not built
      - all seven or none: a view missing, cut short, a line of the wrong
        width, an error or a short count in source.json, a view that is not
        UTF-8 or begins with a byte-order mark, or no installed file to take
        the years from, is a Problem and writes nothing; and nothing is
        written when a guard fires
      - it asks nobody: its command runs sealed from the network
    """
    here = Path(".").resolve()
    tmp = Path(tempfile.mkdtemp(prefix="gr-dayfiles-"))
    try:
        root, views = tmp / "root", tmp / "root" / ".night" / "dbday"
        _dbday_install(root)
        _dbday_views(DF, views)
        files, facts = DF.rebuild(views, root)
        want = _dbday_expected()
        for name in DF.DAY_FILES:
            got = files[name].decode("utf-8-sig").split("\r\n")
            assert files[name].startswith(b"\xef\xbb\xbf") and got[-1] == "", \
                f"{name} is not written as the export writes a file"
            assert got[:-1] == want[name], (
                f"{name} rebuilt from the views is not the export's:\n"
                + "\n".join(f"  got  {a}\n  want {b}" for a, b in zip(got, want[name]) if a != b)[:900]
                + f"\n  ({len(got) - 1} rows, {len(want[name])} wanted)")
        for name in ("LSRs.txt", "LsrSponsors.txt", "LsrsOnly.txt", "legislators.txt",
                     "RollCallSummary.txt", "RollCallHistory.txt"):
            assert files[name] == (root / name).read_bytes(), f"{name} is not byte-identical"
        assert facts["senate_status"] == {"kept": 1, "blank": 0}, (
            "SB 416's Senate status code is 11 in the view and 12 installed, and the rebuilt "
            f"file did not keep the installed one, or did not say so: {facts.get('senate_status')}")
        assert facts["years"] == {"docket": ["2025", "2026"], "session": ["2026"],
                                  "sponsors": ["2026"], "rollcalls": ["2026"]}, facts["years"]
        assert all(o["new"] == 0 for o in facts["order"].values()) and not facts["newer_years"], facts
        sc = DF.scope(DF.installed_files(root))
        assert sc["ask"] == {"Docket": "2025", "Legislation": "2026", "Sponsors": "2026",
                             "RollCallSummary": "2026", "RollCallHistory": "2026"}, sc["ask"]
        result = DF.judge(files, DF.installed_files(root), facts)
        assert not result["stops"] and not result["warnings"], result
        assert all(d["new"] == 0 and d["gone"] == 0 for d in result["differences"].values()), (
            "the fixture's two sources show one state, and a difference was counted on the "
            f"columns both carry: {result['differences']}")
        assert DF.lookup_notes(views, root) == [], DF.lookup_notes(views, root)

        # New rows go after the rows both hold; a row gone from the view is
        # gone; a newer year is left out and said.
        more = dict(_DBDAY_VIEWS)
        more["Docket"] = _DBDAY_VIEWS["Docket"] + [
            "2026|10||09/30/2026 09:00:00|HB54|S|Interim Study Report: Not Recommended|NHLMS|15|"
            "01/01/2200 00:00:00|99000000",
            "2026|10||09/29/2026 16:00:00|HB54|S|Committee Report filed|NHLMS|15|"
            "01/01/2200 00:00:00|98000000",
            "2027|5||01/06/2027 10:00:00|HB1|H|Introduced|NHLMS|2000|01/01/2200 00:00:00|5"]
        more["Legislators"] = _DBDAY_VIEWS["Legislators"] + [
            "104|Gum|Gil|300104||H|True|2045|05|07|R||2 Example Street||Keene|03431|NH|"
            "gil.gum@example.gov|M||NHLMS"]
        more["Legislation"] = _DBDAY_VIEWS["Legislation"] + [_DBDAY_SB532_VIEW]
        _dbday_views(DF, views, more)
        files2, facts2 = DF.rebuild(views, root)
        # A bill record the installed file does not hold is the export's own
        # line in every column but the Senate status code, where the view
        # says 02 of a bill the Senate killed: written with none.
        records = files2["LSRs.txt"].decode("utf-8-sig").split("\r\n")[:-1]
        sb532 = _DBDAY_SB532_EXPORT.split("|")
        assert sb532[24] == "09" and _DBDAY_SB532_VIEW.split("|")[29] == "02"
        assert records[:3] == want["LSRs.txt"] and records[3:] == [
            "|".join(sb532[:24] + [""] + sb532[25:])], (
            f"a new bill record is not the export's line with no Senate status code: {records[3:]}")
        assert facts2["senate_status"] == {"kept": 1, "blank": 1}, facts2["senate_status"]
        docket = files2["Docket.txt"].decode("utf-8-sig").split("\r\n")[:-1]
        kept = want["Docket.txt"]
        assert docket[:len(kept)] == kept and [ln.split("|")[5] for ln in docket[len(kept):]] == [
            "Committee Report filed", "Interim Study Report: Not Recommended"], (
            "new docket rows are not after the installed ones, in the view's statusorder: "
            f"{docket[-3:]}")
        assert facts2["order"]["Docket.txt"] == {"placed": 8, "new": 2}, facts2["order"]
        assert facts2["newer_years"] == {"Docket": {"2027": 1}} and not any(
            ln.startswith("2027") for ln in docket), "a newer session year was built, or not seen"
        people = files2["legislators.txt"].decode("utf-8-sig").split("\r\n")[:-1]
        assert people[:4] == want["legislators.txt"] and people[4].startswith("104|Gum|Gil||H|2045|5|7|"), people
        result2 = DF.judge(files2, DF.installed_files(root), facts2)
        assert any("2027" in w for w in result2["warnings"]) and \
            not any("2027" in s for s in result2["stops"]), result2
        assert result2["differences"]["Docket.txt"] == {"rows": 10, "installed": 8, "new": 2,
                                                        "gone": 0}, result2["differences"]
        # A row gone from the view is gone from the file.
        _dbday_views(DF, views, {"Docket": [r for r in _DBDAY_VIEWS["Docket"]
                                            if "Public Hearing" not in r]})
        files3, _ = DF.rebuild(views, root)
        assert files3["Docket.txt"].decode("utf-8-sig").split("\r\n")[:-1] == [
            ln for ln in want["Docket.txt"] if "Public Hearing" not in ln], \
            "a row gone from the view was kept, or the rest changed order"

        # A row the clerk rewords keeps its place, as it does in the export:
        # between 6 and 15 September HB 1218's amendment number was corrected
        # and the row stayed 18,982nd of 25,313. On the six columns it is a
        # row gone and a row new, and it used to be sent to the end. A row
        # entered at the same second as one that is still there takes
        # nobody's place.
        reworded = [r.replace("LOB 210-211", "LOB 201-203") for r in _DBDAY_VIEWS["Docket"]]
        assert sum(a != b for a, b in zip(reworded, _DBDAY_VIEWS["Docket"])) == 1
        _dbday_views(DF, views, {"Docket": reworded + [
            "2026|10||02/19/2025 10:47:54|HB54|H|  Executive Session: continued|NHLMS|15|"
            "01/01/2200 00:00:00|10050001"]})
        files4, facts4 = DF.rebuild(views, root)
        docket = files4["Docket.txt"].decode("utf-8-sig").split("\r\n")[:-1]
        assert docket[:-1] == [ln.replace("LOB 210-211", "LOB 201-203")
                               for ln in want["Docket.txt"]], (
            "a reworded docket row did not keep the installed row's place: "
            f"{[ln.split('|')[5][:40] for ln in docket]}")
        assert docket[-1].split("|")[5] == "  Executive Session: continued" and \
            facts4["order"]["Docket.txt"] == {"placed": 8, "new": 1}, (docket[-1], facts4["order"])
        assert DF.judge(files4, DF.installed_files(root), facts4)["differences"]["Docket.txt"] == {
            "rows": 9, "installed": 8, "new": 2, "gone": 1}, \
            "a reworded row is no longer counted as a row gone and a row new"
        assert set(DF.ORDER_LOOSE) == {"Docket.txt"}, \
            "another file's rows are placed by a looser key, and the archive shows no edit in one"

        # More rows than the server counted a moment before is a row entered
        # while the view was being read: it is the view, and the night says
        # so. Fewer is a view cut short (below).
        _dbday_views(DF, views, entries={"Docket": {"count": 8, "rows": 9}})
        files5, facts5 = DF.rebuild(views, root)
        result5 = DF.judge(files5, DF.installed_files(root), facts5)
        assert files5 == files and facts5["entered"] == {"Docket": 1} and not facts["entered"], \
            (facts5.get("entered"), facts.get("entered"))
        assert not result5["stops"] and len(result5["warnings"]) == 1 and \
            "1 row more than the server had counted" in result5["warnings"][0] and \
            "Docket view" in result5["warnings"][0], result5
        assert DF.arrived_whole(9, 9) and DF.arrived_whole(0, 0) and DF.arrived_whole(8, 9) and \
            not DF.arrived_whole(9, 8) and not DF.arrived_whole(None, 9) and \
            not DF.arrived_whole(9, None) and not DF.arrived_whole(True, True)

        # A lookup the database disagrees with is a note, and one the export
        # holds more of is not.
        _dbday_views(DF, views, {"Subject": _DBDAY_VIEWS["Subject"] + [
            "4|6|L|Animals|0|1|ANI|True|10/23/2014 00:00:00"], "County": None})
        (views / "County.psv").unlink(missing_ok=True)
        notes = DF.lookup_notes(views, root)
        assert len(notes) == 2 and notes[0].startswith("SubjectCodes.txt differs") and \
            notes[1].startswith("Counties.txt was not compared"), notes

        # All seven or none.
        def problem(what, **kw):
            shutil.rmtree(views, ignore_errors=True)
            _dbday_views(DF, views, **kw)
            try:
                DF.rebuild(views, root)
            except DF.Problem:
                return
            raise AssertionError(f"{what}, and the seven files were rebuilt all the same")
        problem("a view was missing", views={"Sponsors": None})
        problem("a view's line was a column short",
                views={"Docket": _DBDAY_VIEWS["Docket"] + ["2026|10||x|HB54|H|short"]})
        problem("source.json recorded an error for a view",
                entries={"Legislation": {"error": "QUERY_FAIL Execution Timeout Expired", "rows": None}})
        problem("a view wrote fewer rows than the server counted",
                entries={"RollCallHistory": {"count": 9, "rows": 6}})
        problem("there was no source.json", source=False)
        # A view that is not UTF-8 is not read at all. Every byte that would
        # not decode used to be replaced, and a set of views in Windows-1252
        # was installed with U+FFFD in fifteen titles and two members' names,
        # each count under its ceiling. And one that begins with a byte-order
        # mark is not the file fetch_day_db.py wrote: the mark stayed on the
        # first row's first field and took that row out of its year.
        accent = "\r\n".join(_DBDAY_VIEWS["Legislators"]).replace("Cedar", "C" + chr(0xE9) + "dar")
        for what, raw, words in (
                ("a view was written in Windows-1252", accent.encode("cp1252"),
                 "Legislators.psv is not UTF-8 (byte 4 is 0xe9)"),
                ("a view began with a byte-order mark",
                 bytes([0xEF, 0xBB, 0xBF]) + accent.encode("utf-8"),
                 "Legislators.psv begins with a byte-order mark")):
            shutil.rmtree(views, ignore_errors=True)
            _dbday_views(DF, views)
            (views / "Legislators.psv").write_bytes(raw)
            try:
                DF.rebuild(views, root)
                raise AssertionError(f"{what}, and the seven files were rebuilt all the same")
            except DF.Problem as e:
                assert words in str(e), f"{what}, and the reason given was: {e}"
        (views / "Legislators.psv").write_bytes(accent.encode("utf-8"))
        assert ("|C" + chr(0xE9) + "dar|Cy|").encode("utf-8") in DF.rebuild(views, root)[0][
            "legislators.txt"], "a name with an accent, in UTF-8, was not carried through"
        shutil.rmtree(views, ignore_errors=True)
        _dbday_views(DF, views)
        (root / "LSRs.txt").rename(root / "LSRs.txt.away")
        try:
            DF.rebuild(views, root)
            raise AssertionError("the files were rebuilt with no installed LSRs.txt to take the "
                                 "session year from")
        except DF.Problem:
            pass
        (root / "LSRs.txt.away").rename(root / "LSRs.txt")

        # The command: sealed from the network, it writes all seven; and when
        # a guard fires -- a bill gone from the docket -- it writes none.
        out = tmp / "out"
        with _Seal() as seal:
            r = seal.run([sys.executable, _paths.script("dayfiles_from_db.py"), "--views", str(views),
                          "--installed", str(root), "--out", str(out)],
                         capture_output=True, text=True, timeout=300, cwd=str(tmp))
            assert r.returncode == 0 and "every guard passed" in r.stdout, (r.stdout + r.stderr)[-400:]
            assert sorted(p.name for p in out.iterdir()) == sorted(DF.DAY_FILES), \
                sorted(p.name for p in out.iterdir())
            assert all((out / n).read_bytes() == files[n] for n in DF.DAY_FILES), \
                "the command wrote other bytes than rebuild() makes"
            shutil.rmtree(out)
            _dbday_views(DF, views, {"Docket": [r for r in _DBDAY_VIEWS["Docket"] if "SB416" not in r]})
            r = seal.run([sys.executable, _paths.script("dayfiles_from_db.py"), "--views", str(views),
                          "--installed", str(root), "--out", str(out)],
                         capture_output=True, text=True, timeout=300, cwd=str(tmp))
            assert r.returncode == 1 and "STOP:" in r.stdout and not out.exists(), (
                "a guard fired and the command wrote files, or did not say so: "
                + (r.stdout + r.stderr)[-400:])
        assert not list(tmp.rglob("*.part")), "a half-written file was left behind"
        src = _source(_paths.locate("dayfiles_from_db.py"))
        assert not re.search(r"^\s*(?:import|from)\s+(?:urllib|socket|http|subprocess|probe_db|"
                             r"refusal|child)\b", src, re.M), \
            "dayfiles_from_db.py imports something that could ask the network"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a fixture's six views make the export's seven files line for line, in the "
                  "installed order with new rows last; another year and a member who has left "
                  "stay out; a missing, short or failed view is a Problem and writes nothing; "
                  "the command runs sealed and writes none when a guard fires")


def _dbday_bulk():
    """Seven day files big enough for a guard's percentage to mean something:
    {name: [lines]}. 400 docket rows on 40 bills and one bill with a single
    row, 41 bill records, 100 members, 150 sponsors, 5 roll calls of 100
    ballots."""
    docket = []
    for b in range(1, 41):
        for k in range(1, 11):
            when = f"{1 + (b % 9)}/{k}/2026 9:{b:02d}:00 AM"
            docket.append(f"2026|{b:04d}|{when}|HB{1000 + b}|H|Event {k} of HB{1000 + b}|{when}")
    docket.append("2026|0999|1/2/2026 8:00:00 AM|HB1999|H|Introduced|1/2/2026 8:00:00 AM")
    docket.append("2026|0040|9/29/2026 4:00:00 PM|HB1040|H|The newest entry|9/29/2026 4:00:01 PM")
    lsrs = ["|".join(["2026", f"{b:04d}", f"title {b}", "H", "1", "0", "0", "0", f"26-{b:04d}",
                      f"HB  {1000 + b}", f"HB{1000 + b}"] + [""] * 28)
            for b in list(range(1, 41)) + [999]]
    sponsors = [f"2026|{1 + i % 40}|{1 + i // 40}|{500 + i % 100}|{1 if i < 40 else 0}"
                for i in range(150)]
    only = [f"26-{1 + i % 40:04d}|{500 + i % 100}|{9000 + i % 40}|2026|"
            f"{'Prime' if i < 40 else 'Sponsor'}|HB{1001 + i % 40}|H|title {1 + i % 40}"
            for i in range(150)]
    people = ["|".join([str(500 + i), f"Last{i}", f"First{i}", "", "H" if i < 76 else "S",
                        str(3000 + i), "1", str(1 + i % 20), "R" if i % 2 else "D", "1 Street",
                        "", "Concord", "NH", "03301", f"m{i}@example.gov"]) for i in range(100)]
    summary = [f"2026|H|{n}|1/{n}/2026 10:00:00 AM|HB{1000 + n}|60|30|5|5|||Ought to Pass|t||"
               for n in range(1, 6)]
    history = [f"2026|H|{n}|{70000 + i}|{500 + i}|HB{1000 + n}|{'Yea' if i < 60 else 'Nay'}|"
               for n in range(1, 6) for i in range(100)]
    return {"Docket.txt": docket, "LSRs.txt": lsrs, "LsrSponsors.txt": sponsors,
            "LsrsOnly.txt": only, "legislators.txt": people, "RollCallSummary.txt": summary,
            "RollCallHistory.txt": history}


@check("build", "each guard on a database night's files fires on a doctored input, and none "
       "fires on a day that only grew", needs=("dayfiles_from_db",))
def _dayfiles_guards(DF):
    """dayfiles_from_db.judge(): tonight's rebuilt files against the installed
    ones, on the columns both sources carry. A guard that fires stops the
    fallback and nothing is installed, so each is tried here on files doctored
    to trip it and it alone, and at its threshold from both sides:

      the view is behind                 its newest docket entry is older
      the docket lost rows               more than 5 of the installed rows,
                                         none of them reworded
      a bill is gone from the docket     though it is one row
      a bill record is gone              one (year, LSR)
      a roll call is gone, or has fewer ballots; three have other counts
      the roster moved more than 2%      either way, or that share of its
                                         members replaced with the count the
                                         same
      LsrSponsors.txt lost rows          more than 5 of them
      LsrsOnly.txt lost a sponsor        one row of a member still sitting,
                                         on a numbered bill; or more than 2%
                                         of their rows, with no bill number
      a line of the wrong width, or a file with no rows

    And a day that only grew -- new docket rows, a new roll call with its
    ballots, a new member, a sponsor -- trips none; a newer session year in
    the views is a warning and no stop; and so is a member who has left the
    roster and taken their rows of LsrsOnly.txt with them, however many they
    were. What a night lets through under a ceiling that is a guess it says
    in a warning, by how many, and names in "told".
    """
    base = _dbday_bulk()
    installed = {n: _dbday_bytes(v) for n, v in base.items()}

    def stops(name, lines):
        return DF.judge(dict(installed, **{name: _dbday_bytes(lines)}), installed)["stops"]

    same = DF.judge(installed, installed)
    assert (same["stops"], same["warnings"]) == ([], []) and same["differences"] == {
        n: {"rows": len(v), "installed": len(v), "new": 0, "gone": 0}
        for n, v in base.items()}, "the same files were not judged the same"

    def only(got, word, what):
        assert len(got) == 1 and word in got[0], f"{what}: the guards said {got}"

    NAMED = "each named in the night's verdict (day_files, told) and in its what-changed report"
    d = base["Docket.txt"]
    only(stops("Docket.txt", d[:-1]), "is behind", "the newest docket row was dropped")
    # One row of each of 5 bills, and then of 6: no bill goes, no row is
    # reworded, and the newest stays. The five are let through and named.
    got = DF.judge(dict(installed, **{"Docket.txt": _dbday_bytes(
        [ln for i, ln in enumerate(d) if i % 10 or i >= 50])}), installed)
    assert not got["stops"], f"5 docket rows gone, the most allowed, stopped the night: {got['stops']}"
    assert got["warnings"] == [f"Docket.txt: installed rows gone: 5, {NAMED}"] and \
        got["told"] == {"Docket.txt: installed rows gone": [
            "|".join(d[i].split("|")[:6]) for i in range(0, 50, 10)]}, (got["warnings"], got["told"])
    only(stops("Docket.txt", [ln for i, ln in enumerate(d) if i % 10 or i >= 60]),
         "6 installed rows are not in the database's, more than 5",
         "6 docket rows were dropped")
    only(stops("Docket.txt", [ln for ln in d if "HB1999" not in ln]), "bills in the installed docket",
         "a bill's only docket row was dropped")
    # The same rows with another seventh column are the same rows: the
    # database does not carry it.
    assert not stops("Docket.txt", ["|".join(ln.split("|")[:6] + [ln.split("|")[2]]) for ln in d]), \
        "the docket's seventh column was compared"
    only(stops("LSRs.txt", base["LSRs.txt"][1:]), "bill records installed",
         "a bill record was dropped")
    s = base["RollCallSummary.txt"]
    # (Its hundred ballots are then on a roll call the summary does not hold.)
    got = stops("RollCallSummary.txt", s[:-1])
    assert len(got) == 2 and "1 roll calls installed are not in the database's: 2026 H 5" in got[0] \
        and "100 ballots are on a roll call RollCallSummary.txt does not hold" in got[1], got
    # A tally the clerk corrects is one or two, and named; three stop. (That
    # it may not move away from its ballots is tried on real rows, in the
    # check after this one: these 100 ballots are 60 to 40 under a tally of
    # 60 to 30, before and after.)
    label = "RollCallSummary.txt: installed roll calls with other counts (Yeas-Nays-Present-Absent)"
    got = DF.judge(dict(installed, **{"RollCallSummary.txt": _dbday_bytes(
        s[:-1] + [s[-1].replace("|60|30|", "|61|29|")])}), installed)
    assert not got["stops"] and got["told"] == {label: ["2026 H 5 60-30-5-5 now 61-29-5-5"]} and \
        got["warnings"] == [f"{label}: 1, {NAMED}"] and \
        got["held"]["roll calls"]["counts"] == 1, (got["stops"], got["told"], got["warnings"])
    only(stops("RollCallSummary.txt", [ln.replace("|60|30|", "|61|29|") for ln in s[:3]] + s[3:]),
         "3 roll calls have other counts in the database, more than 2: 2026 H 1 60-30-5-5 now "
         "61-29-5-5", "three roll calls' counts were changed")
    # A clerk's correction moves a roll call to another bill and keeps its counts.
    assert not stops("RollCallSummary.txt", s[:-1] + [s[-1].replace("HB1005", "HB1006")]), \
        "a roll call moved to another bill, with the same counts, stopped the night"
    h = base["RollCallHistory.txt"]
    only(stops("RollCallHistory.txt", h[1:]), "fewer ballots", "a ballot was dropped")
    p = base["legislators.txt"]
    assert not stops("legislators.txt", p[:-2]), "a roster 2% smaller stopped the night"
    only(stops("legislators.txt", p[:-3]), "the roster is 97", "the roster lost 3 of 100")
    extra = [ln.replace("|Last", "|New", 1).replace(ln.split("|")[0], str(900 + i), 1)
             for i, ln in enumerate(p[:3])]
    only(stops("legislators.txt", p + extra), "the roster is 103", "the roster gained 3 of 100")
    # By who is on it as well as by how many: the same count of other people
    # is not the same roster.
    assert not stops("legislators.txt", p[:-2] + extra[:2]), \
        "two members of 100 replaced, the count the same, stopped the night"
    only(stops("legislators.txt", p[:-3] + extra), "3 of the 100 members installed are not on",
         "three members of 100 were replaced, the count the same")
    name = "LsrSponsors.txt"
    assert not stops(name, base[name][5:]), f"{name} losing 5 rows, the most allowed, stopped the night"
    only(stops(name, base[name][6:]), "LsrSponsors.txt: 6 installed rows are not in the "
         "database's, more than 5: 2026|1|1|500|1", f"{name} lost 6 of 150")
    # LsrsOnly.txt: a row of a sitting member on a numbered bill is a sponsor
    # on a bill's page, and one gone stops the night. The 2% that may go is
    # for rows with no bill number -- what the Legislation view does not
    # carry (two requests, 13 rows of the real file) and build_data skips. It
    # was 2% of every row, which let the sponsors of ten bills go unremarked.
    # (The ten rows without a number are made for this, in the real ones' shape.)
    bare = [f"26-{2012 + b}|{500 + b}|{9500 + b}|2026|Sponsor||H|a request with no bill number"
            for b in range(10)]
    with_bare = base["LsrsOnly.txt"] + bare
    had = dict(installed, **{"LsrsOnly.txt": _dbday_bytes(with_bare)})

    def only_stops(lines):
        return DF.judge(dict(had, **{"LsrsOnly.txt": _dbday_bytes(lines)}), had)["stops"]
    only(only_stops(with_bare[1:]), "LsrsOnly.txt: 1 installed rows of members still sitting, each "
         "on a numbered bill, are not in the database's: 26-0001|500|9000|2026|Prime|HB1001|H",
         "one sponsor of a numbered bill was dropped")
    assert not only_stops(with_bare[:-3]), \
        "3 of 160 rows gone, each with no bill number, under 2%, stopped the night"
    only(only_stops(with_bare[:-4]), "LsrsOnly.txt: 4 installed rows with no bill number are not "
         "in the database's, more than 2% of the 160 rows", "4 rows with no bill number were dropped")
    # It lists sitting members only, so a member who leaves takes their rows
    # out of it, in the export as in the views. Three members each hold more
    # than 2% of the real file, and held to 98% of ALL its rows one of them
    # resigning stopped the fallback for as long as the export stayed down.
    # It is held to the rows of the members still sitting, and the night says
    # who went.
    busy = base["LsrsOnly.txt"] + [f"26-{b:04d}|500|{9000 + b}|2026|Sponsor|HB{1000 + b}|H|title {b}"
                                   for b in range(41, 47)]
    had = dict(installed, **{"LsrsOnly.txt": _dbday_bytes(busy)})
    without = [ln for ln in busy if ln.split("|")[1] != "500"]
    assert len(busy) - len(without) == 8 > (1 - DF.SPONSORS_KEPT_LEAST) * len(busy)

    def after(only_lines):
        return DF.judge(dict(had, **{"legislators.txt": _dbday_bytes(p[1:]),
                                     "LsrsOnly.txt": _dbday_bytes(only_lines)}), had)
    gone = after(without)
    assert not gone["stops"], ("a member with 8 of LsrsOnly.txt's 156 rows left the roster, "
                               f"and the fallback stopped: {gone['stops']}")
    assert gone["warnings"] == [
        "1 member installed is not on the database's roster, and 8 rows of LsrsOnly.txt went "
        "with them",
        f"legislators.txt: installed members not on the database's roster: 1, {NAMED}"] and \
        gone["told"] == {"legislators.txt: installed members not on the database's roster": [
            "member 500, Last0|First0||H|1|1|D"]}, (gone["warnings"], gone["told"])
    only(after(without[1:])["stops"], "LsrsOnly.txt: 1 installed rows of members still sitting",
         "a member left, and a row of a member still sitting went as well")
    got = stops("Docket.txt", d[:-1] + ["2026|0040|9/30/2026 9:00:00 AM|HB1040|H|a column short"])
    assert any("do not have 7 columns" in x for x in got), got
    got = stops("RollCallHistory.txt", [])
    assert any("gave no rows" in x for x in got), got

    # A DAY THAT ONLY GREW: a docket row, a roll call with the ballots its
    # counts say, a member, and a sponsor on a bill made the day before.
    sixth = [f"2026|H|6|{70000 + i}|{500 + i}|HB1006|{'Yea' if i < 50 else 'Nay'}|"
             for i in range(90)]
    made = ["2026|0041|9/29/2026 9:00:00 AM|HB1041|H|Introduced|x",
            "2026|0040|9/30/2026 9:00:00 AM|HB1040|H|Newer|x"]
    record = "|".join(["2026", "0041", "title 41", "H", "1", "0", "0", "0", "26-0041",
                       "HB  1041", "HB1041"] + [""] * 28)
    grown = DF.judge(dict(
        installed,
        **{"Docket.txt": _dbday_bytes(d + made), "LSRs.txt": _dbday_bytes(base["LSRs.txt"] + [record]),
           "RollCallSummary.txt": _dbday_bytes(s + ["2026|H|6|9/30/2026 10:00:00 AM|HB1006|50|40|5|"
                                                    "5|||Ought to Pass|t||"]),
           "RollCallHistory.txt": _dbday_bytes(h + sixth),
           "legislators.txt": _dbday_bytes(p + extra[:1]),
           "LsrSponsors.txt": _dbday_bytes(base["LsrSponsors.txt"] + ["2026|41|1|500|1"])}),
        installed, {"newer_years": {"Docket": {"2027": 3}}, "asked": "2026-10-01T05:00:00"})
    assert not grown["stops"], f"a day that only grew was stopped: {grown['stops']}"
    assert len(grown["warnings"]) == 2 and "2027" in grown["warnings"][1] and grown["warnings"][0] \
        == f"legislators.txt: members on the database's roster and not the installed one: 1, {NAMED}", \
        grown["warnings"]
    assert grown["differences"]["Docket.txt"]["new"] == 2 and \
        grown["differences"]["RollCallHistory.txt"]["new"] == 90 and \
        grown["held"]["roll calls"] == {"calls": 0, "counts": 0, "ballots": 0, "new": 1,
                                        "strangers": 0, "unsummed": 0} and \
        grown["held"]["LsrSponsors.txt"] == {"new": 1, "late": 0, "gone": 0}, (
            grown["differences"], grown["held"])
    assert (DF.DOCKET_GONE_MOST, DF.SPONSORS_GONE_MOST, DF.ROSTER_TOLERANCE,
            DF.SPONSORS_KEPT_LEAST) == (5, 5, 0.02, 0.98), \
        "a guard's threshold moved; they are 5 rows, 5 rows, 2% and 98%"
    return "ok", ("a view behind the export, 6 docket rows or a bill gone, a bill record gone, a "
                  "roll call gone or short of ballots, three with other counts, a roster 3% off or 3% "
                  "replaced, 6 rows of LsrSponsors.txt gone, one sponsor of a numbered bill gone "
                  "from LsrsOnly.txt, a wrong width and an empty file each stop the night; 5 "
                  "docket rows gone pass and are named; a day that only grew stops nothing, and "
                  "nor does a busy sponsor leaving the roster")
_DBGUARD_TONIGHT = {
    "docket_new": [
        "2026|0038|9/30/2026 1:10:39 PM|HB100|H| Interim Study Report: Not Recommended for Future Leg"
        "islation  09/29/2026 (Vote 10-0; )|9/30/2026 1:10:39 PM",
        "2026|2083|9/30/2026 1:12:19 PM|SB632|H| Interim Study Report: Not Recommended for Future Leg"
        "islation  09/29/2026 (Vote 10-0; )|9/30/2026 1:12:19 PM",
        "2026|0001|9/30/2026 1:13:25 PM|HB561|H| Interim Study Report: Not Recommended for Future Leg"
        "islation  09/29/2026 (Vote 8-2; )|9/30/2026 1:13:25 PM",
        "2026|2986|9/30/2026 3:01:12 PM|HB1753|H| Interim Study Report: Not Recommended for Future Le"
        "gislation  09/28/2026 (Vote 13-0; )|9/30/2026 3:01:12 PM",
        "2026|3022|9/30/2026 3:03:43 PM|HCR16|H| Interim Study Report: Recommended for Future Legisla"
        "tion  09/28/2026 (Vote 11-2; )|9/30/2026 3:03:43 PM",
        "2026|0452|10/1/2026 12:40:24 PM|HB312|H|Executive Session: 10/14/2026 10:00 am GP 229|10/1/2"
        "026 12:40:24 PM",
        "2026|0393|10/1/2026 12:40:31 PM|HB359|H|Executive Session: 10/14/2026 10:00 am GP 229|10/1/2"
        "026 12:40:31 PM",
        "2026|2092|10/1/2026 12:44:34 PM|SB647|H|Executive Session: 10/14/2026 10:00 am GP 229|10/1/2"
        "026 12:44:34 PM",
        "2026|0602|10/1/2026 12:40:40 PM|HB427|H|Executive Session: 10/14/2026 10:00 am GP 229|10/1/2"
        "026 12:40:40 PM",
    ],
    "docket_reworded": [
        "2026|2711|3/4/2026 5:50:17 PM|HB1218|H|Minority Committee Report: Ought to Pass with Amendme"
        "nt # 2026-0956h|9/14/2026 11:08:26 AM",
    ],
    "rollcall_49": [
        "2026|S|49|3/26/2026 12:00:00 AM|SB665|24|0|24|0|||Ought to Pass w/Amendment|(New Title) rela"
        "tive to pharmacy benefits managers, managed care laws, notice of drug pricing options\u00a0and ph"
        "armacy benefit manager business practices.||3/26/2026 3:48:57 PM",
    ],
    "only_bare": [
        "26-2012|8740|1201|2026|Sponsor||S|applying to Congress for an Article V Constitutional Conve"
        "ntion.",
        "26-2012|8747|1201|2026|Prime||S|applying to Congress for an Article V Constitutional Convent"
        "ion.",
        "26-2012|10595|1201|2026|Sponsor||S|applying to Congress for an Article V Constitutional Conv"
        "ention.",
        "26-2012|10607|1201|2026|Sponsor||S|applying to Congress for an Article V Constitutional Conv"
        "ention.",
        "26-2012|10698|1201|2026|Sponsor||S|applying to Congress for an Article V Constitutional Conv"
        "ention.",
        "26-2248|43|1447|2026|Prime||S|regarding the victims of the abuse suffered at the Youth Devel"
        "opment Center.",
        "26-2248|9406|1447|2026|Sponsor||S|regarding the victims of the abuse suffered at the Youth D"
        "evelopment Center.",
        "26-2248|9856|1447|2026|Sponsor||S|regarding the victims of the abuse suffered at the Youth D"
        "evelopment Center.",
        "26-2248|10599|1447|2026|Sponsor||S|regarding the victims of the abuse suffered at the Youth "
        "Development Center.",
        "26-2248|10600|1447|2026|Sponsor||S|regarding the victims of the abuse suffered at the Youth "
        "Development Center.",
    ],
}


@check("build", "a database night's files are held to what the installed ones say and to what "
       "they add: a real night passes and names what it counted, and real rows doctored one "
       "way at a time stop it, each guard at its edge", needs=("dayfiles_from_db",))
def _dayfiles_content(DF):
    """dayfiles_from_db.judge() compared counts and keys until 2 October 2026.
    Two checkers doctored copies of that day's rebuilt files, and a wrong
    committee and title on a third of the bills, 5,000 invented docket rows,
    250 reworded ones, a docket row dated a year back, every Yea and Nay
    swapped, every roll call filed under HB 1 and every member's party
    swapped each passed every guard. It was made to hold the files to their
    content; and two reviewers then found what that still let in -- rows
    ADDED, rows twice, a view in another encoding, a handful of anything
    under a ceiling that was a guess -- and what it stopped that was right:
    the Senate's own late entries. Each guard is tried here.

    The rows are the General Court's own (_DBGUARD_REAL, above). The night
    they make is real in every part, though the parts are of four days:
    nine of the 31 docket rows 2 October brought; HB 1218's amendment number
    as the clerk corrected it on 14 September; Senate roll call 49 as it was
    moved from SB 655 to SB 665 between the 6th and the 13th, its 24 ballots
    with it; and the House status code the view has at 07 where the export
    has 04. That night passes every guard, says what each counted, and names
    the two rows that changed under a ceiling.

    Then one thing is doctored at a time, and each guard fires, at its edge
    from both sides. A ceiling set from a session day -- 1,000 docket rows,
    170 bill records -- is lowered for the test to what a fixture of twenty
    rows can cross, and held to its real value at the end; the ones a few
    real rows reach are tried as they are. A row made for a guard is said to
    be.
    """
    from datetime import timedelta
    real, part = _DBGUARD_REAL, _DBGUARD_TONIGHT
    installed = {n: _dbday_bytes(v) for n, v in real.items()}
    ASKED = {"asked": "2026-10-02T09:55:27"}        # when the real views were asked
    NAMED = "each named in the night's verdict (day_files, told) and in its what-changed report"

    def six(ln):
        """A docket row as the reshaper writes one: the seventh column the third."""
        f = ln.split("|")
        return "|".join(f[:6] + [f[2]])

    def put(ln, at, value):
        f = ln.split("|")
        f[at] = value
        return "|".join(f)
    tonight = {n: list(v) for n, v in real.items()}
    tonight["Docket.txt"] = [six(part["docket_reworded"][0]) if "2026-0596h" in ln else six(ln)
                             for ln in real["Docket.txt"]] + [six(ln) for ln in part["docket_new"]]
    tonight["LSRs.txt"] = [put(ln, 16, "07") if ln.split("|")[10] in ("HB224", "SB570") else ln
                           for ln in real["LSRs.txt"]]
    tonight["RollCallSummary.txt"] = [part["rollcall_49"][0] if ln.split("|")[2] == "49" else ln
                                      for ln in real["RollCallSummary.txt"]]
    tonight["RollCallHistory.txt"] = [put(ln, 5, "SB665") for ln in real["RollCallHistory.txt"]]
    assert [ln.split("|")[10] for ln in real["LSRs.txt"]] == [
        "HB100", "HB224", "SB532", "SB633", "SB570", "HB1218"] and \
        sum(a != b for a, b in zip(real["LSRs.txt"], tonight["LSRs.txt"])) == 2

    def judged(had=None, facts=ASKED, **now):
        return DF.judge({n: _dbday_bytes(now.get(n.split(".")[0], tonight[n])) for n in real},
                        dict(installed, **{n: _dbday_bytes(v) for n, v in (had or {}).items()}),
                        facts)

    def stops(had=None, facts=ASKED, **now):
        return judged(had, facts, **now)["stops"]

    def only(got, words, what):
        assert len(got) == 1 and words in got[0], f"{what}: the guards said {got}"

    def has(got, words, what):
        assert any(words in s for s in got), f"{what}: the guards said {got}"

    names = ("DOCKET_NEW_A_DAY_MOST", "DOCKET_LATE_MOST", "DOCKET_AHEAD_MOST", "DOCKET_TWICE_MOST",
             "DOCKET_CITED_MOST", "DOCKET_MARKED_MOST", "DOCKET_REMARKED_MOST",
             "DOCKET_REWORDED_MOST", "DOCKET_GONE_MOST",
             "LSR_NEW_MOST", "LSR_RETITLED_MOST", "LSR_REWRITTEN_MOST", "LSR_CHANGED_MOST",
             "LSR_UNBACKED_MOST", "LSR_ALONE_MOST", "ROLLCALLS_CHANGED_MOST", "BALLOTS_CHANGED_MOST",
             "ROLLCALL_ADRIFT_MOST",
             "ROLLCALLS_NEW_MOST", "ROLLCALL_STRANGERS_MOST", "ROSTER_TOLERANCE",
             "ROSTER_MOVED_MOST", "ROSTER_CHANGED_MOST", "ROSTER_TOUCHED_MOST",
             "SPONSORS_NEW_MOST", "SPONSORS_LATE_MOST", "SPONSORS_GONE_MOST", "SPONSORS_KEPT_LEAST")
    was = {name: getattr(DF, name) for name in names}

    def at(**ceilings):
        """The ceilings as they really stand, but for these."""
        for name, value in was.items():
            setattr(DF, name, ceilings.get(name, value))
    try:
        # THE REAL NIGHT, at the real thresholds.
        got = judged()
        assert not got["stops"] and got["wider"] == 0, (got["stops"], got.get("wider"))
        assert got["held"] == {
            "nights": 1,
            "Docket.txt": {"new": 9, "busiest_day": ["2026-09-30", 5], "late": 0, "ahead": 0,
                           "cited": 0, "marked": 0, "remarked": 0, "reworded": 1, "gone": 0,
                           "twice": 0},
            "LSRs.txt": {"new": 0, "unsponsored": 0, "changed": 0, "rewritten": 0, "retitled": 0,
                         "unbacked": 0, "ahead_of_docket": 0, "unread": {"House status code": 2}},
            "roll calls": {"calls": 1, "counts": 0, "ballots": 0, "new": 0, "strangers": 0,
                           "unsummed": 0},
            "legislators.txt": {"who": 0, "any": 0, "seat_or_mail": 0, "left": 0, "joined": 0},
            "LsrSponsors.txt": {"new": 0, "late": 0, "gone": 0},
            "LsrsOnly.txt": {"gone_numbered": 0, "gone_unnumbered": 0, "new": 0}}, got["held"]
        said = "\n".join(DF.held_said(got["held"]))
        assert "9 new, the most entered on one day 5 (2026-09-30)" in said and \
            "0 gained a citation, 0 a mark, 1 reworded, 0 gone" in said and \
            "in columns it does not read: House status code on 2" in said and \
            "of the installed 1 read otherwise, 0 ballots cast otherwise" in said, said
        # ... and the two rows that changed under a ceiling are named, each
        # shown where it differs, and the warnings say how many and no more:
        # the rows are the record's words, and a warning is on the run's page.
        assert got["warnings"] == [
            f"Docket.txt: installed rows reworded: 1, {NAMED}",
            f"RollCallSummary.txt: installed roll calls that read otherwise: 1, {NAMED}"], \
            got["warnings"]
        told = got["told"]
        assert list(told) == ["Docket.txt: installed rows reworded",
                              "RollCallSummary.txt: installed roll calls that read otherwise"] and \
            told["Docket.txt: installed rows reworded"] == [
                "2026|2711|3/4/2026 5:50:17 PM|HB1218|H|'...h Amendment # 2026-0596h' now "
                "'...h Amendment # 2026-0956h'"] and \
            told["RollCallSummary.txt: installed roll calls that read otherwise"][0].startswith(
                "2026 S 49 bill 'SB655' now 'SB665'; title \"... Title) relative to employee "
                "leasing companies, workers' com...\" now '... Title) relative to pharmacy "
                "benefits managers"), told
        assert "\n".join(DF.told_said(told)).startswith(
            "  named, Docket.txt: installed rows reworded:\n      2026|2711|"), DF.told_said(told)
        assert not any("HB1218" in w or "SB665" in w for w in got["warnings"])
        # Two titles cut at 40 characters before the place they part printed
        # as the same words; and a difference in spaces alone is shown.
        assert DF._differ("a" * 70 + "X tail", "a" * 70 + "Y tail") == \
            "'..." + "a" * 20 + "X tail' now '..." + "a" * 20 + "Y tail'" and \
            DF._differ(" Hearing", "Hearing") == "' Hearing' now 'Hearing' (8 characters, now 7)"

        # ---- THE DOCKET'S NEW ROWS --------------------------------------
        d = tonight["Docket.txt"]
        session = d[-1]                 # HB 427's executive session, entered 1 October
        # (made: that row under a bill no file knows)
        stray = put(put(session, 1, "9999"), 3, "HB9999")
        only(stops(Docket=d + [stray]), "Docket.txt: 1 new rows are under a bill that neither the "
             "installed docket nor LSRs.txt knows: 2026|9999|10/1/2026 12:40:40 PM|HB9999|H|",
             "a new docket row under a bill nobody knows")
        # ... and it is known once tonight's LSRs.txt brings the bill (made:
        # HB 224's record under that number).
        brought = put(put(put(real["LSRs.txt"][1], 1, "9999"), 10, "HB9999"), 9, "HB  9999")
        assert not stops(Docket=d + [stray], LSRs=tonight["LSRs.txt"] + [brought]), \
            "a new docket row under a bill tonight's LSRs.txt introduces stopped the night"
        # An entry time clock() could not read is passed through as it came.
        only(stops(Docket=d + [put(put(session, 2, "10/01/2026 12:40:40"), 5, "Executive Session")]),
             "Docket.txt: 1 new rows carry an entry time that does not read as one",
             "a new docket row with an entry time that is not one")
        # A row with no words, or in no chamber: the 31 real rows passed with
        # NULL for both.
        only(stops(Docket=d + [put(put(session, 5, " "), 2, "10/1/2026 12:45:00 PM")]),
             "Docket.txt: 1 new rows have no words, or a chamber that is neither H nor S",
             "a new docket row with no words")
        only(stops(Docket=d + [put(put(session, 4, "J"), 5, "Executive Session: adjourned")]),
             "have no words, or a chamber that is neither H nor S", "a new docket row in chamber J")
        got = stops(Docket=d[:-1] + [put(put(session, 4, "NULL"), 5, "NULL")])
        assert len(got) == 2 and "Docket.txt: 2 fields read NULL, None, True or False, which no " \
            "field of an export does" in got[0] and "have no words, or a chamber" in got[1], got

        # ENTERED LONG BEFORE. The checkers' row: an installed House row's own
        # stamp, of February, under other words. It still stops the night.
        old = put(d[0], 5, "Signed by Governor 01/02/2025")
        only(stops(Docket=d + [old]), "Docket.txt: 1 new rows were entered more than 14 days "
             "before the installed file's newest (2026-09-29 12:41:48), and are not the Senate's "
             "late entries -- a House row, or one older than its bill's first: 2026|2711|2/17/2026 "
             "3:29:16 PM|HB1218|H|Signed by Governor", "a new House row dated seven months back")
        # The installed file's newest entry is 29 September 12:41:48; 14 days
        # before it to the second is an ordinary row, and a second more is
        # not. (An entry time runs up to a week AHEAD of the day a row is
        # written -- the conference meeting of 26 May in the fixture, written
        # on the 19th -- which is why the slack is not nothing.)
        edge = put(put(session, 5, "Executive Session: continued"), 2, "9/15/2026 12:41:48 PM")
        assert not stops(Docket=d + [edge]), "a new row 14 days before the newest stopped the night"
        only(stops(Docket=d + [put(edge, 2, "9/15/2026 12:41:47 PM")]), "more than 14 days before",
             "a new House row 14 days and a second before the newest")
        assert DF.DOCKET_STAMP_SLACK == timedelta(days=14)
        # THE SENATE'S LATE ENTRIES ARE REAL, and one is no reason to stop: a
        # row entered late carries the day of the action and the clock of the
        # moment it was typed. HB 609's hearing of 10 March 2026 was entered
        # on 28 April, at 2:22:39 PM, as of 9 March at 2:22:39 PM (the export
        # of 30 September, with its seventh column). Stopping at the first
        # such row stopped eight real nights of the term, and every database
        # night after each. It passes, counted and named.
        hb609 = ["2026|0889|1/16/2025 9:25:16 AM|HB609|H|  Introduced (in recess of) 01/09/2025 "
                 "and referred to Criminal Justice and Public Safety  HJ 3  P. 18|"
                 "2/18/2025 3:08:19 PM",
                 "2026|0889|1/30/2026 9:15:02 AM|HB609|S|  Introduced 01/29/2026 and Referred to "
                 "Judiciary;  SJ 3|1/30/2026 9:15:02 AM"]
        late = ("2026|0889|3/9/2026 2:22:39 PM|HB609|S| Hearing: 03/10/2026, Room 100, SH, "
                "01:30 pm;  SC 9|4/28/2026 2:22:39 PM")
        had = {"Docket.txt": real["Docket.txt"] + hb609}
        with_609 = d + [six(ln) for ln in hb609]
        got = judged(had, Docket=with_609 + [six(late)])
        label = "Docket.txt: new Senate rows entered more than 14 days before the installed file's newest"
        assert not got["stops"] and got["held"]["Docket.txt"]["late"] == 1 and \
            got["held"]["Docket.txt"]["new"] == 10, (got["stops"], got["held"]["Docket.txt"])
        assert got["told"][label] == ["2026|0889|3/9/2026 2:22:39 PM|HB609|S| Hearing: 03/10/2026, "
                                      "Room 100, SH, 01:30 pm;  SC 9"] and \
            f"{label}: 1, {NAMED}" in got["warnings"], (got["told"], got["warnings"])
        # More of them than the Senate enters late in a night is a stop: 17
        # is the most, and 40 the ceiling. (made: a second, a day earlier; the
        # ceiling lowered to one)
        at(DOCKET_LATE_MOST=1)
        only(stops(had, Docket=with_609 + [six(late), put(six(late), 2, "3/8/2026 2:22:39 PM")]),
             "Docket.txt: 2 new Senate rows were entered more than 14 days before the installed "
             "file's newest (2026-09-29 12:41:48), more than the 1 the Senate enters late",
             "two late Senate rows against one")
        at()
        # ... and so is one dated before its bill's first row (made), which
        # no late entry of the term is.
        only(stops(had, Docket=with_609 + [put(six(late), 2, "1/15/2025 2:22:39 PM")]),
             "a House row, or one older than its bill's first: 2026|0889|1/15/2025 2:22:39 PM|HB609|S|",
             "a late Senate row older than its bill")

        # ENTERED AFTER THE VIEWS WERE ASKED. A conference meeting is stamped
        # midnight of its own day, up to a week ahead: counted. (made: HB
        # 427's session as a meeting of 6 October)
        ahead = put(put(session, 2, "10/6/2026 12:00:00 AM"), 5,
                    "Conference Committee Meeting: 10/06/2026 10:00 am GP 228")
        got = judged(Docket=d + [ahead])
        assert not got["stops"] and got["held"]["Docket.txt"]["ahead"] == 1, got
        at(DOCKET_AHEAD_MOST=1)
        only(stops(Docket=d + [ahead, put(ahead, 2, "10/7/2026 12:00:00 AM")]),
             "Docket.txt: 2 new rows are entered after the views were asked (2026-10-02 09:55:27), "
             "more than 1", "two rows entered ahead against one")
        at()
        # A row stamped a year ahead passed every guard, and once it was
        # installed every honest row after it was "entered more than 14 days
        # before the installed file's newest": the fallback stopped for good.
        year_on = put(put(session, 2, "10/2/2027 9:00:00 AM"), 5,
                      "Executive Session: 10/14/2027 10:00 am GP 229")
        only(stops(Docket=d + [year_on]), "Docket.txt: 1 new rows are entered more than 14 days "
             "after the views were asked (2026-10-02 09:55:27): 2026|0602|10/2/2027 9:00:00 AM|"
             "HB427|H|Executive Session: 10/14/2027", "a new docket row stamped a year ahead")
        assert not stops(Docket=d + [put(ahead, 2, "10/16/2026 9:55:27 AM")]) and stops(
            Docket=d + [put(ahead, 2, "10/16/2026 9:55:28 AM")]), "the edge is not 14 days after"
        # ... and were such a row installed all the same, the next night's
        # honest row is measured from the time the views were asked.
        honest = put(put(session, 2, "10/5/2026 10:00:00 AM"), 5,
                     "Executive Session: 10/20/2026 10:00 am GP 229")
        assert not stops({"Docket.txt": real["Docket.txt"] + [year_on]}, {"asked": "2026-10-06T05:00:00"},
                         Docket=d + [year_on, honest]), \
            "with a row stamped a year ahead installed, an honest new row stopped the night"

        # MORE IN A DAY THAN A DAY BRINGS, and in a night than its nights. The
        # real ceiling is 1,000 for both; the fixture's busiest day has 5
        # rows and the night 9. With the installed files five nights old the
        # night's is 2.2 times the day's, 11: a sixth row on the 30th (made:
        # one more interim study report) stops by the day.
        five = dict(ASKED, nights=5)
        at(DOCKET_NEW_A_DAY_MOST=5)
        assert not stops(facts=five), "5 new rows on one day, the most allowed, stopped the night"
        sixth = put(put(d[-5], 5, " Interim Study Report: a sixth"), 2, "9/30/2026 4:00:00 PM")
        only(stops(facts=five, Docket=d + [sixth]), "Docket.txt: 6 new rows entered on 2026-09-30, "
             "more than the 5 a day brings", "6 new docket rows on one day against 5")
        # (A day's ceiling is no wider on a later night; a night's is, and
        # judge() says which kind stopped it: the night's page tells the two
        # apart, since only one of them stops the next night as well.)
        assert judged(facts=five, Docket=d + [sixth])["wider"] == 0
        # ... and the night: 20,000 invented rows spread at 953 a day passed
        # the day's ceiling alone. Nine rows are a night's nine, and not
        # eight's.
        at(DOCKET_NEW_A_DAY_MOST=9)
        assert not stops(), "9 new rows in a night, the most allowed, stopped the night"
        at(DOCKET_NEW_A_DAY_MOST=8)
        only(stops(), "Docket.txt: 9 new rows, more than the 8 that 1 night brings: 2026|0038|"
             "9/30/2026 1:10:39 PM|HB100|H|", "9 new docket rows in a night against 8")
        got = judged()
        assert got["wider"] == 1 and all(type(x) is str for x in got["stops"]), (
            "a stop on a night's ceiling, which is wider the older the installed files are, is "
            "not counted as one", got.get("wider"), got["stops"])
        assert not stops(facts=dict(ASKED, nights=2)), \
            "9 new rows over two nights, against 8 a night, stopped the night"
        at()

        # A ROW TWICE. Every row entered in a fortnight came back twice from
        # a doctored view, 70 of them, and was installed. A conference
        # meeting's notice really is entered twice now and then (three pairs
        # in the term), so four are let be, and named.
        got = judged(Docket=d + [session] * 4)
        assert not got["stops"] and got["held"]["Docket.txt"]["twice"] == 4 and got["told"][
            "Docket.txt: rows there more than once, and not so in the installed file"] == [
                "|".join(session.split("|")[:6])], (got["stops"], got["told"])
        only(stops(Docket=d + [session] * 5), "Docket.txt: 5 rows are there once more than a row "
             "is, or than the installed file has them, more than 4: 2026|0602|10/1/2026 12:40:40 "
             "PM|HB427|H|Executive Session", "a new docket row six times")
        has(stops(Docket=d + d[3:9]), "Docket.txt: 6 rows are there once more than a row is",
            "six installed docket rows twice")
        assert DF.DOCKET_TWICE_MOST == 4

        # ---- THE DOCKET'S OLD ROWS --------------------------------------
        # A citation written onto a row. Four of the fixture's rows carry
        # one; the row before its citation is on no copy on disk, so the
        # installed side is made here by cutting each off (House and Senate
        # alike: "  HJ 6  P. 2", ";  SJ 4").
        cited = [i for i, ln in enumerate(real["Docket.txt"]) if DF.CITATION.search(ln.split("|")[5])]
        assert len(cited) == 4 and all(DF._cited(
            DF.CITATION.sub("", real["Docket.txt"][i].split("|")[5]),
            real["Docket.txt"][i].split("|")[5]) for i in cited), cited
        assert not DF._cited("Ought to Pass: MA VV 03/05/2026", "Inexpedient to Legislate: MA VV "
                             "03/05/2026  HJ 6  P. 2") and not DF._cited("a", "a")
        # A citation completed is one written on; a citation REPLACED is a
        # row reworded: 1,000 rows moved to "HJ 99 P. 999" passed as cited.
        assert DF._cited("Ought to Pass  HJ 6", "Ought to Pass  HJ 6  P. 2") and \
            not DF._cited("Ought to Pass  HJ 6  P. 2", "Ought to Pass  HJ 99 P. 999") and \
            not DF._cited("Ought to Pass  HJ 6", "Ought to Pass  HJ 62  P. 2")

        def uncited(n):
            return [put(ln, 5, DF.CITATION.sub("", ln.split("|")[5])) if i in cited[:n] else ln
                    for i, ln in enumerate(real["Docket.txt"])]
        at(DOCKET_CITED_MOST=3)
        got = judged({"Docket.txt": uncited(3)})
        assert not got["stops"] and got["held"]["Docket.txt"]["cited"] == 3 and \
            got["held"]["Docket.txt"]["reworded"] == 1, (got["stops"], got["held"]["Docket.txt"])
        only(stops({"Docket.txt": uncited(4)}), "Docket.txt: 4 installed rows gained a journal "
             "citation, more than 3", "4 citations against 3")
        # Four real days running wrote 1,078 citations, against 1,000 a
        # night: with the installed files two nights old a night's ceiling
        # is one and a half days', which is 4 here (3 x 1.5, rounded).
        assert not stops({"Docket.txt": uncited(4)}, dict(ASKED, nights=2)), \
            "4 citations over two nights, against 3 a night, stopped the night"
        at()
        other = [put(ln, 5, DF.CITATION.sub("HJ 99 P. 999", ln.split("|")[5])) if i in cited else ln
                 for i, ln in enumerate(d)]
        got = judged(Docket=other)
        assert not got["stops"] and got["held"]["Docket.txt"]["cited"] == 0 and \
            got["held"]["Docket.txt"]["reworded"] == 5, got["held"]["Docket.txt"]
        # A mark put before a row's words. SB 633's cancelled session carries
        # one: the installed row is made by taking the mark off. It is
        # counted apart from a rewording (the most in a real day is 50).
        unmarked = [ln.replace("==CANCELLED== ", "") for ln in real["Docket.txt"]]
        assert sum(a != b for a, b in zip(unmarked, real["Docket.txt"])) == 1
        got = judged({"Docket.txt": unmarked})
        assert not got["stops"] and got["held"]["Docket.txt"]["marked"] == 1 and \
            got["held"]["Docket.txt"]["reworded"] == 1, got["held"]["Docket.txt"]
        at(DOCKET_MARKED_MOST=0)
        only(stops({"Docket.txt": unmarked}), "Docket.txt: 1 installed rows are marked in the "
             "database's, more than 0: 2026|2187|3/19/2026 9:14:15 AM|SB633|H|==CANCELLED==",
             "one marked row against none")
        at()
        # ... AND THE WORDS AFTER THE MARK ARE THE INSTALLED WORDS, or the row
        # is one of a few, and named. A mark was all that was looked for: 100
        # committee reports turned from Ought to Pass to Inexpedient to
        # Legislate behind "==AMENDED==" were installed as 100 rows marked,
        # and nobody was told which. (made: HB 1228's outcome so turned)
        assert got["held"]["Docket.txt"]["remarked"] == 0, got["held"]["Docket.txt"]
        behind = [put(ln, 5, "==AMENDED== " + ln.split("|")[5].replace(
            "Ought to Pass:", "Inexpedient to Legislate:")) if "HB1228" in ln else ln for ln in d]
        assert sum(a != b for a, b in zip(behind, d)) == 1
        got = judged(Docket=behind)
        label = "Docket.txt: installed rows given a mark, and other words after it"
        assert not got["stops"] and got["held"]["Docket.txt"]["remarked"] == 1 and \
            got["held"]["Docket.txt"]["marked"] == 1 and got["held"]["Docket.txt"]["reworded"] == 1 \
            and len(got["told"][label]) == 1 and got["told"][label][0].startswith(
                "2026|2947|3/5/2026 9:24:15 AM|HB1228|H|'Ought to Pass: MA VV 03/05/2026  HJ 6  P. "
                "2' now '==AMENDED== Inexpedient to Legislate: MA VV") and \
            f"{label}: 1, {NAMED}" in got["warnings"] and \
            "1 a mark (1 of them with other words after it)" in "\n".join(
                DF.held_said(got["held"])), (got["stops"], got["held"]["Docket.txt"], got["told"])
        at(DOCKET_REMARKED_MOST=0)
        only(stops(Docket=behind), "Docket.txt: 1 installed rows are given a mark in the "
             "database's and other words after it, more than 0: 2026|2947|3/5/2026 9:24:15 AM|"
             "HB1228|H|'Ought to Pass: MA VV", "one row reworded behind a mark, against none")
        at()
        assert DF.DOCKET_REMARKED_MOST == 50 < DF.DOCKET_MARKED_MOST
        # Reworded any other way: HB 1218's corrected number is one, and the
        # real ceiling is 40 (the most in a real day is 18). 100 outcomes
        # rewritten passed at 100. (made: the second, an outcome turned round)
        turned = [put(ln, 5, ln.split("|")[5].replace("Ought to Pass:", "Inexpedient to Legislate:"))
                  if "HB1228" in ln else ln for ln in d]
        assert sum(a != b for a, b in zip(turned, d)) == 1
        at(DOCKET_REWORDED_MOST=1)
        assert not stops(), "one reworded row, the most allowed, stopped the night"
        only(stops(Docket=turned), "Docket.txt: 2 installed rows are reworded in the database's, "
             "more than 1: 2026|2711|3/4/2026 5:50:17 PM|HB1218|H|'...h Amendment # 2026-0596h' "
             "now '...h Amendment # 2026-0956h'", "2 reworded rows against 1")
        at()
        got = judged(Docket=turned)
        assert not got["stops"] and got["told"]["Docket.txt: installed rows reworded"][1] == (
            "2026|2947|3/5/2026 9:24:15 AM|HB1228|H|'Ought to Pass: MA VV 03/05/2026  HJ 6  P. 2' "
            "now 'Inexpedient to Legislate: MA VV 03/05/2026  HJ 6  P. 2' (43 characters, now "
            "54)"), got["told"]
        # A row gone is counted apart from one reworded, and named (the
        # ceiling's edge is tried on 402 rows, in the check before this one).
        got = judged(Docket=d[1:])
        assert not got["stops"] and got["held"]["Docket.txt"]["gone"] == 1 and \
            got["held"]["Docket.txt"]["reworded"] == 1 and \
            got["told"]["Docket.txt: installed rows gone"] == [
                "2026|2711|2/17/2026 3:29:16 PM|HB1218|H|Executive Session: 03/03/2026 10:00 am "
                "GP 231"], (got["held"]["Docket.txt"], got["told"])

        # ---- THE BILL RECORDS -------------------------------------------
        r = tonight["LSRs.txt"]

        def records(which, at_, value):
            return [put(ln, at_, value) if i in which else ln for i, ln in enumerate(r)]
        # A CHANGED RECORD IS HELD TO THE DOCKET. Tonight's docket has a new
        # row for HB 100 and a reworded one for HB 1218, and SB 570's last is
        # three days old: those three are moving. HB 224 has no docket row in
        # the fixture, SB 532's last is of February and SB 633's of March: at
        # rest. A changed record at rest is one of a handful, named, or the
        # night stops: a subject code changed on 100 bills, a Senate committee
        # invented on 646 and a hearing moved on 700 each passed.
        MOVING, AT_REST = (0, 4, 5), (1, 2, 3)
        label = "LSRs.txt: installed bill records changed with nothing in the docket to say why"
        got = judged(LSRs=records(AT_REST[:1], 12, "STG"))
        assert not got["stops"] and got["held"]["LSRs.txt"]["unbacked"] == 1 and got["told"][label] \
            == ["2026-0213 HB224, subject code 'ENU' now 'STG'"] and \
            f"{label}: 1, {NAMED}" in got["warnings"], (got["stops"], got["told"], got["warnings"])
        got = judged(LSRs=records(MOVING, 12, "STG"))
        assert not got["stops"] and got["held"]["LSRs.txt"] == {
            "new": 0, "unsponsored": 0, "changed": 3, "rewritten": 3, "retitled": 0, "unbacked": 0,
            "ahead_of_docket": 0,
            "unread": {"House status code": 2}} and label not in got["told"], got["held"]["LSRs.txt"]
        at(LSR_UNBACKED_MOST=2)
        assert not stops(LSRs=records(AT_REST[:2], 12, "ZZZ")), \
            "2 bill records at rest changed, the most allowed, stopped the night"
        only(stops(LSRs=records(AT_REST, 12, "ZZZ")), "LSRs.txt: 3 installed bill records changed "
             "where the build reads them with nothing in the docket to say why, more than 2: "
             "2026-0213 HB224, subject code 'ENU' now 'ZZZ'", "3 bill records at rest changed")
        at()
        # The fortnight is from when the views were asked: asked a fortnight
        # later, SB 570 is at rest too.
        assert judged(LSRs=records((4,), 12, "STG"))["held"]["LSRs.txt"]["unbacked"] == 0 and judged(
            facts={"asked": "2026-10-14T09:55:27"},
            LSRs=records((4,), 12, "STG"))["held"]["LSRs.txt"]["unbacked"] == 1
        # A committee of referral in a chamber whose docket has no row for
        # the bill is not backed by it, though the bill is moving: HB 100 has
        # never been to the Senate. (made: a Senate committee for it) ...
        got = judged(LSRs=records((0,), 21, "S24"))
        assert not got["stops"] and got["held"]["LSRs.txt"]["unbacked"] == 1 and got["told"][label] \
            == ["2026-0038 HB100, Senate committee of referral '' now 'S24' (0 characters, now 3)"], \
            got["told"]
        # ... WITH A COMMITTEE SOME INSTALLED RECORD IS ALREADY BEFORE, and
        # nothing else changed, it is a first referral ahead of its docket
        # row: held apart from the handful, named, and stopped only past
        # LSR_ALONE_MOST. Whether the General Court sets the code before it
        # types the row is on no copy on this disk; if it does, the 148 bills
        # the Senate took up on one day of March were 143 too many, and every
        # database night after it was stopped. (made: SB 532's committee,
        # S05, for HB 100, which is moving, and for HB 224, which is at rest)
        ahead = ("LSRs.txt: installed bill records that gained a committee in a chamber whose "
                 "docket has no row of the bill yet")
        got = judged(LSRs=records((0, 1), 21, "S05"))
        assert not got["stops"] and got["held"]["LSRs.txt"]["unbacked"] == 0 and \
            got["held"]["LSRs.txt"]["ahead_of_docket"] == 2 and got["told"][ahead] == [
                "2026-0038 HB100, Senate committee of referral '' now 'S05' (0 characters, now 3)",
                "2026-0213 HB224, Senate committee of referral '' now 'S05' (0 characters, now 3)"] \
            and f"{ahead}: 2, {NAMED}" in got["warnings"] and label not in got["told"] and \
            "2 with a first committee in a chamber whose docket has no row of the bill yet" in \
            "\n".join(DF.held_said(got["held"])), (got["stops"], got["held"]["LSRs.txt"], got["told"])
        at(LSR_ALONE_MOST=1)
        only(stops(LSRs=records((0, 1), 21, "S05")), "LSRs.txt: 2 installed bill records gained a "
             "committee in a chamber whose docket has no row of the bill, more than 1: 2026-0038 "
             "HB100, Senate committee of referral", "2 first referrals ahead of the docket")
        at()
        # (At rest, with something else changed as well, it is one of the
        # handful still: HB 224 with that committee and another subject code.)
        got = judged(LSRs=[put(ln, 12, "STG") if i == 1 else ln
                           for i, ln in enumerate(records((1,), 21, "S05"))])
        assert got["held"]["LSRs.txt"]["unbacked"] == 1 and \
            got["held"]["LSRs.txt"]["ahead_of_docket"] == 0, got["held"]["LSRs.txt"]
        assert DF.LSR_ALONE_MOST == 600
        # ... and with the Senate's row of it tonight (made), it is what a
        # referral is.
        referred = put(put(session, 1, "0038"), 3, "HB100")
        referred = put(put(referred, 4, "S"), 5, "  Introduced 10/01/2026 and Referred to Finance")
        got = judged(LSRs=records((0,), 21, "S24"), Docket=d + [referred])
        assert not got["stops"] and got["held"]["LSRs.txt"]["unbacked"] == 0 and \
            got["held"]["LSRs.txt"]["changed"] == 1 and got["held"]["LSRs.txt"]["rewritten"] == 0, got
        # A bill does not change the chamber it began in, nor its number.
        only(stops(LSRs=records((0,), 10, "HB74")), "LSRs.txt: 1 installed bill records have "
             "another chamber or bill number in the database's, which a bill does not change: "
             "2026-0038 HB74, bill number 'HB100' now 'HB74'", "a bill record under another number")
        only(stops(LSRs=records((5,), 3, "S")), "which a bill does not change: 2026-2711 HB1218, "
             "chamber 'H' now 'S'", "a bill record in the other chamber")
        # THE SESSION DAY'S CEILINGS, for the bills that are moving. The real
        # ones are 40 titles, 170 records rewritten and 700 changed.
        at(LSR_RETITLED_MOST=1, LSR_REWRITTEN_MOST=2, LSR_CHANGED_MOST=2)
        assert not stops(LSRs=records(MOVING[:1], 2, "(New Title) relative to rail.")), \
            "one bill record with a new title, the most allowed, stopped the night"
        only(stops(LSRs=records(MOVING[:2], 2, "(New Title) relative to rail.")), "LSRs.txt: 2 "
             "installed bill records have another title, more than 1: 2026-0038 HB100, title "
             "'prohibiting the use of state funds for new passenger rail pr...' now '(New Title) "
             "relative to rail.'", "2 bill records were given another title")
        # A TITLE REPLACED IS NAMED, at the real ceilings: it is what a page
        # says a bill is. Every bill with a docket row that fortnight, 53 of
        # them, was given another, and 55 more each with one new row, and the
        # night installed with nothing named.
        at()
        got = judged(LSRs=records(MOVING[:2], 2, "(New Title) relative to rail."))
        titled = "LSRs.txt: installed bill records with another title"
        assert not got["stops"] and len(got["told"][titled]) == 2 and got["told"][titled][0].startswith(
            "2026-0038 HB100, title 'prohibiting the use of state funds for new passenger rail "
            "pr...' now '(New Title) relative to rail.'") and \
            f"{titled}: 2, {NAMED}" in got["warnings"], (got["stops"], got["told"], got["warnings"])
        at(LSR_RETITLED_MOST=1, LSR_REWRITTEN_MOST=2, LSR_CHANGED_MOST=2)
        # (A title lost is a value lost, and no new title.)
        assert not stops(LSRs=records(MOVING[:2], 2, "")), \
            "2 bill records without a title, the most allowed, stopped the night"
        only(stops(LSRs=records(MOVING, 2, "")), "LSRs.txt: 3 installed bill records hold another "
             "value, or none, where the build reads one, more than 2: 2026-0038 HB100, title "
             "'prohibiting the use of state funds for new passenger rail pr...' now ''",
             "3 bill records lost their titles")
        only(stops(LSRs=records(MOVING, 31, "")), "hearing date", "3 bill records lost their hearing")
        # A hearing moved to another day is a change, and no value replaced.
        assert not stops(LSRs=records(MOVING[:2], 31, "10/14/2026 10:00:00 AM")), \
            "2 hearings moved to another day, the most allowed, stopped the night"
        only(stops(LSRs=records(MOVING, 31, "10/14/2026 10:00:00 AM")), "LSRs.txt: 3 installed bill "
             "records changed in a column the build reads, more than 2",
             "3 bill records with a hearing moved")
        at()
        # A column the build does not read is counted and never judged, on
        # every record at once: the House status code, here.
        got = judged(LSRs=[put(ln, 16, "99") for ln in r])
        assert not got["stops"] and got["held"]["LSRs.txt"]["unread"] == {"House status code": 6} \
            and got["held"]["LSRs.txt"]["changed"] == 0, (got["stops"], got["held"]["LSRs.txt"])
        # New records (made: HB 224's under other numbers): a day's, with a
        # title, a chamber and a bill number that is no other record's.
        second = put(put(put(brought, 1, "9998"), 10, "HB9998"), 9, "HB  9998")
        at(LSR_NEW_MOST=1)
        assert not stops(LSRs=r + [brought]), "one new bill record stopped the night"
        only(stops(LSRs=r + [brought, second]),
             "LSRs.txt: 2 new bill records, more than 1: 2026-9999 HB9999", "2 new bill records")
        assert not stops(facts=dict(ASKED, nights=5), LSRs=r + [brought, second]), \
            "2 new bill records over five nights, against one a night, stopped the night"
        at()
        only(stops(LSRs=r + [put(brought, 2, "")]), "LSRs.txt: 1 new bill records have no title, "
             "no bill number, or a chamber that is neither H nor S: 2026-9999 HB9999",
             "a new bill record with no title")
        # A bill has a sponsor: all but one of the 1,387 real records have a
        # row in LsrSponsors.txt. 300 invented records, each with a title and
        # a number of its own, passed. Two without one are named, and pass
        # (HB 9999 and HB 9998 have none); a third stops; and with a sponsor
        # each, none is named. (made: a third record, and their sponsors)
        third = put(put(put(brought, 1, "9997"), 10, "HB9997"), 9, "HB  9997")
        got = judged(LSRs=r + [brought, second])
        assert not got["stops"] and got["held"]["LSRs.txt"]["unsponsored"] == 2 and got["told"][
            "LSRs.txt: new bill records with no sponsor in LsrSponsors.txt"][0] == (
            "2026-9999 HB9999, relative to rebates to ratepayers from the renewable energy "
            "fund."), (got["stops"], got["told"])
        only(stops(LSRs=r + [brought, second, third]), "LSRs.txt: 3 new bill records have no "
             "sponsor in LsrSponsors.txt, more than 2: 2026-9999 HB9999", "3 new bill records "
             "with no sponsor")
        got = judged(LSRs=r + [brought, second, third], LsrSponsors=tonight["LsrSponsors.txt"] + [
            f"2026|{n}|1|35|1" for n in (9999, 9998, 9997)])
        assert not got["stops"] and got["held"]["LSRs.txt"]["unsponsored"] == 0 and \
            got["held"]["LSRs.txt"]["new"] == 3, (got["stops"], got["held"]["LSRs.txt"])
        assert DF.LSR_UNSPONSORED_MOST == 2
        # 50 new records under new request numbers and EXISTING bill numbers
        # passed, and build_data.py keeps the last record of a number.
        only(stops(LSRs=r + [put(brought, 10, "HB100")]), "LSRs.txt: 1 bill numbers are on more "
             "than one bill record: HB100", "a new bill record under HB 100's number")
        has(stops(LSRs=r + [put(r[0], 2, "another title")]), "LSRs.txt: 1 bill records are there "
            "more than once: 2026 0038, 2 times", "a bill record twice")

        # ---- THE ROLL CALLS, at the real ceilings ---------------------------
        # Senate roll call 49's move to SB 665 is one. One more refiled makes
        # the two allowed; a third stops. Five passed, and nobody was told
        # which.
        s = tonight["RollCallSummary.txt"]
        others = [i for i, ln in enumerate(s) if ln.split("|")[2] != "49"]

        def refiled(n):
            return [put(put(ln, 4, "HB1"), 11, "Ought to Pass") if i in others[:n] else ln
                    for i, ln in enumerate(s)]
        got = judged(RollCallSummary=refiled(1))
        assert not got["stops"] and len(got["told"][
            "RollCallSummary.txt: installed roll calls that read otherwise"]) == 2, got
        only(stops(RollCallSummary=refiled(2)), "RollCallSummary.txt: 3 installed roll calls read "
             "otherwise in the database's, more than 2: 2026 S 45 bill 'SB566' now 'HB1'",
             "3 roll calls were refiled")
        # A TALLY was held to nothing changing, which stopped the one
        # correction of a tally on record (SB 331 of 2018: a tally and one
        # senator's ballot), and then every night after it. One or two may
        # move, each named -- and never away from the ballots. Roll call 49's
        # 24 ballots are all Yea: its tally at 23 to 1 with no ballot changed
        # is a roll call that added up and no longer does, and stops; with
        # the one senator's ballot it is a correction. (made: both)
        alone = [put(put(ln, 5, "23"), 6, "1") if ln.split("|")[2] == "49" else ln for ln in s]
        only(stops(RollCallSummary=alone), "1 roll calls' Yea and Nay ballots are not their "
             "counts: 2026 S 49 says 23-1 and has 24 Yea and 0 Nay ballots",
             "a roll call's tally was changed, and no ballot with it")
        ballots = tonight["RollCallHistory.txt"]
        got = judged(RollCallSummary=alone, RollCallHistory=[put(ballots[0], 6, "Nay")] + ballots[1:])
        counts = "RollCallSummary.txt: installed roll calls with other counts (Yeas-Nays-Present-Absent)"
        assert not got["stops"] and got["held"]["roll calls"]["counts"] == 1 and \
            got["told"][counts] == ["2026 S 49 24-0-24-0 now 23-1-24-0"] and \
            got["told"]["RollCallHistory.txt: installed ballots cast otherwise"] == [
                "2026 S 49 member 209076 35|Yea now 35|Nay"] and \
            f"{counts}: 1, {NAMED}" in got["warnings"] and \
            "1 have other counts, 1 ballots cast otherwise" in "\n".join(
                DF.held_said(got["held"])), (got["stops"], got["told"], got["warnings"])
        # (The fixture holds no ballots of roll calls 45 to 47, so they do not
        # add up before or after: three tallies moved are one more than two.)
        only(stops(RollCallSummary=[put(ln, 7, "23") for ln in s[:3]] + s[3:]),
             "3 roll calls have other counts in the database, more than 2: 2026 S 45 24-0-24-0 "
             "now 24-0-23-0", "three roll calls' tallies were changed")
        # THE BALLOTS. Roll call 49's 24 were all Yea, and its counts say 24
        # to 0: one cast otherwise is a roll call whose ballots are not its
        # counts. One Yea made a Nay on each of the ten closest roll calls
        # passed, and changed ten tallies.
        h = tonight["RollCallHistory.txt"]
        only(stops(RollCallHistory=[put(h[0], 6, "Nay")] + h[1:]), "1 roll calls' Yea and Nay "
             "ballots are not their counts: 2026 S 49 says 24-0 and has 23 Yea and 1 Nay ballots",
             "one ballot was flipped")
        # Two cast by another member pass, and are named; a third stops.
        got = judged(RollCallHistory=[put(ln, 4, "9999") for ln in h[:2]] + h[2:])
        assert not got["stops"] and got["told"]["RollCallHistory.txt: installed ballots cast "
                                                "otherwise"] == [
            "2026 S 49 member 209076 35|Yea now 9999|Yea",
            "2026 S 49 member 209091 43|Yea now 9999|Yea"], (got["stops"], got["told"])
        only(stops(RollCallHistory=[put(ln, 4, "") for ln in h[:3]] + h[3:]),
             "RollCallHistory.txt: 3 installed ballots are cast otherwise in the database's, or by "
             "another member, more than 2: 2026 S 49 member 209076 35|Yea now |Yea",
             "3 ballots lost their member")
        # ROWS ADDED WERE NEVER JUDGED. Every ballot twice: 419 of 419 roll
        # calls read otherwise, 321-2 as 642-4, and it was installed.
        only(stops(RollCallHistory=h + h), "RollCallHistory.txt: 24 ballots are there more than "
             "once: 2026 S 49 209076, 2 times", "every ballot twice")
        # (made: a 25th ballot on roll call 49, of an employee number nobody has)
        got = stops(RollCallHistory=h + [put(put(h[0], 3, "990000"), 4, "990000")])
        assert len(got) == 2 and "RollCallHistory.txt: 1 ballots are on installed roll calls that " \
            "did not have them: 2026 S 49 member 990000" in got[0] and \
            "says 24-0 and has 25 Yea" in got[1], got
        # A wrong roll call filed in FRONT of the right one: these guards
        # kept the last copy of a key and rollcall_parser.py keeps the first.
        wrong = put(put(s[0], 4, "HB1442"), 11, "Inexpedient to Legislate")
        only(stops(RollCallSummary=[wrong] + s), "RollCallSummary.txt: 1 roll calls are there more "
             "than once: 2026 S 45, 2 times", "a roll call's summary twice, the first wrong")
        # A vote the export does not write: an unknown code passes through as
        # its own digit.
        has(stops(RollCallHistory=[put(h[0], 6, "8")] + h[1:]), "RollCallHistory.txt: 1 ballots "
            "are no vote the export writes: 2026 S 49 member 209076 reads '8'", "a ballot of code 8")
        assert (DF.ROLLCALLS_CHANGED_MOST, DF.BALLOTS_CHANGED_MOST) == (2, 2)
        # A NEW ROLL CALL. The Senate's 27th of 2026 killed SB 532, 16 to 8,
        # on 19 February: its summary row and its 24 ballots as the export
        # has them (the ballots are roll call 49's senators, the eight who
        # voted Nay marked). It passes, numbered under the chamber's top.
        rc27 = ("2026|S|27|2/19/2026 12:00:00 AM|SB532|16|8|24|0|||Inexpedient to Legislate|"
                "increasing the requirements of the education freedom savings account oversight "
                "committee and modifying the purpose of the committee.||2/19/2026 5:03:22 PM")
        nays = {"43", "9406", "9839", "9856", "10599", "10600", "11461", "11463"}
        b27 = [put(put(put(put(ln, 2, "27"), 5, "SB532"), 7, "2/19/2026 5:03:22 PM"), 6,
                   "Nay" if ln.split("|")[4] in nays else "Yea") for ln in h]
        got = judged(RollCallSummary=s + [rc27], RollCallHistory=h + b27)
        assert not got["stops"] and got["held"]["roll calls"] == {
            "calls": 1, "counts": 0, "ballots": 0, "new": 1, "strangers": 0, "unsummed": 0}, (
                got["stops"], got["held"])
        # An invented one was published as a veto overridden 300 to 19, and
        # 300 with no ballots at all passed. Its ballots are its counts -- or
        # a ballot or two from them: the Senate's counts are typed, 14 of 27
        # years' 9,146 roll calls do not add up, and every one of them since
        # 2001 by one ballot or two. Held to the ballot, the next such roll
        # call stopped the fallback, and every night after it. One a ballot
        # short passes, and is named; three short, or three roll calls each
        # one short, stops ...
        got = judged(RollCallSummary=s + [rc27], RollCallHistory=h + b27[1:])
        unsummed = "RollCallSummary.txt: new roll calls whose Yea and Nay ballots are not their counts"
        assert not got["stops"] and got["held"]["roll calls"]["unsummed"] == 1 and \
            got["told"][unsummed] == ["2026 S 27 says 16-8 and has 15 Yea and 8 Nay ballots"] and \
            f"{unsummed}: 1, {NAMED}" in got["warnings"], (got["stops"], got["told"])
        only(stops(RollCallSummary=s + [rc27], RollCallHistory=h + b27[3:]), "1 roll calls' Yea and "
             "Nay ballots are not their counts: 2026 S 27 says 16-8 and has 14 Yea and 7 Nay "
             "ballots, a new roll call", "a new roll call three ballots short")
        more = [(put(rc27, 2, n), [put(ln, 2, n) for ln in b27[1:]]) for n in ("27", "28", "29")]
        only(stops(RollCallSummary=s + [x for x, _ in more],
                   RollCallHistory=h + [ln for _, lines in more for ln in lines]),
             "3 roll calls' Yea and Nay ballots are not their counts: 2026 S 27 says 16-8 and has "
             "15 Yea and 8 Nay ballots, a new roll call", "three new roll calls a ballot short")
        assert DF.ROLLCALL_ADRIFT_MOST == 2
        only(stops(RollCallSummary=s + [rc27]), "2026 S 27 says 16-8 and has 0 Yea and 0 Nay "
             "ballots, a new roll call", "a new roll call with no ballots")
        # ... it is numbered on from its chamber's last, 52 here ...
        far = [put(ln, 2, "500") for ln in b27]
        only(stops(RollCallSummary=s + [put(rc27, 2, "500")], RollCallHistory=h + far),
             "RollCallSummary.txt: 1 new roll calls are numbered out of their chamber's run, which "
             "stands at 52: 2026 S 500", "a new roll call numbered 500")
        assert not stops(RollCallSummary=s + [put(rc27, 2, "194")],
                         RollCallHistory=h + [put(ln, 2, "194") for ln in b27]) and \
            DF.ROLLCALLS_NEW_MOST == 142, "a new roll call 142 past the chamber's last stopped"
        # ... taken by the time the views were asked ...
        only(stops(RollCallSummary=s + [put(rc27, 3, "10/4/2026 12:00:00 AM")],
                   RollCallHistory=h + b27), "RollCallSummary.txt: 1 new roll calls were taken at "
             "no time that reads as one, or after the views were asked: 2026 S 27 '10/4/2026 "
             "12:00:00 AM'", "a new roll call dated two days ahead")
        # ... with counts that are numbers, by members the roster's view knows ...
        has(stops(RollCallSummary=s + [put(rc27, 7, "")], RollCallHistory=h + b27),
            "RollCallSummary.txt: 1 new roll calls have a count that is not a number: 2026 S 27 "
            "16-8--0", "a new roll call with a count missing")
        only(stops(RollCallSummary=s + [rc27], RollCallHistory=h + [put(b27[0], 4, "")] + b27[1:]),
             "RollCallHistory.txt: 1 new roll calls have a ballot of a member the roster's view "
             "does not know: 2026 S 27", "a new roll call with a ballot of nobody")
        # ... and no more of them than a day takes (71 is the most in 27
        # years; 142 the ceiling, lowered to none here).
        at(ROLLCALLS_NEW_MOST=0)
        has(stops(RollCallSummary=s + [rc27], RollCallHistory=h + b27),
            "RollCallSummary.txt: 1 new roll calls, more than 0: 2026 S 27", "one new roll call "
            "against none")
        at()
        # On a "bill" no file knows it is named, and passes: a question on
        # the House's own rules is filed under HRULE64. (made: roll call 27
        # so filed)
        ruled = put(rc27, 4, "HRULE64")
        got = judged(RollCallSummary=s + [ruled], RollCallHistory=h + b27)
        assert not got["stops"] and got["told"]["RollCallSummary.txt: new roll calls on a bill no "
                                                "file knows"] == [
            "2026 S 27 HRULE64 Inexpedient to Legislate"], (got["stops"], got["told"])
        at(ROLLCALL_STRANGERS_MOST=0)
        only(stops(RollCallSummary=s + [ruled], RollCallHistory=h + b27), "RollCallSummary.txt: 1 "
             "new roll calls are on a bill that neither the docket nor LSRs.txt knows, more than "
             "0: 2026 S 27 HRULE64", "a new roll call on an unknown bill against none")
        at()
        # Ballots on a roll call the summary does not hold.
        only(stops(RollCallHistory=h + b27), "RollCallHistory.txt: 24 ballots are on a roll call "
             "RollCallSummary.txt does not hold: 2026 S 27", "ballots with no roll call")

        # ---- THE ROSTER -------------------------------------------------
        # The 24 senators. (The e-mail addresses are made up, so that none a
        # scraper could use is in the repository; the rest of each row is
        # the General Court's.) Who a member is: two may change, and are
        # named; eight passed, and nobody was told which.
        p = tonight["legislators.txt"]

        def swapped(n):
            return [put(ln, 8, "D" if ln.split("|")[8].upper() == "R" else "R") for ln in p[:n]] + p[n:]
        got = judged(legislators=swapped(2))
        assert not got["stops"] and got["told"]["legislators.txt: installed members with another "
                                                "name, chamber, county, district or party"] == [
            "member 11460, McGough|Tim||S|6|11|R now McGough|Tim||S|6|11|D",
            "member 11461, Reardon|Tara||S|7|15|D now Reardon|Tara||S|7|15|R"], (got["stops"], got["told"])
        only(stops(legislators=swapped(3)), "legislators.txt: 3 installed members have another "
             "name, chamber, county, district or party in the database's, more than 2: member "
             "11460, McGough|Tim||S|6|11|R now McGough|Tim||S|6|11|D",
             "3 members' parties were swapped")
        only(stops(legislators=[put(ln, 7, "1") for ln in p]), "more than 2",
             "every senator was put in district 1")
        at(ROSTER_TOUCHED_MOST=3)
        got = judged(legislators=[put(ln, 14, "") for ln in p[:3]] + p[3:])
        assert not got["stops"] and got["told"]["legislators.txt: installed members with another "
                                                "seat, address or e-mail"][0] == \
            "member 11460, McGough|Tim: column 15", (got["stops"], got["told"])
        only(stops(legislators=[put(ln, 14, "") for ln in p[:4]] + p[4:]), "legislators.txt: 4 "
             "installed members changed in a column the build reads, more than 3",
             "4 members lost their e-mail address")
        # ANOTHER SEAT OR E-MAIL ADDRESS THAT READS AS ONE is named and not
        # counted: every member's address moved to another domain in one
        # night stopped the fallback, and every night after it. A blank is
        # not an address (above), and nor is what lands in that column when
        # a row is moved along: a ZIP code.
        moved = [put(ln, 14, ln.split("|")[14].replace("@example.gov", "@example.org")) for ln in p]
        got = judged(legislators=moved)
        label = "legislators.txt: installed members with another seat, address or e-mail"
        assert not got["stops"] and got["held"]["legislators.txt"] == {
            "who": 0, "any": 24, "seat_or_mail": 24, "left": 0, "joined": 0} and \
            len(got["told"][label]) == 24 and f"{label}: 24, {NAMED}" in got["warnings"] and \
            not any("example.org" in x for x in got["told"][label]) and \
            "24 changed at all (24 of them in a seat or an e-mail address only)" in "\n".join(
                DF.held_said(got["held"])), (got["stops"], got["held"]["legislators.txt"])
        assert not stops(legislators=[put(ln, 5, "17") for ln in moved]), \
            "every senator given a seat number, and another address, stopped the night"
        only(stops(legislators=[put(ln, 14, "03301") for ln in p[:4]] + p[4:]), "legislators.txt: 4 "
             "installed members changed in a column the build reads, more than 3",
             "4 members with a ZIP code for an e-mail address")
        only(stops(legislators=[put(ln, 10, "another room") for ln in moved[:4]] + moved[4:]),
             "legislators.txt: 4 installed members changed in a column the build reads, more than "
             "3: member 11460, ", "4 members with another address line, among 24 with another e-mail")
        # The mail label is read by nothing.
        assert not stops(legislators=[put(ln, 9, "another label") for ln in p])
        at()
        assert (DF.ROSTER_CHANGED_MOST, DF.ROSTER_TOUCHED_MOST) == (2, 40)
        # Who is on it. Four may leave and four join in a night, each named;
        # eight former members marked sitting passed. (The 2% the count may
        # move by is less than one senator of 24, so it is set aside here; it
        # is tried on a roster of 100 in the check before this one. The
        # senators have no row of LsrsOnly.txt that the fixture's others
        # depend on but their own, which go with them.)
        at(ROSTER_TOLERANCE=1.0)
        mine = lambda who: [ln for ln in tonight["LsrsOnly.txt"]          # noqa: E731
                            if ln.split("|")[1] not in {x.split("|")[0] for x in who}]
        got = judged(legislators=p[4:], LsrsOnly=mine(p[:4]))
        assert not got["stops"] and got["held"]["legislators.txt"]["left"] == 4 and got["told"][
            "legislators.txt: installed members not on the database's roster"][0] == \
            "member 11460, McGough|Tim||S|6|11|R", (got["stops"], got["told"])
        only(stops(legislators=p[5:], LsrsOnly=mine(p[:5])), "legislators.txt: 5 installed members "
             "not on the database's roster, more than 4: member 11459, McConkey|Mark||S|2|3|R",
             "5 members left in a night")
        # (made: former senators marked sitting)
        back = [put(put(put(ln, 0, str(9000 + i)), 1, f"Former{i}"), 14, f"f{i}@example.gov")
                for i, ln in enumerate(p[:5])]
        got = judged(legislators=p + back[:4])
        assert not got["stops"] and got["told"]["legislators.txt: members on the database's roster "
                                                "and not the installed one"][0] == \
            "member 9000, Former0|Tara||S|7|15|D", (got["stops"], got["told"])
        only(stops(legislators=p + back), "legislators.txt: 5 members on the database's roster and "
             "not the installed one, more than 4: member 9000, Former0|Tara||S|7|15|D",
             "5 members joined in a night")
        only(stops(legislators=p + [put(back[0], 1, "")]), "legislators.txt: 1 new members have no "
             "last name, or a chamber that is neither H nor S", "a new member with no name")
        at()
        has(stops(legislators=p + [put(p[0], 8, "R")]), "legislators.txt: 1 members are there "
            "more than once: 11461, 2 times", "a member twice, the second with another party")
        assert DF.ROSTER_MOVED_MOST == 4

        # ---- LsrSponsors.txt --------------------------------------------
        # A row there last night is there tonight: five may go, and are
        # named. 170 went, the sponsors of bills LsrsOnly.txt does not list.
        sp = tonight["LsrSponsors.txt"]
        got = judged(LsrSponsors=sp[5:])
        assert not got["stops"] and got["held"]["LsrSponsors.txt"] == {"new": 0, "late": 0, "gone": 5} \
            and got["told"]["LsrSponsors.txt: installed rows gone (year, request, place, member, "
                            "prime)"] == sp[:5], (got["stops"], got["told"])
        only(stops(LsrSponsors=sp[6:]), "LsrSponsors.txt: 6 installed rows are not in the "
             "database's, more than 5: 2026|2187|1|43|1", "6 sponsors' rows gone")
        # ROWS ADDED. 5,000 sponsors nobody had signed passed. A new row on a
        # bill whose docket began more than 30 days before is a sponsor added
        # to a bill long since introduced: five may be, and are named. SB
        # 633's docket began in March, in the fixture. (made: senators who
        # did not sponsor it)
        added = [f"2026|2187|{10 + i}|{m}|0" for i, m in enumerate(
            ("35", "8739", "9839", "9845", "10698", "10607"))]
        got = judged(LsrSponsors=sp + added[:5])
        label = ("LsrSponsors.txt: new rows on a bill whose docket began more than 30 days "
                 "before (year, request, place, member, prime)")
        assert not got["stops"] and got["held"]["LsrSponsors.txt"] == {"new": 5, "late": 5, "gone": 0} \
            and got["told"][label] == added[:5], (got["stops"], got["held"], got["told"])
        only(stops(LsrSponsors=sp + added), "LsrSponsors.txt: 6 new rows are on a bill whose docket "
             "began more than 30 days before, more than 5: 2026|2187|10|35|0",
             "6 sponsors added to SB 633")
        # A sponsor of a bill made the day before is the bill's own. (made:
        # HB 9999, its record and its first docket row)
        new_bill = dict(Docket=d + [stray], LSRs=r + [brought])
        got = judged(LsrSponsors=sp + [f"2026|9999|{i}|{m}|{int(i == 1)}" for i, m in enumerate(
            ("35", "8739", "9839", "9845", "10698", "10607"), 1)], **new_bill)
        assert not got["stops"] and got["held"]["LsrSponsors.txt"] == {"new": 6, "late": 0, "gone": 0}, \
            (got["stops"], got["held"]["LsrSponsors.txt"])
        at(SPONSORS_NEW_MOST=5)
        only(stops(LsrSponsors=sp + [f"2026|9999|{i}|{m}|0" for i, m in enumerate(
            ("35", "8739", "9839", "9845", "10698", "10607"), 1)], **new_bill),
            "LsrSponsors.txt: 6 new rows, more than 5: 2026|9999|1|35|0", "6 new sponsors against 5")
        at()
        # Every row twice; a second prime sponsor.
        has(stops(LsrSponsors=sp + sp), "LsrSponsors.txt: 18 sponsors' rows (year, request, member) "
            "are there more than once: 2026 2083 11461, 2 times", "every sponsor's row twice")
        has(stops(LsrSponsors=sp + ["2026|2187|10|35|1"]), "LsrSponsors.txt: 1 requests have more "
            "than one prime sponsor: 2026-2187, 2", "a second prime sponsor of SB 633")
        assert (DF.SPONSORS_GONE_MOST, DF.SPONSORS_LATE_MOST, DF.SPONSORS_NEW_MOST) == (5, 5, 2400)

        # ---- LsrsOnly.txt -----------------------------------------------
        # A sponsor of a numbered bill, a sitting member, is there tonight or
        # the night stops; "Prime" turned to "Sponsor" is that row gone.
        o = tonight["LsrsOnly.txt"]
        only(stops(LsrsOnly=o[1:]), "LsrsOnly.txt: 1 installed rows of members still sitting, each "
             "on a numbered bill, are not in the database's: 26-2083|11461|1272|2026|Prime|SB632|S",
             "one sponsor of SB 632 was dropped")
        only(stops(LsrsOnly=[put(ln, 4, "Sponsor") for ln in o]), "LsrsOnly.txt: 4 installed rows",
             "no row was marked Prime")
        has(stops(LsrsOnly=o + [o[0]]), "LsrsOnly.txt: 1 sponsors' rows (request, member) are "
            "there more than once: 26-2083 11461, 2 times", "a sponsor's row twice")
        # The ten rows the view cannot give -- the senators' on the two
        # requests with no bill number -- are what the share that may go is
        # for. In the real file they are 13 of 6,963, inside its 2%; of these
        # 28 they are a third, so the share is tried at a half here.
        bare = {"LsrsOnly.txt": real["LsrsOnly.txt"] + part["only_bare"]}
        only(stops(bare), "LsrsOnly.txt: 10 installed rows with no bill number are not in the "
             "database's, more than 2% of the 28 rows of members still sitting",
             "10 of 28 rows gone, each with no bill number")
        at(SPONSORS_KEPT_LEAST=0.5)
        got = judged(bare)
        assert not got["stops"] and got["held"]["LsrsOnly.txt"] == {
            "gone_numbered": 0, "gone_unnumbered": 10, "new": 0}, (
                got["stops"], got["held"]["LsrsOnly.txt"])
        only(stops(bare, LsrsOnly=o[1:]), "each on a numbered bill",
             "the allowance for rows with no bill number let a sponsor of a numbered bill go")
        at()

        # ---- WHAT NO EXPORT HOLDS ---------------------------------------
        # A view written in another code page went through with every byte
        # that would not decode replaced: U+FFFD in fifteen titles, two
        # members' names and 96 sponsors' rows. Read as Windows-1252 and
        # written back, a no-break space is two characters. Roll call 49's
        # real title has a no-break space, and is no such thing.
        assert "\u00a0" in tonight["RollCallSummary.txt"][4]
        only(stops(legislators=[put(p[0], 1, "Choini\ufffdre")] + p[1:]), "legislators.txt: 1 "
             "characters read in the wrong encoding, which the installed file has none of: "
             "'11461|Choini\\ufffdre|Tara||S|", "a name with U+FFFD in it")
        got = stops(RollCallSummary=[ln.replace("\u00a0", "\u00c2\u00a0") for ln in s])
        assert len(got) == 1 and "RollCallSummary.txt: 1 characters read in the wrong encoding" \
            in got[0] and "\\xc2\\xa0and ph" in got[0], got
        has(stops(legislators=[put(p[0], 3, "NULL")] + p[1:]), "legislators.txt: 1 fields read "
            "NULL, None, True or False, which no field of an export does: 11461|Reardon|Tara|NULL|S",
            "a middle name that reads NULL")
        has(stops(LsrSponsors=[put(ln, 4, {"1": "True", "0": "False"}[ln.split("|")[4]]) for ln in sp]),
            "LsrSponsors.txt: 18 fields read NULL, None, True or False", "the prime flag as a word")
        # A MEMBER MAY BE NAMED TRUE. The General Court's own table holds a
        # representative of that name (PersonID 908, of Sandown), and the
        # night he sat again was a night stopped. No bit lands in a name; in
        # any other column of the roster the word is still one. (made: a
        # senator under his name; and her county as the word)
        got = judged(legislators=[put(put(p[0], 1, "True"), 2, "Chris")] + p[1:])
        assert not got["stops"] and got["held"]["legislators.txt"]["who"] == 1, got["stops"]
        has(stops(legislators=[put(p[0], 6, "True")] + p[1:]), "legislators.txt: 1 fields read "
            "NULL, None, True or False, which no field of an export does: 11461|Reardon|Tara||S||True",
            "a county that reads True")
        # AN ACCENTED LETTER BEFORE A CURLY QUOTE is no wrong encoding: one
        # character of the second kind after any first one was taken for it,
        # and a new row of Rep. C\u00f4t\u00e9\u2019s would have stopped the night. A character
        # of three bytes read as Windows-1252 is three, and still stops.
        # (made: both rows)
        assert not stops(Docket=d + [put(put(session, 2, "10/1/2026 12:45:00 PM"), 5,
                                         "Floor Amendment by Rep. C\u00f4t\u00e9\u2019s motion: AA VV")]), \
            "a new docket row with an accented letter before a curly quote stopped the night"
        only(stops(Docket=d + [put(put(session, 2, "10/1/2026 12:45:00 PM"), 5,
                                   "Floor Amendment by Rep. C\u00c3\u00b4t\u00c3\u00a9\u00e2\u20ac\u2122s motion: AA VV")]),
             "Docket.txt: 3 characters read in the wrong encoding", "that row read as Windows-1252")

        # ---- WHAT A NIGHT NAMES, AND HOW MANY ---------------------------------
        # Every row behind a count that sits under a handful's ceiling is
        # named: the largest of those ceilings is 50, and so is the most a
        # count names. It was 20 under ceilings of 40, and the warning said
        # "each named" of 35 rows when 20 were. A longer list names its first
        # 50, and the warning says so.
        assert DF.TOLD_MOST == 50 >= max(DF.DOCKET_REWORDED_MOST, DF.DOCKET_REMARKED_MOST,
                                         DF.DOCKET_LATE_MOST, DF.ROSTER_TOUCHED_MOST), DF.TOLD_MOST
        assert DF._name([str(i) for i in range(50)]) == [str(i) for i in range(50)] and \
            DF._name([str(i) for i in range(53)]) == [str(i) for i in range(50)] + ["... and 3 more"]
        assert DF._named(50) == NAMED and DF._named(51) == NAMED.replace(
            "each named", "the first 50 named") != NAMED, (DF._named(50), DF._named(51))

        # ---- A NIGHT'S CEILINGS, and the nights the installed files have ---
        assert [DF._ceiling(1000, n) for n in (1, 2, 3, 4, 5, 7, 10, 14, 30)] == [
            1000, 1500, 1700, 2200, 2200, 2900, 3100, 3600, 3600], "SPAN moved"
        assert [DF._nights(f) for f in ({}, None, {"nights": 3}, {"nights": True}, {"nights": 0},
                                        {"nights": "4"})] == [1, 1, 3, 1, 1, 1]
        assert judged(facts=dict(ASKED, nights=3))["held"]["nights"] == 3 and \
            "the installed files are 3 nights old, and a night's ceilings are 1.7 times a day's" in \
            "\n".join(DF.held_said(judged(facts=dict(ASKED, nights=3))["held"]))
    finally:
        at()
    assert (DF.DOCKET_REMARKED_MOST, DF.LSR_ALONE_MOST, DF.ROLLCALL_ADRIFT_MOST) == (50, 600, 2), \
        "a ceiling of the third pass moved: 50 rows reworded behind a mark, 600 first referrals " \
        "ahead of the docket, and a new roll call two ballots from its counts"
    assert (DF.DOCKET_NEW_A_DAY_MOST, DF.DOCKET_LATE_MOST, DF.DOCKET_AHEAD_MOST,
            DF.DOCKET_CITED_MOST, DF.DOCKET_MARKED_MOST, DF.DOCKET_REWORDED_MOST,
            DF.DOCKET_GONE_MOST, DF.LSR_NEW_MOST, DF.LSR_RETITLED_MOST, DF.LSR_REWRITTEN_MOST,
            DF.LSR_CHANGED_MOST, DF.LSR_UNBACKED_MOST, DF.ROLLCALL_STRANGERS_MOST,
            DF.SPONSORS_KEPT_LEAST) == (1000, 40, 80, 1000, 100, 40, 5, 400, 40, 170, 700, 5, 10,
                                        0.98), \
        "a ceiling moved: each is twice the busiest real day measured on 2 October 2026, or a " \
        "handful above a measured nothing"
    assert (DF.LSR_ACTIVE_DAYS, DF.SPONSOR_LATE_DAYS, DF.DOCKET_AHEAD_SLACK,
            DF.ROLLCALL_AHEAD_SLACK) == (timedelta(days=14), timedelta(days=30),
                                         timedelta(days=14), timedelta(days=1))
    return "ok", ("a night of real rows passes, says what it counted and names the two rows that "
                  "changed; a Senate row entered late passes and is named, a House one stops; a "
                  "stranger's row, one with no words, an unread entry time, a row a year ahead, "
                  "a sixth row in a day or a ninth in a night, a row six times, a fourth "
                  "citation, a second rewording, a record changed at rest beyond a handful, "
                  "another bill number, a second new title, a ballot flipped, added or twice, a "
                  "roll call filed twice, a tally changed with no ballot, a new roll call three "
                  "ballots from its counts, a third "
                  "member's party, a fifth member joined or left, six sponsors gone or added to "
                  "an old bill, a character in the wrong encoding and a field that reads NULL "
                  "each stop it; a row reworded behind a mark, a first referral ahead of its "
                  "docket row, a title replaced, a tally corrected with its ballot, a new roll "
                  "call a ballot short and every member's e-mail address at another domain pass "
                  "and are named; a member may be named True")


class _DbdayProc:
    """A PowerShell that never started, answering as probe_db's bridges read one."""

    def __init__(self, lines, rc=0):
        import io
        self.stdout, self.stderr = iter([x + "\r\n" for x in lines]), io.StringIO("")
        self.returncode, self._rc = None, rc

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = self._rc if self.returncode is None else self.returncode
        return self.returncode

    def kill(self):
        self.returncode = -9


@check("build", "a failed connection to the General Court's database is held, with a record of "
       "its own that expires and lengthens, and every query asks it first",
       needs=("probe_db", "nightly", "cloud"))
def _sql_hold(PD, NI, CL):
    """refusal.py is about the web server's firewall. The SQL host is another
    server with another failure, and since 1 October 2026 the night falls back
    on it, so it has a record of its own, archive/sql-held.json:

      - recorded on GitHub's machine only, when a CONNECTION fails, through
        any of probe_db's bridges; nowhere else, where the laptop's fetches
        would otherwise write a state file the night owns
      - while it stands every bridge exits 5 before PowerShell starts, and
        leaves what was on disk as it was -- read from the source as well, so
        a bridge added later that starts PowerShell without asking fails here
      - it expires by itself and lengthens: 20, 44, 92 and then 164 hours, a
        day, two, four and a week less four hours, so the night after finds
        it over; a connection that opens ends it and the count starts again
      - a query that fails on an open connection is no hold
      - a login the server refuses is recorded as that, expires and lengthens
        like any other, and is over at once when the credentials in
        probe_db.py change; a database the server could not open for the
        login (its error 4060, worded with the same last line) is a
        connection failure and no refused login. A person lifts either here
        with --clear-hold, which asks nobody
      - it travels in the kit's state list, and nightly.py names the same file
        and passes its full path to every step it starts, because take_views
        runs its fetch in a scratch folder; with a hold standing take_views
        asks nothing
    """
    import ast
    import contextlib
    import io
    import refusal
    import time as _time
    import types
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-sqlhold-"))
    saved = (PD.HELD, PD.subprocess.run, PD.child.popen, PD.PASSWORD, refusal.MARK, refusal.LOCK,
             NI.run, NI.LOG, NI.QUIET, sys.argv)
    saved_env = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", PD.HELD_ENV, "GITHUB_RUN_ID")}
    started = []

    def answers(lines, rc=0):
        def popen(cmd, **kw):
            started.append(cmd[-1])
            return _DbdayProc(lines, rc)
        return popen

    def never(*_a, **_k):
        raise AssertionError("PowerShell was started while a hold on the SQL host stood")

    def exits(fn):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            try:
                fn()
            except SystemExit as e:
                return e.code, err.getvalue()
        return None, err.getvalue()

    def record():
        return json.loads(PD.HELD.read_text(encoding="utf-8"))

    def lapse():
        d = record()
        d["until"] = _time.time() - 60
        PD.HELD.write_text(json.dumps(d), encoding="utf-8")

    def counted(lines, rc=0):
        PD.child.popen = answers(lines, rc)
        return PD.run_to_file_counted("x", "SELECT COUNT(*) FROM v", "SELECT a FROM v", tmp / "v.psv")

    FAIL = ["CONNECT_FAIL A network-related or instance-specific error occurred (fixture)"]
    try:
        os.chdir(tmp)
        for k in saved_env:
            os.environ.pop(k, None)
        refusal.MARK, refusal.LOCK = Path("archive") / "refused.json", Path("archive") / ".lock"
        PD.HELD = Path("archive") / "sql-held.json"
        assert PD.hold_file() == PD.HELD and PD.hold_standing() is None

        # Off GitHub's machine a failed connection is reported and not recorded.
        count, rows, err = counted(FAIL, 3)
        assert err and err.startswith("CONNECT_FAIL") and not PD.HELD.exists(), \
            "a failed connection was recorded off GitHub's machine, where the night owns the record"

        # On it, it is: for 20 hours, and every bridge then stops before PowerShell.
        os.environ["GITHUB_ACTIONS"] = "true"
        count, rows, err = counted(FAIL, 3)
        d = record()
        assert err.startswith("CONNECT_FAIL") and d["held"] and d["kind"] == "connection" \
            and d["nights"] == 1 and d["hours"] == 20 and \
            abs(d["until"] - _time.time() - 20 * 3600) < 60, d
        assert PD.hold_standing() and PD.hold_standing(_time.time() + 21 * 3600) is None
        PD.subprocess.run = PD.child.popen = never
        out = tmp / "out.psv"
        out.write_text("what was on disk\n", encoding="utf-8")
        for name, bridge in (
                ("run", lambda: PD.run("x", [("q", "SELECT 1")])),
                ("run_to_file", lambda: PD.run_to_file("x", "SELECT 1", out)),
                ("run_to_file_counted", lambda: PD.run_to_file_counted("x", "SELECT 1", "SELECT 1", out)),
                ("run_to_jsonl", lambda: PD.run_to_jsonl("x", "SELECT 1", "SELECT 1", out))):
            code, said = exits(bridge)
            assert code == PD.SQL_HELD == 5 and "could not be connected to" in said, (name, code, said)
            assert out.read_text(encoding="utf-8") == "what was on disk\n", \
                f"{name} touched its output file while the hold stood"
        os.environ.pop("GITHUB_ACTIONS")
        code, _ = exits(lambda: PD.run_to_file("x", "SELECT 1", out))
        assert code == 5, "the hold on file was not honoured off GitHub's machine"
        os.environ["GITHUB_ACTIONS"] = "true"

        # It lengthens with each night it fails again, to a week and no further.
        for nights, hours in ((2, 44), (3, 92), (4, 164), (5, 164)):
            lapse()
            assert PD.hold_standing() is None, "an expired hold still stood"
            counted(FAIL, 3)
            d = record()
            assert (d["nights"], d["hours"]) == (nights, hours), d
        assert PD.HOLD_HOURS == (20, 44, 92, 164)

        # A connection that opens ends it -- whether its query then failed or
        # not -- and the count starts again.
        lapse()
        count, rows, err = counted(["COUNT 2", "QUERY_FAIL Execution Timeout Expired (fixture)"], 4)
        assert err.startswith("QUERY_FAIL") and record()["held"] is False and \
            record()["nights"] == 0, record()
        counted(FAIL, 3)
        assert record()["nights"] == 1
        lapse()
        count, rows, err = counted(["COUNT 2", "DONE 2"])
        assert (count, rows, err) == (2, 2, None) and record()["held"] is False, (count, rows, err)
        # ... and a query that fails with no hold on file records none.
        PD.HELD.unlink()
        count, rows, err = counted(["COUNT 2", "QUERY_FAIL Execution Timeout Expired (fixture)"], 4)
        assert err.startswith("QUERY_FAIL") and not PD.HELD.exists(), \
            "a query that failed on an open connection was recorded as a hold"

        # The other two bridges record one as well.
        PD.subprocess.run = lambda *a, **k: types.SimpleNamespace(
            stdout="CONNECT_FAIL no route (fixture)", stderr="", returncode=3)
        got, err = PD.run("x", [("q", "SELECT 1")])
        assert got is None and record()["held"] and record()["nights"] == 1, record()
        PD.HELD.unlink()
        PD.child.popen = answers(FAIL, 3)
        rows, err = PD.run_to_file("x", "SELECT 1", tmp / "w.psv")
        assert rows is None and err.startswith("CONNECT_FAIL") and record()["held"], err
        PD.HELD.unlink()

        # A LOGIN the server rejects is recorded as that, and expires and
        # lengthens like any other; it is over at once when the credentials
        # change. As first written it stood for ever, and nothing on GitHub's
        # machine could lift it.
        REFUSED = ["CONNECT_FAIL Login failed for user 'publicuser'. (fixture)"]
        counted(REFUSED, 3)
        d = record()
        assert d["kind"] == "login" and (d["nights"], d["hours"]) == (1, 20) and \
            abs(d["until"] - _time.time() - 20 * 3600) < 60, d
        assert PD.hold_standing() and PD.hold_standing(_time.time() + 21 * 3600) is None, \
            "a refused login is held with no end, and nothing on GitHub's machine can lift it"
        said = PD.hold_sentence(d)
        assert "refused the published login" in said and d["until_at"] in said and \
            "credentials in probe_db.py are changed" in said and "--clear-hold" not in said, said
        PD.PASSWORD = saved[3] + "-changed"
        assert PD.hold_standing() is None, "a login hold outlived the credentials it was about"
        PD.PASSWORD = saved[3]
        assert PD.hold_standing()
        lapse()
        counted(REFUSED, 3)
        assert (record()["kind"], record()["nights"], record()["hours"]) == ("login", 2, 44), record()
        # A record with no time it ends holds nothing, whatever its kind.
        PD.HELD.write_text(json.dumps({"held": True, "kind": "login", "login": PD._login(),
                                       "nights": 1, "at": "t"}), encoding="utf-8")
        assert PD.hold_standing() is None, "a hold with no end stands"
        PD.HELD.unlink()

        # A database that is offline or being restored (the server's error
        # 4060) ends its message with the same "Login failed for user" line.
        # It is not the login being refused: a connection failure like any
        # other, and its sentence does not send a person to read the PDF.
        OFFLINE = ('CONNECT_FAIL Exception calling "Open" with "0" argument(s): "Cannot open '
                   'database "NHLegislatureDB" requested by the login. The login failed. Login '
                   "failed for user 'publicuser'.\" (fixture)")
        counted([OFFLINE], 3)
        d = record()
        assert d["kind"] == "connection" and "login" not in d and d["hours"] == 20 and \
            "refused the published login" not in PD.hold_sentence(d), (
                "a database that could not be opened was recorded as a refused login", d)
        assert PD.login_refused(REFUSED[0]) and not PD.login_refused(OFFLINE) and \
            not PD.login_refused(FAIL[0]) and not PD.login_refused("The login failed.")

        # A person lifts it here, and that asks nobody.
        PD.subprocess.run = PD.child.popen = never
        for flag, word in (("--hold", "Standing:"), ("--clear-hold", "Lifted here")):
            sys.argv = ["probe_db.py", flag]
            said = io.StringIO()
            with contextlib.redirect_stdout(said):
                assert PD.main() == 0
            assert word in said.getvalue(), said.getvalue()
        assert PD.hold_standing() is None and record()["by"] == "a person"

        # Every function in probe_db that starts PowerShell asks hold_check()
        # first. The reader is tried first on one that does not.
        SPAWN = {("child", "popen"), ("subprocess", "run"), ("subprocess", "Popen")}

        def unheld(tree):
            bad, starts = [], []
            for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
                calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
                spawns = [n.lineno for n in calls if isinstance(n.func, ast.Attribute)
                          and isinstance(n.func.value, ast.Name)
                          and (n.func.value.id, n.func.attr) in SPAWN]
                if not spawns:
                    continue
                starts.append(fn.name)
                asks = [n.lineno for n in calls if isinstance(n.func, ast.Name)
                        and n.func.id == "hold_check"]
                if not asks or min(asks) > min(spawns):
                    bad.append(fn.name)
            return bad, starts
        probe = ast.parse("def fine(x):\n    hold_check('q')\n    child.popen(x)\n\n"
                          "def late(x):\n    child.popen(x)\n    hold_check('q')\n\n"
                          "def bare(x):\n    subprocess.run(x)\n")
        assert unheld(probe)[0] == ["late", "bare"], unheld(probe)
        bad, starts = unheld(_parsed(PD.__file__))
        assert {"run", "run_to_file", "_bridge"} <= set(starts) and not bad, (
            f"probe_db starts PowerShell without asking hold_check() first in {bad}")

        # One file, named the same everywhere, and carried between nights.
        assert Path(NI.SQL_HELD) == saved[0] and NI.SQL_HELD_ENV == PD.HELD_ENV, \
            "nightly.py and probe_db.py do not name the same hold"
        os.environ[PD.HELD_ENV] = str(tmp / "elsewhere.json")
        assert PD.hold_file() == tmp / "elsewhere.json"
        os.environ.pop(PD.HELD_ENV)
        src = _source(NI.__file__)
        assert re.search(r"child\.popen\(\[sys\.executable, \"-u\"\] \+ args,[^)]*"
                         r"env=\{SQL_HELD_ENV: str\(SQL_HELD\.resolve\(\)\)\}", src, re.S), \
            "nightly.run() no longer tells the steps it starts where the SQL host's hold is"
        kit = json.loads((Path(here) / CL.KIT_FILE).read_text(encoding="utf-8"))
        assert any(s["path"] == saved[0].as_posix() and s["key"] == "sql-held.json"
                   for s in kit["state"]), "the kit's state list does not carry the SQL host's hold"

        # With a hold standing the night's own study views ask nothing.
        counted(FAIL, 3)
        NI.LOG, NI.QUIET = [], True
        NI.run = never
        with contextlib.redirect_stdout(io.StringIO()):
            got = NI.take_views(("StatStudMeetings",), "the study committees' meetings")
        assert got == {"StatStudMeetings": NI.STUDY_HELD} and NI.STUDY_HELD == (
            "not taken: a hold on the General Court's database is on file"), got
    finally:
        os.chdir(here)
        (PD.HELD, PD.subprocess.run, PD.child.popen, PD.PASSWORD, refusal.MARK, refusal.LOCK,
         NI.run, NI.LOG, NI.QUIET, sys.argv) = saved
        for k, val in saved_env.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a failed connection is held on GitHub's machine for 20, 44, 92 then 164 hours; "
                  "every bridge stops at it before PowerShell and leaves its file alone; an "
                  "opened connection ends it, a failed query is none; a refused login expires "
                  "as any other does and ends when the credentials change, and a database that "
                  "would not open is not one; the kit carries it and the night names it")


def _dbday_call_views(calls):
    return [c["view"] for c in calls]


def _dbday_bridge(P, DF, calls, how):
    """child.popen for probe_db, answering fetch_day_db.py's statements out of
    the fixture's views as PS_STREAM_COUNTED would. how["short"][view] rows
    fewer arrive than the server counted, and how["more"][view] rows more (the
    count is asked first, and those were entered since); a view in
    how["refuse"] cannot connect; one in how["fail"] connects and its query
    fails; one in how["empty"] answers with no rows at all."""
    def popen(cmd, **kw):
        script, env = cmd[-1], dict(kw.get("env") or {})
        view = re.search(r"FROM \[(\w+)\]", env.get("GR_COUNT") or "").group(1)
        calls.append({"view": view, "script": script, "count": env.get("GR_COUNT"),
                      "sql": env.get("GR_SQL"), "out": env.get("GR_OUT")})
        if view in how.get("refuse", ()):
            return _DbdayProc(["CONNECT_FAIL A network-related error occurred (fixture)"], 3)
        if view in how.get("fail", ()):
            return _DbdayProc(["COUNT 3", "QUERY_FAIL Execution Timeout Expired (fixture)"], 4)
        assert script == P.PS_STREAM_COUNTED, "fetch_day_db.py went through another bridge"
        rows = [] if view in how.get("empty", ()) else _DBDAY_VIEWS[view]
        sent = rows[:max(0, len(rows) - how.get("short", {}).get(view, 0))]
        with open(env["GR_OUT"], "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(r + "\r\n" for r in sent))
        counted = len(rows) - how.get("more", {}).get(view, 0)
        return _DbdayProc([f"COUNT {counted}", f"DONE {len(sent)}"], 0)
    return popen


@check("build", "fetch_day_db asks for nothing but SELECT of eleven named views, one connection "
       "each, writes only under .night/dbday, and stops at a hold, a failed connection or a "
       "short view", needs=("fetch_day_db", "dayfiles_from_db", "probe_db", "nightly"))
def _fetch_day_db(FD, DF, P, NI):
    """fetch_day_db.py is the one new script that asks somebody else's server,
    and nothing here lets it: probe_db's child.popen is stood in for, and
    every statement it would have sent is read.

      - --plan prints the statements and starts nothing
      - a whole run is eleven connections, the six views smallest first and
        then the five lookups, PAUSE apart, each through the counted bridge:
        SELECT COUNT(*) and one SELECT of that view alone, every column named
        in the dump's order, the rows of the installed files' first year on
        where the view has a year, and no other statement
      - it writes under .night/dbday and nowhere else: the views, source.json,
        and by hand the rebuilt files to read; the installed files and db/
        are left exactly as they were
      - a view that arrives short, or whose query fails, ends the run with
        nothing more asked, unless it is a lookup, which is said and passed;
        a view with more rows than the server counted a moment before is
        whole, and said
      - a connection that fails ends it at once, is recorded on GitHub's
        machine as the host's hold, and the next run asks nothing
      - another fetch holding archive/.lock stops it before it asks; the web
        server's refusal record does not -- a different server -- and
        nightly.py, which will not start it with one on file, is held to that
        by its own check
    """
    import ast
    import contextlib
    import hashlib
    import io
    import refusal
    import types
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-fetchday-"))
    saved = (P.run, P.child, P.HELD, FD.time, sys.argv, refusal.MARK, refusal.LOCK)
    saved_env = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", P.HELD_ENV, "GITHUB_RUN_ID")}
    calls, how, sleeps = [], {}, []

    def nothing(*_a, **_k):
        raise AssertionError("something was asked for that should not have been")

    def go(*argv):
        sys.argv = ["fetch_day_db.py", *argv]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = FD.main()
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def tree():
        return {p.relative_to(tmp).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in tmp.rglob("*") if p.is_file()}
    try:
        os.chdir(tmp)
        for k in saved_env:
            os.environ.pop(k, None)
        refusal.MARK, refusal.LOCK = Path("archive") / "refused.json", Path("archive") / ".lock"
        P.HELD = Path("archive") / "sql-held.json"
        FD.time = types.SimpleNamespace(sleep=sleeps.append, time=__import__("time").time)
        _dbday_install(tmp)
        Path("db").mkdir()
        Path("db/Docket.psv").write_text("the laptop's dump\n", encoding="utf-8")
        before = tree()

        P.run, P.child = nothing, types.SimpleNamespace(popen=nothing)
        code, said = go("--plan")
        assert code == 0 and "Nothing was asked and nothing was written" in said and \
            tree() == before, said[-300:]

        # A refusal from the web server on file does not stop it: a different
        # server. (nightly.py will not start it with one on file.)
        Path("archive").mkdir()
        Path("archive/refused.json").write_text(json.dumps(
            {"at": "t", "epoch": __import__("time").time(), "where": "preflight", "why": "403"}),
            encoding="utf-8")
        before = tree()
        P.child = types.SimpleNamespace(popen=_dbday_bridge(P, DF, calls, how))
        code, said = go("--fetch-only")
        assert code == 0, f"a clean run exited {code}: {said[-400:]}"
        assert [c["view"] for c in calls] == list(FD.ORDER + FD.LOOKUP_ORDER) and \
            len(calls) == 11 and set(FD.ORDER) == set(DF.VIEWS) and \
            set(FD.LOOKUP_ORDER) == set(DF.LOOKUPS), [c["view"] for c in calls]
        assert sleeps == [FD.PAUSE] * 10 and FD.PAUSE >= 4, f"it paused {sleeps}"
        years = {"Docket": 2025, "Legislation": 2026, "Sponsors": 2026, "RollCallSummary": 2026,
                 "RollCallHistory": 2026}
        for c in calls:
            v = c["view"]
            cols = DF.VIEWS.get(v) or DF.LOOKUPS[v]
            where = f" WHERE [{DF.YEAR_COLUMN[v]}] >= {years[v]}" if v in years else ""
            assert c["script"] == P.PS_STREAM_COUNTED, f"{v} went through another bridge"
            assert c["count"] == f"SELECT COUNT(*) FROM [{v}]{where}", c["count"]
            assert c["sql"] == "SELECT " + ", ".join(f"[{x}]" for x in cols) + f" FROM [{v}]{where}", c["sql"]
            for sql in (c["count"], c["sql"]):
                assert re.fullmatch(r"SELECT [^;*]*|SELECT COUNT\(\*\) [^;*]*", sql) and \
                    not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|MERGE|INTO)\b|--",
                                  sql, re.I), f"not a plain SELECT: {sql[:120]}"
            assert Path(c["out"]).resolve().parent == (tmp / ".night" / "dbday").resolve(), c["out"]
        after = tree()
        new = sorted(set(after) - set(before))
        assert all(n.startswith(".night/dbday/") for n in new) and \
            all(after[k] == h for k, h in before.items()), (
                "fetch_day_db.py wrote outside .night/dbday, or changed a file that was there: "
                f"{[n for n in new if not n.startswith('.night/dbday/')][:5]}")
        assert sorted(new) == sorted([f".night/dbday/{v}.psv" for v in _dbday_call_views(calls)]
                                     + [".night/dbday/source.json"]), new
        src = json.loads(Path(".night/dbday/source.json").read_text(encoding="utf-8"))
        assert len(src["views"]) == 11 and all(
            e["rows"] == e["count"] == len(_DBDAY_VIEWS[v]) and not e.get("error")
            for v, e in src["views"].items()), src["views"]
        assert FD.OUT == DF.VIEWS_DIR == NI.DB_DAY, "the three do not name one scratch folder"

        # By hand: the comparison too, the rebuilt files to read, nothing installed.
        code, said = go()
        assert code == 0 and "every guard passed" in said and "Nothing was installed" in said, said[-400:]
        after = tree()
        assert all(after[k] == h for k, h in before.items()) and sorted(
            n for n in set(after) - set(before) if "/files/" in n) == sorted(
            f".night/dbday/files/{n}" for n in DF.DAY_FILES), "by hand it installed, or wrote elsewhere"

        # A view that arrives short ends the run: nothing more is asked.
        del calls[:]
        how["short"] = {"Docket": 1}
        code, said = go("--fetch-only")
        assert code == 1 and [c["view"] for c in calls][-1] == "Docket" and len(calls) == 5 and \
            not Path(".night/dbday/Docket.psv").exists() and \
            not list(Path(".night/dbday").glob("*.part")), (code, [c["view"] for c in calls])
        try:
            DF.rebuild(DF.VIEWS_DIR, ".")
            raise AssertionError("the day's files were rebuilt from a run that ended short")
        except DF.Problem:
            pass
        # MORE rows than the server counted a moment before is not short: the
        # count is asked first, of tables the clerks write to, and a row
        # entered while the view was read is in the view. The run goes on,
        # says so, and the day's files are rebuilt. Held to equal, one docket
        # entry made in those seconds lost the night its fallback.
        del calls[:]
        how.clear()
        how["more"] = {"Docket": 1}
        code, said = go("--fetch-only")
        got = json.loads(Path(".night/dbday/source.json").read_text(encoding="utf-8"))["views"]
        n = len(_DBDAY_VIEWS["Docket"])
        assert code == 0 and len(calls) == 11 and not got["Docket"].get("error") and \
            (got["Docket"]["count"], got["Docket"]["rows"]) == (n - 1, n), (code, got.get("Docket"))
        assert f"the server had counted {n - 1}: 1 entered while it was read" in said, said[-600:]
        assert DF.rebuild(DF.VIEWS_DIR, ".")[1]["entered"] == {"Docket": 1}
        # ... and so does a query that fails; but a lookup's is said and passed.
        del calls[:]
        how.clear()
        how["fail"] = {"Legislation"}
        code, said = go("--fetch-only")
        assert code == 1 and [c["view"] for c in calls][-1] == "Legislation" and len(calls) == 4, calls
        del calls[:]
        how["fail"] = {"Subject"}
        code, said = go("--fetch-only")
        assert code == 0 and len(calls) == 11 and "FAIL  Subject" in said, said[-300:]
        assert any(n.startswith("SubjectCodes.txt was not compared")
                   for n in DF.lookup_notes(DF.VIEWS_DIR, ".")), DF.lookup_notes(DF.VIEWS_DIR, ".")
        DF.rebuild(DF.VIEWS_DIR, ".")

        # A session that has taken no roll call yet answers with no rows, and
        # that is an answer; a roster with no rows is not.
        del calls[:]
        how.clear()
        how["empty"] = {"RollCallSummary", "RollCallHistory"}
        code, said = go("--fetch-only")
        assert code == 0 and len(calls) == 11, (code, said[-300:])
        del calls[:]
        how["empty"] = {"Legislators"}
        code, said = go("--fetch-only")
        assert code == 1 and len(calls) == 1 and "no rows" in said, (code, said[-300:])
        assert 0 < FD.TIMEOUT <= 300, "a view's query is given more than five minutes"

        # A connection that fails ends it at once; on GitHub's machine it is
        # the host's hold, and the next run asks nothing.
        del calls[:]
        how.clear()
        how["refuse"] = {"Legislators"}
        os.environ["GITHUB_ACTIONS"] = "true"
        code, said = go("--fetch-only")
        assert code == 3 and len(calls) == 1 and P.hold_standing(), (code, len(calls))
        how.clear()
        P.child = types.SimpleNamespace(popen=nothing)
        code, said = go("--fetch-only")
        assert code == P.SQL_HELD and "could not be connected to" in said, (code, said[-300:])
        P.HELD.unlink()
        os.environ.pop("GITHUB_ACTIONS")

        # Another fetch holds the lock: it does not start. Its pid is any but
        # this process's parent's, which refusal.hold takes for the lane that
        # started the fetch and lets through. It was "1", and a suite started
        # in the background from a shell that had since exited can have pid 1
        # for its parent: the fetch went on, and this failed only in such runs.
        Path("archive/.lock").write_text(str(os.getppid() + 1), encoding="utf-8")
        code, said = go("--fetch-only")
        assert code == 3 and "archive/.lock is held" in said, (code, said[-300:])
        Path("archive/.lock").unlink()

        # No installed files, nothing to take the years from: nothing asked.
        Path("Docket.txt").unlink()
        code, said = go("--fetch-only")
        assert code == 1 and said.startswith("NOT ASKED"), (code, said[:200])

        # It reaches the database through probe_db only.
        tree_ = ast.parse(_source(_paths.locate("fetch_day_db.py")))
        imported = {a.name for n in ast.walk(tree_) if isinstance(n, ast.Import) for a in n.names} \
            | {n.module for n in ast.walk(tree_) if isinstance(n, ast.ImportFrom) and n.module}
        assert imported <= {"argparse", "json", "shutil", "sys", "time", "datetime", "pathlib",
                            "_paths", "dayfiles_from_db", "probe_db", "refusal"}, \
            f"fetch_day_db.py imports {sorted(imported)}"
        bridges = {n.func.attr for n in ast.walk(tree_) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                   and n.func.value.id == "P" and n.func.attr.startswith("run")}
        assert bridges == {"run_to_file_counted"}, f"fetch_day_db.py calls probe_db.{sorted(bridges)}"
    finally:
        os.chdir(here)
        (P.run, P.child, P.HELD, FD.time, sys.argv, refusal.MARK, refusal.LOCK) = saved
        for k, val in saved_env.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("eleven connections, smallest first, a pause apart, each a COUNT and one "
                  "SELECT of named columns from the installed files' first year on; only "
                  ".night/dbday is written; a short view, a failed query or connection ends "
                  "it, a held host or a held lock stops it before it asks")


def _dbday_from_dump(DF, db, out, installed):
    """What fetch_day_db.py's statements would have left in `out`, from a dump
    already on disk: each view's rows from the installed files' first year on
    (the roster and the lookups whole), and a source.json. No network."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sc = DF.scope(DF.installed_files(installed))
    src = {"asked": "the dump in db/, filtered as fetch_day_db.py asks", "views": {}}
    for view, cols in list(DF.VIEWS.items()) + list(DF.LOOKUPS.items()):
        col = DF.YEAR_COLUMN.get(view)
        i = cols.index(col) if col else None
        first = int(sc["ask"][view]) if col else None
        n = 0
        with open(Path(db) / f"{view}.psv", encoding="utf-8", errors="replace", newline="") as fh, \
                open(out / f"{view}.psv", "w", encoding="utf-8", newline="") as to:
            for line in fh:
                if i is not None:
                    y = line.split("|")[i].strip()
                    if not y.isdigit() or int(y) < first:
                        continue
                to.write(line)
                n += 1
        src["views"][view] = {"count": n, "rows": n, "seconds": 0}
    (out / DF.SOURCE).write_text(json.dumps(src), encoding="utf-8")
    return src


@check("data", "the day files rebuilt from the dump of 8 September are the export of the 6th, "
       "as measured, and the year-filtered queries would bring the same", needs=("dayfiles_from_db",))
def _dayfiles_pair(DF):
    """The one pair on this disk where both sources show one state: db/*.psv,
    the views as dumped on 8 September 2026, and nh-archive's export of the
    6th, which for these files was still the copy in force. Rebuilt from the
    one and compared with the other, the seven files come out as the design
    measured on 1 October, and dayfiles_from_db.PAIR_MEASURED holds the
    numbers: RollCallSummary.txt, RollCallHistory.txt, LsrSponsors.txt and
    legislators.txt byte-identical; the docket's 25,279 rows identical in the
    six columns the view carries; 1,387 bill records byte-identical with the
    export's own Senate status code kept on the 29 where the view has another;
    LsrsOnly.txt short of 13 rows the Legislation view does not carry. Every
    guard passes, and no lookup differs.

    And what fetch_day_db.py asks for is enough: the same views cut down to
    the rows its statements select -- about 168,000 of the dump's 2.6 million
    -- make the same seven files, byte for byte.

    It is a quiet week's pair, out of session. This holds the mapping to what
    was measured; it does not show what a session day does.
    """
    why = DF.pair_here()
    if why:
        return "skip", why
    got, result, facts = DF.check_pair()
    wrong = {n: g for n, g in got.items()
             if any(g.get(k) != v for k, v in DF.PAIR_MEASURED[n].items())}
    assert not wrong, ("rebuilt from the dump, these are not what was measured on 1 October "
                       f"2026: {wrong}; measured: { {n: DF.PAIR_MEASURED[n] for n in wrong} }")
    assert not result["stops"] and not result["warnings"], result
    tmp = Path(tempfile.mkdtemp(prefix="gr-pair-"))
    try:
        for name, data in DF.export_of("nh-archive", DF.PAIR_EXPORT,
                                       list(DF.DAY_FILES) + list(DF.LOOKUP_FILE.values())).items():
            (tmp / name).write_bytes(data)
        whole, _ = DF.rebuild("db", tmp, need_source=False)
        lookups = all((Path("db") / f"{v}.psv").is_file() for v in DF.LOOKUPS)
        if lookups:
            src = _dbday_from_dump(DF, "db", tmp / "dbday", tmp)
            asked, _ = DF.rebuild(tmp / "dbday", tmp)
            assert all(asked[n] == whole[n] for n in DF.DAY_FILES), (
                "the rows fetch_day_db.py asks for do not make the files the whole dump makes: "
                f"{[n for n in DF.DAY_FILES if asked[n] != whole[n]]}")
            notes = DF.lookup_notes(tmp / "dbday", tmp)
            assert not notes, f"a lookup differs from the database on the pair: {notes}"
            rows = sum(e["rows"] for e in src["views"].values())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("5 of the 7 byte-identical, the 1,387 bill records with the export's Senate "
                  "status code kept on the 29 where the view has another; the docket's 25,279 "
                  "rows in six columns, LsrsOnly 6,950 of 6,963; every guard passes"
                  + (f"; the {rows:,} rows fetch_day_db.py would ask for make the same files, "
                     "and no lookup differs" if lookups else
                     "; the lookup views are not in db/ here, so they were not compared"))


@check("data", "the checkers' and the reviewers' doctored files, made again from the real pair, "
       "each stop a database night at the real ceilings", needs=("dayfiles_from_db",))
def _dayfiles_pair_doctored(DF):
    """On 2 October 2026 two checkers doctored copies of the files the one
    supervised test had rebuilt, and seven of the ten ways passed every
    guard: a wrong House committee and title on a third of the bills, 250
    docket rows reworded to a false outcome, 5,000 invented docket rows, a
    docket row dated back, every member's party swapped, every Yea and Nay
    swapped, every roll call filed under HB 1. The guards were made to hold
    what the files say; and two reviewers then doctored the views 130 ways,
    and what still installed was whatever was ADDED, or twice, or under a
    ceiling that was a guess: every ballot twice, a wrong roll call filed in
    front of the right one, ballots added to a roll call, an invented roll
    call, 500 sponsors nobody signed, 20,000 docket rows spread over three
    weeks, a row stamped a year ahead, the last 25 signings gone, 100
    outcomes turned round, 100 subject codes, two bills' numbers exchanged,
    eight members' parties, one Yea made a Nay on ten roll calls.

    All of them are made here from the pair that stays on this disk -- the
    seven files rebuilt from the dump of 8 September, against the export of
    the 6th -- with no ceiling lowered. Each stops the night, and names the
    file. The files as rebuilt stop nothing and name nothing; and a Senate
    row with an old entry time, which is what the Senate's own late entries
    are, passes and is named.

    _dayfiles_content tries each guard at its edge on a few real rows; this
    holds the ceilings as they stand to the whole of the real files.
    """
    import collections
    import random
    why = DF.pair_here()
    if why:
        return "skip", why
    was = DF.export_of("nh-archive", DF.PAIR_EXPORT)
    tmp = Path(tempfile.mkdtemp(prefix="gr-doctored-"))
    try:
        for name, data in was.items():
            (tmp / name).write_bytes(data)
        files, facts = DF.rebuild("db", tmp, need_source=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    facts = dict(facts, asked="2026-09-08T20:55:00")        # when the dump was taken
    whole = DF.judge(files, was, facts)
    assert not whole["stops"] and not whole["told"], (
        f"the pair as rebuilt was stopped, or named a row: {whole['stops']} {whole['told']}")
    # Each file as its rows, split once: 25 nights are judged below.
    files = {n: DF.export_lines(files[n], DF.WIDTH[n]) for n in DF.DAY_FILES}
    was = {n: DF.export_lines(was[n], DF.WIDTH[n]) for n in DF.DAY_FILES}

    def put(ln, **cols):
        f = ln.split("|")
        for at, value in cols.items():
            f[int(at[1:])] = value
        return "|".join(f)

    def third(ls):
        return [put(ln, c13="H99", c2="WRONG TITLE") if i % 3 == 0 else ln for i, ln in enumerate(ls)]

    def some(n, **cols):
        """`cols` put on `n` rows, picked the same way every time."""
        def go(ls):
            out = list(ls)
            for i in random.Random(7).sample(range(len(out)), n):
                out[i] = put(out[i], **cols)
            return out
        return go

    def flood(ls):
        return ls + [put(ln, c5="Ought to Pass: MA VV 09/08/2026", c2="9/8/2026 9:00:00 AM",
                         c6="9/8/2026 9:00:00 AM") for ln in ls[:5000]]

    def spread(ls):
        """20,000 rows on real bills, 953 to a day, from the day after the
        installed file's newest entry on."""
        out = list(ls)
        for i, ln in enumerate(ls[:20000]):
            day = 5 + i // 953
            out.append(put(ln, c5="Signed by Governor Ayotte; Chapter 999", c6="",
                           c2=f"9/{day}/2026 {1 + i % 11}:{i % 60:02d}:{i // 60 % 60:02d} PM"))
        return out

    def dated(chamber, when):
        def go(ls):
            return ls + [put(next(ln for ln in ls[100:] if ln.split("|")[4] == chamber),
                             c5="Signed by Governor 01/02/2025", **({"c2": when} if when else {}))]
        return go

    def short(ls):
        """One row gone of each of 200 bills that hold ten or more."""
        rows_of = collections.Counter(ln.split("|")[3] for ln in ls)
        seen, out = set(), []
        for ln in ls[:-1]:
            b = ln.split("|")[3]
            if rows_of[b] >= 10 and b not in seen and len(seen) < 200:
                seen.add(b)
                continue
            out.append(ln)
        assert len(seen) == 200
        return out + ls[-1:]

    def unsigned(ls):
        """The last 25 signings gone."""
        gone = [i for i, ln in enumerate(ls) if "Signed by Governor" in ln.split("|")[5]][-25:]
        assert len(gone) == 25
        return [ln for i, ln in enumerate(ls) if i not in set(gone)]

    def turned(ls):
        """100 outcomes turned round."""
        at = [i for i, ln in enumerate(ls) if ln.split("|")[5].startswith("Ought to Pass:")][:100]
        assert len(at) == 100
        return [put(ln, c5=ln.split("|")[5].replace("Ought to Pass:", "Inexpedient to Legislate:"))
                if i in set(at) else ln for i, ln in enumerate(ls)]

    def twenty_bills(ls):
        seen = []
        for ln in ls:
            b = ln.split("|")[5]
            if b and b not in seen and len(seen) < 20:
                seen.append(b)
        return [ln for ln in ls if ln.split("|")[5] not in seen]

    def swap(at, a, b, most=None):
        def go(ls):
            out, n = [], 0
            for ln in ls:
                x = ln.split("|")[at]
                if x in (a, b) and (most is None or n < most):
                    ln = put(ln, **{f"c{at}": {a: b, b: a}[x]})
                    n += 1
                out.append(ln)
            return out
        return go

    def exchanged(ls):
        a, b = ls[0].split("|"), ls[1].split("|")
        return [put(ls[0], c10=b[10], c9=b[9]), put(ls[1], c10=a[10], c9=a[9])] + ls[2:]

    def one_each(ls):
        """One Yea made a Nay on each of ten roll calls."""
        out, seen = [], set()
        for ln in ls:
            f = ln.split("|")
            if f[6] == "Yea" and tuple(f[:3]) not in seen and len(seen) < 10:
                seen.add(tuple(f[:3]))
                ln = put(ln, c6="Nay")
            out.append(ln)
        return out

    def more_ballots(ls):
        return ls + [put(ls[0], c3=str(990000 + i), c4=str(990000 + i)) for i in range(30)]

    def invented(ls):
        top = max(int(ln.split("|")[2]) for ln in ls if ln.split("|")[1] == "H")
        return ls + [put(ls[0], c2=str(top + 1), c5="300", c6="19")]

    def signed_by_nobody(ls):
        """500 sponsors: each of the first 25 members, on 20 requests they
        did not sponsor."""
        have = {(f[1], f[3]) for f in (ln.split("|") for ln in ls)}
        members = list(dict.fromkeys(ln.split("|")[3] for ln in ls))[:25]
        requests = list(dict.fromkeys(ln.split("|")[1] for ln in ls))
        out = []
        for m in members:
            mine = [r for r in requests if (r, m) not in have][:20]
            out += [f"2026|{r}|{90 + j % 9}|{m}|0" for j, r in enumerate(mine)]
        assert len(out) == 500
        return ls + out
    doctored = [
        ("a wrong House committee and title on a third of the bills", "LSRs.txt", third,
         "LSRs.txt: 463 installed bill records have another title, more than 40"),
        ("250 docket rows reworded to a false outcome", "Docket.txt",
         some(250, c5="Inexpedient to Legislate: MA VV 01/01/2026"),
         "Docket.txt: 250 installed rows are reworded in the database's, more than 40"),
        ("5,000 invented docket rows", "Docket.txt", flood,
         "Docket.txt: 5,000 new rows entered on 2026-09-08, more than the 1,000 a day brings"),
        ("20,000 invented docket rows, 953 to a day", "Docket.txt", spread,
         "Docket.txt: 20,000 new rows, more than the 1,000 that 1 night brings"),
        ("a House docket row dated back", "Docket.txt", dated("H", None),
         "Docket.txt: 1 new rows were entered more than 14 days before the installed file's "
         "newest (2026-09-04"),
        ("a docket row stamped a year ahead", "Docket.txt", dated("H", "9/8/2027 9:00:00 AM"),
         "Docket.txt: 1 new rows are entered more than 14 days after the views were asked"),
        ("the docket 200 rows short, its newest still there", "Docket.txt", short,
         "Docket.txt: 200 installed rows are not in the database's, more than 5"),
        ("the last 25 signings gone from the docket", "Docket.txt", unsigned,
         "Docket.txt: 25 installed rows are not in the database's, more than 5"),
        ("100 docket outcomes turned round", "Docket.txt", turned,
         "Docket.txt: 100 installed rows are reworded in the database's, more than 40"),
        ("100 subject codes changed", "LSRs.txt", some(100, c12="ZZZ"),
         "installed bill records changed where the build reads them with nothing in the docket"),
        ("two bills' numbers exchanged", "LSRs.txt", exchanged,
         "LSRs.txt: 2 installed bill records have another chamber or bill number"),
        ("every sponsor of 20 bills gone", "LsrsOnly.txt", twenty_bills,
         "installed rows of members still sitting, each on a numbered bill"),
        ("no sponsor marked Prime", "LsrsOnly.txt",
         lambda ls: [put(ln, c4="Sponsor") for ln in ls],
         "installed rows of members still sitting, each on a numbered bill"),
        ("the prime flag cleared on every sponsor", "LsrSponsors.txt",
         lambda ls: [put(ln, c4="0") for ln in ls],
         "LsrSponsors.txt: 1,399 installed rows are not in the database's, more than 5"),
        ("500 sponsors nobody signed", "LsrSponsors.txt", signed_by_nobody,
         "new rows are on a bill whose docket began more than 30 days before, more than 5"),
        ("170 sponsors' rows gone", "LsrSponsors.txt", lambda ls: ls[170:],
         "LsrSponsors.txt: 170 installed rows are not in the database's, more than 5"),
        ("every member's party swapped", "legislators.txt", swap(8, "R", "D"),
         "installed members have another name, chamber, county, district or party"),
        ("eight members' parties swapped", "legislators.txt", swap(8, "R", "D", 8),
         "legislators.txt: 8 installed members have another name, chamber, county, district or "
         "party in the database's, more than 2"),
        ("every Yea and Nay swapped", "RollCallHistory.txt", swap(6, "Yea", "Nay"),
         "RollCallHistory.txt: 113,119 installed ballots are cast otherwise"),
        ("one Yea made a Nay on each of ten roll calls", "RollCallHistory.txt", one_each,
         "10 roll calls' Yea and Nay ballots are not their counts"),
        ("every ballot twice", "RollCallHistory.txt", lambda ls: ls + ls,
         "RollCallHistory.txt: 131,199 ballots are there more than once"),
        ("30 ballots added to a roll call", "RollCallHistory.txt", more_ballots,
         "RollCallHistory.txt: 30 ballots are on installed roll calls that did not have them"),
        ("every roll call filed under HB 1", "RollCallSummary.txt",
         lambda ls: [put(ln, c4="HB1", c11="Ought to Pass") for ln in ls],
         "RollCallSummary.txt: 419 installed roll calls read otherwise"),
        ("every roll call twice, the first copy under HB 1442", "RollCallSummary.txt",
         lambda ls: [put(ln, c4="HB1442") for ln in ls] + ls,
         "RollCallSummary.txt: 419 roll calls are there more than once"),
        ("an invented roll call, 300 to 19, with no ballots", "RollCallSummary.txt", invented,
         "says 300-19 and has 0 Yea and 0 Nay ballots, a new roll call"),
    ]
    passed = []
    for what, name, how, words in doctored:
        got = DF.judge(dict(files, **{name: how(files[name])}), was, facts)["stops"]
        if not any(words in s for s in got):
            passed.append(f"{what} ({name}): the guards said {got or 'nothing'}")
    assert not passed, ("doctored files that were not stopped, or not for what was done to them:\n"
                        + "\n".join(passed))
    # THE SENATE'S OWN LATE ENTRIES look like the row dated back, and are
    # real: one passes, counted and named, where a House row stops.
    got = DF.judge(dict(files, **{"Docket.txt": dated("S", None)(files["Docket.txt"])}), was, facts)
    assert not got["stops"] and got["held"]["Docket.txt"]["late"] == 1 and len(got["told"]) == 1 \
        and len(got["warnings"]) == 1 and "new Senate rows entered more than 14 days before" in \
        got["warnings"][0], (got["stops"], got["held"]["Docket.txt"], got["warnings"])
    return "ok", (f"{len(doctored)} doctored copies of the real pair's files each stop the night; "
                  "the pair as rebuilt does not, and names nothing; a Senate row entered late "
                  "passes and is named")


# ---- fetch_past_db: the six Past* views ----------------------------------------

PAST_TEXT = "a|b\r\nc\t\"quoted\" café — line sep\x85end"


def _past_catalogue():
    """The six views' columns as INFORMATION_SCHEMA gave them on 26 September.

    The NAMES are the real ones; PastLegislation's middle 43 and every TYPE
    the task did not state are the fixture's own, not a claim about the view.
    """
    leg = ([("SessionYear", "smallint")] + [(f"c{i}", "varchar") for i in range(2, 45)]
           + [("Retained", "bit"), ("legislationID", "int"), ("id", "int")])
    return {
        "PastSponsors": [("SessionYear", "smallint"), ("lsr", "int"),
                         ("LSRSequenceNo", "smallint"), ("employeeNo", "varchar"),
                         ("PrimeSponsor", "int"), ("SignedOff", "bit"),
                         ("DateSignedOff", "smalldatetime"), ("SponsorWithdrawn", "bit")],
        "PastLegislation": leg,
        "PastDocket": [("SessionYear", "smallint"), ("LSR", "int"), ("ExpandedBillNo", "varchar"),
                       ("StatusDate", "datetime"), ("CondensedBillNo", "varchar"),
                       ("LegislativeBody", "varchar"), ("Description", "varchar"),
                       ("legislationid", "int"), ("OrderDate", "datetime"),
                       ("statusorder", "int"), ("id", "int")],
        "PastLegislationText": [("id", "int"), ("BillNbr", "varchar"), ("html", "text"),
                                ("sessionyear", "smallint"), ("VersionID", "int"),
                                ("text", "text"), ("legislationID", "int"), ("lsr", "int"),
                                ("FullDescription", "varchar")],
        "PastAmendments": [("id", "int"), ("LegislationTextID", "int"),
                           ("LegislationText", "varchar"), ("sessionyear", "smallint"),
                           ("legislationID", "int"), ("AmendmentNo", "varchar")],
        "PastCommitteeReports": [("id", "int"), ("committeeSupportID", "int"),
                                 ("chamberCode", "varchar"), ("legislationid", "int"),
                                 ("committeeType", "varchar"), ("releaseDAte", "datetime"),
                                 ("htmlText", "varchar")],
    }


def _past_cell(ty, i):
    """Row i's value for a column of SQL type ty: (what the bridge sends, what JSON holds)."""
    import base64
    b64 = lambda s: base64.b64encode(s.encode("utf-8")).decode("ascii")
    if ty in ("int", "smallint"):
        return b64(str(1000 + i)), 1000 + i
    if ty == "bit":
        return b64("1" if i % 2 == 0 else "0"), i % 2 == 0
    if ty in ("datetime", "smalldatetime"):
        return b64("2016-03-10T14:05:00.1230000" if i == 1 else "2016-03-10T14:05:00.0000000"), \
            ("2016-03-10T14:05:00.123" if i == 1 else "2016-03-10T14:05:00")
    s = [PAST_TEXT, None, ""][i % 3]
    return ("-" if s is None else b64(s)), s


def _past_fake_bridge(P, calls, how):
    """child.popen for probe_db, answering as PS_STREAM and PS_JSONL would.

    how["rows"][view] is the count the server gives (3 unless said); how["short"]
    [view] rows fewer arrive than it counted; a view in how["refuse"] cannot
    connect. Nothing is started and nothing leaves this process.
    """
    import base64
    cat = _past_catalogue()

    class Proc:
        def __init__(self, lines, rc):
            self.stdout, self.stderr = iter([x + "\r\n" for x in lines]), iter([])
            self.returncode, self._rc = None, rc

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = self._rc if self.returncode is None else self.returncode
            return self.returncode

        def kill(self):
            self.returncode = -9

    def popen(cmd, **kw):
        script, env = cmd[-1], dict(kw.get("env") or {})
        view = re.search(r"FROM (\w+)", env.get("GR_COUNT") or "").group(1)
        calls.append({"view": view, "script": script, "count": env.get("GR_COUNT"),
                      "sql": env.get("GR_SQL")})
        if view in how.get("refuse", ()):
            return Proc(["CONNECT_FAIL A network-related error occurred (fixture)"], 3)
        n = how.get("rows", {}).get(view, 3)
        sent = max(0, n - how.get("short", {}).get(view, 0))
        cols = cat[view]
        if script == P.PS_STREAM_COUNTED:
            with open(env["GR_OUT"], "w", encoding="utf-8", newline="") as fh:
                for i in range(sent):
                    fh.write("|".join([f"{view}-{i}"] + ["x"] * (len(cols) - 1)) + "\r\n")
            return Proc([f"COUNT {n}", f"DONE {sent}"], 0)
        assert script == P.PS_JSONL, "a bridge script this fixture does not know"
        names = ",".join(base64.b64encode(c.encode("utf-8")).decode("ascii") for c, _ in cols)
        rows = ["R " + ",".join(_past_cell(t, i)[0] for _, t in cols) for i in range(sent)]
        return Proc([f"COUNT {n}", "COLUMNS " + names] + rows + [f"DONE {sent}"], 0)

    return popen


@check("build", "fetch_past_db asks for nothing but SELECT, and only of its six views",
       needs=("fetch_past_db",))
def _past_select_only(FP):
    """The Past* views are somebody else's database, read on a public account.

    Every statement fetch_past_db.py sends is built from the six names in
    VIEWS and passes select_only() on the way out. This holds the guard to
    what it must refuse -- a write, a second statement, a comment, a view off
    the list, a star, a join -- and proves a column name the catalogue hands
    back cannot become SQL, however it is spelled. It also reads the script:
    it reaches the database only through probe_db's three bridges, imports
    nothing that could open a connection of its own, and holds no statement
    that begins with anything but SELECT.
    """
    import ast
    six = ("PastSponsors", "PastLegislation", "PastAmendments", "PastDocket",
           "PastCommitteeReports", "PastLegislationText")
    assert set(FP.NAMES) == set(six) and len(FP.NAMES) == 6, f"the allow-list is {FP.NAMES}"
    # Every statement built for every view passes, and names only its view.
    cat = _past_catalogue()
    cat["PastSponsors"] = cat["PastSponsors"] + [
        ("x] FROM PastSponsors; DROP TABLE PastSponsors --", "varchar"),
        ("o'brien", "int"), ("scan", "image"), ("memo", "ntext")]
    built = [FP.catalogue_sql(FP.NAMES)]
    for v in FP.NAMES:
        c, s, names, tys = FP.statements(v, cat[v])
        assert c == f"SELECT COUNT(*) AS n FROM {v}", c
        assert s.startswith("SELECT ") and s.endswith(f" FROM {v}"), s[-80:]
        assert len(names) == len(cat[v]) == len(tys), v
        built += [c, s]
    c, s, names, tys = FP.statements("PastSponsors", cat["PastSponsors"])
    assert "[x]] FROM PastSponsors; DROP TABLE PastSponsors --]" in s, \
        "a column name with a ] in it was not escaped: " + s[-160:]
    assert "DATALENGTH([scan]) AS [scan_bytes]" in s and "scan_bytes" in names, \
        "a blob column was asked for as its bytes"
    assert "CAST([memo] AS nvarchar(max))" in s, "ntext is not kept wide"
    assert "CAST([html] AS varchar(max))" in FP.statements(
        "PastLegislationText", cat["PastLegislationText"])[1], "text is not cast"
    for sql in built:
        FP.select_only(sql)
    refused = [
        "DELETE FROM PastSponsors",
        "SELECT [a] FROM PastSponsors; DROP TABLE PastSponsors",
        "SELECT [a] FROM Legislators",
        "SELECT [a] FROM dbo.Legislators",
        "SELECT [a] INTO x FROM PastSponsors",
        "SELECT [a] FROM PastSponsors -- note",
        "SELECT [a] FROM PastSponsors /* note */",
        "SELECT [a] FROM PastSponsors UNION SELECT [a] FROM PastDocket",
        "SELECT [a] FROM PastSponsors JOIN PastDocket ON 1 = 1",
        "SELECT [a] FROM (SELECT [a] FROM PastDocket) q",
        "EXEC sp_who",
        "SELECT * FROM PastSponsors",
        "SELECT @@VERSION",
        "SELECT [a] FROM #t",
        "SELECT CHAR(65) FROM PastSponsors",
        "SELECT OPENROWSET([a]) FROM PastSponsors",
        "SELECT [a FROM PastSponsors",
        "SELECT [a] FROM PastSponsors WHERE [a] = 'x",
        "SELECT [a] FROM PastSponsors WHERE [a] = 'PastDocket'",
        "SELECT TABLE_NAME AS v FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Legislators'",
        "SELECT name FROM sys.databases",
    ]
    let_through = []
    for sql in refused:
        try:
            FP.select_only(sql)
            let_through.append(sql)
        except ValueError:
            pass
    assert not let_through, "select_only let these through: " + " | ".join(let_through)
    for bad in ("Legislators", "PastSponsors; DROP TABLE x"):
        try:
            FP.statements(bad, [("a", "int")])
            raise AssertionError(f"statements() built SQL for {bad!r}")
        except ValueError:
            pass

    # The script itself: nothing reaches the database but through probe_db.
    src = _source(_paths.locate("fetch_past_db.py"))
    tree = ast.parse(src)
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree)
                                     if isinstance(n, ast.ImportFrom) and n.module}
    own = imported & {"subprocess", "child", "socket", "urllib", "http", "requests",
                      "pyodbc", "pymssql", "sqlite3", "ctypes"}
    assert not own, f"fetch_past_db.py imports {sorted(own)}; it reaches the database through probe_db only"
    bridges = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
               and n.func.value.id == "P"}
    assert bridges <= {"run", "run_to_file_counted", "run_to_jsonl"}, \
        f"fetch_past_db.py calls probe_db.{sorted(bridges)}"
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    verb = re.compile(r"^\s*(?:INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|MERGE|"
                      r"TRUNCATE|GRANT|DECLARE|USE|WITH)\b")
    writes = [n.value[:50] for n in ast.walk(tree) if isinstance(n, ast.Constant)
              and isinstance(n.value, str) and id(n) not in docs and verb.search(n.value)]
    assert not writes, f"fetch_past_db.py holds statements that are not SELECTs: {writes}"
    return "ok", (f"{len(built)} statements built for the six views all pass; "
                  f"{len(refused)} that must not, do not; a ] in a column name is escaped; "
                  "the script reaches the database through probe_db's bridges only")


@check("build", "fetch_past_db takes each view whole or not at all, counted, into its own "
       "folder and manifest", needs=("fetch_past_db", "probe_db", "refusal"))
def _past_whole_or_nothing(FP, P, R):
    """A dump of six views, one of them 905 MB, from a machine that is not ours.

    Run end to end against a stand-in for PowerShell that answers the way
    PS_STREAM and PS_JSONL do, with rows holding a pipe, a line break, a tab,
    quotes, characters outside ASCII, U+2028, U+0085, an empty string and a
    NULL. Nothing is started and nothing leaves this process.

    What it holds the script to: --list asks nothing and writes nothing; one
    catalogue question and then one connection per view, COUNT(*) on it
    before the rows; five seconds between views; the text views decode to
    exactly what was sent; the .psv files carry no header; everything lands
    in db/past/ and its own manifest, never db/_manifest.json, which is
    GitHub's nightly's; a complete file is not asked for twice; a short stream
    or an empty view is a non-zero exit that leaves the .part, named, keeps
    the complete file it would have replaced, and stops the run; a refused
    connection leaves nothing behind; and GitHub's machine refuses it outright.
    probe_db.run_to_file is left exactly as its older callers use it.
    """
    import contextlib
    import hashlib
    import io
    import types
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-past-"))
    saved = (P.run, P.child, FP.time, sys.argv)
    saved_env = os.environ.get("GITHUB_ACTIONS")
    calls, asked, sleeps, how = [], [], [], {}
    cat = _past_catalogue()

    def catalogue(conn, queries):
        asked.append(queries)
        rows = [{"s": "dbo", "v": v, "c": c, "ty": t, "n": str(i + 1)}
                for v in reversed(FP.NAMES) for i, (c, t) in reversed(list(enumerate(cat[v])))]
        return [{"name": queries[0][0], "rows": rows}], None

    def nothing(*_a, **_k):
        raise AssertionError("something was asked for that should not have been")

    def go(*argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = FP.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def entry(v):
        return json.loads(Path("db/past/_manifest.json").read_text(encoding="utf-8"))[v]

    try:
        os.chdir(tmp)
        os.environ.pop("GITHUB_ACTIONS", None)
        FP.time = types.SimpleNamespace(sleep=sleeps.append, time=__import__("time").time,
                                        strftime=__import__("time").strftime)

        # --list: the plan, and nothing asked or written.
        P.run, P.child = nothing, types.SimpleNamespace(popen=nothing)
        code, said = go("--list")
        assert code == 0 and "Nothing was asked for" in said, said[-300:]
        assert not Path("db").exists(), "--list wrote something"
        assert said.rstrip().splitlines()[-1].strip().startswith("6 views"), said[-200:]

        # The whole run.
        Path("db").mkdir()
        Path("db/_manifest.json").write_text('{"Docket": {"rows": 1}}', encoding="utf-8")
        P.run, P.child = catalogue, types.SimpleNamespace(popen=_past_fake_bridge(P, calls, how))
        code, said = go()
        assert code == 0, f"a clean run exited {code}: {said[-400:]}"
        last = [x for x in said.splitlines() if "fetched," in x]
        assert last and "6 fetched, 0 already here, 0 failed, 0 not reached" in last[-1], said[-300:]
        assert len(asked) == 1, f"the catalogue was asked {len(asked)} times"
        assert [c["view"] for c in calls] == list(FP.NAMES), \
            f"not one connection per view, smallest first: {[c['view'] for c in calls]}"
        for c in calls:
            assert c["count"] == f"SELECT COUNT(*) AS n FROM {c['view']}", c["count"]
            FP.select_only(c["sql"])
            assert c["sql"].endswith(f" FROM {c['view']}") and "*" not in c["sql"], c["sql"][-80:]
            want = P.PS_STREAM_COUNTED if FP.SPEC[c["view"]][1] == "psv" else P.PS_JSONL
            assert c["script"] == want, f"{c['view']} went through the wrong bridge"
        assert sleeps == [FP.PAUSE] * 5 and FP.PAUSE == 5, f"the pauses were {sleeps}"
        assert Path("db/_manifest.json").read_text(encoding="utf-8") == '{"Docket": {"rows": 1}}', \
            "db/_manifest.json, the nightly's, was written"
        past = sorted(p.name for p in Path("db/past").iterdir())
        assert past == sorted([FP.path_for(v).name for v in FP.NAMES] + ["_manifest.json"]), past
        for v in FP.NAMES:
            p, e = FP.path_for(v), entry(v)
            body = p.read_bytes()
            assert e["rows"] == e["count"] == 3 and e["bytes"] == len(body), (v, e)
            assert e["sha256"] == hashlib.sha256(body).hexdigest(), f"{v}: the sha256 is not the file's"
            assert e["columns"] == [c for c, _ in cat[v]], f"{v}: the column order is not the view's"
            assert len(e["types"]) == len(e["columns"]) and e["fetched"] and e["seconds"] >= 0, v
            if e["format"] == "psv":
                lines = body.decode("utf-8").split("\r\n")
                assert lines[-1] == "" and len(lines) == 4 and e["header"] is False, v
                assert lines[0].startswith(f"{v}-0|") and lines[0].count("|") == len(cat[v]) - 1, \
                    f"{v}.psv has a header or the wrong fields: {lines[0][:60]}"
                continue
            got = [json.loads(x) for x in body.decode("utf-8").split("\n") if x]
            assert body.count(b"\n") == 3 and len(body.decode("utf-8").splitlines()) == 3, \
                f"{v}.jsonl does not hold one row per line, whatever splits it"
            for i, row in enumerate(got):
                assert list(row) == [c for c, _ in cat[v]], f"{v}: keys out of order"
                for c, t in cat[v]:
                    assert row[c] == _past_cell(t, i)[1] and \
                        type(row[c]) is type(_past_cell(t, i)[1]), \
                        f"{v} row {i} {c}: {row[c]!r}, not {_past_cell(t, i)[1]!r}"
        assert entry("PastLegislation")["columns"][-1] == "id" and \
            len(entry("PastLegislation")["columns"]) == 47

        # Again: everything is complete, so nothing is asked.
        n = len(calls)
        code, said = go()
        assert code == 0 and len(calls) == n and len(asked) == 1, "a complete file was asked for again"
        assert "0 fetched, 6 already here" in said, said[-200:]

        # A short stream: non-zero, the .part left and named, the complete file kept.
        before = FP.path_for("PastAmendments").read_bytes()
        how["short"] = {"PastAmendments": 1}
        code, said = go("--only", "PastAmendments", "--refetch")
        part = FP.part_for("PastAmendments")
        assert code == 1 and part.exists() and part.as_posix() in said, f"{code} {said[-300:]}"
        assert "came up short" in said and "1 failed" in said, said[-300:]
        assert FP.path_for("PastAmendments").read_bytes() == before, "a short stream replaced a whole file"
        e = entry("PastAmendments")
        assert e["rows"] == 3 and e["last_error"]["part"] == part.as_posix(), e
        assert FP.complete("PastAmendments", json.loads(
            Path("db/past/_manifest.json").read_text(encoding="utf-8"))), \
            "a failed refetch made the complete file look incomplete"

        # The same for a .psv, named in any case; and an empty view.
        how["short"] = {"PastDocket": 2}
        code, said = go("--only", "pastdocket", "--refetch")
        assert code == 1 and FP.part_for("PastDocket").exists(), said[-300:]
        how["short"], how["rows"] = {}, {"PastSponsors": 0}
        code, said = go("--only", "PastSponsors", "--refetch")
        assert code == 1 and "no rows" in said and entry("PastSponsors")["rows"] == 3, said[-300:]
        how["rows"] = {}

        # A failure stops the run: the view after it is not asked for.
        for v in ("PastAmendments", "PastDocket"):
            FP.path_for(v).unlink()
        how["short"] = {"PastAmendments": 1}
        n, sleeps[:] = len(calls), []
        code, said = go()
        assert code == 1 and [c["view"] for c in calls[n:]] == ["PastAmendments"], \
            f"the run went on past a failure: {[c['view'] for c in calls[n:]]}"
        assert "1 not reached" in said and not sleeps, said[-300:]

        # A refused connection leaves no empty .part behind.
        how["short"], how["refuse"] = {}, {"PastAmendments"}
        code, said = go("--only", "PastAmendments")
        assert code == 1 and not FP.part_for("PastAmendments").exists() and \
            "Nothing of this view was written" in said, said[-300:]
        how["refuse"] = set()
        code, said = go()
        assert code == 0 and "2 fetched, 4 already here" in said, said[-300:]
        assert not list(Path("db/past").glob("*.part")), "a .part outlived the run that finished it"

        # The catalogue unanswered: no view is asked for, and it says so.
        n = len(calls)
        P.run = lambda conn, queries: (None, "A network-related error occurred (fixture)")
        code, said = go("--refetch")
        assert code == 1 and len(calls) == n and "Stopped before the first view" in said \
            and "6 not reached" in said, said[-300:]
        P.run = catalogue

        # Not a name on the list; and not on GitHub.
        code, said = go("--only", "Legislators")
        assert code == 2 and "not one of the six views" in said, said
        n = len(calls)
        os.environ["GITHUB_ACTIONS"] = "true"
        code, said = go("--refetch")
        assert code == 3 and len(calls) == n and "does not run on GitHub" in said, said
        os.environ.pop("GITHUB_ACTIONS", None)

        # run_to_file, which GitHub's nightly calls, runs what it always ran.
        seen = {}

        def older(cmd, **kw):
            seen.update(kw.get("env") or {})
            return types.SimpleNamespace(stdout=iter(["PROGRESS 2\r\n", "DONE 4\r\n"]),
                                         stderr=io.StringIO(""), wait=lambda timeout=None: 0)
        P.child = types.SimpleNamespace(popen=older)
        with contextlib.redirect_stdout(io.StringIO()):
            got = P.run_to_file("conn", "SELECT 1", tmp / "x.psv")
        assert got == (4, None) and "GR_COUNT" not in seen, (got, sorted(seen))
        # PS_STREAM is the nightly's and fetch_archive_db's, and stays what it was:
        # the count question lives only in PS_STREAM_COUNTED.
        assert "GR_COUNT" not in P.PS_STREAM and "GR_COUNT" in P.PS_STREAM_COUNTED, \
            "PS_STREAM carries the count block; it belongs in PS_STREAM_COUNTED only"
    finally:
        os.chdir(here)
        P.run, P.child, FP.time, sys.argv = saved
        if saved_env is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = saved_env
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("six views into db/past/ with their own manifest, one connection each, "
                  "counted first, 5s apart; text exact through JSON Lines; a short or empty "
                  "view stops the run and keeps its .part; never on GitHub")


@check("build", "the JSON Lines bridge keeps text exact through real PowerShell, and every "
       "bridge script parses", needs=("probe_db",))
def _past_bridge_in_powershell(P):
    """The half of run_to_jsonl that runs in PowerShell, run in PowerShell.

    _past_whole_or_nothing stands in for PowerShell; this does not. PS_JSONL's
    row-reading half is handed an in-memory table instead of a connection --
    a SqlConnection is created and never opened -- so the code that turns a
    value into what crosses the pipe is the code that will run against the
    General Court's server, and nothing is asked of anybody. Then PowerShell's
    own parser reads all three bridge scripts, PS_STREAM among them, which
    GitHub's nightly runs every night.
    """
    import base64
    if not shutil.which("powershell"):
        return "skip", "no Windows PowerShell here"
    parse = r"""
$bad = @()
foreach ($k in 'GR_PS_RUN','GR_PS_STREAM','GR_PS_COUNTED','GR_PS_JSONL') {
  $t = $null; $e = $null
  [void][System.Management.Automation.Language.Parser]::ParseInput(
    [Environment]::GetEnvironmentVariable($k), [ref]$t, [ref]$e)
  foreach ($x in $e) { $bad += ($k + ': ' + $x.Message) }
}
if ($bad.Count) { $bad -join ' | ' } else { 'PARSED' }
"""
    r = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", parse],
             capture_output=True, timeout=120,
             env={"GR_PS_RUN": P.PS, "GR_PS_STREAM": P.PS_STREAM, "GR_PS_COUNTED": P.PS_STREAM_COUNTED, "GR_PS_JSONL": P.PS_JSONL})
    assert (r.stdout or "").strip() == "PARSED", \
        f"a bridge script does not parse: {(r.stdout or r.stderr or '')[-300:]}"

    table = r"""
$ErrorActionPreference = 'Stop'
$o = [Console]::Out
$conn = New-Object System.Data.SqlClient.SqlConnection
try {
  $texts = @($env:GR_TEST -split ',' | ForEach-Object {
    [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) })
  $t = New-Object System.Data.DataTable
  [void]$t.Columns.Add('id', [int])
  [void]$t.Columns.Add('html', [string])
  [void]$t.Columns.Add('released', [datetime])
  [void]$t.Columns.Add('signed', [bool])
  [void]$t.Columns.Add('fee', [decimal])
  [void]$t.Rows.Add(1, $texts[0], [datetime]'2016-03-10T14:05:00', $true, [decimal]'1.50')
  [void]$t.Rows.Add(2, [System.DBNull]::Value, [System.DBNull]::Value, $false, [System.DBNull]::Value)
  [void]$t.Rows.Add(3, $texts[1], [datetime]'1999-01-01T00:00:00.123', $true, [decimal]'12')
  $o.WriteLine('COUNT ' + $t.Rows.Count); $o.Flush()
  $rdr = $t.CreateDataReader()
"""
    texts = [PAST_TEXT, ""]
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-pastps-"))
    saved, saved_env, saved_mark = P.PS_JSONL, os.environ.get("GR_TEST"), P.refusal.MARK
    try:
        # probe_db asks refusal.window_check() before every bridge. This one
        # opens no connection, so GitHub's night window on a stood-down laptop
        # has nothing to say about it: the record it reads is a temp folder's.
        P.refusal.MARK = tmp / "archive" / "refused.json"
        os.environ["GR_TEST"] = ",".join(base64.b64encode(x.encode("utf-8")).decode("ascii")
                                         for x in texts)
        P.PS_JSONL = table + P.PS_JSONL_ROWS + P.PS_JSONL_CLOSE
        out = tmp / "t.jsonl"
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            got = P.run_to_jsonl("never opened", "unused", "unused", out,
                                 types={"id": "int", "html": "varchar", "released": "datetime",
                                        "signed": "bit", "fee": "decimal"},
                                 columns=["id", "html", "released", "signed", "fee"],
                                 every=2, timeout=60)
        assert got == (3, 3, None), f"the bridge said {got}"
        rows = [json.loads(x) for x in out.read_text(encoding="utf-8").split("\n") if x]
        want = [{"id": 1, "html": PAST_TEXT, "released": "2016-03-10T14:05:00", "signed": True,
                 "fee": 1.5},
                {"id": 2, "html": None, "released": None, "signed": False, "fee": None},
                {"id": 3, "html": "", "released": "1999-01-01T00:00:00.123", "signed": True,
                 "fee": 12}]
        assert rows == want, f"PowerShell and back changed a value: {rows} != {want}"
        assert type(rows[2]["fee"]) is int and type(rows[0]["fee"]) is float
    finally:
        P.PS_JSONL, P.refusal.MARK = saved, saved_mark
        if saved_env is None:
            os.environ.pop("GR_TEST", None)
        else:
            os.environ["GR_TEST"] = saved_env
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("PS_JSONL's reader, run in PowerShell over a table, hands back a pipe, CRLF, "
                  "a tab, quotes, non-ASCII, U+2028, NULL and an empty string exactly; "
                  "PS, PS_STREAM and PS_JSONL parse")


@check("rollcalls", "a roll call in both the download and the archive is counted once, "
                    "from the download", needs=("build_data", "rollcall_parser"))
def _rollcall_once(build_data, rollcall_parser):
    """At the new term 2026 is archived as rollcalls/*_2026.txt while the
    download may still hold it, and build_data.rows_all and
    rollcall_parser.ballot_counts read every file and added them up: each
    2026 ballot would have counted twice on its member's record, and in the
    headline tally, with no error anywhere. A roll call now comes from the
    first file that holds it, the download first -- and by roll call rather
    than by year, so a new download carrying only a few of the old year's
    roll calls (organization day, if it is filed under 2026) does not take
    the whole year from those few. Real shapes, a byte-order mark included."""
    import io
    import contextlib
    tmp = Path(tempfile.mkdtemp(prefix="gr-rollonce-"))
    try:
        (tmp / "records" / "rollcalls").mkdir(parents=True)

        def put(name, lines):
            (tmp / name).write_text("\ufeff" + "\n".join(lines) + "\n", encoding="utf-8")
        put("RollCallHistory.txt", ["2026|H|1|100|11||Yea|", "2026|H|1|101|12||Nay|"])
        put("RollCallSummary.txt",
            ["2026|H|1|1/7/2026 10:15:33 AM|HB1|1|1|0|0|||Passage|the download|||"])
        # The archive holds the same roll call with other ballots, one the
        # download lacks, and a year of its own.
        put("records/rollcalls/RollCallHistory_2026.txt",
            ["2026|H|1|100|11||Nay|", "2026|H|1|101|12||Nay|", "2026|H|1|102|13||Yea|",
             "2026|H|2|100|11||Yea|"])
        put("records/rollcalls/RollCallSummary_2026.txt",
            ["2026|H|1|1/7/2026 10:15:33 AM|HB1|1|2|0|0|||Passage|the archive|||",
             "2026|H|2|1/7/2026 11:00:00 AM|HB2|1|0|0|0|||Passage|the archive|||"])
        put("records/rollcalls/RollCallHistory_2025.txt", ["2025|H|1|100|11||Yea|"])
        with contextlib.redirect_stdout(io.StringIO()):
            hist = build_data.rows_all(tmp, "RollCallHistory", 8)
            summ = build_data.rows_all(tmp, "RollCallSummary")
            counts = rollcall_parser.ballot_counts(current=tmp / "RollCallHistory.txt",
                                                   extra_dir=tmp / "records" / "rollcalls")
        by = Counter(tuple(r[:3]) for r in hist)
        assert by == {("2026", "H", "1"): 2, ("2026", "H", "2"): 1, ("2025", "H", "1"): 1}, by
        assert [r[6] for r in hist if tuple(r[:3]) == ("2026", "H", "1")] == ["Yea", "Nay"], \
            "roll call 1 of 2026 is not the download's"
        titles = {tuple(r[:3]): r[12] for r in summ}
        assert titles == {("2026", "H", "1"): "the download", ("2026", "H", "2"): "the archive"}, titles
        assert counts[("2026", "H", 1)] == Counter({"Yea": 1, "Nay": 1}), counts[("2026", "H", 1)]
        assert counts[("2026", "H", 2)] == Counter({"Yea": 1}) and \
            counts[("2025", "H", 1)] == Counter({"Yea": 1}), dict(counts)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a roll call in both is read once, from the download; one only the archive "
                  "holds is kept; ballots and summaries agree")


@check("reports", "a past term's Senate reports outlive the database's current view",
       needs=("fetch_reports_db", "senate_hearing_reports"))
def _reports_keep_terms(fetch_reports_db, senate_hearing_reports):
    """CandH_Reports is the database's current-term view, and both files made
    from it were written whole: the first run after the General Court turns
    it over to 2027-2028 would have written 2025-2026's reports out. Worse,
    fetch_reports_db's guard compared the run against the whole file, so it
    would have refused every night -- a handful of 2027 bills against a whole
    2025-2026 -- until somebody passed --force-write, which then dropped it.
    senate_reports.json is merged by term now and guarded term against term;
    senate_hearing_reports reads each term frozen under db/term/<term>/ after
    the current dump."""
    FR, SH = fetch_reports_db, senate_hearing_reports
    prev = {"2025-2026": {f"SB{i}": [{}] for i in range(1, 400)}}
    new = {"2027-2028": {"SB1": [{"x": 1}], "SB2": [{}]}}
    assert FR.shrunk(prev, new) == "", "a new term was judged against the old one"
    merged, kept = FR.merge_terms(prev, new)
    assert kept == ["2025-2026"] and set(merged) == {"2025-2026", "2027-2028"} \
        and merged["2027-2028"]["SB1"] == [{"x": 1}], (kept, list(merged))
    assert "2025-2026" in FR.shrunk(prev, {"2025-2026": {"SB1": [{}]}}), \
        "a term that lost most of its bills is no longer refused"
    assert FR.merge_terms(prev, {"2025-2026": {"SB1": []}})[0] == {"2025-2026": {"SB1": []}}, \
        "a term this run read must replace its own slice"
    src = _source(_paths.locate("fetch_reports_db.py"))
    assert "merged, kept = merge_terms(prev, out)" in src and "shrunk(prev, out)" in src, \
        "fetch_reports_db no longer writes through merge_terms and shrunk"
    saved = SH.parse_all
    try:
        SH.parse_all = lambda f: ({"2025-2026": {"SB9": ["frozen"]},
                                   "2027-2028": {"SB1": ["frozen 2027"]}}, {})
        # After the turn: the session's files are 2027-2028's (5 October 2026,
        # the finished term from its freeze whole; _finished_term_rule).
        out, said = SH.with_frozen({"2027-2028": {"SB1": ["current"]}}, [Path("db/term/2025-2026/x")],
                                   session="2027-2028")
    finally:
        SH.parse_all = saved
    assert out == {"2027-2028": {"SB1": ["current"]}, "2025-2026": {"SB9": ["frozen"]}}, out
    assert said == [(Path("db/term/2025-2026/x"), {"2025-2026": 1})], said
    src = _source(_paths.locate("senate_hearing_reports.py"))
    assert "with_frozen(out, frozen_sources())" in src, \
        "senate_hearing_reports no longer reads the frozen terms"
    kit = json.loads(_source("cloud_kit.json"))
    assert any("db/term/*/*" in e.get("globs", []) and e.get("owner") == "laptop"
               for e in kit["kit"]), "the kit does not carry db/term/, so GitHub's build would not"
    return "ok", ("a 2027 run keeps 2025-2026 and is judged against 2027 alone; a frozen term "
                  "supplies only what the current dump lacks; the kit carries it")


# ------------------------------------------- what the database fills (1 Oct 2026) --
#
# ONE BLOCK: the checks of the measures the General Court's search page left
# out of a past term (build_data.add_past_bills and its kin), the sponsors,
# chapters and designation flags its database fills, and the histories read
# from its past docket view. Every row in a fixture below is a real one,
# copied from db/past/PastLegislation.psv, PastSponsors.psv, the dockets, the
# saved bill pages and the House Journals on disk -- but for the few a
# comment says were made for a guard no real row exercises; the data checks
# at the foot read the files themselves.

def _pl_row(**kw):
    """One PastLegislation row as build_data.past_legislation gives it: the
    columns the builders read, blank or False unless given."""
    row = {k: "" for k in (
        "SessionYear", "LSR", "lsrtitle", "LegislativeBody", "CondensedBillNo",
        "ChapterNo", "HouseCommitteeReferralCode", "HouseStatusCode",
        "SenateCommitteeReferralCode", "SenateStatusCode", "GeneralStatusCode")}
    row.update({"AppropriationCode": "False", "FiscalImpactCode": "False",
                "LocalCode": "False"})
    row.update(kw)
    return row


# db/past/PastLegislation.psv, as dumped on 26 September 2026.
_PAST_ROWS = [
    # Withdrawn prior to introduction, 6 January 2010.
    _pl_row(SessionYear="2010", LSR="2113", LegislativeBody="H", CondensedBillNo="HB1308",
            lsrtitle="relative to health screenings for members of the general court.",
            FiscalImpactCode="True", HouseCommitteeReferralCode="H12",
            GeneralStatusCode="02"),
    # The Senate refused to introduce both; each still carries a referral code.
    _pl_row(SessionYear="2007", LSR="1345", LegislativeBody="S", CondensedBillNo="SB267",
            lsrtitle="relative to the effective date of the compulsory school attendance law.",
            FiscalImpactCode="True", SenateCommitteeReferralCode="S29",
            SenateStatusCode="24", GeneralStatusCode="03"),
    _pl_row(SessionYear="2016", LSR="2743", LegislativeBody="S", CondensedBillNo="SB499",
            lsrtitle="relative to the penalty for certain controlled drug offenses.",
            FiscalImpactCode="True", SenateCommitteeReferralCode="S07",
            SenateStatusCode="24", GeneralStatusCode="03"),
    # H45 is in no table today: Redress of Grievances, 2011-2012.
    _pl_row(SessionYear="2012", LSR="3043", LegislativeBody="H", CondensedBillNo="PET29",
            lsrtitle="grievance of Daniel Shepard.", HouseCommitteeReferralCode="H45",
            HouseStatusCode="01", GeneralStatusCode="02"),
    # H29 is the General Court's word for no committee.
    _pl_row(SessionYear="2012", LSR="3078", LegislativeBody="H", CondensedBillNo="HR31",
            lsrtitle="requesting an opinion of the justices concerning the "
                     "constitutionality of SB 372-FN-LOCAL.",
            HouseCommitteeReferralCode="H29", GeneralStatusCode="02"),
    _pl_row(SessionYear="2017", LSR="587", LegislativeBody="H", CondensedBillNo="HR1",
            lsrtitle="adopting the rules of the 2016 session for the 2017-2018 biennium.",
            HouseStatusCode="10", GeneralStatusCode="02"),
    # No bill number in the row: the docket files LSR 2007-0765 under HB633.
    _pl_row(SessionYear="2007", LSR="765", LegislativeBody="H",
            lsrtitle="requiring interpreting services upon request for persons "
                     "receiving medical treatment.",
            FiscalImpactCode="True", LocalCode="True", HouseCommitteeReferralCode="H09",
            GeneralStatusCode="02"),
    # No bill number and no docket row: a request, not a measure.
    _pl_row(SessionYear="2010", LSR="2156", LegislativeBody="H",
            lsrtitle="including the legislature as a public employer under the public "
                     "employees labor relations act.",
            FiscalImpactCode="True", GeneralStatusCode="02"),
    # Numbered, and never before a chamber: general status 01.
    _pl_row(SessionYear="2009", LSR="869", LegislativeBody="S", CondensedBillNo="SB27",
            lsrtitle="relative to child care employee fingerprinting.",
            FiscalImpactCode="True", SenateCommitteeReferralCode="S10",
            GeneralStatusCode="01"),
    # A placeholder: a number and nothing else.
    _pl_row(SessionYear="2024", LSR="8002", LegislativeBody="H", CondensedBillNo="HB8002"),
    # A number the term already has a record under (2010's SR 1, LSR 2973).
    _pl_row(SessionYear="2009", LSR="1052", LegislativeBody="S", CondensedBillNo="SR1",
            lsrtitle="requesting an opinion of the justices concerning the "
                     "constitutionality of SB 21.",
            SenateCommitteeReferralCode="S29", SenateStatusCode="10",
            GeneralStatusCode="03"),
]
# And three bills the archive already has, for the flags.
_PAST_FLAG_ROWS = [
    # HB 1282 of 2012 is headed "HB 1282-FN-LOCAL" on its own text, and HB 2
    # of 2003 "HB 2-FN-A".
    _pl_row(SessionYear="2012", LSR="2398", LegislativeBody="H", CondensedBillNo="HB1282",
            lsrtitle="relative to workforce housing and the definition of community.",
            FiscalImpactCode="True", LocalCode="True", HouseCommitteeReferralCode="H18",
            HouseStatusCode="10", GeneralStatusCode="02"),
    _pl_row(SessionYear="2003", LSR="1210", LegislativeBody="H", CondensedBillNo="HB2",
            lsrtitle="relative to state fees, funds, revenues, and expenditures.",
            AppropriationCode="True", FiscalImpactCode="True",
            HouseCommitteeReferralCode="H34", HouseStatusCode="18",
            SenateCommitteeReferralCode="S07", SenateStatusCode="17",
            GeneralStatusCode="07"),
    # And one no flag is set on: HB 1186 of 2012.
    _pl_row(SessionYear="2012", LSR="2613", LegislativeBody="H", CondensedBillNo="HB1186",
            lsrtitle="relative to uniform override keys for elevators.",
            HouseCommitteeReferralCode="H43", HouseStatusCode="20",
            GeneralStatusCode="02"),
]


@check("build", "a measure the General Court's database holds and the term's list lacks "
                "joins the record, and nothing else does", needs=("build_data",))
def _past_bills_into_data(BD):
    """build_data.add_past_bills, on real rows. The search page the archive's
    records came from left 23 measures out that PastLegislation holds; each
    becomes a record, in its own term, under its own number, with the
    General Court's words for its status codes and the source named.

    AND NOTHING ELSE: not over a record the term has (2009's SR 1 shares its
    number with 2010's, which has the record); not a request that was never
    before a chamber (SB 27 of 2009, general status 01) or has no title (HB
    8002 of 2024); not into a term that is not here, and never into the
    current one; not a row with no number that no docket row numbers.

    The committee is the docket's own where its introduction row names one,
    else the referral code's -- and none where the chamber REFUSED
    INTRODUCTION, whatever code the row keeps (SB 499 of 2016 carries S07,
    Finance, for a bill the Senate would not introduce), none for the General
    Court's "No Committee Assignment" (H29), and a retired code's name from
    committee_names.CODES (H45, Redress of Grievances) rather than the code.

    AND NONE FOR A BILL THAT WAS NEVER INTRODUCED, because a bill is referred
    when it is introduced. HB 1308 of 2010 is "To Be Introduced 1/6/2010 and
    Referred to Legislative Administration" and then "Withdrawn Prior to
    Introduction": with the committee on its record it was listed among that
    committee's bills. Which bills these are is narrative.build's answer for
    the bill's own docket rows, so with no docket on the machine the record
    keeps the committee. HB 633 of 2007's one row says "Introduced", and the
    House Journal's resolution of introduction steps over 633
    (INTRODUCTION_FROM_JOURNAL): the record carries that reading and no
    committee, and with the table empty it keeps both as the docket has them.

    A row with no number is numbered by the docket only where the docket
    files its LSR under exactly one number, that number is no other row's,
    and the LSR is on no record.

    And the one the docket holds with no title anywhere: HR 69 of 1992, titled
    from the bound House Journal (TITLED_FROM_JOURNAL), only where the docket
    carries it, never over a record, and never into the current term.
    """
    import contextlib
    import io
    general, body = BD.status_words(".")
    assert general.get("03") == "SENATE" and body.get("24") == "REFUSED INTRODUCTION", (
        f"GeneralCodes.txt and BodyStatusCodes.txt read as {general.get('03')!r} and "
        f"{body.get('24')!r}")
    committees = {"H12": {"name": "Legislative Administration"}, "S07": {"name": "Finance"},
                  "H29": {"name": "No Committee Assignment"}, "S10": {"name": "Judiciary"},
                  "H09": {"name": "Health, Human Services and Elderly Affairs"}}
    sr1 = {"bill": "SR1", "lsr": "2010-2973", "lsr_year": "2010", "lsr_num": "2973",
           "archived": True}

    def terms():
        return {"2007-2008": {"HB1": {"bill": "HB1", "lsr_year": "2007", "lsr_num": "1",
                                      "archived": True}},
                "2009-2010": {"SR1": sr1},
                "2011-2012": {"HB26": {"bill": "HB26", "lsr_year": "2011", "lsr_num": "4",
                                       "archived": True}},
                "2015-2016": {"HB224": {"bill": "HB224", "lsr_year": "2015",
                                        "lsr_num": "1", "archived": True}},
                # 2017 on, the archive writes an LSR padded to four.
                "2017-2018": {"CACR1": {"bill": "CACR1", "lsr_year": "2017",
                                        "lsr_num": "0412", "archived": True}},
                "2023-2024": {"HB1": {"bill": "HB1", "lsr_year": "2023", "lsr_num": "0001",
                                      "archived": True}},
                "2025-2026": {"HB1": {"bill": "HB1", "lsr_year": "2025",
                                      "lsr_num": "0001"}}}
    # MADE FOR THE GUARDS: no row on disk is one of these four. A request the
    # docket files under two numbers; one it files under a number the database
    # gives another row (SB267, below); one whose LSR a record already carries
    # (the HB 1 of 2007 here is LSR 1); and a bill the HOUSE refused to
    # introduce, for the House's side of the rule the two Senate bills hold.
    # FIRST, so that a row let through would take a number before its owner.
    guards = [
        _pl_row(SessionYear="2007", LSR="900", LegislativeBody="H",
                lsrtitle="a request the docket files under two numbers.",
                GeneralStatusCode="02"),
        _pl_row(SessionYear="2007", LSR="901", LegislativeBody="S",
                lsrtitle="a request the docket files under SB267.",
                GeneralStatusCode="03"),
        _pl_row(SessionYear="2007", LSR="1", LegislativeBody="H",
                lsrtitle="a request whose LSR a record carries.", GeneralStatusCode="02"),
        _pl_row(SessionYear="2011", LSR="950", LegislativeBody="H", CondensedBillNo="HB950",
                lsrtitle="a bill the House refused to introduce.",
                HouseCommitteeReferralCode="H12", HouseStatusCode="24",
                GeneralStatusCode="02")]
    past = guards + _PAST_ROWS + [
        _pl_row(SessionYear="1987", LSR="1", LegislativeBody="H", CondensedBillNo="HB1",
                lsrtitle="a bill of a term that is not here.", GeneralStatusCode="02"),
        _pl_row(SessionYear="2025", LSR="9999", LegislativeBody="H",
                CondensedBillNo="HB9999", lsrtitle="a row of the current term.",
                GeneralStatusCode="02")]
    # The docket's own first referral, as referrals.read_dockets gives it.
    refs = {("2009-2010", "HB1308"): {"H": "Legislative Administration"},
            ("2007-2008", "HB633"): {"H": "Health, Human Services and Elderly Affairs"}}
    root = Path(tempfile.mkdtemp())
    try:
        # Docket_db_2007-2008.txt line 6193: the row that numbers LSR 0765.
        # and, made for the guards, the rows that file the three requests.
        dk = root / "Docket_db_2007-2008.txt"
        dk.write_text(
            "2007|0765|01/31/2007 05:01:33 PM|HB633|H|Introduced and ref to Health, "
            "Human Services and Elderly Affairs;|01/31/2007 05:01:33 PM\n"
            "2007|0900|01/31/2007 05:02:00 PM|HB700|H|Introduced and ref to Finance;|"
            "01/31/2007 05:02:00 PM\n"
            "2007|0900|01/31/2007 05:03:00 PM|HB701|H|Introduced and ref to Finance;|"
            "01/31/2007 05:03:00 PM\n"
            "2007|0901|09/05/2007 10:30:00 AM|SB267|S|Introduced and Referred to "
            "Finance|09/05/2007 10:30:00 AM\n"
            "2007|0001|01/04/2007 10:00:00 AM|HB999|H|Introduced and ref to Finance;|"
            "01/04/2007 10:00:00 AM\n", encoding="utf-8")
        # Docket_db_2009-2010.txt lines 14258-14259: HB 1308's two rows.
        dk10 = root / "Docket_db_2009-2010.txt"
        dk10.write_text(
            "2010|2113|12/10/2009 11:23:39 AM|HB1308|H|To Be Introduced 1/6/2010 and "
            "Referred to Legislative Administration|12/10/2009 11:23:39 AM\n"
            "2010|2113|01/06/2010 11:33:17 AM|HB1308|H|Withdrawn Prior to Introduction|"
            "01/06/2010 11:33:17 AM\n", encoding="utf-8")
        dockets = {"2007-2008": str(dk), "2009-2010": str(dk10)}
        by_term = terms()
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            added = BD.add_past_bills(by_term, past, committees, refs, general, body,
                                      "2025-2026", dockets=dockets)
            # With no docket to number it, the unnumbered row stays out; and
            # with none to read, a bill keeps the committee its record names.
            bare = terms()
            none = BD.add_past_bills(bare, past, committees, refs, general, body,
                                     "2025-2026", dockets={})
            # With nothing read from the House Journal, the docket's word.
            alone = terms()
            BD.add_past_bills(alone, past, committees, refs, general, body, "2025-2026",
                              dockets=dockets, introductions={})
    finally:
        shutil.rmtree(root, ignore_errors=True)
    got = {t: sorted(bb) for t, bb in added.items()}
    assert got == {"2007-2008": ["HB633", "SB267"], "2009-2010": ["HB1308"],
                   "2011-2012": ["HB950", "HR31", "PET29"], "2015-2016": ["SB499"],
                   "2017-2018": ["HR1"]}, f"added {got}"
    assert sorted(by_term) == sorted(terms()), f"a term was created: {sorted(by_term)}"
    assert by_term["2009-2010"]["SR1"] is sr1 and "source" not in sr1, (
        "a database row was put over a record the term already has")
    assert "HB633" not in none.get("2007-2008", {}), (
        "a row with no bill number was added with no docket row to number it")
    # The three the docket cannot number.
    assert not {"HB700", "HB701"} & set(by_term["2007-2008"]), (
        "a request the docket files under two numbers was given one of them")
    assert by_term["2007-2008"]["SB267"]["lsr"] == "2007-1345", (
        "a row with no number took a number the database gives another row: SB267 is "
        f"LSR {by_term['2007-2008']['SB267']['lsr']}")
    assert "HB999" not in by_term["2007-2008"], (
        "a row whose LSR a record already carries was added under the docket's number")
    r = by_term["2009-2010"]["HB1308"]
    assert (r["lsr"], r["lsr_year"], r["lsr_num"], r["chamber"], r["designation"],
            r["house_committee"], r["gen_status"], r["house_status"], r["source"],
            r["archived"]) == (
        "2010-2113", "2010", "2113", "H", "HB 1308", "",
        "HOUSE", "", BD.PAST_SOURCE, True), (
        f"HB 1308 of 2010, withdrawn prior to introduction, reads {r}")
    assert none["2009-2010"]["HB1308"]["house_committee"] == "Legislative Administration", (
        "with no docket on the machine to say it was never introduced, the committee "
        "its record names was dropped")
    assert by_term["2011-2012"]["HB950"]["house_committee"] == "" and (
        by_term["2011-2012"]["HB950"]["house_status"] == "REFUSED INTRODUCTION"), (
        "a bill the House refused to introduce carries a House committee: "
        f"{by_term['2011-2012']['HB950']}")
    assert r["title"] == "relative to health screenings for members of the general court."
    for term, bid in (("2007-2008", "SB267"), ("2015-2016", "SB499")):
        s = by_term[term][bid]
        assert (s["gen_status"], s["senate_status"], s["senate_committee"],
                s["house_committee"]) == ("SENATE", "REFUSED INTRODUCTION", "", ""), (
            f"{bid} of {term}, which the Senate refused to introduce, reads {s}")
    p = by_term["2011-2012"]["PET29"]
    assert (p["house_committee"], p["house_status"], p["designation"]) == (
        "Redress of Grievances", "NO ACTION", "PET 29"), p
    assert by_term["2011-2012"]["HR31"]["house_committee"] == "", (
        "No Committee Assignment was published as a committee: "
        f"{by_term['2011-2012']['HR31']['house_committee']!r}")
    h = by_term["2017-2018"]["HR1"]
    assert (h["lsr"], h["lsr_num"], h["house_status"]) == (
        "2017-0587", "0587", "PASSED/ADOPTED"), h
    b = by_term["2007-2008"]["HB633"]
    assert (b["lsr"], b["house_committee"], b.get("number_source")) == (
        "2007-765", "", BD.DOCKET_SOURCE), (
        f"HB 633 of 2007, which the House Journal's resolution steps over, reads {b}")
    assert b.get("introduction") == BD.INTRODUCTION_FROM_JOURNAL[("2007-2008", "HB633")] \
        and b["introduction"]["introduced"] is False \
        and b["introduction"] is not BD.INTRODUCTION_FROM_JOURNAL[("2007-2008", "HB633")], b
    a = alone["2007-2008"]["HB633"]
    assert a["house_committee"] == "Health, Human Services and Elderly Affairs" and (
        "introduction" not in a), (
        "with no reading of the House Journal, HB 633's one docket row -- "
        f"\"Introduced and ref to ...\" -- did not stand: {a}")
    assert all("introduction" not in by_term[t][x] for t, x in (
        ("2009-2010", "HB1308"), ("2007-2008", "SB267"), ("2011-2012", "PET29"))), (
        "a record the House Journal table does not name carries a reading of it")
    assert all("number_source" not in by_term[t][x] for t, x in (
        ("2009-2010", "HB1308"), ("2007-2008", "SB267"))), (
        "a record numbered by the database says its number is the docket's")
    assert "8 measure(s)" in said.getvalue() and "HB633 2007-2008" in said.getvalue(), (
        f"what was added is not said: {said.getvalue()[-300:]}")
    assert "2 of them never introduced" in said.getvalue() and (
        "HB633 2007-2008, HB1308 2009-2010" in said.getvalue()), (
        f"the bills given no committee are not said: {said.getvalue()[-300:]}")

    # AND THE RECORDS OF A TERM'S OWN LIST THAT THE TABLE NAMES
    # (journal_introductions). HB 273 of 2017 as the search page and its
    # docket leave it -- a committee, and the page's IN COMMITTEE -- beside
    # HB 272, which the resolution names and the table does not. MADE FOR THE
    # GUARD: its Senate committee, which the real record does not have, so
    # that "no committee" is held for both chambers' fields.
    def of_the_list():
        return {
            "2011-2012": {"HB1512": {"bill": "HB1512", "archived": True,
                                     "house_committee": "Municipal and County Government",
                                     "introduction": {"introduced": True, "its": "own"}}},
            "2017-2018": {
                "HB272": {"bill": "HB272", "archived": True, "senate_committee": "",
                          "house_committee": "Municipal and County Government"},
                "HB273": {"bill": "HB273", "archived": True,
                          "senate_committee": "Executive Departments and Administration",
                          "house_committee": "Executive Departments and Administration",
                          "gen_status": "HOUSE", "house_status": "IN COMMITTEE"}},
            "2025-2026": {"HB1": {"bill": "HB1"}}}
    fact273 = BD.INTRODUCTION_FROM_JOURNAL[("2017-2018", "HB273")]
    with contextlib.redirect_stdout(io.StringIO()) as said:
        lt = of_the_list()
        done = BD.journal_introductions(lt, "2025-2026")
        untold = of_the_list()
        nothing = BD.journal_introductions(untold, "2025-2026", introductions={})
        # Never on the current term, whatever the table names.
        now = {"2017-2018": of_the_list()["2017-2018"]}
        current = BD.journal_introductions(now, "2017-2018")
        # A bill the journal names keeps the committee its record has.
        named = of_the_list()
        BD.journal_introductions(named, "2025-2026", introductions={
            ("2017-2018", "HB272"): {**fact273, "introduced": True}})
    assert done == [("2017-2018", "HB273")], f"the House Journal's word was put on {done}"
    r = lt["2017-2018"]["HB273"]
    assert r.get("introduction") == fact273 and r["introduction"] is not fact273 and (
        r["house_committee"], r["senate_committee"], r["house_status"]) == (
        "", "", "IN COMMITTEE"), (
        f"HB 273 of 2017, which the House's resolution of 4 January 2017 steps over, "
        f"reads {r}")
    assert lt["2017-2018"]["HB272"] == of_the_list()["2017-2018"]["HB272"], (
        "a bill the table does not name was changed: " + str(lt["2017-2018"]["HB272"]))
    assert lt["2011-2012"]["HB1512"] == of_the_list()["2011-2012"]["HB1512"], (
        "the table's reading went over one a record already carries")
    assert nothing == [] and untold == of_the_list(), (
        "with nothing read from the House Journal, a record of the list was changed")
    assert current == [] and now == {"2017-2018": of_the_list()["2017-2018"]}, (
        "the House Journal's table was put on a record of the current term")
    assert named["2017-2018"]["HB272"]["introduction"]["introduced"] is True and (
        named["2017-2018"]["HB272"]["house_committee"] == "Municipal and County "
        "Government"), "a bill the journal says was introduced lost its committee"
    assert "HB273 2017-2018" in said.getvalue() and (
        "1 of them never introduced, and given no committee" in said.getvalue()), (
        f"what the journal's word was put on is not said: {said.getvalue()[-300:]}")
    # And all four of 2017 are in the table as left out, with one resolution.
    assert all(BD.INTRODUCTION_FROM_JOURNAL.get(("2017-2018", b)) == fact273
               and fact273["introduced"] is False
               for b in ("HB177", "HB273", "HB274", "HB277")), (
        "HB 177, HB 273, HB 274 and HB 277 of 2017 are not in build_data's table as "
        "bills the resolution of 4 January 2017 leaves out")

    # HR 69 of 1992: the docket's, with the journal's title.
    with contextlib.redirect_stdout(io.StringIO()) as said:
        bt = {"1991-1992": {"HR68": {"bill": "HR68", "archived": True}}}
        added = BD.add_journal_titled(bt, {("1991-1992", "HR69"): "H"}, current="2025-2026")
        without = {"1991-1992": {}}
        nothing = BD.add_journal_titled(without, {}, current="2025-2026")
        mine = {"bill": "HR69", "title": "the record's own"}
        kept = {"1991-1992": {"HR69": mine}}
        BD.add_journal_titled(kept, {("1991-1992", "HR69"): "H"}, current="2025-2026")
    r = bt["1991-1992"].get("HR69") or {}
    assert added == {"1991-1992": {"HR69": r}} and r.get("title") == (
        "establishing procedures and deadlines for the filing of bills for the 1993 "
        "session."), r
    assert (r["lsr"], r["source"], r["title_source"]["journal"], r["title_source"]["page"],
            r["house_committee"], r["designation"]) == (
        "1992-2737", BD.DOCKET_SOURCE, "House Journal", 1154, "", "HR 69"), r
    assert nothing == {} and not without["1991-1992"], (
        "HR 69 was added with no docket row on the machine")
    assert kept["1991-1992"]["HR69"] is mine, "the journal's title went over a record"
    assert "not added" in said.getvalue(), "a titled measure left out went unsaid"
    # Never into the current term, whatever a table names.
    with contextlib.redirect_stdout(io.StringIO()):
        now = {"2025-2026": {}}
        took = BD.add_journal_titled(
            now, {("2025-2026", "HR69"): "H"}, current="2025-2026",
            table={("2025-2026", "HR69"): BD.TITLED_FROM_JOURNAL[("1991-1992", "HR69")]})
    assert took == {} and not now["2025-2026"], (
        "a measure titled from a journal was added to the current term")
    # The steps in build_data.main, in the order their comments give: every
    # term first, the database's measures, the journal-titled one, the House
    # Journal's own, and the flags last so the records just added take theirs.
    import inspect
    src = inspect.getsource(BD.main)
    at = [src.find(x) for x in ("add_past_bills(by_term", "add_journal_titled(by_term",
                                "add_journal_bills(by_term", "past_flags(by_term")]
    assert all(x >= 0 for x in at) and at == sorted(at), (
        "build_data.main no longer adds the database's measures, the journal-titled "
        f"one, the journal's own and then the flags, in that order: {at}")
    # And the journal's word on the list's own records: once every term is
    # in, and before the committees are named and the file written.
    at = [src.find(x) for x in ("add_past_bills(by_term", "journal_introductions(by_term",
                                "_official_committees(by_term", '"bills.json").write_text')]
    assert all(x >= 0 for x in at) and at == sorted(at), (
        "build_data.main no longer puts the House Journal's word on the records of the "
        f"terms' own lists before it writes bills.json: {at}")
    return "ok", ("7 real rows added, each in its term under its own number; a record, "
                  "a request, a placeholder, a missing term and the current term left "
                  "alone; a row with no number numbered only by one docket number "
                  "nothing else has; no committee for a bill refused introduction or "
                  "never introduced; the House Journal's word, and no committee, on "
                  "HB 273 of 2017, a record of the search page's own list; HR 69 titled "
                  "from the journal only where the docket holds it")


@check("build", "an archived designation takes its flags from the database, and only "
                "where it has none", needs=("build_data",))
def _past_flags(BD):
    """build_data.past_flags, on real rows. HB 1282 of 2012 is headed "HB
    1282-FN-LOCAL" on its own text and HB 2 of 2003 "HB 2-FN-A"; the search
    page gave "HB 1282" and "HB 2". The three flags are the database's
    AppropriationCode, FiscalImpactCode and LocalCode, written in the order
    the current term's designations are: -FN, -A, -LOCAL.

    ONLY WHERE THE DESIGNATION HAS NONE, and only an archived record: not the
    current term's, not a record that carries flags or a suffix already, not
    a journal record's printed designation, not a bill whose LSR the database
    files under another number -- and a bill no flag is set on is left
    exactly as it was, with no key added.
    """
    def rec(bid, year, lsr, **kw):
        return {"bill": bid, "lsr": f"{year}-{lsr}", "lsr_year": year, "lsr_num": lsr,
                "designation": re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid),
                "archived": True, **kw}
    plain = rec("HB1186", "2012", "2613")
    was = dict(plain)
    by_term = {
        "2011-2012": {"HB1282": rec("HB1282", "2012", "2398"), "HB1186": plain,
                      # The same LSR under another number: the guard.
                      "HB999": rec("HB999", "2012", "2398")},
        "2003-2004": {"HB2": rec("HB2", "2003", "1210"),
                      # Already flagged, by whatever wrote it.
                      "HB3": rec("HB3", "2003", "1210", suffix="-FN",
                                 designation="HB 3-FN")},
        "2021-2022": {"HB459": {"bill": "HB459", "lsr": "", "lsr_year": "2021",
                                "lsr_num": "", "designation": "HB 459", "suffix": "",
                                "archived": True, "journal": {}}},
        # The current term, with a row of the same LSR: untouched -- for
        # being the current term, even were a record of it marked archived.
        "2025-2026": {"HB1282": {"bill": "HB1282", "lsr_year": "2012", "lsr_num": "2398",
                                 "designation": "HB 1282", "archived": True}}}
    done = BD.past_flags(by_term, _PAST_FLAG_ROWS, "2025-2026")
    a = by_term["2011-2012"]["HB1282"]
    assert (a["designation"], a["suffix"], a["flags"]) == (
        "HB 1282-FN-LOCAL", "-FN-LOCAL", {"a": False, "fn": True, "local": True}), a
    b = by_term["2003-2004"]["HB2"]
    assert (b["designation"], b["flags"]) == (
        "HB 2-FN-A", {"a": True, "fn": True, "local": False}), b
    assert plain == was, f"a bill no flag is set on was changed: {plain}"
    assert by_term["2011-2012"]["HB999"]["designation"] == "HB 999", (
        "a bill took the flags of an LSR the database files under another number")
    assert by_term["2003-2004"]["HB3"]["designation"] == "HB 3-FN"
    assert by_term["2021-2022"]["HB459"]["designation"] == "HB 459"
    assert by_term["2025-2026"]["HB1282"] == {
        "bill": "HB1282", "lsr_year": "2012", "lsr_num": "2398",
        "designation": "HB 1282", "archived": True}, (
        "a record of the current term was changed")
    assert dict(done) == {"-FN-LOCAL": 1, "-FN-A": 1}, dict(done)
    assert BD.past_flags({"2011-2012": {"HB1282": rec("HB1282", "2012", "2398")}}, None,
                         "2025-2026") == Counter(), "flags were written with no table"
    # Each of the three things that leave a record alone, on a record that is
    # the database's own row in every other respect: a suffix already there,
    # flags already there, and a record that is not the archive's.
    for why, kw in (("a suffix", {"suffix": "-FN", "designation": "HB 1282-FN"}),
                    ("flags", {"flags": {"a": False, "fn": True, "local": False}}),
                    ("no archived mark", {"archived": False})):
        mine = rec("HB1282", "2012", "2398", **kw)
        kept = dict(mine)
        got = BD.past_flags({"2011-2012": {"HB1282": mine}}, _PAST_FLAG_ROWS, "2025-2026")
        assert mine == kept and not got, (
            f"a record with {why} of its own was given the database's flags: {mine}")

    # AND NOT AGAINST THE BILL'S OWN PAGE. The heads of four saved pages, as
    # saved: the version line and the caption of 1999's HB 25 both print
    # -FN-A where the database has the appropriation flag alone; 2022's HB
    # 1419 prints -A where it has the fiscal note alone; 1993's HB 275 prints
    # the bare number where it has -LOCAL; 2012's HB 1282 prints what it has.
    root = Path(tempfile.mkdtemp())
    try:
        for name, text in _SAVED_PAGE_HEADS.items():
            (root / name).write_text(text, encoding="utf-8")
        read = lambda name, kind, num: BD.printed_designations(root / name, kind, num)
        assert read("HB0025.html", "HB", 25) == {"-FN-A"}, read("HB0025.html", "HB", 25)
        assert read("HB1419.html", "HB", 1419) == {"-A"}, read("HB1419.html", "HB", 1419)
        assert read("HB0275.html", "HB", 275) == {""}, read("HB0275.html", "HB", 275)
        assert read("HB1282.html", "HB", "1282") == {"-FN-LOCAL"}, (
            read("HB1282.html", "HB", "1282"))
        # The version line alone says it, on a page cut before its caption.
        (root / "cut.html").write_text(
            _SAVED_PAGE_HEADS["HB1282.html"].split("<p align=\"center\"><font")[0],
            encoding="utf-8")
        assert read("cut.html", "HB", 1282) == {"-FN-LOCAL"}, read("cut.html", "HB", 1282)
        # Another number's page, and no page: nothing printed for this one.
        assert read("HB0025.html", "HB", 26) == set() and read("HB0025.html", "HB", 2) == set()
        assert read("absent.html", "HB", 25) == set()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # db/past/PastLegislation.psv's rows for LSR 1999-1017, 2022-2827 and
    # 1993-0194.
    rows = _PAST_FLAG_ROWS + [
        _pl_row(SessionYear="1999", LSR="1017", LegislativeBody="H", CondensedBillNo="HB25",
                lsrtitle="making appropriations for capital improvements.",
                AppropriationCode="True", GeneralStatusCode="07"),
        _pl_row(SessionYear="2022", LSR="2827", LegislativeBody="H",
                CondensedBillNo="HB1419",
                lsrtitle="relative to establishing a New Hampshire civilian climate "
                         "corps advisory commission.",
                FiscalImpactCode="True", GeneralStatusCode="02"),
        _pl_row(SessionYear="1993", LSR="194", LegislativeBody="H", CondensedBillNo="HB275",
                lsrtitle="allowing towns to create special funds for highway "
                         "expenditures.", LocalCode="True", GeneralStatusCode="07")]
    pages = {("1999-2000", "HB25"): {"-FN-A"}, ("2021-2022", "HB1419"): {"-A"},
             ("1993-1994", "HB275"): {""},
             # Two forms on one page, one of them the database's: agrees.
             ("2011-2012", "HB1282"): {"", "-FN-LOCAL"}}
    held = {"1999-2000": {"HB25": rec("HB25", "1999", "1017")},
            "2021-2022": {"HB1419": rec("HB1419", "2022", "2827")},
            "1993-1994": {"HB275": rec("HB275", "1993", "194")},
            "2011-2012": {"HB1282": rec("HB1282", "2012", "2398")},
            # No saved page: nothing to hold the flags to, and they are written.
            "2003-2004": {"HB2": rec("HB2", "2003", "1210")}}
    asked = []

    def printed(term, bid, record):
        asked.append((term, bid))
        return pages.get((term, bid), set())
    done = BD.past_flags(held, rows, "2025-2026", printed=printed)
    for term, bid, bare in (("1999-2000", "HB25", "HB 25"), ("2021-2022", "HB1419", "HB 1419"),
                            ("1993-1994", "HB275", "HB 275")):
        r = held[term][bid]
        assert r["designation"] == bare and "flags" not in r and "suffix" not in r, (
            f"{bid} of {term} was written {r['designation']!r} from the database over a "
            f"page that prints {sorted(pages[(term, bid)])}")
    assert sorted(BD.PAST_FLAGS_REFUSED) == [
        ("1993-1994", "HB275", "-LOCAL", [""]), ("1999-2000", "HB25", "-A", ["-FN-A"]),
        ("2021-2022", "HB1419", "-FN", ["-A"])], BD.PAST_FLAGS_REFUSED
    assert held["2011-2012"]["HB1282"]["designation"] == "HB 1282-FN-LOCAL" and (
        held["2003-2004"]["HB2"]["designation"] == "HB 2-FN-A") and dict(done) == {
        "-FN-LOCAL": 1, "-FN-A": 1}, (held, dict(done))
    assert len(asked) == 5, f"the page was asked of {asked}"
    # The list is of the last run, not of every run before it.
    BD.past_flags({"2003-2004": {"HB2": rec("HB2", "2003", "1210")}}, rows, "2025-2026",
                  printed=printed)
    assert BD.PAST_FLAGS_REFUSED == [], BD.PAST_FLAGS_REFUSED
    return "ok", ("HB 1282-FN-LOCAL and HB 2-FN-A from the database's three columns; a "
                  "bill with no flag set, one with a suffix, a journal record, another "
                  "number's LSR and the current term untouched; and nothing written "
                  "where the bill's own saved page prints another designation")


# db/Legislation.psv's rows for HB 422, HB 664, HB 138 and SB 131 of 2025 and
# HB 1442 of 2026, as dumped on 8 September 2026, cut after column 26 (the
# Senate committee): the fill reads no further.
_LEGISLATION_2025_ROWS = [
    "0422|HB|2025|0182|increasing penalties for violations of the shoreland and water "
    "quality protection act.|True|H|1|False|True|False|25-0182|ENC|HB  0422|HB422|"
    "01/09/2025 12:30:00||R|H22|H22|01/09/2025 00:00:00|09||03/06/2025 00:00:00|"
    "02/13/2025 00:00:00|0||",
    "0664|HB|2025|0239|relative to childhood immunization requirements.|True|H|1|True|"
    "False|False|25-0239|PMH|HB  0664|HB664|01/17/2025 11:53:00||R|H09|H09|"
    "01/09/2025 00:00:00|09||03/20/2025 00:00:00|03/26/2025 00:00:00|0||",
    "0138|HB|2025|0278|relative to tax impact notation on warrant articles with multi-year "
    "tax impacts.|True|H|1|False|False|True|25-0278|MUN|HB  0138|HB138|"
    "12/31/2024 16:18:00|144|R|H18|H18|01/08/2025 00:00:00|10||03/20/2025 00:00:00|"
    "03/26/2025 00:00:00|0|S92",
    "0131|SB|2025|1064|relative to long-term care eligibility and making an appropriation "
    "therefor.|True|S|2|True|True|False|25-1064|PMH|SB  0131|SB131|01/21/2025 17:13:00||R"
    "||||||||0|S26",
    "1442|HB|2026|2729|(New Title) permitting classification of individuals based on "
    "biological sex under certain limited circumstances.|True|H|1|False|True|False|"
    "26-2729|DIS|HB  1442|HB1442|12/03/2025 08:56:00||R|H10|H10|01/07/2026 00:00:00|18||"
    "03/05/2026 00:00:00|08/19/2026 00:00:00|1|S10"]


@check("build", "a bill of the session's first year takes its -FN, -A and -LOCAL from "
                "the Legislation view, where LSRs.txt does not carry it",
       needs=("build_data",))
def _first_year_designations(BD):
    """build_data.fill_from_legislation, on real rows (the audit of 7 October
    2026, cause 13). LSRs.txt lists session 2026 alone, so every bill of 2025
    was a stub and 449 of them showed the bare number: "HB 422" for HB
    422-FN, "SB 131" for SB 131-FN-A. The view's AppropriationCode,
    FiscalImpactCode and LocalCode give them, in the order the bills print
    them. A 2026 bill keeps what LSRs.txt gave it; a row of another term or
    another LSR fills nothing."""
    def stub(bid, year, lsr):
        return {"bill": bid, "lsr": f"{year}-{lsr}", "lsr_year": year, "lsr_num": lsr,
                "title": "", "chamber": bid[0], "subject_code": "", "subject": "",
                "house_committee": "", "senate_committee": "", "hearing": "",
                "hearing_room": "", "stub": True}
    hb1442 = {**stub("HB1442", "2026", "2729"), "stub": False, "subject_code": "DIS",
              "house_committee": "Judiciary", "senate_committee": "Judiciary",
              "flags": {"a": False, "fn": True, "local": False}, "suffix": "-FN",
              "designation": "HB 1442-FN"}
    kept = json.loads(json.dumps(hb1442))
    bills = {"HB422": stub("HB422", "2025", "0182"), "HB664": stub("HB664", "2025", "0239"),
             "HB138": stub("HB138", "2025", "0278"), "SB131": stub("SB131", "2025", "1064"),
             "HB1442": hb1442}
    filled = BD.fill_from_legislation(bills, _LEGISLATION_2025_ROWS, {}, {})
    got = {b: bills[b].get("designation") for b in ("HB422", "HB664", "HB138", "SB131")}
    assert got == {"HB422": "HB 422-FN", "HB664": "HB 664-A", "HB138": "HB 138-LOCAL",
                   "SB131": "SB 131-FN-A"}, f"the 2025 bills are designated {got}"
    assert bills["SB131"]["flags"] == {"a": True, "fn": True, "local": False} and (
        bills["SB131"]["suffix"] == "-FN-A"), bills["SB131"]
    assert bills["HB1442"] == kept, f"a 2026 bill's LSRs.txt flags were changed: {bills['HB1442']}"
    assert filled["designation"] == 4, dict(filled)
    # A row of another LSR, and one of another term, fill nothing.
    other = {"HB422": stub("HB422", "2025", "0999"), "HB664": stub("HB664", "2023", "0239")}
    BD.fill_from_legislation(other, _LEGISLATION_2025_ROWS, {}, {})
    assert not any("designation" in r for r in other.values()), other
    # The LSRs.txt reading and this one write one form: -FN, -A, -LOCAL, in order.
    assert BD.designation_of("HB1442", True, True, True)[1:] == ("-FN-A-LOCAL",
                                                                 "HB 1442-FN-A-LOCAL")
    return "ok", ("HB 422-FN, HB 664-A, HB 138-LOCAL and SB 131-FN-A from the view; HB "
                  "1442 of 2026 as LSRs.txt gave it; another LSR's or term's row fills "
                  "nothing")


@check("build", "a bill the docket carries and LSRs.txt does not takes its title from the Legislation "
                "view: a new term's first bills the morning their text is public, before the export's "
                "request files carry their year", needs=("build_data",))
def _stub_titles_from_legislation(BD):
    """The rehearsal of 17 November 2026. A request becomes a bill the day
    its text is public, and its first docket row comes that day (2025's HB 10:
    made a bill on 19 December 2024, its text and its docket row 23 December).
    LSRs.txt and LsrsOnly.txt hold one session year, so a bill of the next
    year that the docket names before they turn is a stub, and the fixture
    night of 18 December built 2027's HB 1 with no title: request 2027-0001's
    page, which had one, forwarded to a page headed "HB 1" alone. The view
    the night takes after the switch (nightly.TERM_VIEWS) gives LSRTitle,
    the title LSRs.txt's field 2 gives. On real rows of 8 September: a stub
    is titled; a stub with a title, a bill LSRs.txt carries, and a row of
    another LSR or another term give none."""
    def stub(bid, year, lsr, title=""):
        return {"bill": bid, "lsr": f"{year}-{lsr}", "lsr_year": year, "lsr_num": lsr,
                "title": title, "chamber": bid[0], "subject_code": "", "subject": "",
                "house_committee": "", "senate_committee": "", "hearing": "",
                "hearing_room": "", "stub": True}
    bills = {"HB422": stub("HB422", "2025", "0182"), "HB664": stub("HB664", "2025", "0239"),
             "HB138": stub("HB138", "2025", "0278", "a title the roll calls gave."),
             "HB1442": {**stub("HB1442", "2026", "2729"), "stub": False}}
    filled = BD.fill_from_legislation(bills, _LEGISLATION_2025_ROWS, {}, {})
    assert bills["HB422"]["title"] == ("increasing penalties for violations of the shoreland and "
                                       "water quality protection act.") and \
        bills["HB664"]["title"] == "relative to childhood immunization requirements.", (
        "a stub took no title from the view", bills["HB422"]["title"], bills["HB664"]["title"])
    assert bills["HB138"]["title"] == "a title the roll calls gave.", bills["HB138"]["title"]
    assert bills["HB1442"]["title"] == "", ("a bill LSRs.txt carries was given the view's title",
                                            bills["HB1442"]["title"])
    assert filled["title"] == 2, dict(filled)
    other = {"HB422": stub("HB422", "2025", "0999"), "HB664": stub("HB664", "2023", "0239")}
    BD.fill_from_legislation(other, _LEGISLATION_2025_ROWS, {}, {})
    assert not any(r["title"] for r in other.values()), other
    return "ok", ("HB 422 and HB 664 of 2025, as stubs, titled from the view; a stub's own title, a "
                  "bill LSRs.txt carries and another LSR's or term's row left as they were")


@check("build", "a new bill no sponsor file names yet carries its request's prime sponsor and co-sponsors, "
                "each the one member of the term's roster of that name, else the name as listed; a bill "
                "the files name, and another year's, are left as they are", needs=("build_data",))
def _new_bill_takes_request_sponsors(BD):
    """The rehearsal of 17 November 2026 built 2027's HB 1 with no sponsor: a request is numbered as a
    bill weeks before LsrsOnly.txt and LsrSponsors.txt hold its year (they hold one, and turn in
    January). The owner, the same day: once signed off, "the bill text shows as a PDF on the lsr
    search page along with the co-sponsors". build_data.sponsors_from_requests gives such a bill its
    request's prime sponsor and co-sponsors from the night's lsrs.json, in the list's order, by the
    year and the LSR number, each the one member of the term's roster whose first and last name it is
    (two of a name are neither), else the name as the list prints it with no member; a bill a sponsor
    file names keeps its own, and a bill of another year with the same LSR number takes nothing. And
    build_data's own run asks it, for the session's build and not a frozen term's."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-request-sponsors-"))
    roster = {k: {"id": k, "first": f, "last": l, "name": f"{l}, {f}", "party_code": p, "chamber": "H",
                  "label": f"Rep. {f} {l} ({p} - Rock {k[-1]})"}
              for k, f, l, p in (("9001", "Ellen", "Read", "D"), ("9002", "Bob", "Roe", "R"),
                                 ("9003", "Jane", "Doe", "D"), ("9004", "Jane", "Doe", "R"))}
    try:
        path = tmp / "lsrs.json"
        path.write_text(json.dumps([
            {"lsr": "2027-0001", "session": 2027, "body": "HB", "sponsor": "Ellen Read",
             "cosponsors": ["Bob Roe", "Jane Doe", "Dee New"], "withdrawn": True},
            {"lsr": "2027-0002", "session": 2027, "body": "SB", "sponsor": "Bob Roe", "cosponsors": []}]),
            encoding="utf-8")
        own = [{"member_id": "9002", "name": "Roe, Bob", "prime": True, "sequence": 0}]
        sponsors = {"SB7": list(own)}
        bills = {"HB45": {"lsr_year": "2027", "lsr_num": "1"}, "SB7": {"lsr_year": "2027", "lsr_num": "0002"},
                 "HB1001": {"lsr_year": "2026", "lsr_num": "1"}}
        took = BD.sponsors_from_requests(bills, sponsors, path, roster)
        got = [(s["member_id"], s["label"], s["prime"], s["sequence"], s["source"])
               for s in sponsors.get("HB45") or []]
        assert took == 1 and got == [
            ("9001", "Rep. Ellen Read (D - Rock 1)", True, 0, BD.REQUEST_SOURCE),
            ("9002", "Rep. Bob Roe (R - Rock 2)", False, 1, BD.REQUEST_SOURCE),
            ("", "Jane Doe", False, 2, BD.REQUEST_SOURCE), ("", "Dee New", False, 3, BD.REQUEST_SOURCE)], (
            took, got)
        assert sponsors["SB7"] == own, f"a bill a sponsor file names was given its request's: {sponsors['SB7']}"
        assert "HB1001" not in sponsors, "a bill of another year took a request's sponsors by its number"
        assert BD.sponsors_from_requests(bills, {}, tmp / "none.json", roster) == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = _source(_paths.locate("build_data.py"))
    assert re.search(r"if not frozen:\s+took = sponsors_from_requests\(bills, sponsors, Path\(\"lsrs\.json\"\), "
                     r"term_legs\)", src), "build_data's run no longer asks its requests for a new bill's sponsors"
    return "ok", ("HB 45 of 2027 took Ellen Read (prime), Bob Roe and two names as listed (one shared by two "
                  "members, one nobody's); SB 7, which a file names, and HB 1001 of 2026 kept their own")


# The heads of four saved bill pages, as fetch_legislation.py saved them --
# legislation/1999/HB0025.html, legislation/2022/HB1419.html,
# legislation/1993/HB0275.html and legislation/2012/HB1282.html -- cut after
# the caption, and less the generator's META lines, most of 2022's style
# sheet and 1999's five other amendment stamps.
_SAVED_PAGE_HEADS = {
    "HB0025.html": """<HTML>
<HEAD>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; CHARSET=iso-8859-1">
<TITLE> 0226-hb 0025 </TITLE>
</HEAD>
<BODY><A NAME="TopOfPage"> </A>

<P ALIGN="CENTER"><B><FONT FACE="Century Schoolbook">CHAPTER 226</FONT></B></P>

<P ALIGN="CENTER"><B><FONT FACE="Century Schoolbook">HB 25-FN-A - FINAL VERSION</FONT></B></P>

<P><FONT FACE="Century Schoolbook">13may99.....0917h</FONT></P>

<P ALIGN="CENTER"><FONT FACE="Century Schoolbook">1999 SESSION</FONT></P>

<P><FONT FACE="Century Schoolbook">99-1017</FONT></P>

<P><FONT FACE="Century Schoolbook">10/09</FONT></P>

<P><FONT FACE="Century Schoolbook">HOUSE BILL</FONT><B><I><FONT FACE="Century Schoolbook" SIZE="+1">  25-FN-A</FONT></I></B></P>

<P><FONT FACE="Century Schoolbook">AN ACT making appropriations for capital improvements.</FONT></P>
""",
    "HB1419.html": """<html><head><style type="text/css">
.cs2E86D3A6{text-align:center;text-indent:0pt;margin:0pt 0pt 0pt 0pt}
.cs5925EB86{color:#000000;font-family:'Times New Roman';font-size:12pt;font-weight:bold;}
</style>
	</head>
	<body>
		<p class="cs2E86D3A6"><span class="cs5925EB86">HB 1419-A - AS INTRODUCED</span></p><p class="cs2E86D3A6"><span class="cs5925EB86">&nbsp;</span></p><p class="cs2E86D3A6"><span class="csDD5E5F52">2022 SESSION</span></p><p class="cs95E872D0" style="tab-stops:left 396pt;"><span class="csDD5E5F52">	22-2827</span></p><p class="cs95E872D0" style="tab-stops:left 396pt;"><span class="csDD5E5F52">	07/10</span></p><p class="cs95E872D0" style="tab-stops:left 108pt;"><span class="csDD5E5F52">HOUSE BILL	</span><span class="csED7826F6">1419-A</span></p><p class="csE0B838BE"><span class="csDD5E5F52">AN ACT	</span><a name="bkTitleDraft0"><span class="csDD5E5F52">relative to establishing a New Hampshire civilian climate corps advisory commission.</span></a></p>
""",
    "HB0275.html": """<HTML>
<HEAD>
<TITLE> HB 0275 </TITLE>
</HEAD>
<BODY><A NAME="TopOfPage"> </A>

<P><FONT FACE="Courier New">18feb93.....1161h</FONT></P>

<H1 ALIGN=CENTER><A NAME="P19_64"></A>
<U><FONT FACE="Courier New" SIZE="+0">HOUSE&#160;BILL&#160;-&#160;FINAL&#160;VERSION</FONT></U></H1>

      <UL><UL><UL><P><FONT FACE="Courier New"><B><I>1993 SESSION</I></B> 0184B</FONT></P>

        <UL><P><FONT FACE="Courier New">93-0194</FONT></P>

        <P><FONT FACE="Courier New">08</FONT></P>

</UL></UL></UL></UL><P><FONT FACE="Courier New">HOUSE BILL NO.<U> &#160;&#160;&#160;275&#160;&#160;&#160;</U></FONT></P>

<P><FONT FACE="Courier New">INTRODUCED BY:  Rep. J. Chandler of Merr 1; Rep. Cowenhoven of Hills 14; </FONT></P>
""",
    "HB1282.html": """<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
<title>HB 1282</title>
</head>
<body><a name="TopOfPage"> </a>

<p align="center"><b><font face="Century Schoolbook">HB 1282-FN-LOCAL &#8211; AS INTRODUCED</font></b></p>

<p align="center"><font face="Century Schoolbook">2012 SESSION</font></p>

<p><font face="Century Schoolbook"><a name="P5_46"></a>12-2398</font></p>

<p><font face="Century Schoolbook">06/10</font></p>

<p><font face="Century Schoolbook">HOUSE BILL</font><b><i><font face="Century Schoolbook" size="+1">  1282-FN-LOCAL</font></i></b></p>

<p><font face="Century Schoolbook"><a name="P10_81"></a>AN ACT relative to workforce housing and the definition of community.</font></p>
""",
}


@check("status", "a chapter the docket gave to two bills is settled by the database "
                 "where it tells them apart, and the history says the same number",
       needs=("extract_chapters", "narrative", "build_site_v2"))
def _chapters_settled(EC, N, B):
    """extract_chapters.settle_clashes, on the docket's own rows. HB 1278 and
    HB 1330 of 1992 both read "CHAP.0233"; both were withheld. The General
    Court's database has 232 and 233, and each one's final version is headed
    with the database's number, so each takes it.

    SB 244 of 2015 and SB 524 of 2016 are each chapter 127 -- of two years'
    laws. The docket dates SB 244's signature "06/11/16" on a row entered on
    16 June 2015, which read as a second chapter 127 of 2016. A law line
    entered in an earlier year than it states is of the earlier year's.

    Only a withheld number is filled, and never with a number another bill of
    that year holds or the database also gives the other claimant: were the
    database to say 233 for both of 1992's, neither would be filled. The
    current term's clashes have no row in the past table and stay withheld.

    And narrative.confirmed_chapter tells the history with the number the
    page prints: "making it Chapter 232", not the docket's 233.

    A LINE THAT CARRIES ANOTHER BILL'S CHAPTER CAN CARRY ITS EFFECTIVE DATE.
    SB 28 of 2009's reads "Signed by the Governor on 05/15/09; Effective
    07/07/09; Chapter 0028", which is SB 109's line with the signature's day
    changed: SB 28 is chapter 31, in effect 14 July by its enrolled text and
    by the database. A settled record whose docket number was the other
    bill's carries the database's day (database_effective), and the rail
    takes it only where the line states one day and the database another.
    """
    bills = {
        "1991-1992": {"HB1278": {"lsr_year": "1992", "lsr_num": "2552"},
                      "HB1330": {"lsr_year": "1992", "lsr_num": "2513"}},
        "2015-2016": {"SB244": {"lsr_year": "2015", "lsr_num": "1004"},
                      "SB524": {"lsr_year": "2016", "lsr_num": "2962"}},
        "2025-2026": {"HB511": {"lsr_year": "2025", "lsr_num": "0594"},
                      "SB62": {"lsr_year": "2025", "lsr_num": "1016"}}}
    # Docket_db_1991-1992.txt lines 18447 and 18133, Docket_2015-2016.txt
    # lines 7791 and 20677, Docket.txt lines 9440 and 9443.
    rows = [
        ("d", "1992", "2552", "HB1278", "05/13/1992 02:31:47 PM",
         "SIGNED BY GOVERNOR 05/13/92  EFF: 01/01/93 CHAP.0233"),
        ("d", "1992", "2513", "HB1330", "05/13/1992 02:37:45 PM",
         "SIGNED BY GOVERNOR  05/13/92 EFF: 01/01/93 CHAP.0233"),
        ("d", "2015", "1004", "SB244", "06/16/2015 08:14:48 AM",
         "Signed by the Governor on 06/11/16; Chapter 0127"),
        ("d", "2016", "2962", "SB524", "5/24/2016 12:00:00 AM",
         "Signed by the Governor on 05/20/2016; Chapter 0127; Effective 05/20/2016"),
        ("d", "2025", "0594", "HB511", "5/22/2025 2:51:19 PM",
         "Signed by Governor Ayotte 05/22/2025; Chapter 39; eff. 01/01/2026"),
        ("d", "2025", "1016", "SB62", "5/22/2025 3:50:39 PM",
         "Signed by the Governor on 05/22/2025; Chapter 0039; Effective 01/01/2026")]
    saved = EC.rows
    try:
        EC.rows = lambda: iter(rows)
        found, _skipped = EC.read(bills)
    finally:
        EC.rows = saved

    def withheld():
        out, held = EC.settle(found)
        assert sorted((t, b) for t, b, _n, _y in held) == [
            ("1991-1992", "HB1278"), ("1991-1992", "HB1330"), ("2015-2016", "SB244"),
            ("2015-2016", "SB524"), ("2025-2026", "HB511"), ("2025-2026", "SB62")], held
        return out
    out = withheld()
    # db/past/PastLegislation.psv's ChapterNo for the four past bills.
    said = {("1991-1992", "HB1278"): 232, ("1991-1992", "HB1330"): 233,
            ("2015-2016", "SB244"): 127, ("2015-2016", "SB524"): 127}
    # And its EffectiveDate for each, as database_check hands it on.
    took_effect = {("1991-1992", "HB1278"): "1993-01-01", ("1991-1992", "HB1330"): "1993-01-01",
                   ("2015-2016", "SB524"): "2016-05-20"}
    settled, unsettled = EC.settle_clashes(out, found, dict(said), took_effect)
    assert len(settled) == 4 and not unsettled, (settled, unsettled)
    a, b = out["1991-1992"]["HB1278"], out["1991-1992"]["HB1330"]
    assert (a["chapter"], a["docket"], b["chapter"], b["docket"]) == (232, 233, 233, 233), (a, b)
    # The database's day only beside a docket number that was the other
    # bill's: HB 1330's and SB 524's lines are their own.
    assert a.get("database_effective") == "1993-01-01" and not any(
        "database_effective" in out[t][x] for t, x in (
            ("1991-1992", "HB1330"), ("2015-2016", "SB244"), ("2015-2016", "SB524"))), (
        a, b, out["2015-2016"])
    # A NUMBER ANOTHER BILL HOLDS BY THE DOCKET IS NOT GIVEN TWICE. Made for the
    # guard -- no bill of 1992 is this one: were a third bill chapter 232 on
    # its own docket line, the database's 232 for HB 1278 would settle nothing.
    rows.append(("d", "1992", "2600", "HB1400", "05/13/1992 03:00:00 PM",
                 "SIGNED BY GOVERNOR 05/13/92  EFF: 01/01/93 CHAP.0232"))
    bills["1991-1992"]["HB1400"] = {"lsr_year": "1992", "lsr_num": "2600"}
    try:
        EC.rows = lambda: iter(rows)
        found3, _skipped = EC.read(bills)
    finally:
        EC.rows = saved
        rows.pop()
        del bills["1991-1992"]["HB1400"]
    out3, _held = EC.settle(found3)
    assert out3["1991-1992"]["HB1400"]["chapter"] == 232, out3["1991-1992"]["HB1400"]
    took, left = EC.settle_clashes(out3, found3, {("1991-1992", "HB1278"): 232,
                                                  ("1991-1992", "HB1330"): 233})
    assert out3["1991-1992"]["HB1278"]["chapter"] is None and any(
        "HB1278" in x and "HB1400" in x for x in left), (
        "HB 1278 was given a chapter another bill of the year holds by the docket: "
        f"{took}, {left}")
    assert out3["1991-1992"]["HB1330"]["chapter"] == 233, out3["1991-1992"]["HB1330"]
    assert a["source"] == "the General Court's database" and "withheld" not in a and (
        a["line"].endswith("CHAP.0233")) and "HB1330" in a["settled"], a
    c, d = out["2015-2016"]["SB244"], out["2015-2016"]["SB524"]
    assert (c["chapter"], d["chapter"]) == (127, 127) and "2015" in c["settled"], (c, d)
    assert out["2025-2026"]["SB62"]["chapter"] is None and (
        out["2025-2026"]["HB511"].get("withheld")), (
        "a clash of the current term, which the past table has no row for, was filled")
    # Were the database to give both of 1992's the docket's number, it would
    # tell nothing apart, and nothing would be filled.
    out = withheld()
    settled, unsettled = EC.settle_clashes(
        out, found, {("1991-1992", "HB1278"): 233, ("1991-1992", "HB1330"): 233})
    assert not settled and len(unsettled) == 2 and (
        out["1991-1992"]["HB1278"]["chapter"] is None), (settled, unsettled)

    # The history beside it. Docket_db_1991-1992.txt line 18447.
    root = Path(tempfile.mkdtemp())
    saved = (N.CORRECTIONS, N.MISFILED, N.TERM, N.SETTLED_CHAPTERS)
    try:
        (root / "chapters.json").write_text(json.dumps({
            "1991-1992": {"HB1278": a, "HB1330": b},
            "2015-2016": {"SB244": c}}), encoding="utf-8")
        got = N.load_settled_chapters(root / "chapters.json")
        assert got == {("1991-1992", "HB1278"): (232, 233)}, (
            f"the chapters whose docket number is not the one published: {got}")
        N.CORRECTIONS, N.MISFILED, N.TERM = [], [], "1991-1992"
        line = ["1992|2552|05/13/1992 02:31:47 PM|HB1278|H|SIGNED BY GOVERNOR 05/13/92  "
                "EFF: 01/01/93 CHAP.0233|05/13/1992 02:31:47 PM"]
        N.SETTLED_CHAPTERS = {}
        plain = N.build("HB1278", _docket_rows(line))["narrative"]
        N.SETTLED_CHAPTERS = got
        fixed = N.build("HB1278", _docket_rows(line))["narrative"]
        other = N.build("HB1330", _docket_rows([line[0].replace("HB1278", "HB1330")]))[
            "narrative"]
    finally:
        N.CORRECTIONS, N.MISFILED, N.TERM, N.SETTLED_CHAPTERS = saved
        shutil.rmtree(root, ignore_errors=True)
    assert "Chapter 233" in plain and "Chapter 232" in fixed and "233" not in fixed, (
        plain, fixed)
    assert "Chapter 233" in other, f"HB 1330, which is chapter 233, reads {other!r}"
    assert N.load_settled_chapters("no-such-file.json") == {}

    # The rail. Docket_db_2009-2010.txt line 7481: SB 28's law line, which is
    # SB 109's (line 1915) but for the day of the signature.
    line = "Signed by the Governor on 05/15/09; Effective 07/07/09; Chapter 0028"
    narr28 = {"events": [{"date": "2009-05-19", "type": "governor", "body": "S",
                          "cancelled": False, "raw": line}]}

    def law(narr, bid, chapter, law_line, term, **kw):
        _intro, steps = B.journey(narr, bid, (), chapter, law_line, term, **kw)
        return [s["text"] for s in steps if s["act"] == "law"]
    assert law(narr28, "SB28", 31, line, "2009-2010") == [
        "Chapter 31, in effect Jul 7, 2009"], law(narr28, "SB28", 31, line, "2009-2010")
    assert law(narr28, "SB28", 31, line, "2009-2010", db_effective="2009-07-14") == [
        "Chapter 31, in effect Jul 14, 2009"], (
        "SB 28 of 2009 is not drawn in effect on the database's day: "
        f"{law(narr28, 'SB28', 31, line, '2009-2010', db_effective='2009-07-14')}")
    # The same day from both: nothing changes. And a line that states no day
    # (HB 1417 of 2006's is "Chapter 0263", Docket_db_2005-2006.txt) is given
    # none: the database's is one date where the law may have several. (The
    # event's own day below is made up; only the line is read.)
    assert law(narr28, "SB28", 31, line, "2009-2010", db_effective="2009-07-07") == [
        "Chapter 31, in effect Jul 7, 2009"]
    bare = {"events": [{"date": "2006-06-01", "type": "governor", "body": "H",
                        "cancelled": False, "raw": "Chapter 0263"}]}
    assert law(bare, "HB1417", 262, "Chapter 0263", "2005-2006",
               db_effective="2007-01-01") == ["Chapter 262"], (
        "a law whose docket line states no effective date was given the database's")
    # extract_chapters.database_check hands the clashes to settle_clashes.
    import inspect
    assert "settle_clashes(out, found, clash, effective)" in inspect.getsource(
        EC.database_check), "database_check no longer settles the clashes it finds"
    return "ok", ("HB 1278 of 1992 is chapter 232 and HB 1330 233, by the database and "
                  "each one's own text; SB 244 of 2015 and SB 524 of 2016 are each 127, "
                  "of two years' laws; the history says 232; a number the database "
                  "gives both claimants, one another bill holds, and the current "
                  "term's, stay withheld; SB 28 of 2009 in effect on the database's day")
# Numbered and never before a chamber, or a number with nothing behind it:
# not measures, and not records.
_NOT_MEASURES = [("2005-2006", "SR2"), ("2007-2008", "SR2"), ("2009-2010", "SB27"),
                 ("2023-2024", "HB8002"), ("2023-2024", "HB8012")]


@check("data", "every titled measure the General Court's past table holds, past "
               "Legislative Services, has a record", needs=("build_data",))
def _past_measures_on_record(BD):
    """Measured on the table itself: every row of db/past/PastLegislation.psv
    with a bill number, a title and a general status past 01 is a key of
    data/bills.json under its term. Where a number carries two measures in
    one term the key is the other measure's record -- the keying holds one a
    number -- and that is counted, not hidden. A row with no number is held
    to the same thing through the docket that numbers it: add_past_bills, run
    again over the built records, finds nothing left to add.

    And the 25 by name, each from the source it should be: 23 from the
    database, HR 69 of 1992 from its docket with the House Journal's title,
    HB 459 of 2021 from the House Journal. The numbers that are not measures
    stay out. Nothing of the current term is the database's.
    """
    import contextlib
    import copy
    import io
    bp = Path("data/bills.json")
    if not bp.exists():
        return "skip", "no data/bills.json here; run build_data.py"
    past = BD.past_legislation(".")
    if past is None:
        return "skip", ("no db/past/PastLegislation.psv here (fetch_past_db.py dumps "
                        "it, at a person's word)")
    import proceedings as _PR
    bills = json.loads(bp.read_text(encoding="utf-8"))
    current = max(bills)
    missing, shared, held = [], 0, 0
    for r in past:
        term = _PR.term_of(r.get("SessionYear"))
        bid = BD._bill_number(r.get("CondensedBillNo"))
        if not bid or not r.get("lsrtitle") or term not in bills or term == current \
                or (r.get("GeneralStatusCode") or "") <= BD.PAST_NOT_BEFORE_A_CHAMBER:
            continue
        rec = bills[term].get(bid)
        if rec is None:
            missing.append(f"{bid} of {term} (LSR {r['SessionYear']}-{r['LSR']})")
            continue
        held += 1
        if (str(rec.get("lsr_year") or ""), str(rec.get("lsr_num") or "").lstrip("0")) != (
                r["SessionYear"], r["LSR"].lstrip("0")) and rec.get("lsr_num"):
            shared += 1
    assert not missing, (f"{len(missing)} measure(s) of the General Court's past table "
                         "have no record: " + ", ".join(missing[:8]))
    again = copy.deepcopy(bills)
    general, body = BD.status_words(".")
    with contextlib.redirect_stdout(io.StringIO()):
        more = BD.add_past_bills(again, past, {}, {}, general, body, current)
    assert not more, ("add_past_bills, run over the built records, still adds "
                      + ", ".join(f"{b} {t}" for t, bb in more.items() for b in bb))
    wrong = []
    for (term, bid) in _LEFT_OUT["database"]:
        rec = (bills.get(term) or {}).get(bid) or {}
        if rec.get("source") != BD.PAST_SOURCE or not rec.get("title") or not rec.get("lsr_num"):
            wrong.append(f"{bid} of {term}: {rec.get('source')!r}")
    (t, b), = _LEFT_OUT["docket"]
    hr69 = (bills.get(t) or {}).get(b) or {}
    if hr69.get("title") != BD.TITLED_FROM_JOURNAL[(t, b)]["title"] or (
            (hr69.get("title_source") or {}).get("journal") != "House Journal"):
        wrong.append(f"{b} of {t}: {hr69.get('title')!r}, {hr69.get('title_source')}")
    (t, b), = _LEFT_OUT["journal"]
    hb459 = (bills.get(t) or {}).get(b) or {}
    if not (hb459.get("journal") or {}).get("decided") and Path("journals/2021").is_dir():
        wrong.append(f"{b} of {t}: no House Journal record")
    assert not wrong, "a measure the search page left out is not on the record: " + (
        "; ".join(wrong))
    stray = [f"{b} of {t}" for t, b in _NOT_MEASURES if b in (bills.get(t) or {})]
    assert not stray, f"a number that is not a measure has a record: {stray}"
    ours = [b for b, r in bills[current].items()
            if r.get("source") in (BD.PAST_SOURCE, BD.DOCKET_SOURCE)
            or r.get("number_source") or r.get("title_source")]
    assert not ours, (f"records of {current} say they are the past table's or the "
                      f"docket's alone: {ours[:5]}")
    n = sum(1 for bb in bills.values() for r in bb.values() if r.get("source") == BD.PAST_SOURCE)
    return "ok", (f"{held:,} numbered measures of the past table each have a record "
                  f"({shared} under a number another measure of the term shares); {n} "
                  "records are the database's own, HR 69 of 1992 is titled from the House "
                  "Journal and HB 459 of 2021 is the Journal's")


@check("data", "an archived designation's flags are the database's, and the database's "
               "flags are what the bills print", needs=("build_data", "journal_bills"))
def _past_flags_data(BD, J):
    """Two things, on what was built.

    THE RULE: every archived record that carries flags carries the suffix they
    make and a designation ending in it, and they are the three the past
    table gives its LSR.

    THE AGREEMENT, measured against something neither source produced: the
    designation the House Journal prints for each House measure of the
    current term, in its lists of bills introduced, against the three
    columns of the database's Legislation view -- the columns PastLegislation
    carries under the same names. On 1 October 2026 the appropriation and
    local flags agreed on all 1,650 measures and all three on 1,640: a fiscal
    note can be added after a bill is introduced, and nine were. The bar is
    set under that -- 99 in 100 for each of the two, 95 in 100 for all three
    -- because what it guards against is the columns being read in another
    order, which would agree on about half; and it is not asked of a term so
    new that fewer than 200 measures have been introduced.
    """
    import contextlib
    import io
    bp = Path("data/bills.json")
    if not bp.exists():
        return "skip", "no data/bills.json here; run build_data.py"
    past = BD.past_legislation(".")
    if past is None:
        return "skip", "no db/past/PastLegislation.psv here"
    bills = json.loads(bp.read_text(encoding="utf-8"))
    current = max(bills)
    yes = lambda v: (v or "").strip().lower() in ("1", "true")
    said = {(int(r["SessionYear"]), int(r["LSR"])): (
        yes(r["AppropriationCode"]), yes(r["FiscalImpactCode"]), yes(r["LocalCode"]))
        for r in past if r["SessionYear"].isdigit() and r["LSR"].isdigit()}
    flagged, bad = 0, []
    for term, bb in bills.items():
        if term == current:
            continue
        for bid, r in bb.items():
            fl = r.get("flags")
            if not fl:
                continue
            flagged += 1
            suffix = "".join(x for x, on in (("-FN", fl["fn"]), ("-A", fl["a"]),
                                             ("-LOCAL", fl["local"])) if on)
            key = (int(r["lsr_year"]), int(r["lsr_num"]))
            if suffix != r.get("suffix") or not r.get("designation", "").endswith(suffix) \
                    or not suffix or said.get(key) != (fl["a"], fl["fn"], fl["local"]):
                bad.append(f"{bid} of {term}: {r.get('designation')!r} {fl}")
    assert not bad, f"{len(bad)} archived designations are not the database's, e.g. {bad[:5]}"
    assert flagged, ("the past table is here and no archived designation carries a flag: "
                     "build_data.past_flags did not run")
    out = f"{flagged:,} archived designations carry the database's flags"
    # AND NONE AGAINST THE BILL'S OWN SAVED PAGE, wherever the pages are here.
    # Two by name -- 1999's HB 25 prints -FN-A where the database has -A, and
    # 2022's HB 1419 -A where it has -FN, so each keeps the bare number -- and
    # every twentieth flagged bill, read again off its page.
    if BD.PAGES.is_dir():
        def page_of(bid, r):
            m = re.match(r"^([A-Z]+)(\d+)$", bid)
            f = BD.PAGES / str(r.get("lsr_year")) / f"{m.group(1)}{int(m.group(2)):04d}.html"
            return BD.printed_designations(f, m.group(1), m.group(2)) if f.exists() else set()
        for term, bid, bare in (("1999-2000", "HB25", "HB 25"),
                                ("2021-2022", "HB1419", "HB 1419")):
            r = (bills.get(term) or {}).get(bid) or {}
            if r and page_of(bid, r):
                assert r.get("designation") == bare and not r.get("flags"), (
                    f"{bid} of {term} is designated {r.get('designation')!r} from the "
                    f"database, and its own page prints {sorted(page_of(bid, r))}")
        every = sorted((t, b) for t, bb in bills.items() if t != current
                       for b, r in bb.items() if r.get("flags"))
        against, read = [], 0
        for t, b in every[::20]:
            forms = page_of(b, bills[t][b])
            read += bool(forms)
            if forms and bills[t][b]["suffix"] not in forms:
                against.append(f"{b} of {t}: {bills[t][b]['designation']!r}, page "
                               f"{sorted(forms)}")
        assert not against, (f"{len(against)} flagged designations are not what the "
                             f"bill's own page prints, e.g. {against[:5]}")
        out += (f", none of {read:,} read again against its own saved page, and HB 25 "
                "of 1999 and HB 1419 of 2022 left bare")
    lp, cols = Path("db/Legislation.psv"), Path("db/_columns.json")
    if not (lp.exists() and cols.exists() and J.years()):
        return "ok", out + "; the current term's view or journals are not here to measure with"
    names_ = json.loads(cols.read_text(encoding="utf-8"))["Legislation"]
    at = {k: names_.index(k) for k in ("CondensedBillNo", "AppropriationCode",
                                       "FiscalImpactCode", "LocalCode")}
    view = {}
    with open(lp, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\r\n").split("|")
            if len(f) == len(names_) and f[at["CondensedBillNo"]].strip():
                view[f[at["CondensedBillNo"]].strip().upper()] = (
                    yes(f[at["AppropriationCode"]]), yes(f[at["FiscalImpactCode"]]),
                    yes(f[at["LocalCode"]]))
    with contextlib.redirect_stdout(io.StringIO()):
        intros, _records, _report, problems = J.read_all()
    if problems:
        return "ok", out + "; the journals do not read, so the agreement was not measured"
    n = Counter()
    for (term, bid), e in intros.items():
        got = view.get(bid)
        if got is None or term != current:
            continue
        parts = {x for x in (e.get("suffix") or "").upper().strip("-").split("-") if x}
        printed = ("A" in parts, "FN" in parts, bool(parts & {"L", "LOCAL"}))
        n["compared"] += 1
        n["a"] += got[0] == printed[0]
        n["fn"] += got[1] == printed[1]
        n["local"] += got[2] == printed[2]
        n["all"] += got == printed
    if n["compared"] < 200:
        return "ok", out + (f"; only {n['compared']} measures of {current} are introduced "
                            "and in the view, too few to measure the agreement on")
    assert min(n["a"], n["local"]) >= 0.99 * n["compared"], (
        f"the database's appropriation and local flags are not what the House Journal "
        f"prints: {dict(n)}")
    assert n["all"] >= 0.95 * n["compared"], (
        f"the database's flags agree with the printed designation on {n['all']:,} of "
        f"{n['compared']:,} current House measures, under 95 in 100: {dict(n)}")
    return "ok", out + (f"; on the current term the view's flags are the House Journal's "
                        f"printed designation on {n['all']:,} of {n['compared']:,} "
                        f"measures (fiscal note {n['fn']:,}, appropriation {n['a']:,}, "
                        f"local {n['local']:,})")


@check("data", "the bound House Journal of 1992 prints HR 69's title as the record has it",
       needs=("build_data",))
def _hr69_title_in_journal(BD):
    """HR 69 of 1992 has a docket and no title in any table of the General
    Court's; its record's title is the House Journal's. Read again here from
    the University of New Hampshire's scan of the bound volume wherever that
    is on the machine: the regular calendar of 29 April 1992 prints "HR 69,
    establishing procedures and deadlines for the filing of bills for the
    1993 session. OUGHT TO PASS. Rep. Burns for Rules.", and the numerical
    index prints the same title against the resolution's pages.
    """
    import glob
    import html as _html
    hits = sorted(glob.glob("archive/unh/raw/*journalofhouseof1992newh*djvu.xml*"))
    hits = [h for h in hits if not h.endswith(".meta.json")]
    if not hits:
        return "skip", ("the scan of the 1992 House Journal is not on this machine "
                        "(archive/unh/raw/, Internet Archive item journalofhouseof1992newh)")
    want = BD.TITLED_FROM_JOURNAL[("1991-1992", "HR69")]["title"]
    seen = []
    for h in hits:
        text = Path(h).read_text(encoding="utf-8", errors="replace")
        # The scan's words carry their own trailing space: "<WORD ...>HR </WORD>".
        for m in re.finditer(r"<WORD[^>]*>HR\s*</WORD>", text):
            chunk = text[m.start():m.start() + 6000]
            words = re.sub(r"\s+", " ", " ".join(_html.unescape(w) for w in re.findall(
                r"<WORD[^>]*>(.*?)</WORD>", chunk)))
            if re.match(r"HR 69\b", words):
                seen.append(words[:400])
        if seen:
            break
    assert seen, "the scan is here and HR 69 is not found in its text"
    said = [s for s in seen if re.sub(r"[^a-z0-9]", "", want.lower())
            in re.sub(r"[^a-z0-9]", "", s.lower())]
    assert said, (f"the scan prints HR 69 {len(seen)} time(s) and never with the title "
                  f"on the record: {seen[0][:200]!r}")
    assert any("OUGHT TO PASS" in s for s in said), (
        "the scan prints the title and not the report it was printed with: "
        f"{said[0][:200]!r}")
    return "ok", (f"the scan prints HR 69 with the record's title {len(said)} time(s), "
                  "and with its report, Ought to Pass")


# ---------------------------------------------------------------- resolution sponsors
#
# 173 resolutions had no sponsor (9 November 2026). 95 are the chamber's own business and the
# General Court names none; the rest are memorials and honoring resolutions, and the House
# Journal that prints each says who offered it -- in nearly every case "the House of
# Representatives", which names nobody, and in two ("Offered by: Representatives Gene Chandler,
# Stephen Shurtleff and Speaker Terie Norelli", HR 9 of 2013; "Reps. Flanagan and Shurtleff
# offered the following:", HR 14 of 2015) a person.

_RS_JOURNAL = """\
HOUSE RESOLUTION NO. 9

Honoring the victims and heroes of the Boston Marathon Tragedy
WHEREAS, the House shares the sorrow of the tragedy at this year's Boston Marathon; and
RESOLVED, by the New Hampshire House of Representatives, in Regular Session convened:
That the House does hereby honor all the victims.
Offered by: Representatives Gene Chandler, Stephen Shurtleff and Speaker Terie Norelli

Rep. Shurtleff moved Ought to Pass and requested a roll call; sufficiently seconded.

                         HOUSE RESOLUTION NO. 14

Reps. Flanagan and Shurtleff offered the following:
WHEREAS, the House learned with great sorrow of the tragic shooting in Charleston, South Carolina; and
RESOLVED, that the House stands with the community of Charleston.
Offered and adopted unanimously by the New Hampshire House of Representatives.

                         HOUSE RESOLUTION NO. 6

                  Memorializing State Representative Andre Martel of Manchester
WHEREAS, we have learned with profound sorrow of the death of our friend and colleague; and
RESOLVED, by the House of Representatives, Andre A. Martel be granted the highest praise.
Offered by the House of Representatives and adopted unanimously.

                         RESOLUTION

Reps. Hinch and Shurtleff offered the following: RESOLVED, that the House inform the Senate.
Motion adopted.

                         HOUSE RESOLUTION NO. 7

                  Memorializing State Representative Someone Else of Elsewhere
WHEREAS, we have learned of the death of our colleague; and
RESOLVED, that expressions of sympathy be extended to his family.
Offered and adopted unanimously by the House of Representatives.

Reps. Hinch and Shurtleff offered the following: RESOLVED, that the House adjourn.
Offered by the Speaker
"""


@check("build", "a resolution's sponsor is the person the journal names, and a body names nobody",
       needs=("build_data", "text_sponsors", "build_all"))
def _resolution_sponsors(BD, TS, BA):
    """resolution_sponsors.py reads who offered a resolution off the House Journal. Three
    shapes name a person (a footer "Offered by: Representatives ...", a line "Reps. X and Y
    offered the following:" under the heading); "Offered by the House of Representatives" and
    "Offered and adopted unanimously by the House" name a body and give nothing; a later
    motion of the sitting ("Reps. Hinch and Shurtleff offered the following: RESOLVED, ...")
    and a footer that belongs to another item are not the resolution's. build_data then gives
    the sponsors to a bill that has none, never to a housekeeping resolution, never over a
    sponsor another source named, and never to a bill whose title is not the journal's."""
    import contextlib
    import io
    RS = imp("resolution_sponsors")
    assert RS is not None, ("src/parse/resolution_sponsors.py is not there: 173 resolutions have no "
                            "sponsor, and the House Journal names one for the ones it names")
    plan = BA.plan(type("A", (), {"key": None, "session": "2026", "base": "https://graniterecord.org",
                                  "archive": "nh-archive"})())
    steps = [s.args[0] for s in plan]
    assert "resolution_sponsors.py" in steps, "build_all has no resolution_sponsors.py step"
    assert steps.index("resolution_sponsors.py") < steps.index("build_data.py"), (
        "the resolution sponsors are read after build_data, which takes them")
    assert next(s for s in plan if s.args[0] == "resolution_sponsors.py").kit_required, (
        "the step may be skipped on the nightly's machine, where the sponsors would go with no word")
    root = Path(tempfile.mkdtemp())
    try:
        jd = root / "journals" / "2013"
        jd.mkdir(parents=True)
        (jd / "HJ041.txt").write_text(_RS_JOURNAL, encoding="utf-8")
        got = {(b["number"]): b for b in RS.blocks(jd / "HJ041.txt", "H")}
        assert got[9]["names"] == ["Gene Chandler", "Stephen Shurtleff", "Terie Norelli"], got[9]["names"]
        assert got[14]["names"] == ["Flanagan", "Shurtleff"], got[14]["names"]
        assert got[6]["names"] == [] and got[6]["via"] == "offered by", (
            "'Offered by the House of Representatives' was read as a person: " + repr(got[6]))
        assert got[7]["names"] == [] and "Speaker" not in got[7]["line"], (
            "a footer from another item of the sitting was taken as HR 7's: " + repr(got[7]))
        assert RS.read(root / "journals", root / "absent") == {"2013-2014": {
            "HR9": got_rec(RS, got[9], jd / "HJ041.txt"),
            "HR14": got_rec(RS, got[14], jd / "HJ041.txt")}}, "read() keyed the wrong resolutions"
        out = root / "resolution_sponsors.json"
        with contextlib.redirect_stdout(io.StringIO()):
            assert RS.main.__module__
        out.write_text(json.dumps(RS.read(root / "journals", root / "absent")), encoding="utf-8")
        votes = [{"year": "2013", "body": "H", "member_id": str(i), "name": n, "label": "",
                  "party": p}
                 for i, n, p in ((1, "Chandler, Gene", "R"), (2, "Shurtleff, Steve", "D"),
                                 (3, "Norelli, Terie", "D"), (4, "Flanagan, Jack", "R"))]
        votes += [dict(v, year="2015") for v in votes]
        bills = {"2013-2014": {"HR9": {"title": "Honoring the victims and heroes of the Boston Marathon "
                                                "Tragedy."},
                               "HR14": {"title": "Honoring the victims of Charleston, South Carolina."},
                               "HR6": {"title": "Memorializing State Representative Andre Martel."}},
                 "2015-2016": {"HR14": {"title": "Honoring the victims of Charleston, South Carolina."}}}
        sp = {}
        with contextlib.redirect_stdout(io.StringIO()):
            filled = BD.add_resolution_sponsors(sp, bills, out, TS.Sat(votes), {}, {}, "2025-2026",
                                                "2025-2026")
        assert filled[0] == 2 and set(sp["2013-2014"]) == {"HR9", "HR14"}, (
            "the sponsors of HR 9 and HR 14 were not filled: " + repr(filled))
        # 2013's HR 14 prints no title and opens on Charleston: the bill's own title says so.
        assert [r["name"] for r in sp["2013-2014"]["HR9"]] == [
            "Gene Chandler", "Steve Shurtleff", "Terie Norelli"], sp["2013-2014"]["HR9"]
        assert all(r["prime_inferred"] and r["source"] == "House Journal"
                   for r in sp["2013-2014"]["HR9"])
        # Never over a sponsor another source named, nor onto a housekeeping resolution,
        # nor onto a bill the journal's title does not describe.
        sp2 = {"2013-2014": {"HR9": [{"name": "Someone Else"}]}}
        bills["2013-2014"]["HR14"] = {"title": "Adopting the rules of the 2014 session."}
        with contextlib.redirect_stdout(io.StringIO()):
            BD.add_resolution_sponsors(sp2, bills, out, TS.Sat(votes), {}, {}, "2025-2026", "2025-2026")
        assert sp2["2013-2014"]["HR9"] == [{"name": "Someone Else"}], "overwrote another source's sponsor"
        assert "HR14" not in sp2["2013-2014"], "a housekeeping resolution took a sponsor"
        bills["2013-2014"]["HR14"] = {"title": "Honoring the New Hampshire National Guard."}
        sp3 = {}
        with contextlib.redirect_stdout(io.StringIO()):
            BD.add_resolution_sponsors(sp3, bills, out, TS.Sat(votes), {}, {}, "2025-2026", "2025-2026")
        assert "HR14" not in sp3.get("2013-2014", {}), "a bill the journal does not describe took a sponsor"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # Where the journals are on this disk, the two the House Journal names are found in them.
    if not Path("journals/2013").is_dir() or not Path("journals/2015").is_dir():
        return "ok", "the fixture journals; the real ones are not on this disk"
    res = RS.read(Path("journals"), Path("journals_senate"))
    assert res["2013-2014"]["HR9"]["sponsors"] == ["Gene Chandler", "Stephen Shurtleff", "Terie Norelli"], (
        "HR 9 of 2013 no longer reads from the House Journal")
    assert res["2015-2016"]["HR14"]["sponsors"] == ["Flanagan", "Shurtleff"], (
        "HR 14 of 2015 no longer reads from the House Journal")
    assert not res["2017-2018"].get("HR6"), "a memorial offered by the House took a person"
    return "ok", "fixture journals and the real ones"


def got_rec(RS, b, path):
    """The record read() makes of a block."""
    return {"sponsors": b["names"], "journal": RS.journal_label(path, "H"), "title": b["title"],
            "line": b["line"], "number": b["number"], "opening": b["opening"], "chamber": "H"}
