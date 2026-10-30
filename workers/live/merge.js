/*
 * The live votes file, votes/<date>.json, and how one read is merged into it
 * (the live layer's design, sections 2.4, 2.5 and 5). Pure functions: nothing
 * here reads the bucket or the database.
 *
 * ONE FILE A SITTING DAY, filed under each roll call's own VoteDate, the date
 * the database keeps in New Hampshire's time. The Senate's VoteDate is
 * midnight of the sitting, so a Senate save the next morning updates the
 * sitting's file.
 *
 * NEVER DROP WHAT WAS SHOWN. A roll call already in the file stays. Its
 * fields are brought up to date in place, and first_seen is set once and never
 * moves. A read whose window covered the file's date and did not list a roll
 * call counts a miss; at MISSES_TO_NOTE in a row the roll call gains a note,
 * and is still shown. This is CLAUDE.md's "a writer of a derived file, run on
 * a subset, destroys the rest", applied to one day.
 *
 * BALLOTS are one character a member, aligned to members[body], a list of ids
 * that only grows within a file: Y Yea, N Nay, E excused, X not excused, P
 * presiding, "." no vote recorded (sql.js reads them through live.gen.js). A
 * roll call's ballots are replaced whole when Q2 reads them again. A set is
 * complete when its Y and N counts equal the summary's yeas and nays.
 *
 * THE DOCKET'S TALLY LINES. The House writes "MA RC 190-171", the Senate
 * "Ought to Pass, RC 16Y-8N, MA; 01/29/2026". "RC" counts only before digits
 * (the key's bare "RC" is Regular Calendar). The outcome is the abbreviation
 * beside the tally, read through live.gen.js's DOCKET_OUTCOME, the General
 * Court's own key; a line with none keeps its words and outcome null. A line
 * is matched to its roll call by chamber, bill, yeas and nays, pairing
 * statusorder with sequence order when one bill has two equal tallies. A line
 * with no roll call yet stands as a tally, and is attached when its roll call
 * arrives. THE WORKER NEVER WORKS OUT WHETHER A MOTION CARRIED: a threshold
 * or a two-thirds vote is the night's (vote_passage.py).
 */
import { BILL_NUMBER, DOCKET_OUTCOME } from "./live.gen.js";
import { nhToUtc, termOf } from "./test_mode.js";

export const MISSES_TO_NOTE = 3;
export const SOURCE = "The General Court's public SQL database (RollCallSummary, RollCallHistory, Docket)";
export const NOTES = Object.freeze({
  record: "The night's record replaces this file each morning; a roll call the record holds wins.",
  excusals: "Excused and not excused settle in the days after a vote.",
  senate: "Senate names follow once the Senate enters them, usually that afternoon or the next day.",
  reading: "read_at and next_read_by describe this reader alone, and say nothing about any stream.",
});

export const votesKey = date => `votes/${date}.json`;

export function emptyFile(date) {
  return {
    api: 1, kind: "session.votes", date, provisional: true,
    read_at: null, next_read_by: null,
    status: { state: "reading", problem: null, since: null },
    source: SOURCE,
    record: { H: `/session/H/${date}.json`, S: `/session/S/${date}.json` },
    members: { H: [], S: [] },
    rollcalls: [], tallies: [],
    notes: { ...NOTES },
  };
}

// The date a summary row is filed under: its VoteDate's own date, which the
// database keeps in New Hampshire's time.
export const dayOfRow = r => (r.vote_date ? r.vote_date.slice(0, 10) : null);

const billKey = b => String(b || "").replace(/\s+/g, "").toUpperCase();

// The bill a roll call's bill field names, as the record reads it
// (rollcall_parser.bill_number, its patterns through live.gen.js): spaces
// out, upper case, the flags off, HCACR read as CACR; "" where the field
// names no bill ("SUSPRULE", "RULE 1-2", "HRULE64"). The file's `bill` is
// then null, and bill_as_recorded keeps the words.
const BILL_NO = new RegExp(BILL_NUMBER.pattern, "i");
const FLAGS_OFF = new RegExp(BILL_NUMBER.flags_off);
export function billNumber(raw) {
  const b = billKey(raw).replace(FLAGS_OFF, "").replace(/^HCACR(?=\d)/, "CACR");
  return BILL_NO.test(b) ? b : "";
}
const billOf = (raw, year) => (billNumber(raw) ? `${termOf(year)}/${billNumber(raw)}` : null);

// ---- the docket ---------------------------------------------------------------
const HOUSE_RC = /\bRC (\d+)-(\d+)\b/;
const SENATE_RC = /\bRC (\d+)Y-(\d+)N\b/;
const MDY = /\b(\d{2})\/(\d{2})\/(\d{4})\b/;

