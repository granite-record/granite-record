# Proposal: How New Hampshire works

A civics and participation section for Granite Record. Drafted 6 September
2026.

---

## The idea worth building around

Every state has a civics explainer somewhere. Almost all of them are static
prose that was written once and describes an abstraction.

Granite Record can do something none of them can: **explain a thing and then
show it happening, this term, with the record attached.**

- "A committee of conference is appointed when the two chambers pass different
  versions of a bill." → *Here are the 133 conference committees this term,
  with recordings.*
- "The Governor may veto a bill; two thirds of each chamber can override."
  → *Here are the vetoes this term, and here is the roll call where the
  override failed by four votes.*
- "Most bills die in committee." → *Here is the number this term, and the ten
  most recent.*
- "A public hearing is where anyone may testify." → *Here is one, starting at
  the moment the chair opened it.*

That is the whole argument for building this here rather than linking to
someone else's. The explanation and the evidence are the same object. Nobody
else has both.

It also solves a problem the site already has. Someone arriving from a search
result lands on a bill and sees "Ought to Pass with Amendment, 15-1" with no
idea what that means. The explainer is the missing half of the record.

---

## Structure

Eleven pages, in two groups, under `/learn/`.

### How the state works

**1. The General Court.** The 400-member House and 24-member Senate; two-year
terms; the pay; how unusual the size is. What an LSR is and how it becomes a
bill. The committee system. This is the page everything else hangs off.

**2. How a bill becomes law.** The main diagram. Introduction, committee,
report, floor, crossover, second chamber, conference, enrolment, Governor,
veto and override, effective date. Every stage links to a live example.

**3. The Governor and the Executive Council.** The Council is the page most
worth writing, because it is genuinely unusual — five members, elected by
district, approving contracts, nominations and pardons — and almost no
resident could describe what it does. Most states have nothing like it.

**4. The courts.** Supreme, Superior, Circuit. How judges are appointed and
how long they serve. Where the legislature and the courts meet: a statute
challenged, a decision the legislature responds to.

**5. The Constitution.** New Hampshire's is among the oldest still in force,
and it is not amended the way statutes are: a CACR must pass both chambers by
three fifths and then be approved by the voters. **The site already carries
CACRs.** They sit in the record beside ordinary bills with nothing to say they
are a different kind of thing entirely, or that the last step is an election.
Parts First and Second, what each covers, and what happens to a CACR that
passes.

**6. State agencies.** Who actually carries out what the legislature passes:
Health and Human Services, Transportation, Environmental Services, Education,
Safety, Revenue. How a commissioner is appointed — nominated by the Governor,
confirmed by the Executive Council — which is the concrete answer to "what
does the Council do", and should link straight back to page 3.

This page has an anchor nothing else on the site uses: **agency staff are in
the recordings constantly.** "For the record, I am the deputy commissioner
of…" opens testimony in nearly every hearing. A reader who has watched a
department oppose a bill has already met the agency without knowing what it
is.

**7. Administrative rules.** The most obscure page on the list and one of the
most useful. A statute says what shall happen; the rules say how, and the
agency writes them, not the legislature. The Joint Legislative Committee on
Administrative Rules reviews them, which is where the legislature keeps a say
over how its own statute is carried out.

The anchor is in bill text the site already holds: *"the department shall
adopt rules under RSA 541-A"* appears in a large share of bills, and a reader
following that phrase currently has nowhere to go. JLCAR is also a committee
with recordings, so it fits the committees page when that exists.

**8. Town meeting and local government.** Optional, and last. It matters
enormously in New Hampshire and it is where SB 2, default budgets and warrant
articles come from — all of which appear constantly in the bills this site
carries, unexplained.

### How to take part

**9. Testifying and attending.** How to sign in for or against a bill online,
how to submit written testimony, how to find when a hearing is, what a pink
card is, what happens to what you submit. This is the highest-value page on
the list: the process is genuinely open and almost nobody knows the mechanics.

**10. Finding your representatives.** By town, by district. What the House
district numbering means. Feeds into the existing towns page.

**11. Using this site.** How to search, what the tabs hold, what a timestamp
claims and what it does not, how to follow a bill by RSS, and how the archive
is organised. Also the corrections address, prominently.

