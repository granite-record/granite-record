// YouTube's Data API v3 as a function, for tests: synthetic answers in the
// shape its reference documents, from a world of streams that are scheduled,
// start and end on a clock the test moves. Nothing here was recorded from
// YouTube (developer policy III.E.4.d keeps its data 30 days at most).
//
// A video is { id, chamber, title, scheduled, start, end, listedAt, ... } in
// milliseconds:
//   scheduled   its scheduled start, or null for a stream nobody scheduled
//   start, end  when it went live and ended (null: not yet, or never)
//   listedAt    when it entered its channel's uploads playlist: the day it
//               was scheduled, or for a stream nobody scheduled, its start
//               when the playlist carries it while live and its end when not
//               (streams.md's open question; both are tried)
//   cancelledAt when a scheduled stream stopped being upcoming, never started
//   upload      an ordinary video, no broadcast
//   searchLag   how long after its start search.list finds it
// The playlist is ordered as YouTube orders it: by the listing time, until a
// stream ends, and then by its end, since YouTube rewrites the publish time
// of a stream that has ended.
import { CHANNELS } from "../../workers/live/live.gen.js";
import { readFileSync } from "node:fs";

export const KEY = "synthetic-key-for-tests-only";
export const ITEMS = JSON.parse(readFileSync(new URL("./youtube_items.json", import.meta.url), "utf8"));
const NAMES = { H: "NH House of Representatives Committee Streaming", S: "New Hampshire Senate Livestream" };
const iso = t => new Date(t).toISOString().replace(/\.\d{3}Z$/, "Z");
const uploadsOf = c => "UU" + CHANNELS[c].slice(2);

function answer(status, body) {
  return new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json; charset=UTF-8" } });
}

function badRequest(message, reason = "badRequest") {
  return answer(400, { error: { code: 400, message, errors: [{ message, domain: "global", reason }] } });
}

export class FakeYouTube {
  constructor({ clock, key = KEY } = {}) {
    this.clock = clock;
    this.key = key;
    this.videos = new Map();
    this.calls = [];
    this.errors = [];        // [{ method, status, body }], each used once, in order
    this.hang = null;        // a method that never answers, until its signal aborts
  }

  add(v) {
    const spec = { scheduled: null, start: null, end: null, cancelledAt: null, upload: false,
                   embeddable: true, searchLag: 0, ...v };
    if (spec.listedAt === undefined) spec.listedAt = spec.start;
    this.videos.set(spec.id, spec);
    return spec;
  }

  // Answer the next call of `method` ("*" for any) with one of
  // youtube_items.json's errors.
  fail(method, kind, times = 1) {
    for (let i = 0; i < times; i++) this.errors.push({ method, ...ITEMS.errors[kind] });
  }

  exists(v, now) {
    const from = Math.min(v.listedAt ?? Infinity, v.start ?? Infinity);
    return now >= from;
  }

  order(v, now) {
    return v.end != null && now >= v.end ? v.end : v.listedAt;
  }

  item(v, now, parts) {
    const started = v.start != null && now >= v.start;
    const ended = v.end != null && now >= v.end;
    let lbc = "none";
    if (!v.upload) {
      if (started && !ended) lbc = "live";
      else if (!started && v.scheduled != null && !(v.cancelledAt != null && now >= v.cancelledAt)) lbc = "upcoming";
    }
    const it = { kind: "youtube#video", etag: `synthetic-${v.id}-${lbc}`, id: v.id };
    if (parts.has("snippet")) {
      it.snippet = { publishedAt: iso(this.order(v, now)), channelId: CHANNELS[v.chamber], title: v.title,
                     description: "", thumbnails: {}, channelTitle: NAMES[v.chamber], categoryId: "25",
                     liveBroadcastContent: lbc, localized: { title: v.title, description: "" } };
    }
    if (parts.has("liveStreamingDetails") && !v.upload) {
      const ls = {};
      if (v.scheduled != null) ls.scheduledStartTime = iso(v.scheduled);
      if (started) ls.actualStartTime = iso(v.start);
      if (ended) ls.actualEndTime = iso(v.end);
      if (started && !ended) ls.concurrentViewers = "12";
      it.liveStreamingDetails = ls;
    }
    if (parts.has("status")) {
      it.status = { uploadStatus: ended || v.upload ? "processed" : "uploaded", privacyStatus: "public",
                    license: "youtube", embeddable: v.embeddable, publicStatsViewable: true, madeForKids: false };
    }
    return it;
  }

  playlist(chamber, now, max) {
    return [...this.videos.values()]
      .filter(v => v.chamber === chamber && v.listedAt != null && now >= v.listedAt)
      .sort((a, b) => this.order(b, now) - this.order(a, now) || (a.id < b.id ? -1 : 1))
      .slice(0, max);
  }

