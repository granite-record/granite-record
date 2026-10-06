#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-11.11
"""
The 1999-2006 docket's own vocabulary, mapped onto narrative.py's events.

Read by docket_vocab.py and by nothing else; never used on a 2017-2026
docket. The middle decade writes in mixed case and abbreviates less than the
1990s and more than today:

    Introduced and ref to Education;  HJ15, p189
    Maj Report OTP for Apr 22 (vote 15-6;Reg)
    Passed RC(255-94);  HJ44, p1072-1074 + 1090
    Committee Report, Ought to Pass W/Amendment, 6/24/99
    Signed by the Governor on 6/29/2001 Eff- 6/29/2001 Chap- 0149

The modern patterns recognise 10.3% of these 80,817 rows; with the tables
below it is 87%.

TWO TABLES, BECAUSE ORDER MATTERS. FIRST runs BEFORE narrative.PATTERNS,
for lines a modern pattern matches BADLY: "Signed by the Governor on
5/5/1999 Eff: 7/1/1999 Chap.0022" matches the modern governor pattern and
gives up neither the date nor the chapter, and "Committee Report: Majority
Report, Inexpedient to legislate" reads as a recommendation of "Majority
Report". AFTER runs only on what the modern patterns leave as "other".

The glue at the foot is what a regex cannot do: "Jan 29" and "3/18/99" into
a full date, "Passed" into motion MA, "Maj" into "Majority" (except on the
3,047 unanimous House reports, which have no minority and so are the
committee's), "ITL" into "Inexpedient to Legislate", DIV into DV -- and
join_rows, which puts a House floor day the database cut into pieces back
into the one entry the clerk typed.
"""

import re
from datetime import date, timedelta

# a meeting line that says it did not happen. clean() has already removed a
# well-formed "== CANCELLED ==", which parse_docket() flags; these are the
# spellings its flag regex misses ("==CANCELLED(Storm)==", "Hearing Cancelled",
# "CANCELLED//", "===Cancelled===", "RESCHEDULED TO A DATE UNDETERMINED").
NOCANCEL = r"(?!.*cancel)(?!.*undetermined)(?!.*\bpostponed\b)"
MON = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
       r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
# a date as this era types it: "Jan 29", "April 4, 2001", "3/18/99", "03/13/2003"
DTXT = (rf"(?:{MON}\s*\d{{1,2}}(?:st|nd|rd|th)?(?:\s*,?\s*(?:19|20)\d\d)?(?![\d/])"
        r"|\d{1,2}/\d{1,2}/(?:\d{4}|\d{2,3})(?!\d))")

# --- the House's vote tail: "VV", "RC(213-171)", "DIV(155-226)", "2/3VV",
#     "by nec 2/3DIV(238-9)", "RC (244-106)"
HVOTE = (r"(?:[,\s]*(?:by\s+)?(?:nec\.?\s*|necessary\s*)?(?:2/3|3/5)?\s*,?\s*"
         r"(?P<vote>VV|RC|DV|DIV)\b\s*\(?\s*"
         r"(?:(?P<y>\d+)\s*[-–]\s*(?P<n>\d+))?)?")

# --- House floor. The HEAD is the question; an ADOPTED clause is picked as the
# LAST one on the line, because the House types a floor day as one entry:
#   "ITL, ML RC(160-191); Rep Merrow et al Fl Am{0924}, AA RC(273-76);
#    Passed with Am VV;"  -> the last adopted question is "Passed with Am".
MOVER_H_ = r"(?:,?\s*(?:by\s+)?(?:Reps?\.?|Rep\.)\s+[A-Z][^;]*?(?:\bet\s+al\b)?)?"
H_SELF = (  # questions whose own words say they carried
    r"Passed(?:\s+with\s+(?:Am(?:endment|end)?|AM)\b\.?(?:\s*\{[^}]*\})?)?"
    r"(?:\s+and\s+(?:ref(?:erred)?\.?|Re-?Ref\w*)\s+to\s+(?P<refer>[A-Z][A-Za-z&,.' ]+?)"
    r"(?=\s*(?:\(|,|;|\bVV\b|\bRC\b|\bDIV\b|$)))?"
    r"|Adopted(?:\s+with\s+Am(?:endment|end)?\b\.?)?"
    r"|Introduced\s+and\s+adopted"
    r"|ITL\s+Report\s+[Aa]dopted"
    r"|(?:House\s+)?(?:NON-?Conc\w*|Nonc\w*)(?:\s+(?:with|w/)\s+(?:Sen(?:ate)?\s+)?Am\w*)?"
    r"(?:\s*\{[^}]*\})?,?\s*(?:and\s+)?req\w*\s+(?:Conf\w*\.?\s+Comm\w*|C\s+of\s+C|Comm\w*\s+of\s+Conf\w*)"
    r"(?=\s*(?:;|$))"
    r"|(?:House\s+)?Acced\w*\s+to\s+(?:the\s+)?(?:Sen(?:ate)?\s+)?Req\w*\s+for\s+"
    r"(?:Conf\w*\.?\s+Comm\w*|C\s+of\s+C|Comm\w*\s+of\s+Conf\w*)(?=\s*(?:;|$))"
    r"|Inexpedient\s+to\s+Legislate\s+Report\s+[Aa]dopted"
    r"|Referred\s+to\s+[A-Z][^;]*?\s+for\s+Interim\s+Study"
    r"|Recommitted(?:\s+to\s+[A-Z][\w&,' \-]*?)?(?=\s*(?:,|;|\bVV\b|\bMA\b|$))"
    r"|Indefinitely\s+Postponed"
    r"|La(?:id|y)\s+on\s+(?:the\s+)?Table"
    r"|(?:Conf(?:erence)?\.?\s+Comm(?:ittee)?|C\s+of\s+C|Comm(?:ittee)?\s+of\s+Conf\w*)\s+"
    r"(?:Rep(?:ort|t)?|Rprt|Rpt)\.?\s*(?:\{[^}]*\}\s*)?,?\s*[Aa]dopted"
)
H_MOTION = (  # questions that need MA after them
    r"ITL\s+all\s+bills\s+on\s+(?:the\s+)?table"
    r"|ITL|Inexpedient\s+to\s+Legislate|OTP/AM|OTPA|OTP|Ought\s+to\s+Pass(?:\s+with\s+Am\w*)?"
    r"|(?:Ref(?:er(?:red)?)?\.?\s+(?:for\s+|to\s+)?)?(?:Int(?:erim)?\.?\s*Study)"
    r"|LOT|Lay\s+on\s+(?:the\s+)?Table|Indefinitely\s+Postpone\w*"
    r"|(?:House\s+)?(?:Conc\w*|NON-?Conc\w*|Nonc\w*)(?:\s+(?:with|w/)\s+(?:Sen(?:ate)?\s+)?Am\w*"
    r"(?:\s*\{[^}]*\})?)?(?:,?\s*(?:and\s+)?req\w*\s+(?:Conf\w*\.?\s+Comm\w*|C\s+of\s+C|Comm\w*\s+of\s+Conf\w*))?"
    r"|(?:House\s+)?Acced\w*\s+to\s+(?:the\s+)?(?:Sen(?:ate)?\s+)?Req\w*\s+for\s+"
    r"(?:Conf\w*\.?\s+Comm\w*|C\s+of\s+C|Comm\w*\s+of\s+Conf\w*)"
    r"|(?:Conf(?:erence)?\.?\s+Comm(?:ittee)?|C\s+of\s+C)\s+(?:Rep(?:ort|t)?|Rprt|Rpt)"
    r"|(?:Taken|Removed?)\s+(?:off|from)\s+(?:the\s+)?Table"
    r"|Recommit\w*(?:\s+to\s+[A-Z][\w&,' ]*?)?"
    r"|Re-?Refer\w*\s+to\s+[A-Z][^,;]*?"
    r"|Ref(?:er(?:red)?)?\.?\s+to\s+[A-Z][^;]*?\s+for\s+Interim\s+Study"
    # a carried reconsideration undoes the question before it on the same line
    r"|Reconsider\w*"
)
H_PROC = (  # procedural questions: used only when a line has no substantive one
    r"(?:Special(?:ly)?\s+Order\w*|Moved)\s*,?\s*(?:to\s+)?[^;]*?,?\s*without\s+objection"
    r"|Special(?:ly)?\s+Order\w*\s+to\s+[^;]+?(?=" + MOVER_H_ + r"\s*,?\s*MA\b)"
    r"|Susp\w*\.?\s+(?:the\s+)?Rules?\b[^,;]*?(?=" + MOVER_H_ + r"\s*,?\s*MA\b)"
)
MOVER_H = MOVER_H_

FLOOR_H_ADOPTED = re.compile(
    r"^(?:(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+)?"      # "4/27/2000 House Nonc with Sen Am, ..."
    r"(?:.*;\s*)?"                                   # skip to the last clause that fits
    r"(?:[^;]*?(?:\bmoved?\b(?:\s+to\b)?|,)\s*)??"     # "Rep Kurk moved OTP, " in front
    r"(?P<action>(?:" + H_SELF + r")"
    r"|(?:" + H_MOTION + r")(?=" + MOVER_H + r"\s*,?\s*MA\b))"
    # the mover and MA together, so an empty mover cannot leave MA behind
    r"(?:" + MOVER_H + r"\s*,?\s*(?P<motion>MA)\b)?" + HVOTE, re.I)
FLOOR_H_PROC = re.compile(
    r"^(?:.*;\s*)?(?:[^;]*?(?:\bmoved?\b(?:\s+to\b)?|,)\s*)??"
    r"(?:Reps?\.?\s+[A-Z][\w'.]*(?:\s*(?:,|&|and)\s*[A-Z][\w'.]*)*(?:\s+et\s+al\.?)?\s+)?"
    r"(?P<action>" + H_PROC + r")(?:" + MOVER_H + r"\s*,?\s*(?P<motion>MA)\b)?" + HVOTE, re.I)
# a House line whose only question failed: "ITL, ML RC(160-191)", "OTP, ML VV",
# "Comm Report ITL, ML DIV(15-232)"
FLOOR_H_FAILED = re.compile(
    r"^(?:Comm(?:ittee)?\s+Rep(?:or)?t\s+|Rep\s+[A-Z][\w']+\s+moved\s+)?"
    r"(?P<action>" + H_MOTION + r")" + MOVER_H + r"\s*,?\s*(?P<motion>ML|MF)\b" + HVOTE, re.I)
# THE QUESTION IN QUOTATION MARKS: '"Ought NOT to Pass", MA RC(256-58)' is
# the House adopting the joint committee's report against HA 1 of 1999, the
# address for the removal of a justice, on 1 July 1999 -- the one row of
# 1999-2006 that opens on a quoted phrase. The marks kept every pattern off
# it, so the address read "Killed" over a history that stopped at the
# committee's executive session. The same words without them -- "Ought Not to
# Pass, MA, VV" on HA 1 of 2006 -- are read below, and told the same way.
FLOOR_H_QUOTED = re.compile(
    r'^"(?P<action>[^"]+)"\s*,\s*(?P<motion>MA|ML|MF)\b' + HVOTE, re.I)

