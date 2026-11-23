// The owner's Your input tab, on the page (workers/bench/page.js): the page's own script run
// in a context of its own, on a stub of its elements and of fetch, as page.test.js runs it.
// The tab for her link alone, with the number waiting; the list by section, a waiting row and
// an answered one; an entry and its parts; every value escaped, and a link the list's format
// refuses never drawn as one; an answer required, sent with its note, and the list back with
// the row answered; her latest answer and note shown again; Escape for Back, keeping what she
// typed; the quiet count; and a contributor's page with no tab, asking nothing of it. Every
// token and every link here is made up: a claude.ai artifact's is one letter over and over,
// and preflight's _no_artifact_links refuses any other in a tracked file.

import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { LINK_RULE, SCRIPT, benchPage } from "../../workers/bench/page.js";
import { TIMEZONE } from "../../workers/follow/site.gen.js";

const TOKEN = "C".repeat(40) + "ccc";
const OWNER = { role: "owner", state: "active", queue: "mix", queues: [], items: [], progress: null, far: [], asks: 3 };
const SAM = { role: "contributor", state: "active", queue: "mix", queues: [], items: [], progress: null, far: [] };
const card = (o = {}) => ({ section: "In the update waiting for your word", title: "Navigation in two rows",
  what: "Each section's pages now sit in a second row.\n\nOn a phone the row scrolls.\nSwipe it.",
  where: [{ label: "The home page on the preview", url: "https://dry-run.graniterecord.pages.dev/" },
          { label: "The design you approved", url: "https://claude.ai/artifact/AAAAAAAAAAAAAAAAAAAAAA" }],
  question: "Does the new navigation read right on a computer and on a phone?",
  answers: { yes: "Looks right", no: "Needs changes", unsure: "Let’s discuss" }, recommended: "yes", added: "2026-11-23",
  ...o });
const LIST = [
  { key: "nav-rows", card: card(), answer: null },
  { key: "map-dots", card: card({ title: "Map dots", recommended: null }),
    answer: { answer: "no", note: "Too faint on a phone.", at: "2026-11-22T19:04:12.345Z" } },
  { key: "a-note", card: card({ section: "Anything else", title: "Anything else", where: [], answers: { yes: "Save the note" },
                                recommended: null }), answer: null },
];

function run({ view = OWNER, asks = LIST, answer = null } = {}) {
  const sent = [], els = {}, on = {};
  const el = id => (els[id] ||= { id, hidden: id === "forget", innerHTML: "", textContent: "", value: "", className: "",
    style: {}, dataset: {}, attrs: {}, focused: 0, classList: { add() {}, remove() {} },
    toggleAttribute(k, v) { if (v) this.attrs[k] = ""; else delete this.attrs[k]; },
    setAttribute(k, v) { this.attrs[k] = String(v); }, appendChild() {}, focus() { this.focused++; }, addEventListener() {} });
  el("forget");
  const store = { "gr.bench": TOKEN };
  const storage = m => ({ getItem: k => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); },
                          removeItem: k => { delete m[k]; } });
  const state = { asks: JSON.parse(JSON.stringify(asks)) };
  const respond = (path, body) => {
    if (path === "/api/bench/next") return { status: 200, data: view };
    if (path === "/api/bench/asks" && body.action === "list") return { status: 200, data: { asks: state.asks, waiting: 2 } };
    if (path === "/api/bench/asks" && body.action === "answer") {
      if (answer) return answer(body, state);
      const k = state.asks.find(x => x.key === body.key);
      k.answer = { answer: body.answer, note: body.note, at: "2026-11-23T20:00:00.000Z" };
      return { status: 200, data: { saved: { answer: body.answer }, asks: state.asks, waiting: 1 } };
    }
    return { status: 404, data: null };
  };
  const ctx = vm.createContext({
    location: { hash: "", pathname: "/bench", search: "", origin: "https://example.test", reload() {} },
    history: { replaceState() {} }, localStorage: storage(store), sessionStorage: storage({}),
    document: { hidden: false, head: { appendChild() {} }, createElement: () => ({}), querySelectorAll: () => [],
                getElementById: id => el(id), addEventListener: (t, f) => { on[t] = f; } },
    window: { addEventListener() {} }, navigator: {}, confirm: () => true,
    setInterval: () => 0, setTimeout: () => 0, clearTimeout() {},
    fetch: (path, opts) => {
      const body = JSON.parse(opts.body);
      sent.push({ path, body });
      const r = respond(path, body);
      return Promise.resolve({ status: r.status, text: () => Promise.resolve(JSON.stringify(r.data)) });
    },
  });
  vm.runInContext(SCRIPT, ctx);
  const settle = () => new Promise(r => setImmediate(r));
  const click = dataset => on.click({ target: { closest: () => ({ id: "", dataset }) } });
  const key = k => on.keydown({ key: k, target: { matches: () => true }, preventDefault() {} });
  const type = text => { els.asknote.value = text; on.input({ target: { id: "asknote" } }); };
  return { sent, els, settle, click, key, type, state };
}

