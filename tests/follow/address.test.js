// address.js: an address is kept only sealed, found only by its keyed hash,
// and a link is a random token kept only as a hash.

import test from "node:test";
import assert from "node:assert/strict";
import { ConfigError, TOKEN, cleanAddress, hashToken, lookupHash, newToken, openAddress,
         sameBytes, sameText, sealAddress } from "../../workers/follow/address.js";
import { makeKeys } from "./fakes.js";

const A = "Reader.One@Example.com";

test("an address is sealed with AES-GCM and opens only with its own key and row", async () => {
  const env = makeKeys();
  const h = await lookupHash(env, A);
  const sealed = await sealAddress(env, A, h);
  assert.match(sealed, /^v1\.[A-Za-z0-9_-]{16}\.[A-Za-z0-9_-]+$/);
  assert.ok(!sealed.toLowerCase().includes("reader"), "the sealed form shows nothing of the address");
  assert.equal(await openAddress(env, sealed, h), A);
  assert.notEqual(await sealAddress(env, A, h), sealed, "a fresh nonce each time");
  // Bound to its row: the same ciphertext under another row's hash will not open.
  const other = await lookupHash(env, "someone.else@example.com");
  await assert.rejects(openAddress(env, sealed, other));
  // And not under another key.
  await assert.rejects(openAddress({ ...env, FOLLOW_ADDRESS_KEY: makeKeys().FOLLOW_ADDRESS_KEY },
    sealed, h));
});

test("the lookup hash is keyed, and one address in any capitals is one hash", async () => {
  const env = makeKeys();
  const h = await lookupHash(env, A);
  assert.match(h, /^[0-9a-f]{64}$/);
  assert.equal(await lookupHash(env, A.toLowerCase()), h);
  assert.equal(await lookupHash(env, A.toUpperCase()), h);
  assert.notEqual(await lookupHash(makeKeys(), A), h, "another key, another hash");
});

test("a missing or short key is a ConfigError that says nothing of the key", async () => {
  const env = makeKeys();
  for (const bad of [{ FOLLOW_LOOKUP_KEY: "" }, { FOLLOW_LOOKUP_KEY: "c2hvcnQ=" },
                     { FOLLOW_LOOKUP_KEY: "not base64 at all!" }]) {
    await assert.rejects(lookupHash({ ...env, ...bad }, A), e => {
      assert.ok(e instanceof ConfigError);
      assert.equal(e.message, "follow configuration");
      return true;
    });
  }
  await assert.rejects(sealAddress({ ...env, FOLLOW_ADDRESS_KEY: undefined }, A, "x"), ConfigError);
});

test("only an ordinary address is accepted, and nothing that could end a header", () => {
  for (const ok of ["reader.one@example.com", "a+b@mail.example.com", "x_y-z@example.co.uk"])
    assert.equal(cleanAddress(ok), ok);
  assert.equal(cleanAddress("  reader.one@example.com \n"), "reader.one@example.com");
  for (const bad of ["", "no-at-sign", "a@b", "two@@example.com", "a@b@example.com",
                     "reader@example.com\r\nBcc: x@example.com", "reader one@example.com",
                     "<reader@example.com>", ".lead@example.com", "dots..twice@example.com",
                     "reader@-example.com", "reader@example", "x".repeat(65) + "@example.com",
                     `reader@${"a".repeat(250)}.com`, 42, null, ["reader@example.com"]])
    assert.equal(cleanAddress(bad), null, String(bad).slice(0, 40));
});

test("a token is 32 random bytes in 43 characters, kept only as its SHA-256", async () => {
  const seen = new Set();
  for (let i = 0; i < 200; i++) {
    const t = newToken();
    assert.match(t, TOKEN);
    assert.ok(!seen.has(t));
    seen.add(t);
  }
  const t = newToken();
  const h = await hashToken(t);
  assert.match(h, /^[0-9a-f]{64}$/);
  assert.equal(await hashToken(t), h);
  assert.ok(!h.includes(t));
});

