// functions/api/follow/bounce.js: a signed bounce or complaint deletes the
// address with nobody seeing it; anything unsigned changes nothing.

import test from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { leaks, makeWorld, SITE } from "./fakes.js";
import { handlers, join, snapshot } from "./flows.js";

// Signed as Svix signs: HMAC-SHA-256 of "<id>.<timestamp>.<body>" under the
// secret's bytes, base64, after "v1,".
function signed(w, event, { secret = w.keys.RESEND_WEBHOOK_SECRET, ts, id = "msg_test_1",
                            body, headers = {} } = {}) {
  const text = body ?? JSON.stringify(event);
  const stamp = String(ts ?? Math.floor(w.now.getTime() / 1000));
  const key = Buffer.from(secret.replace(/^whsec_/, ""), "base64");
  const sig = createHmac("sha256", key).update(`${id}.${stamp}.${JSON.stringify(event)}`).digest("base64");
  return new Request(`${SITE}/api/follow/bounce`, { method: "POST", body: text,
    headers: { "Content-Type": "application/json", "svix-id": id, "svix-timestamp": stamp,
               "svix-signature": `v1,${sig}`, ...headers } });
}

const event = (type, to, bounce) => ({ type, created_at: "2026-10-06T15:00:00Z",
  data: { email_id: "e-1", from: "updates@example.com", to: [to], subject: "x",
          ...(bounce ? { bounce } : {}) } });

test("a signed bounce deletes the address and everything it follows", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "bounces.hard");
    const other = await join(w, "stays.put");
    const r = await w.call(handlers.bounce, signed(w, event("email.bounced", s.address,
      { type: "Permanent", subType: "General", message: `${s.address} does not exist` })));
    assert.equal(r.status, 204);
    assert.equal(r.body, "");
    assert.equal(w.d1.rows("subscribers").length, 1);
    assert.equal((await w.call(handlers.count, new Request(`${SITE}/api/follow/count`))).body, "1\n");
    assert.ok(w.logs.lines.includes("follow bounce.forgot 1"));
    assert.ok(other.manage);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a signed complaint deletes the address; a full mailbox does not", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "complains");
    const t = await join(w, "mailbox.full");
    await w.call(handlers.bounce, signed(w, event("email.bounced", t.address,
      { type: "Transient", subType: "MailboxFull" })));
    assert.equal(w.d1.rows("subscribers").length, 2);
    await w.call(handlers.bounce, signed(w, event("email.delivered", t.address)));
    assert.equal(w.d1.rows("subscribers").length, 2, "other events change nothing");
    await w.call(handlers.bounce, signed(w, event("email.complained", s.address.toUpperCase())));
    assert.equal(w.d1.rows("subscribers").length, 1);
    assert.ok(w.logs.lines.includes("follow complaint.forgot 1"));
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a bounce with a bad signature changes nothing", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "not.really.bounced");
    const ev = event("email.bounced", s.address, { type: "Permanent" });
    const before = snapshot(w);
    const attempts = [
      signed(w, ev, { secret: "whsec_" + Buffer.from("not the secret at all!").toString("base64") }),
      signed(w, ev, { ts: Math.floor(w.now.getTime() / 1000) - 301 }),          // too old
      signed(w, ev, { ts: Math.floor(w.now.getTime() / 1000) + 301 }),          // from the future
      signed(w, ev, { body: JSON.stringify({ ...ev, type: "email.complained" }) }), // altered
      signed(w, ev, { headers: { "svix-signature": "v1,AAAA" } }),
      signed(w, ev, { headers: { "svix-signature": "" } }),
      signed(w, ev, { headers: { "svix-id": "" } }),
      signed(w, ev, { headers: { "svix-timestamp": "yesterday" } }),
    ];
    for (const req of attempts) {
      const r = await w.call(handlers.bounce, req);
      assert.equal(r.status, 401);
      assert.equal(r.body, "");
    }
    assert.deepEqual(snapshot(w), before);
    assert.equal(w.logs.lines.filter(l => l === "follow bounce.unsigned").length, attempts.length);
    // The real signature, on the same event, still works.
    const r = await w.call(handlers.bounce, signed(w, ev));
    assert.equal(r.status, 204);
    assert.equal(w.d1.rows("subscribers").length, 0);
  } finally { w.close(); }
});

test("with no webhook secret set, no event is believed", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "no.secret.here");
    const req = signed(w, event("email.bounced", s.address, { type: "Permanent" }));
    delete w.env.RESEND_WEBHOOK_SECRET;
    const r = await w.call(handlers.bounce, req);
    assert.equal(r.status, 503);
    assert.equal(w.d1.rows("subscribers").length, 1);
    assert.ok(w.logs.lines.includes("follow bounce.error.ConfigError"));
  } finally { w.close(); }
});
