// GRANITE_VERSION: 2026-10-08.1
// The rendered sweep's browser: headless Chrome over the DevTools protocol,
// driven by rendered_sweep.py, which serves the built site, writes the list of
// runs this reads and the one report it gathers from what this prints.
//
//     node src/checks/sweep_browser.js <runs.json>
//
// One JSON line on stdout per run, and nothing else there; progress and
// trouble go to stderr. A run that fails says so in its own line rather than
// stopping the rest: a sweep that dies on page 3 of 21 has measured nothing a
// person can use.
//
// SEALED. Chrome is started with every host name resolving to nothing except
// the loopback address and Google Fonts (HOST_RULES), so the real faces load
// and nothing else can be asked for -- no General Court host, no YouTube, no
// graniterecord.org. Its own background traffic is switched off by the flags
// beside them. Every request a page makes to anywhere else is recorded in its
// run as `outside`, and rendered_sweep.py counts them in the report: a page
// that asks for something new shows up there rather than going quiet.
// preflight reads HOST_RULES and holds them to this.
//
// WHAT A RUN MEASURES is measure(), below, which runs inside the page and only
// reads it: every element that owns text, its rendered size and its contrast
// against the first opaque ground behind it; what sticks out sideways; the
// visible h1s and the headings smaller than what they head; the longest lines
// of prose. SVG text counts too, at the size it is drawn (its font-size
// attribute times the drawing's scale), because the vote rings' letters are
// set there and not in the stylesheet.
'use strict';
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const HOST_RULES = 'MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost, '
  + 'EXCLUDE fonts.googleapis.com, EXCLUDE fonts.gstatic.com';
const ALLOWED = /^(http:\/\/(127\.0\.0\.1|localhost)[:/]|data:|about:|blob:|chrome-error:|https:\/\/fonts\.(googleapis|gstatic)\.com\/)/;

const sleep = ms => new Promise(r => setTimeout(r, ms));
const say = m => process.stderr.write(m + '\n');

async function startChrome(chrome, profile) {
  fs.mkdirSync(profile, { recursive: true });
  const args = ['--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + profile,
    '--host-resolver-rules=' + HOST_RULES,
    '--disable-background-networking', '--disable-component-update', '--disable-sync',
    '--disable-default-apps', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-domain-reliability',
    '--disable-client-side-phishing-detection', '--metrics-recording-only', '--no-pings',
    '--disable-features=OptimizationHints,MediaRouter,Translate,AutofillServerCommunication',
    '--force-color-profile=srgb', '--hide-scrollbars', '--window-size=1366,900', 'about:blank'];
  const proc = spawn(chrome, args, { stdio: 'ignore' });
  const portFile = path.join(profile, 'DevToolsActivePort');
  let txt = null;
  for (let i = 0; i < 300 && !txt; i++) {
    await sleep(100);
    try {
      const t = fs.readFileSync(portFile, 'utf8');
      if (t.split('\n').length >= 2) txt = t;
    } catch (e) { /* not written yet */ }
  }
  if (!txt) { proc.kill(); throw new Error('Chrome did not start (no DevToolsActivePort in 30s)'); }
  const [port, wsPath] = txt.trim().split('\n');
  const ws = new WebSocket(`ws://127.0.0.1:${port}${wsPath}`);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0;
  const pending = new Map(), listeners = [];
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const { res, rej } = pending.get(m.id);
      pending.delete(m.id);
      if (m.error) rej(new Error(m.error.message + ' ' + (m.error.data || ''))); else res(m.result);
    } else if (m.method) for (const l of listeners) l(m);
  };
  const send = (method, params = {}, sessionId) => new Promise((res, rej) => {
    const i = ++id;
    pending.set(i, { res, rej });
    ws.send(JSON.stringify({ id: i, method, params, sessionId }));
  });
  const on = fn => listeners.push(fn);
  const version = await send('Browser.getVersion');
  const close = async () => {
    try { await send('Browser.close'); } catch (e) { /* already gone */ }
    await sleep(600);
    try { proc.kill(); } catch (e) { /* already gone */ }
  };
  return { send, on, close, version: version.product };
}

