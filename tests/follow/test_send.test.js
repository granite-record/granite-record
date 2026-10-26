// sender.js's test send (A TEST SEND, 23 October 2026): POST /test-send on
// the preview sender, which builds a reader's daily, weekly and "You're
// following" email over the last nights and sends each with "[Test] " before
// its subject, recording nothing. Behind two guards, both or a 404: the
// TEST_SEND var that only the preview's vars set, and the TEST_SEND_TOKEN
// secret the request's bearer token must match.
//
// preflight's _follow_test_send runs the cases named "test send:" here by
// name; a case renamed or taken out fails it.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import sender, { TEST_KINDS, TEST_SEND_MOST, run, testAsk } from "../../workers/follow/sender.js";
import { makeKeys, makeWorld, SITE, tokensIn } from "./fakes.js";
import { signUp, snapshot } from "./flows.js";
import { followKeys, insertSubscriber } from "./rows.js";

const WORKER = "https://graniterecord-follow-sender-preview.example.workers.dev";
const TOML = readFileSync(new URL("../../workers/follow/wrangler.toml", import.meta.url), "utf8");
const MORNING = "2026-10-10T15:00:00Z";      // the fixtures' current.json is of 10 October

const newToken = () => Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString("base64");

// One section's plain `KEY = "value"` lines of wrangler.toml: what Cloudflare
// hands the Worker as env, for the section named ("vars" is production's).
function tomlVars(section) {
  const out = {};
  let inside = false;
  for (const line of TOML.split(/\r?\n/)) {
    const head = /^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$/.exec(line);
    if (head) { inside = head[1] === section; continue; }
    const m = inside && /^\s*([A-Z_][A-Z0-9_]*)\s*=\s*"([^"]*)"\s*(#.*)?$/.exec(line);
    if (m) out[m[1]] = m[2];
  }
  return out;
}

// A world whose sender is the preview's: the var on and a token set.
function preview(opts = {}) {
  const w = makeWorld({ now: MORNING, ...opts });
  w.env.TEST_SEND = "on";
  w.env.TEST_SEND_TOKEN = newToken();
  return w;
}

// Ask the Worker as the person would, and keep the answer for leaks().
async function ask(w, { body, auth, path = "/test-send", method = "POST", env = w.env } = {}) {
  const bearer = auth === undefined ? `Bearer ${env.TEST_SEND_TOKEN}` : auth;
  const req = new Request(WORKER + path, {
    method,
    headers: { ...(bearer ? { Authorization: bearer } : {}), "Content-Type": "application/json" },
    ...(method === "POST" && body !== undefined
      ? { body: typeof body === "string" ? body : JSON.stringify(body) } : {}),
  });
  const res = await sender.fetch(req, env, { waitUntil() {} });
  const text = await res.text();
  const rec = { url: req.url, method, status: res.status, headers: Object.fromEntries(res.headers),
                body: text };
  w.responses.push(rec);
  let answer = null;
  try { answer = JSON.parse(text); } catch { /* a 404's plain text */ }
  return { ...rec, answer };
}

async function reader(w, name, follows, extra = {}) {
  const address = w.address(name);
  const r = await insertSubscriber(w.d1, w.env, address, { follows, ...extra });
  return { ...r, address };
}

const mailsTo = (w, address) => w.net.outbox.filter(m => m.to.includes(address));
const isNotFound = r => r.status === 404 && r.body === "Not found\n";

