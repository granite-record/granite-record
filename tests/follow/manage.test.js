// functions/api/follow/manage.js: a private link, not a login, the same in
// every email. It shows what is followed and never the address, changes only
// from the site's own page -- as a real browser posts it -- and "send me a new
// link" kills every link before it, once, however many times it is pressed.

import test from "node:test";
import assert from "node:assert/strict";
import { get, lastMailTo, leaks, makeWorld, postForm, SITE, tokensIn } from "./fakes.js";
import { act, confirmLatest, handlers, join, manageToken, signUp, snapshot, view } from "./flows.js";
import { followKeys } from "./rows.js";

// What a browser sends on a form post from a page whose referrer policy
// withholds its origin: seen in a real browser against these Functions.
const BROWSER_NULL = { origin: "null", fetchSite: "same-origin" };

// Resend answering after a short wait, so that two posts at once overlap.
function slowResend(w, ms = 15) {
  const inner = w.net.handle.bind(w.net);
  w.net.handle = async req => {
    if (new URL(req.url).host === "api.resend.com") await new Promise(r => setTimeout(r, ms));
    return inner(req);
  };
}

test("the link's first answer is a shell that posts the token from after #", async () => {
  const w = makeWorld();
  try {
    const r = await w.call(handlers.manage, get("/api/follow/manage"));
    assert.equal(r.status, 200);
    assert.match(r.body, /location\.hash/);
    assert.match(r.body, /f\.submit\(\)/);
    assert.match(r.body, /name="action" value="view"/);
    assert.equal(r.headers["referrer-policy"], "same-origin",
      "not no-referrer, under which a browser posts this page's forms with Origin null");
    assert.match(r.body, /history\.replaceState\(null,"",location\.pathname\)/,
      "the link's private part is taken out of the address bar and its history");
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
    const id = w.d1.rows("subscribers")[0].id;
    assert.deepEqual(await followKeys(w.d1, w.env), [`${id} bill:2026/HB9901`]);
    // Someone else's record, or a made-up one, changes nothing.
    await act(w, s.manage, "remove", { follow: "bill:2026/HB9903" });
    await act(w, s.manage, "remove", { follow: "<script>" });
    assert.equal(w.d1.rows("follows").length, 1);
    // The last one goes with the address, and the page says so first.
    assert.match((await view(w, s.manage)).body, /Unticking everything deletes your address/);
    r = await act(w, s.manage, "remove", { follow: "bill:2026/HB9901" });
    assert.match(r.body, /Your address has been deleted/);
    assert.equal(w.d1.rows("subscribers").length, 0);
    assert.equal(w.d1.rows("follows").length, 0);
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
    assert.equal(w.d1.rows("subscribers")[0].link_gen, 2);
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
    assert.equal(w.d1.rows("subscribers")[0].link_gen, 0, "the move was undone");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("Send me a new link pressed twice at once sends one email, whose links work", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "double.clicker");
    slowResend(w);
    const before = w.net.outbox.length;
    const answers = await Promise.all([act(w, s.manage, "newlink"), act(w, s.manage, "newlink")]);
    for (const a of answers) assert.match(a.body, /A new link is on its way/);
    const mails = w.net.outbox.slice(before);
    assert.equal(mails.length, 1, "one new-link email, not two");
    const t = tokensIn(mails[0]);
    assert.equal((await view(w, t.manage)).status, 200, "its manage link works");
    assert.equal((await view(w, s.manage)).status, 400, "the link that asked does not");
    const one = await w.call(handlers.unsubscribe, new Request(`${SITE}/api/follow/unsubscribe?u=${t.header}`,
      { method: "POST", body: "List-Unsubscribe=One-Click",
        headers: { "Content-Type": "application/x-www-form-urlencoded" } }));
    assert.equal(one.status, 200);
    assert.equal(w.d1.rows("subscribers").length, 0, "and its one-click unsubscribe deletes the address");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("the page's own buttons work as a browser presses them, with Origin null", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "presses.buttons");
    await signUp(w, s.address, "topic", "housing");
    await confirmLatest(w, s.address);
    assert.equal((await view(w, s.manage, BROWSER_NULL)).status, 200);
    assert.equal((await act(w, s.manage, "frequency", { value: "weekly" }, BROWSER_NULL)).status, 303);
    assert.equal(w.d1.rows("subscribers")[0].frequency, "weekly");
    assert.equal((await act(w, s.manage, "remove", { follow: "topic:housing" }, BROWSER_NULL)).status, 303);
    assert.equal(w.d1.rows("follows").length, 1);
    const r = await act(w, s.manage, "unsubscribe", {}, BROWSER_NULL);
    assert.match(r.body, /Your address has been deleted/);
    assert.equal(w.d1.rows("subscribers").length, 0);
  } finally { w.close(); }
});

test("unsubscribing from the page deletes the address and everything with it", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.leaves");
    await signUp(w, s.address, "member", "990001");       // a request still waiting, too
    const r = await act(w, s.manage, "unsubscribe");
    assert.match(r.body, /Your address has been deleted/);
    for (const t of ["subscribers", "follows", "pending"])
      assert.equal(w.d1.rows(t).length, 0, t);
    assert.equal((await view(w, s.manage)).status, 400);
    // It says what was deleted, from where, and what ages out on its own --
    // not "for good", which D1's backups and the mail service's copies are not.
    assert.match(r.body, /deleted from our database/);
    assert.match(r.body, /backups, kept for at most 30 days/);
    assert.match(r.body, /copy of each email/);
    assert.doesNotMatch(r.body, /for good|Nothing is kept/);
    const page = await view(w, (await join(w, "reads.first")).manage);
    assert.doesNotMatch(page.body, /for good|Nothing is kept/);
  } finally { w.close(); }
});

