// mail.js, as the person read it on 17 October 2026 (a daily, a weekly and
// the welcome email) and as the language sweep of that day found it: the
// site's header, every name a link to its page, no opening sentence, a
// committee's day by its kind, plain headings, a reader's words and dates,
// one way to say a study's report, and a palette that survives a client's
// dark mode. Each test fails if the rule it is named for is undone.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { checkCurrent, checkNight } from "../../workers/follow/changes.js";
import { parseKey } from "../../workers/follow/common.js";
import { FOLLOW_BETA, chipWord, keepWhole, MARK, PALETTE, STATUS_INK, TESTIFY_FORMS, VOTE_INK, ballotWords, betaNote, confirmationEmail,
         dateOnce, dayDate, digestEmail, longDate, meetingWords, newLinkEmail, nothingNewEmail, pageNames, shortDate,
         siteClock, welcomeEmail } from "../../workers/follow/mail.js";
import { collect, testifyFor } from "../../workers/follow/sender.js";
import { SITE, loadFixtures } from "./fakes.js";

const FX = loadFixtures();
const CURRENT = checkCurrent(FX.get("/changes/current.json")).value;
const NIGHTS = [...FX].filter(([p]) => /\d{4}-\d{2}-\d{2}\.json$/.test(p))
  .map(([p, v]) => checkNight(v, p.slice(9, 19)).value)
  .sort((a, b) => a.date.localeCompare(b.date));
const FOLLOWS = ["bill:2026/HB9901", "bill:2026/HB9903", "member:990001", "committee:H90",
  "topic:housing", "law:91-A"].map(k => ({ ...parseKey(k), fh: "x" }));
const LINKS = { manage: "M".repeat(43), unsub: "U".repeat(43), feedbackUrl: "https://forms.example.com/x" };
const TODAY = "2026-10-10";

// The fixtures' week as the sender would put it: the weekly reads all of it,
// the daily the nights after `from`.
function digest(frequency, from = "2026-10-02") {
  const sections = collect({ follows: FOLLOWS, nights: NIGHTS.filter(n => n.date > from), cursor: {},
    current: CURRENT, frequency, today: TODAY });
  return digestEmail({ origin: SITE, frequency, date: TODAY, sections, names: pageNames(CURRENT), ...LINKS });
}
function everyEmail() {
  const m = CURRENT.followable.get("bill:2026/HB9903");
  return {
    confirmation: confirmationEmail({ origin: SITE, label: m.label, title: m.title, token: "T".repeat(43) }),
    welcome: welcomeEmail({ origin: SITE, kind: "bill", label: m.label, title: m.title, url: m.url,
      frequency: "daily", total: 3, pausedUntil: "2026-10-20", ...LINKS }),
    newLink: newLinkEmail({ origin: SITE, ...LINKS }),
    daily: digest("daily", "2026-10-07"),
    weekly: digest("weekly"),
    voted: voted(ROLLCALL),
    // The preview sender's test send, where nothing followed had news (sender.js, A TEST SEND).
    nothingNew: nothingNewEmail({ origin: SITE, frequency: "daily", date: TODAY, nights: 7, ...LINKS }),
  };
}

// A daily with one floor roll call on a bill, as build_feeds hands it over
// (follow_changes.rollcall_detail): the vote bar's email.
const ROLLCALL = { yeas: 201, nays: 163, passed: true, need: 183,
  parties: [["R", 190, 13], ["D", 11, 150]] };
function voted(rollcall) {
  return digestEmail({ origin: SITE, frequency: "daily", date: TODAY, names: pageNames(CURRENT), ...LINKS,
    sections: [{ key: "bill:2026/HB9901", kind: "bill", ref: "2026/HB9901", label: "HB 9901", title: "",
      now: "In Committee", url: "/bill/2026/hb9901", more: 0, votes: [], study: null, ended: null, week: null,
      upcoming: [], items: [{ guid: "rc", date: TODAY, kind: "vote", milestone: true, url: "/bill/2026/hb9901",
        summary: "HB 9901 \u2014 Ought to Pass: MA RC 201-163 10/10/2026", rollcall }] }] });
}

// What a reader sees of an email's HTML: its words, without the head, the
// hidden inbox line or the markup, one block a line.
function visible(html) {
  return html.replace(/<head>[\s\S]*?<\/head>/, "").replace(/<div style="display:none[\s\S]*?<\/div>/, "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<(?:br|\/p|\/li|\/td|\/h1|\/h2|\/h3|\/tr)\b[^>]*>/g, "\n").replace(/<[^>]+>/g, "")
    .replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&").replace(/[ \t]+/g, " ");
}
const unlinked = html => visible(html.replace(/<a\b[^>]*>[\s\S]*?<\/a>/g, " "));

// ---- the header ---------------------------------------------------------------------------
test("every email opens with the site's header: the mark beside the name, at the site's size", () => {
  // The drawing in the site header's 33x56 box, with 4px of white tile
  // around it (build_brand.mail_mark), so dark mode cannot hide it.
  assert.deepEqual([MARK.width, MARK.height], [41, 64], "the site header's 33 by 56, and the tile's 4px");
  assert.equal(MARK.path, "/mail-mark.png", "the emails' own copy, on its white tile, not the site's mask");
  for (const [name, m] of Object.entries(everyEmail())) {
    const head = new RegExp(`<td valign="middle" style="[^"]*"><img src="${SITE.replace(/\./g, "\\.")}/mail-mark\\.png" ` +
      `width="41" height="64" alt="" style="[^"]*width:41px;height:64px[^"]*"></td>` +
      `<td valign="middle" style="[^"]*font-size:22px[^"]*"><a href="${SITE.replace(/\./g, "\\.")}/" ` +
      `[^>]*>Granite Record</a></td></tr></table>`);
    assert.match(m.html, head, `${name}: the mark and the name side by side, as the site's header`);
    assert.ok(m.html.indexOf("mail-mark.png") < m.html.indexOf("</td></tr><tr>"), `${name}: before anything else`);
    assert.doesNotMatch(m.html, /\.svg/, `${name}: Gmail shows no SVG`);
    assert.doesNotMatch(m.html, /letter-spacing:\.06em;text-transform:uppercase[^>]*>Granite Record</,
      `${name}: the old small-capitals line is gone`);
  }
});

