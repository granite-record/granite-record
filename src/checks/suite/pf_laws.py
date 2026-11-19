#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
preflight's checks of the laws pages.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import json
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (_run, _source, check)
from pf_fixture import (CHAIN_NEEDS, _fixture_site_shared)
from pf_harness import (_app_js, _node_file, _with_components)
from pf_shared import (_cite_plain, _css_palette, _css_px, _css_screen_rules, _css_specificity,
                       _css_won, _html_walk)


@check("build", "a statute page links only what the table holds, tags a section a moving bill would "
       "change, and gives its history from the source note", needs=("build_rsa", "rsa", "shell"))
def _rsa_pages(B, RSA, S):
    """build_rsa.py on a two-section chapter: RSA 91-A:4's own note and a
    citation of a section the table holds and one it does not, with a bill
    of the sitting term still moving that says it changes 91-A:4 and one of
    an old term that did. The person, 11 October 2026: "tagging sections
    that are in progress that propose to amend that RSA section, with
    history of how it's changed through various bills over the years"."""
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA", "titleNumber", "url"]
    t = RSA.Table([dict(zip(cols, r)) for r in (
        ["1", "VI", "91-A", "91-A-4", "TITLE VI PUBLIC OFFICERS AND EMPLOYEES",
         "CHAPTER 91-A ACCESS TO GOVERNMENTAL RECORDS AND MEETINGS",
         "Section 91-A:4 Minutes and Records Available for Public Inspection.",
         "<p><b>Source.</b> 1967, 251:1. 2019, 107:1, eff. Jan. 1, 2020; 163:2, eff. Jan. 1, 2020. </p>",
         "", "<codesect> I. Every citizen ... except as otherwise prohibited by statute or RSA 91-A:5. "
         "See also RSA 91-A:99.</codesect>", "6", "VI\\91-A\\91-A-4.htm"],
        ["2", "VI", "91-A", "91-A-5", "TITLE VI PUBLIC OFFICERS AND EMPLOYEES",
         "CHAPTER 91-A ACCESS TO GOVERNMENTAL RECORDS AND MEETINGS", "Section 91-A:5 Exemptions.",
         "", "", "<codesect> The following governmental records are exempted</codesect>", "6",
         "VI\\91-A\\91-A-5.htm"])])
    data = {"bills": {"2025-2026": {"HB100": {"changes": ["91-A:4"], "cites": ["91-A:4"]}},
                      "2019-2020": {"HB286": {"changes": ["91-A:4"], "cites": ["91-A:4"]}}},
            "enacted": {"91-A:4": [["1967", "251:1", ""], ["2019", "163:2", "2019-2020/HB286"]]},
            "statute": {"91-A:4": ["91-A:5"]}, "asof": {"laws_through": 2025}}
    root = Path(tempfile.mkdtemp(prefix="gr-rsa-"))
    try:
        (root / "idx").mkdir()
        (root / "idx" / "2025-2026.json").write_text(json.dumps([
            {"id": "HB100", "n": "HB 100", "year": 2025, "title": "relative to records", "kind": "active",
             "chip": "In committee", "term": "2025-2026"}]), encoding="utf-8")
        (root / "idx" / "2019-2020.json").write_text(json.dumps([
            {"id": "HB286", "n": "HB 286", "year": 2019, "title": "x", "kind": "law",
             "chip": "Signed into law", "term": "2019-2020"}]), encoding="utf-8")
        bills = B.Bills(root, "2025-2026")
        page = B.chapter_page(S.template(Path("site")), t, data, bills, "91-A", "https://graniterecord.org")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    sec = page[page.index('id="s4"'):page.index('id="s5"')]
    assert "Pending: 1 bill" in sec and 'href="/bill/2025/hb100"' in sec, "the moving bill is not tagged"
    assert 'href="/laws/91-a#s5"' in sec, "a citation the table holds is not linked to its anchor"
    assert "91-A:99" in sec and 'href="/laws/91-a#s99"' not in sec, "a section the table lacks was linked"
    hist = sec[sec.index("How it has changed"):]
    assert hist.index("2019") < hist.index("1967") and 'href="/bill/2019/hb286"' in hist, \
        "the history is not newest first with its bill"
    assert "Access to Governmental Records and Meetings" in page, "the chapter's name is not in title case"
    # The person, 11 October 2026: "Chapter 71: The Tax Commission rather
    # than just 71"; the sections in a sidebar; and a bill in the history is
    # not listed again beside it ("the exact same bill numbers which is
    # redundant").
    assert "<h1>Chapter 91-A: Access to Governmental Records and Meetings</h1>" in page, \
        "the chapter is not titled Chapter 91-A: its name"
    side = page[page.index('class="rs-side"'):page.index('class="rs-art"')]
    assert 'href="/laws/91-a#s4"' in side and 'href="/laws/91-a#s5"' in side, \
        "the sidebar does not list the chapter's sections"
    # NO BARE FRAGMENT. Every page carries <base href="/">, so href="#s4"
    # opened the home page (the person, 11 October 2026: some RSA links "lead
    # to the homepage and didn't pull up the specific chapter").
    assert 'href="#' not in page, "a link on a statute page is a bare #fragment, which <base> sends home"
    assert B.chapter_file(Path("x"), "404") == Path("x/404/index.html") and \
        B.chapter_file(Path("x"), "91-A") == Path("x/91-a.html"), \
        "RSA 404's page is laws/404.html, which the host serves for every missing /laws/ address"
    assert "Other bills that proposed changes" not in sec and "Also proposed" not in sec, \
        "HB 286, in 91-A:4's history, is listed again as another bill that proposed changes"
    return "ok", ("91-A:4 tagged pending by HB 100, linked to 91-A:5 and not to 91-A:99, history 2019 then "
                  "1967 and HB 286 not repeated; titled Chapter 91-A, its sections in the sidebar")


# RSA 659:27-a's challenge affidavit and 659:13's attestation, paragraph for
# paragraph as the General Court's table holds them (the preview's /laws/659,
# 29 October 2026), cut to the lines a form's blanks are in.
_FORM_PASSAGES = (
    ("659:13", "Identification of Voters at the Polls.", (
        "I ____________________ (Printed Name), in accordance with the authority granted to me in RSA 659:13, "
        "I(c) as a moderator, clerk, supervisor, or selectman of the checklist (circle one) do attest under the "
        "penalty of perjury that:",
        "____________________ (Printed Name of Voter) ____________________ (NH Voter Identification Number)",
        "____________________ Signature ____________________ Office")),
    ("659:27-a", "Challenge Affidavit.", (
        "I. No challenge may be asserted except in the form of a signed affidavit, under oath administered by "
        "an election official, in the following form:",
        "Name being used by the voter who you wish to challenge:",
        "_" * 70,
        "Last Name First Name Middle Name",
        "_____ The person seeking to vote has already voted in the election at (name polling place) "
        "__________ at approximately (state time if known) __________",
        "I hereby swear and affirm, under the penalties of perjury, that to the best of my knowledge and "
        "belief the information above is true and correct.",
        "_" * 70,
        "(Signature of challenger)",
        "On the date shown above, before me, _________________________ (print name of notary public, justice "
        "of the peace, election officer), appeared _________________________ (print name of person whose "
        "signature is being notarized), known to me or satisfactorily proven (circle one) to be the person "
        "whose name appears above.")),
)


# RSA 200-J's name, as the preview's /laws/200-j prints it in its heading
# (29 October 2026): one word of 29 letters and slashes.
_LONG_TITLE = ("XV", "TITLE XV EDUCATION", "200-J", "VETERINARY/MEDICAL/OPTOMETRIC EDUCATION PROGRAM",
               "200-J:1", "Definitions.", ("In this chapter:",))


def _wrap_breaks(rules, chain, memo):
    """(how a word may break in chain[0], or None, and what holds its line
    whole, or None), from app.css's cascade and what the element inherits
    (_css_inherited): overflow-wrap or word-wrap anywhere or break-word, or
    word-break break-all; white-space nowrap or pre."""
    props = ("overflow-wrap", "word-wrap", "word-break", "white-space", "text-wrap-mode", "text-wrap")
    got = _css_inherited(rules, chain, props, memo)
    breaks = [(p, got[p]) for p in ("overflow-wrap", "word-wrap") if p in got
              and got[p][0].split()[0] in ("anywhere", "break-word")]
    breaks += [("word-break", got["word-break"])] if got.get("word-break", ("",))[0] == "break-all" else []
    whole = [(p, got[p]) for p in ("white-space", "text-wrap-mode", "text-wrap") if p in got
             and got[p][0].split()[0] in ("nowrap", "pre")]
    return (breaks[0] if breaks else None), (whole[0] if whole else None)


@check("build", "a Laws page's long words wrap on a phone: every run of 20 or more underscores a "
       "statute's form writes, and every word of 20 or more letters in a chapter's title, sits where "
       "app.css lets a word break", needs=("build_rsa", "rsa", "shell"))
def _statute_blanks_wrap(B, RSA, S):
    """The accessibility sweep of the R1 preview (29 October 2026; WCAG
    1.4.10, reflow): /laws/659 was 648px wide in a 390px phone's viewport,
    and scrolled sideways. RSA 659:27-a prints its affidavit's lines to fill
    in as seventy underscores in a row: one word, 636px at reading size
    (measured on the preview, where the phone's column is 366px and twenty
    are 181px), and nothing let the text break inside a word. With that
    mended, every Laws page of the preview was measured at 390 with the
    branch's sheet (1,801 of them, the index and every chapter): one more
    scrolled, /laws/200-j, 425px wide, because its title's
    "Veterinary/medical/optometric" is one word of 29 characters at the
    title's size, which a slash does not break.

    So the two sections' own words, and 200-J's name, go through build_rsa's
    chapter page, and every run of twenty or more underscores it writes, and
    every word of twenty or more characters in its <h1>, must sit in an
    element on which app.css's cascade -- the element's own rules and what it
    inherits (_wrap_breaks) -- lets a word break where it does not fit and
    does not hold the line whole. A rule taken off, a statute's text or a
    title moved into an element no rule reaches, or a later rule that undoes
    it, each fails here. The renderer and the sheet are what is held, so a
    section of any chapter with a longer blank, and a chapter with a longer
    name, is held too; the sweep of every chapter's width on the preview is
    the audit's, not this check's (it needs a browser and the real table)."""
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA", "titleNumber", "url"]
    tno, tname, ch, cname, addr0, head0, paras0 = _LONG_TITLE
    rows = [("LXIII", "TITLE LXIII ELECTIONS", "659", "ELECTION PROCEDURE", addr, heading, paras)
            for addr, heading, paras in _FORM_PASSAGES] + [(tno, tname, ch, cname, addr0, head0, paras0)]
    t = RSA.Table([dict(zip(cols, (
        str(n), tn, chn, addr.replace(":", "-"), title, f"CHAPTER {chn} {name}", f"Section {addr} {heading}", "",
        f"<center><h2>CHAPTER {chn}<br>{name}</h2></center>",
        "<codesect> <br> " + " <br> ".join(paras) + "</codesect>", "63",
        f"{tn}\\{chn}\\{addr.replace(':', '-')}.htm")))
        for n, (tn, title, chn, name, addr, heading, paras) in enumerate(rows)])
    data = {"bills": {}, "enacted": {}, "statute": {}, "asof": {"laws_through": 2025}}
    root = Path(tempfile.mkdtemp(prefix="gr-rsaform-"))
    try:
        (root / "idx").mkdir()
        bills = B.Bills(root, "2025-2026")
        pages = {c: B.chapter_page(S.template(Path("site")), t, data, bills, c, "https://graniterecord.org")
                 for c in ("659", ch)}
    finally:
        shutil.rmtree(root, ignore_errors=True)
    runs = _html_text_chains(pages["659"], r"_{20,}")
    lengths = sorted(len(r) for r, _c in runs)
    assert lengths.count(70) == 2 and len(runs) >= 8, (
        f"the chapter page does not carry the form's blanks as the table has them: runs of {lengths}")
    words = [(w, c) for p in pages.values() for w, c in _html_text_chains(p, r"[^\s]{20,}") if c[0]["tag"] == "h1"]
    assert any("optometric" in w.lower() for w, _c in words), (
        f"RSA 200-J's page does not carry its name's long word in its heading: {[w for w, _c in words]}")
    rules = _css_screen_rules(_source("src/pages/app.css"))
    memo, held, bad = {}, Counter(), []
    for what, run, chain in [("underscores", r, c) for r, c in runs] + [("title", w, c) for w, c in words]:
        brk, whole = _wrap_breaks(rules, chain, memo)
        where = " > ".join(e["tag"] + "".join("." + c for c in sorted(e["classes"])) for e in reversed(chain[:4]))
        name = f"{len(run)} underscores" if what == "underscores" else f"the title's \"{run}\""
        if not brk or whole:
            bad.append(f"{name} in {where}: "
                       + (f"{whole[0]}:{whole[1][0]} ({whole[1][1]}, app.css line {whole[1][2]})"
                          if whole else "no rule lets a word break there"))
        else:
            held[f"{brk[0]}:{brk[1][0]} from {brk[1][1]}"] += 1
    assert not bad, (
        "a long word on a Laws page cannot wrap, and a 390px phone scrolls sideways past it (RSA "
        "659:27-a's seventy underscores are 636px at reading size, 200-J's title 425px wide): "
        + "; ".join(bad[:4]) + ". app.css's .rs-text and .l-head h1 {overflow-wrap:anywhere} are what let them")
    return "ok", (f"{len(runs)} runs of 20 or more underscores ({lengths[-1]} the longest) in 659:13 and "
                  f"659:27-a's forms and {len(words)} long word in 200-J's title, every one able to break: "
                  + ", ".join(f"{k} ({n})" for k, n in held.items()))


# DEFINED TERMS, ON THE STATUTES' OWN WORDS. Each passage is the General
# Court's table as it read on 24 October 2026, paragraph for paragraph (a
# section is cut short where the rest says nothing to the case): RSA 153:1's
# chapter-wide definitions and 153:27's for its subdivision, Mechanical
# Licensing; 153:2, 153:5, 153:10-a and 153:28, which use them; RSA 540-C:1,
# another chapter's "dwelling units"; and RSA 541-A:1's two dated versions of
# "File", with 541-A:14-a's "an agency files".
_DEF_PASSAGES = (
    ("153:1", "Definitions.", (), (
        "When appearing in this chapter:",
        'II. "Building" means any structure, framework or housing, public or private, excluding single family '
        "dwellings as defined in paragraph X and multi-unit dwellings as defined in paragraph VI, but including "
        "tanks, receptacles and containers for the storage of commodities or other materials.",
        'III. "Dwelling unit" means a single unit providing complete and independent living facilities for one '
        "or more persons including permanent provisions for living, sleeping, eating, cooking, and sanitation.",
        'VIII. "Owner" means a person with legal title to or a freehold interest in property, including any '
        "trustee or a board of trustees of property. A lessee or mortgagee of property is not considered an owner.",
        'X. "Single family dwelling" means any structure not defined in paragraph II which contains one dwelling '
        "unit which is designed to be occupied for living purposes, and which is used by one, 2 or more families "
        "exclusively as a home.")),
    ("153:2", "Membership and Organization.", (), (
        "There shall be a state advisory board of fire control consisting of 12 members appointed by the "
        "governor with the advice and consent of the council.",)),
    ("153:5", "State Fire Code;  Rules.", (), (
        "III. The state fire code and associated rules shall not require automatic fire suppression or "
        "sprinkler systems in detached one, or 2-family dwelling units in a structure used only for residential "
        "purposes.",)),
    ("153:10-a", "Automatic Fire Warning Devices and Carbon Monoxide Detection Devices in Dwellings.", (), (
        "II-a. The owner of the rental unit shall be responsible for maintaining the automatic fire warning "
        "device and carbon monoxide detection device in a suitable condition.",)),
    ("153:27", "Definitions.", ("Mechanical Licensing",), (
        "In this subdivision:",
        'I. "Board" means the mechanical licensing board established in RSA 153:27-a.')),
    ("153:28", "Rulemaking.", ("Mechanical Licensing",), (
        "I. Notwithstanding RSA 21-G:9, the board, with an affirmative vote of at least 4 of the appointed board "
        "members, in consultation with the office of professional licensure and certification and with the "
        "approval of the executive director of the office of professional licensure and certification, shall "
        "adopt rules, pursuant to under RSA 541-A, necessary for the proper implementation of the licensure "
        "requirements established in this subdivision, which shall include the following:",)),
    ("540-C:1", "Covered Units.", (), (
        "This chapter shall apply to all dwelling units which are:",
        "I. Rented for recreational or vacation use at least one month out of the year; and",
        "II. Rented for residential purposes by persons who have no other residence, during part or all of the "
        "non-recreational or vacation period.")),
    ("541-A:1", "Definitions.", (), (
        "In this chapter:",
        "[Paragraph VI effective until January 1, 2027; see also paragraph VI set out below.]",
        'VI. "File" means the actual receipt, by the director of legislative services, of a document required '
        "to be submitted during a rulemaking process established by this chapter, under the terms and in the "
        'format prescribed by the director. The term "file" shall also apply to any other response, submission, '
        "or written explanation required during a rulemaking process established by this chapter.",
        "[Paragraph VI effective January 1, 2027; see also paragraph VI set out above.]",
        'VI. "File" means the actual receipt, by the director of the division of administrative rules for the '
        "office of legislative services, of a document required to be submitted during a rulemaking process "
        "established by this chapter, under the terms and in the format prescribed by the director. The term "
        '"file" shall also apply to any other response, submission, or written explanation required during a '
        "rulemaking process established by this chapter.")),
    ("541-A:14-a", "Extension of Currently Effective Rules Pending Readoption.", (), (
        "[Paragraph I effective until January 1, 2027; see also paragraph I set out below.]",
        "I. If an agency files a notice pursuant to RSA 541-A:6 to readopt existing rules, with or without "
        "amendments, the currently effective rules in the filing which would otherwise expire prior to the "
        "completion of the readoption of the rules by the agency shall continue in effect until the proposed "
        "rules are adopted and effective.")),
)


