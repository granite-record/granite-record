// functions/api/follow/manage.js: a private link, not a login, the same in
// every email. It shows what is followed and never the address, changes only
// from the site's own page -- as a real browser posts it -- and "send me a new
// link" kills every link before it, once, however many times it is pressed.

import test from "node:test";
import assert from "node:assert/strict";
import { get, lastMailTo, leaks, makeWorld, postForm, SITE, tokensIn } from "./fakes.js";
import { act, confirmLatest, handlers, join, manageToken, signUp, snapshot, view } from "./flows.js";
import { followKeys } from "./rows.js";
import { PICK_SCRIPT } from "../../workers/follow/page.js";

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
    // In a reader's words (the language sweep, 17 October 2026): not the
    // build's "rebuilt once a night", not "tonight", not "tick".
    assert.match(r.body, /updates overnight, so even the daily email covers/);
    assert.match(r.body, /This term's bills on a subject\. Check one to follow it\./);
    assert.doesNotMatch(r.body.replace(/<style>[\s\S]*?<\/style>|<script[\s\S]*?<\/script>/g, ""),
      /rebuilt|tonight|\b[Uu]n?tick|records/);
    assert.ok(!r.body.toLowerCase().includes("reader.manages"), "no address on the page");
    // One script, under the answer's nonce: the find box of the lists to add
    // from (page.js PICK_SCRIPT), which reads nothing of the link.
    const scripts = r.body.match(/<script[^>]*>[\s\S]*?<\/script>/g) || [];
    assert.equal(scripts.length, 1, "the page runs one script, its lists' find box");
    assert.ok(scripts[0].includes(PICK_SCRIPT));
    assert.doesNotMatch(scripts[0], /location|history|submit\(|fetch|cookie|storage/i,
      "the find box reads no link, and sends and keeps nothing");
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
    assert.match((await view(w, s.manage)).body, /Unchecking everything deletes your address/);
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
    const before = snapshot(w), mails = w.net.outbox.length;
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
    assert.equal(w.net.outbox.length, mails, "no new-link email went out");
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
    assert.match(page, /<input type="checkbox" name="add" value="member:990001"><span>Rep\. Pat Example/,
      "legislators can be ticked");
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
    // A date as the site writes one, never the ISO form (17 October 2026).
    assert.match((await view(w, s.manage)).body, /Paused through October 20, 2026\./);
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

// ---- the lists to add from (the person's test of 16 October 2026) ---------------------
// "The legislators were not searchable and the drop-down sorted them by first
// name instead of last name. You could only select one committee and
// legislator at a time until you save." Both chambers sitting, beside the
// fixture's own Rep. Pat Example and House Example Committee: a surname of
// three words the roster sorts under V, which the label's last word would put
// under B; an accent; and a committee of each chamber.
const SITTING = {
  "member:990002": { label: "Sen. Ann Zed (D - SD5)", sort: "zed, ann", chamber: "Senate" },
  "member:990003": { label: "Rep. Zoë Abbott (R - Hills 3)", sort: "abbott, zoë", chamber: "House" },
  "member:990004": { label: "Rep. Al Young (D - Coos 1)", sort: "young, al", chamber: "House" },
  "member:990005": { label: "Sen. Bo Adams (R - SD2)", sort: "adams, bo", chamber: "Senate" },
  "member:990006": { label: "Rep. Mary Van Der Berg (D - Straf 2)", sort: "van der berg, mary",
                     chamber: "House" },
  "committee:S90": { label: "Senate Example Committee", chamber: "Senate" },
  "committee:H91": { label: "House Another Committee", chamber: "House" },
};
const sitting = (w, more = SITTING) =>
  Object.assign(w.net.site.get("/changes/current.json").followable, structuredClone(more));

// One list to add from as the page draws it: its chambers in order, and the
// records each offers, in order.
function lists(html) {
  return (html.match(/<details class="pick" data-pick>[\s\S]*?<\/details>/g) || []).map(block => ({
    block,
    summary: /<summary>([^<]*)/.exec(block)[1].trim(),
    sets: (block.match(/<fieldset>[\s\S]*?<\/fieldset>/g) || []).map(f => ({
      chamber: (/<legend>([^<]*)<\/legend>/.exec(f) || [])[1] || "",
      keys: [...f.matchAll(/name="add" value="([^"]+)"/g)].map(m => m[1]),
    })),
  }));
}

test("the lists to add from: the House and the Senate apart, by last name, without what is followed", async () => {
  const w = makeWorld();
  try {
    sitting(w);
    const s = await join(w, "reader.picks", "member", "990001");
    await signUp(w, s.address, "committee", "H90");
    await confirmLatest(w, s.address);
    const page = (await view(w, s.manage)).body;
    assert.doesNotMatch(page, /<select/, "no drop-down");
    const [members, committees, ...rest] = lists(page);
    assert.equal(rest.length, 0);
    assert.equal(members.summary, "Add legislators");
    assert.deepEqual(members.sets, [
      { chamber: "House", keys: ["member:990003", "member:990006", "member:990004"] },
      { chamber: "Senate", keys: ["member:990005", "member:990002"] }],
      "by the roster's sort name, Abbott, Van Der Berg, Young; Adams, Zed -- and Pat Example, followed, left out");
    assert.equal(committees.summary, "Add committees");
    assert.deepEqual(committees.sets, [{ chamber: "House", keys: ["committee:H91"] },
                                       { chamber: "Senate", keys: ["committee:S90"] }]);
    // What is followed is in the list of what is followed, and only there.
    assert.match(page, /name="keep" value="member:990001"/);
    assert.match(page, /name="keep" value="committee:H90"/);
    assert.doesNotMatch(page, /name="add" value="(member:990001|committee:H90)"/);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a list without sort names or chambers is one group in the label's order", async () => {
  // As current.json was before 16 October 2026; the page must still list
  // every one, and work it out from no label.
  const w = makeWorld();
  try {
    sitting(w);
    for (const v of Object.values(w.net.site.get("/changes/current.json").followable)) {
      delete v.sort;
      delete v.chamber;
    }
    const s = await join(w, "reader.older.build");
    const [members, committees] = lists((await view(w, s.manage)).body);
    assert.deepEqual(members.sets, [{ chamber: "", keys: ["member:990004", "member:990006",
      "member:990001", "member:990003", "member:990002", "member:990005"] }],
      "Rep. Al, Rep. Mary, Rep. Pat, Rep. Zoë, Sen. Ann, Sen. Bo: the labels' own order");
    assert.deepEqual(committees.sets, [{ chamber: "", keys: ["committee:H91", "committee:H90",
      "committee:S90"] }]);
  } finally { w.close(); }
});

test("a committee of neither chamber comes last, under a heading of its own", async () => {
  const w = makeWorld();
  try {
    sitting(w);
    sitting(w, { "committee:J90": { label: "Joint Example Committee", url: "/committee/J90" } });
    const s = await join(w, "reader.joint");
    const [, committees] = lists((await view(w, s.manage)).body);
    assert.deepEqual(committees.sets, [{ chamber: "House", keys: ["committee:H91", "committee:H90"] },
                                       { chamber: "Senate", keys: ["committee:S90"] },
                                       { chamber: "Joint and other committees", keys: ["committee:J90"] }]);
    // Still so when every committee with a chamber is followed already.
    await saveForm(w, s.manage, [["listed", "bill:2026/HB9901"], ["keep", "bill:2026/HB9901"],
      ["add", "committee:H90"], ["add", "committee:H91"], ["add", "committee:S90"]]);
    const [, left] = lists((await view(w, s.manage)).body);
    assert.deepEqual(left.sets, [{ chamber: "Joint and other committees", keys: ["committee:J90"] }]);
  } finally { w.close(); }
});

test("without script the whole list shows, and the find box waits for the script", async () => {
  const w = makeWorld();
  try {
    sitting(w);
    const s = await join(w, "reader.no.script");
    const page = (await view(w, s.manage)).body;
    for (const block of lists(page).map(l => l.block)) {
      assert.match(block, /<p class="pickfind" hidden>/, "the box is hidden until the script shows it");
      assert.doesNotMatch(block, /<(li|fieldset|ul|div)[^>]* hidden/, "no row or chamber starts hidden");
      assert.match(block, /<p class="quiet none" data-none hidden>/);
      assert.match(block, /<input type="search" id="find_(member|committee)" data-find/);
    }
    const ticks = [...page.matchAll(/name="add" value="([^"]+)"/g)].map(m => m[1]).sort();
    assert.deepEqual(ticks, ["committee:H90", "committee:H91", "committee:S90", "member:990001", "member:990002",
      "member:990003", "member:990004", "member:990005", "member:990006"]);
    // The district is one unit that a narrow row does not break inside.
    assert.match(page, /value="member:990001"><span>Rep\. Pat Example <span class="tag">\(Merrimack 99\)<\/span><\/span>/);
    assert.match(page, /\.picklist \.tag\{white-space:nowrap\}/);
    // The summary says it opens: the browser's triangle, which a flex summary
    // loses in some browsers and not others, is put away everywhere, and the
    // page's own chevron turns when the list is open.
    assert.match(page, /details\.pick > summary::-webkit-details-marker\{display:none\}/);
    assert.match(page, /details\.pick > summary::marker\{content:""\}/);
    assert.match(page, /details\.pick > summary::before\{content:"";[^}]*border-right:2px solid currentColor;[^}]*transform:rotate\(-45deg\)\}/);
    assert.match(page, /details\.pick\[open\] > summary::before\{transform:rotate\(45deg\)\}/);
  } finally { w.close(); }
});

// The page's own script on a document made of the list as drawn: enough of
// the DOM for PICK_SCRIPT, and no more.
function runPicker(block) {
  const text = s => s.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">");
  const on = {};
  const sets = (block.match(/<fieldset>[\s\S]*?<\/fieldset>/g) || []).map(f => {
    const rows = (f.match(/<li>[\s\S]*?<\/li>/g) || []).map(li => {
      const input = { checked: false, value: /value="([^"]+)"/.exec(li)[1] };
      return { textContent: text(li), hidden: false, input, querySelector: () => input };
    });
    return { hidden: false, rows, querySelector: () => rows.find(r => !r.hidden) || null };
  });
  const rows = sets.flatMap(x => x.rows);
  const box = { value: "", parentNode: { hidden: true },
                addEventListener: (t, f) => { on[t] = f; } };
  const none = { hidden: true }, count = { textContent: "" };
  const d = {
    querySelector: q => ({ "[data-find]": box, "[data-none]": none, "[data-picked]": count })[q],
    querySelectorAll: q => (q === "li" ? rows : q === "fieldset" ? sets : []),
    addEventListener: (t, f) => { on[`d.${t}`] = f; },
  };
  new Function("document", PICK_SCRIPT)({ querySelectorAll: q => (q === "[data-pick]" ? [d] : []) });
  const shown = () => rows.filter(r => !r.hidden).map(r => r.input.value);
  return {
    box, none, count, sets, shown,
    type(v) { box.value = v; on.input(); return shown(); },
    tick(key, yes = true) { rows.find(r => r.input.value === key).input.checked = yes; on["d.change"](); },
    // A key pressed in the find box: whether the script stopped what the
    // browser would have done with it.
    key(k) {
      let stopped = false;
      on.keydown({ key: k, keyCode: k === "Enter" ? 13 : 0, preventDefault() { stopped = true; } });
      return stopped;
    },
  };
}

