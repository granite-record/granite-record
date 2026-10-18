// GRANITE_VERSION: 2026-10-18.1
/* THE FOLLOW PANEL'S STATES, RUN IN NODE.

     node tests/test_follow_panel.js PAGE_JS tests/dom_stub.js

   PAGE_JS is app.js with components.js before it, as every page loads them
   (preflight writes it with _with_components). preflight's
   _follow_panel_states runs this and reads the one line of JSON it prints
   last: the cases run and every failure.

   WHY A DOM OF ITS OWN (18 October 2026). The person, testing the panel:
   "once you click submit for your email, the display doesn't look like much
   happened if anything because only the text below it changes, and the
   Cloudflare verification reloads when you click submit so it looks like
   your email request didn't actually go through even when it did." Each
   fault is in what the panel's own markup does after a press -- which part
   is hidden, which is shown, where the keyboard goes, whether the widget is
   reset -- and dom_stub.js answers every question with an empty element, so
   nothing it is asked can be wrong. app.js is loaded under dom_stub.js, as
   the other checks load it, and then the panel is drawn and pressed on a
   small real tree: markup parsed, hidden and open as attributes, selectors
   matched, focus kept. Only the page's own listeners for the panel are
   fired, picked by what they name, so a change to an unrelated listener
   cannot fail this.

   The endpoints and Turnstile are stubs: nothing leaves the process. */
"use strict";
const fs = require("fs"), path = require("path");
const [pageJs, stubJs] = process.argv.slice(2).map(p => path.resolve(p));
const RT = setTimeout;
require(stubJs);
const on = {};
document.addEventListener = (t, f) => { (on[t] = on[t] || []).push(f); };
let S;
try {
  S = (0, eval)(fs.readFileSync(pageJs, "utf8") +
    ";({mountFollow, followSubmit, FOLLOW_TS, FOLLOW_SAID, FOLLOW_OFTEN})");
} catch (e) { console.log(JSON.stringify({ load: e.constructor.name + ": " + e.message })); process.exit(1); }
// dom_stub runs a timer at once; the token's wait needs a real one.
globalThis.setTimeout = RT;

// ---------------------------------------------------------------- the tree --
const VOID = new Set(["input", "br", "img", "hr", "meta", "link", "source", "wbr"]);
const ENT = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", rsquo: "’",
  lsquo: "‘", mdash: "—", ndash: "–", hellip: "…" };
const unent = s => s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, k) =>
  k[0] === "#" ? String.fromCodePoint(k[1] === "x" || k[1] === "X" ? parseInt(k.slice(2), 16) : +k.slice(1))
    : (ENT[k] ?? m));
