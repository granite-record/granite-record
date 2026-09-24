#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.9
"""The committee a bill was referred to, read out of the docket.

    python3 referrals.py            # what it finds, by term, no network
    python3 referrals.py --check    # every expansion, and the evidence for it

WHY THIS EXISTS

Five terms -- 1989 to 1998, 8,525 bills -- had no committee at all on this
site, and the plan was to fetch one web page per bill to get one. The
committee was already on this disk: the General Court's own database dump
holds the docket back to 1989, and the clerk writes the referral into the
description of the introduction line.

    INTRODUCED AND REF TO EXEC & ADMIN     HJ 13 ,P 138
    Introduced 1/4/2012 and Referred to Judiciary; HJ 11, PG. 183
    PASSED AND REF TO FINANCE VV; HJ35,P943

34,000 referrals, 1989 to 2015, for no requests at all. This file is the one
reader of that text; nothing else parses a referral out of a docket line.

WHICH REFERRAL

The FIRST one per chamber -- the committee of referral, the one the bill's
own text prints as "REFERRED TO:". A bill can be re-referred, and the search
page's "Next/Last Comm" is the LAST one, in ONE chamber. So wherever a
chamber's docket names a referral, that is the committee published, read
from the same docket file the bill's history is narrated from
(from_dockets); where the chamber later vacated the referral and sent the
bill elsewhere, the committee it was sent to replaces the first, and where
it reconsidered the introduction and referred the bill again, the second
referral is the first that stood. Where the
docket names no referral in a chamber, the search page's committee stands.
build_data._pick_committee keeps the search page's name instead of the
docket's only where the docket's is a name the committee tables do not know
and the two are one committee written two ways.

THE ABBREVIATIONS ARE PROVEN, NOT GUESSED

The clerk of 1989 writes "EXEC DEPTS & ADMIN" and the clerk of 2011 writes
"Executive Departments and Administration", and both are in this corpus. So
every expansion below can be checked rather than believed: --check asserts
that each abbreviated form, once expanded, equals a string that appears
spelled out somewhere in the same 34,000 lines. Where no such evidence
exists the abbreviation is LEFT ALONE -- an honest "RES, REC & DEV" beats an
invented expansion, and the site renders a committee with no code as plain
text rather than as a link, so nothing breaks when a 1989 committee has no
page.

A BETTER AUTHORITY THAN THE CORPUS. The General Court publishes its own key to
these abbreviations at bill_status/legacy/bs2016/docket_abbrev.htm, kept here
as docket_abbrev.json. Where the key speaks it wins, and it settled two that
nothing in the corpus ever spelled out: JUD is Judiciary and Family Law (314
bills read "Judiciary and F L" before it) and ECON DEVEL is Economic
Development (130). The key is silent on "Corr and Cj" and on "Pub Prot".

A FOURTH WITNESS: the resolution each House adopts its rules by defines every
standing committee in one sentence -- "the Committee on Public Protection and
Veterans Affairs to consider all matters affecting public protection ..." --
and two of them are on this disk as bill text. That is the body naming its own
committees, it names 22 of them, and it settled "Pub Prot", which the docket
abbreviates nine ways across 1989-1996 and never once writes out. It also
corroborates Judiciary and Family Law independently of the key, and it names
"Corrections and Criminal Justice", which is the evidence "Corr and Cj" had
been waiting for.
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import names

SRC = Path("db/Docket.psv")

# The three ways a referral is written. Anchored at the start of the
# description so that "Committee Report: Refer to Interim Study" -- a
# disposition, not a committee -- cannot match.
#
# THE INTRODUCTION, IN EVERY SHAPE THE CLERKS WROTE IT. The first form of this
# pattern read "Introduced ... and ref(erred) to X" and nothing else, and every
# other shape fell through to the search page's "Next/Last Comm" -- the LAST
# committee -- or to no committee at all. Each alternative below is a shape
# the dockets on this disk really use:
#   "To Be Introduced 1/6/2010 and Referred to X"      pre-filed, 2009-2024
#   "Introduction and referring to X"                  the Senate of 1999-2000
#   "Introducing and referring to X"                   the Senate of 1999
#   "Introduced and ref X" / "Introduced & ref: X"     the House of 2005-2006
#   "04/09/91   INTRODUCED AND REF TO X"               a crossed-over bill's
#                                                      first line, 1991-1998
#   "Rules Comm Approved: Introduced 1/23/2008 and Ref to X"       2007-2008
#   "Introduced and Refered to X"                      misspelt, 1999-2006
#   "(JAN23)INTRODUCED AND REF TO X", "[APPROVED BY RULES] INTRODUCED ..."
#   "SEN X SUSP RULES FOR INTRO, MA 2/3VV; INTRODUCED AND REF TO X"
# Still anchored at the start, so "Committee Report: Refer to Interim Study"
# cannot match, and NOT_A_NAME still refuses a referral to no committee.
#
# "ref\w*+" is possessive and the committee must begin with a character that
# is not a space (\S), and cannot be the word "to" alone: a line that ends
# "INTRODUCED AND REF TO", with the committee on the clerk's next row,
# otherwise gave back the word "To" as a committee. \S also admits
# punctuation, which is harmless: clean() takes off a "<...>" note and
# NOT_A_NAME refuses what is left if it is empty.
INTRO = re.compile(
    r"^\s*(?:"
    r"\(?\d{1,2}/\d{1,2}/\d{2,4}\)?\s*"
    r"|\(?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s?\d{1,2}\)?\s*"
    r"|\[[^\]]*\]\s*"
    r"|rules\s+comm(?:ittee)?\s+approved:\s*"
    r"|[^;]{0,60}\bsusp\w*\b[^;]*;\s*"
    r")?"
    r"(?:to\s+be\s+)?introduc\w*\b.{0,40}?"
    r"(?:\band|&)\s+ref\w*+\.?(?:\s+\d{1,2}/\d{1,2}/\d{2,4})?"
    r"(?:\s*to\b|\s*(?-i:to)(?=[A-Z]))?\s*:?\s*"
    r"(?P<c>(?!to\s*$)\S.*)$", re.I)
PASSED = re.compile(
    r"^\s*passed(?:\s+with\s+am)?\s+and\s+ref(?:erred)?\.?\s+to\s+(?P<c>.+)$", re.I)
REREF = re.compile(r"^\s*re-?ref(?:erred)?\s+to\s+(?P<c>.+)$", re.I)

# A VACATE UNDOES THE REFERRAL BEFORE IT. "VACATED FROM JUDICIARY TO BANKS"
# means the House took the bill away from Judiciary and gave it to Banks, so
# Banks is the committee of referral and Judiciary never held it. 398 lines
# say so across 1989-2015, and none of the three patterns above matches any of
# them -- so until now the site published the committee the chamber had
# explicitly taken the bill away from.
#
# Not anchored at ^ like the others, because half of these name the mover
# first: "Sen. Cohen moved to Vacate from Education to Judiciary".
#
# THE ONE FORM THAT MEANS THE OPPOSITE. "Vacate Referral to Ways & Means" is
# a motion to vacate the referral TO Ways and Means -- that committee is the
# one being LEFT, and a pattern that takes the committee after "to" gets
# exactly the wrong answer. One line in the corpus is this shape (2007 HB829),
# which is few enough to be invisible in a spot check and quite enough to put
# a wrong committee on a bill's page. The lookahead refuses it outright:
# a vacate whose destination cannot be read is better than a confident
# inversion. HB829's destination is on the clerk's next row -- "Referred to
# Municipal & County Government" -- and _read_docket reads it from there (see
# VACATE_NEXT below).
VACATED = re.compile(r"\bvacat\w*\b(?!\s+referral\s+to)[^;]*?"
                     r"\bto\s+(?P<c>[^;]+)", re.I)
# The clerk's record that a motion was voted down: ML, "motion lost", and MF,
# "motion failed". Upper case only, as the clerks write them, so that the
# letters inside a committee's name cannot match.
LOST = re.compile(r"\b(?:ML|MF)\b")

# What follows the committee on the same line: the journal citation, a date
# in brackets, a parenthetical, or two spaces used as a column break.
# The citation also comes run together ("EDUC. HJ9   ,P89"), and a vote's
# fraction can follow the name ("Finance committee 2/3DIV(226-13)"); the
# first reached bill pages as a committee called "Educ. Hj9".
TAIL = re.compile(
    r"\s*[;(\[].*$|\s{2,}.*$|\s+[HS]J(?:\b|(?=\d)).*$|\s*,\s*P(?:G|g)?\.?\s*\d.*$"
    r"|\s*,\s*pg.*$|\s+\d{1,3}/+\d{1,4}.*$", re.I)
# The vote that carried the motion, written after the committee.
# The separator allows a full stop as well as a space or a comma, because the
# clerk writes "MA. VV" as often as "MA, VV" and "MA VV". Without the stop the
# repetition breaks at it and only the LAST token is taken off, so 2000 HB1573
# read "Vacate from Internal Affairs to Finance, MA. VV" and published a
# committee called "Finance, MA".
VOTE = re.compile(r"(?:[\s,.]*\b(?:VV|MA|MF|RC|DV|AA|OTPA?|ITL)\b)+[\s,.;]*$", re.I)
# "Rereferred to Committee" names no committee: it is back to the same one.
# "2nd reading" and "the table" are not committees either: a bill vacated to
# second reading has been taken OUT of committee and put on the chamber's
# calendar, which is the opposite of a referral. Two lines say exactly that
# -- "MOTION TO VACATE FROM FINANCE TO 2ND READING" -- and without this they
# would publish a committee named "2Nd Reading".
NOT_A_NAME = re.compile(r"^(?:committee|the committee|full committee|"
                        r"interim study|committee of conference|"
                        r"no committee assignment|"
                        r"(?:2nd|second|3rd|third)\s+reading|the table)$", re.I)

# The member who moved it, written after the committee on a vacate line:
# "VACATED TO JUDICIARY, REP POWERS MA VV". clean() says why this is here.
MOVER = re.compile(r"\s*,\s*(?:Rep|Sen|Senator|Representative)s?\b.*$", re.I)
# The clerks write both "Ways & Means" and "Ways and Means" for the same
# committee in the same year. This is a spelling, not an abbreviation, so it
# needs no evidence -- but it is the single largest source of a committee
# appearing twice in a count, and it runs after the expansions below so that
# their patterns can still match on the ampersand.
AMP = re.compile(r"\s*[&+]\s*")

# Expansions, each verified by --check against a spelled-out form in the same
# corpus. A phrase is tried before its words so that "H & HS" becomes Health
# and Human Services rather than two lone letters.
PHRASES = [
    # ADM as well as ADMIN: the clerk of 1989 wrote "EXEC DEPTS & ADM",
    # which reached the site as "Exec Depts and Adm". EXECUTIVE and the
    # clerk's "EXECTIVE" as well as EXEC, a singular DEPT as well as DEPTS,
    # the "and" optional ("Exec Depts Admin"), and ADMINSTRATION -- which is
    # how the House wrote its own committee's name five times -- because each
    # of those reached the site abbreviated or misspelt.
    # "Ex." as well, which one clerk of 2000 used: "Ex. Dept. and Admin". It
    # is only allowed to mean Executive here because DEPT and ADM have to
    # follow it, so there is nothing else it could be short for.
    (r"\bEX(?:EC(?:UTIVE|TIVE)?)?\.?\s*DEPTS?\.?\s*(?:(?:&|\+|AND)\s*)?"
     r"ADM(?:IN|INISTRATION|INSTRATION)?\.?\b",
     "Executive Departments and Administration"),
    (r"\bMUN(?:ICIPAL)?\.?\s*(?:&|/|\+|AND)?\s*C(?:N?TY|OUNTY)\.?\s*"
     r"(?:(?:&|\+|AND)\s*)?GOVT?\.?\b",
     "Municipal and County Government"),
    (r"\bCRIM\.?\s*JUST\.?\s*(?:&|\+|AND)\s*"
     r"P(?:\.?\s*SFTY|SAFETY|UB\.?\s*SAFETY)\.?\b",
     "Criminal Justice and Public Safety"),
    (r"\bRES\.?\,?\s*REC\.?\,?\s*(?:&|\+|AND)?\s*DEV\.?\b",
     "Resources, Recreation and Development"),
    (r"\bENV\.?\s*(?:&|\+|AND)\s*AGRIC?\.?\b", "Environment and Agriculture"),
    (r"\bWAYS\s*(?:&|\+)\s*MEANS\b", "Ways and Means"),
    (r"\bCON\.?\s*(?:&|\+|AND)\s*STAT\.?\b",
     "Constitutional and Statutory Revision"),
    (r"\bSCI(?:ENCE)?\.?\s*[,/]?\s*TECH\.?\s*(?:&|\+|/|AND)?\s*EN(?:ERGY)?\b",
     "Science, Technology and Energy"),
    (r"\bPUB\.?\s*WORKS\b", "Public Works"),
    # AFFS as well as AFFAIRS. "Internal Affs" and "Public Affs" were on 24
    # pages, and are the same two committees these patterns already cover.
    (r"\bPUB(?:LIC)?\.?\s*AFF(?:AIR)?S\.?\b", "Public Affairs"),
    # TWO SENATE COMMITTEES WHOSE NAMES END IN "INTERNAL AFFAIRS". The pattern
    # for Internal Affairs was not anchored, so it found those two words inside
    # both longer names and returned the shorter one: S50 Election Law and
    # Internal Affairs (2007-2008) and S40 Rules, Enrolled Bills and Internal
    # Affairs (2013-2016) reached 38 bill cards and 111 histories as "Senate
    # Internal Affairs", a committee none of those terms had. (S50 had the
    # same name again in 2017-2018. That term was unaffected only while no
    # docket line of 2017 or later reached this table; from_dockets now sends
    # every term's docket through it, so 2017-2018 depends on these entries
    # exactly as 2007-2008 does.) Each name maps
    # to itself here, ahead of that pattern, so the spelling without the
    # comma, and the 2015-2016 lines that carry "by the necessary 2/3 vote,
    # Pursuant to Senate Rule 3-26" after the name, come out as the committee
    # too.
    (r"\bELEC(?:TION)?\.?\s*LAW\s*(?:&|\+|AND)\s*INTERNAL\s*AFF(?:AIR)?S\.?\b",
     "Election Law and Internal Affairs"),
    (r"\bRULES\s*,?\s*ENROLLED\s*BILLS\s*,?\s*(?:&|\+|AND)\s*"
     r"INTERNAL\s*AFF(?:AIR)?S\.?\b",
     "Rules, Enrolled Bills and Internal Affairs"),
    # And refused straight after the word "and" or an ampersand: "... and
    # Internal Affairs" is the tail of a longer name or half of a joint
    # referral, and in neither case the committee called Internal Affairs
    # alone. preflight's full-name check is the wider guard: it fails if any
    # entry here turns a committee's full name into a different committee.
    (r"(?<!\bAND\s)(?<!&\s)\bINTERNAL\s*AFF(?:AIR)?S\.?\b", "Internal Affairs"),
    (r"\bELEC\.?\s*LAW\b", "Election Law"),
    (r"\bAPPROP\.?\b", "Appropriations"),
    (r"\bTRANS\.?$", "Transportation"),
    # Added after the first build put these on the site abbreviated. Each is
    # proven the same way -- --check finds it spelled out in the docket or in
    # a bill's own text -- and the ones that are NOT spelled out anywhere are
    # deliberately absent: "Child Y&Jj" and "Pub Instit" keep the clerk's
    # letters, because a plausible expansion of a committee name is still an
    # invented one. ("Pub Instit" is two referrals, and the two candidates on
    # this disk -- Public Institutions, Health and Human Services, and State
    # Institutions and Housing -- are different committees.)
    #
    # "Corr & Cj" came off that list on the same evidence as "Pub Prot": the
    # rules resolution names "the Committee on Corrections and Criminal
    # Justice". 159 referrals on 152 pages, which read "the House Corr and Cj
    # committee" before it.
    (r"\bCORR\.?\s*(?:&|\+|AND)\s*CJ\b", "Corrections and Criminal Justice"),
    #
    # "Pub Prot" came off that list on evidence rather than on a hunch. The
    # docket never writes it out: a search of all 584 referral strings for
    # "PROTECTION" finds only
    # Consumer Protection, which is a different committee, and one
    # "PUB PROTECTION" of 1991, which is still abbreviated. The bills' own
    # text does write it out, and writes it out as a charter:
    # legislation/1995/HR0001.html -- the House resolution adopting its rules
    # -- names "Public Protection and Veterans Affairs to consider all
    # matters affecting public protection including, but not limited to, law
    # enforcement and the training of law enforcement officers", and
    # legislation/2008/HR0020.html names it again. The docket's own ladder of
    # spellings runs to the same place across 1989-1996: PUB PROT (82),
    # PUBLIC PROT (40), PUB PROTECT (6), PUB PROTEC, PUB PROTECTION, and
    # PUBLIC PROT & VETS AFFS (15), which carries the second half of the name
    # the resolution states in full. 148 referrals on 104 pages.
    (r"\bPUB(?:LIC)?\.?\s*PROT(?:EC|ECT|ECTION)?\b",
     "Public Protection and Veterans Affairs"),
    # Same evidence, different committee: legislation/1993/HBI0002.html
    # writes "Commerce, Small Business and Consumer Affairs", which is this
    # abbreviation element for element and adds nothing to it. By 1995 the
    # House had renamed it -- legislation/1995/HR0001.html has "Commerce,
    # Small Business, Consumer Affairs and Economic Development" -- and the
    # abbreviation is only ever written in 1990, before that, so the
    # three-part name is the one this era means. 49 referrals.
    (r"\bCOMMERCE\s*,?\s*SM\.?\s*BUS\.?\s*(?:&|\+|AND)\s*CONS\.?\s*AFFS?\.?\b",
     "Commerce, Small Business and Consumer Affairs"),
    # Spelled out 258 times in the docket itself, and in the same 1995
    # resolution. SRVCS as well as SVCS: "LABOR, INDUS & REHAB SRVCS" is the
    # clerk of one year dropping a different letter.
    (r"\bLABOR\s*,?\s*INDUS(?:TRIAL)?\.?\s*(?:&|\+|AND)\s*"
     r"REHAB(?:ILITATIVE)?\.?\s*S(?:E?RVI?CE?S|VCS|RVCS)\.?\b",
     "Labor, Industrial and Rehabilitative Services"),
    (r"\bHEALTH\s*[,]?\s*(?:HUMAN\s*)?(?:SVCS?|HS)\s*(?:&|\+|AND)\s*EA\b",
     "Health, Human Services and Elderly Affairs"),
    # HUM for HUMAN, SRVCS for SERVICES and ELD AFFS for ELDERLY AFFAIRS, all
    # in one string: "Health, Hum Srvcs and Eld Affs", on 34 pages.
    (r"\bHEALTH\s*,?\s*HUM(?:AN)?\.?\s*S(?:E?RVI?CE?S|VCS|RVCS)\.?\s*"
     r"(?:&|\+|AND)\s*(?:ELD(?:ERLY)?\.?\s*AFF(?:AIR)?S|EA)\.?\b",
     "Health, Human Services and Elderly Affairs"),
    (r"\bHEALTH\s*,\s*HUMAN\s*SVCS?\.?\s*(?:&|\+|AND)\s*ELDERLY\s*AFFAIRS\b",
     "Health, Human Services and Elderly Affairs"),
    # INSTIT as well as INST and INSTITUTIONS: "Pub. Instit. H and Hs" broke
    # this pattern on the two letters between them, and SB 201 of 1997 named
    # its committee that way on the site.
    (r"\bPUB(?:LIC)?\.?\s*INST(?:IT)?(?:UTIONS)?\.?\s*[,/]?\s*H(?:EALTH)?\s*"
     r"(?:&|\+|AND)\s*H(?:UMAN\s*)?S(?:ERVICES)?\b",
     "Public Institutions, Health and Human Services"),
    (r"\bWILDLIFE\s*(?:&|\+|AND)\s*REC\.?$", "Wildlife and Recreation"),
    (r"\bLEG\.?\s*ADMIN\.?\b", "Legislative Administration"),
    # LOCAL as well as LOC. The House's Committee on Regulated Revenues, named
    # so in legislation/1995/HR0001.html, the rules resolution of 1995, is the
    # Committee on Local and Regulated Revenues in legislation/1997/HR0001.html.
    # "LOCAL & REG REV" (1997 HB776) missed this pattern and fell to the next
    # one, which put the older name on a 1997 bill. The next one is
    # anchored at the start for the same reason: "REG REV" is only Regulated
    # Revenues when nothing comes before it.
    (r"\bLOC(?:AL)?\.?\s*(?:&|\+|AND)\s*REG\.?\s*REV\.?\b",
     "Local and Regulated Revenues"),
    (r"^REG\.?\s*REV\.?$", "Regulated Revenues"),
    # REL optional: "St-Fed and Vets Affs" drops it, and there is no other
    # State-Federal committee for it to be confused with.
    (r"\bST\.?[- ]?FED\.?\s*(?:REL\.?\s*)?(?:&|\+|AND)\s*VETS?\.?\b",
     "State-Federal Relations and Veterans Affairs"),
    (r"\bCHILD(?:REN)?\.?\s*(?:&|\+|AND)\s*FAM(?:ILY)?\.?\s*LAW\b",
     "Children and Family Law"),
    # The name with no "and Administration" after it, however the clerk spelt
    # the first word -- "Exective Dept" included, which is one referral and
    # was one page.
    (r"\bEXEC(?:UTIVE|TIVE)?\.?\s*DEPTS?\.?$",
     "Executive Departments and Administration"),
    (r"\bEXEC\.?\s*(?:&|\+|AND)\s*ADMIN\.?\b",
     "Executive Departments and Administration"),
    # From the General Court's own key (docket_abbrev.json): JUD is Judiciary
    # and Family Law, ECON DEVEL is Economic Development. Both stood as the
    # clerk's letters until the source said otherwise -- which was the right
    # rule, and a published key is the thing that lifts it.
    (r"\bJUDICIARY\s*(?:&|\+|AND)\s*F\.?\s*L\.?$", "Judiciary and Family Law"),
    (r"\bECON\.?\s*DEV(?:EL)?\.?$", "Economic Development"),
    # THE HEARING LINE'S SHORTHAND. A hearing of 1989-1998 names its committee
    # after FOR:, in letters the referral line never uses --
    # "HEARING JAN28 08:30 RM104,LOB FOR: ED+A" -- and 9,094 rows of
    # proceedings.csv named no committee the site has, "Ed and a" among them
    # 598 times. Each entry below is in the General Court's key, and each is
    # anchored to the whole string, because the key also holds entries that
    # are only right for one era: PUBLIC WKS is "Public Works and Highways",
    # the committee's name today, where the clerk of 1990 meant "Public
    # Works". None of those is here.
    #
    # The proof is on the same bill. For every bill whose hearing line uses
    # one of these, the referral line of the same bill in the same chamber
    # was read, and it spells the expansion out: ED&A 601 of 630 bills, in
    # both chambers; M&CG 253 of 261; RR&D 174 of 184; E&A 127 of 132; LABOR
    # 178 of 186; HHS&EA 13 of 13; ST&E 9 of 9; CAP BUDGET 36 of 44, the rest
    # a second referral to Transportation. What does not agree is a second
    # committee -- Finance, Appropriations -- that the bill went to later.
    # SB 143 of 1993 is the pattern: "REF TO EXEC DEPTS+ADMIN", then
    # "HEARING ... FOR: ED+A".
    #
    # Left as the clerk wrote them, and why: "ST-FED" (113 hearings) and "ST
    # INST" (118) are not in the key, and each committee changed its name
    # inside these years, so which name a given year means is a guess.
    (r"^E\.?\s*D\.?\s*(?:&|\+|AND)\s*A\.?$", "Executive Departments and Administration"),
    (r"^E\.?\s*(?:&|\+|AND)\s*A\.?$", "Environment and Agriculture"),
    (r"^R\.?\s*R\.?\s*(?:&|\+|AND)\s*D\.?$", "Resources, Recreation and Development"),
    (r"^M\.?\s*(?:&|\+|AND)\s*C\.?\s*G?\.?$", "Municipal and County Government"),
    (r"^S\.?\s*T\.?\s*(?:&|\+|AND)\s*E\.?$", "Science, Technology and Energy"),
    (r"^H\.?\s*H\.?\s*S\.?\s*(?:&|\+|AND)\s*E\.?\s*A\.?$",
     "Health, Human Services and Elderly Affairs"),
    # LABOR alone is the clerk's name for the committee from 1989 to 2008 --
    # 629 lines, every one in the House, where it has one Labor committee --
    # and "LABOR IND REH" is the same name cut short twice.
    (r"^LABOR(?:\s*,?\s*IND\.?\s*(?:&|\+|AND)?\s*REH\.?)?$",
     "Labor, Industrial and Rehabilitative Services"),
    # TRANS is above; these are the lengths the clerks stopped typing at.
    (r"^TRANSP(?:O|OR|ORT|ORTATI)?\.?$", "Transportation"),
    (r"^CAP(?:IT[AO]L)?\.?\s*BUDGET$", "Capital Budget"),
    # THE SAME PROOF, a second pass. Each is the whole string a hearing line
    # wrote, and each agrees with the referral line of the same bill in the
    # same chamber: EDUC 134 of 145 House bills and 110 of 114
    # Senate ones; W&M 73 of 77 in the Senate; CRIM JUST 73 of 83; SCIENCE 102
    # of 106; ENV & AG 35 of 36; INSUR 133 of 137; ENVIRON 79 of 80; PUB WKS 58
    # of 60; PUB INST 187 of 207 (the rest Finance, which a bill went to next).
    #
    # Left alone, and why. JUD is Judiciary in the Senate (139 of 140) and
    # Judiciary and Family Law in the House of 1995-1998, and WILDLIFE is
    # Wildlife and Recreation in the Senate and its own name in the House:
    # this function is not told the chamber, so either expansion would be
    # wrong for one of them. HEALTH agrees 173 times of 250. CHILD Y&JJ, DEV
    # REC & ENV and F&G & REC are spelled out nowhere on this disk. PUB INSTIT
    # stays as the note above explains; the anchor keeps these from reaching it.
    (r"^EDUC\.?$", "Education"),
    (r"^W\s*(?:&|\+)\s*M$", "Ways and Means"),
    (r"^CRIM\.?\s*JUST\.?$", "Criminal Justice and Public Safety"),
    (r"^SCIENCE$", "Science, Technology and Energy"),
    (r"^ENV\.?\s*(?:&|\+|AND)\s*AGR?\.?$", "Environment and Agriculture"),
    (r"^INSUR\.?$", "Insurance"),
    (r"^ENVIRON\.?$", "Environment"),
    (r"^PUB\.?\s*WKS\.?$", "Public Works"),
    (r"^PUB(?:LIC)?\.?\s*INST\.?$", "Public Institutions, Health and Human Services"),
]


def _key(s):
    """A committee name reduced to what does not vary between clerks.

    "Wildlife & Recreation" and "Wildlife and Recreation" are one committee,
    so the ampersand and the word it stands for are both dropped, along with
    punctuation and case. Used only to ask whether a source spells a name
    out; never to decide what to publish.
    """
    words = re.findall(r"[a-z]+", AMP.sub(" and ", s).lower())
    return "".join(w for w in words if w != "and")


def clean(s):
    """The committee, with what the clerk wrote after it taken off."""
    # "Introduced and ref Education <W & M>": the angle brackets are the
    # clerk's note of a SECOND committee the bill is expected to go to, not
    # part of the first one's name. Left in, "Education <W and M>" matched no
    # committee and the search page's last committee -- Ways and Means -- won.
    # A note at the START is different: "<JOINT> APPROP AND WAYS & MEANS"
    # (1989 HB764) is a joint referral to two committees, and the two spaces
    # it leaves are TAIL's column break, so it reads as no committee rather
    # than as one of the two -- which is what it read as before.
    s = re.sub(r"\s*<[^>]*>", " ", s)
    # "Ways &  Means": two spaces after an ampersand are not the column break
    # TAIL takes them for, and without this the committee read "Ways".
    s = re.sub(r"\s*&\s*", " & ", s)
    s = TAIL.sub("", s)
    s = VOTE.sub("", s)
    # AND THE MEMBER WHO MOVED IT. "VACATED TO JUDICIARY, REP POWERS MA VV"
    # leaves "JUDICIARY, REP POWERS" once the vote is stripped, and the site
    # would publish a committee called "Judiciary, Rep Powers", which matches
    # no committee page and reads as nonsense. Three such values are in
    # data/bills.json today -- "Public Works, Rep G Chandler" among them --
    # and the vacate lines this module now reads would have added about forty
    # more, because naming the mover is the house style on a vacate motion.
    #
    # Anchored to a comma and an honorific so it cannot eat a committee whose
    # own name has a comma in it: "Health, Human Services and Elderly Affairs"
    # and "Resources, Recreation and Development" both survive, because what
    # follows their comma is not Rep or Sen.
    s = MOVER.sub("", s)
    s = re.sub(r"[\s.,;:&/+-]+$", "", s).strip()
    return "" if NOT_A_NAME.match(s) else s


def expand(s):
    """An abbreviated committee written out, where the expansion is proven."""
    for pat, full in PHRASES:
        if re.search(pat, s, re.I):
            return full
    return s


def committee(desc):
    """The committee named by one docket description, or "".

    names.committee is the site's one place for turning a shouted name into a
    name, and it runs here rather than only at render time so that the CSV
    exports and data/bills.json carry "Judiciary" as well: the docket writes
    both JUDICIARY and Judiciary across the years, and left alone they are
    two committees in every count.
    """
    for rx in (INTRO, PASSED, REREF):
        m = rx.match(desc or "")
        if m:
            # names.committee first, then the ampersand: it only unshouts a
            # name that is at least 90% upper case, and substituting a
            # lower-case "and" into "JUDICIARY & F L" first drops it below
            # that threshold and leaves the shout standing.
            return AMP.sub(" and ", names.committee(expand(clean(m.group("c")))))
    return ""


def vacated(desc):
    """The committee a vacate motion moves the bill TO, or "".

    See VACATED above for the shape, and for the one form that means the
    opposite and is refused rather than guessed at.

    A MOTION THAT LOST MOVED NOTHING. "REP HAETTENSCHWILLER MOVED TO VACATE
    TO HEALTH, ML RC(167-178)" (1995 HB54) is the House voting NOT to vacate:
    Finance kept the bill and reported it. Read as a vacate, it put a
    committee called "Health, Ml" on the page, and HB55's twin "Ed and a,
    Ml". ML and MF are the clerk's "motion lost" and "motion failed"; these
    two rows are the only ones in the dockets where either sits on a vacate
    this pattern reads.
    """
    m = VACATED.search(desc or "")
    if not m or LOST.search(desc):
        return ""
    return AMP.sub(" and ", names.committee(expand(clean(m.group("c")))))


def from_docket(path=SRC, lo=1989, hi=2015):
    """{(session year, bill): {body: committee}} -- the FIRST per body.

    db/Docket.psv alone, keyed on the session year. The site no longer reads
    this: from_dockets below reads every term's own docket. It stays as the
    reader of the database dump by itself.

    The docket arrives in the order the clerk wrote it, so the first referral
    a body records is the committee of referral. setdefault is what keeps it
    first; a re-referral later in the same body does not replace it.

    A VACATE IS THE EXCEPTION, and it is why this is not a pure setdefault.
    The chamber undoing a referral and sending the bill elsewhere makes the
    second committee the one that held it -- so a vacate REPLACES what is
    standing, where every other later line is ignored. 398 lines across
    1989-2015 do this, and reading them was the difference between the site
    naming the committee that heard the bill and naming the one the chamber
    had taken it away from.

    The order in the file is the clerk's order, so a vacate always arrives
    after the referral it undoes, and the last vacate wins over an earlier
    one. That is the right answer for the handful of bills vacated twice.
    """
    out = collections.defaultdict(dict)
    if not Path(path).exists():
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 7 or not p[0].isdigit():
                continue
            year = int(p[0])
            if not lo <= year <= hi:
                continue
            key, body = (p[0], p[4].strip()), p[5].strip()
            v = vacated(p[6])
            if v:
                out[key][body] = v
                continue
            c = committee(p[6])
            if c:
                out[key].setdefault(body, c)
    return out


def _term(year):
    """"2023" or "2024" -> "2023-2024": the two-year term a session year is in."""
    y = int(year)
    s = y if y % 2 else y - 1
    return f"{s}-{s + 1}"


def term_dockets():
    """{term: path} -- the one docket per archived term the site narrates.

    The same choice narrate_archive.dockets() makes, and deliberately so: the
    committee row and the history under it are read from the same file, so
    the page cannot say "referred to the Special Committee on Housing" in its
    history and name a Senate committee in its header.
    """
    import narrate_archive
    return narrate_archive.dockets()


# A BARE "Referred to X". See _read_docket for when it counts.
PLAIN = re.compile(r"^\s*referred\s+to\s+(?P<c>.+)$", re.I)
# Anything that means the committee has already started on the bill.
HEARD = re.compile(r"\bhearing\b|\bexec(?:utive)?\s+session\b|committee\s+report",
                   re.I)

# THREE THINGS A ROW CAN DO TO THE REFERRAL BEFORE IT, each found by setting
# every changed committee beside the committee that held the bill's first
# hearing in proceedings.csv. Each is a small, written-down shape rather than
# a judgement, and _read_docket applies them.
#
# 1. A VACATE WRITTEN OVER TWO ROWS. The motion on one row, the destination
#    on the chamber's next:
#      "Vacate (Rep Kotowski): MA VV; HJ 31 , PG. 1477"
#      "Referred to Commerce and Consumer Affairs; HJ 31 , PG. 1477"  2015 SB64
#      "Vacated from Ways and Means; HJ 19, pg.390"
#      "Referred to Commerce; HJ 19, pg.390"                          2007 HB613
#      "Sen. Burling Moved HB 866 be Vacated; SJ 15, Pg.329"
#      "From ED&A to Public and Municipal Affairs, MA, VV; SJ 15, Pg.329"
#      "Sen. Cohen moved to Vacate from the Executive Departments and
#       Administration to" / "the Public Institutions, Health and Human
#       Services Committee.  MA, VV."                                 1999 SB108
#    vacated() reads nothing on the first row, and on the second a "Referred
#    to" arrives after the first referral and is outranked by it -- so the
#    page named the committee the chamber had taken the bill AWAY from:
#    Health, Human Services and Elderly Affairs for SB 64, which Commerce and
#    Consumer Affairs heard in LOB 302. So a vacate row that names no
#    destination lets the chamber's next row name one, in these shapes and no
#    others. A row ending in "to" hands over the whole of the next row. A
#    vacate to the table, to a reading or off a calendar -- "Vacated and Laid
#    on Table" and "Vacated from Committee and Laid on Table", 311 rows of
#    2019-2020 -- sent the bill to no committee, so it hands over nothing: a
#    later "Referred to Finance" must not become the referral.
VACATE_WORD = re.compile(r"\bvacat", re.I)
NOT_TO_A_COMMITTEE = re.compile(r"\btable\b|\breading\b|\bcalendar\b", re.I)
VACATE_NEXT = re.compile(
    r"^\s*(?:(?:re-?)?ref(?:erred)?\.?\s+to|from\b[^;]*?\bto|to)\s+(?P<c>[^;]+)",
    re.I)
DANGLING = re.compile(r"\bto\s*$", re.I)
#
# 2. A CHAMBER TAKING BACK ITS OWN REFERRAL. On 31 May 2001 the Senate
#    carried "Reconsideration of Introduction and Committee Referral" on five
#    House bills and introduced each again in January 2002: HB 162 went from
#    Public Affairs to Education, which heard it on 6 February 2002, and HB
#    658 from Executive Departments and Administration to Public
#    Institutions, Health and Human Services. The first referral was undone,
#    so the next one is the first. A motion that lost -- "RECONSIDER
#    INTRODUCTION, ML VV" (1993 SB668) -- undoes nothing.
RECONSIDERED = re.compile(
    r"\breconsider\w*\s+(?:(?:of|for|on)\s+)?(?:the\s+)?introduc", re.I)
#
# 3. AN INTRODUCTION FILED UNDER THE OTHER CHAMBER. The database files a few
#    Senate introductions under the House: SB 369 of 2000's first row is
#    body H, "Introduced and Ref. to Insurance; SJ Convening Day, Pg.10" --
#    the Senate Journal -- and the House's own "Introduced and ref to
#    Commerce; HJ18, p479" comes a month later. Read as filed, the House
#    committee was Insurance, which never held it; Commerce heard it on 11
#    April. So a bill's FIRST row, when it is an introduction filed under the
#    chamber its number does not name and it cites only the journal of the
#    chamber its number does, is that chamber's row. Both conditions are
#    needed: HCR 25 of 1996's House introduction cites "SJ9" and is the
#    House's own (its number is the House's, and the House heard it), and HB
#    1171 of 1996's Senate introduction cites "HJ9" and is the Senate's (it
#    is not the bill's first row). Eight Senate bills of 1991-1992 and SB 369
#    of 2000 are this shape; a CACR's number names no chamber, so none is
#    moved.
NUMBERED = re.compile(r"^([HS])(?:B|R|CR|JR|A)\d", re.I)


def _journal(desc, body):
    """Whether a docket description cites that chamber's journal (HJ or SJ)."""
    return re.search(r"\b%sJ(?:\b|(?=\d))" % body, desc, re.I) is not None


