#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.21
"""
The topics of the civics section: their order, their names, and their prose.

Read by build_civics.py, which does the rendering. Kept apart from it for one
reason: this file is the writing and that one is the machinery, and the
writing is the part a person who knows the building has to read before it
ships. Anyone can review a list of paragraphs; nobody should have to read a
page builder to check whether a description of a veto override is right.

PROPOSAL-civics.md is the brief. Two things in it govern every line here.

THE FIRST is what makes this worth building on Granite Record rather than
linking to somebody else's explainer: explain a thing, then show it happening,
with the record attached. Every page carries links into this site's own data,
and every number in the prose is one this site can produce.

THE SECOND is the risk. A wrong timestamp is embarrassing; a wrong description
of how an override works is the sort of error that gets quoted, and it
undermines the record it sits beside. So:

  * A number in the prose is one measured from this disk, and the page says
    what it is measuring and when.
  * Anything procedural or constitutional is stated plainly and linked to the
    authority -- the Constitution, the chamber rules, the agency -- so a
    reader who wants to check is one click away.
  * Where this site holds nothing to show, the page is shorter and says so
    rather than padding with prose nobody can verify.
  * Where a thing is genuinely contested, the page says it is debated, gives
    the strongest version of each side in a sentence, and stops.

TONE: plain, short sentences. Explain the mechanism, not whether it is good.
No "did you know", no exclamation marks, and no suggestion that the reader
ought to be more engaged than they already are. Someone looking up how to
testify has decided.
"""

# The order is the order of the proposal, and it is the order the "next
# topic" link at the foot of each page walks. Two groups: how the state
# works, then how to take part.
GROUPS = [
    ("How the state works",
     "The institutions, in the order they act on a bill."),
    ("How to take part",
     "The mechanics, which are more open than most people expect."),
]


def topic(slug, title, group, blurb, body, sources, holds=""):
    return {"slug": slug, "title": title, "group": group, "blurb": blurb,
            "body": body, "sources": sources, "holds": holds}


# ---------------------------------------------------------------------------
# Bodies are filled in below. Each is plain HTML: h2, p, ul, and the two
# classes this section adds -- .shows for a block that points into the record,
# and .caveat for a limit stated plainly.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# THE BODIES.
#
# Every figure below is one this site can produce, and the sentence says what
# it counts and over what period, because "most bills die" is an opinion and
# "855 of 2,234 were killed in the 2025-2026 term" is not.
#
# Where the record holds nothing to show -- the courts, the Executive Council
# -- the page is short and says so. Padding those with prose nobody here can
# check is exactly the failure the proposal warns about.
# ---------------------------------------------------------------------------

SHOWS = ('<div class="shows"><h3>In the record</h3>{}</div>')


# ---------------------------------------------------------------------------
# THE COURSE OF A BILL, AS A DIAGRAM.
#
# Written as data rather than as a wall of HTML so the sequence can be read
# and corrected here, in one place, by somebody who knows the building. It
# renders as nested ordered lists -- see the .flow rules in app.css for why
# that rather than an SVG.
#
# Each step is (name, what happens, mark), where mark is:
#   "stop" -- the bill can die here, and most bills die at one of these
#   "say"  -- a member of the public can speak here
#   ""     -- neither
# The marks are the argument of the diagram. A reader arrives thinking a bill
# moves along a pipeline; the shape they should leave with is a course with
# exits at almost every stage.
# ---------------------------------------------------------------------------
FLOW = [
    ("Before it is a bill", [
        ("Filed as an LSR", "A title and an idea, filed in the autumn. "
         "Attorneys at the Office of Legislative Services draft the text.", ""),
    ]),
    ("The first chamber", [
        ("Introduced and referred", "It gets a number and goes to a committee "
         "chosen by subject.", ""),
        ("Public hearing", "The sponsor introduces it, then anyone may speak "
         "for or against, or sign in without speaking.", "say"),
        ("Executive session", "The committee votes on what to recommend. A "
         "separate meeting from the hearing, often days later.", "stop"),
        ("Floor vote", "The full chamber decides, and is not bound by the "
         "committee's recommendation.", "stop"),
    ]),
    ("The second chamber", [
        ("Referred again", "The whole course repeats. Moving between chambers "
         "is called crossover, and there is a deadline for it.", ""),
        # TWO STEPS AND NOT ONE. Folded together, the diagram showed a single
        # "you may speak here" in the whole course, which is wrong and is
        # wrong in the direction that matters: a bill gets a public hearing in
        # each chamber, so a reader who missed the first has not missed their
        # chance. Splitting it also makes the two chambers read as the same
        # course run twice, which is the point of the page.
        ("Public hearing", "A second committee, a second public hearing. "
         "Missing the first chamber's does not cost you this one.", "say"),
        ("Executive session", "The second committee votes on its own "
         "recommendation.", "stop"),
        ("Floor vote", "If this chamber changes the bill, the first must "
         "agree to the change.", "stop"),
        ("Committee of conference", "Where it will not agree: members of both "
         "chambers try to write a version each will accept. Both chambers "
         "must then adopt the report unchanged.", "stop"),
    ]),
    ("The Governor", [
        ("Enrolment", "A final check of the text for errors before it is "
         "sent.", ""),
        ("Signed, vetoed, or left unsigned", "A bill left unsigned becomes "
         "law anyway.", "stop"),
        ("Override", "Two thirds of those voting in both chambers, or the "
         "veto stands.", "stop"),
    ]),
]

# The CSS class is .dies, not .stop: .stop belongs to the passage rail,
# where `.stop b` is a transparent-text circle, and reusing it rendered
# every marked step as invisible words in a grey disc. app.css says more.
#
# A mark is either one of these keys, or a (key, label) pair where the label
# differs step by step -- a constitutional threshold is a different number in
# each chamber, and "Needs a threshold" would be a worse sentence than the
# number it stands for.
MARKS = {"stop": ("dies", "mark", "Can die here"),
         "say": ("say", "say-m", "You may speak here"),
         "needs": ("needs", "needs-m", "")}


def mark_of(mark):
    if isinstance(mark, (tuple, list)) and len(mark) == 2:
        cls, mcls, _ = MARKS.get(mark[0], ("", "", ""))
        return cls, mcls, mark[1]
    return MARKS.get(mark, ("", "", ""))


def flow_diagram(flow=FLOW, heading="The course of a bill", level=2):
    """The sequence as nested lists. No image, no script, no SVG.

    level is what the phase names are written at, and it depends on where the
    diagram sits rather than on the diagram. On the bill page it is the first
    thing after the h1 and its four phases ARE that page's sections, so they
    are h2; on the constitution and testifying pages it follows a section
    heading and belongs under it, so they are h3. Written at 3 everywhere, the
    bill page went from a hidden h1 straight to h3, which is the jump
    LAUNCH.md records -- and a reader navigating by heading on the page that
    explains the whole process met four labels at the wrong depth.
    """
    out = [f'<div class="flow" role="group" aria-label="{heading}">'
           '<ol class="flowphases">']
    for name, steps in flow:
        out.append('<li class="phase">'
                   f'<h{level} class="phname">{name}</h{level}>'
                   '<ol class="steps">')
        for step, what, mark in steps:
            cls, mcls, label = mark_of(mark)
            out.append(f'<li class="step{" " + cls if cls else ""}">'
                       f'<b>{step}</b><span>{what}</span>'
                       + (f'<i class="{mcls}">{label}</i>' if label else "")
                       + "</li>")
        out.append("</ol></li>")
    out.append("</ol></div>")
    return "".join(out)


# ---------------------------------------------------------------------------
# AMENDING THE CONSTITUTION. Every step and every threshold here is one the
# prose on that page already states and cites to the Constitution itself; the
# diagram reorganises it rather than adding to it. The thresholds ARE the
# teaching point -- three fifths of the whole membership in each chamber, then
# two thirds of the voters, and no part for the Governor at any stage -- so
# they are the per-step labels rather than a generic mark.
# ---------------------------------------------------------------------------
FLOW_CACR = [
    ("How it starts", [
        ("Filed as a CACR", "A Constitutional Amendment Concurrent "
         "Resolution. Statutes change by bill; the constitution does not.",
         ""),
    ]),
    ("The first chamber", [
        ("Three fifths of the whole membership", "Not three fifths of those "
         "voting. 240 of the 400 House seats, whether or not everyone is "
         "there, so an absence counts against it.",
         ("needs", "240 of 400 in the House")),
    ]),
    ("The second chamber", [
        ("The same threshold again", "Three fifths of the entire "
         "membership of the other chamber, on the same terms.",
         ("needs", "Three fifths of all seats")),
    ]),
    ("The voters", [
        ("At the next general election", "Put to the people, where it needs "
         "a two-thirds majority to take effect.",
         ("needs", "Two thirds of those voting")),
        ("The Governor has no part", "No signature and no veto, at any point "
         "in this course.", ""),
    ]),
]

