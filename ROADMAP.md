# Granite Record — roadmap

Written 6 September 2026, from a list of everything outstanding. Ordered by
what blocks what, not by size. `ARCHITECTURE.md` has the reasoning behind the
structural items; this places them among the rest.

Three things worth saying before the list.

**The consolidation has already paid for one of the biggest items.** The
committees page described below was expensive a week ago and is nearly free
now: `proceedings.csv` holds one row per (bill, date, kind, recording) with
committee, times and boundaries on it, which is exactly the shape that page
needs. It did not exist on Thursday.

**The archive probe belongs early, not late.** Two past terms and a handful of
gentle requests — though the script that asks the structural question has yet
to be written, so it is a short build plus the requests, not requests alone.
It tells you whether bill numbers, docket shapes and URL
patterns have held since 2005 — and both of the two big archive decisions
(term keying and the file cap) are being made on assumptions that probe would
confirm or destroy. Doing it after building is how you build twice.

**Nothing here should go out before `probe_alignment --truth` is clean.** That
rule has not changed and gets easier to forget as the work moves away from
timestamps.

---

## Now: finish the structure

These are in flight or next, and most other work is easier after them.

**Split `build_site_v2.main`.** `renderDetail` is done — split 6 September
into nine hoisted functions, one per tab, output verified byte-identical
against the pre-split page over ten renders covering every station state.
`build_site_v2.main` remains. The failure mode was a blank page for someone
arriving from a shared link, the worst possible one for a site you are about
to publicise.

**Finish the timestamp work.** Coverage is at 66% of proceedings actually
taken up. `--gaps` and `--phrases` still have room, floor ends are only
partly precise, and committees of conference are not properly modelled.
Everything on the site that points at a recording depends on this.

---

## Next: the committees page

The single best return on the list, and it needs no new data.

A page per committee, with:

- **Composition** — members, chair, vice chair, aide, room. `fetch_committees.py`
  already returns all of it.
- **Bills referred**, as the same cards the search tab uses.
- **Sessions that term**, oldest or newest first, each as a card with the
  recording embedded and per-bill start and end timestamps beneath it, and a
  summary above in the same shape as the bill narrative. One page per
  committee rendering both views client-side, not a page per session: 29
  pages and 29 JSONs rather than 1,061 files, which keeps this clear of the
  file cap entirely. It says what was heard and what was done —
  which bills, which were executed, which were voted, which went to consent.
  `proceedings.csv` plus `committee_reports.json` has every part of that.
- **Statistics** — bills referred, hearings held, reports filed, how often the
  committee's recommendation was followed on the floor.

Why it is worth doing now: it is a genuinely different way into the record.
Bill-first search answers "what happened to HB 1442". This answers "what did
Legislative Administration do on 3 March", which is the question a reporter or
a committee member actually asks. It also surfaces the timestamp work, since a
committee day is where the boundaries are densest.

Do it after the `build_site_v2` split, not before — it adds pages to the same
function that is being taken apart.

---

## Then: decide the archive shape

In this order. Each depends on the one before.

**1. Probe two past terms.** 2023–2024 and 2005–2006. What is the same, what
moved, what does not exist that far back. Four requests, gentle, one at a
time. **This script does not exist yet.** `probe_archive.py` answers a
different question — whether a year's Secretary of State PDFs carry a text
layer or are scans needing OCR — and its defaults are 108 requests, most of
them 404s on constructed filenames, which is one of the two things that got
this address blocked. Run it narrowed to a single year and sample.
`setup_archive.py` is local only and touches no network.

Probed 6 September, one request each: 2005 and 2023 both returned 404 at
`/BillHistory/SofS_Archives/{year}/{chamber}/{bill}.pdf`. `netcheck.py`
immediately after showed every ordinary request answering 200, so this is not
a block and not the firewall -- the constructed URL pattern simply does not
resolve. (The 403s netcheck reports are a WAF rule against HTTP/1.0
specifically; HTTP/1.1 answers 200 on the same URLs.) The pattern in the
docstring is cited from a 2001 example, so the next step is one request
against that exact example to tell a stale pattern from patchy year coverage.
Do not sweep years looking for a hit: probing filenames that do not exist is
one of the two things that got this address blocked.

