#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-11.1
"""
The 1989-1998 docket's own vocabulary, mapped onto narrative.py's events.

Read by docket_vocab.py, which is read by narrative.py for a database-era
docket and by nothing else. Nothing here is used on a 2017-2026 docket.

WHY A SEPARATE VOCABULARY

narrative.py's PATTERNS were written against the web docket of 2017-2026,
which spells things out and ends most lines with a four-digit date. These
ten years abbreviate almost everything and date almost nothing:

    MAJ REPORT OTP/AM FOR MAR10 (VOTE 12-0;CC)
    BURTON SUBST OTP, ML RC (89-255); ITL REPORT ADOPTED VV; HJ35, P788-792
    SIGNED BY GOVERNOR  5/8/89   EFF:  7/7/89     CHAP: 112
    OVERRIDE GOV VETO, ML <FAILED 2/3> RC(14-10); SJ24,P629-631

Run against that, the modern patterns recognise 11.1% of 106,881 rows. The
table below takes it to 81.3%, with another 19.0% deliberately left as
routine notices (seat pockets, due dates, appointments), so 98.0% of the
lines are accounted for.

HOW IT MAPS

Every pattern yields one of narrative.py's EXISTING event types and its
named groups, so describe(), stage_of() and build() render these events with
no knowledge that they came from a different decade. The glue below does
what a regex cannot: it turns MON## and M/D/YY into a full date (the row's
own timestamp decides the year), ITL into "Inexpedient to Legislate", MAJ
into "Majority", DIV into the "DV" this project writes, and the clerk's
committee abbreviations into the committee's name.

THE LAST DECIDING CLAUSE WINS. A 1989 floor line carries a whole afternoon:
a substitute motion that failed, then the report that was adopted, then a
reconsideration. The floor pattern anchors on the last clause that settled
something, because that is the one the bill's status depends on.
"""

import re
from datetime import date

I = re.I
MONTHS = r"(?:JAN|FEB|MAR|APR|MAY|JUNE?|JULY?|AUG|SEPT?|OCT|NOV|DEC)"
DATE = (MONTHS + r"\.?\s?\d{1,2}(?!\d)"
        r"|\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}\b|\d{1,2}/\d{1,2}(?![/\d])")
TIME = r"(?:\d{1,2}:\d{2}(?:\s*[AP]\.?M\.?)?|NOON)"
# A member, or "REPS A TORR & BUCKLEY": an optional initial, a surname of at
# most two words, and further names only after "&" or ",". The words that
# follow a mover in this docket may never be read as part of the name.
STOP = r"(?!(?:MOVED?|SUBST?|SUB|SUSP\w*|RULES?|FOR|TO|WITHDREW|REMOVED|PROP|FL|AM|MA|ML|VV|RC|DIV)\b)"
NAME = (r"(?:REPS?|SENS?)\.?\s+(?:[A-Z]\.?\s+)?" + STOP + r"[A-Z][A-Z.'\-]*(?:\s+" + STOP + r"[A-Z][A-Z'\-]+)?"
        r"(?:\s*(?:&|,)\s*(?:[A-Z]\.?\s+)?" + STOP + r"[A-Z][A-Z.'\-]*(?:\s+" + STOP + r"[A-Z][A-Z'\-]+)?)*")
VOTE = r"(?P<vote>VV|RC|DIV|DV)"
TALLY = r"\(\s*(?P<y>\d+)\s*-\s*(?P<n>\d+)\s*\)"
# Not a cancelled notice, and not a conditional one ("SUBCOM WK SESS (IF
# NEEDED)", "EXEC SESS OCT26 (& OCT27 IF NEC)"): describe() says "held".
NOTCANCEL = r"(?!.*\b(?:CANCEL|IF\s+NEC|IF\s+NEEDED))"
CMTE = r"[A-Z][A-Z&+,'/. \-]*?"

# (id, event type, compiled pattern, fixed groups merged in after a match)
TABLE = []


def P(pid, typ, rx, **fixed):
    TABLE.append((pid, typ, re.compile(rx, I), fixed))


