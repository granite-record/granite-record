#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.4
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
SOS_ABSENTEE = "https://www.sos.nh.gov/elections/voters/absentee-ballots"
SOS_LOOKUP = "https://app.sos.nh.gov/viphome"
SOS_CLERKS = "https://app.sos.nh.gov/clerkinformation"
SOS_POLLS = "https://app.sos.nh.gov/pollingplacesampleballot"

VOTING = guide(
    "how-to-vote", "How to Vote in New Hampshire",
    "Checking that you are registered, registering if you are not, what to bring, and "
    "where to vote, step by step, with the Secretary of State's page for each.",
    "You vote at the polling place for the town or city ward where you live. If you are not "
    "registered there yet, you can register with your town or city clerk before the election, "
    "or at the polling place on election day itself. When you register you will be asked for "
    "proof of who you are, your age, your citizenship and where you live.",
    [ask("Are you registered to vote where you live now?",
         [("Yes", "Find your polling place, then vote."),
          ("No, or not sure", "Check online. If you are not, register with your clerk before the "
                              "election, or at the polling place on election day.")]),
     box("If you are registering, bring proof of who you are, your age, your citizenship and "
         "where you live."),
     box("Vote at your polling place on election day, or by absentee ballot if you will be away "
         "or cannot go in person.")],
    [step("Check whether you are already registered",
          "<p>The Secretary of State&rsquo;s lookup tells you whether you are on the list of voters "
          "(the <em>checklist</em>) in your town, which party you are registered with, if any, and "
          "where you vote.</p><p>You can vote only in the town, or the ward of a city, where you "
          "live. If you have moved to a new town or ward, you need to register at your new address; "
          "a move within the same town or ward is an address change, made on the same form.</p>",
          actions=[("Look up your registration", SOS_LOOKUP)], law=["RSA 654:7, I"]),
     step("Make sure you can register",
          "<p>You can register if, on the day of the next election, you will be:</p><ul>"
          "<li>at least 18 years old,</li><li>a United States citizen, and</li>"
          "<li>living in the town or city where you are registering.</li></ul>"
          "<p>&ldquo;Living&rdquo; here is what the law calls your <em>domicile</em>: the one "
          "place you call home and take part in public life from. You can have only one.</p>",
          law=["RSA 654:7, I"]),
     step("Register with your clerk, or at the polls",
          "<p>There are two ways, and you can choose either:</p><ul>"
          "<li><b>Before the election</b>, at your town or city clerk&rsquo;s office during its "
          "office hours. The clerk stops taking registrations at the last meeting of the "
          "supervisors of the checklist before the election, so ask your clerk for that date.</li>"
          "<li><b>On election day</b>, at your polling place. You register, then vote at that "
          "election. If you are waiting in line to register when the polls close, you may still "
          "register and vote.</li></ul>",
          actions=[("Find your town or city clerk", SOS_CLERKS)],
          law=["RSA 654:8", "RSA 654:7-a"]),
     step("Bring proof",
          "<p>When you register you will be asked for proof of four things: your identity, your "
          "age, your citizenship and where you live.</p>",
          actions=[("What the state accepts as proof", SOS_PROOF)], law=["RSA 654:12"],
          note="<b>This has changed recently.</b> What counts as proof of citizenship, and whether "
               "a signed statement can stand in for a document, has changed since 2024 and has been "
               "decided in court. Check the Secretary of State&rsquo;s page before you go, and ask "
               "your clerk if you are unsure."),
     step("Vote",
          "<p>On election day, go to your polling place. The Secretary of State&rsquo;s lookup "
          "shows where it is and lets you see a sample ballot first.</p>"
          # Your town's polling place and clerk, from places.json (find.js).
          '<div class="yt" data-yt="vote" hidden></div>',
          actions=[("Find your polling place and sample ballot", SOS_POLLS)]),
     step("If you cannot go in person",
          "<p>You can vote by absentee ballot if, on election day, you will be away from the town "
          "where you vote, you cannot vote in person because of a disability, or a religious "
          "commitment keeps you from appearing in public. Work that keeps you from the polls the "
          "whole time they are open counts as being away, and caring for children or for adults "
          "who need care counts as work here, paid or not.</p><p>You ask your town or city clerk "
          "for the ballot, not the state.</p>",
          actions=[("Absentee ballots", SOS_ABSENTEE)], law=["RSA 657:1"])],
    [("Register to vote (Secretary of State)", SOS_REGISTER),
     ("Proof of voter registration qualifications (Secretary of State)", SOS_PROOF),
     ("Absentee ballots (Secretary of State)", SOS_ABSENTEE),
     ("Voter information lookup (Secretary of State)", SOS_LOOKUP),
     ("Town and city clerks (Secretary of State)", SOS_CLERKS),
     ("Polling places and sample ballots (Secretary of State)", SOS_POLLS),
     ("Voters and Checklists, RSA 654", "/laws/654"),
     ("Absentee Voting, RSA 657", "/laws/657")],
    ["654", "657", "659"],
    [claim("The lookup shows whether you are on the checklist, your party and where you vote.",
           SOS_LOOKUP),
     claim("You register where you are domiciled, so a move to a new town or ward means registering "
           "there; the form's own options are a new registration, a transfer, and a name or "
           "address update within the town or ward.", "RSA 654:7", "2026-10-11"),
     claim("At least 18 by the next election, a citizen, domiciled in the town or city; domicile is the "
           "one place from which you take part in democratic self-government, and only one.",
           "RSA 654:7", "2026-10-11"),
     claim("Register with the clerk in office hours, until the supervisors' last meeting before "
           "an election.", "RSA 654:8", "2026-10-11"),
     claim("Register at the polling place on election day and vote at that election; someone "
           "waiting to register when the polls close may vote if qualified.", "RSA 654:7-a", "2026-10-11"),
     claim("The Secretary of State lists every clerk.", SOS_CLERKS),
     claim("Proof of identity, age, citizenship and domicile is asked for.", "RSA 654:12", "2026-10-11"),
     claim("What counts as proof, and the affidavit, changed since 2024 and has been in court; the "
           "Secretary of State's page says what is accepted now.", SOS_PROOF),
     claim("The lookup gives the polling place and a sample ballot.", SOS_POLLS),
     claim("Absence, disability, religious observance; an employment obligation for all polling "
           "hours, including care of children and infirm adults, counts as absence.",
           "RSA 657:1", "2026-10-11"),
     claim("Absentee ballots are asked for from the town or city clerk, not the state.", SOS_ABSENTEE),
     claim("The Secretary of State's registration page is current.", SOS_REGISTER)],
    see=[("Finding your representatives", "/learn/your-representatives.html")])