  // The fetch the Worker is given.
  fetch = async (url, init = {}) => {
    const u = new URL(String(url));
    const method = u.pathname.split("/").pop();
    const params = Object.fromEntries(u.searchParams);
    const now = +this.clock();
    const { key, ...asked } = params;
    this.calls.push({ method, params: asked, at: now, keyed: key === this.key });
    if (u.origin + u.pathname.slice(0, u.pathname.lastIndexOf("/") + 1) !== "https://www.googleapis.com/youtube/v3/") {
      throw new Error(`the Worker asked ${u.origin}${u.pathname}, which is not YouTube's Data API`);
    }
    if (this.hang === method) {
      return new Promise((_, reject) => {
        init.signal.addEventListener("abort", () => reject(init.signal.reason));
      });
    }
    const at = this.errors.findIndex(e => e.method === method || e.method === "*");
    if (at >= 0) {
      const [e] = this.errors.splice(at, 1);
      return answer(e.status, e.body);
    }
    if (key !== this.key) return answer(ITEMS.errors.key_invalid.status, ITEMS.errors.key_invalid.body);
    const parts = new Set((params.part || "").split(",").filter(Boolean));
    if (!parts.size) return badRequest("No filter selected. Expected one of: ...", "missingRequiredParameter");
    const max = params.maxResults === undefined ? 5 : Number(params.maxResults);
    if (!(max >= 0 && max <= 50)) return badRequest("Invalid value for parameter maxResults.", "invalidParameter");

    if (method === "channels") {
      const items = (params.id || "").split(",").filter(Boolean)
        .map(id => Object.entries(CHANNELS).find(([, cid]) => cid === id))
        .filter(Boolean)
        .map(([c, id]) => ({ kind: "youtube#channel", etag: `synthetic-${id}`, id,
                             contentDetails: { relatedPlaylists: { likes: "", uploads: uploadsOf(c) } } }));
      return answer(200, { kind: "youtube#channelListResponse", etag: "synthetic",
                           pageInfo: { totalResults: items.length, resultsPerPage: 5 }, items });
    }
    if (method === "playlistItems") {
      const chamber = Object.keys(CHANNELS).find(c => uploadsOf(c) === params.playlistId);
      if (!chamber) return answer(ITEMS.errors.playlist_not_found.status, ITEMS.errors.playlist_not_found.body);
      const listed = this.playlist(chamber, now, max);
      return answer(200, {
        kind: "youtube#playlistItemListResponse", etag: "synthetic", nextPageToken: "synthetic-next",
        items: listed.map(v => ({ kind: "youtube#playlistItem", etag: `synthetic-${v.id}`, id: `pl-${v.id}`,
                                  contentDetails: { videoId: v.id, videoPublishedAt: iso(this.order(v, now)) } })),
        pageInfo: { totalResults: 9999, resultsPerPage: max } });
    }
    if (method === "videos") {
      const ids = (params.id || "").split(",").filter(Boolean);
      if (params.maxResults !== undefined) {
        return badRequest("The request specifies an unsupported maxResults with the id parameter.", "unsupportedFilter");
      }
      if (ids.length > 50) return badRequest("More than 50 ids.", "invalidParameter");
      const items = ids.map(id => this.videos.get(id)).filter(v => v && this.exists(v, now))
        .map(v => this.item(v, now, parts));
      return answer(200, { kind: "youtube#videoListResponse", etag: "synthetic", items,
                           pageInfo: { totalResults: items.length, resultsPerPage: items.length } });
    }
    if (method === "search") {
      if (params.eventType && params.type !== "video") {
        return badRequest("eventType requires type=video.", "invalidSearchFilter");
      }
      const chamber = Object.keys(CHANNELS).find(c => CHANNELS[c] === params.channelId);
      const items = [...this.videos.values()].filter(v => v.chamber === chamber && !v.upload
          && v.start != null && now >= v.start + v.searchLag && !(v.end != null && now >= v.end))
        .slice(0, max)
        .map(v => ({ kind: "youtube#searchResult", etag: `synthetic-${v.id}`,
                     id: { kind: "youtube#video", videoId: v.id },
                     snippet: { publishedAt: iso(v.start), channelId: CHANNELS[v.chamber], title: v.title,
                                description: "", thumbnails: {}, channelTitle: NAMES[v.chamber],
                                liveBroadcastContent: "live", publishTime: iso(v.start) } }));
      return answer(200, { kind: "youtube#searchListResponse", etag: "synthetic", regionCode: "US",
                           pageInfo: { totalResults: items.length, resultsPerPage: max }, items });
    }
    return answer(404, { error: { code: 404, message: "Not Found", errors: [] } });
  };

  // What was spent, as YouTube counts it: search.list from its own
  // allowance, everything else a unit a call.
  spent(from = -Infinity, to = Infinity) {
    const inside = this.calls.filter(c => c.at >= from && c.at < to);
    return { units: inside.filter(c => c.method !== "search").length,
             searches: inside.filter(c => c.method === "search").length };
  }
}
