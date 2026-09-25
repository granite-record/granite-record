#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-24.1
"""One name per committee: the name it had at the time.

    import committee_names as CN
    CN.official("Child Y and Jj", "H", "1991-1992")
        -> "Children, Youth and Juvenile Justice"
    CN.official("Exec Depts and Admin for Interim Study", "H", "2001-2002")
        -> "Executive Departments and Administration"
    CN.official("Dev, Rec, and Envir", "S", "1989-1990")
        -> "Development, Recreation and Environment"

    python3 committee_names.py     # every committee this table knows, by term

WHY THIS EXISTS

The 1991-1992 Committee filter on the bills page listed "House Child Y and
Jj" (34 bills), "House Child, Y and Jj" (12) and "House Children Y and Jj"
(3) as three committees. They are one: every one of those bills whose text is
on this disk prints "REFERRED TO: Children, Youth and Juvenile Justice". The
1989-1990 filter had 112 values for 39 committees -- the Senate's
Development, Recreation and Environment alone nine ways -- and a reader who
ticked one of them got part of a committee's bills without being told.

The same shorthand kept hearings off the committee pages. The clerk of
1999-2006 wrote "Exec Depts and Admin", "Crim Just and PSfty" and "Mun and
Cnty Govt" on the hearing lines, the committee pages matched names exactly,
and so House Executive Departments and Administration, Criminal Justice and
Public Safety and Election Law showed no sitting at all for 1999-2004 beside
more than a hundred bills referred in each of those terms.

WHERE IT RUNS

Where names enter the pipeline, so every reader downstream agrees:
build_data.py for each bill's committees (the cards, the Committee filter,
meta.json, bills.csv and the committee pages' bill lists all read those), and
build_proceedings.py for each hearing's (the committee pages' sittings, the
Hearings tab and proceedings.csv). page_code, which says which committee's
page a name at the time belongs on, is asked by build_committees.py for the
pages and by build_site_v2.py for the links to them.

WHAT IT MAY DO, AND WHAT IT MAY NOT

A name comes back either exactly as it went in, or as a name in OFFICIAL
below -- a committee that chamber had in that term, spelt as the General
Court's own documents spell it. Nothing else. Three ways get it there:

  ALIASES      a hand-written table, each entry with its evidence
  the tail     what the clerk wrote after the name: "for Interim Study", a
               journal citation, a bracketed date, a vote, "committee"
  expansion    referrals.expand, the docket's shorthand already proven there

and the second and third are only accepted when what they produce is in
OFFICIAL for that chamber and term. So an abbreviation this file cannot place
stays as the clerk wrote it -- an honest "St Inst" beats an invented name --
and one chamber's committee can never be written onto the other's.

THE NAME AT THE TIME, NEVER A LATER ONE. The House's commerce committee was
"Commerce, Small Business and Consumer Affairs" until 1994, "Commerce, Small
Business, Consumer Affairs and Economic Development" in 1995-1996 and
"Commerce" from 1997; the Senate's was "Executive Departments" until 1992 and
"Executive Departments and Administration" from 1993. The term decides which,
and a name is never replaced by the one the committee carried later.

AN OLDER NAME LINKS, AND STAYS THE OLDER NAME. The person decided on 24
September that where a bill or a hearing names a committee by a name it has
since lost, the name is printed as it was and links to the page of the
committee it was. Which committee that is comes from the General Court's own
code for it, never from the names looking alike: CODES below, each entry with
its witness. 1995's Corrections and Criminal Justice is H26, which sits today
as Criminal Justice and Public Safety; 1995-2008's Commerce is H33, a code the
General Court has retired, and so a page of its own in the committees page's
archived list -- not the page of 2009's Commerce and Consumer Affairs, which
is H43, a different code.

THE EVIDENCE, and how each entry below cites it:

  TEXT   the bill's own text, saved under legislation/<year>/, which prints
         the committee it was referred to ("REFERRED TO:" to 1994,
         "COMMITTEE:" after). Cited as the share of the bills carrying that
         spelling whose text prints the official name. The strongest witness:
         it is the General Court's printed document for that very bill.
  RULES  the House's rules resolution, legislation/1995/HR0001.html and
         legislation/1997/HR0001.html, which names every standing committee.
  KEY    docket_abbrev.json, the General Court's own key to its docket.
  DOCKET the docket's referral lines, Docket_db_<term>.txt.
  SAME   for a hearing's name: the share of that name's hearings whose bill
         was referred, in that chamber, to the official name -- the proof
         referrals.py uses for the hearing line's shorthand.

A wrong merge -- two committees shown as one -- is worse than a missed one, so
an entry needs a witness, and preflight fails if any alias could turn the name
of a different committee of the same chamber and term into its own.
"""

import re
import sys

import names
import referrals