# ---------------------------------------------------------------------------
# TESTIFYING, in the order a person actually does it. Same source as the
# prose beside it: the chamber rules and the General Court's own sign-in
# system. The two things worth separating are that signing in and speaking
# are different acts, and that the second chamber gives a second chance.
# ---------------------------------------------------------------------------
FLOW_TESTIFY = [
    ("Find out", [
        ("The calendar", "Hearings are announced in the chamber's weekly "
         "calendar and on the General Court's meeting schedule. The median "
         "notice in the hearings parsed here is five days; some give one.",
         ""),
    ]),
    ("Sign in", [
        ("Online, for or against", "Your name and town, whether you are a "
         "member of the public or representing an organisation, and which "
         "side. You may attach written testimony.",
         ("needs", "Counted, and published")),
        ("Before the day ends", "The window opens once the hearing is "
         "scheduled and closes at the end of the day of the hearing.", ""),
    ]),
    ("At the hearing", [
        ("Speaking is separate", "A different act from signing in, and the "
         "chambers ask for it differently: a pink card in the House, a "
         "column to tick on the Senate's sheet. The sponsor speaks first, "
         "and a chair may set a time limit for everyone after.", "say"),
        ("You need not speak", "A sign-in without a word said is in the "
         "record and is counted.", ""),
    ]),
    ("Afterwards", [
        ("Executive session", "The committee votes on its recommendation at "
         "a later meeting. Testimony is not taken at it.", ""),
        ("The other chamber", "If the bill passes, it gets a hearing in the "
         "second chamber and a second sign-in window on the same terms.",
         "say"),
    ]),
]

# HOW A RULE IS MADE. Every step and every number here was read out of RSA
# 541-A itself -- the chapter is on this disk in db/NH_RSA.psv, all 51
# sections of it -- rather than from anybody's memory of how rulemaking works.
# RSA 541-A:3 gives the sequence in the statute's own words: "Except for
# interim or emergency rules, an agency shall adopt a rule by" filing a notice
# under :6, filing the text under :10, holding a public hearing under :11,
# filing a final proposal under :12, responding to the committee under :13,
# and adopting and filing under :14. The phases below are that list, with the
# deadlines from the sections it points at.
#
# THE EXCEPTION IS IN THE FIRST FIVE WORDS and is deliberately not drawn here.
# Interim rules (:19) and emergency rules (:18) skip most of this, last 180
# days, and are a different route rather than a branch of this one; the page's
# prose carries them. Drawing them inside the sequence would misdescribe the
# sequence.
#
# TWO CORRECTIONS WORTH KEEPING, both caught by checking the draft against the
# statute a second time. There is no bare "amend" in this chapter: the actions
# are adoption, readoption, readoption with amendment, and repeal. And part I,
# article 28-a protects political subdivisions generally -- counties, cities,
# towns and school districts -- not towns alone.
FLOW_RULES = [
    ("Before anyone can comment", [
        ("The statute hands it over", "A bill says the agency \"shall adopt "
         "rules\" about something, and stops. Everything it left open is "
         "settled from here on, by the agency rather than by the "
         "legislature.", ""),
        ("Notice in the register", "The agency sends the director of "
         "legislative services notice of what it means to do &mdash; adopt a "
         "rule, readopt one, readopt it with a change, or repeal it. The "
         "notice carries a fiscal impact statement and a statement that the "
         "rule lays no unfunded obligation on a county, city, town or school "
         "district.", ("needs", "20 days before the hearing")),
        ("The full text, not a summary", "At least one complete section of "
         "the rules as they would read, filed with the same office.", ""),
    ]),
    ("The public's turn", [
        ("A public hearing", "At least one, on every proposed rule. Anyone "
         "may speak, and anyone may send data, views or arguments in writing "
         "instead.", "say"),
        ("Comment stays open after it", "Written comment is taken for a "
         "further period once the hearing is over.",
         ("needs", "at least 5 business days")),
    ]),
    ("The legislature's turn", [
        ("The final proposal", "The agency weighs the comment, settles the "
         "text, and files it.",
         ("needs", "21 to 180 days after the notice")),
        ("The committee has 60 days", "The Joint Legislative Committee on "
         "Administrative Rules &mdash; JLCAR, legislators from both chambers "
         "&mdash; may approve the rule, approve it on a stated condition, or "
         "object to it.", "stop"),
        ("Silence is approval", "If the 60 days pass with no notice of "
         "approval, conditional approval or objection, the statute deems the "
         "rule approved. A rule can take effect without anyone having voted "
         "for it.", ("needs", "no vote required")),
        ("An objection is not a veto", "To actually stop a rule the "
         "committee has to sponsor a joint resolution, and that has to pass "
         "both chambers and go to the Governor like any other bill.", ""),
    ]),
    ("In force, and not for ever", [
        ("Effective the next day", "Once adopted and filed the rule binds "
         "whoever it covers, exactly as a statute would.", ""),
        ("Ten years, then it lapses", "No rule is effective for longer than "
         "ten years. To keep it, the agency runs the whole course again.",
         "stop"),
    ]),
]


BODY_GENERAL_COURT = """
<p>The New Hampshire legislative branch is made up of 400 representatives and
24 senators. It is the largest state legislature in the country: the last
redistricting drew House districts to <b>3,444 residents a seat</b>.</p>

<p>Members are paid <b>$200 for the two-year term</b> plus mileage &mdash; one
payment, in January of the first year, less withholding. It is often quoted as
$100 a year, which is the same money divided by two. Almost none have staff.
Most have other jobs, and the session is arranged around that: the House meets
on a small number of full days, and committee work fills the rest.</p>

<p>Four hundred is the number of seats, not the number of members. Seats fall
vacant and are filled at by-elections through the term, so the working size of
the House moves.</p>

<h2>A term is two years</h2>
<p>The General Court sits in two-year terms beginning in odd years. Bill
numbers are unique across the whole term, so there is only ever one HB 84 in
2025&ndash;2026, and there will be another in the next term. That is why every
address on this site carries the year.</p>
<p>Most bills are either passed or killed in the year they are filed. Two
things can happen to the rest, and they are not the same thing, though they
are easily confused because both leave a bill unfinished at the end of a
year.</p>
<p><b>Retaining</b> happens in the first year only. A committee keeps the bill
for more work, studies it over the autumn, and reports it to the chamber in
the second year, where it is voted on like any other bill. A retained bill
survives into the second year and keeps its number. Those show as
<b>carried over</b> here, and they are the ones people most often fail to
find, because they search the current year for a bill filed in the previous
one.</p>
<p><b>Interim study</b> happens in the second year only, and it ends the
bill. The committee studies it over the autumn and may report on it, but the
bill itself dies with the term. To come back it has to be filed again in the
next term, where it will be a new bill with a new number &mdash; so a bill
sent to interim study is not waiting to be taken up again, whatever the name
suggests.</p>

<h2>Every bill gets a public hearing</h2>
<p>This is unusual. In most states a committee chair can decline to hear a
bill and it dies without anyone speaking on it. In New Hampshire every bill
introduced is referred to a committee and given a public hearing that anyone
may attend and speak at.</p>

<h2>Bills and resolutions are not the same thing</h2>
<p>Which chamber a measure starts in follows from its prime sponsor: a
representative's bill begins in the House, a senator's in the Senate.</p>
<table><tbody>
<tr><td><b>HB</b></td><td><b>House Bill:</b> a proposed change to New
Hampshire law. Begins in the House, must pass both chambers, goes to the
Governor.</td></tr>
<tr><td><b>SB</b></td><td><b>Senate Bill:</b> begins in the Senate, otherwise
the same as a House Bill.</td></tr>
<tr><td><b>HR</b> / <b>SR</b></td><td><b>House or Senate Resolution:</b> a
formal, non-binding expression of opinion, policy preference, or internal
rule. It does not go to the other chamber or the Governor and does not change
any law.</td></tr>
<tr><td><b>HCR</b> / <b>SCR</b></td><td><b>House/Senate Concurrent
Resolution:</b> similar to an HR or SR, but voted on by both chambers.</td></tr>
<tr><td><b>CACR</b></td><td><b>Constitutional Amendment Concurrent
Resolution:</b> a proposed change to the state constitution, requiring a
three-fifths vote in both chambers and a two-thirds majority of voters. See
<a href="learn/the-constitution.html">The Constitution</a>.</td></tr>
</tbody></table>

<h2>How committees work</h2>
<p>Every bill is referred to a committee chosen by subject, and the committee
holds the public hearing, votes on a recommendation following an executive
session, and writes a report explaining its reasoning. If the committee is
split on what action to recommend, there are separate reports from the
majority and the minority. The full chamber is not bound by those
recommendations, but [[follows_committee]]% of the bills it decided this term
went the way its committee recommended.</p>

<p>The motions a committee most often recommends are these:</p>
<table><tbody>
<tr><td><b>OTP</b></td><td>Ought to Pass</td></tr>
<tr><td><b>OTP/A</b></td><td>Ought to Pass as Amended</td></tr>
<tr><td><b>ITL</b></td><td>Inexpedient to Legislate &mdash; kill the bill</td></tr>
<tr><td><b>IS</b></td><td>Interim Study &mdash; second year only, and the
bill dies with the term</td></tr>
<tr><td><b>Retain</b></td><td>Hold the bill in the committee &mdash; first
year only, and it returns in the second</td></tr>
</tbody></table>
""" + SHOWS.format("""
<p>The [[term]] term filed <b>[[bills]] bills</b>: [[hb]] House bills, [[sb]]
Senate bills, [[cacr]] constitutional amendments and [[resolutions]] resolutions.</p>
<p>The House is <b>[[house_seats]] seats and [[house_sitting]] sitting members</b> as
the record stands, with [[house_vacant]] vacant. The record shows that moving:
roll calls this term were taken with as many as [[seated_most]] members seated
and as few as [[seated_fewest]].</p>
<p>There are <b>[[house_districts]] House districts and [[senate_districts]] Senate
districts</b>. [[floterial]] of those House districts are floterial districts,
which cover several towns or wards together &mdash; see
<a href="learn/your-representatives.html">Finding your
representatives</a>.</p>
<p><a href="committees.html">Every committee</a>, who sits on it, and what it
did on each day it met. <a href="legislators.html">Every member</a>, with how
they voted.</p>""")