def _def_table(RSA, passages):
    """An rsa.Table of `passages`, each row in the shape db/NH_RSA.psv holds
    it: the chapter's and the subdivision's headings as <h2> in "rsa", the
    text in "EntireRSA"'s <codesect>, a paragraph to a <br>."""
    names = {"153": "STATE BOARD OF FIRE CONTROL", "540-C": "SEASONAL RENTAL UNITS",
             "541-A": "ADMINISTRATIVE PROCEDURE ACT"}
    names = type("N", (dict,), {"__missing__": lambda self, k: "A CHAPTER"})(names)
    rows = []
    for n, (addr, heading, heads, paras) in enumerate(passages):
        ch = addr.split(":")[0]
        rows.append({"id": str(n), "TitleNo": "XII", "ChapterNo": ch, "SectionNo": addr.replace(":", "-"),
                     "Title": "TITLE XII PUBLIC SAFETY AND WELFARE", "Chapter": f"CHAPTER {ch} {names[ch]}",
                     "Section": f"Section {addr} {heading}", "SourceNote": "",
                     "rsa": f"<center><h2>CHAPTER {ch}<br>{names[ch]}</h2></center>"
                            + "".join(f"<center><h2>{h}</h2></center>" for h in heads),
                     "EntireRSA": "<codesect> <br> " + " <br> ".join(paras) + "</codesect>",
                     "titleNumber": "12", "url": f"XII\\{ch}\\{addr.replace(':', '-')}.htm"})
    return RSA.Table(rows)


# THE WORDS OF THE STATUTES, as RSA 126-X:1, 318-B:26, 625:9 and 270:101 print
# them, and a clause of 214:17 (the owner's walk of dry run 9, 8 November
# 2026).
_ELSEWHERE_PASSAGES = (
    ("126-X:1", "Definitions.", (), (
        "In this chapter:",
        'VI. "Designated caregiver" means an individual who:',
        "(a) Is at least 21 years of age;",
        "(b) Has agreed to assist with one or more (not to exceed 5) qualifying patient's therapeutic use of "
        "cannabis, except if the qualifying patient and designated caregiver each live greater than 50 miles "
        "from the nearest alternative treatment center, in which case the designated caregiver may assist with "
        "the therapeutic use of cannabis for up to 9 qualifying patients;",
        "(c) Has never been convicted of a felony or any felony drug-related offense; and",
        "(d) Possesses a valid registry identification card issued pursuant to RSA 126-X:4.",
        'X. "Qualifying patient" means a resident of New Hampshire who has been diagnosed by a provider as '
        "having a qualifying medical condition and who possesses a valid registry identification card issued "
        "pursuant to RSA 126-X:4.")),
    ("318-B:26", "Penalties.", (), (
        "IX-a. A qualifying patient or designated caregiver as defined in RSA 126-X:1 who sells cannabis to a "
        "person who is not a qualifying patient or a designated caregiver shall be guilty of a class B felony "
        "and shall be sentenced to a maximum term of imprisonment of not more than 7 years, a fine of not "
        "more than $300,000, or both.",)),
    ("625:9", "Classification of Crimes.", (), (
        "II. Every offense is either a felony, misdemeanor or violation.",
        "III. A felony is murder or a crime so designated by statute within or outside this code or a crime "
        "defined by statute outside of this code where the maximum penalty provided is imprisonment in excess "
        "of one year; provided, however, that a crime defined by statute outside of this code is a felony when "
        "committed by a corporation or an unincorporated association if the maximum fine therein provided is "
        "more than $200.",
        "(a) Felonies other than murder are either class A felonies or class B felonies when committed by an "
        "individual. Felonies committed by a corporation or an unincorporated association are unclassified.",
        "(1) Class A felonies are crimes so designated by statute within or outside this code and any crime "
        "defined by statute outside of this code for which the maximum penalty, exclusive of fine, is "
        "imprisonment in excess of 7 years.",
        "(2) Class B felonies are crimes so designated by statute within or outside this code and any crime "
        "defined outside of this code for which the maximum penalty, exclusive of fine, is imprisonment in "
        "excess of one year but not in excess of 7 years.",
        "IV. Misdemeanors are either class A misdemeanors or class B misdemeanors when committed by an "
        "individual. Misdemeanors committed by a corporation or an unincorporated association are "
        "unclassified.",
        "(a) A class A misdemeanor is any crime so designated by statute within or outside this code and any "
        "crime defined outside of this code for which the maximum penalty, exclusive of fine, is "
        "imprisonment not in excess of one year.",
        "(b) A class B misdemeanor is any crime so designated by statute within or outside this code and any "
        "crime defined outside of this code for which the maximum penalty does not include any term of "
        "imprisonment or any fine in excess of the maximum provided for a class B misdemeanor in RSA 651:2, "
        "IV(a).",
        "V. A violation is an offense so designated by statute within or outside this code and, except as "
        "provided in this paragraph, any offense defined outside of this code for which there is no other "
        "penalty provided other than a fine or fine and forfeiture or other civil penalty. In the case of a "
        "corporation or an unincorporated association, offenses defined outside of this code are violations "
        "if the amount of any such fine provided does not exceed $50.")),
    ("270:101", "Penalties.", (), (
        "Any person who violates this section shall be guilty of a violation.",)),
    ("214:17", "Penalties.", (), (
        "Failure to comply shall be a violation of the provisions of this chapter.",)),
)


@check("build", "a term a section says is defined in another chapter, and each class of crime RSA 625:9 "
       "defines, has a pop-up wherever it is used, with the statute's own words and its citation",
       needs=("build_rsa", "rsa", "shell"))
def _rsa_defined_elsewhere(B, RSA, S):
    """The owner's walk of dry run 9, 8 November 2026: "designated caregiver"
    in RSA 318-B:26 had no pop-up though RSA 126-X:1, VI defines it, in a
    lead-in and four lettered parts; and "class B felony" had none anywhere.
    A definition was marked only in its own chapter. Now a section that says
    "as defined in RSA 126-X:1" marks the terms it defines, in that sentence,
    and 625:9's classes are marked wherever they are used, the whole phrase
    ("class B felony", not "felony"); "violation" only where a section says
    an act is one. Each pop-up holds the definition's own paragraphs, and its
    citation names the paragraph."""
    t = _def_table(RSA, _ELSEWHERE_PASSAGES)
    d = t.defined()

    def got(addr):
        paras = RSA.paragraphs(t.sections[addr].text)
        e = d.extra_marks(addr, d.marks(addr)[0])
        return {(li, paras[li][st:en].lower(), x.cite) for li, ms in e.items() for st, en, x in ms}

    m = got("318-B:26")
    assert (0, "qualifying patient", "RSA 126-X:1, X") in m and (0, "designated caregiver", "RSA 126-X:1, VI") in m, \
        f"RSA 318-B:26 does not mark the terms it says RSA 126-X:1 defines: {sorted(m)}"
    assert (0, "class b felony", "RSA 625:9, III(a)(2)") in m and not any(w == "felony" for _l, w, _c in m), \
        f"'class B felony' is not marked as a whole phrase with its own paragraph: {sorted(m)}"
    c126 = got("126-X:1")
    assert (4, "felony", "RSA 625:9, III") in c126, f"'felony' in 126-X:1, VI(c) is not marked: {sorted(c126)}"
    p625 = got("625:9")
    for want in ((0, "felony", "RSA 625:9, III"), (0, "misdemeanor", "RSA 625:9, IV"),
                 (2, "class a felonies", "RSA 625:9, III(a)(1)"), (2, "class b felonies", "RSA 625:9, III(a)(2)"),
                 (5, "class a misdemeanors", "RSA 625:9, IV(a)"), (5, "class b misdemeanors", "RSA 625:9, IV(b)")):
        assert want in p625, f"RSA 625:9's own use of its classes lacks {want}: {sorted(p625)}"
    assert not any(c == "RSA 625:9, V" for _l, _w, c in p625), \
        "'violation' is marked in RSA 625:9, II, which names it with no 'a'"
    assert any(w == "violation" and c == "RSA 625:9, V" for _l, w, c in got("270:101")), \
        "'guilty of a violation' (RSA 270:101) is not marked as the class of offense"
    assert not got("214:17"), \
        f"'a violation of the provisions of this chapter' is marked as the class: {sorted(got('214:17'))}"
    root = Path(tempfile.mkdtemp(prefix="gr-rsaaway-"))
    try:
        bills = B.Bills(root, "2025-2026")
        page = B.chapter_page(S.template(Path("site")), t, {}, bills, "318-B", "https://graniterecord.org")
        crimes = B.chapter_page(S.template(Path("site")), t, {}, bills, "625", "https://graniterecord.org")
        home = B.chapter_page(S.template(Path("site")), t, {}, bills, "126-X", "https://graniterecord.org")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert ('<a class="rs-tm" href="/laws/126-x#s1_VI" data-def="away_126_X_1_s1_VI">designated caregiver</a>' in page
            and '<a class="rs-tm" href="/laws/625#s9_III_a_2" data-def="away_625_9_s9_III_a_2">class B felony</a>'
            in page), "318-B's page does not link the terms to their definitions in other chapters"
    held = page[page.index('id="away_126_X_1_s1_VI"'):]
    held = held[:held.index("</div>")]
    assert 'data-cite="RSA 126-X:1, VI"' in held and 'data-href="/laws/126-x#s1_VI"' in held and " hidden>" in held \
        and all(w in held for w in ("<p>VI. &quot;Designated caregiver&quot; means an individual who:</p>",
                                    "<p>(a) Is at least 21 years of age;</p>", "<p>(c) Has never been convicted",
                                    "<p>(d) Possesses a valid registry identification card issued pursuant to "
                                    "RSA 126-X:4.</p>")), \
        f"the held definition of 'designated caregiver' is not the statute's lead-in and its lettered parts: {held[:300]}"
    assert B.DEFS_JS in page, "a page that marks a term has no pop-up script"
    for anchor in ('id="s9_III_a_2"', 'id="s9_IV_b"', 'id="s9_V"'):
        assert anchor in crimes, f"RSA 625's page does not anchor {anchor} for the pages that link to it"
    assert 'id="s1_VI"' in home, "126-X's page does not anchor the definition other chapters link to"
    return "ok", "318-B:26's two terms, the classes of crime, 'violation' only as a class, and the page that holds them"


