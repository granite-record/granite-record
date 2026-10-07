// store.js and the schema: the purge, forgetting, links, the count, the
// ceiling -- and that no column can hold anything about a reader but the
// sealed address and its keyed hash.

import test from "node:test";
import assert from "node:assert/strict";
import { lookupHash, sealAddress } from "../../workers/follow/address.js";
import { countConfirmed, forget, issueLink, purge, subscriberFor, underCeiling }
  from "../../workers/follow/store.js";
import { FakeD1 } from "./fake_d1.js";
import { makeKeys } from "./fakes.js";

const T0 = new Date("2026-10-06T15:00:00Z");
const at = h => new Date(T0.getTime() + h * 3600000);

async function subscriber(db, env, address, follows = [["bill", "2026/HB9901"]]) {
  const h = await lookupHash(env, address);
  const id = await db.prepare("INSERT INTO subscribers (email_hmac, email_enc, frequency, " +
    "confirmed_at) VALUES (?1, ?2, 'daily', ?3) RETURNING id")
    .bind(h, await sealAddress(env, address, h), T0.toISOString()).first("id");
  for (const [k, r] of follows)
    await db.prepare("INSERT INTO follows VALUES (?1, ?2, ?3, ?4)").bind(id, k, r, "x").run();
  return { id, h };
}

async function pending(db, env, address, when) {
  const h = await lookupHash(env, address);
  await db.prepare("INSERT INTO pending (email_hmac, email_enc, follow_kind, follow_ref, " +
    "confirm_token_hash, created_at) VALUES (?1, ?2, 'bill', '2026/HB9901', ?3, ?4)")
    .bind(h, await sealAddress(env, address, h), crypto.randomUUID(),
          when.toISOString().replace(/\.\d+Z$/, "Z")).run();
}

test("the schema has no column about a reader but the sealed address and its keyed hash", () => {
  const db = new FakeD1();
  const cols = Object.fromEntries(db.tables().map(t => [t, db.columns(t)]));
  assert.deepEqual(cols, {
    follows: ["subscriber_id", "kind", "ref", "since"],
    links: ["token_hash", "subscriber_id", "purpose", "created_at"],
    pending: ["id", "email_hmac", "email_enc", "follow_kind", "follow_ref",
              "confirm_token_hash", "created_at"],
    sends: ["date", "frequency", "emails_sent", "items", "failed", "ended"],
    signup_days: ["day", "n"],
    subscribers: ["id", "email_hmac", "email_enc", "frequency", "confirmed_at",
                  "last_sent_on", "sent_date", "sent_built"],
  });
  const all = Object.values(cols).flat().join(" ");
  assert.doesNotMatch(all, /\b(ip|email|address|name|cookie|agent|referr?er|session)\b/i,
    "no column for an IP, a name, a cookie, a browser or a referrer");
});

test("an unconfirmed request is kept 48 hours and purged after", async () => {
  const db = new FakeD1(), env = makeKeys();
  await pending(db, env, "waiting@example.com", T0);
  await purge(db, at(47));
  assert.equal(db.rows("pending").length, 1, "still there at 47 hours");
  await purge(db, at(48));
  assert.equal(db.rows("pending").length, 1, "still there at exactly 48 hours");
  const r = await purge(db, at(49));
  assert.equal(r.pending, 1);
  assert.equal(db.rows("pending").length, 0, "gone at 49 hours");
});

test("forgetting an address takes the subscriber, every follow, link and pending request", async () => {
  const db = new FakeD1(), env = makeKeys();
  const a = await subscriber(db, env, "gone@example.com", [["bill", "2026/HB9901"], ["topic", "housing"]]);
  const b = await subscriber(db, env, "stays@example.com");
  await issueLink(db, a.id, "manage", T0);
  await issueLink(db, a.id, "unsubscribe", T0);
  await issueLink(db, b.id, "manage", T0);
  await pending(db, env, "gone@example.com", T0);
  assert.equal(await forget(db, { id: a.id }), 1);
  assert.deepEqual(db.rows("subscribers").map(r => r.id), [b.id]);
  assert.ok(db.rows("follows").every(r => r.subscriber_id === b.id));
  assert.ok(db.rows("links").every(r => r.subscriber_id === b.id));
  assert.equal(db.rows("pending").length, 0);
  // and by the hash alone, as a bounce does
  await pending(db, env, "stays@example.com", T0);
  assert.equal(await forget(db, { hmac: b.h }), 1);
  for (const t of db.tables().filter(t => !["sends", "signup_days"].includes(t)))
    assert.equal(db.rows(t).length, 0, t);
});

test("a link is good for its age, and an address's newest link always is", async () => {
  const db = new FakeD1(), env = makeKeys();
  const a = await subscriber(db, env, "links@example.com");
  const old = await issueLink(db, a.id, "manage", T0);
  const day = 24;
  assert.equal((await subscriberFor(db, old, "manage", at(59 * day)))?.id, a.id);
  assert.equal((await subscriberFor(db, old, "manage", at(400 * day)))?.id, a.id,
    "the newest manage link works whatever its age");
  const newer = await issueLink(db, a.id, "manage", at(10 * day));
  assert.equal(await subscriberFor(db, old, "manage", at(61 * day)), null, "past 60 days, and not the newest");
  assert.equal((await subscriberFor(db, newer, "manage", at(61 * day)))?.id, a.id);
  assert.equal(await subscriberFor(db, newer, "unsubscribe", at(11 * day)), null,
    "a manage link is not an unsubscribe link");
  await purge(db, at(61 * day));
  assert.equal(db.rows("links").length, 1, "the purge takes the expired one and keeps the newest");
  assert.equal(await subscriberFor(db, "not a token", "manage", T0), null);
});

test("the count is confirmed subscribers only, as one integer", async () => {
  const db = new FakeD1(), env = makeKeys();
  assert.equal(await countConfirmed(db), 0);
  await subscriber(db, env, "one@example.com");
  await subscriber(db, env, "two@example.com");
  await pending(db, env, "three@example.com", T0);
  assert.equal(await countConfirmed(db), 2);
});

test("the day's ceiling is raised and checked in one statement", async () => {
  const db = new FakeD1();
  for (let i = 1; i <= 3; i++) assert.equal(await underCeiling(db, "2026-10-06", 3), i);
  assert.equal(await underCeiling(db, "2026-10-06", 3), null);
  assert.equal(await underCeiling(db, "2026-10-07", 3), 1, "a new day starts again");
});

test("an address left following nothing is deleted a day on", async () => {
  const db = new FakeD1(), env = makeKeys();
  const a = await subscriber(db, env, "orphan@example.com", []);
  await issueLink(db, a.id, "manage", T0);
  await purge(db, at(2));
  assert.equal(db.rows("subscribers").length, 1, "not within the day");
  const r = await purge(db, at(25));
  assert.equal(r.orphans, 1);
  assert.equal(db.rows("subscribers").length, 0);
  assert.equal(db.rows("links").length, 0);
});