// ---- accessibility (22 October 2026) ----------------------------------------------------------
// What a screen reader and a reader who enlarges nothing meet in every email.
test("every email can be read without seeing it, and without small type", () => {
  for (const [name, m] of Object.entries(everyEmail())) {
    const h = m.html;
    assert.match(h, /^<!doctype html><html lang="en">/, `${name}: says its language`);
    assert.ok(h.includes(`<title>${m.subject.replace(/&/g, "&amp;").replace(/'/g, "&#39;")
      .replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</title>`),
      `${name}: its title is its subject`);
    for (const img of h.match(/<img\b[^>]*>/g) || []) {
      assert.match(img, /\salt="[^"]*"/, `${name}: an image with no alt: ${img}`);
    }
    // A link a screen reader can name: words in it, or an image that has some.
    for (const [, inner] of h.matchAll(/<a\b[^>]*>([\s\S]*?)<\/a>/g)) {
      const words = inner.replace(/<img\b[^>]*\balt="([^"]*)"[^>]*>/g, " $1 ").replace(/<[^>]+>/g, "").trim();
      assert.ok(words, `${name}: a link with nothing to read: ${inner.slice(0, 80)}`);
    }
    // Nothing a reader sees is set under 14px; the hidden preheader is not seen.
    const seen = h.replace(/<div style="display:none[\s\S]*?<\/div>/, "");
    for (const [, px] of seen.matchAll(/font-size:(\d+)px/g)) {
      assert.ok(Number(px) >= 14, `${name}: ${px}px type`);
    }
    // Headings in order: at most one h1, and no level skipped below it.
    const levels = [...h.matchAll(/<h([1-6])\b/g)].map(x => Number(x[1]));
    assert.ok(levels.filter(l => l === 1).length <= 1, `${name}: more than one h1`);
    levels.forEach((l, i) => assert.ok(l <= (i ? levels[i - 1] : 1) + 1,
      `${name}: an h${l} after ${i ? `an h${levels[i - 1]}` : "nothing"}`));
    // Every layout table says it is one, so a screen reader does not read it as data.
    for (const t of h.match(/<table\b[^>]*>/g) || []) {
      assert.match(t, /role="presentation"/, `${name}: a table without role="presentation"`);
    }
  }
});

test("a daily or weekly's day is its one heading of its own, above the sections", () => {
  for (const [name, m] of Object.entries(everyEmail())) {
    if (!["daily", "weekly"].includes(name)) continue;
    assert.match(m.html, /<h1 style="[^"]*">(Daily|Weekly) update — [^<]+<\/h1>/, `${name}: the day is the h1`);
  }
});