BODY_BILL = """
<p>A bill is a proposed change to New Hampshire law. It becomes law when both
chambers have passed it in identical form and the Governor has signed it. A
bill the Governor does not sign can still become law, either without a
signature or over a veto.</p>

<p>It has to clear the same course twice, once in each chamber, and it can
stop at any point on it. Most do.</p>
""" + flow_diagram() + """
<p>A public hearing and an executive session are different meetings, and they
are the two most often confused. A <b>public hearing</b> is where anyone may
speak, and the committee takes no decision at it. An <b>executive session</b>
is where the committee votes on what to recommend, usually days later and
usually covering several bills at once. See
<a href="learn/testifying.html">Testifying and attending</a> for what happens
at each, and
<a href="learn/governor-and-council.html">The Governor and the Executive
Council</a> for the last stage.</p>

<h2>How most bills end</h2>
<p>Of the [[bills]] bills filed in the [[term]] term, <b>[[killed]] were
killed</b> on a motion of Inexpedient to Legislate, written <b>ITL</b>, and
<b>[[signed]] were signed into law</b>. Among the rest, [[study]] were sent
for interim study, [[tabled]] died on the table, and [[session_end]] died when
the session ended without a final vote. Dying is the ordinary outcome, not a
failure of the bill or its sponsor.</p>

<h2>How a chamber votes, and what is recorded</h2>
<p>A chamber can put a question three ways. A <b>voice vote</b> records only
which side sounded louder. A <b>division</b> records the count but not who
voted which way. A <b>roll call</b> records every member by name. In the House
one is taken only when a member moves for it and the required number of other
members second the motion.</p>
<p>Across the [[all_bills]] bills in this record, <b>[[all_rollcall]] have at
least one recorded roll call and [[all_no_rollcall]] have none</b>. For a
great many bills there is no answer to "how did my representative vote",
because no record of names was ever made.</p>

<h2>Votes that need more than a majority</h2>
<p>Overriding a veto takes a two-thirds vote in each chamber, under Part
Second, Article 44 of the state constitution, counted against the members
voting. Amending the constitution takes three fifths of the entire membership
of each chamber, which is 240 of the 400 House seats, and then two thirds of
the voters, under Part Second, Article 100. That three-fifths threshold is
counted against every seat rather than against the members present, so a
measure can win a clear majority of those voting and fail anyway.</p>

<h2>The consent calendar</h2>
<p>A committee decides in executive session whether to send a bill to the
consent calendar, and the ones that go there are the bills it broadly agrees
about. Usually that agreement is unanimous, but not always: this
site&rsquo;s own record holds thousands of committee reports marked for the
consent calendar on a divided vote, among them reports carried 15&ndash;3 and
4&ndash;2. The calendar is then
decided in a single vote, without floor debate. What that vote adopts is the
committee's recommendation on each bill, which for some of them is to kill it.
Any member may ask for a bill to be taken off, and one that comes off is
debated and voted on by itself at the end of the regular calendar.</p>

<h2>Two bills, followed all the way</h2>
<p>Both ran the whole course, and in each the closest floor vote divided the
House without dividing it by party. A majority of Republicans voted one way, a
majority of Democrats the other, and a substantial minority of each party
voted against its own side.</p>

<h3>HB 1002 (2024) &mdash; what a public record may cost</h3>
<p>The ordinary course, start to finish. A town or agency answering a
right-to-know request may charge for the copies. The question was whether it
may also charge for the staff time spent finding and reviewing the records.
Supporters said small towns without full-time staff absorb real cost for
requests that can run to thousands of pages. Opponents said a fee that tracks
staff time can be set high enough to price an ordinary resident out of
oversight. It was signed into law.</p>
<p>It had a public hearing on 17 January 2024 and two executive sessions, all
three on video. The committee split, and the House divided <b>193 to 179</b>
on the majority's motion to pass the bill with an amendment: 62 Republicans
for and 125 against, 128 Democrats for and 53 against.</p>

<h3>HB 1215 (2024) &mdash; a bill that went to a committee of conference</h3>
<p>The same course by the longer road. It went to a Special Committee on
Housing, then to a second chamber that changed it. On the motion to accept
that change the House divided <b>172 to 180</b>, and the bill went to a
<b>committee of conference</b>. It dealt with how long an approved development
keeps the rules it was approved under, and where a building code dispute may
be appealed: local control of what gets built against the time and cost of
getting anything built. Six of its proceedings are on video, the conference
among them. The House then rejected the conference report <b>102 to 261</b>,
and the bill did not become law.</p>
<p class="caveat">Both are offered as examples of the process and not as
settled questions. The site takes no position on either. The arguments above
are summarised from what was said for and against, and the recordings are
there so you can check whether that summary is fair.</p>
""" + SHOWS.format("""
<p>Follow the two worked examples through the record:
<a href="bill/2024/hb1002.html">HB 1002 (2024)</a> and
<a href="bill/2024/hb1215.html">HB 1215 (2024)</a>, with each hearing, each
committee vote, each floor vote, and the recording of each.</p>
<p><b>Killed:</b>
<a href="bill/2025/hb66.html">HB 66</a>, on what counts as material a public
body must disclose under the right-to-know law. Two roll calls before it
died.</p>
<p><b>Signed into law:</b>
<a href="bill/2025/hb2.html">HB 2</a>, the budget trailer bill, which carries
the statutory changes the state budget needs, with [[hb2_rollcalls]] recorded
votes.</p>
<p><b>Vetoed, and the override failed:</b>
<a href="bill/2026/hb349.html">HB 349</a>, on whether optometrists may perform
ophthalmic laser procedures. It passed both chambers and was vetoed, and the
override fell at 145 to 206 where two thirds of those voting was needed.</p>
<p><b>Vetoed, and overridden anyway:</b>
<a href="bill/2026/hb2026.html">HB 2026</a>, on the ten-year transportation
plan.</p>
<p><b>Carried over</b> into the second year:
<a href="bill/2026/hb649.html">HB 649</a>, on the maintenance obligations of
motor vehicle operators, which passed in the second year and became law.</p>
<p>Across the [[all_bills]] bills on this site, [[all_rollcall]] have at least
one recorded vote and [[all_no_rollcall]] have none: most bills stop before
anybody is asked to go on the record.</p>
<p>Of the [[narrated]] bills with a narrative this term, <b>[[both_chambers]]
reached both chambers</b> and <b>[[conference]] went to a committee of
conference</b>. [[law]] became law: [[signed]] signed, [[unsigned]] without a
signature, and [[overridden]] over a veto.</p>""")


BODY_GOVERNOR = """
<p>The New Hampshire governor serves as the state's head of government and
supreme executive magistrate, responsible for enforcing state laws, proposing
the biennial state budget, and commanding the New Hampshire National
Guard.</p>

<p>The Governor is elected for two years, at the same election as the whole
legislature. When a bill has passed both chambers the Governor may sign it,
veto it, or do nothing, in which case it becomes law without a signature after
five days, Sundays excepted &mdash; unless the legislature has adjourned in the
meantime, and then it does not become law at all. Part Second, Article 44 of
the state constitution sets both.</p>

<h2>A veto is not always the end</h2>
<p>The legislature can override a veto, but it takes two thirds of the members
voting in each chamber. That is a high bar and most attempts fail.</p>
<p>Across the [[terms]] terms on this site there are <b>[[vetoed]] vetoed bills</b>.
In <b>[[veto_failed]]</b> the override failed. In <b>[[veto_overridden]]</b> it
succeeded and the bill became law over the Governor's objection.[[veto_pending]]</p>
<p>When the Governor vetoes a bill, the reasons are set out in a message read
into the record of the chamber the bill came from. Those messages are printed
in the House and Senate calendars, and this site carries [[veto_messages]] of the
[[vetoed]].</p>

<h2>The Executive Council</h2>
<p>Five councillors, each elected by district, meeting with the Governor.
Almost no state has anything like it, and not many people can describe what it
does.</p>
<p>Its approval is required for a great deal of what the executive branch
does: state contracts above a threshold, the appointment of commissioners and
judges, and pardons. A commissioner nominated by the Governor takes office
only when the Council confirms them, and a Governor who has the legislature
and not the Council cannot simply proceed.</p>
<p>The Council is genuinely debated. Supporters say it is a check on
executive power that no single elected officer should be without. Critics say
it gives five people a veto over routine administration and slows work that
has already been authorised. Both are arguments about the same fact.</p>
"""

BODY_GOVERNOR_HOLDS = """This site indexes the legislature, and it holds
almost nothing about the Executive Council: no agendas, no contract votes, no
nominations. What it does hold is the legislative half &mdash; the vetoes and
the override votes, linked below. For the Council's own record, go to the
Council."""


BODY_COURTS = """
<p>New Hampshire has three courts. The <b>Supreme Court</b> hears appeals and
is the final word on what a state law means. The <b>Superior Court</b> holds
jury trials and hears the more serious civil and criminal cases. The
<b>Circuit Court</b> handles the highest volume of cases each year, including
misdemeanours, small claims, probate and domestic relations.</p>

<h2>How a judge gets the job</h2>
<p>The Governor nominates and the Executive Council confirms &mdash; the same
route as a commissioner, which is the clearest illustration of what the
Council is for. There is no judicial election in New Hampshire at any level.
Judges serve until the age of seventy, which is set by the constitution
itself: Part Two, Article 78.</p>

<h2>Where the courts and the legislature meet</h2>
<p>The legislature writes statutes, and the courts decide what they mean when
there is a dispute over what was originally intended, and whether they are
permitted by the state or federal constitution. A decision striking down or
narrowing a statute is sometimes followed by bills amending the language
around the new standard, and those bills are in the record here like any
other.</p>
"""

