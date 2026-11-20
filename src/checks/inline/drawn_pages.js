
const fs = require("fs"), vm = require("vm"), path = require("path");
const [stubPath, jobsPath, outPath] = process.argv.slice(2);
const STUB = fs.readFileSync(stubPath, "utf8");
const jobs = JSON.parse(fs.readFileSync(jobsPath, "utf8"));
let errors = null;
process.on("unhandledRejection", e => { if (errors) errors.push("unhandled: " + String(e && e.stack || e).split("\n")[0]); });
process.on("uncaughtException", e => { if (errors) errors.push("uncaught: " + String(e && e.stack || e).split("\n")[0]); });
const tick = () => new Promise(r => setImmediate(r));

const PRELUDE = String.raw`
(function(){
  const R = Date, T = new R(__today[0], __today[1] - 1, __today[2], 12, 0, 0).getTime();
  class FixedDate extends R { constructor(...a) { if (a.length) super(...a); else super(T); }
    static now() { return T; } }
  globalThis.Date = FixedDate;
})();
`;
// The stub's elements, given what a page's scripts ask of an element beyond
// it: attributes that are kept and read back, the insertion methods, and an
// id that getElementById can find once something has drawn it.
const AFTER_STUB = String.raw`
var ALL = [];
(function(){
  const bare = el;
  el = function (tag) {
    const e = bare(tag);
    e._attr = {};
    e.setAttribute = (k, v) => { e._attr[k] = String(v); if (k === "id") e.id = String(v); };
    e.getAttribute = k => (k in e._attr ? e._attr[k] : null);
    e.hasAttribute = k => k in e._attr;
    e.removeAttribute = k => { delete e._attr[k]; };
    e.toggleAttribute = (k, on) => { const v = on === undefined ? !(k in e._attr) : !!on;
      if (v) e._attr[k] = ""; else delete e._attr[k]; return v; };
    e.after = e.before = e.prepend = e.replaceWith = e.replaceChildren = () => {};
    e.insertAdjacentHTML = (where, h) => { if (where === "beforeend") e.innerHTML += h;
      else if (where === "afterbegin") e.innerHTML = h + e.innerHTML; };
    e.matches = () => false;
    e.cloneNode = () => el(tag);
    ALL.push(e);
    return e;
  };
})();
(function(){
  const PAGE = __page, json = {};
  for (const m of PAGE.matchAll(/<script type="application\/json" id="([^"]+)">([\s\S]*?)<\/script>/g))
    json[m[1]] = m[2];
  const has = id => { const n = 'id="' + id + '"'; if (PAGE.includes(n)) return true;
    return ALL.some(e => (e._html || "").includes(n)); };
  const q = document.querySelector;
  document.getElementById = function (id) {
    if (made[id]) return made[id];
    const own = ALL.find(e => e.id === id);
    if (own) return own;
    if (!has(id)) return null;
    const e = made[id] = el(); if (id in json) e.textContent = json[id];
    // An element the page itself carries keeps the attributes its tag gives it.
    const tag = new RegExp('<([a-z][a-z0-9]*)\\b[^>]*\\bid="' + id + '"[^>]*>').exec(PAGE);
    if (tag) {
      e.tagName = tag[1].toUpperCase();
      const unq = v => v.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">").replace(/&amp;/g, "&");
      for (const a of tag[0].matchAll(/\s([a-z][\w-]*)(?:="([^"]*)")?/g)) e._attr[a[1]] = unq(a[2] || "");
    }
    return e; };
  document.querySelector = function (sel) {
    const mm = /^meta\[name="([^"]+)"\]$/.exec(sel);
    if (mm) { const x = new RegExp('<meta name="' + mm[1] + '" content="([^"]*)"').exec(PAGE);
      if (!x) return null; const e = el(); e.getAttribute = a => a === "content" ? x[1] : null; return e; }
    if (/^#[\w-]+$/.test(sel)) return document.getElementById(sel.slice(1));
    return q.call(document, sel); };
  globalThis.clearTimeout = globalThis.clearInterval = () => {};
  globalThis.setInterval = () => 0;
  // A TIMER A WHILE AWAY IS THE PAGE LATER (5 November 2026). The stub runs
  // every timer's callback at once. live.js's hook on a committee page looks
  // at the clock once a minute until it learns there is no stream; on a
  // weekend, outside its hours, it never asks, so run at once that look
  // re-armed itself without end and no committee page drawn on a Saturday or
  // a Sunday ever finished. A drawing is the page as it first stands: a timer
  // set LATER_MS or more away never fires in it, as an interval never does.
  // The pages' own short timers (six seconds and under) still fire at once.
  { const soon = globalThis.setTimeout;
    globalThis.setTimeout = (f, ms, ...a) => (Number(ms) >= __LATER_MS ? 0 : soon(f, ms, ...a)); }
  const heard = {};
  document.addEventListener = (t, f) => (heard["d:" + t] = heard["d:" + t] || []).push(f);
  globalThis.addEventListener = (t, f) => (heard["w:" + t] = heard["w:" + t] || []).push(f);
  globalThis.__fire = k => (heard[k] || []).forEach(f => { try { f({type: k.slice(2), target: document}); }
    catch (e) { __err("listener " + k + ": " + e.constructor.name + ": " + e.message); } });
  globalThis.fetch = async u => { const b = __read(String(u));
    return b === null ? {ok: false, status: 404, statusText: "Not Found",
                         json: async () => { throw new Error("HTTP 404 " + u); }, text: async () => ""}
                      : {ok: true, status: 200, json: async () => JSON.parse(b), text: async () => b}; };
  location.pathname = __path; location.href = "https://x" + __path; location.origin = "https://x";
  location.search = ""; location.hash = "";
})();
`;

