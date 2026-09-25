#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-11.1
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
committee's), "ITL" into "Inexpedient to Legislate", DIV into DV.
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
    r"(?:ref(?:erred|erring|er)?\.?)\s*(?:to\b|:)?\s*"
    r"(?P<committee>[A-Z][^;<\[]*?)" + _CMTE_END, re.I)
VACATED = re.compile(
    r"^Vacated\s+(?:from\s+[A-Z][^;]*?\s+)?(?:and\s+)?(?:Re-?)?(?:Ref(?:erred)?\.?\s+)?to\s+"
    r"(?P<committee>[A-Z][^;(]*?)(?=\s*(?:;|,\s*(?:Reps?|Sen)\b|\s(?:MA|ML)\b|\(|,?\s*(?:HJ|SJ)\s*\d|$))", re.I)
REREF_H = re.compile(
    r"^(?:ref|Re-?Referred|Referred|Refer)\.?\s+to\s+(?P<committee>(?!.*Interim\s+Study)[A-Z][^;(\[]*?)"
    # committee names carry commas ("Res, Rec & Dev"): stop at a mover, a vote or the end
    r"(?:\s+committee)?(?=\s*(?:[;(\[]|,\s*(?:Reps?|Sen)\b|,?\s*(?:VV|RC|DIV|DV|MA)\b|,?\s*$))", re.I)

# --- meetings -----------------------------------------------------------------
HEARING = re.compile(
    NOCANCEL +
    r"^(?:(?:(?:Re-?)?Resched(?:uled|\.)?|Continued|Fin(?:ance)?(?:\s+Div\s+[IV]+)?|Joint|W\s*&\s*M|Ways\s*&\s*Means|"
    r"Full\s+Comm(?:ittee)?|Re-?Ref(?:er)?|Int(?:erim)?\s+Study)\s+){0,2}"
    r"(?P<kind>Public\s+Hearing|Hearing)"
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
    r"(?:(?:Fin(?:ance)?|W\s*&\s*M|Ways\s*&\s*Means|RE-?REF|Re-?Ref(?:erred)?|Int(?:erim)?\s+Study"
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
AMEND_OLD = re.compile(
    # a House floor day typed as one entry ends in the bill's own outcome
    # ("Comm Am{0236}, AA VV; ...; Passed with Am VV"): that line is the floor's
    r"^(?!.*;\s*[^;]*?\b(?:Passed|Adopted\s+with|ITL|OTP\w*|Ought\s+to\s+Pass|Inexpedient|Laid|Int\w*\s+Study"
    r"|Indefinitely|Recommit\w*|Re-?Ref\w*|Referred)\b)"
    r"(?:(?P<mover>(?:Rep|Sen)\.?\s+(?:(?!Enrolled\b|Committee\b|Floor\b|Fl\b|Comm\b|FL\b)"
    r"[A-Z][\w'.\-]*\s+){1,3}))?"
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
    r"|(?P<y>\d+)\s*Y?\s*[-–]\s*(?P<n>\d+)\s*N?|[\dYN]+\s*-\s*[\dYN]+|Division|\(|\))[,;\s]*){1,6}", re.I)
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
    (r"^(?:OTP/AM|OTPA|Ought\s+to\s+Pass\s+as\s+Amended.*|Passed\s+with\s+Am.*|Adopted\s+with\s+Am.*)$",
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
    r"|(?:House\s+)?(?:NON-?Conc|Nonc|Acced)"
    r"|(?:Special|Moved).*without\s+objection$"
    r"|Spec(?:ial)?\.?\s+Order)", re.I)


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
            elif o == "adopted" or SELF_ADOPTING.match(a):
                ev["motion"] = "MA"
        if (ev.get("motion") or "").upper() == "AA":
            ev["motion"] = "MA"            # "OTP/A {1234}, AA, VV" with no third-reading MA
        lead = LEAD_SENATOR.match(a) if not mover else None
        if lead and plain(lead.group("rest")) != lead.group("rest"):
            mover, a = lead.group("mover"), lead.group("rest")
        ev["action"] = plain(a) if not re.match(r"^Sen", a) else a
        if mover:
            # "(Sen. Johnson)", which narrative.split_mover takes back off.
            name = re.sub(r"^Sen(?:ator|\.)?\s*", "", mover)
            ev["action"] = f"{ev['action']} (Sen. {name})"
    if t == "amendment" and re.match(r"(?:Comm|Maj|Min)\w*\.?\s+Am", ev.get("what") or "", re.I):
        ev["what"] = "Committee Amendment"
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
