// A committee's page: its live stream at the top (the live layer's design,
// section 1.6), live.js's startCommittee under node after components.js: no
// request outside the Worker's window, at a weekend or with no hook; the
// committee's own stream and not a session stream or another committee's; a
// card with a stub and no frame; a refresh keeping a playing frame; an end
// removing the card, or keeping the player with "Ended at"; stale and 404
// saying nothing; one player at a time; and the forbidden sentences never.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { WINDOW } from "../../workers/live/live.gen.js";

const read = rel => readFileSync(new URL(`../../${rel}`, import.meta.url), "utf8");
function load(extra = {}) {
  const ctx = vm.createContext({ console, Intl, Date, Math, JSON, Promise, setTimeout, clearTimeout, ...extra });
  ctx.window = ctx;
  vm.runInContext(read("src/pages/components.js"), ctx, { filename: "components.js" });
  vm.runInContext(read("src/pages/live.js"), ctx, { filename: "live.js" });
  return ctx;
}
const L = load().GRLive;
const T = s => Date.parse(s);
const MATCH = ["house finance", "finance", "house finance division i"];

const streams = (over = {}) => ({ kind: "live.streams", day: "2027-01-07", checked: "2027-01-07T15:20:00Z",
  next_check: "2027-01-07T15:22:00Z", status: { ok: true, problem: null, since: null }, streams: [], ...over });
const s = over => ({ video: "AAAAAAAAAAA", chamber: "H", title: "House Finance (01/07/2027)", status: "live",
  scheduled: "2027-01-07T15:00:00Z", started: "2027-01-07T15:02:00Z", ended: null, embeddable: true, ...over });

// The hook and the cards live.js makes, deep enough for startCommittee.
function page({ match = MATCH, chamber = "H", win = WINDOW } = {}) {
  const mk = (tag = "div") => {
    const e = { tagName: tag, attrs: {}, children: [], hidden: false, _html: "", className: "",
      setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k] ?? null; },
      appendChild(c) { c.parent = this; this.children.push(c); return c; },
      remove() { if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); this.gone = true; },
      querySelector(sel) {
        if (sel === "iframe") return this.frame || null;
        this.parts = this.parts || {};
        return (this.parts[sel] = this.parts[sel] || mk());
      } };
    Object.defineProperty(e, "innerHTML", { get() { return this._html; }, set(v) { this._html = String(v); this.parts = {}; } });
    return e;
  };
  const hook = mk("section");
  hook.hidden = true;
  Object.assign(hook.attrs, { "data-committee": "H09", "data-chamber": chamber, "data-name": "House Finance",
                              "data-match": JSON.stringify(match), "data-window": JSON.stringify(win) });
  const doc = { hidden: false, _on: {}, getElementById: id => (id === "live-now" ? hook : null), createElement: mk,
                addEventListener(t, f) { (this._on[t] = this._on[t] || []).push(f); } };
  return { doc, hook };
}
function server(answers) {
  const asked = [];
  const fetch = async (url, init) => {
    asked.push([url, (init && init.headers && init.headers["If-None-Match"]) || null]);
    const a = typeof answers === "function" ? answers(url) : answers[url];
    if (!a) return { status: 404, ok: false, headers: { get: () => null }, json: async () => null };
    return { status: a.status || 200, ok: (a.status || 200) === 200, headers: { get: () => a.etag || '"e"' }, json: async () => a.body };
  };
  return { fetch, asked };
}
const timers = () => { const t = []; return { t, ctx: load({ setTimeout: (f, ms) => { t.push(ms); return t.length; }, clearTimeout: () => {} }) }; };

test("the window is the Worker's: weekdays 07:00 to 20:00 New Hampshire time, from live.gen.js", () => {
  assert.deepEqual({ ...WINDOW }, { from: 7, to: 20 });
  assert.equal(L.inWindow(T("2027-01-07T12:00:00Z"), WINDOW), true, "a Thursday at 07:00 EST");
  assert.equal(L.inWindow(T("2027-01-07T11:59:00Z"), WINDOW), false, "06:59");
  assert.equal(L.inWindow(T("2027-01-08T00:59:00Z"), WINDOW), true, "19:59");
  assert.equal(L.inWindow(T("2027-01-08T01:00:00Z"), WINDOW), false, "20:00");
  assert.equal(L.inWindow(T("2027-01-09T16:00:00Z"), WINDOW), false, "a Saturday");
  assert.equal(L.inWindow(T("2027-01-10T16:00:00Z"), WINDOW), false, "a Sunday");
  assert.equal(L.inWindow(T("2027-07-07T11:00:00Z"), WINDOW), true, "07:00 EDT");
});

