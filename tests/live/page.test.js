// Live Now's script (src/pages/live.js) under node, after components.js as
// the page loads them (the live layer's design, section 7.1's page tests):
// stale is said as stale against next_check, and a quiet evening checked
// every 30 minutes is not; "not streaming" and "nothing is live" never
// appear; every status code of the votes file has its own sentence and an
// unknown one "Not read since"; a stream is matched to its meeting by stem;
// and a refresh keeps an opened player's iframe. preflight runs this suite
// (_live_tests).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { stem as workerStem } from "../../workers/live/youtube.js";

const read = rel => readFileSync(new URL(`../../${rel}`, import.meta.url), "utf8");
const CASES = JSON.parse(read("tests/components_cases.json"));

// components.js then live.js, in one context, as a page's head and body run them.
function load(extra = {}) {
  const ctx = vm.createContext({ console, Intl, Date, Math, JSON, Promise, setTimeout, clearTimeout, ...extra });
  ctx.window = ctx;
  vm.runInContext(read("src/pages/components.js"), ctx, { filename: "components.js" });
  vm.runInContext(read("src/pages/live.js"), ctx, { filename: "live.js" });
  return ctx;
}
const ctx = load();
const L = ctx.GRLive;
const T = s => Date.parse(s);
const NBSP = " ";

const file = (over = {}) => ({ kind: "live.streams", day: "2027-01-07", checked: "2027-01-07T19:14:00Z",
  next_check: "2027-01-07T19:16:00Z", status: { ok: true, problem: null, since: null }, streams: [], ...over });
const stream = over => ({ video: "AbCdEfGhIjK", chamber: "H", title: "House Finance (01/07/2027)", status: "live",
  scheduled: "2027-01-07T15:00:00Z", started: "2027-01-07T15:02:00Z", ended: null, embeddable: true, ...over });
const SCHEDULE = { days: { "2027-01-07": [
  { id: "H|Finance|2027-01-07", chamber: "H", kind: "standing", name: "House Finance", href: "/committee/H09",
    card: '<div class="calcard">House Finance, 10:00 AM</div>', match: ["house finance", "finance"] },
  { id: "H|Floor|2027-01-07", chamber: "H", kind: "floor", name: "House Session", href: "/session/H/today",
    card: "", match: ["house session"] },
  { id: "S|Judiciary|2027-01-07", chamber: "S", kind: "standing", name: "Senate Judiciary", href: "/committee/S11",
    card: "", match: ["senate judiciary", "judiciary"] }] } };

test("times are the site's own: components.clock's cases, through New Hampshire's clock", () => {
  for (const c of CASES.clock.filter(c => typeof c.args[0] === "string" && /^\d{1,2}:\d\d$/.test(c.args[0]) && !c.args[1] && Number(c.args[0].split(":")[0]) < 24)) {
    const [h, m] = c.args[0].split(":").map(Number);
    const iso = new Date(Date.UTC(2027, 0, 7, h + 5, m)).toISOString();
    assert.equal(L.timeOf(iso), c.want, c.args[0]);
  }
  assert.equal(L.timeOf("2027-07-07T14:02:00Z"), `10:02${NBSP}AM`, "daylight time");
});

