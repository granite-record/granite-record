// functions/api/follow/confirm.js: a GET changes nothing, a confirmation
// works once and for 48 hours, only from the site's own page, and only for
// what can still be followed; a new subscriber gets daily or weekly as the
// sign-up box was set, and one already subscribed keeps their own.

import test from "node:test";
import assert from "node:assert/strict";
import { hashToken, lookupHash, openFollow } from "../../workers/follow/address.js";
import { run } from "../../workers/follow/sender.js";
import { get, lastMailTo, leaks, makeWorld, postForm, postJson, tokensIn } from "./fakes.js";
import { act, confirmLatest, handlers, join, manageToken, signUp, snapshot, view } from "./flows.js";
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
    // The confirmation and the "You're following" it sent are not updates.
    const to = () => w.net.outbox.filter(m => m.to.includes(a) &&
                                              !/^(Confirm:|You're following)/.test(m.subject));
    w.at("2026-10-08T12:00:00Z");                          // Thursday, 8:00 EDT
    await run(w.env, w.now);
    assert.equal(to().length, 0, "no update on a Thursday");
    w.at("2026-10-10T12:00:00Z");                          // Saturday, 8:00 EDT
    await run(w.env, w.now);
    assert.equal(to().length, 1);
    assert.match(to()[0].subject, /^Your week/);
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

// THE EMAIL A CONFIRMATION SENDS (the person's test of 16 October 2026: the
// confirmation link was spent, no other email had come, and there was no way
// back to the manage page).
const RESEND = "https://api.resend.com/emails";
const welcomes = (w, a) => w.net.outbox.filter(m => m.to.includes(a) && /^You're following /.test(m.subject));

test("a confirmation sends one email, You're following, whose manage link opens the manage page", async () => {
  const w = makeWorld();
  try {
    const a = w.address("comes.back");
    await signUp(w, a, "bill", "2026/HB9903");
    const r = await confirmLatest(w, a);
    assert.equal(r.status, 303);
    assert.ok(!r.beforeAnswer.asked.includes(RESEND), "the confirmation is answered before the email goes");
    const [m, ...more] = welcomes(w, a);
    assert.ok(m, "no email was sent on confirming");
    assert.equal(more.length, 0, "one email a confirmation");
    assert.equal(m.subject, "You're following HB 9903-FN");
    assert.match(m.text, /^You are now following:\n\n  HB 9903-FN — relative to an invented fee, written for these tests\n  https:\/\/graniterecord\.org\/bill\/2026\/hb9903\n/);
    assert.match(m.text, /Updates come daily: about 8:00 a\.m\. New Hampshire time, and only on days when something is new\./);
    assert.match(m.text, /Keep this email until your first update arrives/);
    assert.doesNotMatch(m.text, /You follow \d+ records/, "a new subscriber follows the one record");
    assert.doesNotMatch(m.text + m.html, /this reports what changed/, "it reports nothing, and does not say it does");
    // Its manage link is the one the confirmation landed on, and it opens the page.
    const t = tokensIn(m);
    assert.equal(t.manage, manageToken(r));
    const page = await view(w, t.manage);
    assert.equal(page.status, 200);
    assert.match(page.body, /HB 9903-FN/);
    // The way out every other email carries: the link, and the one-click header.
    assert.ok(t.unsub && t.header);
    assert.equal(m.headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
    assert.match(m.html, /Change what you follow, how often, or pause/);
    assert.match(m.html, /<a href="https:\/\/graniterecord\.org\/bill\/2026\/hb9903"[^>]*>HB 9903-FN<\/a>/);
    assert.ok(w.logs.lines.includes("follow confirm.welcome-sent 1"));
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a subscriber adding a record is told it, with their count, how often as before, and a pause", async () => {
  const w = makeWorld();
  try {
    const a = w.address("adds.a.committee");
    await signUp(w, a, "bill", "2026/HB9901", { frequency: "weekly" });
    const first = await confirmLatest(w, a);
    assert.equal(welcomes(w, a).length, 1);
    await act(w, manageToken(first), "save", { listed: "bill:2026/HB9901", keep: "bill:2026/HB9901",
      frequency: "weekly", pause: "until", pause_until: "2026-10-20" });
    await signUp(w, a, "committee", "H90");                // the box left on Daily
    const r = await confirmLatest(w, a);
    assert.match(r.headers.location, /&n=kept$/);
    const m = welcomes(w, a)[1];
    assert.equal(m.subject, "You're following the House Example Committee");
    assert.match(m.text, /You follow 2 records in all\./);
    assert.match(m.text, /Updates come weekly, as before: on Saturday about 8:00 a\.m\., with the week ahead and then the week's news\. Signing up again does not change how often\./);
    assert.match(m.text, /Your updates are paused through 20 October 2026\./);
    // A subscriber already is not told to wait for a first update.
    assert.doesNotMatch(m.text + m.html, /until your first update arrives/);
    assert.match(m.text, /The link below opens your page for email updates, where you can change what you follow and how often\. Every update carries the same link\./);
    assert.equal(tokensIn(m).manage, manageToken(first), "the same link as every other email");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a pause is told through its last day, and not once that day has gone by", async () => {
  // Nothing clears paused_until when its day passes; the sender and the
  // manage page read a date before today as no pause, and so does this.
  const w = makeWorld();
  try {
    const a = w.address("pause.ends");
    await signUp(w, a, "bill", "2026/HB9901");
    const first = await confirmLatest(w, a);
    await act(w, manageToken(first), "save", { listed: "bill:2026/HB9901", keep: "bill:2026/HB9901",
      frequency: "daily", pause: "until", pause_until: "2026-10-08" });
    assert.equal(w.d1.rows("subscribers")[0].paused_until, "2026-10-08");
    w.at("2026-10-08T15:00:00Z");                          // its last day, in New Hampshire
    await signUp(w, a, "committee", "H90");
    await confirmLatest(w, a);
    assert.match(welcomes(w, a)[1].text, /Your updates are paused through 8 October 2026\./);
    w.at("2026-10-20T15:00:00Z");
    await signUp(w, a, "topic", "housing");
    await confirmLatest(w, a);
    const m = welcomes(w, a)[2];
    assert.ok(m, "the third confirmation sent its email");
    assert.doesNotMatch(m.text + m.html, /paused/i, "a pause that has ended is not told");
    assert.equal(w.d1.rows("subscribers")[0].paused_until, "2026-10-08", "and nothing was written to say so");
  } finally { w.close(); }
});

test("a confirmation that adds nothing sends nothing, and two presses at once send one", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "follows.it.already");
    assert.equal(welcomes(w, s.address).length, 1);
    await signUp(w, s.address);                            // HB 9901 again
    const r = await confirmLatest(w, s.address);
    assert.equal(r.status, 303);
    assert.equal(w.d1.rows("pending").length, 0, "the request is spent all the same");
    assert.equal(welcomes(w, s.address).length, 1, "nothing was added, so nothing was sent");
    // Confirm pressed twice at once: one follow, one email.
    const b = w.address("double.confirm");
    await signUp(w, b, "topic", "housing");
    const t = tokensIn(lastMailTo(w, b)).confirm;
    const both = await Promise.all([1, 2].map(() => w.call(handlers.confirm, postForm("/api/follow/confirm", { t }))));
    assert.ok(both.some(x => x.status === 303));
    assert.equal(welcomes(w, b).length, 1, "one email for one follow");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a confirmation still confirms when its email cannot be sent, and says nothing of it", async () => {
  for (const fault of ["refused", "unconfigured"]) {
    const w = makeWorld();
    try {
      const a = w.address(`unlucky.${fault}`);
      await signUp(w, a, "topic", "elections");
      if (fault === "refused") w.net.resendStatus = 500;
      else w.env.MAIL_FROM = "";                           // sendMail throws ConfigError
      const r = await confirmLatest(w, a);
      assert.equal(r.status, 303, fault);
      assert.match(r.headers.location, /&n=confirmed$/);
      assert.equal(w.d1.rows("subscribers").length, 1);
      assert.equal(w.d1.rows("follows").length, 1);
      assert.equal(welcomes(w, a).length, 0);
      assert.ok(w.logs.lines.includes(fault === "refused" ? "follow confirm.welcome-refused.500"
        : "follow confirm.welcome-error.ConfigError"), w.logs.lines.join(" / "));
      const page = await view(w, manageToken(r));
      assert.equal(page.status, 200, "the manage page opens, and shows no error");
      assert.doesNotMatch(page.body, /went wrong|could not be sent/);
      assert.deepEqual(leaks(w), []);
    } finally { w.close(); }
  }
});

test("a spent link says every email we send has the way back", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "lost.the.page");
    const again = await confirmLatest(w, s.address);
    assert.equal(again.status, 400);
    assert.match(again.body, /expired or been used/);
    // True also for a reader who confirmed before that email was sent at all.
    assert.match(again.body, /A confirmation link works once, for 48 hours\.[^<]*<\/p>\s*<p>If you have already confirmed, the link to your page for email updates, where you can change what you follow, is at the foot of every email we send you about them\. If you cannot find one, your next update will have it\.<\/p>/);
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
    assert.equal(welcomes(w, s.address).length, 1, "the join's own; a follow refused sends nothing");
  } finally { w.close(); }
});
