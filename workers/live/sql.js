/*
 * The three statements the live Worker sends to the General Court's public
 * SQL database, the one function that writes a value into them, and the
 * readers that turn their rows into records. The live layer's design (26
 * October 2026), section 2.2, is what they are held to:
 *
 *   Q1  summary rows dated in a window, both chambers (RollCallSummary)
 *   Q2  the ballots of up to 20 roll calls (RollCallHistory, legislators)
 *   Q3  the docket's roll-call tally lines for a day, both chambers (Docket)
 *
 * and SELECT @@VERSION, sent only by the November test (test_mode.js).
 *
 * THE RULES, which preflight's _live_sql holds every statement here to:
 *   - one SELECT over the views above, with no ";", no comment and no "*";
 *   - every output column a CAST(... AS nvarchar(n)), or a date as
 *     CONVERT(nvarchar(19), x, 126), ISO 8601, so that tds.js reads one type;
 *   - every column it names is one db/_columns.json lists for its view;
 *   - a value enters a statement only through fill(), which writes each one
 *     with lit(): an integer the Worker made, a date as 'YYYYMMDD' (read the
 *     same under every DATEFORMAT and language), a chamber as 'H' or 'S'.
 *     TDS's SQL_BATCH has no parameters, and nothing a reader sends ever
 *     reaches here.
 *
 * Each statement is written with {NAME} where fill() puts a value. The
 * readers check what comes back has the statement's width and that each
 * field is what it should be; a row that is not throws SqlShapeError, whose
 * code "shape" the caller treats as a failed statement, never as data.
 */
import { BALLOT_CHAR } from "./live.gen.js";

export const MAX_ROLLCALLS = 20;

export const Q1 = `SELECT CAST(s.LegislativeBody AS nvarchar(1)), CAST(s.VoteSequenceNumber AS nvarchar(8)),
       ISNULL(CONVERT(nvarchar(19), s.VoteDate, 126), ''),
       CAST(ISNULL(s.CondensedBillNo, '') AS nvarchar(20)),
       CAST(ISNULL(s.Yeas, 0) AS nvarchar(8)), CAST(ISNULL(s.Nays, 0) AS nvarchar(8)),
       CAST(ISNULL(s.Present, 0) AS nvarchar(8)), CAST(ISNULL(s.Absent, 0) AS nvarchar(8)),
       CAST(ISNULL(s.Question_Motion, '') AS nvarchar(400)),
       ISNULL(CONVERT(nvarchar(19), s.DateModified, 126), ''),
       CAST(ISNULL(s.UserName, '') AS nvarchar(40))
FROM RollCallSummary s
WHERE s.SessionYear = {Y} AND s.VoteDate >= {FROM} AND s.VoteDate < {UNTIL}
ORDER BY s.LegislativeBody, s.VoteSequenceNumber`;

export const Q2 = `SELECT CAST(h.LegislativeBody AS nvarchar(1)), CAST(h.VoteSequenceNumber AS nvarchar(8)),
       ISNULL(CAST(l.PersonID AS nvarchar(12)), CAST(ISNULL(h.EmployeeNumber, '') AS nvarchar(12))),
       CAST(ISNULL(h.Vote, 0) AS nvarchar(4))
FROM RollCallHistory h LEFT JOIN legislators l ON l.Employeeno = h.EmployeeNumber
WHERE h.SessionYear = {Y}
  AND ({CHAMBERS})`;

// One chamber's roll calls in Q2; {CHAMBERS} is one of these, or two joined by OR.
export const Q2_CHAMBER = `(h.LegislativeBody = {BODY} AND h.VoteSequenceNumber IN ({SEQS}))`;

