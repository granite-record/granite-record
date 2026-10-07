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

import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { checkCurrent, checkNight } from "../../workers/follow/changes.js";

export function checkFolder(dir) {
  const out = [];
  const files = readdirSync(dir).filter(f => f.endsWith(".json")).sort();
  const nights = files.filter(f => /^\d{4}-\d{2}-\d{2}\.json$/.test(f));
  if (!files.includes("current.json")) out.push("current.json: missing");
  if (!nights.length) out.push("no night's file at all");
  for (const f of files) {
    let obj;
    try { obj = JSON.parse(readFileSync(join(dir, f), "utf8")); }
    catch { out.push(`${f}: not JSON`); continue; }
    const r = f === "current.json" ? checkCurrent(obj)
      : nights.includes(f) ? checkNight(obj, f.slice(0, 10)) : null;
    if (!r) { out.push(`${f}: not a changes file's name`); continue; }
    for (const p of r.problems) out.push(`${f}: ${p}`);
    for (const n of r.notes) out.push(`${f}: ${n}`);
  }
  return { files: files.length, nights: nights.length, problems: out };
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