// ---- the guards -----------------------------------------------------------------------------
test("test send: 404 without the TEST_SEND var", async () => {
  const w = preview();
  try {
    await reader(w, "no.var", ["bill:2026/HB9903"]);
    for (const v of [undefined, "", "off", "ON", "On", "yes", "true", "1", " on"]) {
      const env = { ...w.env, TEST_SEND: v };
      if (v === undefined) delete env.TEST_SEND;
      assert.ok(isNotFound(await ask(w, { env })), `TEST_SEND ${JSON.stringify(v)} answered`);
    }
    // And every other address, as it always was.
    for (const [method, path] of [["GET", "/"], ["GET", "/test-send"], ["POST", "/"]])
      assert.ok(isNotFound(await ask(w, { method, path, env: { ...w.env, TEST_SEND: undefined } })));
    assert.equal(w.net.outbox.length, 0);
    assert.deepEqual(w.net.asked, [], "a 404 asks nothing of the site, the database or Resend");
  } finally { w.close(); }
});

test("test send: 404 with a wrong or missing token", async () => {
  const w = preview();
  try {
    await reader(w, "wrong.token", ["bill:2026/HB9903"]);
    const right = w.env.TEST_SEND_TOKEN;
    const flipped = (right[0] === "A" ? "B" : "A") + right.slice(1);
    for (const auth of ["", `Bearer ${flipped}`, `Bearer ${right.slice(0, -1)}`, `Bearer ${right}x`,
                        `Basic ${right}`, right, `Bearer`, `Bearer  `, `Bearer ${right} extra`])
      assert.ok(isNotFound(await ask(w, { auth })), `${JSON.stringify(auth.replace(right, "<token>"))} answered`);
    // No secret set, or one too short to be the README's: no token matches.
    for (const t of [undefined, "", "   ", "short-token", "x".repeat(31)]) {
      const env = { ...w.env, TEST_SEND_TOKEN: t };
      assert.ok(isNotFound(await ask(w, { env, auth: `Bearer ${t ?? ""}` })), `a token of ${String(t).length}`);
    }
    // The right token on another address, or by another method, is still nothing.
    for (const [method, path] of [["GET", "/test-send"], ["PUT", "/test-send"], ["POST", "/test-send/"],
                                  ["POST", "/TEST-SEND"], ["POST", "/"]])
      assert.ok(isNotFound(await ask(w, { method, path })), `${method} ${path} answered`);
    assert.equal(w.net.outbox.length, 0);
    // The right one, with a newline after it as a pipe into `wrangler secret put` can leave.
    const ok = await ask(w, { env: { ...w.env, TEST_SEND_TOKEN: `${right}\r\n` }, body: { kinds: ["daily"] } });
    assert.equal(ok.status, 200);
    assert.equal(ok.answer.sent, 1);
  } finally { w.close(); }
});

test("test send: 404 on the production configuration, and answered on the preview's", async () => {
  const prod = tomlVars("vars"), prev = tomlVars("env.preview.vars");
  assert.ok(prod.SITE_ORIGIN && prev.SITE_ORIGIN, "both sections of wrangler.toml were read");
  assert.equal(prod.TEST_SEND, undefined, "production's vars set TEST_SEND");
  assert.equal(prev.TEST_SEND, "on", "the preview's vars do not set TEST_SEND");
  const w = preview();
  try {
    await reader(w, "prod.config", ["bill:2026/HB9903"]);
    // Production's own vars, with every secret -- a token included, as if one
    // were set there by mistake -- and the right bearer token.
    const keys = Object.fromEntries(Object.entries(w.env).filter(([k]) => /^[A-Z_]+$/.test(k) && !(k in prev)));
    const production = { ...keys, ...prod, FOLLOW_DB: w.d1, SITE_ORIGIN: SITE, SEND_GAP_MS: "0" };
    delete production.TEST_SEND;
    production.TEST_SEND_TOKEN = w.env.TEST_SEND_TOKEN;
    assert.ok(isNotFound(await ask(w, { env: production })));
    assert.equal(w.net.outbox.length, 0);
    // The preview's own vars (its site is the fakes' here) answer.
    const previewEnv = { ...keys, ...prev, FOLLOW_DB: w.d1, SITE_ORIGIN: SITE, SEND_GAP_MS: "0",
                         TEST_SEND_TOKEN: w.env.TEST_SEND_TOKEN, CLOCK: w.env.CLOCK };
    const r = await ask(w, { env: previewEnv, body: { kinds: ["daily"] } });
    assert.equal(r.status, 200);
    assert.equal(w.net.outbox.length, 1);
  } finally { w.close(); }
});

