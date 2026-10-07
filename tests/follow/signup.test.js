// functions/api/follow/signup.js: the answer never depends on the address,
// the request is kept sealed, and nothing is followed until confirmed.

import test from "node:test";
import assert from "node:assert/strict";
import { hashToken } from "../../workers/follow/address.js";
import { get, leaks, makeWorld, postJson, SITE, tokensIn } from "./fakes.js";
import { handlers, join, signUp, snapshot } from "./flows.js";

const same = r => JSON.stringify({ status: r.status, headers: r.headers, body: r.body });

test("sign-up says the same thing whether or not the address is already subscribed", async () => {
  const w = makeWorld();
  try {
    const fresh = await signUp(w, w.address("brand.new"));
    const { address: known } = await join(w, "already.here");
    const again = await signUp(w, known);                          // already follows HB 9901
    const more = await signUp(w, known, "bill", "2026/HB9903");     // subscribed, new record
    const busy = w.address("asked.often");
    for (let i = 0; i < 3; i++) await signUp(w, busy);
    const fourth = await signUp(w, busy);                           // three already waiting
    const upper = await signUp(w, known.toUpperCase());              // the same address, shouted
    for (const r of [again, more, fourth, upper]) assert.equal(same(r), same(fresh));
    assert.equal(fresh.status, 202);
    assert.deepEqual(JSON.parse(fresh.body), { ok: true });
    // Every one but the fourth was sent a confirmation, subscriber or not.
    const sent = a => w.net.outbox.filter(m => m.to[0].toLowerCase() === a.toLowerCase()).length;
    assert.equal(sent(known), 4, "the join's own, then again, more and upper");
    assert.equal(sent(busy), 3);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("sign-up never even asks whether the address is subscribed", async () => {
  const w = makeWorld();
  try {
    await signUp(w, w.address("asks.nothing"));
    assert.ok(!w.d1.prepared.some(s => /FROM subscribers|subscribers WHERE/i.test(s)),
      "no statement sign-up made reads the subscribers table");
  } finally { w.close(); }
});

test("a request is kept sealed, with its token's hash and never the token", async () => {
  const w = makeWorld();
  try {
    const a = w.address("sealed.request");
    await signUp(w, a, "committee", "H90");
    const [row] = w.d1.rows("pending");
    const t = tokensIn(w.net.outbox[0]).confirm;
    assert.match(row.email_hmac, /^[0-9a-f]{64}$/);
    assert.match(row.email_enc, /^v1\./);
    assert.equal(row.confirm_token_hash, await hashToken(t));
    assert.deepEqual([row.follow_kind, row.follow_ref], ["committee", "H90"]);
    for (const cell of w.d1.everyCell()) {
      assert.ok(!cell.toLowerCase().includes("sealed.request"), "no address in any cell");
      assert.ok(!cell.includes(t), "no token in any cell");
    }
    assert.equal(w.d1.rows("subscribers").length, 0, "nothing is followed before the confirmation");
    const m = w.net.outbox[0];
    assert.match(m.subject, /^Confirm: email updates on House Example Committee$/);
    assert.match(m.text, /Nothing is sent unless you confirm/);
    assert.match(m.text, /deleted within 48 hours/);
    assert.ok(!("reply_to" in m), "no reply address");
    assert.equal(m.from, "Granite Record <updates@example.com>");
  } finally { w.close(); }
});

test("Turnstile's no is an answer about the form, and keeps and sends nothing", async () => {
  const w = makeWorld();
  try {
    const r = await signUp(w, w.address("robot"), "bill", "2026/HB9901", { turnstile: "fail" });
    assert.equal(r.status, 400);
    assert.deepEqual(JSON.parse(r.body), { ok: false, why: "check" });
    assert.equal(w.net.outbox.length, 0);
    assert.equal(w.d1.rows("pending").length, 0);
  } finally { w.close(); }
});

test("only what can be followed tonight: a moving bill, a sitting-term topic", async () => {
  const w = makeWorld();
  try {
    const a = w.address("follows.wrong");
    const cases = [
      ["bill", "2026/HB9902", "not-followable"],    // concluded: not in current.json
      ["topic", "taxes-state", "not-followable"],   // a topic the sitting term does not carry
      ["topic", "2023-2024/housing", "invalid"],    // an archived term's topic is no ref at all
      ["bill", "2026/hb9901", "invalid"],
      ["member", "Pat Example", "invalid"],
      ["town", "concord", "invalid"],
    ];
    for (const [kind, ref, why] of cases) {
      const r = await signUp(w, a, kind, ref);
      assert.equal(r.status, 400, `${kind} ${ref}`);
      assert.equal(JSON.parse(r.body).why, why, `${kind} ${ref}`);
    }
    for (const [kind, ref] of [["topic", "housing"], ["member", "990001"], ["bill", "2026/HB9903"]])
      assert.equal((await signUp(w, a, kind, ref)).status, 202, `${kind} ${ref}`);
    assert.equal(w.d1.rows("pending").length, 3);
  } finally { w.close(); }
});

test("an address that is not one is refused before anything else is asked", async () => {
  const w = makeWorld();
  try {
    for (const email of ["", "nobody", "a@b", "x@example.com\r\nBcc: y@example.com", null, 7]) {
      const r = await signUp(w, email);
      assert.equal(r.status, 400);
      assert.equal(JSON.parse(r.body).why, "invalid");
    }
    assert.equal(w.net.asked.length, 0, "not even Turnstile was asked");
  } finally { w.close(); }
});

test("the day's ceiling answers 429 for everyone alike", async () => {
  const w = makeWorld();
  try {
    w.env.SIGNUP_DAILY_CEILING = "2";
    assert.equal((await signUp(w, w.address("first"))).status, 202);
    assert.equal((await signUp(w, w.address("second"))).status, 202);
    const r = await signUp(w, w.address("third"));
    assert.equal(r.status, 429);
    assert.deepEqual(JSON.parse(r.body), { ok: false, why: "busy" });
    assert.equal(w.net.outbox.length, 2);
  } finally { w.close(); }
});

test("a refused email or a failing database answers 503, keeps nothing, and logs only a code", async () => {
  const w = makeWorld();
  try {
    const a = w.address("refused.here");
    w.net.resendStatus = 422;          // and Resend's message names the address
    let r = await signUp(w, a);
    assert.equal(r.status, 503);
    assert.equal(w.d1.rows("pending").length, 0, "the request is not kept without its email");
    w.net.resendStatus = 200;
    // A database error whose message carries the address and a token.
    w.d1.failWhen = sql => /INSERT INTO pending/.test(sql)
      ? new Error(`UNIQUE constraint failed: pending.email ${a} token`) : null;
    r = await signUp(w, a);
    assert.equal(r.status, 503);
    assert.deepEqual(JSON.parse(r.body), { ok: false, why: "unavailable" });
    assert.deepEqual(w.logs.lines, ["follow signup.resend-refused.422", "follow signup.error.Error"]);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("only the site's own names, the exact path, a JSON POST, and a bound database", async () => {
  const w = makeWorld();
  try {
    const body = { email: w.address("wrong.door"), kind: "bill", ref: "2026/HB9901", turnstile: "pass" };
    const at = (url, init = {}) => new Request(url, { method: "POST", body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", Origin: SITE, ...(init.headers || {}) }, ...init });
    const { signup } = handlers;
    assert.equal((await w.call(signup, at("https://graniterecord.pages.dev/api/follow/signup"))).status, 404);
    assert.equal((await w.call(signup, at("https://0123abcd.graniterecord.pages.dev/api/follow/signup"))).status, 404);
    assert.equal((await w.call(signup, at(`${SITE}/api/follow/signup/`))).status, 404);
    assert.equal((await w.call(signup, at(`${SITE}/API/follow/signup`))).status, 404);
    assert.equal((await w.call(signup, get("/api/follow/signup"))).status, 405);
    assert.equal((await w.call(signup, postJson("/api/follow/signup", body,
      { origin: "https://elsewhere.example.com" }))).status, 400);
    assert.equal((await w.call(signup, postJson("/api/follow/signup", body, { origin: null }))).status, 400);
    assert.equal((await w.call(signup, new Request(`${SITE}/api/follow/signup`, { method: "POST",
      headers: { "Content-Type": "text/plain", Origin: SITE }, body: JSON.stringify(body) }))).status, 400);
    assert.equal((await w.call(signup, postJson("/api/follow/signup",
      { ...body, padding: "x".repeat(5000) }))).status, 400);
    const closed = { ...w.env, FOLLOW_DB: undefined };
    const r = await signup({ request: postJson("/api/follow/signup", body), env: closed });
    assert.equal(r.status, 404, "with no database bound there is no endpoint");
    assert.equal(w.net.outbox.length, 0);
    assert.deepEqual(snapshot(w).pending, []);
  } finally { w.close(); }
});

test("the honeypot is answered as a person is, and nothing is kept or sent", async () => {
  const w = makeWorld();
  try {
    const r = await signUp(w, w.address("honey.pot"), "bill", "2026/HB9901", { website: "x" });
    assert.equal(r.status, 202);
    assert.equal(w.net.outbox.length, 0);
    assert.equal(w.d1.rows("pending").length, 0);
  } finally { w.close(); }
});

test("without tonight's list of what can be followed, it answers 503 and keeps nothing", async () => {
  const w = makeWorld();
  try {
    w.net.site.delete("/changes/current.json");
    const r = await signUp(w, w.address("no.list"));
    assert.equal(r.status, 503);
    assert.deepEqual(w.logs.lines, ["follow signup.current-unreadable"]);
    assert.equal(w.d1.rows("pending").length, 0);
  } finally { w.close(); }
});