async function newPage(browser) {
  const { targetId } = await browser.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await browser.send('Target.attachToTarget', { targetId, flatten: true });
  const S = (m, p) => browser.send(m, p, sessionId);
  await S('Page.enable'); await S('Runtime.enable'); await S('Network.enable');
  await S('Network.setCacheDisabled', { cacheDisabled: true });
  const st = { inflight: new Set(), outside: [], failed: [], errors: [], lastNet: Date.now(), loaded: false };
  browser.on(m => {
    if (m.sessionId !== sessionId) return;
    const p = m.params;
    if (m.method === 'Network.requestWillBeSent') {
      st.inflight.add(p.requestId); st.lastNet = Date.now();
      if (!ALLOWED.test(p.request.url)) st.outside.push(p.request.url.slice(0, 200));
    } else if (m.method === 'Network.loadingFinished' || m.method === 'Network.loadingFailed') {
      st.inflight.delete(p.requestId); st.lastNet = Date.now();
    } else if (m.method === 'Network.responseReceived') {
      if (p.response.status >= 400 && /^http:\/\/(127\.0\.0\.1|localhost)/.test(p.response.url)) {
        st.failed.push(p.response.status + ' ' + p.response.url.replace(/^http:\/\/[^/]+/, ''));
      }
    } else if (m.method === 'Page.loadEventFired') {
      st.loaded = true;
    } else if (m.method === 'Runtime.exceptionThrown') {
      const d = p.exceptionDetails;
      st.errors.push(String((d.exception && d.exception.description) || d.text).slice(0, 300));
    }
  });
  const settle = async (quiet = 500, max = 20000) => {
    const t0 = Date.now();
    while (Date.now() - t0 < max) {
      if (st.loaded && st.inflight.size === 0 && Date.now() - st.lastNet > quiet) return true;
      await sleep(100);
    }
    return false;
  };
  const evaluate = async expr => {
    const r = await S('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true, userGesture: true });
    if (r.exceptionDetails) {
      const d = r.exceptionDetails;
      throw new Error('in the page: ' + ((d.exception && d.exception.description) || d.text));
    }
    return r.result.value;
  };
  const goto = async url => {
    st.inflight.clear(); st.outside = []; st.failed = []; st.errors = [];
    st.loaded = false; st.lastNet = Date.now();
    await S('Page.navigate', { url });
    const ok = await settle();
    await evaluate('document.fonts.ready.then(() => 1)');
    await sleep(400);
    return ok;
  };
  return { S, st, settle, evaluate, goto };
}

// One view: the width and the device, the theme, forced colours, and the
// browser's own default text size (Settings > Appearance > Font size).
async function setView(pg, run) {
  const mobile = !!run.mobile;
  await pg.S('Emulation.setDeviceMetricsOverride',
    { width: run.width, height: run.height, deviceScaleFactor: 1, mobile });
  await pg.S('Emulation.setTouchEmulationEnabled', { enabled: mobile, maxTouchPoints: mobile ? 5 : 1 });
  await pg.S('Emulation.setEmulatedMedia', { features: [
    { name: 'prefers-color-scheme', value: run.mode === 'dark' ? 'dark' : 'light' },
    { name: 'forced-colors', value: run.mode === 'forced' ? 'active' : 'none' },
    { name: 'prefers-reduced-motion', value: 'reduce' }] });
  const std = run.standard || 16;
  await pg.S('Page.setFontSizes', { fontSizes: { standard: std, fixed: Math.round(std * 13 / 16) } });
}

// The steps that open a state of a page: a tab, or a button.
async function act(pg, steps) {
  const said = [];
  for (const s of steps || []) {
    const js = s.click
      ? `(()=>{const e=document.querySelector(${JSON.stringify(s.click)});if(!e)return null;e.click();return ${JSON.stringify(s.click)}})()`
      : `(()=>{const re=new RegExp(${JSON.stringify(s.tab)});const b=[...document.querySelectorAll('[role=tab]')].find(b=>re.test(b.textContent.trim())&&b.getClientRects().length);if(!b)return null;b.click();return b.textContent.trim()})()`;
    const got = await pg.evaluate(js);
    if (got === null) throw new Error('no ' + (s.click ? 'element ' + s.click : 'tab matching /' + s.tab + '/') + ' to open');
    said.push(got);
    await sleep(500);
    await pg.settle(400, 10000);
  }
  return said;
}

// ---------------------------------------------------------------- in the page --
// Reads only. Serialised with toString() and run by Runtime.evaluate, so it
// may use nothing from this file.
function measure(opts) {
  const de = document.documentElement;
  const vw = de.clientWidth;
  const std = opts.standard || 16;
  const txt = s => (s || '').replace(/\s+/g, ' ').trim();
  const cut = (s, n) => { s = txt(s); return s.length > n ? s.slice(0, n) + '…' : s; };
  const one = e => {
    let s = e.tagName.toLowerCase();
    if (e.id && !/\d{2,}/.test(e.id)) return s + '#' + e.id;
    const c = (e.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).slice(0, 2);
    return c.length ? s + '.' + c.join('.') : s;
  };
  const sig = el => {
    const parts = [];
    for (let e = el, i = 0; i < 3 && e && e.nodeType === 1 && e !== document.body; i++, e = e.parentElement) parts.unshift(one(e));
    return parts.join(' > ');
  };
  const isVis = el => {
    if (el.checkVisibility && !el.checkVisibility({ checkVisibilityCSS: true, checkOpacity: true })) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  // Text a screen reader gets and a reader does not: one pixel, clipped
  // away, or put beyond the left edge, where no scrolling reaches it (the
  // skip link until it has focus).
  const srOnly = el => {
    const r = el.getBoundingClientRect();
    if (r.width <= 2 || r.height <= 2 || r.right <= 0) return true;
    for (let e = el, i = 0; i < 4 && e && e.nodeType === 1; i++, e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.clipPath && /inset\((50|100)%/.test(cs.clipPath)) return true;
      if (cs.clip && /rect\(0(px)?,? 0(px)?,? 0(px)?,? 0(px)?\)|rect\(1px,? 1px,? 1px,? 1px\)/.test(cs.clip)) return true;
      if (/(^|\s)(sr|sr-only|visually-hidden)(\s|$)/.test(e.getAttribute('class') || '')) return true;
    }
    return false;
  };
  // ---- colour, by WCAG 2's arithmetic
  const cctx = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
  const cache = new Map();
  const rgba = s => {
    if (cache.has(s)) return cache.get(s);
    let v;
    const m = /^rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)$/.exec(s);
    if (m) v = [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
    else {
      cctx.clearRect(0, 0, 1, 1); cctx.fillStyle = '#000'; cctx.fillStyle = s; cctx.fillRect(0, 0, 1, 1);
      const d = cctx.getImageData(0, 0, 1, 1).data;
      v = [d[0], d[1], d[2], d[3] / 255];
    }
    cache.set(s, v);
    return v;
  };
  const over = (f, b) => [0, 1, 2].map(i => f[i] * f[3] + b[i] * (1 - f[3])).concat(1);
  const lum = c => { const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const hex = c => '#' + [0, 1, 2].map(i => Math.round(c[i]).toString(16).padStart(2, '0')).join('');
  const rootBg = (() => {
    let c = rgba(getComputedStyle(de).backgroundColor);
    if (c[3] === 0) c = rgba(getComputedStyle(document.body).backgroundColor);
    return c[3] < 1 ? over(c, [255, 255, 255, 1]) : c;
  })();
  const bgCache = new Map();
  // The first opaque ground up the ancestors, with the translucent ones on
  // the way composited over it. A ground drawn by an image or a gradient is
  // not a colour: the run says so beside the ratio (`img`).
  const bgOf = el => {
    if (bgCache.has(el)) return bgCache.get(el);
    const stack = [];
    let img = false;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none'
          && !/^linear-gradient\((transparent|rgba\(0, 0, 0, 0\))/.test(cs.backgroundImage)) img = true;
      const c = rgba(cs.backgroundColor);
      if (c[3] > 0) { stack.push(c); if (c[3] === 1) break; }
    }
    let b = rootBg;
    if (stack.length && stack[stack.length - 1][3] === 1) b = stack.pop();
    while (stack.length) b = over(stack.pop(), b);
    const r = { c: b, img };
    bgCache.set(el, r);
    return r;
  };
  const opacityOf = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };

  // ---- what kind of text, roughly, so the floors can be read by role later
  const chipRe = /(^|\s)([\w-]*chip[\w-]*|badge|pill|sgn|mtag|cstat|rcres|calkind|btv|stat|vcast|pass|fail)(\s|$)/;
  const roleOf = (el, cs) => {
    if (el.closest('h1,h2,h3,h4,h5,h6,[role=heading]')) return 'heading';
    if (el.closest('nav.top, body > header, a.skip')) return 'nav';
    if (el.closest('body > footer, footer.site')) return 'footer';
    if (el.closest('.rail')) return 'rail';
    for (let e = el, i = 0; i < 3 && e && e.nodeType === 1; i++, e = e.parentElement) if (chipRe.test(e.getAttribute('class') || '')) return 'chip';
    if (el.closest('svg')) return 'chart';
    if (el.closest('th')) return 'column head';
    if (el.closest('td')) return 'table cell';
    if (el.closest('button,select,input,textarea,label,summary,[role=tab],[role=button],option')) return 'control';
    if (cs.textTransform === 'uppercase' || el.closest('dt,legend')) return 'label';
    if (el.closest('figcaption,caption,small,.note,.meta,.sub,.hint,.dim,.src,.fine,.cnote,.crumb')) return 'note';
    if (el.closest('p,li,dd,blockquote,.prose')) return 'body';
    return 'other';
  };

  // ---- the census: every element that owns text
  const owners = new Map();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) {
    const t = txt(n.nodeValue);
    if (!t) continue;
    const p = n.parentElement;
    if (!p || p.closest('script,style,noscript,template,title,desc')) continue;
    owners.set(p, (owners.get(p) || '') + ' ' + t);
  }
  const sizes = {}, roles = {}, fails = [], decorative = [], small = {}, mixed13 = {};
  let elements = 0, chars = 0, minSize = 1e9, minAt = null, low = null, measured = 0, imgGround = 0;
  const failSeen = new Set();
  const fontLabel = cs => cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
  for (const [el, own] of owners) {
    if (!isVis(el) || srOnly(el)) continue;
    const cs = getComputedStyle(el);
    const svg = el instanceof SVGElement;
    let px = parseFloat(cs.fontSize);
    if (svg) {
      const m = el.getScreenCTM && el.getScreenCTM();
      if (m) px *= Math.hypot(m.a, m.b);
    }
    px = Math.round(px * 100) / 100;
    // The size as it would be at the browser's default of 16px: the floors
    // are set there, and a page that follows the reader's setting scales
    // with it (opts.standard).
    const at16 = Math.round(px * 16 / std * 100) / 100;
    const weight = +cs.fontWeight;
    const t = txt(own);
    const n = t.length;
    const role = roleOf(el, cs);
    const s = sig(el);
    elements++; chars += n;
    sizes[at16] = (sizes[at16] || 0) + n;
    const ro = roles[role] || (roles[role] = { el: 0, chars: 0, under16: 0, under14: 0, under13: 0, min: 1e9 });
    ro.el++; ro.chars += n; ro.min = Math.min(ro.min, at16);
    if (at16 < 16) ro.under16 += n;
    if (at16 < 14) ro.under14 += n;
    if (at16 < 13) ro.under13 += n;
    if (at16 < minSize) { minSize = at16; minAt = { sig: s, text: cut(t, 40), px, font: fontLabel(cs) }; }
    if (at16 < 13) { const k = s + ' @' + at16; small[k] = small[k] || { sig: s, at16, el: 0, chars: 0, text: cut(t, 30) }; small[k].el++; small[k].chars += n; }
    // 13px is the floor for capitals only (a label); mixed case under 14px
    // is read in passing and needs 14.
    if (at16 >= 13 && at16 < 14 && cs.textTransform !== 'uppercase' && /[a-z]/.test(t)) {
      const k = s; mixed13[k] = mixed13[k] || { sig: s, el: 0, text: cut(t, 30) }; mixed13[k].el++;
    }
    // ---- contrast
    const paint = svg ? cs.fill : cs.color;
    if (!paint || /^url|^none/.test(paint)) continue;
    const fg0 = rgba(paint);
    const op = opacityOf(el);
    const bg = bgOf(svg ? (el.ownerSVGElement || el).parentElement || el : el);
    const fg = over([fg0[0], fg0[1], fg0[2], fg0[3] * op], bg.c);
    const r = ratio(fg, bg.c);
    // WCAG's large text is a drawn size, whatever the reader's setting.
    const large = px >= 24 || (px >= 18.66 && weight >= 700);
    const need = large ? 3 : 4.5;
    // A glyph with no letter or digit in it (a separator, an arrow) carries
    // nothing to read; it is listed, not judged.
    if (!/[\p{L}\p{N}]/u.test(t)) {
      if (r < need - 0.005 && decorative.length < 20) decorative.push({ sig: s, text: cut(t, 12), ratio: Math.round(r * 100) / 100 });
      continue;
    }
    measured++;
    if (bg.img) imgGround++;
    if (!low || r / need < low.ratio / low.need) low = { sig: s, text: cut(t, 40), ratio: Math.round(r * 100) / 100, need, fg: hex(fg), bg: hex(bg.c) };
    if (r < need - 0.005) {
      const k = s + hex(fg) + hex(bg.c);
      if (!failSeen.has(k)) {
        failSeen.add(k);
        fails.push({ sig: s, text: cut(t, 50), px, weight, fg: hex(fg), bg: hex(bg.c), ratio: Math.round(r * 100) / 100, need, opacity: Math.round(op * 100) / 100, img: bg.img });
      }
    }
  }

  // ---- headings: the visible h1s, and a heading smaller than what it heads
  const h1 = [...document.querySelectorAll('h1')].filter(h => isVis(h) && !srOnly(h))
    .map(h => ({ text: cut(h.textContent, 60), px: parseFloat(getComputedStyle(h).fontSize), sig: sig(h) }));
  const rank = [];
  for (const h of document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role=heading]')) {
    if (!isVis(h) || srOnly(h)) continue;
    const hc = getComputedStyle(h), hs = parseFloat(hc.fontSize), hw = +hc.fontWeight;
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    tw.currentNode = h;
    let next = null;
    for (let m, g = 0; (m = tw.nextNode()) && g < 400; g++) {
      if (h.contains(m) || !txt(m.nodeValue)) continue;
      const p = m.parentElement;
      if (!p || !isVis(p) || srOnly(p)) continue;
      if (p.closest('h1,h2,h3,h4,h5,h6,[role=heading]')) break;
      next = p; break;
    }
    if (!next) continue;
    const nc = getComputedStyle(next), ns = parseFloat(nc.fontSize), nw = +nc.fontWeight;
    if (hs < ns - 0.4 || (Math.abs(hs - ns) <= 0.4 && hw <= nw)) {
      rank.push({ heading: cut(h.textContent, 40), sig: sig(h), px: hs, next: cut(next.textContent, 40), nextSig: sig(next), nextPx: ns });
    }
  }

  // ---- lines of prose: characters a line, for paragraphs of 160 or more
  const lines = [];
  for (const el of document.querySelectorAll('p, li, dd, blockquote')) {
    if (lines.length > 400) break;
    if (el.querySelector('p,li,ul,ol,div,table')) continue;
    const t = txt(el.innerText || '');
    if (t.length < 160 || !isVis(el) || srOnly(el)) continue;
    const rg = document.createRange();
    rg.selectNodeContents(el);
    const tops = [];
    for (const r of rg.getClientRects()) if (r.width >= 2 && !tops.some(y => Math.abs(y - r.top) < 4)) tops.push(r.top);
    if (tops.length < 2) continue;
    lines.push({ sig: sig(el), cpl: Math.round(t.length / tops.length), lines: tops.length });
  }
  lines.sort((a, b) => b.cpl - a.cpl);

  // ---- what sticks out sideways
  const poking = [], scrollers = [], clipped = [];
  const flagged = new Set();
  for (const e of document.querySelectorAll('body *')) {
    if (e.checkVisibility && !e.checkVisibility({ checkVisibilityCSS: true })) continue;
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const cs = getComputedStyle(e);
    if ((r.right > vw + 1 || (r.left < -1 && r.right > 0)) && cs.position !== 'fixed' && !srOnly(e)) {
      let held = false;
      for (let p = e.parentElement; p && p !== document.body && p !== de; p = p.parentElement) {
        if (flagged.has(p)) { held = true; break; }
        if (/(auto|scroll|hidden|clip)/.test(getComputedStyle(p).overflowX)) { held = true; break; }
      }
      if (!held) { flagged.add(e); poking.push({ sig: sig(e), left: Math.round(r.left), right: Math.round(r.right), by: Math.round(Math.max(r.right - vw, -r.left)) }); }
    }
    if (/(auto|scroll)/.test(cs.overflowX) && e.scrollWidth > e.clientWidth + 2) {
      scrollers.push({ sig: sig(e), scrollWidth: e.scrollWidth, width: e.clientWidth });
    }
    if (/(hidden|clip)/.test(cs.overflowX) && e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 2
        && txt(e.textContent).length && !e.querySelector('iframe,svg,canvas,img,video') && !srOnly(e)) {
      clipped.push({ sig: sig(e), scrollWidth: e.scrollWidth, width: e.clientWidth, ellipsis: cs.textOverflow === 'ellipsis', text: cut(e.textContent, 40) });
    }
  }
  // A placeholder wider than its box is cut off where a reader starts.
  const placeholders = [];
  for (const f of document.querySelectorAll('input[placeholder], textarea[placeholder]')) {
    if (!isVis(f) || !f.placeholder) continue;
    const cs = getComputedStyle(f);
    cctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const need = cctx.measureText(f.placeholder).width;
    const room = f.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    placeholders.push({ sig: sig(f), text: f.placeholder, need: Math.round(need), room: Math.round(room), fits: need <= room + 0.5 });
  }

  const fontsLoaded = [...new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/"/g, '') + ' ' + f.weight))].sort();
  const fontsFailed = [...new Set([...document.fonts].filter(f => f.status === 'error').map(f => f.family.replace(/"/g, '') + ' ' + f.weight))].sort();
  const top = (o, k) => Object.values(o).sort((a, b) => (b.chars || b.el) - (a.chars || a.el)).slice(0, k);
  return {
    title: document.title, rootPx: parseFloat(getComputedStyle(de).fontSize),
    width: vw, docWidth: de.scrollWidth, docHeight: de.scrollHeight,
    fontsLoaded, fontsFailed,
    text: { elements, chars, sizes, roles, min: minSize === 1e9 ? null : minSize, minAt,
      small: top(small, 25), mixedCase13: top(mixed13, 15) },
    contrast: { measured, imgGround, failures: fails.length, fails: fails.slice(0, 40), lowest: low, decorative },
    headings: { h1, rank: rank.slice(0, 20) },
    lines: { paragraphs: lines.length, over80: lines.filter(l => l.cpl > 80).length, widest: lines.slice(0, 5) },
    overflow: { sideways: de.scrollWidth > vw + 1, poking: poking.slice(0, 25), scrollers: scrollers.slice(0, 15),
      clipped: clipped.slice(0, 15), placeholders },
  };
}

// -------------------------------------------------------------------- the runs --
(async () => {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  if (job.shots) fs.mkdirSync(job.shots, { recursive: true });
  const browser = await startChrome(job.chrome, job.profile);
  process.stdout.write(JSON.stringify({ browser: browser.version, hostRules: HOST_RULES }) + '\n');
  let pg = await newPage(browser);
  try {
    for (const run of job.runs) {
      const t0 = Date.now();
      const out = { id: run.id, page: run.page, width: run.width, mode: run.mode, path: run.path };
      try {
        await setView(pg, run);
        out.settled = await pg.goto(job.base + run.path);
        out.opened = await act(pg, run.steps);
        out.m = await pg.evaluate(`(${measure.toString()})(${JSON.stringify({ standard: run.standard || 16 })})`);
        if (job.shots) {
          await pg.evaluate('window.scrollTo(0, 0)');
          const lm = await pg.S('Page.getLayoutMetrics');
          const h = Math.max(1, Math.min(job.shotCap || 2400, Math.ceil(lm.cssContentSize.height)));
          const shot = await pg.S('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
            clip: { x: 0, y: 0, width: run.width, height: h, scale: 1 } });
          out.shot = run.id + '.png';
          fs.writeFileSync(path.join(job.shots, out.shot), Buffer.from(shot.data, 'base64'));
        }
      } catch (e) {
        out.error = String(e.message || e).slice(0, 400);
        // A page that broke the tab is not left to break the next run too.
        try { pg = await newPage(browser); } catch (e2) { /* the next run will say */ }
      }
      out.outside = [...new Set(pg.st.outside)].slice(0, 20);
      out.failed = pg.st.failed.slice(0, 20);
      out.errors = pg.st.errors.slice(0, 5);
      out.seconds = Math.round((Date.now() - t0) / 100) / 10;
      process.stdout.write(JSON.stringify(out) + '\n');
      say(`${run.id}  ${out.error ? 'ERROR ' + out.error.slice(0, 120) : out.seconds + 's'}`);
    }
  } finally {
    await browser.close();
  }
})().catch(e => { say('sweep_browser: ' + (e.stack || e)); process.exit(1); });
