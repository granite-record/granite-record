// sender.js: when it sends (8:00 New Hampshire time daily, Saturday 8:00
// weekly, across both daylight-saving changes), what it says (the week's
// votes and executive sessions, hearings coming up, an interim study's
// recommendation, a bill's ending), and what it keeps (counts).

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { hashToken } from "../../workers/follow/address.js";
import { digestEmail } from "../../workers/follow/mail.js";
import { due, nhClock, run } from "../../workers/follow/sender.js";
import { leaks, loadFixtures, makeWorld, SITE, tokensIn } from "./fakes.js";
import { handlers, view } from "./flows.js";
import { followKeys, insertSubscriber } from "./rows.js";

const FX = loadFixtures();
const CURRENT = FX.get("/changes/current.json");

// The site as it stood on a morning: the nights up to that date, and a
// current.json that still lists HB 9902 until it ended on the 7th.
function siteAsOf(w, date, { extra = {} } = {}) {
  w.net.site.clear();
  for (const [p, v] of FX) {
    const m = /\/(\d{4}-\d{2}-\d{2})\.json$/.exec(p);
    if (m && m[1] <= date) w.net.site.set(p, structuredClone(v));
  }
  const cur = structuredClone(CURRENT);
  cur.date = date;
  if (date < "2026-10-07")
    cur.followable["bill:2026/HB9902"] = { label: "HB 9902", url: "/bill/2026/hb9902",
      title: "relative to an invented example that becomes law" };
  Object.assign(cur, extra);
  w.net.site.set("/changes/current.json", cur);
}

// A subscriber already sent everything up to the night `cursor` -- as the
// sender would have left them, cursor and all.
async function subscribe(w, name, follows, { frequency = "daily", cursor = "2026-10-04" } = {}) {
  const address = w.address(name);
  const { id, links } = await insertSubscriber(w.d1, w.env, address, { frequency, follows,
    lastSentOn: cursor, sentDate: cursor,
    sentBuilt: FX.get(`/changes/${cursor}.json`)?.built ?? `${cursor}T09:00:00Z` });
  return { id, address, links };
}

const mailsTo = (w, address) => w.net.outbox.filter(m => m.to.includes(address));
const followsOf = async (w, id) => (await followKeys(w.d1, w.env))
  .filter(k => k.startsWith(`${id} `)).map(k => k.slice(String(id).length + 1));

// ---- when -----------------------------------------------------------------------------
test("New Hampshire's clock, either side of both daylight-saving changes", () => {
  const cases = [
    ["2026-10-31T11:59:00Z", "2026-10-31", 7, "Sat", false, false],
    ["2026-10-31T12:00:00Z", "2026-10-31", 8, "Sat", true, true],    // EDT: UTC-4
    ["2026-11-01T05:30:00Z", "2026-11-01", 1, "Sun", false, false],  // the hour that repeats
    ["2026-11-01T06:30:00Z", "2026-11-01", 1, "Sun", false, false],
    ["2026-11-01T12:00:00Z", "2026-11-01", 7, "Sun", false, false],  // EST now: UTC-5
    ["2026-11-01T13:00:00Z", "2026-11-01", 8, "Sun", true, false],
    ["2026-11-07T12:00:00Z", "2026-11-07", 7, "Sat", false, false],
    ["2026-11-07T13:00:00Z", "2026-11-07", 8, "Sat", true, true],
    ["2027-03-13T12:00:00Z", "2027-03-13", 7, "Sat", false, false],
    ["2027-03-13T13:00:00Z", "2027-03-13", 8, "Sat", true, true],
    ["2027-03-14T12:00:00Z", "2027-03-14", 8, "Sun", true, false],  // EDT again
    ["2027-03-20T11:00:00Z", "2027-03-20", 7, "Sat", false, false],
    ["2027-03-20T12:00:00Z", "2027-03-20", 8, "Sat", true, true],
    ["2026-11-01T03:30:00Z", "2026-10-31", 23, "Sat", false, false], // still Saturday there
    ["2026-10-10T23:59:00Z", "2026-10-10", 19, "Sat", true, true],   // the window's last hour
    ["2026-10-11T00:00:00Z", "2026-10-10", 20, "Sat", false, false],
  ];
  for (const [utc, date, hour, weekday, daily, weekly] of cases) {
    const c = nhClock(new Date(utc));
    assert.deepEqual([c.date, c.hour, c.weekday], [date, hour, weekday], utc);
    const d = due(new Date(utc));
    assert.deepEqual([d.daily, d.weekly], [daily, weekly], utc);
  }
});

// Nights made up for a fortnight: one item a night for each record.
function fortnight(w, from, to, keys) {
  w.net.site.clear();
  const cur = structuredClone(CURRENT);
  for (let d = from; d <= to; d = new Date(Date.parse(d) + 86400000).toISOString().slice(0, 10)) {
    const built = `${d}T09:00:00Z`;
    const refs = {};
    for (const k of keys)
      refs[k] = { items: [{ guid: `${k}:${d}`, date: d, kind: "action", term: "2025-2026",
                            summary: `Something new on ${d}`, seen: built }] };
    w.net.site.set(`/changes/${d}.json`, { format: 1, date: d, built,
      sitting_term: "2025-2026", new_by: "first-seen", refs });
    cur.date = d;
    cur.built = built;
  }
  w.net.site.set("/changes/current.json", cur);
}

async function everyHour(w, fromIso, toIso) {
  for (let t = Date.parse(fromIso); t < Date.parse(toIso); t += 3600000) {
    w.now = new Date(t);
    await run(w.env, w.now);
  }
}