# --- Senate floor: "Ought to Pass, MA, VV; OT3rdg", "Inexpedient to Legislate,
# RC 14Y-10N, MA", "Sen. Flanders Moved Laid on Table; MA, VV",
# "Ought to Pass with Amendment {1234}, AA, VV; OT3rdg, MA, VV". The motion,
# vote and tally in any order; OT3rdg and a leftover "= =" are absorbed so the
# motion that is kept is the LAST one of the question (the third-reading MA).
S_FACTS = (r"(?:(?:(?P<motion>MA|MF|ML|AA|AF)\b|(?P<vote>VV|DV|RC)\b"
           r"|(?P<y>\d+)\s*Y\s*[-–]\s*(?P<n>\d+)\s*N|O[Tt]\s*3rd\w*|=+|2/3\s*nec\.?"
           r"|by\s+nec\.?\s*(?:2/3|3/5)|\(?3/5\s*Nec\w*\)?|Division|(?:BILL\s+)?KILLED)[,;:\s]*){1,8}")
S_TOK = (r"(?:VV|DV|RC|Division|Roll\s+Call|\d+\s*Y\s*[-–]\s*\d+\s*N|O[Tt]\s*3rd\w*|=+|"
         r"(?:BILL\s+)?KILLED|2/3\s*nec\.?|by\s+nec\.?\s*(?:2/3|3/5)|\(?3/5\s*Nec\w*\)?|[,;:\s])")
S_ACTION = (r"(?!(?:MA|MF|ML|AA|AF|VV|DV|RC|O[Tt]\s*3\w*|SJ|Reps?|Division)\b)"
            # an amendment clause is never the question the line decided
            r"(?![^;,]*\b(?:Floor|Fl\.?|Committee|Comm|Maj|Min)\s+Am(?:endment|end)?\b)"
            r"(?!Am(?:endment|end)?\b)"
            r"(?P<action>(?:Sen(?:ator|\.)?,?\s+[A-Z][^;,]*?\s+)?[A-Z][^;{\[,]*?)"
            r"\s*(?:,?\s*(?:\{[^}]*\}|\[[^\]]*\]|\((?:\d\w*\s+)?New Title\)|\{?New Title\}?)\s*)*")
S_DATE = r"(?:\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\]\s*)?"   # "[05/05/05] Sen. X Accede to ..."
S_REFER = r"(?:(?:Refer\s+to|Rule\s*2[46]\s*\(Refer\s+to)\s+(?P<refer>Finance)\b)?"
# the LAST clause on the line whose own facts carry MA or AA
FLOOR_S_ADOPTED = re.compile(
    r"^" + S_DATE + r"(?:.*[;,]\s*)?" + S_ACTION + r"\s*[,;:]?\s*"
    r"(?=" + S_TOK + r"*(?:MA|AA)\b)" + S_FACTS + S_REFER, re.I)
# the first clause, when nothing on the line carried
FLOOR_S_ANY = re.compile(
    r"^" + S_DATE + S_ACTION + r"\s*[,;:]?\s*(?=" + S_TOK + r"*(?:MA|MF|ML)\b)" + S_FACTS + S_REFER, re.I)
# "OT3rdg, MA, VV" on a row of its own, after the question's row
FLOOR_S_OT3 = re.compile(r"^(?P<action>O[Tt]\s*3rd\w*)\s*,?\s*(?=[^;]*\bMA\b)" + S_FACTS, re.I)
# "Passed by Third Reading Resolution" -- the Senate's final passage, en bloc
FLOOR_S_3RD = re.compile(r"^(?P<action>Passed\s+by\s+(?:Third|3rd)\w*\s+Reading\s+Resolution)", re.I)
# "Conference Committee Report{1234}, Adopted, VV" / "Conf. Comm Report Adopted, VV"
FLOOR_CONF = re.compile(
    r"^(?P<action>(?:Conf(?:erence)?\.?\s+Comm(?:ittee)?\.?|Committee\s+of\s+Conference|C\s+of\s+C)"
    r"(?:\s+(?:Rep(?:ort|t)?|Rprt|Rpt)\.?)?)\s*"
    r"(?:\{[^}]*\}\s*|\([^)]*\)\s*|\[[^\]]*\]\s*|#?\s*\d{4}(?:-\d+)?[a-z]?\s*)?[,;:]?\s*"
    r"(?P<outcome>Adopted|adopted|Rejected|Not Adopted)"
    r"(?:" + MOVER_H + r"\s*,?\s*(?P<motion>MA|ML)\b)?" + HVOTE, re.I)

# --- a senator's motion, read as the senator's -------------------------------
# The Senate clerk names the senator who moved a question AFTER it, "Senate
# Accedes to Req for Conference Committee, Sen. McCarley, MA, VV" (77 rows of
# 1999-2000), or BEFORE it with the outcome in words, "Senator Johnson Accede
# to House Request for C of C, Adopted [05/06/04]". FLOOR_S_ADOPTED took the
# name for the question, it being the last clause before MA, so the Senate
# "adopted 'Sen. McCarley'"; FLOOR_H_ADOPTED took the House's bare "Adopted"
# -- passage -- after the comma, so 29 accessions and 28 nonconcurrences, four
# special orders and three suspensions of the rules, 1999-2006, read "the
# Senate voted to pass it" and their sitting pages "On the motion: Ought to
# Pass ... it carried in this chamber". Both are read here, before either:
# the question is the action and the senator its mover, which normalise()
# hands on the way the 1989 era does, "(Sen. Johnson)". The name is matched
# case-sensitively, so "Senate", "Sen Am" and "Sen. Floor Amendment" are not
# a senator.
S_NAME = (r"(?-i:Sen(?:ator\s+|\.\s*|\s+))"
          r"(?!(?-i:Am|Amend\w*|Floor|Fl|Comm\w*|Committee|Enrolled|Moved)\b)"
          r"(?:(?-i:[A-Z])\.\s*)?(?-i:[A-Z][\w'’\-]+)")
S_SKIP = r"(?:\s*,?\s*(?:\{[^}]*\}|\[[^\]]*\]|\((?:\d\w*\s+)?New Title\)))*"
# "Senate Concurs W/House Amendment, Sen. Pignatelli, MA, VV",
# "Conf Comm Report {1921}, Sen Gordon, MA, VV"
FLOOR_S_MOVER_AFTER = re.compile(
    r"^" + S_DATE + r"(?P<action>[A-Z][^;{\[,]*?)" + S_SKIP +
    r"\s*,\s*(?P<mover>" + S_NAME + r")\s*,?\s*"
    r"(?=" + S_TOK + r"*(?:MA|MF|ML)\b)" + S_FACTS, re.I)
# "Senator O'Hearn Nonconcur with House Am Requests Committee of Conference,
# Adopted", "Sen. Burns Non Concur with House Am {2949},(New Title), RC 12y -
# 9n, Adopted", "Sen. J. King Moved For Susp. of Rules, Adopted by 2/3rds vote"
FLOOR_S_MOVER_FIRST = re.compile(
    r"^" + S_DATE + r"(?P<mover>" + S_NAME + r")\s+(?:Moved\s+(?:to\s+|for\s+)?)?"
    r"(?P<action>[A-Z][^;{,]*?)" + S_SKIP +
    r"\s*[,;.]?\s*(?:(?:(?P<vote>RC|DV|Division|Roll\s+Call)\s*)?"
    r"(?P<y>\d+)\s*Y\s*[-–]\s*(?P<n>\d+)\s*N\s*[,;]?\s*)?"
    r"(?P<outcome>Adopted|Rejected|Not\s+Adopted)\b"
    r"(?:\s*[,;]?\s*(?P<vote_after>VV|DV)\b)?", re.I)
# The senator's name ahead of an abbreviated question that is the whole of
# it: "Sen. Krueger OTP, MA, VV", "Sen. Gordon LOT; MA, VV" -- seven rows of
# 1999-2000, whose motion read "Sen. Krueger OTP". normalise() splits the name off
# where WORDS knows the abbreviation. A question in words after the name,
# "Sen. Kenney Accede to House Request For Committee of Conference", already
# says what it is, and is left as the clerk wrote it.
LEAD_SENATOR = re.compile(r"^(?P<mover>" + S_NAME + r")\s+(?P<rest>(?-i:[A-Z][A-Z/]{1,5}))$", re.I)

# --- introduced / vacated / re-referred ---------------------------------------
_CMTE_END = (r"(?=\s*(?:[;<\[]|,?\s*\((?:See|also)|,?\s*(?:HJ|SJ|HC|SC)\s*\d|,\s*SJ\b"
             r"|,?\s*\d{1,2}/\d{1,2}/\d{2,4}|[,.\s]*$))")
INTRO = re.compile(
    r"^(?:\[?(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\]?\s+)?"
    r"Introduc(?:ed|e|tion)\s*(?:\((?:in recess(?:\s+of)?|Approved by Rules Comm\w*)\)\s*)?(?:and|&)\s+"
    # The verb however the clerk spelt it: "Refered" (HB 722 of 1999, HB
    # 1163 of 2006), "Referrred" (SB 389 of 2006), "referrring" (HB 363 of
    # 1999), "referral" (HB 581 of 1999). Read as "ref" and no more, each
    # left the rest of its word in front of the committee -- "the House ed to
    # Science, Technology and Energy committee" -- on six histories.
    r"(?:ref(?:e?r+(?:ed|ing|al)|er)?\.?)\s*(?:to\b|:)?\s*"
    r"(?P<committee>[A-Z][^;<\[]*?)" + _CMTE_END, re.I)
VACATED = re.compile(
    r"^Vacated\s+(?:from\s+[A-Z][^;]*?\s+)?(?:and\s+)?(?:Re-?)?(?:Ref(?:erred)?\.?\s+)?to\s+"
    r"(?P<committee>[A-Z][^;(]*?)(?=\s*(?:;|,\s*(?:Reps?|Sen)\b|\s(?:MA|ML)\b|\(|,?\s*(?:HJ|SJ)\s*\d|$))", re.I)
REREF_H = re.compile(
    r"^(?:ref|Re-?Referred|Referred|Refer)\.?\s+to\s+(?P<committee>(?!.*Interim\s+Study)[A-Z][^;(\[]*?)"
    # committee names carry commas ("Res, Rec & Dev"): stop at a mover, a vote or the end
    # -- or the rule it was sent under: "Refer To Finance Rule 26" (HB 618 of
    # 2003) sent the bill to "the Finance Rule 26 committee".
    r"(?:\s+committee)?(?=\s*(?:[;(\[]|Rule\b|,\s*(?:Reps?|Sen)\b|,?\s*(?:VV|RC|DIV|DV|MA)\b|,?\s*$))", re.I)

# --- meetings -----------------------------------------------------------------
HEARING = re.compile(
    NOCANCEL +
    r"^(?:(?:(?:Re-?)?Resched(?:uled|\.)?|Continued|Fin(?:ance)?(?:\s+Div\s+[IV]+)?|Joint|W\s*&\s*M|Ways\s*&\s*Means|"
    # The second committee's own name, as Finance's is: "Pub Works  Hearing
    # Jan 9" (SB 102 of 2002, passed by the House and sent to Public Works).
    r"Pub(?:lic)?\s+W(?:or)?ks|"
    r"Full\s+Comm(?:ittee)?|Re-?Ref(?:er)?|Int(?:erim)?\s+Study)\s+){0,2}"
    # "Hearings, Feb 16, Room 102, LOB, 2:20 p.m." (SB 19, SB 28 and SB 36 of
    # 1999): the Senate's notice in the plural, with its comma and nothing in
    # front of it, which read as nothing left SB 36 no hearing told once its
    # Finance hearing of 2 April was called off (cancelled_notice).
    r"(?P<kind>Public\s+Hearing|(?<![A-Za-z]\s)Hearings(?=\s*,)|Hearing)"
    r"(?:\s+on\s+(?:the\s+)?(?:Prop(?:osed)?\.?\s+(?:Comm\s+)?Am(?:endment|end)?\.?|Amendment)"
    r"(?:\s*\{\d+\w?\})?)?(?:\s+(?:and|&)\s+Exec(?:utive)?\.?\s+Sess(?:ion)?)?"
    r"\s*[;,:]?\s*(?:=\s*)*(?:RESCHEDULED\s*=*\s*)?"
    r"(?P<date>" + DTXT + r")", re.I)
