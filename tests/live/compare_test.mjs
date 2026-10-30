// The November test's comparison (the live layer's design, 26 October 2026,
// section 2.7), run by a person once the deployed Worker has written its test
// files. It asks nobody anything: it reads the downloaded file and the record
// in git.
//
//   npx wrangler r2 object get graniterecord-live/test/2026-03-11.json --file test-2026-03-11.json --remote
//   node tests/live/compare_test.mjs test-2026-03-11.json
//   node tests/live/compare_test.mjs test-2026-03-11.json --docket <the kit's Docket.txt>
//
// Every roll call the test read is compared with records/rollcalls/ in git:
// the same roll calls, each one's tally, bill and time, and every ballot by
// vote. With --docket, the docket lines Q3 returned are compared with the
// lines of the kit's Docket.txt that Q3's filter should take. It says the
// go conditions as it finds them: the server does not require encryption,
// both comparisons are exact, Q2 and Q3 each answer in under 2 s (Q3 over 1 s
// means it runs on one hot run in five). Exit 0 when all of that holds.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { nhLocal } from "../../workers/live/test_mode.js";
import { addDays } from "../../workers/live/sql.js";

const RECORDS = new URL("../../records/rollcalls/", import.meta.url);
// The record's word for a ballot as the live file's character: the design's
// section 2.5 written out here, and not taken from live.gen.js, so that a
// mapping the Worker has wrong is not also the one it is compared with.
export const CHAR_OF_WORD = Object.freeze({
  "Yea": "Y", "Nay": "N", "Not Voting/Excused": "E", "Not Voting/Not Excused": "X", "Presiding": "P",
  "No vote recorded": ".", "": ".",
});

// "3/11/2026 9:23:27 AM", the record's way, as 2026-03-11T09:23:27.
export function recordTime(s) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4}) (\d{1,2}):(\d{2}):(\d{2}) ([AP]M)$/.exec((s || "").trim());
  if (!m) return null;
  const h = (Number(m[4]) % 12) + (m[7] === "PM" ? 12 : 0);
  const two = n => String(n).padStart(2, "0");
  return `${m[3]}-${two(m[1])}-${two(m[2])}T${two(h)}:${m[5]}:${m[6]}`;
}

function lines(url) {
  return readFileSync(url, "utf8").replace(/^﻿/, "").split(/\r?\n/).filter(l => l.trim()).map(l => l.split("|"));
}

// The record's roll calls dated `day`: Map id -> {..., ballots: Map member -> character},
// read once a process for each folder and day (the tests compare many copies).
const DAYS = new Map();
export function recordDay(day, dir = RECORDS) {
  const key = `${dir}|${day}`;
  if (!DAYS.has(key)) DAYS.set(key, readDay(day, dir));
  return DAYS.get(key);
}

function readDay(day, dir) {
  const year = day.slice(0, 4);
  const out = new Map();
  for (const f of lines(new URL(`RollCallSummary_${year}.txt`, dir))) {
    if (f[0] !== year || (recordTime(f[3]) || "").slice(0, 10) !== day) continue;
    out.set(`${year}-${f[1]}-${Number(f[2])}`, {
      body: f[1], seq: Number(f[2]), local: recordTime(f[3]), bill: f[4] || null,
      yeas: Number(f[5]), nays: Number(f[6]), present: Number(f[7]), absent: Number(f[8]),
      modified: recordTime(f[14]), ballots: new Map(),
    });
  }
  for (const f of lines(new URL(`RollCallHistory_${year}.txt`, dir))) {
    const rc = out.get(`${year}-${f[1]}-${Number(f[2])}`);
    if (rc) rc.ballots.set(f[4] || f[3], CHAR_OF_WORD[f[6]] ?? `?${f[6]}`);
  }
  return out;
}

const local = iso => (iso ? nhLocal(new Date(iso)) : null);