// ---- what it sends --------------------------------------------------------------------------
test("test send: only confirmed subscribers are sent, each subject prefixed Test, with their own links", async () => {
  const w = preview();
  try {
    const a = await reader(w, "first.reader", ["bill:2026/HB9903", "topic:housing"]);
    const b = await reader(w, "second.reader", ["member:990001"], { frequency: "weekly" });
    // A request never confirmed is in pending, not subscribers: it is sent nothing.
    const waiting = w.address("never.confirmed");
    await signUp(w, waiting, "bill", "2026/HB9901");
    const before = w.net.outbox.length;
    assert.equal(mailsTo(w, waiting).length, 1, "the sign-up's confirmation");

    const r = await ask(w);
    assert.equal(r.status, 200);
    assert.deepEqual(r.answer.kinds, TEST_KINDS);
    assert.equal(r.answer.nights, 7);
    assert.equal(r.answer.subscribers, 2);
    assert.equal(r.answer.sent, 6);
    assert.deepEqual(r.answer.emails, { daily: 2, weekly: 2, welcome: 2 });
    assert.equal(r.answer.ok, true);
    const sent = w.net.outbox.slice(before);
    assert.equal(sent.length, 6);
    assert.equal(mailsTo(w, waiting).length, 1, "the unconfirmed address had nothing more");
    for (const m of sent) assert.match(m.subject, /^\[Test\] \S/, m.subject);
    for (const [x, freq] of [[a, "daily"], [b, "weekly"]]) {
      const mine = mailsTo(w, x.address);
      assert.deepEqual(mine.map(m => m.text.slice(0, m.text.search(/ — |:/))),
        ["Daily update", "Weekly update", "You are now following"], "the daily, the weekly and the welcome");
      // The reader's own manage and unsubscribe links, as every real email carries.
      for (const m of mine) {
        const t = tokensIn(m);
        assert.equal(t.manage, x.links.manage);
        assert.equal(t.unsub, x.links.unsub);
        assert.equal(t.header, x.links.unsub);
      }
      const welcome = mine.find(m => m.text.startsWith("You are now following:"));
      assert.match(welcome.text, freq === "weekly" ? /Updates come weekly/ : /Updates come daily/);
    }
    assert.match(mailsTo(w, a.address).find(m => /Daily update/.test(m.text)).text, /^Daily update — Saturday, October 10, 2026/);
    assert.match(mailsTo(w, a.address).find(m => /Weekly update/.test(m.text)).text, /^Weekly update — /);

    // Asked again, it sends again: a fresh Idempotency-Key each request.
    const again = await ask(w, { body: { kinds: ["welcome"] } });
    assert.equal(again.answer.sent, 2);
    assert.equal(w.net.repeats, 0, "Resend refused nothing as a repeat");
    assert.equal([...w.net.keys].filter(k => k.startsWith("test/")).length, 8);
    assert.equal(new Set([...w.net.keys].filter(k => k.startsWith("test/")).map(k => k.split("/")[1])).size, 2,
      "one key's batch a request");
  } finally { w.close(); }
});