HEARING = re.compile(NOCANCEL + r"^(?:=\s*)*" + HEARING.pattern[len(NOCANCEL) + 1:], re.I)
WORK = re.compile(
    NOCANCEL +
    r"^(?:=\s*)*(?:[\w&./()\-]+\s+){0,6}?"
    r"(?P<kind>(?:Subcom(?:mittee)?|Sub-?committee|Full\s+Comm(?:ittee)?)?\s*Work\s*"
    r"(?:&\s*Exec(?:utive)?\s*)?Sess(?:ion)?s?|(?<![\w ])Meeting(?=\s*[;,]))\s*[;:,]?\s*(?:=\s*)*"
    r"(?:\((?:if needed|Jt[^)]*|[^)]*after[^)]*)\)\s*)?(?P<date>" + DTXT + r")", re.I)
EXEC = re.compile(
    NOCANCEL +
    r"^(?:[\w&./()\-]+\s+){0,6}?Exec(?:utive)?\.?\s+Sess(?:ion)?s?(?:\s+on\s+Pending\s+Legislation)?\s*[;:,]?\s*"
    r"(?P<date>" + DTXT + r")", re.I)
CONF_MEET = re.compile(
    NOCANCEL +
    r"^(?:=\s*)*(?:Continued\s+|\**\s*RECESSED\s*\**\s*)?"
    r"(?:(?:Conf(?:erence)?\.?\s+Comm(?:ittee)?\.?|Comm(?:ittee)?\s+of\s+Conf(?:erence)?|C\s+of\s+C|Conference\s+Committee)"
    r"\s*;?\s*(?:Meeting|mtg)s?|Committee\s+of\s+Conference)\s*[:;,]?\s*(?:=\s*)*"
    r"(?P<date>" + DTXT + r")", re.I)

# --- committee reports ----------------------------------------------------------
# House: "Maj Report ITL for Feb 10 (vote 19-6;Reg)", "Min Report OTP/AM",
# "Comm Rprt: OTP/AM {0830h} for March 7 (vote 18-0; CC)", "Fin Maj Report OTP
# for June 22 (vote 23-0;CC)", "Comm Report for Jan 4, 2006;  Refer Interim
# Study  (vote 18-0; CC)". REFUSED when the line carries a floor outcome -- the
# House also writes the chamber's vote ON the report as "Comm Report ITL, ML".
H_REC = (r"ITL|OTP/AM|OTPA|OTP|Ought\s+to\s+Pass(?:\s+with\s+Am\w*)?|Inexpedient\s+to\s+Legislate"
         r"|RE-?REF\w*|Re-?Refer\w*(?:\s+to\s+[A-Z][\w&, ]*?)?"
         r"|(?:Ref(?:er)?\.?\s+(?:for\s+|to\s+)?)?Int(?:erim)?\.?\s*Study|Retain\w*"
         r"|(?:Without|No)\s+Rec\w*|Adopt\w*|Concur|Nonconcur|Indefinitely\s+Postpone\w*"
         r"|Lay\s+on\s+(?:the\s+)?Table")
REPORT_H = re.compile(
    r"^(?!.*\b(?:MA|ML|MF)\b)(?!.*\b(?:Passed|adopted)\b)"
    r"(?:(?:Fin(?:ance)?|W\s*&\s*M|Ways\s*&\s*Means|Pub(?:lic)?\s+W(?:or)?ks|RE-?REF|Re-?Ref(?:erred)?|Int(?:erim)?\s+Study"
    r"|Ret(?:ained)?|Educ|Elec|ED\s*&\s*A|Comm)\s+){0,2}"
    r"(?:(?P<side>Maj\w*|Min\w*)\.?\s+(?:Comm(?:ittee)?\s+)?|Comm(?:ittee)?\s+)"
    r"(?:Rep(?:or)?t|Rprt|Rpt)\.?\s*:?\s*"
    r"(?:for\s+[^;:]*?[;:]\s*)?"
    r"(?P<rec>" + H_REC + r")"
    r"(?:\s*[{(]\s*#?(?P<amend>\d{4}[a-z]?)\s*[})])?"
    r"(?P<rest>.*)$", re.I)
# Senate: "Committee Report; Ought to Pass [05/19/05]; SC20", "Committee
# Report, Ought to Pass W/Amendment, 4/22/99", "Committee Report; Ought to Pass
# with Amendment{1234} [05/05/05]", "Committee Report: Majority Report,
# Inexpedient to legislate (6/29/99)"
REPORT_S_SIDE = re.compile(   # "Committee Report: Majority Report, Inexpedient to legislate"
    r"^Committee\s+Report\s*[;,:]?\s*(?P<side>Major\w*|Minor\w*)\s+(?:Report|Rpt\.?)\s*,?\s*"
    r"(?P<rec>[A-Z][^\[{(;,0-9]*?)(?:\s*[{(]\s*#?(?P<amend>\d{4}[a-z]?)\s*[})])?"
    r"(?=\s*(?:[\[{(;,]|\d|\bVote\b|$))(?P<rest>.*)$", re.I)
REPORT_S = re.compile(
    r"^(?:(?P<side>Major\w*|Minor\w*)\s+)?Committee\s+Report\s*[;,:]?\s*"
    r"(?P<rec>(?!Adopted)(?!Filed)(?!Majority)(?!Minority)[A-Z][^\[{(;,0-9]*?)"
    r"(?:\s*[{(]\s*#?(?P<amend>\d{4}[a-z]?)\s*[})])?"
    r"(?=\s*(?:[\[{(;,]|\d|\bVote\b|$))(?P<rest>.*)$", re.I)

# --- amendments ---------------------------------------------------------------
# "Committee Amendment{1981}, (New Title), AA, VV", "Sen. Clegg Floor
# Amendment{1462}, AA, VV", "Enrolled Bill Amendment {1878}, (New Title),
# Adopted", "Fl Am{1765}, AA RC(235-53)". A motion is REQUIRED: a bare
# "Committee Amendment, {1417}" is the number of a proposed amendment, and
# describe() calls every amendment without AA/Adopted "rejected". MA is refused
# for the same reason (describe reads MA on an amendment as not adopted).
AMEND_NOT_THE_FLOORS = (
    # a House floor day typed as one entry ends in the bill's own outcome
    # ("Comm Am{0236}, AA VV; ...; Passed with Am VV"): that line is the floor's
    r"^(?!.*;\s*[^;]*?\b(?:Passed|Adopted\s+with|ITL|OTP\w*|Ought\s+to\s+Pass|Inexpedient|Laid|Int\w*\s+Study"
    r"|Indefinitely|Recommit\w*|Re-?Ref\w*|Referred)\b)")
AMEND_MOVER = (
    r"(?:(?P<mover>(?:Rep|Sen)\.?\s+(?:(?!Enrolled\b|Committee\b|Floor\b|Fl\b|Comm\b|FL\b)"
    r"[A-Z][\w'.\-]*\s+){1,3}))?")
AMEND_BODY = (
    # "Comm AM" (House, 2005-06) is the committee's amendment; describe() says
    # so only if what contains "Committee", which normalise() supplies
    r"(?P<what>(?:Enrolled\s+Bill\s+|Committee\s+|Comm\.?\s+|Maj(?:ority)?\.?\s+|Min(?:ority)?\.?\s+"
    r"|Floor\s+|Fl\.?\s+)?Am(?:endment|end\.?)?)"
    r"\s*,?\s*(?:\(New Title\)\s*)?(?:[{(\[]|#)\s*#?(?P<num>\d{4}[a-z]?)\b\s*[})\]]?:?\s*,?\s*"
    r"[;,]?\s*(?:[({\[]?\s*(?:\d\w*\s+)?New\s*Title\s*[)}\]]?\s*[,;]?\s*|<N?NT>\s*,?\s*)?[;,]?\s*"
    # an outcome for THIS amendment, and no MA ahead of it (MA after it is
    # the third reading: "Floor Amendment {1929}, AA, VV, OT3rdg, MA, VV")
    r"(?=[^;]*\b(?:AA|AF|AL|Adopted)\b)(?!(?:(?!\b(?:AA|AF|AL|Adopted)\b)[^;])*\bMA\b)"
    r"(?:(?:(?P<motion>AA|Adopted|AF|AL)\b|(?P<vote>VV|DV|RC)(?:\b|(?=\d))"
    r"|(?P<y>\d+)\s*Y?\s*[-–]\s*(?P<n>\d+)\s*N?|[\dYN]+\s*-\s*[\dYN]+|Division|\(|\))[,;\s]*){1,6}")
AMEND_OLD = re.compile(AMEND_NOT_THE_FLOORS + AMEND_MOVER + AMEND_BODY, re.I)
ENROLLED_OLD = re.compile(
    r"^(?:\(?(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\)?\s+)?Enrolled(?:\s+Bill)?\s*[,;]?\s*"
    r"(?:(?P<motion>Adopted)\b|(?=(?:HJ|SJ)\s*\d|\[|$))", re.I)
UNSIGNED_OLD = re.compile(
    r"^Became\s+Law\s+Without\s+(?:the\s+)?Signature\s*(?:on\s+)?(?P<date>\d{1,2}/\d{1,2}/\d{4})?"
    r"(?=(?:.*?\bCha?p(?:ter|t)?\.?\s*[:.\-,]?\s*0*(?P<chapter>\d+))?)", re.I)

# --- the rest -----------------------------------------------------------------
CONSENT_OFF_OLD = re.compile(
    r"^Removed\s+from\s+(?:the\s+)?Cons(?:ent)?\.?\s*Cal(?:endar)?\b", re.I)
DIED_OLD = re.compile(r"^Died\s+(?:on\s+(?:the\s+)?Table\b|\(All\s+bills\s+Laid\s+on\s+Table)", re.I)
RETAINED_OLD = re.compile(r"^Retained\s+in\s+Comm", re.I)
INTERIM_OLD = re.compile(
    r"^Int(?:erim)?\.?\s+Study\s+Report\s*:\s*(?P<rec>[A-Za-z][A-Za-z ,.]*?(?:\s+(?:IN\s+)?\d{4})?)\s*"
    r"(?:\(\s*Vote\s*(?P<y>\d+)\s*-\s*(?P<n>\d+)\s*;?\s*(?P<cal>CC|RC)?\s*\))?\s*$", re.I)
# "Governor's Veto Sustained RC(210-145)", "Veto Sustained -failed nec 2/3- RC(212-160)",
# "Veto Overridden RC(290-78)"
VETO_OLD = re.compile(
    r"^(?=[^;]*\b(?:RC|DIV)\s*\()"               # the old House tally "RC(212-160)"
    r"(?:Governor'?s\s+)?Veto\s+(?P<outcome>Sustained|Overridden)\b"
    r"(?:[^;]*?(?P<vote>RC|VV|DV|DIV)\s*\(?\s*(?P<y>\d+)\s*Y?\s*[-–]\s*(?P<n>\d+))?", re.I)