// ---- the palette --------------------------------------------------------------------------
const lum = hex => {
  const c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

test("the palette survives a client's dark mode: light declared, white ground everywhere, dark ink only", () => {
  const { white, pine } = PALETTE;
  for (const [name, m] of Object.entries(everyEmail())) {
    assert.match(m.html, /<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">/);
    assert.match(m.html, new RegExp(`<body style="[^"]*background:${white}[^"]*" bgcolor="${white}">`));
    // The vote bar (22 October 2026) is the one ground besides: the ring's two
    // inks, in cells that hold no words and that a screen reader is not read.
    const bars = m.html.match(/<table role="presentation" aria-hidden="true"[\s\S]*?<\/table>/g) || [];
    for (const b of bars) {
      assert.equal(b.replace(/<[^>]+>/g, "").replace(/&nbsp;/g, ""), "", `${name}: words in the vote bar`);
      for (const [, bg] of b.matchAll(/background:(#[0-9A-Fa-f]{6})/g))
        assert.ok(Object.values(VOTE_INK).includes(bg.toUpperCase()), `${name}: a bar of ${bg}`);
    }
    const unbarred = bars.reduce((h, b) => h.replace(b, ""), m.html);
    for (const [, bg] of unbarred.matchAll(/background(?:-color)?:(#[0-9A-Fa-f]{6})/g))
      assert.ok([white, pine].includes(bg.toUpperCase()), `${name}: a ground of ${bg}`);
    let onPine = 0;
    for (const [, fg] of m.html.matchAll(/(?<![-\w])color:(#[0-9A-Fa-f]{6})/g)) {
      if (fg.toUpperCase() === white) { onPine++; continue; }
      assert.ok(Object.values(PALETTE).includes(fg.toUpperCase()), `${name}: ${fg} is not the site's`);
      assert.ok(contrast(fg, white) >= 4.5, `${name}: ${fg} is ${contrast(fg, white).toFixed(2)}:1 on white`);
    }
    // White ink only on the pine button, where it reads.
    const buttons = (m.html.match(new RegExp(`<td bgcolor="${pine}"[^>]*><a [^>]*color:${white}`, "g")) || []).length;
    assert.equal(onPine, buttons, `${name}: white text off the button`);
    assert.ok(contrast(white, pine) >= 4.5);
    assert.doesNotMatch(m.html, /<div style="[^"]*border/, `${name}: boxes are tables, as Outlook draws them`);
  }
});

// ---- links --------------------------------------------------------------------------------
test("every bill, law, legislator and committee an email names links to its page", () => {
  for (const m of [digest("weekly"), digest("daily", "2026-10-07")]) {
    const rest = unlinked(m.html);
    assert.doesNotMatch(rest, /\b(?:HB|SB) \d{3,4}/, "a bill named without its link");
    assert.doesNotMatch(rest, /House Example Committee|Rep\. Pat Example|RSA 91-A/);
    assert.match(m.html, /<a href="https:\/\/graniterecord\.org\/committee\/H90"[^>]*>House Example Committee<\/a>/);
  }
  // A law's items, a committee's day, and a bill that has since concluded
  // and is no longer in current.json but whose item carries its page.
  const law = { key: "law:91-A", kind: "law", ref: "91-A", label: "RSA 91-A: Access to Governmental Records",
    url: "/laws/91-a", title: "", now: "", more: 0, votes: [], study: null, ended: null, week: null, upcoming: [],
    items: [
      { guid: "a", date: "2026-10-07", kind: "exec", summary: "HB 9903-FN — Executive Session: 10/07/2026",
        plain: "HB 9903-FN — Executive session, 10:00 a.m., Granite Place 229", url: "/bill/2026/hb9903" },
      { guid: "b", date: "2026-10-06", kind: "action", summary: "HB 9950 — Amends RSA 91-A:4 and RSA 674",
        url: "/bill/2026/hb9950" }] };
  const cmte = { key: "committee:H90", kind: "committee", ref: "H90", label: "House Example Committee",
    url: "/committee/H90", title: "", now: "", more: 0, votes: [], study: null, ended: null, week: null,
    upcoming: [], items: [{ guid: "c", date: "2026-10-05", kind: "sitting",
      summary: "House Example Committee — October 5, 2026", plain: "Executive session on HB 9901 and HB 9977",
      url: "/committee/H90" }] };
  const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, sections: [law, cmte],
    names: pageNames(CURRENT), ...LINKS });
  const link = (path, name) => new RegExp(`<a href="https://graniterecord\\.org${path}"[^>]*>${name}</a>`);
  assert.match(m.html, link("/bill/2026/hb9903", "HB 9903-FN"));
  assert.match(m.html, link("/bill/2026/hb9950", "HB 9950"), "a concluded bill by its item's page");
  assert.match(m.html, link("/laws/91-a", "RSA 91-A"), "a law named inside a line");
  assert.match(m.html, link("/bill/2026/hb9901", "HB 9901"), "a bill in a committee's day, by current.json");
  assert.match(m.html, /HB 9977/, "a bill with no page the email knows is left as text, not linked wrongly");
  assert.doesNotMatch(m.html, />HB 9977<\/a>/);
});

// ---- what an email says -------------------------------------------------------------------
test("a digest opens on its day, with no sentence about the record or the build", () => {
  const d = digest("daily", "2026-10-07"), w = digest("weekly");
  assert.match(d.text, /^Daily update — Saturday, October 10, 2026\n\n/);
  assert.match(w.text, /^Weekly update — Saturday, October 10, 2026\n\n/);
  for (const m of [d, w]) {
    assert.doesNotMatch(m.text + m.html, /What changed on the record you follow|Your week on the record/);
    assert.match(visible(m.html), /^\s*Granite Record\s*\n[\s\S]*?(Daily|Weekly) update — Saturday, October 10, 2026/);
  }
});

test("plain headings: what each kind of record is, and what is coming up", () => {
  const w = digest("weekly");
  for (const h of ["Coming up", "Bills you follow", "Legislators you follow", "Committees you follow"]) {
    assert.match(w.html, new RegExp(`<h2 [^>]*>${h}</h2>`));
    assert.match(w.text, new RegExp(`^${h.toUpperCase()}$`, "m"));
  }
  assert.doesNotMatch(w.text + w.html, /week that was|the week ahead/i);
});

test("a reader's words: no build, proceeding, tonight or record you follow, and dates month first", () => {
  for (const [name, m] of Object.entries(everyEmail())) {
    const words = `${m.subject}\n${m.text.replace(/https?:\/\/\S+/g, "")}\n${visible(m.html)}`;
    assert.doesNotMatch(words, /last night|\bbuild\b|proceeding|tonight|records? you follow|You follow \d+ records/i, name);
    assert.doesNotMatch(words, /Report a problem with this page|record's page/, name);
    assert.doesNotMatch(words, /\b\d{4}-\d{2}-\d{2}\b/, `${name}: an ISO date`);
    assert.doesNotMatch(words, /\b\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4}/,
      `${name}: a day before its month`);
    assert.doesNotMatch(words, /colour|licence|organis|travell|favour|centre|honour|fortnight|\b(?:un)?tick/i,
      `${name}: a British spelling`);
  }
  assert.match(everyEmail().welcome.text, /paused through October 20, 2026\./);
  assert.match(everyEmail().welcome.text, /You now follow 3 things in all\./);
});

test("the footer names the report button only where a page has one", () => {
  for (const m of [digest("weekly"), everyEmail().welcome]) {
    assert.match(m.text, /use “Report a problem” on the bill's, legislator's or committee's page, or the feedback form/);
    assert.match(m.html, /on the bill&#39;s, legislator&#39;s or committee&#39;s page, or <a href="https:\/\/forms\.example\.com\/x"/);
  }
});

// A date as the site's components write it: mail.js cannot load the
// browser's components.js, so this loads it and holds the two to one answer.
test("an email's dates are components.js's dateWords, in its full, long and day forms", () => {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(readFileSync(new URL("../../src/pages/components.js", import.meta.url), "utf8") +
    ";this.dateWords=dateWords;", ctx);
  for (const d of ["2026-10-17", "2026-01-01", "2024-02-29", "2026-12-31", "2027-03-14", "2026-11-03"]) {
    assert.equal(longDate(d), ctx.dateWords(d, "full"), d);
    assert.equal(longDate(d, true), ctx.dateWords(d, "long"), d);
    assert.equal(shortDate(d, d), ctx.dateWords(d, "short"), d);
    assert.equal(shortDate(d, "1999-01-01"), ctx.dateWords(d), d);
    assert.equal(dayDate(d), ctx.dateWords(d, "day"), d);
  }
});

test("a committee's day says what kind of meeting it was, and every day is said once", () => {
  const w = digest("weekly");
  assert.match(w.text, /October 5, 2026 {2}Public hearing on HB 9903-FN\n/);
  assert.doesNotMatch(w.text, /House Example Committee — October 5, 2026/);
  assert.equal(dateOnce("HB 9903-FN — Executive Session: 10/06/2026 1:00 pm LOB 305", "2026-10-06"),
    "HB 9903-FN — Executive Session: 1:00 pm LOB 305");
  assert.equal(dateOnce("House Labor Committee — October 13, 2026", "2026-10-13"), "House Labor Committee");
  assert.equal(dateOnce("House Labor Committee — 13 October 2026", "2026-10-13"), "House Labor Committee");
  assert.equal(dateOnce("Public Hearing: 10/14/2026 10:00 am LOB 305", "2026-10-06"),
    "Public Hearing: 10/14/2026 10:00 am LOB 305", "a meeting on another day keeps its date: that is the news");
});

// ---- a meeting set, in plain words --------------------------------------------------------
// The person, 17 October 2026: "emails can use plain words for hearing
// entries". meeting_cases.json is the table: preflight holds
// plain_action.meeting to each case's `meeting`, and these hold the email to
// its `words`, one test a form, each failing if the email goes back to the
// clerk's line.
const MEETINGS = JSON.parse(readFileSync(new URL("./meeting_cases.json", import.meta.url), "utf8")).cases;
const billWith = items => ({ key: "bill:2026/HB9903", kind: "bill", ref: "2026/HB9903", label: "HB 9903-FN",
  url: "/bill/2026/hb9903", title: "", now: "", items, votes: [], more: 0, study: null, ended: null,
  week: null, upcoming: [] });
const meetingItem = (c, extra = {}) => ({ guid: `m:${c.form}`, date: c.date, kind: "scheduled", milestone: true,
  summary: `HB 9903-FN — ${c.line}`, plain: "", url: "/bill/2026/hb9903",
  ...(c.meeting ? { meeting: { time: "", venue: "", state: "", ...c.meeting } } : {}), ...extra });

for (const c of MEETINGS) {
  test(`an email says a docket line in plain words where it sets a meeting: ${c.form}`, () => {
    const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, sections: [billWith([meetingItem(c)])],
      names: pageNames(CURRENT), ...LINKS });
    if (!c.meeting) {
      // A line the email does not word stays as the clerk wrote it -- under
      // its own bill without the bill's number again (the email pass, 29
      // October 2026).
      const line = dateOnce(c.line, c.date);
      assert.ok(m.text.includes(`  ${longDate(c.date)}  ${line.charAt(0).toUpperCase() + line.slice(1)}\n`), m.text);
      return;
    }
    assert.ok(m.text.includes(`  ${longDate(c.date)}  ${c.words}\n`),
      `the plain text lacks: ${c.words}\n${m.text}`);
    assert.ok(visible(m.html).includes(`${shortDate(c.date, TODAY)}\n${c.words}\n`),
      `the HTML lacks: ${c.words}`);
    const clerk = c.line.slice(c.line.indexOf(":") + 1).trim();
    assert.ok(!(m.text + visible(m.html)).includes(clerk), `the clerk's line is still printed: ${clerk}`);
    assert.doesNotMatch(m.text, /\b\d{1,2}\/\d{1,2}\/\d{2,4}\b|\b\d{1,2}:\d{2} ?(?:am|pm|AM|PM)\b|Scheduled:|==/,
      "a date, an hour or a mark in the clerk's form");
    // The contract carries it: the build's meeting passes changes.js as it is.
    const night = { format: 1, date: "2026-10-10", built: "2026-10-10T09:00:00Z", sitting_term: "2025-2026",
      new_by: "record-date", refs: { "bill:2026/HB9903": { items: [{ guid: "g", date: c.date, kind: "scheduled",
        summary: `HB 9903-FN — ${c.line}`, meeting: c.meeting }] } } };
    const r = checkNight(night, "2026-10-10");
    assert.deepEqual(r.notes, []);
    assert.equal(meetingWords(r.value.refs.get("bill:2026/HB9903").items[0].meeting, c.date), c.words);
  });
}

test("a meeting's day is said where no date stands beside it: the subject and the preheader", () => {
  const same = MEETINGS.find(c => c.form === "same day");
  const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, sections: [billWith([meetingItem(same)])],
    names: pageNames(CURRENT), ...LINKS });
  assert.equal(m.subject, "HB 9903-FN — Executive session set for Tuesday, October 6, 1:00 p.m., " +
    "Legislative Office Building 305");
  assert.match(m.text, /October 6, 2026 {2}Executive session set for 1:00 p\.m\., Legislative Office Building 305\n/,
    "beside its own date, the hour alone");
  // A meeting still to come is "set for", so it is not also "Scheduled:".
  const ahead = { ...same, date: "2026-10-14",
    meeting: { ...same.meeting, date: "2026-10-14", what: "public hearing" } };
  const later = digestEmail({ origin: SITE, frequency: "daily", date: TODAY,
    sections: [billWith([meetingItem(ahead)])], names: pageNames(CURRENT), ...LINKS });
  assert.match(later.text, /October 14, 2026 {2}Hearing set for 1:00 p\.m\., Legislative Office Building 305\n/);
  assert.match(later.subject, /^HB 9903-FN — Hearing set for Wednesday, October 14, 1:00 p\.m\./);
  assert.doesNotMatch(later.text + later.subject, /Scheduled:/);
  // A meeting the contract does not know how to read is left out, with a note.
  const bad = checkNight({ format: 1, date: "2026-10-10", built: "2026-10-10T09:00:00Z", sitting_term: "2025-2026",
    new_by: "record-date", refs: { "bill:2026/HB9903": { items: [{ guid: "g", date: "2026-10-06", kind: "exec",
      summary: "HB 9903-FN — x", meeting: { what: "executive session", date: "10/13/2026" } }] } } }, "2026-10-10");
  assert.equal(bad.value.refs.get("bill:2026/HB9903").items[0].meeting, null);
  assert.equal(bad.notes.length, 1);
});

test("the week ahead lists what a meeting concerns without a run-on, and the sitting committee once", () => {
  const up = { date: "2026-10-14", time: "10:00", what: "executive session",
               committee: "House Example Committee", venue: "Granite Place 231" };
  const n = [9901, 9903, 9905, 9906, 9907, 9908, 9909];
  const section = (kind, key, label, url) => ({ key, kind, ref: key.split(":")[1], label, url, title: "",
    now: "", items: [], votes: [], more: 0, study: null, ended: null, week: { votes: 0, exec: 0 }, upcoming: [up] });
  const sections = [...n.map(x => section("bill", `bill:2026/HB${x}`, `HB ${x}`, `/bill/2026/hb${x}`)),
                    section("committee", "committee:H90", "House Example Committee", "/committee/H90")];
  const m = digestEmail({ origin: SITE, frequency: "weekly", date: TODAY, sections, names: pageNames(CURRENT), ...LINKS });
  assert.match(m.text, /Wednesday, October 14, 10:00 a\.m\.: Executive session, House Example Committee, Granite Place 231\. For HB 9901, HB 9903, HB 9905, HB 9906 and 3 more you follow\.\n/);
  assert.doesNotMatch(m.text, /HB \d+ and HB \d+ and|For [^\n]*House Example Committee/);
  assert.doesNotMatch(m.html, /For (?:(?!<\/span>).)*House Example Committee/);
  assert.match(m.subject, /^Your week: 1 meeting coming up/);
});

test("a ballot and its motion are said in the site's words", () => {
  const ballots = ["yes", "no", "excused", "not voting", "presiding", "Not Voting/Excused", "Not Voting/Not Exc…"];
  const votes = ballots.map((ballot, i) => ({ guid: `v${i}`, date: "2026-10-07", kind: "vote",
    summary: "HB 9903-FN — x", url: "/bill/2026/hb9903", milestone: true,
    vote: { ballot, result: "passed", tally: "11-9", bill: "HB 9903-FN", title: "",
            motion: "Ought to Pass with Amendment (OTPA, Pass the bill with changes)" } }));
  const s = { key: "member:990001", kind: "member", ref: "990001", label: "Rep. Pat Example (Merrimack 99)",
    url: "/legislator/pat-example-merrimack-99", title: "", now: "", items: [], votes, more: 0, study: null,
    ended: null, week: null, upcoming: [] };
  const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, sections: [s], ...LINKS });
  const said = ["voted yes", "voted no", "excused absence", "absent, not excused", "presiding",
                "excused absence", "absent, not excused"];
  const lines = m.text.split("\n").filter(l => / — On /.test(l));
  assert.deepEqual(lines.map(l => /: ([^;]+);/.exec(l)[1]), said);
  assert.match(lines[0], /On Ought to Pass with Amendment \(OTPA, Pass the bill with changes\): voted yes; the motion passed, 11-9$/);
  assert.doesNotMatch(m.text + m.html, /voted (?:not voting|excused|presiding)|Not Voting|On OTPA:/i);
  // The words are app.js's own for the three that are neither yes nor no.
  const app = readFileSync(new URL("../../src/pages/app.js", import.meta.url), "utf8");
  for (const w of ["Excused absence", "Absent, not excused", "Presiding"]) assert.ok(app.includes(`"${w}"`), w);
});

// ONLY A YES OR A NO IS "VOTED" ANYTHING (the review of 17 October 2026): the
// older terms' "No vote recorded" read "voted no vote recorded".
test("a ballot code that is not a yes or a no is never said as a vote", () => {
  assert.equal(ballotWords("No vote recorded"), "no vote recorded");
  assert.equal(ballotWords("NO VOTE RECORDED"), "no vote recorded");
  assert.equal(ballotWords("Paired"), "recorded as “Paired”");
  assert.equal(ballotWords(""), "no vote recorded");
  assert.equal(ballotWords("No"), "voted no");
  assert.equal(ballotWords("Nay"), "voted no");
  for (const code of ["No vote recorded", "Paired", "Not Present", "Abstain", "?"])
    assert.doesNotMatch(ballotWords(code), /^voted /, code);
});

test("an ending says what happened, and a follow's end in a reader's words", () => {
  const s = ended => ({ key: "bill:2026/HB9901", kind: "bill", ref: "2026/HB9901", label: "HB 9901",
    url: "/bill/2026/hb9901", title: "", now: "", items: [], votes: [], more: 0, study: null, ended,
    week: null, upcoming: [] });
  const told = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, ...LINKS,
    sections: [s({ how: "law", summary: "HB 9901 — Became law unsigned." })] });
  assert.equal(told.subject, "HB 9901 — Became law unsigned");
  assert.match(told.text, /HB 9901 — Became law unsigned\. There will be no more updates on it, so it has been taken off what you follow\./);
  const bare = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, ...LINKS,
    sections: [s({ how: "done", summary: "" })] });
  assert.match(bare.text, /HB 9901 has concluded\./);
  assert.doesNotMatch(bare.text + told.text, /finished its course|This follow has ended|a record that has finished/);
});

