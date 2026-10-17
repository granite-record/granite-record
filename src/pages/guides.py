#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.11
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


# ---------------------------------------------------------------------------
# THE GENERAL COURT'S OWN DOCUMENTS AS A SOURCE (17 October 2026). The four
# guides below were picked by the person for the soft launch of 10 November:
# how to take part in the General Court itself. What they rest on is the
# Court's own record -- the chamber rules as its journals print them, the
# notices in its calendars, its bills' own text and the tables of its
# database -- and none of that is an agency page guide_sources.py could read.
# The Court's website is never asked anything from here (the project's rule
# since its address was blocked), so each of these claims names the document
# on this disk it was read in, as a reader would find it ("House Calendar
# No. 8, January 17, 2025, p. 1"), and carries words of that document that
# state it. preflight finds those words in the document wherever it is on
# disk, the way build_civics finds a figure's words in the statute table, and
# a machine that does not hold the calendars says how many it could not read
# rather than passing them as read.
#
# A CLAIM ABOUT THIS SITE ITSELF -- that a bill's page lists its hearings --
# names the page of this site that shows or explains it, and the guide must
# link that page, so a reader can see for themselves.
#
# What these guides do NOT say, because only the General Court's website says
# it and no document on this disk does: when the House's online sign-in
# closes, how a speaker asks to be heard in each chamber, and whether the
# Senate takes sign-ins online. Testifying and Attending is linked for the
# first two; the third is left unsaid. Nor does a guide cite House Rule 44's
# requirement of a hearing on every bill, or its notice period: the adopted
# text of the current rules is not on this disk, only amendments to them
# that were tabled or failed, and an amendment's words are not the rule's
# (the fact-check of 17 October 2026).
# ---------------------------------------------------------------------------
RECORD_HOMES = ("calendars/", "calendars_senate/", "journals/", "journals_senate/",
                "legislation/", "bill_text/", "db/", "Members.txt")
READ = "2026-10-17"   # the day these documents were read for the four guides below


def record(says, cite, path, words, checked=None):
    """A claim on one of the General Court's own documents on this disk:
    `cite` names it as a reader would find it, `path` is where it is here,
    and `words` are the words of it (one string or several) that state the
    claim, matched with any run of spaces and line breaks between them."""
    c = claim(says, cite, checked)
    c.update(path=path, words=[words] if isinstance(words, str) else list(words))
    return c


def ours(says, page, checked=None):
    """A claim about this site, resting on the page of it (a path) that shows
    or explains what is claimed. The guide must link that page."""
    return claim(says, page, checked)


def links(g):
    """Every page of this site the guide links, without its #section."""
    found = ({u for _l, u in g["sources"]} | {u for _l, u in g["see"]}
             | {u for s_ in g["steps"] for _l, u in s_["actions"]}
             | set(re.findall(r'href="([^"]+)"', text(g))))
    return {u.split("#")[0] for u in found if u.startswith("/")}


def _document(path):
    """A document as it is, and its words: a saved page's with its markup
    taken off, any other file's as it is."""
    import html
    from pathlib import Path
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    if path.endswith((".html", ".htm")):
        return raw, html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return raw, raw


def _says(words, document):
    """Whether the document says the words. WORDS WITH MARKUP IN THEM ARE
    MATCHED AGAINST THE PAGE AS SAVED (17 October 2026): a claim about how a
    bill prints its changes -- which words are bold italic and which are
    plain -- is a claim about the markup, and only the markup can check it."""
    raw, words_of = document
    return re.search(r"\s+".join(map(re.escape, words.split())),
                     raw if "<" in words or "{" in words else words_of) is not None


def claim_faults(g, root="."):
    """What is wrong with the guide's record and site claims, and how many
    record claims a document on this disk confirmed: (faults, confirmed,
    absent). A document is read once, and a large table is searched as it
    is, with the words' spaces matching any whitespace, so that the House's
    100 MB sign-in table costs a second and not a copy of itself."""
    from pathlib import Path
    faults, confirmed, absent, read = [], 0, 0, {}
    for c in g["claims"]:
        if c.get("path"):
            if not c["path"].startswith(RECORD_HOMES):
                faults.append(f"{c['source']}: {c['path']} is not one of the General Court's documents")
                continue
            if not c["words"] or not all(w.strip() for w in c["words"]):
                faults.append(f"{c['source']}: no words of the document are given")
                continue
            f = Path(root) / c["path"]
            if not f.is_file():
                absent += 1
                continue
            if c["path"] not in read:
                read[c["path"]] = _document(str(f))
            gone = [w for w in c["words"] if not _says(w, read[c["path"]])]
            if gone:
                faults.append(f"{c['source']} ({c['path']}) does not say: " + "; ".join(gone))
            else:
                confirmed += 1
        elif c["source"].startswith("/") and c["source"].split("#")[0] not in links(g):
            faults.append(f"a claim rests on {c['source']}, which the guide does not link")
    return faults, confirmed, absent


