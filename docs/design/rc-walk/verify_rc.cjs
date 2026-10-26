// Walk the release candidate's preview: each stop's page, what it must say and must not.
// node verify_rc.cjs [filter]   -> one line per stop, PASS or FAIL with the evidence
const { open } = require('./site.cjs');
const STOPS = [
  { path: '/bill/2025/hb282/votes', width: 390, why: 'M1 vote date opens the day at the bill',
    js: `[...document.querySelectorAll('a')].filter(a=>/Feb 20, 2025/.test(a.textContent)).map(a=>a.getAttribute('href'))`,
    ok: v => v.length && v.every(h => /session\/H\/2025-02-20#HB282$/.test(h) && !/\.html/.test(h)) },
  { path: '/bill/2026/sb406', why: 'M2 Senate hearing counted', js: `[...document.querySelectorAll('details.testify')].map(d=>d.textContent).join(' ')`, ok: v => /Online testimony for this bill has passed/.test(v) && !/has not opened yet/.test(v) },
  { path: '/bill/2025/hb282', why: 'M2 no "opens again"', js: `[...document.querySelectorAll('details.testify')].map(d=>d.textContent).join(' ')`, ok: v => /its last public hearing was/.test(v) && !/opens again/.test(v) },
  { path: '/bill/1997/hb200/votes', why: 'S4 pre-1999 Votes tab', has: [/Named roll calls here begin in 1999/] },
  { path: '/bill/2017/hb520', why: 'S4 Died over In committee', has: [/Died when the session ended/] },
  { path: '/bill/2026/hb131/hearings', why: 'S2 recording cards', has: [/Two recordings that day/], not: [/window opens/, /timed to the second/] },
  { path: '/search?q=RSA%2091-A', why: 'M3 search finds a law', has: [/RSA 91-A/, /Access to Governmental Records/] },
  { path: '/town/concord', why: 'M4 city address redirects', redirect: /\/officials\?town=Concord$/ },
  { path: '/guides', why: 'S6 /guides redirects', redirect: /\/resources$/ },
  { path: '/town/acworth', width: 390, why: 'M6 short tabs, no sideways scroll',
    js: `({tabs:[...document.querySelectorAll('.twntabs [role=tab]')].map(t=>t.textContent.trim()), sw:document.scrollingElement.scrollWidth})`,
    ok: v => v.tabs.join('|') === 'Representatives|Map|Officials|Vote|Services' && v.sw <= 390 },
  { path: '/town/gilford', why: 'S4 vacant seat count', has: [/1 seat vacant/] },
  { path: '/', why: 'home players back (26 Oct)', has: [/Recent Session Days/i, /House Session \(Aug 19, 2026\)/], not: [/August 19th/, /sits mostly from January to June/],
    js: `[...document.querySelectorAll('#session button.pstub')].length`, ok: v => v === 2 },
  { path: '/bills', width: 390, why: 'M7 25 cards at a time',
    js: `document.querySelectorAll('#results .card, #results article').length`, ok: v => v > 0 && v <= 25 },
  { path: '/calendar', why: 'S7 plain room names', not: [/GP Room \d/, /\bGP \d{3}\b/] },
  { path: '/learn/by-the-numbers', width: 390, why: 'S9 wide table scrolls in its box',
    js: `[...document.querySelectorAll('.l-tablewrap > table')].map(t=>getComputedStyle(t).display)`,
    ok: v => v.length && v.every(d => d === 'table') },
  { path: '/bill/2026/hb1442', width: 390, why: 'S9 Report fits on a phone', has: [/\bReport\b/] },
  { path: '/guides/fishing-license', why: 'outdoor guide built', js: `document.title`, ok: (v, s) => s === 200 && !/not found/i.test(v) },
  { path: '/guides/hunting-license', why: 'outdoor guide built', js: `document.title`, ok: (v, s) => s === 200 && !/not found/i.test(v) },
  { path: '/guides/boating', why: 'outdoor guide built', js: `document.title`, ok: (v, s) => s === 200 && !/not found/i.test(v) },
  { path: '/town/acworth', why: 'transfer station card', js: `document.querySelector('#services') ? document.querySelector('#services').innerText : ''`,
    ok: v => /Transfer station/i.test(v) && /NH DES/.test(v) },
];
(async () => {
  const only = process.argv[2];
  let fails = 0;
  for (const s of STOPS) {
    if (only && !s.path.includes(only) && !s.why.includes(only)) continue;
    let line;
    if (s.redirect) { // a redirect escapes the browser's route: ask with fetch, which the proxy carries
      const r = await fetch(require('./site.cjs').B + s.path, { redirect: 'manual' });
      const loc = r.headers.get('location') || ''; const pass = r.status >= 300 && r.status < 400 && s.redirect.test(loc);
      if (!pass) fails++; console.log(`${pass ? 'PASS' : 'FAIL'} ${s.path} [${s.why}] status=${r.status} location=${loc}`); continue;
    }
    try {
      const { b, p, status, errors } = await open(s.path, s.width || 1280);
      const text = await p.evaluate(() => document.body.innerText);
      const v = s.js ? await p.evaluate(s.js) : null;
      const miss = (s.has || []).filter(r => !r.test(text)).map(String);
      const extra = (s.not || []).filter(r => r.test(text)).map(String);
      const okjs = s.ok ? s.ok(v, status) : true;
      const pass = status < 400 && !miss.length && !extra.length && okjs;
      if (!pass) fails++;
      line = `${pass ? 'PASS' : 'FAIL'} ${s.path} @${s.width || 1280} [${s.why}] status=${status}`
        + (miss.length ? ` missing=${miss.join(',')}` : '') + (extra.length ? ` present=${extra.join(',')}` : '')
        + (s.js ? ` value=${JSON.stringify(v).slice(0, 200)}` : '') + (errors.length ? ` errors=${errors.slice(0, 2).join(' | ').slice(0, 200)}` : '');
      await b.close();
    } catch (e) { fails++; line = `FAIL ${s.path} [${s.why}] ${String(e).slice(0, 200)}`; }
    console.log(line);
  }
  console.log(`${fails} failed`);
})();