# ---------------------------------------------------------------------------
# Every committee this table can write, by chamber and the terms it had that
# name: (chamber, first year, last year, name). A term is inside when both of
# its years are. Several committees had a name, lost it and had it again, and
# those are two rows: the House's Judiciary was Judiciary and Family Law in
# 1995-1998 (RULES 1995 and 1997 name no other Judiciary), and an alias that
# writes "Judiciary" must not reach those four years.
#
# Built from the bills' own texts (TEXT), the House rules resolutions (RULES)
# and the General Court's committee table (data/committees.json, for the
# names in use today). A committee not listed here is not unknown to the site
# -- its name simply passes through unchanged -- so this is the list of names
# this file may WRITE, not of names that exist.
OFFICIAL = [
    # ---- House ----
    ("H", 1989, 1994, "Appropriations"),                           # TEXT
    ("H", 1989, 1994, "Children, Youth and Juvenile Justice"),     # TEXT
    ("H", 1999, 2026, "Children and Family Law"),                  # TEXT, H37
    ("H", 1989, 1994, "Commerce, Small Business and Consumer Affairs"),  # TEXT
    ("H", 1995, 1996,
     "Commerce, Small Business, Consumer Affairs and Economic Development"),  # RULES 1995
    ("H", 1997, 2010, "Commerce"),                                 # RULES 1997, TEXT
    ("H", 2009, 2026, "Commerce and Consumer Affairs"),            # TEXT, H43
    ("H", 1989, 1996, "Constitutional and Statutory Revision"),    # TEXT, RULES 1995
    ("H", 2011, 2012, "Constitutional Review and Statutory Recodification"),  # TEXT
    ("H", 1993, 1996, "Corrections and Criminal Justice"),         # TEXT, RULES 1995
    ("H", 1997, 2026, "Criminal Justice and Public Safety"),       # RULES 1997, H26
    ("H", 2017, 2018, "Criminal Justice and Public Safety Joint with Judiciary"),  # H53
    ("H", 1991, 1994, "Economic Development"),                     # TEXT
    ("H", 1989, 2024, "Education"),                                # H05
    ("H", 2025, 2026, "Education Funding"),                        # H63
    ("H", 2025, 2026, "Education Policy and Administration"),      # H62
    ("H", 1997, 2026, "Election Law"),                             # RULES 1997, H36
    ("H", 1989, 2026, "Environment and Agriculture"),              # H06
    ("H", 1989, 2026, "Executive Departments and Administration"),  # H07
    ("H", 1995, 2026, "Finance"),                                  # RULES 1995, H34
    ("H", 1989, 1992, "Fish and Game"),                            # TEXT
    ("H", 2001, 2010, "Fish and Game"),                            # TEXT
    ("H", 2009, 2026, "Fish and Game and Marine Resources"),       # TEXT, H42
    ("H", 1989, 2026, "Health, Human Services and Elderly Affairs"),  # H09
    ("H", 2025, 2026, "Housing"),                                  # H64
    ("H", 1999, 2008, "Joint Committee on Address"),               # TEXT
    ("H", 1989, 1994, "Judiciary"),                                # TEXT
    ("H", 1999, 2026, "Judiciary"),                                # TEXT, H10
    ("H", 1995, 1998, "Judiciary and Family Law"),                 # RULES 1995, 1997; KEY
    ("H", 1989, 2026, "Labor, Industrial and Rehabilitative Services"),  # H11
    ("H", 1989, 2026, "Legislative Administration"),               # H12
    ("H", 1997, 1998, "Local and Regulated Revenues"),             # RULES 1997
    ("H", 2009, 2010, "Local and Regulated Revenues"),             # TEXT
    ("H", 1989, 2026, "Municipal and County Government"),          # H18
    ("H", 1989, 1996, "Public Protection and Veterans Affairs"),   # TEXT, RULES 1995
    ("H", 1989, 1994, "Public Works"),                             # TEXT
    ("H", 1995, 2026, "Public Works and Highways"),                # RULES 1995, TEXT, H20
    ("H", 1989, 1996, "Regulated Revenues"),                       # TEXT, RULES 1995
    ("H", 1989, 2026, "Resources, Recreation and Development"),    # H22
    ("H", 1989, 2026, "Rules"),                                    # RULES, H23
    ("H", 1989, 2026, "Science, Technology and Energy"),           # H24
    ("H", 2011, 2012, "Special Committee on Education Funding Reform"),  # TEXT
    ("H", 2011, 2012, "Special Committee on Public Employee Pensions Reform"),  # TEXT
    ("H", 2015, 2016, "Special Committee on Public Employee Pension Plans"),  # TEXT, H47
    ("H", 2011, 2012, "Special Committee on Redistricting"),       # TEXT, H55
    ("H", 2021, 2022, "Special Committee on Redistricting"),       # TEXT, H55
    ("H", 2023, 2024, "Special Committee on Childcare"),           # TEXT, H56
    ("H", 2023, 2024, "Special Committee on Housing"),             # TEXT, H58
    ("H", 1989, 1992, "State Institutions and Housing"),           # TEXT
    ("H", 1989, 1996, "State-Federal Relations"),                  # TEXT, RULES 1995
    ("H", 1997, 2026, "State-Federal Relations and Veterans Affairs"),  # RULES 1997, H25
    ("H", 1989, 2026, "Transportation"),                           # H27
    ("H", 1989, 1994, "Ways and Means"),                           # TEXT
    ("H", 2001, 2026, "Ways and Means"),                           # TEXT, H28
    ("H", 1993, 2000, "Wildlife and Marine Resources"),            # TEXT, RULES, KEY
    # ---- Senate ----
    ("S", 1993, 1994, "Appropriations"),                           # TEXT
    ("S", 1989, 2004, "Banks"),                                    # TEXT
    ("S", 2005, 2006, "Banks and Insurance"),                      # TEXT
    ("S", 1989, 2026, "Capital Budget"),                           # TEXT, S02
    ("S", 2025, 2026, "Children and Family Law"),                  # S41
    ("S", 2011, 2026, "Commerce"),                                 # TEXT, S37
    ("S", 2007, 2010, "Commerce, Labor and Consumer Protection"),  # TEXT
    ("S", 1989, 1990, "Development, Recreation and Environment"),  # TEXT
    ("S", 1991, 1998, "Economic Development"),                     # TEXT
    ("S", 1989, 2012, "Education"),                                # TEXT, S05
    ("S", 2015, 2018, "Education"),                                # TEXT, S05
    ("S", 2021, 2026, "Education"),                                # TEXT, S05
    ("S", 2019, 2020, "Education and Workforce Development"),      # TEXT, S91
    ("S", 2025, 2026, "Education Finance"),                        # s42
    ("S", 2007, 2008, "Election Law and Internal Affairs"),        # TEXT, S50
    ("S", 2017, 2018, "Election Law and Internal Affairs"),        # TEXT, S50
    ("S", 2019, 2026, "Election Law and Municipal Affairs"),       # TEXT, S92
    ("S", 2009, 2010, "Election Law and Veterans' Affairs"),       # TEXT
    ("S", 1999, 2006, "Energy and Economic Development"),          # TEXT
    ("S", 2011, 2026, "Energy and Natural Resources"),             # TEXT, S38
    ("S", 2007, 2010, "Energy, Environment and Economic Development"),  # TEXT
    ("S", 1991, 2004, "Environment"),                              # TEXT
    ("S", 2005, 2006, "Environment and Wildlife"),                 # TEXT
    ("S", 1989, 1992, "Executive Departments"),                    # TEXT, DOCKET
    ("S", 1993, 2026, "Executive Departments and Administration"),  # TEXT, S06
    ("S", 1989, 1992, "Finance"),                                  # TEXT
    ("S", 1995, 2026, "Finance"),                                  # TEXT, S07
    ("S", 1993, 1994, "Finance Executive Committee"),              # TEXT
    ("S", 1995, 1996, "Fish and Game/Recreation"),                 # TEXT
    ("S", 2005, 2012, "Health and Human Services"),                # TEXT, S26
    ("S", 2015, 2026, "Health and Human Services"),                # TEXT, S26
    ("S", 2013, 2014, "Health, Education and Human Services"),     # TEXT
    ("S", 1989, 2004, "Insurance"),                                # TEXT
    ("S", 1989, 1992, "Internal Affairs"),                         # TEXT, KEY
    ("S", 1997, 2006, "Internal Affairs"),                         # TEXT
    ("S", 2011, 2012, "Internal Affairs"),                         # TEXT
    ("S", 1989, 2004, "Interstate Cooperation"),                   # TEXT, KEY
    ("S", 1989, 2026, "Judiciary"),                                # TEXT, S10
    ("S", 1989, 2004, "Public Affairs"),                           # TEXT, KEY
    ("S", 2005, 2018, "Public and Municipal Affairs"),             # TEXT, S27
    ("S", 1989, 2004, "Public Institutions, Health and Human Services"),  # TEXT, KEY
    ("S", 2005, 2026, "Rules and Enrolled Bills"),                 # TEXT, S45
    ("S", 2013, 2016, "Rules, Enrolled Bills and Internal Affairs"),  # TEXT, S40
    ("S", 1989, 2004, "Transportation"),                           # TEXT
    ("S", 2011, 2026, "Transportation"),                           # TEXT, S16
    ("S", 2005, 2010, "Transportation and Interstate Cooperation"),  # TEXT
    ("S", 1989, 2026, "Ways and Means"),                           # TEXT, S17
    ("S", 1991, 1994, "Wildlife and Recreation"),                  # TEXT, KEY
    ("S", 1997, 2004, "Wildlife and Recreation"),                  # TEXT
    ("S", 2007, 2008, "Wildlife, Fish and Game"),                  # TEXT
    ("S", 2007, 2010, "Wildlife, Fish and Game and Agriculture"),  # TEXT
]