# Where the documents are, and how each is cited. A journal's or calendar's
# page is the page of the PDF, which is the page it prints.
HC5 = "calendars/2025/HC005.txt"
HC8 = "calendars/2025/HC008.txt"
HC14 = "calendars/2025/HC014.txt"
HC6 = "calendars/2026/HC006.txt"
SC3 = "calendars_senate/2026/SC003.txt"
HJ2 = "journals/2025/HJ 02 January 8, 2025.txt"
SJ22 = "journals_senate/2023/SJ 01 December 7, 2022 - Organization Day.txt"
SJ24 = "journals_senate/2025/SJ 01 December 4, 2024 Organization Day.txt"
HB1001 = "legislation/2024/HB1001.html"
HB15 = "legislation/2024/HB0015.html"
HB2 = "bill_text/HB2.html"
SIGNINS = "db/houseRemoteTestify.psv"
COLUMNS = "db/_columns.json"
REPORTS = "db/CandH_Reports.psv"
VERSIONS = "db/DocumentVersion.psv"
MEMBERS = "Members.txt"
DB = "the General Court's database, as copied to this disk on September 8, 2026"
DOCS = "/calendar.html#cdocs"   # the Calendar page's Calendars & Journals: every build writes it

# The rules both chambers work under in 2025-2026, which more than one guide
# rests on. The Senate printed its rules whole on Organization Day 2022 and
# readopted them in 2024 with three changes, none to the rules cited here;
# the House's one rule cited here, 44(b), is the floor amendment Convening
# Day 2025 adopted, whose text the journal prints whole.
SENATE_RULES_KEPT = record(
    "The Senate adopted the 2023-2024 rules as its 2025-2026 rules, changing Rules 2-33, 4-7 and "
    "7-1 only.", "Senate Journal No. 1, December 4, 2024, p. 6", SJ24,
    ["RESOLVED, that the Rules of the 2023-2024 Session be adopted as the Rules of the 2025-2026 "
     "Session", "Amend Senate Rule 2-33", "Amend Senate Rule 4-7", "Amend Senate Rule 7-1"], READ)
EXEC_MAY_FOLLOW = [
    record("Senate hearing notices end a committee's list with 'executive session may follow'.",
           "Senate Calendar No. 3, January 22, 2026, pp. 25-26", SC3, "EXECUTIVE SESSION MAY FOLLOW", READ),
    record("House Rule 44(b), as amended and adopted January 8, 2025: an executive session may be "
           "held without further notice immediately after a duly noticed public hearing, with the "
           "chair's and ranking member's concurrence.", "House Journal No. 2, January 8, 2025, p. 20",
           HJ2, ["Executive Sessions may also be held without further notice if held immediately after "
                 "the close of a duly noticed public hearing",
                 "amendment to House Rule 44 (b) was adopted"], READ)]


