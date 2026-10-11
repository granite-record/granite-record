// The privacy line, across everything at once: a reader signs up, confirms,
// manages, is sent updates, asks for a new link, and leaves; another bounces;
// the count is read. Then every log line, every answer and every database
// cell is searched for what must not be in it. And the code itself is read
// for the ways a leak would get in.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join as joinPath } from "node:path";
import { createHmac } from "node:crypto";
import { run } from "../../workers/follow/sender.js";
import { everyToken, get, lastMailTo, leaks, makeWorld, postForm, SITE, tokensIn } from "./fakes.js";
import { act, confirmLatest, handlers, join, signUp, view } from "./flows.js";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SOURCES = [
  ...readdirSync(joinPath(ROOT, "workers/follow")).filter(f => f.endsWith(".js"))
    .map(f => `workers/follow/${f}`),
  ...readdirSync(joinPath(ROOT, "functions/api/follow")).filter(f => f.endsWith(".js"))
    .map(f => `functions/api/follow/${f}`),
];
const source = f => readFileSync(joinPath(ROOT, f), "utf8");

test("a whole life of a subscription leaves no address, token or follow list where it must not", async () => {
  const w = makeWorld({ now: "2026-10-04T15:00:00Z" });
  try {
    const a = await join(w, "whole.life");
    await signUp(w, a.address, "topic", "housing");
    await confirmLatest(w, a.address);
    await signUp(w, a.address, "member", "990001");          // left waiting
    await act(w, a.manage, "frequency", { value: "daily" });
    await view(w, a.manage);
    for (const day of ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]) {
      w.at(`${day}T12:00:00Z`);
      await run(w.env, w.now);
    }
    await act(w, a.manage, "newlink");
    const fresh = tokensIn(lastMailTo(w, a.address));
    const b = await join(w, "bounces.away", "committee", "H90");
    const ev = JSON.stringify({ type: "email.bounced", data: { to: [b.address], bounce: { type: "Permanent" } } });
    const ts = String(Math.floor(w.now.getTime() / 1000));
    const sig = createHmac("sha256", Buffer.from(w.keys.RESEND_WEBHOOK_SECRET.slice(6), "base64"))
      .update(`m1.${ts}.${ev}`).digest("base64");
    await w.call(handlers.bounce, new Request(`${SITE}/api/follow/bounce`, { method: "POST", body: ev,
      headers: { "svix-id": "m1", "svix-timestamp": ts, "svix-signature": `v1,${sig}` } }));
    await w.call(handlers.count, get("/api/follow/count"));
    await w.call(handlers.unsubscribe, postForm("/api/follow/unsubscribe", { u: fresh.unsub }));
    await w.call(handlers.count, get("/api/follow/count"));

    // Logs: a code and a count, never an address, a token or a record.
    assert.deepEqual(leaks(w), []);
    assert.ok(w.logs.lines.length > 5, "the run did log, and every line was looked at");

    // Answers: no address in any; no token but where the token's holder is answered.
    const tokens = [...everyToken(w)];
    assert.ok(tokens.length >= 8);
    for (const r of w.responses) {
      const path = new URL(r.url).pathname;
      const holderPage = r.method === "POST" && (path === "/api/follow/manage" || path === "/api/follow/confirm");
      if (holderPage) continue;
      const all = r.body + JSON.stringify(r.headers);
      for (const t of tokens) assert.ok(!all.includes(t), `${r.method} ${path} answered a token`);
    }
    const bodies = w.responses.filter(r => new URL(r.url).pathname === "/api/follow/count").map(r => r.body);
    assert.deepEqual(bodies, ["1\n", "0\n"], "the only figure out is one integer");

    // The database: no address and no token in any cell, of any table.
    for (const cell of w.d1.everyCell()) {
      for (const addr of w.addresses) assert.ok(!cell.toLowerCase().includes(addr.toLowerCase()));
      for (const t of tokens) assert.ok(!cell.includes(t));
    }
    // And everything is gone: both addresses, all follows, all requests.
    for (const t of ["subscribers", "follows", "pending"])
      assert.equal(w.d1.rows(t).length, 0, t);
    assert.ok(w.d1.rows("sends").length > 0, "what is left is counts");
  } finally { w.close(); }
});

