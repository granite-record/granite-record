#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-25.10
"""
New livestreams, every night: the recordings the House and Senate channels
finished since the last run, indexed and captioned, and read into the start
times the site publishes -- by the night alone, with no laptop in the loop.

    python3 src/ops/livestreams.py --since-state   the nightly step, before build_all
    python3 src/ops/livestreams.py --markers       build_all's step after the chair's
                                                   boundaries: this step's recordings
                                                   read, scored, and kept
    python3 src/ops/livestreams.py --catch-up      on the laptop, by hand: asks YouTube
                                                   from there and reads what it gets
                                                   into the laptop's own files; sends
                                                   nothing anywhere
    python3 src/ops/livestreams.py --status        what the state says; asks nothing
    python3 src/ops/livestreams.py --carry         the files carried between nights

WHAT IT ASKS, AND WHOM

Two of YouTube's hosts, and nothing of the General Court's:

  googleapis.com, the YouTube Data API, with the key in YOUTUBE_API_KEY. The
  key reaches this script as that environment variable and no other way --
  not a flag, which any process on the machine can read, and not a file. A
  night is one playlistItems.list page per channel, the newest fifty uploads,
  and, when anything is new or still to air, one videos.list call for the
  start, end and length of up to fifty recordings: two or three units on an
  ordinary night, and twenty at the very most -- four pages a channel and the
  calls to cover them -- against the 10,000 a project is given a day.
  channels.list is asked once per channel, ever, for its uploads playlist,
  which the state then remembers.

  youtube.com, for the captions, through yt-dlp: auto-captions, json3, no
  audio, and ONE caption track to a recording -- `en`, the file every reader
  here tries first. fetch_archive_captions.py, which this once copied, asks
  for `en.*`, and that is two caption requests a recording for one track:
  yt-dlp lists a recording's own captions under `en` and again under
  `en-orig`, from the same address, and all 4,265 recordings in work/ on
  1 October 2026 held both files (300 compared, 300 identical). `en-orig` is
  asked for only when `en` is not there, and only at a recording's last ask,
  a week after its stream, before it is taken to have no captions at all.

  One recording at a time, one to two minutes apart, with yt-dlp's own pauses
  between the requests inside one recording (--sleep-requests,
  --sleep-subtitles). On 30 September 2026 the laptop asked twenty seconds
  apart, two tracks a recording, and YouTube answered the second recording
  with "HTTP Error 429: Too Many Requests".

  With a JavaScript runtime (10 October 2026). yt-dlp 2026.08.19 enables
  only deno by default, which neither machine has, and without a runtime it
  reads YouTube with one fallback client and warns that "YouTube extraction
  without a JS runtime has been deprecated, and some formats may be
  missing". So every ask names node (--js-runtimes node; the night sets up
  Node 24 before this step), and the night installs the challenge solver
  yt-dlp names in its own metadata, yt-dlp-ejs, pinned beside it. Whether
  this is why YouTube refuses either machine is not known: it is the one
  thing wrong on this side the disk showed, and it costs nothing. What the
  run had -- yt-dlp's version, node's, the solver's -- goes into the state's
  last_run, so a refusal can be read against the setup that met it.

  yt-dlp's warnings were never seen: --no-warnings hid them, among them the
  two that say a track was discarded for want of a token. They are now kept
  -- and kept OUT of how an answer is read, which is exactly what it was
  under --no-warnings: a warning that mentions an HTTP error on a request
  yt-dlp retried is not the answer. They go to logs/youtube-<day>.log, with
  everything yt-dlp said about an ask that brought no captions. The night
  sends that file to the bucket with its other logs; nothing of it goes to
  the run's public page, where only the outcome line is printed.

HOW MUCH A RUN ASKS FOR

What is waiting, up to twenty recordings asked for the first time
(--max-captions): two on a quiet evening, twenty in session, and the pauses
the same either way. A fixed six, which this had for a day, does not keep up.
By the date in their titles the two channels finished 6.0 recordings a weekday
from 5 January to 31 March 2026, 23 of the 54 days with any brought more than
six, and the busiest day on record, 18 February 2025, brought 23.

Replayed against every recording of 2025 and of 2026, one run an evening, the
evening after the night that lists it -- so no wait can be under a day and a
quarter -- and counting from the end of the stream:

                    recordings   worst wait   waited 3 days or more
  six a run, 2025          814     9.3 days                     394
  six a run, 2026          610     6.3 days                     247
  up to twenty, 2025       814     2.2 days                       0
  up to twenty, 2026       610     1.5 days                       0

Under twenty, two recordings in the two years missed their first evening: the
last two of 18 February 2025. 2021 to 2024 replay the same way: nothing waits
three days.

The longest run is twenty recordings asked for the first time and two asked
again: 22 caption requests, or 24 if both of the two are at their last ask;
21 pauses of one to two minutes, 23 with those; and inside each recording
yt-dlp's own requests for the page, a second and a half apart -- three or
four, by a reading of its 2026.08.19 source: the watch page, the player script
unless it has it, and its two default clients. Some 110 requests of
youtube.com at most, over about forty minutes and under an hour. The 22 and
the pauses are this file's own; the three or four, and the twenty seconds a
recording is taken to need inside yt-dlp, are estimates and not measurements.
--budget, sixty minutes, ends a run that is taking longer, whatever the
reason.

That is the longest whatever is due, because what a run may ask is counted
in caption requests and not in recordings. The recordings asked again take
the requests the new ones leave of the twenty, and one at its last ask is
two of them; only the two that ride on top are outside the count. Counted
in recordings, as it was for a day, an evening with nothing new and twenty
recordings a week old to ask again made forty requests. It makes twenty
now, for ten of them, and the other ten wait for the next run.

Nothing on this disk says YouTube will answer twenty in an evening at this
pace; six was the size the pacing was agreed at. So twenty is what a run works
up to: see A REFUSAL.

A RECORDING WITHOUT CAPTIONS

Some never get them: 127 of the 3,490 in archive/captions.json. One asked
for and found without captions is not asked first again. It goes behind
every recording that has not been asked yet; it is asked again a day later,
then two, four and eight days after that; and those asks are on top of what
the run was going to ask for, never out of it -- two a run at least, however
much else is waiting. A week after its stream, at its second ask or later,
it is asked for both tracks and then taken to have none.

With six a run and the oldest first, six such recordings filled every run for
good: replayed, 107 recordings of 2022 and 117 of 2024 were never asked for
at all, behind the nine without captions of 16 to 19 May 2022 and the seven
of 4 and 5 June 2024.

The same goes for any answer that is not captions and not a refusal -- a
failure, a recording gone private. The laptop's by-hand --catch-up cannot
write the night's state and would otherwise open every run with the same
one, so it keeps count itself, in archive/youtube.refused.json, and after
five such answers stops asking.

A recording is taken to have none, or given up on, only by a run that
captioned something. "No captions" is also what yt-dlp says when it could
not get at them: it discards tracks YouTube wants a token for, and says so
in a warning this step does not see. So a run in which three recordings or
more answer "no captions" at their first ask, and nothing is captioned, is
not a normal night. It is read as a refusal that did not say so: the hold
below starts, nothing is taken to have none, and the run after the hold
stops at its third such answer if it has captioned nothing by then. Replayed
with a fortnight of nothing but "no captions" in February 2026, that is 5
requests the first evening and 3 at each of four runs after it, 17 in all,
where six a run made 150.

While a refusal stands -- the last thing YouTube gave this machine was one,
said or not, and nothing has been captioned since -- a run is wary, and two
things are different.

A "no captions" from a recording asked before counts toward that third
answer too, unless the recording has already said it in a run that captioned
something. That run showed YouTube was answering this machine, so the answer
was the recording's own, and its saying so again is what was expected. One
that has only ever said it in runs that captioned nothing has shown nothing
yet. Without this a run made only of such recordings was never stopped and
never read as anything: on a copy of the laptop's state of 1 October 2026
with every answer "no captions", 38 requests in a run, exit 0, with seven
refusals in a row on the record.

And each recording is asked for one track, `en`, and none is taken to have
no captions: the second track is for the run that closes a recording, and a
wary run is not one.

Replayed with a 429 on each evening of 2021 to 2026 in turn, the worst wait
and the number of recordings waiting three days or more are what they were
before, on every evening of every year. Counting every "no captions" a wary
run heard, vouched for or not, was tried first and did cost: after a 429 on
17 January 2022 the next evening had nothing new and seven recordings due
again that really had no captions; they renewed the hold twice, and 34
recordings waited three days or more where two had.

WHAT AN API KEY CAN AND CANNOT DO

It can list a public channel's uploads and read each video's title, when it
was published, whether it is upcoming, live or over, when it was scheduled,
when it actually started and ended, and how long it is. That is all the video
index holds.

It cannot fetch a caption. captions.list and captions.download both need
OAuth, and captions.download needs "permission to edit the video" -- the
channel owner's, not this project's -- at 200 units a call. So captions come
the way they always have, through yt-dlp, and the key plays no part in it.

WHAT IT WRITES, AND NOTHING ELSE

  videos_house_livestreams.csv    the video index's rows for recordings the
  videos_senate_livestreams.csv   committed collected/videos/videos_*.csv do
                                  not carry, or carry
                                  from before they aired. The twelve columns
                                  fetch_channel_index.py writes, made by its own
                                  title parser. At the root, where the kit
                                  carries them and git never does; every
                                  reader takes these and the committed ones
                                  (proceedings.video_indexes) and takes the
                                  chamber from the file's name.
  work/<video>/captions*.json3    where segment_markers and caption_span look.
  candidate_segments.json         by --markers: what the chair said where, for
  caption_spans.json              this step's recordings, merged in; and where
                                  their captions stop. The night's files in
                                  the kit since 10 October 2026.
  archive/livestreams.json        what it has seen, what it waits for, and any
                                  refusal still in force; and what --markers
                                  read, and how the guard judged it.
  logs/youtube-<day>.log          yt-dlp's warnings, and what it said about an
                                  ask that brought no captions.
  archive/youtube.refused.json    on the laptop only, by --catch-up: YouTube's
                                  refusal of that machine, and what it asked
                                  for and got no captions: how often, when it
                                  asks again, and which it has stopped asking.

Never a committed file: on GitHub's machine a changed tracked file stops the
deploy, and nobody commits there.

WHAT TURNS THEM INTO TIMESTAMPS

build_all.py --local, which the night runs next. build_manifest and
build_floor_index read the new rows and build_proceedings writes the table;
then `livestreams.py --markers`, a step of its own, runs segment_markers over
this step's recordings and nothing else, and puts where each one's captions
stop into the caption summary. Both merge, so every other recording keeps the
answer it had, and build_site_v2 publishes the lot. On the laptop step 15 has
read these already and --markers finds them in its cache; on GitHub's
machine step 15 does not run, and --markers is how a new recording gets its
times. The late-caption check reads the caption file where there is one, and
that night it is there.

THE NIGHT KEEPS WHAT IT READS (10 October 2026)

candidate_segments.json and caption_spans.json are the night's files in the
kit (cloud_kit.json): kit-down brings last night's, --markers adds tonight's
recordings, kit-up sends them back. Until then they were the laptop's -- its
evening job captioned what the night could not and sent them -- so a reading
the night made travelled in the state instead and was put back each night
until the laptop had read the recording itself. The evening job was switched
off on 8 October 2026: YouTube had answered it with a 429 every evening since
30 September, and it had once sent a laptop build's reading into the kit. A
reading an older night still carries in the state is folded into the files
by the next --markers, once, and carried no longer.

A recording counts as read when the caption summary names it and
candidate_segments.json does too -- or when no proceeding names it, so there
is nothing to read it against yet (a study commission's meeting). One the
docket later schedules something on is asked for again, because its captions
did not stay on the machine that read it. `--carry` lists the three small
files of this step's own that the bucket must keep: the state and the two
row files.

THE GUARD, BEFORE ANY TIME READ HERE GOES OUT

CLAUDE.md: nothing about timestamps goes on the site before
`probe_alignment.py --truth --candidate candidate_segments.json` has been run
and the median has not regressed. --markers keeps copies of both files before
it reads, and after it reads it asks two things. Did any entry but tonight's
recordings change? And does the probe, against the hand-timed proceedings,
place as many as the copy did, with a median no worse? Either answer wrong,
or a probe that would not run, and both files are put back as they came
down: tonight's readings go nowhere, the recordings are asked for again on a
later night (three times at most), the state says why, and the night's
verdict warns. The rest of the night publishes as usual. The night reads new
recordings and none of them is hand-timed, so this should never fire; it is
there for a change to the code that slips through, which is where a quiet
regression would otherwise go out every night. It cannot judge a better or
worse pattern -- the night never re-reads a hand-timed recording -- and does
not try to.

A REFUSAL

YouTube refusing a caption request stops the captions for that run and is
recorded; the recording waits. Nothing more is asked of YouTube from that
machine for twelve hours, so its next night opens with one request, the
oldest recording waiting, and goes on only if that one is answered. Each
refusal in a row doubles the wait: a day, two, four, then a week -- each of
those two hours short, because a run comes round a day later to the minute
or the second and never exactly, and a hold of a whole day would be one day
or two by that accident. Inside a hold nothing is asked at all, and nothing
is ever asked again in the same run. The laptop's by-hand --catch-up keeps
its own record: a refusal is about an address, and the two machines have
different ones.

The run after a refusal is also a small one: six new recordings at most, or
half of what the refused run had been answered if that is more. Each run
that then ends without a refusal lets the next ask for two more, until
twenty is the ceiling again. A refusal is the only measure of "too much"
YouTube gives, so it is used as one. A run of nothing but "no captions" read
as a refusal sets no size of its own and keeps the one in force: the small
run a refusal in words called for is still owed when the hold after it ends.

THE DATA CENTRE RISK

YouTube often answers a data centre's address -- GitHub's among them -- with
"Sign in to confirm you're not a bot", and it has answered every caption the
night asked for since 26 September 2026 that way. That is read as a refusal,
not a failure: the recording waits under the hold above, its index row and
the schedule's start still reach the site, marked approximate, nothing
already published changes, and the night goes on and publishes. The night's
verdict counts what waits and says why -- YouTube's refusal of GitHub's
machine, and until when nothing is asked -- and warns once a recording has
waited three days. That is the fallback, and it is what the site showed all
along: approximate starts for new recordings, and every recording already
read keeps its times. Getting past the refusal from GitHub's address (a
newer yt-dlp, or a route that costs money) is a person's decision, not
something this step tries by itself.

A NEW TERM RUN ASKS FOR NO CAPTIONS

The night a term turns over is the longest run there is, and the workflow's
NEW_TERM, which every step of it inherits, says it is that night. This step
then lists what is new as on any night -- two or three API units -- and asks
YouTube for nothing: what waits is asked for by the next scheduled night.

EXIT STATUS

  0  done: nothing new, or everything new handled, deferrals included -- the
     last line always begins LIVESTREAMS: and says which
  1  broken: the state could not be read, or a file could not be written.
     Every file written is whole.
  3  not configured: no YOUTUBE_API_KEY or the API refused the key itself, so
     nothing new was listed -- what was already waiting was still captioned;
     or yt-dlp is not installed, so no caption was asked for and nothing
     counted against a recording.

WITHOUT THE NETWORK

--replay DIR answers every API call from recorded responses and fails any it
has no answer for; --record DIR keeps real ones, never the key. --captions-from
DIR takes a recording's captions from DIR/<video>/ instead of asking YouTube,
and DIR/<video>/ERROR.txt stands for what yt-dlp would have said. preflight
runs the step on fixtures that way.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import hashlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

# The index's own parser and channel list. One reader of a title: a row made
# here has to be the row fetch_channel_index.py would have written. Importing
# it asks nothing; its main() is never called.
import fetch_channel_index as FCI

STATE = Path("archive/livestreams.json")
LOCK = Path("archive/livestreams.lock")
# The laptop's own record of YouTube refusing it, under archive/ with the
# General Court's: local, never carried.
LAPTOP_REFUSAL = Path("archive/youtube.refused.json")
# In that file, beside the refusal: {video: {...}} for each recording this
# machine asked for and got no captions -- how many such answers counted,
# when it is asked again, whether a run that captioned something has heard
# it say so ("vouched"), and "closed" once it is no longer asked.
ASKED = "asked"
WORK = Path("work")
MARKERS = Path("candidate_segments.json")
# yt-dlp's warnings and what it said about an ask that brought no captions,
# by the machine's own day; the night's kit-up sends logs/* to the bucket.
YT_LOG = "logs/youtube-{day}.log"
# The workflow's word that tonight is the New term run (nightly.yml's env,
# which every step inherits): no captions are asked for on it.
NEW_TERM_ENV = "NEW_TERM"

CHANNELS = {c: cid for c, (cid, _name) in FCI.CHANNELS.items()}
# fetch_channel_index.main's columns, in its order; preflight reads that file
# and holds the two together.
COLS = ["video_id", "title", "title_parsed", "parsed_committee", "parsed_date",
        "date_from", "has_start_time", "start_eastern", "actual_start_utc",
        "actual_end_utc", "duration_iso", "published_at"]
# Quota units per call, from the API's own table. Nothing that costs more --
# search.list at 100, the caption methods at 50 and 200 -- is ever called.
COST = {"channels": 1, "playlistItems": 1, "videos": 1}

# yt-dlp, as fetch_archive_captions.fetch runs it but for the pauses and the
# track: --sub-langs is added to each ask by ytdlp_args, one track and no
# wildcard. The two pauses are yt-dlp's own, inside one recording: between
# the requests it makes to read the page, and before it asks for the caption
# file. Twice what its own "sleep" preset uses (0.75 and 5); a judgment, not
# a measured threshold -- YouTube publishes none. A JavaScript runtime, node,
# which yt-dlp does not use unless named (WHAT IT ASKS); and no --no-warnings:
# the warnings are split off and logged (split_warnings), never read.
YTDLP = ["-m", "yt_dlp", "--write-auto-subs", "--sub-format", "json3/vtt",
         "--skip-download", "--js-runtimes", "node",
         "--sleep-requests", "1.5", "--sleep-subtitles", "10"]
# The challenge solver that --js-runtimes needs, by its package's name: yt-dlp
# names the version it wants in its own metadata, and the night pins it.
SOLVER = "yt-dlp-ejs"
# The two minutes past BUDGET the last recording of a run can take, every
# pause at its longest: its pause, two tracks at --timeout each and the pause
# between them. The night's step allows BUDGET and this, and a little more.
LAST_ASK_MINUTES = 14
# The caption tracks, in the order they are asked for and ONE to an ask.
# yt-dlp matches --sub-langs as a whole-name pattern, so `en` is that track
# and not `en-orig` with it. `en.*` matched both, and both are the same
# captions: its YouTube extractor lists a recording's own track under the
# plain name and again with "-orig", from one address.
CAPTION_TRACKS = ["en", "en-orig"]
# The caption files segment_markers.read_words and caption_span.last_cue read,
# in the order they try them: the file each track above arrives as.
CAPTION_FILES = ["captions.en.json3", "captions.en-orig.json3"]

MAX_PAGES = 4          # pages of fifty uploads, per channel per night
LOOKBACK_DAYS = 14     # how far behind the last run a page may reach
NONE_YET_DAYS = 7      # auto-captions can lag a stream; this long after it,
                       # ask once more, for every track, and take it to
                       # have none
MAX_TRIES = 3          # failures that are not refusals, or readings not
                       # kept, then left for a person ("for-laptop")
PENDING_DAYS = 30      # past its scheduled time, an unaired stream never aired
STALE_DAYS = 60        # a pre-air committed row this near today is rechecked
PRUNE_DAYS = 60        # settled entries leave the state after this
HOLD_HOURS = 12        # after one refusal: nothing more that night; the next
                       # one opens with a single request. Doubles: 24, 48, 96
HOLD_MAX = 168         # the longest hold, a week
EARLY_HOURS = 2        # a wait of a day or more ends this much short of it:
                       # the run a day later starts seconds or minutes off
                       # the last one's time, and must find the wait over
MAX_CAPTIONS = 20      # the most recordings one run asks for the first time;
                       # up to that, a run asks for whatever is waiting
AFTER_REFUSAL = 6      # ...but after a refusal, this many -- the size a run
                       # had when the pacing was agreed -- or half of what
                       # the refused run had been answered, if that is more
EASE = 2               # and this many more after each run without one
AGAIN_MIN = 2          # recordings asked AGAIN in a run, at least, on top of
                       # those: a retry never takes a new recording's place
RETRY_DAYS = (1, 2, 4, 8)  # after an ask that brought no captions, how long
                       # before the next: a day, then two, four, and eight
CLOSE_ASKS = 2         # a recording is taken to have no captions at its
                       # second ask or later, never at its first
GIVE_UP_ASKS = 5       # asks before the laptop stops asking for one that
                       # keeps failing, or is gone: 15 days of them
ALL_NONE = 3           # "no captions" this often in a run that captioned
                       # nothing is a refusal that did not say so
DELAY = 60.0           # seconds between two recordings, at least
JITTER = 60.0          # and up to this many more, so the gaps are not a beat
BUDGET = 60.0          # minutes of caption requests in one run, at most
TIMEOUT = 300.0        # seconds allowed for one track's ask
LOCK_BEAT = 30         # seconds between two touches of a held lock
LOCK_STALE = 300       # a lock untouched this long was left by a run that is
                       # gone: the night's step killed at its time limit

# What yt-dlp says, read the way fetch_archive_captions reads it, plus the one
# answer that script never met: a data centre's bot check, "Sign in to confirm
# you're not a bot". Matched on "not a bot" and not on "sign in to confirm",
# which also opens "Sign in to confirm your age" -- a fact about a video, not
# a refusal of an address.
REFUSED = re.compile(
    r"not a bot|http error 429|too many requests|rate.?limit|captcha|"
    r"try again later|http error 403", re.I)
NOT_AIRED = re.compile(r"live event will begin|premieres in|will begin in|"
                       r"is not currently live", re.I)
GONE = re.compile(r"video unavailable|private video|has been removed|"
                  r"this video is private|no longer available", re.I)
NONE_YET = re.compile(r"no subtitles|no automatic captions|"
                      r"subtitles are not available", re.I)


class Broken(Exception):
    """Something a person has to look at: exit 1."""


# ---------------------------------------------------------------- time --

def utcnow(fixed=None):
    if fixed:
        return datetime.fromisoformat(fixed.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


# --------------------------------------------------------------- files --

def atomic_write(path, text):
    """Whole or not at all. A state file cut off half way is a night that
    decides it has never seen anything, and asks for all of it again."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)


