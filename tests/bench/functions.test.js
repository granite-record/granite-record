// The bench's Functions (functions/bench.js, functions/api/bench/*.js): every
// route a 404 until BENCH_DB is bound, the address and the origin checked as
// the follows check them, a wrong token one read and a 404, what the page is
// told (and not told), the owner's Links tab, and a log of codes and counts.

import test from "node:test";
import assert from "node:assert/strict";
import { onRequest as page } from "../../functions/bench.js";
import { onRequest as nextFn } from "../../functions/api/bench/next.js";
import { onRequest as judgeFn } from "../../functions/api/bench/judge.js";
import { onRequest as undoFn } from "../../functions/api/bench/undo.js";
import { onRequest as holdFn } from "../../functions/api/bench/hold.js";
import { onRequest as linksFn } from "../../functions/api/bench/links.js";
import { onRequest as asksFn } from "../../functions/api/bench/asks.js";
import { SITE, T0, addLink, loadPack, makeBench } from "./world.js";

const ROUTES = { "/bench": page, "/api/bench/next": nextFn, "/api/bench/judge": judgeFn,
                 "/api/bench/undo": undoFn, "/api/bench/hold": holdFn, "/api/bench/links": linksFn,
                 "/api/bench/asks": asksFn };
// The body a route takes: 4 KiB, but the owner's answer with its note of 2,000 characters.
const BODY_MOST = path => (path === "/api/bench/asks" ? 8192 : 4096);
const API = Object.keys(ROUTES).filter(p => p.startsWith("/api/"));

function captureConsole() {
  const lines = [], saved = {};
  for (const m of ["log", "info", "warn", "error", "debug"]) {
    saved[m] = console[m];
    console[m] = (...a) => lines.push(a.map(String).join(" "));
  }
  return { lines, restore() { Object.assign(console, saved); } };
}

async function world(opts = {}) {
  const d1 = makeBench();
  await loadPack(d1, opts);
  const owner = await addLink(d1, { id: "owner2", name: "You", role: "owner" });
  const sam = await addLink(d1, { id: "sam234", name: "Sam" });
  const w = { d1, owner, sam, now: new Date(T0), logs: captureConsole() };
  w.env = { BENCH_DB: d1, REPORT_ORIGINS: "graniterecord.org www.graniterecord.org", CLOCK: () => w.now.getTime() };
  w.later = s => { w.now = new Date(w.now.getTime() + s * 1000); };
  w.call = async (path, body, { method = "POST", origin = SITE, site = "same-origin", host = SITE,
                                type = "application/json", env = w.env, raw = null } = {}) => {
    const headers = { ...(type ? { "Content-Type": type } : {}), ...(origin ? { Origin: origin } : {}),
                      ...(site ? { "Sec-Fetch-Site": site } : {}) };
    const req = new Request(host + path, { method, headers,
      ...(method === "POST" ? { body: raw ?? JSON.stringify(body ?? {}) } : {}) });
    const res = await ROUTES[path]({ request: req, env });
    const text = await res.text();
    let data = null;
    try { data = JSON.parse(text); } catch { /* not JSON */ }
    return { status: res.status, headers: Object.fromEntries(res.headers), text, data };
  };
  w.close = () => w.logs.restore();
  return w;
}

test("every route answers 404 until BENCH_DB is bound, and only at its own address", async () => {
  const w = await world();
  try {
    for (const path of Object.keys(ROUTES)) {
      const method = path === "/bench" ? "GET" : "POST";
      for (const env of [{}, { REPORT_ORIGINS: "graniterecord.org" }]) {
        const r = await w.call(path, { t: w.owner.token }, { method, env });
        assert.equal(r.status, 404, `${path} without the database`);
        assert.equal(r.text, "Not found\n");
      }
      for (const host of ["https://abc123.graniterecord.pages.dev", "https://evil.example"]) {
        const r = await w.call(path, { t: w.owner.token }, { method, host });
        assert.equal(r.status, 404, `${path} at ${host}`);
      }
      const slash = await ROUTES[path]({ request: new Request(SITE + path + "/", { method }), env: w.env });
      assert.equal(slash.status, 404, `${path}/`);
    }
  } finally { w.close(); }
});