function draw(job) {
  const html = fs.readFileSync(path.join(job.site, job.page), "utf8");
  const ctx = vm.createContext({
    console: {log() {}, warn() {}, error() {}, info() {}, debug() {}},
    URL, URLSearchParams, setImmediate, queueMicrotask, TextEncoder, TextDecoder,
    __today: job.today, __page: html, __path: job.path, __LATER_MS: job.later_ms,
    __err: m => errors.push(m),
    __read: u => {
      let p;
      try { p = decodeURIComponent(new URL(u, "https://x/").pathname).replace(/^\/+/, ""); }
      catch (_) { return null; }
      let f = path.join(job.site, p);
      if (p && !fs.existsSync(f) && fs.existsSync(f + ".html")) f += ".html";
      if (!p || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return null;
      return fs.readFileSync(f, "utf8");
    }});
  const run = (code, name) => {
    try { vm.runInContext(code, ctx, {filename: name}); }
    catch (e) { errors.push(name + ": " + e.constructor.name + ": " + e.message); }
  };
  run(PRELUDE, "prelude");
  run(STUB, "dom_stub.js");
  run(AFTER_STUB, "the page");
  const later = [];
  for (const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
    const attrs = m[1], src = /\bsrc="([^"]+)"/.exec(attrs), type = /\btype="([^"]+)"/.exec(attrs);
    if (type && !/javascript/.test(type[1])) continue;
    if (src) {
      const file = path.join(job.site, src[1].replace(/^\/+/, ""));
      if (!fs.existsSync(file)) { errors.push(src[1] + ": not in the site"); continue; }
      const code = fs.readFileSync(file, "utf8");
      if (/\bdefer\b/.test(attrs)) later.push([code, src[1]]); else run(code, src[1]);
    } else run(m[2], "an inline script");
  }
  for (const [code, name] of later) run(code, name);
  run('__fire("d:DOMContentLoaded"); __fire("w:load");', "the page loaded");
  return ctx;
}

(async () => {
  const out = {};
  for (const job of jobs) {
    errors = [];
    const ctx = draw(job);
    let last = "", still = 0;
    for (let i = 0; i < 2000 && still < 40; i++) {
      await tick();
      const now = vm.runInContext("Object.keys(made).map(k => k.length + (made[k]._html || '').length + "
        + "String(made[k].textContent || '').length).join()", ctx);
      still = now === last ? still + 1 : 0; last = now;
    }
    const els = vm.runInContext("Object.keys(made).sort().map(k => [k, made[k]._html || '', "
      + "String(made[k].textContent || ''), !!made[k].hidden, String(made[k].value || ''), "
      + "JSON.stringify(Object.fromEntries(Object.entries(made[k]._attr || {}).sort()))])", ctx);
    out[job.key] = {title: String(vm.runInContext("document.title", ctx) || ""),
                    elements: els.filter(e => e[1] || e[2] || e[3] || e[4] || e[5] !== "{}"), errors};
    errors = null;
  }
  fs.writeFileSync(outPath, JSON.stringify(out));
})();
