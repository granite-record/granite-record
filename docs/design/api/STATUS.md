# Public data API: status

Written by the API session for the manager on the laptop. Last update:
7 November 2026, after Alice's answers of that morning. The latest commit on
`design/api` carries the same status in its message.

## Ready for review, not merged (nothing merges before this weekend's release)

1. **`feat/api-link` @ a5a4afbd**: link and announce the API, for the first
   release after the webinar (about 11 to 12 November).
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
   - Preflight --code: 985 passed, 0 failed. Full-build proof is running.
2. **`feat/api-recordings` @ 316e60bb**, on top of feat/api-link: Q18,
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
   - Preflight --code: 985 passed, 0 failed. Full-build proof is queued
     behind the linking branch's.

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
