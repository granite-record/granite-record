// The session.votes shape (schema/session.votes.json; design sections 4.4
// and 5): the shared cases, the Worker's own empty file, and the day the
// merge writes from a read. The replays check their live files too
// (replay.test.js).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { check } from "./schema.js";
import { emptyFile, merge } from "../../workers/live/merge.js";

const CASES = JSON.parse(readFileSync(new URL("./schema_cases.json", import.meta.url), "utf8")).cases;

test("session.votes: every shared case is judged as the cases file says", () => {
  assert.ok(CASES.length >= 30 && CASES.some(c => c.valid) && CASES.some(c => !c.valid));
  const wrong = CASES.filter(c => {
    try { check(c.doc); return !c.valid; } catch (e) { return c.valid; }
  }).map(c => c.name);
  assert.deepEqual(wrong, []);
});

test("session.votes: the Worker's empty file and a merged read hold to the schema", () => {
  check(emptyFile("2027-01-07"));
  const { file } = merge(emptyFile("2027-01-07"), {
    date: "2027-01-07", at: "2027-01-07T15:42:58Z", covered: true, misses: {}, saves: {},
    rows: [{ id: "2027-H-14", body: "H", seq: 14, year: 2027, bill_as_recorded: "HB2", question: "Ought to Pass",
             vote_date: "2027-01-07T10:41:07", modified: "2027-01-07T10:41:30", user: "VOTE SYSTEM",
             yeas: 1, nays: 0, present: 0, absent: 0 }],
    ballots: new Map([["2027-H-14", new Map([["11463", "Y"]])]]),
    lines: [{ body: "H", bill_as_recorded: "HB2", order: 1, entered: "2027-01-07T10:43:00", line: "MA RC 1-0 01/07/2027" }],
  });
  assert.equal(file.rollcalls.length, 1);
  check(file);
  // A field the shape lacks is caught, so the check above can fail.
  assert.throws(() => check({ ...file, extra: 1 }), /extra is not a field/);
});
