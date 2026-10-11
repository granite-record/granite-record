#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.1
"""
The how-to guides: their words, their sources, and what each was checked
against. Read by build_civics.py, which draws them on the Resources hub's
How-To Guides tab and at /guides/<slug>.

THE BRIEF is the person's resources plan (October 2026). Three lines of it
govern every guide here:

  * "A hand-written resources page is wrong within months, and wrong here
    means sending someone in crisis to a dead number." So a guide is data
    with a date on every claim, and a claim with no date is not published.
  * "The guides are short and procedural. Where the state explains something
    well, link to it and write one orienting sentence."
  * "Never publish eligibility math. No income thresholds, no benefit
    amounts, no deadlines stated as fact without a link to the source that
    sets them."

And the caution on position: describe how to apply, never whether a program
is good, who expanded it, or who voted for it. The bills that touch a guide
are listed by rule, from the statute chapters it names, without a word about
them.

HOW A GUIDE IS CHECKED. Every statement a guide makes is a CLAIM: the words,
and the one source that supports them. A statute claim (source "RSA 91-A:4")
is checked against the General Court's own statute table on this disk, the
text the Laws pages print. An agency claim (source an https address) is
checked against the page itself as guide_sources.py saved it, never against
memory or another site, because the state's web host refuses this project's
cloud machines and a guess is exactly what the plan forbids. A claim is
checked when its "checked" date is set, by the person or the session that
read the source, and not before.

A GUIDE IS PUBLISHED WHEN EVERY CLAIM IN IT IS CHECKED and every outside
address it links is one guide_sources.py reads, so the laptop's run checks
the link too. Until then build_civics.py leaves it out of the site and the
hub says there are no guides yet; `build_civics.py --drafts` draws it, marked
as a draft, for a person to read.

A CHECK GOES STALE. Past STALE_DAYS a guide still publishes, with a notice
above it that it may be out of date and where to check.
"""

STALE_DAYS = 180

# The statute table these claims were read in: db/_manifest.json's NH_RSA,
# which the weekly refreshes. A statute claim checked against an older table
# is checked again when the table is retaken (build_civics says so).
TABLE = "2026-09-08"


def claim(says, source, checked=None):
    """One statement and the one source that supports it."""
    return {"says": says, "source": source, "checked": checked}


def guide(slug, title, blurb, body, sources, laws, claims, see=()):
    """`body` is HTML in <h2> sections, as a Learn page's is. `sources` are
    [(label, url)] for Where This Comes From; `laws` the RSA chapters whose
    pending bills and recent laws the guide lists; `see` the site's own
    pages worth reading next [(label, path)]."""
    return {"slug": slug, "title": title, "blurb": blurb, "body": body, "sources": sources,
            "laws": laws, "claims": claims, "see": list(see)}


# ---------------------------------------------------------------------------
# GETTING A PUBLIC RECORD. Nearly all of it is the statute, which is on this
# disk; the one thing it cannot say is whether the ombudsman's office is
# taking complaints, and the plan found it was not (October 2026). The guide
# does not say which: it sends the reader to the office's own page, which is
# checked when the laptop's copy of it is.
# ---------------------------------------------------------------------------
RTK = "https://www.doj.nh.gov/resources/forms-publications/right-know"
RTK_MEMO = "https://mm.nh.gov/files/uploads/doj/remote-docs/right-to-know.pdf"
OMBUDSMAN = "https://www.sos.nh.gov/administration/office-right-know-ombudsman"