const escT = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escA = s => escT(s).replace(/"/g, "&quot;");
const kebab = k => k.replace(/[A-Z]/g, c => "-" + c.toLowerCase());

class Text {
  constructor(t) { this.data = t; this.nodeType = 3; this.parentNode = null; }
  get textContent() { return this.data; }
}
class El {
  constructor(tag, doc) {
    this.localName = tag.toLowerCase(); this.tagName = tag.toUpperCase(); this.nodeType = 1;
    this.attrs = new Map(); this.childNodes = []; this.parentNode = null; this.doc = doc;
    this._value = null; this._checked = null; this._on = {};
  }
  getAttribute(n) { return this.attrs.has(n) ? this.attrs.get(n) : null; }
  setAttribute(n, v) { this.attrs.set(n, String(v)); }
  removeAttribute(n) { this.attrs.delete(n); }
  hasAttribute(n) { return this.attrs.has(n); }
  _flag(n, v) { if (v) this.setAttribute(n, ""); else this.removeAttribute(n); }
  get id() { return this.getAttribute("id") || ""; }
  set id(v) { this.setAttribute("id", v); }
  get className() { return this.getAttribute("class") || ""; }
  set className(v) { this.setAttribute("class", v); }
  get classList() {
    const el = this, list = () => el.className.split(/\s+/).filter(Boolean);
    const put = l => el.setAttribute("class", l.join(" "));
    return {
      contains: c => list().includes(c),
      add: (...c) => put([...new Set([...list(), ...c])]),
      remove: (...c) => put(list().filter(x => !c.includes(x))),
      toggle(c, force) {
        const want = force === undefined ? !list().includes(c) : !!force;
        if (want) this.add(c); else this.remove(c);
        return want;
      },
    };
  }
  get dataset() {
    const el = this;
    return new Proxy({}, {
      get: (_, k) => typeof k === "string" ? (el.getAttribute("data-" + kebab(k)) ?? undefined) : undefined,
      set: (_, k, v) => { el.setAttribute("data-" + kebab(k), v); return true; },
      deleteProperty: (_, k) => { el.removeAttribute("data-" + kebab(k)); return true; },
      has: (_, k) => el.hasAttribute("data-" + kebab(k)),
    });
  }
  get hidden() { return this.hasAttribute("hidden"); } set hidden(v) { this._flag("hidden", v); }
  get disabled() { return this.hasAttribute("disabled"); } set disabled(v) { this._flag("disabled", v); }
  get open() { return this.hasAttribute("open"); } set open(v) { this._flag("open", v); }
  get type() { return this.getAttribute("type") || ""; }
  get name() { return this.getAttribute("name") || ""; }
  get value() { return this._value ?? this.getAttribute("value") ?? ""; }
  set value(v) { this._value = String(v); }
  get checked() { return this._checked ?? this.hasAttribute("checked"); }
  set checked(v) {
    this._checked = !!v;
    if (v && this.type === "radio") {
      const root = this.closest("form") || this.doc.documentElement;
      root.querySelectorAll(`input[name="${this.name}"]`).forEach(o => { if (o !== this) o._checked = false; });
    }
  }
  get children() { return this.childNodes.filter(n => n.nodeType === 1); }
  get firstChild() { return this.childNodes[0] || null; }
  get nextSibling() {
    const s = this.parentNode && this.parentNode.childNodes;
    return s ? s[s.indexOf(this) + 1] || null : null;
  }
  get textContent() { return this.childNodes.map(n => n.textContent).join(""); }
  set textContent(v) { this.childNodes = []; if (String(v)) this.appendChild(new Text(String(v))); }
  get innerHTML() { return this.childNodes.map(serialize).join(""); }
  set innerHTML(v) { this.childNodes = []; parseInto(this, String(v), this.doc); }
  appendChild(n) { if (n.parentNode) n.remove(); n.parentNode = this; this.childNodes.push(n); return n; }
  insertBefore(n, ref) {
    if (!ref) return this.appendChild(n);
    if (n.parentNode) n.remove();
    n.parentNode = this; this.childNodes.splice(this.childNodes.indexOf(ref), 0, n); return n;
  }
  before(n) { this.parentNode.insertBefore(n, this); }
  remove() {
    const p = this.parentNode;
    if (p) { p.childNodes.splice(p.childNodes.indexOf(this), 1); this.parentNode = null; }
  }
  contains(n) { for (let x = n; x; x = x.parentNode) if (x === this) return true; return false; }
  *_all() { for (const c of this.children) { yield c; yield* c._all(); } }
  querySelectorAll(sel) { const g = parseSel(sel); return [...this._all()].filter(e => matchSel(e, g)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  matches(sel) { return matchSel(this, parseSel(sel)); }
  closest(sel) {
    const g = parseSel(sel);
    for (let x = this; x && x.nodeType === 1; x = x.parentNode) if (matchSel(x, g)) return x;
    return null;
  }
  get elements() {
    const out = {};
    for (const e of this._all())
      if (/^(input|button|select|textarea)$/.test(e.localName) && e.name && !(e.name in out)) out[e.name] = e;
    return out;
  }
  focus() { this.doc.activeElement = this; }
  blur() { if (this.doc.activeElement === this) this.doc.activeElement = this.doc.body; }
  select() {}
  addEventListener(t, f) { (this._on[t] = this._on[t] || []).push(f); }
  removeEventListener() {}
  getBoundingClientRect() { return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 }; }
  scrollIntoView() {}
  requestSubmit() {}
}
function serialize(n) {
  if (n.nodeType === 3) return escT(n.data);
  const a = [...n.attrs].map(([k, v]) => v === "" ? ` ${k}` : ` ${k}="${escA(v)}"`).join("");
  return VOID.has(n.localName) ? `<${n.localName}${a}>` : `<${n.localName}${a}>${n.innerHTML}</${n.localName}>`;
}
function parseInto(root, html, doc) {
  const re = /<!--[\s\S]*?-->|<\/([a-zA-Z][\w-]*)\s*>|<([a-zA-Z][\w-]*)((?:\s+[^\s"'>\/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*)\s*(\/?)>|[^<]+|</g;
  const stack = [root];
  let m;
  while ((m = re.exec(html))) {
    const top = stack[stack.length - 1];
    if (m[0].startsWith("<!--")) continue;
    if (m[1]) {
      const t = m[1].toLowerCase();
      const at = stack.map(e => e.localName).lastIndexOf(t);
      if (at > 0) stack.length = at;
      continue;
    }
    if (m[2]) {
      const el = new El(m[2], doc);
      const ar = /([^\s"'>\/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
      let a;
      while ((a = ar.exec(m[3] || ""))) el.setAttribute(a[1].toLowerCase(), unent(a[2] ?? a[3] ?? a[4] ?? ""));
      top.appendChild(el);
      if (!m[4] && !VOID.has(el.localName)) stack.push(el);
      continue;
    }
    top.appendChild(new Text(unent(m[0])));
  }
}
// Selectors: lists, descendant and child combinators, and compounds of a
// tag, #id, .class, [attr], [attr=value] and :checked -- what app.js asks.
function splitTop(s, ch) {
  const out = []; let depth = 0, q = "", cur = "";
  for (const c of s) {
    if (q) { if (c === q) q = ""; cur += c; continue; }
    if (c === '"' || c === "'") { q = c; cur += c; continue; }
    if (c === "[" || c === "(") depth++;
    if (c === "]" || c === ")") depth--;
    if (depth === 0 && (ch === " " ? /\s/.test(c) : c === ch)) { out.push(cur); cur = ""; continue; }
    cur += c;
  }
  out.push(cur);
  return out.map(x => x.trim()).filter(Boolean);
}
function parseSel(sel) {
  return splitTop(sel, ",").map(cx => {
    const parts = splitTop(cx.replace(/\s*>\s*/g, " > "), " ");
    const steps = [];
    let comb = " ";
    for (const p of parts) {
      if (p === ">") { comb = ">"; continue; }
      steps.push({ comb, test: compound(p) });
      comb = " ";
    }
    return steps;
  });
}
function compound(p) {
  const tests = [];
  const re = /^([a-zA-Z][\w-]*|\*)|#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\]]*)))?\]|:([\w-]+)/g;
  let m;
  while ((m = re.exec(p))) {
    if (m[1] && m[1] !== "*") { const t = m[1].toLowerCase(); tests.push(e => e.localName === t); }
    else if (m[2]) { const v = m[2]; tests.push(e => e.id === v); }
    else if (m[3]) { const v = m[3]; tests.push(e => e.classList.contains(v)); }
    else if (m[4]) {
      const n = m[4], v = m[5] ?? m[6] ?? m[7];
      tests.push(e => e.hasAttribute(n) && (v === undefined || e.getAttribute(n) === v));
    } else if (m[8] === "checked") tests.push(e => !!e.checked);
    else if (m[8]) { const w = m[8]; tests.push(() => { throw new Error("no :" + w + " here"); }); }
  }
  return e => tests.every(t => t(e));
}
function matchSel(el, group) {
  const at = (e, steps, i) => {
    if (!steps[i].test(e)) return false;
    if (i === 0) return true;
    if (steps[i].comb === ">") return !!(e.parentNode && e.parentNode.nodeType === 1 && at(e.parentNode, steps, i - 1));
    for (let p = e.parentNode; p && p.nodeType === 1; p = p.parentNode) if (at(p, steps, i - 1)) return true;
    return false;
  };
  return group.some(steps => at(el, steps, steps.length - 1));
}
function makeDoc() {
  const doc = { activeElement: null, title: "", readyState: "complete" };
  doc.documentElement = new El("html", doc);
  doc.head = doc.documentElement.appendChild(new El("head", doc));
  doc.body = doc.documentElement.appendChild(new El("body", doc));
  doc.activeElement = doc.body;
  doc.createElement = t => new El(t, doc);
  doc.getElementById = id => doc.documentElement.querySelector("#" + id);
  doc.querySelector = s => doc.documentElement.querySelector(s);
  doc.querySelectorAll = s => doc.documentElement.querySelectorAll(s);
  doc.addEventListener = document.addEventListener;
  doc.removeEventListener = () => {};
  return doc;
}

// ---------------------------------------------------------------- the stubs --
const tick = () => new Promise(r => setImmediate(r));
const settle = async (n = 8) => { for (let i = 0; i < n; i++) await tick(); };
const reply = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
const KEY = "bill:2026/HB1442", FEED = "/feeds/bill/2026/hb1442.xml";
let net;
globalThis.fetch = async (u, init) => {
  u = String(u);
  if (u.startsWith("/api/follow/count")) return reply(net.count, { count: 3 });
  if (u.startsWith("/changes/current.json")) return reply(200, { followable: net.followable });
  if (u === "/api/follow/signup") { net.sent.push(JSON.parse(init.body)); return net.signup(); }
  return reply(404, {});
};
let TS;
function turnstile() {
  TS = { renders: 0, resets: 0, opts: null,
    render(w, opts) { this.renders++; this.opts = opts; const n = this.renders;
      queueMicrotask(() => opts.callback("tok-" + n)); return "w" + n; },
    reset() { this.resets++; const n = this.resets; queueMicrotask(() => this.opts.callback("tok-r" + n)); } };
  globalThis.turnstile = TS;
}
// Only the page's listeners for the panel, picked by what each names.
const PICK = { toggle: ["followMail(", "#pageacts details[open]"],
  click: ["ACT_PANES", "data-followagain"], submit: [".followform"] };
async function fire(type, target) {
  const e = { type, target, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; },
    stopPropagation() {} };
  const fs_ = (on[type] || []).filter(f => PICK[type].some(w => String(f).includes(w)));
  await Promise.all(fs_.map(f => f(e)));
  return e;
}

// A record's page with its feed, Follow mounted beside Cite and opened.
async function page({ count = 200, followable = { [KEY]: { label: "HB 1442 (2026)" } },
  signup = () => reply(202, { ok: true }) } = {}) {
  net = { count, followable, signup, sent: [] };
  turnstile();
  const doc = makeDoc();
  globalThis.document = doc;
  doc.head.innerHTML = `<link rel="alternate" type="application/rss+xml" href="${FEED}">`;
  doc.body.innerHTML = `<div class="pageacts" id="pageacts"><details class="pcite"><summary>Cite this page</summary>
    <div class="citebody"></div></details></div><h1>HB 1442</h1><div id="results"></div>`;
  S.mountFollow("bill", "", "2026/HB1442");
  const follow = doc.querySelector("details.follow");
  follow.open = true;
  await fire("toggle", follow);
  await settle();
  const form = doc.querySelector(".followform");
  return { doc, follow, form, pane: doc.querySelector(".followpane") };
}
async function submit(p, email = "reader@example.com", often = "daily") {
  p.form.elements.email.value = email;
  p.form.querySelector(`input[value="${often}"]`).checked = true;
  const e = fire("submit", p.form);
  return e;
}
const visible = el => { for (let x = el; x && x.nodeType === 1; x = x.parentNode) if (x.hidden) return false; return true; };

// ---------------------------------------------------------------- the cases --
const fail = [], cases = [];
// SILENCE IS NOT A PASS: node leaves quietly, exit 0, when what it waits on
// can never settle -- a request that went out to a stub that never answers.
let finished = false;
process.on("exit", () => {
  if (finished) return;
  console.log(JSON.stringify({ cases, fail: fail.concat("the run stopped at " + JSON.stringify(cases.at(-1))
    + ": something it waited on never settled") }));
  process.exitCode = 1;
});
async function test(name, fn) {
  cases.push(name);
  try { await fn(); } catch (e) { fail.push(`${name}: ${e.message}`); }
}
function ok(cond, what) { if (!cond) throw new Error(what); }

(async () => {
await test("email first, RSS folded under it in a disclosure that starts closed", async () => {
  const p = await page();
  ok(p.form && visible(p.form), "no email form is shown where the sign-up answers");
  const kids = p.pane.children.map(c => c.className);
  ok(kids.indexOf("followmail") === 0 && kids.indexOf("followrss") === 1,
    "the email box is not first and the feed second in the pane: " + kids.join(", "));
  const alt = p.pane.querySelector(".followrss > details.followalt");
  ok(alt && !alt.open, "the feed is not in a closed disclosure under the email box");
  const sum = alt.querySelector("summary");
  ok(sum && sum.parentNode === alt && /^Follow by RSS instead$/.test(sum.textContent.trim()),
    "the disclosure's button does not say Follow by RSS instead: " + (sum && sum.textContent));
  const body = alt.querySelector(".followaltbody");
  ok(body && body.querySelector(".feedurl input") && body.querySelector("[data-copyfeed]"),
    "the feed's address and Copy the address are not inside the disclosure");
  ok(p.pane.querySelector(".followrss").children.length === 1,
    "something of the feed's sits outside the disclosure");
});

await test("where email cannot be taken, RSS stays open and is the whole pane", async () => {
  for (const [why, opts] of [["the sign-up does not answer", { count: 404 }],
                             ["tonight's list does not name the record", { followable: {} }]]) {
    const p = await page(opts);
    ok(!p.form || !visible(p.form), `${why}: an email form is shown`);
    ok(!p.pane.querySelector(".followalt"), `${why}: the feed is folded behind a disclosure`);
    const rss = p.pane.querySelector(".followrss");
    ok(rss && visible(rss) && rss.querySelector(".feedurl input") && rss.querySelector("[data-copyfeed]"),
      `${why}: the feed's address and Copy the address are not shown`);
    ok(/By RSS, in any feed reader:/.test(rss.textContent), `${why}: the RSS sentence is gone`);
  }
});

await test("sending: the button says Sending… and is disabled, and a second press sends nothing", async () => {
  let release;
  const p = await page({ signup: () => new Promise(r => { release = () => r(reply(202, { ok: true })); }) });
  const first = submit(p);
  await settle();
  const btn = p.form.querySelector(".followsend");
  ok(btn.disabled && btn.textContent === "Sending…",
    `while sending the button is ${btn.disabled ? "disabled" : "enabled"} and says ${JSON.stringify(btn.textContent)}`);
  ok(p.form.getAttribute("aria-busy") === "true", "the form is not marked busy while sending");
  // Not waited for: a second request that went out would wait on an answer
  // that never comes.
  fire("submit", p.form);
  S.followSubmit({ preventDefault() {} }, p.form);
  await settle();
  ok(net.sent.length === 1, `${net.sent.length} sign-up requests for one address pressed three times`);
  release();
  await first;
  await settle();
  ok(!btn.disabled && btn.textContent === "Email me updates", "the button was not given back after the answer");
});

await test("success: Check your email replaces the form, with the address, the steps and how often", async () => {
  for (const often of ["daily", "weekly"]) {
    const p = await page();
    await submit(p, "reader@example.com", often);
    await settle();
    const done = p.doc.querySelector(".followdone");
    ok(done && visible(done), `${often}: no confirmation is shown`);
    ok(!visible(p.form), `${often}: the form is still shown beside the confirmation`);
    const h = done.querySelector(".panh");
    ok(h && /^h[1-6]$/.test(h.localName) && h.textContent.trim() === "Check your email",
      `${often}: the confirmation's heading is not "Check your email": ` + (h && h.outerHTML));
    ok(p.doc.activeElement === h && h.getAttribute("tabindex") === "-1",
      `${often}: the keyboard is not on the confirmation's heading`);
    ok(done.querySelector(".followto") && done.querySelector(".followto").textContent === "reader@example.com",
      `${often}: the confirmation does not name the address the link went to`);
    const txt = done.textContent.replace(/\s+/g, " ");
    ok(/use its link to confirm/.test(txt) && /spam or junk/.test(txt) && /a minute or two/.test(txt),
      `${often}: the confirmation does not say to confirm, that it may take a minute, and to look in spam`);
    const said = S.FOLLOW_OFTEN[often].replace(/^About\b/, "about");
    ok(txt.includes(often === "weekly" ? "Weekly" : "Daily") && txt.includes(said),
      `${often}: the confirmation does not say how often was chosen`);
    ok(net.sent.length === 1 && net.sent[0].frequency === often, `${often}: sent ${JSON.stringify(net.sent)}`);
    ok(!p.form.querySelector(".followstate").classList.contains("followerr"),
      `${often}: the taken sign-up is drawn as a refusal`);
    // The pane stays as it is: nothing else moves it on its own.
    await settle(20);
    ok(visible(done) && !visible(p.form), `${often}: the confirmation did not stay`);
  }
});

await test("success: Turnstile is neither reset nor drawn again, and no challenge is in view", async () => {
  const p = await page();
  await submit(p);
  await settle(20);
  ok(TS.resets === 0, `the widget was reset ${TS.resets} time(s) after a sign-up that was taken`);
  ok(TS.renders === 1, `the widget was drawn ${TS.renders} times`);
  const shown = p.doc.querySelectorAll(".followcheck").filter(visible);
  ok(!shown.length, "a Turnstile widget is in view beside the confirmation");
  const w = p.form.querySelector(".followcheck"), st = S.FOLLOW_TS.get(w);
  ok(st && st.token === "", "the spent token is kept for another request");
});

await test("error: the address is kept, the refusal is drawn as one, and the check is reset for a retry", async () => {
  const p = await page({ signup: () => reply(503, { ok: false, why: "unavailable" }) });
  await submit(p);
  await settle();
  const st = p.form.querySelector(".followstate"), btn = p.form.querySelector(".followsend");
  ok(visible(p.form) && !visible(p.doc.querySelector(".followdone")), "a refused sign-up hid the form");
  ok(p.form.elements.email.value === "reader@example.com", "what was typed is gone after a refusal");
  ok(st.textContent === S.FOLLOW_SAID.unavailable && st.classList.contains("followerr"),
    `the refusal reads ${JSON.stringify(st.textContent)}, class ${JSON.stringify(st.className)}`);
  ok(!btn.disabled && btn.textContent === "Email me updates", "the button is not there to try again");
  ok(TS.resets === 1, `the widget was reset ${TS.resets} times after a refusal, not once`);
  await settle();
  net.signup = () => reply(202, { ok: true });
  await submit(p);
  await settle();
  ok(net.sent.length === 2 && net.sent[1].turnstile === "tok-r1",
    "the retry did not go with the new check's token: " + JSON.stringify(net.sent.map(s => s.turnstile)));
  ok(visible(p.doc.querySelector(".followdone")), "the retry that was taken did not say so");
  ok(!st.classList.contains("followerr"), "the refusal's mark outlived the retry");
});

await test("error: Turnstile's own codes are named, and an address that is not one asks nothing", async () => {
  const p = await page({ signup: () => reply(400, { ok: false, why: "check", codes: ["timeout-or-duplicate"] }) });
  await submit(p);
  await settle();
  const st = p.form.querySelector(".followstate");
  ok(st.textContent.includes("(Turnstile timeout-or-duplicate)") && st.classList.contains("followerr"),
    "a failed check reads " + JSON.stringify(st.textContent));
  const q = await page();
  await submit(q, "not an address");
  await settle();
  const s2 = q.form.querySelector(".followstate");
  ok(!net.sent.length && TS.resets === 0, "an address that is not one was sent, or reset the check");
  ok(s2.textContent === S.FOLLOW_SAID.invalid && s2.classList.contains("followerr"),
    "a bad address reads " + JSON.stringify(s2.textContent));
  ok(q.form.elements.email.value === "not an address", "what was typed is gone");
});

await test("Enter it again: the form back with its address, and a fresh check for the new request", async () => {
  const p = await page();
  await submit(p);
  await settle();
  const again = p.doc.querySelector("[data-followagain]");
  ok(again && again.localName === "button", "the confirmation has no button to enter the address again");
  await fire("click", again);
  await settle();
  ok(visible(p.form) && !visible(p.doc.querySelector(".followdone")), "the form did not come back");
  ok(p.doc.activeElement === p.form.elements.email && p.form.elements.email.value === "reader@example.com",
    "the keyboard is not on the address, kept to correct");
  ok(TS.resets === 1, `the check was reset ${TS.resets} times for a new request`);
  ok(p.follow.open, "pressing it shut the Follow pane");
});

await test("the RSS disclosure opens inside the pane without shutting it, and stays open while used", async () => {
  const p = await page();
  const alt = p.pane.querySelector(".followalt");
  alt.open = true;
  await fire("toggle", alt);
  ok(p.follow.open && alt.open, "opening Follow by RSS instead shut the Follow pane");
  await fire("click", p.form.elements.email);
  ok(p.follow.open && alt.open, "a press on the email box folded the feed again or shut the pane");
  await fire("click", p.doc.querySelector("h1"));
  ok(!p.follow.open, "a press outside the pane no longer shuts it");
  const cite = p.doc.querySelector("details.pcite");
  p.follow.open = true;
  cite.open = true;
  await fire("toggle", cite);
  ok(!p.follow.open, "opening Cite no longer shuts Follow");
});

finished = true;
console.log(JSON.stringify({ cases, fail }));
process.exit(fail.length ? 1 : 0);
})().catch(e => { console.log(JSON.stringify({ cases, fail: fail.concat("RUN " + e.stack) })); process.exit(1); });