export const Q3 = `SELECT CAST(d.LegislativeBody AS nvarchar(1)), CAST(ISNULL(d.CondensedBillNo, '') AS nvarchar(20)),
       ISNULL(CONVERT(nvarchar(19), d.StatusDate, 126), ''),
       CAST(ISNULL(d.statusorder, 0) AS nvarchar(8)),
       CAST(CAST(d.Description AS nvarchar(max)) AS nvarchar(1000))
FROM Docket d
WHERE d.SessionYear = {Y} AND d.Description LIKE '%RC [0-9]%'
  AND (   (d.StatusDate >= {DAY} AND d.StatusDate < {NEXT})
       OR (d.StatusDate >= {SINCE} AND d.Description LIKE {MDY}))
ORDER BY d.LegislativeBody, d.CondensedBillNo, d.statusorder`;

export const VERSION = `SELECT @@VERSION`;

// How many columns each statement returns, which its reader checks.
export const WIDTH = { q1: 11, q2: 4, q3: 5, version: 1 };

export class SqlShapeError extends Error {
  constructor(message) { super(message); this.name = "SqlShapeError"; this.code = "shape"; }
}

// ---- writing a value ---------------------------------------------------------
const DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

function realDay(v) {
  const m = DAY.exec(typeof v === "string" ? v : "");
  if (!m) return null;
  const t = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return t.toISOString().slice(0, 10) === v ? m : null;
}

export function addDays(day, n) {
  if (!realDay(day)) throw new RangeError(`${day} is not a date`);
  const t = Date.UTC(+day.slice(0, 4), +day.slice(5, 7) - 1, +day.slice(8, 10)) + n * 86400000;
  return new Date(t).toISOString().slice(0, 10);
}

// The one function that writes a value into a statement.
export function lit(kind, v) {
  if (kind === "int") {
    if (!Number.isSafeInteger(v) || v < 0) throw new RangeError(`${String(v)} is not a whole number`);
    return String(v);
  }
  if (kind === "ints") {
    if (!Array.isArray(v) || !v.length) throw new RangeError("an empty list of numbers");
    return v.map(x => lit("int", x)).join(",");
  }
  if (kind === "day" || kind === "mdy") {
    const m = realDay(v);
    if (!m) throw new RangeError(`${String(v)} is not a date written YYYY-MM-DD`);
    return kind === "day" ? `'${m[1]}${m[2]}${m[3]}'` : `'%${m[2]}/${m[3]}/${m[1]}%'`;
  }
  if (kind === "body") {
    if (v !== "H" && v !== "S") throw new RangeError(`${String(v)} is not H or S`);
    return `'${v}'`;
  }
  throw new RangeError(`no literal of kind ${kind}`);
}

// A statement with each {NAME} written by lit(): values are {NAME: [kind, value]}.
export function fill(template, values) {
  const used = new Set();
  const out = template.replace(/\{([A-Z0-9]+)\}/g, (_, name) => {
    if (!Object.hasOwn(values, name)) throw new RangeError(`no value for {${name}}`);
    used.add(name);
    return lit(...values[name]);
  });
  const extra = Object.keys(values).filter(k => !used.has(k));
  if (extra.length) throw new RangeError(`no place for ${extra.join(", ")}`);
  return out;
}

// ---- the statements ------------------------------------------------------------
// Roll calls dated from `from` up to, not including, `until`.
export function q1({ year, from, until }) {
  return fill(Q1, { Y: ["int", year], FROM: ["day", from], UNTIL: ["day", until] });
}

// The ballots of `rollcalls`, [{body, seq}], at most MAX_ROLLCALLS of them.
export function q2({ year, rollcalls }) {
  const seqs = { H: new Set(), S: new Set() };
  for (const r of rollcalls || []) {
    if (!seqs[r?.body]) throw new RangeError(`${String(r?.body)} is not H or S`);
    seqs[r.body].add(r.seq);
  }
  const n = seqs.H.size + seqs.S.size;
  if (!n || n > MAX_ROLLCALLS) throw new RangeError(`${n} roll calls: one statement asks for 1 to ${MAX_ROLLCALLS}`);
  const chambers = ["H", "S"].filter(b => seqs[b].size)
    .map(b => fill(Q2_CHAMBER, { BODY: ["body", b], SEQS: ["ints", [...seqs[b]].sort((x, y) => x - y)] }))
    .join(" OR ");
  return fill(Q2.replace("{CHAMBERS}", chambers), { Y: ["int", year] });
}