def fresh_state():
    return {"version": 1, "channels": {}, "last_run": {}, "refusals": {},
            "videos": {}}


def load_state(path=STATE):
    """The state, or a fresh one where there has never been one.

    NEVER a fresh one in place of a file that is there and cannot be read.
    Starting over would take every recording on the first page for new and ask
    YouTube for all of their captions at once -- the hammering this file
    exists to prevent. Likewise a state that did not arrive while the rows it
    wrote did: that is a kit that came down short, not a first night.
    """
    p = Path(path)
    if not p.exists():
        ours = [csv_path(c) for c in CHANNELS if csv_path(c).exists()]
        if ours:
            raise Broken(f"{p.as_posix()} is not here but {ours[0]} is: the state did "
                         "not arrive with the rows it wrote. Not starting "
                         "over, which would ask for everything again.")
        return fresh_state()
    try:
        st = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise Broken(f"{p.as_posix()} is there and cannot be read ({e}). Not starting "
                     "over, which would ask for everything again. Restore "
                     "last night's copy, or move this one aside by hand.")
    if not isinstance(st, dict) or not isinstance(st.get("videos"), dict):
        raise Broken(f"{p.as_posix()} is not a livestreams state file.")
    base = fresh_state()
    base.update(st)
    return base


def save_state(st, path=STATE):
    atomic_write(path, json.dumps(st, indent=1, sort_keys=True) + "\n")