// {ok, said: [lines], counts}
export function compare(file, { dir = RECORDS } = {}) {
  const said = [];
  const counts = { rollcalls: 0, ballots: 0 };
  let ok = true;
  const no = s => { ok = false; said.push(`  DIFFERS  ${s}`); };
  if (file?.kind !== "session.votes" || !file.test) {
    return { ok: false, said: ["this is not a test file the live Worker wrote"], counts };
  }
  const t = file.test;
  const enc = t.connection?.prelogin?.encryption;
  if (enc) {
    if (enc === "NOT_SUP" || enc === "OFF") said.push(`go: the server does not require encryption (it answered ${enc})`);
    else no(`the server answered encryption ${enc}: a Worker cannot read it (design section 2.8)`);
  }
  if (t.connection?.server) said.push(`the server: ${t.connection.server.program} ${t.connection.server.version}, TDS ${t.connection.tds}`);
  if (t.version) said.push(`SELECT @@VERSION: ${t.version.split("\n")[0]}`);
  if (t.problem) {
    no(`the test did not read: ${t.problem}: ${t.error}`);
    said.push("no-go: the differences above");
    return { ok, said, counts };
  }
  for (const s of t.statements || []) {
    if (s.problem) { no(`${s.name} failed (${s.problem}): ${s.error}`); continue; }
    said.push(`${s.name}: ${s.rows} rows, ${s.bytes} bytes, ${(s.ms / 1000).toFixed(2)} s`);
    if (/^q[23]/.test(s.name) && s.ms >= 2000) no(`${s.name} took ${(s.ms / 1000).toFixed(1)} s, over the 2 s the go asks`);
    else if (s.name === "q3" && s.ms >= 1000) said.push("  so Q3, over 1 s, runs on one hot run in five in session");
  }
  if ((t.unread || []).length) no(`the ballots of ${t.unread.length} roll calls were not read`);

  const record = recordDay(file.date, dir);
  const mine = new Map((file.rollcalls || []).map(r => [r.id, r]));
  for (const id of record.keys()) if (!mine.has(id)) no(`${id} is in the record and not in the test file`);
  for (const id of mine.keys()) if (!record.has(id)) no(`${id} is in the test file and not in the record`);
  for (const [id, r] of mine) {
    const rec = record.get(id);
    if (!rec) continue;
    counts.rollcalls++;
    for (const k of ["yeas", "nays", "present", "absent"]) {
      if (r[k] !== rec[k]) no(`${id} ${k}: ${r[k]}, the record ${rec[k]}`);
    }
    if ((r.bill_as_recorded || null) !== rec.bill) no(`${id} bill: ${r.bill_as_recorded}, the record ${rec.bill}`);
    if (r.body === "H" && local(r.taken) !== rec.local) no(`${id} taken: ${local(r.taken)}, the record ${rec.local}`);
    if (r.body === "S" && rec.modified && local(r.saved) !== rec.modified) {
      no(`${id} saved: ${local(r.saved)}, the record ${rec.modified}`);
    }
    if (!r.ballots_complete) no(`${id}'s ballots are not complete against its tally`);
    const members = file.members?.[r.body] || [];
    const got = new Map(members.map((m, i) => [m, r.ballots?.[i] ?? "."]));
    for (const m of new Set([...got.keys(), ...rec.ballots.keys()])) {
      const a = got.get(m) ?? ".";
      const b = rec.ballots.get(m) ?? ".";
      if (a !== b) no(`${id} member ${m}: ${a}, the record ${b}`);
      else if (a !== ".") counts.ballots++;
    }
  }
  said.push(ok
    ? `go: ${counts.rollcalls} roll calls and ${counts.ballots.toLocaleString("en-US")} ballots, every tally and every ballot equal to records/rollcalls/`
    : "no-go: the differences above");
  return { ok, said, counts };
}

// The kit's Docket.txt (year|LSR|entered|bill|chamber|words|entered) against
// Q3's lines in the test file: those Q3's filter should take, as a multiset.
export function compareDocket(file, docketText) {
  const day = file.date;
  const year = day.slice(0, 4);
  const [y, m, d] = day.split("-");
  const mdy = `${m}/${d}/${y}`;
  const since = addDays(day, -21);
  const next = addDays(day, 1);
  const want = [];
  for (const f of docketText.replace(/^﻿/, "").split(/\r?\n/).filter(Boolean).map(l => l.split("|"))) {
    const entered = recordTime(f[2]);
    if (f[0] !== year || !entered || !/RC [0-9]/i.test(f[5] || "")) continue;
    const on = entered.slice(0, 10);
    if ((on >= day && on < next) || (on >= since && f[5].includes(mdy))) want.push(`${f[4]}|${f[3]}|${f[5]}`);
  }
  const got = (file.test?.docket || []).map(x => `${x.body}|${x.bill_as_recorded || ""}|${x.line}`);
  const said = [];
  const left = [...got];
  for (const w of want) {
    const i = left.indexOf(w);
    if (i >= 0) left.splice(i, 1);
    else said.push(`  DIFFERS  in Docket.txt, not read by Q3: ${w}`);
  }
  for (const g of left) said.push(`  DIFFERS  read by Q3, not in Docket.txt: ${g}`);
  const ok = !said.length;
  said.push(ok ? `go: Q3's ${got.length} docket lines are Docket.txt's, exactly` : "no-go: the docket lines above differ");
  return { ok, said };
}

function main(argv) {
  const args = argv.slice(2);
  if (!args.length) {
    // `node --test tests/live/` runs every *_test.mjs it finds; this is a
    // command, not a test, and its own tests are in sql.test.js.
    if (process.env.NODE_TEST_CONTEXT) return 0;
    console.error("usage: node tests/live/compare_test.mjs <test file> [--docket <Docket.txt>]");
    return 2;
  }
  const at = args.indexOf("--docket");
  const docket = at >= 0 ? args.splice(at, 2)[1] : null;
  const file = JSON.parse(readFileSync(args[0], "utf8"));
  console.log(`${args[0]}: the test's read of ${file.date}, at ${file.read_at}`);
  const a = compare(file);
  console.log(a.said.join("\n"));
  let ok = a.ok;
  if (docket) {
    const b = compareDocket(file, readFileSync(docket, "utf8"));
    console.log(b.said.join("\n"));
    ok = ok && b.ok;
  }
  return ok ? 0 : 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exitCode = main(process.argv);
