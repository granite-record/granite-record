// sender.js: when it sends (8:00 New Hampshire time daily, Saturday 8:00
// weekly, across both daylight-saving changes), what it says (the week's
// votes and executive sessions, hearings coming up, an interim study's
// recommendation, a bill's ending), and what it keeps (counts).

import test from "node:test";
import assert from "node:assert/strict";
import { lookupHash, sealAddress, hashToken } from "../../workers/follow/address.js";
import { due, nhClock, run } from "../../workers/follow/sender.js";
import { leaks, loadFixtures, makeWorld } from "./fakes.js";

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
  const h = await lookupHash(w.env, address);
  const id = await w.d1.prepare("INSERT INTO subscribers (email_hmac, email_enc, frequency, " +
    "confirmed_at, last_sent_on, sent_date, sent_built) VALUES (?1, ?2, ?3, ?4, ?5, ?5, ?6) RETURNING id")
    .bind(h, await sealAddress(w.env, address, h), frequency, "2026-09-30T12:00:00Z",
          cursor, FX.get(`/changes/${cursor}.json`)?.built ?? `${cursor}T09:00:00Z`).first("id");
  for (const k of follows) {
    const i = k.indexOf(":");
    await w.d1.prepare("INSERT INTO follows VALUES (?1, ?2, ?3, '2026-09-30T12:00:00Z')")
      .bind(id, k.slice(0, i), k.slice(i + 1)).run();
  }
  return { id, address };
}

const mailsTo = (w, address) => w.net.outbox.filter(m => m.to.includes(address));
const followsOf = (w, id) => w.d1.rows("follows").filter(f => f.subscriber_id === id)
  .map(f => `${f.kind}:${f.ref}`).sort();

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
    assert.match(m[0].subject, /^Granite Record: 1 update on what you follow$/);
    assert.match(m[0].text, /HB 9901 — Full Committee Work Session: 10\/02\/2026/);
    assert.match(m[0].text, /rebuilt once a night/);

    m = await morning("2026-10-06");
    assert.match(m[0].text, /prime sponsor/);
    assert.match(m[0].text, /House Example Committee — 5 October 2026/);
    assert.doesNotMatch(m[0].text, /Work Session/, "the 5th's news is not sent twice");

    m = await morning("2026-10-07");
    assert.match(m[0].text, /HB 9902 was signed into law\. This follow has ended/);
    assert.match(m[0].text, /Executive Session: 10\/06\/2026/);
    assert.deepEqual(followsOf(w, s.id), ["bill:2026/HB9901", "bill:2026/HB9903",
      "committee:H90", "member:990001", "topic:housing"], "the ended bill's follow is gone");

    m = await morning("2026-10-08");
    assert.match(m[0].text, /The interim study committee recommended future legislation\./);
    assert.match(m[0].text, /Committee roll call: Ought to Pass, 11-9/);
    assert.match(m[0].text, /yes on Ought to Pass/);
    assert.doesNotMatch(m[0].text, /HB 9902/, "nothing more about the bill that ended");
    assert.doesNotMatch(m[0].text, /HB 9904|05\/02\/2024/, "a topic sends the sitting term's items only");

    m = await morning("2026-10-09");
    assert.equal(m.length, 0, "a night with nothing new sends nothing");

    m = await morning("2026-10-10");
    assert.match(m[0].text, /Executive Session: 10\/13\/2026/);
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
    assert.equal(m.subject, "Granite Record: your week to Saturday 10 October 2026");
    const hb9903 = m.text.slice(m.text.indexOf("HB 9903-FN"),
      m.text.indexOf("https://graniterecord.org/committee/H90"));
    assert.match(hb9903, /This week: 1 roll call vote and 1 executive session\./);
    assert.match(hb9903, /Coming up: 14 October 2026, 10:00 a\.m\., public hearing, House Example Committee, LOB 305\./);
    assert.match(m.text, /HB 9901[\s\S]*No roll call votes or executive sessions this week\./);
    assert.match(m.text, /The interim study committee recommended future legislation\./);
    assert.match(m.text, /Coming up: 13 October 2026, 1:00 p\.m\., executive session/);
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
    assert.match(m.text, /takes no replies[\s\S]*Report a problem with this page[\s\S]*feedback form/);
    const links = w.d1.rows("links");
    assert.ok(links.some(l => l.purpose === "manage" && l.token_hash !== manage));
    const hashes = new Set(links.map(l => l.token_hash));
    assert.ok(hashes.has(await hashToken(manage)) && hashes.has(await hashToken(unsub)));
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
    assert.match(m.text, /HB 9902 was signed into law\./);
    assert.match(m.text, /That was the last thing you followed, so your address has been deleted/);
    assert.doesNotMatch(m.text, /manage#t=|unsubscribe#u=/, "no link that would not work");
    assert.equal(m.headers, undefined);
    assert.equal(w.d1.rows("subscribers").length, 0);
    assert.equal(w.d1.rows("links").length, 0);
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
    assert.match(m.text, /HB 9905 \(2026\) is no longer moving on the record\. This follow has ended/);
    assert.deepEqual(followsOf(w, s.id), ["bill:2026/HB9901"]);
    // But an empty list is a broken build, not every bill ending at once.
    const v = await subscribe(w, "reader.emptylist", ["bill:2026/HB9906"], { cursor: "2026-10-09" });
    siteAsOf(w, "2026-10-10", { extra: { followable: { "committee:H90": { label: "House Example Committee" } } } });
    w.now = new Date("2026-10-10T12:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, v.address).length, 0);
    assert.deepEqual(followsOf(w, v.id), ["bill:2026/HB9906"]);
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
    assert.match(m.subject, /1 update/);
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
    assert.match(m.text, /recommended future legislation/);
    assert.match(m.text, /Ought to Pass, 11-9/);
    assert.equal(w.logs.lines.filter(l => l.startsWith("follow sender.entries")).length, 0);
  } finally { w.close(); }
});

test("a refused send is given back, its links removed, and tried again next hour", async () => {
  const w = makeWorld();
  try {
    siteAsOf(w, "2026-10-05");
    const s = await subscribe(w, "reader.retry", ["bill:2026/HB9901"]);
    w.net.resendStatus = 422;
    w.now = new Date("2026-10-05T12:00:00Z");
    const r = await run(w.env, w.now);
    assert.equal(r.failed, 1);
    assert.equal(w.d1.rows("links").length, 0, "the links made for it are gone");
    assert.equal(w.d1.rows("subscribers")[0].last_sent_on, "2026-10-04", "the day is given back");
    assert.ok(w.logs.lines.includes("follow sender.resend-refused.422 1"));
    w.net.resendStatus = 200;
    w.now = new Date("2026-10-05T13:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, s.address).length, 1);
    assert.equal(w.d1.rows("sends")[0].failed, 1);
    assert.equal(w.d1.rows("sends")[0].emails_sent, 1);
    assert.deepEqual(leaks(w), [], "Resend's error named the address, and no log line did");
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
    await run(w.env, w.now);
    assert.equal(w.net.refused, 1, "one refusal, and no second try in the same run");
    w.net.resendStatus = 200;
    w.now = new Date("2026-10-05T13:00:00Z");
    await run(w.env, w.now);
    assert.equal(mailsTo(w, a.address).length + mailsTo(w, b.address).length, 2);
  } finally { w.close(); }
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
      .every(a => /\/changes\/(current|\d{4}-\d{2}-\d{2})\.json$/.test(a)));
  } finally { w.close(); }
});
