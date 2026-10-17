// functions/api/follow/confirm.js: a GET changes nothing, a confirmation
// works once and for 48 hours, only from the site's own page, and only for
// what can still be followed; a new subscriber gets daily or weekly as the
// sign-up box was set, and one already subscribed keeps their own.

import test from "node:test";
import assert from "node:assert/strict";
import { hashToken, lookupHash, openFollow } from "../../workers/follow/address.js";
import { run } from "../../workers/follow/sender.js";
import { get, lastMailTo, leaks, makeWorld, postForm, postJson, tokensIn } from "./fakes.js";
import { confirmLatest, handlers, join, manageToken, signUp, snapshot, view } from "./flows.js";
import { insertFollow } from "./rows.js";

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
    assert.equal(s.confirmed_on, "2026-10-06", "a day, not a moment");
    assert.equal(s.last_sent_on, "2026-10-06", "nothing is sent the day of confirming");
    assert.equal(s.sent_built, "2026-10-06T15:00:00Z", "nothing published before now is sent");
    assert.equal(s.manage_hash, await hashToken(manageToken(r)), "the link is kept as its hash");
    const [f] = w.d1.rows("follows");
    assert.equal(f.since, "2026-10-06");
    assert.equal(await openFollow(w.env, f.follow_enc, s.email_hmac), "topic:housing");
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

test("a subscriber who confirms another record is sent to the same manage link", async () => {
  const w = makeWorld();
  try {
    const first = await join(w, "follows.two");
    await signUp(w, first.address, "member", "990001");
    const r = await confirmLatest(w, first.address);
    assert.equal(manageToken(r), first.manage, "one reader, one manage link");
    assert.equal(w.d1.rows("subscribers").length, 1);
    assert.equal(w.d1.rows("follows").length, 2);
    assert.match((await view(w, first.manage)).body, /Rep\. Pat Example/);
  } finally { w.close(); }
});