# "Signed by the Governor on 5/5/1999 Eff: 7/1/1999 Chap.0022",
# "Signed by Governor, 5/2/06, Eff. date 1/1/07, Chapter 0075". The date must
# follow at once, so modern "Signed by Governor Ayotte 06/27/2025" still falls
# to the existing pattern.
GOV_OLD = re.compile(
    r"(?P<what>Signed\s+by\s+(?:the\s+)?Governor|Vetoed\s+by\s+(?:the\s+)?Governor|Governor\s+signed)"
    r"\s*,?\s*(?:on\s+)?[,;]?\s*\[?\s*(?P<date>\d{1,2}/\d{1,2}/\d{2,4})(?![\d/])\s*\]?"
    # "Eff: 7/1/1999", "Eff- 6/28/2001", "Eff. date 7/9/06"; "Chap.0022",
    # "Chap- 0126", "Chap, 0070", "Chapter: 0295"
    # lookaheads, so the two may come in either order (modern: Chapter first)
    r"(?=(?:.*?\bEff\w*\.?\s*(?:date\s*)?[:.\-,]?\s*(?P<eff>\d{1,2}/\d{1,2}/\d{2,4}))?)"
    r"(?=(?:.*?\bCha?p(?:ter|t)?\.?\s*[:.\-,]?\s*0*(?P<chapter>\d+))?)", re.I)

REPORT_S_SIDE2 = re.compile(   # "Committee Majority Report, Ought to Pass W/Amendment, 4/8/99"
    r"^Committee\s+(?P<side>Major\w*|Minor\w*)\s+(?:Report|Rpt\.?)\s*[;,:]?\s*"
    r"(?P<rec>[A-Z][^\[{(;,0-9]*?)(?:\s*[{(]\s*#?(?P<amend>\d{4}[a-z]?)\s*[})])?"
    r"(?=\s*(?:[\[{(;,]|\d|\bVote\b|$))(?P<rest>.*)$", re.I)
# "Notwithstanding the Governors Veto Shall the Bill Pass, RC 10y - 14n, Veto Sustained"
VETO_S_OLD = re.compile(
    r"^Notwithstanding\s+the\s+Governor'?s\s+Veto,?\s*Shall\s+the\s+Bill\s+(?:Pass|Become\s+Law)"
    r"[,;:=\s]*(?:(?P<vote>RC|VV|DV)\s*(?P<y>\d+)\s*Y?\s*[-–]\s*(?P<n>\d+)\s*N?)?[,;:=\s]*"
    r"Veto\s+(?P<outcome>Sustained|Overridden)", re.I)
# a special order with no vote recorded on the line: "Special Order to February 3, 2000"
FLOOR_H_SPECIAL = re.compile(
    r"^(?!.*\b(?:MA|ML|MF)\b)(?:Without\s+Objection,?\s*)?"
    r"(?P<action>Spec(?:ial)?\.?\s+Order\w*\s*,?\s*(?:to\s+)?[^;]*?)\s*(?:;|$)", re.I)

OLD_FIRST = [
    ("governor", GOV_OLD),
    # the existing VETO_HOUSE_RE takes the outcome but not "RC(212-160)"
    ("veto_override", VETO_OLD),
    # the existing report pattern reads "Committee Report: Majority Report,
    # Inexpedient to legislate" as a report whose recommendation is "Majority Report"
    ("report", REPORT_S_SIDE),
]
OLD = [
    ("introduced", INTRO),
    ("vacated", VACATED),
    ("hearing", HEARING),
    ("worksession", WORK),
    ("exec", EXEC),
    ("conference_meeting", CONF_MEET),
    ("veto_override", VETO_S_OLD),
    ("unsigned_law", UNSIGNED_OLD),
    ("amendment", AMEND_OLD),
    ("enrolled", ENROLLED_OLD),
    ("floor", FLOOR_CONF),
    ("floor", FLOOR_S_3RD),
    ("floor", FLOOR_S_OT3),
    ("floor", FLOOR_S_MOVER_AFTER),
    ("floor", FLOOR_S_MOVER_FIRST),
    ("floor", FLOOR_H_QUOTED),
    ("floor", FLOOR_H_ADOPTED),
    ("floor", FLOOR_S_ADOPTED),
    ("floor", FLOOR_H_PROC),
    ("floor", FLOOR_H_FAILED),
    ("floor", FLOOR_S_ANY),
    ("floor", FLOOR_H_SPECIAL),
    ("report", REPORT_H),
    ("report", REPORT_S_SIDE2),
    ("report", REPORT_S),
    ("consent_off", CONSENT_OFF_OLD),
    ("died", DIED_OLD),
    ("interim_report", INTERIM_OLD),
    ("rereferred", REREF_H),
]


# ------------------------------------------------------- the glue
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# A ROW THAT GIVES A HEARING'S NEW DAY AND NAMES NO HEARING IN A WAY THE
# PATTERNS ABOVE READ (7 October 2026). The Senate of 1999-2000 wrote the move
# a dozen ways, and every one was read as no event at all, so the history told
# the hearing on the day it was moved from and never on the day it was held:
#
#   "==RESCHEDULED== Feb.3, Room 104, LOB, 8:30 a.m.; SC3, Pg. 6"   (SB 373)
#   "=RESCHEDULED= Hearing  April 24, Room 102, LOB, 2:30 pm; SC23"  (HB 1195)
#   "Hearing =RESCHEDULED= Hearing May 1, Room102, LOB, 11:30 a.m."  (HB 1335)
#   "==CANCELED AND RESCHEDULED== Feb.11, Room 103, SH, 10:00 a.m."  (SB 405)
#   "(RESCHEDULED) Feb. 14, 10:00 a.m. Rooms 206-208, LOB"           (SB 324)
#   "New Date , Feb. 22 , 2:30 p.m., Room 102 , LOB"                 (SB 326)
#   "Hearing Rescheduled, 3/16/99, Room 104, LOB, 2:45 p.m."         (SB 155)
#   "Rescheduled Hearings, 4/2/99, Room 103, SH, 9:00 a.m."          (SB 186)
#   "Rescheduled Hearing, 3/24/99, Room 103, LOB, 9:00 a.m. Hearing Cancelled"
#
# The last is the notice of the 24th and the cancellation is the earlier
# hearing's: Senate Calendar 12a of 1999 prints SB 79 on 24 March
# "RESCHEDULED FROM MARCH 17TH", and Calendar 11 SB 27's "RESCHEDULED TO
# MARCH 17TH" from the 10th. HB 1195's and HB 1335's hearings of 16 May 2000
# were told after the Senate had passed the bills; Calendar 23 prints both
# rescheduled, to 24 April and 1 May, and "Cancelled" under 16 May.
#
# Each is the notice of the day it names (rescheduled_notice), read only
# where nothing else reads the row, and its words are the rescheduling row's
# (narrative.RESCHEDULING), which moves the earlier notice there. Not a time
# or room change on the same day ("==TIME CHANGE== Jan. 25", "==NEW TIME==
# Feb.10"), and not a recessed hearing's new day ("==RECESSED== NEW DATE==
# Feb.9", "Hearing == RE-CONVINED = May 3"), which sat and went on.
#
# And the notice the Senate entered once a hearing it had put off "TO A DATE
# UNDETERMINED" had its day (decision 59b): "==HEARING== April 24, Room 102,
# LOB, 2:00 p.m.; SC21, Pg.13" (HB 618 of 2000, after "Hearing; RESCHEDULED TO
# A DATE UNDETERMINED" over its hearing of 28 March), which Senate Calendars
# 21 to 24 print on 24 April. Read as nothing, the bill's one Senate hearing
# told was the one called off. The only row of its kind on disk.
RESCHEDULED_TO = re.compile(
    r"^\W*(?:"
    r"(?:Hearing\s*)?=+\s*(?:CANCELL?ED\s+AND\s+)?(?:RESCHEDULED|HEARING)\s*=+\s*,?\s*(?:Hearing\s*)?"
    r"|\(\s*RESCHEDULED\s*\)\s*"
    r"|New\s+Date\s*,\s*"
    r"|(?:Hearing\s+Rescheduled|Rescheduled\s+Hearings?)\s*,\s*"
    r")(?P<date>" + DTXT + r")"
    r"(?:(?!\bcancel|\brecess|\bcontinu|\breconven|\bre-?con|\bre-?open|\bundetermined)"
    r"[^;])*?(?:;|$|\bHearing\s+Cancell?ed\s*$)", re.I)
# "Rescheduled Hearing, 3/24/99 ... Hearing Cancelled" only with those words
# last; another cancellation or a recess anywhere in the row is not this.
RESCHEDULED_TO_CANCEL = re.compile(r"\bcancel", re.I)


def rescheduled_notice(desc, created):
    """The hearing notice a row that gives a hearing's new day is
    (RESCHEDULED_TO), as {"_type": "hearing", "kind", "date"}, or None."""
    m = RESCHEDULED_TO.match(desc or "")
    if not m or created is None:
        return None
    rest = (desc or "")[m.end("date"):]
    if RESCHEDULED_TO_CANCEL.search(rest) and not re.search(
            r"\bHearing\s+Cancell?ed\s*$", rest, re.I):
        return None
    if RESCHEDULED_TO_CANCEL.search(desc[:m.start("date")]) and not re.search(
            r"CANCELL?ED\s+AND\s+RESCHEDULED", desc[:m.start("date")], re.I):
        return None
    day = full_date(m.group("date"), created, forward=True)
    if not day:
        return None
    return {"_type": "hearing", "kind": "Hearing", "date": day, "_era": "1999:rescheduled"}


# A ROW THAT SAYS ONLY THAT A HEARING WAS CALLED OFF (decision 59b, 7 October
# 2026). The Senate of 1999 typed the cancellation as a row of its own and
# named no meeting: "Hearing Cancelled" and "Hearing cancelled" (SB 12, SB 36,
# SB 37, SB 45 and SB 131, entered on 16 March over their Finance hearings of
# 2 April, which Senate Calendar 15 prints "CANCELLED"), "Hearing Cancelled
# Due To Town Meeting Day" (SB 55, SB 58, SB 107, SB 114 and SCR 2, over their
# hearings of 9 March, Town Meeting Day), or with the day: "3/8/99 Hearing
# Cancelled" (SB 24), "Hearing, 3/10/99 Cancelled" (SB 66). And 2002's
# "Hearing === CANCELLED === TO BE RESCHEDULED AT A LATER DATE ===; SC3" (SB
# 344, over its hearing of 16 January) and 2000's "Hearing; RESCHEDULED TO A
# DATE UNDETERMINED" (HB 618, over its hearing of 28 March, which Senate
# Calendar 19 no longer prints). The era's patterns refuse a row that says
# "cancel" (NOCANCEL) and read these as nothing, so the history told the
# hearing each one called off. Each is a hearing called off: on the day it
# names, or, naming none, the bill's hearing it was entered over
# (narrative._cancelled_by).
CANCELLED_ONLY = re.compile(
    r"^\W*(?:(?P<before>" + DTXT + r")\s+)?Hearing\s*"
    r"(?:,\s*(?P<after>" + DTXT + r")\s*)?"
    r"(?:=+\s*)?Cancell?ed\b\s*=*\s*"
    r"(?:Due\s+To\s+[A-Za-z ]{3,30}?|TO\s+BE\s+RESCHEDULED(?:\s+AT\s+A\s+LATER\s+DATE)?\s*=*)?"
    r"\s*(?:;\s*SC\s*\d+[A-Za-z]?(?:\s*,\s*P(?:g)?\.?\s*\d+)?)?\s*$"
    r"|^\W*Hearing\s*;\s*RESCHEDULED\s+TO\s+A\s+DATE\s+UNDETERMINED\s*$", re.I)


