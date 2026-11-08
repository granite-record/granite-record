# Public data API: status

Written by the API session for the manager on the laptop. Last update:
8 November 2026. The latest commit on `design/api` carries the same status
in its message.

**READY: `feat/api-link` @ 8a2a4446 for the post-webinar release.** It
contains dev 92247871, and preflight --code passes: 987 passed, 0 failed.

- **Where it links the API from:**
  - the data page's For Developers section (its first paragraph, "The Data
    API");
  - the site search;
  - the directory.
- The sitemap lists /api, and the page is no longer noindex.
- The full-build proof below was made at a5a4afbd. Since then only dev's
  merge has come in, plus one stamp moved one past dev's.

## Ready for review, not merged

1. **`feat/api-link` @ 8a2a4446** (proven at a5a4afbd): link and announce
   the API, for the first release after the webinar (about 11 to 12
   November).
   - /api loses its noindex and joins the sitemap, dated like /data.
   - **Where it is linked (proposed):**
     - a first paragraph, "The Data API", at the top of the data page's
       For Developers section;
     - the site search ("The Data API", found by api, developers, json,
       database);
     - the directory, beside "The data, as tables".
     - Not the header: Data already leads there. Say if you want it in the
       footer's "The record" column too.
   - **What the page stops saying:**
     - the noindex tag;
     - the note in its code that it is unlinked;
     - "A page on another site may read the manifest and the spreadsheets"
       now reads "every file the manifest lists", since dev's _headers
       serve each API file to any origin.
   - Nothing else on the page refers to being unlinked or to December.
   - Preflight --code: 985 passed, 0 failed.
   - **Proof:** a full build of dev e308cee5 against the branch changes only
     api.html (no noindex), data.html (the new paragraph), directory.html
     (one line), find.json (one entry) and sitemap.xml (one address); the
     other 57,652 files are identical. The two seeds give 0 differences.
   - Screenshots of the For Developers section and of /api at 390 and
     1280, light and dark, with no sideways scroll: `screens/link/`.
2. **`feat/api-recordings` @ 7982981a** (proven at 316e60bb), on top of feat/api-link: Q18,
   publish the watch links. This is for the release after the linking.
   - proceedings.csv gains `watch_url` at the end:
     `https://www.youtube.com/watch?v=<id>&t=<start>s`, built from the id and
     this site's own start, with no `t=` where there is no start.
   - The database gains `recordings`: term, bill, video_id, committee,
     chamber, date, start_seconds, end_seconds, how_placed, watch_url. One
     row per sitting that has a recording, so it is the rows of
     proceedings.csv with a video_id.
   - video_title and scheduled_seconds stay out. The "a YouTube column stops
     the build" guard is replaced: preflight now holds proceedings.csv and
     recordings to their approved column lists exactly.
   - The bill files' stations still carry no watch link, because the answer
     named only the database and proceedings.csv.
   - Preflight --code: 985 passed, 0 failed.
   - **Proof** (316e60bb; 52c9e015 changes only two descriptions in
     schema.json), against feat/api-link:
     - proceedings.csv: 105,476 rows, identical but for the new last
       column. 22,601 have a watch_url, all well formed; 15,223 of them
       carry a start.
     - The database: recordings has 22,601 rows, one for each.
     - Also changed: manifest.json, schema.json, data.html (the column
       list and the size, 10.3 MB to 11.5 MB) and api.html.
     - No video_title or scheduled_seconds anywhere.
     - The two seeds give 0 differences in 57,657 files.
   - Measured on the build: 4,392 recordings have no committee, nearly all
     floor debates and conferences, which are no one committee's. The
     schema says so.

## New project: 2027 requests on members' pages, and members-elect pages

The design is in `docs/design/requests-members/DESIGN.md`, written before
building as asked. Alice's answers of 7 November are recorded in its section
4:

- B1: the banner counts the 305 standing requests.
- B2: elect pages are noindex until numbered.
- B3: elect pages stay past 2 December.
- B4: a member with no requests opens on 2025–2026.

