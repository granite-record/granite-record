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
import { MARK, PALETTE, ballotWords, confirmationEmail, dateOnce, dayDate, digestEmail, longDate,
         meetingWords, newLinkEmail, pageNames, welcomeEmail } from "../../workers/follow/mail.js";
import { collect } from "../../workers/follow/sender.js";
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
  };
}

// What a reader sees of an email's HTML: its words, without the head, the
// hidden inbox line or the markup, one block a line.
function visible(html) {
  return html.replace(/<head>[\s\S]*?<\/head>/, "").replace(/<div style="display:none[\s\S]*?<\/div>/, "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<(?:br|\/p|\/li|\/td|\/h2|\/h3|\/tr)\b[^>]*>/g, "\n").replace(/<[^>]+>/g, "")
    .replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&").replace(/[ \t]+/g, " ");
}
const unlinked = html => visible(html.replace(/<a\b[^>]*>[\s\S]*?<\/a>/g, " "));

// ---- the header ---------------------------------------------------------------------------
test("every email opens with the site's header: the mark beside the name, sized, with alt text", () => {
  assert.deepEqual([MARK.width, MARK.height], [26, 44], "the site header's proportions, 99 by 168");
  for (const [name, m] of Object.entries(everyEmail())) {
    const head = new RegExp(`<img src="${SITE.replace(/\./g, "\\.")}/mark\\.png" width="26" height="44" ` +
      `alt="Granite Record logo" style="[^"]*width:26px;height:44px;[^"]*"></a></td>` +
      `<td valign="middle" style="[^"]*font-size:22px[^"]*"><a href="${SITE.replace(/\./g, "\\.")}/" ` +
      `[^>]*>Granite Record</a></td></tr></table>`);
    assert.match(m.html, head, `${name}: the mark and the name side by side, as the site's header`);
    assert.ok(m.html.indexOf("mark.png") < m.html.indexOf("</td></tr><tr>"), `${name}: before anything else`);
    assert.doesNotMatch(m.html, /\.svg/, `${name}: Gmail shows no SVG`);
    assert.doesNotMatch(m.html, /letter-spacing:\.06em;text-transform:uppercase[^>]*>Granite Record</,
      `${name}: the old small-capitals line is gone`);
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
    for (const [, bg] of m.html.matchAll(/background(?:-color)?:(#[0-9A-Fa-f]{6})/g))
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
      // A line the email does not word stays as the clerk wrote it.
      assert.ok(m.text.includes(`  ${longDate(c.date)}  HB 9903-FN — ${dateOnce(c.line, c.date)}\n`), m.text);
      return;
    }
    assert.ok(m.text.includes(`  ${longDate(c.date)}  HB 9903-FN — ${c.words}\n`),
      `the plain text lacks: ${c.words}\n${m.text}`);
    assert.ok(visible(m.html).includes(`${longDate(c.date)} — HB 9903-FN — ${c.words}\n`),
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

test("a meeting's day is said where no date stands beside it: the subject and at a glance", () => {
  const same = MEETINGS.find(c => c.form === "same day");
  const m = digestEmail({ origin: SITE, frequency: "daily", date: TODAY, sections: [billWith([meetingItem(same)])],
    names: pageNames(CURRENT), ...LINKS });
  assert.equal(m.subject, "HB 9903-FN — Executive session set for Tuesday, October 6, 1:00 p.m., " +
    "Legislative Office Building 305");
  assert.match(m.text, /October 6, 2026 {2}HB 9903-FN — Executive session set for 1:00 p\.m\., Legislative Office Building 305\n/,
    "beside its own date, the hour alone");
  // A meeting still to come is "set for", so it is not also "Scheduled:".
  const ahead = { ...same, date: "2026-10-14",
    meeting: { ...same.meeting, date: "2026-10-14", what: "public hearing" } };
  const later = digestEmail({ origin: SITE, frequency: "daily", date: TODAY,
    sections: [billWith([meetingItem(ahead)])], names: pageNames(CURRENT), ...LINKS });
  assert.match(later.text, /October 14, 2026 {2}HB 9903-FN — Hearing set for 1:00 p\.m\., Legislative Office Building 305\n/);
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
  assert.match(m.subject, /^Your week: 1 committee meeting coming up/);
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
        assert.ok(v.includes(`${e[1]} — ${e[2]}`), `the HTML lacks: ${e[1]} — ${e[2]}`);
      } else if (/^[A-Z][A-Z ]+$/.test(line)) {
        assert.ok(v.toUpperCase().includes(line), `the HTML lacks the heading ${line}`);
      }
    }
    assert.ok(dated >= 3, "the dated entries were compared");
    assert.ok(v.includes(m.text.split("\n")[0]), "the dateline");
  }
});