PUBLIC_RECORD = guide(
    "public-records", "Getting a Public Record",
    "How to ask a town, school district, county or state agency for its records under "
    "the Right-to-Know Law, what it may charge, and what you can do if it says no.",
    """
<h2>Who to Ask</h2>
<p>Ask the body or agency that keeps the record: the town or city office, the school
district, the county, or the state agency. The law gives every citizen the right to
inspect its governmental records during its business hours, at its office, and to copy
them, unless another statute or <a href="/laws/91-a#s5">RSA 91-A:5</a> exempts them
(<a href="/laws/91-a#s4">RSA 91-A:4, I</a>).</p>

<h2>How to Ask</h2>
<p>Describe the records well enough that they can be found: the law covers a record
&ldquo;reasonably described&rdquo; (<a href="/laws/91-a#s4">RSA 91-A:4, IV(a)</a>). Ask in
writing and keep a copy. If you later complain to the ombudsman, the complaint must
include your request and the answer you got, where there is one
(<a href="/laws/91-a#s7-b">RSA 91-A:7-b, I</a>).</p>
<p>The body does not have to create a record, or put information together in a form it
does not already keep (<a href="/laws/91-a#s4">RSA 91-A:4, VII</a>). It may suggest
narrowing the request so it can be answered faster or for less
(<a href="/laws/91-a#s4">RSA 91-A:4, IV(e)</a>).</p>

<h2>How Long It Can Take</h2>
<p>A record that is immediately available is to be made available. If it is not, within
5 business days of your request the body must do one of three things: make it available,
deny the request, or tell you in writing how long it reasonably needs, why, and an
itemized estimate of any charge (<a href="/laws/91-a#s4">RSA 91-A:4, IV(b)</a>).</p>

<h2>What It Can Charge</h2>
<p>Looking at a record is free, and so is having it delivered without copying. If the
body copies it on its own machine, it may charge the actual cost of the copy. A fee
another law sets for a copy still applies, but nothing on top of it
(<a href="/laws/91-a#s4">RSA 91-A:4, IV(d)</a>).</p>
<p>For a request covering more than 250 emails or other electronic messages, the law
allows a per-message charge, within a limit it sets, and requires it to be waived in some
cases (<a href="/laws/91-a#s4">RSA 91-A:4, VIII and IX</a>).</p>

<h2>If the Answer Is No</h2>
<p>A denial must be in writing, name the specific exemption, and briefly explain how it
applies to what was withheld (<a href="/laws/91-a#s4">RSA 91-A:4, IV(c)</a>).</p>
<p>The law gives two routes from there, and choosing one closes the other
(<a href="/laws/91-a#s7">RSA 91-A:7</a>):</p>
<ul>
<li><b>Superior court.</b> You may file a petition yourself, with or without a lawyer,
and the court is to give it high priority (<a href="/laws/91-a#s7">RSA 91-A:7, I</a>).</li>
<li><b>The right-to-know ombudsman.</b> A signed, written complaint with a fee, which the
ombudsman may waive (<a href="/laws/91-a#s7-b">RSA 91-A:7-b</a>). Before choosing this
route, check the office&rsquo;s own page for whether it is taking complaints.</li>
</ul>
<p>The Attorney General publishes a memorandum on the law, written for the public bodies
that answer requests, which is the fullest plain account of what the exemptions cover.</p>
""",
    [("Right-to-Know Law, RSA 91-A", "/laws/91-a"),
     ("Right-to-Know (New Hampshire Department of Justice)", RTK),
     ("Memorandum on the Right-to-Know Law (Attorney General)", RTK_MEMO),
     ("Office of the Right-to-Know Ombudsman", OMBUDSMAN)],
    ["91-A"],
    [claim("Every citizen may inspect and copy governmental records during business hours at "
           "the body's office, unless a statute or RSA 91-A:5 exempts them.", "RSA 91-A:4", "2026-10-11"),
     claim("A request covers a record reasonably described.", "RSA 91-A:4", "2026-10-11"),
     claim("An ombudsman complaint attaches the request and the response, if applicable.",
           "RSA 91-A:7-b", "2026-10-11"),
     claim("No duty to compile or assemble information into a form not already kept.",
           "RSA 91-A:4", "2026-10-11"),
     claim("The body may suggest a reasonable modification of the scope.", "RSA 91-A:4", "2026-10-11"),
     claim("Within 5 business days: make available, deny, or a written statement of time, reason "
           "and an itemized cost estimate.", "RSA 91-A:4", "2026-10-11"),
     claim("No charge for inspection or delivery without copying; actual cost of a copy on the "
           "body's machine; a fee set by other law applies with nothing added.", "RSA 91-A:4", "2026-10-11"),
     claim("Per-communication charge beyond 250 electronic communications, capped, with waivers.",
           "RSA 91-A:4", "2026-10-11"),
     claim("A denial is written, names the specific exemption and explains how it applies.",
           "RSA 91-A:4", "2026-10-11"),
     claim("Superior court or the ombudsman; choosing one forecloses the other.", "RSA 91-A:7", "2026-10-11"),
     claim("A petition may be filed with or without counsel and has high priority.", "RSA 91-A:7", "2026-10-11"),
     claim("The ombudsman complaint is signed, written, with a fee the ombudsman may waive.",
           "RSA 91-A:7-b", "2026-10-11"),
     claim("The Department of Justice's Right-to-Know page exists and links the memorandum.", RTK),
     claim("The Attorney General's memorandum is addressed to public bodies and explains the "
           "exemptions.", RTK_MEMO),
     claim("The ombudsman's page is the office's own, and is where to see whether it takes "
           "complaints.", OMBUDSMAN)],
    see=[("Town meeting and local government", "/learn/local-government.html")])