BODY_COURTS_HOLDS = """This site holds no court records: no opinions, no
dockets, no filings. Judicial nominations go to the Executive Council rather
than the legislature, so they are not here either. This page is here because
you cannot follow a statute's life without knowing who else acts on it, and
it links out for anything more."""


BODY_CONSTITUTION = """
<p>New Hampshire's constitution took effect in 1784 and is among the oldest
still in force anywhere. It is in two parts. <b>Part First</b> is the Bill of
Rights &mdash; thirty-odd articles on what the state may not do. <b>Part
Second</b> is the Form of Government: the House, the Senate, the Governor, the
Council, the courts, and how each is chosen.</p>

<h2>It is not amended the way statutes are</h2>
<p>A statute changes when a bill passes both chambers and the Governor signs
it. The constitution does not. A change starts as a <b>CACR</b> &mdash; a
Constitutional Amendment Concurrent Resolution &mdash; and it has to clear
three thresholds, none of which involves the Governor.</p>
""" + flow_diagram(FLOW_CACR, "How the constitution is amended", level=3) + """

<h2>Why almost none get through</h2>
<p>The first step is the one that stops most of them, because a three-fifths
threshold measured against the whole membership is very close to
unattainable in a chamber where turnout varies.</p>
""" + SHOWS.format("""
<p>The [[term]] term filed <b>[[cacr]] CACRs</b>. [[cacr_voters]]
[[cacr_killed]] were killed outright, [[cacr_session_end]] died when the session
ended, [[cacr_one_chamber]] passed one chamber and stopped, and the rest are
still in committee or were postponed.</p>
<p>They sit in <a href="bills.html">the bill list</a> beside ordinary bills.
A CACR that shows "Passed one chamber" has a much longer way to go than a bill
with the same words beside it.</p>""")


BODY_AGENCIES = """
<p>The legislature passes a law. An agency carries it out. Health and Human
Services, Transportation, Environmental Services, Education, Safety, Revenue
Administration and the rest are where statutes get applied around New
Hampshire.</p>

<h2>How a commissioner gets the job</h2>
<p>Nominated by the Governor, confirmed by the Executive Council. That is the
same route as a judge, and it is the most concrete answer to
<a href="learn/governor-and-council.html">what the Council does</a>. A
commissioner serves a fixed term and can be reappointed the same way.</p>

<h2>How departments interact with the legislature</h2>
<p>A department is usually among the first bodies asked what a bill would
actually do, and often the body that would have to do it, so agency staff
appear at hearings regularly. An agency may support a bill, oppose it, or
appear as neutral and simply explain the effect.</p>
<p>If you have watched a hearing on this site and heard a department's staff
explain how a bill would be administered, or ask for a technical change, that
is what you were listening to. Departments may request legislation, but the
bill itself has to be filed by a legislator.</p>

<h2>What an agency cannot do</h2>
<p>It cannot give itself powers the statute does not grant. What it can do is
decide the detail, and it does that by writing
<a href="learn/administrative-rules.html">administrative rules</a>, which the
legislature approves through JLCAR, the Joint Legislative Committee on
Administrative Rules.</p>
""" + SHOWS.format("""
<p>Hearing recordings are linked from every bill's Videos tab, at the moment
the bill was taken up. <a href="committees.html">Committee pages</a> list
every day a committee met and what it heard.</p>""")


BODY_RULES = """
<p>An administrative rule is a requirement a state agency writes to carry out a
statute. Rules are made under RSA 541-A, the Administrative Procedure Act.</p>

<p>A statute rarely says how. The detail &mdash; the form, the threshold, the
deadline, the licence conditions &mdash; is left to the rule, and an
<a href="learn/state-agencies.html">agency</a> writes it, not the legislature.
A bill often says so in as many words: "the department shall adopt rules under
RSA 541-A". [[rules_delegated]] of the [[bills]] bills filed in the [[term]]
term carry a sentence of that kind.</p>

<h2>How a rule is made</h2>
<p>RSA 541-A:3 sets out the course, and the deadlines below come from the
sections it points at. The whole of it happens in the rulemaking register
&mdash; a free bulletin the legislature's own staff publish online each week
&mdash; and not in a chamber calendar, which is why a rulemaking can run its
full course without ever appearing where people look for legislation.</p>
""" + flow_diagram(FLOW_RULES, "How a rule is made", level=3) + """
<p>Two routes skip most of that. An <b>emergency rule</b> (RSA 541-A:18) takes
effect at once where the agency finds an imminent peril to public health or
safety, with only whatever notice the agency finds practicable; an
<b>interim rule</b> (RSA 541-A:19) is a fast track for matching a new statute,
a court decision or a federal requirement. Neither lasts more than 180 days,
so both end in the ordinary course above or they end altogether.</p>

<h2>How the legislature reviews a rule</h2>
<p>The <b>Joint Legislative Committee on Administrative Rules</b>, or JLCAR,
has members from both chambers and meets at least once a month. The final
proposal goes to it before the rule can be adopted. It may approve the rule,
approve it on condition of a stated change, or object to it. The grounds for an
objection are set out at RSA 541-A:13, IV, and include a rule beyond the
agency's authority and one contrary to the intent of the legislature.</p>
<p>An objection does not by itself stop the rule. To block it the committee
sponsors a joint resolution, which has to pass both chambers and go to the
Governor <a href="learn/how-a-bill-becomes-law.html">like any other
legislation</a>.</p>

<h2>After the bill becomes law</h2>
<p>The law is often not the whole answer. What the statute left open is settled
in the rule, and the rule's hearing is announced in the rulemaking register,
not in a chamber calendar.</p>
"""

BODY_RULES_HOLDS = """This site does not carry administrative rules
themselves, and does not track a rulemaking after a bill becomes law. The
rules register and JLCAR's own dockets are where that continues, linked
below."""


BODY_LOCAL = """
<p>Local government in New Hampshire is the city or town, the school district
and the county. There are [[municipalities]] cities and towns. A city has an
elected council or board of aldermen. Most towns have no council: the
legislative body is the town meeting, and the registered voters adopt the
budget themselves.</p>

<h2>How a town meeting works</h2>
<p><b>Warrant:</b> the notice of the meeting and the list of business to be
decided at it. Nothing done at a town meeting except electing its officers is
valid unless the subject was stated in the warrant (RSA 39:2). A <b>petitioned
article</b> is one the selectmen must put on the warrant on the written
application of 25 registered voters, or of 2 percent of the town's registered
voters, whichever is fewer (RSA 39:3). The articles are debated and amended
from the floor, and the budget is decided in the room.</p>

<h2>How SB 2 towns vote</h2>
<p>A town, school district or village district may instead adopt the
<b>official ballot referendum form of meeting</b> (RSA 40:13), called
<b>SB 2</b> after <a href="bill/1995/sb2.html">the 1995 bill</a> that created
it. The meeting is then in two parts. At the first, the <b>deliberative
session</b>, the articles are debated and amended and nothing is decided. At
the second, they are voted on by official ballot on election day, as the first
session left them.</p>

<h2>The default budget</h2>
<p><b>Default budget:</b> what a town or district that has adopted the
official ballot form falls back on if the operating budget on the ballot is
defeated. It is last year's appropriations, adjusted for debt service,
contracts and other obligations already incurred or mandated by law, and
reduced by one-time spending (RSA 40:13, IX(b)). The voters cannot amend it
(RSA 40:13, XI(b)). That is why the argument at a deliberative session is
often about the default rather than the proposed budget.</p>
"""

BODY_LOCAL_HOLDS = """This site covers the state legislature only. It holds no
town meeting warrants, no local budgets and no municipal votes. This page is
here because bills about towns are in the record constantly and the words in
them assume you already know all of this."""