# ---------------------------------------------------------------- governor
P("gov_signed", "governor",
  r"^(?P<what>SIGNED BY (?:THE )?GOVERNOR)\s*(?:ON\s+)?(?P<date>" + DATE + r")?[\s,;]*"
  r"(?:EFF(?:ECTIVE)?(?:\s+DATE)?\s*[.:]?\s*(?P<eff>\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4})?\s*\*?)?[\s,;]*"
  r"(?:CH(?:AP(?:TER)?)?\s*[.:]?\s*(?P<chapter>\d+))?")
P("gov_vetoed", "governor",
  r"^(?P<what>VETOED BY (?:THE )?GOVERNOR)(?:\s+ON)?\s*"
  r"(?P<date>\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4})?")
P("unsigned", "unsigned_law",
  r"^(?:BECAME\s+)?LAW\s+WITHOUT\s+(?:GOVERNOR'?S?\s+)?SIGNATURE\s*"
  r"(?P<date>\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4})?"
  r"(?:.*?\bCH(?:AP(?:TER)?)?\s*[.:]?\s*(?P<chapter>\d+))?")
P("veto_result", "veto_override",
  r"^(?:GOVERNOR'?S\s+|GOV'?S\s+)?VETO\s+(?P<outcome>SUSTAINED|OVERRIDDEN)\b[\s,;]*"
  r"(?:(?P<vote>RC|DIV|VV)\s*" + TALLY + r"|(?P<vote2>ROLL CALL)\s*:\s*YEAS\s*(?P<y2>\d+)\s*NAYS\s*(?P<n2>\d+))?")
P("veto_motion", "veto_override",
  r"^OVERRIDE\s+(?:THE\s+)?(?:GOV(?:ERNOR)?'?S?\s+)?VETO\s*,?\s*"
  r"(?P<outcome>ML|MA|FAILED|FAILS|ADOPTED)\b[^;]*?(?P<vote>RC|DIV|VV)\s*" + TALLY)

# ---------------------------------------------------------------- enrolment
P("enrolled_dated", "enrolled",
  r"^(?P<date>\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4})\s+ENROLLED\b(?!\s+(?:BILL|AM))")
P("enrolled_bills", "enrolled",
  r"^ENROLLED\s+BILLS?\s*(?:[:;,]\s*)?(?=(?:SJ|HJ|$))")

# ---------------------------------------------------------------- floor
# The LAST clause of a compound line that decides something. The greedy
# prefix backtracks from the end of the line, so "SUBST OTP, ML RC(89-255);
# ITL REPORT ADOPTED VV" yields the ITL, and "MOVED TO RECONSIDER, MA VV;
# ... PASSED WITH AM VV" yields the passage.
FLOOR_ACTION = (
    r"ITL\s+(?:REPORT|REPT?|MOTION)\s+ADOPTED(?:/CONS\s+CAL)?"
    r"|PASSED(?:/ADOPTED)?(?:\s+(?:WITH|W/)\s*AMS?(?:END(?:ED|MENTS?)?)?)?"
    r"|(?<!,\s)(?<!,)(?:INTRODUCED\s+AND\s+)?ADOPTED(?:\s+(?:WITH|W/)\s*AMS?(?:END(?:ED|MENTS?)?)?)?"
    r"|(?:RE-?)?REFERRED\s+(?:TO\s+" + CMTE + r"\s+)?(?:FOR|TO)\s+(?:INT(?:ERIM)?\.?\s+)?STUDY"
    r"|(?:INT(?:ERIM)?|REF(?:ER)?\s+FOR)\s+STUDY\s+(?:REPORT|REPT)\s+ADOPTED"
    r"|INDEF(?:INITELY)?\.?\s+POST(?:PONED|PONE)?\.?"
    r"|LAID\s+ON\s+(?:THE\s+)?TABLE"
    r"|(?:TAKEN|REMOVED)\s+(?:OFF|FROM)\s+(?:THE\s+)?TABLE"
    r"|(?:HOUSE|SEN(?:ATE)?)\s+(?:CONC(?:UR(?:RED|S)?)?|NONC(?:ONC(?:UR(?:RED|S)?)?)?)\b[^,;]*"
    r"|(?:HOUSE|SEN(?:ATE)?)\s+ACCEDED?\b[^,;]*"
    r"|(?:NEW\s+)?CONF(?:ERENCE)?\s+COMM(?:ITTEE)?\s+(?:REPORT|REPT)\s+(?:\((?!UNABLE)[^)]*\)\s*)?ADOPTED"
    r"|RECOMM?ITT?ED\s+TO\s+" + CMTE + r"(?=\s*(?:,|;|$|\b(?:VV|RC|DIV|MA)\b))"
    # a substitute or moved motion counts only when it CARRIED
    r"|(?:(?:SUBST?|SUB\s+MOTION|MOVED(?:\s+TO)?)\.?\s+)"
    r"(?:ITL|OTP\s*/\s*AM|OTPA|OTP|RE-?REF\w*|REF(?:ER)?\s+FOR\s+(?:INTERIM\s+)?STUDY|INT(?:ERIM)?\s+STUDY"
    r"|LOT|LAY\s+ON\s+(?:THE\s+)?TABLE|IP|INDEF\w*\s+POST\w*)(?=\s*,?\s*MA\b)"
)
P("floor_decisive", "floor",
  r"^(?:.*[;,]\s*)?(?:(?P<mover>" + NAME + r")\s+)?"
  r"(?P<action>" + FLOOR_ACTION + r")"
  r"(?:\s+AND\s+REF(?:ERRED)?\s+TO\s+(?P<refer>" + CMTE + r")"
  r"(?=\s*(?:;|,\s*(?:REPS?|SENS?)\b|$|\b(?:VV|RC|DIV|DV|MA)\b)))?"
  r"(?:[^;]*?\b(?P<motion>MA|ML|MF)\b)?"
  r"(?:[^;]*?(?<![A-Z])" + VOTE + r"\b\s*(?:" + TALLY + r")?)?")