test("the find box narrows the list as the reader types, case and accents aside, by name or district", async () => {
  const w = makeWorld();
  try {
    sitting(w);
    const s = await join(w, "reader.types");
    const [members, committees] = lists((await view(w, s.manage)).body);
    const p = runPicker(members.block);
    assert.equal(p.box.parentNode.hidden, false, "with script, the box is shown");
    assert.equal(p.shown().length, 6, "everyone to begin with");
    assert.deepEqual(p.type("ZOE"), ["member:990003"], "case and the accent of Zoë aside");
    assert.equal(p.sets[1].hidden, true, "a chamber with nobody left is hidden with its heading");
    assert.deepEqual(p.type("berg van"), ["member:990006"], "every word, anywhere in the name");
    assert.deepEqual(p.type("hills"), ["member:990003"], "the district the label carries");
    assert.deepEqual(p.type("sd2"), ["member:990005"]);
    assert.deepEqual(p.type("Merrimack 99"), ["member:990001"]);
    assert.equal(p.type("  ").length, 6, "nothing typed is everyone");
    assert.equal(p.sets[1].hidden, false);
    // A ticked one stays in sight whatever is typed, and is counted.
    p.tick("member:990004");
    assert.equal(p.count.textContent, "1 checked");
    assert.deepEqual(p.type("adams"), ["member:990004", "member:990005"]);
    assert.deepEqual(p.type("nobody at all"), ["member:990004"]);
    assert.equal(p.none.hidden, true, "a ticked one is still there to see");
    p.tick("member:990004", false);
    assert.deepEqual(p.shown(), []);
    assert.equal(p.none.hidden, false, "and with none at all, it says so");
    assert.equal(p.count.textContent, "");
    const c = runPicker(committees.block);
    assert.deepEqual(c.type("senate"), ["committee:S90"]);
    // Enter in the box does not send the page's one form: a phone's Search
    // key would save it halfway through ticking. Other keys are typed.
    assert.equal(p.key("Enter"), true, "Enter in the find box submitted the form");
    assert.equal(c.key("Enter"), true);
    assert.equal(p.key("a"), false);
  } finally { w.close(); }
});

