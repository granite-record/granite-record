// Hold a folder of changes files to workers/follow/CHANGES_FORMAT.md, with
// the same code the sender reads them with (workers/follow/changes.js).
//
//   node tests/follow/check_changes.js site/changes
//   node tests/follow/check_changes.js tests/follow/fixtures/changes
//
// Fails on a file refused whole, and on any entry the sender would drop or
// mend: the build should write nothing the sender has to forgive. Also
// fails on a folder with no current.json, or with no night at all, because
// a build that wrote nothing is not a quiet night.
//
// AND THE RULES THAT SPAN FILES, which no one file can break alone:
//   - every file says the same new_by;
//   - the newest night is current.json's date, the nights run without a gap,
//     and there are at least eight of them (a weekly reads seven, and the
//     eighth covers a Saturday whose build ran late);
//   - a record's item -- its guid -- is in at most one night, and so is its
//     study report and its ending; the sender keeps no memory of guids
//     between emails, so an item in two nights reaches a reader twice;
//   - under record-date, a night D holds only items dated D - 1;
//   - a bill, member or committee that any night names and current.json no
//     longer lists has an ended in some night (a topic need not: it leaves
//     the list between terms and comes back). The full rule -- a key in last
//     night's current.json and not tonight's carries an ended tonight -- needs
//     last night's current.json, which a folder does not hold; preflight
//     holds that one against the build's own two nights.

import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { checkCurrent, checkNight } from "../../workers/follow/changes.js";

export const NIGHTS_KEPT = 8;
const ENDS = new Set(["bill", "member", "committee"]);

const dayBefore = d => new Date(Date.parse(`${d}T00:00:00Z`) - 86400000).toISOString().slice(0, 10);

// files: Map of file name -> parsed JSON (or undefined for a file that was
// not JSON). The folder's checks, on what is already read.
export function checkFiles(files, { nightsKept = NIGHTS_KEPT } = {}) {
  const out = [];
  const names = [...files.keys()].sort();
  const nightNames = names.filter(f => /^\d{4}-\d{2}-\d{2}\.json$/.test(f));
  if (!names.includes("current.json")) out.push("current.json: missing");
  if (!nightNames.length) out.push("no night's file at all");
  let current = null;
  const nights = [];
  for (const f of names) {
    const obj = files.get(f);
    if (obj === undefined) { out.push(`${f}: not JSON`); continue; }
    const r = f === "current.json" ? checkCurrent(obj)
      : nightNames.includes(f) ? checkNight(obj, f.slice(0, 10)) : null;
    if (!r) { out.push(`${f}: not a changes file's name`); continue; }
    for (const p of r.problems) out.push(`${f}: ${p}`);
    for (const n of r.notes) out.push(`${f}: ${n}`);
    if (!r.value) continue;
    if (f === "current.json") current = r.value; else nights.push(r.value);
  }

  // ---- across files ------------------------------------------------------------
  const bases = new Set([current, ...nights].filter(Boolean).map(v => v.new_by));
  if (bases.size > 1) out.push(`new_by differs between files: ${[...bases].sort().join(", ")}`);

  nights.sort((a, b) => a.date.localeCompare(b.date));
  if (nights.length) {
    const newest = nights[nights.length - 1].date;
    if (current && newest !== current.date)
      out.push(`the newest night is ${newest} and current.json's date is ${current.date}`);
    for (let i = 1; i < nights.length; i++)
      if (dayBefore(nights[i].date) !== nights[i - 1].date)
        out.push(`no night between ${nights[i - 1].date} and ${nights[i].date}`);
    if (nights.length < nightsKept)
      out.push(`${nights.length} night(s) kept, fewer than ${nightsKept}`);
  }

  const seen = new Map();       // "<key> <guid>" -> the night that holds it
  const once = (key, guid, date, what) => {
    const id = `${key} ${guid}`;
    if (seen.has(id)) out.push(`${key}: ${what} ${guid.slice(0, 80)} is in ${seen.get(id)} and ${date}`);
    else seen.set(id, date);
  };
  const ended = new Set(), named = new Set();
  for (const n of nights) {
    const want = n.new_by === "record-date" ? dayBefore(n.date) : null;
    for (const [key, r] of n.refs) {
      named.add(key);
      for (const it of r.items) {
        once(key, it.guid, n.date, "item");
        if (want && it.date !== want)
          out.push(`${n.date}.json: ${key} item ${it.guid.slice(0, 60)} is dated ${it.date}; ` +
            `under record-date this night holds ${want} only`);
      }
      if (r.study) {
        once(key, r.study.guid || "study", n.date, "study report");
        if (want && r.study.date !== want)
          out.push(`${n.date}.json: ${key} study is dated ${r.study.date}; under record-date ` +
            `this night holds ${want} only`);
      }
      if (r.ended) { once(key, "(ended)", n.date, "ending"); ended.add(key); }
    }
  }
  if (current)
    for (const key of [...named].sort()) {
      const kind = key.slice(0, key.indexOf(":"));
      if (ENDS.has(kind) && !current.followable.has(key) && !ended.has(key))
        out.push(`${key}: named by a night, no longer followable, and no night says it ended`);
    }
  return { files: names.length, nights: nightNames.length, problems: out };
}

export function checkFolder(dir, opts = {}) {
  const files = new Map();
  for (const f of readdirSync(dir).filter(f => f.endsWith(".json"))) {
    let obj;
    try { obj = JSON.parse(readFileSync(join(dir, f), "utf8")); } catch { obj = undefined; }
    files.set(f, obj);
  }
  return checkFiles(files, opts);
}

if (import.meta.url === pathToFileURL(resolve(process.argv[1] || "")).href) {
  const dir = process.argv[2];
  if (!dir) { console.error("usage: node tests/follow/check_changes.js <folder>"); process.exit(2); }
  const r = checkFolder(dir);
  for (const p of r.problems.slice(0, 40)) console.log(`  ${p}`);
  if (r.problems.length) {
    console.log(`FAIL: ${r.problems.length} problem(s) in ${r.files} file(s)`);
    process.exit(1);
  }
  console.log(`ok: ${r.files} file(s), ${r.nights} night(s), all to the format`);
}