# 1989-1990 Senate: the motion on one row, "MOTION ADOPTED" on the next
# (joined by rule 2).
P("floor_senate89", "floor",
  r"^(?:SUBSTITUTE\s+)?MOTION\s*:?\s*(?:TO\s+)?(?P<action>[A-Z][A-Z /]*?)\s+MOTION\s+"
  r"(?P<motion>ADOPTED|FAILED|LOST)\b")
P("floor_all_bills", "floor",
  r"^(?P<mover>" + NAME + r")\s+(?:MOVED\s+)?[(\[]ALL BILLS[^)\]]*[)\]]\s*"
  r"(?P<action>ITL|INDEF\w*\s+POST\w*)\s*,\s*(?P<motion>MA|ML)\b[^;]*?(?:(?<![A-Z])" + VOTE + r"\b\s*(?:" + TALLY + r")?)?")

# ---------------------------------------------------------------- committee report
REC = (r"OTP\s*/\s*AM|OTPA|OTP|ITL|RE-?REF(?:ER(?:RED)?)?(?:\s+TO\s+COMM(?:ITTEE)?)?"
       r"|REF(?:ER)?\s+FOR\s+(?:INTERIM\s+)?STUDY|INT(?:ERIM)?\s+STUDY|IS\b|LOT\b|IP\b"
       r"|INDEF\w*\s+POST\w*|WITHOUT\s+REC\w*|NO\s+REC\w*|RNF\b")
COMMWORD = (r"(?:FIN(?:ANCE)?|APPROP\w*|W&M|WAYS\s*&\s*MEANS|CAP(?:ITAL)?\s+BUDGET|COMM(?:ITTEE)?"
            r"|SUBCOM|EXEC|JOINT)")
VOTE_TAIL = r"(?:.*?(?<![A-Z])V[O0]TE\s*:?\s*\(?\s*(?P<y>\d+)\s*-\s*(?P<n>\d+))?"
P("report_side", "report",
  r"^(?:RE-?REF(?:ERRED)?\s+)?(?:" + COMMWORD + r"\s+){0,2}(?P<side>MAJ(?:ORITY)?|MIN(?:ORITY)?)\s+"
  r"(?:" + COMMWORD + r"\s+){0,2}(?:REPORT|REPT|REP)\b\s*:?\s*(?P<rec>" + REC + r")" + VOTE_TAIL)