// {yeas, nays, abbrev, outcome, day} of a tally line, or null when it holds no
// roll-call tally. `day` is the date the line writes, or null.
export function parseTally(line, body) {
  const text = String(line || "");
  const m = (body === "S" ? SENATE_RC : HOUSE_RC).exec(text) || HOUSE_RC.exec(text) || SENATE_RC.exec(text);
  if (!m) return null;
  // The outcome is the key's abbreviation nearest the tally, within the
  // tally's own clause (between semicolons): "Ought to Pass, RC 16Y-8N, MA;"
  // or "OTPA: MA RC 171-143 ...", never a word further along the line.
  const from = text.lastIndexOf(";", m.index) + 1;
  const end = text.indexOf(";", m.index);
  const clause = text.slice(from, end < 0 ? text.length : end);
  let abbrev = null, best = Infinity;
  for (const a of clause.matchAll(/\b([A-Z]{2,4})\b/g)) {
    if (!Object.hasOwn(DOCKET_OUTCOME, a[1])) continue;
    const d = Math.abs(from + a.index - m.index);
    if (d < best) { best = d; abbrev = a[1]; }
  }
  // The line's date is the last it writes: "Reconsider vote of 01/22/2027,
  // RC 12Y-11N, MF; 01/29/2027" is the 29th's.
  const dates = [...text.matchAll(new RegExp(MDY.source, "g"))];
  const d = dates.at(-1);
  return { yeas: Number(m[1]), nays: Number(m[2]), abbrev, outcome: abbrev ? DOCKET_OUTCOME[abbrev] : null,
           day: d ? `${d[3]}-${d[1]}-${d[2]}` : null, days: dates.map(x => `${x[3]}-${x[1]}-${x[2]}`) };
}

// The date a docket line belongs to: `today` when the line writes it (Q3
// took it for that), else the last date it writes, else the day it was
// entered (session_days dates a row "by the one the row writes").
export function dayOfLine(l, today = null) {
  const t = parseTally(l.line, l.body);
  if (t && today && t.days.includes(today)) return today;
  return (t && t.day) || (l.entered ? l.entered.slice(0, 10) : null);
}