def _filed_under(bill, body, desc):
    """The chamber a bill's FIRST row belongs to: see 3 above."""
    m = NUMBERED.match(bill)
    if not m or not INTRO.match(desc):
        return body
    own = m.group(1).upper()
    if body in ("H", "S") and body != own and _journal(desc, own) \
            and not _journal(desc, body):
        return own
    return body


def _destination(text):
    """The committee a two-row vacate's second row names, or "": see 1 above."""
    s = re.sub(r"^\s*(?:the\s+)?(?:committee\s+on\s+)?", "", text, flags=re.I)
    s = re.sub(r"\s+committee$", "", clean(s), flags=re.I)
    return AMP.sub(" and ", names.committee(expand(s))) if s else ""


def _own_rows(path, term, lsr_of=None):
    """[((term, bill), body, description)] -- each bill's OWN rows, in order.

    ONE BILL NUMBER CAN CARRY TWO MEASURES. Resolutions and CACRs can be
    numbered again in a term's second year, so 50 bill numbers across the
    archived dockets carry rows under two or more LSRs in one term, 48 of
    them with an introduction under more than one -- two different measures
    under one number: SCR 2 of 1989-1990 is LSR 0564 in 1989 and the Fast
    Day resolution, LSR 2730, in 1990; CACR 20 of 2007-2008 is the Senate's
    LSR 1342 and, on one House row, LSR 2023. The database also files a few
    rows under a bill number with another bill's LSR. So a bill's rows are
    the ones whose LSR is the record's own (lsr_of, {(term, bill): lsr});
    where the record names none, or names one that no row carries, the LSR
    most of the bill's rows carry.
    """
    rows = []
    lsrs = collections.defaultdict(collections.Counter)
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\r\n").split("|")
            if len(p) < 7 or not p[0].strip().isdigit():
                continue
            if _term(p[0].strip()) != term:
                continue
            # The body is upper-cased: 65 rows of 1999-2002 write "s".
            key = (term, p[3].strip().upper())
            lsr = p[1].strip().lstrip("0")
            lsrs[key][lsr] += 1
            rows.append((key, lsr, p[4].strip().upper(),
                         "|".join(p[5:-1]) if len(p) > 7 else p[5]))
    want = {}
    for key, n in lsrs.items():
        own = str((lsr_of or {}).get(key) or "").strip().lstrip("0")
        want[key] = own if own in n else n.most_common(1)[0][0]
    return [(key, body, desc) for key, lsr, body, desc in rows
            if lsr == want[key]]