test("the API takes a post from the site's own page and nothing else", async () => {
  const w = await world();
  try {
    for (const path of API) {
      const get = await w.call(path, null, { method: "GET" });
      assert.equal(get.status, 405, `${path} GET`);
      assert.equal(get.text, "POST only\n");
      assert.equal(get.headers.allow, "POST");
      for (const [what, o] of [["another site", { origin: "https://evil.example" }],
                               ["no origin", { origin: null }],
                               ["a cross-site fetch", { site: "cross-site" }]]) {
        const r = await w.call(path, { t: w.owner.token }, o);
        assert.equal(r.status, 403, `${path} from ${what}`);
      }
    }
    assert.equal((await w.call("/bench", null, { method: "POST" })).status, 405, "the page takes no post");
  } finally { w.close(); }
});

test("a wrong token, a link turned off, a body too long or not JSON: one read at most, and a 404", async () => {
  const w = await world();
  try {
    const off = await addLink(w.d1, { id: "off234", state: "off" });
    for (const path of API) {
      assert.equal((await w.call(path, { t: off.token })).status, 404, `${path}: a link turned off`);
      const before = w.d1.prepared.length;
      const r = await w.call(path, { t: "A".repeat(43) });
      assert.equal(r.status, 404, `${path}: a wrong token`);
      assert.equal(w.d1.prepared.length - before, 1, `${path}: one statement for a wrong token`);
      assert.equal((await w.call(path, { t: "short" })).status, 404);
      assert.equal((await w.call(path, null, { raw: JSON.stringify({ t: w.owner.token,
                                                                       x: "y".repeat(BODY_MOST(path) + 900) }) })).status,
                   404, `${path}: a body over ${BODY_MOST(path) / 1024} KiB`);
      assert.equal((await w.call(path, { t: w.owner.token }, { type: "text/plain" })).status, 404, `${path}: not JSON`);
    }
  } finally { w.close(); }
});

test("the page is told each item's reference, queue and card, and never its key or that it is calibration", async () => {
  const w = await world({ topics: 30, calib: 2 });
  try {
    const r = await w.call("/api/bench/next", { t: w.sam.token, queue: "topic" });
    assert.equal(r.status, 200);
    assert.equal(r.data.role, "contributor");
    assert.deepEqual(r.data.queues.map(q => q.queue), ["timing", "topic", "tag"]);
    assert.deepEqual(r.data.queues[1].options, ["Education - General", "Employment", "Police", "Miscellaneous"]);
    assert.equal(r.data.items.length, 2);
    for (const it of r.data.items) assert.deepEqual(Object.keys(it).sort(), ["card", "queue", "ref"]);
    assert.doesNotMatch(r.text, /topic\|2023-2024|"key"|"kind"|"calib"|"grp"|\|title\|/,
                        "no key, kind, group or calibration flag");
    assert.deepEqual(r.data.progress, { label: "Bills of 2023-2024", goal: 30, done: 0 });
    assert.deepEqual(r.data.far.map(q => q.queue), ["timing", "topic", "tag"]);
    assert.equal(r.headers["cache-control"], "no-store");
    assert.equal(r.headers["x-robots-tag"], "noindex");
  } finally { w.close(); }
});

