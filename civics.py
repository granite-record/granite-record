#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.7
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

SHOWS = ('<div class="shows"><h4>In the record</h4>{}</div>')


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


def flow_diagram(flow=FLOW, heading="The course of a bill"):
    """The sequence as nested lists. No image, no script, no SVG."""
    out = [f'<div class="flow" role="group" aria-label="{heading}">'
           '<ol class="flowphases">']
    for name, steps in flow:
        out.append('<li class="phase">'
                   f'<h3 class="phname">{name}</h3><ol class="steps">')
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
        ("Speaking is separate", "A different act from signing in, and you "
         "fill in a card to do it. The sponsor speaks first.", "say"),
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


BODY_GENERAL_COURT = """
<p>The General Court is the legislature: a House of 400 representatives and
a Senate of 24. It is the largest state legislature in the country, and the
districts are correspondingly small.</p>

<p>Members are paid $100 a year plus mileage. Almost none have staff. Most
have other jobs, and the session is arranged around that: the House meets on
a small number of full days, and committee work fills the rest.</p>

<p>Four hundred is the number of seats, not the number of members. Seats fall
vacant and are filled at by-elections through the term, so the working size of
the House moves.</p>

<h2>A term is two years</h2>
<p>The General Court sits in two-year terms beginning in odd years. Bill
numbers are unique across the whole term, so there is only ever one HB 84 in
2025&ndash;2026 &mdash; and there will be another in the next term. That is
why every address on this site carries the year.</p>
<p>Most bills are settled in the year they are filed. Some are not: a
committee can retain a bill for further work, or the chamber can send it for
interim study, and it is taken up again the following year. Those show as
<b>carried over</b> here, and they are the ones people most often fail to
find, because they search the current year for a bill filed in the previous
one.</p>

<h2>Every bill gets a public hearing</h2>
<p>This is unusual. In most states a committee chair can decline to hear a
bill and it dies without anyone speaking on it. In New Hampshire every bill
introduced is referred to a committee and given a public hearing that anyone
may attend and speak at. That is why the hearing recordings matter here more
than they would elsewhere: the hearing is where the substantive argument
actually happens.</p>

<h2>Bills and resolutions are not the same thing</h2>
<p>Which chamber a measure starts in follows from its prime sponsor: a
representative's bill begins in the House, a senator's in the Senate.</p>
<table><tbody>
<tr><td><b>HB</b></td><td>House Bill &mdash; begins in the House, must pass
both chambers, goes to the Governor</td></tr>
<tr><td><b>SB</b></td><td>Senate Bill &mdash; begins in the Senate, otherwise
the same</td></tr>
<tr><td><b>HR</b> / <b>SR</b></td><td>A resolution voted on by that chamber
alone. It does not go to the other chamber or the Governor and does not change
any law.</td></tr>
<tr><td><b>HCR</b> / <b>SCR</b></td><td>Concurrent resolution &mdash;
introduced in one chamber, voted on by both</td></tr>
<tr><td><b>CACR</b></td><td>A proposed change to the state constitution, which
works differently from everything else here. See
<a href="learn/the-constitution.html">The Constitution</a>.</td></tr>
</tbody></table>

<h2>Committees do the work</h2>
<p>Every bill is referred to a committee chosen by subject, and the committee
holds the hearing, votes on a recommendation, and writes a report explaining
it. The chamber is not bound by that recommendation, but it usually follows
it.</p>
""" + SHOWS.format("""
<p>The 2025&ndash;2026 term filed <b>2,234 bills</b>: 1,564 House bills, 566
Senate bills, 31 constitutional amendments and 73 resolutions.</p>
<p>The House is <b>400 seats and 382 sitting members</b> as this was written,
with 18 vacant. The record shows that moving: roll calls this term were taken
with as many as 399 members seated and as few as 384.</p>
<p>There are <b>203 House districts and 24 Senate districts</b>. Of the 162
ordinary House districts, 75 elect a single member and 42 elect two; the
largest elects ten. The other 41 are floterial &mdash; see
<a href="learn/your-representatives.html">Finding your
representatives</a>.</p>
<p><a href="committees.html">Every committee</a>, who sits on it, and what it
did on each day it met. <a href="legislators.html">Every member</a>, with how
they voted.</p>""")