test("the plain text says what the HTML says", () => {
  for (const m of [digest("daily", "2026-10-07"), digest("weekly")]) {
    const v = visible(m.html).replace(/ \n/g, "\n");
    let dated = 0;
    for (const line of m.text.split("\n")) {
      const e = /^ {2}(\w+ \d{1,2}, \d{4}) {2}(.+)$/.exec(line);
      const ballot = / — (On .+)$/.exec(line);
      if (ballot) {
        // A roll call is laid out apart in each: the HTML puts the ballot
        // under the bill, the text after it.
        assert.ok(v.includes(ballot[1]), `the HTML lacks: ${ballot[1]}`);
      } else if (e) {
        dated++;
        // The HTML sets the date short in a column of its own (22 October
        // 2026): "Oct 7" beside the words, the year only when it differs.
        const [mo, d, y] = e[1].replace(",", "").split(" ");
        const short = `${mo.slice(0, 3)} ${d}`;
        assert.ok(v.includes(`${short}\n${e[2]}\n`) || v.includes(`${short}, ${y}\n${e[2]}\n`),
          `the HTML lacks: ${short} / ${e[2]}`);
      } else if (/^[A-Z][A-Z ]+$/.test(line)) {
        assert.ok(v.toUpperCase().includes(line), `the HTML lacks the heading ${line}`);
      }
    }
    assert.ok(dated >= 3, "the dated entries were compared");
    assert.ok(v.includes(m.text.split("\n")[0]), "the dateline");
  }
});

