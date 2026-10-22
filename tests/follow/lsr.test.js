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
      summary: "LSR 2027-0001 has been drafted and introduced as HB 9901.",
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
    assert.match(mail.text, /LSR 2027-0001 has been drafted and introduced as HB 9901\. You now follow/);
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