# ---------------------------------------------------------------------------
# THE ALIASES: (chamber, first year, last year, pattern, official name).
#
# The pattern is matched whole, ignoring case, against the name as _norm
# writes it -- lower case, "&" as "and", apostrophes dropped, every other
# run of punctuation one space -- so "Child, Y & JJ", "Child Y and Jj" and
# "CHILD Y&JJ" are all "child y and jj", and one pattern covers what the
# clerks wrote with and without their commas, stops and slashes.
#
# Each entry's comment gives what it renamed on the build of 24 September
# 2026: bill cards (a bill's committee in one chamber, data/bills.json) and
# hearings (rows of proceedings.csv), with the witnesses the module's
# docstring names. TEXT counts only the bills whose chamber of origin is the
# entry's, since a bill's text prints its first chamber's referral. SAME is
# lower for Finance, Appropriations and Ways and Means than for the others,
# and rightly: they are the second committee most bills reach, so the hearing
# row names them and the card names the first.
ALIASES = [
    # ---- House ----
    # THE ONE THE PERSON REPORTED. 12 spellings on 166 cards of 1989-1994,
    # 22 on 183 hearings. TEXT 116 of 119 print "Children, Youth and Juvenile
    # Justice" (the other three print a different committee altogether, a
    # disagreement between text and docket about WHICH committee, not a
    # spelling); SAME 183 of 183. Of the texts of 1989-1994, 117 print the
    # name and one "Children, Youth, and Juvenile Justice", as the person
    # wrote it; the site keeps the General Court's majority spelling. It is
    # the only committee of those texts whose name begins "Child".
    ("H", 1989, 1994,
     r"(?:ch|chy|child|children|cyjj)(?: (?:and )?(?:y|yth|youth))?"
     r"(?: (?:and )?(?:jj|juv jus|juv just|justice|juvenile justice))?",
     "Children, Youth and Juvenile Justice"),
    # "Commerce" is what the clerk wrote for this committee, and it is also
    # the name the committee took in 1997 -- on a card of 1989-1996 a later
    # name as well as a short one. 1989-1994: 336 cards, 629 hearings; TEXT
    # 252 of 255 print "Commerce, Small Business and Consumer Affairs" (as
    # does legislation/1993/HBI0002.html; the other three are two 1991
    # vacates the text records and one Legislative Administration bill).
    # 1995-1996: 162 cards, 376 hearings; TEXT 116 of 117 print "Commerce,
    # Small Business, Consumer Affairs and Economic Development" (the 117th
    # misspells it), which RULES 1995 names. RULES 1997 names "Commerce", and
    # from then "Comm" and "Commerc" are the hearing line's: 12 hearings,
    # SAME 12 of 12.
    ("H", 1989, 1994,
     r"comm(?:erc|erce)?(?: sb(?: cons af)?)?|sb and cons aff|csb and ca",
     "Commerce, Small Business and Consumer Affairs"),
    ("H", 1995, 1996, r"comm(?:erc|erce)?",
     "Commerce, Small Business, Consumer Affairs and Economic Development"),
    ("H", 1997, 1998, r"comm(?:erc)?", "Commerce"),
    # Typed, not abbreviated: "Commerce anad Consumer Affairs" and "Commerce
    # and Consume Affairs", 8 hearings of 2009-2014.
    ("H", 2009, 2026, r"commerce an(?:a)?d consumer? affairs",
     "Commerce and Consumer Affairs"),
    # 16 cards of 1989, 37 hearings of 1989-1996: TEXT 14 of 15 (the 15th
    # prints "Revisions"), SAME 35 of 37.
    ("H", 1989, 1996,
     r"con(?:st(?:itutional)?)? and stat(?:utory)?(?: rev(?:ision)?)?",
     "Constitutional and Statutory Revision"),
    ("H", 2011, 2012, r"consitutional review and statutory recodification",
     "Constitutional Review and Statutory Recodification"),     # 1 card; TEXT 1 of 1
    # From 1997 (RULES 1997) the House's one committee whose name holds
    # "Criminal Justice", but for 2017's joint one with Judiciary. 2 cards,
    # TEXT 2 of 2; 948 hearings, "Crim Just and PSfty" 714 of them, SAME 933
    # of 948.
    ("H", 1997, 2026,
     r"crim(?:inal)? j(?:ust(?:ice|sice)?|s)"
     r"(?: and p(?:ub(?:lic|ic)?)? ?s(?:afety|fty))?",
     "Criminal Justice and Public Safety"),
    # 1 card, TEXT 1 of 1; 552 hearings ("Elec Law" 523), SAME 552 of 552.
    ("H", 1997, 2026, r"elec(?: l(?:a)?w)?", "Election Law"),
    # 6 cards, TEXT 6 of 6; 634 hearings ("Env and Agric" 462), SAME 617 of 634.
    ("H", 1989, 2026,
     r"env(?:ir|iron|ironment)? and ag(?:r|ri|ric|irculture|riculture)?",
     "Environment and Agriculture"),
    # 7 cards, TEXT 4 of 5 (the fifth names Commerce); 1,414 hearings ("Exec
    # Depts and Admin" 1,094), SAME 1,397 of 1,414. The House's committee
    # carried "and Administration" throughout -- 81 texts of 1989-1990 print
    # it -- so 1989's lone "Executive Departments" is a short form here, where
    # in the Senate it is the name (below).
    ("H", 1989, 2026,
     r"ex(?:ec(?:utive|tive)?)?(?: dep\w*)?(?: and| ans)? adm\w*"
     r"|executive departments",
     "Executive Departments and Administration"),
    # From 1995 (RULES 1995) the House has one Finance. "House Finance" is a
    # card of 1995 with the chamber written twice. A division of Finance is
    # part of Finance -- build_committees already files a member of "Finance
    # - Division II" under Finance -- and 1997's "Fin Div I/II" and "Finance
    # Div III" hearings (41) go to it. 276 hearings in all.
    ("H", 1995, 2026, r"(?:house )?fin(?:a|an|anc|ance)?(?: div(?:ision)? i{1,3})?",
     "Finance"),
    # 13 hearings; SAME 13 of 13.
    ("H", 1989, 1992, r"f(?:ish)? and g(?:ame)?", "Fish and Game"),
    ("H", 2001, 2010, r"f(?:ish)? and g(?:ame)?", "Fish and Game"),
    # "Health" alone: 53 cards, TEXT 37 of 39 (the other two print a
    # misspelling of it and Appropriations); 77 hearings, SAME 76 of 77. The
    # House's one health committee through 1998: RULES 1995 and 1997 name no
    # other, and neither do the texts of 1989-1994.
    ("H", 1989, 1998, r"health", "Health, Human Services and Elderly Affairs"),
    # 9 cards, TEXT 8 of 8; 547 hearings ("Health HS and EA" 406), SAME 537
    # of 547.
    ("H", 1989, 2026,
     r"(?:health|hlth|hth|h)(?: and)? (?:hs|hum ser|human svcs)"
     r"(?:(?: and)? (?:ea|eld|elderly affairs?))?"
     r"|health human services(?: and elderly affair)?",
     "Health, Human Services and Elderly Affairs"),
    # 1995-1998 had no committee called Judiciary: RULES 1995 and 1997 name
    # Judiciary and Family Law and no other, and KEY reads "JUD" so. 6 cards,
    # TEXT 1 of 1; 119 hearings, SAME 118 of 119.
    ("H", 1995, 1998, r"ju(?:d(?:iciary)?)?(?: and f ?l)?(?: div)?",
     "Judiciary and Family Law"),
    ("H", 1989, 1994, r"juciciary", "Judiciary"),               # 1 card; TEXT 1 of 1
    # 1 card, TEXT 1 of 1; 345 hearings ("Labor" 244), SAME 335 of 345; KEY.
    ("H", 1989, 2026,
     r"lab(?:o|or)?(?: ind(?:ustrial)?)?(?: and)?(?: reh(?:ab(?:ilitative)?)?)?"
     r"(?: s(?:vcs|ervices|rvcs))?",
     "Labor, Industrial and Rehabilitative Services"),
    # 23 cards, TEXT 21 of 22 (the 22nd misspells it); 167 hearings, SAME
    # 150 of 167; KEY.
    ("H", 1989, 2026,
     r"leg(?:is(?:lative)?)?(?: adm(?:in(?:istrationn?)?)?)?",
     "Legislative Administration"),
    # 35 hearings of 1997-1998 (RULES 1997), SAME 35 of 35; 1 card and 16
    # hearings of 2009-2010, SAME 16 of 16.
    ("H", 1997, 1998,
     r"l(?:oc(?:al)?)? and (?:rr|reg(?:ulated)? rev(?:enues?|eneus)?)",
     "Local and Regulated Revenues"),
    ("H", 2009, 2010,
     r"l(?:oc(?:al)?)? and (?:rr|reg(?:ulated)? rev(?:enues?|eneus)?)",
     "Local and Regulated Revenues"),
    # "Muncipal": the clerk's shorthand for this committee is written out by
    # referrals.PHRASES (885 hearings), and this is the one misspelling it
    # does not read.
    ("H", 1989, 2026, r"mun(?:i)?cipal and county government",
     "Municipal and County Government"),
    # 1 card, TEXT 1 of 1; 15 hearings, SAME 15 of 15.
    ("H", 1989, 1996,
     r"pub(?:l|lic)? pro(?:t(?:ec(?:t(?:ion)?)?)?)?(?: and vet(?:s|erans)?(?: aff(?:s|airs)?)?)?",
     "Public Protection and Veterans Affairs"),
    # 4 cards, TEXT 4 of 4; 16 hearings, SAME 16 of 16.
    ("H", 1989, 1994, r"pw|pub(?:lic)? w(?:o)?r?ks", "Public Works"),
    # RULES 1995 names "Public Works and Highways", and so does the text of
    # every bill of 1995-2006 whose card said "Public Works" and has one: 212
    # of 212. 248 cards, 570 hearings (SAME 568). The search page's spelling
    # of the same bills, which build_data._same_committee already calls one
    # committee with this.
    ("H", 1995, 2026,
     r"(?:pw|p(?:u|up)b(?:lic)? w(?:o)?r?ks)(?: and h(?:ighways)?)?",
     "Public Works and Highways"),
    # 6 cards; 11 hearings, SAME 11 of 11; KEY.
    ("H", 1989, 1996, r"reg(?:ulated)? rev(?:enues?)?", "Regulated Revenues"),
    # 3 cards, TEXT 3 of 3; 559 hearings ("Res, Rec and Dev" 439), SAME 554.
    ("H", 1989, 2026,
     r"res(?:o?ources|ourses)?(?: rec(?:reation)?)?(?: and)? dev(?:elopment|leopment)?",
     "Resources, Recreation and Development"),
    # 5 cards, TEXT 4 of 4; 637 hearings ("Science, Tech and En" 510), SAME 636.
    ("H", 1989, 2026,
     r"sci(?:en|ence)?(?: (?:and )?tech(?:nology|noloby)?)?(?: and)?(?: en(?:er|ergy)?)?",
     "Science, Technology and Energy"),
    # TEXT 9 of 9: the bills of 2011-2012 whose card said "...Pension Plans"
    # print "Special Committee on Public Employee Pensions Reform", as do the
    # docket and the term's other 15 cards. "Pension Plans" is the name the
    # committee's code (H47) carries now, which the search page wrote back
    # onto these; 2015-2016's own texts print it. 10 cards.
    ("H", 2011, 2012, r"special committee on public employee pension plans",
     "Special Committee on Public Employee Pensions Reform"),
    # 76 cards, TEXT 66 of 66; 113 hearings, SAME 113 of 113.
    ("H", 1989, 1992, r"st(?:ate)? ins(?:t|ts|titutions)?(?: and)?(?: h(?:sng|sg|ousing)?)?",
     "State Institutions and Housing"),
    # 69 cards, TEXT 24 of 24; 65 hearings, SAME 65 of 65; RULES 1995.
    ("H", 1989, 1996, r"st(?:ate)? fed(?:eral)?(?: r(?:el(?:s|ations)?|eg)?)?",
     "State-Federal Relations"),
    # RULES 1997 names "State-Federal Relations and Veterans Affairs". 9
    # cards, TEXT 1 of 1; 219 hearings, SAME 217 of 219.
    ("H", 1997, 2026,
     r"s(?:t|tate|atte) fed(?:eral)?(?: r(?:el(?:s|ations)?|ed)?)?"
     r"(?:(?: and)? vet(?:s|erans?)?(?: aff(?:s|airs)?)?)?",
     "State-Federal Relations and Veterans Affairs"),
    # 2 cards, TEXT 1 of 1; 50 hearings, SAME 50 of 50; KEY.
    ("H", 1989, 2026,
     r"trans(?:p|po|por|port|porat|poration|portaion|portati|portation)?",
     "Transportation"),
    # 1 card, TEXT 1 of 1; 98 hearings.
    ("H", 1989, 1994, r"ways? and means|w and m", "Ways and Means"),
    ("H", 2001, 2026, r"ways? and means|w and m", "Ways and Means"),
    # 168 cards, TEXT 147 of 149 (two print another committee); 287
    # hearings, SAME 287 of 287; RULES 1995 and 1997; KEY: WILDLIFE is
    # "Wildlife and Marine Resources".
    ("H", 1993, 2000, r"wildl(?:i|if|ife|f)?(?: and marine res(?:ources)?)?",
     "Wildlife and Marine Resources"),
    # 1 card, TEXT 1 of 1; 4 hearings; KEY.
    ("H", 1989, 1994, r"approp(?:s|riation)?", "Appropriations"),
    # 1 card, TEXT 1 of 1; 567 hearings ("Child and Fam Law" 471), SAME 567.
    ("H", 1999, 2026, r"child(?:ren)? and f(?:a)?m(?:ily|ly)?(?: law)?",
     "Children and Family Law"),
    # ---- Senate ----
    # 7 cards, TEXT 2 of 2; 21 hearings (most the second committee); KEY.
    ("S", 1993, 1994, r"(?:sen )?approps?", "Appropriations"),
    ("S", 1989, 2026, r"cap(?:ital)? bud(?:get)?", "Capital Budget"),  # 1 card; TEXT 1 of 1
    ("S", 2007, 2010, r"commerce labor and comsumer protection",
     "Commerce, Labor and Consumer Protection"),                # 2 cards; TEXT 2 of 2
    # NINE SPELLINGS ON 154 CARDS OF 1989-1990, and 158 hearings. TEXT 38 of
    # 39 print "Development, Recreation and Environment" (the 39th misspells
    # it); SAME 157 of 158. Nothing else of that term's Senate begins "Dev".
    # referrals.py left "DEV REC & ENV" as the clerk wrote it because the
    # docket never spells it out; the bills' texts do.
    ("S", 1989, 1990, r"de[vc] rec(?: and)? (?:env(?:ir)?|rec)",
     "Development, Recreation and Environment"),
    ("S", 1991, 1998, r"econ(?:omic)? dev(?:el)?", "Economic Development"),  # 6 cards; KEY
    ("S", 2009, 2010, r"election law and veterans affairsl",
     "Election Law and Veterans' Affairs"),                     # 1 card, 1 hearing
    ("S", 1999, 2006, r"enery and economic development",
     "Energy and Economic Development"),                        # 1 card
    # 1 card, TEXT 1 of 1; and "En", the legacy hearing line's (7 hearings,
    # SAME 7 of 7), only in years when the Senate had no committee called
    # Energy anything.
    ("S", 1991, 2004, r"envirnment|enrivon|environ", "Environment"),
    ("S", 1991, 1998, r"en", "Environment"),
    # THE SENATE'S COMMITTEE WAS "EXECUTIVE DEPARTMENTS" UNTIL 1992, and the
    # site printed the name it took in 1993. Two witnesses that do not depend
    # on each other. TEXT: 79 of the 81 texts of 1989-1992 whose card said
    # "Executive Departments and Administration" print "Executive
    # Departments". DOCKET: the Senate's clerk wrote the committee on 192
    # introductions of 1989-1992 and never with "& ADMIN"; on 1993-1994's
    # 150, every one has it ("EXEC DEPTS+ADMIN"), and the texts change then
    # too. The longer name reached 184 cards and 197 hearings from
    # referrals.PHRASES, whose expansion of a bare "EXEC DEPTS" is right for
    # the House of every term and the Senate from 1993. 195 cards and 206
    # hearings in all.
    ("S", 1989, 1992,
     r"exec(?:utive|tive)?(?: dep(?:t|ts|art|artment|artments)?)?(?: and adm\w*)?",
     "Executive Departments"),
    # 8 cards, TEXT 7 of 7; 84 hearings, SAME 84 of 84.
    ("S", 1993, 2026, r"ex(?:ec(?:utive)?)? dep\w*(?: and| ans)? adm\w*",
     "Executive Departments and Administration"),
    # 10 cards of 1991, TEXT 1 of 1; 7 hearings.
    ("S", 1989, 1992, r"(?:sen(?:ate)? )?fin(?:a|an|anc|ance)?", "Finance"),
    ("S", 1995, 2026, r"(?:sen(?:ate)? )?fin(?:a|an|anc|ance)?", "Finance"),
    # 15 cards, TEXT 8 of 8 print "Finance Executive Committee" -- 1993's HB1,
    # the budget, went there -- and no Senate text of 1993-1994 prints plain
    # "Finance". 15 hearings, SAME 15 of 15. Whether it was the Senate's
    # Finance under another name is not something this file claims.
    ("S", 1993, 1994, r"fin(?:ance)? exec(?:utive)?(?: comm(?:ittee)?)?",
     "Finance Executive Committee"),
    # 66 cards, TEXT 15 of 15 print "Fish & Game/Recreation" (the site writes
    # "and" for "&" in every name); 69 hearings, SAME 69 of 69. Another of
    # referrals.py's "spelled out nowhere on this disk": the docket never
    # does, and the bills' texts do.
    ("S", 1995, 1996, r"f(?:ish)? and g(?:ame)?(?: and)?(?: rec(?:reation)?)?",
     "Fish and Game/Recreation"),
    ("S", 1989, 2004, r"insuranc+e", "Insurance"),              # 1 card; TEXT 1 of 1
    # 37 cards of 1989-1992, TEXT 16 of 16, 30 hearings SAME 30 of 30; and
    # "Internal" alone on 16 cards of 1999-2003, TEXT 6 of 6. KEY: INT AFFAIR.
    ("S", 1989, 1992, r"int(?:er(?:nal)?)? aff(?:s|air|airs)?|internal",
     "Internal Affairs"),
    ("S", 1997, 2006, r"int(?:er(?:nal)?)? aff(?:s|air|airs)?|internal",
     "Internal Affairs"),
    # 39 cards, TEXT 20 of 20; 42 hearings, SAME 42 of 42; KEY: INTERSTATE.
    ("S", 1989, 2004, r"int(?:er(?:st(?:ate)?)?)? coop(?:eration)?|interstate",
     "Interstate Cooperation"),
    ("S", 1989, 2026, r"judicary|judiicary", "Judiciary"),     # 2 cards; TEXT 1 of 1
    # "Public" alone and a misspelling: 6 cards, TEXT 5 of 5; 10 hearings; KEY.
    ("S", 1989, 2004, r"public|pub(?:lic|ilc)? aff(?:s|air|airs)?",
     "Public Affairs"),
    # 156 cards under 14 spellings (115 of them the "&" of 1999-2003), TEXT 40
    # of 42 (the other two print the name cut to "Public Institutions"); 35
    # hearings, SAME 35 of 35; KEY: PUB INST. The Senate had one such
    # committee; "State Institutions and Housing" is the House's.
    ("S", 1989, 2004,
     r"pub(?:l|lic)? in(?:s|st|stit|t|stitutions)"
     r"|(?:pi|p(?:ub(?:l|lic)?)?(?: in(?:s|st|stit|t|stitutions|stitutitions))?)"
     r"(?: and)? h(?:ealth|elath)?(?: and)? h(?:uman)? ?s(?:ervices)?",
     "Public Institutions, Health and Human Services"),
    ("S", 1989, 2004, r"trans(?:p|po|por|port|portion|portation)?",
     "Transportation"),                                         # 1 card
    # 70 cards (69 the "&" of 1999-2003), TEXT 9 of 10 (the tenth names
    # another committee); TEXT prints "Wildlife" alone for five of 1993-1994's
    # bills. KEY: "W & R".
    ("S", 1991, 1994, r"wildlife(?: and rec(?:reation)?)?|w and r",
     "Wildlife and Recreation"),
    ("S", 1997, 2004, r"wildlife(?: and rec(?:reation)?)?|w and r",
     "Wildlife and Recreation"),
    ("S", 2007, 2008, r"wildlife fish a[mn]d game", "Wildlife, Fish and Game"),  # 3 cards
    # KEY: "W & M" is Ways and Means. The manifest writes the ampersand as
    # "and", which referrals.expand's "^W & M$" does not read. 1 hearing.
    ("S", 1989, 2026, r"w and m", "Ways and Means"),
]