test("daily at 8:00 and weekly on Saturday at 8:00 New Hampshire time, across the autumn change", async () => {
  const w = makeWorld();
  try {
    fortnight(w, "2026-10-28", "2026-11-09", ["bill:2026/HB9901"]);
    const d = await subscribe(w, "daily.autumn", ["bill:2026/HB9901"], { cursor: "2026-10-29" });
    const k = await subscribe(w, "weekly.autumn", ["bill:2026/HB9901"],
      { frequency: "weekly", cursor: "2026-10-29" });
    await everyHour(w, "2026-10-30T00:00:00Z", "2026-11-09T00:00:00Z");
    assert.deepEqual(mailsTo(w, d.address).map(m => m.at), [
      "2026-10-30T12:00:00.000Z", "2026-10-31T12:00:00.000Z",
      "2026-11-01T13:00:00.000Z", "2026-11-02T13:00:00.000Z", "2026-11-03T13:00:00.000Z",
      "2026-11-04T13:00:00.000Z", "2026-11-05T13:00:00.000Z", "2026-11-06T13:00:00.000Z",
      "2026-11-07T13:00:00.000Z", "2026-11-08T13:00:00.000Z"]);
    assert.deepEqual(mailsTo(w, k.address).map(m => m.at),
      ["2026-10-31T12:00:00.000Z", "2026-11-07T13:00:00.000Z"]);
    // Each daily carries its own night and no other.
    for (const m of mailsTo(w, d.address)) {
      const day = m.at.slice(0, 10);
      assert.match(m.text, new RegExp(`Something new on ${day}`));
      assert.equal((m.text.match(/Something new on/g) || []).length, 1, day);
    }
    // The weekly carries the week: Saturday's from the 1st to the 7th.
    const second = mailsTo(w, k.address)[1].text;
    for (const day of ["2026-11-01", "2026-11-04", "2026-11-07"])
      assert.match(second, new RegExp(`Something new on ${day}`));
    assert.doesNotMatch(second, /Something new on 2026-10-31/, "last week's is not sent again");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("daily at 8:00 and weekly on Saturday at 8:00 New Hampshire time, across the spring change", async () => {
  const w = makeWorld();
  try {
    fortnight(w, "2027-03-10", "2027-03-22", ["committee:H90"]);
    const d = await subscribe(w, "daily.spring", ["committee:H90"], { cursor: "2027-03-11" });
    const k = await subscribe(w, "weekly.spring", ["committee:H90"],
      { frequency: "weekly", cursor: "2027-03-11" });
    await everyHour(w, "2027-03-12T00:00:00Z", "2027-03-22T00:00:00Z");
    assert.deepEqual(mailsTo(w, d.address).map(m => m.at), [
      "2027-03-12T13:00:00.000Z", "2027-03-13T13:00:00.000Z",
      "2027-03-14T12:00:00.000Z", "2027-03-15T12:00:00.000Z", "2027-03-16T12:00:00.000Z",
      "2027-03-17T12:00:00.000Z", "2027-03-18T12:00:00.000Z", "2027-03-19T12:00:00.000Z",
      "2027-03-20T12:00:00.000Z", "2027-03-21T12:00:00.000Z"]);
    assert.deepEqual(mailsTo(w, k.address).map(m => m.at),
      ["2027-03-13T13:00:00.000Z", "2027-03-20T12:00:00.000Z"]);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

// ---- what -------------------------------------------------------------------------------
test("a week of dailies from the fixtures: each night once, the ending told, the follow ended", async () => {
  const w = makeWorld();
  try {
    const s = await subscribe(w, "reader.daily", ["bill:2026/HB9901", "bill:2026/HB9902",
      "bill:2026/HB9903", "member:990001", "committee:H90", "topic:housing"]);
    const morning = async date => {
      siteAsOf(w, date);
      w.now = new Date(`${date}T12:00:00Z`);
      await run(w.env, w.now);
      return mailsTo(w, s.address).filter(m => m.at.startsWith(date));
    };
    let m = await morning("2026-10-05");
    assert.equal(m.length, 1);
    assert.match(m[0].subject, /^1 update on what you follow$/, "no milestone, so the count");
    // The day once: the meeting's day, the entry's own date, is not printed
    // again (the language sweep, 17 October 2026), and the meeting is said in
    // plain words (the person's approval of the same day).
    assert.match(m[0].text, /October 2, 2026 {2}HB 9901 — Full committee work session set for 10:00 a\.m\., Legislative Office Building 305\n/);
    assert.match(m[0].text, /updated once a day, overnight/);

    m = await morning("2026-10-06");
    assert.match(m[0].text, /prime sponsor/);
    // A committee's day says what kind of meeting it was (17 October 2026).
    assert.match(m[0].text, /October 5, 2026 {2}Public hearing on HB 9903-FN/);
    assert.doesNotMatch(m[0].text, /work session/i, "the 5th's news is not sent twice");

    m = await morning("2026-10-07");
    assert.match(m[0].text, /HB 9902 — Signed into law\. There will be no more updates on it/);
    assert.match(m[0].subject, /^HB 9902 — Signed into law, and \d+ more updates$/,
      "the subject names how a bill ended before anything else");
    assert.match(m[0].text, /October 6, 2026 {2}HB 9903-FN — Executive session set for 1:00 p\.m\., Legislative Office Building 305\n/);
    assert.deepEqual(await followsOf(w, s.id), ["bill:2026/HB9901", "bill:2026/HB9903",
      "committee:H90", "member:990001", "topic:housing"], "the ended bill's follow is gone");

    m = await morning("2026-10-08");
    assert.match(m[0].text, /HB 9901 — Interim study report: recommends future legislation/);
    assert.match(m[0].text, /Committee roll call: Ought to Pass, 11-9/);
    assert.match(m[0].text, /HB 9903-FN \(relative to an invented fee, written for these tests\) — On Ought to Pass \(OTP, Pass the bill\): voted yes; the motion passed, 11-9/,
      "a followed legislator's ballot is set beside the roll call's result");
    assert.doesNotMatch(m[0].text, /HB 9902/, "nothing more about the bill that ended");
    assert.doesNotMatch(m[0].text, /HB 9904|05\/02\/2024/, "a topic sends the sitting term's items only");

    m = await morning("2026-10-09");
    assert.equal(m.length, 0, "a night with nothing new sends nothing");

    m = await morning("2026-10-10");
    assert.match(m[0].text, /Executive session set for Tuesday, October 13, 1:00 p\.m\./);
    assert.equal(mailsTo(w, s.address).length, 5);

    // The send log is counts and nothing else.
    const sends = w.d1.rows("sends");
    assert.deepEqual(sends.map(r => Object.keys(r).sort()),
      sends.map(() => ["date", "emails_sent", "ended", "failed", "frequency", "items"]));
    assert.equal(sends.reduce((n, r) => n + r.emails_sent, 0), 5);
    assert.equal(sends.reduce((n, r) => n + r.ended, 0), 1);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("the weekly: votes and executive sessions, hearings coming up, the study's recommendation", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-10");
    const s = await subscribe(w, "reader.weekly", ["bill:2026/HB9901", "bill:2026/HB9903",
      "committee:H90", "topic:housing"], { frequency: "weekly", cursor: "2026-10-03" });
    w.now = new Date("2026-10-09T12:00:00Z");      // Friday: not the weekly's day
    await run(w.env, w.now);
    assert.equal(mailsTo(w, s.address).length, 0);
    w.now = new Date("2026-10-10T12:00:00Z");      // Saturday, 8:00 EDT
    await run(w.env, w.now);
    const [m] = mailsTo(w, s.address);
    assert.equal(m.subject, "Your week: 2 committee meetings coming up, and HB 9903-FN — Committee roll call: Ought to Pass, 11-9");
    assert.ok(m.text.indexOf("COMING UP") > 0 &&
      m.text.indexOf("COMING UP") < m.text.indexOf("BILLS YOU FOLLOW"), "the weekly opens with the week ahead");
    // Plain headings (the person, 17 October 2026: "'Bills: the week that
    // was'" read confusingly).
    assert.doesNotMatch(m.text + m.html, /week that was|WEEK THAT WAS|THE WEEK AHEAD/);
    const hb9903 = m.text.slice(m.text.indexOf("HB 9903-FN"),
      m.text.indexOf("https://graniterecord.org/committee/H90"));
    assert.match(hb9903, /This week: 1 roll call vote and 1 executive session\./);
    // The committee that sits is named once, and not again after "For".
    assert.match(m.text, /Wednesday, October 14, 10:00 a\.m\.: Public hearing, House Example Committee, Legislative Office Building 305\. For HB 9903-FN\.\n/);
    assert.match(m.text, /HB 9901[\s\S]*No roll call votes or executive sessions this week\./);
    assert.match(m.text, /HB 9901 — Interim study report: recommends future legislation/);
    assert.match(m.text, /Tuesday, October 13, 1:00 p\.m\.: Executive session, House Example Committee, Legislative Office Building 305\.\n/);
    assert.doesNotMatch(m.text, /HB 9904/);
    assert.match(m.html, /This week: 1 roll call vote and 1 executive session\./);
    // A second run that Saturday sends nothing more.
    w.now = new Date("2026-10-10T15:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, s.address).length, 1);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("every update carries a manage link, an unsubscribe link and the RFC 8058 headers", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const s = await subscribe(w, "reader.links", ["bill:2026/HB9901"]);
    w.now = new Date("2026-10-05T12:00:00Z");
    await run(w.env, w.now);
    const [m] = mailsTo(w, s.address);
    const manage = /manage#t=([A-Za-z0-9_-]{43})/.exec(m.text)[1];
    const unsub = /unsubscribe#u=([A-Za-z0-9_-]{43})/.exec(m.text)[1];
    assert.equal(m.headers["List-Unsubscribe"],
      `<https://graniterecord.org/api/follow/unsubscribe?u=${unsub}>`);
    assert.equal(m.headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
    assert.ok(!("reply_to" in m) && !("replyTo" in m), "no reply address");
    assert.match(m.text, /takes no replies[\s\S]*“Report a problem” on the bill's, legislator's or committee's page[\s\S]*feedback form/);
    const [row] = w.d1.rows("subscribers");
    assert.equal(row.manage_hash, await hashToken(manage));
    assert.equal(row.unsub_hash, await hashToken(unsub));
    assert.deepEqual([manage, unsub], [s.links.manage, s.links.unsub], "the reader's own links");
    assert.ok(!w.d1.everyCell().some(c => c.includes(manage) || c.includes(unsub)),
      "the database holds the tokens' hashes, never the tokens");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("when every follow ends, the address goes with them and the email says so", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-07");
    const s = await subscribe(w, "reader.ending", ["bill:2026/HB9902"]);
    w.now = new Date("2026-10-07T12:00:00Z");
    await run(w.env, w.now);
    const [m] = mailsTo(w, s.address);
    assert.match(m.text, /HB 9902 — Signed into law\./);
    assert.match(m.text, /That was the last thing you followed, so your address has been deleted/);
    assert.doesNotMatch(m.text, /manage#t=|unsubscribe#u=/, "no link that would not work");
    assert.equal(m.headers, undefined);
    assert.equal(w.d1.rows("subscribers").length, 0);
    assert.equal(w.d1.rows("follows").length, 0);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a followed bill that drops off the list with no ending is told as stopped, once", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-09");
    const s = await subscribe(w, "reader.fallback", ["bill:2026/HB9905", "bill:2026/HB9901"],
      { cursor: "2026-10-08" });
    w.now = new Date("2026-10-09T12:00:00Z");
    await run(w.env, w.now);
    const [m] = mailsTo(w, s.address);
    assert.match(m.text, /HB 9905 \(2026\) is no longer moving on the record\. There will be no more updates on it/);
    assert.deepEqual(await followsOf(w, s.id), ["bill:2026/HB9901"]);
    // But an empty list is a broken build, not every bill ending at once.
    const v = await subscribe(w, "reader.emptylist", ["bill:2026/HB9906"], { cursor: "2026-10-09" });
    siteAsOf(w, "2026-10-10", { extra: { followable: { "committee:H90": { label: "House Example Committee" } } } });
    w.now = new Date("2026-10-10T12:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, v.address).length, 0);
    assert.deepEqual(await followsOf(w, v.id), ["bill:2026/HB9906"]);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a topic is followed for the sitting term only", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-08");
    const s = await subscribe(w, "reader.topic", ["topic:housing"], { cursor: "2026-10-07" });
    w.now = new Date("2026-10-08T12:00:00Z");
    await run(w.env, w.now);
    const [m] = mailsTo(w, s.address);
    assert.match(m.text, /HB 9903-FN — Committee roll call/);
    assert.doesNotMatch(m.text, /HB 9904/);
    assert.equal(m.subject, "HB 9903-FN — Committee roll call: Ought to Pass, 11-9",
      "one update, and a milestone: the subject is the update");
  } finally { w.close(); }
});

test("it waits for tonight's file until noon, then sends what it has, and says so", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-10");
    const s = await subscribe(w, "reader.waits", ["committee:H90"], { cursor: "2026-10-10" });
    for (const h of [12, 13, 14, 15]) {          // 8:00 to 11:00 EDT on Sunday the 11th
      w.now = new Date(`2026-10-11T${h}:00:00Z`);
      await run(w.env, w.now);
    }
    assert.equal(mailsTo(w, s.address).length, 0);
    assert.equal(w.logs.lines.filter(l => l === "follow sender.waiting-for-tonight 1").length, 4);
    w.now = new Date("2026-10-11T16:00:00Z");    // noon
    await run(w.env, w.now);
    assert.ok(w.logs.lines.includes("follow sender.tonight-missing-sending-anyway 1"));
    assert.equal(w.d1.rows("subscribers")[0].last_sent_on, "2026-10-11", "taken for the day");
    // The night publishes late; the next morning sends it.
    w.net.site.set("/changes/2026-10-11.json", { format: 1, date: "2026-10-11",
      built: "2026-10-11T17:30:00Z", sitting_term: "2025-2026", new_by: "first-seen",
      refs: { "committee:H90": { items: [{ guid: "late", date: "2026-10-10", kind: "sitting",
        summary: "A late night's news", term: "2025-2026", seen: "2026-10-11T17:30:00Z" }] } } });
    w.net.site.set("/changes/2026-10-12.json", { format: 1, date: "2026-10-12",
      built: "2026-10-12T09:00:00Z", sitting_term: "2025-2026", new_by: "first-seen", refs: {} });
    w.now = new Date("2026-10-12T12:00:00Z");
    await run(w.env, w.now);
    const sent = mailsTo(w, s.address);
    assert.equal(sent.length, 1);
    assert.match(sent[0].text, /A late night's news/);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a night rebuilt the same day sends only what the rebuild first saw", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-08");
    const s = await subscribe(w, "reader.rebuilt", ["bill:2026/HB9903"], { cursor: "2026-10-07" });
    w.now = new Date("2026-10-08T12:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, s.address).length, 1);
    // Rebuilt by hand at 15:00 with one item more.
    const n = structuredClone(FX.get("/changes/2026-10-08.json"));
    n.built = "2026-10-08T15:00:00Z";
    n.refs["bill:2026/HB9903"].items.push({ guid: "rebuilt-item", date: "2026-10-08",
      kind: "report", summary: "HB 9903-FN — Committee Report filed", term: "2025-2026",
      seen: "2026-10-08T15:00:00Z" });
    w.net.site.set("/changes/2026-10-08.json", n);
    w.net.site.set("/changes/2026-10-09.json", structuredClone(FX.get("/changes/2026-10-09.json")));
    w.now = new Date("2026-10-09T12:00:00Z");
    await run(w.env, w.now);
    const second = mailsTo(w, s.address)[1];
    assert.match(second.text, /Committee Report filed/);
    assert.doesNotMatch(second.text, /Ought to Pass, 11-9/, "what was sent is not sent again");
  } finally { w.close(); }
});

test("under record-date, the same week reads the same, with no seen at all", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-08");
    for (const [p, v] of w.net.site) {
      v.new_by = "record-date";
      for (const r of Object.values(v.refs || {})) {
        for (const it of r.items || []) delete it.seen;
        if (r.study) delete r.study.seen;
      }
    }
    const s = await subscribe(w, "reader.recorddate", ["bill:2026/HB9901", "bill:2026/HB9903"],
      { cursor: "2026-10-07" });
    w.now = new Date("2026-10-08T12:00:00Z");
    await run(w.env, w.now);
    const [m] = mailsTo(w, s.address);
    assert.match(m.text, /recommends future legislation/);
    assert.match(m.text, /Ought to Pass, 11-9/);
    assert.equal(w.logs.lines.filter(l => l.startsWith("follow sender.entries")).length, 0);
  } finally { w.close(); }
});

test("a send Resend fails is given back and tried again next hour", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const s = await subscribe(w, "reader.retry", ["bill:2026/HB9901"]);
    w.net.resendStatus = 500;
    w.now = new Date("2026-10-05T12:00:00Z");
    const r = await run(w.env, w.now);
    assert.equal(r.failed, 1);
    assert.equal(w.d1.rows("subscribers")[0].last_sent_on, "2026-10-04", "the day is given back");
    assert.equal(w.d1.rows("subscribers")[0].sent_date, "2026-10-04", "and the cursor stays");
    assert.ok(w.logs.lines.includes("follow sender.resend-refused.500 1"));
    w.net.resendStatus = 200;
    w.now = new Date("2026-10-05T13:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, s.address).length, 1);
    assert.equal(w.d1.rows("sends")[0].failed, 1);
    assert.equal(w.d1.rows("sends")[0].emails_sent, 1);
    assert.deepEqual(leaks(w), [], "Resend's error named the address, and no log line did");
  } finally { w.close(); }
});

test("an email Resend took whose answer was lost is not sent again", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const s = await subscribe(w, "reader.lost", ["bill:2026/HB9901"]);
    w.net.loseAnswer = true;
    w.now = new Date("2026-10-05T12:00:00Z");
    let r = await run(w.env, w.now);
    assert.equal(r.failed, 1);
    assert.equal(mailsTo(w, s.address).length, 1, "Resend took it");
    assert.equal(w.d1.rows("subscribers")[0].last_sent_on, "2026-10-04",
      "the answer lost, the day is given back");
    w.now = new Date("2026-10-05T13:00:00Z");
    r = await run(w.env, w.now);
    assert.equal(mailsTo(w, s.address).length, 1, "the same key again, and Resend sent nothing");
    assert.equal(w.net.repeats, 1);
    assert.deepEqual([...w.net.keys], [`digest/2026-10-05/daily/${s.id}`]);
    assert.equal(w.d1.rows("subscribers")[0].last_sent_on, "2026-10-05", "the day stays taken");
    assert.equal(w.d1.rows("subscribers")[0].sent_date, "2026-10-05", "and the cursor moves on");
    assert.ok(w.logs.lines.includes("follow sender.resend-already-has-it 1"));
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("Resend's rate limit stops the run, and the rest go next hour", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const a = await subscribe(w, "first.in.line", ["bill:2026/HB9901"]);
    const b = await subscribe(w, "second.in.line", ["bill:2026/HB9901"]);
    w.net.resendStatus = 429;
    w.now = new Date("2026-10-05T12:00:00Z");
    const r = await run(w.env, w.now);
    assert.equal(w.net.refused, 2, "one refusal waited out and asked once more, then no more");
    assert.deepEqual(r.problems, ["resend-rate"]);
    w.net.resendStatus = 200;
    w.now = new Date("2026-10-05T13:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, a.address).length + mailsTo(w, b.address).length, 2);
  } finally { w.close(); }
});

test("a daily cap that lasts serves every reader in turn, not the same ones every day", async () => {
  const w = makeWorld();
  try {
    fortnight(w, "2026-10-12", "2026-10-16", ["bill:2026/HB9901"]);
    // Resend's daily cap, at two a day; three readers with news every night.
    const perDay = new Map();
    const inner = w.net.handle.bind(w.net);
    w.net.handle = async req => {
      if (new URL(req.url).host === "api.resend.com") {
        const day = w.now.toISOString().slice(0, 10);
        w.net.resendStatus = (perDay.get(day) || 0) >= 2 ? 429 : 200;
        const r = await inner(req);
        if (r.status === 200) perDay.set(day, (perDay.get(day) || 0) + 1);
        return r;
      }
      return inner(req);
    };
    const subs = [];
    for (const n of ["one", "two", "three"])
      subs.push(await subscribe(w, `turn.${n}`, ["bill:2026/HB9901"], { cursor: "2026-10-12" }));
    await everyHour(w, "2026-10-13T00:00:00Z", "2026-10-17T00:00:00Z");
    const days = subs.map(s => mailsTo(w, s.address).map(m => m.at.slice(0, 10)));
    for (const [i, d] of days.entries()) assert.ok(d.length >= 2, `turn.${i}: ${d.join(" ")}`);
    assert.equal(days.flat().length, 8, "two a day for four days");
    // And nothing was lost by waiting: the one refused on a day has that day's
    // news in its next email.
    const third = mailsTo(w, subs[2].address)[0];
    assert.match(third.text, /Something new on 2026-10-13/);
  } finally { w.close(); }
});

test("an email that went is not given back when a write after it fails", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const s = await subscribe(w, "reader.after", ["bill:2026/HB9901"]);
    let fail = 1;
    w.d1.failWhen = sql => (fail > 0 && /^UPDATE subscribers SET sent_date/.test(sql))
      ? (fail--, new Error("D1_ERROR: transient")) : null;
    w.now = new Date("2026-10-05T12:00:00Z");
    const r1 = await run(w.env, w.now);
    assert.deepEqual([r1.sent, r1.failed], [1, 0], "counted as sent");
    const [m] = mailsTo(w, s.address);
    const t = tokensIn(m);
    assert.equal(w.d1.rows("subscribers")[0].sent_date, "2026-10-05", "the cursor moved on the second try");
    assert.equal((await view(w, t.manage)).status, 200, "the delivered email's manage link works");
    w.now = new Date("2026-10-05T13:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, s.address).length, 1, "and it is not sent again");
    // When both tries fail: logged, still sent, still not sent twice today.
    const v = await subscribe(w, "reader.after2", ["bill:2026/HB9901"]);
    w.d1.failWhen = sql => /^UPDATE subscribers SET sent_date/.test(sql) ? new Error("D1_ERROR") : null;
    await run(w.env, w.now);
    w.now = new Date("2026-10-05T14:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, v.address).length, 1);
    assert.ok(w.logs.lines.includes("follow sender.after-send-failed.Error 1"));
    const one = await w.call(handlers.unsubscribe, new Request(
      `${SITE}/api/follow/unsubscribe?u=${tokensIn(mailsTo(w, v.address)[0]).header}`,
      { method: "POST", body: "List-Unsubscribe=One-Click",
        headers: { "Content-Type": "application/x-www-form-urlencoded" } }));
    assert.equal(one.status, 200);
    assert.equal(w.d1.rows("subscribers").length, 1, "its one-click unsubscribe deleted the reader");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("every email carries the same manage link, until a new one is asked for", async () => {
  const w = makeWorld();
  try {
    fortnight(w, "2026-10-12", "2026-11-12", ["bill:2026/HB9901"]);
    const s = await subscribe(w, "reader.samelink", ["bill:2026/HB9901"], { cursor: "2026-10-12" });
    for (let d = Date.parse("2026-10-13T13:00:00Z"); d < Date.parse("2026-11-12T00:00:00Z"); d += 86400000) {
      w.now = new Date(d);
      await run(w.env, w.now);
    }
    const mails = mailsTo(w, s.address);
    assert.equal(mails.length, 30);
    assert.equal(new Set(mails.map(m => tokensIn(m).manage)).size, 1, "one manage link in thirty emails");
    assert.equal(new Set(mails.map(m => tokensIn(m).unsub)).size, 1, "and one unsubscribe link");
    assert.equal(tokensIn(mails[0]).manage, s.links.manage);
  } finally { w.close(); }
});

test("a run stops taking readers before it would pass the D1 statement limit", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const subs = [];
    for (let i = 0; i < 20; i++)
      subs.push(await subscribe(w, `budget.${i}`, ["bill:2026/HB9901"]));
    let statements = 0;
    const inner = w.d1.failWhen;
    w.d1.failWhen = (sql, args) => { statements++; return inner ? inner(sql, args) : null; };
    w.now = new Date("2026-10-05T12:00:00Z");
    const r = await run(w.env, w.now);           // D1_QUERIES_PER_RUN unset: 50
    assert.ok(statements <= 50, `${statements} statements in one run`);
    assert.equal(r.queries, statements, "the run counts what it ran");
    assert.ok(r.sent >= 8 && r.sent < 20, `sent ${r.sent}`);
    assert.ok(w.logs.lines.some(l => /^follow sender\.query-budget-reached \d+$/.test(l)));
    for (let h = 13; h < 16; h++) {
      statements = 0;
      w.now = new Date(`2026-10-05T${h}:00:00Z`);
      await run(w.env, w.now);
      assert.ok(statements <= 50, `${statements} statements at ${h}:00`);
    }
    for (const s of subs) assert.equal(mailsTo(w, s.address).length, 1, s.address);
  } finally { w.close(); }
});

test("a member or committee that leaves the list is told as stopped; a topic is kept", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-09");
    const s = await subscribe(w, "reader.turnover", ["member:990009", "committee:H99",
      "topic:fisheries", "bill:2026/HB9901"], { cursor: "2026-10-08" });
    w.now = new Date("2026-10-09T12:00:00Z");
    await run(w.env, w.now);
    const [m] = mailsTo(w, s.address);
    assert.match(m.text, /Legislator no\. 990009 is no longer among the sitting legislators on the record\. There will be no more updates on it/);
    assert.match(m.text, /Committee H99 is no longer among the committees on the record\. There will be no more updates on it/);
    assert.doesNotMatch(m.text, /Fisheries/, "a topic out of the list for now is not ended");
    assert.deepEqual(await followsOf(w, s.id), ["bill:2026/HB9901", "topic:fisheries"]);
  } finally { w.close(); }
});

// THE INTERIM STUDY REPORT, SAID ONE WAY (the language sweep, 17 October
// 2026): it was a fixed sentence, the clerk's line after it, and the sentence
// again at a glance and in the subject, naming no bill.
test("an interim study's report is said one way, in plain_action's words, naming its bill", () => {
  const base = { origin: "https://graniterecord.org", frequency: "daily", date: "2026-10-08",
    manage: "M".repeat(43), unsub: "U".repeat(43) };
  const section = study => ({ key: "bill:2026/HB9901", kind: "bill", ref: "2026/HB9901",
    label: "HB 9901", title: "", url: "/bill/2026/hb9901", items: [], more: 0, study, ended: null,
    week: null, upcoming: [] });
  const words = { true: "recommends future legislation", false: "does not recommend future legislation",
                  null: "makes no recommendation" };
  for (const [recommends, said] of [[true, words.true], [false, words.false], [null, words.null]]) {
    const m = digestEmail({ ...base, sections: [section({ recommends, date: "2026-10-07",
      summary: "Interim Study Report: Recommended for Future Legislation 10/07/2026 (Vote 12-2; )" })] });
    assert.equal(m.subject, `HB 9901 — Interim study report: ${said}`, "the subject names the bill");
    assert.equal((m.text.match(/Interim study report/g) || []).length, 1, "said once in the text");
    assert.match(m.text, new RegExp(`October 7, 2026 {2}HB 9901 — Interim study report: ${said}\\n`));
    assert.doesNotMatch(m.text + m.html, /Interim Study Report:|interim study committee|Vote 12-2/,
      "the clerk's line and the old sentence are gone");
  }
  // plain_action.py says the same report in the same words, so a law's or a
  // topic's line for it reads as the bill's does.
  const pa = readFileSync(new URL("../../src/parse/plain_action.py", import.meta.url), "utf8");
  for (const said of Object.values(words)) assert.ok(pa.includes(`Interim study report: ${said}`), said);
});

test("at most SEND_LIMIT emails a run; the next hour finishes the list", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    w.env.SEND_LIMIT = "2";
    const subs = [];
    for (const n of ["one", "two", "three"]) subs.push(await subscribe(w, `limit.${n}`, ["bill:2026/HB9901"]));
    w.now = new Date("2026-10-05T12:00:00Z");
    await run(w.env, w.now);
    assert.equal(w.net.outbox.length, 2);
    w.now = new Date("2026-10-05T13:00:00Z");
    await run(w.env, w.now);
    assert.equal(w.net.outbox.length, 3);
    for (const s of subs) assert.equal(mailsTo(w, s.address).length, 1);
  } finally { w.close(); }
});

test("without its configuration it sends nothing and says only a code", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const s = await subscribe(w, "reader.config", ["bill:2026/HB9901"]);
    w.now = new Date("2026-10-05T12:00:00Z");
    await run({ ...w.env, SITE_ORIGIN: "" }, w.now);
    assert.ok(w.logs.lines.includes("follow sender.config"));
    await run({ ...w.env, MAIL_FROM: "" }, w.now);
    assert.ok(w.logs.lines.includes("follow sender.error.ConfigError 1"));
    assert.equal(w.net.outbox.length, 0);
    assert.equal(w.d1.rows("subscribers")[0].last_sent_on, "2026-10-04", "nothing taken");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, s.address).length, 1);
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("the sender asks nothing but the site's changes files and Resend", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-08");
    await subscribe(w, "reader.hosts", ["bill:2026/HB9901"], { cursor: "2026-10-07" });
    w.now = new Date("2026-10-08T12:00:00Z");
    await run(w.env, w.now);
    const hosts = new Set(w.net.asked.map(a => a.replace(/^(https:\/\/[^/]+).*$/, "$1")));
    assert.deepEqual([...hosts].sort(), ["https://api.resend.com", "https://graniterecord.org"]);
    assert.ok(w.net.asked.filter(a => a.startsWith("https://graniterecord.org"))
      .every(a => /\/changes\/(current|\d{4}-\d{2}-\d{2})\.json$|\/api\/follow\/count$/.test(a)));
  } finally { w.close(); }
});

// ---- the reader's own settings (the manage page, 11 October 2026) ----------------------
const setRow = (w, id, sql, ...v) => w.d1.sql.prepare(`UPDATE subscribers SET ${sql} WHERE id = ?`).run(...v, id);

test("a pause sends nothing through its last day, and the day after starts from there", async () => {
  const w = makeWorld();
  try {
    const s = await subscribe(w, "reader.pause", ["bill:2026/HB9903"], { cursor: "2026-10-04" });
    setRow(w, s.id, "paused_until = ?", "2026-10-07");
    for (const d of ["2026-10-07", "2026-10-08"]) {
      siteAsOf(w, d);
      w.now = new Date(`${d}T12:00:00Z`);
      await run(w.env, w.now);
    }
    const m = mailsTo(w, s.address);
    assert.equal(m.length, 1, "the 7th is paused, the 8th is not");
    assert.ok(m[0].at.startsWith("2026-10-08"));
    assert.match(m[0].text, /Committee roll call/, "the 8th's news");
    assert.doesNotMatch(m[0].text, /HB 9903-FN — Executive session/i, "not the news of the paused days");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a pause until the reader turns it back on sends nothing at all", async () => {
  const w = makeWorld();
  try {
    const s = await subscribe(w, "reader.away", ["bill:2026/HB9903"], { cursor: "2026-10-04" });
    setRow(w, s.id, "paused_until = ?", "9999-12-31");
    for (const d of ["2026-10-07", "2026-10-08", "2026-10-10"]) {
      siteAsOf(w, d);
      w.now = new Date(`${d}T12:00:00Z`);
      await run(w.env, w.now);
    }
    assert.equal(mailsTo(w, s.address).length, 0);
  } finally { w.close(); }
});

test("milestones only: the decisions and what is scheduled, not every docket line", async () => {
  const w = makeWorld();
  try {
    const all = await subscribe(w, "reader.all", ["bill:2026/HB9901", "bill:2026/HB9903"], { cursor: "2026-10-04" });
    const few = await subscribe(w, "reader.few", ["bill:2026/HB9901", "bill:2026/HB9903"], { cursor: "2026-10-04" });
    setRow(w, few.id, "detail = ?", "milestones");
    for (const d of ["2026-10-05", "2026-10-07"]) {
      siteAsOf(w, d);
      w.now = new Date(`${d}T12:00:00Z`);
      await run(w.env, w.now);
    }
    const a = mailsTo(w, all.address), f = mailsTo(w, few.address);
    assert.equal(a.length, 2);
    assert.match(a[0].text, /Full committee work session set for/, "everything has the work session");
    assert.equal(f.length, 1, "the 5th held no milestone, so nothing went");
    assert.match(f[0].text, /October 6, 2026 {2}HB 9903-FN — Executive session set for 1:00 p\.m\./);
    assert.match(f[0].text, /October 6, 2026 {2}HB 9903-FN — Hearing set for Wednesday, October 14, 10:00 a\.m\./,
      "a meeting on another day keeps its date");
  } finally { w.close(); }
});

test("a law can be followed by its chapter, and is named by it", async () => {
  const { parseKey, fallbackLabel } = await import("../../workers/follow/common.js");
  assert.deepEqual(parseKey("law:91-A"), { kind: "law", ref: "91-A" });
  assert.deepEqual(parseKey("law:674"), { kind: "law", ref: "674" });
  assert.equal(parseKey("law:91-a"), null, "a chapter is in capitals, as its page names it");
  assert.equal(parseKey("law:91-A:4"), null, "a chapter, not a section");
  assert.equal(fallbackLabel("law", "91-A"), "RSA 91-A");
});

// ---- before go-live (the review of 22 October 2026) ------------------------------------
test("a 429 is waited out once and the same email sent under the same key", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const s = await subscribe(w, "reader.patient", ["bill:2026/HB9901"]);
    w.net.resendStatusOnce = 429;
    w.now = new Date("2026-10-05T12:00:00Z");
    const r = await run(w.env, w.now);
    assert.equal(w.net.refused, 1);
    assert.equal(mailsTo(w, s.address).length, 1, "sent on the second ask");
    assert.equal(r.sent, 1);
    assert.deepEqual(r.problems, []);
  } finally { w.close(); }
});

test("an address Resend calls bad keeps its day, waits for tomorrow, and is never deleted", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const bad = await subscribe(w, "reader.bad", ["bill:2026/HB9901"]);
    const good = await subscribe(w, "reader.good", ["bill:2026/HB9901"]);
    w.net.resendStatusOnce = 422;
    w.now = new Date("2026-10-05T12:00:00Z");
    const r = await run(w.env, w.now);
    assert.equal(r.failed, 1);
    assert.equal(mailsTo(w, good.address).length, 1, "the next reader is not held up");
    const row = w.d1.rows("subscribers").find(x => x.id === bad.id);
    assert.equal(row.last_sent_on, "2026-10-05", "the day stays taken");
    assert.equal(row.sent_date, "2026-10-04", "and the cursor stays, so tomorrow carries the news");
    w.now = new Date("2026-10-05T13:00:00Z");
    await run(w.env, w.now);
    assert.equal(w.net.refused, 1, "not asked again the same day");
    w.now = new Date("2026-10-06T12:00:00Z");
    siteAsOf(w, "2026-10-06");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, bad.address).length, 1, "tomorrow it goes");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("a key or domain Resend refuses stops the run and is a problem", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    await subscribe(w, "reader.one", ["bill:2026/HB9901"]);
    await subscribe(w, "reader.two", ["bill:2026/HB9901"]);
    w.net.resendStatus = 401;
    w.now = new Date("2026-10-05T12:00:00Z");
    const r = await run(w.env, w.now);
    assert.equal(w.net.refused, 1, "one refusal, and the run stops");
    assert.deepEqual(r.problems, ["resend-auth"]);
    assert.ok(w.d1.rows("subscribers").every(x => x.last_sent_on === "2026-10-04"), "both given back");
  } finally { w.close(); }
});