P("report_comm", "report",
  r"^(?!(?:NEW\s+)?CONF)(?:RE-?REF(?:ERRED)?\s+)?(?:" + COMMWORD + r"\s+){0,3}"
  r"(?:REPORT|REPT)\s*:?\s*(?P<rec>" + REC + r")" + VOTE_TAIL)
P("interim_report", "interim_report",
  r"^(?:INT(?:ERIM)?\s+STUDY|IS)\s+(?:REPORT|REPT)\s*:?\s*(?P<rec>.+?)\s*"
  r"(?=\(\s*(?:V[O0]TE|NO\s+VOTE)|<|$)"
  r"(?:\(\s*(?:V[O0]TE\s*:?\s*\(?\s*P?(?P<y>\d+)\s*-\s*(?P<n>\d+)|NO\s+VOTE|V[O0]TE\s*)[^)]*\))?")

# ---------------------------------------------------------------- meetings
PREFIX = (r"(?:(?:RESCHED(?:ULED)?|CONTINUED|RECESSED|RECONVENED|JOINT|ADDITIONAL|2ND|SECOND"
          r"|FIN(?:ANCE)?|APPROP\w*|W&M|INT(?:ERIM)?\s+ST(?:UDY)?|IN\s+STUDY|RE-?REF(?:ER(?:RED)?)?"
          r"|PUBLIC|FULL\s+COMM(?:ITTEE)?|SUB-?COMM?(?:ITTEE)?|SUBCOM|DIV(?:ISION)?\s*[IV]+|&"
          r"|(?:[A-Z]+\s+){1,2}SUBCOM)\s+)*")
P("conf_meeting", "conference_meeting",
  r"^" + NOTCANCEL + r"(?:RESCHED(?:ULED)?\s+|CONTINUED\s+|NEW\s+)?CONF(?:ERENCE)?\s+COMM(?:ITTEE)?\s+"
  r"(?:MEETING|MTG)\s*:?\s*(?P<date>" + DATE + r")\s*(?P<time>" + TIME + r")?\s*(?P<venue>.*)$")
P("hearing", "hearing",
  r"^" + NOTCANCEL + PREFIX + r"(?P<kind>HEARING)\s*[:\-]?\s*(?:ON\s+(?:PROP(?:OSED)?\s+AM\w*\s+)?)?"
  r"(?P<date>" + DATE + r")\s*(?:AT\s+)?(?P<time>" + TIME + r")?\s*(?P<venue>.*)$")
P("worksession", "worksession",
  r"^" + NOTCANCEL + PREFIX + r"(?P<kind>(?:WORK|WK|WRK)(?:\s*&\s*EX(?:EC(?:UTIVE)?)?)?\s+SESS(?:ION)?S?"
  r"|(?:ORG(?:ANIZATIONAL)?\s+)?(?:MEETING|MTG)S?)\s*:?\s*(?:\([^)]*\)\s*)?(?:ON\s+)?(?P<date>" + DATE + r")")
P("exec", "exec",
  r"^" + NOTCANCEL + PREFIX + r"EXEC(?:UTIVE)?\s+SESS(?:ION)?S?\s*:?\s*(?:ON\s+)?(?P<date>" + DATE + r")")

# ---------------------------------------------------------------- referral
P("introduced", "introduced",
  r"(?:^|;\s*)(?:(?P<date>\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4})\s+)?INTRODUCED(?:\s*\([^)]*\))?"
  r"\s+AND\s+(?:RE-?)?REF(?:ERRED)?\.?\s+TO\s+(?P<committee>[A-Z][^;(]*?)\s*(?:[;(]|\s{2,}|\s+[HS]J\s*\d|$)")
P("vacated", "vacated",
  r"(?:^|;\s*)VACATED\s+(?:FROM\s+[A-Z][^;]*?\s+AND\s+)?(?:RE-?)?(?:REF(?:ERRED)?\s+)?TO\s+"
  r"(?P<committee>[A-Z][^;(,]*?)\s*(?:[;(,]|\b(?:VV|MA)\b|$)")
P("retained", "retained",
  r"(?:^|;\s*)RE-?REF(?:ERRED)?\s+TO\s+COMM(?:ITTEE)?\b")
