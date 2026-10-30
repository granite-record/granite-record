// The fake SQL Server's answers from the record: Q1 and Q2 from
// records/rollcalls/ in git, Q3 from a few docket lines in the recorded forms,
// each filtered by the literals the statement carries. sql.test.js and
// wire.test.js both answer from here.
import { readFileSync } from "node:fs";
import { VERSION } from "../../workers/live/sql.js";
import { VOTE_WORD } from "../../workers/live/live.gen.js";
import { text } from "./fake_tds.js";
import { recordTime } from "./compare_test.mjs";

const RECORDS = new URL("../../records/rollcalls/", import.meta.url);
const fields = name => readFileSync(new URL(name, RECORDS), "utf8").replace(/^﻿/, "").split(/\r?\n/)
  .filter(Boolean).map(l => l.split("|"));
const YEARS = new Map();
// A session year's two files, read once.
export function year(y) {
  if (!YEARS.has(y)) {
    // A year the record does not hold yet (2027, say) is a database with no roll calls in it.
    const read = name => { try { return fields(name); } catch (e) { if (e.code === "ENOENT") return []; throw e; } };
    YEARS.set(y, { summary: read(`RollCallSummary_${y}.txt`), history: read(`RollCallHistory_${y}.txt`) });
  }
  return YEARS.get(y);
}
export const SUMMARY = year("2026").summary;
export const HISTORY = year("2026").history;
export const CODE = Object.fromEntries(Object.entries(VOTE_WORD).map(([code, word]) => [word, code]));
const ymd = s => `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;

// Docket lines in the recorded forms, two that Q3 must take and three it must not.
export const DOCKET = [
  ["H", "HB1376", "2026-03-11T09:32:51", "12", "OTPA: MA RC 171-143 03/11/2026 HJ 8 P. 20", true],
  ["S", "SB501", "2026-03-01T10:00:00", "7", "Ought to Pass, RC 16Y-8N, MA; 03/11/2026", true],
  ["S", "SB502", "2026-02-17T10:00:00", "3", "Ought to Pass, RC 15Y-9N, MA; 03/11/2026", false],
  ["H", "HB1378", "2026-03-10T15:00:00", "9", "OTP: MA RC 175-149 03/10/2026", false],
  ["H", "HB1400", "2026-03-11T11:00:00", "4", "Special Order to RC", false],
];

// The fake's answers: the record for Q1 and Q2, the lines above for Q3, each
// filtered by the literals the statement carries.
// over: version, q1, q3 (answers in place of the record's); docket (lines
// in place of DOCKET); released(summaryFields) -> whether the database holds
// that roll call yet, for a replay on a clock (its ballots go with it).
export function fromRecords(over = {}) {
  const shown = over.released || (() => true);
  return (sql) => {
    if (sql === VERSION) {
      return over.version || { columns: text(""), rows: [["Microsoft SQL Server 2019 (RTM) - 15.0.2000.5 (X64) (a fake)"]] };
    }
    let m = /FROM RollCallSummary s\nWHERE s\.SessionYear = (\d+) AND s\.VoteDate >= '(\d{8})' AND s\.VoteDate < '(\d{8})'\n/.exec(sql);
    if (m) {
      if (over.q1) return over.q1;
      const [, y, from, until] = m;
      const rows = year(y).summary.filter(f => f[0] === y && shown(f) && recordTime(f[3]).slice(0, 10) >= ymd(from)
                                  && recordTime(f[3]).slice(0, 10) < ymd(until))
        .map(f => [f[1], f[2], recordTime(f[3]), f[4], f[5], f[6], f[7], f[8], f[11], recordTime(f[14]) || "",
                   f[1] === "H" ? "VOTE SYSTEM" : "senclerk"]);
      return { columns: text(...Array(11).fill("")), rows };
    }
    m = /FROM RollCallHistory h LEFT JOIN legislators l ON l\.Employeeno = h\.EmployeeNumber\nWHERE h\.SessionYear = (\d+)\n  AND \((.*)\)$/s.exec(sql);
    if (m) {
      const asked = new Set();
      for (const c of m[2].matchAll(/\(h\.LegislativeBody = '([HS])' AND h\.VoteSequenceNumber IN \(([\d,]+)\)\)/g)) {
        for (const s of c[2].split(",")) asked.add(`${c[1]}-${s}`);
      }
      const out = new Set(year(m[1]).summary.filter(f => f[0] === m[1] && shown(f)).map(f => `${f[1]}-${f[2]}`));
      const rows = year(m[1]).history.filter(f => f[0] === m[1] && asked.has(`${f[1]}-${f[2]}`)
                                                 && out.has(`${f[1]}-${f[2]}`))
        .map(f => [f[1], f[2], f[4] || f[3], CODE[f[6]]]);
      return { columns: text("", "", "", ""), rows };
    }
    m = /WHERE d\.SessionYear = (\d+) AND d\.Description LIKE '%RC \[0-9\]%'\n  AND \(   \(d\.StatusDate >= '(\d{8})' AND d\.StatusDate < '(\d{8})'\)\n       OR \(d\.StatusDate >= '(\d{8})' AND d\.Description LIKE '%(\d\d\/\d\d\/\d{4})%'\)\)/.exec(sql);
    if (m) {
      if (over.q3) return over.q3;
      const [, , day, next, since, mdy] = m;
      const lineShown = over.lineShown || (() => true);
      const rows = (over.docket || DOCKET).filter(([, , at, , line]) => /RC [0-9]/.test(line) && lineShown(at)
          && ((at.slice(0, 10) >= ymd(day) && at.slice(0, 10) < ymd(next)) || (at.slice(0, 10) >= ymd(since) && line.includes(mdy))))
        .map(([b, bill, at, order, line]) => [b, bill, at, order, line]);
      return { columns: text("", "", "", "", ""), rows };
    }
    return { error: { number: 102, message: "Incorrect syntax: the fake knows the live Worker's statements alone" } };
  };
}