# ---------------------------------------------------------------- rows --

def csv_path(chamber):
    return Path(f"videos_{chamber}_livestreams.csv")


def chamber_of_path(p):
    # build_manifest.load_videos's rule, and build_floor_index's.
    return "senate" if "senate" in str(p).lower() else "house"


def read_rows(files=None):
    """{video_id: [(file name, row), ...]} across every index on disk: the
    committed ones in collected/videos/ and this step's own at the root
    (proceedings.video_indexes), or `files`."""
    import proceedings
    out = {}
    for f in (proceedings.video_indexes() if files is None else files):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("video_id"):
                    out.setdefault(r["video_id"], []).append((f.name, r))
    return out


def rank(row):
    """How much a row knows about its stream -- build_manifest._aired's scale,
    which decides between two rows for one recording: 2 once it has the
    length, which only an ended stream has; 1 with a start and no length,
    written while it was live; 0 with neither, written while it was only
    scheduled."""
    if (row.get("duration_iso") or "").strip() not in ("", "P0D"):
        return 2
    return 1 if (row.get("actual_start_utc") or "").strip() else 0


def make_row(vid, title, published_at, item):
    """The row fetch_channel_index.py writes, from the same answers.

    Its main() builds the row inline; the statements below follow it one for
    one, and preflight checks the result against every row it has written.
    """
    live = (item or {}).get("liveStreamingDetails", {}) or {}
    v = {"video_id": vid, "title": title, "published_at": published_at,
         "actual_start_utc": live.get("actualStartTime", ""),
         "actual_end_utc": live.get("actualEndTime", ""),
         "duration_iso": ((item or {}).get("contentDetails", {}) or {}).get("duration", "")}
    cmte, d = FCI.parse_title(v["title"])
    if not cmte:
        m = FCI.BILL_TITLE_RE.match(v["title"])
        if m and v.get("published_at"):
            try:
                d = datetime.fromisoformat(
                    v["published_at"].replace("Z", "+00:00")).date()
                cmte = m.group("committee").strip()
                v["date_from"] = "published"
            except ValueError:
                pass
    v["parsed_committee"] = cmte or ""
    v["parsed_date"] = d.isoformat() if d else ""
    v["title_parsed"] = "yes" if cmte else "NO"
    v.setdefault("date_from", "title")
    v["has_start_time"] = "yes" if v["actual_start_utc"] else "NO"
    v["start_eastern"] = FCI.to_eastern_clock(v["actual_start_utc"])
    return {c: v.get(c, "") for c in COLS}


def write_rows(chamber, updates, removals=(), committed=None):
    """Merge rows into one chamber's livestreams file: (added, replaced, dropped).

    Never a rewrite from a subset. A row already there stays unless a newer
    answer about the same recording replaces it, the recording no longer
    exists (`removals`), or a committed index now carries it finished -- in
    which case dropping it here loses nothing. A row is never replaced by one
    that knows less about the stream.
    """
    path = csv_path(chamber)
    have = {}
    if path.exists():
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("video_id"):
                    have[r["video_id"]] = {c: r.get(c, "") for c in COLS}
    before = dict(have)
    added = replaced = dropped = 0
    for vid, row in updates.items():
        old = have.get(vid)
        if old is not None and rank(row) < rank(old):
            continue
        if old is None:
            added += 1
        elif old != row:
            replaced += 1
        have[vid] = row
    for vid in removals:
        if have.pop(vid, None) is not None:
            dropped += 1
    for vid in list(have):
        if vid in (committed or {}):
            del have[vid]
            dropped += 1
    if have == before:
        return 0, 0, 0
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLS, extrasaction="ignore")
    w.writeheader()
    for r in sorted(have.values(), key=lambda r: (r["published_at"], r["video_id"])):
        w.writerow(r)
    atomic_write(path, buf.getvalue())
    return added, replaced, dropped


# ----------------------------------------------------------------- API --

class ApiError(Exception):
    """kind: quota or failed -- try tomorrow; config -- a person's."""

    def __init__(self, kind, why):
        super().__init__(why)
        self.kind, self.why = kind, why


def canonical(endpoint, params):
    q = urllib.parse.urlencode(sorted((k, str(v)) for k, v in params.items()
                                      if k != "key"))
    return f"{endpoint}?{q}"