BODY_BILL = """
<p>A bill has to clear the same course twice, once in each chamber, and can
stop at any point on it. Most do.</p>
""" + flow_diagram() + """
<p>Two of those stages are worth separating, because they are the two most
often confused. A <b>public hearing</b> is where anyone may speak; the
committee takes no decision at it. An <b>executive session</b> is where the
committee votes on what to recommend, usually days later and usually covering
several bills at once. See
<a href="learn/testifying.html">Testifying and attending</a> for what happens
at each, and
<a href="learn/governor-and-council.html">The Governor and the Executive
Council</a> for the last stage.</p>

<h2>Most bills stop somewhere</h2>
<p>Of the 2,234 bills filed in the 2025&ndash;2026 term, <b>855 were
killed</b> &mdash; the motion is <i>Inexpedient to Legislate</i> &mdash; and
<b>632 were signed into law</b>. Another 214 were sent for interim study, 197
died on the table, and 126 died when the session ended without a final vote.
Dying is the ordinary outcome, not a failure of the bill or its sponsor.</p>

<h2>Most votes leave no record of who voted</h2>
<p>Unless a member requests a roll call, a chamber votes by voice or by
division. A voice vote records only which side sounded louder. A division
records the count but not who voted which way. Only a roll call records each
member by name.</p>
<p>Across the 4,230 bills on this site, <b>865 have at least one recorded roll
call and 3,365 have none</b>. For a great many bills there is simply no answer
to "how did my representative vote" &mdash; not because it is hidden, but
because it was never recorded.</p>

<h2>A majority is not always enough</h2>
<p>Overriding a veto takes two thirds of those voting. A constitutional
amendment takes three fifths of the entire membership &mdash; 240 of 400 in
the House &mdash; whether or not everyone shows up. Measures regularly win a
clear majority and fail anyway.</p>

<h2>The consent calendar</h2>
<p>A bill goes on the consent calendar when the committee vote was unanimous
or nearly so and no dissenting member objected to it being placed there. It
then passes without floor debate, along with everything else on the calendar,
in a single vote. Ten members may petition to pull a bill off and have it
taken up separately.</p>

<h2>Two bills, followed all the way</h2>
<p>These two are here because the whole course is on the record for both, and
because each divided the House without dividing it by party &mdash; which is
the useful kind of example. In both, a majority of Republicans voted one way
and a majority of Democrats the other, and in both a substantial minority of
each party voted against its own side. There is a real argument on each
side of them.</p>

<h3>HB 1002 (2024) &mdash; what a public record may cost</h3>
<p>The ordinary course, start to finish. A town or agency answering a
right-to-know request may charge for the copies; the question was whether it
may also charge for the staff time spent finding and reviewing the records.
Supporters said small towns without full-time staff absorb real cost for
requests that can run to thousands of pages. Opponents said a fee that
tracks staff time can be set high enough to price an ordinary resident out of
oversight. It was signed into law.</p>
<p>Its page carries the <b>public hearing of 17 January 2024</b> and two
<b>executive sessions</b>, each with the recording and the moment the
committee took the bill up &mdash; so the difference between the two kinds of
meeting can be watched rather than taken on trust. The House divided
<b>193 to 179</b>: 62 Republicans for and 125 against, 128 Democrats for and
53 against.</p>

<h3>HB 1215 (2024) &mdash; the complicated path</h3>
<p>The same course, but it took the longer road: a Special Committee on
Housing, then a second chamber that changed it, then a <b>committee of
conference</b> to settle the difference. Conference is the stage hardest to
picture and the one least often recorded; here it is. The bill dealt with how
long a town has to decide a development application and what may be appealed
&mdash; local control of what gets built against the time and cost of getting
anything built. Six of its proceedings are on video.</p>
<p class="caveat">Both are offered as examples of the process and not as
settled questions. The site takes no position on either; the arguments above
are summarised from what was said for and against, and the recordings are
there so you can check whether that summary is fair.</p>
""" + SHOWS.format("""
<p>Follow the two worked examples through the record:
<a href="bill/2024/hb1002.html">HB 1002 (2024)</a> and
<a href="bill/2024/hb1215.html">HB 1215 (2024)</a> &mdash; each hearing, each
committee vote, each floor vote, and the recording of each.</p>
<p><b>Killed in committee:</b>
<a href="bill/2026/sb71.html">SB 71-FN</a>, on cooperation with federal immigration
authorities &mdash; three roll calls before it died.</p>
<p><b>Signed into law:</b>
<a href="bill/2025/hb2.html">HB 2</a>, the budget trailer bill, with 44 recorded
votes and a fiscal note running to four years.</p>
<p><b>Vetoed, and the override failed:</b>
<a href="bill/2026/hb1442.html">HB 1442-FN</a> &mdash; passed both chambers, vetoed,
and the House fell short of two thirds on the override.</p>
<p><b>Vetoed, and overridden anyway:</b>
<a href="bill/2026/hb2026.html">HB 2026</a>, on the ten-year transportation
plan.</p>
<p><b>Carried over</b> into the second year:
<a href="bill/2026/hb751.html">HB 751-FN</a>.</p>
<p>Of the 2,233 bills with a narrative this term, <b>1,068 reached both
chambers</b> and <b>86 went to a committee of conference</b>. 649 became law:
632 signed, 10 without a signature, and 7 over a veto.</p>""")