test("every legislator and committee ticked is added on one Save", async () => {
  const w = makeWorld();
  try {
    sitting(w);
    const s = await join(w, "reader.ticks.four");
    const mails = w.net.outbox.length;
    const r = await saveForm(w, s.manage, [["listed", "bill:2026/HB9901"], ["keep", "bill:2026/HB9901"],
      ["add", "member:990002"], ["add", "member:990003"], ["add", "member:990006"],
      ["add", "committee:S90"], ["add", "committee:H91"]]);
    assert.match(r.headers.location, /n=saved$/);
    const id = w.d1.rows("subscribers")[0].id;
    assert.deepEqual(await followKeys(w.d1, w.env), [`${id} bill:2026/HB9901`, `${id} committee:H91`,
      `${id} committee:S90`, `${id} member:990002`, `${id} member:990003`, `${id} member:990006`]);
    assert.equal(w.net.outbox.length, mails, "adding from the manager sends nothing");
    // And what was added leaves the lists to add from.
    const sets = lists((await view(w, s.manage)).body).map(l => l.sets);
    assert.deepEqual(sets, [[{ chamber: "House", keys: ["member:990001", "member:990004"] },
                             { chamber: "Senate", keys: ["member:990005"] }],
                            [{ chamber: "House", keys: ["committee:H90"] }]],
      "what was added is no longer offered, and a chamber with nothing left has no heading");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a Save that ticks more than the room left adds up to 200, however long the form", async () => {
  const w = makeWorld();
  try {
    const many = Object.fromEntries(Array.from({ length: 260 }, (_, i) => [`member:${991000 + i}`,
      { label: `Rep. Member ${i} (R - Hills ${i})`, sort: `member, ${String(i).padStart(3, "0")}`,
        chamber: "House" }]));
    sitting(w, many);
    const s = await join(w, "reader.ticks.everyone");
    const fields = [["listed", "bill:2026/HB9901"], ["keep", "bill:2026/HB9901"],
      ...Object.keys(many).map(k => ["add", k])];
    assert.ok(new URLSearchParams(fields).toString().length > 4096,
      "longer than the 4 KiB that was once read as no form at all");
    const r = await saveForm(w, s.manage, fields);
    assert.equal(r.status, 303, "a long form is a form");
    assert.match(r.headers.location, /n=full$/);
    assert.equal(w.d1.rows("follows").length, 200);
    const said = await w.call(handlers.manage, postForm("/api/follow/manage",
      { t: s.manage, action: "view", notice: "full" }));
    assert.match(said.body, /one address can follow at most 200 bills, laws, legislators, committees and topics in all, so not everything you asked to add was added/);
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