// The docket's tally lines entered on `day`, or entered in the 21 days
// before it and carrying its date in their words (the Senate's floor lines,
// created days ahead and filled in during the sitting).
export function q3({ year, day }) {
  return fill(Q3, { Y: ["int", year], DAY: ["day", day], NEXT: ["day", addDays(day, 1)],
                    SINCE: ["day", addDays(day, -21)], MDY: ["mdy", day] });
}

// ---- reading what comes back -----------------------------------------------------
function rowsOf(result, width, what) {
  if (!result || !Array.isArray(result.rows) || result.columns?.length !== width) {
    throw new SqlShapeError(`${what} came back ${result?.columns?.length ?? "no"} columns wide, not ${width}`);
  }
  return result.rows;
}

function shaped(what, field, value, test) {
  if (!test) throw new SqlShapeError(`${what}: ${field} is ${JSON.stringify(value)}`);
  return value;
}

const whole = (what, field, v) => Number(shaped(what, field, v, typeof v === "string" && /^\d{1,9}$/.test(v)));
const chamber = (what, v) => shaped(what, "the chamber", v, v === "H" || v === "S");

// A date and time as CONVERT(..., 126) writes it, cut to the second; a date
// alone stands at midnight; "" or NULL is null.
function stamp(what, field, v) {
  if (v === "" || v === null) return null;
  if (typeof v === "string" && realDay(v)) return `${v}T00:00:00`;
  return shaped(what, field, v, typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(v)
                                && realDay(v.slice(0, 10)));
}

// Q1: [{id, year, body, seq, vote_date, bill_as_recorded, yeas, nays, present,
// absent, question, modified, user}], dates in New Hampshire's time as the
// database keeps them.
export function readSummary(result, year) {
  return rowsOf(result, WIDTH.q1, "Q1").map(r => {
    const what = `Q1 row ${JSON.stringify(r).slice(0, 80)}`;
    const body = chamber(what, r[0]);
    const seq = whole(what, "the sequence number", r[1]);
    return {
      id: `${year}-${body}-${seq}`, year, body, seq,
      vote_date: stamp(what, "VoteDate", r[2]),
      bill_as_recorded: r[3] || null,
      yeas: whole(what, "Yeas", r[4]), nays: whole(what, "Nays", r[5]),
      present: whole(what, "Present", r[6]), absent: whole(what, "Absent", r[7]),
      question: r[8] ?? "",
      modified: stamp(what, "DateModified", r[9]),
      user: r[10] ?? "",
    };
  });
}

// Q2: [{body, seq, member, vote}], the vote as the live file's character.
export function readBallots(result) {
  return rowsOf(result, WIDTH.q2, "Q2").map(r => {
    const what = `Q2 row ${JSON.stringify(r)}`;
    return {
      body: chamber(what, r[0]),
      seq: whole(what, "the sequence number", r[1]),
      member: shaped(what, "the member", r[2], typeof r[2] === "string" && /^[A-Za-z0-9-]{1,12}$/.test(r[2])),
      vote: BALLOT_CHAR[shaped(what, "the vote", r[3], Object.hasOwn(BALLOT_CHAR, r[3] ?? ""))],
    };
  });
}

// Q3: [{body, bill_as_recorded, entered, order, line}].
export function readDocket(result) {
  return rowsOf(result, WIDTH.q3, "Q3").map(r => {
    const what = `Q3 row ${JSON.stringify(r).slice(0, 80)}`;
    return {
      body: chamber(what, r[0]),
      bill_as_recorded: r[1] || null,
      entered: stamp(what, "StatusDate", r[2]),
      order: whole(what, "statusorder", r[3]),
      line: r[4] ?? "",
    };
  });
}

export function readVersion(result) {
  const [r] = rowsOf(result, WIDTH.version, "SELECT @@VERSION");
  return shaped("SELECT @@VERSION", "the version", r?.[0], typeof r?.[0] === "string");
}
