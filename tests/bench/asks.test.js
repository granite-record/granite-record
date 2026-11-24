// The owner's Your input tab, server side (workers/bench/store.js askList, askWaiting,
// askAnswer; functions/api/bench/asks.js; view.js's count): her list and her answers, her
// own link alone, every refusal, the latest answer shown and the rest kept, a database made
// before the two tables, and a contributor's bench exactly as it was.

import test from "node:test";
import assert from "node:assert/strict";
import { cleanNote } from "../../functions/api/report.js";
import { longNote, onRequest as asksFn } from "../../functions/api/bench/asks.js";
import { onRequest as nextFn } from "../../functions/api/bench/next.js";
import { onRequest as judgeFn } from "../../functions/api/bench/judge.js";
import { onRequest as undoFn } from "../../functions/api/bench/undo.js";
import { ASK_NOTE_MOST, QUEUES, askAnswer, askList, askWaiting, linkFor, makeLink, queuesOf }
  from "../../workers/bench/store.js";
import { SITE, T0, addLink, askCard, at, benchBeforeAsks, loadAsks, loadPack, makeBench } from "./world.js";

const ROUTES = { "/api/bench/asks": asksFn, "/api/bench/next": nextFn, "/api/bench/judge": judgeFn,
                 "/api/bench/undo": undoFn };
const ONE = { yes: "Save the note" };
const LIST = [
  { key: "nav-rows", section: "release", ord: 1000, card: askCard() },
  { key: "map-dots", section: "release", ord: 1, card: askCard({ title: "Map dots", answers: { yes: "Looks right", no: "Needs changes" } }) },
  { key: "old-one", section: "design", ord: 2000, card: askCard({ title: "An old one" }), state: "withdrawn" },
  { key: "a-note", section: "notes", ord: 4000, card: askCard({ title: "Anything else", answers: ONE, recommended: null }) },
];

async function bench({ before = false } = {}) {
  const d1 = before ? benchBeforeAsks() : makeBench();
  await loadPack(d1, { topics: 6 });
  if (!before) loadAsks(d1, LIST);
  const owner = await addLink(d1, { id: "owner2", name: "You", role: "owner" });
  const sam = await addLink(d1, { id: "sam234", name: "Sam" });
  return { d1, tokens: { owner, sam }, owner: await linkFor(d1, owner.token), sam: await linkFor(d1, sam.token) };
}

function captureConsole() {
  const lines = [], saved = {};
  for (const m of ["log", "info", "warn", "error", "debug"]) {
    saved[m] = console[m];
    console[m] = (...a) => lines.push(a.map(String).join(" "));
  }
  return { lines, restore() { Object.assign(console, saved); } };
}

async function world(opts) {
  const b = await bench(opts);
  const w = { ...b, now: new Date(T0), logs: captureConsole() };
  w.env = { BENCH_DB: b.d1, REPORT_ORIGINS: "graniterecord.org", CLOCK: () => w.now.getTime() };
  w.later = s => { w.now = new Date(w.now.getTime() + s * 1000); };
  w.call = async (path, body, { raw = null, method = "POST", site = "same-origin" } = {}) => {
    const req = new Request(SITE + path, { method, headers: { "Content-Type": "application/json", Origin: SITE,
                                                              ...(site ? { "Sec-Fetch-Site": site } : {}) },
                                          ...(method === "POST" ? { body: raw ?? JSON.stringify(body ?? {}) } : {}) });
    const res = await ROUTES[path]({ request: req, env: w.env });
    const text = await res.text();
    let data = null;
    try { data = JSON.parse(text); } catch { /* not JSON */ }
    return { status: res.status, text, data };
  };
  w.close = () => w.logs.restore();
  return w;
}

