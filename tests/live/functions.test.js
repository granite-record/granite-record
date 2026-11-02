// The two read-only Pages Functions (functions/api/live/, the live layer's
// design, sections 5 and 6.4): 404 without the binding; GET and HEAD only;
// only their own path shapes reach the bucket, so control.json, state.json
// and test/ are unreachable; CORS on the votes file alone and noindex on the
// streams; 304 on If-None-Match; the today-or-yesterday streams rule; a copy
// per data centre. The bucket is an R2 in memory (fake_r2.js) and the Cache
// API a Map on the test's clock. preflight runs this suite (_live_tests).
import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeR2 } from "./fake_r2.js";
import { liveStore } from "../../functions/api/live/_store.js";
import { onRequest as streams } from "../../functions/api/live/streams.js";
import { onRequest as votes } from "../../functions/api/live/votes/[day].js";

const SITE = "https://graniterecord.org";

// The Cache API's default cache, honouring max-age on the test's clock.
function fakeCaches(clock) {
  const store = new Map();
  const c = {
    store,
    async match(req) {
      const e = store.get(new URL(req.url).toString());
      if (!e || clock() >= e.until) return undefined;
      return e.res.clone();
    },
    async put(req, res) {
      const age = Number((/max-age=(\d+)/.exec(res.headers.get("Cache-Control") || "") || [])[1] || 0);
      store.set(new URL(req.url).toString(), { res: res.clone(), until: clock() + age * 1000 });
    },
  };
  globalThis.caches = { default: c };
  return c;
}

function setup({ bound = true, now = "2027-01-07T15:00:00Z" } = {}) {
  const w = { now: Date.parse(now) };
  w.r2 = new FakeR2({ clock: () => w.now });
  w.r2.head = async key => (w.r2.objects.has(key) ? w.r2._meta(key, w.r2.objects.get(key)) : null);
  w.cache = fakeCaches(() => w.now);
  w.env = bound ? { LIVE: w.r2 } : {};
  w.get = (path, init = {}) => {
    const request = new Request(SITE + path, init);
    const m = /^\/api\/live\/votes\/([^?]*)/.exec(path);          // Pages hands the route its path, not the query
    return m ? votes({ request, env: w.env, params: { day: decodeURIComponent(m[1]) }, waitUntil: () => {} })
             : streams({ request, env: w.env, waitUntil: () => {} }, { now: w.now });
  };
  return w;
}

const VOTES = { api: 1, kind: "session.votes", date: "2027-01-07", provisional: true, rollcalls: [] };
const STREAMS = day => ({ kind: "live.streams", day, streams: [] });

test("without the LIVE binding every live Function answers 404, cached a minute", async () => {
  const w = setup({ bound: false });
  for (const p of ["/api/live/streams", "/api/live/votes/2027-01-07"]) {
    const r = await w.get(p);
    assert.equal(r.status, 404, p);
    assert.equal(r.headers.get("Cache-Control"), "public, max-age=60", p);
  }
});

test("GET and HEAD only: anything else is 405, and HEAD carries no body", async () => {
  const w = setup();
  w.r2.seed("votes/2027-01-07.json", VOTES);
  w.r2.seed("streams/2027-01-07.json", STREAMS("2027-01-07"));
  for (const method of ["POST", "PUT", "DELETE", "PATCH"]) {
    for (const p of ["/api/live/streams", "/api/live/votes/2027-01-07"]) {
      const r = await w.get(p, { method, body: method === "DELETE" ? undefined : "x" });
      assert.equal(r.status, 405, `${method} ${p}`);
      assert.equal(r.headers.get("Allow"), "GET, HEAD");
    }
  }
  const h = await w.get("/api/live/votes/2027-01-07", { method: "HEAD" });
  assert.equal(h.status, 200);
  assert.equal(await h.text(), "");
  assert.deepEqual(w.r2.ops.filter(([op]) => op !== "get"), [], "nothing but reads reached the bucket");
});

test("only the two path shapes reach the bucket: control.json, state.json and test/ are unreachable", async () => {
  const w = setup();
  for (const k of ["control.json", "state.json", "test/2026-03-11.json", "votes/x.json"]) w.r2.seed(k, { secret: k });
  for (const day of ["control", "../control", "../state", "..%2Fcontrol", "2026-03-11/../../test/2026-03-11",
                     "2027-02-30", "2027-1-7", "x", "", "2027-01-07.json"]) {
    const r = await w.get(`/api/live/votes/${encodeURIComponent(day)}`);
    assert.equal(r.status, 404, day);
    assert.doesNotMatch(await r.text(), /secret/);
  }
  const r = await votes({ request: new Request(`${SITE}/api/live/votes/a/b`), env: w.env, params: { day: ["..", "control"] } });
  assert.equal(r.status, 404, "a catch-all of parts is not a date");
  assert.deepEqual(w.r2.ops.filter(([op]) => op === "get").map(([, k]) => k), [], "the bucket was not asked");
  assert.deepEqual(Object.keys(liveStore(w.env)).sort(), ["get", "head"], "the facade reads and nothing else");
  assert.ok(Object.isFrozen(liveStore(w.env)));
});