test("an answer is kept and the next items come back; refusals say why", async () => {
  const w = await world({ topics: 6 });
  try {
    const t = w.sam.token;
    let r = await w.call("/api/bench/next", { t, queue: "topic" });
    const [a, b] = r.data.items;
    const hidden = "the note" + String.fromCodePoint(0x200B) + " " + "z".repeat(400);
    r = await w.call("/api/bench/judge", { t, queue: "topic", ref: a.ref, answer: { answer: "no", better: "Police" },
                                           note: hidden });
    assert.equal(r.status, 200);
    assert.deepEqual(r.data.saved, { side: "no" });
    assert.equal(r.data.items[0].ref, b.ref, "the one fetched ahead is next");
    const j = w.d1.rows("judgments").at(-1);
    assert.deepEqual([j.verdict, JSON.parse(j.fields).better_topic, j.hidden, j.note.length], ["wrong", "Police", 1, 280]);
    assert.ok(!j.note.includes("​"), "the hidden character taken out, and said to have been");
    assert.equal((await w.call("/api/bench/judge", { t, ref: a.ref, answer: { answer: "yes" } })).status, 409,
                 "answered already");
    assert.equal((await w.call("/api/bench/judge", { t, ref: b.ref, answer: { answer: "yes" } })).status, 429,
                 "within a second");
    w.later(2);
    assert.equal((await w.call("/api/bench/judge", { t, ref: b.ref, answer: { answer: "partly" } })).status, 400);
    assert.equal((await w.call("/api/bench/judge", { t, ref: b.ref, answer: { answer: "yes", better: "Police" } }))
      .status, 400, "a better topic only with a No");
    w.d1.sql.prepare("UPDATE links SET state = 'paused' WHERE id = 'sam234'").run();
    r = await w.call("/api/bench/judge", { t, ref: b.ref, answer: { answer: "yes" } });
    assert.deepEqual([r.status, r.data.why, r.data.state, r.data.items.length], [409, "paused", "paused", 0]);
  } finally { w.close(); }
});

test("undo gives back the latest answer's item first, and hold keeps the page's items", async () => {
  const w = await world({ topics: 6 });
  try {
    const t = w.sam.token;
    const [a] = (await w.call("/api/bench/next", { t, queue: "topic" })).data.items;
    await w.call("/api/bench/judge", { t, queue: "topic", ref: a.ref, answer: { answer: "yes" } });
    w.later(1);
    let r = await w.call("/api/bench/undo", { t, queue: "topic" });
    assert.equal(r.data.undone, true);
    assert.equal(r.data.items[0].ref, a.ref, "the item taken back is shown again first");
    r = await w.call("/api/bench/undo", { t, queue: "topic" });
    assert.equal(r.data.undone, false, "a second undo takes nothing more");
    w.later(9 * 60);
    r = await w.call("/api/bench/hold", { t });
    assert.deepEqual(r.data, { held: 3 }, "the item given back and the two held");
  } finally { w.close(); }
});

test("the Links tab is the owner's alone: list, a new link shown once, pause, take back, turn off", async () => {
  const w = await world({ topics: 6 });
  try {
    assert.equal((await w.call("/api/bench/links", { t: w.sam.token, action: "list" })).status, 404,
                 "a contributor's link does not open it");
    const t = w.owner.token;
    let r = await w.call("/api/bench/links", { t, action: "make", name: "Civics class", queues: ["tag"] });
    assert.equal(r.status, 200);
    const { id, token } = r.data.made;
    assert.match(token, /^[A-Za-z0-9_-]{43}$/);
    assert.ok(w.d1.everyCell().every(c => !c.includes(token)), "the new token is not kept");
    assert.equal((await w.call("/api/bench/links", { t, action: "make", name: "", queues: ["tag"] })).status, 400);
    const civics = (await w.call("/api/bench/next", { t: token })).data;
    assert.ok(civics.items.every(x => x.queue === "tag"), "the new link judges what it was given");
    r = await w.call("/api/bench/next", { t: w.sam.token, queue: "topic" });
    await w.call("/api/bench/judge", { t: w.sam.token, ref: r.data.items[0].ref, answer: { answer: "yes" } });
    r = await w.call("/api/bench/links", { t, action: "list" });
    const sam = r.data.links.find(l => l.id === "sam234");
    assert.deepEqual([sam.name, sam.answers, sam.unmerged, sam.state], ["Sam", 1, 1, "active"]);
    r = await w.call("/api/bench/links", { t, action: "answers", id: "sam234" });
    assert.equal(r.data.answers.length, 1);
    r = await w.call("/api/bench/links", { t, action: "takeone", id: "sam234", answer: r.data.answers[0].id });
    assert.equal(r.data.taken, 1);
    assert.equal((await w.call("/api/bench/links", { t, action: "pause", id })).status, 200);
    assert.equal((await w.call("/api/bench/next", { t: token })).data.state, "paused");
    assert.equal((await w.call("/api/bench/links", { t, action: "off", id })).status, 200);
    assert.equal((await w.call("/api/bench/next", { t: token })).status, 404, "a link turned off opens nothing");
    assert.equal((await w.call("/api/bench/links", { t, action: "resume", id })).status, 409, "and stays off");
    assert.equal((await w.call("/api/bench/links", { t, action: "off", id: "owner2" })).status, 409,
                 "her own link is not turned off from the page");
    assert.equal((await w.call("/api/bench/links", { t, action: "merge" })).status, 400, "no merge here");
  } finally { w.close(); }
});