BODY_GOVERNOR = """
<p>The Governor is elected for two years, at the same election as the whole
legislature. When a bill has passed both chambers the Governor may sign it,
veto it, or do nothing &mdash; in which case it becomes law without a
signature.</p>

<h2>A veto is not the end</h2>
<p>The legislature can override a veto, but it takes two thirds of the members
voting in each chamber. That is a high bar and most attempts fail.</p>
<p>Across the two terms on this site there are <b>68 vetoed bills</b>. In
<b>58</b> the override failed. In <b>9</b> it succeeded and the bill became law
over the Governor's objection. One was still awaiting its override vote when
this was written.</p>
<p>When the Governor vetoes a bill, the reasons are set out in a message read
into the record of the chamber the bill came from. Those messages are printed
in the House and Senate calendars, and this site carries 67 of the 68.</p>

<h2>The Executive Council</h2>
<p>Five councillors, each elected by district, meeting with the Governor.
Almost no state has anything like it, and almost no resident could describe
what it does.</p>
<p>Its consent is required for a great deal of what the executive branch does:
state contracts above a threshold, the appointment of commissioners and
judges, and pardons. A Governor who has the legislature and not the Council
cannot simply proceed. This is the concrete answer to what the Council is for
&mdash; a commissioner nominated by the Governor takes office only when the
Council confirms them.</p>
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
<b>Circuit Court</b> handles most of what people actually encounter: district
court matters, probate, and family cases.</p>

<h2>How a judge gets the job</h2>
<p>The Governor nominates and the Executive Council confirms &mdash; the same
route as a commissioner, which is the clearest illustration of what the
Council is for. There is no judicial election in New Hampshire at any level.
Judges serve until the age of seventy.</p>

<h2>Where the courts and the legislature meet</h2>
<p>The legislature writes statutes; the courts decide what they mean when a
case turns on it, and whether they are permitted by the state or federal
constitution. A decision striking down or narrowing a statute is often
followed by bills responding to it, and those bills are in the record here
like any other.</p>
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
""" + flow_diagram(FLOW_CACR, "How the constitution is amended") + """

<h2>Why almost none get through</h2>
<p>The first step is the one that stops most of them, because a three-fifths
threshold measured against the whole membership is very close to
unattainable in a chamber where turnout varies.</p>
""" + SHOWS.format("""
<p>There are <b>57 CACRs</b> in the record across the two terms this site
covers. <b>None of them reached the voters.</b> Nineteen were killed outright,
twenty-seven died when the session ended, three passed one chamber and stopped,
and the rest are still in committee or were postponed.</p>
<p>They sit in <a href="bills.html">the bill list</a> beside ordinary bills.
A CACR that shows "Passed one chamber" has a much longer way to go than a bill
with the same words beside it.</p>""")