def _read_docket(path, term, lsr_of=None):
    """({(term, bill): {body: committee}}, {(term, bill): body}) from one file.

    The first: the FIRST referral per body, which a vacate replaces -- the
    rule from_docket states -- including a vacate written over two rows, and
    which a carried reconsideration of the introduction clears. The second:
    the body of the bill's first row, which is the chamber it began in. A
    first row filed under the wrong chamber counts as the right one's for
    both. The three rules are numbered above VACATE_WORD.
    """
    refs = collections.defaultdict(dict)
    began = {}
    heard = set()
    seen = set()
    pending = {}    # (key, body) -> True if the vacate row ended in "to"
    for key, body, desc in _own_rows(path, term, lsr_of):
        if key not in seen:
            seen.add(key)
            body = _filed_under(key[1], body, desc)
        if body in ("H", "S"):
            began.setdefault(key, body)
        dangling = pending.pop((key, body), None)
        if dangling is not None:
            m = None if dangling else VACATE_NEXT.match(desc)
            dest = (_destination(desc) if dangling and not HEARD.search(desc)
                    else _destination(m.group("c")) if m else "")
            if dest:
                refs[key][body] = dest
                continue
        if RECONSIDERED.search(desc) and not LOST.search(desc):
            refs.get(key, {}).pop(body, None)
            continue
        v = vacated(desc)
        if v:
            refs[key][body] = v
            continue
        if VACATE_WORD.search(desc) and not VACATED.search(desc) \
                and not LOST.search(desc) and not NOT_TO_A_COMMITTEE.search(desc):
            pending[(key, body)] = DANGLING.search(desc) is not None
        c = committee(desc)
        if not c and (key, body) not in heard:
            # A BARE "Referred to X", before anything has been heard. A bill
            # drafted late opens "Late Drafting and Introduction Approved By
            # Rules Committee" and is then "Referred to Judiciary". 19
            # bill-chambers of 2009-2016 are read this way; for nine House
            # bills of 2012 it is the only House committee on record, and
            # their pages named only the Senate's. Only before a hearing:
            # HB 1288 of 2022 has no introduction row, was heard by Executive
            # Departments and Administration, and THEN "Referred to Ways and
            # Means", which is the money pass and not the committee of
            # referral. Its House committee stays empty rather than wrong.
            m = PLAIN.match(desc)
            if m and not re.search(r"interim\s+study", desc, re.I):
                c = AMP.sub(" and ", names.committee(expand(clean(m.group("c")))))
        if HEARD.search(desc):
            heard.add((key, body))
        if c:
            refs[key].setdefault(body, c)
    return refs, began