test("no request outside the window, at a weekend, or with no hook", async () => {
  for (const at of ["2027-01-07T11:30:00Z", "2027-01-08T02:00:00Z", "2027-01-09T16:00:00Z"]) {
    const { doc } = page();
    const { fetch, asked } = server({ "/api/live/streams": { body: streams() } });
    const p = L.startCommittee(doc, { fetch, now: () => T(at) });
    try { await p.first; assert.deepEqual(asked, [], at); } finally { p.stop(); }
  }
  const none = { hidden: false, getElementById: () => null, addEventListener() {} };
  assert.equal(L.startCommittee(none, { fetch: () => { throw new Error("asked"); } }), null);
});

test("the committee's own stream, and not a session stream or another committee's", () => {
  assert.equal(L.isCommittees(s({}), MATCH, "H"), true);
  assert.equal(L.isCommittees(s({ title: "House Finance Division I Work Session (01/07/2027)" }), MATCH, "H"), true);
  assert.equal(L.isCommittees(s({ title: "Finance (1/7/27 - morning session)" }), MATCH, "H"), true);
  assert.equal(L.isCommittees(s({ title: "House Session (01/07/2027)" }), ["house session", ...MATCH], "H"), false, "a session stream never");
  assert.equal(L.isCommittees(s({ title: "House Financial Services (01/07/2027)" }), MATCH, "H"), false, "a stem, not a prefix of a word");
  assert.equal(L.isCommittees(s({ title: "House Finances Review (01/07/2027)" }), MATCH, "H"), false, "whole words only");
  assert.equal(L.isCommittees(s({ chamber: "S", title: "Senate Finance (01/07/2027)" }), MATCH, "H"), false);
  assert.equal(L.isCommittees(s({ chamber: "S", title: "Finance (01/07/2027)" }), MATCH, "H"), false, "the other chamber's");
  assert.equal(L.isCommittees(s({ chamber: "S", title: "Finance (01/07/2027)" }), MATCH, ""), true, "a joint committee: any chamber");
});

test("a live stream shows one card, with a stub and no frame, and the agenda from the night's schedule", async () => {
  const { doc, hook } = page();
  const sched = { days: { "2027-01-07": [{ href: "/committee/S11", card: "<details>other</details>" },
                                         { href: "/committee/H09", card: '<details class="calmeet">HB 2</details>' }] } };
  const { fetch, asked } = server({ "/api/live/streams": { body: streams({ streams: [s({}), s({ video: "BBBBBBBBBBB", title: "House Session (01/07/2027)" })] }) },
                                    "/live/schedule.json": { body: sched } });
  const p = L.startCommittee(doc, { fetch, now: () => T("2027-01-07T15:21:00Z") });
  try {
    await p.first;
    assert.equal(hook.hidden, false);
    assert.equal(hook.children.length, 1);
    const card = hook.children[0];
    assert.equal(card.attrs["data-video"], "AAAAAAAAAAA");
    assert.match(card.innerHTML, /class="pstub"[^>]*data-embed="AAAAAAAAAAA\|0\|lv-AAAAAAAAAAA"/);
    assert.match(card.innerHTML, /data-title="Live stream of House Finance"/);
    assert.doesNotMatch(card.innerHTML, /<iframe/, "nothing from YouTube before a press");
    assert.match(card.parts[".lv-head"].innerHTML, /<p class="lv-name">Live now<\/p>.*Live since 10:02/);
    assert.doesNotMatch(card.innerHTML + card.parts[".lv-head"].innerHTML, /<h[1-6]/, "no heading above the page's own h1");
    assert.equal(hook.attrs["aria-label"], "House Finance is live now");
    assert.match(card.parts[".lv-foot"].innerHTML, /On YouTube.*class="lv-agenda".*HB 2/);
    assert.doesNotMatch(card.parts[".lv-foot"].innerHTML, /other/);
    assert.deepEqual(asked.map(a => a[0]), ["/api/live/streams", "/live/schedule.json"]);
  } finally { p.stop(); }
});

test("no agenda in the schedule: the stream shows, and nothing says why", async () => {
  const { doc, hook } = page();
  const { fetch } = server({ "/api/live/streams": { body: streams({ streams: [s({})] }) } });
  const p = L.startCommittee(doc, { fetch, now: () => T("2027-01-07T15:21:00Z") });
  try {
    await p.first;
    const foot = hook.children[0].parts[".lv-foot"].innerHTML;
    assert.match(foot, /On YouTube/);
    assert.doesNotMatch(foot, /lv-agenda|calendar|agenda/i);
  } finally { p.stop(); }
});

