/*
 * Reading the changes files the build publishes under /changes/, and holding
 * them to CHANGES_FORMAT.md. The sender reads the nights and current.json;
 * sign-up, confirmation and the manage page read current.json, to know what
 * can be followed tonight and what each thing is called.
 *
 * A file that breaks the format at its head (format, date, built,
 * sitting_term, new_by, the map it carries) is refused whole. An entry that
 * breaks it is dropped or mended and noted, so one bad item cannot cost a
 * reader the rest of their email; tests/follow/check_changes.js fails on any
 * note at all, which is how the build is held to the contract.
 */

import { parseKey, oneLine } from "./common.js";

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const STAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const TERM = /^\d{4}-\d{4}$/;
const TIME = /^\d{2}:\d{2}$/;
const HOW = /^[a-z][a-z-]{0,30}$/;
const PATH = /^\/(?!\/)[A-Za-z0-9\-._~/?=&%+]*$/;
export const ITEM_KINDS = new Set(["action", "hearing", "scheduled", "exec", "vote",
  "report", "sponsor", "sitting", "study"]);
const BASES = new Set(["first-seen", "record-date"]);

const isObj = o => !!o && typeof o === "object" && !Array.isArray(o);

function checkHead(obj, problems) {
  if (!isObj(obj)) { problems.push("the file is not a JSON object"); return; }
  if (obj.format !== 1) problems.push("format is not 1");
  if (!DAY.test(obj.date ?? "")) problems.push("date is not YYYY-MM-DD");
  if (!STAMP.test(obj.built ?? "")) problems.push("built is not YYYY-MM-DDTHH:MM:SSZ");
  if (!TERM.test(obj.sitting_term ?? "")) problems.push("sitting_term is not YYYY-YYYY");
  if (!BASES.has(obj.new_by)) problems.push("new_by is neither first-seen nor record-date");
}

// Plain text of at most max characters; longer is clipped and noted.
function text(v, max, where, notes, required = true) {
  if (v === undefined || v === null || v === "") {
    if (required) notes.push(`${where}: missing`);
    return required ? null : "";
  }
  if (typeof v !== "string") { notes.push(`${where}: not text`); return required ? null : ""; }
  if (v.length > max) notes.push(`${where}: longer than ${max}`);
  const t = oneLine(v, max);
  if (!t && required) { notes.push(`${where}: empty`); return null; }
  return t;
}

function path(v, where, notes) {
  if (v === undefined || v === null || v === "") return "";
  if (typeof v === "string" && PATH.test(v)) return v;
  notes.push(`${where}: url is not a path on the site`);
  return "";
}

// ---- current.json ----------------------------------------------------------------
export function checkCurrent(obj) {
  const problems = [], notes = [];
  checkHead(obj, problems);
  if (isObj(obj) && !isObj(obj.followable)) problems.push("followable is not an object");
  if (isObj(obj) && obj.upcoming !== undefined && !isObj(obj.upcoming))
    problems.push("upcoming is not an object");
  if (problems.length) return { value: null, problems, notes };

  const followable = new Map();
  for (const [k, v] of Object.entries(obj.followable)) {
    if (!parseKey(k)) { notes.push(`followable ${k.slice(0, 40)}: not a record key`); continue; }
    if (!isObj(v)) { notes.push(`followable ${k}: not an object`); continue; }
    const label = text(v.label, 120, `followable ${k} label`, notes);
    if (!label) continue;
    followable.set(k, { label,
      title: text(v.title, 300, `followable ${k} title`, notes, false),
      url: path(v.url, `followable ${k}`, notes) });
  }
  const upcoming = new Map();
  for (const [k, list] of Object.entries(obj.upcoming || {})) {
    if (!parseKey(k)) { notes.push(`upcoming ${k.slice(0, 40)}: not a record key`); continue; }
    if (!Array.isArray(list)) { notes.push(`upcoming ${k}: not a list`); continue; }
    const rows = [];
    for (const [i, u] of list.entries()) {
      const w = `upcoming ${k}[${i}]`;
      if (!isObj(u) || !DAY.test(u.date ?? "")) { notes.push(`${w}: no date`); continue; }
      const what = text(u.what, 120, `${w} what`, notes);
      if (!what) continue;
      if (u.time !== undefined && u.time !== "" && !TIME.test(u.time)) notes.push(`${w}: time is not HH:MM`);
      rows.push({ date: u.date, what, time: TIME.test(u.time ?? "") ? u.time : "",
        committee: text(u.committee, 120, `${w} committee`, notes, false),
        venue: text(u.venue, 120, `${w} venue`, notes, false) });
    }
    rows.sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
    if (rows.length) upcoming.set(k, rows);
  }
  return { value: { date: obj.date, built: obj.built, sitting_term: obj.sitting_term,
                    new_by: obj.new_by, followable, upcoming }, problems, notes };
}

