// The changes files' contract (workers/follow/CHANGES_FORMAT.md): the
// fixtures meet it exactly, and what breaks it is refused or dropped.

import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { checkCurrent, checkNight } from "../../workers/follow/changes.js";
import { checkFolder } from "./check_changes.js";
import { FIXTURES, loadFixtures } from "./fixtures.js";

const fx = loadFixtures();
const night = d => structuredClone(fx.get(`/changes/${d}.json`));

test("the fixtures meet the format with nothing dropped or mended", () => {
  const r = checkFolder(FIXTURES);
  assert.deepEqual(r.problems, []);
  assert.equal(r.nights, 6);
});

test("check_changes.js passes the fixtures from the command line, and fails a bad folder", () => {
  const script = fileURLToPath(new URL("./check_changes.js", import.meta.url));
  const out = execFileSync(process.execPath, [script, FIXTURES], { encoding: "utf8" });
  assert.match(out, /^ok: 7 file\(s\), 6 night\(s\)/);
  assert.throws(() => execFileSync(process.execPath, [script, fileURLToPath(new URL(".", import.meta.url))],
    { encoding: "utf8", stdio: "pipe" }));
});

test("a night with nothing new is an empty refs, and is a night", () => {
  const r = checkNight(night("2026-10-09"), "2026-10-09");
  assert.deepEqual(r.problems, []);
  assert.equal(r.value.refs.size, 0);
});

test("a file is refused whole when its head is wrong", () => {
  for (const [field, value] of [["format", 2], ["date", "10/9/2026"], ["built", "2026-10-09"],
                                ["sitting_term", "2025"], ["new_by", "guess"], ["refs", []]]) {
    const n = night("2026-10-09");
    n[field] = value;
    const r = checkNight(n, "2026-10-09");
    assert.equal(r.value, null, field);
    assert.ok(r.problems.length, field);
  }
  assert.equal(checkNight(night("2026-10-09"), "2026-10-08").value, null, "a file under another date's name");
  assert.equal(checkCurrent({ ...structuredClone(fx.get("/changes/current.json")), followable: [] }).value, null);
});

test("an item that breaks the format is dropped or mended, and noted", () => {
  const n = night("2026-10-08");
  const items = n.refs["bill:2026/HB9903"].items;
  items.push({ date: "2026-10-07", kind: "vote", summary: "no guid" });
  items.push({ guid: "g2", date: "7 Oct", kind: "vote", summary: "bad date" });
  items.push({ guid: "g3", date: "2026-10-07", kind: "vote", summary: "" });
  items.push({ guid: "g4", date: "2026-10-07", kind: "something-new", summary: "a new kind",
               term: "2025-2026", seen: n.built, url: "javascript:alert(1)" });
  n.refs["topic:housing"].items.push({ guid: "g5", date: "2026-10-07", kind: "action",
                                       summary: "a topic item with no term", seen: n.built });
  n.refs["not a key"] = { items: [] };
  const r = checkNight(n, "2026-10-08");
  const hb = r.value.refs.get("bill:2026/HB9903").items;
  assert.equal(hb.length, 2, "the good item and the one with a new kind");
  const g4 = hb.find(i => i.guid === "g4");
  assert.equal(g4.kind, "action", "an unknown kind reads as action");
  assert.equal(g4.url, "", "a url that is not a path on the site is dropped");
  assert.ok(!r.value.refs.get("topic:housing").items.some(i => i.guid === "g5"));
  assert.ok(r.notes.length >= 5);
});

test("ended, study and upcoming are read as written", () => {
  const e = checkNight(night("2026-10-07"), "2026-10-07").value.refs.get("bill:2026/HB9902");
  assert.equal(e.ended.how, "law");
  assert.equal(e.ended.summary, "HB 9902 was signed into law.");
  const s = checkNight(night("2026-10-08"), "2026-10-08").value.refs.get("bill:2026/HB9901");
  assert.equal(s.study.recommends, true);
  const cur = checkCurrent(structuredClone(fx.get("/changes/current.json"))).value;
  assert.deepEqual(cur.upcoming.get("committee:H90").map(u => u.date), ["2026-10-13", "2026-10-14"],
    "upcoming is put in date order");
  assert.equal(cur.followable.size, 6);
});
