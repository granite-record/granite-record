# 2027 bill requests on members' pages, a banner on the bill search, and pages for new members-elect: design

From the API session, 7 November 2026, for the laptop manager and Alice.
This is the design to agree before building. The branch is
`feat/requests-on-members`, off dev once this weekend's release is live.
Every figure below is read from origin/dev 92247871; file:line references
are to that commit.

## 1. The bill search banner

**What exists.** The bill search opens on `terms[0]` of meta.json (the
newest-term rule, app.js:3062-3081). build_lsrs.py puts
`meta.requests = {term, label, year, n, withdrawn}` beside it. The requests
are a term in the picker, between All Terms and the current term
(app.js:3173-3190). A `<button class="link" data-term="...">` already opens
them; requestOffer uses it (app.js:2518-2526).

**Proposed.**

- **Words.** "**312 bill requests filed for 2027** — see them". The count
  is `meta.requests.n` and the year is `meta.requests.year`, never typed in
  (preflight's `_requests_year_their_own` holds that). "See them" is the
  existing `button.link data-term`, which opens the requests term.
- **Look.** The `.lsrnote` box the requests term already shows (app.css:
  3411), so a banner and the list it opens read as one thing.
- **Where.** Above the results, in `#summary`'s place on the open term
  (app.js:10933-10946).
- **When it shows.** Only on the newest term (`term === terms[0]`), and
  only while the requests' year is after that term's first year. On
  2025–2026 it shows: 2027 > 2025. It is gone by itself the night
  2027–2028 becomes `terms[0]`, the night the first 2027 bill is published,
  so it never offers requests from the term the site is already on. It does
  not show on All Terms, an older term or the requests term itself.
- **Question B1.**
  - `n` (312) counts the 7 withdrawn requests too. Alice's words were "n
    from meta.json", so the default is 312 with the words "filed for 2027",
    which is true of all 312.
  - The alternative is "305 bill requests for 2027" (n − withdrawn), the
    ones still standing.

## 2. Requests on a sitting member's page

**What exists.** A member's page is drawn by app.js from
`legislators/<id>.json`, not from the bill search's `#year`.
- Its term picker is `termControl()`'s `select[data-pf=term]`
  (app.js:8236).
- Its terms come from the member's own sponsored rows and votes
  (`recordTerms`, app.js:10582).
- It opens on the newest published term they have
  (`PAGE.terms.find(published)`, :10786).
- build_lsrs.py already matches each request to a sitting member
  (`sponsor_slug`, by a folded name that only one sitting member has,
  build_lsrs.py:114-144). It runs after the member files are written
  (build_all.py:853 against :808).

**Proposed.**

- **Telling the page which members have requests.** build_lsrs.py adds one
  key to `meta.requests`: `by_slug`, which maps each member's slug to their
  number of requests. That is about 200 small entries.
- **The picker.** `recordTerms` adds the requests term to a member's terms
  when `by_slug` names them, labelled `meta.requests.label` ("2027 Bill
  Requests"), newest first.
- **Which term the page opens on.**
  - It opens on the requests term when the member has requests.
  - It opens on 2025–2026 when they have none, so nobody lands on an empty
    term. This is the manager's suggestion; I agree.
- **Fetching.** The page fetches `idx/2027-requests.json` (312 rows, small)
  only when that term is opened. preflight's `_no_index_off_the_list` holds
  that a page asks for no index it does not read.
- **On the requests term:**
  - The Bills tab lists the member's requests with the bill search's own
    request card (`lsrCardHtml`): number, title, House or Senate request,
    and filed or withdrawn.
  - Above the list, one line in the bill search's own words: "These are
    requests, not bills yet." (app.js:10933).
  - The Votes tab says "No votes: requests are not voted on until they are
    bills." The term's summary and attendance are left out.
  - Co-sponsored is empty, because a request names only its prime sponsor.
    The tab says "A request names only its prime sponsor."
- **January.** Requests become bills when introduced. build_lsrs already
  marks each one ("Introduced as HB 45", `became_bills`, :150-175), and
  the newest-term rule moves the site to 2027–2028. From that night the
  page opens on 2027–2028 if the member has bills there, through the same
  `published` rule, and the requests term stays in the picker while
  build_lsrs still writes it.

## 3. Pages for new members-elect

### What exists

- `site/members_elect.json` is written by build_members_elect.py only
  between the election and Organization Day (the window, :222-244), and is
  removed outside it (:1155-1162).
- Every page draws a member-elect from `for_pages()` alone (:924-978).
- New people (`k: "new"`, 168 of 405) carry no id and no slug, so nothing
  links them (components.py:848).
- The rules of 16 October, held by preflight:
  - `_elect_never_the_roster` and `_elect_pages_never_sitting`: a
    member-elect is never in legislators.json, former.json, places.json
    or the census.
  - `_elect_pages_retire`: nothing is drawn from 2 December.
- Alice's rule of 30 October (commit 776cbe70): no id until the General
  Court assigns one.

### Proposed: a provisional page, kept apart

1. **Its own list, not the roster.**
   - A new writer, `src/pages/build_elect_pages.py`, reads the results
     file (`collected/election_2026.json`, already on dev) and the owner's
     `corrections/members_elect.json` (only "matches": a `null` there is a
     confirmed new person).
   - It writes `site/elect_pages.json`: name as the results print it,
     party, race (chamber, county, district), towns from districts.json,
     and slug.
   - It writes nothing else, and no id. It never touches legislators.json,
     former.json, places.json or the census, so those checks hold as they
     are.
   - It reads the results file rather than `members_elect.json` because
     that file is removed on 2 December, and the pages must outlive it
     (point 5).
2. **The address.**
   - It is `build_site_v2.member_slug` applied to the printed name and the
     race: the same function the roster will use, so most pages keep their
     address when the person is numbered.
   - A slug that is already a sitting or former member's page address, or
     that two new people share, is not written. That person stays unlinked,
     and the build names them for a person to settle.
   - Nothing like a suffix is invented.
3. **The page.**
   - It is written by build_legislator_pages.py with the members' own
     template.
   - It sets `GR_ELECT_ONLY` and the slug, and no `GR_MEMBER`, because
     there is no id.
   - It shows: the name as the ballot prints it, party, district and its
     towns, and "Elected November 3, 2026. Takes office December 2,
     2026." (from 2 December: "Took office December 2, 2026.").
   - Then their 2027 requests, the same cards as in 2.
   - There is no contact detail, no votes, no seat and no committees,
     because none is published for them. Each fills in when the General
     Court publishes it and numbers them, as for every member.
   - The breadcrumb is Officials, Members-Elect.
4. **Requests, matched by name only where certain.**
   - A request's sponsor is matched to a new member-elect when their folded
     name is the same, the chamber of the request (HB/HR or SB/SR) is
     theirs, and no sitting member, former member or other member-elect
     has that folded name.
   - Anything less stays unlinked in the search, as today.
   - build_lsrs writes the slug for these too, so the search links them.
5. **What happens on 2 December, and after.**
   - The members-elect file and every members-elect block retire on 2
     December, as now. `_elect_pages_retire` is unchanged.
   - The provisional pages do not retire on 2 December. Taking them down
     the day their people take office would turn every link and bookmark
     to a 404 until the roster numbers them.
   - Each stays, worded "Took office December 2, 2026", until the night
     the General Court's roster carries that person. That person is
     matched to an elect page by the same rule as 4: name, chamber and
     district, with only one candidate.
   - That night the regular page is written:
     - **The same address**, when the roster's slug equals the provisional
       one, which is the usual case. The regular page simply replaces it.
     - **A different address** (the roster spells the name differently):
       the provisional address must become a 301. moved_addresses.json is
       written only by a person (`record_moves.py`). So the build stops and
       names the address until the person records it. check_site refuses a
       provisional address that is neither a page nor a 301.
   - The provisional list ends when every one of its people is numbered,
     or at the next general election, whichever is first.
6. **Links to them.**
   - The Members-Elect tab and the town pages' members-elect chips link a
     new person to their elect page (`pchip` with the slug).
   - The district map's members-elect line does the same.
   - The sitting and former links are unchanged.
7. **Search engines.**
   - Default: an elect page is in the sitemap and indexed, like any
     member's.
   - Question B2: or noindex until numbered? Its address is meant to last,
     so indexing seems right.

### Checks to add

- An elect page is written for every certain new person and for no one
  else.
- None is in legislators.json, former.json, places.json or the census.
- No page carries an id.
- No elect page shares an address with a member's page.
- Request matching names only certain matches.
- After 2 December the pages stay, and the members-elect blocks go.
- The numbered night: the same address gives the regular page, and a
  different address without a recorded 301 stops the build.

## 4. Alice's answers (7 November 2026, late evening, relayed by the laptop manager)

These replace the defaults above where they differ.

- **B1.** The banner counts the standing requests only:
  "**305 bill requests filed for 2027** — see them" (n − withdrawn). The
  withdrawn stay listed in the requests term, marked withdrawn.
- **B2.** Elect pages are **noindex**, and stay out of the sitemap, until the
  General Court numbers the person and the page becomes their regular one.
- **B3.** Elect pages stay past 2 December until the person is numbered,
  saying they took office on December 2.
- **B4.** A sitting member with no requests opens on 2025–2026.

## 5. Order of work, for the post-webinar dry run (Wednesday 11 November)

1. Banner (app.js, one test in preflight's bill search harness).
2. Requests on sitting members (build_lsrs `by_slug`, app.js member page).
3. Elect pages (the new writer, legislator pages, links, checks).

Each is proven on real data with screenshots at 390 and 1280, light and
dark. The whole branch gets an adversarial review before it is called
ready.