# ---------------------------------------------------------------------------
# ATTENDING AND SPEAKING AT A PUBLIC HEARING (17 October 2026). Testifying
# and Attending explains hearings at length; this is the same ground as a
# sequence of things to do, and it links that page for what it already says
# well -- the buildings, and how each chamber takes a request to speak.
# ---------------------------------------------------------------------------
HEARING = guide(
    "attend-a-hearing", "How to Attend and Speak at a Public Hearing",
    "Finding a bill's public hearing, going in person or watching it, and asking to speak, "
    "step by step, with what happens after.",
    "Committees of the House and of the Senate hold public hearings on bills, and the "
    "Senate&rsquo;s rules require one on every bill sent to a committee. You may attend and "
    "testify. Find the hearing in the chamber&rsquo;s "
    "calendar or on the bill&rsquo;s page here, go to the room the notice names or watch the "
    "live stream, and tell the committee you want to speak. If you cannot go, you can send "
    "your position in writing instead.",
    [box("Find the hearing: the committee, the room, the day, and the time for your bill."),
     ask("Can you go in person?",
         [("Yes", "Go to the room, and tell the committee you want to speak."),
          ("No", "Watch the live stream, and send your position in writing.")]),
     box("Afterward, the committee votes on what to recommend, sometimes the same day.")],
    [step("Find the hearing",
          "<p>A hearing is announced in the calendar of the chamber holding it. The notice names "
          "the committee, the building and room, the day, and a time for each bill. The House "
          "lists its hearings under Committee Meetings in the House Calendar, and the "
          "Senate&rsquo;s rules require at least 4 days&rsquo; notice in the Senate "
          "Calendar.</p>"
          "<p>On this site, a bill&rsquo;s page lists its hearings with the day, time and room, "
          "and the Calendar shows the week&rsquo;s hearings by committee. Follow on a "
          "bill&rsquo;s page gives you its new actions as they are recorded, and the site keeps a "
          "feed of hearings coming up as well.</p>",
          actions=[("This week's hearings", "/calendar.html"), ("Find a bill", "/bills.html")]),
     step("Decide how to take part",
          "<p>Legislative committee meetings, executive sessions included, are open to the "
          "public, with narrow exceptions in the law, and anyone may record them. You can:</p><ul>"
          "<li><b>go in person</b>, to the building and room the notice names. Testifying and "
          "Attending explains the buildings;</li>"
          "<li><b>watch</b>: the House and the Senate live stream their standing "
          "committees&rsquo; hearings, and a bill&rsquo;s page here links the recording where "
          "there is one; or</li>"
          "<li><b>send your position in writing</b>, with or without going: online for a House "
          "hearing, or by email to the committee.</li></ul>",
          actions=[("The buildings", "/learn/testifying.html#s-how-hearings-are-announced"),
                   ("Submit testimony", "/guides/submit-testimony.html")],
          law=["RSA 91-A:1-a, VI(a)", "RSA 91-A:2, II"]),
     step("Ask to speak",
          "<p>Tell the committee you want to speak when you arrive. The House and the Senate each "
          "ask for it their own way, and Testifying and Attending explains both. When the chair "
          "calls you, say who you are, where you live and whether you speak for an "
          "organization, then whether you support or oppose the bill, and why. The most useful "
          "testimony is specific: what the bill would do to you, in your town.</p>",
          actions=[("Speaking at the hearing", "/learn/testifying.html#s-speaking-at-the-hearing")]),
     step("After the hearing",
          "<p>The committee votes on what to recommend at an executive session, which you may "
          "watch. It can follow the hearing directly: Senate notices often say so, and a House "
          "committee may hold one right after a noticed hearing. The recommendation, such as "
          "Ought to Pass or Inexpedient to Legislate, goes to the full chamber. If the bill "
          "passes, a committee of the other chamber holds its own hearing on it.</p>"
          "<p>In the Senate, the committee&rsquo;s hearing report lists who supported, opposed "
          "or was neutral on the bill and summarizes the testimony.</p>",
          actions=[("How a bill becomes law", "/learn/how-a-bill-becomes-law.html")])],
    [("House Calendars No. 8 (2025) and No. 6 (2026), Senate Calendar No. 3 (2026), House Journal "
      "No. 2 (2025) and Senate Journals No. 1 (2022 and 2024): open them from the Calendar's "
      "Calendars & Journals", DOCS),
     ("Testifying and Attending", "/learn/testifying.html"),
     ("Right-to-Know Law, RSA 91-A", "/laws/91-a")],
    ["91-A"],
    [record("Senate Rule 4-1: a hearing on each bill referred to a committee, advertised at least 4 "
            "days before in the Senate Calendar.", "Senate Journal No. 1, December 7, 2022, p. 21",
            SJ22, "A hearing shall be held upon each bill or resolution referred to a committee, and "
                  "notice of such hearing shall be advertised at least 4 days before such hearing in "
                  "the Senate Calendar", READ),
     SENATE_RULES_KEPT,
     record("The House Calendar lists House public hearings on bills under Committee Meetings, each "
            "notice giving the committee, the room and building, and a time for each bill.",
            "House Calendar No. 6, February 6, 2026, p. 22", HC6,
            ["COMMITTEE MEETINGS", "STATE-FEDERAL RELATIONS AND VETERANS AFFAIRS, Room 228, GP "
             "9:00 a.m. Continued public hearing on HB 1287"], READ),
     record("A Senate notice gives the committee, the room and building, its members and a time for "
            "each bill.", "Senate Calendar No. 3, January 22, 2026, p. 25", SC3,
            ["COMMERCE, Room 100, SH", "9:45 a.m. SB 482-FN"], READ),
     record("Legislators and citizens may submit testimony online for bills coming up for a House "
            "public hearing.", "House Calendar No. 8, January 17, 2025, p. 1", HC8,
            "Legislators and citizens are reminded of the availability to submit testimony online for "
            "bills coming up for a public hearing", READ),
     record("All onsite public meetings of House standing committees are livestreamed and archived.",
            "House Calendar No. 8, January 17, 2025, p. 1", HC8,
            "All onsite public meetings of standing committees are livestreamed and archived", READ),
     record("All Senate standing committee hearings are livestreamed.",
            "Senate Calendar No. 3, January 22, 2026, p. 1", SC3,
            "All Standing Committee hearings will be livestreamed on the NH Senate's YouTube channel",
            READ),
     claim("The general court, including executive sessions of committees, is a public body.",
           "RSA 91-A:1-a", READ),
     claim("All meetings are open to the public, subject to RSA 91-A:3; any person may use recording "
           "devices.", "RSA 91-A:2", READ),
     ours("A bill's page lists each hearing with its day, time and room, and the recording where "
          "there is one; Follow gives a bill's feed; there is a feed of hearings coming up.",
          "/learn/using-this-site.html", READ),
     ours("The Calendar shows the week's hearings by committee.", "/calendar.html", READ),
     ours("The buildings the notices name; the chambers take requests to speak differently; the "
          "most useful testimony is concrete.", "/learn/testifying.html", READ),
     ours("A bill that passes is referred to a committee of the second chamber, which holds its own "
          "public hearing.", "/learn/how-a-bill-becomes-law.html", READ)]
    + EXEC_MAY_FOLLOW
    + [record("Senate Rule 4-2: every bill is reported out with a recommendation, among them ought to "
              "pass and inexpedient to legislate.", "Senate Journal No. 1, December 7, 2022, p. 21",
              SJ22, "All bills and resolutions in the possession of committees shall be reported out "
                    "with one of the following recommendations: ought to pass, ought to pass with "
                    "amendment, rerefer to committee, inexpedient to legislate", READ),
       record("A Senate hearing report lists who supports, opposes and is neutral on the bill, and "
              "summarizes the testimony.", "Senate committee hearing reports (CandH_Reports), " + DB,
              REPORTS, ["Who supports the bill", "Who opposes the bill", "Who is neutral on the bill",
                        "Summary of testimony presented in support"], READ)],
    see=[("Testifying and attending", "/learn/testifying.html"),
         ("How to submit testimony online or in writing", "/guides/submit-testimony.html"),
         ("How to contact your legislators", "/guides/contact-your-legislators.html"),
         ("Using this site", "/learn/using-this-site.html")])