def cancelled_notice(desc, created):
    """A row that says only that a hearing was called off (CANCELLED_ONLY), as
    {"_type": "hearing", "date", "_cancels": True}, with "_cancels_next" where
    it names no day; or None."""
    m = CANCELLED_ONLY.match(desc or "")
    if not m or created is None:
        return None
    said = m.group("before") or m.group("after")
    day = full_date(said, created, forward=True) if said else None
    if said and not day:
        return None
    got = {"_type": "hearing", "kind": "Hearing", "_era": "1999:cancelled", "_cancels": True}
    if day:
        got["date"] = day
    else:
        got["_cancels_next"] = True
    return got


def full_date(txt, created, forward=False):
    """mm/dd/yyyy from "Jan 29", "April 4, 2001", "3/18/99", "06/21/000"; else None.

    forward: the line is a NOTICE of a meeting to come, so a month-and-day
    more than 45 days before the row's created date belongs to the next year
    (a December notice for a January hearing)."""
    t = (txt or "").strip().strip("[]").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})$", t)
    try:
        if m:
            mo, d, y = int(m[1]), int(m[2]), m[3]
            yr = (int(y) if len(y) == 4 else
                  (1900 + int(y) if int(y) >= 50 else 2000 + int(y)) if len(y) == 2
                  else created.year)                      # "06/21/000": a typo
            return date(yr, mo, d).strftime("%m/%d/%Y")
        m = re.match(r"([A-Za-z]{3})[a-z]*\.?\s*(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?$", t)
        if not m or m[1].lower() not in MONTHS:
            return None
        mo, d = MONTHS[m[1].lower()], int(m[2])
        yr = int(m[3]) if m[3] else created.year
        out = date(yr, mo, d)
        if not m[3] and forward and out < created.date() - timedelta(days=45):
            out = date(yr + 1, mo, d)
        return out.strftime("%m/%d/%Y")
    except ValueError:
        return None


# types whose line carries no date because the clerk entered it the day it
# happened: the created date IS the event date (measured in e5).
SAME_DAY = {"introduced", "vacated", "floor", "rereferred", "consent_off",
            "amendment", "enrolled"}
NOTICE = {"hearing", "worksession", "exec", "conference_meeting"}

# the era's words -> the phrase narrative.RECOMMENDATION already knows, and
# which build_site_v2.DISPOSED / adopted_floor read. From docket_abbrev.json:
# ITL, OTP, OTP/AM, OTPA, LOT, IS, CONC, NONCONC, RE-REF, REF FOR STUDY.
WORDS = [
    (r"^(?:ITL|Inexpedient\s+to\s+Legislate)(?:\s+Report)?(?:\s+adopted)?$"
     r"|^ITL\s+all\s+bills\s+on\s+(?:the\s+)?table$", "Inexpedient to Legislate"),
    (r"^(?:OTP/AM|OTPA|Ought\s+to\s+Pass\s+as\s+Amended.*|Passed\s+with\s+Am.*|Adopted\s+(?:with|as)\s+Am.*)$",
     "Ought to Pass with Amendment"),
    # "Adopted" stays inside "ought to pass|adopted", the words build_site_v2's
    # adopted_floor reads for a one-chamber resolution.
    (r"^(?:OTP|Passed|Adopted|Introduced\s+and\s+adopted"
     r"|Passed\s+by\s+(?:Third|3rd)\w*\s+Reading\s+Resolution)$", "Ought to Pass"),
    (r"^Passed\s+and\s+ref.*$", "Ought to Pass"),
    (r"^(?:Ref(?:er(?:red)?)?\.?\s+(?:for\s+|to\s+)?)?Int(?:erim)?\.?\s*Study$"
     r"|^Referred\s+to\s+.*\bfor\s+Interim\s+Study$", "Refer for Interim Study"),
    (r"^(?:LOT|La(?:id|y)\s+on\s+(?:the\s+)?Table)$", "Lay on Table"),
    (r"^Indefinitely\s+Postpone\w*$", "Indefinitely Postpone"),
    (r"^(?:House\s+)?NON-?Conc\w*.*$|^(?:House\s+)?Nonc\b.*$", "Nonconcur"),
    (r"^(?:House\s+)?Conc\w*.*$", "Concur"),
    (r"^(?:RE-?REF\w*|Re-?Refer\w*(?:\s+to\s+Committee)?|Recommit\w*(?:\s+to\s+committee)?)$",
     "Rerefer to Committee"),
    (r"^Retain\w*$", "Retain"),
]
WORDS = [(re.compile(p, re.I), w) for p, w in WORDS]
SELF_ADOPTING = re.compile(
    r"^(?:Passed|Adopted|Introduced\s+and\s+adopted|ITL\s+Report|Inexpedient\s+to\s+Legislate\s+Report"
    r"|Referred\s+to\b|Recommitted|Indefinitely\s+Postponed|La(?:id|y)\s+on\s+(?:the\s+)?Table"
    r"|Conf|C\s+of\s+C|Comm(?:ittee)?\s+of\s+Conf"
    r"|(?:House\s+)?(?:NON-?Conc|Nonc|Acced|Concurred\b)"
    r"|(?:Special|Moved).*without\s+objection$"
    r"|Spec(?:ial)?\.?\s+Order)", re.I)


# A QUESTION WHOSE WORDS SOUND CARRIED CAN STILL HAVE LOST. FLOOR_H_ADOPTED
# takes "Lay on Table" and "Passed" as questions that say they carried, so
# normalise() made each one adopted without reading the clause's own result:
# "Lay on Table, ML, RC (140-198)" (2006 HB 162) and "Sen. Larsen Moved Laid
# on Table Division 8Y-15N, MF" (2005 SB 42) told as tabled, and "Passed with
# AM {0795h}, ML, RC (141-181)" told 2006 HB 1240 as passed on the day passage
# failed -- as it did HB 1621, HB 1594, CACR 37 and HB 1714 that spring.
# Measured on the rows as cut, 98 events in 91 histories of 1999-2006 read
# that way, and no other term's docket has the shape. The result written in
# the question's own clause, from its words to the next ";", is the result --
# or, where the clause has none, the clause after it when that holds nothing
# but a vote and a result: the clerk put a semicolon between the question and
# its outcome in "Sen. Fernald Moved Laid on Table; Division 8y-14n, MF,VV"
# (SB 301 of 2000) and "Rep Vaillancourt moved lay on table; MF VV" (SB 1 of
# the 2006 special session), both told as tabled.
LOST_AFTER = re.compile(
    r"[^;]*?\b(?P<r>ML|MF)\b"
    r"|(?:(?!\b(?:MA|AA|AL|AF)\b)[^;])*;"
    r"(?:\s|[,\-–()/:.]|\d+\s*[YyNn]?\b|(?:RC|DV|DIV|Div|Division|VV|Roll\s+Call)\b)*?"
    r"\b(?P<r2>ML|MF)\b")


# The House's vote as HVOTE reads it, and with the comma the 2006 clerk put
# between the kind and the count: "Lay on Table,  ML, RC, (144-195)".
LOST_VOTE = re.compile(
    r"[,\s]*(?:by\s+)?(?:nec\.?\s*|necessary\s*)?(?:2/3|3/5)?\s*,?\s*"
    r"(?P<vote>VV|RC|DV|DIV)\b\s*,?\s*\(?\s*(?:(?P<y>\d+)\s*[-–]\s*(?P<n>\d+))?", re.I)
VOTE_AHEAD = re.compile(r"\d|\b(?:Div(?:ision)?|DIV|RC|DV|VV|Roll\s+Call)\b")


def _lost(ev, action):
    """"ML" or "MF" where the line's own clause for this question says it lost.

    AND THE HOUSE'S COUNT COMES AFTER THE RESULT, "Lay on the Table, ML
    RC(161-182)", where the pattern that took the question's words looks for
    it straight after them and finds "ML" in the way. So a question read as
    lost here takes the vote written after its result, where it has none:
    without it HB 633 of 1999's tabling motion, lost 161-182 on a roll call,
    sat with no vote beside two passages and a reconsideration that each had
    theirs. The Senate writes its count BEFORE the result ("Moved Laid on
    Table; Division 8y-14n, MF,VV"); where anything of a vote stands between
    the question and its result, nothing is taken from after it."""
    raw = ev.get("_raw") or ""
    i = raw.rfind(action) if action else -1
    m = LOST_AFTER.match(raw, i + len(action)) if i >= 0 else None
    if not m:
        return None
    if not ev.get("vote") and not VOTE_AHEAD.search(m.group(0)):
        v = LOST_VOTE.match(raw, m.end())
        if v and v.group("vote"):
            kind = v.group("vote").upper()
            ev["vote"] = "DV" if kind == "DIV" else kind
            ev["y"], ev["n"] = v.group("y"), v.group("n")
    return m.group("r") or m.group("r2")


# A SENATE QUESTION AND A THIRD READING ON ONE LINE, WITH TWO OUTCOMES. The
# Senate pattern reads a third reading's facts as the question's own, because
# "Ought to Pass, MA, VV, OT3rdg, MA, VV" is one passage, and keeps the last
# result it finds. Where the two came out differently they are two results:
#
#   "Sen. Gordon Moved Rerefer to Committee, RC 10Y-14N, MF, OT3rdg, MA, VV"
#   (SB 108 of 1999) is a recommittal that failed 10-14, and then the third
#   reading ordered. Read as one, the Senate "voted to send it back to
#   committee on a voice vote 10-14".
#
#   "Ought to Pass with Amendment {3073}[New Title], AA, VV, Ordered to 3rd
#   Reading, RC 12y -12n, MF" (SB 219 of 2000) is the amendment adopted and
#   the third reading failing on a tie. Read as one, AA became MA and the
#   Senate "voted to pass it with changes".
#
# A motion that lost keeps its own result, and a passage whose third reading
# lost takes that one; the vote and tally are the ones written beside the
# result kept.
THIRD = re.compile(r"\b(?:O[Tt]\s*3rd\w*|Ordered\s+to\s+3rd\s+Reading)\b")
S_RESULT = re.compile(r"\b(?P<r>MA|MF|ML|AA|AF)\b")
S_VOTE_KIND = re.compile(r"\b(?P<v>RC|DV|DIV|Div|Division|VV|Roll\s+Call)\b")
S_TALLY = re.compile(r"(?P<y>\d+)\s*Y\s*[-–]\s*(?P<n>\d+)\s*N\b", re.I)


def _third_apart(ev, action):
    """Mutates a Senate floor event whose question and third reading, one
    line, came out differently (above)."""
    raw = ev.get("_raw") or ""
    i = raw.rfind(action) if action else -1
    if i < 0:
        return
    tail = raw[i + len(action):].split(";", 1)[0]
    t = THIRD.search(tail)
    if not t:
        return
    own, third = tail[:t.start()], tail[t.end():]
    r_own = [m.group("r") for m in S_RESULT.finditer(own)]
    r_third = [m.group("r") for m in S_RESULT.finditer(third)]
    if not r_own or not r_third:
        return
    if r_own[-1] in ("MF", "ML") and r_third[-1] == "MA":
        keep, motion = own, r_own[-1]
    elif r_own[-1] == "AA" and r_third[-1] in ("MF", "ML"):
        keep, motion = third, r_third[-1]
    else:
        return
    ev["motion"] = motion
    v = S_VOTE_KIND.search(keep)
    if v:
        k = v.group("v").upper()
        ev["vote"] = "RC" if k.startswith(("RC", "ROLL")) else "VV" if k == "VV" else "DV"
    y = S_TALLY.search(keep)
    ev["y"], ev["n"] = (y.group("y"), y.group("n")) if y else (None, None)