P("rereferred", "rereferred",
  r"(?:^|;\s*)(?:RE-?)?REF(?:ERRED)?\s+TO\s+(?P<committee>" + CMTE + r")"
  r"(?=\s*(?:[;(]|,\s*(?:REPS?|SENS?)\b|\b(?:VV|RC|DIV|MA|RULE)\b|$))")
P("consent_off", "consent_off",
  r"^REMOVED\s+FROM\s+(?:THE\s+)?(?:CONS(?:ENT)?\.?\s+CAL(?:ENDAR)?|CC)\b")

# ---------------------------------------------------------------- lesser floor actions
P("suspend", "floor",
  r"^(?:(?P<mover>" + NAME + r")\s+)?(?P<action>(?:MOVED\s+(?:TO\s+)?)?SUSP(?:END(?:ED)?)?\.?\s+"
  r"(?:(?:JT|JOINT|HOUSE|SENATE|ALL)\.?\s+(?:&\s+JOINT\s+)?)?RULES?\b[^;]*?)"
  r"\s*,?\s*(?:MOTION\s+)?(?P<motion>MA|ML|MF)\b[^;]*?(?:(?<![A-Z])" + VOTE + r"\b\s*(?:" + TALLY + r")?)?")
P("floor_motion", "floor",
  r"^(?:.*[;,]\s*)?(?:(?P<mover>" + NAME + r")\s+)?(?:(?:MOVED(?:\s+TO)?|SUBST?|SUB(?:\s+MOTION)?)\.?\s+)?"
  r"(?P<action>ITL|OTP\s*/\s*AM|OTPA|OTP|RE-?REF\w*|REF(?:ER)?\s+FOR\s+(?:INTERIM\s+)?STUDY"
  r"|INT(?:ERIM)?\s+STUDY|LOT|LAY\s+ON\s+(?:THE\s+)?TABLE|IP|INDEF\w*\s+POST\w*|RECONSIDER\w*"
  r"|RECOMM?ITT?\w*|3RD\s+READ(?:ING)?)\b[^;]*?\b(?P<motion>ML|MF|MA)\b"
  r"(?:[^;]*?(?<![A-Z])" + VOTE + r"\b\s*(?:" + TALLY + r")?)?")
P("amendment", "amendment",
  r"(?:^|;\s*)(?:(?P<mover>" + NAME + r")\s+)?"
  r"(?P<what>(?:REMAINING\s+)?(?:COMMITTEE|COMM|FL|FLOOR|MAJ|MIN|APPR|APPROP|FIN(?:\s+COMM)?|W&M|ENROLLED(?:\s+BILLS?)?)\s*AM(?:END(?:MENT)?)?)"
  r"\s*(?:#\s*\d+|<\s*(?P<num>\d+)\s*>)?(?:\s*\(NEW TITLE\))?\s*,?\s*(?:INTRO(?:DUCED)?\s*)?/?\s*(?:AM\s+)?"
  r"(?P<motion>AA|AL|AF|ADOPTED|FAILED|LOST)\b[\s,]*(?:" + VOTE + r"\s*(?:" + TALLY + r")?)?")
P("special_order", "floor",
  r"^(?:.*[;,]\s*)?(?P<action>SPEC(?:IAL)?\.?\s+ORD(?:ER)?(?:ED)?\s+(?:TO|FOR)\s+"
  r"(?:" + DATE + r"|THE\s+\w+(?:\s+\w+)?|LATER\s+IN\s+(?:THE\s+)?DAY|\d+(?:ST|ND|RD|TH)\s+ITEM)(?:\s+(?:AT\s+)?" + TIME + r")?)"
  r"(?:[^;]*?\b(?P<motion>MA|ML)\b)?(?:[^;]*?(?<![A-Z])" + VOTE + r"\b)?", motion="MA")

