# A second route for captions

Research only, 29 October 2026. No code on any main path changes. Nothing here
was fetched from YouTube or the General Court; every claim about an outside
service cites the page it came from, and what could not be verified says so.

## The problem

Every timestamp on the site past the schedule's rests on a recording's caption
track (`segment_markers.read_words`). Today those tracks arrive one way: the
owner's laptop runs `src/ops/livestreams.py --to-inbox` at 19:30 (Task
Scheduler, `src/ops/README.md`), asks YouTube with yt-dlp for the recordings
the night lists (`inbox_wants`), and drops each `captions.en.json3` into the
bucket's `inbox/captions/` (`cloud.inbox_add`). The night takes them down
(`cloud.py inbox-down`), checks size, sha256 and that words can be read
(`livestreams.take_inbox`), and the build reads them. GitHub's machines cannot
ask YouTube themselves: its bot check has answered them since 26 September and
on every request since 12 October (`livestreams.py`, "THE DATA CENTRE RISK").
Two free fixes have been tried there already (a JS runtime with yt-dlp-ejs, 10
October; curl_cffi impersonation, 18 October).

So if the laptop is off, asleep, or refused (it was on 17-18 October), captions
stop, and recordings keep the schedule's approximate start until it is back.

## What any route must deliver

- **A json3 track, or a change to accept something else.** The inbox accepts
  `captions.*.json3` only (`cloud.py`'s inbox key rules; `CAPTION_FILES` in
  `livestreams.py`). `read_words` also reads a Whisper-style `transcript.json`
  (`[{start, end, text}]`), but gives every word its line's start time — a
  coarser clock than json3's per-word `tOffsetMs`.
- **The timestamp bar (CLAUDE.md).** `python3 src/hearings/probe_alignment.py
  --truth --candidate candidate_segments.json` against `review/ground_truth.csv`
  (35 timed proceedings) and the bench. The candidate median is 0m 01s; it must
  not regress on the proceedings both old and new results place, and those
  placed for the first time must be within a minute at the median
  (`livestreams.worse` / `guard`, `NEW_PLACED_MEDIAN = 60`). A route whose
  words carry different times must be scored on that before anything reaches
  the site.
- **No captions quoted on the site** (CLAUDE.md): unchanged by any route; the
  words are only ever used to find a moment.

## The routes

Volume assumed: about 40 hours of recordings a month in session (an estimate);
about 4,350 recordings captioned so far.

| Route | Works without the laptop? | Cost a month | Needs from the owner | Terms / block risk | Effort |
|---|---|---|---|---|---|
| **A. Channel owners authorise the official captions API** | Yes | $0 | An ask to House and Senate IT; a Google account given a channel role; one OAuth consent | None: the sanctioned route | Little code; slow politics |
| **B. The state supplies caption or audio files** (export, records request) | Yes | $0 to ~$10 (transcription, if audio) | The same ask, in a different form | None | Little code; slow politics |
| C. Unofficial transcript endpoints (timedtext / InnerTube) from the cloud | No: cloud IPs are blocked | $0 | — | High | — |
| D. Same, or yt-dlp, through a rotating residential proxy | Mostly | ~$3.50 (1 GB plan) | A proxy account and a card | Breaks YouTube's Terms; can stop any day | Low |
| E. A VPS or a Cloudflare Worker running yt-dlp | Probably not (datacenter IPs; Workers unverified) | €6–7 VPS, $0–5 Workers | A server | High | Medium |
| F. Our own transcription (audio via D) | Yes, given audio | proxy ~$3.50 + $0–14 transcription | A proxy, a speech API key, a card | Breaks Developer Policies III.E.1/III.I.7 and the Terms | Medium |
| Today: the laptop | No | $0 | The laptop on at 19:30 | Automated access outside the Terms, from a residential IP | Built |

### A. The official captions API, authorised by the channel owners

- `captions.download` "requires the user to have permission to edit the
  video", with OAuth scope `youtube.force-ssl` or `youtubepartner`; an API key
  alone is refused (403).
  https://developers.google.com/youtube/v3/docs/captions/download ·
  https://developers.google.com/youtube/v3/docs/captions/list
- Quota: `captions.list` 50 units, `captions.download` 200, default 10,000 a
  day — about 40 recordings a day, plenty for a session week; the 4,350
  backlog would take ~110 days unless Google raises the quota.
  https://developers.google.com/youtube/v3/determine_quota_cost