_COMPILED = [(ch, lo, hi, re.compile(p), full) for ch, lo, hi, p, full in ALIASES]


def _norm(s):
    """A name as the aliases see it: lower case, "&" as "and", apostrophes
    dropped, any other run of punctuation one space."""
    s = (s or "").lower()
    s = re.sub(r"['’`]", "", s)
    s = re.sub(r"[&+]", " and ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


_OFFICIAL_BY = {}
for _ch, _lo, _hi, _nm in OFFICIAL:
    _OFFICIAL_BY.setdefault((_ch, _norm(_nm)), []).append((_lo, _hi, _nm))


def _start(term):
    """"1991-1992" -> 1991; None for anything that is not a term."""
    m = re.match(r"^\s*(\d{4})", str(term or ""))
    return int(m.group(1)) if m else None


def _covers(lo, hi, y):
    return y is not None and lo <= y and y + 1 <= hi


def known(name, chamber, term):
    """The official spelling if `name` is a committee OFFICIAL lists for that
    chamber and term, however it was cased or punctuated; else None."""
    y = _start(term)
    for lo, hi, full in _OFFICIAL_BY.get((chamber, _norm(name)), ()):
        if _covers(lo, hi, y):
            return full
    return None


def alias(name, chamber, term):
    """The official name an ALIASES entry gives `name` in that chamber and
    term, or None."""
    y = _start(term)
    n = _norm(name)
    if not n:
        return None
    for ch, lo, hi, rx, full in _COMPILED:
        if ch == chamber and _covers(lo, hi, y) and rx.fullmatch(n):
            return full
    return None


# WHAT THE CLERK WROTE AFTER THE NAME. Each was on a hearing or a card:
#   "Exec Depts and Admin for Interim Study VV"     the committee held it for
#                                                   interim study
#   "Executive Departments and Administration [3/17/2011]"  the day, twice
#   "Finance (4/11/07)"  "(Cons Cal by nec 2/3VV)"  a date or a calendar note
#   "Education <Finance>"  "<Note Time Change>"     the clerk's note
#   "Health HS and EA: HJ18, p274"  "Judiciary Hj9" the journal
#   "WAYS and MEANS, REP HORTON MA VV"              the mover and the vote
#   "Res, Rec and Dev committee RC(158-154)"        the word, and a tally
#   "... by the necessary 2/3 vote, Pursuant to Senate Rule 3-26"
#   "to Public Works"  "a Joint Committee on Address"  a word before it
#   "Insurance,1/13/00"                             a date after a comma
#   "the Judiciary Committee for Interim Study"     an article
#   "House Finance"                                 the chamber, twice
# A parenthesis without a digit is left alone: "(DCYF)" is part of H61's name.
# The tally goes before the parenthesis rule, or "RC(252-67)" would lose its
# numbers first and leave "RC" behind.
_TAILS = [
    re.compile(r"\s*<[^>]*>?"),
    re.compile(r"\s*\[[^\]]*\]"),
    re.compile(r"(?:[\s,:;.]+(?:MA|VV|MF|ML|2/3\s*VV"
               r"|(?:RC|DIV|DV|2/3\s*DIV)\s*\(\s*\d+\s*-\s*\d+\s*\)))+\s*$", re.I),
    re.compile(r"\s*\((?=[^)]*\d)[^)]*\)"),
    re.compile(r"\s+(?:for|to)\s+int(?:erim|\.)?\s+study\b.*$", re.I),
    re.compile(r"\s+by\s+the\s+necessary\b.*$", re.I),
    re.compile(r"\s*[:;,]?\s*\b[HS]J\s*\d.*$", re.I),
    re.compile(r"\s*,\s*\d{1,2}/\d{1,2}/\d{2,4}.*$"),
    referrals.MOVER,
    re.compile(r"\s+committeel?$", re.I),
    re.compile(r"^(?:to|a|the|house|senate)\s+", re.I),
]


def untailed(name):
    """The name without anything _TAILS lists after (or before) it."""
    s = (name or "").strip()
    for _ in range(6):
        was = s
        for rx in _TAILS:
            s = rx.sub("", s).strip(" ,;:.")
        if s == was:
            break
    return s


def _distance(a, b, cap):
    """Levenshtein distance between two strings, or cap + 1 once it is over."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


# A TYPING SLIP, and only that: a name at most TYPO letters -- added, dropped
# or changed -- from exactly one committee OFFICIAL lists for that chamber and
# term. "Juduciary", "Execuutive Departments and Administration", "Public
# Institutions, Health and Human Sevices", "Municipal and Count Government".
# A name that close to two of them is left as it was written. So are names
# under eight letters, where two letters is a quarter of the word: "Ed" is
# two from "Educ" and "En" two from "Env".
TYPO = 2


def typo(name, chamber, term):
    """The one OFFICIAL name `name` is a typing slip of, or None."""
    n = _norm(name)
    if len(n) < 8:
        return None
    y = _start(term)
    near = set()
    for (ch, nn), rows in _OFFICIAL_BY.items():
        if ch != chamber or nn == n:
            continue
        for lo, hi, full in rows:
            if _covers(lo, hi, y) and _distance(n, nn, TYPO) <= TYPO:
                near.add(full)
    return near.pop() if len(near) == 1 else None


def _resolve(s, chamber, term):
    got = alias(s, chamber, term) or known(s, chamber, term)
    if got:
        return got
    # The docket's shorthand, which referrals.PHRASES writes out where it has
    # proof -- accepted only if what it writes is a committee this chamber
    # had that term. expand() is not told the chamber, and this is what
    # keeps it from writing one chamber's committee onto the other's, or a
    # name onto a year before the committee carried it (it writes "Public
    # Works" for PUB WKS, which the alias above turns into Public Works and
    # Highways from 1995).
    e = referrals.AMP.sub(" and ", names.committee(referrals.expand(s)))
    if e and _norm(e) != _norm(s):
        got = alias(e, chamber, term) or known(e, chamber, term)
        if got:
            return got
    return typo(s, chamber, term)


def official(name, chamber, term):
    """The committee's name as it was in that chamber and term.

    `chamber` is "H" or "S" (or "House"/"Senate"); `term` is "1991-1992" or
    anything starting with its first year. Returns `name` unchanged unless it
    can be placed on a name OFFICIAL lists for that chamber and term: see the
    module's docstring for what may and may not happen here.
    """
    raw = name or ""
    ch = str(chamber or "").strip().upper()[:1]
    if not raw.strip() or ch not in ("H", "S") or _start(term) is None:
        return raw
    # The name without its tail first, so a note after it -- "Education <W &
    # M>" -- can never be what the expansion reads.
    for s in dict.fromkeys((untailed(raw), raw.strip())):
        if s:
            got = _resolve(s, ch, term)
            if got:
                return got
    return raw


# ---------------------------------------------------------------------------
# THE COMMITTEE A NAME AT THE TIME WAS, where that is not the committee the
# General Court lists today under the same name: (chamber, first year, last
# year, name, code). `name` is the name as official() writes it for those
# terms; `code` is the General Court's own code for the committee -- one it
# lists today under a later name, one it has retired, or None where the
# record says the committee was NOT today's namesake and does not say which
# it was.
#
# Only the General Court's own filing places a name here. Two witnesses:
#
#   STATUS  archive_samples/<year>/<bill>.html, the legacy bill-status page,
#           which links a bill's committee of referral by its code
#           (committeedetails.aspx?code=H26) and prints the name that code
#           carries TODAY -- in capitals where the code is retired. So 1995's
#           HB 109, whose own text prints "COMMITTEE: Corrections and
#           Criminal Justice", is filed under H26 and printed "Criminal
#           Justice and Public Safety".
#   LIST    archive_bills.json, the General Court's legacy search list of
#           each term from 1997-1998, which prints beside every bill the name
#           the code it is filed under carries today: mixed case for a code
#           still listed, capitals for a retired one. The list names a
#           bill's LAST committee, so its Finance and its committees of
#           conference are left out of the counts below.
#
# CAPITALS NAME A RETIRED CODE, NOT WHICH ONE. Mixed case is one of today's
# codes, and today's list has one per name in a chamber. Capitals say only
# that the code carrying that name is retired, and the General Court has put
# a name on a second code before: S33 and S50 are both Election Law and
# Internal Affairs, and 2005-2008's retired Rules and Enrolled Bills is not
# S45. So LIST carries a run only where the run is unbroken from a term a
# STATUS page files under the code. A name that stopped and came back is two
# runs, and the later one could be a new code under the old name: the
# Senate's Internal Affairs of 1997-2006 and 2011-2012 and the House's Local
# and Regulated Revenues of 2009-2010 print in capitals as S09 and H21 do,
# and no page on this disk files a bill of those years under either, so they
# are None until one does.
#
# A name keeps its entry for every term official() gives it, where a witness
# falls inside that run, and not past a witness that files the name's bills
# under another code: LIST puts 2009's House "Commerce" bills under H43, so
# H33's entry ends with 2008. A run no witness reaches is left out. So
# 1989-1992's House Fish and Game, whose code is on no page on this disk,
# links nowhere, while 2001-2008's is H08. Nothing here claims why a
# committee stopped: the records show a code carrying a new name, or a code
# stopping, and no more.
CODES = [
    # ---- renamed, and sitting today under the later name ----
    # STATUS 1995 HB 109 (see above); RULES 1995 names Corrections and
    # Criminal Justice, RULES 1997 Criminal Justice and Public Safety, and
    # neither names another committee on criminal justice.
    ("H", 1993, 1996, "Corrections and Criminal Justice", "H26"),
    # LIST: all 10 of the term's bills the list files with a special
    # committee are filed under H47, "...Pension Plans", as are 2015-2016's.
    # One code and one subject; the committee was formed again after a term
    # without it.
    ("H", 2011, 2012, "Special Committee on Public Employee Pensions Reform", "H47"),
    # ---- retired: a code the General Court no longer lists ----
    ("H", 1989, 1994, "Children, Youth and Juvenile Justice", "H02"),  # STATUS 1989
    ("H", 1989, 1994, "Commerce, Small Business and Consumer Affairs", "H03"),  # STATUS 1992
    # LIST: 14 of 14 of 1999-2000, filed under FISH AND GAME; the House
    # Calendar of 2006 (calendars/2006/HC064.txt) speaks of "the Fish and Game
    # Committee, formerly the Wildlife and Marine Resources Committee".
    ("H", 1993, 2000, "Wildlife and Marine Resources", "H08"),
    # STATUS 2005; LIST 54 of 54. Not 2009-2010, though official() writes the
    # name to 2010: the House's reports of those years are signed "Fish and
    # Game and Marine Resources", H42, and the two 2009 hearings and one card
    # still headed "Fish and Game" may be either -- so they link nowhere.
    ("H", 2001, 2008, "Fish and Game", "H08"),
    ("H", 1989, 1996, "Public Protection and Veterans Affairs", "H19"),  # STATUS 1989, 1992
    # STATUS 1995: a Regulated Revenues bill filed under H21, printed "LOCAL
    # AND REGULATED REVENUES", the name RULES 1997 gives it.
    ("H", 1989, 1996, "Regulated Revenues", "H21"),
    ("H", 1997, 1998, "Local and Regulated Revenues", "H21"),
    # LIST 55 of 55 in capitals, after ten years without the name: H21, or a
    # new code under its name, and nothing here says which.
    ("H", 2009, 2010, "Local and Regulated Revenues", None),
    ("H", 1991, 1994, "Economic Development", "H32"),  # STATUS 1993
    # STATUS 1995: filed under H33, printed "COMMERCE". Not H43, 2009's
    # Commerce and Consumer Affairs: LIST files 504 of 504 of 1999-2008's
    # Commerce bills under the retired COMMERCE and 2009's under H43.
    ("H", 1995, 1996,
     "Commerce, Small Business, Consumer Affairs and Economic Development", "H33"),
    ("H", 1997, 2008, "Commerce", "H33"),             # STATUS 1997, 2002, 2005
    ("H", 1995, 1998, "Judiciary and Family Law", "H35"),  # STATUS 1995, 1998
    ("S", 1989, 2004, "Banks", "S01"),                # STATUS 1992; LIST 24
    ("S", 1989, 2004, "Insurance", "S08"),            # STATUS 1992, 1995; LIST 100
    ("S", 1989, 1992, "Internal Affairs", "S09"),     # STATUS 1992
    # LIST 168 and 27, INTERNAL AFFAIRS, after gaps of four years and of
    # four: S09 or a new code under its name. The Senate's own table
    # (db/Committees.psv) numbers the codes first used in 2011 with no slot
    # for S09, which leans against it for 2011-2012 and settles nothing.
    ("S", 1997, 2006, "Internal Affairs", None),
    ("S", 2011, 2012, "Internal Affairs", None),
    ("S", 1989, 2004, "Public Affairs", "S13"),       # STATUS 2002; LIST 165
    ("S", 1989, 2004, "Public Institutions, Health and Human Services", "S14"),  # STATUS 1989-1998; LIST 116
    # STATUS 1993: an Economic Development bill filed under S18, printed
    # "ENERGY AND ECONOMIC DEVELOPMENT".
    ("S", 1991, 1998, "Economic Development", "S18"),
    ("S", 1999, 2006, "Energy and Economic Development", "S18"),  # STATUS 2000; LIST 97
    ("S", 1991, 2004, "Environment", "S19"),          # STATUS 1991, 1992; LIST 86
    ("S", 2005, 2006, "Banks and Insurance", "S23"),  # STATUS 2005; LIST 51
    # NOT S50. STATUS 2008 and LIST (46 of 46) file 2007-2008's under S33,
    # retired; S50 is the committee of the same name formed for 2017-2018.
    ("S", 2007, 2008, "Election Law and Internal Affairs", "S33"),
    # NOT S45. LIST files both of 2005-2008's under a retired RULES AND
    # ENROLLED BILLS, and no page on this disk gives that code, so they link
    # nowhere rather than to the committee formed later under the name.
    ("S", 2005, 2008, "Rules and Enrolled Bills", None),
]

_CODES_BY = {}
for _ch, _lo, _hi, _nm, _code in CODES:
    _CODES_BY.setdefault((_ch, _norm(_nm)), []).append((_lo, _hi, _code))


def _chamber(chamber):
    ch = str(chamber or "").strip().upper()[:1]
    return ch if ch in ("H", "S") else ""


def filed(name, chamber, term):
    """(True, code) where CODES places `name` in that chamber and term -- code
    None where the record says it was not today's namesake and no more --
    and (False, None) where CODES says nothing about it."""
    y = _start(term)
    for lo, hi, code in _CODES_BY.get((_chamber(chamber), _norm(name)), ()):
        if _covers(lo, hi, y):
            return True, code
    return False, None


def page_code(name, chamber, term, today):
    """The code of the committee page a committee named `name` in that chamber
    and term belongs on, or None.

    `today` is {(chamber, _norm(name)): code} for the committees the General
    Court lists now, the map every page has always been found by. CODES is
    asked first, because it is what says a name meant a different committee
    in an earlier term than it means today.
    """
    said, code = filed(name, chamber, term)
    if said:
        return code
    return today.get((_chamber(chamber), _norm(name)))


def retired():
    """{code: the name it last carried on this record} for every code in
    CODES that the General Court does not list today -- the committees that
    get a page of their own in the committees page's archived list. Whether a
    code is listed today is the caller's to say; this returns every code CODES
    names, and the names of H26 and H47 are overridden by today's list."""
    last = {}
    for ch, lo, hi, nm, code in CODES:
        if code and (code not in last or hi > last[code][0]):
            last[code] = (hi, nm)
    return {c: nm for c, (hi, nm) in last.items()}


def codes_problems():
    """[message] for every CODES entry that is not a name official() writes
    for that chamber in each of its terms, whose code is of the other
    chamber, that overlaps another entry for the same name, or that puts a
    code on a run begun after a gap in that code's runs.

    The gap is the case capitals cannot settle (see CODES): a committee that
    came back after terms without it may have come back under a new code. A
    bill-status page filing a bill of the later run under the old code would
    settle it, and would be the reason to teach this rule an exception."""
    out = []
    by_code = {}
    for ch, lo, hi, nm, code in CODES:
        if code:
            by_code.setdefault(code, []).append((lo, hi, nm))
    for code, spans in sorted(by_code.items()):
        spans.sort()
        for (lo, hi, nm), (lo2, hi2, nm2) in zip(spans, spans[1:]):
            if lo2 > hi + 1:
                out.append(f"{code}: {nm!r} {lo}-{hi}, then {nm2!r} "
                           f"{lo2}-{hi2} after a gap -- the later run may be "
                           "a new code under the old name")
    for ch, lo, hi, nm, code in CODES:
        for y in range(lo, hi, 2):
            if not known(nm, ch, f"{y}-{y + 1}"):
                out.append(f"{ch} {lo}-{hi} {nm!r}: not a {ch} committee of "
                           f"{y}-{y + 1} in OFFICIAL")
                break
        if code and code[:1].upper() != ch:
            out.append(f"{ch} {lo}-{hi} {nm!r} -> {code}: the code is the "
                       "other chamber's")
    for (ch, nn), runs in _CODES_BY.items():
        runs = sorted(runs)
        for (lo, hi, _), (lo2, hi2, _) in zip(runs, runs[1:]):
            if lo2 <= hi:
                out.append(f"{ch} {nn!r}: {lo}-{hi} and {lo2}-{hi2} overlap")
    return out


def conflicts():
    """[message] for every alias that would turn a DIFFERENT committee's
    official name into its own, in a term both cover. Empty is the rule; it
    is what "never merge two committees that coexisted" means in code."""
    out = []
    for ch, lo, hi, rx, full in _COMPILED:
        for och, olo, ohi, onm in OFFICIAL:
            if och != ch or onm == full:
                continue
            if max(lo, olo) + 1 <= min(hi, ohi) and rx.fullmatch(_norm(onm)):
                out.append(f"{ch} {lo}-{hi} {rx.pattern!r} -> {full!r} would "
                           f"also take {onm!r} ({olo}-{ohi})")
    return out


def unplaced():
    """[message] for every alias whose target is not an OFFICIAL name of that
    chamber in every term the alias covers -- a target spelt wrong, or a later
    name written onto a year before the committee carried it."""
    out = []
    for ch, lo, hi, _rx, full in _COMPILED:
        for y in range(lo, hi, 2):
            if not known(full, ch, f"{y}-{y + 1}"):
                out.append(f"{ch} {lo}-{hi} -> {full!r}: not a {ch} committee "
                           f"of {y}-{y + 1}")
                break
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    bad = conflicts() + unplaced() + codes_problems()
    for ch, word in (("H", "House"), ("S", "Senate")):
        print(word)
        for c, lo, hi, nm in sorted((r for r in OFFICIAL if r[0] == ch),
                                    key=lambda r: (r[3], r[1])):
            code = next((cd for c2, lo2, hi2, nm2, cd in CODES
                         if c2 == ch and nm2 == nm and lo2 <= lo and hi <= hi2), "")
            print(f"  {lo}-{hi}  {nm}" + (f"  [{code}]" if code else ""))
    print(f"\n{len(OFFICIAL)} names, {len(ALIASES)} aliases, "
          f"{len(CODES)} names placed on a code")
    for b in bad:
        print("  PROBLEM: " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