# ---------------------------------------------------------------- routine
# Shapes deliberately left unclassified: notices that change nothing about
# where a bill stands. (id, pattern)
ROUTINE = [(pid, re.compile(rx, I)) for pid, rx in [
    ("seat_pocket", r"^IN\s+SEAT\s+POCKET\b"),
    ("copy_to_chair", r"^COPY\s+TO\s+CHAIRMAN\b"),
    ("due_date", r"^;?\s*DUE\s+(?:ON|DATE)\b"),
    ("prop_amendment", r"^(?:RE-?REF\s+)?(?:(?:" + NAME + r")\s+)?(?://[A-Z ]+//)?PROP(?:OSED)?\b"),
    ("extension", r"^(?:\d+\s+)?(?:CAL(?:ENDAR)?\s+|LEGISLATIVE\s+|LEG\s+)?(?:DAY\s+)?(?:CAL(?:ENDAR)?\s+)?EXT(?:ENSION)?\b"),
    ("appointments", r"^[<(\[{]?\s*(?:SPKR|PRES|SPEAKER|PRESIDENT)\s+APP(?:OIN)?TS?\b"),
    ("subcom_members", r"^[<(\[{]\s*(?:RE-?REF\s+|INT(?:ERIM)?\s+ST(?:UDY)?\s+)?SUB-?COMM?(?:ITTEE)?\b|^[(\[]\s*SUBC\b|^\(\s*(?:REPS?|SENS?)\s+(?!AM\b)[A-Z]"),
    ("conferee_change", r"^CONFEREE\s+CHANGE"),
    ("calendar_move", r"^MOVED\s+TO\s+(?:" + DATE + r")\s*(?:CAL(?:ENDAR)?\s+)?(?:WITHOUT|W/O)\s+OBJ"),
    ("conf_report_filed", r"^\(?(?:NEW\s+)?CONF(?:ERENCE)?\s+COMM(?:ITTEE)?\s+(?:REPORT|REPT)\b.*\b(?:FILED|SIGNED)\b"),
    ("report_filed", r"^(?:RE-?REF\s+)?REPORT\s+FILED\b"),
    ("deadline", r"^DEADLINE\s+CHANGED"),
    ("cancelled_notice", r"^(?://|==|\*\*)?\s*CANCELL?ED\b|^//CANCEL|^==CANCEL"),
    ("conditional_meeting", r"\bIF\s+NEC|\bIF\s+NEEDED"),
    ("storm_note", r"^\*+\s*(?:CHANGED|REPORTED)\b.*\bSTORM"),
    ("bare_citation", r"^(?:[HS]J\s*\d+[A-Z]?\s*,?\s*P|\(SEE\s+|\(JRNL|P\s*\d|[+\-]\s*P?\s*\d|\d+\s*[+\-)]?\s*\d*\s*$)"),
    ("veto_message", r"^(?:GOV(?:ERNOR)?'?S\s+)?(?:VETO\s+)?MESSAGE\b|^GOV'?S\s+VETO\s+MESSAGE"),
    ("notes", r"^[<(\[{]\s*(?:NOTE|NOTICE)\b|^NOTICE\s+OF\s+RECON|^\d+\s+LSR\s*:"),
]]


# ---------------------------------------------------------------- glue
MON = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7,
       "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def norm_date(tok, created, forward=False):
    """A 1989-1998 docket date -> MM/DD/YYYY, or None.

    MON## and M/D carry no year. forward=True (meeting notices, special
    orders): the created year, plus one if that puts the date more than 30
    days before the row was entered. Otherwise the year that puts the date
    nearest the created stamp. M/D/YY is 19YY for YY >= 50."""
    if forward and tok:
        t = re.sub(r"\s+", "", tok.upper()).rstrip(".")
        m = re.match(r"^([A-Z]{3})[A-Z]*\.?(\d{1,2})$", t) or re.match(r"^(\d{1,2})/(\d{1,2})$", t)
        if m:
            mo = MON.get(m.group(1)) if m.group(1).isalpha() else int(m.group(1))
            try:
                d = date(created.year, mo, int(m.group(2)))
                if (d - created.date()).days < -30:
                    d = date(created.year + 1, mo, int(m.group(2)))
                return d.strftime("%m/%d/%Y")
            except (ValueError, TypeError):
                return None
    if not tok:
        return None
    t = re.sub(r"\s+", "", tok.upper()).rstrip(".")
    m = re.match(r"^([A-Z]{3})[A-Z]*\.?(\d{1,2})$", t)
    yr = None
    if m and m.group(1) in MON:
        mo, dy = MON[m.group(1)], int(m.group(2))
    else:
        m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", t)
        if not m:
            return None
        mo, dy = int(m.group(1)), int(m.group(2))
        if m.group(3):
            yr = int(m.group(3))
            yr = yr + (1900 if yr >= 50 else 2000) if yr < 100 else yr
    if yr is None:
        best = None
        for y in (created.year - 1, created.year, created.year + 1):
            try:
                d = date(y, mo, dy)
            except ValueError:
                continue
            k = abs((d - created.date()).days)
            if best is None or k < best[0]:
                best = (k, d)
        return best[1].strftime("%m/%d/%Y") if best else None
    try:
        return date(yr, mo, dy).strftime("%m/%d/%Y")
    except ValueError:
        return None