# AN AMENDMENT TOLD FROM ITS OWN CLAUSE HAS ITS RESULT AND VOTE IN IT. The
# amendment pattern was written for whole lines of both chambers and reads
# neither the House's "DIV(78-262)" nor a result behind "(NT)" or inside
# "{4542 (to Sec.5)}", so "Rep Hinman Fl Am{3963}, AL DIV(78-262)" came out
# rejected with no vote and "Rep Mirski Fl Am{2223}(NT), AL RC(53-296)" with
# no result at all -- which the bill page's amendment list shows as an
# amendment nobody decided. In a clause that is one amendment and nothing
# else, the result is the clause's AA, AL or AF and the vote is what the
# House wrote after it. Only for a clause of a split line (docket_vocab.
# questions): a whole line's amendment is read as it always was.
CLAUSE_AMENDMENT = "1999:clause:amendment"
MINORITY_AMENDMENT = "Minority Amendment"
AMEND_RESULT = re.compile(r"\b(?P<motion>AA|AL|AF)\b" + HVOTE)


def _clause_amendment_vote(ev):
    m = AMEND_RESULT.search(ev.get("_raw") or "")
    if not m:
        return
    ev["motion"] = ev.get("motion") or m.group("motion")
    if m.group("vote"):
        kind = m.group("vote").upper()
        ev["vote"] = "DV" if kind == "DIV" else kind
        ev["y"], ev["n"] = m.group("y"), m.group("n")


def amendment_kind(what):
    """The clerk's word for whose amendment it is, as describe() and stage_of
    read it: the committee's ("Comm Am", "Maj Am"), its minority's ("Min
    Am"), or the word left as written ("Fl Am", "Am")."""
    if re.match(r"Min\w*\.?\s+Am", what or "", re.I):
        return MINORITY_AMENDMENT
    if re.match(r"(?:Comm|Maj)\w*\.?\s+Am", what or "", re.I):
        return "Committee Amendment"
    return what


def plain(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    for pat, w in WORDS:
        if pat.match(s):
            return w
    return s


def normalise(ev, created):
    """Mutates ev: date, motion, vote, action/rec, side."""
    t = ev["_type"]
    d = ev.get("date")
    if d and not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", d):
        ev["date"] = full_date(d, created, forward=t in NOTICE) or d
    if not ev.get("date") and t in SAME_DAY:
        ev["date"] = created.strftime("%m/%d/%Y")
    if ev.get("eff") and not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", ev["eff"]):
        ev["eff"] = full_date(ev["eff"], created) or ev["eff"]
    if t == "floor" and not ev.get("vote") and ev.get("vote_after"):
        ev["vote"] = ev["vote_after"]
    v = re.sub(r"\s+", " ", (ev.get("vote") or "")).upper()
    if v in ("DIV", "DIVISION", "ROLL CALL"):
        ev["vote"] = "RC" if v == "ROLL CALL" else "DV"
    if t == "floor":
        a = (ev.get("action") or "").strip()
        mover = (ev.get("mover") or "").strip()
        if not ev.get("motion"):
            o = re.sub(r"\s+", " ", (ev.get("outcome") or "")).lower()
            if o in ("rejected", "not adopted"):
                ev["motion"] = "ML"
            elif o == "adopted":
                ev["motion"] = "MA"
            elif SELF_ADOPTING.match(a):
                ev["motion"] = _lost(ev, a) or "MA"
        _third_apart(ev, a)
        if (ev.get("motion") or "").upper() == "AA":
            ev["motion"] = "MA"            # "OTP/A {1234}, AA, VV" with no third-reading MA
        lead = LEAD_SENATOR.match(a) if not mover else None
        if lead and plain(lead.group("rest")) != lead.group("rest"):
            mover, a = lead.group("mover"), lead.group("rest")
        ev["action"] = plain(a) if not re.match(r"^Sen", a) else a
        # The clerk's capitals on HA 1 of 1999, '"Ought NOT to Pass"'.
        if re.fullmatch(r"ought\s+not\s+to\s+pass", ev["action"], re.I):
            ev["action"] = "Ought Not to Pass"
        if mover:
            # "(Sen. Johnson)", which narrative.split_mover takes back off.
            name = re.sub(r"^Sen(?:ator|\.)?\s*", "", mover)
            ev["action"] = f"{ev['action']} (Sen. {name})"
    # THE MINORITY'S AMENDMENT IS NOT THE COMMITTEE'S. "Maj Am{1177}, AL
    # RC(158-182); Min Am{1208}, AA VV" (SB 324 of 2004) is the committee's
    # amendment rejected and the one its minority wrote adopted in its place,
    # and both were told as "the committee's amendment": 5 histories of
    # 1999-2006 said that of a minority's while a row was read alone, 11 once
    # a line's clauses were. narrative.describe words this kind as the
    # committee minority's, and stage_of puts it on the floor, where the
    # minority offers it.
    if t == "amendment":
        ev["what"] = amendment_kind(ev.get("what"))
    if t == "amendment" and ev.get("_era") == CLAUSE_AMENDMENT and not ev.get("vote"):
        _clause_amendment_vote(ev)
    # A vote on some of an amendment (CLAUSE_AMEND_PART): "rest" where it is
    # the remainder, which decides the amendment once sections are divided
    # out of it, else "some".
    if t == "amendment" and ev.get("part"):
        ev["part"] = "rest" if re.match(r"Remain", ev["part"].strip(), re.I) else "some"
    if t == "report":
        ev["rec"] = plain(ev.get("rec"))
        s = (ev.get("side") or "").lower()
        # The House clerk writes "Maj Report" on unanimous reports too (3,047
        # of 5,184 House "Maj" lines are n=0); a unanimous report has no
        # minority, so it is the committee's.
        ev["side"] = ("" if s.startswith("maj") and ev.get("n") == "0" else
                      "Majority" if s.startswith("maj") else
                      "Minority" if s.startswith("min") else ev.get("side"))
    return ev


# -------------------------------------------------------------- joining
# THE HOUSE TYPED A FLOOR DAY AS ONE ENTRY, and the database cut it into rows
# of about a hundred characters or fewer, so a piece read alone can say the
# opposite of the whole. HB 605 of 1999:
#
#     "ITL Report adopted;  Consent Cal reconsidered, Rep Mock"
#     "MA VV; Removed from Consent Cal, req Rep Mock; Recommitted to"
#     "committee, Rep Mock MA VV;  HJ40, p943"
#
# The first piece alone is the report to kill it adopted, and the history,
# the 14 April 1999 sitting page and its consent grouping all said killed. The
# whole is the consent calendar reconsidered and the bill recommitted on Rep.
# Mock's motion, as HJ 40 p943 prints it, and it passed on 13 May. The other
# two eras have a joiner; this one had none, and docket_vocab.join_rows hands
# back a module's rows unjoined when it finds none, so the House rows of
# 1999-2006 that carry on the row before were each read as an entry of its
# own. Read whole, a joined line tells its LAST adopted question, as a line
# the clerk typed uncut always has -- and then each of its other decided
# questions is told too, in the order the clerk typed them: THE QUESTIONS OF
# ONE ENTRY, below.
#
# A row joins the one before it, the same chamber the same day, when it opens
# on what cannot start an entry: the rest of a page citation the row before
# broke off ("HJ29," then "p633-634"); a bare result (MA, ML, AA...) where the
# clause before has none; a vote (VV, RC(, DIV() after a row that does not end
# on its own vote; or a lowercase word after one that ends on neither a vote
# nor a citation. That last keeps 2005-2006's "Passed with AM {0074h}, MA, VV"
# and the "ref to Ways & Means" row after it apart, which the clerk typed as
# two entries. House rows only: the Senate's cut rows, about fifteen, read no
# better joined.
#
# AND WHATEVER IT OPENS ON, WHERE THE ROW BEFORE STOPS IN MID-CLAUSE. The cut
# falls between words, so the next row as often opens on a capital: a name
# ("...ML RC(168-169); Rep" then "Langer moved ITL; Laid on the Table, Rep
# Burling MA RC(167-166)"), a motion ("Rep Burling moved to" then "Lay on the
# Table, ML RC(161-182)", HB 633 of 1999), a committee ("Passed with Am and
# ref to Exec Depts &" then "Admin RC(258-100)"). Read alone those rows gave
# "the House adopted 'Burling'" (CACR 21 of 1999), "adopted 'Sen Am'" (HB 374
# of 1999, HB 672 of 2002), and no outcome at all for SB 315 of 2002, whose
# referral to interim study, 292-64, is on its third row. open_end() says a
# row stops in mid-clause: the text so far holds a decided question, so it is
# a floor entry and not a roster of conferees; what follows its last ";" has
# neither a result nor a vote; and it does not end the way an entry ends -- on
# a ";", a citation, a page number, a closing bracket or a word of outcome.
# Read against every same-day pair of House rows of 1999-2006 it joins 73
# and each is the same entry carried on. It does not reach the second-year
# clerk of 2006, who typed one question to a row and left none unfinished. A
# row that opens on a date still starts an entry, which leaves HB 346 of
# 1999's "11/3/99 ... Conf Comm Report" and "11/3/99 Adopted VV" apart: the
# clerk dated both rows, and joined they would put a date in mid-sentence.
CITE_DONE = re.compile(r"\b(?:HJ|SJ|HC|SC)\s*\d+[A-Za-z]?\s*,?\s*p(?:g|\.)?\s*\d+[\d\s\-+,]*"
                       r"(?:\((?:See|SEE)[^)]*\))?\s*(?:==[^=]*==)?\s*$", re.I)
CITE_OPEN = re.compile(r"(?:\b(?:HJ|SJ)\s*\d+[A-Za-z]?\s*,?|\+|\bp)\s*$", re.I)
CITE_REST = re.compile(r"^(?:p(?:g|\.)?\s*\d|\+\s*\d)", re.I)
VOTE_FIRST = re.compile(r"^(?:(?:VV|DV)\b|RC\s*\(|DIV\s*\(|(?:2/3|3/5)\s*(?:VV|RC|DIV)\b)")
RESULT_FIRST = re.compile(r"^(?:MA|MF|ML|AA|AF|AL)\b")
LOWER_FIRST = re.compile(r"^[a-z]")
DATED_FIRST = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}\b")
ENDS_DECIDED = re.compile(r"(?:\b(?:MA|MF|ML|AA|AF|AL|VV|DV)\b|\))[\s,;.]*$")
ENDS_OUTCOME = re.compile(r"\b(?:MA|MF|ML|AA|AF|AL)\b[\s,;.]*$")
HAS_RESULT = re.compile(r"\b(?:MA|MF|ML|AA|AF|AL)\b|\b(?:adopted|failed|passed)\b", re.I)
DECIDED = re.compile(r"\b(?:MA|MF|ML|AA|AF|AL|VV|DV)\b|\b(?:RC|DIV)\s*\(")
ENDS_CLOSED = re.compile(r"(?:[;.)\]>=]|\d)\s*$")
ENDS_SAID = re.compile(r"\b(?:adopted|denied|withdrawn|enrolled)\s*$", re.I)
# narrative.clean() ends a line at the first "HC 33" or "HJ 29" it meets,
# taking the citation for the line's last words. HB 1 of 2001's first row
# names its amendments by calendar, "Maj Am {HC 33, entire}, AA VV; ...", so
# joined to its second the whole floor day would be cut off after "Maj Am {".
CITE_WITHIN = re.compile(r"\b(?:HJ|SJ|HC|SC)\s+\d")