# ---------------------------------------------------------------------------
# SUBMITTING TESTIMONY ONLINE OR IN WRITING (17 October 2026). The House's
# online form is described from the House's own records of it: the calendar
# notices that name it and say where its submissions go, and the columns and
# choices of the sign-in table in the Court's database. No name or word of
# anyone's testimony is read into this file or printed by the guide; the
# words checked are the form's own choices.
# ---------------------------------------------------------------------------
TESTIMONY = guide(
    "submit-testimony", "How to Submit Testimony Online or in Writing",
    "Registering your position on a bill and sending a committee written testimony without "
    "going to Concord, and when to send it.",
    "For a House hearing, you can sign in online to say whether you support or oppose a bill, "
    "and attach written testimony. For a hearing in either chamber, you can email the "
    "committee&rsquo;s members. Send it before the hearing: committee members receive the "
    "online testimony at the end of each hearing day, and a committee may vote as soon as its "
    "hearing ends.",
    [box("Find the hearing: which committee, and which day."),
     box("A House hearing: sign in online, for or against, with written testimony if you wish."),
     box("Any hearing: email the committee&rsquo;s members from its page here."),
     box("Send it before the hearing. The committee may vote the same day.")],
    [step("Find the hearing",
          "<p>Open the bill&rsquo;s page here: it lists each hearing with the committee, the day "
          "and the time. The Calendar shows the week&rsquo;s hearings.</p>",
          actions=[("Find a bill", "/bills.html"), ("This week's hearings", "/calendar.html")]),
     step("Sign in online for a House hearing",
          "<p>The House&rsquo;s Sign-in Form and Online Testimony Submission is on the General "
          "Court&rsquo;s website, and Testifying and Attending links it. Each sign-in is for one "
          "bill at one committee&rsquo;s hearing on one day. Among other things, it asks "
          "for:</p><ul>"
          "<li>your name, town and state;</li>"
          "<li>who you are, such as a member of the public, an elected official, a lobbyist or "
          "state agency staff, and whom you represent, if anyone; and</li>"
          "<li>whether you support the bill, oppose it, or are neutral.</li></ul>"
          "<p>You may attach written testimony, or sign in without it: a sign-in for or against is "
          "part of the record and is counted. What you submit goes to the committee&rsquo;s "
          "members. This site publishes only how many people signed in supporting, opposing and "
          "neutral, never names or written testimony.</p>",
          actions=[("Where to sign in", "/learn/testifying.html#sources")]),
     step("Write it so it is useful",
          "<p>Start with the bill&rsquo;s number, HB or SB and then the number, and say whether "
          "you support or oppose it. Then say why in a few specific sentences: what the bill "
          "would do to you, your family, your work or your town. If you write for an "
          "organization, say so.</p>"),
     step("Send it before the hearing",
          "<p>Committee members can read what is submitted online in the House&rsquo;s portal, "
          "bill by bill, and are sent links to it at the end of each day their committee holds "
          "hearings. A committee can vote as soon as its hearing "
          "ends: Senate notices often say &ldquo;executive session may follow&rdquo;, and a House "
          "committee may meet in executive session straight after a noticed hearing. So send "
          "your testimony before the hearing, as soon as you can once it is scheduled.</p>"),
     step("Or email the committee",
          "<p>Every committee&rsquo;s page here lists its members and has a button that opens "
          "one email to all of them. Put the bill&rsquo;s number in the subject line. It works for "
          "a House or a Senate committee, and for a bill whose hearing has passed but whose "
          "committee has not yet voted.</p>",
          actions=[("Committees", "/committees.html")])],
    [("House Calendars No. 8 and No. 14 (2025), House Journal No. 2 (2025) and Senate Calendar "
      "No. 3 (2026): open them from the Calendar's Calendars & Journals", DOCS),
     ("Testifying and Attending", "/learn/testifying.html")],
    [],
    [ours("A bill's page lists each hearing with the committee, day and time.",
          "/learn/using-this-site.html", READ),
     ours("The Calendar shows the week's hearings.", "/calendar.html", READ),
     record("The House's online form is its House Sign-in Form and Online Testimony Submission, on "
            "the General Court website, for bills coming up for a public hearing.",
            "House Calendar No. 8, January 17, 2025, p. 1", HC8,
            "submit testimony online for bills coming up for a public hearing using our House Sign-in "
            "Form and Online Testimony Submission on the General Court website", READ),
     ours("Testifying and Attending links the House online testimony sign-in; a sign-in for or "
          "against is part of the record and counted; specific testimony is the most useful; this "
          "site publishes the counts, not names or written testimony.", "/learn/testifying.html", READ),
     record("Each sign-in records a hearing date, a committee and a bill; name, town and state; who "
            "the person is, whom they represent, their position; and any testimony text.",
            "The House's online sign-ins (houseRemoteTestify), its columns, " + DB, COLUMNS,
            '"CommitteeDate", "committeeID", "legislationID", "whoIsName", "Expr1", "representing", '
            '"Town", "State", "nonGermane", "Expr2_bytes", "TestimonyText"', READ),
     record("Who the person is: a member of the public, an elected official, a lobbyist or state "
            "agency staff, among others; position: support, oppose or neutral.",
            "The House's online sign-ins (houseRemoteTestify), " + DB, SIGNINS,
            ["A Member of the Public|support|", "A Member of the Public|oppose|", "|neutral|",
             "|An Elected Official|", "|A Lobbyist|", "|State Agency Staff|"], READ),
     record("Testimony submitted online goes to the committee: its members view submissions by "
            "committee and bill, and are emailed links at the end of each day it holds hearings.",
            "House Calendar No. 14, February 28, 2025, p. 1", HC14,
            ["choose your Committee from the drop-down list, and choose the bills you wish to view "
             "submissions on",
             "Emails containing links to testimony your committee receives through the online portal "
             "will be sent at the end of the days your committee has hearings"], READ),
     record("Bills are numbered by type, and a Senate bill is marked Senate Bill.",
            "Senate Journal No. 1, December 7, 2022, p. 19", SJ22,
            "shall be numbered serially according to the type of bill or resolution", READ)]
    + EXEC_MAY_FOLLOW
    + [ours("Every committee page lists its members and has a button that opens an email to all of "
            "them at once.", "/learn/your-representatives.html", READ)],
    see=[("Testifying and attending", "/learn/testifying.html"),
         ("How to attend and speak at a public hearing", "/guides/attend-a-hearing.html"),
         ("How to contact your legislators", "/guides/contact-your-legislators.html"),
         ("Using this site", "/learn/using-this-site.html"),
         ("Finding your representatives", "/learn/your-representatives.html")])