**2. Decide the file cap.** Cloudflare Pages allows 20,000 files. One term is
at 8,045 — already 40%, which *contradicts* the fourth-term arithmetic rather
than confirming it. That figure assumed two files per bill; there are three,
because `feed/bill/` is one per bill too. 6,701 a term in bill files alone
means the cap breaks partway through the THIRD term. Either older terms get
fewer static pages each, or per-bill data moves to R2 behind a Worker. The
probe informs this: if 2005 has no roll call
detail, older terms need far less per bill.

**3. Term-keyed identifiers.** `(term, bill)` everywhere. Cannot start before
2, because the two cap options imply different paths.

**4. Back-fill one term end to end**, 2023–2024, as the proof.

---

## Independent of all of the above

These need no structural work and can fill any gap.

**Cheap, and each removes a visible rough edge:**

- A link to the bill text from the card view.
- RSA links are only partially working on the detail view. A citation that
  silently fails to link is the one place a reader goes to check a
  committee's reasoning against the statute, so this is a defect rather than
  a polish item.
- Bill text and amendment text layout in the detail view.
- Corrections email forwarding, and turning off Cloudflare's Email Address
  Obfuscation, which currently breaks the address on a site whose whole
  invitation is to be told when it is wrong.
- The about and how-it-works pages, which are stale.
- Progress circles on the compressed card — House, committee, Senate,
  Governor — filled, checked or crossed. Communicates status faster than the
  chip does, and is the sort of thing a first-time visitor reads without being
  taught.
- More definition between cards and background; the same for search controls.

**Sharing and navigation, which matter more once the site is publicised:**

- Returning to a search after opening a bill, without a long URL. Every shared
  link carries the search state today. Worth fixing before the site is shared
  widely, because the URLs people paste now are the ones that will circulate.
- RSS and email follows for bills, legislators, committees and calendars. The
  feeds exist; nothing on the site explains they do, and there is no email
  path at all.

**Scaling, mobile and desktop:** text, tabs, search, embeds. Do this after the
card and page changes above, or it gets done twice.

---

## Needs data not yet fetched

Each is a fetch plus a parser plus a place to put it. None blocks anything
else, and each is worth doing when the structure around it is settled.

| | Notes |
|---|---|
| Senate committee reports | The House side is done; the Senate is not |
| Public hearing testimony | 565 of 1,237 fetched |
| Permanent journal speeches | **The largest content addition available.** The House journal records what members actually said. Nothing else on the site carries a member's own words |
| Fiscal notes | Already inside the bill text, at the bottom, not parsed |
| Amendment text | `billtext.aspx?txtFormat=amend&id=2026-1054H` reaches it directly; would replace the current 40% ceiling and make diffing possible |
| Committees of conference | 133 recordings exist and are linked, but the proceeding is not modelled |
| Executive Council, Governor | `status/officials.txt` is unedited, so neither appears |
| Rules and executive departments | Not started |

**Amendment text is the one I would do first** of these: it unblocks amendment
diffing, which is on the list separately, and the endpoint is already known.

---

## Legislator pages

Grouped separately because the list has several items that are really one job.

Sponsored bills are missing, roll call votes are hard to read or compare, the
layout is not parsable, and the legislators index page is poorly formatted.
That is one redesign, not four fixes, and it wants doing in a single pass
after the `build_site_v2` split — the same reason as the committees page.

---

## What I would not do yet

**Bill indexing.** The sitemap has never been submitted, so nothing is indexed
at all. Submitting it before the URL and sharing scheme is retooled means
search engines index URLs that are about to change.

**Publicising widely.** The `renderDetail` crash class is fixed but the
function is still 472 lines, and a blank page for an arriving visitor is worse
than no visitor. After the split.