# ---------------------------------------------------------------------------
# REGISTERING AND VOTING. The plan's highest-value and highest-risk guide.
# What counts as proof of citizenship has changed twice since 2024 and is
# under appeal (the plan, October 2026), and the statute on this disk is the
# law as written, which a court has since ruled on: so the guide states the
# qualifications the statute sets, says plainly that what counts as proof is
# the Secretary of State's to say this year, and sends the reader there. It
# lists no document as sufficient.
# ---------------------------------------------------------------------------
SOS_REGISTER = "https://www.sos.nh.gov/elections/register-vote"
SOS_PROOF = "https://www.sos.nh.gov/proof-voter-registration-qualifications"
SOS_ABSENTEE = "https://www.sos.nh.gov/elections/voters/absentee-ballots"
SOS_LOOKUP = "https://app.sos.nh.gov/viphome"
SOS_CLERKS = "https://app.sos.nh.gov/clerkinformation"
SOS_POLLS = "https://app.sos.nh.gov/pollingplacesampleballot"

VOTING = guide(
    "registering-to-vote", "Registering to Vote and Voting",
    "Who may register in New Hampshire, where and when, what to bring, and how to vote "
    "absentee. What counts as proof has changed recently: check the Secretary of State "
    "before you go.",
    """
<h2>Check Whether You Are Registered</h2>
<p>The Secretary of State&rsquo;s voter information lookup shows whether you are on the
checklist, your party, and where you vote.</p>

<h2>Who May Register</h2>
<p>To register you must be at least 18 on the day of the next election, a United States
citizen, and domiciled in the town or city where you register
(<a href="/laws/654#s7">RSA 654:7, I</a>).</p>

<h2>Where and When</h2>
<p>You can register with your town or city clerk during the clerk&rsquo;s office hours,
up to the last meeting of the supervisors of the checklist before an election
(<a href="/laws/654#s8">RSA 654:8</a>). You can also register at your polling place on
election day and vote at that election (<a href="/laws/654#s7-a">RSA 654:7-a</a>). The
Secretary of State lists every clerk and their hours.</p>

<h2>What to Bring</h2>
<p>You will be asked for proof of citizenship, age, domicile and identity
(<a href="/laws/654#s12">RSA 654:12</a>). <b>What counts as proof, and whether a signed
affidavit can stand in for a document, has changed since 2024 and has been in court.</b>
The Secretary of State&rsquo;s page on proof of qualifications says what is accepted now;
read it before you go, and ask your clerk if you are unsure.</p>

<h2>Voting Absentee</h2>
<p>You may vote by absentee ballot if you will be away from your town on election day,
cannot vote in person because of a disability, or cannot appear in public that day because
of a religious commitment. Being unable to get to the polls at any time they are open
because of work, including caring for children or adults who need it, counts as being
away (<a href="/laws/657#s1">RSA 657:1</a>). You apply to your town or city clerk, not to
the state.</p>

<h2>Where You Vote</h2>
<p>The Secretary of State&rsquo;s lookup gives your polling place and a sample ballot.</p>
""",
    [("Register to vote (Secretary of State)", SOS_REGISTER),
     ("Proof of voter registration qualifications (Secretary of State)", SOS_PROOF),
     ("Absentee ballots (Secretary of State)", SOS_ABSENTEE),
     ("Voter information lookup (Secretary of State)", SOS_LOOKUP),
     ("Town and city clerks (Secretary of State)", SOS_CLERKS),
     ("Polling places and sample ballots (Secretary of State)", SOS_POLLS),
     ("Voters and Checklists, RSA 654", "/laws/654"),
     ("Absentee Voting, RSA 657", "/laws/657")],
    ["654", "657", "659"],
    [claim("The lookup shows registration, party and polling place.", SOS_LOOKUP),
     claim("At least 18 by the next election, a citizen, domiciled in the town or city.",
           "RSA 654:7", "2026-10-11"),
     claim("Register with the clerk in office hours, until the supervisors' last meeting before "
           "an election.", "RSA 654:8", "2026-10-11"),
     claim("Register at the polling place on election day and vote at that election.",
           "RSA 654:7-a", "2026-10-11"),
     claim("The Secretary of State lists every clerk and their hours.", SOS_CLERKS),
     claim("Proof of citizenship, age, domicile and identity is required.", "RSA 654:12", "2026-10-11"),
     claim("What counts as proof, and the affidavit, changed since 2024 and has been in court; the "
           "Secretary of State's page says what is accepted now.", SOS_PROOF),
     claim("Absence, disability, religious observance; an employment obligation, including care "
           "of children and infirm adults, counts as absence.", "RSA 657:1", "2026-10-11"),
     claim("Absentee applications go to the town or city clerk, not the state.", SOS_ABSENTEE),
     claim("The lookup gives the polling place and a sample ballot.", SOS_POLLS),
     claim("The Secretary of State's registration page is current.", SOS_REGISTER)],
    see=[("Finding your representatives", "/learn/your-representatives.html")])