async function onTab(opts) {
  const p = run(opts);
  await p.settle();
  p.click({ tab: "input" });
  await p.settle();
  return p;
}

test("the tab is her link's alone, with the number waiting beside its name", async () => {
  const p = run();
  await p.settle();
  assert.equal(p.els.tabs.hidden, false);
  assert.equal(p.els.inputn.textContent, "3");
  assert.equal(p.els.inputn.hidden, false);
  assert.equal(p.els.inputtab.attrs["aria-label"], "Your input, 3 waiting");
  assert.equal(p.els.top.className, "top own");
  const sam = run({ view: SAM });
  await sam.settle();
  assert.equal(sam.els.tabs.hidden, true, "a contributor's page shows no tabs");
  assert.equal(sam.els.inputn.hidden, true);
  assert.equal(sam.els.top.className, "top");
  assert.ok(sam.sent.every(s => s.path !== "/api/bench/asks"), "and asks nothing of the list");
  const none = run({ view: { ...OWNER, asks: null } });
  await none.settle();
  assert.equal(none.els.inputn.hidden, true, "no number before the list's tables are made");
  const html = await benchPage().text();
  assert.match(html, /<button type="button" id="inputtab" data-tab="input">Your input<span class="n" id="inputn" aria-hidden="true" hidden><\/span><\/button><\/nav>/);
  assert.match(html, /Only you see your answers and notes here; they reach the laptop when you pull them, and never become part of Granite Record’s open data\./);
});

test("the list: by section in the list's order, a waiting row and a quieter answered one", async () => {
  const p = await onTab();
  assert.deepEqual(p.sent.map(s => [s.path, s.body.action || ""]), [["/api/bench/next", ""], ["/api/bench/asks", "list"]]);
  assert.ok(p.sent.every(s => s.body.t === TOKEN), "the token in the body");
  const h = p.els.inputbody.innerHTML;
  assert.equal(p.els.input.hidden, false);
  assert.equal(p.els.judge.hidden, true);
  assert.equal(p.els.links.hidden, true);
  assert.deepEqual([...h.matchAll(/<h2>([^<]*)<\/h2>/g)].map(m => m[1]), ["In the update waiting for your word", "Anything else"]);
  assert.match(h, /<button type="button" class="ask wait" id="row-nav-rows" data-ask="nav-rows"><b>Navigation in two rows<\/b><span class="st">Waiting<\/span><\/button>/);
  assert.match(h, /class="ask done" id="row-map-dots" data-ask="map-dots"><b>Map dots<\/b><span class="st">Answered 22 Nov: Needs changes<\/span>/);
  assert.equal(p.els.inputhead.hidden, false, "the line saying what this is, at the top of the list");
  assert.equal(p.els.inputn.textContent, "2", "the count as the list says it");
});

test("her answer's day is the state's clock's: an evening's answer is not dated the next day", async () => {
  // 20:30 on 23 November by the state's clock (site.gen.js TIMEZONE, America/New_York) is
  // 01:30 on the 24th in UTC.
  assert.ok(SCRIPT.includes(`var ZONE=${JSON.stringify(TIMEZONE)};`), "the zone is the site's own setting");
  const late = { answer: "yes", note: "", at: "2026-11-24T01:30:00.000Z" };
  const p = await onTab({ asks: [{ key: "late-one", card: card({ title: "Late" }), answer: late }] });
  assert.match(p.els.inputbody.innerHTML, /<b>Late<\/b><span class="st">Answered 23 Nov: Looks right<\/span>/);
  p.click({ ask: "late-one" });
  assert.match(p.els.inputbody.innerHTML, /<p class="was">Answered 23 Nov: Looks right<\/p>/);
});