test("test send: changes no subscriber row, cursor, follow, sends or signup_days", async () => {
  const w = preview();
  try {
    // A reader mid-week, cursor and all, following a bill that ended on the
    // 7th: a real run would move the cursor, count the send and end the follow.
    await reader(w, "kept.as.was", ["bill:2026/HB9902", "bill:2026/HB9903"],
      { lastSentOn: "2026-10-05", sentDate: "2026-10-05", sentBuilt: "2026-10-05T09:04:11Z" });
    await reader(w, "weekly.one", ["committee:H90"], { frequency: "weekly" });
    await w.d1.prepare("INSERT INTO signup_days (day, n) VALUES ('2026-10-10', 3)").run();
    const before = snapshot(w), follows = await followKeys(w.d1, w.env);
    const prepared = w.d1.prepared.length;
    const r = await ask(w);
    assert.equal(r.answer.sent, 6);
    assert.deepEqual(snapshot(w), before, "a table changed");
    assert.deepEqual(await followKeys(w.d1, w.env), follows);
    for (const sql of w.d1.prepared.slice(prepared))
      assert.match(sql, /^\s*SELECT\b/i, `the test send wrote: ${sql}`);
  } finally { w.close(); }
});

test("test send: a run after a test send does exactly what a run without one does", async () => {
  // Two worlds, one after the other (each holds the global fetch while it
  // is open), with the same keys and the same readers: one is sent a test
  // first, and then each has the 8:00 run of 10 October.
  const keys = makeKeys();
  const world = async withTest => {
    const w = preview();
    try {
      Object.assign(w.env, keys);
      await reader(w, "same.daily", ["bill:2026/HB9901", "bill:2026/HB9902", "bill:2026/HB9903", "topic:housing"],
        { lastSentOn: "2026-10-07", sentDate: "2026-10-07", sentBuilt: "2026-10-07T09:06:30Z" });
      await reader(w, "same.weekly", ["committee:H90", "member:990001"],
        { frequency: "weekly", lastSentOn: "2026-10-03", sentDate: "2026-10-03", sentBuilt: "2026-10-03T09:00:00Z" });
      if (withTest) assert.equal((await ask(w)).answer.sent, 6);
      const tested = w.net.outbox.length, logged = w.logs.lines.length;
      w.at("2026-10-10T12:00:00Z");                    // 8:00 in New Hampshire, a Saturday
      const out = await run(w.env, w.now);
      const sealed = new Set(["email_enc", "follow_enc"]);
      const tables = Object.fromEntries(Object.entries(snapshot(w)).map(([t, rows]) =>
        [t, rows.map(r => Object.fromEntries(Object.entries(r).filter(([k]) => !sealed.has(k))))]));
      return { out, tables, follows: await followKeys(w.d1, w.env), logs: w.logs.lines.slice(logged),
               mail: w.net.outbox.slice(tested).map(({ at, ...m }) => m) };
    } finally { w.close(); }
  };
  const plain = await world(false), tested = await world(true);
  assert.ok(plain.mail.length >= 2, "the run sent the daily and the weekly");
  assert.ok(plain.mail.every(m => !m.subject.startsWith("[Test]")));
  assert.deepEqual(tested.mail, plain.mail, "the run's emails differ");
  assert.deepEqual(tested.out, plain.out);
  assert.deepEqual(tested.tables, plain.tables);
  assert.deepEqual(tested.follows, plain.follows);
  assert.deepEqual(tested.logs, plain.logs);
});

test("test send: testify blocks where a followed bill has a public hearing ahead", async () => {
  const w = preview();
  try {
    // HB 9903's hearing of 14 October is set on the 7th: one night, the
    // 10th, has nothing on it, and a real daily that morning would say nothing.
    const x = await reader(w, "hearing.ahead", ["bill:2026/HB9903"]);
    const r = await ask(w, { body: { kinds: ["daily", "weekly"], nights: 1 } });
    assert.equal(r.answer.sent, 2);
    assert.equal(r.answer.testify, 2);
    assert.equal(r.answer.nothing_new, 0);
    assert.ok(!r.answer.notes.some(n => /testify/.test(n)));
    const [daily, weekly] = mailsTo(w, x.address);
    // The site's Testify button and pane, in their words (26 October 2026).
    assert.match(daily.text, /\n {2}Testify until Oct 14\n/);
    assert.match(daily.text, /The public hearing on HB 9903-FN is scheduled for Wednesday, October 14 at 10:00\u00a0AM in /);
    assert.match(daily.html, /Submit Online Testimony<\/a>/);
    // The weekly has it beside the hearing in the week ahead.
    assert.match(weekly.text, /Wednesday, October 14, 10:00 a\.m\.: Public hearing/);
    assert.match(weekly.text, /Submit Online Testimony: https:/);

    // ... and the run that morning, for the same reader, sends nothing: the
    // block is the test's alone, outside the three mornings a real one says it.
    await w.d1.prepare("UPDATE subscribers SET sent_date = '2026-10-09', sent_built = '2026-10-09T09:02:05Z'").run();
    const before = w.net.outbox.length;
    w.at("2026-10-10T12:00:00Z");
    await run(w.env, w.now);
    assert.equal(w.net.outbox.length, before);
  } finally { w.close(); }
});