def read_dockets(found=None, lsr_of=None):
    """(from_dockets(), first_bodies()) in one pass over the files."""
    refs, began = {}, {}
    for term, path in (found if found is not None else term_dockets()).items():
        if Path(path).exists():
            r, b = _read_docket(path, term, lsr_of)
            refs.update(r)
            began.update(b)
    return refs, began


def from_dockets(found=None, lsr_of=None):
    """{(term, bill): {body: committee}} -- the FIRST per body, every term.

    from_docket() read db/Docket.psv, which stops part way through 2016 and
    has nothing for 2017-2024, and it was keyed on the session year. So four
    and a half terms -- 2016 to 2024, about 9,000 bills -- took their
    committee from the search page's "Next/Last Comm" alone: the LAST
    committee, and only in ONE chamber. HB 1215 of 2024 was referred to the
    House Special Committee on Housing and its page named only the Senate's
    Election Law and Municipal Affairs, because that is where it ended.

    Keyed on the TERM, because a bill carried into the second year keeps its
    number and gains rows under the next session year. Which rows are the
    bill's is decided by its LSR: _own_rows says why.

    `found` is {term: path}, term_dockets() when omitted; `lsr_of` is
    {(term, bill): the archive record's own LSR}.
    """
    return read_dockets(found, lsr_of)[0]


