#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.5
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

WRITTEN FOR SOMEONE WITH NO CONTEXT (the person, 11 October 2026: "more of a
helpful step by step guide with diagrams that are accessible even to someone
who has no context and just looked up how to vote in New Hampshire. Sources
cited in the text where helpful as a reference like a button taking you to
the secretary of state voter registration checker page"). So a guide is:

  * AT A GLANCE: the answer in two or three sentences, before anything else;
  * A DIAGRAM of the path through it, drawn in HTML so it is read aloud as
    text, a question's answers side by side;
  * NUMBERED STEPS, each a few plain sentences, with a button to the official
    page that step needs and, under it, the section of law it rests on;
  * a NOTE, outlined, where something has changed or is in dispute.
"""

STALE_DAYS = 180

# The statute table these claims were read in: db/_manifest.json's NH_RSA,
# which the weekly refreshes. A statute claim checked against an older table
# is checked again when the table is retaken (build_civics says so).
TABLE = "2026-09-08"


import re


def claim(says, source, checked=None):
    """One statement and the one source that supports it."""
    return {"says": says, "source": source, "checked": checked}


def step(title, text, actions=(), law=(), note=""):
    """One numbered step: its words (HTML), the buttons to the official pages
    it needs [(label, url)], the sections of law it rests on ["RSA 654:7"],
    and a note to set apart, where something has changed or is disputed."""
    return {"title": title, "text": text, "actions": list(actions), "law": list(law), "note": note}


def box(text):
    """A diagram's step."""
    return ("box", text)


def ask(question, answers):
    """A diagram's question, its answers side by side: [(answer, what then)]."""
    return ("ask", question, list(answers))


def guide(slug, title, blurb, glance, flow, steps, sources, laws, claims, more="", see=()):
    """`glance` is the answer in a sentence or three (HTML); `flow` the
    diagram, a list of box() and ask(); `steps` the numbered steps; `more`
    any section after them, in <h2> sections as a Learn page's are;
    `sources` [(label, url)] for Where This Comes From; `laws` the RSA
    chapters whose pending bills and recent laws the guide lists; `see` the
    site's own pages worth reading next [(label, path)]."""
    return {"slug": slug, "title": title, "blurb": blurb, "glance": glance, "flow": list(flow),
            "steps": list(steps), "more": more, "sources": sources, "laws": laws,
            "claims": claims, "see": list(see)}


LAW_REF = re.compile(r"^RSA (\d{1,3}(?:-[A-Z]{1,2})?)(?::([0-9a-z-]+))?(.*)$")


def law_href(ref):
    """"RSA 654:7, I" -> /laws/654#s7: the section's place on the Laws page."""
    m = LAW_REF.match(ref)
    if not m:
        raise ValueError(f"not a statute reference: {ref!r}")
    return f"/laws/{m.group(1).lower()}" + (f"#s{m.group(2)}" if m.group(2) else "")


# ---------------------------------------------------------------------------
# HOW TO VOTE. The plan's highest-value and highest-risk guide. What counts
# as proof of citizenship has changed since 2024 and has been in court (the
# plan, October 2026), and the statute on this disk is the law as written,
# which a court has since ruled on: so the guide says what proof is asked
# for, says plainly that what counts is the Secretary of State's to say this
# year, and sends the reader there. It lists no document as sufficient.
# ---------------------------------------------------------------------------
SOS_REGISTER = "https://www.sos.nh.gov/elections/register-vote"
SOS_PROOF = "https://www.sos.nh.gov/proof-voter-registration-qualifications"
# The address the page ends at: /elections/voters/absentee-ballots, the one
# first listed, sends the reader here.
SOS_ABSENTEE = "https://www.sos.nh.gov/elections/absentee-ballots"
# The Secretary of State's own "Check your Voter Registration" and "Find your
# Polling Location" both lead here (the Register to Vote page's links, read
# 12 October 2026); the clerk finder is the one its Absentee Ballots page
# links for "contact information for your local clerk".
SOS_APP = "https://app.sos.nh.gov/"
SOS_CLERKS = "https://app.sos.nh.gov/clerkinformation"
SOS_HB1569 = "https://mm.nh.gov/files/uploads/sos/docs/5-29-26-secretary-of-state-issues-statement-on-hb-1569.pdf"
SOS_DEADLINES = "https://www.sos.nh.gov/elections/register-vote/registration-deadlines"
SOS_ABS_APP = ("https://www.sos.nh.gov/sites/g/files/ehbemt561/files/docs/"
               "absentee-ballot-application-state-election-eff-9.30.25-3.pdf")
SOS_FREE_VITAL = ("https://www.sos.nh.gov/sites/g/files/ehbemt561/files/inline-documents/sonh/"
                  "application-for-a-free-certified-copy-of-a-new-hampshire-vital-record-for-voter-registration.pdf")
CHECKED = "2026-10-12"   # the day the person read these pages and sent them


def table(caption, heads, rows):
    """A small table in a guide's prose, as a Learn page draws one: l-stack,
    so on a phone each row restacks with its column's name beside each cell
    (civics.layers_diagram), and explicit roles because the rows restack."""
    return ('<div class="l-tablewrap l-stack"><table class="l-table" role="table"><caption>' + caption
            + '</caption><thead role="rowgroup"><tr role="row">'
            + "".join(f'<th scope="col" role="columnheader">{h}</th>' for h in heads)
            + '</tr></thead><tbody role="rowgroup">'
            + "".join('<tr role="row">' + f'<th scope="row" role="rowheader" class="is-text">{r[0]}</th>'
                      + "".join(f'<td role="cell" data-l="{h}">{c}</td>' for h, c in zip(heads[1:], r[1:]))
                      + "</tr>" for r in rows) + "</tbody></table></div>")


VOTING = guide(
    "how-to-vote", "How to Vote in New Hampshire",
    "Checking that you are registered, registering if you are not, what to bring, and "
    "where to vote, step by step, with the Secretary of State's page for each.",
    "You vote at the polling place for the town or city ward where you live. If you are not "
    "registered there yet, you can register with your town or city clerk before the election, "
    "or at your polling place on election day. To register you need proof of your identity, "
    "your age, your citizenship and where you live, and every voter shows proof of identity "
    "to get a ballot.",
    [ask("Are you registered to vote where you live now?",
         [("Yes", "Find your polling place, then vote."),
          ("No, or not sure", "Check online. If you are not, register with your clerk before the "
                              "election, or at the polling place on election day.")]),
     box("To register, bring proof of who you are, your age, your citizenship and where you live."),
     box("On election day, show proof of identity to get your ballot, or vote absentee if you "
         "qualify.")],
    [step("Check whether you are already registered",
          "<p>The Secretary of State&rsquo;s voter information lookup tells you whether you are "
          "registered and where your polling place is.</p><p>You can vote only in the town, or "
          "the ward of a city, where you live. If you have moved to a new town or ward, you need "
          "to register at your new address; a move within the same town or ward is an address "
          "change, made on the same form.</p>",
          actions=[("Check your voter registration", SOS_APP)], law=["RSA 654:7, I"]),
     step("Make sure you can register",
          "<p>You can register if, on election day, you will be:</p><ul>"
          "<li>at least 18 years old,</li><li>a United States citizen, and</li>"
          "<li>living in the town or city ward where you are registering.</li></ul>"
          "<p>There is no minimum time you must have lived there first. &ldquo;Living&rdquo; "
          "here is what the law calls your <em>domicile</em>: the one place you call home and "
          "take part in public life from. You can have only one.</p>"
          "<p>You can register as a Democrat, a Republican, or Undeclared.</p>",
          law=["RSA 654:7, I"]),
     step("Register with your clerk, or at the polls",
          "<p>You fill in a voter registration form, and you can do it in any of these ways:</p><ul>"
          "<li><b>Before the election</b>, at your town or city clerk&rsquo;s office in office "
          "hours, or at a session of the supervisors of the checklist. Registration before an "
          "election closes 6 to 13 days before it, on a date your supervisors set, so ask your "
          "clerk for it.</li>"
          "<li><b>On election day</b>, at your polling place. You register, then vote at that "
          "election. If you are waiting in line to register when the polls close, you may still "
          "register and vote.</li>"
          "<li><b>By absentee registration</b>, if you qualify and cannot register in person.</li></ul>",
          actions=[("Find your town or city clerk", SOS_CLERKS),
                   ("Registration deadlines", SOS_DEADLINES)],
          law=["RSA 654:8", "RSA 654:7-a"]),
     step("Bring proof of four things",
          "<p>When you register you must show proof of your identity, your age, your citizenship "
          "and your domicile. Examples the Secretary of State gives:</p><ul>"
          "<li><b>Identity:</b> a photo driver&rsquo;s license from any state; a U.S. passport, "
          "passport card or armed services ID; or photo ID from a local, state or federal "
          "government.</li>"
          "<li><b>Age:</b> a driver&rsquo;s license, government photo ID, or passport or passport "
          "card.</li>"
          "<li><b>Citizenship:</b> a U.S. birth certificate, U.S. passport or passport card, or "
          "naturalization papers. Being registered to vote in New Hampshire now, or before, also "
          "proves it.</li>"
          "<li><b>Domicile:</b> a New Hampshire driver&rsquo;s license or non-driver ID, a New "
          "Hampshire vehicle registration, a federal photo ID, or a government check, benefit "
          "statement or tax document showing your address. Without one of those, there is a form "
          "to fill in together with a lease, a utility bill, or a confirmation signed by the "
          "owner, manager or tenant where you live, and a separate form for people who are "
          "homeless.</li></ul>"
          "<p>If you are missing a document, ask your clerk: with your permission, election "
          "officials can check New Hampshire voter, motor vehicle and vital records to help prove "
          "your qualifications. A certified copy of a New Hampshire birth or other vital record "
          "is free when it is only for registering to vote.</p>",
          actions=[("What counts as proof", SOS_PROOF),
                   ("Free vital record for voter registration", SOS_FREE_VITAL)],
          law=["RSA 654:12"],
          note="<b>This changed in 2026, and the courts are still involved.</b> After a court order "
               "of May 28, 2026, you may again prove <em>citizenship only</em> by signing a "
               "qualified voter affidavit, if you lack the documents; an affidavit cannot prove "
               "identity, age or domicile. A further order of October 2, 2026 lets a student ID "
               "be weighed with other evidence of identity. This is what the Secretary of State "
               "said on October 12, 2026: check the page before you go."),
     step("Vote",
          "<p>On election day, go to your polling place. Every voter must show proof of identity "
          "to get a ballot. If you have no approved photo ID, you can get one free, for voting "
          "only, from the Division of Motor Vehicles, with a voucher from your clerk or the "
          "Secretary of State.</p>"
          # Your town's polling place and clerk, from places.json (find.js).
          '<div class="yt" data-yt="vote" hidden></div>',
          actions=[("Find your polling place", SOS_APP)], law=["RSA 659:13"]),
     step("If you cannot go in person",
          "<p>You can vote by absentee ballot if you cannot vote in person because, on election "
          "day:</p><ul><li>you will be out of town;</li><li>a religious observance prevents it;</li>"
          "<li>a physical disability or illness prevents it;</li><li>work, or caring for a child "
          "or an adult, takes the whole time the polls are open;</li><li>you are confined for a "
          "misdemeanor conviction or awaiting trial;</li><li>you are in the Attorney "
          "General&rsquo;s Address Confidentiality Program or protected by a domestic violence "
          "order; or</li><li>the National Weather Service has issued a winter storm, blizzard or "
          "ice storm warning for your town and you are worried about travelling.</li></ul>"
          "<p>Send the absentee ballot application to your town or city clerk, not the state, "
          "with the proof of identity the form asks for. You can apply up to six months before "
          "the election. The deadline to ask by mail is noon the day before the election, and "
          "to ask and vote in person at the clerk&rsquo;s office, 5 p.m. the day before. A "
          "mailed ballot must reach your clerk by 5 p.m. on election day, so ask for it more "
          "than two weeks ahead. The voter information lookup shows when your clerk got your "
          "request, sent your ballot, and received it back.</p>",
          actions=[("Absentee ballots", SOS_ABSENTEE), ("Absentee ballot application", SOS_ABS_APP)],
          law=["RSA 657:1"])],
    [("Register to vote (Secretary of State)", SOS_REGISTER),
     ("Proof of voter registration qualifications (Secretary of State)", SOS_PROOF),
     ("Absentee ballots (Secretary of State)", SOS_ABSENTEE),
     ("Statement on the court's HB 1569 ruling, May 29, 2026 (Secretary of State)", SOS_HB1569),
     ("Voter information lookup (Secretary of State)", SOS_APP),
     ("Town and city clerks (Secretary of State)", SOS_CLERKS),
     ("Voters and Checklists, RSA 654", "/laws/654"),
     ("Absentee Voting, RSA 657", "/laws/657"),
     ("Election Procedure, RSA 659", "/laws/659")],
    ["654", "657", "659"],
    [claim("The lookup checks your registration and finds your polling place.", SOS_REGISTER, CHECKED),
     claim("You register where you are domiciled, so a move to a new town or ward means registering "
           "there; the form's own options are a new registration, a transfer, and a name or "
           "address update within the town or ward.", "RSA 654:7", "2026-10-11"),
     claim("At least 18 on election day, a citizen, domiciled in the town or ward; domicile is the "
           "one place from which you take part in democratic self-government, and only one.",
           "RSA 654:7", "2026-10-11"),
     claim("No minimum period of residence; register as Democrat, Republican or Undeclared.",
           SOS_REGISTER, CHECKED),
     claim("Register with the clerk in office hours, or at a supervisors' session, up to 6 to 13 "
           "days before the election; or at the polls; or absentee if unable in person.",
           SOS_REGISTER, CHECKED),
     claim("Register with the clerk in office hours, until the supervisors' last meeting before "
           "an election.", "RSA 654:8", "2026-10-11"),
     claim("Register at the polling place on election day and vote at that election; someone "
           "waiting to register when the polls close may vote if qualified.", "RSA 654:7-a", "2026-10-11"),
     claim("The clerk finder is the Secretary of State's link for local clerk contact information.",
           SOS_ABSENTEE, CHECKED),
     claim("Proof of identity, age, citizenship and domicile is asked for.", "RSA 654:12", "2026-10-11"),
     claim("The examples of proof for each qualification, the domicile forms, and that NH "
           "registration proves citizenship.", SOS_REGISTER, CHECKED),
     claim("Officials may, with permission, search voter, DMV and vital records data; a free "
           "certified NH vital record for voter registration only; a free photo ID for voting "
           "from the DMV with a voucher from the clerk or Secretary of State; every voter shows "
           "proof of identity to get a ballot.", SOS_PROOF, CHECKED),
     claim("May 28, 2026 order: the affidavit is back for citizenship only, not identity, age or "
           "domicile; proof of identity still needed for a ballot.", SOS_HB1569, CHECKED),
     claim("October 2, 2026 order on student IDs: may be considered with other evidence of "
           "identity at registration.", SOS_REGISTER, CHECKED),
     claim("A voter presents proof of identity to the ballot clerk to receive a ballot.",
           "RSA 659:13", CHECKED),
     claim("The absentee reasons, applying to the local clerk with proof of identity, six months "
           "ahead, the noon and 5 p.m. deadlines, receipt by 5 p.m. on election day, the two-week "
           "advice and tracking in the lookup.", SOS_ABSENTEE, CHECKED),
     claim("Absence, disability, religious observance; an employment obligation for all polling "
           "hours, including care of children and infirm adults, counts as absence; storm "
           "warnings.", "RSA 657:1", CHECKED)],
    more="<h2>Who Can Help</h2>"
         "<p>Your town or city clerk is the person to ask about registering and voting where you "
         "live: what to bring, the deadline, and absentee ballots. The Secretary of State calls "
         "local and state election officials voters&rsquo; trusted source of election "
         "information.</p>",
    see=[("Finding your representatives", "/learn/your-representatives.html"),
         ("How to get a birth or other vital record", "/guides/vital-records.html")])


# ---------------------------------------------------------------------------
# GETTING A PUBLIC RECORD. Nearly all of it is the statute, which is on this
# disk. The Department of Justice's page and the ombudsman's office page were
# read on 12 October 2026, and the ombudsman's page says the post is vacant and
# no filing can be acted on until it is filled, so the guide says that, with
# the date, and sends the reader to the office's own page.
# ---------------------------------------------------------------------------
RTK = "https://www.doj.nh.gov/resources/forms-publications/right-know"
RTK_MEMO = "https://mm.nh.gov/files/uploads/doj/remote-docs/right-to-know.pdf"
OMBUDSMAN = "https://www.sos.nh.gov/administration/office-right-know-ombudsman"

PUBLIC_RECORD = guide(
    "public-records", "How to Get a Public Record",
    "Asking a town, school district, county or state agency for its records under New "
    "Hampshire's Right-to-Know Law, step by step, with a request you can copy.",
    "The Right-to-Know Law gives every citizen the right to see and copy the records of New "
    "Hampshire&rsquo;s towns, cities, school districts, counties and state agencies, apart "
    "from what the law exempts. Ask the office that keeps the record. It has five business "
    "days to answer, looking is free, and copies generally cost only what they cost to make.",
    [box("Ask the office that keeps the record, in writing."),
     box("Within 5 business days, it must answer."),
     ask("What did it say?",
         [("Here are the records", "Look at them for free, or pay only what copies cost to make."),
          ("We need more time", "It must say in writing how long, why, and what it may cost."),
          ("No", "It must say why, in writing. You can take it to Superior Court, or to the "
                 "Right-to-Know ombudsman once that post is filled.")])],
    [step("Work out who keeps the record",
          "<p>Ask the public body or agency that keeps the record: the town or city office, the "
          "school district, the county, or the state agency. You have the right to look at its "
          "records during its business hours, at its office, and to copy them, unless a law makes "
          "them confidential.</p>",
          law=["RSA 91-A:4, I", "RSA 91-A:5"]),
     step("Ask, in writing",
          "<p>Describe what you want clearly enough that it can be found: the law covers a record "
          "&ldquo;reasonably described&rdquo;. A letter or an email is enough, and keep a copy: if "
          "you complain later, you will need it.</p>"
          "<p>The office does not have to create a record that does not exist, or put information "
          "together in a form it does not already keep. It may suggest narrowing your request so "
          "it can answer faster or for less.</p>"
          '<div class="g-sample"><p class="g-sample-h">A request you can copy</p>'
          "<p>To the [office]:</p><p>Under New Hampshire&rsquo;s Right-to-Know Law, RSA 91-A, I am "
          "asking to inspect [describe the records, with dates if you know them]. If you will "
          "charge for copies, please tell me the cost before making them.</p>"
          "<p>[Your name, and how to reach you]</p></div>",
          law=["RSA 91-A:4, IV(a)", "RSA 91-A:4, VII", "RSA 91-A:4, IV(e)", "RSA 91-A:7-b, I"]),
     step("Wait up to five business days",
          "<p>A record that is ready should be made available right away. If it is not, the office "
          "must, within 5 business days of your request, do one of three things:</p><ul>"
          "<li>let you see it,</li><li>refuse, or</li>"
          "<li>tell you in writing how long it needs, why, and an estimate of any cost.</li></ul>",
          law=["RSA 91-A:4, IV(b)"]),
     step("Pay only for copies",
          "<p>Looking at a record is free, and so is having it sent to you without copying. If "
          "the office makes copies on its own machine, it can charge what the copies actually "
          "cost. Where another law sets a fee for a copy, that fee applies, with nothing added.</p>"
          "<p>For a request covering more than 250 emails or other electronic messages, the law "
          "allows a charge per message within a limit it sets, and requires it to be waived in "
          "some cases.</p>",
          law=["RSA 91-A:4, IV(d)", "RSA 91-A:4, VIII"]),
     step("If the answer is no",
          "<p>A refusal must be in writing, name the specific exemption it relies on, and "
          "briefly explain how it applies. If you think it is wrong, the law gives you two "
          "routes, and choosing one closes the other:</p><ul>"
          "<li><b>Superior Court.</b> You can file a petition yourself, with or without a lawyer, "
          "and the court is to give it priority.</li>"
          "<li><b>The Right-to-Know ombudsman.</b> A signed, written complaint with a fee, which "
          "the ombudsman may waive. Since July 2025 the ombudsman&rsquo;s office has been part "
          "of the Office of State and Public Sector Labor Relations. On October 12, 2026 its page "
          "said the ombudsman post was vacant and that no filing could be acted on until it is "
          "filled, while Right-to-Know cases can still be filed in Superior Court. Check the "
          "office&rsquo;s page before you choose this route.</li></ul>",
          actions=[("The ombudsman's office", OMBUDSMAN)],
          law=["RSA 91-A:4, IV(c)", "RSA 91-A:7", "RSA 91-A:7-a", "RSA 91-A:7-b"])],
    [("Right-to-Know Law, RSA 91-A", "/laws/91-a"),
     ("Right to Know (Department of Justice)", RTK),
     ("The Attorney General's Right-to-Know memorandum (Department of Justice)", RTK_MEMO),
     ("Office of the Right to Know Ombudsman (Secretary of State)", OMBUDSMAN)],
    ["91-A"],
    [claim("Every citizen may inspect and copy governmental records during business hours at "
           "the body's office, unless a statute or RSA 91-A:5 exempts them.", "RSA 91-A:4", "2026-10-11"),
     claim("RSA 91-A:5 lists the exemptions.", "RSA 91-A:5", "2026-10-11"),
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
     claim("The ombudsman's office is administratively attached to the office of state and public "
           "sector labor relations (2025, 141:206).", "RSA 91-A:7-a", "2026-10-12"),
     claim("The office moved to the Office of State and Public Sector Labor Relations effective "
           "July 1, 2025; the post is vacant; no action on filings until it is filled; cases may "
           "still be filed in superior court.", OMBUDSMAN, CHECKED),
     claim("The Attorney General's memorandum explains RSA 91-A for citizens and officials; it is "
           "not legal advice, and people with specific questions should consult a lawyer.",
           RTK, CHECKED)],
    more="<h2>Who Can Help</h2>"
         "<p>The office that keeps the record is the first place to ask how to get it. To "
         "understand the law in more depth, the Attorney General publishes a memorandum on the "
         "Right-to-Know Law for citizens and public officials alike. It says it is not legal "
         "advice, and that anyone with a specific question should consult a lawyer.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{RTK_MEMO}" target="_blank" rel="noopener">'
         "The Attorney General&rsquo;s memorandum</a></p>",
    see=[("Town meeting and local government", "/learn/local-government.html")])


# ---------------------------------------------------------------------------
# HELP WITH HEATING AND ELECTRIC BILLS. "The single least-known thing in
# this whole list": the Department of Energy runs it and community action
# agencies deliver it. From the Department's Fuel Assistance and Community
# Action Agencies pages, read 12 October 2026. The benefit range is the
# Department's and is given with the day it was read.
# ---------------------------------------------------------------------------
DOE_FUEL = "https://www.energy.nh.gov/fap"
DOE_CAA = "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills/community-action-agencies"
NH211 = "https://www.211nh.org/"

ENERGY = guide(
    "heating-and-electric-help", "How to Get Help With Heating and Electric Bills",
    "Where to apply for fuel assistance, help with electric bills and weatherization in New "
    "Hampshire, step by step, and what to do in a no-heat emergency.",
    "New Hampshire&rsquo;s Fuel Assistance Program is the state&rsquo;s part of the federal "
    "Low Income Home Energy Assistance Program. The Department of Energy runs it, and the "
    "community action agency for your area takes applications, for fuel assistance, the "
    "electric bill discount and weatherization alike. Fuel assistance is a grant you do not pay "
    "back. In a no-heat emergency, call your community action agency.",
    [box("Find the community action agency for your county."),
     box("Call it to set up an appointment and apply. You can apply for all three programs at once."),
     box("No heat right now? Call the agency and say it is an emergency.")],
    [step("Find your community action agency",
          "<p>Five agencies cover the state, each its own counties. The Department of Energy "
          "lists every office and its number.</p>"
          + table("Community action agencies by county (Department of Energy, October 12, 2026)",
                  ["Counties", "Agency", "Phone"],
                  [["Belknap and Merrimack", "Community Action Program Belknap-Merrimack Counties",
                    "(603) 223-0043"],
                   ["Hillsborough and Rockingham",
                    "Community Action Partnership of Hillsborough and Rockingham Counties",
                    "Several offices; see the Department&rsquo;s list"],
                   ["Cheshire and Sullivan", "Southwestern Community Services",
                    "Keene (603) 352-7512, Claremont (603) 542-9528"],
                   ["Strafford", "Community Action Partnership of Strafford County",
                    "(603) 435-2500, ext. 4001"],
                   ["Carroll, Coos and Grafton", "Tri-County Community Action Program",
                    "Carroll (603) 323-7400, Coos (603) 752-3248, Grafton (603) 968-3560"]]),
          actions=[("Every agency and office", DOE_CAA)]),
     step("Apply through the agency",
          "<p>Call to set up an appointment or to ask how to apply. You can apply for fuel "
          "assistance, electric assistance and weatherization at the same time, and you do not "
          "need one to get another. Bring everything the agency asks for and keep your "
          "appointment.</p><p>If you cannot get to an office, ask about an interview at home or "
          "by phone, or a mail-in application.</p>",
          actions=[("Fuel Assistance Program", DOE_FUEL)]),
     step("Know what each program does",
          "<ul><li><b>Fuel assistance</b> helps with heating costs as funds become available. "
          "It is a grant, not a loan, and it is not counted as income when you apply for other "
          "help. The amount depends on household income, energy costs, the local climate and "
          "your kind of housing. The Department&rsquo;s page gives the current range.</li>"
          "<li><b>Electric assistance</b> is a discount on your monthly electric bill if your "
          "income qualifies.</li>"
          "<li><b>Weatherization</b> helps lower-income households make their homes cheaper to "
          "heat.</li></ul>",
          actions=[("Fuel assistance: amounts and income limits", DOE_FUEL)]),
     step("In a heating emergency",
          "<p>Call your community action agency. Fuel assistance can arrange an emergency "
          "delivery of fuel, delay a shut-off notice, or point you to other help.</p>"
          "<p>If you heat with oil, kerosene or propane, the Department advises calling your "
          "supplier at least ten days before you need a delivery.</p>")],
    [("Fuel Assistance Program (Department of Energy)", DOE_FUEL),
     ("Community action agencies (Department of Energy)", DOE_CAA),
     ("Department of Energy, RSA 12-P", "/laws/12-p")],
    ["12-P"],
    [claim("FAP is New Hampshire's arm of federal LIHEAP; the Department administers it and "
           "community action agencies do the work; benefits are a grant, not repaid, not counted "
           "as income for other programs; $100 to $2,177 depending on income, energy costs, "
           "heating degree days and housing type.", DOE_FUEL, CHECKED),
     claim("To apply, contact your local community action agency to set up an appointment.",
           DOE_FUEL, CHECKED),
     claim("Emergency: emergency fuel delivery, delaying a shut-off notice, or referral.",
           DOE_FUEL, CHECKED),
     claim("Electric assistance is a monthly bill discount for income-eligible customers; "
           "weatherization helps low-income households with conservation improvements.",
           DOE_FUEL, CHECKED),
     claim("Call your fuel vendor at least ten days ahead.", DOE_FUEL, CHECKED),
     claim("The agencies, the counties each serves and their numbers; apply for all three "
           "programs at once, none required for another; homebound applicants may ask for a home "
           "or phone interview or mail-in application; no-heat emergencies go to the local agency.",
           DOE_CAA, CHECKED),
     claim("211, Neighbor Helping Neighbor (Eversource, Liberty and Unitil customers), Project Care "
           "(NHEC customers) and NH Adult and Aging Care, 1-866-634-9412.", DOE_CAA, CHECKED)],
    more="<h2>Who Can Help</h2>"
         "<p>Your community action agency is where to apply and where to ask about your "
         "household. The Department of Energy also lists these:</p><ul>"
         "<li><b>211 New Hampshire:</b> dial 211, or 1-866-444-4211, for help finding other "
         "assistance.</li>"
         "<li><b>NH Adult and Aging Care:</b> 1-866-634-9412.</li>"
         "<li><b>Neighbor Helping Neighbor</b>, for customers of Eversource, Liberty and Unitil, "
         "and <b>Project Care</b>, for New Hampshire Electric Co-op customers.</li></ul>"
         f'<p class="g-acts"><a class="g-btn" href="{NH211}" target="_blank" rel="noopener">211 '
         "New Hampshire</a></p>")


# ---------------------------------------------------------------------------
# A BIRTH, DEATH, MARRIAGE OR DIVORCE CERTIFICATE. From the Secretary of
# State's Vital Records and Request for Certificates pages and the
# application itself (rev. 7/2025), read 12 October 2026, and RSA 5-C.
# ---------------------------------------------------------------------------
DVRA = "https://www.sos.nh.gov/vital-records-0"
DVRA_REQUEST = "https://www.sos.nh.gov/vital-records-0/purchasing-correcting-vital-records/request-certificates"
DVRA_APP = ("https://www.sos.nh.gov/sites/g/files/ehbemt561/files/inline-documents/sonh/"
            "vital-record-application-2.pdf")
DVRA_NO_ID = ("https://www.sos.nh.gov/sites/g/files/ehbemt561/files/inline-documents/sonh/"
              "documentary-evidence-required.pdf")
DVRA_CONTACT = "https://www.sos.nh.gov/vital-records-0/vital-records-contact-information"

VITAL = guide(
    "vital-records", "How to Get a Birth, Death, Marriage or Divorce Certificate",
    "Getting a certified copy of a New Hampshire birth, death, marriage, divorce or civil union "
    "record from your town or city clerk or the state, step by step: who may ask, what to "
    "bring and what it costs.",
    "Any of New Hampshire&rsquo;s 234 town and city clerks, or the state&rsquo;s Division of "
    "Vital Records Administration in Concord, can issue a certified copy. You fill in an "
    "application, show photo identification, and pay a search fee that includes one copy, with "
    "a smaller fee for each extra copy made at the same time. Only the person named, close "
    "family and a few others may get a recent record.",
    [ask("Is the record yours, or a close family member's?",
         [("Yes", "Apply with your photo ID."),
          ("No", "You may still qualify, with a letter showing why you need it.")]),
     box("Apply at your town or city clerk&rsquo;s office, or by mail to the state."),
     box("Pay the search fee, which includes one copy.")],
    [step("Check that you may get the record",
          "<p>Birth records from before 1901, and death, marriage and divorce records from before "
          "1948, are public. A newer record is issued only to someone with a <em>direct and "
          "tangible interest</em> in it:</p><ul><li>the person it is about;</li><li>a member of "
          "their immediate family;</li><li>their legal guardian or legal representative;</li>"
          "<li>someone who needs it to establish or protect a personal or property right;</li>"
          "<li>the news media, for information of a public nature;</li><li>someone the immediate "
          "family has authorized to do genealogical research; and</li><li>a former spouse, for "
          "the divorce record.</li></ul><p>If you are not immediate family, include a letter "
          "saying which record you need, why, and any evidence for it. The clerk or the state "
          "registrar decides, and a refusal can be appealed.</p>",
          law=["RSA 5-C:102"]),
     step("Fill in the application",
          "<p>Fill in the section for the kind of record you want, and the applicant section "
          "with your name, address, reason and relationship, and sign it. For a death record you "
          "choose whether it shows the cause and manner of death, and whether the Social "
          "Security number is suppressed. A false statement on the application is a "
          "felony.</p>",
          actions=[("The application", DVRA_APP)], law=["RSA 5-C:14"]),
     step("Apply in person, or by mail",
          "<p><b>In person:</b> take the application and your photo ID to your town or city "
          "clerk.</p><p><b>By mail:</b> send it to the Division of Vital Records Administration, "
          "9 Ratification Way, Concord, NH 03301-2455, with:</p><ul>"
          "<li>a check or money order in U.S. funds, payable to &ldquo;Treasurer-State of New "
          "Hampshire&rdquo;;</li><li>a legible photocopy of your photo ID;</li>"
          "<li>proof of your mailing address, such as a utility bill or lease, if it is not on "
          "your ID; and</li><li>a stamped envelope addressed to you, for faster return.</li></ul>"
          "<p>A driver&rsquo;s license, passport or other picture ID is accepted. Without one, "
          "there is a form listing the other documents that will do.</p>",
          actions=[("Request a certificate", DVRA_REQUEST), ("If you have no photo ID", DVRA_NO_ID)]),
     step("Pay the fee",
          "<p>The search fee includes one copy, and each further copy of the same record issued "
          "at the same time costs less. The law sets both, and the Secretary of State&rsquo;s "
          "page gives the current amounts. The search fee is paid whether or not the record is "
          "found, and a card payment may cost extra.</p>",
          actions=[("Current fees", DVRA_REQUEST)], law=["RSA 5-C:10"])],
    [("Vital Records (Secretary of State)", DVRA),
     ("Request for Certificates (Secretary of State)", DVRA_REQUEST),
     ("Application for a certified copy of a vital record (Secretary of State)", DVRA_APP),
     ("Vital Records Administration, RSA 5-C", "/laws/5-c")],
    ["5-C"],
    [claim("DVRA issues certified copies of birth, death, marriage, divorce and civil union "
           "certificates, as do all 234 local clerks, to those with a direct and tangible "
           "interest; apply to DVRA or at the local clerk; $15 search fee, payable whether or not "
           "found, plus card costs; $10 for additional copies at the same time; positive "
           "identification required, or the documentary evidence form.", DVRA_REQUEST, CHECKED),
     claim("The DVRA mailing address.", DVRA_REQUEST, CHECKED),
     claim("The application's sections, the death record options, and the mailing checklist: "
           "check or money order payable to Treasurer-State of New Hampshire, ID photocopy, proof "
           "of address, return envelope.", DVRA_APP, CHECKED),
     claim("Records public before 1901 (births) and 1948 (others); who has a direct and tangible "
           "interest; a letter for a claim, reviewed by the registrar or clerk, with appeal.",
           "RSA 5-C:102", CHECKED),
     claim("$15 search including the copy, $10 each subsequent copy.", "RSA 5-C:10", CHECKED),
     claim("A false statement in an application for a certified copy is a class B felony.",
           "RSA 5-C:14", CHECKED)],
    more="<h2>Who Can Help</h2>"
         "<p>Your town or city clerk issues certified copies, and is the nearest place to ask. "
         "The Division of Vital Records Administration lists how "
         "to reach it on its contact page. A certified copy needed only to register to vote is "
         "free: see How to Vote.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_CLERKS}" target="_blank" rel="noopener">'
         "Find your town or city clerk</a> "
         f'<a class="g-btn" href="{DVRA_CONTACT}" target="_blank" rel="noopener">Contact Vital '
         "Records</a></p>",
    see=[("How to vote in New Hampshire", "/guides/how-to-vote.html")])


# ---------------------------------------------------------------------------
# APPEALING A PROPERTY TAX ASSESSMENT. From the Board of Tax and Land Appeals'
# Property Tax page and its abatement application (rev. June 2023), the
# Department of Revenue Administration's abatement page, read 12 October
# 2026, and RSA 76.
# ---------------------------------------------------------------------------
BTLA = "https://www.btla.nh.gov/jurisdiction/property-tax"
BTLA_ABATE = "https://www.btla.nh.gov/sites/g/files/ehbemt601/files/inline-documents/sonh/abatement.pdf"
BTLA_APPEAL = "https://www.btla.nh.gov/sites/g/files/ehbemt601/files/inline-documents/sonh/appeals.pdf"
BTLA_FAQ = ("https://www.btla.nh.gov/sites/g/files/ehbemt601/files/inline-documents/sonh/"
            "commonly-asked-questions-pt.pdf")
DRA_ABATE = ("https://www.revenue.nh.gov/about-dra/municipal-and-property-division/property-bureau/"
             "property-tax-abatement-appeal-process")

ABATEMENT = guide(
    "property-tax-abatement", "How to Appeal Your Property Tax Assessment",
    "Asking your town or city for a property tax abatement, and appealing to the Board of Tax "
    "and Land Appeals or the Superior Court if it says no, step by step, with every deadline.",
    "If you think your property is assessed too high, or you cannot pay because of poverty, ask "
    "your town or city for an <em>abatement</em> by March 1 after your final tax bill. It has "
    "until July 1 to decide, and silence counts as no. Then you can appeal to the Board of Tax "
    "and Land Appeals or the Superior Court, one or the other, by September 1. Keep paying your "
    "taxes meanwhile: if you win, you are refunded with interest.",
    [box("Apply to your town or city by March 1 after the final tax bill."),
     box("The town decides by July 1. No answer counts as a denial."),
     ask("Still disagree?",
         [("Appeal to the Board of Tax and Land Appeals", "With a filing fee, by September 1."),
          ("Or to the Superior Court", "By September 1. One or the other, not both.")])],
    [step("Know your deadlines",
          "<p>Every deadline counts from the <em>notice of tax</em>: the date your town mailed the "
          "final tax bill. If your town bills twice a year, that is the second bill, and you apply "
          "after it, not before.</p>"
          + table("Property tax abatement and appeal deadlines (Board of Tax and Land Appeals)",
                  ["Step", "Final bill on or before December 31", "Final bill after December 31"],
                  [["Apply to your town", "By March 1", "Within 2 months of the bill"],
                   ["Town decides", "By July 1", "Within 6 months"],
                   ["Appeal", "By September 1, and not before the town decides or July 1",
                    "Within 8 months, and not before the town decides or 6 months"]]),
          law=["RSA 76:1-a", "RSA 76:16-d, II"]),
     step("Build your case",
          "<p>A town may abate a tax &ldquo;for good cause shown&rdquo;. That usually means one "
          "of these:</p><ul><li><b>An error</b> in how your property is described or measured.</li>"
          "<li><b>A disproportionate assessment.</b> You show what the property was worth on "
          "April 1 of the tax year, with an appraisal or sales of comparable properties, and "
          "that your <em>equalized assessment</em> is higher. To get it, divide your assessment "
          "by your town&rsquo;s equalization ratio.</li>"
          "<li><b>Poverty and inability to pay</b>, explained in detail, including why an "
          "abatement fits better than other help.</li></ul>"
          "<p>&ldquo;Taxes too high&rdquo; is not enough: the application asks for specifics. "
          "List every property you own in the town, not only the one you are appealing.</p>",
          law=["RSA 76:16"]),
     step("File the application with your town",
          "<p>Use the Board&rsquo;s abatement application, sign it, and keep a copy. It is filed "
          "on the day you hand it in, the day it is postmarked, or the day an overnight carrier "
          "receipts it. Your town may charge for the form.</p>",
          actions=[("The abatement application", BTLA_ABATE)], law=["RSA 76:16, I(b)"]),
     step("Wait for the decision",
          "<p>The town must grant or deny in writing by July 1, or within 6 months where the "
          "final bill went out after December 31. Not answering counts as a denial. A written "
          "decision tells you how to appeal and by when.</p>",
          law=["RSA 76:16, II"]),
     step("Appeal, if you still disagree",
          "<p>You can appeal to the <b>Board of Tax and Land Appeals</b> or to the <b>Superior "
          "Court</b>, but not both. For the Board, fill in its appeal form and mail it or hand it "
          "in, with the filing fee its page states, by check or money order payable to "
          "&ldquo;Treasurer, State of NH&rdquo;, to the Board of Tax and Land Appeals, 107 Pleasant Street, Johnson Hall, "
          "Concord, NH 03301. It does not accept appeals filed electronically. Either way, the "
          "decision can then be appealed to the Supreme Court.</p>",
          actions=[("The Board's property tax page", BTLA), ("The Board's appeal form", BTLA_APPEAL),
                   ("Commonly asked questions", BTLA_FAQ)],
          law=["RSA 76:16-a", "RSA 76:17"])],
    [("Property Tax (Board of Tax and Land Appeals)", BTLA),
     ("Taxpayer's RSA 76:16 abatement application (Board of Tax and Land Appeals)", BTLA_ABATE),
     ("Property tax abatement and appeal process (Department of Revenue Administration)", DRA_ABATE),
     ("Apportionment, Assessment and Abatement of Taxes, RSA 76", "/laws/76")],
    ["76"],
    [claim("Abatement for good cause; the four-step process; the deadline chart for bills on or "
           "before and after December 31; notice of tax is the mailing of the final bill; BTLA or "
           "superior court, not both, then the supreme court; the $65 fee by check or money "
           "order to Treasurer, State of NH; the address; no electronic filing; damaged "
           "buildings within 60 days or by March 1.", BTLA, CHECKED),
     claim("Taxes are paid as assessed and refunded with interest; filing date by hand, postmark "
           "or overnight receipt; semiannual billing applies after the final bill; good cause "
           "means an error, disproportionality or poverty and inability to pay; equalized "
           "assessment is assessment divided by the ratio; specificity; list other properties; "
           "the applicant signs.", BTLA_ABATE, CHECKED),
     claim("An abatement refunds taxes for description errors, damaged buildings or value; a "
           "denial is appealed to the BTLA or superior court.", DRA_ABATE, CHECKED),
     claim("Apply by March 1 after notice of tax; the municipality may charge for the form; "
           "decision by July 1, failure to respond is denial; written decisions give the appeal "
           "procedure and deadline.", "RSA 76:16", CHECKED),
     claim("BTLA appeal on payment of a $65 fee by September 1.", "RSA 76:16-a", CHECKED),
     claim("Superior court in lieu of the BTLA, by September 1.", "RSA 76:17", CHECKED),
     claim("2, 6 and 8 months where notice of tax is after December 31.", "RSA 76:16-d", CHECKED),
     claim("Date of the final tax bill and date of notice of tax defined.", "RSA 76:1-a", CHECKED),
     claim("Damaged buildings: apply within 60 days of the event or by March 1, whichever is "
           "later; appeal as under 76:16-a or 76:17.", "RSA 76:21", CHECKED)],
    more="<h2>If a Fire or Disaster Damaged Your Building</h2>"
         "<p>When a fire you did not cause, or a natural disaster, leaves a building unusable "
         "during the tax year, its assessment is prorated for the days it could be used. Apply "
         "in writing to your town within 60 days of the damage or by March 1, whichever is later. "
         'Appeals follow the same routes and deadlines (<a href="/laws/76#s21">RSA 76:21</a>).</p>'
         "<h2>Who Can Help</h2>"
         "<p>Your town or city&rsquo;s assessing officials are who you apply to for an "
         "abatement. For questions about appealing, the Board of Tax and Land Appeals asks you to "
         "read its commonly asked questions or call its office at (603) 271-2578.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{BTLA}" target="_blank" rel="noopener">The '
         "Board of Tax and Land Appeals</a></p>",
    see=[("Help paying property tax on a low or moderate income", "/guides/property-tax-relief.html")])


# ---------------------------------------------------------------------------
# LOW AND MODERATE INCOME HOMEOWNERS PROPERTY TAX RELIEF. From the Department
# of Revenue Administration's page, read 12 October 2026, and RSA 198:56-61,
# which says HOUSEHOLD income where the page says the claimant's: the guide
# follows the statute and says what household income is.
# ---------------------------------------------------------------------------
DRA_LMI = ("https://www.revenue.nh.gov/resource-center/taxpayer-assistance/"
           "low-and-moderate-income-homeowners-property-tax-relief")
DRA_GTC = "https://gtc.revenue.nh.gov/TAP/_/"
DRA_FORMS = "https://www.revenue.nh.gov/nhdra-home/resource-center/current-year-forms-instructions"
DRA_LMI_FAQ = ("https://www.revenue.nh.gov/resource-center/frequently-asked-questions/"
               "low-moderate-property-tax-relief")

LMI = guide(
    "property-tax-relief", "How to Get Property Tax Relief on a Low or Moderate Income",
    "New Hampshire's Low and Moderate Income Homeowners Property Tax Relief: who qualifies, "
    "how much it can be, and how to apply between May 1 and June 30.",
    "If you own and live in your home and your household income is under a limit the law sets, "
    "the state refunds some or all of the State Education Property Tax on it. You apply to the "
    "Department of Revenue Administration between May 1 and June 30, online or on Form DP-8.",
    [ask("Do you own and live in your home, and is your household income under the limit?",
         [("Yes", "Apply between May 1 and June 30."),
          ("Not sure", "Read who qualifies below, or call the Department.")]),
     box("Apply online at Granite Tax Connect, or on Form DP-8."),
     box("The Department has 120 days to process a complete claim.")],
    [step("Check that you qualify",
          "<p>You qualify if all of these are true:</p><ul>"
          "<li>you own a home, or an interest in one, that is subject to the State Education "
          "Property Tax;</li><li>you lived in it on April 1 of the year you are claiming for; "
          "and</li><li>your household income is at or under the limit for a single person, or "
          "the higher limit for a married person or head of household. The Department&rsquo;s "
          "page gives both.</li></ul>"
          "<p><b>Household income</b> is the federal adjusted gross income of you and of every "
          "other adult who lives in the home.</p>",
          actions=[("Who qualifies, and the limits", DRA_LMI)],
          law=["RSA 198:56", "RSA 198:57, III"]),
     step("Apply between May 1 and June 30",
          "<p>Claims are accepted only in that window. Apply online through the Department&rsquo;s "
          "Granite Tax Connect portal, using &ldquo;Apply for Property Tax Relief&rdquo;, or on "
          "Form DP-8 from the Department&rsquo;s forms page.</p>",
          actions=[("Granite Tax Connect", DRA_GTC), ("Forms, including DP-8", DRA_FORMS)]),
     step("Wait for the decision",
          "<p>The Department has 120 days from receiving your complete application. If your "
          "claim is turned down in whole or in part, it must tell you within 90 days of receiving "
          "the claim and its documents.</p>",
          law=["RSA 198:61"]),
     step("If you are turned down",
          "<p>You can appeal in writing to the Board of Tax and Land Appeals within 30 days of "
          "the notice.</p>",
          law=["RSA 198:60"])],
    [("Low and Moderate Income Homeowners Property Tax Relief (Department of Revenue Administration)",
      DRA_LMI),
     ("Frequently asked questions (Department of Revenue Administration)", DRA_LMI_FAQ),
     ("School Money, RSA 198", "/laws/198")],
    ["198"],
    [claim("Eligibility as the page gives it; the May 1 to June 30 filing period; Granite Tax "
           "Connect or Form DP-8; 120 days for processing; the phone line (603) 230-5920.",
           DRA_LMI, CHECKED),
     claim("Household income is the AGI of the claimant and any adult member of the household "
           "living in the homestead.", "RSA 198:56", CHECKED),
     claim("Owns a homestead subject to the education tax, resided there April 1, household "
           "income limits $37,000 and $47,000; the relief formula and its percentages.",
           "RSA 198:57", CHECKED),
     claim("Appeal to the BTLA in writing within 30 days.", "RSA 198:60", CHECKED),
     claim("Certification within 120 days; notice of rejection within 90 days.", "RSA 198:61", CHECKED),
     claim("A fraudulent claim is a misdemeanor; audits within 3 years.", "RSA 198:59", CHECKED)],
    more="<h2>How Much It Can Be</h2>"
         "<p>The relief is part or all of the State Education Property Tax on your home, on a "
         "sliding scale by household income that the law sets out "
         '(<a href="/laws/198#s57">RSA 198:57</a>). The Department works it out from your '
         "claim. A false claim is a crime, and the Department may audit a claim within three "
         'years of granting it (<a href="/laws/198#s59">RSA 198:59</a>).</p>'
         "<h2>Who Can Help</h2>"
         "<p>The Department of Revenue Administration answers questions about this program at "
         "(603) 230-5920, and keeps a page of frequently asked questions.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{DRA_LMI_FAQ}" target="_blank" rel="noopener">'
         "Frequently asked questions</a></p>",
    see=[("How to appeal your property tax assessment", "/guides/property-tax-abatement.html")])


GUIDES = [VOTING, PUBLIC_RECORD, ENERGY, VITAL, ABATEMENT, LMI]


def text(g):
    """Every word the guide prints, with each law reference as the link it
    becomes: what the checks read."""
    bits = [g["glance"], g["more"]]
    for node in g["flow"]:
        bits.append(node[1])
        if node[0] == "ask":
            bits += [f"{a} {b}" for a, b in node[2]]
    for s_ in g["steps"]:
        bits += [s_["title"], s_["text"], s_["note"]] + [label for label, _u in s_["actions"]]
        bits += [f'href="{law_href(r)}"' for r in s_["law"]]
    return " ".join(bits)


def outside(g):
    """The guide's outside addresses: its sources', its buttons' and every claim's."""
    return sorted({u for _l, u in g["sources"] if u.startswith("http")}
                  | {u for s_ in g["steps"] for _l, u in s_["actions"] if u.startswith("http")}
                  | {c["source"] for c in g["claims"] if c["source"].startswith("http")})


def unchecked(g):
    return [c for c in g["claims"] if not c["checked"]]


def checked_on(g):
    """The oldest check on the guide: what its date says it is worth."""
    return min((c["checked"] for c in g["claims"] if c["checked"]), default=None)
