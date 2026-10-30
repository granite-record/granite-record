#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.66
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

OBSERVED PRACTICE IS A SOURCE OF ITS OWN KIND (17 October 2026). How a
hearing runs in the room -- the House's pink cards, a chair's time limit, the
last call before the hearing closes, a meeting that starts late -- is written
in no rule or notice on this disk, and the person, who attends hearings and
session days, set it down first-hand. Such a claim is an observed() one: it
carries the label OBSERVED, never a document's name; the guide shows it to
readers as practice, by saying "in practice" and by naming OBSERVED under
Where This Comes From; and it may never state a fee, a deadline or any other
requirement of law, or a number of seats, which only a statute, a rule or an
official count can support. Where an official document says the same thing,
the guide cites the document instead -- the Senate's own guidance for the
public, saved in records/sources/, confirms its online sign-in and its
sign-up sheets, so those are record() claims and only the box on the sheet
for speaking is observed.

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

# The General Court's addresses are civics.py's, the one file that holds them
# (17 October 2026): a guide that links the chambers' sign-in forms takes them
# from there rather than writing them a second time.
import civics


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

# A COUNT IS A FIGURE TOO (23 October 2026, approved by the person that day).
# FIGURE caught dollars and percentages only, so "5 business days", "60 days"
# and "24 Senate districts" were printed with nothing holding them to the
# sections that set them. COUNT is a number with a unit a law counts in --
# days, weeks, months, years, hours, minutes, an age, districts, seats,
# members -- and every one a guide prints is declared as a fig(), as a dollar
# amount is. A date ("March 1"), a year ("since 1997"), a time ("5 p.m."), a
# phone number, a form's number ("DSMV 450") or a bill's carries no such unit
# and is not one.
#
# WHERE A COUNT MAY REST. On a statute, its words found in this build's table
# (build_civics.guide_ready), as a dollar amount's are; on a record() claim of
# the guide, its words among the words that claim_faults finds in the
# General Court's own document; or on a checked claim of the guide on an
# agency's page, its words in what that claim records the page as saying. The
# last is the weakest: nothing on this disk reads an agency's page, so such a
# count is as good as the claim's date, and goes stale with the guide. It is
# allowed for a count and never for a dollar amount, because a deadline an
# agency sets is one a reader needs ("no deadlines stated as fact without a
# link to the source that sets them", the plan), and the page is linked.
_N = r"\d{1,3}(?:,\d{3})*"
_SP = r"(?:\s|&nbsp;)+"
COUNT = re.compile(
    r"(?<![\w$.,:/#-])" + _N + r"(?:" + _SP + r"(?:to|or|and)" + _SP + _N + r")?"
    r"(?:" + _SP + r"|-)(?:(?:business|calendar|legislative)" + _SP + r")?"
    r"(?:days?|weeks?|months?|years?|hours?|minutes?)(?![\w-])"
    r"|(?<![\w$.,:/#-])" + _N + _SP + r"(?:(?:Senate|House|state|county)" + _SP + r")?"
    r"(?:districts?|seats?|members?|senators|representatives|councilors)(?![\w-])"
    r"|\baged?" + _SP + _N + r"(?![\w,-]*\d)", re.I)


def fig(text, ref, says):
    """`text` as the guide prints it ("$15"), the section that sets it
    ("RSA 5-C:10") and words of that section that state it ("the sum of $15").
    A count may instead name a claim of the guide's own as `ref`: a record()
    claim's citation, or an agency page's address (COUNT says which)."""
    return {"text": text, "ref": ref, "says": says}


def _flat(s):
    return re.sub(_SP, " ", s)


def unbacked(g):
    """The dollar, percentage and counted figures the guide prints that no
    fig() of it declares."""
    declared = {_flat(f["text"]) for f in g.get("figures") or []}
    words = text(g)
    found = {m.group(0).replace(" ", "") for m in FIGURE.finditer(words)}
    found |= {_flat(m.group(0)) for m in COUNT.finditer(words)}
    return sorted(found - declared)


# A CONTACT DETAIL IS A CLAIM TOO (the person, 26 October 2026: "make sure
# there are absolutely no hallucinations in those sorts of pages and in the
# instructions"). FIGURE and COUNT hold money, shares and periods to their
# sources; nothing held the details a reader acts on most directly -- a phone
# number, an email address, an office's hours, a street address, a date. An
# audit that day found phone numbers no claim of their guide recorded, right
# or not. So each one a guide prints must be found in the words a claim of
# that guide records its source as saying: a phone number by its ten digits,
# an email address as written, an hour by its clock number, a street address
# by its number and street, a date by its month and day.
PHONE = re.compile(r"(?<![\d-])(?:1[-\s.]?)?\(?\d{3}\)?[-\s.]\d{3}[-\s.]\d{4}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.I)
# "8 a.m." as a source writes it, and "8:00 AM" as a guide does, clock()'s
# form since the cohesion audit of 30 October 2026 (I-3): the hours a guide
# prints in its own words are held to their claims whichever way.
CLOCK = re.compile(r"\b(\d{1,2}(?::\d\d)?)(?:\s|&nbsp;)?(?:[aApP]\.[mM]\.|[AP]M\b)")
STREET = re.compile(r"\b(\d{1,5})\s+((?:[A-Z][a-z]+\s){1,3}(?:Street|Road|Drive|Avenue|Lane|Way|"
                    r"Boulevard|Place|Square|Highway))\b")
MONTH_DAY = re.compile(r"\b(January|February|March|April|May|June|July|August|September|"
                       r"October|November|December)(?:\s|&nbsp;)+(\d{1,2})(?!\d)")


def _plain(s):
    import html as _h
    return re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", s or "")))


# WAITING FOR A PRINTOUT, BY NAME. Contact details the audit of 26 October
# 2026 found printed with no claim recording them, which no source on this
# disk can settle digit by digit. Each is named with why, and preflight
# fails on any other -- and on any of these once a claim records it, so the
# list only ever shrinks. Clear one by adding the claim from the person's
# printout and taking its line out.
CONTACTS_AWAITING = {
}


def unsourced_contacts(g):
    """The phone numbers, email addresses, hours, street addresses and dates
    the guide prints that no claim of it records its source as saying."""
    said = [_plain(c["says"] + " " + " ".join(c.get("words") or [])) for c in g["claims"]]
    said += [_plain(f["says"]) for f in g.get("figures") or []]
    digits = [re.sub(r"\D", "", s) for s in said]
    low = [s.lower() for s in said]
    words = _plain(text(g))
    out = []
    for m in PHONE.finditer(words):
        d = re.sub(r"\D", "", m.group(0))[-10:]
        if not any(d in x for x in digits):
            out.append(f"phone {m.group(0)}")
    for m in EMAIL.finditer(words):
        e = m.group(0).rstrip(".").lower()
        if not any(e in s for s in low):
            out.append(f"email {e}")
    for m in CLOCK.finditer(words):
        n = m.group(1)
        # "8 a.m." in a claim is the "8:00 AM" a guide prints, and the other way round.
        alts = {n, n[:-3]} if n.endswith(":00") else {n, n + ":00"}
        if not any(re.search(r"(?<![\d:])" + re.escape(a) + r"(?![\d:])", s) for a in alts
                   for s in said):
            out.append(f"hour {m.group(0)}")
    for m in STREET.finditer(words):
        if not any(m.group(1) in s and m.group(2).split()[0].lower() in s.lower() for s in said):
            out.append(f"address {m.group(0)}")
    # "On October 12, 2026 its page said": the day a claim of the guide was
    # checked is a date the guide may give for when it read its source.
    import components
    read_on = {components.date_words(c["checked"], "full").split(",")[0] for c in g["claims"]
               if re.fullmatch(r"\d{4}-\d\d-\d\d", str(c["checked"] or ""))}
    for m in MONTH_DAY.finditer(words):
        mon, day = m.group(1), m.group(2)
        if f"{mon} {int(day)}" in read_on:
            continue
        # A range a claim records ("June 3-12") holds both its days.
        if not any(re.search(rf"\b{mon[:3]}\w*\.?\s+{day}(?!\d)", s) or
                   re.search(rf"\b{mon[:3]}\w*\.?\s+\d{{1,2}}\s*[-–]\s*{day}(?!\d)", s) or
                   re.search(rf"\b{day}\s+{mon[:3]}", s) for s in said):
            out.append(f"date {mon} {day}")
    return sorted(set(out))


def fig_faults(g):
    """What is wrong with the guide's figures that needs no statute table: a
    figure whose number its words do not state, a dollar amount or
    percentage resting on anything but a statute, and a count resting on a
    claim of the guide that does not say it. The statute's own words are
    build_civics.guide_ready's to find."""
    faults = []
    for f in g.get("figures") or []:
        nums = re.findall(r"\d+(?:[,.]\d+)*", f["text"])
        if not nums or not all(n in f["says"] for n in nums):
            faults.append(f"the figure {f['text']} is not a number its words state: {f['says']!r}")
        if f["ref"].startswith("RSA "):
            continue
        if FIGURE.search(f["text"]):
            faults.append(f"{f['text']} rests on {f['ref']}: a dollar amount or percentage rests on a "
                          "statute or is not printed")
            continue
        on = [c for c in g["claims"] if c["source"] == f["ref"] and c["checked"]
              and not c.get("observed") and (c.get("path") or c["source"].startswith("https://"))]
        if not any(_flat(f["says"]) in _flat(w) for c in on for w in (c.get("words") or [c["says"]])):
            faults.append(f"{f['text']} rests on {f['ref']}, and no checked claim of the guide on it "
                          f"says {f['says']!r}")
    return faults


def step(title, text, actions=(), law=(), note="", part=""):
    """One numbered step: its words (HTML), the buttons to the official pages
    it needs [(label, url)], the sections of law it rests on ["RSA 654:7"],
    and a note to set apart, where something has changed or is disputed.

    `part` is a heading over this step and the ones after it, numbered from 1
    again (the person's notes, 29 October 2026: a guide would "finish
    explaining how to do the first thing and switch to a different topic, but
    keep the step by step format as though step 5 is a continuation"). A guide
    that has parts gives its first step one, so no step stands outside a
    heading."""
    return {"title": title, "text": text, "actions": list(actions), "law": list(law), "note": note,
            "part": part}


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
        "weekdays 8:30&nbsp;AM to 4:30&nbsp;PM.</li>",
        [],
        [("ADRC, formerly ServiceLink, a DHHS program of locally accessible resource centers; "
          "options counseling on benefits, applications, housing, Medicare and Medicaid; no fee "
          "or eligibility requirement; 1-866-634-9412, Monday to Friday 8:30 to 4:30.", ADRC)]),
    "legal_aid": (
        "<li><b>Free civil legal aid.</b> New Hampshire Legal Assistance helps people with low "
        "income and limited assets, and adults 60 and over, mainly with housing (including "
        "property tax deeding), domestic violence and family law, and public "
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
        "603-229-0002, weekdays 9:00&nbsp;AM to 3:30&nbsp;PM, or ask online.</li>",
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
# The day the statutes under the guides' counts were read in the table (COUNT),
# for the claims added then to cite them.
COUNTED = "2026-10-23"

# COURT ORDERS NO GUIDE MAY DESCRIBE AS IN FORCE (23 October 2026), each by
# the date a guide would name it by, with what stayed it. The How to Vote note
# said the District Court's order of October 2, 2026 "lets election officials
# consider a student ID", and on 22 October 2026 the U.S. Supreme Court stayed
# it and the order of October 5 (No. 26A512, Scanlan v. Coalition for Open
# Democracy, pending the First Circuit's appeal and any petition for
# certiorari). preflight's _vote_guide_stayed_orders reads every guide's
# words and claims: a sentence naming one of these orders must say it is
# stayed or on hold. Take a row out only when the stay has ended, and say
# when and by what.
STAYED_ORDERS = {
    "October 2, 2026": "stayed by the U.S. Supreme Court on October 22, 2026 (No. 26A512)",
    "October 5, 2026": "stayed by the U.S. Supreme Court on October 22, 2026 (No. 26A512)",
}


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
     box("Registering? Bring proof of who you are, your age, your citizenship and where you live."),
     box("On election day, show proof of identity to get your ballot, or vote absentee if you "
         "qualify.")],
    [step("Check whether you are already registered",
          "<p>The Secretary of State&rsquo;s voter information lookup tells you whether you are "
          "registered and where your polling place is.</p><p>You can vote only in the town, or "
          "the ward of a city, where you live. If you have moved to a new town or ward, you need "
          "to register at your new address.</p>",
          actions=[("Check your voter registration", SOS_APP)], law=["RSA 654:7, I"]),
     step("Make sure you can register",
          "<p>You can register if, on election day, you will be:</p><ul>"
          "<li>at least 18 years old,</li><li>a United States citizen, and</li>"
          "<li>living in the town or city ward where you are registering.</li></ul>"
          "<p>There is no minimum time you must have lived there first.</p>"
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
          "election.</li>"
          "<li><b>By absentee registration</b>, if you qualify and cannot register in person.</li></ul>",
          actions=[("Find your town or city clerk", SOS_CLERKS),
                   ("Registration deadlines", SOS_DEADLINES)],
          law=["RSA 654:8", "RSA 654:27", "RSA 654:7-a"]),
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
          "statement or tax document showing your address.</li></ul>"
          "<p>Missing a document? The questions below say what you can do.</p>",
          actions=[("What counts as proof", SOS_PROOF),
                   ("Free vital record for voter registration", SOS_FREE_VITAL)],
          law=["RSA 654:12"],
          # THE STUDENT ID SENTENCE IS OUT (23 October 2026). It said "A further
          # order of October 2, 2026 lets election officials consider a student
          # ID, together with other evidence, as proof of identity when you
          # register". On 22 October 2026 the U.S. Supreme Court stayed that
          # order and the one of October 5 (No. 26A512, Scanlan v. Coalition
          # for Open Democracy), so the sentence stopped being true. Saying so
          # instead would cite supremecourt.gov, which guide_sources.SOURCES
          # does not hold (its rule: a state agency's page, anything else the
          # person's decision), and guide_ready would hold the whole guide off
          # the site the week of the election. So the sentence is gone, and
          # what replaces it is the person's: STAYED_ORDERS, below, and
          # preflight's _vote_guide_stayed_orders keep it from coming back.
          # THE SECRETARY OF STATE IS THE WORD ON WHAT IS ACCEPTED (the person,
          # 23 October 2026: "defer to the official sources where possible").
          # The rules on proof changed more than once this year and the courts
          # are still deciding them, so the note sends the reader to the
          # Secretary of State's page first, and gives what that page said on
          # the day it was read as that, and dated.
          note="<b>This changed in 2026, and the courts are still involved.</b> What you may "
               "use as proof has changed more than once this year and may change again before "
               "the election. The Secretary of State's page is the official word: check it "
               "before you go. On October 24, 2026 it still said that if you lack the documents "
               "to prove your citizenship, you may sign a qualified voter affidavit instead, "
               "subject to the penalties for voter fraud, as a court order of May 28, 2026 "
               "allowed again. The affidavit covers citizenship and "
               "nothing else: you still need proof of identity, age and domicile."),
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
          "<li>a physical disability or illness prevents it;</li><li>work, or caring for "
          "children or an infirm adult, takes the whole time the polls are open;</li><li>you are "
          "confined for a misdemeanor or while awaiting trial; or</li><li>you are in the "
          "Attorney General&rsquo;s Address Confidentiality Program.</li></ul>"
          "<p>If the National Weather Service issues a winter storm, blizzard or ice storm "
          "warning for election day in your town, and you are worried about traveling in it, or "
          "expect school or care to be canceled for those you look after, you may vote absentee "
          "at your clerk&rsquo;s office on the day before the election.</p>"
          "<p>Send the absentee ballot application to your town or city clerk, not the state, "
          "with the proof of identity the form asks for. The deadline to ask by mail is noon the day before the election, and "
          "to ask and vote in person at the clerk&rsquo;s office, 5:00&nbsp;PM the day before. A "
          "mailed ballot must reach your clerk by 5:00&nbsp;PM on election day, so ask for it more "
          "than two weeks ahead.</p>",
          actions=[("Absentee ballots", SOS_ABSENTEE), ("Absentee ballot application", SOS_ABS_APP)],
          law=["RSA 657:1", "RSA 657:4", "RSA 7:46"])],
    [("Register to vote (Secretary of State)", SOS_REGISTER),
     ("Proof of voter registration qualifications (Secretary of State)", SOS_PROOF),
     ("Absentee ballots (Secretary of State)", SOS_ABSENTEE),
     ("Statement on the court's HB 1569 ruling, May 29, 2026 (Secretary of State)", SOS_HB1569),
     ("Voter information lookup (Secretary of State)", SOS_APP),
     ("Town and city clerks (Secretary of State)", SOS_CLERKS),
     ("Voters and Checklists, RSA 654", "/laws/654"),
     ("Absentee Voting, RSA 657", "/laws/657"),
     ("Election Procedure, RSA 659", "/laws/659")],
    ["654", "657", "659", "7"],
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
     claim("The supervisors' session for correcting the checklist, at which hearings close, is on "
           "a day they designate 6 to 13 days before the election.", "RSA 654:27", COUNTED),
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
     # Read again on 24 October 2026, in the person's PDF of the page that day.
     claim("Citizenship only may be proven by a qualified voter affidavit, subject to the "
           "penalties for voter fraud, by a citizen without some or all of the documents; no "
           "affidavit for identity, age or domicile.", SOS_PROOF, "2026-10-24"),
     claim("May 28, 2026 order: the affidavit is back for citizenship only, not identity, age or "
           "domicile; proof of identity still needed for a ballot.", SOS_HB1569, CHECKED),
     claim("A voter presents proof of identity to the ballot clerk to receive a ballot.",
           "RSA 659:13", CHECKED),
     claim("The absentee reasons, applying to the local clerk with proof of identity, six months "
           "ahead, the noon and 5 p.m. deadlines, receipt by 5 p.m. on election day, the two-week "
           "advice and tracking in the lookup.", SOS_ABSENTEE, CHECKED),
     claim("Absence, disability, religious observance; an employment obligation for all polling "
           "hours, including care of children and infirm adults, counts as absence; storm "
           "warnings.", "RSA 657:1", CHECKED),
     claim("A winter storm, blizzard or ice storm warning for election day: a person with "
           "concerns for safety traveling in the storm, or caring for children or infirm adults "
           "whose school or care may be canceled, is considered absent and may vote absentee on "
           "the day immediately prior to the election; the clerk's office is open that day.",
           "RSA 657:1", "2026-10-26"),
     claim("The application's reasons include being confined in a penal institution for a "
           "misdemeanor or while awaiting trial.", "RSA 657:4", "2026-10-26"),
     claim("A participant in the Address Confidentiality Program who is otherwise qualified to "
           "vote may apply as an absentee voter.", "RSA 7:46", "2026-10-26")],
    more=civics.faq(
        ("I moved within my town. Do I register again?",
         "<p>No. A move within the same town or ward is an address change, made on the same "
         "voter registration form. A move to a new town or ward means registering there.</p>"),
        ("What does &ldquo;living there&rdquo; mean?",
         "<p>&ldquo;Living&rdquo; here is what the law calls your <em>domicile</em>: the one place "
         "you call home and take part in public life from. You can have only one, and there is "
         "no minimum time you must have lived there first.</p>"),
        ("What if I am in line to register when the polls close?",
         "<p>You may still register and vote.</p>"),
        ("What if I have no document showing where I live?",
         "<p>There is a form to fill in together with a lease, a utility bill, or a confirmation "
         "signed by the owner, manager or tenant where you live, and a separate form for people "
         "who are homeless.</p>"),
        ("What if I am missing a document?",
         "<p>Ask your clerk: with your permission, local election officials may be able to "
         "check New Hampshire voter, motor vehicle and vital records to help prove your "
         "qualifications. A certified "
         "copy of a New Hampshire birth or other vital record is free when it is only for "
         "registering to vote.</p>"),
        ("How early can I ask for an absentee ballot, and can I track it?",
         "<p>You can apply up to six months before the election. The voter information lookup "
         "shows when your clerk got your request, sent your ballot, and received it back.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Your town or city clerk is the person to ask about registering and voting where you "
         "live: what to bring, the deadline, and absentee ballots.</p>",
    see=[("New to New Hampshire: license, registration and voting", "/guides/new-to-new-hampshire.html"),
         ("How to get a birth or other vital record", "/guides/vital-records.html"),
         ("Finding your representatives", "/guides/your-representatives.html")],
    figures=[fig("18 years", "RSA 654:7", "At least 18 years of age on the day of the next election"),
             fig("6 to 13 days", "RSA 654:27", "6 to 13 days prior to the election")])


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
          "cost.</p>",
          law=["RSA 91-A:4, IV(d)", "RSA 91-A:4, VIII"]),
     step("If the answer is no",
          "<p>A refusal must be in writing, name the specific exemption it relies on, and "
          "briefly explain how it applies. To have a refusal reviewed, the law provides two "
          "routes. Going to Superior Court rules out the ombudsman; filing with the ombudsman "
          "rules out the court until the ombudsman rules or the deadline for a ruling "
          "passes:</p><ul>"
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
     claim("Superior court or the ombudsman; a petition to the superior court forecloses a "
           "complaint to the ombudsman; a complaint to the ombudsman forecloses the superior "
           "court until the ombudsman issues a final ruling or the deadline for such a ruling has "
           "passed.", "RSA 91-A:7", "2026-10-26"),
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
    more=civics.faq(
        ("Does the office have to create a record for me?",
         "<p>The office does not have to create a record that does not exist, or put information "
         "together in a form it does not already keep. It may suggest narrowing your request so "
         "it can answer faster or for less.</p>"),
        ("What if another law sets a fee for a copy?",
         "<p>Where another law sets a fee for a copy, that fee applies, with nothing added.</p>"),
        ("Can I be charged for a request covering many emails?",
         "<p>For a request covering more than 250 emails or other electronic messages, the law "
         "allows a charge per message within a limit it sets, and requires it to be waived in "
         "some cases.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>The office that keeps the record is the first place to ask how to get it. To "
         "understand the law in more depth, the Attorney General publishes a memorandum on the "
         "Right-to-Know Law for citizens and public officials alike. It says it is not legal "
         "advice, and that anyone with a specific question should consult a lawyer.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{RTK_MEMO}" target="_blank" rel="noopener">'
         "The Attorney General&rsquo;s memorandum</a></p>"
         + helps("lawyer"),
    see=[("Town meeting and local government", "/learn/local-government.html"),
         ("Who to contact about an issue", "/guides/who-to-contact.html")],
    figures=[fig("5 business days", "RSA 91-A:4", "within 5 business days of a request"),
             fig("250", "RSA 91-A:4", "in excess of 250 communications")])


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
          "<p>The Department of Energy lists five agencies, each serving its own counties, "
          "and every office and its number.</p>"
          + table("Community action agencies by county (Department of Energy, October 26, 2026)",
                  ["Counties", "Agency", "Phone"],
                  [["Belknap and Merrimack", "Community Action Program, Belknap/Merrimack Counties",
                    "(603) 223-0043"],
                   ["Hillsborough and Rockingham",
                    "Community Action Partnership Hillsborough and Rockingham Counties",
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
          "appointment.</p>",
          actions=[("Fuel Assistance Program", DOE_FUEL)]),
     step("Know what each program does",
          "<ul><li><b>Fuel assistance</b> helps with heating costs. "
          "It is a grant, not a loan.</li>"
          "<li><b>Electric assistance</b> is a discount on your monthly electric bill if your "
          "income qualifies.</li>"
          "<li><b>Weatherization</b> helps lower-income households make their homes cheaper to "
          "heat.</li></ul>",
          actions=[("Fuel assistance: amounts and income limits", DOE_FUEL)]),
     step("In a heating emergency",
          "<p>Call your community action agency. Fuel assistance can arrange an emergency "
          "delivery of fuel, delay a shut-off notice, or point you to other help.</p>")],
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
     # The person's printout of the page, 26 October 2026, its numbers as printed.
     claim("Community Action Program, Belknap/Merrimack Counties: All Belknap and Merrimack "
           "County Residents (603) 223-0043. Community Action Partnership Hillsborough and "
           "Rockingham Counties (CAPHR): Hillsborough County and Rockingham County offices. "
           "Southwestern Community Services (Cheshire and Sullivan Counties): Keene (603) "
           "352-7512; Claremont (603) 542-9528. Community Action Partnership of Strafford County: "
           "Dover (603) 435-2500 Ext. 4001. Tri-County Community Action Program (Coos, Carroll and "
           "Grafton Counties): Carroll County: (603) 323-7400; Coos County: (603) 752-3248; "
           "Grafton County: (603) 968-3560. You can apply for Electric Assistance, Fuel "
           "Assistance, and Weatherization Assistance at the same time. You do not need to "
           "receive benefits from one program to participate in the other programs. If you are "
           "homebound and unable to visit a CAA office, please call your local Community Action "
           "Agency office and ask about other options, such as a home interview, an interview "
           "over the phone, and mail-in applications. For NO-HEAT EMERGENCIES and other "
           "assistance inquiries, please contact your local community action agency.",
           DOE_CAA, "2026-10-26"),
     claim("Other Assistance Resources: Neighbor Helping Neighbor (for customers of Eversource, "
           "Liberty and Unitil); Project Care (for NHEC customers only); 211 Dial 211 or "
           "1-866-444-4211; NH Adult and Aging Care 1-866-634-9412.", DOE_CAA, "2026-10-26"),
     # 211's own number, as the homelessness guide records 211 NH's page saying it.
     claim("211 NH connects residents to resources through trained Information and Referral "
           "Specialists, available 24 hours, 365 days a year, by phone, email or text, for "
           "housing, utilities, food, mental health and more; dial 211 or 1-866-444-4211; 911 "
           "for emergencies; 988 for suicide and crisis help.", "https://211nh.org/",
           "2026-10-24")]
    + help_claims("nheasy", "adrc"),
    more=civics.faq(
        ("What if I cannot get to an office?",
         "<p>Ask about an interview at home or by phone, or a mail-in application.</p>"),
        ("Do I have to pay fuel assistance back?",
         "<p>No. It is a grant, not a loan, and it is not counted as income when you apply for "
         "other help.</p>"),
        ("How much fuel assistance will I get?",
         "<p>The amount depends on household income, energy costs, the local climate and your "
         "kind of housing. The Department&rsquo;s page gives the current range.</p>"),
        ("When should I order heating fuel?",
         "<p>If you heat with oil, kerosene or propane, the Department advises calling your "
         "supplier at least ten days before you need a delivery.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Your community action agency is where to apply and where to ask about your "
         "household. The Department of Energy also lists these:</p><ul>"
         "<li><b>211 New Hampshire:</b> dial 211, or 1-866-444-4211, for help finding other "
         "assistance.</li>"
         "<li><b>Neighbor Helping Neighbor</b>, for customers of Eversource, Liberty and Unitil, "
         "and <b>Project Care</b>, for New Hampshire Electric Co-op customers.</li></ul>"
         f'<p class="g-acts"><a class="g-btn" href="{NH211}" target="_blank" rel="noopener">211 '
         "New Hampshire</a></p>"
         "<p>For help with other benefits, and someone to talk them through with:</p>"
         + helps("nheasy", "adrc"),
    see=[("How to apply for food or health assistance", "/guides/food-and-health-assistance.html"),
         ("How to prepare for storms, power outages and other emergencies",
          "/guides/storms-and-emergencies.html")])


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
          "saying which record you need, why, and any evidence for it.</p>",
          law=["RSA 5-C:102"]),
     step("Fill in the application",
          "<p>Fill in the section for the kind of record you want, and the applicant section "
          "with your name, address, reason and relationship, and sign it. Willfully and knowingly "
          "making a false statement on the application is a class B felony.</p>",
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
          "copy of the same record issued at the same time. The law sets both.</p>",
          actions=[("Current fees", DVRA_REQUEST)], law=["RSA 5-C:10"])],
    [("Vital Records (Secretary of State)", DVRA),
     ("Request for Certificates (Secretary of State)", DVRA_REQUEST),
     ("Application for a certified copy of a vital record (Secretary of State)", DVRA_APP),
     ("Vital Records Administration, RSA 5-C", "/laws/5-c")],
    ["5-C"],
    # The person's printouts of the page and the form, 26 October 2026.
    [claim("In addition to all 234 local City and Town Clerks, the Division of Vital Records "
           "Administration (DVRA) issues certified copies of birth, death, marriage, divorce and "
           "civil union certificates to qualified individuals and agencies that provide a "
           "\"direct and tangible\" interest; complete the application and send it to the DVRA "
           "or visit your local City or Town Clerk and pay a search fee; the current fee is $15, "
           "plus any additional expenses incurred for credit card transactions, payable whether or "
           "not a record is found; additional copies of the same record issued at the same time "
           "are $10; present positive identification including, but not limited to, a driver's "
           "license, passport or other picture identification, or complete the form "
           "Documentation Evidence for Individuals Not Possessing An Acceptable Picture "
           "Identification.", DVRA_REQUEST, "2026-10-26"),
     claim("Submit the completed application (with payment in U.S. funds ONLY and photo "
           "identification) to: NH Department of State, Division of Vital Records "
           "Administration, Registration / Certification, 9 Ratification Way, Concord, NH "
           "03301-2455.", DVRA_REQUEST, "2026-10-26"),
     claim("Event sections and an applicant section (legal name, mailing address, reason for "
           "request, signature, relationship to registrant); for a death record, with cause of "
           "death & manner of death, manner of death only, or without cause or manner of death, "
           "and whether the social security number is suppressed; when mailing: check or money "
           "order in US funds made payable to \"Treasurer-State of New Hampshire\", legible "
           "photocopy of your photo identification, proof of your mailing address (utility bill, "
           "lease agreement, car registration, etc.) if it isn't on the photo ID, self-addressed, "
           "pre-stamped return envelope for faster mailing; any person shall be guilty of a "
           "CLASS B Felony if they willfully and knowingly make any false statement in an "
           "application for a certified copy of a vital record (RSA 5-C:14).", DVRA_APP,
           "2026-10-26"),
     claim("Records public before 1901 (births) and 1948 (others); who has a direct and tangible "
           "interest; a letter for a claim, reviewed by the registrar or clerk, with appeal.",
           "RSA 5-C:102", CHECKED),
     claim("$15 search including the copy, $10 each subsequent copy.", "RSA 5-C:10", CHECKED),
     claim("A false statement in an application for a certified copy is a class B felony.",
           "RSA 5-C:14", CHECKED)],
    more=civics.faq(
        ("What choices are there on a death record?",
         "<p>For a death record you choose whether it shows the cause and manner of death, and "
         "whether the Social Security number is suppressed.</p>"),
        ("Do I get the fee back if no record is found?",
         "<p>No. The $15 is paid whether or not the record is found, and a card payment may cost "
         "extra.</p>"),
        ("Who decides whether I may have a record?",
         "<p>The clerk or the state registrar decides, and a refusal can be appealed.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Your town or city clerk issues certified copies, and is the nearest place to ask. "
         "The Division of Vital Records Administration lists how "
         "to reach it on its contact page. A certified copy needed only to register to vote is "
         "free: see How to Vote.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_CLERKS}" target="_blank" rel="noopener">'
         "Find your town or city clerk</a> "
         f'<a class="g-btn" href="{DVRA_CONTACT}" target="_blank" rel="noopener">Contact Vital '
         "Records</a></p>",
    see=[("How to get a REAL ID", "/guides/real-id.html"),
         ("How to get a U.S. passport", "/guides/passport.html"),
         ("How to vote in New Hampshire", "/guides/how-to-vote.html")],
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
          "<li><b>A disproportionate assessment:</b> your <em>equalized assessment</em> is "
          "higher than the property&rsquo;s value. The application has a place to list "
          "comparable properties.</li>"
          "<li><b>Poverty and inability to pay</b>, explained in detail.</li></ul>"
          "<p>The application asks for specific reasons, not a general statement about the tax. "
          "List every property you own in the town, not only the one you are appealing.</p>",
          law=["RSA 76:16"]),
     step("File the application with your town",
          "<p>Use the Board&rsquo;s abatement application, sign it, and keep a copy. To apply, "
          "you must have complied with the property inventory law, RSA 74, and the application "
          "has a section on it.</p>",
          actions=[("The abatement application", BTLA_ABATE)],
          law=["RSA 76:16, I(b)", "RSA 76:16, III"]),
     step("Wait for the decision",
          "<p>The town must grant or deny in writing by July 1, or within 6 months where the "
          "final bill went out after December 31. Not answering counts as a denial. A written "
          "decision tells you how to appeal and by when.</p>",
          law=["RSA 76:16, II"]),
     step("Appeal a denial",
          "<p>You can appeal to the <b>Board of Tax and Land Appeals</b> or to the <b>Superior "
          "Court</b>, but not both. For the Board, fill in its appeal form and mail it or hand it "
          "in, with the $65 filing fee by check or money order payable to &ldquo;Treasurer, "
          "State of NH&rdquo;, to the Board of Tax and Land Appeals at the address its property "
          "tax page gives.</p>",
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
     claim("Any person aggrieved who has complied with the requirements of RSA 74 may apply; the "
           "form includes a section concerning compliance with the RSA 74 inventory requirement "
           "and a section to list any comparable properties.", "RSA 76:16", "2026-10-26"),
     claim("BTLA appeal on payment of a $65 fee by September 1.", "RSA 76:16-a", CHECKED),
     claim("Superior court in lieu of the BTLA, by September 1.", "RSA 76:17", CHECKED),
     claim("2, 6 and 8 months where notice of tax is after December 31.", "RSA 76:16-d", CHECKED),
     claim("Date of the final tax bill and date of notice of tax defined.", "RSA 76:1-a", CHECKED),
     claim("Damaged buildings: apply within 60 days of the event or by March 1, whichever is "
           "later; appeal as under 76:16-a or 76:17.", "RSA 76:21", CHECKED)]
    + help_claims("legal_aid", "lawyer"),
    more=civics.faq(
        ("How do I work out my equalized assessment?",
         "<p>Divide your assessment by your town&rsquo;s equalization ratio.</p>"),
        ("When does my application count as filed?",
         "<p>It is filed on the day you hand it in, the day it is postmarked, or the day an "
         "overnight carrier receipts it.</p>"),
        ("Does the application form cost anything?",
         "<p>Your town may charge for the form.</p>"),
        ("Can I file an appeal online?",
         "<p>No. The Board of Tax and Land Appeals does not accept appeals filed "
         "electronically.</p>"),
        ("What if I lose my appeal?",
         "<p>Whether you appealed to the Board or to the Superior Court, the decision can then be "
         "appealed to the Supreme Court.</p>"),
        ("What if a fire or disaster damaged my building?",
         "<p>When a fire you did not cause, or a natural disaster, leaves a building unusable "
         "during the tax year, its assessment is prorated for the days it could be used. Apply "
         "in writing to your town within 60 days of the damage or by March 1, whichever is later. "
         'Appeals follow the same routes and deadlines (<a href="/laws/76#s21">RSA 76:21</a>).</p>'))
         + "<h2>Who Can Help</h2>"
         "<p>Your town or city&rsquo;s assessing officials are who you apply to for an "
         "abatement. For questions about appealing, the Board of Tax and Land Appeals publishes "
         "commonly asked questions, and its property tax page says how to reach it.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{BTLA}" target="_blank" rel="noopener">The '
         "Board of Tax and Land Appeals</a></p>"
         "<p>For legal help, including if you are at risk of losing your home over unpaid "
         "property taxes:</p>"
         + helps("legal_aid", "lawyer"),
    see=[("Help paying property tax on a low or moderate income", "/guides/property-tax-relief.html")],
    figures=[fig("$65", "RSA 76:16-a", "upon payment of a $65 filing fee"),
             fig("2 months", "RSA 76:16-d", "within 2 months of the date of notice of tax"),
             fig("6 months", "RSA 76:16-d", "within 6 months of the date of notice of tax"),
             fig("8 months", "RSA 76:16-d", "within 8 months of the date of notice of tax"),
             fig("60 days", "RSA 76:21", "within 60 days of the event described in paragraph I or by "
                                         "March 1, whichever is later")])


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
          "Property Tax;</li><li>you lived in it on April 1 of the year you are claiming for, "
          "or were away on active military duty or for a while, keeping it as your main home; "
          "and</li><li>your household income is $37,000 or less if you are single, or $47,000 or "
          "less if you are married or a head of household.</li></ul>"
          "<p><b>Household income</b> is the federal adjusted gross income of you and of every "
          "other adult who lives in the home.</p>",
          actions=[("Who qualifies, and the limits", DRA_LMI)],
          law=["RSA 198:56", "RSA 198:57, III"]),
     step("Apply between May 1 and June 30",
          "<p>Claims are filed in that window. The Department may accept a late, complete claim "
          "up to November 1 if an accident, mistake or misfortune kept you from filing on time, "
          "or if you or another adult in your household asked for an extension to file a federal "
          "income tax return.</p>"
          "<p>Apply online through the Department&rsquo;s "
          "Granite Tax Connect portal, using &ldquo;Apply for Property Tax Relief&rdquo;, or on "
          "Form DP-8 from the Department&rsquo;s forms page.</p>",
          actions=[("Granite Tax Connect", DRA_GTC), ("Forms, including DP-8", DRA_FORMS)],
          law=["RSA 198:57, VI"]),
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
     claim("Resided in such homestead on April 1 of the year for which the claim is made, except "
           "persons on active duty in the United States armed forces or temporarily away but "
           "maintaining the homestead as a primary domicile; complete applications filed between "
           "May 1 and June 30; the commissioner may accept late filed, but complete, applications "
           "filed on or before November 1, if prevented from timely filing due to accident, "
           "mistake or misfortune, or if the claimant or other adult member of the household "
           "requested an extension of time to file a federal income tax return.", "RSA 198:57",
           "2026-10-26"),
     claim("Appeal to the BTLA in writing within 30 days.", "RSA 198:60", CHECKED),
     claim("Certification within 120 days; notice of rejection within 90 days.", "RSA 198:61", CHECKED),
     claim("A fraudulent claim is a misdemeanor; audits within 3 years; the commissioner may "
           "assess and collect sums granted on a fraudulent or erroneously paid claim, with "
           "interest and a penalty.", "RSA 198:59", "2026-10-26")]
    + help_claims("adrc", "legal_aid"),
    more=civics.faq(
        ("How much relief can I get?",
         "<p>The relief is a share of the State Education Property Tax on the lesser of your "
         "home&rsquo;s assessed value and $220,000 multiplied by your town&rsquo;s equalization "
         "ratio, at the education tax rate on your bill. The share depends on your household "
         "income. The Department works it out from your claim.</p>"
         + table("The share of the tax refunded (RSA 198:57, IV)",
                 ["Share", "Single", "Married or head of household"],
                 [["100%", "Under $23,100", "Under $29,400"],
                  ["60%", "$23,100 to under $27,800", "$29,400 to under $35,300"],
                  ["40%", "$27,800 to under $32,400", "$35,300 to under $41,100"],
                  ["20%", "$32,400 to $37,000", "$41,100 to $47,000"]])),
        ("Can my claim be checked later?",
         "<p>Yes. A fraudulent claim is a crime, and the Department may audit a claim within "
         "three years of granting it and collect back what was paid in error, with interest and "
         'a penalty (<a href="/laws/198#s59">RSA 198:59</a>).</p>'))
         + "<h2>Who Can Help</h2>"
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
             fig("$41,100", "RSA 198:57", "$35,300 but less than $41,100, 40 percent"),
             fig("120 days", "RSA 198:61", "certify such amount to the state treasurer within 120 days"),
             fig("90 days", "RSA 198:61", "within 90 days of the department's receipt of the claim"),
             fig("30 days", "RSA 198:60", "may appeal in writing within 30 days of notice of such "
                                          "refusal")])


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
# WHAT THE FIRST DRAFT LEFT UNSAID, AND WHAT SAYS IT NOW (17 October 2026).
# When the online sign-ins close, how a speaker asks to be heard in each
# chamber, and whether the Senate takes sign-ins online were left out at
# first, because no document on this disk said them. The Senate's own Public
# Guidance for Committee Meetings (September 7, 2021), which the person saved
# byte for byte into records/sources/, says the third and part of the second,
# and Senate Calendar No. 20 of 2025 prints its form's address; the rest is
# the person's first-hand account, cited as observed() practice. Still not
# cited: House Rule 44's requirement of a hearing on every bill, or its notice
# period, because the adopted text of the current rules is not on this disk,
# only amendments to them that were tabled or failed, and an amendment's words
# are not the rule's (the fact-check of 17 October 2026).
# ---------------------------------------------------------------------------
# The chambers' own guidance for the public, saved in records/sources/ under
# the chamber's name, is the General Court's document as much as a calendar.
# The State House Visitor Center is the General Court's too -- its page is on
# gc.nh.gov -- and its Rules for Tours, saved as "state-house-..." on 17
# October 2026, are the one document the guide to touring rests on.
# THE CONSTITUTION TOO (23 October 2026): nh.gov's pages of it, saved byte for
# byte with their sha256 on 17 October and read by parse_constitution, are
# tracked in git, so a claim on them is confirmed on every machine and never
# counted absent. Read as any saved page is, markup off.
RECORD_HOMES = ("calendars/", "calendars_senate/", "journals/", "journals_senate/",
                "legislation/", "bill_text/", "db/", "Members.txt",
                "records/sources/senate-", "records/sources/house-",
                "records/sources/state-house-", "records/sources/constitution/")
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


# OBSERVED PRACTICE (the docstring says what it is). The label is the one
# readers see under Where This Comes From, civics.py's, so a guide and a
# Learn page name the same source in the same words.
OBSERVED = civics.SRC_OBSERVED[0]
# What an observed claim may never state, with the word a fault names it by:
# a fee or any figure of money or share, a deadline or other requirement of
# law, a number of seats. Each is a statute's, a rule's or an official
# count's to say, never one person's account of a room.
NEVER_OBSERVED = (
    ("fee", re.compile(r"\bfees?\b|" + FIGURE.pattern, re.I)),
    ("deadline set by law", re.compile(r"\bdeadlines?\b|\b(?:by|under|in) (?:law|statute)\b|"
                                       r"\brequired by\b|\bRSA\b|\bRule \d", re.I)),
    ("number of seats", re.compile(r"\bseats?\b", re.I)),
)


def observed(says, checked=None):
    """A claim only the person's own first-hand account supports: how a
    hearing or a session day runs in practice. It carries OBSERVED as its
    source, and claim_faults holds it to the rules above."""
    c = claim(says, OBSERVED, checked)
    c["observed"] = True
    return c


def links(g):
    """Every page of this site the guide links, without its #section."""
    found = ({u for _l, u in g["sources"]} | {u for _l, u in g["see"]}
             | {u for s_ in g["steps"] for _l, u in s_["actions"]}
             | set(re.findall(r'href="([^"]+)"', text(g))))
    return {u.split("#")[0] for u in found if u.startswith("/")}


def _document(path):
    """A document as it is, and its words: a saved page's with its markup
    taken off, a PDF's as pdfplumber reads them, any other file's as it is.
    None where a PDF cannot be read here, which counts as not on this disk."""
    import html
    from pathlib import Path
    # A PDF IS READ FOR ITS WORDS (17 October 2026): the Senate's guidance is
    # kept as the PDF it was published as, so its words are taken from the
    # PDF itself, page by page, and never from a copy typed out of it.
    if path.lower().endswith(".pdf"):
        try:
            import pdfplumber
        except ImportError:
            return None
        with pdfplumber.open(path) as pdf:
            words = "\n\f".join(p.extract_text() or "" for p in pdf.pages)
        return words, words
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
    """What is wrong with the guide's record, site and observed claims, and how many
    record claims a document on this disk confirmed: (faults, confirmed,
    absent). A document is read once, and a large table is searched as it
    is, with the words' spaces matching any whitespace, so that the House's
    100 MB sign-in table costs a second and not a copy of itself."""
    from pathlib import Path
    faults, confirmed, absent, read = [], 0, 0, {}
    # OBSERVED PRACTICE IS SHOWN AS PRACTICE (17 October 2026): a guide that
    # rests anything on the editor's account names it under Where This Comes
    # From and says "in practice" in its own words, so a reader can tell a
    # rule from what usually happens.
    if any(c.get("observed") for c in g["claims"]):
        if OBSERVED not in {label for label, _u in g["sources"]}:
            faults.append(f"it rests on observed practice and does not name {OBSERVED!r} "
                          "under Where This Comes From")
        if "in practice" not in text(g).lower():
            faults.append("it rests on observed practice and never says 'in practice' to its readers")
    for c in g["claims"]:
        if c.get("observed"):
            if c["source"] != OBSERVED:
                faults.append(f"an observed claim is labelled {c['source']!r}, not {OBSERVED!r}")
            for what, pattern in NEVER_OBSERVED:
                if pattern.search(c["says"]):
                    faults.append(f"an observed claim states a {what}, which no account of a room "
                                  f"can support: {c['says'][:70]}")
            continue
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
            if read[c["path"]] is None:      # a PDF, and no pdfplumber here to read it
                absent += 1
                continue
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
# Read for the hearing and testimony guides' second pass (17 October 2026).
# The first House calendar on this disk to print the executive-session line
# "may be held throughout the day" in full (HC 21 of five days earlier has a
# shorter form), and the first of 2026 to print it.
HC23_97 = "calendars/1997/HC023.txt"
HC2_26 = "calendars/2026/HC002.txt"
HC7_21 = "calendars/2021/HC007.txt"
SC20_25 = "calendars_senate/2025/SC020.txt"
SENATE_GUIDANCE = "records/sources/senate-public-guidance-committee-meetings-2021-09-07.pdf"
GUIDANCE = "New Hampshire Senate, Public Guidance for Committee Meetings, September 7, 2021"

# THE GENERAL COURT'S OWN PAGES A GUIDE MAY LINK (17 October 2026): the two
# chambers' online sign-in forms, which a reader uses on that site. They are
# civics.py's, where check_civics_links.py -- under the refusal guard, and only
# when a person starts it -- asks whether they still answer. They are not in
# guide_sources.py, which makes requests: nothing here asks the General
# Court's server, and a fetching script that named its address would be one.
HOUSE_SIGNIN = civics.SRC_TESTIFY[1]
SENATE_SIGNIN = civics.SRC_SENATE_TESTIFY[1]
# And the General Court's own site, which the Resources hub names first among
# the other ways to follow legislation (civics.FOLLOW_OFFICIAL, 17 October
# 2026): a link to gc.nh.gov anywhere in the guides' part of the site is one
# of these, so the one list says every address of the Court's this part
# links and nothing here asks.
GENERAL_COURT_LINKS = {HOUSE_SIGNIN, SENATE_SIGNIN, civics.SRC_GENERAL_COURT[1],
                       # The Visitor Center's page, for the guide to touring
                       # the State House (17 October 2026).
                       civics.SRC_VISITOR_CENTER[1]}

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
# The Senate's online sign-in, as its own calendar of 2025 prints it. The
# words are built from the address the guides link, so the day civics.py's
# address and the calendar's part, this claim fails (17 October 2026).
SENATE_ONLINE = record(
    "The Senate takes positions online, at the address the guides link.",
    "Senate Calendar No. 20, May 8, 2025, p. 24", SC20_25,
    ["Individuals looking to register their position may do so remotely",
     "Link: " + SENATE_SIGNIN], READ)
# The line many House committee notices end with, in the calendars' words.
EXEC_THROUGHOUT = ("Executive session on pending legislation may be held throughout the day, time "
                   "permitting, from the time the committee is initially convened")


# ---------------------------------------------------------------------------
# WHAT A HEARING IS LIKE, WRITTEN ONCE (the person's approval of 23 October
# 2026). Testifying and Attending (civics.BODY_TESTIFYING, published at
# /guides/testifying.html) said in copied paragraphs what the two guides below
# say -- how hearings are announced, a meeting that starts late, the pink card
# and the Senate's sheet, the chair's time, notes, props and signs, the last
# call, paper copies, when the online sign-ins open and close and what each
# form asks, where written testimony goes, and the executive session after --
# and the copies had begun to drift: the page said a sign-in window opened
# once a hearing was "published", the guides did not, and each said the
# executive-session line in its own words. Each is written here once, in the
# guide whose claims source it (HEARING or TESTIMONY, which draw their steps
# from these), and the page marks where one goes, <!-- guides:NAME -->, which
# build_civics fills from here (reused). Where the two had said one thing
# differently, the words are the guide's, with what the page added that the
# guide's claims also support: the notice's time "the earliest it will begin,
# not a promise", a vote you "may have to watch the whole day" for, the line
# printed "and still" in 2026, an executive session held "without further
# notice" (House Rule 44(b)), and the Senate's form taking no testimony.
# preflight's _testifying_reuses_the_guides holds the page to these and to
# nothing typed again.
# ---------------------------------------------------------------------------
SAID = {
    # HEARING's.
    "announced": (
        "<p>A hearing is announced in the calendar of the chamber holding it. The notice names the "
        "committee, the building and room, the day, and a time for each bill. The House lists its "
        "hearings under Committee Meetings in the House Calendar, and the Senate&rsquo;s rules "
        "require at least 4 days&rsquo; notice in the Senate Calendar.</p>"),
    "starts-late": (
        "<p>In practice a committee meeting <b>never starts before the time its notice gives, and it "
        "often starts later</b>: an earlier hearing in the same room may have run long with more "
        "speakers than expected, or a lunch break or a caucus before the meeting may have run over. "
        "The time in the notice is the earliest it will begin, not a promise, so plan to wait.</p>"),
    "ask-to-speak": (
        "<p>Speaking is a separate step from signing in, and spoken testimony is given in "
        "person. Each chamber asks for it its own way:</p><ul>"
        "<li><b>In the House</b>, in practice there is a stack of pink cards on a table and a "
        "registration sheet near the front of the room. Anyone may sign the sheet with their "
        "name and whether they support or oppose the bill. To speak, fill out a pink card and "
        "hand it to a staff member or a committee member, who passes it to the chair.</li>"
        "<li><b>In the Senate</b>, sign up on the sheet in the committee room on the day of "
        "the hearing: the Senate&rsquo;s guidance says so, and its notices tell anyone who "
        "wishes to speak to sign up in person. In practice the sheet has a box to mark if you "
        "want to speak.</li></ul>"),
    # The practice in the room, each an item of a list. The sponsor first, and
    # no rule on time, the person, 23 October 2026: "The no rule sets a time
    # limit is correct, but chairs have the discretion to apply or not apply
    # one. Typically the prime sponsor speaks first to introduce the bill and
    # is not time limited."
    "sponsor-first": (
        "<li><b>The sponsor goes first.</b> The prime sponsor usually speaks first to "
        "introduce the bill, and is not held to a time limit.</li>"),
    "chair-time": (
        "<li><b>The chair sets the time.</b> No rule sets a time limit: whether to set one, "
        "and when to stop a speaker, is the chair&rsquo;s call. With a few speakers there may "
        "be no limit. With many, "
        "more than about ten, chairs often give each person two or three minutes and ask "
        "speakers not to repeat points already made several times, so that each brings their "
        "own view.</li>"),
    "notes": "<li><b>Notes are fine.</b> You may read from prepared notes or from your phone.</li>",
    "props": (
        "<li><b>No props.</b> Props are not allowed while you testify. Signs are allowed in "
        "the hallways, not in the committee room.</li>"),
    "last-call": (
        "<li><b>The last call.</b> Before closing the hearing, the chair usually asks whether "
        "anyone who has not yet spoken would like to speak on the bill: a last chance for "
        "anyone who did not sign up. If no one does, the hearing is closed.</li>"),
    "exec-session": (
        "<p>The committee votes on what to recommend at an executive session, which you may "
        "watch. It can follow the hearing directly: Senate notices often say so, and a House "
        "committee may hold one right after a noticed hearing without further notice, if the "
        "chair and the ranking member agree. Some "
        "notices give one block of "
        "time to &ldquo;executive session on pending legislation&rdquo;, and in practice the "
        "chair then takes up the bills in any order.</p>"),
    "throughout-the-day": (
        "<p>Many House committee notices also say that an &ldquo;executive session on pending "
        "legislation may be held throughout the day, time permitting, from the time the "
        "committee is initially convened&rdquo;. That means the committee may vote on any bill "
        "it has pending at any point in that day, so the notice gives the vote no time: to see "
        "a particular vote you may have to watch the whole day, and you may learn when it "
        "happened only afterward. House calendars have printed that line since at least "
        "February 1997, and still do.</p>"),
    # TESTIMONY's.
    "window": (
        "You can sign in once the hearing is scheduled, and not before: the Senate&rsquo;s "
        "guidance says so of its form, and encourages you to sign in well ahead of the hearing. "
        "In practice the House&rsquo;s opens the same way, and both close at midnight at the end "
        "of the day of the hearing."),
    "forms": (
        "<p><b>The House&rsquo;s</b> Sign-in Form and Online Testimony Submission asks, among "
        "other things, for:</p><ul>"
        "<li>your name, town and state;</li>"
        "<li>who you are, such as a member of the public, an elected official, a lobbyist or "
        "state agency staff, and whom you represent, if anyone; and</li>"
        "<li>whether you support the bill, oppose it, or are neutral.</li></ul>"
        "<p>You may attach written testimony, or sign in without it. What you submit goes to "
        "the committee&rsquo;s members.</p>"
        "<p><b>The Senate&rsquo;s</b> form asks you to choose the day, the committee and the "
        "bill; whether you are an elected official, a lobbyist, agency staff or a member of the "
        "public, and whom you represent, if anyone; whether you support the bill, oppose it or "
        "are neutral; and your name and contact information. It takes no written testimony: "
        "its confirmation page says how to send it.</p>"),
    "email": (
        "<p>The Senate&rsquo;s guidance says to send written testimony to the committee through "
        "the &ldquo;Email All Committee Members&rdquo; link on the committee&rsquo;s page on "
        "the General Court&rsquo;s website. <a href=\"/committees.html\">Every committee&rsquo;s "
        "page here</a>, House or Senate, does the same: it lists the members and has a button "
        "that opens one email to all of them. Put the bill&rsquo;s number in the subject "
        "line.</p>"),
    "paper": (
        "<p>In practice you can also bring written testimony to the hearing on paper: one "
        "printed copy for each member of the committee, which they will take and pass around. "
        "Paper copies are optional; an email reaches the same members.</p>"),
}
REUSE = re.compile(r"<!-- guides:([a-z-]+) -->")


def reused(html):
    """`html`, a page of civics.py's, with each <!-- guides:NAME --> it marks
    written out as SAID[NAME]. A name SAID does not hold is a ValueError,
    which stops the build rather than publish a page with a hole in it."""
    unknown = sorted(set(REUSE.findall(html or "")) - set(SAID))
    if unknown:
        raise ValueError(f"a page marks paragraphs guides.SAID does not hold: {unknown}")
    return REUSE.sub(lambda m: SAID[m.group(1)], html or "")


# ---------------------------------------------------------------------------
# ATTENDING AND SPEAKING AT A PUBLIC HEARING (17 October 2026). Testifying
# and Attending explains hearings at length; this is the same ground as a
# sequence of things to do, and it links that page for what it already says
# well -- the buildings, and how each chamber takes a request to speak. The
# second pass of the same day added what a reader meets in the room -- the
# pink card, the Senate's sign-up sheet, the chair's time and last call, a
# meeting that starts late -- from the Senate's guidance and the person's
# first-hand account, the second cited as practice. Since 23 October 2026
# those paragraphs are SAID's, above, and that page draws them from here.
# ---------------------------------------------------------------------------
HEARING = guide(
    "attend-a-hearing", "How to Attend and Speak at a Public Hearing",
    "Finding a bill's public hearing, going in person or watching it, and asking to speak, "
    "step by step, with what happens after.",
    "Committees of the House and of the Senate hold public hearings on bills, and the "
    "Senate&rsquo;s rules require one on every bill sent to a committee. You may attend and "
    "testify. Find the hearing in the chamber&rsquo;s "
    "calendar or on the bill&rsquo;s page here, go to the room the notice names or watch the "
    "live stream, and ask to speak when you arrive: on a pink card in the House, on the "
    "sign-up sheet in the committee room in the Senate. In practice a hearing never starts "
    "before the time in its notice, and often starts later. If you cannot go, you can sign "
    "in online or send your position in writing instead.",
    [box("Find the hearing: the committee, the room, the day, and the time for your bill."),
     ask("Can you go in person?",
         [("Yes", "Go to the room, and ask to speak: a pink card in the House, the sign-up sheet "
                  "in the Senate."),
          ("No", "Watch the live stream, and sign in online or send your position in writing.")]),
     box("When the chair calls you, speak briefly. Before closing, the chair usually asks whether anyone "
         "else wishes to speak."),
     box("Afterward, the committee votes on what to recommend, sometimes the same day.")],
    [step("Find the hearing",
          SAID["announced"]
          + "<p>On this site, a bill&rsquo;s page lists its hearings with the day, time and room, "
          "and the Calendar shows the week&rsquo;s hearings by committee. Follow on a "
          "bill&rsquo;s page gives you its new actions as they are recorded, and the site keeps a "
          "feed of hearings coming up as well.</p>",
          actions=[("This week's hearings", "/calendar.html"), ("Find a bill", "/bills.html")]),
     step("Decide how to take part",
          "<p>Legislative committee meetings, executive sessions included, are open to the "
          "public, with narrow exceptions in the law, and anyone may record them. You can:</p><ul>"
          "<li><b>go in person</b>, to the building and room the notice names. How Public "
          "Hearings Work explains the buildings;</li>"
          "<li><b>watch</b>: the House and the Senate live stream their standing "
          "committees&rsquo; hearings, and a bill&rsquo;s page here links the recording where "
          "there is one; or</li>"
          "<li><b>sign in or send your position in writing</b>, with or without going: the House "
          "and the Senate both take sign-ins online, and written testimony goes to the "
          "committee&rsquo;s members by email, or on paper at the hearing.</li></ul>",
          actions=[("The buildings", "/guides/testifying.html#s-how-hearings-are-announced"),
                   ("Submit testimony", "/guides/submit-testimony.html")],
          law=["RSA 91-A:1-a, VI(a)", "RSA 91-A:2, II"]),
     step("Ask to speak",
          SAID["ask-to-speak"],
          actions=[("Speaking at the hearing", "/guides/testifying.html#s-speaking-at-the-hearing")]),
     step("When you speak",
          "<p>When the chair calls you, say who you are, where you live and whether you speak "
          "for an organization, then whether you support or oppose the bill, and why. The most "
          "useful testimony is specific: what the bill would do to you, in your town.</p>"
          "<p>In practice:</p><ul>"
          + SAID["notes"]
          # Testifying and Attending says this under Written Testimony, in
          # the other guide's words (SAID["paper"]).
          + "<li><b>Paper copies are optional.</b> To hand the committee written testimony, bring "
          "one printed copy for each member; they will take them and pass them around.</li>"
          + SAID["last-call"] + "</ul>",
          actions=[("Written testimony", "/guides/submit-testimony.html")]),
     step("After the hearing",
          SAID["exec-session"]
          + "<p>The recommendation, such as Ought to Pass or Inexpedient to Legislate, goes to the "
          "full chamber. If the bill passes, a committee of the other chamber holds its own "
          "hearing on it.</p>",
          actions=[("How a bill becomes law", "/learn/how-a-bill-becomes-law.html")])],
    [("House Calendars No. 23 (1997), No. 7 (2021), No. 8 (2025) and Nos. 2 and 6 (2026), Senate "
      "Calendars No. 20 (2025) and No. 3 (2026), House Journal No. 2 (2025) and Senate Journals "
      "No. 1 (2022 and 2024): open them from the Calendar's Calendars & Journals", DOCS),
     civics.SRC_SENATE_GUIDANCE,
     ("How Public Hearings Work", "/guides/testifying.html"),
     ("Right-to-Know Law, RSA 91-A", "/laws/91-a"),
     (OBSERVED, "")],
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
          "/guides/using-this-site.html", READ),
     ours("The Calendar shows the week's hearings by committee.", "/calendar.html", READ),
     # Only what that page says that this guide does not source itself: how
     # each chamber takes a request to speak is the record's and the
     # practice's below, which the page draws from here (SAID, 23 October 2026).
     ours("How Public Hearings Work explains the buildings the notices name, and that the most "
          "useful testimony is concrete.", "/guides/testifying.html", READ),
     ours("A bill that passes is referred to a committee of the second chamber, which holds its own "
          "public hearing.", "/learn/how-a-bill-becomes-law.html", READ),
     # The second pass (17 October 2026): the Senate's guidance and notices,
     # the House's pink card, the executive-session line, and the practice.
     SENATE_ONLINE,
     record("The Senate's guidance: spoken testimony is given in person at the State House complex, "
            "signing up on the sheets in the committee rooms on the day of the hearing.",
            GUIDANCE, SENATE_GUIDANCE,
            ["All spoken testimony before the committee will be done in person at the State House "
             "Complex", "please use the sign-up sheets provided in the committee rooms on the day of "
                        "the hearing"], READ),
     record("A Senate notice: those who wish to speak sign up in person.",
            "Senate Calendar No. 20, May 8, 2025, p. 24", SC20_25,
            "Individuals who wish to speak will need to sign up in person", READ),
     record("The House's ways of taking part in a hearing include a pink card and a blue sheet, for "
            "which the remote hearings of 2021 needed equivalents.",
            "House Calendar No. 7, January 15, 2021, p. 1", HC7_21,
            "hearing participation (pink card equivalent, blue sheet equivalent", READ),
     record("Some notices give one block of time to executive session on pending legislation, "
            "naming no bill.", "Senate Calendar No. 20, May 8, 2025, p. 24", SC20_25,
            ["JUDICIARY, Room 100, SH", "1:00 p.m. EXECUTIVE SESSION ON PENDING LEGISLATION"], READ),
     record("The first House calendar on this disk to print the line in full: executive session on "
            "pending legislation may be held throughout the day, time permitting, from the time the "
            "committee is initially convened.", "House Calendar No. 23, February 19, 1997, p. 13",
            HC23_97, EXEC_THROUGHOUT, READ),
     record("House notices still print it in 2026, as Education Policy and Administration's of "
            "January 2026 does.", "House Calendar No. 2, January 9, 2026, p. 4", HC2_26,
            ["EDUCATION POLICY AND ADMINISTRATION, Room 232, GP", EXEC_THROUGHOUT], READ),
     observed("A committee meeting never starts before the time its notice gives, and often starts "
              "later: an earlier hearing ran long, or a lunch break or a caucus before the meeting "
              "ran over.", READ),
     observed("House: a stack of pink cards on a table and a registration sheet near the front of "
              "the room; anyone may sign the sheet with their name and position; to speak, a pink "
              "card handed to a staff member or a committee member, who passes it to the chair.", READ),
     observed("Senate: the sign-up sheet has a box to mark if you want to speak.", READ),
     observed("The prime sponsor usually speaks first to introduce the bill, and is not held to a "
              "time limit.", READ),
     observed("No rule sets a time limit: whether to set one, and when to stop a speaker, is the "
              "chair's call. With a few "
              "speakers often no limit; with many, more than about ten, two or three minutes each, "
              "and no repeating points already made several times.", READ),
     observed("Speakers may read from prepared notes or a phone; no props while testifying; signs in "
              "the hallways, not in the committee room.", READ),
     observed("Written testimony on paper: one printed copy for each member, taken and passed "
              "around; paper copies are optional.", READ),
     observed("Before closing, the chair usually asks whether anyone who has not yet spoken would "
              "like to speak on the bill; if no one does, the hearing is closed.", READ),
     observed("Where a notice gives one block of time to executive session, the chair takes up the "
              "bills in any order; the throughout-the-day line makes it hard to know when a vote "
              "happened until afterward.", READ)]
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
    more=civics.faq(
        ("Will the hearing start at the time in the notice?", SAID["starts-late"]),
        ("Who speaks first, and how long can I speak?",
         "<ul>" + SAID["sponsor-first"] + SAID["chair-time"] + "</ul>"),
        ("Can I bring a sign or props?", "<ul>" + SAID["props"] + "</ul>"),
        ("Why can&rsquo;t I tell when the committee will vote?", SAID["throughout-the-day"]),
        ("Is there a record of who spoke?",
         "<p>In the Senate, the committee&rsquo;s hearing report lists who supported, opposed "
         "or was neutral on the bill and summarizes the testimony.</p>")),
    see=[("How public hearings work", "/guides/testifying.html"),
         ("How to submit testimony online or in writing", "/guides/submit-testimony.html"),
         ("How to contact your legislators", "/guides/contact-your-legislators.html"),
         ("Using this site", "/guides/using-this-site.html")],
    # Senate Rule 4-1's notice period, in the words of the journal that prints it.
    figures=[fig("4 days", "Senate Journal No. 1, December 7, 2022, p. 21",
                 "advertised at least 4 days before such hearing in the Senate Calendar")])


# ---------------------------------------------------------------------------
# SUBMITTING TESTIMONY ONLINE OR IN WRITING (17 October 2026). The House's
# online form is described from the House's own records of it: the calendar
# notices that name it and say where its submissions go, and the columns and
# choices of the sign-in table in the Court's database. No name or word of
# anyone's testimony is read into this file or printed by the guide; the
# words checked are the form's own choices. The Senate's form is described
# from the Senate's own guidance for the public and its calendar of May 2025,
# and the two chambers' forms' closing time and testimony on paper from the
# person's account, as practice (the second pass, 17 October 2026).
# ---------------------------------------------------------------------------
TESTIMONY = guide(
    "submit-testimony", "How to Submit Testimony Online or in Writing",
    "Registering your position on a bill and sending a committee written testimony without "
    "going to Concord, and when to send it.",
    "The House and the Senate both take sign-ins online: you say whether you support or oppose "
    "a bill, and on the House&rsquo;s form you can attach written testimony. To give a "
    "committee written testimony, email its members, or bring one printed copy for each member "
    "to the hearing. You can sign in once the hearing is scheduled, and in practice the forms "
    "close at midnight at the end of the day of the hearing. Send it early: a committee may "
    "vote as soon as its hearing ends.",
    [box("Find the hearing: which committee, and which day."),
     box("Sign in online, House or Senate: for, against or neutral, once the hearing is "
         "scheduled."),
     box("Written testimony: email the committee&rsquo;s members, or bring a printed copy for "
         "each."),
     box("Send it before the hearing. The committee may vote the same day.")],
    [step("Find the hearing",
          "<p>Open the bill&rsquo;s page here: it lists each hearing with the committee, the day "
          "and the time. The Calendar shows the week&rsquo;s hearings.</p>",
          actions=[("Find a bill", "/bills.html"), ("This week's hearings", "/calendar.html")]),
     step("Sign in online",
          "<p>Each chamber has its own online form on the General Court&rsquo;s website, and each "
          "sign-in is for one bill at one committee&rsquo;s hearing on one day. "
          + SAID["window"] + "</p>"
          "<p>Each form asks who you are, whom you represent, if anyone, and whether you "
          "support the bill, oppose it or are neutral; the questions below say what else.</p>",
          actions=[("House sign-in", HOUSE_SIGNIN), ("Senate sign-in", SENATE_SIGNIN)]),
     step("Write it so it is useful",
          "<p>Start with the bill&rsquo;s number, HB or SB and then the number, and say whether "
          "you support or oppose it. Then say why in a few specific sentences: what the bill "
          "would do to you, your family, your work or your town. If you write for an "
          "organization, say so.</p>"),
     step("Send it before the hearing",
          "<p>A committee can vote as soon as its hearing "
          "ends: Senate notices often say &ldquo;executive session may follow&rdquo;, and a House "
          "committee may meet in executive session straight after a noticed hearing. So send "
          "your testimony before the hearing, as soon as you can once it is scheduled.</p>"),
     step("Email it, or bring it on paper",
          SAID["email"] + SAID["paper"],
          actions=[("Committees", "/committees.html")])],
    [("House Calendars No. 8 and No. 14 (2025), House Journal No. 2 (2025) and Senate Calendars "
      "No. 20 (2025) and No. 3 (2026): open them from the Calendar's Calendars & Journals", DOCS),
     civics.SRC_SENATE_GUIDANCE,
     civics.SRC_TESTIFY,
     civics.SRC_SENATE_TESTIFY,
     ("How Public Hearings Work", "/guides/testifying.html"),
     (OBSERVED, "")],
    [],
    [ours("A bill's page lists each hearing with the committee, day and time.",
          "/guides/using-this-site.html", READ),
     ours("The Calendar shows the week's hearings.", "/calendar.html", READ),
     record("The House's online form is its House Sign-in Form and Online Testimony Submission, on "
            "the General Court website, for bills coming up for a public hearing.",
            "House Calendar No. 8, January 17, 2025, p. 1", HC8,
            "submit testimony online for bills coming up for a public hearing using our House Sign-in "
            "Form and Online Testimony Submission on the General Court website", READ),
     ours("How Public Hearings Work links the House online testimony sign-in; a sign-in for or "
          "against is part of the record and counted; specific testimony is the most useful; this "
          "site publishes the counts, not names or written testimony.", "/guides/testifying.html", READ),
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
            "them at once.", "/guides/your-representatives.html", READ),
       # The second pass (17 October 2026): the Senate's own form and
       # guidance, and the practice of both chambers' forms and of paper.
       SENATE_ONLINE,
       record("The Senate's form registers support or opposition on a bill with a public hearing "
              "scheduled, from the moment it is scheduled and not before; signing in well ahead is "
              "encouraged.", GUIDANCE, SENATE_GUIDANCE,
              ["To register support or opposition on a bill that has a public hearing scheduled",
               "remotecommittee/senate.aspx",
               "This online form will allow you to sign in on a bill as soon as it has been "
               "scheduled for a hearing", "If no hearings are scheduled, no positions can be registered",
               "You are encouraged to sign in well in advance of the hearing"], READ),
       record("The Senate's form: the day, the committee and the bill; a category of elected "
              "official, lobbyist, agency staff or member of the public; whom you represent; support, "
              "oppose or neutral; name and contact information; a confirmation page that says how "
              "to send testimony.", GUIDANCE, SENATE_GUIDANCE,
              ["Click on the date that the bill you are interested in is being heard",
               "Select the committee that is hearing the bill", "Select the bill you are interested in",
               "Select a category (elected official, lobbyist, agency staff, member of the public)",
               "If you are representing an entity or someone other than yourself",
               "Indicate whether you support, oppose or are neutral on the bill",
               "Enter your name and contact information",
               "the confirmation page will include instructions for submitting testimony"], READ),
       record("The Senate's guidance: written testimony goes to the committee through the Email All "
              "Committee Members link on the committee's web page.", GUIDANCE, SENATE_GUIDANCE,
              ["Written testimony should be submitted to the committee via the",
               "Email All Committee Members", "link found on the relevant committee web page"], READ),
       observed("The House's online sign-in, like the Senate's, opens when the hearing is scheduled; "
                "both close at midnight at the end of the day of the hearing.", READ),
       observed("Written testimony may be brought on paper, one printed copy for each committee "
                "member, which they take and pass around; paper copies are optional.", READ)],
    more=civics.faq(
        ("What exactly does each sign-in form ask for?", SAID["forms"]),
        ("Is my sign-in counted, and does this site publish it?",
         "<p>Each online sign-in is kept in the House&rsquo;s database with its hearing, "
         "committee and bill, and committee members can read the submissions bill by bill. For "
         "House hearings this site publishes only how many people signed in supporting, opposing "
         "and neutral, never names or written testimony.</p>"),
        ("When do committee members see what I submit online?",
         "<p>Committee members can read what is submitted online in the House&rsquo;s portal, "
         "bill by bill, and are sent links to it at the end of each day their committee holds "
         "hearings.</p>")),
    see=[("How public hearings work", "/guides/testifying.html"),
         ("How to attend and speak at a public hearing", "/guides/attend-a-hearing.html"),
         ("How to contact your legislators", "/guides/contact-your-legislators.html"),
         ("Using this site", "/guides/using-this-site.html"),
         ("Finding your representatives", "/guides/your-representatives.html")])


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
    "email address they list with the General Court. Say where you live, "
    "name the bill by its number, say how you want them to vote, and send it before the "
    "vote.",
    [box("Find who represents your town: one senator, and one or more representatives."),
     box("Choose email or a call. Nearly every member lists an email address; the General "
         "Court&rsquo;s member list carries the phone numbers they give it."),
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
          "<p>A member&rsquo;s page here, and your town&rsquo;s page, give the email address the "
          "member lists with the General Court, which nearly every member does. This site does "
          "not repeat members&rsquo; phone numbers, because many are personal ones; the General "
          "Court&rsquo;s own member list carries the numbers they give it, and senators list an "
          "office in Concord. To write to every member of a committee at once, use the button on "
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
     ("Finding Your Representatives", "/guides/your-representatives.html"),
     ("House Calendar No. 6 (2026) and Senate Journal No. 1 (2022): open them from the Calendar's "
      "Calendars & Journals", DOCS)],
    ["662"],
    [claim("The state is divided into 24 senatorial districts, each electing one senator.", "RSA 662:3", READ),
     claim("The state is divided into districts for state representatives, each electing the number "
           "set forth opposite it.", "RSA 662:5", READ),
     ours("A floterial district is laid over two or more House districts and elects additional "
          "members; a town's page and the town finder name its districts and members; committee "
          "pages have a button that emails all their members.", "/guides/your-representatives.html", READ),
     ours("My Town shows who represents a town; a member's page and a town's page give the email the "
          "member lists.", "/officials.html", READ),
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
    see=[("Finding your representatives", "/guides/your-representatives.html"),
         ("How to submit testimony online or in writing", "/guides/submit-testimony.html"),
         ("How to attend and speak at a public hearing", "/guides/attend-a-hearing.html")],
    figures=[fig("24 Senate districts", "RSA 662:3",
                 "The state is divided into 24 districts for the choosing of state senators")])


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
          actions=[("Reading the shorthand", "/guides/using-this-site.html#s-reading-the-shorthand")],
          law=["RSA 14:48"]),
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
          "through</s>] are words being removed.</li>"
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
          "estimate; if less, it says so.</p>",
          law=["RSA 14:44", "RSA 14:46", "RSA 14:47"])],
    [("HB 1001 of 2024 (Granite Record)", "/bill/2024/hb1001.html"),
     ("House Calendars No. 5 (December 27, 2024) and No. 6 (2026), Senate Calendar No. 3 (2026) "
      "and Senate Journal No. 1 (2022): open them from the Calendar's Calendars & Journals", DOCS),
     ("Legislative Officers and Proceedings, RSA 14", "/laws/14"),
     ("Using This Site", "/guides/using-this-site.html")],
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
          "the text and its amendments.", "/guides/using-this-site.html", READ),
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
             # Quoted from the saved page, not this site's CSS: each line is split
             # after "font-" so the rule that every size here is in rem does not
             # take the General Court's own stylesheet for ours (17 October 2026).
             ".cs22FF6315{color:#000000;background-color:transparent;font-family:'Century "
             "Schoolbook';font-" "size:10pt;font-weight:bold;font-style:italic;}",
             ".csDD5E5F52{color:#000000;background-color:transparent;font-family:'Century "
             "Schoolbook';font-" "size:10pt;font-weight:normal;font-style:normal;}"], READ),
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
    more=civics.faq(
        ("What is the number at the top of the text, like 24-2288?",
         "<p>Before a bill has a number it is a Legislative Service Request, or LSR: a "
         "legislator&rsquo;s request, which the Office of Legislative Services drafts into a "
         "bill. When the bill is introduced it gets its number, and its text keeps the "
         "request&rsquo;s number near the top: HB 1001 of 2024 prints 24-2288, the "
         "session&rsquo;s year and then the request&rsquo;s own number. While requests for the "
         "next session are being filed, this site&rsquo;s <a href=\"/bills.html\">bill search</a> "
         "lists them by title and "
         "prime sponsor.</p>"),
        ("Is there a bill I can look at as an example?",
         "<p>In HB 1001 of 2024, the first section prints a paragraph of current law in regular "
         "type with one phrase in bold italics: the addition.</p>"),
        ("Who writes the fiscal note?",
         "<p>The Office of Legislative Budget Assistant prepares it and names its sources, and "
         "the note is corrected to match the bill as it is amended.</p>"),
        ("What does a fiscal note show?",
         "<p>The note marks whether the state, counties or local governments are affected, "
         "estimates the change in appropriations, revenue and spending by fiscal year, and "
         "explains how under Methodology. An effect it cannot put a number on may be called "
         "indeterminable.</p>")),
    see=[("Reading the shorthand", "/guides/using-this-site.html#s-reading-the-shorthand"),
         ("How a bill becomes law", "/learn/how-a-bill-becomes-law.html"),
         ("Glossary", "/learn/glossary.html"),
         ("How to contact your legislators", "/guides/contact-your-legislators.html")],
    figures=[fig("$10,000", "RSA 14:44", "total fiscal impact of $10,000 or more")])

CIVIC = [HEARING, TESTIMONY, CONTACT, READ_BILL]


GUIDES = [VOTING, PUBLIC_RECORD, ENERGY, VITAL, ABATEMENT, LMI] + CIVIC


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
# day go in without touching these. Their claims carry READ, the day defined
# above for the four civic guides, which is the day these were read too.
# ---------------------------------------------------------------------------
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
# appointments and fees pages, and RSA 263. The fees are printed because RSA
# 263:42 and 260:21 set them, and the DMV's fee table says the same; the
# others, which the fact check of 17 October 2026 found the guide silent on
# while it described a non-driver ID, are linked. The DMV mails its
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
    "DMV office. A driver&rsquo;s license renewal costs $50, or $60 for a REAL ID license; a "
    "non-driver ID card costs $20.",
    [ask("Does your renewal notice say you can renew online?",
         [("Yes", "Renew online with the Renewal Identification Number on the notice."),
          ("No, or no notice", "Make an appointment at a DMV office and bring what it asks for.")]),
     box("Getting a REAL ID for the first time? That renewal is in person."),
     # No claim of this guide gives the paper license's 60 days, which the
     # DMV's page for new residents does (NEW_RESIDENT), so it is not printed
     # here (COUNT, 23 October 2026); the card's 60 days are DMV_ONLINE's.
     box("Online, you print a temporary license to carry with your old card, and the new card "
         "comes by mail within 60 days.")],
    [step("Watch for your renewal notice",
          "<p>About two months before your license expires, the DMV mails a renewal notice to the "
          "address it has for you.</p>",
          actions=[("License renewal (DMV)", DMV_RENEW)]),
     step("Renew online, if your notice says you can",
          "<p>You need:</p><ul>"
          "<li>the <b>Renewal Identification Number</b> from your notice, which works from 60 days "
          "before your birthday to 60 days after it;</li>"
          "<li>your current license in hand, because you will type in details printed on it;</li>"
          "<li>a MasterCard, VISA, Discover or American Express card; and</li>"
          "<li>a printer, to print the temporary license you carry with your old card until the "
          "new one arrives.</li></ul>",
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
          "<p>A renewed driver&rsquo;s license costs $50, or $60 for a REAL ID license, and a "
          "non-driver ID card costs $20. The law sets all three. The DMV takes credit "
          "cards, cash in person, and checks or money orders payable to &ldquo;State of NH - "
          "DMV&rdquo;.</p>",
          actions=[("All licensing fees", DMV_FEES)], law=["RSA 263:42, I", "RSA 260:21"]),
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
           "one to three years, three years or more, with the tests; a non-driver ID renews online "
           "if eligible or by appointment with the DSMV 450 and proof of identity and residency; a "
           "CDL renews only by appointment, with the DSMV 312, the current CDL, the fee, a vision "
           "test and a valid medical certificate unless exempt.", DMV_RENEW, READ),
     claim("Online: the RIN on the notice, valid 60 days before and after the birthday; only you "
           "can renew your own; have the current card; MasterCard, VISA, Discover or American "
           "Express; print the temporary, which with the old card serves until the new one is "
           "mailed within 60 days; the current photo is reused; a first REAL ID is in person.",
           DMV_ONLINE, READ),
     claim("The DMV is fully appointment based; book online or call 603-227-4000.", DMV_APPT, READ),
     claim("Payment by credit card, cash in person, or check or money order payable to State of NH "
           "- DMV; $50 operator, $60 REAL ID operator, $20 non-driver ID, and the youth, non-US "
           "citizen, motorcycle and CDL fees.", DMV_FEES, READ),
     claim("A license expires on the fifth anniversary of the holder's birth date following issue; "
           "online renewal only once in every other renewal cycle, the next in person.",
           "RSA 263:10", READ),
     claim("$60 for a Real ID Act compliant license, $50 for each other license, original or "
           "renewal.", "RSA 263:42", READ),
     claim("The fee for a nondriver's picture identification card is $20, not refundable.",
           "RSA 260:21", READ)],
    more=civics.faq(
        ("Why didn&rsquo;t I get a renewal notice?",
         "<p>You will not get one if your mail is forwarded, if you moved and did not tell the DMV "
         "your new address, or if your license is suspended.</p>"
         "<p>The expiration date is printed in red on the front of your license.</p>"),
        ("Can I renew online every time?",
         "<p>Only you can renew your own license, and your current photo is reused. The law allows "
         "an online renewal only every other time, so the renewal after an online one is in "
         "person.</p>"),
        ("How do I renew a non-driver ID or a commercial license?",
         "<p>A non-driver ID card renews the same two ways: online if your notice allows, or by "
         "appointment with the same application and proof of your identity and residence. A "
         "commercial driver&rsquo;s license is renewed only by appointment, on its own "
         "application (form DSMV 312), with a valid medical certificate unless you are "
         "exempt.</p>"),
        ("What do other kinds of license cost?",
         "<p>Other licenses cost different amounts, among them youth, motorcycle and commercial "
         "licenses and a license for someone who is not a U.S. citizen; the DMV&rsquo;s fees page "
         "lists them.</p>")) + DMV_HELP,
    see=[("How to get a REAL ID", "/guides/real-id.html"),
         ("New to New Hampshire: license, registration and voting", "/guides/new-to-new-hampshire.html")],
    figures=[fig("$60", "RSA 263:42", "$60 for a Real ID Act compliant license"),
             fig("$50", "RSA 263:42", "$50 for each other license"),
             fig("$20", "RSA 260:21", "The fee for such card shall be $20"),
             fig("60 days", DMV_ONLINE, "valid 60 days before and after the birthday"),
             fig("60 days", DMV_ONLINE, "mailed within 60 days")])


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
          "<li><b>From a private seller:</b> the title, properly signed over to you.</li></ul>"
          "<p>A vehicle exempt from titling, or one leased or financed out of state, needs "
          "something different: the questions below say what.</p>",
          actions=[("Vehicle registrations", DMV_REG), ("VIN verification form", DMV_VIN),
                   ("Temporary plates", DMV_TEMP_PLATES)],
          law=["RSA 261:148"]),
     step("Start at your town or city clerk",
          "<p>Every motor vehicle except a moped starts at the clerk&rsquo;s office of the town or "
          "city where you live. The clerk confirms your residence and issues the town&rsquo;s "
          "permit, which the state needs before it will register the vehicle.</p>",
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
          "renew, go to your town or city and pay the town&rsquo;s fees first; many towns can "
          "take the state&rsquo;s part as well.</p>",
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
           "online or mail.", DMV_REG, "2026-10-26"),
     claim("New/Transfer Registration (state portion only) and Registration Renewal (state portion "
           "only): drop box or appointment.", DMV_APPT, READ),
     # As the license guide read it.
     claim("The DMV is fully appointment based; book online or call 603-227-4000.", DMV_APPT, READ),
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
    more=civics.faq(
        ("My vehicle is exempt from titling. What do I bring?",
         "<p>If you bought it from a private seller: a bill of sale with the details the law "
         "lists, and proof of the vehicle identification number (VIN): the title or a copy, a past "
         "New Hampshire registration or a copy, or the DMV&rsquo;s VIN verification form.</p>"),
        ("My vehicle is leased or financed through a lender in another state. Where do I start?",
         "<p>If the vehicle is leased or financed through a lender in another state, start with "
         "the DMV&rsquo;s page on 60-day temporary plates.</p>"),
        ("How is the town&rsquo;s fee figured?",
         "<p>The town&rsquo;s fee is set by law from the maker&rsquo;s list price, and gets "
         "smaller as the vehicle ages.</p>"),
        ("Can I renew online or by mail?",
         "<p>Ask your clerk or tax collector whether your town takes renewals online or by "
         "mail.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Your town or city clerk is the place to start, and can tell you what your town asks "
         "for and whether it does the state&rsquo;s part. The Division of Motor Vehicles answers "
         "questions at 603-227-4000.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_CLERKS}" target="_blank" rel="noopener">'
         "Find your town or city clerk</a></p>",
    see=[("New to New Hampshire: license, registration and voting", "/guides/new-to-new-hampshire.html")],
    figures=[fig("60-day", DMV_REG, "the 60-day temporary plate page")])


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
    "office, when you renew or by appointment, with documents proving your identity, your "
    "citizenship, your Social Security number and that you live in New Hampshire.",
    [ask("Will you fly within the U.S. or enter secure federal buildings without a passport?",
         [("Yes", "Consider a REAL ID, and plan at least three months ahead."),
          ("No", "You might not need one. A card without the star says Not for Federal "
                 "Identification.")]),
     box("Want one? Check which documents to bring, then make a DMV appointment."),
     box("Go in person: a first REAL ID cannot be done online.")],
    [step("Decide whether you need one",
          "<p>A REAL ID license or ID has a star in the top right corner. Since May 7, 2025, you "
          "need one, or a passport or another accepted ID, to board a domestic flight or enter a "
          "secure federal facility such as a military base or a courthouse.</p>"
          "<p>REAL ID is voluntary in New Hampshire.</p>",
          actions=[("REAL ID (DMV)", DMV_REALID), ("REAL ID (TSA)", TSA_REALID)]),
     step("Gather your documents",
          "<p>The law asks for documents proving your identity, your United States citizenship, "
          "your Social Security number, and that you live in New Hampshire. The DMV&rsquo;s "
          "online document checker shows what to bring for your situation. If you are not a "
          "U.S. citizen, the DMV lists what to bring on its own page.</p>",
          actions=[("Online document checker", DMV_DOC_CHECK), ("The list of documents", DMV_REALID_DOCS),
                   ("If you are not a U.S. citizen", DMV_NON_US)],
          law=["RSA 263:14-b", "RSA 260:21-a"]),
     step("Make an appointment",
          "<p>You can get a REAL ID when you renew, or upgrade before then by appointment. The DMV "
          "suggests booking at least three months before you need it. Bring the application for "
          "your kind of license (form DSMV 450 for a driver&rsquo;s license or non-driver ID) with "
          "your documents. A first REAL ID cannot be done by online renewal.</p>",
          actions=[("Make an appointment", DMV_APPT), ("Application (DSMV 450)", DMV_APP)]),
     step("Pay the fee",
          "<p>At renewal, a REAL ID driver&rsquo;s license costs $60, against $50 for a "
          "driver&rsquo;s license without the star. For a non-driver ID card, the law sets $10 "
          "for a REAL ID card and $20 for one without the star. The DMV&rsquo;s fees page "
          "gives what it charges.</p>",
          actions=[("Licensing fees", DMV_FEES)],
          law=["RSA 263:42, I", "RSA 260:21-a", "RSA 260:21"])],
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
     claim("Upgrade to REAL ID outside renewal by appointment; a renewal may upgrade; the DMV is "
           "fully appointment based; book online or call 603-227-4000.", DMV_APPT, READ),
     claim("Renew by appointment with the DSMV 450; a non-driver ID renews by appointment with "
           "the DSMV 450 and proof of identity and residency.", DMV_RENEW, READ),
     claim("A license that complies with Public Law 109-13 to a resident who provides documents "
           "required to demonstrate identity, United States citizenship, social security number, "
           "and New Hampshire residency.", "RSA 263:14-b", "2026-10-26"),
     claim("A nondriver's picture identification card that complies with Public Law 109-13: "
           "documents to demonstrate identity, United States citizenship, social security "
           "number, and New Hampshire residency; the fee for such card shall be $10.",
           "RSA 260:21-a", "2026-10-26"),
     claim("Enforcement began May 7, 2025; REAL ID compliant to board domestic flights and access "
           "certain federal facilities; a star; a passport is acceptable; travelers without an "
           "acceptable ID pay a fee.", TSA_REALID, READ),
     claim("Operator $50, REAL ID operator $60, non-driver ID $20, and the other licenses' fees.",
           DMV_FEES, READ),
     claim("$60 for a Real ID Act compliant license, $50 for each other license.", "RSA 263:42", READ),
     claim("Application for Driver License or Non-Driver ID Card; I am applying for: Opt-in Real "
           "ID, yes or no; an original license, a renewal or a non-driver ID card.", DMV_APP,
           "2026-10-26"),
     claim("The fee for a nondriver's picture identification card, marked not acceptable for "
           "federal identification purposes, is $20, not refundable.", "RSA 260:21", "2026-10-26")],
    more=civics.faq(
        ("What if I do not get a REAL ID?",
         "<p>A card without the star is marked &ldquo;NOT FOR FEDERAL IDENTIFICATION&rdquo;, and "
         "you would show a passport or another accepted ID for those purposes instead. The "
         "Transportation Security Administration charges a fee to travelers who arrive without an "
         "accepted ID.</p>"),
        ("My name has changed. What do I bring?",
         "<p>If your name has changed, through marriage, divorce, adoption or otherwise, your "
         "birth certificate or passport will show a different name, so bring proof of each change "
         "that links it to your current name. The document checker&rsquo;s Name Change Wizard "
         "helps.</p>"),
        ("Does it cost more to upgrade before my renewal is due?",
         "<p>If you upgrade before your renewal is due, the DMV also charges a replacement fee, "
         "which its REAL ID page gives.</p>"),
        ("What do other kinds of license cost?",
         "<p>Other licenses cost different amounts; the DMV&rsquo;s fees page lists them.</p>"))
         + DMV_HELP,
    see=[("How to renew your driver's license", "/guides/renew-drivers-license.html")],
    figures=[fig("$60", "RSA 263:42", "$60 for a Real ID Act compliant license"),
             fig("$50", "RSA 263:42", "$50 for each other license"),
             fig("$20", "RSA 260:21", "The fee for such card shall be $20"),
             fig("$10", "RSA 260:21-a", "The fee for such card shall be $10")])


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
          "principal place of physical presence, to the exclusion of every other.</p>",
          actions=[("New to New Hampshire (DMV)", DMV_NEW)]),
     step("Get a New Hampshire driver's license",
          "<p>If you drive in New Hampshire, get a New Hampshire license within 60 days. If you do "
          "not drive here, you do not need one.</p>"
          "<p>Make an appointment at a DMV office, and bring the completed application (form DSMV "
          "450), proof of your identity and residence for the kind of license you want (a REAL ID "
          "or not), and the fee; there is a vision test. You must hand in every license from "
          "another state. You leave with a 60-day paper license, and the card comes by mail within "
          "60 days. If you are not a U.S. citizen, the DMV&rsquo;s page explains where to "
          "apply.</p>",
          actions=[("Transfer a license from another state", DMV_TRANSFER),
                   ("Make an appointment", DMV_APPT), ("If you are not a U.S. citizen", DMV_NON_US)],
          law=["RSA 263:35, I", "RSA 263:4"]),
     step("Register your vehicle",
          "<p>If you own a vehicle you use in New Hampshire, register it here within 60 days. Take "
          "the title and proof of your residence to the clerk&rsquo;s office of the town or city "
          "where you live. Fees differ for each vehicle, so ask your clerk.</p>",
          actions=[("Find your town or city clerk", SOS_CLERKS)], law=["RSA 261:45, I"]),
     step("Register to vote",
          "<p>There is no minimum time you must live here before registering. You can register with "
          "your town or city clerk, or at a session of the supervisors of the checklist, until "
          "registration closes 6 to 13 days before an election, on a date your supervisors set. You "
          "can also register at your polling place on election day. Bring proof of your "
          "identity, age, citizenship and domicile; How to Vote lists what counts.</p>",
          actions=[("Register to vote", SOS_REGISTER)], law=["RSA 654:27"]),
     step("Keep your address up to date",
          "<p>Once you hold a New Hampshire license, notify the DMV in writing within 30 days "
          "whenever you change your name, your home or your mailing address. An address change "
          "can go through the "
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
     claim("Address change by drop box service; the DMV is fully appointment based; book "
           "online or call 603-227-4000.", DMV_APPT, READ),
     claim("Citizen, 18 on election day, resident of the town or ward, no minimum period; register "
           "with the clerk or supervisors 6 to 13 days before, or at the polls; proof of identity, "
           "age, citizenship and domicile.", SOS_REGISTER, READ),
     claim("A nonresident with a valid license from another jurisdiction has 60 days from "
           "establishing bona fide residency to obtain a NH license.", "RSA 263:35", READ),
     claim("No license until every other jurisdiction's license is surrendered.", "RSA 263:4", READ),
     claim("A new resident has 60 days from residency to register vehicles in NH.", "RSA 261:45", READ),
     claim("A licensed driver notifies the director in writing within 30 days of a change of "
           "legal name, permanent residence or mailing address.", "RSA 263:9", READ),
     claim("The supervisors' session for correcting the checklist, at which hearings close, is on "
           "a day they designate 6 to 13 days before the election.", "RSA 654:27", COUNTED)],
    more=civics.faq(
        ("What shows that New Hampshire is my home?",
         "<p>Actions such as buying or leasing your main house or apartment, registering a "
         "vehicle here, putting your children in a public school, or registering to vote show "
         "that you have made it your home.</p>"),
        ("Can I keep driving on my out-of-state license until then?",
         "<p>The DMV lists a few kinds of out-of-state license that are not valid for driving in "
         "New Hampshire, on its page about transferring a license.</p>"),
        ("My vehicle is leased, financed or exempt from titling. What do I bring?",
         "<p>If the vehicle is leased, financed, or exempt from titling, bring your registration "
         "from the other state, the lease if there is one, your lender&rsquo;s name and address, "
         "and proof of residence. The clerk prepares a New Hampshire title application.</p>"),
        ("Do I need a New Hampshire license to vote?",
         "<p>You do not need a New Hampshire driver&rsquo;s license to register or to vote.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Your town or city clerk handles both your vehicle registration and your voter "
         "registration. The Division of Motor Vehicles answers licensing questions at "
         "603-227-4000.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_CLERKS}" target="_blank" rel="noopener">'
         "Find your town or city clerk</a></p>",
    see=[("How to vote in New Hampshire", "/guides/how-to-vote.html"),
         ("How to register a car", "/guides/register-a-car.html"),
         ("How to get a REAL ID", "/guides/real-id.html")],
    figures=[fig("60 days", "RSA 263:35", "a maximum of 60 days from the date his or her residency "
                                          "was established"),
             fig("60 days", "RSA 261:45", "a maximum of 60 days from the date of his or her residency "
                                          "in which to register"),
             fig("60-day", DMV_NEW, "a 60-day paper temporary"),
             fig("6 to 13 days", "RSA 654:27", "6 to 13 days prior to the election"),
             fig("30 days", "RSA 263:9", "notify the director in writing of such change within 30 days")])


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
          "size, income, expenses and resources.</li>"
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
          "800MA.</p>",
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
          "your District Office, mail it to the Administrative Appeals Unit, or email it.</p>"
          "<p>Generally you have 30 days from the date on your Notice of Decision, or 90 days for "
          "SNAP. You do not need a lawyer.</p>",
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
    more=civics.faq(
        ("Can I get SNAP if I own a home, or have no children?",
         "<p>You may qualify whether you own a home, have none, live alone or with others, and "
         "whether or not you work or have children.</p>"),
        ("Can I get a SNAP application by mail?",
         "<p>For SNAP, you can also call 603-271-9700 to have an application mailed to you.</p>"),
        ("What if someone is helping me apply?",
         "<p>If someone is helping you apply, you both fill in the Authorized Representative "
         "Declaration (Form 778).</p>"),
        ("Can I keep my benefits while I appeal?",
         "<p>If you appeal within 15 days, you may in some cases keep your benefits at the same "
         "level until the appeal is decided, but must repay them if the Department&rsquo;s "
         "decision is upheld.</p>"),
        ("What if I cannot write my appeal?",
         "<p>If you cannot write, tell a Department representative that you want to "
         "appeal.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>The Department&rsquo;s customer service center answers questions about applying, and "
         "your local District Office can help in person.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{DHHS_OFFICES}" target="_blank" rel="noopener">'
         "Find your District Office</a></p>"
         "<p>For help with an application, someone to talk your options through with, and free "
         "legal help if a benefit is denied or cut:</p>"
         + helps("nheasy", "adrc", "legal_aid"),
    see=[("How to get help with heating and electric bills", "/guides/heating-and-electric-help.html")],
    # Federal law and the Department's own appeal rules, which no statute
    # table here holds: each count as the claim on the Department's page
    # records it.
    figures=[fig("aged 18", DHHS_SNAP, "ABAWDs 18 through 64"),
             fig("80 hours", DHHS_SNAP, "need 80 hours a month"),
             fig("30 days", DHHS_APPEALS, "generally 30 days from the Notice of Decision"),
             fig("90 days", DHHS_APPEALS, "90 for SNAP"),
             fig("15 days", DHHS_APPEALS, "within 15 days benefits may continue")])


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
          "claims on time.</p>"
          "<p>You must also have earned enough in a base period, usually the first four of the "
          "last five completed calendar quarters before your claim; New Hampshire Employment "
          "Security&rsquo;s eligibility page gives the amounts.</p>",
          actions=[("Unemployment eligibility", NHES_ELIG)],
          law=["RSA 282-A:31, I", "RSA 282-A:2"]),
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
          "part in activities that prepare you to go back to work.</p>"),
     step("If you disagree with a determination",
          "<p>Every determination on your claim is on your dashboard and explains how to appeal. "
          "You have 14 calendar days from when it was issued.</p>",
          actions=[("Unemployment appeals", NHES_APPEALS)], law=["RSA 282-A:48"])],
    [("File for Unemployment Benefits (New Hampshire Employment Security)", NHES_FILE),
     ("Unemployment Eligibility (New Hampshire Employment Security)", NHES_ELIG),
     ("Unemployment Appeals (New Hampshire Employment Security)", NHES_APPEALS),
     ("Unemployment Compensation, RSA 282-A", "/laws/282-a")],
    ["282-A"],
    # "What to have ready" names its 18 months since 23 October 2026, so the
    # count rests on the claim (COUNT): the words are the guide's own list,
    # which this claim was checked against, not a second reading of the page.
    [claim("Register or log in to Workforce Connect, File for Benefits, Apply for Unemployment "
           "Insurance Benefits, answer accurately, review and certify, print the confirmation; what "
           "to have ready, employers and a DD 214 from the last 18 months among it; a weekly work "
           "search unless notified of an exemption, contacting "
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
     claim("Base period means the first 4 of the last 5 completed calendar quarters immediately "
           "preceding the individual's benefit year; an alternate base period of the last 4 "
           "completed quarters for one who does not qualify under it.", "RSA 282-A:2",
           "2026-10-26"),
     claim("An appeal received or postmarked within 14 calendar days after the determination was "
           "mailed, extendable for sufficient grounds.", "RSA 282-A:48", READ)],
    more=civics.faq(
        ("Can I get unemployment if I work part-time?",
         "<p>Working part-time does not rule you out; working full-time does.</p>"
         "<p>If you work part-time, report your hours and earnings on the weekly claim.</p>"),
        ("Can a school employee get unemployment between terms?",
         "<p>School employees between terms are judged case by case.</p>"),
        ("What happens after I appeal?",
         "<p>After you appeal you will get an Appeal Request Notice, and the hearing is held by "
         "an Appeal Tribunal chairperson.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>New Hampshire Employment Security&rsquo;s unemployment hotline, (603) 271-7700, "
         "answers questions on weekdays from 8:00&nbsp;AM to 4:30&nbsp;PM. Its NH Works offices help in "
         "person, with claims and with finding work.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{NHES_OFFICES}" target="_blank" rel="noopener">'
         "NH Works offices</a></p>",
    see=[("How to apply for food or health assistance", "/guides/food-and-health-assistance.html"),
         ("How to get help paying for child care", "/guides/child-care-scholarship.html")],
    figures=[fig("14 calendar days", "RSA 282-A:48",
                 "within 14 calendar days after the determination was mailed"),
             fig("18 months", NHES_FILE, "from the last 18 months")])


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
    "candidacy in a filing period of about ten days in a state election year, in June through "
    "2026 and in March from 2028: with the "
    "Secretary of State for most offices, or with your town or city clerk if you are running for "
    "state representative. You pay a fee the law sets, or file petitions signed by voters of your "
    "party instead. Town and city offices are filed with your town or city clerk, on dates of "
    "their own.",
    [ask("Which office?",
         [("Governor, Congress, Executive Council, state senate or county",
           "File with the Secretary of State in the filing period."),
          ("State representative", "File in the filing period with the clerk of the town or "
                                   "city where you live."),
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
          actions=[("Qualifications for office", SOS_QUAL)], law=["RSA 655:2", "RSA 655:29"]),
     step("File in the filing period",
          "<p>To run in a party&rsquo;s primary you must be a registered member of that party. File "
          "a declaration of candidacy, with a statement of financial interests, between the first "
          "Wednesday in June and the Friday of the following week. In 2026 that was June 3 to June "
          "12. A filing on the last day must be made in person by the candidate, by 5:00&nbsp;PM.</p>"
          "<p>Candidates for governor, U.S. senator, U.S. representative, executive councilor, "
          "state senator and county office file with the Secretary of State. Candidates for state "
          "representative file with the clerk of the town or city where they live.</p>",
          actions=[("Running for office", SOS_RUN), ("Find your town or city clerk", SOS_CLERKS)],
          law=["RSA 655:14", "RSA 655:15"],
          note='From January 1, 2028, a law passed in 2026, <a href="/bill/2026/hb481.html">HB '
               '481</a> (chapter 44), moves the filing period to the first Friday in March and the '
               'Friday of the following week.'),
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
          "with the Secretary of State in the same filing period, pay the same fee, and file "
          "nomination papers signed by registered voters: 3,000 for governor or U.S. senator, 1,500 "
          "from each congressional district; 1,500 for U.S. representative; 750 for executive "
          "councilor or state senator; and 150 for state representative or county officer.</p>",
          actions=[("Running for office", SOS_RUN)], law=["RSA 655:14-a", "RSA 655:42"]),
     step("Town and city offices",
          "<p><b>In a town</b> that uses the nonpartisan ballot, file a declaration of candidacy "
          "with the town clerk. Filing opens on the seventh Wednesday before the town election and "
          "closes on the Friday of the following week, and a filing on the last day must be made in "
          "person. Your town clerk can tell you which offices are on the ballot.</p>"
          "<p><b>In a city</b>, ask the city clerk.</p>",
          actions=[("Find your town or city clerk", SOS_CLERKS), ("Concord's filing page", CONCORD_FILE)],
          law=["RSA 669:19"])],
    [("Running For Office (Secretary of State)", SOS_RUN),
     ("Qualifications for Office (Secretary of State)", SOS_QUAL),
     ("Filing for Office (City of Concord)", CONCORD_FILE),
     ("Nominations, RSA 655", "/laws/655"),
     ("Town Elections, RSA 669", "/laws/669")],
    ["655", "669"],
    # "As tabled" spelled out on 23 October 2026, so the table's counts rest
    # on the claim (COUNT): the numbers are the table's, which this claim was
    # checked against, not a second reading of the page.
    [claim("The qualifications for president, governor, U.S. senator, U.S. representative, "
           "executive councilor, state senator, state representative and county officer, as "
           "tabled: domiciled in New Hampshire 7 years for governor, councilor and state senator "
           "and 2 years for state representative; a U.S. citizen 9 years for U.S. senator and 7 "
           "years for U.S. representative.", SOS_QUAL, READ),
     claim("To hold any elective office in the state, a person must have a domicile in the state.",
           "RSA 655:2", READ),
     # THE STATE'S DOMICILE YEARS IN ITS OWN STATUTE (23 October 2026): the
     # candidate's affidavit, which uses the guide's own word, domiciled. The
     # federal offices' citizenship years stay on the Secretary of State's
     # page, the federal constitution not being on this disk.
     claim("A candidate swears to have been domiciled in New Hampshire for at least 7 years "
           "before the election for governor, executive councilor and state senator, and for at "
           "least 2 years for state representative.", "RSA 655:29", READ),
     claim("A primary candidate is a registered member of the party, meets the age and domicile "
           "qualifications by the general election, and files a declaration of candidacy between "
           "the first Wednesday in June and the Friday of the following week.", "RSA 655:14", READ),
     ours("HB 481 of 2026, chapter 44, effective January 1, 2028, amends RSA 655:14: file "
          "between the first Friday in March and the Friday of the following week.",
          "/bill/2026/hb481.html", "2026-10-26"),
     claim("The appropriate official: the Secretary of State for governor, U.S. senator, "
           "representative in Congress, councilor, state senator and county office (I); for state "
           "representative in a district of more than one town or ward, the clerk of the town or "
           "city where the filer is domiciled, or for an unincorporated place the town clerk the "
           "Secretary of State designates (III); a one-town or one-ward district also names the "
           "Secretary of State (II), which the guide leaves out as the Secretary of State's page "
           "does.", "RSA 655:15", READ),
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
    more=civics.faq(
        ("I live in an unincorporated place. Where do I file for state representative?",
         "<p>With the town clerk the Secretary of State designates.</p>"),
        ("Where do nomination papers go first?",
         "<p>To the supervisors of the checklist in each town or city, on deadlines in the "
         "summer that the Secretary of State&rsquo;s page gives.</p>"),
        ("How does filing work in a city, such as Concord?",
         "<p>In Concord, for example, candidates for mayor, city council and ward offices file at "
         "the City Clerk&rsquo;s Office, from September 3 to 13, 2027, for the election of "
         "November 2, 2027, with a fee or by petition.</p>"))
    + "<h2>Who Can Help</h2>"
         "<p>The Secretary of State&rsquo;s Elections Division answers questions about filing for "
         "state and federal office at 603-271-3242 or elections@sos.nh.gov. For town and city "
         "offices, ask your town or city clerk.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_RUN}" target="_blank" rel="noopener">'
         "Running for office</a></p>",
    see=[("How to vote in New Hampshire", "/guides/how-to-vote.html"),
         ("Finding your representatives", "/guides/your-representatives.html")],
    figures=[fig("$100", "RSA 655:19-c", "For governor and United States senator, $100"),
             fig("$50", "RSA 655:19-c", "For representative to Congress, $50"),
             fig("$25", "RSA 655:19-c", "For executive councilor, $25"),
             fig("$10", "RSA 655:19-c", "For state senator, $10"),
             fig("$2", "RSA 655:19-c", "For state representative, $2"),
             # The petitions and the nomination papers: no unit makes them a
             # COUNT, and the statute sets them, so they are held to it too.
             fig("200", "RSA 655:19-c", "for governor and United States senator, 200"),
             fig("100", "RSA 655:19-c", "for representative in Congress, 100"),
             fig("50", "RSA 655:19-c", "for executive councilor and county officer, 50"),
             fig("20", "RSA 655:19-c", "for state senator, 20"),
             fig("5", "RSA 655:19-c", "for state representative, 5"),
             fig("3,000", "RSA 655:42", "the names of 3,000 registered voters, 1,500 from each "
                                        "United States congressional district"),
             fig("1,500", "RSA 655:42", "the names of 1,500 voters registered in the district"),
             fig("750", "RSA 655:42", "750 to nominate a candidate for councilor or state senator"),
             fig("150", "RSA 655:42", "150 to nominate a candidate for state representative or "
                                      "county officer"),
             fig("7 years", "RSA 655:29", "domiciled in the state of New Hampshire for at least "
                                          "7 years immediately preceding the election"),
             fig("2 years", "RSA 655:29", "domiciled in the state of New Hampshire for at least "
                                          "2 years immediately preceding the election"),
             fig("9 years", SOS_QUAL, "a U.S. citizen 9 years")])


GUIDES += [LICENSE, CAR, REAL_ID, NEW_RESIDENT, BENEFITS, UNEMPLOYMENT, RUN]


# ---------------------------------------------------------------------------
# A MOTORCYCLE LICENSE, OR A MOPED (the person, 26 October 2026: "Since there
# are various types of vehicle licensing, it might make sense to add a
# motorcycle/moped license to that"). Built on the statutes, read on the
# site's Laws pages that day: RSA 259:57 and 259:63 for what a moped and a
# motorcycle are, RSA 263:30 to 263:34-i for the permit, the test, rider
# training and the fees, RSA 265:120 to 265:123 for riding, and RSA 261 for
# registering. The DMV's motorcycle pages refuse this machine, as its others
# do; their claims rest on the person's printouts of 26 October 2026
# (motorcycle1-7: the endorsement page with each of its three panels open,
# the rider training page with each of its three courses, and the FAQ;
# fees1, the licensing fees; registration1, vehicle registrations). The
# guide prints no course tuition or agency-page fee, which no statute sets.
# Where the DMV's page and the statute differ -- its "$25 for permit
# renewal" against RSA 263:42's $25 and RSA 263:34-i's added $5 -- the guide
# says what the statute says. The helmet law covers riders under 18 only
# (RSA 265:122) and names no moped, so the guide says nothing of helmets on
# a moped. Registering is the car guide's, and is linked rather than told
# again.
# ---------------------------------------------------------------------------
MOTO_READ = "2026-10-26"             # the statutes, on the site's Laws pages
MOTO_DMV_READ = "2026-10-26"         # the DMV's pages: the person's printouts
DMV_MOTO = "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/motorcycle-license-endorsement"
DMV_MOTO_TRAIN = ("https://www.dmv.nh.gov/drivers-licensenon-driver-ids/"
                  "motorcycle-rider-training-program")
DMV_MOTO_FAQ = "https://www.dmv.nh.gov/motorcycle-endorsement-frequently-asked-questions"

MOTORCYCLE = guide(
    "motorcycle-license", "How to Get a Motorcycle License or Ride a Moped",
    "Getting a motorcycle license or endorsement in New Hampshire, step by step: the learner's "
    "permit, rider training and the road test, the fees, the helmet and riding rules, and what a "
    "moped needs.",
    "To ride a motorcycle in New Hampshire you need a motorcycle license or endorsement, a "
    "3-wheeled motorcycle endorsement, or a motorcycle learner&rsquo;s permit. You can start "
    "with a permit, then pass a road test on a motorcycle or finish a state-approved rider "
    "training course instead. A moped needs less: any valid driver&rsquo;s license, or a moped "
    "license earned with a written test, and a registration.",
    [ask("What will you ride?",
         [("A motorcycle, on 2 or 3 wheels",
           "Get a learner's permit, then pass the road test or finish rider training."),
          ("A moped", "Ride on any valid driver's license, or pass a written test for a moped "
                      "license.")]),
     box("Register it before you ride it on the road."),
     box("On a motorcycle without a windshield, protect your eyes. Under 18, wear a helmet too.")],
    [step("Get a learner's permit",
          "<p>A motorcycle learner&rsquo;s permit lets you ride while you learn, with limits. "
          "You can get one if you "
          "are 18 or older, or if you are 16 or 17, have finished an approved driver education "
          "course and hold a New Hampshire driver&rsquo;s license. If you are under 18, the DMV "
          "also requires you to finish a Basic RiderCourse and bring a parental permission form. "
          "You pass a vision test, and a written motorcycle knowledge test or the state&rsquo;s "
          "rider training course in its place. There is no road test for a permit.</p>"
          "<p>Make an appointment with the DMV. Its page lists what to bring: the application for "
          "a driver&rsquo;s license or ID card (form DSMV 450), your current driver&rsquo;s "
          "license and the fee.</p>"
          "<p>With a permit you may ride only after sunrise and before sunset, and you may not "
          "carry a passenger. It is good for 45 days, and can be renewed once for another "
          "45 days.</p>",
          actions=[("Motorcycle endorsement (DMV)", DMV_MOTO), ("Make an appointment", DMV_APPT),
                   ("Application (DSMV 450)", DMV_APP)], law=["RSA 263:32"]),
     step("Pass the road test, or take rider training",
          "<p>To get the license or endorsement itself, you pass a vision test and a driving test "
          "on a motorcycle, which the DMV calls the skills test. It gives the test by appointment, "
          "in the season when conditions are safe. You bring your own motorcycle, registered and "
          "inspected, and you may ride it there only on a valid learner&rsquo;s permit. A "
          "3-wheeled motorcycle has its own, separate test. If you already have a driver&rsquo;s "
          "license, what you get is an endorsement on it; if you do not, a motorcycle "
          "license.</p>"
          "<p>A state-approved motorcycle rider training course can take the place of the skills "
          "test: the DMV says its graduates do not take its written and skills tests. Under 18, "
          "the course is required. The law opens courses to New Hampshire residents who hold a "
          "driver&rsquo;s license of any kind or could get a learner&rsquo;s permit, and a course "
          "may charge tuition. The DMV&rsquo;s rider training page lists the courses and what "
          "they cost; register online, or call the Motorcycle Rider Training office at "
          "(603) 227-4025.</p>"
          "<p>To apply, bring your current New Hampshire license, the application for a "
          "motorcycle endorsement, the fee, and either a rider training completion card from "
          "within the past year or your passing skills test result.</p>",
          actions=[("Motorcycle rider training (DMV)", DMV_MOTO_TRAIN),
                   ("Motorcycle endorsement questions (DMV)", DMV_MOTO_FAQ)],
          law=["RSA 263:30", "RSA 263:31", "RSA 263:34-b", "RSA 263:34-h"]),
     step("Pay the fee",
          "<p>The law sets these fees: $25 for a first motorcycle endorsement or 3-wheeled "
          "motorcycle endorsement, and nothing to renew either one; $50 for a motorcycle license "
          "on its own, which the law calls a special motorcycle license, first or renewed; and "
          "$25 to renew a learner&rsquo;s permit. Another $5 is added to each motorcycle permit, "
          "license or endorsement, and to each renewal. The DMV&rsquo;s fees page lists them with "
          "the $5 added, and its motorcycle endorsement page gives what a learner&rsquo;s permit "
          "costs. If you paid for a learner&rsquo;s permit within a year before you apply for the "
          "license, the DMV does not charge the license fee.</p>",
          actions=[("Licensing fees (DMV)", DMV_FEES)], law=["RSA 263:42, I", "RSA 263:34-i, II"]),
     step("Register your motorcycle",
          "<p>A motorcycle is registered the way a car is: first at the clerk&rsquo;s office of "
          "the town or city where you live, which issues the permit for registration, then for "
          "the state. The state&rsquo;s fee for a motorcycle is $30, and another $1 is added to "
          "each registration and renewal. Riding an unregistered motorcycle carries a $100 fine. "
          "How to Register a Car explains each part.</p>",
          actions=[("How to register a car", "/guides/register-a-car.html"),
                   ("Find your town or city clerk", SOS_CLERKS)],
          law=["RSA 261:148", "RSA 261:141, III", "RSA 263:34-i, I", "RSA 261:40"]),
     step("Ride by the rules",
          "<p>If you are under 18, you must wear a helmet of a type the DMV approves, with a neck "
          "or chin strap, whether you drive or ride as a passenger. A driver who carries a "
          "passenger under 18 without one breaks the law too. The helmet law covers riders under "
          "18.</p>"
          "<p>At any age, if your motorcycle has no windshield or screen that protects your eyes "
          "and face, wear eyeglasses, goggles or a face shield while it is moving.</p>"
          "<p>Ride on the permanent seat, astride and facing forward, and carry nothing that "
          "keeps both hands off the handlebars. A motorcycle is entitled to a full lane of "
          "traffic.</p>",
          law=["RSA 265:122", "RSA 265:123", "RSA 265:120", "RSA 265:121"]),
     step("If you ride a moped",
          "<p>The law calls a vehicle a moped if it goes no faster than 30 miles per hour within "
          "a mile and, if it has a gas engine, the engine is no bigger than 50 cubic centimeters "
          "and has no gears to shift. Anything more is a motorcycle, and needs a motorcycle "
          "license.</p>"
          "<p>To ride a moped on the road, you need a valid driver&rsquo;s license from any "
          "state, a motorcycle license, or a moped license. A moped license is for someone with "
          "neither, and you get it by passing a written test.</p>"
          "<p>A moped is registered too, with its own kind of plate. The state&rsquo;s fee is $14, "
          "and the town permit that a car or motorcycle needs first is not required. Ask the DMV "
          "or your clerk where to register it.</p>",
          actions=[("Vehicle registrations (DMV)", DMV_REG)],
          law=["RSA 259:57", "RSA 259:63", "RSA 263:33", "RSA 263:33-a", "RSA 261:80",
               "RSA 261:148"])],
    [("Motorcycle License Endorsement (Division of Motor Vehicles)", DMV_MOTO),
     ("Motorcycle Rider Training Program (Division of Motor Vehicles)", DMV_MOTO_TRAIN),
     ("Motorcycle Endorsement Frequently Asked Questions (Division of Motor Vehicles)",
      DMV_MOTO_FAQ),
     ("Words and Phrases Defined, RSA 259", "/laws/259"),
     ("Certificates of Title and Registration of Vehicles, RSA 261", "/laws/261"),
     ("Drivers' Licenses, RSA 263", "/laws/263"),
     ("Rules of the Road, RSA 265", "/laws/265")],
    ["259", "261", "263", "265"],
    [claim("Applicants for a motorcycle license must pass a vision test and provide proof of "
           "their fitness to drive a motorcycle, by passing a motorcycle Basic Rider Class or by "
           "taking a DMV motorcycle skills test; at least 16 years old; any applicant under 18 "
           "must successfully complete a motorcycle Basic Rider Class and provide a parental "
           "permission form in order to apply for a motorcycle license or permit. Apply: a "
           "current, valid New Hampshire license; an Application for Motorcycle Endorsement; the "
           "fee; a completion card from a New Hampshire Motorcycle Rider Training Program showing "
           "successful completion within the past year, or motorcycle skills test results showing "
           "a passing grade. Any applicant who pays for a motorcycle learner permit within a year "
           "of applying for a motorcycle license will not be charged the motorcycle license fee. "
           "Learner's permit: 18 or older, or 16 to 18 with an approved driver education course "
           "and a valid New Hampshire driver's license; after sunrise and before sunset; no "
           "passengers; valid for 45 days; renewed one time; request an appointment and bring the "
           "Application for Driver License or ID Card (DSMV 450), current driver license, payment "
           "of $30.00, $25 for permit renewal; vision test; knowledge test. Skills tests are "
           "given on a seasonal basis, only when conditions are safe for testing; schedule an "
           "appointment; applicants provide their own motorcycle, and to ride it to the test "
           "location must have a valid motorcycle learner's permit; currently registered and "
           "inspected; an applicant who fails the skills test twice is required to take a "
           "motorcycle rider training class. A three-wheeled motorcycle endorsement: the same "
           "vision and knowledge exam; may drive any registered three-wheeled motorcycle, but "
           "shall not drive any two-wheeled motorcycle.", DMV_MOTO, MOTO_DMV_READ),
     claim("Basic RiderCourse: mandatory for those drivers under the age of 18 who wish to obtain "
           "a motorcycle endorsement; a completion card will allow a motorcycle endorsement to be "
           "added to their license; course graduates are exempt from the DMV written and skills "
           "tests; a motorcycle learner's permit is not required; motorcycles and helmets are "
           "provided; under 18 must have a valid driver license and a Motorcycle Safety Course "
           "Waiver signed by a parent or guardian; register on-line, or contact our office at "
           "(603) 227-4025; take the completion card to the NH DMV within one year. Intermediate "
           "and Experienced RiderCourses for riders with some experience.", DMV_MOTO_TRAIN,
           MOTO_DMV_READ),
     claim("How can I obtain a New Hampshire motorcycle endorsement? Transfer an endorsement from "
           "your out-of-state license, successfully complete the Motorcycle Rider Training Course, "
           "or successfully complete written and road tests. Am I required to take a motorcycle "
           "training course? No; anyone who successfully completes the course is exempt from "
           "taking the required DMV skills test; the course is required if you are under the age "
           "of 18. Without a course: make an appointment to schedule the written test to obtain a "
           "45-day motorcycle permit; you will receive the date, time and location of the skills "
           "test. The course costs are listed. Out-of-state residents may register for a course.",
           DMV_MOTO_FAQ, MOTO_DMV_READ),
     claim("Licensing fees: Motorcycle Only or Motor Driven Cycle Only $55.00; Moped $8.00; First "
           "time New Hampshire Motorcycle or 3-Wheel License Endorsement $30.00; Renewal of "
           "Motorcycle or 3-Wheel License Endorsement $5.00.", DMV_FEES, MOTO_DMV_READ),
     claim("With the exception of Mopeds, all motor vehicles must begin their registration process "
           "at the town or city clerk in the town or city in which they reside.", DMV_REG,
           MOTO_DMV_READ),
     claim("Application for Driver License or Non-Driver ID Card: I am applying for an original "
           "license, a renewal, a non-driver ID card, a limited privilege license or a "
           "motorcycle endorsement (includes 3 wheel and motor driven cycle).", DMV_APP,
           MOTO_DMV_READ),
     claim("The town and city clerks lookup lists each town's clerk.", SOS_CLERKS, CHECKED),
     # As the license guide read it.
     claim("The DMV is fully appointment based; book online or call 603-227-4000.", DMV_APPT, READ),
     claim("A moped is a motor-driven cycle whose speed attainable in one mile is 30 miles per "
           "hour or less; an internal combustion engine no more than 50 cubic centimeters, with "
           "no gear shifting; not an electric bicycle.", "RSA 259:57", MOTO_READ),
     claim("A motorcycle is a motor vehicle with a seat or saddle, on not more than 3 wheels, "
           "excluding electric bicycles, tractors and mopeds.", "RSA 259:63", MOTO_READ),
     claim("No person may drive a motorcycle without a motorcycle license or endorsement, a "
           "3-wheeled motorcycle endorsement or a learner's permit; any of them lets the holder "
           "drive any registered 2-wheeled or 3-wheeled motorcycle without any other class of "
           "license; a restricted 3-wheeled endorsement covers 3-wheeled motorcycles only.",
           "RSA 263:30", MOTO_READ),
     claim("A motorcycle license for persons without a driver's license, an endorsement for those "
           "with one; a driver examination conducted on a motorcycle; separate examinations for "
           "the 3-wheeled restriction; the director may waive it on proof of a state-approved "
           "rider education course; no more than two attempts, then the rider education program.",
           "RSA 263:31", MOTO_READ),
     claim("A learner's permit at 18 or older, or 16 to 18 with an approved driver education "
           "course and a valid NH driver's license; a written knowledge test or the rider "
           "education program, no driver examination; after sunrise and before sunset, no "
           "passengers; valid for 45 days, one renewal for an additional 45 days.",
           "RSA 263:32", MOTO_READ),
     claim("A moped needs a current valid driver's license from any state, a motorcycle license "
           "or a restricted motorcycle license.", "RSA 263:33", MOTO_READ),
     claim("A restricted license for mopeds, for persons without a driver's or motorcycle "
           "license, on passing a written examination.", "RSA 263:33-a", MOTO_READ),
     claim("Rider training courses are open to residents with a valid driver's license of any "
           "classification or eligible for a learner's permit; a reasonable tuition fee may be "
           "charged.", "RSA 263:34-b", MOTO_READ),
     claim("The director may exempt applicants from the licensing skills test on proof of a rider "
           "training course with a similar test of skills.", "RSA 263:34-h", MOTO_READ),
     claim("An additional $1 on each motorcycle registration and renewal; an additional $5 on each "
           "motorcycle permit, license or endorsement fee and each renewal.", "RSA 263:34-i",
           MOTO_READ),
     claim("Special motorcycle license, original or renewal, $50; original motorcycle endorsement "
           "$25; 3-wheeled motorcycle endorsement $25; endorsement renewals no charge; learner's "
           "permit renewal $25.", "RSA 263:42", MOTO_READ),
     claim("Registration fees: each motorcycle $30, each moped $14.", "RSA 261:141", MOTO_READ),
     claim("No vehicle but an OHRV, snowmobile or moped is registered until its owner has a "
           "permit for registration from the city or town.", "RSA 261:148", MOTO_READ),
     claim("Driving an unregistered vehicle not exempt is a violation, with a $100 fine.",
           "RSA 261:40", MOTO_READ),
     claim("A registered moped gets a number plate of a design different from motorcycle plates.",
           "RSA 261:80", MOTO_READ),
     claim("Ride only on the permanent and regular seat; a passenger only on a motorcycle designed "
           "for more than one, on a seat for 2, a seat fixed at the rear or side, or a sidecar; "
           "astride, facing forward; nothing that prevents keeping both hands on the handlebars.",
           "RSA 265:120", MOTO_READ),
     claim("Full use of a lane; 2 abreast at most; no passing in the same lane; no driving between "
           "lanes or rows of vehicles.", "RSA 265:121", MOTO_READ),
     claim("Under 18, approved protective headgear with a neck or chin strap, driving or riding; "
           "an operator carrying a person under 18 in violation is guilty of a violation.",
           "RSA 265:122", MOTO_READ),
     claim("Without a windshield or screen protecting the eyes and face, the driver wears "
           "eyeglasses, goggles or a protective face shield while in motion.", "RSA 265:123",
           MOTO_READ)],
    more=civics.faq(
        ("What if I fail the road test twice?",
         "<p>You cannot take it a third time. The law requires you to finish the motorcycle rider "
         "training course instead.</p>"),
        ("Do I need a car license to ride a motorcycle?",
         "<p>Not under the law: it provides a motorcycle license for someone with no "
         "driver&rsquo;s license, and a motorcycle license, endorsement or permit lets you drive "
         "any registered motorcycle, on 2 or 3 wheels, without any other license. The "
         "DMV&rsquo;s permit page, though, lists a current driver&rsquo;s license among what to "
         "bring, so ask the DMV first if you have none. To get a permit at 16 or 17, you need a "
         "New Hampshire driver&rsquo;s license.</p>"),
        ("Is a 3-wheeled motorcycle different?",
         "<p>A 3-wheeled motorcycle endorsement comes with its own test, on the skills that kind "
         "of motorcycle needs. With it alone you may drive a 3-wheeled motorcycle but not a "
         "2-wheeled one. A full motorcycle endorsement covers both.</p>"),
        ("Is an electric bicycle a moped?",
         "<p>No. The law leaves electric bicycles out of what it calls a moped, and out of what "
         "it calls a motorcycle, so the license rules in this guide do not cover one.</p>"),
        ("Can I carry a passenger?",
         "<p>Not on a learner&rsquo;s permit. With a license or endorsement, only if the "
         "motorcycle is built to carry more than one person: on a seat made for two, a seat "
         "firmly attached behind or beside you, or a sidecar. The passenger sits astride, facing "
         "forward.</p>"),
        ("Can I ride between lanes of traffic?",
         "<p>No. You may not ride between lanes or rows of traffic, or pass a vehicle in its own "
         "lane. A motorcycle is entitled to a full lane, and two motorcycles may ride side by "
         "side in one lane, but no more than two.</p>"))
         + DMV_HELP,
    see=[("How to register a car", "/guides/register-a-car.html"),
         ("How to renew your driver's license", "/guides/renew-drivers-license.html")],
    figures=[fig("45 days", "RSA 263:32", "valid for 45 days from the date of issuance"),
             fig("$25", "RSA 263:42", "for each original motorcycle endorsement-$25"),
             fig("$50", "RSA 263:42", "special motorcycle license renewal-$50"),
             fig("$5", "RSA 263:34-i", "an additional fee of $5"),
             fig("$1", "RSA 263:34-i", "an additional fee of $1"),
             fig("$30", "RSA 261:141", "For each motorcycle-$30"),
             fig("$14", "RSA 261:141", "For each moped-$14"),
             fig("$100", "RSA 261:40", "The fine for a violation of this section shall be $100")])

GUIDES += [MOTORCYCLE]


# ---------------------------------------------------------------------------
# VANITY AND SPECIAL PLATES (the person, 26 October 2026: "add a guide on how
# to get a vanity plate or specialty plate like a gold star license plate,
# national guard plate, etc."). From the sections of RSA 261 that create each
# plate -- who qualifies and what it costs are the law's, and every dollar
# printed is a fig() on its section -- and the DMV's Vehicle Registrations
# page, as the person's printout of it read that day, for changing a plate
# during the year. Where to apply, the mailing address, the character rules of
# Saf-C 513.62 and how a denial is appealed are the DMV's Vanity Plates page,
# the person's printout of it (vanityplates1), at the address the person gave
# on 26 October 2026. The decal plates that page lists have no section in RSA
# 261 on this site's Laws page, so the guide leaves them out.
# ---------------------------------------------------------------------------
PLATES_READ = "2026-10-26"
DMV_VANITY = ("https://www.dmv.nh.gov/vehicles-boats-and-titles/vehicle-registrations/"
              "vanity-plates")
_PLATE_ROWS = [
    ("Veteran", "A veteran of the U.S. armed forces, or one discharged with a general discharge "
     "under honorable conditions, with proof of veteran status",
     "The regular registration fee and the $4 a plate fee", "RSA 261:87-b"),
    ("Disabled Veteran, Purple Heart, former prisoner of war, Pearl Harbor survivor",
     "A veteran the U.S. Department of Veterans Affairs rates permanently and totally disabled "
     "from a service-connected disability, or who received a vehicle from the U.S. government as "
     "an amputee or paraplegic; a veteran totally blind from a service-connected disability; a "
     "former prisoner of war; a Purple Heart recipient; a Pearl Harbor survivor, with proof",
     "The first set is free", "RSA 261:86"),
    ("Gold Star Mother, Father or Family",
     "The mother or stepmother, the father or stepfather, or an immediate family member of a "
     "person killed while on duty in the U.S. armed forces",
     "The regular registration fees, and no plate fee", "RSA 261:87-c"),
    ("National Guard and active duty",
     "A member or retired member of the National Guard of any state, or an active-duty member "
     "of the armed forces", "The registration fee", "RSA 261:91"),
    ("New Hampshire First for Veterans", "Anyone who applies",
     "$60, then $30 a year when you renew", "RSA 261:97-g"),
    ("Conservation (moose)", "Anyone who applies", "$30, and $30 a year when you renew",
     "RSA 261:97-a"),
    ("State park symbol, on any plate", "Anyone who applies",
     "$85, at registration and at each yearly renewal", "RSA 261:75-c"),
]

PLATES = guide(
    "vanity-and-special-plates", "How to Get a Vanity or Special Plate",
    "Getting a vanity plate with letters you choose, or a special plate such as a veteran, Gold "
    "Star, National Guard or conservation plate, in New Hampshire: who qualifies, how to apply, "
    "and what each costs.",
    "A <b>vanity plate</b> carries letters and numbers you choose, approved by the Division of "
    "Motor Vehicles. A <b>special plate</b> shows that you belong to a group the law names, such "
    "as veterans, Gold Star families or the National Guard, or supports a cause, such as "
    "conservation or the state parks. Each plate is set by its own section of RSA 261, which "
    "says who qualifies and what it costs on top of your regular registration.",
    [ask("What kind of plate do you want?",
         [("Letters you choose", "A vanity plate, with letters and numbers the DMV approves."),
          ("A plate for a group you belong to", "A veteran, Gold Star or National Guard plate, "
           "with proof that you qualify."),
          ("A plate that supports a cause", "A conservation (moose) plate, a First for Veterans "
           "plate, or the state park symbol.")]),
     box("Apply when you register or renew, or change your plate type during the year."),
     box("If the DMV turns down a vanity plate, it refunds or credits the vanity fee.")],
    [step("Choose your plate",
          "<p>A vanity plate carries the letters, or letters and numbers, that the DMV&rsquo;s "
          "rules allow, and no two plates may be the same. Under the DMV&rsquo;s rule (Saf-C "
          "513.62), a vanity plate may not:</p><ul>"
          "<li>include a zero;</li>"
          "<li>have more than 7 characters;</li>"
          "<li>have more than 2 ampersands, plus signs or minus signs, or two of them side by "
          "side;</li>"
          "<li>have any character other than letters, numerals, ampersands, plus signs and "
          "minus signs;</li>"
          "<li>be only numerals, or only numerals with those symbols;</li>"
          "<li>have characters that are hard to tell apart;</li>"
          "<li>refer to, in any language and read any way, intimate body parts, profane or "
          "vulgar acts, profanity or obscenity, violence, illegal activities, illegal drugs, "
          "gangs, or slurs, discrimination or bigotry.</li></ul>"
          + table("The most characters each kind of vanity plate can have",
                  ["Plate", "Characters"],
                  [["Passenger", "7"],
                   ["Apportioned, Conservation, Commercial, Trailer, Veteran, State Park, Active "
                    "Duty Military", "6"],
                   ["Antique", "6, or 4 with the Old Man replica"],
                   ["National Guard, Decal, Veteran Decal", "5"],
                   ["Motorcycle", "5, no ampersand"],
                   ["Walking Disability, Purple Heart, Street Rod, Conservation State Park, "
                    "Disabled Veteran", "4"],
                   ["Veteran Motorcycle", "4, no ampersand"],
                   ["Purple Heart Motorcycle, Walking Disability Motorcycle",
                    "3, two of them letters, no ampersand"]])
          + "<p>The DMV&rsquo;s Vanity Plate Search shows whether a choice looks available, but "
          "it cannot save a plate for you, so it may be gone by the time you apply.</p>"
          "<p>For a special plate, find yours in the table under &ldquo;A special plate&rdquo;, below: who may "
          "have it and what "
          "it costs.</p>",
          actions=[("Vanity plates (DMV)", DMV_VANITY)], law=["RSA 261:89"]),
     step("Apply when you register, or change your plate during the year",
          "<p>A vanity plate is issued only on application. When you register or renew, bring "
          "the DMV&rsquo;s <b>Application for Vanity Plates</b> to your town or city clerk&rsquo;s "
          "office. Once the clerk has done the town&rsquo;s part of your registration, you can "
          "also apply at any DMV office that processes registrations, or mail the application, "
          "the town portion of your registration and a check for the fees to: NH Dept. of "
          "Safety, DMV &ndash; Registration Bureau, 23 Hazen Drive, Concord NH 03305. An approved "
          "plate is mailed to you.</p>"
          "<p>To change to a vanity plate at another time, bring the application and your "
          "current registration to your town or city clerk&rsquo;s office or a DMV location. To "
          "change to another plate type during the year, the DMV asks for a completed "
          "Application for Replacement Plates and Decals, the plate fees, a new registration "
          "fee, and any other fees for the plate you want.</p>",
          actions=[("Vanity plates (DMV)", DMV_VANITY),
                   ("Vehicle registrations (DMV)", DMV_REG)], law=["RSA 261:89"]),
     step("Pay the fees",
          "<p>A vanity plate costs a special vanity plate service fee of $60, on top of your "
          "regular registration fee and the number plate fee of $4 a plate, and $60 a year for "
          "each set when you renew. The DMV prorates the vanity fee by the month. Changing your "
          "plate before your next renewal adds a one-time plate fee and a certified registration "
          "fee, which the DMV&rsquo;s Vanity Plates page lists.</p>"
          "<p>If the DMV turns your choice down, you get a letter in the mail with a set of "
          "number plates and a new registration. The vanity fee you paid is credited to your "
          "customer account, and you can choose a new plate or ask for a refund.</p>",
          law=["RSA 261:89", "RSA 261:75"]),
     step("Show that you qualify",
          "<p>Each special plate is issued on application, and the plates for a group need "
          "proof that you belong to it. For a Gold Star plate, that is a report of casualty (DD "
          "Form 1300) or an official casualty notice; proof of your relationship, such as a "
          "birth certificate; or a marriage certificate or a letter from the U.S. Department of "
          "Veterans Affairs.</p><p>To change to a special plate during the year, the DMV asks "
          "for a completed Application for Replacement Plates and Decals, the plate fees, a new "
          "registration fee, and any other fees for the plate you want.</p>"
          + table("Special plates and who may have them (RSA 261)",
                  ["Plate", "Who qualifies", "What it costs", "The law"],
                  [(a, b, c, f'<a href="/laws/261#s{d.split(":")[1]}">{d}</a>')
                   for a, b, c, d in _PLATE_ROWS])
          + "<p>Some special plates can carry letters you choose too: a Gold Star plate, and a "
          "conservation or First for Veterans plate, for which you pay the vanity fee as well. "
          "The state park symbol can go on a vanity plate.</p>",
          law=["RSA 261:86", "RSA 261:87-b", "RSA 261:87-c", "RSA 261:91"])],
    [("Vanity Plates (Division of Motor Vehicles)", DMV_VANITY),
     ("Vehicle Registrations (Division of Motor Vehicles)", DMV_REG),
     ("Certificates of Title and Registration of Vehicles, RSA 261", "/laws/261")],
    ["261"],
    [claim("Related Resources: Plate Types; Vanity Plates. Plate Changes: you may change your "
           "plate type at any point during the year; a completed Application for Replacement "
           "Plates and Decals is required, and you will be required to pay the plate fees, the "
           "new registration fee, plus any other applicable fees for the plate type requested. "
           "With the exception of Mopeds, all motor vehicles must begin their registration "
           "process at the town or city clerk in the town or city in which they reside.",
           DMV_REG, PLATES_READ),
     # The DMV's Vanity Plates page, the person's printout of 26 October 2026.
     claim("For new and renewal registration, bring the Application for Vanity Plates to your "
           "Town/City clerk's office; you can also apply for a new vanity plate at any DMV office "
           "that processes registrations after processing the town/city portion of your "
           "registration; you may also mail the application, town portion of the registration "
           "and a check for the appropriate fees to the Concord DMV at: NH Dept. of Safety, DMV - "
           "Registration Bureau, 23 Hazen Drive, Concord NH 03305. Changing your plate anytime "
           "other than renewal: bring the application along with your current vehicle "
           "registration to your Town/City clerk's office or nearest DMV location. If approved, "
           "the plates will be mailed to you; if denied, a letter by mail along with a set of "
           "number plates and a new registration; a credit for the paid vanity fees will be "
           "credited to your customer account; a choice of selecting a new plate or applying for "
           "a refund; pursuant to Saf-C 508.04, a person whose plate has been denied may submit "
           "a written request to the Director setting forth a detailed explanation as to why it "
           "should be issued. Vanity Plate fee (for 12 months, prorated per month); one-time "
           "plate fee; changing before your next renewal includes the one-time plate fee and a "
           "certified registration fee. Saf-C 513.62(c): a vanity plate shall not include a "
           "zero; refer to intimate body parts or genitals, profane or vulgar sexual or excretory "
           "acts, profanity or obscenity, advocating violence, illegal activities, illegal drugs "
           "or intoxicants, gangs, racial, ethnic, religious, gender or sexual orientation slur, "
           "discrimination, genocide, hatred or bigotry, in any language, forward, backward, by "
           "mirror image or by phonetic spelling; have more than 7 characters; have more than 2 "
           "ampersands, plus signs, or minus signs, not consecutive; have characters other than "
           "ampersands, numerals, plus signs, minus signs, or letters; have only numerals or "
           "only numerals and ampersands, plus signs, or minus signs; have characters which may "
           "cause difficulty of distinction. Maximum characters: Passenger seven; Apportioned, "
           "Conservation, Commercial, Trailer, Veteran, State Park, Active Duty Military six; "
           "Antique six (four with Old Man Replica); Walking Disability, Purple Heart, Street "
           "Rod, Conservation State Park, Disabled Veteran four; National Guard, Decal, Veteran "
           "Decal five; Motorcycle five (ampersand not available); Veteran Motorcycle four "
           "(ampersand not available); Purple Heart Motorcycle, Walking Disability Motorcycle "
           "three (two must be letters, ampersand not available). The Vanity Plate Search may "
           "indicate that your plate choice is available, but it cannot save the plate for you. "
           "Plate Recall: pursuant to Saf-C 513.62(d) the Director may recall any vanity plate "
           "found not to conform; complaints must be sent to the Director in letter form, signed, "
           "with an explanation; anonymous letters will not be accepted.", DMV_VANITY,
           PLATES_READ),
     # As the license guide read it.
     claim("The DMV is fully appointment based; book online or call 603-227-4000.", DMV_APPT, READ),
     claim("Vanity plates bearing such letters or letters and numbers as the director shall "
           "prescribe, with no duplication, issued only upon application and payment of a "
           "special vanity plate service fee of $60, in addition to the regular registration fee "
           "and any number plate fee; renewed annually for $60 per set; a rejected application's "
           "fee refunded or credited and a plate of the same classification issued; "
           "nonconforming plates recalled whenever issued, the prorated fee refunded or "
           "credited.", "RSA 261:89", PLATES_READ),
     claim("A number plate or plates for a fee of $4.00 per plate.", "RSA 261:75", PLATES_READ),
     claim("One set of special plates, the first without charge, for a veteran who is an amputee "
           "or paraplegic and received the vehicle from the U.S. government, or is rated "
           "permanently and totally disabled from a service-connected disability; totally blind "
           "from a service-connected disability; a former prisoner of war; awarded the Purple "
           "Heart; a Pearl Harbor survivor; with satisfactory proof; a surviving spouse may keep "
           "a prisoner of war's, Purple Heart or Pearl Harbor plate unless he or she remarries.",
           "RSA 261:86", PLATES_READ),
     claim("Veterans' plates for veterans as defined in RSA 21:50, I(a), and those with a general "
           "discharge under honorable conditions, on application, proof of veteran status and "
           "payment of the regular registration fee and the $4 per plate fees; renewals at the "
           "standard fee; the surviving spouse may use the plates until remarriage.",
           "RSA 261:87-b", PLATES_READ),
     claim("Gold star plates for a gold star mother (mother or stepmother), father (father or "
           "stepfather) or family (an immediate family member) of a person killed while on duty "
           "in the United States armed forces; documented by DD Form 1300 or an official casualty "
           "notification document, proof of relationship such as a birth certificate, or a "
           "marriage certificate or a VA benefit or certification letter; upon payment of "
           "regular registration fees, and no additional plate fees; applicants may request a "
           "specific combination of characters that meets the requirements for any plate and is "
           "not already in use.", "RSA 261:87-c", PLATES_READ),
     claim("A special plate, upon payment of the registration fee, for members or retired members "
           "of the national guard of any state and active-duty members of the armed forces, "
           "attached only to vehicles registered in the name of the person issued the plates; a "
           "retired member's surviving spouse may use them until remarriage.", "RSA 261:91",
           PLATES_READ),
     claim("New Hampshire first for veterans plates, issued only upon application and payment of "
           "a $60 fee in addition to the regular registration and number plate fees; vanity "
           "versions with the vanity fee as well; renewed annually for $30 per set.",
           "RSA 261:97-g", PLATES_READ),
     claim("Conservation plates, issued only upon application and payment of a $30 fee in "
           "addition to the regular registration and number plate fees; vanity conservation "
           "plates with the vanity fee as well; renewed annually for $30 per set.",
           "RSA 261:97-a", PLATES_READ),
     claim("A special registration plate symbol benefitting the state park system, on any type of "
           "plate for private passenger vehicles, recreational vehicles and motorcycles, "
           "available to any applicant upon payment of a fee of $85, in addition to other fees, "
           "and on a vanity plate with the vanity fee; the fees apply to original registrations "
           "and annual renewals.", "RSA 261:75-c", PLATES_READ)],
    more=civics.faq(
        ("Can I choose the letters on a special plate?",
         "<p>On some. A Gold Star plate can carry a combination you ask for, if it meets the "
         "rules for any plate and is not already in use. A conservation or First for Veterans "
         "plate can be a vanity plate if you pay the vanity fee as well.</p>"),
        ("What happens if my vanity plate is turned down?",
         "<p>The law has the DMV refund or credit the vanity fee you paid, and issue you a plate "
         "of the same kind as the one you asked for. Under the DMV&rsquo;s rule (Saf-C 508.04), "
         "you may also ask the Director in writing to issue the plate, explaining in detail why "
         "it should be.</p>"),
        ("Can a vanity plate be taken back after it is issued?",
         "<p>Yes. The law has the DMV recall a vanity plate that does not meet the law and the "
         "rules, whenever it was issued, and refund or credit the unused part of the fee. A "
         "complaint about a plate goes to the Director in a signed letter explaining why it "
         "does not meet the rules; anonymous letters are not accepted.</p>"),
        ("Can my spouse keep my plate after I die?",
         "<p>For some plates, yes, until they remarry: a Veteran plate, a National Guard "
         "plate of a retired member, and a former prisoner of war, Purple Heart or Pearl Harbor "
         "survivor plate.</p>"))
         + DMV_HELP,
    see=[("How to register a car", "/guides/register-a-car.html"),
         ("How to get a motorcycle license or ride a moped", "/guides/motorcycle-license.html")],
    figures=[fig("$60", "RSA 261:89", "a special vanity plate service fee of $60"),
             fig("$60", "RSA 261:89", "renewed on an annual basis for $60 per set"),
             fig("$4", "RSA 261:75", "for a fee of $4.00 per plate"),
             fig("$60", "RSA 261:97-g", "upon payment of a $60 fee"),
             fig("$30", "RSA 261:97-g", "renewed on an annual basis for $30 per set"),
             fig("$30", "RSA 261:97-a", "upon payment of a $30 fee"),
             fig("$85", "RSA 261:75-c", "a special registration plate symbol fee of $85")])

GUIDES += [PLATES]


# ---------------------------------------------------------------------------
# TOURING THE STATE HOUSE (the person, 17 October 2026: a guide to touring
# the State House -- booking through the Visitor Center, as a school field
# trip, or as a representative's guest). It rests on one document, the State
# House Visitor Center's Rules for Tours, which the person saved in
# records/sources/ that day: its words are read from the PDF by pdfplumber at
# every check, never from a copy typed out of it. The Visitor Center is the
# General Court's -- its page is on gc.nh.gov and its director's address on
# the legislature's mail -- so the PDF is one of the Court's own documents
# (RECORD_HOMES). It is undated and written for school groups, so the guide
# says the rules are the Visitor Center's as printed, and to check with it
# when booking. Its page is linked, never fetched (GENERAL_COURT_LINKS). The
# rules say nothing of visiting as a representative's guest, and the person's
# notes say nothing of how that is done, so the guide says only to contact
# your representative or senator, through the site's own guides to finding
# and contacting them. The director's name and address, which the rules
# print, are left out: the Visitor Center's number is the way in.
# ---------------------------------------------------------------------------
TOUR_RULES = "records/sources/state-house-visitor-center-rules-for-tours.pdf"
TOUR_CITE = "State House Visitor Center, Rules for Tours (undated; saved October 17, 2026)"
VISITOR_CENTER = civics.SRC_VISITOR_CENTER[1]


def tour(says, words):
    """A claim on the Visitor Center's Rules for Tours."""
    return record(says, TOUR_CITE, TOUR_RULES, words, READ)


TOUR = guide(
    "tour-the-state-house", "How to Tour the New Hampshire State House",
    "Arranging a tour of the State House in Concord through its Visitor Center, bringing a class "
    "on a field trip, and what to expect on the day.",
    "The State House Visitor Center in Concord schedules tours of the State House for groups, "
    "school classes among them, and a tour is generally an hour. With any question about a tour, "
    "call the Visitor Center at (603) 271-2154. Before a class visits, share the Visitor Center&rsquo;s rules for "
    "tours with every adult coming: arrive on time, leave backpacks behind, and bring no food, "
    "drink or gum. To visit with your own representative or senator, contact them directly.",
    [box("Contact the Visitor Center about a tour for your group or class."),
     ask("Bringing a class?",
         [("Yes", "Share the rules for tours with every adult, and plan chaperones, lunches and "
                  "your arrival."),
          ("No", "Ask the Visitor Center what your group needs to know.")]),
     box("On the day, arrive on time, and let the Visitor Center know you are there before the "
         "group comes in."),
     box("The tour takes about an hour, and may change around what is happening in the building "
         "that day.")],
    [step("Arrange the tour",
          "<p>The State House Visitor Center schedules the tours, many groups each day. Call it at "
          "(603) 271-2154 with any question, including how to book, or start from its page.</p>"
          "<p>To visit with your own representative or senator, contact them directly. Finding "
          "your representatives says who they are, and How to contact your legislators how to "
          "reach them.</p>",
          actions=[("State House Visitor Center", VISITOR_CENTER),
                   ("Find your representatives", "/guides/your-representatives.html"),
                   ("Contact your legislators", "/guides/contact-your-legislators.html")],
          note="The rules in this guide are the Visitor Center&rsquo;s own, as its Rules for "
               "Tours prints them. That document carries no date, so ask the Visitor Center "
               "about anything that matters to your visit when you book."),
     step("Before a class visits",
          "<p>The Visitor Center asks you to print its rules for tours and share them with every "
          "adult who will be touring. Among them:</p><ul>"
          "<li><b>Keep to your times.</b> Plan to arrive and leave at your scheduled times; tours "
          "are generally one hour. If you will be more than 10 minutes early or late, call the "
          "Visitor Center at 271-2154.</li>"
          "<li><b>Chaperones.</b> Bring no more than four per class, and tell them the class "
          "tours as one large group rather than in smaller ones.</li>"
          "<li><b>No backpacks.</b> If your group brings lunches, the Visitor Center will store "
          "them.</li></ul>"),
     step("On the day",
          "<ul><li><b>Check in first.</b> Do not bring the group into the building until someone "
          "from the Visitor Center knows you have arrived: it is a security precaution.</li>"
          "<li><b>The way in.</b> Groups enter by the front doors, into the Hall of Flags, a "
          "memorial hall near committee hearing rooms where meetings may be under way.</li>"
          "<li><b>No food, drink or gum</b> unless medically necessary, and hats off inside. "
          "The rules apply to the adults too.</li>"
          "<li><b>A working building.</b> State officials and staff are at work, so remind "
          "students to whisper.</li>"
          "<li><b>Cameras.</b> Only adults use cameras.</li>"
          "<li><b>Restrooms</b> are available, and students must be supervised. If students need "
          "the restroom before the tour begins, tell the Visitor Center right away.</li></ul>")],
    [("Rules for Tours, required reading for a State House tour, undated (New Hampshire State "
      "House Visitor Center)", ""),
     civics.SRC_VISITOR_CENTER,
     # The site's own pages it rests on; the guide to contacting legislators
     # is under See Also and on the first step's button instead, which a
     # build that holds that guide back takes off (build_civics.unlinked).
     ("Finding Your Representatives", "/guides/your-representatives.html"),
     ("The Calendar", "/calendar.html")],
    [],
    [tour("The Visitor Center schedules many groups each day; tours are generally one hour.",
          ["We schedule many groups each day", "Tours are generally ONE HOUR"]),
     tour("Questions go to the Visitor Center at (603) 271-2154.",
          ["Any questions or concerns contact", "or call (603) 271-2154"]),
     tour("Read and print the rules, and share them with every adult touring.",
          ["REQUIRED READING FOR YOUR STATE HOUSE TOUR", "Please read and print out!",
           "Share this information with ALL adults who will be touring the State House"]),
     tour("Arrive and leave at the scheduled times; more than 10 minutes early or late, notify "
          "the Visitor Center at 271-2154.",
          ["plan to arrive and leave at your scheduled times",
           "IF you are going to be more than 10 minutes early or late, NOTIFY the Visitor Center "
           "@ 271-2154"]),
     tour("At most four chaperones per class; the class travels as one large group.",
          ["We ask you limit the number of chaperones to 4 per class",
           "we travel as one large group"]),
     tour("No backpacks; lunches are stored in the Visitor Center.",
          ["No BACK PACKS Please!",
           "If your group is bringing lunches we will store them in the Visitor Center"]),
     tour("Students are encouraged to dress up, but it is not required.",
          "Students should be encouraged to dress up for their special visit, but not required"),
     tour("A visit to the gift shop needs prior arrangements.",
          "if you wish to have your group visit the gift shop, you must make prior arrangements"),
     tour("The group does not enter until the Visitor Center knows it has arrived, a security "
          "precaution.",
          ["Do not bring group into the building until someone from the Visitor Center has been "
           "notified of your arrival", "This is a security precaution"]),
     tour("Groups enter by the front doors into the Hall of Flags, a memorial hall near committee "
          "hearing rooms where there may be meetings.",
          ["Groups will enter the front doors which open into the historic Hall of Flags",
           "This room is a memorial hall and is also located near committee hearing rooms",
           "there may be meetings in these rooms"]),
     tour("No food, drink or gum unless medically necessary; hats off; the rules apply to adults.",
          ["No Food, Drink, or Gum unless medically necessary", "Remove hats inside the building",
           "the rules regarding food, drink and hats apply to them too"]),
     tour("A working building: officials and staff are working, so students whisper.",
          ["The State House is a working building",
           "remind students state officials and staff are working"]),
     tour("Only adults use cameras.", "We ask that only adults use cameras"),
     tour("Restrooms are available but supervised; a need before the tour is told right away.",
          ["Bathrooms are available but must be supervised",
           "If your students need the restroom before the tour begins, notify us right away"]),
     tour("Legislators are notified of the visit in the House and Senate Calendars and often try "
          "to meet the students.",
          ["Senators & Representatives are notified of your visit in the House and Senate "
           "Calendars", "legislators often try to meet the students"]),
     tour("The Governor's Office is in the tour; the Governor may meet groups when the schedule "
          "permits; students are not to be told they will.",
          ["Office is included in the tour", "schedule permits, he often tries to meet groups",
           "Please do NOT tell your students they will be seeing him"]),
     tour("Rallies, events, sessions, press conferences and bill signings can change a tour; the "
          "chambers are at times unavailable to the public.",
          ["Rallies, political events, legislative session, press conferences, bill signings and "
           "other activities may be scheduled on the date of your tour",
           "there are times that the legislative or executive chambers may be unavailable to the "
           "public"]),
     ours("Finding Your Representatives names who represents a town.",
          "/guides/your-representatives.html", READ),
     ours("How to Contact Your Legislators says how to reach them.",
          "/guides/contact-your-legislators.html", READ),
     ours("The Calendar shows the week's hearings and session days.", "/calendar.html", READ)],
    more=civics.faq(
        ("Will students meet their legislators or the Governor?",
         "<p>Senators and representatives are told of your visit in the House and Senate "
         "Calendars, and they often try to meet the students. The tour includes the "
         "Governor&rsquo;s Office, and the Governor sometimes meets groups when the schedule "
         "allows; the Visitor Center asks that students not be told they will.</p>"),
        ("Could the tour change on the day?",
         "<p>Rallies, press conferences, bill signings, a session of the House or Senate and "
         "other events can change the tour, and at times the legislative or executive chambers "
         "are closed to the public. The Calendar here shows the week&rsquo;s hearings and "
         "session days.</p>"),
        ("Do students need to dress up, and can we visit the gift shop?",
         "<ul>" "<li><b>Dress.</b> Students are encouraged to dress up for the visit, but it is not "
         "required.</li>"
         "<li><b>The gift shop.</b> To visit it with your group, arrange it in advance.</li></ul>")),
    see=[("Finding your representatives", "/guides/your-representatives.html"),
         ("How to contact your legislators", "/guides/contact-your-legislators.html"),
         ("How to attend and speak at a public hearing", "/guides/attend-a-hearing.html")],
    figures=[fig("10 minutes", TOUR_CITE, "more than 10 minutes early or late")])

GUIDES += [TOUR]


# ---------------------------------------------------------------------------
# PUTTING AN ARTICLE ON THE WARRANT (the person, 24 October 2026: "Filing a
# town warrant is a good one as well"). From RSA 39, 40:13 and 197 alone, read
# on 24 October 2026 in this site's own Laws pages, which print the statute
# table: no agency page is needed, because the law states the whole procedure.
# A city, and a town whose charter replaced its meeting with a council, has no
# warrant a petition reaches this way, and the guide says so and sends the
# reader to the Learn page that explains them rather than to a charter it
# cannot read. The deadlines are the law's; a town's own date for its meeting
# is not, so the guide gives the rule and has the reader ask the clerk for the
# day.
# ---------------------------------------------------------------------------
WARRANT_READ = "2026-10-24"

WARRANT = guide(
    "town-warrant-article", "How to Put an Article on Your Town Meeting Warrant",
    "Petitioning your selectmen or school board to put a question before the voters at the annual "
    "town or school district meeting: the signatures, the deadline, and what happens next.",
    "Any registered voter can ask the voters of their town or school district to decide a question. "
    "Write it as a warrant article, collect the signatures of 25 registered voters, or 2 percent of "
    "them if that is fewer (never fewer than 10), and hand the petition to the selectmen or the "
    "school board before the deadline. They must put it on the warrant for the annual meeting, "
    "where the voters decide it.",
    [box("Write the article: one question, stated clearly and without commentary."),
     box("Collect the signatures of 25 registered voters, or 2 percent if fewer, never under 10."),
     ask("Does your town or school district vote on its articles at the polls (SB 2)?",
         [("No: a traditional meeting",
           "Town: due by the fifth Tuesday before the meeting. School district: 30 days before "
           "it, or the second Tuesday in March if that is earlier."),
          ("Yes: SB 2",
           "The petition is due by the second Tuesday in January, for a March meeting.")]),
     box("The selectmen or school board put it on the warrant, and the voters decide it.")],
    [step("Check that this is the route for your town",
          "<p>This guide is for a town that holds a town meeting and for a school district. In a "
          "town, petition the <b>selectmen</b>; for the school district meeting, the <b>school "
          "board</b>. A city, or a town whose charter replaced its meeting with a town council, "
          "is governed by an elected council instead, and its charter sets its own rules; "
          '<a href="/learn/city-and-town-government.html">Cities, Towns and Who Runs Them</a> '
          "explains the difference.</p>"
          "<p>Find out whether your town or school district holds a <b>traditional meeting</b>, "
          "where the voters debate and vote on each article in the same room, or uses the "
          "<b>official ballot</b> form called <b>SB 2</b>, where the articles are debated at a "
          "deliberative session and voted on later at the polls. The deadline depends on it, so ask "
          "your town clerk or the selectmen&rsquo;s office which your town uses and the date of "
          "its meeting.</p>",
          actions=[("Find your town or city clerk", SOS_CLERKS)],
          law=["RSA 39:1", "RSA 40:13"]),
     step("Write the article",
          "<p>A warrant article states the subject the voters are asked to act on. The law "
          "requires the intent and effect of each article to be stated clearly and without "
          "commentary or ambiguity, and nothing done at a meeting is valid unless its subject is "
          "stated in the warrant. Write one question, as you want it to appear, for example "
          "&ldquo;To see if the town will vote to&hellip;&rdquo;.</p>"
          "<p>The selectmen or the school board may make only minor changes to the wording, and "
          "never ones that change what the article was meant to do.</p>",
          law=["RSA 39:2", "RSA 39:3", "RSA 39:3-c"]),
     step("Collect the signatures",
          "<p>The petition must be signed by <b>25 or more registered voters</b> of the town or "
          "school district, or <b>2 percent</b> of its registered voters if that is fewer, and "
          "never fewer than 10.</p>",
          law=["RSA 39:3", "RSA 197:6"]),
     step("Hand it in before the deadline",
          "<p>Give the petition to the selectmen, or any one of them, for the town meeting, or to "
          "the school board, or any one member, for the school district meeting. Keep a copy.</p>"
          + table("When a petitioned article is due",
                  ["Meeting", "Traditional meeting", "SB 2 (official ballot)"],
                  [["Town", "By the fifth Tuesday before the annual meeting",
                    "By the second Tuesday in January, for a meeting in March"],
                   ["School district",
                    "At least 30 days before the meeting, or by the second Tuesday in March if "
                    "that is earlier",
                    "By the second Tuesday in January, for a meeting in March"]])
          + "<p>Meeting in April or May, or proposing a bond? See the questions below.</p>",
          law=["RSA 39:3", "RSA 197:6", "RSA 40:13, II-a"]),
     step("What happens next",
          "<p>The selectmen or the school board must put the article in the warrant. The warrant "
          "is posted at least 14 days before the meeting.</p>"
          "<p>At a <b>traditional meeting</b> the voters debate the article and can amend it "
          "before they vote; where it asks for a sum of money, the meeting may vote more or less, "
          "within the limits of the municipal budget law where the town has adopted it. "
          "In an <b>SB 2</b> town or district it is debated at the first session, the "
          "deliberative session, where it can be amended but not changed to remove its subject, "
          "and every article then goes on the official ballot for the final vote.</p>",
          law=["RSA 39:3-b", "RSA 39:9", "RSA 39:5", "RSA 197:7", "RSA 40:13, IV"])],
    [("Time for Holding Town Meetings and Warning Thereof, RSA 39", "/laws/39"),
     ("Government of Town Meeting, RSA 40", "/laws/40"),
     ("School Meetings and Officers, RSA 197", "/laws/197"),
     ("Town and city clerks (Secretary of State)", SOS_CLERKS)],
    ["39", "40", "197"],
    [claim("A town meets annually on the second Tuesday of March, or under RSA 40:13 if adopted.",
           "RSA 39:1", WARRANT_READ),
     claim("The subject of all business is distinctly stated in the warrant, its intent and "
           "effect clearly and without commentary or ambiguity; nothing done is valid unless so "
           "stated, except electing officers; a specific sum may be decreased or increased by the "
           "town's vote, subject to RSA 32:18.", "RSA 39:2", WARRANT_READ),
     claim("On the written application of 25 or more registered voters or 2 percent, whichever "
           "is less, never fewer than 10, presented to the selectmen or one of them by the fifth "
           "Tuesday before the annual meeting, the selectmen insert the petitioned article with "
           "only minor textual changes that do not change its intended effect; registered voters "
           "counted before the last state general election; a primary petitioner may be named, "
           "else the first registered voter listed.", "RSA 39:3", WARRANT_READ),
     claim("Selectmen who refuse to insert a petitioned article are guilty of a violation.",
           "RSA 39:3-b", WARRANT_READ),
     claim("A petitioned article abolishing a planning board or zoning commission must meet RSA "
           "673:18, II.", "RSA 39:3-c", WARRANT_READ),
     claim("The warrant is posted at least 14 days before the meeting.", "RSA 39:5", WARRANT_READ),
     claim("The school board posts the warrant 14 days before the meeting.", "RSA 197:7",
           WARRANT_READ),
     claim("If the selectmen unreasonably refuse to insert an article, a superior court justice, "
           "on the written application of 25 or more voters or 1/6 of them, may order it "
           "inserted.", "RSA 39:9", WARRANT_READ),
     claim("SB 2 subdivisions vote all issues by official ballot in two sessions; petitioned "
           "articles under RSA 39:3 and 197:6 are due the second Tuesday in January, February or "
           "March for meetings in March, April or May, the preceding Friday for a bond under "
           "33:8-a; the first session debates and may amend articles but not eliminate their "
           "subject; every article goes on the official ballot for a final vote.",
           "RSA 40:13", WARRANT_READ),
     claim("A school district petition of 25 or more voters or 2 percent, whichever is less, "
           "never fewer than 10, presented to the school board or one of them not later than 30 "
           "days before the meeting or the second Tuesday in March, whichever is earlier; minor "
           "textual changes only; a primary petitioner.", "RSA 197:6", WARRANT_READ),
     claim("The town and city clerks lookup lists each town's clerk.", SOS_CLERKS, CHECKED),
     ours("Cities, Towns and Who Runs Them explains a city's council and a town council charter.",
          "/learn/city-and-town-government.html", WARRANT_READ),
     ours("Town Meeting and Local Government explains the traditional meeting and SB 2.",
          "/learn/local-government.html", WARRANT_READ)],
    more=civics.faq(
        ("Which registered voters count toward the 2 percent?",
         "<p>For a town, the 2 percent is counted from the voters registered before the last "
         "state general election.</p>"),
        ("What is a primary petitioner?",
         "<p>You may name one signer as the <b>primary petitioner</b>. If you do not, the first "
         "registered voter listed is the primary petitioner.</p>"),
        ("My SB 2 town meets in April or May, or the article proposes a bond. When is it due?",
         "<p>An SB 2 town or district that holds its meeting in April or May has the same "
         "deadline a month or two later: the second Tuesday in February or in March. If the "
         "article proposes a bond, the SB 2 deadline is the Friday before.</p>"),
        ("What if the selectmen refuse to put it on the warrant?",
         "<p>In a town, selectmen who refuse are guilty of a violation, and if they unreasonably "
         "refuse, a Superior Court justice can order the article inserted on the written "
         "application of 25 or more voters, or of one-sixth of the town&rsquo;s voters.</p>"),
        ("Are there special rules for some articles?",
         "<p>An article that would abolish a planning board or zoning commission must also meet "
         "the petition rule in <a href=\"/laws/673#s18\">RSA 673:18, II</a>.</p>"))
    + "<h2>Who Can Help</h2>"
         "<p>Start with your town clerk or the selectmen&rsquo;s office, for the date of the "
         "meeting and whether it uses SB 2. For the school district meeting, ask the school "
         "board. The Secretary of State lists every town&rsquo;s clerk.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_CLERKS}" target="_blank" rel="noopener">'
         "Find your town or city clerk</a></p>",
    see=[("Town meeting and local government", "/learn/local-government.html"),
         ("Cities, towns and who runs them", "/learn/city-and-town-government.html"),
         ("How to vote", "/guides/how-to-vote.html")],
    figures=[fig("30 days", "RSA 197:6", "not later than 30 days before the date prescribed for "
                                         "the school district meeting"),
             fig("14 days", "RSA 39:5", "at least 14 days before the day of meeting")])

GUIDES += [WARRANT]


# ---------------------------------------------------------------------------
# WORKING AT THE POLLS (the person, 26 October 2026: "how to be a poll worker
# or volunteer with elections including explaining the structure of election
# moderators and various ways the results are confirmed to be accurate").
# From the statutes alone, as this site's Laws pages print them that day:
# who the election officers are and how each is chosen (RSA 40:1, 41:16,
# 41:46-a, 652:14, 658), what they may not do (658:24, 659:44, 659:58), and
# each check on the count the law sets -- paper ballots, approved and tested
# counting devices, a public count, the moderator's declaration, the
# clerk's return, sealed and kept ballots, recounts and the state audit
# (656, 659, 660). RSA 658:2 carries a change that takes effect on 1 January
# 2028 (HB 481 of 2026), and the text on the Laws page may already be the
# new one, so the guide gives no date from it: only who appoints inspectors,
# which both versions say. The Secretary of State's own pages for election
# workers have not been read here, so nothing is said of training or pay.
# ---------------------------------------------------------------------------
ELECTION_READ = "2026-10-26"
# The Secretary of State's published procedures (RSA 660:17-c requires them),
# read from the person's copies of 26 October 2026, at the addresses the
# person gave that day.
SOS_RECOUNT = ("https://www.sos.nh.gov/sites/g/files/ehbemt561/files/documents/2024-09/"
               "2024-recount-procedures-primary.pdf")
SOS_TOP_AUDIT = ("https://www.sos.nh.gov/sites/g/files/ehbemt561/files/documents/2024-10/"
                 "audit-procedures-top-of-ticket.pdf")
_OFFICER_ROWS = [
    ("Moderator",
     "Elected by the voters by ballot, for 2 or 3 years as the town decides; in a city, each "
     "ward&rsquo;s moderator is elected at every other city election",
     "Oversees the voting and the counting of votes, appoints the assistants, and announces "
     "the result", "RSA 40:1, 659:9, 659:60, 659:70"),
    ("Town or ward clerk",
     "A town&rsquo;s clerk is chosen by ballot at the annual town meeting",
     "Opens the sealed ballots and counts them with the officers, gives the ballot clerks a "
     "copy of the checklist, prepares and signs the election return, and keeps the sealed "
     "ballots afterward", "RSA 41:16, 658:25, 658:31, 659:74, 659:98"),
    ("Supervisors of the checklist",
     "Three voters of the town, one elected by ballot every even-numbered year for 6 years, or "
     "for a 3-year term where the town adopts it",
     "Bring the corrected checklist of voters and stay all day; may appoint assistant "
     "supervisors to register voters on election day", "RSA 41:46-a, 658:7, 659:10"),
    ("Selectmen",
     "The town&rsquo;s or ward&rsquo;s selectmen",
     "Provide and equip the polling place, appoint inspectors where the parties do not, and are "
     "present when the ballots are sealed", "RSA 658:2, 658:9, 658:22, 659:95"),
    ("Inspectors of election",
     "Appointed by the state committees of the two parties that received the most votes for "
     "governor at the last general election, or by the selectmen in equal numbers from those "
     "two parties; registered to vote at that polling place",
     "Two, one from each party, are the ballot clerks who hand out the ballots; the others do "
     "what the moderator assigns, including helping a voter who asks for help",
     "RSA 658:2, 658:3, 658:25, 659:20"),
    ("Assistant moderator and other officials",
     "Appointed by the moderator for that election, at least 17 years old",
     "What the moderator delegates to them, except declaring the vote",
     "RSA 658:7, 658:7-a, 658:8"),
]


def _law_links(cites):
    """"RSA 658:7, 658:7-a" as links to each section on the Laws pages."""
    out = []
    for c in cites.replace("RSA ", "").split(", "):
        ch, sec = c.split(":")
        out.append(f'<a href="/laws/{ch}#s{sec}">{c}</a>')
    return "RSA " + ", ".join(out)


# The sections on training, the manual and pay, read on the Laws pages on 26
# October 2026 after the person's printout of Ballotpedia pointed to them.
PW_READ = "2026-10-26"

ELECTION = guide(
    "election-worker", "How to Work at the Polls on Election Day",
    "Serving as an election officer at your polling place in New Hampshire: who runs an "
    "election, how each officer is chosen, how to take part, and how the count is checked.",
    "Every polling place is run by local election officers. The <b>moderator</b>, elected by "
    "the voters, runs the polling place and oversees the count. The <b>clerk</b> handles the "
    "ballots and the official return, the <b>supervisors of the checklist</b> keep the list of "
    "voters, and the <b>inspectors of election</b>, appointed through the two largest parties, "
    "hand out ballots and help voters. The moderator may also appoint assistants for the day. "
    "The count is public, every election is held on paper ballots that are sealed and kept "
    "afterward, and recounts and a state audit check the count against the paper.",
    [ask("How would you like to serve?",
         [("As an inspector of election", "Appointed through your party&rsquo;s state "
           "committee, or by your selectmen; you must be registered to vote at that polling "
           "place."),
          ("As an assistant for the day", "The moderator may appoint election officials, at "
           "least 17 years old."),
          ("In an elected office", "Run for moderator, town clerk or supervisor of the "
           "checklist.")]),
     box("Take the oath, and serve from the opening of the polls until the ballots are "
         "sealed."),
     box("After the polls close, the votes are counted in public, the moderator announces the "
         "result, and the ballots are sealed and kept for a recount or an audit.")],
    [step("Learn who runs the polling place",
          "<p>The law calls them election officers: the moderator and the moderator&rsquo;s "
          "deputy or assistant, the town, city or ward clerk and their deputies, the selectmen, "
          "and the supervisors of the checklist. The inspectors of election work beside "
          "them.</p>"
          + table("Who runs a polling place",
                  ["Officer", "How chosen", "What they do", "The law"],
                  [(a, b, c, _law_links(d)) for a, b, c, d in _OFFICER_ROWS]),
          law=["RSA 652:14", "RSA 652:23", "RSA 41:1-a", "RSA 656:1"]),
     step("Ask to be appointed",
          "<p><b>Inspectors of election</b> are appointed for each polling place by the state "
          "committees of the two parties that received the most votes for governor at the last "
          "general election, through their chairs. Where a party does not appoint them, the "
          "selectmen do, in equal numbers from the two parties. An inspector must be "
          "registered to vote at the polling place where they serve, is sworn, and holds the "
          "office for 2 years. The committees, or the selectmen with the moderator, may also "
          "name alternates, who are called in order when an inspector cannot serve.</p>"
          "<p><b>Assistants for the day.</b> The moderator may appoint an assistant moderator "
          "and the other election officials the moderator thinks necessary, and the supervisors "
          "may appoint assistant supervisors to register voters on election day. An assistant "
          "must be at least 17 years old, takes the oath, and serves only for that "
          "election.</p>"
          "<p>So to serve, ask your town&rsquo;s moderator, your party&rsquo;s state committee, "
          "or your selectmen.</p>"
          "<p><b>The manual and training.</b> Before each state general election the Secretary "
          "of State, with the Attorney General&rsquo;s approval, prepares a manual on New "
          "Hampshire&rsquo;s election laws and how to conduct an election, written in "
          "nontechnical language. It goes free to every moderator, board of selectmen, city "
          "council, board of supervisors of the checklist and town, city and ward clerk, and the "
          "Secretary of State may send it to anyone else who asks. The law also refers to the "
          "online training on the Secretary of State&rsquo;s website, and has the Secretary of "
          "State train the supervisors of the checklist in using the state&rsquo;s voter "
          "database to confirm a voter&rsquo;s identity.</p>",
          law=["RSA 658:2", "RSA 658:3", "RSA 658:4", "RSA 658:5", "RSA 658:7", "RSA 658:7-a",
               "RSA 658:8", "RSA 652:22", "RSA 659:13", "RSA 659:77"]),
     step("Know what an election officer may not do",
          "<p>A person whose name is on the ballot for an office other than an election office "
          "may not work as an election official in that election. A moderator, clerk, "
          "selectman, inspector or supervisor who is on the ballot may keep their place, but "
          "may not handle marked ballots or count votes; the moderator appoints someone to "
          "count in their place.</p>"
          "<p>No election officer may electioneer while on duty, that is, act in any way meant "
          "to influence how someone votes. Doing so is a misdemeanor.</p>",
          law=["RSA 658:24", "RSA 659:58", "RSA 659:44"]),
     step("How the count is checked on election day",
          "<p><b>Before the polls open.</b> Every election is held on paper ballots, so that "
          "the votes can be examined and recounted. The clerk breaks the seal on the ballots in "
          "public, and the officers count them in front of the clerk, the moderator and at "
          "least one other voter. The ballot box is opened in public and shown to be "
          "empty.</p>"
          "<p><b>Counting machines.</b> A town may use only a counting device the Ballot Law "
          "Commission has approved, and only one that reads the voter&rsquo;s choice from a "
          "paper ballot. Each device is tested after it is installed and before every "
          "election. The clerk gives public notice of the test and marks the test ballots "
          "&ldquo;TEST&rdquo;. The device is sealed, no seal may be broken without 2 "
          "witnesses, and every break is logged. If a seal looks tampered with, the moderator "
          "does not use the device and reports it to the Attorney General and the Secretary "
          "of State.</p>"
          "<p><b>After the polls close.</b> The votes are counted in public and the count is "
          "not stopped until it is finished. Where officers disagree on how to count a mark, "
          "the majority of those counting decides; if no count has a majority, the ballot is "
          "not counted for that office. The counting documents are open for public review "
          "when the results are announced, and a machine&rsquo;s printed results are posted "
          "within 60 minutes of the last ballot. The moderator announces the final count, and "
          "the clerk prepares the election return in front of the other officials, signs it, "
          "and sends a copy to the Secretary of State by 8:00&nbsp;AM the next day. The other "
          "copy is kept by the clerk, open to the public.</p>"
          "<p><b>Sealing the ballots.</b> The moderator, with the selectmen, seals every "
          "ballot in containers from the Secretary of State, writes the number of ballots on "
          "each seal, and both sign it. The clerk stores the sealed containers and keeps a log "
          "of where they are, and only those working for the clerk, a recount or the "
          "Secretary of State may reach them.</p>",
          law=["RSA 656:1-a", "RSA 658:31", "RSA 658:36", "RSA 656:41", "RSA 656:42",
               "RSA 659:63", "RSA 659:64", "RSA 659:70", "RSA 659:75", "RSA 659:95",
               "RSA 659:98"]),
     step("Recounts and the state audit",
          "<p><b>A recount.</b> A candidate who lost by less than 20 percent of the ballots "
          "cast may ask the Secretary of State in writing for a recount, no later than the "
          "Friday after the election, and pays a fee that depends on the office and the "
          "margin: a candidate for state representative pays $10 when the margin is under one "
          "percent, and a candidate for governor $500. The Secretary of State and assistants "
          "recount the ballots in Concord, looking at each one; no machine may be used. The "
          "candidates may inspect the ballots and protest how any one is counted.</p>"
          "<p><b>How a recount runs.</b> The Secretary of State publishes its recount "
          "procedures; those for state primaries describe it this way. Every recount is open to "
          "the public, and its time and place are posted on the Secretary of State&rsquo;s "
          "website. At least one team of two people counts each race. Across the table from "
          "them sits each candidate, or one person for the candidate, with other observers "
          "standing behind; cameras show every ballot and the tally sheet on screens facing the "
          "candidates, and do not record. Each box is opened in front of them and shown empty. "
          "The ballots are sorted into piles, in a race for one seat one for each candidate and "
          "piles for undervotes, overvotes and write-ins, and counted out loud in sets of 25, "
          "each set checked by the second counter. A candidate may challenge how any ballot is "
          "counted, without giving a reason; the Secretary of State rules on it, and a ballot "
          "still disputed is kept with a memo of the ruling in case of an appeal. The "
          "Secretary of State compares the recount with the election night results and "
          "declares the result, which is final unless changed on an appeal to the Ballot Law "
          "Commission within 10 days.</p>"
          "<p><b>The top-of-the-ticket audit.</b> When state representative races are "
          "recounted after a general election, the Secretary of State also audits the votes on "
          "those same ballots for President, United States Senate, United States House or "
          "Governor, choosing the office, for 10 of the recounted races picked at random (or "
          "all of them, if fewer than 10 are recounted). A discrepancy of more than one percent "
          "from the reported results allows a full recount of that race. The audit follows the "
          "general election recount procedures, and its results are published on the "
          "Secretary of State&rsquo;s website.</p>"
          "<p><b>The audit.</b> After each state primary, general election and presidential "
          "primary, the Secretary of State audits the counting devices. At least 8 devices "
          "are chosen at random, and which ones is not announced until the polls open. A team "
          "of at least 2 people runs the paper ballots through separate audit equipment and "
          "compares its results with the device&rsquo;s, and examines a random sample of the "
          "paper ballots by hand. The audit is open to the public. If there are significant "
          "differences, the Secretary of State may look at more ballots or order a full hand "
          "recount. The results are published before noon on the Friday after the "
          "election.</p>",
          actions=[("Recount procedures (Secretary of State)", SOS_RECOUNT),
                   ("Top-of-the-ticket audit procedures (Secretary of State)", SOS_TOP_AUDIT)],
          law=["RSA 660:1", "RSA 660:2", "RSA 660:4", "RSA 660:5", "RSA 660:17-b",
               "RSA 660:17-c", "RSA 660:33", "RSA 660:35"])],
    [("Election Officers, RSA 658", "/laws/658"),
     ("Conduct of Elections, RSA 659", "/laws/659"),
     ("Recounts and Audits, RSA 660", "/laws/660"),
     ("Recount Procedures, State Primary Elections (Secretary of State, 2024)", SOS_RECOUNT),
     ("Audit Procedures, Top-of-the-Ticket Audits (Secretary of State)", SOS_TOP_AUDIT),
     ("Ballots and Counting Devices, RSA 656", "/laws/656"),
     ("Town Meetings and Moderators, RSA 40", "/laws/40"),
     ("Town Officers, RSA 41", "/laws/41")],
    ["658", "659", "660"],
    [claim("Election officer means any moderator, deputy moderator, assistant moderator, town "
           "clerk, deputy town clerk, city clerk, deputy city clerk, ward clerk, selectman, "
           "supervisor of the checklist, registrar, or deputy registrar.", "RSA 652:14",
           ELECTION_READ),
     claim("The secretary of state shall be the chief election officer for the state.",
           "RSA 652:23", ELECTION_READ),
     claim("The secretary of state, with the advice and approval of the attorney general, shall "
           "prepare preceding each state general election an up-to-date manual on the New "
           "Hampshire election laws and procedures for conducting elections, written in "
           "nontechnical language, distributed free of charge to each moderator, board of "
           "selectmen, city council, and board of supervisors of the checklist and to each town, "
           "city, and ward clerk; the secretary of state may distribute it to any other person "
           "who requests it.", "RSA 652:22", PW_READ),
     claim("The secretary of state shall provide training for supervisors of the checklist on "
           "how the nonpublic data in the statewide centralized voter registration database may "
           "be used to satisfy voter identification requirements.", "RSA 659:13", PW_READ),
     claim("An election monitor's report documents the extent to which the town or ward "
           "complies with state law and utilizes the best practices set forth in the election "
           "procedures manual and the on-line training available on the secretary of state's "
           "website.", "RSA 659:77", PW_READ),
     claim("When the ballot law commission directs the supervisors to revise and verify a "
           "checklist, the supervisors and assistant supervisors shall receive such sums as may "
           "be voted by the city government or town meeting of the city or town in which they "
           "serve.", "RSA 654:38", PW_READ),
     claim("Every 2 years or 3 years a moderator shall be chosen by ballot, by plurality vote; "
           "the election of moderators in city wards shall be at every other regular city "
           "election.", "RSA 40:1", ELECTION_READ),
     claim("At any annual town meeting the voters may vote to determine if they are in favor of "
           "having 2-year or 3-year terms for the moderator.", "RSA 41:1-a", ELECTION_READ),
     claim("Every town at the annual meeting shall choose, by ballot, a town clerk.", "RSA 41:16",
           ELECTION_READ),
     claim("Ballots for use in all state elections shall be prepared and delivered by the "
           "secretary of state.", "RSA 656:1", ELECTION_READ),
     claim("The board of supervisors of the checklist shall consist of 3 legal voters of the "
           "town; at the annual town election in every even numbered year the voters elect one "
           "supervisor for a term of 6 years; a city or town's legislative body may adopt a "
           "3-year term.", "RSA 41:46-a", ELECTION_READ),
     claim("The state political committees of the 2 parties which received the largest number of "
           "votes cast for governor at the last previous general election appoint, through their "
           "chairmen, inspectors of election to act at each polling place; if the appointments "
           "are not made, the selectmen make them in equal numbers from the 2 parties.",
           "RSA 658:2", ELECTION_READ),
     claim("The inspectors of election shall be registered to vote at the polling place where "
           "they serve.", "RSA 658:3", ELECTION_READ),
     claim("Each inspector of election shall be sworn and shall hold office for 2 years.",
           "RSA 658:4", ELECTION_READ),
     claim("The political committees, or the selectmen in consultation with the moderator, may "
           "designate a list of alternates, called in numerical order when a principal appointee "
           "is unavailable.", "RSA 658:5", ELECTION_READ),
     claim("The moderator may appoint an assistant moderator and such other election officials "
           "as he or she deems necessary; they take the oath and have the powers the moderator "
           "delegates, except the declaration of the vote; the supervisors may appoint assistant "
           "supervisors to register voters on election day.", "RSA 658:7", ELECTION_READ),
     claim("An assistant election official shall be at least 17 years of age.", "RSA 658:7-a",
           ELECTION_READ),
     claim("An assistant election official's term expires at the end of the proceedings at the "
           "election for which he or she was appointed.", "RSA 658:8", ELECTION_READ),
     claim("The selectmen of each town and ward shall provide a suitable place to hold state "
           "elections, furnished with a ballot box, pens or pencils and booths.", "RSA 658:9",
           ELECTION_READ),
     claim("If an appointed inspector is absent, the selectmen appoint a qualified person, using "
           "the list of alternates.", "RSA 658:22", ELECTION_READ),
     claim("A person other than a moderator, clerk, selectman, inspector of election or "
           "supervisor of the checklist whose name appears on a ballot for an elective position, "
           "other than a position of an election official, is disqualified from performing "
           "duties as an election official in that election; those officers are disqualified "
           "from handling marked ballots and counting votes.", "RSA 658:24", ELECTION_READ),
     claim("Two of the inspectors, one from each of the 2 political parties, designated by the "
           "moderator, act as ballot clerks, have charge of the ballots and furnish them to the "
           "voters, with a duplicate copy of the checklist from the clerk; the other inspectors "
           "do the duties the moderator assigns, including assisting voters under RSA 659:20.",
           "RSA 658:25", ELECTION_READ),
     claim("The seal of the packages of ballots is publicly broken by the clerk, and the ballots "
           "are examined and counted by the election officers in the presence of the clerk, the "
           "moderator, and at least one other legal voter.", "RSA 658:31", ELECTION_READ),
     claim("At the opening of the polls, the ballot box shall be publicly opened and shown to be "
           "empty.", "RSA 658:36", ELECTION_READ),
     claim("All elections shall be conducted using paper ballots, for purposes of facilitating "
           "the examination and recounting of votes cast.", "RSA 656:1-a", ELECTION_READ),
     claim("No device shall be used in any election unless it reads the voter's choice on a "
           "paper ballot and is of a type approved by the ballot law commission.", "RSA 656:41",
           ELECTION_READ),
     claim("Each device shall be tested after installation and prior to each election; the clerk "
           "gives public notice of the pre-election test and marks the test ballots \"TEST\"; no "
           "person shall break a counting device seal without the presence of 2 witnesses, and "
           "each break is recorded in the activity log; if a seal appears tampered with, the "
           "moderator shall refrain from using the device and report it to the attorney general, "
           "the secretary of state, the clerk and the selectmen.", "RSA 656:42", ELECTION_READ),
     claim("It shall be the duty of the moderator to secure the observance of the provisions "
           "relating to the conduct of voting.", "RSA 659:9", ELECTION_READ),
     claim("The supervisors shall be present at the opening of each election with the corrected "
           "checklist and remain until the close.", "RSA 659:10", ELECTION_READ),
     claim("A voter who needs assistance receives the assistance of one or both of the "
           "inspectors of election detailed for that purpose by the moderator, or of a person of "
           "the voter's choice.", "RSA 659:20", ELECTION_READ),
     claim("No election officer shall electioneer while in the performance of official duties, "
           "meaning to act in any way specifically designed to influence the vote of a voter; a "
           "violation is a misdemeanor.", "RSA 659:44", ELECTION_READ),
     claim("An election official who is a candidate for an office other than an election "
           "official shall disqualify himself or herself from the tabulation of votes, and the "
           "moderator shall appoint an assistant in that official's place.", "RSA 659:58",
           ELECTION_READ),
     claim("The moderator shall oversee the counting of votes by other election officers.",
           "RSA 659:60", ELECTION_READ),
     claim("The counting and tabulation of votes shall be public and shall not be adjourned nor "
           "postponed until completed; documents generated during the tabulation shall be "
           "available for public review when results are announced; the printed results from "
           "the voting machine shall be posted within 60 minutes of running the last ballot.",
           "RSA 659:63", ELECTION_READ),
     claim("Where the election officers disagree over how to count a ballot, it is counted by "
           "the majority vote of the officials present and counting; if no count has a "
           "majority, the ballot is defective for that office.", "RSA 659:64", ELECTION_READ),
     claim("The moderator shall announce the final count for each office and question.",
           "RSA 659:70", ELECTION_READ),
     claim("The town or ward clerk shall prepare the election return in the presence of the "
           "other election officials, in duplicate, and sign and certify it.", "RSA 659:74",
           ELECTION_READ),
     claim("One copy of the return shall be forwarded to the secretary of state no later than "
           "8:00 a.m. on the day following a state election; the other is kept by the clerk and "
           "open to public inspection.", "RSA 659:75", ELECTION_READ),
     claim("The moderator, in the presence of the selectmen, places the ballots in the containers "
           "provided by the secretary of state, seals them, enters the number of ballots on the "
           "sealer, and both sign it.", "RSA 659:95", ELECTION_READ),
     claim("The clerk stores the sealed containers, keeps a log of their location, and once "
           "stored they are accessible only to individuals working under the direction of the "
           "clerk, as required for recounts, or for the secretary of state.", "RSA 659:98",
           ELECTION_READ),
     claim("A candidate may apply in writing to the secretary of state for a recount, no later "
           "than the Friday following the election, if the difference is less than 20 percent "
           "of the total ballots cast.", "RSA 660:1", ELECTION_READ),
     claim("Where the difference is less than one percent: candidate for governor, $500; "
           "candidate for state representative, $10.", "RSA 660:2", ELECTION_READ),
     claim("A recount takes place at a state facility in Concord designated by the secretary of "
           "state.", "RSA 660:4", ELECTION_READ),
     claim("The secretary of state and assistants shall visually inspect each ballot; no "
           "mechanical, optical, or electronic device shall be used; the candidates may inspect "
           "the ballots and protest the counting of any ballot.", "RSA 660:5", ELECTION_READ),
     claim("All recounts, including location and time, will be published on the Secretary of "
           "State's website. All recounts are open to the public. The Secretary of State will "
           "assign at least one team of two people for each scheduled recount. The space on the "
           "opposite side of the table is reserved for each candidate, the candidate's counsel, "
           "or the candidate's designee - one individual for each candidate - to sit, observe, "
           "and exercise their right to protest. Additional observers may stand behind the "
           "candidates or designees. The projection system shows the ballots and tally sheet; "
           "the cameras do not record. The Secretary of State or designee will open all the "
           "boxes from each race in view of the candidates, designees, and observers; the box "
           "will be shown to be empty.", SOS_RECOUNT, ELECTION_READ),
     claim("Sorting in a primary election with 'Vote for not more than 1.' - Recounters will "
           "sort all ballots into the following piles: Candidate 1, Candidate 2, Candidate 3, "
           "etc.; Undervote; Overvote; Write-in. The first recounter will show all ballots by "
           "placing the ballot under the camera and audibly counting out 25 ballots. The second "
           "recounter checks this count of 25 ballots. A candidate or designee does not need to "
           "state a reason to challenge a ballot. The Secretary of State shall rule on the "
           "voter's intention of the challenged ballot. If a candidate or their designee wishes "
           "to further challenge the ballot, the Secretary of State will attach a memorandum to "
           "the ballot stating the ruling; the ballots will be kept separate in case the results "
           "are appealed to the Ballot Law Commission. The summary sheet will compare the "
           "recount results to the election night results. The Secretary of State will declare "
           "the result of the recount which shall be final unless the result is changed because "
           "of a successful appeal made within 10 days to the Ballot Law Commission.",
           SOS_RECOUNT, ELECTION_READ),
     claim("For general election recounts of state representative races, the secretary of "
           "state's office shall randomly select 10 of the state representative races to "
           "conduct an audit of the votes cast on those ballots for President, United States "
           "Senate, United States House of Representatives, or Governor. The Secretary of State "
           "will select the office to be audited. The audit procedures for the selected race "
           "will follow the same procedures used for a state general election recount. The "
           "Secretary of State will announce the results of each audit and publish the results "
           "of the audit on the Secretary of State's website.", SOS_TOP_AUDIT, ELECTION_READ),
     claim("For general election recounts of state representative races, the secretary of "
           "state's office shall conduct an audit of the votes cast on those ballots for "
           "President, United States Senate, United States House of Representatives, or "
           "governor, using the ballots for 10 of the state representative races to be "
           "recounted, selected randomly; if less than 10 races are to be recounted, the "
           "ballots for each recounted race shall be audited; select the office to be audited; "
           "and allow a full recount of any race where there is a discrepancy of greater than "
           "one percent from the election results reported to the secretary of state.",
           "RSA 660:17-b", ELECTION_READ),
     claim("The secretary of state shall publish all recount and audit procedures, as well as "
           "the times to hold any recounts and audits that may take place.", "RSA 660:17-c",
           ELECTION_READ),
     claim("The secretary of state shall conduct an audit of the devices used to tabulate ballots "
           "after each state primary, general elections, and after the presidential primary.",
           "RSA 660:33", ELECTION_READ),
     claim("The secretary of state randomly selects not less than 8 devices and does not announce "
           "them until after the polls are open; each audit team has at least 2 individuals; the "
           "audit is open to the public; the paper ballots are processed by the audit equipment "
           "and compared with the device; a random sample of the paper ballots is physically "
           "examined; on significant differences the secretary may expand the sample or order a "
           "full hand recount; results are available prior to 12:00 p.m. on the Friday after "
           "the election.", "RSA 660:35", ELECTION_READ)],
    more=civics.faq(
        ("Do I have to belong to a party?",
         "<p>For an inspector of election, the law looks to the parties: inspectors are appointed from the "
         "two parties that received the most votes for governor, by their state committees or "
         "by the selectmen in equal numbers from the two, and the two ballot clerks are one from "
         "each. The law does not tie the assistants the moderator appoints to a party.</p>"),
        ("Can I work at the polls if I am on the ballot?",
         "<p>Not as an election official, if you are running for an office other than an "
         "election office. A moderator, clerk, selectman, inspector or supervisor who is on the "
         "ballot keeps their place but may not handle marked ballots or count votes.</p>"),
        ("Is there training?",
         "<p>The Secretary of State prepares a manual on the election laws and procedures before "
         "each state general election, sends it free to moderators, clerks, selectmen and "
         "supervisors of the checklist, and may send it to anyone who asks. The law also refers "
         "to online training on the Secretary of State&rsquo;s website.</p>"),
        ("Are election workers paid?",
         "<p>The sections that create inspectors of election and the moderator&rsquo;s "
         "assistants (RSA 658:2 to 658:8) say nothing about pay. One election law does: when the "
         "Ballot Law Commission orders a checklist re-verified, the supervisors and their "
         "assistants are paid what the town or city votes "
         '(<a href="/laws/654#s38">RSA 654:38</a>).</p>'),
        ("Who decides a ballot whose mark is unclear?",
         "<p>The election officers counting the votes, by majority. If no way of counting it "
         "wins a majority, the ballot is not counted for that office.</p>"),
        ("Can I watch the count?",
         "<p>Yes. The law makes the counting public, and its documents are open for public "
         "review when the results are announced. The state audit of counting machines is open "
         "to the public too.</p>"),
        ("Who oversees elections across the state?",
         "<p>The Secretary of State, the state&rsquo;s chief election officer, who prepares the "
         "ballots, receives every town&rsquo;s return, and runs recounts and the audit.</p>")),
    see=[("How to vote", "/guides/how-to-vote.html"),
         ("How to run for office", "/guides/run-for-office.html")],
    figures=[fig("10 days", SOS_RECOUNT, "a successful appeal made within 10 days"),
             fig("2 or 3 years", "RSA 40:1", "Every 2 years or 3 years"),
             fig("6 years", "RSA 41:46-a", "one supervisor for a term of 6 years"),
             fig("3-year", "RSA 41:46-a", "may adopt a 3-year term"),
             fig("17 years", "RSA 658:7-a", "at least 17 years of age"),
             fig("2 years", "RSA 658:4", "shall hold office for 2 years"),
             fig("60 minutes", "RSA 659:63", "within 60 minutes of running the last ballot"),
             fig("$10", "RSA 660:2", "Candidate for state representative, $10"),
             fig("$500", "RSA 660:2", "Candidate for president, United States senator or "
                                      "governor, $500")])

GUIDES += [ELECTION]


# ---------------------------------------------------------------------------
# HOW YOUR PROPERTY TAX IS FIGURED, AND HOW TO READ YOUR BILL (the person, 25
# October 2026: "how to read your property tax bill or how property taxes are
# assessed"). From RSA 72, 75, 76 and 21-J alone, read on 25 October 2026 in
# this site's own Laws pages, which print the statute table, as the warrant
# guide is: the law says how property is appraised, who sets the rate, what a
# bill must show, when interest starts, and every exemption, credit and
# deferral a town may offer. The Department of Revenue Administration's own
# pages refuse this machine, and none of their addresses has been read, so the
# guide links none; a town's own figures -- its rate, its exemption amounts --
# are its own, and the guide sends the reader to the town for them. Abatement
# and the state's low-income relief have guides of their own, linked rather
# than repeated.
# ---------------------------------------------------------------------------
TAX_BILL_READ = "2026-10-25"

TAX_BILL = guide(
    "property-tax-bill", "How Your Property Tax Is Figured, and How to Read Your Bill",
    "How your town or city assesses your property, how the tax rate is set, what your property "
    "tax bill must show, when it is due, and the exemptions, credits and deferrals you can apply "
    "for.",
    "Your town or city assesses your property at its market value as of April 1, and must "
    "revalue every property at least every fifth year. The voters and officials of your town, "
    "school district and county set their budgets, and the state works out the rate that raises "
    "them. Your bill shows your assessment and four rates: town, local school, state education "
    "and county. If the tax is hard to pay, you may qualify for an exemption or credit, for "
    "which you apply to your town by April 15, or a deferral, by March 1 after the final "
    "bill.",
    [box("Your town assesses your property at its market value, as of April 1."),
     box("The budgets are voted; the state sets the rate that raises them."),
     box("Your bill shows your assessment and four rates: town, local school, state education "
         "and county."),
     ask("Is something wrong, or is the tax hard to pay?",
         [("The assessment is too high", "Ask your town for an abatement, by March 1 after the "
           "final bill."),
          ("It is hard to pay", "Apply to your town by April 15 for an exemption or credit, "
           "or by March 1 for a deferral.")])],
    [step("How your property is assessed",
          "<p>Your town or city&rsquo;s assessors or selectmen appraise your land and buildings "
          "at their <b>market value</b>: what the law calls their full and true value. Each "
          "year they adjust assessments for changes, such as an addition, a new owner, a "
          "subdivision or a change in zoning, and to correct errors, so that every assessment in "
          "town stays in proportion. At least every fifth year they reappraise every property "
          "in town at full value.</p>"
          "<p>The tax year runs from April 1 to March 31, and every property is taxed on what it "
          "was on April 1.</p>",
          law=["RSA 75:1", "RSA 75:8", "RSA 75:8-a", "RSA 76:2"]),
     step("How the tax rate is set",
          "<p>Your property tax pays for four things: your town or city, your local schools, the "
          "state&rsquo;s education tax, and your county, and a village district&rsquo;s where "
          "there is one. Each is voted by its own body: town meeting or the city council, the "
          "school district meeting, the "
          '<a href="/learn/county-government.html">county convention</a>. The state&rsquo;s '
          "Department of Revenue Administration checks each budget and estimate of revenue, "
          "then computes and sets the tax rate for each town and city.</p>"
          "<p>The state education tax rate is set by the Department each year to raise a sum the "
          "law fixes statewide.</p>",
          law=["RSA 76:5", "RSA 21-J:35", "RSA 76:3"]),
     step("Read your bill",
          "<p>The law says what every property tax bill must show:</p><ul>"
          "<li><b>The rates</b> for the municipal, local education, state education and county "
          "taxes, each separately.</li>"
          "<li><b>Your assessed valuation</b>: the value of the land and buildings you are taxed "
          "on.</li>"
          "<li><b>Your right to ask for an abatement</b>, in writing, from your selectmen or "
          "assessors.</li>"
          "<li><b>A statement on tax relief</b>, on the bill or with it, at least as much as "
          "this: &ldquo;If you are elderly, disabled, blind, a veteran, or veteran&rsquo;s "
          "spouse, or are unable to pay taxes due to poverty or other good cause, you may be "
          "eligible for a tax exemption, credit, abatement, or deferral.&rdquo;</li>"
          "<li><b>The date interest starts</b>, which the tax collector sets by the day the last "
          "bill went out.</li></ul>",
          law=["RSA 76:11-a", "RSA 76:11", "RSA 76:13"]),
     step("When it is due",
          "<p>A town that has voted to bill twice a year sends a first bill, worked out from last "
          "year&rsquo;s assessment and half of last year&rsquo;s rate, due July 1, and a second "
          "bill for the rest of the year&rsquo;s tax, once the new rate is set, due December 1. "
          "Ask your tax collector which your town does.</p>"
          "<p>Tax not paid by its due date is charged interest at 8 percent a year. Where the "
          "bills go out late, interest does not start until 30 days after they were mailed. The "
          "bill says the date.</p>",
          law=["RSA 76:15-a", "RSA 76:13"]),
     step("Apply for an exemption or credit by April 15, or a deferral by March 1",
          "<p>New Hampshire law lets each town and city offer relief to some owners, and the "
          "town&rsquo;s voters or council decide which it offers and, within the law&rsquo;s "
          "limits, how much. Ask your assessing office or the selectmen what yours offers. You "
          "apply once, on the state&rsquo;s form, to your selectmen or assessors, <b>by April "
          "15</b>, and the application stands from year to year while you live in the same home, "
          "though your town may ask you to update your information as often as once a year.</p>"
          + table("Property tax relief a town may offer (RSA 72)",
                  ["Relief", "Who it is for", "How much"],
                  [["Elderly exemption",
                    "Owners 65 or older who have lived in New Hampshire for at least 3 "
                    "consecutive years, under the town&rsquo;s limits on income and assets",
                    "Set by the town by age group, never less than $5,000 off the assessed "
                    "value. The income limit is never under $13,400 single or $20,400 married, "
                    "and the asset limit, not counting your home, never under $35,000."],
                   ["Exemption for the blind",
                    "Owners who are legally blind",
                    "$15,000 off the assessed value of your home, or more if the town votes it"],
                   ["Exemption for the disabled",
                    "Owners eligible for Social Security disability benefits (SSDI or SSI) "
                    "who have lived in New Hampshire at least 5 years and live in the home, "
                    "under the town&rsquo;s limits on income and assets, where the town has "
                    "adopted it",
                    "Set by the town"],
                   ["Veterans&rsquo; tax credit",
                    "A veteran who served at least 90 days in a qualifying war or conflict and "
                    "was honorably discharged, or the veteran&rsquo;s spouse or surviving spouse",
                    "$50 off the tax, or the town&rsquo;s optional credit of $51 up to $750 "
                    "($1,000 from April 1, 2027)"]])
          + "<p>Other credits exist, among them for a veteran with a total and permanent "
          "service-connected disability, and for the surviving spouse of a service member who "
          "died on active duty; the assessing office has the list.</p>"
          "<p>A <b>tax deferral</b> lets an owner who is 65 or older, or eligible for Social "
          "Security disability benefits, put off all or part of the tax, with interest at 5 "
          "percent a year, if paying it would cause undue hardship. You must live in the home "
          "and have owned it for at least 5 consecutive years if you apply by age, or one year "
          "if you apply by disability. Apply by March 1 after the final tax bill. A mortgage "
          "lender must agree.</p>",
          actions=[("Find your town or city clerk", SOS_CLERKS)],
          law=["RSA 72:33", "RSA 72:27-a", "RSA 72:39-a", "RSA 72:39-b", "RSA 72:37",
               "RSA 72:37-b", "RSA 72:28", "RSA 72:35", "RSA 72:29-a", "RSA 72:38-a"]),
     step("If your assessment is wrong, or you cannot pay",
          "<p>If you think your assessment is higher than your property is worth, or you cannot "
          "pay because of poverty, ask your town for an <b>abatement</b> by March 1 after the "
          "final bill: the guide to appealing your assessment has every step and deadline. If "
          "your household income is low or moderate, the state refunds part of the education "
          "tax: apply between May 1 and June 30.</p>",
          actions=[("How to appeal your assessment", "/guides/property-tax-abatement.html"),
                   ("Property tax relief on a low or moderate income",
                    "/guides/property-tax-relief.html")],
          law=["RSA 76:16"])],
    [("Exemptions and credits, RSA 72", "/laws/72"),
     ("Inventory and appraisal, RSA 75", "/laws/75"),
     ("Apportionment, Assessment and Abatement of Taxes, RSA 76", "/laws/76"),
     ("Department of Revenue Administration, RSA 21-J", "/laws/21-j"),
     ("Town and city clerks (Secretary of State)", SOS_CLERKS)],
    ["72", "75", "76"],
    [claim("Property is appraised at its market value, its full and true value as it would be "
           "appraised in payment of a just debt due from a solvent debtor.", "RSA 75:1",
           TAX_BILL_READ),
     claim("Annually, assessments are adjusted to reflect changes and correct errors so that "
           "all are reasonably proportional; considered for material physical change, change "
           "in ownership, zoning changes, subdivision and other changes affecting value.",
           "RSA 75:8", TAX_BILL_READ),
     claim("All real estate is reappraised at full and true value at least as often as every "
           "fifth year.", "RSA 75:8-a", TAX_BILL_READ),
     claim("The property tax year is April 1 to March 31, assessed on the inventory taken in "
           "April.", "RSA 76:2", TAX_BILL_READ),
     claim("The selectmen assess state and county taxes, town taxes, and school and village "
           "district taxes.", "RSA 76:5", TAX_BILL_READ),
     claim("The commissioner of revenue administration computes and establishes the tax rate "
           "of each town, city, or unincorporated place, examining appropriations and revenue "
           "estimates.", "RSA 21-J:35", TAX_BILL_READ),
     claim("The commissioner sets the education tax rate each fiscal year to generate a fixed "
           "revenue statewide.", "RSA 76:3", TAX_BILL_READ),
     claim("The tax bill shows the rate for municipal, local education, state education, and "
           "county taxes separately, the assessed valuation of all lands and buildings, and the "
           "right to apply in writing to the selectmen or assessors for an abatement; it also "
           "contains the tax relief statement, on the bill or on a separate sheet enclosed.",
           "RSA 76:11-a", TAX_BILL_READ),
     claim("Upon written request of a mortgagee, the collector mails a duplicate copy of the "
           "property tax bill.", "RSA 76:11", TAX_BILL_READ),
     claim("Interest at 8 percent per annum on taxes not paid on or before December 1, or 30 "
           "days after the bills are mailed where a bill is sent on or after November 2 and "
           "before April 1; the collector states on the bill the date from which interest will "
           "be charged.", "RSA 76:13", TAX_BILL_READ),
     claim("In a town that adopts semi-annual collection, a partial payment of 1/2 of the "
           "previous year's rate times the prior year's valuation is due July 1, and the "
           "remainder December 1.", "RSA 76:15-a", TAX_BILL_READ),
     claim("Exemptions and credits require a permanent application, filed with the selectmen "
           "or assessors by April 15, on the commissioner's form; it is sufficient on an annual "
           "basis so long as the applicant does not change residence; assessing officials may "
           "require the information periodically but no more frequently than annually.",
           "RSA 72:33", TAX_BILL_READ),
     claim("A town or city adopts, modifies or rescinds an exemption or credit by vote of town "
           "meeting or its legislative body.", "RSA 72:27-a", TAX_BILL_READ),
     claim("An elderly exemption requires residence in the state for at least 3 consecutive "
           "years and net income under the town's limits, never less than $13,400 single or "
           "$20,400 married.", "RSA 72:39-a", TAX_BILL_READ),
     claim("Elderly exemption amounts set by the town for ages 65 to 75, 75 to 80, and 80 or "
           "older; net income limits not less than $13,400 or $20,400; net assets not less than "
           "$35,000 excluding the residence; no exemption less than $5,000.", "RSA 72:39-b",
           TAX_BILL_READ),
     claim("A legally blind inhabitant is exempt on residential real estate to the value of "
           "$15,000, and a town may exempt more.", "RSA 72:37", TAX_BILL_READ),
     claim("Where adopted, a person eligible under Title II or Title XVI of the Social Security "
           "Act for benefits to the disabled receives a yearly exemption in an amount chosen by "
           "the town.", "RSA 72:37-b", TAX_BILL_READ),
     claim("The standard veterans' tax credit is $50; the optional credit, where adopted, $51 "
           "up to $750, and $51 up to $1,000 from April 1, 2027 (HB 1494, chapter 96 of the "
           "Laws of 2026); a veteran with not less than 90 days of active service in a "
           "qualifying war or armed conflict, honorably discharged, or the spouse or surviving "
           "spouse.", "RSA 72:28", TAX_BILL_READ),
     claim("A tax credit for a person discharged with total and permanent service-connected "
           "disability, or the surviving spouse.", "RSA 72:35", TAX_BILL_READ),
     claim("A tax credit for the surviving spouse of a person killed or who died while on "
           "active duty.", "RSA 72:29-a", TAX_BILL_READ),
     claim("A resident owner at least 65, or eligible for Social Security disability benefits, "
           "who has owned the homestead 5 consecutive years (elderly) or one year (disabled) and "
           "lives in it, may be granted a deferral with annual interest at 5 percent, up to 85 "
           "percent of equity value; apply by March 1 following notice of tax; the mortgage "
           "holder's approval; payable within 9 months of the owner's death or on sale.",
           "RSA 72:38-a", TAX_BILL_READ),
     claim("Abatement on application by March 1 after notice of tax.", "RSA 76:16",
           TAX_BILL_READ),
     claim("The town and city clerks lookup lists each town's clerk.", SOS_CLERKS, CHECKED),
     ours("County Government explains that the county convention of the county's state "
          "representatives sets its budget.", "/learn/county-government.html", TAX_BILL_READ),
     ours("How to Appeal Your Property Tax Assessment explains abatement, its deadlines and the "
          "equalization ratio.", "/guides/property-tax-abatement.html", TAX_BILL_READ),
     ours("How to Get Property Tax Relief on a Low or Moderate Income explains the state's "
          "relief and its May 1 to June 30 filing period.", "/guides/property-tax-relief.html",
          TAX_BILL_READ)],
    more=civics.faq(
        ("What is the equalization ratio?",
         "<p>Between revaluations, assessments can drift from what properties sell for, and a "
         "town&rsquo;s <em>equalization ratio</em> measures how far; the guide to appealing your "
         "assessment explains how to use it.</p>"),
        ("Why did my tax change when my assessment did not?",
         "<p>Your tax can change even when your assessment does not: when a budget rises or "
         "falls, or other revenue changes.</p>"),
        ("Can my mortgage lender get a copy of my bill?",
         "<p>If you have a mortgage, your lender can ask the town for a copy of your bill.</p>"),
        ("What happens to deferred tax when the home is sold or the owner dies?",
         "<p>When the home is sold, the deferred tax and its interest must be paid in full. When "
         "the owner dies, the heirs may pay it off within 9 months; after that the town may send "
         "it to the tax collector.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Your town or city&rsquo;s <b>assessing office</b>, or the selectmen&rsquo;s office "
         "in a small town, answers questions about your assessment and the relief your town "
         "offers, and has the application forms. The <b>tax collector</b> answers questions "
         "about a bill, a payment or interest; the town clerk&rsquo;s office can tell you who "
         "yours is.</p>"
         f'<p class="g-acts"><a class="g-btn" href="{SOS_CLERKS}" target="_blank" rel="noopener">'
         "Find your town or city clerk</a></p>",
    see=[("How to appeal your property tax assessment", "/guides/property-tax-abatement.html"),
         ("Help paying property tax on a low or moderate income", "/guides/property-tax-relief.html"),
         ("Town meeting and local government", "/learn/local-government.html")],
    figures=[fig("8 percent", "RSA 76:13", "Interest at 8 percent per annum"),
             fig("30 days", "RSA 76:13", "30 days after the bills are mailed"),
             fig("$5,000", "RSA 72:39-b", "be less than $5,000"),
             fig("$13,400", "RSA 72:39-b", "not less than $13,400"),
             fig("$20,400", "RSA 72:39-b", "not less than $20,400"),
             fig("$35,000", "RSA 72:39-b", "not less than $35,000 excluding the value of the "
                                          "person's residence"),
             fig("$15,000", "RSA 72:37", "to the value of $15,000"),
             fig("90 days", "RSA 72:28", "not less than 90 days on active service"),
             fig("$50", "RSA 72:28", "credit shall be $50"),
             fig("$51", "RSA 72:28", "an amount from $51 up to $750"),
             fig("$750", "RSA 72:28", "an amount from $51 up to $750"),
             fig("$1,000", "RSA 72:28", "an amount from $51 up to $1,000"),
             fig("5 percent", "RSA 72:38-a", "annual interest at 5 percent"),
             fig("9 months", "RSA 72:38-a", "within 9 months of the date of death"),
             fig("5 years", "RSA 72:37-b", "resident for at least 5 years")])

GUIDES += [TAX_BILL]


# ---------------------------------------------------------------------------
# HELP PAYING FOR CHILD CARE (the person, 24 October 2026, who named the child
# care scholarship among the guides to add and allowed federal sources that
# day). From the Department of Health and Human Services' Child Development
# and Head Start page, whose Information for Families section is the program's
# page for families, its Provider Enrollment page and its Family Assistance
# Manual's section 901, each read on 24 October 2026 in the PDFs the person
# printed and sent, since nh.gov refuses a cloud session; and from the federal
# rules the program runs on, 45 CFR 98, read at eCFR the same day. The federal
# rules add what the Department's pages do not say: what holds between one
# year's eligibility and the next, and the parent's choice of provider. No
# income limit, copayment or scholarship amount is printed: they are the
# Department's and change (the plan: no eligibility math), and the guide
# links where the Department states them.
# ---------------------------------------------------------------------------
CC_READ = "2026-10-24"
DHHS_CHILD_DEV = ("https://www.dhhs.nh.gov/programs-services/childcare-parenting-childbirth/"
                  "child-development-and-head-start")
DHHS_CC_PROVIDERS = DHHS_CHILD_DEV + "/child-care"
DHHS_FAM_901 = "https://www.dhhs.nh.gov/fam_htm/html/901_application_process_fam.htm"
_ECFR = "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-A/part-98/"
CFR_REDETERMINE = _ECFR + "subpart-C/section-98.21"
CFR_CHOICE = _ECFR + "subpart-D/section-98.30"

CHILD_CARE = guide(
    "child-care-scholarship", "How to Get Help Paying for Child Care",
    "Applying for New Hampshire's Child Care Scholarship through the Department of Health and "
    "Human Services, step by step: who it is for, how to apply, choosing a provider, and keeping "
    "it.",
    "New Hampshire&rsquo;s Child Care Scholarship helps eligible families pay for child care, "
    "with payments made directly to the child care provider. It is for children under 13, or "
    "under 18 with a disability, whose parents are working, looking for work or in a training "
    "program. Apply to the Department of Health and Human Services online at NH Easy, or in "
    "person or by mail on paper. The Department decides within 30 days, and you apply again "
    "every year.",
    [box("Check that it fits your family: a child under 13 (under 18 with a disability), and "
         "parents working, looking for work, or in a training program."),
     ask("How do you want to apply?",
         [("Online", "Apply at NH Easy."),
          ("On paper", "Apply in person or by mail at your District Office.")]),
     box("The Department decides within 30 days. Choose a provider enrolled with it."),
     box("Apply again every 12 months.")],
    [step("Check whether it fits your family",
          "<p>The scholarship pays part of the cost of child care, directly to the provider, for "
          "eligible families. To be eligible:</p>"
          "<ul><li>your child is under 13 years old, or under 18 years old with a "
          "disability;</li>"
          "<li>the parents are working, looking for work, or in a training program; and</li>"
          "<li>your household&rsquo;s income is within the Department&rsquo;s current limits, "
          "which it publishes each year, effective July 1.</li></ul>",
          actions=[("The scholarship, for families", DHHS_CHILD_DEV)]),
     step("Apply online or on paper",
          "<p><b>Online:</b> apply at NH Easy, the Department&rsquo;s site for all its services, "
          "child care among them.</p>"
          "<p><b>On paper:</b> apply in person or by mail at a District Office, which can give "
          "you the application.</p>"
          "<p>To schedule a follow-up appointment, call 1-844-ASK-DHHS (1-844-275-3447). "
          "Everyone has the right to apply, and to a decision within 30 days.</p>",
          actions=[("NH Easy", NHEASY), ("Find your District Office", DHHS_OFFICES)]),
     step("Choose a child care provider",
          "<p>You choose who cares for your child.</p>"
          "<p>The scholarship is paid to the provider, so the provider must be enrolled with the "
          "Department to accept it. Ask a provider you are considering whether it is. The "
          "Department&rsquo;s free Child Care Search, linked from the same page as the "
          "scholarship, shows providers&rsquo; quality ratings, "
          "licensing history and services, and Child Care Aware of New Hampshire helps families "
          "find care for free: call 1-855-393-1731, extension 2531, weekdays 8:00&nbsp;AM to 5:00&nbsp;PM.</p>",
          actions=[("Providers and the scholarship", DHHS_CC_PROVIDERS)]),
     step("Keeping the scholarship",
          "<p>Your eligibility is checked again every 12 months, and you reapply each year.</p>"),
     step("If you disagree with a decision",
          "<p>You can ask for an administrative appeal "
          "hearing, in writing, on the Department&rsquo;s appeal request form or in a letter. "
          "Generally you have 30 days from the date on your Notice of Decision. You do not need "
          "a lawyer.</p>",
          actions=[("Administrative appeals", DHHS_APPEALS)])],
    [("Child Development and Head Start (Department of Health and Human Services)", DHHS_CHILD_DEV),
     ("Child Care Scholarship Provider Enrollment and Web Billing (Department of Health and "
      "Human Services)", DHHS_CC_PROVIDERS),
     ("Accessing the NH Child Care Scholarship, Family Assistance Manual 901 (Department of "
      "Health and Human Services)", DHHS_FAM_901),
     ("Administrative Appeals (Department of Health and Human Services)", DHHS_APPEALS),
     ("Eligibility determination, 45 CFR 98.21 (federal)", CFR_REDETERMINE),
     ("Parental choice, 45 CFR 98.30 (federal)", CFR_CHOICE)],
    [],
    [claim("Information for Families: the NH CCSP provides funds for eligible families by direct "
           "payments to qualified providers; children may be under 13 years old (or under 18 "
           "years old if they have a disability); parents working, looking for work, or in a "
           "training program, with household income meeting current requirements; eligibility "
           "redetermined every 12 months and families reapply annually; Income Eligibility "
           "Levels effective July 1; apply online at NH EASY, the one-stop-shop for all DHHS "
           "services including child care; 1-844-ASK-DHHS (1-844-275-3447) to schedule a follow "
           "up appointment; in-person or by mail with a paper application at District Offices; "
           "Child Care Search, a free service, shows providers' quality rating, licensing history "
           "and services; Child Care Aware of NH, 1-855-393-1731, ext. 2531, Monday to Friday "
           "8:00 AM to 5:00 PM.", DHHS_CHILD_DEV, CC_READ),
     claim("The program pays qualified providers directly; providers enroll to accept the "
           "scholarship, whether licensed, license-exempt or licensed out of state.",
           DHHS_CC_PROVIDERS, CC_READ),
     claim("Any individual has the right to apply and to an eligibility decision within 30 "
           "days; an application from any District Office, the DHHS website or by telephone, or "
           "through NH EASY; an applicant experiencing homelessness is authorized for expedited "
           "child care within 7 days of the date of application when the child is linked to a "
           "DHHS enrolled provider, with a final decision within 30 days.", DHHS_FAM_901, CC_READ),
     # Federal law, read at eCFR on 24 October 2026.
     claim("Eligibility is redetermined no sooner than 12 months after the last determination; "
           "meanwhile the child receives services at least at the same level despite income "
           "below 85 percent of the state median or a temporary change: an absence to care for "
           "a family member or illness, a seasonal worker between seasons, a student break, "
           "reduced hours, turning 13, a move within the state; on loss of work or of a program, "
           "assistance continues at least three months; co-payments are not increased within "
           "the 12-month period except as paragraph (b)(3) allows.", CFR_REDETERMINE, CC_READ),
     claim("Parents choose a provider; certificates allow center-based, family and in-home "
           "care, with any limits on in-home care in the Plan; information on the range of "
           "options includes sectarian providers and relatives.", CFR_CHOICE, CC_READ),
     # Read before, for the food and health guide.
     claim("Appeal in writing by form or letter, to the District Office, by mail to the AAU, or by "
           "email, or by telling a DHHS representative; generally 30 days from the Notice of "
           "Decision, 90 for SNAP; within 15 days benefits may continue, repaid if upheld; no "
           "attorney needed and none appointed.", DHHS_APPEALS, READ)]
    + help_claims("nheasy", "legal_aid"),
    more=civics.faq(
        ("Can a relative or a religious provider care for my child?",
         "<p>Federal rules let you choose among child care centers, family child care homes and, "
         "within the state&rsquo;s limits, care in your own home. Relatives and religious "
         "providers are among the choices.</p>"),
        ("What if my income goes up, or my situation changes for a while?",
         "<p>Between those yearly checks, federal rules keep the scholarship going at least "
         "at the same level "
         "even if your income goes up, as long as it stays under the federal limit, and "
         "through temporary changes such as time off work for an illness or to care for a "
         "family member, a break between seasonal jobs, a school break, fewer hours, or your "
         "child turning 13. Your share of the cost cannot be raised in that time except as the "
         "rules allow.</p>"),
        ("What if I lose my job or leave my program?",
         "<p>If you lose your job or leave your program, it continues for at least three months "
         "so you can look for work or go back.</p>"),
        ("My family is homeless. Can we get child care sooner?",
         "<p><b>Families experiencing homelessness</b> can be approved for child care within 7 "
         "days of applying, once the child is linked to a provider enrolled with the "
         "Department. The final decision still comes within 30 days. Say so when you "
         "apply.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>For questions about the scholarship and your application, call the Department at "
         "1-844-ASK-DHHS (1-844-275-3447), or ask your local District Office in person. For help "
         "finding child care, call Child Care Aware of New Hampshire at 1-855-393-1731, "
         "extension 2531.</p>"
         + helps("nheasy", "legal_aid"),
    see=[("How to apply for food or health assistance", "/guides/food-and-health-assistance.html"),
         ("How to file for unemployment", "/guides/file-for-unemployment.html")],
    figures=[fig("13 years", DHHS_CHILD_DEV, "under 13 years old"),
             fig("18 years", DHHS_CHILD_DEV, "under 18 years old"),
             fig("30 days", DHHS_FAM_901, "an eligibility decision within 30 days"),
             fig("7 days", DHHS_FAM_901, "within 7 days of the date of application"),
             fig("12 months", DHHS_CHILD_DEV, "redetermined every 12 months")])

GUIDES += [CHILD_CARE]


# ---------------------------------------------------------------------------
# WHEN YOU NEED A BUILDING PERMIT OR AN INSPECTION (the person, 25 October
# 2026: "what modifications you need permits for or an inspector for things
# like house additions or electrical or plumbing work"). The state sets the
# code and the trades' licenses; the town decides how permits are issued and
# inspects. So the guide says what state law requires, and sends the reader
# to the town's building office first, for its own permits. Read on 25
# October 2026, as the Laws pages print them: RSA 155-A (the state building
# code; RSA 674:51 and 676:11 and :13, which once held the town's part, were
# repealed on 1 July 2026 and the code's own chapter holds it now; 155-A:7 has
# a change taking effect 1 July 2027, and the guide says only what both texts
# say), RSA 319-C (electricians), RSA 153 (plumbers and gas fitters, since
# RSA 329-A's repeal in 2013), RSA 485-A (septic systems), RSA 483-B
# (shoreland) and RSA 482-A (wetlands). The Fire Marshal's, the licensing
# boards' and the Department of Environmental Services' pages refuse a cloud
# session and wait for the person's printouts; DES's septic page is not
# linked until its address is seen.
# ---------------------------------------------------------------------------
BP_READ = "2026-10-25"
BP_PAGES_READ = "2026-10-26"         # the person's printouts
# The State Building Code page: the printout shows no address; its title is the
# page a search finds at this one (26 October 2026).
FM_CODES = "https://www.firemarshal.dos.nh.gov/laws-rules-regulatory/state-building-code"
OPLC_ELECTRICIANS = "https://www.oplc.nh.gov/electricians-board"
DES_SHORELAND = "https://www.des.nh.gov/land/waterfront-development/protected-shoreland"
DES_WETLANDS = "https://des.nh.gov/water/wetlands/permit-assistance"

BUILDING_PERMITS = guide(
    "building-permits", "When You Need a Building Permit or an Inspection",
    "What New Hampshire's building code covers, getting a permit and inspections from your "
    "town, who may do electrical, plumbing and gas work, septic approval, and permits for work "
    "near water.",
    "Every building project in New Hampshire, from a new house or an addition to a renovation "
    "or a repair, must meet the state building code. Your town decides how permits are issued "
    "and who inspects, so ask its building office before you start. Electrical and plumbing "
    "work needs a licensed electrician or plumber, though you may do your own in a "
    "single-family home you own and live in. A new septic system, or work that adds to the "
    "load on one, needs the state&rsquo;s approval first, and so does most building, digging "
    "or filling near a lake, pond, river, the coast or a wetland.",
    [box("Before you start, ask your town&rsquo;s building office what permits the work "
         "needs."),
     ask("What is the work?",
         [("Building, adding on, remodeling or repairing",
           "It must meet the state building code. Your town issues the permit and inspects."),
          ("Electrical, plumbing or gas",
           "A licensed trade, or you, in a single-family home you own and live in (for gas, "
           "only an existing, stand-alone house that is your main home)."),
          ("A septic system, or adding to the load on one",
           "The state approves the septic plans first."),
          ("Near a lake, pond, river, the coast or a wetland",
           "A state shoreland or wetlands permit may be needed too.")]),
     box("Get the permits before work starts, and have the work inspected when the town "
         "asks.")],
    [step("Start with your town’s building office",
          "<p>The <b>state building code</b> applies to every building and structure in New "
          "Hampshire: building one, and altering, renovating, repairing or tearing one down. "
          "It is a set of national codes the state adopts, among them the building, "
          "residential, plumbing, mechanical, energy and electrical codes.</p>"
          "<p>Before work starts, the person responsible for it must get a permit. How that "
          "works is the town&rsquo;s to set: a town or city that enforces the code has a "
          "building official, often called the building inspector or code enforcement "
          "officer, who reviews plans, issues permits and inspects the work. Ask at your town "
          "or city office before you begin. A permit will not be issued for work that breaks "
          "the town&rsquo;s zoning or planning board rules, so the same office can tell you "
          "whether the project needs those boards&rsquo; approval too.</p>",
          actions=[("The State Building Code (Division of Fire Safety)", FM_CODES)],
          law=["RSA 155-A:1", "RSA 155-A:2", "RSA 155-A:3", "RSA 155-A:4", "RSA 155-A:7"]),
     step("Inspections, and if you disagree",
          "<p>The building official may inspect the work, the site and the building, so plan "
          "for the inspections your town asks for.</p>"
          "<p>When a town issues a building permit or a notice of violation, it must tell you "
          "how to appeal, locally and to the state. A town that enforces the code has a "
          "building code board of appeals, and there is no fee to appeal a notice of "
          "violation or another decision of a code official.</p>",
          law=["RSA 155-A:3", "RSA 155-A:7"]),
     step("Electrical work",
          "<p>Electrical work done for pay must be done by an electrician licensed by the "
          "state. A homeowner may do electrical work in or about a <b>single-family home</b> "
          "they own and live in, or are building to live in. Your town may still require a "
          "permit and an inspection for it.</p>"
          "<p>Otherwise, the state&rsquo;s Electricians&rsquo; Board says, work at 30 volts or "
          "more needs an active New Hampshire electrician&rsquo;s license. To ask about an "
          "inspection or report a safety concern, call the Department of Safety at (603) "
          "271-2791.</p>",
          actions=[("Electricians' Board (Office of Professional Licensure and "
                    "Certification)", OPLC_ELECTRICIANS)],
          law=["RSA 319-C:1", "RSA 319-C:15"]),
     step("Plumbing and gas work",
          "<p>Plumbers and gas fitters are licensed by the state&rsquo;s Mechanical Licensing "
          "Board, part of the Office of Professional Licensure and Certification. A property owner may install, repair or replace the plumbing in "
          "their own <b>single-family house or townhouse</b>, including in new construction; "
          "the work must still meet the state plumbing code.</p>"
          "<p>Gas fitting is narrower: you may do it yourself only in an existing, stand-alone "
          "single-family house that you own and live in as your main home, and the work must "
          "meet the codes and pass any inspection that applies. Your town&rsquo;s building "
          "office may enforce the plumbing and gas rules.</p>",
          law=["RSA 153:27-a", "RSA 153:36", "RSA 153:35"]),
     step("Septic systems",
          "<p>No one may build a house or other building that will send wastewater to a septic "
          "system, or build a septic system, until the Department of Environmental Services "
          "has approved its plans. The same goes before adding on to a building, or changing "
          "its use, in a way that would add to the load on its septic system. Your town may have its own rules on top of the state&rsquo;s.</p>"
          "<p>You may replace or repair the septic system of your own home yourself, following "
          "the Department&rsquo;s rules.</p>",
          law=["RSA 485-A:32", "RSA 485-A:35", "RSA 485-A:36", "RSA 485-A:38"]),
     step("Work near water",
          "<p>Land within 250 feet of a lake or pond of more than 10 acres, a larger river (one "
          "of fourth order or higher, or one the state has designated as protected) or tidal "
          "water is <b>protected shoreland</b>. Building, digging or filling there needs a shoreland permit from the "
          "Department of Environmental Services. Small projects that meet its standards can "
          "go ahead on a simpler <b>permit by notification</b>, as soon as the Department "
          "confirms it has your complete notice.</p>"
          "<p>Digging, filling, dredging or building in or on a bank, marsh or swamp next to a "
          "lake, river or other water needs a <b>wetlands permit</b> from the Department, "
          "applied for through your town or city clerk, who signs the application.</p>"
          "<p>The Department has an online tool that tells you whether a project needs a "
          "shoreland permit. For questions, call (603) 271-2147 and ask for the Inspector of the "
          "Day, or email shoreland@des.nh.gov; for wetlands, lrm@des.nh.gov, with photos, plans "
          "and the location.</p>",
          actions=[("Protected shoreland (Department of Environmental Services)", DES_SHORELAND),
                   ("Wetlands permit help (Department of Environmental Services)", DES_WETLANDS)],
          law=["RSA 483-B:4", "RSA 483-B:5-b", "RSA 482-A:3"])],
    [("State Building Code (Division of Fire Safety)", FM_CODES),
     ("Electricians' Board (Office of Professional Licensure and Certification)",
      OPLC_ELECTRICIANS),
     ("Protected Shoreland (Department of Environmental Services)", DES_SHORELAND),
     ("Wetlands Permit Assistance (Department of Environmental Services)", DES_WETLANDS),
     ("New Hampshire Building Code, RSA 155-A", "/laws/155-a"),
     ("Electricians, RSA 319-C", "/laws/319-c"),
     ("State Board of Fire Control, RSA 153", "/laws/153"),
     ("Water Pollution and Waste Disposal, RSA 485-A", "/laws/485-a"),
     ("Shoreland Water Quality Protection Act, RSA 483-B", "/laws/483-b"),
     ("Fill and Dredge in Wetlands, RSA 482-A", "/laws/482-a")],
    ["155-A", "319-C", "153", "485-A", "483-B", "482-A"],
    [# The statutes, as the Laws pages print them, read on 25 October 2026.
     claim("The state building code is the adoption by reference of the International Building "
           "Code 2024, the International Existing Building Code 2024, the International Plumbing "
           "Code 2024, the International Mechanical Code 2024, the International Energy "
           "Conservation Code 2018, the International Swimming Pool and Spa Code 2024 and the "
           "International Residential Code 2024, and the National Electrical Code 2023.",
           "RSA 155-A:1", "2026-10-26"),
     claim("All buildings, building components, and structures constructed in New Hampshire "
           "shall comply with the state building code and state fire code; it governs the "
           "construction and the alteration, renovation, rehabilitation, repair, removal, or "
           "demolition of buildings; where a municipality has not adopted an enforcement "
           "mechanism, the contractor shall notify the state fire marshal before construction "
           "begins excluding one- and 2-family dwellings.", "RSA 155-A:2", BP_READ),
     claim("The local legislative body may establish a local enforcement agency; a building "
           "code board of appeals; a building official with authority to review construction "
           "documents, issue building permits and perform inspections.", "RSA 155-A:3",
           BP_READ),
     claim("Before starting work, the person responsible for such construction shall obtain a "
           "permit, conforming to the locally adopted process; the building official shall "
           "not issue any permit for construction which will not comply with zoning "
           "ordinances, building codes, or planning board regulations.", "RSA 155-A:4",
           BP_READ),
     claim("The local enforcement agency enforces the state building code; where there is no "
           "local enforcement agency, the state fire marshal may enforce it upon written "
           "request of the municipality; the agency may inspect all buildings, structures and "
           "construction sites; information on the local and state appeals process is given "
           "when issuing a building permit or notice of violation; no fee shall be required "
           "to appeal a notice of violation or other decision of a code official.",
           "RSA 155-A:7", BP_READ),
     claim("No electrician installation shall be made for compensation, unless made by an "
           "electrician licensed by the office of professional licensure and certification.",
           "RSA 319-C:1", BP_READ),
     claim("Nothing in this chapter shall prevent a homeowner from making electrical "
           "installations in or about a single family residence owned and occupied by him or "
           "her or to be occupied by him or her as his or her bona fide personal abode.",
           "RSA 319-C:15", BP_READ),
     claim("The license requirements do not apply to fuel gas fitting within an existing single "
           "family, stand alone structure owned and occupied by the person as a primary "
           "residence, who shall comply with applicable code and inspection requirements; nor "
           "to a property owner who installs, repairs, or replaces plumbing in the property "
           "owner's own single-family detached or townhouse residence, including new "
           "construction, which shall conform to the state plumbing code.", "RSA 153:36",
           BP_READ),
     claim("The mechanical licensing board is established as a unit within the office of "
           "professional licensure and certification.", "RSA 153:27-a", "2026-10-26"),
     claim("The mechanical licensing board's rules may be enforced by the building inspection "
           "department or by any officer designated by the city or town.", "RSA 153:35",
           BP_READ),
     claim("No person shall construct any building from which sewage or other wastes will "
           "discharge or construct a sewage or waste disposal system without prior approval of "
           "the plans and specifications by the department; local requirements are not "
           "lessened.", "RSA 485-A:32", BP_READ),
     claim("Applications for subsurface sewage or waste disposal systems shall be prepared and "
           "signed by the individual who is directly responsible for them and who has a permit "
           "issued by the department.", "RSA 485-A:35", BP_READ),
     claim("No individual shall engage in the business of installing subsurface systems "
           "without an installer's permit; a person installing a replacement system or "
           "repairing a system for their own domicile is not required to obtain one, provided "
           "they comply with the department's rules.", "RSA 485-A:36", BP_READ),
     claim("Prior to expanding any structure or any change in use which would increase the "
           "load on a sewage disposal system, the owner shall apply to the department for "
           "approval of the system.", "RSA 485-A:38", BP_READ),
     claim("Protected shoreland means all land located within 250 feet of the reference line of "
           "public waters; public waters include all lakes, ponds, and artificial impoundments "
           "greater than 10 acres in size; coastal waters subject to the ebb and flow of the "
           "tide; and rivers, all year-round flowing waters of fourth order or higher and all "
           "rivers and river segments designated as protected under RSA 483:15.", "RSA 483-B:4",
           "2026-10-26"),
     claim("No person shall commence construction, excavation, or filling activities within "
           "the protected shoreland without a permit from the department; projects with no "
           "impact on water quality qualify for a permit by notification, and the owner may "
           "proceed upon written notice that a complete notification has been received.",
           "RSA 483-B:5-b", BP_READ),
     claim("No person shall excavate, remove, fill, dredge, or construct any structures in or "
           "on any bank, flat, marsh, or swamp in and adjacent to any waters of the state "
           "without a permit from the department; the application form is signed by the town "
           "or city clerk.", "RSA 482-A:3", BP_READ),
     # The agencies' own pages, from the person's printouts.
     claim("The State Building Code applies in every municipality statewide; a municipality "
           "that chooses to enforce it adopts an ordinance confirmed by the Building Code Review "
           "Board; as of July 1, 2026, local amendments are limited to administrative matters; "
           "effective July 1, 2026 the code is updated (IBC, IRC, IPC, IMC and others, 2024), "
           "with a six-month concurrence period from July 1 - December 31, 2026 during which "
           "permit requests can be submitted under either the 2021 or 2024 codes; Building Code "
           "Review Board (603) 223-4315.", FM_CODES, BP_PAGES_READ),
     claim("An active and valid New Hampshire Electrician license is required to work with 30 "
           "volts or higher; for assistance regarding an inspection or to report a safety "
           "concern please contact the Department of Safety by calling (603) 271-2791.",
           OPLC_ELECTRICIANS, BP_PAGES_READ),
     claim("Within the protected shoreland, vegetation removal, excavation, fill, and "
           "development are regulated; proposed projects typically require a shoreland permit; "
           "an interactive tool to determine if a shoreland permit is required; email "
           "shoreland@des.nh.gov or call (603) 271-2147 and ask to speak with the Inspector of "
           "the Day.", DES_SHORELAND, BP_PAGES_READ),
     claim("Projects that involve excavation, fill, dredge, removal, and/or construction of "
           "structures in or on any bank, flat, marsh, or swamp in or adjacent to wetlands and "
           "waterbodies often require wetlands permits; questions by email to lrm@des.nh.gov or "
           "shoreland@des.nh.gov, with photos, plans and location information.", DES_WETLANDS,
           BP_PAGES_READ)],
    more=civics.faq(
        ("Which edition of the code applies?",
         "<p>A town or city that enforces the code does so by an ordinance the state&rsquo;s "
         "Building Code Review Board confirms; it may add local amendments, limited since July "
         "1, 2026 to administrative matters. On July 1, 2026 the state moved six of its codes "
         "to their 2024 editions: the building, residential, existing building, plumbing, "
         "mechanical, and swimming pool and spa codes. The energy code stays the 2018 edition "
         "and the electrical code the 2023. Through December 31, 2026 a permit may be sought "
         "under either the 2021 or the 2024 codes. The Review Board answers questions at (603) 223-4315.</p>"),
        ("What if my town has no building inspector?",
         "<p>Where a town has no one of its own to enforce the code, the State Fire Marshal "
         "may enforce it at the town&rsquo;s written request. In such a town, a contractor "
         "must tell the Fire Marshal before starting any building other than a one- or "
         "two-family home.</p>"),
        ("Who may design and install a septic system?",
         "<p>The plans must be prepared and signed by a designer who holds a permit from the "
         "Department of Environmental Services, and a system is installed by an installer with "
         "the Department&rsquo;s permit.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Your town or city&rsquo;s building inspector or code enforcement officer is the "
         "first person to ask, about its permits, its fees and its inspections. Where your "
         "town has none, ask the selectboard&rsquo;s office.</p>",
    see=[("Who to contact about an issue", "/guides/who-to-contact.html"),
         ("Cities, towns and who runs them", "/learn/city-and-town-government.html")])

GUIDES += [BUILDING_PERMITS]


# ---------------------------------------------------------------------------
# HELP AFTER DOMESTIC VIOLENCE, SEXUAL ASSAULT OR STALKING (the person, 24
# October 2026: "support services for things like sexual assault victims,
# domestic violence victims, or the homeless"; homelessness is a guide of its
# own, because a reader in crisis needs the one answer for their situation
# first). From the New Hampshire Coalition Against Domestic and Sexual
# Violence -- the statewide body of the crisis centers, whose site answers a
# cloud session -- read on 24 October 2026, and from RSA 173-B, 633:3-a, 7:41-43
# and 21-M:8-c and 8-h as the Laws pages print the statute table. The
# Coalition is not a state agency (guide_sources.OTHER), and the person
# approved it as a source on 24 October 2026. The plan's first line governs this guide above all: a dead number
# here sends someone in crisis nowhere, so every number printed is one the
# Coalition's own page gives, and the claims carry the day it was read.
# ---------------------------------------------------------------------------
DV_READ = "2026-10-24"
NHCADSV = "https://www.nhcadsv.org/"
NHCADSV_CENTERS = "https://www.nhcadsv.org/member-programs.html"
NHCADSV_SAFETY = "https://www.nhcadsv.org/safety-planning1.html"
NHCADSV_EXAMS = "https://www.nhcadsv.org/medicalforensic-exams.html"
NHCADSV_LEGAL = "https://www.nhcadsv.org/legal-resources.html"
NHCADSV_SERVICES = "https://www.nhcadsv.org/support-services--programs.html"
# The court's and the Attorney General's own pages, read in the PDFs the person
# printed and sent on 24 October 2026.
COURTS_PROTECT = "https://www.courts.nh.gov/self-help/restraining-orders"
DOJ_ACP = "https://www.doj.nh.gov/bureaus/office-victimwitness-assistance/address-confidentiality-program"

VIOLENCE = guide(
    "domestic-violence-help", "How to Get Help After Domestic Violence, Sexual Assault or Stalking",
    "Where to call, how to make a safety plan, how to ask a court for a protective order, and "
    "what happens at the hospital after a sexual assault, with New Hampshire's free and "
    "confidential crisis centers.",
    "If you are in danger now, call 911. Otherwise, call New Hampshire&rsquo;s 24-hour "
    "domestic and sexual violence helpline, <a href=\"tel:+18666443574\">1-866-644-3574</a>. It is free and "
    "confidential, it is "
    "open to everyone, and you do not need to be in crisis to call. An advocate from your local "
    "crisis center can help you make a safety plan, find shelter, get medical care and ask a "
    "court for a protective order, which costs nothing to file.",
    [box("In danger now? Call 911."),
     box("Call the 24-hour helpline, 1-866-644-3574. It is free and confidential."),
     ask("What do you need?",
         [("Protection from someone",
           "Ask the circuit court for a protective order. There is no fee, and you need no lawyer."),
          ("Care after a sexual assault",
           "Go to a hospital. The exam is free, and you choose whether to report to the police.")])],
    [step("Reach someone now",
          "<p>In an emergency, call 911.</p>"
          "<p>At any hour, call the statewide helpline, <b><a href=\"tel:+18666443574\">1-866-644-3574</a></b>. An "
          "answering "
          "service usually takes your first name and number, and an advocate from your local "
          "crisis center calls you back, generally in about 5 minutes. The advocates listen, "
          "explain your options and never pressure you. They can help with a safety plan, "
          "shelter, support groups, money, medical care, legal referrals and other services. "
          "The crisis centers serve victims of domestic violence, sexual assault, stalking, "
          "child abuse and human trafficking, and their services are free and confidential and "
          "open to all. If no advocate speaks Spanish, they use an interpreter.</p>",
          actions=[("Find your local crisis center", NHCADSV_CENTERS)]),
     step("Make a safety plan",
          "<p>A safety plan is a practical plan for your own situation: how to avoid danger "
          "and what to do if you are in danger. It helps while you are still with someone who "
          "is abusive, while you prepare to leave, and after you have left. Abusers may monitor "
          "calls and texts or track where you are, so a plan covers your phone and other "
          "technology too. Crisis center advocates help make or review a plan at any hour.</p>",
          actions=[("Safety planning", NHCADSV_SAFETY)]),
     step("Ask the court for a protective order",
          "<p>If a family or household member, or a current or former partner, has abused you, "
          "you can file a <b>domestic violence petition</b> at the circuit court where you or "
          "they live, or where you are staying if you left home to get away. The clerk has the "
          "forms. <b>There is no filing fee</b>, no fee to have the papers served, and you do "
          "not need a lawyer. A minor can ask for an order against a partner or former partner "
          "without a parent.</p>"
          "<ul><li>If you are in immediate danger, the court can make a <b>temporary order</b> "
          "without first telling the other person.</li>"
          "<li>When the court is closed, go to or call the nearest police department; it does "
          "not have to be your own town&rsquo;s. An officer can help you fill out the forms and "
          "reach a judge by phone. An emergency order lasts only until the court&rsquo;s next "
          "business day ends, so go to a circuit court before then to ask for an order that "
          "lasts longer.</li>"
          "<li>The court holds a hearing within 30 days of the petition, or 10 days after the "
          "other person is served, whichever is later.</li></ul>",
          actions=[("Orders of protection (Judicial Branch)", COURTS_PROTECT),
                   ("Legal help, from the Coalition", NHCADSV_LEGAL)],
          law=["RSA 173-B:1", "RSA 173-B:2", "RSA 173-B:3", "RSA 173-B:4", "RSA 173-B:10",
               "RSA 633:3-a"]),
     step("After a sexual assault: medical care",
          "<p>Going to a hospital is about your health and safety: you may have injuries you "
          "cannot see, or have been exposed to an infection or to pregnancy. Emergency "
          "contraception works best within 72 hours.</p>"
          "<ul><li><b>The exam is free.</b> The bill is never sent to you or your family.</li>"
          "<li><b>You choose whether to report</b> to the police, and the exam can be "
          "anonymous. If you are under 18, the hospital staff must report it.</li>"
          "<li><b>You choose what happens.</b> You can say no to any part of the exam, at any "
          "time.</li>"
          "<li>An advocate from the crisis center can be with you, for free.</li></ul>",
          actions=[("What to expect at the hospital", NHCADSV_EXAMS)],
          law=["RSA 21-M:8-c"]),
     step("Other protections and help",
          "<ul><li><b>Keeping a new address private:</b> the Attorney General&rsquo;s Address "
          "Confidentiality Program, and <b>costs of a crime:</b> the Victims&rsquo; Compensation "
          "Program. The questions below say more.</li>"
          "<li><b>Free legal help</b> with housing, family law, benefits and more: 603 Legal "
          "Aid, 1-800-639-5290.</li></ul>",
          actions=[("Address Confidentiality Program (Attorney General)", DOJ_ACP),
                   ("Services and programs, from the Coalition", NHCADSV_SERVICES)],
          law=["RSA 7:43", "RSA 21-M:8-h"])],
    [("New Hampshire Coalition Against Domestic and Sexual Violence", NHCADSV),
     ("Contact your local crisis center (the Coalition)", NHCADSV_CENTERS),
     ("Safety planning (the Coalition)", NHCADSV_SAFETY),
     ("Medical/forensic exams (the Coalition)", NHCADSV_EXAMS),
     ("Legal and other resources (the Coalition)", NHCADSV_LEGAL),
     ("Services and programs (the Coalition)", NHCADSV_SERVICES),
     ("Orders of Protection and Restraining Orders (Judicial Branch)", COURTS_PROTECT),
     ("Address Confidentiality Program (Attorney General)", DOJ_ACP),
     ("Protection of Persons from Domestic Violence, RSA 173-B", "/laws/173-b")],
    ["173-B"],
    [claim("A 24-hour helpline, 1-866-644-3574; the crisis centers serve victims of domestic "
           "violence, sexual assault, stalking, child abuse and human trafficking; free and "
           "confidential, open and affirming to all, no need to be in crisis; in an emergency "
           "call 911; to report child abuse or neglect, DCYF at (800) 894-5533 in state or "
           "(603) 271-6562.", NHCADSV, DV_READ),
     claim("The statewide helpline is answered by a service that takes a first name and number "
           "and has a local advocate call back, generally in about 5 minutes; advocates help "
           "with safety planning, shelter, support groups, financial services, medical care, "
           "legal referrals and social services, listen, share options and never pressure; an "
           "interpreter where no advocate speaks Spanish; the National Domestic Violence "
           "Hotline 1-800-799-SAFE and RAINN 1-800-656-HOPE outside NH.", NHCADSV_CENTERS, DV_READ),
     claim("A safety plan is personalized to avoid dangerous situations, for while with the "
           "abuser, preparing to leave and after; advocates help craft or review one 24/7; "
           "abusers may monitor calls and texts and track location, so technology safety is "
           "part of it.", NHCADSV_SAFETY, DV_READ),
     claim("The exam is about health and safety: unseen injuries, infection, pregnancy; no charge "
           "for the exam; it may be anonymous and the survivor chooses whether to report, except "
           "that under 18 the staff must report; any part may be refused at any time; a crisis "
           "center advocate is available free; emergency contraception is most effective "
           "within 72 hours.", NHCADSV_EXAMS, DV_READ),
     claim("The DOVE Project gives free legal representation to qualifying survivors of "
           "domestic violence at final restraining order hearings, through the crisis center; "
           "603 Legal Aid at 800-639-5290 or 603-224-3333, the single point of entry to free "
           "legal services, including domestic violence, housing, family law and benefits.",
           NHCADSV_LEGAL, DV_READ),
     claim("Free and confidential crisis center services, including accompaniment to hospitals, "
           "police and courts and emergency shelter; the Victims' Compensation Program helps "
           "innocent victims of violent crime with expenses directly related to crime injuries.",
           NHCADSV_SERVICES, DV_READ),
     claim("If the court is closed, go to or call the nearest police department, not "
           "necessarily where you live; an officer helps fill out the forms and contacts a "
           "judge by telephone; the order lasts until the close of the next business day the "
           "court is open, and the plaintiff must go to a circuit court before then for a longer "
           "order; a stalking order needs no special relationship; court staff cannot advise "
           "which order is best; the checklist is in Spanish and other languages.",
           COURTS_PROTECT, DV_READ),
     claim("The ACP lets participants use a substitute address for state and local services "
           "such as a driver's license or car registration, and forwards first class mail; for "
           "victims who have left and live where the abuser does not know, who have not created "
           "records with the new address; a restraining order, charges or a report are not "
           "required; mail may be delayed by as much as 5 to 7 days; the law has applicants "
           "consult one of the crisis centers; sexual assault and stalking line 1-800-277-5570.",
           DOJ_ACP, DV_READ),
     claim("Proceedings may be brought where the plaintiff temporarily resides after leaving to "
           "avoid abuse.", "RSA 173-B:2", DV_READ),
     claim("Abuse is by a family or household member or a current or former sexual or intimate "
           "partner.", "RSA 173-B:1", DV_READ),
     claim("A petition in the county or district where either party resides; a minor plaintiff "
           "may get an order against a present or former intimate partner without a parent; no "
           "filing fee or fee for service, and no counsel needed; clerks supply forms; a hearing "
           "within 30 days of filing or 10 days of service, whichever is later.",
           "RSA 173-B:3", DV_READ),
     claim("Temporary orders on a showing of immediate and present danger, with or without notice "
           "to the defendant; by telephone through a law enforcement officer, effective until "
           "the close of the next regular court business day.", "RSA 173-B:4", DV_READ),
     claim("Officers give notice that a victim may ask for help with safety, an emergency "
           "telephonic order, retrieving toiletries, medication and clothing, being taken to a "
           "safe place, and an ambulance.", "RSA 173-B:10", DV_READ),
     claim("A victim of stalking may file a civil petition, with relief and procedures as under "
           "RSA 173-B.", "RSA 633:3-a", DV_READ),
     claim("Examinations of a victim of an alleged sexual offense are provided without charge; "
           "the bill is not sent or given to the victim or family.", "RSA 21-M:8-c", DV_READ),
     claim("A victim of domestic violence, stalking or sexual assault may apply to the attorney "
           "general for a designated address; certified for 4 years.", "RSA 7:43", DV_READ),
     claim("Personal injury from a felony or misdemeanor; claims within 2 years of the crime "
           "unless good cause; not ineligible for failure to apprehend or convict.",
           "RSA 21-M:8-h", DV_READ)]
    + help_claims("legal_aid"),
    more=civics.faq(
        ("Is there a line for sexual assault or stalking, or for someone outside New Hampshire?",
         "<p>For sexual assault or stalking, you can also call 1-800-277-5570. Outside New "
         "Hampshire, call the National Domestic Violence Hotline, 1-800-799-SAFE, or RAINN for "
         "sexual assault, 1-800-656-HOPE.</p>"),
        ("What can the police do when they respond?",
         "<p>When the police respond to abuse, they must help keep you safe: you can ask them "
         "to request an emergency order, to help you collect clothing, medication and other "
         "essentials, to take you to a safe place, and to get you an ambulance.</p>"),
        ("What if someone is stalking me, and can I get help at the hearing?",
         "<p>If someone is <b>stalking</b> you, you can ask the court for a stalking order the "
         "same way, whatever your relationship to them. Court staff cannot tell you which order "
         "is best for you, but an advocate or legal aid can. The court&rsquo;s checklist for the "
         "petition comes in Spanish and other languages. The DOVE Project gives free lawyers to "
         "qualifying survivors of domestic violence at the final hearing; ask your crisis "
         "center.</p>"),
        ("Can I keep a new address private?",
         "<p><b>Keeping a new address private.</b> If you have moved, or are about to move, "
         "somewhere the person who harmed you does not know, the Attorney General&rsquo;s "
         "Address Confidentiality Program gives you a substitute address to use for state and "
         "local services, such as a driver&rsquo;s license or car registration, and forwards "
         "your first-class mail. You do not need a restraining order, criminal charges or a "
         "police report. Apply before you create any records at the new address, and with a "
         "crisis center&rsquo;s help, as the law requires. Mail can be delayed by as much as 5 "
         "to 7 days. A certification lasts 4 years.</p>"),
        ("Is there help with the costs of a crime?",
         "<p><b>Costs of a crime.</b> The Victims&rsquo; Compensation Program helps victims of "
         "violent crime with costs that come from their injuries. Claims are generally filed "
         "within 2 years of the crime, and you can still qualify if no one is arrested or "
         "convicted.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Your local crisis center, through the 24-hour helpline at <a href=\"tel:+18666443574\">1-866-644-3574</a>, "
         "is the "
         "place to start for anything on this page. Its advocates can go with you to the "
         "hospital, the police or the court.</p>"
         "<p>If you think a child under 18 is being abused or neglected, New Hampshire law "
         'requires you to report it right away (<a href="/laws/169-c#s29">RSA 169-C:29</a> and '
         '<a href="/laws/169-c#s30">30</a>) to the Division for Children, Youth and Families: call '
         "(800) 894-5533 in New Hampshire, or (603) 271-6562.</p>"
         + helps("legal_aid"),
    see=[("How to get help if you are homeless or may lose your home", "/guides/homelessness-help.html"),
         ("How to apply for food or health assistance", "/guides/food-and-health-assistance.html"),
         ("How to vote", "/guides/how-to-vote.html")],
    figures=[fig("24-hour", NHCADSV, "A 24-hour helpline"),
             fig("5 to 7 days", DOJ_ACP, "as much as 5 to 7 days"),
             fig("5 minutes", NHCADSV_CENTERS, "generally in about 5 minutes"),
             fig("72 hours", NHCADSV_EXAMS, "within 72 hours"),
             fig("30 days", "RSA 173-B:3", "within 30 days of the filing of a petition"),
             fig("10 days", "RSA 173-B:3", "within 10 days of service of process"),
             fig("4 years", "RSA 7:43", "certified for 4 years"),
             fig("2 years", "RSA 21-M:8-h", "within 2 years of the crime")])

GUIDES += [VIOLENCE]


# ---------------------------------------------------------------------------
# IF YOU FACE DISCRIMINATION (the person, 25 October 2026: "Write all three
# know your rights guides too"). New Hampshire's Law Against Discrimination,
# RSA 354-A, read on the site's own Laws pages on 25 October 2026: who and
# what it protects at work, in housing and in places open to the public, the
# Commission for Human Rights, the 180 days to file a complaint, and the
# choice of Superior Court after it. The U.S. Equal Employment Opportunity
# Commission's page on filing a charge answers this machine and was read the
# same day; HUD's complaint page draws itself by script and was not, so the
# guide names no federal housing route. The Commission's own pages refuse a
# cloud session and wait for the person's printouts.
# ---------------------------------------------------------------------------
DISC_READ = "2026-10-25"
DISC_PAGES_READ = "2026-10-26"       # the person's printout of humanrights.nh.gov
HRC_HOME = "https://www.humanrights.nh.gov/"
EEOC_FILE = "https://www.eeoc.gov/how-file-charge-employment-discrimination"

DISCRIMINATION = guide(
    "discrimination", "If You Face Discrimination: Work, Housing and Public Places",
    "What New Hampshire's Law Against Discrimination protects at work, in renting or buying a "
    "home, and in stores, restaurants and other places open to the public, and how to file a "
    "complaint with the Commission for Human Rights.",
    "New Hampshire law forbids discrimination because of your age, sex, gender identity, race, "
    "creed, color, marital status, physical or mental disability, national origin or sexual "
    "orientation: at work and when you apply for a job, when you rent or buy a home, and in "
    "places open to the public. In housing, it also protects families with a child under 18 "
    "living with them. And no one may fire, expel or otherwise punish you for opposing "
    "discrimination, filing a complaint, or testifying or helping in a case about it. If it "
    "happens to you, you can file a "
    "written complaint with the New Hampshire Commission for Human Rights within 180 days.",
    [ask("Where did it happen?",
         [("At work, or applying for a job",
           "An employer with 6 or more employees is covered, and so are the state and every "
           "town."),
          ("Renting or buying a home",
           "Landlords, sellers and agents are covered, with a few exceptions."),
          ("A store, restaurant, hotel or other place open to the public",
           "Every place that serves the public is covered, except a private club.")]),
     box("Write down what happened, when, and who was there. Keep any letters, messages or "
         "notices."),
     box("File a complaint with the Commission for Human Rights within 180 days."),
     box("The Commission investigates, and tries to settle it. You may go to court instead, "
         "within the limits the law sets.")],
    [step("Know what the law protects",
          "<p>New Hampshire&rsquo;s <b>Law Against Discrimination</b> protects you from being "
          "treated differently because of your <b>age, sex, gender identity, race, creed, color, "
          "marital status, physical or mental disability, national origin or sexual "
          "orientation</b>. In housing it also protects <b>familial status</b>: having a child "
          "under 18 living with you.</p>"
          "<ul><li><b>Sexual harassment</b>, such as unwelcome sexual advances or requests for "
          "sexual favors, is discrimination because of sex.</li>"

          "<li><b>Retaliation</b> is against the law: no one may fire, expel or otherwise punish "
          "you because you opposed discrimination, filed a complaint, or testified or helped in "
          "a case.</li></ul>",
          law=["RSA 354-A:1", "RSA 354-A:7", "RSA 354-A:19"]),
     step("At work",
          "<p>An employer may not refuse to hire you, fire you, or treat you differently in pay "
          "or in the terms of your job because of any of the reasons above, unless the reason is "
          "a genuine requirement of the job. Job advertisements and applications may not state "
          "such a preference.</p>",
          law=["RSA 354-A:2", "RSA 354-A:6", "RSA 354-A:7"]),
     step("Renting or buying a home",
          "<p>No one may refuse to rent or sell to you, offer you different terms, tell you a "
          "home is not available when it is, or advertise a preference, because of any of the "
          "reasons above or because you have children under 18.</p>",
          law=["RSA 354-A:8", "RSA 354-A:10", "RSA 354-A:15"]),
     step("Stores, restaurants and other places open to the public",
          "<p>A place of <b>public accommodation</b> is any place that offers its goods or "
          "services to the public: a store, a restaurant, a hotel, a theater, a barbershop, a "
          "health care provider, a bus, and many more. It may not refuse you service, or treat "
          "you differently, because of any of the reasons above, or post a notice that some "
          "people are unwelcome. A club that is distinctly private is not covered.</p>",
          law=["RSA 354-A:2", "RSA 354-A:16", "RSA 354-A:17"]),
     step("File a complaint with the Commission for Human Rights",
          "<p>The <b>New Hampshire Commission for Human Rights</b> takes complaints of "
          "discrimination. Your complaint is in writing and signed, names who discriminated "
          "against you, and says what happened. File it <b>within 180 days</b> of the act. Write "
          "things down as they happen, and keep any letters, emails, texts or notices.</p>"
          "<p>The Commission also takes complaints of discrimination in K-12 public schools, and "
          "offers mediation. Submit a complaint from its website, or call (603) 271-2767, "
          "Monday through Friday, 8:00&nbsp;AM to 4:00&nbsp;PM; its office is at 57 Regional Drive, Suite 8, "
          "in Concord.</p>"
          "<p>A commissioner investigates, with the Commission&rsquo;s staff, and encourages "
          "both sides to settle. If the commissioner finds no probable cause, the complaint is "
          "dismissed, and you can appeal to the Superior Court. If there is probable cause and "
          "it is not settled, a hearing may be held before 3 commissioners, who can order the "
          "discrimination to stop and order hiring, reinstatement, back pay and damages. You "
          "have 30 days after the Commission&rsquo;s order is served to ask the Superior Court "
          "to review it.</p>",
          actions=[("Commission for Human Rights", HRC_HOME),
                   ("File a federal charge (EEOC)", EEOC_FILE)],
          law=["RSA 354-A:5", "RSA 354-A:21", "RSA 354-A:22"]),
     step("Or take it to court",
          "<p>Instead of waiting for the Commission to decide, you may sue in the Superior Court "
          "of your county, or of the county where it happened: once your complaint has been at "
          "the Commission for 180 days, or sooner if the Commission agrees in writing, and no "
          "later than <b>3 years</b> after the discrimination. Either side may ask for a jury. "
          "If you go to court, you cannot bring the same complaint back to the Commission, and "
          "you cannot go to court once a Commission hearing has begun.</p>"
          "<p>These deadlines are strict, and the choices between the Commission and the court "
          "are hard to undo. A lawyer can advise you on your own case (below).</p>",
          law=["RSA 354-A:21-a"])],
    [("Commission for Human Rights (New Hampshire)", HRC_HOME),
     ("How to File a Charge of Employment Discrimination (U.S. Equal Employment Opportunity "
      "Commission)", EEOC_FILE),
     ("Law Against Discrimination, RSA 354-A", "/laws/354-a")],
    ["354-A"],
    [# The Law Against Discrimination, as the site's own Laws pages print it, 25 October 2026.
     claim("Discrimination because of age, sex, gender identity, race, creed, color, marital "
           "status, familial status, physical or mental disability or national origin, in "
           "employment, in places of public accommodation and in housing accommodations; no "
           "person be discriminated against on account of sexual orientation.",
           "RSA 354-A:1", DISC_READ),
     claim("\"Employer\" does not include any employer with fewer than 6 persons in its employ, an "
           "exclusively social club, or a fraternal or religious association or corporation not "
           "organized for private profit; it includes the state and all political subdivisions, "
           "boards, departments, and commissions; \"employee\" does not include any individual "
           "employed by a parent, spouse or child, or in the domestic service of any person; "
           "familial status, individuals under 18 domiciled with a parent or custodian; a place "
           "of public accommodation includes any inn, hotel, restaurant, public conveyance, "
           "barbershop, theater, health care provider, store or other establishment which offers "
           "its goods or services to the general public, not any institution or club which is "
           "in its nature distinctly private.", "RSA 354-A:2", DISC_READ),
     claim("The opportunity to obtain employment without discrimination is a civil right.",
           "RSA 354-A:6", DISC_READ),
     claim("Unlawful for an employer to refuse to hire, to discharge, or to discriminate in "
           "compensation or in terms, conditions or privileges of employment, unless based upon "
           "a bona fide occupational qualification; or to print any statement, advertisement or "
           "application form expressing a limitation; harassment on the basis of sex is "
           "unlawful sex discrimination, including unwelcome sexual advances and requests for "
           "sexual favors; sex includes pregnancy; leave for the temporary physical disability "
           "of pregnancy and childbirth, and the original or a comparable job on return unless "
           "business necessity makes this impossible or unreasonable; reasonable accommodations "
           "for a qualified individual with a disability unless an undue hardship.",
           "RSA 354-A:7", DISC_READ),
     claim("The opportunity to obtain housing without discrimination, including familial status "
           "and sexual orientation, is a civil right.", "RSA 354-A:8", DISC_READ),
     claim("Unlawful to refuse a real estate transaction, alter its terms, represent that real "
           "property is not available when it is, or publish a notice or advertisement "
           "indicating a preference, limitation, or discrimination.", "RSA 354-A:10", DISC_READ),
     claim("Exemptions from RSA 354-A:10: certain private sales of single family homes by an "
           "owner without a broker; rental in a building of not more than 4 families if the "
           "owner resides in one; rental of rooms in a private home by an owner; the exemptions "
           "do not apply to RSA 354-A:10, VII.", "RSA 354-A:15", DISC_READ),
     claim("Equal access to places of public accommodation is a civil right; unlawful to "
           "refuse, withhold or deny its accommodations, or to post a notice that any person is "
           "unwelcome.", "RSA 354-A:17", DISC_READ),
     claim("Equal access to places of public accommodation without discrimination is a civil "
           "right, including sexual orientation.", "RSA 354-A:16", DISC_READ),
     claim("Unlawful to discharge, expel, or otherwise retaliate against any person because he "
           "has opposed any practices forbidden under this chapter or has filed a complaint, "
           "testified or assisted in any proceeding.", "RSA 354-A:19", DISC_READ),
     claim("The commission receives, investigates and passes upon complaints alleging "
           "violations of this chapter.", "RSA 354-A:5", DISC_READ),
     claim("A verified complaint in writing naming who committed the practice and the "
           "particulars; investigation by a commissioner, encouraging settlement; dismissal on "
           "no probable cause, with a right of appeal to superior court; conciliation; a hearing "
           "before 3 members of the commission; orders to cease and desist, hiring, "
           "reinstatement, back pay, compensatory damages; must be filed within 180 days after "
           "the alleged act of discrimination.", "RSA 354-A:21", DISC_READ),
     claim("At the expiration of 180 days after the timely filing of a complaint with the "
           "commission, or sooner if the commission assents in writing, but not later than 3 "
           "years after the alleged unlawful practice occurred, a civil action in the superior "
           "court for the county where it occurred or of the party's residence; trial by jury; "
           "not available once a commission hearing has begun or concluded; a party electing "
           "court is barred from a subsequent complaint to the commission on the same practice.",
           "RSA 354-A:21-a", DISC_READ),
     claim("Judicial review of a commission order in the superior court, instituted within 30 "
           "days after the service of the order of the commission.", "RSA 354-A:22", DISC_READ),
     # The EEOC's page, read on 25 October 2026.
     claim("The 180-calendar-day filing deadline is extended to 300 calendar days if a state or "
           "local agency enforces a law that prohibits employment discrimination on the same "
           "basis; if you file a charge with either EEOC or a FEPA with a worksharing agreement, "
           "the charge also will be automatically filed with the other agency (dual filing); "
           "you can let the state agency know if you also want your charge filed with the EEOC; "
           "1-800-669-4000.", EEOC_FILE, DISC_READ),
     # The Commission's own page, from the person's printout.
     claim("A state agency established by RSA 354-A for the purpose of education and enforcement "
           "of the law against discrimination in employment, housing, places of public "
           "accommodation and K-12 public schools; Submit a Complaint; Mediation; 57 Regional "
           "Drive, Suite 8, Concord, NH 03301; (603) 271-2767; Monday - Friday, 8AM - 4PM.",
           HRC_HOME, DISC_PAGES_READ)]
    + help_claims("lawyer"),
    more=civics.faq(
        ("Does the law cover pregnancy?",
         "<p>Discrimination because of sex includes <b>pregnancy</b>. An employer must give a "
         "leave of absence for a disability caused by pregnancy or childbirth, and hold your "
         "job or a comparable one for your return unless business necessity makes that "
         "impossible or unreasonable.</p>"),
        ("Must an employer adjust my job for a disability?",
         "<p>An employer must make <b>reasonable accommodations</b> for a qualified employee "
         "or applicant with a disability, such as a changed schedule or equipment, unless "
         "doing so would be an undue hardship.</p>"),
        ("Which employers does the law cover?",
         "<p>The law covers employers with 6 or more employees, and the state and its cities, "
         "towns, boards and departments. It does not cover a nonprofit social "
         "club, or a nonprofit fraternal or religious organization, as an employer, or work "
         "for your own parent, spouse or child, or in someone&rsquo;s home as a domestic "
         "worker.</p>"),
        ("Are there exceptions in housing?",
         "<p>There are a few exceptions. They include renting a unit in a building of no more "
         "than 4 units where the owner lives in one of them, renting a room in the "
         "owner&rsquo;s own home, and some sales of a single-family home by its owner without "
         "a real estate agent.</p>"),
        ("Can I file with the federal government too?",
         "<p><b>At work, federal law protects you too.</b> The U.S. Equal Employment "
         "Opportunity Commission says that where a state agency enforces a law like this one, "
         "its own deadline is extended to 300 days, and that a charge filed with a state "
         "agency that works with it can be filed with both at once. Tell the Commission if you "
         "want yours filed with the federal agency as well.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>The Commission for Human Rights can tell you how to file a complaint. For advice "
         "on your own case, talk to a lawyer:</p>"
         + helps("lawyer"),
    see=[("Your rights as a tenant", "/guides/tenant-rights.html"),
         ("Your rights at work: getting paid", "/guides/wage-rights.html"),
         ("How to get help after domestic violence, sexual assault or stalking",
          "/guides/domestic-violence-help.html")],
    figures=[fig("180 days", "RSA 354-A:21", "within 180 days after the alleged act of discrimination"),
             fig("3 years", "RSA 354-A:21-a", "not later than 3 years after the alleged unlawful "
                 "practice occurred"),
             fig("30 days", "RSA 354-A:22", "within 30 days after the service of the order of the "
                 "commission"),
             fig("300 days", EEOC_FILE, "extended to 300 calendar days")])

GUIDES += [DISCRIMINATION]


# ---------------------------------------------------------------------------
# HELP IF YOU ARE HOMELESS OR MAY LOSE YOUR HOME (the person, 24 October
# 2026). From the Department of Health and Human Services' Homeless Services
# page, the Judicial Branch's Landlord/Tenant page and the Department of
# Education's page on homeless children and youth, read in the PDFs the person
# printed and sent that day; from 211 New Hampshire and New Hampshire
# Housing's pages, which answer a cloud session and were read the same day;
# from RSA 165, 540 and 540-A as the Laws pages print them; and from the
# federal McKinney-Vento Act, 42 U.S.C. 11432, at govinfo. No income limit is
# printed: the voucher's is HUD's and changes (the plan: no eligibility
# math), and the guide links New Hampshire Housing's page that states it.
# ---------------------------------------------------------------------------
HL_READ = "2026-10-24"
NH211_HOME = "https://211nh.org/"
DHHS_HOMELESS = "https://www.dhhs.nh.gov/programs-services/homeless-services"
COURTS_LLT = "https://www.courts.nh.gov/our-courts/circuit-court/district-division/landlordtenant"
DOE_EHCY = ("https://www.education.nh.gov/who-we-are/division-of-learner-support/"
            "bureau-of-instructional-support/ehcy")
NHH_APPLY = "https://www.nhhousing.org/rental-assistance/apply/"
NHH_RENTERS = "https://www.nhhousing.org/resources/resources-for-renters/"
USC_11432 = ("https://www.govinfo.gov/content/pkg/USCODE-2024-title42/html/"
             "USCODE-2024-title42-chap119-subchapVI-partB-sec11432.htm")

HOMELESS = guide(
    "homelessness-help", "How to Get Help If You Are Homeless or May Lose Your Home",
    "Where to find shelter and emergency help, what your town must do, your rights if you are "
    "facing eviction, how to apply for a housing voucher, and your children's right to stay in "
    "school.",
    "Call 2-1-1, at any hour, to find shelter and housing help near you, or go to your town or "
    "city welfare office, which must help a person there who is poor and unable to support "
    "themselves. If you are facing eviction, your landlord can only make you leave through the "
    "court, and free mediation and free legal aid can help. If you are leaving someone who "
    "hurts you, call 1-866-644-3574.",
    [box("Call 2-1-1, at any hour, for shelter and housing help near you."),
     ask("What is happening?",
         [("You have nowhere to stay",
           "Call 2-1-1 for a shelter, and ask your town or city welfare office for help."),
          ("You may be evicted",
           "Only a court can make you leave. Answer the court papers, and get free legal help.")]),
     box("Apply for a housing voucher, and ask your school&rsquo;s homeless liaison to keep your "
         "children in school.")],
    [step("Call 2-1-1, or your town’s welfare office",
          "<p><b>2-1-1 New Hampshire</b> connects you with shelter, housing, food, utility and "
          "other help where you are, 24 hours a day, every day of the year, by phone, email or "
          "text. Dial 2-1-1, or call 1-866-444-4211. In an emergency, call 911; in a mental "
          "health crisis, call 988.</p>"
          "<p><b>Your town or city welfare office</b> must help a person who is poor and unable "
          "to support themselves, under the written guidelines every town and city adopts: how "
          "to apply, who is eligible, and how to appeal a decision.</p>",
          actions=[("2-1-1 New Hampshire", NH211_HOME)],
          law=["RSA 165:1", "RSA 165:1-c"]),
     step("Find a shelter",
          "<p>The Department of Health and Human Services&rsquo; Bureau of Homeless Services "
          "funds shelters and other homeless services through local agencies in all ten "
          "counties. To find a bed, call 2-1-1 or your town&rsquo;s welfare office. Your local "
          "Community Action Program can help too.</p>"
          "<p>If you are leaving someone who hurts you, the crisis centers run emergency "
          "shelters: call 1-866-644-3574, at any hour.</p>",
          actions=[("Homeless services (Department of Health and Human Services)", DHHS_HOMELESS)]),
     step("If you may be evicted",
          "<p><b>Only a court can make you leave.</b> A landlord may not lock you out or shut "
          "off your heat, water, electricity or other utilities to force you out.</p>"
          "<ul><li><b>Before any court case,</b> you and your landlord can use the court&rsquo;s "
          "free Eviction Diversion Program, where a mediator helps you try to reach an "
          "agreement. Taking part is your choice, and you give up no rights.</li>"
          "<li><b>If you are served court papers</b> (a Landlord/Tenant Writ), file an Appearance "
          "form with the court by the <em>return date</em> on the writ to be heard. The return "
          "date is not the hearing; the trial is usually about 10 days after you file. If you "
          "do not file, or do not come to the hearing, the court issues a Notice of Default, and "
          "no sooner than 5 business days later it can issue a Writ of Possession, which lets "
          "the landlord take back the home.</li>"
          "<li><b>If the case is only about unpaid rent,</b> it is dismissed if, before the "
          "hearing, you pay all the rent you owe, any other lawful charges in your lease, $15, "
          "and the landlord&rsquo;s filing and service costs. You can do this up to 3 times in a "
          "12-month period.</li></ul>"
          "<p>Get free legal help as early as you can, from 603 Legal Aid or New Hampshire "
          "Legal Assistance.</p>",
          actions=[("Landlord and tenant cases (Judicial Branch)", COURTS_LLT)],
          law=["RSA 540-A:3", "RSA 540:9"]),
     step("Apply for a housing voucher",
          "<p>With a <b>Housing Choice Voucher</b>, you pay part of your income toward rent and "
          "utilities and New Hampshire Housing pays the rest to the landlord. You choose the "
          "place, which must meet housing quality standards. It is for households with very low "
          "incomes; New Hampshire Housing&rsquo;s page gives the limits.</p>"
          "<p>The wait is long, 7 to 9 years for most applicants, but New Hampshire Housing "
          "encourages anyone struggling to pay rent to apply and to mark every preference that "
          "fits their household on the application. Apply online, or call 1-800-439-7247 to "
          "have an application mailed. Some towns have their own housing authority with its own "
          "programs: ask your town.</p>",
          actions=[("Apply for a voucher (New Hampshire Housing)", NHH_APPLY),
                   ("Resources for renters (New Hampshire Housing)", NHH_RENTERS)]),
     step("Keep your children in school",
          "<p>Under the federal McKinney-Vento Act, a child or youth without a fixed home can "
          "stay in their <b>school of origin</b>, the school they went to before, where that is "
          "in their best interest, or go to the local school where they are staying now. The "
          "school must <b>enroll them right away</b>, even without school or health records, "
          "proof of residency or other documents, and must provide or arrange transportation "
          "to the school of origin.</p>"
          "<p>Every school district has a <b>homeless liaison</b> whose job is to make sure "
          "this happens. The Department of Education lists every liaison in the state, with "
          "information on the rights of parents and of young people on their own.</p>",
          actions=[("Homeless children and youth (Department of Education)", DOE_EHCY)])],
    [("2-1-1 New Hampshire", NH211_HOME),
     ("Homeless Services (Department of Health and Human Services)", DHHS_HOMELESS),
     ("Landlord/Tenant, District Division (Judicial Branch)", COURTS_LLT),
     ("Housing Choice Voucher: Apply (New Hampshire Housing)", NHH_APPLY),
     ("Resources for Renters (New Hampshire Housing)", NHH_RENTERS),
     ("Education for Homeless Children and Youth Program (Department of Education)", DOE_EHCY),
     ("New Hampshire Coalition Against Domestic and Sexual Violence", NHCADSV),
     ("Support Services and Programs (Coalition Against Domestic and Sexual Violence)",
      NHCADSV_SERVICES),
     ("Education for homeless children and youths, 42 U.S.C. 11432 (federal)", USC_11432),
     ("Aid to Assisted Persons, RSA 165", "/laws/165"),
     ("Actions Against Tenants, RSA 540", "/laws/540"),
     ("Prohibited Practices and Security Deposits, RSA 540-A", "/laws/540-a")],
    ["165", "540", "540-A"],
    [claim("211 NH connects residents to resources through trained Information and Referral "
           "Specialists, available 24 hours, 365 days a year, by phone, email or text, for "
           "housing, utilities, food, mental health and more; dial 211 or 1-866-444-4211; 911 "
           "for emergencies; 988 for suicide and crisis help.", NH211_HOME, HL_READ),
     claim("For housing and shelter resources, call NH 2-1-1 or contact your local city or "
           "town welfare office; the Bureau of Homeless Services plans and funds homeless "
           "services through contracted agencies across New Hampshire's ten counties, offered "
           "locally through community partners.", DHHS_HOMELESS, HL_READ),
     claim("For emergency shelter or housing, call 2-1-1, contact your local Community Action "
           "Program, or contact town welfare; New Hampshire Housing encourages anyone "
           "struggling to pay rent to apply and indicate preferences; wait about 7 to 9 years; "
           "contact your town about a town housing authority; for eviction help, 603 Legal Aid "
           "and New Hampshire Legal Assistance.", NHH_RENTERS, HL_READ),
     claim("A qualified household pays a portion of adjusted income toward rent and utilities "
           "and New Hampshire Housing pays the remainder to the landlord; the household selects "
           "a unit meeting housing quality standards; for very low-income households, with "
           "income limits on the page; apply online or call 1-800-439-7247 for a mailed "
           "application; for a paper application, contact us at (603) 472-8623 or "
           "rentinfo@nhhousing.org to request one be mailed to you; for most applicants an "
           "estimated wait of 7 to 9 years.",
           NHH_APPLY, HL_READ),
     claim("The Eviction Diversion Program: free mediation before a court case, voluntary, no "
           "rights given up; a tenant files an Appearance by the return date on the "
           "Landlord/Tenant Writ to be heard; the return date is not the hearing; trial within "
           "about 10 days of an Appearance; failing to file or appear brings a Notice of "
           "Default, and the Writ of Possession does not issue for at least 5 business days; "
           "after judgment for the landlord, 7 days to file a Notice of Intent to Appeal, with "
           "weekly rent paid during the appeal.", COURTS_LLT, HL_READ),
     claim("The EHCY program addresses the challenges homeless children and youth face in "
           "enrolling, attending and succeeding in school; the homeless liaison contact list "
           "gives every liaison in the state; information on the educational rights of parents "
           "and of unaccompanied youth.", DOE_EHCY, HL_READ),
     claim("The local educational agency, in the child's best interest, continues the child in "
           "the school of origin or enrolls the child where actually living; the school "
           "immediately enrolls the child even without records, immunization records or proof "
           "of residency; transportation to and from the school of origin is provided or "
           "arranged; each agency has a liaison who ensures homeless children are identified "
           "and enrolled.", USC_11432, HL_READ),
     claim("A person in any town who is poor and unable to support themselves is relieved by "
           "the town's overseers of public welfare; every town and city adopts written "
           "guidelines on applying, eligibility and appeals; proof of residency includes an "
           "attestation by the welfare official, a law enforcement or fire official, an EMS "
           "provider or a local third party social services provider with an existing service "
           "relationship, on official agency letterhead, with the last date of contact, signed "
           "and dated by an authorized official, unless the welfare official identifies specific, "
           "substantiated evidence contradicting it.",
           "RSA 165:1", HL_READ),
     claim("A 24-hour helpline, 1-866-644-3574; the crisis centers serve victims of domestic "
           "violence, sexual assault, stalking, child abuse and human trafficking; free and "
           "confidential.", NHCADSV, DV_READ),
     claim("Free and confidential crisis center services, including accompaniment to hospitals, "
           "police and courts and emergency shelter.", NHCADSV_SERVICES, DV_READ),
     claim("A person temporarily in a town that is not their residence is given reasonable and "
           "necessary temporary assistance.", "RSA 165:1-c", HL_READ),
     claim("No landlord may interrupt utility service or deny a tenant access to the premises "
           "other than through proper judicial process.", "RSA 540-A:3", HL_READ),
     claim("A possession action for nonpayment alone is dismissed if before the hearing the "
           "tenant pays all rent due, other lawful charges, $15 liquidated damages and the "
           "landlord's filing fee and service charges; not more than 3 times within a 12-month "
           "period.", "RSA 540:9", HL_READ)]
    + help_claims("legal_aid"),
    more=civics.faq(
        ("What if I am only staying in a town for now?",
         "<p>If you are only staying in a town for now, it must still give you the temporary "
         "help that is reasonable and necessary.</p>"),
        ("What if I have no lease or bill to prove where I live?",
         "<p>If you are asked to prove where you live and have no lease or bill, a signed and "
         "dated statement on agency letterhead, giving the last date of contact, counts. It can "
         "come from the welfare official, a police or fire official, an emergency medical "
         "provider, or a local social services provider already serving you, unless the welfare "
         "official has specific evidence against it.</p>"),
        ("Can I appeal if I lose an eviction case?",
         "<p><b>If you lose,</b> you have 7 days from the Notice of Judgment to file a Notice "
         "of Intent to Appeal, and you will have to pay rent each week while the appeal goes "
         "on.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>2-1-1 New Hampshire, at any hour, and your town or city welfare office are the "
         "places to start. To have a housing voucher application mailed to you, call New "
         "Hampshire Housing at (603) 472-8623. "
         "For help with an eviction or a denial of town assistance:</p>"
         + helps("legal_aid"),
    see=[("How to get help after domestic violence, sexual assault or stalking",
          "/guides/domestic-violence-help.html"),
         ("How to apply for food or health assistance", "/guides/food-and-health-assistance.html"),
         ("How to get help with heating and electric bills", "/guides/heating-and-electric-help.html")],
    figures=[fig("24 hours", NH211_HOME, "24 hours, 365 days"),
             fig("$15", "RSA 540:9", "$15 liquidated damages"),
             fig("12-month", "RSA 540:9", "within a 12-month period"),
             fig("10 days", COURTS_LLT, "about 10 days"),
             fig("5 business days", COURTS_LLT, "at least 5 business days"),
             fig("7 days", COURTS_LLT, "7 days to file a Notice of Intent to Appeal"),
             fig("7 to 9 years", NHH_APPLY, "wait of 7 to 9 years")])

GUIDES += [HOMELESS]


# ---------------------------------------------------------------------------
# RENTING A HOME: THE TENANT'S RIGHTS AND THE LANDLORD'S DUTIES (the person,
# 25 October 2026: "know your rights guides for both tenants and
# landlords"). One law, two readers, so two guides that say it alike and link
# each other. Read on 25 October 2026 from RSA 540 (actions against tenants),
# RSA 540-A (prohibited practices and security deposits) and RSA 48-A:14
# (the minimum standards where a town has no housing code of its own) as this
# site's Laws pages print them -- with the paragraphs in force since 8
# October 2026, where the chapters print an old and a new version -- and from
# the Judicial Branch's landlord-tenant page and New Hampshire Housing's
# renters' page, as the homelessness guide read them on 24 October 2026.
# Neither guide is legal advice: each says where a reader gets a lawyer or
# free legal aid. The security deposit rules do not reach every landlord
# (RSA 540-A:5, I), nor does the need for a reason to evict (RSA 540:1-a), and
# each guide says so where it matters.
# ---------------------------------------------------------------------------
RENT_READ = "2026-10-25"

TENANT = guide(
    "tenant-rights", "Your Rights as a Tenant",
    "What a New Hampshire landlord may and may not do, your security deposit, repairs and heat, "
    "rent increases, and what happens in an eviction, step by step, with the law for each.",
    "In New Hampshire only a court can make you leave your home: a landlord may not lock you "
    "out, shut off your utilities or hold your belongings to force you out. For most rentals, a "
    "security deposit can be no more than one month&rsquo;s rent or $100, whichever is more, "
    "and it comes back within 30 days after you move out, less the cost of any damage beyond "
    "normal wear and tear. Your home must meet basic standards for heat, water, plumbing and "
    "safety. If you get an eviction notice or court papers, read the dates and get free legal "
    "help right away.",
    [ask("What is happening?",
         [("You were locked out, or a utility was shut off",
           "That is against the law. Ask the district court to order it stopped; there is no "
           "filing fee."),
          ("Something needs repair",
           "Tell your landlord in writing. If it is not fixed, ask your town whether it has a "
           "housing code and who enforces it."),
          ("You got an eviction notice or court papers",
           "Read the dates, and get free legal help now. Only a court can make you leave."),
          ("You are moving out",
           "Your deposit comes back within 30 days, with a written list of any deductions.")]),
     box("Keep copies of your lease, rent receipts, letters and photos.")],
    [step("Only a court can make you leave",
          "<p>A landlord may not:</p>"
          "<ul><li><b>shut off or interrupt a utility</b>, such as water, heat, electricity or "
          "gas, except briefly while repairs are made or in an emergency;</li>"
          "<li><b>lock you out</b>, or keep you from your home or your belongings, except "
          "through the court;</li>"
          "<li><b>enter your home without your consent</b>, except to make emergency repairs "
          "or with a court&rsquo;s order.</li></ul>"
          "<p>You, in turn, may not damage the landlord&rsquo;s property or keep the landlord "
          "from making necessary repairs, at a reasonable time after notice that is adequate "
          "for the situation.</p>"
          "<p>If a landlord breaks these rules, you can file a petition in the circuit "
          "court&rsquo;s district division where the home is. There is <b>no filing fee</b>, "
          "you do not need a lawyer, and the clerk has the forms. The court holds a hearing "
          "within 30 days of the filing or 10 days after the landlord is served, whichever is "
          "later, and can order the landlord to stop at once if you face immediate harm. It can "
          "also award you damages, and order the landlord to pay your costs and attorney&rsquo;s "
          "fees.</p>",
          actions=[("Landlord and tenant cases (Judicial Branch)", COURTS_LLT)],
          law=["RSA 540-A:2", "RSA 540-A:3", "RSA 540-A:4"]),
     step("Your security deposit",
          "<ul><li><b>The limit:</b> one month&rsquo;s rent or $100, whichever is more.</li>"
          "<li><b>A receipt</b> stating the amount and where the deposit is held, unless you "
          "paid by check.</li>"
          "<li><b>Within 5 days of moving in,</b> give your landlord a written list of anything "
          "in the home that needs repair, and keep a copy. Your landlord must tell you that you "
          "can.</li>"
          "<li><b>When you move out,</b> the landlord returns it within 30 days, with any "
          "interest. A landlord who keeps any of it for damage beyond reasonable wear and tear, "
          "unpaid rent or other charges must give you a written, itemized list.</li></ul>"
          "<p>Give your landlord your new address when you leave. A landlord who does not "
          "return a deposit as the law requires can owe you twice the amount wrongly kept.</p>",
          law=["RSA 540-A:5", "RSA 540-A:6", "RSA 540-A:7", "RSA 540-A:8"]),
     step("Repairs, heat and a safe home",
          "<p>Where your town has no housing code of its own, the law sets the minimum: no "
          "insect, rodent or bed bug infestation left without an inspection and treatment "
          "program; no defective plumbing or sewage back-up; no exposed wires or other danger "
          "of shock or fire; no roof or walls that leak; no falling plaster, large holes, or "
          "unsound porches, stairs or railings; enough water and working hot water equipment; "
          "no gas leaks; and heat that can keep every room at an average of at least 65 "
          "degrees. Towns with a housing code enforce their own standards.</p>"
          "<p><b>Tell your landlord in writing</b> what needs fixing, and keep a copy. If it is "
          "not fixed, ask your town or city whether it has a housing code: where it does, a "
          "town board or officer enforces it and can find a home unfit to live in. A "
          "landlord must look into a report of bed bugs or other pests within 7 days.</p>",
          law=["RSA 48-A:14", "RSA 48-A:3", "RSA 540-A:3", "RSA 540:13-d"]),
     step("Rent increases, the end of a lease, and retaliation",
          "<p><b>When a landlord needs a reason.</b> For most rentals, a landlord can end your "
          "tenancy only for a reason the law lists: unpaid rent, substantial damage, breaking "
          "a material term of the lease, behavior that threatens others&rsquo; health or "
          "safety, or other good cause, which can be a legitimate business or economic reason. "
          "A lease of 12 months or longer, counting renewals, can also end at its term, if the "
          "landlord gave you written notice at least 60 days before and goes to court within 6 "
          "months after the lease ends. The exceptions, where no reason is needed: a "
          "single-family house whose owner owns no more than 3, a unit in a building of 4 units "
          "or fewer that the owner lives in, and a single-family house a bank or other lender "
          "took through foreclosure.</p>"
          "<p><b>Rent increases.</b> Refusing a rent increase can be good cause to evict, but "
          "only if the landlord gave you written notice of the amount and the date at least 30 "
          "days before it takes effect.</p>"
          "<p><b>Retaliation.</b> A landlord may not evict you for reporting a code violation, "
          "for going to court under the tenant protection law, or for meeting with other "
          "tenants, unless you owe a week&rsquo;s rent or more. An eviction, a rent increase or "
          "a big change in your terms within 6 months of that is presumed to be retaliation, "
          "and the court can award you up to 3 months&rsquo; rent.</p>",
          law=["RSA 540:1-a", "RSA 540:2", "RSA 540:11", "RSA 540:11-b", "RSA 540:13-a",
               "RSA 540:13-b", "RSA 540:14"]),
     step("If you get an eviction notice or court papers",
          "<ul><li><b>The eviction notice</b> must be in writing and say why. It gives you 7 "
          "days to leave for unpaid rent, substantial damage or a threat to others&rsquo; "
          "safety, and 30 days for other reasons. It does not make you leave by itself: if you "
          "stay, the landlord must go to court.</li>"
          "<li><b>For unpaid rent,</b> the case is dismissed if, before the hearing, you pay "
          "all the rent you owe, other lawful charges, $15 and the landlord&rsquo;s filing and "
          "service costs. You can do this up to 3 times in a 12-month period.</li>"
          "<li><b>Before any court case,</b> the court&rsquo;s free Eviction Diversion Program "
          "offers a mediator to help you and your landlord reach an agreement.</li>"
          "<li><b>If you are served court papers</b> (a Landlord/Tenant Writ), file an "
          "Appearance by the <em>return date</em> on the writ, and an answer with your defenses "
          "no more than 5 days after it. If you do not, you can lose without a hearing.</li>"
          "<li><b>If you lose,</b> the court may give you up to 60 days to move, or 75 in "
          "limited cases you must prove, if you pay the rent each week in advance and have not "
          "defaulted. To appeal, file a notice of intent to appeal within 7 days of "
          "the decision, and pay rent as it comes due.</li></ul>",
          actions=[("Landlord and tenant cases (Judicial Branch)", COURTS_LLT)],
          law=["RSA 540:3", "RSA 540:9", "RSA 540:13", "RSA 540:13-c", "RSA 540-A:3"])],
    [("Landlord/Tenant, District Division (Judicial Branch)", COURTS_LLT),
     ("Resources for Renters (New Hampshire Housing)", NHH_RENTERS),
     ("Actions Against Tenants, RSA 540", "/laws/540"),
     ("Prohibited Practices and Security Deposits, RSA 540-A", "/laws/540-a"),
     ("Housing Standards, RSA 48-A", "/laws/48-a")],
    ["540", "540-A", "48-A"],
    [# The Judicial Branch's and New Hampshire Housing's pages, as the
     # homelessness guide read them on 24 October 2026.
     claim("The Eviction Diversion Program: free mediation before a court case, voluntary, no "
           "rights given up; a tenant files an Appearance by the return date on the "
           "Landlord/Tenant Writ to be heard; the return date is not the hearing; trial within "
           "about 10 days of an Appearance; failing to file or appear brings a Notice of "
           "Default, and the Writ of Possession does not issue for at least 5 business days; "
           "after judgment for the landlord, 7 days to file a Notice of Intent to Appeal, with "
           "weekly rent paid during the appeal.", COURTS_LLT, HL_READ),
     claim("For emergency shelter or housing, call 2-1-1, contact your local Community Action "
           "Program, or contact town welfare; New Hampshire Housing encourages anyone "
           "struggling to pay rent to apply and indicate preferences; wait about 7 to 9 years; "
           "contact your town about a town housing authority; for eviction help, 603 Legal Aid "
           "and New Hampshire Legal Assistance.", NHH_RENTERS, HL_READ),
     # The statutes, as this site's Laws pages print them, read 25 October 2026.
     claim("No landlord shall willfully violate a tenant's right to quiet enjoyment or attempt "
           "to circumvent lawful procedures for eviction; no tenant shall willfully damage the "
           "landlord's property or prevent completion of necessary repairs.", "RSA 540-A:2",
           RENT_READ),
     claim("No landlord shall willfully interrupt or terminate any utility service, including "
           "water, heat, light, electricity and gas, except temporarily while repairs are in "
           "process or in emergencies (I); deny a tenant access to the premises (II) or to the "
           "tenant's property (III) other than through proper judicial process; enter without "
           "prior consent other than to make emergency repairs (IV), or with a court order "
           "(V-d); a tenant shall not willfully prevent necessary repairs or refuse access at a "
           "reasonable time after adequate notice (V); a landlord investigates a report of an "
           "infestation within 7 days (V-a); stores a vacated tenant's personal property with "
           "reasonable care for 7 days, recoverable without rent or storage fees (VII).",
           "RSA 540-A:3", RENT_READ),
     claim("A petition in the district court, no filing fee, without legal counsel; the clerks "
           "supply forms; a hearing within 30 days of filing or 10 days of service, whichever "
           "is later; temporary orders on an immediate threat of irreparable harm; damages; "
           "the civil remedies of RSA 358-A:10 with costs and reasonable attorney's fees.",
           "RSA 540-A:4", RENT_READ),
     claim("A landlord for this subdivision excludes a person who rents a single-family "
           "residence and owns no other rental property, or rents units in an owner-occupied "
           "building of 5 units or less, except for a unit occupied by a person 60 years of "
           "age or older.", "RSA 540-A:5", RENT_READ),
     claim("No security deposit in excess of one month's rent or $100, whichever is greater; a "
           "signed receipt stating the amount and where held, not required when paid by check; "
           "notice that conditions needing repair be noted in writing within 5 days of "
           "occupancy; deposits held in trust; interest on a deposit held one year or longer.",
           "RSA 540-A:6", RENT_READ),
     claim("Return the security deposit and interest within 30 days from the termination of the "
           "tenancy; deduct damages excluding reasonable wear and tear, unpaid rent and other "
           "lawful charges, with a written, itemized list.", "RSA 540-A:7", RENT_READ),
     claim("A landlord who does not comply with RSA 540-A:6, IV or 540-A:7 is liable for twice "
           "the deposit plus interest, less lawful charges; not liable if the tenant failed to "
           "give a new address; unclaimed deposits after 6 months become the landlord's.",
           "RSA 540-A:8", RENT_READ),
     claim("In a municipality without its own ordinance, no landlord shall maintain premises "
           "infested by insects, rodents or bed bugs without an inspection program; with "
           "defective plumbing or sewage back-up; electrical dangers; leaking roof or walls; "
           "falling plaster; substantial holes; unsound porches, stairs or railings; garbage "
           "in common areas; inadequate water or hot water equipment; gas leaks; or heating "
           "not capable of a temperature of at least an average of 65 degrees.",
           "RSA 48-A:14", RENT_READ),
     claim("No possessory action for nonpayment if the premises are in substantial violation "
           "of RSA 48-A or local codes materially affecting habitability, the tenant gave notice "
           "while not in arrears, and the landlord failed to correct within 14 days; the court "
           "may require rent paid into court.", "RSA 540:13-d", RENT_READ),
     claim("Nonrestricted property: single-family houses whose owner owns not more than 3, "
           "units in an owner-occupied building of 4 dwelling units or fewer, and single-family "
           "houses acquired by banks or other mortgagees through foreclosure; restricted "
           "property is all other residential rental property.", "RSA 540:1-a", RENT_READ),
     claim("A public agency a municipality's housing code establishes, which on inspection or a "
           "petition finds a dwelling unfit for human habitation and orders it repaired or "
           "closed.", "RSA 48-A:3", "2026-10-26"),
     claim("Restricted property may be terminated only for nonpayment, substantial damage, "
           "failure to comply with a material term, behavior adversely affecting health or "
           "safety, other good cause, and the other listed reasons; a lease of 12 months or "
           "longer, or renewed to 12 months or longer, at its expiration with written notice at "
           "least 60 days in advance, provided the landlord has filed a possessory action within "
           "6 months of the lease expiring; refusal "
           "of a rent increase is good cause if written notice of the amount and effective "
           "date came at least 30 days prior; other good cause includes any legitimate "
           "business or economic reason; no termination solely because a tenant is a victim "
           "of domestic violence, sexual assault or stalking.", "RSA 540:2", RENT_READ),
     claim("A month-to-month tenancy may be terminated by the lessee upon 30 days notice.",
           "RSA 540:11", RENT_READ),
     claim("A tenant may terminate a lease when the tenant or a household member has been, "
           "within the most recent 150 days, a victim of domestic violence, sexual assault or "
           "stalking, with written verification; the tenant shall vacate within 30 days of "
           "giving notice.", "RSA 540:11-b", RENT_READ),
     claim("Except where the tenant owes a week's rent or more, a defense that the possessory "
           "action retaliates for reporting a violation, initiating an action under RSA 540-A, "
           "or meeting with other tenants.", "RSA 540:13-a", RENT_READ),
     claim("A rebuttable presumption of retaliation when a possessory action, an increase in "
           "rent or a substantial alteration in the terms is instituted within 6 months after "
           "the protected act.", "RSA 540:13-b", RENT_READ),
     claim("On a successful defense of retaliation, damages of not more than 3 months' rent.",
           "RSA 540:14", RENT_READ),
     claim("For residential tenancies, 30 days' notice; 7 days' notice for nonpayment, "
           "substantial damage, behavior affecting health or safety; the eviction notice "
           "states the reason with specificity, and for nonpayment the right to avoid eviction "
           "by payment.", "RSA 540:3", RENT_READ),
     claim("A possessory action for nonpayment is dismissed if the tenant pays, before the "
           "hearing, all rent due, other lawful charges, $15 liquidated damages and the filing "
           "fee and service charges; not more than 3 times within a 12-month period.",
           "RSA 540:9", RENT_READ),
     claim("The tenant files an appearance no later than the return day on the writ and an "
           "answer not more than 5 days after the return date; a notice of intent to appeal "
           "within 7 days of the notice of decision, paying rent as it comes due.",
           "RSA 540:13", RENT_READ),
     claim("Any tenant default precludes a discretionary stay; after judgment, the court may "
           "order that the tenant not be dispossessed until a date not later than 60 days, or "
           "not more than 75 days where the defendant proves a longer stay will not harm the "
           "landlord, the tenant paying the weekly former rent in advance.",
           "RSA 540:13-c", "2026-10-26")]
    + help_claims("legal_aid"),
    more=civics.faq(
        ("Do the deposit rules apply to every landlord?",
         "<p>The deposit rules apply to most landlords. They do not apply to someone who rents "
         "out a single-family home and owns no other rental property, or who rents units in a "
         "building of 5 units or fewer that they live in themselves, unless the tenant is 60 "
         "or older.</p>"),
        ("Do I get interest on my deposit?",
         "<p><b>It stays your money,</b> held in trust. If it is held for a year or longer, "
         "the landlord pays you the interest it earned.</p>"),
        ("Can I hold back rent until repairs are made?",
         "<p>If you are evicted for not paying rent, the court may refuse the eviction when "
         "the home has a serious health or safety violation that you reported in writing "
         "while you were not behind on rent, and the landlord did not fix it within 14 days. "
         "The court may require you to pay the rent into court meanwhile. Holding back rent is "
         "risky: talk to legal aid before you do.</p>"),
        ("How do I end a month-to-month tenancy myself?",
         "<p><b>Moving out yourself.</b> To end a month-to-month tenancy, give 30 days&rsquo; "
         "written notice. A victim of domestic violence, sexual assault or stalking can end a "
         "lease early, with written verification, if the abuse happened within the last 150 "
         "days, and must then leave within 30 days. For most rentals, a landlord may not end a "
         "tenancy solely because a tenant is a victim, once the tenant gives written "
         "verification.</p>"),
        ("What happens to things I leave behind?",
         "<p>After you leave, your landlord must store anything you left behind, with "
         "reasonable care, for 7 days, and let you take it without paying rent or storage "
         "fees.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Get help as early as you can, before a deadline passes. Your town or city can "
         "tell you whether it has a housing code and who enforces it. For an eviction, a "
         "lockout or a deposit:</p>"
         + helps("legal_aid"),
    see=[("Renting out a home: a landlord's rights and duties", "/guides/landlord-duties.html"),
         ("How to get help if you are homeless or may lose your home",
          "/guides/homelessness-help.html"),
         ("How to get help after domestic violence, sexual assault or stalking",
          "/guides/domestic-violence-help.html")],
    figures=[fig("$100", "RSA 540-A:6", "one month's rent or $100"),
             fig("30 days", "RSA 540-A:7", "within 30 days from the termination of the tenancy"),
             fig("10 days", "RSA 540-A:4", "within 10 days of service of process"),
             fig("5 units", "RSA 540-A:5", "building of 5 units or less"),
             fig("5 days", "RSA 540-A:6", "within 5 days of occupancy"),
             fig("7 days", "RSA 540-A:3", "within 7 days of receiving notice"),
             fig("14 days", "RSA 540:13-d", "within 14 days of the receipt"),
             fig("12 months", "RSA 540:2", "original term of which is 12 months or longer"),
             fig("60 days", "RSA 540:2", "at least 60 days in advance"),
             fig("4 units", "RSA 540:1-a", "containing a total of 4 dwelling units or fewer"),
             fig("6 months", "RSA 540:13-b", "within 6 months after"),
             fig("150 days", "RSA 540:11-b", "within the most recent 150 days"),
             fig("75", "RSA 540:13-c", "not more than 75 days"),
             fig("3 months", "RSA 540:14", "not more than 3 months' rent"),
             fig("$15", "RSA 540:9", "$15 liquidated damages"),
             fig("12-month", "RSA 540:9", "within a 12-month period")])

LANDLORD = guide(
    "landlord-duties", "Renting Out a Home: A Landlord's Rights and Duties",
    "What New Hampshire law asks of a landlord: security deposits, entering the home, repairs "
    "and minimum standards, ending a tenancy, and the only lawful way to evict, through the "
    "district court.",
    "A New Hampshire landlord ends a tenancy with a written eviction notice and, if the tenant "
    "stays, a case in the circuit court&rsquo;s district division: changing the locks, shutting "
    "off a utility or removing a tenant&rsquo;s belongings is against the law. Most landlords "
    "may hold a security deposit of no more than one month&rsquo;s rent or $100, whichever is "
    "more, and must return it within 30 days of the end of the tenancy, with an itemized list "
    "of any deductions. You must keep the home free of the hazards the law lists, and you may "
    "enter without the tenant&rsquo;s consent only for emergency repairs or with a court "
    "order.",
    [ask("What do you need to do?",
         [("Take a security deposit",
           "At most one month&rsquo;s rent or $100, whichever is more, with a receipt."),
          ("Get into the unit",
           "With the tenant&rsquo;s consent, after adequate notice; without it, only for "
           "emergency repairs or with a court order."),
          ("End a tenancy",
           "Serve a written eviction notice; if the tenant stays, file a case in the district "
           "court."),
          ("Close out after a tenant leaves",
           "Return the deposit within 30 days, and store belongings left behind for 7 days.")]),
     box("Never lock a tenant out, shut off a utility or remove belongings: only the court and "
         "the sheriff can.")],
    [step("Before you rent",
          "<p><b>Know which rules apply to your property.</b> A residential rental is "
          "&ldquo;restricted property&rdquo;, where you need a reason the law lists to end a "
          "tenancy, unless it is one of the exceptions: a single-family house, if you own no "
          "more than 3; a unit in a building of 4 units or fewer that you live in; or a "
          "single-family house a bank or other lender took through foreclosure.</p>",
          law=["RSA 540:1-a", "RSA 540:1-b", "RSA 540-A:3"]),
     step("Security deposits",
          "<p>These rules apply unless you rent out a single-family home and own no other "
          "rental property, or rent units in a building of 5 units or fewer that you live in, "
          "and even then they apply to a tenant 60 or older.</p>"
          "<ul><li><b>The limit:</b> one month&rsquo;s rent or $100, whichever is more.</li>"
          "<li><b>A signed receipt</b> stating the amount and where it is held, unless the "
          "tenant paid by check, and written notice that the tenant may list conditions needing "
          "repair within 5 days of moving in.</li>"
          "<li><b>Hold it in trust,</b> apart from your own money, in a New Hampshire bank or "
          "credit union, or post a bond with the town or city clerk. Held a year or longer, it "
          "earns the tenant interest.</li>"
          "<li><b>Return it within 30 days</b> of the end of the tenancy, with any interest. "
          "You may deduct the cost of damage beyond reasonable wear and tear, unpaid rent and "
          "other lawful charges, with a written, itemized list and evidence of the repairs, "
          "such as receipts or estimates.</li></ul>"
          "<p>A landlord who does not return a deposit as required can owe the tenant twice "
          "the amount.</p>",
          law=["RSA 540-A:5", "RSA 540-A:6", "RSA 540-A:7", "RSA 540-A:8"]),
     step("Entering the home, repairs and minimum standards",
          "<p><b>Entry.</b> Enter only with the tenant&rsquo;s consent, given at a reasonable "
          "time after notice that is adequate under the circumstances. Without consent, you "
          "may enter only to make emergency repairs, or with a court order; if a tenant "
          "refuses reasonable access, you can ask the district court for one.</p>"
          "<p><b>Minimum standards.</b> Where the town has no housing code of its own, the law "
          "forbids keeping a rental with an untreated insect, rodent or bed bug infestation, "
          "defective plumbing or sewage back-up, electrical hazards, a leaking roof or walls, "
          "falling plaster, large holes, unsound porches, stairs or railings, garbage piling "
          "up in common areas, too little water or broken hot water equipment, gas leaks, or "
          "heat that cannot keep every room at an average of at least 65 degrees. Towns with a "
          "housing code enforce their own.</p>"
          "<p>Investigate a tenant&rsquo;s report of bed bugs or other pests within 7 days, and "
          "take reasonable steps to remove them. A tenant who reported a serious violation in "
          "writing, and was not behind on rent, has a defense to an eviction for nonpayment if "
          "you did not fix it within 14 days, unless the tenant, the tenant&rsquo;s household or "
          "guests caused it, or extreme weather or the tenant&rsquo;s refusal of access "
          "prevented the repair.</p>",
          law=["RSA 540-A:3", "RSA 540-A:4", "RSA 48-A:14", "RSA 540:13-d"]),
     step("Reasons and notice",
          "<p><b>The reasons.</b> For restricted property: unpaid rent, substantial damage, "
          "breaking a material term of the lease, behavior that threatens others&rsquo; health "
          "or safety, or other good cause, which can be a legitimate business or economic "
          "reason. If the cause is the tenant&rsquo;s own conduct, first give a written warning "
          "that it would be grounds for eviction. A lease of 12 months or longer, counting "
          "renewals, can end at its term if you give written notice at least 60 days before "
          "that you will not renew it, and file any eviction within 6 months of the lease "
          "ending. A tenant who refuses a rent "
          "increase can be evicted for good cause only if you gave written notice of the amount "
          "and the date at least 30 days ahead.</p>"
          "<p><b>The notice.</b> An eviction notice is in writing and states the reason "
          "specifically. It allows 7 days for unpaid rent, substantial damage or a threat to "
          "health or safety, and 30 days for other reasons. For unpaid rent, serve a demand "
          "for rent too, and the notice must tell the tenant of any right to pay and stay, which "
          "a tenant may use no more than 3 times in 12 months. "
          "Anyone can serve them, in hand or at the tenant&rsquo;s home; the court has the "
          "forms.</p>"
          "<p><b>What you may not do.</b> You may not evict to retaliate against a tenant who "
          "reported a code violation, went to court under the tenant protection law, or met "
          "with other tenants, unless the tenant owes a week&rsquo;s rent or more; nor end a "
          "tenancy solely because a tenant or a member of the household is a victim of domestic "
          "violence, sexual assault or stalking, once the tenant gives you written verification "
          "of it.</p>",
          law=["RSA 540:2", "RSA 540:3", "RSA 540:5", "RSA 540:9", "RSA 540:13-a",
               "RSA 540:13-b"]),
     step("Going to court",
          "<p>If the tenant has not left when the notice runs out, buy a Landlord/Tenant Writ "
          "from the circuit court&rsquo;s district division, complete it, file it and pay the "
          "filing fee. Every residential eviction also needs the court&rsquo;s Affidavit of "
          "Compliance with Federal Law, filed with the writ. You deliver the writ to the sheriff, "
          "who serves it, and it is returnable 7 days after service. You may claim unpaid rent in the same case, up to "
          "$1,500, and sue separately for more. Before any case, the court&rsquo;s free Eviction Diversion Program offers a "
          "mediator.</p>"
          "<p>In a case only for unpaid rent, the tenant can end it by paying, before the "
          "hearing, the rent owed, other lawful charges, $15 and your filing and service costs, "
          "up to 3 times in a 12-month period. You may accept back rent during the case without "
          "creating a new tenancy, if you tell the tenant in writing that you are going ahead "
          "with the eviction.</p>"
          "<p>If you win, the court issues a writ of possession, and the sheriff, not you, "
          "removes the tenant. Unless the tenant defaulted, the court may give the tenant up to "
          "60 days, or 75 in limited cases the tenant must prove, with rent paid weekly in "
          "advance.</p>",
          actions=[("Landlord and tenant cases (Judicial Branch)", COURTS_LLT)],
          law=["RSA 540:9", "RSA 540:13", "RSA 540:13-c", "RSA 540:14", "RSA 540-A:4"]),
     step("After the tenant leaves",
          "<p>Return the security deposit, with any interest and an itemized list of "
          "deductions, within 30 days. If the tenant gave you no new address, you are not "
          "liable for missing the deadline, and a deposit unclaimed after 6 months becomes "
          "yours.</p>"
          "<p>Store anything the tenant left behind, with reasonable care, for 7 days after "
          "they leave, and let them take it back without paying rent or storage fees. After "
          "that, you may dispose of it.</p>",
          law=["RSA 540-A:7", "RSA 540-A:8", "RSA 540-A:3"])],
    [("Landlord/Tenant, District Division (Judicial Branch)", COURTS_LLT),
     ("Actions Against Tenants, RSA 540", "/laws/540"),
     ("Prohibited Practices and Security Deposits, RSA 540-A", "/laws/540-a"),
     ("Housing Standards, RSA 48-A", "/laws/48-a")],
    ["540", "540-A", "48-A"],
    [# The Judicial Branch's page, as the homelessness guide read it on 24
     # October 2026.
     claim("The Eviction Diversion Program: free mediation before a court case, voluntary, no "
           "rights given up; a tenant files an Appearance by the return date on the "
           "Landlord/Tenant Writ to be heard; the return date is not the hearing; trial within "
           "about 10 days of an Appearance; failing to file or appear brings a Notice of "
           "Default, and the Writ of Possession does not issue for at least 5 business days; "
           "after judgment for the landlord, 7 days to file a Notice of Intent to Appeal, with "
           "weekly rent paid during the appeal.", COURTS_LLT, HL_READ),
     # The same page in the person's printout (evictions1), read 26 October 2026.
     claim("Landlords are required to submit an Affidavit of Compliance with Federal Law "
           "approved by the Circuit Court prior to requesting a Landlord/Tenant Writ in all "
           "residential evictions; the Landlord/Tenant Writ must be purchased from the court, "
           "completed (except for the return date), filed with the court, and filing fee paid "
           "prior to service of process; it is the responsibility of the landlord to deliver the "
           "completed Landlord/Tenant Writ to the sheriff for service; landlords or tenants in "
           "doubt as to the legal requirements should consult with an attorney.", COURTS_LLT,
           HL_READ),
     # The statutes, as this site's Laws pages print them, read 25 October 2026.
     claim("Nonrestricted property: single-family houses whose owner owns not more than 3, "
           "units in an owner-occupied building of 4 dwelling units or fewer, and single-family "
           "houses acquired by banks or other mortgagees through foreclosure; restricted "
           "property is all other residential rental property.", "RSA 540:1-a", RENT_READ),
     claim("An owner of restricted property files with the town or city clerk, within 30 days "
           "of becoming the owner, the name, address and telephone number of a person within "
           "the state authorized to accept service of process; it may be the owner.",
           "RSA 540:1-b", RENT_READ),
     claim("No utility interruption (I), denial of access to the premises (II) or to the "
           "tenant's property (III) other than through proper judicial process; entry only "
           "with prior consent, for emergency repairs (IV), or with a court order (V-d); a "
           "tenant may not refuse access at a reasonable time after adequate notice (V); "
           "investigate a reported infestation within 7 days and take reasonable measures "
           "(V-a); store a vacated tenant's property with reasonable care for 7 days, then "
           "dispose of it (VII); disclose an application fee in writing and return the excess "
           "within 30 days (VIII); allow at least one non-electronic form of payment (X).",
           "RSA 540-A:3", RENT_READ),
     claim("A petition in the district court to enforce RSA 540-A:2 and 540-A:3; the civil "
           "remedies of RSA 358-A:10 with costs and reasonable attorney's fees; landlord "
           "damages for an unlawful lock-out where the premises have been re-let not less "
           "than $3,000.", "RSA 540-A:4", RENT_READ),
     claim("A landlord for this subdivision excludes a person who rents a single-family "
           "residence and owns no other rental property, or rents units in an owner-occupied "
           "building of 5 units or less, except for a unit occupied by a person 60 years of "
           "age or older.", "RSA 540-A:5", RENT_READ),
     claim("No security deposit in excess of one month's rent or $100, whichever is greater; a "
           "signed receipt stating the amount and where held, not required when paid by check; "
           "notice that conditions needing repair be given in writing within 5 days of "
           "occupancy; deposits held in trust, not mingled with the landlord's money, in a New "
           "Hampshire bank, savings and loan or credit union, or a bond posted with the town or "
           "city clerk; turned over on a sale with notice by registered or certified mail; "
           "interest on a deposit held one year or longer.", "RSA 540-A:6", RENT_READ),
     claim("Return the security deposit and interest within 30 days from the termination of the "
           "tenancy; deduct damages excluding reasonable wear and tear, with a written, "
           "itemized list and satisfactory evidence of repair such as receipts and estimates; "
           "deduct unpaid rent and lawful charges with an itemized list.", "RSA 540-A:7",
           RENT_READ),
     claim("A landlord who does not comply with RSA 540-A:6, IV or 540-A:7 is liable for twice "
           "the deposit plus interest, less lawful charges; not liable if the tenant failed to "
           "give a new address; unclaimed deposits after 6 months become the landlord's.",
           "RSA 540-A:8", RENT_READ),
     claim("In a municipality without its own ordinance, no landlord shall maintain premises "
           "infested by insects, rodents or bed bugs without an inspection program; with "
           "defective plumbing or sewage back-up; electrical dangers; leaking roof or walls; "
           "falling plaster; substantial holes; unsound porches, stairs or railings; garbage "
           "in common areas; inadequate water or hot water equipment; gas leaks; or heating "
           "not capable of a temperature of at least an average of 65 degrees.",
           "RSA 48-A:14", RENT_READ),
     claim("No possessory action for nonpayment if the premises are in substantial violation "
           "of RSA 48-A or local codes materially affecting habitability, the tenant gave notice "
           "while not in arrears, and the landlord failed to correct within 14 days; provided "
           "the violations were not caused by the tenant, the tenant's family or others on the "
           "premises with the tenant's consent, and repairs were not prevented by extreme "
           "weather or the tenant's failure to allow reasonable access.",
           "RSA 540:13-d", RENT_READ),
     claim("Restricted property may be terminated only for nonpayment, substantial damage, "
           "failure to comply with a material term, behavior adversely affecting health or "
           "safety, other good cause, and the other listed reasons; written notice before an "
           "eviction for other good cause based on the tenant's conduct; a lease of 12 months "
           "or longer, or renewed to 12 months or longer, at its expiration with written notice "
           "at least 60 days in advance, provided the landlord has filed a possessory action "
           "within 6 months of the lease expiring; "
           "refusal of a rent increase is good cause if written notice came at least 30 days "
           "prior; other good cause includes any legitimate business or economic reason; no "
           "termination solely because a tenant or household member is a victim of domestic "
           "violence, sexual assault or stalking, provided the victim gives written "
           "verification.", "RSA 540:2", RENT_READ),
     claim("For residential tenancies, 30 days' notice; 7 days' notice for nonpayment, "
           "substantial damage, behavior affecting health or safety; the reason stated with "
           "specificity; for nonpayment, notice of the right, if any, to avoid eviction by "
           "payment.", "RSA 540:3", RENT_READ),
     claim("A demand for rent or eviction notice may be served by any person, personally or at "
           "the last and usual place of abode; the district court provides forms.",
           "RSA 540:5", RENT_READ),
     claim("Except where the tenant owes a week's rent or more, a defense that the possessory "
           "action retaliates for reporting a violation, initiating an action under RSA 540-A, "
           "or meeting with other tenants.", "RSA 540:13-a", RENT_READ),
     claim("A rebuttable presumption of retaliation when a possessory action, an increase in "
           "rent or a substantial alteration in the terms is instituted within 6 months after "
           "the protected act.", "RSA 540:13-b", RENT_READ),
     claim("A possessory action for nonpayment is dismissed if the tenant pays, before the "
           "hearing, all rent due, other lawful charges, $15 liquidated damages and the filing "
           "fee and service charges; not more than 3 times within a 12-month period.",
           "RSA 540:9", RENT_READ),
     claim("The writ is returnable 7 days from service by the sheriff; a claim for unpaid rent, "
           "a money judgment limited to a maximum of $1,500; accepting the arrearage during "
           "the action without creating a new tenancy, with written notice of the intent to "
           "proceed.", "RSA 540:13", RENT_READ),
     claim("Any tenant default precludes a discretionary stay; after judgment, the court may "
           "order that the tenant not be dispossessed until a date not later than 60 days, or "
           "not more than 75 days where the defendant proves a longer stay will not harm the "
           "landlord, the tenant paying the weekly former rent in advance.",
           "RSA 540:13-c", "2026-10-26"),
     claim("A writ of possession authorizes the sheriff to remove the defendant from the "
           "premises.", "RSA 540:14", RENT_READ)]
    + help_claims("lawyer"),
    more=civics.faq(
        ("Do I need someone to accept court papers for me?",
         "<p>If you own restricted property, file a statement with the town or city clerk, "
         "within 30 days of becoming the owner, naming a person in New Hampshire who can "
         "accept court papers for you; it may be you.</p>"),
        ("Can I charge an application fee, or require rent online?",
         "<p>Before you charge an application fee, tell the applicant in writing how much it "
         "is and whether you require a background or credit check. If you do not rent to "
         "them, return whatever is beyond the actual cost of those checks and reasonable "
         "costs within 30 days. You may not require rent to be paid only electronically: "
         "accept at least one other way.</p>"),
        ("What if I sell the property?",
         "<p><b>If you sell the property,</b> turn the deposits over to the buyer and tell "
         "each tenant by registered or certified mail.</p>"),
        ("What does a lockout or a utility shut-off cost a landlord?",
         "<p>A lockout, a utility shut-off or removing a tenant&rsquo;s things instead of "
         "going to court can cost you the tenant&rsquo;s damages, costs and attorney&rsquo;s "
         "fees, and no less than $3,000 if you have already re-let the home.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>The district court has the forms for a demand for rent, an eviction notice and a "
         "Landlord/Tenant Writ. It advises landlords in doubt about the law&rsquo;s "
         "requirements to consult a lawyer:</p>"
         + helps("lawyer"),
    see=[("Your rights as a tenant", "/guides/tenant-rights.html"),
         ("How to appeal your property tax assessment", "/guides/property-tax-abatement.html")],
    figures=[fig("$100", "RSA 540-A:6", "one month's rent or $100"),
             fig("30 days", "RSA 540-A:7", "within 30 days from the termination of the tenancy"),
             fig("7 days", "RSA 540-A:3", "for a period of 7 days"),
             fig("4 units", "RSA 540:1-a", "containing a total of 4 dwelling units or fewer"),
             fig("5 units", "RSA 540-A:5", "building of 5 units or less"),
             fig("5 days", "RSA 540-A:6", "within 5 days of occupancy"),
             fig("14 days", "RSA 540:13-d", "within 14 days of the receipt"),
             fig("12 months", "RSA 540:2", "original term of which is 12 months or longer"),
             fig("60 days", "RSA 540:2", "at least 60 days in advance"),
             fig("$1,500", "RSA 540:13", "a maximum of $1,500"),
             fig("$15", "RSA 540:9", "$15 liquidated damages"),
             fig("12-month", "RSA 540:9", "within a 12-month period"),
             fig("12 months", "RSA 540:9", "3 times within a 12-month period"),
             fig("75", "RSA 540:13-c", "not more than 75 days"),
             fig("$3,000", "RSA 540-A:4", "shall not be less than $3,000"),
             fig("6 months", "RSA 540-A:8", "after 6 months from the termination")])

GUIDES += [TENANT, LANDLORD]


# ---------------------------------------------------------------------------
# STORMS, POWER OUTAGES AND OTHER EMERGENCIES (the person, 24 October 2026).
# From FEMA's Ready.gov pages on a supply kit, power outages and winter
# weather, read on 24 October 2026 through the session's web reader (Ready.gov
# refuses this machine's own requests but answered that), the National
# Weather Service's page on winter watches and warnings, read directly, and
# 211 New Hampshire. New Hampshire's own alert system, NH Alerts, is the
# Department of Safety's, whose pages refuse a cloud session: they and ReadyNH
# were read in the PDFs the person printed and sent the same day. Neither page
# calls NH Alerts free, so the guide does not.
# Every safety instruction is the federal page's own, in plain words; none is
# this site's advice.
# ---------------------------------------------------------------------------
WX_READ = "2026-10-24"
NH_ALERTS = "https://www.desc.dos.nh.gov/resources/nh-alerts"
READYNH = "https://www.readynh.gov/"
READY_KIT = "https://www.ready.gov/kit"
READY_POWER = "https://www.ready.gov/power-outages"
READY_WINTER = "https://www.ready.gov/winter-weather"
NWS_WINTER = "https://www.weather.gov/safety/winter-ww"

WEATHER = guide(
    "storms-and-emergencies", "How to Prepare for Storms, Power Outages and Other Emergencies",
    "Getting New Hampshire's emergency alerts, keeping supplies at home and in the car, staying "
    "safe in a power outage or winter storm, and where to find a warm place or help.",
    "Sign up for NH Alerts, the state&rsquo;s official emergency alerts, and keep enough food, "
    "water and supplies at home to last several days. In a storm or a power outage, never run "
    "a generator, grill or camp stove indoors, and never heat your home with a gas stove or "
    "oven: carbon monoxide can kill. If you need a warm place, ask your town or city which "
    "warming places are open; for housing, utility help and more, call 2-1-1. In an "
    "emergency, call 911.",
    [box("Sign up for NH Alerts, and learn what a watch and a warning mean."),
     box("Keep supplies for several days at home, and a kit in your car."),
     ask("Has the power gone out?",
         [("Yes", "Keep the refrigerator and freezer closed. Use a generator only outdoors."),
          ("Yes, and you need a warm place", "Ask your town about warming places, or call "
                                             "2-1-1 for other help.")])],
    [step("Get alerts",
          "<p><b>NH Alerts</b> is New Hampshire&rsquo;s official emergency notification system. "
          "It sends alerts about local weather, evacuations, AMBER Alerts, hazardous materials "
          "and other emergencies by phone call, text message, email or app. Create an account to "
          "choose how you are reached; to get text messages, add your mobile number as a text "
          "(SMS) contact. Or download the Genasys Protect app, which shows alerts where you are "
          "without an account.</p>"
          "<p><b>ReadyNH.gov</b> is the state&rsquo;s official source of information during "
          "emergencies, with what to do before, during and after floods, extreme cold and heat, "
          "power outages, winter storms and other disasters.</p>"
          "<p>The National Weather Service&rsquo;s alerts tell you how serious a storm is:</p>"
          "<ul><li><b>Advisory: be aware.</b> Winter weather is expected; be ready for "
          "difficult driving.</li>"
          "<li><b>Watch: be prepared.</b> A significant storm is possible.</li>"
          "<li><b>Warning: take action.</b> Dangerous weather is coming or has begun. Under a "
          "winter storm warning, find shelter right away and delay travel.</li></ul>",
          actions=[("Sign up for NH Alerts", NH_ALERTS), ("ReadyNH", READYNH),
                   ("Watches and warnings (National Weather Service)", NWS_WINTER)]),
     step("Keep supplies at home and in the car",
          "<p>After an emergency you may need to manage on your own for several days. A basic "
          "kit includes:</p>"
          "<ul><li>water, one gallon per person per day, for several days;</li>"
          "<li>at least a several-day supply of food that will not spoil, and a manual can "
          "opener;</li>"
          "<li>a flashlight, a battery-powered or hand-crank radio, and extra batteries;</li>"
          "<li>a first aid kit and a whistle to signal for help;</li>"
          "<li>a cell phone with chargers and a backup battery.</li></ul>"
          "<p>Add what your household needs, such as medicines. Store it all in one or two "
          "containers that are easy to carry, and replace anything that expires.</p>"
          "<p>In the car, keep jumper cables, sand, a flashlight, warm clothes, blankets, "
          "bottled water and snacks, and keep the gas tank full.</p>",
          actions=[("Build a kit (Ready.gov)", READY_KIT)]),
     step("In a power outage",
          "<ul><li><b>Carbon monoxide can kill</b>, and you cannot see or smell it. Use a "
          "generator, camp stove or grill only outdoors, at least 20 feet from windows, doors and "
          "attached garages. Never heat your home with a gas stove or oven. Have carbon monoxide "
          "detectors with battery backup on every level of your home.</li>"
          "<li><b>Keep the refrigerator and freezer closed</b>, so food stays cold longer.</li>"
          "<li><b>Plan ahead for medicines that need refrigeration</b> and for medical devices "
          "that need power.</li>"
          "<li><b>If it is very cold or very hot,</b> go to a place in your community with power. "
          "Ask local officials which warming or cooling places are open.</li></ul>",
          actions=[("Power outages (Ready.gov)", READY_POWER)]),
     step("In a winter storm",
          "<ul><li>Stay off the roads if you can. If you are trapped in your car, stay "
          "inside it.</li>"
          "<li>Avoid overexertion when shoveling or walking in snow.</li>"
          "<li>Watch for frostbite and hypothermia: the questions below say what to do.</li></ul>",
          actions=[("Winter weather (Ready.gov)", READY_WINTER)]),
     step("If you need a warm place or other help",
          "<p>Ask your town or city which warming places are open. Call <b>2-1-1</b>, at any "
          "hour, for housing, utility help and other services near you. In an emergency, call "
          "911.</p>"
          "<p>If you are running out of heating fuel or have no heat, call your community "
          "action agency: fuel assistance can arrange an emergency delivery. The guide to help "
          "with heating and electric bills has the agencies.</p>",
          actions=[("2-1-1 New Hampshire", NH211_HOME)])],
    [("NH Alerts (Department of Safety)", NH_ALERTS),
     ("ReadyNH", READYNH),
     ("Build a kit (Ready.gov, FEMA)", READY_KIT),
     ("Power outages (Ready.gov, FEMA)", READY_POWER),
     ("Winter weather (Ready.gov, FEMA)", READY_WINTER),
     ("Winter weather watches, warnings and advisories (National Weather Service)", NWS_WINTER),
     ("2-1-1 New Hampshire", NH211_HOME)],
    [],
    # NH Alerts and ReadyNH, read in the person's printouts of 24 October 2026.
    [claim("NH Alerts is the State's official emergency and public notification system, by "
           "phone calls, text messages, emails and app notifications, for local weather "
           "impacts, evacuations, AMBER Alerts, missing persons, hazardous materials incidents "
           "and severe traffic situations; registering lets you choose how you are contacted, "
           "and for texts add your mobile number as an SMS contact; the Genasys Protect app "
           "gives location-based alerts without an account; anyone who lives, works, owns "
           "property or regularly visits an area where NH Alerts are used can sign up, and may "
           "register for areas where loved ones live.", NH_ALERTS, WX_READ),
     claim("ReadyNH.gov is New Hampshire's official source for information during state "
           "emergencies: sign up for NH Alerts, and learn what to do before, during and after a "
           "disaster, among them blackouts and power outages, extreme cold and heat, floods and "
           "winter storms.", READYNH, WX_READ),
     claim("After an emergency you may need to survive on your own for several days; a basic "
           "kit: water, one gallon per person per day for several days; at least a several-day "
           "supply of non-perishable food; a battery-powered or hand crank radio; a flashlight; "
           "a first aid kit; extra batteries; a whistle; a manual can opener; a cell phone with "
           "chargers and a backup battery; additional supplies such as medications; one or two "
           "easy-to-carry containers; replace expired items.", READY_KIT, WX_READ),
     claim("Keep freezers and refrigerators closed; generators, camp stoves or charcoal grills "
           "outdoors and at least 20 feet away from windows, doors and attached garages; never "
           "heat with a gas stovetop or oven; carbon monoxide is colorless and odorless and can "
           "kill; carbon monoxide detectors with battery backup on every level; the refrigerator "
           "keeps food cold for about 4 hours and a full freezer about 48 hours; throw away "
           "food at 40 degrees or higher for 2 hours or more; when in doubt, throw it out; "
           "plans for refrigerated medicines and power-dependent medical devices; check with "
           "local officials about heating and cooling locations; go to a community location "
           "with power if heat or cold is extreme.", READY_POWER, WX_READ),
     claim("A Winter Storm Warning is issued when hazardous winter weather is imminent or "
           "occurring; under a winter storm warning, find shelter right away; NOAA Weather Radio and the "
           "Emergency Alert System give alerts; a car kit of jumper cables, sand, a flashlight, "
           "warm clothes, blankets, bottled water and snacks, and a full tank; stay off roads, "
           "and if trapped in a car stay inside; avoid overexertion shoveling and walking in "
           "snow; frostbite: loss of feeling and color, go to a warm room, soak in warm water, "
           "do not massage or use a heating pad; hypothermia: below 95 degrees is an emergency, "
           "warm room, warm the center first, keep dry and wrapped including head and neck.",
           READY_WINTER, WX_READ),
     claim("Warnings: take action; a Winter Storm Warning for a significant winter weather "
           "event, delay travel; Watches: be prepared, a Winter Storm Watch when conditions "
           "favor a significant winter storm; Advisories: be aware, be prepared for winter "
           "driving conditions.", NWS_WINTER, WX_READ),
     claim("211 NH connects residents to resources 24 hours, 365 days a year, for housing, "
           "utilities and more; 911 for emergencies.", NH211_HOME, WX_READ),
     ours("The heating guide says fuel assistance can arrange an emergency fuel delivery "
          "through the community action agency.", "/guides/heating-and-electric-help.html",
          WX_READ)],
    more=civics.faq(
        ("Who can sign up for NH Alerts?",
         "<p>Anyone who lives, works, owns property or often visits where NH Alerts is used can "
         "sign up, and you can add the places your family lives.</p>"),
        ("Are there other ways to get alerts?",
         "<p>A NOAA Weather Radio and the Emergency Alert System on radio and TV give alerts "
         "too.</p>"),
        ("How long does food stay safe in a power outage?",
         "<p>A refrigerator keeps food cold for about 4 hours, and a full freezer for about 48 "
         "hours. Throw out food that has been at 40 degrees or warmer for 2 hours or more: when "
         "in doubt, throw it out.</p>"),
        ("How do I recognize and treat frostbite?",
         "<p><b>Frostbite</b> causes loss of feeling and color. Go "
         "to a warm room and soak in warm water; do not massage the skin or use a heating "
         "pad.</p>"),
        ("What is hypothermia, and what should I do?",
         "<p><b>Hypothermia</b>, a body temperature below 95 degrees, is an emergency. Go to a "
         "warm room, warm the center of the body first, and keep dry and wrapped in warm "
         "blankets, including the head and neck.</p>"))
    + "<h2>Who Can Help</h2>"
         "<p>2-1-1 New Hampshire, at any hour, for housing, utility help and other help near "
         "you, and your town or city for local warming places and storm information. In an "
         "emergency, call 911.</p>",
    see=[("How to get help with heating and electric bills", "/guides/heating-and-electric-help.html"),
         ("How to get help if you are homeless or may lose your home", "/guides/homelessness-help.html")],
    figures=[fig("4 hours", READY_POWER, "about 4 hours"),
             fig("48 hours", READY_POWER, "about 48 hours"),
             fig("2 hours", READY_POWER, "2 hours or more")])

GUIDES += [WEATHER]


# ---------------------------------------------------------------------------
# SCAMS AND CONSUMER COMPLAINTS (the person, 25 October 2026: "Write all
# three know your rights guides too", of "scams and consumer complaints").
# What a buyer may do rests on the law, read on 25 October 2026 as the Laws
# pages print it: the Consumer Protection Act (RSA 358-A) for what is unfair
# or deceptive, who enforces it and what a court may award; the home
# solicitation sale rules (RSA 361-B) for cancelling a sale made away from a
# store; and the Prizes and Gifts Act (RSA 358-O) for the "you have won"
# letter or call. The Attorney General's Consumer Protection and Antitrust
# Bureau's pages refuse this machine; their addresses come from a web search
# and their claims wait for the person's printouts. The FTC's consumer pages
# answer this machine with an empty page, so the guide does not cite them.
# ---------------------------------------------------------------------------
CP_READ = "2026-10-25"
CP_AG_READ = "2026-10-26"            # the person's printouts of doj.nh.gov
AG_CPB = "https://www.doj.nh.gov/bureaus/consumer-protection-antitrust-bureau"
AG_COMPLAINT = "https://www.doj.nh.gov/consumer/complaints"

CONSUMER = guide(
    "consumer-rights", "Scams and Consumer Complaints: Your Rights as a Buyer",
    "How to spot a scam, how to cancel a sale made at your door, your rights with gift "
    "certificates, and how to complain to the Attorney General or take a business to court "
    "in New Hampshire.",
    "New Hampshire&rsquo;s Consumer Protection Act forbids unfair and deceptive business "
    "practices, and the Attorney General&rsquo;s Consumer Protection and Antitrust Bureau "
    "enforces it. If a seller came to your door, you can usually cancel the sale until midnight "
    "of the third business day after it. A prize you are told you have won must cost you "
    "nothing. If a business "
    "cheated you, you can complain to the Bureau, and you can take the business to court "
    "yourself.",
    [ask("What happened?",
         [("You bought something from a seller at your door",
           "Cancel in writing by midnight of the third business day."),
          ("A business misled or cheated you",
           "Complain to the Attorney General&rsquo;s Consumer Protection Bureau."),
          ("A call or letter says you won a prize, for a fee",
           "A prize the law allows costs you nothing. Do not pay.")]),
     box("You can also take the business to court yourself, unless the sale was more than 3 "
         "years before you knew, or should have known, what it did.")],
    [step("Know what the law forbids",
          "<p>The Consumer Protection Act makes it unlawful for a business to use any unfair or "
          "deceptive practice. Among the examples the law lists:</p>"
          "<ul><li>claiming a product or service has an approval, a certification, a quality or "
          "a benefit it does not have, or that the business is connected with someone it is "
          "not;</li>"
          "<li>selling used, reconditioned or secondhand goods as new;</li>"
          "<li>advertising something with no intent to sell it as advertised;</li>"
          "<li>false or misleading claims about a sale price or a price reduction.</li></ul>",
          law=["RSA 358-A:2"]),
     step("A prize should never cost you anything",
          "<p>If a seller tells you that you have won something, with words such as "
          "&ldquo;Congratulations&rdquo; or &ldquo;You have won&rdquo;, the law requires the "
          "prize to be yours without any obligation, delivered at no cost to you within 10 days. "
          "A &ldquo;prize&rdquo; that asks you to pay a handling, registration, redemption or "
          "delivery fee, or to buy something first, is not one the law allows. Do not pay, and "
          "report it (see &ldquo;Complain to the Attorney General&rdquo;, below).</p>",
          law=["RSA 358-O:3", "RSA 358-O:4"]),
     step("Cancel a sale made at your door",
          "<p>A sale of goods or services priced at $150 or more, made anywhere other than the "
          "seller&rsquo;s permanent place of business, such as at your home, is a <b>home "
          "solicitation sale</b>. You may cancel it until <b>midnight of the third business "
          "day</b> after the sale. The seller must give you a receipt or contract that says so, "
          "with its name and address.</p>"
          "<p>To cancel, mail the seller a written notice, preferably by certified or registered "
          "mail, or return the goods in person within that time. The seller must then return, "
          "within 15 days, everything you paid, any trade-in, and any note you signed. If the "
          "seller had already done work that changed your property, you get all your money "
          "back, or, if it can reasonably be done, you may ask instead for the property to be put "
          "back as it was. The seller "
          "must come for its goods or pay to have them returned, and once it has refunded you, "
          "you must let it have them back within the same 15 days. If it makes no effort to get "
          "them back within 90 days of the sale, they are yours.</p>",
          law=["RSA 361-B:1", "RSA 361-B:2", "RSA 361-B:3"]),
     step("Gift certificates of $250 or less do not expire",
          "<p>A gift certificate with a face value of $250 or less may not carry an expiration "
          "date, and no gift certificate may lose value to a dormancy fee or any other service "
          "charge. Season passes are not covered.</p>",
          law=["RSA 358-A:2"]),
     step("Complain to the Attorney General",
          "<p>The Attorney General&rsquo;s <b>Consumer Protection and Antitrust Bureau</b> "
          "enforces the Consumer Protection Act. It can ask a court to stop a business&rsquo;s "
          "unlawful practice and to order money or property returned to the people it harmed.</p>"
          "<p>A complaint is made in writing, on the Bureau&rsquo;s consumer complaint form: "
          "online, after you create an account with the State for filing forms, or on the "
          "paper form, mailed or emailed. Give as much detail as you can, with every paper that "
          "bears on it, such as a car dealer&rsquo;s paperwork. An attorney reviews it and may "
          "send it to the business to answer in writing. It is not a formal legal process, it "
          "can take time, and it does not guarantee an answer or a resolution; the Bureau "
          "cannot represent you or give you legal advice. If you are not satisfied, consider a "
          "private lawyer or small claims court.</p>",
          actions=[("File a consumer complaint (Attorney General)", AG_COMPLAINT)],
          law=["RSA 358-A:4", "RSA 358-A:3"]),
     step("Take the business to court",
          "<p>You can sue a business that used an unfair or deceptive practice against you. If "
          "you win, the court awards your actual losses or $1,000, whichever is greater, and "
          "two to three times that if the business knew it was breaking the law, plus your court "
          "costs and reasonable attorney&rsquo;s fees. An agreement that gives up this right does "
          "not hold. The law does not reach a transaction more than 3 years before you knew, or should have "
          "known, what the business did.</p>"
          "<p>A lawyer can tell you whether you have a case (below).</p>",
          law=["RSA 358-A:10", "RSA 358-A:3"])],
    [("Consumer Protection and Antitrust Bureau (Attorney General)", AG_CPB),
     ("File a Consumer Complaint (Attorney General)", AG_COMPLAINT),
     ("Regulation of Business Practices for Consumer Protection, RSA 358-A", "/laws/358-a"),
     ("Prizes and Gifts Act, RSA 358-O", "/laws/358-o"),
     ("Retail Selling, RSA 361-B", "/laws/361-b")],
    ["358-A", "358-O", "361-B"],
    [# The statutes, as the Laws pages print them, read on 25 October 2026.
     claim("Unlawful: any unfair or deceptive act or practice in trade or commerce, including "
           "representing that goods or services have sponsorship, approval, characteristics or "
           "benefits they do not have, or an affiliation the person does not have; representing "
           "goods as new if deteriorated, reconditioned, used or secondhand; advertising with "
           "intent not to sell as advertised; false or misleading statements of fact concerning "
           "price reductions; gift certificates having a face value of $250 or less with "
           "expiration dates; dormancy fees or other service charges reducing a gift "
           "certificate; not applying to season passes.", "RSA 358-A:2", CP_READ),
     claim("A seller stating a post office box, a mail-receiving street address or an "
           "answering-service number in its advertising must disclose its legal name, the "
           "street address from which business actually is conducted, and a telephone number "
           "for customer inquiries and complaints; except retail premises open to the public.",
           "RSA 361-B:2-a", CP_READ),
     claim("No person shall represent that another has won anything of value unless it is "
           "given without obligation and delivered at no expense to the recipient within 10 "
           "days; \"Congratulations\" or \"You have won\" is such a representation; a handling "
           "charge includes promotional, redemption, registration fees or delivery costs.",
           "RSA 358-O:3", CP_READ),
     claim("A chance to win must disclose on whose behalf the promotion is conducted and all "
           "material conditions; in writing, each prize's retail value, the number to be "
           "awarded and the odds.", "RSA 358-O:4", CP_READ),
     claim("A home solicitation sale is a sale of goods or services, priced at $150 or more, "
           "with a solicitation and sale at any place other than the seller's permanent place "
           "of business.", "RSA 361-B:1", CP_READ),
     claim("The seller furnishes a receipt and contract with its name and address and the "
           "statement that the buyer may cancel any time prior to midnight of the third "
           "business day after the date of the transaction; cancel by written notice mailed, "
           "preferably certified or registered, or by returning the merchandise in person; "
           "the seller returns within 15 days of the cancellation payments, any trade-in and "
           "any note; if work physically altered the buyer's property, a refund of all funds, "
           "or full restoration instead; the seller calls for the merchandise or pays for its "
           "return; after 90 days following the sale without effort to recover it, it becomes "
           "the buyer's property; after returning all payments the seller is entitled to receive "
           "the goods within the same 15 day period.", "RSA 361-B:2", CP_READ),
     claim("A violation of this chapter is an unfair or deceptive act under RSA 358-A:2, "
           "enforced by RSA 358-A's remedies.", "RSA 361-B:3", CP_READ),
     claim("Administered and enforced by the consumer protection and antitrust bureau, "
           "department of justice; the attorney general may seek an injunction and restitution "
           "of money or property to any person injured.", "RSA 358-A:4", CP_READ),
     claim("Exempt: trade or commerce subject to the bank commissioner, the insurance "
           "commissioner or the public utilities commission; transactions entered into more "
           "than 3 years prior to the time the plaintiff knew, or reasonably should have known, "
           "of the conduct.", "RSA 358-A:3", CP_READ),
     claim("Any person injured may bring an action for damages and equitable relief; recovery "
           "of actual damages or $1,000, whichever is greater; for a willful or knowing "
           "violation as much as 3 times, but not less than 2 times, such amount; costs and "
           "reasonable attorney's fees; any attempted waiver of the right to these damages is "
           "void.", "RSA 358-A:10", CP_READ),
     # The Attorney General's pages, from the person's printouts.
     claim("The Consumer Protection and Antitrust Bureau enforces state and federal laws that "
           "make unfair and deceptive business practices unlawful; Consumer Complaints; "
           "Consumer Protection Hotline; Office of the Attorney General, 1 Granite Place South, "
           "Concord, (603) 271-3658.", AG_CPB, CP_AG_READ),
     claim("You may file a complaint with the Consumer Protection and Antitrust Bureau; all "
           "complaints submitted in writing using a consumer complaint form, electronically "
           "after creating an account with the State for filing forms online, or printed and "
           "mailed or emailed; include all supporting documents, for example a dealership's "
           "paperwork; reviewed by an attorney, who may send it to the business for review and "
           "response in writing; not a formal legal process; can take time; does not guarantee "
           "a response or resolution; the Bureau cannot provide legal representation or advice; "
           "consider speaking to a private lawyer or seeking relief in small claims court.",
           AG_COMPLAINT, CP_AG_READ)]
    + help_claims("lawyer"),
    more=civics.faq(
        ("What must a seller by mail, phone or online tell me?",
         "<p>A business that gives only a post office box, a mail drop or an answering "
         "service in its advertising must also give its legal name, the street address it "
         "actually works from, and a phone number for complaints, with some exceptions, such as "
         "a shop open to the public "
         '(<a href="/laws/361-b#s2-a">RSA 361-B:2-a</a>). A seller who will not say who and '
         "where it is is a warning sign.</p>"),
        ("What about contests and sweepstakes?",
         "<p>A sales promotion that tells you that you have a chance to win must say who runs "
         "it and every condition you must meet, and, in writing, each prize&rsquo;s value, how "
         "many there are and your odds. The rule does not apply where you need only send in or "
         "phone in an entry, or where you never have to listen to a sales pitch or pay "
         "anything.</p>"),
        ("What about a bank, an insurance company or a utility?",
         "<p>Some businesses answer to their own regulator instead: for a bank, an insurance "
         "company or a utility, complain to the Bank Commissioner, the Insurance Commissioner "
         "or the Public Utilities Commission.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>The Attorney General&rsquo;s Consumer Protection and Antitrust Bureau takes "
         "complaints on its consumer complaint form; the Attorney General&rsquo;s office "
         "answers at (603) 271-3658. For advice on your own case:</p>"
         + helps("lawyer"),
    see=[("Who to contact about an issue", "/guides/who-to-contact.html")],
    figures=[fig("$150", "RSA 361-B:1", "priced at $150 or more"),
             fig("15 days", "RSA 361-B:2", "within 15 days of the cancellation"),
             fig("90 days", "RSA 361-B:2", "after 90 days following the sale"),
             fig("10 days", "RSA 358-O:3", "within 10 days of the representation"),
             fig("$250", "RSA 358-A:2", "a face value of $250 or less"),
             fig("$1,000", "RSA 358-A:10", "$1,000, whichever is greater"),
             fig("3 years", "RSA 358-A:3", "more than 3 years prior")])

GUIDES += [CONSUMER]


# ---------------------------------------------------------------------------
# PRIVATE HEALTH INSURANCE (the person, 26 October 2026: "insurance like car
# insurance, renters insurance, homeowner's insurance, private health
# insurance"). The Marketplace's dates, Special Enrollment Periods, savings,
# ways to apply, job-based coverage and a parent's plan are HealthCare.gov's,
# whose pages answer this machine and were read on 26 October 2026; its
# Marketplace in Your State page does not name a state without a click, so
# the guide says how to find a state's way of applying rather than naming
# one. A denied claim rests on the Managed Care Law (RSA 420-J: the
# insurer's appeal, external review and expedited review), complaints on
# the Insurance Department's consumer services program (RSA 400-A:15-e),
# and the two FAQs on RSA 420-G:6 and RSA 415:22, all read on 26 October
# 2026 as the Laws pages print them. The Insurance Department's pages
# refuse this machine; they were read in the person's printouts of 26
# October 2026 (its home page, Independent External Review, and Healthcare
# and Long Term Care Appeals, which print no address and were matched by
# their titles). Medicaid and Medicare are their own guides, linked rather
# than repeated.
# ---------------------------------------------------------------------------
HI_READ = "2026-10-26"
HI_NHID_READ = "2026-10-26"          # the person's printouts of insurance.nh.gov
HC_DATES = "https://www.healthcare.gov/quick-guide/dates-and-deadlines/"
HC_SEP = "https://www.healthcare.gov/coverage-outside-open-enrollment/special-enrollment-period/"
HC_APPLY = "https://www.healthcare.gov/apply-and-enroll/how-to-apply/"
HC_LOWER = "https://www.healthcare.gov/lower-costs/"
HC_JOB = "https://www.healthcare.gov/have-job-based-coverage/options/"
HC_U26 = "https://www.healthcare.gov/young-adults/children-under-26/"
HC_EXT = "https://www.healthcare.gov/appeal-insurance-company-decision/external-review/"
HC_STATE = "https://www.healthcare.gov/marketplace-in-your-state/"
NHID = "https://www.insurance.nh.gov/"
NHID_EXT = "https://www.insurance.nh.gov/consumers/health-insurance/independent-external-review"
NHID_APPEALS = ("https://www.insurance.nh.gov/consumers/health-insurance/"
                "healthcare-and-long-term-care-appeals")

HEALTH_INSURANCE = guide(
    "health-insurance", "How to Get Private Health Insurance",
    "Buying a plan through the Health Insurance Marketplace, when you can enroll, help paying "
    "premiums, coverage through a job or a parent’s plan, and what to do if your "
    "insurance company denies a claim in New Hampshire.",
    "You can get private health insurance through a job, or buy a plan through the Health "
    "Insurance Marketplace, whose official site is HealthCare.gov. You can enroll in a "
    "Marketplace plan during Open Enrollment, November 1 to January 15, or after a life change "
    "such as losing other coverage, moving or having a baby, and you may get help paying your "
    "premiums based on your income. If your insurance company denies a claim, you can appeal "
    "to it, and then ask the New Hampshire Insurance Department for an independent external "
    "review, which the insurance company pays for.",
    [ask("How will you get coverage?",
         [("Through a job",
           "Ask the employer&rsquo;s benefits office how and when to sign up."),
          ("On your own",
           "Apply for a Marketplace plan, and see if you can get help paying."),
          ("On a low income, at 65, or with a disability",
           "Medicaid or Medicare may cover you (see &ldquo;Where Medicaid and Medicare fit&rdquo;, below).")]),
     box("If your insurance company denies a claim, appeal to it first, then ask the Insurance "
         "Department for an external review within 180 days.")],
    [step("Know when you can sign up",
          "<p>For a plan through the Marketplace, <b>Open Enrollment</b> runs from November 1 "
          "to January 15. Enroll by December 15 and your coverage can start January 1; enroll "
          "from December 16 to January 15 and it starts February 1, once you pay your first "
          "premium. These are HealthCare.gov&rsquo;s dates. How you apply depends on whether "
          "your state has its own Marketplace: HealthCare.gov&rsquo;s Marketplace in Your "
          "State page shows how residents of each state apply.</p>"
          "<p>From January 16 to October 31 you can enroll only with a <b>Special Enrollment "
          "Period</b>, which certain life changes open. Among them, in the past 60 days:</p>"
          "<ul><li>getting married, having a baby, adopting a child or placing a child in "
          "foster care;</li>"
          "<li>moving to a new ZIP code or county;</li>"
          "<li>losing qualifying health coverage, such as a job&rsquo;s plan or a "
          "parent&rsquo;s plan when you turn 26, or expecting to lose it in the next 60 days. "
          "A loss of Medicaid or CHIP counts within 90 days.</li></ul>"
          "<p>Dropping COBRA coverage yourself does not open one. You may be asked for "
          "documents that show the change. Medicaid and "
          "CHIP can be applied for at any time.</p>",
          actions=[("Dates and deadlines (HealthCare.gov)", HC_DATES),
                   ("Special Enrollment Periods (HealthCare.gov)", HC_SEP),
                   ("The Marketplace in your state (HealthCare.gov)", HC_STATE)]),
     step("Apply",
          "<p>You can apply for a Marketplace plan:</p>"
          "<ul><li>online at HealthCare.gov, the fastest way;</li>"
          "<li>by phone, with free help, in other languages too;</li>"
          "<li>with a local person or organization that helps people apply;</li>"
          "<li>through a certified enrollment partner, such as an insurance company or an "
          "online health insurance seller;</li>"
          "<li>on a paper application, mailed in. Eligibility results come by mail within 2 "
          "weeks.</li></ul>",
          actions=[("Ways to apply (HealthCare.gov)", HC_APPLY)]),
     step("See if you can get help paying",
          "<p>Depending on your income, you may get savings on your Marketplace premiums, or "
          "qualify for Medicaid or CHIP instead. Savings are based on your estimate of your "
          "income for the year you want coverage, not last year. Count yourself, your spouse "
          "if you are married, and everyone you will claim as a tax dependent. You see the "
          "exact prices and savings when you fill out the application.</p>"
          "<p>If you have, or are offered, a job-based plan that is considered affordable and "
          "meets minimum standards, you will not get savings on a Marketplace plan; most "
          "job-based plans meet them. If you already have a Marketplace plan and get an offer "
          "of coverage through a job, it may end your savings even if you turn the offer "
          "down, so update your Marketplace application.</p>",
          actions=[("Income levels and savings (HealthCare.gov)", HC_LOWER),
                   ("If you have job-based insurance (HealthCare.gov)", HC_JOB)]),
     step("Coverage through a job, COBRA, or a parent’s plan",
          "<p>For a plan through your job, ask your employer&rsquo;s benefits office how and "
          "when to sign up.</p>"
          "<p><b>COBRA</b> lets you and your family keep your employer&rsquo;s "
          "group health insurance for a limited time after an event such as losing your job or "
          "having your hours cut. When your COBRA coverage ends, you have 60 days to enroll in a "
          "Marketplace plan.</p>"
          "<p>If a parent&rsquo;s plan covers dependents, you can usually be added to it and "
          "stay on it until you turn 26. On a parent&rsquo;s job-based plan you can generally "
          "stay until 26 even if you are married, have a child, live away from home or are not "
          "claimed as a tax dependent. On a parent&rsquo;s Marketplace plan, you can stay "
          "through December 31 of the year you turn 26.</p>",
          actions=[("Getting or staying on a parent’s plan (HealthCare.gov)", HC_U26)]),
     step("Appeal a denied claim to your insurance company",
          "<p>Every health insurance company must have a written procedure for appealing a "
          "denied claim, with a full and fair review by someone other than the person who "
          "denied it. You have at least 180 days after you are told of the denial to appeal, "
          "and you may send written comments, documents and records. The company must decide "
          "an appeal of a prior authorization or of care already given within 30 days, and an "
          "urgent care appeal within 72 hours. You, or someone you authorize, can make the "
          "appeal.</p>",
          actions=[("Health insurance appeals (Insurance Department)", NHID_APPEALS)],
          law=["RSA 420-J:5"]),
     step("Ask the Insurance Department for an external review",
          "<p>If the company still says no, or misses its deadline, you can ask for an "
          "<b>independent external review</b>: send a written request to the Insurance "
          "Commissioner within 180 days of the company&rsquo;s final denial. An independent "
          "review organization decides. The insurance company pays for the review, it must "
          "follow the decision, and it may not retaliate against you for asking.</p>"
          "<p>The Insurance Department&rsquo;s page says this right is for people covered by "
          "fully-insured health or dental plans, that there is no cost to you, and that a "
          "standard review may take up to 60 days. Send its External Health Review Form by "
          "email or mail.</p>"
          "<p>If your doctor or other provider certifies that waiting would seriously endanger "
          "your life or health, or your ability to regain full function, you can ask for an "
          "<b>expedited</b> review, even while the company&rsquo;s own appeal is under way; it "
          "is decided within 72 hours. It needs a Provider Certification Form signed by your "
          "provider. It is not available for care already given.</p>"
          "<p>This review is not for Medicaid, CHIP or Medicare, except Granite Advantage "
          "coverage through a private insurer; for a self-funded employer plan run by an "
          "administrator; or for a federal employee plan. Those have their own appeals. Nor "
          "is it for a claim of malpractice. Your Explanation of Benefits or the "
          "company&rsquo;s final denial names who handles your external review.</p>",
          actions=[("Independent external review (Insurance Department)", NHID_EXT)],
          law=["RSA 420-J:5-a", "RSA 420-J:5-c", "RSA 420-J:5-e"]),
     step("Complain to the Insurance Department",
          "<p>The <b>Insurance Department</b> investigates complaints about insurance companies "
          "and agents, through a toll-free number and a complaint form. It may tell the "
          "company about your complaint, ask it for relief for you, and meet with both of you "
          "to settle it, but it cannot decide a claim. When you ask, it helps you through an "
          "insurance company&rsquo;s appeal and an external review. Call its Consumer "
          "Services staff at (603) 271-2261, toll free in New Hampshire at 1-800-852-3416, or "
          "email consumerservices@ins.nh.gov.</p>",
          actions=[("New Hampshire Insurance Department", NHID)],
          law=["RSA 400-A:15-e", "RSA 420-J:5-e"]),
     step("Where Medicaid and Medicare fit",
          "<p><b>Medicaid</b>, a federal and state program, gives free or low-cost coverage "
          "to some people with low incomes, families, children, pregnant women, older people "
          "and people with disabilities; CHIP covers children and pregnant women in families "
          "that earn too much for Medicaid. In New Hampshire you apply through the Department "
          "of Health and Human Services. <b>Medicare</b> is the federal health program for "
          "people 65 and older and some younger people with disabilities or kidney failure. "
          "Each has its own guide (below).</p>")],
    [("Dates and Deadlines (HealthCare.gov)", HC_DATES),
     ("Special Enrollment Periods (HealthCare.gov)", HC_SEP),
     ("Ways to Apply and Enroll (HealthCare.gov)", HC_APPLY),
     ("Income Levels and Savings (HealthCare.gov)", HC_LOWER),
     ("If You Have Job-Based Insurance (HealthCare.gov)", HC_JOB),
     ("How to Get or Stay on a Parent’s Plan (HealthCare.gov)", HC_U26),
     ("External Review (HealthCare.gov)", HC_EXT),
     ("The Marketplace in Your State (HealthCare.gov)", HC_STATE),
     ("Independent External Review (Insurance Department)", NHID_EXT),
     ("Healthcare and Long Term Care Appeals (Insurance Department)", NHID_APPEALS),
     ("New Hampshire Insurance Department", NHID),
     ("Managed Care Law, RSA 420-J", "/laws/420-j"),
     ("Insurance Department, RSA 400-A", "/laws/400-a"),
     ("Portability, Availability, and Renewability of Health Coverage, RSA 420-G",
      "/laws/420-g"),
     ("Accident and Health Insurance, RSA 415", "/laws/415")],
    ["420-J", "400-A", "420-G", "415"],
    [# HealthCare.gov's pages, read on 26 October 2026.
     claim("November 1: Open Enrollment starts; coverage can start as soon as January 1. "
           "December 15: last day to enroll in or change plans for coverage to start January "
           "1. January 15: Open Enrollment ends. February 1: coverage starts for those who "
           "enroll in or change plans December 16 through January 15 and pay their first "
           "premium. Between January 16 and October 31, only with a Special Enrollment Period. "
           "Medicaid or CHIP at any time. Medicaid: a joint federal and state program, free or "
           "low-cost health coverage to some low-income individuals, families, children, "
           "pregnant women, the elderly, and people with disabilities; CHIP: children and "
           "pregnant women in families that earn too much to qualify for Medicaid.",
           HC_DATES, HI_READ),
     claim("You may qualify for a Special Enrollment Period if in the past 60 days you or "
           "anyone in your household got married; had a baby, adopted a child, or placed a "
           "child for foster care; moved to a new ZIP code or county; lost qualifying health "
           "coverage in the past 60 days or expects to lose coverage in the next 60 days; lost "
           "Medicaid or CHIP coverage in the past 90 days; turned 26 and can no longer be on a "
           "parent's plan. COBRA lets you and your family continue your employer-sponsored "
           "group health insurance for a limited time after a qualifying life event, like "
           "losing your job or having your work hours reduced; when your COBRA coverage ends, "
           "you have 60 days to enroll in a Marketplace health plan; voluntarily dropping "
           "COBRA doesn't count. You may have to submit documents. Turned down for a Special "
           "Enrollment Period, you can appeal the decision. Medicare: a federal health program "
           "for people 65 and older and certain younger people with disabilities and ESRD.",
           HC_SEP, HI_READ),
     claim("Apply online at HealthCare.gov, the fastest way; over the phone, free, non-biased "
           "help, in other languages; local people and organizations that help you apply; a "
           "certified enrollment partner, like an insurance company or online health insurance "
           "seller; a paper application, with eligibility results in the mail within 2 weeks.",
           HC_APPLY, HI_READ),
     claim("Savings on Marketplace premiums, or Medicaid or CHIP, based on your income; savings "
           "are based on your income estimate for the year you want coverage, not last year; "
           "count yourself, your spouse if you're married, plus everyone you'll claim as a tax "
           "dependent; exact plan prices and savings when you fill out a Marketplace "
           "application.", HC_LOWER, HI_READ),
     claim("With job-based insurance now or an offer of it, no savings on a Marketplace plan if "
           "the job-based plan is considered affordable and meets minimum standards; most "
           "job-based plans meet these standards; with a Marketplace plan, an offer of "
           "job-based insurance may end your savings even if you don't accept it; update your "
           "Marketplace application.", HC_JOB, HI_READ),
     claim("If a parent's plan covers dependents, you usually can be added to it and stay on it "
           "until you turn 26; on a parent's Marketplace plan, through December 31 of the year "
           "you turn 26; on a parent's job-based plan, generally until 26 even if you got "
           "married, have a child, live out of the home or aren't claimed as a tax dependent.",
           HC_U26, HI_READ),
     claim("Your insurer is required by law to accept the external reviewer's decision; a "
           "state external review process that meets the federal standards is the one "
           "insurers in that state follow; your Explanation of Benefits or the final denial of "
           "the internal appeal gives the contact for the organization that will handle your "
           "external review.", HC_EXT, HI_READ),
     claim("How you apply depends on if your state has its own Marketplace; pick your state.",
           HC_STATE, HI_READ),
     # The statutes, as the Laws pages print them, read on 26 October 2026.
     claim("Every carrier maintains a written procedure to appeal a claim denial, with a full "
           "and fair review; the persons reviewing are not those who made the initial "
           "determination; at least 180 days following receipt of a notification of a claim "
           "denial to appeal; the claimant may submit written comments, documents and records; "
           "a nonexpedited appeal of a prior authorization or post-service claim decided in no "
           "event more than 30 days after receipt; an expedited urgent care appeal decided no "
           "more than 72 hours after it is filed; a claimant or a representative of the "
           "claimant may appeal.", "RSA 420-J:5", HI_READ),
     claim("A covered person has the right to independent external review of an adverse "
           "determination after completing internal review, or if the carrier agreed or missed "
           "its time frames; the request in writing to the commissioner within 180 days of the "
           "denial decision; not for Medicaid, CHIP or Medicare, except private coverage under "
           "the granite advantage program; not for self-funded plans administered by an "
           "administrative services organization or third-party administrator, or federal "
           "employee benefit programs; not for malpractice.", "RSA 420-J:5-a", HI_READ),
     claim("Expedited external review when the treating provider certifies that the standard "
           "time frames would seriously jeopardize the life or health of the covered person or "
           "the ability to regain maximum function; may be pursued simultaneous with internal "
           "review; decided no more than 72 hours after it is requested; not for "
           "determinations made on a retrospective basis.", "RSA 420-J:5-c", HI_READ),
     claim("The health carrier pays the cost of the external review; the decision is binding on "
           "the carrier, and on the covered person except where other remedies exist; the "
           "carrier shall not retaliate; on request, the commissioner provides consumer "
           "assistance with internal grievances and external review.", "RSA 420-J:5-e",
           HI_READ),
     claim("The commissioner maintains a program to investigate complaints against insurers, "
           "producers and others the commissioner regulates, with a toll-free telephone number "
           "and a standardized complaint form; may notify the insurer, request relief for the "
           "complainant and mediate; no power to adjudicate claims.", "RSA 400-A:15-e",
           HI_READ),
     claim("Health carriers shall not establish rules of eligibility, including continued "
           "eligibility, in relation to health status, medical condition, claims experience, "
           "receipt of health care, medical history, genetic information, evidence of "
           "insurability or disability; no rescission except for fraud or an intentional "
           "misrepresentation of material fact; renewable except for nonpayment of required "
           "premiums, fraud or intentional misrepresentation, an employer's failure to meet "
           "participation requirements or violation of the chapter, or the carrier ceasing to "
           "offer coverage in the market.", "RSA 420-G:6", HI_READ),
     claim("Health insurance policies cover a newly born child from the moment of birth; if a "
           "specific premium is required, notice of the birth and payment within 31 days after "
           "the date of birth for coverage to continue; no additional premium for the first 31 "
           "days.", "RSA 415:22", HI_READ),
     # The Insurance Department's pages, in the person's printouts of 26 October 2026.
     claim("New Hampshire law gives individuals who are covered by fully-insured health or "
           "dental insurance plans the right to have a nationally accredited, independent, "
           "medical review organization (IRO) review and assess whether the company's denial "
           "is justified. There is no cost to the patient for an external review. Standard "
           "External Review: a fully-insured health or dental insurance plan, completed the "
           "insurer's internal appeal process, received a final denial; must be submitted to "
           "the Insurance Department within 180 days of the insurance company's final denial "
           "and may take up to 60 days for the IRO to make its decision. Expedited External "
           "Review: the treating provider must certify that delaying treatment will seriously "
           "jeopardize the life or health of the patient or the patient's ability to regain "
           "maximum function; IROs must complete expedited reviews within 72 hours; may be "
           "requested at the same time the patient pursues an expedited internal appeal. A "
           "completed Provider Certification Form, signed by your provider, is required for an "
           "expedited external review. Download the External Health Review Form PDF to submit "
           "via email or mail. Call 800-852-3416 to speak with a Consumer Services Officer.",
           NHID_EXT, HI_NHID_READ),
     claim("Healthcare and Long Term Care Appeals: guides for understanding the health and "
           "long-term care insurance appeals process: Understand Health Insurance Claim "
           "Appeals; Understand Self-Funded or Self-Insured Health Insurance; Consumer Guide to "
           "External Review; External Review Appeals; Health Insurance Appeals Law; Health "
           "Insurance Appeals Regulations; NH Certified Independent Review Organizations (IROs) "
           "for External Appeal of a Healthcare Decision.", NHID_APPEALS, HI_NHID_READ),
     claim("The New Hampshire Insurance Department regulates the insurance industry in New "
           "Hampshire. Have questions, need assistance? Call our Consumer Services staff: "
           "(603) 271-2261, in state toll free (800) 852-3416 or email "
           "consumerservices@ins.nh.gov. Submit a Complaint; Health Care Appeals.", NHID,
           HI_NHID_READ)]
    + help_claims("nheasy", "lawyer"),
    more=civics.faq(
        ("Can an insurance company turn me down because of a health condition?",
         "<p>No. New Hampshire law forbids a health insurance company to base whether you can "
         "get or keep coverage on your health, a medical condition, your medical history, "
         "genetic information or a disability (<a href=\"/laws/420-g#s6\">RSA 420-G:6</a>). "
         "It may not cancel your coverage back to its start except for fraud or an intentional "
         "misrepresentation of an important fact, and it may decline to renew it only for the "
         "reasons the law lists, such as unpaid premiums.</p>"),
        ("Is my new baby covered?",
         "<p>A health insurance policy covers a newborn from the moment of birth. If adding a "
         "child costs more, the policy may require you to tell the company about the birth "
         "and pay within 31 days after it for the coverage to continue; there is no extra "
         "premium for those first 31 days (<a href=\"/laws/415#s22\">RSA 415:22</a>).</p>"),
        ("What if I am turned down for a Special Enrollment Period?",
         "<p>You can appeal the decision. HealthCare.gov&rsquo;s Special Enrollment Periods "
         "page explains how.</p>"),
        ("Can someone appeal for me?",
         "<p>Yes. Someone you authorize to act for you, such as your doctor, can make an "
         "appeal to the insurance company or ask for an external review on your behalf.</p>"))
    + "<h2>Who Can Help</h2>"
         "<p>The Insurance Department&rsquo;s Consumer Services, at (603) 271-2261 or toll "
         "free in New Hampshire at 1-800-852-3416, for questions and complaints about an "
         "insurance company, and help with an appeal. For "
         "Medicaid, or advice on your own case:</p>"
         + helps("nheasy", "lawyer"),
    see=[("How to apply for food or health assistance", "/guides/food-and-health-assistance.html"),
         ("How to sign up for Medicare and Social Security, and get help with the costs",
          "/guides/medicare-and-social-security.html"),
         ("How to report a scam or file a consumer complaint", "/guides/consumer-rights.html")],
    figures=[fig("180 days", "RSA 420-J:5-a", "within 180 days of the date"),
             fig("180 days", "RSA 420-J:5", "at least 180 days following receipt"),
             fig("30 days", "RSA 420-J:5", "more than 30 days after receipt"),
             fig("72 hours", "RSA 420-J:5-c", "more than 72 hours after the expedited external review is requested"),
             fig("72 hours", "RSA 420-J:5", "more than 72 hours after the appeal is filed"),
             fig("31 days", "RSA 415:22", "within 31 days after the date of birth"),
             fig("60 days", HC_SEP, "in the past 60 days"),
             fig("90 days", HC_SEP, "in the past 90 days"),
             fig("2 weeks", HC_APPLY, "within 2 weeks"),
             fig("60 days", NHID_EXT, "may take up to 60 days")])

GUIDES += [HEALTH_INSURANCE]


# ---------------------------------------------------------------------------
# TRASH, RECYCLING, YARD WASTE AND HAZARDOUS WASTE (the person, 24 October
# 2026: "proper disposal of trash, recycling, compost, large items, and
# hazardous materials (Hazardous materials day) which varies by town and
# local transfer stations"). What varies by town is the town's to say, so the
# guide gives the state's rules -- RSA 149-M as the Laws pages print it: what
# a town must provide, what it may require, and what may never go in the
# trash anywhere in the state -- and sends the reader to the town for the
# rest. The EPA's pages on household hazardous waste and composting at home,
# read on 24 October 2026, give the safe handling. The Department of
# Environmental Services' list of collection contacts refuses a cloud
# session; it was read in the person's printout the same day.
# ---------------------------------------------------------------------------
TR_READ = "2026-10-24"
DES_HHW = ("https://www.des.nh.gov/sites/g/files/ehbemt341/files/documents/"
           "hhw-collection-contacts.pdf")
EPA_HHW = "https://www.epa.gov/hw/household-hazardous-waste-hhw"
EPA_COMPOST = "https://www.epa.gov/recycle/composting-home"

TRASH = guide(
    "trash-and-recycling", "How to Get Rid of Trash, Recycling, Yard Waste and Hazardous Waste",
    "Your town's transfer station or trash pickup, what may never go in the trash in New "
    "Hampshire, household hazardous waste collection days, and composting at home.",
    "Trash and recycling are your town&rsquo;s to run: every town must provide a place for its "
    "residents&rsquo; trash, or arrange for one, and sets its own rules, fees and recycling. "
    "State law keeps some things out of New Hampshire&rsquo;s landfills and incinerators: "
    "electronics, wet-cell and lithium-ion batteries, products containing mercury, and leaves "
    "and yard waste. Paint, "
    "pesticides, cleaners and other hazardous household products go to a household hazardous "
    "waste collection.",
    [box("Ask your town how it takes trash and recycling: a transfer station, pickup, bags or "
         "stickers."),
     ask("Is it something special?",
         [("Electronics, wet-cell and lithium-ion batteries, mercury, yard waste",
           "Never in the trash. Ask your transfer station where it goes."),
          ("Paint, cleaners, pesticides, oil",
           "Keep it for a household hazardous waste collection.")]),
     box("Compost food scraps and yard trim at home, or in a town program.")],
    [step("Learn your town’s rules",
          "<p>Every town must either run a solid waste facility, often called the transfer "
          "station or the dump, or make sure its residents can use one elsewhere. The town "
          "sets the rules: what must be separated for recycling, how trash is collected, what "
          "it costs, and whether you must use special bags or stickers, which the town sells "
          "at a reasonable price.</p>"
          "<p>Your town or city office, its website or the transfer station can tell you the "
          "hours, what it takes and how, including anything large.</p>",
          law=["RSA 149-M:17"]),
     step("Never put these in the trash",
          "<p>State law forbids putting these in a landfill or incinerator anywhere in New "
          "Hampshire:</p>"
          "<ul><li><b>Electronics:</b> computers and monitors, printers, televisions and other "
          "screens, cell phones, copiers and fax machines.</li>"
          "<li><b>Wet-cell and lithium-ion batteries.</b></li>"
          "<li><b>Products that contain mercury</b>, such as mercury fever thermometers. Keep "
          "them separate from your trash, for recycling or hazardous waste disposal.</li>"
          "<li><b>Leaves and yard waste.</b></li></ul>",
          law=["RSA 149-M:4", "RSA 149-M:27", "RSA 149-M:51", "RSA 149-M:58"]),
     step("Hazardous products: keep them for a collection day",
          "<p>Leftover products that can catch fire, react, explode, corrode or poison, such as "
          "paints, cleaners, oils, batteries and pesticides, are <b>household hazardous "
          "waste</b>. Do not pour them down the drain, on the ground or into a storm drain, and "
          "check before putting any out with the trash.</p>"
          "<ul><li>Keep them in their original containers with the labels on, and never mix "
          "them.</li>"

          "<li>Take them to a household hazardous waste collection. The Department of "
          "Environmental Services lists each town&rsquo;s contact for one, often a regional "
          "event run by a planning commission or a nearby city. If your town has no event "
          "listed, call the Department&rsquo;s Household Hazardous Waste Program at (603) "
          "271-2047.</li></ul>",
          actions=[("Collection day contacts by town (Department of Environmental Services)",
                    DES_HHW),
                   ("Household hazardous waste (EPA)", EPA_HHW)]),
     step("Compost at home",
          "<p>You can compost food scraps from your kitchen with leaves and other yard "
          "trim. Mix &ldquo;greens&rdquo;, such as fruit and vegetable scraps, coffee "
          "grounds and grass clippings, with &ldquo;browns&rdquo;, such as dry leaves, twigs, "
          "shredded paper and cardboard. If you have no room, look for a town or "
          "community composting program that collects food scraps or takes them at a "
          "drop-off.</p>",
          actions=[("Composting at home (EPA)", EPA_COMPOST)])],
    [("Collection event contacts, 2026-2027 (Department of Environmental Services)", DES_HHW),
     ("Household Hazardous Waste (EPA)", EPA_HHW),
     ("Composting at Home (EPA)", EPA_COMPOST),
     ("Solid Waste Management, RSA 149-M", "/laws/149-m")],
    ["149-M"],
    # Read in the person's printout of 24 October 2026 (revised 27 March 2026).
    [claim("Contacts for 2026-2027 household hazardous waste collection events, town by town, "
           "many hosted by a regional planning commission, a city or a district; No Event "
           "Identified where a town has none; the Household Hazardous Waste Program at (603) "
           "271-2047 or hhw@des.nh.gov.", DES_HHW, TR_READ),
     claim("Each town shall provide a facility or assure access to another approved solid "
           "waste facility for its residents; bylaws on its facility, reasonable rates, "
           "separation and collection of refuse; designated bags or containers or disposal "
           "stickers sold at a reasonable price; civil penalties for violating the bylaws.",
           "RSA 149-M:17", TR_READ),
     claim("No person shall dispose of wet-cell batteries, lithium-ion batteries or electronic "
           "devices in a landfill or incinerator; municipalities and facilities make educational "
           "materials available on recycling them and should provide recycling where possible; "
           "no leaf or yard waste in a landfill or incinerator.", "RSA 149-M:27", TR_READ),
     claim("Electronic device means computer, computer monitor, computer peripheral, printer, "
           "television, wireless telephones, copiers, fax machines and video display device.",
           "RSA 149-M:4", TR_READ),
     claim("No person shall knowingly dispose of mercury-added products in landfills, transfer "
           "stations or incinerators; every person separates them for recycling or disposal as "
           "hazardous waste; facilities give customers information about collection programs.",
           "RSA 149-M:58", TR_READ),
     claim("A mercury fever thermometer is a mercury-added product.", "RSA 149-M:51", TR_READ),
     claim("Leftover products that can catch fire, react or explode, or are corrosive or toxic, "
           "such as paints, cleaners, oils, batteries and pesticides; improper disposal includes "
           "pouring down the drain, on the ground, into storm sewers, or in some cases out with "
           "the regular trash; keep in original containers, never remove labels, never mix; corroding "
           "containers: call the fire department; designated collection days; some garages "
           "accept used motor oil.", EPA_HHW, TR_READ),
     claim("Compost food scraps with dry leaves and yard trim; greens such as fruit and "
           "vegetable scraps, coffee grounds and grass clippings; browns such as dry leaves, "
           "twigs, shredded paper and cardboard; avoid meat, fish, bones, dairy, fats and oils, "
           "which can attract animals, and pet waste; a municipal or community program may "
           "collect food scraps or offer a drop-off.", EPA_COMPOST, TR_READ)],
    more=civics.faq(
        ("Can my town fine me for breaking its trash rules?",
         "<p>Yes: a town may fine people who break its rules.</p>"),
        ("Where can I recycle batteries and electronics?",
         "<p>Towns, and the operators of landfills and incinerators, must make information "
         "available on recycling wet-cell and lithium-ion batteries and electronics, and "
         "should offer recycling for them where they can. Ask at your town&rsquo;s transfer "
         "station.</p>"),
        ("What if a hazardous product's container is corroding?",
         "<p>Call your fire department for instructions.</p>"),
        ("What do I do with used motor oil?",
         "<p>Some garages accept used motor oil for recycling.</p>"),
        ("What should I keep out of a compost pile?",
         "<p>Meat, fish, bones, dairy, fats and oils, which attract animals, and pet "
         "waste.</p>"))
    + "<h2>Who Can Help</h2>"
         "<p>Your town or city office, and your transfer station, for the local rules, hours "
         "and fees and the date of the next household hazardous waste collection.</p>",
    see=[("Who to contact about an issue", "/guides/who-to-contact.html"),
         ("How to prepare for storms, power outages and other emergencies",
          "/guides/storms-and-emergencies.html")])

GUIDES += [TRASH]


# ---------------------------------------------------------------------------
# YOUR RIGHTS AT WORK: GETTING PAID (the person, 25 October 2026: "Write all
# three know your rights guides too"). From RSA 275 (payment of wages, the
# final paycheck, deductions, notice, the wage claim, retaliation, meal
# breaks) and RSA 279 (minimum wage and overtime), read in the site's own
# Laws pages on 25 October 2026, and the U.S. Department of Labor's overtime
# page, read the same day. New Hampshire's minimum wage is the federal one
# (RSA 279:21), and no dollar amount is printed: the statute sets none of its
# own (FIGURE above). The New Hampshire Department of Labor's own pages refuse
# this machine, so their claim waits for the person's printouts.
# ---------------------------------------------------------------------------
WG_READ = "2026-10-25"
WG_PAGES_READ = "2026-10-26"         # the person's printout of dol.nh.gov's home page
NH_DOL = "https://www.dol.nh.gov/"
# The online wage claim form's address, as the person gave it on 26 October
# 2026. Nobody here has read the form, so the guide says nothing of it but
# that it is where a claim is filed online.
NH_WAGE_CLAIM = "https://www.dol.nh.gov/online-forms/file-online-wage-claim"
WHD_OVERTIME = "https://www.dol.gov/agencies/whd/overtime"

WAGES = guide(
    "wage-rights", "Your Rights at Work: Getting Paid",
    "When your pay is due in New Hampshire, your final paycheck, what your employer may take out "
    "of your pay, minimum wage, overtime and meal breaks, and how to file a wage claim with the "
    "Department of Labor.",
    "In New Hampshire your employer must tell you your rate of pay when you are hired and pay "
    "you on regular paydays set in advance. If you are fired, all your wages are due within 72 "
    "hours; if you quit or are laid off, by the next regular payday. Your employer may take money "
    "out of your pay only as the law requires or you agree in writing. If you are not paid what "
    "you earned, you can file a wage claim with the New Hampshire Department of Labor, and your "
    "employer may not punish you for it.",
    [ask("Were you paid everything you earned, on time?",
         [("Yes", "Keep your pay statements: they list what was taken out of each paycheck."),
          ("No", "File a wage claim with the Department of Labor, within 36 months.")]),
     ask("Did your job end?",
         [("You were fired", "Your wages are due in full within 72 hours."),
          ("You quit or were laid off", "Your wages are due by the next regular payday.")]),
     box("Your employer may not fire or punish you for filing a claim, or for asking about or "
         "discussing wages.")],
    [step("Know when you must be paid",
          "<p>Your employer must pay all the wages you have earned on regular paydays set in "
          "advance, at no cost to you: within 8 days after the end of the work week if you are "
          "paid weekly, or within 15 days if you are paid every two weeks. The Department of "
          "Labor may allow some employers to pay less often, but never less than once a "
          "month.</p>"
          "<p>When you are hired, your employer must tell you your rate of pay and the day and "
          "place you will be paid, and must tell you before either changes.</p>",
          law=["RSA 275:43", "RSA 275:49"]),
     step("Your last paycheck",
          "<ul><li><b>If you are fired</b>, your employer must pay all your wages within 72 "
          "hours.</li>"
          "<li><b>If you quit</b>, by the next regular payday. If you gave at least one pay "
          "period&rsquo;s notice, within 72 hours.</li>"
          "<li><b>If you are laid off</b>, or your work stops because of a labor dispute, by the "
          "next regular payday.</li></ul>"
          "<p>An employer that willfully, "
          "and without good cause, pays late owes you extra, as liquidated damages: 10 percent "
          "of the unpaid wages for each day the pay is late, not counting Sundays and legal "
          "holidays, up to the amount of the unpaid wages.</p>",
          law=["RSA 275:44"]),
     step("What may be taken out of your pay",
          "<p>Your employer may hold back part of your wages only when a state or federal law "
          "requires or allows it, such as payroll taxes, or when you have agreed in writing to "
          "a deduction for a lawful purpose that benefits you, such as union dues, health "
          "insurance, retirement contributions, a charity, or anything else you agree to that "
          "gives your employer no financial advantage. A deduction you agree to for some other "
          "purpose may not be used to pay for things you need to do your job.</p>"
          "<p>Each pay period that something is taken out, your employer must give you a "
          "statement of the deductions.</p>",
          law=["RSA 275:48", "RSA 275:49"]),
     step("Minimum wage, overtime and meal breaks",
          "<p><b>Minimum wage.</b> New Hampshire&rsquo;s minimum wage is the federal minimum "
          "wage.</p>"
          "<p><b>Overtime.</b> Unless your job is exempt, you must be paid time and one-half "
          "your regular rate for every hour over 40 hours in a work week. Federal law requires "
          "it of the employers the Fair Labor Standards Act covers; New Hampshire&rsquo;s law "
          "requires it of most other employers.</p>"
          "<p><b>Meal breaks.</b> Your employer may not make you work more than 5 consecutive "
          "hours without a half-hour break to eat, unless you can eat while you work and your "
          "employer lets you.</p>",
          actions=[("Overtime pay (U.S. Department of Labor)", WHD_OVERTIME)],
          law=["RSA 279:21", "RSA 275:30-a"]),
     step("File a wage claim",
          "<p>You can file a <b>wage claim</b> with the New Hampshire Department of Labor, no "
          "later than 36 months after the wages were due. The Department sends a copy to your "
          "employer, who has 20 days to object; if it does not, the Department may order it to "
          "pay. Either side can ask for a hearing, and the Department decides in writing within "
          "30 days after it. A decision can be appealed to the superior court within 20 "
          "days.</p>"
          "<p>You can also sue for unpaid wages in court, yourself or through a representative, "
          "and the court may order your employer to pay your costs and reasonable "
          "attorney&rsquo;s fees.</p>"
          "<p>File your claim online with the Department&rsquo;s wage claim form. Its office "
          "answers at 603-271-3176, Monday through Friday, 8:00&nbsp;AM to 4:30&nbsp;PM; mail and "
          "hearings stay at 95 Pleasant Street, Spaulding Building, in Concord.</p>",
          actions=[("File a wage claim online (Department of Labor)", NH_WAGE_CLAIM),
                   ("New Hampshire Department of Labor", NH_DOL)],
          law=["RSA 275:51", "RSA 275:53"]),
     step("Your employer may not punish you for it",
          "<p>An employer may not fire you, or treat you differently in any other way, because "
          "you filed a complaint or a claim, took part in an investigation or hearing about "
          "your pay, or asked about, talked about or shared what you or a coworker are "
          "paid.</p>"
          "<p>It is also illegal to pay someone less than a coworker for equal work because of "
          "their sex. Your employer must post a notice saying so, with how to reach the "
          "Department of Labor.</p>",
          law=["RSA 275:38-a", "RSA 275:37", "RSA 275:49"])],
    [("New Hampshire Department of Labor", NH_DOL),
     ("Overtime Pay (U.S. Department of Labor)", WHD_OVERTIME),
     ("Protective Legislation, RSA 275", "/laws/275"),
     ("Minimum Wage Law, RSA 279", "/laws/279")],
    ["275", "279"],
    [# The statutes, read on 25 October 2026 in the site's own Laws pages.
     claim("Every employer shall pay all wages due within 8 days after the expiration of the "
           "work week if paid weekly, or within 15 days if paid biweekly, on regular paydays "
           "designated in advance and at no cost to the employee: in money, by electronic fund "
           "transfer, by direct deposit with written authorization, by a payroll card with at "
           "least one free means to withdraw the full balance each pay period, or by checks "
           "cashable near the place of employment; an employer paying electronically shall offer "
           "the check option (I); the commissioner may permit payment at least once each "
           "calendar month (IV); vacation pay, severance pay, personal days, holiday pay, sick "
           "pay and employee expenses, when a matter of employment practice or policy, are "
           "wages when due (V).", "RSA 275:43", WG_READ),
     claim("Discharged: wages in full within 72 hours (I); quits or resigns: no later than the "
           "next regular payday, or within 72 hours after at least one pay period's notice, by "
           "mail if requested (II); laid off or suspended by a labor dispute: not later than the "
           "next regular payday (III); willfully and without good cause failing to pay: "
           "liquidated damages of 10 percent of the unpaid wages for each day except Sunday and "
           "legal holidays, or an amount equal to the unpaid wages, whichever is smaller (IV).",
           "RSA 275:44", WG_READ),
     claim("No employer may withhold or divert any portion of an employee's wages unless "
           "required or empowered by state or federal law, including payroll taxes, or with a "
           "written authorization for a lawful purpose accruing to the benefit of the employee, "
           "among them union dues, insurance, pension and charity, or any purpose agreed that "
           "does not grant financial advantage to the employer; not to offset payments for items "
           "required in the performance of the job.", "RSA 275:48", WG_READ),
     claim("Notify employees at hiring of the rate of pay and the day and place of payment, and "
           "of changes before they happen; make available in writing or by posted notice the "
           "policies on vacation pay, sick leave and other fringe benefits; furnish a statement "
           "of deductions for each pay period deductions are made; post the equal pay notice "
           "with how to contact the Department of Labor.", "RSA 275:49", WG_READ),
     claim("A wage claim may be filed by an employee no later than 36 months from the date the "
           "wages were due; the employer is served and may object within 20 days from the "
           "receipt of such notice, or the commissioner may order payment; a hearing if "
           "requested; a written decision within 30 days after the hearing; appeal to the "
           "superior court not later than 20 days from the date thereof.", "RSA 275:51",
           WG_READ),
     claim("An employee may sue for unpaid wages and liquidated damages in any court of "
           "competent jurisdiction, himself or through an agent or representative; the court "
           "may allow costs and reasonable attorney's fees; the commissioner may take an "
           "assignment of the claim.", "RSA 275:53", WG_READ),
     claim("No employer shall discharge or in any other manner discriminate against an employee "
           "because he or she made a charge, filed a complaint, took part in an investigation, "
           "proceeding or hearing, or inquired about, discussed, or disclosed his or her wages "
           "or those of another employee.", "RSA 275:38-a", WG_READ),
     claim("No employer shall pay employees of one sex at a rate less than the rate paid to "
           "employees of the other sex for equal work, with exceptions such as seniority and "
           "merit systems.", "RSA 275:37", WG_READ),
     claim("An employer may not require an employee to work more than 5 consecutive hours "
           "without granting a 1/2 hour lunch or eating period, unless it is feasible for the "
           "employee to eat while working and the employer permits it.", "RSA 275:30-a",
           WG_READ),
     claim("No employee at an hourly rate lower than that set forth in the federal minimum wage "
           "law; tipped employees of a restaurant, hotel and the like who customarily receive "
           "tips get a lower base rate from the employer, and the employer pays the difference "
           "if wages at the end of a pay period do not equal the minimum wage for all hours "
           "worked; exceptions for household, domestic and farm labor, outside salesmen, summer "
           "camps, and lower rates for some young and inexperienced workers; time and one-half "
           "for all time worked in excess of 40 hours in any one week, except, among others, "
           "employees of employers covered by the federal Fair Labor Standards Act (VIII).",
           "RSA 279:21", WG_READ),
     # The U.S. Department of Labor's page, read on 25 October 2026.
     claim("Unless exempt, employees covered by the Fair Labor Standards Act must receive overtime "
           "pay for hours worked over 40 in a workweek at a rate not less than time and one-half "
           "their regular rates of pay.", WHD_OVERTIME, WG_READ),
     # The New Hampshire Department of Labor's page, from the person's printouts.
     claim("Submit a Wage Claim: your claim will be reviewed for scheduling for a hearing before "
           "a Department Hearings Officer; the Department has moved to Londergan Hall, 101 "
           "Pleasant Street; hearings and mailed correspondence remain at 95 Pleasant Street, "
           "Spaulding Building, Concord, NH 03301; phone 603-271-3176; Monday - Friday, 8AM - "
           "4:30PM.", NH_DOL, WG_PAGES_READ),
     # The person's word, not a page read here.
     claim("The Department of Labor's online wage claim form is at this address, as the person "
           "gave it on 26 October 2026.", NH_WAGE_CLAIM, "2026-10-26")]
    + help_claims("lawyer"),
    more=civics.faq(
        ("How can I be paid?",
         "<p>You can be paid in cash, by a check you can cash near work, by direct deposit you "
         "have agreed to in writing, or on a payroll card with at least one free way to take "
         "out your whole balance each pay period. An employer that pays electronically must "
         "also offer you a paper check.</p>"),
        ("Do vacation pay and other benefits count as wages?",
         "<p>Your employer&rsquo;s rules on vacation pay, sick leave and other benefits must "
         "be given to you in "
         "writing or posted where you can see them. Vacation, holiday and sick pay, severance "
         "and work expenses that are your employer&rsquo;s practice or policy count as wages "
         "when they are due.</p>"),
        ("Can my last paycheck be mailed to me?",
         "<p>If you quit or are laid off, you can ask for the last paycheck to be mailed to "
         "you.</p>"),
        ("Can a tipped worker be paid less than the minimum wage?",
         "<p>A tipped worker in a restaurant or hotel who regularly gets tips may be paid a "
         "lower base rate by the employer, but if base pay and tips together come to less than "
         "the minimum wage for all the hours worked in a pay period, the employer must pay the "
         "difference.</p>"),
        ("Does the minimum wage cover every job?",
         "<p>The law exempts some work, such as farm and household labor, and lets some young "
         "and new workers be paid less.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>The New Hampshire Department of Labor enforces the state&rsquo;s wage laws and takes "
         "wage claims. The U.S. Department of Labor&rsquo;s overtime page explains the federal "
         "overtime rule. For advice about your own situation, a "
         "lawyer can help:</p>"
         + helps("lawyer"),
    see=[("How to file for unemployment", "/guides/file-for-unemployment.html"),
         ("How to apply for food or health assistance", "/guides/food-and-health-assistance.html")],
    figures=[fig("72 hours", "RSA 275:44", "within 72 hours"),
             fig("36 months", "RSA 275:51", "no later than 36 months from the date the wages were due"),
             fig("8 days", "RSA 275:43", "within 8 days after the expiration of the work week"),
             fig("15 days", "RSA 275:43", "within 15 days after the expiration of the work week"),
             fig("10 percent", "RSA 275:44", "10 percent of the unpaid wages"),
             fig("40 hours", "RSA 279:21", "in excess of 40 hours in any one week"),
             fig("5 consecutive hours", "RSA 275:30-a", "more than 5 consecutive hours"),
             fig("20 days", "RSA 275:51", "within 20 days from the receipt of such notice"),
             fig("30 days", "RSA 275:51", "within 30 days after the hearing")])

GUIDES += [WAGES]


# ---------------------------------------------------------------------------
# A U.S. PASSPORT (the person, 25 October 2026: "go ahead with the passport
# guide"; federal sources allowed, 24 October 2026). A passport is federal:
# the Department of State issues it and New Hampshire has no part, so the
# guide rests on the federal rules (22 CFR part 51, read at eCFR on 25 October
# 2026, current to 22 October) and on the Postal Service's passport page, read
# the same day, and sends a reader to the State Department's own pages for
# the forms, fees and processing times, which change. travel.state.gov
# refuses this machine; its pages are the person's printouts of 25 October
# 2026, at the addresses the printouts show -- the State Department had moved
# them since the guide was drafted, so its links are the printouts' now. No
# fee is printed: a dollar amount rests on a statute, and none of New
# Hampshire's sets these (FIGURE above). Renewing by mail is the State
# Department's "Renew Your Passport by Mail", the person's printout of 26
# October 2026 (passport7), at the address it shows.
# ---------------------------------------------------------------------------
PP_READ = "2026-10-25"
PP_MAIL_READ = "2026-10-26"          # the person's printout (passport7)
STATE_MAIL = "https://travel.state.gov/en/passports/renew-replace/mail.html"
PP_STATE_READ = "2026-10-25"         # the person's printouts of travel.state.gov
STATE_ADULT = "https://travel.state.gov/en/passports/apply/adults.html"
STATE_ONLINE = "https://travel.state.gov/en/passports/renew-replace/online.html"
STATE_CHILD = "https://travel.state.gov/en/passports/apply/child/under-16.html"
STATE_FAST = "https://travel.state.gov/en/passports/apply/get-fast.html"
STATE_APPOINT = "https://travel.state.gov/en/passports/apply/get-fast/make-appointment.html"
USPS_PASSPORTS = "https://www.usps.com/international/passports.htm"
_CFR22 = "https://www.ecfr.gov/current/title-22/chapter-I/subchapter-F/part-51/subpart-B/"
CFR_PP_EXECUTE = _CFR22 + "section-51.21"
CFR_PP_AGENTS = _CFR22 + "section-51.22"
CFR_PP_MINORS = _CFR22 + "section-51.28"
CFR_PP_BIRTH = _CFR22.replace("subpart-B", "subpart-C") + "section-51.42"
CFR_PP_VALID = ("https://www.ecfr.gov/current/title-22/chapter-I/subchapter-F/part-51/"
                "subpart-A/section-51.4")

PASSPORT = guide(
    "passport", "How to Get a U.S. Passport",
    "Getting a first U.S. passport or renewing one from New Hampshire, step by step: whether you "
    "can renew by mail, what to bring to a post office, a child's passport, and what to do if "
    "you travel soon.",
    "A U.S. passport comes from the U.S. Department of State, not from New Hampshire. If it is "
    "your first passport, if you are under 16, or if you cannot renew, you apply in person on "
    "Form DS-11 at an acceptance facility, such as a post office, by appointment. Bring proof of "
    "U.S. citizenship, such as a certified birth certificate, a photo ID, a photocopy of each, "
    "and a photo. If your last passport was issued for 10 years, within the last 15 years, you "
    "can usually renew by mail or online instead.",
    [ask("Have you had a U.S. passport issued for 10 years, within the last 15 years?",
         [("Yes", "You can usually renew by mail or online. You cannot renew at a post "
                  "office."),
          ("No, or it is for a child under 16",
           "Apply in person on Form DS-11, at a post office or another acceptance facility.")]),
     box("Applying in person? Gather proof of citizenship, a photo ID, a photocopy of each, and a "
         "photo."),
     box("Make an appointment, and sign the form only when the agent asks you to."),
     box("Pay two fees there: one to the Department of State, one to the facility.")],
    [step("Check whether you can renew instead",
          "<p>You can renew by mail only if your most recent passport was issued for 10 years, "
          "when you were 16 or older; it was issued no more than 15 years ago; it has never been "
          "reported lost or stolen; it is undamaged, apart from normal wear; it was issued in your "
          "current name, or you can send a document such as a marriage certificate, divorce "
          "decree or court order showing your name change; and you can send it in with your "
          "application.</p>"
          "<p>You can <b>renew online</b> instead if that passport was valid for 10 years and "
          "expires within a year or expired less than 5 years ago; you are 25 or older; you are "
          "not changing your name or sex; you are not traveling for at least 6 weeks, since an "
          "online renewal cannot be expedited; you are in the United States when you apply; and "
          "you have the passport, undamaged. You pay by card, and you keep the old passport, "
          "which is canceled once you apply.</p>"
          "<p>A renewal is never done in person at a post office. If you cannot renew, apply in "
          "person as a first-time applicant would, as the steps below describe.</p>",
          actions=[("Renew by mail (State Department)", STATE_MAIL),
                   ("Renew online (State Department)", STATE_ONLINE)]),
     step("Renew by mail",
          "<ul><li><b>Fill out Form DS-82</b> with the State Department&rsquo;s Form Filler, "
          "print it on single-sided paper, and <b>sign and date it</b> before you mail it.</li>"
          "<li><b>Send your most recent passport.</b> It comes back to you in a separate "
          "mailing.</li>"
          "<li><b>If your name has changed</b>, send a certified copy of the legal document that "
          "changed it, such as a marriage certificate, divorce decree or court order. It comes "
          "back to you too.</li>"
          "<li><b>Staple one photo</b> to the application, with four staples in the corners, and "
          "do not bend it.</li>"
          "<li><b>Pay by personal check or money order</b> payable to the U.S. Department of "
          "State, with the applicant&rsquo;s full name and date of birth on the front. Do not "
          "send cash. The fee depends on whether you renew a book, a card or both; the page "
          "below lists it.</li></ul>"
          "<p>Mail it through the U.S. Postal Service. From New Hampshire, routine service goes "
          "to National Passport Processing Center, Post Office Box 90155, Philadelphia, PA "
          "19190-0155. For expedited service, for an extra fee, write &ldquo;EXPEDITE&rdquo; on "
          "the envelope and mail it to National Passport Processing Center, Post Office Box "
          "90955, Philadelphia, PA 19190-0955. A post office should not charge you its facility "
          "fee or review a renewal form.</p>",
          actions=[("Renew by mail (State Department)", STATE_MAIL)]),
     step("Fill out Form DS-11, and do not sign it yet",
          "<p>A first passport, a passport for a child under 16, and one for anyone who cannot "
          "renew are applied for in person. Fill out Form DS-11 with the State "
          "Department&rsquo;s form filler and print it on one side of the paper, but <b>do not "
          "sign it</b>: you sign it in front of the acceptance agent, under oath.</p>",
          actions=[("Apply for an adult passport (State Department)", STATE_ADULT)]),
     step("Gather your documents and a photo",
          "<ul><li><b>Proof of U.S. citizenship.</b> If you were born in the United States, this "
          "is generally a certified birth certificate showing your full name, the date and place "
          "of your birth and your parents&rsquo; full names, with the registrar&rsquo;s signature "
          "and seal. If you were born in New Hampshire, your town or city clerk can issue one "
          "(the guide linked at the end of this page says how). It must be on paper: a "
          "digital or mobile birth certificate is not accepted. A full-validity U.S. passport, "
          "a Consular Report of Birth Abroad, or a certificate of naturalization or citizenship "
          "also proves it.</li>"
          "<li><b>A photo ID</b>, such as a driver&rsquo;s license. If it is from another state, "
          "bring a second photo ID.</li>"
          "<li><b>A photocopy of the front and back</b> of both the citizenship document and the "
          "ID, on one side of plain letter-size paper.</li>"
          "<li><b>A photo</b> that meets the State Department&rsquo;s rules. Do not staple it to "
          "the form. Many post offices take one for a fee.</li></ul>"
          "<p>No birth certificate that meets the rules? The questions below say what the State "
          "Department accepts instead.</p>"),
     step("Make an appointment and apply",
          "<p>Thousands of post offices accept first-time applications, by appointment: book "
          "online, at a post office&rsquo;s self-service kiosk, or at the counter. Some offer "
          "limited walk-in hours. Libraries, local government offices and the clerks of some "
          "courts accept applications too; ask the facility whether you need an "
          "appointment.</p>"
          "<p>You pay two separate fees. The State Department&rsquo;s fee goes in with your "
          "application, by check or money order payable to &ldquo;U.S. Department of "
          "State&rdquo;, with your name and date of birth in the memo line, not by card. The "
          "facility&rsquo;s own acceptance fee is paid there, and a post office takes cards. "
          "The State Department&rsquo;s adult passport page lists the current amounts.</p>",
          actions=[("Book at a post office (USPS)", USPS_PASSPORTS),
                   ("Fees and how to apply (State Department)", STATE_ADULT)]),
     step("A passport for a child under 16",
          "<p>The child goes to the appointment, with both parents or guardians. A child&rsquo;s "
          "passport cannot be renewed: you apply in person each time. Bring the child&rsquo;s "
          "proof of citizenship, which, if it is a U.S. birth certificate, also shows who the "
          "parents are, and each parent&rsquo;s photo ID, with photocopies.</p>"
          "<p>If one parent cannot come, that parent signs the Statement of Consent, Form "
          "DS-3053, before a notary, and you bring it, with a photocopy of the ID they showed "
          "the notary, within 90 days of its signing.</p>",
          actions=[("A child under 16 (State Department)", STATE_CHILD)]),
     step("If you travel soon",
          "<p>Routine processing takes 4 to 6 weeks, and expedited service, for an extra fee, 2 "
          "to 3 weeks. Neither counts the mail, which can add up to 2 weeks each way; you can "
          "pay for faster shipping both ways. The State Department&rsquo;s page has the current "
          "times.</p>"
          "<p>If you travel abroad in less than 3 weeks, make an appointment at a passport "
          "agency or center once you are within 14 days of your trip, or 28 days if you need a "
          "foreign visa. New Hampshire has one: the <b>National Passport Center in "
          "Portsmouth</b>. Appointments are free, through the State Department&rsquo;s online "
          "appointment system; if you have already applied, call 1-877-487-2778. Anyone who "
          "asks you to pay for an appointment is not the State Department.</p>",
          actions=[("Get your passport fast (State Department)", STATE_FAST),
                   ("Make an appointment at a passport agency", STATE_APPOINT)])],
    [("Apply for Your Adult Passport (U.S. Department of State)", STATE_ADULT),
     ("Renew Your Passport by Mail (U.S. Department of State)", STATE_MAIL),
     ("Renew Your Passport Online (U.S. Department of State)", STATE_ONLINE),
     ("Apply for a Child's Passport Under 16 (U.S. Department of State)", STATE_CHILD),
     ("Get Your Passport Fast (U.S. Department of State)", STATE_FAST),
     ("Make an Appointment at a Passport Agency (U.S. Department of State)", STATE_APPOINT),
     ("Passports (U.S. Postal Service)", USPS_PASSPORTS),
     ("Execution of passport application, 22 CFR 51.21 (federal)", CFR_PP_EXECUTE),
     ("Passport agents and acceptance agents, 22 CFR 51.22 (federal)", CFR_PP_AGENTS),
     ("Minors, 22 CFR 51.28 (federal)", CFR_PP_MINORS),
     ("Persons born in the United States, 22 CFR 51.42 (federal)", CFR_PP_BIRTH),
     ("Validity of passports, 22 CFR 51.4 (federal)", CFR_PP_VALID)],
    [],
    [# Federal rules, read at eCFR on 25 October 2026.
     claim("Apply in person: a minor, a person never issued a passport, one not issued a 10-year "
           "passport within 15 years, or anyone not eligible to apply by mail; verify by oath or "
           "affirmation before the agent and sign; provide photographs; pay the fees. By mail: "
           "a person previously issued a passport valid for 10 years, the most recent issued at "
           "16 years of age or older, applying not more than 15 years after its issue date, "
           "submitting it with the application; on-line on the conditions in (b)(2).",
           CFR_PP_EXECUTE, PP_READ),
     claim("Passport acceptance agents include an employee of the clerk of a federal or state "
           "court of record and a postal employee at a post office selected to accept "
           "applications.", CFR_PP_AGENTS, PP_READ),
     claim("A minor under 16 appears in person; both parents or each legal guardian execute the "
           "application, first or renewal; or one, with a notarized statement of consent from "
           "the other or evidence of sole parentage or custody: a birth certificate naming only "
           "the applying parent, a death certificate, an adoption decree, or a court order "
           "granting sole legal custody.", CFR_PP_MINORS, PP_READ),
     claim("A birth certificate showing the full name, place and date of birth and the full name "
           "of the parents, signed by the official custodian of birth records with the seal, "
           "filed within one year of birth; otherwise secondary evidence: hospital birth "
           "certificates, baptismal certificates, medical and school records, and others.",
           CFR_PP_BIRTH, PP_READ),
     claim("A passport issued at 16 years of age or older is valid for 10 years (ten years) from "
           "the date of issue; under 16 years of age, for 5 years.", CFR_PP_VALID, PP_READ),
     # The Postal Service's page, read on 25 October 2026.
     claim("Thousands of Post Offices accept first-time passport applications; you must renew by "
           "mail or online, you cannot renew in person; appointments by the online scheduler, a "
           "lobby self-service kiosk or the retail counter, with limited walk-in hours at select "
           "locations; bring the unsigned application, proof of identity and of citizenship with "
           "a photocopy of the front and back of each, and a photo, which many Post Offices take "
           "for a fee; DO NOT SIGN YOUR APPLICATION, a Postal employee must witness your "
           "signature; State Department fees are mailed with the application, payable to U.S. "
           "Department of State, not by credit or debit card; the acceptance fee is paid at the "
           "Post Office, by check, money order, debit or credit card.", USPS_PASSPORTS, PP_READ),
     # The State Department's own pages, from the person's printouts of 25
     # October 2026, at the addresses they show.
     claim("First-time adults and those who do not qualify for renewal must apply in person at "
           "an acceptance facility; Form Filler, print on single-sided paper; do not sign your "
           "form until asked to do so by a passport acceptance agent; evidence of U.S. "
           "citizenship: a U.S. birth certificate, a full validity, undamaged U.S. passport, a "
           "Consular Report of Birth Abroad, or a Certificate of Naturalization or Citizenship; "
           "adults who do not qualify for renewal because their passport was lost, stolen, or "
           "damaged, issued over 15 years ago, or issued when they were under age 16; normal "
           "wear such as folded pages or small bends does not count as a damaged passport; "
           "we do not accept digital evidence such as a mobile or electronic birth certificate; "
           "a physical photo ID, the most common a driver's license; if your ID is from a "
           "different state, bring a second photo ID; photocopies on 8.5 by 11 inch paper, a "
           "single side; do not attach or staple your photo; if you owe over $2500 in "
           "child support or have seriously delinquent tax debt, your application "
           "will be delayed or denied; 2 fees, the application fee to the U.S. Department of "
           "State by check or money order with the applicant's name and date of birth in the "
           "memo, the acceptance fee to the facility; acceptance facilities such as a post "
           "office, library, or local government office, check with the facility to see if you "
           "need to make an appointment.", STATE_ADULT, PP_STATE_READ),
     # The State Department's Renew by Mail page, the person's printout of 26 October 2026.
     claim("You can renew by mail if: you can submit your most recent passport with your "
           "application; your passport has never been reported lost or stolen; was issued "
           "within the last 15 years; was issued when you were age 16 or older and was valid for "
           "10 years; was issued in your current name, or you can provide a document like a "
           "marriage certificate, divorce decree, or court order to show you have changed your "
           "name; is not damaged, other than normal wear and tear. Fill out your form and print "
           "it: Form Filler, single-sided paper; sign and date your renewal form before mailing "
           "it; Form DS-82; you must mail your application; postal employees should not charge "
           "you a facility fee or review your form and documents. We will return your most "
           "recent passport book or card in a separate mailing. Name change: a certified copy "
           "of the legal name change document, such as a marriage certificate, divorce decree, "
           "court-ordered name change document, returned in a separate mailing. You must provide "
           "1 photo; staple your photo to the application, four staples vertically in the "
           "corners; do not bend the photo. Your fee depends on what document you are renewing; "
           "pay using a personal check or money order payable to the U.S. Department of State; "
           "do not send cash; write the full name and date of birth of the applicant on the "
           "front. Mail your application using the United States Postal Service; routine "
           "service, any other state: National Passport Processing Center, Post Office Box "
           "90155, Philadelphia, PA 19190-0155; expedited service: write EXPEDITE on the outside "
           "of the envelope, National Passport Processing Center, Post Office Box 90955, "
           "Philadelphia, PA 19190-0955.", STATE_MAIL, PP_MAIL_READ),
     claim("Renew online if: the passport is (or was) valid for 10 years, expiring within 1 "
           "year or expired less than 5 years ago; you are age 25 or older; not changing your "
           "name or sex; not traveling for at least 6 weeks, online renewals cannot be "
           "expedited; located in a U.S. state or territory; you have your passport, not "
           "damaged, not reported lost or stolen; credit or debit card; we will cancel the "
           "passport you are renewing; do not mail it, keep it; the only official place to "
           "renew online is opr.travel.state.gov, other websites may be fraudulent and charge "
           "extra fees.", STATE_ONLINE, PP_STATE_READ),
     claim("Both parents or guardians must be present with the child applying in person; you "
           "cannot renew a child's passport, you must apply in-person each time; valid for 5 "
           "years; a U.S. birth certificate shows citizenship and relationship; both parents' "
           "photo IDs and photocopies; if 1 parent cannot go, they sign Statement of Consent "
           "Form DS-3053 before a certified notary public, with a photocopy of the photo ID "
           "presented to the notary, submitted within 90 days after it is notarized; sole "
           "custody: a court order granting sole custody, a certified birth certificate or "
           "adoption decree listing you as the only parent, or the deceased parent's death "
           "certificate.", STATE_CHILD, PP_STATE_READ),
     claim("Routine service takes 4-6 weeks and expedited 2-3 weeks, for a fee, neither "
           "including mailing times, which may add 2 weeks; faster shipping both ways for a "
           "fee; urgent: traveling in less than 2-3 weeks, make an appointment at a passport "
           "agency or center when you are within 14 calendar days of your international travel "
           "date, or 28 days if you need a foreign visa.", STATE_FAST, PP_STATE_READ),
     claim("Passport agencies and centers accept appointments for urgent travel abroad in the "
           "next 14 days or a foreign visa in the next 28 days; we do not charge a fee to make "
           "appointments; the Online Passport Appointment System; if you already applied, dial "
           "877-487-2778; National Passport Center, Portsmouth, NH.", STATE_APPOINT,
           PP_STATE_READ)],
    more=civics.faq(
        ("Are other websites that offer to renew my passport safe?",
         "<p>Renew only at the State Department&rsquo;s own site: others that offer to do it for "
         "you charge extra and put your information at risk.</p>"),
        ("What if I have no birth certificate that meets the rules?",
         "<p>If you have no birth certificate that meets the rules, the State Department accepts "
         "other early records of your birth instead, such as hospital, baptismal, medical or "
         "school records. Its adult passport page says what to bring.</p>"),
        ("Can unpaid child support or taxes stop an application?",
         "<p>Unpaid child support over the State Department&rsquo;s limit, or seriously "
         "delinquent federal tax debt, will delay or stop an application: settle it "
         "first.</p>"),
        ("What if I alone have custody of my child?",
         "<p>Bring proof of it instead of the other parent&rsquo;s consent, such as a court order "
         "granting you sole custody, a birth certificate or adoption decree naming only you, or "
         "the other parent&rsquo;s death certificate.</p>"),
        ("How long is a passport good for?",
         "<p>A passport issued to someone under 16 is valid for 5 years; one issued at 16 or older, "
         "for 10.</p>")),
    see=[("How to get a birth, death, marriage or divorce certificate", "/guides/vital-records.html"),
         ("How to get a REAL ID", "/guides/real-id.html")],
    figures=[fig("10 years", CFR_PP_VALID, "valid for 10 years"),
             fig("15 years", CFR_PP_EXECUTE, "within 15 years"),
             fig("5 years", CFR_PP_VALID, "for 5 years"),
             fig("6 weeks", STATE_ONLINE, "not traveling for at least 6 weeks"),
             fig("90 days", STATE_CHILD, "within 90 days after it is notarized"),
             fig("4 to 6 weeks", STATE_FAST, "Routine service takes 4-6 weeks"),
             fig("2 to 3 weeks", STATE_FAST, "expedited 2-3 weeks"),
             fig("2 weeks", STATE_FAST, "may add 2 weeks"),
             fig("3 weeks", STATE_FAST, "traveling in less than 2-3 weeks"),
             fig("14 days", STATE_APPOINT, "urgent travel abroad in the next 14 days"),
             fig("28 days", STATE_APPOINT, "a foreign visa in the next 28 days")])

GUIDES += [PASSPORT]


# ---------------------------------------------------------------------------
# MEDICARE AND SOCIAL SECURITY (the person, 25 October 2026: "medicare and
# social security guides"; first asked for as "how to get help with managing
# your social security, medicare, or medicaid"). Both are federal; signing up
# for Medicare is done through Social Security, and the help with its costs
# -- the Medicare Savings Programs -- is the state's, under RSA 167:4-g (2026,
# 279:3, in force 5 September 2026). Read on 25 October 2026: medicare.gov's
# pages, which answer a cloud session, the Social Security Administration's
# entry at USA.gov for its number, and the federal rules at eCFR. ssa.gov
# refuses this machine; its pages are the person's printouts of 25 October
# 2026 (the my Social Security page printed without its address; its title
# and words are that page's). The Department of Health and Human Services'
# page on the savings programs still waits for a printout.
# Medicaid itself is the food and health guide's.
#
# THE GROUNDWORK FIRST (the person, 26 October 2026: the guide "was very
# dense and I didn't quite understand things like part A and part B, so it
# may be better to have a separate explanation for each with a bit of
# groundwork on how the programs are structured before jumping into the step
# by step"). Step 1 says what each program is and who runs it, from the same
# printouts and pages, and the steps after it say only what to do. What each
# part covers, Part C's name and what Original Medicare is are Medicare.gov's
# "Parts of Medicare", the person's printout of 26 October 2026 (medicare4),
# in its own words; it states no costs, so the guide prints none.
#
# WHAT IT COSTS. Medicare.gov's "Costs", the person's printout of 26 October
# 2026 (medicare5): the kinds of cost each part carries -- premium,
# deductible, coinsurance, copayment, the yearly out-of-pocket limits -- in
# its words. Its dollar amounts and percentages are federal, set each year,
# and not a statute's (guides.FIGURE), so none is printed: the guide links
# the page, which lists the current year's.
# ---------------------------------------------------------------------------
MC_READ = "2026-10-25"
SSA_PAGES_READ = "2026-10-25"        # the person's printouts of ssa.gov
DHHS_MSP_READ = "2026-10-25"         # the person's printout
MEDICARE_START = ("https://www.medicare.gov/basics/get-started-with-medicare/sign-up/"
                  "when-does-medicare-coverage-start")
MEDICARE_AUTO = ("https://www.medicare.gov/basics/get-started-with-medicare/sign-up/"
                 "how-do-i-sign-up-for-medicare")
MEDICARE_SIGNUP = ("https://www.medicare.gov/basics/get-started-with-medicare/sign-up/"
                   "ready-to-sign-up-for-part-a-part-b")
MEDICARE_PLANS = ("https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/"
                  "joining-a-plan")
MEDICARE_MSP = "https://www.medicare.gov/basics/costs/help/medicare-savings-programs"
MEDICARE_EXTRA = "https://www.medicare.gov/basics/costs/help/drug-costs"
MEDICARE_CONTACT = "https://www.medicare.gov/talk-to-someone"
MEDICARE_PARTS = ("https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/"
                  "parts-of-medicare")
MC_PARTS_READ = "2026-10-26"         # the person's printout (medicare4)
MEDICARE_COSTS = "https://www.medicare.gov/basics/costs/medicare-costs"
MC_COSTS_READ = "2026-10-26"         # the person's printout (medicare5)
USA_SSA = "https://www.usa.gov/agencies/social-security-administration"
SSA_APPLY = "https://www.ssa.gov/apply"
SSA_MEDICARE = "https://www.ssa.gov/medicare/sign-up"
SSA_ACCOUNT = "https://www.ssa.gov/myaccount/"
DHHS_MSP = ("https://www.dhhs.nh.gov/programs-services/medicaid/"
            "nh-medicaid-medical-assistance-eligibility/medicare-beneficiaries")
CFR_OLD_AGE = "https://www.ecfr.gov/current/title-20/section-404.310"

MEDICARE = guide(
    "medicare-and-social-security",
    "How to Sign Up for Medicare and Social Security, and Get Help With the Costs",
    "When and how to sign up for Medicare, applying for Social Security retirement benefits, "
    "choosing your coverage, and the state and federal programs that help pay Medicare's costs, "
    "with free counseling in New Hampshire.",
    "Social Security pays benefits to people who worked and paid Social Security taxes, when "
    "they retire or become disabled, and to some of their families. Medicare is health insurance "
    "for people 65 or older and some younger people with disabilities. You sign up for Medicare through Social Security, generally in the 7 months "
    "around your 65th birthday, and if you already get Social Security benefits you are usually "
    "enrolled automatically. Retirement benefits can start as early as age 62. If paying for "
    "Medicare is hard, state and federal programs can help with the costs: apply even if you are "
    "not sure you qualify. New Hampshire&rsquo;s Aging and Disability Resource Centers give free, "
    "one-on-one help.",
    [ask("Do you already get Social Security benefits?",
         [("Yes", "You are usually enrolled in Medicare automatically. Watch for your card."),
          ("No", "Sign up through Social Security in the 7 months around your 65th birthday.")]),
     box("Choose Original Medicare or a Medicare Advantage Plan, and a drug plan. Review it every "
         "fall, October 15 to December 7."),
     box("If the costs are hard to pay, apply for a Medicare Savings Program and Extra Help.")],
    [step("Know how the programs fit together",
          "<p><b>Social Security</b> is a set of programs run by the Social Security "
          "Administration:</p><ul>"
          "<li><b>Retirement benefits</b>, for people who worked and paid Social Security taxes, "
          "starting as early as age 62.</li>"
          "<li><b>Disability benefits</b>, for people who worked and paid Social Security taxes "
          "long enough and have a medical condition that makes it hard or impossible to work and "
          "will last at least one year or result in death.</li>"
          "<li><b>Family and survivor benefits</b>, for the spouse, former spouse, child or "
          "dependent parent of someone who worked and paid Social Security taxes.</li>"
          "<li><b>Supplemental Security Income (SSI)</b>, a separate program for people who are "
          "blind, have a disability, or are 65 or older, and have little or no income or "
          "assets.</li></ul>"
          "<p><b>Medicare</b> is the country&rsquo;s health insurance program for people 65 or "
          "older, and for some younger people (see Common Questions below). It comes in "
          "parts:</p>"
          + table("The parts of Medicare",
                  ["Part", "What it helps cover", "How you get it"],
                  [["Part A (Hospital Insurance)", "Inpatient care in hospitals, skilled nursing "
                    "facility care, hospice care, and home health care.",
                    "Through Social Security. Many people are enrolled automatically (Medicare, step 1)."],
                   ["Part B (Medical Insurance)", "Services from doctors and other health care "
                    "providers, outpatient care, home health care, durable medical equipment "
                    "(like wheelchairs, walkers and hospital beds), and many preventive services "
                    "(like screenings, shots or vaccines, and yearly wellness visits). It has a "
                    "premium, and signing up late can add a penalty for as long as you have it.",
                    "Through Social Security, with Part A, or later on its own. You can put it off "
                    "while a job&rsquo;s group health plan covers you."],
                   ["Part C (Medicare Advantage)", "An alternative to Original Medicare: a private "
                    "health plan that Medicare approved, which bundles Part A, Part B and usually "
                    "Part D. You may need to use the plan&rsquo;s network of doctors, and most plans "
                    "offer extra benefits Original Medicare does not cover, like vision, hearing "
                    "and dental. You need both Part A and Part B to join one.",
                    "You choose one on Medicare.gov (Medicare, step 3)."],
                   ["Part D (Drug coverage)", "The cost of prescription drugs. Plans are run by "
                    "private insurance companies that follow rules set by Medicare.",
                    "You add a drug plan to Original Medicare, or get it in a Medicare Advantage "
                    "Plan with drug coverage, on Medicare.gov (Medicare, step 3)."]])
          + "<p><b>Original Medicare</b> is Part A and Part B. With it you can use any doctor or "
          "hospital that takes Medicare, join a separate drug plan, and buy supplemental "
          "coverage, called <b>Medigap</b>, from a private company to help pay your share of the "
          "costs. The other way is a Medicare Advantage Plan. You choose when you first sign up, "
          "and can change at certain times of the year.</p>"
          "<p><b>What Medicare costs</b> depends on the coverage you have and the services you "
          "use. The costs come in a few kinds:</p><ul>"
          "<li>A <b>premium</b>, paid each month. Most people pay no premium for Part A, because "
          "they or a spouse paid Medicare taxes long enough while working, and no one who gets "
          "Medicare before turning 65 pays one. Part B has a monthly premium, which you pay even "
          "if you use no Part B services, and which is higher for some people depending on "
          "income.</li>"
          "<li>A <b>deductible</b>, what you pay before Original Medicare starts to pay: for "
          "Part A, once for each hospital benefit period, which can be more than once a year; "
          "for Part B, once each year.</li>"
          "<li><b>Coinsurance</b>, your share of the cost of each covered service after you have "
          "paid your deductible, and <b>copayments</b>, such as the one a hospital charges for "
          "each outpatient service.</li></ul>"
          "<p>A Medicare Advantage Plan&rsquo;s and a drug plan&rsquo;s premiums and other costs "
          "vary by plan. Medicare.gov&rsquo;s Costs page lists the current amounts, several of "
          "which can change each year.</p>"
          "<p>You sign up for Part A and Part B through Social Security, which can take your "
          "premiums out of your benefit payments. You choose a Medicare Advantage Plan or a drug "
          "plan on Medicare.gov.</p>"
          "<p><b>Help with the costs</b> comes from two programs: the state&rsquo;s <b>Medicare "
          "Savings Programs</b>, which help pay Medicare premiums and, for some people, other "
          "costs; and the federal <b>Extra Help</b> program, which pays part of the cost of drug "
          "coverage. The step &ldquo;Get help paying the costs&rdquo;, below, says who qualifies and how "
          "to apply.</p>",
          actions=[("What Medicare costs (Medicare)", MEDICARE_COSTS)]),
     step("Know when to sign up for Medicare",
          "<p>Your first chance is your Initial Enrollment Period: 7 months, starting 3 months "
          "before the month you turn 65 and ending 3 months after it. Coverage always starts on "
          "the first of a month, and signing up before your birthday month means it starts "
          "sooner.</p>"
          "<p><b>You are enrolled automatically</b> in Part A and Part B "
          "if you start getting Social Security benefits at least 4 months "
          "before you turn 65, or after you have received disability benefits for 24 months. "
          "Your Medicare card comes in the mail.</p>"
          "<p><b>If you miss your first chance,</b> you may have to wait for the General "
          "Enrollment Period, January 1 to March 31, and pay a monthly late enrollment penalty "
          "for as long as you have Part B. Some situations open a Special Enrollment "
          "Period.</p>",
          actions=[("When coverage starts (Medicare)", MEDICARE_START),
                   ("Do I get Medicare automatically? (Medicare)", MEDICARE_AUTO)]),
     step("Sign up through Social Security",
          "<p>Medicare Part A and Part B are signed up for through the Social Security "
          "Administration, not through Medicare. The easiest way is online, with a my Social "
          "Security account, if you are 65 or older. You can also call Social Security at "
          "1-800-772-1213, Monday through Friday, 8:00&nbsp;AM to 7:00&nbsp;PM (TTY 1-800-325-0778), and "
          "make an appointment.</p>",
          actions=[("Sign up for Medicare (Medicare)", MEDICARE_SIGNUP),
                   ("Sign up for Medicare (Social Security)", SSA_MEDICARE)]),
     step("Choose your coverage, and review it every fall",
          "<p>With Part A and Part B, you choose between Original Medicare, with or without a "
          "drug plan, and a Medicare Advantage Plan. Each fall, from <b>October 15 to December "
          "7</b>, you can join, switch or drop a plan, and the change starts January 1.</p>"
          "<p>For free help comparing plans, call your Aging and Disability Resource "
          "Center (below), or 1-800-MEDICARE (1-800-633-4227), any hour of any day.</p>",
          actions=[("Joining a plan (Medicare)", MEDICARE_PLANS)]),
     step("Get help paying the costs",
          "<p>New Hampshire&rsquo;s <b>Medicare Savings Programs</b> are together called the "
          "<b>Medicare Beneficiaries Savings Program</b>, or the Buy-In program. They are for "
          "people with low incomes who are eligible for Medicare, and your home and vehicles do "
          "not count against their limits:</p>"
          + table("What each Medicare Savings Program pays",
                  ["Program", "What it helps pay"],
                  [["QMB", "Part A and Part B premiums, penalties for signing up late, deductibles "
                    "and coinsurance. Medicare providers may not bill you for covered care."],
                   ["SLMB", "The Part B premium and penalties for signing up late."],
                   ["QDWI", "The Part A premium, for people with disabilities who work and have "
                    "lost Medicare because of their earnings."]])
          + "<p>Apply to the Department of Health and Human Services through NH Easy, under "
          "Medicare beneficiary assistance; its Customer Service Center answers at 1-844-ASK-DHHS "
          "(1-844-275-3447), Monday through Friday, 8:00&nbsp;AM to 4:00&nbsp;PM. Medicare advises applying "
          "even if you do not think you qualify.</p>"
          "<p><b>Extra Help</b> is a federal program that pays part of your drug plan&rsquo;s "
          "costs. You get it automatically if you have full-benefit Medicaid, a Medicare Savings "
          "Program or "
          "SSI. Otherwise apply through Social Security.</p>",
          actions=[("NH Easy", NHEASY),
                   ("Medicare Savings Programs (NH Department of Health and Human Services)", DHHS_MSP),
                   ("Extra Help (Medicare)", MEDICARE_EXTRA)],
          law=["RSA 167:4-g"]),
     step("Apply for Social Security retirement benefits",
          "<p>You can get retirement benefits from age 62 if you have worked and paid Social "
          "Security taxes for at least 10 years, and you must apply for them: they do not "
          "start on their own. Apply online on Social Security&rsquo;s Apply page, which also "
          "lets you enroll in Medicare, or call 1-800-772-1213.</p>",
          actions=[("Apply for benefits (Social Security)", SSA_APPLY)]),
     step("Manage your benefits online",
          "<p>A <b>my Social Security</b> account lets you change your address or direct "
          "deposit, print proof of your benefits or a tax form, request a replacement Social "
          "Security card, and see your Social Security Statement and earnings record, without "
          "a call or a visit. You create it through Login.gov or ID.me, with an email address, "
          "a government-issued photo ID and a phone.</p>",
          actions=[("my Social Security", SSA_ACCOUNT)])],
    [("When Does Medicare Coverage Start? (Medicare)", MEDICARE_START),
     ("How Do I Sign Up for Medicare? (Medicare)", MEDICARE_AUTO),
     ("Ready to Sign Up for Part A and Part B (Medicare)", MEDICARE_SIGNUP),
     ("Joining a Plan (Medicare)", MEDICARE_PLANS),
     ("Medicare Savings Programs (Medicare)", MEDICARE_MSP),
     ("Help With Drug Costs (Medicare)", MEDICARE_EXTRA),
     ("Contact Medicare (Medicare)", MEDICARE_CONTACT),
     ("Parts of Medicare (Medicare)", MEDICARE_PARTS),
     ("Costs (Medicare)", MEDICARE_COSTS),
     ("Social Security Administration (USA.gov)", USA_SSA),
     ("Apply for Social Security Benefits (Social Security Administration)", SSA_APPLY),
     ("Sign Up for Medicare (Social Security Administration)", SSA_MEDICARE),
     ("my Social Security (Social Security Administration)", SSA_ACCOUNT),
     ("Medicare Beneficiaries Savings Program (Department of Health and Human Services)", DHHS_MSP),
     ("When am I entitled to old-age benefits?, 20 CFR 404.310 (federal)", CFR_OLD_AGE),
     ("Public Assistance to Blind, Aged, or Disabled Persons, RSA 167", "/laws/167")],
    ["167"],
    [# medicare.gov, read on 25 October 2026.
     claim("Initial Enrollment Period: 7 months, starting 3 months before you turn 65 and ending "
           "3 months after the month you turn 65; coverage always starts on the first of the "
           "month; sign up before the month you turn 65 and Part B starts the month you turn "
           "65, later and it starts the next month; General Enrollment Period January 1-March "
           "31, coverage the month after; a monthly late enrollment penalty for as long as you "
           "have Part B; Special Enrollment Periods in certain situations.", MEDICARE_START,
           MC_READ),
     claim("Automatic Part A and Part B at 65 if you start getting Social Security benefits at "
           "least 4 months before you turn 65; automatically after getting disability benefits "
           "for 24 months; a welcome package with the Medicare card in the mail.",
           MEDICARE_AUTO, MC_READ),
     claim("To sign up for Part A and/or Part B, contact the Social Security Administration; "
           "apply online, the easiest and fastest way, with a my Social Security account; adding "
           "Part B on losing job-based coverage, the employer fills out form CMS-L564, sent to "
           "the local Social Security office; the Medicare Number to create a Medicare account "
           "on Medicare.gov.", MEDICARE_SIGNUP, MC_READ),
     claim("Original Medicare with a drug plan, or a Medicare Advantage Plan, which needs both "
           "Part A and Part B; Open Enrollment Period October 15-December 7: join, drop or "
           "switch, coverage January 1.", MEDICARE_PLANS, MC_READ),
     claim("Medicare Savings Programs are run by your state and pay Part A and Part B premiums, "
           "and with QMB deductibles, coinsurance and copayments, which Medicare providers are "
           "not allowed to bill; apply through your state; even if you don't think you qualify, "
           "you should still apply.", MEDICARE_MSP, MC_READ),
     claim("Extra Help pays Medicare drug coverage costs; automatic with full-benefit Medicaid, "
           "a Medicare Savings Program or SSI; otherwise apply; Social Security sends "
           "information to your state to initiate an MSP application unless you tell them "
           "not to.", MEDICARE_EXTRA, MC_READ),
     claim("1-800-MEDICARE (1-800-633-4227), 24 hours a day, 7 days a week; TTY 1-877-486-2048; "
           "contact SSA to sign up for Part A and Part B; contact your state for Medicare "
           "Savings Programs; SHIPs give free counseling.", MEDICARE_CONTACT, MC_READ),
     claim("Social Security Administration, toll-free number 1-800-772-1213.", USA_SSA, MC_READ),
     # Medicare.gov's Parts of Medicare, the person's printout of 26 October 2026.
     claim("Part A (Hospital Insurance) helps cover inpatient care in hospitals, skilled nursing "
           "facility care, hospice care, and home health care. Part B (Medical Insurance) helps "
           "cover services from doctors and other health care providers, outpatient care, home "
           "health care, durable medical equipment (like wheelchairs, walkers, hospital beds), "
           "and many preventive services (like screenings, shots or vaccines, and yearly "
           "Wellness visits). Part D (Drug coverage) helps cover the cost of prescription drugs; "
           "you join a Medicare drug plan in addition to Original Medicare, or get it by joining "
           "a Medicare Advantage Plan with drug coverage; plans are run by private insurance "
           "companies that follow rules set by Medicare. Medicare Supplemental Insurance "
           "(Medigap): extra insurance you can buy from a private company that helps pay your "
           "share of costs in Original Medicare. When you first sign up and during certain times "
           "of the year, you can choose; 2 main ways: Original Medicare includes Part A and Part "
           "B, any doctor or hospital that takes Medicare, a separate drug plan, supplemental "
           "coverage; Medicare Advantage (also known as Part C) offers an alternative to "
           "Original Medicare, a private health plan that Medicare approved, bundled plans "
           "including Part A, Part B, and usually Part D; you may need to use doctors in the "
           "plan's network; most plans offer extra benefits Original Medicare doesn't cover, "
           "like vision, hearing, dental. Medicare is federal health insurance for anyone age 65 "
           "and older, and some people under 65 with certain disabilities or conditions; "
           "Medicaid is a joint federal and state program that provides health coverage for "
           "certain low-income people, families and children, pregnant women, the elderly, and "
           "people with disabilities; if you qualify, you can have both Medicare and Medicaid.",
           MEDICARE_PARTS, MC_PARTS_READ),
     # Medicare.gov's Costs, the person's printout of 26 October 2026.
     claim("What you pay for Medicare depends on the coverage you have and services you use. "
           "Part A premium: $0 for most people (because they or a spouse paid Medicare taxes "
           "long enough while working); if you get Medicare earlier than age 65, you won't pay "
           "a Part A premium; this is sometimes called premium-free Part A. If you don't qualify "
           "for premium-free Part A you might be able to buy it, the amount depending on how "
           "long you or your spouse worked and paid Medicare taxes; you also have to sign up for "
           "Part B to buy Part A; if you don't buy Part A when you're first eligible for "
           "Medicare (usually when you turn 65), you might pay a penalty. Part A deductible for "
           "each inpatient hospital benefit period, before Original Medicare starts to pay; no "
           "limit to the number of benefit periods you can have in a year, so you may pay the "
           "deductible more than once in a year. Part B premium each month (or higher depending "
           "on your income); the amount can change each year; you'll pay the premium each "
           "month, even if you don't get any Part B-covered services. Part B deductible before "
           "Original Medicare starts to pay; you pay this deductible once each year. "
           "Coinsurance: usually a share of the cost for each Medicare-covered service or item "
           "after you've paid your deductible. You'll also pay a copayment to the hospital for "
           "each service you get in a hospital outpatient setting. Original Medicare: there's no "
           "yearly limit on what you pay out-of-pocket, unless you have supplemental coverage, "
           "like a Medicare Supplement Insurance (Medigap) policy or join a Medicare Advantage "
           "Plan (Part C). Medicare Advantage: premiums and other costs vary by plan; these "
           "amounts can change each year; you must have Part B and keep paying your Part B "
           "premium to stay in your plan; out-of-pocket limit varies by plan; once you pay the "
           "plan's limit, the plan pays your covered health services for the rest of the "
           "calendar year. Part D: premium varies by plan; you may have to pay more, depending "
           "on your income; 2 ways to avoid paying a Part D late enrollment penalty: get "
           "Medicare drug coverage when you first get Medicare Part A and/or Part B, and don't "
           "go 63 days or more without creditable drug coverage (coverage that's similar in "
           "value to Part D); deductibles, copayments and coinsurance vary by plan and pharmacy; "
           "a yearly out-of-pocket limit that includes your deductible, out-of-pocket spending, "
           "and certain payments made on your behalf, like through the Extra Help program; if "
           "you qualify for Extra Help, you won't have to pay the Part D late enrollment "
           "penalty. Medigap: premium varies based on which policy you buy, where you live, and "
           "other factors; the amount can change each year; you must have Part B and keep "
           "paying your Part B premium to keep your Medigap policy; Medigap usually helps pay "
           "your portion of the costs (like deductibles and coinsurance) for services that "
           "Part A and Part B cover in Original Medicare.", MEDICARE_COSTS, MC_COSTS_READ),
     claim("Entitled to old-age benefits if at least 62 years old, fully insured, and you "
           "apply.", CFR_OLD_AGE, MC_READ),
     claim("The department shall administer the Medicare savings program as described in 42 "
           "U.S.C. section 1396a(a)(10)(E).", "RSA 167:4-g", MC_READ),
     # Social Security's and the Department's own pages, from the person's printouts.
     claim("Retirement benefits: you're at least 62 years old; you've worked and paid Social "
           "Security taxes for at least 10 years; you may also enroll in Medicare if you are "
           "eligible. Family benefits: you're a spouse, ex-spouse, child, or dependent parent of "
           "someone who worked and paid Social Security taxes. Disability benefits: you have a "
           "medical condition that will last at least one year or result in death; your "
           "condition makes it hard or impossible to work; you worked and paid Social Security "
           "taxes long enough. Survivor benefits: a spouse, ex-spouse, child, or dependent parent "
           "of someone who worked and paid Social Security taxes before they died. Supplemental "
           "Security Income (SSI): SSI for Disability, you're blind or have a disability; SSI for "
           "Age 65+, you're 65 or older; you have little or no income or assets such as money or "
           "property.",
           SSA_APPLY, SSA_PAGES_READ),
     claim("Medicare is our country's health insurance program for people age 65 or older. "
           "You'll sign up for Medicare Part A and Part B through Social Security, so you can "
           "make both retirement and Medicare choices and withhold any premiums from your benefit "
           "payments; under 65, "
           "eligible with permanent kidney failure or if you receive Disability benefits; SSI "
           "does not qualify you for Medicare on its own; if you're 65 or older, you can enroll "
           "online; you can delay Part B if you're already covered through an employer group "
           "health plan; sign up for Part B only if you already have Part A and previously "
           "declined or never signed up for Part B; review and sign up for Medicare Advantage and "
           "drug plans on Medicare.gov; Apply for Part D Extra Help; make an appointment: call "
           "800-772-1213, Monday through Friday, 8 a.m. to 7 p.m.; TTY 800-325-0778.",
           SSA_MEDICARE, SSA_PAGES_READ),
     claim("With a personal my Social Security account: request a replacement Social Security "
           "Number card; change your address or direct deposit; print proof of benefits or tax "
           "forms; get your Social Security Statement; review earnings; create it through "
           "Login.gov or ID.me, with an email address, a government-issued photo ID and a phone "
           "number or a device with a camera.", SSA_ACCOUNT, SSA_PAGES_READ),
     claim("The Medicare Beneficiaries Savings Program assists low-income elderly or disabled "
           "individuals who are eligible for Medicare; also referred to as the Buy-In program; "
           "QMB helps pay the Medicare Part A (hospital insurance) premium, Medicare Part B "
           "(supplemental insurance) premium, premium penalties for late enrollment, "
           "deductibles and coinsurance; SLMB or SLMB135 help pay the Part B premium and late "
           "penalties; QDWI pays the Part A premium of disabled working individuals who have "
           "lost Medicare due to earnings; a current resident of NH, no length of time; we do "
           "not count the home you are living in, vehicles or burial plots; to find out if you "
           "are eligible, visit NH EASY; DHHS Customer Service Center 1-844-ASK-DHHS "
           "(1-844-275-3447), Monday through Friday, 8:00 a.m. to 4:00 p.m.; administrative "
           "appeal hearing.", DHHS_MSP, DHHS_MSP_READ)]
    + help_claims("adrc", "nheasy", "legal_aid"),
    more=civics.faq(
        ("Can I get Medicare before I turn 65?",
         "<p>Under 65, you may get Medicare if you receive Social Security disability benefits "
         "or have permanent kidney failure. SSI alone does not qualify you.</p>"),
        ("I am losing coverage through a job. How do I add Part B?",
         "<p>If you already have Part A and are adding Part B because you are losing coverage "
         "through a job, your employer fills out form CMS-L564, which you send to your local "
         "Social Security office.</p>"),
        ("Does applying for Extra Help also apply for a Medicare Savings Program?",
         "<p>Yes, unless you say not to: applying for Extra Help through Social Security also "
         "starts an application for a Medicare Savings Program.</p>"),
        ("What is the difference between Medicare and Medicaid?",
         "<p>Medicare is federal health insurance for people 65 and older and some younger people "
         "with certain disabilities or conditions. Medicaid is a joint federal and state program "
         "that provides health coverage for certain people with low incomes, families and "
         "children, pregnant women, older people and people with disabilities. If you qualify, "
         "you can have both.</p>"),
        ("Is there a limit on what I pay out of pocket?",
         "<p>Not in Original Medicare: there is no yearly limit on what you pay for Part A and "
         "Part B services, unless you have a Medigap policy or join a Medicare Advantage Plan. "
         "Each Medicare Advantage Plan sets its own yearly limit; once you have paid it, the plan "
         "pays for your covered health services for the rest of the calendar year. Drug "
         "coverage (Part D) has a yearly limit too, which counts your deductible, what you pay "
         "yourself, and certain payments made for you, such as through Extra Help.</p>"),
        ("What if I don't qualify for premium-free Part A?",
         "<p>You might be able to buy it, for a monthly premium that depends on how long you or "
         "your spouse worked and paid Medicare taxes. You also have to sign up for Part B to buy "
         "Part A, and if you don't buy Part A when you are first eligible, usually when you turn "
         "65, you might pay a penalty.</p>"),
        ("How do I avoid a late penalty for drug coverage?",
         "<p>Get Medicare drug coverage when you first get Part A, Part B or both, and don't go "
         "63 days or more without creditable drug coverage, which is coverage similar in value "
         "to Part D. If you qualify for Extra Help, you won't have to pay the Part D late "
         "enrollment penalty.</p>"),
        ("Do I still pay the Part B premium with a Medicare Advantage Plan or Medigap?",
         "<p>Yes. You must have Part B and keep paying its premium to stay in a Medicare "
         "Advantage Plan, or to keep a Medigap policy.</p>"),
        ("Can I manage Medicare online too?",
         "<p>Once you have your Medicare card, you can make a Medicare account on Medicare.gov "
         "with your Medicare Number.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Medicare answers at 1-800-MEDICARE (1-800-633-4227), 24 hours a day (TTY "
         "1-877-486-2048), and Social Security at 1-800-772-1213.</p>"
         + helps("adrc", "nheasy", "legal_aid"),
    see=[("How to apply for food or health assistance (Medicaid)",
          "/guides/food-and-health-assistance.html"),
         ("How to get disability benefits and services", "/guides/disability-help.html")],
    figures=[fig("7 months", MEDICARE_START, "7 months"),
             fig("3 months", MEDICARE_START, "3 months before you turn 65"),
             fig("4 months", MEDICARE_AUTO, "at least 4 months before you turn 65"),
             fig("24 months", MEDICARE_AUTO, "disability benefits for 24 months"),
             fig("age 62", CFR_OLD_AGE, "at least 62 years old"),
             fig("10 years", SSA_APPLY, "for at least 10 years"),
             fig("24 hours", MEDICARE_CONTACT, "24 hours a day"),
             fig("63 days", MEDICARE_COSTS, "63 days or more without creditable drug coverage")])

GUIDES += [MEDICARE]


# ---------------------------------------------------------------------------
# DISABILITY BENEFITS AND SERVICES (the person, 25 October 2026: "disability
# assistance"). Five doors, each with its own rules: Social Security's two
# programs (federal), the state's cash assistance and Medicaid for workers
# (RSA 167:6, VI and IX), the area agencies for developmental disabilities
# (RSA 171-A), and vocational rehabilitation (RSA 200-C). The statutes are
# read in this build's table; the federal rules at eCFR on 25 October 2026.
# The agencies' own pages -- ssa.gov, the Department of Health and Human
# Services' and the Department of Education's -- refuse this machine and wait
# for the person's printouts. The Disability Rights Center and Granite State
# Independent Living are not state agencies and wait for the person's word.
# ---------------------------------------------------------------------------
DIS_READ = "2026-10-25"
DIS_PRINT_READ = "2026-10-25"        # the person's printouts, sent 25 October 2026
SSA_SSI = "https://www.ssa.gov/ssi/eligibility"
DHHS_APTD = ("https://www.dhhs.nh.gov/programs-services/disability-care/"
             "aid-permanently-totally-disabled")
DHHS_DEV = "https://www.dhhs.nh.gov/programs-services/disability-care/developmental-services"
NHVR = ("https://www.education.nh.gov/who-we-are/deputy-commissioner/"
        "bureau-vocational-rehabilitation/programs-and-services/vocational-rehabilitation-services")
CFR_DISABLED = "https://www.ecfr.gov/current/title-20/section-404.1505"
CFR_SSDI = "https://www.ecfr.gov/current/title-20/section-404.315"
CFR_SSI = "https://www.ecfr.gov/current/title-20/section-416.202"
CFR_RECONSIDER = "https://www.ecfr.gov/current/title-20/section-404.909"

DISABILITY = guide(
    "disability-help", "How to Get Disability Benefits and Services",
    "The help available in New Hampshire to a person with a disability, and how to apply: "
    "Social Security's disability benefits, the state's cash and medical assistance, services "
    "for developmental disabilities, and help getting or keeping a job.",
    "Social Security pays two kinds of disability benefits: SSDI, if you have worked and paid "
    "Social Security taxes, and SSI, if your income and savings are limited. Apply as soon as "
    "a condition keeps you from working. New Hampshire adds cash and medical assistance for "
    "adults with a long-term disability, Medicaid for people with disabilities who work, "
    "services through a regional area agency for a developmental disability, and vocational "
    "rehabilitation to help you get or keep a job. Free help with any of it is a phone call "
    "away.",
    [ask("What do you need?",
         [("Income, because you cannot work",
           "Apply to Social Security for SSDI or SSI, and to the state for cash assistance."),
          ("Health coverage while you work", "Ask the state about Medicaid for workers (MEAD)."),
          ("Services for a developmental disability", "Apply to your region&rsquo;s area agency."),
          ("Help getting or keeping a job", "Apply for vocational rehabilitation.")]),
     box("If you are turned down, read the notice: it says how to appeal, and by when.")],
    [step("Apply to Social Security for SSDI or SSI",
          "<p>Social Security counts you as disabled if a medical condition keeps you from doing "
          "any substantial work and is expected to last at least 12 months or to result in "
          "death. It runs two programs:</p>"
          "<ul><li><b>SSDI</b> (Social Security Disability Insurance) is for people who have "
          "worked long enough, and paid Social Security taxes, to be insured.</li>"
          "<li><b>SSI</b> (Supplemental Security Income) is for people who are disabled, blind "
          "or 65 or older, and whose income and savings are under its limits.</li></ul>"
          "<p>Apply as soon as you can, online on Social Security&rsquo;s Apply page, or call "
          "1-800-772-1213 for an appointment.</p>",
          actions=[("Apply for benefits (Social Security)", SSA_APPLY),
                   ("Who can get SSI (Social Security)", SSA_SSI)]),
     step("Apply to the state for cash and medical assistance",
          "<p>New Hampshire&rsquo;s <b>Aid to the Permanently and Totally Disabled</b> (APTD) "
          "gives cash assistance to residents between the ages of 18 and 64 who are disabled "
          "as Social Security defines it, except that the condition must be expected to last "
          "at least 48 months. Anyone who receives it also qualifies for medical assistance "
          "(Medicaid). You must also apply for any federal benefits you may be entitled to, "
          "such as SSI, and pursue their appeals.</p>"
          "<p><b>Medicaid for Employed Adults with Disabilities</b> (MEAD) gives medical "
          "assistance to working people with a disability between 18 and 64; a similar program, "
          "MOAD, is for those 65 and older. You must be working when you enroll.</p>"
          "<p>Apply for either through NH Easy, or at a Department of Health and Human Services "
          "District Office, where a worker helps you through the application interview.</p>",
          actions=[("NH Easy", NHEASY), ("APTD (Department of Health and Human Services)", DHHS_APTD)],
          law=["RSA 167:6"]),
     step("Services for a developmental disability: your area agency",
          "<p>For a developmental disability or an acquired brain disorder, the state&rsquo;s "
          "services come through ten regional <b>area agencies</b>. Apply to the one for where "
          "you live. It arranges an evaluation, and makes its first recommendations within 21 "
          "days of your application. Its services include service coordination, help living in "
          "the community, and employment and day services.</p>",
          actions=[("Developmental services and the area agencies (Department of Health and "
                    "Human Services)", DHHS_DEV)],
          law=["RSA 171-A:6", "RSA 171-A:18", "RSA 171-A:18-a"]),
     step("Help getting or keeping a job: vocational rehabilitation",
          "<p>The Department of Education&rsquo;s <b>Bureau of Vocational Rehabilitation</b> "
          "helps people with disabilities prepare for, find and keep a job, under the federal "
          "vocational rehabilitation program.</p>"
          "<p>Any New Hampshire resident with a disability may qualify, whether looking for a "
          "first job or wanting to keep working after a disability. Its help includes career "
          "counseling, job training, help finding a job, and assistive technology. To apply, "
          "fill in the online referral form on its page.</p>",
          actions=[("Vocational Rehabilitation (Department of Education)", NHVR)],
          law=["RSA 200-C:1", "RSA 200-C:24", "RSA 200-C:25"]),
     step("If you are turned down",
          "<p><b>Social Security:</b> you can ask it to reconsider, in writing, within 60 days "
          "after you receive its decision. The notice says how.</p>"
          "<p><b>The state:</b> you can ask for an administrative appeal hearing, in writing, on "
          "the Department&rsquo;s form or in a letter. Generally you have 30 days from the date "
          "on your Notice of Decision. You do "
          "not need a lawyer, and free legal aid can help with benefits appeals (below).</p>",
          actions=[("Administrative appeals (Department of Health and Human Services)",
                    DHHS_APPEALS)])],
    [("Apply for Social Security Benefits (Social Security Administration)", SSA_APPLY),
     ("Who Can Get SSI (Social Security Administration)", SSA_SSI),
     ("Aid to the Permanently and Totally Disabled (Department of Health and Human Services)",
      DHHS_APTD),
     ("Developmental Services (Department of Health and Human Services)", DHHS_DEV),
     ("Vocational Rehabilitation Services (Department of Education)", NHVR),
     ("Administrative Appeals (Department of Health and Human Services)", DHHS_APPEALS),
     ("Basic definition of disability, 20 CFR 404.1505 (federal)", CFR_DISABLED),
     ("Who is entitled to disability benefits?, 20 CFR 404.315 (federal)", CFR_SSDI),
     ("Who may get SSI benefits, 20 CFR 416.202 (federal)", CFR_SSI),
     ("How to request reconsideration, 20 CFR 404.909 (federal)", CFR_RECONSIDER),
     ("Public Assistance to Blind, Aged, or Disabled Persons, RSA 167", "/laws/167"),
     ("Services for the Developmentally Disabled, RSA 171-A", "/laws/171-a"),
     ("Vocational Rehabilitation, RSA 200-C", "/laws/200-c")],
    ["167", "171-A", "200-C"],
    [# The federal rules, read at eCFR on 25 October 2026.
     claim("Disability is the inability to do any substantial gainful activity by reason of a "
           "medically determinable impairment which can be expected to result in death or has "
           "lasted or can be expected to last for a continuous period of not less than 12 "
           "months.", CFR_DISABLED, DIS_READ),
     claim("Entitled to disability benefits if insured for disability, you apply, you have a "
           "disability, and you have been disabled for 5 full consecutive months (the 5-month "
           "waiting period) or no waiting period is required.", CFR_SSDI, DIS_READ),
     claim("Eligible for SSI if aged 65 or older, blind or disabled, a resident and citizen or "
           "qualified noncitizen, with no more income or resources than permitted.",
           CFR_SSI, DIS_READ),
     claim("Reconsideration on a written request within 60 days after the date you receive "
           "notice of the initial determination.", CFR_RECONSIDER, DIS_READ),
     claim("Automatic Part A and Part B after getting disability benefits for 24 months.",
           MEDICARE_AUTO, DIS_READ),
     claim("Social Security Administration, toll-free number 1-800-772-1213.", USA_SSA, DIS_READ),
     # The statutes, as this build's table prints them.
     claim("APTD: between the ages of 18 and 64 years of age inclusive, a resident, disabled as "
           "defined in the Social Security Act, except that the minimum required duration of "
           "the impairment shall be 48 months; eligibility conditioned on applying for federal "
           "cash benefits and pursuing all appeals; categorically needy for medical assistance "
           "if receiving it (VII); MEAD: a person with a disability between 18 and 64 years of "
           "age, employed at the time of enrollment (IX); MOAD, 65 and older (IX-a).",
           "RSA 167:6", DIS_READ),
     claim("A person seeking service applies to the area agency in his or her geographic region; "
           "a comprehensive screening evaluation; preliminary recommendations within 21 days "
           "after application for service.", "RSA 171-A:6", DIS_READ),
     claim("Area agency programs include diagnosis and evaluation, service coordination, "
           "community living arrangements, employment and day services.", "RSA 171-A:18",
           DIS_READ),
     claim("Family-centered early supports and services for children birth up to age 3 with an "
           "established condition, developmental delays, or at risk of substantial delays.",
           "RSA 171-A:18-a", DIS_READ),
     claim("The bureau of vocational rehabilitation of the department of education, under the "
           "federal vocational rehabilitation program.", "RSA 200-C:1", DIS_READ),
     claim("An independent living program within the bureau, to assist eligible persons with "
           "disabilities in increasing their independence.", "RSA 200-C:24", DIS_READ),
     claim("The independent living program's services include services to the elderly blind "
           "for the purpose of increasing independence.", "RSA 200-C:25", "2026-10-26"),
     # Read before, for the food and health guide.
     claim("Appeal in writing by form or letter, to the District Office, by mail to the AAU, or by "
           "email, or by telling a DHHS representative; generally 30 days from the Notice of "
           "Decision, 90 for SNAP; within 15 days benefits may continue, repaid if upheld; no "
           "attorney needed and none appointed.", DHHS_APPEALS, READ),
     # The agencies' own pages, from the person's printouts.
     claim("Disability benefits: you have a medical condition that will last at least one "
           "year or result in death; your condition makes it hard or impossible to work; you "
           "worked and paid Social Security taxes long enough. SSI for Disability: you're "
           "blind or have a disability; little or no income or assets.", SSA_APPLY,
           DIS_PRINT_READ),
     claim("Adults and children might be eligible for SSI if they have little or no income, "
           "little or no resources, and a disability, blindness, or are age 65 or older; "
           "common resources are vehicles and money in bank accounts, with limits for "
           "individuals and couples; if you're age 64 or younger, a disability that affects "
           "your ability to work for a year or more, or will result in death.", SSA_SSI,
           DIS_PRINT_READ),
     claim("Aid to the Permanently and Totally Disabled (APTD) is cash assistance for individuals "
           "who are between the ages of 18 and 64 and who are physically or mentally disabled; "
           "if you are eligible for cash assistance, you are also eligible for medical "
           "assistance; you must apply for all potential kinds of income, such as Social "
           "Security Benefits (including SSI); a medical condition that stops you from working "
           "and that is expected to last for at least 48 months or result in death; to apply, "
           "visit a DHHS District Office and speak with a DHHS worker; you may request an "
           "Administrative Appeals hearing.", DHHS_APTD, DIS_PRINT_READ),
     claim("The Bureau of Developmental Services supports individuals of all ages with "
           "developmental disabilities or acquired brain disorders; ten (10) designated "
           "non-profit area agencies that represent specific geographic regions of NH; supports "
           "include service coordination, day and vocational services, personal care, community "
           "support, Early Supports and Services, assistive technology and respite; BDS, "
           "(603) 271-5034.", DHHS_DEV, DIS_PRINT_READ),
     claim("If you're a New Hampshire resident with a disability, you may qualify for vocational "
           "rehabilitation (VR) services from VR New Hampshire: career counseling, educational "
           "guidance, job training, job search assistance, help securing assistive technology; "
           "for people seeking employment for the first time and those who want to continue "
           "working after acquiring a disability; to apply, complete the online referral form; "
           "(603) 271-3494.", NHVR, DIS_PRINT_READ)]
    + help_claims("adrc", "nheasy", "legal_aid"),
    more=civics.faq(
        ("When do SSDI benefits begin, and when does Medicare start?",
         "<p>Benefits begin after a waiting period of 5 months of disability. After 24 months of "
         "disability benefits, you get Medicare automatically.</p>"),
        ("Does SSI count what I own?",
         "<p>SSI also counts what you own, such as money in the bank and vehicles, up to a "
         "limit. Social Security&rsquo;s Who Can Get SSI page gives the income and resource "
         "limits.</p>"),
        ("Is there help for a young child with a developmental delay?",
         "<p>For a child from birth up to age 3 with a developmental delay, or at risk of one, "
         "the Department of Health and Human Services runs Family Centered Early Supports and "
         "Services.</p>"),
        ("Is there help living more independently?",
         "<p>The Bureau of Vocational Rehabilitation&rsquo;s independent living program helps "
         "people with disabilities, and older people who are blind, live more "
         "independently.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Social Security answers at 1-800-772-1213. For help with the state&rsquo;s "
         "programs, and with finding your way among all of them:</p>"
         + helps("adrc", "nheasy", "legal_aid"),
    see=[("How to sign up for Medicare and Social Security, and get help with the costs",
          "/guides/medicare-and-social-security.html"),
         ("How to apply for food or health assistance", "/guides/food-and-health-assistance.html")],
    figures=[fig("12 months", CFR_DISABLED, "not less than 12 months"),
             fig("5 months", CFR_SSDI, "5 full consecutive months"),
             fig("24 months", MEDICARE_AUTO, "disability benefits for 24 months"),
             fig("48 months", "RSA 167:6", "the minimum required duration of the impairment "
                 "shall be 48 months"),
             fig("21 days", "RSA 171-A:6", "within 21 days after application for service"),
             fig("age 3", "RSA 171-A:18-a", "birth up to age 3"),
             fig("60 days", CFR_RECONSIDER, "within 60 days"),
             fig("30 days", DHHS_APPEALS, "generally 30 days from the Notice of Decision")])

GUIDES += [DISABILITY]


# ---------------------------------------------------------------------------
# WHO TO CONTACT, AND FOR WHAT (the person, 25 October 2026: "explaining what
# you might contact different elected officials for, like contacting state
# reps about legislation or state agencies, contacting city councilors about
# things like sidewalk issues, school board, federal delegation for
# assistance with federal programs"). A routing guide: it names no official,
# because the people change and My Town names them, and sends a reader to
# the office whose job the problem is. Read on 25 October 2026: the statutes
# in this build's table; the federal Privacy Act at govinfo; the casework
# pages of a New Hampshire senator and representative, which say what such
# an office does; USA.gov and the two chambers' finders. The Governor's and
# the Executive Council's pages refuse this machine; their claims rest on the
# person's printouts of 25 October 2026. The guide names no councilor: My
# Town does.
# ---------------------------------------------------------------------------
WC_READ = "2026-10-25"
WC_PRINT_READ = "2026-10-25"         # the person's printouts, sent 25 October 2026
SENATE_CONTACT = "https://www.senate.gov/senators/senators-contact.htm"
HOUSE_FIND = "https://www.house.gov/representatives/find-your-representative"
CASEWORK_SENATE = "https://www.hassan.senate.gov/services/help-with-a-federal-agency"
CASEWORK_HOUSE = "https://goodlander.house.gov/services/help-federal-agency/"
PRIVACY_ACT = ("https://www.govinfo.gov/content/pkg/USCODE-2024-title5/html/"
               "USCODE-2024-title5-partI-chap5-subchapII-sec552a.htm")
USA_OFFICIALS = "https://www.usa.gov/elected-officials"
COUNCIL_ABOUT = "https://www.council.nh.gov/about-us"
COUNCIL_CONTACT = "https://www.council.nh.gov/contact-us"
GOVERNOR_CONTACT = "https://www.governor.nh.gov/contact-governor-ayotte"

WHO_TO_CONTACT = guide(
    "who-to-contact", "Who to Contact About an Issue: Town, School, State or Federal",
    "Which office to contact about a problem or a law, from potholes and sidewalks to a state "
    "program or a federal agency, and how to find the people who hold it.",
    "Start with whoever runs the thing. Town roads, sidewalks, trash and local rules are your town or "
    "city&rsquo;s: its departments, then the selectboard or city council. Schools are the school "
    "board&rsquo;s. A state program is the state agency&rsquo;s that runs it, and a state law or "
    "bill is your state representatives&rsquo; and senator&rsquo;s. A problem with a federal "
    "agency, such as Social Security, veterans&rsquo; benefits or a passport, is what your U.S. "
    "senators&rsquo; and representative&rsquo;s offices help with.",
    [ask("What is it about?",
         [("A road, a sidewalk, trash, a local rule", "Your town or city: the department, then "
           "the selectboard or city council."),
          ("A school", "The school, then the superintendent and the school board."),
          ("A state program or a state law", "The state agency for a program; your state "
           "representatives and senator for a law or a bill."),
          ("A federal agency or a federal law", "Your U.S. senators and U.S. representative.")]),
     box("Not sure? Ask any of them: an office that cannot help usually knows who can.")],
    [step("Find who represents you",
          "<p>Choose your town to see everyone who represents it, from your state representatives "
          "to your members of Congress, each with a page here.</p>"
          '<div class="yt" data-yt="reps" hidden></div>',
          actions=[("Find your town", "/officials.html#my-town")]),
     step("Your town or city: roads, sidewalks, trash and local rules",
          "<p>Most everyday problems are local. Your town or city maintains its own roads and "
          "repairs its sidewalks, and runs or arranges trash and recycling.</p>"
          "<p>Start with the department that handles it, such as public works for a pothole or a "
          "broken sidewalk. If that does not settle it, contact the selectboard or your city "
          "councilor. A change to the town&rsquo;s budget or rules may go to town meeting.</p>",
          actions=[("How towns and cities are run", "/learn/city-and-town-government.html")],
          law=["RSA 41:8", "RSA 41:11", "RSA 47:1", "RSA 231:3", "RSA 231:113",
               "RSA 149-M:17"]),
     step("Schools",
          "<p>A question about your child starts with the teacher and the principal. A district "
          "policy, a budget or a decision of the district is for the superintendent and the "
          "<b>school board</b>, the district&rsquo;s governing body, which provides its "
          "schools.</p>",
          actions=[("Town meeting and local government", "/learn/local-government.html")],
          law=["RSA 189:1"]),
     step("A state program or agency",
          "<p>Start with the agency that runs the program: the Division of Motor Vehicles for a "
          "license, the Department of Health and Human Services for SNAP or Medicaid, and so on. "
          "Each guide here links the agency&rsquo;s page.</p>"
          "<p>If you cannot get an answer, the <b>Governor&rsquo;s office</b> takes requests for "
          "help from residents: call its Constituent Services at (603) 271-7676, or choose "
          "Request Assistance on its contact page. Your <b>Executive Councilor</b>, one of five elected by "
          "district every two years, serves, in the Council&rsquo;s own words, as an advocate "
          "for the people and their eyes and ears in Concord. The Council&rsquo;s office is at "
          "(603) 271-3632.</p>",
          actions=[("Contact the Governor's office", GOVERNOR_CONTACT),
                   ("The Executive Council", COUNCIL_CONTACT)]),
     step("A state law or a bill",
          "<p>Your <b>state representatives and state senator</b> vote on the bills that make and "
          "change New Hampshire&rsquo;s laws. Contact them about a bill, or to ask for a new law. "
          "You can also tell the committee that hears a bill where you stand.</p>",
          actions=[("How to contact your legislators", "/guides/contact-your-legislators.html"),
                   ("How to submit testimony on a bill", "/guides/submit-testimony.html")]),
     step("A federal agency or a federal law",
          "<p>Your two <b>U.S. senators</b> and your <b>U.S. representative</b> help residents "
          "with federal agencies: Social Security, veterans&rsquo; benefits, passports, the IRS, "
          "citizenship and others. Contact them too about a federal "
          "law or bill.</p>",
          actions=[("Find your U.S. senators", SENATE_CONTACT),
                   ("Find your U.S. representative", HOUSE_FIND)]),
     step("The county",
          "<p>Your county runs the county jail and the county nursing home, among other things. "
          "Its commissioners run it day to day, and its budget is set by the state "
          "representatives elected from the county.</p>",
          actions=[("How county government works", "/learn/county-government.html")])],
    [("Find and contact elected officials (USA.gov)", USA_OFFICIALS),
     ("Contact your senators (U.S. Senate)", SENATE_CONTACT),
     ("Find your representative (U.S. House of Representatives)", HOUSE_FIND),
     ("Help with a federal agency (a U.S. senator's office)", CASEWORK_SENATE),
     ("Help with a federal agency (a U.S. representative's office)", CASEWORK_HOUSE),
     ("The Privacy Act, 5 U.S.C. 552a (federal)", PRIVACY_ACT),
     ("About the Executive Council (Executive Council)", COUNCIL_ABOUT),
     ("Contact the Executive Council (Executive Council)", COUNCIL_CONTACT),
     ("Contact the Governor (Office of the Governor)", GOVERNOR_CONTACT),
     ("Town officers, RSA 41", "/laws/41"),
     ("City councils, RSA 47", "/laws/47"),
     ("Highways and sidewalks, RSA 231", "/laws/231"),
     ("Solid waste management, RSA 149-M", "/laws/149-m"),
     ("School boards, RSA 189", "/laws/189")],
    ["41", "47", "189", "231", "149-M"],
    [# The statutes, as this build's table prints them.
     claim("The selectmen shall manage the prudential affairs of the town.", "RSA 41:8", WC_READ),
     claim("The selectmen may regulate the use of all public highways, sidewalks, and commons in "
           "their towns.", "RSA 41:11", WC_READ),
     claim("All the powers vested by law in towns shall be exercised by the city councils.",
           "RSA 47:1", WC_READ),
     claim("All class V highways shall be constructed, reconstructed, and maintained by the city or "
           "town in which they are located.", "RSA 231:3", WC_READ),
     claim("Sidewalks shall be maintained, repaired and reconstructed by the city or town in which "
           "they are located, under the selectmen or the mayor and aldermen.", "RSA 231:113",
           WC_READ),
     claim("The school board of every district shall provide standard schools.", "RSA 189:1",
           WC_READ),
     claim("Each town shall either provide a facility or assure access to another approved solid "
           "waste facility for its residents.", "RSA 149-M:17", "2026-10-26"),
     # Federal, read on 25 October 2026.
     claim("No agency shall disclose any record to any person except pursuant to a written request "
           "by, or with the prior written consent of, the individual to whom the record pertains, "
           "with exceptions.", PRIVACY_ACT, WC_READ),
     claim("Help with any issue involving a federal agency: veterans benefits, citizenship, housing, "
           "small business, IRS/taxes, passports, Social Security; cannot guarantee a favorable "
           "outcome but will seek a fair and timely response; judicial or state matters are "
           "directed elsewhere; the Privacy Act requires written authorization, a signed privacy "
           "release form, before the office looks into a case.", CASEWORK_SENATE, WC_READ),
     claim("If you can't get an answer from a federal agency, or feel treated unfairly, the office "
           "may be able to help; it cannot guarantee a favorable outcome; written authorization "
           "under the Privacy Act; include claim numbers.", CASEWORK_HOUSE, WC_READ),
     claim("Contact information for U.S. senators, state by state.", SENATE_CONTACT, WC_READ),
     claim("Find your U.S. representative.", HOUSE_FIND, WC_READ),
     claim("Get the names and contact information for the people who represent you on the federal, "
           "state, and local levels.", USA_OFFICIALS, WC_READ),
     # This site's own pages.
     ours("My Town shows everyone who represents a town, from the House to the US House, each with "
          "a page.", "/officials.html", WC_READ),
     ours("How a town's selectboard and a city's council and mayor or manager run them.",
          "/learn/city-and-town-government.html", WC_READ),
     ours("Local government is the city or town, the school district and the county; the school "
          "board is a school district's governing body.",
          "/learn/local-government.html", WC_READ),
     ours("A county keeps a jail (RSA 30-B:1) and runs nursing homes; three commissioners; the "
          "county convention of the county's state representatives sets its budget.",
          "/learn/county-government.html", WC_READ),
     # The Governor's and the Council's own pages, from the person's printouts.
     claim("Contact Governor Ayotte: Office of the Governor, State House, 107 North Main Street, "
           "Concord; (603) 271-2121; open Monday - Friday, 8:30 AM - 4:30 PM; Constituent "
           "Services: (603) 271-7676; select the option that best fits the reason for "
           "contacting us: Share My Opinion, Request Assistance, and others.", GOVERNOR_CONTACT,
           WC_PRINT_READ),
     claim("Each of the five Executive Councilors represents one fifth of the population; "
           "Councilors are elected every two years, concurrently with the Governor; the candidate "
           "must live in the district; Executive Councilors are the constituent's eyes and ears "
           "in Concord; Councilors are elected every two years to serve as advocates for the "
           "people; 107 North Main Street, State House, Room 207, (603) 271-3632.",
           COUNCIL_ABOUT, WC_PRINT_READ),
     claim("New Hampshire Executive Council: gcweb@nh.gov, (603) 271-3632; Contact Councilor "
           "links for each of the five councilors.", COUNCIL_CONTACT, WC_PRINT_READ)],
    more=civics.faq(
        ("Who runs a town, and who runs a city?",
         "<p>In a town the <b>selectboard</b> manages the town&rsquo;s business and may regulate "
         "the use of its roads and sidewalks; in a city the <b>city council</b> holds those "
         "powers, with the mayor or city manager running the departments.</p>"),
        ("Can my members of Congress fix a problem with a federal agency?",
         "<p>They cannot promise an outcome, but they can ask the agency for a fair and timely "
         "answer.</p>"),
        ("Why do they ask me to sign a privacy release?",
         "<p>Before they can look into your case, you sign a <b>privacy release</b>, because "
         "federal law lets an agency share your records only with your written consent. Each "
         "office&rsquo;s website has its form.</p>")),
    see=[("How to find your representatives", "/guides/your-representatives.html"),
         ("How to contact your legislators", "/guides/contact-your-legislators.html")])

GUIDES += [WHO_TO_CONTACT]


# ---------------------------------------------------------------------------
# A POTHOLE, A BROKEN SIGNAL OR A SIDEWALK (the person, 25 October 2026: "how
# to report issues like potholes, broken stoplights, or sidewalk issues to
# your town"). Who keeps which road is the law's -- RSA 229:5's classes, the
# state's duty in RSA 230:1-4 and the town's in RSA 231:2-3 and 231:113 --
# and so is what a written notice makes a town or the state do, and answer
# for (RSA 231:90-92-a, RSA 230:78-81), with the deadlines to claim for
# damage (RSA 507-B:7 for a town, RSA 541-B:14 for the state). Read on 25
# October 2026 in this build's statute table. No statute says who owns a
# traffic signal or a streetlight, so the guide sends those to whoever keeps
# the road and says no more. The Department of Transportation's pages refuse
# this machine; their claims wait for the person's printouts.
# ---------------------------------------------------------------------------
ROAD_READ = "2026-10-25"
ROAD_STATE_READ = "2026-10-26"       # the person's printouts of dot.nh.gov
NHDOT_PUBLIC = "https://www.dot.nh.gov/doing-business-nhdot/general-public"
NHDOT_CONTACT = "https://www.dot.nh.gov/about-nh-dot/contact-us"

ROAD_PROBLEM = guide(
    "report-a-road-problem", "How to Report a Pothole, a Broken Signal or a Sidewalk Problem",
    "Who fixes which road in New Hampshire, how to report a pothole, a broken sidewalk or a "
    "signal to your town or the state, and what to do if a road problem damaged your car.",
    "Town roads and sidewalks are your town or city&rsquo;s to fix: report a pothole, a broken "
    "sidewalk, a streetlight or a signal to its public works or highway department. The main "
    "state highways are the state Department of Transportation&rsquo;s: report those to its "
    "maintenance district for your town. For a dangerous spot, a signed written notice to the "
    "town makes it act, and answer for damage if it does not. If a road problem damaged your "
    "car, the deadline to give notice is short.",
    [ask("Whose road is it?",
         [("A town or city street, or its sidewalk",
           "Your town or city&rsquo;s public works or highway department."),
          ("A state highway",
           "The Department of Transportation&rsquo;s maintenance district for your town.")]),
     box("Dangerous? Put it in writing, signed, saying where it is and what is wrong."),
     box("Damaged your car? Give written notice of the date, time and place, within the "
         "deadline.")],
    [step("Work out whose road it is",
          "<p>Most roads are your town&rsquo;s or city&rsquo;s. It maintains every ordinary town "
          "road, and keeps up the sidewalks it has built along its roads, at no further charge "
          "to the owners next to them.</p>"
          "<p>The state&rsquo;s <b>Department of Transportation</b> maintains the main state "
          "highways, and the parts of the secondary state highways it has improved; a town "
          "maintains the rest of those.</p>"
          "<p>If you are not sure whose road it is, start with your town.</p>",
          law=["RSA 229:5", "RSA 230:1", "RSA 230:3", "RSA 230:4", "RSA 231:2", "RSA 231:3",
               "RSA 231:93", "RSA 231:113"]),
     step("Report it to your town or city",
          "<p>Call or email your town or city&rsquo;s <b>public works</b> or <b>highway "
          "department</b>, or the selectboard&rsquo;s office in a small town. Say exactly where "
          "the problem is (the street, the nearest house "
          "number or cross street) and what it is: a pothole, a broken or heaved sidewalk, a "
          "streetlight that is out, a signal that is dark or stuck, a blocked drain.</p>"
          "<p>A traffic signal that is out at a busy intersection is a danger to everyone "
          "using it: report it at once, and if someone may be hurt, call 911.</p>",
          law=["RSA 231:113"]),
     step("Report it to the state, for a state highway",
          "<p>If a signal is out, a stop sign is down or a state road is iced over, call the "
          "Department of Transportation&rsquo;s <b>Traffic Management Center</b> at (603) "
          "271-6862. For a pothole, drainage or another problem on a state road, contact the "
          "Department&rsquo;s highway maintenance district for your town; its page for the "
          "public links the districts, and a form for a damage claim. Other questions go to "
          "(603) 271-3734 or info@dot.nh.gov.</p>"
          "<p>Anyone may notify the Department of a dangerous spot on a state highway. Once "
          "it is notified, unless it decides in good faith there is no danger, it must put up "
          "warnings at once and make a plan to repair the spot within 96 hours.</p>",
          actions=[("The Department of Transportation, for the public", NHDOT_PUBLIC),
                   ("Contact the Department of Transportation", NHDOT_CONTACT)],
          law=["RSA 230:78", "RSA 230:79"]),
     step("For a dangerous spot, put it in writing",
          "<p>The law gives a written notice weight a phone call does not have. If a town "
          "road, a bridge or a sidewalk is <b>insufficient</b> &ndash; not passable safely, or "
          "with a hazard a careful traveler could not see or avoid &ndash; anyone may give the "
          "town written notice. Sign it, say in general terms where it is and what is wrong, "
          "and give it to a selectman or the highway agent (in a city, the mayor or a street "
          "commissioner), with a copy to the town or city clerk.</p>"
          "<p>The town must then, unless it decides in good faith there is no such danger, "
          "put up warnings at once and, within 72 hours, make a plan to repair it, and carry "
          "the plan out. If it does not, it is liable for the injury or damage the danger "
          "causes.</p>",
          law=["RSA 231:90", "RSA 231:91", "RSA 231:92-a"]),
     step("If a road problem damaged your car",
          "<p><b>On a town road</b>, the town answers for damage only if it had written notice "
          "of the danger and did not act, or its officials knew of it and were grossly "
          "negligent or acted in bad faith, or its employee created it on purpose or "
          "recklessly. Before you can sue, the town or city clerk must be told by "
          "<b>registered mail within 60 days</b> of the damage the date, time and place it "
          "happened, and a suit must be brought within 3 years.</p>"
          "<p><b>On a state highway</b>, the Department of Transportation answers on the same "
          "terms. A claim against the state goes to the state Board of Claims or the Superior "
          "Court, depending on its size. The Department must be told in writing, within 180 "
          "days of the damage, the date, time and place it happened, and the claim must be "
          "brought within 3 years.</p>"
          "<p>Take pictures of the spot and the damage, and keep your repair bills.</p>",
          law=["RSA 231:92", "RSA 507-B:7", "RSA 230:80", "RSA 541-B:9", "RSA 541-B:14"])],
    [("General Public (New Hampshire Department of Transportation)", NHDOT_PUBLIC),
     ("Contact Us (New Hampshire Department of Transportation)", NHDOT_CONTACT),
     ("Classification of Highways, RSA 229", "/laws/229"),
     ("Highways: Layout and Maintenance by the State, RSA 230", "/laws/230"),
     ("Municipal Highways, RSA 231", "/laws/231"),
     ("Actions Against Governmental Units, RSA 507-B", "/laws/507-b"),
     ("Board of Claims, RSA 541-B", "/laws/541-b")],
    ["229", "230", "231", "507-B", "541-B"],
    [# The statutes, as this build's table prints them.
     claim("Class I highways: the primary state highway system; class II: the secondary state "
           "highway system; class IV: highways within the compact sections of the cities and "
           "towns listed (among them Concord, Manchester, Nashua); class V: all other traveled "
           "highways the town has the duty to maintain regularly, town roads; class VI: all "
           "other existing public ways, including highways not maintained and repaired by the "
           "town for 5 successive years or more.", "RSA 229:5", ROAD_READ),
     claim("The department of transportation shall assume full control and pay the costs of "
           "construction, reconstruction and maintenance of all class I highways.",
           "RSA 230:1", ROAD_READ),
     claim("The department shall assume full control and pay the costs of reconstruction and "
           "maintenance of all class II highways which have been improved to the satisfaction "
           "of the commissioner.", "RSA 230:3", ROAD_READ),
     claim("All other class II highways shall be maintained by the city or town in which they "
           "are located.", "RSA 230:4", ROAD_READ),
     claim("All class IV highways shall be wholly constructed, reconstructed and maintained by "
           "the city or town in which they are located.", "RSA 231:2", ROAD_READ),
     claim("All class V highways shall be constructed, reconstructed, and maintained by the "
           "city or town in which they are located.", "RSA 231:3", ROAD_READ),
     claim("Municipalities shall not be deemed to have any duty of care whatsoever with respect "
           "to the construction, maintenance or repair of class I, III, III-a or VI highways, "
           "or state maintained portions of class II highways.", "RSA 231:93", ROAD_READ),
     claim("The highway agent, under the direction of the mayor and aldermen or the selectmen, "
           "has charge of the repair of sidewalks, maintained, repaired and reconstructed by "
           "the city or town without further assessment to the abutting owner.",
           "RSA 231:113", ROAD_READ),
     claim("Any person may give written notice of an insufficiency of a class IV or V highway, "
           "bridge or sidewalk to one of the selectmen or highway agents, or the mayor or "
           "street commissioners, with a copy to the clerk; signed, setting forth in general "
           "terms the location and the nature of the insufficiency; insufficient only if not "
           "passable in any safe manner, or a safety hazard not reasonably discoverable or "
           "avoidable; not insufficient merely by not being kept to the standard of another "
           "highway.", "RSA 231:90", ROAD_READ),
     claim("On notice, unless no insufficiency exists in good faith, the municipality shall "
           "immediately place danger signals and within 72 hours thereafter develop a plan for "
           "repairing it and implement it; if it fails to act, it is liable for personal "
           "injury or property damage proximately caused by the insufficiency.",
           "RSA 231:91", ROAD_READ),
     claim("A municipality is not liable unless the damage was caused by an insufficiency and it "
           "received written notice and failed to act, or officials had actual knowledge and "
           "were grossly negligent or exercised bad faith, or the condition was created by an "
           "intentional act of an employee with gross negligence or reckless disregard.",
           "RSA 231:92", ROAD_READ),
     claim("Not liable for hazards caused solely by snow, ice, or other inclement weather when "
           "a delay results from a winter maintenance policy adopted in good faith, absent "
           "gross negligence or reckless disregard.", "RSA 231:92-a", ROAD_READ),
     claim("Any person may give notice of an insufficiency of a class I or class II highway or "
           "highway bridge to the department of transportation, setting forth its location and "
           "nature.", "RSA 230:78", ROAD_READ),
     claim("On notice, unless no insufficiency exists in good faith, the department shall "
           "immediately place danger signals and within 96 hours thereafter develop a plan for "
           "repairing it; if it fails to act it is liable for damage proximately caused.",
           "RSA 230:79", ROAD_READ),
     claim("The department of transportation is not liable unless the damage was caused by an "
           "insufficiency and it received notice and failed to act, or the commissioner had "
           "actual knowledge and was grossly negligent or in bad faith, or an employee created "
           "it intentionally with gross negligence or reckless disregard.", "RSA 230:80",
           ROAD_READ),
     claim("An action against a governmental unit within 3 years after the time of injury or "
           "damage; as a condition precedent, the clerk of the governmental unit shall be "
           "notified by registered mail within 60 days after the time of the injury or damage "
           "as to the date, time and location.", "RSA 507-B:7", ROAD_READ),
     claim("The board of claims hears claims against an agency up to an amount, concurrently "
           "with the superior court above it, and the superior court alone above a higher "
           "amount.", "RSA 541-B:9", ROAD_READ),
     claim("A claim brought within 3 years of the damage; as a condition precedent, the agency "
           "shall be provided written notice within 180 days after the time of the injury or "
           "damage as to the date, time, and location.", "RSA 541-B:14", ROAD_READ),
     # The Department of Transportation's own pages, from the person's printouts.
     claim("If there is an immediate concern, a signal is out, a stop sign is down, the road "
           "is iced over, please call the Traffic Management Center at (603) 271-6862; other "
           "road issues, on State Roads, i.e., potholes, drainage issues, contact the "
           "Maintenance District that maintains the roads in your specific town; To Submit a "
           "Damage Claim please visit the link and fill out the form.", NHDOT_PUBLIC,
           ROAD_STATE_READ),
     claim("All Road Emergencies, including broken signal lights: call the NHDOT Traffic "
           "Management Center (603) 271-6862; General Road Concerns on State Roads: call the "
           "appropriate NHDOT Highway Maintenance District Office; General Questions: (603) "
           "271-3734 or info@dot.nh.gov.", NHDOT_CONTACT, ROAD_STATE_READ)]
    + help_claims("lawyer"),
    more=civics.faq(
        ("Who fixes a state route through a city center?",
         "<p>In the built-up centers of the cities and towns the law lists, such as Concord, "
         "Manchester and Nashua, the city or town maintains the state routes too, except the "
         "turnpikes and interstates, which stay the state&rsquo;s.</p>"),
        ("What is a class VI road?",
         "<p>A class VI road is a public way the town does not maintain, and the town has no "
         "duty to repair it.</p>"),
        ("Is every bad road &ldquo;insufficient&rdquo;?",
         "<p>No. A road simply in worse shape than others is not insufficient, and snow and ice "
         "the town is clearing under a winter policy adopted in good faith are generally not a "
         "ground for a claim, unless the town was grossly negligent or reckless.</p>"))
         + "<h2>Who Can Help</h2>"
         "<p>Your town or city&rsquo;s public works or highway department is the place to ask "
         "about a town road, and the town office can tell you who that is. For a claim for "
         "damage, a lawyer can tell you whether you have one:</p>"
         + helps("lawyer"),
    see=[("Who to contact about an issue", "/guides/who-to-contact.html"),
         ("Cities, towns and who runs them", "/learn/city-and-town-government.html")],
    figures=[fig("96 hours", "RSA 230:79", "within 96 hours thereafter"),
             fig("72 hours", "RSA 231:91", "within 72 hours thereafter"),
             fig("60 days", "RSA 507-B:7", "within 60 days after the time of the injury or damage"),
             fig("3 years", "RSA 507-B:7", "within 3 years after the time of injury or damage"),
             fig("180 days", "RSA 541-B:14", "within 180 days after the time of the injury or damage")])

GUIDES += [ROAD_PROBLEM]


# ---------------------------------------------------------------------------
# FISHING, HUNTING AND BOATING (the person, 25 October 2026: "adding things
# like how to get a fishing license, hunting license, boat license, etc would
# be a good fit"). Three guides, resting first on the statutes, read that day
# on this site's own Laws pages (RSA 207, 208, 211, 214, 270, 270-D, 270-E and
# 72-A); then on Fish and Game's online license system (nhfishandgame.com, a
# state system at a .com address, which answers this machine) and the U.S.
# Fish and Wildlife Service's Duck Stamp page, both read the same day. Fish
# and Game's, Marine Patrol's and the DMV's own pages refuse this machine, so
# their claims wait for the person's printouts and hold the guides back
# until then. Hunting and fishing fees are set by Fish and Game (RSA 214:8,
# II; RSA 206:10, I), not by statute, so neither guide prints one: they link
# the fee page. The boating fees the law sets (RSA 270-D:17, 270-E:5) are
# printed, each a fig() held to its section's words.
# ---------------------------------------------------------------------------
OUT_READ = "2026-10-25"
# Fish and Game's, Marine Patrol's and the DMV's own pages, from the person's
# printouts of 25 October 2026 (thirteen PDFs, read page by page).
OUT_STATE_READ = "2026-10-25"
FG_SALT_FAQ = "https://www.wildlife.nh.gov/saltwater-fisheries-new-hampshire/saltwater-fishing-faqs"
NHFG_LICENSE = "https://www.nhfishandgame.com/"
FG_REQUIREMENTS = "https://www.wildlife.nh.gov/licenses-and-permits/nh-license-requirements"
FG_FEES = "https://www.wildlife.nh.gov/fishing-new-hampshire/licenses-and-permits"
FG_FREE_DAYS = "https://www.wildlife.nh.gov/fishing-new-hampshire/free-fishing-days-new-hampshire"
FG_MARINE = "https://www.wildlife.nh.gov/saltwater-fisheries-new-hampshire/marine-licenses-and-permits"
FG_SENIOR = "https://www.wildlife.nh.gov/licenses-and-permits/senior-and-milestone-licenses"
FG_HUNTER_ED = ("https://www.wildlife.nh.gov/hunting-nh/hunter-education/"
                "hunter-education-frequently-asked-questions")
FG_HIP = ("https://www.wildlife.nh.gov/licenses-and-permits/"
          "national-migratory-bird-harvest-information-program-hip")
DUCK_STAMP = "https://www.fws.gov/service/buy-duck-stamp-or-e-stamp"
MP_BOATING_FAQ = ("https://www.nhsp.dos.nh.gov/our-services/field-operations-bureau/marine-patrol/"
                  "boating-education/boating-education-faqs")
MP_TEMPORARY = ("https://www.nhsp.dos.nh.gov/our-services/field-operations-bureau/marine-patrol/"
                "boating-education/14-day-temporary-safe-boating")
DMV_BOATS = "https://www.dmv.nh.gov/vehicles-boats-and-titles/boat-registrations"

# What the license system's own page says, read on 25 October 2026.
NHFG_SAYS = claim(
    "Licenses run on calendar year (except temporary types), expiring on December 31st; must be "
    "purchased by the licensee, who enters residency proof; no refunds or exchanges; sportspersons "
    "without a prior hunting or archery license (or NH safety certificate) in the system cannot buy "
    "their hunting or archery license online and must buy it at a traditional license agent, "
    "showing the prior license or certificate; a license must be printed and signed by the "
    "applicant, except that for fishing licenses (not hunting) an image on a smart phone is "
    "sufficient if a photo ID can be presented; residents 68 and over born 1948 or later buy "
    "discounted senior licenses; those born 1947 or earlier obtain a permanent Milestone license "
    "from Fish and Game in Concord or select agents; HIP permit and deer and turkey registration "
    "online.", NHFG_LICENSE, OUT_READ)

FISHING = guide(
    "fishing-license", "How to Get a Fishing License",
    "Who needs a New Hampshire fishing license and who does not, the free fishing days, saltwater "
    "fishing, and how to buy a license online or from an agent.",
    "Anyone 16 or older needs a license to fish in New Hampshire, in fresh water or salt water, "
    "except on the free fishing days Fish and Game sets each year and in a few other cases (step "
    "1). Buy it online from Fish and Game or from a license agent. Most licenses end on December "
    "31.",
    [ask("Are you under 16?",
         [("Yes", "You may fish without a license."),
          ("No", "You need a license, unless it is a free fishing day.")]),
     ask("Where will you fish?",
         [("Lakes, ponds, rivers and streams", "A freshwater fishing license."),
          ("The coast and tidal waters", "A recreational saltwater license.")])],
    [step("Check whether you need one",
          "<p>To fish in New Hampshire you need a license, and you carry it while you fish. You "
          "do <b>not</b> need one:</p>"
          "<ul><li>if you are under 16;</li>"
          "<li>if you are a New Hampshire resident fishing on your own land;</li>"
          "<li>on a <b>free fishing day</b>. The law lets Fish and Game set 2 days a year when "
          "anyone may fish by angling without a license: the first Saturday in June and the third "
          "Saturday in January, in fresh water or salt water. Season dates, limits and the other "
          "rules still apply, and anyone in a fishing tournament still needs a license that "
          "day.</li></ul>",
          actions=[("Free fishing days", FG_FREE_DAYS)],
          law=["RSA 214:1", "RSA 214:2", "RSA 214:1-e"]),
     step("Choose your license",
          "<p><b>Resident or nonresident.</b> You are a resident for a license if you hold a "
          "New Hampshire driver&rsquo;s license or non-driver photo ID and claim residence in no "
          "other state for any purpose.</p>"
          "<p><b>Fresh water.</b> A resident fishing license, or a one-day license. A "
          "nonresident can buy a season license or a one-day, 3-day or 7-day license. A combined "
          "hunting and fishing license is sold too.</p>"
          "<p><b>Salt water.</b> Fishing for saltwater fish in coastal and tidal waters takes a "
          "recreational saltwater license, unless you are fishing from a licensed charter or party "
          "boat. Anglers 68 or older need it too. It also lets you fish Massachusetts&rsquo; "
          "coastal waters and the whole Maine coast.</p>"
          "<p><b>Lower-cost and free licenses.</b> Residents 68 or older can buy a discounted "
          "senior license; residents born in 1947 or earlier get a free, permanent Milestone "
          "license from Fish and Game in Concord, its regional offices in Lancaster, New Hampton "
          "and Keene, or select agents, or by mail.</p>"
          "<p>Fish and Game sets the fees; its license page lists each license and its "
          "price.</p>",
          actions=[("License fees and requirements", FG_FEES),
                   ("Saltwater licenses", FG_MARINE),
                   ("Senior and Milestone licenses", FG_SENIOR)],
          law=["RSA 207:1", "RSA 214:5-b", "RSA 214:9", "RSA 211:64-b", "RSA 211:18",
               "RSA 214:7-a", "RSA 214:13", "RSA 214:3", "RSA 214:8"]),
     step("Buy it online or from an agent",
          "<p>Buy your license on Fish and Game&rsquo;s online license system or from a license "
          "agent. You buy it yourself, as the person who will use it, and give proof of where you "
          "live.</p>"
          "<p>Print your license and sign it, or keep an image of it on your phone: for a fishing "
          "license, that is enough if you can also show a photo ID. Carry it while you fish, and "
          "show it when asked.</p>"
          "<p>A license ends on <b>December 31</b> of the year you bought it, unless it is one "
          "of the permanent licenses, and cannot be passed to anyone else.</p>",
          actions=[("Buy a license online", NHFG_LICENSE)],
          law=["RSA 214:1", "RSA 214:36"]),
     step("Before you go",
          "<p>Seasons, limits and the waters with special rules vary. Check Fish and "
          "Game&rsquo;s rules for the water you plan to fish.</p>",
          actions=[("License requirements", FG_REQUIREMENTS)])],
    [("Buy a license online (NH Fish and Game)", NHFG_LICENSE),
     ("License fees and requirements (NH Fish and Game)", FG_FEES),
     ("NH license requirements (NH Fish and Game)", FG_REQUIREMENTS),
     ("Free fishing days (NH Fish and Game)", FG_FREE_DAYS),
     ("Marine licenses and permits (NH Fish and Game)", FG_MARINE),
     ("Saltwater fishing questions (NH Fish and Game)", FG_SALT_FAQ),
     ("Senior and Milestone licenses (NH Fish and Game)", FG_SENIOR),
     ("Fish and game licenses, RSA 214", "/laws/214"),
     ("Marine fisheries, RSA 211", "/laws/211")],
    ["207", "211", "214"],
    [claim("No person shall fish without first procuring a proper and valid license, and the "
           "licensee shall carry it when so engaged, subject to inspection on demand.", "RSA 214:1",
           OUT_READ),
     claim("RSA 214:1 shall not apply to resident land owners while upon their own land or to "
           "persons under 16 years of age while fishing; fishing licenses may be issued without "
           "charge to resident legally blind persons, effective for the remainder of the "
           "person's life.", "RSA 214:2", OUT_READ),
     claim("The executive director may adopt rules establishing 2 days per year on which persons "
           "may fish by angling only without a license, except that anglers in a fishing "
           "tournament on either day shall possess a valid fishing license.", "RSA 214:1-e",
           OUT_READ),
     claim("Resident: a resident of the state as defined in RSA 21:6, except that no person shall "
           "be deemed a resident who claims residence in any other state for any purpose.",
           "RSA 207:1", OUT_READ),
     claim("A nonresident full-time student in this state may purchase a nonresident student "
           "license for hunting or fishing at the fee charged to a resident.", "RSA 214:5-b",
           OUT_READ),
     claim("Resident fishing license; one-day resident fishing license; resident hunting and "
           "fishing license; nonresident fishing license; 7-day, 3-day and one-day nonresident "
           "fishing licenses; recreational saltwater license for finfish from coastal and "
           "estuarine waters, persons on a licensed for-hire vessel exempt.", "RSA 214:9",
           OUT_READ),
     claim("No person shall take clams for such person's own use unless the person is a resident "
           "of the state and has been duly licensed.", "RSA 211:64-b", OUT_READ),
     claim("No person shall take lobsters and crabs without first procuring a valid and proper "
           "license.", "RSA 211:18", OUT_READ),
     claim("Any resident 68 years of age or over may apply each year for a special license to "
           "fish and hunt, at no more than 50 percent of the regular resident fee.", "RSA 214:7-a",
           OUT_READ),
     claim("A resident totally and permanently disabled from service-connected disability, "
           "discharged other than dishonorably, is issued a perpetual special veteran's license; "
           "a $10 administrative fee shall be charged once.", "RSA 214:13", OUT_READ),
     claim("A resident on regular active duty permanently stationed outside the state may acquire "
           "at no charge a special license to hunt and fish while on leave or furlough.",
           "RSA 214:3", OUT_READ),
     claim("All licenses shall expire on December 31 next following their issuance, and shall not "
           "be transferable.", "RSA 214:36", OUT_READ),
     claim("The executive director shall set fees for the various license types described in "
           "RSA 214:9.", "RSA 214:8", OUT_READ),
     NHFG_SAYS,
     # Fish and Game's own pages, from the person's printouts.
     claim("Two free fishing days each year: the first Saturday in June and the third Saturday "
           "in January; residents and nonresidents alike can fish any inland water or saltwater "
           "without a license; season dates, bag limits and all other regulations must be "
           "followed; persons in a fishing tournament must still hold a license; youth under 16 "
           "do not need a license.", FG_FREE_DAYS, OUT_STATE_READ),
     claim("License prices for each license type, resident and nonresident.", FG_FEES,
           OUT_STATE_READ),
     claim("A New Hampshire resident is someone who holds a valid NH driver's license or "
           "non-driver photo identification and does not claim a residence in any other state "
           "for any purpose; one-day licenses for residents, 1-, 3- and 7-day licenses for "
           "nonresidents; clam and oyster licenses for residents only.", FG_REQUIREMENTS,
           OUT_STATE_READ),
     claim("All persons 16 and older recreationally fishing in coastal and estuarine waters must "
           "purchase a NH Saltwater Recreational Fishing License; lobster and crab licenses "
           "separately.", FG_MARINE, OUT_STATE_READ),
     claim("All anglers 16 and older, those 68 and older included, must pay for the recreational "
           "saltwater license; it allows fishing in NH coastal and estuarine waters, all "
           "Massachusetts coastal and estuarine waters, and the entire Maine coast; exempt on a "
           "licensed charter or party boat.", FG_SALT_FAQ, OUT_STATE_READ),
     claim("Discounted senior licenses for residents at least 68 at purchase and born in or after "
           "1948, bought annually; free permanent Milestone licenses for residents born in or "
           "before 1947, only at Fish and Game headquarters or Regional Offices 1 (Lancaster), 2 "
           "(New Hampton), 4 (Keene), and at limited license agents; you may also print and mail "
           "an application to headquarters in Concord; not valid if the holder moves out of "
           "state.", FG_SENIOR,
           OUT_STATE_READ)],
    more=civics.faq(
        ("Is a fishing license free for someone who is blind?",
         "<p>A New Hampshire resident who is legally blind may get a fishing license free, and "
         "it lasts for life.</p>"),
        ("I am a student from another state. What do I pay?",
         "<p>A nonresident full-time student at a school or college in New Hampshire pays the "
         "resident fee.</p>"),
        ("Do I need a license to dig clams or take lobsters?",
         "<p>Yes. Digging clams takes a separate license, sold to residents only, and taking "
         "lobsters or crabs another.</p>"),
        ("Are there licenses for veterans and service members?",
         "<p>A resident veteran, discharged other than dishonorably, who is totally and "
         "permanently disabled from a service-connected disability gets a permanent license, "
         "with a one-time $10 administrative fee. A resident on active duty "
         "stationed outside the state can get a free license to use while home on leave.</p>"),
        ("Can I get a refund?",
         "<p>No. Fish and Game cannot refund a license or exchange it.</p>")),
    see=[("How to get a hunting license", "/guides/hunting-license.html"),
         ("Boating: your certificate and registration", "/guides/boating.html")],
    figures=[fig("2 days", "RSA 214:1-e", "establishing 2 days per year"),
             fig("3-day", "RSA 214:9", "3-day nonresident fishing license"),
             fig("7-day", "RSA 214:9", "7-day nonresident fishing license"),
             fig("$10", "RSA 214:13", "A $10 administrative fee shall be charged once")])

GUIDES += [FISHING]

HUNTING = guide(
    "hunting-license", "How to Get a Hunting License",
    "Hunter education, the apprentice license, licenses for turkey, pheasant and waterfowl, and how "
    "to buy a New Hampshire hunting license.",
    "To buy a hunting license you need a hunter education certificate, or proof that you have held "
    "a hunting license before. A first-time hunter takes the course first, or buys an apprentice "
    "license once and hunts beside a licensed adult. Turkey, pheasant and waterfowl each need a "
    "license on top of it, and most licenses end on December 31.",
    [ask("Have you held a hunting license before?",
         [("Yes", "Show that license to buy a new one."),
          ("No", "Take hunter education, or buy an apprentice license once.")]),
     box("Then buy any extra license your hunt needs: archery, turkey, pheasant or waterfowl.")],
    [step("Take hunter education, or show a past license",
          "<p>No hunting license is sold without one of these:</p>"
          "<ul><li>a certificate from a <b>hunter education</b> course in New Hampshire;</li>"
          "<li>proof you completed an equivalent course in another state, province or "
          "country;</li>"
          "<li>proof you have held a hunting license before, here or elsewhere.</li></ul>"
          "<p>To hunt with a bow you need the same for <b>bow hunter education</b>: an archery "
          "license and a hunting license do not stand in for each other. Fish and "
          "Game&rsquo;s page lists the courses and how to sign up.</p>",
          actions=[("Hunter education", FG_HUNTER_ED)],
          law=["RSA 214:23-a"]),
     step("Or start with an apprentice license",
          "<p>If you have not taken the course, you may buy an <b>apprentice hunting "
          "license</b>, once in your lifetime. You may hunt with it only beside a licensed hunter "
          "who is 18 or older, who answers for what you do.</p>",
          law=["RSA 214:6-a"]),
     step("Hunters under 16",
          "<p>A hunter under 16 may hunt only with a properly licensed person 18 or older, and "
          "needs no general hunting license while hunting with that person. A young hunter must "
          "still buy some special licenses: for turkey, bear, a special archery deer, or the "
          "Unit M and Unit L deer permits; and a nonresident under 16 a muzzleloader "
          "license.</p>",
          law=["RSA 207:2-a", "RSA 214:2"]),
     step("Choose your licenses",
          "<p>Start with a resident or nonresident <b>hunting license</b>, or a combined hunting "
          "and fishing license. You are a resident for a license if you hold a New Hampshire "
          "driver&rsquo;s license or non-driver photo ID and claim residence in no other state "
          "for any purpose.</p>"
          "<p>Add what your hunt needs:</p>"
          "<ul><li>an <b>archery license</b> to hunt with a bow;</li>"
          "<li>a <b>turkey</b> license or permit to hunt wild turkey;</li>"
          "<li>a <b>pheasant</b> license to hunt pheasant;</li>"
          "<li>a <b>bear</b> license to hunt bear;</li>"
          "<li>a <b>muzzleloader</b> license for the muzzleloader deer season;</li>"
          "<li>for ducks and geese, a state <b>waterfowl</b> license and the federal <b>Duck "
          "Stamp</b>. A Duck Stamp is sold at most post offices, and you sign it for it to be "
          "valid;</li>"
          "<li>for any migratory bird, such as ducks, geese, woodcock, snipe or coot, a free "
          "<b>HIP</b> permit number if you are 16 or older.</li></ul>"
          "<p>Fish and Game sets the fees; its license page lists them.</p>",
          actions=[("License fees and requirements", FG_FEES),
                   ("The HIP permit", FG_HIP),
                   ("Buy a Duck Stamp", DUCK_STAMP)],
          law=["RSA 207:1", "RSA 214:9", "RSA 208:5", "RSA 214:1-b", "RSA 214:1-c",
               "RSA 214:1-d", "RSA 214:7-a", "RSA 214:13"]),
     step("Buy it, print it and sign it",
          "<p>If you have bought a hunting license from New Hampshire before, you can buy online. "
          "A first-time buyer cannot: go to a license agent with your hunter education certificate "
          "or your past license.</p>"
          "<p>A hunting license must be printed and signed to be valid. Carry it while you hunt. "
          "It ends on <b>December 31</b>, and Fish and Game cannot refund it.</p>",
          actions=[("Buy a license online", NHFG_LICENSE)],
          law=["RSA 214:8", "RSA 214:1", "RSA 214:36"]),
     step("In the field",
          "<p>A deer you take must be <b>registered</b>; you can do it online, as you can a "
          "turkey.</p>",
          actions=[("Register a deer or turkey", NHFG_LICENSE)],
          law=["RSA 207:38-b", "RSA 208:15-g"])],
    [("Buy a license online (NH Fish and Game)", NHFG_LICENSE),
     ("License fees and requirements (NH Fish and Game)", FG_FEES),
     ("NH license requirements (NH Fish and Game)", FG_REQUIREMENTS),
     ("Hunter education questions (NH Fish and Game)", FG_HUNTER_ED),
     ("The HIP permit (NH Fish and Game)", FG_HIP),
     ("Senior and Milestone licenses (NH Fish and Game)", FG_SENIOR),
     ("Buy a Duck Stamp (U.S. Fish and Wildlife Service)", DUCK_STAMP),
     ("Fish and game licenses, RSA 214", "/laws/214"),
     ("Hunting, RSA 207 and 208", "/laws/207")],
    ["207", "208", "214"],
    [claim("No hunting license shall be issued unless the applicant presents a certificate of "
           "completion from a basic hunter education program, proof of an equivalent program in "
           "any state, province or country, or proof of a previous hunting license; the same for "
           "an archery license and bow hunter education; neither license is proof of the "
           "other.", "RSA 214:23-a", OUT_READ),
     claim("An apprentice hunting license allows hunting only when accompanied by a properly "
           "licensed person 18 years of age or over, who is accountable; not valid for moose; not "
           "proof of a previous license; may be purchased only once in the lifetime of the "
           "hunter.", "RSA 214:6-a", OUT_READ),
     claim("No minor under 16 shall hunt using a firearm, bow and arrow, air rifle, or crossbow "
           "except when accompanied by a person at least 18 years of age who is properly "
           "licensed.", "RSA 207:2-a", OUT_READ),
     claim("RSA 214:1 shall not apply to persons under 16 years of age while hunting when "
           "accompanied by a licensee 18 years of age or over.", "RSA 214:2", OUT_READ),
     claim("Resident: a resident of the state as defined in RSA 21:6, except that no person shall "
           "be deemed a resident who claims residence in any other state for any purpose.",
           "RSA 207:1", OUT_READ),
     claim("Resident and nonresident hunting licenses; resident and nonresident hunting and "
           "fishing licenses; pheasant, wild turkey and migratory waterfowl licenses.",
           "RSA 214:9", OUT_READ),
     claim("Archery licenses for residents and nonresidents; the licensee may hunt wildlife with "
           "bow and arrow.", "RSA 208:5", OUT_READ),
     claim("No person shall hunt pheasants without, in addition to the hunting license, a "
           "pheasant license.", "RSA 214:1-b", OUT_READ),
     claim("No person shall hunt wild turkey without, in addition to the hunting license, a "
           "permit or license.", "RSA 214:1-c", OUT_READ),
     claim("No person shall hunt migratory waterfowl without, in addition to the hunting license "
           "and the federal duck stamp, a state migratory waterfowl license.", "RSA 214:1-d",
           OUT_READ),
     claim("Any resident 68 years of age or over may apply each year for a special license to "
           "fish and hunt, at no more than 50 percent of the regular resident fee.", "RSA 214:7-a",
           OUT_READ),
     claim("A resident totally and permanently disabled from service-connected disability, "
           "discharged other than dishonorably, is issued a perpetual special veteran's license; "
           "a $10 administrative fee shall be charged once.", "RSA 214:13", OUT_READ),
     claim("The license, to be valid, shall be countersigned by the licensee; the executive "
           "director shall set fees.", "RSA 214:8", OUT_READ),
     claim("No person shall hunt without first procuring a proper and valid license, and the "
           "licensee shall carry it when so engaged.", "RSA 214:1", OUT_READ),
     claim("All licenses shall expire on December 31 next following their issuance, and shall not "
           "be transferable.", "RSA 214:36", OUT_READ),
     claim("Any person hunting with a firearm or bow and arrow, except a person legally hunting "
           "waterfowl, should wear a hat, vest or other suitable clothing of hunter orange "
           "visible from all sides.", "RSA 207:38-b", OUT_READ),
     claim("No person shall possess any deer which has not been legally registered.",
           "RSA 208:15-g", OUT_READ),
     NHFG_SAYS,
     claim("A physical Federal Duck Stamp is sold at most U.S. Post Offices, participating "
           "retailers, select refuges and online; to be valid for hunting you must sign your "
           "physical stamp upon receipt.", DUCK_STAMP, OUT_READ),
     # Fish and Game's own pages, from the person's printouts.
     claim("To receive a certificate of completion in hunter education you must be at least 12, "
           "for the in-person course and the online course with required in-person field day.",
           FG_HUNTER_ED, OUT_STATE_READ),
     claim("License prices for each license type, resident and nonresident.", FG_FEES,
           OUT_STATE_READ),
     claim("A general firearm hunting, fishing or archery license is not required for minors "
           "under 16; minors must purchase Special Archery Deer, Turkey, Bear, additional bear, "
           "and Unit M and Unit L special deer tags; nonresident minors under 16 must also "
           "purchase a muzzleloader license; a resident holds a valid NH driver's license or "
           "non-driver photo ID and claims no residence in any other state; licenses for bear, "
           "muzzleloader, wild turkey, pheasant and migratory waterfowl, which also needs a "
           "federal waterfowl stamp and a HIP permit number; buying a hunting or archery license "
           "for the first time in NH must be in person at a traditional license agent.",
           FG_REQUIREMENTS, OUT_STATE_READ),
     claim("Hunters aged 16 and older intending to hunt migratory game birds (including ducks, "
           "geese, snipe, woodcock and coot) must have a HIP permit number; there is no charge.",
           FG_HIP, OUT_STATE_READ),
     claim("Senior licenses for residents 68 and older, and the Milestone license.", FG_SENIOR,
           OUT_STATE_READ)],
    more=civics.faq(
        ("How old must I be for hunter education, and is the course online?",
         "<p>You must be at least 12 to get the certificate, and the online course ends with an "
         "in-person field day.</p>"),
        ("What can I not do with an apprentice license?",
         "<p>It is not valid for moose, and it does not count as a past license when you buy "
         "your next one.</p>"),
        ("Are there discounted licenses?",
         "<p>Residents 68 or older can buy discounted senior licenses, and a resident veteran, "
         "discharged other than dishonorably, who is totally and permanently disabled from a "
         "service-connected disability gets a permanent license, with a one-time $10 "
         "administrative fee.</p>"),
        ("Do I have to wear hunter orange?",
         "<p>The law recommends that anyone hunting with a firearm or a bow, except for "
         "waterfowl, wear a hat, vest or other clothing in <b>hunter orange</b> that can be seen "
         "from all sides.</p>")),
    see=[("How to get a fishing license", "/guides/fishing-license.html"),
         ("Boating: your certificate and registration", "/guides/boating.html")],
    figures=[fig("$10", "RSA 214:13", "A $10 administrative fee shall be charged once")])

GUIDES += [HUNTING]

BOATING = guide(
    "boating", "Boating: Your Safe Boater Certificate and Boat Registration",
    "Who needs New Hampshire's safe boater education certificate, how to get it, and how to "
    "register a boat each year.",
    "To run a boat with a motor of more than 25 horsepower you need a <b>safe boater education "
    "certificate</b>, which lasts for life; the state&rsquo;s fee for it is $10, and all fees "
    "together, the course included, may not exceed $50. A boat with a motor, and a sailboat 12 "
    "feet or longer, must also be <b>registered</b> every year, at the DMV or a boat agent; every "
    "registration ends on December 31.",
    [ask("Does your boat have a motor of more than 25 horsepower?",
         [("Yes", "You need a safe boater education certificate to run it."),
          ("No", "No certificate is needed.")]),
     ask("Does it need registering?",
         [("A boat with any motor, or a sailboat 12 feet or longer", "Yes, every year."),
          ("A rowboat or canoe with no motor, or a sailboat under 12 feet", "No.")])],
    [step("Get your safe boater education certificate",
          "<p>You need the certificate to operate a boat with a motor of more than 25 horsepower "
          "on New Hampshire&rsquo;s public waters. To get it, pass a safe boater education course "
          "approved by the state, or an equivalency exam. Adults may take the exam online; anyone "
          "under 18 takes a supervised exam.</p>"
          "<p>It is issued from age 16, and if you pass at 15 you receive it when you turn 16. It "
          "lasts for life. The state charges $10 for it, and all the fees you can be charged for "
          "it, the course included, may not exceed $50.</p>"
          "<p>Carry it, or a copy or a photo of the front and back on your phone, while you "
          "operate, and show it to a Marine Patrol officer who asks.</p>",
          actions=[("Boating education", MP_BOATING_FAQ)],
          law=["RSA 270-D:10", "RSA 270-D:13", "RSA 270-D:15", "RSA 270-D:17", "RSA 270-D:11"]),
     step("Visiting or renting: a temporary certificate",
          "<p>If you are 16 or older and do not have a certificate, a boat dealer or rental "
          "business approved by the state can give you a short exam and a <b>temporary "
          "certificate</b>, good for up to 14 days and for New Hampshire&rsquo;s waters only. "
          "Bring a photo ID to the exam. It costs $10, and you can get no more than one in a "
          "calendar year; it is meant as a short-term answer, not a substitute for the "
          "course.</p>",
          actions=[("The temporary certificate", MP_TEMPORARY)],
          law=["RSA 270-D:14", "RSA 270-D:17"]),
     step("Young boaters",
          "<p>A person under 16 may operate a boat with a motor of more than 25 horsepower only "
          "with a person 18 or older aboard who holds a safe boater certificate. A personal "
          "watercraft (the law calls it a ski craft) may be operated only by someone 16 or "
          "older.</p>",
          law=["RSA 270:30", "RSA 270:74", "RSA 270:30-a"]),
     step("Register your boat every year",
          "<p>Every boat on New Hampshire&rsquo;s waters must be registered and display a "
          "<b>boat fee decal</b>, except a sailboat under 12 feet, a rowboat or canoe moved by "
          "oars, paddles or sail with no motor, and a boat registered elsewhere that is here for "
          "not more than 30 consecutive days.</p>"
          "<p>Register through the DMV&rsquo;s drop box service, with an authorized boat agent, "
          "or by mail to the DMV in Concord. Bring the registration application, proof you own the boat (a bill of sale "
          "signed by you and the seller), your driver&rsquo;s license and the fees.</p>"
          + table("The registration fee, by the boat&rsquo;s length (RSA 270-E:5)",
                  ["Length", "Registration fee"],
                  [["Up to 16 feet", "$24"], ["Over 16, up to 21 feet", "$34"],
                   ["Over 21, up to 30 feet", "$52"], ["Over 30, up to 45 feet", "$72"],
                   ["Over 45 feet", "$92"]])
          + "<p>An agent who is not a DMV employee adds $5 to the registration fee. The "
          "boat fee decal and the boat fee, which depends on the kind of boat, its length and its "
          "age, are paid with it; the DMV&rsquo;s boat registration office, (603) 227-4030, can "
          "tell you the total for your boat. The DMV mails a renewal notice before the "
          "registration ends.</p>"
          "<p>Keep the registration certificate aboard. Every registration ends on <b>December "
          "31</b>.</p>",
          actions=[("Boat registration (DMV)", DMV_BOATS),
                   ("The boat fee table, RSA 72-A:3", "/laws/72-a#s3")],
          law=["RSA 270-E:3", "RSA 270-E:4", "RSA 270-E:5", "RSA 270-E:5-a", "RSA 72-A:3",
               "RSA 270-E:8", "RSA 270-E:10"])],
    [("Boating education (NH State Police, Marine Patrol)", MP_BOATING_FAQ),
     ("The 14-day temporary certificate (NH State Police, Marine Patrol)", MP_TEMPORARY),
     ("Boat registrations (NH DMV)", DMV_BOATS),
     ("Boating safety education, RSA 270-D", "/laws/270-d"),
     ("Boat registration, RSA 270-E", "/laws/270-e"),
     ("The boat fee, RSA 72-A", "/laws/72-a"),
     ("Boating, RSA 270", "/laws/270")],
    ["72-A", "270", "270-D", "270-E"],
    [claim("No person shall operate a motorized vessel with any type of power motor in excess of "
           "25 horsepower on the public waters of this state without first obtaining a "
           "certificate of boating safety education.", "RSA 270-D:10", OUT_READ),
     claim("The certificate is issued to a person 16 years of age or older who passes an approved "
           "course, with an online examination if 18 or older or a proctored examination if "
           "under 18, or an equivalency examination; valid for the lifetime of the person; a "
           "person who passes after reaching the age of 15 is issued it upon attaining 16.",
           "RSA 270-D:13", OUT_READ),
     claim("A certificate is not required of a person holding a certificate from any state that "
           "meets these requirements, from the U.S. Coast Guard Auxiliary, the U.S. Power "
           "Squadron, or an approved Canadian certificate.", "RSA 270-D:15", OUT_READ),
     claim("The department shall charge a fee of $10 for issuing a safe boater education "
           "certificate; the fee for a temporary certificate shall be $10; the total of all fees "
           "shall not exceed $50.", "RSA 270-D:17", OUT_READ),
     claim("The certificate shall be a physical original or copy, an electronic copy, or a "
           "photograph of the front and back, possessed while operating and presented on demand "
           "of a marine patrol officer.", "RSA 270-D:11", OUT_READ),
     claim("A temporary certificate is issued to a person 16 or older who passes a temporary "
           "examination, valid for up to 14 days on New Hampshire waters only; no more than one "
           "in any calendar year; dealers and renters approved by the commissioner may give "
           "it.", "RSA 270-D:14", OUT_READ),
     claim("No person under 16 years of age shall operate a motorized vessel having power in "
           "excess of 25 horsepower unless accompanied by a person 18 years of age or older who "
           "has a valid safe boater education certificate.", "RSA 270:30", OUT_READ),
     claim("No person shall operate a ski craft on any lake, pond, or river unless the person is "
           "16 years of age or older.", "RSA 270:74", OUT_READ),
     claim("No child 12 years of age or under shall operate, control, or be transported on the "
           "deck of a boat which is underway unless wearing a Coast Guard approved personal "
           "flotation device, with an exception for boats with continuous side rails.",
           "RSA 270:30-a", OUT_READ),
     claim("No person shall put, place, or operate a vessel on any waters of the state unless it "
           "is registered; the certificate shall be kept upon the vessel; registrations expire on "
           "December 31; the commissioner may authorize agents.", "RSA 270-E:3", OUT_READ),
     claim("Exempt: sailboats under 12 feet in length, rowboats and canoes powered by sail, oars, "
           "paddles, or other human power, any vessel with a motor not exempt; vessels registered "
           "in another state temporarily using these waters for not more than 30 consecutive "
           "days.", "RSA 270-E:4", OUT_READ),
     claim("Registration fees by length: up to and including 16 feet $24; 16.1 to 21 feet $34; "
           "21.1 to 30 feet $52; 30.1 to 45 feet $72; 45.1 feet and over $92; $5 for each "
           "registration processed by an authorized agent who is not an employee of the "
           "department.", "RSA 270-E:5", OUT_READ),
     claim("No person shall operate a vessel unless it displays a boat fee decal.",
           "RSA 270-E:5-a", OUT_READ),
     claim("The boat fee by kind, length and age of the boat.", "RSA 72-A:3", OUT_READ),
     claim("Numbers on each side of the forward half of the vessel, not less than 3 inches in "
           "height, with block letters of contrasting color.", "RSA 270-E:8", OUT_READ),
     claim("The owner shall furnish written notice of the transfer, destruction or abandonment of "
           "a vessel within 15 days.", "RSA 270-E:10", OUT_READ),
     # Marine Patrol's and the DMV's own pages, from the person's printouts.
     claim("After a classroom course, or an online course and its online or proctored exam, the "
           "certificate card is mailed; for students who take a course at 15, on or around the "
           "16th birthday; children 12 and younger must wear a life jacket when transported in a "
           "boat; the 14-day temporary certificate through an agent.", MP_BOATING_FAQ,
           OUT_STATE_READ),
     claim("Under RSA 270-D:14, a 14-day temporary certificate, valid only in New Hampshire; "
           "only a short-term solution; a minimum of 16 years of age; picture identification at "
           "the time of the test.", MP_TEMPORARY, OUT_STATE_READ),
     claim("To register: a completed Boat Registration Application, proof of ownership (a bill "
           "of sale with the signatures of the applicant and the seller), the owner's driver "
           "license, and the fees, for which call the DMV Boat Registration office at (603) "
           "227-4030; by drop box, at authorized boat agents, or by mail to the Concord DMV; "
           "registrations expire December 31 and the DMV mails renewal notices before then.",
           DMV_BOATS, OUT_STATE_READ)],
    more=civics.faq(
        ("Does a boating certificate from another state count?",
         "<p>A certificate from another state whose course meets New Hampshire&rsquo;s "
         "standard, or one from the U.S. Coast Guard Auxiliary, the U.S. Power Squadron, or an "
         "approved Canadian card, counts instead.</p>"),
        ("Must children wear a life jacket?",
         "<p>A child 12 or under must wear a Coast Guard approved life jacket on the deck of a "
         "boat that is underway, unless the boat has the side rails the law describes.</p>"),
        ("How do I display my registration number?",
         "<p>Display the number on each side of the front half of the boat, in block letters at "
         "least 3 inches high in a contrasting color.</p>"),
        ("What if I sell my boat?",
         "<p>If you sell the boat, or it is destroyed or abandoned, tell the DMV in writing "
         "within 15 days.</p>")),
    see=[("How to get a fishing license", "/guides/fishing-license.html"),
         ("How to get a hunting license", "/guides/hunting-license.html")],
    figures=[fig("age 16", "RSA 270-D:13", "a person 16 years of age or older"),
             fig("$10", "RSA 270-D:17", "a fee of $10 for issuing a safe boater education certificate"),
             fig("$50", "RSA 270-D:17", "shall not exceed $50"),
             fig("14 days", "RSA 270-D:14", "valid for up to 14 days"),
             fig("30 consecutive days", "RSA 270-E:4", "not more than 30 consecutive days"),
             fig("15 days", "RSA 270-E:10", "within 15 days"),
             fig("$24", "RSA 270-E:5", "Up to and including 16 feet $24"),
             fig("$34", "RSA 270-E:5", "16.1 feet to 21 feet $34"),
             fig("$52", "RSA 270-E:5", "21.1 feet to 30 feet $52"),
             fig("$72", "RSA 270-E:5", "30.1 feet to 45 feet $72"),
             fig("$92", "RSA 270-E:5", "45.1 feet and over $92"),
             fig("$5", "RSA 270-E:5", "there shall be $5 collected for each registration")])

GUIDES += [BOATING]


# ---------------------------------------------------------------------------
# INSURANCE: CAR, RENTERS AND HOMEOWNERS (the person, 26 October 2026: "add
# guides to insurance like car insurance, renters insurance, homeowner's
# insurance, private health insurance, etc."). What the law requires rests on
# the statutes, read on 26 October 2026 as the Laws pages print them: the
# financial responsibility law (RSA 264) for when the state asks a driver for
# proof of insurance, the least a car policy must cover (RSA 259:61) and the
# uninsured motorist and medical payments coverage every policy carries; the
# rules on cancelling a car policy (RSA 417-A) and a home or renters policy
# (RSA 417-B); and the unfair claim practices the Insurance Department
# enforces (RSA 417). No statute on this disk was found to require car
# insurance to register a car, and the Insurance Department's Automobile
# Insurance page, in the person's printout of 26 October 2026, does not say
# either way ("Most states require that you purchase some kind of insurance
# coverage"), so the car guide says only what the financial responsibility
# law does. The Department's pages refuse this machine and were read in the
# person's printouts that day (Automobile Insurance, Homeowners and Renters
# Insurance, Filing a Complaint, matched by their titles), with its Consumer
# Complaint Form. The guides recommend no insurer and no amount of
# coverage. FEMA's FloodSmart page answers this machine and was read the
# same day (guide_sources.OTHER).
# ---------------------------------------------------------------------------
INS_LAW_READ = "2026-10-26"
INS_DEPT_READ = "2026-10-26"         # the person's printouts of insurance.nh.gov
FLOOD_READ = "2026-10-26"
INS_AUTO = "https://www.insurance.nh.gov/consumers/automobile-insurance"
INS_HOME = "https://www.insurance.nh.gov/consumers/homeowners-and-renters-insurance"
INS_COMPLAINT = "https://www.insurance.nh.gov/consumers/filing-complaint"
# The Department's Auto Insurance Consumer Guide, whose address the person gave
# with their printout of it (26 October 2026).
INS_AUTO_GUIDE = "https://mm.nh.gov/files/uploads/nhid/documents/nh-auto-guide.pdf"
FLOOD_ELIGIBLE = "https://www.floodsmart.gov/get-insured/eligibility"

# The complaint step and its claims, which the renters and homeowners guides
# share: the unfair claim practices of RSA 417:4, XV, and what a consumer may
# do after the Insurance Department has acted on a complaint, or has not.
PROPERTY_CLAIM_STEP = step(
    "If you have a loss: filing a claim",
    "<p>Tell your insurance company about the loss as your policy directs, and keep a record of "
    "what you send and when. The law treats it as an <b>unfair claim settlement practice</b> "
    "for an insurer, without just cause, to fail to act promptly on what you send about a "
    "claim, to fail to try in good faith to settle fairly and promptly once its liability is "
    "reasonably clear, or to fail to say whether it covers the claim within a reasonable time "
    "after you send the proof of loss forms.</p>",
    law=["RSA 417:4"])
PROPERTY_COMPLAINT_STEP = step(
    "If you disagree with your insurer: complain to the Insurance Department",
    "<p>The <b>New Hampshire Insurance Department</b> takes complaints about insurance "
    "companies and agents. Its Filing a Complaint page has an online complaint form, and a "
    "printable Consumer Complaint Form to mail or fax to the Department. If you complain for "
    "someone else, such as a spouse, an adult child or a friend, also send its Release of "
    "Information Form. A Consumer Services Officer reviews what you send and, if the "
    "Department has authority over it, forwards it to the company or agent for a response; if "
    "not, the officer refers it to the agency that has and tells you by letter. The Department "
    "is not always able to get you the remedy you want. The Insurance Commissioner may examine "
    "and investigate an insurer&rsquo;s practices.</p>"
    "<p>With a question, call Consumer Services at (603) 271-2261, toll free in New Hampshire "
    "at 1-800-852-3416, or email consumerservices@ins.nh.gov.</p>"
    "<p>If the Department finds that an insurer broke the law and its finding becomes final, a "
    "consumer harmed by the practice may sue the insurer for the loss, and one who wins also "
    "recovers the cost of the suit, reasonable attorney&rsquo;s fees included. If the Department "
    "takes no action within 120 days of receiving your complaint, that counts as a finding of no "
    "violation, which you may appeal.</p>",
    actions=[("File a complaint (Insurance Department)", INS_COMPLAINT)],
    law=["RSA 417:5", "RSA 417:19", "RSA 417:20"])
PROPERTY_CLAIM_CLAIMS = [
    claim("Unfair claim settlement practices, if committed without just cause and not merely "
          "inadvertently or accidentally: failing to acknowledge and act promptly upon "
          "communications with respect to claims; not attempting in good faith to effectuate "
          "prompt, fair and equitable settlements of claims in which liability has become "
          "reasonably clear; failing to affirm or deny coverage of claims within a reasonable "
          "time after proof of loss forms have been submitted.", "RSA 417:4", INS_LAW_READ),
    claim("The commissioner may examine and investigate the affairs of every person engaged in "
          "the business of insurance in this state.", "RSA 417:5", INS_LAW_READ),
    claim("When a supplier has been found in violation and the finding has become final, any "
          "consumer adversely affected may bring suit to recover damages; failure of the "
          "commissioner to take action within 120 days from the date of the receipt of a "
          "complaint shall constitute a finding that the practice is not in violation, which "
          "may be appealed in accordance with RSA 541.", "RSA 417:19", INS_LAW_READ),
    claim("A consumer who prevails in an action under RSA 417:19, I recovers, in addition to "
          "damages, the cost of the suit, including reasonable attorneys' fees.", "RSA 417:20",
          INS_LAW_READ),
    claim("Consumer Complaint Forms: Online Consumer Complaint Form (Electronic version); "
          "Consumer Complaint Form (Printable), intended to be printed for completion and mailed "
          "or faxed to the New Hampshire Insurance Department; Auto Body Shop Complaint Form; "
          "Health Provider Complaint Form; Release of Information Form. If you are submitting a "
          "grievance or request for someone other than yourself (such as a spouse, adult child, "
          "friend, patient, customer, etc.), please also complete and submit the Release of "
          "Information Form. If the CSO assigned to your case determines the Department has the "
          "jurisdictional authority to intervene on your behalf, he/she will forward your "
          "submission to the appropriate licensee for a response. The Insurance Department is "
          "not always able to negotiate the remedy you desire. If the issue does not fall within "
          "the jurisdiction of the Insurance Department, your CSO will refer your complaint to "
          "that agency and will inform you of the referral by letter. Contact the department's "
          "Consumer Services Unit at 800-852-3416 or via email at consumerservices@ins.nh.gov. "
          "21 South Fruit Street, Suite 14, Concord, NH 03301; Phone: (603) 271-2261.", INS_COMPLAINT, INS_DEPT_READ)]
PROPERTY_CANCEL_CLAIMS = [
    claim("Chapter 417-B applies to insurance other than automobile and workers' compensation "
          "on personal, family, and household risks insuring loss of or damage to real property, "
          "loss of or damage to personal property, or legal liability for loss of, damage to, or "
          "injury to persons or property.", "RSA 417-B:1", INS_LAW_READ),
    claim("No insurer shall cancel or refuse to write or renew such a policy solely because of "
          "age, residence, race, color, creed, national origin, ancestry, marital status, or "
          "lawful occupation, including the military service, or solely because another insurer "
          "has refused to write, cancelled or refused to renew.", "RSA 417-B:2", INS_LAW_READ),
    claim("No insurer shall cancel, refuse to write, or refuse to renew solely on the basis of "
          "credit information, without consideration of any other underwriting factor.",
          "RSA 417-B:2-a", INS_LAW_READ),
    claim("After a policy has been in effect for 90 days, or if it is a renewal, an insurer may "
          "cancel only for nonpayment of premium; conviction of a crime increasing a hazard "
          "insured against; fraud or material misrepresentation in pursuing a claim; grossly "
          "negligent acts substantially increasing the hazards; physical changes making the "
          "property uninsurable; or the specific request of the insured.", "RSA 417-B:3",
          INS_LAW_READ),
    claim("A written notice of cancellation or refusal to renew, effective not less than 45 days "
          "after it is mailed or delivered, or 10 days for nonpayment of premium or within 90 "
          "days of a new policy's effective date, stating the specific reason or reasons.",
          "RSA 417-B:4", INS_LAW_READ)]
PROPERTY_CANCEL_FIGS = [
    fig("90 days", "RSA 417-B:3", "has been in effect for 90 days"),
    fig("45 days", "RSA 417-B:4", "shall not be less than 45 days after"),
    fig("10 days", "RSA 417-B:4", "may be 10 days from the date of mailing"),
    fig("120 days", "RSA 417:19", "within 120 days from the date of the receipt of a complaint")]

CAR_INSURANCE = guide(
    "car-insurance", "How Car Insurance Works in New Hampshire",
    "Whether New Hampshire requires car insurance, when a driver must prove they can pay for a "
    "crash, the least a car insurance policy here must cover, uninsured motorist coverage, and "
    "what to do if your insurer cancels your policy.",
    "New Hampshire law does not require you to carry car insurance, but you must be able to "
    "pay enough to meet its <b>financial responsibility</b> requirements if you cause an "
    "accident, or your driving privileges may be suspended. After a crash you were in without "
    "insurance, or after certain convictions, the state can suspend "
    "your license and registration until you file <b>proof of financial responsibility</b>, "
    "usually an insurance company&rsquo;s certificate. A motor vehicle liability policy here "
    "must cover at least $25,000 for injury to one person, $50,000 for one accident, and "
    "$25,000 for damage to property, and must include <b>uninsured motorist</b> coverage, and "
    "on a private passenger car medical payments coverage.",
    [ask("Do you have car insurance?",
         [("Yes", "Your policy carries at least the state&rsquo;s minimums and uninsured motorist "
                  "coverage."),
          ("No", "The law does not require it, but a crash you must report, or certain "
                 "convictions, can cost you your license and registration until you file proof "
                 "of financial responsibility.")]),
     ask("Were you just in a crash?",
         [("Someone was hurt, or the damage is over $1,000",
           "Report it to the DMV in writing within 15 days, unless the police investigated."),
          ("No one was hurt and the damage is less", "Exchange information at the scene.")])],
    [step("What the law requires",
          "<p>New Hampshire law does not require you to carry car insurance. You must, though, "
          "be able to show you can pay enough to meet the state&rsquo;s financial responsibility "
          "requirements if you cause an accident, and if you cannot, your driving privileges may "
          "be suspended, as the Insurance Department&rsquo;s Auto Insurance Consumer Guide "
          "explains.</p>"
          "<p>The <b>financial responsibility law</b> decides when the state requires proof that "
          "you can pay for damage you cause: after a crash you had to report and had no "
          "insurance for, or after certain convictions (the next two steps).</p>"
          "<p>That proof means being able to pay $25,000 for injury to or death of one person, "
          "$50,000 for injury to or death of two or more people in one accident, and $25,000 "
          "for damage to property, for each vehicle registered in your name.</p>"
          "<p>The Insurance Department&rsquo;s Automobile Insurance page divides auto insurance "
          "into two basic coverage areas, liability and property damage. With a question about "
          "your coverage, call its Consumer Services unit at (603) 271-2261, toll free in New "
          "Hampshire at 1-800-852-3416, or email consumerservices@ins.nh.gov.</p>",
          actions=[("Auto Insurance Consumer Guide (Insurance Department)", INS_AUTO_GUIDE),
                   ("Automobile insurance (Insurance Department)", INS_AUTO)],
          law=["RSA 264:20"]),
     step("After a crash",
          "<p>Stop at the scene. Give the other driver, anyone hurt, and the owner of any "
          "property damaged your name and address, your driver&rsquo;s license number, your "
          "insurance company and policy information, the registration number of the vehicle, "
          "and the name and address of each person in it.</p>"
          "<p>If anyone was hurt or killed, or the damage to property is over $1,000, report the "
          "crash to the DMV in writing within 15 days, unless a police officer investigated "
          "it.</p>"
          "<p>If the crash had to be reported and you had no insurance policy or bond covering "
          "it, the state suspends your license and registration, and you must turn in your plates, until you put up enough "
          "security to pay any judgment for the damage and file proof of financial "
          "responsibility. You receive notice at least 10 days before the suspension starts. It "
          "lasts until you are released from the claim, win in court, or pay a judgment against "
          "you. If no one tells the DMV within 2 years that they have sued you, it may give you "
          "back your license and registration once you file proof.</p>",
          law=["RSA 264:25", "RSA 264:3", "RSA 264:7"]),
     step("After certain convictions",
          "<p>The state may also suspend your license and registration until you file proof of "
          "financial responsibility, and keep it on file, after a conviction for:</p>"
          "<ul><li>driving under the influence of alcohol or drugs;</li>"
          "<li>failing to stop and report after a crash;</li>"
          "<li>homicide or assault arising from driving;</li>"
          "<li>a second conviction for speeding at an excessive rate, or for reckless "
          "driving.</li></ul>"
          "<p>You receive notice at least 10 days before the suspension starts. The DMV may stop "
          "requiring the proof after 3 years, if you have no new conviction, crash or unpaid "
          "judgment.</p>",
          law=["RSA 264:2", "RSA 264:7"]),
     step("Filing proof of financial responsibility",
          "<p>Proof is usually a <b>certificate</b> that an insurance company or a surety company "
          "files with the DMV for you, showing that you carry the amounts the law sets. It can "
          "also be a deposit of money or securities with the state. Ask your insurance company to "
          "file the certificate.</p>",
          law=["RSA 264:21", "RSA 264:20"]),
     step("What a car insurance policy must include",
          "<p>A <b>motor vehicle liability policy</b>, the kind of car insurance whose terms New "
          "Hampshire law sets, must cover your liability to others for at least $25,000 for injury to or death of one person, $50,000 for one accident "
          "injuring or killing more than one, and $25,000 for damage to others&rsquo; property. "
          "You may buy more.</p>"
          "<p>It must also include:</p>"
          "<ul><li><b>Uninsured motorist coverage</b>, which protects you when a driver with no "
          "insurance, or a hit-and-run driver, injures you. It is at least as much as the policy&rsquo;s "
          "coverage for injury, and if you buy more than the minimum liability coverage, it rises "
          "to match.</li>"
          "<li>On a private passenger car, <b>medical payments coverage</b> of at least $1,000 "
          "per person, for reasonable "
          "medical costs of the driver and passengers hurt in a crash in your car, for costs "
          "within 3 years of the crash.</li></ul>",
          actions=[("Automobile insurance (Insurance Department)", INS_AUTO)],
          law=["RSA 259:61", "RSA 264:15", "RSA 264:16"]),
     step("If your insurer cancels or will not renew your policy",
          "<p>Once a policy has been in effect for 60 days, or once it has been renewed, an "
          "insurer may cancel it only if you do not pay the premium, if you ask it to, or if you "
          "were not a New Hampshire resident when the policy was issued or renewed, unless the car "
          "was garaged only in New Hampshire then. It may not "
          "cancel or refuse to renew your policy solely because of your age, where you live, "
          "your race, color, creed, national origin, ancestry, marital status or lawful "
          "occupation, or because another insurer turned you down.</p>"
          "<p>The insurer must send you written notice that states its specific reasons. The "
          "cancellation takes effect at least 45 days after the notice, or 10 days for not paying "
          "or in the first 60 days of a new policy. The notice tells you how to reach the "
          "Insurance Department, and you may ask the Insurance Commissioner to review the "
          "decision by writing within 10 days of receiving it.</p>",
          actions=[("File a complaint (Insurance Department)", INS_COMPLAINT)],
          law=["RSA 417-A:4", "RSA 417-A:3", "RSA 417-A:5", "RSA 417-A:7"])],
    [("Auto Insurance Consumer Guide (NH Insurance Department)", INS_AUTO_GUIDE),
     ("Automobile Insurance (NH Insurance Department)", INS_AUTO),
     ("Filing a Complaint (NH Insurance Department)", INS_COMPLAINT),
     ("Financial responsibility, RSA 264", "/laws/264"),
     ("The motor vehicle liability policy, RSA 259:61", "/laws/259#s61"),
     ("Driver licenses, RSA 263", "/laws/263"),
     ("Cancelling car insurance, RSA 417-A", "/laws/417-a")],
    ["259", "263", "264", "417-A"],
    [claim("New Hampshire motor vehicle laws do not require you to carry auto insurance, but you "
           "must be able to demonstrate that you are able to provide sufficient funds to meet New "
           "Hampshire motor vehicle financial responsibility requirements in the event of an "
           "\u201cat-fault\u201d accident. If you are unable to meet these requirements your "
           "driving privileges in New Hampshire may be suspended.", INS_AUTO_GUIDE, INS_DEPT_READ),
     claim("Proof of financial responsibility shall mean proof of ability to respond in damages "
           "in the amount of $25,000 because of bodily injury or death to any one person; $50,000 "
           "because of bodily injury to or death to 2 or more persons in any one accident, and "
           "$25,000 because of injury to and destruction of property; furnished for each motor "
           "vehicle registered by such person.", "RSA 264:20", INS_LAW_READ),
     claim("The driver shall immediately stop and give the driver's name and address, driver's "
           "license number, insurance provider and policy information, registration number and "
           "the name and address of each occupant; within 15 days report in writing if any "
           "person is injured or killed, or if damage to property is in excess of $1,000, unless "
           "the accident is investigated by a police officer.", "RSA 264:25", INS_LAW_READ),
     claim("After the report of an accident the director shall suspend the license and "
           "registration and require the surrender of the plates until the driver or owner has "
           "furnished security for any judgment and gives and maintains proof of financial "
           "responsibility, with notice not less than 10 days prior; not applicable if a motor "
           "vehicle liability policy or bond was in effect, or other insurance or bond covered "
           "the liability.", "RSA 264:3", INS_LAW_READ),
     claim("The suspension remains until a release, a judgment in the person's favor, or a "
           "satisfied judgment, with proof of financial responsibility; if no written notice that "
           "suit has been brought is received within 2 years, a new license and registration may "
           "be issued with proof; the requirement may be waived after 3 years' duration from the "
           "accident or conviction, with no further record.", "RSA 264:7", INS_LAW_READ),
     claim("Upon conviction for driving under the influence; failing to stop and report when "
           "involved in an accident; homicide or assault arising out of driving; the second time "
           "for an excessive rate of speed; the second time for reckless driving, the director "
           "may suspend license and registration until proof of financial responsibility is "
           "given and maintained; notice not less than 10 days prior.", "RSA 264:2",
           INS_LAW_READ),
     claim("Proof is given by filing a certificate of an insurance company or surety company, "
           "or by a deposit of money or securities.", "RSA 264:21", INS_LAW_READ),
     claim("A motor vehicle liability policy: at least $25,000 on account of injury to or death "
           "of any one person, at least $50,000 on account of any one accident resulting in "
           "injury to or death of more than one person, and at least $25,000 for damage to "
           "property of others.", "RSA 259:61", INS_LAW_READ),
     claim("No policy under RSA 264:14 for a vehicle registered or principally garaged in the "
           "state is issued without uninsured motorist coverage.", "RSA 264:15", "2026-10-26"),
     claim("Every policy includes uninsured and hit-and-run motor vehicle coverage at least in "
           "the amounts prescribed for bodily injury; when the insured buys liability coverage "
           "greater than the minimum, uninsured motorist coverage is automatically equal to it; "
           "umbrella or excess policies provide it unless the named insured rejects it in "
           "writing.", "RSA 264:15", INS_LAW_READ),
     claim("Any motor vehicle liability policy covering a private passenger automobile includes "
           "medical payments coverage of $1,000 per person or more for reasonable medical costs "
           "of the driver and passengers, for costs incurred during 3 years following the "
           "injuries; not any commercial policy insuring more than 4 automobiles; the insured "
           "may claim under medical payments or health insurance or both, "
           "without duplicate payment.", "RSA 264:16", INS_LAW_READ),
     # RSA 263:17's third route, "emancipated by marriage", is not printed: RSA 457:4
     # makes any marriage of a person under 18 void (the person, 26 October 2026,
     # pointed out that New Hampshire bans child marriage).
     claim("No person under the age of 18 years shall be issued a driver's license unless a "
           "parent or guardian, or where there is none another responsible adult, gives written "
           "permission, insurance coverage is presented, or the person is emancipated by "
           "marriage.", "RSA 263:17", INS_LAW_READ),
     claim("After a policy has been in effect for 60 days, or if it is a renewal, an insurer may "
           "cancel only for nonpayment of premium, the specific request of the insured, or the "
           "named insured not being a resident of New Hampshire when it was issued or renewed, "
           "unless the insured vehicle was exclusively garaged in New Hampshire then.",
           "RSA 417-A:4", INS_LAW_READ),
     claim("No insurer shall cancel, refuse to write or refuse to renew solely because of age, "
           "residence, race, color, creed, national origin, ancestry, marital status or lawful "
           "occupation, or solely because another insurer has refused, cancelled or not "
           "renewed.", "RSA 417-A:3", INS_LAW_READ),
     claim("A written notice stating the specific reasons, effective not less than 45 days after "
           "it is mailed or delivered, or 10 days for nonpayment or within 60 days of a new "
           "policy; advising the right to request the commissioner's review by written request "
           "within 10 days; with the insurance department's phone number and mailing address.",
           "RSA 417-A:5", INS_LAW_READ),
     claim("Any insured may within 10 days of the receipt of a notice of cancellation or "
           "nonrenewal request in writing that the commissioner review the action.",
           "RSA 417-A:7", INS_LAW_READ),
     # The Insurance Department's own pages, in the person's printouts of 26 October 2026.
     claim("Auto insurance can be divided into two basic coverage areas: liability and property "
           "damage. Have a question about your coverage? Call the Consumer Services unit at "
           "603-271-2261, in state toll free (800) 852-3416 or email "
           "consumerservices@ins.nh.gov.", INS_AUTO, INS_DEPT_READ),
     claim("Consumer Complaint Forms: Online Consumer Complaint Form (Electronic version); "
          "Consumer Complaint Form (Printable), intended to be printed for completion and mailed "
          "or faxed to the New Hampshire Insurance Department; Auto Body Shop Complaint Form; "
          "Health Provider Complaint Form; Release of Information Form. If you are submitting a "
          "grievance or request for someone other than yourself (such as a spouse, adult child, "
          "friend, patient, customer, etc.), please also complete and submit the Release of "
          "Information Form. If the CSO assigned to your case determines the Department has the "
          "jurisdictional authority to intervene on your behalf, he/she will forward your "
          "submission to the appropriate licensee for a response. The Insurance Department is "
          "not always able to negotiate the remedy you desire. If the issue does not fall within "
          "the jurisdiction of the Insurance Department, your CSO will refer your complaint to "
          "that agency and will inform you of the referral by letter. Contact the department's "
          "Consumer Services Unit at 800-852-3416 or via email at consumerservices@ins.nh.gov. "
          "21 South Fruit Street, Suite 14, Concord, NH 03301; Phone: (603) 271-2261.", INS_COMPLAINT, INS_DEPT_READ)],
    more=civics.faq(
        ("Does a driver under 18 need insurance?",
         "<p>A person under 18 gets a license only with written permission from a parent or "
         "guardian (or, where there is none, another responsible adult), or with insurance "
         'coverage shown when applying (<a href="/laws/263#s17">RSA 263:17</a>).</p>'),
        ("Does my car insurance or my health insurance pay my medical bills after a crash?",
         "<p>You choose: you may claim under your car policy&rsquo;s medical payments coverage, "
         "your health insurance, or both, but you may not be paid twice for the same bill.</p>"),
        ("Does an umbrella policy include uninsured motorist coverage?",
         "<p>Yes, an umbrella or excess policy over a car policy includes uninsured motorist "
         "coverage equal to its limits, unless you turn it down in writing.</p>"),
        ("How long must I keep proof on file?",
         "<p>Until the DMV stops requiring it. It may do so after 3 years, if you have had no "
         "new conviction, crash or unpaid judgment.</p>")),
    see=[("How to register a car", "/guides/register-a-car.html"),
         ("How to renew your driver’s license", "/guides/renew-drivers-license.html")],
    figures=[fig("$25,000", "RSA 259:61", "at least $25,000 on account of injury"),
             fig("$50,000", "RSA 259:61", "at least $50,000 on account of any one accident"),
             fig("$1,000", "RSA 264:25", "damage to property is in excess of $1,000"),
             fig("$1,000", "RSA 264:16", "greater than $1,000 per person"),
             fig("15 days", "RSA 264:25", "within 15 days after such accident"),
             fig("10 days", "RSA 264:3", "not less than 10 days prior"),
             fig("2 years", "RSA 264:7", "within 2 years from the date of the accident"),
             fig("3 years", "RSA 264:7", "after 3 years' duration"),
             fig("3 years", "RSA 264:16", "during 3 years following"),
             fig("60 days", "RSA 417-A:4", "has been in effect for 60 days"),
             fig("45 days", "RSA 417-A:5", "shall not be less than 45 days after")])

GUIDES += [CAR_INSURANCE]

RENTERS_INSURANCE = guide(
    "renters-insurance", "Renters Insurance in New Hampshire",
    "What a renters insurance policy covers, the rules on cancelling one, and how to file a "
    "claim and complain to the Insurance Department.",
    "If you rent, your landlord&rsquo;s insurance does not cover the things you own; a renters "
    "policy does, the Insurance Department explains, and some policies also cover your living "
    "expenses if an insured loss keeps you out of your home. Once a policy has been in effect "
    "for 90 days, the insurer may "
    "cancel it only for the reasons the law lists, with written notice. If an insurer handles "
    "your claim unfairly, you can complain to the <b>Insurance Department</b>.",
    [ask("Do you rent your home?",
         [("Yes", "A renters policy can cover your belongings, which your landlord&rsquo;s "
                  "insurance does not."),
          ("No, you own it", "See homeowners insurance.")]),
     box("If you have a loss, tell your insurer and keep a record of what you send."),
     box("If you disagree with how it is handled, complain to the Insurance Department.")],
    [step("What renters insurance covers",
          "<p>New Hampshire&rsquo;s law on home insurance covers policies on a household&rsquo;s "
          "<b>real property</b> (a building), its <b>personal property</b> (belongings) and its "
          "<b>legal liability</b> for injury to other people or damage to their property.</p>"
          "<p>The Insurance Department&rsquo;s Homeowners and Renters Insurance page explains "
          "that if you rent an apartment, house or condominium, your landlord&rsquo;s insurance "
          "does not cover the things you own. A renters policy covers your belongings; some "
          "policies also cover your living expenses if you cannot live in your home because of "
          "an insured loss, and renters insurance may also protect you from lawsuits alleging "
          "negligence.</p>",
          actions=[("Homeowners and renters insurance (Insurance Department)", INS_HOME)],
          law=["RSA 417-B:1"]),
     step("If your insurer cancels or will not renew your policy",
          "<p>An insurer may not cancel or refuse to write or renew your policy solely because "
          "of your age, where you live, your race, color, creed, national origin, ancestry, "
          "marital status or lawful occupation, because another insurer turned you down, or on "
          "your credit information alone.</p>"
          "<p>Once a policy has been in effect for 90 days, or once it has been renewed, the "
          "insurer may cancel it only if you do not pay the premium, are convicted of a crime "
          "that increases a hazard insured against, commit fraud or material misrepresentation in "
          "a claim, act with gross negligence that substantially increases a hazard, make "
          "physical changes that leave the property uninsurable, or ask it to.</p>"
          "<p>It must send written notice that states its specific reasons, at least 45 days "
          "before the cancellation or nonrenewal takes effect, or 10 days for not paying or in "
          "the first 90 days of a new policy.</p>",
          law=["RSA 417-B:2", "RSA 417-B:2-a", "RSA 417-B:3", "RSA 417-B:4"]),
     PROPERTY_CLAIM_STEP,
     PROPERTY_COMPLAINT_STEP],
    [("Homeowners and Renters Insurance (NH Insurance Department)", INS_HOME),
     ("Filing a Complaint (NH Insurance Department)", INS_COMPLAINT),
     ("Home and renters insurance, RSA 417-B", "/laws/417-b"),
     ("Unfair insurance practices, RSA 417", "/laws/417")],
    ["417", "417-B"],
    [*PROPERTY_CANCEL_CLAIMS, *PROPERTY_CLAIM_CLAIMS,
     claim("Renters insurance is another important insurance product to consider. If you live "
           "in a rented apartment, house, or condominium, your landlord's insurance doesn't "
           "cover the things you own. In addition to covering your belongings, some policies "
           "will also cover your living expenses if you are unable to live in your apartment or "
           "home because of an insured loss. Renters insurance may also protect you from "
           "lawsuits alleging negligence.", INS_HOME, INS_DEPT_READ)],
    more=civics.faq(
        ("Can my insurer drop me because of my credit?",
         "<p>Not on your credit information alone: the insurer must weigh other factors "
         "too.</p>"),
        ("Is there a time limit for the Insurance Department to act on my complaint?",
         "<p>If it takes no action within 120 days, you may treat that as a finding against your "
         "complaint and appeal it.</p>")),
    see=[("Your rights as a tenant", "/guides/tenant-rights.html"),
         ("Homeowners insurance", "/guides/homeowners-insurance.html")],
    figures=PROPERTY_CANCEL_FIGS)

GUIDES += [RENTERS_INSURANCE]

HOMEOWNERS_INSURANCE = guide(
    "homeowners-insurance", "Homeowners Insurance in New Hampshire",
    "What a homeowners insurance policy covers, why a lender may require it and flood "
    "insurance, the rules on cancelling a policy, and how to file a claim and complain.",
    "A homeowners policy covers the structure of your home, your belongings and your "
    "<b>liability</b> for injuries to others or their property while they are on your "
    "property, the Insurance Department explains. Most mortgage lenders require it for as long "
    "as you have a mortgage, and most homeowners policies do not cover flood damage. Once a "
    "policy has "
    "been in effect for 90 days, the insurer may cancel it only for the reasons the law lists, "
    "and it may not refuse to renew it solely because you filed a single valid claim in one "
    "policy term. If an insurer handles "
    "your claim unfairly, you can complain to the <b>Insurance Department</b>.",
    [ask("Do you have a mortgage?",
         [("Yes", "Most lenders require homeowners insurance, and flood insurance in a "
                  "high-risk flood area."),
          ("No", "The Insurance Department&rsquo;s first reason to buy it is to protect your "
                 "assets.")]),
     box("If you have a loss, tell your insurer and keep a record of what you send."),
     box("If you disagree with how it is handled, complain to the Insurance Department.")],
    [step("What homeowners insurance covers",
          "<p>New Hampshire&rsquo;s law on home insurance covers policies on a household&rsquo;s "
          "<b>real property</b> (the house), its <b>personal property</b> (belongings) and its "
          "<b>legal liability</b> for injury to other people or damage to their property. The "
          "Insurance Department&rsquo;s Homeowners and Renters Insurance page explains that "
          "homeowners insurance covers the structure of your home and your personal property, "
          "and your legal responsibility for injuries to others or their property while they "
          "are on your property.</p>",
          actions=[("Homeowners and renters insurance (Insurance Department)", INS_HOME)],
          law=["RSA 417-B:1"]),
     step("What a lender may require, and flood insurance",
          "<p>Most mortgage lenders require you to have insurance for as long as you have a "
          "mortgage, and to list them as the mortgagee on the policy, the Insurance Department "
          "explains. If you let your insurance lapse, your lender will likely insure the home "
          "itself: the premium might be much higher than a policy you would buy, the coverage "
          "is limited to damage to the structure, and the lender can require you to pay it until "
          "you get your own homeowners insurance again.</p>"
          "<p>Most homeowners insurance does not cover flood damage, says FEMA&rsquo;s National "
          "Flood Insurance Program. You must have flood insurance if you own a home in a "
          "<b>Special Flood Hazard Area</b> and have a government-backed mortgage, and some "
          "lenders require it outside those areas. If the property has received federal "
          "disaster assistance before, it needs flood insurance to qualify again.</p>",
          actions=[("Who needs flood insurance (FloodSmart, FEMA)", FLOOD_ELIGIBLE)]),
     step("If your insurer cancels or will not renew your policy",
          "<p>An insurer may not cancel or refuse to write or renew your policy solely because "
          "of your age, where you live, your race, color, creed, national origin, ancestry, "
          "marital status or lawful occupation, because another insurer turned you down, or on "
          "your credit information alone. It may not refuse to renew a homeowners policy solely "
          "because you filed a single valid claim in one policy term, and asking about your "
          "coverage is not a claim.</p>"
          "<p>Once a policy has been in effect for 90 days, or once it has been renewed, the "
          "insurer may cancel it only if you do not pay the premium, are convicted of a crime "
          "that increases a hazard insured against, commit fraud or material misrepresentation "
          "in a claim, act with gross negligence that substantially increases a hazard, make "
          "physical changes that leave the property uninsurable, or ask it to.</p>"
          "<p>It must send written notice that states its specific reasons, at least 45 days "
          "before the cancellation or nonrenewal takes effect, or 10 days for not paying or in "
          "the first 90 days of a new policy.</p>",
          law=["RSA 417-B:2", "RSA 417-B:2-a", "RSA 417-B:3-a", "RSA 417-B:3", "RSA 417-B:4"]),
     PROPERTY_CLAIM_STEP,
     PROPERTY_COMPLAINT_STEP],
    [("Homeowners and Renters Insurance (NH Insurance Department)", INS_HOME),
     ("Filing a Complaint (NH Insurance Department)", INS_COMPLAINT),
     ("Who’s Eligible for NFIP Flood Insurance? (FloodSmart, FEMA)", FLOOD_ELIGIBLE),
     ("Home and renters insurance, RSA 417-B", "/laws/417-b"),
     ("Unfair insurance practices, RSA 417", "/laws/417")],
    ["417", "417-B"],
    [*PROPERTY_CANCEL_CLAIMS, *PROPERTY_CLAIM_CLAIMS,
     claim("The nonrenewal of a homeowner's insurance policy is prohibited if based solely on the "
           "insured having filed a single valid claim within any one previous or current policy "
           "term; inquiries about coverage do not constitute a valid claim.", "RSA 417-B:3-a",
           INS_LAW_READ),
     claim("There are two major reasons to buy homeowners insurance: Protect your assets: "
           "Homeowners insurance covers the structure of your home and your personal property, "
           "as well as your personal legal responsibility (or liability) for injuries to others "
           "or their property while they're on your property. Satisfy your mortgage lender: "
           "Most mortgage lenders require you to have insurance as long as you have a mortgage "
           "and to list them as the mortgagee on the policy. If you let your insurance lapse, "
           "your mortgage lender will likely have your home insured. Compared to a policy you "
           "would buy on your own, the premium might be much higher and the coverage will be "
           "limited to damage to the structure of your home. The lender can require you to pay "
           "this higher premium until you get your own homeowners insurance again.", INS_HOME,
           INS_DEPT_READ),
     claim("You're required to have flood insurance if you own a home or business in a Special "
           "Flood Hazard Area (SFHA) and have a government-backed mortgage; some banks require "
           "flood insurance even if you don't live in a high-risk area; if your property has "
           "received federal disaster assistance before, you must have flood insurance to "
           "qualify for future disaster assistance; this requirement is tied to a property, not "
           "an individual homeowner; most homeowners insurance does not cover flood damage.",
           FLOOD_ELIGIBLE, FLOOD_READ)],
    more=civics.faq(
        ("Can my insurer refuse to renew my policy because I filed a claim?",
         "<p>Not solely because of a single valid claim in one policy term, and asking about "
         "your coverage is not a claim.</p>"),
        ("Does a flood insurance requirement follow the house?",
         "<p>Yes: if the home received federal disaster assistance before, it needs flood "
         "insurance to qualify for more, even after it is sold.</p>"),
        ("Is there a time limit for the Insurance Department to act on my complaint?",
         "<p>If it takes no action within 120 days, you may treat that as a finding against your "
         "complaint and appeal it.</p>")),
    see=[("Renters insurance", "/guides/renters-insurance.html"),
         ("How to get ready for storms and power outages", "/guides/storms-and-emergencies.html"),
         ("How to read your property tax bill", "/guides/property-tax-bill.html")],
    figures=PROPERTY_CANCEL_FIGS)

GUIDES += [HOMEOWNERS_INSURANCE]


# ---------------------------------------------------------------------------
# THE GUIDES BY TASK (the person, 17 October 2026: "refine how the how to
# guides are displayed on the main resources page and the homepage so it's
# more intuitive for the general public"). A reader arrives with something to
# do -- renew a license, find out who represents them, speak on a bill -- and
# not with the name of a guide, so the How-To Guides tab lists them under the
# task they serve, each by a plain task title and one line, and the home
# page's Common Questions (HOME, below) offer the few most people come for
# the same way. A guide's
# own title ("How to Renew Your Driver's License") stays on its page and in
# search results; these are the words of the list.
#
# A slug here is a guide above or one of civics.HOW_TO, the three Learn pages
# that became guides the same day. preflight holds the two lists together:
# every guide and every one of those pages is under exactly one task, and
# every task names one of them. A guide published that is under no task --
# a guide added without a line here -- is still listed, under More Guides,
# rather than left off the tab.
# ---------------------------------------------------------------------------
def task(slug, does, line, head=None):
    """One entry of the How-To Guides tab: the guide's slug, the task in a
    reader's words ("Renew your driver's license"), one line on it, and the
    short headline the tab lists it by ("How to renew your driver's
    license"), which is "How to" and the task unless it is given."""
    head = head or "How to " + does[:1].lower() + does[1:]
    return {"slug": slug, "does": does, "line": line, "head": head}


# THE HOW-TO TAB, COMPACT AND SEARCHABLE (the person, 24 October 2026: "a most
# common questions for the essential guides, a searchbar that matches likely
# search terms to a dropdown of suggested guides ... Then below the search and
# top guides would be various dropdown topics like voting and elections as
# they are categorized today, but made more compact with a simpler headline
# like "How to Vote" "How to submit legislative testimony" ... I want to
# expand the number of useful guides while avoiding making the menus a
# nightmare to navigate"). Each task's head is that headline; the groups fold
# shut; the search reads every guide's title, task, line, head and WORDS.
# This replaces the rule of 17 October that the tab never say "How to".
#
# MOST COMMON, the tab's first list: chosen by judgment, as HOME's are -- the
# site keeps no count of what is read -- the errands a member of the public
# most often has with the state and the legislature. The person's to change.
# New to New Hampshire took food and health assistance's place the same day,
# at the person's word.
COMMON = ["how-to-vote", "renew-drivers-license", "register-a-car", "your-representatives",
          "submit-testimony", "new-to-new-hampshire"]


# A GUIDE'S STEPS IN PARTS (the person's notes, 29 October 2026, through the
# manager session: a guide would "finish explaining how to do the first thing
# and switch to a different topic, but keep the step by step format as though
# step 5 is a continuation"). Where a guide's steps change subject, each part
# has a heading and is numbered from 1 (guides.step's `part`). Named by the
# title of the step each part opens; a title that is not there stops the
# build, so a renamed step cannot silently lose its heading. election-worker
# waits until after the 3 November election, at the person's word.
PARTS = {
    "passport": {"Check whether you can renew instead": "Renewing an adult passport",
                 "Fill out Form DS-11, and do not sign it yet": "Applying in person",
                 "If you travel soon": "Either way"},
    "vanity-and-special-plates": {"Choose your plate": "A vanity plate",
                                  "Show that you qualify": "A special plate"},
    "medicare-and-social-security": {"Know how the programs fit together": "Start here",
                                     "Know when to sign up for Medicare": "Medicare",
                                     "Apply for Social Security retirement benefits": "Social Security"},
    "motorcycle-license": {"Get a learner's permit": "A motorcycle",
                           "If you ride a moped": "A moped"},
    "run-for-office": {"Check that you qualify": "An office on the state ballot",
                       "Town and city offices": "A town or city office"},
    "wage-rights": {"Know when you must be paid": "Your rights to your pay",
                    "File a wage claim": "If your employer breaks the law"},
    "consumer-rights": {"Know what the law forbids": "What the law protects",
                        "Complain to the Attorney General": "If a business breaks the law"},
    "discrimination": {"Know what the law protects": "What the law protects",
                       "File a complaint with the Commission for Human Rights": "Making a complaint"},
    "health-insurance": {"Know when you can sign up": "Getting coverage",
                         "Appeal a denied claim to your insurance company": "If a claim is denied, or you have a complaint",
                         "Where Medicaid and Medicare fit": "Medicaid and Medicare"},
    "car-insurance": {"What the law requires": "Financial responsibility",
                      "What a car insurance policy must include": "Your policy"},
    "renters-insurance": {"What renters insurance covers": "Your policy",
                          "If you have a loss: filing a claim": "After a loss, or a dispute"},
    "homeowners-insurance": {"What homeowners insurance covers": "Your policy",
                             "If you have a loss: filing a claim": "After a loss, or a dispute"},
    "boating": {"Get your safe boater education certificate": "Boater education",
                "Register your boat every year": "Your boat"},
    "building-permits": {"Start with your town’s building office": "Building work",
                         "Electrical work": "Electrical, plumbing and gas work",
                         "Septic systems": "Septic systems and work near water"},
    "homelessness-help": {"Call 2-1-1, or your town’s welfare office": "Finding shelter now",
                          "If you may be evicted": "Keeping or finding a home",
                          "Keep your children in school": "Children and school"},
    "domestic-violence-help": {"Reach someone now": "Staying safe",
                               "After a sexual assault: medical care": "After a sexual assault",
                               "Other protections and help": "More help"},
    "who-to-contact": {"Find who represents you": "Start here",
                       "Your town or city: roads, sidewalks, trash and local rules": "Who handles what"},
    "tenant-rights": {"Only a court can make you leave": "Your rights as a tenant",
                      "If you get an eviction notice or court papers": "If you are facing eviction"},
    "landlord-duties": {"Before you rent": "Renting",
                        "Reasons and notice": "Ending a tenancy"},
    "property-tax-bill": {"How your property is assessed": "Understanding your bill",
                          "Apply for an exemption or credit by April 15, or a deferral by March 1":
                              "Relief and appeals"},
    "disability-help": {"Apply to Social Security for SSDI or SSI": "Where to apply",
                        "If you are turned down": "Appealing a decision"},
}


def _parts():
    import html as _h
    by = {g["slug"]: g for g in GUIDES}
    for slug, heads in PARTS.items():
        # A step two guides share is copied, so one guide's heading is never the other's.
        by[slug]["steps"] = [dict(s_) for s_ in by[slug]["steps"]]
        titles = {_h.unescape(s_["title"]): s_ for s_ in by[slug]["steps"]}
        for title, head in heads.items():
            assert title in titles, f"PARTS: {slug} has no step {title!r}"
            titles[title]["part"] = head
        assert by[slug]["steps"][0].get("part"), f"PARTS: {slug}'s first step has no heading"


_parts()


TASKS = [
    ("Take Part in the Legislature", [
        task("your-representatives", "Find your representatives",
             "Who represents your town in the House and the Senate, and what the district "
             "numbers mean."),
        task("who-to-contact", "Find out who to contact about an issue",
             "Your town for roads and sidewalks, the school board, a state agency, your "
             "legislators, or your members of Congress.",
             head="How to know who to contact"),
        task("contact-your-legislators", "Contact your legislators",
             "Email or call the people who represent you, and write a message they can act on."),
        task("attend-a-hearing", "Attend or speak at a public hearing",
             "Find a bill&rsquo;s hearing, go in person or watch it, and ask to speak.",
             head="How to attend or speak at a hearing"),
        task("submit-testimony", "Send testimony online or in writing",
             "Tell a committee where you stand on a bill without going to Concord.",
             head="How to submit testimony on a bill"),
        task("testifying", "Learn how hearings work before you go",
             "The notices, signing in, speaking, written testimony and what follows a hearing, "
             "in one place.",
             head="How public hearings work"),
        task("read-a-bill", "Read a bill",
             "What the parts of a bill are, and how its text shows what it changes."),
        task("using-this-site", "Use this site to follow a bill",
             "What each tab holds, how to follow a bill, and how to tell us when something is "
             "wrong.",
             head="How to follow a bill on this site"),
    ]),
    ("Voting and Elections", [
        task("how-to-vote", "Vote",
             "Check that you are registered, register if you are not, and find what to bring "
             "and where to go."),
        task("run-for-office", "Run for office",
             "Who files where and when, and what it takes, from governor to town offices."),
        task("town-warrant-article", "Put an article on your town meeting warrant",
             "Petition your selectmen or school board to put a question to the voters."),
        task("election-worker", "Work at the polls on election day",
             "Who runs a polling place, how to be appointed, and how the count is checked."),
    ]),
    ("Driving and Vehicles", [
        task("renew-drivers-license", "Renew your driver&rsquo;s license",
             "Online or at a DMV appointment, and what to do if it has expired."),
        task("register-a-car", "Register a car",
             "At your town or city clerk and then for the state, and renewing it."),
        task("real-id", "Get a REAL ID",
             "Whether you need one, and the documents to bring."),
        task("new-to-new-hampshire", "Move to New Hampshire",
             "Your license, your vehicle&rsquo;s registration and registering to vote."),
        task("motorcycle-license", "Get a motorcycle license or ride a moped",
             "The learner&rsquo;s permit, rider training and the road test, the riding rules, "
             "and what a moped needs.", head="How to get a motorcycle license"),
        task("vanity-and-special-plates", "Get a vanity or special plate",
             "Letters you choose, or a veteran, Gold Star, National Guard or conservation "
             "plate: who qualifies and what each costs."),
    ]),
    ("Help and Benefits", [
        task("food-and-health-assistance", "Apply for food or health assistance",
             "SNAP and Medicaid, online at NH Easy or on paper."),
        task("heating-and-electric-help", "Get help with heating and electric bills",
             "Fuel assistance, help with electric bills, weatherization, and what to do with no "
             "heat."),
        task("file-for-unemployment", "File for unemployment",
             "Your claim, the weekly claims that follow, and how to appeal."),
        task("child-care-scholarship", "Get help paying for child care",
             "The Child Care Scholarship: who it is for, how to apply, and choosing a provider."),
        task("homelessness-help", "Get help if you are homeless or may lose your home",
             "Shelter, your town&rsquo;s welfare office, your rights in an eviction, and a "
             "housing voucher."),
        task("domestic-violence-help", "Get help after domestic violence, sexual assault or stalking",
             "The 24-hour helpline, a safety plan, a protective order, and care after an assault."),
        task("storms-and-emergencies", "Prepare for storms, power outages and emergencies",
             "Emergency alerts, supplies, power outage and winter storm safety, and where to "
             "find a warm place."),
    ]),
    ("Federal Benefits", [
        task("medicare-and-social-security", "Sign up for Medicare and Social Security",
             "When to sign up, choosing coverage, and help paying Medicare&rsquo;s costs."),
        task("disability-help", "Get disability benefits and services",
             "SSDI and SSI, the state&rsquo;s cash and medical assistance, area agencies and "
             "vocational rehabilitation."),
    ]),
    ("Know Your Rights", [
        task("tenant-rights", "Know your rights as a tenant",
             "Security deposits, repairs and heat, rent increases, and what happens in an "
             "eviction.",
             head="Your rights as a tenant, from deposits to eviction"),
        task("wage-rights", "Get paid what you are owed at work",
             "When pay is due, your last paycheck, deductions, minimum wage, overtime, and "
             "filing a wage claim.",
             head="Your rights at work: getting paid"),
        task("discrimination", "Get help if you face discrimination",
             "At work, renting or buying a home, and in stores and other public places: what "
             "the law forbids, and how to file a complaint."),
        task("consumer-rights", "Report a scam or a business that cheated you",
             "Cancel a sale made at your door, your rights with gift certificates, and "
             "complaining to the Attorney General.",
             head="How to report a scam or file a consumer complaint"),
        task("public-records", "Get a public record",
             "Ask a town, school district, county or state agency for its records."),
    ]),
    ("Insurance", [
        task("car-insurance", "Understand car insurance in New Hampshire",
             "When the state requires proof of insurance, the least a policy must cover, and "
             "uninsured motorist coverage.",
             head="How car insurance works in New Hampshire"),
        task("renters-insurance", "Understand renters insurance",
             "What a renters policy covers, cancellation, and filing a claim or a complaint.",
             head="Renters insurance: what it covers and your rights"),
        task("homeowners-insurance", "Understand homeowners insurance",
             "What a homeowners policy covers, what a lender may require, flood insurance, and "
             "filing a claim or a complaint.",
             head="Homeowners insurance: what it covers and your rights"),
        task("health-insurance", "Get private health insurance",
             "The Marketplace and when to enroll, help paying premiums, coverage through a job "
             "or a parent&rsquo;s plan, and appealing a denied claim."),
    ]),
    ("Property and Records", [
        task("property-tax-abatement", "Appeal your property tax assessment",
             "Ask your town for an abatement, and appeal if it says no."),
        task("property-tax-relief", "Get property tax relief on a low or moderate income",
             "Who qualifies for the state&rsquo;s relief, and how to apply.",
             head="How to get property tax relief"),
        task("property-tax-bill", "Understand your property tax bill",
             "How your property is assessed, how the rate is set, what the bill shows, and the "
             "relief you can apply for.",
             head="How to read your property tax bill"),
        task("landlord-duties", "Rent out a home",
             "A landlord&rsquo;s duties: security deposits, entry, minimum standards, and "
             "evicting through the court."),
        task("vital-records", "Get a birth, death, marriage or divorce certificate",
             "From your town or city clerk or the state: who may ask and what to bring."),
        task("passport", "Get a U.S. passport",
             "A first passport or a renewal, what to bring to a post office, and a child&rsquo;s "
             "passport."),
    ]),
    ("Outdoors and Recreation", [
        task("fishing-license", "Get a fishing license",
             "Who needs one, the free fishing days, saltwater fishing, and buying one online."),
        task("hunting-license", "Get a hunting license",
             "Hunter education, the apprentice license, and licenses for turkey, pheasant and "
             "waterfowl."),
        task("boating", "Get a boater certificate and register a boat",
             "The safe boater education certificate, the temporary one, and registering a boat "
             "each year.", head="How to get a boater certificate and register a boat"),
    ]),
    ("Around Your Town", [
        task("report-a-road-problem", "Report a pothole or a sidewalk problem",
             "Who fixes which road, how to tell your town or the state, and what to do if a "
             "road problem damaged your car.",
             head="How to report a pothole or a road problem"),
        task("building-permits", "Find out when you need a building permit",
             "The building code, permits and inspections, who may do electrical and plumbing "
             "work, septic approval, and building near water.",
             head="How to know when you need a building permit"),
        task("trash-and-recycling", "Get rid of trash, recycling and hazardous waste",
             "Your transfer station, what never goes in the trash, hazardous waste days and "
             "composting."),
    ]),
    ("Visiting the State House", [
        task("tour-the-state-house", "Tour the State House",
             "Arrange a visit through the Visitor Center, bring a class, and know what to expect."),
    ]),
]
MORE = "More Guides"

# THE HOME PAGE'S COMMON QUESTIONS, under its cards. The person, 18 October
# 2026, of the "How do I...?" row of six buttons that stood here: "it feels
# like the phrasing is too vague to understand what's useful about it. Maybe
# we could have a sort of top 3-5 guides for the most common inquiries like
# how to vote, how to run for office, and new to New Hampshire." So five
# guides, each by a plain title and a line saying what a reader will learn
# or be able to do there, which a one-word button ("Vote") could not say.
#
# The three the person named, and the two errands a member of the public
# most often has with the state after them: who represents my town, and the
# license. Chosen by judgment, not counted -- the site keeps no count of
# which guides are read -- which is why the block is headed Common Questions
# and not Popular. A title here may differ from the task's on the How-To
# Guides tab ("How to vote" where the tab says "Vote"): the tab sets each
# task under a group heading that gives it its context, and the home page
# has no group heading to lean on. Each line is held to its guide's own
# steps; change the guide and read the line again. A pick whose guide is
# held back is left off the block.
HOME = [
    task("how-to-vote", "How to vote",
         "Register, find your polling place and what to bring, or vote absentee if you qualify."),
    task("run-for-office", "Run for office",
         "Who can run, when and where to file, and the fee or petitions, from governor to town "
         "offices."),
    task("new-to-new-hampshire", "New to New Hampshire",
         "Your New Hampshire license and vehicle registration within 60 days, and registering to "
         "vote."),
    task("your-representatives", "Find your representatives",
         "Who represents your town in the House and the Senate, and what the district numbers "
         "mean."),
    task("renew-drivers-license", "Renew your driver&rsquo;s license",
         "Online or at a DMV appointment: what to bring, what it costs, and what to do if it has "
         "expired."),
]


# THE WORDS A READER TYPES FOR EACH TASK (the person, 17 October 2026: "the
# how to guides should be incorporated into the search in some fashion").
# A guide is found in the header's search and on /search by its title and
# its task, and by these: the plain words and phrases a member of the public
# uses for the same thing ("register my car", "food stamps", "testify"),
# which its title may never say. find.js reads every word typed against the
# guide's title, its task and these as against a name, so a guide whose task
# words were typed is listed above the bills and the Learn pages, and never
# above a bill whose exact number was typed. A few each, and only words that
# mean the guide: a word that would find it for a reader who wanted
# something else costs that reader a wrong first answer.
WORDS = {
    "your-representatives": ("my representative", "my senator", "who represents me",
                             "who is my state rep", "state representative",
                             "district", "legislator"),
    "who-to-contact": ("who do i contact", "complaint", "pothole", "sidewalk", "city council",
                       "selectboard", "school board", "congressman", "senator", "federal agency",
                       "casework", "help with a state agency", "constituent services"),
    "report-a-road-problem": ("pothole", "streetlight", "street light", "traffic light",
                              "traffic signal", "stoplight", "sidewalk", "road repair",
                              "public works", "highway department", "car damage"),
    "contact-your-legislators": ("email my representative", "call my senator",
                                 "write my legislator", "contact"),
    "attend-a-hearing": ("testify", "public hearing", "speak on a bill", "attend"),
    "submit-testimony": ("testify", "written testimony", "sign in", "support or oppose a bill",
                         "testimony", "comment on a bill"),
    "testifying": ("testify", "hearing", "attend"),
    "read-a-bill": ("bill text", "amendment", "fiscal note"),
    "using-this-site": ("help", "follow a bill", "email updates", "report an error"),
    "how-to-vote": ("voting", "register to vote", "voter registration", "polling place",
                    "absentee ballot", "where do i vote", "election"),
    "run-for-office": ("candidate", "file for office", "declaration of candidacy"),
    "renew-drivers-license": ("license", "drivers license", "renew my license", "dmv",
                              "update my license", "expired license"),
    "register-a-car": ("register my car", "car registration", "vehicle registration", "plates",
                       "dmv"),
    "building-permits": ("building permit", "permit", "inspection", "building inspector",
                         "code enforcement", "addition", "renovation", "remodel", "electrical",
                         "electrician", "plumbing", "plumber", "septic", "shoreland",
                         "wetlands", "contractor"),
    "real-id": ("real id", "license", "id"),
    "vanity-and-special-plates": ("vanity plate", "license plate", "special plate",
                                  "gold star", "veteran plate", "national guard plate",
                                  "moose plate", "conservation plate", "purple heart"),
    "motorcycle-license": ("motorcycle", "motorcycle license", "motorcycle endorsement", "moped",
                           "scooter", "learner's permit", "helmet"),
    "new-to-new-hampshire": ("moving to new hampshire", "new resident", "license",
                             "register my car", "register to vote"),
    "food-and-health-assistance": ("snap", "food stamps", "medicaid", "health insurance",
                                   "benefits", "nh easy"),
    "file-for-unemployment": ("unemployment", "laid off", "lost my job", "benefits", "jobless"),
    "wage-rights": ("wages", "paycheck", "final paycheck", "last paycheck", "unpaid wages",
                    "not paid", "overtime", "minimum wage", "wage claim", "meal break",
                    "pay stub", "department of labor"),
    "child-care-scholarship": ("child care", "childcare", "daycare", "child care scholarship",
                               "child care assistance"),
    "domestic-violence-help": ("domestic violence", "sexual assault", "stalking", "abuse",
                               "restraining order", "protective order", "rape"),
    "discrimination": ("discrimination", "discriminated", "harassment", "sexual harassment",
                       "human rights", "fair housing", "racism", "retaliation"),
    "homelessness-help": ("homeless", "shelter", "eviction", "evicted", "housing voucher",
                          "section 8", "town welfare", "rent"),
    "tenant-rights": ("tenant", "renter", "renting", "landlord", "security deposit",
                      "eviction", "evicted", "lease", "rent increase", "repairs", "no heat",
                      "locked out", "bed bugs"),
    "landlord-duties": ("landlord", "rental property", "evict a tenant", "eviction notice",
                        "security deposit", "lease", "tenant", "demand for rent"),
    "storms-and-emergencies": ("storm", "power outage", "emergency", "nh alerts", "generator",
                               "snow storm", "warming center", "emergency kit"),
    "trash-and-recycling": ("trash", "recycling", "dump", "transfer station", "hazardous waste",
                            "compost", "electronics recycling", "paint disposal"),
    "health-insurance": ("health insurance", "marketplace", "healthcare.gov", "obamacare",
                         "open enrollment", "cobra", "denied claim", "external review",
                         "insurance department", "parent's plan"),
    "consumer-rights": ("scam", "fraud", "consumer complaint", "consumer protection",
                        "attorney general", "cancel a sale", "door to door", "gift card",
                        "gift certificate", "prize"),
    "heating-and-electric-help": ("fuel assistance", "heating", "electric bill", "weatherization"),
    "medicare-and-social-security": ("medicare", "social security", "retirement", "turning 65",
                                     "medicare savings program", "extra help", "part b",
                                     "open enrollment", "medicaid"),
    "disability-help": ("disability", "ssdi", "ssi", "disabled", "aptd", "mead",
                        "vocational rehabilitation", "area agency", "developmental disability"),
    "property-tax-abatement": ("property tax", "abatement", "assessment"),
    "property-tax-relief": ("property tax", "tax relief", "low income"),
    "property-tax-bill": ("property tax bill", "tax rate", "assessment", "assessed value",
                          "revaluation", "elderly exemption", "veterans credit", "tax deferral"),
    "public-records": ("right to know", "91-a", "records request", "foia"),
    "car-insurance": ("car insurance", "auto insurance", "insurance", "sr-22", "sr22",
                      "proof of insurance", "financial responsibility", "uninsured motorist",
                      "license suspended", "accident report", "crash"),
    "renters-insurance": ("renters insurance", "renter's insurance", "insurance", "tenant",
                          "apartment insurance", "insurance claim", "insurance complaint"),
    "homeowners-insurance": ("homeowners insurance", "home insurance", "insurance",
                             "flood insurance", "mortgage", "insurance claim",
                             "insurance complaint", "policy cancelled"),
    "vital-records": ("birth certificate", "death certificate", "marriage certificate",
                      "divorce certificate"),
    "fishing-license": ("fishing license", "fishing", "fish", "free fishing day",
                        "saltwater license", "fish and game"),
    "hunting-license": ("hunting license", "hunting", "hunter education", "hunter safety",
                        "deer", "turkey", "duck stamp", "archery", "fish and game"),
    "boating": ("boat registration", "boating license", "boat license", "boater certificate",
                "safe boater", "boating safety", "jet ski", "marine patrol"),
    "passport": ("passport", "renew my passport", "passport card", "travel abroad",
                 "ds-11", "ds-82", "international travel"),
    "town-warrant-article": ("warrant article", "petitioned article", "town meeting",
                             "school district meeting", "petition"),
    "election-worker": ("poll worker", "election worker", "ballot clerk", "inspector of election",
                        "moderator", "volunteer", "recount", "audit", "supervisors of the checklist"),
    "tour-the-state-house": ("tour", "visit the state house", "field trip", "school trip",
                             "visitor center"),
}


def search_words(slug):
    """What find.json carries for the guide beyond its title and line (its
    fifth field, build_indexes.find_index): the task in a reader's words and
    the words above, "Renew your driver's license · license · dmv", with
    any markup and entity read as the reader sees it. "" for a guide no task
    names."""
    import html as _html
    _g, t = task_of(slug)
    if not t:
        return ""
    does = _html.unescape(re.sub(r"<[^>]+>", "", t["does"])).replace("’", "'")
    return " · ".join([does, *WORDS.get(slug, ())])


def task_of(slug):
    """(group, task) for the guide, or (None, None) where no task names it."""
    for group, tasks in TASKS:
        for t in tasks:
            if t["slug"] == slug:
                return group, t
    return None, None


def text(g):
    """Every word the guide prints, with each law reference as the link it
    becomes: what the checks read."""
    bits = [g["glance"], g["more"]]
    for node in g["flow"]:
        bits.append(node[1])
        if node[0] == "ask":
            bits += [f"{a} {b}" for a, b in node[2]]
    for s_ in g["steps"]:
        bits += [s_.get("part", ""), s_["title"], s_["text"], s_["note"]]
        bits += [label for label, _u in s_["actions"]]
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


# ---------------------------------------------------------------------------
# THE GUIDES IN ANOTHER LANGUAGE (the owner, 24 October 2026: "The how to
# pages are the next important section I think is worth translating."). A
# guide's words are the data above, so they are translated as data: every
# piece of words a page prints (i18n.pieces -- a paragraph, a list item, a
# heading, a table cell, a button's label) has its own entry in
# lang/<code>.json, keyed by the page and a slug of its own first words,
# "guide.how-to-vote.you-can-register-if-on-election", and keeping the
# English it was made from. So an edit to one sentence re-opens one piece:
# the page says that piece in English until its translation catches up,
# and preflight names it meanwhile. A key is not a position: a paragraph put
# in above another leaves the other's key, and its translation, alone.
#
# A FIGURE IS NOT TRANSLATED. Where a page's words carry a count, a date or a
# name from the record, the piece holds its [[figure]] and the figure is
# filled in after (build_civics.fill), so the night's numbers never make a
# translation stale. The words SAID and HELP write once for several pages
# are keyed once, where they are written ("guide.said.announced.a-hearing-
# is-announced"), and the shorthand table on Using This Site is the
# glossary's own words, said in the glossary's translations (gloss.*).
# ---------------------------------------------------------------------------
SHORTHAND_SLOT = "<!-- shorthand -->"


def topic_of(slug):
    """civics.py's page `slug`, one of civics.HOW_TO, or None."""
    return next((t for t in civics.TOPICS if t["slug"] == slug and slug in civics.HOW_TO), None)


def learn_topic(slug):
    """civics.py's page `slug`, one of Learn's own pages (not civics.HOW_TO),
    or None. Its words are translated as a guide's are (the person, 25
    October 2026: "start on the Learn pages"), keyed learn.<slug>.*."""
    return next((t for t in civics.TOPICS if t["slug"] == slug and slug not in civics.HOW_TO),
                None)


def topic_body(t):
    """A page of civics.py's as it is translated: its shorthand table, which
    is drawn from the glossary in the page's language, left as a slot."""
    return t["body"].replace(civics.SHORTHAND_TABLE, SHORTHAND_SLOT)


def wording(slug):
    """[(where, words, html)] of everything the page `slug` -- a guide, or a
    page of civics.HOW_TO -- prints in its own words, in reading order:
    `html` False where the words are plain text (a title, a button's label),
    True where they are a page's HTML, which is translated piece by piece.
    The record's own words (In the Record's bills and chapters) and the
    law's references ("RSA 654:7, I") are not in it."""
    t = topic_of(slug) or learn_topic(slug)
    if t:
        out = [("title", t["title"], False), ("lead", t["blurb"], False),
               ("page", reused(topic_body(t)), True)]
        if t.get("holds"):
            out.append(("the limit it states", t["holds"], True))
        return out + [("Where This Comes From", label, False) for label, _u in t["sources"]]
    g = next((g for g in GUIDES if g["slug"] == slug), None)
    if g is None:
        return []
    out = [("title", g["title"], False), ("lead", g["blurb"], False),
           ("At a Glance", g["glance"], True)]
    for node in g["flow"]:
        out.append(("At a Glance, the diagram", node[1], True))
        if node[0] == "ask":
            for a, then in node[2]:
                out += [("At a Glance, the diagram", a, True), ("At a Glance, the diagram", then, True)]
    part, k = "", 0
    for s_ in g["steps"]:
        if s_.get("part"):
            part, k = s_["part"], 0
        k += 1
        where = f"{part}, step {k}" if part else f"step {k}"
        if s_.get("part"):
            out.append((f"{part}, its heading", s_["part"], False))
        out += [(where, s_["title"], False), (where, s_["text"], True), (where, s_["note"], True)]
        out += [(where, label, False) for label, _u in s_["actions"]]
    out.append(("after the steps", g["more"], True))
    out += [("See Also", label, False) for label, _u in g["see"]]
    return out + [("Where This Comes From", label, False) for label, _u in g["sources"]]


def _shared():
    """{English: key} of the pieces SAID, HELP and DMV_HELP write once for
    several pages, each keyed where it is written."""
    import i18n
    out = {}
    for name, block in ([(f"said.{n}", h) for n, h in SAID.items()]
                        + [(f"help.{n}", h[0]) for n, h in HELP.items()]
                        + [("help.dmv", DMV_HELP)]):
        seen = {}
        for s, e in i18n.pieces(block):
            en = i18n.norm(block[s:e])
            if en in out:
                continue
            base = f"guide.{name}.{i18n.slug_words(en)}"
            key, n = base, 2
            while seen.get(key, en) != en:
                key, n = f"{base}-{n}", n + 1
            seen[key] = en
            out[en] = key
    return out


def page_words(slug):
    """[(key, English, where)] of every piece of the page `slug`, in reading
    order, once each: a title and lead under .title and .lead, every other
    piece under a slug of its own first words, numbered where two of the
    page's begin alike, or under its shared key (_shared)."""
    import i18n
    shared, keys, used, out = _shared(), {}, {}, []
    pre = "learn" if learn_topic(slug) else "guide"
    folder = "learn" if pre == "learn" else "guides"
    for where, words, is_html in wording(slug):
        if not words:
            continue
        spans = i18n.pieces(words) if is_html else [(0, len(words))]
        for s, e in spans:
            en = i18n.norm(words[s:e])
            if not en or en in keys:
                continue
            if where in ("title", "lead") and not is_html:
                key = f"{pre}.{slug}.{where}"
            elif en in shared:
                key = shared[en]
            else:
                base = f"{pre}.{slug}.{i18n.slug_words(en)}"
                key, n = base, 2
                while used.get(key, en) != en:
                    key, n = f"{base}-{n}", n + 1
            used[key] = en
            keys[en] = key
            out.append((key, en, f"{folder}/{slug}: {where}"))
    return out


def page_keys(slug):
    """{English: key} of the page `slug`'s pieces (page_words), which
    i18n.say_html draws the page in another language with."""
    return {en: key for key, en, _w in page_words(slug)}


def task_words():
    """[(key, English, where)] of the How-To Guides tab's own words: each
    group's heading, and each task in a reader's words with its line."""
    import i18n
    out = [(f"guide.group.{i18n.slug_words(group)}", group, "the How-To Guides tab")
           for group, _tasks in TASKS]
    out.append(("guide.group.more", MORE, "the How-To Guides tab"))
    for _group, tasks in TASKS:
        for t in tasks:
            out += [(f"guide.task.{t['slug']}.does", i18n.norm(t["does"]), "the How-To Guides tab"),
                    (f"guide.task.{t['slug']}.line", i18n.norm(t["line"]), "the How-To Guides tab"),
                    (f"guide.task.{t['slug']}.head", i18n.norm(t["head"]), "the How-To Guides tab")]
    return out


def translated(lang):
    """The slugs of the guides `lang` has (i18n.PAGES), in its order."""
    import i18n
    return [p[len("guides/"):-len(".html")] for p in i18n.PAGES.get(lang, ())
            if p.startswith("guides/")]


def learn_translated(lang):
    """The slugs of the Learn pages `lang` has (i18n.PAGES), in its order:
    civics.py's own pages, not the glossary, which is keyed by term."""
    import i18n
    return [p[len("learn/"):-len(".html")] for p in i18n.PAGES.get(lang, ())
            if p.startswith("learn/") and learn_topic(p[len("learn/"):-len(".html")])]


def translated_words():
    """Every piece of every guide a language other than English has, and the
    How-To Guides tab's words where one has the hub: what i18n.code_words
    asks a catalog to answer. A piece several guides share is listed once."""
    import i18n
    out, seen = [], set()
    langs = [c for c in i18n.LANGS if c != i18n.DEFAULT]
    slugs = list(dict.fromkeys(s for c in langs for s in translated(c) + learn_translated(c)))
    rows = [r for s in slugs for r in page_words(s)]
    if any(i18n.has(c, "resources.html") for c in langs):
        rows += task_words()
    for key, en, where in rows:
        if key not in seen:
            seen.add(key)
            out.append((key, en, where))
    return out
