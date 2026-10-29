/*
 * The YouTube half: which House and Senate streams are live, scheduled for
 * today, or ended today, asked of YouTube's Data API with YOUTUBE_API_KEY and
 * nothing else. It never reads the site and never asks the General Court.
 *
 * WHAT ONE LOOK ASKS (clock.js says when each is due):
 *   playlistItems.list   each chamber's uploads playlist, newest 50 (50 costs
 *                        what 10 does): 1 unit each
 *   videos.list          snippet, liveStreamingDetails and status for up to
 *                        50 ids a call, 1 unit: the ids new to the playlists,
 *                        the ids live, the upcoming ids due from two hours ago
 *                        to the end of today -- or, on the day's first run in
 *                        the window, every upcoming id kept
 *   search.list          eventType=live on each channel, every 30 minutes in
 *                        the window: search's own allowance of 100 calls a day
 *   channels.list        once, to confirm each uploads playlist (1 unit), and
 *                        again only if state.json is lost or has forgotten
 *                        them (YouTube switched off, or 30 days unanswered)
 * About 1,270 units of the project's 10,000 on a weekday, and 52 searches
 * (tests/live/youtube.test.js counts them over a simulated week).
 *
 * PRE-SCHEDULED STREAMS ARE KEPT. A House stream scheduled weeks ahead keeps
 * its scheduling-date place in the uploads list until it ends, so a newer 50
 * can push it out. Every upcoming id seen is kept in state.json with its
 * scheduled start until its day has passed, and re-asked on the first run in
 * the window each day: that refresh is also what keeps it inside YouTube's
 * 30 days (developer policy III.E.4.d), and an id not refreshed for 30
 * calendar days is dropped all the same.
 *
 * STATUS (statusOf) is livestreams.status_of's reading of the same fields,
 * with one difference: a stream whose liveStreamingDetails has an
 * actualEndTime has ended, even while YouTube still reports its length as
 * P0D, because the page wants the end. preflight's _live_layer runs
 * status_of on tests/live/youtube_items.json and holds the two together.
 *
 * WHAT IS WRITTEN is streams/<New Hampshire date>.json (fileOf): today's live,
 * upcoming and ended streams. On a failed look the file keeps what the last
 * good look found and its time, and says the problem (status.ok false), so a
 * failure is said as a failure and never read as "nothing is live". The key
 * is sent in the query string, as YouTube asks, and is never in a message, a
 * log line or a file: errors name the method and the status alone.
 *
 * WHAT state.json KEEPS OF YOUTUBE (forget) is only what the next look
 * needs: the upcoming ids, the ids live, the last playlist reads and the
 * uploads playlists. None of it outlives 30 calendar days unrefreshed, even
 * through a month of failed looks, and all of it goes the day control.json
 * turns YouTube off (index.js).
 */
import { CHANNELS, SESSION_TITLE } from "./live.gen.js";
import { addDays } from "../follow/common.js";
import { HOUR, NEW_YORK, PACIFIC, iso, midnightAfter, nextLook, nh } from "./clock.js";

export const API = "https://www.googleapis.com/youtube/v3/";
export const TIMEOUT_MS = 8000;
export const PAGE = 50;
export const KEEP_DAYS = 30;
// A failed look is counted; at this many in a row, Healthchecks hears /fail.
export const FAILS_TO_TELL = 5;
// A stream videos.list leaves out is kept as last seen for this many looks in
// a row, and dropped at the next: deleted, made private, or YouTube's slip.
export const MISSES_TO_DROP = 3;

export const CHAMBERS = ["H", "S"];
export const CHAMBER_OF = Object.fromEntries(Object.entries(CHANNELS).map(([c, id]) => [id, c]));
export const uploadsOf = channel => "UU" + channel.slice(2);