test("her list: every entry not withdrawn, in the list's order, each with her latest answer", async () => {
  const { d1, owner } = await bench();
  let list = await askList(d1);
  assert.deepEqual(list.map(x => x.key), ["map-dots", "nav-rows", "a-note"], "by ord, the withdrawn one left out");
  assert.ok(list.every(x => x.answer === null));
  assert.equal(list[1].card.title, "Navigation in two rows");
  assert.equal(await askWaiting(d1), 3);
  assert.deepEqual(await askAnswer(d1, owner, { key: "nav-rows", answer: "no", note: { text: "It wraps.", hidden: 0 } },
                                   at(0)), { ok: true, answer: "no" });
  assert.equal(await askWaiting(d1), 2);
  assert.deepEqual(await askAnswer(d1, owner, { key: "nav-rows", answer: "yes", note: { text: "Fine now.\nThanks.", hidden: 0 } },
                                   at(2)), { ok: true, answer: "yes" });
  list = await askList(d1);
  assert.deepEqual(list[1].answer, { answer: "yes", note: "Fine now.\nThanks.", at: at(2).toISOString() },
                   "the latest answer is the one shown");
  assert.equal(d1.rows("ask_answers").filter(r => r.key === "nav-rows").length, 2, "and the one before it is kept");
  assert.equal(await askWaiting(d1), 2, "an entry answered twice is answered");
  assert.ok((await askAnswer(d1, owner, { key: "a-note", answer: "yes", note: { text: "", hidden: 0 } }, at(4))).ok,
            "an entry offering one answer takes it");
});

test("refused: an entry unknown or withdrawn, an answer it does not offer, a long note, two saves in a second", async () => {
  const { d1, owner } = await bench();
  const say = (key, answer, s, text = "") => askAnswer(d1, owner, { key, answer, note: { text, hidden: 0 } }, at(s));
  assert.deepEqual(await say("no-such-entry", "yes", 0), { ok: false, why: "gone" });
  assert.deepEqual(await say("x", "yes", 0), { ok: false, why: "gone" }, "not a key at all");
  assert.deepEqual(await say("old-one", "yes", 0), { ok: false, why: "gone" }, "withdrawn");
  assert.deepEqual(await say("map-dots", "unsure", 0), { ok: false, why: "bad" }, "an answer the entry does not offer");
  assert.deepEqual(await say("map-dots", "partly", 0), { ok: false, why: "bad" });
  assert.deepEqual(await say("a-note", "no", 0), { ok: false, why: "bad" }, "the one answer offered, and no other");
  assert.deepEqual(await say("map-dots", "yes", 0, "x".repeat(ASK_NOTE_MOST + 1)), { ok: false, why: "long" });
  assert.equal(d1.rows("ask_answers").length, 0, "nothing refused was kept");
  assert.ok((await say("map-dots", "yes", 0, "x".repeat(ASK_NOTE_MOST))).ok, "2,000 characters is a note");
  assert.deepEqual(await say("nav-rows", "yes", 0.5), { ok: false, why: "fast" }, "one save a second");
  assert.ok((await say("nav-rows", "yes", 1.5)).ok);
  assert.equal(ASK_NOTE_MOST, 2000);
});

test("a withdrawn entry is hidden, and her answers to it are kept", async () => {
  const { d1, owner } = await bench();
  await askAnswer(d1, owner, { key: "map-dots", answer: "no", note: { text: "Too faint.", hidden: 0 } }, at(0));
  d1.sql.prepare("UPDATE asks SET state = 'withdrawn' WHERE key = 'map-dots'").run();
  assert.ok(!(await askList(d1)).some(x => x.key === "map-dots"));
  assert.equal(await askWaiting(d1), 2);
  assert.deepEqual(d1.rows("ask_answers").map(r => [r.key, r.answer, r.note]), [["map-dots", "no", "Too faint."]]);
});

test("a database made before the two tables: no list and no count, and her bench as it was", async () => {
  const w = await world({ before: true });
  try {
    assert.deepEqual(await askList(w.d1), []);
    assert.equal(await askWaiting(w.d1), null);
    assert.deepEqual(await askAnswer(w.d1, w.owner, { key: "nav-rows", answer: "yes" }, at(0)), { ok: false, why: "gone" });
    const r = await w.call("/api/bench/asks", { t: w.tokens.owner.token, action: "list" });
    assert.deepEqual([r.status, r.data], [200, { asks: [], waiting: null }]);
    const v = await w.call("/api/bench/next", { t: w.tokens.owner.token, queue: "topic" });
    assert.deepEqual([v.status, v.data.items.length, v.data.asks], [200, 2, null], "her Judge tab works, with no count");
  } finally { w.close(); }
});