# ---------------------------------------------------------------------------
# COUNTY AND MUNICIPAL GOVERNMENT, asked for by the person on 17 September:
# "pages to explain the various elected officials at the county and municipal
# level and their roles, how some towns have a mayor and city council and
# other towns have a select board".
#
# They are two pages rather than one because the two levels answer different
# questions and share almost nothing: a county is run by a body nobody is
# elected to, and a town or city is run by whichever of five or six forms its
# voters adopted. Both sit after "local-government", which already holds town
# meeting, SB 2 and the default budget, and neither repeats it -- each links
# it instead.
#
# Every RSA citation in both bodies was read on gc.nh.gov/rsa on 17 September
# 2026. Where a sentence could not be tied to a section it carries no citation
# rather than a guessed one; the county commissioners' number and the county
# nursing homes are the two that were rewritten for exactly that reason.
# ---------------------------------------------------------------------------
BODY_COUNTY = """
<p>New Hampshire has ten counties: Belknap, Carroll, Cheshire, Coos, Grafton,
Hillsborough, Merrimack, Rockingham, Strafford and Sullivan. Each is a unit of
government with its own budget, its own elected officers and its own line on
your property tax bill. Title II of the Revised Statutes is the law that
governs them.</p>

<p>A county has no council and no mayor. Its legislative body is a group of
people you already elected to something else.</p>

<h2>The county convention, which is the county delegation</h2>
<p><b>County convention:</b> the legislative body of a county. It consists of
the state representatives of the representative districts of the county
(RSA 24:1). Nobody is elected to it separately. A representative elected to
the House from a district in Grafton County is, by that fact alone, a member
of the Grafton County convention.</p>

<p>You will meet it under two names. The statutes say convention; legislators,
county staff and county budget papers usually say <b>delegation</b>. They are
the same body, and the statute itself uses both words in one sentence:
RSA 24:9-a gives the chair of the county delegation the job of setting the
time and place of the first meeting of the county convention.</p>

<p>A House district carries its county in its name &mdash; Rockingham 13,
Hillsborough 44 &mdash; and that name is what places its members. In the
present map every House district, floterial districts included, lies within a
single county, so each representative sits in exactly one delegation.</p>

<p>At its first regular meeting the convention elects a chairperson, a
vice-chairperson, a clerk and an <b>executive committee</b>, whose party
balance has to reflect the balance of the convention itself (RSA 24:2). The
first meeting is held during the week of the second Wednesday of December in
each even-numbered year, after the general election (RSA 24:9-a). Later
meetings are called by the chairperson or by a majority of the members, and
the chairperson has to call one when the county commissioners ask in writing
(RSA 24:9-c). Notice of the time, place and purpose goes to every member and
to a newspaper circulating in the county at least 7 days beforehand
(RSA 24:9-d).</p>

<h2>How the county budget is decided</h2>
<p>The budget is the delegation's main business, and RSA 24 sets out the
sequence. Two bodies act, in turn, and the order is what decides who can
change what.</p>

<p><b>The commissioners propose.</b> Before 1 December each year they deliver
their recommended budget to every member of the convention, to the chair of
the selectmen of every town and the mayor of every city in the county, and to
the Secretary of State (RSA 24:21-a, I). A county on an optional fiscal year
does this before 1 June instead (RSA 24:21-a, II).</p>

<p><b>There is a public hearing.</b> It is held not earlier than 5 nor later
than 20 days after that statement is mailed, and the clerk of the convention
publishes notice of it, with a summary of the budget, in a newspaper at least
3 days ahead (RSA 24:23).</p>

<p><b>The executive committee examines it.</b> The convention may designate
the executive committee to sit as a subcommittee on the budget and report
recommendations back to the full convention (RSA 24:2). That is where a county
budget is gone through line by line, but the committee recommends: it does not
appropriate.</p>

<p><b>The delegation votes.</b> Raising county taxes and making appropriations
are the convention's powers, not the commissioners' (RSA 24:13), so the figure
the convention adopts may be above or below the one the commissioners
recommended. The vote cannot be taken until 28 days have passed since the
recommendations were mailed (RSA 24:21-a, III). Appropriations are itemised in
detail and the clerk keeps the record of them (RSA 24:14, I).</p>

<p><b>Missing the deadline has a consequence.</b> A convention that has not
adopted a budget within 90 days of the start of the fiscal year does not get
an extension. The budget as recommended by the commissioners takes effect as
the county budget (RSA 24:14, II).</p>

<h2>What happens after the budget is adopted</h2>
<p>The delegation is still the body that has to be asked. Commissioners and
county officers may not pay out money that has not been appropriated, or
exceed what was appropriated (RSA 24:15).</p>

<p><b>Supplemental appropriation:</b> a further appropriation made after the
annual budget has been adopted. The commissioners may apply to the convention
for one, or the convention may take one up on its own initiative. It needs
notice to the members, towns and cities, a public hearing within 30 days of
that notice, and its own vote of the convention (RSA 24:14-a). A narrower
emergency route runs through the executive committee, again after a public
hearing (RSA 24:15).</p>

<p>The convention also sets what the elected county officers are paid. It
establishes their salaries, benefits and other compensation every two years,
acting on the executive committee's recommendation, before the filing period
for the next election (RSA 23:7).</p>

<p>These are the same people this site already holds pages for. A state
representative has a second job most residents never see: the member who voted
on a bill in Concord in the morning may spend the evening setting a county
budget that arrives on the same property tax bill as the town's.</p>

<h2>The county commissioners</h2>
<p><b>County commissioners:</b> the county's executive, and the body that
runs it day to day. RSA 662:4 divides each of the ten counties into three
county commissioner districts, and one commissioner is chosen from each, so
every county has three. In most counties each is elected by the voters of that
district alone; in Carroll and Sullivan, each is elected from a district but by
the voters of the whole county (RSA 653:1, VI).</p>

<p>They choose a chairman and a clerk from among themselves (RSA 28:1). They
have the custody and care of all property belonging to the county (RSA 28:4),
run its departments from day to day, and prepare the budget the convention
votes on. The county treasurer pays money out only on their orders
(RSA 29:1).</p>

<h2>The officers on the county part of your ballot</h2>
<p>Five county officers are elected by the voters of the county at the state
general election: a <b>sheriff</b>, a <b>county attorney</b>, a <b>county
treasurer</b>, a <b>register of deeds</b> and a <b>register of probate</b>.
The term is two years, except in Rockingham County, which moved to four-year
terms in 2022, and Coos County, which did so in 2024 (RSA 653:1, V).</p>

<p><b>Sheriff:</b> the sheriff and the sheriff's deputies serve and execute
writs and other process directed to the department, and the department's
bailiffs provide security in the state courts (RSA 104:5). Sheriffs and
deputies have the same authority throughout the state as in their own county
to serve process, investigate crimes and apprehend, and may enforce civil
orders issued by any court (RSA 104:6).</p>

<p><b>County attorney:</b> the county's prosecutor. The office acts under the
direction of the Attorney General, performs the Attorney General's duties for
the county in the Attorney General's absence, and prosecutes or defends suits
in which the county has an interest (RSA 7:34).</p>

<p><b>County treasurer:</b> has custody of all money belonging to the county,
pays it out only on the commissioners' orders, keeps the account of what comes
in and goes out, and reports at the end of the fiscal year (RSA 29:1).</p>

<p><b>Register of deeds:</b> keeps the registry of deeds, which is the
county's record of who owns which land. Every deed, mortgage and plan is
recorded there and kept in the office the county provides (RSA 478:1).</p>

<p><b>Register of probate:</b> still elected, and almost all of the duties are
gone. The probate court became a division of the Circuit Court, and most of
RSA 548 was repealed with effect from 1 July 2011. What is left is a duty to
work with the administrative judge of the Circuit Court on preserving closed
files of historical significance (RSA 548:5). The office is named in the
constitution, so removing it takes an amendment and not a bill:
<a href="bill/2022/cacr21.html">CACR 21 (2022)</a> would have struck it out,
passed both chambers, and went to the voters, where it did not reach the
<a href="learn/the-constitution.html">two thirds of those voting</a> an
amendment needs.</p>

<p><b>Coroner:</b> New Hampshire elects none. RSA 611, the coroners chapter,
is repealed, and sudden, unexpected or unnatural deaths are investigated by
the state's Office of the Chief Medical Examiner under RSA 611-B rather than
by a county officer.</p>

<h2>What the county pays for, and where the money comes from</h2>
<p>Two things dominate a county budget. A county may provide, keep and
maintain facilities for the confinement of prisoners, administered by a county
department of corrections (RSA 30-B:1); that is the jail. And long-term care is
a county liability: counties reimburse the state for nursing home and other
long-term care Medicaid spending on the residents each county is answerable
for, to the extent of the whole non-federal share of it, subject to a limit on
how fast that bill may rise (RSA 167:18-a). Counties also run nursing homes of
their own, which no chapter of Title II creates and which they have run for
long enough that the statutes treat them as a given. The registry of deeds, the
sheriff's department and the county attorney's office are on the county payroll
as well.</p>

<p>No county collects a tax directly. The county treasurer issues a warrant to
the selectmen of each town in the county, requiring them to assess and collect
that town's share of the county tax and pay it over (RSA 29:11). The town
raises it in the property tax. That is why a tax bill carries a county line
beside the town, school and state education lines, and why a vote taken by a
delegation in December turns up on a bill months later.</p>
""" + SHOWS.format("""
<p><a href="legislators.html">Every member of both chambers</a> has a page
here, with the county and district they were elected from. The House members
from a county are that county's convention, so the roster is the membership
list.</p>
<p><a href="directory/towns.html">Every town and ward</a> is listed by county,
with the districts that cover it.</p>""")

BODY_COUNTY_HOLDS = """This site is the record of the state legislature, and
county government is not in it. There are no county budgets here, no minutes
or warrants of a county convention, no county election results and no county
officers' accounts. What it does hold is the roster: the representatives who
make up each county's delegation have pages here because of the other office
they were elected to. The county's own record is kept by the county."""


