## 7. The order of work, from now to the January session

The owner's attention for approvals and merges to `main` is the real bottleneck. Sizes are agent-days and are guesses; agents work in parallel, so a phase's sum is not its length.

| Phase | When | What | Size |
|---|---|---|---|
| **0. The release** | 27 Oct – 1 Nov | **The release** goes out as frozen; only owner-named XS items join it (P14, P2's example, P8). **The owner, this week:** answer D1, D8, D11 and D14 (and D23, D26); create the restricted YouTube key; send the IT office letter (its points are in §9, D8). **Agents, on dev only:** §5 items 1 and 3; rebase `night-clock` | S (≈2) |
| **1. To the webinar** | 2 – 10 Nov | **No new feature shows.** `night-clock` to main after a dry run. §5 item 4 (the laptop's files) and, after D26, item 5. The live timer written and tested, then deployed in shadow by the person once approved, by 13 Nov. The API contract on paper (ids, file list, licence line) for the owner. **The webinar:** show the CSVs and say Live Now and an API are coming before the session. Promise no date | M (≈6–8) |
| **2. To the release before the turn** | 11 – 24 Nov | Shadow watches unscheduled House streams, and the pre-scheduled ones on 16–18 Nov. **Live Now:** `live/schedule.json`, the `/live` page and the home line, unlinked, with their checks. **API:** `build_api.py` v1 (manifest extended, schemas, bill bundles, `people.json`, ISO dates and `person_id`), published unannounced and marked beta. **Votes:** §3.3 stage 1 and P9. **Preflight:** §5 item 8's helpers, new checks in their own files. **Polish:** batch A. **The release candidate by 20 Nov; to main by 24 Nov only after `tests/rehearse_turn.py` (the full run, on the laptop) and a New term dry run pass on that candidate.** If either fails, the night-touching parts wait until after 6 Dec | ≈14–23 by the item sizes (live page 2–4, API 5–8, votes 1–2, helpers 1–2, polish A 3–4, release and rehearsal 1–2, shadow 0.5–1). If it runs over, cosmetic polish moves to December first, then the API's schemas page |
| **3. The term turn** | 25 Nov – 6 Dec | **No merge to main that changes the night.** The turn on 2 Dec runs on the 24 November code, rehearsed on that candidate. With `night-clock` merged, a New term run started by hand outside 08:00–12:00 UTC (03:00–07:00 EST) skips the bill requests and the document lists; they are taken the next night, and the rehearsal shows it. The live timer sees Organization Day, the Senate's one test. v1 is watched through the turn | S for agents; the person's turn steps |
| **4. December** | 7 Dec – ~30 Dec | **Live Now public, with the home line and link, about 9 Dec. `/developers` published and the API announced (beta).** `record.sqlite.gz` and the `/changes/` extension. Polish batch B (P6, P10, P13) once the owner has seen the words. Preflight moves as time allows. **The last release to main before session, about 30 Dec** | L (≈10–14) |
| **5. The first session weeks** | January | Fixes only in the first session week. **The measurement on the first and second House session days**, only with the IT office's yes (D10). Then, with that yes and fresh views, the database poller (§3.3), proposed for approval | M |
| **6. After** | February on | §5 item 11: the record becomes the source; raw kept by date; one normaliser; the turn machinery replaced. The documents cut to a year boundary (D11). The video indexes move out of git (D7). `publish.bat` retired (D21). **Optional, each on its own decision:** a public bucket and per-record files; the full record and text in SQL; bill text versions; party per term; an Open States crosswalk | XL |

**Ready before the first session day, or it is not done:**
- Live Now public: every live stream, its committee and its day's schedule, linked from the home page;
- each session-day page drawing its votes from its own data, saying "as of this morning";
- API v1 (beta) with its generated docs, the SQLite of the tables, the bill bundles and the extended change log;
- `night-clock` merged;
- preflight no slower than today;
- the term turn complete;
- the IT office asked.

**What can follow:** votes within minutes (the IT office's answer and the January measurement); an evening run, only if the IT office declines polling; the documents on the night; a public bucket and per-record files; the record as the pages' source; the preflight split's remaining areas.

---