test("test send: an empty digest is a short note, and no hearing ahead is said", async () => {
  const w = preview();
  try {
    const x = await reader(w, "nothing.new", ["bill:2026/HB9901"]);
    const r = await ask(w, { body: { kinds: ["daily"], nights: 1 } });
    assert.equal(r.status, 200);
    assert.equal(r.answer.sent, 1);
    assert.equal(r.answer.nothing_new, 1);
    assert.equal(r.answer.testify, 0);
    assert.ok(r.answer.notes.includes("no followed bill has a public hearing ahead, so no email has a testify block"));
    const [m] = mailsTo(w, x.address);
    assert.equal(m.subject, "[Test] Nothing new for your daily update on October 10, 2026");
    assert.match(m.text, /^Daily update — Saturday, October 10, 2026\n\nNothing you follow had news on the record on October 10, 2026, so a real daily update would not have been sent\./);
    assert.match(m.text, /Nothing about your updates has changed\./);
    assert.equal(tokensIn(m).manage, x.links.manage, "the note carries the way out too");
    assert.ok(m.headers["List-Unsubscribe"]);

    // Two nights back, not three: the 8th has HB 9901's interim study report.
    const week = await ask(w, { body: { kinds: ["weekly"], nights: 2 } });
    assert.equal(week.answer.nothing_new, 1);
    assert.equal(mailsTo(w, x.address)[1].subject, "[Test] Nothing new for your weekly update in the last 2 nights");
    assert.match(mailsTo(w, x.address)[1].text,
      /from October 9, 2026 to October 10, 2026, so a real weekly update would not have been sent/);
    const three = await ask(w, { body: { kinds: ["weekly"], nights: 3 } });
    assert.equal(three.answer.nothing_new, 0, "the study report of the 8th is news");
  } finally { w.close(); }
});

test("test send: at most five subscribers, and the answer says how many were left", async () => {
  const w = preview();
  try {
    const all = [];
    for (let i = 1; i <= TEST_SEND_MOST + 2; i++) all.push(await reader(w, `capped.${i}`, ["bill:2026/HB9903"]));
    const r = await ask(w, { body: { kinds: ["daily"] } });
    assert.equal(r.answer.subscribers, 7);
    assert.equal(r.answer.taken, TEST_SEND_MOST);
    assert.equal(r.answer.sent, TEST_SEND_MOST);
    assert.ok(r.answer.notes.includes(
      "7 confirmed subscribers: test emails went to the first 5 by id, and the other 2 were sent nothing"));
    assert.deepEqual(all.map(x => mailsTo(w, x.address).length), [1, 1, 1, 1, 1, 0, 0]);
  } finally { w.close(); }
});