test("the title's stem is the Worker's, on every synthetic title and the committed index's", () => {
  const titles = JSON.parse(read("tests/live/youtube_items.json")).items.map(i => i.item.snippet && i.item.snippet.title).filter(Boolean);
  const csv = read("collected/videos/videos_house_2026-01-01_to_2026-06-30.csv").split("\n").slice(1, 400)
    .map(l => (l.match(/^[^,]*,("(?:[^"]|"")*"|[^,]*)/) || [])[1] || "").map(t => t.replace(/^"|"$/g, "").replace(/""/g, '"'));
  titles.push(...csv, "Committee of Conference on SB 534  (05/22/2026", "Ways & Means (1/7/27 - morning session)");
  assert.ok(titles.length > 300);
  for (const t of titles) assert.equal(L.stem(t), workerStem(t), t);
  assert.equal(L.sessionOf("House Session (12/04/2024)"), "H");
  assert.equal(L.sessionOf("Full Committee Work Session (01/07/2027)"), null);
});

test("stale is said as stale against next_check; a quiet evening checked every 30 minutes is not", () => {
  const f = file();
  assert.equal(L.streamsStatus(f, T("2027-01-07T19:21:00Z")).sentence, `No stream found right now (checked 2:14${NBSP}PM)`);
  assert.equal(L.streamsStatus(f, T("2027-01-07T19:21:01Z")).sentence, `Live status has not been checked since 2:14${NBSP}PM`);
  const evening = file({ checked: "2027-01-08T01:00:00Z", next_check: "2027-01-08T01:30:00Z" });
  assert.equal(L.streamsStatus(evening, T("2027-01-08T01:34:00Z")).kind, "fresh", "20:34, between looks");
  assert.equal(L.streamsStatus(file({ streams: [stream()] }), T("2027-01-07T19:15:00Z")).sentence,
               `Checked 2:14${NBSP}PM`);
  assert.equal(L.streamsStatus(file({ status: { ok: false, problem: "off" } }), T("2027-01-07T19:15:00Z")).sentence,
               "Live status is turned off");
  assert.equal(L.streamsStatus(null, T("2027-01-07T19:15:00Z"), 404).sentence, "Live status is not available");
  assert.equal(L.streamsStatus(file({ status: { ok: false, problem: "quota" } }), T("2027-01-07T19:15:00Z")).kind, "stale");
  assert.equal(L.streamsStatus(file(), T("2027-01-08T05:30:00Z")).kind, "stale", "yesterday's file is not today's");
  assert.equal(L.streamsStatus(null, T("2027-01-07T19:15:00Z"), 0).sentence, "Live status has not been checked yet today");
});

test('"not streaming" and "nothing is live" never appear, in any state the page can be in', () => {
  const said = [];
  const states = [file(), file({ streams: [stream()] }), file({ streams: [stream({ status: "ended", ended: "2027-01-07T17:00:00Z" })] }),
                  file({ status: { ok: false, problem: "off" } }), file({ status: { ok: false, problem: "key" } }), null];
  for (const f of states) for (const t of ["2027-01-07T19:15:00Z", "2027-01-07T23:00:00Z", "2027-01-08T12:00:00Z"]) {
    for (const http of [200, 404, 0]) {
      const v = L.view(f, SCHEDULE, T(t), http);
      said.push(v.status.sentence, ...v.live.map(c => c.parts.head + c.parts.foot), ...v.scheduled, ...v.nostream, ...v.earlier);
    }
  }
  const text = said.join("\n").toLowerCase();
  for (const bad of ["not streaming", "nothing is live", "no streams", "isn't live", "is not live"]) {
    assert.ok(!text.includes(bad), bad);
  }
});

test("a stream is matched to its meeting by stem; a session stream to the chamber's floor; another committee's is not", () => {
  const rows = SCHEDULE.days["2027-01-07"];
  assert.equal(L.match(stream(), rows).id, "H|Finance|2027-01-07");
  assert.equal(L.match(stream({ title: "House Finance - Division II (01/07/2027)" }), rows).id, "H|Finance|2027-01-07");
  assert.equal(L.match(stream({ title: "House Session (01/07/2027)" }), rows).id, "H|Floor|2027-01-07");
  assert.equal(L.match(stream({ title: "Senate Judiciary (01/07/2027)" }), rows), null, "the House's stream is not the Senate's committee");
  assert.equal(L.match(stream({ title: "Financial Institutions (01/07/2027)" }), rows), null, "'finance' is not 'financial'");
  const v = L.view(file({ streams: [stream(), stream({ video: "zzzzzzzzzzz", title: "Fiscal Committee (01/07/2027)" })] }),
                   SCHEDULE, T("2027-01-07T19:15:00Z"), 200);
  assert.deepEqual(Array.from(v.live, c => c.name), ["Fiscal Committee", "House Finance"]);
  assert.match(v.live[1].parts.head, /href="\/committee\/H09"/);
  assert.match(v.live[1].parts.head, new RegExp(`Live since 10:02${NBSP}AM`));
  assert.match(v.live[1].parts.foot, /calcard/);
  assert.equal(v.nostream.length, 2, "the floor and Senate Judiciary: on today's calendar, no stream found");
});

test("every status code of the votes file has its own sentence, and an unknown one is 'Not read since'", () => {
  const now = T("2027-01-07T15:44:00Z");
  const v = (status, over = {}) => ({ read_at: "2027-01-07T15:42:00Z", next_read_by: "2027-01-07T15:46:00Z",
                                      status, rollcalls: [{ body: "H", seq: 1 }], ...over });
  const got = {};
  for (const p of ["connect", "login", "encrypt", "query", "budget", "off", "day_over", "a_new_one"]) {
    got[p] = L.votesSentence(v({ state: "reading", problem: p, since: "2027-01-07T15:43:00Z" }), now, "H");
  }
  assert.equal(new Set(Object.values(got)).size, 8, "each its own");
  assert.match(got.connect, /could not be reached since/);
  assert.match(got.login, /refused the published login/);
  assert.match(got.encrypt, /encrypted connection/);
  assert.match(got.budget, /today's limit/);
  assert.match(got.off, new RegExp(`turned off by this site at 10:43${NBSP}AM`));
  assert.match(got.day_over, /Reading stopped for the day/);
  assert.match(got.a_new_one, new RegExp(`^Not read since 10:42${NBSP}AM\\.`));
  for (const s of Object.values(got)) assert.match(s, /Every vote reaches this page with tomorrow morning's record\.$/);
  assert.match(L.votesSentence(v({ state: "reading", problem: null }), now, "H"), /^Read from the General Court's database at 10:42/);
  assert.match(L.votesSentence(v({ state: "reading", problem: null }), T("2027-01-07T15:52:00Z"), "H"), /^Not read since/,
               "past next_read_by by more than 5 minutes");
  const none = L.votesSentence(v({ state: "reading", problem: null }, { rollcalls: [] }), now, "S");
  assert.match(none, /^No roll calls read yet today \(read at 10:42.*The Senate enters its roll calls after it rises\./);
  assert.match(L.votesSentence(null, now, "H"), /^No roll calls read today\./);
  for (const s of [...Object.values(got), none]) assert.doesNotMatch(s.toLowerCase(), /no votes/);
});

test("a chamber's roll calls, newest first, with the docket's outcome named as the docket's", () => {
  const f = { rollcalls: [
    { id: "2027-H-14", body: "H", seq: 14, bill: "2027-2028/HB2", bill_as_recorded: "HB2", question: "Ought to Pass", taken: "2027-01-07T15:41:07Z",
      yeas: 190, nays: 171, ballots_complete: true, docket: { outcome: "Motion Adopted" }, note: null },
    { id: "2027-H-15", body: "H", seq: 15, bill_as_recorded: "HB3", question: "Table", taken: "2027-01-07T15:50:00Z",
      yeas: 100, nays: 250, ballots_complete: false, docket: null, note: null },
    { id: "2027-S-3", body: "S", seq: 3, bill_as_recorded: "SB12", question: "OTP", taken: null, saved: "2027-01-08T14:12:00Z",
      yeas: 15, nays: 8, ballots_complete: true, docket: null, note: null }] };
  const h = L.votesItems(f, "H", { "2027-2028": { 2027: ["HB2", "HB3"] } });
  assert.equal(h.length, 2);
  assert.match(h[0], /data-id="2027-H-15".*outcome not yet in the docket.*names follow/);
  assert.match(h[1], /href="\/bill\/2027\/hb2\.html".*Motion Adopted, clerk's docket.*names: in/);
  assert.match(L.votesItems(f, "S")[0], new RegExp(`saved at 9:12${NBSP}AM`));
});

test("a roll call's bill links to the page of the year it was introduced, through the term's index", () => {
  // The term's own index, as build_live.bill_years writes it: HB 1 of 2025
  // carried over into 2026; CACR 13 and HB 1442 introduced in 2026.
  const bills = { "2025-2026": { 2025: ["CACR5", "HB1", "SB12"], 2026: ["CACR13", "HB1442"] } };
  const rc = (b, term) => ({ id: "2026-H-3", body: "H", seq: 3, bill: `${term || "2025-2026"}/${b}`, bill_as_recorded: b,
    question: "OTP", taken: "2026-01-08T15:00:00Z", yeas: 1, nays: 0, ballots_complete: true, docket: null, note: null });
  // Voted in 2026, introduced in 2025: the 2025 page, never /bill/2026/hb1.
  assert.equal(L.billHref(rc("HB1"), bills), "/bill/2025/hb1.html");
  assert.equal(L.billHref(rc("HB 1"), bills), "/bill/2025/hb1.html");
  assert.equal(L.billHref(rc("CACR13"), bills), "/bill/2026/cacr13.html");
  const li = L.votesItems({ rollcalls: [rc("HB1")] }, "H", bills)[0];
  assert.match(li, /href="\/bill\/2025\/hb1\.html"/);
  assert.doesNotMatch(li, /\/bill\/2026\//);
  // Not in the index, another term's, or no index at all: the number, unlinked.
  for (const [r, b] of [[rc("HB9999"), bills], [rc("HB1", "2027-2028"), bills], [rc("HB1"), undefined], [rc("HB1"), {}]]) {
    assert.equal(L.billHref(r, b), null);
    const item = L.votesItems({ rollcalls: [r] }, "H", b)[0];
    assert.doesNotMatch(item, /href=/);
    assert.match(item, /<span class="bmention" translate="no">HB/);
  }
  // A key the index would only hold by inheritance is not a bill.
  assert.equal(L.billHref(rc("HB1", "constructor"), bills), null);
  assert.equal(L.billHref({ ...rc("HB1"), bill: null, bill_as_recorded: "<b>x" }, bills), null);
  assert.match(L.votesItems({ rollcalls: [{ ...rc("HB1"), bill: null, bill_as_recorded: "<b>x" }] }, "H", bills)[0], /&lt;b&gt;x/);
  // A procedural vote: the words as typed, no bill, no link.
  assert.equal(L.billHref({ ...rc("SUSPRULE"), bill: null }, bills), null);
  // The link follows the record's reading of the field, not its words.
  assert.equal(L.billHref({ ...rc("HB 1-FN"), bill: "2025-2026/HB1" }, bills), "/bill/2025/hb1.html");
});

// ---- the votes file's rings, union and session card ----------------------------
const rcOf = over => ({ id: "2027-H-14", body: "H", seq: 14, bill: "2027-2028/HB2", bill_as_recorded: "HB2",
  question: "Ought to Pass", taken: "2027-01-07T15:41:07Z", saved: null, yeas: 186, nays: 169,
  ballots_complete: true, docket: null, note: null, ...over });

test("which side prevailed is a source's: the record's passed, else the clerk's docket; never the tally", () => {
  assert.equal(L.passedOf(rcOf({ passed: false })), false, "186-169 and sustained: the record says so");
  assert.equal(L.passedOf(rcOf({ docket: { outcome: "Motion Adopted" } })), true);
  assert.equal(L.passedOf(rcOf({ docket: { outcome: "Amendment Adopted" } })), true);
  assert.equal(L.passedOf(rcOf({ docket: { outcome: "Motion Failed" } })), false);
  assert.equal(L.passedOf(rcOf({ docket: { outcome: "Amendment Lost" } })), false);
  assert.equal(L.passedOf(rcOf({})), null, "no docket line yet: nobody says");
  assert.equal(L.passedOf(rcOf({ docket: { outcome: null } })), null);
  assert.equal(L.passedOf(rcOf({ passed: true, docket: { outcome: "Motion Failed" } })), true, "the record wins");
});

test("a ring is app.js's simpleDonut, and only where a source says who prevailed", () => {
  const drawn = [];
  const c2 = load({ simpleDonut: (rc, bid, i, what) => { drawn.push({ rc, bid, i, what }); return `<svg data-i="${i}"></svg>`; } });
  const L2 = c2.GRLive;
  assert.equal(L.ring(rcOf({ passed: true }), 0), "", "no app.js on the page: no ring, the tally stands as text");
  assert.equal(L2.ring(rcOf({}), 0), "", "no outcome: no ring");
  assert.match(L2.ring(rcOf({ passed: false, threshold_needed: 237 }), 3), /data-i="3"/);
  assert.deepEqual(JSON.parse(JSON.stringify(drawn[0].rc)), { yeas: 186, nays: 169, passed: false, threshold_needed: 237,
                                                              threshold_unknown: false }, "the record's threshold");
  // A live row: the docket says it failed, and nobody says what it needed (an
  // override needs two thirds): no mark, no number needed.
  L2.ring(rcOf({ yeas: 220, nays: 150, docket: { outcome: "Motion Failed" } }), 4);
  assert.deepEqual(JSON.parse(JSON.stringify(drawn.at(-1).rc)), { yeas: 220, nays: 150, passed: false, threshold_needed: null,
                                                                   threshold_unknown: true });
  L2.ring(rcOf({ passed: true, threshold_needed: null }), 5);
  assert.equal(drawn.at(-1).rc.threshold_unknown, false, "the record's null is a majority, on record");
  assert.equal(drawn[0].what, "Roll call");
  const items = L2.votesItems({ rollcalls: [rcOf({ docket: { outcome: "Motion Adopted" } })] }, "H", undefined, { rings: true });
  assert.match(items[0], /<svg data-i="0">/);
  assert.doesNotMatch(L2.votesItems({ rollcalls: [rcOf({})] }, "H", undefined, { rings: true })[0], /<svg/);
  const broken = load({ simpleDonut: () => { throw new Error("x"); } }).GRLive;
  assert.equal(broken.ring(rcOf({ passed: true }), 0), "", "a ring that throws costs the ring, not the list");
});

test("the overlay is the union by roll-call id, the record winning", () => {
  const record = { rollcalls: [rcOf({ id: "2027-H-14", seq: 14 }), rcOf({ id: "2027-H-15", seq: 15 })] };
  const live = { read_at: "2027-01-07T16:43:00Z", rollcalls: [rcOf({ id: "2027-H-14", seq: 14, yeas: 1 }), rcOf({ id: "2027-H-16", seq: 16 }),
    rcOf({ id: "2027-H-17", seq: 17 }), rcOf({ id: "2027-S-3", body: "S", seq: 3 })] };
  assert.deepEqual(L.overlay(record, live, "H").map(r => r.id), ["2027-H-17", "2027-H-16"]);
  assert.deepEqual(L.overlay(null, live, "H").map(r => r.id), ["2027-H-17", "2027-H-16", "2027-H-14"], "no record yet: every live one");
  assert.deepEqual([...L.overlay(record, null, "H")], []);
  assert.deepEqual([...L.overlay({ rollcalls: live.rollcalls }, live, "H")], [], "the record has every id: nothing overlaid");
  const items = L.votesItems(live, "H", undefined, { rollcalls: L.overlay(record, live, "H"), provisional: true });
  assert.equal(items.length, 2);
  assert.match(items[0], new RegExp(`data-id="2027-H-17".*provisional · read at 11:43${NBSP}AM`));
});

test("the votes file is asked every 30 seconds while a reader is at work, else every 2 minutes", () => {
  const now = T("2027-01-07T16:00:00Z");
  assert.equal(L.votesEvery({ next_read_by: "2027-01-07T16:02:00Z" }, now), 30000);
  assert.equal(L.votesEvery({ next_read_by: "2027-01-07T15:51:00Z" }, now), 30000, "overdue by 9 minutes: still close");
  assert.equal(L.votesEvery({ next_read_by: "2027-01-07T16:15:00Z" }, now), 120000, "the quarter-hour heartbeat");
  assert.equal(L.votesEvery({ next_read_by: "2027-01-07T13:00:00Z" }, now), 120000, "a reader stopped hours ago");
  assert.equal(L.votesEvery({ next_read_by: null }, now), 120000);
  assert.equal(L.votesEvery(null, now), 120000);
});

test("the poller: If-None-Match, a 304 keeps the file, a 404 forgets it, a new address starts afresh", async () => {
  const asked = [], heard = [];
  let answer = { status: 200, etag: '"a"', body: { n: 1 } };
  const doc = { hidden: false, addEventListener() {} };
  let url = "/x/1";
  const p = L.poller({ doc, url: () => url, every: () => 0,
    // As the browser's fetch: called with any `this` but the global, it throws.
    fetch: async function (u, init) {
      if (this !== undefined && this !== globalThis) throw new TypeError("Illegal invocation");
      asked.push([u, init.headers["If-None-Match"] || null]);
      return { status: answer.status, ok: answer.status === 200, headers: { get: () => answer.etag }, json: async () => answer.body }; },
    onFile: (f, code) => heard.push([f && f.n, code]) });
  await p.first;
  answer = { status: 304 };
  await p.poll();
  answer = { status: 503 };
  await p.poll();
  answer = { status: 404 };
  await p.poll();
  answer = { status: 200, etag: '"b"', body: { n: 2 } };
  await p.poll();
  url = "/x/2";
  await p.poll();
  assert.deepEqual(asked, [["/x/1", null], ["/x/1", '"a"'], ["/x/1", '"a"'], ["/x/1", '"a"'], ["/x/1", null], ["/x/2", null]]);
  assert.deepEqual(heard, [[1, 200], [1, 304], [1, 503], [null, 404], [2, 200], [2, 200]]);
  p.stop();
  await p.poll();
  assert.equal(asked.length, 6, "stopped: asks no more");
});

test("Live Now's session card: the chamber's list, its sentence, provisional, and its today page", () => {
  const f = { read_at: "2027-01-07T16:43:00Z", next_read_by: "2027-01-07T16:45:00Z", status: { state: "reading", problem: null, since: null },
    rollcalls: [rcOf({ docket: { outcome: "Motion Adopted" } })] };
  const now = T("2027-01-07T16:44:00Z");
  const h = L.sessionCard(f, "H", now, 200, { "2027-2028": { 2027: ["HB2"] } });
  assert.match(h, /<h2 class="lv-name">House roll calls today<\/h2>/);
  assert.match(h, /href="\/bill\/2027\/hb2\.html"/);
  assert.match(h, /Read from the General Court's database at 11:43/);
  assert.match(h, /Provisional: the night's record replaces this tomorrow morning; excusals settle days later\./);
  assert.match(h, /href="\/session\/H\/today">The House today</);
  assert.doesNotMatch(h, /Senate names follow/);
  const s = L.sessionCard(f, "S", now, 200);
  assert.doesNotMatch(s, /<ol/, "no Senate roll calls: no list");
  assert.match(s, /No roll calls read yet today/);
  assert.doesNotMatch(s, /Provisional/);
  assert.match(L.sessionCard({ ...f, rollcalls: [rcOf({ body: "S", id: "2027-S-1" })] }, "S", now, 200),
               /Senate names follow once the Senate enters them/);
  assert.deepEqual([...L.sessionBodies(SCHEDULE, null, "2027-01-07")], ["H"], "the House's floor row");
  assert.deepEqual([...L.sessionBodies(SCHEDULE, { rollcalls: [rcOf({ body: "S" })] }, "2027-01-07")], ["H", "S"]);
  assert.deepEqual([...L.sessionBodies(SCHEDULE, null, "2027-01-08")], [], "no sitting: no card");
});

test("/live asks for the votes file only on a day the schedule has a sitting", async () => {
  for (const [day, want] of [["2027-01-07T16:44:00Z", 2], ["2027-01-08T16:44:00Z", 1]]) {
    const { doc, els } = page();
    els["live-now-votes"] = { hidden: true, innerHTML: "" };
    const asked = [];
    const fetch = async url => { asked.push(url);
      return { status: 404, ok: false, headers: { get: () => null }, json: async () => null }; };
    const p = L.start(doc, { fetch, now: () => T(day) });
    try {                                    // stopped whatever fails: no timer left to hang the run
      await p.first;
      if (p.votes) await p.votes.first;
      assert.equal(asked.length, want, day);
      if (want === 2) {
        assert.deepEqual(asked, ["/api/live/streams", "/api/live/votes/2027-01-07"]);
        assert.match(els["live-now-votes"].innerHTML, /No roll calls read today\./);
        assert.equal(els["live-now-votes"].hidden, false);
      }
    } finally { p.stop(); }
  }
});

test("a votes file that could not be fetched is said as such, never as a day with none", () => {
  const now = T("2027-01-07T15:45:00Z");
  for (const code of [0, 503]) {
    const s = L.votesSentence(null, now, "H", code);
    assert.match(s, new RegExp(`^The live votes could not be fetched at 10:45${NBSP}AM; this page asks again\\.`), String(code));
    assert.doesNotMatch(s, /No roll calls/);
  }
  assert.match(L.votesSentence(null, now, "H", 404), /^No roll calls read today\./, "a 404 is a day with no file");
});

test("Live Now's session card shows tallies as text, even where app.js is loaded", () => {
  const c2 = load({ simpleDonut: () => "<svg></svg>" });
  const h = c2.GRLive.sessionCard({ rollcalls: [rcOf({ docket: { outcome: "Motion Adopted" } })], status: {} }, "H", T("2027-01-07T16:44:00Z"), 200);
  assert.doesNotMatch(h, /<svg/);
  assert.match(h, /186&ndash;169/);
});

test("/live's session card keeps a sitting past midnight until 06:00, and an open page finds the next morning's", async () => {
  const sched = { days: { "2027-01-07": [{ id: "f", chamber: "H", kind: "floor", name: "House Session", match: [] }],
                          "2027-01-08": [], "2027-01-11": [{ id: "g", chamber: "S", kind: "floor", name: "Senate Session", match: [] }] } };
  let at = T("2027-01-08T05:10:00Z");                                    // 00:10 on the 8th
  const { doc, els } = page();
  els["live-schedule"] = { textContent: JSON.stringify(sched) };
  els["live-now-votes"] = { hidden: true, innerHTML: "" };
  const asked = [];
  const fetch = async url => {
    asked.push(url);
    if (url === "/api/live/streams") return { status: 200, ok: true, headers: { get: () => '"s"' }, json: async () => file() };
    return { status: 404, ok: false, headers: { get: () => null }, json: async () => null };
  };
  const p = L.start(doc, { fetch, now: () => at });
  try {
    await p.first;
    await p.votes.first;
    assert.ok(asked.includes("/api/live/votes/2027-01-07"), "the 7th's sitting, at 00:10 on the 8th");
    assert.equal(els["live-now-votes"].hidden, false);
    p.votes.stop();
    p.votes = null;
    // Monday morning, the page still open: the next streams poll starts the Senate's.
    at = T("2027-01-11T14:00:00Z");
    await p.poll();
    assert.ok(p.votes, "a poller for the new day");
    await p.votes.first;
    assert.equal(asked.at(-1), "/api/live/votes/2027-01-11");
  } finally { p.stop(); }
});

// A page just deep enough for L.start: the stream cards' box, keyed children.
function page() {
  const els = {};
  const mk = tag => {
    const e = { tagName: tag, attrs: {}, children: [], hidden: false, textContent: "", className: "", _html: "",
      setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k] ?? null; },
      appendChild(c) { c.parent = this; this.children.push(c); return c; },
      remove() { if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); },
      querySelector(sel) {
        const m = /^\[data-video="(.*)"\]$/.exec(sel);
        if (m) return this.children.find(c => c.attrs["data-video"] === m[1]) || null;
        const k = sel.replace(/^\./, "");
        this.parts = this.parts || {};
        return (this.parts[k] = this.parts[k] || mk("div"));
      },
      querySelectorAll(sel) { return sel === "[data-video]" ? this.children.filter(c => c.attrs["data-video"]) : []; } };
    Object.defineProperty(e, "innerHTML", { get() { return this._html; }, set(v) { this._html = String(v); } });
    return e;
  };
  for (const id of ["live-now-streams", "live-now-status", "live-now-scheduled", "live-now-nostream", "live-now-earlier",
                    "live-now-scheduled-h", "live-now-earlier-h"]) els[id] = mk("div");
  els["live-schedule"] = { textContent: JSON.stringify(SCHEDULE) };
  const doc = { hidden: false, _on: {}, getElementById: id => els[id] || null, createElement: mk,
                addEventListener(t, f) { (this._on[t] = this._on[t] || []).push(f); } };
  return { doc, els };
}

test("a refresh keeps an opened player's card, and a card whose stream ended goes; a 404 asks no more", async () => {
  const { doc, els } = page();
  let answer = { status: 200, etag: '"e1"', body: file({ streams: [stream()] }) };
  const asked = [];
  const fetch = async (url, init) => {
    asked.push(init.headers["If-None-Match"] || null);
    return { status: answer.status, ok: answer.status === 200, headers: { get: () => answer.etag },
             json: async () => answer.body };
  };
  const now = () => T("2027-01-07T19:15:00Z");
  const p = L.start(doc, { fetch, now });
  try {                                      // stopped whatever fails: no timer left to hang the run
  await p.first;
  const box = els["live-now-streams"];
  assert.equal(box.children.length, 1);
  const card = box.children[0];
  card.playerOpened = true;                  // the reader pressed play: the iframe lives in this card
  answer = { status: 200, etag: '"e2"', body: file({ checked: "2027-01-07T19:16:00Z", next_check: "2027-01-07T19:18:00Z",
                                                     streams: [stream()] }) };
  await p.poll();
  assert.equal(box.children[0], card, "the same card, its player untouched");
  assert.ok(box.children[0].playerOpened);
  assert.deepEqual(asked, [null, '"e1"'], "If-None-Match on the next poll");
  answer = { status: 200, etag: '"e3"', body: file({ streams: [stream({ status: "ended", ended: "2027-01-07T19:10:00Z" })] }) };
  await p.poll();
  assert.equal(box.children.length, 0, "its stream ended: the card goes");
  assert.match(els["live-now-earlier"].innerHTML, /House Finance/);
  assert.equal(els["live-now-earlier-h"].hidden, false, "a list with a line: its heading");
  assert.equal(els["live-now-scheduled-h"].hidden, true, "an empty list shows no heading");
  answer = { status: 404, etag: null, body: null };
  await p.poll();
  assert.equal(els["live-now-status"].textContent, "Live status is not available");
  const n = asked.length;
  await p.poll();
  assert.equal(asked.length, n, "after a 404 it asks no more");
  } finally { p.stop(); }
});

// ---- the session-day pages (sections 4.2 and 4.3) --------------------------------
// A today page or a dated page, deep enough for startToday and startOverlay:
// elements by id, and the children querySelectorAll looks through.
function dayPage({ body = "H", built = "2027-01-07", dated = null, hook = null, bills = {} } = {}) {
  const mk = (attrs = {}, cls = "") => {
    const e = { attrs: { ...attrs }, className: cls, hidden: false, textContent: "", children: [], _html: "",
      getAttribute(k) { return this.attrs[k] ?? null; }, setAttribute(k, v) { this.attrs[k] = String(v); },
      appendChild(c) { c.parent = this; this.children.push(c); return c; },
      remove() { if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); },
      querySelector(sel) {
        const m = /^\[data-video="(.*)"\]$/.exec(sel);
        if (m) return this.children.find(c => c.attrs["data-video"] === m[1]) || null;
        this.parts = this.parts || {};
        return (this.parts[sel] = this.parts[sel] || mk());
      },
      querySelectorAll(sel) {
        if (sel === "[data-video]") return this.children.filter(c => c.attrs["data-video"]);
        if (sel === "[data-day]") return this.children.filter(c => "data-day" in c.attrs);
        if (sel.startsWith(".")) return this.children.filter(c => c.className.split(" ").includes(sel.slice(1)));
        return [];
      } };
    Object.defineProperty(e, "innerHTML", { get() { return this._html; }, set(v) { this._html = String(v); } });
    return e;
  };
  const els = {};
  const root = mk({ "data-body": body, "data-built": built });
  for (const [cls, attrs] of [["lv-floor", { "data-day": built }], ["lv-provisional", {}], ["lv-senate", {}]]) {
    const c = root.appendChild(mk(attrs, cls));
    c.hidden = cls !== "lv-floor";
  }
  if (dated) root.appendChild(mk({ "data-day": dated }, "lv-dated"));
  els["live-today"] = root;
  for (const id of ["live-today-day", "live-today-status", "live-today-stream", "live-today-votes", "live-today-votes-status",
                    "live-today-dated"]) els[id] = mk();
  els["live-today-dated"].hidden = true;
  els["live-bills"] = { textContent: JSON.stringify(bills) };
  if (hook) els["live-votes"] = mk({ "data-day": hook.day, "data-body": hook.body || body });
  if (hook) delete els["live-today"];
  const doc = { hidden: false, _on: {}, getElementById: id => els[id] || null, createElement: () => mk(),
                addEventListener(t, f) { (this._on[t] = this._on[t] || []).push(f); } };
  return { doc, els, root };
}
// A fetch answering by address: {url: body} for 200, a missing address 404.
function server(files) {
  const asked = [];
  const fetch = async (url, init) => {
    asked.push(url);
    const body = files[url];
    const status = body === undefined ? 404 : 200;
    return { status, ok: status === 200, headers: { get: () => (status === 200 ? `"${url}"` : null) }, json: async () => body };
  };
  return { fetch, asked };
}
const liveFile = (date, rcs, over = {}) => ({ api: 1, kind: "session.votes", date, provisional: true,
  read_at: `${date}T16:43:00Z`, next_read_by: `${date}T16:45:00Z`, status: { state: "reading", problem: null, since: null },
  rollcalls: rcs, tallies: [], ...over });

test("the reader's session day is New Hampshire's, the day before until 06:00", () => {
  assert.equal(L.readerDay(T("2027-01-08T10:59:00Z")), "2027-01-07", "05:59 EST: still the 7th");
  assert.equal(L.readerDay(T("2027-01-08T11:00:00Z")), "2027-01-08", "06:00 EST");
  assert.equal(L.readerDay(T("2027-01-08T04:30:00Z")), "2027-01-07", "23:30 EST on the 7th");
  assert.equal(L.readerDay(T("2027-03-01T10:00:00Z")), "2027-02-28", "05:00 EST on 1 March: across a month");
  assert.equal(L.readerDay(T("2027-06-01T09:59:00Z")), "2027-05-31", "05:59 EDT");
  assert.equal(L.readerDay(T("2027-06-01T10:00:00Z")), "2027-06-01", "06:00 EDT");
  assert.equal(L.daysBetween("2027-01-07", "2027-01-21"), 14);
  assert.equal(L.daysBetween("2027-03-13", "2027-03-15"), 2, "across the change to daylight time");
  assert.equal(L.dayWords("2027-01-07"), "Thursday, January 7");
});

test("/session/H/today: the reader's day, the night's dated parts hidden on another, the record and the live union", async () => {
  // The night built it on the 7th; the reader comes on the 8th at 10:00.
  const now = () => T("2027-01-08T15:00:00Z");
  const { doc, els, root } = dayPage({ built: "2027-01-07", dated: "2027-01-08", bills: { "2027-2028": { 2027: ["HB2"] } } });
  const record = { date: "2027-01-08", rollcalls: [rcOf({ id: "2027-H-14", seq: 14, passed: true })] };
  const live = liveFile("2027-01-08", [rcOf({ id: "2027-H-14", seq: 14, yeas: 1 }), rcOf({ id: "2027-H-15", seq: 15, ballots_complete: false })]);
  const { fetch, asked } = server({ "/session/H/2027-01-08.json": record, "/api/live/votes/2027-01-08": live,
                                    "/api/live/streams": file({ day: "2027-01-08", checked: "2027-01-08T14:59:00Z", next_check: "2027-01-08T15:01:00Z",
                                      streams: [stream({ title: "House Session (01/08/2027)" })] }) });
  const p = L.startToday(doc, { fetch, now });
  try {
    await p.first;
    assert.equal(root.children.find(c => c.className === "lv-floor").hidden, true, "the 7th's floor card, hidden on the 8th");
    assert.equal(root.children.find(c => c.className === "lv-dated").hidden, false, "the 8th's dated page: linked");
    assert.match(els["live-today-day"].textContent, /Friday, January 8/);
    assert.ok(asked.includes("/session/H/2027-01-08.json"), "the record of the day, since the night has its page");
    const list = els["live-today-votes"].innerHTML;
    assert.equal((list.match(/<li /g) || []).length, 2);
    assert.match(list, /data-id="2027-H-15".*provisional · read at/);
    assert.match(list, /data-id="2027-H-14".*186&ndash;169/, "the record's copy of 14, not the live 1-169");
    const own = list.slice(list.indexOf('data-id="2027-H-14"'));
    assert.doesNotMatch(own, /not yet in the docket|names follow|provisional/, "the record's row waits on nothing");
    assert.doesNotMatch(list, /data-id="2027-H-14"[^]*provisional[^]*data-id="2027-H-14"/);
    assert.ok(list.indexOf("2027-H-15") < list.indexOf("2027-H-14"), "newest first");
    assert.match(list, /href="\/bill\/2027\/hb2\.html"/);
    assert.equal(root.children.find(c => c.className === "lv-provisional").hidden, false);
    assert.equal(els["live-today-stream"].children.length, 1, "the House session stream");
    assert.match(els["live-today-status"].textContent, /^Checked/);
  } finally { p.stop(); }
});

test("/session/S/today before 06:00: yesterday's sitting, no record yet, every live roll call provisional; no stream said as such", async () => {
  const now = () => T("2027-01-08T09:30:00Z");                         // 04:30 EST on the 8th
  const { doc, els, root } = dayPage({ body: "S", built: "2027-01-07" });
  const live = liveFile("2027-01-07", [rcOf({ id: "2027-S-3", body: "S", seq: 3, ballots_complete: false }),
                                       rcOf({ id: "2027-H-9", seq: 9 })]);
  const files = { "/api/live/votes/2027-01-07": live,
    "/api/live/streams": file({ day: "2027-01-08", checked: "2027-01-08T09:29:00Z", next_check: "2027-01-08T09:59:00Z",
                                streams: [stream({ title: "House Session (01/08/2027)" })] }) };
  const { fetch, asked } = server(files);
  const p = L.startToday(doc, { fetch, now });
  try {
    await p.first;
    assert.ok(asked.includes("/api/live/votes/2027-01-07"));
    assert.ok(asked.includes("/session/S/2027-01-07.json"), "the record is looked for, and not there");
    assert.equal(els["live-today-dated"].hidden, true, "no record: no dated page linked");
    assert.match(els["live-today-votes-status"].textContent, /this morning's record\./, "the 7th's record comes this morning");
    assert.doesNotMatch(els["live-today-votes-status"].textContent, /tomorrow/);
    assert.equal(root.children.find(c => c.className === "lv-floor").hidden, false, "the 7th's floor card stays on the 7th");
    const list = els["live-today-votes"].innerHTML;
    assert.equal((list.match(/<li /g) || []).length, 1, "the Senate's only");
    assert.match(list, /2027-S-3.*provisional/);
    assert.equal(root.children.find(c => c.className === "lv-senate").hidden, false, "names follow");
    assert.match(els["live-today-status"].textContent, /^No Senate session stream found right now \(checked 4:29/);
    assert.doesNotMatch(els["live-today-status"].textContent.toLowerCase(), /not streaming|nothing is live/);
    assert.equal(els["live-today-stream"].children.length, 0, "the House's stream is not the Senate's");
    files["/api/live/votes/2027-01-07"] = { ...live, rollcalls: [rcOf({ id: "2027-S-3", body: "S", seq: 3, ballots_complete: true })] };
    await p.votes.poll();
    assert.equal(root.children.find(c => c.className === "lv-senate").hidden, true, "names in: the line goes");
  } finally { p.stop(); }
});

test("/session/H/today with no binding: says so, and asks the streams no more", async () => {
  const timers = [];
  const c2 = load({ setTimeout: (f, ms) => { timers.push(ms); return timers.length; }, clearTimeout: () => {} });
  const { doc, els } = dayPage();
  const { fetch, asked } = server({});
  const p = c2.GRLive.startToday(doc, { fetch, now: () => T("2027-01-07T15:00:00Z") });
  try {
    await p.first;
    await new Promise(r => setImmediate(r));
    assert.deepEqual([...timers], [120000], "the votes file asked again in 2 minutes; the streams never");
    assert.equal(els["live-today-votes"].hidden, true);
    assert.match(els["live-today-votes-status"].textContent, /^No roll calls read today\./);
    assert.equal(els["live-today-status"].textContent, "Live status is not available");
    const n = asked.filter(u => u === "/api/live/streams").length;
    await p.streams.poll();
    assert.equal(asked.filter(u => u === "/api/live/streams").length, n + 1);
  } finally { p.stop(); }
});

test("/session/H/today between the night and 06:00: the record of the day before is found, linked and wins", async () => {
  // Built on the 8th by a night at 03:17; the reader's day is still the 7th.
  const now = () => T("2027-01-08T09:30:00Z");                         // 04:30 EST
  const { doc, els, root } = dayPage({ built: "2027-01-08", dated: "2027-01-08" });
  const record = { date: "2027-01-07", rollcalls: [rcOf({ id: "2027-H-14", seq: 14, passed: true }), rcOf({ id: "2027-H-15", seq: 15, passed: false })] };
  const live = liveFile("2027-01-07", [rcOf({ id: "2027-H-14", seq: 14 }), rcOf({ id: "2027-H-15", seq: 15 })]);
  const { fetch } = server({ "/session/H/2027-01-07.json": record, "/api/live/votes/2027-01-07": live });
  const p = L.startToday(doc, { fetch, now });
  try {
    await p.first;
    assert.equal(root.children.find(c => c.className === "lv-dated").hidden, true, "the 8th's link: not the reader's day");
    assert.equal(els["live-today-dated"].hidden, false);
    assert.match(els["live-today-dated"].innerHTML, /href="\/session\/H\/2027-01-07"/);
    const list = els["live-today-votes"].innerHTML;
    assert.equal((list.match(/<li /g) || []).length, 2);
    assert.doesNotMatch(list, /provisional|not yet in the docket|names follow/, "every row the record's");
    assert.equal(els["live-today-votes-status"].textContent, "The night's record holds Thursday, January 7's roll calls.");
    assert.equal(root.children.find(c => c.className === "lv-provisional").hidden, true);
  } finally { p.stop(); }
});

test("/session/H/today: a live file that could not be fetched is not a day with none", async () => {
  const { doc, els } = dayPage();
  const fetch = async url => ({ status: 503, ok: false, headers: { get: () => null }, json: async () => null });
  const p = L.startToday(doc, { fetch, now: () => T("2027-01-07T15:45:00Z") });
  try {
    await p.first;
    assert.match(els["live-today-votes-status"].textContent, /^The live votes could not be fetched at 10:45/);
  } finally { p.stop(); }
});

test("the record is asked again every 10 minutes while it is not there, and once found, no more", async () => {
  let at = T("2027-01-07T15:00:00Z");
  const files = { "/api/live/votes/2027-01-07": liveFile("2027-01-07", [rcOf({})]) };
  const { doc } = dayPage();
  const { fetch, asked } = server(files);
  const p = L.startToday(doc, { fetch, now: () => at });
  const n = () => asked.filter(u => u === "/session/H/2027-01-07.json").length;
  try {
    await p.first;
    assert.equal(n(), 1);
    at += 5 * 60000; await p.votes.poll();
    assert.equal(n(), 1, "five minutes on: not again");
    at += 6 * 60000; await p.votes.poll();
    assert.equal(n(), 2, "eleven minutes on: again");
    files["/session/H/2027-01-07.json"] = { date: "2027-01-07", rollcalls: [] };
    at += 11 * 60000; await p.votes.poll();
    at += 11 * 60000; await p.votes.poll();
    assert.equal(n(), 3, "found: asked no more");
  } finally { p.stop(); }
});

test("/session/H/today: the day before's dated link goes when the day turns at 06:00", async () => {
  let at = T("2027-01-08T10:30:00Z");                                  // 05:30 on the 8th: the 7th
  const { doc, els } = dayPage({ built: "2027-01-08" });
  const { fetch } = server({ "/session/H/2027-01-07.json": { date: "2027-01-07", rollcalls: [] },
                             "/api/live/votes/2027-01-07": liveFile("2027-01-07", []), "/api/live/votes/2027-01-08": liveFile("2027-01-08", []) });
  const p = L.startToday(doc, { fetch, now: () => at });
  try {
    await p.first;
    assert.equal(els["live-today-dated"].hidden, false);
    assert.match(els["live-today-dated"].innerHTML, /2027-01-07/);
    at = T("2027-01-08T11:30:00Z");                                    // 06:30: the 8th
    await p.votes.poll();
    assert.match(els["live-today-day"].textContent, /Friday, January 8/);
    assert.equal(els["live-today-dated"].hidden, true, "no record of the 8th yet: no link");
    assert.doesNotMatch(els["live-today-dated"].innerHTML, /2027-01-07/);
  } finally { p.stop(); }
});

test("the dated page's overlay: within 14 days, the live roll calls the record lacks; none without a record; older pages ask nothing", async () => {
  const record = { date: "2027-01-07", rollcalls: [rcOf({ id: "2027-H-14", seq: 14 })] };
  const live = liveFile("2027-01-07", [rcOf({ id: "2027-H-14", seq: 14 }), rcOf({ id: "2027-H-16", seq: 16 }),
                                       rcOf({ id: "2027-S-2", body: "S", seq: 2 })]);
  const files = { "/session/H/2027-01-07.json": record, "/api/live/votes/2027-01-07": live };
  // On the day: drawn, and polling.
  let pg = dayPage({ hook: { day: "2027-01-07" } });
  let s = server(files);
  let p = L.startOverlay(pg.doc, { fetch: s.fetch, now: () => T("2027-01-07T20:00:00Z") });
  try {
    await p.first;
    const html = pg.els["live-votes"].innerHTML;
    assert.match(html, /Read during the day/);
    assert.equal((html.match(/<li /g) || []).length, 1);
    assert.match(html, /data-id="2027-H-16".*provisional · read at/);
    assert.equal(pg.els["live-votes"].hidden, false);
    assert.equal(L.votesEvery(live, T("2027-01-07T20:00:00Z")) > 0, true);
  } finally { p.stop(); }
  // The record has caught up: nothing drawn.
  pg = dayPage({ hook: { day: "2027-01-07" } });
  s = server({ ...files, "/session/H/2027-01-07.json": { date: "2027-01-07", rollcalls: live.rollcalls } });
  p = L.startOverlay(pg.doc, { fetch: s.fetch, now: () => T("2027-01-09T20:00:00Z") });
  try {
    await p.first;
    assert.equal(pg.els["live-votes"].innerHTML, "");
    assert.equal(pg.els["live-votes"].hidden, true);
  } finally { p.stop(); }
  // No record file: nothing drawn, the live file not even asked.
  pg = dayPage({ hook: { day: "2027-01-07" } });
  s = server({ "/api/live/votes/2027-01-07": live });
  p = L.startOverlay(pg.doc, { fetch: s.fetch, now: () => T("2027-01-08T20:00:00Z") });
  await p.first;
  assert.deepEqual(s.asked, ["/session/H/2027-01-07.json"]);
  assert.equal(pg.els["live-votes"].innerHTML, "");
  p.stop();
  // Fifteen days on, or a page dated ahead: no request at all.
  for (const at of ["2027-01-22T20:00:00Z", "2027-01-06T20:00:00Z"]) {
    pg = dayPage({ hook: { day: "2027-01-07" } });
    s = server(files);
    assert.equal(L.startOverlay(pg.doc, { fetch: s.fetch, now: () => T(at) }), null, at);
    assert.deepEqual(s.asked, []);
  }
  const last = L.startOverlay(dayPage({ hook: { day: "2027-01-07" } }).doc, { fetch: server(files).fetch, now: () => T("2027-01-21T20:00:00Z") });
  try { assert.ok(last, "fourteen days on: still asked"); await last.first; } finally { last.stop(); }
});

test("the overlay polls only while its date is today in New Hampshire", async () => {
  const files = { "/session/H/2027-01-07.json": { date: "2027-01-07", rollcalls: [] },
                  "/api/live/votes/2027-01-07": liveFile("2027-01-07", [rcOf({})]) };
  const timers = [];
  const c2 = load({ setTimeout: (f, ms) => { timers.push(ms); return timers.length; }, clearTimeout: () => {} });
  for (const [at, want] of [["2027-01-07T16:44:00Z", [30000]], ["2027-01-07T20:00:00Z", [120000]], ["2027-01-08T20:00:00Z", []]]) {
    timers.length = 0;
    const pg = dayPage({ hook: { day: "2027-01-07" } });
    const p = c2.GRLive.startOverlay(pg.doc, { fetch: server(files).fetch, now: () => T(at) });
    await p.first;
    await new Promise(r => setImmediate(r));
    assert.deepEqual([...timers], want, at);
  }
});