# ---------------------------------------------------------------------------
# CONTACTING YOUR LEGISLATORS (17 October 2026). Who represents a reader is
# the statute's (RSA 662) and the town finder's; how to reach them is the
# member list the General Court publishes, which every senator fills with a
# Concord office and most representatives with an email address. The advice
# on what to write is the procedure's own logic -- a member represents a
# district of towns, votes on a numbered bill and on a committee's
# recommendation -- and not anybody's view of what persuades.
# ---------------------------------------------------------------------------
CONTACT = guide(
    "contact-your-legislators", "How to Contact Your Legislators",
    "Finding who represents you in the New Hampshire House and Senate, choosing between email "
    "and a call, and writing a message a legislator can act on.",
    "You have one state senator and one or more state representatives, set by the town or "
    "city ward you live in. Find them by your town here: each member&rsquo;s page gives the "
    "email address and phone number they list with the General Court. Say where you live, "
    "name the bill by its number, say how you want them to vote, and send it before the "
    "vote.",
    [box("Find who represents your town: one senator, and one or more representatives."),
     box("Choose email or a call. Senators list an office in Concord; most representatives list "
         "an email address."),
     box("Say where you live, name the bill, and say how you want them to vote, before the vote.")],
    [step("Find who represents you",
          "<p>Every town and city ward is in one of 24 Senate districts, each electing one "
          "senator, and in a House district, which may elect several representatives. Some are "
          "also in a floterial district laid over their own, which elects more. Choose your town "
          "to see them all.</p>"
          # Your town's districts and members, from places.json (find.js).
          '<div class="yt" data-yt="reps" hidden></div>',
          actions=[("Find your town", "/officials.html#my-town")],
          law=["RSA 662:3", "RSA 662:5"]),
     step("Find how to reach them",
          "<p>A member&rsquo;s page here, and your town&rsquo;s page, give the email address and "
          "phone number the member lists with the General Court. Senators list an office in "
          "Concord with its phone number. Most representatives list an email address, and many "
          "a phone number. To write to every member of a committee at once, use the button on "
          "the committee&rsquo;s page.</p>",
          actions=[("Committees", "/committees.html")]),
     step("Choose email or a call",
          "<p><b>Email</b> reaches nearly every member, gives them your words exactly, and can go "
          "to a whole committee at once. <b>A call</b> is quicker when a vote is close, to a "
          "member who lists a number. Either way, keep to one bill.</p>"),
     step("Say what you are asking",
          "<ul><li><b>Say where you live.</b> Each member represents the towns and wards of a "
          "district, so your town tells them you are a constituent.</li>"
          "<li><b>Name the bill by its number</b>, HB or SB and then the number.</li>"
          "<li><b>Say how you want them to vote.</b> The chamber votes on its committee&rsquo;s "
          "recommendation, such as Ought to Pass or Inexpedient to Legislate.</li>"
          "<li><b>Say why</b>, in a few sentences, from what it would mean for you or your "
          "town.</li></ul>"),
     step("Send it before the vote",
          "<p>Write to a committee before its executive session, where it votes on its "
          "recommendation, and to your own members before the vote of the full House or Senate. "
          "Each chamber&rsquo;s calendar lists the committee meetings and prints the "
          "committees&rsquo; reports on the bills coming to a vote.</p>",
          actions=[("This week's calendar", "/calendar.html")])],
    [("Every sitting legislator, from the General Court's member list (Granite Record)", "/officials.html"),
     ("Representatives and senators' districts, RSA 662", "/laws/662"),
     ("Finding Your Representatives", "/learn/your-representatives.html"),
     ("House Calendar No. 6 (2026) and Senate Journal No. 1 (2022): open them from the Calendar's "
      "Calendars & Journals", DOCS)],
    ["662"],
    [claim("The state is divided into 24 senatorial districts, each electing one senator.", "RSA 662:3", READ),
     claim("The state is divided into districts for state representatives, each electing the number "
           "set forth opposite it.", "RSA 662:5", READ),
     ours("A floterial district is laid over two or more House districts and elects additional "
          "members; a town's page and the town finder name its districts and members; committee "
          "pages have a button that emails all their members.", "/learn/your-representatives.html", READ),
     ours("My Town shows who represents a town; a member's page and a town's page give the email and "
          "phone the member lists.", "/officials.html", READ),
     record("The General Court's member list carries each member's address, phone and email. Read on "
            "October 17, 2026: every senator a State House or State House Annex office and phone; "
            "of the 366 sitting representatives (the 18 rows marked Former left out), 364 an email "
            "address and 227 a phone number.",
            "The General Court's member list (Members.txt), as taken on this disk", MEMBERS,
            "Address address2 city Zipcode State Phone WorkEmail", READ),
     record("Bills are numbered by type, and a Senate bill is marked Senate Bill.",
            "Senate Journal No. 1, December 7, 2022, p. 19", SJ22,
            ["shall be numbered serially according to the type of bill or resolution",
             'Each bill shall be marked on the first page "Senate Bill"'], READ),
     record("Senate Rule 4-2: every bill is reported out with a recommendation, among them ought to "
            "pass and inexpedient to legislate.", "Senate Journal No. 1, December 7, 2022, p. 21",
            SJ22, "shall be reported out with one of the following recommendations: ought to pass", READ),
     SENATE_RULES_KEPT,
     record("A House calendar holds the committee reports and the week's committee meetings, among "
            "them reports of Ought to Pass with Amendment.", "House Calendar No. 6, February 6, 2026, "
            "pp. 1, 5 and 22", HC6, ["Contains: Amendments; Committee Reports", "OUGHT TO PASS WITH "
                                     "AMENDMENT", "COMMITTEE MEETINGS"], READ),
     record("Senate Rule 4-4: the list of bills with the committee's report is published in the "
            "Senate Calendar for the day of action.", "Senate Journal No. 1, December 7, 2022, p. 21",
            SJ22, "a list of such bills and resolutions with the report of the committee thereon shall "
                  "be published in the senate calendar for the day on which action shall be taken",
            READ),
     ours("The Calendar lists the week's committee meetings.", "/calendar.html", READ)],
    see=[("Finding your representatives", "/learn/your-representatives.html"),
         ("How to submit testimony online or in writing", "/guides/submit-testimony.html"),
         ("How to attend and speak at a public hearing", "/guides/attend-a-hearing.html")])


