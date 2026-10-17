#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.10
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


# A FIGURE THE LAW SETS (the person, 12 October 2026: "Allow figures set by
# statute and have a way to check to make sure the costs are up to date").
# A guide may print a dollar amount or a percentage only as one of these: the
# figure as printed, the section that sets it, and the words of that section
# that state it. build_civics.guide_ready finds those words in the statute
# table every build -- the weekly takes the table fresh from the General
# Court's database -- and holds the guide back, naming the figure, the day
# the law stops saying them. A figure from an agency's page, which no table
# checks, is still never printed: the guide links the page.
FIGURE = re.compile(r"\$\s?\d+(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?\s?%")


def fig(text, ref, says):
    """`text` as the guide prints it ("$15"), the section that sets it
    ("RSA 5-C:10") and words of that section that state it ("the sum of $15")."""
    return {"text": text, "ref": ref, "says": says}


def unbacked(g):
    """The dollar and percentage figures the guide prints that no fig() of
    it declares."""
    declared = {f["text"] for f in g.get("figures") or []}
    return sorted({m.group(0).replace(" ", "") for m in FIGURE.finditer(text(g))} - declared)


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


# WHERE TO GET HELP FROM A PERSON (the person, 12 October 2026: "link to
# official benefits assistance programs as well so that folks can speak
# directly to experts if they need further assistance past the guides or
# referrals for legal services"). Each entry is a line for a guide's Who Can
# Help, its buttons, and the claims that check it, from pages the person sent.
# Legal aid and the Bar's referral service are not state agencies; the person
# chose them (guide_sources.OTHER).
NHEASY = "https://nheasy.nh.gov/#/"
ADRC = "https://nhcare-c.org/aging-and-disability-resource-center/"
NHLA = "https://www.nhla.org"
LEGAL_AID = "https://www.603legalaid.org/self-help-articles/"
LRS = "https://www.nhbar.org/lawyer-referral-service/"
HELP_CHECKED = "2026-10-12"
HELP = {
    "nheasy": (
        "<li><b>NH Easy</b>, the Department of Health and Human Services&rsquo; benefits site: "
        "apply for cash, medical, SNAP (food) and child care assistance, Medicare beneficiary "
        "and long-term care assistance, or check first whether you might qualify. To speak to "
        "someone, call 1-844-ASK-DHHS (1-844-275-3447).</li>",
        [("NH Easy", NHEASY)],
        [("NH Easy: apply for cash, medical, SNAP, child care, Medicare beneficiary and long term "
          "care assistance; Do I Qualify?; customer service 1-844-ASK-DHHS (1-844-275-3447).", NHEASY)]),
    "adrc": (
        "<li><b>Aging and Disability Resource Centers</b> (formerly ServiceLink), a Department of "
        "Health and Human Services program with local resource centers: free counseling for "
        "older adults, adults with disabilities and caregivers, on benefits, applications, "
        "housing, Medicare and Medicaid, with no eligibility requirement. Call 1-866-634-9412, "
        "weekdays 8:30 a.m. to 4:30 p.m.</li>",
        [],
        [("ADRC, formerly ServiceLink, a DHHS program of locally accessible resource centers; "
          "options counseling on benefits, applications, housing, Medicare and Medicaid; no fee "
          "or eligibility requirement; 1-866-634-9412, Monday to Friday 8:30 to 4:30.", ADRC)]),
    "legal_aid": (
        "<li><b>Free civil legal aid.</b> New Hampshire Legal Assistance helps people with low "
        "income and limited assets, and adults 60 and over, mainly with housing (eviction, "
        "foreclosure and property tax deeding), domestic violence and family law, and public "
        "benefits. Apply through 603 Legal Aid, online or at 1-800-639-5290; it also publishes "
        "self-help articles.</li>",
        [("603 Legal Aid", LEGAL_AID)],
        [("NHLA: free civil legal aid, mainly housing including property tax deeding, domestic "
          "violence and family law, public benefits; low income and limited assets, and 60 and "
          "over; apply through 603 Legal Aid online or 1 (800) 639-5290.", NHLA),
         ("603 Legal Aid publishes self-help articles, benefits among them.", LEGAL_AID)]),
    "lawyer": (
        "<li><b>The New Hampshire Bar Association&rsquo;s Lawyer Referral Service</b> refers you "
        "to a lawyer who handles your kind of problem, for an administrative fee. Call "
        "603-229-0002, weekdays 9 a.m. to 3:30 p.m., or ask online.</li>",
        [("Lawyer Referral Service", LRS)],
        [("NHBA Lawyer Referral Service: 603-229-0002, Monday to Friday 9 to 3:30, an "
          "administrative fee, referral by phone or online.", LRS)]),
}


def helps(*keys):
    """The Who Can Help list for these entries, with their buttons."""
    acts = [a for k in keys for a in HELP[k][1]]
    return ('<ul class="g-help">' + "".join(HELP[k][0] for k in keys) + "</ul>"
            + ('<p class="g-acts">' + " ".join(
                f'<a class="g-btn" href="{u}" target="_blank" rel="noopener">{label}</a>'
                for label, u in acts) + "</p>" if acts else ""))


def help_claims(*keys):
    return [claim(says, src, HELP_CHECKED) for k in keys for says, src in HELP[k][2]]


def guide(slug, title, blurb, glance, flow, steps, sources, laws, claims, more="", see=(),
          figures=()):
    """`glance` is the answer in a sentence or three (HTML); `flow` the
    diagram, a list of box() and ask(); `steps` the numbered steps; `more`
    any section after them, in <h2> sections as a Learn page's are;
    `sources` [(label, url)] for Where This Comes From; `laws` the RSA
    chapters whose pending bills and recent laws the guide lists; `see` the
    site's own pages worth reading next [(label, path)]."""
    return {"slug": slug, "title": title, "blurb": blurb, "glance": glance, "flow": list(flow),
            "steps": list(steps), "more": more, "sources": sources, "laws": laws,
            "claims": claims, "see": list(see), "figures": list(figures)}


LAW_REF = re.compile(r"^RSA (\d{1,3}(?:-[A-Z]{1,2})?)(?::([0-9a-z-]+))?(.*)$")


