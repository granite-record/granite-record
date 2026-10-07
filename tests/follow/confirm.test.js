// functions/api/follow/confirm.js: a GET changes nothing, a confirmation
// works once and for 48 hours, only from the site's own page, and only for
// what can still be followed.

import test from "node:test";
import assert from "node:assert/strict";
import { get, lastMailTo, leaks, makeWorld, postForm, tokensIn } from "./fakes.js";
import { confirmLatest, handlers, join, manageToken, signUp, snapshot, view } from "./flows.js";

test("opening the link changes nothing, and offers one button", async () => {
  const w = makeWorld();
  try {
    await signUp(w, w.address("just.looking"));
    const before = snapshot(w);
    const r = await w.call(handlers.confirm, get("/api/follow/confirm"));
    assert.equal(r.status, 200);
    assert.match(r.body, /<form method="post" action="\/api\/follow\/confirm">/);
    assert.match(r.body, /<button type="submit">Confirm<\/button>/);
    const nonce = /script-src 'nonce-([A-Za-z0-9_-]+)'/.exec(r.headers["content-security-policy"])[1];
    assert.match(r.body, new RegExp(`<script nonce="${nonce}">`));
    assert.doesNotMatch(r.body, /\.submit\(\)/, "the button is pressed by a person, not the page");
    assert.deepEqual(snapshot(w), before);
  } finally { w.close(); }
});

test("a confirmation makes the subscriber, the follow and a manage link, and spends the request", async () => {
  const w = makeWorld();
  try {
    const a = w.address("confirms.once");
    await signUp(w, a, "topic", "housing");
    const r = await confirmLatest(w, a);
    assert.equal(r.status, 303);
    assert.match(r.headers.location, /^\/api\/follow\/manage#t=[A-Za-z0-9_-]{43}&n=confirmed$/);
    const [s] = w.d1.rows("subscribers");
    assert.equal(s.frequency, "daily");
    assert.equal(s.last_sent_on, "2026-10-06", "nothing is sent the day of confirming");
    assert.equal(s.sent_built, "2026-10-06T15:00:00Z", "nothing published before now is sent");
    assert.deepEqual(w.d1.rows("follows").map(f => [f.kind, f.ref]), [["topic", "housing"]]);
    assert.deepEqual(w.d1.rows("links").map(l => l.purpose), ["manage"]);
    assert.equal(w.d1.rows("pending").length, 0);
    // The shell passes on the "n=confirmed" after "#" as the view's notice.
    const page = await w.call(handlers.manage, postForm("/api/follow/manage",
      { t: manageToken(r), action: "view", notice: "confirmed" }));
    assert.match(page.body, /Confirmed\. You will get email updates/);
    assert.match(page.body, />Housing</);
    // The same link again: spent.
    const again = await confirmLatest(w, a);
    assert.equal(again.status, 400);
    assert.match(again.body, /expired or been used/);
    assert.equal(w.d1.rows("follows").length, 1);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a confirmation link lasts 48 hours", async () => {
  const w = makeWorld();
  try {
    const a = w.address("too.late");
    await signUp(w, a);
    const t = tokensIn(lastMailTo(w, a)).confirm;
    w.later(49);
    const r = await w.call(handlers.confirm, postForm("/api/follow/confirm", { t }));
    assert.equal(r.status, 400);
    assert.equal(w.d1.rows("subscribers").length, 0);
  } finally { w.close(); }
});

test("a confirmation from another site, or from no page at all, changes nothing", async () => {
  const w = makeWorld();
  try {
    const a = w.address("forged.confirm");
    await signUp(w, a);
    const t = tokensIn(lastMailTo(w, a)).confirm;
    for (const opts of [{ origin: "https://evil.example.com" }, { origin: null },
                        { fetchSite: "cross-site" }, { fetchSite: "same-site" },
                        { origin: "https://graniterecord.org.evil.example.com" }]) {
      const r = await w.call(handlers.confirm, postForm("/api/follow/confirm", { t }, opts));
      assert.equal(r.status, 403, JSON.stringify(opts));
    }
    assert.equal(w.d1.rows("subscribers").length, 0);
    assert.equal(w.d1.rows("pending").length, 1, "the request still waits for its owner");
  } finally { w.close(); }
});

test("a subscriber who confirms another record keeps their links and gains one", async () => {
  const w = makeWorld();
  try {
    const first = await join(w, "follows.two");
    await signUp(w, first.address, "member", "990001");
    const r = await confirmLatest(w, first.address);
    const second = manageToken(r);
    assert.ok(second && second !== first.manage);
    assert.equal(w.d1.rows("subscribers").length, 1);
    assert.equal(w.d1.rows("follows").length, 2);
    assert.equal((await view(w, first.manage)).status, 200, "the first link still works");
    assert.match((await view(w, second)).body, /Rep\. Pat Example/);
  } finally { w.close(); }
});

test("a record that ends before the confirmation is not followed", async () => {
  const w = makeWorld();
  try {
    const a = w.address("too.slow");
    await signUp(w, a, "bill", "2026/HB9903");
    const cur = structuredClone(w.net.site.get("/changes/current.json"));
    delete cur.followable["bill:2026/HB9903"];
    w.net.site.set("/changes/current.json", cur);
    const r = await confirmLatest(w, a);
    assert.equal(r.status, 200);
    assert.match(r.body, /can no longer be followed/);
    assert.equal(w.d1.rows("subscribers").length, 0);
    assert.equal(w.d1.rows("pending").length, 0);
  } finally { w.close(); }
});

test("one address follows at most 200 records", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "follows.everything");
    const [row] = w.d1.rows("subscribers");
    for (let i = 1; i < 200; i++)
      await w.d1.prepare("INSERT INTO follows VALUES (?1, 'bill', ?2, 'x')").bind(row.id, `2026/SB${i}`).run();
    await signUp(w, s.address, "committee", "H90");
    const r = await confirmLatest(w, s.address);
    assert.match(r.body, /follow as many records as this allows/);
    assert.equal(w.d1.rows("follows").length, 200);
  } finally { w.close(); }
});