// ---- titles -------------------------------------------------------------------
// live_gen.py's stem(), held to it on every committed title by preflight.
const DATE_TAIL = /\(\s*[0-9]{1,2}\/[0-9]{1,2}\/[0-9]{2,4}[\s\S]*$/;
export function stem(title) {
  const t = String(title || "").replace(DATE_TAIL, "").toLowerCase().replace(/&/g, " and ");
  return (t.match(/[a-z0-9]+/g) || []).join(" ");
}

const SESSION = Object.entries(SESSION_TITLE).map(([c, source]) => [c, new RegExp(source)]);
// "H" or "S" when the title is that chamber's session stream, else null.
export function sessionOf(title) {
  const s = stem(title);
  for (const [c, re] of SESSION) if (re.test(s)) return c;
  return null;
}

// ---- status -------------------------------------------------------------------
// live | upcoming | ended | never (scheduled, never started, no longer
// upcoming: cancelled) | upload (no broadcast at all: an ordinary video).
export function statusOf(item) {
  const ls = item && item.liveStreamingDetails;
  if (!ls) return "upload";
  if (ls.actualEndTime) return "ended";
  const lbc = (item.snippet && item.snippet.liveBroadcastContent) || "none";
  if (lbc === "live" || lbc === "upcoming") return lbc;
  // Started, not ended, and no longer said to be live: kept as live and asked
  // again, as livestreams.status_of keeps it.
  if (ls.actualStartTime) return "live";
  return "never";
}

// ---- asking -------------------------------------------------------------------
export class YouTubeError extends Error {
  constructor(problem, detail) {
    super(detail);
    this.problem = problem;      // "quota" | "key" | "youtube"
    this.detail = detail;
  }
}

const QUOTA = new Set(["quotaExceeded", "dailyLimitExceeded", "RATE_LIMIT_EXCEEDED_DAILY"]);
const KEY = new Set(["keyInvalid", "keyExpired", "forbidden", "accessNotConfigured",
                     "ipRefererBlocked", "API_KEY_INVALID", "API_KEY_EXPIRED",
                     "API_KEY_SERVICE_BLOCKED", "API_KEY_HTTP_REFERRER_BLOCKED",
                     "API_KEY_IP_ADDRESS_BLOCKED", "SERVICE_DISABLED"]);

// The reasons in an error answer, from both places YouTube puts them.
export function reasonsOf(body) {
  const e = (body && body.error) || {};
  return [...(e.errors || []), ...(e.details || [])].map(x => x && x.reason).filter(Boolean);
}

// quota: held to midnight Pacific. key: a refused or missing key, held for
// the rest of New Hampshire's day. youtube: anything else, tried again at the
// next look.
export function problemOf(status, body) {
  const reasons = reasonsOf(body);
  if (reasons.some(r => QUOTA.has(r))) return "quota";
  if (status === 401 || reasons.some(r => KEY.has(r))) return "key";
  return "youtube";
}

async function ask(fetchImpl, key, method, params, tally, timeoutMs) {
  const url = `${API}${method}?${new URLSearchParams({ ...params, key })}`;
  // Counted before it is sent: a request YouTube refuses still costs.
  if (method === "search") tally.searches++; else tally.units++;
  let r;
  try {
    r = await fetchImpl(url, { headers: { Accept: "application/json" },
                               signal: AbortSignal.timeout(timeoutMs) });
  } catch (e) {
    const late = e && (e.name === "TimeoutError" || e.name === "AbortError");
    throw new YouTubeError("youtube", `${method}: ${late ? `no answer in ${timeoutMs / 1000} s` : "no answer"}`);
  }
  let body = null;
  try { body = await r.json(); } catch { /* not JSON: said below */ }
  if (!r.ok || !body || body.error) {
    const why = reasonsOf(body)[0];
    throw new YouTubeError(problemOf(r.status, body), `${method}: HTTP ${r.status}${why ? ` ${why}` : ""}`);
  }
  return body;
}

// ---- the file -------------------------------------------------------------------
export const streamsKey = day => `streams/${day}.json`;

const dayOf = when => (when && Number.isFinite(Date.parse(when)) ? nh(Date.parse(when)).date : null);

// Today's file as the last run left it, or an empty one for a new day.
function base(prev, today) {
  const same = prev && prev.kind === "live.streams" && prev.day === today;
  return {
    kind: "live.streams", day: today,
    checked: same ? prev.checked || null : null,
    next_check: same ? prev.next_check || null : null,
    status: same && prev.status ? prev.status : { ok: true, problem: null, since: null },
    streams: same && Array.isArray(prev.streams) ? prev.streams : [],
  };
}

function said(prev, today, problem, at, next) {
  const f = base(prev, today);
  const since = f.status && f.status.problem === problem ? f.status.since : at;
  return { ...f, next_check: next, status: { ok: false, problem, since } };
}

// The file a run writes when control.json says "youtube": "off": what was
// last checked stays, and the page says the Worker was turned off.
export function offFile(prev, today, at) {
  return said(prev, today, "off", at, null);
}

function entry(item, old, chamberHint) {
  const sn = item.snippet || {};
  const ls = item.liveStreamingDetails || {};
  const st = item.status || {};
  return {
    video: item.id,
    chamber: CHAMBER_OF[sn.channelId] || chamberHint || (old && old.chamber) || null,
    title: sn.title || (old && old.title) || "",
    status: statusOf(item),
    scheduled: ls.scheduledStartTime || null,
    started: ls.actualStartTime || null,
    ended: ls.actualEndTime || null,
    embeddable: typeof st.embeddable === "boolean" ? st.embeddable : null,
    seen: { playlist: (old && old.seen && old.seen.playlist) || null,
            search: (old && old.seen && old.seen.search) || null },
  };
}

// ---- what state.json keeps ------------------------------------------------------
// YouTube's data in `yt`, dropped once 30 calendar days old (III.E.4.d): an
// upcoming id by the day it was last answered, or once its day has passed;
// the playlist reads, the ids live, the misses and the uploads playlists by
// the last discovery that worked. Run on every run that holds the lease, so a
// month of failed looks keeps nothing longer than a month. It changes `yt`
// in place and returns it.
export function forget(yt, now) {
  if (!yt) return yt;
  const today = nh(now).date, oldest = addDays(today, -KEEP_DAYS);
  for (const [id, u] of Object.entries(yt.upcoming || {})) {
    const day = u && dayOf(u.at), seen = u && dayOf(u.seen);
    if ((day && day < today) || !seen || seen <= oldest) delete yt.upcoming[id];
  }
  const listed = dayOf(yt.listed);
  if (!listed || listed <= oldest) {
    for (const k of ["lists", "live", "gone", "uploads", "listed"]) delete yt[k];
  }
  return yt;
}

// ---- one look -------------------------------------------------------------------
// `yt` is state.json's yt as read, `prev` today's streams file as it stands
// (or null), `due` clock.youtubeDue's answer. Returns the new yt, the file to
// write, what was spent, and what Healthchecks must hear:
//   { yt, file, tally, problem, detail, fail, notes }
export async function look({ key, fetchImpl = fetch, now, yt: before = {}, prev = null, due,
                             timeoutMs = TIMEOUT_MS }) {
  const t = +now, at = iso(now), today = nh(now).date;
  const yt = JSON.parse(JSON.stringify(before || {}));
  yt.upcoming = yt.upcoming || {};
  yt.live = yt.live || [];
  const tally = { units: 0, searches: 0 };
  const notes = [];
  let searchFail = null;
  const call = (method, params) => ask(fetchImpl, key, method, params, tally, timeoutMs);
  // Each interval runs from this look whether it worked or not, so a failing
  // YouTube is asked at the usual cadence and no faster.
  if (due.discover) yt.discovery = at;
  if (due.discover || due.live) yt.looked = at;
  if (due.search) yt.search = at;

  try {
    if (!key) throw new YouTubeError("key", "no YOUTUBE_API_KEY secret");
    if (due.discover && !(yt.uploads && yt.uploads.H && yt.uploads.S)) {
      const body = await call("channels", { part: "contentDetails", id: `${CHANNELS.H},${CHANNELS.S}` });
      const got = {};
      for (const it of body.items || []) {
        const u = it && it.contentDetails && it.contentDetails.relatedPlaylists
          && it.contentDetails.relatedPlaylists.uploads;
        if (CHAMBER_OF[it && it.id] && u) got[CHAMBER_OF[it.id]] = u;
      }
      if (!got.H || !got.S) throw new YouTubeError("youtube", "channels: a chamber's channel was not answered");
      for (const c of CHAMBERS) {
        if (got[c] !== uploadsOf(CHANNELS[c])) notes.push(`uploads ${c} is ${got[c]}, not UU of its channel`);
      }
      yt.uploads = got;
      if (!yt.listed) yt.listed = at;     // so forget() keeps them while discovery is failing
    }

    // The uploads playlists, and which of their ids are new since the last read.
    const lists = {}, fresh = new Map();
    if (due.discover) {
      for (const c of CHAMBERS) {
        const body = await call("playlistItems", { part: "contentDetails", playlistId: yt.uploads[c],
                                                   maxResults: String(PAGE) });
        lists[c] = (body.items || []).map(i => i && i.contentDetails && i.contentDetails.videoId)
          .filter(Boolean);
        const known = new Set(((yt.lists || {})[c]) || []);
        for (const id of lists[c]) if (!known.has(id)) fresh.set(id, c);
      }
    }

    // The backstop: what search says is live on each channel.
    const found = new Map();
    if (due.search) {
      try {
        for (const c of CHAMBERS) {
          const body = await call("search", { part: "snippet", channelId: CHANNELS[c], eventType: "live",
                                              type: "video", maxResults: String(PAGE) });
          for (const it of body.items || []) if (it && it.id && it.id.videoId) found.set(it.id.videoId, c);
        }
      } catch (e) {
        // Search has its own allowance: running out of it holds search alone.
        // A refused key is the whole half's; anything else waits 30 minutes.
        if (!(e instanceof YouTubeError) || e.problem === "key") throw e;
        if (e.problem === "quota") {
          yt.search_held = iso(midnightAfter(now, PACIFIC));
          searchFail = `search's own allowance is spent: search waits for midnight Pacific, the playlists are still read (${e.detail})`;
        }
        notes.push(e.problem === "quota" ? "search held to midnight Pacific" : `search failed (${e.detail})`);
      }
    }

    // Which ids to ask after.
    const asked = new Set();
    if (due.discover) for (const id of fresh.keys()) asked.add(id);
    for (const id of found.keys()) asked.add(id);
    if (due.discover || due.live) for (const id of yt.live) asked.add(id);
    if (due.discover) {
      const endOfToday = +midnightAfter(now, NEW_YORK);
      for (const [id, u] of Object.entries(yt.upcoming)) {
        const s = Date.parse(u.at);
        if (due.refresh || (s >= t - 2 * HOUR && s < endOfToday)) asked.add(id);
      }
    }
    const items = new Map();
    const ids = [...asked];
    for (let i = 0; i < ids.length; i += PAGE) {
      const body = await call("videos", { part: "snippet,liveStreamingDetails,status",
                                          id: ids.slice(i, i + PAGE).join(",") });
      for (const it of body.items || []) if (it && it.id) items.set(it.id, it);
    }

    // A stream already known that videos.list left out is kept as last seen,
    // up to MISSES_TO_DROP looks in a row; an id never known is let go.
    const f = base(prev, today);
    const byId = new Map(f.streams.map(s => [s.video, s]));
    const misses = {};
    for (const id of asked) {
      if (items.has(id) || !(yt.live.includes(id) || id in yt.upcoming || byId.has(id))) continue;
      const n = ((yt.gone || {})[id] || 0) + 1;
      if (n <= MISSES_TO_DROP) misses[id] = n;
    }
    const missed = Object.keys(misses).length;
    if (missed) notes.push(`${missed} known stream(s) left out by videos.list, kept as last seen`);

    // What state.json keeps for the next look.
    if (due.discover) { yt.lists = lists; yt.listed = at; }
    if (due.refresh) yt.refreshed = today;
    const live = new Set(yt.live);
    for (const id of asked) {
      if (id in misses) continue;
      const it = items.get(id);
      const st = it ? statusOf(it) : "gone";
      if (st === "live") live.add(id); else live.delete(id);
      if (st === "upcoming") {
        yt.upcoming[id] = { at: (it.liveStreamingDetails || {}).scheduledStartTime || null, seen: at };
      } else {
        delete yt.upcoming[id];
      }
    }
    yt.live = [...live];
    if (missed) yt.gone = misses; else delete yt.gone;
    forget(yt, now);
    yt.fails = 0;
    if (yt.held) yt.held = null;

    // Today's file: what was there, with every stream asked about brought up
    // to date, and the time each path first saw it today.
    const inList = new Map();
    for (const c of CHAMBERS) for (const id of lists[c] || []) inList.set(id, c);
    for (const id of asked) {
      if (id in misses) continue;                         // kept as it was
      const it = items.get(id);
      const old = byId.get(id);
      if (!it) { byId.delete(id); continue; }            // gone: deleted or made private
      const st = statusOf(it);
      const ls = it.liveStreamingDetails || {};
      const keep = st === "live"
        || (st === "upcoming" && dayOf(ls.scheduledStartTime) === today)
        || (st === "ended" && (Boolean(old) || dayOf(ls.actualEndTime) === today
                               || dayOf(ls.actualStartTime) === today));
      if (!keep) { byId.delete(id); continue; }
      byId.set(id, entry(it, old, found.get(id) || inList.get(id) || fresh.get(id)));
    }
    for (const s of byId.values()) {
      s.seen = { playlist: null, search: null, ...(s.seen || {}) };
      if (!s.seen.playlist && inList.has(s.video)) s.seen.playlist = at;
      if (!s.seen.search && found.has(s.video)) s.seen.search = at;
    }
    const order = s => s.started || s.scheduled || s.ended || "";
    const streams = [...byId.values()].sort((a, b) =>
      order(a) < order(b) ? -1 : order(a) > order(b) ? 1 : a.video < b.video ? -1 : 1);
    const file = { kind: "live.streams", day: today, checked: at, next_check: iso(nextLook(now, yt)),
                   status: { ok: true, problem: null, since: null }, streams };
    return { yt, file, tally, problem: null, detail: null, fail: searchFail, notes };
  } catch (e) {
    if (!(e instanceof YouTubeError)) throw e;
    let fail = null;
    if (e.problem === "quota") {
      yt.held = { why: "quota", until: iso(midnightAfter(now, PACIFIC)), since: at };
      fail = `YouTube's quota is spent: the YouTube half waits for midnight Pacific (${e.detail})`;
    } else if (e.problem === "key" && !key) {
      // Not held: YouTube was not asked, and the first run after the person
      // puts the secret uses it.
      fail = "there is no YOUTUBE_API_KEY secret, so YouTube was not asked: README.md says how to put it";
    } else if (e.problem === "key") {
      // Held for the rest of New Hampshire's day, as a refused key should be.
      // To try a new key sooner, the person turns YouTube off and on again
      // (README.md): turning it off clears the hold with the rest.
      yt.held = { why: "key", until: iso(midnightAfter(now, NEW_YORK)), since: at };
      fail = `YouTube refused the key: the YouTube half waits for tomorrow, or a new key (${e.detail})`;
    } else {
      yt.fails = (yt.fails || 0) + 1;
      if (yt.fails >= FAILS_TO_TELL) fail = `${yt.fails} looks at YouTube in a row have failed (${e.detail})`;
    }
    const file = said(prev, today, e.problem, at, iso(nextLook(now, yt)));
    return { yt, file, tally, problem: e.problem, detail: e.detail, fail, notes };
  }
}