test("read without the keys, no cell of the database shows what anyone follows", async () => {
  // As the D1 dashboard, or a session holding the account's wrangler login,
  // would see it: every table, every cell.
  const w = makeWorld();
  try {
    const one = await join(w, "plain.follows", "bill", "2026/HB9901");
    await signUp(w, one.address, "member", "990001");
    await confirmLatest(w, one.address);
    await signUp(w, one.address, "topic", "housing");        // left waiting
    const two = await join(w, "same.record", "bill", "2026/HB9901");
    await signUp(w, two.address, "committee", "H90");          // left waiting
    assert.equal(w.d1.rows("follows").length, 3);
    assert.equal(w.d1.rows("pending").length, 2);
    for (const cell of w.d1.everyCell()) {
      // A sealed value is random base64url, where three letters can turn up
      // by chance; only the longer words are looked for in one.
      const sealed = /^v1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(cell);
      for (const word of ["HB9901", "990001", "housing", "H90", "bill", "member", "topic", "committee"])
        if (!(sealed && word.length < 4)) assert.ok(!cell.includes(word), `a cell shows "${word}"`);
    }
    const hashes = w.d1.rows("follows").map(f => f.follow_hmac);
    assert.equal(new Set(hashes).size, 3, "two readers of HB 9901 show two unrelated hashes");
    // Days, not moments, where only a day is needed.
    for (const f of w.d1.rows("follows")) assert.match(f.since, /^\d{4}-\d{2}-\d{2}$/);
    for (const s of w.d1.rows("subscribers")) assert.match(s.confirmed_on, /^\d{4}-\d{2}-\d{2}$/);
  } finally { w.close(); }
});

test("an address goes only to Resend, as the recipient, and to nobody else", async () => {
  const w = makeWorld({ now: "2026-10-04T15:00:00Z" });
  try {
    const seen = [];
    const inner = w.net.handle.bind(w.net);
    w.net.handle = async req => {
      const body = req.method === "POST" ? await req.clone().text() : "";
      seen.push({ url: req.url, body });
      return inner(req);
    };
    const a = await join(w, "goes.nowhere");
    w.at("2026-10-05T12:00:00Z");
    await run(w.env, w.now);
    for (const s of seen) {
      const has = (s.url + s.body).toLowerCase().includes("goes.nowhere");
      if (s.url === "https://api.resend.com/emails")
        assert.deepEqual(JSON.parse(s.body).to, [a.address]);
      else assert.equal(has, false, s.url);
    }
    assert.ok(seen.some(s => s.url.startsWith("https://challenges.cloudflare.com")));
  } finally { w.close(); }
});

test("the code writes to the console in one place, logs no message, and reads no Resend error", () => {
  for (const f of SOURCES) {
    const text = source(f);
    if (f !== "workers/follow/common.js")
      assert.doesNotMatch(text, /console\./, `${f} writes to the console itself`);
    assert.doesNotMatch(text, /\.message\b/, `${f} reads an error's message`);
    assert.doesNotMatch(text, /\.stack\b/, `${f} reads a stack`);
  }
  const common = source("workers/follow/common.js");
  assert.equal((common.match(/console\.log\(/g) || []).length, 2, "note() is the only writer");
  assert.doesNotMatch(source("workers/follow/mail.js"), /res\.(json|text|arrayBuffer)\(/,
    "a Resend answer's body, which can name the address, is never read");
});

test("the follow code reads no header, and nothing of the request, that could identify a reader", () => {
  const allowed = new Set(["origin", "content-type", "content-length", "sec-fetch-site",
                           "svix-id", "svix-timestamp", "svix-signature"]);
  for (const f of SOURCES) {
    // The code, not its comments, which say "no cookie" and must.
    const code = source(f).replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|\s)\/\/.*$/gm, "$1");
    for (const m of code.matchAll(/headers\.get\(\s*["']([^"']+)["']/gi))
      assert.ok(allowed.has(m[1].toLowerCase()), `${f} reads the ${m[1]} header`);
    for (const leak of ["request.cf", "cookie", "cf-connecting-ip", "x-forwarded-for",
                        "x-real-ip", "user-agent", "referer", "remoteip"])
      assert.ok(!code.toLowerCase().includes(leak), `${f} reads ${leak}`);
  }
});

test("no secret and no address is written in any file of the follow code", () => {
  const files = [...SOURCES, "workers/follow/wrangler.toml", "workers/follow/schema.sql"];
  for (const f of files) {
    const text = source(f);
    assert.doesNotMatch(text, /whsec_[A-Za-z0-9+/=]{10,}/, `${f} carries a webhook secret`);
    assert.doesNotMatch(text, /\bre_[A-Za-z0-9]{16,}/, `${f} carries a Resend key`);
    assert.doesNotMatch(text, /[A-Za-z0-9+/]{43}=/, `${f} carries a 32-byte key`);
    const addresses = text.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g) || [];
    // The site's own sending address (MAIL_FROM, noreply@ on the domain
    // verified with Resend) is no reader's; any other address is.
    assert.deepEqual(addresses.filter(x => !/@(example\.(com|org)|your-verified-domain)$/.test(x)
                                           && x !== "noreply@mail.graniterecord.org"), [],
      `${f} names an address`);
  }
  const toml = source("workers/follow/wrangler.toml");
  assert.doesNotMatch(toml, /^\s*(RESEND_API_KEY|FOLLOW_ADDRESS_KEY|FOLLOW_LOOKUP_KEY|TURNSTILE_SECRET|RESEND_WEBHOOK_SECRET)\s*=/m,
    "a secret is set with wrangler secret put, never in the file");
  assert.match(toml, /database_id = "00000000-0000-0000-0000-000000000000"/);
});