def law_href(ref):
    """"RSA 654:7, I" -> /laws/654#s7: the section's place on the Laws page."""
    m = LAW_REF.match(ref)
    if not m:
        raise ValueError(f"not a statute reference: {ref!r}")
    # The chapter's address as build_rsa writes it, RSA 404's with its slash
    # (build_rsa.chapter_path, the sitemap audit, 16 October 2026). Imported
    # here rather than above, so the guides' words load with nothing else.
    import build_rsa
    return build_rsa.chapter_path(m.group(1), m.group(2) or "")


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
          "hours, or at a session of the supervisors of the checklist (the elected board "
          "that keeps your town's list of voters). Registration before an "
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
               "of May 28, 2026, if you lack the documents to prove your citizenship you may again "
               "sign a qualified voter affidavit instead. The affidavit covers citizenship and "
               "nothing else: you still need proof of identity, age and domicile. A further "
               "order of October 2, 2026 lets election officials consider a student ID, together "
               "with other evidence, as proof of identity when you register. This is what the Secretary of State "
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
          "ice storm warning for your town and you are worried about traveling.</li></ul>"
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
          "&ldquo;reasonably described&rdquo;. A letter or an email is enough. Keep a copy: a "
          "complaint to the ombudsman includes the request.</p>"
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
          "briefly explain how it applies. To have a refusal reviewed, the law provides two "
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
           RTK, CHECKED)] + help_claims("lawyer"),
    more="<h2>Who Can Help</h2>"
         "<p>The office that keeps the record is the first place to ask how to get it. To "
         "understand the law in more depth, the Attorney General publishes a memorandum on the "
         "Right-to-Know Law for citizens and public officials alike. It says it is not legal "
         "advice, and that anyone with a specific question should consult a lawyer.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{RTK_MEMO}" target="_blank" rel="noopener">'
         "The Attorney General&rsquo;s memorandum</a></p>"
         + helps("lawyer"),
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
           "(NHEC customers) and NH Adult and Aging Care, 1-866-634-9412.", DOE_CAA, CHECKED)]
    + help_claims("nheasy", "adrc"),
    more="<h2>Who Can Help</h2>"
         "<p>Your community action agency is where to apply and where to ask about your "
         "household. The Department of Energy also lists these:</p><ul>"
         "<li><b>211 New Hampshire:</b> dial 211, or 1-866-444-4211, for help finding other "
         "assistance.</li>"
         "<li><b>Neighbor Helping Neighbor</b>, for customers of Eversource, Liberty and Unitil, "
         "and <b>Project Care</b>, for New Hampshire Electric Co-op customers.</li></ul>"
         f'<p class="g-acts"><a class="g-btn" href="{NH211}" target="_blank" rel="noopener">211 '
         "New Hampshire</a></p>"
         "<p>For help with other benefits, and someone to talk them through with:</p>"
         + helps("nheasy", "adrc"))


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
    "application, show photo identification, and pay $15, which includes one copy; more copies "
    "of the same record made at the same time are $10 each. Only the person named, close family "
    "and a few others may get a recent record.",
    [ask("Is the record yours, or a close family member's?",
         [("Yes", "Apply with your photo ID."),
          ("No", "You may still qualify, with a letter showing why you need it.")]),
     box("Apply at your town or city clerk&rsquo;s office, or by mail to the state."),
     box("Pay $15 for the search and one copy, and $10 for each extra copy.")],
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
          "<p>The fee is $15 for the search, which includes one copy, and $10 for each further "
          "copy of the same record issued at the same time. The law sets both. The $15 is paid "
          "whether or not the record is found, and a card payment may cost extra.</p>",
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
    see=[("How to vote in New Hampshire", "/guides/how-to-vote.html")],
    figures=[fig("$15", "RSA 5-C:10", "the sum of $15 for making a search"),
             fig("$10", "RSA 5-C:10", "$10 for each subsequent copy")])


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
    "If you believe your assessment does not reflect your property&rsquo;s value, or you are "
    "unable to pay because of poverty, you can ask your town or city for an <em>abatement</em> by March 1 after your final tax bill. It has "
    "until July 1 to decide, and silence counts as no. Then you can appeal to the Board of Tax "
    "and Land Appeals or the Superior Court, one or the other, by September 1. Keep paying your "
    "taxes meanwhile: if an abatement is granted, the amount abated is refunded with interest.",
    [box("Apply to your town or city by March 1 after the final tax bill."),
     box("The town decides by July 1. No answer counts as a denial."),
     ask("Was the abatement denied?",
         [("Appeal to the Board of Tax and Land Appeals", "$65, by September 1."),
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
          "<p>The application asks for specific reasons, not a general statement about the tax. "
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
     step("Appeal a denial",
          "<p>You can appeal to the <b>Board of Tax and Land Appeals</b> or to the <b>Superior "
          "Court</b>, but not both. For the Board, fill in its appeal form and mail it or hand it "
          "in, with the $65 filing fee by check or money order payable to &ldquo;Treasurer, "
          "State of NH&rdquo;, to the Board of Tax and Land Appeals, 107 Pleasant Street, Johnson Hall, "
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
           "later; appeal as under 76:16-a or 76:17.", "RSA 76:21", CHECKED)]
    + help_claims("legal_aid", "lawyer"),
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
         "Board of Tax and Land Appeals</a></p>"
         "<p>For legal help, including if you are at risk of losing your home over unpaid "
         "property taxes:</p>"
         + helps("legal_aid", "lawyer"),
    see=[("Help paying property tax on a low or moderate income", "/guides/property-tax-relief.html")],
    figures=[fig("$65", "RSA 76:16-a", "upon payment of a $65 filing fee")])


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
    "If you own and live in your home and your household income is $37,000 or less (single) or "
    "$47,000 or less (married or head of household), the state refunds some or all of the State "
    "Education Property Tax on it. You apply to the Department of Revenue Administration "
    "between May 1 and June 30, online or on Form DP-8.",
    [ask("Do you own and live in your home, and is your household income under the limit?",
         [("Yes", "Apply between May 1 and June 30."),
          ("Not sure", "Read who qualifies below, or call the Department.")]),
     box("Apply online at Granite Tax Connect, or on Form DP-8."),
     box("The Department has 120 days to process a complete claim.")],
    [step("Check that you qualify",
          "<p>You qualify if all of these are true:</p><ul>"
          "<li>you own a home, or an interest in one, that is subject to the State Education "
          "Property Tax;</li><li>you lived in it on April 1 of the year you are claiming for; "
          "and</li><li>your household income is $37,000 or less if you are single, or $47,000 or "
          "less if you are married or a head of household.</li></ul>"
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
     claim("A fraudulent claim is a misdemeanor; audits within 3 years.", "RSA 198:59", CHECKED)]
    + help_claims("adrc", "legal_aid"),
    more="<h2>How Much It Can Be</h2>"
         "<p>The relief is a share of the State Education Property Tax on the lesser of your "
         "home&rsquo;s assessed value and $220,000 multiplied by your town&rsquo;s equalization "
         "ratio, at the education tax rate on your bill. The share depends on your household "
         "income. The Department works it out from your claim.</p>"
         + table("The share of the tax refunded (RSA 198:57, IV)",
                 ["Share", "Single", "Married or head of household"],
                 [["100%", "Under $23,100", "Under $29,400"],
                  ["60%", "$23,100 to under $27,800", "$29,400 to under $35,300"],
                  ["40%", "$27,800 to under $32,400", "$35,300 to under $41,100"],
                  ["20%", "$32,400 to $37,000", "$41,100 to $47,000"]])
         + "<p>A false claim is a crime, and the Department may audit a claim within three years "
           'of granting it (<a href="/laws/198#s59">RSA 198:59</a>).</p>'
         "<h2>Who Can Help</h2>"
         "<p>The Department of Revenue Administration answers questions about this program at "
         "(603) 230-5920, and keeps a page of frequently asked questions.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{DRA_LMI_FAQ}" target="_blank" rel="noopener">'
         "Frequently asked questions</a></p>"
         "<p>For help with an application, or with other benefits, and for legal help if you are "
         "at risk of losing your home over property taxes:</p>"
         + helps("adrc", "legal_aid"),
    see=[("How to appeal your property tax assessment", "/guides/property-tax-abatement.html")],
    figures=[fig("$37,000", "RSA 198:57", "$37,000 or less if a single person"),
             fig("$47,000", "RSA 198:57", "$47,000 or less if a married person or head of a New Hampshire household"),
             fig("$220,000", "RSA 198:57", "Multiply $220,000 by the most current local equalization ratio"),
             fig("100%", "RSA 198:57", "less than $23,100, 100 percent"),
             fig("60%", "RSA 198:57", "$23,100 but less than $27,800, 60 percent"),
             fig("40%", "RSA 198:57", "$27,800 but less than $32,400, 40 percent"),
             fig("20%", "RSA 198:57", "$32,400 but less than or equal to $37,000, 20 percent"),
             fig("$23,100", "RSA 198:57", "less than $23,100, 100 percent"),
             fig("$27,800", "RSA 198:57", "$23,100 but less than $27,800, 60 percent"),
             fig("$32,400", "RSA 198:57", "$27,800 but less than $32,400, 40 percent"),
             fig("$29,400", "RSA 198:57", "less than $29,400, 100 percent"),
             fig("$35,300", "RSA 198:57", "$29,400 but less than $35,300, 60 percent"),
             fig("$41,100", "RSA 198:57", "$35,300 but less than $41,100, 40 percent")])


GUIDES = [VOTING, PUBLIC_RECORD, ENERGY, VITAL, ABATEMENT, LMI]


# ---------------------------------------------------------------------------
# THE SEVEN GUIDES OF 17 OCTOBER 2026, which the person chose that day for the
# soft launch of 10 November. Each agency page was read on 17 October 2026 in
# the desktop app's browser on the laptop, one page at a time, because the
# state's web host answered a fetch from anywhere else with 403 that day as it
# did on the 11th; each statute was read in the table on this disk. A form or
# a lookup a guide links is one the page it was read on links, by that link's
# address. The forms themselves were not opened, because there a PDF downloads
# rather than displays, so no guide says what a form contains. They are added
# to the list here, after it, so that guides written beside them on the same
# day go in without touching these.
# ---------------------------------------------------------------------------
READ = "2026-10-17"

DMV_RENEW = "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/renew-driver-licensenon-driver-id"
DMV_ONLINE = "https://www.dmv.nh.gov/online-services/online-renewals"
DMV_APPT = "https://www.dmv.nh.gov/appointments-and-services"
DMV_FEES = "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/licensing-fees"
DMV_REALID = "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/real-id"
DMV_TRANSFER = "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/transfer-license-another-state"
DMV_REG = "https://www.dmv.nh.gov/vehicles-boats-and-titles/vehicle-registrations"
DMV_NEW = "https://www.dmv.nh.gov/vehicles-boats-and-titles/vehicle-registrations/new-resident-new-hampshire"
# Linked from the pages above.
DMV_APP = "https://www.dmv.nh.gov/sites/g/files/ehbemt416/files/inline-documents/dsmv450.pdf"
DMV_REALID_DOCS = "https://www.dmv.nh.gov/sites/g/files/ehbemt416/files/inline-documents/sonh/dsmv634a.pdf"
DMV_DOC_CHECK = "https://www.app-support.nh.gov/erealid/"
DMV_NON_US = "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/non-us-citizen"
DMV_LOCATIONS = "https://www.dmv.nh.gov/hours-and-locations"
DMV_FEE_EST = "https://services.dos.nh.gov/mos/vfchk"
DMV_TEMP_PLATES = "https://www.dmv.nh.gov/vehicles-boats-and-titles/temporary-plates"
DMV_VIN = "https://www.dmv.nh.gov/sites/g/files/ehbemt416/files/inline-documents/tdmv19a.pdf"
# The federal page the person named for REAL ID (guide_sources.OTHER).
TSA_REALID = "https://www.tsa.gov/real-id"

DMV_HELP = ("<h2>Who Can Help</h2>"
            "<p>The Division of Motor Vehicles answers questions and books appointments at "
            "603-227-4000.</p>"
            f'<p class="g-acts"><a class="g-btn" href="{DMV_LOCATIONS}" target="_blank" '
            'rel="noopener">DMV offices and hours</a></p>')


# ---------------------------------------------------------------------------
# RENEWING A DRIVER'S LICENSE. From the DMV's renewal, online renewal,
# appointments and fees pages, and RSA 263. The two fees are printed because
# RSA 263:42 sets them, and the DMV's fee table says the same. The DMV mails its
# notice about two months ahead where RSA 263:10 asks for 30 days, so the
# guide gives the DMV's practice, with its page, rather than the law's floor.
# ---------------------------------------------------------------------------
LICENSE = guide(
    "renew-drivers-license", "How to Renew Your Driver's License",
    "Renewing a New Hampshire driver's license or non-driver ID online or at a DMV appointment, "
    "step by step: what to bring, what it costs, and what to do if it has expired.",
    "A New Hampshire driver&rsquo;s license expires on your birthday in the fifth year after it "
    "was issued. About two months before, the Division of Motor Vehicles mails you a renewal "
    "notice. If the notice says you can renew online, you can; otherwise make an appointment at a "
    "DMV office. A renewal costs $50, or $60 for a REAL ID license.",
    [ask("Does your renewal notice say you can renew online?",
         [("Yes", "Renew online with the Renewal Identification Number on the notice."),
          ("No, or no notice", "Make an appointment at a DMV office and bring what it asks for.")]),
     box("Getting a REAL ID for the first time? That renewal is in person."),
     box("You leave with a 60-day paper license, and the new card comes by mail within 60 days.")],
    [step("Watch for your renewal notice",
          "<p>About two months before your license expires, the DMV mails a renewal notice to the "
          "address it has for you. You will not get one if your mail is forwarded, if you moved and "
          "did not tell the DMV your new address, or if your license is suspended.</p>"
          "<p>The expiration date is printed in red on the front of your license.</p>",
          law=["RSA 263:10, I"]),
     step("Renew online, if your notice says you can",
          "<p>You need:</p><ul>"
          "<li>the <b>Renewal Identification Number</b> from your notice, which works from 60 days "
          "before your birthday to 60 days after it;</li>"
          "<li>your current license in hand, because you will type in details printed on it;</li>"
          "<li>a MasterCard, VISA, Discover or American Express card; and</li>"
          "<li>a printer, to print the temporary license you carry with your old card until the "
          "new one arrives.</li></ul>"
          "<p>Only you can renew your own license, and your current photo is reused. The law allows "
          "an online renewal only every other time, so the renewal after an online one is in "
          "person.</p>",
          actions=[("Renew online", DMV_ONLINE)], law=["RSA 263:10, II"]),
     step("Or renew at a DMV appointment",
          "<p>DMV offices see people by appointment. Book online, or call 603-227-4000. Bring:</p><ul>"
          "<li>the completed Application for Driver License (form DSMV 450);</li>"
          "<li>your current license, or other proof of identity if you cannot find it;</li>"
          "<li>the fee; and</li><li>be ready for a vision test.</li></ul>"
          "<p>To upgrade to a REAL ID at the same time, bring the extra documents it needs. If you "
          "are not a U.S. citizen, the DMV lists what to bring on a page of its own.</p>",
          actions=[("Make an appointment", DMV_APPT), ("Application (DSMV 450)", DMV_APP),
                   ("If you are not a U.S. citizen", DMV_NON_US)]),
     step("Pay the fee",
          "<p>A renewed license costs $50, or $60 for a REAL ID license. The law sets both. The DMV "
          "takes credit cards, cash in person, and checks or money orders payable to &ldquo;State of "
          "NH - DMV&rdquo;. Its fees page lists the rest, for youth, motorcycle and commercial "
          "licenses.</p>",
          actions=[("All licensing fees", DMV_FEES)], law=["RSA 263:42, I"]),
     step("If your license has already expired",
          "<p>You may not drive until you renew it. What you need depends on how long ago it "
          "expired:</p><ul>"
          "<li><b>Less than a year:</b> renew as usual.</li>"
          "<li><b>One to three years:</b> bring proof of identity and residence for your kind of "
          "license to a DMV office.</li>"
          "<li><b>Three years or more:</b> the same documents, and you must pass a vision test, a "
          "knowledge test and a road test.</li></ul>",
          actions=[("Renewal requirements", DMV_RENEW)])],
    [("Renew a Driver License/CDL/Non Driver ID (Division of Motor Vehicles)", DMV_RENEW),
     ("Online Renewals (Division of Motor Vehicles)", DMV_ONLINE),
     ("Appointments and Services (Division of Motor Vehicles)", DMV_APPT),
     ("Licensing Fees (Division of Motor Vehicles)", DMV_FEES),
     ("Drivers' Licenses, RSA 263", "/laws/263")],
    ["263"],
    [claim("The DMV mails a renewal notice about two months before expiry, not if mail is forwarded, "
           "the address was not updated or the license is suspended; the date is in red on the "
           "front; renew online if the notice allows, or by appointment with the DSMV 450, the "
           "current license or other proof of identity, the fee and a vision test; a REAL ID "
           "upgrade needs more documents; non-citizens have their own page; expired under a year, "
           "one to three years, three years or more, with the tests; a CDL and a non-driver ID "
           "renew the same ways.", DMV_RENEW, READ),
     claim("Online: the RIN on the notice, valid 60 days before and after the birthday; only you "
           "can renew your own; have the current card; MasterCard, VISA, Discover or American "
           "Express; print the temporary, which with the old card serves until the new one is "
           "mailed within 60 days; the current photo is reused; a first REAL ID is in person.",
           DMV_ONLINE, READ),
     claim("The DMV is fully appointment based; book online or call 603-227-4000.", DMV_APPT, READ),
     claim("Payment by credit card, cash in person, or check or money order payable to State of NH "
           "- DMV; $50 operator, $60 REAL ID operator, and the youth, motorcycle and CDL fees.",
           DMV_FEES, READ),
     claim("A license expires on the fifth anniversary of the holder's birth date following issue; "
           "online renewal only once in every other renewal cycle, the next in person.",
           "RSA 263:10", READ),
     claim("$60 for a Real ID Act compliant license, $50 for each other license, original or "
           "renewal.", "RSA 263:42", READ)],
    more=DMV_HELP,
    see=[("How to get a REAL ID", "/guides/real-id.html"),
         ("New to New Hampshire: license, registration and voting", "/guides/new-to-new-hampshire.html")],
    figures=[fig("$60", "RSA 263:42", "$60 for a Real ID Act compliant license"),
             fig("$50", "RSA 263:42", "$50 for each other license")])


# ---------------------------------------------------------------------------
# REGISTERING A CAR. The DMV's own words: "a two-part process", the town first
# and then the state. From its Vehicle Registrations page and RSA 261. The fees
# depend on the vehicle -- the town's on its list price and age (RSA 261:153),
# the state's set out in RSA 261:141 -- so the guide links the DMV's estimator
# rather than print a figure.
# ---------------------------------------------------------------------------
CAR = guide(
    "register-a-car", "How to Register a Car",
    "Registering a vehicle in New Hampshire in its two parts, at your town or city clerk and then "
    "for the state, step by step: what to bring for each kind of purchase, how the fees work, and "
    "renewing.",
    "Registering a vehicle in New Hampshire is a two-part process. You start at the town or city "
    "clerk where you live, who confirms that you live there and collects the town&rsquo;s fee. The "
    "second part is the state&rsquo;s registration, which many clerks can complete for you for an "
    "extra fee; otherwise you finish it with the Division of Motor Vehicles.",
    [box("Go to the town or city clerk where you live, with your title or bill of sale and photo ID."),
     box("Pay the town&rsquo;s fee there. The state cannot register the vehicle until it is paid."),
     ask("Can your clerk do the state part too?",
         [("Yes", "Finish there, for an extra fee."),
          ("No", "Finish with the DMV, by appointment or drop box.")])],
    [step("Gather what you need",
          "<p>Bring a current government photo ID, and proof that you live in the town if your clerk "
          "has not already seen it. What else depends on how you got the vehicle:</p><ul>"
          "<li><b>From a New Hampshire dealer:</b> the certificate of title, or the blue copies of "
          "the title application.</li>"
          "<li><b>From a dealer in another state:</b> the title from the dealer, or the New "
          "Hampshire title application from your lender. For a brand-new vehicle, the "
          "manufacturer&rsquo;s statement of origin.</li>"
          "<li><b>From a private seller:</b> the title, properly signed over to you.</li>"
          "<li><b>A vehicle exempt from titling, from a private seller:</b> a bill of sale with "
          "the details the law lists, and proof of the vehicle identification number (VIN): the "
          "title or a copy, a past New Hampshire registration or a copy, or the DMV&rsquo;s VIN "
          "verification form.</li></ul>"
          "<p>If the vehicle is leased or financed through a lender in another state, start with "
          "the DMV&rsquo;s page on 60-day temporary plates.</p>",
          actions=[("Vehicle registrations", DMV_REG), ("VIN verification form", DMV_VIN),
                   ("Temporary plates", DMV_TEMP_PLATES)],
          law=["RSA 261:148"]),
     step("Start at your town or city clerk",
          "<p>Every motor vehicle except a moped starts at the clerk&rsquo;s office of the town or "
          "city where you live. The clerk confirms your residence and issues the town&rsquo;s "
          "permit, which the state needs before it will register the vehicle. The town&rsquo;s "
          "fee is set by law from the maker&rsquo;s list price, and gets smaller as the vehicle "
          "ages.</p>",
          actions=[("Find your town or city clerk", SOS_CLERKS)],
          law=["RSA 261:148", "RSA 261:153"]),
     step("Finish the state part",
          "<p>Many clerks are agents of the state and can complete the state registration too, "
          "for an extra fee. If you have the title, or the vehicle needs none, you may be able to "
          "do everything at the clerk&rsquo;s office. Otherwise, the DMV completes the state part by "
          "appointment or through its drop box service.</p>",
          actions=[("DMV appointments and drop box", DMV_APPT)], law=["RSA 261:74-a"]),
     step("Know what you will pay",
          "<p>You pay fees to both the town and the state, and a plate fee the first time you order "
          "plates. The amount differs for each vehicle, so use the DMV&rsquo;s estimator, or ask "
          "your clerk.</p>",
          actions=[("Estimate your fees", DMV_FEE_EST)], law=["RSA 261:141", "RSA 261:153"]),
     step("Renew every year",
          "<p>A registration in your own name expires at the end of the month of your birthday. To "
          "renew, bring your registration or renewal notice to your town or city and pay the "
          "town&rsquo;s fees first; many towns can take the state&rsquo;s part as well. Ask your "
          "clerk or tax collector whether your town takes renewals online or by mail.</p>",
          law=["RSA 261:62"])],
    [("Vehicle Registrations (Division of Motor Vehicles)", DMV_REG),
     ("Appointments and Services (Division of Motor Vehicles)", DMV_APPT),
     ("Town and city clerks (Secretary of State)", SOS_CLERKS),
     ("Certificates of Title and Registration of Vehicles, RSA 261", "/laws/261")],
    ["261"],
    [claim("Two-part process; all motor vehicles but mopeds begin at the town or city clerk where "
           "they reside, who determines residency; the clerk may be a municipal agent and do the "
           "state part for an additional fee; with a title or a title-exempt vehicle the whole "
           "transaction may be done at the clerk; out-of-state loan or lease: the 60-day temporary "
           "plate page; fees to both, RSA 261:141 and 261:153, an $8 plate fee the first time, the "
           "estimator; the documents for a NH dealer, an out-of-state dealer (MSO if new), a "
           "private sale and a title-exempt private sale (bill of sale per RSA 261:148, proof of "
           "VIN by title, past NH registration or the VIN form); proof of residency; renewals at "
           "the town with town fees first, municipal agents, ask the clerk or tax collector about "
           "online or mail.", DMV_REG, READ),
     claim("New/Transfer Registration (state portion only) and Registration Renewal (state portion "
           "only): drop box or appointment.", DMV_APPT, READ),
     claim("No registration until the town's permit; the clerk needs a current government-issued "
           "photo ID and the title or title application, or for a title-exempt vehicle a bill of "
           "sale with the listed details.", "RSA 261:148", READ),
     claim("The town's permit fee is a number of mills on the maker's list price, falling with each "
           "model year to the fifth.", "RSA 261:153", READ),
     claim("The department's registration fees.", "RSA 261:141", READ),
     claim("Municipal officials may be appointed agents to issue, renew or transfer registrations.",
           "RSA 261:74-a", READ),
     claim("An individual's registration expires at the end of the month of the registrant's "
           "birthday, the first after issue or, for an original issued in the four months before "
           "it, the second.", "RSA 261:62", READ)],
    more="<h2>Who Can Help</h2>"
         "<p>Your town or city clerk is the place to start, and can tell you what your town asks "
         "for and whether it does the state&rsquo;s part. The Division of Motor Vehicles answers "
         "questions at 603-227-4000.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_CLERKS}" target="_blank" rel="noopener">'
         "Find your town or city clerk</a></p>",
    see=[("New to New Hampshire: license, registration and voting", "/guides/new-to-new-hampshire.html")])


# ---------------------------------------------------------------------------
# A REAL ID. From the DMV's REAL ID page and the Transportation Security
# Administration's, the federal page the person named. RSA 263:14-b names
# citizenship among the documents and the DMV's page does not, so the guide
# follows the DMV for what to bring and sends anyone who is not a citizen to
# the DMV's own page, citing the statute only for the fee.
# ---------------------------------------------------------------------------
REAL_ID = guide(
    "real-id", "How to Get a REAL ID",
    "Getting a REAL ID driver's license or non-driver ID in New Hampshire, step by step: whether "
    "you need one, the documents to bring to a DMV appointment, and what it costs.",
    "A REAL ID is a driver&rsquo;s license or non-driver ID marked with a star. Since May 7, 2025, "
    "you need one, or a passport or another accepted ID, to board a domestic flight or enter a "
    "secure federal building. In New Hampshire it is voluntary. You get one in person at a DMV "
    "office, when you renew or by appointment, with documents proving your identity, your Social "
    "Security number and that you live in New Hampshire.",
    [ask("Will you fly within the U.S. or enter secure federal buildings without a passport?",
         [("Yes", "Consider a REAL ID, and plan at least three months ahead."),
          ("No", "You might not need one. A card without the star says Not for Federal "
                 "Identification.")]),
     box("Check which documents to bring, then make a DMV appointment."),
     box("Go in person: a first REAL ID cannot be done online.")],
    [step("Decide whether you need one",
          "<p>A REAL ID license or ID has a star in the top right corner. Since May 7, 2025, you "
          "need one, or a passport or another accepted ID, to board a domestic flight or enter a "
          "secure federal facility such as a military base or a courthouse.</p>"
          "<p>REAL ID is voluntary in New Hampshire. A card without the star is marked &ldquo;NOT "
          "FOR FEDERAL IDENTIFICATION&rdquo;, and you would show a passport or another accepted "
          "ID for those purposes instead. The Transportation Security Administration charges a fee "
          "to travelers who arrive without an accepted ID.</p>",
          actions=[("REAL ID (DMV)", DMV_REALID), ("REAL ID (TSA)", TSA_REALID)]),
     step("Gather your documents",
          "<p>You prove three things: your identity, your Social Security number, and that you live "
          "in New Hampshire. The DMV&rsquo;s online document checker shows what to bring for your "
          "situation.</p>"
          "<p>If your name has changed, through marriage, divorce, adoption or otherwise, your "
          "birth certificate or passport will show a different name, so bring proof of each change "
          "that links it to your current name. The document checker&rsquo;s Name Change Wizard "
          "helps. If you are not a U.S. citizen, the DMV lists what to bring on its own page.</p>",
          actions=[("Online document checker", DMV_DOC_CHECK), ("The list of documents", DMV_REALID_DOCS),
                   ("If you are not a U.S. citizen", DMV_NON_US)]),
     step("Make an appointment",
          "<p>You can get a REAL ID when you renew, or upgrade before then by appointment. The DMV "
          "suggests booking at least three months before you need it. Bring the application for "
          "your kind of license (form DSMV 450 for a driver&rsquo;s license or non-driver ID) with "
          "your documents. A first REAL ID cannot be done by online renewal.</p>",
          actions=[("Make an appointment", DMV_APPT), ("Application (DSMV 450)", DMV_APP)]),
     step("Pay the fee",
          "<p>At renewal, a REAL ID license costs $60, against $50 for a license without the "
          "star. The law sets both. If you upgrade before your renewal is due, the DMV also "
          "charges a replacement fee, which its REAL ID page gives.</p>",
          actions=[("Licensing fees", DMV_FEES)], law=["RSA 263:42, I"])],
    [("REAL ID (Division of Motor Vehicles)", DMV_REALID),
     ("REAL ID (Transportation Security Administration)", TSA_REALID),
     ("Appointments and Services (Division of Motor Vehicles)", DMV_APPT),
     ("Drivers' Licenses, RSA 263", "/laws/263")],
    ["263"],
    [claim("From May 7, 2025, a federally compliant license or ID, or a passport, to board domestic "
           "flights or enter a secure federal facility (a military base or courthouse); the star "
           "in the top right; voluntary in NH; otherwise the card says NOT FOR FEDERAL "
           "IDENTIFICATION; plan at least three months ahead; at renewal or by appointment, with "
           "documents proving identity, Social Security number and NH residency; the online "
           "document checker and its Name Change Wizard; proof of each name change; a replacement "
           "fee to opt in before renewal; bring the application for the license type.",
           DMV_REALID, READ),
     claim("A first REAL ID needs an in-person appointment, not an online renewal.", DMV_ONLINE, READ),
     claim("Upgrade to REAL ID outside renewal by appointment; a renewal may upgrade.", DMV_APPT, READ),
     claim("Enforcement began May 7, 2025; REAL ID compliant to board domestic flights and access "
           "certain federal facilities; a star; a passport is acceptable; travelers without an "
           "acceptable ID pay a fee.", TSA_REALID, READ),
     claim("Operator $50, REAL ID operator $60.", DMV_FEES, READ),
     claim("$60 for a Real ID Act compliant license, $50 for each other license.", "RSA 263:42", READ)],
    more=DMV_HELP,
    see=[("How to renew your driver's license", "/guides/renew-drivers-license.html")],
    figures=[fig("$60", "RSA 263:42", "$60 for a Real ID Act compliant license"),
             fig("$50", "RSA 263:42", "$50 for each other license")])


# ---------------------------------------------------------------------------
# NEW TO NEW HAMPSHIRE. The two 60-day deadlines are the statute's (RSA
# 263:35 and 261:45), and the DMV's New Resident page says the same. That page
# also says every vehicle must be safety inspected, but the statute table holds
# RSA 266:1 repealed from January 31, 2026 (2025, 141:253), so the guide says
# nothing about inspection until the two agree. It says too that a voter
# without proof may sign an affidavit for any qualification, which the 2026
# changes narrowed, so voting is left to the Secretary of State's page and How
# to Vote.
# ---------------------------------------------------------------------------
NEW_RESIDENT = guide(
    "new-to-new-hampshire", "New to New Hampshire: License, Registration and Voting",
    "Moving to New Hampshire: the 60-day deadlines to get a New Hampshire driver's license and "
    "register your vehicle, where to go for each, and how to register to vote.",
    "Once New Hampshire is your home, you have 60 days to get a New Hampshire driver&rsquo;s "
    "license if you drive here, and 60 days to register any vehicle you own and use here. The "
    "license comes from a DMV office, by appointment; the registration starts at your town or city "
    "clerk. You can register to vote with your clerk before an election, or at your polling place "
    "on election day, with no waiting period.",
    [box("Make a home in a New Hampshire town or city: the 60 days start then."),
     ask("Do you drive here, or own a vehicle you use here?",
         [("I drive here", "Get a New Hampshire license from the DMV within 60 days."),
          ("I own a vehicle", "Register it within 60 days, starting at your town or city clerk.")]),
     box("Register to vote with your clerk, or at the polls on election day.")],
    [step("Know when the 60 days start",
          "<p>They start when you make a town or city ward in New Hampshire your home: your "
          "principal place of physical presence, to the exclusion of every other. Actions such as "
          "buying or leasing your main house or apartment, registering a vehicle here, putting "
          "your children in a public school, or registering to vote show that you have.</p>",
          actions=[("New to New Hampshire (DMV)", DMV_NEW)]),
     step("Get a New Hampshire driver's license",
          "<p>If you drive in New Hampshire, get a New Hampshire license within 60 days. If you do "
          "not drive here, you do not need one.</p>"
          "<p>Make an appointment at a DMV office, and bring the completed application (form DSMV "
          "450), proof of your identity and residence for the kind of license you want (a REAL ID "
          "or not), and the fee; there is a vision test. You must hand in every license from "
          "another state. You leave with a 60-day paper license, and the card comes by mail within "
          "60 days. If you are not a U.S. citizen, the DMV&rsquo;s page explains where to "
          "apply.</p>"
          "<p>The DMV lists a few kinds of out-of-state license that are not valid for driving in "
          "New Hampshire, on its page about transferring a license.</p>",
          actions=[("Transfer a license from another state", DMV_TRANSFER),
                   ("Make an appointment", DMV_APPT), ("If you are not a U.S. citizen", DMV_NON_US)],
          law=["RSA 263:35, I", "RSA 263:4"]),
     step("Register your vehicle",
          "<p>If you own a vehicle you use in New Hampshire, register it here within 60 days. Take "
          "the title and proof of your residence to the clerk&rsquo;s office of the town or city "
          "where you live. If the vehicle is leased, financed, or exempt from titling, bring "
          "your registration from the other state, the lease if there is one, your lender&rsquo;s "
          "name and address, and proof of residence. The clerk prepares a New Hampshire title "
          "application. Fees differ for each vehicle, so ask your clerk.</p>",
          actions=[("Find your town or city clerk", SOS_CLERKS)], law=["RSA 261:45, I"]),
     step("Register to vote",
          "<p>There is no minimum time you must live here before registering. Register with your "
          "town or city clerk, or at a session of the supervisors of the checklist, up to 6 to 13 "
          "days before an election, or at your polling place on election day. Bring proof of your "
          "identity, age, citizenship and domicile; How to Vote lists what counts.</p>"
          "<p>You do not need a New Hampshire driver&rsquo;s license to register or to vote.</p>",
          actions=[("Register to vote", SOS_REGISTER)]),
     step("Keep your address up to date",
          "<p>Once you hold a New Hampshire license, tell the DMV within 30 days whenever you change "
          "your name, your home or your mailing address. An address change can go through the "
          "DMV&rsquo;s drop box service.</p>",
          actions=[("DMV appointments and drop box", DMV_APPT)], law=["RSA 263:9"])],
    [("New Resident to New Hampshire (Division of Motor Vehicles)", DMV_NEW),
     ("Transfer License From Another State (Division of Motor Vehicles)", DMV_TRANSFER),
     ("Register to vote (Secretary of State)", SOS_REGISTER),
     ("Drivers' Licenses, RSA 263", "/laws/263"),
     ("Certificates of Title and Registration of Vehicles, RSA 261", "/laws/261")],
    ["263", "261"],
    [claim("Domicile/residence is making a town or ward the principal place of physical presence to "
           "the exclusion of all others, shown by actions such as a home, a resident registration, "
           "children in public school, registering to vote; a driver gets a NH license within 60 "
           "days, a non-driver need not; a vehicle owner registers within 60 days with the town or "
           "city; title and proof of residency, or for leased, financed or title-exempt vehicles "
           "the out-of-state registration, lease, lienholder and proof of residency; fees differ, "
           "contact the town; title applications prepared by a clerk, dealer or lender; a NH "
           "license is not needed to register to vote or vote; out-of-state licenses surrendered; "
           "a 60-day paper temporary and the card mailed within 60 days.", DMV_NEW, READ),
     claim("A NH license within 60 days of residency; by appointment with the DSMV 450, proof of "
           "identity and residency for REAL ID or not, the fee and a vision test; non-citizens see "
           "their page; listed out-of-state license classes are invalid in NH.", DMV_TRANSFER, READ),
     claim("Address change by drop box service.", DMV_APPT, READ),
     claim("Citizen, 18 on election day, resident of the town or ward, no minimum period; register "
           "with the clerk or supervisors 6 to 13 days before, or at the polls; proof of identity, "
           "age, citizenship and domicile.", SOS_REGISTER, READ),
     claim("A nonresident with a valid license from another jurisdiction has 60 days from "
           "establishing bona fide residency to obtain a NH license.", "RSA 263:35", READ),
     claim("No license until every other jurisdiction's license is surrendered.", "RSA 263:4", READ),
     claim("A new resident has 60 days from residency to register vehicles in NH.", "RSA 261:45", READ),
     claim("A licensed driver notifies the director within 30 days of a change of legal name, "
           "permanent residence or mailing address.", "RSA 263:9", READ)],
    more="<h2>Who Can Help</h2>"
         "<p>Your town or city clerk handles both your vehicle registration and your voter "
         "registration. The Division of Motor Vehicles answers licensing questions at "
         "603-227-4000.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_CLERKS}" target="_blank" rel="noopener">'
         "Find your town or city clerk</a></p>",
    see=[("How to vote in New Hampshire", "/guides/how-to-vote.html"),
         ("How to register a car", "/guides/register-a-car.html"),
         ("How to get a REAL ID", "/guides/real-id.html")])


# ---------------------------------------------------------------------------
# FOOD AND HEALTH ASSISTANCE. One application covers SNAP and Medicaid, so one
# guide. From the Department of Health and Human Services' SNAP, Medicaid,
# Apply for Assistance, Stay Covered and Administrative Appeals pages. Income
# limits and benefit amounts are the Department's and change, and the plan
# forbids eligibility math, so none is printed. The note on work requirements
# gives the change as the Department states it, and names the 2025 federal law
# by its date, as the SNAP page does.
# ---------------------------------------------------------------------------
DHHS_SNAP = ("https://www.dhhs.nh.gov/programs-services/food-meals-assistance/"
             "supplemental-nutrition-assistance-program-snap")
DHHS_MEDICAID = "https://www.dhhs.nh.gov/programs-services/medicaid"
DHHS_APPLY = "https://www.dhhs.nh.gov/apply-assistance"
DHHS_STAY = "https://www.dhhs.nh.gov/programs-services/stay-covered-new-hampshire"
DHHS_APPEALS = "https://www.dhhs.nh.gov/doing-business-dhhs/legal-services/administrative-appeals"
# Linked from the pages above.
DHHS_PROOF = "https://nheasy.nh.gov/forms/E/800V.pdf"
DHHS_OFFICES = "https://www.dhhs.nh.gov/about-dhhs/locations-facilities#locations"

BENEFITS = guide(
    "food-and-health-assistance", "How to Apply for Food or Health Assistance",
    "Applying for SNAP food benefits and Medicaid health coverage through New Hampshire's "
    "Department of Health and Human Services, online at NH Easy or on paper, step by step, and "
    "what to do if you disagree with a decision.",
    "The Department of Health and Human Services takes applications for SNAP (food assistance) and "
    "Medicaid (health coverage) together. Apply online at NH Easy, or on the paper Application for "
    "Assistance mailed to your local District Office. After you apply you may have an interview, "
    "and you will be asked for proof of your household&rsquo;s circumstances. The Department says "
    "the only way to find out whether you qualify is to apply.",
    [ask("How do you want to apply?",
         [("Online", "Apply at NH Easy, for SNAP, Medicaid, cash and child care at once."),
          ("On paper", "Fill in the Application for Assistance and mail it to your District Office.")]),
     box("Answer the Department&rsquo;s questions: an interview if it asks, and proof of your "
         "household&rsquo;s circumstances."),
     box("Read the Notice of Decision. If you disagree, you can appeal.")],
    [step("Know what you are applying for",
          "<ul><li><b>SNAP</b>, the Supplemental Nutrition Assistance Program, gives eligible "
          "low-income people and families benefits to buy food, paid each month onto an EBT card "
          "used like a debit card at the checkout. Whether you qualify depends on your household&rsquo;s "
          "size, income, expenses and resources. You may qualify whether you own a home, have none, "
          "live alone or with others, and whether or not you work or have children.</li>"
          "<li><b>Medicaid</b> is health coverage, paid for by the federal and state governments, "
          "for people and families who meet its eligibility requirements.</li></ul>",
          actions=[("SNAP", DHHS_SNAP), ("Medicaid", DHHS_MEDICAID)], law=["RSA 167:4"],
          note="<b>Work requirements changed in 2025.</b> Since November 1, 2025, under federal "
               "legislation passed on July 4, 2025, adults aged 18 through 64 who are able to work "
               "and have no child under 14 in their household must work, volunteer or take part in "
               "training at least 80 hours a month to get SNAP for more than three months in three "
               "years, unless they are exempt; the SNAP page lists the exemptions. The Department is "
               "also preparing for changes to Medicaid eligibility, including work or other "
               "community engagement requirements for people covered through the Granite Advantage "
               "Health Care Program; its Stay Covered New Hampshire page has them. This is what the "
               "Department said on October 17, 2026: check its pages before you apply."),
     step("Apply online or on paper",
          "<p><b>Online:</b> NH Easy, the Department&rsquo;s benefits site, takes one application "
          "for cash, SNAP, child care and Medicaid, and can tell you first whether you might "
          "qualify.</p>"
          "<p><b>On paper:</b> to apply for every kind of assistance, fill in both the Application "
          "for Assistance (Form 800) and its Medical Assistance insert, and mail them to your local "
          "District Office. Both come in Spanish too. For Medicaid alone there is a shorter form, "
          "800MA. For SNAP, you can also call 603-271-9700 to have an application mailed to "
          "you.</p>"
          "<p>If someone is helping you apply, you both fill in the Authorized Representative "
          "Declaration (Form 778).</p>",
          actions=[("NH Easy", NHEASY), ("Paper applications", DHHS_APPLY)]),
     step("After you apply",
          "<p>You may need to talk with a Department specialist about your situation in an "
          "interview; the Department tells you if one is needed. You will also give proof of your "
          "household&rsquo;s circumstances. Form 800V gives examples of what is accepted, and you "
          "can upload documents through NH Easy. Have them with you at an interview to avoid "
          "delays.</p>",
          actions=[("Examples of acceptable proof (Form 800V)", DHHS_PROOF)]),
     step("If you disagree with a decision",
          "<p>You can ask for an administrative appeal hearing. Ask in writing, on the "
          "Department&rsquo;s appeal request form or in a letter, and drop it off or mail it to "
          "your District Office, mail it to the Administrative Appeals Unit, or email it. If you "
          "cannot write, tell a Department representative that you want to appeal.</p>"
          "<p>Generally you have 30 days from the date on your Notice of Decision, or 90 days for "
          "SNAP; your notice gives your deadline. If you appeal within 15 days, you may in some "
          "cases keep your benefits at the same level until the appeal is decided, but must repay "
          "them if the Department&rsquo;s decision is upheld. You do not need a lawyer.</p>",
          actions=[("Administrative appeals", DHHS_APPEALS)])],
    [("Supplemental Nutrition Assistance Program (Department of Health and Human Services)", DHHS_SNAP),
     ("Medicaid (Department of Health and Human Services)", DHHS_MEDICAID),
     ("Apply for Assistance (Department of Health and Human Services)", DHHS_APPLY),
     ("Stay Covered New Hampshire (Department of Health and Human Services)", DHHS_STAY),
     ("Administrative Appeals (Department of Health and Human Services)", DHHS_APPEALS),
     ("Public Assistance, RSA 167", "/laws/167")],
    ["167"],
    [claim("SNAP gives nutrition benefits to eligible low-income individuals and families; "
           "eligibility depends on household size, income, expenses and resources, whether or not "
           "you own a home, have none, live alone or with others, work or have children; the only "
           "way to find out is to apply; NH Easy, or call 603-271-9700 for a mailed application; "
           "monthly deposits to an EBT card; from November 1, 2025, after federal legislation of "
           "July 4, 2025, ABAWDs 18 through 64 with no child under 14 and able to work need 80 "
           "hours a month of work, volunteering or training for SNAP beyond three months in three "
           "years, with listed exemptions.", DHHS_SNAP, READ),
     claim("Medicaid is a federal and state funded health care program for those who meet "
           "eligibility requirements; DHHS is preparing for eligibility changes including work or "
           "community engagement requirements for Granite Advantage; NH Easy takes applications "
           "for cash, SNAP, child care and Medicaid; the Authorized Representative Declaration "
           "(778); 1-844-ASK-DHHS, weekdays 8 to 4; the District Office.", DHHS_MEDICAID, READ),
     claim("Preparing for Medicaid changes after 2025 federal legislation, including work or other "
           "community engagement requirements for Granite Advantage.", DHHS_STAY, READ),
     claim("Apply online or print, complete and mail to the District Office; for all types, both "
           "Form 800 and the Form 800 Insert, with Spanish versions; Medicaid only, Form 800MA; "
           "after applying, an interview if required and proof per Form 800V, uploaded or brought "
           "to the interview.", DHHS_APPLY, READ),
     claim("Appeal in writing by form or letter, to the District Office, by mail to the AAU, or by "
           "email, or by telling a DHHS representative; generally 30 days from the Notice of "
           "Decision, 90 for SNAP; within 15 days benefits may continue, repaid if upheld; no "
           "attorney needed and none appointed.", DHHS_APPEALS, READ),
     claim("Public assistance, including medical assistance and food stamps, is granted under RSA "
           "167 or RSA 161 to eligible people without sufficient income or resources.",
           "RSA 167:4", READ)]
    + help_claims("nheasy", "adrc", "legal_aid"),
    more="<h2>Who Can Help</h2>"
         "<p>The Department&rsquo;s customer service center answers questions about applying, and "
         "your local District Office can help in person.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{DHHS_OFFICES}" target="_blank" rel="noopener">'
         "Find your District Office</a></p>"
         "<p>For help with an application, someone to talk your options through with, and free "
         "legal help if a benefit is denied or cut:</p>"
         + helps("nheasy", "adrc", "legal_aid"),
    see=[("How to get help with heating and electric bills", "/guides/heating-and-electric-help.html")])


# ---------------------------------------------------------------------------
# UNEMPLOYMENT. From New Hampshire Employment Security's File, Eligibility
# and Appeals pages and RSA 282-A. The earnings a claim needs are on the
# Eligibility page and are not printed (the plan: no eligibility math); the
# appeal window is the statute's 14 calendar days, which NHES gives too.
# ---------------------------------------------------------------------------
NHES_FILE = "https://www.nhes.nh.gov/individuals/file-unemployment-benefits"
NHES_ELIG = "https://www.nhes.nh.gov/individuals/unemployment-eligibility"
NHES_APPEALS = "https://www.nhes.nh.gov/individuals/unemployment-appeals"
NHES_OFFICES = "https://www.nhes.nh.gov/resources/office-locations"

UNEMPLOYMENT = guide(
    "file-for-unemployment", "How to File for Unemployment",
    "Filing an unemployment claim with New Hampshire Employment Security, step by step: what to "
    "have ready, the weekly claims and work search that follow, and how to appeal a determination.",
    "If you are out of work, or your hours were cut, through no fault of your own, you can file a "
    "claim for unemployment benefits with New Hampshire Employment Security, online. File with the "
    "state where you physically worked. You will be told whether your past wages qualify and how "
    "much you could receive, and each week after that you file a claim and, unless you are told "
    "otherwise, look for work.",
    [box("File your claim online with New Hampshire Employment Security."),
     box("Read your monetary determination: whether your past wages qualify, and how much."),
     box("Each week, file your weekly claim and do your work search."),
     ask("Do you disagree with a determination?",
         [("Yes", "Appeal within 14 calendar days, as the determination explains."),
          ("No", "Keep filing each week while you are out of work.")])],
    [step("Check that unemployment fits your situation",
          "<p>Unemployment insurance replaces part of your wages if you are unemployed, fully or "
          "partly, through no fault of your own. To be paid for a week you must be able to work, "
          "available for work, and looking for it unless you are exempt, and you must file your "
          "claims on time. Working part-time does not rule you out; working full-time does. School "
          "employees between terms are judged case by case.</p>"
          "<p>You must also have earned enough in a base period of four calendar quarters before "
          "your claim; New Hampshire Employment Security&rsquo;s eligibility page gives the "
          "amounts.</p>",
          actions=[("Unemployment eligibility", NHES_ELIG)], law=["RSA 282-A:31, I"]),
     step("Have these ready",
          "<ul><li>your Social Security number;</li>"
          "<li>if you are not a U.S. citizen, your alien registration number and its expiration "
          "date;</li>"
          "<li>the name, address and phone number of every employer you worked for in the last 18 "
          "months;</li>"
          "<li>your DD 214, if you were in the military in the last 18 months; and</li>"
          "<li>your bank details, if you want payments by direct deposit.</li></ul>"),
     step("File your claim online",
          "<p>On New Hampshire Employment Security&rsquo;s filing page, choose Register or Login "
          "and create an account in Workforce Connect, its claims site. From your dashboard choose "
          "File for Benefits, then Apply for Unemployment Insurance Benefits. Answer every question "
          "accurately, since your answers affect your claim; review and certify it; and print the "
          "confirmation for your records.</p>",
          actions=[("File for unemployment benefits", NHES_FILE)]),
     step("Every week: file a claim and look for work",
          "<p>You file a claim for each week. Unless you are told you are exempt, you must also look "
          "for work every week and report it on your weekly claim: contacting employers, and taking "
          "part in activities that prepare you to go back to work. If you work part-time, report "
          "your hours and earnings on the weekly claim.</p>"),
     step("If you disagree with a determination",
          "<p>Every determination on your claim is on your dashboard and explains how to appeal. "
          "You have 14 calendar days from when it was issued. After you appeal you will get an "
          "Appeal Request Notice, and the hearing is held by an Appeal Tribunal chairperson.</p>",
          actions=[("Unemployment appeals", NHES_APPEALS)], law=["RSA 282-A:48"])],
    [("File for Unemployment Benefits (New Hampshire Employment Security)", NHES_FILE),
     ("Unemployment Eligibility (New Hampshire Employment Security)", NHES_ELIG),
     ("Unemployment Appeals (New Hampshire Employment Security)", NHES_APPEALS),
     ("Unemployment Compensation, RSA 282-A", "/laws/282-a")],
    ["282-A"],
    [claim("Register or log in to Workforce Connect, File for Benefits, Apply for Unemployment "
           "Insurance Benefits, answer accurately, review and certify, print the confirmation; what "
           "to have ready; a weekly work search unless notified of an exemption, contacting "
           "employers and reemployment activities; a monetary determination of wage requirements "
           "and amounts, with appeal rights; part-time may qualify, hours and earnings reported "
           "weekly, full-time does not; school workers case by case; file where you physically "
           "worked; unemployed through no fault of your own; the hotline (603) 271-7700, weekdays "
           "8:00 to 4:30.", NHES_FILE, READ),
     claim("Partial wage replacement for those unemployed through no fault of their own; minimum "
           "base-period earnings; totally or partially unemployed, available, able, seeking work "
           "unless exempted, filing timely claims; weekly work search with proof on the weekly "
           "claim; NHWorks offices and the hotline.", NHES_ELIG, READ),
     claim("Determinations on the dashboard with instructions to appeal; 14 calendar days from "
           "issue; an Appeal Request Notice; a hearing by an Appeal Tribunal Chairperson.",
           NHES_APPEALS, READ),
     claim("Eligible for a week only if registered for work, a claim made, able and available, and "
           "seeking work, with the exemption for a definite return date.", "RSA 282-A:31", READ),
     claim("An appeal received or postmarked within 14 calendar days after the determination was "
           "mailed, extendable for sufficient grounds.", "RSA 282-A:48", READ)],
    more="<h2>Who Can Help</h2>"
         "<p>New Hampshire Employment Security&rsquo;s unemployment hotline, (603) 271-7700, "
         "answers questions on weekdays from 8:00 a.m. to 4:30 p.m. Its NH Works offices help in "
         "person, with claims and with finding work.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{NHES_OFFICES}" target="_blank" rel="noopener">'
         "NH Works offices</a></p>")


# ---------------------------------------------------------------------------
# RUNNING FOR OFFICE. From the Secretary of State's Running for Office and
# Qualifications for Office pages, RSA 655 and RSA 669:19, and the City of
# Concord's filing page as one city's example. The fees and petition counts
# are printed because RSA 655:19-c sets them, and the Secretary of State's
# 2026 table says the same.
# ---------------------------------------------------------------------------
SOS_RUN = "https://www.sos.nh.gov/elections/running-office"
SOS_QUAL = "https://www.sos.nh.gov/elections/qualifications-office"
# A city's own page (guide_sources.OTHER), the example of a city's calendar.
CONCORD_FILE = "https://concordnh.gov/1088/Filing-for-Office"

RUN = guide(
    "run-for-office", "How to Run for Office in New Hampshire",
    "Filing to run for elected office in New Hampshire, from governor to town and city offices, "
    "step by step: who files where, the filing period, the fee or petitions, and who is eligible.",
    "To run in a party primary for a state, federal or county office, you file a declaration of "
    "candidacy in a filing period of about ten days in June of a state election year: with the "
    "Secretary of State for most offices, or with your town or city clerk if you are running for "
    "state representative. You pay a fee the law sets, or file petitions signed by voters of your "
    "party instead. Town and city offices are filed with your town or city clerk, on dates of "
    "their own.",
    [ask("Which office?",
         [("Governor, Congress, Executive Council, state senate or county",
           "File with the Secretary of State in June."),
          ("State representative", "File in June, with your town or city clerk or the Secretary of "
                                   "State."),
          ("Town or city office", "File with your town or city clerk, on its own dates.")]),
     box("Pay the fee the law sets, or file primary petitions from voters of your party instead."),
     box("Running without a party&rsquo;s primary? File a declaration of intent, the fee, and "
         "nomination papers.")],
    [step("Check that you qualify",
          "<p>To hold any elected office in New Hampshire, you must be domiciled in the state. Each "
          "office adds its own requirements:</p>"
          + table("Qualifications by office (Secretary of State, October 17, 2026)",
                  ["Office", "Age", "Also"],
                  [["Governor", "30", "Registered voter; domiciled in New Hampshire 7 years"],
                   ["U.S. senator", "30", "U.S. citizen 9 years; living in New Hampshire when elected"],
                   ["U.S. representative", "25", "U.S. citizen 7 years; living in New Hampshire when "
                    "elected"],
                   ["Executive councilor", "30", "Registered voter; domiciled in New Hampshire 7 "
                    "years; living in the district"],
                   ["State senator", "30", "Registered voter; domiciled in New Hampshire 7 years; "
                    "living in the district"],
                   ["State representative", "18", "Registered voter; domiciled in New Hampshire 2 "
                    "years; living in the town or ward"],
                   ["County officer", "18", "Registered voter in the county where you live"]]),
          actions=[("Qualifications for office", SOS_QUAL)], law=["RSA 655:2"]),
     step("File in the June filing period",
          "<p>To run in a party&rsquo;s primary you must be a registered member of that party. File "
          "a declaration of candidacy, with a statement of financial interests, between the first "
          "Wednesday in June and the Friday of the following week. In 2026 that was June 3 to June "
          "12. A filing on the last day must be made in person by the candidate, by 5 p.m.</p>"
          "<p>Candidates for governor, U.S. senator, U.S. representative, executive councilor, "
          "state senator and county office file with the Secretary of State. Candidates for state "
          "representative may file with the clerk of the town or city where they live.</p>",
          actions=[("Running for office", SOS_RUN), ("Find your town or city clerk", SOS_CLERKS)],
          law=["RSA 655:14", "RSA 655:15"]),
     step("Pay the fee, or file petitions instead",
          "<p>With your declaration, pay the fee for your office, or instead file the number of "
          "primary petitions below, each signed by a registered member of your party, together "
          "with one written assent to your candidacy.</p>"
          + table("Fees and primary petitions (RSA 655:19-c)",
                  ["Office", "Fee", "Or primary petitions"],
                  [["Governor", "$100", "200"], ["U.S. senator", "$100", "200"],
                   ["U.S. representative", "$50", "100"], ["Executive councilor", "$25", "50"],
                   ["State senator", "$10", "20"], ["County officer", "$10", "50"],
                   ["State representative", "$2", "5"]]),
          actions=[("Running for office", SOS_RUN)], law=["RSA 655:19-c"]),
     step("Running without a party's primary",
          "<p>To reach the general election ballot by another route, file a declaration of intent "
          "with the Secretary of State in the same June period, pay the same fee, and file "
          "nomination papers signed by registered voters: 3,000 for governor or U.S. senator, 1,500 "
          "from each congressional district; 1,500 for U.S. representative; 750 for executive "
          "councilor or state senator; and 150 for state representative or county officer. The "
          "papers go first to the supervisors of the checklist in each town or city, on deadlines in the "
          "summer that the Secretary of State&rsquo;s page gives.</p>",
          actions=[("Running for office", SOS_RUN)], law=["RSA 655:14-a", "RSA 655:42"]),
     step("Town and city offices",
          "<p><b>In a town</b> that uses the nonpartisan ballot, file a declaration of candidacy "
          "with the town clerk. Filing opens on the seventh Wednesday before the town election and "
          "closes on the Friday of the following week, and a filing on the last day must be made in "
          "person. Your town clerk can tell you which offices are on the ballot.</p>"
          "<p><b>In a city</b>, ask the city clerk. In Concord, for example, candidates for mayor, "
          "city council and ward offices file at the City Clerk&rsquo;s Office, from September 3 to "
          "13, 2027, for the election of November 2, 2027, with a fee or by petition.</p>",
          actions=[("Find your town or city clerk", SOS_CLERKS), ("Concord's filing page", CONCORD_FILE)],
          law=["RSA 669:19"])],
    [("Running For Office (Secretary of State)", SOS_RUN),
     ("Qualifications for Office (Secretary of State)", SOS_QUAL),
     ("Filing for Office (City of Concord)", CONCORD_FILE),
     ("Nominations, RSA 655", "/laws/655"),
     ("Town Elections, RSA 669", "/laws/669")],
    ["655", "669"],
    [claim("The qualifications for president, governor, U.S. senator, U.S. representative, "
           "executive councilor, state senator, state representative and county officer, as "
           "tabled.", SOS_QUAL, READ),
     claim("To hold any elective office in the state, a person must have a domicile in the state.",
           "RSA 655:2", READ),
     claim("A primary candidate is a registered member of the party, meets the age and domicile "
           "qualifications by the general election, and files a declaration of candidacy between "
           "the first Wednesday in June and the Friday of the following week.", "RSA 655:14", READ),
     claim("The appropriate official: the Secretary of State for governor, U.S. senator, "
           "representative in Congress, councilor, state senator and county office; the town or "
           "city clerk, or the Secretary of State, for state representative.", "RSA 655:15", READ),
     claim("2026: filing June 3-12; a declaration of candidacy with a Statement of Financial "
           "Interests and the fee, or primary petitions with an assent; last-day filings in person "
           "by 5:00 p.m.; who files with the Secretary of State and who may file with the town or "
           "city clerk; the fee and petition table; declarations of intent, the fee and nomination "
           "papers, first to the supervisors of the checklist, with the summer deadlines; the "
           "Elections Division at 603-271-3242 and elections@sos.nh.gov.", SOS_RUN, READ),
     claim("The administrative assessment for governor and U.S. senator $100, Congress $50, "
           "councilor $25, state senator $10, county officer $10, state representative $2; or "
           "primary petitions 200, 100, 50, 20, 50 and 5 with one written assent to candidacy; "
           "declarations of intent pay the assessment and file nomination papers.",
           "RSA 655:19-c", READ),
     claim("A candidate for the general election ballot other than by party primary files a "
           "declaration of intent with the Secretary of State in the same period.",
           "RSA 655:14-a", READ),
     claim("Nomination papers: 3,000, 1,500 from each congressional district, for president, U.S. "
           "senator or governor; 1,500 for U.S. representative; 750 for councilor or state senator; "
           "150 for state representative or county officer.", "RSA 655:42", READ),
     claim("In a nonpartisan-ballot town, a declaration of candidacy with the town clerk, from the "
           "seventh Wednesday to the Friday of the following week before the town election; "
           "last-day filings in person.", "RSA 669:19", READ),
     claim("Concord: mayor, ward councilor, councilor-at-large, ward moderator, ward clerk and "
           "supervisor of the checklist; filings at the City Clerk's Office, September 3 to 13, "
           "2027, for the election of November 2, 2027; a fee, or by petition until September 17, "
           "2027.", CONCORD_FILE, READ)],
    more="<h2>Who Can Help</h2>"
         "<p>The Secretary of State&rsquo;s Elections Division answers questions about filing for "
         "state and federal office at 603-271-3242 or elections@sos.nh.gov. For town and city "
         "offices, ask your town or city clerk.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_RUN}" target="_blank" rel="noopener">'
         "Running for office</a></p>",
    see=[("How to vote in New Hampshire", "/guides/how-to-vote.html"),
         ("Finding your representatives", "/learn/your-representatives.html")],
    figures=[fig("$100", "RSA 655:19-c", "For governor and United States senator, $100"),
             fig("$50", "RSA 655:19-c", "For representative to Congress, $50"),
             fig("$25", "RSA 655:19-c", "For executive councilor, $25"),
             fig("$10", "RSA 655:19-c", "For state senator, $10"),
             fig("$2", "RSA 655:19-c", "For state representative, $2")])


GUIDES += [LICENSE, CAR, REAL_ID, NEW_RESIDENT, BENEFITS, UNEMPLOYMENT, RUN]


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