**READY for review: `feat/requests-on-members` @ e9bb088b**, for the dry run
on Wednesday 11 November. It contains dev 92247871, which is still dev's tip.
Preflight --code: 990 passed, 0 failed.

- **Bill search:** "300 bill requests filed for 2027 — see them" on
  2025–2026. On the live kit it will count n − withdrawn; this build's kit
  holds 302 requests, 2 of them withdrawn. The banner is gone once 2027–2028
  is published.
- **Members' pages:**
  - "2027 Bill Requests" is a term in the member's own picker. 92 members
    have requests in this build's kit.
  - A member opens on their requests; one with none opens on 2025–2026.
  - From 2027–2028 on, its bills come first.
- **New members-elect:** 168 provisional pages. Each shows:
  - name and party;
  - chamber and district, with its towns linked;
  - "Elected November 3, 2026. Takes office December 2, 2026."
    ("Member of" and "Took office" from that day);
  - their requests where certain;
  - the source.

  The pages are noindex, left out of the sitemap, and have no id and no
  contact details. The Officials tab, the town pages, the My Town card and
  the district map link a new person to their page.
- **2 December and after:**
  - The pages stay up.
  - The night the roster carries the person, their regular page takes the
    same address.
  - If the roster gives them another address, the old one answers with a
    301 automatically. That is written by build_pages from
    elect_pages.json's "moved" for as long as the 2026 results are the
    newest. A person can make it permanent in moved_addresses.json.
- **Proof:** a full build dated 8 November, two seeds, 0 differences in
  57,827 files. Against dev, only these change:
  - legislators/*.json: each gains its "slug";
  - the town pages, officials.html and es/officials.html: the new links;
  - members_elect.json, places.json and district_map.json: "e" links only.
    places.json was proven byte-identical to dev's once the new links are
    taken out;
  - meta.json: "by_slug";
  - app.js, components.js, data.html: the stamp count;
  - the 168 new pages.

  legislators.json and former.json are unchanged.
- **Review:** an adversarial review found 9 problems, now fixed. The worst
  was that no member file carried a slug, so on real data no member was
  offered their requests; its test had added one by hand. The screenshots
  then caught the provisional pages drawn blank with script on, and that is
  fixed too.
- **Screenshots** at 390 and 1280, light and dark, with no sideways scroll:
  `docs/design/requests-members/screens/`. They show the banner, a member
  on their requests (David Watters) and a provisional page (Kurt Webber).

**One difference from the design.** There is no breadcrumb on the
provisional page. The Members-Elect tab it would name is removed on 2
December, and the page outlives it.

## Questions (answer by a commit message, or through Alice)

- **Q-A, the CC0 line and the timings.** The approved rights line names
  "the keys and joins it makes and the corrections made here by hand"; it
  does not name timings. Your message says "the CC0 line then covers the
  timings".
  - Default: leave the approved words as they are, and add "the moments it
    places in recordings" to them in feat/api-recordings only if Alice wants
    the timings named.
- **Q-B, recordings, one row a sitting or one row a video?** I built one row
  per sitting with a recording, since DESIGN.md 2.10 lists start and end
  seconds, which belong to a sitting.
  - Default: as built. A table of videos alone (id, committee, chamber,
    day) would be a smaller second table, if wanted.

## Next, once answered or released

- **Election results (QE1 to QE6, every default accepted).** The branch
  waits on two things:
  - the 2026 results reaching dev (`collected/election_2026.json` is still
    only on `data/election-2026-sos`);
  - the shared "is this race final" function the election results session
    is to put in src/lib (`race_final`).
  - Until then: totals only; counts for every candidate once a race is
    final; losers with no person number; 2024 included once its recount
    entry is in members_elect.json; other offices once the official file
    holds them.
- **Q21**: Senate hearing testimony stays out of the bulk files, as now.
- **Branch 7, the change-log key**: still waits on follow and feeds.