// ---- testifying (22 October 2026) -----------------------------------------------------------
// The person: "emails include updates for when testimony has opened for a
// certain bill and when it closes, with a similar button to click to go
// straight to the testify page", and, asked when it closes, "both": the day
// before the hearing and the morning of it. And on 26 October 2026: "Emails
// should stay in sync with how the site displays the testify button" -- the
// hearings it counts, which the build marks with "form", and the words of
// its live pane (preflight's _testify_email_in_sync draws both).
test("a bill's testimony is told when its hearing is set, the day before it and the day of it", () => {
  const up = CURRENT.upcoming.get("bill:2026/HB9903");
  const set = { meeting: { what: "public hearing", date: "2026-10-14" } };
  const phase = (...a) => testifyFor(...a)?.phase ?? null;
  assert.equal(phase("bill", up, [set], "daily", "2026-10-10"), "open", "the night it was set");
  assert.equal(phase("bill", up, [], "daily", "2026-10-10"), null, "days away and nothing new: nothing");
  assert.equal(phase("bill", up, [], "daily", "2026-10-13"), "eve");
  assert.equal(phase("bill", up, [set], "daily", "2026-10-13"), "eve", "set the day before: one block, the closing one");
  assert.equal(phase("bill", up, [], "daily", "2026-10-14"), "day");
  assert.equal(phase("bill", up, [], "daily", "2026-10-15"), null, "after the hearing");
  assert.equal(phase("bill", up, [], "weekly", "2026-10-13"), null, "a weekly has it in its week ahead");
  assert.equal(phase("bill", up, [set], "weekly", "2026-10-10"), "open");
  assert.equal(phase("topic", up, [set], "daily", "2026-10-10"), null, "a bill's own follower only");
  assert.equal(phase("bill", up, [{ meeting: { ...set.meeting, state: "cancelled" } }], "daily", "2026-10-10"),
    null, "a cancelled hearing opens nothing");
  // The build's mark decides: a hearing the bill's Testify does not count as
  // live -- a bill that can no longer be heard, a meeting that is not a
  // public hearing -- carries none, and is not told.
  assert.equal(phase("bill", up.map(u => ({ ...u, form: "" })), [], "daily", "2026-10-14"), null,
    "a row without the build's mark is told nothing");
  assert.equal(phase("bill", up.map(u => ({ ...u, form: "" })), [set], "daily", "2026-10-10"), null);
  // A hearing on a proposed amendment, set that night: the docket's line, as
  // plain_action.meeting hands it over, is a hearing set.
  const amd = up.map(u => ({ ...u, amendment: "a proposed non-germane amendment (2026-0422h)",
                             amendment_num: "2026-0422h" }));
  assert.equal(phase("bill", amd, [{ meeting: { what: "public hearing on non-germane amendment 2026-0422h",
    date: "2026-10-14" } }], "daily", "2026-10-10"), "open", "the night a hearing on an amendment was set");
  assert.deepEqual(testifyFor("bill", up, [], "daily", "2026-10-14"), { phase: "day", chamber: "H",
    date: "2026-10-14", time: "10:00", committee: "House Example Committee", venue: "Legislative Office Building 305",
    amendment: "", amendment_num: "" });
  assert.deepEqual(testifyFor("bill", amd, [], "daily", "2026-10-13"), { phase: "eve", chamber: "H",
    date: "2026-10-14", time: "10:00", committee: "House Example Committee", venue: "Legislative Office Building 305",
    amendment: "a proposed non-germane amendment (2026-0422h)", amendment_num: "2026-0422h" });
});

// The audit of 25 October 2026 (M2): the Senate calls its hearings "hearing",
// the House "public hearing", and the emails read the House's word alone, so a
// Senate hearing told no follower that testimony was open.
test("a Senate hearing takes testimony as a House public hearing does, in the daily and the week ahead", () => {
  const senate = rows => rows.map(r => r.what === "public hearing"
    ? { ...r, what: "hearing", committee: "Senate Example Committee", ...(r.form ? { form: "S" } : {}) } : r);
  const current = { ...CURRENT, upcoming: new Map([...CURRENT.upcoming].map(([k, rows]) => [k, senate(rows)])) };
  const up = current.upcoming.get("bill:2026/HB9903");
  assert.deepEqual(testifyFor("bill", up, [], "daily", "2026-10-14"), { phase: "day", chamber: "S",
    date: "2026-10-14", time: "10:00", committee: "Senate Example Committee", venue: "Legislative Office Building 305",
    amendment: "", amendment_num: "" });
  assert.equal(testifyFor("bill", up, [{ meeting: { what: "hearing", date: "2026-10-14" } }], "daily",
    "2026-10-10")?.phase, "open", "the night a Senate hearing was set");
  const sections = collect({ follows: FOLLOWS, nights: NIGHTS.filter(n => n.date > "2026-10-02"), cursor: {},
    current, frequency: "weekly", today: TODAY });
  const weekly = digestEmail({ origin: SITE, frequency: "weekly", date: TODAY, sections,
    names: pageNames(current), ...LINKS });
  const ahead = weekly.html.slice(weekly.html.indexOf(">Coming up<"));
  assert.ok(ahead.includes(TESTIFY_FORMS.S[1]), "the Senate form beside the Senate hearing");
  assert.match(visible(ahead), /Wednesday, October 14, 2026\nSenate Example Committee\nHB 9903-FN\n/);
});

// A daily on the day before and the day of the hearing, with nothing else new.
function onDay(today, current = CURRENT) {
  const follows = [{ ...parseKey("bill:2026/HB9903"), fh: "x" }];
  const sections = collect({ follows, nights: [], cursor: {}, current, frequency: "daily", today });
  return digestEmail({ origin: SITE, frequency: "daily", date: today, sections, names: pageNames(current), ...LINKS });
}

