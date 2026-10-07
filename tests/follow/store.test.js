// store.js and the schema: the purge, forgetting, links, the count, the
// ceiling -- and that no column can hold anything about a reader but the
// sealed address, its keyed hashes and what they follow, sealed.

import test from "node:test";
import assert from "node:assert/strict";
import { linksFor, lookupHash, mailboxHash, sealAddress, sealFollow }
  from "../../workers/follow/address.js";
import { countConfirmed, dayFull, forget, purge, subscriberFor, underCeiling }
  from "../../workers/follow/store.js";
import { FakeD1 } from "./fake_d1.js";
import { makeKeys } from "./fakes.js";
import { insertSubscriber } from "./rows.js";

const T0 = new Date("2026-10-06T15:00:00Z");
const at = h => new Date(T0.getTime() + h * 3600000);

const subscriber = (db, env, address, follows = ["bill:2026/HB9901"]) =>
  insertSubscriber(db, env, address, { follows, confirmedOn: "2026-10-06" });

async function pending(db, env, address, when) {
  const h = await lookupHash(env, address);
  await db.prepare("INSERT INTO pending (email_hmac, email_enc, mailbox_hmac, follow_enc, " +
    "confirm_token_hash, created_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6)")
    .bind(h, await sealAddress(env, address, h), await mailboxHash(env, address),
          await sealFollow(env, "bill:2026/HB9901", h), crypto.randomUUID(),
          when.toISOString().replace(/\.\d+Z$/, "Z")).run();
}

test("the schema has no column about a reader but the sealed address and its keyed hashes", () => {
  const db = new FakeD1();
  const cols = Object.fromEntries(db.tables().map(t => [t, db.columns(t)]));
  assert.deepEqual(cols, {
    follows: ["subscriber_id", "follow_hmac", "follow_enc", "since"],
    pending: ["id", "email_hmac", "email_enc", "mailbox_hmac", "follow_enc",
              "confirm_token_hash", "created_at"],
    sends: ["date", "frequency", "emails_sent", "items", "failed", "ended"],
    signup_days: ["day", "n"],
    subscribers: ["id", "email_hmac", "email_enc", "frequency", "confirmed_on", "link_gen",
                  "manage_hash", "unsub_hash", "last_sent_on", "sent_date", "sent_built"],
  });
  const all = Object.values(cols).flat().join(" ");
  assert.doesNotMatch(all, /\b(ip|email|address|name|cookie|agent|referr?er|session)\b/i,
    "no column for an IP, a name, a cookie, a browser or a referrer");
  assert.doesNotMatch(all, /\b(kind|ref|follow_kind|follow_ref)\b/,
    "no column that holds what is followed in the clear");
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

test("forgetting an address takes the subscriber, every follow and pending request", async () => {
  const db = new FakeD1(), env = makeKeys();
  const a = await subscriber(db, env, "gone@example.com", ["bill:2026/HB9901", "topic:housing"]);
  const b = await subscriber(db, env, "stays@example.com");
  await pending(db, env, "gone@example.com", T0);
  assert.equal(await forget(db, { id: a.id }), 1);
  assert.deepEqual(db.rows("subscribers").map(r => r.id), [b.id]);
  assert.ok(db.rows("follows").every(r => r.subscriber_id === b.id));
  assert.equal(db.rows("pending").length, 0);
  // and by the hash alone, as a bounce does
  await pending(db, env, "stays@example.com", T0);
  assert.equal(await forget(db, { hmac: b.h }), 1);
  for (const t of db.tables().filter(t => !["sends", "signup_days"].includes(t)))
    assert.equal(db.rows(t).length, 0, t);
});

test("a link finds its reader for as long as it is current, and only for its purpose", async () => {
  const db = new FakeD1(), env = makeKeys();
  const a = await subscriber(db, env, "links@example.com");
  assert.equal((await subscriberFor(db, a.links.manage, "manage"))?.id, a.id);
  assert.equal((await subscriberFor(db, a.links.unsub, "unsubscribe"))?.id, a.id);
  assert.equal(await subscriberFor(db, a.links.manage, "unsubscribe"), null,
    "a manage link is not an unsubscribe link");
  assert.equal(await subscriberFor(db, a.links.unsub, "manage"), null,
    "and an unsubscribe link opens no manage page");
  assert.equal(await subscriberFor(db, a.links.manage, "manage_hash"), null, "no other column");
  assert.equal(await subscriberFor(db, "not a token", "manage"), null);
  // The same reader and generation make the same links; the next generation others.
  assert.deepEqual(await linksFor(env, a.h, 0), a.links);
  const next = await linksFor(env, a.h, 1);
  assert.notEqual(next.manage, a.links.manage);
  assert.notEqual(next.unsub, a.links.unsub);
  assert.ok(!db.everyCell().some(c => c.includes(a.links.manage) || c.includes(a.links.unsub)),
    "the database holds the links' hashes, never the links");
});

test("the count is confirmed subscribers only, as one integer", async () => {
  const db = new FakeD1(), env = makeKeys();
  assert.equal(await countConfirmed(db), 0);
  await subscriber(db, env, "one@example.com");
  await subscriber(db, env, "two@example.com");
  await pending(db, env, "three@example.com", T0);
  assert.equal(await countConfirmed(db), 2);
});

test("the day's ceiling is raised and checked in one statement, and read without raising", async () => {
  const db = new FakeD1();
  assert.equal(await dayFull(db, "2026-10-06", 3), false);
  for (let i = 1; i <= 3; i++) assert.equal(await underCeiling(db, "2026-10-06", 3), i);
  assert.equal(await dayFull(db, "2026-10-06", 3), true);
  assert.equal(await underCeiling(db, "2026-10-06", 3), null);
  assert.equal(await underCeiling(db, "2026-10-07", 3), 1, "a new day starts again");
  assert.deepEqual(db.rows("signup_days").map(r => r.n), [3, 1], "reading raised nothing");
});

test("an address left following nothing is deleted a day or two on", async () => {
  const db = new FakeD1(), env = makeKeys();
  await subscriber(db, env, "orphan@example.com", []);
  await purge(db, at(2));
  assert.equal(db.rows("subscribers").length, 1, "not within the day");
  const r = await purge(db, at(48));
  assert.equal(r.orphans, 1);
  assert.equal(db.rows("subscribers").length, 0);
});