# ---------------------------------------------------------------------------
# GETTING A PUBLIC RECORD. Nearly all of it is the statute, which is on this
# disk; the one thing it cannot say is whether the ombudsman's office is
# taking complaints, and the plan found it was not (October 2026). The guide
# does not say which: it sends the reader to the office's own page, which is
# checked when the laptop's copy of it is. The sample request is a template,
# not a claim: it asserts nothing about the law beyond what the steps cite.
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
          ("No", "It must say why, in writing. You can take it to Superior Court or to the "
                 "Right-to-Know ombudsman, one or the other.")])],
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
          "the ombudsman may waive. Since 2025 the ombudsman&rsquo;s office has been attached to "
          "the Office of State and Public Sector Labor Relations; before you choose this route, "
          "ask that office whether the ombudsman is taking complaints.</li></ul>",
          law=["RSA 91-A:4, IV(c)", "RSA 91-A:7", "RSA 91-A:7-a", "RSA 91-A:7-b"])],
    # THE STATUTE ALONE, FOR NOW (the person, 12 October 2026: "get at least
    # the prototype versions live"). The Department of Justice's page, the
    # Attorney General's memorandum and the ombudsman's page (RTK, RTK_MEMO,
    # OMBUDSMAN above) go back in, with their claims, once guide_sources.py's
    # copies of them have been read; until then the guide says only what the
    # statute on this disk says.
    [("Right-to-Know Law, RSA 91-A", "/laws/91-a")],
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
           "sector labor relations (2025, 141:206).", "RSA 91-A:7-a", "2026-10-12")],
    see=[("Town meeting and local government", "/learn/local-government.html")])


# ---------------------------------------------------------------------------
# HELP WITH HEATING AND ELECTRIC BILLS. "The single least-known thing in
# this whole list": the Department of Energy runs it and community action
# agencies deliver it. No amount, threshold or date is stated; the agencies'
# numbers go in only from the Department's own directory page, when its copy
# is read.
# ---------------------------------------------------------------------------
DOE_HELP = "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills"
DOE_FUEL = "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills/fuel-assistance-program"
DOE_CAA = "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills/community-action-agencies"

ENERGY = guide(
    "heating-and-electric-help", "How to Get Help With Heating and Electric Bills",
    "Where to apply for fuel assistance and help with electric bills in New Hampshire, step "
    "by step. You apply through the community action agency for your town.",
    "New Hampshire&rsquo;s fuel assistance and electric bill programs are run by the "
    "Department of Energy and delivered by local community action agencies. You apply "
    "through the agency that serves your town. If you are not sure where to start, dial 211.",
    [box("Find the community action agency that serves your town."),
     box("Contact it to apply."),
     box("The Department of Energy&rsquo;s page lists the programs and who may qualify.")],
    [step("Find your community action agency",
          "<p>Each community action agency serves its own part of the state. The Department of "
          "Energy lists them and the towns each one serves.</p>",
          actions=[("Find your agency", DOE_CAA)]),
     step("Contact the agency to apply",
          "<p>The agency takes your application for fuel assistance and for help with electric "
          "bills. If you are not sure where to start, dial 211.</p>",
          actions=[("Fuel Assistance Program", DOE_FUEL)]),
     step("Check what you may qualify for",
          "<p>The programs, and who may qualify for each, are on the Department of Energy&rsquo;s "
          "page. Amounts and income limits change every year, so read them there rather than "
          "anywhere else.</p>",
          actions=[("Help with energy and utility bills", DOE_HELP)])],
    [("Help with energy and utility bills (Department of Energy)", DOE_HELP),
     ("Fuel Assistance Program (Department of Energy)", DOE_FUEL),
     ("Community action agencies (Department of Energy)", DOE_CAA),
     ("Department of Energy, RSA 12-P", "/laws/12-p")],
    ["12-P"],
    [claim("The Department of Energy runs fuel assistance and the electric programs, delivered "
           "by community action agencies; you apply through the agency.", DOE_FUEL),
     claim("Each agency serves its own area; the Department lists them and their towns.", DOE_CAA),
     claim("211 is a place to start.", DOE_HELP),
     claim("The Department's page lists the programs and who may qualify.", DOE_HELP)])


GUIDES = [VOTING, PUBLIC_RECORD, ENERGY]


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