BODY_AGENCIES = """
<p>The legislature passes a law. An agency carries it out. Health and Human
Services, Transportation, Environmental Services, Education, Safety, Revenue
Administration and the rest are where a statute becomes something that happens
to somebody.</p>

<h2>How a commissioner gets the job</h2>
<p>Nominated by the Governor, confirmed by the Executive Council. That is the
same route as a judge, and it is the most concrete answer to
<a href="learn/governor-and-council.html">what the Council does</a>. A
commissioner serves a fixed term and can be reappointed the same way.</p>

<h2>You have probably already met them</h2>
<p>A department is usually among the first bodies asked what a bill would
actually do, and often the body that would have to do it, so agency staff
appear at hearings regularly. An agency may support a bill, oppose it, or
appear as neutral and simply explain the effect.</p>
<p>If you have watched a hearing on this site and heard someone explain why a
bill would be difficult to administer, that is what you were listening
to.</p>

<h2>What an agency cannot do</h2>
<p>It cannot give itself powers the statute does not grant. What it can do is
decide the detail, and it does that by writing rules &mdash; which is the
next page.</p>
""" + SHOWS.format("""
<p>Hearing recordings are linked from every bill's Videos tab, at the moment
the bill was taken up. <a href="committees.html">Committee pages</a> list
every day a committee met and what it heard.</p>""")


BODY_RULES = """
<p>This is the least visible part of the process and one of the most
consequential.</p>
<p>A statute says what shall happen. It rarely says how. The detail &mdash;
the form, the threshold, the deadline, the licence conditions &mdash; goes
into <b>administrative rules</b>, and the agency writes those, not the
legislature. A bill will often say, in as many words, that "the department
shall adopt rules under RSA 541-A". That sentence is the legislature handing
over the detail.</p>

<h2>The legislature keeps a say</h2>
<p>Rules do not simply take effect. The <b>Joint Legislative Committee on
Administrative Rules</b> &mdash; JLCAR, members of both chambers &mdash;
reviews proposed rules and can object to one it thinks goes beyond what the
statute allows or conflicts with legislative intent. This is where the
legislature keeps a hold on how its own statute is carried out.</p>

<h2>Why it matters to a reader here</h2>
<p>If you have followed a bill through this site to the point where it became
law, the law may not be the end of the story. The rule written afterwards is
often where the question you actually care about is answered, and it is
written in a process with far fewer people watching than the hearing you
listened to.</p>
"""

BODY_RULES_HOLDS = """This site does not carry administrative rules
themselves, and does not track a rulemaking after a bill becomes law. The
rules register and JLCAR's own dockets are where that continues, linked
below."""


BODY_LOCAL = """
<p>New Hampshire does a great deal at town level, and the vocabulary turns up
constantly in bills here without being explained.</p>

<h2>Town meeting</h2>
<p>The traditional form: residents gather on a single day, debate the
<b>warrant</b> &mdash; the list of articles to be decided &mdash; amend
articles from the floor, and vote on them there and then. The budget is
decided by the people in the room.</p>

<h2>"SB 2 towns"</h2>
<p>A town that has adopted the official-ballot form votes on warrant articles
by ballot on election day instead, after a separate deliberative session where
the articles can be amended. It is called SB 2 after the bill that created the
option, and many towns and school districts have adopted it.</p>
<p>The trade is participation for reach: a deliberative session is attended by
far fewer people than a town meeting, but far more people vote on the
result.</p>

<h2>The default budget</h2>
<p>If a town rejects the budget put to it, spending does not stop. It falls
back to the <b>default budget</b> &mdash; broadly last year's, adjusted for
obligations already contracted. Which is why the argument at a deliberative
session is often not about the proposed budget at all but about what the
default would be.</p>
"""

