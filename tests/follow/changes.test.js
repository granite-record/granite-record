// The changes files' contract (workers/follow/CHANGES_FORMAT.md): the
// fixtures meet it exactly, and what breaks it is refused or dropped.

import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { checkCurrent, checkNight } from "../../workers/follow/changes.js";
import { checkFiles, checkFolder } from "./check_changes.js";
import { FIXTURES, loadFixtures } from "./fixtures.js";

const fx = loadFixtures();
const night = d => structuredClone(fx.get(`/changes/${d}.json`));

test("the fixtures meet the format with nothing dropped or mended", () => {
  const r = checkFolder(FIXTURES);
  assert.deepEqual(r.problems, []);
  assert.equal(r.nights, 8);
});

test("check_changes.js passes the fixtures from the command line, and fails a bad folder", () => {
  const script = fileURLToPath(new URL("./check_changes.js", import.meta.url));
  const out = execFileSync(process.execPath, [script, FIXTURES], { encoding: "utf8" });
  assert.match(out, /^ok: 9 file\(s\), 8 night\(s\)/);
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

// The fixtures as a folder of parsed files, to be broken one rule at a time.
const folder = () => new Map([...fx].map(([p, v]) => [p.slice("/changes/".length), structuredClone(v)]));
const problems = files => checkFiles(files).problems;

test("an item in two nights is caught, for the same record; the same guid under two records is not", () => {
  const f = folder();
  assert.deepEqual(problems(f), [], "the fixtures' HB 9903 roll call is under the bill and the topic, one night");
  const dup = structuredClone(f.get("2026-10-07.json").refs["bill:2026/HB9903"].items[0]);
  f.get("2026-10-08.json").refs["bill:2026/HB9903"].items.push(dup);
  const p = problems(f);
  assert.equal(p.length, 1);
  assert.match(p[0], /^bill:2026\/HB9903: item .* is in 2026-10-07 and 2026-10-08$/);
});

test("under record-date a night holds the day before it, and only that day", () => {
  const f = folder();
  for (const v of f.values()) {
    v.new_by = "record-date";
    for (const r of Object.values(v.refs || {})) {
      for (const it of r.items || []) delete it.seen;
      if (r.study) delete r.study.seen;
    }
  }
  const p = problems(f);
  // The fixtures were written first-seen: the 5th holds the 2nd's work session.
  assert.ok(p.some(x => /^2026-10-05\.json: bill:2026\/HB9901 item .* is dated 2026-10-02; under record-date this night holds 2026-10-04 only$/.test(x)), p.join("\n"));
  // The 7th's items are the 6th's, as the rule asks: nothing said of them.
  assert.ok(!p.some(x => x.startsWith("2026-10-07.json")), p.join("\n"));
  // The topic's 2024 item in the 8th is caught as well.
  assert.ok(p.some(x => /2026-10-08\.json: topic:housing item .* dated 2024-05-02/.test(x)));
});

test("one way of deciding new across the folder, the nights unbroken, and eight of them", () => {
  let f = folder();
  f.get("2026-10-06.json").new_by = "record-date";
  for (const r of Object.values(f.get("2026-10-06.json").refs)) for (const it of r.items) delete it.seen;
  assert.ok(problems(f).some(p => p === "new_by differs between files: first-seen, record-date"));
  f = folder();
  f.delete("2026-10-06.json");
  assert.deepEqual(problems(f), ["no night between 2026-10-05 and 2026-10-07",
                                 "7 night(s) kept, fewer than 8"]);
  f = folder();
  f.delete("2026-10-10.json");
  assert.ok(problems(f).includes("the newest night is 2026-10-09 and current.json's date is 2026-10-10"));
});

test("a bill, member or committee that leaves the list must say it ended; a topic need not", () => {
  const f = folder();
  const cur = f.get("current.json");
  delete cur.followable["bill:2026/HB9903"];
  delete cur.followable["member:990001"];
  delete cur.followable["committee:H90"];
  delete cur.followable["topic:housing"];
  assert.deepEqual(problems(f), [
    "bill:2026/HB9903: named by a night, no longer followable, and no night says it ended",
    "committee:H90: named by a night, no longer followable, and no night says it ended",
    "member:990001: named by a night, no longer followable, and no night says it ended"]);
  f.get("2026-10-10.json").refs["member:990001"] = { ended: { how: "left", date: "2026-10-09",
    summary: "Rep. Pat Example (Merrimack 99) no longer sits.", guid: "member:990001:left" } };
  assert.equal(problems(f).length, 2);
});

test("ended, study and upcoming are read as written", () => {
  const e = checkNight(night("2026-10-07"), "2026-10-07").value.refs.get("bill:2026/HB9902");
  assert.equal(e.ended.how, "law");
  assert.equal(e.ended.summary, "HB 9902 — Signed into law.");
  const s = checkNight(night("2026-10-08"), "2026-10-08").value.refs.get("bill:2026/HB9901");
  assert.equal(s.study.recommends, true);
  const cur = checkCurrent(structuredClone(fx.get("/changes/current.json"))).value;
  assert.deepEqual(cur.upcoming.get("committee:H90").map(u => u.date), ["2026-10-13", "2026-10-14"],
    "upcoming is put in date order");
  assert.equal(cur.followable.size, 7);
  assert.equal(cur.followable.get("bill:2026/HB9901").now, "In committee");
  assert.equal(cur.followable.get("law:91-A").label, "RSA 91-A: Access to Governmental Records and Meetings");
  const v = checkNight(night("2026-10-08"), "2026-10-08").value.refs.get("member:990001").items[0];
  assert.deepEqual([v.milestone, v.vote.ballot, v.vote.result, v.vote.tally, v.vote.bill],
    [true, "yes", "passed", "11-9", "HB 9903-FN"], "a ballot keeps its roll call");
});

test("a floor roll call's count is kept as written, and one that is not a count is dropped and noted", () => {
  const n = night("2026-10-08");
  const items = n.refs["bill:2026/HB9903"].items;
  const base = { date: "2026-10-07", kind: "vote", summary: "HB 9903-FN \u2014 MA RC 201-163",
                 term: "2025-2026", seen: n.built };
  items.push({ ...base, guid: "r1", rollcall: { yeas: 201, nays: 163, passed: true, need: 183,
    rule: "a majority", parties: [["R", 190, 13], ["D", 11, 150]] } });
  items.push({ ...base, guid: "r2", rollcall: { yeas: "201", nays: 163, passed: true } });
  items.push({ ...base, guid: "r3", rollcall: { yeas: 0, nays: 0, passed: false } });
  items.push({ ...base, guid: "r4", rollcall: { yeas: 5, nays: 4, passed: "yes" } });
  items.push({ ...base, guid: "r5", rollcall: { yeas: 5, nays: 4, passed: false, rule: "no need given",
    parties: [["R", 5, 4], ["democrat", 1, 1], ["D", -1, 2]] } });
  const r = checkNight(n, "2026-10-08");
  const got = Object.fromEntries(r.value.refs.get("bill:2026/HB9903").items.map(i => [i.guid, i.rollcall]));
  assert.deepEqual(got.r1, { yeas: 201, nays: 163, passed: true, need: 183, rule: "a majority",
    parties: [["R", 190, 13], ["D", 11, 150]] });
  for (const g of ["r2", "r3", "r4"]) assert.equal(got[g], null, `${g}: not a count`);
  assert.deepEqual(got.r5, { yeas: 5, nays: 4, passed: false, need: 0, rule: "", parties: [["R", 5, 4]] },
    "a rule with no need is not kept, nor a party that is not a code and two counts");
  assert.ok(r.notes.some(x => /rollcall has no yeas/.test(x)) && r.notes.some(x => /rollcall party/.test(x)));
  assert.ok(Object.values(got).filter(Boolean).length === 2 && got.r1, "an item keeps its place without one");
});