- Auto-generated tracks appear as `trackKind: ASR`.
  https://developers.google.com/youtube/v3/docs/captions
  **Unverified:** that an owner-authorised call can download an ASR track
  (non-owners report 403 on them), and that a delegated channel role (YouTube
  has Manager, Editor and Subtitle Editor roles,
  https://support.google.com/youtube/answer/9481328) satisfies "permission to
  edit the video". Both are answered by one test call once a role is granted.
- The project already holds a YouTube Data API key (`YOUTUBE_API_KEY`) for
  discovery; this route adds an OAuth client and a refresh token, kept in the
  environment's secrets like the R2 keys. No service accounts: YouTube does
  not support them (https://developers.google.com/youtube/v3/docs/errors).
- The API returns the track in a format we choose (`tfmt`: sbv, scc, srt, ttml,
  vtt); **not** json3. A small converter to json3 (or teaching `read_words`
  vtt, which it does not read today: a `.vtt` alone is classed "failed") is
  needed, and its words' times must be proven against the json3 the laptop
  gets for the same recording.
- Developer Policies III.E.4 (storing API data past 30 days without refresh)
  — **unverified** whether caption text counts; the site never shows the
  words, only the moment, which helps, but it should be asked.
  https://developers.google.com/youtube/terms/developer-policies

### B. The state supplies the files

The House and Senate stream to their own YouTube channels; no other public
source of the recordings was found (search results only; gc.nh.gov not
fetched). Whether the chambers keep original recordings is **unverified**. An
ask could be: a periodic caption export run by their IT, or audio files on
request, which we transcribe (route F's transcription half, without the
proxy). Same politics as A, and it also clears the backlog.

### C–E. Asking YouTube from somewhere else

- youtube-transcript-api's own README: "YouTube has started blocking most IPs
  that are known to belong to cloud providers"; it recommends rotating
  residential proxies; cookie authentication currently broken.
  https://github.com/jdepoix/youtube-transcript-api
- yt-dlp subtitle requests on the web client need a PO token, which "does not
  guarantee bypassing 403 errors or bot checks".
  https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide ·
  https://github.com/Brainicism/bgutil-ytdlp-pot-provider
- VPSs are datacenter IPs and report the same failure (Render, AWS,
  PythonAnywhere threads). Cloudflare Workers egress: **unverified**.
- A residential proxy works most of the time for a few dollars
  (https://www.webshare.io/pricing), but it is automated access YouTube's
  Terms forbid (https://www.youtube.com/static?template=terms), on a civic
  site whose standing is its record. Not recommended.

### F. Transcribing ourselves

Transcription is cheap; the audio is the problem — getting it from YouTube is
the same blocked step and breaks Developer Policies III.E.1 and III.I.7.

| Service | Price | ~40 h/month | Word times |
|---|---|---|---|
| Cloudflare Workers AI whisper-large-v3-turbo | $0.0005/min | ~$1.20 (likely $0 inside the free daily allowance) | **unverified** |
| AssemblyAI Universal-2 | $0.15/h | ~$6 | yes (`words`, ms) |
| Deepgram Nova-3 | $0.0043/min | ~$10 | yes |
| OpenAI whisper-1 | $0.006/min | ~$14 | yes, but whisper-1 retires 26 Feb 2027 |
| faster-whisper on a CPU VPS (small, int8) | €6+ server | ~5 h of compute | yes |

Sources: https://developers.cloudflare.com/workers-ai/platform/pricing/ ·
https://www.assemblyai.com/pricing · https://deepgram.com/pricing ·
https://developers.openai.com/api/docs/pricing ·
https://github.com/SYSTRAN/faster-whisper

`src/fetch/youtube/transcribe_and_align.py` already runs faster-whisper
(`--source whisper`), but with `word_timestamps=False`, writing line-level
`transcript.json`, and it takes its audio from YouTube too.

None of these has been scored against `review/ground_truth.csv`. A different
recogniser hears different words: the chair's phrases `segment_markers` looks
for ("the chair will open the hearing on …") may come out differently, which
could move timestamps either way. That is what the timestamp bar is for.

## Recommendation

1. **Ask the House and Senate for route A** (or B): a channel role for a
   project Google account, for the official captions API. It is the only route
   inside YouTube's Terms, it costs nothing, and it also covers the backlog
   (with a quota raise). The owner, as a member, is the right person to ask;
   the ask is one paragraph (below). Until it is answered, the laptop stays.
2. **Prove it before relying on it:** once a role is granted, one authorised
   `captions.list` + `captions.download` on a recording the laptop already
   captioned answers both unverified points; a converter to json3 is then
   proven word-for-word against the laptop's file, and a week of both routes
   is scored with `probe_alignment.py --truth` (median must not regress).
3. **Make a laptop miss visible sooner, at no risk**: the night already warns
   when the inbox is 48 h stale (`nightly.LAPTOP_RUN`); that stays the
   fallback signal.
4. **Do not** adopt residential proxies or self-downloaded audio (routes D–F
   as built on YouTube): cheap, but outside YouTube's Terms, and a civic
   record should not rest on a workaround it would have to defend.

### The ask, as a draft

> Granite Record (graniterecord.org) links each bill to the moment in the
> House's or Senate's YouTube recording where its hearing began. We find that
> moment from the recording's automatic captions, which we never publish.
> Would the [House/Senate] grant our project's Google account the channel's
> Subtitle Editor (or Viewer-with-captions) role, so that we can read those
> caption files through YouTube's official API rather than by other means?
> We ask nothing else of the channel and change nothing on it.

## What this needs from the owner

- Route A/B: sending the ask; later, one OAuth consent on a project Google
  account; the OAuth client secret and refresh token added to the cloud
  environment's secrets (never the repository).
- Nothing else until then.