BODY_LOCAL_HOLDS = """This site covers the state legislature only. It holds no
town meeting warrants, no local budgets and no municipal votes. This page is
here because bills about towns are in the record constantly and the words in
them assume you already know all of this."""


BODY_TESTIFYING = """
<p>Anyone may testify on any bill. You do not need to be invited, you do not
need to live in the district, and you do not need to speak &mdash; signing in
for or against is itself part of the record, and it is counted.</p>

<h2>How to find out a hearing is happening</h2>
<p>Hearings are announced in the chamber's calendar, which is published
weekly, and on the meeting schedule the General Court keeps online. Across the
hearings this site has parsed out of those calendars, the <b>median notice is
five days</b> &mdash; the calendar carrying the announcement is published, on
the middle case, five days before the hearing itself. Some give as little as
one day.</p>

<h2>Signing in</h2>
<p>The House takes sign-ins online, before and during the hearing. You give
your name and town, say whether you are a member of the public or representing
an organisation, and mark yourself supporting, opposing or neutral. You may
attach written testimony. The counts are read by the committee and they are
published afterwards.</p>
<p>The window is not open indefinitely. Sign-in opens once the hearing is
scheduled and published, and closes at the end of the day of the hearing. If
the bill passes one chamber and gets a hearing in the other, there is a second
window on the same terms.</p>

<h2>All of it, in order</h2>
""" + flow_diagram(FLOW_TESTIFY, "How to testify, in order") + """

<h2>Speaking</h2>
<p>Speaking is a separate thing from signing in, and you fill in a card to do
it. The sponsor speaks first, then the committee generally hears anyone who
has asked to. There is no fixed time limit but a chair will ask you to be
brief if many people are waiting, and repeating what the last speaker said is
the thing most likely to get you moved along.</p>
<p>You do not have to be an expert. The most useful testimony is usually the
most specific: what this bill would do to you, in your town, with a number or
a date in it.</p>

<h2>What happens to it</h2>
<p>The committee votes on a recommendation in a later meeting called an
executive session, which is public and which you may also attend. Sign-in
counts and written testimony go into the record either way.</p>
""" + SHOWS.format("""
<p>This site has parsed <b>7,250 public hearings</b> out of the House and
Senate calendars, each with the committee, the day, the time and the room.
Every bill's page shows its own hearings, and the Videos tab links the
recording at the moment the bill was taken up.</p>
<p>Bills also carry the sign-in counts: how many people registered supporting,
opposing and neutral.</p>""")


BODY_REPS = """
<p>Every resident has one senator and at least one representative, and most
have several representatives, because House districts are drawn to towns
rather than to equal population.</p>

<h2>What the district numbering means</h2>
<p>A House district is written as a county and a number &mdash; Rockingham 13,
Hillsborough 44. The number is not a rank or a size; it is just an index
within that county, and it is redrawn every ten years after the census. A
district may be one town, part of a town, or several small towns together, and
a district covering several towns elects several representatives at large
across the whole of it.</p>
<p>Senate districts are numbered 1 to 24 statewide and cut across county
lines.</p>

<h2>Floterial districts</h2>
<p>Some towns are in two House districts at once. A <b>floterial</b> district
sits on top of several ordinary ones and elects an additional member or two
across the whole of it, which is how the state gets closer to equal
representation without splitting small towns.</p>
<p>If you live in one, you have more representatives than you might expect:
the members of your own district, plus the floterial members shared with
neighbouring towns. Of New Hampshire's 203 House districts, <b>41 are
floterial</b>, and they account for 65 of the 400 seats.</p>

<h2>Getting in touch</h2>
<p>Members publish an address and, for nearly all of them, an email. There is
no staff between you and them: a message to a representative is read by that
representative. They are also, mostly, working other jobs.</p>
""" + SHOWS.format("""
<p><a href="legislators.html">Every member of both chambers</a>, with their
district, party and county, and every recorded vote they have cast.</p>
<p>Every <a href="committees.html">committee page</a> lists its members and
has a button that opens an email to all of them at once.</p>""")