test("test send: a reader paused today is left out, as a run leaves them", async () => {
  const w = preview();
  try {
    const p = await reader(w, "paused.reader", ["bill:2026/HB9903"]);
    const q = await reader(w, "pause.over", ["bill:2026/HB9903"]);
    await w.d1.prepare("UPDATE subscribers SET paused_until = ?1 WHERE id = ?2").bind("2026-10-10", p.id).run();
    await w.d1.prepare("UPDATE subscribers SET paused_until = ?1 WHERE id = ?2").bind("2026-10-09", q.id).run();
    const r = await ask(w, { body: { kinds: ["daily", "welcome"] } });
    assert.deepEqual(r.answer.skipped, { paused: 1 });
    assert.equal(mailsTo(w, p.address).length, 0);
    assert.equal(mailsTo(w, q.address).length, 2);
    assert.doesNotMatch(mailsTo(w, q.address)[1].text, /paused/, "a pause gone by is not told");
  } finally { w.close(); }
});

test("test send: a refusal is counted by its status, and nothing is given back or written", async () => {
  const w = preview();
  try {
    await reader(w, "refused.one", ["bill:2026/HB9903"]);
    const before = snapshot(w);
    w.net.resendStatus = 422;
    const r = await ask(w, { body: { kinds: ["daily", "welcome"] } });
    assert.equal(r.status, 200);
    assert.equal(r.answer.ok, false);
    assert.equal(r.answer.sent, 0);
    assert.deepEqual(r.answer.failed, { "resend-422": 2 });
    assert.deepEqual(snapshot(w), before);
    assert.ok(w.logs.lines.includes("follow sender.test-failed.resend-422 2"));
    // A key Resend refuses stops it at the first.
    w.net.resendStatus = 401;
    const stopped = await ask(w);
    assert.deepEqual(stopped.answer.failed, { "resend-401": 1 });
    assert.ok(stopped.answer.notes.includes("stopped early: see failed"));
  } finally { w.close(); }
});

test("test send: a body it cannot read is refused with what it expects, and sends nothing", async () => {
  // What Windows PowerShell 5.1 hands curl.exe for -d '{"kinds":["daily"]}' (its
  // inner quotes stripped), and what PowerShell 7.3 or later hands it for the
  // \"-escaped form 5.1 needs: each is refused, never read as something else.
  for (const raw of ["{kinds:[daily],nights:7}", '{\\"kinds\\":[\\"daily\\"],\\"nights\\":7}',
                     '{"kinds":["monthly"]}', '{"kinds":[]}', '{"kinds":"daily"}', '{"nights":0}',
                     '{"nights":11}', '{"nights":7.5}', '{"nights":"7"}', '{"extra":1}', "[]", "null",
                     "7", '"daily"'])
    assert.equal(testAsk(raw), null, raw);
  assert.equal(testAsk(null), null, "a body over the cap");
  assert.deepEqual(testAsk(""), { kinds: ["daily", "weekly", "welcome"], nights: 7 });
  assert.deepEqual(testAsk("  \n"), { kinds: ["daily", "weekly", "welcome"], nights: 7 });
  assert.deepEqual(testAsk('{"kinds":["daily"],"nights":7}'), { kinds: ["daily"], nights: 7 });
  assert.deepEqual(testAsk('{"kinds":["welcome","daily","daily"]}'), { kinds: ["daily", "welcome"], nights: 7 });
  assert.deepEqual(testAsk('{"nights":10}'), { kinds: ["daily", "weekly", "welcome"], nights: 10 });

  const w = preview();
  try {
    await reader(w, "bad.body", ["bill:2026/HB9903"]);
    for (const body of ["{kinds:[daily],nights:7}", JSON.stringify({ kinds: ["daily"], pad: "x".repeat(300) })]) {
      const r = await ask(w, { body });
      assert.equal(r.status, 400);
      assert.equal(r.answer.why, "invalid");
      assert.match(r.answer.expects, /"kinds"/);
    }
    assert.equal(w.net.outbox.length, 0);
    // No body at all: every kind, over seven nights.
    const r = await ask(w, { body: undefined });
    assert.deepEqual(r.answer.emails, { daily: 1, weekly: 1, welcome: 1 });
  } finally { w.close(); }
});
