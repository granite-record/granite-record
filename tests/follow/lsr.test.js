// A bill request followed until it is a bill (22 October 2026): the night
// it is drafted, its follower is told once, and the follow moves onto the
// bill -- never ending it, never deleting the address -- and the manage page
// mends the moved row's fingerprint on the reader's next visit.

import test from "node:test";
import assert from "node:assert/strict";
import { followHash } from "../../workers/follow/address.js";
import { checkNight } from "../../workers/follow/changes.js";
import { run } from "../../workers/follow/sender.js";
import { loadFixtures, makeWorld } from "./fakes.js";
import { view } from "./flows.js";
import { followKeys, insertSubscriber } from "./rows.js";

const FX = loadFixtures();
const CURRENT = FX.get("/changes/current.json");

// The site on the morning of the 6th: LSR 2027-0001 drafted overnight into
// HB 9901, which is followable.
function site(w) {
  w.net.site.clear();
  const cur = structuredClone(CURRENT);
  cur.date = "2026-10-06";
  w.net.site.set("/changes/current.json", cur);
  w.net.site.set("/changes/2026-10-06.json", { format: 1, date: "2026-10-06",
    built: "2026-10-06T09:00:00Z", sitting_term: "2025-2026", new_by: "first-seen",
    refs: { "lsr:2027-0001": { ended: { how: "drafted", becomes: "bill:2026/HB9901",
      summary: "LSR 2027-0001 has been drafted and filed as HB 9901.",
      date: "2026-10-06", guid: "lsr:2027-0001:ended:drafted" } } } });
}

test("a drafted request's ending names the bill, and only a bill", () => {
  const night = { format: 1, date: "2026-10-06", built: "2026-10-06T09:00:00Z",
    sitting_term: "2025-2026", new_by: "first-seen", refs: {
      "lsr:2027-0001": { ended: { how: "drafted", becomes: "bill:2026/HB9901", summary: "x",
                                  date: "2026-10-06", guid: "g" } },
      "lsr:2027-0002": { ended: { how: "drafted", becomes: "member:12", summary: "x",
                                  date: "2026-10-06", guid: "g2" } } } };
  const r = checkNight(night, "2026-10-06");
  assert.equal(r.value.refs.get("lsr:2027-0001").ended.becomes, "bill:2026/HB9901");
  assert.equal(r.value.refs.get("lsr:2027-0002").ended.becomes, undefined);
  assert.ok(r.notes.some(n => n.includes("becomes is not a bill's key")));
});

test("the request's follower is told, the follow moves onto the bill, and the address stays", async () => {
  const w = makeWorld();
  try {
    site(w);
    const s = await insertSubscriber(w.d1, w.env, w.address("lsr.only"), {
      follows: ["lsr:2027-0001"], lastSentOn: "2026-10-05", sentDate: "2026-10-05",
      sentBuilt: "2026-10-05T09:00:00Z" });
    w.now = new Date("2026-10-06T12:00:00Z");
    const r = await run(w.env, w.now);
    assert.equal(r.sent, 1);
    const mail = w.net.outbox[0];
    assert.match(mail.text, /LSR 2027-0001 has been drafted and filed as HB 9901\. You now follow/);
    assert.match(mail.text, /BILL REQUESTS YOU FOLLOW/);
    assert.equal(w.d1.rows("subscribers").length, 1, "the address is kept: its follow moved, not ended");
    assert.deepEqual(await followKeys(w.d1, w.env), [`${s.id} bill:2026/HB9901`]);
    assert.ok(w.logs.lines.includes("follow sender.requests-moved-to-bills 1"));
    // The next visit to the manage page mends the moved row's fingerprint.
    const row = () => w.d1.rows("follows")[0];
    assert.equal(row().follow_hmac, await followHash(w.env, s.h, "lsr:2027-0001"));
    await view(w, s.links.manage);
    assert.equal(row().follow_hmac, await followHash(w.env, s.h, "bill:2026/HB9901"));
  } finally { w.close(); }
});

test("a reader already following the bill keeps one follow of it", async () => {
  const w = makeWorld();
  try {
    site(w);
    const s = await insertSubscriber(w.d1, w.env, w.address("both"), {
      follows: ["lsr:2027-0001", "bill:2026/HB9901"], lastSentOn: "2026-10-05",
      sentDate: "2026-10-05", sentBuilt: "2026-10-05T09:00:00Z" });
    w.now = new Date("2026-10-06T12:00:00Z");
    await run(w.env, w.now);
    assert.deepEqual(await followKeys(w.d1, w.env), [`${s.id} bill:2026/HB9901`]);
  } finally { w.close(); }
});

// "View the text" (the owner, 17 November 2026: "maybe include a link that
// says View the text that shows the granite record tab once we've imported
// the text"): the ending's url, the request page's Bill Text tab, where the
// build gives one -- and nothing where it gives none or what is no path.
test("a drafted request whose text is on the site links it as View the text", async () => {
  const where = "/request/2027-0001#pane_LSR20270001_6";
  const night = { format: 1, date: "2026-10-06", built: "2026-10-06T09:00:00Z",
    sitting_term: "2025-2026", new_by: "first-seen", refs: {
      "lsr:2027-0001": { ended: { how: "drafted", becomes: "bill:2026/HB9901", summary: "x",
                                  date: "2026-10-06", guid: "g", url: where } },
      "lsr:2027-0002": { ended: { how: "drafted", becomes: "bill:2026/HB9902", summary: "x",
                                  date: "2026-10-06", guid: "g2", url: "https://example.org/x" } } } };
  const r = checkNight(night, "2026-10-06");
  assert.equal(r.value.refs.get("lsr:2027-0001").ended.url, where);
  assert.equal(r.value.refs.get("lsr:2027-0002").ended.url, undefined);
  assert.ok(r.notes.some(n => n.includes("url is not a path on the site")));
  const w = makeWorld();
  try {
    site(w);
    const day = w.net.site.get("/changes/2026-10-06.json");
    day.refs["lsr:2027-0001"].ended.url = where;
    await insertSubscriber(w.d1, w.env, w.address("lsr.text"), {
      follows: ["lsr:2027-0001"], lastSentOn: "2026-10-05", sentDate: "2026-10-05",
      sentBuilt: "2026-10-05T09:00:00Z" });
    w.now = new Date("2026-10-06T12:00:00Z");
    assert.equal((await run(w.env, w.now)).sent, 1);
    const mail = w.net.outbox[0];
    assert.match(mail.text, /drafted and filed as HB 9901\. You now follow[^\n]*\n {2}View the text: https?:\/\/[^\s]*\/request\/2027-0001#pane_LSR20270001_6/);
    assert.match(mail.html, /<a href="https?:\/\/[^"]*\/request\/2027-0001#pane_LSR20270001_6"[^>]*>View the text<\/a>/);
  } finally { w.close(); }
  const v = makeWorld();
  try {
    site(v);
    await insertSubscriber(v.d1, v.env, v.address("lsr.notext"), {
      follows: ["lsr:2027-0001"], lastSentOn: "2026-10-05", sentDate: "2026-10-05",
      sentBuilt: "2026-10-05T09:00:00Z" });
    v.now = new Date("2026-10-06T12:00:00Z");
    await run(v.env, v.now);
    assert.doesNotMatch(v.net.outbox[0].text + v.net.outbox[0].html, /View the text/);
  } finally { v.close(); }
});
