// A legislator who sits on under another number (16 November 2026): the
// General Court gives a representative elected to the Senate a new number, so
// the night its roster turns their key leaves the list. Their follower is told
// once where they sit now, and the follow moves to the new key -- never ending
// it, never deleting the address -- while a member who truly left is told so
// and that follow ends, as before.

import test from "node:test";
import assert from "node:assert/strict";
import { checkNight } from "../../workers/follow/changes.js";
import { run } from "../../workers/follow/sender.js";
import { loadFixtures, makeWorld } from "./fakes.js";
import { followKeys, insertSubscriber } from "./rows.js";

const FX = loadFixtures();
const CURRENT = FX.get("/changes/current.json");

const MOVED = { how: "moved", becomes: "member:990101",
  summary: "Pat Example now sits in the Senate for District 8.",
  date: "2026-10-06", guid: "member:990001:ended:moved" };
const LEFT = { how: "left",
  summary: "Rep. Lee Other (D - Merrimack 98) is no longer among the sitting legislators.",
  date: "2026-10-06", guid: "member:990002:ended:left" };

// The site on the morning of the 6th: the roster turned overnight. Rep. Pat
// Example (member:990001) sits in the Senate as member:990101, which the list
// carries for email; Rep. Lee Other (member:990002) left.
function site(w) {
  w.net.site.clear();
  const cur = structuredClone(CURRENT);
  cur.date = "2026-10-06";
  delete cur.followable["member:990001"];
  cur.followable["member:990101"] = { label: "Sen. Pat Example (R - SD8)",
    sort: "example, pat", chamber: "Senate", url: "/legislator/pat-example-sd-8" };
  w.net.site.set("/changes/current.json", cur);
  w.net.site.set("/changes/2026-10-06.json", { format: 1, date: "2026-10-06",
    built: "2026-10-06T09:00:00Z", sitting_term: "2025-2026", new_by: "first-seen",
    refs: { "member:990001": { ended: MOVED }, "member:990002": { ended: LEFT } } });
}

test("a legislator's ending names their new key, and only a member's key, not their own", () => {
  const night = { format: 1, date: "2026-10-06", built: "2026-10-06T09:00:00Z",
    sitting_term: "2025-2026", new_by: "first-seen", refs: {
      "member:990001": { ended: MOVED },
      "member:990003": { ended: { ...MOVED, becomes: "bill:2026/HB9901", guid: "g3" } },
      "member:990004": { ended: { ...MOVED, becomes: "member:990004", guid: "g4" } },
      "committee:H90": { ended: { ...MOVED, becomes: "committee:H91", guid: "g5" } } } };
  const r = checkNight(night, "2026-10-06");
  assert.equal(r.value.refs.get("member:990001").ended.becomes, "member:990101");
  for (const k of ["member:990003", "member:990004", "committee:H90"])
    assert.equal(r.value.refs.get(k).ended.becomes, undefined, k);
  assert.equal(r.notes.filter(n => n.includes("becomes is not a member's key")).length, 2, r.notes);
  assert.ok(r.notes.some(n => n.startsWith("refs committee:H90 ended: becomes is not a bill's key")),
    r.notes);
});

test("the moved legislator's follower is told where they sit, the follow moves, and the address stays",
  async () => {
    const w = makeWorld();
    try {
      site(w);
      const s = await insertSubscriber(w.d1, w.env, w.address("moved.only"), {
        follows: ["member:990001"], lastSentOn: "2026-10-05", sentDate: "2026-10-05",
        sentBuilt: "2026-10-05T09:00:00Z" });
      w.now = new Date("2026-10-06T12:00:00Z");
      const r = await run(w.env, w.now);
      assert.equal(r.sent, 1);
      const mail = w.net.outbox[0];
      assert.match(mail.text, /Pat Example now sits in the Senate for District 8\. Your follow has moved with them/);
      assert.doesNotMatch(mail.text, /no longer among the sitting|no more updates|the bill in its place/);
      assert.equal(w.d1.rows("subscribers").length, 1, "the address is kept: its follow moved, not ended");
      assert.deepEqual(await followKeys(w.d1, w.env), [`${s.id} member:990101`]);
      assert.ok(w.logs.lines.includes("follow sender.members-moved 1"), w.logs.lines);
      assert.ok(!w.logs.lines.some(l => l.startsWith("follow sender.requests-moved-to-bills")));
    } finally { w.close(); }
  });

test("a legislator who left is told so and that follow ends; one already following the new key keeps one",
  async () => {
    const w = makeWorld();
    try {
      site(w);
      const a = await insertSubscriber(w.d1, w.env, w.address("left.too"), {
        follows: ["member:990002", "bill:2026/HB9901"], lastSentOn: "2026-10-05",
        sentDate: "2026-10-05", sentBuilt: "2026-10-05T09:00:00Z" });
      const b = await insertSubscriber(w.d1, w.env, w.address("both.keys"), {
        follows: ["member:990001", "member:990101"], lastSentOn: "2026-10-05",
        sentDate: "2026-10-05", sentBuilt: "2026-10-05T09:00:00Z" });
      w.now = new Date("2026-10-06T12:00:00Z");
      await run(w.env, w.now);
      const told = w.net.outbox.find(m => /Lee Other/.test(m.text));
      assert.ok(told, "the reader of the member who left was not told");
      assert.match(told.text, /Rep\. Lee Other \(D - Merrimack 98\) is no longer among the sitting legislators\. There will be no more updates on it/);
      assert.deepEqual(await followKeys(w.d1, w.env),
        [`${a.id} bill:2026/HB9901`, `${b.id} member:990101`]);
    } finally { w.close(); }
  });