def open_end(p):
    """True where the text so far is a floor entry that stops in mid-clause
    (AND WHATEVER IT OPENS ON, above)."""
    p = p.rstrip()
    if not DECIDED.search(p) or ENDS_CLOSED.search(p) or CITE_OPEN.search(p):
        return False
    if CITE_WITHIN.search(p):
        return False
    last = p.rsplit(";", 1)[-1]
    return bool(last.strip()) and not DECIDED.search(last) and not ENDS_SAID.search(last)


def joins(prev, d):
    """The rule that joins row text d onto the text before it, or None."""
    p = prev.rstrip()
    if DATED_FIRST.match(d):
        return None
    if CITE_REST.match(d):
        return "page" if CITE_OPEN.search(p) else None
    if CITE_DONE.search(p):
        return None
    if RESULT_FIRST.match(d):
        return "result" if not HAS_RESULT.search(p.rsplit(";", 1)[-1]) else None
    if VOTE_FIRST.match(d):
        return "vote" if (ENDS_OUTCOME.search(p) or not ENDS_DECIDED.search(p)) else None
    if LOWER_FIRST.match(d):
        return "phrase" if not ENDS_DECIDED.search(p) else None
    return "open" if open_end(p) else None


# A JOINED LINE THAT STILL TELLS ONE MOTION SAYS SO. The sitting page credits
# every speech on a bill to its one motion where the record holds one. While
# a joined line told only its last carried question that put speeches on the
# wrong side: HB 1348 of 2002's line has a failed motion to nonconcur,
# 146-157, before the concurrence that carried, and the speeches on
# nonconcurring were credited to concurring. That line is now two motions
# again (THE QUESTIONS OF ONE ENTRY, below), each with its own count, and
# needs no mark. What still does is a line whose rows were read as several
# floor actions and which, split, tells one: CACR 21 of 1999's "OTP/AM fails
# 3/5 DIV(224-109); ...; Laid on the Table, Rep Burling MA DIV(191-142)",
# where the passage that failed is in no shape the clause table tells. So
# docket_vocab marks those, and build_session_pages asks such a line for
# evidence before it credits a speech to its one motion. The other two
# eras' joiners do not ask for the mark, and their pages are as they were.
MARK_JOINED = True


def join_rows(rows):
    """[(created, bill, body, desc)] -> the same, House continuations joined on.
    The joined row keeps the first piece's timestamp."""
    out = []
    for r in rows:
        created, bill, body, desc = r
        if out and body == "H":
            pc, pb, pbody, pdesc = out[-1]
            same = (pb, pbody) == (bill, body) and (
                not pc or not created or pc.date() == created.date())
            if same and joins(pdesc, desc.strip()):
                out[-1] = (pc, pb, pbody, pdesc.rstrip() + " " + desc.strip())
                continue
        out.append(tuple(r))
    return out


# ------------------------------------------- the questions of one entry
# A JOINED ENTRY IS A FLOOR DAY, AND A FLOOR DAY IS SEVERAL QUESTIONS. Read
# whole it tells the last one that carried, and while the rows were read one
# by one the others were told by accident, a row at a time. Joined and told
# as one, HB 323 of 2005 read killed 164-153 on 23 March and passed a week
# later with no reconsideration between, because the reconsideration, 153-150
# on a roll call, opens the line its passage ends; HB 633 of 1999 lost the
# first of its two 172-171 passages and the 175-167 reconsideration between
# them; and seven bills lost an amendment from their lists. So a line that was
# joined is split again -- at its ";", where the clerk put the divisions, not
# where the database cut it -- and each clause that decides a question with
# its own result is told as its own event, in the clerk's order, beside the
# one the whole line tells.
#
# WHAT A CLAUSE MUST BE TO BE TOLD ALONE (the CLAUSE table). An amendment the
# clerk numbered, with its own outcome ("Comm Am{1063}, AA VV", "Rep Buckley
# Fl Am{0102}, AL RC(58-292)"); a motion with its result ("Rep Norelli moved
# to Reconsider, MA RC(153-150)", "OTP/AM ML RC(170-173)", "Taken from the
# Table, Rep Scanlan MA RC(195-184)"); a disposal in words that carries a
# vote ("Passed with Am RC(172-171)", "Rep K Herman moved ITL, ITL Report
# Adopted RC(174-169)"); a suspension of the rules or a special order that
# carried, which a line holding nothing else has always told; or any other
# motion a member made, with its result, in the clerk's own words; an
# article of an address adopted on its own; a third reading the House voted
# on by itself; a veto it sustained or overrode; and a numbered amendment's
# vote on some of its sections or on the rest (each is set out with its
# pattern, below). Nothing looser: a section of a divided question the clerk
# did not number ("Secs. 1-5, AA RC(226-118)"), an amendment with no number,
# a motion only announced ("Rep Welch moved OTP/AM"), or a passage that fell
# short of two thirds or three fifths ("OTP/AM failed 3/5 RC(186-172)", which
# no sentence here can yet say without reading as 186 voting it down) stays
# in the line, untold, as it is on a line that was never cut.
# And a disposal in words with NO vote of its own is not a question the House
# put: HB 605's "ITL Report adopted" is the consent calendar's, which the
# next clause reconsiders, and telling it is how that bill came to read
# killed.
#
# A line the database did not cut is left whole and tells its last carried
# question, as it always has. Split the same way, 273 uncut House lines of
# 1999-2006 would tell 335 more events (186 amendments and 149 motions,
# counted on 1 October 2026); that is a decision about the era's histories
# and was not part of this repair.
SEMI = re.compile(r";(?![^()\[\]{}]*[)\]}])")        # not the ";" in "(vote 13-1;CC)"
TAIL_FIRST = re.compile(r"^(?:(?:HJ|SJ|HC|SC)\s*\d|\(?\s*(?:Also\s+)?See\b|p\s*\d)", re.I)


def clauses(text):
    """[(start, end)] of the clauses of one entry, each a question the clerk
    set off with ";". A clause that opens on a bare result or vote belongs to
    the one before it ("Susp Rules for Intro & Consideration; MA 2/3VV"), and
    so does the citation the entry ends with."""
    cuts, a = [], 0
    for m in SEMI.finditer(text):
        cuts.append((a, m.start()))
        a = m.end()
    cuts.append((a, len(text)))
    out = []
    for a, b in cuts:
        piece = text[a:b].strip()
        if not piece:
            continue
        if out and (RESULT_FIRST.match(piece) or VOTE_FIRST.match(piece)
                    or TAIL_FIRST.match(piece)):
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


# "Rep X moved [to] ", "Rep X moved ITL, " ahead of the result in words, and
# "Comm Rept " ahead of the report's motion.
Q_LEAD = (r"(?:Comm(?:ittee)?\s+Rep(?:or)?t\s*[,:]?\s+"
          r"|Reps?\.?\s+[^;]*?\bmoved\s+(?:to\s+)?(?:[^;,]*,\s*)?)??")
# A disposal in words, with the vote it must carry to be told; its result is
# read where the clause writes one ("Lay on the Table, ML DIV(63-221)"), so a
# question that lost keeps its count.
#
# AND THE HOUSE CONCURRING, said in the past tense with no MA: "Rep Mock moved
# to Concur with Sen Ams; Rep D Eaton moved LOT, ML RC(175-198); House
# Concurred with Sen Am, RC(197-176)" (HB 763 of 2003). With the tabling
# motion told and the concurrence not, that bill's House history ended on a
# motion to table it that lost, three sentences before the governor signed it.
CLAUSE_H_SAID = re.compile(
    r"^" + Q_LEAD +
    r"(?P<action>(?:Adopted\s+as\s+Am(?:ended|end)?\b\.?"
    r"|(?:House\s+)?Concurred(?:\s+(?:with|w/)\s+(?:Sen(?:ate)?\s+)?Am\w*\.?)?"
    r"|" + H_SELF + r")"
    r"(?=[^;]*(?:\b(?:MA|ML|MF|VV|DV)\b|\b(?:RC|DIV)\s*\()))"
    r"(?:" + MOVER_H + r"\s*,?\s*(?P<motion>MA|ML|MF)\b)?" + HVOTE, re.I)
# A motion and its result: "Rep Norelli moved to Reconsider, MA RC(153-150)",
# "OTP/AM ML RC(170-173)", "ITL Report, ML RC(115-226)".
# And the committee's report to re-refer, in the clerk's shortest form: "Comm
# Rept Re-Ref ML RC(158-168)" (HCR 10 of 1999), the first of three questions
# on that line and the only one that was not told.
CLAUSE_H_MOVED = re.compile(
    r"^" + Q_LEAD + r"(?P<action>" + H_MOTION + r"|Re-?Ref\b)(?:\s+Rep(?:or)?t)?"
    + MOVER_H + r"\s*,?\s*(?P<motion>MA|ML|MF)\b" + HVOTE, re.I)
# Any other motion a member made, with its result, told in the clerk's words
# as the questions the tables do not know always are: "Rep M Clark moved to
# print remarks, ML DIV(138-184)" is the House failing "print remarks" on a
# division, which a row cut after "Rep" used to tell as failing "M Clark
# moved to print remarks". Not the clerk's "Div ?", which is shorthand and
# not a motion's name.
#
# A motion in two halves is one motion: "Rep Dalrymple moved to discharge Conf
# Comm, and req New Conf Comm, MA VV" (SB 140 of 1999). Read to the first
# comma it was no motion at all, and the House's part in that bill ended on
# its conference report failing -- which is why it asked for a new
# conference, whose report it adopted the same day. Only ", and": a comma
# alone ends the motion, as in "Rep Hunt moved OTP/AM, ...".
CLAUSE_H_OTHER = re.compile(
    r"^Reps?\.?\s+[^;]*?\bmoved\s+(?:to\s+)?"
    r"(?P<action>(?-i:[A-Za-z])[^;,?]*?(?:,\s+and\s+[^;,?]*?)?)\s*,\s*"
    r"(?P<motion>MA|ML|MF)\b" + HVOTE, re.I)
# The third reading, where the House voted on it by itself: "Rep Chandler
# susp rules for 3rd reading, MA DIV(262-62); 3rd reading MA RC(257-68)" (CACR
# 6 of 1999). For a constitutional amendment that is the vote that sends it
# on, by three fifths, and with the suspension told and the reading not, the
# line read as rules suspended for a reading that was never held.
CLAUSE_H_THIRD = re.compile(
    r"^(?P<action>3rd\s+reading)\s*,?\s*(?P<motion>MA|ML|MF)\b"
    r"(?:\s*\(\s*by\s+nec\.?\s*(?:2/3|3/5)\s*\))?" + HVOTE, re.I)