test("the Confirm button works as a browser presses it: Origin null, from a same-origin page", async () => {
  const w = makeWorld();
  try {
    const a = w.address("real.browser");
    await signUp(w, a);
    const t = tokensIn(lastMailTo(w, a)).confirm;
    // A sandboxed frame on another site also sends "null", and says cross-site.
    const framed = await w.call(handlers.confirm, postForm("/api/follow/confirm", { t },
      { origin: "null", fetchSite: "cross-site" }));
    assert.equal(framed.status, 403);
    const blind = await w.call(handlers.confirm, postForm("/api/follow/confirm", { t },
      { origin: "null", fetchSite: null }));
    assert.equal(blind.status, 403, "null with no Sec-Fetch-Site is not taken on trust");
    const r = await w.call(handlers.confirm, postForm("/api/follow/confirm", { t },
      { origin: "null", fetchSite: "same-origin" }));
    assert.equal(r.status, 303);
    assert.equal(w.d1.rows("subscribers").length, 1);
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

// THE BOX'S DAILY OR WEEKLY (16 October 2026), carried from the sign-up to
// the subscriber, and on to what the sender does with it.
test("a weekly sign-up is confirmed as weekly, and its first email is Saturday's week", async () => {
  const w = makeWorld();                                   // Tuesday 6 October
  try {
    const a = w.address("weekly.reader");
    await signUp(w, a, "bill", "2026/HB9903", { frequency: "weekly" });
    assert.deepEqual(w.d1.rows("pending").map(p => p.frequency), ["weekly"]);
    const r = await confirmLatest(w, a);
    assert.equal(r.status, 303);
    const [s] = w.d1.rows("subscribers");
    assert.equal(s.frequency, "weekly");
    assert.equal(w.d1.rows("pending").length, 0);
    // The manage page it lands on has Weekly chosen.
    const page = await view(w, manageToken(r));
    assert.match(page.body, /<input type="radio" name="frequency" value="weekly" checked>/);
    assert.doesNotMatch(page.body, /name="frequency" value="daily" checked/);
    // Sent as a weekly reader is: nothing on a weekday, the week on Saturday.
    const to = () => w.net.outbox.filter(m => m.to.includes(a));
    w.at("2026-10-08T12:00:00Z");                          // Thursday, 8:00 EDT
    await run(w.env, w.now);
    assert.equal(to().length, 1, "only the confirmation on a Thursday");
    w.at("2026-10-10T12:00:00Z");                          // Saturday, 8:00 EDT
    await run(w.env, w.now);
    assert.equal(to().length, 2);
    assert.match(to()[1].subject, /^Your week/);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a sign-up that names no frequency is confirmed as daily", async () => {
  const w = makeWorld();
  try {
    const a = w.address("box.from.before");
    // As a page loaded before the box had the choice sends it: no frequency.
    await w.call(handlers.signup, postJson("/api/follow/signup",
      { email: a, kind: "bill", ref: "2026/HB9903", turnstile: "pass", website: "" }));
    assert.deepEqual(w.d1.rows("pending").map(p => p.frequency), ["daily"]);
    const r = await confirmLatest(w, a);
    assert.equal(r.status, 303);
    assert.deepEqual(w.d1.rows("subscribers").map(s => s.frequency), ["daily"]);
    assert.match((await view(w, manageToken(r))).body,
      /<input type="radio" name="frequency" value="daily" checked>/);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a reader already subscribed keeps how often they chose, and is told so when the box asked otherwise", async () => {
  // The box opens on Daily, so a weekly reader following one more record
  // without touching it must not be turned daily; nor a daily reader weekly
  // by a second sign-up. Where the box asked for the other one, the manage
  // page says how often they still come instead of a plain "Confirmed.", and
  // its How often is where it changes. A second sign-up that asked for what
  // is kept is confirmed plainly.
  const w = makeWorld();
  try {
    const weekly = w.address("chose.weekly"), daily = w.address("chose.daily");
    await signUp(w, weekly, "bill", "2026/HB9901", { frequency: "weekly" });
    await confirmLatest(w, weekly);
    await signUp(w, daily, "bill", "2026/HB9901", { frequency: "daily" });
    await confirmLatest(w, daily);
    await signUp(w, weekly, "topic", "housing", { frequency: "daily" });
    await signUp(w, daily, "committee", "H90", { frequency: "weekly" });
    const rw = await confirmLatest(w, weekly), rd = await confirmLatest(w, daily);
    for (const r of [rw, rd]) {
      assert.equal(r.status, 303);
      assert.match(r.headers.location, /^\/api\/follow\/manage#t=[A-Za-z0-9_-]{43}&n=kept$/);
    }
    const by = new Map(w.d1.rows("subscribers").map(s => [s.email_hmac, s.frequency]));
    assert.equal(by.get(await lookupHash(w.env, weekly)), "weekly");
    assert.equal(by.get(await lookupHash(w.env, daily)), "daily");
    assert.equal(w.d1.rows("follows").length, 4, "the second records were followed all the same");
    assert.equal(w.d1.rows("pending").length, 0);
    // The shell passes on the "n=kept" after "#" as the view's notice.
    const seen = async r => (await w.call(handlers.manage, postForm("/api/follow/manage",
      { t: manageToken(r), action: "view", notice: "kept" }))).body;
    const pw = await seen(rw), pd = await seen(rd);
    assert.match(pw, /<p class="note">Confirmed\. You will get email updates on what is listed below, weekly as before: signing up again does not change how often\. To change it, choose under How often and save\.<\/p>/);
    assert.match(pw, /<input type="radio" name="frequency" value="weekly" checked>/);
    assert.match(pd, /listed below, daily as before: signing up again does not change how often/);
    assert.match(pd, /<input type="radio" name="frequency" value="daily" checked>/);
    // Asked for what is kept: nothing to tell.
    await signUp(w, weekly, "bill", "2026/HB9903", { frequency: "weekly" });
    assert.match((await confirmLatest(w, weekly)).headers.location, /&n=confirmed$/);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("the manage page shows only its own notices, whatever notice it is handed", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "types.a.notice");
    for (const notice of ["constructor", "toString", "__proto__", "hasOwnProperty", "nonsense"]) {
      const page = await w.call(handlers.manage, postForm("/api/follow/manage",
        { t: s.manage, action: "view", notice }));
      assert.equal(page.status, 200, notice);
      assert.doesNotMatch(page.body, /<p class="note">/, notice);
    }
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("one address follows at most 200 records", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "follows.everything");
    const [row] = w.d1.rows("subscribers");
    for (let i = 1; i < 200; i++)
      await insertFollow(w.d1, w.env, row.id, row.email_hmac, `bill:2026/SB${i}`);
    await signUp(w, s.address, "committee", "H90");
    const r = await confirmLatest(w, s.address);
    assert.match(r.body, /follow as many records as this allows/);
    assert.equal(w.d1.rows("follows").length, 200);
  } finally { w.close(); }
});