test("the day before and the day of a hearing, the daily says what the site's Testify pane says, and leads with it", () => {
  const label = CURRENT.followable.get("bill:2026/HB9903").label;
  const url = TESTIFY_FORMS.H[1];
  const eve = onDay("2026-10-13"), day = onDay("2026-10-14");
  assert.equal(eve.subject, `Public hearing tomorrow on ${label}: testify online`);
  assert.equal(day.subject, `Public hearing today on ${label}: testify online`);
  for (const m of [eve, day]) {
    const words = visible(m.html).replace(/\u00a0/g, " ");
    // The button's words, the hearing and when it closes, a rule, what to
    // choose, the form, and the three values, a line each: the pane's.
    const block = ["Testify until Oct 14",
      `The public hearing on ${label} is scheduled for Wednesday, October 14 at 10:00 AM in Legislative ` +
      "Office Building 305. Public testimony is open until midnight the day of the hearing.",
      "To submit online testimony, choose the hearing date, committee, and bill number as shown below.",
      "Submit Online Testimony", "Wednesday, October 14, 2026", "House Example Committee", label];
    // Each after the one before it, in the order the pane says them.
    const inOrder = s => block.reduce((at, b) => at < 0 ? at : s.indexOf(b, at), s.indexOf("Testify until"));
    assert.ok(inOrder(words) >= 0, `the block, in order: ${words}`);
    assert.match(m.html, /<hr style="border:0;border-top:1px solid [^"]+">\s*<p style="margin:0">To submit online/,
      "a rule between the hearing and how to submit, as the pane's");
    for (const old of ["In practice", "Anyone may sign in", "On the form", "online testimony</a>",
                       "public hearing is tomorrow", "’s public hearing"])
      assert.ok(!m.html.includes(old) && !m.text.includes(old), `the block still says ${old}`);
    // The button: the chamber's own form, as a pine button.
    assert.match(m.html, new RegExp(`<td bgcolor="${PALETTE.pine}"[^>]*><a href="${url.replace(/[.?]/g, "\\$&")}"` +
      "[^>]*>Submit Online Testimony</a>"));
    // The plain text carries the same, in the same order.
    const text = m.text.replace(/\u00a0/g, " ");
    assert.ok(inOrder(text) >= 0, `the plain text's block, in order: ${text}`);
    assert.ok(m.text.includes(`Submit Online Testimony: ${url}`), "the plain text carries the form too");
  }
});

test("a hearing on a proposed amendment says so, its number opening it on the Bill Text tab", () => {
  const amend = (num, keep = true) => ({ ...CURRENT, upcoming: new Map([...CURRENT.upcoming].map(([k, rows]) =>
    [k, rows.map(r => r.form ? { ...r, amendment: `a proposed non-germane amendment (${num})`,
                                  ...(keep ? { amendment_num: num } : {}) } : r)])) });
  const m = onDay("2026-10-13", amend("2026-0422h"));
  const words = visible(m.html).replace(/\u00a0/g, " ");
  assert.ok(words.includes("The public hearing on a proposed non-germane amendment (2026-0422h) to HB 9903-FN " +
    "is scheduled for Wednesday, October 14 at 10:00 AM in Legislative Office Building 305."), words);
  assert.match(m.html, /\(<a href="https:\/\/graniterecord\.org\/bill\/2026\/hb9903\/text#amendment-2026-0422h"[^>]*>2026-0422h<\/a>\) to <a href="https:\/\/graniterecord\.org\/bill\/2026\/hb9903"/,
    "the number opens the amendment on the bill's Bill Text tab");
  assert.ok(m.text.includes("The public hearing on a proposed non-germane amendment (2026-0422h) to HB 9903-FN is"));
  // Where the tab cannot open it (no amendment_num), the number is words alone.
  const plain = onDay("2026-10-13", amend("2026-0422h", false));
  assert.ok(visible(plain.html).includes("(2026-0422h) to HB 9903-FN"));
  assert.doesNotMatch(plain.html, /#amendment-/);
  // The weekly's week ahead names it too, a row of its own.
  const current = amend("2026-0422h");
  const sections = collect({ follows: FOLLOWS, nights: NIGHTS.filter(n => n.date > "2026-10-02"), cursor: {},
    current, frequency: "weekly", today: TODAY });
  const weekly = digestEmail({ origin: SITE, frequency: "weekly", date: TODAY, sections, names: pageNames(current), ...LINKS });
  const ahead = weekly.html.slice(weekly.html.indexOf(">Coming up<"));
  assert.match(visible(ahead), /Public hearing on a proposed non-germane amendment \(2026-0422h\)/);
  assert.match(ahead, /#amendment-2026-0422h/);
});

test("the night a hearing is set, the daily says testimony is open; the weekly puts the form in its week ahead", () => {
  const daily = digest("daily", "2026-10-02");
  const words = visible(daily.html).replace(/\u00a0/g, " ");
  assert.ok(words.includes("Testify until Oct 14"), "open, the night it was set");
  assert.ok(words.includes("Public testimony is open until midnight the day of the hearing."));
  const weekly = digest("weekly");
  assert.doesNotMatch(weekly.html, /Testify until/, "the weekly says it once, in its week ahead");
  const ahead = weekly.html.slice(weekly.html.indexOf(">Coming up<"));
  assert.ok(ahead.includes(TESTIFY_FORMS.H[1]), "the House form beside the public hearing");
  assert.match(visible(ahead), /Public testimony is open until midnight the day of the hearing\. To submit online testimony, choose the hearing date, committee, and bill number as shown below\.\n?[^\n]*\n*Submit Online Testimony\n*[\s\S]*Wednesday, October 14, 2026\nHouse Example Committee\nHB 9903-FN\n/);
  assert.ok(!/Tuesday, October 13[^\n]*\n[^\n]*Submit Online Testimony/.test(visible(ahead)), "not beside an executive session");
  assert.match(weekly.text, /\n {4}Submit Online Testimony: https:[^\n]+\n {6}Wednesday, October 14, 2026\n {6}House Example Committee\n {6}HB 9903-FN\n/);
});

// The time as the site's pane says it: components.js's clock.
test("the testimony block's time is components.js's clock", () => {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(readFileSync(new URL("../../src/pages/components.js", import.meta.url), "utf8") +
    ";this.clock=clock;", ctx);
  for (const t of ["00:00", "09:05", "10:00", "11:59", "12:00", "12:30", "13:15", "23:59", "", "24:00", "x"])
    assert.equal(siteClock(t), ctx.clock(t), t);
});

// EMAIL FOLLOWING IS IN BETA UNTIL THE WEBINAR (the person, 26 October
// 2026). Every email says so, plain and HTML, through 10 November in Concord,
// and none does from the 11th: the email's own day where it has one.
test("every email says email following is in beta, until the day after the webinar", () => {
  const m = CURRENT.followable.get("bill:2026/HB9903");
  const each = today => ({
    confirmation: confirmationEmail({ origin: SITE, label: m.label, title: m.title, token: "T".repeat(43), today }),
    welcome: welcomeEmail({ origin: SITE, kind: "bill", label: m.label, title: m.title, url: m.url,
      frequency: "daily", ...LINKS, today }),
    newLink: newLinkEmail({ origin: SITE, ...LINKS, today }),
    daily: digestEmail({ origin: SITE, frequency: "daily", date: today, names: pageNames(CURRENT), ...LINKS,
      sections: collect({ follows: FOLLOWS, nights: NIGHTS, cursor: {}, current: CURRENT, frequency: "daily", today }) }),
    weekly: digestEmail({ origin: SITE, frequency: "weekly", date: today, names: pageNames(CURRENT), ...LINKS,
      sections: collect({ follows: FOLLOWS, nights: NIGHTS, cursor: {}, current: CURRENT, frequency: "weekly", today }) }),
    nothingNew: nothingNewEmail({ origin: SITE, frequency: "daily", date: today, nights: 1, ...LINKS }),
  });
  assert.equal(FOLLOW_BETA.until, "2026-11-11");
  for (const [day, said] of [["2026-10-26", true], ["2026-11-10", true], ["2026-11-11", false], ["2027-01-05", false]]) {
    for (const [name, e] of Object.entries(each(day))) {
      assert.equal(e.text.includes(FOLLOW_BETA.note), said, `${name} on ${day}: the plain text`);
      assert.equal(visible(e.html).includes(FOLLOW_BETA.note), said, `${name} on ${day}: the HTML`);
    }
  }
  assert.equal(betaNote("2026-11-10"), FOLLOW_BETA.note);
  assert.equal(betaNote("2026-11-11"), "");
});

test("a bill's status chip is coloured as the site colours it, on a bar, its word dark", () => {
  const ink = words => STATUS_INK[{ "Became Law": "law", Died: "done", "Interim Study": "study", Tabled: "table",
    Vetoed: "veto", Withdrawn: "done" }[words] || "active"];
  for (const now of ["Became Law", "Died", "Interim Study", "Tabled", "Vetoed", "Withdrawn", "In Committee"]) {
    const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, names: pageNames(CURRENT), ...LINKS,
      sections: [{ key: "bill:2026/HB9901", kind: "bill", ref: "2026/HB9901", label: "HB 9901", title: "", now,
        url: "/bill/2026/hb9901", more: 0, votes: [], study: null, ended: null, week: null, upcoming: [],
        items: [{ guid: "g", date: TODAY, kind: "action", summary: "HB 9901 — Introduced" }] }] });
    assert.match(m.html, new RegExp(`border-left:4px solid ${ink(now)};[^"]*color:${PALETTE.ink};[^"]*">${now}</span>`), now);
  }
});

