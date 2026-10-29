// The live layer's design, section 7.3: measured before Q3 is relied on, on
// the laptop with the kit (no network; Docket.txt is the kit's, the roll
// calls are records/rollcalls/ in git).
//
//   node tests/live/measure_docket.mjs <the kit's Docket.txt> [2025 2026]
//
// Q3 takes a tally line if it was entered on the sitting day, or entered in
// the 21 days before and carries the sitting's date in its words. Each tally
// line is matched to its roll call by chamber, bill, yeas and nays, and two
// shares are counted:
//   House  RC n-n lines entered on their roll call's day
//   Senate RC nY-nN lines whose words carry their roll call's day as MM/DD/YYYY
// Either under 95% means Q3's text test is widened (lines entered in the
// last 21 days, filtered in JavaScript), as the design says.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { recordTime } from "./compare_test.mjs";

export const ENOUGH = 0.95;
const HOUSE = /\bRC (\d+)-(\d+)\b/, SENATE = /\bRC (\d+)Y-(\d+)N\b/;

const rows = text => text.replace(/^﻿/, "").split(/\r?\n/).filter(l => l.trim()).map(l => l.split("|"));
const mdy = day => `${day.slice(5, 7)}/${day.slice(8, 10)}/${day.slice(0, 4)}`;
const bill = b => String(b || "").replace(/\s+/g, "").toUpperCase();

// {H: {lines, matched, onDay}, S: {lines, matched, dated}} for the years.
export function measure(docketText, summaries, years) {
  const calls = new Map();       // "H|2026|HB2|190|171" -> [days]
  for (const f of summaries) {
    if (!years.includes(f[0]) || !f[4]) continue;
    const k = `${f[1]}|${f[0]}|${bill(f[4])}|${Number(f[5])}|${Number(f[6])}`;
    if (!calls.has(k)) calls.set(k, []);
    calls.get(k).push(recordTime(f[3]).slice(0, 10));
  }
  const out = { H: { lines: 0, matched: 0, onDay: 0 }, S: { lines: 0, matched: 0, dated: 0 } };
  for (const f of rows(docketText)) {
    const [y, , entered, b, body, words] = f;
    if (!years.includes(y) || (body !== "H" && body !== "S")) continue;
    const m = (body === "S" ? SENATE : HOUSE).exec(words || "");
    if (!m) continue;
    const o = out[body];
    o.lines++;
    const days = calls.get(`${body}|${y}|${bill(b)}|${Number(m[1])}|${Number(m[2])}`);
    if (!days) continue;
    o.matched++;
    const on = (recordTime(entered) || "").slice(0, 10);
    if (body === "H" && days.includes(on)) o.onDay++;
    if (body === "S" && days.some(d => words.includes(mdy(d)))) o.dated++;
  }
  return out;
}

export function report(m) {
  const share = (n, d) => (d ? n / d : NaN);
  const h = share(m.H.onDay, m.H.matched), s = share(m.S.dated, m.S.matched);
  const pct = x => (Number.isNaN(x) ? "no lines" : `${(100 * x).toFixed(1)}%`);
  const said = [
    `House: ${m.H.lines} RC lines, ${m.H.matched} matched to a roll call, ${pct(h)} entered on its day`,
    `Senate: ${m.S.lines} RC lines, ${m.S.matched} matched to a roll call, ${pct(s)} carrying its day as MM/DD/YYYY`,
  ];
  const ok = h >= ENOUGH && s >= ENOUGH;
  said.push(ok ? "Q3's filter stands as designed"
               : "under 95%: widen Q3's text test to lines entered in the last 21 days, filtered in JavaScript (design 7.3)");
  return { ok, said };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [file, ...ys] = process.argv.slice(2);
  if (!file) {
    console.error("usage: node tests/live/measure_docket.mjs <Docket.txt> [years, default 2025 2026]");
    process.exit(2);
  }
  const years = ys.length ? ys : ["2025", "2026"];
  const summaries = years.flatMap(y => rows(readFileSync(new URL(`../../records/rollcalls/RollCallSummary_${y}.txt`,
                                                                  import.meta.url), "utf8")));
  const r = report(measure(readFileSync(file, "utf8"), summaries, years));
  for (const l of r.said) console.log(l);
  process.exit(r.ok ? 0 : 1);
}
