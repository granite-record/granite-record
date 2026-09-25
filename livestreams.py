#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-25.1
"""
New livestreams, every night: the recordings the House and Senate channels
finished since the last run, indexed and captioned, and left where the build
turns captions into timestamps.

    python3 livestreams.py --since-state   the nightly step, before build_all
    python3 livestreams.py --markers       build_all's step after the chair's
                                           boundaries: this step's recordings
    python3 livestreams.py --catch-up      on the laptop: the recordings the
                                           nightly could not caption
    python3 livestreams.py --status        what the state says; asks nothing
    python3 livestreams.py --carry         the files carried between nights

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

  youtube.com, for the captions, through yt-dlp with the arguments
  fetch_archive_captions.py uses: auto-captions, English, json3, no audio. One
  recording at a time, twenty seconds apart, twenty at most a night.

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
  videos_senate_livestreams.csv   committed videos_*.csv do not carry, or carry
                                  from before they aired. The twelve columns
                                  fetch_channel_index.py writes, made by its own
                                  title parser. Every reader globs videos_*.csv
                                  and takes the chamber from the file's name.
  work/<video>/captions*.json3    where segment_markers and caption_span look.
  archive/livestreams.json        what it has seen, what it waits for, and any
                                  refusal still in force.

Never a committed file: on GitHub's machine a changed tracked file stops the
deploy, and nobody commits there.

WHAT TURNS THEM INTO TIMESTAMPS

build_all.py --local, which the night runs next. build_manifest and
build_floor_index read the new rows and build_proceedings writes the table;
then `livestreams.py --markers`, a step of its own, runs segment_markers over
this step's recordings and nothing else. segment_markers merges, so every
other recording keeps the answer the laptop's caption job gave it, and
build_site_v2 publishes the lot. On the laptop step 15 has read these already
and --markers finds them in its cache; on GitHub's machine step 15 does not
run, and --markers is how a new recording gets its times. The late-caption
check reads the caption file where there is one, and that night it is there.

CARRIED BETWEEN NIGHTS

GitHub's machine starts empty and its kit carries no captions, so what was
read off a recording travels instead: --markers keeps the recording's
candidate_segments.json entry and its caption-summary entry in the state, and
on the nights after puts both back -- only where the laptop's copies have
nothing for it -- so the times stay on the site. It stops once the laptop has
read the recording itself, which is when its candidate_segments.json and its
caption summary both name it. `--carry` lists the three small files the
bucket must keep: the state and the two row files.

A REFUSAL

YouTube refusing a caption request stops the captions for the night and is
recorded; the recording waits. The next night asks nothing, the one after makes
one request as a probe, and each refusal in a row doubles the wait, to a week.
The laptop keeps its own record: a refusal is about an address, and the two
machines have different ones.

THE DATA CENTRE RISK

YouTube often answers a data centre's address -- GitHub's among them -- with
"Sign in to confirm you're not a bot". That is read as a refusal, not a
failure: the recording waits for the laptop, its index row and the schedule's
offsets still reach the site, nothing already published changes, and the
night goes on. On the laptop, `python3 livestreams.py --catch-up` captions what
the nightly could not and reads it; the next night sees that the laptop has.

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

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The index's own parser and channel list. One reader of a title: a row made
# here has to be the row fetch_channel_index.py would have written. Importing
# it asks nothing; its main() is never called.
import fetch_channel_index as FCI

HERE = Path(__file__).resolve().parent
STATE = Path("archive/livestreams.json")
LOCK = Path("archive/livestreams.lock")
# The laptop's own record of YouTube refusing it, under archive/ with the
# General Court's: local, never carried.
LAPTOP_REFUSAL = Path("archive/youtube.refused.json")
WORK = Path("work")
MARKERS = Path("candidate_segments.json")

CHANNELS = {c: cid for c, (cid, _name) in FCI.CHANNELS.items()}
# fetch_channel_index.main's columns, in its order; preflight reads that file
# and holds the two together.
COLS = ["video_id", "title", "title_parsed", "parsed_committee", "parsed_date",
        "date_from", "has_start_time", "start_eastern", "actual_start_utc",
        "actual_end_utc", "duration_iso", "published_at"]
# Quota units per call, from the API's own table. Nothing that costs more --
# search.list at 100, the caption methods at 50 and 200 -- is ever called.
COST = {"channels": 1, "playlistItems": 1, "videos": 1}

# yt-dlp, exactly as fetch_archive_captions.fetch runs it.
YTDLP = ["-m", "yt_dlp", "--write-auto-subs", "--sub-langs", "en.*",
         "--sub-format", "json3/vtt", "--skip-download", "--no-warnings"]
# The caption files segment_markers.read_words and caption_span.last_cue read,
# in the order they try them.
CAPTION_FILES = ["captions.en.json3", "captions.en-orig.json3"]

MAX_PAGES = 4          # pages of fifty uploads, per channel per night
LOOKBACK_DAYS = 14     # how far behind the last run a page may reach
NONE_YET_DAYS = 7      # auto-captions can lag a stream; ask nightly this long
MAX_TRIES = 3          # failures that are not refusals, then the laptop's
PENDING_DAYS = 30      # past its scheduled time, an unaired stream never aired
STALE_DAYS = 60        # a pre-air committed row this near today is rechecked
PRUNE_DAYS = 60        # settled entries leave the state after this
HOLD_HOURS = 36        # after one refusal: skip a night, probe the next
HOLD_MAX = 168         # the longest hold, a week

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


def read_rows(pattern="videos_*.csv"):
    """{video_id: [(file name, row), ...]} across every index on disk."""
    out = {}
    for f in sorted(Path(".").glob(pattern)):
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


def fetch_captions(vid, work=WORK, source=None, timeout=300):
    """One recording's captions into work/<vid>/: (outcome, why).

    `source` replays instead of asking: source/<vid>/ holds the files yt-dlp
    would have written, or ERROR.txt with what it would have said.
    """
    d = Path(work) / vid
    existed = d.exists()
    d.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in d.iterdir()}
    if source:
        s = Path(source) / vid
        rc, said = 0, ""
        if (s / "ERROR.txt").exists():
            rc, said = 1, (s / "ERROR.txt").read_text(encoding="utf-8")
        elif s.is_dir():
            for f in sorted(s.glob("captions*")):
                shutil.copy2(f, d / f.name)
    else:
        cmd = [sys.executable] + YTDLP + [
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
    f = caption_file(vid, work)
    vtt = next(iter(sorted(d.glob("captions*.vtt"))), None)
    readable = False
    if f:
        import segment_markers
        readable = bool(segment_markers.read_words(d))
    outcome, why = classify(rc, said, f.name if f else None, vtt, readable)
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

    def note(self, now, why):
        n = int(self.record().get("count") or 0) + 1
        hours = min(HOLD_HOURS * 2 ** (n - 1), HOLD_MAX)
        self.table[self.origin] = {
            "at": iso(now), "why": why[:200], "count": n,
            "until": now.timestamp() + hours * 3600,
            "until_iso": iso(now + timedelta(hours=hours))}
        return hours

    def answered(self):
        r = self.table.get(self.origin)
        if r and r.get("count"):
            r.update(count=0, until=0, until_iso="")


def caption_queue(st, now, work=WORK):
    """The recordings whose captions are due tonight, oldest stream first.

    One still without auto-captions a week after its stream is taken to have
    none; one that failed three times for reasons that were not refusals is
    left for the laptop.
    """
    due = []
    for vid, v in st["videos"].items():
        if v.get("status") != "finished":
            continue
        c = v.get("captions")
        if c not in ("waiting", "deferred", "none-yet", "failed"):
            continue
        if c == "none-yet":
            ended = parse_iso(v.get("ended")) or parse_iso(v.get("seen"))
            if not ended or now - ended > timedelta(days=NONE_YET_DAYS):
                v["captions"] = "none-published"
                continue
        if c == "failed" and int(v.get("tries") or 0) >= MAX_TRIES:
            v["captions"] = "for-laptop"
            continue
        due.append(vid)
    due.sort(key=lambda x: (st["videos"][x].get("ended") or "", x))
    return due


def run_captions(st, vids, refusals, now, a, work=WORK, save=None):
    """One at a time, gently, and not one more after a refusal.

    Returns (Counter of outcomes, the refusal's words or None).
    """
    got = Counter()
    if vids and refusals.held(now):
        r = refusals.record()
        print(f"  captions: YouTube refused this machine at {r.get('at')} "
              f"({r.get('why')}). Nothing is asked of it until "
              f"{r.get('until_iso')}; {len(vids)} wait.")
        for vid in vids:
            st["videos"][vid]["captions"] = "deferred"
        got["deferred"] = len(vids)
        return got, r.get("why")
    t0, refused, in_a_row = time.time(), None, 0
    for i, vid in enumerate(vids):
        v = st["videos"][vid]
        if i >= a.max_captions or time.time() - t0 > a.budget * 60:
            got["left for tomorrow"] += len(vids) - i
            break
        if i and not a.captions_from:
            time.sleep(a.delay)
        outcome, why = fetch_captions(vid, work, a.captions_from, a.timeout)
        v["tried"] = iso(now)
        if outcome != "refused":
            got[outcome] += 1
        if outcome == "captioned":
            v.update(captions="captioned", fetched=iso(now), by=a.origin, why="")
            v.pop("tries", None)
            refusals.answered()
            in_a_row = 0
        elif outcome == "refused":
            v.update(captions="deferred", why=why)
            hours = refusals.note(now, why)
            refused = why
            for rest in vids[i + 1:]:
                st["videos"][rest]["captions"] = "deferred"
            got["deferred"] += len(vids) - i
            print(f"  {vid}: REFUSED -- {why}\n  Stopping. Nothing more is "
                  f"asked of YouTube from this machine for {hours} hours.")
        elif outcome == "none-yet":
            v.update(captions="none-yet", why=why)
            in_a_row = 0
        elif outcome == "not-aired":
            v.update(status="live", why=why)
        elif outcome == "gone":
            v.update(status="gone", why=why)
        else:
            v.update(captions="failed", why=why, tries=int(v.get("tries") or 0) + 1)
            in_a_row += 1
        if outcome != "refused":
            print(f"  {vid}: {outcome}"
                  + (f" ({why})" if outcome == "captioned" else f" -- {why}")
                  + f"   {str(v.get('title') or '')[:60]}")
        if save:
            save()
        if refused:
            break
        if in_a_row >= a.stop_after:
            got["left for tomorrow"] += len(vids) - i - 1
            print(f"  {in_a_row} failures in a row that were not refusals. "
                  "Stopping for tonight; the rest wait.")
            break
    return +got, refused


# ------------------------------------------------------------ carrying --

def carry_list(st=None):
    """What GitHub's machine is given for this step each night and sends back
    after it: download each one the bucket holds, upload each one that exists.

    Three small files and no caption file. The kit carries no captions, so
    what this step read off a recording travels in the state instead -- the
    candidate_segments.json entry segment_markers made and the caption-summary
    entry caption_span would make -- until the laptop has read the recording
    itself (see --markers and adopt).
    """
    return [p.as_posix() for p in (STATE, csv_path("house"), csv_path("senate"))]


def laptop_has(markers=MARKERS, summary=None):
    """The recordings the laptop has read, or None when this machine cannot
    tell.

    Read means both of the laptop's files name it: candidate_segments.json,
    what segment_markers found in its captions, and the caption summary,
    where they stop -- because once this step stops restoring a recording,
    the summary is all build_site_v2 has to check that its track is in step,
    and a recording with times and neither has its times withheld. Where
    there is no summary at all the first is enough.

    Both files are the laptop's only until the night's build writes its own
    copies, so once a site has been built on a machine that starts every
    night empty, this refuses to judge.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true" and Path("site/build.json").exists():
        print("  site/build.json is here, so the build has already run and "
              "candidate_segments.json is this machine's own. Nothing is "
              "judged taken over tonight. Run this step before build_all.")
        return None
    try:
        read = set(json.loads(Path(markers).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None
    summary = Path(summary or summary_path())
    if summary.exists():
        try:
            doc = json.loads(summary.read_text(encoding="utf-8"))
            read &= set((doc.get("recordings") or {}) if isinstance(doc, dict) else {})
        except (OSError, ValueError):
            return None
    return read


def summary_path():
    """caption_span's summary file, by its own name where it has one."""
    import caption_span
    return Path(getattr(caption_span, "SUMMARY", "caption_spans.json"))


def adopt(st, now, laptop):
    """Stop restoring what the laptop has read; its own files now answer."""
    n = 0
    for vid, v in st["videos"].items():
        if v.get("carry") and laptop is not None and vid in laptop:
            v.update(carry=False, adopted=now.strftime("%Y-%m-%d"))
            v.pop("result", None)
            v.pop("span", None)
            n += 1
    return n


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
                and (v.get("adopted") or v.get("by") != "runner")):
            del st["videos"][vid]


def span_of(folder):
    """The caption-summary entry for one recording, in caption_span's own
    shape: where its captions stop, and the size and date of each file that
    answer was read from."""
    import caption_span
    from segment_markers import WORK_FILES
    if hasattr(caption_span, "caption_files"):
        files = caption_span.caption_files(folder)
    else:
        files = {}
        for name in WORK_FILES:
            f = Path(folder) / name
            if f.exists():
                s = f.stat()
                files[name] = [s.st_size, int(s.st_mtime)]
    return {"last": caption_span.last_cue(folder), "files": files}


def store_results(st, vids, marks, work=WORK):
    """Keep what segment_markers read off these recordings, so the next night
    -- on a machine that will not have their captions -- can put it back."""
    n = 0
    for vid in vids:
        if vid not in marks:
            continue
        v = st["videos"][vid]
        v["result"] = {"segs": marks[vid],
                       "absent": (marks.get("_absent") or {}).get(vid),
                       "sequence": (marks.get("_sequence") or {}).get(vid)}
        v["span"] = span_of(Path(work) / vid)
        v["carry"] = True
        n += 1
    return n


def restore_results(st, markers=MARKERS, summary=None, work=WORK):
    """Put back what earlier nights read, for recordings whose captions are
    not on this machine. Only where the laptop's files have nothing for the
    recording: an answer the laptop made is never replaced by this one.
    Returns the recordings restored."""
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

    laptop = laptop_has() if a.origin == "runner" else None
    taken = adopt(st, now, laptop)
    if taken:
        print(f"  {taken} recording(s) the laptop has read need nothing more "
              "from this step")
    if a.origin == "runner":
        # A recording captioned here whose reading never reached the state --
        # build_all's --markers step did not run, or the docket named nothing
        # on it then and does now -- is asked for again, because its captions
        # did not come with this machine. Only those.
        import proceedings as P
        named = set(P.by_video(P.load()))
        again = [vid for vid, v in st["videos"].items()
                 if v.get("captions") == "captioned" and v.get("by") == "runner"
                 and not v.get("result") and not v.get("adopted")
                 and vid in named and not has_captions(vid)]
        for vid in again:
            st["videos"][vid].update(captions="waiting",
                                     why="read on no night yet; asked for again")
        if again:
            print(f"  {len(again)} recording(s) captioned on an earlier night "
                  "were never read into the state; asked for again")

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

    # Not asked for again: a recording the laptop has already read -- its
    # --catch-up, after a night YouTube refused this machine -- and one whose
    # captions are already on this disk.
    queue = caption_queue(st, now)
    for vid in list(queue):
        v = st["videos"][vid]
        if laptop is not None and vid in laptop:
            v.update(captions="captioned", by=v.get("by") or "laptop",
                     fetched=v.get("fetched") or iso(now),
                     adopted=now.strftime("%Y-%m-%d"), why="")
            queue.remove(vid)
        elif has_captions(vid):
            v.update(captions="captioned", by=v.get("by") or "found",
                     fetched=v.get("fetched") or iso(now), why="")
            queue.remove(vid)
    if queue and not yt_dlp_here(a):
        code = 3
        notes.append(f"not configured: yt-dlp is not installed here, so "
                     f"{len(queue)} recording(s) wait for captions")
        queue = []
    got, refused = run_captions(st, queue, refusals, now, a,
                                save=lambda: save_state(st))
    if refused:
        notes.append(f"captions deferred: YouTube refused ({refused})")

    prune(st, now)
    carried = sum(1 for v in st["videos"].values() if v.get("carry"))
    said = []
    if counts["new"] or counts["finished"]:
        said.append(f"{counts['new']} new on the channels, {counts['finished']} "
                    "now over and indexed"
                    + (f", {counts['not yet over']} not yet over"
                       if counts["not yet over"] else ""))
    if got:
        said.append("captions: " + ", ".join(f"{n} {k}" for k, n in got.items()))
    head = "; ".join(said) if said else "nothing new"
    tail = [f"holding {carried} reading(s) for the laptop"] if carried else []
    tail.append(f"{units} API unit{'' if units == 1 else 's'}")
    line = "LIVESTREAMS: " + head + "; " + ", ".join(tail) + \
        ("; " + "; ".join(notes) if notes else "")
    st["last_run"] = {"at": iso(now), "origin": a.origin, "units": units,
                      "verdict": line}
    save_state(st)
    print("\n" + line)
    return code


def catch_up(a):
    """On the laptop: caption the night's new recordings that are not here --
    the ones YouTube refused GitHub's machine, and the ones it captioned
    there, whose files the kit never brings back -- then read them.

    Reads the nightly's state and never writes it. That file is GitHub's, and
    a second writer is how one machine's night overwrites the other's. What
    this does reaches the nightly through the laptop's own two files: its
    candidate_segments.json, which segment_markers merges these into, and its
    caption summary, which the caption_span writer refreshes. Once both name a
    recording, the next night stops waiting for it, or stops holding its
    reading, and asks YouTube nothing about it again.
    """
    if a.origin == "runner":
        raise Broken("--catch-up is the laptop's; on GitHub's machine run "
                     "--since-state")
    now = utcnow(a.now)
    st = load_state()
    table = load_laptop_refusals()
    want = sorted((vid for vid, v in st["videos"].items()
                   if v.get("status") == "finished"
                   and v.get("captions") in ("waiting", "deferred", "failed",
                                             "for-laptop", "none-yet", "captioned")
                   and not v.get("adopted") and not has_captions(vid)),
                  key=lambda x: (st["videos"][x].get("ended") or "", x))
    was = Counter("captioned on GitHub's machine"
                  if st["videos"][v].get("captions") == "captioned"
                  else "not captioned there" for v in want)
    print(f"{len(want)} of the night's recording(s) have no captions here"
          + (": " + ", ".join(f"{n} {k}" for k, n in was.items()) if want else ""))
    shadow = {"videos": {vid: dict(st["videos"][vid], captions="waiting")
                         for vid in want}}
    if want and not yt_dlp_here(a):
        raise Broken("yt-dlp is not installed here: python3 -m pip install "
                     "yt-dlp, at the version the nightly pins")
    got, refused = run_captions(shadow, want, Refusals(table, "laptop"), now, a)
    atomic_write(LAPTOP_REFUSAL, json.dumps(table, indent=1) + "\n")
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
        print("\nThen send the laptop's candidate_segments.json and caption "
              "summary to the bucket with cloud.py, as after any caption job.")
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
    r = child.run([sys.executable, str(HERE / "caption_span.py"), "--write"])
    return 0 if r.returncode == 0 else 1


def markers(a):
    """build_all's step after the chair's boundaries: segment_markers over this
    step's recordings, and nothing else.

    Where their captions are on this machine it reads them, through
    segment_markers, which merges -- every other recording keeps the answer
    the laptop's caption job gave it. On the laptop, step 15 has just read
    them and this finds them in its cache. On GitHub's machine, where step 15
    does not run, this is where a new recording gets its times, and what was
    read is kept in the state; on the nights after, when the captions are not
    on the machine, it is put back into candidate_segments.json and the
    caption summary -- only where the laptop's copies have nothing for the
    recording -- until the laptop has read the recording itself.
    """
    try:
        st = load_state()
    except Broken as e:
        print(f"LIVESTREAMS MARKERS: broken -- {e}")
        return 1
    here = sorted(vid for vid, v in st["videos"].items()
                  if v.get("captions") == "captioned" and has_captions(vid))
    code = read_markers(here) if here else 0
    stored = back = 0
    if a.origin == "runner":
        try:
            marks = json.loads(MARKERS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            marks = {}
        stored = store_results(st, here, marks)
        back = len(restore_results(st))
        save_state(st)
    print(f"\nLIVESTREAMS MARKERS: {len(here)} recording(s) read"
          + (f", {stored} reading(s) kept for the nights after" if stored else "")
          + (f", {back} put back from earlier nights" if back else "")
          + ("" if not code else "; segment_markers did not finish"))
    return code


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
    r = child.run([sys.executable, str(HERE / "segment_markers.py"),
                   "--transcript", *folders, "--data", "data", "--quiet"])
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
    print(f"  {sum(1 for v in vids.values() if v.get('carry'))} reading(s) held "
          "for the laptop, put back each night until it has read them")
    for origin, r in sorted((st.get("refusals") or {}).items()):
        if r.get("count"):
            print(f"  YouTube refused the {origin} at {r.get('at')} "
                  f"({r.get('why')}); held until {r.get('until_iso')}")
    lr = st.get("last_run") or {}
    if lr:
        print(f"  last run {lr.get('at')} on the {lr.get('origin')}:\n    "
              f"{lr.get('verdict', '')}")
    return 0


class lock:
    """One run of this step at a time on one machine."""

    def __enter__(self):
        if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 2 * 3600:
            raise Broken(f"{LOCK} is held "
                         f"({LOCK.read_text(encoding='utf-8').strip()}): "
                         "another run of this step is going")
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        LOCK.write_text(f"pid {os.getpid()}", encoding="utf-8")
        return self

    def __exit__(self, *exc):
        LOCK.unlink(missing_ok=True)
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--since-state", action="store_true",
                      help="the nightly step: list, index, caption")
    mode.add_argument("--catch-up", action="store_true",
                      help="on the laptop: caption what the nightly could not")
    mode.add_argument("--markers", action="store_true",
                      help="build_all's step: segment_markers over this step's "
                           "recordings only")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--carry", action="store_true",
                      help="the files carried between nights, one a line")
    ap.add_argument("--max-captions", type=int, default=20,
                    help="caption requests a night (default 20)")
    ap.add_argument("--delay", type=float, default=20.0,
                    help="seconds between caption requests (default 20)")
    ap.add_argument("--budget", type=float, default=45.0,
                    help="minutes of caption requests a night (default 45)")
    ap.add_argument("--timeout", type=float, default=300.0,
                    help="seconds allowed for one recording's captions")
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