test("secrets are compared in constant time, whole", () => {
  const a = new Uint8Array([1, 2, 3, 4]);
  assert.equal(sameBytes(a, new Uint8Array([1, 2, 3, 4])), true);
  assert.equal(sameBytes(a, new Uint8Array([1, 2, 3, 5])), false);
  assert.equal(sameBytes(a, new Uint8Array([1, 2, 3])), false);
  assert.equal(sameBytes(a, "1234"), false);
  assert.equal(sameText("abc", "abc"), true);
  assert.equal(sameText("abc", "abd"), false);
});

test("one inbox is one mailbox: +tags, capitals, and Gmail's dots and second name", async () => {
  const { mailboxOf, mailboxHash } = await import("../../workers/follow/address.js");
  assert.equal(mailboxOf("Pat+news@Example.com"), "pat@example.com");
  assert.equal(mailboxOf("pat+1+2@example.com"), "pat@example.com");
  assert.equal(mailboxOf("p.a.t+x@gmail.com"), "pat@gmail.com");
  assert.equal(mailboxOf("P.A.T@googlemail.com"), "pat@gmail.com");
  assert.equal(mailboxOf("p.a.t@example.com"), "p.a.t@example.com", "dots count outside Gmail");
  assert.equal(mailboxOf("+x@example.com"), "+x@example.com", "a local part that is only a tag is kept");
  const env = makeKeys();
  assert.equal(await mailboxHash(env, "pat+1@example.com"), await mailboxHash(env, "PAT+2@example.com"));
  assert.notEqual(await mailboxHash(env, "pat@example.com"), await lookupHash(env, "pat@example.com"),
    "the mailbox hash is not the address's lookup hash");
});

test("what is followed is sealed to its reader, and its hash differs from reader to reader", async () => {
  const { followHash, openFollow, sealFollow } = await import("../../workers/follow/address.js");
  const env = makeKeys();
  const a = await lookupHash(env, "one@example.com"), b = await lookupHash(env, "two@example.com");
  const sealed = await sealFollow(env, "bill:2026/HB9901", a);
  assert.ok(!sealed.includes("HB9901") && !sealed.includes("bill"));
  assert.equal(await openFollow(env, sealed, a), "bill:2026/HB9901");
  await assert.rejects(openFollow(env, sealed, b), "another reader's row will not open it");
  await assert.rejects(openAddress(env, sealed, a), "nor will it open as an address");
  const ha = await followHash(env, a, "bill:2026/HB9901");
  assert.match(ha, /^[0-9a-f]{64}$/);
  assert.equal(await followHash(env, a, "bill:2026/HB9901"), ha);
  assert.notEqual(await followHash(env, b, "bill:2026/HB9901"), ha,
    "two readers of one record show two unrelated hashes");
});

test("a reader's links are the same every time for one generation, and only their hashes are kept", async () => {
  const { linksFor } = await import("../../workers/follow/address.js");
  const env = makeKeys();
  const h = await lookupHash(env, "links@example.com");
  const one = await linksFor(env, h, 0), again = await linksFor(env, h, 0);
  assert.deepEqual(one, again);
  assert.match(one.manage, TOKEN);
  assert.match(one.unsub, TOKEN);
  assert.notEqual(one.manage, one.unsub);
  assert.equal(one.manageHash, await hashToken(one.manage));
  const next = await linksFor(env, h, 1);
  assert.notEqual(next.manage, one.manage);
  assert.notDeepEqual(await linksFor({ ...env, FOLLOW_ADDRESS_KEY: makeKeys().FOLLOW_ADDRESS_KEY }, h, 0), one,
    "under another key, other links");
  await assert.rejects(linksFor({ ...env, FOLLOW_ADDRESS_KEY: "" }, h, 0), ConfigError);
});