test("a post from another site, or with no Origin, or a GET with an action, changes nothing", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.targeted");
    const before = snapshot(w);
    for (const opts of [{ origin: "https://evil.example.com" }, { origin: null },
                        { fetchSite: "cross-site" }, { fetchSite: "same-site" },
                        { origin: "null", fetchSite: "cross-site" }, { origin: "null", fetchSite: null },
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

// ---- the one form (11 October 2026) -------------------------------------------------------
const saveForm = (w, t, pairs, opts = {}) =>
  w.call(handlers.manage, postForm("/api/follow/manage", [["t", t], ["action", "save"], ...pairs], opts));

test("one Save: untick, add a bill and a law by typing, a legislator and a topic, with no email", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.saves", "bill", "2026/HB9901");
    await signUp(w, s.address, "committee", "H90");
    await confirmLatest(w, s.address);
    const mails = w.net.outbox.length;
    const page = (await view(w, s.manage)).body;
    assert.match(page, /name="keep" value="topic:housing"/, "every topic tonight has a box");
    assert.match(page, /<option value="member:990001">Rep\. Pat Example/, "legislators can be picked");
    assert.match(page, /Now: In committee/, "a bill says where it stands");
    const r = await saveForm(w, s.manage, [
      ["listed", "bill:2026/HB9901"], ["keep", "bill:2026/HB9901"],
      ["listed", "committee:H90"],                                 // unticked
      ["listed", "topic:housing"], ["keep", "topic:housing"],      // ticked, not followed
      ["listed", "topic:elections"],
      ["add_bill", "hb 9903"], ["add_law", "RSA 91-a"], ["add", "member:990001"],
      ["frequency", "weekly"], ["detail", "milestones"], ["pause", "none"]]);
    assert.equal(r.status, 303);
    assert.match(r.headers.location, /n=saved$/);
    const id = w.d1.rows("subscribers")[0].id;
    assert.deepEqual(await followKeys(w.d1, w.env), [`${id} bill:2026/HB9901`, `${id} bill:2026/HB9903`,
      `${id} law:91-A`, `${id} member:990001`, `${id} topic:housing`]);
    const row = w.d1.rows("subscribers")[0];
    assert.deepEqual([row.frequency, row.detail, row.paused_until], ["weekly", "milestones", null]);
    assert.equal(w.net.outbox.length, mails, "adding from the manager sends no confirmation email");
    assert.equal(w.d1.rows("pending").length, 0);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("what cannot be followed tonight is not added, and the page says so", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.typos");
    const r = await saveForm(w, s.manage, [["listed", "bill:2026/HB9901"], ["keep", "bill:2026/HB9901"],
      ["add_bill", "HB 12345"], ["add", "member:12"], ["add_law", "RSA 999-ZZ"],
      ["keep", "bill:2026/HB9903"]]);                     // a box the page never showed
    assert.match(r.headers.location, /n=notfound$/);
    const id = w.d1.rows("subscribers")[0].id;
    assert.deepEqual(await followKeys(w.d1, w.env), [`${id} bill:2026/HB9901`]);
  } finally { w.close(); }
});

test("a pause through a day, a pause for good, and back again from now", async () => {
  const w = makeWorld();
  try {
    w.now = new Date("2026-10-08T15:00:00Z");
    const s = await join(w, "reader.pauses");
    const base = [["listed", "bill:2026/HB9901"], ["keep", "bill:2026/HB9901"]];
    await saveForm(w, s.manage, [...base, ["pause", "until"], ["pause_until", "2026-10-20"]]);
    assert.equal(w.d1.rows("subscribers")[0].paused_until, "2026-10-20");
    assert.match((await view(w, s.manage)).body, /Paused through 2026-10-20/);
    await saveForm(w, s.manage, [...base, ["pause", "until"], ["pause_until", "2026-10-01"]]);
    assert.equal(w.d1.rows("subscribers")[0].paused_until, "2026-10-20", "a day already past is no pause");
    await saveForm(w, s.manage, [...base, ["pause", "until"], ["pause_until", "2028-01-01"]]);
    assert.equal(w.d1.rows("subscribers")[0].paused_until, "2026-10-20", "nor one more than a year off");
    await saveForm(w, s.manage, [...base, ["pause", "forever"]]);
    assert.equal(w.d1.rows("subscribers")[0].paused_until, "9999-12-31");
    assert.match((await view(w, s.manage)).body, /Paused until you turn updates back on/);
    await saveForm(w, s.manage, [...base, ["pause", "none"]]);
    const row = w.d1.rows("subscribers")[0];
    assert.equal(row.paused_until, null);
    assert.deepEqual([row.sent_date, row.sent_built], ["2026-10-08", "2026-10-08T15:00:00Z"],
      "back from a pause, the reader starts from now");
  } finally { w.close(); }
});

test("unticking everything deletes the address, as removing the last record always has", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.leaves");
    const r = await saveForm(w, s.manage, [["listed", "bill:2026/HB9901"]]);
    assert.match(r.body, /Your address has been deleted/);
    assert.equal(w.d1.rows("subscribers").length, 0);
    assert.equal(w.d1.rows("follows").length, 0);
  } finally { w.close(); }
});

test("the one form is refused from anywhere but the site's own page", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reader.guarded");
    const before = snapshot(w);
    const r = await saveForm(w, s.manage, [["listed", "bill:2026/HB9901"]], { origin: "https://evil.example" });
    assert.equal(r.status, 403);
    assert.deepEqual(snapshot(w), before);
  } finally { w.close(); }
});
