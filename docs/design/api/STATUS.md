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
   - Preflight --code: 985 passed, 0 failed.
   - **Proof:** a full build of dev e308cee5 against the branch changes only
     api.html (no noindex), data.html (the new paragraph), directory.html
     (one line), find.json (one entry) and sitemap.xml (one address); the
     other 57,652 files are identical. The two seeds give 0 differences.
   - Screenshots of the For Developers section and of /api at 390 and
     1280, light and dark, with no sideways scroll: `screens/link/`.
2. **`feat/api-recordings` @ 52c9e015**, on top of feat/api-link: Q18,
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
building as asked. The build starts once dev moves after Sunday's release, on
`feat/requests-on-members`. Questions B1 to B4 are in the design's section 4,
each with a default:

- **B1.** The banner's count: 312, or 305 still standing?
- **B2.** Members-elect pages indexed, or noindex until numbered?
- **B3.** Members-elect pages stay after 2 December until the General Court
  numbers the person?
- **B4.** A member with no requests opens on 2025–2026?

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