BODY_TOWNS = """
<p>There are [[municipalities]] cities and towns in New Hampshire, and Title
III of the Revised Statutes governs all of them. The difference between a city
and a town is not size, and not the word on the sign. It is who the
legislative body is &mdash; who adopts the budget and passes the
ordinances.</p>

<p>In a town, the legislative body is the voters themselves, assembled at
<a href="learn/local-government.html">town meeting</a>. In a city, it is an
elected council. Nearly everything else follows from that one difference.</p>

<h2>A town: the meeting decides, the selectboard carries it out</h2>
<p><b>Selectmen:</b> the executive of a town. The statutes say selectmen
(RSA 41:8); selectboard is the term in common use now for the same body. A
town elects one selectman each year for a 3-year term, which makes a board of
three (RSA 41:8). On the written application of 25 registered voters, or 2
percent of them, whichever is less and never fewer than 10, the question of
increasing the board to 5 goes on the ballot (RSA 41:8-b).</p>

<p>The board does not set policy on its own account. It carries out what the
meeting voted, administers the town between meetings, and puts together the
warrant for the next one. The money it spends is the money the meeting
appropriated.</p>

<p><b>Moderator:</b> presides at the meeting, regulates its business, decides
questions of order and declares every vote passed. The moderator may postpone
a session for a weather warning, or for an emergency that makes the place
unsafe (RSA 40:4).</p>

<h2>A city: a council decides, a mayor or a manager carries it out</h2>
<p>A city has no town meeting. The powers the law vests in towns, or in the
inhabitants of them, are exercised by the city council (RSA 47:1). The council
may be called a <b>city council</b> or a <b>board of aldermen</b>; the name is
the city's and the function is the same. How many members there are, and
whether they are elected by ward or at large or both, is set by the city's
charter.</p>

<p><b>Mayor:</b> under the general law the mayor is the chief executive
officer of the city (RSA 45:7), presides in the board of aldermen, and has a
veto the aldermen can override only by two thirds of all the aldermen elected
(RSA 45:9).</p>

<p><b>Council-manager:</b> the other common arrangement, set out for charter
cities at RSA 49-C. The charter names either the mayor or an appointed
<b>city manager</b> as chief administrative officer, heading the
administrative branch, supervising the city's administrative affairs and
carrying out the policies the elected body enacts (RSA 49-C:16). The council
appoints the manager for an indefinite term and fixes the salary, by a vote of
at least a majority of the council, and the charter sets out how the manager
may be removed (RSA 49-C:17). Where a city runs this way, the mayor chairs the
council and the manager runs the administration.</p>

<h2>Town managers and town administrators</h2>
<p>A town may adopt the town manager form under RSA 37. It takes a vote: the
chapter does not operate in a town until a majority of the voters present and
voting at an annual meeting adopt it, and 10 or more voters may petition to
put the question on the warrant (RSA 37:11). Once adopted, the selectmen
appoint the manager (RSA 37:2), who becomes the administrative head of all
departments of the town and is responsible for administering them (RSA 37:5).
The manager appoints and dismisses subordinate staff, examines the affairs of
any department, and prepares the year's expenditure and revenue estimates
(RSA 37:6). What the manager does not get are the things the meeting and the
selectmen keep: warning town meetings, making bylaws, borrowing money, and
assessing or collecting taxes (RSA 37:5).</p>

<p>A <b>town administrator</b> is a different thing, and the difference
matters when you are working out who decides. There is no statutory office of
town administrator. The selectmen hire one to help them run the town's
business, and the administrator works under their direct supervision. Adopting
RSA 37 moves authority from the elected board to an appointed officer; hiring
an administrator does not, and needs no vote of the meeting.</p>

<h2>Village districts</h2>
<p><b>Village district:</b> a smaller unit inside one or more towns, formed to
provide one service or a few. On the petition of 10 or more voters domiciled
in a village the selectmen fix the district's bounds, and the statute lists
the purposes one may be formed for: fire protection, street lighting, water
supply, sidewalks and drains, sewage, parks, police, roads and ambulance
service among them (RSA 52:1). Once formed it is a body corporate and politic,
with the same powers a town has in relation to the same objects
(RSA 52:3).</p>

<p>A district holds its own meeting and has its own moderator, clerk,
treasurer and commissioners, who have the same powers over the district's
business as a town's moderator, clerk, treasurer and selectmen have over the
town's (RSA 52:8). A village district may adopt the manager form on the same
footing as a town (RSA 37:14). If you live in one, it is a separate line on
your tax bill.</p>

<h2>The other names on a town ballot</h2>
<p>Some offices every town elects by ballot: selectmen, the moderator, the
supervisors of the checklist, the town clerk, the town treasurer and highway
agents (RSA 669:15).</p>

<p>Others a town elects only if it has voted to: the tax collector, town
assessors, constables or police officers, the fire chief or firewards, and the
elected members of a planning board, zoning board of adjustment, budget
committee or conservation commission (RSA 669:17).</p>

<table><tbody>
<tr><td><b>Town clerk</b></td><td>Keeps the town's records, issues the
licences and registrations, and runs the mechanics of elections. A town may
vote to make the term 3 years (RSA 41:16-b).</td></tr>
<tr><td><b>Tax collector</b></td><td>Collects the taxes the selectmen commit,
remits them to the treasurer weekly, keeps the account of what was collected
and abated, and reports at year end (RSA 41:35).</td></tr>
<tr><td><b>Clerk/tax collector</b></td><td>Many towns have combined the two
into one office. It takes a petitioned article and a majority at the annual
meeting, and the combined officer is then elected for a term of one year or
three (RSA 41:45-a).</td></tr>
<tr><td><b>Treasurer</b></td><td>Has custody of the town's money, pays it out
on the selectmen's orders, keeps the accounts, and invests what is not
immediately needed under the selectmen's investment policy
(RSA 41:29).</td></tr>
<tr><td><b>Supervisors of the checklist</b></td><td>Three legal voters of the
town, who keep the voter checklist. One is elected every even-numbered year
for 6 years, unless the town has adopted 3-year terms
(RSA 41:46-a).</td></tr>
<tr><td><b>Trustees of trust funds</b></td><td>Three, or five if the town has
voted for five, administering the funds held in trust for the town. One is
elected each year for three years (RSA 31:22).</td></tr>
<tr><td><b>Library trustees</b></td><td>Any odd number the town decides on,
elected at town meeting for staggered 3-year terms (RSA 202-A:6).</td></tr>
<tr><td><b>Cemetery trustees</b></td><td>Elected by ballot at the annual town
meeting to replace those whose terms expire; in a city, chosen as the city's
ordinance provides (RSA 289:6).</td></tr>
</tbody></table>

<h2>Planning board and zoning board of adjustment</h2>
<p>These two decide what may be built and where, and whether a particular
property is let off a rule. In some towns you elect them and in others you do
not, and which it is was a choice the town made.</p>

<p>A <b>planning board</b> has 5 or 7 members in most towns, 7 or 9 in a town
with a council, and 9 in a city. Members are appointed by the selectmen unless
the local legislative body has voted that they be elected, and a town that has
voted for election may later vote to go back (RSA 673:2).</p>

<p>A <b>zoning board of adjustment</b> has 5 members, either elected in the
manner RSA 669 prescribes or appointed in the manner the local legislative
body prescribes (RSA 673:3).</p>

<h2>School boards and the SAU</h2>
<p>A school district is a body separate from the town, with its own meeting,
its own budget and its own ballot. Its <b>school board</b> has 3, 5, 7 or 9
members as the district votes, and 3 if it has not voted, elected for three
years with an equal number elected each year where that can be done
(RSA 671:4). A cooperative school district covers more than one town, and its
board is made up of members from each.</p>

<p><b>School administrative unit:</b> the SAU, the administrative body serving
one district or several together. Its board is made up of the school board
members of the districts in it. That board arranges superintendent services,
sets the salaries of the administrative staff and apportions the cost among
the member districts, and it has the power to remove the superintendent
(RSA 194-C:5). This is why the superintendent answers to a board you did not
vote for directly: you elected your district's school board, and your
district's school board sits on the SAU board.</p>

<h2>Changing the form of government: the charter</h2>
<p><b>Charter:</b> a municipality's own written constitution, adopted by its
voters. Any incorporated town or city, whatever its population, may draw one
up under RSA 49-B, the home rule chapter. A charter prepared under RSA 49-C
establishes a city government; one prepared under RSA 49-D establishes a town
government (RSA 49-B:2).</p>

<p>It starts with a question on the ballot. On the petition of 25 registered
voters, or 2 percent of them, whichever is less and never fewer than 10, the
voters are asked whether a charter commission shall be established
(RSA 49-B:3). If they say yes, the commission is elected, it reports, and the
charter it writes goes back to the voters at a referendum. An existing charter
is amended by the same route (RSA 49-B:5), and a municipality may vote to
return to the form of government it had before (RSA 49-B:12).</p>

<p>A town charter does not have to abolish the town meeting. RSA 49-D:3 sets
out the forms a town charter may choose between: a town council; an official
ballot town council; a budgetary town meeting, which keeps the meeting but
limits it to the operating budget and bonds; an official ballot town meeting;
and a representative town meeting, where members elected from districts vote
in place of the whole electorate. A charter may also make a <b>town
manager</b> the chief administrative officer, under the town council-town
manager form (RSA 49-D:2).</p>

<p>This is why two towns of the same size, ten miles apart, can be run in
entirely different ways, and why the offices on your ballot are not the
offices on your neighbour's.</p>
""" + SHOWS.format("""
<p><a href="directory/towns.html">Every town and ward</a> is listed here with
the House and Senate districts that cover it, which is the route from where
you live to the legislators who represent it.</p>
<p>Bills changing what towns and cities may do arrive in the record
constantly. They are in <a href="bills.html">the bill list</a> with everything
else, and a bill's page names the committee that heard it.</p>""")

BODY_TOWNS_HOLDS = """This site holds the state legislature's record and
nothing municipal. There are no town or city budgets here, no warrants, no
minutes of a selectboard or a council, no local ordinances and no municipal
election results. Your town or city clerk keeps those. This page is here
because bills about towns and cities arrive in the record every week, written
as though you already knew all of this."""