// ---- the merge ----------------------------------------------------------------
// One read into one day's file.
//   prev      the file as it stands, or null
//   rows      Q1's records filed under this date (readSummary's shape)
//   ballots   Map id -> Map member -> character, for the roll calls Q2 read
//   lines     Q3's records belonging to this date (readDocket's shape)
//   at        this read's time, ISO
//   covered   whether this read's window covered the date (a miss counts
//             only then)
//   misses    {id: count} as state.json keeps them; returned updated
//   saves     {id: DateModified} as state.json keeps them; returned updated
// Returns {file, misses, saves, changed: [ids new, or whose tally or save
// changed]}.
export function merge(prev, { date, rows = [], ballots = new Map(), lines = [], at, covered = false, misses = {},
                              saves = {} }) {
  const f = prev && prev.kind === "session.votes" && prev.date === date ? structuredClone(prev) : emptyFile(date);
  f.members = { H: [...(f.members?.H || [])], S: [...(f.members?.S || [])] };
  const byId = new Map(f.rollcalls.map(r => [r.id, r]));
  const out = { ...misses };
  const saved = { ...saves };
  const changed = [];
  const listed = new Set();

  for (const r of rows) {
    listed.add(r.id);
    const old = byId.get(r.id);
    if (!old || old.yeas !== r.yeas || old.nays !== r.nays || saved[r.id] !== r.modified) changed.push(r.id);
    saved[r.id] = r.modified;
    const rc = old || { id: r.id, first_seen: at, ballots: "", ballots_complete: false, docket: null, note: null };
    Object.assign(rc, {
      body: r.body, seq: r.seq,
      bill: billOf(r.bill_as_recorded, r.year),
      bill_as_recorded: r.bill_as_recorded, question: r.question,
      taken: r.body === "H" ? nhToUtc(r.vote_date) : null,
      saved: r.body === "S" ? nhToUtc(r.modified) : null,
      keyed_by: r.user === "VOTE SYSTEM" ? "voting system" : "clerk",
      yeas: r.yeas, nays: r.nays, present: r.present, absent: r.absent,
      note: null,
    });
    delete out[r.id];
    byId.set(r.id, rc);
  }

  // Ballots: the members only grow; a set read again replaces the old.
  for (const [id, got] of ballots) {
    const rc = byId.get(id);
    if (!rc) continue;
    for (const m of got.keys()) if (!f.members[rc.body].includes(m)) f.members[rc.body].push(m);
    rc.read = [...got.entries()];
  }
  for (const rc of byId.values()) {
    const got = new Map(rc.read || []);
    if (!ballots.has(rc.id) && rc.ballots) {
      // Not read again: the string as it was, padded to the members now known.
      const ids = f.members[rc.body];
      rc.ballots = rc.ballots.padEnd(ids.length, ".");
    } else if (got.size) {
      rc.ballots = f.members[rc.body].map(m => got.get(m) || ".").join("");
    }
    delete rc.read;
    const count = c => [...(rc.ballots || "")].filter(x => x === c).length;
    // Complete: Y and N agree with the tally, and something was recorded (a
    // 0-0 set of nothing but "." is not yet keyed).
    rc.ballots_complete = Boolean(rc.ballots) && count("Y") === rc.yeas && count("N") === rc.nays
      && (rc.yeas + rc.nays > 0 || /[^.]/.test(rc.ballots));
  }

  // Misses: a roll call the window covered and did not list.
  if (covered) {
    for (const rc of byId.values()) {
      if (listed.has(rc.id)) continue;
      const n = (out[rc.id] || 0) + 1;
      out[rc.id] = n;
      if (n >= MISSES_TO_NOTE && !rc.note) {
        rc.note = `no longer listed by the database at ${clockOf(at)}; the record will settle it`;
      }
    }
  }

  // The docket: each line kept by chamber, bill and order, first_seen once.
  const tally = new Map((f.tallies || []).map(t => [`${t.body}|${billKey(t.bill_as_recorded)}|${t.order}`, t]));
  for (const l of lines) {
    const p = parseTally(l.line, l.body);
    if (!p) continue;
    const k = `${l.body}|${billKey(l.bill_as_recorded)}|${l.order}`;
    const old = tally.get(k);
    tally.set(k, {
      body: l.body,
      bill: billOf(l.bill_as_recorded, Number(date.slice(0, 4))),
      bill_as_recorded: l.bill_as_recorded, order: l.order, entered: nhToUtc(l.entered), line: l.line,
      yeas: p.yeas, nays: p.nays, abbrev: p.abbrev, outcome: p.outcome,
      first_seen: old ? old.first_seen : at, rollcall: null,
    });
  }
  f.tallies = [...tally.values()].sort((a, b) =>
    a.body < b.body ? -1 : a.body > b.body ? 1 : billKey(a.bill_as_recorded) < billKey(b.bill_as_recorded) ? -1
      : billKey(a.bill_as_recorded) > billKey(b.bill_as_recorded) ? 1 : a.order - b.order);
  f.rollcalls = [...byId.values()].sort((a, b) => (a.body < b.body ? -1 : a.body > b.body ? 1 : a.seq - b.seq));
  attach(f);
  return { file: f, misses: out, saves: saved, changed };
}

// Each roll call's docket line: same chamber, bill, yeas and nays; equal
// tallies on one bill paired in order, statusorder against sequence.
export function attach(f) {
  const groups = new Map();
  const key = x => `${x.body}|${billKey(x.bill_as_recorded)}|${x.yeas}|${x.nays}`;
  for (const t of f.tallies) {
    t.rollcall = null;
    if (!groups.has(key(t))) groups.set(key(t), { t: [], r: [] });
    groups.get(key(t)).t.push(t);
  }
  for (const rc of f.rollcalls) {
    rc.docket = null;
    if (rc.bill_as_recorded && groups.has(key(rc))) groups.get(key(rc)).r.push(rc);
  }
  for (const { t, r } of groups.values()) {
    // Paired only when it is certain: as many lines as roll calls. Two equal
    // tallies on one bill with one roll call saved so far (the Senate saves
    // out of order) wait for the other, rather than guess which it is.
    if (t.length !== r.length) continue;
    t.sort((a, b) => a.order - b.order);
    r.sort((a, b) => a.seq - b.seq);
    for (let i = 0; i < t.length; i++) {
      t[i].rollcall = r[i].id;
      r[i].docket = { line: t[i].line, abbrev: t[i].abbrev, outcome: t[i].outcome };
    }
  }
}

// "14:12" in New Hampshire, for a note.
function clockOf(iso) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York", hourCycle: "h23", hour: "2-digit", minute: "2-digit",
  }).formatToParts(new Date(iso)).map(x => [x.type, x.value]));
  return `${String(Number(p.hour) % 24).padStart(2, "0")}:${p.minute}`;
}