// ---- a roll call, drawn (22 October 2026) ----------------------------------------------------
// The person: bill emails should have "similar elements to what's on the bill
// pages with the vote diagrams".
test("a floor roll call is drawn as the bill page's two sides, and said in words", () => {
  const m = voted(ROLLCALL);
  const bar = m.html.match(/<table role="presentation" aria-hidden="true"[\s\S]*?<\/table>/)[0];
  const cells = [...bar.matchAll(/<td width="(\d+)%" bgcolor="(#[0-9A-F]{6})"/g)].map(x => [Number(x[1]), x[2]]);
  assert.deepEqual(cells, [[55, VOTE_INK.yes], [45, VOTE_INK.no]], "yes then no, as wide as their share");
  const words = visible(m.html);
  assert.ok(/Yes 201\s*\n?\s*No 163/.test(words), "each side's count under its end");
  assert.ok(words.includes("Passed (183 needed). Yes: 190 Republicans, 11 Democrats. No: 150 Democrats, " +
    "13 Republicans."), words);
  assert.ok(m.text.includes("Yes 201, No 163. Passed (183 needed). Yes: 190 Republicans"), "the plain text says it too");
  // One side only: one cell, and a party of one is one member.
  const one = voted({ yeas: 1, nays: 0, passed: true, parties: [["L", 1, 0]] });
  const onebar = one.html.match(/<table role="presentation" aria-hidden="true"[\s\S]*?<\/table>/)[0];
  assert.equal((onebar.match(/<td /g) || []).length, 1, "no empty side");
  assert.ok(visible(one.html).includes("Passed. Yes: 1 Libertarian."));
  const failed = visible(voted({ ...ROLLCALL, passed: false, rule: "two thirds of those voting", need: 243 }).html);
  assert.ok(failed.includes("Failed (243 needed, two thirds of those voting)."), failed);
  // No roll call, no bar.
  assert.doesNotMatch(voted(undefined).html, /aria-hidden/);
});

// ---- the email pass (29 October 2026) ------------------------------------------------------
// The person, through the manager session: the emails "aren't actively wrong
// or bad, but definitely could use another pass at the layout and visuals to
// ensure the information is easy to parse". Each bill was told twice; a tally
// broke across two lines; the subject ran long; "Now" said the record's words
// where the site's chip says its own.
test("the email pass: each update once, a line of counts, and a short subject", () => {
  const bill = (n, items, extra = {}) => ({ key: `bill:2026/HB${n}`, kind: "bill", ref: `2026/HB${n}`,
    label: `HB ${n}`, url: `/bill/2026/hb${n}`, title: "", now: "", items, votes: [], more: 0, study: null,
    ended: null, week: null, upcoming: [], ...extra });
  const item = (n, i) => ({ guid: `g${n}${i}`, date: "2026-10-09", kind: "report", milestone: true,
    summary: `HB ${n} — Committee report: Ought to Pass, 14–0`, plain: "", url: `/bill/2026/hb${n}` });
  const sections = [9901, 9903, 9905, 9906].map(n => bill(n, [item(n, 1), item(n, 2)]));
  const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, sections, ...LINKS });
  assert.equal(m.subject, "8 updates on HB 9901, HB 9903 and 2 more");
  assert.doesNotMatch(m.text + visible(m.html), /at a glance/i, "no list that repeats the sections");
  assert.match(m.text, /^Daily update — [^\n]+\n\n8 updates on 4 bills\.\n/);
  assert.equal((visible(m.html).match(/Committee report: Ought to Pass/g) || []).length, 8,
    "each update told once");
  assert.doesNotMatch(m.text, /October 9, 2026 {2}HB 99\d\d — /, "a bill's line does not name its bill again");
  // A tally is held on one line wherever it is printed in the HTML, and no
  // address or attribute is touched.
  assert.match(m.html, /<span style="white-space:nowrap">14–0<\/span>/);
  assert.equal(keepWhole('<a href="/bill/2026/hb9901?x=10-4">10-4 and 201 - 163</a>'),
    '<a href="/bill/2026/hb9901?x=10-4"><span style="white-space:nowrap">10-4</span> and ' +
    '<span style="white-space:nowrap">201 - 163</span></a>');
  // One update with words of its own is still said in them.
  const one = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, ...LINKS,
    sections: [bill(9901, [item(9901, 1)])] });
  assert.equal(one.subject, "HB 9901 — Committee report: Ought to Pass, 14–0");
  // A hearing today on a bill the reader may testify on still leads.
  const day = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, ...LINKS, sections: [
    ...sections, bill(9907, [], { testify: { phase: "day", chamber: "H", date: TODAY, time: "10:00",
      committee: "House Example Committee", venue: "Legislative Office Building 305" } })] });
  assert.match(day.subject, /^Public hearing today on HB 9907: testify online, and 8 updates$/);
});