# A suspension of the rules as the second-year clerk of 2006 wrote one, the
# words first and what it was for after a comma: "Emergency Session;
# Suspension of Rules for Intro. & Consideration at Present time, & if passed
# third reading & final passage, MA VV" (SB 393 of 2006), which the database
# cut after "&". H_PROC reads "Susp Rules ..." up to its first comma, and this
# line's second row alone used to be told as the House adopting "if passed
# third reading & final passage". The whole of it is the question.
CLAUSE_H_SUSPENSION = re.compile(
    r"^(?P<action>Suspension\s+of\s+(?:the\s+)?Rules?\b[^;]*?)\s*,\s*"
    r"(?P<motion>MA|ML|MF)\b" + HVOTE, re.I)
# An article of an address, voted on its own: "Art 1, Adopted RC(219-138);
# Art 2, Adopted RC(252-104); Art 3, Adopted RC(242-112)" are the three
# articles of HR 51 of 2000, the impeachment of the Chief Justice, each a
# roll call. Cut after "Rep Jacobson", that row told its last as the House
# voting 242-112 to pass the resolution, which it adopted as amended 253-95
# later on the same line; the article is told as the article.
CLAUSE_H_ARTICLE = re.compile(
    r"^(?P<action>Art(?:icle)?\.?\s*\d+)\s*,\s*(?P<outcome>Adopted|Rejected|Not\s+Adopted)\b"
    + HVOTE, re.I)
# An amendment as AMEND_OLD reads one, but offered by several ("Reps Stritch
# and Scanlan Fl Am{3536}(New Title), AA RC(200-147)"), proposed and then
# voted ("Rep Burling prop Fl Am{2176}(New Title), AL RC(131-217)"), or named
# for the committee or the side that wrote it ("Fin Comm Am{1462}, AL
# RC(106-184)", "Comm Maj Am{1074}, AA VV", "Corrected Maj Am{1344}"). A whole
# line that opens on any of those is left to the floor's patterns, as it
# always has been.
CLAUSE_AMEND = re.compile(
    r"^(?:(?P<mover>Reps?\.?\s+(?:(?!(?:Enrolled|Committee|Floor|Fl|Comm|FL|Maj|Min|Fin|Prop)\b)"
    r"(?:[A-Z][\w'.\-]*,?|&)\s+){1,8}))?(?:Prop\.?\s+)?"
    r"(?:(?:Fin|W\s*&\s*M|ED\s*&\s*A|Corrected|Comm(?:ittee)?|Maj(?:ority)?|Min(?:ority)?)\.?\s+)*?"
    + AMEND_BODY, re.I)

# A NUMBERED AMENDMENT VOTED ON IN PARTS. The House divides the question and
# the clerk writes each vote after the number: "Reps Lozeau & Burling Fl
# Am{2229}, Rep Alger Div?, Secs,17 & 18, AA RC(255-96); Am{2229}, Remaining
# Secs, AA RC(239-112)" (HB 999 of 1999). Neither clause is an amendment as
# CLAUSE_AMEND reads one, the part standing between the number and the
# result, so 2229 was told nowhere -- on a line whose five other floor
# amendments all lost, which left the history saying the House "took up 5
# floor amendments and rejected all of them" of a day it adopted one, and
# the bill's list of amendments with six rejected and none adopted on a bill
# that passed amended. Each numbered part is told as part of its amendment,
# with its own vote, and says which it is ("part": normalise): the remainder
# decides the amendment once sections are divided out of it; a section
# alone ("Comm Am{4383}, Sec. 5, AL DIV(141-160)", SB 303 of 2000, whose
# remainder carried 238-74) decides only itself, and the list of amendments
# claims no outcome from it. A part the clerk did not number ("Secs. 6-14, AA
# RC(224-119)") is still not told: nothing in its clause says whose it is.
AMEND_PART_OF = (r"(?:Remaining\s+Secs?\.?|Remainder"
                 r"|Secs?\.?[\s,]*\d+(?:[\s,&\-]*(?:and\s+)?\d+)*)")
CLAUSE_AMEND_PART = re.compile(
    r"^(?:(?P<mover>Reps?\.?\s+(?:(?!(?:Enrolled|Committee|Floor|Fl|Comm|FL|Maj|Min|Fin|Prop)\b)"
    r"(?:[A-Z][\w'.\-]*,?|&)\s+){1,8}))?(?:Prop\.?\s+)?"
    r"(?:(?:Fin|W\s*&\s*M|ED\s*&\s*A|Corrected|Comm(?:ittee)?|Maj(?:ority)?|Min(?:ority)?)\.?\s+)*?"
    r"(?P<what>(?:Committee\s+|Comm\.?\s+|Maj(?:ority)?\.?\s+|Min(?:ority)?\.?\s+"
    r"|Floor\s+|Fl\.?\s+)?Am(?:endment|end\.?)?)"
    r"\s*[{(\[]\s*#?(?P<num>\d{4}[a-z]?)\s*[})\]]\s*(?:\((?:NT|New\s+Title)\)\s*)?,\s*"
    r"(?:Reps?\.?\s+[A-Z][\w'.\-]*\s+Div\s*\?\s*,\s*)?"
    r"(?P<part>" + AMEND_PART_OF + r")\s*,?\s*(?P<motion>AA|AL|AF)\b" + HVOTE, re.I)

# WHOSE A BARE "Am{N}" IS, THE LINE HAS ALREADY SAID. A part's clause often
# names the amendment by number alone, the kind having been written a clause
# earlier: "Reps Lozeau & Burling Fl Am{2229}, ...; Am{2229}, Remaining Secs"
# is the floor amendment, and "Rep Alger div question on Maj Am; Am{2606},
# secs 1-5, AA RC(191-164)" (HB 1423 of 2002) is the majority's, which a bare
# "Am" alone would tell as one offered on the floor. The kind is the last one
# the line names before the clause.
KIND_NAMED = re.compile(
    r"\b(?:Committee|Comm|Maj(?:ority)?|Min(?:ority)?|Floor|Fl)\.?\s+Am(?:endment|end)?\b", re.I)


def clause_context(ev, before):
    """Mutates one clause's event with what the line said before the clause
    (docket_vocab.questions calls this for every clause it tells)."""
    if ev.get("_type") != "amendment" or not ev.get("part"):
        return
    if not re.fullmatch(r"Am(?:endment|end\.?)?", (ev.get("what") or "").strip(), re.I):
        return
    named = KIND_NAMED.findall(before or "")
    if named:
        ev["what"] = amendment_kind(re.sub(r"\s+", " ", named[-1]))


# The dispatcher's contract for a clause: (id, event type, pattern, groups
# merged in after a match), tried in order; a clause none fits is not told.
#
# A veto the House voted on is a clause like any other: "Reps Weatherspoon &
# Sargent moved LOT, ML RC(134-203); Governor's Veto Sustained [fails 2/3]
# RC(194-148)" (HB 1548 of 2000, the repeal of the death penalty). With the
# tabling motion told and the veto not, the bill's history ended on the
# House declining to table it.
CLAUSE = [(CLAUSE_AMENDMENT, "amendment", CLAUSE_AMEND, {}),
          (CLAUSE_AMENDMENT, "amendment", CLAUSE_AMEND_PART, {}),
          ("1999:clause:veto", "veto_override", VETO_OLD, {}),
          ("1999:clause:floor", "floor", FLOOR_CONF, {}),
          ("1999:clause:floor", "floor", CLAUSE_H_ARTICLE, {}),
          ("1999:clause:floor", "floor", CLAUSE_H_SAID, {}),
          ("1999:clause:floor", "floor", CLAUSE_H_MOVED, {}),
          ("1999:clause:floor", "floor", CLAUSE_H_THIRD, {}),
          ("1999:clause:floor", "floor", FLOOR_H_PROC, {}),
          ("1999:clause:floor", "floor", CLAUSE_H_SUSPENSION, {}),
          ("1999:clause:floor", "floor", CLAUSE_H_OTHER, {})]


# ------------------------------------------------ routine notices
ROUTINE = [
    ("copy to chairman / report due (bill sent to the committee chair)",
     r"^Copy\s+to\s+Chair\w*|^Report\s+due\b|^Copy\s+to\b"),
    ("proposed amendment printed in the calendar (not a vote)",
     r"^(?:Reps?\.?\s+[^;]*?\s+)?(?:Prop(?:osed)?\.?\s+(?:(?:Fl(?:oor)?|Maj(?:ority)?|Min(?:ority)?|Fin(?:ance)?|"
     r"W\s*&\s*M|Educ|Div\s+[IV]+|Comm(?:ittee)?|Ret(?:ained)?|Int\w*\s+Study)\.?\s+)*(?:Comm\w*\s+)?Am\w*"
     r"|Proposed\s+Committee\s+Amendment)"
     r"|^(?:Fin\s+Comm\s+)?Prop\s+Am|^Committee\s+Amendment\s*,?\s*[{(]\d+[a-z]?[})]\s*(?:,\s*\(New Title\))?\s*"
     r"(?:,?\s*SC\s*\d+.*)?$|^(?:Fin|W&M)\s+Comm\s+Prop\s+Am"),
    ("roster: subcommittee / Speaker's or President's appointments / conferees",
     r"^\(?\s*(?:Subcom|Sub-?committee|Spkr|Speaker|Re-?Ref\w*\s+Subcom|Int(?:erim)?\.?\s+Study\s+Subcom|"
     r"Div\s+[IV]+|Fin\s+Div|Conf\w*\s+Comm\w*\s*:|Reps?\s*:)"
     r"|^(?:President|Pres\.?)\s+Ap\w*|^(?:Senate|House)\s+Conferees|^Conferees?\b"
     r"|^Study\s+Committee\s+Members|^Senate\s+Committee\s+Members|^Conferee\s+Change"
     r"|^Committee\s+Members|^Speaker\s+Ap\w*|^\(?Spkr\b"),
    ("question put, not voted on (result on another row)", r"\[?\bNot\s+Voted\s+On\b\]?"),
    ("conference report filed / not signed (no vote)",
     r"^\(?(?:Conf(?:erence)?\.?\s+Comm(?:ittee)?|Committee\s+of\s+Conference|C\s+of\s+C)\.?"
     r"(?:\s+(?:Rep(?:or)?t|Rprt|Rpt)\.?)?\b.*\b(?:Filed|Not\s+Signed|Not\s+Filed)\b"),
    ("notice of reconsideration (a notice, not a vote)", r"Notice\s+of\s+Reconsideration|Served\s+Notice"),
    ("cancelled / undetermined meeting the flag regex misses",
     r"cancel|UNDETERMINED|\bpostponed\b"),
    ("bare question, result on the next row (Senate)",
     r"^(?:Ought\s+to\s+Pass(?:\s+with\s+Amendment)?(?:\s*\{\d+\})?|Inexpedient\s+to\s+Legislate|"
     r"Interim\s+Study|Rerefer(?:red)?\s+to\s+Committee|Sen\.?\s+[A-Z][\w'.]*\s+Moved\s+[^,;]*)\s*$"),
    ("empty", r"^\s*$"),
]
ROUTINE = [(n, re.compile(p, re.I)) for n, p in ROUTINE]


def routine(clean_line):
    for n, rx in ROUTINE:
        if rx.search(clean_line):
            return n
    return None


# The dispatcher's contract: FIRST is tried before narrative.PATTERNS, AFTER
# only on what they leave as "other". Each entry is (id, event type, pattern,
# groups merged in after a match), the same shape every era module uses.
FIRST = [(f"1999:{t}", t, p, {}) for t, p in OLD_FIRST]
AFTER = [(f"1999:{t}", t, p, {}) for t, p in OLD]