test("upcoming within 15 minutes: 'Scheduled to stream at', no stub; starting gains the stub in place", async () => {
  const { doc, hook } = page();
  let body = streams({ streams: [s({ status: "upcoming", started: null, scheduled: "2027-01-07T15:30:00Z" })] });
  const { fetch } = server(url => (url === "/api/live/streams" ? { body } : null));
  let at = T("2027-01-07T15:21:00Z");
  const p = L.startCommittee(doc, { fetch, now: () => at });
  try {
    await p.first;
    const card = hook.children[0];
    assert.match(card.parts[".lv-head"].innerHTML, /Scheduled to stream at 10:30/);
    assert.doesNotMatch(card.innerHTML, /pstub/);
    body = streams({ checked: "2027-01-07T15:31:00Z", next_check: "2027-01-07T15:33:00Z",
                     streams: [s({ started: "2027-01-07T15:30:30Z" })] });
    at = T("2027-01-07T15:32:00Z");
    await p.poll();
    assert.equal(hook.children.length, 1);
    assert.equal(hook.children[0], card, "the same card");
    assert.match(card.innerHTML, /pstub/);
    // An upcoming one an hour away is not shown.
    body = streams({ streams: [s({ status: "upcoming", started: null, scheduled: "2027-01-07T17:00:00Z" })] });
    at = T("2027-01-07T15:21:00Z");
    await p.poll();
    assert.equal(hook.hidden, true);
  } finally { p.stop(); }
});