---

## The diagrams

Four, and they should be the only illustrative element on these pages.

**How a bill moves** — the main one. Stages left to right, both chambers,
with the branches that kill a bill drawn as clearly as the path that passes
one, since most bills die. Colour by chamber, not decoratively.

**Who is elected, and when** — 400 representatives, 24 senators, 5 councillors,
a governor, all on two-year terms, all elected together. That "all on the same
cycle" fact surprises people and explains a lot about how the place behaves.

**How a judge is appointed** — Governor nominates, Council confirms, service
to seventy. Short, and it is the diagram that makes the Council concrete. The
same shape covers a commissioner's appointment, so one drawing serves two
pages.

**Statute to rule to enforcement** — the legislature passes a law, the agency
writes rules, JLCAR reviews them, the agency enforces. This is what makes page
7 land, and there is nothing comparable published anywhere a resident would
find it.

**Where the money is decided** — House Finance, its divisions, Senate Finance,
committee of conference, the two-year budget. Only if the first three land
well; this one is the hardest to make honest and simple at once.

Build them as **static SVG in the page markup**, not as a library. They must
be readable at 360px, work in high-contrast mode, and carry real text rather
than paths. A diagram that needs 200KB of JavaScript to explain a legislature
is the wrong tool for this brief.

---

## Accuracy, which is the whole risk

A wrong timestamp is embarrassing. A wrong description of how a veto override
works is a different category — it is the sort of error that gets quoted, and
it undermines the record it sits beside.

So the project's own rule applies unchanged: **read the artefact before
describing it.**

- Structure and powers: the New Hampshire Constitution, Parts First and
  Second.
- Procedure: the House Rules and the Senate Rules, which are published each
  term and are the actual authority for what a committee may do.
- Deadlines and crossover: the session calendar the General Court publishes.
- Anything about the Council: the Constitution, Part Second, and the Council's
  own published agendas.
- The courts: the Judicial Branch's own site.
- Administrative rules: RSA 541-A, the JLCAR rules manual, and the rules
  register the state publishes.
- Agencies: each department's own site for what it does, and the budget for
  what it costs.

Every page ends with its sources, linked. Not a bibliography for
respectability — because a reader who wants to check should be one click from
the authority, and because it is what the rest of the site already does.

**Have a person who knows the building read it before it ships.** A clerk, a
long-serving member, a State House reporter. The prose will be wrong in small
ways that only someone who has sat through it will catch, and the corrections
address exists for exactly this.

---

## Tone

Plain, short sentences. Explain the mechanism, not whether it is good.

Where something is genuinely contested — whether 400 members is too many,
whether the Council should exist — say that it is debated, give the strongest
version of each side in a sentence, and stop. The site's credibility rests on
being the place people of every view can agree the facts are right, and this
section is where that is easiest to lose.

Avoid civic-education register. No "did you know", no exclamation marks, no
implication that the reader ought to be more engaged than they are. Someone
looking up how to testify has already decided.

---

## Sequencing

Do not build all eleven. Build one, publish it, see whether anyone reads it.

**First: "Testifying and attending."** Highest value, no diagram needed,
smallest research burden, and it is immediately useful to somebody. It also
tests whether this section belongs on the site at all.

**Second: "How a bill becomes law"**, with the main diagram, linked from every
bill page. This is the one that changes how the rest of the site reads.

**Then the Constitution page**, because CACRs already sit in the record
labelled as ordinary bills, and that is a correctness problem as much as an
explanatory one.

**Then the rest**, in the order above, as gaps allow. Agencies and
administrative rules have the least written about them anywhere else, and are
the two most likely to be the reason somebody links to this site.

Against the roadmap: this fits after the committees page and alongside the
archive work. It needs no new data and touches no pipeline, which makes it
good work for a stretch when a fetch is running.

---

## One thing to decide early

Whether these pages are **linked from bill pages contextually** or only from a
menu. Contextual is far more useful — "Ought to Pass with Amendment" linking
to the paragraph that explains committee reports — and it is a small addition
to `build_bill_pages.py` while that file is already being restructured.

It is also the difference between an explainer somebody has to go looking for
and one that arrives when the question does.