# The page's script in a page made by hand: a definition, a word that links to
# it, a long definition and a word that links to that, and a paragraph
# elsewhere; node drives it by keyboard, by touch and by mouse, on a clock it
# holds, and presses the box's own link and button.
_DEFS_NODE = r"""
let now = 1000, timers = [];
const tick = ms => { now += ms; timers.forEach(t => { if (t.f && t.at <= now) { const f = t.f; t.f = null; f(); } }); };
const on = {}, ids = {};
function match(x, sel) {
  return sel.split(",").some(s => { s = s.trim(); if (/^\w+$/.test(s)) return x.tagName === s;
    const m = /^(\w+)?\.([\w-]+)$/.exec(s);
    return m && (!m[1] || x.tagName === m[1]) && (" " + (x.className || "") + " ").includes(" " + m[2] + " "); });
}
function node(tag, attrs, parent) {
  const n = {tagName: tag, attrs: Object.assign({}, attrs || {}), children: [], parentNode: null,
    style: {setProperty(k, v) { this[k] = v; }},
    hidden: false, _text: "", className: (attrs || {}).class || "", listeners: {},
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") ids[v] = this; },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { if (c.parentNode) c.parentNode.removeChild(c);
      c.parentNode = this; this.children.push(c); return c; },
    insertBefore(c, ref) { if (c.parentNode) c.parentNode.removeChild(c); c.parentNode = this;
      const i = ref ? this.children.indexOf(ref) : -1;
      if (i < 0) this.children.push(c); else this.children.splice(i, 0, c); return c; },
    removeChild(c) { this.children = this.children.filter(x => x !== c); c.parentNode = null; return c; },
    get nextSibling() { const k = this.parentNode ? this.parentNode.children : []; return k[k.indexOf(this) + 1] || null; },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    contains(x) { while (x) { if (x === this) return true; x = x.parentNode; } return false; },
    closest(sel) { let x = this; while (x) { if (match(x, sel)) return x; x = x.parentNode; } return null; },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    querySelectorAll(sel) { const out = []; const walk = y => y.children.forEach(c => { if (match(c, sel)) out.push(c); walk(c); });
      walk(this); return out; },
    getBoundingClientRect() { return this.rect || {left: 0, right: 0, top: 0, bottom: 0}; },
    focus() { const was = doc.activeElement; doc.activeElement = this; if (was !== this) fire("focusin", {target: this}); }};
  Object.defineProperty(n, "textContent", {get() { return n._text + n.children.map(c => c.textContent).join(""); },
    set(v) { n._text = String(v); n.children.forEach(c => { c.parentNode = null; }); n.children = []; }});
  Object.defineProperty(n, "id", {get() { return n.attrs.id; }, set(v) { n.setAttribute("id", v); }});
  if (n.attrs.id) ids[n.attrs.id] = n;
  if (parent) parent.appendChild(n);
  return n;
}
const doc = {activeElement: null, documentElement: {clientWidth: 1200}, getElementById: k => ids[k] || null,
  createElement: t => node(t), addEventListener(t, f) { (on[t] = on[t] || []).push(f); }};
function fire(t, ev) { let no = false; (on[t] || []).forEach(f => f(Object.assign({preventDefault() { no = true; }}, ev))); return no; }
// A press: the element's own listeners, then the document's, as a click bubbles.
function press(x) { (x.listeners.click || []).forEach(f => f({target: x})); return fire("click", {target: x}); }
const art = node("div", {class: "rs-art"}); art.rect = {left: 100, right: 800, top: 0, bottom: 5000};
const dfn = node("div", {class: "rs-dfn", id: "s1_III", "data-cite": "RSA 153:1, III", "data-for": "this chapter"}, art);
node("p", {}, dfn)._text = DEFINITION;
const long = node("div", {class: "rs-dfn", id: "s1_IX", "data-cite": "RSA 153:1, IX", "data-for": "this chapter"}, art);
LONG.forEach(t => { node("p", {}, long)._text = t; });
const para = node("p", {}, art);
const word = node("a", {class: "rs-tm", href: "/laws/153#s1_III"}, para); word._text = "dwelling units";
word.rect = {left: 300, right: 400, top: 200, bottom: 220};
const para2 = node("p", {}, art);
const word2 = node("a", {class: "rs-tm", href: "/laws/153#s1_IX"}, para2); word2._text = "residential";
const elsewhere = node("p", {}, art);
doc.activeElement = elsewhere;
global.document = doc; global.window = {innerHeight: 900};
global.setTimeout = (f, ms) => timers.push({at: now + ms, f});
global.clearTimeout = i => { if (i && timers[i - 1]) timers[i - 1].f = null; };
global.Date = {now: () => now};
new Function(SCRIPT)();
const box = () => ids["rs-dpop"], out = {};
const link = () => box().querySelector("a"), more = () => box().querySelector("button");
fire("keydown", {key: "Tab"}); word.focus();
out.focus = !!box() && !box().hidden; out.says = box() && box().textContent;
out.described = word.getAttribute("aria-describedby"); out.role = box() && box().getAttribute("role");
out.link = link() && [link().href, link().textContent]; out.short_has_more = !!more();
out.in_text = box().parentNode === para && para.children.indexOf(box()) === para.children.indexOf(word) + 1;
// Tab from the word into the box's link: it stays open, and Escape there
// closes it and gives the word the keyboard without opening it again.
const into = link() || more() || elsewhere;
fire("focusout", {target: word, relatedTarget: into}); doc.activeElement = into;
fire("focusin", {target: into}); tick(300); out.tab_in_stays = into !== elsewhere && !box().hidden;
fire("keydown", {key: "Escape"});
out.escape = box().hidden && doc.activeElement === word && !word.getAttribute("aria-describedby");
// Its link goes to the definition, and the box closes behind it.
doc.activeElement = elsewhere; word.focus();
out.link_follows = !!link() && !press(link()) && box().hidden;
// A long one: cut, with Show more, which opens all of it, a paragraph a line.
doc.activeElement = elsewhere; word2.focus();
out.cut = box().querySelector(".rs-dptext").textContent;
out.more = !!more() && more().textContent === "Show more" && more().getAttribute("aria-expanded") === "false";
if (more()) press(more());
out.whole = box().querySelector(".rs-dptext").children.map(c => c.textContent);
out.more_open = !!more() && !box().hidden && more().textContent === "Show less" && more().getAttribute("aria-expanded") === "true";
if (more()) press(more());
out.less = !!more() && box().querySelector(".rs-dptext").textContent === out.cut && more().textContent === "Show more";
fire("keydown", {key: "Escape"});
doc.activeElement = elsewhere;
fire("pointerdown", {pointerType: "touch", target: word});
out.tap_stays = fire("click", {target: word}); out.tap_opens = !box().hidden;
out.tap_link = !!link();
// The owner's walk of dry run 8, 8 November 2026: a press on the word keeps
// the box open, wherever the pointer goes, and never navigates; the word
// again, Escape or a press elsewhere closes it; Space is a press.
fire("pointerout", {pointerType: "mouse", target: word, relatedTarget: elsewhere}); tick(1500);
out.pinned_stays = !box().hidden;
(box().listeners.pointerleave || []).forEach(f => f({pointerType: "mouse"})); tick(1500);
out.pinned_stays = out.pinned_stays && !box().hidden;
fire("pointerdown", {pointerType: "touch", target: word});
out.second_tap_closes = fire("click", {target: word}) && box().hidden;
fire("click", {target: word}); out.reopens = !box().hidden;
fire("keydown", {key: "Escape"}); out.pinned_escape = box().hidden;
fire("keydown", {key: " ", target: word}); out.space_opens = !box().hidden;
out.space_pins = (tick(1500), !box().hidden);
fire("keydown", {key: " ", target: word}); out.space_closes = box().hidden;
fire("click", {target: word}); fire("pointerdown", {pointerType: "touch", target: elsewhere});
out.press_in_box_stays = (fire("click", {target: box().querySelector(".rs-dptext")}), !box().hidden);
fire("click", {target: elsewhere});
out.press_elsewhere = box().hidden;
fire("pointerover", {pointerType: "mouse", target: word}); tick(200); out.hover_waits = box().hidden;
tick(400); out.hover_opens = !box().hidden;
fire("pointerout", {pointerType: "mouse", target: word, relatedTarget: box()}); tick(300);
out.onto_box_stays = !box().hidden;
fire("pointerout", {pointerType: "mouse", target: word, relatedTarget: elsewhere}); tick(300);
out.leave_closes = box().hidden;
// Escape with the keyboard elsewhere: the box closes, the keyboard stays.
fire("pointerover", {pointerType: "mouse", target: word}); tick(600);
fire("keydown", {key: "Escape"}); out.escape_elsewhere = box().hidden && doc.activeElement === elsewhere;
// A press inside the box that sends the keyboard nowhere keeps it open.
word2.focus(); fire("pointerdown", {pointerType: "mouse", target: box().querySelector(".rs-dptext")});
fire("focusout", {target: word2, relatedTarget: null}); tick(300); out.press_inside_stays = !box().hidden;
fire("keydown", {key: "Escape"}); doc.activeElement = elsewhere;
// THE SIDE IS KEPT. Low on a screen 900 high, a short box opens under the
// word; Show more, now 500 high, keeps it there, no taller than the room.
word2.rect = {left: 300, right: 400, top: 600, bottom: 620}; box().rect = null;
word2.focus(); out.short_below = box().style.top;
box().rect = {left: 300, right: 700, top: 0, bottom: 500}; if (more()) press(more());
out.more_below = [box().style.top, box().style.maxHeight];
fire("keydown", {key: "Escape"}); doc.activeElement = elsewhere;
// Near the bottom, a box 500 high opens over the word, and Show less keeps it there.
word2.rect = {left: 300, right: 400, top: 800, bottom: 820};
word2.focus(); out.opens_above = [box().style.top, box().style.maxHeight];
if (more()) press(more()); out.more_above = box().style.top;
// A definition another chapter holds, hidden, under data-def (the owner's walk
// of dry run 9, 8 November 2026); the word's href is deliberately an id this
// page has, and its box's citation goes to the other chapter.
fire("keydown", {key: "Escape"}); doc.activeElement = elsewhere;
const away = node("div", {class: "rs-dfn rs-away", id: "away_126", "data-cite": "RSA 126-X:1, VI",
  "data-for": "chapter 126-X", "data-href": "/laws/126-x#s1_VI"}, art); away.hidden = true;
node("p", {}, away)._text = 'VI. "Designated caregiver" means an individual who:';
node("p", {}, away)._text = "(a) Is at least 21 years of age;";
const para3 = node("p", {}, art);
const word3 = node("a", {class: "rs-tm", href: "/laws/126-x#s1_III", "data-def": "away_126"}, para3);
word3._text = "designated caregiver"; word3.rect = {left: 300, right: 400, top: 200, bottom: 220};
word3.focus(); out.away = [box().textContent, link().href];
// THE POINTER (the owner, 10 November 2026): the box under its word points up
// at the word's middle from the box's left; over it, class "above"; and a
// box moved to stay on the screen points at the word still.
fire("keydown", {key: "Escape"}); doc.activeElement = elsewhere;
word3.focus(); out.point_below = [box().className, box().style["--arrow"]];
fire("keydown", {key: "Escape"}); doc.activeElement = elsewhere;
word3.rect = {left: 300, right: 400, top: 800, bottom: 820}; box().rect = {left: 300, right: 700, top: 0, bottom: 500};
word3.focus(); out.point_above = [box().className, box().style["--arrow"]];
fire("keydown", {key: "Escape"}); doc.activeElement = elsewhere;
word3.rect = {left: 1000, right: 1100, top: 200, bottom: 220};
word3.focus(); out.point_shifted = [box().style.left, box().style["--arrow"]];
// THE /laws PREVIEW (the owner, 11 November 2026: a click on a defined word
// there "takes you to the full page link"): the pane is .lw-read, not .rs-art,
// holding a section and, hidden, the definitions its words point at, copied
// from the chapter's page. A press opens the box in place, does not navigate,
// and the box's link and Show more work.
fire("keydown", {key: "Escape"}); doc.activeElement = elsewhere;
const pane = node("aside", {class: "lw-read"}); pane.rect = {left: 600, right: 1100, top: 0, bottom: 3000};
const held = node("div", {}, pane); held.hidden = true;
const pdef = node("div", {class: "rs-dfn", id: "s1_IX", "data-cite": "RSA 153:1, IX", "data-for": "this chapter",
  "data-href": "/laws/153#s1_IX"}, held); pdef.hidden = true;
LONG.forEach(t => { node("p", {}, pdef)._text = t; });
const ppara = node("p", {}, pane);
const pword = node("a", {class: "rs-tm", href: "/laws/153#s1_IX"}, ppara); pword._text = "residential";
pword.rect = {left: 700, right: 800, top: 200, bottom: 220};
fire("pointerdown", {pointerType: "mouse", target: pword});
out.pane_no_nav = fire("click", {target: pword});
out.pane_opens = !!box() && !box().hidden && box().parentNode === ppara;
out.pane_link = !!link() && link().href === "/laws/153#s1_IX" && link().textContent === "RSA 153:1, IX";
out.pane_more = !!more() && (press(more()), box().querySelector(".rs-dptext").children.length === 3);
fire("click", {target: ppara}); out.pane_closes = box().hidden;
console.log(JSON.stringify(out));
"""


@check("build", "a defined word is not marked where the text already spells out its definition ('department of "
       "transportation' under '\"Department\" means the department of transportation'), and is marked "
       "everywhere else", needs=("build_rsa", "rsa", "shell"))
def _rsa_spelled_out_terms(B, RSA, S):
    """The owner, 11 November 2026: RSA 228:1, VII's "department of
    transportation" opened a box saying "Department" means the department of
    transportation. Skipped only where the definition is '"X" means Y' (Y
    all it says) and the words at the use are Y; a bare "department", or one
    followed by other words, is marked, and a definition with more than Y in
    it ("... and ...") is never read as Y."""
    t = _def_table(RSA, (
        ("153:1", "Definitions.", (), (
            "In this chapter:",
            'IV. "Department" means the department of transportation.',
            'VI. "Board" means the board of fire control and the commissioner.')),
        ("153:7", "Works.", (), (
            "Works administered through the department of transportation, division of public works, "
            "are reported by the board of fire control.",
            "The department of administrative services keeps a copy.",
            "A bare department files a form with the board.")),
    ))
    got, _w = t.defined().marks("153:7")
    p = RSA.paragraphs(t.sections["153:7"].text)
    words = [(li, p[li][st:en]) for li, v in sorted(got.items()) for st, en, _i in v]
    assert (0, "department") not in words,         f"'department of transportation' is marked where the text spells out its definition: {words}"
    assert (1, "department") not in words, \
        f"'department of administrative services' is marked with the department of transportation's definition: {words}"
    assert (2, "department") in words, "the bare 'department' after them is not marked in its place"
    assert (0, "board") in words, "'board' ('and the commissioner' follows the meaning) is not marked"
    return "ok", ("the spelled-out use and another department skipped, the bare one marked in its place, "
                  "a longer meaning not read as a short one")


@check("build", "a statute page marks a defined term where the definition's own words apply it, and only "
       "there: not outside its subdivision or chapter, not where two definitions could apply, not in its "
       "own definition", needs=("build_rsa", "rsa", "shell"))