test("a refresh keeps a playing frame; its end keeps the player with 'Ended at'; an unplayed card just goes", async () => {
  const { doc, hook } = page();
  let body = streams({ streams: [s({}), s({ video: "CCCCCCCCCCC", title: "House Finance Division I (01/07/2027)", started: "2027-01-07T15:10:00Z" })] });
  const { fetch } = server(url => (url === "/api/live/streams" ? { body } : null));
  let at = T("2027-01-07T15:21:00Z");
  const p = L.startCommittee(doc, { fetch, now: () => at });
  try {
    await p.first;
    assert.deepEqual(hook.children.map(c => c.attrs["data-video"]), ["CCCCCCCCCCC", "AAAAAAAAAAA"], "newest first");
    const watched = hook.children[1];
    watched.frame = { id: "yt_lv-AAAAAAAAAAA" };                  // the reader pressed play
    await p.poll();
    assert.equal(hook.children[1], watched);
    assert.equal(watched.frame.id, "yt_lv-AAAAAAAAAAA", "the frame untouched");
    body = streams({ checked: "2027-01-07T17:14:00Z", next_check: "2027-01-07T17:16:00Z", streams: [] });
    at = T("2027-01-07T17:14:30Z");
    await p.poll();
    assert.equal(hook.children.length, 1, "the unplayed card went");
    assert.equal(hook.children[0], watched);
    assert.match(watched.parts[".lv-head"].innerHTML, /Ended at 12:14.*The recording reaches this page's Videos tab after the next nightly update\./);
    assert.equal(hook.hidden, false);
  } finally { p.stop(); }
});

test("stale or failed: an unplayed card goes, a watched one stays as it was, and nothing is said", async () => {
  const { doc, hook } = page();
  let answer = { body: streams({ streams: [s({}), s({ video: "CCCCCCCCCCC" })] }) };
  const { fetch } = server(url => (url === "/api/live/streams" ? answer : null));
  let at = T("2027-01-07T15:21:00Z");
  const p = L.startCommittee(doc, { fetch, now: () => at });
  try {
    await p.first;
    const watched = hook.children[0];
    watched.frame = { id: "yt_lv-AAAAAAAAAAA" };
    const before = watched.parts[".lv-head"].innerHTML;
    at = T("2027-01-07T15:28:00Z");                                // 6 minutes past next_check
    await p.poll();
    assert.deepEqual(hook.children, [watched]);
    assert.equal(watched.parts[".lv-head"].innerHTML, before, "no 'Ended at' on a stale answer");
    answer = { status: 503 };
    await p.poll();
    assert.deepEqual(hook.children, [watched]);
    const all = JSON.stringify(hook.children.map(c => c.innerHTML + JSON.stringify(c.parts)));
    assert.doesNotMatch(all.toLowerCase(), /not streaming|nothing is live|not checked/);
  } finally { p.stop(); }
});

test("a 404 (no binding): the hook stays hidden, and nothing more is asked", async () => {
  const { t, ctx } = timers();
  const { doc, hook } = page();
  const { fetch, asked } = server({});
  const p = ctx.GRLive.startCommittee(doc, { fetch, now: () => T("2027-01-07T15:21:00Z") });
  await p.first;
  assert.equal(hook.hidden, true);
  assert.deepEqual(t, [], "no timer");
  await p.poll();
  assert.equal(asked.length, 1);
});

test("polling: a minute inside the window; past 20:00 only while the stream shown is live", async () => {
  // Timers held here and run by hand: each run is the next minute.
  const held = [];
  const ctx = load({ setTimeout: (f, ms) => { held.push([f, ms]); return held.length; }, clearTimeout: () => {} });
  const next = async () => { const [f] = held.shift(); f(); await new Promise(r => setImmediate(r)); await new Promise(r => setImmediate(r)); };
  let at = T("2027-01-08T00:58:00Z");                                // 19:58 EST on the 7th
  let list = [s({})];
  const { doc } = page();
  const { fetch, asked } = server(() => ({ body: streams({ checked: new Date(at).toISOString(),
    next_check: new Date(at + 120000).toISOString(), streams: list }) }));
  const p = ctx.GRLive.startCommittee(doc, { fetch, now: () => at });
  await p.first;
  const n = () => asked.filter(a => a[0] === "/api/live/streams").length;
  assert.equal(n(), 1);
  assert.equal(held[0][1], 60000, "every minute");
  at = T("2027-01-08T01:30:00Z");                                    // 20:30, the stream still live
  await next();
  assert.equal(n(), 2, "carried on past 20:00 while it is live");
  list = [];                                                          // it ended
  at = T("2027-01-08T01:31:00Z");
  await next();
  assert.equal(n(), 3);
  at = T("2027-01-08T01:32:00Z");
  await next();
  assert.equal(n(), 3, "ended past 20:00: no more requests");
  assert.equal(held.length, 1, "the clock is still looked at, asking nobody");
  at = T("2027-01-08T12:00:00Z");                                    // 07:00 on the 8th
  await next();
  assert.equal(n(), 4, "the window opens: asked again");
  p.stop();
});

test("the Videos tab's bar: only while a stream is live and its card out of view; 'Playing live' while watched", async () => {
  let seen = null;
  const ctx = load({ IntersectionObserver: function (cb) { seen = cb; this.observe = () => {}; } });
  const { doc, hook } = page();
  const bar = { hidden: true, innerHTML: "", addEventListener() {} };
  doc.querySelector = sel => (sel === ".lv-strip" ? bar : null);
  let list = [s({})];
  const { fetch } = server(url => (url === "/api/live/streams" ? { body: streams({ streams: list }) } : null));
  const p = ctx.GRLive.startCommittee(doc, { fetch, now: () => T("2027-01-07T15:21:00Z") });
  try {
    await p.first;
    assert.equal(bar.hidden, true, "the card in view: no bar");
    seen([{ isIntersecting: false }]);
    assert.equal(bar.hidden, false);
    assert.match(bar.innerHTML, /House Finance is live now.*<button type="button" class="lv-strip-go">Watch<\/button>/);
    hook.children[0].frame = { id: "yt_lv-AAAAAAAAAAA" };
    seen([{ isIntersecting: false }]);
    assert.match(bar.innerHTML, /Playing live/);
    seen([{ isIntersecting: true }]);
    assert.equal(bar.hidden, true, "back in view: no bar");
    list = [];
    hook.children[0].frame = null;
    await p.poll();
    seen([{ isIntersecting: false }]);
    assert.equal(bar.hidden, true, "nothing live: no bar");
  } finally { p.stop(); }
});

test("one plays at a time: a player started pauses every other frame on the page", () => {
  const posted = [];
  const frame = id => ({ id, contentWindow: { postMessage: m => posted.push([id, JSON.parse(m).func]) } });
  const frames = [frame("yt_lv-AAAAAAAAAAA"), frame("yt_vw-2027-01-05"), frame("yt_vw-2026-12-01")];
  const doc = { querySelectorAll: sel => (sel === "iframe[id^='yt_']" ? frames : []) };
  L.pauseOthers(doc, "yt_lv-AAAAAAAAAAA");
  assert.deepEqual(posted, [["yt_vw-2027-01-05", "pauseVideo"], ["yt_vw-2026-12-01", "pauseVideo"]]);
  posted.length = 0;
  L.pauseOthers(doc, "yt_vw-2027-01-05");
  assert.deepEqual(posted.map(x => x[0]), ["yt_lv-AAAAAAAAAAA", "yt_vw-2026-12-01"]);
});