# ---------------------------------------------------------------------------
# HELP WITH HEATING AND ELECTRIC BILLS. "The single least-known thing in
# this whole list": the Department of Energy runs it and five community
# action agencies deliver it. No amount, threshold or date is stated; the
# agencies' numbers go in only from the Department's own directory page,
# when its copy is read.
# ---------------------------------------------------------------------------
DOE_HELP = "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills"
DOE_FUEL = "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills/fuel-assistance-program"
DOE_CAA = "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills/community-action-agencies"

ENERGY = guide(
    "heating-and-electric-help", "Help With Heating and Electric Bills",
    "Who runs New Hampshire's fuel and electric assistance, and where you apply. You "
    "apply through the community action agency for your area.",
    """
<h2>Who Runs It</h2>
<p>Fuel assistance and the electric bill programs are run by the New Hampshire
Department of Energy, not the Department of Health and Human Services, and delivered by
community action agencies, each serving its own part of the state.</p>

<h2>Where You Apply</h2>
<p>You apply through the community action agency for the town you live in. The
Department of Energy lists the agencies and the towns each serves. If you are not sure
where to start, dial 211.</p>

<h2>What It Covers</h2>
<p>The Department of Energy&rsquo;s page on help with energy and utility bills lists the
programs and who may qualify. Amounts and income limits change every year; read them
there rather than anywhere else.</p>
""",
    [("Help with energy and utility bills (Department of Energy)", DOE_HELP),
     ("Fuel Assistance Program (Department of Energy)", DOE_FUEL),
     ("Community action agencies (Department of Energy)", DOE_CAA),
     ("Department of Energy, RSA 12-P", "/laws/12-p")],
    ["12-P"],
    [claim("The Department of Energy runs fuel assistance and the electric programs, delivered "
           "by community action agencies.", DOE_FUEL),
     claim("Each agency serves its own area; the Department lists them and their towns.", DOE_CAA),
     claim("211 is a place to start.", DOE_HELP),
     claim("The Department's page lists the programs and who may qualify.", DOE_HELP)])


GUIDES = [PUBLIC_RECORD, VOTING, ENERGY]


def outside(g):
    """The guide's outside addresses: its sources' and every claim's."""
    return sorted({u for _l, u in g["sources"] if u.startswith("http")}
                  | {c["source"] for c in g["claims"] if c["source"].startswith("http")})


def unchecked(g):
    return [c for c in g["claims"] if not c["checked"]]


def checked_on(g):
    """The oldest check on the guide: what its date says it is worth."""
    return min((c["checked"] for c in g["claims"] if c["checked"]), default=None)