class Api:
    """The Data API: live, recorded, or replayed.

    Replay answers only what was recorded, keyed on the request with the key
    left out; an unrecorded request is an error, so a test hears about a call
    it did not expect instead of the call quietly working.
    """

    def __init__(self, key=None, replay=None, record=None, timeout=30):
        self.key, self.timeout = key, timeout
        self.replay = Path(replay) if replay else None
        self.record = Path(record) if record else None
        self.units, self.calls, self._index = 0, [], {}
        if self.replay:
            ip = self.replay / "index.json"
            if not ip.exists():
                raise Broken(f"--replay {self.replay}: no index.json there")
            self._index = json.loads(ip.read_text(encoding="utf-8"))

    def get(self, endpoint, **params):
        canon = canonical(endpoint, params)
        self.calls.append(canon)
        self.units += COST.get(endpoint, 1)
        if self.replay:
            name = self._index.get(canon)
            if not name:
                raise ApiError("failed", f"no recorded answer for {canon}")
            doc = json.loads((self.replay / name).read_text(encoding="utf-8"))
            if isinstance(doc, dict) and "error" in doc:
                raise api_error(int(doc.get("_status") or 400), json.dumps(doc))
            return doc
        if not self.key:
            raise ApiError("config", "no YOUTUBE_API_KEY")
        url = (FCI.API + endpoint + "?"
               + urllib.parse.urlencode({**params, "key": self.key}))
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as r:
                body = r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            # The body's reason and nothing else: the exception's own text and
            # its .url carry the address, and the address carries the key.
            try:
                text = e.read().decode("utf-8", "replace")
            except Exception:                                   # noqa: BLE001
                text = ""
            raise api_error(e.code, text)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ApiError("failed", "could not reach the API: "
                           + str(getattr(e, "reason", "") or type(e).__name__))
        if self.record:
            self._save(canon, body)
        return json.loads(body)

    def _save(self, canon, body):
        if self.key and self.key in body:
            raise Broken("an API answer carried the key; not recording it")
        self.record.mkdir(parents=True, exist_ok=True)
        ip = self.record / "index.json"
        idx = json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else {}
        name = (canon.split("?")[0] + "-"
                + hashlib.sha1(canon.encode()).hexdigest()[:10] + ".json")
        (self.record / name).write_text(body, encoding="utf-8")
        idx[canon] = name
        ip.write_text(json.dumps(idx, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8")


def api_error(code, text):
    """One reading of the API's refusals. Google's error names a reason, and
    the reason, not the status, says whether tomorrow will be different."""
    reasons, message = [], ""
    try:
        err = json.loads(text).get("error", {}) or {}
        message = str(err.get("message") or "")
        reasons = [str(x.get("reason") or "") for x in err.get("errors") or []]
        reasons += [str(d.get("reason") or "") for d in err.get("details") or []
                    if isinstance(d, dict)]
    except (ValueError, AttributeError):
        message = text[:200]
    blob = " ".join(reasons + [message]).lower()
    short = f"HTTP {code}: " + (", ".join(r for r in reasons if r) or message[:120])
    if any(k in blob for k in ("quotaexceeded", "dailylimitexceeded",
                               "ratelimitexceeded", "userratelimitexceeded")):
        return ApiError("quota", short + " -- the day's quota, which resets at "
                        "midnight Pacific")
    if code in (400, 401, 403) and any(k in blob for k in (
            "keyinvalid", "api key not valid", "accessnotconfigured",
            "has not been used", "api_key", "blocked", "referer", "forbidden",
            "permission")):
        return ApiError("config", short + " -- the key itself was refused. It "
                        "must be a YouTube Data API v3 key, restricted to that "
                        "API and not to one address or website")
    if code == 404:
        return ApiError("config", short + " -- a channel or its uploads "
                        "playlist was not found")
    return ApiError("failed", short)


# ------------------------------------------------------------- listing --

def uploads_playlist(api, st, chamber):
    ch = st["channels"].setdefault(chamber, {})
    ch["id"] = CHANNELS[chamber]
    if not ch.get("uploads"):
        items = api.get("channels", part="contentDetails",
                        id=CHANNELS[chamber]).get("items") or []
        if not items:
            raise ApiError("config", f"no channel {CHANNELS[chamber]}")
        ch["uploads"] = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    return ch["uploads"]


def list_uploads(api, st, chamber, known, floor, max_pages=MAX_PAGES):
    """[(video_id, title, published_at)] from the newest uploads, newest first.

    The next page is read only while this one held something new and reached
    no further back than `floor`. The uploads playlist runs in publish order,
    and a stream scheduled weeks ahead is published when it is scheduled, so
    "stop at the first id already known" stops too soon. "Stop at a page with
    nothing new on it" does not.
    """
    pl = uploads_playlist(api, st, chamber)
    out, token, pages = [], None, 0
    while pages < max_pages:
        params = {"part": "contentDetails,snippet", "playlistId": pl,
                  "maxResults": 50}
        if token:
            params["pageToken"] = token
        page = api.get("playlistItems", **params)
        pages += 1
        new, oldest = 0, None
        for it in page.get("items") or []:
            cd = it.get("contentDetails") or {}
            sn = it.get("snippet") or {}
            vid = cd.get("videoId") or (sn.get("resourceId") or {}).get("videoId")
            title = sn.get("title") or ""
            if not vid or title in ("Private video", "Deleted video"):
                continue
            pub = cd.get("videoPublishedAt") or sn.get("publishedAt") or ""
            out.append((vid, title, pub))
            new += vid not in known
            when = parse_iso(pub)
            if when and (oldest is None or when < oldest):
                oldest = when
        token = page.get("nextPageToken")
        if not token or not new or (floor and oldest and oldest < floor):
            break
    return out


def video_details(api, ids):
    """{video_id: item}, fifty to a call -- one unit however many there are."""
    out, ids = {}, sorted(set(ids))
    for i in range(0, len(ids), 50):
        data = api.get("videos", part="snippet,contentDetails,liveStreamingDetails",
                       id=",".join(ids[i:i + 50]))
        for it in data.get("items") or []:
            out[it["id"]] = it
    return out


def status_of(item):
    """upcoming | live | finished | never, from the API's own fields.

    A broadcast that has ended can go on reporting P0D for a while as YouTube
    processes it; it is kept as live and asked about again rather than taken
    for finished with no length. One that is over and never started was
    cancelled.
    """
    sn = item.get("snippet") or {}
    live = item.get("liveStreamingDetails") or {}
    lbc = sn.get("liveBroadcastContent") or "none"
    if lbc in ("upcoming", "live"):
        return lbc
    if (item.get("contentDetails") or {}).get("duration") not in (None, "", "P0D"):
        return "finished"
    if live.get("actualStartTime") or live.get("actualEndTime"):
        return "live"
    return "never"


def wants_captions(row, item):
    """A finished livestream, or an upload whose title the index could match
    to a proceeding. A four-minute film about the dome is neither."""
    if (item or {}).get("liveStreamingDetails"):
        return True
    return row.get("title_parsed") == "yes"


def discover(api, st, rows, now, max_pages=MAX_PAGES):
    """Ask, and turn the answers into rows and state.

    Returns (counts, {chamber: {video: row}}, {chamber: {video to remove}}).
    What is asked about: every upload newer than anything known, whatever this
    step is still waiting on to air or to finish, and any committed row that
    was written before its stream happened -- four such rows, of 14 to 18
    September, were in the index on 25 September, and their recordings had
    no start, no length, and so no predicted offset and no caption check.
    """
    known = set(rows) | set(st["videos"])
    last = parse_iso((st.get("last_run") or {}).get("at"))
    counts = Counter()
    updates = {"house": {}, "senate": {}}
    removals = {"house": set(), "senate": set()}
    listed, fresh = {}, {}
    for chamber in ("house", "senate"):
        if last:
            floor = last - timedelta(days=LOOKBACK_DAYS)
        else:
            pubs = [parse_iso(r.get("published_at")) for fr in rows.values()
                    for f, r in fr if chamber_of_path(f) == chamber]
            pubs = [p for p in pubs if p]
            floor = max(pubs) - timedelta(days=LOOKBACK_DAYS) if pubs else None
        for vid, title, pub in list_uploads(api, st, chamber, known, floor,
                                            max_pages):
            listed[vid] = (title, pub)
            if vid not in known:
                fresh[vid] = chamber

    ask = {vid: v["chamber"] for vid, v in st["videos"].items()
           if v.get("status") in ("upcoming", "live")}
    for vid, fr in rows.items():
        if vid in st["videos"] or max(rank(r) for _, r in fr) == 2:
            continue
        f, r = fr[0]
        if (r.get("duration_iso") or "") != "P0D":
            continue
        when = parse_iso(r.get("published_at"))
        try:
            day = datetime.strptime(r.get("parsed_date") or "", "%Y-%m-%d")
            day = day.replace(tzinfo=timezone.utc)
        except ValueError:
            day = when
        if day and abs((now - day).days) <= STALE_DAYS:
            ask[vid] = chamber_of_path(f)
    ask.update(fresh)
    items = video_details(api, ask) if ask else {}

    for vid, chamber in sorted(ask.items()):
        it = items.get(vid)
        v = st["videos"].get(vid)
        if it is None:
            # Not returned: deleted, or private. A row this step wrote for it
            # goes; a committed row is not this step's to touch.
            if v is None:
                st["videos"][vid] = {"chamber": chamber, "status": "gone",
                                     "seen": iso(now),
                                     "title": listed.get(vid, ("", ""))[0]}
            else:
                sched = parse_iso(v.get("scheduled"))
                if sched and now - sched < timedelta(days=PENDING_DAYS):
                    continue
                v["status"] = "gone"
            removals[chamber].add(vid)
            continue
        sn = it.get("snippet") or {}
        live = it.get("liveStreamingDetails") or {}
        title = sn.get("title") or listed.get(vid, ("", ""))[0]
        pub = (listed[vid][1] if vid in listed else "") or sn.get("publishedAt") \
            or (rows[vid][0][1].get("published_at") if vid in rows else "")
        row = make_row(vid, title, pub, it)
        status = status_of(it)
        if v is None:
            v = st["videos"][vid] = {"chamber": chamber, "seen": iso(now)}
        if vid in fresh:
            counts["new"] += 1
        was = v.get("status")
        v.update(title=title, status=status,
                 scheduled=live.get("scheduledStartTime") or v.get("scheduled"),
                 ended=live.get("actualEndTime") or v.get("ended"))
        sched = parse_iso(v.get("scheduled"))
        if status == "never" or (status == "upcoming" and sched
                                 and now - sched > timedelta(days=PENDING_DAYS)):
            v.update(status="gone", why="scheduled and never aired")
            removals[chamber].add(vid)
            continue
        if status in ("upcoming", "live"):
            counts["not yet over"] += 1
        elif was != "finished":
            counts["finished"] += 1
            if v.get("captions") in (None, "not-needed"):
                v["captions"] = "waiting" if wants_captions(row, it) else "not-needed"
        # A committed row that already says as much -- a stream still only
        # scheduled -- is watched, and copied nowhere until there is more.
        committed = [rank(r) for f, r in rows.get(vid, [])
                     if not f.endswith("_livestreams.csv")]
        if committed and rank(row) <= max(committed):
            continue
        updates[chamber][vid] = row
    return counts, updates, removals


# ------------------------------------------------------------ captions --

def yt_dlp_here(a):
    """Whether this machine can ask for captions at all. Without yt-dlp every
    request would fail the same way and each would count against its
    recording; better to say so once and leave them all waiting."""
    if a.captions_from:
        return True
    import importlib.util
    if importlib.util.find_spec("yt_dlp") is None:
        print("  yt-dlp is not installed on this machine, so no captions are "
              "asked for tonight; the recordings wait. The nightly's setup "
              "should pip install yt-dlp at the laptop's version.")
        return False
    return True


def setup():
    """What this machine asks YouTube with: {"yt-dlp", "node", SOLVER}, each a
    version or "" where it is not here. Read from the installed packages and
    node itself; asks nothing. Kept in the state's last_run, so that a
    refusal can be read against the setup that met it."""
    import importlib.metadata as md
    out = {}
    for pkg in ("yt-dlp", SOLVER):
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = ""
    node = shutil.which("node")
    out["node"] = ""
    if node:
        try:
            r = subprocess.run([node, "--version"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=20)
            out["node"] = (r.stdout or "").strip() if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            pass
    return out


def setup_said(s):
    """One line for the log: what a run asks with, and what it lacks."""
    have = f"yt-dlp {s.get('yt-dlp') or '(not installed)'}"
    if not s.get("node"):
        return have + ", and no node: YouTube's challenges go unsolved"
    if not s.get(SOLVER):
        return (have + f", node {s['node']}, and no {SOLVER}: node has no challenge "
                f"solver to run (pip install {SOLVER} at the version yt-dlp names)")
    return have + f", node {s['node']} and {SOLVER} {s[SOLVER]}"


def split_warnings(said):
    """(what yt-dlp said less its warnings, the warnings): each line that
    opens "WARNING:" is one. What is left is exactly what yt-dlp prints
    under --no-warnings, which is what every answer here was read from
    before the warnings were kept."""
    keep, warned = [], []
    for ln in (said or "").splitlines():
        (warned if ln.lstrip().startswith("WARNING:") else keep).append(ln)
    return "\n".join(keep), warned


def log_answer(vid, track, outcome, warned, said, day=None):
    """yt-dlp's warnings about one ask, and everything it said when the ask
    brought no captions, into the day's log. Never on the run's page. A log
    that cannot be written is said once and costs the ask nothing."""
    if not warned and outcome == "captioned":
        return
    path = Path(YT_LOG.format(day=day or datetime.now().strftime("%Y-%m-%d")))
    lines = [f"{iso(datetime.now(timezone.utc))} {vid} {track}: {outcome}"]
    lines += [f"  {ln.strip()}" for ln in warned]
    if outcome != "captioned":
        lines += [f"  | {ln.rstrip()}" for ln in (said or "").splitlines() if ln.strip()]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError as e:
        print(f"  ({path.as_posix()} could not be written: {type(e).__name__})")


def caption_file(vid, work=WORK):
    d = Path(work) / vid
    return next((d / f for f in CAPTION_FILES if (d / f).exists()), None)


def has_captions(vid, work=WORK):
    return caption_file(vid, work) is not None


def classify(rc, said, json3, vtt, readable):
    """(outcome, why): captioned | refused | not-aired | gone | none-yet | failed."""
    if json3 and readable:
        return "captioned", json3
    low = (said or "").lower()
    if REFUSED.search(low):
        line = next((ln for ln in (said or "").splitlines() if REFUSED.search(ln)),
                    said or "")
        return "refused", line.strip()[:200]
    if NOT_AIRED.search(low):
        return "not-aired", "not yet broadcast"
    if GONE.search(low):
        return "gone", "YouTube says the video is not available"
    if json3:
        return "failed", "a caption file arrived with no words in it"
    if vtt:
        return "failed", "only a .vtt arrived, which segment_markers cannot read"
    if NONE_YET.search(low) or rc == 0:
        return "none-yet", "no auto-captions published yet"
    last = [ln for ln in (said or "").strip().splitlines() if ln.strip()]
    return "failed", (last[-1] if last else f"yt-dlp exit {rc}")[:200]


def ytdlp_args(track):
    """yt-dlp's arguments for one ask: one caption track, named outright."""
    if track not in CAPTION_TRACKS:
        raise Broken(f"{track!r} is not a caption track this step asks for")
    return YTDLP + ["--sub-langs", track]


def fetch_captions(vid, work=WORK, source=None, timeout=300, tracks=None,
                   pause=None):
    """One recording's captions into work/<vid>/: (outcome, why).

    One track to an ask. `tracks` is the order to ask in, by default the first
    of CAPTION_TRACKS and nothing else; a later one is asked for only when the
    one before it answered that it is not there, and after `pause()`. Any
    other answer -- captions, a refusal, a failure -- ends it there.

    `source` replays instead of asking: source/<vid>/ holds the files yt-dlp
    would have written, or ERROR.txt with what it would have said.
    """
    outcome, why = "none-yet", "no track was asked for"
    for k, track in enumerate(tracks or CAPTION_TRACKS[:1]):
        if k and pause:
            pause()
        outcome, why = ask_track(vid, track, work, source, timeout)
        if outcome != "none-yet":
            break
    return outcome, why


def ask_track(vid, track, work=WORK, source=None, timeout=300):
    """One ask: one track of one recording. (outcome, why)."""
    args = ytdlp_args(track)
    d = Path(work) / vid
    existed = d.exists()
    d.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in d.iterdir()}
    warned, live = [], not source
    if source:
        s = Path(source) / vid
        rc, said = 0, ""
        if (s / "ERROR.txt").exists():
            rc, said = 1, (s / "ERROR.txt").read_text(encoding="utf-8")
        elif s.is_dir():
            # Only the track asked for, as yt-dlp would write only that one.
            for f in sorted(s.glob(f"captions.{track}.*")):
                shutil.copy2(f, d / f.name)
    else:
        cmd = [sys.executable] + args + [
            "-o", str(d / "captions"), f"https://www.youtube.com/watch?v={vid}"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=timeout)
            rc, said = r.returncode, (r.stderr or "") + "\n" + (r.stdout or "")
        except subprocess.TimeoutExpired:
            rc, said = -1, f"took longer than {timeout:g}s"
        except OSError as e:
            rc, said = -1, f"yt-dlp would not start: {e}"
    # Read as it was read under --no-warnings; the warnings go to the log.
    said, warned = split_warnings(said)
    f = caption_file(vid, work)
    vtt = next(iter(sorted(d.glob("captions*.vtt"))), None)
    readable = False
    if f:
        import segment_markers
        readable = bool(segment_markers.read_words(d))
    outcome, why = classify(rc, said, f.name if f else None, vtt, readable)
    if live:
        log_answer(vid, track, outcome, warned, said)
    if outcome != "captioned":
        # Only what this attempt left: the folder held no captions when it
        # started, so any file in it now that was not there then is its own.
        for p in d.iterdir():
            if p.name not in before and p.is_file():
                p.unlink()
        if not existed and not any(d.iterdir()):
            d.rmdir()
    return outcome, why


class Refusals:
    """A refusal is a fact about an address, so it is kept per machine."""

    def __init__(self, table, origin):
        self.table, self.origin = table, origin

    def record(self):
        return self.table.get(self.origin) or {}

    def held(self, now):
        return now.timestamp() < float(self.record().get("until") or 0)

    def note(self, now, why, silent=False, answered=0):
        """Record a refusal and start the hold: the hours it lasts.

        `silent` is a refusal read off a run of nothing but "no captions",
        which YouTube did not put into words; the record says which.
        `answered` is how many recordings the run had been answered when a
        refusal in words stopped it, which sets how many new ones the runs
        after it may ask for -- see most()."""
        was = self.record()
        n = int(was.get("count") or 0) + 1
        hours = min(HOLD_HOURS * 2 ** (n - 1), HOLD_MAX)
        if hours >= 24:
            hours -= EARLY_HOURS
        rec = self.table[self.origin] = {
            "at": iso(now), "why": why[:200], "count": n,
            "until": now.timestamp() + hours * 3600,
            "until_iso": iso(now + timedelta(hours=hours))}
        if silent:
            rec["silent"] = True
        if not silent:
            rec["most"] = max(AFTER_REFUSAL, answered // 2)
        elif self.small(was):
            # A silent refusal says nothing about how much is too much, so
            # it keeps whatever the record before it allowed: its figure, or
            # the AFTER_REFUSAL an older record without one is read as.
            # Carrying only a figure that was written down lost the second.
            # The laptop's record of its 429 of 30 September 2026 has none,
            # and one evening of "no captions" after it would have let the
            # run after that ask for twenty.
            rec["most"] = self.small(was)
        return hours

    def answered(self):
        r = self.table.get(self.origin)
        if r and r.get("count"):
            r.update(count=0, until=0, until_iso="")

    def most(self, ceiling):
        """The most new recordings a run may ask for: `ceiling`, or fewer
        for a while after a refusal.

        The run after a refusal in words asks for AFTER_REFUSAL, or for half
        of what the refused run had been answered if that is more; each run
        that then ends without a refusal lets the next ask for EASE more,
        until that is the ceiling again. So the larger runs are something
        this works up to and backs down from, not something it insists on.
        The half and the EASE are a judgment: YouTube publishes no limit to
        set them by. A record written before this was kept -- a refusal
        standing, and no figure -- is read as AFTER_REFUSAL."""
        m = self.small(self.record())
        return min(ceiling, m) if m > 0 else ceiling

    @staticmethod
    def small(r):
        """The figure a record holds a run to, or 0 where it holds it to
        none: its own, or AFTER_REFUSAL for a refusal in words recorded
        before a figure was kept. One reading, for most() and for note(),
        which has to carry it past a silent refusal."""
        return int(r.get("most") or 0) or (AFTER_REFUSAL if r.get("count")
                                           and not r.get("silent") else 0)

    def eased(self, was, ceiling):
        """A run that could ask for `was` new recordings, and captioned
        something, ended without a refusal."""
        r = self.table.get(self.origin)
        if r is None or was >= ceiling:
            return
        if was + EASE >= ceiling:
            r.pop("most", None)
        else:
            r["most"] = was + EASE


def week_on(v, now):
    """Whether a recording's stream ended more than NONE_YET_DAYS ago: by then
    its auto-captions are published if they are ever going to be."""
    ended = parse_iso(v.get("ended")) or parse_iso(v.get("seen"))
    return not ended or now - ended > timedelta(days=NONE_YET_DAYS)


def tracks_for(v, now):
    """The caption tracks one ask of this recording may name, in order: the
    first of CAPTION_TRACKS, and the rest as well only at its last ask --
    its stream ended more than a week ago and it has been asked before. The
    length of this is the most caption requests the ask can make."""
    last = week_on(v, now) and int(v.get("asks") or 0) >= CLOSE_ASKS - 1
    return list(CAPTION_TRACKS if last else CAPTION_TRACKS[:1])


def wait(a):
    """The pause between two asks of YouTube: --delay seconds and up to
    --jitter more. A replay asks nobody and waits for nothing."""
    if not a.captions_from:
        time.sleep(a.delay + random.uniform(0, a.jitter))


# What `captions` says of a recording still to be asked for, tonight or later.
WAITING = ("waiting", "deferred", "none-yet", "failed")


def settle(st, now, done, work=WORK):
    """The recordings that need nothing more asked of YouTube: how many.

    One whose reading the caption results already hold (`done`, in_files) --
    read on an earlier night, or by the laptop's caption job while there was
    one -- and one whose captions are already on this disk. EVERY recording
    still waiting is looked at, whether it is due tonight or not, and the
    ones left for a person with them. For a day only the ones due were: a
    recording answered "no captions" here and read elsewhere that evening
    stayed `none-yet` until its turn came round, up to eight days in which
    the night's three-day warning counted it.
    """
    n = 0
    for vid, v in st["videos"].items():
        if v.get("status") != "finished" \
                or v.get("captions") not in WAITING + ("for-laptop",):
            continue
        if done is not None and vid in done:
            v.update(captions="captioned", by=v.get("by") or "files",
                     fetched=v.get("fetched") or iso(now),
                     read=now.strftime("%Y-%m-%d"), why="")
        elif has_captions(vid, work):
            v.update(captions="captioned", by=v.get("by") or "found",
                     fetched=v.get("fetched") or iso(now), why="")
        else:
            continue
        for k in ("tries", "asks", "again", "vouched"):
            v.pop(k, None)
        n += 1
    return n


def allowance(waiting, most=MAX_CAPTIONS):
    """How many recordings one run asks for, of `waiting` that are due: all
    of them, up to `most`. It follows the backlog -- two on a quiet evening,
    `most` in session -- and the pauses between them do not change."""
    return max(0, min(int(waiting), int(most)))


def retry_after(asks):
    """How long after its `asks`-th ask that brought no captions a recording
    is asked again: RETRY_DAYS, each EARLY_HOURS short so that the run that
    many days later finds it due."""
    days = RETRY_DAYS[min(max(asks, 1), len(RETRY_DAYS)) - 1]
    return timedelta(hours=24 * days - EARLY_HOURS)


def caption_queue(st, now, work=WORK):
    """(first, again): the recordings whose captions are due, in two lanes.

    `first` has never been asked for and answered with anything but captions
    or a refusal: oldest stream first. `again` has -- it carries the time it
    may be asked again, and is here once that has passed: longest due first.
    A recording asked for and found without captions is therefore never ahead
    of one that has not been asked, and not due at all until its turn comes
    round, a day later and then two, four and eight.

    One that failed three times for reasons that were not refusals -- or
    whose reading was not kept three times (markers) -- is left for a person
    ("for-laptop", the name it had while the laptop's evening job took them):
    the night's verdict counts it among what waits.

    A recording whose last ask was refused goes behind the rest of its lane
    (`refused`, cleared by its next answer), so the next run asks another
    first. From 30 September 2026 the laptop's catch-up asked the same
    recording first every evening, the oldest one waiting (aNisQhENQwc, House
    Commerce of 9 September), and was refused on it with a 429 four evenings
    running -- the first of them a minute after another recording had been
    captioned -- while 26 others waited behind it and the hold grew to four
    days. Whether the refusal is the recording's or the machine's, a run that
    meets another first finds out, and still asks nothing after a refusal.
    """
    first, again = [], []
    for vid, v in st["videos"].items():
        if v.get("status") != "finished":
            continue
        c = v.get("captions")
        if c not in WAITING:
            continue
        if c == "failed" and int(v.get("tries") or 0) >= MAX_TRIES:
            v["captions"] = "for-laptop"
            continue
        if not v.get("again"):
            first.append(vid)
        elif (parse_iso(v["again"]) or now) <= now:
            again.append(vid)

    def age(x):
        return (st["videos"][x].get("ended") or "", x)

    def refused(x):
        return (bool(st["videos"][x].get("refused")),)

    first.sort(key=lambda x: refused(x) + age(x))
    again.sort(key=lambda x: refused(x) + (st["videos"][x].get("again") or "",) + age(x))
    return first, again


def tonight(first, again, most=MAX_CAPTIONS, cost=None):
    """(the recordings one run asks for, in order; how many due it leaves).

    `most` is a number of caption REQUESTS. The recordings never asked
    before come first, a request each, and take as much of it as they need.
    The ones asked before take what is left -- `cost(video)` requests each,
    one unless it says otherwise, and it says two for a recording at its
    last ask -- and AGAIN_MIN of them are asked whatever is left, so a retry
    is never asked for in a new recording's place and never waits for ever
    behind a lane that stays full.

    So no run asks for more than `most` + AGAIN_MIN recordings, or makes
    more requests than `most` and what AGAIN_MIN retries cost. While this
    counted recordings, a run with nothing new and twenty retries a week
    old was twenty recordings and forty requests.
    """
    cost = cost or (lambda vid: 1)
    new = list(first[:allowance(len(first), most)])
    room, floor, old = max(0, int(most)) - len(new), (AGAIN_MIN if most > 0 else 0), []
    for vid in again:
        if len(old) >= floor and cost(vid) > room:
            break
        old.append(vid)
        room -= cost(vid)
    return new + old, len(first) + len(again) - len(new) - len(old)


def run_captions(st, first, again, refusals, now, a, work=WORK, save=None):
    """One at a time, gently, and not one more after a refusal.

    `first` and `again` are caption_queue's two lanes; tonight() says which
    of them this run asks for, and the rest wait for the next. Each is asked
    for one track, the first of CAPTION_TRACKS. A recording whose stream
    ended more than a week ago, and which has been asked before, is at its
    last ask: there the tracks are tried in order, the next only when the
    one before is not there, and one with none of them is taken to have no
    captions and is not asked for again.

    Whatever a recording answers that is not captions and not a refusal, it
    is given a time before which it is not asked again -- RETRY_DAYS, longer
    with each such answer -- and that puts it behind every recording not yet
    asked.

    It is taken to have no captions only by a run that captioned something.
    "No captions" is also what yt-dlp says when it could not get at them --
    it discards tracks YouTube wants a token for, and says so in a warning
    this step does not see -- so a run in which nothing was captioned has
    shown nothing about any one recording, and closes none.

    And such a run, once ALL_NONE recordings have answered "no captions" at
    their FIRST ask, is read as a refusal that did not say so: recorded as
    one, with the same hold. Only a first ask: a recording that has said it
    before is expected to say it again. (Counting those too, a replay of
    2021 read nine quiet summer evenings as refusals -- each had three
    retries due and nothing new -- worked the hold up to a week, and kept a
    new recording waiting six days.)

    The run after a hold is wary, and so is every run until one captions
    something. It stops at the ALL_NONE-th "no captions" if it has captioned
    nothing by then, instead of going through the rest -- and there a
    retry's answer counts too, unless the recording is `vouched`: it has
    said "no captions" before in a run that captioned something, which
    showed the answer was its own. A retry that has only said it in runs
    that captioned nothing is no better known than a recording never asked,
    and a run made of nothing but those was otherwise never stopped and
    never read as anything: on a copy of the laptop's state with every
    answer "none", 38 requests in a run, exit 0, with seven refusals in a
    row on the record. (Counting every retry in a wary run, vouched or not,
    is the 2021 mistake again in a smaller place: after a 429 on 17 January
    2022, six recordings that really had no captions renewed the hold twice
    and 34 recordings waited three days or more.)

    A wary run also asks one track of every recording, and so closes none:
    three recordings to find out that nothing has changed are three
    requests, not six.

    Returns (Counter of outcomes, the refusal's words or None).
    """
    got = Counter()
    due = list(first) + list(again)
    if due and refusals.held(now):
        r = refusals.record()
        print("  captions: YouTube "
              + ("gave this machine no captions at all" if r.get("silent")
                 else "refused this machine")
              + f" at {r.get('at')} ({r.get('why')}). Nothing is asked of it "
              f"until {r.get('until_iso')}; {len(due)} wait.")
        for vid in due:
            st["videos"][vid]["captions"] = "deferred"
        got["deferred"] = len(due)
        return got, r.get("why")
    wary = bool(refusals.record().get("count"))
    most = refusals.most(a.max_captions)
    if most < a.max_captions and len(first) > most:
        print(f"  asking for {most} new recordings at most, not "
              f"{a.max_captions}: YouTube refused this machine at "
              f"{refusals.record().get('at')}, and each run without a refusal "
              f"since has added {EASE}.")

    def tracks(vid):
        """What this run asks of one recording: tracks_for, and while a
        refusal stands the first of those and no other."""
        named = tracks_for(st["videos"][vid], now)
        return named[:1] if wary else named

    ask, _ = tonight(first, again, most, lambda vid: len(tracks(vid)))
    t0, refused, in_a_row, done, empty = time.time(), None, 0, 0, []
    new, nones, quiet = set(first), 0, 0

    def hold(why, silent=False):
        """A refusal, said or not: the hold starts and everything due that
        this run has not asked waits for it."""
        hours = refusals.note(now, why, silent, answered=done)
        rest = [x for x in due if x not in ask[:done]]
        for vid in rest:
            st["videos"][vid]["captions"] = "deferred"
        got["deferred"] += len(rest)
        return hours

    for vid in ask:
        v = st["videos"][vid]
        if time.time() - t0 > a.budget * 60:
            print(f"  {a.budget:g} minutes of caption requests: stopping "
                  "for tonight; the rest wait.")
            break
        if done:
            wait(a)
        named = tracks(vid)
        last = len(named) > 1
        outcome, why = fetch_captions(vid, work, a.captions_from, a.timeout,
                                      named, lambda: wait(a))
        v["tried"] = iso(now)
        if outcome == "none-yet" and last:
            why = ("no auto-captions a week after its stream, as "
                   + " or ".join(CAPTION_TRACKS))
        if outcome == "refused":
            v["why"] = why
            v["refused"] = iso(now)
            hours = hold(why)
            refused = why
            print(f"  {vid}: REFUSED -- {why}\n  Stopping. Nothing more is "
                  f"asked of YouTube from this machine for {hours} hours.")
            if save:
                save()
            break
        done += 1
        got[outcome] += 1
        v.pop("refused", None)
        if outcome == "captioned":
            v.update(captions="captioned", fetched=iso(now), by=a.origin, why="")
            for k in ("tries", "asks", "again", "vouched"):
                v.pop(k, None)
            refusals.answered()
            in_a_row = 0
        else:
            empty.append((vid, outcome, last))
            if outcome == "none-yet":
                v.update(captions="none-yet", why=why)
                nones += vid in new or (wary and not v.get("vouched"))
                quiet += 1
                in_a_row = 0
            elif outcome == "not-aired":
                v.update(status="live", why=why)
            elif outcome == "gone":
                v.update(status="gone", why=why)
            else:
                v.update(captions="failed", why=why,
                         tries=int(v.get("tries") or 0) + 1)
                in_a_row += 1
        print(f"  {vid}: {outcome}"
              + (f" ({why})" if outcome == "captioned" else f" -- {why}")
              + f"   {str(v.get('title') or '')[:60]}")
        if save:
            save()
        if in_a_row >= a.stop_after:
            print(f"  {in_a_row} failures in a row that were not refusals. "
                  "Stopping for tonight; the rest wait.")
            break
        if wary and nones >= ALL_NONE and not got["captioned"]:
            break
    sure = bool(got["captioned"])
    if not refused and not sure and nones >= ALL_NONE:
        refused = (f"\"no captions\" from {nones} recordings "
                   + ("with a refusal already standing" if wary
                      else "asked for the first time")
                   + " and captions from none: read as a refusal that "
                   f"did not say so, not as {nones} recordings without captions")
        hours = hold(refused, silent=True)
        print(f"  {refused}.\n  Nothing more is asked of YouTube from this "
              f"machine for {hours} hours, and none of them is taken to have "
              "no captions.")
    else:
        if not refused and done < len(due):
            got["left for tomorrow"] = len(due) - done
        if not refused and sure:
            refusals.eased(most, a.max_captions)

    # What an answer that was not captions costs its recording: a time before
    # which it is not asked again, further off with each one. That time is
    # what puts it behind the unasked. Only a run that captioned something
    # goes further and takes "no captions" for the recording's last word.
    closed = []
    for vid, outcome, last in empty:
        v = st["videos"][vid]
        n = v["asks"] = int(v.get("asks") or 0) + 1
        if outcome == "none-yet" and sure:
            v["vouched"] = True
        if outcome == "none-yet" and last and sure:
            v["captions"] = "none-published"
            v.pop("again", None)
            closed.append(vid)
        else:
            v["again"] = iso(now + retry_after(n))
    if closed:
        got["none-yet"] -= len(closed)
        got["none-published"] = len(closed)
        print(f"  {len(closed)} taken to have no captions and not asked for "
              "again: " + ", ".join(closed))
    if quiet and not sure and not refused:
        print(f"  {quiet} answered that they have no captions, in a run that "
              "captioned nothing: not enough to read anything into either "
              "way. None is taken to have none; each is asked again, later "
              "and after anything new.")
    if empty and save:
        save()
    return +got, refused


# ------------------------------------------------------------ carrying --

def carry_list(st=None):
    """What GitHub's machine is given for this step each night and sends back
    after it: download each one the bucket holds, upload each one that exists.

    Three small files of this step's own. What it reads off a recording is
    kept in candidate_segments.json and caption_spans.json, which the kit
    carries as the night's (THE NIGHT KEEPS WHAT IT READS); until 10 October
    2026 it travelled in the state instead.
    """
    return [p.as_posix() for p in (STATE, csv_path("house"), csv_path("senate"))]


# candidate_segments.json's two maps beside its recordings (segment_markers).
SIDES = ("_absent", "_sequence")


def in_files(markers=MARKERS, summary=None, named=None):
    """The recordings whose reading the caption results already hold, or
    None when this machine cannot tell.

    Read means the caption summary names it -- where its captions stop,
    which is all build_site_v2 has to check that its track is in step, and a
    recording with times and no entry has its times withheld -- and
    candidate_segments.json names it too, which is what segment_markers
    found in its captions. Or no proceeding names it (`named`, by default
    proceedings.csv's), and there is nothing to read it against yet: a study
    commission's meeting is read when it is captioned, and its summary entry
    is all there is to keep. Where there is no summary at all, the first
    file alone answers; where there is no proceedings table, the second rule
    is not applied.
    """
    try:
        marks = json.loads(Path(markers).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(marks, dict):
        return None
    marks = {k for k in marks if k not in SIDES}
    summary = Path(summary or summary_path())
    if not summary.exists():
        return marks
    try:
        doc = json.loads(summary.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rec = set((doc.get("recordings") or {}) if isinstance(doc, dict) else {})
    if named is None:
        import proceedings as P
        named = set(P.by_video(P.load())) if Path(P.PATH).exists() else None
    if named is None:
        return marks & rec
    return {v for v in rec if v in marks or v not in named}


def summary_path():
    """caption_span's summary file, by its own name where it has one."""
    import caption_span
    return Path(getattr(caption_span, "SUMMARY", "caption_spans.json"))


def prune(st, now):
    """Settled entries leave the state. Their rows stay in the index, which
    is what makes a recording known."""
    for vid in list(st["videos"]):
        v = st["videos"][vid]
        seen = parse_iso(v.get("seen"))
        if v.get("carry") or not seen or now - seen < timedelta(days=PRUNE_DAYS):
            continue
        if v.get("status") == "gone" or v.get("captions") in (
                "none-published", "not-needed", "for-laptop") or (
                v.get("captions") == "captioned"
                and (v.get("read") or v.get("adopted") or v.get("by") != "runner")):
            del st["videos"][vid]


def restore_results(st, markers=MARKERS, summary=None, work=WORK):
    """Fold what an older night carried in the state into the caption
    results, for recordings whose captions are not on this machine: the one
    night of overlap after 10 October 2026, when the files became the
    night's and the carrying stopped (THE NIGHT KEEPS WHAT IT READS). Only
    where the files have nothing for the recording: an answer already there
    is never replaced by this one. Returns the recordings put into
    candidate_segments.json."""
    held = {vid: v for vid, v in st["videos"].items()
            if v.get("carry") and v.get("result") and not has_captions(vid, work)}
    if not held:
        return []
    p = Path(markers)
    marks = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    back = []
    for vid, v in sorted(held.items()):
        if vid in marks:
            continue
        r = v["result"]
        marks[vid] = r["segs"]
        for side, key in (("_absent", "absent"), ("_sequence", "sequence")):
            if r.get(key):
                marks.setdefault(side, {})[vid] = r[key]
        back.append(vid)
    if back:
        atomic_write(p, json.dumps(marks, indent=2))
    sp = Path(summary or summary_path())
    if sp.exists():
        doc = json.loads(sp.read_text(encoding="utf-8"))
        rec = doc.setdefault("recordings", {})
        added = [vid for vid in held if vid not in rec and held[vid].get("span")]
        for vid in added:
            rec[vid] = held[vid]["span"]
        if added:
            atomic_write(sp, json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return back


# ----------------------------------------------------------------- run --

def since_state(a):
    now = utcnow(a.now)
    st = load_state()
    refusals = Refusals(st["refusals"], a.origin)
    rows = read_rows()
    # Recordings a committed index carries finished: a livestreams row for
    # one of those is redundant and is dropped from this step's file.
    committed = {vid: r for vid, fr in rows.items() for f, r in fr
                 if not f.endswith("_livestreams.csv") and rank(r) == 2}
    code, notes, units = 0, [], 0

    # What the caption results already hold: last night's files, as the kit
    # brought them, the night's own since 10 October 2026.
    done = in_files()
    if a.origin == "runner" and done is not None:
        # A recording captioned here whose reading the files do not hold --
        # build_all's --markers step did not run, its guard put the files
        # back, or the docket named nothing on it then and does now -- is
        # asked for again, because its captions did not come with this
        # machine: as a failure, so that after MAX_TRIES it is left for a
        # person rather than asked every night. A reading an older night
        # still carries in the state is not: --markers folds it in.
        again = [vid for vid, v in st["videos"].items()
                 if v.get("captions") == "captioned" and v.get("by") == "runner"
                 and not v.get("carry") and vid not in done and not has_captions(vid)]
        for vid in again:
            v = st["videos"][vid]
            v.update(captions="failed", tries=int(v.get("tries") or 0) + 1,
                     why=str(v.get("why") or "") or "its reading is in no night's files; "
                         "asked for again")
            v.pop("read", None)
        if again:
            print(f"  {len(again)} recording(s) captioned on an earlier night "
                  "are not in the caption results; asked for again")

    counts = Counter()
    updates, removals = {"house": {}, "senate": {}}, {"house": set(), "senate": set()}
    key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    if not key and not a.replay:
        code = 3
        notes.append("not configured: YOUTUBE_API_KEY is not set, so nothing "
                     "new was listed")
        print("  YOUTUBE_API_KEY is not set: nothing new can be listed. What "
              "was already waiting is still captioned.")
    else:
        api = Api(key=key or None, replay=a.replay, record=a.record)
        try:
            counts, updates, removals = discover(api, st, rows, now, a.max_pages)
        except ApiError as e:
            if e.kind == "config":
                code = 3
                notes.append(f"not configured: {e.why}")
            else:
                notes.append(f"listing deferred: {e.why}")
            print(f"  the listing stopped: {e.why}")
        units = api.units

    for chamber in ("house", "senate"):
        add, rep, drop = write_rows(chamber, updates[chamber], removals[chamber],
                                    committed)
        if add or rep or drop:
            print(f"  {csv_path(chamber)}: {add} added, {rep} updated, "
                  f"{drop} dropped")
    save_state(st)

    # Not asked for again: a recording the caption results already hold, and
    # one whose captions are already on this disk -- before the queue is
    # made, so one that is not due tonight is seen as well.
    settle(st, now, done)
    first, again = caption_queue(st, now)
    kit = {}
    if (first or again) and a.origin == "runner" \
            and os.environ.get(NEW_TERM_ENV) == "true":
        print(f"  a New term run: no captions are asked for tonight; "
              f"{len(first) + len(again)} recording(s) wait for the next night")
        notes.append("no captions asked for: a New term run")
        first, again = [], []
    if (first or again) and not yt_dlp_here(a):
        code = 3
        notes.append(f"not configured: yt-dlp is not installed here, so "
                     f"{len(first) + len(again)} recording(s) wait for captions")
        first, again = [], []
    if (first or again) and not a.captions_from:
        kit = setup()
        print(f"  asking with {setup_said(kit)}")
    got, refused = run_captions(st, first, again, refusals, now, a,
                                save=lambda: save_state(st))
    if refused:
        notes.append(f"captions deferred: YouTube refused ({refused})")

    prune(st, now)
    carried = sum(1 for v in st["videos"].values() if v.get("carry"))
    waiting = sum(1 for v in st["videos"].values() if v.get("status") == "finished"
                  and v.get("captions") in WAITING + ("for-laptop",))
    said = []
    if counts["new"] or counts["finished"]:
        said.append(f"{counts['new']} new on the channels, {counts['finished']} "
                    "now over and indexed"
                    + (f", {counts['not yet over']} not yet over"
                       if counts["not yet over"] else ""))
    if got:
        said.append("captions: " + ", ".join(f"{n} {k}" for k, n in got.items()))
    head = "; ".join(said) if said else "nothing new"
    tail = [f"{waiting} wait for captions"] if waiting else []
    tail += [f"{carried} older reading(s) to fold into the caption results"] if carried else []
    tail.append(f"{units} API unit{'' if units == 1 else 's'}")
    line = "LIVESTREAMS: " + head + "; " + ", ".join(tail) + \
        ("; " + "; ".join(notes) if notes else "")
    # What the night's verdict reads (nightly.captions_record): tonight's
    # answers by outcome, what still waits, and the setup that asked.
    st["last_run"] = {"at": iso(now), "origin": a.origin, "units": units,
                      "captions": dict(got), "waiting": waiting,
                      "verdict": line, **({"setup": kit} if kit else {})}
    save_state(st)
    print("\n" + line)
    return code


def catch_up(a):
    """On the laptop, by hand: caption the night's new recordings that are not
    here -- the ones YouTube refused GitHub's machine, and the ones it
    captioned there, whose files the kit never brings back -- then read them.

    Until 8 October 2026 the laptop's evening job ran this every evening and
    sent the two files it reads into to the kit. Now it is a person's tool:
    a test of whether YouTube answers this machine (its own refusal record,
    archive/youtube.refused.json, says what happened), and captions for
    development. Reads the nightly's state and never writes it. What it reads
    goes into the laptop's own candidate_segments.json and caption summary,
    and no further: both are the night's files in the kit since 10 October
    2026, and cloud.py seed-kit never sends a night's file over the night's
    copy. The night asks for these recordings itself.
    """
    if a.origin == "runner":
        raise Broken("--catch-up is the laptop's; on GitHub's machine run "
                     "--since-state")
    now = utcnow(a.now)
    st = load_state()
    table = load_laptop_refusals()
    # What this machine has asked for and got no captions. The state is
    # GitHub's and is not written here, so without this the laptop would open
    # every evening with the same recordings -- 127 of the 3,490 in
    # archive/captions.json on 1 October 2026 have no captions published --
    # and never learn to ask them less often, or last.
    # An entry leaves when the night's state has dropped the recording; when
    # the recording needs nothing more from this machine; or when GitHub's
    # machine got captions for it AFTER this machine last asked, which is
    # news -- they exist now, whatever was answered here before.
    # Not merely because the state calls it captioned: this machine still
    # wants a recording GitHub's machine captioned, whose files never come
    # here. For a day such an entry was dropped every evening, so one that
    # answered this machine "no captions" or "private" was asked every
    # evening, ahead of the new ones, its count stuck at one.
    def stands(vid, e):
        v = st["videos"].get(vid)
        if not isinstance(e, dict) or v is None:
            return False
        if v.get("captions") != "captioned":
            return True
        if v.get("adopted") or v.get("read") or has_captions(vid):
            return False
        return not str(v.get("fetched") or "") > str(e.get("tried") or "")

    mine = {vid: dict(e) for vid, e in (table.get(ASKED) or {}).items()
            if stands(vid, e)}
    closed = {vid for vid, e in mine.items() if e.get("closed")}
    want = [vid for vid, v in st["videos"].items()
            if v.get("status") == "finished"
            and v.get("captions") in ("waiting", "deferred", "failed",
                                      "for-laptop", "none-yet", "captioned")
            and not v.get("adopted") and not v.get("read") and not has_captions(vid)
            and vid not in closed]
    # The night's entry for each, as this machine sees it: waiting, and
    # carrying what this machine's own asks have counted against it.
    shadow = {"videos": {}}
    for vid in want:
        v = dict(st["videos"][vid], captions="waiting")
        for k in ("asks", "again", "tries", "vouched", "refused"):
            v.pop(k, None)
        v.update({k: mine[vid][k] for k in ("asks", "again", "vouched", "refused")
                  if (mine.get(vid) or {}).get(k)})
        shadow["videos"][vid] = v
    first, again = caption_queue(shadow, now)
    later = len(want) - len(first) - len(again)
    was = Counter("captioned on GitHub's machine"
                  if st["videos"][v].get("captions") == "captioned"
                  else "not captioned there" for v in want)
    print(f"{len(want)} of the night's recording(s) have no captions here"
          + (": " + ", ".join(f"{n} {k}" for k, n in was.items()) if want else "")
          + (f"; {len(again)} of them asked before and due again" if again else "")
          + (f"; {later} asked before and not due yet" if later else "")
          + (f"; {len(closed)} more are no longer asked for" if closed else ""))
    if (first or again) and not yt_dlp_here(a):
        raise Broken("yt-dlp is not installed here: python3 -m pip install "
                     "yt-dlp, at the version the nightly pins")
    got, refused = run_captions(shadow, first, again, Refusals(table, "laptop"),
                                now, a)
    for vid in want:
        v = shadow["videos"][vid]
        if v.get("captions") == "captioned":
            mine.pop(vid, None)
            continue
        if v.get("refused") == iso(now):
            # Refused this run: as it was, and behind the rest next evening.
            mine[vid] = dict(mine.get(vid) or {}, refused=iso(now))
            continue
        if int(v.get("asks") or 0) <= int((mine.get(vid) or {}).get("asks") or 0):
            continue            # not asked this run: as it was
        e = {"asks": int(v["asks"]), "tried": iso(now),
             "why": str(v.get("why") or "")[:200]}
        if v.get("vouched"):
            e["vouched"] = True
        if v.get("captions") == "none-published":
            e["closed"] = "none-published"
        elif (e["asks"] >= GIVE_UP_ASKS
              and (got["captioned"] or v.get("status") != "finished")):
            # Like "no captions", only on the word of a run that captioned
            # something -- or YouTube's own that the recording is gone.
            e["closed"] = "given-up"
            print(f"  {vid}: asked {e['asks']} times and never captioned "
                  f"({e['why']}); not asked for again")
        else:
            e["again"] = v["again"]
        mine[vid] = e
    table.pop(ASKED, None)
    if mine:
        table[ASKED] = mine
    atomic_write(LAPTOP_REFUSAL, json.dumps(table, indent=1, sort_keys=True) + "\n")
    done = [vid for vid in want
            if shadow["videos"][vid].get("captions") == "captioned"]
    code = 0
    if done:
        code = read_markers(done)
        code = code or write_summary()
    line = "LIVESTREAMS CATCH-UP: " + (", ".join(f"{n} {k}" for k, n in got.items())
                                       or "nothing to do")
    if refused:
        line += f"; YouTube refused this machine as well ({refused})"
    print("\n" + line)
    if done:
        print("\nWhat was read is in this laptop's candidate_segments.json and caption "
              "summary, and goes no further: the night owns both in the kit, and asks "
              "YouTube for these recordings itself.")
    return code


def write_summary():
    """The caption summary, refreshed from work/ where the caption_span that
    writes one is here; otherwise said, so nobody takes a missing summary for
    a current one."""
    import caption_span
    if not hasattr(caption_span, "write_summary"):
        print("  this caption_span.py writes no caption summary; nothing to "
              "refresh")
        return 0
    import child
    r = child.run([sys.executable, _paths.script("caption_span.py"), "--write"])
    return 0 if r.returncode == 0 else 1


def markers(a):
    """build_all's step after the chair's boundaries: segment_markers over this
    step's recordings, and nothing else, scored before anything is kept.

    Where their captions are on this machine it reads them, through
    segment_markers, which merges into candidate_segments.json, and puts
    where each one's captions stop into the caption summary, which merges
    too: every other recording keeps the answer it had. On the laptop, step
    15 has just read them and this finds them in its cache. On GitHub's
    machine, where step 15 does not run, this is where a new recording gets
    its times, and the two files go back to the kit as the night's. A
    reading an older night carried in the state is folded in once (fold).

    Then the guard (THE GUARD): an entry other than tonight's that changed,
    or a probe against the hand-timed proceedings that places fewer or has
    a worse median, or one that would not run, and both files are put back
    as they were. Exit 0 either way, so the rest of the build and the night
    go on: the state says what happened and the night's verdict warns.
    Exit 1 only when segment_markers itself failed, and then too the files
    are put back first.
    """
    try:
        st = load_state()
    except Broken as e:
        print(f"LIVESTREAMS MARKERS: broken -- {e}")
        return 1
    here = sorted(vid for vid, v in st["videos"].items()
                  if v.get("captions") == "captioned" and has_captions(vid))
    runner = a.origin == "runner"
    held = sorted(vid for vid, v in st["videos"].items()
                  if runner and v.get("carry") and v.get("result")
                  and not has_captions(vid))
    now = utcnow(a.now)
    record = {"at": iso(now), "read": len(here), "folded": 0}
    if not here and not held:
        record["guard"] = "nothing to read"
        print("\nLIVESTREAMS MARKERS: 0 recording(s) read")
        if runner:
            st["markers"] = record
            save_state(st)
        return 0
    copies = Copies(MARKERS, summary_path())
    try:
        return _read_and_judge(st, here, held, copies, record, now, runner)
    except BaseException:
        # Whatever stopped it half way, nothing it wrote is kept.
        copies.put_back()
        raise
    finally:
        copies.close()


def _read_and_judge(st, here, held, copies, record, now, runner):
    """markers(), from the copies on: read, judge, keep or put back, and
    say so in the state. The exit status."""
    if held:
        restore_results(st)
    code = read_markers(here) if here else 0
    if code == 0 and here:
        code = summarize(here)
    # The fold may add a held recording's summary entry where its reading
    # was in the file already, so every held one may change, not only the
    # ones it put into candidate_segments.json.
    tonight = set(here) | set(held)
    why, scores = ("segment_markers did not finish", None) if code else \
        guard(copies, tonight)
    if scores:
        record["probe"] = scores
    if why:
        copies.put_back()
        record["guard"] = "put back: " + why
        for vid in here:
            v = st["videos"][vid]
            v.update(captions="failed", tries=int(v.get("tries") or 0) + 1,
                     why=f"read on {now:%Y-%m-%d} and not kept: {why}"[:200])
            v.pop("read", None)
        print(f"\nLIVESTREAMS MARKERS: {len(here)} recording(s) read and NOT kept: {why}. "
              "candidate_segments.json and the caption summary are as they came down; "
              "the recordings are asked for again on a later night.")
    else:
        record["guard"] = "passed" if copies.changed() else "nothing changed"
        day = now.strftime("%Y-%m-%d")
        done = in_files() or set()
        for vid in here:
            if vid in done:
                st["videos"][vid]["read"] = day
        # A carried reading the files now hold is carried no longer: folded
        # tonight, or there already.
        released = 0
        for vid in held:
            v = st["videos"][vid]
            if vid in done:
                v.update(carry=False, read=day)
                v.pop("result", None)
                v.pop("span", None)
                released += 1
        record["folded"] = released
        after = (scores or {}).get("after") or {}
        print(f"\nLIVESTREAMS MARKERS: {len(here)} recording(s) read"
              + (f", {released} older reading(s) folded into the caption results"
                 if released else "")
              + (f"; the timestamp probe places {after['placed']} of {after['marked']} "
                 "hand-timed proceedings, median "
                 + ("-" if after.get("median") is None else f"{after['median']:g}s")
                 + ", no worse than before" if after else ""))
    if runner:
        st["markers"] = record
        save_state(st)
    return 1 if code else 0


class Copies:
    """The two caption results as they were before a reading, to compare
    with and to put back. A file that was not there is put back as not
    there."""

    def __init__(self, *paths):
        import tempfile
        self.dir = Path(tempfile.mkdtemp(prefix="gr-markers-"))
        self.files = {}
        for k, p in enumerate(paths):
            p = Path(p)
            keep = self.dir / f"{k}-{p.name}"
            if p.exists():
                shutil.copy2(p, keep)
                self.files[p] = keep
            else:
                self.files[p] = None

    def before(self, path):
        return self.files.get(Path(path))

    def changed(self):
        for p, keep in self.files.items():
            if (keep is None) != (not p.exists()):
                return True
            if keep is not None and keep.read_bytes() != p.read_bytes():
                return True
        return False

    def put_back(self):
        for p, keep in self.files.items():
            if keep is None:
                p.unlink(missing_ok=True)
            else:
                tmp = p.with_name(p.name + ".tmp")
                shutil.copy2(keep, tmp)
                os.replace(tmp, p)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def summarize(vids, work=WORK):
    """Where each of these recordings' captions stop, merged into the caption
    summary (caption_span.merge_summary, the writer --write uses): 0, or 1
    when it could not be written."""
    import caption_span
    try:
        caption_span.merge_summary([Path(work) / v for v in vids])
    except (OSError, SystemExit) as e:
        print(f"  the caption summary could not be written: {e}")
        return 1
    return 0


def changed_besides(before, after, tonight):
    """The entries of two candidate files, or two caption summaries'
    recordings, that differ other than tonight's recordings': [name]."""
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    out = []
    for k in sorted(set(before) | set(after)):
        if k in SIDES:
            b, x = before.get(k) or {}, after.get(k) or {}
            out += [f"{k}/{v}" for v in sorted(set(b) | set(x))
                    if v not in tonight and b.get(v) != x.get(v)]
        elif k not in tonight and before.get(k) != after.get(k):
            out.append(k)
    return out


def probe(candidate):
    """probe_alignment.py --truth on one candidate file: {"marked", "placed",
    "median"} (seconds, None where nothing was placed), or None when the
    probe would not run. Its scoreboard is read from the file --score-out
    writes, in a folder of its own, not from what it prints."""
    import child
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="gr-probe-"))
    try:
        out = d / "score.json"
        r = child.run([sys.executable, _paths.script("probe_alignment.py"), "--truth",
                       "--candidate", str(candidate), "--score-out", str(out)],
                      capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            return None
        doc = json.loads(out.read_text(encoding="utf-8"))
        truth, cand = doc.get("truth") or {}, doc.get("candidate") or {}
        marked = int(truth.get("marked") or cand.get("marked") or 0)
        if not marked:
            return None
        med = cand.get("median")
        return {"marked": marked, "placed": int(cand.get("placed") or 0),
                "median": None if med is None else round(float(med), 3)}
    except (OSError, ValueError, TypeError):
        return None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def worse(before, after):
    """Why `after` scores worse than `before`, or "": laptop_evening.py's
    rule, which this replaces. A median that grew, or fewer of the same
    hand-timed proceedings placed."""
    if before.get("median") is not None and (after.get("median") is None
                                             or after["median"] > before["median"]):
        return (f"the timestamp probe's median went from {before['median']}s to "
                f"{after.get('median')}s")
    if after["marked"] == before["marked"] and after["placed"] < before["placed"]:
        return (f"the timestamp probe places {after['placed']} of {after['marked']} "
                f"hand-timed proceedings, where it placed {before['placed']}")
    return ""


def guard(copies, tonight):
    """(why the reading is not kept, or "", the probe before and after): see
    THE GUARD. Nothing changed is nothing to judge."""
    if not copies.changed():
        return "", None
    names = []
    for path, inner in ((MARKERS, None), (summary_path(), "recordings")):
        keep = copies.before(path)
        try:
            was = json.loads(keep.read_text(encoding="utf-8")) if keep else {}
            now = json.loads(Path(path).read_text(encoding="utf-8")) \
                if Path(path).exists() else {}
        except (OSError, ValueError) as e:
            return f"{Path(path).name} will not read after the reading ({e})", None
        if inner:
            was, now = (was or {}).get(inner), (now or {}).get(inner)
        names += [f"{Path(path).name}: {n}" for n in changed_besides(was, now, tonight)]
    if names:
        return (f"entries besides tonight's recordings changed ({', '.join(names[:3])}"
                + (f" and {len(names) - 3} more" if len(names) > 3 else "") + ")"), None
    keep = copies.before(MARKERS)
    before = probe(keep) if keep else {"marked": 0, "placed": 0, "median": None}
    after = probe(MARKERS)
    scores = {"before": before, "after": after}
    if after is None or (keep and before is None):
        return ("the timestamp probe (probe_alignment.py --truth) would not run, so "
                "nothing read tonight could be scored"), scores
    if before.get("marked"):
        why = worse(before, after)
        if why:
            return why, scores
    return "", scores


def load_laptop_refusals():
    try:
        return json.loads(LAPTOP_REFUSAL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def read_markers(vids):
    """segment_markers over these recordings only. It merges into
    candidate_segments.json, so every other recording keeps its answer."""
    import proceedings as P
    named = set(P.by_video(P.load()))
    folders = [(WORK / v).as_posix() for v in vids if v in named]
    later = [v for v in vids if v not in named]
    if later:
        print(f"  {len(later)} not in proceedings.csv, so there is nothing to "
              "read them against until the docket schedules something on "
              "them: " + ", ".join(later[:6]))
    if not folders:
        return 0
    if not (Path("data") / "bills.json").exists():
        print("  data/bills.json is not here and segment_markers needs it: "
              "run this after build_all's data step, as its own step does.")
        return 1
    import child
    r = child.run([sys.executable, _paths.script("segment_markers.py"),
                   "--transcript", *folders, "--data", "data", "--quiet"],
                  capture_output=True, text=True)
    # What it found, in its own few lines; all of it where it failed.
    said = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    keep = [ln for ln in said if re.match(r"\s+\d[\d,]*\s{2}", ln) or "%" in ln]
    for ln in (keep if r.returncode == 0 else said[-12:] + (r.stderr or "").splitlines()[-12:]):
        print(f"  segment_markers: {ln.strip()}")
    return 0 if r.returncode == 0 else 1


def status(a):
    st = load_state()
    vids = st["videos"]
    print(f"{len(vids)} recording(s) in {STATE.as_posix()}")
    for k, n in Counter(v.get("status") for v in vids.values()).most_common():
        print(f"  {n:>5}  {k}")
    for k, n in Counter(v.get("captions") for v in vids.values()
                        if v.get("status") == "finished").most_common():
        print(f"  {n:>5}  captions {k}")
    behind = [v for v in vids.values() if v.get("status") == "finished"
              and v.get("again") and v.get("captions") in WAITING]
    if behind:
        print(f"  {len(behind):>5}  of those asked for and answered without "
              "captions: behind the rest, next due "
              + min(v["again"] for v in behind))
    print(f"  {sum(1 for v in vids.values() if v.get('carry'))} older reading(s) "
          "carried in the state, folded into the caption results by the next "
          "--markers")
    mk = st.get("markers") or {}
    if mk:
        print(f"  the last --markers, {mk.get('at')}: {mk.get('read', 0)} read; "
              f"the guard: {mk.get('guard')}")
    for origin, r in sorted((st.get("refusals") or {}).items()):
        if r.get("count"):
            print("  YouTube "
                  + ("gave no captions at all to" if r.get("silent") else "refused")
                  + f" the {origin} at {r.get('at')} "
                  f"({r.get('why')}); held until {r.get('until_iso')}")
    lr = st.get("last_run") or {}
    if lr:
        print(f"  last run {lr.get('at')} on the {lr.get('origin')}:\n    "
              f"{lr.get('verdict', '')}")
    return 0


class lock:
    """One run of this step at a time on one machine.

    Touched every LOCK_BEAT seconds while it is held, and taken over once it
    has gone LOCK_STALE seconds untouched: the night's step is killed at its
    time limit with the lock still on disk, and until 10 October 2026 a lock
    held for two hours by its date alone would then have failed the build's
    --markers step -- a failed step, which check_site will not publish. A
    run that is alive touches it ten times in that while, whatever yt-dlp is
    doing."""

    def __enter__(self):
        if LOCK.exists() and time.time() - LOCK.stat().st_mtime < LOCK_STALE:
            raise Broken(f"{LOCK} is held "
                         f"({LOCK.read_text(encoding='utf-8').strip()}): "
                         "another run of this step is going")
        if LOCK.exists():
            print(f"  {LOCK.as_posix()} has not been touched for "
                  f"{(time.time() - LOCK.stat().st_mtime) / 60:.0f} minutes: the run "
                  "that held it is gone, so this one takes it")
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        LOCK.write_text(f"pid {os.getpid()}", encoding="utf-8")
        import threading
        self._stop = threading.Event()

        def beat():
            while not self._stop.wait(LOCK_BEAT):
                try:
                    os.utime(LOCK, None)
                except OSError:
                    pass
        threading.Thread(target=beat, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        LOCK.unlink(missing_ok=True)
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--since-state", action="store_true",
                      help="the nightly step: list, index, caption")
    mode.add_argument("--catch-up", action="store_true",
                      help="on the laptop, by hand: ask YouTube from there for what "
                           "the nightly could not caption; sends nothing")
    mode.add_argument("--markers", action="store_true",
                      help="build_all's step: segment_markers over this step's "
                           "recordings only, scored before it is kept")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--carry", action="store_true",
                      help="the files carried between nights, one a line")
    ap.add_argument("--max-captions", type=int, default=MAX_CAPTIONS,
                    help="the most recordings one run asks for the first "
                         f"time, oldest first (default {MAX_CAPTIONS}); up "
                         "to that, it asks for whatever is waiting")
    ap.add_argument("--delay", type=float, default=DELAY,
                    help="seconds between two recordings, at least "
                         f"(default {DELAY:g})")
    ap.add_argument("--jitter", type=float, default=JITTER,
                    help="and up to this many more, at random "
                         f"(default {JITTER:g})")
    ap.add_argument("--budget", type=float, default=BUDGET,
                    help="minutes of caption requests in one run, at most "
                         f"(default {BUDGET:g})")
    ap.add_argument("--timeout", type=float, default=TIMEOUT,
                    help="seconds allowed for one track's ask "
                         f"(default {TIMEOUT:g})")
    ap.add_argument("--stop-after", type=int, default=3,
                    help="failures in a row, not refusals, before stopping")
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES)
    ap.add_argument("--replay", metavar="DIR",
                    help="answer API calls from recorded responses")
    ap.add_argument("--record", metavar="DIR",
                    help="keep the API's answers here; never the key")
    ap.add_argument("--captions-from", metavar="DIR",
                    help="captions from DIR/<video>/ instead of YouTube")
    ap.add_argument("--now", help="the time to act as of, for tests")
    ap.add_argument("--origin", choices=["runner", "laptop"],
                    help="which machine this is; GITHUB_ACTIONS decides by default")
    a = ap.parse_args(argv)
    a.origin = a.origin or ("runner" if os.environ.get("GITHUB_ACTIONS") == "true"
                            else "laptop")
    if a.replay and a.record:
        ap.error("--replay and --record cannot be used together")
    try:
        if a.status:
            return status(a)
        if a.carry:
            print("\n".join(carry_list()))
            return 0
        with lock():
            if a.markers:
                return markers(a)
            return catch_up(a) if a.catch_up else since_state(a)
    except Broken as e:
        print(f"\nLIVESTREAMS: broken -- {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