test("the route is her own link's alone: every other is the same 404 as no bench, and every refusal says why", async () => {
  const w = await world();
  try {
    const t = w.tokens.owner.token;
    assert.equal((await w.call("/api/bench/asks", { t: w.tokens.sam.token, action: "list" })).status, 404,
                 "a contributor's link");
    const before = w.d1.prepared.length;
    assert.equal((await w.call("/api/bench/asks", { t: "A".repeat(43), action: "list" })).status, 404, "a wrong token");
    assert.equal(w.d1.prepared.length - before, 1, "one statement for a wrong token");
    w.d1.sql.prepare("UPDATE links SET state = 'off' WHERE id = 'owner2'").run();
    assert.equal((await w.call("/api/bench/asks", { t, action: "list" })).status, 404, "her link turned off");
    w.d1.sql.prepare("UPDATE links SET state = 'active' WHERE id = 'owner2'").run();
    let r = await w.call("/api/bench/asks", { t, action: "list" });
    assert.equal(r.status, 200);
    assert.deepEqual(r.data.asks.map(x => x.key), ["map-dots", "nav-rows", "a-note"]);
    assert.equal(r.data.waiting, 3);
    r = await w.call("/api/bench/asks", { t, action: "answer", key: "nav-rows", answer: "no", note: "It wraps on my phone." });
    assert.deepEqual([r.status, r.data.saved, r.data.waiting], [200, { answer: "no" }, 2]);
    assert.equal(r.data.asks.find(x => x.key === "nav-rows").answer.note, "It wraps on my phone.");
    assert.deepEqual([(r = await w.call("/api/bench/asks", { t, action: "answer", key: "map-dots", answer: "yes" })).status,
                      r.data.why], [429, "fast"]);
    w.later(2);
    for (const [body, status, why] of [[{ key: "old-one", answer: "yes" }, 409, "gone"],
                                       [{ key: "nope-nope", answer: "yes" }, 409, "gone"],
                                       [{ key: "map-dots", answer: "unsure" }, 400, "bad"],
                                       [{ key: "map-dots", answer: "yes", note: "x".repeat(2001) }, 400, "long"]]) {
      r = await w.call("/api/bench/asks", { t, action: "answer", ...body });
      assert.deepEqual([r.status, r.data.why], [status, why], JSON.stringify(body).slice(0, 80));
      assert.ok(Array.isArray(r.data.asks), "a refusal brings the list back too");
      w.later(2);
    }
    assert.equal((await w.call("/api/bench/asks", { t, action: "merge" })).status, 400);
    assert.equal(w.d1.rows("ask_answers").length, 1, "nothing refused was kept");
  } finally { w.close(); }
});

test("its body may be 8 KiB, for a note of 2,000 characters; every other route keeps 4 KiB", async () => {
  const w = await world();
  try {
    const t = w.tokens.owner.token;
    const note = "é".repeat(1990) + "\n\n\n\nend";
    const raw = JSON.stringify({ t, action: "answer", key: "nav-rows", answer: "yes", note });
    assert.ok(new TextEncoder().encode(raw).length > 4096 && new TextEncoder().encode(raw).length < 8192);
    const r = await w.call("/api/bench/asks", null, { raw });
    assert.equal(r.status, 200, r.text.slice(0, 200));
    assert.equal(w.d1.rows("ask_answers").at(-1).note, "é".repeat(1990) + "\n\nend", "cleaned: a third blank line gone");
    assert.equal((await w.call("/api/bench/next", null, { raw: JSON.stringify({ t, x: "y".repeat(5000) }) })).status, 404,
                 "the other routes' cap is as it was");
    w.later(2);
    const big = JSON.stringify({ t, action: "list", x: "y".repeat(8200) });
    assert.equal((await w.call("/api/bench/asks", null, { raw: big })).status, 404, "a body over 8 KiB");
    const hidden = "a" + String.fromCodePoint(0x200B) + "b\r\nc";
    await w.call("/api/bench/asks", { t, action: "answer", key: "map-dots", answer: "no", note: hidden });
    const kept = w.d1.rows("ask_answers").at(-1);
    assert.deepEqual([kept.note, kept.hidden], ["ab\nc", 1], "the characters that hide text taken out, and said to have been");
  } finally { w.close(); }
});