def _rsa_defined_terms(B, RSA, S):
    """The person, 24 October 2026: "Could you make it so that definitions in
    the rsa pages show up as tooltips in sections that cite them like
    'dwelling unit' being defined in 153:1 and later referenced so that you
    know which definition it's referring to?"

    A definition applies where its own words say (rsa.Defined), and accuracy
    was asked for ahead of coverage, so this holds the reader to five things
    on real passages: "dwelling units" in RSA 153:5 is marked with 153:1's
    definition, which says it applies "in this chapter"; "board" in 153:28 is
    marked with 153:27's, which applies "in this subdivision", and in 153:2,
    outside the subdivision, is not marked at all; "dwelling units" in RSA
    540-C:1, another chapter, is not marked; "files" in 541-A:14-a, which two
    dated versions of 541-A:1, VI define, is not marked -- while with one
    version it is, so it is the second definition that withholds it; and a
    term is not marked inside its own definition. Then the page: the word a
    quiet link to the definition's own paragraphs, which carry its citation
    and scope once; and its script, by keyboard, by touch and by mouse.

    And the person, 7 November 2026: "you need to be able to click to where
    that definition is as a link ... Maybe a show more option as well". The
    box's citation is a link to the definition (the word's own address), it
    closes behind it; a definition over 400 characters is cut, with Show
    more opening all of it, a paragraph a line, and Show less after; the box
    sits straight after the word, so Tab goes into it and it stays, Escape
    there gives the word the keyboard without opening it again, and the
    pointer can cross onto it."""
    t = _def_table(RSA, _DEF_PASSAGES)
    d = t.defined()

    def got(addr):
        marks, held = d.marks(addr)
        paras = RSA.paragraphs(t.sections[addr].text)
        return ({(li, paras[li][st:en].lower(), d.defs[i].cite, d.defs[i].scope)
                 for li, ms in marks.items() for st, en, i in ms}, held)

    m5, _ = got("153:5")
    assert (0, "dwelling units", "RSA 153:1, III", "chapter") in m5, \
        f"153:1's chapter-wide 'dwelling unit' is not marked in 153:5: {sorted(m5)}"
    m28, _ = got("153:28")
    assert (0, "board", "RSA 153:27, I", "subdivision") in m28, \
        f"153:27's 'board' is not marked inside its own subdivision, in 153:28: {sorted(m28)}"
    m2, _ = got("153:2")
    assert not m2, f"153:27's 'board', defined for its subdivision only, is marked in 153:2: {sorted(m2)}"
    m540, _ = got("540-C:1")
    assert not m540, f"a definition in RSA 153 is marked in another chapter, RSA 540-C: {sorted(m540)}"
    m14, held = got("541-A:14-a")
    assert not m14 and held == {"files"}, \
        f"'files', which two versions of 541-A:1, VI define, is marked or not counted: {sorted(m14)}, {held}"
    one = _def_table(RSA, [p if p[0] != "541-A:1" else p[:3] + (p[3][:3],) for p in _DEF_PASSAGES])
    alone = one.defined().marks("541-A:14-a")[0]
    assert alone, "with one definition of 'File' its use in 541-A:14-a is not marked, so the ambiguity check proves nothing"
    # NOT IN ITS OWN DEFINITION: "A lessee or mortgagee of property is not
    # considered an owner" is 153:1, VIII's own sentence, while 153:10-a's
    # "The owner of the rental unit" is a use of it.
    m1, _ = got("153:1")
    at = {p.split(".")[0]: li for li, p in enumerate(RSA.paragraphs(t.sections["153:1"].text))}
    assert not any(li in (at["III"], at["VIII"]) for li, *_ in m1), \
        f"a term is marked inside its own definition, 153:1, III or VIII: {sorted(m1)}"
    assert (0, "owner", "RSA 153:1, VIII", "chapter") in got("153:10-a")[0], \
        "153:1, VIII's 'owner' is not marked where 153:10-a uses it"
    assert (at["X"], "dwelling unit", "RSA 153:1, III", "chapter") in m1 and \
        not any(w == "single family dwelling" for li, w, *_ in m1 if li == at["X"]), \
        f"paragraph X marks its own term, or not paragraph III's: {sorted(m1)}"
    assert (at["II"], "single family dwellings", "RSA 153:1, X", "chapter") in m1, \
        f"153:1, II's 'single family dwellings' is not marked with paragraph X: {sorted(m1)}"
    # The page: a quiet link to the definition, whose paragraphs say once
    # where and for what; the script only where something is marked.
    root = Path(tempfile.mkdtemp(prefix="gr-rsadef-"))
    try:
        bills = B.Bills(root, "2025-2026")
        page = B.chapter_page(S.template(Path("site")), t, {}, bills, "153", "https://graniterecord.org")
        other = B.chapter_page(S.template(Path("site")), t, {}, bills, "540-C", "https://graniterecord.org")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    s5 = page[page.index('id="s5"'):]
    assert '<a class="rs-tm" href="/laws/153#s1_III">dwelling units</a>' in s5, \
        "153:5's 'dwelling units' is not a link to 153:1, III on the page"
    assert '<div class="rs-dfn" id="s1_III" data-cite="RSA 153:1, III" data-for="this chapter">' in page, \
        "153:1, III does not carry its id, citation and scope for the words that point at it"
    assert page.count('class="rs-dfn"') == 4 and "</div>" in page[page.index('id="s1_III"'):page.index('id="s2"')], \
        "the definitions the page points at are not each held once"
    assert 'href="#' not in page and B.DEFS_JS in page and B.DEFS_JS not in other and "rs-tm" not in other, \
        "the script is missing where a term is marked, or a page with none carries it or a mark"
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "ok", "five cases on real passages and the page; node is not here for the script"
    script = B.DEFS_JS[len("<script>"):-len("</script>")]
    definition = RSA.paragraphs(t.sections["153:1"].text)[at["III"]]
    # A long definition, three paragraphs, the first opening with its numbers.
    long = ["IX. \"Residential\" means " + "a use of property as a home or as rooms let for living in, " * 9 + "and nothing else.",
            "(a) It includes a house, an apartment, a manufactured housing unit and a room let by the week.",
            "(b) It does not include a hotel room let by the night."]
    prog = (f"const SCRIPT = {json.dumps(script)};\nconst DEFINITION = {json.dumps(definition)};\n"
            f"const LONG = {json.dumps(long)};\n" + _DEFS_NODE)
    r = _node_file(node, prog, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, "the page's definitions script stopped: " + (r.stderr or "").strip()[-300:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["says"] == ('Defined for this chapter in RSA 153:1, III"Dwelling unit" means a single unit '
                           "providing complete and independent living facilities for one or more persons "
                           "including permanent provisions for living, sleeping, eating, cooking, and sanitation."), \
        f"the box does not give the definition and where it is from: {out['says']!r}"
    # WHERE IT IS, AND ALL OF IT (the person, 7 November 2026): the citation a
    # link to the definition, the word's own address; a long one cut, with
    # Show more opening all of it, a paragraph a line, and Show less after.
    assert out["link"] == ["/laws/153#s1_III", "RSA 153:1, III"] and not out["short_has_more"], \
        f"the box's citation is not a link to the definition, or a short one offers Show more: {out}"
    first = long[0].split(". ", 1)[1]
    whole = [first] + long[1:]
    assert out["cut"].endswith("…") and len(out["cut"]) <= 401 and first.startswith(out["cut"][:-1]) \
        and out["more"] and out["whole"] == whole and out["more_open"] and out["less"], (
        f"a long definition is not cut with Show more, or Show more does not open all of it, a "
        f"paragraph a line, and close it again: {out}")
    assert out["away"] == ['Defined for chapter 126-X in RSA 126-X:1, VI"Designated caregiver" means an individual '
                           "who: (a) Is at least 21 years of age;", "/laws/126-x#s1_VI"], \
        f"a definition held for another chapter's page does not open from data-def, or does not link there: {out['away']}"
    assert out.get("pane_no_nav") and out.get("pane_opens") and out.get("pane_link") and out.get("pane_more")         and out.get("pane_closes"), (
        f"a click on a defined word in the Laws page's preview does not open its box in place, or navigates: {out}")
    reader = B.LANDING_JS[B.LANDING_JS.find("read.innerHTML='<p class=\"lw-rcrumb\">"):]
    assert 'querySelectorAll("a.rs-tm")' in reader and "importNode" in reader and "doc.getElementById(id)" in reader,         "the Laws page's reader does not bring in the definitions its section's defined words point at"
    assert "</div>{DEFS_JS}{LANDING_JS}" in _source("src/pages/build_rsa.py"),         "the Laws page does not carry the definitions script beside its own"
    wrong = [k for k in ("focus", "in_text", "tab_in_stays", "escape", "link_follows", "tap_stays",
                         "tap_opens", "tap_link", "pinned_stays", "second_tap_closes", "reopens",
                         "pinned_escape", "space_opens", "space_pins", "space_closes",
                         "press_in_box_stays", "press_elsewhere", "hover_waits",
                         "hover_opens", "onto_box_stays", "leave_closes", "escape_elsewhere",
                         "press_inside_stays") if not out[k]]
    # The word at 600-620 of a screen 900 high: under it, 626, and Show more's
    # 500 kept there in the 266 left; at 800-820, 500 high goes over it, 294,
    # and stays there when Show less is pressed (the box's height in node is
    # the one set, so its top does not move).
    place = {"short_below": out.get("short_below"), "more_below": out.get("more_below"),
             "opens_above": out.get("opens_above"), "more_above": out.get("more_above")}
    assert place == {"short_below": "626px", "more_below": ["626px", "266px"],
                     "opens_above": ["294px", ""], "more_above": "294px"}, \
        f"the box does not open where there is room, or jumps sides when Show more is pressed: {place}"
    assert not wrong and out["described"] == "rs-dpcite rs-dptext" and out["role"] is None, \
        f"the definition box fails by keyboard, touch or mouse: {wrong}, {out}"
    # The pointer: word 300-400 under a box at 300 points at 50; over it, the
    # box is marked above; the word at 1000-1100 shifts the box to 792 (692
    # from its host) and the pointer to 258, the word's middle still.
    assert out["point_below"] == ["termpop rs-dpop", "50px"] \
        and out["point_above"] == ["termpop rs-dpop above", "50px"] \
        and out["point_shifted"] == ["692px", "258px"], (
        f"the definition box's pointer is not at its word: "
        f"{[out.get(k) for k in ('point_below', 'point_above', 'point_shifted')]}")
    css = _source("src/pages/app.css")
    for rule in (".termpop:not(.seatpop)::before", ".termpop.above:not(.seatpop)::after",
                 ".rs-dpin{display:block;min-height:0;overflow-y:auto}"):
        assert rule in css, f"app.css lacks {rule}: the definition boxes would have no pointer, or cut it off"
    assert '"--arrow"' in _source("src/pages/components.js"), \
        "components.js's term popovers do not set their pointer's place"
    return "ok", ("153:5 marked from 153:1 and 153:28 from 153:27, not 153:2 or 540-C:1; 541-A:14-a's 'files' "
                  "withheld for two definitions; no term in its own; the box by keyboard, tap and mouse, "
                  "its link to the definition and Show more for a long one")


# The chapter page's script on lists made by hand: a fold holding a list of
# ten, and a list of eight; node presses "Show all" and closes the fold.
_FOLD_NODE = r"""
const on = {}, uls = [];
function node(tag, parent) {
  const n = {tagName: tag, children: [], parentNode: null, hidden: false, attrs: {}, listeners: {}, open: true,
    _text: "", className: "",
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    setAttribute(k, v) { this.attrs[k] = String(v); },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    insertBefore(c, ref) { c.parentNode = this; const i = ref ? this.children.indexOf(ref) : -1;
      if (i < 0) this.children.push(c); else this.children.splice(i, 0, c); return c; },
    get nextSibling() { const k = this.parentNode ? this.parentNode.children : []; return k[k.indexOf(this) + 1] || null; },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    closest(sel) { let x = this; while (x) { if (x.tagName === sel) return x; x = x.parentNode; } return null; },
    querySelector(sel) { return this.children.find(c => c.tagName === sel) || null; },
    focus() { doc.activeElement = this; }};
  Object.defineProperty(n, "textContent", {get() { return n._text; }, set(v) { n._text = String(v); }});
  if (parent) parent.appendChild(n);
  return n;
}
const doc = {activeElement: null, createElement: t => node(t),
  querySelectorAll: sel => sel === "ul[data-fold]" ? uls.filter(u => u.getAttribute("data-fold")) : [],
  querySelector: () => null, addEventListener() {}};
global.document = doc; global.window = {};
function list(parent, n, fold) { const u = node("ul", parent); if (fold) u.setAttribute("data-fold", fold);
  for (let i = 0; i < n; i++) { const li = node("li", u); node("a", li)._text = "RSA " + i; } uls.push(u); return u; }
const d = node("details"); const part = node("div", d);
const ten = list(part, 10, "8"), eight = list(node("div"), 8, "8"); node("p", part);
new Function(SCRIPT)();
const btn = ten.nextSibling, out = {};
const shown = u => u.children.filter(li => !li.hidden).length;
const press = () => (btn.listeners.click || []).forEach(f => f({target: btn}));
out.after_list = !!btn && btn.tagName === "button" && btn.parentNode === part && part.children.indexOf(btn) === 1;
out.folded = [shown(ten), btn.textContent, btn.getAttribute("aria-expanded")];
press(); out.opened = [shown(ten), btn.textContent, btn.getAttribute("aria-expanded"),
                       doc.activeElement === ten.children[8].children[0]];
press(); out.closed = [shown(ten), btn.textContent];
press(); d.open = false; (d.listeners.toggle || []).forEach(f => f({})); out.with_fold = [shown(ten), btn.textContent];
out.eight = [shown(eight), eight.nextSibling === null];
const late = list(node("div"), 9, "8"), only = {querySelectorAll: () => [late]};
window.rsFold(only); window.rsFold(only);
out.later = [shown(late), late.parentNode.children.filter(c => c.tagName === "button").length];
console.log(JSON.stringify(out));
"""


@check("build", "a statute section's history and citations are one fold, its counts in its line, and "
       "\"Show all\" opens the rest of its own list where it is and closes with the fold",
       needs=("build_rsa", "rsa", "shell"))
def _rsa_section_fold(B, RSA, S):
    """The person, 7 November 2026: "I'd like a more compact navigation of the
    how it has changed, other bills that proposed changes, cites, and cited
    by sections all compacted into one dropdown before you expand it", and
    "The show all 12 for the cited by is also formatted strangely since it
    doesn't move with the dropdown it just expands another section under."

    On the definitions check's own chapter, given a history of ten laws, a
    citation and eleven sections citing it: the section has one fold, "History
    and citations" with nothing else in its line, holding each list under a heading one level below the section's, the
    history drawn whole with data-fold, and no Show all of the old kind
    (rs-more) anywhere on the page; fold_counts says one in the singular
    and leaves out what is not there. Then the chapter's script in node: the
    button straight after its list, "Show all 10" showing eight, pressed
    showing all ten and taking the keyboard to the first it showed, "Show
    fewer" folding it again, closing the fold folding it too; and a list of
    eight given no button."""
    t = _def_table(RSA, _DEF_PASSAGES)
    data = {"enacted": {"153:5": [[str(1990 + i), f"{10 + i}:1", ""] for i in range(10)]},
            "statute": dict({"153:5": ["153:1"], "153:2": ["153:5"], "153:10-a": ["153:5"]},
                         **{f"99:{i}": ["153:5"] for i in range(1, 10)})}
    root = Path(tempfile.mkdtemp(prefix="gr-rsafold-"))
    try:
        page = B.chapter_page(S.template(Path("site")), t, data, B.Bills(root, "2025-2026"), "153",
                              "https://graniterecord.org")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    s5 = page[page.index('id="s5"'):]
    s5 = s5[:s5.index("</section>")]
    lv = int(re.search(r'<h(\d) class="rs-h">', s5).group(1))
    bad = []
    folds = s5.count('<details class="rs-fold">')
    if folds != 1:
        bad.append(f"153:5 has {folds} folds, not one")
    # The owner's walk of dry run 8, 8 November 2026: the fold's line is its
    # name alone; each list's count is on its heading, Cites first.
    if '<summary><span class="rs-fname">History and citations</span></summary>' not in s5:
        bad.append("the fold's line is not \"History and citations\" alone")
    heads = re.findall(r'<div class="rs-fpart"><h(\d) class="rs-fh">([^<]+) <span class="rs-fcount">'
                       r'&middot; (\d+)</span></h\d>', s5)
    if heads != [(str(lv + 1), "Cites", "1"), (str(lv + 1), "Cited by", "11"),
                 (str(lv + 1), "How it has changed", "10")]:
        bad.append(f"the fold's lists are not headed one level under the section's h{lv}: {heads}")
    if not re.search(r'How it has changed <span class="rs-fcount">&middot; 10</span></h\d>'
                     r'<p class="rs-note">[^<]*</p>'
                     r'<ul class="rs-list" data-fold="8">(?:<li[^>]*>.*?</li>){10}</ul>', s5):
        bad.append("the history of ten is not drawn whole with data-fold=\"8\"")
    if not re.search(r'<h\d class="rs-fh">Cited by <span class="rs-fcount">&middot; 11</span></h\d><ul class="rs-refs" data-fold="8">(?:<li>.*?</li>){11}</ul>', s5):
        bad.append("Cited by's eleven are not drawn whole with data-fold=\"8\"")
    if "rs-more" in page or "<summary>Show all" in page:
        bad.append("the page still draws a Show all of its own beside a list")
    # The act's own words, its section with them, stay in its pill
    # (_rsa_history_pills holds the pills).
    if 'title="Laws of 1990, chapter 10, section 1"' not in s5:
        bad.append("a history pill does not keep the act's words")
    # The Laws page's reader puts a section in after the page has loaded,
    # and folds its lists as the chapter's page does.
    read = B.LANDING_JS[B.LANDING_JS.find("read.innerHTML='<p class=\"lw-rcrumb\">"):]
    if not ("window.rsFold=fold" in B.CHAPTER_JS and B.CHAPTER_JS in page
            and 0 <= read.find("window.rsFold(read)") < read.find("read.scrollTop=0")):
        bad.append("the Laws page's reader does not fold the lists of the section it puts in")
    node = shutil.which("node") or shutil.which("node.exe")
    if node:
        script = B.CHAPTER_JS[len("<script>"):-len("</script>")]
        r = _node_file(node, f"const SCRIPT = {json.dumps(script)};\n" + _FOLD_NODE,
                       capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, "the chapter page's script stopped: " + (r.stderr or "").strip()[-300:]
        out = json.loads(r.stdout.strip().splitlines()[-1])
        want = {"after_list": True, "folded": [8, "Show all 10", "false"],
                "opened": [10, "Show fewer", "true", True], "closed": [8, "Show all 10"],
                "with_fold": [8, "Show all 10"], "eight": [8, True], "later": [8, 1]}
        if out != want:
            bad.append(f"Show all does not open and close in place: {out}, not {want}")
    assert not bad, "; ".join(bad)
    return "ok", ("one fold, \"History and citations\" with its counts, its lists headed under the section; "
                  + ("Show all opens and closes in place, and with the fold" if node else
                     "node is not here for the script"))


@check("build", "a section's history is drawn as pills, one for each act, newest first: the bill "
       "linked with the law's year, or the year and chapter where there is no bill, the law's own "
       "words kept for a screen reader and a pointer, and the fold counting the pills",
       needs=("build_rsa", "rsa", "shell"))
def _rsa_history_pills(B, RSA, S):
    """Alice, 8 November 2026, on dry run 7 from her phone: the History and
    citations fold "looks a lot better", but How it has changed should be
    pills, as the other three lists are -- "Knowing the session chapter law
    info is usually just visual noise and the pills are significantly
    cleaner and more compact." Each act is one pill, in the shape of Other
    bills that proposed changes: the bill linked with the law's year, "HB
    1604-FN 2022"; where the record has no bill, the year and chapter, "1985
    ch. 302". The rows of one act are one pill -- RSA 100-A:1 had eleven of
    2025 chapter 142, eleven sections of HB 282-FN -- and the fold's count is
    of the pills. "Laws of 2022, chapter 269, section 2" leaves what is seen
    and stays in the pill's name for a screen reader, and as its title.
    Held on the definitions check's chapter, with a history of an act of
    three sections with its bill, two acts of one year with none, an act of
    an earlier term's bill, and a law the note cites by its chapter alone."""
    t = _def_table(RSA, _DEF_PASSAGES)
    hist = [["1913", "145:18", ""], ["1937", "107:14", ""], ["1937", "133:75", ""],
            ["1994", "54:1", "1993-1994/HB1157"],
            ["2025", "142:4", "2025-2026/HB282"], ["2025", "142:27", "2025-2026/HB282"],
            ["2025", "142:9", "2025-2026/HB282"], ["2026", "12", ""]]
    data = {"enacted": {"153:5": hist}, "statute": {}}
    root = Path(tempfile.mkdtemp(prefix="gr-rsapills-"))
    try:
        (root / "idx").mkdir()
        for term, row in (("2025-2026", {"id": "HB282", "n": "HB 282-FN", "year": 2025}),
                          ("1993-1994", {"id": "HB1157", "n": "HB 1157", "year": 1994})):
            (root / "idx" / f"{term}.json").write_text(json.dumps([dict(row, title="x", kind="law",
                                                       chip="Became Law", term=term)]), encoding="utf-8")
        bills = B.Bills(root, "2025-2026")
        page = B.chapter_page(S.template(Path("site")), t, data, bills, "153", "https://graniterecord.org")
        pills = B.history_pills(list(reversed(hist)), bills)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    s5 = page[page.index('id="s5"'):]
    s5 = s5[:s5.index("</section>")]
    bad = []
    no_bill = lambda y, ch, says: (f'<li title="{says}"><span aria-hidden="true">{y} ch. {ch}</span>'
                                   f'<span class="sr">{says}</span></li>')
    a_bill = lambda href, n, y, says: (f'<li title="{says}"><a href="{href}">{n}<span class="sr">, {says}'
                                       f'</span></a> <span class="rs-yr">{y}</span></li>')
    want = [no_bill("2026", "12", "Laws of 2026, chapter 12"),
            a_bill("/bill/2025/hb282", "HB 282-FN", "2025", "Laws of 2025, chapter 142, sections 4, 9 and 27"),
            a_bill("/bill/1994/hb1157", "HB 1157", "1994", "Laws of 1994, chapter 54, section 1"),
            no_bill("1937", "133", "Laws of 1937, chapter 133, section 75"),
            no_bill("1937", "107", "Laws of 1937, chapter 107, section 14"),
            no_bill("1913", "145", "Laws of 1913, chapter 145, section 18")]
    if pills != want:
        bad.append(f"history_pills draws {pills}, not one pill an act, newest first: {want}")
    part = re.search(r'<h\d class="rs-fh">How it has changed <span class="rs-fcount">&middot; 6</span></h\d>'
                     r'<p class="rs-note">From the section'
                     r"(?:&#x27;|')s source note, newest first\.</p>(<ul[^>]*>.*?</ul>)", s5)
    ul = part.group(1) if part else ""
    if ul != '<ul class="rs-list">' + "".join(want) + "</ul>":
        bad.append(f"How it has changed is not the pills in a list of pills, under its note: {ul[:200]!r}")
    seen = re.sub(r"<[^>]+>", " ", re.sub(r'<span class="sr">.*?</span>', "", ul))
    if "Laws of" in seen or "chapter" in seen:
        bad.append(f"a law's words are on a pill where they are seen: {seen.strip()[:200]!r}")
    if 'How it has changed <span class="rs-fcount">&middot; 6</span>' not in s5:
        bad.append("the heading does not count the pills, six acts of eight rows")
    if "rs-hist" in _source("src/pages/app.css") \
            or "rs-hist" in _source("src/pages/build_rsa.py"):
        bad.append("the history's rows (rs-hist) are still styled or drawn")
    assert not bad, "; ".join(bad)
    return "ok", ("six acts of eight rows are six pills, newest first, a bill's with its law's year "
                  "and a law's with no bill as its year and chapter, the law's words in each pill's "
                  "name and title, and the fold counting six")


@check("build", "the Laws landing: titles say which chapters they hold, chapters carry their name, "
       "status and topic, and a repealed or moved chapter says so in words", needs=("build_rsa", "rsa", "shell"))
def _rsa_landing(B, RSA, S):
    """The person, 11 October 2026: laid out as the bill search is, "filters
    on the side"; "the top level titles should have something similar to the
    general court's RSA website that tells you which chapters each title
    includes before you click it"; topics "in a similar way to bills"; and
    repealed chapters plain to see. The two repeal notes are the table's own
    for RSA 71 and RSA 373."""
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA", "titleNumber", "url"]
    t = RSA.Table([dict(zip(cols, r)) for r in (
        ["1", "V", "72", "72-1", "TITLE V TAXATION", "CHAPTER 72 PERSONS AND PROPERTY LIABLE TO TAXATION",
         "Section 72:1 Poll Taxes.", "", "", "<codesect> Repealed.</codesect>", "5", "V\\72\\72-1.htm"],
        ["2", "V", "72", "72-6", "TITLE V TAXATION", "CHAPTER 72 PERSONS AND PROPERTY LIABLE TO TAXATION",
         "Section 72:6 Real Estate.", "", "", "<codesect> All real estate</codesect>", "5",
         "V\\72\\72-6.htm"])])
    assert "72" in t.chapters, sorted(t.chapters)
    data = {"bills": {"2025-2026": {"HB100": {"changes": ["72:6"]}, "HB101": {"changes": ["72:6"]}}},
            "statute": {}, "enacted": {},
            "asof": {"laws_through": 2025}}
    root = Path(tempfile.mkdtemp(prefix="gr-rsal-"))
    try:
        (root / "idx").mkdir()
        (root / "idx" / "2025-2026.json").write_text(json.dumps([
            {"id": "HB100", "n": "HB 100", "year": 2025, "title": "x", "kind": "active", "chip": "In committee",
             "term": "2025-2026", "topic": "Taxes - State"},
            {"id": "HB101", "n": "HB 101", "year": 2025, "title": "y", "kind": "law", "chip": "Signed into law",
             "term": "2025-2026", "topic": "Taxes - State"}]), encoding="utf-8")
        bills = B.Bills(root, "2025-2026")
        topics, pending = B.chapter_topics(data, bills), B.chapter_pending(data, bills)
        page = B.landing_page(S.template(Path("site")), t, data, "https://graniterecord.org", topics, pending)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert topics.get("72") == ["Taxes - State"] and pending.get("72"), (topics, pending)
    title = page[page.index('id="t-V"'):]
    # The span and the count, and since 14 October 2026 (the person's ask) not
    # the first chapters' names as well: a closed title is its number, its
    # name, its span and how many chapters it holds.
    closed = title[:title.index('class="lw-chs"')]
    assert '<span class="lw-tno">Title V</span>' in title and "Chapter 72 &middot;" in title, \
        "Title V does not say which chapters it holds before it is opened"
    assert "Persons and Property Liable to Taxation" not in closed and "lw-tpeek" not in closed, \
        "a closed title lists its chapters' names again, under the count"
    assert '<span class="lw-chn">Chapter 72:</span>' in page and 'data-topics="Taxes - State"' in page \
        and 'data-pend="1"' in page and "1 pending" in page, "the chapter's label, topic or pending count is missing"
    for name in ("st", "tp", "ti"):
        assert f'name="{name}"' in page, f"the {name} filter is missing"
    assert 'id="lwread"' in page and 'data-sec' in B.LANDING_JS, "no reader for a chosen section"
    gone = B.repeal_words("TITLE V\nTAXATION CHAPTER 71\nTHE TAX COMMISSION Chapter 71 Repealed \u2013 "
                          "Entire Chapter was repealed\n[Repealed 1973, 544:19, eff. Sept. 1, 1973.]")
    assert gone == " It was repealed by the Laws of 1973, chapter 544:19, effective Sept. 1, 1973.", gone
    note = ("TITLE XX\nTRANSPORTATION CHAPTER 373\nCROSSINGS Chapter 373 Repealed \u2013 Entire Chapter was "
            "repealed\n[Redesignated as RSA 246 by 2024, 33:4, eff. July 1, 2024.]")
    assert B.moved_to(note) == "246" and 'It is now <a href="/laws/246">RSA 246</a>' in B.repeal_words(note), \
        B.repeal_words(note)
    css = _source("src/pages/app.css")
    assert re.search(r"\.rs-folds\{[^}]*flex-direction:column", css), \
        "the section's folds sit side by side, so opening one moves the other"
    assert re.search(r"\.rs-banner\{[^}]*var\(--t-lead\)", css), "the repeal banner is not at the lead's size"
    return "ok", ("Title V names Chapter 72 before it opens; status, topic and title filters; 71 repealed "
                  "in 1973 and 373 moved to RSA 246, in words")


@check("build", "the Laws landing is laid out as the bill search is: its search box first, its filters as the "
       "bill search's groups with Topic open and the rest shut, and the topics by name",
       needs=("build_rsa", "rsa", "shell", "parse_constitution"))
def _laws_search_layout(B, RSA, S, PC):
    """The person, 24 October 2026: "Topics in the rsa pages should be sorted
    alphabetically", and "The search system on the RSA page should be more
    similar to the bills page with the searchbar at the top, the filters on
    the left side that are dropdowns closed by default except for the first
    one which is the most common filter to be used, likely topics for the
    laws page".

    The topics here are named to sort wrongly three ways: by how many
    chapters hold each (Zoning first, as the list ran until that day), by
    case ("animals" after "Zoning") and by accent ("élections" after both).
    The markup is the bill search's (app.js fgroup, bills.html's box and
    Filter button), so the two read as one search; and on the page with its
    Constitution tab, the search is first in the statutes' panel, above the
    panel's lead."""
    t = _rsa_fixture_table(RSA)
    topics = {"3-A": ["Zoning and Planning", "élections"], "404": ["Zoning and Planning", "Banking", "animals"],
              "999": ["Agriculture"]}
    data = {"bills": {}, "statute": {}, "enacted": {}, "asof": {"laws_through": 2025}}
    page = B.landing_page(S.template(Path("site")), t, data, "https://graniterecord.org", topics, {}, con={})
    shown = re.findall(r'<input type="checkbox" name="tp" value="([^"]+)">', page)
    assert shown == ["animals", "Banking", "élections", "Zoning and Planning"], (
        f"the Topic filter lists {shown}, not by name with case and accents set aside")
    assert B.shown_order("Éducation") < B.shown_order("Elections") < B.shown_order("fish") \
        < B.shown_order("Fish & Game"), "shown_order does not set case and accents aside"
    # The count beside a topic is of the chapters the page lists: RSA 999,
    # which no row lists, does not count, nor offer Agriculture at all.
    assert 'value="Agriculture"' not in page and re.search(
        r'value="Zoning and Planning"><span>Zoning and Planning</span><span class="c">2</span>', page), (
        "a topic counts a chapter the page does not list")
    # The search box first, as the bill search's is, in its markup.
    assert re.search(r'<div class="lw-q" role="search" aria-label="Search the laws"><form id="rsform" '
                     r'class="qline"[^>]*>.*?<div class="qbox"><input id="rsq"', page), (
        "the Laws search is not the bill search's box (.qline, .qbox) in a role=search row")
    assert page.index('id="rsq"') < page.index('id="lwfacets"') < page.index('id="lwdir"'), (
        "the search box does not come before the filters, nor the filters before the directory")
    heads = re.findall(r'<button type="button" class="fhead" data-lwg="(\w+)" aria-expanded="(\w+)" '
                       r'aria-controls="lwg-\1">', page)
    assert heads == [("tp", "true"), ("st", "false"), ("ti", "false")], (
        f"the filter groups and whether each is open: {heads}, not Topic open first and Status and Title shut")
    for key, shut in (("tp", False), ("st", True), ("ti", True)):
        m = re.search(rf'<div class="fbody(?: whole)?" id="lwg-{key}"( hidden)?>', page)
        assert m and bool(m.group(1)) == shut, f"the {key} group's body is {'open' if shut else 'shut'}"
    assert page.count('<div class="fgroup') == 3 and 'class="fopt"' in page and 'class="c"' in page, (
        "the groups are not drawn as the bill search's (.fgroup, .fopt, .c)")
    assert ('<button class="ftoggle" id="lwftoggle" type="button" aria-expanded="false" '
            'aria-controls="lwfacets">') in page, "no Filter button for a narrow screen, as /bills has"
    assert '<aside class="facets lw-side" id="lwfacets" aria-label="Filters">' in page
    js = B.LANDING_JS
    for said, what in (('closest(".fhead[data-lwg]")', "a group's head does not open and shut it"),
                       ('root.classList.toggle("fopen",on)', "the Filter button does not open the groups"),
                       ('tog.setAttribute("aria-expanded"', "the Filter button does not say it is open"),
                       ('NAMES={tp:"topic",st:"status",ti:"title"}', "the filters are not in the address"),
                       ("history.replaceState(history.state", "the filters are not written into the address"),
                       ("keepCh(chOf(x[0]))", "the search's hits are not held to the filters")):
        assert said in js, what
    css = _source("src/pages/app.css")
    narrow = re.search(r"@media \(max-width:59\.9375em\)\{\n  \.lw\{[^\n]*grid-template-areas:\"t\" \"f\" \"d\""
                       r"(.*?)\n\}", css, re.S)
    assert narrow and ".shell .lw .ftoggle{display:flex}" in narrow.group(1) \
        and ".shell .lw:not(.fopen) .facets{display:none}" in narrow.group(1), (
            "under 60em the Laws filters are not behind their Filter button, as the bill search's are")
    assert ".shell .lw .facets{display:block}" in css and \
        ".shell:has(.rs-page) > .facets,.shell:has(.rs-page) > .ftoggle{display:none}" in css, (
            "the template's rule that hides its own filter column on the Laws pages hides theirs too")
    assert "#q,#rsq{" in css and "#qgo,#rsgo{" in css, "the Laws box is not drawn as the bill search's"
    app = _source("src/pages/app.js")
    assert 'const g=e.target.closest("#facets .fhead");' in app, (
        "app.js's click on a filter group's head is not held to /bills' own, so the Laws page's would redraw it")
    con = PC.load()
    if not con:
        return "ok", "the layout held; collected/constitution.json is not here, so the tabbed page was not drawn"
    tabbed = B.landing_page(S.template(Path("site")), t, data, "https://graniterecord.org", topics, {}, con=con)
    panel = tabbed[tabbed.index('id="statutes" role="tabpanel"'):]
    assert panel.index('id="rsq"') < panel.index("Includes changes through 2025"), (
        "in the statutes' panel the search is under the panel's lead, not at the top")
    return "ok", ("topics animals, Banking, élections, Zoning and Planning; the box first, Topic open, Status "
                  "and Title shut, the Filter button under 60em; the search above the panel's lead")


def _passed_record(body, steps=()):
    """A bill page that carries its record, as shell.page writes one: the
    bill's text (billtext.body) and its journey's steps."""
    rec = {"billtext": {"version": "FINAL VERSION", "body": body},
           "journey": {"steps": [dict(s) for s in steps], "rail": []}}
    return ('<!DOCTYPE html><html><body><script type="application/json" id="gr-data">'
            + json.dumps(rec).replace("</", "<\\/") + "</script></body></html>")


@check("build", "a statute page lists the bills passed that change it and have not taken effect, each with "
       "when it takes effect: the chaptered law's day, the section's own, a counted day said as counted, "
       "and \"not stated\" where the record says none", needs=("build_rsa", "rsa", "shell"))
def _rsa_passed_not_in_effect(B, RSA, S):
    """The person, 24 October 2026: "Pending rsas should show when a bill has
    passed but has not yet taken effect, with a line about when the bill
    takes effect and a link to its page". Until then Pending was the bills
    still before the General Court, and after the session there were none.

    Seven bills of the sitting term change RSA 91-A, on 24 October 2026:
      HB 1  law, its rail's Law stop January 1, 2027: "Takes effect January 1, 2027"
      HB 2  law in parts, its chaptered text's own last lines: section 2, the
            prospective repeal of 91-A:6, II, on January 1, 2027, the rest
            (91-A:5) on August 1, 2026 -- and a docket line that is another
            bill's, which is not read (HB 1184 of 2026's)
      HB 3  law, its Law stop August 1, 2026: in effect, and not listed
      HB 4  became law unsigned on October 1, 2026, "60 days after its
            passage": November 30, 2026, said as counted
      HB 5  through both chambers and with the Governor, no effective date in
            its text: "Effective date not stated in the record we hold"
      HB 6  law, nothing in its record to read: listed apart, as stated
            nowhere, and not counted as pending
      HB 7  in committee: one of the bills before the General Court
    And the readers each hold real lines from the bills' pages (24 October
    2026): HB 1384's 12:01 a.m., SB 245's "Sections 3.4.5", SB 464's Article
    44 sentence, HB 1184's "Effective:", HB 358 of 2023's line not read."""
    import datetime as _dt
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA", "titleNumber", "url"]
    rows_ = []
    for n, (sec, head) in enumerate((("4", "Minutes and Records Available for Public Inspection."),
                                     ("5", "Exemptions."), ("6", "Fees."))):
        rows_.append([str(n), "VI", "91-A", f"91-A-{sec}", "TITLE VI PUBLIC OFFICERS AND EMPLOYEES",
                      "CHAPTER 91-A ACCESS TO GOVERNMENTAL RECORDS AND MEETINGS", f"Section 91-A:{sec} {head}",
                      "", "", "<codesect> I. The records.<br> II. The fees.</codesect>", "6",
                      f"VI\\91-A\\91-A-{sec}.htm"])
    t = RSA.Table([dict(zip(cols, r)) for r in rows_])
    data = {"bills": {"2025-2026": {
        "HB1": {"changes": ["91-A:4"]}, "HB2": {"changes": ["91-A:5", "91-A:6"]}, "HB3": {"changes": ["91-A:5"]},
        "HB4": {"changes": ["91-A:5"]}, "HB5": {"changes": ["91-A:4"]}, "HB6": {"changes": ["91-A:4"]},
        "HB7": {"changes": ["91-A:4"]}}}, "statute": {}, "enacted": {}, "asof": {"laws_through": 2026}}
    law = lambda i, gm, g, lday, ch, status="Signed into law": {   # noqa: E731
        "id": i, "n": i[:2] + " " + i[2:], "year": 2026, "title": "relative to records", "kind": "law",
        "status": status, "chip": "Became Law", "term": "2025-2026", "chapter": ch,
        "rail": [["Ip", "2026-01-07"], ["Hp", "2026-03-05"], ["Sp", "2026-05-07"], [gm, g, "signed"],
                 ["Lp", lday, f"Chapter {ch}"]]}
    idx = [law("HB1", "Gp", "2026-07-02", "2027-01-01", "207"), law("HB2", "Gp", "2026-07-02", "", "205"),
           law("HB3", "Gp", "2026-06-02", "2026-08-01", "90"),
           law("HB4", "Gp", "2026-10-01", "", "128", "Became law unsigned"), law("HB6", "Gp", "2026-06-11", "", "129"),
           {"id": "HB5", "n": "HB 5", "year": 2026, "title": "y", "kind": "active", "status": "Enrolled",
            "chip": "Enrolled", "term": "2025-2026",
            "rail": [["Ip", "2026-01-07"], ["Hp", "2026-03-05"], ["Sp", "2026-05-07"], ["Gh"], ["L-"]]},
           {"id": "HB7", "n": "HB 7", "year": 2026, "title": "z", "kind": "active", "status": "In committee",
            "chip": "In committee", "term": "2025-2026"}]
    idx[3]["rail"][3][2] = "unsigned"
    root = Path(tempfile.mkdtemp(prefix="gr-rsapass-"))
    try:
        (root / "idx").mkdir()
        (root / "idx" / "2025-2026.json").write_text(json.dumps(idx), encoding="utf-8")
        (root / "bill" / "2026").mkdir(parents=True)
        (root / "bill" / "2026" / "hb2.html").write_text(_passed_record(
            "Be it Enacted by the Senate and House of Representatives in General Court convened:\n"
            "205:1 Records. Amend RSA 91-A:5, I to read as follows:\nI. The records.\n"
            "205:2 Prospective Repeal. RSA 91-A:6, II, relative to fees, is repealed.\n"
            "205:3 Effective Date.\nI. Section 2 of this act shall take effect January 1, 2027.\n"
            "II. The remainder of this act shall take effect 30 days after its passage.\n"
            "Approved: July 02, 2026\nEffective Date:\nI. Section 2 effective January 1, 2027\n"
            "II. Remainder effective August 1, 2026",
            [{"act": "law", "text": "Chapter 205, in effect in parts: section 2 on Jan 1, 2028, "
                                    "the rest on Jan 1, 2028"}]), encoding="utf-8")
        (root / "bill" / "2026" / "hb4.html").write_text(_passed_record(
            "128:1 Repeal. RSA 91-A:5, II is repealed.\n128:2 Effective Date. This act shall take effect "
            "60 days after its passage.\nApproved: October 01, 2026\nEffective Date:\nEnacted in accordance "
            "with Article 44, Part II of the N.H. Constitution, without the signature of the governor "
            "October 1, 2026"), encoding="utf-8")
        (root / "bill" / "2026" / "hb5.html").write_text(_passed_record(
            "1 Records. Amend RSA 91-A:4 to read as follows: the records."), encoding="utf-8")
        bills = B.Bills(root, "2025-2026", today=_dt.date(2026, 10, 24), table=t)
        page = B.chapter_page(S.template(Path("site")), t, data, bills, "91-A", "https://graniterecord.org")
        pending = B.chapter_pending(data, bills)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    block = page[page.index('class="rs-pending"'):page.index('class="rs-sec"')]
    known = block[block.index("<h2>Passed, not yet in effect</h2>"):block.index("<h2>Passed this term")]
    want = {"HB1": "Takes effect January 1, 2027.",
            "HB2": "Its changes here take effect January 1, 2027: ",
            "HB4": "Takes effect November 30, 2026 (60 days after its passage, counted from October 1, 2026, "
                   "the day it became law without the Governor&#x27;s signature).",
            "HB5": "Effective date not stated in the record we hold."}
    for bill, line in want.items():
        item = known[known.index(f'href="/bill/2026/{bill.lower()}"'):]
        item = item[:item.index("</li>")]
        assert line in item, f"{bill}'s line in the chapter's list is {re.sub(r'<[^>]+>', '', item)!r}"
    hb2 = known[known.index('href="/bill/2026/hb2"'):]
    hb2 = hb2[:hb2.index("</li>")]
    assert 'href="/laws/91-a#s6">91-A:6</a>' in hb2 and "91-A:5" not in hb2, (
        "HB 2's change to 91-A:6, section 2 of the act, is not the one listed, or its part already in "
        "effect (91-A:5) is")
    assert "Jan 1, 2028" not in page and "January 1, 2028" not in page, (
        "HB 2's day was read from a docket line that is another bill's, over its own chaptered text")
    assert "Passed both chambers; with the Governor" in known and "chapter 207 of the Laws of 2026" in known, \
        "a bill with the Governor, or a law's chapter of the session laws, is not said"
    tags = "".join(re.findall(r'<details class="rs-tag">.*?</details>', page, re.S))
    assert 'href="/bill/2026/hb3"' not in block + tags, "HB 3, in effect since August 1, 2026, is listed as pending"
    unread = block[block.index("<h2>Passed this term, effective date not stated</h2>"):]
    assert 'href="/bill/2026/hb6"' in unread[:unread.index("</ul>")] and 'href="/bill/2026/hb6"' not in known, \
        "a law whose record states no effective date is not listed apart"
    assert "Bills now before the General Court" in block and 'href="/bill/2026/hb7"' in block
    assert pending.get("91-A") == ["2025-2026/HB1", "2025-2026/HB2", "2025-2026/HB4", "2025-2026/HB5",
                                   "2025-2026/HB7"], f"RSA 91-A's pending changes are {pending.get('91-A')}"
    s6 = page[page.index('id="s6"'):]
    assert "Change takes effect Jan 1, 2027" in s6[:s6.index("</summary>")] and \
        "Its change to this section takes effect January 1, 2027." in s6, "91-A:6's tag does not say its day"
    s5 = page[page.index('id="s5"'):page.index('id="s6"')]
    tag5 = s5[s5.index('<details class="rs-tag">'):s5.index("</details>")]
    assert "Change takes effect Nov 30, 2026" in tag5 and 'href="/bill/2026/hb2"' not in tag5, (
        "91-A:5's tag is not HB 4's day alone: HB 2's change there took effect August 1, 2026 -- " + tag5[:300])
    s4 = page[page.index('id="s4"'):page.index('id="s5"')]
    assert "Pending: 4 bills" in s4, "91-A:4's tag does not count its four bills"

    # The readers, on lines as the bills' pages print them.
    day = _dt.date
    parts = B.chaptered_parts("x\nApproved: July 02, 2026\nEffective Date:\nI. Section 2 effective 12:01 a.m. "
                              "January 1, 2027\nII. Remainder effective January 1, 2027")
    assert [(sorted(p.secs), p.rest, p.day) for p in parts] == [([2], False, day(2027, 1, 1)),
                                                                ([], True, day(2027, 1, 1))], parts
    assert B.effect_words(B.Effect(parts, "law", False), day(2026, 10, 24)) == "Takes effect January 1, 2027."
    parts = B.chaptered_parts("x\nEffective Date:\nI. Section 2 effective January 1, 2028\nII. Sections 3.4.5 "
                              "effective January 1, 2026\nV. Remainder effective July 31, 2025")
    assert parts and sorted(parts[1].secs) == [3, 4, 5], parts
    parts = B.chaptered_parts("x\nEffective Date: January 01, 2027\nEnacted in accordance with Article 44, Part II "
                              "of the N.H. Constitution, without the signature of the governor June 20, 2026")
    assert len(parts) == 1 and parts[0].rest and parts[0].day == day(2027, 1, 1), parts
    parts = B.chaptered_parts("x\nVETOED July 10, 2026 / Veto Overridden August 19, 2026.\nEffective:\n"
                              "I. Section 3 effective August 19, 2027\nII. Remainder effective October 18, 2026")
    assert [p.day for p in parts] == [day(2027, 8, 19), day(2026, 10, 18)], parts
    assert B.chaptered_parts("x\nEffective Date:\nI. Sec 20, except RSA 275:82 eff July 1, 2025\nII. RSA 275:82 "
                             "inserted by Sec 20 eff July 1, 2026\nIII. Remainder effective October 3, 2023") is None, \
        "a part read only in part (HB 358 of 2023's 'Sec 20, except RSA 275:82') was read as though whole"
    parts = B.journey_parts({"journey": {"steps": [{"act": "law", "text": "Chapter 287, in effect in parts: sections "
                                                    "1 and 2 as section 3 provides, section 14 on Jan 1, 2027, the "
                                                    "rest on Jan 1, 2026"}]}})
    assert [(sorted(p.secs), p.day, p.how) for p in parts] == [
        ([1, 2], None, "as section 3 of the act provides"), ([14], day(2027, 1, 1), ""), ([], day(2026, 1, 1), "")], parts
    assert B.note_days("2026, 179:1, eff. Aug. 18, 2026; 262:5, eff. Jan. 1, 2027; 309:8, eff. Jan. 1, 2027.",
                       "2026", "309") == {8: day(2027, 1, 1)}
    assert B.note_days("2015, 276:127, eff. July 1, 2105.", "2015", "276") == {}, \
        "a note's slip of the keys (RSA 287-E:16's 2105) was read as a day"
    many = tuple(B.Part(frozenset([n]), False, "", d, "") for n, d in
                 ((1, day(2025, 8, 26)), (4, day(2026, 1, 1)), (3, day(2027, 7, 1)))) + (
        B.Part(frozenset(), True, "", day(2025, 7, 1), ""),)
    assert B.effect_words(B.Effect(many, "law", False), day(2026, 10, 24)) == (
        "Section 3 of the act takes effect July 1, 2027; its other parts have taken effect."), \
        B.effect_words(B.Effect(many, "law", False), day(2026, 10, 24))
    return "ok", ("HB 1 on January 1, 2027; HB 2's section 2 on 91-A:6 and not its part in effect, its own "
                  "chaptered lines over another bill's docket line; HB 4 counted to November 30, 2026 and "
                  "said so; HB 5 with the Governor, not stated; HB 6 apart; HB 3 not listed")


# The harness of _filter_offers: app.js in node beside stub.js (dom_stub.js),
# with a search box that keeps its attributes, so the combobox's can be read.
_OFFERS_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
const q = document.querySelector("#q");
q.id = "q"; q.attrs = {};
q.setAttribute = (k, v) => { q.attrs[k] = String(v); };
q.getAttribute = k => (k in q.attrs ? q.attrs[k] : null);
q.removeAttribute = k => { delete q.attrs[k]; };
const urls = [];
history.replaceState = (s, t, u) => { urls.push(String(u)); };
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({filterOffers, QOFFERS, sel, IDX, openGroups, setMeta:(m)=>{META=m;}, setTerm:(t)=>{term=t;},"
  + " getQuery:()=>query})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
s.setMeta({terms: ["2025-2026"], committee_codes: {}, topics: ["Housing", "Education - General"]});
const row = (id, topic, committees) => ({id, n: id, title: "relative to " + topic.toLowerCase(), kind: "active",
  status: "In committee", chip: "In committee", committees, committee: committees[0] || "", topic, sponsor: "",
  term: "2025-2026", year: 2026, passage: "", votedays: [], nrc: 0, last_action: ""});
s.IDX.length = 0;
s.IDX.push(row("HB1", "Housing", ["House Housing"]), row("HB2", "Housing", ["House Judiciary"]),
           row("HB3", "Education - General", ["House Housing"]), row("HB4", "Education - General", ["Senate Education"]),
           row("HB5", "Elections", ["House No Committee Assignment"]));
s.setTerm("2025-2026");
const out = {};
const type = v => { q.value = v; q.fire("input"); };
const key = k => q.fire("keydown", {key: k});
try {
  type("housing");
  out.offers = s.QOFFERS.rows().map(o => [o.key, o.v, o.n, o.rest]);
  out.list = s.QOFFERS.list.innerHTML;
  out.shown = !s.QOFFERS.list.hidden;
  out.box = [q.attrs.role, q.attrs["aria-autocomplete"], q.attrs["aria-controls"], q.attrs["aria-expanded"]];
  out.say = s.QOFFERS.say.textContent;
  key("ArrowDown");
  out.active = q.attrs["aria-activedescendant"];
  out.selected = (s.QOFFERS.list.innerHTML.match(/aria-selected="true"/g) || []).length;
  key("Enter");
  out.taken = {topic: [...s.sel.topic], query: s.getQuery(), box: q.value, open: s.openGroups.has("topic"),
    url: urls.filter(u => u.includes("topic=")).pop() || "", shut: s.QOFFERS.list.hidden,
    expanded: q.attrs["aria-expanded"]};
  out.facets = document.querySelector("#facets").innerHTML;
  s.sel.topic.clear();
  type("affordable housing");
  out.affordable = s.QOFFERS.rows().map(o => [o.key, o.v, o.rest]);
  type("senate housing");
  out.senate = s.QOFFERS.rows().map(o => [o.key, o.v]);
  type("hou");
  out.begun = s.QOFFERS.rows().map(o => [o.key, o.v]);
  type("ho");
  out.short = s.QOFFERS.rows().length;
  type("HB 1");
  out.number = s.QOFFERS.rows().length;
  type("education");
  out.education = s.QOFFERS.rows().map(o => [o.key, o.v]);
  type("housing"); key("Escape");
  out.escape = [s.QOFFERS.rows().length, s.QOFFERS.list.hidden];
  // Return with the offers open and none chosen: the words are searched.
  type("housing");
  out.openBeforeReturn = s.QOFFERS.rows().length;
  key("Enter");
  out.words = {query: s.getQuery(), topic: [...s.sel.topic], committee: [...s.sel.committee]};
  // The Laws page's filters, given to the same function as LANDING_JS gives them.
  out.laws = s.filterOffers("housing", [
    {key: "tp", values: [["Housing", "Housing", 23], ["Zoning and Planning", "Zoning and Planning", 40]],
     say: n => "All chapters with the topic <b>" + n + "</b>"},
    {key: "ti", values: [["XVII", "Housing and Redevelopment", 11], ["LV", "Proceedings in Special Cases", 30]],
     say: (n, v) => "All chapters in <b>Title " + v + ": " + n + "</b>"}]).map(o => [o.key, o.v, o.html]);
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").split("\n")[1]; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "typing a filter's name in the bill search's box offers that filter, as a combobox, and "
                   "choosing one ticks it as the list would; Return without choosing searches the words",
       needs=("build_rsa",))
def _filter_offers(B):
    """The person, 24 October 2026: "Searching for a topic in the searchbar in
    the laws page or the bills page should show a dropdown if you type in the
    name of a filter like 'housing' asking if you want to view all bills with
    the housing topics or all bills referred to the housing committee, and
    clicking it will select that filter without you having to manually scroll
    through all the list of topics."

    This runs app.js in node on five bills: "housing" offers the topic
    Housing and the House Housing committee, each with the count it would
    list; the box is a combobox (WAI-ARIA's pattern) whose arrow keys name the
    offer they are on in aria-activedescendant; Return on it ticks the topic,
    opens its group, writes it into the address and takes the word out of the
    box. "affordable housing" offers the same and leaves "affordable";
    "senate housing" offers no House committee; "hou" offers what it begins;
    two letters, a bill number, or Escape offer nothing; and Return with the
    offers open and none chosen searches the words, as it did before. The
    Laws page gives the same function its own filters (LANDING_JS)."""
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return "skip", "app.js, dom_stub.js or node is not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "go.js").write_text(_OFFERS_HARNESS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not run under node: " + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "threw" not in got, f"the offers threw {got['threw']}"
    assert got["offers"] == [["topic", "Housing", 2, ""], ["committee", "House Housing", 2, ""]], (
        f"'housing' offers {got['offers']}")
    assert "All bills with the topic <b>Housing</b>" in got["list"] and \
        "All bills referred to the <b>House Housing Committee</b>" in got["list"] and \
        got["list"].count('role="option"') == 2 and got["shown"], f"the list drawn: {got['list'][:300]}"
    assert got["box"] == ["combobox", "list", "q-offers", "true"], f"the box's combobox attributes: {got['box']}"
    assert got["say"].startswith("2 filters match"), f"the status line says {got['say']!r}"
    assert got["active"] == "q-offers-0" and got["selected"] == 1, (
        f"the down arrow put aria-activedescendant on {got['active']!r}")
    assert got["taken"] == {"topic": ["Housing"], "query": "", "box": "", "open": True,
                            "url": got["taken"]["url"], "shut": True, "expanded": "false"} \
        and "topic=Housing" in got["taken"]["url"], f"Return on the offer: {got['taken']}"
    assert re.search(r'data-g="topic"\s+aria-expanded="true"', got["facets"]) and re.search(
        r'data-f="topic"\s+value="Housing" checked', got["facets"]), "the Topic group is not open with Housing ticked"
    assert got["affordable"] == [["topic", "Housing", "affordable"], ["committee", "House Housing", "affordable"]], \
        f"'affordable housing' offers {got['affordable']}"
    assert got["senate"] == [["topic", "Housing"]], f"'senate housing' offers {got['senate']}"
    assert got["begun"] == [["topic", "Housing"], ["committee", "House Housing"]], f"'hou' offers {got['begun']}"
    assert got["short"] == 0 and got["number"] == 0, "two letters, or a bill number, offered a filter"
    assert got["education"] == [["topic", "Education - General"], ["committee", "Senate Education"]], (
        f"'education' offers {got['education']}: the committee named for it first, and no 'No Committee "
        "Assignment'")
    assert got["escape"] == [0, True], "Escape does not shut the offers"
    assert got["openBeforeReturn"] == 2 and got["words"] == {"query": "housing", "topic": [], "committee": []}, (
        f"Return with no offer chosen did not search the words: {got['words']}")
    assert got["laws"] == [["tp", "Housing", "All chapters with the topic <b>Housing</b>"],
                           ["ti", "XVII", "All chapters in <b>Title XVII: Housing and Redevelopment</b>"]], got["laws"]
    for said in ("window.filterCombo(box,{offers:lawOffers,choose:take", "if(offers&&offers.enter())return;",
                 '{key:"tp",values:vals("tp")', '{key:"ti",values:vals("ti")', '{key:"st",values:vals("st")'):
        assert said in B.LANDING_JS, f"the Laws page's search does not offer its filters: no {said}"
    css = _source("src/pages/app.css")
    assert re.search(r"\.qoffer\{[^}]*min-height:44px", css), "an offer is not 44px tall"
    return "ok", ("'housing' offers the topic and the House Housing committee with their counts; the arrow, "
                  "Return and Escape as WAI-ARIA's combobox; the topic ticked and in the address, the word out "
                  "of the box; Return on words still searches them; the Laws page's filters through the same")


@check("build", "the Laws page has a Constitution tab: every article under its own anchor with a link to itself, "
       "a lead saying what it is and when nh.gov's text was read, and an address naming an article opens it",
       needs=("build_rsa", "constitution_tab", "parse_constitution", "rsa", "shell"))
def _constitution_tab(B, CT, PC, RSA, S):
    """The person, 17 October 2026: the Constitution "on the laws page,
    possibly on its own tab". The statutes stay the first tab and read as
    they did; the Constitution is the second, laid out as a statute chapter
    is, each article at /laws#part1-art2-a and each part at /laws#part1.
    Without collected/constitution.json the page is built as it was, with no
    tabs. And the site the fixture builds -- build_rsa's main(), not only
    this function -- carries the tab with all 156 articles."""
    con = PC.load()
    assert con, "collected/constitution.json is not on this disk"
    data = {"bills": {}, "statute": {}, "enacted": {}, "asof": {"laws_through": 2025}}
    t = _rsa_fixture_table(RSA)
    page = B.landing_page(S.template(Path("site")), t, data, "https://graniterecord.org", {}, {}, con=con)
    assert 'role="tablist"' in page and page.index('id="tab-statutes"') < page.index('id="tab-constitution"'), \
        "the Laws page has no tabs, or the Constitution is not the second"
    assert 'id="constitution" role="tabpanel"' in page and 'id="statutes" role="tabpanel"' in page
    panel = page[page.index('id="constitution" role="tabpanel"'):]
    missing, unlinked = [], []
    for p, a in PC.articles(con):
        if panel.count(f'id="{a["anchor"]}"') != 1:
            missing.append(a["anchor"])
        if f'href="/laws#{a["anchor"]}"' not in panel:
            unlinked.append(a["anchor"])
    assert not missing, f"articles not on the tab once under their anchor: {missing[:8]}"
    assert not unlinked, f"articles with no link to themselves: {unlinked[:8]}"
    assert panel.count('class="rs-sec cn-art"') == 156, panel.count('class="rs-sec cn-art"')
    assert 'id="part1"' in panel and 'id="part2"' in panel, "a part has no anchor"
    assert "read on October 17, 2026" in panel and 'href="https://www.nh.gov/glance/state-constitution"' in panel, \
        "the lead does not say when nh.gov's text was read, or does not link it"
    assert "Includes changes through 2025" in page, "the statutes' own lead is gone from their tab"
    # An address naming an article, not a panel, opens the panel that holds it.
    assert 'closest(".twnpane")' in CT.TABS_JS and "scrollIntoView" in CT.TABS_JS, \
        "an address naming an article does not open the Constitution tab"
    bare = B.landing_page(S.template(Path("site")), t, data, "https://graniterecord.org", {}, {}, con={})
    assert 'role="tablist"' not in bare and 'id="lw"' in bare, "without the file the page is not the one it was"
    css = _source("src/pages/app.css")
    assert ".cn-notes{" in css and ".lw-tabs{" in css, "app.css has no rules for the Constitution tab"
    absent = [x for x in CHAIN_NEEDS + ["build_rsa.py"] if not _paths.locate(x).exists()]
    if absent:
        return "ok", "the tab held; the fixture site was not built: not here, " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    built = (shared / "site" / "laws.html").read_text(encoding="utf-8")
    assert 'id="tab-constitution"' in built and built.count('class="rs-sec cn-art"') == 156, (
        "the fixture's laws.html, as build_rsa's main() wrote it, has no Constitution tab of 156 articles")
    return "ok", "156 articles on the second tab, each anchored and linked; the fixture's laws.html carries it"


@check("build", "a Laws page says where its text is from once, and names next year's laws as "
       "not yet included only from the January that session opens", needs=("build_rsa",))
def _statute_lead_once(B):
    """The audit of 25 October 2026 (S7): a chapter's page opened "The text as
    the General Court's table holds it. Includes changes through 2026; 2027
    laws not yet included. Taken from the General Court's database on ...":
    where the text is from said twice, and, in October 2026, the laws of a
    session that would not open until January. The lead says how current
    the text is, when it was taken and where the official text is; next
    year's laws are said not to be in it from 1 January of that year."""
    import datetime as _dt
    saved = B.TABLE_TAKEN
    try:
        B.TABLE_TAKEN = ""
        for latest, day, want in (
                ("2026", _dt.date(2026, 10, 25), "Includes changes through 2026."),
                ("2026", _dt.date(2026, 12, 31), "Includes changes through 2026."),
                ("2026", _dt.date(2027, 1, 1),
                 "Includes changes through 2026; 2027 laws not yet included."),
                ("2025", _dt.date(2026, 10, 25),
                 "Includes changes through 2025; 2026 laws not yet included.")):
            got = B.as_of(latest, today=day)
            assert got == want, f"with the table through {latest}, on {day}, the lead says {got!r}"
        B.TABLE_TAKEN = "October 18, 2026"
        assert B.as_of("2026", today=_dt.date(2026, 10, 25)) == (
            "Includes changes through 2026. Taken from the General Court's database on "
            "October 18, 2026."), B.as_of("2026", today=_dt.date(2026, 10, 25))
    finally:
        B.TABLE_TAKEN = saved
    src = _source(B.__file__)
    for gone in ("The text as the General Court's table holds it", "as the General Court\\'s table "
                 "holds them"):
        assert gone not in src, f"build_rsa still says {gone!r}"
    return "ok", ("next year's laws named only from its January; the table's source said once, "
                  "by the day it was taken")


@check("build", "the statute reader takes a bill's own instructions, new sections and lists "
       "included, and holds its score against the source notes", needs=("rsa",))
def _rsa_reader(RSA):
    """src/parse/rsa.py (RSA_PAGE.md, 11 October 2026). Every passage below is
    from a real bill text on disk, never typed out of a description:

    - SB 617 (1995-1996): a new section, named by its neighbour, whose own
      heading the text then writes;
    - SB 29 (1991-1992): a new chapter, declared as "CHAPTER 14-B";
    - HB 59 (1989-1990): "Amend the following RSA provisions", whose targets
      follow the colon in a list that drops "RSA".

    Where db/NH_RSA.psv is on disk, the reader is scored against the source
    notes, which it did not write: on the table of 8 September 2026, 90.6% of
    its section claims for enacted bills are confirmed by a note and it finds
    84.5% of what the notes say. A change that lowers either fails here. The
    note of RSA 91-A:4 is read whole: a second law of 2019 after an effective
    date was once lost, and every section's history with it."""
    sb617 = ("commissioners; however, nothing in this chapter is to be construed to alter the "
             "applicability of RSA 38, 149-I or 231.  197:2 New Section; Appointment of Sewer "
             "Commissioners. Amend RSA 149-I by inserting after section 20 the following new "
             "section:  149-I:20-a Appointment. The commissioners may be appointed by the mayor")
    got = RSA.changes(sb617)
    assert "149-I:20-a" in got and "149-I" in got, got
    assert "38" not in got and "231" not in got, f"a mention read as a change: {got}"
    sb29 = ("1 New Chapter; Legislative Ethics Committee Established. Amend RSA by inserting "
            "after chapter 14-A the following new chapter:  CHAPTER 14-B  LEGISLATIVE ETHICS "
            "COMMITTEE  14-B:1 Definitions. In this chapter:  I. \"Investigation\" means")
    assert "14-B:1" in RSA.changes(sb29), RSA.changes(sb29)
    hb59 = ("1 Change from Postsecondary Vocational-technical to Postsecondary Technical. Amend the "
            "following RSA provisions by replacing \"vocational-technical\" with \"technical\": "
            "RSA 4:8-a; 21-K:11, IV; 21-K:14, IV; 94:1-a, I; 188-B:2; 188-D:2, I, III, and IV; "
            "and 188-F.  2 Effective Date. This act shall take effect")
    got = RSA.changes(hb59)
    for a in ("4:8-a", "21-K:11", "21-K:14", "94:1-a", "188-B:2", "188-D:2"):
        assert a in got, f"{a} not read from HB 59's list: {got}"
    note = ("1967, 251:1. 2019, 107:1, eff. Jan. 1, 2020; 163:2, eff. Jan. 1, 2020 at 12:01 a.m. "
            "2024, 49:1, 2, eff. Aug. 13, 2024.")     # RSA 91-A:4's source note
    h = RSA.history(note, {(2024, 49): "2023-2024/SB1"})
    assert [(y, law) for y, law, _b in h] == [(1967, "251:1"), (2019, "107:1"), (2019, "163:2"),
                                              (2024, "49:1")], h
    assert h[-1][2] == "2023-2024/SB1"
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA"]
    t = RSA.Table([dict(zip(cols, r)) for r in (
        ["1", "XXXI", "339", "339-1", "TITLE XXXI", "CHAPTER 339 X", "Section 339:1 Sales Tickets.",
         "", "", "<codesect> I. Every seller shall</codesect>"],
        ["2", "XXXI", "339", "339-71", "TITLE XXXI", "CHAPTER 339 X",
         "Section 339:71-339:76 Repealed by 2007, 138:6, II, eff. Aug. 17, 2007.", "", "",
         "<codesect></codesect>"])])
    assert t.resolve("339", "73") == ("range", "339:71"), t.resolve("339", "73")
    assert t.resolve("339", "80") == (None, None) and not t.dropped, t.dropped
    table = RSA.load()
    if table is None:
        return "ok", "the reader on four real passages; db/NH_RSA.psv not here to score against"
    # THE SCORE NEEDS THE BUILD'S OWN INPUTS: chapters.json, which turns a
    # note's session law into the bill it was, and the bill texts. GitHub's
    # night runs preflight before it builds, with the table from the kit and
    # neither of those yet, and scored 0% for want of them (dry run of
    # 5f317a5, 11 October 2026): that is nothing to score, not a fall.
    chp = Path("chapters.json")
    if not chp.is_file():
        return "ok", "the reader on four real passages; no chapters.json yet to score against the notes"
    data = RSA.build(table, RSA.bill_texts(), json.loads(chp.read_text(encoding="utf-8")))
    sc = RSA.score(table, data)
    if not sc["claims"] or not sc["notes"]:
        return "ok", (f"the reader on four real passages; nothing to score yet ({sc['claims']:,} claims, "
                      f"{sc['notes']:,} notes naming a bill)")
    assert sc["precision"] >= 0.90 and sc["recall"] >= 0.84, \
        f"the reader against the source notes fell: precision {sc['precision']:.1%}, recall {sc['recall']:.1%}"
    return "ok", (f"four real passages; against the source notes precision {sc['precision']:.1%}, "
                  f"recall {sc['recall']:.1%}")


def _css_inherited(rules, chain, props, _memo=None):
    """{property: (value, selector, line, how far out)} for inherited
    properties on chain[0]: each from the nearest element outward that a
    rule sets it on (0 for chain[0] itself), "inherit" and "unset" passed
    through to the next. A property nothing sets is left out: its initial
    value. `_memo` keeps each ancestry's cascade between calls."""
    memo = {} if _memo is None else _memo
    out = {}
    for j in range(len(chain)):
        sig = tuple((e["tag"], tuple(sorted(e["ids"])), tuple(sorted(e["classes"])),
                     tuple(sorted((k, str(v)) for k, v in e["attrs"].items())), tuple(sorted(e["states"])))
                    for e in chain[j:])
        if sig not in memo:
            memo[sig] = _css_won(rules, chain[j:])
        for p in props:
            if p not in out and p in memo[sig] and memo[sig][p][0] not in ("inherit", "unset"):
                out[p] = memo[sig][p] + (j,)
        if len(out) == len(props):
            break
    return out


def _html_text_chains(page, pattern):
    """[(the text matched, chain)] for every match of `pattern` in a page's
    text, chain[0] the element it is written in and then its ancestors out to
    the root (_html_walk)."""
    found = []
    _html_walk(page, text=lambda data, chain: found.extend(
        (m.group(0), chain) for m in re.finditer(pattern, data)))
    return found


@check("frontend", "a Laws chapter's outline skips no level: its sections an h2 under the title, or an h3 "
       "under a part's h2", needs=("build_rsa", "rsa", "shell"))
def _laws_chapter_outline(B, RSA, S):
    """The cohesion audit of 30 October 2026 (I-1): a chapter without parts,
    most of them, went from its h1 to an h3 for every section, with no h2
    anywhere. _heading_levels reads only the pages a fixture site writes at
    the top and in learn/, so it never saw one. Two chapters are drawn here
    through build_rsa's chapter_page, one with a part and one without, and
    each outline must step down one level at a time."""
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA", "titleNumber", "url"]

    def chapter(part):
        rows = []
        for i, (no, name) in enumerate((("659-1", "Hours of Polling."), ("659-2", "Moderator."))):
            rows.append(dict(zip(cols, (
                str(i), "LXIII", "659", no, "TITLE LXIII ELECTIONS", "CHAPTER 659 ELECTION PROCEDURE",
                f"Section {no.replace('-', ':')} {name}", "",
                "<center><h2>CHAPTER 659<br>ELECTION PROCEDURE</h2></center>"
                + ("<h2>Hours of Polling</h2>" if part else ""),
                "<codesect> <br> I. The polls shall be open at least 8 hours.</codesect>", "63",
                f"LXIII\\659\\{no}.htm"))))
        data = {"bills": {}, "enacted": {}, "statute": {}, "asof": {"laws_through": 2025}}
        tmp = Path(tempfile.mkdtemp(prefix="gr-rsaoutline-"))
        try:
            (tmp / "idx").mkdir()
            return B.chapter_page(S.template(Path("site")), RSA.Table(rows), data, B.Bills(tmp, "2025-2026"),
                                  "659", "https://graniterecord.org")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    bad, said = [], []
    for part in (False, True):
        page = chapter(part)
        main = page[page.find("<main"):page.find("</main>")] if "<main" in page else page
        levels = [int(m.group(1)) for m in re.finditer(r"<h([1-6])[ >]", main)]
        secs = re.findall(r'<h([1-6]) class="rs-h"', main)
        what = "with a part" if part else "without parts"
        if not secs:
            bad.append(f"a chapter {what} drew no section heading")
            continue
        prev = 0
        for lv in levels:
            if prev and lv > prev + 1:
                bad.append(f"a chapter {what} goes from h{prev} to h{lv}")
                break
            prev = lv
        # And each kind is what it says it is, so that a part no longer
        # parsed cannot pass as a chapter without one.
        if part and ('class="rs-sub"' not in main or secs[0] != "3"):
            bad.append(f"a chapter with a part draws its sections at h{secs[0]}, not h3 under the part's h2")
        if not part and secs[0] != "2":
            bad.append(f"a chapter without parts draws its sections at h{secs[0]}, not h2")
        said.append(f"{what}, its sections h{secs[0]}")
    assert not bad, "; ".join(bad)
    return "ok", "a Laws chapter " + " and ".join(said)


def _css_font_px(rules, chain, tokens, memo=None):
    """(px, selector, line) of the size app.css's cascade draws chain[0]'s
    text at, at the browser's 16px (_css_px): from the nearest element
    outward that a rule sizes, an em or % of its parent's; None for a size
    this cannot read."""
    for j in range(len(chain)):
        got = _css_inherited(rules, chain[j:], ("font-size",), memo)
        if not got:
            return 16.0, "the browser's", 0
        v, one, line, far = got["font-size"]
        px, how = _css_px(v, tokens)
        if px is not None:
            return px, one, line
        m = re.fullmatch(r"(\d*\.?\d+)(em|%)", v.strip())
        if not m:
            return None, one, line
        parent = _css_font_px(rules, chain[j + far + 1:], tokens, memo) if j + far + 1 < len(chain) \
            else (16.0, "the browser's", 0)
        if parent[0] is None:
            return parent
        return parent[0] * float(m.group(1)) / (100 if m.group(2) == "%" else 1), one, line
    return 16.0, "the browser's", 0


def _css_calc_px(value, em, look):
    """Pixels of a length as app.css writes one -- px, rem at the browser's
    16px, em of `em`, a var() through `look(name)` (None where nothing sets
    it), calc() and its + - * / -- or None where it cannot be read."""
    import ast as _ast
    v = value.strip()
    for _ in range(12):
        nxt = re.sub(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)",
                     lambda m: "(" + (look(m.group(1)) or m.group(2) or "nan") + ")", v)
        if nxt == v:
            break
        v = nxt
    v = re.sub(r"\bcalc\(", "(", v)
    v = re.sub(r"(\d*\.?\d+)(px|rem|em)\b",
               lambda m: f"({float(m.group(1)) * {'px': 1, 'rem': 16, 'em': em}[m.group(2)]!r})", v)
    try:
        tree = _ast.parse(v, mode="eval")
    except SyntaxError:
        return None
    ok = (_ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Constant, _ast.Add, _ast.Sub, _ast.Mult, _ast.Div,
          _ast.USub, _ast.UAdd)
    if not all(isinstance(n, ok) for n in _ast.walk(tree)):
        return None
    try:
        return float(eval(compile(tree, "<css>", "eval"), {"__builtins__": {}}))
    except (ZeroDivisionError, TypeError, ValueError):
        return None


@check("frontend", "a heading is drawn no smaller than the text it heads: a member's ATTENDANCE and BILLS, "
       "and a Laws chapter's parts, whose lines that wrap are 1.2 apart at the least and whose one line "
       "takes the room it took", needs=("build_rsa", "rsa", "shell"))
def _headings_outrank(B, RSA, S):
    """The accessibility sweep of the R1 preview (29 October 2026): a
    member's term at a glance headed its figures ATTENDANCE and BILLS at
    13px over labels at 16px, and a Laws chapter headed its parts ("HOURS OF
    POLLING", h2.rs-sub, the Constitution tab's h4s too) at 13px over the
    law at 16px. app.css's own rule (A HEADING OUTRANKS WHAT IT HEADS) is
    that no heading reads smaller than the text under it.

    So each is drawn where the pages draw it -- termGlance in node for a
    member with figures, in bills.html's #results; a chapter with a part
    through build_rsa's chapter page -- and the cascade's size for the
    heading (_css_font_px: font-size and the font shorthand's size, the
    tokens at the browser's 16px) must be at least the size of each run of
    text it heads: the figures' labels, and the law's paragraphs.

    A PART'S HEADING THAT WRAPS IS NOT CRAMPED (the review of the same
    day). h2.rs-sub kept the 13px label's line, calc(var(--t-label) * 1.3),
    16.9px under 16px text: 1.06, and RSA 126-A's long part heading ran six
    tight lines at 390. Its line must be 1.2 its size at the least, and a
    heading of one line must take the room it took on that line -- its
    padding above and margin below, each with half the line, what .75rem
    and half of 16.9px are (_css_calc_px reads the cascade's calc()) -- so
    that the page does not move."""
    css = _source("src/pages/app.css")
    rules = _css_screen_rules(css)
    tokens = _css_palette(css)["light"]
    memo = {}
    held_in = []
    _html_walk(_source("src/pages/bills.html"),
               element=lambda c: held_in.append(c) if "results" in c[0]["ids"] else None)
    assert held_in, "bills.html has no #results"
    glance = _app_js('scope.termGlance({term_figures:{"2025-2026":{bills_filed:12,prime:4,cosponsored:8,'
                     'bills_passed:3,became_law:2}},attendance:{"2025-2026":{attended:40,days:42,voted:300,'
                     'presided:0,conflict:1,roll_calls:310}}},"2025-2026")', names=("termGlance",))
    pages = []
    if glance is not None:
        pages.append(("a member's term at a glance (termGlance)", glance, held_in[0],
                      lambda c: c[0]["tag"] == "h3" and "mfgrp" in c[1]["classes"],
                      lambda c: c[0]["tag"] in ("span", "small", "p") and any(
                          "mf" in e["classes"] or "mfnone" in e["classes"] for e in c[:2])))
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA", "titleNumber", "url"]
    t = RSA.Table([dict(zip(cols, (
        "0", "LXIII", "659", "659-1", "TITLE LXIII ELECTIONS", "CHAPTER 659 ELECTION PROCEDURE",
        "Section 659:1 Hours of Polling.", "",
        "<center><h2>CHAPTER 659<br>ELECTION PROCEDURE</h2></center><h2>Hours of Polling</h2>",
        "<codesect> <br> I. The polls shall be open at least 8 hours. <br> II. The moderator shall "
        "announce the hours.</codesect>", "63", "LXIII\\659\\659-1.htm")))])
    data = {"bills": {}, "enacted": {}, "statute": {}, "asof": {"laws_through": 2025}}
    root = Path(tempfile.mkdtemp(prefix="gr-rsasub-"))
    try:
        (root / "idx").mkdir()
        page = B.chapter_page(S.template(Path("site")), t, data, B.Bills(root, "2025-2026"), "659",
                              "https://graniterecord.org")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    pages.append(("a Laws chapter's part (h2.rs-sub)", page, [],
                  lambda c: "rs-sub" in c[0]["classes"],
                  lambda c: c[0]["tag"] == "p" and len(c) > 1 and "rs-text" in c[1]["classes"]))
    bad, said = [], []
    for what, html, outer, is_head, is_body in pages:
        heads, bodies = [], []
        _html_walk(html, text=lambda d, c: (heads if is_head(c) else bodies if is_body(c) else []).append(c)
                   if d.strip() and c else None)
        assert heads and bodies, f"{what}: no heading or no text under it was drawn ({len(heads)}, {len(bodies)})"
        h = [_css_font_px(rules, c + outer, tokens, memo) for c in heads]
        b = [_css_font_px(rules, c + outer, tokens, memo) for c in bodies]
        if any(x[0] is None for x in h + b):
            bad.append(f"{what}: a size this cannot read ({[x for x in h + b if x[0] is None][:2]})")
            continue
        hmin, bmax = min(h), max(b)
        if hmin[0] < bmax[0]:
            bad.append(f"{what}: the heading is {hmin[0]:g}px ({hmin[1]}, app.css line {hmin[2]}) over text "
                       f"at {bmax[0]:g}px ({bmax[1]}, app.css line {bmax[2]})")
        said.append(f"{what} {hmin[0]:g}px over {bmax[0]:g}px")
        if "rs-sub" not in what:
            continue
        # Its line: the font shorthand's (which sets line-height, "normal"
        # where it names none) or line-height's, whichever rule wins.
        chain = heads[0] + outer
        won = _css_won(rules, chain)
        lead = won.get("line-height", (None,))[0]
        if "font" in won and (lead is None or (_css_specificity(won["font"][1]), won["font"][2])
                              >= (_css_specificity(won["line-height"][1]), won["line-height"][2])):
            m = re.search(r"/\s*((?:[\w.-]+\((?:[^()]|\([^()]*\))*\))|[^\s/]+)", won["font"][0])
            lead = m.group(1) if m else "normal"
        size = hmin[0]

        def look(name, won=won):
            return won[name][0] if name in won else tokens.get(name)
        line = (float(lead) * size if re.fullmatch(r"\d*\.?\d+", lead.strip())
                else _css_calc_px(lead, size, look))
        pad = _css_calc_px(won.get("padding-top", ("0",))[0], size, look)
        below = _css_calc_px(won.get("margin-bottom", ("0",))[0], size, look)
        was = _css_calc_px("calc(.75rem + var(--t-label) * 1.3 / 2)", size, look)
        if line is None or pad is None or below is None:
            bad.append(f"{what}: a line ({lead!r}), padding or margin this cannot read")
        elif line < 1.2 * size - 1e-6:
            bad.append(f"{what}: its lines are {line:g}px apart at {size:g}px, {line / size:.2f} (from {lead!r}): "
                       f"a heading that wraps is cramped")
        elif abs(pad + line / 2 - was) > .05 or abs(line / 2 + below - was) > .05:
            bad.append(f"{what}: a heading of one line moves the page: {pad:g}px + half of {line:g}px above its "
                       f"text's middle and {below:g}px under it, where it had {was:g}px each")
        else:
            said[-1] += f", its lines {line / size:.2f} apart"
    assert not bad, "a heading is drawn smaller than the text it heads: " + "; ".join(bad)
    return "ok", "; ".join(said) + ("" if glance is not None else " (node is not here for termGlance)")


# ---- the sitemap audit's fixes (16 October 2026) -------------------------------
#
# Four read-only audits of the sitemap and a skeptic for each finding, on 16
# October 2026. Each rule the fixes added is held here, and each check fails
# if its rule is undone.

def _rsa_fixture_table(RSA):
    """A statute table of two chapters: RSA 3-A, and RSA 404, the one chapter
    whose page is a folder's index.html (build_rsa.chapter_file)."""
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA", "titleNumber", "url"]
    return RSA.Table([dict(zip(cols, r)) for r in (
        ["1", "I", "3-A", "3-A-1", "TITLE I THE STATE AND ITS GOVERNMENT", "CHAPTER 3-A POET LAUREATE",
         "Section 3-A:1 Appointment.", "", "", "<codesect> The governor shall appoint.</codesect>", "1",
         "I\\3-A\\3-A-1.htm"],
        ["2", "XXXVII", "404", "404-1", "TITLE XXXVII INSURANCE",
         "CHAPTER 404 SAFETY FUNDS OF FIRE INSURANCE COMPANIES", "Section 404:1 Definitions.", "", "",
         "<codesect> In this chapter, see RSA 3-A:1.</codesect>", "37", "XXXVII\\404\\404-1.htm"])])


@check("build", "every chapter's row on /laws carries a plain link to its page, beside the row's "
       "summary, and RSA 404 is written everywhere at the address the host serves",
       needs=("build_rsa", "rsa", "shell", "check_site", "build_bill_pages"))
def _laws_rows_link_chapters(B, RSA, S, CS, BBP):
    """THE SITEMAP AUDIT'S FIRST FINDING (16 October 2026): /laws linked no
    chapter at all. The way to a chapter's page was written by LANDING_JS
    only once a reader opened its row, which a crawler never does, and 315 of
    the 1,786 chapter pages had no link from anywhere on the site. Each row
    carries a plain <a href> now, beside its <summary> so the row still opens
    on a click of the name; check_site.laws_linked refuses a site where a
    chapter in the sitemap has none.

    And /laws/404 (the fourth finding): the host answers it with a 308 to
    /laws/404/, where chapter_file writes the page, so its address is written
    with the slash wherever it is written -- the row's link, the sitemap, the
    page's canonical, og:url and citation, a section's link to it, and a bill
    page's link to the law (build_bill_pages.law_href)."""
    import contextlib
    import io
    t = _rsa_fixture_table(RSA)
    assert {"3-A", "404"} <= set(t.chapters), sorted(t.chapters)
    assert B.chapter_path("404") == "/laws/404/" and B.chapter_path("3-A") == "/laws/3-a", (
        f"chapter_path gives {B.chapter_path('404')!r} and {B.chapter_path('3-A')!r}, not the "
        "addresses the host serves (/laws/404/ and /laws/3-a)")
    assert B.href("404:1") == "/laws/404/#s1", f"a section of RSA 404 is linked at {B.href('404:1')}"
    data = {"bills": {}, "statute": {"404:1": ["3-A:1"]}, "enacted": {}, "asof": {"laws_through": 2025}}
    root = Path(tempfile.mkdtemp(prefix="gr-lawlinks-"))
    try:
        (root / "idx").mkdir()
        bills = B.Bills(root, "2025-2026")
        tmpl = S.template(Path("site"))
        page = B.landing_page(tmpl, t, data, "https://graniterecord.org", {}, {})
        ch404 = B.chapter_page(tmpl, t, data, bills, "404", "https://graniterecord.org")
        ch3a = B.chapter_page(tmpl, t, data, bills, "3-A", "https://graniterecord.org")
        plain = CS._SCRIPTS.sub(" ", page)
        for c in ("3-A", "404"):
            row = plain[plain.index(f'<li class="lw-ch" data-ch="{c}"'):]
            row = row[:row.index("</li>")]
            want = f'<a class="lw-go" href="{B.chapter_path(c)}">'
            assert want in row, f"Chapter {c}'s row on /laws carries no plain link to its page: {row[:300]}"
            summary = row[row.index("<summary>"):row.index("</summary>")]
            assert "<a " not in summary, (
                f"Chapter {c}'s link is inside its <summary>, so a click on its name leaves the "
                "page instead of opening the row")
        assert "> .lw-go" in B.LANDING_JS, (
            "the landing's script builds a chapter's address itself, not from the row's link, "
            "so RSA 404's loses its slash there")
        base = "https://graniterecord.org"
        for what, pat in (("canonical", r'<link rel="canonical" href="([^"]*)"'),
                          ("og:url", r'<meta property="og:url" content="([^"]*)"')):
            got = re.findall(pat, ch404)
            assert got == [f"{base}/laws/404/"], f"RSA 404's {what} is {got}, not {base}/laws/404/"
        cites = re.findall(re.escape(base) + r"/laws/404/?",
                           _cite_plain(ch404[ch404.index('class="citeforms"'):]))
        assert cites and all(u == f"{base}/laws/404/" for u in cites), (
            f"RSA 404's citation names {sorted(set(cites))}")
        assert 'href="/laws/404/#s1"' in ch3a, "RSA 3-A's Cited by does not link RSA 404:1 at /laws/404/"
        assert 'href="/laws/404#' not in ch404 + ch3a + page, "an address of RSA 404 without its slash is left"

        # check_site holds every chapter in the sitemap to a plain link on /laws.
        site = root / "site"
        site.mkdir()
        locs = [f"{base}/laws", f"{base}/laws/3-a", f"{base}/laws/404/"]
        (site / "laws.html").write_text(page, encoding="utf-8")
        errors = []
        with contextlib.redirect_stdout(io.StringIO()):
            CS.laws_linked(site, locs, base + "/", errors)
        assert not errors, f"check_site refuses a /laws that links every chapter: {errors}"
        (site / "laws.html").write_text(re.sub(r'<a class="lw-go"[^>]*>[^<]*</a>', "", page),
                                        encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            CS.laws_linked(site, locs, base + "/", errors)
        assert errors and "no plain link on /laws" in errors[0] and "/laws/404/" in errors[0], (
            f"check_site passes a /laws that links no chapter: {errors}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    saved = list(BBP._LAWS)
    BBP._LAWS[:] = [{"404", "3-A"}]
    try:
        assert BBP.law_href("RSA 404:5") == "/laws/404/#s5" and BBP.law_href("RSA 404") == "/laws/404/" \
            and BBP.law_href("RSA 3-A:1") == "/laws/3-a#s1", (
            "a bill page links RSA 404 at " + repr(BBP.law_href("RSA 404")))
    finally:
        BBP._LAWS[:] = saved
    css = _source("src/pages/app.css")
    assert re.search(r"\.lw-ch\{[^}]*position:relative", css) and \
        re.search(r"\.lw-go\{[^}]*position:absolute", css), (
            "app.css does not set the chapter's link at its row's right")
    return "ok", ("each chapter's row links its page beside the summary, check_site refuses a /laws "
                  "that does not, and RSA 404 is /laws/404/ in its link, canonical, og:url, citation "
                  "and a bill's link to it")


@check("build", "every chapter address is written by one rule, RSA 404's with its slash: the bill "
       "records, the guides, the app and the not-found page, and no file of the built fixture "
       "writes it without", needs=("build_rsa", "build_site_v2", "guides", "build_pages", "rsa"))
def _chapter_addresses_one_rule(BR, BSV, G, BP, RSA):
    """RSA 404 WITHOUT ITS SLASH, OUTSIDE build_rsa (the review of the sitemap
    fixes, 16 October 2026). build_rsa wrote /laws/404/ and seven other
    writers still built a chapter's address themselves: the bill record's
    statute links (build_site_v2.rsa_url), the guides' (guides.law_href) and
    the Laws section's on a guide's page, a law's follow address
    (build_feeds), the app's two (rsaHref, changedLine), and the not-found
    page's script that lower-cases a typed citation. The Python ones ask
    build_rsa.chapter_path; the scripts, which cannot, carry
    FOLDER_CHAPTERS as a list held to it here -- since 25 October 2026 the
    site search's too (find.js's Law row, which _find_laws runs for RSA
    404:5). And every file of the
    fixture site, whose statute table carries RSA 404, is read for an
    address of it without the slash, so a writer added later is caught by
    what it writes rather than by its name."""
    for ch in BR.FOLDER_CHAPTERS:
        assert BR.chapter_file(Path("laws"), ch).name == "index.html" \
            and BR.chapter_path(ch).endswith("/"), f"RSA {ch}'s file and address disagree"
    assert BR.chapter_path("91-A", "4") == "/laws/91-a#s4" and BR.chapter_path("404", "5") == "/laws/404/#s5"
    t = _rsa_fixture_table(RSA)
    keep = list(BSV._STATUTES)
    try:
        BSV._STATUTES[:] = [t]
        got = (BSV.rsa_url("404", "1"), BSV.rsa_url("404"), BSV.rsa_url("404", "99"), BSV.rsa_url("3-A", "1"))
    finally:
        BSV._STATUTES[:] = keep
    assert got == ("/laws/404/#s1", "/laws/404/", "/laws/404/", "/laws/3-a#s1"), (
        f"a bill record links RSA 404 at {got}")
    assert (G.law_href("RSA 404:1, I"), G.law_href("RSA 91-A:4")) == ("/laws/404/#s1", "/laws/91-a#s4"), (
        f"a guide links RSA 404:1 at {G.law_href('RSA 404:1, I')}")
    js = _source("src/pages/app.js")
    # And the site search's Law row (find.js, findLawRow; 25 October 2026).
    fjs = _source("src/pages/find.js")
    for where, text, pat in (("app.js", js, r"const LAW_FOLDERS=(\[[^\]]*\]);"),
                             ("find.js", fjs, r"const FLAW_FOLDERS=(\[[^\]]*\]);"),
                             ("build_pages.NOT_FOUND", BP.NOT_FOUND, r"var FOLDERS=(\[[^\]]*\]);")):
        m = re.search(pat, text)
        assert m and tuple(json.loads(m.group(1))) == tuple(BR.FOLDER_CHAPTERS), (
            f"{where}'s list of chapters in a folder is {m and m.group(1)}, not build_rsa.FOLDER_CHAPTERS "
            f"{BR.FOLDER_CHAPTERS}")
    said = []
    app = _app_js('[scope.rsaHref("404:1"), scope.rsaHref("404"), scope.rsaHref("91-A:4"), '
                  'scope.changedLine({changed:["404:2"]})]', names=("rsaHref", "changedLine"))
    if app is None:
        said.append("node not here for app.js")
    else:
        assert app[:3] == ["/laws/404/#s1", "/laws/404/", "/laws/91-a#s4"] and 'href="/laws/404/#s2"' in app[3], (
            f"app.js links RSA 404 at {app}")
    node = shutil.which("node")
    if node:
        script = re.search(r"<script>(.*?)</script>", BP.NOT_FOUND, re.S).group(1)
        prog = ("function go(p){var res=null;var location={pathname:p,search:'',hash:'',"
                "replace:function(u){res=u;}};var document={getElementById:function(){return null;}};"
                "(function(location,document){" + script + "})(location,document);return res;}\n"
                "process.stdout.write(JSON.stringify([go('/laws/404:5'),go('/laws/91-A:4'),go('/laws/91-A')]));\n")
        r = _node_file(node, prog, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, f"the not-found page's script did not run: {(r.stderr or '')[-300:]}"
        nf = json.loads(r.stdout)
        assert nf == ["/laws/404/#s5", "/laws/91-a#s4", "/laws/91-a"], (
            f"the not-found page sends /laws/404:5, /laws/91-A:4 and /laws/91-A to {nf}")
    else:
        said.append("node not here for the not-found page")
    absent = [x for x in CHAIN_NEEDS + ["build_rsa.py"] if not _paths.locate(x).exists()]
    if absent:
        return "ok", "the writers held; the fixture site was not built: not here, " + ", ".join(absent)
    shared, base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    bad, good = [], Counter()
    for p in site.rglob("*"):
        if p.suffix not in (".html", ".json", ".xml", ".txt", ".js") or not p.is_file():
            continue
        b = p.read_bytes()
        rel = p.relative_to(site).as_posix()
        bad += [f"{rel}: ...{b[max(0, m.start() - 60):m.end() + 10].decode('utf-8', 'replace')}"
                for m in re.finditer(rb"/laws/404(?![/\w-])", b)]
        if b.count(b"/laws/404/"):
            good[rel] += b.count(b"/laws/404/")
    assert not bad, f"{len(bad)} address(es) of RSA 404 without its slash in the built fixture: {bad[:3]}"
    for rel in ("laws.html", "laws/404/index.html", "laws/91-a.html", "sitemap.xml"):
        assert good.get(rel), f"the fixture's {rel} does not link RSA 404 at all, so this held nothing there"
    return "ok", (f"bill records, guides, app.js and the not-found page give /laws/404/; "
                  f"{sum(good.values())} addresses of it across {len(good)} built files, none without "
                  "its slash" + ("; " + "; ".join(said) if said else ""))