test("the page: noindex, no-store, framed by nothing, its script under a nonce, and no token in it", async () => {
  const w = await world();
  try {
    const r = await w.call("/bench", null, { method: "GET" });
    assert.equal(r.status, 200);
    assert.match(r.headers["content-type"], /^text\/html/);
    assert.equal(r.headers["cache-control"], "no-store");
    assert.equal(r.headers["x-robots-tag"], "noindex");
    assert.equal(r.headers["x-frame-options"], "DENY");
    assert.equal(r.headers["referrer-policy"], "strict-origin-when-cross-origin");
    const csp = r.headers["content-security-policy"];
    const n = /'nonce-([A-Za-z0-9_-]+)'/.exec(csp)[1];
    assert.match(csp, /default-src 'none'/);
    assert.match(csp, /frame-ancestors 'none'/);
    assert.match(csp, /connect-src 'self'/);
    assert.match(csp, /frame-src https:\/\/www\.youtube-nocookie\.com/);
    assert.ok(r.text.includes(`<script nonce="${n}">`));
    assert.match(r.text, /<meta name="robots" content="noindex">/);
    assert.ok(!r.text.includes(w.owner.token) && !r.text.includes(w.sam.token));
    const again = await w.call("/bench", null, { method: "GET" });
    assert.notEqual(/'nonce-([A-Za-z0-9_-]+)'/.exec(again.headers["content-security-policy"])[1], n,
                    "a new nonce each answer");
  } finally { w.close(); }
});

test("the log is codes and counts: no token, no link's name or id, no note, no item", async () => {
  const w = await world({ topics: 6 });
  try {
    const t = w.sam.token;
    const [a] = (await w.call("/api/bench/next", { t, queue: "topic" })).data.items;
    await w.call("/api/bench/judge", { t, ref: a.ref, answer: { answer: "no" }, note: "a secret note" });
    await w.call("/api/bench/judge", { t, ref: a.ref, answer: { answer: "no" } });
    await w.call("/api/bench/undo", { t });
    await w.call("/api/bench/links", { t: w.owner.token, action: "make", name: "Ann", queues: ["tag"] });
    // An error whose message carries what must not be logged: it is logged by its name alone.
    w.d1.failWhen = () => new Error(`Sam's secret note ${t}`);
    await w.call("/api/bench/next", { t });
    w.d1.failWhen = null;
    assert.ok(w.logs.lines.length >= 5, w.logs.lines.join(" | "));
    assert.ok(w.logs.lines.includes("bench next.error.Error"), w.logs.lines.join(" | "));
    for (const line of w.logs.lines) {
      assert.match(line, /^bench [a-z0-9_.?-]+( \d+)?$/i, line);
      for (const secret of ["Sam", "sam234", "secret", "Ann", "HB 20", "topic|"])
        assert.ok(!line.includes(secret), `${line} carries ${secret}`);
      for (const tok of [t, w.owner.token])
        for (let i = 0; i + 12 <= tok.length; i++)
          assert.ok(!line.includes(tok.slice(i, i + 12)), `${line} carries part of a token`);
    }
  } finally { w.close(); }
});