def first_bodies(found=None, lsr_of=None):
    """{(term, bill): "H" or "S"} -- the chamber of the bill's first docket row.

    The search page files every CACR under the House, and 80 archived CACRs
    were the Senate's. Its own docket says which chamber it began in.
    """
    return read_dockets(found, lsr_of)[1]


def _corpus(path=SRC, lo=1989, hi=2015):
    """Every cleaned, UNexpanded referral string with its count."""
    seen = collections.Counter()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 7 or not p[0].isdigit() or not lo <= int(p[0]) <= hi:
                continue
            for rx in (INTRO, PASSED, REREF):
                m = rx.match(p[6])
                if m:
                    c = clean(m.group("c"))
                    if c:
                        seen[c] += 1
                    break
    return seen


ABBREV = Path("docket_abbrev.json")


def _key_names():
    """The committee names in the General Court's own key to its docket.

    docket_abbrev.json, copied verbatim from
    bill_status/legacy/bs2016/docket_abbrev.htm. One entry is corrected: the
    page prints ST&E as "Science. Technology and Energy", with a full stop
    where the comma belongs, and publishing a committee's name with a typo in
    it because the source had one is deference rather than accuracy.
    """
    if not ABBREV.exists():
        return []
    try:
        raw = json.loads(ABBREV.read_text(encoding="utf-8")).get("abbrev", {})
    except ValueError:
        return []
    return [v.replace("Science. Technology", "Science, Technology")
            for v in raw.values()]