test("longNote is the report box's cleaning, with room for 2,000 characters where it keeps 1,000", () => {
  const samples = ["", "  plain  ", "a\r\nb\rc", "x  \n  y", "one\n\n\n\n\ntwo", "tab\there", "zero" + "​" + "width",
                   "‮right to left", "soft­hyphen", "️selector", "ㅤfiller", "ﾠhalf", "ﬁ ligature",
                   "\u0007bell\u0085next", "é", "é", "\u{E0041}tag", "😀 emoji", "a".repeat(999)];
  for (const s of samples) {
    const c = cleanNote(s);
    assert.deepEqual(longNote(s, 1000), { text: c.text, hidden: c.hidden ? 1 : 0 }, JSON.stringify(s).slice(0, 40));
  }
  const long = ("A line of a note. ".repeat(10) + "\n").repeat(10);
  assert.equal(cleanNote(long).text.length, 1000);
  const whole = long.replace(/ \n/g, "\n").trim();
  assert.ok(whole.length > 1700);
  assert.equal(longNote(long, ASK_NOTE_MOST).text, whole, "kept whole, where the report box cuts it");
  assert.equal(longNote("x".repeat(2500), ASK_NOTE_MOST).text.length, 2000);
});

test("a contributor's bench is as it was: no count, no new key, and no link can be given the tab", async () => {
  const w = await world();
  try {
    const t = w.tokens.sam.token;
    const keys = d => Object.keys(d).sort();
    const base = ["far", "items", "progress", "queue", "queues", "role", "state"];
    let r = await w.call("/api/bench/next", { t, queue: "topic" });
    assert.deepEqual(keys(r.data), base);
    assert.doesNotMatch(r.text, /asks|input|nav-rows|Navigation/);
    r = await w.call("/api/bench/judge", { t, queue: "topic", ref: r.data.items[0].ref, answer: { answer: "yes" } });
    assert.deepEqual(keys(r.data), [...base, "saved"].sort());
    w.later(2);
    r = await w.call("/api/bench/undo", { t, queue: "topic" });
    assert.deepEqual(keys(r.data), [...base, "undone"].sort());
    assert.doesNotMatch(r.text, /asks/);
    const mine = await w.call("/api/bench/next", { t: w.tokens.owner.token, queue: "topic" });
    assert.deepEqual([keys(mine.data), mine.data.asks], [[...base, "asks"].sort(), 3], "her view carries the count");
    assert.deepEqual(QUEUES, ["timing", "topic", "tag"], "the tab is not a queue");
    assert.equal(await makeLink(w.d1, { name: "Ann", queues: ["asks", "input"] }, at(0)), null,
                 "a link made for the tab alone is not made");
    assert.deepEqual(queuesOf({ role: "contributor", queues: JSON.stringify(["asks", "input", "tag"]) }), ["tag"]);
    assert.ok(!queuesOf({ role: "owner" }).includes("asks"));
  } finally { w.close(); }
});

test("the log is codes and counts: no note, no key, no title, no token", async () => {
  const w = await world();
  try {
    const t = w.tokens.owner.token;
    await w.call("/api/bench/asks", { t, action: "list" });
    await w.call("/api/bench/asks", { t, action: "answer", key: "nav-rows", answer: "no", note: "a secret note" });
    await w.call("/api/bench/asks", { t, action: "answer", key: "old-one", answer: "no", note: "a secret note" });
    w.d1.failWhen = sql => /FROM asks/.test(sql) ? new Error(`secret ${t} nav-rows`) : null;
    await w.call("/api/bench/asks", { t, action: "list" });
    w.d1.failWhen = null;
    assert.ok(w.logs.lines.includes("bench asks.list 3") && w.logs.lines.includes("bench asks.answered") &&
              w.logs.lines.includes("bench asks.refused.gone") && w.logs.lines.includes("bench asks.error.Error"),
              w.logs.lines.join(" | "));
    for (const line of w.logs.lines) {
      assert.match(line, /^bench [a-z0-9_.?-]+( \d+)?$/i, line);
      for (const secret of ["secret", "nav-rows", "old-one", "Navigation", "owner2"])
        assert.ok(!line.includes(secret), `${line} carries ${secret}`);
      for (let i = 0; i + 12 <= t.length; i++) assert.ok(!line.includes(t.slice(i, i + 12)), `${line} carries a token`);
    }
  } finally { w.close(); }
});