test("an entry: what, where to look in a new tab, the question, its own answers, the note and Save", async () => {
  const p = await onTab();
  p.click({ ask: "nav-rows" });
  const h = p.els.inputbody.innerHTML;
  assert.equal(p.els.inputhead.hidden, true);
  assert.ok(p.els.asktitle.focused, "the entry's title takes the focus");
  assert.match(h, /data-do="askback">&larr; Back to the list<\/button>/);
  assert.match(h, /<p class="label">In the update waiting for your word<\/p><h2 id="asktitle" tabindex="-1">Navigation in two rows<\/h2>/);
  assert.match(h, /<div class="what"><p>Each section&#39;s pages now sit in a second row\.<\/p><p>On a phone the row scrolls\.\nSwipe it\.<\/p><\/div>/,
               "paragraphs at the blank lines");
  assert.match(h, /<a href="https:\/\/dry-run\.graniterecord\.pages\.dev\/" target="_blank" rel="noopener noreferrer">The home page on the preview<\/a>/);
  assert.match(h, /<a href="https:\/\/claude\.ai\/artifact\/AAAAAAAAAAAAAAAAAAAAAA" target="_blank" rel="noopener noreferrer">/);
  assert.match(h, /<p class="q">Does the new navigation read right on a computer and on a phone\?<\/p>/);
  assert.deepEqual([...h.matchAll(/data-pick="(\w+)" aria-pressed="(\w+)">([^<]*)(<small>Recommended<\/small>)?/g)]
    .map(m => [m[1], m[2], m[3], !!m[4]]),
    [["yes", "false", "Looks right", true], ["no", "false", "Needs changes", false], ["unsure", "false", "Let’s discuss", false]],
    "the entry's own words, the recommended one marked, and none chosen in advance");
  assert.match(h, /<textarea id="asknote" rows="5" maxlength="2000" aria-describedby="askcount"><\/textarea>/);
  assert.match(h, /data-do="asksave">Save<\/button>/);
  assert.equal(p.els.asknote.value, "");
  p.key("Escape");
  assert.match(p.els.inputbody.innerHTML, /id="row-nav-rows"/, "Escape is Back");
  assert.ok(p.els["row-nav-rows"].focused, "and the row it came from takes the focus");
});

test("every value is drawn as text: an entry titled <img src=x onerror=alert(1)> among them", async () => {
  const bad = "<img src=x onerror=alert(1)>";
  const p = await onTab({ asks: [{ key: "bad-one", answer: { answer: "yes", note: "</textarea><script>x()</script>", at: bad },
    card: card({ section: bad, title: bad, what: "<b>bold</b>\n\n" + bad, question: bad + "?",
                 where: [{ label: bad, url: "https://graniterecord.org/\"><img src=x onerror=alert(1)>" }],
                 answers: { yes: bad, no: "<i>no</i>", unsure: "\" onfocus=\"x" }, recommended: "yes" }) }] });
  const list = p.els.inputbody.innerHTML;
  p.click({ ask: "bad-one" });
  const entry = p.els.inputbody.innerHTML;
  for (const h of [list, entry]) {
    assert.ok(!/<img|<script|<b>bold|<i>no|onerror|onfocus="x/.test(h.replace(/&lt;img src=x onerror=alert\(1\)&gt;/g, "")),
              h.slice(0, 300));
    assert.match(h, /&lt;img src=x onerror=alert\(1\)&gt;/);
  }
  assert.match(entry, /<p>&lt;b&gt;bold&lt;\/b&gt;<\/p>/);
  assert.match(entry, /data-pick="unsure" aria-pressed="false">&quot; onfocus=&quot;x</);
  assert.equal(p.els.asknote.value, "</textarea><script>x()</script>", "her note goes into the box as its value, never as markup");
  assert.doesNotMatch(entry, /<a href/, "a link with a quote in it is not a link the format allows");
});