test("the email pass: Now says the site's chip word, coloured by the record's", () => {
  // components.card_word's words, from chips.json "short" and Title Case.
  assert.equal(chipWord("In committee"), "In Committee");
  assert.equal(chipWord("Passed, awaiting the governor"), "To the Governor");
  assert.equal(chipWord("Passed both chambers, goes to the voters in November"), "To the Voters");
  assert.equal(chipWord("Interim Study"), "Interim Study");
  assert.equal(chipWord("Became Law"), "Became Law");
  const chips = JSON.parse(readFileSync(new URL("../../src/pages/words/chips.json", import.meta.url), "utf8"));
  for (const [record, card] of Object.entries(chips.short)) assert.equal(chipWord(record), card, record);
  const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, ...LINKS, sections: [{
    key: "bill:2026/HB9901", kind: "bill", ref: "2026/HB9901", label: "HB 9901", url: "/bill/2026/hb9901",
    title: "", now: "In committee", votes: [], more: 0, study: null, ended: null, week: null, upcoming: [],
    items: [{ guid: "g", date: "2026-10-09", kind: "report", milestone: true, url: "/bill/2026/hb9901",
              summary: "HB 9901 — Committee report: Ought to Pass, 14–0", plain: "" }] }] });
  assert.match(m.text, /\n {2}Now: In Committee\n/);
  assert.match(visible(m.html), /Now\s*In Committee/);
});

// The review of the email pass (29 October 2026).
const PREHEADER = /<div style="display:none;max-height:0;[^"]*">([^<]*)<\/div>/;
const sec = (n, items, extra = {}) => ({ key: `bill:2026/HB${n}`, kind: "bill", ref: `2026/HB${n}`,
  label: `HB ${n}`, url: `/bill/2026/hb${n}`, title: "", now: "", items, votes: [], more: 0, study: null,
  ended: null, week: null, upcoming: [], ...extra });
const rpt = (n, i, date = "2026-10-09") => ({ guid: `r${n}${i}`, date, kind: "report", milestone: true,
  summary: `HB ${n} — Committee report: Ought to Pass, 14–0`, plain: "", url: `/bill/2026/hb${n}` });
const hearing = phase => ({ phase, chamber: "H", date: phase === "day" ? TODAY : "2026-10-11", time: "10:00",
  committee: "House Example Committee", venue: "Legislative Office Building 305" });

test("the email pass: the chip word is components.js's cardWord, for every word the site knows", () => {
  const read = f => JSON.parse(readFileSync(new URL(`../../src/pages/words/${f}`, import.meta.url), "utf8"));
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(`var WORDBOOK=${JSON.stringify({ chips: read("chips.json"), meeting_kinds: read("meeting_kinds.json") })};` +
    readFileSync(new URL("../../src/pages/components.js", import.meta.url), "utf8") + ";this.cardWord=cardWord;", ctx);
  const chips = read("chips.json");
  const words = [...Object.keys(chips.short), ...Object.keys(chips.chip), ...chips.short_passed,
    ...chips.short_prefix.map(([p]) => `${p} in November`), "Filed as a request", "INEXPEDIENT TO LEGISLATE",
    "In Committee", "Passed House", "To the Governor"];
  for (const w of words) assert.equal(chipWord(w), ctx.cardWord(w, ""), w);
});

test("the email pass: the preheader says what the subject does not", () => {
  const sections = [9901, 9903].map(n => sec(n, [rpt(n, 1), rpt(n, 2)]));
  const many = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, sections, ...LINKS });
  assert.equal(many.subject, "4 updates on HB 9901 and HB 9903");
  assert.equal(PREHEADER.exec(many.html)[1], "HB 9901 — Committee report: Ought to Pass, 14–0");
  // One update is its own subject, so the preheader is the count, not it again.
  const one = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, ...LINKS, sections: [sec(9901, [rpt(9901, 1)])] });
  assert.equal(one.subject, "HB 9901 — Committee report: Ought to Pass, 14–0");
  assert.equal(PREHEADER.exec(one.html)[1], "1 update on 1 bill");
  // A hearing tomorrow leads the subject, and the preheader is the next news.
  const eve = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, ...LINKS,
    sections: [...sections, sec(9907, [], { testify: hearing("eve") })] });
  assert.equal(eve.subject, "Public hearing tomorrow on HB 9907: testify online, and 4 updates");
  assert.notEqual(PREHEADER.exec(eve.html)[1], "Public hearing tomorrow on HB 9907: testify online");
});

test("the email pass: a record with no update is neither counted nor named, but its hearing leads its list", () => {
  const sections = [sec(9901, [rpt(9901, 1), rpt(9901, 2)]), sec(9903, [rpt(9903, 1)]),
    sec(9907, [], { testify: hearing("open") })];
  const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, sections, ...LINKS });
  assert.equal(m.subject, "3 updates on HB 9901 and HB 9903");
  assert.match(m.text, /\n3 updates on 2 bills\.\n/);
  assert.ok(m.text.indexOf("HB 9907\n") < m.text.indexOf("HB 9901\n"), "the bill with testimony open comes first");
  // A weekly with nothing new and nothing coming up says so plainly.
  const quiet = digestEmail({ origin: SITE, frequency: "weekly", date: TODAY, ...LINKS, sections: [] });
  assert.equal(quiet.subject, "Your week to Saturday, October 10, 2026");
});

test("the email pass: an ending leads its record, and a bill's own name comes off however it is written", () => {
  const ended = sec(9902, [{ guid: "x", date: "2026-10-09", kind: "report", milestone: true, url: "/bill/2026/hb9902",
    summary: "HB 9902-FN — Committee report: Ought to Pass, 14–0", plain: "" },
    { guid: "y", date: "2026-10-12", kind: "scheduled", milestone: true, url: "/bill/2026/hb9902",
      summary: "HB 9902 — Conference committee report filed", plain: "" }],
    { label: "HB 9902 (2026)", ended: { how: "law", summary: "HB 9902 — Signed into law." } });
  const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, ...LINKS, sections: [ended, sec(9901, [rpt(9901, 1)])] });
  const block = m.text.slice(m.text.indexOf("HB 9902 (2026)"));
  assert.ok(block.indexOf("Signed into law") < block.indexOf("Committee report"), "the ending before the rows");
  assert.match(block, /October 9, 2026 {2}Committee report: Ought to Pass, 14–0\n/, "the -FN number comes off too");
  assert.match(block, /October 12, 2026 {2}Scheduled: Conference committee report filed\n/, "and after Scheduled:");
  assert.match(m.subject, /^4 updates on HB 9902 \(2026\) and HB 9901$/, "two lines, the ending and one more");
});

test("the email pass: keepWhole holds tallies, and only between tags", () => {
  assert.equal(keepWhole("<p>passed, 201-163; 14–0</p>"),
    '<p>passed, <span style="white-space:nowrap">201-163</span>; <span style="white-space:nowrap">14–0</span></p>');
  assert.equal(keepWhole('<a title="11-9" href="/x?a=1-2">see</a>'), '<a title="11-9" href="/x?a=1-2">see</a>');
  assert.equal(keepWhole("<p>2026-0422h and &#8211; alone</p>"), "<p>2026-0422h and &#8211; alone</p>");
});