test("CORS on the votes file alone; the streams carry noindex and no CORS header, on every answer", async () => {
  const w = setup();
  w.r2.seed("votes/2027-01-07.json", VOTES);
  w.r2.seed("streams/2027-01-07.json", STREAMS("2027-01-07"));
  const v = await w.get("/api/live/votes/2027-01-07");
  assert.deepEqual([v.status, v.headers.get("Access-Control-Allow-Origin"), v.headers.get("Content-Type"),
                    v.headers.get("Cache-Control")], [200, "*", "application/json; charset=utf-8", "public, max-age=15"]);
  assert.deepEqual(await v.json(), VOTES);
  for (const p of ["/api/live/streams", "/api/live/votes/2027-01-08"]) {
    const r = await w.get(p);
    if (p.includes("streams")) {
      assert.equal(r.headers.get("Cache-Control"), "public, max-age=30");
      assert.equal(r.headers.get("X-Robots-Tag"), "noindex");
    }
  }
  for (const [p, init] of [["/api/live/streams", {}], ["/api/live/streams", { method: "POST" }],
                           ["/api/live/streams", { headers: { "If-None-Match": "x" } }]]) {
    const r = await w.get(p, init);
    assert.equal(r.headers.get("Access-Control-Allow-Origin"), null, `${init.method || "GET"} streams: no CORS`);
    assert.equal(r.headers.get("X-Robots-Tag"), "noindex");
  }
  assert.equal((await setup({ bound: false }).get("/api/live/streams")).headers.get("Access-Control-Allow-Origin"), null);
});

test("304 when If-None-Match holds the ETag, weak or strong, from the bucket or the cached copy", async () => {
  const w = setup();
  w.r2.seed("votes/2027-01-07.json", VOTES);
  const first = await w.get("/api/live/votes/2027-01-07");
  const etag = first.headers.get("ETag");
  assert.match(etag, /^".+"$/);
  for (const held of [etag, `W/${etag}`, `"other", ${etag}`]) {
    const r = await w.get("/api/live/votes/2027-01-07", { headers: { "If-None-Match": held } });
    assert.equal(r.status, 304, held);
    assert.equal(await r.text(), "");
  }
  assert.equal((await w.get("/api/live/votes/2027-01-07", { headers: { "If-None-Match": '"stale"' } })).status, 200);
  // A new write: a new ETag, after the cached copy has run out.
  w.r2.seed("votes/2027-01-07.json", { ...VOTES, rollcalls: [{ id: "2027-H-1" }] });
  w.now += 16_000;
  const r = await w.get("/api/live/votes/2027-01-07", { headers: { "If-None-Match": etag } });
  assert.equal(r.status, 200);
  assert.notEqual(r.headers.get("ETag"), etag);
});

test("a copy per data centre: the bucket is read once while the copy lasts, 15 s for votes and 30 s for streams", async () => {
  const w = setup();
  w.r2.seed("votes/2027-01-07.json", VOTES);
  w.r2.seed("streams/2027-01-07.json", STREAMS("2027-01-07"));
  const reads = key => w.r2.ops.filter(([op, k]) => op === "get" && k === key).length;
  for (let i = 0; i < 10; i++) { await w.get("/api/live/votes/2027-01-07"); await w.get("/api/live/streams"); w.now += 1000; }
  assert.deepEqual([reads("votes/2027-01-07.json"), reads("streams/2027-01-07.json")], [1, 1]);
  w.now += 6_000;                                         // 16 s on
  await w.get("/api/live/votes/2027-01-07"); await w.get("/api/live/streams");
  assert.deepEqual([reads("votes/2027-01-07.json"), reads("streams/2027-01-07.json")], [2, 1]);
  w.now += 15_000;                                        // 31 s on
  await w.get("/api/live/streams");
  assert.equal(reads("streams/2027-01-07.json"), 2);
  // A 404 is not kept in the copy: the file that arrives is served at once.
  await w.get("/api/live/votes/2027-01-09");
  w.r2.seed("votes/2027-01-09.json", { ...VOTES, date: "2027-01-09" });
  assert.equal((await w.get("/api/live/votes/2027-01-09")).status, 200);
});