# THE HOUSE NAMING ITS OWN STANDING COMMITTEES. The resolution that adopts
# the rules for a term defines each committee in one construction -- "It shall
# be the duty of the Committee on Science, Technology and Energy to consider
# all matters relating to ..." -- and legislation/1995/HR0001.html and
# legislation/1997/HR0001.html carry 22 of them between them.
#
# This is the strongest witness on the disk after the General Court's own key,
# and for the same reason: it is the body saying what its committees are
# called, in a sentence whose whole purpose is to say so. It is also not
# circular. The pattern is the resolution's grammar, not a name this file
# hopes to prove, so it finds committees nothing here asked about -- among
# them "Corrections and Criminal Justice", whose abbreviation "Corr & Cj" the
# docket never spells out.
RULES_COMMITTEE = re.compile(
    r"Committee on ([A-Z][A-Za-z,'&\-. ]{4,70}?)\s+to consider all matters")


def _rules_names():
    """Committee names the chamber's own rules resolution writes out."""
    out = collections.Counter()
    pages = Path("legislation")
    if not pages.is_dir():
        return out
    for f in pages.rglob("*.html"):
        try:
            text = f.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            continue
        if "to consider all matters" not in text:
            continue
        flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))
        for name in RULES_COMMITTEE.findall(flat):
            out[name.strip(" .,")] += 1
    return out