BODY_TESTIFYING = """
<p><b>Every legislative meeting and hearing is open to the public.</b> You may
attend in person, and most are live streamed and archived, so you can watch
one later. Where you may <i>speak</i> is narrower: a public hearing is the
meeting for that, and it is the only one at which members of the public are
heard. You may attend any other meeting &mdash; an executive session, a
subcommittee, a work session &mdash; but not speak at it.</p>
<p>A public hearing is the meeting at which a committee hears a bill before it
votes on what to recommend. Every bill introduced gets one, and anyone may
speak at it.</p>
<p>You do not need to be invited, and you do not need to speak: signing in for
or against is itself part of the record, and it is counted. Nor does a bill
have to affect you. Committees hear bills for the whole state rather than for
a district, so anyone may speak on any bill, whoever they are and wherever
they live.</p>

<h2>How hearings are announced</h2>
<p>A hearing is announced in the chamber's calendar, which is published weekly,
and on the meeting schedule the General Court keeps online. The notice gives
the committee, the bill, the day, the time and the room. Across the
[[notice_hearings]] hearings those calendars announced in the [[term]] term,
the median notice is <b>[[notice_median]] days</b>. That is the gap between the
day the calendar is published and the day of the hearing.</p>
<p>Notices name the room by building:</p>
<table><tbody>
<tr><td><b>SH</b></td><td><b>State House:</b> 107 North Main Street,
Concord.</td></tr>
<tr><td><b>LOB</b></td><td><b>Legislative Office Building:</b> 33 North State
Street, Concord. Out of use for hearings while it is being worked on, and
named in older notices.</td></tr>
<tr><td><b>GP</b></td><td><b>Granite Place:</b> 1 Granite Place, Concord, where
House committee meetings are now held.</td></tr>
</tbody></table>
<p>The Legislative Office Building is expected back in service around the
start of the next term, and Granite Place to drop out of the rota when it is.
That is what is expected rather than what has been announced, and this site
will say it has happened when the notices say so. <b>Go by the notice for the
hearing you are attending</b> &mdash; it names the building and the room, and
it is right about the day it was published whatever this page says.</p>
<p>Both chambers live stream their standing committee hearings, so a hearing
can be watched as it happens.</p>

<h2>Signing in</h2>
<p>The House takes sign-ins online, before and during the hearing. You give
your name and town, say whether you are a member of the public or representing
an organisation, and mark yourself supporting, opposing or neutral. You may
attach written testimony. The committee is given the counts, and the sign-ins
are published after the hearing.</p>
<p>The window is not open indefinitely. It opens once the hearing is scheduled
and published, and it closes at the end of the day of the hearing. If the bill
passes one chamber and gets a hearing in the other, there is a second window on
the same terms.</p>
<p>The sign-ins are not part of the bill's docket, and no link on the docket
leads to them. They are kept in the General Court's own sign-in records, which
its website offers as a lookup of its own. How long that lookup keeps a
hearing is not documented anywhere this site can point to.</p>

<h2>The steps, in order</h2>
""" + flow_diagram(FLOW_TESTIFY, "How to testify, in order", level=3) + """

<h2>Speaking at the hearing</h2>
<p>Speaking is a separate act from signing in, and the two chambers ask for it
differently. In the <b>House</b> you fill in a pink card. In the <b>Senate</b>
there is one sign-in sheet for everything, with a column to tick if you want
to speak.</p>
<p>The sponsor speaks first, then the committee generally hears anyone who has
asked to. <b>No rule sets a time limit, but chairs may set one and often do</b>
&mdash; commonly the sponsor is given as long as they need and everyone else
about three minutes. A chair will also ask you to be brief when many people are
waiting, and repeating what the last speaker said is the thing most likely to
get you moved along.</p>
<p>You do not have to be an expert. The most useful testimony is the most
concrete: what this bill would do to you, in your town, said in particulars
rather than in general &mdash; the cost, the date it would take effect, the
number of people it would reach, whatever the specific is in your case.</p>

<h2>What happens after the hearing</h2>
<p>The committee votes on what to recommend at a later meeting called an
executive session. It is public and you may attend it, but no testimony is
taken at it. The committee then reports its recommendation to the chamber, and
where it was split the majority and the minority each write a report. Whether
you spoke or only signed in, the counts and any written testimony stay in the
record.</p>
""" + SHOWS.format("""
<p>This site holds <b>[[hearings]] public hearings</b>, each with the committee
and the day. Every bill's page shows its own hearings, and the Videos tab links
the recording at the moment the bill was taken up.
<a href="committees.html">A committee's page</a> lists every day it met and
what it heard.</p>
<p>Bills also carry the sign-in counts: how many people registered supporting,
opposing and neutral. Names and written testimony are not published here.</p>""")


BODY_REPS = """
<p>New Hampshire is divided into [[house_districts]] House districts and
[[senate_districts]] Senate districts. Every resident lives in one Senate
district and in at least one House district, set by the town or ward they live
in. Most people have more than one representative, because a House district is
built out of whole towns and wards rather than drawn to equal population.</p>

<h2>What the district numbering means</h2>
<p>A House district is written as a county and a number: Rockingham 13,
Hillsborough 44, or abbreviated to <b>Rock 13</b>. The number is not a rank or
a size. It is an index within that county, and the map is redrawn every ten
years after the federal census.</p>
<p>A district may be a single town, one or more wards of a city, or several
small towns together. Where it has more than one seat, its members are elected
at large across the whole of it, not one to each town. The largest elects
[[largest]] representatives.</p>
<p>Senate districts are numbered 1 to [[senate_districts]] across the whole
state rather than by county, and many cross county lines. Each elects one
senator, and district 22 is written <b>SD22</b>.</p>

<h2>What a floterial district is</h2>
<p>A floterial district is a House district drawn over several towns or wards
that each already elect their own representative. It elects one or more
additional members across all of them together.</p>
<p>A town's population is rarely an exact multiple of what one seat is worth.
A floterial is where those remainders are pooled, rather than a town being
split between two districts.</p>
<p>If you live in one of those towns, you are represented by both: the members
of your own district, and the floterial members you share with the towns
around you. [[floterial]] of the [[house_districts]] House districts are
floterial, and they account for [[floterial_seats]] of the [[house_seats]]
seats.</p>

<h2>How to contact a member</h2>
<p>[[members_email]] of the [[members_sitting]] sitting members publish an
email address in the General Court's directory. Almost none have staff, so a
message to a representative is read by that representative. Most have other
jobs.</p>
""" + SHOWS.format("""
<p><a href="legislators.html">Every member of both chambers</a>, with their
district, party and county, and every recorded vote they have cast.</p>
<p>Every <a href="committees.html">committee page</a> lists its members and
has a button that opens an email to all of them at once.</p>""")


BODY_SITE = """
<p>Granite Record is an index of the New Hampshire General Court's own record:
[[all_bills]] bills across [[terms]] two-year terms, back to [[first_year]],
with what each bill does, who sponsored it, when it was heard, how it was
voted on, and where in the recording that happened. It is built by machine
from the General Court's published files and rebuilt every night.</p>

<p>Older terms hold less, and every bill's page says what its term carries and
what has not been fetched.</p>

<h2>How to find a bill, a member or a town</h2>
<p>The <b>Search</b> button in the header finds legislators, committees, towns
and this site's own pages: typing Litchfield offers both the town and the
representative of that name. Anything else goes to
<a href="bills.html">the bill search</a>, which takes a bill number, several
separated by commas, or words from a title, sponsor or committee. It covers
one term at a time and narrows by committee, topic, prime sponsor, status and
floor vote day. <a href="legislators.html">Every sitting member</a> and
<a href="committees.html">every committee</a> has a page of their own.</p>

<h2>What a bill's page holds</h2>
<ul>
<li><b>Summary</b> &mdash; the General Court's own analysis, the current
status, and a narrative of what has happened, in order, with each action
linked to the journal or calendar that recorded it.</li>
<li><b>Bill Text</b> &mdash; the text and its amendments, where more than one
was published.</li>
<li><b>Votes</b> &mdash; every recorded roll call, by member. Voice and
division votes appear in the narrative but have no member-by-member record to
show, because none was made.</li>
<li><b>Videos</b> &mdash; the hearing and floor recordings, opened at the
moment the bill was taken up.</li>
<li><b>Reports</b> &mdash; what the committee recommended and why, in the
committee's own words, and the Governor's message where a bill was
vetoed.</li>
<li><b>Sponsors</b>, and <b>Documents</b> &mdash; the official pages this all
comes from.</li>
</ul>

<h2>What a timestamp claims</h2>
<p>Not all of them claim the same thing, and the page says which.</p>
<ul>
<li>Where the chair can be heard taking the bill up, that is the time.</li>
<li>Where a roll call has a clock time in the official record, that is
used.</li>
<li>Otherwise the time is estimated from where the bill falls in the recording
and marked <b>approximate</b>. It can be several minutes out.</li>
<li>Where no moment has been found, the page says so and offers the whole
sitting.</li>
</ul>
<p>Captions are never quoted here. Automatic transcription renders "HB 1381"
as "HP 1381" often enough that a quotation would be a transcription error
wearing the clothes of a citation. The timestamp is the claim. The recording
is the evidence.</p>

<h2>Reading the shorthand</h2>
<table><tbody>
<tr><td><b>OTP</b></td><td><b>Ought to Pass:</b> a motion to pass the bill</td></tr>
<tr><td><b>OTP/A</b></td><td><b>Ought to Pass with Amendment</b></td></tr>
<tr><td><b>ITL</b></td><td><b>Inexpedient to Legislate:</b> a motion to kill it</td></tr>
<tr><td><b>MA</b> / <b>MF</b></td><td><b>Motion Adopted / Motion Failed</b></td></tr>
<tr><td><b>VV</b></td><td><b>Voice vote:</b> no count and no names</td></tr>
<tr><td><b>DV</b></td><td><b>Division vote:</b> counted, names not recorded</td></tr>
<tr><td><b>RC</b></td><td><b>Roll call:</b> each member recorded by name</td></tr>
<tr><td><b>CC</b></td><td><b>Consent Calendar:</b> the committee's
recommendation, to pass or to kill, adopted with the whole calendar in one
vote, without floor debate</td></tr>
<tr><td><b>OT3rdg</b></td><td><b>Ordered to a third reading</b></td></tr>
<tr><td><b>HJ</b> / <b>SJ</b></td><td><b>House or Senate Journal:</b> the
chamber's own record of the day, cited by issue and sometimes page</td></tr>
<tr><td><b>-FN</b></td><td><b>Fiscal note:</b> an estimate of what the bill
would cost</td></tr>
<tr><td><b>-A</b></td><td><b>Appropriation:</b> the bill contains one</td></tr>
<tr><td><b>-LOCAL</b></td><td><b>Local fiscal impact:</b> on towns or schools</td></tr>
</tbody></table>

<h2>Following a bill</h2>
<p>A bill still moving through the General Court carries an RSS feed, and so
does every sitting member, every committee still sitting, and every topic. The
<b>Follow</b> control on a record's page gives the address where there is one.
There are also feeds for the record's newest actions and for hearings coming
up. A bill's feed ends once the bill is settled. There is no email option yet.
No account, no email address, nothing to leak.</p>

<h2>How to report an error</h2>
<p>Every record's page carries a <b>Report a problem</b> box at the foot,
because this will be wrong somewhere. It sends nothing that identifies you,
which also means we cannot reply. For an answer, or for an error on these
explanatory pages, write to
<a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a>.</p>
"""