// ---- one night ---------------------------------------------------------------------
function checkItem(it, where, firstSeen, topic, notes) {
  if (!isObj(it)) { notes.push(`${where}: not an object`); return null; }
  const guid = typeof it.guid === "string" && it.guid && it.guid.length <= 300 ? it.guid : null;
  if (!guid) { notes.push(`${where}: no usable guid`); return null; }
  if (!DAY.test(it.date ?? "")) { notes.push(`${where}: date is not YYYY-MM-DD`); return null; }
  const summary = text(it.summary, 300, `${where} summary`, notes);
  if (!summary) return null;
  let kind = it.kind;
  if (typeof kind !== "string" || !kind) { notes.push(`${where}: no kind`); kind = "action"; }
  else if (!ITEM_KINDS.has(kind)) kind = "action";       // forward compatible, not a breach
  let term = "";
  if (it.term !== undefined) {
    if (TERM.test(it.term)) term = it.term;
    else notes.push(`${where}: term is not YYYY-YYYY`);
  }
  if (topic && !term) { notes.push(`${where}: a topic's item has no term`); return null; }
  let seen = "";
  if (it.seen !== undefined) {
    if (STAMP.test(it.seen)) seen = it.seen;
    else notes.push(`${where}: seen is not a UTC timestamp`);
  }
  if (firstSeen && !seen) notes.push(`${where}: no seen, under first-seen`);
  return { guid, date: it.date, kind, summary, url: path(it.url, where, notes), term, seen };
}

export function checkNight(obj, expectDate) {
  const problems = [], notes = [];
  checkHead(obj, problems);
  if (isObj(obj) && !isObj(obj.refs)) problems.push("refs is not an object");
  if (isObj(obj) && expectDate && obj.date !== expectDate)
    problems.push(`date ${String(obj.date).slice(0, 10)} is not the file's own ${expectDate}`);
  if (problems.length) return { value: null, problems, notes };

  const firstSeen = obj.new_by === "first-seen";
  const refs = new Map();
  for (const [k, r] of Object.entries(obj.refs)) {
    const key = parseKey(k);
    if (!key) { notes.push(`refs ${k.slice(0, 40)}: not a record key`); continue; }
    if (!isObj(r)) { notes.push(`refs ${k}: not an object`); continue; }
    const out = { items: [], study: null, ended: null };
    if (r.items !== undefined && !Array.isArray(r.items)) notes.push(`refs ${k} items: not a list`);
    for (const [i, it] of (Array.isArray(r.items) ? r.items : []).entries()) {
      const v = checkItem(it, `refs ${k} items[${i}]`, firstSeen, key.kind === "topic", notes);
      if (v) out.items.push(v);
    }
    if (r.study !== undefined && r.study !== null) {
      const s = r.study, w = `refs ${k} study`;
      if (!isObj(s) || ![true, false, null].includes(s.recommends))
        notes.push(`${w}: recommends is not true, false or null`);
      else {
        const v = checkItem({ ...s, kind: "study" }, w, firstSeen, false, notes);
        if (v) out.study = { ...v, recommends: s.recommends };
      }
    }
    if (r.ended !== undefined && r.ended !== null) {
      const e = r.ended, w = `refs ${k} ended`;
      if (!isObj(e) || !HOW.test(e.how ?? "")) notes.push(`${w}: how is not a word`);
      if (isObj(e)) {
        out.ended = {
          how: HOW.test(e.how ?? "") ? e.how : "ended",
          summary: text(e.summary, 300, `${w} summary`, notes, false),
          date: DAY.test(e.date ?? "") ? e.date : obj.date,
          guid: typeof e.guid === "string" ? e.guid.slice(0, 300) : "",
        };
        if (!DAY.test(e.date ?? "")) notes.push(`${w}: date is not YYYY-MM-DD`);
      }
    }
    if (out.items.length || out.study || out.ended) refs.set(k, out);
  }
  return { value: { date: obj.date, built: obj.built, sitting_term: obj.sitting_term,
                    new_by: obj.new_by, refs }, problems, notes };
}

// ---- fetching ------------------------------------------------------------------------
// get(path) is the caller's way to the site: env.ASSETS in a Pages Function,
// the public site from the sender. Answers { value } or { missing } or { bad },
// and how many entries were dropped or mended, for the log.
async function read(get, path, check) {
  let res;
  try { res = await get(path); } catch { return { bad: true, why: "fetch" }; }
  if (res.status === 404) return { missing: true };
  if (!res.ok) return { bad: true, why: "status" };
  let obj;
  try { obj = await res.json(); } catch { return { bad: true, why: "json" }; }
  const r = check(obj);
  return r.value ? { value: r.value, notes: r.notes.length } : { bad: true, why: "format" };
}

export const readCurrent = get => read(get, "/changes/current.json", checkCurrent);
export const readNight = (get, date) =>
  read(get, `/changes/${date}.json`, o => checkNight(o, date));