def _spelled_out():
    """Committee names written in full, from the four sources that write them.

    The docket, where a later clerk spelled out what an earlier one
    abbreviated; the bills saved under legislation/, where the committee is
    printed beside REFERRED TO: in the bill's own text; the resolution each
    House adopts its rules by, which defines every standing committee by name;
    and the General Court's own key, which is the best of the four because it
    is the body saying what its own shorthand means rather than this project
    inferring it.

    The bill texts are the only witness to "Constitutional and Statutory
    Revision", which the docket only ever abbreviates. The key is the only
    witness to "Judiciary and Family Law" and "Economic Development", which
    nothing else on this disk ever writes out. The rules resolutions are the
    only witness to "Public Protection and Veterans Affairs", which the
    docket abbreviates nine ways across 1989-1996 and never once writes out.
    """
    out = collections.Counter()
    for name in _key_names():
        out[name] += 1
    for name, n in _corpus().items():
        out[name] += n
    for name, n in _rules_names().items():
        out[name] += n
    pages = Path("legislation")
    if pages.is_dir():
        try:
            import fetch_legislation as FL
        except ImportError:
            return out
        for f in pages.rglob("*.html"):
            got = FL.parse(FL.decode(f.read_bytes()))
            if got.get("committee"):
                out[got["committee"]] += 1
    return out