test("Resend failing three times in a row stops the run", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    for (const n of ["a", "b", "c", "d", "e"]) await subscribe(w, `reader.${n}`, ["bill:2026/HB9901"]);
    w.net.resendStatus = 503;
    w.now = new Date("2026-10-05T12:00:00Z");
    const r = await run(w.env, w.now);
    assert.equal(w.net.refused, 3);
    assert.deepEqual(r.problems, ["resend-down"]);
  } finally { w.close(); }
});

test("nothing is mailed while the site's follow pages do not answer", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const s = await subscribe(w, "reader.nolinks", ["bill:2026/HB9901"]);
    w.net.followLive = false;
    w.now = new Date("2026-10-05T12:00:00Z");
    const r = await run(w.env, w.now);
    assert.equal(w.net.outbox.length, 0);
    assert.deepEqual(r.problems, ["site-follow"]);
    assert.ok(w.logs.lines.includes("follow sender.site-follow-missing.404 1"));
    assert.equal(w.d1.rows("subscribers")[0].last_sent_on, "2026-10-04", "nothing taken");
    w.net.followLive = true;
    w.now = new Date("2026-10-05T13:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, s.address).length, 1);
  } finally { w.close(); }
});

test("a weekly whose Saturday did not go goes on a later day; a new weekly waits for Saturday", async () => {
  const w = makeWorld();
  try {
    fortnight(w, "2026-10-03", "2026-10-12", ["bill:2026/HB9901"]);
    const missed = await subscribe(w, "weekly.missed", ["bill:2026/HB9901"],
      { frequency: "weekly", cursor: "2026-10-03" });
    const fresh = await subscribe(w, "weekly.fresh", ["bill:2026/HB9901"],
      { frequency: "weekly", cursor: "2026-10-03" });
    w.d1.sql.prepare("UPDATE subscribers SET last_sent_on = NULL WHERE id = ?").run(fresh.id);
    // Saturday the 10th went by unsent; Monday the 12th, 8:00 EDT.
    w.now = new Date("2026-10-12T12:00:00Z");
    await run(w.env, w.now);
    const got = mailsTo(w, missed.address);
    assert.equal(got.length, 1, "caught up on Monday");
    for (const d of ["2026-10-04", "2026-10-10", "2026-10-12"])
      assert.ok(got[0].text.includes(`Something new on ${d}`) || got[0].html.includes(`Something new on ${d}`),
        `the week reaches back to ${d}`);
    assert.equal(mailsTo(w, fresh.address).length, 0, "never yet sent: Saturday");
    assert.ok(w.logs.lines.includes("follow sender.weekly-catch-up 1"));
  } finally { w.close(); }
});

test("each run pings Healthchecks: plainly when well, /fail with codes and counts when not", async () => {
  const { ping } = await import("../../workers/follow/sender.js");
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const s = await subscribe(w, "reader.ping", ["bill:2026/HB9901"]);
    const env = { ...w.env, HEALTHCHECK_URL: "https://hc-ping.com/abc-123" };
    w.now = new Date("2026-10-05T12:00:00Z");
    await ping(env, await run(env, w.now));
    assert.equal(w.net.pings.at(-1).url, "/abc-123");
    assert.match(w.net.pings.at(-1).body, /sent 1/);
    w.net.followLive = false;
    w.now = new Date("2026-10-06T12:00:00Z");
    siteAsOf(w, "2026-10-06");
    await ping(env, await run(env, w.now));
    assert.equal(w.net.pings.at(-1).url, "/abc-123/fail");
    assert.match(w.net.pings.at(-1).body, /problem: site-follow/);
    assert.ok(!w.net.pings.some(p => p.body.includes(s.address.split("@")[0])), "no address in a ping");
    assert.equal(await ping(w.env, { problems: [] }), false, "no secret, no ping");
  } finally { w.close(); }
});