test("the streams are today's in New Hampshire, or yesterday's in the hour after midnight before today's exists", async () => {
  const at = now => { const w = setup({ now }); w.r2.seed("streams/2027-01-07.json", STREAMS("2027-01-07")); return w; };
  let r = await at("2027-01-08T05:30:00Z").get("/api/live/streams");           // 00:30 EST on the 8th
  assert.equal(r.status, 200);
  assert.equal((await r.json()).day, "2027-01-07");
  r = await at("2027-01-08T06:30:00Z").get("/api/live/streams");               // 01:30
  assert.equal(r.status, 404, "past the hour: no file for today");
  const w = at("2027-01-08T05:30:00Z");
  w.r2.seed("streams/2027-01-08.json", STREAMS("2027-01-08"));
  assert.equal((await (await w.get("/api/live/streams")).json()).day, "2027-01-08", "today's when it exists");
  r = await at("2027-01-07T04:30:00Z").get("/api/live/streams");               // 23:30 EST on the 6th
  assert.equal(r.status, 404, "New Hampshire's date, not UTC's");
});

test("a bucket that cannot be read is a 503, never a 404 and never kept", async () => {
  const w = setup();
  w.r2.hooks.get = async () => { throw new Error("R2 said 500"); };
  for (const p of ["/api/live/streams", "/api/live/votes/2027-01-07"]) {
    const r = await w.get(p);
    assert.equal(r.status, 503, p);
    assert.equal(r.headers.get("Cache-Control"), "no-store");
  }
  assert.equal(w.cache.store.size, 0);
});

test("a page elsewhere can poll the votes file with If-None-Match: its preflight is answered, and it can read the ETag", async () => {
  const w = setup();
  w.r2.seed("votes/2027-01-07.json", VOTES);
  const pre = await w.get("/api/live/votes/2027-01-07", { method: "OPTIONS",
    headers: { Origin: "https://example.org", "Access-Control-Request-Headers": "if-none-match" } });
  assert.equal(pre.status, 204);
  assert.equal(pre.headers.get("Access-Control-Allow-Origin"), "*");
  assert.equal(pre.headers.get("Access-Control-Allow-Methods"), "GET, HEAD");
  assert.equal(pre.headers.get("Access-Control-Allow-Headers"), "If-None-Match");
  const r = await w.get("/api/live/votes/2027-01-07");
  assert.equal(r.headers.get("Access-Control-Expose-Headers"), "ETag");
  const again = await w.get("/api/live/votes/2027-01-07", { headers: { "If-None-Match": r.headers.get("ETag") } });
  assert.equal(again.headers.get("Access-Control-Expose-Headers"), "ETag", "on the 304 too");
  const s = await w.get("/api/live/streams", { method: "OPTIONS" });
  assert.equal(s.status, 405, "the streams answer no preflight");
  assert.equal(s.headers.get("Access-Control-Allow-Origin"), null);
});

test("a query string is no way round the copy to the bucket; If-None-Match: * matches; every answer says nosniff", async () => {
  const w = setup();
  w.r2.seed("votes/2027-01-07.json", VOTES);
  w.r2.seed("streams/2027-01-07.json", STREAMS("2027-01-07"));
  for (let i = 0; i < 5; i++) { await w.get(`/api/live/votes/2027-01-07?r=${i}`); await w.get(`/api/live/streams?x=${i}`); }
  const reads = key => w.r2.ops.filter(([op, k]) => op === "get" && k === key).length;
  assert.deepEqual([reads("votes/2027-01-07.json"), reads("streams/2027-01-07.json")], [1, 1]);
  assert.equal((await w.get("/api/live/votes/2027-01-07", { headers: { "If-None-Match": "*" } })).status, 304);
  for (const [p, init] of [["/api/live/votes/2027-01-07", {}], ["/api/live/votes/2027-01-09", {}],
                           ["/api/live/votes/2027-01-07", { method: "POST" }], ["/api/live/streams", {}],
                           ["/api/live/votes/2027-01-07", { method: "OPTIONS" }]]) {
    assert.equal((await w.get(p, init)).headers.get("X-Content-Type-Options"), "nosniff", `${init.method || "GET"} ${p}`);
  }
  w.r2.hooks.get = async () => { throw new Error("R2 said 500"); };
  w.now += 60_000;
  assert.equal((await w.get("/api/live/votes/2027-01-07")).headers.get("X-Content-Type-Options"), "nosniff", "503");
});