def check():
    """Every expansion, against a form spelled out by one of the sources."""
    seen = _corpus()
    full_forms = _spelled_out()
    # Every spelling that reduces to the same key, and the total across them:
    # one representative undercounts a name the sources write six ways.
    spelled = collections.defaultdict(int)
    for k, n in full_forms.items():
        spelled[_key(k)] += n
    bad = []
    for pat, full in PHRASES:
        key = _key(full)
        hits = [k for k in seen if re.search(pat, k, re.I)]
        if key not in spelled:
            bad.append(f"{full!r}: nothing spells it out, so the expansion "
                       "is invented and the abbreviation should stand")
        print(f"  {full:46} <- {sum(seen[k] for k in hits):5,} referrals, "
              f"{len(hits):3} spellings, written out {spelled.get(key, 0):,} times")
    if bad:
        print()
        for b in bad:
            print("  UNPROVEN: " + b)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--src", default=str(SRC))
    a = ap.parse_args()
    if a.check:
        if not Path(a.src).exists():
            sys.exit(f"No {a.src}. --check reads the database dump's referrals.")
        print("EXPANSIONS, and the evidence for each:")
        return check()
    if not term_dockets():
        sys.exit("No archived docket on this disk (Docket_db_*.txt, Docket_<term>.txt).")
    got = from_dockets()
    by_term = collections.Counter()
    for (term, _bill), bodies in got.items():
        by_term[term] += len(bodies)
    print(f"{len(got):,} bills carry a referral, "
          f"{sum(by_term.values()):,} bill-chambers, from each term's own docket")
    print()
    for t in sorted(by_term):
        print(f"  {t}: {by_term[t]:,}")
    names = collections.Counter()
    for bodies in got.values():
        for c in bodies.values():
            names[c] += 1
    print()
    print(f"{len(names)} distinct committee names. The twelve most referred:")
    for k, v in names.most_common(12):
        print(f"  {v:6,}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