test("a link the list's format refuses is never drawn as a link, even from the database", async () => {
  const urls = ["javascript:alert(1)", "http://graniterecord.org/", "https://evil.example/", "https://user:pw@claude.ai/",
                "https://claude.ai:443/", "https://graniterecord.org.evil.com/", "data:text/html,x", "https://Claude.ai/",
                "https://graniterecord.pages.dev/", "//claude.ai/x", "https://claude.ai\\@evil.example/", " https://claude.ai/",
                "https://claude.ai/ x", "https://www.graniterecord.org/", 7, null];
  const p = await onTab({ asks: [{ key: "links-one", answer: null, card: card({
    where: [...urls.map((u, i) => ({ label: `bad ${i}`, url: u })), { label: "good", url: "https://abc123.graniterecord.pages.dev/bill/2026/hb1#votes" }] }) }] });
  p.click({ ask: "links-one" });
  const h = p.els.inputbody.innerHTML;
  assert.deepEqual([...h.matchAll(/<a href="([^"]*)"/g)].map(m => m[1]), ["https://abc123.graniterecord.pages.dev/bill/2026/hb1#votes"]);
  assert.equal([...h.matchAll(/<span class="plain">bad \d+<\/span>/g)].length, urls.length, "each drawn as its words alone");
  const rule = new RegExp(LINK_RULE);
  assert.ok(urls.every(u => !rule.test(u)) && rule.test("https://graniterecord.org") && rule.test("https://claude.ai/x?y=1"));
});

test("saving: an answer is required, then sent with her note, and the list comes back with the row answered", async () => {
  const p = await onTab();
  p.click({ ask: "nav-rows" });
  p.click({ do: "asksave" });
  assert.equal(p.els.askmsg.textContent, "Choose an answer first.");
  assert.ok(p.els.pick0.focused);
  assert.ok(!p.sent.some(s => s.body.action === "answer"), "nothing is sent without an answer");
  p.click({ pick: "no" });
  assert.deepEqual([p.els.pick0.attrs["aria-pressed"], p.els.pick1.attrs["aria-pressed"], p.els.pick2.attrs["aria-pressed"]],
                   ["false", "true", "false"]);
  p.type("The second row wraps on my phone.\nOtherwise fine.");
  p.click({ do: "asksave" });
  await p.settle();
  assert.deepEqual(p.sent.at(-1), { path: "/api/bench/asks", body: { t: TOKEN, action: "answer", key: "nav-rows", answer: "no",
                                                                    note: "The second row wraps on my phone.\nOtherwise fine." } });
  assert.match(p.els.inputbody.innerHTML, /class="ask done" id="row-nav-rows" data-ask="nav-rows"><b>Navigation in two rows<\/b><span class="st">Answered 23 Nov: Needs changes<\/span>/);
  assert.equal(p.els.toastwords.textContent, "Saved: Needs changes");
  assert.equal(p.els.toast.hidden, false);
  assert.equal(p.els.inputn.textContent, "1", "the count as the bench now says it");
  // Reopened: her latest answer chosen and her latest note in the box; saving again adds another.
  p.click({ ask: "nav-rows" });
  assert.match(p.els.inputbody.innerHTML, /data-pick="no" aria-pressed="true">Needs changes/);
  assert.match(p.els.inputbody.innerHTML, /<p class="was">Answered 23 Nov: Needs changes<\/p>/);
  assert.equal(p.els.asknote.value, "The second row wraps on my phone.\nOtherwise fine.");
  p.click({ do: "asksave" });
  await p.settle();
  assert.deepEqual(p.sent.filter(s => s.body.action === "answer").map(s => s.body.answer), ["no", "no"]);
});

test("an entry with one answer saves with its words; Back keeps what she typed; a refusal says why", async () => {
  let p = await onTab();
  p.click({ ask: "a-note" });
  assert.doesNotMatch(p.els.inputbody.innerHTML, /class="picks"/, "no choice to make");
  assert.match(p.els.inputbody.innerHTML, /data-do="asksave">Save the note<\/button>/);
  p.type("A thought.");
  p.click({ do: "asksave" });
  await p.settle();
  assert.deepEqual(p.sent.at(-1).body, { t: TOKEN, action: "answer", key: "a-note", answer: "yes", note: "A thought." });
  // Back, with a choice and a note not saved, and in again: both still there.
  p.click({ ask: "nav-rows" });
  p.click({ pick: "unsure" });
  p.type("Half a thought");
  p.key("Escape");
  p.click({ ask: "nav-rows" });
  assert.match(p.els.inputbody.innerHTML, /data-pick="unsure" aria-pressed="true">/);
  assert.equal(p.els.asknote.value, "Half a thought");
  // The quiet count, near the end of 2,000 characters.
  p.type("x".repeat(1500));
  assert.equal(p.els.askcount.textContent, "");
  p.type("x".repeat(1750));
  assert.equal(p.els.askcount.textContent, "250 characters left");
  p.type("x".repeat(1999));
  assert.equal(p.els.askcount.textContent, "1 character left");
  p.type("x".repeat(2000));
  assert.equal(p.els.askcount.textContent, "No characters left");
  // Refused: a note too long stays in the entry and says so; so does an entry withdrawn while it
  // was open, her note still in the box to copy, and Back then shows the list without it.
  p = await onTab({ answer: body => body.key === "nav-rows" ? { status: 400, data: { why: "long", asks: LIST } }
                                                           : { status: 409, data: { why: "gone", asks: LIST.slice(0, 1) } } });
  p.click({ ask: "nav-rows" });
  p.click({ pick: "yes" });
  p.click({ do: "asksave" });
  await p.settle();
  assert.equal(p.els.askmsg.textContent, "Not saved: a note is 2,000 characters at most.");
  assert.match(p.els.inputbody.innerHTML, /id="asktitle"/, "still in the entry");
  p.key("Escape");
  p.click({ ask: "map-dots" });
  p.click({ pick: "yes" });
  p.type("Three paragraphs of thought.");
  p.click({ do: "asksave" });
  await p.settle();
  assert.equal(p.els.askmsg.textContent, "Not saved: this one is no longer on the list. Your note is still here to copy.");
  assert.match(p.els.inputbody.innerHTML, /id="asktitle"[^>]*>Map dots</, "still in the entry");
  assert.match(p.els.inputbody.innerHTML, /<textarea id="asknote"/, "and its note box");
  assert.equal(p.els.asknote.value, "Three paragraphs of thought.");
  p.key("Escape");
  assert.match(p.els.inputbody.innerHTML, /row-nav-rows/);
  assert.doesNotMatch(p.els.inputbody.innerHTML, /row-map-dots/, "Back shows the list without it");
});

test("an entry changed while it was open is drawn again from the list sent back, her note kept, to choose again", async () => {
  const fewer = LIST.map(k => (k.key === "nav-rows" ? { ...k, card: card({ answers: { yes: "Looks right", no: "Needs changes" } }) } : k));
  const p = await onTab({ answer: () => ({ status: 400, data: { why: "bad", asks: fewer, waiting: 2 } }) });
  p.click({ ask: "nav-rows" });
  p.click({ pick: "unsure" });
  p.type("Talk on Friday?");
  p.click({ do: "asksave" });
  await p.settle();
  const h = p.els.inputbody.innerHTML;
  assert.equal(p.els.askmsg.textContent, "Not saved: this entry changed while it was open. Choose again.");
  assert.deepEqual([...h.matchAll(/data-pick="(\w+)" aria-pressed="(\w+)"/g)].map(m => [m[1], m[2]]),
                   [["yes", "false"], ["no", "false"]], "drawn again with the answers it offers now, none chosen");
  assert.ok(p.els.pick0.focused, "the first of them takes the focus");
  assert.equal(p.els.asknote.value, "Talk on Friday?");
  p.click({ pick: "no" });
  p.click({ do: "asksave" });
  await p.settle();
  assert.deepEqual(p.sent.at(-1).body, { t: TOKEN, action: "answer", key: "nav-rows", answer: "no", note: "Talk on Friday?" });
});

test("on her tab no key judges anything, and the Judge tab's keys are where they were", async () => {
  const p = await onTab();
  p.click({ ask: "nav-rows" });
  for (const k of ["ArrowRight", "ArrowLeft", "ArrowDown", "z", "n", " "]) p.key(k);
  assert.ok(!p.sent.some(s => s.path === "/api/bench/judge" || s.path === "/api/bench/undo"));
  assert.match(p.els.inputbody.innerHTML, /id="asktitle"/, "nothing but Escape leaves the entry");
  p.click({ tab: "judge" });
  assert.equal(p.els.input.hidden, true);
  assert.equal(p.els.judge.hidden, false);
  p.click({ tab: "input" });
  await p.settle();
  assert.match(p.els.inputbody.innerHTML, /id="row-nav-rows"/, "the tab opens on the list");
});