REC_DECODE = [  # the captured code -> wording RECOMMENDATION already knows
    (r"^OTP\s*/\s*AM$|^OTPA$", "Ought to Pass with Amendment"),
    (r"^OTP$", "Ought to Pass"),
    (r"^ITL$", "Inexpedient to Legislate"),
    (r"^RE-?REF", "Rerefer to Committee"),
    (r"FOR\s+(?:INTERIM\s+)?STUDY$|^INT(?:ERIM)?\s+STUDY$|^IS$", "Refer for Interim Study"),
    (r"^LOT$", "Lay on Table"),
    (r"^IP$|^INDEF", "Indefinitely Postpone"),
    (r"^(?:WITHOUT|NO)\s+REC", "Without Recommendation"),
    (r"^RNF$", "Recommended, but Not Funded"),
]


def decode_rec(code):
    c = re.sub(r"\s+", " ", (code or "").strip().upper())
    for pat, full in REC_DECODE:
        if re.search(pat, c):
            return full
    return code


def decode_action(a):
    """The captured floor action -> the modern wording describe() knows."""
    s = re.sub(r"\s+", " ", (a or "").upper().strip())
    s = re.sub(r"^(?:SUBST?|SUB MOTION|MOVED(?: TO)?)\.? ", "", s)
    s = re.sub(r"^(?:FOR|TO) ", "", s)
    if s.startswith("ITL"):
        return "Inexpedient to Legislate"
    if re.match(r"^PASSED.*(?:WITH|W/) ?AM", s):
        return "Ought to Pass with Amendment"
    if s.startswith("PASSED"):
        return "Ought to Pass"
    if re.match(r"^(?:INTRODUCED AND )?ADOPTED", s):
        return "Adopt"
    if "STUDY" in s:
        return "Refer for Interim Study"
    if s.startswith("INDEF") or s == "IP":
        return "Indefinitely Postpone"
    if s.startswith("LAID ON") or s.startswith("LAY ON") or s == "LOT":
        return "Laid on Table"
    if s.startswith("TAKEN") or s.startswith("REMOVED"):
        return "Take from Table"
    if re.search(r"\bNONC", s):
        return "Nonconcur" + (" and Request Committee of Conference" if "CONF" in s else "")
    if re.search(r"\bCONC", s):
        return "Concur"
    if "ACCEDE" in s:
        return "Accede to Request for Committee of Conference"
    if "CONF" in s and "ADOPTED" in s:
        return "Conference Committee Report"
    if s.startswith("RECOMM") or s.startswith("RECOMIT"):
        return "Recommit"
    if s.startswith("RECONSIDER"):
        return "Reconsider"
    if s.startswith("3RD READ"):
        return "Third Reading"
    if s.startswith("RE-REF") or s.startswith("REREF"):
        return "Rerefer to Committee"
    if s.startswith("OTP/AM") or s == "OTPA" or s.startswith("OTP /"):
        return "Ought to Pass with Amendment"
    if s.startswith("OTP"):
        return "Ought to Pass"
    if s.startswith("SPEC"):
        return "Special Order " + re.sub(r"^SPEC(?:IAL)?\.?\s+ORD(?:ER)?(?:ED)?\s+", "", s).lower()
    if "SUSP" in s:
        return "Suspend Rules" + (" " + a.upper().split("RULES", 1)[1].strip(" ,").lower()
                                  if "RULES" in a.upper() else "")
    return a.title()


