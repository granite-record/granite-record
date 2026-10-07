// functions/api/follow/manage.js: a private link, not a login. It shows what
// is followed and never the address, changes only from the site's own page,
// and "send me a new link" kills every link before it.

import test from "node:test";
import assert from "node:assert/strict";
import { get, lastMailTo, leaks, makeWorld, postForm, SITE, tokensIn } from "./fakes.js";
import { act, confirmLatest, handlers, join, manageToken, signUp, snapshot, view } from "./flows.js";

test("the link's first answer is a shell that posts the token from after #", async () => {
  const w = makeWorld();
  try {
    const r = await w.call(handlers.manage, get("/api/follow/manage"));
    assert.equal(r.status, 200);
    assert.match(r.body, /location\.hash/);
    assert.match(r.body, /f\.submit\(\)/);
    assert.match(r.body, /name="action" value="view"/);
    assert.equal(r.headers["referrer-policy"], "no-referrer");
    assert.equal(r.headers["cache-control"], "no-store");
    assert.match(r.headers["content-security-policy"], /frame-ancestors 'none'/);
  } finally { w.close(); }
});

test("the page shows what is followed and how often, and never the address", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.manages", "bill", "2026/HB9901");
    await signUp(w, s.address, "committee", "H90");
    await confirmLatest(w, s.address);
    const r = await view(w, s.manage);
    assert.equal(r.status, 200);
    assert.match(r.body, /<a href="https:\/\/graniterecord\.org\/bill\/2026\/hb9901">HB 9901<\/a>/);
    assert.match(r.body, /House Example Committee/);
    assert.match(r.body, /value="daily" checked/);
    assert.match(r.body, /rebuilt once a night/);
    assert.ok(!r.body.toLowerCase().includes("reader.manages"), "no address on the page");
    assert.doesNotMatch(r.body, /<script/, "the page itself runs no script");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("how often, and removing a record", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.changes");
    await signUp(w, s.address, "topic", "housing");
    await confirmLatest(w, s.address);
    let r = await act(w, s.manage, "frequency", { value: "weekly" });
    assert.equal(r.status, 303);
    assert.equal(r.headers.location, `/api/follow/manage#t=${s.manage}&n=saved`);
    assert.equal(w.d1.rows("subscribers")[0].frequency, "weekly");
    await act(w, s.manage, "frequency", { value: "hourly" });
    assert.equal(w.d1.rows("subscribers")[0].frequency, "weekly", "only daily or weekly");
    r = await act(w, s.manage, "remove", { follow: "topic:housing" });
    assert.match(r.headers.location, /n=removed$/);
    assert.deepEqual(w.d1.rows("follows").map(f => f.ref), ["2026/HB9901"]);
    // Someone else's record, or a made-up one, changes nothing.
    await act(w, s.manage, "remove", { follow: "bill:2026/HB9903" });
    await act(w, s.manage, "remove", { follow: "<script>" });
    assert.equal(w.d1.rows("follows").length, 1);
    // The last one goes with the address, and the page says so first.
    assert.match((await view(w, s.manage)).body, /Remove, and delete my address/);
    r = await act(w, s.manage, "remove", { follow: "bill:2026/HB9901" });
    assert.match(r.body, /Your address has been deleted/);
    assert.equal(w.d1.rows("subscribers").length, 0);
    assert.equal(w.d1.rows("links").length, 0);
  } finally { w.close(); }
});

test("a second new link kills the first, and every link before it", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.relinks");
    const r1 = await act(w, s.manage, "newlink");
    assert.match(r1.body, /A new link is on its way/);
    const m1 = lastMailTo(w, s.address);
    assert.equal(m1.subject, "Your new link for Granite Record email updates");
    const first = tokensIn(m1);
    assert.ok(first.manage && first.unsub && first.header);
    assert.ok(!r1.body.includes(first.manage), "the new link is emailed, not shown");
    assert.equal((await view(w, s.manage)).status, 400, "the link it replaced is dead");
    assert.equal((await view(w, first.manage)).status, 200);
    await act(w, first.manage, "newlink");
    const second = tokensIn(lastMailTo(w, s.address));
    assert.notEqual(second.manage, first.manage);
    assert.equal((await view(w, first.manage)).status, 400, "the first new link is dead");
    assert.equal((await view(w, s.manage)).status, 400);
    assert.equal((await view(w, second.manage)).status, 200);
    // The first new link's unsubscribe link died with it.
    const u = await w.call(handlers.unsubscribe, postForm("/api/follow/unsubscribe", { u: first.unsub }));
    assert.match(u.body, /no longer current/);
    assert.equal(w.d1.rows("subscribers").length, 1);
    assert.deepEqual(w.d1.rows("links").map(l => l.purpose).sort(), ["manage", "unsubscribe"]);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a new link that cannot be sent changes nothing", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.unlucky");
    w.net.resendStatus = 500;
    const r = await act(w, s.manage, "newlink");
    assert.equal(r.status, 503);
    assert.match(r.body, /this link still works/);
    assert.equal((await view(w, s.manage)).status, 200);
    assert.deepEqual(w.d1.rows("links").map(l => l.purpose), ["manage"]);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("unsubscribing from the page deletes the address and everything with it", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.leaves");
    await signUp(w, s.address, "member", "990001");       // a request still waiting, too
    const r = await act(w, s.manage, "unsubscribe");
    assert.match(r.body, /Your address has been deleted/);
    for (const t of ["subscribers", "follows", "links", "pending"])
      assert.equal(w.d1.rows(t).length, 0, t);
    assert.equal((await view(w, s.manage)).status, 400);
  } finally { w.close(); }
});

test("a post from another site, or with no Origin, or a GET with an action, changes nothing", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.targeted");
    const before = snapshot(w);
    for (const opts of [{ origin: "https://evil.example.com" }, { origin: null },
                        { fetchSite: "cross-site" }, { fetchSite: "same-site" },
                        { origin: "http://graniterecord.org.evil.example.com" }])
      for (const [action, extra] of [["frequency", { value: "weekly" }], ["unsubscribe", {}],
                                     ["newlink", {}], ["remove", { follow: "bill:2026/HB9901" }]]) {
        const r = await act(w, s.manage, action, extra, opts);
        assert.equal(r.status, 403, `${action} ${JSON.stringify(opts)}`);
      }
    const g = await w.call(handlers.manage,
      get("/api/follow/manage", `?t=${s.manage}&action=unsubscribe`));
    assert.equal(g.status, 200);
    // A form post of another content type is not a form.
    const j = await w.call(handlers.manage, new Request(`${SITE}/api/follow/manage`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: SITE },
      body: JSON.stringify({ t: s.manage, action: "unsubscribe" }) }));
    assert.equal(j.status, 400);
    assert.deepEqual(snapshot(w), before);
    assert.equal(w.net.outbox.length, 1, "no new-link email went out");
  } finally { w.close(); }
});

test("a link that is not current says so, and nothing else", async () => {
  const w = makeWorld();
  try {
    await join(w, "reader.real");
    for (const t of ["", "short", "A".repeat(43), "<script>alert(1)</script>"]) {
      const r = await view(w, t);
      assert.equal(r.status, 400);
      assert.match(r.body, /no longer current/);
      assert.doesNotMatch(r.body, /<script>alert/);
    }
  } finally { w.close(); }
});