# ---------------------------------------------------------------------------
# READING A BILL (17 October 2026). Every statement about a bill's layout is
# read off real bills' own pages as the General Court published them: HB 1001
# of 2024 as introduced, for the parts and the marking of changes, chosen
# because it is short and its change is plain to see; a fiscal note's parts
# from an introduced bill that carries one. What the letters and the note
# are for is RSA 14:44-48.
#
# REGULAR TYPE IS NOT ONLY "ALL NEW" (the fact-check of 17 October 2026).
# The bill's own note says regular type is matter all new or repealed and
# reenacted, and the first draft said only that; but in a paragraph being
# amended, the words kept from current law are regular type too, with the
# additions in bold italics -- HB 1001's first section is exactly that. So
# the guide says both, and the claim is checked against the saved page's
# markup, where the plain and the bold italic runs are two styles.
# ---------------------------------------------------------------------------
READ_BILL = guide(
    "read-a-bill", "How to Read a Bill",
    "The parts of a New Hampshire bill, how its text marks what it adds to the law and what it "
    "removes, what amendments and fiscal notes are, and what the letters after its number mean.",
    "A bill is a set of changes to the state&rsquo;s laws. Its first page gives its title, "
    "sponsors and committee, and a short analysis. Each section then says which law it changes. "
    "Where it rewrites part of a law, regular type is the law as it stands, words in "
    "<b><i>bold italics</i></b> are being added, and words [<s>in brackets and struck "
    "through</s>] are being removed; a section that is all new is printed wholly in regular "
    "type. Letters after the number flag money: FN means a fiscal note is attached, and LOCAL "
    "that local governments&rsquo; spending or revenue may be affected.",
    [box("The first page: the number and its letters, the title, the sponsors, the committee and "
         "the analysis."),
     box("The sections: each changes a law. Regular type is the law as it stands, bold italics "
         "are added, [<s>struck</s>] words removed; an all-new section is wholly regular type."),
     ask("Has the bill been amended?",
         [("Yes", "Read the latest version, and each amendment for what it changed."),
          ("No", "The text as introduced is the current one.")]),
     box("FN after the number? The fiscal note after the text estimates the cost.")],
    [step("Start with the number and its letters",
          "<p>The number says which chamber the bill began in: HB for a House bill, SB for a "
          "Senate bill. Letters after the number flag money:</p><ul>"
          "<li><b>FN</b>: the bill carries a fiscal note, an estimate of its cost, printed after "
          "its text.</li>"
          "<li><b>LOCAL</b>: the bill may affect what local governments spend, or require the "
          "state to pass revenue on to cities and towns.</li></ul>"
          "<p>The other letters are explained under Reading the Shorthand.</p>",
          actions=[("Reading the shorthand", "/learn/using-this-site.html#s-reading-the-shorthand")],
          law=["RSA 14:48"]),
     step("Find its request number",
          "<p>Before a bill has a number it is a Legislative Service Request, or LSR: a "
          "legislator&rsquo;s request, which the Office of Legislative Services drafts into a "
          "bill. When the bill is introduced it gets its number, and its text keeps the "
          "request&rsquo;s number near the top: HB 1001 of 2024 prints 24-2288, the "
          "session&rsquo;s year and then the request&rsquo;s own number. While requests for the "
          "next session are being filed, this site&rsquo;s bill search lists them by title and "
          "prime sponsor.</p>",
          actions=[("Search bills and requests", "/bills.html")]),
     step("Read the first page",
          "<p>The first page gives the bill&rsquo;s title, which begins &ldquo;AN ACT&rdquo;; its "
          "sponsors, each with their district; the committee it was sent to; and an "
          "<b>analysis</b>, a short summary of what it does. A bill that has been amended carries "
          "an amended analysis.</p>"),
     step("Read what it changes",
          "<p>After the words &ldquo;Be it Enacted by the Senate and House of Representatives in "
          "General Court convened&rdquo;, each numbered section names the law it changes, such as "
          "&ldquo;Amend RSA 72:23-c, I to read as follows&rdquo;, and prints that law as it would "
          "read. The type shows what changes:</p><ul>"
          "<li>In a section that rewrites part of a law, <b>regular type</b> is the law as it "
          "stands, <b><i>bold italics</i></b> are words being added, and [<s>brackets, struck "
          "through</s>] are words being removed. In HB 1001 of 2024, the first section prints a "
          "paragraph of current law in regular type with one phrase in bold italics: the "
          "addition.</li>"
          "<li>A section that is all new, or repealed and written again, is printed wholly in "
          "regular type, as a note on the first page says.</li></ul>"
          "<p>The last section says when the change would take effect. To read a law as it "
          "stands now, look it up in Laws.</p>",
          actions=[("Laws", "/laws.html")]),
     step("Check for amendments",
          "<p>A committee or a member can propose an amendment: a separate document with its own "
          "number, such as 2026-0176s, that says what to replace in the bill, from one paragraph "
          "to everything after the enacting clause. A committee&rsquo;s amendment is printed in "
          "the calendar with its report, before the chamber votes on it. Once a chamber adopts "
          "amendments, the bill is printed again as amended by the House or the Senate, and the "
          "text both chambers pass is published as the final version.</p>"
          "<p>On a bill&rsquo;s page here, the Bill Text tab shows the text and its "
          "amendments.</p>"),
     step("Read the fiscal note",
          "<p>With some exceptions, such as the budget bills, a bill that would change what the "
          "state, a county, a city or a town spends or collects carries a fiscal note. If the "
          "effect is $10,000 or more in each fiscal year the note covers, the note sets out the "
          "estimate; if less, it says so. The Office of Legislative Budget Assistant prepares it "
          "and names its sources, and the note is corrected to match the bill as it is "
          "amended.</p>"
          "<p>The note marks whether the state, counties or local governments are affected, "
          "estimates the change in appropriations, revenue and spending by fiscal year, and "
          "explains how under Methodology. An effect it cannot put a number on may be called "
          "indeterminable.</p>",
          law=["RSA 14:44", "RSA 14:46", "RSA 14:47"])],
    [("HB 1001 of 2024 (Granite Record)", "/bill/2024/hb1001.html"),
     ("House Calendars No. 5 (December 27, 2024) and No. 6 (2026), Senate Calendar No. 3 (2026) "
      "and Senate Journal No. 1 (2022): open them from the Calendar's Calendars & Journals", DOCS),
     ("Legislative Officers and Proceedings, RSA 14", "/laws/14"),
     ("Using This Site", "/learn/using-this-site.html")],
    ["14"],
    [record("HB 1001 of 2024 is marked House Bill and prints its LSR number, 24-2288, under the "
            "session's year.", "HB 1001 of 2024, as introduced", HB1001,
            ["2024 SESSION 24-2288", "HOUSE BILL 1001"], READ),
     record("Bills are numbered by type, and a Senate bill is marked Senate Bill.",
            "Senate Journal No. 1, December 7, 2022, p. 19", SJ22,
            'Each bill shall be marked on the first page "Senate Bill"', READ),
     record("A bill whose number carries FN prints a fiscal note after its text, headed with that "
            "number.", "HB 15-FN of 2023, as introduced", HB15,
            ["HOUSE BILL 15-FN", "HB 15-FN- FISCAL NOTE"], READ),
     claim("LOCAL is placed after the number of bills and amendments which may impact local "
           "expenditures or require the state to forward designated revenues to cities or towns.",
           "RSA 14:48", READ),
     ours("Reading the Shorthand explains the letters after a bill's number; the Bill Text tab shows "
          "the text and its amendments.", "/learn/using-this-site.html", READ),
     record("The Office of Legislative Services prepares the bills to be introduced.",
            "Senate Journal No. 1, December 7, 2022, p. 19", SJ22,
            "shall be delivered or caused to be delivered to the Office of Legislative Services, who "
            "shall prepare the items in proper form", READ),
     record("The House calls the requests LSRs: the last day to sign off on them.",
            "House Calendar No. 5, December 27, 2024, p. 2", HC5,
            "Last day to sign-off on all LSRs", READ),
     SENATE_RULES_KEPT,
     ours("While requests for the next session are being filed, the bill search lists them by title "
          "and prime sponsor.", "/bills.html", READ),
     record("The first page: the title beginning AN ACT, the sponsors with their districts, the "
            "committee and the analysis.", "HB 1001 of 2024, as introduced", HB1001,
            ["AN ACT relative to exempting", "SPONSORS: Rep. Packard, Rock. 16",
             "COMMITTEE: Municipal and County Government", "ANALYSIS This bill adds"], READ),
     record("An amended bill carries an amended analysis.", "HB 2 of 2025, final version", HB2,
            "AMENDED ANALYSIS", READ),
     record("The enacting clause; a section naming the law it amends; the explanation of bold "
            "italics, brackets and regular type; the effective date.", "HB 1001 of 2024, as introduced",
            HB1001, ["Be it Enacted by the Senate and House of Representatives in General Court convened",
                     "Amend RSA 72:23-c, I to read as follows",
                     "Matter added to current law appears in bold italics",
                     "Matter removed from current law appears [ in brackets and struckthrough",
                     "Matter which is either (a) all new or (b) repealed and reenacted appears in "
                     "regular type", "This act shall take effect"], READ),
     record("In a paragraph being amended, the words kept from current law are regular type and the "
            "addition bold italic: section 1 reprints RSA 72:23-c, I in the plain style with only "
            "'Masonic lodge or Masonic association,' in the bold italic one, as the page's own "
            "styles define them.", "HB 1001 of 2024, as introduced, section 1", HB1001,
            ['charitable organization, Grange, </span><span class="cs22FF6315">Masonic lodge or '
             'Masonic association, </span><span class="csDD5E5F52">the Veterans of Foreign Wars',
             ".cs22FF6315{color:#000000;background-color:transparent;font-family:'Century "
             "Schoolbook';font-size:10pt;font-weight:bold;font-style:italic;}",
             ".csDD5E5F52{color:#000000;background-color:transparent;font-family:'Century "
             "Schoolbook';font-size:10pt;font-weight:normal;font-style:normal;}"], READ),
     record("An amendment has its own number and says what to replace, a subparagraph or all after "
            "the enacting clause.", "Senate Calendar No. 3, January 22, 2026, pp. 13 and 25", SC3,
            ["2026-0176s", "Amend the bill by replacing all after the enacting clause with the following",
             "Amend subparagraph I(b) as inserted by section 2 of the bill by replacing it with the "
             "following"], READ),
     record("Senate Rule 3-15: amendments are in writing, with the senator's name or, for a committee "
            "amendment, the committee's.", "Senate Journal No. 1, December 7, 2022, p. 20", SJ22,
            "or in the case of a committee amendment the name of the committee that recommended it", READ),
     record("Senate Rule 4-4: a committee's amendment is printed in the Senate Calendar on the day its "
            "report is listed for action.", "Senate Journal No. 1, December 7, 2022, p. 21", SJ22,
            "The amendment shall be printed in the senate calendar on the date that the report is "
            "listed for action", READ),
     record("A House calendar carries amendments, committee reports and revised fiscal notes.",
            "House Calendar No. 6, February 6, 2026, p. 1", HC6,
            ["Contains: Amendments; Committee Reports", "Revised Fiscal Notes"], READ),
     record("A bill's text is published as introduced, as amended by the House, as amended by the "
            "Senate, as the version adopted by both bodies, and as the final version.",
            "Document versions (DocumentVersion), " + DB, VERSIONS,
            ["|Introduced|", "|As Amended by the House|", "|As Amended by the Senate|",
             "|Version adopted by both bodies|", "|FINAL VERSION|"], READ),
     claim("A fiscal note for bills with a total fiscal impact of $10,000 or more a year on the state, "
           "a city, town or county; a note saying so below that; none for budget bills, among other "
           "exceptions.", "RSA 14:44", READ),
     claim("The legislative budget assistant prepares fiscal notes and identifies the sources of the "
           "data.", "RSA 14:46", READ),
     claim("The fiscal note accompanies the bill and is amended to correct errors or agree with "
           "substantive amendments.", "RSA 14:47", READ),
     record("A fiscal note marks the state, county or local impact, estimates appropriation, revenue "
            "and expenditures by fiscal year, explains its methodology, and may find an effect "
            "indeterminable.", "HB 15-FN of 2023, as introduced, its fiscal note", HB15,
            ["FISCAL IMPACT:", "Estimated Increase / (Decrease)", "Appropriation", "Revenue",
             "Expenditures", "METHODOLOGY:", "Indeterminable Decrease", "AGENCIES CONTACTED:"], READ)],
    see=[("Reading the shorthand", "/learn/using-this-site.html#s-reading-the-shorthand"),
         ("How a bill becomes law", "/learn/how-a-bill-becomes-law.html"),
         ("Glossary", "/learn/glossary.html"),
         ("How to contact your legislators", "/guides/contact-your-legislators.html")],
    figures=[fig("$10,000", "RSA 14:44", "total fiscal impact of $10,000 or more")])

CIVIC = [HEARING, TESTIMONY, CONTACT, READ_BILL]


GUIDES = [VOTING, PUBLIC_RECORD, ENERGY, VITAL, ABATEMENT, LMI] + CIVIC


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