def committee_name(raw):
    try:
        import referrals, names  # noqa
        return referrals.AMP.sub(" and ", names.committee(referrals.expand(referrals.clean(raw))))
    except Exception:
        return raw


NEEDS_DATE = ("introduced", "floor", "rereferred", "amendment", "consent_off", "veto_override")


def fix(d, typ, created):
    """Turn the captured groups into what describe() reads. Returns d."""
    fwd = typ in ("hearing", "worksession", "exec", "conference_meeting")
    for k in ("date", "eff"):
        if d.get(k):
            d[k] = norm_date(d[k], created, forward=fwd)
    if d.get("chapter"):
        d["chapter"] = str(int(d["chapter"]))
    if d.get("vote"):
        d["vote"] = {"DIV": "DV"}.get(d["vote"].upper(), d["vote"].upper())
    if d.get("vote2"):
        d["vote"], d["y"], d["n"] = "RC", d.get("y2"), d.get("n2")
    for k in ("vote2", "y2", "n2"):
        d.pop(k, None)
    if typ == "report":
        d["side"] = {"MAJ": "Majority", "MAJORITY": "Majority", "MIN": "Minority",
                     "MINORITY": "Minority"}.get((d.get("side") or "").upper(), "")
        d["rec"] = decode_rec(d.get("rec"))
    if typ == "interim_report":
        r = (d.get("rec") or "").upper()
        if re.search(r"NOT\s+RE+C", r):
            d["rec"] = "Not Recommended for Future Legislation"
        elif re.search(r"\bRE+C\w*\s+FOR\b.*\bLEG", r):
            d["rec"] = "Recommended for Future Legislation"
        elif re.search(r"\bITL\b", r):
            d["rec"] = "Inexpedient to Legislate"
        elif re.search(r"\bOTP", r):
            d["rec"] = "Ought to Pass"
    if typ == "veto_override":
        o = (d.get("outcome") or "").upper()
        d["outcome"] = "Overridden" if o in ("OVERRIDDEN", "MA", "ADOPTED") else "Sustained"
    if typ == "floor":
        m = (d.get("motion") or "").upper()
        d["motion"] = {"ADOPTED": "MA", "FAILED": "ML", "LOST": "ML", "": "MA"}.get(m, m)
        act = decode_action(d.get("action"))
        if act.startswith("Special Order") or act.startswith("Suspend Rules"):
            # "SPECIAL ORDER TO MAR11" -> "Special Order to 03/11/1993", the
            # modern docket's own wording
            act = re.sub(MONTHS + r"\.?\s?\d{1,2}(?!\d)|\d{1,2}/\d{1,2}(?:/\d{2,4})?",
                         lambda m: norm_date(m.group(0), created, forward=True) or m.group(0), act, flags=I)
        mover = (d.get("mover") or "").strip()
        if mover:
            hon, _, rest = mover.partition(" ")
            hon = "Sen." if hon.upper().startswith("SEN") else "Rep."
            act = f"{act} ({hon} {rest.title()})"
        d["action"] = act
        if d.get("refer"):
            d["refer"] = committee_name(d["refer"])
    if typ == "amendment":
        w = (d.get("what") or "").upper()
        d["what"] = ("Enrolled Bill Amendment" if "ENROLLED" in w else
                     "Committee Amendment" if re.search(r"\b(?:COMM|COMMITTEE|MAJ|APPR\w*|FIN|W&M)\b", w) else
                     "Floor Amendment")
        d["motion"] = {"ADOPTED": "AA", "FAILED": "AF", "LOST": "AL"}.get(
            (d.get("motion") or "").upper(), (d.get("motion") or "").upper())
        d["num"] = d.get("num") or ""
    if typ in ("introduced", "vacated", "rereferred") and d.get("committee"):
        d["committee"] = committee_name(d["committee"])
    # Types whose sentence needs a date the line does not carry: the day the
    # clerk entered the row.
    if typ in NEEDS_DATE and not d.get("date"):
        d["date"] = created.strftime("%m/%d/%Y")
    return d