BODY_SITE = """
<p>Granite Record indexes the public record: what each bill does, who
sponsored it, when it was heard, how it was voted on, and where in the
recording that happened.</p>

<h2>What a bill's page holds</h2>
<ul>
<li><b>Summary</b> &mdash; the General Court's own analysis, the current
status, and a narrative of what has happened, in order, with each action
linked to the journal or calendar that recorded it.</li>
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
<li>Where the chair can be heard opening an item, the time is that moment.</li>
<li>Where a roll call has a clock time in the official record, that is
used.</li>
<li>Otherwise the time is estimated from where the bill appears in the
recording, and it says <b>approximate</b>. It can be several minutes out.</li>
</ul>
<p>Captions are never quoted here. Automatic transcription renders "HB 1381"
as "HP 1381" often enough that a quotation would be a transcription error
wearing the clothes of a citation. The timestamp is the claim; the recording
is the evidence.</p>

<h2>Reading the shorthand</h2>
<table><tbody>
<tr><td><b>OTP</b></td><td>Ought to Pass &mdash; a motion to pass the bill</td></tr>
<tr><td><b>OTP/A</b></td><td>Ought to Pass with Amendment</td></tr>
<tr><td><b>ITL</b></td><td>Inexpedient to Legislate &mdash; a motion to kill it</td></tr>
<tr><td><b>MA / MF</b></td><td>Motion Adopted / Motion Failed</td></tr>
<tr><td><b>VV</b></td><td>Voice vote &mdash; no record of individual votes</td></tr>
<tr><td><b>DV</b></td><td>Division vote &mdash; counted, names not recorded</td></tr>
<tr><td><b>RC</b></td><td>Roll call &mdash; each member recorded by name</td></tr>
<tr><td><b>CC</b></td><td>Consent Calendar</td></tr>
<tr><td><b>OT3rdg</b></td><td>Ordered to a third reading</td></tr>
<tr><td><b>HJ / SJ</b></td><td>House or Senate Journal, and the page</td></tr>
<tr><td><b>-FN</b></td><td>Carries a fiscal note</td></tr>
<tr><td><b>-A</b></td><td>Contains an appropriation</td></tr>
<tr><td><b>-LOCAL</b></td><td>Has a local fiscal impact, on towns or schools</td></tr>
</tbody></table>

<h2>Following a bill</h2>
<p>Every bill, member and committee has an RSS feed, and there is one for
upcoming hearings. No account, no email address, nothing to leak.</p>

<h2>Telling us we are wrong</h2>
<p>This is assembled by machine from official sources and it will be wrong
somewhere. If you find something wrong &mdash; particularly on these
explanatory pages, where an error is harder to spot than a wrong date &mdash;
write to <a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a>.</p>
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

SRC_CONSTITUTION = ("The New Hampshire Constitution",
                    GC + "/constitution/constitution.html")
SRC_HOUSE_RULES = ("House Rules", GC + "/house/aboutthehouse/houserules.aspx")
SRC_SENATE_RULES = ("Senate Rules", GC + "/senate/aboutthesenate/senaterules.aspx")
SRC_RSA = ("New Hampshire Revised Statutes Annotated", RSA)
SRC_FIND_MEMBER = ("Find your legislators, by address",
                   GC + "/house/members/wml.aspx")
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


# ---------------------------------------------------------------------------
# The eleven. Order is the proposal's order and it is what the "next topic"
# link walks; the hub and the sitemap read the same list.
# ---------------------------------------------------------------------------
HOW = "How the state works"
PART = "How to take part"

TOPICS = [
    topic("general-court", "The General Court", HOW,
          "400 representatives and 24 senators, paid $100 a year. The "
          "largest state legislature in the country, and the page everything "
          "else here hangs off.",
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
          [SRC_COURTS, SRC_CONSTITUTION],
          BODY_COURTS_HOLDS),

    topic("the-constitution", "The Constitution", HOW,
          "One of the oldest still in force, and it is not amended the way "
          "statutes are: a CACR needs three fifths of both chambers and then "
          "the voters.",
          BODY_CONSTITUTION,
          [SRC_CONSTITUTION, SRC_SOS]),

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