# The official addresses these pages send a reader to. Kept in one place
# because every one of them is a promise that something is there, and a
# promise made eleven times in eleven files is one nobody checks.
#
# check_civics_links.py verifies them over the network when somebody asks it
# to. Nothing here has been verified by this file, and preflight only checks
# that they are well formed and on a state domain -- so a link that has moved
# will read as fine until that script is run.
GC = "https://gc.nh.gov"
RSA = GC + "/rsa/html"
NH = "https://www.nh.gov"

# NOT on gc.nh.gov. The address this pointed at answers 404, and the state
# publishes the constitution under nh.gov rather than the General Court.
SRC_CONSTITUTION = ("The New Hampshire Constitution",
                    "https://www.nh.gov/glance/state-constitution")
# Both chambers publish their rules as a PDF now; the .aspx pages both of
# these named answer 404, which is how a source link rots quietly.
SRC_HOUSE_RULES = ("House Rules", GC + "/house/aboutthehouse/houseRules.pdf")
SRC_SENATE_RULES = ("Senate Rules", GC + "/senate/about_senate/senate_rules.pdf")
SRC_RSA = ("New Hampshire Revised Statutes Annotated", RSA)
# THIS SITE, not the General Court. Their address-lookup page answers 404,
# and the record already holds what it was there to give: a town page
# names that town's House and Senate districts, its Executive Councillor
# and its member of Congress, and the directory lists every town. A link
# to our own pages cannot rot without us noticing, because preflight
# resolves every internal link the builders write.
SRC_FIND_MEMBER = ("Find your legislators, by town",
                   "/directory")
SRC_TESTIFY = ("House online testimony sign-in",
               GC + "/house/committees/remotetestimony/")
SRC_SCHEDULE = ("House meeting schedule", GC + "/house/schedule/dailyschedule.aspx")
SRC_SENATE_SCHEDULE = ("Senate meeting schedule",
                       GC + "/senate/schedule/dailyschedule.aspx")
SRC_CALENDARS = ("House calendars and journals",
                 GC + "/house/calendars_journals/")
# The three below were NH + "/council", "/governor" and "/agencies" until
# 11 September, when a browser found each one a "Page Not Found" on nh.gov.
# The replacements are the addresses nh.gov itself links to: the governor
# from its front page, the council from its agency list, and the list
# from its front page's "State Agency" link.
SRC_COUNCIL = ("The Executive Council", "https://www.council.nh.gov/")
SRC_GOVERNOR = ("The Governor's office", "https://www.governor.nh.gov/")
SRC_COURTS = ("New Hampshire Judicial Branch", "https://www.courts.nh.gov")
SRC_RULES = ("Administrative rules, RSA 541-A",
             RSA + "/NHTOC/NHTOC-LV-541-A.htm")
SRC_JLCAR = ("Joint Legislative Committee on Administrative Rules",
             GC + "/rules")
SRC_AGENCIES = ("State agencies, A to Z",
                NH + "/government/state-government-agencies")
SRC_SOS = ("Secretary of State", "https://www.sos.nh.gov")
# Neither of the two below is an authority, and both are labelled so, the way
# SRC_BALLOT_LIST is. They are here because each is the place the officials
# themselves send a resident next, and neither the state nor the counties
# publish an equivalent in one place.
SRC_COUNTIES = ("County government, county by county (New Hampshire "
                "Association of Counties, a membership body)",
                "https://www.nhcounties.org")
SRC_NHMA = ("Guidance for towns and cities (New Hampshire Municipal "
            "Association, a membership body)",
            "https://www.nhmunicipal.org")
# Not an authority, and labelled so. Every other source on these pages is
# the body that made the thing; this is a third party's list, included
# because it carries the vote share each amendment got at the polls and
# the Secretary of State does not publish those in one place.
SRC_BALLOT_LIST = ("Past amendments and their vote shares (Ballotpedia, "
                   "a third party)",
                   "https://ballotpedia.org/List_of_New_Hampshire_ballot_measures")
# The office that answers for a court decision on a statute, which is
# where a reader of the courts page most often wants to go next.
SRC_DOJ = ("New Hampshire Department of Justice", "https://www.doj.nh.gov")


# ---------------------------------------------------------------------------
# The eleven. Order is the proposal's order and it is what the "next topic"
# link walks; the hub and the sitemap read the same list.
# ---------------------------------------------------------------------------
HOW = "How the state works"
PART = "How to take part"

TOPICS = [
    topic("general-court", "The General Court", HOW,
          "400 representatives and 24 senators, paid $200 for the two-year "
          "term. The largest state legislature in the country, and the page "
          "everything else here hangs off.",
          BODY_GENERAL_COURT,
          [SRC_CONSTITUTION, SRC_HOUSE_RULES, SRC_SENATE_RULES,
           SRC_FIND_MEMBER]),

    topic("how-a-bill-becomes-law", "How a bill becomes law", HOW,
          "From an idea filed in the autumn to a law that takes effect, and "
          "the several places along the way where a bill can stop.",
          BODY_BILL,
          [SRC_HOUSE_RULES, SRC_SENATE_RULES, SRC_CALENDARS,
           SRC_CONSTITUTION]),

    topic("governor-and-council", "The Governor and the Executive Council",
          HOW,
          "The Governor signs or vetoes. The Council -- five members, elected "
          "by district -- approves contracts, nominations and pardons, and "
          "almost no resident could say what it does.",
          BODY_GOVERNOR,
          [SRC_CONSTITUTION, SRC_GOVERNOR, SRC_COUNCIL],
          BODY_GOVERNOR_HOLDS),

    topic("the-courts", "The courts", HOW,
          "Supreme, Superior and Circuit; how judges are appointed and how "
          "long they serve; and where the legislature and the courts meet.",
          BODY_COURTS,
          [SRC_COURTS, SRC_CONSTITUTION, SRC_DOJ],
          BODY_COURTS_HOLDS),

    topic("the-constitution", "The Constitution", HOW,
          "One of the oldest still in force, and it is not amended the way "
          "statutes are: a CACR needs three fifths of both chambers and then "
          "the voters.",
          BODY_CONSTITUTION,
          [SRC_CONSTITUTION, SRC_SOS, SRC_BALLOT_LIST]),

    topic("state-agencies", "State agencies", HOW,
          "Who actually carries out what the legislature passes, and how a "
          "commissioner gets the job.",
          BODY_AGENCIES,
          [SRC_AGENCIES, SRC_COUNCIL, SRC_CONSTITUTION]),

    topic("administrative-rules", "Administrative rules", HOW,
          "A statute says what shall happen; the rules say how, and the "
          "agency writes them. This is the least visible part of the process "
          "and one of the most consequential.",
          BODY_RULES,
          [SRC_RULES, SRC_JLCAR, SRC_RSA],
          BODY_RULES_HOLDS),

    topic("local-government", "Town meeting and local government", HOW,
          "Where warrant articles, default budgets and \u201cSB 2 towns\u201d "
          "come from -- all of which turn up in bills here, unexplained.",
          BODY_LOCAL,
          [SRC_RSA, SRC_SOS],
          BODY_LOCAL_HOLDS),

    topic("county-government", "County government", HOW,
          "Ten counties, and the body that sets each one's budget is the "
          "state representatives you already elected, meeting under a second "
          "name.",
          BODY_COUNTY,
          [SRC_RSA, SRC_COUNTIES, SRC_SOS],
          BODY_COUNTY_HOLDS),

    topic("city-and-town-government", "Cities, towns and who runs them", HOW,
          "A town meeting and a selectboard, or a council and a mayor, or a "
          "council and a manager -- and the other offices you elect without "
          "being told what they do.",
          BODY_TOWNS,
          [SRC_RSA, SRC_NHMA, SRC_SOS],
          BODY_TOWNS_HOLDS),

    topic("testifying", "Testifying and attending", PART,
          "The most open part of the process and the least known. Anyone may "
          "speak on any bill, and you do not need to be invited.",
          BODY_TESTIFYING,
          [SRC_TESTIFY, SRC_SCHEDULE, SRC_SENATE_SCHEDULE, SRC_CALENDARS]),

    topic("your-representatives", "Finding your representatives", PART,
          "By town and by district, and what the district numbering means.",
          BODY_REPS,
          [SRC_FIND_MEMBER, SRC_SOS]),

    topic("using-this-site", "Using this site", PART,
          "What the tabs hold, what a timestamp claims and what it does not, "
          "how to follow a bill, and how to tell us we are wrong.",
          BODY_SITE,
          [SRC_CALENDARS, SRC_RSA]),
]
